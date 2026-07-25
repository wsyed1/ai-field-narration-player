import Foundation

enum BackendConfig {
    // Physical device on the same WiFi as the Mac running Flask.
    // If testing on the Simulator instead, switch back to "http://127.0.0.1:5000".
    static let baseURL = "http://10.0.0.63:5000"
}
