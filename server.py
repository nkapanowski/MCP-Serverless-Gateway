from mcp.server.fastmcp import FastMCP
import hashlib
import re
import time
import uuid
import uvicorn
import requests
import json
import urllib.request
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
def _get_fruit_info(fruit: str) -> dict:
    fruit_name = fruit.strip().lower()
    if not fruit_name:
        return {"error": "No fruit specified"}

    url = f"https://www.fruityvice.com/api/fruit/{fruit_name}"

    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read().decode())
            calories = data['nutritions']['calories']
            sugar = data['nutritions']['sugar']

            return {
                "fruit": fruit_name,
                "calories": calories,
                "sugar": sugar,
                "sum_rounded": round(calories + sugar)
            }
    except Exception as e:
        return {"error": str(e)}
def _get_price_internal(pair: str):
    pair = pair.strip().upper()
    if not pair:
        return {"error": "No trading pair specified"}

    url = f"https://www.okx.com/api/v5/market/ticker?instId={pair}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )

        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())

            price_str = data["data"][0]["last"]
            price = float(price_str)

            result = price + 0
            rounded = round(result, 2)

            return {
                "pair": pair,
                "price": price,
                "result": result,
                "rounded": rounded
            }

    except Exception as e:
        return {"error": str(e)}
# minimal city → coordinates mapping
CITY_COORDS = {
    "london": {"lat": 51.5074, "lon": -0.1278},
    "new york": {"lat": 40.7128, "lon": -74.0060},
    "san francisco": {"lat": 37.7749, "lon": -122.4194}
}

def _get_weather_internal(args: dict) -> dict:
    """
    Internal function to fetch weather for a city.
    Converts Celsius → Kelvin and rounds to 2 decimals.
    """
    city = args.get("city", "").strip().lower()
    if not city:
        raise ValueError("No city specified")

    if city not in CITY_COORDS:
        raise ValueError(f"Unsupported city: {city}")

    lat = CITY_COORDS[city]["lat"]
    lon = CITY_COORDS[city]["lon"]

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())

        temp_c = data["current_weather"]["temperature"]
        temp_k = round(temp_c + 273.15, 2)

        return {
            "city": city,
            "temp_c": temp_c,
            "temp_k": temp_k
        }

    except KeyError as e:
        raise ValueError(f"Missing field in API response: {e}")
    except Exception as e:
        raise RuntimeError(str(e))

def _list_departments_internal() -> dict:
    """Fetch first two Met Museum departments and compute sum."""
    url = "https://collectionapi.metmuseum.org/public/collection/v1/departments"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            departments = data["departments"]
            if len(departments) < 2:
                return {"error": "Not enough departments returned"}

            dept_id_1 = departments[0]["departmentId"]
            dept_id_2 = departments[1]["departmentId"]
            total = dept_id_1 + dept_id_2
            rounded = round(total)

            return {
                "dept_id_1": dept_id_1,
                "dept_id_2": dept_id_2,
                "sum": total,
                "rounded": rounded
            }
    except KeyError as e:
        return {"error": f"Missing field in API response: {e}"}
    except Exception as e:
        return {"error": str(e)}
@mcp.tool()
def get_fruit_info(fruit: str, request_id: str | None = None) -> Dict[str, Any]:
    """Get nutrition info for a fruit."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())

    result = _get_fruit_info(fruit)

    if "error" in result:
        return _error(rid, "FRUIT_ERROR", result["error"], start)

    return _success(rid, result, start)
@mcp.tool()
def get_price(pair: str, request_id: str | None = None):
    """Get current price for a trading pair from OKX."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())

    try:
        result = _get_price_internal(pair)
        return _success(rid, {"result": result}, start)
    except Exception as e:
        return _error(rid, "PRICE_ERROR", str(e), start)
@mcp.tool()
def get_weather(city: str, request_id: str | None = None) -> dict:
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        result = _get_weather_internal({"city": city})
        return _success(rid, {"result": result}, start)
    except Exception as e:
        return _error(rid, "WEATHER_ERROR", str(e), start)
@mcp.tool()
def list_departments(request_id: str | None = None) -> dict:
    """Fetch Met Museum departments and return sum of first two department IDs."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        result = _list_departments_internal()
        return _success(rid, {"result": result}, start)
    except Exception as e:
        return _error(rid, "INTERNAL_ERROR", str(e), start)
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
            "get_fruit_info": lambda p: get_fruit_info(**p),
            "get_price": lambda p: get_price(**p),
            "get_weather": lambda p: get_weather(**p),
            "list_departments": lambda p: list_departments(**p)
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
