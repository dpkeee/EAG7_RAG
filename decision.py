from perception import PerceptionResult
from memory import MemoryItem
from typing import List, Optional
from dotenv import load_dotenv
from models import GeneratePlanInput, GeneratePlanOutput    
#from google import genai
import google.generativeai as genai
import os

# Optional: import log from agent if shared, else define locally
try:
    from .agent import log
except ImportError:
    import datetime
    def log(stage: str, msg: str):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] [{stage}] {msg}")

load_dotenv()
#client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_plan(
    perception: PerceptionResult,
    memory_items: List[MemoryItem],
    tool_descriptions: Optional[str] = None
) -> str:
   """Generates a plan using LLM based on structured perception and memory."""
   memory_texts = "\n".join(f"- {m.text}" for m in memory_items) or "None"
   tool_context = f"\nYou have access to the following tools:\n{tool_descriptions}" if tool_descriptions else ""

   prompt = f"""
    You are a reasoning-driven AI agent with access to tools. {tool_context}The tool descriptions include both the tool names and their required parameter names. These are the ONLY allowed names. Your job is to solve the user's request step-by-step by:"""+"""
    
    1. If using a tool, respond in this format:
        FUNCTION_CALL: tool_name|param1=value1|param2=value2
                          
    2. If the result is final, respond in this format:
        "FINAL_ANSWER": "Final result"
    3. If you're uncertain, a tool fails, or an answer cannot be computed reliably, explain why and stop with:
        {{"ERROR": "Explanation of the issue"}}"""+f"""

    Guidelines:
    - Respond using EXACTLY ONE of the formats above per step.
    - You can reference these relevant memories:
    {memory_texts}
    
Input Summary:
- User input: "{perception.user_input}"
- Intent: {perception.intent}
- Entities: {', '.join(perception.entities)}
- Tool hint: {perception.tool_hint or 'None'}
    
✅ Examples:
- FUNCTION_CALL: search_documents|query=In 2023, which country is largest producer of Gold?
   
- FINAL_ANSWER: The largest producer of Gold in 2023 is China.
    
    IMPORTANT:
    - 🚫 Do NOT invent tools. Use only the tools listed below.
    - 📄 If the question may relate to factual knowledge, use the 'search_documents' tool to look for the answer.
    - 🤖 If the previous tool output already contains factual information, DO NOT search again. Instead, consolidate all the relevant facts (Do NOT skimp out on facts provided to the user) and respond with: {{"FINAL_ANSWER": "your final answer"}} 
    - ❌ Do NOT use `search_documents` multiple times. 
    - ❌ Do NOT repeat function calls with the same parameters.
    - ❌ Do NOT output unstructured responses.
    - ❌ Do NOT include ANY extra text, markers, or formatting such as: tool_code, json, function_call, or similar. 
    - ✅ Use exactly the parameter names as listed in the tool descriptions. Do NOT invent or change parameter names.
    - ✅ Only provide a FINAL_ANSWER if all parts of the user's request are fully satisfied (for example emailing the results) and no further action is required. If any part is incomplete or uncertain, proceed with a FUNCTION_CALL instead.
     """
   try:
        # response = client.models.generate_content(
        #     model="gemini-2.0-flash",
        #     contents=prompt
        # )
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        
        raw = response.text.strip()
        log("plan", f"LLM output: {raw}")

        for line in raw.splitlines():
            log("plan", f"line output: {line.strip()}")
            if line.strip().startswith("FUNCTION_CALL:") or line.strip().startswith("FINAL_ANSWER:"):
                return line.strip()
        return raw.strip()

   except Exception as e:
        log("plan", f"⚠️ Decision generation failed: {e}")
        return "FINAL_ANSWER: [unknown]"
