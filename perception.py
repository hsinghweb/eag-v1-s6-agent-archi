import json
import re
from pydantic import BaseModel, Field
from typing import List, Union, Optional, Literal
from logger_config import setup_logger

# Setup logger
logger = setup_logger('perception', 'ai_agent.log')

# Pydantic Models for Input/Output Validation
class FunctionCallInput(BaseModel):
    type: Literal["function_call"] = Field(default="function_call")
    function: str
    params: dict

class PowerPointOperationInput(BaseModel):
    type: Literal["powerpoint"] = Field(default="powerpoint")
    operation: str
    params: dict

class FinalAnswerOutput(BaseModel):
    type: Literal["final_answer"] = Field(default="final_answer")
    value: Union[str, int, float]

class ArrayInput(BaseModel):
    values: List[int] = Field(..., min_items=1)

def clean_llm_response(response_text: str) -> str:
    """Clean up the LLM response text by removing markdown and other formatting"""
    # Remove markdown code block formatting if present
    response_text = response_text.strip()
    if '```' in response_text:
        response_text = response_text.split('```')[1] if len(response_text.split('```')) > 1 else response_text
    response_text = response_text.replace('json\n', '').strip()
    # Remove any leading/trailing whitespace or quotes
    return response_text.strip('`').strip('"').strip()

def parse_and_validate_response(response_text: str):
    """Parse and validate the LLM response against expected schemas"""
    try:
        # Try to parse the cleaned response text
        try:
            response_json = json.loads(response_text)
        except json.JSONDecodeError:
            # If initial parse fails, try to extract JSON from the text
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                response_text = json_match.group(0)
                response_json = json.loads(response_text)
            else:
                raise ValueError("No valid JSON found in response")
        
        if not isinstance(response_json, dict) or 'type' not in response_json:
            raise ValueError("Invalid response format")
        
        # Validate response against expected schemas
        valid_types = ['function_call', 'powerpoint', 'final_answer']
        if response_json['type'] not in valid_types:
            raise ValueError(f"Invalid response type. Expected one of {valid_types}")
        
        # Validate against appropriate schema
        if response_json['type'] == 'function_call':
            return FunctionCallInput(**response_json)
        elif response_json['type'] == 'powerpoint':
            return PowerPointOperationInput(**response_json)
        elif response_json['type'] == 'final_answer':
            return FinalAnswerOutput(**response_json)
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        raise
    except Exception as e:
        logger.error(f"Error validating response: {e}")
        raise

def format_tool_response(result, iteration: int, func_name: str = None, arguments: dict = None) -> tuple[str, str]:
    """Format the response from a tool execution"""
    # Get the full result content
    if hasattr(result, 'content'):
        if isinstance(result.content, list):
            iteration_result = [
                item.text if hasattr(item, 'text') else str(item)
                for item in result.content
            ]
        else:
            iteration_result = str(result.content)
    else:
        iteration_result = str(result)
        
    # Format the response based on result type
    if isinstance(iteration_result, list):
        result_str = f"[{', '.join(iteration_result)}]"
    else:
        result_str = str(iteration_result)
    
    # Create iteration response string
    if func_name and arguments:
        response_str = (
            f"In the {iteration + 1} iteration you called {func_name} with {arguments} parameters, "
            f"and the function returned {result_str}."
        )
    else:
        response_str = f"In the {iteration + 1} iteration the operation returned {result_str}."
    
    return response_str, iteration_result