"""
Data retention cron stub (CLAUDE.md Section 2.8 Data Retention Policy)

Purges:
- Sessions soft-deleted > 30 days (Heuristic Eval H3 fix)
- Masked check_requests > 90 days
- Audit log > 1 year

วิธีใช้:
    # Manual run:
    python -m app.services.retention_cron --dry-run
    python -m app.services.retention_cron --apply

    # Schedule via cron (Linux) or Task Scheduler (Windows):
    # 0 3 * * *  python -m app.services.retention_cron --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database.connection import SessionLocal


PURGE_RULES = {
    "soft_deleted_chat_sessions": {
        "table": "chat_sessions",
        "column": "deleted_at",
        "days": 30,
        "description": "Sessions soft-deleted > 30 days ago",
    },
    "old_check_requests": {
        "table": "check_requests",
        "column": "created_at",
        "days": 90,
        "description": "Masked check_requests > 90 days (CLAUDE.md 2.8)",
    },
    "old_audit_log": {
        "table": "pii_access_log",
        "column": "timestamp",
        "days": 365,
        "description": "Audit log > 1 year (PDPA มาตรา 39)",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                       help="Actually delete (default = dry-run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        print(f"=== Retention cron — {'APPLY' if args.apply else 'DRY-RUN'} | now={now.isoformat()} ===\n")

        for rule_name, rule in PURGE_RULES.items():
            cutoff = now - timedelta(days=rule["days"])
            table = rule["table"]
            col = rule["column"]

            # count first
            count_q = text(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NOT NULL AND {col} < :cutoff")
            n = db.execute(count_q, {"cutoff": cutoff}).scalar() or 0

            print(f"[{rule_name}]")
            print(f"  {rule['description']}")
            print(f"  Cutoff: {cutoff.isoformat()} ({rule['days']}d ago)")
            print(f"  Eligible for purge: {n} rows")

            if args.apply and n > 0:
                delete_q = text(f"DELETE FROM {table} WHERE {col} IS NOT NULL AND {col} < :cutoff")
                db.execute(delete_q, {"cutoff": cutoff})
                db.commit()
                print(f"  ✅ DELETED {n} rows")
            elif n > 0:
                print(f"  (dry-run — re-run with --apply to delete)")
            print()

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
