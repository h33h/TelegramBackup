import SwiftUI

struct SearchView: View {
    let entity: BackupEntity
    @ObservedObject var backupService: BackupService
    @StateObject private var searchService = SearchService()
    @State private var showFilters = false
    
    var body: some View {
        VStack(spacing: 0) {
            // Search bar
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)
                
                TextField("Search messages...", text: $searchService.searchText)
                    .textFieldStyle(.plain)
                    .onSubmit {
                        performSearch()
                    }
                
                if !searchService.searchText.isEmpty {
                    Button(action: {
                        searchService.clearSearch()
                    }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }
                
                Button(action: { showFilters.toggle() }) {
                    Image(systemName: "line.3.horizontal.decrease.circle")
                        .foregroundColor(hasActiveFilters ? .blue : .secondary)
                }
                .buttonStyle(.plain)
            }
            .padding()
            .background(Color.secondary.opacity(0.1))
            
            // Filters panel
            if showFilters {
                FilterPanel(searchService: searchService)
                    .transition(.move(edge: .top))
            }
            
            Divider()
            
            // Results
            if searchService.isSearching {
                ProgressView("Searching...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if searchService.searchText.isEmpty {
                VStack(spacing: 20) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 50))
                        .foregroundColor(.gray)
                    
                    Text("Enter a search term")
                        .font(.body)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if searchService.searchResults.isEmpty {
                VStack(spacing: 20) {
                    Image(systemName: "doc.text.magnifyingglass")
                        .font(.system(size: 50))
                        .foregroundColor(.gray)
                    
                    Text("No results found")
                        .font(.body)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(searchService.searchResults) { message in
                            SearchResultRow(message: message, entity: entity, searchText: searchService.searchText)
                        }
                    }
                }
            }
        }
        .navigationTitle("Search in \(entity.displayName)")
    }
    
    private var hasActiveFilters: Bool {
        searchService.startDate != nil ||
        searchService.endDate != nil ||
        searchService.selectedMediaType != nil ||
        searchService.selectedSender != nil ||
        !searchService.showServiceMessages
    }
    
    private func performSearch() {
        Task {
            do {
                let manager = try backupService.getDatabaseManager(for: entity)
                await searchService.search(in: entity, using: manager)
            } catch {
                // Handle error
            }
        }
    }
}

struct FilterPanel: View {
    @ObservedObject var searchService: SearchService
    
    var body: some View {
        VStack(spacing: 12) {
            // Date filters
            HStack {
                DatePicker("From", selection: Binding(
                    get: { searchService.startDate ?? Date() },
                    set: { searchService.startDate = $0 }
                ), displayedComponents: .date)
                .labelsHidden()
                
                Text("to")
                
                DatePicker("To", selection: Binding(
                    get: { searchService.endDate ?? Date() },
                    set: { searchService.endDate = $0 }
                ), displayedComponents: .date)
                .labelsHidden()
                
                Spacer()
                
                if searchService.startDate != nil || searchService.endDate != nil {
                    Button("Clear dates") {
                        searchService.startDate = nil
                        searchService.endDate = nil
                    }
                    .font(.caption)
                }
            }
            
            // Other filters
            HStack {
                Toggle("Show service messages", isOn: $searchService.showServiceMessages)
                    .font(.caption)
                
                Spacer()
                
                Button("Clear all filters") {
                    searchService.clearFilters()
                }
                .font(.caption)
            }
        }
        .padding()
        .background(Color.secondary.opacity(0.05))
    }
}

struct SearchResultRow: View {
    let message: Message
    let entity: BackupEntity
    let searchText: String
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Circle()
                .fill(Color.blue.opacity(0.2))
                .frame(width: 40, height: 40)
                .overlay(
                    Text(message.senderName?.prefix(1) ?? "?")
                        .font(.subheadline)
                        .foregroundColor(.blue)
                )
            
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(message.senderName ?? "Unknown")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    
                    Spacer()
                    
                    Text(message.formattedDate)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                
                if let text = message.text {
                    Text(highlightedText(text, searchTerm: searchText))
                        .font(.caption)
                        .lineLimit(2)
                        .foregroundColor(.primary)
                }
                
                if message.mediaType != nil {
                    HStack(spacing: 4) {
                        Image(systemName: MediaManager.shared.getMediaIcon(for: message.mediaType))
                        Text(message.mediaType?.replacingOccurrences(of: "MessageMedia", with: "") ?? "Media")
                    }
                    .font(.caption2)
                    .foregroundColor(.secondary)
                }
            }
        }
        .padding()
    }
    
    private func highlightedText(_ text: String, searchTerm: String) -> AttributedString {
        var attributedString = AttributedString(text)
        
        if let range = attributedString.range(of: searchTerm, options: .caseInsensitive) {
            attributedString[range].backgroundColor = .yellow.opacity(0.3)
        }
        
        return attributedString
    }
}

