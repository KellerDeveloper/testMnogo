//
//  Config.swift
//  testMnogoIOS
//

import Foundation

enum Config {
    /// API-ключ Яндекс.Карт (для карты и геокодинга)
    static let yandexMapsApiKey = "9dd9f21c-5de2-417a-ab4a-9c9c20f39080"

    static var courierBaseURL: String {
        let v = UserDefaults.standard.string(forKey: "courierBaseURL")?.trimmingCharacters(in: .whitespaces)
        return (v != nil && !v!.isEmpty) ? v! : "http://localhost:8001"
    }
    static var orderBaseURL: String {
        // Если явно задан URL для order — используем его
        if let raw = UserDefaults.standard.string(forKey: "orderBaseURL")?.trimmingCharacters(in: .whitespaces),
           !raw.isEmpty {
            return raw
        }
        // Иначе стараемся вывести URL order из courierBase:
        // тот же хост, но порт 8000. Это нужно для реального устройства,
        // когда courierBase указывает на IP мака (например, http://192.168.1.84:8001).
        let courier = courierBaseURL
        if var comps = URL(string: courier) {
            var urlComps = URLComponents(url: comps, resolvingAgainstBaseURL: false)
            urlComps?.port = 8000
            if let derived = urlComps?.url?.absoluteString {
                return derived
            }
        }
        // Фоллбек
        return "http://localhost:8000"
    }
    static func setCourierBaseURL(_ url: String) {
        UserDefaults.standard.set(url, forKey: "courierBaseURL")
    }
    static func setOrderBaseURL(_ url: String) {
        UserDefaults.standard.set(url, forKey: "orderBaseURL")
    }
}
