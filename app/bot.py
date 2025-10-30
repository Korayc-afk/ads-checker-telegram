import os
import sys
import httpx
import datetime as dt
from dotenv import load_dotenv

load_dotenv()

# Proje yolunu ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- GÜNCELLENDİ: v3 için doğru importlar ---
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
# --- BİTTİ ---

# --- Ortam Değişkenleri ve Sabitler ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN .env dosyasında eksik!")

# Render'da, bot ve API aynı yerde çalışacak.
# API_BASE'i .env'den al, yoksa Render'ın varsayılanını kullan
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:10000") 

DEFAULT_GL = os.getenv("DEFAULT_GL", "tr")
DEFAULT_HL = os.getenv("DEFAULT_HL", "tr")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)  # v2'de bot burada verilir

USER_DEVICE = {}
USER_LOCATION = {}

def get_device(uid: int) -> str:
    return USER_DEVICE.get(uid, "desktop")

def get_location(uid: int) -> str:
    return USER_LOCATION.get(uid)

# --- GÜNCELLENDİ: v3 Komut formatı ---
@dp.message(Command("start", "help"))
async def help_command(m: types.Message):
    await m.reply(
        "Merhaba! Google'da reklam kontrolü yaparım.\n\n"
        "Komutlar:\n"
        "• `/mobile on|off` → Cihaz modunu değiştirir.\n"
        "• `/mode` → Aktif cihaz modunu gösterir.\n"
        "• `/location [Şehir, Ülke]` → Arama konumunu ayarlar.\n"
        "• `/location` → Konumu sıfırlar.\n\n"
        "Örnek Kullanım:\n"
        "`/location Istanbul, Turkey`\n"
        "`kredi kartı`"
    )

# --- GÜNCELLENDİ: v3 Komut formatı ---
@dp.message(Command("mobile"))
async def set_mobile_mode(m: types.Message):
    parts = m.text.split()
    if len(parts) >= 2 and parts[1].lower() in ("on", "off"):
        mode = "mobile" if parts[1].lower() == "on" else "desktop"
        USER_DEVICE[m.from_user.id] = mode
        await m.reply(f"✅ Arama modu `{mode}` olarak ayarlandı.")
    else:
        await m.reply("Kullanım: `/mobile on` veya `/mobile off`")

# --- GÜNCELLENDİ: v3 Komut formatı ---
@dp.message(Command("mode"))
async def get_current_mode(m: types.Message):
    current_mode = get_device(m.from_user.id)
    await m.reply(f"ℹ️ Cihaz modu: `{current_mode}`")

# --- GÜNCELLENDİ: v3 Komut formatı ---
@dp.message(Command("location"))
async def set_location(m: types.Message):
    # .get_args() v2'de kaldı, v3'te manuel ayıklama daha garanti
    location_query = m.text.replace("/location", "").strip()
    if location_query:
        USER_LOCATION[m.from_user.id] = location_query
        await m.reply(f"✅ Konum başarıyla `{location_query}` olarak ayarlandı.")
    else:
        if m.from_user.id in USER_LOCATION:
            del USER_LOCATION[m.from_user.id]
        await m.reply("ℹ️ Konum sıfırlandı. Artık genel arama yapılacak.")

# --- GÜNCELLENDİ: v3 "diğer tüm mesajlar" formatı ---
@dp.message()
async def run_query(m: types.Message):
    # Komutları ayıkla, eğer mesaj bir komutla başlıyorsa işlem yapma
    if m.text and m.text.startswith("/"):
        return

    query = m.text.strip()
    if not query:
        return await m.reply("Lütfen boş mesaj göndermeyin.")

    dev = get_device(m.from_user.id)
    loc = get_location(m.from_user.id)
    
    location_info = f" ({loc})" if loc else ""
    wait_message = await m.reply(f"⏳ `{query}` için reklamlar aranıyor...\nCihaz: `{dev}`{location_info}")

    payload = {"query": query, "device": dev, "gl": DEFAULT_GL, "hl": DEFAULT_HL}
    if loc:
        payload["location"] = loc

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{API_BASE}/v1/check", json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return await wait_message.edit_text(f"🚨 Hata: API servisine bağlanılamadı.\nDetay: {e}")

    if data.get("has_ads"):
        ads = data.get("ads") or []
        lines = []
        for ad in ads:
            pos, title, url = ad.get("pos", ""), (ad.get("title") or "").strip(), (ad.get("url") or "").strip()
            display_url = url.replace("https://", "").replace("http://", "")
            if title and display_url:
                lines.append(f"{pos}) {title}\n   └ {display_url}")
            elif display_url:
                lines.append(f"{pos}) {display_url}")
        
        ads_count = data.get("ads_count", 0)
        head = f"🔔 Reklam Bulundu ({ads_count} adet)\nSorgu: `{query}` ({dev}){location_info}"
        body = "\n\n".join(lines) if lines else ""
        await wait_message.edit_text(head + ("\n\n" + body if body else ""), disable_web_page_preview=True)
    else:
        await wait_message.edit_text(f"✅ Reklam Yok\nSorgu: `{query}` ({dev})")