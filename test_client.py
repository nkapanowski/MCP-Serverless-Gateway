"""
Simple test client for MCP Gateway.
"""
import asyncio
import json
from typing import Dict, Any
import aiohttp


class MCPClient:
    """Client for interacting with MCP Gateway."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/mcp",
                json={"action": "list_tools"}
            ) as response:
                return await response.json()
    
    async def invoke_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        request_id: str = None
    ) -> Dict[str, Any]:
        """Invoke a tool."""
        payload = {
            "action": "invoke_tool",
            "data": {
                "tool_name": tool_name,
                "parameters": parameters
            }
        }
        
        if request_id:
            payload["data"]["request_id"] = request_id
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/mcp",
                json=payload
            ) as response:
                return await response.json()


async def main():
    """Example usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_client.py <base_url>")
        print("Example: python test_client.py http://localhost:8000")
        sys.exit(1)
    
    base_url = sys.argv[1]
    client = MCPClient(base_url)
    
    print(f"Testing MCP Gateway at {base_url}\n")
    
    # Test 1: List tools
    print("1. Listing available tools...")
    result = await client.list_tools()
    print(json.dumps(result, indent=2))
    print()
    
    # Test 2: Search tool
    print("2. Testing search tool...")
    result = await client.invoke_tool(
        "search",
        {"query": "test query", "limit": 3}
    )
    print(json.dumps(result, indent=2))
    print()
    
    # Test 3: Database tool
    print("3. Testing database tool...")
    result = await client.invoke_tool(
        "database",
        {
            "operation": "query",
            "table": "users"
        }
    )
    print(json.dumps(result, indent=2))
    print()
    
    # Test 4: File operations tool
    print("4. Testing file_ops tool...")
    result = await client.invoke_tool(
        "file_ops",
        {
            "operation": "list",
            "path": "/tmp"
        }
    )
    print(json.dumps(result, indent=2))
    print()
    
    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
