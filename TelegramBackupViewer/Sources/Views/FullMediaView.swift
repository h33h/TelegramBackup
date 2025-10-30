import SwiftUI
import AVKit

#if os(macOS)
import AppKit
#endif

struct FullMediaView: View {
    let message: Message
    let entity: BackupEntity
    @Environment(\.dismiss) private var dismiss
    @State private var fullImage: Image?
    @State private var isLoading = true
    
    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            
            if isLoading {
                ProgressView()
                    .scaleEffect(1.5)
                    .tint(.white)
            } else if MediaManager.shared.isVideoFile(message.mediaFile ?? "") {
                // Видео плеер
                if let mediaURL = MediaManager.shared.getMediaURL(for: message, in: entity) {
                    VideoPlayer(player: AVPlayer(url: mediaURL))
                        .ignoresSafeArea()
                }
            } else if let fullImage = fullImage {
                // Изображение с зумом
                ScrollView([.horizontal, .vertical]) {
                    fullImage
                        .resizable()
                        .scaledToFit()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            
            // Close button
            VStack {
                HStack {
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 32))
                            .foregroundColor(.white)
                            .shadow(color: .black.opacity(0.3), radius: 3)
                    }
                    .buttonStyle(.plain)
                    .padding()
                }
                Spacer()
            }
            
            // Info overlay
            VStack {
                Spacer()
                
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        if let sender = message.senderName {
                            Text(sender)
                                .font(.headline)
                                .foregroundColor(.white)
                        }
                        
                        Text(message.formattedDate)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.8))
                        
                        if let fileSize = message.fileSize {
                            Text(formatFileSize(fileSize))
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.8))
                        }
                    }
                    .padding()
                    .background(
                        Color.black.opacity(0.7)
                            .cornerRadius(12)
                    )
                    
                    Spacer()
                }
                .padding()
            }
        }
        .task {
            if !MediaManager.shared.isVideoFile(message.mediaFile ?? "") {
                fullImage = await MediaManager.shared.loadImage(for: message, in: entity)
            }
            isLoading = false
        }
        #if os(iOS)
        .statusBarHidden()
        #endif
    }
    
    private func formatFileSize(_ bytes: Int) -> String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB, .useGB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }
}



