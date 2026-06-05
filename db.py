import os
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "sentinel_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_last_processed_id():
    """Queries the database to get the max row_id."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(row_id) FROM analytics_data"))
        max_id = result.scalar()
        return max_id if max_id is not None else -1

def save_batch_to_db(batch_df, llm_results):
    """Saves the merged data to the database."""
    # Convert LLM results to a dictionary for easy mapping by row_id
    llm_dict = {item['row_id']: item for item in llm_results}

    with engine.begin() as conn:
        for _, row in batch_df.iterrows():
            row_id = row['row_id']
            # Default values if LLM failed to process this row
            sentiment = None
            polarity = None
            angle = None
            attacked_json = '[]'
            defended_json = '[]'

            if row_id in llm_dict:
                res = llm_dict[row_id]
                sentiment = res.get('primary_sentiment')
                polarity = res.get('polarity_score')
                angle = res.get('narrative_angle')
                attacked_json = json.dumps(res.get('attacked_entities', []))
                defended_json = json.dumps(res.get('defended_entities', []))

            # Views and Likes might be NaN or missing
            views = int(row['Views']) if 'Views' in row and not pd.isna(row['Views']) else 0
            likes = int(row['Likes']) if 'Likes' in row and not pd.isna(row['Likes']) else 0
            
            # Format date (assuming it's a pandas timestamp)
            tanggal = row['Tanggal'].strftime('%Y-%m-%d') if not pd.isna(row['Tanggal']) else None

            conn.execute(
                text("""
                    INSERT INTO analytics_data (
                        row_id, tanggal, akun, konten, views, likes, 
                        sentiment, polarity, angle, attacked_json, defended_json
                    ) VALUES (
                        :row_id, :tanggal, :akun, :konten, :views, :likes,
                        :sentiment, :polarity, :angle, :attacked_json, :defended_json
                    )
                    ON CONFLICT (row_id) DO NOTHING;
                """),
                {
                    "row_id": row_id,
                    "tanggal": tanggal,
                    "akun": str(row['X akun']),
                    "konten": str(row['Konten']),
                    "views": views,
                    "likes": likes,
                    "sentiment": sentiment,
                    "polarity": polarity,
                    "angle": angle,
                    "attacked_json": attacked_json,
                    "defended_json": defended_json
                }
            )
