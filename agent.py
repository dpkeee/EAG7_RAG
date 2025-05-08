import asyncio
import time
import os
import datetime
from perception import extract_perception
from memory import MemoryManager, MemoryItem
from decision import generate_plan
from action import execute_tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from models import PerceptionInput, GeneratePlanInput,ExecuteToolInput, MemoryOutput
 # use this to connect to running server

import shutil
import sys

def log(stage: str, msg: str):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{stage}] {msg}")

max_steps = 3

async def main(user_input: str):
    try:
        print("[agent] Starting agent...")
        print(f"[agent] Current working directory: {os.getcwd()}")
        
        server_params = StdioServerParameters(
            command="python",
            args=["C:/Users/vamsi/EAG/Week_7/RAG-BACKEND/mcp_server.py"]
             #cwd="C:/Users/vamsi/EAG/Week_7/RAG-BACKEND"
        )

        try:
            async with stdio_client(server_params) as (read, write):
                print("Connection established, creating session...")
                try:
                    async with ClientSession(read, write) as session:
                        print("[agent] Session created, initializing...")
 
                        try:
                            await session.initialize()
                            print("[agent] MCP session initialized")

                            # Your reasoning, planning, perception etc. would go here
                            tools = await session.list_tools()
                            print("Available tools:", [t.name for t in tools.tools])

                            # Get available tools
                            print("Requesting tool list...")
                            tools_result = await session.list_tools()
                            tools = tools_result.tools
                            tool_descriptions = "\n".join(
                                f"- {tool.name}: {getattr(tool, 'description', 'No description')}" 
                                for tool in tools
                            )

                            log("agent", f"{len(tools)} tools loaded")

                            memory = MemoryManager()
                            session_id = f"session-{int(time.time())}"
                            query = user_input  # Store original intent
                            step = 0
                            # final_result = None
                            # last_tool_result = None

                            while step < max_steps:
                                log("loop", f"Step {step + 1} started")
                                                          

                                perception = extract_perception(PerceptionInput(user_input=query))
                                log("perception", f"Intent: {perception.intent}, Tool hint: {perception.tool_hint}")

                                retrieved = memory.retrieve(query=user_input, top_k=3, session_filter=session_id)
                                log("memory", f"Retrieved {len(retrieved)} relevant memories")

                                plan = generate_plan(
                                    perception=perception,
                                    memory_items=retrieved,
                                    tool_descriptions=tool_descriptions
                                )
                                log("plan", f"Plan generated: {plan}")

                                if plan.startswith("FINAL_ANSWER:"):
                                    log("agent", f'✅ FINAL RESULT: {plan}')
                                    break

                                try:
                                    if plan.startswith("FUNCTION_CALL:"):
                                        # Parse the function call string into a dictionary
                                        parts = plan.replace("FUNCTION_CALL: ", "").split("|")
                                        tool_name = parts[0]
                                        params = {}
                                        for param in parts[1:]:
                                            key, value = param.split("=")
                                            params[key] = value
                                        
                                        # Create the response dictionary
                                        response_dict = {
                                            "function": tool_name,
                                            "parameters": params
                                        }
                                        
                                        result = await execute_tool(ExecuteToolInput(
                                            session=session, 
                                            tools=tools, 
                                            response=response_dict
                                        ))
                                        log("tool", f"{result.tool_name} returned: {result.result}")
                                        last_tool_result = result.result

                                        # Format the search results into a meaningful response
                                        if result.tool_name == "search_documents":
                                            if isinstance(result.result, list):
                                                formatted_response = "Here's what I found:\n\n"
                                                for i, item in enumerate(result.result, 1):
                                                    formatted_response += f"{i}. {item}\n\n"
                                                final_result = formatted_response
                                            else:
                                                final_result = str(result.result)
                                        else:
                                            final_result = str(result.result)

                                        memory.add(MemoryItem(
                                            text=f"Tool call: {result.tool_name} with {result.arguments}, got: {result.result}",
                                            type="tool_output",
                                            tool_name=result.tool_name,
                                            user_query=user_input,
                                            tags=[result.tool_name],
                                            session_id=session_id
                                        ))

                                        user_input = f"Original task: {query}\nPrevious output: {result.result}\nWhat should I do next?"

                                    else:
                                        result = await execute_tool(ExecuteToolInput(
                                            session=session, 
                                            tools=tools, 
                                            response=plan  # Pass the plan string directly
                                        ))
                                        log("tool", f"{result.tool_name} returned: {result.result}")
                                        last_tool_result = result.result

                                        memory.add(MemoryItem(
                                            text=f"Tool call: {result.tool_name} with {result.arguments}, got: {result.result}",
                                            type="tool_output",
                                            tool_name=result.tool_name,
                                            user_query=user_input,
                                            tags=[result.tool_name],
                                            session_id=session_id
                                        ))

                                        user_input = f"Original task: {query}\nPrevious output: {result.result}\nWhat should I do next?"

                                except Exception as e:
                                    log("error", f"Tool execution failed: {e}")
                                    break

                                step += 1
                        except Exception as e:
                            print(f"[agent] Session initialization error: {str(e)}")
                except Exception as e:
                    print(f"[agent] Session creation error: {str(e)}")
        except Exception as e:
            import traceback
            print(f"[agent] Connection error: {str(e)}")
            traceback.print_exc()
    except Exception as e:
        print(f"[agent] Overall error: {str(e)}")

    log("agent", "Agent session complete.")
    if final_result is None:
        final_result = "No final answer found."
    return final_result

if __name__ == "__main__":
    query = input("🧑 What do you want to solve today? → ")
    asyncio.run(main(query))


# Find the ASCII values of characters in INDIA and then return sum of exponentials of those values.
# How much Anmol singh paid for his DLF apartment via Capbridge? 
# What do you know about Don Tapscott and Anthony Williams?
# What is the relationship between Gensol and Go-Auto?