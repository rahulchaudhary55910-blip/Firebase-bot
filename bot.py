import json
import os
import re
import time
import base64
import zipfile
import tempfile
import requests
from flask import Flask
import threading
import functools

try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

print = functools.partial(print, flush=True)

# ================= APNA CONFIG YAHAN SET HAI =================
BOT_TOKEN = "8632363521:AAHmUpYvXtViGysiVRkhXiII_2SxcBnorIw"
ADMIN_CHAT_ID = "6755426755"
TIMEOUT = 10
# ==============================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Firebase Extractor Bot is active and running 24x7 with Ultimate Parser!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def self_ping():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:10000")
    while True:
        try:
            requests.get(render_url, timeout=10)
        except Exception:
            pass
        time.sleep(300)

def send_keyboard_message(session, token, chat_id, text, inline_keyboard):
    try:
        r = session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={
                             "chat_id": chat_id,
                             "text": text,
                             "reply_markup": {"inline_keyboard": inline_keyboard},
                             "parse_mode": "Markdown"
                         }, timeout=15)
        return r.status_code == 200
    except Exception:
        return False

def answer_callback(session, token, callback_query_id, text=""):
    try:
        session.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                     json={"callback_query_id": callback_query_id, "text": text}, timeout=10)
    except Exception:
        pass

# --- ULTIMATE LINK PARSER (Handles share, s, m, zeniths & Double Base64) ---
def parse_links_bulk(text):
    lines = text.strip().split('\n')
    parsed_results = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Check for any parameter containing base64 data (?share=, ?s=, ?m=, ?zeniths=, etc.)
        param_match = re.search(r'[?&](?:share|s|m|zeniths)=([A-Za-z0-9+/=_-]+)', line)
        if param_match:
            try:
                raw = param_match.group(1).replace('-', '+').replace('_', '/')
                raw += '=' * (-len(raw) % 4)
                decoded_bytes = base64.b64decode(raw)
                decoded = decoded_bytes.decode('utf-8', errors='ignore')
                
                # Double decoding check (Agar decode karne ke baad bhi base64 ya text ho)
                if not decoded.startswith(('{', '[')) and re.match(r'^[A-Za-z0-9+/=]+$', decoded.strip()):
                    try:
                        decoded = base64.b64decode(decoded.strip()).decode('utf-8', errors='ignore')
                    except:
                        pass

                try:
                    data = json.loads(decoded)
                except:
                    # Agar JSON direct load na ho, toh regex se Firebase URL nikal lo
                    urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.firebaseio\.com', decoded)
                    for u in urls:
                        pm = re.search(r'https://([^.]+)', u)
                        p_name = pm.group(1) if pm else "unknown"
                        parsed_results.append((u.rstrip('/'), "dummy", p_name))
                    continue

                # Agar JSON ek list hai
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            p_url = item.get('url', '').rstrip('/')
                            p_key = item.get('key', 'dummy') or "dummy"
                            if p_url:
                                if not p_url.startswith("http"):
                                    p_url = "https://" + p_url
                                pm = re.search(r'https://([^.]+)', p_url)
                                p_name = pm.group(1) if pm else "unknown"
                                parsed_results.append((p_url, p_key, p_name))
                    continue
                
                # Agar JSON ek dictionary hai
                elif isinstance(data, dict):
                    if "panels" in data:
                        for panel in data["panels"]:
                            if isinstance(panel, dict):
                                p_url = panel.get("url", "").rstrip('/')
                                p_key = panel.get("key", "dummy") or "dummy"
                                if p_url:
                                    if not p_url.startswith("http"):
                                        p_url = "https://" + p_url
                                    pm = re.search(r'https://([^.]+)', p_url)
                                    p_name = pm.group(1) if pm else "unknown"
                                    parsed_results.append((p_url, p_key, p_name))
                        continue
                    elif "url" in data:
                        url = data.get('url', '').rstrip('/')
                        key = data.get('key', 'dummy') or "dummy"
                        if url:
                            pm = re.search(r'https://([^.]+)', url)
                            p_name = pm.group(1) if pm else "unknown"
                            parsed_results.append((url, key, p_name))
                            continue
            except Exception as e:
                print(f"Parser Decode Error: {e}")

        # Separator format (URL|||KEY)
        if '|||' in line:
            parts = line.split('|||')
            url = parts[0].strip()
            key = parts[1].strip() if len(parts) > 1 else "dummy"
            if url:
                url = url.rstrip('/')
                if not url.startswith("http"):
                    url = "https://" + url
                pm = re.search(r'https://([^.]+)', url)
                p_name = pm.group(1) if pm else "unknown"
                parsed_results.append((url, key, p_name))
                continue

        # Plain URL fallback
        url = line.strip()
        if url.startswith("http") or "firebaseio.com" in url:
            url = url.rstrip('/')
            pm = re.search(r'https://([^.]+)', url)
            p_name = pm.group(1) if pm else "unknown"
            parsed_results.append((url, "dummy", p_name))

    return parsed_results

# --- APK PARSER ---
def extract_firebase_from_apk(apk_path):
    extracted_urls = []
    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            for filename in z.namelist():
                if filename.endswith('.dex') or filename.endswith('.json') or 'res/raw' in filename:
                    try:
                        content = z.read(filename)
                        urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.firebaseio\.com', str(content))
                        for u in urls:
                            if u not in extracted_urls:
                                extracted_urls.append(u)
                    except:
                        continue
    except Exception as e:
        print(f"APK Parse Error: {e}")
    return extracted_urls

# --- FIREBASE CHECKER ---
def check_firebase(url, key):
    result = {
        "url": url,
        "key": key,
        "panel_name": "unknown",
        "status": "unknown",
        "total_devices": 0,
        "online_devices": 0,
        "error": None
    }

    pm = re.search(r'https://([^.]+)', url)
    if pm:
        result["panel_name"] = pm.group(1)

    clients_url = f"{url}/clients.json"
    if key and key != "dummy":
        clients_url += f"?auth={key}"

    try:
        res = requests.get(clients_url, timeout=TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, dict):
                result["status"] = "live"
                result["total_devices"] = len(data)
                result["online_devices"] = sum(
                    1 for d in data.values() 
                    if isinstance(d, dict) and (d.get("status") or d.get("online") or d.get("lastSeen"))
                )
                return result
            else:
                result["status"] = "empty"
                return result
        elif res.status_code == 401:
            if key and key != "dummy":
                try:
                    res2 = requests.get(f"{url}/clients.json", timeout=TIMEOUT)
                    if res2.status_code == 200:
                        data = res2.json()
                        if data and isinstance(data, dict):
                            result["status"] = "live_no_auth"
                            result["total_devices"] = len(data)
                            result["online_devices"] = sum(
                                1 for d in data.values() 
                                if isinstance(d, dict) and (d.get("status") or d.get("online") or d.get("lastSeen"))
                            )
                            return result
                except:
                    pass
            result["status"] = "auth_error"
            return result
        else:
            result["status"] = f"http_{res.status_code}"
            return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:100]
        return result

# --- TELEGRAM LISTENER ---
def telegram_listener(token, session):
    offset = 0
    print("[Bot] Ultimate Firebase Extractor started.")
    
    waiting_for_panel = {}

    while True:
        try:
            r = session.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        
                        callback = update.get("callback_query")
                        if callback:
                            cq_id = callback.get("id")
                            chat_id = str(callback.get("message", {}).get("chat", {}).get("id"))
                            data_val = callback.get("data", "")
                            
                            if data_val == "btn_history":
                                answer_callback(session, token, cq_id)
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📜 Aapka scan history khali hai."})
                            elif data_val == "btn_stats":
                                answer_callback(session, token, cq_id)
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📊 Bot Status: 🟢 Online & Running 24x7\n🔒 User Limit: Max 5 Panels per scan\n👑 Admin: Unlimited Access"})
                            elif data_val == "btn_web_panel":
                                answer_callback(session, token, cq_id, "Web Panel mode activated!")
                                waiting_for_panel[chat_id] = True
                                limit_text = " (Unlimited Access 👑)" if chat_id == str(ADMIN_CHAT_ID) else " (Limit: Max 5 Panels)"
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🌐 Kripya apna **Web Panel Link(s)** ya text yahan bhejiye{limit_text}:"})
                            continue

                        message = update.get("message")
                        if not message:
                            continue
                        
                        chat_id = str(message.get("chat", {}).get("id"))
                        text = message.get("text", "").strip()
                        document = message.get("document")

                        if text == "/start" or text == "/help":
                            welcome_text = (
                                "⚡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━⚡\n"
                                "🔥   **FIREBASE EXTRACTOR BOT**   🔥\n"
                                "⚡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━⚡\n\n"
                                "👋  Welcome!  Welcome to the most advanced\n"
                                "    Firebase extractor on Telegram.\n\n"
                                "✦ ─────────────────────────── ✦\n\n"
                                "**What I Extract:**\n"
                                "  🔥  Firebase Database URL & Online Status\n"
                                "  🔑  Google API Key & App ID\n"
                                "  📦  Package name & version\n"
                                "  🟢  Active Connection Monitoring\n\n"
                                "**Rules & Limits:**\n"
                                "  👤 Normal Users: Max 5 Panels per scan\n"
                                "  👑 Admin (Zaib): Unlimited Scans\n\n"
                                "/help     — Commands\n"
                                "/history  — Your scan history\n"
                                "/stats    — Bot statistics\n"
                                "/myid     — Your profile\n"
                                "✦ ─────────────────────────── ✦"
                            )
                            keyboard = [
                                [{"text": "📁 History", "callback_data": "btn_history"}, {"text": "📊 Stats", "callback_data": "btn_stats"}],
                                [{"text": "🌐 Extract from Web Panel", "callback_data": "btn_web_panel"}],
                                [{"text": "🔥 Send an APK to Start Scanning!", "callback_data": "btn_web_panel"}]
                            ]
                            send_keyboard_message(session, token, chat_id, welcome_text, keyboard)
                        
                        elif text == "/history":
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📜 Aapka scan history yahan show hoga."})
                        elif text == "/stats":
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📊 Bot Statistics: Active & Healthy.\n🔒 User Limit: 5 Panels/scan\n👑 Admin Mode: Active"})
                        elif text == "/myid":
                            is_admin = "Yes (👑 Admin)" if chat_id == str(ADMIN_CHAT_ID) else "No (Normal User — Limit: 5 panels)"
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"👤 Your Chat ID: `{chat_id}`\n👑 Admin Status: {is_admin}", "parse_mode": "Markdown"})
                        
                        elif document:
                            file_name = document.get("file_name", "")
                            if file_name.endswith(".apk"):
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📥 APK file mil gayi hai, scan ki ja rahi hai..."})
                                file_id = document.get("file_id")
                                
                                file_info = session.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}").json()
                                if file_info.get("ok"):
                                    file_path = file_info["result"]["file_path"]
                                    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                                    
                                    apk_data = session.get(download_url).content
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=".apk") as tmp:
                                        tmp.write(apk_data)
                                        tmp_name = tmp.name
                                    
                                    found_urls = extract_firebase_from_apk(tmp_name)
                                    try:
                                        os.remove(tmp_name)
                                    except:
                                        pass
                                    
                                    if found_urls:
                                        for fu in found_urls:
                                            res = check_firebase(fu, "dummy")
                                            reply = (f"🔥 **APK Firebase Extracted!**\n\n"
                                                     f"🏢 Panel: `{res['panel_name']}`\n"
                                                     f"🔗 URL: `{res['url']}`\n"
                                                     f"📊 Status: `{res['status'].upper()}`\n"
                                                     f"📱 Total Devices: `{res['total_devices']}`\n"
                                                     f"🟢 Online Connections: `{res['online_devices']}`")
                                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"})
                                    else:
                                        session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Is APK ke andar koi valid Firebase URL nahi mila."})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Kripya sirf `.apk` file hi bhejiye."})

                        elif text:
                            if chat_id in waiting_for_panel and waiting_for_panel[chat_id]:
                                waiting_for_panel[chat_id] = False
                            
                            parsed_links = parse_links_bulk(text)
                            if parsed_links:
                                is_admin = (chat_id == str(ADMIN_CHAT_ID))
                                if not is_admin and len(parsed_links) > 5:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"⚠️ **Limit Exceeded!** Aap ek baar mein maximum **5 panels** scan kar sakte hain (Aapne {len(parsed_links)} bheje hain)."})
                                    continue

                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🔍 Total {len(parsed_links)} panel(s) parse ho gaye hain, Firebase & Online connections check ho rahe hain..."})
                                
                                for url, key, panel in parsed_links:
                                    res = check_firebase(url, key)
                                    status = res["status"]
                                    
                                    if status in ["live", "live_no_auth"]:
                                        reply = (f"✅ **WEB PANEL FIREBASE LIVE!**\n\n"
                                                 f"🏢 Panel: `{res['panel_name']}`\n"
                                                 f"🔗 URL: `{res['url']}`\n"
                                                 f"🔑 Key: `{res['key']}`\n"
                                                 f"📱 Total Devices: `{res['total_devices']}`\n"
                                                 f"🟢 Online Connections: `{res['online_devices']}`")
                                    else:
                                        reply = (f"⚠️ **Panel Status: {status.upper()}**\n\n"
                                                 f"🏢 Panel: `{res['panel_name']}`\n"
                                                 f"🔗 URL: `{res['url']}`\n"
                                                 f"❌ Reason: `{res.get('error', 'Dead / Inactive')}`")
                                    
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Invalid link or format. Kripya sahi link bhejiye."})
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
        time.sleep(1)

if __name__ == "__main__":
    print("="*50)
    print("  Ultimate Firebase Extractor Bot Running...")
    print("="*50)
    session = requests.Session()
    threading.Thread(target=telegram_listener, args=(BOT_TOKEN, session), daemon=True).start()
    run_flask()
