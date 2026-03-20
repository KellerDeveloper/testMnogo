//
//  Order.swift
//  testMnogoIOS
//

import Foundation

struct Order: Codable {
    let orderId: String
    let kitchenId: String
    let status: String
    let promisedDeliveryTime: String?
    let assignedCourierId: String?
    let customerLocation: CustomerLocation?

    struct CustomerLocation: Codable, Equatable {
        let lat: Double
        let lon: Double
    }

    enum CodingKeys: String, CodingKey {
        case orderId = "order_id"
        case kitchenId = "kitchen_id"
        case status
        case promisedDeliveryTime = "promised_delivery_time"
        case assignedCourierId = "assigned_courier_id"
        case customerLocation = "customer_location"
    }
}
