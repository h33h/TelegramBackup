// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TelegramBackupViewer",
    platforms: [
        .macOS(.v14),
        .iOS(.v17)
    ],
    products: [
        .library(
            name: "TelegramBackupViewerLib",
            targets: ["TelegramBackupViewerLib"]
        )
    ],
    dependencies: [
        .package(url: "https://github.com/stephencelis/SQLite.swift.git", from: "0.15.0")
    ],
    targets: [
        .target(
            name: "TelegramBackupViewerLib",
            dependencies: [
                .product(name: "SQLite", package: "SQLite.swift")
            ],
            path: "Sources"
        )
    ]
)

