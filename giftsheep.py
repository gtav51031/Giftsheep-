import os
import json
import time
import random
import threading
import re
import requests
import telebot
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, jsonify

# ============================================
# 🔐 إعدادات البوت الأساسية
# ============================================
BOT_TOKEN = "8738226982:AAFyBMXGSFXz1stdeWQfb4J-hnrW3kr7RKE"
OWNER_ID = int(6366853738)
CHANNEL_TG = "thaish12"
CHANNEL_YT = "https://youtube.com/@tahish159?si=5ehTRVzB7WOnOj5s"
BOT_USERNAME = "Giftsheep1_bot"
TOKEN_API = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJndGF2NTEwMzFAZ21haWwuY29tIn0.LR0lbOdO6Qq5d_4X0jKUC6mx18PP1-w2ChvBXQTETw0"

INITIAL_POINTS = 50
REFERRAL_POINTS = 20
YOUTUBE_VERIFY_KEY = "youtube_verified"
YOUTUBE_VERIFY_DAYS = 7

# ============================================
# 🔥 إعدادات GiftSheep
# ============================================
FIREBASE_API_KEY = "AIzaSyDR1RcaMP9IOmIy7i_daFPNr3e7kmWid6o"
BASE_URL = "https://us-central1-gift-sheep-b21df.cloudfunctions.net"
SPIN_URL = f"{BASE_URL}/claimSpinReward"
TOKEN_TYPE = "Bearer"

# ============================================
# 📂 ملفات البيانات
# ============================================
DATA_DIR = "user_data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_user_file(user_id, filename):
    return os.path.join(DATA_DIR, f"{filename}_{user_id}.json")

# ---------------- نقاط المستخدم ----------------
def load_user_points(user_id):
    filepath = get_user_file(user_id, "points")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f).get("points", INITIAL_POINTS)
    return INITIAL_POINTS

def save_user_points(user_id, points):
    with open(get_user_file(user_id, "points"), "w") as f:
        json.dump({"points": points}, f)

# ---------------- إعدادات المستخدم ----------------
def load_user_settings(user_id):
    filepath = get_user_file(user_id, "user_settings")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

def save_user_settings(user_id, data):
    with open(get_user_file(user_id, "user_settings"), "w") as f:
        json.dump(data, f, indent=2)

def get_user_setting(user_id, key, default=None):
    return load_user_settings(user_id).get(key, default)

def set_user_setting(user_id, key, value):
    data = load_user_settings(user_id)
    data[key] = value
    save_user_settings(user_id, data)

# ---------------- جلسات المستخدمين ----------------
def load_user_sessions():
    filepath = os.path.join(DATA_DIR, "user_sessions.json")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

def save_user_sessions(sessions):
    with open(os.path.join(DATA_DIR, "user_sessions.json"), "w") as f:
        json.dump(sessions, f, indent=2)

# ---------------- نظام الإحالات ----------------
def load_referral_data():
    filepath = os.path.join(DATA_DIR, "referral_data.json")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

def save_referral_data(data):
    with open(os.path.join(DATA_DIR, "referral_data.json"), "w") as f:
        json.dump(data, f, indent=2)

def get_referral_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start={user_id}"

def process_referral_new_user(new_user_id, referrer_id):
    if str(new_user_id) == str(referrer_id):
        return False, "❌ لا يمكنك إحالة نفسك!"
    if not is_subscribed_telegram(new_user_id) or not is_subscribed_youtube(new_user_id):
        return False, "❌ يجب الاشتراك في القناة وتأكيد يوتيوب أولاً!"

    referral_data = load_referral_data()
    if str(new_user_id) in referral_data.get("referred_users", {}):
        return False, "⚠️ هذا المستخدم تمت إحالته مسبقاً!"

    if str(referrer_id) not in referral_data.get("referrals", {}):
        referral_data.setdefault("referrals", {})[str(referrer_id)] = {"count": 0, "points_earned": 0, "users": []}

    referral_data["referrals"][str(referrer_id)]["count"] += 1
    referral_data["referrals"][str(referrer_id)]["points_earned"] += REFERRAL_POINTS
    referral_data["referrals"][str(referrer_id)]["users"].append(str(new_user_id))
    referral_data.setdefault("referred_users", {})[str(new_user_id)] = str(referrer_id)
    save_referral_data(referral_data)

    current_points = load_user_points(referrer_id)
    save_user_points(referrer_id, current_points + REFERRAL_POINTS)
    save_user_points(new_user_id, INITIAL_POINTS)
    return True, f"✅ تمت الإحالة! حصلت على {REFERRAL_POINTS} نقطة."

# ---------------- الاشتراكات ----------------
def is_owner(user_id):
    return str(user_id) == str(OWNER_ID)

def is_subscribed_telegram(user_id):
    if is_owner(user_id):
        return True
    try:
        chat_member = bot.get_chat_member(f"@{CHANNEL_TG}", user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except:
        return False

def is_subscribed_youtube(user_id):
    if is_owner(user_id):
        return True
    data = load_user_settings(user_id)
    verified = data.get(YOUTUBE_VERIFY_KEY, False)
    if verified:
        last_verify = data.get("youtube_verify_date")
        if last_verify:
            try:
                days_passed = (datetime.now() - datetime.fromisoformat(last_verify)).days
                if days_passed > YOUTUBE_VERIFY_DAYS:
                    return False
            except:
                return False
    return verified

def check_all_subscriptions(user_id):
    if is_owner(user_id):
        return True, None
    if not is_subscribed_telegram(user_id):
        return False, "telegram"
    if not is_subscribed_youtube(user_id):
        return False, "youtube"
    return True, None

# ============================================
# ⚙️ دوال Firebase (من الكود السابق)
# ============================================
def refresh_access_token(refresh_token):
    url = "https://securetoken.googleapis.com/v1/token"
    params = {"key": FIREBASE_API_KEY}
    payload = {"grantType": "refresh_token", "refreshToken": refresh_token}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, params=params, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("access_token"), data.get("refresh_token")
    except:
        pass
    return None, None

def get_headers(access_token, instance_token):
    return {
        "authorization": f"{TOKEN_TYPE} {access_token}",
        "firebase-instance-id-token": instance_token,
        "content-type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36"
    }

def check_game_access(user_data):
    headers = get_headers(user_data.get("access_token"), user_data.get("instance_token"))
    url = f"{BASE_URL}/checkGameAccess"
    try:
        resp = requests.post(url, json={"data": None}, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("result", {})
            return {"success": True, "can_play": data.get("canPlay", False), "stars": data.get("stars", 0), "remaining_time": data.get("remainingTime", 0)}
        elif resp.status_code == 401:
            new_token, new_refresh = refresh_access_token(user_data.get("refresh_token"))
            if new_token:
                user_data["access_token"] = new_token
                if new_refresh:
                    user_data["refresh_token"] = new_refresh
                save_user_data(user_data["user_id"], user_data)
                return check_game_access(user_data)
            return {"success": False, "error": "انتهت صلاحية التوكن ولا يمكن تجديده"}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def collect_points(user_data, score):
    headers = get_headers(user_data.get("access_token"), user_data.get("instance_token"))
    url = f"{BASE_URL}/collectGamePoints"
    payload = {"data": {"score": score}}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            result = resp.json().get("result", {})
            return {"success": result.get("success", False), "new_balance": result.get("newBalance", 0), "stars": result.get("stars", 0), "message": result.get("message", "")}
        elif resp.status_code == 401:
            new_token, _ = refresh_access_token(user_data.get("refresh_token"))
            if new_token:
                user_data["access_token"] = new_token
                save_user_data(user_data["user_id"], user_data)
                return collect_points(user_data, score)
            return {"success": False, "error": "توكن منتهي"}
        return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def generate_random_score():
    return random.choice([50, 100, 150, 200, 250, 70, 300, 80, 400, 120, 500, 60])

# ============================================
# 🎡 دوال العجلة (Spin Wheel)
# ============================================
def claim_spin_reward(user_data):
    headers = get_headers(user_data.get("access_token"), user_data.get("instance_token"))
    try:
        resp = requests.post(SPIN_URL, json={"data": None}, headers=headers, timeout=10)
        if resp.status_code == 200:
            result = resp.json().get("result", {})
            success = result.get("success", False)
            message = result.get("message", "")
            reward_type = result.get("type", "")

            return {
                "success": success,
                "message": message,
                "reward_type": reward_type
            }
        elif resp.status_code == 401:
            new_token, _ = refresh_access_token(user_data.get("refresh_token"))
            if new_token:
                user_data["access_token"] = new_token
                save_user_data(user_data["user_id"], user_data)
                return claim_spin_reward(user_data)
            return {"success": False, "message": "Token expired", "reward_type": "error"}
        else:
            return {"success": False, "message": f"HTTP {resp.status_code}", "reward_type": "error"}
    except Exception as e:
        return {"success": False, "message": str(e), "reward_type": "error"}

def check_spin_availability(user_data):
    result = claim_spin_reward(user_data)
    if result.get("success"):
        return {"available": True, "reward": result.get("message", "Reward"), "reward_type": result.get("reward_type", "unknown")}
    elif "Come back in" in result.get("message", ""):
        hours_match = re.search(r"(\d+) hours?", result.get("message", ""))
        hours = int(hours_match.group(1)) if hours_match else 23
        return {"available": False, "hours_left": hours}
    else:
        return {"available": False, "error": result.get("message")}

# ============================================
# 🤖 إعداد البوت
# ============================================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

def save_user_data(user_id, data):
    filepath = get_user_file(user_id, "gs_data")
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def load_user_data(user_id):
    filepath = get_user_file(user_id, "gs_data")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}

# ============================================
# 🚀 حلقة الهجوم في الخلفية
# ============================================
attack_status = {}

def attack_loop(user_id, chat_id):
    user_id_str = str(user_id)
    user_data = load_user_data(user_id)
    attack_status[user_id_str] = {"running": True}

    bot.send_message(chat_id, "🚀 تم بدء الهجوم الذكي مع نظام العجلة")

    while attack_status[user_id_str]["running"]:
        # فحص العجلة (كل 6 ساعات تقريبًا حتى لا نكرر الطلب في كل ثانية)
        now = time.time()
        last_spin_check = attack_status[user_id_str].get("last_spin_check", 0)
        if now - last_spin_check > 21600:  # 6 ساعات
            spin_status = check_spin_availability(user_data)
            attack_status[user_id_str]["last_spin_check"] = now

            if spin_status.get("available"):
                bot.send_message(chat_id, f"🎡 العجلة متاحة! جاري الدوران...")
                reward_message = spin_status.get("reward", "جائزة")
                bot.send_message(chat_id, f"🎉 حصلت من العجلة على: {reward_message}")
            else:
                if "hours_left" in spin_status:
                    bot.send_message(chat_id, f"⏳ العجلة غير متاحة. متبقي {spin_status['hours_left']} ساعة.")
                else:
                    bot.send_message(chat_id, f"⚠️ خطأ في العجلة: {spin_status.get('error')}")

        # التحقق من النقاط
        points = load_user_points(user_id)
        if points <= 0 and not is_owner(user_id):
            referral_link = get_referral_link(user_id)
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔗 رابط الإحالة", callback_data="my_referral"))
            bot.send_message(chat_id, f"⚠️ **نفدت نقاطك!**\nشارك رابط الإحالة للحصول على {REFERRAL_POINTS} نقطة:\n`{referral_link}`", parse_mode="Markdown", reply_markup=keyboard)
            attack_status[user_id_str]["running"] = False
            break

        # التحقق من النجوم والوقت
        status = check_game_access(user_data)
        if not status.get("success"):
            bot.send_message(chat_id, f"❌ فشل التحقق: {status.get('error')}")
            break

        stars = status.get("stars", 0)
        remaining = status.get("remaining_time", 0)

        if stars <= 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            bot.send_message(chat_id, f"⏳ لا يوجد نجوم! متبقي {mins} دقيقة و {secs} ثانية.\n⏸️ سأنتظر حتى تتوفر نجمة جديدة...")

            for _ in range(int(remaining)):
                if not attack_status[user_id_str]["running"]:
                    break
                time.sleep(1)
            continue

        # نجمة متوفرة - ابدأ الجمع
        score = generate_random_score()
        bot.send_message(chat_id, f"⭐ تم العثور على نجمة! جاري الجمع بقيمة: {score}...")

        result = collect_points(user_data, score)

        if result.get("success"):
            current_points = load_user_points(user_id)
            save_user_points(user_id, current_points - 1)
            bot.send_message(chat_id, f"✅ نجاح! +{score} (الرصيد: {result.get('new_balance')})\n💎 نقاطك المتبقية: {current_points - 1}")
        else:
            error = result.get("error") or result.get("message", "غير معروف")
            bot.send_message(chat_id, f"⚠️ فشل: {error}")

        time.sleep(3)

    bot.send_message(chat_id, "⏹️ توقف الهجوم.")

# ============================================
# 📨 أوامر البوت
# ============================================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "مستخدم"

    referrer_id = None
    if message.text and message.text.startswith('/start'):
        parts = message.text.split()
        if len(parts) > 1 and parts[1].isdigit():
            referrer_id = int(parts[1])

    sessions = load_user_sessions()
    user_id_str = str(user_id)
    if user_id_str not in sessions:
        sessions[user_id_str] = {"first_name": first_name, "username": message.from_user.username or "", "joined": datetime.now().isoformat()}
        save_user_sessions(sessions)

    sub_ok, sub_type = check_all_subscriptions(user_id)
    referral_data = load_referral_data()

    if referrer_id and user_id_str not in referral_data.get("referred_users", {}):
        if not is_subscribed_telegram(user_id) or not is_subscribed_youtube(user_id):
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("📢 اشترك في قناة التلجرام", url=f"https://t.me/{CHANNEL_TG}"))
            keyboard.add(InlineKeyboardButton("🎬 تأكيد يوتيوب", callback_data="verify_youtube"))
            keyboard.add(InlineKeyboardButton("✅ تأكيد الإحالة", callback_data=f"confirm_referral_{referrer_id}"))
            bot.reply_to(message, f"👋 أهلاً {first_name}!\nتمت دعوتك، اشترك في القناة وأكد يوتيوب أولاً.", reply_markup=keyboard)
            return
        else:
            success, msg = process_referral_new_user(user_id, referrer_id)
            bot.reply_to(message, f"🔗 تمت الإحالة!\n{msg}")
            start(message)
            return

    if not sub_ok:
        keyboard = InlineKeyboardMarkup(row_width=1)
        if sub_type == "telegram":
            keyboard.add(InlineKeyboardButton("📢 اشترك في القناة", url=f"https://t.me/{CHANNEL_TG}"))
        elif sub_type == "youtube":
            keyboard.add(InlineKeyboardButton("🎬 تأكيد يوتيوب", callback_data="verify_youtube"))
        keyboard.add(InlineKeyboardButton("✅ تحقق", callback_data="check_sub"))
        bot.reply_to(message, "🔒 اشترك في جميع القنوات وأكد يوتيوب.", reply_markup=keyboard)
        return

    # القائمة الرئيسية
    keyboard = InlineKeyboardMarkup(row_width=2)
    user_data = load_user_data(user_id)
    if not user_data.get("access_token"):
        keyboard.add(InlineKeyboardButton("🔑 إدخال التوكنات", callback_data="set_tokens"))
    else:
        keyboard.add(
            InlineKeyboardButton("▶️ بدء الهجوم", callback_data="start_attack"),
            InlineKeyboardButton("⏹️ إيقاف", callback_data="stop_attack"),
            InlineKeyboardButton("📊 الحالة", callback_data="status"),
            InlineKeyboardButton("🎡 العجلة", callback_data="spin_wheel"),
            InlineKeyboardButton("🔑 تعديل التوكنات", callback_data="set_tokens"),
            InlineKeyboardButton("🔗 رابط الإحالة", callback_data="my_referral")
        )

    points = load_user_points(user_id)

    bot.reply_to(message, f"✅ مرحباً {first_name}!\n"
                           "بوت جمع نقاط GiftSheep الذكي.\n"
                           "💎 نقاطك: {points}\n"
                           "يقوم بتغيير القيم تلقائياً (50, 200, 70...) لتفادي الحظر.", reply_markup=keyboard)

# ============================================
# 📋 معالجة الأزرار
# ============================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    user_id_str = str(user_id)

    if call.data == "verify_youtube":
        set_user_setting(user_id, YOUTUBE_VERIFY_KEY, True)
        set_user_setting(user_id, "youtube_verify_date", datetime.now().isoformat())
        bot.answer_callback_query(call.id, "✅ تم تأكيد يوتيوب!", show_alert=True)
        start(call.message)
        return

    if call.data.startswith("confirm_referral_"):
        referrer_id = int(call.data.replace("confirm_referral_", ""))
        if not is_subscribed_telegram(user_id) or not is_subscribed_youtube(user_id):
            bot.answer_callback_query(call.id, "❌ اشترك في القناة وأكد يوتيوب!", show_alert=True)
            return
        success, msg = process_referral_new_user(user_id, referrer_id)
        bot.answer_callback_query(call.id, msg[:100], show_alert=True)
        start(call.message)
        return

    if call.data == "check_sub":
        sub_ok, _ = check_all_subscriptions(user_id)
        if sub_ok:
            bot.answer_callback_query(call.id, "✅ تم التحقق!", show_alert=True)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ تأكد من الاشتراك!", show_alert=True)
        return

    if call.data == "set_tokens":
        msg = bot.send_message(chat_id, "🔐 أرسل ACCESS_TOKEN:")
        bot.register_next_step_handler(msg, process_access_token, user_id)
        bot.answer_callback_query(call.id)
        return

    if call.data == "start_attack":
        user_data = load_user_data(user_id)
        if not user_data.get("access_token"):
            bot.answer_callback_query(call.id, "⚠️ أدخل التوكنات أولاً!", show_alert=True)
            return
        points = load_user_points(user_id)
        if points <= 0 and not is_owner(user_id):
            bot.answer_callback_query(call.id, "⚠️ نفذت نقاطك، شارك رابط الإحالة!", show_alert=True)
            return
        if attack_status.get(user_id_str, {}).get("running", False):
            bot.answer_callback_query(call.id, "⚠️ الهجوم يعمل بالفعل!", show_alert=True)
            return

        attack_status[user_id_str] = {"running": True, "last_spin_check": 0}
        thread = threading.Thread(target=attack_loop, args=(user_id, chat_id))
        thread.daemon = True
        thread.start()
        bot.answer_callback_query(call.id, "▶️ تم البدء!", show_alert=True)
        return

    if call.data == "stop_attack":
        if attack_status.get(user_id_str, {}).get("running", False):
            attack_status[user_id_str]["running"] = False
            bot.answer_callback_query(call.id, "⏹️ سيتم الإيقاف...", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "⚠️ لا يوجد هجوم نشط!", show_alert=True)
        return

    if call.data == "status":
        user_data = load_user_data(user_id)
        if not user_data.get("access_token"):
            bot.send_message(chat_id, "⚠️ لم يتم إدخال التوكنات بعد!")
            return
        status = check_game_access(user_data)
        if status.get("success"):
            mins = int(status.get("remaining_time", 0) // 60)
            secs = int(status.get("remaining_time", 0) % 60)
            running = attack_status.get(user_id_str, {}).get("running", False)
            points = load_user_points(user_id)
            text = (f"📊 **الحالة:**\n"
                    f"▶️ الهجوم: {'يعمل' if running else 'متوقف'}\n"
                    f"⭐ النجوم: {status.get('stars')}\n"
                    f"⏳ الوقت المتبقي: {mins} دقيقة {secs} ثانية\n"
                    f"💎 نقاطك: {points}")
            bot.send_message(chat_id, text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"❌ خطأ: {status.get('error')}")
        bot.answer_callback_query(call.id)
        return

    if call.data == "spin_wheel":
        user_data = load_user_data(user_id)
        if not user_data.get("access_token"):
            bot.send_message(chat_id, "⚠️ أدخل التوكنات أولاً!")
            return
        spin_status = check_spin_availability(user_data)
        if spin_status.get("available"):
            reward_message = spin_status.get("reward", "جائزة")
            bot.send_message(chat_id, f"🎡 تم تدوير العجلة بنجاح!\n🎉 حصلت على: {reward_message}")
        else:
            if "hours_left" in spin_status:
                bot.send_message(chat_id, f"⏳ العجلة غير متاحة. متبقي {spin_status['hours_left']} ساعة.")
            else:
                bot.send_message(chat_id, f"⚠️ خطأ في العجلة: {spin_status.get('error')}")
        bot.answer_callback_query(call.id)
        return

    if call.data == "my_referral":
        link = get_referral_link(user_id)
        bot.reply_to(call.message, f"🔗 رابطك:\n`{link}`\n\nشاركه لتحصل على {REFERRAL_POINTS} نقطة!", parse_mode="Markdown")
        return

# ============================================
# 🔑 خطوات إدخال التوكنات
# ============================================
def process_access_token(message, user_id):
    access = message.text.strip()
    msg = bot.send_message(message.chat.id, "🔐 أرسل INSTANCE_TOKEN:")
    bot.register_next_step_handler(msg, process_instance_token, user_id, access)

def process_instance_token(message, user_id, access):
    instance = message.text.strip()
    msg = bot.send_message(message.chat.id, "🔐 أرسل REFRESH_TOKEN (اختياري):")
    bot.register_next_step_handler(msg, process_refresh_token, user_id, access, instance)

def process_refresh_token(message, user_id, access, instance):
    refresh = message.text.strip()

    user_data = {
        "user_id": user_id,
        "access_token": access,
        "instance_token": instance,
        "refresh_token": refresh if refresh else None
    }
    save_user_data(user_id, user_data)

    bot.reply_to(message, "✅ تم حفظ التوكنات بنجاح!\nيمكنك الآن بدء الهجوم أو تدوير العجلة.")
    start(message)

# ============================================
# 🖥️ خادم Flask والتشغيل
# ============================================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "bot is running"}), 200

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def keep_alive():
    while True:
        try:
            requests.get("https://giftsheep-bot.onrender.com/health", timeout=5)
            print("✅ تم إرسال طلب keep-alive")
        except Exception as e:
            print(f"⚠️ فشل keep-alive: {e}")
        time.sleep(600)

if __name__ == "__main__":
    print("="*60)
    print("🤖 بوت GiftSheep الذكي مع نظام العجلة والنقاط")
    print(f"👤 المالك: {OWNER_ID}")
    print(f"📢 قناة التلجرام: @{CHANNEL_TG}")
    print("="*60)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    while True:
        try:
            bot.polling(none_stop=True, interval=1)
        except Exception as e:
            print(f"⚠️ خطأ في البوت: {e}")
            time.sleep(5)
