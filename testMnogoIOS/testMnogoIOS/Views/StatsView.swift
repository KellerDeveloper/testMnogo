//
//  StatsView.swift
//  testMnogoIOS
//

import SwiftUI

struct StatsView: View {
    let courierId: String

    @State private var stats: CourierStatsSummary?
    @State private var isLoading = false
    @State private var errorMessage: String?

    private let api = APIClient()

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Статистика смены")
                .font(.title2.weight(.semibold))

            if isLoading && stats == nil {
                ProgressView("Загружаем статистику…")
            } else if let err = errorMessage {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Статистика недоступна")
                        .font(.subheadline.weight(.semibold))
                    Text(err)
                        .foregroundStyle(.red)
                        .font(.caption)
                    Button("Повторить") { Task { await load() } }
                        .buttonStyle(.bordered)
                }
            } else if let s = stats {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Заказов за эту смену")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Text("\(s.ordersDeliveredToday)")
                            .font(.largeTitle.weight(.bold))
                    }
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Среднее по кухне")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Text(String(format: "%.1f", s.kitchenAvgOrdersToday))
                            .font(.title2)
                    }
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Твоё место по заказам")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Text("\(s.rankByOrders) из \(s.totalCouriersOnKitchen)")
                            .font(.title2)
                    }
                }
            } else {
                Text("Статистика появится после первой доставленной за сегодня посылки.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .navigationTitle("Статистика")
        .refreshable { await load() }
        .task {
            await load()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                await load()
            }
        }
    }

    private func load() async {
        guard !courierId.isEmpty else { return }
        await MainActor.run {
            if stats == nil { isLoading = true }
            errorMessage = nil
        }
        do {
            let s = try await api.getStatsSummary(courierId: courierId)
            await MainActor.run { stats = s; isLoading = false }
        } catch {
            await MainActor.run {
                isLoading = false
                if case APIError.httpError(let code, _) = error, code == 404 {
                    errorMessage = "Курьер не найден"
                } else {
                    errorMessage = error.localizedDescription
                }
            }
        }
    }
}
