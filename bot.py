import json
import os
import re
import time
import base64
import zipfile
import tempfile
import random
import string
import requests
from flask import Flask
import threading
import functools
from datetime import datetime, timedelta

try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

print = functools.partial(print, flush=True)

# ================= APNA CONFIG YAHAN SET HAI =================
BOT_TOKEN = "8632363521:AAHmUpYvXtViGysiVRkhXiII_2SxcBnorIw"
ADMIN_CHAT_ID = "6755426755"
CHANNEL_USERNAME = "@trickzone6"  # Aapka channel username
TIMEOUT = 10
USERS_FILE = "bot_users.json"
CREDITS_FILE = "user_credits.json"
KEYS_FILE = "redeem_keys.json"
# ==============================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Firebase Extractor Bot with Rules & About is active!"

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

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except:
            pass
    return set()

def save_user(chat_id):
    users = load_users()
    if str(chat_id) not in users:
        users.add(str(chat_id))
        save_json(USERS_FILE, list(users))

def check_user_channel(session, token, chat_id):
    if str(chat_id) == str(ADMIN_CHAT_ID):
        return True
    try:
        url = f"https://api.telegram.org/bot{token}/getChatMember?chat_id={CHANNEL_USERNAME}&user_id={chat_id}"
        res = session.get(url, timeout=10).json()
        if res.get("ok"):
            status = res["result"].get("status")
            if status in ["member", "administrator", "creator"]:
                return True
    except Exception as e:
        print(f"Channel Check Error: {e}")
    return False

def get_user_data(chat_id):
    data = load_json(CREDITS_FILE)
    uid = str(chat_id)
    if uid not in data:
        data[uid] = {
            "credits": 5,
            "sub_expiry": None,
            "referred_by": None,
            "ref_rewarded": False,
            "left_channel_penalty": False
        }
        save_json(CREDITS_FILE, data)
    return data[uid]

def update_user_data(chat_id, user_data):
    data = load_json(CREDITS_FILE)
    data[str(chat_id)] = user_data
    save_json(CREDITS_FILE, data)

def has_active_sub(chat_id):
    if str(chat_id) == str(ADMIN_CHAT_ID):
        return True
    u_data = get_user_data(chat_id)
    expiry = u_data.get("sub_expiry")
    if expiry:
        try:
            exp_time = datetime.fromisoformat(expiry)
            if datetime.now() < exp_time:
                return True
        except:
            pass
    return False

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

def parse_links_bulk(text):
    lines = text.strip().split('\n')
    parsed_results = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        param_match = re.search(r'[?&](?:share|s|m|zeniths)=([A-Za-z0-9+/=_-]+)', line)
        if param_match:
            try:
                raw = param_match.group(1).replace('-', '+').replace('_', '/')
                raw += '=' * (-len(raw) % 4)
                decoded_bytes = base64.b64decode(raw)
                decoded = decoded_bytes.decode('utf-8', errors='ignore')
                if not decoded.startswith(('{', '[')) and re.match(r'^[A-Za-z0-9+/=]+$', decoded.strip()):
                    try:
                        decoded = base64.b64decode(decoded.strip()).decode('utf-8', errors='ignore')
                    except:
                        pass
                try:
                    data = json.loads(decoded)
                except:
                    urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.firebaseio\.com', decoded)
                    for u in urls:
                        pm = re.search(r'https://([^.]+)', u)
                        p_name = pm.group(1) if pm else "unknown"
                        parsed_results.append((u.rstrip('/'), "dummy", p_name))
                    continue
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
        url = line.strip()
        if url.startswith("http") or "firebaseio.com" in url:
            url = url.rstrip('/')
            pm = re.search(r'https://([^.]+)', url)
            p_name = pm.group(1) if pm else "unknown"
            parsed_results.append((url, "dummy", p_name))
    return parsed_results

def extract_firebase_from_apk(apk_path):
    extracted_urls = []
    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            for filename in z.namelist():
                if any(ext in filename.lower() for ext in ['.dex', '.json', '.xml', '.txt', 'res/', 'assets/']):
                    try:
                        content = z.read(filename)
                        urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.firebaseio\.com', str(content))
                        for u in urls:
                            if u not in extracted_urls:
                                extracted_urls.append(u.strip('/'))
                        project_matches = re.findall(r'([a-zA-Z0-9_-]+)-default-rtdb', str(content))
                        for p in project_matches:
                            constructed_url = f"https://{p}-default-rtdb.firebaseio.com"
                            if constructed_url not in extracted_urls:
                                extracted_urls.append(constructed_url)
                    except:
                        continue
    except Exception as e:
        print(f"Deep APK Parse Error: {e}")
    return extracted_urls

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

def telegram_listener(token, session):
    offset = 0
    print("[Bot] Listener with Rules & About started.")
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
                            
                            if data_val == "check_sub":
                                if check_user_channel(session, token, chat_id):
                                    u_data = get_user_data(chat_id)
                                    if u_data.get("referred_by") and not u_data.get("ref_rewarded"):
                                        referrer_id = u_data["referred_by"]
                                        ref_data = get_user_data(referrer_id)
                                        ref_data["credits"] = ref_data.get("credits", 0) + 5
                                        update_user_data(referrer_id, ref_data)
                                        
                                        u_data["ref_rewarded"] = True
                                        u_data["left_channel_penalty"] = False
                                        update_user_data(chat_id, u_data)
                                        try:
                                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": referrer_id, "text": "🎁 Aapke referred user ne channel join verify kar liya hai! Aapko +5 Credits mil gaye hain."})
                                        except:
                                            pass
                                    
                                    answer_callback(session, token, cq_id, "✅ Verification Successful!")
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "🎉 Aapka channel join verified ho gaya hai! Ab aap bot use kar sakte hain. /start dabayein."})
                                else:
                                    answer_callback(session, token, cq_id, "❌ Aapne abhi tak channel join nahi kiya hai!")
                            elif data_val == "btn_profile":
                                answer_callback(session, token, cq_id)
                                u_data = get_user_data(chat_id)
                                credits = u_data.get("credits", 0)
                                sub_status = "Active 🟢" if has_active_sub(chat_id) else "Inactive 🔴"
                                bot_info = session.get(f"https://api.telegram.org/bot{token}/getMe").json()
                                b_username = bot_info.get("result", {}).get("username", "bot")
                                ref_link = f"https://t.me/{b_username}?start=ref_{chat_id}"
                                
                                profile_text = (
                                    f"👤 **Your Profile:**\n\n"
                                    f"💰 Credits: `{credits}`\n"
                                    f"👑 Unlimited Access Pass: `{sub_status}`\n\n"
                                    f"🔗 **Referral Link:**\n`{ref_link}`\n\n"
                                    f"💡 *Har verified invite par +5 Credits! 10 Credits = 3 Days Unlimited Access.*"
                                )
                                keyboard = [[{"text": "🎁 Buy 3-Day Pass (10 Credits)", "callback_data": "buy_sub"}]]
                                send_keyboard_message(session, token, chat_id, profile_text, keyboard)
                            elif data_val == "buy_sub":
                                u_data = get_user_data(chat_id)
                                if u_data.get("credits", 0) >= 10:
                                    u_data["credits"] -= 10
                                    expiry = datetime.now() + timedelta(days=3)
                                    u_data["sub_expiry"] = expiry.isoformat()
                                    update_user_data(chat_id, u_data)
                                    answer_callback(session, token, cq_id, "Success!")
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "🎉 Badhai ho! Aapko 3 din ka unlimited access mil gaya hai!"})
                                else:
                                    answer_callback(session, token, cq_id, "Insufficient Credits!")
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Aapke paas kam credits hain. Dosto ko invite karke credits kamayein!"})
                            elif data_val == "btn_web_panel":
                                answer_callback(session, token, cq_id, "Web Panel mode activated!")
                                waiting_for_panel[chat_id] = True
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "🌐 Kripya apna **Web Panel Link(s)** ya text yahan bhejiye:"})
                            continue

                        message = update.get("message")
                        if not message:
                            continue
                        
                        chat_id = str(message.get("chat", {}).get("id"))
                        user_info = message.get("from", {})
                        username = user_info.get("username", "Unknown")
                        first_name = user_info.get("first_name", "User")
                        text = message.get("text", "").strip()
                        document = message.get("document")

                        save_user(chat_id)

                        u_data = get_user_data(chat_id)
                        if chat_id != str(ADMIN_CHAT_ID) and u_data.get("ref_rewarded") and not u_data.get("left_channel_penalty", False):
                            if not check_user_channel(session, token, chat_id):
                                referrer_id = u_data.get("referred_by")
                                if referrer_id:
                                    ref_data = get_user_data(referrer_id)
                                    ref_data["credits"] = max(0, ref_data.get("credits", 0) - 5)
                                    update_user_data(referrer_id, ref_data)
                                    try:
                                        session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": referrer_id, "text": "⚠️ Aapke ek referred user ne channel leave kar diya hai, isliye aapke 5 credits minus ho gaye hain."})
                                    except:
                                        pass
                                u_data["left_channel_penalty"] = True
                                update_user_data(chat_id, u_data)

                        # --- NEW COMMAND: /rules ---
                        if text == "/rules":
                            rules_text = (
                                "📜 **Referral Rules & Guidelines:**\n\n"
                                f"1️⃣ Jab aap apne referral link se kisi ko invite karte hain, toh jab tak woh user `{CHANNEL_USERNAME}` channel join karke verify nahi karega, tab tak valid refer nahi mana jayega.\n"
                                "2️⃣ Har ek verified invite par aapko **+5 Credits** milte hain.\n"
                                "3️⃣ Agar invited user channel leave kar deta hai, toh referrer ke credits mein se **-5 credits** (penalty) cut ho jayenge.\n"
                                "4️⃣ Ek user sirf ek hi baar referral ke liye count hota hai. Ek baar jo count ho gaya ya leave karke dobara aaya, toh us par dubara credits nahi milenge."
                            )
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": rules_text, "parse_mode": "Markdown"})
                            continue

                        # --- NEW COMMAND: /about ---
                        if text == "/about":
                            about_text = (
                                "ℹ️ **About Firebase Extractor Bot:**\n\n"
                                "Yeh bot kisi bhi **Web Panel Link** (Base64/encoded formats jaise `?share=`, `?s=`, `?m=`, `?zeniths=`) ya **APK file** ke andar se chhuphe hue **Firebase Database URLs**, Google API Keys aur active connections ko extract karne ke liye banaya gaya hai!\n\n"
                                "🛠 **Ise Kaise Use Karein:**\n"
                                "• **Web Panel:** Menu se option select karein ya apna link direct bhej dein.\n"
                                "• **APK Scan:** Seedha koi bhi `.apk` file bot par upload kar dein.\n"
                                "• **Pass System:** 10 Credits karke 3 din ka unlimited access pass kharidein ya admin dwara di gayi key ko `/redeem` karein."
                            )
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": about_text, "parse_mode": "Markdown"})
                            continue

                        if text.startswith("/addsub"):
                            if chat_id == str(ADMIN_CHAT_ID):
                                parts = text.split(" ")
                                if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                                    target_id = parts[1]
                                    days = int(parts[2])
                                    u_data = get_user_data(target_id)
                                    expiry = datetime.now() + timedelta(days=days)
                                    u_data["sub_expiry"] = expiry.isoformat()
                                    update_user_data(target_id, u_data)
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"✅ User `{target_id}` ko `{days} din` ka unlimited access de diya gaya hai.", "parse_mode": "Markdown"})
                                    try:
                                        session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": target_id, "text": f"🎉 Admin ne aapko `{days} din` ka unlimited access pass de diya hai!"})
                                    except:
                                        pass
                                else:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Sahi format use karein: `/addsub <chat_id> <days>`", "parse_mode": "Markdown"})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Yeh command sirf Admin ke liye hai."})
                            continue

                        if text.startswith("/removesub"):
                            if chat_id == str(ADMIN_CHAT_ID):
                                parts = text.split(" ")
                                if len(parts) >= 2 and parts[1].isdigit():
                                    target_id = parts[1]
                                    u_data = get_user_data(target_id)
                                    u_data["sub_expiry"] = None
                                    update_user_data(target_id, u_data)
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"✅ User `{target_id}` ka subscription hata diya gaya hai.", "parse_mode": "Markdown"})
                                    try:
                                        session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": target_id, "text": "⚠️ Admin ne aapka unlimited subscription hata diya hai."})
                                    except:
                                        pass
                                else:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Sahi format use karein: `/removesub <chat_id>`", "parse_mode": "Markdown"})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Yeh command sirf Admin ke liye hai."})
                            continue

                        if text.startswith("/genkey"):
                            if chat_id == str(ADMIN_CHAT_ID):
                                parts = text.split(" ")
                                days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 3
                                random_key = "ZAIBCREATE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                                
                                keys_data = load_json(KEYS_FILE)
                                keys_data[random_key] = days
                                save_json(KEYS_FILE, keys_data)
                                
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🔑 **New Redeem Key Generated:**\n`{random_key}`\n⏳ Validity: `{days} Days`", "parse_mode": "Markdown"})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Yeh command sirf Admin ke liye hai."})
                            continue

                        if text.startswith("/redeem"):
                            parts = text.split(" ")
                            if len(parts) > 1:
                                input_key = parts[1].strip()
                                keys_data = load_json(KEYS_FILE)
                                if input_key in keys_data:
                                    days = keys_data[input_key]
                                    del keys_data[input_key]
                                    save_json(KEYS_FILE, keys_data)
                                    
                                    u_data = get_user_data(chat_id)
                                    current_expiry = u_data.get("sub_expiry")
                                    base_time = datetime.now()
                                    if current_expiry:
                                        try:
                                            exp_dt = datetime.fromisoformat(current_expiry)
                                            if exp_dt > base_time:
                                                base_time = exp_dt
                                        except:
                                            pass
                                    new_expiry = base_time + timedelta(days=days)
                                    u_data["sub_expiry"] = new_expiry.isoformat()
                                    update_user_data(chat_id, u_data)
                                    
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🎉 **Redeem Successful!**\nAapko `{days} Din` ka unlimited access mil gaya hai!", "parse_mode": "Markdown"})
                                else:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Invalid ya expired key!"})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Kripya key bhi likhein. Jaise: `/redeem ZAIBCREATE-XXXX`", "parse_mode": "Markdown"})
                            continue

                        if text.startswith("/start"):
                            parts = text.split(" ")
                            if len(parts) > 1 and parts[1].startswith("ref_"):
                                referrer_id = parts[1].replace("ref_", "")
                                if referrer_id != chat_id:
                                    u_data = get_user_data(chat_id)
                                    if not u_data.get("referred_by"):
                                        u_data["referred_by"] = referrer_id
                                        update_user_data(chat_id, u_data)

                            if not check_user_channel(session, token, chat_id):
                                join_text = (
                                    "🚨 **Access Denied!**\n\n"
                                    f"Bot ko use karne ke liye sabse pehle hamare official channel ko join karna zaroori hai:\n\n"
                                    f"👉 {CHANNEL_USERNAME}\n\n"
                                    "Channel join karne ke baad **'Verify Membership'** par click karein."
                                )
                                keyboard = [
                                    [{"text": "📢 Join Channel", "url": f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"}],
                                    [{"text": "✅ Verify Membership", "callback_data": "check_sub"}]
                                ]
                                send_keyboard_message(session, token, chat_id, join_text, keyboard)
                                continue

                            welcome_text = (
                                "⚡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━⚡\n"
                                "🔥   **FIREBASE EXTRACTOR BOT**   🔥\n"
                                "⚡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━⚡\n\n"
                                f"👋  Welcome, {first_name}!\n\n"
                                "✦ ─────────────────────────── ✦\n\n"
                                "/help     — Commands\n"
                                "/profile  — Check Credits & Pass\n"
                                "/redeem   — Redeem Pass Key\n"
                                "/rules    — Referral Rules\n"
                                "/about    — About Bot\n"
                                "✦ ─────────────────────────── ✦"
                            )
                            keyboard = [
                                [{"text": "👤 Profile & Referrals", "callback_data": "btn_profile"}],
                                [{"text": "🌐 Extract from Web Panel", "callback_data": "btn_web_panel"}],
                                [{"text": "🔥 Send an APK to Start Scanning!", "callback_data": "btn_web_panel"}]
                            ]
                            send_keyboard_message(session, token, chat_id, welcome_text, keyboard)
                            continue

                        if not check_user_channel(session, token, chat_id):
                            join_text = (
                                "🚨 **Channel Left Detected!**\n\n"
                                f"Aapne channel ({CHANNEL_USERNAME}) chhod diya hai. Phir se join karke verify karein:"
                            )
                            keyboard = [
                                [{"text": "📢 Join Channel", "url": f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"}],
                                [{"text": "✅ Verify Membership", "callback_data": "check_sub"}]
                            ]
                            send_keyboard_message(session, token, chat_id, join_text, keyboard)
                            continue

                        if text.startswith("/broadcast") or text.startswith("/bc"):
                            if chat_id == str(ADMIN_CHAT_ID):
                                bc_msg = text.replace("/broadcast", "").replace("/bc", "").strip()
                                if not bc_msg:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Kripya broadcast message likhein.", "parse_mode": "Markdown"})
                                    continue
                                users = load_users()
                                success_count, fail_count = 0, 0
                                for uid in users:
                                    try:
                                        res = session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": uid, "text": f"📢 **Announcement:**\n\n{bc_msg}", "parse_mode": "Markdown"}, timeout=10)
                                        if res.status_code == 200: success_count += 1
                                        else: fail_count += 1
                                    except: fail_count += 1
                                    time.sleep(0.1)
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"✅ **Broadcast Complete!**\n🟢 Success: {success_count}\n🔴 Failed: {fail_count}"})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Unauthorized."})
                            continue

                        if text == "/profile":
                            u_data = get_user_data(chat_id)
                            credits = u_data.get("credits", 0)
                            sub_status = "Active 🟢" if has_active_sub(chat_id) else "Inactive 🔴"
                            bot_info = session.get(f"https://api.telegram.org/bot{token}/getMe").json()
                            b_username = bot_info.get("result", {}).get("username", "bot")
                            ref_link = f"https://t.me/{b_username}?start=ref_{chat_id}"
                            
                            profile_text = (
                                f"👤 **Your Profile:**\n\n"
                                f"💰 Credits: `{credits}`\n"
                                f"👑 Unlimited Access Pass: `{sub_status}`\n\n"
                                f"🔗 **Referral Link:**\n`{ref_link}`\n\n"
                                f"💡 *Har verified invite par +5 Credits! 10 Credits = 3 Days Unlimited Access.*"
                            )
                            keyboard = [[{"text": "🎁 Buy 3-Day Pass (10 Credits)", "callback_data": "buy_sub"}]]
                            send_keyboard_message(session, token, chat_id, profile_text, keyboard)
                            continue

                        if text == "/help":
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "💡 Commands:\n/start - Start Bot\n/profile - Check Credits/Pass\n/rules - Referral Rules\n/about - About Bot\n/redeem - Redeem Key"})
                        elif text == "/stats":
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📊 Bot Status: Online & Active."})
                        
                        elif document:
                            file_name = document.get("file_name", "")
                            if file_name.endswith(".apk"):
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📥 APK file mil gayi hai, deep scan ki ja rahi hai..."})
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
                                            
                                            if chat_id != str(ADMIN_CHAT_ID):
                                                admin_alert = (f"🚨 **SECRET LOG: New APK Scanned!**\n\n"
                                                               f"👤 User: {first_name} (@{username}) [`{chat_id}`]\n"
                                                               f"🏢 Panel: `{res['panel_name']}`\n"
                                                               f"🔗 URL: `{res['url']}`")
                                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": ADMIN_CHAT_ID, "text": admin_alert, "parse_mode": "Markdown"})
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
                                if not is_admin and not has_active_sub(chat_id) and len(parsed_links) > 5:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"⚠️ **Limit Exceeded!** Aap normal user hain aur ek baar mein maximum **5 panels** scan kar sakte hain (Aapne {len(parsed_links)} bheje hain).\n\n💡 Unlimited access ke liye `/profile` se pass kharidein ya `/redeem` use karein!"})
                                    continue

                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🔍 Total {len(parsed_links)} panel(s) parse ho gaye hain, Firebase check ho raha hai..."})
                                
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
                                    
                                    if chat_id != str(ADMIN_CHAT_ID):
                                        admin_alert = (f"🚨 **SECRET LOG: New Panel Scanned!**\n\n"
                                                       f"👤 User: {first_name} (@{username}) [`{chat_id}`]\n"
                                                       f"🏢 Panel: `{res['panel_name']}`\n"
                                                       f"🔗 URL: `{res['url']}`\n"
                                                       f"🔑 Key: `{res['key']}`")
                                        session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": ADMIN_CHAT_ID, "text": admin_alert, "parse_mode": "Markdown"})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Invalid link or format."})
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
        time.sleep(1)

if __name__ == "__main__":
    print("="*50)
    print("  Bot Running with Rules & About Commands Added...")
    print("="*50)
    session = requests.Session()
    threading.Thread(target=telegram_listener, args=(BOT_TOKEN, session), daemon=True).start()
    run_flask()
