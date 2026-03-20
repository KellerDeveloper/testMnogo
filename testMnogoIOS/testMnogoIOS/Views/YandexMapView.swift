//
//  YandexMapView.swift
//  testMnogoIOS
//

import CoreLocation
import SwiftUI
import WebKit

struct YandexMapMarker: Identifiable, Equatable {
    let id: String
    let lat: Double
    let lon: Double
}

struct YandexMapView: UIViewRepresentable {
    let courierCoordinate: CLLocationCoordinate2D?
    let orderMarkers: [YandexMapMarker]
    let zoom: Int

    init(
        courierCoordinate: CLLocationCoordinate2D?,
        orderMarkers: [YandexMapMarker],
        zoom: Int = 14
    ) {
        self.courierCoordinate = courierCoordinate
        self.orderMarkers = orderMarkers
        self.zoom = zoom
    }

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView(frame: .zero, configuration: context.coordinator.webViewConfig)
        webView.scrollView.isScrollEnabled = false
        webView.loadHTMLString(makeHTML(), baseURL: nil)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        let encoder = JSONEncoder()
        encoder.outputFormatting = []

        struct CourierPayload: Codable {
            let lat: Double
            let lon: Double
        }

        struct MarkerPayload: Codable {
            let id: String
            let lat: Double
            let lon: Double
        }

        let courierPayload: CourierPayload? = courierCoordinate.map {
            CourierPayload(lat: $0.latitude, lon: $0.longitude)
        }
        let courierJSON: String = {
            guard let payload = courierPayload else { return "null" }
            let data = try! encoder.encode(payload)
            return String(data: data, encoding: .utf8)!
        }()

        let orderPayloads = orderMarkers.map { MarkerPayload(id: $0.id, lat: $0.lat, lon: $0.lon) }
        let ordersJSONData = try! encoder.encode(orderPayloads)
        let ordersJSON = String(data: ordersJSONData, encoding: .utf8)!

        let js = """
        window.__updateLocations && window.__updateLocations(\(courierJSON), \(ordersJSON));
        """
        webView.evaluateJavaScript(js, completionHandler: nil)
    }

    func makeHTML() -> String {
        let apiKey = Config.yandexMapsApiKey
        // В ymaps API координаты в массивах задаются как [lat, lon].
        let defaultLat = courierCoordinate?.latitude ?? 55.751574
        let defaultLon = courierCoordinate?.longitude ?? 37.573856
        let initialCourierJS: String = {
            guard let courierCoordinate else { return "null" }
            return "{lat: \(courierCoordinate.latitude), lon: \(courierCoordinate.longitude)}"
        }()

        return """
        <!doctype html>
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>
            html, body { width: 100%; height: 100%; margin: 0; padding: 0; background: #f2f2f2; }
            #map { width: 100%; height: 100%; }
          </style>
          <script src="https://api-maps.yandex.ru/2.1/?lang=ru_RU&apikey=\(apiKey)" type="text/javascript"></script>
        </head>
        <body>
          <div id="map"></div>
          <script type="text/javascript">
            var map = null;
            var geoObjects = null;
            var pendingCourier = null;
            var pendingOrders = [];

            function createMap() {
              map = new ymaps.Map('map', {
                center: [\(defaultLat), \(defaultLon)],
                zoom: \(zoom),
                controls: []
              });
              geoObjects = new ymaps.GeoObjectCollection();
              map.geoObjects.add(geoObjects);
            }

            function applyPending() {
              if (!map || !geoObjects) return;
              geoObjects.removeAll();

              if (pendingCourier) {
                geoObjects.add(new ymaps.Placemark([pendingCourier.lat, pendingCourier.lon], {
                  preset: 'islands#blueIcon'
                }));
                map.setCenter([pendingCourier.lat, pendingCourier.lon], \(zoom), {duration: 200});
              }

              if (Array.isArray(pendingOrders)) {
                pendingOrders.forEach(function(o) {
                  if (o && typeof o.lat === 'number' && typeof o.lon === 'number') {
                    geoObjects.add(new ymaps.Placemark([o.lat, o.lon], {
                      preset: 'islands#redIcon'
                    }));
                  }
                });
              }
            }

            // Эта функция может быть вызвана до ymaps.ready(). Поэтому она сначала сохраняет payload,
            // а реально применяет его только после создания карты.
            window.__updateLocations = function(courier, orders) {
              pendingCourier = courier || null;
              pendingOrders = Array.isArray(orders) ? orders : [];
              applyPending();
            };

            ymaps.ready(function() {
              createMap();
              // Стартовая отрисовка (если данные пришли сразу).
              window.__updateLocations(\(initialCourierJS), []);
            });
          </script>
        </body>
        </html>
        """
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject {
        let webViewConfig: WKWebViewConfiguration

        override init() {
            webViewConfig = WKWebViewConfiguration()
            webViewConfig.allowsInlineMediaPlayback = true
            super.init()
        }
    }
}

