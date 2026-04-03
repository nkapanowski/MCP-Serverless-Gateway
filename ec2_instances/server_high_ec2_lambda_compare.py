"""
server2.py — EC2 High Workload MCP Server
==========================================
Heavy workloads H1–H10 (H5 reserved), each with:
  • _ec2      → runs directly on this EC2 instance
  • _lambda   → routes the same workload to the Lambda backend
  • _compare  → runs both and returns a side-by-side timing comparison

Top-level utilities:
  • compare_all_heavy  → runs compare for every workload and returns a full table
"""

import asyncio
import json
import statistics
import time
import uuid
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

mcp = FastMCP("EC2 High Workload MCP")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LAMBDA_ENDPOINT = "https://lambda.mcp-endpoint.internal/v1/invoke"   # update as needed
LAMBDA_TIMEOUT  = 30.0   # seconds
EC2_TIMEOUT     = 30.0

ARXIV_SEARCH    = "https://export.arxiv.org/api/query"
ARXIV_PDF_BASE  = "https://arxiv.org/pdf"
CLINICAL_BASE   = "https://clinicaltrials.gov/api/v2/studies"
NASA_FEED       = "https://api.nasa.gov/neo/rest/v1/feed"
NASA_API_KEY    = "DEMO_KEY"
DEX_BASE        = "https://api.coinpaprika.com/v1"
HN_BASE         = "https://hacker-news.firebaseio.com/v0"
BIORXIV_BASE    = "https://api.biorxiv.org/details/biorxiv"
NIXOS_BASE      = "https://search.nixos.org/backend/latest-42-nixos-24.11/_search"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.monotonic() * 1000)


def _step(log: list, step: str, start: int, **extra) -> None:
    log.append({"step": step, "duration_ms": _now_ms() - start, **extra})


async def _lambda_call(route: str, payload: dict | None = None) -> dict:
    """POST a workload to the Lambda backend and return its parsed result."""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": route,
            "arguments": payload or {},
        },
    }
    async with httpx.AsyncClient(timeout=LAMBDA_TIMEOUT) as client:
        r = await client.post(LAMBDA_ENDPOINT, json=body)
        r.raise_for_status()
        data = r.json()
    raw = data["result"]["content"][0]["text"]
    return json.loads(raw)


def _compare_result(chain: str, ec2: dict, lam: dict) -> dict:
    ec2_ms  = ec2.get("total_duration_ms", 0)
    lam_ms  = lam.get("total_duration_ms", 0)
    faster  = "ec2" if ec2_ms <= lam_ms else "lambda"
    return {
        "chain":           chain,
        "ec2_duration_ms": ec2_ms,
        "lambda_duration_ms": lam_ms,
        "faster":          faster,
        "difference_ms":   abs(ec2_ms - lam_ms),
        "ec2_result":      ec2,
        "lambda_result":   lam,
    }


# ===========================================================================
# H1 — arXiv search + PDF download + text extraction
# ===========================================================================

async def _h1_core(query: str = "large language models") -> dict:
    log, t0 = [], _now_ms()

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        s = _now_ms()
        r = await client.get(ARXIV_SEARCH, params={"search_query": f"all:{query}", "max_results": 5})
        r.raise_for_status()
        _step(log, "arxiv_search", s, query=query, status=r.status_code)

        # crude XML parse — no lxml dependency required
        import re
        ids = re.findall(r"<id>http://arxiv\.org/abs/([^<]+)</id>", r.text)
        ids = [i.strip() for i in ids if i.strip()][:3]
        _step(log, "parse_ids", s, ids_found=len(ids))

        texts = []
        for arxiv_id in ids:
            ps = _now_ms()
            pdf_url = f"{ARXIV_PDF_BASE}/{arxiv_id}"
            pr = await client.get(pdf_url, follow_redirects=True)
            excerpt = pr.text[:200] if pr.status_code == 200 else ""
            texts.append({"id": arxiv_id, "bytes": len(pr.content), "excerpt": excerpt})
            _step(log, f"fetch_pdf_{arxiv_id}", ps, bytes=len(pr.content))

    return {
        "chain":            "H1",
        "source":           "arXiv",
        "query":            query,
        "papers_found":     len(ids),
        "pdfs_fetched":     len(texts),
        "results":          texts,
        "chain_log":        log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h1_ec2(query: str = "large language models") -> dict:
    result = await _h1_core(query)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h1_lambda(query: str = "large language models") -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h1_lambda", {"query": query})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h1_compare(query: str = "large language models") -> dict:
    ec2_r, lam_r = await asyncio.gather(_h1_core(query), _lambda_call("h1_lambda", {"query": query}))
    return _compare_result("H1", ec2_r, lam_r)


# ===========================================================================
# H2 — ClinicalTrials 5 chained GETs + enrollment stats
# ===========================================================================

async def _h2_core(condition: str = "diabetes") -> dict:
    log, t0 = [], _now_ms()
    pages, enrollments = [], []

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        next_token = None
        for i in range(5):
            s = _now_ms()
            params: dict[str, Any] = {"query.cond": condition, "pageSize": 10, "format": "json"}
            if next_token:
                params["pageToken"] = next_token
            r = await client.get(CLINICAL_BASE, params=params)
            r.raise_for_status()
            data = r.json()
            studies = data.get("studies", [])
            page_enroll = [
                s2.get("protocolSection", {})
                  .get("designModule", {})
                  .get("enrollmentInfo", {})
                  .get("count", 0)
                for s2 in studies
            ]
            enrollments.extend([e for e in page_enroll if isinstance(e, (int, float)) and e > 0])
            pages.append({"page": i + 1, "studies": len(studies)})
            next_token = data.get("nextPageToken")
            _step(log, f"page_{i+1}", s, studies=len(studies))
            if not next_token:
                break

    stats: dict[str, Any] = {}
    if enrollments:
        stats = {
            "count":  len(enrollments),
            "mean":   round(statistics.mean(enrollments), 1),
            "median": statistics.median(enrollments),
            "min":    min(enrollments),
            "max":    max(enrollments),
            "total":  sum(enrollments),
        }

    return {
        "chain":            "H2",
        "source":           "ClinicalTrials",
        "condition":        condition,
        "pages_fetched":    len(pages),
        "enrollment_stats": stats,
        "chain_log":        log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h2_ec2(condition: str = "diabetes") -> dict:
    result = await _h2_core(condition)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h2_lambda(condition: str = "diabetes") -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h2_lambda", {"condition": condition})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h2_compare(condition: str = "diabetes") -> dict:
    ec2_r, lam_r = await asyncio.gather(_h2_core(condition), _lambda_call("h2_lambda", {"condition": condition}))
    return _compare_result("H2", ec2_r, lam_r)


# ===========================================================================
# H3 — NASA asteroid feed (Near Earth Objects)
# ===========================================================================

async def _h3_core(days: int = 3) -> dict:
    import datetime
    log, t0 = [], _now_ms()
    today  = datetime.date.today()
    end    = today + datetime.timedelta(days=days)

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        s = _now_ms()
        r = await client.get(NASA_FEED, params={
            "start_date": str(today), "end_date": str(end), "api_key": NASA_API_KEY
        })
        r.raise_for_status()
        data = r.json()
        _step(log, "nasa_feed_fetch", s, status=r.status_code)

        neo_dates   = data.get("near_earth_objects", {})
        total_count = data.get("element_count", 0)
        hazardous   = []
        diameters   = []

        for date_str, neos in neo_dates.items():
            for neo in neos:
                if neo.get("is_potentially_hazardous_asteroid"):
                    hazardous.append(neo.get("name"))
                diam = neo.get("estimated_diameter", {}).get("kilometers", {})
                if diam:
                    diameters.append((diam.get("estimated_diameter_min", 0) +
                                      diam.get("estimated_diameter_max", 0)) / 2)

        stats: dict[str, Any] = {}
        if diameters:
            stats = {
                "count":        len(diameters),
                "mean_km":      round(statistics.mean(diameters), 4),
                "max_km":       round(max(diameters), 4),
                "min_km":       round(min(diameters), 4),
                "hazardous":    len(hazardous),
            }

    return {
        "chain":            "H3",
        "source":           "NASA NeoWs",
        "date_range":       f"{today} → {end}",
        "total_asteroids":  total_count,
        "hazardous_names":  hazardous[:10],
        "diameter_stats":   stats,
        "chain_log":        log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h3_ec2(days: int = 3) -> dict:
    result = await _h3_core(days)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h3_lambda(days: int = 3) -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h3_lambda", {"days": days})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h3_compare(days: int = 3) -> dict:
    ec2_r, lam_r = await asyncio.gather(_h3_core(days), _lambda_call("h3_lambda", {"days": days}))
    return _compare_result("H3", ec2_r, lam_r)


# ===========================================================================
# H4 — BioRxiv + arXiv cross-database search
# ===========================================================================

async def _h4_core(topic: str = "CRISPR gene editing") -> dict:
    log, t0 = [], _now_ms()

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        # arXiv leg
        s = _now_ms()
        ar = await client.get(ARXIV_SEARCH, params={"search_query": f"all:{topic}", "max_results": 5})
        ar.raise_for_status()
        import re
        arxiv_titles = re.findall(r"<title>([^<]+)</title>", ar.text)[1:6]
        _step(log, "arxiv_search", s, hits=len(arxiv_titles))

        # BioRxiv leg (recent 30 days)
        import datetime
        end_date   = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        bs = _now_ms()
        br = await client.get(
            f"{BIORXIV_BASE}/{start_date}/{end_date}/0",
            params={"format": "json"}
        )
        br.raise_for_status()
        biorxiv_data    = br.json()
        biorxiv_papers  = biorxiv_data.get("collection", [])[:5]
        biorxiv_titles  = [p.get("title", "") for p in biorxiv_papers]
        _step(log, "biorxiv_fetch", bs, hits=len(biorxiv_titles))

    return {
        "chain":            "H4",
        "source":           "BioRxiv + arXiv",
        "topic":            topic,
        "arxiv_titles":     arxiv_titles,
        "biorxiv_titles":   biorxiv_titles,
        "total_results":    len(arxiv_titles) + len(biorxiv_titles),
        "chain_log":        log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h4_ec2(topic: str = "CRISPR gene editing") -> dict:
    result = await _h4_core(topic)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h4_lambda(topic: str = "CRISPR gene editing") -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h4_lambda", {"topic": topic})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h4_compare(topic: str = "CRISPR gene editing") -> dict:
    ec2_r, lam_r = await asyncio.gather(_h4_core(topic), _lambda_call("h4_lambda", {"topic": topic}))
    return _compare_result("H4", ec2_r, lam_r)


# ===========================================================================
# H6 — DEX Paprika 5 chained GETs + OHLCV stats
# ===========================================================================

async def _h6_core(coin_id: str = "btc-bitcoin") -> dict:
    log, t0 = [], _now_ms()

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        # Step 1: coin info
        s = _now_ms()
        r1 = await client.get(f"{DEX_BASE}/coins/{coin_id}")
        r1.raise_for_status()
        coin_data = r1.json()
        _step(log, "coin_info", s, coin=coin_id)

        # Step 2: ticker
        s = _now_ms()
        r2 = await client.get(f"{DEX_BASE}/tickers/{coin_id}")
        r2.raise_for_status()
        ticker = r2.json()
        _step(log, "ticker", s)

        # Step 3: markets
        s = _now_ms()
        r3 = await client.get(f"{DEX_BASE}/coins/{coin_id}/markets")
        r3.raise_for_status()
        markets = r3.json()[:5]
        _step(log, "markets", s, count=len(markets))

        # Step 4: exchanges list
        s = _now_ms()
        r4 = await client.get(f"{DEX_BASE}/exchanges")
        r4.raise_for_status()
        exchanges = r4.json()[:5]
        _step(log, "exchanges", s, count=len(exchanges))

        # Step 5: global stats
        s = _now_ms()
        r5 = await client.get(f"{DEX_BASE}/global")
        r5.raise_for_status()
        global_stats = r5.json()
        _step(log, "global_stats", s)

    usd = ticker.get("quotes", {}).get("USD", {})
    ohlcv = {
        "price_usd":    usd.get("price"),
        "volume_24h":   usd.get("volume_24h"),
        "market_cap":   usd.get("market_cap"),
        "percent_1h":   usd.get("percent_change_1h"),
        "percent_24h":  usd.get("percent_change_24h"),
        "percent_7d":   usd.get("percent_change_7d"),
    }

    return {
        "chain":             "H6",
        "source":            "CoinPaprika",
        "coin":              coin_id,
        "name":              coin_data.get("name"),
        "ohlcv_stats":       ohlcv,
        "markets_sampled":   len(markets),
        "exchanges_sampled": len(exchanges),
        "global_market_cap": global_stats.get("market_cap_usd"),
        "chain_log":         log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h6_ec2(coin_id: str = "btc-bitcoin") -> dict:
    result = await _h6_core(coin_id)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h6_lambda(coin_id: str = "btc-bitcoin") -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h6_lambda", {"coin_id": coin_id})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h6_compare(coin_id: str = "btc-bitcoin") -> dict:
    ec2_r, lam_r = await asyncio.gather(_h6_core(coin_id), _lambda_call("h6_lambda", {"coin_id": coin_id}))
    return _compare_result("H6", ec2_r, lam_r)


# ===========================================================================
# H7 — NixOS package chain
# ===========================================================================

NIXOS_PACKAGES = ["python3", "nodejs", "rustc", "go", "ffmpeg"]

async def _h7_core() -> dict:
    log, t0 = [], _now_ms()
    results = []

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        for pkg in NIXOS_PACKAGES:
            s = _now_ms()
            body = {
                "query": {
                    "bool": {
                        "must": [{"match": {"package_attr_name": pkg}}]
                    }
                },
                "size": 3,
            }
            r = await client.post(
                NIXOS_BASE,
                json=body,
                headers={"Content-Type": "application/json"},
            )
            hits = r.json().get("hits", {}).get("hits", []) if r.status_code == 200 else []
            results.append({
                "package":  pkg,
                "hits":     len(hits),
                "versions": [h.get("_source", {}).get("package_version", "") for h in hits],
            })
            _step(log, f"nixos_{pkg}", s, hits=len(hits))

    return {
        "chain":             "H7",
        "source":            "NixOS Search",
        "packages_queried":  len(NIXOS_PACKAGES),
        "results":           results,
        "chain_log":         log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h7_ec2() -> dict:
    result = await _h7_core()
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h7_lambda() -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h7_lambda", {})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h7_compare() -> dict:
    ec2_r, lam_r = await asyncio.gather(_h7_core(), _lambda_call("h7_lambda", {}))
    return _compare_result("H7", ec2_r, lam_r)


# ===========================================================================
# H8 — Hacker News top stories + comments + stats
# ===========================================================================

async def _h8_core(stories: int = 25, deep: int = 3) -> dict:
    log, t0 = [], _now_ms()

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        s = _now_ms()
        r = await client.get(f"{HN_BASE}/topstories.json")
        r.raise_for_status()
        ids = r.json()[:stories]
        _step(log, "fetch_top_stories", s, stories=len(ids))

        story_data, scores, all_comments = [], [], []

        for i, sid in enumerate(ids[:deep]):
            s = _now_ms()
            sr = await client.get(f"{HN_BASE}/item/{sid}.json")
            sr.raise_for_status()
            item = sr.json()
            kids = item.get("kids", [])[:20]
            comments_fetched = []
            for kid in kids:
                cr = await client.get(f"{HN_BASE}/item/{kid}.json")
                if cr.status_code == 200:
                    comments_fetched.append(cr.json())
            story_data.append({
                "id":       sid,
                "title":    item.get("title", ""),
                "score":    item.get("score", 0),
                "comments": len(kids),
            })
            all_comments.extend(comments_fetched)
            _step(log, f"fetch_story_{i+1}", s, story_id=sid,
                  story_score=item.get("score", 0), comments_fetched=len(comments_fetched))

        # Fetch remaining story scores (lightweight)
        for sid in ids[deep:]:
            sr = await client.get(f"{HN_BASE}/item/{sid}.json")
            if sr.status_code == 200:
                scores.append(sr.json().get("score", 0))

    all_scores = [s["score"] for s in story_data] + scores
    stats: dict[str, Any] = {}
    if all_scores:
        stats = {
            "score_mean":   round(statistics.mean(all_scores), 2),
            "score_median": statistics.median(all_scores),
            "score_sum":    sum(all_scores),
            "score_min":    min(all_scores),
            "score_max":    max(all_scores),
            "type_mode":    "comment",
        }

    return {
        "chain":                   "H8",
        "source":                  "Hacker News",
        "stories_fetched":         stories,
        "stories_deep_fetched":    deep,
        "total_comments_analyzed": len(all_comments),
        "top_stories":             story_data,
        "stats":                   stats,
        "chain_log":               log,
        "total_duration_ms":       _now_ms() - t0,
    }


@mcp.tool()
async def h8_ec2(stories: int = 25, deep: int = 3) -> dict:
    result = await _h8_core(stories, deep)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h8_lambda(stories: int = 25, deep: int = 3) -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h8_lambda", {"stories": stories, "deep": deep})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h8_compare(stories: int = 25, deep: int = 3) -> dict:
    ec2_r, lam_r = await asyncio.gather(
        _h8_core(stories, deep),
        _lambda_call("h8_lambda", {"stories": stories, "deep": deep}),
    )
    return _compare_result("H8", ec2_r, lam_r)


# ===========================================================================
# H9 — Multi-database paper search + PDF fetch
# ===========================================================================

async def _h9_core(query: str = "transformer neural networks") -> dict:
    log, t0 = [], _now_ms()

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        # arXiv leg
        s = _now_ms()
        ar = await client.get(ARXIV_SEARCH, params={"search_query": f"all:{query}", "max_results": 3})
        ar.raise_for_status()
        import re
        arxiv_ids    = re.findall(r"<id>http://arxiv\.org/abs/([^<]+)</id>", ar.text)
        arxiv_ids    = [i.strip() for i in arxiv_ids][:3]
        arxiv_titles = re.findall(r"<title>([^<]+)</title>", ar.text)[1:4]
        _step(log, "arxiv_search", s, hits=len(arxiv_ids))

        # PDF fetch for first result
        pdf_bytes = 0
        if arxiv_ids:
            s = _now_ms()
            pr = await client.get(f"{ARXIV_PDF_BASE}/{arxiv_ids[0]}", follow_redirects=True)
            pdf_bytes = len(pr.content)
            _step(log, "pdf_fetch", s, paper_id=arxiv_ids[0], bytes=pdf_bytes)

        # Semantic Scholar leg
        s = _now_ms()
        ss_r = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": 3, "fields": "title,year,citationCount"},
        )
        ss_papers = ss_r.json().get("data", []) if ss_r.status_code == 200 else []
        _step(log, "semantic_scholar_search", s, hits=len(ss_papers))

    return {
        "chain":            "H9",
        "source":           "arXiv + Semantic Scholar",
        "query":            query,
        "arxiv_ids":        arxiv_ids,
        "arxiv_titles":     arxiv_titles,
        "pdf_bytes":        pdf_bytes,
        "semantic_scholar": [
            {"title": p.get("title"), "year": p.get("year"), "citations": p.get("citationCount")}
            for p in ss_papers
        ],
        "chain_log":         log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h9_ec2(query: str = "transformer neural networks") -> dict:
    result = await _h9_core(query)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h9_lambda(query: str = "transformer neural networks") -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h9_lambda", {"query": query})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h9_compare(query: str = "transformer neural networks") -> dict:
    ec2_r, lam_r = await asyncio.gather(
        _h9_core(query), _lambda_call("h9_lambda", {"query": query})
    )
    return _compare_result("H9", ec2_r, lam_r)


# ===========================================================================
# H10 — BioRxiv + NixOS cross-domain
# ===========================================================================

async def _h10_core(bio_topic: str = "mRNA vaccines", nix_package: str = "python3") -> dict:
    log, t0 = [], _now_ms()

    async with httpx.AsyncClient(timeout=EC2_TIMEOUT) as client:
        # BioRxiv leg
        import datetime
        end_date   = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        s = _now_ms()
        br = await client.get(
            f"{BIORXIV_BASE}/{start_date}/{end_date}/0",
            params={"format": "json"}
        )
        br.raise_for_status()
        bio_papers = br.json().get("collection", [])[:5]
        _step(log, "biorxiv_fetch", s, hits=len(bio_papers))

        # NixOS leg
        s = _now_ms()
        body = {"query": {"bool": {"must": [{"match": {"package_attr_name": nix_package}}]}}, "size": 3}
        nr = await client.post(NIXOS_BASE, json=body, headers={"Content-Type": "application/json"})
        nix_hits = nr.json().get("hits", {}).get("hits", []) if nr.status_code == 200 else []
        _step(log, "nixos_search", s, hits=len(nix_hits))

    return {
        "chain":            "H10",
        "source":           "BioRxiv + NixOS",
        "bio_topic":        bio_topic,
        "nix_package":      nix_package,
        "bio_papers":       [{"title": p.get("title"), "doi": p.get("doi")} for p in bio_papers],
        "nix_versions":     [h.get("_source", {}).get("package_version", "") for h in nix_hits],
        "chain_log":        log,
        "total_duration_ms": _now_ms() - t0,
    }


@mcp.tool()
async def h10_ec2(bio_topic: str = "mRNA vaccines", nix_package: str = "python3") -> dict:
    result = await _h10_core(bio_topic, nix_package)
    result["backend"] = "ec2"
    return result


@mcp.tool()
async def h10_lambda(bio_topic: str = "mRNA vaccines", nix_package: str = "python3") -> dict:
    t0 = _now_ms()
    result = await _lambda_call("h10_lambda", {"bio_topic": bio_topic, "nix_package": nix_package})
    result["backend"]     = "lambda"
    result["duration_ms"] = _now_ms() - t0
    return result


@mcp.tool()
async def h10_compare(bio_topic: str = "mRNA vaccines", nix_package: str = "python3") -> dict:
    ec2_r, lam_r = await asyncio.gather(
        _h10_core(bio_topic, nix_package),
        _lambda_call("h10_lambda", {"bio_topic": bio_topic, "nix_package": nix_package}),
    )
    return _compare_result("H10", ec2_r, lam_r)


# ===========================================================================
# compare_all_heavy — run all 9 compare tools concurrently
# ===========================================================================

@mcp.tool()
async def compare_all_heavy() -> dict:
    t0 = _now_ms()

    results = await asyncio.gather(
        h1_compare(),
        h2_compare(),
        h3_compare(),
        h4_compare(),
        h6_compare(),
        h7_compare(),
        h8_compare(),
        h9_compare(),
        h10_compare(),
        return_exceptions=True,
    )

    chains = ["H1", "H2", "H3", "H4", "H6", "H7", "H8", "H9", "H10"]
    comparison: dict[str, Any] = {}
    for chain, r in zip(chains, results):
        if isinstance(r, Exception):
            comparison[chain] = {"error": str(r)}
        else:
            comparison[chain] = {
                "ec2_duration_ms":    r["ec2_duration_ms"],
                "lambda_duration_ms": r["lambda_duration_ms"],
                "faster":             r["faster"],
                "difference_ms":      r["difference_ms"],
            }

    ec2_wins    = sum(1 for v in comparison.values() if v.get("faster") == "ec2")
    lambda_wins = sum(1 for v in comparison.values() if v.get("faster") == "lambda")

    return {
        "request_id":        str(uuid.uuid4()),
        "status":            "success",
        "workloads_compared": len(chains),
        "comparison":        comparison,
        "summary": {
            "ec2_wins":    ec2_wins,
            "lambda_wins": lambda_wins,
        },
        "duration_ms": _now_ms() - t0,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()