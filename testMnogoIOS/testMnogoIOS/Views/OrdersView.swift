//
//  OrdersView.swift
//  testMnogoIOS
//

import CoreLocation
import SwiftUI

struct OrdersView: View {
    let courierId: String

    @State private var courier: Courier?
    @State private var orders: [String: Order] = [:]
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var locationSyncError: String?
    @State private var deliveryMinutesPerOrder: [String: String] = [:]
    @State private var actionLoading: Set<String> = []
    @StateObject private var locationManager = LocationManager()
    @StateObject private var networkMonitor = NetworkStatusMonitor()
    @ObservedObject private var locationQueueStore = LocationQueueStore.shared
    @State private var showQRScanner = false
    @Environment(\.openURL) private var openURL

    private let api = APIClient()
    /// Размер батча на один запрос (типичный диапазон продуктов 20–50).
    private let locationBatchChunkSize = 40

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let err = errorMessage {
                    Text(err)
                        .foregroundStyle(.red)
                        .font(.caption)
                        .padding(.horizontal)
                }

                if let locErr = locationSyncError {
                    Text(locErr)
                        .foregroundStyle(.red)
                        .font(.caption)
                        .padding(.horizontal)
                }

                if isLoading && courier == nil {
                    ProgressView("Загрузка…")
                        .frame(maxWidth: .infinity)
                        .padding()
                } else if let c = courier {
                    courierCard(c)
                    locationBlock(courierId: courierId, courier: c)
                    currentOrdersSection(courier: c)
                }
            }
            .padding()
        }
        .navigationTitle("Мои заказы")
        .refreshable {
            await loadCourier()
            await flushLocationQueueIfPossible()
        }
        .task {
            await loadCourier()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                await loadCourier()
            }
        }
    }

    private func courierCard(_ c: Courier) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(c.name).font(.headline)
                Text(statusLabel(for: c.status))
                    .font(.caption2.bold())
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(statusColor(for: c.status).opacity(0.15))
                    .foregroundStyle(statusColor(for: c.status))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            Text("Заказов за смену: \(c.ordersDeliveredToday) · Сейчас: \(c.currentOrders.count)/\(c.maxBatchSize)")
                .font(.caption)
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                Label(networkMonitor.status.rawValue, systemImage: networkStatusIcon)
                    .font(.caption2)
                    .foregroundStyle(networkStatusColor)
                Text(gpsQualityShortHint)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 10) {
                Button("Начать смену") {
                    Task { await startShift() }
                }
                .disabled(c.status != "offline" || actionLoading.contains("start"))
                Button("Закончить смену") {
                    Task { await endShift() }
                }
                .disabled(c.currentOrders.count > 0 || actionLoading.contains("end"))
            }
            .buttonStyle(.bordered)

            HStack(spacing: 8) {
                ForEach(
                    [("Свободен", "idle"), ("Везу заказ", "delivering"), ("Возвращаюсь", "returning"), ("Оффлайн", "offline")],
                    id: \.1
                ) { label, value in
                    Button {
                        Task { await updateStatus(value) }
                    } label: {
                        Text(label)
                            .font(.caption2)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 6)
                    }
                    .buttonStyle(.bordered)
                    .tint(value == c.status ? statusColor(for: value) : .secondary)
                    .disabled(actionLoading.contains("status") || value == c.status)
                }
            }

            if c.status == "returning" {
                Button("Я на кухне") {
                    Task {
                        actionLoading.insert("arrival")
                        defer { actionLoading.remove("arrival") }
                        do {
                            try await api.requestArrivalQR(courierId: courierId)
                            await MainActor.run { showQRScanner = true }
                        } catch {
                            await MainActor.run { errorMessage = messageFor(error) }
                        }
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(actionLoading.contains("arrival"))
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .sheet(isPresented: $showQRScanner) {
            QRScannerView(
                onCodeScanned: { token in
                    Task {
                        do {
                            try await api.confirmArrival(courierId: courierId, token: token)
                            await loadCourier()
                            await MainActor.run { showQRScanner = false }
                        } catch {
                            await MainActor.run { errorMessage = messageFor(error) }
                        }
                    }
                },
                onClose: { showQRScanner = false }
            )
            .presentationDetents([.medium])
            .presentationDragIndicator(.visible)
        }
    }

    private func locationBlock(courierId: String, courier: Courier) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Геолокация").font(.subheadline.weight(.medium))

            Text(locationTrackingHint)
                .font(.caption2)
                .foregroundStyle(.secondary)

            Text(gpsQualityDetailHint)
                .font(.caption2)
                .foregroundStyle(.secondary)

            if networkMonitor.status == .offline {
                Text("Сеть недоступна: координаты копятся в локальном журнале и уйдут батчами при появлении связи.")
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }

            if locationQueueStore.pendingCount > 0 {
                Text("В очереди на отправку: \(locationQueueStore.pendingCount) точек (офлайн-first)")
                    .font(.caption2)
                    .foregroundStyle(.orange)
            }

            if locationManager.authorizationStatus == .denied {
                Text("Доступ к геолокации отключён. Включите в Настройках → Конфиденциальность.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            if let courierCoord = locationManager.lastLocation?.coordinate {
                YandexMapView(
                    courierCoordinate: courierCoord,
                    orderMarkers: orderMarkersForMap(courier: courier),
                    zoom: 14
                )
                .frame(height: 160)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .onAppear {
            locationManager.requestPermissionIfNeeded()
            locationManager.onSignificantLocation = { loc in
                Task { await enqueueAndTryFlush(loc: loc, modeTag: "significant") }
            }
            syncCourierTrackingMode(courier: courier)
            Task { await flushLocationQueueIfPossible() }
        }
        .onDisappear {
            locationManager.onSignificantLocation = nil
            locationManager.stopAllTracking()
        }
        .onChange(of: courier.status) { _, _ in
            syncCourierTrackingMode(courier: courier)
        }
        .onChange(of: courier.currentOrders.count) { _, _ in
            syncCourierTrackingMode(courier: courier)
        }
        .onChange(of: networkMonitor.status) { _, newStatus in
            guard newStatus != .offline else { return }
            locationSyncError = nil
            Task { await flushLocationQueueIfPossible() }
        }
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(12))
                guard !Task.isCancelled else { break }
                guard locationManager.courierTrackingMode == .activeDelivery else { continue }
                guard locationManager.authorizationStatus == .authorizedWhenInUse
                    || locationManager.authorizationStatus == .authorizedAlways else { continue }
                do {
                    let loc = try await locationManager.requestCurrentLocation()
                    await enqueueAndTryFlush(loc: loc, modeTag: "active")
                } catch {
                    // тихо — сеть/GPS
                }
            }
        }
    }

    private var locationTrackingHint: String {
        switch locationManager.courierTrackingMode {
        case .off:
            return "Трекинг выключен (смена не начата / офлайн)."
        case .significantOnly:
            return "Экономия батареи: только крупные перемещения (significant location). Точное GPS — при активном заказе."
        case .activeDelivery:
            return "Активный заказ: точная геолокация и отправка каждые ~12 с."
        }
    }

    private var networkStatusIcon: String {
        switch networkMonitor.status {
        case .online: return "wifi"
        case .constrained: return "exclamationmark.triangle.fill"
        case .offline: return "wifi.slash"
        }
    }

    private var networkStatusColor: Color {
        switch networkMonitor.status {
        case .online: return .secondary
        case .constrained: return .orange
        case .offline: return .red
        }
    }

    /// Короткая подсказка по качеству GPS для строки под статусом смены.
    private var gpsQualityShortHint: String {
        guard let loc = locationManager.lastLocation else {
            return "GPS: нет точки"
        }
        let acc = loc.horizontalAccuracy
        if acc < 0 {
            return "GPS: нет точности (помехи?)"
        }
        if acc <= 35 {
            return String(format: "GPS: ок ±%.0f м", acc)
        }
        if acc <= 120 {
            return String(format: "GPS: слабее ±%.0f м", acc)
        }
        return String(format: "GPS: грубо ±%.0f м", acc)
    }

    /// Развёрнуто в блоке геолокации.
    private var gpsQualityDetailHint: String {
        guard let loc = locationManager.lastLocation else {
            return "Нет зафиксированной точки. Разрешите геолокацию и подождите."
        }
        let acc = loc.horizontalAccuracy
        if acc < 0 {
            return "Точность неизвестна — типично при глушении GNSS или внутри здания; координаты могут «прыгать»."
        }
        if acc <= 35 {
            return String(format: "Сигнал хороший: горизонтальная точность ~±%.0f м (GNSS).", acc)
        }
        if acc <= 120 {
            return String(
                format: "Точность снижена (~±%.0f м): возможен Wi‑Fi/LBS или помехи; на карте для клиента это может быть «приблизительно».",
                acc
            )
        }
        return String(
            format: "Грубая точка (~±%.0f м): опирайтесь на здравый смысл и маршрут; трек всё равно сохранится локально.",
            acc
        )
    }

    private func syncCourierTrackingMode(courier: Courier) {
        if courier.status == "offline" {
            locationManager.setCourierTrackingMode(.off)
        } else if !courier.currentOrders.isEmpty {
            locationManager.setCourierTrackingMode(.activeDelivery)
        } else {
            locationManager.setCourierTrackingMode(.significantOnly)
        }
    }

    private func orderMarkersForMap(courier: Courier) -> [YandexMapMarker] {
        courier.currentOrders.compactMap { orderId in
            guard let o = orders[orderId],
                  let loc = o.customerLocation else { return nil }
            return YandexMapMarker(id: orderId, lat: loc.lat, lon: loc.lon)
        }
    }

    private func routeFromCoordinate(for courier: Courier) -> CLLocationCoordinate2D? {
        if let loc = locationManager.lastLocation {
            return loc.coordinate
        }
        if let cl = courier.currentLocation,
           let lat = cl.lat,
           let lon = cl.lon {
            return CLLocationCoordinate2D(latitude: lat, longitude: lon)
        }
        return nil
    }

    private func openYandexRoute(from: CLLocationCoordinate2D, to: CLLocationCoordinate2D) {
        var comps = URLComponents(string: "https://yandex.ru/maps/")!
        comps.queryItems = [
            URLQueryItem(
                name: "rtext",
                value: "\(from.latitude),\(from.longitude)~\(to.latitude),\(to.longitude)"
            ),
            URLQueryItem(name: "rtt", value: "auto")
        ]
        if let url = comps.url {
            openURL(url)
        }
    }

    private func enqueueAndTryFlush(loc: CLLocation, modeTag: String) async {
        LocationQueueStore.shared.append(location: loc, modeTag: modeTag)
        await flushLocationQueueIfPossible()
    }

    private func flushLocationQueueIfPossible() async {
        // Важно: не пытаемся слать, пока не получили courier-карточку
        // (иначе возможен 404 "courier not found", если id/смена еще не синхронизированы).
        guard courier != nil else { return }
        guard networkMonitor.status != .offline else { return }
        let activeCourierId = courier?.courierId ?? courierId
        while true {
            guard networkMonitor.status != .offline else { break }
            let snap = LocationQueueStore.shared.snapshotForUpload()
            guard !snap.isEmpty else { break }
            let chunk = Array(snap.prefix(locationBatchChunkSize))
            do {
                try await api.sendLocationBatch(courierId: activeCourierId, points: chunk)
                LocationQueueStore.shared.removeFirst(chunk.count)
            } catch {
                await MainActor.run {
                    locationSyncError = "Не удалось отправить точки геолокации (courierId=\(activeCourierId)): \(error.localizedDescription)"
                }
                break
            }
        }
    }

    private func currentOrdersSection(courier: Courier) -> some View {
        let fromCoord = routeFromCoordinate(for: courier)
        return VStack(alignment: .leading, spacing: 8) {
            Text("Текущие заказы (\(courier.currentOrders.count))").font(.subheadline.weight(.medium))
            if courier.currentOrders.isEmpty {
                Text("Нет активных заказов. Новые появятся после назначения с кухни или диспетчера.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            } else {
                ForEach(courier.currentOrders, id: \.self) { orderId in
                    orderRow(orderId: orderId, courierId: courierId, fromCoord: fromCoord)
                }
            }
        }
    }

    private func orderRow(orderId: String, courierId: String, fromCoord: CLLocationCoordinate2D?) -> some View {
        let order = orders[orderId]
        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text("Заказ \(String(orderId.prefix(8)))")
                    .font(.subheadline.weight(.medium))
                    .monospaced()
                Spacer()
                if let o = order {
                    Text(statusLabel(for: o.status))
                        .font(.caption2.bold())
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(statusColor(for: o.status).opacity(0.15))
                        .foregroundStyle(statusColor(for: o.status))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                } else {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }
            if let o = order {
                if let deadlineText = formattedPromisedTime(o.promisedDeliveryTime) {
                    Text("Дедлайн: \(deadlineText)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if let fromCoord, let loc = o.customerLocation {
                    Button("Построить маршрут") {
                        let to = CLLocationCoordinate2D(latitude: loc.lat, longitude: loc.lon)
                        openYandexRoute(from: fromCoord, to: to)
                    }
                    .disabled(actionLoading.contains("route_\(orderId)"))
                    .buttonStyle(.bordered)
                }

                if o.status == "assigned" {
                    Button("Забрал") {
                        Task { await pickUp(orderId: orderId) }
                    }
                    .disabled(actionLoading.contains("pick_\(orderId)"))
                    .buttonStyle(.borderedProminent)
                } else if o.status == "picked_up" {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Когда заказ доставлен до клиента — нажмите кнопку ниже.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Button("Доставлен") {
                            Task { await markDelivered(orderId: orderId) }
                        }
                        .disabled(actionLoading.contains("del_\(orderId)"))
                        .buttonStyle(.borderedProminent)
                    }
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.tertiarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .task {
            if orders[orderId] == nil { await fetchOrder(orderId) }
        }
    }

    private func statusLabel(for status: String) -> String {
        switch status {
        case "assigned": return "Назначен"
        case "picked_up": return "В пути"
        case "delivered": return "Доставлен"
        case "cancelled": return "Отменён"
        default: return status
        }
    }

    private func statusColor(for status: String) -> Color {
        switch status {
        case "assigned": return .blue
        case "picked_up": return .orange
        case "delivered": return .green
        case "cancelled": return .red
        default: return .secondary
        }
    }

    private func formattedPromisedTime(_ iso: String?) -> String? {
        guard let iso, !iso.isEmpty else { return nil }
        let isoFormatter = ISO8601DateFormatter()
        guard let date = isoFormatter.date(from: iso) else { return iso }
        let fmt = DateFormatter()
        fmt.dateStyle = .none
        fmt.timeStyle = .short
        return fmt.string(from: date)
    }

    private func loadCourier() async {
        guard !courierId.isEmpty else { return }
        await MainActor.run { isLoading = true; errorMessage = nil }
        do {
            let c = try await api.getCourier(id: courierId)
            await MainActor.run { courier = c; isLoading = false }
            await flushLocationQueueIfPossible()
            for id in c.currentOrders where orders[id] == nil {
                await fetchOrder(id)
            }
        } catch {
            await MainActor.run {
                isLoading = false
                errorMessage = messageFor(error)
            }
        }
    }

    private func fetchOrder(_ orderId: String) async {
        do {
            let o = try await api.getOrder(id: orderId)
            await MainActor.run { orders[orderId] = o }
        } catch {
            await MainActor.run { orders[orderId] = nil }
        }
    }

    private func startShift() async {
        actionLoading.insert("start")
        defer { actionLoading.remove("start") }
        do {
            try await api.startShift(courierId: courierId)
            await loadCourier()
            await MainActor.run {
                locationManager.requestAlwaysIfNeededForBackgroundTracking()
            }
        } catch {
            await MainActor.run { errorMessage = messageFor(error) }
        }
    }

    private func endShift() async {
        actionLoading.insert("end")
        defer { actionLoading.remove("end") }
        do {
            try await api.endShift(courierId: courierId)
            await loadCourier()
        } catch {
            await MainActor.run { errorMessage = messageFor(error) }
        }
    }

    private func updateStatus(_ status: String) async {
        actionLoading.insert("status")
        defer { actionLoading.remove("status") }
        do {
            try await api.updateStatus(courierId: courierId, status: status)
            await loadCourier()
        } catch {
            await MainActor.run { errorMessage = messageFor(error) }
        }
    }

    private func pickUp(orderId: String) async {
        actionLoading.insert("pick_\(orderId)")
        defer { actionLoading.remove("pick_\(orderId)") }
        do {
            try await api.updateOrderStatus(orderId: orderId, status: "picked_up", courierId: courierId)
            await loadCourier()
            if let o = try? await api.getOrder(id: orderId) {
                await MainActor.run { orders[orderId] = o }
            }
        } catch {
            await MainActor.run { errorMessage = messageFor(error) }
        }
    }

    private func markDelivered(orderId: String) async {
        let mins = Int(deliveryMinutesPerOrder[orderId] ?? "0") ?? 0
        actionLoading.insert("del_\(orderId)")
        defer { actionLoading.remove("del_\(orderId)") }
        do {
            try await api.markDelivered(courierId: courierId, orderId: orderId, deliveryTimeMinutes: mins)
            try await api.updateOrderStatus(orderId: orderId, status: "delivered", courierId: courierId)
            await loadCourier()
            await MainActor.run {
                orders.removeValue(forKey: orderId)
                deliveryMinutesPerOrder.removeValue(forKey: orderId)
            }
        } catch {
            await MainActor.run { errorMessage = messageFor(error) }
        }
    }

    private func messageFor(_ error: Error) -> String {
        if case APIError.httpError(let code, _) = error {
            if code == 404 { return "Курьер не найден" }
            return "Ошибка \(code)"
        }
        return error.localizedDescription
    }
}
