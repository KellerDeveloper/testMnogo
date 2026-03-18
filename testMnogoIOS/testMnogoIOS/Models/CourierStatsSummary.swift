//
//  CourierStatsSummary.swift
//  testMnogoIOS
//

import Foundation

struct CourierStatsSummary: Codable {
    let courierId: String
    let ordersDeliveredToday: Int
    let totalDeliveryTimeTodayMinutes: Int
    let kitchenAvgOrdersToday: Double
    let rankByOrders: Int
    let totalCouriersOnKitchen: Int

    enum CodingKeys: String, CodingKey {
        case courierId = "courier_id"
        case ordersDeliveredToday = "orders_delivered_today"
        case totalDeliveryTimeTodayMinutes = "total_delivery_time_today_minutes"
        case kitchenAvgOrdersToday = "kitchen_avg_orders_today"
        case rankByOrders = "rank_by_orders"
        case totalCouriersOnKitchen = "total_couriers_on_kitchen"
    }
}
