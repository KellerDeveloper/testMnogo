//
//  LocationQueueStore.swift
//  testMnogoIOS
//
//  Offline-first: журнал трека на диске, синхронизация батчами при появлении сети.
//

import Combine
import CoreLocation
import Foundation

@MainActor
final class LocationQueueStore: ObservableObject {
    static let shared = LocationQueueStore()

    /// Для подписи во View (счётчик «в очереди»).
    @Published private(set) var pendingCount: Int = 0

    struct PendingPoint: Codable, Equatable, Sendable {
        let lat: Double
        let lon: Double
        /// ISO8601 с долями секунды (как ожидает courier-сервис)
        let timestamp: String?
        /// Логический источник: gnss / грубое LBS-Wi-Fi / significant cell и т.д.
        let source: String
        /// Горизонтальная точность iOS (м), если известна
        let accuracyM: Double?

        enum CodingKeys: String, CodingKey {
            case lat, lon, timestamp, source
            case accuracyM = "accuracy_m"
        }
    }

    private var points: [PendingPoint] = []

    private let isoFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private var fileURL: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        let sub = base.appendingPathComponent("testMnogo", isDirectory: true)
        try? FileManager.default.createDirectory(at: sub, withIntermediateDirectories: true)
        return sub.appendingPathComponent("pending_locations.json")
    }

    private init() {
        loadFromDisk()
    }

    /// Эвристика источника: iOS не всегда разделяет LBS/Wi‑Fi, опираемся на точность и режим съёма.
    private static func resolvedSourceTag(modeTag: String, location: CLLocation) -> String {
        if modeTag == "significant" {
            return "significant_cell"
        }
        let acc = location.horizontalAccuracy
        if acc < 0 { return "gps_unknown_accuracy" }
        if acc <= 35 { return "gps_gnss" }
        if acc <= 120 { return "gps_degraded_or_wifi_lbs" }
        return "coarse_lbs_wifi"
    }

    private func loadFromDisk() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            points = []
            pendingCount = 0
            return
        }
        do {
            let data = try Data(contentsOf: fileURL)
            points = try JSONDecoder().decode([PendingPoint].self, from: data)
        } catch {
            points = []
        }
        pendingCount = points.count
    }

    private func saveToDisk() {
        do {
            let data = try JSONEncoder().encode(points)
            try data.write(to: fileURL, options: [.atomic])
        } catch {
            // очередь остаётся в памяти до следующей попытки
        }
    }

    /// Добавить точку в журнал (и на диск). `modeTag`: `"significant"` | `"active"`.
    func append(location: CLLocation, modeTag: String) {
        let ts = isoFormatter.string(from: location.timestamp)
        let src = Self.resolvedSourceTag(modeTag: modeTag, location: location)
        let acc: Double? = location.horizontalAccuracy >= 0 ? location.horizontalAccuracy : nil
        points.append(
            PendingPoint(
                lat: location.coordinate.latitude,
                lon: location.coordinate.longitude,
                timestamp: ts,
                source: src,
                accuracyM: acc
            )
        )
        pendingCount = points.count
        saveToDisk()
    }

    /// Снимок для отправки (FIFO).
    func snapshotForUpload() -> [PendingPoint] {
        points
    }

    /// Удалить первые n успешно отправленных точек.
    func removeFirst(_ count: Int) {
        guard count > 0, !points.isEmpty else { return }
        let n = min(count, points.count)
        points.removeFirst(n)
        pendingCount = points.count
        saveToDisk()
    }
}
