from typing import List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from logger_config import setup_logger

# Setup logger
logger = setup_logger('memory', 'memory.log')

@dataclass
class MemoryItem:
    """Represents a single memory item"""
    timestamp: datetime
    type: str  # 'llm_response', 'tool_result', 'iteration_response'
    content: Any
    metadata: dict = None

class Memory:
    """Global memory management class"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Memory, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the memory storage"""
        self.memories: List[MemoryItem] = []
        self.last_response: Optional[Any] = None
        self.iteration: int = 0
        self.iteration_responses: List[str] = []
        self.powerpoint_opened: bool = False
        logger.info("Memory system initialized")

    def add_memory(self, type: str, content: Any, metadata: dict = None):
        """Add a new memory item"""
        memory_item = MemoryItem(
            timestamp=datetime.now(),
            type=type,
            content=content,
            metadata=metadata or {}
        )
        self.memories.append(memory_item)
        logger.debug(f"Added memory: {type} - {content}")

        # Update relevant state based on memory type
        if type == 'llm_response':
            self.last_response = content
        elif type == 'iteration_response':
            self.iteration_responses.append(content)

    def get_recent_memories(self, limit: int = None, type: str = None) -> List[MemoryItem]:
        """Get recent memories, optionally filtered by type"""
        filtered = self.memories
        if type:
            filtered = [m for m in filtered if m.type == type]
        return filtered[-limit:] if limit else filtered

    def get_context_for_prompt(self) -> str:
        """Generate context string from recent memories for prompt construction"""
        if not self.iteration_responses:
            return ""
        
        context = "\n\n".join(self.iteration_responses)
        if self.last_response:
            context += "\nWhat should I do next?"
        return context

    def reset(self):
        """Reset the memory state"""
        self._initialize()
        logger.info("Memory state reset")

    @property
    def current_iteration(self) -> int:
        """Get current iteration number"""
        return self.iteration
    
    def increment_iteration(self):
        """Increment the iteration counter"""
        self.iteration += 1
        logger.debug(f"Iteration incremented to {self.iteration}")
    
    @property
    def is_powerpoint_open(self) -> bool:
        """Check if PowerPoint is currently open"""
        return self.powerpoint_opened
    
    def set_powerpoint_state(self, is_open: bool):
        """Set PowerPoint open/closed state"""
        self.powerpoint_opened = is_open
        logger.debug(f"PowerPoint state set to: {is_open}")

    def get_last_calculation_result(self) -> Optional[str]:
        """Get the last calculation result from memory"""
        for memory in reversed(self.iteration_responses):
            if "returned" in memory:
                return memory.split("returned")[1].strip()
        return None