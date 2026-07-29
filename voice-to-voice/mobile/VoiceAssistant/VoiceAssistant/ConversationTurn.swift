import Foundation

struct ConversationTurn: Identifiable {
    let id = UUID()
    let role: Role
    let text: String

    enum Role {
        case user
        case assistant
    }
}
