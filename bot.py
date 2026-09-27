import json
import os
import re
import time
import base64
import zipfile
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
BOT_TOKEN = "8632363521:AAGqaQT0-amCGntB2FZR4GG_HidShHwCfac"
ADMIN_CHAT_ID = "6755426755"
CHANNEL_USERNAME = "@trickzone6"  # Aapka official channel username
TIMEOUT = 10
USERS_FILE = "bot_users.json"
CREDITS_FILE = "user_credits.json"
KEYS_FILE = "redeem_keys.json"
# ==============================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "✨ Ultimate Premium Firebase Extractor Bot is Active & Running Live!"

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
            "credits": 0,
            "sub_expiry": None,
            "referred_by": None,
            "ref_rewarded": False,
            "left_channel_penalty": False,
            "my_databases": []
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

# --- UNIVERSAL ADVANCED LINK & QUERY PARSER ---
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
                        data2 = res2.json()
                        if data2 and isinstance(data2, dict):
                            result["status"] = "live_no_auth"
                            result["total_devices"] = len(data2)
                            result["online_devices"] = sum(
                                1 for d in data2.values() 
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
    print("[Bot] Universal Premium Listener started.")
    waiting_for_panel = {}
    waiting_for_key = {}
    waiting_for_broadcast = {}
    waiting_for_genkey = {}

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
                                        ref_data["credits"] = ref_data.get("credits", 0) + 10
                                        update_user_data(referrer_id, ref_data)
                                        
                                        u_data["ref_rewarded"] = True
                                        u_data["left_channel_penalty"] = False
                                        update_user_data(chat_id, u_data)
                                        try:
                                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                                "chat_id": referrer_id, 
                                                "text": "🎉 **New Verified Referral!**\n\nAapke referred user ne channel join verify kar liya hai.\n🎁 **+10 Credits** added to your account!"
                                            })
                                        except:
                                            pass
                                    
                                    answer_callback(session, token, cq_id, "✅ Verification Successful!")
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                        "chat_id": chat_id, 
                                        "text": "🎉 **Verification Successful!**\n\nAapka channel join verify ho gaya hai. Ab aap /start dabakar bot use kar sakte hain."
                                    })
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
                                    "👤 **P R O F I L E   D A S H B O A R D**\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"💰 **Credits Balance:** `{credits} Credits`\n"
                                    f"👑 **Subscription Status:** `{sub_status}`\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                    f"🔗 **Your Referral Link:**\n`{ref_link}`\n\n"
                                    "🎁 **Rule:** Har verified invite par **+10 Credits**. Referred user ko channel join rakhna hoga, warna leave karne par credits minus ho jayenge!"
                                )
                                keyboard = [
                                    [{"text": "💳 Buy 3-Day Pass (10 Credits)", "callback_data": "buy_sub"}],
                                    [{"text": "🔙 Back to Main Menu", "callback_data": "main_menu"}]
                                ]
                                send_keyboard_message(session, token, chat_id, profile_text, keyboard)

                            elif data_val == "buy_sub":
                                u_data = get_user_data(chat_id)
                                if u_data.get("credits", 0) >= 10:
                                    u_data["credits"] -= 10
                                    expiry = datetime.now() + timedelta(days=3)
                                    u_data["sub_expiry"] = expiry.isoformat()
                                    update_user_data(chat_id, u_data)
                                    answer_callback(session, token, cq_id, "Success!")
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                        "chat_id": chat_id, 
                                        "text": "🎉 **SUBSCRIPTION ACTIVATED!**\n\n✅ Plan: 3 Days Unlimited Access\n📉 Deducted: `-10 Credits`\n⏳ Expiry: `" + expiry.strftime('%Y-%m-%d %H:%M:%S') + "`"
                                    })
                                else:
                                    answer_callback(session, token, cq_id, "Insufficient Credits!")
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                        "chat_id": chat_id, 
                                        "text": "❌ **Insufficient Credits!**\n\nAapke paas kam se kam 10 credits hone chahiye. Dosto ko invite karein ya key redeem karein!"
                                    })

                            elif data_val == "btn_web_panel":
                                if not check_user_channel(session, token, chat_id):
                                    answer_callback(session, token, cq_id, "❌ Join channel first!")
                                    continue
                                if not has_active_sub(chat_id):
                                    answer_callback(session, token, cq_id, "❌ Active subscription required!")
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                        "chat_id": chat_id,
                                        "text": "❌ **Access Denied!**\n\nFirebase extract karne ke liye aapke paas active subscription honi zaroori hai. Pehle 10 credits se 3 din ka pass buy karein!"
                                    })
                                    continue

                                answer_callback(session, token, cq_id, "Extractor activated!")
                                waiting_for_panel[chat_id] = True
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                    "chat_id": chat_id, 
                                    "text": "📥 **SEND PANEL DATA OR LINKS**\n\n_Aap kisi bhi panel ka link (Zenith, EdgeOne, etc.), Base64 string, ya direct links bhej sakte hain._"
                                })

                            elif data_val == "btn_redeem":
                                answer_callback(session, token, cq_id)
                                waiting_for_key[chat_id] = True
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                    "chat_id": chat_id,
                                    "text": "🔑 **REDEEM LICENSE KEY**\n\nKripya apni valid license key yahan bhejein:"
                                })

                            elif data_val == "btn_history":
                                answer_callback(session, token, cq_id)
                                u_data = get_user_data(chat_id)
                                dbs = u_data.get("my_databases", [])
                                if not dbs:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                        "chat_id": chat_id,
                                        "text": "📊 **YOUR HISTORY & DATABASES**\n\n⚠️ Aapne abhi tak koi bhi Firebase extract nahi kiya hai."
                                    })
                                else:
                                    filename = f"my_firebases_{chat_id}.txt"
                                    with open(filename, "w", encoding="utf-8") as f:
                                        f.write(f"# Your Extracted Firebases — User ID: {chat_id}\n\n")
                                        for item in dbs:
                                            if item.get('key') and item.get('key') != "dummy":
                                                f.write(f"{item['url']}|||{item['key']}\n")
                                            else:
                                                f.write(f"{item['url']}\n")
                                    
                                    with open(filename, "rb") as doc:
                                        session.post(f"https://api.telegram.org/bot{token}/sendDocument", 
                                                     data={"chat_id": chat_id, "caption": f"📊 **Aapke Total Saved Firebases:** `{len(dbs)}`"},
                                                     files={"document": doc})

                            elif data_val == "btn_rules":
                                answer_callback(session, token, cq_id)
                                rules_text = (
                                    "ℹ️ **H E L P   &   R U L E S   G U I D E**\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    "1️⃣ **Subscription Rule:** Firebase extract karne ke liye 10 credits se 3 din ki subscription purchase karna zaroori hai.\n"
                                    "2️⃣ **Channel Membership:** Official channel join rakhna compulsory hai.\n"
                                    "3️⃣ **Referral Policy:** Har verified refer par **+10 Credits** milte hain. Channel leave karne par credits deduct ho jayenge.\n"
                                    "4️⃣ **Security:** All extracted data is safely saved in your private history."
                                )
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": rules_text})

                            elif data_val == "admin_download_all" and chat_id == str(ADMIN_CHAT_ID):
                                answer_callback(session, token, cq_id)
                                all_dbs = set()
                                all_data = load_json(CREDITS_FILE)
                                for u_info in all_data.values():
                                    for db in u_info.get("my_databases", []):
                                        if db.get('url'):
                                            all_dbs.add(db['url'])
                                
                                if not all_dbs:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Database mein koi firebase nahi hai."})
                                else:
                                    filename = "all_admin_firebases.txt"
                                    with open(filename, "w", encoding="utf-8") as f:
                                        f.write("\n".join(sorted(all_dbs)))
                                    with open(filename, "rb") as doc:
                                        session.post(f"https://api.telegram.org/bot{token}/sendDocument", 
                                                     data={"chat_id": chat_id, "caption": f"📁 Total **{len(all_dbs)}** Unique Firebases Collected Across All Users!"},
                                                     files={"document": doc})

                            elif data_val == "admin_gen" and chat_id == str(ADMIN_CHAT_ID):
                                answer_callback(session, token, cq_id)
                                waiting_for_genkey[chat_id] = True
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "🔑 Kitne credits ki key banani hai? Sirf number bhejein (jaise: `10`):"})

                            elif data_val == "admin_bc" and chat_id == str(ADMIN_CHAT_ID):
                                answer_callback(session, token, cq_id)
                                waiting_for_broadcast[chat_id] = True
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "📢 Jo message saare users ko bhejna hai, woh yahan forward ya type karein:"})

                            elif data_val == "main_menu":
                                answer_callback(session, token, cq_id)
                                u_data = get_user_data(chat_id)
                                credits = u_data.get("credits", 0)
                                sub_status = "Lifetime (Admin)" if chat_id == str(ADMIN_CHAT_ID) else ("Active 🟢" if has_active_sub(chat_id) else "Expired / None 🔴")
                                
                                welcome_text = (
                                    "✨ **P R E M I U M   F I R E B A S E   H U B** ✨\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"👋 *Welcome back, {callback.get('message', {}).get('chat', {}).get('first_name', 'User')}!*\n\n"
                                    f"💳 **Aapke Credits:** `{credits} Credits`\n"
                                    f"⏳ **Subscription Status:** `{sub_status}`\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    "_Select an option from the dashboard below:_"
                                )
                                keyboard = [
                                    [{"text": "🚀 Extract From Web Panel", "callback_data": "btn_web_panel"}, {"text": "💳 Buy 3-Day Sub (10 Cr)", "callback_data": "buy_sub"}],
                                    [{"text": "📊 My History & DB", "callback_data": "btn_history"}, {"text": "🎁 Refer & Earn", "callback_data": "btn_profile"}],
                                    [{"text": "🔑 Redeem Key", "callback_data": "btn_redeem"}, {"text": "ℹ️ Help & Rules", "callback_data="btn_rules"}],
                                    [{"text": "⚡ System Status", "callback_data": "btn_status"}]
                                ]
                                if chat_id == str(ADMIN_CHAT_ID):
                                    keyboard.append([{"text": "📥 Download All DBs (Admin)", "callback_data": "admin_download_all"}])
                                    keyboard.append([{"text": "📢 Broadcast", "callback_data": "admin_bc"}, {"text": "🎟️ Generate Key", "callback_data": "admin_gen"}])
                                
                                send_keyboard_message(session, token, chat_id, welcome_text, keyboard)
                            continue

                        message = update.get("message")
                        if not message:
                            continue
                        
                        chat_id = str(message.get("chat", {}).get("id"))
                        user_info = message.get("from", {})
                        first_name = user_info.get("first_name", "User")
                        text = message.get("text", "").strip()

                        save_user(chat_id)

                        # Leave channel check penalty calculation
                        u_data = get_user_data(chat_id)
                        if chat_id != str(ADMIN_CHAT_ID) and u_data.get("ref_rewarded") and not u_data.get("left_channel_penalty", False):
                            if not check_user_channel(session, token, chat_id):
                                referrer_id = u_data.get("referred_by")
                                if referrer_id:
                                    ref_data = get_user_data(referrer_id)
                                    ref_data["credits"] = max(0, ref_data.get("credits", 0) - 10)
                                    update_user_data(referrer_id, ref_data)
                                    try:
                                        session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                            "chat_id": referrer_id, 
                                            "text": "⚠️ **Referral Alert!**\n\nAapke ek referred user ne channel leave kar diya hai, isliye aapke **10 credits** minus ho gaye hain!"
                                        })
                                    except:
                                        pass
                                u_data["left_channel_penalty"] = True
                                update_user_data(chat_id, u_data)

                        if text.startswith("/start"):
                            text_args = text.split()
                            if len(text_args) > 1 and text_args[1].startswith("ref_"):
                                try:
                                    ref_id = text_args[1].split("_")[1]
                                    if ref_id != chat_id and not u_data.get("referred_by"):
                                        if check_user_channel(session, token, chat_id):
                                            u_data["referred_by"] = ref_id
                                            update_user_data(chat_id, u_data)
                                            
                                            ref_data = get_user_data(ref_id)
                                            ref_data["credits"] = ref_data.get("credits", 0) + 10
                                            update_user_data(ref_id, ref_data)
                                            u_data["ref_rewarded"] = True
                                            update_user_data(chat_id, u_data)
                                            
                                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                                "chat_id": ref_id, 
                                                "text": "🎁 **New Verified Referral!**\n\nAapke link se ek naye user ne join kiya hai.\n🎁 **+10 Credits** added to your account!"
                                            })
                                except:
                                    pass

                            if not check_user_channel(session, token, chat_id):
                                join_kb = [
                                    [{"text": "📢 Join Official Channel", "url": f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"}],
                                    [{"text": "🔄 Verify Membership", "callback_data": "check_sub"}]
                                ]
                                send_keyboard_message(
                                    session, token, chat_id,
                                    "⚠️ **ACCESS DENIED!**\n\n"
                                    f"Bot ko use karne ke liye pehle hamara channel join karna compulsory hai:\n👉 {CHANNEL_USERNAME}\n\n"
                                    "Join karne ke baad niche **Verify Membership** par click karein.",
                                    join_kb
                                )
                                continue

                            credits = u_data.get("credits", 0)
                            sub_status = "Lifetime (Admin)" if chat_id == str(ADMIN_CHAT_ID) else ("Active 🟢" if has_active_sub(chat_id) else "Expired / None 🔴")
                            
                            welcome_text = (
                                "✨ **P R E M I U M   F I R E B A S E   H U B** ✨\n"
                                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"👋 *Welcome back, {first_name}!*\n\n"
                                f"💳 **Aapke Credits:** `{credits} Credits`\n"
                                f"⏳ **Subscription Status:** `{sub_status}`\n"
                                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                "_Select an option from the dashboard below:_"
                            )
                            keyboard = [
                                [{"text": "🚀 Extract From Web Panel", "callback_data": "btn_web_panel"}, {"text": "💳 Buy 3-Day Sub (10 Cr)", "callback_data": "buy_sub"}],
                                [{"text": "📊 My History & DB", "callback_data": "btn_history"}, {"text": "🎁 Refer & Earn", "callback_data": "btn_profile"}],
                                [{"text": "🔑 Redeem Key", "callback_data": "btn_redeem"}, {"text": "ℹ️ Help & Rules", "callback_data": "btn_rules"}],
                                [{"text": "⚡ System Status", "callback_data": "btn_status"}]
                            ]
                            if chat_id == str(ADMIN_CHAT_ID):
                                keyboard.append([{"text": "📥 Download All DBs (Admin)", "callback_data": "admin_download_all"}])
                                keyboard.append([{"text": "📢 Broadcast", "callback_data": "admin_bc"}, {"text": "🎟️ Generate Key", "callback_data": "admin_gen"}])
                            
                            send_keyboard_message(session, token, chat_id, welcome_text, keyboard)
                            continue

                        # Handle Gen Key State
                        if chat_id == str(ADMIN_CHAT_ID) and chat_id in waiting_for_genkey:
                            waiting_for_genkey.pop(chat_id, None)
                            if text.isdigit():
                                credits_val = int(text)
                                random_key = "FIRE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
                                keys_data = load_json(KEYS_FILE)
                                keys_data[random_key] = credits_val
                                save_json(KEYS_FILE, keys_data)
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                    "chat_id": chat_id,
                                    "text": f"✅ **License Key Generated Successfully!**\n\n🔑 Key: `{random_key}`\n💎 Credits: `{credits_val}`"
                                })
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Sirf valid number bhejein."})
                            continue

                        # Handle Redeem Key State
                        if chat_id in waiting_for_key:
                            waiting_for_key.pop(chat_id, None)
                            keys_data = load_json(KEYS_FILE)
                            if text in keys_data:
                                creds = keys_data.pop(text)
                                save_json(KEYS_FILE, keys_data)
                                
                                u_data["credits"] = u_data.get("credits", 0) + creds
                                update_user_data(chat_id, u_data)
                                
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                    "chat_id": chat_id,
                                    "text": f"🎉 **Successfully Redeemed!**\n+{creds} Credits added to your account."
                                })
                                
                                # Notify Admin
                                admin_alert = (
                                    "🔔 **NEW KEY REDEEMED!**\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"👤 User: `{first_name}`\n"
                                    f"🆔 User ID: `{chat_id}`\n"
                                    f"🔑 Key: `{text}`\n"
                                    f"💎 Credits Added: `+{creds}`\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                )
                                try:
                                    session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": ADMIN_CHAT_ID, "text": admin_alert})
                                except:
                                    pass
                            else:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Invalid ya already used key!"})
                            continue

                        # Handle Broadcast State
                        if chat_id == str(ADMIN_CHAT_ID) and chat_id in waiting_for_broadcast:
                            waiting_for_broadcast.pop(chat_id, None)
                            all_users = load_users()
                            success, fail = 0, 0
                            for uid in all_users:
                                try:
                                    res = session.post(f"https://api.telegram.org/bot{token}/copyMessage", json={
                                        "chat_id": uid,
                                        "from_chat_id": chat_id,
                                        "message_id": message.get("message_id")
                                    })
                                    if res.status_code == 200:
                                        success += 1
                                    else:
                                        fail += 1
                                except:
                                    fail += 1
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": f"📢 **Broadcast Completed!**\n\n✅ Delivered: {success}\n❌ Failed: {fail}"
                            })
                            continue

                        # Handle Web Panel / Links Extractor State
                        if chat_id in waiting_for_panel:
                            waiting_for_panel.pop(chat_id, None)
                            
                            if not check_user_channel(session, token, chat_id):
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "⚠️ Pehle channel join karein."})
                                continue
                            if chat_id != str(ADMIN_CHAT_ID) and not has_active_sub(chat_id):
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": "❌ Active subscription required!"})
                                continue

                            parsed_items = parse_links_bulk(text)
                            if not parsed_items:
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                    "chat_id": chat_id,
                                    "text": "❌ **No Valid Firebase Found!**\n\nKripya sahi panel link ya text bhejein."
                                })
                                continue

                            for idx, (url, key, p_name) in enumerate(parsed_items, 1):
                                stats = check_firebase(url, key)
                                total = stats["total_devices"]
                                online = stats["online_devices"]
                                status_str = stats["status"]
                                
                                res_msg = (
                                    f"✨ **FIREBASE EXTRACTED #{idx}** ✨\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"🔗 **URL:** `{url}`\n"
                                    f"🔑 **Key:** `{key}`\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"📱 **Total Connections:** `{total}`\n"
                                    f"🟢 **Online Connections:** `{online}`\n"
                                    f"⚡ **Status:** `{status_str}`\n"
                                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                                )
                                session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": res_msg})

                                # Save to user private database history
                                db_entry = {"url": url, "key": key}
                                if db_entry not in u_data["my_databases"]:
                                    u_data["my_databases"].append(db_entry)
                            
                            update_user_data(chat_id, u_data)
                            session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": f"✅ **Successfully Processed {len(parsed_items)} Firebase(s)!**"
                            })
                            continue

        except Exception as e:
            print(f"Listener Error: {e}")
        time.sleep(1)

def main():
    session = requests.Session()
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()
    
    print("[Bot] Starting Telegram Listener...")
    telegram_listener(BOT_TOKEN, session)

if __name__ == "__main__":
    main()
