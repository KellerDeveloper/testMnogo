# Расписание/описание сервисов: как работает и зачем нужен

Ниже — разбор **каждого микросервиса** в системе (`services/*`): как работает, зачем нужен, какие основные REST/WS точки и какие сцепки есть между компонентами.

---

## `order` (Order Service)

### Зачем нужен
Хранит и управляет жизненным циклом заказа в кухне: создание, “готов к отправке”, назначение исполнителя, статусы `picked_up/delivered/cancelled`. Также пушит обновления на кухни/офис через WebSocket.

### Как работает
- Заказы лежат в **PostgreSQL**.
- При изменениях статусов/назначений сервис:
  - рассылает события по **WebSocket** (кухня подписана по `kitchen_id`),
  - и/или публикует события в **RabbitMQ** (чтобы воркер `dispatcher` принял решение).

### Публичные API (основные)
- REST:
  - `POST /orders` — создать заказ
  - `GET /orders/{order_id}` — получить заказ
  - `GET /orders` — список с фильтрами (кухня/статус) и пагинацией
  - `POST /orders/{order_id}/ready_for_dispatch` — перевести в `pending` и опубликовать событие `order.ready_for_dispatch`
  - `POST /orders/{order_id}/manual_assign` — ручное назначение курьера (ставит lock в Redis, чтобы диспатчер 30с не назначал заново) + лог override в `log` + добавление заказа курьеру
  - `POST /orders/{order_id}/assign` — назначение (используется диспатчером)
  - `POST /orders/{order_id}/status` — обновление `picked_up/delivered/cancelled` (и публикация событий в RabbitMQ)
- WebSocket:
  - `@app.websocket("/ws")` — кухня подписывается по `kitchen_id`, сервер шлёт `orders_changed`
- `GET /health`

### Ключевой сценарий
Кухня переводит заказ в `ready_for_dispatch` → воркер `dispatcher` принимает решение → затем `order` фиксирует `assign` → курьер меняет статусы через `order`.

---

## `courier` (Courier Service)

### Зачем нужен
Состояние смены и текущие данные курьера, включая:
- список текущих заказов (`current_orders`),
- смену/статусы,
- геолокацию (в т.ч. offline-first батчи),
- QR-флоу “я на кухне”,
- статистику.

Курьерское приложение (iOS) и кухни/офис используют этот сервис для синхронизации.

### Как работает
- Состояние курьера хранится в **PostgreSQL**.
- Быстрый доступ: список “available couriers” кэшируется в **Redis**.
- Обновления UI рассылаются через WebSocket:
  - `courier_changed` всем, кто подписан на `courier_id` или на `kitchen_id`.

### Гео и offline-first
- iOS может не иметь стабильной сети: координаты копятся локально и отправляются пачками:
  - `POST /couriers/{id}/location/batch`
- Если настроен `GEO_SERVICE_URL`, то `courier` прокидывает точки в `geo` сервис (в текущей реализации — по каждой точке в цикле), после чего обновляет `current_location` по **последней точке** батча.

### Публичные API (основные)
- REST:
  - `POST /couriers` — создать курьера
  - `GET /couriers` — список курьеров (фильтрация по кухне)
  - `GET /couriers/{courier_id}` — получить карточку
  - `GET /couriers/available/{kitchen_id}` — курьеры, доступные для назначения (учёт `max_batch_size`)
  - `POST /couriers/{courier_id}/shift/start` — старт смены
  - `POST /couriers/{courier_id}/shift/end` — конец смены
  - `PATCH /couriers/{courier_id}/status` — смена статуса (`idle/delivering/returning/offline`)
  - `PATCH /couriers/{courier_id}/location` — одиночная точка
  - `POST /couriers/{courier_id}/location/batch` — батч offline-first точек
  - `PATCH /couriers/{courier_id}/geo_trust_score` — изменение trust score (опционально)
  - `POST /couriers/{courier_id}/arrival_qr` — сгенерировать QR-токен на 15 секунд
  - `POST /couriers/{courier_id}/arrival_confirm` — подтвердить QR-токен и вернуть `idle`
  - `POST /couriers/{courier_id}/orders` — добавить заказ в `current_orders` (и переключить в `delivering`)
  - `DELETE /couriers/{courier_id}/orders/{order_id}` — убрать заказ (и при пустом списке вернуть `returning`)
  - `POST /couriers/{courier_id}/delivered` — завершить доставку: инкремент статистики + убрать из `current_orders`
  - `GET /couriers/{courier_id}/stats_summary` — сводка по курьеру
  - `POST /couriers/{courier_id}/feedback` — канал обратной связи (сейчас заглушка)
- WebSocket:
  - `@app.websocket("/ws")` — подписка `subscribe { courier_id }` или `subscribe { kitchen_id }` и рассылка `courier_changed`
- `GET /health`

### Ключевой UX-сценарий
Возврат курьера на кухню:
1) в `returning` iOS вызывает `POST /arrival_qr`,
2) кухня по WS показывает QR,
3) курьер сканирует QR → `POST /arrival_confirm`,
4) сервер переводит курьера в `idle`.

---

## `dispatcher` (Dispatcher Worker)

### Зачем нужен
Принимает решения “кому назначить заказ” (dispatch), опираясь на:
- доступных курьеров,
- гео-данные и trust score,
- конфигурацию скоринга,
- опционально 3PL-фолбэк.

Это отдельная логика из web/API, которая выполняется в воркере.

### Как работает (основной поток)
`services/dispatcher/worker.py` подписан на RabbitMQ:
- exchange: `order_exchange`
- routing_key: `order.ready_for_dispatch`
- очередь: `dispatcher_ready_for_dispatch`

При получении события:
1. Берёт Redis lock `dispatch_lock:{order_id}`, чтобы не пересекаться с manual override.
2. Запрашивает `courier`:
   - `GET /couriers/available/{kitchen_id}`
3. Запрашивает `geo`:
   - `POST /location/batch` для получения доверенных координат и trust score
4. Запрашивает `gateway3pl` (опционально):
   - `POST /eta` чтобы получить варианты 3PL с ETA/cost
5. Запрашивает `config`:
   - `GET /configs/active/{kitchen_id}` (веса, SLA пороги)
6. Строит кандидатов и запускает алгоритм из `pkg/dispatcher_algorithm`.
7. Логирует решение в `log`:
   - `POST /decisions`
8. Если `shadow_mode=false`:
   - назначает в `order` (`POST /orders/{order_id}/assign`),
   - обновляет курьеру список заказов (`POST /couriers/{id}/orders`) или создаёт 3PL-заказ через `gateway3pl`.
9. Публикует event в RabbitMQ: `dispatch.decision_made`.

---

## `geo` (Geo Service)

### Зачем нужен
Гео-данные, доверие к гео (trust score) и верификация “подходящих координат”.
Это нужно, чтобы диспетчер не назначал по “нарисованным” или подозрительным точкам.

### Как работает
- MongoDB:
  - коллекция `locations` — трек точек
  - коллекция `courier_trust` — trust score
- При `POST /location` для точки:
  - рассчитывает правдоподобие движения (`level1_speed_check`)
  - учитывает разрывы по времени (`level3_gap_penalty`)
  - обновляет trust score
  - пишет точку с флагами `accepted`/`verified`.

### Публичные API
- REST:
  - `POST /location` — принять одну точку
  - `GET /location/{courier_id}` — отдать последнюю точку:
    - если есть `accepted=True`, отдаёт её (`verified=true`)
    - иначе отдаёт последнюю известную (`verified=false`)
  - `POST /location/batch` — отдать карту `courier_id -> lat/lon + trust`
  - `GET /health`

---

## `config` (Algorithm Config Service)

### Зачем нужен
Хранит параметры скоринга/алгоритма диспетчеризации:
- веса факторов,
- SLA fallback threshold,
- staff priority bonus,
- привязка config к кухням.

### Как работает
- Postgres: хранение конфигов.
- Redis cache: ускоряет `GET /configs/active/{kitchen_id}`.
- Выдача активного конфига:
  - сначала — явная привязка кухня→config,
  - затем fallback — config, где `kitchen_id` входит в `kitchen_ids` и `is_active=true`.

### Публичные API
- `POST /configs`
- `GET /configs`
- `GET /configs/{config_id}`
- `GET /configs/active/{kitchen_id}`
- `PATCH /configs/{config_id}`
- `POST /configs/assign` (привязать кухню к конфигу)
- `GET /health`

---

## `log` (Decision Log / Analytics)

### Зачем нужен
Хранить “решения диспатчера” для офиса и аналитики:
- кому назначили заказ,
- почему (reason/factors),
- метаданные алгоритма,
- доли override и агрегаты.

### Как работает
- ClickHouse:
  - быстрые запросы по большим логам решений,
  - удобные агрегаты.
- `POST /decisions` принимает `dict`, внутри сервис сериализует поля в ClickHouse.

### Публичные API
- `POST /decisions`
- `GET /decisions`
- `GET /decisions/{decision_id}`
- `GET /decisions/analytics/override_rate`
- `GET /health`

---

## `notification` (Notification Service)

### Зачем нужен
Единая точка уведомлений после назначения.
В проде обычно это push/FCM/APNs и/или интеграция с кухней/офисом.

### Как работает (сейчас)
- Заглушка: если `settings.push_enabled`, в коде подразумевается отправка, но фактически сейчас просто возвращается ответ.

### Публичные API
- `POST /notify/assignment`
- `GET /health`

---

## `gateway3pl` (3PL Gateway)

### Зачем нужен
Fallback на сторонние службы (3PL) и расчёт ETA/cost по провайдерам, когда staff-курьеры не справляются по SLA.

### Как работает
- Хранит провайдеров в **PostgreSQL**.
- `POST /eta` возвращает для доступных provider’ов:
  - `eta_minutes` как сумму `avg_pickup_time_minutes + avg_delivery_time_minutes`,
  - `cost_per_order`,
  - `current_sla_minutes`,
  - `success_rate`.
- `POST /orders` — создание 3PL-заказа (stub внешней интеграции).

### Публичные API
- `POST /providers`
- `GET /providers/available/{kitchen_id}`
- `POST /eta`
- `POST /orders`
- `GET /health`

---

## Клиентские части (что “видит” пользователь)

### Web (frontend)
- Кухня и офис обновляются:
  - реальным временем через WebSocket (`orders_changed`, `courier_changed`),
  - плюс REST для загрузки данных.

### iOS (курьер)
- iOS вызывает endpoints `courier`:
  - `shift/*`, `status`, `orders`, `delivered`, `arrival_qr/*`.
- Гео отправляется offline-first:
  - накопление локальной очереди точек,
  - отправка пачками `POST /couriers/{id}/location/batch`.

