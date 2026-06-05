import os
import json
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from dotenv import load_dotenv

load_dotenv()

# Initialize the GenAI client with stripped API key to prevent UI copy-paste newline issues
raw_api_key = os.getenv("GEMINI_API_KEY", "")
clean_api_key = raw_api_key.replace('\n', '').replace('\r', '').replace('"', '').strip()
client = genai.Client(api_key=clean_api_key)

# Switch to Gemini 2.0 Flash to bypass the 500 requests/day limit on the previous model
model_name = 'gemini-2.0-flash'

SYSTEM_PROMPT = """
You are a data parser specialized in Indonesian sociopolitical nuances.
Analyze the provided batch of social media posts.
Your output MUST be a strict JSON Array of objects. Do not wrap the JSON in markdown blocks (e.g. ```json).
Just return the raw JSON array.

Expected Schema per object:
{
  "row_id": "Integer (Matches the input row_id exactly)",
  "primary_sentiment": "String (Strict Enum: 'Positif', 'Negatif', 'Netral')",
  "emotion": "String (Dominant emotion: 'Marah', 'Takut', 'Antisipasi', 'Sedih', 'Gembira', 'Jijik', 'Terkejut', 'Percaya', or 'Netral')",
  "narrative_category": "String (Short topic label, 1-4 words max, act as a category for grouping. e.g., 'Kritik Kebijakan', 'Dukungan Pejabat')",
  "actor_type": "String (Guess based on text: 'Organik' or 'Buzzer')",
  "attacked_entities": ["String", "String"],
  "defended_entities": ["String", "String"],
  "hashtags": ["String"]
}
"""

@retry(wait=wait_exponential(multiplier=2, min=5, max=65), stop=stop_after_attempt(8))
def call_llm_api(prompt_text):
    """Calls the Gemini API with retry logic."""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt_text,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=8192
        )
    )
    return response.text

def process_batch_with_llm(batch_df):
    """Formats the batch and sends it to the LLM."""
    
    # Prepare the payload
    payload = []
    for _, row in batch_df.iterrows():
        payload.append({
            "row_id": int(row['row_id']),
            "akun": str(row['X akun']),
            "konten": str(row['Konten'])
        })
        
    prompt_text = SYSTEM_PROMPT + "\n\nInput Batch:\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    
    try:
        response_text = call_llm_api(prompt_text)
        
        # Try to parse the JSON
        try:
            # Ekstrak hanya dari kurung siku pertama hingga terakhir
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']')
            if start_idx != -1 and end_idx != -1:
                clean_json = response_text[start_idx:end_idx+1]
                # Smart Trimmer: Gunting kurung berlebih dari belakang jika gagap
                while clean_json:
                    try:
                        results = json.loads(clean_json)
                        return results
                    except json.JSONDecodeError:
                        end_idx = clean_json.rfind(']', 0, -1)
                        if end_idx == -1:
                            raise
                        clean_json = clean_json[:end_idx+1]
            else:
                results = json.loads(response_text)
                return results
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {e}\nRaw Response: {response_text}")
            
    except RetryError as re:
        err_msg = re.last_attempt.exception()
        # Log failed rows
        with open("error_log.txt", "a") as f:
            failed_ids = [p['row_id'] for p in payload]
            f.write(f"Failed to process batch with row_ids: {failed_ids}. Error: {err_msg}\n")
        raise Exception(f"API Limit/Error: {err_msg}")
    except Exception as e:
        # Log failed rows
        with open("error_log.txt", "a") as f:
            failed_ids = [p['row_id'] for p in payload]
            f.write(f"Failed to process batch with row_ids: {failed_ids}. Error: {e}\n")
        raise Exception(f"API Error: {e}")
