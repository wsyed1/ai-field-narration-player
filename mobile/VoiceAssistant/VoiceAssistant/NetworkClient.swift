import Foundation

enum NetworkError: Error, LocalizedError {
    case badResponse
    case server(String)

    var errorDescription: String? {
        switch self {
        case .badResponse:
            return "Unexpected response from server."
        case .server(let message):
            return message
        }
    }
}

struct VoiceReplyMetadata {
    let userText: String?
    let responseText: String?
}

final class NetworkClient {
    static let shared = NetworkClient()
    private let session = URLSession.shared

    private init() {}

    /// Streams the assistant's spoken reply to `text` chunk-by-chunk.
    /// `onChunk` is called on a background task for each PCM chunk as it arrives;
    /// returns once the stream ends, with the reply's text metadata.
    func streamText(
        _ text: String,
        sessionId: String,
        onChunk: @escaping (Data) -> Void
    ) async throws -> VoiceReplyMetadata {
        guard let url = URL(string: "\(BackendConfig.baseURL)/voice/chat/text") else {
            throw NetworkError.badResponse
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "text": text,
            "session_id": sessionId
        ])
        return try await performStreamingRequest(request, onChunk: onChunk)
    }

    /// Uploads a recorded audio file for cloud transcription, then streams the reply.
    func streamAudioFile(
        at fileURL: URL,
        sessionId: String,
        onChunk: @escaping (Data) -> Void
    ) async throws -> VoiceReplyMetadata {
        guard let url = URL(string: "\(BackendConfig.baseURL)/voice/chat/whisper") else {
            throw NetworkError.badResponse
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "audio_file_path": fileURL.path,
            "session_id": sessionId
        ])
        return try await performStreamingRequest(request, onChunk: onChunk)
    }

    func interrupt(sessionId: String) async {
        guard let url = URL(string: "\(BackendConfig.baseURL)/voice/interrupt") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["session_id": sessionId])
        _ = try? await session.data(for: request)
    }

    private func performStreamingRequest(
        _ request: URLRequest,
        onChunk: @escaping (Data) -> Void
    ) async throws -> VoiceReplyMetadata {
        let (bytes, response) = try await session.bytes(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.badResponse
        }
        let contentType = httpResponse.value(forHTTPHeaderField: "Content-Type") ?? ""

        if httpResponse.statusCode != 200 || contentType.contains("application/json") {
            var buffer = Data()
            for try await byte in bytes {
                buffer.append(byte)
            }
            if let json = try? JSONSerialization.jsonObject(with: buffer) as? [String: Any] {
                if let errorMessage = json["error"] as? String {
                    throw NetworkError.server(errorMessage)
                }
                if let status = json["status"] as? String {
                    throw NetworkError.server("Response was \(status), not audio.")
                }
            }
            throw NetworkError.badResponse
        }

        let userText = httpResponse.value(forHTTPHeaderField: "X-User-Text")?
            .removingPercentEncoding
        let responseText = httpResponse.value(forHTTPHeaderField: "X-Response-Text")?
            .removingPercentEncoding

        // Group incoming bytes into reasonably sized chunks before handing them
        // to the audio player, rather than scheduling a buffer per single byte.
        var chunkBuffer = Data()
        let chunkSize = 4096
        for try await byte in bytes {
            chunkBuffer.append(byte)
            if chunkBuffer.count >= chunkSize {
                onChunk(chunkBuffer)
                chunkBuffer.removeAll(keepingCapacity: true)
            }
        }
        if !chunkBuffer.isEmpty {
            onChunk(chunkBuffer)
        }

        return VoiceReplyMetadata(userText: userText, responseText: responseText)
    }
}
