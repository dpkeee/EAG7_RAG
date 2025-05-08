from pydantic import BaseModel
from typing import List, Any, Dict, Optional, Union
from pydantic import BaseModel
from mcp import ClientSession

class MemoryItem(BaseModel):
    text: str
    type: str
    tool_name: Optional[str] = None
    user_query: Optional[str] = None
    tags: List[str] = []
    session_id: Optional[str] = None

# Input/Output models for tools

class PerceptionInput(BaseModel):
    user_input: str

class PerceptionResult(BaseModel):
    user_input: str
    intent: str
    entities: List[str]
    tool_hint: Optional[str] = None

# Input/Output models for memory
class MemoryInput(BaseModel):
    iteration: int
    function_name: str
    arguments: Dict[str, Any]
    result: Any

class MemoryOutput(BaseModel):
    memory_items: List[MemoryItem]

class GeneratePlanInput(BaseModel):
    perception: PerceptionResult
    memory_items: MemoryOutput
    tool_descriptions: Optional[str] = None

class GeneratePlanOutput(BaseModel):
    output: Dict[str, Any]

class ExecuteToolInput(BaseModel): 
    session: Any
    tools: list[Any]
    response: Union[str, Dict[str, Any]]

class ToolCallResult(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Union[str, list, dict]
    raw_response: Any

class AddInput(BaseModel):
    a: int
    b: int

class AddOutput(BaseModel):
    result: int

class SqrtInput(BaseModel):
    a: int

class SqrtOutput(BaseModel):
    result: float

class StringsToIntsInput(BaseModel):
    string: str

class StringsToIntsOutput(BaseModel):
    ascii_values: List[int]

class ExpSumInput(BaseModel):
    int_list: List[int]

class ExpSumOutput(BaseModel):
    result: float

 


