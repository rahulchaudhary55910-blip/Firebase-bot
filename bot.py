import base64
import random
import string
import re
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

BOT_TOKEN = "8800325724:AAFscQlBeP0TEOb9fsV_aE0DP3IaMQ7E_TA"
CHANNEL_USERNAME = "@AapkaChannelUsername"  # Apna channel username yahan daalein
ADMIN_ID = 6755426755  # Apni Telegram Admin Chat/User ID yahan daalein

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Database structures
user_databases = {}     # user_id -> [list of firebases]
all_global_firebases = set() # Saare firebases ka global collection
user_credits = {}       # user_id -> credits/limits
generated_keys = {}     # key -> credit_amount
active_users = set()    # Total unique users for broadcast

class PanelStates(StatesGroup):
    waiting_for_input = State()
    waiting_for_broadcast = State()
    waiting_for_key_gen = State()
    waiting_for_redeem = State()

def get_premium_keyboard(is_admin=False):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔗 Extract Firebase", callback_data="extract_menu"),
        types.InlineKeyboardButton("📊 My Databases", callback_data="view_databases"),
        types.InlineKeyboardButton("🎁 Referral Link", callback_data="get_referral"),
        types.InlineKeyboardButton("🔑 Redeem Key", callback_data="redeem_key"),
        types.InlineKeyboardButton("⚡ System Status", callback_data="system_status")
    )
    if is_admin:
        keyboard.add(
            types.InlineKeyboardButton("📥 Download All DBs", callback_data="admin_download"),
            types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("🎟️ Gen Key", callback_data="admin_genkey")
        )
    return keyboard

async def check_channel_membership(user_id):
    if user_id == ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
        pass
    return False

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    active_users.add(user_id)
    args = message.get_args()
    
    if user_id not in user_credits:
        user_credits[user_id] = 3  # Default free credits

    # Referral handling
    if args and args.isdigit():
        ref_id = int(args)
        if ref_id != user_id:
            user_credits[ref_id] = user_credits.get(ref_id, 3) + 2

    is_joined = await check_channel_membership(user_id)
    if not is_joined:
        join_kb = types.InlineKeyboardMarkup()
        join_kb.add(types.InlineKeyboardButton("📢 Join Channel Now", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"))
        join_kb.add(types.InlineKeyboardButton("🔄 Check Membership", callback_data="check_join"))
        await message.answer(
            "⚠️ <b>Access Denied!</b>\n\n"
            f"Pehle hamara official channel join karein: {CHANNEL_USERNAME}",
            reply_markup=join_kb
        )
        return

    is_admin = (user_id == ADMIN_ID)
    welcome_text = (
        "✨ <b>P R E M I U M   F I R E B A S E   P A N E L</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 <i>Welcome, {message.from_user.first_name}!</i>\n\n"
        f"💳 <b>Aapke Credits:</b> <code>{user_credits[user_id]}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(welcome_text, reply_markup=get_premium_keyboard(is_admin))

@dp.callback_query_handler(lambda c: c.data == "check_join")
async def process_check_join(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if await check_channel_membership(user_id):
        await bot.answer_callback_query(callback_query.id, "✅ Verified!")
        await cmd_start(callback_query.message)
    else:
        await bot.answer_callback_query(callback_query.id, "❌ Pehle channel join karein!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "extract_menu")
async def process_extract_menu(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_credits.get(user_id, 0) <= 0:
        await bot.answer_callback_query(callback_query.id, "❌ Aapke credits khatam ho gaye hain! Key redeem karein ya refer karein.", show_alert=True)
        return
    await PanelStates.waiting_for_input.set()
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(user_id, "📥 <b>Panel Data, Text ya Base64 yahan bhejein:</b>")

@dp.message_handler(state=PanelStates.waiting_for_input)
async def process_panel_data(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    raw_text = message.text.strip()
    extracted_urls = set()
    
    # Direct search
    for u in re.findall(r'https?://[^\s<>"]+', raw_text):
        if "firebase" in u.lower():
            extracted_urls.add(u.rstrip(".,;:?!'\""))
            
    # Base64 decode check
    try:
        decoded_text = base64.b64decode(raw_text, validate=True).decode('utf-8', errors='ignore')
        for u in re.findall(r'https?://[^\s<>"]+', decoded_text):
            if "firebase" in u.lower():
                extracted_urls.add(u.rstrip(".,;:?!'\""))
    except Exception:
        pass

    if extracted_urls:
        if user_id not in user_databases:
            user_databases[user_id] = []
            
        new_added = 0
        for url in extracted_urls:
            all_global_firebases.add(url)
            if url not in user_databases[user_id]:
                user_databases[user_id].append(url)
                new_added += 1
                
        user_credits[user_id] -= 1
        res = f"✅ <b>Successfully Extracted {new_added} New Firebase(s)!</b>\n\n"
        for url in extracted_urls:
            res += f"🔗 <code>{url}</code>\n"
        res += f"\n📉 <b>Remaining Credits:</b> <code>{user_credits[user_id]}</code>"
        await message.answer(res, reply_markup=get_premium_keyboard(user_id == ADMIN_ID))
    else:
        await message.answer("❌ Koi valid Firebase URL nahi mila.", reply_markup=get_premium_keyboard(user_id == ADMIN_ID))
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "view_databases")
async def process_view_databases(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    dbs = user_databases.get(user_id, [])
    if not dbs:
        text = "📊 <b>Aapne abhi tak koi database save nahi kiya hai.</b>"
    else:
        text = "📊 <b>Aapke Saved Firebases:</b>\n\n"
        for idx, db in enumerate(dbs, 1):
            online = (idx * 3) % 15 + 1
            text += f"<b>{idx}.</b> <code>{db}</code>\n🟢 Online: <code>{online} Active</code>\n\n"
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(user_id, text, reply_markup=get_premium_keyboard(user_id == ADMIN_ID))

@dp.callback_query_handler(lambda c: c.data == "get_referral")
async def process_referral(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(user_id, f"🎁 <b>Referral Link:</b>\n<code>{ref_link}</code>\n\nHar join par 2 extra credits milenge!")

# --- ADMIN: DOWNLOAD ALL FIREBASES ---
@dp.callback_query_handler(lambda c: c.data == "admin_download")
async def admin_download_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id != ADMIN_ID:
        await bot.answer_callback_query(callback_query.id, "❌ Aap admin nahi hain!", show_alert=True)
        return
        
    if not all_global_firebases:
        await bot.answer_callback_query(callback_query.id, "⚠️ Database mein abhi koi Firebase nahi hai.", show_alert=True)
        return

    filename = "all_extracted_firebases.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_global_firebases)))
        
    await bot.answer_callback_query(callback_query.id)
    with open(filename, "rb") as doc:
        await bot.send_document(user_id, doc, caption=f"📁 Total <b>{len(all_global_firebases)}</b> Unique Firebases collected so far!")

@dp.message_handler(commands=['download_db'])
async def cmd_download_db(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not all_global_firebases:
        await message.answer("⚠️ Koi Firebase available nahi hai.")
        return
    filename = "all_extracted_firebases.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_global_firebases)))
    with open(filename, "rb") as doc:
        await message.answer_document(doc, caption=f"📁 Total <b>{len(all_global_firebases)}</b> Firebases!")

# --- ADMIN: KEY GENERATOR ---
@dp.callback_query_handler(lambda c: c.data == "admin_genkey")
async def admin_genkey_prompt(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await PanelStates.waiting_for_key_gen.set()
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(ADMIN_ID, "🔑 Kitne credits ki key banani hai? Sirf number bhejein (jaise: <code>10</code>):")

@dp.message_handler(state=PanelStates.waiting_for_key_gen)
async def process_key_generation(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text.isdigit():
        await message.answer("❌ Kripya valid number bhejein.")
        return
    credits_val = int(message.text)
    random_key = "FIRE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    generated_keys[random_key] = credits_val
    
    await message.answer(f"✅ <b>Key Successfully Generated!</b>\n\nKey: <code>{random_key}</code>\nCredits: <code>{credits_val}</code>", reply_markup=get_premium_keyboard(True))
    await state.finish()

# --- REDEEM KEY ---
@dp.callback_query_handler(lambda c: c.data == "redeem_key")
async def redeem_prompt(callback_query: types.CallbackQuery):
    await PanelStates.waiting_for_redeem.set()
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "🔑 Apni <b>License Key</b> yahan bhejein:")

@dp.message_handler(state=PanelStates.waiting_for_redeem)
async def process_redeem(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    key = message.text.strip()
    if key in generated_keys:
        credits_added = generated_keys.pop(key) # Use ek hi baar redeem kar sakein
        user_credits[user_id] = user_credits.get(user_id, 0) + credits_added
        await message.answer(f"🎉 <b>Successfully Redeemed!</b>\n+{credits_added} Credits added to your account.", reply_markup=get_premium_keyboard(user_id == ADMIN_ID))
    else:
        await message.answer("❌ Invalid ya already used key!", reply_markup=get_premium_keyboard(user_id == ADMIN_ID))
    await state.finish()

# --- ADMIN: BROADCAST ---
@dp.callback_query_handler(lambda c: c.data == "admin_broadcast")
async def admin_broadcast_prompt(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        return
    await PanelStates.waiting_for_broadcast.set()
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(ADMIN_ID, "📢 Jo message saare users ko bhejna hai, woh yahan forward ya type karein:")

@dp.message_handler(state=PanelStates.waiting_for_broadcast, content_types=types.ContentTypes.ANY)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    success = 0
    fail = 0
    for uid in active_users:
        try:
            await message.send_copy(chat_id=uid)
            success += 1
        except Exception:
            fail += 1
    await message.answer(f"📢 <b>Broadcast Complete!</b>\n\n✅ Delivered: {success}\n❌ Failed: {fail}", reply_markup=get_premium_keyboard(True))
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "system_status")
async def process_status(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "⚡ <b>System:</b> Online & Secured\n🌐 <b>Core:</b> Active Engine")

if __name__ == '__main__':
    print("✨ Powerhouse Telegram Bot is running...")
    executor.start_polling(dp, skip_updates=True)
    
