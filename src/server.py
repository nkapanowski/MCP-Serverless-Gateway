"""
Main MCP Gateway Server.
"""
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .schemas import MCPRequest, MCPResponse, ToolRequest
from .tools import ToolRegistry
from .observability import ObservabilityLogger

# Initialize FastAPI app
app = FastAPI(
    title="MCP Serverless Gateway",
    description="Model Context Protocol gateway for tool-using LLMs",
    version="1.0.0"
)

# Initialize components
tool_registry = ToolRegistry()
logger = ObservabilityLogger()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mcp-gateway"}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "tools_available": len(tool_registry.list_tools()),
        "timestamp": time.time()
    }


@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """
    Main MCP gateway endpoint.
    
    Handles:
    - list_tools: Returns available tools
    - invoke_tool: Invokes a specific tool
    """
    start_time = time.time()
    
    try:
        if request.action == "list_tools":
            tools = tool_registry.list_tools()
            latency_ms = (time.time() - start_time) * 1000
            
            logger.log_request(
                action="list_tools",
                data={"tool_count": len(tools)},
                latency_ms=latency_ms,
                success=True
            )
            
            return MCPResponse(
                success=True,
                data={"tools": [tool.model_dump() for tool in tools]},
                latency_ms=latency_ms
            )
        
        elif request.action == "invoke_tool":
            if not request.data:
                raise HTTPException(status_code=400, detail="Missing tool invocation data")
            
            tool_request = ToolRequest(**request.data)
            tool = tool_registry.get_tool(tool_request.tool_name)
            
            if not tool:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Tool '{tool_request.tool_name}' not found"
                )
            
            # Invoke tool with error handling and timing
            tool_response = await tool.invoke(
                parameters=tool_request.parameters,
                request_id=tool_request.request_id
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            logger.log_request(
                action="invoke_tool",
                data={
                    "tool_name": tool_request.tool_name,
                    "tool_success": tool_response.success
                },
                latency_ms=latency_ms,
                success=True
            )
            
            return MCPResponse(
                success=True,
                data=tool_response.model_dump(),
                latency_ms=latency_ms
            )
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown action: {request.action}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        error_msg = f"{type(e).__name__}: {str(e)}"
        
        logger.log_request(
            action=request.action,
            latency_ms=latency_ms,
            success=False,
            error=error_msg
        )
        
        return MCPResponse(
            success=False,
            error=error_msg,
            latency_ms=latency_ms
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with structured logging."""
    logger.log_request(
        action="http_error",
        data={"status_code": exc.status_code, "detail": exc.detail},
        success=False,
        error=str(exc.detail)
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
