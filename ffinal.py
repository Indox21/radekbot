import logging
import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import requests

# ==== НАСТРОЙКИ ====
BOT_TOKEN = "7478278605:AAFP8aVEDX1W8XRtfFXhJY7vTS1FFUgQLtA"
OPENROUTER_API_KEY = "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"
MODEL = "deepseek/deepseek-chat"
WEBHOOK_URL = "https://radekbot-3.onrender.com"
PORT = 10000

# ==== СОСТОЯНИЯ ====
MODES = ["буйный", "шизик", "философ", "шутник", "сломанный"]
current_mode = random.choice(MODES)
last_messages = []
last_active_time = datetime.utcnow()

def switch_mode():
    global current_mode
    current_mode = random.choice(MODES)

# ==== ФРАЗЫ ====
BUILTIN_QUOTES = [
    "Смотри ты назвал меня вафлей, ты меня чморишь...",
    "Ты не человек, Раиль",
    "Свинья ты ебаная",
    "Я скучаю. Хоть вы и вафли ржавые.",
    "Я покакал",
    "Называйте меня теперь пиченья"
]

def load_custom_quotes():
    if os.path.exists("radek_quotes.json"):
        try:
            with open("radek_quotes.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                return [q.strip() for q in data if isinstance(q, str)]
        except Exception as e:
            print(f"⚠️ Ошибка загрузки цитат: {e}")
    return []

def get_all_quotes():
    return BUILTIN_QUOTES + load_custom_quotes()

# ==== ПОДГОТОВКА ПРОМПТА ====
def generate_prompt():
    examples = "\n".join(f"- {quote}" for quote in get_all_quotes())
    base_prompt = (
        "Ты — Радёк. Реальный пацан из Ульяновска. Дерзкий, грубый, но с душой. "
        "Короткие ответы, минимум пунктуации. Работаешь в Победе, вспоминаешь детство, друзей, пьянки.\n"
        "Вот примеры:\n" + examples + "\n"
    )
    mode_addon = {
        "буйный": "Ты агрессивный и посылаешь, но не по злу.",
        "шизик": "Отвечаешь абсурдно, несвязно, местами жутко.",
        "философ": "Пишешь с душой, ностальгируешь, философствуешь.",
        "шутник": "Шутишь нелепо: 'я член?', 'пельмень в аду'.",
        "сломанный": "Ты уставший, добрый, немного потерянный."
    }[current_mode]
    return base_prompt + mode_addon

# ==== ОТВЕТ ЧЕРЕЗ OPENROUTER ====
async def ask_openrouter(text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": generate_prompt()},
            {"role": "user", "content": text}
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"❌ Ошибка OpenRouter: {e}")
        return "Брат, чёт мне хуёво, не могу сейчас..."

# ==== НАСТРОЕНИЕ ПО ПОСЛЕДНИМ СООБЩЕНИЯМ ====
def analyze_mood(messages):
    text = " ".join(messages).lower()
    if any(w in text for w in ["грустно", "тоска", "депрессия", "одиноко"]):
        return "грусть"
    elif any(w in text for w in ["ахах", "угар", "жиза"]):
        return "угар"
    elif any(w in text for w in ["нахуй", "блядь", "ебать"]):
        return "жёстко"
    return "норм"

# ==== ОБРАБОТКА СООБЩЕНИЙ ====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_messages, last_active_time

    msg = update.message
    text = msg.text
    chat_id = update.effective_chat.id
    context.application.chat_ids.add(chat_id)

    tagged = any(w in text.lower() for w in ["радек", "радёк", "@neirolenya_bot"]) or \
             (msg.reply_to_message and msg.reply_to_message.from_user.username == context.bot.username)

    if not tagged and random.random() > 0.05:
        return

    print(f"[{chat_id}] {update.effective_user.first_name}: {text}")
    last_messages.append(text)
    if len(last_messages) > 10:
        last_messages = last_messages[-10:]
    last_active_time = datetime.utcnow()
    switch_mode()

    reply = await ask_openrouter(text)
    await msg.reply_text(reply)

# ==== АВТО-РЕПЛИКИ ====
async def auto_reply_task(app):
    global last_active_time

    await asyncio.sleep(10)
    while True:
        await asyncio.sleep(30)
        if datetime.utcnow() - last_active_time > timedelta(minutes=5):
            switch_mode()
            mood = analyze_mood(last_messages)
            lines = {
                "грусть": [
                    "Бля, как будто мы опять в девятом классе. Только теперь никого нет.",
                    "Тоска, пацаны. Обнял бы, да некого...",
                    "Я скучаю. Хоть вы и вафли ржавые."
                ],
                "угар": [
                    "Яйцо в трусах — мой новый дом 😂",
                    "Пиченьяяяяя!",
                    "Какать как? Ты член??"
                ],
                "жёстко": [
                    "Ты вафля. Причём не свежая, а ебаная.",
                    "Раиль, подумай. Подумай, блядь.",
                    "Серёга, не выёбывайся, или в тапок превращу."
                ],
                "норм": [
                    "Пацаны, жизнь — это сон, а я во сне обоссался.",
                    "Слышь... а помнишь, как мы зимой под мостом орали?",
                    "Всё по кайфу. Даже если грустно."
                ]
            }
            for chat in app.chat_ids:
                try:
                    await app.bot.send_message(chat, text=random.choice(lines[mood]))
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение в чат {chat}: {e}")
            last_active_time = datetime.utcnow()

# ==== ЗАПУСК ====
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.chat_ids = set()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def main():
        await app.initialize()
        await app.bot.delete_webhook()
        await app.start()
        await app.updater.start_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="",
            webhook_url=WEBHOOK_URL
        )
        asyncio.create_task(auto_reply_task(app))
        print("✅ Радёк слушает по вебхуку")
        await app.updater.idle()

    asyncio.run(main())
