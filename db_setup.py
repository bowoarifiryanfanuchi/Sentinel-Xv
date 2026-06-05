import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "sentinel_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS analytics_data (
                    row_id INT PRIMARY KEY,
                    tanggal DATE NOT NULL,
                    akun VARCHAR(255) NOT NULL,
                    konten TEXT NOT NULL,
                    views INT DEFAULT 0,
                    likes INT DEFAULT 0,
                    sentiment VARCHAR(50),
                    polarity INT,
                    angle TEXT,
                    attacked_json JSONB,
                    defended_json JSONB
                );
            """))
        print("Database schema initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_db()
