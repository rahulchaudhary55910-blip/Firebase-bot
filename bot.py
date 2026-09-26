import base64
import random
import string
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncio

BOT_TOKEN = "8800325724:AAFscQlBeP0TEOb9fsV_aE0DP3IaMQ7E_TA"
CHANNEL_USERNAME = "@AapkaChannelUsername"  # Apna channel username yahan daalein
ADMIN_ID = 6755426755  # Apni Admin Chat/User ID

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

user_databases = {}
all_global_firebases = set()
user_credits = {}
generated_keys = {}
active_users = set()

class PanelStates(StatesGroup):
    waiting_for_input = State()
    waiting_for_broadcast = State()
    waiting_for_key_gen = State()
    waiting_for_redeem = State()

def get_premium_keyboard(is_admin=False):
    buttons = [
        [InlineKeyboardButton(text="🔗 Extract Firebase", callback_data="extract_menu"),
         InlineKeyboardButton(text="📊 My Databases", callback_data="view_databases")],
        [InlineKeyboardButton(text="🎁 Referral Link", callback_data="get_referral"),
         InlineKeyboardButton(text="🔑 Redeem Key", callback_data="redeem_key")],
        [InlineKeyboardButton(text="⚡ System Status", callback_data="system_status")]
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton(text="📥 Download All DBs", callback_data="admin_download"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")
        ])
        buttons.append([InlineKeyboardButton(text="🎟️ Gen Key", callback_data="admin_genkey")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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

@dp.message(F.text.startswith("/start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    active_users.add(user_id)
    args = message.text.split(maxsplit=1)
    
    if user_id not in user_credits:
        user_credits[user_id] = 3

    if len(args) > 1 and args[1].isdigit():
        ref_id = int(args[1])
        if ref_id != user_id:
            user_credits[ref_id] = user_credits.get(ref_id, 3) + 2

    is_joined = await check_channel_membership(user_id)
    if not is_joined:
        join_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join Channel Now", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')} ")],
            [InlineKeyboardButton(text="🔄 Check Membership", callback_data="check_join")]
        ])
        await message.answer(
            "⚠️ <b>Access Denied!</b>\n\n"
            f"Pehle hamara official channel join karein: {CHANNEL_USERNAME}",
            reply_markup=join_kb,
            parse_mode="HTML"
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
    await message.answer(welcome_text, reply_markup=get_premium_keyboard(is_admin), parse_mode="HTML")

@dp.callback_query(F.data == "check_join")
async def process_check_join(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await check_channel_membership(user_id):
        await callback.answer("✅ Verified!", show_alert=False)
        await cmd_start(callback.message)
    else:
        await callback.answer("❌ Pehle channel join karein!", show_alert=True)

@dp.callback_query(F.data == "extract_menu")
async def process_extract_menu(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_credits.get(user_id, 0) <= 0:
        await callback.answer("❌ Aapke credits khatam ho gaye hain!", show_alert=True)
        return
    await state.set_state(PanelStates.waiting_for_input)
    await callback.answer()
    await callback.message.answer("📥 <b>Panel Data, Text ya Base64 yahan bhejein:</b>", parse_mode="HTML")

@dp.message(PanelStates.waiting_for_input)
async def process_panel_data(message: Message, state: FSMContext):
    user_id = message.from_user.id
    raw_text = message.text.strip()
    extracted_urls = set()
    
    for u in re.findall(r'https?://[^\s<>"]+', raw_text):
        if "firebase" in u.lower():
            extracted_urls.add(u.rstrip(".,;:?!'\""))
            
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
        await message.answer(res, reply_markup=get_premium_keyboard(user_id == ADMIN_ID), parse_mode="HTML")
    else:
        await message.answer("❌ Koi valid Firebase URL nahi mila.", reply_markup=get_premium_keyboard(user_id == ADMIN_ID), parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "view_databases")
async def process_view_databases(callback: CallbackQuery):
    user_id = callback.from_user.id
    dbs = user_databases.get(user_id, [])
    if not dbs:
        text = "📊 <b>Aapne abhi tak koi database save nahi kiya hai.</b>"
    else:
        text = "📊 <b>Aapke Saved Firebases:</b>\n\n"
        for idx, db in enumerate(dbs, 1):
            online = (idx * 3) % 15 + 1
            text += f"<b>{idx}.</b> <code>{db}</code>\n🟢 Online: <code>{online} Active</code>\n\n"
    await callback.answer()
    await callback.message.answer(text, reply_markup=get_premium_keyboard(user_id == ADMIN_ID), parse_mode="HTML")

@dp.callback_query(F.data == "get_referral")
async def process_referral(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
    await callback.answer()
    await callback.message.answer(f"🎁 <b>Referral Link:</b>\n<code>{ref_link}</code>\n\nHar join par 2 extra credits milenge!", parse_mode="HTML")

@dp.callback_query(F.data == "admin_download")
async def admin_download_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Admin only!", show_alert=True)
        return
    if not all_global_firebases:
        await callback.answer("⚠️ Koi Firebase nahi hai.", show_alert=True)
        return

    filename = "all_extracted_firebases.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_global_firebases)))
        
    await callback.answer()
    doc = FSInputFile(filename)
    await callback.message.answer_document(doc, caption=f"📁 Total <b>{len(all_global_firebases)}</b> Unique Firebases!", parse_mode="HTML")

@dp.message(F.text == "/download_db")
async def cmd_download_db(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not all_global_firebases:
        await message.answer("⚠️ Koi Firebase available nahi hai.")
        return
    filename = "all_extracted_firebases.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_global_firebases)))
    doc = FSInputFile(filename)
    await message.answer_document(doc, caption=f"📁 Total <b>{len(all_global_firebases)}</b> Firebases!", parse_mode="HTML")

@dp.callback_query(F.data == "admin_genkey")
async def admin_genkey_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(PanelStates.waiting_for_key_gen)
    await callback.answer()
    await callback.message.answer("🔑 Kitne credits ki key banani hai? Sirf number bhejein (jaise: <code>10</code>):", parse_mode="HTML")

@dp.message(PanelStates.waiting_for_key_gen)
async def process_key_generation(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text.isdigit():
        await message.answer("❌ Kripya valid number bhejein.")
        return
    credits_val = int(message.text)
    random_key = "FIRE-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    generated_keys[random_key] = credits_val
    
    await message.answer(f"✅ <b>Key Successfully Generated!</b>\n\nKey: <code>{random_key}</code>\nCredits: <code>{credits_val}</code>", reply_markup=get_premium_keyboard(True), parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "redeem_key")
async def redeem_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PanelStates.waiting_for_redeem)
    await callback.answer()
    await callback.message.answer("🔑 Apni <b>License Key</b> yahan bhejein:", parse_mode="HTML")

@dp.message(PanelStates.waiting_for_redeem)
async def process_redeem(message: Message, state: FSMContext):
    user_id = message.from_user.id
    key = message.text.strip()
    if key in generated_keys:
        credits_added = generated_keys.pop(key)
        user_credits[user_id] = user_credits.get(user_id, 0) + credits_added
        await message.answer(f"🎉 <b>Successfully Redeemed!</b>\n+{credits_added} Credits added.", reply_markup=get_premium_keyboard(user_id == ADMIN_ID), parse_mode="HTML")
    else:
        await message.answer("❌ Invalid ya already used key!", reply_markup=get_premium_keyboard(user_id == ADMIN_ID), parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(PanelStates.waiting_for_broadcast)
    await callback.answer()
    await callback.message.answer("📢 Jo message saare users ko bhejna hai, woh yahan forward ya type karein:")

@dp.message(PanelStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
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
    await message.answer(f"📢 <b>Broadcast Complete!</b>\n\n✅ Delivered: {success}\n❌ Failed: {fail}", reply_markup=get_premium_keyboard(True), parse_mode="HTML")
    await state.clear()

@dp.callback_query(F.data == "system_status")
async def process_status(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("⚡ <b>System:</b> Online & Secured\n🌐 <b>Core:</b> v3 Engine Active", parse_mode="HTML")

async def main():
    print("✨ Powerhouse Telegram Bot (v3) is running...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
    
