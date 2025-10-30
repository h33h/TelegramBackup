import Foundation
import SwiftUI

#if os(macOS)
import AppKit
#else
import UIKit
#endif

class MediaManager: ObservableObject {
    static let shared = MediaManager()
    
    // HIGH PRIORITY FIX: Use NSCache instead of unlimited Dictionary for memory safety
    private let imageCache = NSCache<NSString, ImageCacheItem>()
    private let cacheQueue = DispatchQueue(label: "com.telegrambackup.mediacache")
    
    init() {
        // Configure NSCache with reasonable limits
        imageCache.countLimit = 100 // Max 100 images
        imageCache.totalCostLimit = 200 * 1024 * 1024 // Max 200MB
    }
    
    func getMediaURL(for message: Message, in entity: BackupEntity) -> URL? {
        guard let mediaFile = message.mediaFile else {
            print("⚠️ MediaManager: No mediaFile in message \(message.id)")
            return nil
        }
        
        var mediaURL: URL
        
        // CRITICAL FIX: Improved path detection for absolute vs relative paths
        // Handle various path formats:
        // - /absolute/path/file.mp4
        // - file:///absolute/path/file.mp4
        // - C:\Windows\path\file.mp4 (Windows)
        // - ./relative/path/file.mp4
        // - relative/path/file.mp4
        
        let trimmedPath = mediaFile.trimmingCharacters(in: .whitespaces)
        
        // Check if it's an absolute path
        let isAbsolute = trimmedPath.hasPrefix("/") || 
                        trimmedPath.hasPrefix("file://") ||
                        (trimmedPath.count > 2 && trimmedPath[trimmedPath.index(trimmedPath.startIndex, offsetBy: 1)] == ":" && trimmedPath[trimmedPath.index(trimmedPath.startIndex, offsetBy: 2)] == "\\") // Windows C:\
        
        if isAbsolute {
            // Это абсолютный путь
            if trimmedPath.hasPrefix("file://") {
                mediaURL = URL(string: trimmedPath) ?? URL(fileURLWithPath: trimmedPath)
            } else {
                mediaURL = URL(fileURLWithPath: trimmedPath)
            }
        } else {
            // Это относительный путь от директории бэкапа
            // Убираем префикс ./ если он есть
            let cleanPath = trimmedPath.hasPrefix("./") ? String(trimmedPath.dropFirst(2)) : trimmedPath
            mediaURL = entity.directoryPath.appendingPathComponent(cleanPath)
        }
        
        print("📂 MediaManager: Looking for media file:")
        print("   Entity directoryPath: \(entity.directoryPath.path)")
        print("   Media file: \(mediaFile)")
        print("   Full path: \(mediaURL.path)")
        print("   File exists: \(FileManager.default.fileExists(atPath: mediaURL.path))")
        
        guard FileManager.default.fileExists(atPath: mediaURL.path) else {
            print("❌ MediaManager: File not found at path: \(mediaURL.path)")
            return nil
        }
        
        print("✅ MediaManager: File found!")
        return mediaURL
    }
    
    func loadImage(for message: Message, in entity: BackupEntity) async -> Image? {
        guard let mediaURL = getMediaURL(for: message, in: entity) else {
            return nil
        }
        
        let cacheKey = mediaURL.path as NSString
        
        // Check cache first (thread-safe NSCache)
        if let cachedItem = imageCache.object(forKey: cacheKey) {
            return cachedItem.image
        }
        
        // MEDIUM PRIORITY FIX: Load image asynchronously to not block main thread
        let imageData: Data
        do {
            imageData = try await Task {
                try Data(contentsOf: mediaURL)
            }.value
        } catch {
            print("⚠️ Failed to load image data: \(error)")
            return nil
        }
        
        #if os(macOS)
        guard let nsImage = NSImage(data: imageData) else {
            return nil
        }
        let image = Image(nsImage: nsImage)
        #else
        guard let uiImage = UIImage(data: imageData) else {
            return nil
        }
        let image = Image(uiImage: uiImage)
        #endif
        
        // Cache it with cost (approximate size in bytes)
        let cost = imageData.count
        let cacheItem = ImageCacheItem(image: image)
        imageCache.setObject(cacheItem, forKey: cacheKey, cost: cost)
        
        return image
    }
    
    func getThumbnail(for message: Message, in entity: BackupEntity, size: CGSize = CGSize(width: 200, height: 200)) async -> Image? {
        guard let mediaURL = getMediaURL(for: message, in: entity) else {
            return nil
        }
        
        let cacheKey = "\(mediaURL.path)_thumb_\(Int(size.width))x\(Int(size.height))" as NSString
        
        // Check cache first (thread-safe NSCache)
        if let cachedItem = imageCache.object(forKey: cacheKey) {
            return cachedItem.image
        }
        
        // MEDIUM PRIORITY FIX: Load and resize image asynchronously
        let imageData: Data
        do {
            imageData = try await Task {
                try Data(contentsOf: mediaURL)
            }.value
        } catch {
            print("⚠️ Failed to load thumbnail data: \(error)")
            return nil
        }
        
        #if os(macOS)
        guard let nsImage = NSImage(data: imageData) else {
            return nil
        }
        
        // CRITICAL FIX: Use defer to ensure unlockFocus is called (prevents memory leaks)
        let thumbnail = NSImage(size: size)
        thumbnail.lockFocus()
        defer { thumbnail.unlockFocus() }
        nsImage.draw(in: NSRect(origin: .zero, size: size))
        
        let image = Image(nsImage: thumbnail)
        #else
        guard let uiImage = UIImage(data: imageData) else {
            return nil
        }
        
        let renderer = UIGraphicsImageRenderer(size: size)
        let thumbnail = renderer.image { _ in
            uiImage.draw(in: CGRect(origin: .zero, size: size))
        }
        
        let image = Image(uiImage: thumbnail)
        #endif
        
        // Cache it with estimated cost
        let cost = Int(size.width * size.height * 4) // Rough estimate: width * height * 4 bytes per pixel
        let cacheItem = ImageCacheItem(image: image)
        imageCache.setObject(cacheItem, forKey: cacheKey, cost: cost)
        
        return image
    }
    
    func isImageType(_ mediaType: String?) -> Bool {
        guard let mediaType = mediaType else { return false }
        return mediaType == "MessageMediaPhoto" || mediaType.contains("Photo")
    }
    
    func isVideoType(_ mediaType: String?) -> Bool {
        guard let mediaType = mediaType else { return false }
        return mediaType == "MessageMediaDocument" && 
               (mediaType.contains("Video") || mediaType.contains("video"))
    }
    
    func isAudioType(_ mediaType: String?) -> Bool {
        guard let mediaType = mediaType else { return false }
        return mediaType.contains("Audio") || mediaType.contains("audio")
    }
    
    func isImageFile(_ filename: String) -> Bool {
        let imageExtensions = ["jpg", "jpeg", "png", "gif", "webp", "heic", "bmp", "tiff"]
        let ext = (filename as NSString).pathExtension.lowercased()
        return imageExtensions.contains(ext)
    }
    
    func isVideoFile(_ filename: String) -> Bool {
        let videoExtensions = ["mp4", "mov", "avi", "mkv", "m4v", "3gp", "webm"]
        let ext = (filename as NSString).pathExtension.lowercased()
        return videoExtensions.contains(ext)
    }
    
    func shouldShowMediaPreview(for message: Message) -> Bool {
        // Проверяем по типу медиа
        if isImageType(message.mediaType) {
            return true
        }
        
        // Проверяем по расширению файла
        if let filename = message.mediaFile {
            return isImageFile(filename) || isVideoFile(filename)
        }
        
        return false
    }
    
    func getMediaIcon(for mediaType: String?) -> String {
        guard let mediaType = mediaType else { return "doc" }
        
        if isImageType(mediaType) {
            return "photo"
        } else if isVideoType(mediaType) {
            return "video"
        } else if isAudioType(mediaType) {
            return "music.note"
        } else {
            return "doc"
        }
    }
    
    func clearCache() {
        imageCache.removeAllObjects()
    }
}

// HIGH PRIORITY FIX: Wrapper class for Image to store in NSCache
class ImageCacheItem {
    let image: Image
    
    init(image: Image) {
        self.image = image
    }
}

