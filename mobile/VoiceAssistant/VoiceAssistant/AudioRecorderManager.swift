import AVFoundation

/// Records audio to a file for Precision Mode (server-side cloud transcription).
final class AudioRecorderManager: NSObject {
    private var recorder: AVAudioRecorder?
    private(set) var currentFileURL: URL?

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

        recorder = try AVAudioRecorder(url: fileURL, settings: settings)
        recorder?.record()
        currentFileURL = fileURL
    }

    /// Stops recording and returns the file URL, or nil if nothing was recording.
    @discardableResult
    func stopRecording() -> URL? {
        guard recorder != nil else { return nil }
        recorder?.stop()
        let url = currentFileURL
        recorder = nil
        currentFileURL = nil
        return url
    }
}
