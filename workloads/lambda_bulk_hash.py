"""
AWS Lambda – MCP Tool: bulk_hash
High-workload tool: hash a list of strings in one shot.

Supports: sha256 (default), sha512, sha1, md5
Returns a list of {input, hash} objects in the same order as the input.

Deploy as: Lambda function connected to route POST /bulkHash
Runtime: Python 3.14
"""

import hashlib
import json
import time
import uuid

# Helpers

SUPPORTED_ALGORITHMS = {"sha256", "sha512", "sha1", "md5"}
MAX_MESSAGES = 500  # cap per invocation to protect Lambda timeout

def _now_ms() -> int:
    return int(time.time() * 1000)

def _success(request_id: str, result: dict, start: int) -> dict:
    return {
        "request_id": request_id,
        "status": "success",
        "result": result,
        "duration_ms": _now_ms() - start,
    }

def _error(request_id: str, code: str, message: str, start: int) -> dict:
    return {
        "request_id": request_id,
        "status": "error",
        "error": {"code": code, "message": message},
        "duration_ms": _now_ms() - start,
    }

def _jsonrpc_response(id_, result_body: dict) -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": id_,
            "result": result_body,
        }),
    }

def _jsonrpc_error(id_, code: int, message: str) -> dict:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "jsonrpc": "2.0",
            "id": id_,
            "error": {"code": code, "message": message},
        }),
    }

# Logic

def _hash_one(message: str, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    h.update(message.encode("utf-8"))
    return h.hexdigest()

def _bulk_hash(messages: list[str], algorithm: str) -> list[dict]:
    return [
        {"input": msg, "hash": _hash_one(msg, algorithm)}
        for msg in messages
    ]


TOOLS = [
    {
        "name": "bulk_hash",
        "description": (
            "Hash a list of strings in a single call using the chosen algorithm. "
            f"Supported algorithms: {', '.join(sorted(SUPPORTED_ALGORITHMS))}. "
            f"Maximum {MAX_MESSAGES} messages per call. "
            "Returns results in the same order as the input."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"List of strings to hash (max {MAX_MESSAGES})",
                },
                "algorithm": {
                    "type": "string",
                    "description": "Hash algorithm to use (default: sha256)",
                    "enum": sorted(SUPPORTED_ALGORITHMS),
                    "default": "sha256",
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional idempotency / tracing ID",
                },
            },
            "required": ["messages"],
        },
    }
]


def _call_bulk_hash(args: dict, rid: str) -> dict:
    start     = _now_ms()
    messages  = args.get("messages")
    algorithm = (args.get("algorithm") or "sha256").lower()

    if not isinstance(messages, list) or messages is None:
        return _error(rid, "INVALID_INPUT", "'messages' must be a list of strings", start)
    if len(messages) == 0:
        return _error(rid, "INVALID_INPUT", "'messages' list cannot be empty", start)
    if len(messages) > MAX_MESSAGES:
        return _error(
            rid, "TOO_MANY_INPUTS",
            f"Maximum {MAX_MESSAGES} messages per call; received {len(messages)}",
            start,
        )
    if algorithm not in SUPPORTED_ALGORITHMS:
        return _error(
            rid, "UNSUPPORTED_ALGORITHM",
            f"Algorithm '{algorithm}' is not supported. "
            f"Choose from: {', '.join(sorted(SUPPORTED_ALGORITHMS))}",
            start,
        )
    # Ensure all items are strings
    if any(not isinstance(m, str) for m in messages):
        return _error(rid, "INVALID_INPUT", "All items in 'messages' must be strings", start)

    hashed = _bulk_hash(messages, algorithm)
    return _success(
        rid,
        {
            "algorithm": algorithm,
            "count": len(hashed),
            "result": hashed,
        },
        start,
    )



def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _jsonrpc_error(None, -32700, "Parse error: invalid JSON")

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "initialize":
        return _jsonrpc_response(rpc_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "bulk_hash_lambda", "version": "1.0.0"},
        })

    if method == "tools/list":
        return _jsonrpc_response(rpc_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments  = params.get("arguments", {})
        rid = arguments.get("request_id") or str(uuid.uuid4())

        if tool_name != "bulk_hash":
            return _jsonrpc_error(rpc_id, -32601, f"Unknown tool: {tool_name}")

        tool_result = _call_bulk_hash(arguments, rid)
        return _jsonrpc_response(rpc_id, {
            "content": [{"type": "text", "text": json.dumps(tool_result)}]
        })

    return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")
