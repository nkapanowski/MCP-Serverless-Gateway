# MCP Gateway - Quick Reference

## Installation

```bash
git clone <repository-url>
cd MCP-Serverless-Gateway
pip install -r requirements.txt
```

## Local Testing

```bash
# Start server
python deployments/ec2/server.py

# In another terminal, run tests
python test_client.py http://localhost:8000

# Or run unit tests
pytest tests/ -v
```

## API Examples

### List Available Tools
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"action": "list_tools"}'
```

### Search Tool
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "invoke_tool",
    "data": {
      "tool_name": "search",
      "parameters": {
        "query": "machine learning",
        "limit": 5
      }
    }
  }'
```

### Database Tool
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "invoke_tool",
    "data": {
      "tool_name": "database",
      "parameters": {
        "operation": "query",
        "table": "users"
      }
    }
  }'
```

### File Operations Tool
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "action": "invoke_tool",
    "data": {
      "tool_name": "file_ops",
      "parameters": {
        "operation": "list",
        "path": "/tmp"
      }
    }
  }'
```

## Deployment

### Lambda
```bash
cd deployments/lambda
./deploy.sh
sam deploy --guided
```

### EC2
```bash
# Using CloudFormation
aws cloudformation create-stack \
  --stack-name mcp-gateway \
  --template-body file://deployments/ec2/cloudformation.yaml \
  --parameters \
    ParameterKey=KeyName,ParameterValue=your-key \
    ParameterKey=VpcId,ParameterValue=vpc-xxx \
    ParameterKey=SubnetId,ParameterValue=subnet-xxx

# Or manual setup
ssh ec2-user@your-instance
cd deployments/ec2
./setup.sh
```

## Comparison Testing

```bash
python compare_deployments.py \
  --lambda-url https://xxx.execute-api.us-east-1.amazonaws.com/Prod \
  --ec2-url http://ec2-instance:8000 \
  --requests 100
```

## Response Format

All responses follow this structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "latency_ms": 12.34
}
```

Tool invocation responses:

```json
{
  "tool_name": "search",
  "success": true,
  "result": { ... },
  "error": null,
  "latency_ms": 5.67,
  "request_id": "optional-id"
}
```

## Common Issues

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000
# Kill the process
kill -9 <PID>
```

### Lambda Package Too Large
- Ensure `__pycache__` and `.pyc` files are excluded
- Check that development dependencies aren't included
- Use Lambda layers for large dependencies

### EC2 Connection Refused
- Check security group allows port 8000
- Verify service is running: `sudo systemctl status mcp-gateway`
- Check logs: `sudo journalctl -u mcp-gateway -f`

## Monitoring

### Check Health
```bash
curl http://localhost:8000/health
```

### View Logs (EC2)
```bash
sudo journalctl -u mcp-gateway -f
```

### View Logs (Lambda)
```bash
aws logs tail /aws/lambda/mcp-gateway-lambda --follow
```

## Environment Variables

- `PORT`: Server port (default: 8000)
- `LOG_LEVEL`: Logging level (default: INFO)

## Adding Custom Tools

1. Create tool class in `src/tools.py`:
```python
class MyTool(BaseTool):
    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="my_tool",
            type=ToolType.SEARCH,
            description="My custom tool",
            parameters={...}
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        # Implementation
        return {"result": "data"}
```

2. Register in `ToolRegistry._register_default_tools()`:
```python
self.register_tool(MyTool())
```

## Support

- Documentation: See README.md and DEPLOYMENT_COMPARISON.md
- Issues: GitHub Issues
- Tests: Run `pytest tests/ -v`
