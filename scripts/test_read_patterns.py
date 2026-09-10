from app.database.connection import SessionLocal
from app.database.repository import get_all_patterns

def test_read_patterns():
    db = SessionLocal()
    try:
        patterns = get_all_patterns(db)
        for pattern in patterns:
            print(pattern.pattern_name, "-", pattern.keyword)
    finally:
        db.close()

if __name__ == "__main__":
    test_read_patterns()