import SwiftUI

struct ContentView: View {
    @StateObject private var backupService = BackupService()
    @State private var selectedEntity: BackupEntity?
    @State private var showSearch = false
    
    var body: some View {
        Group {
            if backupService.backupFolderURL == nil {
                FolderSelectionView(backupService: backupService)
            } else {
                #if os(macOS)
                MacOSContentView(
                    backupService: backupService,
                    selectedEntity: $selectedEntity,
                    showSearch: $showSearch
                )
                #else
                IOSContentView(
                    backupService: backupService,
                    selectedEntity: $selectedEntity
                )
                #endif
            }
        }
        .onAppear {
            backupService.loadSavedBackupFolder()
        }
    }
}

#if os(macOS)
struct MacOSContentView: View {
    @ObservedObject var backupService: BackupService
    @Binding var selectedEntity: BackupEntity?
    @Binding var showSearch: Bool
    
    var body: some View {
        NavigationSplitView(
            columnVisibility: .constant(.doubleColumn),
            sidebar: {
                BackupListView(
                    backupService: backupService,
                    selectedEntity: $selectedEntity
                )
            },
            detail: {
                if let entity = selectedEntity {
                    if showSearch {
                        SearchView(entity: entity, backupService: backupService)
                    } else {
                        MessagesView(entity: entity, backupService: backupService)
                    }
                } else {
                    VStack(spacing: 20) {
                        Image(systemName: "sidebar.left")
                            .font(.system(size: 60))
                            .foregroundColor(.gray)
                        
                        Text("Select a backup from the sidebar")
                            .font(.title2)
                            .foregroundColor(.secondary)
                    }
                }
            }
        )
        .toolbar {
            ToolbarItem(placement: .navigation) {
                Button(action: toggleSidebar) {
                    Label("Toggle Sidebar", systemImage: "sidebar.left")
                }
            }
            
            if selectedEntity != nil {
                ToolbarItem(placement: .primaryAction) {
                    Button(action: { showSearch.toggle() }) {
                        Label(showSearch ? "Show Messages" : "Search", 
                              systemImage: showSearch ? "message" : "magnifyingglass")
                    }
                }
                
                ToolbarItem(placement: .automatic) {
                    Button(action: changeFolder) {
                        Label("Change Folder", systemImage: "folder")
                    }
                }
            }
        }
    }
    
    private func toggleSidebar() {
        NSApp.keyWindow?.firstResponder?
            .tryToPerform(#selector(NSSplitViewController.toggleSidebar(_:)), with: nil)
    }
    
    private func changeFolder() {
        backupService.backupFolderURL = nil
        selectedEntity = nil
        UserDefaults.standard.removeObject(forKey: "backupFolderPath")
        UserDefaults.standard.removeObject(forKey: "backupFolderBookmark")
    }
}
#endif

#if os(iOS)
struct IOSContentView: View {
    @ObservedObject var backupService: BackupService
    @Binding var selectedEntity: BackupEntity?
    
    var body: some View {
        NavigationStack {
            BackupListView(
                backupService: backupService,
                selectedEntity: $selectedEntity
            )
            .navigationDestination(item: $selectedEntity) { entity in
                MessagesView(entity: entity, backupService: backupService)
                    .toolbar {
                        ToolbarItem(placement: .primaryAction) {
                            NavigationLink(destination: SearchView(entity: entity, backupService: backupService)) {
                                Label("Search", systemImage: "magnifyingglass")
                            }
                        }
                    }
            }
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button(action: {
                            Task {
                                await backupService.scanBackups()
                            }
                        }) {
                            Label("Refresh", systemImage: "arrow.clockwise")
                        }
                        
                        Button(action: changeFolder) {
                            Label("Change Folder", systemImage: "folder")
                        }
                    } label: {
                        Label("More", systemImage: "ellipsis.circle")
                    }
                }
            }
        }
    }
    
    private func changeFolder() {
        backupService.backupFolderURL = nil
        selectedEntity = nil
        UserDefaults.standard.removeObject(forKey: "backupFolderPath")
        UserDefaults.standard.removeObject(forKey: "backupFolderBookmark")
    }
}
#endif

