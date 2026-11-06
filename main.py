import os
import telebot
from flask import Flask
import threading

TG_BOT_TOKEN = "8557665353:AAFgCEM8jBl6gZ1_Jou6JjRqskrdnj_kSrc"
bot = telebot.TeleBot(TG_BOT_TOKEN)

# --- KEEP-ALIVE FLASK SERVER FOR RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Card Splitter Bot is Alive and Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        "🤖 **Card Splitter Bot (With File Support)**\n\n"
        "🚀 **Usage:**\n"
        "1. Text bhej dein: `/split <lines> <cards>`\n"
        "2. Ya koi `.txt` file upload karein aur caption mein line count likh dein (jaise `5`)."
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

def process_and_send(chat_id, text_content, batch_size=9):
    try:
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]
        if not lines:
            bot.send_message(chat_id, "⚠️ File ya text khali hai!")
            return

        batches = [lines[i:i + batch_size] for i in range(0, len(lines), batch_size)]

        response = f"✅ Total Cards: {len(lines)} | Per Batch: {batch_size}\n📦 Total Batches: {len(batches)}\n\n"
        for idx, batch in enumerate(batches, 1):
            response += f"**Batch {idx}:**\n```text\n" + "\n".join(batch) + "\n```\n\n"

        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                bot.send_message(chat_id, response[i:i+4000], parse_mode="Markdown")
        else:
            bot.send_message(chat_id, response, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['split'])
def split_cards(message):
    try:
        parts = message.text.split("\n", 1)
        first_line = parts[0].replace("/split", "").strip()
        
        batch_size = 9
        card_text = ""
        
        if first_line.isdigit():
            batch_size = int(first_line)
            card_text = parts[1] if len(parts) > 1 else ""
        else:
            card_text = message.text.replace("/split", "").strip()
            
        if not card_text and message.reply_to_message:
            card_text = message.reply_to_message.text
            
        if not card_text:
            bot.reply_to(message, "⚠️ Please cards ki list bhejein ya file upload karein!", parse_mode="Markdown")
            return

        process_and_send(message.chat.id, card_text, batch_size)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')
        
        batch_size = 9
        if message.caption and message.caption.isdigit():
            batch_size = int(message.caption)
            
        process_and_send(message.chat.id, file_content, batch_size)
    except Exception as e:
        bot.reply_to(message, f"❌ File read karne mein error aayi: {str(e)}")

if __name__ == "__main__":
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("🤖 Card Splitter Bot on Render is running...")
    bot.infinity_polling()
    
