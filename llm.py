import os
import json
import random
import requests
from google import genai
from google.genai import types
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from dotenv import load_dotenv

load_dotenv()

# Build provider pool
providers = []

# 1. Load Gemini Keys (Bisa lebih dari 1 key dipisahkan koma)
gemini_keys_raw = os.getenv("GEMINI_API_KEYS", "")
if not gemini_keys_raw:
    # fallback to single key
    gemini_keys_raw = os.getenv("GEMINI_API_KEY", "")

for k in gemini_keys_raw.split(','):
    clean_k = k.replace('\n', '').replace('\r', '').replace('"', '').strip()
    if clean_k:
        providers.append({"type": "gemini", "client": genai.Client(api_key=clean_k)})

# 2. Load Groq Keys (Bisa lebih dari 1 key dipisahkan koma)
groq_keys_raw = os.getenv("GROQ_API_KEYS", "")
if not groq_keys_raw:
    groq_keys_raw = os.getenv("GROQ_API_KEY", "")
    
for k in groq_keys_raw.split(','):
    clean_k = k.replace('\n', '').replace('\r', '').replace('"', '').strip()
    if clean_k:
        providers.append({"type": "groq", "client": Groq(api_key=clean_k)})

# 3. Load OpenRouter Keys (Master Key untuk semua AI Gratis & OP)
openrouter_keys_raw = os.getenv("OPENROUTER_API_KEYS", "")
if not openrouter_keys_raw:
    openrouter_keys_raw = os.getenv("OPENROUTER_API_KEY", "")

for k in openrouter_keys_raw.split(','):
    clean_k = k.replace('\n', '').replace('\r', '').replace('"', '').strip()
    if clean_k:
        providers.append({"type": "openrouter", "client": clean_k})  # Simpan key-nya langsung

SYSTEM_PROMPT = """
You are a data parser specialized in Indonesian sociopolitical nuances.
Analyze the provided batch of social media posts.
Your output MUST be a strict JSON object containing a "data" array. Do not wrap the JSON in markdown blocks (e.g. ```json).
Just return the raw JSON object.

Expected Schema:
{
  "data": [
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
  ]
}
"""

@retry(wait=wait_exponential(multiplier=2, min=5, max=65), stop=stop_after_attempt(10))
def call_llm_api(prompt_text):
    """Calls the Gemini or Groq API with load balancing and retry logic."""
    if not providers:
        raise Exception("Tidak ada API Key yang valid (Gemini atau Groq) yang dikonfigurasi!")
        
    provider = random.choice(providers)
    
    if provider["type"] == "gemini":
        response = provider["client"].models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return response.text
    elif provider["type"] == "groq":
        response = provider["client"].chat.completions.create(
            messages=[
                {"role": "user", "content": prompt_text}
            ],
            model="llama3-70b-8192",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    elif provider["type"] == "openrouter":
        headers = {
            "Authorization": f"Bearer {provider['client']}",
            "Content-Type": "application/json"
        }
        
        # OpenRouter punya akses gratis ke banyak model elit. Kita acak agar tidak gampang limit!
        openrouter_models = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "google/gemini-2.0-flash-exp:free"
        ]
        
        data = {
            "model": random.choice(openrouter_models),
            "messages": [
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.1
        }
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        if resp.status_code != 200:
            raise Exception(f"OpenRouter Error {resp.status_code}: {resp.text}")
        return resp.json()["choices"][0]["message"]["content"]

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
        
        # SMART TRIMMER: Handle JSON Hallucinations
        clean_json = response_text.strip()
        
        # Remove markdown if any
        if clean_json.startswith("```json"): clean_json = clean_json[7:]
        if clean_json.startswith("```"): clean_json = clean_json[3:]
        if clean_json.endswith("```"): clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        # Find outermost brackets (either { or [)
        start_idx = clean_json.find('{')
        if start_idx == -1:
            start_idx = clean_json.find('[')
            
        if start_idx != -1:
            clean_json = clean_json[start_idx:]
            
        # Try parsing and trimming from right
        parsed = None
        while clean_json:
            try:
                parsed = json.loads(clean_json)
                break
            except json.JSONDecodeError:
                # Find the next rightmost closing bracket
                end_idx_dict = clean_json.rfind('}', 0, -1)
                end_idx_list = clean_json.rfind(']', 0, -1)
                end_idx = max(end_idx_dict, end_idx_list)
                if end_idx == -1:
                    break
                clean_json = clean_json[:end_idx+1]
                
        if parsed is None:
            raise Exception(f"Gagal total JSON Trimmer\nRaw: {response_text}")
            
        # Extract the array robustly
        if isinstance(parsed, dict) and "data" in parsed:
            return parsed["data"]
        elif isinstance(parsed, list):
            return parsed
        else:
            return [parsed]
            
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
