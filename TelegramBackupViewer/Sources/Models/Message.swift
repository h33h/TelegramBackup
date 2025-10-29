import Foundation

struct Message: Identifiable, Codable {
    let id: Int
    let entityId: Int
    let date: Date
    let text: String?
    let mediaType: String?
    let mediaFile: String?
    let mediaHash: String?
    let forwarded: String?
    let fromId: String?
    let views: Int?
    let senderName: String?
    let replyToMsgId: Int?
    let reactionsJSON: String?
    let webPreview: String?
    let extractionTime: String?
    let isServiceMessage: Bool
    let isVoiceMessage: Bool
    let isPinned: Bool
    let userId: String?
    let fileId: String?
    let fileUniqueId: String?
    let fileSize: Int?
    let mediaFileId: Int?
    
    var reactions: [Reaction] {
        guard let reactionsJSON = reactionsJSON,
              let data = reactionsJSON.data(using: .utf8),
              let decoded = try? JSONDecoder().decode([Reaction].self, from: data) else {
            return []
        }
        return decoded
    }
    
    var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
    
    var displayText: String {
        if isServiceMessage {
            return text ?? "[Service Message]"
        }
        return text ?? "[No text]"
    }
}

struct Reaction: Codable, Identifiable {
    let emoticon: String
    let count: Int
    
    var id: String { emoticon }
}

struct Reply: Identifiable {
    let messageId: Int
    let entityId: Int
    let replyToMsgId: Int
    let quoteText: String?
    
    var id: String { "\(messageId)-\(entityId)" }
}

struct MessageButton: Identifiable {
    let messageId: Int
    let entityId: Int
    let row: Int
    let column: Int
    let text: String?
    let data: String?
    let url: String?
    
    var id: String { "\(messageId)-\(entityId)-\(row)-\(column)" }
}

struct MediaFile: Identifiable {
    let id: Int
    let filePath: String
    let fileHash: String
    let fileSize: Int?
    let fileId: String?
    let accessHash: String?
    let mediaType: String?
    let mimeType: String?
}

