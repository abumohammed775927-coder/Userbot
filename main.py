import asyncio

# Pyrogram 2.0.106 يحتاج حلقة asyncio موجودة عند تشغيله على Python 3.14.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import os
import re
from threading import Thread

from flask import Flask, jsonify
from pyrogram import Client, filters
from pyrogram.errors import FloodWait


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


API_ID = int(required_env("API_ID"))
API_HASH = required_env("API_HASH")
SESSION_STRING = required_env("SESSION_STRING")
DESTINATION_RAW = required_env("DESTINATION_CHAT")

try:
    DESTINATION_CHAT = int(DESTINATION_RAW)
except ValueError:
    DESTINATION_CHAT = DESTINATION_RAW

# الكلمات مصنفة حتى لا تنتقل الرسائل التي تحتوي كلمة واحدة عابرة فقط.
INTENT_WORDS = [
    "ابي", "ابغى", "ابغا", "اريد", "احتاج", "محتاج", "عندي",
    "مين", "احد", "عندكم", "فيه", "هل يوجد", "ابحث عن",
]

ACTION_WORDS = [
    "يسوي", "يعمل", "يحل", "حل", "احل", "يساعد", "اساعد", "اساعدني",
    "يجهز", "يكتب", "يصمم", "يفزع", "فزعه", "متفرغ", "ساعدوني",
]

TASK_WORDS = [
    "واجب", "واجبات", "تكليف", "بحث", "مشروع", "تقرير", "عرض",
    "برزنتيشن", "بوربوينت", "اختبار", "اختبارات", "كويز", "اسئله",
    "مناقشه", "تسليم",
]

DIRECT_PHRASES = [
    "شخص يسوي", "شخص يساعد", "يعرف احد", "يعرف شخص", "مين يحل",
    "احد يحل", "ابي احد", "ابغى احد",
]


def normalize_arabic(text: str) -> str:
    text = text or ""
    text = text.lower()
    text = re.sub(r"[إأآٱا]", "ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[َ ُ ِ ّ ْ ـً ٌ ٍ]", "", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def contains_term(text: str, term: str) -> bool:
    term = normalize_arabic(term)
    if " " in term:
        return term in text
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def score_message(text: str) -> int:
    normalized = normalize_arabic(text)
    score = 0
    if any(contains_term(normalized, word) for word in INTENT_WORDS):
        score += 1
    if any(contains_term(normalized, word) for word in ACTION_WORDS):
        score += 1
    if any(contains_term(normalized, word) for word in TASK_WORDS):
        score += 1
    if any(contains_term(normalized, phrase) for phrase in DIRECT_PHRASES):
        score = max(score, 2)
    return score


def make_message_links(message):
    user = message.from_user
    if user and user.username:
        user_link = f"https://t.me/{user.username}"
    elif user:
        user_link = f"tg://user?id={user.id}"
    else:
        user_link = "غير متاح؛ الرسالة منشورة باسم القناة أو كمستخدم مخفي"

    chat = message.chat
    if chat.username:
        group_link = f"https://t.me/{chat.username}"
    else:
        group_link = "غير متاح؛ المجموعة خاصة ولا تملك رابطاً عاماً"

    message_link = getattr(message, "link", None)
    if not message_link and chat.username:
        message_link = f"https://t.me/{chat.username}/{message.id}"
    if not message_link and str(chat.id).startswith("-100"):
        message_link = f"https://t.me/c/{str(chat.id)[4:]}/{message.id}"
    message_link = message_link or "غير متاح"

    return (
        "\n\n--- معلومات المصدر ---\n"
        f"رابط المستخدم: {user_link}\n"
        f"رابط المجموعة: {group_link}\n"
        f"رابط الرسالة: {message_link}"
    )


telegram = Client(
    "render_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
)


@telegram.on_message(
    (filters.group | filters.channel) & ~filters.chat(DESTINATION_CHAT)
)
async def copy_matching_message(client, message):
    text = message.text or message.caption or ""
    if score_message(text) < 2:
        return

    try:
        # هذا ينشئ نسخة جديدة في الوجهة، وليس Forward؛ استخدمه فقط للمحتوى
        # الذي تملك حق إعادة نشره أو لديك إذن بنقله.
        await message.copy(DESTINATION_CHAT)
        await client.send_message(
            DESTINATION_CHAT,
            make_message_links(message),
            disable_web_page_preview=True,
        )
        source = message.chat.title or str(message.chat.id)
        print(f"Copied matching message and source links from: {source}", flush=True)
    except FloodWait as error:
        print(f"Telegram requested a wait of {error.value} seconds", flush=True)
        await asyncio.sleep(error.value)
    except Exception as error:
        print(f"Copy failed: {error}", flush=True)


web = Flask(__name__)


@web.get("/")
def health():
    return jsonify({"status": "running", "service": "telegram-userbot"})


@web.get("/health")
def health_check():
    return "OK", 200


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    web.run(host="0.0.0.0", port=port, threaded=True, use_reloader=False)


if __name__ == "__main__":
    Thread(target=run_health_server, daemon=True).start()
    print("Telegram userbot is starting", flush=True)
    telegram.run()
