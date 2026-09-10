from app.database.connection import engine, Base
from app.database import models  # noqa: F401

def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

if __name__ == "__main__":
    create_tables()