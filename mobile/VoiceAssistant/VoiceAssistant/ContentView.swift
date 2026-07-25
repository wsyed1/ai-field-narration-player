import SwiftUI

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
}

private enum ConversationState {
    case idle
    case listening
    case thinking
    case speaking
}

@MainActor
final class ConversationViewModel: ObservableObject {
    @Published var mode: ListeningMode = .live
    @Published var liveTranscript = ""
    @Published var lastUserText = ""
    @Published var lastResponseText = ""
    @Published var errorMessage: String?

    fileprivate var state: ConversationState = .idle {
        didSet { objectWillChange.send() }
    }

    /// True once the user has tapped the mic to begin a conversation session.
    /// Distinct from `state == .listening`: stays true across think/speak turns
    /// so the session auto-resumes listening after each response.
    private var sessionActive = false

    let sessionId = UUID().uuidString

    let speechRecognizer = SpeechRecognizerManager()
    let audioRecorder = AudioRecorderManager()
    let audioPlayer = AudioPlayerManager()

    private static let greeting = "Hey, what's on your mind today?"

    init() {
        speechRecognizer.onPauseDetected = { [weak self] text in
            Task { @MainActor in
                await self?.sendText(text)
            }
        }
        audioPlayer.onPlaybackFinished = { [weak self] in
            Task { @MainActor in
                self?.playbackDidFinish()
            }
        }
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

    /// Manual stop for Precision Mode, where recording length is user-controlled
    /// (Live Mode ends listening automatically via pause detection instead).
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
        NavigationStack {
            VStack(spacing: 24) {
                modePicker

                transcriptCard

                Spacer()

                micButton

                responseCard
            }
            .padding()
            .navigationTitle("Voice AI Assistant")
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
    }

    private var modePicker: some View {
        VStack(spacing: 4) {
            Picker("Mode", selection: $viewModel.mode) {
                ForEach(ListeningMode.allCases) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .disabled(!viewModel.isIdle)

            Text(viewModel.mode.subtitle)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var transcriptCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Live Transcript", systemImage: "waveform")
                .font(.subheadline.bold())
                .foregroundStyle(.secondary)

            Text(transcriptText)
                .font(.body)
                .frame(maxWidth: .infinity, minHeight: 80, alignment: .topLeading)
                .padding()
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }

    private var transcriptText: String {
        if viewModel.isListening {
            if viewModel.mode == .live {
                return viewModel.speechRecognizer.liveTranscript.isEmpty
                    ? "Listening..."
                    : viewModel.speechRecognizer.liveTranscript
            }
            return "Recording... tap the mic again to send."
        }
        return viewModel.lastUserText.isEmpty ? "Tap the mic to start talking." : viewModel.lastUserText
    }

    private var micButton: some View {
        VStack(spacing: 12) {
            Button(action: micTapped) {
                ZStack {
                    Circle()
                        .fill(micColor)
                        .frame(width: 96, height: 96)
                        .shadow(radius: 6)

                    if viewModel.isThinking {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Image(systemName: micIcon)
                            .font(.system(size: 36))
                            .foregroundStyle(.white)
                    }
                }
            }
            .animation(.easeInOut(duration: 0.15), value: micColor)

            Text(micStatusText)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private func micTapped() {
        if viewModel.mode == .precision && viewModel.isListening {
            viewModel.stopListeningManually()
        } else {
            viewModel.micButtonTapped()
        }
    }

    private var micColor: Color {
        if viewModel.isIdle { return .accentColor }
        if viewModel.isListening { return .red }
        return .orange
    }

    private var micIcon: String {
        viewModel.isIdle ? "mic.fill" : "stop.fill"
    }

    private var micStatusText: String {
        if viewModel.isThinking { return "Thinking..." }
        if viewModel.isSpeaking { return "Speaking \u{2014} tap mic to end" }
        if viewModel.isListening {
            return viewModel.mode == .live ? "Listening \u{2014} pause to send" : "Tap again to send"
        }
        return "Tap to speak"
    }

    private var responseCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("AI Response", systemImage: "text.bubble")
                .font(.subheadline.bold())
                .foregroundStyle(.secondary)

            Text(viewModel.lastResponseText.isEmpty ? "\u{2014}" : viewModel.lastResponseText)
                .font(.body)
                .frame(maxWidth: .infinity, minHeight: 80, alignment: .topLeading)
                .padding()
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }
}

#Preview {
    ContentView()
}
