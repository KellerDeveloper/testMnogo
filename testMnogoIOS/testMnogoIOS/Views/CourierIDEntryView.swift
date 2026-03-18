//
//  CourierIDEntryView.swift
//  testMnogoIOS
//

import SwiftUI

enum CourierIDStorage {
    static let key = "courierId"
    static var courierId: String? {
        get { UserDefaults.standard.string(forKey: key) }
        set {
            if let v = newValue { UserDefaults.standard.set(v, forKey: key) }
            else { UserDefaults.standard.removeObject(forKey: key) }
        }
    }
}

struct CourierIDEntryView: View {
    @State private var inputId = ""
    @State private var serverURL: String = UserDefaults.standard.string(forKey: "courierBaseURL")?.trimmingCharacters(in: .whitespaces) ?? "http://localhost:8001"
    @State private var isLoading = false
    @State private var errorMessage: String?

    private var api: APIClient {
        let url = serverURL.trimmingCharacters(in: .whitespaces)
        let base = url.isEmpty ? "http://localhost:8001" : url
        return APIClient(courierBase: base, orderBase: Config.orderBaseURL)
    }

    var body: some View {
        VStack(spacing: 20) {
            Text("Вход курьера")
                .font(.title)
            TextField("URL сервера (Courier API)", text: $serverURL, prompt: Text("http://localhost:8001"))
                .textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)
                .onChange(of: serverURL) { _, new in
                    let t = new.trimmingCharacters(in: .whitespaces)
                    UserDefaults.standard.set(t.isEmpty ? nil : t, forKey: "courierBaseURL")
                }
                .padding(.horizontal)
            TextField("Логин (6 цифр)", text: $inputId)
                .textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.numberPad)
                .padding(.horizontal)

            if let msg = errorMessage {
                Text(msg)
                    .foregroundStyle(.red)
                    .font(.caption)
                    .multilineTextAlignment(.center)
            }

            Button(action: login) {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .frame(maxWidth: .infinity)
                } else {
                    Text("Войти")
                        .frame(maxWidth: .infinity)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(isLoading || inputId.trimmingCharacters(in: .whitespaces).isEmpty)
            .padding(.horizontal, 40)
        }
        .padding()
    }

    private func login() {
        let id = inputId.trimmingCharacters(in: .whitespaces)
        guard !id.isEmpty else { return }
        errorMessage = nil
        isLoading = true
        Task {
            do {
                _ = try await api.getCourier(id: id)
                await MainActor.run {
                    CourierIDStorage.courierId = id
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    if let apiErr = error as? APIError {
                        errorMessage = apiErr.localizedDescription
                    } else {
                        // Сеть недоступна, таймаут и т.п.
                        errorMessage = "Нет связи с сервером. Проверьте, что Courier API запущен (порт 8001) и URL в настройках правильный."
                    }
                }
            }
        }
    }
}

#Preview {
    CourierIDEntryView()
}
