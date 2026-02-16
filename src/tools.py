"""
Tool implementations for MCP gateway.
"""
import time
import json
import os
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from .schemas import ToolSchema, ToolType, ToolResponse
from .observability import get_logger


class BaseTool(ABC):
    """Base class for all tools."""
    
    def __init__(self):
        self.logger = get_logger()
    
    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """Return tool schema."""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool with given parameters."""
        pass
    
    async def invoke(self, parameters: Dict[str, Any], request_id: Optional[str] = None) -> ToolResponse:
        """Invoke the tool and return a response with timing and error handling."""
        start_time = time.time()
        
        try:
            result = await self.execute(parameters)
            latency_ms = (time.time() - start_time) * 1000
            
            self.logger.log_tool_invocation(
                tool_name=self.get_schema().name,
                latency_ms=latency_ms,
                success=True
            )
            
            return ToolResponse(
                tool_name=self.get_schema().name,
                success=True,
                result=result,
                latency_ms=latency_ms,
                request_id=request_id
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            self.logger.log_tool_invocation(
                tool_name=self.get_schema().name,
                latency_ms=latency_ms,
                success=False,
                error=error_msg
            )
            
            return ToolResponse(
                tool_name=self.get_schema().name,
                success=False,
                error=error_msg,
                latency_ms=latency_ms,
                request_id=request_id
            )


class SearchTool(BaseTool):
    """Tool for searching content."""
    
    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="search",
            type=ToolType.SEARCH,
            description="Search for content based on a query",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute search."""
        query = parameters.get("query", "")
        limit = parameters.get("limit", 10)
        
        if not query:
            raise ValueError("Query parameter is required")
        
        # Simulate search operation
        results = [
            {
                "id": i,
                "title": f"Result {i} for '{query}'",
                "score": 1.0 - (i * 0.1)
            }
            for i in range(1, min(limit + 1, 6))
        ]
        
        return {
            "query": query,
            "count": len(results),
            "results": results
        }


class DatabaseTool(BaseTool):
    """Tool for database operations."""
    
    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="database",
            type=ToolType.DATABASE,
            description="Query database for records",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["query", "insert", "update", "delete"],
                        "description": "Database operation"
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "data": {
                        "type": "object",
                        "description": "Operation data"
                    }
                },
                "required": ["operation", "table"]
            }
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute database operation."""
        operation = parameters.get("operation")
        table = parameters.get("table")
        data = parameters.get("data", {})
        
        if not operation or not table:
            raise ValueError("Operation and table parameters are required")
        
        # Simulate database operation
        return {
            "operation": operation,
            "table": table,
            "affected_rows": 1 if operation != "query" else 5,
            "data": data if operation != "query" else [
                {"id": i, "name": f"Record {i}"} for i in range(1, 6)
            ]
        }


class FileOpsTool(BaseTool):
    """Tool for file operations."""
    
    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="file_ops",
            type=ToolType.FILE_OPS,
            description="Perform file operations (read, write, list)",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list", "delete"],
                        "description": "File operation"
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write operation)"
                    }
                },
                "required": ["operation", "path"]
            }
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute file operation."""
        operation = parameters.get("operation")
        path = parameters.get("path")
        content = parameters.get("content")
        
        if not operation or not path:
            raise ValueError("Operation and path parameters are required")
        
        # Simulate file operations (not actual file I/O for safety)
        if operation == "read":
            return {
                "operation": operation,
                "path": path,
                "content": f"Simulated content of {path}",
                "size": 1024
            }
        elif operation == "write":
            if not content:
                raise ValueError("Content parameter is required for write operation")
            return {
                "operation": operation,
                "path": path,
                "bytes_written": len(content)
            }
        elif operation == "list":
            return {
                "operation": operation,
                "path": path,
                "files": [f"file_{i}.txt" for i in range(1, 4)],
                "count": 3
            }
        elif operation == "delete":
            return {
                "operation": operation,
                "path": path,
                "deleted": True
            }
        else:
            raise ValueError(f"Unknown operation: {operation}")


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default tools."""
        self.register_tool(SearchTool())
        self.register_tool(DatabaseTool())
        self.register_tool(FileOpsTool())
    
    def register_tool(self, tool: BaseTool):
        """Register a tool."""
        schema = tool.get_schema()
        self.tools[schema.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> List[ToolSchema]:
        """List all available tools."""
        return [tool.get_schema() for tool in self.tools.values()]
