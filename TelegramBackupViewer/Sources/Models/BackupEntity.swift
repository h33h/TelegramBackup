import Foundation

struct BackupEntity: Identifiable, Hashable {
    let id: Int
    let name: String
    let directoryPath: URL
    let databasePath: URL
    let mediaPath: URL
    
    var displayName: String {
        name
    }
    
    var hasDatabase: Bool {
        FileManager.default.fileExists(atPath: databasePath.path)
    }
    
    var messageCount: Int? {
        // This will be populated by BackupService
        nil
    }
    
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
        hasher.combine(name)
    }
    
    static func == (lhs: BackupEntity, rhs: BackupEntity) -> Bool {
        lhs.id == rhs.id && lhs.name == rhs.name
    }
}


