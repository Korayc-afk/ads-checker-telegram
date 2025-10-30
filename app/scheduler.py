import os
import sys
import time
import httpx
from dotenv import load_dotenv
from datetime import datetime
import asyncio

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import get_due_jobs, update_job_next_run, init_db, engine, Session, select, ScheduledJob, datetime, timedelta # Modelleri doğru import et
from app.serp import check_ads

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NOTIFICATION_GROUP_ID = os.getenv("TELEGRAM_NOTIFICATION_GROUP_ID")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_notification(chat_id: str, message: str):
    payload = {'chat_id': chat_id, 'text': message}
    try:
        with httpx.Client() as client:
            r = client.post(API_URL, json=payload, timeout=10)
            r.raise_for_status()
        print(f"-> Bildirim başarıyla gönderildi: {chat_id}")
    except Exception as e:
        print(f"-> HATA: Bildirim gönderilemedi: {chat_id}, Hata: {e}")

async def run_scheduler():
    print("Zamanlayıcı v2.0 (Sessiz Mod) başlatıldı... Her 60 saniyede bir görevler kontrol edilecek.")
    if not NOTIFICATION_GROUP_ID:
        print("UYARI: .env dosyasında TELEGRAM_NOTIFICATION_GROUP_ID bulunamadı.")
    
    # Veritabanını başlat
    init_db()

    while True:
        try:
            due_jobs = get_due_jobs()
            if due_jobs:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(due_jobs)} adet çalışacak görev bulundu.")

            for job in due_jobs:
                print(f"--> Görev çalıştırılıyor: '{job.query}'")
                result = await check_ads(q=job.query, device=job.device, location=job.location)
                
                if result.get("has_ads"):
                    print(f"--> REKLAM BULUNDU! Bildirim hazırlanıyor...")
                    location_info = f" ({result.get('location_used', job.location)})" if result.get('location_used', job.location) else ""
                    
                    message_header = (f"🔔 Zamanlanmış Uyarı: Reklam Bulundu!\n\n"
                                      f"Sorgu: {job.query}{location_info}\n"
                                      f"Reklam Sayısı: {result.get('ads_count', 0)} adet")
                    
                    ad_lines = []
                    ad_details = result.get("ads", [])
                    if ad_details:
                        ad_lines.append("\n--- Bulunan Reklamlar ---")
                        for i, ad in enumerate(ad_details, start=1):
                            title = ad.get("title", "Başlık Yok")
                            url = ad.get("url", "URL Yok")
                            ad_lines.append(f"{i}) {title}\n   └ {url}")
                    
                    message = message_header + "\n" + "\n\n".join(ad_lines)

                    target_chat_id = job.telegram_user_id or NOTIFICATION_GROUP_ID
                    if target_chat_id:
                        send_telegram_notification(target_chat_id, message)
                else:
                    print(f"--> Reklam bulunamadı, bildirim gönderilmiyor.")
                
                update_job_next_run(job.id, job.interval_minutes)
                print(f"--> Görev tamamlandı ve güncellendi: '{job.query}'")

        except Exception as e:
            print(f"Zamanlayıcı döngüsünde bir hata oluştu: {e}")
        
        time.sleep(60)

if __name__ == "__main__":
    asyncio.run(run_scheduler())