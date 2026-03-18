//
//  SettingsView.swift
//  testMnogoIOS
//

import SwiftUI

struct SettingsView: View {
    let courierId: String
    var onLogout: () -> Void

    @State private var reason = "unfair"
    @State private var comment = ""
    @State private var isLoading = false
    @State private var sent = false
    @State private var errorMessage: String?

    private let api = APIClient()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Сервер").font(.subheadline.weight(.medium))
                TextField("URL Courier API", text: Binding(
                    get: { UserDefaults.standard.string(forKey: "courierBaseURL") ?? "" },
                    set: { UserDefaults.standard.set($0.trimmingCharacters(in: .whitespaces).isEmpty ? nil : $0.trimmingCharacters(in: .whitespaces), forKey: "courierBaseURL") }
                ), prompt: Text("http://localhost:8001"))
                .textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never)
                .keyboardType(.URL)
                Text("Для симулятора: localhost:8001. Для устройства: IP вашего Mac, например http://192.168.1.5:8001")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Divider().padding(.vertical, 4)

                Text("Вы можете оставить обратную связь по справедливости распределения заказов.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                if sent {
                    Text("Спасибо, обратная связь отправлена.")
                        .foregroundStyle(.green)
                }
                if let err = errorMessage {
                    Text(err).foregroundStyle(.red).font(.caption)
                }

                Text("Причина").font(.subheadline.weight(.medium))
                Picker("Причина", selection: $reason) {
                    Text("unfair").tag("unfair")
                    Text("routes").tag("routes")
                    Text("other").tag("other")
                }
                .pickerStyle(.segmented)

                Text("Комментарий (необязательно)").font(.subheadline.weight(.medium))
                TextEditor(text: $comment)
                    .frame(minHeight: 80)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.secondary.opacity(0.3), lineWidth: 1))

                Button(action: sendFeedback) {
                    if isLoading {
                        ProgressView().progressViewStyle(CircularProgressViewStyle(tint: .white))
                            .frame(maxWidth: .infinity)
                    } else {
                        Text("Отправить feedback").frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(isLoading)

                Divider().padding(.vertical, 8)

                Button("Выйти", role: .destructive) {
                    CourierIDStorage.courierId = nil
                    onLogout()
                }
                .frame(maxWidth: .infinity)
            }
            .padding()
        }
        .navigationTitle("Настройки")
    }

    private func sendFeedback() {
        errorMessage = nil
        sent = false
        isLoading = true
        Task {
            do {
                try await api.sendFeedback(courierId: courierId, reason: reason, comment: comment.isEmpty ? nil : comment)
                await MainActor.run {
                    isLoading = false
                    sent = true
                    comment = ""
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = error.localizedDescription
                }
            }
        }
    }
}
