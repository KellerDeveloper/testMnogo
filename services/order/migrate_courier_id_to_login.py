"""
Миграция: orders.assigned_courier_id с UUID на 6-значный логин.
Запуск после migrate_uuid_to_login (courier). Читает courier_uuid_to_login.json.
Запуск из корня репозитория: python -m services.order.migrate_courier_id_to_login
Требуется: psycopg2 (pip install psycopg2-binary).
"""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("Install: pip install psycopg2-binary")
    sys.exit(1)


def get_sync_url():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def main():
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    mapping_path = REPO_ROOT / "courier_uuid_to_login.json"
    if not mapping_path.exists():
        print("Run courier migration first: python -m services.courier.migrate_uuid_to_login")
        sys.exit(1)
    mapping = json.loads(mapping_path.read_text())

    url = get_sync_url()
    db_info = f"{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ.get('POSTGRES_DB', 'postgres')}"
    print(f"Connecting to DB: {db_info}")

    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'orders' AND column_name = 'assigned_courier_id'
        """)
        row = cur.fetchone()
        if not row:
            print("Table 'orders' or column assigned_courier_id not found. Use same DB as courier migration (POSTGRES_* in .env).")
            conn.rollback()
            return
        if row["data_type"] != "uuid":
            print("orders.assigned_courier_id is already not UUID (likely already migrated).")
            conn.rollback()
            return

        cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS assigned_courier_login VARCHAR(6)")
        conn.commit()

        cur.execute("SELECT order_id, assigned_courier_id FROM orders WHERE assigned_courier_id IS NOT NULL")
        for r in cur.fetchall():
            uid = str(r["assigned_courier_id"])
            login = mapping.get(uid)
            if login:
                cur.execute(
                    "UPDATE orders SET assigned_courier_login = %s WHERE order_id = %s",
                    (login, r["order_id"]),
                )

        conn.commit()

        cur.execute("ALTER TABLE orders DROP COLUMN assigned_courier_id")
        cur.execute("ALTER TABLE orders RENAME COLUMN assigned_courier_login TO assigned_courier_id")
        conn.commit()

        print("Orders.assigned_courier_id migrated to 6-digit login.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
