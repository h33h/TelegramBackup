import Foundation

@MainActor
class SearchService: ObservableObject {
    @Published var searchResults: [Message] = []
    @Published var isSearching = false
    @Published var searchText = ""
    
    // Filters
    @Published var startDate: Date?
    @Published var endDate: Date?
    @Published var selectedMediaType: String?
    @Published var selectedSender: String?
    @Published var showServiceMessages = true
    
    func search(in entity: BackupEntity, using databaseManager: DatabaseManager) async {
        guard !searchText.isEmpty else {
            await MainActor.run {
                self.searchResults = []
            }
            return
        }
        
        await MainActor.run {
            self.isSearching = true
        }
        
        do {
            let results = try databaseManager.searchMessages(
                entityId: entity.id,
                searchText: searchText,
                limit: 500
            )
            
            // Apply additional filters
            let filtered = results.filter { message in
                if !showServiceMessages && message.isServiceMessage {
                    return false
                }
                
                if let mediaTypeFilter = selectedMediaType,
                   message.mediaType != mediaTypeFilter {
                    return false
                }
                
                if let senderFilter = selectedSender,
                   message.senderName != senderFilter {
                    return false
                }
                
                if let start = startDate, message.date < start {
                    return false
                }
                
                if let end = endDate, message.date > end {
                    return false
                }
                
                return true
            }
            
            await MainActor.run {
                self.searchResults = filtered
                self.isSearching = false
            }
        } catch {
            await MainActor.run {
                self.searchResults = []
                self.isSearching = false
            }
        }
    }
    
    func clearFilters() {
        startDate = nil
        endDate = nil
        selectedMediaType = nil
        selectedSender = nil
        showServiceMessages = true
    }
    
    func clearSearch() {
        searchText = ""
        searchResults = []
        clearFilters()
    }
}


