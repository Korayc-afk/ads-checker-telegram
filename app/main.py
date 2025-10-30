import os
import sys
import asyncio
from typing import Literal, Optional, List
from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.serp import check_ads
from app.models import init_db, add_log, list_logs, SearchLog, ScheduledJob, add_job, list_all_jobs, delete_job_by_id
from app.bot import dp, bot # Bot dosyamızdan import ediyoruz

# --- YENİ KISIM: Zamanlayıcı mantığını import et ---
# app/scheduler.py dosyasındaki "run_job_once" fonksiyonunu çek
from app.scheduler import run_job_once
# --- BİTTİ ---

DEFAULT_GL = os.getenv("DEFAULT_GL", "tr")
DEFAULT_HL = os.getenv("DEFAULT_HL", "tr")
# --- YENİ KISIM: Cron için gizli şifre ---
CRON_SECRET = os.getenv("CRON_SECRET")
# --- BİTTİ ---

app = FastAPI(title="Ads Checker API")

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.on_event("startup")
async def on_startup():
    init_db()
    print("Web API'si başlatıldı, Telegram Botu arka planda başlatılıyor...")
    asyncio.create_task(dp.start_polling())

# --- YENİ KISIM: Gizli Şifre Kontrolcüsü ---
async def check_cron_secret(secret: Optional[str] = Query(None)):
    """Harici cron servisinin gizli şifreyi bilip bilmediğini kontrol eder."""
    if not CRON_SECRET:
        print("UYARI: CRON_SECRET ayarlanmamış. Zamanlayıcı trigger'ı güvensiz.")
        return # Ayarlanmamışsa bile çalışsın ama uyarsın
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Geçersiz cron secret")
    return
# --- BİTTİ ---

@app.get("/health")
async def health():
    return {"ok": True}

# --- YENİ KISIM: Harici Cron Tetikleyici Endpoint'i ---
@app.get("/v1/trigger-scheduler")
async def trigger_scheduler(secret_check: None = Depends(check_cron_secret)):
    """
    Harici bir cron job servisi tarafından (örn: cron-job.org) tetiklenir.
    Zamanı gelmiş görevleri bir kez çalıştırır.
    """
    print("Harici cron trigger'ı alındı, zamanlayıcı çalıştırılıyor...")
    try:
        # Zamanlayıcı mantığını arka planda çalıştır, 'await' etme ki 
        # cron servisi uzun süre beklemesin.
        asyncio.create_task(run_job_once())
        return {"status": "success", "message": "Zamanlayıcı tetiklendi, görevler arka planda işleniyor."}
    except Exception as e:
        print(f"Harici cron trigger hatası: {e}")
        raise HTTPException(status_code=500, detail="Zamanlayıcıyı tetiklerken hata oluştu.")
# --- BİTTİ ---

# ... (Kalan tüm API endpoint'leri (/v1/check, /v1/jobs vb.) AYNI KALIYOR) ...
class CheckRequest(BaseModel):
    query: str = Field(..., min_length=1)
    device: Literal["desktop", "mobile"] = "desktop"
    gl: str = DEFAULT_GL
    hl: str = DEFAULT_HL
    location: Optional[str] = None
@app.post("/v1/check")
async def check(req: CheckRequest):
    try:
        res = await check_ads(req.query, gl=req.gl, hl=req.hl, device=req.device, location=req.location)
    except Exception as e:
        raise HTTPException(502, f"Upstream error: {e}")
    entry = SearchLog(query=res["query"], has_ads=res["has_ads"], ads_count=res["ads_count"], types=",".join(res["types"]), device=res["device"], gl=res["gl"], hl=res["hl"], latency_ms=res["latency_ms"])
    add_log(entry)
    return res
class JobCreateRequest(BaseModel):
    query: str
    interval_minutes: int
    location: Optional[str] = None
    device: Literal["desktop", "mobile"] = "desktop"
    telegram_user_id: Optional[str] = None
@app.post("/v1/jobs", response_model=ScheduledJob, status_code=201)
async def create_job(req: JobCreateRequest):
    job = ScheduledJob(
        query=req.query,
        interval_minutes=req.interval_minutes,
        location=req.location,
        device=req.device,
        telegram_user_id=req.telegram_user_id,
        next_run_at=datetime.utcnow() + timedelta(minutes=req.interval_minutes)
    )
    created_job = add_job(job)
    return created_job
@app.get("/v1/jobs", response_model=List[ScheduledJob])
async def get_all_jobs():
    return list_all_jobs()
@app.delete("/v1/jobs/{job_id}", status_code=204)
async def delete_job(job_id: int):
    success = delete_job_by_id(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return
@app.get("/", include_in_schema=False)
async def read_index():
    return FileResponse(os.path.join(static_dir, 'index.html'))