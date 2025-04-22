# MCP (Mathematical Computation and Presentation) System

A sophisticated mathematical computation system with integrated PowerPoint visualization capabilities. The system leverages AI-driven natural language processing to perform complex mathematical operations and automatically generate visual presentations of the results. Built with modular components, it offers a seamless workflow from mathematical computation to visual representation.

## Components

### MCP Server (mcp-server.py)
- Provides various mathematical functions including:
  - Basic arithmetic operations (add, subtract, multiply, divide)
  - Advanced math functions (power, square root, cube root, factorial, logarithm)
  - Trigonometric functions (sin, cos, tan)
  - Special functions (ASCII conversion, exponential sum, Fibonacci sequence)
- PowerPoint automation capabilities:
  - Create and manage presentations
  - Draw shapes (rectangles)
  - Add and format text
  - Automated presentation handling

### Action Layer (action.py)
- Handles all tool execution and PowerPoint operations
- Manages tool parameter validation and conversion
- Provides clean interface for function calls and PowerPoint manipulation
- Maintains state of PowerPoint operations

### AI Agent (agent.py)
- Provides intelligent natural language interface for mathematical operations
- Takes user input queries through console interface
- Performs step-by-step mathematical reasoning and problem-solving
- Executes complex mathematical computations with detailed explanations
- Automatically generates PowerPoint visualizations of mathematical results
- Maintains a structured workflow from computation to presentation

### Support Components
- Decision Layer (decision.py): Handles action decision making and validation
- Memory Layer (memory.py): Manages state and historical context
- Perception Layer (perception.py): Handles response parsing and validation
- Logger Configuration (logger_config.py): Provides structured logging across components

## Setup and Usage

1. Ensure Python is installed on your system
2. Install required dependencies:
   ```
   pip install mcp python-pptx pywinauto google-cloud-aiplatform python-dotenv
   ```
3. Configure environment variables:
   - Create a .env file with your GEMINI_API_KEY
4. Run the server:
   ```
   python mcp-server.py dev
   ```
5. Run the AI agent:
   ```
   python agent.py
   ```
6. Enter your mathematical query when prompted

## Example Operations

- Complex Mathematical Problem Solving
  - Step-by-step reasoning and computation
  - Advanced mathematical functions and operations
  - Detailed explanation of solution process
- Automated Visualization
  - PowerPoint generation of mathematical results
  - Visual representation of computational steps
  - Professional formatting and layout
- Interactive Mathematical Processing
  - Natural language query interpretation
  - Real-time computation and visualization
  - Dynamic result presentation

## Requirements

- Python 3.x
- PowerPoint installation (for presentation features)
- Required Python packages:
  - mcp
  - python-pptx
  - pywinauto
  - google-cloud-aiplatform
  - python-dotenv
