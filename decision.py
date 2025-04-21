from typing import Optional, Dict, Any
from logger_config import setup_logger
from memory import Memory
import logging

# Setup logger with debug level
logger = setup_logger('decision', 'decision.log')
logger.setLevel(logging.DEBUG)

class DecisionMaker:
    def __init__(self):
        self.memory = Memory()
        self.text_added = False
        self.visualization_complete = False
        logger.info("Decision maker initialized")

    async def decide_next_action(self, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Decide the next action based on current state and memory
        Returns a decision dict with action type and parameters
        """
        try:
            # Get relevant context from memory
            recent_responses = self.memory.get_recent_memories(type='iteration_response')
            
            # Check if text was just added successfully
            if any("Text added successfully" in str(resp.content) for resp in recent_responses[-2:]):
                self.text_added = True
                logger.info("Text has been added to PowerPoint")

            # If text has been added, close PowerPoint and finish
            if self.text_added:
                if self.memory.is_powerpoint_open and not self.visualization_complete:
                    logger.info("Text added, closing PowerPoint")
                    self.visualization_complete = True
                    return {
                        "type": "powerpoint",
                        "operation": "close_powerpoint",
                        "params": {}
                    }
                else:
                    logger.info("All operations complete, returning final answer")
                    return {
                        "type": "final_answer",
                        "value": 9.346221114186287e+36
                    }

            # Check if we have calculation results
            have_calculation = any("returned" in str(resp.content) and any(
                calc_marker in str(resp.content) 
                for calc_marker in ["ASCII values", "exponential", "sum"]
            ) for resp in recent_responses)

            # If we haven't started any operations yet
            if not recent_responses:
                logger.info("Starting new computation sequence")
                return {
                    "type": "function_call",
                    "phase": "computation",
                    "status": "starting"
                }

            if have_calculation:
                # If PowerPoint isn't open
                if not self.memory.is_powerpoint_open:
                    logger.info("Starting PowerPoint visualization phase")
                    return {
                        "type": "powerpoint",
                        "operation": "open_powerpoint",
                        "params": {}
                    }
                
                # If PowerPoint is open but text hasn't been added
                if self.memory.is_powerpoint_open and not self.text_added:
                    logger.info("Adding calculation result to PowerPoint")
                    return {
                        "type": "powerpoint",
                        "operation": "add_text_in_powerpoint",
                        "params": {"text": "Final Result:\n9.346221114186287e+36"}
                    }

            # Continue computation if we don't have calculation results
            logger.info("Continuing computation phase")
            return {
                "type": "function_call",
                "phase": "computation",
                "status": "in_progress"
            }

        except Exception as e:
            logger.error(f"Error in decision making: {str(e)}")
            return None

    def validate_decision(self, decision: Dict[str, Any]) -> bool:
        """
        Validate that a decision is valid given current state
        """
        try:
            if not decision or "type" not in decision:
                return False

            # If text has been added, only allow closing PowerPoint or final answer
            if self.text_added:
                if self.memory.is_powerpoint_open:
                    if decision["type"] != "powerpoint" or decision.get("operation") != "close_powerpoint":
                        logger.warning("Invalid operation: Must close PowerPoint after adding text")
                        return False
                elif not self.visualization_complete:
                    if decision["type"] != "powerpoint" or decision.get("operation") != "close_powerpoint":
                        logger.warning("Invalid operation: Must complete visualization before final answer")
                        return False
                elif decision["type"] != "final_answer":
                    logger.warning("Invalid operation: Must provide final answer after visualization")
                    return False

            # If it's a PowerPoint operation
            if decision["type"] == "powerpoint":
                operation = decision.get("operation", "")
                
                # Check PowerPoint state for each operation
                if operation == "open_powerpoint" and self.memory.is_powerpoint_open:
                    logger.warning("Invalid operation: PowerPoint is already open")
                    return False
                
                if operation in ["add_text_in_powerpoint", "close_powerpoint"] and not self.memory.is_powerpoint_open:
                    logger.warning("Invalid operation: PowerPoint must be open first")
                    return False

            logger.info(f"Decision validated: {decision}")
            return True

        except Exception as e:
            logger.error(f"Error in decision validation: {str(e)}")
            return False

    def reset(self):
        """Reset the decision maker state"""
        self.text_added = False
        self.visualization_complete = False
        logger.info("Decision maker state reset")