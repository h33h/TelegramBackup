import SwiftUI

struct MessagesView: View {
    let entity: BackupEntity
    @ObservedObject var backupService: BackupService
    @StateObject private var viewModel: MessagesViewModel
    @Namespace private var messageNamespace
    
    init(entity: BackupEntity, backupService: BackupService) {
        self.entity = entity
        self.backupService = backupService
        _viewModel = StateObject(wrappedValue: MessagesViewModel(entity: entity, backupService: backupService))
    }
    
    var body: some View {
        Group {
            if viewModel.isLoading && viewModel.messages.isEmpty {
                ProgressView("Loading messages...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let error = viewModel.error {
                VStack(spacing: 20) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 50))
                        .foregroundColor(.red)
                    
                    Text(error)
                        .font(.body)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding()
            } else if viewModel.messages.isEmpty {
                VStack(spacing: 20) {
                    Image(systemName: "bubble.left.and.bubble.right")
                        .font(.system(size: 50))
                        .foregroundColor(.gray)
                    
                    Text("No messages found")
                        .font(.body)
                        .foregroundColor(.secondary)
                }
                .padding()
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 0) {
                            // Load more indicator at top (для загрузки старых сообщений)
                            if viewModel.hasMoreMessages && !viewModel.isLoading {
                                Color.clear
                                    .frame(height: 1)
                                    .id("loadMore")
                                    .onAppear {
                                        Task {
                                            await viewModel.loadMoreMessages()
                                        }
                                    }
                            }
                            
                            if viewModel.isLoading && viewModel.messages.isEmpty {
                                ProgressView()
                                    .padding()
                                    .frame(maxWidth: .infinity)
                            }
                            
                            ForEach(Array(viewModel.messages.enumerated()), id: \.element.id) { index, message in
                                // Добавляем разделитель дат
                                if index == 0 || !Calendar.current.isDate(
                                    message.date,
                                    inSameDayAs: viewModel.messages[index - 1].date
                                ) {
                                    DateSeparatorView(date: message.date)
                                        .scaleEffect(y: -1)
                                }
                                
                                // Отображаем сообщение в стиле чата
                                if message.isServiceMessage {
                                    ServiceMessageView(message: message)
                                        .scaleEffect(y: -1)
                                } else {
                                    ChatBubbleView(
                                        message: message,
                                        entity: entity,
                                        viewModel: viewModel,
                                        scrollProxy: proxy
                                    )
                                    .id(message.id)
                                    .scaleEffect(y: -1)
                                }
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.vertical, 8)
                    }
                    .scaleEffect(y: -1)
                    .scrollIndicators(.visible, axes: .vertical)
                    #if os(iOS)
                    .background(Color(uiColor: .systemGroupedBackground))
                    #else
                    .background(Color(nsColor: .controlBackgroundColor))
                    #endif
                    .onChange(of: viewModel.scrollToMessageId) { oldValue, newValue in
                        if let messageId = newValue {
                            withAnimation {
                                proxy.scrollTo(messageId, anchor: .center)
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                                viewModel.scrollToMessageId = nil
                            }
                        }
                    }
                }
                .id(entity.id) // Пересоздаём view при смене чата
            }
        }
        .navigationTitle(entity.displayName)
        .task {
            await viewModel.loadMessages()
        }
        .onChange(of: entity.id) { oldValue, newValue in
            Task {
                await viewModel.updateEntity(entity)
            }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button(action: {
                    Task {
                        await viewModel.refresh()
                    }
                }) {
                    Label("Refresh", systemImage: "arrow.clockwise")
                }
            }
        }
    }
}

@MainActor
class MessagesViewModel: ObservableObject {
    @Published var messages: [Message] = []
    @Published var isLoading = false
    @Published var error: String?
    @Published var hasMoreMessages = true
    @Published var scrollToMessageId: Int?
    
    private var entity: BackupEntity
    private let backupService: BackupService
    private var databaseManager: DatabaseManager?
    private var currentOffset = 0
    private let pageSize = 50
    
    init(entity: BackupEntity, backupService: BackupService) {
        self.entity = entity
        self.backupService = backupService
    }
    
    func loadMessages() async {
        // Всегда сбрасываем при загрузке
        messages = []
        currentOffset = 0
        hasMoreMessages = true
        error = nil
        isLoading = true
        databaseManager = nil
        
        do {
            let manager = try backupService.getDatabaseManager(for: entity)
            self.databaseManager = manager
            
            let fetchedMessages = try manager.fetchMessages(
                entityId: entity.id,
                limit: pageSize,
                offset: 0
            )
            
            // Для инвертированного скролла НЕ реверсируем - база уже возвращает DESC
            self.messages = fetchedMessages
            self.currentOffset = fetchedMessages.count
            self.hasMoreMessages = fetchedMessages.count == pageSize
            self.isLoading = false
        } catch {
            self.error = "Failed to load messages: \(error.localizedDescription)"
            self.isLoading = false
        }
    }
    
    func loadMoreMessages() async {
        guard !isLoading, hasMoreMessages, let manager = databaseManager else {
            return
        }
        
        isLoading = true
        
        do {
            let fetchedMessages = try manager.fetchMessages(
                entityId: entity.id,
                limit: pageSize,
                offset: currentOffset
            )
            
            if !fetchedMessages.isEmpty {
                // Для инвертированного скролла добавляем в конец (старые сообщения)
                self.messages.append(contentsOf: fetchedMessages)
                self.currentOffset += fetchedMessages.count
                self.hasMoreMessages = fetchedMessages.count == pageSize
            } else {
                self.hasMoreMessages = false
            }
            
            self.isLoading = false
        } catch {
            self.error = "Failed to load more messages: \(error.localizedDescription)"
            self.isLoading = false
            self.hasMoreMessages = false
        }
    }
    
    func refresh() async {
        await loadMessages()
    }
    
    func updateEntity(_ newEntity: BackupEntity) async {
        // Обновляем entity и перезагружаем сообщения
        self.entity = newEntity
        await loadMessages()
    }
    
    func getMessage(byId id: Int) -> Message? {
        return messages.first { $0.id == id }
    }
    
    func scrollToMessage(id: Int) {
        scrollToMessageId = id
    }
}

