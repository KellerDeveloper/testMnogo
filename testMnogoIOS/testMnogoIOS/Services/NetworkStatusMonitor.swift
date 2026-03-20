//
//  NetworkStatusMonitor.swift
//  testMnogoIOS
//
//  Индикатор связи для offline-first UX (Online / ограничено / Offline).
//

import Combine
import Foundation
import Network

/// Мониторит путь до интернета; обновления доставляются на main queue.
final class NetworkStatusMonitor: ObservableObject {
    enum Status: String {
        case online = "Онлайн"
        case constrained = "Сеть ограничена"
        case offline = "Офлайн"
    }

    @Published private(set) var status: Status = .online

    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue(label: "testMnogo.network")

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            let next: Status
            if path.status == .satisfied {
                next = path.isConstrained ? .constrained : .online
            } else {
                next = .offline
            }
            DispatchQueue.main.async {
                self?.status = next
            }
        }
        monitor.start(queue: queue)
    }

    deinit {
        monitor.cancel()
    }
}
