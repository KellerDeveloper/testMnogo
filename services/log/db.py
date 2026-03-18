from clickhouse_driver import Client

from config import settings


def get_client() -> Client:
    return Client(
        host=settings.clickhouse_host,
        port=9000,
        database=settings.clickhouse_db,
    )


def init_schema(client: Client) -> None:
    client.execute("""
        CREATE TABLE IF NOT EXISTS dispatch_decisions (
            decision_id UUID,
            order_id UUID,
            timestamp DateTime64(3),
            assigned_to String,
            carrier_type String,
            assignment_source String,
            algorithm_version String,
            scores String,
            winner_score Float64,
            reason_summary String,
            factors String,
            context_snapshot String,
            override_info String,
            operator_id String DEFAULT '',
            override_reason String DEFAULT ''
        ) ENGINE = MergeTree()
        ORDER BY (order_id, timestamp)
    """)
