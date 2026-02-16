"""
Integration tests for MCP Gateway server.
"""
import pytest
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_endpoint():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["tools_available"] == 3
    assert "timestamp" in data


def test_list_tools():
    """Test listing tools."""
    response = client.post("/mcp", json={"action": "list_tools"})
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "tools" in data["data"]
    assert len(data["data"]["tools"]) == 3
    assert data["latency_ms"] > 0


def test_invoke_search_tool():
    """Test invoking search tool."""
    response = client.post("/mcp", json={
        "action": "invoke_tool",
        "data": {
            "tool_name": "search",
            "parameters": {"query": "test", "limit": 3}
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    tool_response = data["data"]
    assert tool_response["tool_name"] == "search"
    assert tool_response["success"] is True
    assert tool_response["result"]["query"] == "test"


def test_invoke_database_tool():
    """Test invoking database tool."""
    response = client.post("/mcp", json={
        "action": "invoke_tool",
        "data": {
            "tool_name": "database",
            "parameters": {
                "operation": "query",
                "table": "users"
            }
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    tool_response = data["data"]
    assert tool_response["tool_name"] == "database"
    assert tool_response["success"] is True


def test_invoke_file_ops_tool():
    """Test invoking file_ops tool."""
    response = client.post("/mcp", json={
        "action": "invoke_tool",
        "data": {
            "tool_name": "file_ops",
            "parameters": {
                "operation": "list",
                "path": "/tmp"
            }
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    tool_response = data["data"]
    assert tool_response["tool_name"] == "file_ops"
    assert tool_response["success"] is True


def test_invoke_nonexistent_tool():
    """Test invoking a non-existent tool."""
    response = client.post("/mcp", json={
        "action": "invoke_tool",
        "data": {
            "tool_name": "nonexistent",
            "parameters": {}
        }
    })
    
    assert response.status_code == 404


def test_invalid_action():
    """Test invalid action."""
    response = client.post("/mcp", json={
        "action": "invalid_action"
    })
    
    assert response.status_code == 400


def test_missing_tool_data():
    """Test invoke_tool without data."""
    response = client.post("/mcp", json={
        "action": "invoke_tool"
    })
    
    assert response.status_code == 400


def test_tool_error_handling():
    """Test tool error handling."""
    response = client.post("/mcp", json={
        "action": "invoke_tool",
        "data": {
            "tool_name": "search",
            "parameters": {}  # Missing required 'query' parameter
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    
    tool_response = data["data"]
    assert tool_response["success"] is False
    assert "Query parameter is required" in tool_response["error"]
