from telethon import TelegramClient, events, Button, utils
from telethon.sessions import StringSession
import datetime
import html
import asyncio
import os
from flask import Flask
import threading

# إعدادات البوت - سيتم قراءتها من متغيرات البيئة
api_id = int(os.environ.get("API_ID", 0))
api_hash = os.environ.get("API_HASH", "")
session_string = os.environ.get("SESSION_STRING", "")

KEYWORDS = ["يساعدني","يحل", "يحِل", "ابغى", "يسوي", "أبغى", "يساعد"]
ALERT_TARGET = os.environ.get("ALERT_TARGET", "abdualrzaq") # يمكن تغييرها لتكون متغير بيئة أيضاً

# استخدام StringSession إذا كانت متوفرة، وإلا فابدأ جلسة جديدة
client = TelegramClient(StringSession(session_string) if session_string else None, api_id, api_hash)

def contains_keyword(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(kw.lower() in t for kw in KEYWORDS)

def build_chat_link(chat, chat_id, message_id):
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}/{message_id}"
    try:
        s = str(chat_id)
        if s.startswith("-100"):
            short = s[4:]
            return f"https://t.me/c/{short}/{message_id}"
    except Exception:
        pass
    return None

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    try:
        text = event.message.message or ""
        if not text or not contains_keyword(text):
            return

        chat = await event.get_chat()
        sender = await event.get_sender()

        sender_name = utils.get_display_name(sender) if sender else "مجهول"
        if sender and getattr(sender, "username", None):
            sender_user_field = f"@{sender.username}"
            sender_link = f"https://t.me/{sender.username}"
        elif sender and getattr(sender, "id", None):
            sender_user_field = f"{sender_name}"
            sender_link = f"tg://user?id={sender.id}"
        else:
            sender_user_field = "لا يوجد"
            sender_link = None

        chat_title = getattr(chat, "title", None) or getattr(chat, "first_name", None) or "المجموعة"
        chat_id = event.chat_id
        chat_link = build_chat_link(chat, chat_id, event.message.id)

        when = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        header = (
            f"📢 رسالة مهمة:\n\n"
            f"👤 المرسل: {html.escape(sender_name)}\n"
            f"🔗 يوزر/رابط المرسل: {sender_user_field}\n"
            f"🏷️ المجموعة: {html.escape(chat_title)}\n"
            f"🔗 رابط الرسالة: {chat_link if chat_link else 'لا يمكن توليد رابط عام'}\n"

            f"🕒 الوقت: {when}\n\n"
            f"— الرسالة الأصلية ستأتي بعد هذه الملاحظة —"
        )

        buttons = []
        if chat_link:
            buttons.append([Button.url("🔗 الانتقال إلى الرسالة", chat_link)])

        await client.send_message(ALERT_TARGET, header, buttons=buttons)

        try:
            await client.forward_messages(ALERT_TARGET, event.message)
        except Exception as fe:
            await client.send_message(ALERT_TARGET, "💬 (لم أستطع إعادة توجيه الرسالة — أدرج النص أدناه):\n\n" + text)

    except Exception as e:
        print("Error handling message:", repr(e))

# Flask app for keep-alive
app = Flask(__name__)

@app.route("/")
def home():
    return "I am alive!"

def run_flask_app():
    app.run(host="0.0.0.0", port=7860)

async def main():
    # Start Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True # Allow main program to exit even if thread is running
    flask_thread.start()

    print("Connecting to Telegram...")
    await client.start()
    print("Userbot started — listening...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
