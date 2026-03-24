"""
AWS Lambda – MCP Tool: prime_factors
High-workload tool: returns the complete prime factorisation of a positive integer.
Trial-division with early sqrt cutoff – intentionally CPU-bound for large n.

Deploy as: Lambda function connected to route POST /primeFactors
Runtime: Python 3.14
"""

import json
import math
import time
import uuid

#Helpers

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

MAX_N = 10_000_000_000  # 10 billion – keeps Lambda within timeout

def _factorize(n: int) -> list[int]:
    """Return sorted list of prime factors (with repetition) for n."""
    factors = []
    # Handle factor 2 separately so the main loop steps by 2
    while n % 2 == 0:
        factors.append(2)
        n //= 2
    # Check odd divisors up to sqrt(n)
    divisor = 3
    while divisor <= math.isqrt(n):
        while n % divisor == 0:
            factors.append(divisor)
            n //= divisor
        divisor += 2
    if n > 1:           # remaining n is a prime factor
        factors.append(n)
    return factors

def _factor_map(factors: list[int]) -> dict[str, int]:
    """Convert factor list to {prime: exponent} mapping."""
    fm: dict[str, int] = {}
    for f in factors:
        key = str(f)
        fm[key] = fm.get(key, 0) + 1
    return fm


TOOLS = [
    {
        "name": "prime_factors",
        "description": (
            "Return the complete prime factorisation of a positive integer n "
            f"(1 ≤ n ≤ {MAX_N:,}). "
            "Result includes the sorted factor list, the exponent map, and "
            "whether n itself is prime."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": f"Positive integer to factorise (max {MAX_N:,})",
                    "minimum": 1,
                    "maximum": MAX_N,
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional idempotency / tracing ID",
                },
            },
            "required": ["n"],
        },
    }
]


def _call_prime_factors(args: dict, rid: str) -> dict:
    start = _now_ms()
    n = args.get("n")

    if n is None:
        return _error(rid, "INVALID_INPUT", "'n' is required", start)
    if not isinstance(n, int) or isinstance(n, bool):
        return _error(rid, "INVALID_INPUT", "'n' must be an integer", start)
    if n < 1:
        return _error(rid, "INVALID_INPUT", "'n' must be >= 1", start)
    if n > MAX_N:
        return _error(rid, "INVALID_INPUT", f"'n' must be <= {MAX_N:,}", start)

    factors = _factorize(n)
    is_prime = (n > 1 and len(factors) == 1 and factors[0] == n)

    return _success(
        rid,
        {
            "n": n,
            "factors": factors,
            "factor_map": _factor_map(factors),
            "is_prime": is_prime,
            "num_distinct_factors": len(set(factors)),
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
            "serverInfo": {"name": "prime_factors_lambda", "version": "1.0.0"},
        })

    if method == "tools/list":
        return _jsonrpc_response(rpc_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments  = params.get("arguments", {})
        rid = arguments.get("request_id") or str(uuid.uuid4())

        if tool_name != "prime_factors":
            return _jsonrpc_error(rpc_id, -32601, f"Unknown tool: {tool_name}")

        tool_result = _call_prime_factors(arguments, rid)
        return _jsonrpc_response(rpc_id, {
            "content": [{"type": "text", "text": json.dumps(tool_result)}]
        })

    return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")
