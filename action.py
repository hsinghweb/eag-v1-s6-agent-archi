import os
from logger_config import setup_logger
from memory import Memory
from perception import format_tool_response
from typing import Dict, Any, Optional
import time

# Setup logger
logger = setup_logger('action', 'action.log')

class Action:
    def __init__(self, session):
        self.session = session
        self.memory = Memory()
        self.tools = []
        
    def set_tools(self, tools):
        """Set available tools after session initialization"""
        self.tools = tools
        logger.info(f"Tools set: {[tool.name for tool in tools]}")

    async def execute_function_call(self, func_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a function call with given parameters"""
        logger.info(f"[Calling Tool] Function name: {func_name}")
        logger.info(f"[Calling Tool] Parameters: {params}")
        
        try:
            # Find the matching tool to get its input schema
            tool = next((t for t in self.tools if t.name == func_name), None)
            if not tool:
                logger.error(f"Unknown tool: {func_name}")
                raise ValueError(f"Unknown tool: {func_name}")

            logger.info(f"[Calling Tool] Found tool: {tool.name}")
            logger.info(f"[Calling Tool] Tool schema: {tool.inputSchema}")

            # Prepare arguments according to the tool's input schema
            arguments = {}
            schema_properties = tool.inputSchema.get('properties', {})
            logger.debug(f"[Calling Tool] Schema properties: {schema_properties}")

            for param_name, param_info in schema_properties.items():
                # Use the correct parameter name from the tool's schema
                param_value = params.get(param_name, params.get('numbers')) if func_name == 'int_list_to_exponential_sum' else params.get(param_name)
                
                if param_value is None:  # Check if parameter is provided
                    if param_name in tool.inputSchema.get('required', []):
                        raise ValueError(f"Required parameter {param_name} not provided for {func_name}")
                    continue
                    
                param_type = param_info.get('type', 'string')
                
                logger.debug(f"[Calling Tool] Converting parameter {param_name} with value {param_value} to type {param_type}")
                
                # Convert the value to the correct type based on the schema
                if param_type == 'integer':
                    arguments[param_name] = int(param_value)
                elif param_type == 'number':
                    arguments[param_name] = float(param_value)
                elif param_type == 'array':
                    logger.debug(f"Processing array parameter {param_name} with value {param_value}")
                    try:
                        # Handle result from strings_to_chars_to_int function
                        if isinstance(param_value, (list, tuple)):
                            arguments[param_name] = [int(x) for x in param_value]
                        elif isinstance(param_value, str):
                            # Handle string representation of array
                            if param_value.startswith('[') and param_value.endswith(']'):
                                array_str = param_value.strip('[]')
                                arguments[param_name] = [int(x.strip()) for x in array_str.split(',')] if array_str else []
                            else:
                                # Handle comma-separated string without brackets
                                arguments[param_name] = [int(x.strip()) for x in param_value.split(',')] if ',' in param_value else [int(param_value)]
                        else:
                            logger.error(f"Invalid type for array parameter {param_name}: {type(param_value)}")
                            raise ValueError(f"Invalid array format for parameter {param_name}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error converting value to array: {str(e)}")
                        raise ValueError(f"Failed to convert {param_value} to integer array: {str(e)}")
                else:
                    arguments[param_name] = str(param_value)

            logger.info(f"[Calling Tool] Final arguments: {arguments}")
            logger.info(f"[Calling Tool] Calling tool {func_name}")
            
            result = await self.session.call_tool(func_name, arguments=arguments)
            logger.info(f"[Calling Tool] Raw result: {result}")
            
            response_str, iteration_result = format_tool_response(result, self.memory.current_iteration, func_name, arguments)
            self.memory.add_memory('tool_result', iteration_result)
            self.memory.add_memory('iteration_response', response_str)
            
            return result

        except Exception as e:
            logger.error(f"Error in execute_function_call: {str(e)}")
            import traceback
            traceback.print_exc()
            self.memory.add_memory('iteration_response', f"Error in iteration {self.memory.current_iteration + 1}: {str(e)}")
            return None

    async def execute_powerpoint_operation(self, operation: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a PowerPoint operation with given parameters"""
        logger.info(f"[Calling Tool] PowerPoint operation: {operation}")
        logger.info(f"[Calling Tool] PowerPoint parameters: {params}")
        
        try:
            if operation == "open_powerpoint":
                if not self.memory.is_powerpoint_open:
                    result = await self.session.call_tool("open_powerpoint")
                    self.memory.set_powerpoint_state(True)
                else:
                    self.memory.add_memory('iteration_response', "PowerPoint is already open")
                    return None
                    
            elif operation == "draw_rectangle":
                if self.memory.is_powerpoint_open:
                    try:
                        result = await self.session.call_tool(
                            "draw_rectangle",
                            arguments=params
                        )
                    except Exception as e:
                        logger.error(f"[Calling Tool] Error with rectangle parameters: {e}")
                        self.memory.add_memory('iteration_response', f"Error: Invalid rectangle parameters - {str(e)}")
                        return None
                else:
                    self.memory.add_memory('iteration_response', "PowerPoint must be opened first")
                    return None
                    
            elif operation == "add_text_in_powerpoint":
                if self.memory.is_powerpoint_open:
                    text = params.get('text', '')
                    
                    # If this is the final result text, append the calculated value
                    if "Final Result:" in text:
                        calc_result = self.memory.get_last_calculation_result()
                        if calc_result:
                            text = f"Final Result:\n{calc_result}"
                    
                    result = await self.session.call_tool(
                        "add_text_in_powerpoint",
                        arguments={"text": text}
                    )
                else:
                    self.memory.add_memory('iteration_response', "PowerPoint must be opened first")
                    return None
                    
            elif operation == "close_powerpoint":
                if self.memory.is_powerpoint_open:
                    result = await self.session.call_tool("close_powerpoint")
                    self.memory.set_powerpoint_state(False)
                else:
                    self.memory.add_memory('iteration_response', "PowerPoint is not open")
                    return None
            else:
                self.memory.add_memory('iteration_response', f"Unknown PowerPoint operation: {operation}")
                return None
            
            response_str, iteration_result = format_tool_response(result, self.memory.current_iteration)
            self.memory.add_memory('tool_result', iteration_result)
            self.memory.add_memory('iteration_response', response_str)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in PowerPoint operation: {e}")
            self.memory.add_memory('iteration_response', f"Error in PowerPoint operation: {str(e)}")
            return None