import SwiftUI

/// The central visual for the voice conversation — a soft, breathing orb that
/// changes color, glow, and motion based on conversation state. Inspired by
/// Claude/ChatGPT voice mode: one continuous visual metaphor instead of a
/// static button that swaps icons.
struct VoiceOrb: View {
    enum Style {
        case idle
        case listening
        case thinking
        case speaking
    }

    let style: Style
    let action: () -> Void

    @State private var breathe = false
    @State private var rotate = false

    private var baseColor: Color {
        switch style {
        case .idle: return .accentColor
        case .listening: return .pink
        case .thinking: return .purple
        case .speaking: return .orange
        }
    }

    private var coreScale: CGFloat {
        switch style {
        case .idle: return 1.0
        case .listening: return breathe ? 1.08 : 0.96
        case .thinking: return breathe ? 1.04 : 0.98
        case .speaking: return breathe ? 1.1 : 0.94
        }
    }

    var body: some View {
        Button(action: action) {
            ZStack {
                ForEach(0..<3) { index in
                    Circle()
                        .fill(baseColor.opacity(0.12))
                        .frame(width: 220 - CGFloat(index) * 30, height: 220 - CGFloat(index) * 30)
                        .scaleEffect(style == .idle ? 1 : (breathe ? 1.15 : 0.9))
                        .opacity(style == .idle ? 0.3 : 0.7)
                }

                Circle()
                    .fill(
                        RadialGradient(
                            colors: [baseColor.opacity(0.95), baseColor.opacity(0.55)],
                            center: .center,
                            startRadius: 4,
                            endRadius: 90
                        )
                    )
                    .frame(width: 150, height: 150)
                    .scaleEffect(coreScale)
                    .shadow(color: baseColor.opacity(0.6), radius: 24)

                icon
                    .font(.system(size: 44, weight: .medium))
                    .foregroundStyle(.white)
                    .rotationEffect(style == .thinking ? .degrees(rotate ? 360 : 0) : .degrees(0))
            }
        }
        .buttonStyle(.plain)
        .animation(
            .easeInOut(duration: style == .speaking ? 0.5 : 1.1).repeatForever(autoreverses: true),
            value: breathe
        )
        .animation(.linear(duration: 1.6).repeatForever(autoreverses: false), value: rotate)
        .onAppear {
            breathe = true
            rotate = true
        }
    }

    @ViewBuilder
    private var icon: some View {
        switch style {
        case .idle:
            Image(systemName: "mic.fill")
        case .listening:
            Image(systemName: "waveform")
        case .thinking:
            Image(systemName: "sparkle")
        case .speaking:
            Image(systemName: "waveform.and.mic")
        }
    }
}
