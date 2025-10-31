from dotenv import load_dotenv
load_dotenv()

import os
import time
import httpx
from urllib.parse import urlparse
from typing import Optional, List, Dict

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
GOOGLE_DOMAIN = os.getenv("GOOGLE_DOMAIN", "google.com.tr")
DEFAULT_GL = os.getenv("DEFAULT_GL", "tr")
DEFAULT_HL = os.getenv("DEFAULT_HL", "tr")

def _host(u: str) -> str:
    try:
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return u

async def _make_serpapi_request(params: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://serpapi.com/search", params=params)
        r.raise_for_status()
        return r.json()

async def check_ads(q: str, gl: str = DEFAULT_GL, hl: str = DEFAULT_HL, device: str = "desktop", location: Optional[str] = None):
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY .env dosyasında eksik!")

    base_params = {
        "engine": "google", "q": q, "gl": gl, "hl": hl,
        "google_domain": GOOGLE_DOMAIN, "api_key": SERPAPI_KEY,
        "device": "mobile" if device == "mobile" else "desktop", "num": 10,
    }

    search_attempts: List[Dict] = []
    
    # Adım 1: En geniş arama. Konumsuz, genel Türkiye araması (VPN taklidi).
    search_attempts.append({"params": {}, "name": "Genel Türkiye (Konumsuz)"})

    # Adım 2: Şehir bazlı arama (eğer kullanıcı bir konum girdiyse).
    if location:
        clean_location = location.split('/')[0].strip() + ", Turkey"
        search_attempts.append({"params": {"location": clean_location}, "name": f"Şehir Bazlı: {clean_location}"})

    # Adım 3 (Nadir durumlar için): Kullanıcının girdiği ham veriyi de deneyelim.
    if location and clean_location != location:
         search_attempts.append({"params": {"location": location}, "name": f"Ham Konum: {location}"})
    
    unique_attempts = []
    seen = set()
    for attempt in search_attempts:
        key = str(attempt["params"])
        if key not in seen:
            unique_attempts.append(attempt)
            seen.add(key)

    t0 = time.perf_counter()
    final_data = None
    location_used = location
    
    for attempt in unique_attempts:
        print(f"-> Arama denemesi yapılıyor... Strateji: {attempt['name']}")
        current_params = base_params.copy()
        current_params.update(attempt["params"])
        
        data = await _make_serpapi_request(current_params)
        raw_ads = data.get("ads") or data.get("ad_results") or []

        if raw_ads:
            print(f"--> REKLAM BULUNDU! Strateji: {attempt['name']}")
            final_data = data
            location_used = attempt["params"].get("location")
            break 
        else:
            print(f"--> Reklam bulunamadı. Sonraki strateji denenecek...")
    
    if not final_data:
        final_data = data
    
    latency_ms = int((time.perf_counter() - t0) * 1000)
    final_raw_ads = final_data.get("ads") or final_data.get("ad_results") or []
    has_ads = len(final_raw_ads) > 0

    details = []
    for i, ad in enumerate(final_raw_ads, start=1):
        title = ad.get("title") or ad.get("headline") or ""
        link = ad.get("link") or ad.get("displayed_link") or ad.get("tracking_link") or ""
        details.append({"pos": i, "title": title, "url": link, "domain": _host(link)})

    types = []
    if has_ads:
        types.append("search")
    if final_data.get("shopping_results") or final_data.get("inline_shopping_results"):
        types.append("shopping")

    return {
        "query": q,
        "has_ads": has_ads,
        "ads_count": len(final_raw_ads),
        "types": types,
        "latency_ms": latency_ms,
        "gl": gl,
        "hl": hl,
        "device": device,
        "location_used": location_used,
        "ads": details,
    }