import logging
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

logger = logging.getLogger('ai_agent.memory')

class MemoryState(BaseModel):
    iteration: int = 0
    iteration_response: List[str] = []
    powerpoint_opened: bool = False
    last_response: Optional[Dict[str, Any]] = None

def reset_state() -> MemoryState:
    """
    Reset all memory state variables to initial values
    """
    logger.info('Resetting memory state')
    return MemoryState()

def update_state(
    current_state: MemoryState,
    iteration_response: List[str],
    powerpoint_opened: bool,
    last_response: Dict[str, Any]
) -> MemoryState:
    """
    Update memory state with new values
    """
    logger.debug('Updating memory state')
    return MemoryState(
        iteration=current_state.iteration + 1,
        iteration_response=iteration_response,
        powerpoint_opened=powerpoint_opened,
        last_response=last_response
    )