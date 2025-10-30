import Foundation

@MainActor
class BackupService: ObservableObject {
    @Published var backupEntities: [BackupEntity] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var backupFolderURL: URL?
    
    private var databaseManagers: [Int: DatabaseManager] = [:]
    
    func setBackupFolder(_ url: URL) {
        self.backupFolderURL = url
        
        // Save to UserDefaults
        if let bookmark = try? url.bookmarkData(options: .minimalBookmark, includingResourceValuesForKeys: nil, relativeTo: nil) {
            UserDefaults.standard.set(bookmark, forKey: "backupFolderBookmark")
        }
        
        UserDefaults.standard.set(url.path, forKey: "backupFolderPath")
        
        Task {
            await scanBackups()
        }
    }
    
    func loadSavedBackupFolder() {
        // Try to load from bookmark first (more secure)
        if let bookmarkData = UserDefaults.standard.data(forKey: "backupFolderBookmark") {
            var isStale = false
            if let url = try? URL(resolvingBookmarkData: bookmarkData, options: .withoutUI, relativeTo: nil, bookmarkDataIsStale: &isStale) {
                self.backupFolderURL = url
                Task {
                    await scanBackups()
                }
                return
            }
        }
        
        // Fallback to path
        if let path = UserDefaults.standard.string(forKey: "backupFolderPath") {
            let url = URL(fileURLWithPath: path)
            if FileManager.default.fileExists(atPath: url.path) {
                self.backupFolderURL = url
                Task {
                    await scanBackups()
                }
            }
        }
    }
    
    func scanBackups() async {
        guard let backupFolderURL = backupFolderURL else {
            await MainActor.run {
                self.error = "No backup folder selected"
            }
            return
        }
        
        await MainActor.run {
            self.isLoading = true
            self.error = nil
        }
        
        do {
            let fileManager = FileManager.default
            let contents = try fileManager.contentsOfDirectory(
                at: backupFolderURL,
                includingPropertiesForKeys: [.isDirectoryKey],
                options: [.skipsHiddenFiles]
            )
            
            var entities: [BackupEntity] = []
            
            for url in contents {
                var isDirectory: ObjCBool = false
                guard fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory),
                      isDirectory.boolValue else {
                    continue
                }
                
                // Parse directory name: {entity_id}_{entity_name}
                let dirName = url.lastPathComponent
                guard let underscoreIndex = dirName.firstIndex(of: "_"),
                      let entityId = Int(dirName[..<underscoreIndex]) else {
                    continue
                }
                
                let entityName = String(dirName[dirName.index(after: underscoreIndex)...])
                let databasePath = url.appendingPathComponent("backup.db")
                let mediaPath = url.appendingPathComponent("media")
                
                // Only add if database exists
                if fileManager.fileExists(atPath: databasePath.path) {
                    let entity = BackupEntity(
                        id: entityId,
                        name: entityName,
                        directoryPath: url,
                        databasePath: databasePath,
                        mediaPath: mediaPath
                    )
                    entities.append(entity)
                }
            }
            
            // Sort by name
            entities.sort { $0.name < $1.name }
            
            await MainActor.run {
                self.backupEntities = entities
                self.isLoading = false
            }
        } catch {
            await MainActor.run {
                self.error = "Failed to scan backups: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
    
    func getDatabaseManager(for entity: BackupEntity) throws -> DatabaseManager {
        if let existing = databaseManagers[entity.id] {
            return existing
        }
        
        let manager = try DatabaseManager(databasePath: entity.databasePath.path)
        databaseManagers[entity.id] = manager
        return manager
    }
    
    func validateBackupFolder(_ url: URL) -> Bool {
        let fileManager = FileManager.default
        var isDirectory: ObjCBool = false
        
        guard fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory),
              isDirectory.boolValue else {
            return false
        }
        
        // Check if it contains at least one valid backup directory
        do {
            let contents = try fileManager.contentsOfDirectory(
                at: url,
                includingPropertiesForKeys: [.isDirectoryKey],
                options: [.skipsHiddenFiles]
            )
            
            for dirURL in contents {
                var isDirCheck: ObjCBool = false
                guard fileManager.fileExists(atPath: dirURL.path, isDirectory: &isDirCheck),
                      isDirCheck.boolValue else {
                    continue
                }
                
                let databasePath = dirURL.appendingPathComponent("backup.db")
                if fileManager.fileExists(atPath: databasePath.path) {
                    return true
                }
            }
        } catch {
            return false
        }
        
        return false
    }
    
    func clearDatabaseConnections() {
        for manager in databaseManagers.values {
            manager.close()
        }
        databaseManagers.removeAll()
    }
}



