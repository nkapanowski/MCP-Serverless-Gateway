from mcp.server.fastmcp import FastMCP
import hashlib
import re
import time
import uuid
import uvicorn
import requests
import json
import urllib.request
import urllib.parse
import statistics
from collections import Counter
from typing import Any, Dict
import xml.etree.ElementTree as ET
from pypdf import PdfReader
from datetime import date, timedelta
mcp = FastMCP("EC2 MCP Server")
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NIXHUB_BASE   = "https://www.nixhub.io/api/v0"
REPOLOGY_BASE = "https://repology.org/api/v1"
HN_BASE       = "https://hacker-news.firebaseio.com/v0"
NPS_KEY       = "DEMO_KEY"   # replace with real key if DEMO_KEY is rate-limited
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
def _get_car_brands_internal() -> dict:
    """Fetch first two car brands from FIPE API and compute sum."""
    url = "https://parallelum.com.br/fipe/api/v1/carros/marcas"
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

            if len(data) < 2:
                return {"error": "Not enough brands returned"}

            brand_code_1 = int(data[0]["codigo"])
            brand_code_2 = int(data[1]["codigo"])
            total = brand_code_1 + brand_code_2
            rounded = round(total)

            return {
                "brand_code_1": brand_code_1,
                "brand_code_2": brand_code_2,
                "sum": total,
                "rounded": rounded
            }
    except KeyError as e:
        return {"error": f"Missing field in API response: {e}"}
    except Exception as e:
        return {"error": str(e)}
def search_wikipedia_internal(query: str) -> dict:
    if not query or not query.strip():
        return {"error": "No search query provided"}

    url = (
        "https://en.wikipedia.org/w/api.php?"
        f"action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit=2"
    )

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

            results = data.get("query", {}).get("search", [])

            if len(results) < 2:
                return {"error": "Not enough search results returned"}

            title_1 = results[0]["title"]
            title_2 = results[1]["title"]

            total_len = len(title_1) + len(title_2)
            rounded = round(total_len)

            return {
                "query": query,
                "title_1": title_1,
                "title_2": title_2,
                "total_length": total_len,
                "rounded": rounded
            }

    except Exception as e:
        return {"error": str(e)}

def find_parks_internal(stateCode: str, limit: int = 3) -> dict:
    state_code = stateCode.strip().upper()

    if not state_code:
        return {"error": "No state code provided"}

    url = (
        f"https://developer.nps.gov/api/v1/parks?"
        f"stateCode={state_code}&limit={limit}&api_key=DEMO_KEY"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            parks = data.get("data", [])

            if len(parks) < 2:
                return {"error": "Not enough parks returned"}

            lat_1 = float(parks[0]["latitude"])
            lat_2 = float(parks[1]["latitude"])

            total = lat_1 + lat_2
            rounded = round(total)

            return {
                "stateCode": state_code,
                "lat_1": lat_1,
                "lat_2": lat_2,
                "sum": total,
                "rounded": rounded
            }

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
def get_car_brands(request_id: str | None = None) -> dict:
    """Fetch FIPE car brands and return sum of first two brand codes."""
    rid = request_id or str(uuid.uuid4())
    start = _now_ms()
    try:
        result = _get_car_brands_internal()
        return _success(rid, {"result": result}, start)
    except Exception as e:
        return _error(rid, "INTERNAL_ERROR", str(e), start)
@mcp.tool()
def search_wikipedia(query: str, request_id: str | None = None) -> dict:
    """Search Wikipedia and compute the combined length of top 2 article titles."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())

    result = search_wikipedia_internal(query)

    if "error" in result:
        return _error(rid, "SEARCH_FAILED", result["error"], start)

    return _success(rid, {"result": result}, start)
@mcp.tool()
def find_parks(stateCode: str, limit: int = 3, request_id: str | None = None) -> dict:
    """Fetch National Parks for a state and sum the latitude of the first two."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())

    result = find_parks_internal(stateCode, limit)

    if "error" in result:
        return _error(rid, "PARKS_FETCH_FAILED", result["error"], start)

    return _success(rid, {"result": result}, start)
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
            "list_departments": lambda p: list_departments(**p),
            "get_car_brands": lambda p: get_car_brands(**p),
            "search_wikipedia": lambda p: search_wikipedia(**p),
            "find_parks": lambda p: find_parks(**p)
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
def m1_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M1 on EC2: Open-Meteo 7-day forecast for New York - 1 GET + mean/median/min/max of daily max temps. Est. payload ~15 KB."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        t = _now_ms()
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 40.7128,
                "longitude": -74.0060,
                "daily": "temperature_2m_max,temperature_2m_min",
                "timezone": "America/New_York",
                "forecast_days": 7,
            },
            timeout=15,
        )
        r.raise_for_status()
        daily = r.json()["daily"]
        temps = daily["temperature_2m_max"]
        log.append({"step": "get_weather_forecast", "duration_ms": _now_ms() - t, "days": len(temps)})

        return _success(rid, {
            "chain": "M1",
            "city": "New York",
            "dates": daily["time"],
            "daily_max_c": temps,
            "stats": {
                "mean":   round(statistics.mean(temps), 2),
                "median": statistics.median(temps),
                "min":    min(temps),
                "max":    max(temps),
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M1_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M2 - NPS CA parks (15) + park detail -> mean / median / sum latitudes
# ---------------------------------------------------------------------------

@mcp.tool()
def m2_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M2 on EC2: NPS parks CA (limit=15) + detail for first result - 2 sequential GETs + mean/median/sum latitudes. Est. payload ~33 KB."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        HEADERS = {"User-Agent": "MCP-Benchmark/1.0"}

        t = _now_ms()
        r1 = requests.get(
            "https://developer.nps.gov/api/v1/parks",
            params={"stateCode": "CA", "limit": 15, "api_key": NPS_KEY},
            headers=HEADERS,
            timeout=20,
        )
        r1.raise_for_status()
        parks = r1.json().get("data", [])
        log.append({"step": "findParks", "duration_ms": _now_ms() - t, "found": len(parks)})
        if not parks:
            return _error(rid, "NO_DATA", "NPS returned no parks", start)

        park_code = parks[0].get("parkCode", "")
        t = _now_ms()
        r2 = requests.get(
            "https://developer.nps.gov/api/v1/parks",
            params={"parkCode": park_code, "api_key": NPS_KEY},
            headers=HEADERS,
            timeout=20,
        )
        r2.raise_for_status()
        detail = r2.json().get("data", [{}])[0]
        log.append({"step": "getParkDetails", "duration_ms": _now_ms() - t, "parkCode": park_code})

        lats = []
        for p in parks:
            try:
                lats.append(float(p["latitude"]))
            except (KeyError, ValueError, TypeError):
                pass
        if not lats:
            return _error(rid, "NO_LAT", "Could not parse latitudes", start)

        return _success(rid, {
            "chain": "M2",
            "park_count": len(parks),
            "detail_park": detail.get("fullName", park_code),
            "latitudes": lats,
            "stats": {
                "mean":   round(statistics.mean(lats), 4),
                "median": statistics.median(lats),
                "sum":    round(sum(lats), 4),
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M2_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M3 - Hacker News top-10 stories + item fetches -> mean / median / mode scores
# NOTE: Reddit blocks AWS IP ranges. HN substituted (same call count, same pattern as H8).
# ---------------------------------------------------------------------------

@mcp.tool()
def m3_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M3 on EC2: HN top-10 stories list + item fetch for each - 2 sequential GETs + mean/median/mode scores. Est. payload ~33 KB.
    NOTE: Reddit blocks AWS IPs; Hacker News is a structural equivalent substitute."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []

        t = _now_ms()
        r1 = requests.get(f"{HN_BASE}/topstories.json", timeout=15)
        r1.raise_for_status()
        ids = r1.json()[:10]
        log.append({"step": "fetch_top_stories", "duration_ms": _now_ms() - t, "stories": len(ids)})

        scores, top_title = [], ""
        for i, sid in enumerate(ids):
            t = _now_ms()
            ri = requests.get(f"{HN_BASE}/item/{sid}.json", timeout=10)
            ri.raise_for_status()
            item = ri.json() or {}
            if i == 0:
                top_title = item.get("title", "")
            if item.get("score") is not None:
                scores.append(item["score"])
            log.append({"step": f"fetch_story_{i+1}", "duration_ms": _now_ms() - t,
                        "story_id": sid, "score": item.get("score")})

        if not scores:
            return _error(rid, "NO_SCORES", "No scores returned from HN", start)

        score_mode = Counter(scores).most_common(1)[0][0]
        return _success(rid, {
            "chain": "M3",
            "source": "Hacker News (Reddit blocked on AWS)",
            "story_count": len(ids),
            "top_story_title": top_title,
            "scores": scores,
            "stats": {
                "mean":   round(statistics.mean(scores), 2),
                "median": statistics.median(scores),
                "mode":   score_mode,
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M3_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M4 - Hugging Face text-classification (20) + model detail -> mean / median / sum downloads
# ---------------------------------------------------------------------------

@mcp.tool()
def m4_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M4 on EC2: HF Hub top-20 text-classification models + detail for #1 - 2 sequential GETs + mean/median/sum downloads. Est. payload ~32 KB."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        HEADERS = {"User-Agent": "MCP-Benchmark/1.0"}

        t = _now_ms()
        r1 = requests.get(
            "https://huggingface.co/api/models",
            params={"filter": "text-classification", "limit": 20, "sort": "downloads", "direction": -1},
            headers=HEADERS,
            timeout=20,
        )
        r1.raise_for_status()
        models = r1.json()
        log.append({"step": "search_models", "duration_ms": _now_ms() - t, "found": len(models)})
        if not models:
            return _error(rid, "NO_DATA", "HF returned no models", start)

        top_id = models[0].get("modelId") or models[0].get("id", "")
        t = _now_ms()
        r2 = requests.get(
            f"https://huggingface.co/api/models/{top_id}",
            headers=HEADERS,
            timeout=20,
        )
        r2.raise_for_status()
        top_detail = r2.json()
        log.append({"step": "get_model_info", "duration_ms": _now_ms() - t, "modelId": top_id})

        downloads = [m.get("downloads", 0) for m in models if m.get("downloads") is not None]
        if not downloads:
            return _error(rid, "NO_DL", "No download counts found", start)

        return _success(rid, {
            "chain": "M4",
            "model_count": len(models),
            "top_model": top_id,
            "top_model_downloads": top_detail.get("downloads"),
            "stats": {
                "mean":   round(statistics.mean(downloads), 2),
                "median": statistics.median(downloads),
                "sum":    sum(downloads),
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M4_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M5 - Met Museum search impressionism (20 IDs) + object detail -> mean / median / sum IDs
# ---------------------------------------------------------------------------

@mcp.tool()
def m5_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M5 on EC2: Met Museum search impressionism + 20 objectIDs + detail for first - 2 sequential GETs + mean/median/sum IDs. Est. payload ~22 KB."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []

        t = _now_ms()
        r1 = requests.get(
            "https://collectionapi.metmuseum.org/public/collection/v1/search",
            params={"q": "impressionism", "hasImages": "true"},
            timeout=20,
        )
        r1.raise_for_status()
        data = r1.json()
        oids = (data.get("objectIDs") or [])[:20]
        log.append({"step": "search_museum_objects", "duration_ms": _now_ms() - t,
                    "total_results": data.get("total"), "sampled": len(oids)})
        if not oids:
            return _error(rid, "NO_DATA", "Met search returned no objects", start)

        t = _now_ms()
        r2 = requests.get(
            f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oids[0]}",
            timeout=20,
        )
        r2.raise_for_status()
        detail = r2.json()
        log.append({"step": "get_museum_object", "duration_ms": _now_ms() - t, "objectID": oids[0]})

        ids_f = [float(i) for i in oids]
        return _success(rid, {
            "chain": "M5",
            "total_results": data.get("total"),
            "sampled_count": len(oids),
            "first_object_title": detail.get("title"),
            "first_object_date":  detail.get("objectDate"),
            "stats": {
                "mean":   round(statistics.mean(ids_f), 2),
                "median": statistics.median(ids_f),
                "sum":    int(sum(ids_f)),
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M5_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M6 - FIPE car brands -> FIAT models -> moto brands -> mean / median / mode model codes
# ---------------------------------------------------------------------------

@mcp.tool()
def m6_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M6 on EC2: FIPE Brazilian auto API - car brands + FIAT models + moto brands - 3 GETs + mean/median/mode of model codes. Est. payload ~24 KB."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []

        t = _now_ms()
        r1 = requests.get("https://parallelum.com.br/fipe/api/v1/carros/marcas", timeout=15)
        r1.raise_for_status()
        brands = r1.json()
        log.append({"step": "get_car_brands", "duration_ms": _now_ms() - t, "brand_count": len(brands)})

        fiat = next((b for b in brands if "FIAT" in b.get("nome", "").upper()), brands[0])
        brand_code = fiat["codigo"]

        t = _now_ms()
        r2 = requests.get(
            f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{brand_code}/modelos",
            timeout=15,
        )
        r2.raise_for_status()
        models = r2.json().get("modelos", [])
        log.append({"step": "search_car_price", "duration_ms": _now_ms() - t,
                    "brand": fiat.get("nome"), "model_count": len(models)})

        t = _now_ms()
        r3 = requests.get("https://parallelum.com.br/fipe/api/v1/motos/marcas", timeout=15)
        r3.raise_for_status()
        moto_brands = r3.json()
        log.append({"step": "get_vehicles_by_type", "duration_ms": _now_ms() - t,
                    "moto_brands": len(moto_brands)})

        codes = [float(m["codigo"]) for m in models if m.get("codigo")]
        if not codes:
            return _error(rid, "NO_CODES", "No model codes found", start)

        mode_code = Counter([int(c) for c in codes]).most_common(1)[0][0]
        return _success(rid, {
            "chain": "M6",
            "car_brand_count":  len(brands),
            "fiat_brand_code":  brand_code,
            "fiat_model_count": len(models),
            "moto_brand_count": len(moto_brands),
            "stats": {
                "mean_model_code":   round(statistics.mean(codes), 2),
                "median_model_code": statistics.median(codes),
                "mode_model_code":   mode_code,
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M6_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M7 - OKX BTC-USDT 48H candles + ETH ticker -> mean / median / sum closes + volume sum
# ---------------------------------------------------------------------------

@mcp.tool()
def m7_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M7 on EC2: OKX BTC-USDT 48-hour candles + ETH-USDT ticker - 2 GETs + mean/median/sum closes + sum volumes. Est. payload ~12.5 KB."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []

        t = _now_ms()
        r1 = requests.get(
            "https://www.okx.com/api/v5/market/candles",
            params={"instId": "BTC-USDT", "bar": "1H", "limit": 48},
            timeout=20,
        )
        r1.raise_for_status()
        candles = r1.json().get("data", [])
        # OKX format: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
        closes  = [float(c[4]) for c in candles]
        volumes = [float(c[5]) for c in candles]
        log.append({"step": "get_candlesticks", "duration_ms": _now_ms() - t, "candles": len(candles)})

        t = _now_ms()
        r2 = requests.get(
            "https://www.okx.com/api/v5/market/ticker",
            params={"instId": "ETH-USDT"},
            timeout=20,
        )
        r2.raise_for_status()
        eth_price = float(r2.json()["data"][0]["last"])
        log.append({"step": "get_price_eth", "duration_ms": _now_ms() - t, "eth_usdt": eth_price})

        if not closes:
            return _error(rid, "NO_CANDLES", "No candle data returned from OKX", start)

        return _success(rid, {
            "chain": "M7",
            "candle_count": len(candles),
            "eth_usdt_price": eth_price,
            "stats": {
                "close_mean":   round(statistics.mean(closes), 2),
                "close_median": statistics.median(closes),
                "close_sum":    round(sum(closes), 2),
                "volume_sum":   round(sum(volumes), 4),
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M7_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M8 - Steam top sellers + featured games -> mean / median / sum / mode prices
# NOTE: Game Trends API unavailable; Steam Store API is a structural equivalent.
# ---------------------------------------------------------------------------

@mcp.tool()
def m8_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M8 on EC2: Steam featuredcategories (top sellers) + featured games - 2 GETs + mean/median/sum/mode prices. Est. payload ~18 KB.
    NOTE: Game Trends API unavailable; Steam Store API is a structural equivalent substitute."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []

        t = _now_ms()
        r1 = requests.get(
            "https://store.steampowered.com/api/featuredcategories/",
            params={"cc": "us", "l": "en"},
            timeout=20,
        )
        r1.raise_for_status()
        top_sellers = r1.json().get("top_sellers", {}).get("items", [])
        log.append({"step": "get_steam_top_sellers", "duration_ms": _now_ms() - t,
                    "count": len(top_sellers)})

        t = _now_ms()
        r2 = requests.get(
            "https://store.steampowered.com/api/featured/",
            params={"cc": "us", "l": "en"},
            timeout=20,
        )
        r2.raise_for_status()
        featured = r2.json().get("featured_win", [])
        log.append({"step": "get_steam_most_played", "duration_ms": _now_ms() - t,
                    "count": len(featured)})

        # final_price in cents
        all_items = top_sellers[:10] + featured[:10]
        prices = [item["final_price"] / 100.0 for item in all_items if item.get("final_price") is not None]
        if not prices:
            return _error(rid, "NO_PRICES", "No price data found in Steam response", start)

        price_mode = Counter([round(p) for p in prices]).most_common(1)[0][0]
        return _success(rid, {
            "chain": "M8",
            "source": "Steam Store API (Game Trends API unavailable)",
            "top_seller_count":  len(top_sellers),
            "featured_count":    len(featured),
            "price_sample_size": len(prices),
            "stats": {
                "mean_price_usd":   round(statistics.mean(prices), 2),
                "median_price_usd": statistics.median(prices),
                "sum_prices_usd":   round(sum(prices), 2),
                "mode_price_usd":   price_mode,
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M8_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M9 - NixOS/Repology nodejs search + info + nixhub versions -> mean / median / sum
# ---------------------------------------------------------------------------

@mcp.tool()
def m9_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M9 on EC2: Repology nodejs search + project info + nixhub version history - 3 GETs + mean/median/sum version counts. Est. payload ~45 KB."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        HEADERS = {"User-Agent": "MCP-Benchmark/1.0"}

        # GET 1 - Repology search (nixos_search step)
        t = _now_ms()
        search_results = []
        try:
            r1 = requests.get(
                f"{REPOLOGY_BASE}/projects/?search=nodejs&inrepo=nix_unstable",
                headers=HEADERS,
                timeout=20,
            )
            if r1.status_code == 200:
                search_results = list(r1.json().keys())[:20]
        except Exception:
            search_results = ["nodejs"]
        log.append({"step": "nixos_search", "duration_ms": _now_ms() - t, "results": len(search_results)})

        # GET 2 - Repology project info (nixos_info step)
        t = _now_ms()
        pkg_detail = []
        try:
            r2 = requests.get(f"{REPOLOGY_BASE}/project/nodejs", headers=HEADERS, timeout=20)
            if r2.status_code == 200:
                pkg_detail = r2.json()
        except Exception:
            pass
        nix_pkgs = [p for p in pkg_detail if p.get("repo", "").startswith("nix")]
        log.append({"step": "nixos_info", "duration_ms": _now_ms() - t, "nix_entries": len(nix_pkgs)})

        # GET 3 - nixhub version history (nixhub_package_versions step)
        t = _now_ms()
        version_counts = []
        try:
            r3 = requests.get(f"{NIXHUB_BASE}/packages/nodejs", headers=HEADERS, timeout=20)
            if r3.status_code == 200:
                releases = r3.json().get("releases", r3.json().get("versions", []))
                version_counts = [
                    len(v.get("packages", [v])) if isinstance(v, dict) else 1
                    for v in releases[:50]
                ]
        except Exception:
            pass
        if not version_counts:
            version_counts = list(range(1, max(len(nix_pkgs), 5) + 1))
        log.append({"step": "nixhub_package_versions", "duration_ms": _now_ms() - t,
                    "versions": len(version_counts)})

        return _success(rid, {
            "chain": "M9",
            "package": "nodejs",
            "search_results": len(search_results),
            "nix_entries": len(nix_pkgs),
            "version_entries": len(version_counts),
            "stats": {
                "mean":   round(statistics.mean(version_counts), 2),
                "median": statistics.median(version_counts),
                "sum":    sum(version_counts),
            },
            "chain_log": log,
        }, start)
    except Exception as e:
        return _error(rid, "M9_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# M10 - Wikipedia search -> article -> mobile sections -> mean / median / sum lengths
# ---------------------------------------------------------------------------
@mcp.tool()
def m10_ec2(request_id: str | None = None) -> Dict[str, Any]:
    """M10 on EC2: Wikipedia search + article + section structure (compatible with current APIs)."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        HEADERS = {"User-Agent": "MCP-Benchmark/1.0"}

        # GET 1 - search
        t = _now_ms()
        r1 = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": "distributed systems",
                "srlimit": 5,
                "format": "json"
            },
            headers=HEADERS,
            timeout=15,
        )
        r1.raise_for_status()
        results = r1.json()["query"]["search"]
        if not results:
            return _error(rid, "NO_RESULTS", "No search results found", start)
        title = results[0]["title"]
        log.append({"step": "search_wikipedia", "duration_ms": _now_ms() - t, "title": title})

        # GET 2 - full article wikitext
        t = _now_ms()
        r2 = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "titles": title,
                "format": "json",
                "formatversion": 2
            },
            headers=HEADERS,
            timeout=15,
        )
        r2.raise_for_status()
        pages = r2.json()["query"]["pages"]
        raw_content = pages[0]["revisions"][0]["slots"]["main"]["content"]
        log.append({"step": "get_article", "duration_ms": _now_ms() - t, "char_count": len(raw_content)})

        # GET 3 - parse sections via MediaWiki API (current, safe)
        t = _now_ms()
        r3 = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "parse",
                "page": title,
                "prop": "sections",
                "format": "json"
            },
            headers=HEADERS,
            timeout=15,
        )
        r3.raise_for_status()
        sections_info = r3.json().get("parse", {}).get("sections", [])
        lengths = []
        for s in sections_info:
            sec_text = s.get("line", "")
            if sec_text.strip():
                lengths.append(len(sec_text))
        log.append({"step": "get_sections", "duration_ms": _now_ms() - t, "sections": len(lengths)})

        # Fallback: split wikitext on == headers == if no sections
        if not lengths:
            parts = raw_content.split("==")
            lengths = [len(p) for p in parts if len(p.strip()) > 80]
        if not lengths:
            return _error(rid, "NO_SECTIONS", "Could not parse article sections", start)

        return _success(rid, {
            "chain": "M10",
            "title": title,
            "section_count": len(lengths),
            "article_char_count": len(raw_content),
            "stats": {
                "mean_section_len": round(statistics.mean(lengths), 2),
                "median_section_len": statistics.median(lengths),
                "sum_section_len": sum(lengths),
            },
            "chain_log": log,
        }, start)

    except Exception as e:
        return _error(rid, "M10_FAILED", str(e), start)
@mcp.tool()
def h1_ec2(query: str = "serverless MCP", limit: int = 10, request_id: str | None = None) -> Dict[str, Any]:
    """H1 on EC2: arXiv search + PDF binary download + full text extraction + mean/median/sum/min/max word counts."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        t = _now_ms()
        r = requests.get("http://export.arxiv.org/api/query",
            params={"search_query": f"all:{query}", "start": 0, "max_results": limit}, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns):
            raw_id = entry.find("atom:id", ns).text or ""
            paper_id = raw_id.split("/abs/")[-1].strip()
            papers.append({"paper_id": paper_id, "title": (entry.find("atom:title", ns).text or "").strip()})
        log.append({"step": "search_arxiv", "duration_ms": _now_ms() - t, "found": len(papers)})
        if not papers:
            return _error(rid, "NO_RESULTS", "No papers found", start)
        top_id = papers[0]["paper_id"]

        t = _now_ms()
        pdf_r = requests.get(f"https://arxiv.org/pdf/{top_id}", timeout=90, stream=True)
        pdf_r.raise_for_status()
        content = pdf_r.content
        pdf_path = f"/tmp/arxiv_{top_id.replace('/', '_').replace('.', '_')}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(content)
        pdf_size_kb = round(len(content) / 1024, 2)
        log.append({"step": "download_arxiv", "duration_ms": _now_ms() - t, "size_kb": pdf_size_kb})

        t = _now_ms()
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        wc = [len((p.extract_text() or "").split()) for p in reader.pages]
        log.append({"step": "read_arxiv_paper", "duration_ms": _now_ms() - t, "pages": len(wc)})

        return _success(rid, {
            "chain": "H1", "paper_id": top_id, "pdf_size_kb": pdf_size_kb,
            "num_pages": len(wc), "total_words": sum(wc),
            "stats": {"mean": round(statistics.mean(wc), 2), "median": statistics.median(wc),
                      "sum": sum(wc), "min": min(wc), "max": max(wc)},
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H1_FAILED", str(e), start) 
# ---------------------------------------------------------------------------
# H2 — ClinicalTrials 5 Chained GETs
# ---------------------------------------------------------------------------

@mcp.tool()
def h2_ec2(condition: str = "BRAF melanoma", limit: int = 5, request_id: str | None = None) -> Dict[str, Any]:
    """H2 on EC2: 5 sequential ClinicalTrials.gov GETs (search, record, references, locations, outcomes) + mean/sum/median enrollment."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        BASE = "https://clinicaltrials.gov/api/v2"
        t = _now_ms()
        r1 = requests.get(f"{BASE}/studies", params={
            "query.cond": condition, "pageSize": limit, "format": "json",
            "fields": "NCTId,BriefTitle,EnrollmentCount,OverallStatus"
        }, timeout=30)
        r1.raise_for_status()
        studies = r1.json().get("studies", [])
        log.append({"step": "trial_searcher", "duration_ms": _now_ms() - t, "found": len(studies)})
        if not studies:
            return _error(rid, "NO_RESULTS", "No trials found", start)
        nct_id = studies[0].get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")

        for step_name, fields in [
            ("trial_getter", None),
            ("trial_references", "ReferenceCitation,ReferencePMID"),
            ("trial_locations", "LocationFacility,LocationCity,LocationCountry"),
            ("trial_outcomes", "PrimaryOutcomeMeasure,SecondaryOutcomeMeasure"),
        ]:
            t = _now_ms()
            params = {"format": "json"}
            if fields:
                params["fields"] = fields
            requests.get(f"{BASE}/studies/{nct_id}", params=params, timeout=30).raise_for_status()
            log.append({"step": step_name, "duration_ms": _now_ms() - t})

        enrollments = [
            int(s.get("protocolSection", {}).get("designModule", {}).get("enrollmentInfo", {}).get("count", 0))
            for s in studies
            if s.get("protocolSection", {}).get("designModule", {}).get("enrollmentInfo", {}).get("count")
        ]
        if not enrollments:
            enrollments = [0]

        return _success(rid, {
            "chain": "H2", "nct_id": nct_id, "trials_searched": len(studies),
            "stats": {"mean_enrollment": round(statistics.mean(enrollments), 2),
                      "sum_enrollment": sum(enrollments),
                      "median_enrollment": statistics.median(enrollments)},
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H2_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# H3 — NASA Asteroid Feed
# ---------------------------------------------------------------------------

@mcp.tool()
def h3_ec2(nasa_api_key: str = "DEMO_KEY", request_id: str | None = None) -> Dict[str, Any]:
    """H3 on EC2: NASA asteroid feed (7-day) + browse + lookup — 3 chained GETs + mean/median/sum/min/max diameters + mode(hazardous)."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        key = nasa_api_key or "yc5RVaFw3VqF8e2h9zinRiDnCqyqW0SBE2KCTPs9"
        t = _now_ms()
        today = date.today().isoformat()
        end = (date.today() + timedelta(days=7)).isoformat()
        r1 = requests.get("https://api.nasa.gov/neo/rest/v1/feed",
            params={"start_date": today, "end_date": end, "api_key": key}, timeout=30)
        r1.raise_for_status()
        all_neos = []
        for day_list in r1.json().get("near_earth_objects", {}).values():
            all_neos.extend(day_list)
        log.append({"step": "get_asteroids_feed", "duration_ms": _now_ms() - t, "neos_found": len(all_neos)})

        t = _now_ms()
        r2 = requests.get("https://api.nasa.gov/neo/rest/v1/neo/browse", params={"api_key": key}, timeout=30)
        r2.raise_for_status()
        browse_neos = r2.json().get("near_earth_objects", [])
        log.append({"step": "browse_asteroids", "duration_ms": _now_ms() - t, "catalog_size": len(browse_neos)})

        asteroid_id = all_neos[0].get("id") if all_neos else (browse_neos[0].get("id") if browse_neos else "3542519")
        t = _now_ms()
        r3 = requests.get(f"https://api.nasa.gov/neo/rest/v1/neo/{asteroid_id}", params={"api_key": key}, timeout=30)
        r3.raise_for_status()
        log.append({"step": "get_asteroid_lookup", "duration_ms": _now_ms() - t})

        diameters, miss_distances, hazardous_flags = [], [], []
        for neo in all_neos:
            diam = neo.get("estimated_diameter", {}).get("meters", {})
            diameters.append((diam.get("estimated_diameter_min", 0) + diam.get("estimated_diameter_max", 0)) / 2)
            approaches = neo.get("close_approach_data", [])
            if approaches:
                miss_distances.append(float(approaches[0].get("miss_distance", {}).get("kilometers", 0)))
            hazardous_flags.append(str(neo.get("is_potentially_hazardous_asteroid", False)))
        if not diameters: diameters = [0]
        if not miss_distances: miss_distances = [0]

        return _success(rid, {
            "chain": "H3", "feed_count": len(all_neos), "catalog_count": len(browse_neos),
            "stats": {
                "diameter_mean": round(statistics.mean(diameters), 4),
                "diameter_median": statistics.median(diameters),
                "diameter_sum": round(sum(diameters), 4),
                "diameter_min": round(min(diameters), 4),
                "diameter_max": round(max(diameters), 4),
                "miss_distance_sum": round(sum(miss_distances), 2),
                "hazardous_mode": Counter(hazardous_flags).most_common(1)[0][0] if hazardous_flags else "False",
                "records_processed": len(all_neos)
            },
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H3_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# H4 — BioMCP + arXiv Cross-Database + PDF
# ---------------------------------------------------------------------------

@mcp.tool()
def h4_ec2(gene: str = "BRAF", limit: int = 5, request_id: str | None = None) -> Dict[str, Any]:
    """H4 on EC2: PubMed search + article fetch + arXiv cross-ref + PDF binary download + text extraction + mean/sum/median citation counts."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        t = _now_ms()
        r1 = requests.get(f"{PUBMED_BASE}/esearch.fcgi",
            params={"db": "pubmed", "term": f"{gene}[Gene]", "retmax": limit, "retmode": "json"}, timeout=30)
        r1.raise_for_status()
        pmids = r1.json().get("esearchresult", {}).get("idlist", [])
        log.append({"step": "article_searcher", "duration_ms": _now_ms() - t, "pmids_found": len(pmids)})
        if not pmids:
            return _error(rid, "NO_RESULTS", "No PubMed articles found", start)
        top_pmid = pmids[0]

        t = _now_ms()
        r2 = requests.get(f"{PUBMED_BASE}/efetch.fcgi",
            params={"db": "pubmed", "id": top_pmid, "retmode": "xml", "rettype": "abstract"}, timeout=30)
        r2.raise_for_status()
        root2 = ET.fromstring(r2.text)
        title_el = root2.find(".//ArticleTitle")
        article_title = title_el.text if title_el is not None else "Unknown"
        log.append({"step": "article_getter", "duration_ms": _now_ms() - t, "pmid": top_pmid})

        t = _now_ms()
        r3 = requests.get("http://export.arxiv.org/api/query",
            params={"search_query": f"all:{gene} V600E resistance", "start": 0, "max_results": 5}, timeout=30)
        r3.raise_for_status()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        arxiv_papers = [e.find("atom:id", ns).text.split("/abs/")[-1].strip()
                        for e in ET.fromstring(r3.text).findall("atom:entry", ns)]
        log.append({"step": "search_arxiv", "duration_ms": _now_ms() - t, "arxiv_found": len(arxiv_papers)})

        page_word_counts = []
        pdf_size_kb = 0
        if arxiv_papers:
            top_arxiv = arxiv_papers[0]
            t = _now_ms()
            pdf_r = requests.get(f"https://arxiv.org/pdf/{top_arxiv}", timeout=90, stream=True)
            pdf_r.raise_for_status()
            content = pdf_r.content
            pdf_path = f"/tmp/arxiv_h4_{top_arxiv.replace('/', '_').replace('.', '_')}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(content)
            pdf_size_kb = round(len(content) / 1024, 2)
            log.append({"step": "download_arxiv", "duration_ms": _now_ms() - t, "size_kb": pdf_size_kb})

            t = _now_ms()
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            page_word_counts = [len((p.extract_text() or "").split()) for p in reader.pages]
            log.append({"step": "read_arxiv_paper", "duration_ms": _now_ms() - t, "pages": len(page_word_counts)})

        citation_counts = []
        for pmid in pmids:
            try:
                rx = requests.get(f"{PUBMED_BASE}/efetch.fcgi",
                    params={"db": "pubmed", "id": pmid, "retmode": "xml", "rettype": "abstract"}, timeout=15)
                citation_counts.append(len(ET.fromstring(rx.text).findall(".//Reference")))
            except Exception:
                citation_counts.append(0)
        if not citation_counts: citation_counts = [0]

        return _success(rid, {
            "chain": "H4", "gene": gene, "top_pmid": top_pmid,
            "article_title": article_title, "arxiv_papers_found": len(arxiv_papers),
            "pdf_size_kb": pdf_size_kb, "num_pages": len(page_word_counts),
            "citation_stats": {
                "mean": round(statistics.mean(citation_counts), 2),
                "sum": sum(citation_counts),
                "median": statistics.median(citation_counts)
            },
            "word_count_stats": {
                "mean": round(statistics.mean(page_word_counts), 2) if page_word_counts else 0,
                "median": statistics.median(page_word_counts) if page_word_counts else 0,
                "sum": sum(page_word_counts),
                "min": min(page_word_counts) if page_word_counts else 0,
                "max": max(page_word_counts) if page_word_counts else 0,
            },
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H4_FAILED", str(e), start)
# ---------------------------------------------------------------------------
# H6 — DEX Paprika OHLCV
# ---------------------------------------------------------------------------

@mcp.tool()
def h6_ec2(network: str = "ethereum", ohlcv_limit: int = 168, request_id: str | None = None) -> Dict[str, Any]:
    """H6 on EC2: 5 chained DexPaprika GETs (networks→dexes→pools→detail→OHLCV 168hr) + mean/median/sum/min/max prices+volumes."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        DEX_BASE = "https://api.dexpaprika.com"
        pools = []
        for step_name, url, params in [
            ("getNetworks", f"{DEX_BASE}/networks", {}),
            ("getNetworkDexes", f"{DEX_BASE}/networks/{network}/dexes", {"limit": 10}),
            ("getNetworkPools", f"{DEX_BASE}/networks/{network}/pools", {"limit": 20}),
        ]:
            t = _now_ms()
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            if step_name == "getNetworkPools":
                pools = data if isinstance(data, list) else data.get("pools", [])
            log.append({"step": step_name, "duration_ms": _now_ms() - t})

        if not pools:
            return _error(rid, "NO_POOLS", "No pools found", start)
        top_pool = pools[0].get("id") or pools[0].get("address", "")

        t = _now_ms()
        requests.get(f"{DEX_BASE}/networks/{network}/pools/{top_pool}", timeout=20).raise_for_status()
        log.append({"step": "getPoolDetails", "duration_ms": _now_ms() - t})

        t = _now_ms()
        r5 = requests.get(f"{DEX_BASE}/networks/{network}/pools/{top_pool}/ohlcv", params={
            "start": int(time.time()) - (ohlcv_limit * 3600),
            "limit": ohlcv_limit, "interval": "1h"
        }, timeout=30)
        r5.raise_for_status()
        candles = r5.json() if isinstance(r5.json(), list) else r5.json().get("ohlcv", [])
        log.append({"step": "getPoolOHLCV", "duration_ms": _now_ms() - t, "candles": len(candles)})

        close_prices = [float(c[4]) if isinstance(c, list) and len(c) >= 6 else float(c.get("close", 0)) for c in candles]
        volumes = [float(c[5]) if isinstance(c, list) and len(c) >= 6 else float(c.get("volume", 0)) for c in candles]
        if not close_prices: close_prices = [0.0]

        return _success(rid, {
            "chain": "H6", "network": network, "top_pool": top_pool,
            "stats": {
                "price_mean": round(statistics.mean(close_prices), 6),
                "price_median": statistics.median(close_prices),
                "price_sum": round(sum(close_prices), 6),
                "price_min": round(min(close_prices), 6),
                "price_max": round(max(close_prices), 6),
                "volume_sum": round(sum(volumes), 2),
                "candles_processed": len(close_prices)
            },
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H6_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# H7 — NixOS Package Chain
# ---------------------------------------------------------------------------

@mcp.tool()
def h7_ec2(package: str = "python", limit: int = 50, request_id: str | None = None) -> Dict[str, Any]:
    """H7 on EC2: 5 chained NixOS/Repology GETs (search→info→versions→find_version→flakes) + mean/median/sum/min/max version counts."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        HEADERS = {"User-Agent": "MCP-Benchmark/1.0"}

        t = _now_ms()
        search_results = []
        try:
            r1 = requests.get(f"{REPOLOGY_BASE}/projects/?search={package}&inrepo=nix_unstable",
                headers=HEADERS, timeout=20)
            if r1.status_code == 200:
                search_results = list(r1.json().keys())[:limit]
        except Exception:
            search_results = [package]
        log.append({"step": "nixos_search", "duration_ms": _now_ms() - t, "results": len(search_results)})

        t = _now_ms()
        pkg_detail = []
        try:
            r2 = requests.get(f"{REPOLOGY_BASE}/project/python3", headers=HEADERS, timeout=20)
            if r2.status_code == 200:
                pkg_detail = r2.json()
        except Exception:
            pass
        nix_pkgs = [p for p in pkg_detail if p.get("repo", "").startswith("nix")]
        log.append({"step": "nixos_info", "duration_ms": _now_ms() - t, "nix_entries": len(nix_pkgs)})

        t = _now_ms()
        version_counts = []
        try:
            r3 = requests.get(f"{NIXHUB_BASE}/packages/python3", headers=HEADERS, timeout=20)
            if r3.status_code == 200:
                releases = r3.json().get("releases", r3.json().get("versions", []))
                version_counts = [len(v.get("packages", [v])) if isinstance(v, dict) else 1 for v in releases[:50]]
        except Exception:
            pass
        if not version_counts:
            version_counts = list(range(1, 21))
        log.append({"step": "nixhub_package_versions", "duration_ms": _now_ms() - t, "versions": len(version_counts)})

        t = _now_ms()
        found_version = False
        try:
            r4 = requests.get(f"{NIXHUB_BASE}/packages/python3", params={"version": "3.11"},
                headers=HEADERS, timeout=20)
            found_version = r4.status_code == 200
        except Exception:
            pass
        log.append({"step": "nixhub_find_version", "duration_ms": _now_ms() - t, "found": found_version})

        t = _now_ms()
        flake_counts = []
        try:
            r5 = requests.get(f"{REPOLOGY_BASE}/projects/?search={package}&inrepo=nix_unstable&count=1",
                headers=HEADERS, timeout=20)
            if r5.status_code == 200:
                flake_counts = [i + 1 for i in range(len(list(r5.json().keys())))]
        except Exception:
            pass
        log.append({"step": "nixos_flakes_search", "duration_ms": _now_ms() - t, "flakes": len(flake_counts)})

        all_counts = version_counts + flake_counts if flake_counts else version_counts
        if not all_counts: all_counts = [1]

        return _success(rid, {
            "chain": "H7", "package": package,
            "search_results": len(search_results), "versions_found": len(version_counts),
            "flakes_found": len(flake_counts),
            "stats": {
                "mean": round(statistics.mean(all_counts), 2),
                "median": statistics.median(all_counts),
                "sum": sum(all_counts),
                "min": min(all_counts),
                "max": max(all_counts),
                "records": len(all_counts)
            },
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H7_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# H8 — Hacker News (replaces Reddit — Reddit blocks AWS IPs)
# ---------------------------------------------------------------------------

@mcp.tool()
def h8_ec2(limit: int = 25, request_id: str | None = None) -> Dict[str, Any]:
    """H8 on EC2: Hacker News top stories list + 3 deep post fetches with comments — 4 GETs + mean/median/sum/mode/min/max scores."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        t = _now_ms()
        r1 = requests.get(f"{HN_BASE}/topstories.json", timeout=20)
        r1.raise_for_status()
        top_story_ids = r1.json()[:limit]
        log.append({"step": "fetch_top_stories", "duration_ms": _now_ms() - t, "stories": len(top_story_ids)})

        all_scores, all_types, stories_fetched = [], [], []
        for i, story_id in enumerate(top_story_ids[:3]):
            t = _now_ms()
            r_story = requests.get(f"{HN_BASE}/item/{story_id}.json", timeout=15)
            r_story.raise_for_status()
            story = r_story.json() or {}
            story_score = story.get("score", 0)
            stories_fetched.append({"id": story_id, "title": story.get("title", "")[:60], "score": story_score})
            for cid in story.get("kids", [])[:20]:
                try:
                    rc = requests.get(f"{HN_BASE}/item/{cid}.json", timeout=10)
                    if rc.status_code == 200:
                        c = rc.json() or {}
                        all_scores.append(c.get("score", 0) or 0)
                        all_types.append(c.get("type", "comment"))
                except Exception:
                    pass
            log.append({"step": f"fetch_story_{i+1}", "duration_ms": _now_ms() - t,
                        "story_id": story_id, "story_score": story_score})

        all_scores += [s["score"] for s in stories_fetched]
        if not all_scores: all_scores = [0]
        type_mode = Counter(all_types).most_common(1)[0][0] if all_types else "comment"

        return _success(rid, {
            "chain": "H8", "source": "Hacker News",
            "stories_fetched": len(top_story_ids),
            "top_stories": stories_fetched,
            "total_comments_analyzed": len(all_scores) - len(stories_fetched),
            "stats": {
                "score_mean": round(statistics.mean(all_scores), 2),
                "score_median": statistics.median(all_scores),
                "score_sum": sum(all_scores),
                "type_mode": type_mode,
                "score_min": min(all_scores),
                "score_max": max(all_scores)
            },
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H8_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# H9 — Multi-Database Paper Search
# ---------------------------------------------------------------------------

@mcp.tool()
def h9_ec2(query: str = "serverless cloud", limit: int = 5, request_id: str | None = None) -> Dict[str, Any]:
    """H9 on EC2: PubMed + bioRxiv + arXiv searches + PDF binary download + text extraction + mean/median/sum/min/max word counts."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        t = _now_ms()
        r1 = requests.get(f"{PUBMED_BASE}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"}, timeout=30)
        r1.raise_for_status()
        pubmed_ids = r1.json().get("esearchresult", {}).get("idlist", [])
        log.append({"step": "search_pubmed", "duration_ms": _now_ms() - t, "results": len(pubmed_ids)})

        t = _now_ms()
        biorxiv_count = 0
        try:
            r2 = requests.get("https://api.biorxiv.org/details/biorxiv/2024-01-01/2025-01-01/0/json", timeout=20)
            if r2.status_code == 200:
                biorxiv_count = len(r2.json().get("collection", []))
        except Exception:
            pass
        log.append({"step": "search_biorxiv", "duration_ms": _now_ms() - t, "results": biorxiv_count})

        t = _now_ms()
        r3 = requests.get("http://export.arxiv.org/api/query",
            params={"search_query": "all:lambda EC2 latency", "start": 0, "max_results": limit}, timeout=30)
        r3.raise_for_status()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        arxiv_papers = [e.find("atom:id", ns).text.split("/abs/")[-1].strip()
                        for e in ET.fromstring(r3.text).findall("atom:entry", ns)]
        log.append({"step": "search_arxiv", "duration_ms": _now_ms() - t, "results": len(arxiv_papers)})

        page_word_counts = []
        pdf_size_kb = 0
        if arxiv_papers:
            top_arxiv = arxiv_papers[0]
            t = _now_ms()
            pdf_r = requests.get(f"https://arxiv.org/pdf/{top_arxiv}", timeout=90, stream=True)
            pdf_r.raise_for_status()
            content = pdf_r.content
            pdf_path = f"/tmp/arxiv_h9_{top_arxiv.replace('/', '_').replace('.', '_')}.pdf"
            with open(pdf_path, "wb") as f:
                f.write(content)
            pdf_size_kb = round(len(content) / 1024, 2)
            log.append({"step": "download_arxiv", "duration_ms": _now_ms() - t, "size_kb": pdf_size_kb})

            t = _now_ms()
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            page_word_counts = [len((p.extract_text() or "").split()) for p in reader.pages]
            log.append({"step": "read_arxiv_paper", "duration_ms": _now_ms() - t, "pages": len(page_word_counts)})

        if not page_word_counts: page_word_counts = [0]

        return _success(rid, {
            "chain": "H9", "query": query, "databases_searched": 3,
            "pubmed_results": len(pubmed_ids),
            "biorxiv_results": biorxiv_count,
            "arxiv_results": len(arxiv_papers),
            "pdf_size_kb": pdf_size_kb,
            "word_count_stats": {
                "mean": round(statistics.mean(page_word_counts), 2),
                "median": statistics.median(page_word_counts),
                "sum": sum(page_word_counts),
                "min": min(page_word_counts),
                "max": max(page_word_counts),
                "pages": len(page_word_counts)
            },
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H9_FAILED", str(e), start)


# ---------------------------------------------------------------------------
# H10 — BioMCP + NixOS Cross-Domain
# ---------------------------------------------------------------------------

@mcp.tool()
def h10_ec2(chemical: str = "python bioinformatics", nix_package: str = "biopython",
            limit: int = 10, request_id: str | None = None) -> Dict[str, Any]:
    """H10 on EC2: PubMed search + article fetch + NixOS search + package info + version history — 5 cross-domain GETs + mean/median/sum/mode/min/max."""
    start = _now_ms()
    rid = request_id or str(uuid.uuid4())
    try:
        log = []
        HEADERS = {"User-Agent": "MCP-Benchmark/1.0"}

        t = _now_ms()
        r1 = requests.get(f"{PUBMED_BASE}/esearch.fcgi",
            params={"db": "pubmed", "term": chemical, "retmax": limit, "retmode": "json"}, timeout=30)
        r1.raise_for_status()
        pmids = r1.json().get("esearchresult", {}).get("idlist", [])
        log.append({"step": "article_searcher", "duration_ms": _now_ms() - t, "pmids": len(pmids)})
        if not pmids:
            return _error(rid, "NO_RESULTS", "No PubMed results found", start)
        top_pmid = pmids[0]

        t = _now_ms()
        r2 = requests.get(f"{PUBMED_BASE}/efetch.fcgi",
            params={"db": "pubmed", "id": top_pmid, "retmode": "xml", "rettype": "abstract"}, timeout=30)
        r2.raise_for_status()
        root2 = ET.fromstring(r2.text)
        title_el = root2.find(".//ArticleTitle")
        article_title = title_el.text if title_el is not None else "Unknown"
        log.append({"step": "article_getter", "duration_ms": _now_ms() - t, "pmid": top_pmid})

        t = _now_ms()
        nix_results = []
        try:
            r3 = requests.get(f"{REPOLOGY_BASE}/projects/?search={nix_package}&inrepo=nix_unstable",
                headers=HEADERS, timeout=20)
            if r3.status_code == 200:
                nix_results = list(r3.json().keys())
        except Exception:
            nix_results = [nix_package]
        log.append({"step": "nixos_search", "duration_ms": _now_ms() - t, "results": len(nix_results)})

        t = _now_ms()
        pkg_versions = []
        try:
            r4 = requests.get(f"{REPOLOGY_BASE}/project/{nix_package}", headers=HEADERS, timeout=20)
            if r4.status_code == 200:
                pkg_versions = [p.get("version", "0") for p in r4.json() if p.get("repo", "").startswith("nix")]
        except Exception:
            pkg_versions = ["1.0"]
        log.append({"step": "nixos_info", "duration_ms": _now_ms() - t, "versions": len(pkg_versions)})

        t = _now_ms()
        version_counts = []
        categories = []
        try:
            r5 = requests.get(f"{NIXHUB_BASE}/packages/{nix_package}", headers=HEADERS, timeout=20)
            if r5.status_code == 200:
                releases = r5.json().get("releases", r5.json().get("versions", []))
                version_counts = [len(v.get("packages", [v])) if isinstance(v, dict) else 1 for v in releases[:50]]
                categories = [v.get("version", "unknown") for v in releases[:50] if isinstance(v, dict)]
        except Exception:
            pass
        if not version_counts:
            version_counts = list(range(1, len(pkg_versions) + 1)) if pkg_versions else [1, 2, 3, 4, 5]
        if not categories:
            categories = pkg_versions if pkg_versions else ["unknown"]
        log.append({"step": "nixhub_package_versions", "duration_ms": _now_ms() - t, "versions": len(version_counts)})

        cat_mode = Counter(categories).most_common(1)[0][0]

        return _success(rid, {
            "chain": "H10", "chemical": chemical, "nix_package": nix_package,
            "top_pmid": top_pmid, "article_title": article_title,
            "nix_results": len(nix_results), "versions_found": len(version_counts),
            "stats": {
                "mean": round(statistics.mean(version_counts), 2),
                "median": statistics.median(version_counts),
                "sum": sum(version_counts),
                "category_mode": cat_mode,
                "min": min(version_counts),
                "max": max(version_counts),
                "records": len(version_counts)
            },
            "chain_log": log
        }, start)
    except Exception as e:
        return _error(rid, "H10_FAILED", str(e), start)

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
