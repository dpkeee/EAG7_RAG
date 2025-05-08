from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv
#from google import genai
import google.generativeai as genai
from pydantic import BaseModel
from models import PerceptionInput, PerceptionResult
import re

# Optional: import log from agent if shared, else define locally
try:
    from agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{stage}] {msg}")

load_dotenv()

#client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))




def extract_perception(input: PerceptionInput) -> PerceptionResult:
    """Extracts intent, entities, and tool hints using LLM"""
    user_input = input.user_input
    prompt = f"""
You are an AI that extracts structured facts from user input and suggests the most appropriate tool to use.

Input: "{user_input}"

Return the response as a Python dictionary with keys:
- intent: (brief phrase about what the user wants)
- entities: a list of strings representing keywords or values (e.g., ["INDIA", "ASCII"])
- tool_hint: (name of the MCP tool that might be useful, if any)

IMPORTANT TOOL SELECTION RULES:
- If the query is about factual information, knowledge, or looking up information, ALWAYS suggest "search_documents"
- For questions about specific topics, people, places, or things, use "search_documents"
- For mathematical operations, use the appropriate math tool (add, subtract, etc.)
- If unsure, default to "search_documents" for information lookup

Available tools: search_documents, add, sqrt, subtract, multiply, divide, power, cbrt, factorial, log, remainder, sin, cos, tan, mine, strings_to_chars_to_int, int_list_to_exponential_sum, fibonacci_numbers

Output only the dictionary on a single line. Do NOT wrap it in ```json or other formatting. Ensure `entities` is a list of strings, not a dictionary.
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        
        raw = response.text.strip()
        clean = re.sub(r"^```json|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        log("perception", f"LLM output: {raw}")

        try:
            parsed = eval(clean)
        except Exception as e:
            log("perception", f"⚠️ Failed to parse cleaned output: {e}")
            # Return a default result with required fields
            return PerceptionResult(
                user_input=user_input,
                intent="unknown",
                entities=[],
                tool_hint=None
            )

        # Fix common issues
        if isinstance(parsed.get("entities"), dict):
            parsed["entities"] = list(parsed["entities"].values())

        return PerceptionResult(user_input=user_input, **parsed)

    except Exception as e:
        log("perception", f"⚠️ Extraction failed: {e}")
        # Return a default result with required fields
        return PerceptionResult(
            user_input=user_input,
            intent="unknown",
            entities=[],
            tool_hint=None
        )
