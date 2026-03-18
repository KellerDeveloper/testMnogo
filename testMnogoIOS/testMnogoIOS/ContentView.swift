//
//  ContentView.swift
//  testMnogoIOS
//
//  Created by Дмитрий Келлер on 14.03.2026.
//

import SwiftUI

struct ContentView: View {
    @AppStorage(CourierIDStorage.key) private var courierId: String = ""

    var body: some View {
        if courierId.isEmpty {
            CourierIDEntryView()
        } else {
            TabView {
                NavigationStack {
                    OrdersView(courierId: courierId)
                }
                .tabItem { Label("Мои заказы", systemImage: "list.bullet") }
                NavigationStack {
                    StatsView(courierId: courierId)
                }
                .tabItem { Label("Статистика", systemImage: "chart.bar") }
                NavigationStack {
                    SettingsView(courierId: courierId) {
                        courierId = ""
                    }
                }
                .tabItem { Label("Настройки", systemImage: "gearshape") }
            }
        }
    }
}

#Preview {
    ContentView()
}
