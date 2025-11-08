"""
Professional Telegram Test Bot
Foydalanuvchilar ro'yxati + Testni to'xtatish/boshlash
"""

import os
import json
import csv
import random
import asyncio
import logging
from shutil import copyfile
from datetime import datetime
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------- CONFIG ----------
TOKEN = "8261515196:AAG27QuFZb7ZZ7Apcw8djihYmaTY60qVwOQ"
ADMINS = [8147432628]  # admin ID lar
USERS_FILE = Path("users.json")
QUESTIONS_FILE = Path("questions.json")
BACKUP_DIR = Path("backup")
DAILY_LIMIT = 20
TEST_ACTIVE = True  # test holati

# ---------- Logging ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- Keyboards ----------
main_keyboard = ReplyKeyboardMarkup(
    [["🚀 Testni boshlash"], ["📊 Natijalar"], ["🆘 Yordam"]],
    resize_keyboard=True,
)

admin_keyboard = ReplyKeyboardMarkup(
    [
        ["🚀 Testni boshlash", "⏹ Testni to‘xtatish"],
        ["📄 CSV yuklash", "📚 Savollar ro‘yxati"],
        ["🗑️ Savolni o‘chirish", "📊 Statistikani ko‘rish"],
        ["📋 Foydalanuvchilar ro‘yxati"],
        ["✏️ Savol qo‘shish", "📢 E’lon yuborish"],
        ["⬅️ Asosiy menyu", "🧹 Ballarni nol qilish"],
    ],
    resize_keyboard=True,
)

# ---------- Utilities ----------
def safe_load_json(path: Path, default):
    try:
        if not path.exists():
            return default
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load {path}: {e}")
        return default

def safe_save_json(path: Path, data):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {path}: {e}")

def backup_files():
    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if USERS_FILE.exists():
            copyfile(str(USERS_FILE), str(BACKUP_DIR / f"users_{ts}.json"))
        if QUESTIONS_FILE.exists():
            copyfile(str(QUESTIONS_FILE), str(BACKUP_DIR / f"questions_{ts}.json"))
        logger.info("Backup completed")
    except Exception as e:
        logger.warning(f"Backup failed: {e}")

def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def load_users():
    return safe_load_json(USERS_FILE, {})

def save_users(u):
    safe_save_json(USERS_FILE, u)

def load_questions():
    return safe_load_json(QUESTIONS_FILE, [])

def save_questions(q):
    safe_save_json(QUESTIONS_FILE, q)

# fayllar birinchi ishga tushganda yaratiladi
if not USERS_FILE.exists():
    save_users({})
if not QUESTIONS_FILE.exists():
    save_questions([])

# ---------- Core ----------
async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, users):
    uid = str(update.effective_user.id)
    user = users.get(uid, {})
    idx = user.get("session_index", 0)
    session = user.get("session", [])
    if not session or idx >= len(session):
        await update.message.reply_text("❗ Sessiya tugadi.", reply_markup=main_keyboard)
        return
    qid = session[idx]
    questions = load_questions()
    question = next((q for q in questions if q.get("id") == qid), None)
    if not question:
        await update.message.reply_text("❗ Savol topilmadi.", reply_markup=main_keyboard)
        return
    opts = ReplyKeyboardMarkup(
        [[a] for a in question.get("answers", [])],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        f"🧠 {idx+1}/{len(session)} — ❓ {question.get('question')}",
        reply_markup=opts,
    )

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    uid = str(update.effective_user.id)
    if uid not in users or not users[uid].get("name"):
        await update.message.reply_text("Assalomu alaykum! Ismingizni kiriting:")
        context.user_data["awaiting_name"] = True
        users.setdefault(uid, {"name": None, "score": 0, "answered": [], "daily_count": 0, "last_day": "", "session": [], "session_index": 0})
        save_users(users)
        return
    name = users[uid].get("name", "Foydalanuvchi")
    kb = admin_keyboard if int(uid) in ADMINS else main_keyboard
    await update.message.reply_text(f"Salom, {name}! 👋", reply_markup=kb)

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global TEST_ACTIVE
    text = (update.message.text or "").strip()
    uid = str(update.effective_user.id)
    users = load_users()
    questions = load_questions()
    user = users.setdefault(uid, {"name": None, "score": 0, "answered": [], "daily_count": 0, "last_day": "", "session": [], "session_index": 0})

# === YANGI: JAVOB QABUL QILISH ===
    if user.get("session") and user.get("session_index", 0) < len(user.get("session", [])):
        # Foydalanuvchi sessiyada → bu javob
        questions = load_questions()
        qid = user["session"][user["session_index"]]
        question = next((q for q in questions if q["id"] == qid), None)
        if not question:
            await update.message.reply_text("❌ Savol topilmadi.")
            return

        correct = question["correct"]
        if text == correct:
            user["score"] = user.get("score", 0) + 5
            user["answered"].append(qid)
            user["daily_count"] = user.get("daily_count", 0) + 1
            await update.message.reply_text("✅ To‘g‘ri! +5 ball")
        else:
            await update.message.reply_text(f"❌ Noto‘g‘ri. To‘g‘ri javob: {correct}")

        # Keyingi savolga o‘tish
        user["session_index"] += 1
        save_users(users)

        if user["session_index"] >= len(user["session"]):
            # Sessiya tugadi
            await update.message.reply_text(
                f"🎉 Sessiya yakunlandi!\n"
                f"📊 Bugun: {user['daily_count']} ta savol\n"
                f"🏆 Umumiy ball: {user['score']}",
                reply_markup=main_keyboard
            )
            user["session"] = []
            user["session_index"] = 0
            save_users(users)
            return

        # Keyingi savolni yuborish
        await asyncio.sleep(1.2)  # kichik pauza
        await send_question(update, context, users)
        return
    # === JAVOB QAYTA ISHLASH TUGADI ===
    
    # ism kiritish
    if context.user_data.get("awaiting_name"):
        users[uid]["name"] = text or "Anonim"
        users[uid]["last_day"] = ""
        save_users(users)
        context.user_data["awaiting_name"] = False
        kb = admin_keyboard if int(uid) in ADMINS else main_keyboard
        await update.message.reply_text("✅ Ro‘yxatdan o‘tdingiz!", reply_markup=kb)
        return

    # ADMIN TUGMALAR
    if int(uid) in ADMINS:
        if text == "📋 Foydalanuvchilar ro‘yxati":
            if not users:
                await update.message.reply_text("📋 Hozircha hech kim ro‘yxatdan o‘tmagan.")
                return
            msg = "📋 *Ro‘yxatdan o‘tganlar:*\n\n"
            for i, (user_id, data) in enumerate(users.items(), 1):
                name = data.get("name", "Ismsiz")
                score = data.get("score", 0)
                msg += f"{i}. {name} — {score} ball (ID: {user_id})\n"
                if i % 30 == 0:
                    await update.message.reply_text(msg, parse_mode="Markdown")
                    msg = ""
            if msg:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return

        if text == "⏹ Testni to‘xtatish":
            TEST_ACTIVE = False
            await update.message.reply_text("⏹ Test to‘xtatildi. Endi foydalanuvchilar javob bera olmaydi.")
            return

        if text == "🚀 Testni boshlash":
            TEST_ACTIVE = True
            await update.message.reply_text("🚀 Test qayta yoqildi! Hammaga ochiq.")
            return

        if text == "📄 CSV yuklash":
            await update.message.reply_text("📎 .csv faylni yuboring.")
            return

        if text == "📚 Savollar ro‘yxati":
            await list_questions(update)
            return

        if text == "🗑️ Savolni o‘chirish":
            await update.message.reply_text("🆔 Savol ID sini kiriting:")
            context.user_data["awaiting_delete_id"] = True
            return

        if context.user_data.get("awaiting_delete_id"):
            if text.isdigit():
                await delete_question(update, int(text))
            else:
                await update.message.reply_text("❗ Raqam kiriting.")
            context.user_data["awaiting_delete_id"] = False
            return

        if text == "📊 Statistikani ko‘rish":
            await show_stats(update)
            await show_ranking(update, users)
            return

        if text == "📢 E’lon yuborish":
            await update.message.reply_text("✍️ E’lon matnini yuboring:")
            context.user_data["awaiting_announcement"] = True
            return

        if context.user_data.get("awaiting_announcement"):
            announcement = text
            users = load_users()
            count = 0
            await update.message.reply_text("📤 E’lon yuborilmoqda, kuting...")

            for user_id in users.keys():
                try:
                    await context.bot.send_message(chat_id=int(user_id), text=f"📢 *E’lon:*\n\n{announcement}", parse_mode="Markdown")
                    count += 1
                    await asyncio.sleep(0.1)  # flood control
                except Exception as e:
                    logger.warning(f"E’lon yuborilmadi foydalanuvchi {user_id}: {e}")

            context.user_data["awaiting_announcement"] = False
            await update.message.reply_text(f"✅ E’lon {count} ta foydalanuvchiga yuborildi.", reply_markup=admin_keyboard)
            return
            
        if text == "✏️ Savol qo‘shish":
            await update.message.reply_text("✍️ Savol matnini kiriting:")
            context.user_data["adding_question"] = {"step": "question"}
            return

        if "adding_question" in context.user_data:
            data = context.user_data["adding_question"]
            step = data["step"]
            data[step] = text
            next_step = {"question": "answer1", "answer1": "answer2", "answer2": "answer3", "answer3": "answer4", "answer4": "correct"}
            if step != "correct":
                data["step"] = next_step[step]
                await update.message.reply_text("✅ Javob saqlandi. Keyingi javobni kiriting:")
            else:
                answers = [data.get(f"answer{i}", "") for i in range(1, 5)]
                correct = text
                if correct not in answers:
                    await update.message.reply_text("❌ To‘g‘ri javob variantlar ichida bo‘lishi kerak.")
                    context.user_data.pop("adding_question", None)
                    return
                new_id = max((q.get("id", 0) for q in questions), default=0) + 1
                questions.append({"id": new_id, "question": data["question"], "answers": answers, "correct": correct})
                save_questions(questions)
                await update.message.reply_text(f"✅ Savol qo‘shildi! ID: {new_id}", reply_markup=admin_keyboard)
                context.user_data.pop("adding_question", None)
            return

        if text == "⬅️ Asosiy menyu":
            await update.message.reply_text("🔙 Asosiy menyuga qaytdingiz.", reply_markup=admin_keyboard)
            return

        if text == "🧹 Ballarni nol qilish":
            for uid2, data in users.items():
                data["score"] = 0
                data["answered"] = []
                data["daily_count"] = 0
            save_users(users)
            await update.message.reply_text(
                "✅ Barcha foydalanuvchilarning ballari muvaffaqiyatli 0 qilindi!",
                reply_markup=admin_keyboard
            )
            return

    # USER TEST BOSHLASH
    if text == "🚀 Testni boshlash":
        if not TEST_ACTIVE:
            await update.message.reply_text("⏹ Test hozircha to‘xtatilgan. Admin kutib turing!")
            return
        today = get_today()
        if user.get("last_day") != today:
            user["daily_count"] = 0
            user["last_day"] = today
        if user.get("daily_count", 0) >= DAILY_LIMIT:
            await update.message.reply_text("📅 Bugun 20 ta savolga javob berdingiz. Ertaga davom eting!", reply_markup=main_keyboard)
            save_users(users)
            return
        unanswered = [q for q in questions if q.get("id") not in user.get("answered", [])]
        if not unanswered:
            await update.message.reply_text("🎉 Barcha savollarga javob berdingiz!", reply_markup=main_keyboard)
            return
        random.shuffle(unanswered)
        user["session"] = [q.get("id") for q in unanswered]
        user["session_index"] = 0
        user["session_date"] = today
        save_users(users)
        await send_question(update, context, users)
        return

    if text == "📊 Natijalar":
        ranking = sorted(users.items(), key=lambda x: x[1].get("score", 0), reverse=True)
        result = "🏆 *Top 10 Reyting:*\n\n"
        for i, (uid2, data) in enumerate(ranking[:10], 1):
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else ""
            correct_count = len(data.get("answered", []))
            max_possible = correct_count * 5 if correct_count else 0
            ratio = f"({round((data.get('score',0)/max_possible)*100,1)}%)" if max_possible else "(0%)"
            result += f"{i}. {data.get('name','User')} — {data.get('score',0)} ball {medal} {ratio}\n"
        await update.message.reply_text(result, parse_mode="Markdown")
        return

    if text in ("🆘 Yordam", "ℹ️ Yordam"):
        await update.message.reply_text(
            "🧠 Har kuni ta savol. To‘g‘ri javob +5 ball.\n"
            "Admin bilan bog‘lanish uchun @Testbot0710 buyrug‘ini yuboring.",
            reply_markup=main_keyboard,
        )
        return

# ---------- Admin utils ----------
async def list_questions(update: Update):
    questions = load_questions()
    if not questions:
        await update.message.reply_text("❌ Savollar topilmadi.")
        return
    chunk = []
    for i, q in enumerate(questions, 1):
        chunk.append(f"{i}. ID: {q.get('id')} — {q.get('question')[:80]}")
        if i % 40 == 0 or i == len(questions):
            await update.message.reply_text("📚 Savollar:\n\n" + "\n".join(chunk), parse_mode="Markdown")
            chunk = []

async def delete_question(update: Update, qid: int):
    questions = load_questions()
    new_q = [q for q in questions if q.get("id") != qid]
    if len(new_q) == len(questions):
        await update.message.reply_text(f"❌ ID {qid} topilmadi.")
    else:
        save_questions(new_q)
        await update.message.reply_text(f"🗑️ Savol ID {qid} o‘chirildi.")

async def show_stats(update: Update):
    users = load_users()
    total_users = len(users)
    total_answers = sum(len(u.get("answered", [])) for u in users.values())
    top_score = max((u.get("score", 0) for u in users.values()), default=0)
    await update.message.reply_text(
        f"📊 *Statistika:*\n\n"
        f"👥 Foydalanuvchilar: {total_users}\n"
        f"✅ Umumiy javoblar: {total_answers}\n"
        f"🏆 Eng yuqori ball: {top_score}",
        parse_mode="Markdown",
    )

async def show_ranking(update: Update, users):
    ranking = sorted(users.items(), key=lambda x: x[1].get("score", 0), reverse=True)
    result = "🏆 Reyting:\n\n"
    for i, (uid2, data) in enumerate(ranking[:10], 1):
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else ""
        result += f"{i}. {data.get('name','User')} — {data.get('score',0)} ball {medal}\n"
    await update.message.reply_text(result, parse_mode="Markdown")

# ---------- CSV ----------
async def handle_csv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("⛔ Ruxsat yo‘q.")
        return
    document = update.message.document
    if not document or not document.file_name.endswith(".csv"):
        await update.message.reply_text("📄 Faqat .csv fayl yuboring.")
        return
    file = await document.get_file()
    file_path = Path("uploaded.csv")
    await file.download_to_drive(str(file_path))
    try:
        existing = load_questions()
        existing_ids = {q.get("id") for q in existing}
        new_questions = []
        invalid_rows = 0
        with file_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    qid = int(row.get("id") or 0)
                    if qid in existing_ids or qid == 0:
                        invalid_rows += 1
                        continue
                    question_text = (row.get("question") or "").strip()
                    answers = [(row.get(k) or "").strip() for k in ("answer1", "answer2", "answer3", "answer4")]
                    correct = (row.get("correct") or "").strip()
                    if not question_text or any(not a for a in answers) or correct not in answers:
                        invalid_rows += 1
                        continue
                    new_questions.append({"id": qid, "question": question_text, "answers": answers, "correct": correct})
                except Exception:
                    invalid_rows += 1
        all_questions = existing + new_questions
        save_questions(all_questions)
        await update.message.reply_text(
            f"✅ {len(new_questions)} ta savol qo‘shildi. ❌ {invalid_rows} ta noto‘g‘ri qator o‘tkazib yuborildi."
        )
    finally:
        try:
            file_path.unlink()
        except:
            pass
            
# ---------- Flask keep-alive ----------
from flask import Flask
from threading import Thread

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot ishlayapti!"

def run_flask():
    app_flask.run(host="0.0.0.0", port=8080)

def keep_alive():
    thread = Thread(target=run_flask)
    thread.daemon = True
    thread.start()


# ---------- Main ----------
async def main():
    backup_files()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_csv_upload))

    logger.info("✅ Bot ishga tushdi...")
    await app.run_polling()


if __name__ == "__main__":
    # Flask keep-alive serverini yoqamiz
    keep_alive()

    # asyncio loop patch
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except:
        pass

    asyncio.run(main())