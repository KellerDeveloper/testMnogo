import AVFoundation
import SwiftUI

// Минималистичный сканер QR для подтверждения “Я на кухне”.
// На симуляторе iOS камеры нет → превью будет пустым (это ожидаемо).
// На реальном устройстве iOS покажет системный запрос на доступ к камере
// (NSCameraUsageDescription уже добавлен в проект).
struct QRScannerView: UIViewControllerRepresentable {
    let onCodeScanned: (String) -> Void
    let onClose: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onCodeScanned: onCodeScanned, onClose: onClose)
    }

    func makeUIViewController(context: Context) -> UIViewController {
        let controller = ScannerHostViewController()
        controller.onClose = {
            context.coordinator.stopSession()
            onClose()
        }

        let session = AVCaptureSession()
        guard
            let device = AVCaptureDevice.default(for: .video),
            let input = try? AVCaptureDeviceInput(device: device),
            session.canAddInput(input)
        else {
            return controller
        }
        session.addInput(input)
        let output = AVCaptureMetadataOutput()
        guard session.canAddOutput(output) else { return controller }
        session.addOutput(output)
        output.setMetadataObjectsDelegate(context.coordinator, queue: DispatchQueue.main)
        output.metadataObjectTypes = [.qr]

        let preview = AVCaptureVideoPreviewLayer(session: session)
        preview.videoGravity = .resizeAspectFill
        controller.previewLayer = preview
        controller.startPreviewContainerIfNeeded(with: preview)

        session.startRunning()
        context.coordinator.session = session
        return controller
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}

    final class Coordinator: NSObject, AVCaptureMetadataOutputObjectsDelegate {
        let onCodeScanned: (String) -> Void
        let onClose: () -> Void
        var session: AVCaptureSession?

        init(onCodeScanned: @escaping (String) -> Void, onClose: @escaping () -> Void) {
            self.onCodeScanned = onCodeScanned
            self.onClose = onClose
        }

        func stopSession() {
            session?.stopRunning()
        }

        func metadataOutput(
            _ output: AVCaptureMetadataOutput,
            didOutput metadataObjects: [AVMetadataObject],
            from connection: AVCaptureConnection
        ) {
            guard let obj = metadataObjects.first as? AVMetadataMachineReadableCodeObject,
                  obj.type == .qr,
                  let value = obj.stringValue
            else { return }
            // Останавливаем сессию сразу, чтобы не словить “дважды один и тот же код”
            // и не уехать в двойные запросы confirmArrival().
            session?.stopRunning()
            onCodeScanned(value)
        }
    }

    final class ScannerHostViewController: UIViewController {
        var onClose: (() -> Void)?
        var previewLayer: AVCaptureVideoPreviewLayer?
        private let previewContainer = UIView()
        private let closeButton = UIButton(type: .system)

        override func viewDidLoad() {
            super.viewDidLoad()
            view.backgroundColor = .black

            previewContainer.backgroundColor = .black
            previewContainer.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview(previewContainer)

            NSLayoutConstraint.activate([
                previewContainer.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 16),
                previewContainer.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -16),
                previewContainer.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 52),
                previewContainer.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24)
            ])

            closeButton.setTitle("Закрыть", for: .normal)
            closeButton.tintColor = .white
            closeButton.backgroundColor = UIColor.black.withAlphaComponent(0.35)
            closeButton.layer.cornerRadius = 10
            closeButton.translatesAutoresizingMaskIntoConstraints = false
            closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
            view.addSubview(closeButton)

            NSLayoutConstraint.activate([
                closeButton.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 8),
                closeButton.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -12),
                closeButton.widthAnchor.constraint(equalToConstant: 92),
                closeButton.heightAnchor.constraint(equalToConstant: 36)
            ])
        }

        func startPreviewContainerIfNeeded(with preview: AVCaptureVideoPreviewLayer) {
            // Слой preview привязываем к отдельному контейнеру, чтобы он занимал не весь экран.
            previewContainer.layer.masksToBounds = true
            previewContainer.layer.addSublayer(preview)
            preview.frame = previewContainer.bounds
        }

        override func viewDidLayoutSubviews() {
            super.viewDidLayoutSubviews()
            previewLayer?.frame = previewContainer.bounds
        }

        @objc private func closeTapped() {
            // Останавливаем сессию в Coordinator через onClose-вызов в представлении.
            onClose?()
        }
    }
}

