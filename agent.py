import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import asyncio
from google import genai
from concurrent.futures import TimeoutError
from functools import partial
from logger_config import setup_logger
from perception import (
    clean_llm_response, parse_and_validate_response, format_tool_response
)
from memory import Memory
from prompt_config import MATH_AGENT_SYSTEM_PROMPT

# Setup logger
logger = setup_logger('ai_agent', 'ai_agent.log')

# Initialize global memory
memory = Memory()

# Load environment variables from .env file
logger.info('Loading environment variables')
load_dotenv()

# Access your API key and initialize Gemini client correctly
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error('GEMINI_API_KEY not found in environment variables')
    raise ValueError('GEMINI_API_KEY not found')

logger.info('Initializing Gemini client')
client = genai.Client(api_key=api_key)

max_iterations = 10

async def generate_with_timeout(client, prompt, timeout=10):
    """Generate content with a timeout"""
    logger.info('Starting LLM generation')
    logger.debug(f'Prompt length: {len(prompt)}')
    logger.info(f'Prompt request: {prompt}')
    try:
        # Convert the synchronous generate_content call to run in a thread
        loop = asyncio.get_event_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None, 
                lambda: client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
            ),
            timeout=timeout
        )
        logger.info('LLM generation completed successfully')
        logger.info(f'Prompt response: {response.text}')
        return response
    except TimeoutError:
        logger.error(f'LLM generation timed out after {timeout} seconds')
        raise
    except Exception as e:
        logger.error(f'Error in LLM generation: {str(e)}')
        raise

def reset_state():
    """Reset all state using memory layer"""
    logger.debug('Resetting global state')
    memory.reset()
    logger.info('Global state reset completed')

async def main():
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            reset_state()  # Reset at the start of main
            logger.info("Starting main execution")
            
            # Create a single MCP server connection
            logger.info("Establishing connection to MCP server")
            server_params = StdioServerParameters(
                command="python",
                args=["mcp-server.py", "dev"]
            )

            async with stdio_client(server_params) as (read, write):
                logger.info("Connection established, creating session")
                async with ClientSession(read, write) as session:
                    logger.info("Session created, initializing")
                    try:
                        await session.initialize()
                        logger.info("Session initialized successfully")
                    except Exception as e:
                        logger.error(f"Failed to initialize session: {str(e)}")
                        continue
                    
                    # Get available tools
                    logger.info("Requesting tool list")
                    try:
                        tools_result = await session.list_tools()
                        tools = tools_result.tools
                        logger.info(f"Successfully retrieved {len(tools)} tools")
                        logger.debug(f"Available tools: {[tool.name for tool in tools]}")
                    except Exception as e:
                        logger.error(f"Failed to get tool list: {str(e)}")
                        continue
                    
                    # Create system prompt with available tools
                    print("Creating system prompt...")
                    print(f"Number of tools: {len(tools)}")
                    
                    try:
                        tools_description = []
                        for i, tool in enumerate(tools):
                            try:
                                params = tool.inputSchema
                                desc = getattr(tool, 'description', 'No description available')
                                name = getattr(tool, 'name', f'tool_{i}')
                                
                                if 'properties' in params:
                                    param_details = []
                                    for param_name, param_info in params['properties'].items():
                                        param_type = param_info.get('type', 'unknown')
                                        param_details.append(f"{param_name}: {param_type}")
                                    params_str = ', '.join(param_details)
                                else:
                                    params_str = 'no parameters'

                                tool_desc = f"{i+1}. {name}({params_str}) - {desc}"
                                tools_description.append(tool_desc)
                                print(f"Added description for tool: {tool_desc}")
                            except Exception as e:
                                print(f"Error processing tool {i}: {e}")
                                tools_description.append(f"{i+1}. Error processing tool")
                        
                        tools_description = "\n".join(tools_description)
                        print("Successfully created tools description")
                    except Exception as e:
                        print(f"Error creating tools description: {e}")
                        tools_description = "Error loading tools"
                    
                    print("Creating system prompt...")
                    system_prompt = MATH_AGENT_SYSTEM_PROMPT + """\nAvailable Tools: """ + tools_description
                    print("System prompt created\n", system_prompt)

                    query = """Find the ASCII values of characters in HIMANSHU and then return sum of exponentials of those values. 
                    Also, create a PowerPoint presentation showing the Final Answer inside a rectangle box."""
                    print("Starting iteration loop...")
                    
                    while memory.current_iteration < max_iterations:
                        print(f"\n--- Iteration {memory.current_iteration + 1} ---")
                        
                        # Get context from memory for the prompt
                        context = memory.get_context_for_prompt()
                        current_query = query if not context else f"{query}\n\n{context}"

                        # Get model's response with timeout
                        print("Preparing to generate LLM response...")
                        prompt = f"{system_prompt}\n\nQuery: {current_query}"
                        try:
                            response = await generate_with_timeout(client, prompt)
                            response_text = clean_llm_response(response.text)
                            print(f"LLM Response: {response_text}")
                            
                            # Store LLM response in memory
                            memory.add_memory('llm_response', response_text)
                            
                            # Parse and validate the response
                            try:
                                response_json = parse_and_validate_response(response_text)
                            except Exception as e:
                                print(f"Failed to parse response: {e}")
                                break
                            
                        except Exception as e:
                            print(f"Failed to get LLM response: {e}")
                            break

                        if response_json.type == 'function_call':
                            func_name = response_json.function
                            params = response_json.params
                            
                            print(f"[Calling Tool] Function name: {func_name}")
                            print(f"[Calling Tool] Parameters: {params}")
                            
                            try:
                                # Find the matching tool to get its input schema
                                tool = next((t for t in tools if t.name == func_name), None)
                                if not tool:
                                    print(f"[Calling Tool] Available tools: {[t.name for t in tools]}")
                                    raise ValueError(f"Unknown tool: {func_name}")

                                print(f"[Calling Tool] Found tool: {tool.name}")
                                print(f"[Calling Tool] Tool schema: {tool.inputSchema}")

                                # Prepare arguments according to the tool's input schema
                                arguments = {}
                                schema_properties = tool.inputSchema.get('properties', {})
                                print(f"[Calling Tool] Schema properties: {schema_properties}")

                                for param_name, param_info in schema_properties.items():
                                    # Use the correct parameter name from the tool's schema
                                    param_value = params.get(param_name, params.get('numbers')) if func_name == 'int_list_to_exponential_sum' else params.get(param_name)
                                    
                                    if param_value is None:  # Check if parameter is provided
                                        if param_name in tool.inputSchema.get('required', []):
                                            raise ValueError(f"Required parameter {param_name} not provided for {func_name}")
                                        continue
                                        
                                    param_type = param_info.get('type', 'string')
                                    
                                    print(f"[Calling Tool] Converting parameter {param_name} with value {param_value} to type {param_type}")
                                    
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

                                print(f"[Calling Tool] Final arguments: {arguments}")
                                print(f"[Calling Tool] Calling tool {func_name}")
                                
                                result = await session.call_tool(func_name, arguments=arguments)
                                print(f"[Calling LLM] Raw result: {result}")
                                
                                response_str, iteration_result = format_tool_response(result, memory.current_iteration, func_name, arguments)
                                memory.add_memory('tool_result', iteration_result)
                                memory.add_memory('iteration_response', response_str)

                            except Exception as e:
                                print(f"[Calling LLM] Error details: {str(e)}")
                                print(f"[Calling LLM] Error type: {type(e)}")
                                import traceback
                                traceback.print_exc()
                                memory.add_memory('iteration_response', f"Error in iteration {memory.current_iteration + 1}: {str(e)}")
                                break

                        elif response_json.type == 'powerpoint':
                            operation = response_json.operation
                            params = response_json.params
                            
                            print(f"[Calling Tool] PowerPoint operation: {operation}")
                            print(f"[Calling Tool] PowerPoint parameters: {params}")
                            
                            try:
                                if operation == "open_powerpoint":
                                    if not memory.is_powerpoint_open:
                                        result = await session.call_tool("open_powerpoint")
                                        memory.set_powerpoint_state(True)
                                    else:
                                        memory.add_memory('iteration_response', "PowerPoint is already open")
                                        continue
                                elif operation == "draw_rectangle":
                                    if memory.is_powerpoint_open:
                                        try:
                                            result = await session.call_tool(
                                                "draw_rectangle",
                                                arguments=params
                                            )
                                        except Exception as e:
                                            print(f"[Calling Tool] Error with rectangle parameters: {e}")
                                            memory.add_memory('iteration_response', f"Error: Invalid rectangle parameters - {str(e)}")
                                            continue
                                    else:
                                        memory.add_memory('iteration_response', "PowerPoint must be opened first")
                                        continue
                                elif operation == "add_text_in_powerpoint":
                                    if memory.is_powerpoint_open:
                                        text = params.get('text', '')
                                        
                                        # If this is the final result text, append the calculated value
                                        if "Final Result:" in text:
                                            calc_result = memory.get_last_calculation_result()
                                            if calc_result:
                                                text = f"Final Result:\n{calc_result}"
                                        
                                        result = await session.call_tool(
                                            "add_text_in_powerpoint",
                                            arguments={"text": text}
                                        )
                                    else:
                                        memory.add_memory('iteration_response', "PowerPoint must be opened first")
                                        continue
                                elif operation == "close_powerpoint":
                                    if memory.is_powerpoint_open:
                                        result = await session.call_tool("close_powerpoint")
                                        memory.set_powerpoint_state(False)
                                    else:
                                        memory.add_memory('iteration_response', "PowerPoint is not open")
                                        continue
                                else:
                                    memory.add_memory('iteration_response', f"Unknown PowerPoint operation: {operation}")
                                    continue
                                
                                response_str, iteration_result = format_tool_response(result, memory.current_iteration)
                                memory.add_memory('tool_result', iteration_result)
                                memory.add_memory('iteration_response', response_str)
                                
                            except Exception as e:
                                print(f"Error in PowerPoint operation: {e}")
                                memory.add_memory('iteration_response', f"Error in PowerPoint operation: {str(e)}")
                                break
                                
                        elif response_json.type == 'final_answer':
                            value = response_json.value
                            memory.add_memory('iteration_response', f"Final answer: {value}")
                            break
                            
                        memory.increment_iteration()
                        
                    if memory.current_iteration >= max_iterations:
                        print("Reached maximum iterations")
                        break
                        
                    print("\nFinal Results:")
                    for resp in memory.get_recent_memories(type='iteration_response'):
                        print(resp.content)
                        
                    return
                    
        except Exception as e:
            print(f"Error in main loop: {e}")
            retry_count += 1
            if retry_count >= max_retries:
                print("Maximum retries reached")
                break
            print(f"Retrying... ({retry_count}/{max_retries})")
            continue

if __name__ == "__main__":
    asyncio.run(main())


