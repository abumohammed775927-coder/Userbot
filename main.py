import asyncio
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
        source = message.chat.title or str(message.chat.id)
        print(f"Copied matching message from: {source}", flush=True)
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
