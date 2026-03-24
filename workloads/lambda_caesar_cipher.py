"""
AWS Lambda – MCP Tool: caesar_cipher
High-workload tool: encode or decode arbitrarily long text with a Caesar cipher.

- Operates on A-Z / a-z only; non-alphabetic characters are preserved.
- mode: "encode" (default) shifts letters forward; "decode" shifts backward.
- Brute-force mode: when mode="bruteforce", returns all 25 possible decryptions
  (useful for ciphertext-only attacks on short messages).

Deploy as: Lambda function connected to route POST /caesarCipher
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

def _shift_text(text: str, shift: int) -> str:
    """Apply a Caesar shift (positive = forward, negative = backward)."""
    shift = shift % 26  # normalise to [0, 25]
    result = []
    for ch in text:
        if ch.isupper():
            result.append(chr((ord(ch) - ord('A') + shift) % 26 + ord('A')))
        elif ch.islower():
            result.append(chr((ord(ch) - ord('a') + shift) % 26 + ord('a')))
        else:
            result.append(ch)  # preserve digits, spaces, punctuation
    return "".join(result)

def _bruteforce(text: str) -> list[dict]:
    """Return all 25 non-trivial shift candidates."""
    return [
        {"shift": s, "text": _shift_text(text, s)}
        for s in range(1, 26)
    ]


TOOLS = [
    {
        "name": "caesar_cipher",
        "description": (
            "Encode or decode text using a Caesar cipher. "
            "Letters A-Z / a-z are shifted; all other characters are unchanged. "
            "mode='encode' shifts forward by <shift> positions. "
            "mode='decode' shifts backward by <shift> positions. "
            "mode='bruteforce' ignores <shift> and returns all 25 candidate decryptions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to encode or decode",
                },
                "shift": {
                    "type": "integer",
                    "description": "Number of positions to shift (0-25). Ignored for bruteforce.",
                    "minimum": 0,
                    "maximum": 25,
                    "default": 13,
                },
                "mode": {
                    "type": "string",
                    "description": "Operation mode: 'encode', 'decode', or 'bruteforce'",
                    "enum": ["encode", "decode", "bruteforce"],
                    "default": "encode",
                },
                "request_id": {
                    "type": "string",
                    "description": "Optional idempotency / tracing ID",
                },
            },
            "required": ["text"],
        },
    }
]


def _call_caesar_cipher(args: dict, rid: str) -> dict:
    start = _now_ms()
    text  = args.get("text")
    shift = args.get("shift", 13)
    mode  = (args.get("mode") or "encode").lower()

    if not text:
        return _error(rid, "INVALID_INPUT", "'text' cannot be empty", start)
    if mode not in {"encode", "decode", "bruteforce"}:
        return _error(rid, "INVALID_INPUT",
                      "mode must be 'encode', 'decode', or 'bruteforce'", start)
    if not isinstance(shift, int) or isinstance(shift, bool):
        return _error(rid, "INVALID_INPUT", "'shift' must be an integer", start)
    if not (0 <= shift <= 25):
        return _error(rid, "INVALID_INPUT", "'shift' must be between 0 and 25", start)

    if mode == "bruteforce":
        candidates = _bruteforce(text)
        return _success(
            rid,
            {
                "mode": "bruteforce",
                "original": text,
                "candidates": candidates,
            },
            start,
        )

    actual_shift = shift if mode == "encode" else -shift
    output = _shift_text(text, actual_shift)
    return _success(
        rid,
        {
            "mode": mode,
            "shift": shift,
            "input":  text,
            "result": output,
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
            "serverInfo": {"name": "caesar_cipher_lambda", "version": "1.0.0"},
        })

    if method == "tools/list":
        return _jsonrpc_response(rpc_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments  = params.get("arguments", {})
        rid = arguments.get("request_id") or str(uuid.uuid4())

        if tool_name != "caesar_cipher":
            return _jsonrpc_error(rpc_id, -32601, f"Unknown tool: {tool_name}")

        tool_result = _call_caesar_cipher(arguments, rid)
        return _jsonrpc_response(rpc_id, {
            "content": [{"type": "text", "text": json.dumps(tool_result)}]
        })

    return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")
