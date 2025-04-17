import logging
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
from mcp import ClientSession

logger = logging.getLogger('ai_agent.action')

class ActionInput(BaseModel):
    action_type: str
    action_details: Dict[str, Any]
    session: ClientSession

class ActionOutput(BaseModel):
    result: Dict[str, Any]
    iteration_response: List[str]

def validate_action_input(action_input: Dict[str, Any]) -> bool:
    """Validate action input against expected schemas"""
    valid_types = ['function_call', 'powerpoint', 'final_answer']
    return action_input.get('type') in valid_types

async def execute_action(input_data: ActionInput) -> ActionOutput:
    """
    Execute the determined action (function call, PowerPoint operation, or final answer)
    """
    logger.info(f'Executing action of type: {input_data.action_type}')
    
    if input_data.action_type == 'function_call':
        try:
            result = await input_data.session.call_tool(
                input_data.action_details['function'],
                arguments=input_data.action_details['params']
            )
            
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
            
            return ActionOutput(
                result={'type': 'function_call_result', 'content': iteration_result},
                iteration_response=[iteration_result]
            )
        except Exception as e:
            logger.error(f'Failed to execute function call: {str(e)}')
            return ActionOutput(
                result={'type': 'error', 'message': str(e)},
                iteration_response=[]
            )
    
    # TODO: Implement other action types (powerpoint, final_answer)
    return ActionOutput(result={}, iteration_response=[])