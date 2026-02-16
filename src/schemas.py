"""
Core MCP Protocol schemas and models.
"""
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field


class ToolType(str, Enum):
    """Available tool types."""
    SEARCH = "search"
    DATABASE = "database"
    FILE_OPS = "file_ops"


class ToolSchema(BaseModel):
    """Tool definition schema."""
    name: str = Field(..., description="Tool name")
    type: ToolType = Field(..., description="Tool type")
    description: str = Field(..., description="Tool description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")


class ToolRequest(BaseModel):
    """Tool invocation request."""
    tool_name: str = Field(..., description="Name of the tool to invoke")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class ToolResponse(BaseModel):
    """Tool invocation response."""
    tool_name: str = Field(..., description="Name of the tool invoked")
    success: bool = Field(..., description="Whether the invocation succeeded")
    result: Optional[Any] = Field(None, description="Tool execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    latency_ms: float = Field(..., description="Execution latency in milliseconds")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class MCPRequest(BaseModel):
    """MCP gateway request."""
    action: str = Field(..., description="Action to perform: list_tools, invoke_tool")
    data: Optional[Dict[str, Any]] = Field(None, description="Action-specific data")


class MCPResponse(BaseModel):
    """MCP gateway response."""
    success: bool = Field(..., description="Whether the request succeeded")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if failed")
    latency_ms: float = Field(..., description="Request latency in milliseconds")
