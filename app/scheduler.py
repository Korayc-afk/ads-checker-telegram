import os
import sys
import httpx
from dotenv import load_dotenv
from datetime import datetime
import asyncio

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Modelleri ve SerpAPI'yi import et
from app.models import get_due_jobs, update_job_next_run, init_db
from app.serp import check_ads

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NOTIFICATION_GROUP_ID = os.getenv("TELEGRAM_NOTIFICATION_GROUP_ID")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Istanbul, Turkey")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_notification(chat_id: str, message: str):
    # (Bu fonksiyon bir önceki cevaptakiyle aynı)
    payload = {'chat_id': chat_id, 'text': message, 'disable_web_page_preview': True}
    try:
        with httpx.Client() as client:
            r = client.post(API_URL, json=payload, timeout=10)
            if r.status_code != 200:
                print("-> TG API Error:", r.status_code, r.text)
            r.raise_for_status()
        print(f"-> Bildirim başarıyla gönderildi: {chat_id}")
    except Exception as e:
        print(f"-> HATA: Bildirim gönderilemedi: {chat_id}, Hata: {e}")

async def run_job_once():
    """
    Bu fonksiyon SADECE BİR KEZ çalışır ve kapanır.
    Cron Job tarafından tetiklenmek için tasarlanmıştır.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cron Job tetiklendi. Zamanı gelmiş görevler aranıyor...")
    
    # Veritabanını başlat
    init_db()
    
    if not NOTIFICATION_GROUP_ID:
        print("UYARI: .env dosyasında TELEGRAM_NOTIFICATION_GROUP_ID bulunamadı.")

    try:
        due_jobs = get_due_jobs()
        if due_jobs:
            print(f"-> {len(due_jobs)} adet çalışacak görev bulundu.")

            for job in due_jobs:
                print(f"--> Görev çalıştırılıyor: '{job.query}'")
                # Lokasyon boşsa default kullan
                loc = (job.location or "").strip() or DEFAULT_LOCATION
                result = await check_ads(q=job.query, device=job.device, location=loc)
                
                if result.get("has_ads"):
                    print(f"--> REKLAM BULUNDU! Bildirim hazırlanıyor...")
                    # ... (Bildirim mesajı oluşturma kodu aynı) ...
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
        else:
            print("-> Çalıştırılacak zamanı gelmiş görev bulunamadı.")

    except Exception as e:
        print(f"Cron Job çalışırken bir hata oluştu: {e}")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cron Job tamamlandı.")

if __name__ == "__main__":
    # Script'i bir kez çalıştırıp bitir
    asyncio.run(run_job_once())
