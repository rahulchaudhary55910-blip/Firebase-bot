import base64
import random
import string
import re
import os
import threading
import requests
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════
#  🔧 CONFIG & TOKENS
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = "8632363521:AAHmUpYvXtViGysiVRkhXiII_2SxcBnorIw"
CHANNEL_USERNAME = "@trickzone6"  # Apna channel username yahan daalein
ADMIN_ID = 6755426755  # Aapki Admin ID

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# 📊 Storage
user_databases = {}          # user_id -> [{'url': ..., 'key': ...}]
all_global_firebases = set() # Saare global firebases ka collection
user_credits = {}            # user_id -> remaining extractions/credits
generated_keys = {}          # key -> credit amount
active_users = set()         # Total unique users for broadcast
user_states = {}             # Temporary state handler for text inputs

# ═══════════════════════════════════════════════════════════════
#  🌐 DUMMY WEB SERVER FOR RENDER (Port Binding Fix)
# ═══════════════════════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Firebase Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ═══════════════════════════════════════════════════════════════
#  🎨 PREMIUM KEYBOARDS
# ═══════════════════════════════════════════════════════════════
def get_main_keyboard(is_admin=False):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🚀 Extract From Web Panel", callback_data="extract_menu"),
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

# ═══════════════════════════════════════════════════════════════
#  🔒 CHANNEL SUBSCRIPTION CHECK
# ═══════════════════════════════════════════════════════════════
def check_channel_membership(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

# ═══════════════════════════════════════════════════════════════
#  🔍 LIVE FIREBASE STATS CHECKER (Connections & Online Count)
# ═══════════════════════════════════════════════════════════════
def check_firebase_stats(url, key):
    total, online = 0, 0
    try:
        clean_url = url.rstrip('/')
        clients_url = f"{clean_url}/clients.json"
        if key and key != "dummy":
            clients_url += f"?auth={key}"
        
        res = requests.get(clients_url, timeout=6)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict) and data:
                total = len(data)
                online = sum(1 for d in data.values() if isinstance(d, dict) and d.get("status"))
        elif res.status_code == 401 and key and key != "dummy":
            res2 = requests.get(f"{clean_url}/clients.json", timeout=6)
            if res2.status_code == 200:
                data2 = res2.json()
                if isinstance(data2, dict) and data2:
                    total = len(data2)
                    online = sum(1 for d in data2.values() if isinstance(d, dict) and d.get("status"))
    except:
        pass
    return total, online

# ═══════════════════════════════════════════════════════════════
#  🔗 ADVANCED CLEAN PARSER FOR URL & KEY
# ═══════════════════════════════════════════════════════════════
def parse_panel_data(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return []

    extracted_entries = []
    try:
        if "?" in line or "=" in line:
            params = re.findall(r'[?&](?:share|s|m|data|payload)=([A-Za-z0-9+/=_-]+)', line)
            if not params and len(line) > 20 and not line.startswith("http"):
                params = [line]

            for raw_param in params:
                try:
                    raw = raw_param.replace('-', '+').replace('_', '/')
                    raw += '=' * (-len(raw) % 4)
                    decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
                    
                    try:
                        import json
                        data = json.loads(decoded)
                        if isinstance(data, dict) and "panels" in data:
                            for panel in data["panels"]:
                                if isinstance(panel, dict):
                                    p_url = panel.get("url", "").rstrip('/')
                                    p_key = panel.get("key", "dummy") or "dummy"
                                    if p_url:
                                        if not p_url.startswith("http"):
                                            p_url = "https://" + p_url
                                        extracted_entries.append((p_url, p_key))
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    p_url = item.get("url", "").rstrip('/')
                                    p_key = item.get("key", "dummy") or "dummy"
                                    if p_url:
                                        if not p_url.startswith("http"):
                                            p_url = "https://" + p_url
                                        extracted_entries.append((p_url, p_key))
                        elif isinstance(data, dict) and "url" in data:
                            p_url = data.get('url', '').rstrip('/')
                            p_key = data.get('key', 'dummy') or "dummy"
                            if p_url:
                                if not p_url.startswith("http"):
                                    p_url = "https://" + p_url
                                extracted_entries.append((p_url, p_key))
                    except:
                        sub_urls = re.findall(r'https?://[^\s<>"]+', decoded)
                        for su in sub_urls:
                            if "firebase" in su.lower() or "rtdb" in su.lower():
                                clean_su = su.split('|||')[0].rstrip(".,;:?!'\"")
                                extracted_entries.append((clean_su, "dummy"))
                except:
                    pass

        if '|||' in line:
            parts = line.split('|||')
            url = parts[0].strip()
            key = parts[1].strip() if len(parts) > 1 and parts[1].strip() != parts[0].strip() else "dummy"
            if url:
                if not url.startswith("http"):
                    url = "https://" + url
                extracted_entries.append((url, key))

        general_urls = re.findall(r'https?://[^\s<>"]+', line)
        for u in general_urls:
            if "firebase" in u.lower() or "rtdb" in u.lower():
                clean_url = u.split('|||')[0].rstrip(".,;:?!'\"")
                if not any(entry[0] == clean_url for entry in extracted_entries):
                    extracted_entries.append((clean_url, "dummy"))
    except:
        pass

    final_clean = []
    for url, key in extracted_entries:
        if "firebase" in url.lower() or "rtdb" in url.lower():
            if not any(e['url'] == url for e in final_clean):
                final_clean.append({'url': url, 'key': key})

    return final_clean

# ═══════════════════════════════════════════════════════════════
#  🚀 BOT COMMANDS & FLOW
# ═══════════════════════════════════════════════════════════════
@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    active_users.add(user_id)
    text_args = message.text.split()
    
    if user_id not in user_credits:
        user_credits[user_id] = 5

    if len(text_args) > 1 and text_args[1].isdigit():
        ref_id = int(text_args[1])
        if ref_id != user_id:
            user_credits[ref_id] = user_credits.get(ref_id, 5) + 3

    if not check_channel_membership(user_id):
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

    is_admin = (user_id == ADMIN_ID)
    welcome_text = (
        "✨ <b>P R E M I U M   F I R E B A S E   H U B</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 <i>Welcome back, {message.from_user.first_name}!</i>\n\n"
        f"💎 <b>Aapke Available Credits:</b> <code>{'Unlimited (Admin)' if is_admin else user_credits[user_id]}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Select an option from the dashboard below:</i>"
    )
    bot.send_message(user_id, welcome_text, reply_markup=get_main_keyboard(is_admin))

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "check_join":
        if check_channel_membership(user_id):
            bot.answer_callback_query(call.id, "✅ Verification Successful!")
            cmd_start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Aapne abhi tak channel join nahi kiya hai!", show_alert=True)

    elif data == "extract_menu":
        if not check_channel_membership(user_id):
            bot.answer_callback_query(call.id, "❌ Pehle channel join karein!", show_alert=True)
            return
        is_admin = (user_id == ADMIN_ID)
        if not is_admin and user_credits.get(user_id, 0) <= 0:
            bot.answer_callback_query(call.id, "❌ Aapke credits khatam ho chuke hain! Key redeem karein ya refer karein.", show_alert=True)
            return
            
        user_states[user_id] = "waiting_for_input"
        bot.answer_callback_query(call.id)
        bot.send_message(
            user_id,
            "📥 <b>SEND PANEL DATA OR LINKS</b>\n\n"
            "<i>Aap Base64 encoded string, ?s=, ?m= formats, web panel text, ya direct links bhej sakte hain.</i>\n"
            "⚡ <i>Normal users ek baar mein max 5 links bhej sakte hain.</i>"
        )

    elif data == "view_databases":
        dbs = user_databases.get(user_id, [])
        if not dbs:
            text = "📊 <b>YOUR HISTORY & DATABASES</b>\n\n⚠️ Aapne abhi tak koi bhi Firebase extract nahi kiya hai."
            bot.answer_callback_query(call.id)
            bot.send_message(user_id, text, reply_markup=get_main_keyboard(user_id == ADMIN_ID))
        else:
            filename = f"my_firebases_{user_id}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# Your Extracted Firebases — User ID: {user_id}\n\n")
                for item in dbs:
                    if item['key'] and item['key'] != "dummy":
                        f.write(f"{item['url']}|||{item['key']}\n")
                    else:
                        f.write(f"{item['url']}\n")
            
            bot.answer_callback_query(call.id)
            with open(filename, "rb") as doc:
                bot.send_document(
                    user_id, doc, 
                    caption=f"📊 <b>Aapke Total Saved Firebases:</b> <code>{len(dbs)}</code>",
                    reply_markup=get_main_keyboard(user_id == ADMIN_ID)
                )

    elif data == "get_referral":
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        bot.answer_callback_query(call.id)
        bot.send_message(
            user_id,
            "🎁 <b>REFERRAL PROGRAM & RULES</b>\n\n"
            "Apne dosto ko apna unique link share karein. Har naye user ke join karne par aapko <b>+3 Extra Credits</b> milenge!\n\n"
            f"🔗 <b>Your Link:</b>\n<code>{ref_link}</code>"
        )

    elif data == "help_menu":
        bot.answer_callback_query(call.id)
        bot.send_message(
            user_id,
            "ℹ️ <b>HELP & RULES GUIDE</b>\n\n"
            "1️⃣ <b>Subscription:</b> Bot use karne ke liye official channel join rakhna zaroori hai.\n"
            "2️⃣ <b>Extraction Limit:</b> Normal users ek baar mein maximum 5 links tak process kar sakte hain.\n"
            "3️⃣ <b>Referral:</b> Link share karke apne credits badhayein.\n"
            "4️⃣ <b>Security:</b> Har extracted firebase automatically secure database mein log ho jata hai."
        )

    elif data == "admin_download":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        if not all_global_firebases:
            bot.answer_callback_query(call.id, "⚠️ Database mein koi firebase nahi hai.", show_alert=True)
            return
        filename = "all_admin_firebases.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(all_global_firebases)))
        bot.answer_callback_query(call.id)
        with open(filename, "rb") as doc:
            bot.send_document(user_id, doc, caption=f"📁 Total <b>{len(all_global_firebases)}</b> Unique Firebases Collected Across All Users!")

    elif data == "admin_genkey":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        user_states[user_id] = "waiting_for_key_gen"
        bot.answer_callback_query(call.id)
        bot.send_message(ADMIN_ID, "🔑 Kitne credits ki key banani hai? Sirf number bhejein (jaise: <code>10</code>):")

    elif data == "redeem_key":
        user_states[user_id] = "waiting_for_redeem"
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "🔑 Apni <b>License Key</b> yahan bhejein:")

    elif data == "admin_broadcast":
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Access Denied!", show_alert=True)
            return
        user_states[user_id] = "waiting_for_broadcast"
        bot.answer_callback_query(call.id)
        bot.send_message(ADMIN_ID, "📢 Jo message saare users ko bhejna hai, woh yahan forward ya type karein:")

    elif data == "system_status":
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "⚡ <b>System Status:</b> Operational 🟢\n🔒 <b>Security:</b> Fully Encrypted\n🌐 <b>Core:</b> Universal Engine Active")

@bot.message_handler(commands=['download_db'])
def cmd_download_db(message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        return
    if not all_global_firebases:
        bot.send_message(message.chat.id, "⚠️ Koi Firebase available nahi hai.")
        return
    filename = "all_admin_firebases.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_global_firebases)))
    with open(filename, "rb") as doc:
        bot.send_document(message.chat.id, doc, caption=f"📁 Total <b>{len(all_global_firebases)}</b> Firebases Exported!")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    if not check_channel_membership(user_id):
        bot.send_message(user_id, "⚠️ Pehle channel join karein taaki aap bot access kar sakein.")
        return

    state = user_states.get(user_id)
    text = message.text.strip() if message.text else ""
    is_admin = (user_id == ADMIN_ID)

    if state == "waiting_for_input":
        lines = text.splitlines()
        extracted_results = []
        
        if not is_admin and len(lines) > 5:
            lines = lines[:5]

        for line in lines:
            parsed = parse_panel_data(line)
            for item in parsed:
                if not any(e['url'] == item['url'] for e in extracted_results):
                    extracted_results.append(item)

        if extracted_results:
            if user_id not in user_databases:
                user_databases[user_id] = []
            
            new_added = 0
            for item in extracted_results:
                all_global_firebases.add(item['url'])
                if not any(db['url'] == item['url'] for db in user_databases[user_id]):
                    user_databases[user_id].append(item)
                    new_added += 1

            if not is_admin:
                user_credits[user_id] = max(0, user_credits[user_id] - 1)

            for idx, item in enumerate(extracted_results, 1):
                total, online = check_firebase_stats(item['url'], item['key'])
                
                res = (
                    f"✨ <b>FIREBASE EXTRACTED #{idx}</b> ✨\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔗 <b>URL:</b> <code>{item['url']}</code>\n"
                    f"🔑 <b>Key:</b> <code>{item['key']}</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📱 <b>Total Connections:</b> <code>{total}</code>\n"
                    f"🟢 <b>Online Connections:</b> <code>{online}</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                bot.send_message(user_id, res)

            final_msg = f"✅ <b>Successfully Processed {len(extracted_results)} Firebase(s)!</b>"
            if not is_admin:
                final_msg += f"\n📉 <b>Remaining Credits:</b> <code>{user_credits[user_id]}</code>"
            
            bot.send_message(user_id, final_msg, reply_markup=get_main_keyboard(is_admin))
        else:
            bot.send_message(user_id, "❌ Koi valid Firebase URL ya panel data nahi mila.", reply_markup=get_main_keyboard(is_admin))
        user_states.pop(user_id, None)

    elif state == "waiting_for_key_gen":
        if user_id != ADMIN_ID:
            user_states.pop(user_id, None)
            return
        if not text.isdigit():
            bot.send_message(user_id, "❌ Kripya sirf valid number bhejein.")
            return
        credits_val = int(text)
        random_key = "FIRE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        generated_keys[random_key] = credits_val
        bot.send_message(
            user_id,
            f"✅ <b>License Key Generated Successfully!</b>\n\n"
            f"🔑 Key: <code>{random_key}</code>\n"
            f"💎 Credits: <code>{credits_val}</code>",
            reply_markup=get_main_keyboard(True)
        )
        user_states.pop(user_id, None)

    elif state == "waiting_for_redeem":
        if text in generated_keys:
            credits_added = generated_keys.pop(text)
            user_credits[user_id] = user_credits.get(user_id, 0) + credits_added
            
            # 🎉 Send success message to the user
            bot.send_message(
                user_id,
                f"🎉 <b>Successfully Redeemed!</b>\n+{credits_added} Credits added to your account.",
                reply_markup=get_main_keyboard(is_admin)
            )
            
            # 📢 Notify Admin about the key redemption
            user_name = message.from_user.first_name
            username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
            admin_notification = (
                "🔔 <b>NEW KEY REDEEMED!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> {user_name} ({username})\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"🔑 <b>Redeemed Key:</b> <code>{text}</code>\n"
                f"💎 <b>Credits Added:</b> <code>+{credits_added}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                bot.send_message(ADMIN_ID, admin_notification)
            except Exception:
                pass
        else:
            bot.send_message(user_id, "❌ Invalid ya already used key!", reply_markup=get_main_keyboard(is_admin))
        user_states.pop(user_id, None)

    elif state == "waiting_for_broadcast":
        if user_id != ADMIN_ID:
            user_states.pop(user_id, None)
            return
        success, fail = 0, 0
        for uid in active_users:
            try:
                bot.copy_message(chat_id=uid, from_chat_id=user_id, message_id=message.message_id)
                success += 1
            except Exception:
                fail += 1
        bot.send_message(
            user_id,
            f"📢 <b>Broadcast Completed!</b>\n\n✅ Delivered: {success}\n❌ Failed: {fail}",
            reply_markup=get_main_keyboard(True)
        )
        user_states.pop(user_id, None)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("✨ Ultimate Premium Firebase Bot with Admin Alerts is running...")
    bot.infinity_polling(skip_pending=True)
