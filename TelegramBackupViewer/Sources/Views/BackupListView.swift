import SwiftUI

struct BackupListView: View {
    @ObservedObject var backupService: BackupService
    @Binding var selectedEntity: BackupEntity?
    
    var body: some View {
        Group {
            if backupService.isLoading {
                ProgressView("Loading backups...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let error = backupService.error {
                VStack(spacing: 20) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 50))
                        .foregroundColor(.red)
                    
                    Text(error)
                        .font(.body)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    
                    Button("Retry") {
                        Task {
                            await backupService.scanBackups()
                        }
                    }
                }
                .padding()
            } else if backupService.backupEntities.isEmpty {
                VStack(spacing: 20) {
                    Image(systemName: "tray")
                        .font(.system(size: 50))
                        .foregroundColor(.gray)
                    
                    Text("No backups found")
                        .font(.body)
                        .foregroundColor(.secondary)
                    
                    Button("Change Folder") {
                        backupService.backupFolderURL = nil
                        UserDefaults.standard.removeObject(forKey: "backupFolderPath")
                        UserDefaults.standard.removeObject(forKey: "backupFolderBookmark")
                    }
                }
                .padding()
            } else {
                List(backupService.backupEntities, selection: $selectedEntity) { entity in
                    BackupEntityRow(entity: entity)
                        .tag(entity)
                }
                .listStyle(.sidebar)
            }
        }
        .navigationTitle("Backups")
        #if os(macOS)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button(action: {
                    Task {
                        await backupService.scanBackups()
                    }
                }) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
            }
        }
        #endif
    }
}

struct BackupEntityRow: View {
    let entity: BackupEntity
    
    var body: some View {
        HStack {
            Image(systemName: "message.fill")
                .foregroundColor(.blue)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(entity.displayName)
                    .font(.headline)
                
                Text("ID: \(entity.id)")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            if entity.hasDatabase {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                    .font(.caption)
            }
        }
        .padding(.vertical, 4)
    }
}



