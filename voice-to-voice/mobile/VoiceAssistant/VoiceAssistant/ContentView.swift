import SwiftUI
import Combine

enum ListeningMode: String, CaseIterable, Identifiable {
    case precision = "Precision Mode"
    case live = "Live Mode"

    var id: String { rawValue }

    var subtitle: String {
        switch self {
        case .precision: return "Cloud transcription \u{2022} higher accuracy"
        case .live: return "On-device \u{2022} real-time transcript"
        }
    }

    var icon: String {
        switch self {
        case .precision: return "cloud.fill"
        case .live: return "bolt.fill"
        }
    }
}

private enum ConversationState {
    case idle
    case listening
    case thinking
    case speaking
}

@MainActor
final class ConversationViewModel: ObservableObject {
    @Published var mode: ListeningMode = .live {
        didSet {
            guard oldValue != mode else { return }
            liveTranscript = ""
            lastUserText = ""
            lastResponseText = ""
        }
    }
    @Published var liveTranscript = ""
    @Published var lastUserText = ""
    @Published var lastResponseText = ""
    @Published var errorMessage: String?

    fileprivate var state: ConversationState = .idle {
        didSet {
            objectWillChange.send()
            guard oldValue != state else { return }
            if state == .speaking {
                startBargeInMonitor()
            } else if oldValue == .speaking {
                bargeInMonitor.stop()
            }
        }
    }

    /// True once the user has tapped the mic to begin a conversation session.
    /// Distinct from `state == .listening`: stays true across think/speak turns
    /// so the session auto-resumes listening after each response.
    private var sessionActive = false

    /// Each mode gets its own independent session/history — switching modes
    /// doesn't carry conversation context over, and switching back resumes
    /// that mode's own history rather than starting over.
    private var sessionIds: [ListeningMode: String] = [
        .live: UUID().uuidString,
        .precision: UUID().uuidString
    ]
    var sessionId: String { sessionIds[mode]! }

    let speechRecognizer = SpeechRecognizerManager()
    let audioRecorder = AudioRecorderManager()
    let audioPlayer = AudioPlayerManager()
    private let bargeInMonitor = BargeInMonitor()
    private var cancellables = Set<AnyCancellable>()

    private static let greeting = "Hey, what's on your mind today?"

    init() {
        // SpeechRecognizerManager is its own ObservableObject; ContentView only
        // observes this view model, so mirror its live partial-result updates
        // here or the transcript won't visibly update while the user is talking.
        speechRecognizer.$liveTranscript
            .receive(on: DispatchQueue.main)
            .assign(to: \.liveTranscript, on: self)
            .store(in: &cancellables)

        speechRecognizer.onPauseDetected = { [weak self] text in
            Task { @MainActor in
                await self?.sendText(text)
            }
        }
        audioRecorder.onPauseDetected = { [weak self] fileURL in
            Task { @MainActor in
                await self?.sendAudioFile(fileURL)
            }
        }
        audioPlayer.onPlaybackFinished = { [weak self] in
            Task { @MainActor in
                self?.playbackDidFinish()
            }
        }
        bargeInMonitor.onSpeechDetected = { [weak self] in
            Task { @MainActor in
                self?.handleBargeIn()
            }
        }
    }

    private func startBargeInMonitor() {
        do {
            try bargeInMonitor.start()
        } catch {
            // Barge-in is a nice-to-have; failing to start it shouldn't interrupt playback.
        }
    }

    private func handleBargeIn() {
        guard sessionActive, state == .speaking else { return }
        bargeInMonitor.stop()
        audioPlayer.stop()
        Task { await NetworkClient.shared.interrupt(sessionId: sessionId) }
        beginListening()
    }

    var isListening: Bool { state == .listening }
    var isThinking: Bool { state == .thinking }
    var isSpeaking: Bool { state == .speaking }
    var isIdle: Bool { state == .idle }

    func micButtonTapped() {
        if sessionActive {
            endSession()
        } else {
            startSession()
        }
    }

    private func startSession() {
        errorMessage = nil
        sessionActive = true
        lastResponseText = Self.greeting
        beginListening()
    }

    private func endSession() {
        sessionActive = false
        speechRecognizer.stopListening()
        audioRecorder.stopRecording()
        audioPlayer.stop()
        bargeInMonitor.stop()
        Task { await NetworkClient.shared.interrupt(sessionId: sessionId) }
        state = .idle
        liveTranscript = ""
    }

    private func beginListening() {
        liveTranscript = ""

        switch mode {
        case .live:
            Task {
                let authorized = await speechRecognizer.requestAuthorization()
                guard authorized else {
                    errorMessage = "Speech recognition permission denied."
                    sessionActive = false
                    return
                }
                do {
                    try speechRecognizer.startListening()
                    state = .listening
                } catch {
                    errorMessage = error.localizedDescription
                    sessionActive = false
                }
            }
        case .precision:
            Task {
                let granted = await audioRecorder.requestPermission()
                guard granted else {
                    errorMessage = "Microphone permission denied."
                    sessionActive = false
                    return
                }
                do {
                    try audioRecorder.startRecording()
                    state = .listening
                } catch {
                    errorMessage = error.localizedDescription
                    sessionActive = false
                }
            }
        }
    }

    /// Manual early-stop for Precision Mode, in case the user wants to send
    /// before the silence-based auto-send timer fires.
    func stopListeningManually() {
        guard mode == .precision, state == .listening else { return }
        guard let fileURL = audioRecorder.stopRecording() else { return }
        Task { await sendAudioFile(fileURL) }
    }

    private func playbackDidFinish() {
        guard sessionActive else { return }
        beginListening()
    }

    private func sendText(_ text: String) async {
        guard sessionActive else { return }
        lastUserText = text
        liveTranscript = ""
        state = .thinking
        do {
            try audioPlayer.startStream()
            let metadata = try await NetworkClient.shared.streamText(text, sessionId: sessionId) { [weak self] chunk in
                Task { @MainActor in
                    self?.state = .speaking
                    self?.audioPlayer.scheduleChunk(chunk)
                }
            }
            lastResponseText = metadata.responseText ?? ""
            audioPlayer.endStream()
        } catch {
            errorMessage = error.localizedDescription
            sessionActive = false
            state = .idle
        }
    }

    private func sendAudioFile(_ fileURL: URL) async {
        guard sessionActive else { return }
        state = .thinking
        do {
            try audioPlayer.startStream()
            let metadata = try await NetworkClient.shared.streamAudioFile(at: fileURL, sessionId: sessionId) { [weak self] chunk in
                Task { @MainActor in
                    self?.state = .speaking
                    self?.audioPlayer.scheduleChunk(chunk)
                }
            }
            lastUserText = metadata.userText ?? "(transcribed audio)"
            lastResponseText = metadata.responseText ?? ""
            audioPlayer.endStream()
        } catch {
            errorMessage = error.localizedDescription
            sessionActive = false
            state = .idle
        }
    }
}

struct ContentView: View {
    @StateObject private var viewModel = ConversationViewModel()

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 0) {
                modeToggle
                    .padding(.top, 8)

                Spacer()

                VoiceOrb(style: orbStyle, action: micTapped)

                Text(statusText)
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.7))
                    .padding(.top, 28)
                    .animation(.easeInOut, value: statusText)

                Spacer()

                captionArea
                    .padding(.bottom, 24)
            }
            .padding(.horizontal, 20)
        }
        .preferredColorScheme(.dark)
        .alert(
            "Something went wrong",
            isPresented: Binding(
                get: { viewModel.errorMessage != nil },
                set: { if !$0 { viewModel.errorMessage = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }

    private var modeToggle: some View {
        HStack(spacing: 8) {
            ForEach(ListeningMode.allCases) { mode in
                Button {
                    viewModel.mode = mode
                } label: {
                    Label(mode.rawValue, systemImage: mode.icon)
                        .font(.caption.weight(.medium))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(
                            Capsule().fill(viewModel.mode == mode ? Color.white.opacity(0.18) : .clear)
                        )
                        .foregroundStyle(viewModel.mode == mode ? .white : .white.opacity(0.5))
                }
                .disabled(!viewModel.isIdle)
            }
        }
        .padding(4)
        .background(Capsule().fill(Color.white.opacity(0.06)))
    }

    private var orbStyle: VoiceOrb.Style {
        if viewModel.isThinking { return .thinking }
        if viewModel.isSpeaking { return .speaking }
        if viewModel.isListening { return .listening }
        return .idle
    }

    private var statusText: String {
        if viewModel.isThinking { return "Thinking\u{2026}" }
        if viewModel.isSpeaking { return "Speaking \u{2014} tap to interrupt" }
        if viewModel.isListening {
            return viewModel.mode == .live ? "Listening \u{2014} pause when you're done" : "Tap again to send"
        }
        return "Tap to start talking"
    }

    private func micTapped() {
        if viewModel.mode == .precision && viewModel.isListening {
            viewModel.stopListeningManually()
        } else {
            viewModel.micButtonTapped()
        }
    }

    private var captionArea: some View {
        VStack(alignment: .leading, spacing: 14) {
            if !transcriptCaption.isEmpty {
                captionRow(icon: "person.wave.2.fill", text: transcriptCaption, color: .white.opacity(0.65))
            }
            if !viewModel.lastResponseText.isEmpty {
                captionRow(icon: "sparkle", text: viewModel.lastResponseText, color: .white)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func captionRow(icon: String, text: String, color: Color) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(color.opacity(0.8))
                .padding(.top, 3)

            Text(text)
                .font(.callout)
                .foregroundStyle(color)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var transcriptCaption: String {
        if viewModel.isListening && viewModel.mode == .live {
            return viewModel.liveTranscript
        }
        return viewModel.lastUserText
    }
}

#Preview {
    ContentView()
}
