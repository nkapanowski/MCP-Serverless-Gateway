from mcp.server.fastmcp import FastMCP
import hashlib
import re
import time
import uuid
import uvicorn
import requests
from typing import Any, Dict

mcp = FastMCP("EC2 MCP Server")

def _now_ms() -> int:
    return int(time.time() * 1000)

def _success(request_id: str, result: dict, start: int) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "success",
        "result": result,
        "duration_ms": _now_ms() - start
    }

def _error(request_id: str, code: str, message: str, start: int) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "error",
        "error": {
            "code": code,
            "message": message
        },
        "duration_ms": _now_ms() - start
    }

@mcp.tool()
def add(a: float, b: float, request_id: str | None = None) -> Dict[str, Any]:
    """Add two numbers together."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    return _success(rid, {"result": a + b}, start)

@mcp.tool()
def hash_this(message: str, request_id: str | None = None) -> Dict[str, Any]:
    """SHA-256 hash a message."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    if not message or not message.strip():
        return _error(rid, "INVALID_INPUT", "message cannot be empty", start)
    hashed = hashlib.sha256(message.encode("utf-8")).hexdigest()
    return _success(rid, {"result": hashed}, start)

@mcp.tool()
def timestamp(request_id: str | None = None) -> Dict[str, Any]:
    """Return the current Unix timestamp."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    return _success(rid, {"result": int(time.time())}, start)

@mcp.tool()
def word_dictionary(sentence: str, request_id: str | None = None) -> Dict[str, Any]:
    """Count word occurrences in a sentence."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    if not sentence or not sentence.strip():
        return _error(rid, "INVALID_INPUT", "sentence cannot be empty", start)
    cleaned = re.sub(r"[^\w\s]", "", sentence.lower())
    words = cleaned.split()
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return _success(rid, {"result": counts}, start)

@mcp.tool()
def sorted_word_dictionary(sentence: str, n: int = 5, request_id: str | None = None) -> Dict[str, Any]:
    """Return the top-n most frequent words in a sentence."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    if not sentence or not sentence.strip():
        return _error(rid, "INVALID_INPUT", "sentence cannot be empty", start)
    cleaned = re.sub(r"[^\w\s]", "", sentence.lower())
    words = cleaned.split()
    counts = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]
    return _success(rid, {"result": sorted_words}, start)

@mcp.tool()
def hello(name: str = "Natalie", request_id: str | None = None) -> Dict[str, Any]:
    """Say hello to someone."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    return _success(rid, {"result": f"Hello there {name}!"}, start)

@mcp.tool()
def hello_world(name: str = "Natalie", request_id: str | None = None) -> Dict[str, Any]:
    """Say hello world to someone."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    return _success(rid, {"result": f"Hello World, {name}!"}, start)

@mcp.tool()
def goodbye(name: str = "Natalie", request_id: str | None = None) -> Dict[str, Any]:
    """Say goodbye to someone."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    return _success(rid, {"result": f"Goodbye, {name}!"}, start)

def _call_ec2_backend(payload: dict) -> dict:
    start = _now_ms()
    try:
        tool_name = payload.get("tool", "timestamp")
        parameters = payload.get("parameters", {})
        
        tool_map = {
            "add": lambda p: add(**p),
            "hashThis": lambda p: hash_this(message=p.get("message") or p.get("thing", "")),
            "hash_this": lambda p: hash_this(message=p.get("message") or p.get("thing", "")),
            "timestamp": lambda p: timestamp(),
            "getTimeStampOfService": lambda p: timestamp(),
            "word_dictionary": lambda p: word_dictionary(**p),
            "wordDictionary": lambda p: word_dictionary(**p),
            "sorted_word_dictionary": lambda p: sorted_word_dictionary(**p),
            "sortedWordDictionary": lambda p: sorted_word_dictionary(**p),
            "hello": lambda p: hello(**p),
            "hello_world": lambda p: hello_world(**p),
            "helloWorld": lambda p: hello_world(**p),
            "goodbye": lambda p: goodbye(**p),
        }
        
        if tool_name not in tool_map:
            return {"backend": "ec2", "error": f"Tool '{tool_name}' not found", "duration_ms": _now_ms() - start}
        
        result = tool_map[tool_name](parameters)
        return {"backend": "ec2", "result": result, "duration_ms": _now_ms() - start}
    except Exception as e:
        return {"backend": "ec2", "error": str(e), "duration_ms": _now_ms() - start}

def _call_lambda_backend(payload: dict) -> dict:
    start = _now_ms()
    try:
        rpc_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": payload.get("tool", "echo"),
                "arguments": payload.get("parameters", payload)
            }
        }
        response = requests.post(
            "https://u099e6zzcg.execute-api.us-east-2.amazonaws.com/mcp",
            json=rpc_payload,
            timeout=10,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        response.raise_for_status()
        data = response.json()
        return {"backend": "lambda", "result": data, "duration_ms": _now_ms() - start}
    except Exception as e:
        return {"backend": "lambda", "error": str(e), "duration_ms": _now_ms() - start}

@mcp.tool()
def route_backend(payload: dict, backend: str = "ec2", request_id: str | None = None) -> dict:
    """Route a payload to either the EC2 or Lambda backend."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    if backend == "lambda":
        result = _call_lambda_backend(payload)
    else:
        result = _call_ec2_backend(payload)
    return _success(rid, result, start)

@mcp.tool()
def compare_backends(payload: dict, request_id: str | None = None) -> dict:
    """Call both EC2 and Lambda backends and return which was faster."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    ec2_result = _call_ec2_backend(payload)
    lambda_result = _call_lambda_backend(payload)
    faster = "ec2" if ec2_result["duration_ms"] < lambda_result["duration_ms"] else "lambda"
    return _success(rid, {"ec2": ec2_result, "lambda": lambda_result, "faster": faster}, start)

if __name__ == "__main__":
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")