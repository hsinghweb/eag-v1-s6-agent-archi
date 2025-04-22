import os
import sys
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
from decision import DecisionMaker
from action import Action
from prompt_config import MATH_AGENT_SYSTEM_PROMPT

# Setup logger
logger = setup_logger('ai_agent', 'ai_agent.log')

# Initialize global memory and decision maker
memory = Memory()
decision_maker = DecisionMaker()

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
    decision_maker.reset()
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

                    # Initialize action layer with session and tools
                    action = Action(session)
                    action.set_tools(tools)
                    
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
                        
                        # Get next action from decision maker
                        current_state = {
                            "iteration": memory.current_iteration,
                            "powerpoint_open": memory.is_powerpoint_open,
                            "last_response": memory.last_response
                        }
                        
                        next_action = await decision_maker.decide_next_action(current_state)
                        if not next_action or not decision_maker.validate_decision(next_action):
                            logger.error("Invalid or no decision returned")
                            break

                        # If we have a final answer, we're done
                        if next_action["type"] == "final_answer":
                            value = next_action["value"]
                            memory.add_memory('iteration_response', f"Final answer: {value}")
                            print("\nFinal Results:")
                            for resp in memory.get_recent_memories(type='iteration_response'):
                                print(resp.content)
                            return

                        # Get context from memory for the prompt
                        context = memory.get_context_for_prompt()
                        current_query = query if not context else f"{query}\n\n{context}"

                        # Prepare prompt with current phase information
                        phase_context = ""
                        if "phase" in next_action:
                            phase_context = f"\nCurrent phase: {next_action['phase']}"
                            if "status" in next_action:
                                phase_context += f"\nStatus: {next_action['status']}"
                        prompt = f"{system_prompt}\n\nQuery: {current_query}{phase_context}"

                        # Get model's response with timeout
                        try:
                            response = await generate_with_timeout(client, prompt)
                            response_text = clean_llm_response(response.text)
                            print(f"LLM Response: {response_text}")
                            memory.add_memory('llm_response', response_text)
                            response_json = parse_and_validate_response(response_text)
                            
                        except Exception as e:
                            logger.error(f"Failed to get or parse LLM response: {e}")
                            break

                        # Execute action based on response type
                        if response_json.type == 'function_call':
                            await action.execute_function_call(response_json.function, response_json.params)
                        elif response_json.type == 'powerpoint':
                            await action.execute_powerpoint_operation(response_json.operation, response_json.params)
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


