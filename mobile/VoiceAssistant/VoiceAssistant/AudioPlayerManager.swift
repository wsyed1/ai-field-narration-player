import AVFoundation

/// Plays streamed 16-bit PCM audio (24kHz mono, matching the backend's OpenAI TTS
/// stream) as chunks arrive over the network, instead of waiting for the full
/// response to download.
final class AudioPlayerManager: NSObject, ObservableObject {
    @Published var isPlaying = false

    /// Called once all scheduled audio has finished playing (not on interrupt/stop).
    var onPlaybackFinished: (() -> Void)?

    private let engine = AVAudioEngine()
    private let playerNode = AVAudioPlayerNode()
    private let format: AVAudioFormat

    private var pendingBufferCount = 0
    private var didFinishNaturally = false

    override init() {
        // Matches the backend's stream_speech_pcm: 16-bit signed little-endian, 24kHz, mono.
        format = AVAudioFormat(
            commonFormat: .pcmFormatInt16,
            sampleRate: 24000,
            channels: 1,
            interleaved: true
        )!
        super.init()
        engine.attach(playerNode)
        engine.connect(playerNode, to: engine.mainMixerNode, format: format)
    }

    /// Call once before feeding the first chunk of a new response.
    func startStream() throws {
        stop()
        didFinishNaturally = false

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playback, mode: .default)
        try session.setActive(true)

        if !engine.isRunning {
            try engine.start()
        }
        playerNode.play()
        isPlaying = true
    }

    /// Feed one chunk of raw PCM bytes as it arrives from the network.
    func scheduleChunk(_ data: Data) {
        guard let buffer = makeBuffer(from: data) else { return }
        pendingBufferCount += 1
        playerNode.scheduleBuffer(buffer) { [weak self] in
            DispatchQueue.main.async {
                guard let self else { return }
                self.pendingBufferCount -= 1
                if self.pendingBufferCount == 0 && self.didFinishNaturally {
                    self.isPlaying = false
                    self.onPlaybackFinished?()
                }
            }
        }
    }

    /// Call once no more chunks are coming (the network stream ended normally).
    func endStream() {
        didFinishNaturally = true
        if pendingBufferCount == 0 {
            isPlaying = false
            onPlaybackFinished?()
        }
    }

    /// Stops playback immediately (barge-in interrupt). Does not fire onPlaybackFinished.
    func stop() {
        didFinishNaturally = false
        pendingBufferCount = 0
        playerNode.stop()
        isPlaying = false
    }

    private func makeBuffer(from data: Data) -> AVAudioPCMBuffer? {
        let bytesPerFrame = 2 // 16-bit mono
        let frameCount = UInt32(data.count / bytesPerFrame)
        guard frameCount > 0,
              let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frameCount) else {
            return nil
        }
        buffer.frameLength = frameCount

        data.withUnsafeBytes { rawBuffer in
            guard let source = rawBuffer.bindMemory(to: Int16.self).baseAddress else { return }
            let destination = buffer.int16ChannelData![0]
            destination.update(from: source, count: Int(frameCount))
        }
        return buffer
    }
}
