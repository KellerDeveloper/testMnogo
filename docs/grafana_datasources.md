# Дашборды и метрики

## Источники данных

- **Decision Log Service (ClickHouse)** — логи решений, override rate. API: `GET /decisions`, `GET /decisions/analytics/override_rate`.
- **Order Service (PostgreSQL)** — заказы, статусы, SLA. Метрики можно считать по статусам и promised_delivery_time.
- **Courier Service** — утилизация, заказы за смену.

## Ключевые метрики

| Метрика | Описание | Где брать |
|---------|----------|-----------|
| SLA compliance rate | Доля заказов доставленных в срок | Order Service: delivered vs promised_delivery_time |
| Override rate | Доля ручных переопределений | Log Service: /decisions/analytics/override_rate |
| Доля 3PL | % заказов с carrier_type=3pl | Log Service: по decisions |
| Утилизация курьеров | Время в доставке / время смены | Courier Service (расчёт по статусам) |

## Экспорт для Prometheus/Grafana

Скрипт `scripts/metrics_export.py` выводит override_rate и счётчики. Можно обернуть в node_exporter textfile или вызывать из cron и писать в файл для Prometheus.

## Grafana

1. Добавить Data Source: HTTP API или PostgreSQL/ClickHouse по данным из сервисов.
2. Запросы к API Log Service и Order Service через JSON API datasource или скрипт, пишущий в InfluxDB/Prometheus.
