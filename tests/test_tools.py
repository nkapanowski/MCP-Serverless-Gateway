"""
Unit tests for MCP Gateway tools.
"""
import pytest
from src.tools import SearchTool, DatabaseTool, FileOpsTool, ToolRegistry
from src.schemas import ToolType


@pytest.mark.asyncio
async def test_search_tool_success():
    """Test successful search tool execution."""
    tool = SearchTool()
    response = await tool.invoke({"query": "test", "limit": 5})
    
    assert response.success is True
    assert response.error is None
    assert response.result["query"] == "test"
    assert response.result["count"] == 5
    assert len(response.result["results"]) == 5
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_search_tool_missing_query():
    """Test search tool with missing query parameter."""
    tool = SearchTool()
    response = await tool.invoke({})
    
    assert response.success is False
    assert "Query parameter is required" in response.error
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_database_tool_query():
    """Test database tool query operation."""
    tool = DatabaseTool()
    response = await tool.invoke({
        "operation": "query",
        "table": "users"
    })
    
    assert response.success is True
    assert response.error is None
    assert response.result["operation"] == "query"
    assert response.result["table"] == "users"
    assert response.result["affected_rows"] == 5
    assert len(response.result["data"]) == 5


@pytest.mark.asyncio
async def test_database_tool_missing_params():
    """Test database tool with missing parameters."""
    tool = DatabaseTool()
    response = await tool.invoke({})
    
    assert response.success is False
    assert "required" in response.error.lower()


@pytest.mark.asyncio
async def test_file_ops_tool_list():
    """Test file operations list command."""
    tool = FileOpsTool()
    response = await tool.invoke({
        "operation": "list",
        "path": "/tmp"
    })
    
    assert response.success is True
    assert response.error is None
    assert response.result["operation"] == "list"
    assert response.result["path"] == "/tmp"
    assert response.result["count"] == 3


@pytest.mark.asyncio
async def test_file_ops_tool_write():
    """Test file operations write command."""
    tool = FileOpsTool()
    response = await tool.invoke({
        "operation": "write",
        "path": "/tmp/test.txt",
        "content": "test content"
    })
    
    assert response.success is True
    assert response.error is None
    assert response.result["bytes_written"] == 12


@pytest.mark.asyncio
async def test_file_ops_tool_write_missing_content():
    """Test file operations write without content."""
    tool = FileOpsTool()
    response = await tool.invoke({
        "operation": "write",
        "path": "/tmp/test.txt"
    })
    
    assert response.success is False
    assert "Content parameter is required" in response.error


def test_tool_registry():
    """Test tool registry initialization."""
    registry = ToolRegistry()
    tools = registry.list_tools()
    
    assert len(tools) == 3
    
    tool_names = [t.name for t in tools]
    assert "search" in tool_names
    assert "database" in tool_names
    assert "file_ops" in tool_names


def test_get_tool():
    """Test getting a tool from registry."""
    registry = ToolRegistry()
    
    search_tool = registry.get_tool("search")
    assert search_tool is not None
    assert search_tool.get_schema().name == "search"
    assert search_tool.get_schema().type == ToolType.SEARCH
    
    invalid_tool = registry.get_tool("nonexistent")
    assert invalid_tool is None


def test_tool_schemas():
    """Test that all tools have valid schemas."""
    registry = ToolRegistry()
    
    for tool_schema in registry.list_tools():
        assert tool_schema.name
        assert tool_schema.type
        assert tool_schema.description
        assert tool_schema.parameters
        assert "type" in tool_schema.parameters
        assert "properties" in tool_schema.parameters
