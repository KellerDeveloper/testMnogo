//
//  LocationManager.swift
//  testMnogoIOS
//
//  Режимы как в foodtech: significant location без активного заказа,
//  высокая точность только пока есть текущие заказы (экономия батареи).
//

import Combine
import CoreLocation
import Foundation

@MainActor
final class LocationManager: NSObject, ObservableObject {
    enum CourierTrackingMode: Equatable {
        case off
        /// Крупные перемещения (~смена соты), минимальный расход батареи
        case significantOnly
        /// Активная доставка — точное GPS
        case activeDelivery
    }

    @Published var lastLocation: CLLocation?
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined
    @Published private(set) var courierTrackingMode: CourierTrackingMode = .off
    @Published var errorMessage: String?

    /// Вызывается при новой точке в режиме significantOnly (для офлайн-очереди).
    var onSignificantLocation: ((CLLocation) -> Void)?

    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<CLLocation, Error>?

    override init() {
        super.init()
        manager.delegate = self
        manager.pausesLocationUpdatesAutomatically = true
        authorizationStatus = manager.authorizationStatus
    }

    func requestPermissionIfNeeded() {
        guard authorizationStatus == .notDetermined else { return }
        manager.requestWhenInUseAuthorization()
    }

    /// Для фоновых significant updates нужен «Всегда» + UIBackgroundModes location.
    func requestAlwaysIfNeededForBackgroundTracking() {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse:
            manager.requestAlwaysAuthorization()
        default:
            break
        }
    }

    /// Запросить текущую геопозицию (одноразово). Сначала запрашивает разрешение при необходимости.
    func requestCurrentLocation() async throws -> CLLocation {
        requestPermissionIfNeeded()
        if let loc = lastLocation, Date().timeIntervalSince(loc.timestamp) < 30 {
            return loc
        }
        return try await withCheckedThrowingContinuation { cont in
            self.continuation = cont
            manager.requestLocation()
        }
    }

    func setCourierTrackingMode(_ mode: CourierTrackingMode) {
        guard mode != courierTrackingMode else {
            refreshBackgroundUpdatesFlag()
            return
        }
        courierTrackingMode = mode

        switch mode {
        case .off:
            manager.stopUpdatingLocation()
            manager.stopMonitoringSignificantLocationChanges()
            manager.allowsBackgroundLocationUpdates = false
        case .significantOnly:
            manager.stopUpdatingLocation()
            manager.desiredAccuracy = kCLLocationAccuracyKilometer
            manager.distanceFilter = kCLDistanceFilterNone
            manager.activityType = .otherNavigation
            manager.startMonitoringSignificantLocationChanges()
            refreshBackgroundUpdatesFlag()
        case .activeDelivery:
            manager.stopMonitoringSignificantLocationChanges()
            manager.desiredAccuracy = kCLLocationAccuracyBest
            manager.distanceFilter = 35
            manager.activityType = .automotiveNavigation
            manager.startUpdatingLocation()
            refreshBackgroundUpdatesFlag()
        }
    }

    private func refreshBackgroundUpdatesFlag() {
        let always = manager.authorizationStatus == .authorizedAlways
        manager.allowsBackgroundLocationUpdates = always && courierTrackingMode != .off
    }

    func stopAllTracking() {
        setCourierTrackingMode(.off)
    }
}

extension LocationManager: CLLocationManagerDelegate {
    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let loc = locations.last else { return }
        Task { @MainActor in
            lastLocation = loc
            if courierTrackingMode == .significantOnly {
                onSignificantLocation?(loc)
            }
            if let cont = continuation {
                continuation = nil
                cont.resume(returning: loc)
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            errorMessage = error.localizedDescription
            if let cont = continuation {
                continuation = nil
                cont.resume(throwing: error)
            }
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        Task { @MainActor in
            authorizationStatus = manager.authorizationStatus
            refreshBackgroundUpdatesFlag()
        }
    }
}
