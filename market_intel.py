
import os, json
import requests

def fetch_and_analyze():
    url=os.environ.get("MARKET_API_URL","").strip()
    if not url:
        return {
            "source_status":"DEMO / API not configured",
            "summary":"No authorized market-data API configured. Demo mode keeps the prototype functional.",
            "competitiveness_score":50,
            "recommendation":"Configure an approved market-data API before using this as an operational intelligence source.",
            "raw_json":"{}",
        }
    try:
        r=requests.get(url,timeout=15)
        r.raise_for_status()
        data=r.json()
        # Generic adapter: a real API adapter should map its own fields here.
        return {
            "source_status":"LIVE CONFIGURED API",
            "summary":str(data.get("summary") or data.get("message") or "Market data received."),
            "competitiveness_score":float(data.get("competitiveness_score",50)),
            "recommendation":str(data.get("recommendation") or "Review market signals with human decision-maker."),
            "raw_json":json.dumps(data,ensure_ascii=False)[:10000],
        }
    except Exception as e:
        return {
            "source_status":"API ERROR — fallback demo",
            "summary":"Market API unavailable; no unsupported claim was generated.",
            "competitiveness_score":50,
            "recommendation":"Check API connectivity and continue with human review.",
            "raw_json":json.dumps({"error":str(e)}),
        }
