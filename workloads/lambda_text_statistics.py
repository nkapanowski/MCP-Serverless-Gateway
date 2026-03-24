"""
AWS Lambda – MCP Tool: text_statistics
High-workload tool: comprehensive text analytics over an arbitrary body of text.

Metrics returned
  - char_count, char_count_no_spaces
  - word_count, unique_word_count
  - sentence_count, paragraph_count
  - avg_word_length, avg_sentence_length_words
  - lexical_diversity  (unique / total words)
  - estimated_reading_time_seconds  (at 200 wpm)
  - most_common_words  (top-10 with frequencies)
  - longest_word

Deploy as: Lambda function connected to route POST /textStatistics
Runtime: Python 3.14
"""

import json
import re
import time
import uuid
from collections import Counter

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
STOP_WORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "is","it","its","this","that","these","those","was","are","were","be",
    "been","being","have","has","had","do","does","did","will","would","shall",
    "should","may","might","must","can","could","not","as","by","from","up",
    "about","into","through","during","before","after","above","below","i",
    "he","she","we","they","you","me","him","her","us","them","my","your",
    "his","our","their","what","which","who","whom","how","when","where","why",
    "so","if","then","than","because","while","although","though","however",
}

def _analyse(text: str, top_n: int) -> dict:
    char_count          = len(text)
    char_count_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))

    # Words: strip punctuation, lowercase
    raw_words = re.findall(r"\b[a-zA-Z']+\b", text)
    words     = [w.lower() for w in raw_words]
    word_count        = len(words)
    unique_word_count = len(set(words))

    # Sentences: split on . ! ?
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_count = len(sentences)

    # Paragraphs: blank-line separated
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paragraph_count = max(len(paragraphs), 1)

    avg_word_length = (
        round(sum(len(w) for w in words) / word_count, 2) if word_count else 0.0
    )
    avg_sentence_length = (
        round(word_count / sentence_count, 2) if sentence_count else 0.0
    )
    lexical_diversity = (
        round(unique_word_count / word_count, 4) if word_count else 0.0
    )
    reading_time_sec = round((word_count / 200) * 60, 1)  # 200 wpm average

    # Most common – skip stop-words for meaningful insight
    meaningful = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    counter    = Counter(meaningful)
    most_common = [
        {"word": w, "count": c} for w, c in counter.most_common(top_n)
    ]

    longest_word = max(words, key=len) if words else ""

    return {
        "char_count":                    char_count,
        "char_count_no_spaces":          char_count_no_spaces,
        "word_count":                    word_count,
        "unique_word_count":             unique_word_count,
        "sentence_count":                sentence_count,
        "paragraph_count":               paragraph_count,
        "avg_word_length":               avg_word_length,
        "avg_sentence_length_words":     avg_sentence_length,
        "lexical_diversity":             lexical_diversity,
        "estimated_reading_time_seconds": reading_time_sec,
        "most_common_words":             most_common,
        "longest_word":                  longest_word,
    }


TOOLS = [
    {
        "name": "text_statistics",
        "description": (
            "Perform comprehensive statistical analysis on a body of text. "
            "Returns character counts, word counts, sentence/paragraph counts, "
            "lexical diversity, estimated reading time, and top frequent words."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The body of text to analyse",
                },
                "top_n": {
                    "type": "integer",
                    "description": "How many most-common words to return (default 10, max 50)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
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


def _call_text_statistics(args: dict, rid: str) -> dict:
    start = _now_ms()
    text  = args.get("text")
    top_n = args.get("top_n", 10)

    if not text or not text.strip():
        return _error(rid, "INVALID_INPUT", "'text' cannot be empty", start)
    if not isinstance(top_n, int) or isinstance(top_n, bool):
        top_n = 10
    top_n = max(1, min(top_n, 50))

    stats = _analyse(text, top_n)
    return _success(rid, {"result": stats}, start)


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
            "serverInfo": {"name": "text_statistics_lambda", "version": "1.0.0"},
        })

    if method == "tools/list":
        return _jsonrpc_response(rpc_id, {"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments  = params.get("arguments", {})
        rid = arguments.get("request_id") or str(uuid.uuid4())

        if tool_name != "text_statistics":
            return _jsonrpc_error(rpc_id, -32601, f"Unknown tool: {tool_name}")

        tool_result = _call_text_statistics(arguments, rid)
        return _jsonrpc_response(rpc_id, {
            "content": [{"type": "text", "text": json.dumps(tool_result)}]
        })

    return _jsonrpc_error(rpc_id, -32601, f"Method not found: {method}")
