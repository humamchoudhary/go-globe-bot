# gemini_quota_test.py
import os
import time
from google import genai
from google.genai import types

API_KEY = ""
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # try gemini-1.5-flash too

def run_once(prompt):
    if not API_KEY:
        raise RuntimeError("Set GEMINI_API_KEY first")

    client = genai.Client(api_key=API_KEY)

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=200,
                temperature=0.2
            ),
        )

        print("OK")
        print("Model:", MODEL)
        print("Text:", (response.text or "")[:300])

        usage = getattr(response, "usage_metadata", None)
        if usage:
            # SDK versions differ, so use safe access
            print("Usage metadata:", usage)

    except Exception as e:
        print("FAILED")
        print("Model:", MODEL)
        print("Error type:", type(e).__name__)
        print("Error text:", str(e))

        # Some SDK errors include response details
        for attr in ["status_code", "code", "message", "details", "response"]:
            if hasattr(e, attr):
                print(f"{attr}:", getattr(e, attr))

if __name__ == "__main__":
    run_once("Return exactly: hello")