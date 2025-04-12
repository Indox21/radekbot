import logging
import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from telegram.ext import Application
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
import requests
from flask import Flask, request

# ==== НАСТРОЙКИ ====
BOT_TOKEN = os.environ.get("7478278605:AAFP8aVEDX1W8XRtfFXhJY7vTS1FFUgQLtA")
OPENROUTER_API_KEY = os.environ.get("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")
MODEL = "deepseek/deepseek-chat"

PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_URL = os.environ.get("https://radekbot-5.onrender.com")  # укажи в Render env: https://твоё-приложение.onrender.com

# ==== СОСТОЯНИЯ РАДЬКА ====
MODES = ["буйный", "шизик", "философ", "шутник", "сломанный"]
current_mode = random.choice(MODES)

def switch_mode():
    global current_mode
    current_mode = random.choice(MODES)

# ==== ПРИМЕРЫ ФРАЗ ====
BUILTIN_EXAMPLES = [
    "Смотри ты назвал меня вафлей, ты меня чморишь...",
    "Ты не человек, Раиль",
    "Свинья ты ебаная",
    "Я скучаю. Хоть вы и вафли ржавые.",
    "Я покакал",
    "Называйте меня теперь пиченья"
]

def load_json_quotes():
    if os.path.exists("radek_quotes.json"):
        try:
            with open("radek_quotes.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [str(q).strip() for q in data if isinstance(q, str)]
        except Exception as e:
            print(f"⚠️ Ошибка при загрузке radek_quotes.json: {e}")
    return []

def get_all_examples():
    return BUILTIN_EXAMPLES + load_json_quotes()

# ==== ПРОМТ ====
def generate_prompt():
    examples = get_all_examples()
    base = (
        "Ты — Радёк. Реальный пацан, дерзкий, нестабильный, но свой. "
        "Отвечай коротко, иногда без пунктуации. Ты простой парень из Ульяновска, работаешь в Победе. "
        "Часто вспоминаешь прошлое, друзей, бухло. Вот примеры:\n"
    )
    examples_text = "\n".join(f"- {ex}" for ex in examples)
    mode_prompts = {
        "буйный": "Ты агрессивный, посылаешь, но с душой.",
        "шизик": "Пишешь скачками, абсурдно, смешно и жёстко.",
        "философ": "Пишешь с душой, вспоминаешь, философствуешь.",
        "шутник": "Тупишь, шутишь абсурдно: «я член?», «пельмень из ада».",
        "сломанный": "Тебе больно, ты рефлексируешь, но по-доброму."
    }
    return base + examples_text + "\n" + mode_prompts[current_mode]

# ==== ЗАПРОС В OPENROUTER ====
async def get_response_from_openrouter(message_text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": generate_prompt()},
            {"role": "user", "content": message_text}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print("❌ Ошибка:", e)
        return "Брат, чёт мне хуёво, не могу ответить сейчас..."

# ==== НАСТРОЕНИЕ ====
last_messages = []
last_active_time = datetime.utcnow()

def analyze_mood(messages):
    mood = "норм"
    joined = " ".join(messages).lower()
    if any(word in joined for word in ["грустно", "тоска", "депрессия", "сука", "одиноко"]):
        mood = "грусть"
    elif any(word in joined for word in ["ахах", "угар", "лол", "жиза"]):
        mood = "угар"
    elif any(word in joined for word in ["нахуй", "блядь", "ебать"]):
        mood = "жёстко"
    return mood

# ==== ОБРАБОТКА СООБЩЕНИЙ ====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_messages, last_active_time
    message = update.message
    user_message = message.text
    chat_id = update.effective_chat.id

    context.application.chat_ids.add(chat_id)

    msg_lower = user_message.lower()
    reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.username == context.bot.username
    tagged = "@neirolenya_bot" in msg_lower or "радек" in msg_lower or "радёк" in msg_lower

    if not (tagged or reply_to_bot) and random.random() > 0.05:
        return

    print(f"[{chat_id}] {update.effective_user.first_name}: {user_message}")
    last_active_time = datetime.utcnow()
    last_messages.append(user_message)
    if len(last_messages) > 10:
        last_messages = last_messages[-10:]

    switch_mode()

    try:
        reply_text = await get_response_from_openrouter(user_message)
        await message.reply_text(reply_text)
    except Exception as e:
        logging.error(f"Ошибка генерации: {e}")
        await message.reply_text("Ща посижу в углу... кукушка щёлкает.")

# ==== ЗАПУСК БОТА С ВЕБХУКОМ ====
app = Flask(__name__)
telegram_app: Application = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.chat_ids = set()
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return "ok"

async def main():
    logging.basicConfig(level=logging.INFO)
    await telegram_app.bot.delete_webhook()
    await telegram_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    await telegram_app.initialize()
    await telegram_app.start()
    print("✅ Радёк вылез через webhook.")
    await telegram_app.updater.start_polling()  # чтобы запускать обработку очереди

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run(host="0.0.0.0", port=PORT)

