import AVFoundation
import Speech

/// Drives Live Mode: on-device speech recognition with a live-updating transcript
/// and silence-based auto-send (pause detection).
final class SpeechRecognizerManager: NSObject, ObservableObject {
    @Published var liveTranscript = ""
    @Published var isListening = false

    /// Called with the final transcript once silence has been detected for `silenceThreshold`.
    var onPauseDetected: ((String) -> Void)?

    private let silenceThreshold: TimeInterval = 1.5

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()
    private var silenceTimer: Timer?

    /// Requests both speech-recognition and microphone permission. Live Mode needs both.
    func requestAuthorization() async -> Bool {
        let speechAuthorized = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
        guard speechAuthorized else { return false }

        if #available(iOS 17.0, *) {
            return await AVAudioApplication.requestRecordPermission()
        } else {
            return await withCheckedContinuation { continuation in
                AVAudioSession.sharedInstance().requestRecordPermission { granted in
                    continuation.resume(returning: granted)
                }
            }
        }
    }

    enum SpeechError: Error, LocalizedError {
        case recognizerUnavailable

        var errorDescription: String? {
            "Speech recognizer is unavailable right now. Check your internet connection or try again."
        }
    }

    func startListening() throws {
        stopListening()
        liveTranscript = ""

        print("[Speech] startListening called")

        guard let recognizer, recognizer.isAvailable else {
            print("[Speech] recognizer unavailable (recognizer=\(String(describing: recognizer)))")
            throw SpeechError.recognizerUnavailable
        }
        print("[Speech] recognizer available, locale=\(recognizer.locale.identifier)")

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.record, mode: .measurement, options: .duckOthers)
        try session.setActive(true, options: .notifyOthersOnDeactivation)
        print("[Speech] audio session category set, route inputs=\(session.currentRoute.inputs)")

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        recognitionRequest = request

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        print("[Speech] input node format=\(recordingFormat)")

        var bufferCount = 0
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            bufferCount += 1
            if bufferCount % 20 == 1 {
                print("[Speech] tap received buffer #\(bufferCount), frameLength=\(buffer.frameLength)")
            }
            self?.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        try audioEngine.start()
        isListening = true
        print("[Speech] audioEngine started, isRunning=\(audioEngine.isRunning)")

        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let result {
                self.liveTranscript = result.bestTranscription.formattedString
                print("[Speech] partial result: \(self.liveTranscript)")
                self.resetSilenceTimer()
            }
            if let error {
                print("[Speech] recognitionTask error: \(error)")
                self.stopListening()
            }
        }

        resetSilenceTimer()
    }

    func stopListening() {
        silenceTimer?.invalidate()
        silenceTimer = nil

        if audioEngine.isRunning {
            audioEngine.stop()
            audioEngine.inputNode.removeTap(onBus: 0)
        }
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        isListening = false
    }

    private func resetSilenceTimer() {
        silenceTimer?.invalidate()
        guard !liveTranscript.isEmpty else { return }
        silenceTimer = Timer.scheduledTimer(withTimeInterval: silenceThreshold, repeats: false) { [weak self] _ in
            guard let self, !self.liveTranscript.isEmpty else { return }
            let finalText = self.liveTranscript
            self.stopListening()
            self.onPauseDetected?(finalText)
        }
    }
}
