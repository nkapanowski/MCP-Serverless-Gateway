"""
AWS Lambda – MCP Tool: matrix_multiply
High-workload tool: multiplies two 2-D matrices (lists of lists of numbers).
Follows the JSON-RPC / MCP protocol pattern used by IndividualGateway.

Deploy as: Lambda function connected to route POST /matrixMultiply
Runtime: Python 3.14
"""

import json
import time
import uuid

# Helpers

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

def _multiply(matrix_a: list, matrix_b: list) -> list:
    """Pure Python matrix multiplication (no numpy required in Lambda)."""
    rows_a = len(matrix_a)
    cols_a = len(matrix_a[0])
    cols_b = len(matrix_b[0])

    result = [[0.0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += matrix_a[i][k] * matrix_b[k][j]
    return result

TOOLS = [
    {
        "name": "matrix_multiply",
        "description": (
            "Multiply two 2-D matrices (lists of lists of numbers). "
            "matrix_a must be M×K and matrix_b must be K×N; result is M×N."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "matrix_a": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "First matrix (M rows × K cols)",
                },
                "matrix_b": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "Second matrix (K rows × N cols)",
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional idempotency / tracing ID",
                },
            },
            "required": ["matrix_a", "matrix_b"],
        },
    }
]


def _call_matrix_multiply(args: dict, rid: str) -> dict:
    start = _now_ms()
    matrix_a = args.get("matrix_a")
    matrix_b = args.get("matrix_b")

    # Validate presence
    if matrix_a is None or matrix_b is None:
        return _error(rid, "INVALID_INPUT", "matrix_a and matrix_b are required", start)

    # Validate non-empty
    if not matrix_a or not matrix_a[0]:
        return _error(rid, "INVALID_INPUT", "matrix_a must be a non-empty 2-D list", start)
    if not matrix_b or not matrix_b[0]:
        return _error(rid, "INVALID_INPUT", "matrix_b must be a non-empty 2-D list", start)

    cols_a = len(matrix_a[0])
    rows_b = len(matrix_b)

    # Validate inner dimensions match
    if cols_a != rows_b:
        return _error(
            rid,
            "DIMENSION_MISMATCH",
            f"matrix_a has {cols_a} columns but matrix_b has {rows_b} rows; "
            "inner dimensions must match for multiplication",
            start,
        )

    # Validate all rows have consistent widths
    if any(len(row) != cols_a for row in matrix_a):
        return _error(rid, "INVALID_INPUT", "All rows of matrix_a must have the same length", start)
    cols_b = len(matrix_b[0])
    if any(len(row) != cols_b for row in matrix_b):
        return _error(rid, "INVALID_INPUT", "All rows of matrix_b must have the same length", start)

    product = _multiply(matrix_a, matrix_b)
    return _success(
        rid,
        {
            "result": product,
            "shape": f"{len(product)}x{len(product[0])}",
        },
        start,
    )


def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _jsonrpc_error(None, -32700, "Parse error: invalid JSON")

    rpc_id  = body.get("id")
    method  = body.get("method", "")
    params  = body.get("params", {})

    if method == "initialize":
        return _jsonrpc_response(rpc_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "matrix_multiply_lambda", "version": "1.0.0"},
        })

    if method == "tools/list":
        return _jsonrpc_response(rpc_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        rid = arguments.get("request_id") or str(uuid.uuid4())

        if tool_name != "matrix_multiply":
            return _jsonrpc_error(rpc_id, -32601, f"Unknown tool: {tool_name}")

        tool_result = _call_matrix_multiply(arguments, rid)

        # Wraps inner result as MCP content block
        return _jsonrpc_response(rpc_id, {
            "content": [{"type": "text", "text": json.dumps(tool_result)}]
        })

    return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")
