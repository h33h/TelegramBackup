import SwiftUI

struct FolderSelectionView: View {
    @ObservedObject var backupService: BackupService
    @State private var showFilePicker = false
    @State private var validationMessage = ""
    
    var body: some View {
        VStack(spacing: 30) {
            Spacer()
            
            Image(systemName: "folder.badge.questionmark")
                .font(.system(size: 80))
                .foregroundColor(.blue)
            
            VStack(spacing: 10) {
                Text("Welcome to Telegram Backup Viewer")
                    .font(.title)
                    .fontWeight(.bold)
                
                Text("Select a folder containing your Telegram backups")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            
            Button(action: {
                showFilePicker = true
            }) {
                Label("Select Backup Folder", systemImage: "folder")
                    .font(.headline)
                    .padding()
                    .frame(minWidth: 200)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }
            .buttonStyle(.plain)
            
            if !validationMessage.isEmpty {
                Text(validationMessage)
                    .font(.caption)
                    .foregroundColor(validationMessage.contains("successfully") ? .green : .red)
                    .padding()
            }
            
            Spacer()
        }
        .padding()
        .fileImporter(
            isPresented: $showFilePicker,
            allowedContentTypes: [.folder],
            allowsMultipleSelection: false
        ) { result in
            handleFolderSelection(result)
        }
    }
    
    private func handleFolderSelection(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            guard let url = urls.first else { return }
            
            // Start accessing security-scoped resource
            _ = url.startAccessingSecurityScopedResource()
            
            if backupService.validateBackupFolder(url) {
                backupService.setBackupFolder(url)
                validationMessage = "Folder validated successfully!"
            } else {
                validationMessage = "Invalid folder. Please select a folder containing Telegram backups."
                url.stopAccessingSecurityScopedResource()
            }
            
        case .failure(let error):
            validationMessage = "Error: \(error.localizedDescription)"
        }
    }
}



