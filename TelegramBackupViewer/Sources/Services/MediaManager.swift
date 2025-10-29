import Foundation
import SwiftUI

#if os(macOS)
import AppKit
#else
import UIKit
#endif

class MediaManager: ObservableObject {
    static let shared = MediaManager()
    
    private var imageCache: [String: Image] = [:]
    private let cacheQueue = DispatchQueue(label: "com.telegrambackup.mediacache")
    
    func getMediaURL(for message: Message, in entity: BackupEntity) -> URL? {
        guard let mediaFile = message.mediaFile else {
            print("⚠️ MediaManager: No mediaFile in message \(message.id)")
            return nil
        }
        
        var mediaURL: URL
        
        // Проверяем, является ли mediaFile абсолютным путем
        if mediaFile.hasPrefix("/") || mediaFile.hasPrefix("file://") {
            // Это абсолютный путь
            mediaURL = URL(fileURLWithPath: mediaFile)
        } else {
            // Это относительный путь от директории бэкапа (entity.directoryPath)
            // Например: "media/file.mp4" или "media/2208833410/file.mp4"
            mediaURL = entity.directoryPath.appendingPathComponent(mediaFile)
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
        
        let cacheKey = mediaURL.path
        
        // Check cache first
        if let cachedImage = cacheQueue.sync(execute: { imageCache[cacheKey] }) {
            return cachedImage
        }
        
        // Load image
        guard let imageData = try? Data(contentsOf: mediaURL) else {
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
        
        // Cache it
        cacheQueue.async { [weak self] in
            self?.imageCache[cacheKey] = image
        }
        
        return image
    }
    
    func getThumbnail(for message: Message, in entity: BackupEntity, size: CGSize = CGSize(width: 200, height: 200)) async -> Image? {
        guard let mediaURL = getMediaURL(for: message, in: entity) else {
            return nil
        }
        
        let cacheKey = "\(mediaURL.path)_thumb_\(Int(size.width))x\(Int(size.height))"
        
        // Check cache first
        if let cachedImage = cacheQueue.sync(execute: { imageCache[cacheKey] }) {
            return cachedImage
        }
        
        // Load and resize image
        guard let imageData = try? Data(contentsOf: mediaURL) else {
            return nil
        }
        
        #if os(macOS)
        guard let nsImage = NSImage(data: imageData) else {
            return nil
        }
        
        let thumbnail = NSImage(size: size)
        thumbnail.lockFocus()
        nsImage.draw(in: NSRect(origin: .zero, size: size))
        thumbnail.unlockFocus()
        
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
        
        // Cache it
        cacheQueue.async { [weak self] in
            self?.imageCache[cacheKey] = image
        }
        
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
        cacheQueue.async { [weak self] in
            self?.imageCache.removeAll()
        }
    }
}

