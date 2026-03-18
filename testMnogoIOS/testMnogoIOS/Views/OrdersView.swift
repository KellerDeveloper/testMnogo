//
//  OrdersView.swift
//  testMnogoIOS
//

import CoreLocation
import MapKit
import SwiftUI

struct OrdersView: View {
    let courierId: String

    @State private var courier: Courier?
    @State private var orders: [String: Order] = [:]
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var deliveryMinutesPerOrder: [String: String] = [:]
    @State private var actionLoading: Set<String> = []
    @StateObject private var locationManager = LocationManager()
    @State private var showQRScanner = false

    private let api = APIClient()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if let err = errorMessage {
                    Text(err)
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
                    locationBlock(courierId: courierId)
                    currentOrdersSection(courier: c)
                }
            }
            .padding()
        }
        .navigationTitle("Мои заказы")
        .refreshable { await loadCourier() }
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
            QRScannerView { token in
                Task {
                    do {
                        try await api.confirmArrival(courierId: courierId, token: token)
                        await loadCourier()
                        await MainActor.run { showQRScanner = false }
                    } catch {
                        await MainActor.run { errorMessage = messageFor(error) }
                    }
                }
            }
        }
    }

    private func locationBlock(courierId: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Геолокация").font(.subheadline.weight(.medium))

            if locationManager.authorizationStatus == .denied {
                Text("Доступ к геолокации отключён. Включите в Настройках → Конфиденциальность.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }

            if let region = mapRegion {
                Map(initialPosition: .region(region), interactionModes: [.zoom])
                    .frame(height: 160)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .onAppear {
            locationManager.requestPermissionIfNeeded()
            locationManager.startUpdatingLocation()
        }
        .onDisappear { locationManager.stopUpdatingLocation() }
        .task {
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(10))
                await sendLocationInBackground()
            }
        }
    }

    private var mapRegion: MKCoordinateRegion? {
        guard let loc = locationManager.lastLocation else { return nil }
        return MKCoordinateRegion(
            center: loc.coordinate,
            span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
        )
    }

    private func sendLocationInBackground() async {
        guard locationManager.authorizationStatus == .authorizedWhenInUse || locationManager.authorizationStatus == .authorizedAlways else { return }
        do {
            let loc = try await locationManager.requestCurrentLocation()
            try await api.updateLocation(courierId: courierId, lat: loc.coordinate.latitude, lon: loc.coordinate.longitude)
        } catch {
            // тихо игнорируем в фоне
        }
    }

    private func currentOrdersSection(courier: Courier) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Текущие заказы (\(courier.currentOrders.count))").font(.subheadline.weight(.medium))
            if courier.currentOrders.isEmpty {
                Text("Нет активных заказов. Новые появятся после назначения с кухни или диспетчера.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            } else {
                ForEach(courier.currentOrders, id: \.self) { orderId in
                    orderRow(orderId: orderId, courierId: courierId)
                }
            }
        }
    }

    private func orderRow(orderId: String, courierId: String) -> some View {
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
