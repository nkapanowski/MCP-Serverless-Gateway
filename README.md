# MCP Serverless Gateway

A production-ready MCP (Model Context Protocol) gateway for tool-using LLMs, designed to compare and evaluate performance, latency, and reliability trade-offs between AWS Lambda and EC2 deployments.

## Features

- 🔧 **Modular Tool System**: Structured tools for search, database, and file operations
- 📊 **Observability**: Built-in timing, logging, and failure tracking
- 🔒 **Error Handling**: Explicit error handling with detailed error messages
- 📈 **Performance Comparison**: Built-in tools to compare Lambda vs EC2 deployments
- 🚀 **Deployment Ready**: Includes CloudFormation templates and deployment scripts
- 📝 **JSON Schemas**: Structured Pydantic models for all requests and responses

## Architecture

### Core Components

1. **MCP Server** (`src/server.py`): FastAPI-based server implementing the MCP protocol
2. **Tool Registry** (`src/tools.py`): Pluggable tool system with built-in tools
3. **Schemas** (`src/schemas.py`): Pydantic models for type-safe operations
4. **Observability** (`src/observability.py`): Structured logging and timing utilities

### Available Tools

- **Search Tool**: Full-text search functionality
- **Database Tool**: Database query and manipulation operations
- **File Operations Tool**: File read, write, list, and delete operations

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server locally
python deployments/ec2/server.py

# Test the server
python test_client.py http://localhost:8000
```

### AWS Lambda Deployment

```bash
# Build and deploy to Lambda
cd deployments/lambda
chmod +x deploy.sh
./deploy.sh

# Or use SAM CLI
sam deploy --template-file template.yaml --guided
```

### EC2 Deployment

```bash
# Deploy using CloudFormation
aws cloudformation create-stack \
  --stack-name mcp-gateway-ec2 \
  --template-body file://deployments/ec2/cloudformation.yaml \
  --parameters ParameterKey=KeyName,ParameterValue=your-key-name

# Or manual setup on existing EC2 instance
ssh your-ec2-instance
git clone <repository-url>
cd deployments/ec2
chmod +x setup.sh
./setup.sh
```

## Performance Comparison

Compare Lambda and EC2 deployments:

```bash
python compare_deployments.py \
  --lambda-url https://your-lambda-url.amazonaws.com/Prod \
  --ec2-url http://your-ec2-ip:8000 \
  --requests 100
```

This generates a detailed comparison report including:
- Mean, median, P95, and P99 latencies
- Success rates and reliability metrics
- Latency distributions
- Operational trade-offs

## API Reference

### List Tools

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "list_tools"}'
```

### Invoke Tool

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "invoke_tool",
    "data": {
      "tool_name": "search",
      "parameters": {
        "query": "test query",
        "limit": 10
      }
    }
  }'
```

## Observability

All operations are logged with:
- Execution latency (milliseconds)
- Success/failure status
- Error details
- Structured JSON format

Example log entry:
```json
{
  "timestamp": 1234567890.123,
  "level": "INFO",
  "action": "invoke_tool",
  "tool_name": "search",
  "latency_ms": 45.67,
  "success": true
}
```

## Deployment Comparison: Lambda vs EC2

### AWS Lambda
**Advantages:**
- No server management
- Automatic scaling
- Pay-per-request pricing
- Built-in high availability

**Trade-offs:**
- Cold start latency (first request)
- Execution time limits (30s max)
- Memory constraints
- Potential throttling

### EC2
**Advantages:**
- Consistent low latency
- No cold starts
- Full control over resources
- Predictable performance

**Trade-offs:**
- Requires server management
- Manual scaling setup
- Fixed costs regardless of usage
- Need to handle availability

## Error Handling

All errors are handled explicitly and return structured responses:

```json
{
  "success": false,
  "error": "ValueError: Query parameter is required",
  "latency_ms": 2.34
}
```

## Development

### Project Structure

```
MCP-Serverless-Gateway/
├── src/
│   ├── __init__.py
│   ├── server.py          # Main FastAPI server
│   ├── schemas.py         # Pydantic models
│   ├── tools.py           # Tool implementations
│   └── observability.py   # Logging utilities
├── deployments/
│   ├── lambda/
│   │   ├── handler.py     # Lambda handler
│   │   ├── template.yaml  # SAM template
│   │   └── deploy.sh      # Deployment script
│   └── ec2/
│       ├── server.py      # EC2 server runner
│       ├── setup.sh       # Setup script
│       └── cloudformation.yaml
├── test_client.py         # Test client
├── compare_deployments.py # Comparison tool
├── requirements.txt       # Dependencies
└── README.md
```

### Adding New Tools

1. Create a new tool class inheriting from `BaseTool`
2. Implement `get_schema()` and `execute()` methods
3. Register the tool in `ToolRegistry`

Example:

```python
class CustomTool(BaseTool):
    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="custom_tool",
            type=ToolType.SEARCH,
            description="Custom tool description",
            parameters={...}
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        # Implementation
        return {"result": "data"}
```

## License

MIT
