from app.database.connection import SessionLocal

def test_connection():
    db = SessionLocal()
    try:
        print("Database connection successful.")
    finally:
        db.close()

if __name__ == "__main__":
    test_connection()