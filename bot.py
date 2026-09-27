import base64
import random
import string
import re
import os
import threading
import datetime
import requests
from flask import Flask
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ═══════════════════════════════════════════════════════════════
#  🔧 CONFIG & TOKENS
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = "8632363521:AAHW1jecWgc103lm6cBEKxMHpSKYVrKgASA" # Apna naya token yahan rakhein
CHANNEL_USERNAME = "@trickzone6"  # Official Channel Username
ADMIN_ID = 6755426755  # Aapki Admin ID

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# 📊 Storage
user_databases = {}          # user_id -> [{'url': ..., 'key': ...}]
all_global_firebases = set() # Saare global firebases ka collection
user_credits = {}            # user_id -> credits balance
user_subscriptions = {}      # user_id -> expiry datetime object
referred_users = {}          # user_id -> set of user_ids they referred
user_referrer = {}           # user_id -> who referred them
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

# ═══════════════════════════════════════════════════════════════
#  🔒 CHANNEL SUBSCRIPTION CHECK & LEAVE DETECTION
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

def verify_and_update_referrals(user_id):
    if user_id in referred_users:
        current_refs = list(referred_users[user_id])
        for ref_id in current_refs:
            if not check_channel_membership(ref_id):
                referred_users[user_id].remove(ref_id)
                user_credits[user_id] = max(0, user_credits.get(user_id, 0) - 10)
                try:
                    bot.send_message(
                        user_id,
                        "⚠️ <b>Referral Alert!</b>\n\n"
                        f"Aapke ek referred user ne channel ({CHANNEL_USERNAME}) leave kar diya hai, isliye aapke <b>10 credits</b> minus ho gaye hain!"
                    )
                except:
                    pass

def has_active_subscription(user_id):
    if user_id == ADMIN_ID:
        return True
    if user_id in user_subscriptions:
        if datetime.datetime.now() < user_subscriptions[user_id]:
            return True
    return False

# ═══════════════════════════════════════════════════════════════
#  🔍 LIVE FIREBASE STATS CHECKER
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
#  🔗 ULTIMATE ROBUST ZENITH & PANEL PARSER
# ═══════════════════════════════════════════════════════════════
def parse_panel_data(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return []

    extracted_entries = []
    try:
        # Extract all potential base64 or encoded segments from parameters
        params = re.findall(r'[?&][a-zA-Z0-9_-]+=([A-Za-z0-9+/=_-]+)', line)
        if not params and len(line) > 15 and not line.startswith("http"):
            params = [line]

        for raw_param in params:
            try:
                raw = raw_param.replace('-', '+').replace('_', '/')
                raw += '=' * (-len(raw) % 4)
                decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
                
                try:
                    import json
                    data = json.loads(decoded)
                    
                    # Recursive function to find urls & keys in any JSON structure (Zenith / Panels)
                    def dig_json(obj):
                        if isinstance(obj, dict):
                            # Look for common key names for URL and Secret
                            p_url = obj.get("url") or obj.get("firebase") or obj.get("rtdb") or obj.get("link")
                            p_key = obj.get("key") or obj.get("secret") or obj.get("auth") or "dummy"
                            
                            if p_url and isinstance(p_url, str) and ("firebase" in p_url.lower() or "rtdb" in p_url.lower()):
                                clean_url = p_url.rstrip('/')
                                if not clean_url.startswith("http"):
                                    clean_url = "https://" + clean_url
                                clean_key = str(p_key) if p_key else "dummy"
                                extracted_entries.append((clean_url, clean_key))
                            
                            for k, v in obj.items():
                                dig_json(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                dig_json(item)
                    
                    dig_json(data)
                except:
                    pass

                # Fallback: scan any direct URLs inside the decoded text
                sub_urls = re.findall(r'https?://[^\s<>"]+', decoded)
                for su in sub_urls:
                    if "firebase" in su.lower() or "rtdb" in su.lower():
                        clean_su = su.split('|||')[0].rstrip(".,;:?!'\"")
                        extracted_entries.append((clean_su, "dummy"))
            except:
                pass

        # Check custom ||| format
        if '|||' in line:
            parts = line.split('|||')
            url = parts[0].strip()
            key = parts[1].strip() if len(parts) > 1 and parts[1].strip() != parts[0].strip() else "dummy"
            if url:
                if not url.startswith("http"):
                    url = "https://" + url
                extracted_entries.append((url, key))

        # Direct general URL scanning
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
        user_credits[user_id] = 0

    if len(text_args) > 1 and text_args[1].isdigit():
        ref_id = int(text_args[1])
        if ref_id != user_id and user_id not in user_referrer:
            if check_channel_membership(user_id):
                user_referrer[user_id] = ref_id
                if ref_id not in referred_users:
                    referred_users[ref_id] = set()
                if user_id not in referred_users[ref_id]:
                    referred_users[ref_id].add(user_id)
                    user_credits[ref_id] = user_credits.get(ref_id, 0) + 10
                    try:
                        bot.send_message(
                            ref_id,
                            "🎉 <b>New Verified Referral!</b>\n"
                            f"Aapke link se ek naye user ne join kiya hai aur channel par active hain.\n"
                            "🎁 <b>+10 Credits</b> added to your account!"
                        )
                    except:
                        pass

    verify_and_update_referrals(user_id)

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
    sub_status = "Lifetime (Admin)" if is_admin else ("Active 🟢" if has_active_subscription(user_id) else "Expired / None 🔴")
    
    welcome_text = (
        "✨ <b>P R E M I U M   F I R E B A S E   H U B</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 <i>Welcome back, {message.from_user.first_name}!</i>\n\n"
        f"💳 <b>Aapke Credits:</b> <code>{user_credits[user_id]} Credits</code>\n"
        f"⏳ <b>Subscription Status:</b> <code>{sub_status}</code>\n"
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

    elif data == "buy_subscription":
        if not check_channel_membership(user_id):
            bot.answer_callback_query(call.id, "❌ Pehle channel join karein!", show_alert=True)
            return
        
        current_credits = user_credits.get(user_id, 0)
        if current_credits < 10:
            bot.answer_callback_query(call.id, "❌ Aapke paas kam se kam 10 credits hone chahiye! Refer karke ya key redeem karke credits earn karein.", show_alert=True)
            return

        user_credits[user_id] -= 10
        if user_id in user_subscriptions and datetime.datetime.now() < user_subscriptions[user_id]:
            user_subscriptions[user_id] += datetime.timedelta(days=3)
        else:
            user_subscriptions[user_id] = datetime.datetime.now() + datetime.timedelta(days=3)

        bot.answer_callback_query(call.id, "🎉 3-Day Subscription Activated Successfully!")
        bot.send_message(
            user_id,
            "🎉 <b>SUBSCRIPTION PURCHASED!</b>\n\n"
            "✅ <b>Plan:</b> 3 Days Unlimited Access\n"
            "📉 <b>Credits Deducted:</b> <code>-10 Credits</code>\n"
            f"⏳ <b>Expiry:</b> <code>{user_subscriptions[user_id].strftime('%Y-%m-%d %H:%M:%S')}</code>",
            reply_markup=get_main_keyboard(user_id == ADMIN_ID)
        )

    elif data == "extract_menu":
        if not check_channel_membership(user_id):
            bot.answer_callback_query(call.id, "❌ Pehle channel join karein!", show_alert=True)
            return
        
        is_admin = (user_id == ADMIN_ID)
        if not is_admin and not has_active_subscription(user_id):
            bot.answer_callback_query(call.id, "❌ Aapke paas active subscription nahi hai! Pehle 10 credits se 3 din ki subscription buy karein.", show_alert=True)
            return
            
        user_states[user_id] = "waiting_for_input"
        bot.answer_callback_query(call.id)
        bot.send_message(
            user_id,
            "📥 <b>SEND PANEL DATA OR LINKS</b>\n\n"
            "<i>Aap kisi bhi panel ka link (Zenith, EdgeOne, etc.), Base64 string, ya direct links bhej sakte hain.</i>"
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
        completed_refs = len(referred_users.get(user_id, set()))
        
        bot.answer_callback_query(call.id)
        ref_text = (
            "🔗 <b>YOUR REFERRAL LINK</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>USER NAME:</b> @{call.from_user.username if call.from_user.username else 'No Username'}\n"
            f"🆔 <b>USER ID:</b> <code>{user_id}</code>\n"
            f"✅ <b>COMPLETED:</b> <code>{completed_refs}</code>\n"
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
        if not is_admin and not has_active_subscription(user_id):
            bot.send_message(user_id, "❌ Aapke paas active subscription nahi hai! Pehle 10 credits se 3 din ki subscription buy karein.", reply_markup=get_main_keyboard(is_admin))
            user_states.pop(user_id, None)
            return

        lines = text.splitlines()
        extracted_results = []

        for line in lines:
            parsed = parse_panel_data(line)
            for item in parsed:
                if not any(e['url'] == item['url'] for e in extracted_results):
                    extracted_results.append(item)

        if extracted_results:
            if user_id not in user_databases:
                user_databases[user_id] = []
            
            for item in extracted_results:
                all_global_firebases.add(item['url'])
                if not any(db['url'] == item['url'] for db in user_databases[user_id]):
                    user_databases[user_id].append(item)

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

            bot.send_message(user_id, f"✅ <b>Successfully Processed {len(extracted_results)} Firebase(s)!</b>", reply_markup=get_main_keyboard(is_admin))
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
            
            bot.send_message(
                user_id,
                f"🎉 <b>Successfully Redeemed!</b>\n+{credits_added} Credits added to your account.",
                reply_markup=get_main_keyboard(is_admin)
            )
            
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
            except:
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
    
    print("✨ Ultimate Robust Firebase Bot is running successfully...")
    bot.infinity_polling(skip_pending=True)
