import AVFoundation

/// Records audio to a file for Precision Mode (server-side cloud transcription).
/// Detects silence via audio metering and auto-stops after a pause, mirroring
/// Live Mode's silence-based auto-send.
final class AudioRecorderManager: NSObject {
    /// Called once silence has been detected for `silenceThreshold` after some speech was heard.
    var onPauseDetected: ((URL) -> Void)?

    private let silenceThreshold: TimeInterval = 1.5
    private let silenceLevelThreshold: Float = -35 // dBFS; below this is treated as silence
    private let meteringInterval: TimeInterval = 0.1

    private var recorder: AVAudioRecorder?
    private(set) var currentFileURL: URL?
    private var meteringTimer: Timer?
    private var silenceStartedAt: Date?
    private var hasHeardSpeech = false

    func requestPermission() async -> Bool {
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

    func startRecording() throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .default, options: .defaultToSpeaker)
        try session.setActive(true)

        let fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("recording-\(UUID().uuidString).m4a")

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]

        let newRecorder = try AVAudioRecorder(url: fileURL, settings: settings)
        newRecorder.isMeteringEnabled = true
        newRecorder.record()
        recorder = newRecorder
        currentFileURL = fileURL

        hasHeardSpeech = false
        silenceStartedAt = nil
        startMetering()
    }

    /// Stops recording and returns the file URL, or nil if nothing was recording.
    @discardableResult
    func stopRecording() -> URL? {
        stopMetering()
        guard recorder != nil else { return nil }
        recorder?.stop()
        let url = currentFileURL
        recorder = nil
        currentFileURL = nil
        return url
    }

    private func startMetering() {
        meteringTimer?.invalidate()
        meteringTimer = Timer.scheduledTimer(withTimeInterval: meteringInterval, repeats: true) { [weak self] _ in
            self?.checkAudioLevel()
        }
    }

    private func stopMetering() {
        meteringTimer?.invalidate()
        meteringTimer = nil
        silenceStartedAt = nil
    }

    private func checkAudioLevel() {
        guard let recorder else { return }
        recorder.updateMeters()
        let level = recorder.averagePower(forChannel: 0)

        if level > silenceLevelThreshold {
            hasHeardSpeech = true
            silenceStartedAt = nil
            return
        }

        guard hasHeardSpeech else { return }

        if let silenceStartedAt {
            if Date().timeIntervalSince(silenceStartedAt) >= silenceThreshold {
                let fileURL = currentFileURL
                stopRecording()
                if let fileURL {
                    onPauseDetected?(fileURL)
                }
            }
        } else {
            silenceStartedAt = Date()
        }
    }
}
