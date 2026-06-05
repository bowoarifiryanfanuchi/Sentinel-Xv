import os
import time
import pandas as pd
from db import get_last_processed_id, save_batch_to_db
from db_setup import init_db
from llm import process_batch_with_llm

def ingest_and_process(file_path, batch_size=15):
    """Reads the input file, chunks it, and processes it through the pipeline."""
    
    print(f"Loading data from {file_path}...")
    try:
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        elif file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            raise ValueError("Unsupported file format. Must be .xlsx or .csv")
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    # Validate required columns
    required_cols = ['Tanggal', 'Waktu', 'X akun', 'Konten', 'Komentar', 'Repost', 'Likes', 'Views', 'Link']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"Error: Missing required columns: {missing_cols}")
        return

    # Add row_id if not present
    if 'row_id' not in df.columns:
        df['row_id'] = range(1, len(df) + 1)
        
    # Convert 'Tanggal' to datetime objects safely
    df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')

    # Get checkpoint
    last_id = get_last_processed_id()
    print(f"Resuming from row_id > {last_id}")

    # Filter dataframe to only include rows we haven't processed
    df_to_process = df[df['row_id'] > last_id]
    
    total_rows = len(df_to_process)
    if total_rows == 0:
        print("No new rows to process.")
        return

    print(f"Found {total_rows} rows to process. Starting batches...")

    start_time = time.time()
    processed_count = 0

    # Batch generator
    for start_idx in range(0, total_rows, batch_size):
        end_idx = min(start_idx + batch_size, total_rows)
        batch_df = df_to_process.iloc[start_idx:end_idx]
        
        print(f"Processing batch: rows {batch_df['row_id'].iloc[0]} to {batch_df['row_id'].iloc[-1]}...")
        
        llm_results = process_batch_with_llm(batch_df)
        
        save_batch_to_db(batch_df, llm_results)
        
        processed_count += len(batch_df)
        elapsed = time.time() - start_time
        print(f"Processed {processed_count}/{total_rows} rows in {elapsed:.2f} seconds.")

    print("Data ingestion and processing completed.")

if __name__ == "__main__":
    init_db()
    
    # Check if a test dataset exists
    dataset_path = "dataset.xlsx"
    if not os.path.exists(dataset_path):
        print(f"Please place your dataset at {dataset_path} to run the pipeline.")
        print("For testing, you can create a dummy CSV file.")
    else:
        ingest_and_process(dataset_path)
