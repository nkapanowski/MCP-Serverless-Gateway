# server.py
# MCP Serverless Gateway
# Exposes "tools" through mcp server that can be called by LLM agents via MCP protocol.

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

# FastMCP = high level wrapper for MCP protocol
from mcp.server.fastmcp import FastMCP  

# Creates MCP server instance
# json_response=True lets the tools return python dicts that are automatically converted to JSON responses
mcp = FastMCP("MCP Serverless Gateway", json_response=True)


# Timing and standardized response helpers
# Measures tool execution time and formats consistent
# success and error responses according to schemas.md

def _now_ms() -> int:
    return int(time.time() * 1000)


def _success(request_id: str, data: Dict[str, Any], start_ms: int) -> Dict[str, Any]:
    return {
        "status": "success",
        "request_id": request_id,
        "data": data,
        "execution_time_ms": _now_ms() - start_ms,
    }


def _error(request_id: str, code: str, message: str, start_ms: int) -> Dict[str, Any]:
    return {
        "status": "error",
        "request_id": request_id,
        "error": {"code": code, "message": message},
        "execution_time_ms": _now_ms() - start_ms,
    }


# MCP Tools

@mcp.tool() # Registers function as MCP tool that can be called by LLM agents via MCP protocol
def search(query: str, request_id: str | None = None) -> Dict[str, Any]:
    """ 
    Stub Search Tool, validates input and returns placeholder result for now
    """
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())

    
    if not query or not query.strip():
        return _error(rid, "INVALID_INPUT", "query cannot be empty", start)

    # TODO for Phase 2+: replace stub with real search implementation
    results = [f"Stub result for: {query.strip()}"]
    return _success(rid, {"results": results}, start)


@mcp.tool()
def file_read(filename: str, request_id: str | None = None) -> Dict[str, Any]:
    """
    File read tool that reads local file with basic checks
    """
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())

    if not filename or not filename.strip():
        return _error(rid, "INVALID_INPUT", "filename cannot be empty", start)

    try:
        # Basic security to prevent path separators
        if "/" in filename or "\\" in filename:
            return _error(rid, "INVALID_INPUT", "filename must not include path separators", start)

        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()

        return _success(rid, {"content": content}, start)

    except FileNotFoundError:
        return _error(rid, "EXECUTION_ERROR", f"file not found: {filename}", start)
    except Exception as e:
        return _error(rid, "INTERNAL_ERROR", f"unexpected error: {e}", start)


@mcp.tool()
def db_query(query: str, request_id: str | None = None) -> Dict[str, Any]:
    """
    Stub Database Tool, simulates querying structured data
    """
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())

    # Validation check
    if not query or not query.strip():
        return _error(rid, "INVALID_INPUT", "SQL query cannot be empty", start)

    # TODO for Phase 2+: replace with real SQLite or Postgres connection
    # For now, its returns hard-coded stub
    mock_data = [
        {"id": 1, "name": "User_Alpha", "status": "active"},
        {"id": 2, "name": "User_Beta", "status": "pending"}
    ]
    
    return _success(rid, {"results": mock_data, "query_echo": query.strip()}, start)

# Server startup
# Starts MCP server using Streamable HTTP transport
if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("MCP Serverless Gateway stopped")


# === EC2/Lambda Comparison Framework === STUB REPLACED WITH REAL EC2 CALL, LAMBDA STILL STUBBED
import requests

def _call_ec2_backend(payload: dict) -> dict:
    start = _now_ms()
    try:
        response = requests.post(
            "http://3.139.91.10:5000/api",
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        return {"backend": "ec2", "result": data, "duration_ms": _now_ms() - start}
    except Exception as e:
        return {"backend": "ec2", "error": str(e), "duration_ms": _now_ms() - start}

def _call_lambda_backend(payload: dict) -> dict:
    start = _now_ms()
    # TODO: Replace with real Lambda call
    time.sleep(0.05)
    return {"backend": "lambda", "result": "stub", "duration_ms": _now_ms() - start}

@mcp.tool()
def route_backend(payload: dict, backend: str = "ec2", request_id: str | None = None) -> dict:

    # Routes payload to specified backend (ec2 or lambda).

    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    if backend == "lambda":
        result = _call_lambda_backend(payload)
    else:
        result = _call_ec2_backend(payload)
    return _success(rid, result, start)

@mcp.tool()
def compare_backends(payload: dict, request_id: str | None = None) -> dict:
    
   # Calls both EC2 and Lambda backends, returns both results and which was faster.
    
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    ec2_result = _call_ec2_backend(payload)
    lambda_result = _call_lambda_backend(payload)
    faster = "ec2" if ec2_result["duration_ms"] < lambda_result["duration_ms"] else "lambda"
    return _success(rid, {"ec2": ec2_result, "lambda": lambda_result, "faster": faster}, start)