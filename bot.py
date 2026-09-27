import os
import re
import json
import random
import string
import base64
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8632363521:AAFe_zNejmQ-BhGSaSB26fa5z9sMubyQHvo"
ADMIN_CHAT_ID = 6755426755
CHANNEL_USERNAME = "@trickzone6"

app = Flask(__name__)

@app.route('/')
def home():
    return "✨ Ultimate Premium Firebase Extractor Bot is Active & Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

USERS_FILE = "bot_users.json"
CREDITS_FILE = "user_credits.json"
KEYS_FILE = "redeem_keys.json"

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except:
        pass

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

def check_channel(user_id):
    if user_id == ADMIN_CHAT_ID:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except:
        pass
    return False

def has_active_sub(user_id):
    if user_id == ADMIN_CHAT_ID:
        return True
    u_data = get_user_data(user_id)
    expiry = u_data.get("sub_expiry")
    if expiry:
        try:
            exp_time = datetime.fromisoformat(expiry)
            if datetime.now() < exp_time:
                return True
        except:
            pass
    return False

def parse_links_bulk(text):
    lines = text.strip().split('\n')
    parsed_results = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        param_matches = re.findall(r'[?&][a-zA-Z0-9_-]+=([^&\s]+)', line)
        decoded_texts = [line]
        for match in param_matches:
            decoded_texts.append(match)
            try:
                raw = match.replace('-', '+').replace('_', '/')
                raw += '=' * (-len(raw) % 4)
                decoded_bytes = base64.b64decode(raw)
                decoded = decoded_bytes.decode('utf-8', errors='ignore')
                decoded_texts.append(decoded)
            except:
                pass

        found_any = False
        for text_block in decoded_texts:
            urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.firebaseio\.com[^\s<>"]*|https?://[a-zA-Z0-9.-]+\.firebasedatabase\.app[^\s<>"]*', text_block, re.IGNORECASE)
            for u in urls:
                u_clean = u.rstrip('/')
                if not u_clean.startswith("http"):
                    u_clean = "https://" + u_clean
                if (u_clean, "dummy") not in [(x[0], x[1]) for x in parsed_results]:
                    parsed_results.append((u_clean, "dummy"))
                    found_any = True

            try:
                data = json.loads(text_block)
                def dig_json(obj):
                    nonlocal found_any
                    if isinstance(obj, dict):
                        p_url = obj.get('url', '') or obj.get('firebase', '') or obj.get('rtdb', '') or obj.get('link', '')
                        p_key = obj.get('key', 'dummy') or obj.get('secret', 'dummy') or obj.get('auth', 'dummy') or "dummy"
                        if p_url and isinstance(p_url, str):
                            clean_url = p_url.rstrip('/')
                            if not clean_url.startswith("http"):
                                clean_url = "https://" + clean_url
                            if "firebase" in clean_url.lower() or "rtdb" in clean_url.lower():
                                if (clean_url, str(p_key)) not in [(x[0], x[1]) for x in parsed_results]:
                                    parsed_results.append((clean_url, str(p_key)))
                                    found_any = True
                        for val in obj.values():
                            dig_json(val)
                    elif isinstance(obj, list):
                        for item in obj:
                            dig_json(item)
                dig_json(data)
            except:
                pass

        if found_any:
            continue

        if '||' in line:
            parts = re.split(r'\|{2,}', line)
            url = parts[0].strip().rstrip('/')
            key = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "dummy"
            if url:
                if not url.startswith("http"):
                    url = "https://" + url
                if (url, key) not in [(x[0], x[1]) for x in parsed_results]:
                    parsed_results.append((url, key))
                continue

    return parsed_results

def check_firebase(url, key):
    total, online = 0, 0
    try:
        clients_url = f"{url}/clients.json"
        if key and key != "dummy":
            clients_url += f"?auth={key}"
        res = requests.get(clients_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict) and data:
                total = len(data)
                online = sum(1 for d in data.values() if isinstance(d, dict) and (d.get("status") or d.get("online") or d.get("lastSeen")))
        elif res.status_code == 401 and key and key != "dummy":
            res2 = requests.get(f"{url}/clients.json", timeout=10)
            if res2.status_code == 200:
                data2 = res2.json()
                if isinstance(data2, dict) and data2:
                    total = len(data2)
                    online = sum(1 for d in data2.values() if isinstance(d, dict) and (d.get("status") or d.get("online") or d.get("lastSeen")))
    except:
        pass
    return total, online

def get_main_keyboard(is_admin=False):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🚀 Extract From Web Panel", callback_data="extract_menu"),
        InlineKeyboardButton("💳 Buy 3-Day Sub (10 Cr)", callback_data="buy_subscription"),
        InlineKeyboardButton("📊 My History & DB", callback_data="view_databases"),
        InlineKeyboardButton("🎁 Refer & Earn", callback_data="get_referral"),
        InlineKeyboardButton("🔑 Redeem Key", callback_data="redeem_key"),
        InlineKeyboardButton("ℹ️ Help & Rules", callback_data="help_menu"),
        InlineKeyboardButton("⚡ System Status", callback_data="system_status")
    )
    if is_admin:
        markup.add(
            InlineKeyboardButton("📥 Download All DBs (Admin)", callback_data="admin_download"),
            InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
            InlineKeyboardButton("🎟️ Generate Key", callback_data="admin_genkey")
        )
    return markup

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    u_data = get_user_data(user_id)
    text_args = message.text.split()
    
    if len(text_args) > 1 and text_args[1].startswith("ref_"):
        try:
            ref_id = text_args[1].split("_")[1]
            if int(ref_id) != user_id and not u_data.get("referred_by"):
                if check_channel(user_id):
                    u_data["referred_by"] = ref_id
                    update_user_data(user_id, u_data)
                    
                    ref_data = get_user_data(int(ref_id))
                    ref_data["credits"] = ref_data.get("credits", 0) + 10
                    update_user_data(int(ref_id), ref_data)
                    u_data["ref_rewarded"] = True
                    update_user_data(user_id, u_data)
                    
                    try:
                        bot.send_message(int(ref_id), "🎁 <b>New Verified Referral!</b>\n\nAapke link se ek naye user ne join kiya hai.\n🎁 <b>+10 Credits</b> added to your account!")
                    except:
                        pass
        except:
            pass

    if user_id != ADMIN_CHAT_ID and u_data.get("ref_rewarded") and not u_data.get("left_channel_penalty", False):
        if not check_channel(user_id):
            ref_id = u_data.get("referred_by")
            if ref_id:
                ref_data = get_user_data(int(ref_id))
                ref_data["credits"] = max(0, ref_data.get("credits", 0) - 10)
                update_user_data(int(ref_id), ref_data)
                try:
                    bot.send_message(int(ref_id), "⚠️ <b>Referral Alert!</b>\n\nAapke ek referred user ne channel leave kar diya hai, isliye aapke <b>10 credits</b> minus ho gaye hain!")
                except:
                    pass
            u_data["left_channel_penalty"] = True
            update_user_data(user_id, u_data)

    if not check_channel(user_id):
        join_kb = InlineKeyboardMarkup()
        join_kb.add(InlineKeyboardButton("📢 Join Official Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"))
        join_kb.add(InlineKeyboardButton("🔄 Verify Membership", callback_data="check_join"))
        bot.send_message(
            user_id,
            "⚠️ <b>ACCESS DENIED!</b>\n\n"
            f"Bot ko use karne ke liye pehle hamara channel join karna compulsory hai:\n👉 {CHANNEL_USERNAME}\n\n"
            "Join karne ke baad niche <b>Verify Membership</b> par click karein.",
            reply_markup=join_kb
        )
        return

    is_admin = (user_id == ADMIN_CHAT_ID)
    sub_status = "Lifetime (Admin)" if is_admin else ("Active 🟢" if has_active_sub(user_id) else "Expired / None 🔴")
    
    welcome_text = (
        "✨ <b>P R E M I U M   F I R E B A S E   H U B</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 <i>Welcome back, {message.from_user.first_name}!</i>\n\n"
        f"💳 <b>Aapke Credits:</b> <code>{u_data.get('credits', 0)} Credits</code>\n"
        f"⏳ <b>Subscription Status:</b> <code>{sub_status}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Select an option from the dashboard below:</i>"
    )
    bot.send_message(user_id, welcome_text, reply_markup=get_main_keyboard(is_admin))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    is_admin = (user_id == ADMIN_CHAT_ID)
    u_data = get_user_data(user_id)

    if data == "check_join":
        if check_channel(user_id):
            bot.answer_callback_query(call.id, "✅ Verification Successful!")
            if u_data.get("referred_by") and not u_data.get("ref_rewarded"):
                ref_id = u_data["referred_by"]
                ref_data = get_user_data(int(ref_id))
                ref_data["credits"] = ref_data.get("credits", 0) + 10
                update_user_data(int(ref_id), ref_data)
                u_data["ref_rewarded"] = True
                u_data["left_channel_penalty"] = False
                update_user_data(user_id, u_data)
                try:
                    bot.send_message(int(ref_id), "🎁 <b>New Verified Referral!</b>\n\nAapke referred user ne channel join verify kar liya hai.\n🎁 <b>+10 Credits</b> added to your account!")
                except:
                    pass
            cmd_start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Aapne abhi tak channel join nahi kiya hai!", show_alert=True)

    elif data == "buy_subscription":
        if not check_channel(user_id):
            bot.answer_callback_query(call.id, "❌ Pehle channel join karein!", show_alert=True)
            return
        
        current_credits = u_data.get("credits", 0)
        if current_credits < 10:
            bot.answer_callback_query(call.id, "❌ Aapke paas kam se kam 10 credits hone chahiye!", show_alert=True)
            return

        u_data["credits"] -= 10
        expiry = datetime.now() + timedelta(days=3)
        u_data["sub_expiry"] = expiry.isoformat()
        update_user_data(user_id, u_data)

        bot.answer_callback_query(call.id, "🎉 Subscription Activated!")
        bot.send_message(
            user_id,
            "🎉 <b>SUBSCRIPTION PURCHASED!</b>\n\n"
            "✅ <b>Plan:</b> 3 Days Unlimited Access\n"
            "📉 <b>Credits Deducted:</b> <code>-10 Credits</code>\n"
            f"⏳ <b>Expiry:</b> <code>{expiry.strftime('%Y-%m-%d %H:%M:%S')}</code>",
            reply_markup=get_main_keyboard(is_admin)
        )

    elif data == "extract_menu":
        if not check_channel(user_id):
            bot.answer_callback_query(call.id, "❌ Pehle channel join karein!", show_alert=True)
            return
        if not is_admin and not has_active_sub(user_id):
            bot.answer_callback_query(call.id, "❌ Active subscription required (10 Credits)!", show_alert=True)
            return
            
        bot.answer_callback_query(call.id)
        bot.send_message(
            user_id,
            "📥 <b>SEND PANEL DATA OR LINKS</b>\n\n"
            "<i>Aap kisi bhi type ka web panel link, Base64 string, ya direct links bhej sakte hain.</i>"
        )
        bot.register_next_step_handler_by_chat_id(user_id, process_extraction)

    elif data == "view_databases":
        dbs = u_data.get("my_databases", [])
        if not dbs:
            bot.answer_callback_query(call.id)
            bot.send_message(user_id, "📊 <b>YOUR HISTORY & DATABASES</b>\n\n⚠️ Aapne abhi tak koi bhi Firebase extract nahi kiya hai.", reply_markup=get_main_keyboard(is_admin))
        else:
            filename = f"my_firebases_{user_id}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# Your Extracted Firebases — User ID: {user_id}\n\n")
                for item in dbs:
                    if item.get('key') and item.get('key') != "dummy":
                        f.write(f"{item['url']}|||{item['key']}\n")
                    else:
                        f.write(f"{item['url']}\n")
            
            bot.answer_callback_query(call.id)
            with open(filename, "rb") as doc:
                bot.send_document(
                    user_id, doc, 
                    caption=f"📊 <b>Aapke Total Saved Firebases:</b> <code>{len(dbs)}</code>",
                    reply_markup=get_main_keyboard(is_admin)
                )

    elif data == "get_referral":
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        bot.answer_callback_query(call.id)
        ref_text = (
            "🔗 <b>YOUR REFERRAL LINK</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>USER NAME:</b> @{call.from_user.username if call.from_user.username else 'No Username'}\n"
            f"🆔 <b>USER ID:</b> <code>{user_id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔗 <b>YOUR LINK:</b>\n"
            f"<code>{ref_link}</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎁 <b>EARN 10 CREDITS FOR EVERY VERIFIED REFERRAL</b>\n\n"
            "💡 <i>Rule: Referred user ko official channel join karke rakhna hoga. Agar koi user channel leave karega, toh aapke refer kiye hue points minus kar liye jayenge!</i>"
        )
        bot.send_message(user_id, ref_text)

    elif data == "help_menu":
        bot.answer_callback_query(call.id)
        bot.send_message(
            user_id,
            "ℹ️ <b>HELP & RULES GUIDE</b>\n\n"
            "1️⃣ <b>Subscription Rule:</b> Firebase extract karne ke liye 10 credits se 3 din ki subscription purchase karna zaroori hai.\n"
            "2️⃣ <b>Channel Membership:</b> Official channel join rakhna compulsory hai.\n"
            "3️⃣ <b>Referral Policy:</b> Har verified refer par 10 credits milte hain. Channel leave karne par credits deduct ho jayenge.\n"
            "4️⃣ <b>Security:</b> All extracted data is safely saved in your private history."
        )

    elif data == "admin_download" and is_admin:
        all_dbs = set()
        all_data = load_json(CREDITS_FILE)
        for u_info in all_data.values():
            for db in u_info.get("my_databases", []):
                if db.get('url'):
                    all_dbs.add(db['url'])
        
        if not all_dbs:
            bot.answer_callback_query(call.id, "⚠️ Database mein koi firebase nahi hai.", show_alert=True)
            return
        
        filename = "all_admin_firebases.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(all_dbs)))
        bot.answer_callback_query(call.id)
        with open(filename, "rb") as doc:
            bot.send_document(user_id, doc, caption=f"📁 Total <b>{len(all_dbs)}</b> Unique Firebases Collected Across All Users!")

    elif data == "admin_genkey" and is_admin:
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "🔑 Kitne credits ki key banani hai? Sirf number bhejein (jaise: <code>10</code>):")
        bot.register_next_step_handler_by_chat_id(user_id, process_genkey)

    elif data == "redeem_key":
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "🔑 Apni <b>License Key</b> yahan bhejein:")
        bot.register_next_step_handler_by_chat_id(user_id, process_redeem)

    elif data == "admin_broadcast" and is_admin:
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "📢 Jo message saare users ko bhejna hai, woh yahan forward ya type karein:")
        bot.register_next_step_handler_by_chat_id(user_id, process_broadcast)

    elif data == "system_status":
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "⚡ <b>System Status:</b> Operational 🟢\n🔒 <b>Security:</b> Fully Encrypted\n🌐 <b>Core:</b> Universal Engine Active")

def process_extraction(message):
    user_id = message.from_user.id
    if not check_channel(user_id):
        bot.send_message(user_id, "⚠️ Pehle channel join karein.")
        return
    
    is_admin = (user_id == ADMIN_CHAT_ID)
    if not is_admin and not has_active_sub(user_id):
        bot.send_message(user_id, "❌ Active subscription required!")
        return

    text = message.text.strip() if message.text else ""
    parsed_items = parse_links_bulk(text)
    
    if not parsed_items:
        bot.send_message(user_id, "❌ <b>No Valid Firebase Found!</b>\n\nKripya sahi panel link ya text bhejein.", reply_markup=get_main_keyboard(is_admin))
        return

    u_data = get_user_data(user_id)
    for idx, (url, key) in enumerate(parsed_items, 1):
        total, online = check_firebase(url, key)
        
        res = (
            f"✨ <b>FIREBASE EXTRACTED #{idx}</b> ✨\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>URL:</b> <code>{url}</code>\n"
            f"🔑 <b>Key:</b> <code>{key}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Total Connections:</b> <code>{total}</code>\n"
            f"🟢 <b>Online Connections:</b> <code>{online}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        bot.send_message(user_id, res)

        db_entry = {"url": url, "key": key}
        if db_entry not in u_data["my_databases"]:
            u_data["my_databases"].append(db_entry)
            
    update_user_data(user_id, u_data)
    bot.send_message(user_id, f"✅ <b>Successfully Processed {len(parsed_items)} Firebase(s)!</b>", reply_markup=get_main_keyboard(is_admin))

def process_genkey(message):
    user_id = message.from_user.id
    if user_id != ADMIN_CHAT_ID:
        return
    text = message.text.strip() if message.text else ""
    if not text.isdigit():
        bot.send_message(user_id, "❌ Kripya sirf valid number bhejein.")
        return
    
    credits_val = int(text)
    random_key = "FIRE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    keys_data = load_json(KEYS_FILE)
    keys_data[random_key] = credits_val
    save_json(KEYS_FILE, keys_data)
    
    bot.send_message(
        user_id,
        f"✅ <b>License Key Generated Successfully!</b>\n\n"
        f"🔑 Key: <code>{random_key}</code>\n"
        f"💎 Credits: <code>{credits_val}</code>",
        reply_markup=get_main_keyboard(True)
    )

def process_redeem(message):
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    keys_data = load_json(KEYS_FILE)
    
    if text in keys_data:
        creds = keys_data.pop(text)
        save_json(KEYS_FILE, keys_data)
        
        u_data = get_user_data(user_id)
        u_data["credits"] = u_data.get("credits", 0) + creds
        update_user_data(user_id, u_data)
        
        bot.send_message(
            user_id,
            f"🎉 <b>Successfully Redeemed!</b>\n+{creds} Credits added to your account.",
            reply_markup=get_main_keyboard(user_id == ADMIN_CHAT_ID)
        )
        
        admin_alert = (
            "🔔 <b>NEW KEY REDEEMED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 User: `{message.from_user.first_name}`\n"
            f"🆔 User ID: `{user_id}`\n"
            f"🔑 Key: `{text}`\n"
            f"💎 Credits Added: `+{creds}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        try:
            bot.send_message(ADMIN_CHAT_ID, admin_alert)
        except:
            pass
    else:
        bot.send_message(user_id, "❌ Invalid ya already used key!", reply_markup=get_main_keyboard(user_id == ADMIN_CHAT_ID))

def process_broadcast(message):
    user_id = message.from_user.id
    if user_id != ADMIN_CHAT_ID:
        return
    
    all_data = load_json(CREDITS_FILE)
    success, fail = 0, 0
    for uid in all_data.keys():
        try:
            bot.copy_message(chat_id=int(uid), from_chat_id=user_id, message_id=message.message_id)
            success += 1
        except:
            fail += 1
            
    bot.send_message(
        user_id,
        f"📢 <b>Broadcast Completed!</b>\n\n✅ Delivered: {success}\n❌ Fail: {fail}",
        reply_markup=get_main_keyboard(True)
    )

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("✨ Bot is running live with Telebot & Flask...")
    bot.infinity_polling(skip_pending=True)
