import os
import telebot
from flask import Flask
import threading
import json as _json
import time

TG_BOT_TOKEN = "9014709821:AAEOl-cT2pxipHS0faW_pLD-bV1FBQxBRcc"
ADMIN_CHAT_ID = 6755426755
bot = telebot.TeleBot(TG_BOT_TOKEN)

USERS_FILE = "bot_users.json"

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return _json.load(f)
        except:
            pass
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        _json.dump(data, f)

def save_user(user_id):
    data = load_json(USERS_FILE)
    users = set(data.get("users", []))
    if user_id not in users:
        users.add(user_id)
        data["users"] = list(users)
        save_json(USERS_FILE, data)

# --- KEEP-ALIVE FLASK SERVER FOR RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Card Splitter Bot with Broadcast is Alive and Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_user(message.from_user.id)
    user_name = message.from_user.first_name or "Zaib"
    user_id = message.from_user.id
    
    help_text = (
        "╔════════════════════════════════════╗\n"
        "     🔥 𝑪𝑨𝑹𝑫 𝑺𝑷𝑳𝑰𝑻𝑻𝑬𝑹 𝑼𝑻𝑰𝑳𝑰𝑻𝒀 🔥     \n"
        "╚════════════════════════════════════╝\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✰ 𝑼𝒔𝒆𝒓      ➔ {user_name} ⭐\n"
        f"✰ 𝑰𝑫        ➔ <code>{user_id}</code>\n"
        "✰ 𝑺𝒕𝒂𝒕𝒖𝒔    ➔ ✅ 𝑨𝒄𝒕𝒊𝒗𝒆 (𝑷𝒓𝒆𝒎𝒊𝒖𝒎)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 𝑯𝑶𝑾 𝑻𝑶 𝑼𝑺𝑬 :\n\n"
        "• 📝 <b>Text Mode:</b>\n"
        "  <code>/split &lt;lines_count&gt;</code> likh kar niche cards paste karein.\n"
        "  <i>Example:</i> <code>/split 5</code>\n\n"
        "• 📁 <b>File Mode (.txt):</b>\n"
        "  1. Koi bhi <code>.txt</code> file upload karein aur caption mein <code>/split &lt;lines_count&gt;</code> likhein.\n"
        "  2. Ya pehle file bhejein, phir us par reply karke <code>/split &lt;lines_count&gt;</code> likhein.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.reply_to(message, help_text, parse_mode="HTML")

def process_and_send(chat_id, text_content, batch_size=9):
    try:
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]
        if not lines:
            bot.send_message(chat_id, "⚠️ File ya text khali hai!", parse_mode="HTML")
            return

        batches = [lines[i:i + batch_size] for i in range(0, len(lines), batch_size)]

        response = f"<b>✅ Total Cards:</b> {len(lines)} | <b>Per Batch:</b> {batch_size}\n<b>📦 Total Batches:</b> {len(batches)}\n\n"
        for idx, batch in enumerate(batches, 1):
            response += f"<b>Batch {idx}:</b>\n<pre>" + "\n".join(batch) + "</pre>\n\n"

        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                bot.send_message(chat_id, response[i:i+4000], parse_mode="HTML")
        else:
            bot.send_message(chat_id, response, parse_mode="HTML")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(commands=['split'])
def split_cards(message):
    save_user(message.from_user.id)
    try:
        # Case 1: Reply to a document file with "/split 5"
        if message.reply_to_message and message.reply_to_message.document:
            parts = message.text.split()
            batch_size = 9
            if len(parts) > 1 and parts[1].isdigit():
                batch_size = int(parts[1])
            
            doc = message.reply_to_message.document
            file_info = bot.get_file(doc.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_content = downloaded_file.decode('utf-8', errors='ignore')
            
            process_and_send(message.chat.id, file_content, batch_size)
            return

        # Case 2: Direct text split
        parts = message.text.split("\n", 1)
        first_line = parts[0].replace("/split", "").strip()
        
        batch_size = 9
        card_text = ""
        
        if first_line.isdigit():
            batch_size = int(first_line)
            card_text = parts[1] if len(parts) > 1 else ""
        else:
            card_text = message.text.replace("/split", "").strip()
            
        if not card_text and message.reply_to_message and message.reply_to_message.text:
            card_text = message.reply_to_message.text
            
        if not card_text:
            bot.reply_to(message, "⚠️ Please cards ki list bhejein ya file par reply karein!", parse_mode="HTML")
            return

        process_and_send(message.chat.id, card_text, batch_size)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    save_user(message.from_user.id)
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')
        
        batch_size = 9
        caption = message.caption or ""
        
        if caption.startswith("/split"):
            parts = caption.split()
            if len(parts) > 1 and parts[1].isdigit():
                batch_size = int(parts[1])
        elif caption.isdigit():
            batch_size = int(caption)
            
        process_and_send(message.chat.id, file_content, batch_size)
    except Exception as e:
        bot.reply_to(message, f"❌ File read karne mein error aayi: <code>{str(e)}</code>", parse_mode="HTML")

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    save_user(message.from_user.id)
    if message.from_user.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ You are not authorized to use this command.", parse_mode="HTML")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Please provide message to broadcast. Example:\n<code>/broadcast Hello users!</code>", parse_mode="HTML")
        return
    
    bc_text = parts[1]
    data = load_json(USERS_FILE)
    users = data.get("users", [])
    success = 0
    fail = 0
    
    status_msg = bot.reply_to(message, f"📢 Broadcasting to {len(users)} users...", parse_mode="HTML")
    
    for uid in users:
        try:
            bot.send_message(uid, f"📢 <b>Announcement:</b>\n\n{bc_text}", parse_mode="HTML")
            success += 1
            time.sleep(0.05)
        except:
            fail += 1
            
    bot.edit_message_text(f"✅ <b>Broadcast Completed!</b>\n\nSuccessful: {success}\nFailed: {fail}", chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="HTML")

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("🤖 Card Splitter Bot with Broadcast & File Support is running...")
    bot.infinity_polling()
    
