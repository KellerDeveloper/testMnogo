# Форматы событий (шина RabbitMQ)

Обмен: **order_events**, **courier_events**, **dispatch_events** (topic).

## order_events

| Routing key | Описание | Payload (JSON) |
|-------------|----------|----------------|
| order.ready_for_dispatch | Заказ готов к отправке | order_id, kitchen_id, customer_location: {lat, lon}, promised_delivery_time, preparation_ready_time |
| order.assigned | Заказ назначен | order_id, assigned_courier_id?, assigned_carrier_type?, assignment_source |
| order.picked_up | Курьер забрал заказ | order_id, courier_id |
| order.delivered | Заказ доставлен | order_id, courier_id? |
| order.cancelled | Заказ отменён | order_id, reason? |

## dispatch_events

| Routing key | Описание | Payload (JSON) |
|-------------|----------|----------------|
| dispatch.decision_made | Решение диспатчера записано | decision_id, order_id, timestamp, assigned_to, carrier_type, assignment_source, algorithm_version, scores, winner_score, reason_summary, factors, context_snapshot, override_info? |
| dispatch.manual_override | Ручное переопределение | order_id, operator_id, assigned_courier_id, override_reason?, previous_assignment?, kitchen_context? |

## courier_events

| Routing key | Описание |
|-------------|----------|
| courier.status_changed | courier_id, kitchen_id, status |
| courier.location_updated | courier_id, lat, lon, source, timestamp |

Схемы Pydantic: см. `pkg/events/schemas.py`.
