//
//  Courier.swift
//  testMnogoIOS
//

import Foundation

struct CourierLocation: Codable {
    let lat: Double?
    let lon: Double?
}

struct Courier: Codable {
    let courierId: String
    let kitchenId: String
    let name: String
    let status: String
    let currentLocation: CourierLocation?
    let currentOrders: [String]
    let maxBatchSize: Int
    let ordersDeliveredToday: Int
    let totalDeliveryTimeToday: Int
    let geoTrustScore: Double

    enum CodingKeys: String, CodingKey {
        case courierId = "courier_id"
        case kitchenId = "kitchen_id"
        case name
        case status
        case currentLocation = "current_location"
        case currentOrders = "current_orders"
        case maxBatchSize = "max_batch_size"
        case ordersDeliveredToday = "orders_delivered_today"
        case totalDeliveryTimeToday = "total_delivery_time_today"
        case geoTrustScore = "geo_trust_score"
    }
}
