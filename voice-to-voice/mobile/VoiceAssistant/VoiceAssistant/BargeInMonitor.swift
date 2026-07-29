import AVFoundation

/// Passively watches the mic while the assistant is speaking. If the user's
/// voice crosses a volume threshold, fires `onSpeechDetected` so playback can
/// stop and a fresh listening turn can begin — no tap required.
///
/// This is a simple level-threshold trigger, not true echo cancellation: it
/// uses `.voiceChat` audio session mode (which applies some automatic echo
/// suppression) to reduce false positives from the phone hearing its own
/// speaker output, but loud playback can still trigger it. Good enough as a
/// first version; a dedicated AEC pass can replace the threshold check later
/// without changing how callers use this class.
final class BargeInMonitor {
    var onSpeechDetected: (() -> Void)?

    /// dBFS threshold above which incoming audio is treated as the user talking.
    private let triggerLevelThreshold: Float = -20
    private let meteringInterval: TimeInterval = 0.1

    private let engine = AVAudioEngine()
    private var meteringTimer: Timer?
    private var isTapInstalled = false

    /// Assumes the shared AVAudioSession is already active with a category that
    /// allows recording (AudioPlayerManager sets `.playAndRecord`/`.voiceChat`
    /// before playback begins) — this does not touch session category itself,
    /// to avoid fighting the currently-playing engine over shared session state.
    func start() throws {
        stop()
        print("[BargeIn] start called")

        let inputNode = engine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        print("[BargeIn] input format=\(format)")

        var currentLevel: Float = -160
        var tapCallCount = 0
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            tapCallCount += 1
            currentLevel = Self.averagePower(of: buffer)
            if tapCallCount % 10 == 1 {
                print("[BargeIn] tap #\(tapCallCount) level=\(currentLevel)")
            }
        }
        isTapInstalled = true

        engine.prepare()
        try engine.start()
        print("[BargeIn] engine started, isRunning=\(engine.isRunning)")

        meteringTimer = Timer.scheduledTimer(withTimeInterval: meteringInterval, repeats: true) { [weak self] _ in
            guard let self else { return }
            if currentLevel > self.triggerLevelThreshold {
                print("[BargeIn] threshold crossed, level=\(currentLevel)")
                self.onSpeechDetected?()
            }
        }
    }

    func stop() {
        meteringTimer?.invalidate()
        meteringTimer = nil

        if isTapInstalled {
            engine.inputNode.removeTap(onBus: 0)
            isTapInstalled = false
        }
        if engine.isRunning {
            engine.stop()
        }
    }

    private static func averagePower(of buffer: AVAudioPCMBuffer) -> Float {
        guard let channelData = buffer.floatChannelData?[0] else { return -160 }
        let frameLength = Int(buffer.frameLength)
        guard frameLength > 0 else { return -160 }

        var sum: Float = 0
        for i in 0..<frameLength {
            let sample = channelData[i]
            sum += sample * sample
        }
        let rms = sqrt(sum / Float(frameLength))
        guard rms > 0 else { return -160 }
        return 20 * log10(rms)
    }
}
