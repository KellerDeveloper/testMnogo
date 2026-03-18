"""
Миграция: courier_id с UUID на 6-значный логин.
Запуск из корня репозитория: python -m services.courier.migrate_uuid_to_login
Требуется: psycopg2 (pip install psycopg2-binary).
Для существующих курьеров назначаются логины 100000, 100001, ...
Создаётся файл courier_uuid_to_login.json для миграции заказов (assigned_courier_id).
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

# Sync URL from env (same as .env for courier/order)
def get_sync_url():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "postgres")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def main():
    # Load .env if present
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    url = get_sync_url()
    # Print DB (without password) for debugging
    db_info = f"{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ.get('POSTGRES_DB', 'postgres')}"
    print(f"Connecting to DB: {db_info}")

    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Check if couriers table exists at all
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'couriers'
            )
        """)
        if not cur.fetchone()["exists"]:
            print("Table 'couriers' not found in the database.")
            print("  — If this is a fresh DB: no migration needed. Start the app and tables will be created with 6-digit login.")
            print("  — If data is in Docker: set in .env and re-run: POSTGRES_HOST=localhost, POSTGRES_PORT=5432 (port from docker), POSTGRES_DB=dispatcher, POSTGRES_USER=dispatcher, POSTGRES_PASSWORD=dispatcher")
            conn.rollback()
            return

        # Check if couriers.courier_id is UUID
        cur.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'couriers' AND column_name = 'courier_id'
        """)
        row = cur.fetchone()
        if not row:
            print("Column courier_id not found in couriers (maybe already migrated or different schema). Nothing to migrate.")
            conn.rollback()
            return
        if row["data_type"] != "uuid":
            print("couriers.courier_id is already not UUID (likely already migrated).")
            conn.rollback()
            return

        # Add new column
        cur.execute("ALTER TABLE couriers ADD COLUMN IF NOT EXISTS login VARCHAR(6) UNIQUE")
        conn.commit()

        # Fetch all courier_id (UUID) and assign 100000, 100001, ...
        cur.execute("SELECT courier_id FROM couriers ORDER BY courier_id")
        rows = cur.fetchall()
        mapping = {}
        for i, r in enumerate(rows):
            uid = str(r["courier_id"])
            login = str(100000 + i)
            mapping[uid] = login
            cur.execute("UPDATE couriers SET login = %s WHERE courier_id = %s", (login, r["courier_id"]))

        conn.commit()

        # Drop PK, drop old column, rename login -> courier_id, add PK
        cur.execute("ALTER TABLE couriers DROP CONSTRAINT IF EXISTS couriers_pkey")
        cur.execute("ALTER TABLE couriers DROP COLUMN courier_id")
        cur.execute("ALTER TABLE couriers RENAME COLUMN login TO courier_id")
        cur.execute("ALTER TABLE couriers ADD PRIMARY KEY (courier_id)")
        conn.commit()

        # Save mapping for order service migration
        out_path = REPO_ROOT / "courier_uuid_to_login.json"
        out_path.write_text(json.dumps(mapping, indent=2))
        print(f"Couriers migrated. Mapping saved to {out_path}")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
