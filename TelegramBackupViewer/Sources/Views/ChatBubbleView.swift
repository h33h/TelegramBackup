import SwiftUI

struct ChatBubbleView: View {
    let message: Message
    let entity: BackupEntity
    @ObservedObject var viewModel: MessagesViewModel
    let scrollProxy: ScrollViewProxy
    @State private var thumbnail: Image?
    @State private var replyMessage: Message?
    
    // Определяем, является ли сообщение исходящим (от текущего пользователя)
    private var isOutgoing: Bool {
        // Все сообщения показываем как входящие (слева)
        false
    }
    
    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            VStack(alignment: isOutgoing ? .trailing : .leading, spacing: 4) {
                // Имя отправителя (только для входящих)
                if !isOutgoing && !message.isServiceMessage {
                    Text(message.senderName ?? "Unknown")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.blue)
                        .padding(.leading, 12)
                }
                
                // Bubble с контентом
                VStack(alignment: .leading, spacing: 8) {
                    // Ответ на сообщение - компактный вид
                    if let replyId = message.replyToMsgId {
                        ReplyPreviewView(
                            replyToMsgId: replyId,
                            replyMessage: replyMessage,
                            onTap: {
                                viewModel.scrollToMessage(id: replyId)
                            }
                        )
                        .task {
                            // Загружаем сообщение, на которое ответили
                            replyMessage = viewModel.getMessage(byId: replyId)
                        }
                    }
                    
                    // Пересланное сообщение
                    if message.forwarded != nil {
                        HStack(spacing: 4) {
                            Image(systemName: "arrowshape.turn.up.right.fill")
                                .font(.caption2)
                            Text("Forwarded message")
                                .font(.caption2)
                        }
                        .foregroundColor(.secondary)
                    }
                    
                    // Текст сообщения (перед медиа)
                    if let text = message.text, !text.isEmpty {
                        Text(text)
                            .font(.body)
                            .textSelection(.enabled)
                            .foregroundColor(message.isServiceMessage ? .secondary : .primary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    
                    // Медиа внизу
                    if message.mediaType != nil {
                        MediaContentView(
                            message: message,
                            entity: entity,
                            thumbnail: $thumbnail
                        )
                    }
                    
                    // Реакции
                    if !message.reactions.isEmpty {
                        ReactionsView(reactions: message.reactions)
                    }
                    
                    // Футер: время, статусы
                    HStack(spacing: 4) {
                        if message.isPinned {
                            Image(systemName: "pin.fill")
                                .font(.caption2)
                        }
                        
                        if message.views ?? 0 > 0 {
                            Image(systemName: "eye")
                                .font(.caption2)
                            Text("\(message.views!)")
                                .font(.caption2)
                        }
                        
                        Spacer()
                        
                        Text(formatTime(message.date))
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
                .padding(12)
                .background(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(bubbleColor)
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .strokeBorder(bubbleBorderColor, lineWidth: message.isPinned ? 2 : 0)
                )
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .layoutPriority(1)
            
            Spacer(minLength: 0)
                .frame(minWidth: 0)
                .layoutPriority(0)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .task {
            if MediaManager.shared.shouldShowMediaPreview(for: message) {
                thumbnail = await MediaManager.shared.getThumbnail(
                    for: message,
                    in: entity,
                    size: CGSize(width: 600, height: 800)
                )
            }
        }
    }
    
    private var bubbleColor: Color {
        if message.isServiceMessage {
            return Color.secondary.opacity(0.1)
        }
        return isOutgoing ? Color.blue.opacity(0.2) : Color.secondary.opacity(0.15)
    }
    
    private var bubbleBorderColor: Color {
        message.isPinned ? .blue : .clear
    }
    
    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}

// MARK: - Media Content View
struct MediaContentView: View {
    let message: Message
    let entity: BackupEntity
    @Binding var thumbnail: Image?
    @State private var showFullMedia = false
    
    var body: some View {
        Group {
            if MediaManager.shared.shouldShowMediaPreview(for: message) {
                // Изображения и видео - показываем превью
                Button(action: { showFullMedia = true }) {
                    mediaPreviewContent
                }
                .buttonStyle(.plain)
                .sheet(isPresented: $showFullMedia) {
                    FullMediaView(message: message, entity: entity)
                }
            } else {
                // Документы, аудио - компактный вид без клика
                documentContent
            }
        }
    }
    
    @ViewBuilder
    private var mediaPreviewContent: some View {
        if MediaManager.shared.isImageType(message.mediaType) || 
           MediaManager.shared.isImageFile(message.mediaFile ?? "") {
            // Изображения - большое превью
            if let thumbnail = thumbnail {
                thumbnail
                    .resizable()
                    .scaledToFill()
                    .frame(maxWidth: 300, maxHeight: 400)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.secondary.opacity(0.1))
                    .frame(width: 300, height: 200)
                    .overlay(
                        ProgressView()
                    )
            }
        } else if MediaManager.shared.isVideoFile(message.mediaFile ?? "") {
            // Видео - превью с иконкой play
            ZStack {
                if let thumbnail = thumbnail {
                    thumbnail
                        .resizable()
                        .scaledToFill()
                        .frame(maxWidth: 300, maxHeight: 400)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.secondary.opacity(0.1))
                        .frame(width: 300, height: 200)
                }
                
                // Play icon overlay
                Circle()
                    .fill(Color.black.opacity(0.6))
                    .frame(width: 60, height: 60)
                    .overlay(
                        Image(systemName: "play.fill")
                            .font(.title)
                            .foregroundColor(.white)
                    )
                
                // Duration badge (if available)
                VStack {
                    Spacer()
                    HStack {
                        Spacer()
                        if let size = message.fileSize {
                            Text(formatFileSize(size))
                                .font(.caption2)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.black.opacity(0.7))
                                .foregroundColor(.white)
                                .cornerRadius(6)
                                .padding(8)
                        }
                    }
                }
            }
            .frame(maxWidth: 300)
        }
    }
    
    @ViewBuilder
    private var documentContent: some View {
        HStack(spacing: 12) {
            Image(systemName: MediaManager.shared.getMediaIcon(for: message.mediaType))
                .font(.title2)
                .foregroundColor(.blue)
                .frame(width: 40, height: 40)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
            
            VStack(alignment: .leading, spacing: 2) {
                Text(message.mediaFile ?? "Media file")
                    .font(.subheadline)
                    .lineLimit(1)
                
                if let size = message.fileSize {
                    Text(formatFileSize(size))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
        }
        .padding(8)
        .background(Color.secondary.opacity(0.08))
        .cornerRadius(10)
    }
    
    private func formatFileSize(_ bytes: Int) -> String {
        let formatter = ByteCountFormatter()
        formatter.allowedUnits = [.useKB, .useMB, .useGB]
        formatter.countStyle = .file
        return formatter.string(fromByteCount: Int64(bytes))
    }
}

// MARK: - Reply Preview
struct ReplyPreviewView: View {
    let replyToMsgId: Int
    let replyMessage: Message?
    let onTap: () -> Void
    
    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 6) {
                // Синяя вертикальная полоска
                Rectangle()
                    .fill(Color.blue)
                    .frame(width: 2)
                
                VStack(alignment: .leading, spacing: 2) {
                    // Имя отправителя
                    Text(replyMessage?.senderName ?? "Loading...")
                        .font(.caption)
                        .foregroundColor(.blue)
                        .fontWeight(.semibold)
                        .lineLimit(1)
                    
                    // Текст сообщения или тип медиа
                    if let replyText = replyMessage?.text, !replyText.isEmpty {
                        Text(replyText)
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    } else if replyMessage?.mediaType != nil {
                        HStack(spacing: 3) {
                            Image(systemName: MediaManager.shared.getMediaIcon(for: replyMessage?.mediaType))
                                .font(.caption2)
                            Text(replyMessage?.mediaType?.replacingOccurrences(of: "MessageMedia", with: "") ?? "Media")
                                .font(.caption)
                        }
                        .foregroundColor(.secondary)
                    } else {
                        Text("Message #\(replyToMsgId)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.blue.opacity(0.05))
            .cornerRadius(6)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Reactions View
struct ReactionsView: View {
    let reactions: [Reaction]
    
    var body: some View {
        HStack(spacing: 6) {
            ForEach(reactions) { reaction in
                HStack(spacing: 3) {
                    Text(reaction.emoticon)
                        .font(.caption)
                    Text("\(reaction.count)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    Capsule()
                        .fill(Color.secondary.opacity(0.15))
                )
            }
        }
    }
}

// MARK: - Service Message View
struct ServiceMessageView: View {
    let message: Message
    
    var body: some View {
        HStack {
            Spacer()
            
            Text(message.displayText)
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(
                    Capsule()
                        .fill(Color.secondary.opacity(0.1))
                )
            
            Spacer()
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Date Separator
struct DateSeparatorView: View {
    let date: Date
    
    var body: some View {
        HStack {
            Spacer()
            
            Text(formatDate(date))
                .font(.caption)
                .foregroundColor(.secondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(
                    Capsule()
                        .fill(Color.secondary.opacity(0.1))
                )
            
            Spacer()
        }
        .padding(.vertical, 8)
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: date)
    }
}

