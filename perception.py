import json
import re
from pydantic import BaseModel, Field
from typing import List, Union, Optional, Literal
from logger_config import setup_logger

# Setup logger
logger = setup_logger('perception', 'perception.log')
logger.info("Perception module initialized")

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
    logger.debug(f"Cleaning LLM response text: {response_text[:100]}...")
    
    # Remove markdown code block formatting if present
    response_text = response_text.strip()
    if '```' in response_text:
        logger.debug("Removing markdown code block formatting")
        response_text = response_text.split('```')[1] if len(response_text.split('```')) > 1 else response_text
    response_text = response_text.replace('json\n', '').strip()
    
    cleaned_text = response_text.strip('`').strip('"').strip()
    logger.debug(f"Cleaned response text: {cleaned_text[:100]}...")
    return cleaned_text

def parse_and_validate_response(response_text: str):
    """Parse and validate the LLM response against expected schemas"""
    logger.info("Starting response parsing and validation")
    try:
        # Try to parse the cleaned response text
        try:
            logger.debug("Attempting to parse JSON response")
            response_json = json.loads(response_text)
        except json.JSONDecodeError:
            logger.debug("Initial JSON parse failed, attempting to extract JSON from text")
            # If initial parse fails, try to extract JSON from the text
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                response_text = json_match.group(0)
                response_json = json.loads(response_text)
                logger.debug("Successfully extracted and parsed JSON from text")
            else:
                logger.error("No valid JSON found in response")
                raise ValueError("No valid JSON found in response")
        
        if not isinstance(response_json, dict) or 'type' not in response_json:
            logger.error("Invalid response format: missing 'type' field or not a dictionary")
            raise ValueError("Invalid response format")
        
        # Validate response against expected schemas
        valid_types = ['function_call', 'powerpoint', 'final_answer']
        logger.debug(f"Validating response type: {response_json['type']}")
        if response_json['type'] not in valid_types:
            logger.error(f"Invalid response type: {response_json['type']}")
            raise ValueError(f"Invalid response type. Expected one of {valid_types}")
        
        # Validate against appropriate schema
        logger.debug(f"Validating against {response_json['type']} schema")
        if response_json['type'] == 'function_call':
            result = FunctionCallInput(**response_json)
        elif response_json['type'] == 'powerpoint':
            result = PowerPointOperationInput(**response_json)
        elif response_json['type'] == 'final_answer':
            result = FinalAnswerOutput(**response_json)
        
        logger.info(f"Successfully validated response as {response_json['type']}")
        return result
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        raise
    except Exception as e:
        logger.error(f"Error validating response: {e}")
        raise

def format_tool_response(result, iteration: int, func_name: str = None, arguments: dict = None) -> tuple[str, str]:
    """Format the response from a tool execution"""
    logger.debug(f"Formatting tool response for iteration {iteration}")
    
    # Get the full result content
    if hasattr(result, 'content'):
        logger.debug("Processing result with content attribute")
        if isinstance(result.content, list):
            iteration_result = [
                item.text if hasattr(item, 'text') else str(item)
                for item in result.content
            ]
        else:
            iteration_result = str(result.content)
    else:
        logger.debug("Processing result without content attribute")
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
    
    logger.info(f"Completed formatting response for iteration {iteration}")
    logger.debug(f"Formatted response: {response_str[:100]}...")
    
    return response_str, iteration_result