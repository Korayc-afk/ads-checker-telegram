import os
import sys
import httpx
from dotenv import load_dotenv
from datetime import datetime
import asyncio

# .env dosyasındaki değişkenleri yükler
load_dotenv()

# Proje ana dizinini Python'un import yoluna ekler
# Bu, Render (ve systemd) gibi ortamlarda app.models ve app.serp'in bulunmasını sağlar
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import get_due_jobs, update_job_next_run, init_db
from app.serp import check_ads

# --- Ortam Değişkenleri ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NOTIFICATION_GROUP_ID = os.getenv("TELEGRAM_NOTIFICATION_GROUP_ID")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_notification(chat_id: str, message: str):
    """Verilen sohbet ID'sine Telegram üzerinden düz metin mesaj gönderir."""
    payload = {'chat_id': chat_id, 'text': message}
    try:
        with httpx.Client() as client:
            # İsteği 10 saniye zaman aşımı ile gönder
            r = client.post(API_URL, json=payload, timeout=10)
            r.raise_for_status() # Hata varsa (4xx, 5xx) exception fırlat
        print(f"-> Bildirim başarıyla gönderildi: {chat_id}")
    except Exception as e:
        print(f"-> HATA: Bildirim gönderilemedi: {chat_id}, Hata: {e}")

async def run_job_once():
    """
    Bu fonksiyon SADECE BİR KEZ çalışır ve kapanır.
    Render'daki harici Cron Job tarafından tetiklenmek için tasarlanmıştır.
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cron Job tetiklendi. Zamanı gelmiş görevler aranıyor...")
    
    # Her çalıştığında veritabanı bağlantısını ve tabloları garantiler
    init_db()
    
    if not NOTIFICATION_GROUP_ID:
        print("UYARI: .env dosyasında TELEGRAM_NOTIFICATION_GROUP_ID bulunamadı.")

    due_jobs = []
    try:
        # Veritabanından zamanı gelmiş ve aktif olan görevleri çek
        due_jobs = get_due_jobs()
        if due_jobs:
            print(f"-> {len(due_jobs)} adet çalışacak görev bulundu.")
        else:
            print("-> Çalıştırılacak zamanı gelmiş görev bulunamadı.")
            
    except Exception as e:
        print(f"Veritabanından görevler alınırken hata oluştu: {e}")
        return # Görev alınamazsa devam etmenin anlamı yok

    # Bulunan her görev için döngü başlat
    for job in due_jobs:
        # --- Hata Yakalama Döngünün İçinde ---
        # Bu sayede bir görev hata alsa bile, diğer görevler çalışmaya devam eder.
        try:
            print(f"--> Görev çalıştırılıyor: '{job.query}'")
            
            # app/serp.py içindeki kademeli arama fonksiyonunu çağır
            result = await check_ads(q=job.query, device=job.device, location=job.location)
            
            # --- Sadece Reklam Varsa Bildirim Gönder ---
            if result.get("has_ads"):
                print(f"--> REKLAM BULUNDU! Bildirim hazırlanıyor...")
                
                # Konum bilgisi ekle (eğer varsa)
                location_info = f" ({result.get('location_used', job.location)})" if result.get('location_used', job.location) else ""
                
                # Bildirim mesajının başlığı
                message_header = (f"🔔 Zamanlanmış Uyarı: Reklam Bulundu!\n\n"
                                  f"Sorgu: {job.query}{location_info}\n"
                                  f"Reklam Sayısı: {result.get('ads_count', 0)} adet")
                
                # Reklam detaylarını (linkler) mesaja ekle
                ad_lines = []
                ad_details = result.get("ads", [])
                if ad_details:
                    ad_lines.append("\n--- Bulunan Reklamlar ---")
                    for i, ad in enumerate(ad_details, start=1):
                        title = ad.get("title", "Başlık Yok")
                        url = ad.get("url", "URL Yok")
                        ad_lines.append(f"{i}) {title}\n   └ {url}")
                
                message = message_header + "\n" + "\n\n".join(ad_lines)

                # Hedef ID'yi belirle (göreve özel ID yoksa, varsayılan grup ID'sini kullan)
                target_chat_id = job.telegram_user_id or NOTIFICATION_GROUP_ID
                if target_chat_id:
                    send_telegram_notification(target_chat_id, message)
            else:
                print(f"--> Reklam bulunamadı, bildirim gönderilmiyor (Sessiz Mod).")
            
            # Görevi başarıyla tamamlandı olarak işaretle ve bir sonraki çalışma zamanını ayarla
            update_job_next_run(job.id, job.interval_minutes)
            print(f"--> Görev tamamlandı ve güncellendi: '{job.query}'")

        except Exception as e:
            # Bir görev hata alırsa, bunu logla ama döngüyü kırma
            print(f"!!! HATA: '{job.query}' görevi çalıştırılırken bir hata oluştu: {e}")
            print(f"!!! Diğer görevlere devam ediliyor...")
        # --- Hata Yakalama Bitişi ---
            
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cron Job tamamlandı.")

if __name__ == "__main__":
    # Bu script doğrudan çalıştırıldığında (Render Cron Job gibi)
    # run_job_once fonksiyonunu çalıştırır ve biter.
    asyncio.run(run_job_once())