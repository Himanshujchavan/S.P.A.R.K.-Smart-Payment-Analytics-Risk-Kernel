"""Apply later SQL migrations against DATABASE_URL. Safe to re-run."""

from pathlib import Path

from sqlalchemy import create_engine, text

from api.core.config import settings

MIGRATIONS = [
    "db/migrations/005_auth_hardening.sql",
    "db/migrations/006_audit_event_type.sql",
    "db/migrations/007_unique_fraud_label_txn.sql",
    "db/migrations/008_integrity_and_thresholds.sql",
]


def main() -> None:
    engine = create_engine(settings.DATABASE_URL)
    root = Path(__file__).resolve().parent
    with engine.begin() as conn:
        for rel in MIGRATIONS:
            path = root / rel
            print(f"Applying {rel}")
            sql = path.read_text(encoding="utf-8")
            cur = conn.connection.driver_connection.cursor()
            cur.execute(sql)
            cur.close()
        cols = conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'users'
                  AND column_name IN ('failed_login_attempts', 'locked_until')
                ORDER BY column_name
                """
            )
        ).fetchall()
    print("users columns:", [c[0] for c in cols])


if __name__ == "__main__":
    main()
