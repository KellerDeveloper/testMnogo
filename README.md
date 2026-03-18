# Диспатчер (dispatcher)

Система распределения заказов для dark kitchen. Компоненты синхронизируются по REST и WebSocket, а решения диспатчера сохраняются в Decision Log для последующего просмотра в офисе.

Коротко по потокам:
- **Кухня (web)** создаёт заказы и позволяет вручную назначать курьеров.
- **Диспатчер (worker)** получает событие “заказ готов к отправке”, выбирает исполнителя и пишет решение в лог (и при необходимости назначает).
- **Курьер (iOS)** ведёт смену, получает список текущих заказов и отправляет геолокацию.
- **Офис (web)** показывает таймлайн решений, детали решений и override‑аналитику.

---

## Основные компоненты

- `frontend/` — React (Vite + MUI): страницы “Кухня” и “Офис”.
- `testMnogoIOS/` — iOS‑приложение курьера (SwiftUI).
- `services/` — микросервисы FastAPI:
  - `order/` — заказы, статусы, ручное назначение, WebSocket `/ws` для кухни.
  - `courier/` — курьеры, смены, статусы, гео, WebSocket `/ws`, подтверждение прибытия на кухню через QR.
  - `dispatcher/` — worker, который слушает события и принимает решение.
  - `log/` — Decision Log в ClickHouse (включая override‑аналитику).
  - `geo/`, `config/`, `notification/`, `gateway3pl/` — окружение и внешние интеграции.
- `pkg/` — общие модели/DTO и схемы событий.
- `docker-compose.yml` — окружение для локальной разработки.

---

## Порты (локально)

- Web (frontend / Vite): `http://localhost:3000`
- Order service: `http://localhost:8000`
- Courier service: `http://localhost:8001`
- Geo: `http://localhost:8002`
- Config: `http://localhost:8003`
- Log: `http://localhost:8004`
- Notification: `http://localhost:8005`
- Gateway3PL: `http://localhost:8006`

Инфраструктура:
- Postgres: `5433` (внешний порт контейнера)
- Redis: `6379`
- RabbitMQ: `5672` (+ UI `15672`)
- MongoDB: `27017`
- ClickHouse: `8123` (HTTP), `9000` (native)

---

## Быстрый старт

### 1) Поднять инфраструктуру и сервисы

```bash
cd /Users/dmitrijkeller/Documents/XCodeProj/testMnogo
docker-compose up -d
```

### 2) Запустить фронтенд (dev)

```bash
cd /Users/dmitrijkeller/Documents/XCodeProj/testMnogo/frontend
npm install
npm run dev
```

Открыть `http://localhost:3000`.

Во время dev Vite проксирует запросы:
- `/api/order/*`
- `/api/courier/*`
- `/api/log/*`

### 3) Запустить iOS‑приложение курьера

Открой проект `testMnogoIOS/testMnogoIOS.xcodeproj`.

На реальном устройстве введите:
- **URL Courier API**: `http://<IP_МАШИНЫ>:8001`
- **Логин курьера**: 6‑значный courier_id (например `100000`)

Важно: на реальном устройстве нельзя использовать `localhost`, потому что это адрес самого телефона, а не вашего Mac.

---

## Вход курьера

Логин — это **6‑значный courier_id**.

1. Создай курьера в интерфейсе веба (раздел “Кухня → Курьеры” или “Офис → Курьеры”).
2. Возьми courier_id из сообщения “Курьер создан… Логин для входа”.
3. В iOS приложении введи этот courier_id в экран “Вход курьера”.

---

## Сценарии UI

### Кухня (web)
- **Создать заказ** — добавление заказа с `kitchen_id`.
- **Очередь заказов** — список заказов с ручным назначением.
- **Курьеры** — список курьеров кухни. При возвращении курьера на кухню здесь может появляться QR‑код для подтверждения прибытия.

### Курьер (iOS)
- **Начать смену** → `status = idle`
- При назначении заказа → `status = delivering` и добавление заказа в список.
- После доставки → переход в `delivered`.
- При возвращении → `status = returning`.
- В `returning` показывается кнопка **“Я на кухне”**:
  - генерируется короткоживущий токен прибытия (валиден **15 секунд**),
  - появляется QR на стороне кухни,
  - после сканирования токена статус меняется на `idle`, QR исчезает.

Геолокация отправляется автоматически (фоновой цикл с периодом 10 секунд).

### Офис (web)
- **Решения** — таймлайн решений диспатчера (включая ручные override‑ы).
- **Аналитика** — override‑rate (доля manual_override среди решений).

---

## WebSocket обновления

Поддерживаются для “живых” обновлений в интерфейсах:
- Order service: `GET /ws` (подписка по `kitchen_id`)
- Courier service: `GET /ws` (подписка по `kitchen_id` и/или `courier_id`)

В dev фронте WebSocket проксируется через Vite:
- `ws://localhost:3000/api/order/ws`
- `ws://localhost:3000/api/courier/ws`

---

## QR‑подтверждение “Я на кухне” (как работает)

1. Курьер нажимает **“Я на кухне”** при `status = returning`.
2. Courier service генерирует токен и время истечения:
   - хранится в `couriers.arrival_qr_token`
   - истечение: `couriers.arrival_qr_expires_at` (15 секунд)
3. Courier service публикует событие через WebSocket, кухня получает актуальный `arrival_qr_*` и рисует QR на экране.
4. Курьер сканирует QR, приложение вызывает `arrival_confirm`:
   - токен должен совпасть и быть ещё валидным
   - после подтверждения токен очищается
   - статус курьера переводится в `idle`

---

## OpenAPI

Каждый сервис имеет документацию Swagger:
- Order: `http://localhost:8000/docs`
- Courier: `http://localhost:8001/docs`
- Config: `http://localhost:8003/docs`
- Log: `http://localhost:8004/docs`
- Notification: `http://localhost:8005/docs`
