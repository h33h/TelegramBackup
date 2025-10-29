import Foundation
import SQLite

enum DatabaseError: Error {
    case connectionFailed
    case queryFailed
    case invalidData
    case fileNotFound
}

class DatabaseManager {
    private var connection: Connection?
    private let databasePath: String
    
    // Table definitions
    private let messages = Table("messages")
    private let buttons = Table("buttons")
    private let replies = Table("replies")
    private let reactions = Table("reactions")
    private let mediaFiles = Table("media_files")
    
    // Message columns
    private let id = Expression<Int>("id")
    private let entityId = Expression<Int>("entity_id")
    private let date = Expression<String>("date")
    private let text = Expression<String?>("text")
    private let mediaType = Expression<String?>("media_type")
    private let mediaFile = Expression<String?>("media_file")
    private let mediaHash = Expression<String?>("media_hash")
    private let forwarded = Expression<String?>("forwarded")
    private let fromId = Expression<String?>("from_id")
    private let views = Expression<Int?>("views")
    private let senderName = Expression<String?>("sender_name")
    private let replyToMsgId = Expression<Int?>("reply_to_msg_id")
    private let reactionsJSON = Expression<String?>("reactions")
    private let webPreview = Expression<String?>("web_preview")
    private let extractionTime = Expression<String?>("extraction_time")
    private let isServiceMessage = Expression<Bool>("is_service_message")
    private let isVoiceMessage = Expression<Bool>("is_voice_message")
    private let isPinned = Expression<Bool>("is_pinned")
    private let userId = Expression<String?>("user_id")
    private let fileId = Expression<String?>("file_id")
    private let fileUniqueId = Expression<String?>("file_unique_id")
    private let fileSize = Expression<Int?>("file_size")
    private let mediaFileId = Expression<Int?>("media_file_id")
    
    init(databasePath: String) throws {
        self.databasePath = databasePath
        
        guard FileManager.default.fileExists(atPath: databasePath) else {
            throw DatabaseError.fileNotFound
        }
        
        do {
            self.connection = try Connection(databasePath, readonly: true)
        } catch {
            throw DatabaseError.connectionFailed
        }
    }
    
    func fetchMessages(entityId: Int, limit: Int = 100, offset: Int = 0) throws -> [Message] {
        guard let connection = connection else {
            throw DatabaseError.connectionFailed
        }
        
        var messageList: [Message] = []
        
        do {
            let query = messages
                .filter(self.entityId == entityId)
                .order(self.id.desc)
                .limit(limit, offset: offset)
            
            for row in try connection.prepare(query) {
                let message = try parseMessage(from: row)
                messageList.append(message)
            }
        } catch {
            throw DatabaseError.queryFailed
        }
        
        return messageList
    }
    
    func fetchMessageById(messageId: Int, entityId: Int) throws -> Message? {
        guard let connection = connection else {
            throw DatabaseError.connectionFailed
        }
        
        do {
            let query = messages
                .filter(self.id == messageId && self.entityId == entityId)
                .limit(1)
            
            for row in try connection.prepare(query) {
                return try parseMessage(from: row)
            }
        } catch {
            throw DatabaseError.queryFailed
        }
        
        return nil
    }
    
    func searchMessages(entityId: Int, searchText: String, limit: Int = 100) throws -> [Message] {
        guard let connection = connection else {
            throw DatabaseError.connectionFailed
        }
        
        var messageList: [Message] = []
        
        do {
            let query = messages
                .filter(self.entityId == entityId && text.like("%\(searchText)%"))
                .order(self.id.desc)
                .limit(limit)
            
            for row in try connection.prepare(query) {
                let message = try parseMessage(from: row)
                messageList.append(message)
            }
        } catch {
            throw DatabaseError.queryFailed
        }
        
        return messageList
    }
    
    func getTotalMessageCount(entityId: Int) throws -> Int {
        guard let connection = connection else {
            throw DatabaseError.connectionFailed
        }
        
        do {
            let count = try connection.scalar(
                messages.filter(self.entityId == entityId).count
            )
            return count
        } catch {
            throw DatabaseError.queryFailed
        }
    }
    
    private func parseMessage(from row: Row) throws -> Message {
        let dateString = try row.get(date)
        let messageDate = ISO8601DateFormatter().date(from: dateString) ?? Date()
        
        return Message(
            id: try row.get(id),
            entityId: try row.get(entityId),
            date: messageDate,
            text: try row.get(text),
            mediaType: try row.get(mediaType),
            mediaFile: try row.get(mediaFile),
            mediaHash: try row.get(mediaHash),
            forwarded: try row.get(forwarded),
            fromId: try row.get(fromId),
            views: try row.get(views),
            senderName: try row.get(senderName),
            replyToMsgId: try row.get(replyToMsgId),
            reactionsJSON: try row.get(reactionsJSON),
            webPreview: try row.get(webPreview),
            extractionTime: try row.get(extractionTime),
            isServiceMessage: try row.get(isServiceMessage),
            isVoiceMessage: try row.get(isVoiceMessage),
            isPinned: try row.get(isPinned),
            userId: try row.get(userId),
            fileId: try row.get(fileId),
            fileUniqueId: try row.get(fileUniqueId),
            fileSize: try row.get(fileSize),
            mediaFileId: try row.get(mediaFileId)
        )
    }
    
    func fetchReplies(messageId: Int, entityId: Int) throws -> [Reply] {
        guard let connection = connection else {
            throw DatabaseError.connectionFailed
        }
        
        let msgId = Expression<Int>("message_id")
        let entId = Expression<Int>("entity_id")
        let replyId = Expression<Int>("reply_to_msg_id")
        let quote = Expression<String?>("quote_text")
        
        var replyList: [Reply] = []
        
        do {
            let query = replies.filter(msgId == messageId && entId == entityId)
            
            for row in try connection.prepare(query) {
                let reply = Reply(
                    messageId: try row.get(msgId),
                    entityId: try row.get(entId),
                    replyToMsgId: try row.get(replyId),
                    quoteText: try row.get(quote)
                )
                replyList.append(reply)
            }
        } catch {
            throw DatabaseError.queryFailed
        }
        
        return replyList
    }
    
    func close() {
        connection = nil
    }
}


