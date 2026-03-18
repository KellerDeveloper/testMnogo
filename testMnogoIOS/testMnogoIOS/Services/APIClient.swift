//
//  APIClient.swift
//  testMnogoIOS
//

import Foundation

enum APIError: Error, LocalizedError {
    case invalidURL
    case httpError(statusCode: Int, data: Data?)
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Неверный адрес сервера. Проверьте настройки URL (Настройки или localhost:8001)."
        case .httpError(let code, _):
            if code == 404 { return "Курьер не найден" }
            return "Ошибка сервера: \(code)"
        case .decoding:
            return "Ошибка формата ответа сервера"
        }
    }
}

final class APIClient {
    private let courierBase: String
    private let orderBase: String
    private let session: URLSession
    private let decoder: JSONDecoder

    init(courierBase: String = Config.courierBaseURL, orderBase: String = Config.orderBaseURL) {
        self.courierBase = courierBase
        self.orderBase = orderBase
        self.session = URLSession.shared
        self.decoder = JSONDecoder()
    }

    // MARK: - Courier

    func getCourier(id: String) async throws -> Courier {
        guard let url = URL(string: "\(courierBase)/couriers/\(id)") else { throw APIError.invalidURL }
        let (data, response) = try await session.data(from: url)
        try checkResponse(response, data: data)
        return try decoder.decode(Courier.self, from: data)
    }

    func startShift(courierId: String) async throws {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/shift/start") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
    }

    func endShift(courierId: String) async throws {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/shift/end") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
    }

    func updateStatus(courierId: String, status: String) async throws {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/status") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "PATCH"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["status": status])
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
    }

    func updateLocation(courierId: String, lat: Double, lon: Double) async throws {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/location") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "PATCH"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["lat": lat, "lon": lon])
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
    }

    func requestArrivalQR(courierId: String) async throws {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/arrival_qr") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
        _ = data // токен нам на клиенте не нужен, его читает сканер на кухне
    }

    func confirmArrival(courierId: String, token: String) async throws {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/arrival_confirm") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["token": token])
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
        _ = data
    }

    func markDelivered(courierId: String, orderId: String, deliveryTimeMinutes: Int) async throws {
        var components = URLComponents(string: "\(courierBase)/couriers/\(courierId)/delivered")!
        components.queryItems = [
            URLQueryItem(name: "order_id", value: orderId),
            URLQueryItem(name: "delivery_time_minutes", value: String(deliveryTimeMinutes))
        ]
        guard let url = components.url else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
    }

    func getStatsSummary(courierId: String) async throws -> CourierStatsSummary {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/stats_summary") else { throw APIError.invalidURL }
        let (data, response) = try await session.data(from: url)
        try checkResponse(response, data: data)
        return try decoder.decode(CourierStatsSummary.self, from: data)
    }

    func sendFeedback(courierId: String, reason: String, comment: String?) async throws {
        guard let url = URL(string: "\(courierBase)/couriers/\(courierId)/feedback") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: Any] = ["reason": reason]
        if let c = comment, !c.isEmpty { body["comment"] = c }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
    }

    // MARK: - Orders

    func getOrder(id: String) async throws -> Order {
        guard let url = URL(string: "\(orderBase)/orders/\(id)") else { throw APIError.invalidURL }
        let (data, response) = try await session.data(from: url)
        try checkResponse(response, data: data)
        return try decoder.decode(Order.self, from: data)
    }

    func updateOrderStatus(orderId: String, status: String, courierId: String) async throws {
        guard let url = URL(string: "\(orderBase)/orders/\(orderId)/status") else { throw APIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["status": status, "courier_id": courierId])
        let (data, response) = try await session.data(for: req)
        try checkResponse(response, data: data)
    }

    // MARK: - Helpers

    private func checkResponse(_ response: URLResponse?, data: Data?) throws {
        guard let http = response as? HTTPURLResponse else { return }
        if http.statusCode >= 400 {
            throw APIError.httpError(statusCode: http.statusCode, data: data)
        }
    }
}
