import os
import sqlite3
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    Update
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

BASE_URL = os.getenv("BASE_URL")  # masalan: https://photo-bot-rm8n.onrender.com
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

# ================= BOT =================
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ================= DB =================
db = sqlite3.connect("data.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    lang TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service TEXT,
    comment TEXT,
    phone TEXT,
    status TEXT,
    file_id TEXT
)
""")
db.commit()

# ================= LANG =================
TEXTS = {
    "choose_lang": {
        "uz": "🌐 Tilni tanlang",
        "ru": "🌐 Выберите язык",
        "en": "🌐 Choose language",
        "qq": "🌐 Tildi tańlań",
        "kk": "🌐 Тілді таңдаңыз"
    },
    "menu": {
        "uz": "📸 Xizmatni tanlang:",
        "ru": "📸 Выберите услугу:",
        "en": "📸 Select service:",
        "qq": "📸 Xızmetti tańlań:",
        "kk": "📸 Қызметті таңдаңыз:"
    },
    "confirm": {
        "uz": "Davom etamizmi?",
        "ru": "Продолжаем?",
        "en": "Shall we continue?",
        "qq": "Davom etemizbe?",
        "kk": "Жалғастырамыз ба?"
    },
    "cancel": {
        "uz": "❌ Bekor qilish",
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "qq": "❌ Biykarlaw",
        "kk": "❌ Болдырмау"
    },
    "continue": {
        "uz": "✅ Davom etamiz",
        "ru": "✅ Продолжить",
        "en": "✅ Continue",
        "qq": "✅ Davom etemiz",
        "kk": "✅ Жалғастыру"
    },
    "send_photo": {
        "uz": "📷 Rasm yoki fayl yuboring",
        "ru": "📷 Отправьте фото или файл",
        "en": "📷 Send photo or file",
        "qq": "📷 Foto yaki fayl jiberiń",
        "kk": "📷 Фото немесе файл жіберіңіз"
    },
    "send_comment": {
        "uz": "📝 Izoh yozing",
        "ru": "📝 Напишите комментарий",
        "en": "📝 Write a comment",
        "qq": "📝 Izoh jazıń",
        "kk": "📝 Пікір жазыңыз"
    },
    "send_phone": {
        "uz": "📞 Telefon raqamingizni yuboring",
        "ru": "📞 Отправьте номер телефона",
        "en": "📞 Send your phone number",
        "qq": "📞 Telefon nomerińizdi jiberiń",
        "kk": "📞 Телефон нөміріңізді жіберіңіз"
    },
    "accepted": {
        "uz": "⏳ Buyurtma qabul qilindi",
        "ru": "⏳ Заказ принят",
        "en": "⏳ Order accepted",
        "qq": "⏳ Buyırtpa qabıl etildi",
        "kk": "⏳ Тапсырыс қабылданды"
    },
    "working": {
        "uz": "⚙️ Buyurtma ishlanmoqda",
        "ru": "⚙️ Заказ в работе",
        "en": "⚙️ Order in progress",
        "qq": "⚙️ Buyırtpa islewde",
        "kk": "⚙️ Тапсырыс орындалуда"
    },
    "done": {
        "uz": "✅ Buyurtma tayyor",
        "ru": "✅ Заказ готов",
        "en": "✅ Order ready",
        "qq": "✅ Buyırtpa tayyar",
        "kk": "✅ Тапсырыс дайын"
    }
}

SERVICES = {
    "restore": {
        "uz": "📷 Foto restavratsiya",
        "ru": "📷 Реставрация фото",
        "en": "📷 Photo restoration",
        "qq": "📷 Foto restavratsiya",
        "kk": "📷 Фото реставрация"
    },
    "4k": {
        "uz": "🖼 4K / 8K qilish",
        "ru": "🖼 4K / 8K",
        "en": "🖼 4K / 8K",
        "qq": "🖼 4K / 8K",
        "kk": "🖼 4K / 8K"
    },
    "video": {
        "uz": "🎞 Video qilish",
        "ru": "🎞 Видео",
        "en": "🎞 Video",
        "qq": "🎞 Video",
        "kk": "🎞 Видео"
    }
}

# ================= HELPERS =================
def get_lang(uid):
    cur.execute("SELECT lang FROM users WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else "uz"

def set_lang(uid, lang):
    cur.execute("INSERT OR REPLACE INTO users VALUES(?,?)", (uid, lang))
    db.commit()

def menu_kb(lang):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SERVICES[k][lang])] for k in SERVICES],
        resize_keyboard=True
    )

def confirm_kb(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS["continue"][lang])],
            [KeyboardButton(text=TEXTS["cancel"][lang])]
        ],
        resize_keyboard=True
    )

def admin_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Accepted", callback_data=f"s:{order_id}:accepted")],
        [InlineKeyboardButton(text="⚙️ Working", callback_data=f"s:{order_id}:working")],
        [InlineKeyboardButton(text="✅ Done", callback_data=f"s:{order_id}:done")]
    ])

# ================= FSM =================
class Order(StatesGroup):
    file = State()
    comment = State()
    phone = State()

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="UZ", callback_data="lang_uz"),
         InlineKeyboardButton(text="RU", callback_data="lang_ru")],
        [InlineKeyboardButton(text="EN", callback_data="lang_en"),
         InlineKeyboardButton(text="QQ", callback_data="lang_qq")],
        [InlineKeyboardButton(text="KK", callback_data="lang_kk")]
    ])
    await m.answer(TEXTS["choose_lang"]["uz"], reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(c: CallbackQuery):
    lang = c.data.split("_")[1]
    set_lang(c.from_user.id, lang)
    await c.message.answer(TEXTS["menu"][lang], reply_markup=menu_kb(lang))
    await c.answer()

# ================= SERVICE =================
@dp.message(lambda m: m.text in [v for s in SERVICES.values() for v in s.values()])
async def choose_service(m: Message, state: FSMContext):
    lang = get_lang(m.from_user.id)
    service = next(k for k, v in SERVICES.items() if v[lang] == m.text)
    await state.update_data(service=service)
    await m.answer(TEXTS["confirm"][lang], reply_markup=confirm_kb(lang))

@dp.message(lambda m: m.text in TEXTS["cancel"].values())
async def cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(TEXTS["menu"][get_lang(m.from_user.id)], reply_markup=menu_kb(get_lang(m.from_user.id)))

@dp.message(lambda m: m.text in TEXTS["continue"].values())
async def cont(m: Message, state: FSMContext):
    await state.set_state(Order.file)
    await m.answer(TEXTS["send_photo"][get_lang(m.from_user.id)], reply_markup=ReplyKeyboardRemove())

# ================= FILE =================
@dp.message(Order.file, F.photo | F.document)
async def get_file(m: Message, state: FSMContext):
    file_id = m.photo[-1].file_id if m.photo else m.document.file_id
    await state.update_data(file_id=file_id)
    await state.set_state(Order.comment)
    await m.answer(TEXTS["send_comment"][get_lang(m.from_user.id)])

@dp.message(Order.comment)
async def get_comment(m: Message, state: FSMContext):
    await state.update_data(comment=m.text)
    await state.set_state(Order.phone)
    await m.answer(TEXTS["send_phone"][get_lang(m.from_user.id)],
                   reply_markup=ReplyKeyboardMarkup(
                       keyboard=[[KeyboardButton(text="📞", request_contact=True)]],
                       resize_keyboard=True))

@dp.message(Order.phone, F.contact)
async def finish(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(m.from_user.id)

    cur.execute("""
    INSERT INTO orders(user_id, service, comment, phone, status, file_id)
    VALUES(?,?,?,?,?,?)
    """, (m.from_user.id, data["service"], data["comment"],
          m.contact.phone_number, "accepted", data["file_id"]))
    db.commit()
    order_id = cur.lastrowid

    await bot.send_message(ADMIN_ID, f"🆕 Order #{order_id}", reply_markup=admin_kb(order_id))
    await m.answer(TEXTS["accepted"][lang], reply_markup=menu_kb(lang))
    await state.clear()

# ================= ADMIN =================
@dp.callback_query(F.data.startswith("s:"))
async def status(c: CallbackQuery):
    _, oid, st = c.data.split(":")
    cur.execute("UPDATE orders SET status=? WHERE id=?", (st, oid))
    db.commit()
    cur.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    uid = cur.fetchone()[0]
    await bot.send_message(uid, TEXTS[st][get_lang(uid)])
    await c.answer("OK")

# ================= WEBHOOK =================
async def webhook(request):
    upd = Update.model_validate(await request.json())
    await dp.feed_update(bot, upd)
    return web.Response(text="OK")

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
app.router.add_post(WEBHOOK_PATH, webhook)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print("SERVER STARTED ON PORT:", port)
    web.run_app(app, host="0.0.0.0", port=port)

