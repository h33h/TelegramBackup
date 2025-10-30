import SwiftUI

@main
struct TelegramBackupViewerApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        #if os(macOS)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
        #endif
    }
}



