import os
import sqlite3
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ================== CONFIG ==================
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PORT = int(os.getenv("PORT", 8080))

if not TOKEN or not ADMIN_ID:
    raise RuntimeError("TOKEN yoki ADMIN_ID yo‘q")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== DATABASE ==================
conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT,
    price TEXT,
    comment TEXT,
    phone TEXT,
    status TEXT,
    user_id INTEGER
)
""")
conn.commit()

# ================== HELPERS ==================
def get_lang(user_id):
    cursor.execute("SELECT language FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "uz"

def set_lang(user_id, lang):
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)",
        (user_id, lang)
    )
    conn.commit()

# ================== TEXTS ==================
TEXTS = {
    "start": {
        "qq": "📸 Foto xızmetleri botına xosh kelipsiz!",
        "uz": "📸 Foto xizmatlar botiga xush kelibsiz!",
        "ru": "📸 Добро пожаловать в фото-сервис бот!",
        "en": "📸 Welcome to the photo services bot!",
        "kk": "📸 Фото қызметтері ботына қош келдіңіз!"
    },
    "choose_lang": {
        "qq": "🌐 Tildi tańlań",
        "uz": "🌐 Tilni tanlang",
        "ru": "🌐 Выберите язык",
        "en": "🌐 Choose language",
        "kk": "🌐 Тілді таңдаңыз"
    },
    "menu": {
        "qq": "📸 Xızmetti tańlań:",
        "uz": "📸 Xizmatni tanlang:",
        "ru": "📸 Выберите услугу:",
        "en": "📸 Select service:",
        "kk": "📸 Қызметті таңдаңыз:"
    },
    "confirm": {
        "qq": "Davom etemizbe?",
        "uz": "Davom etamizmi?",
        "ru": "Продолжаем?",
        "en": "Shall we continue?",
        "kk": "Жалғастырамыз ба?"
    },
    "cancel": {
        "qq": "❌ Biykarlaw",
        "uz": "❌ Bekor qilish",
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "kk": "❌ Болдырмау"
    },
    "continue": {
        "qq": "✅ Davom etemiz",
        "uz": "✅ Davom etamiz",
        "ru": "✅ Продолжить",
        "en": "✅ Continue",
        "kk": "✅ Жалғастыру"
    },
    "photo": {
        "qq": "📷 Surat jiberiñ (foto yoki fayl)",
        "uz": "📷 Rasm yuboring (foto yoki fayl)",
        "ru": "📷 Отправьте изображение",
        "en": "📷 Send image",
        "kk": "📷 Суретті жіберіңіз"
    },
    "status_user": {
        "accepted": {
            "qq": "⏳ Buyurtmañız qabıl etildi",
            "uz": "⏳ Buyurtmangiz qabul qilindi",
            "ru": "⏳ Ваш заказ принят",
            "en": "⏳ Your order has been accepted",
            "kk": "⏳ Тапсырысыңыз қабылданды"
        },
        "working": {
            "qq": "⚙️ Buyurtmañız islewde",
            "uz": "⚙️ Buyurtmangiz ishlanmoqda",
            "ru": "⚙️ Ваш заказ в работе",
            "en": "⚙️ Your order is in progress",
            "kk": "⚙️ Тапсырысыңыз орындалуда"
        },
        "done": {
            "qq": "✅ Buyurtmañız tayyar!",
            "uz": "✅ Buyurtmangiz tayyor!",
            "ru": "✅ Ваш заказ готов!",
            "en": "✅ Your order is ready!",
            "kk": "✅ Тапсырысыңыз дайын!"
        }
    }
}

# ================== SERVICES ==================
SERVICES = {
    "restore": {
        "qq": "📷 Foto restavratsiya",
        "uz": "📷 Foto restavratsiya",
        "ru": "📷 Реставрация фото",
        "en": "📷 Photo restoration",
        "kk": "📷 Фото реставрация"
    },
    "4k": {
        "qq": "🖼 4K / 8K qılıw",
        "uz": "🖼 4K / 8K qilish",
        "ru": "🖼 Сделать 4K / 8K",
        "en": "🖼 Make 4K / 8K",
        "kk": "🖼 4K / 8K жасау"
    },
    "video": {
        "qq": "🎞 Video qılıw",
        "uz": "🎞 Video qilish",
        "ru": "🎞 Сделать видео",
        "en": "🎞 Make video",
        "kk": "🎞 Видео жасау"
    }
}

PRICES = {
    "restore": "50 000 so‘m",
    "4k": "30 000 so‘m",
    "video": "80 000 so‘m"
}

# ================== FSM ==================
class Order(StatesGroup):
    photo = State()
    comment = State()
    phone = State()

# ================== KEYBOARDS ==================
def get_menu(lang):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SERVICES[k][lang])] for k in SERVICES],
        resize_keyboard=True
    )

def get_confirm_kb(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS["continue"][lang])],
            [KeyboardButton(text=TEXTS["cancel"][lang])]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

phone_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📞 Telefon raqam yuborish", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

lang_kb = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="Qaraqalpaqsha", callback_data="lang_qq"),
        InlineKeyboardButton(text="O'zbekcha", callback_data="lang_uz")
    ],
    [
        InlineKeyboardButton(text="Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="English", callback_data="lang_en")
    ],
    [
        InlineKeyboardButton(text="Qazaqsha", callback_data="lang_kk")
    ]
])

def admin_buttons(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Accepted", callback_data=f"status:{order_id}:accepted")],
        [InlineKeyboardButton(text="⚙️ Working", callback_data=f"status:{order_id}:working")],
        [InlineKeyboardButton(text="✅ Done", callback_data=f"status:{order_id}:done")]
    ])

# ================== HANDLERS ==================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(TEXTS["choose_lang"]["uz"], reply_markup=lang_kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(call: CallbackQuery):
    lang = call.data.split("_")[1]
    set_lang(call.from_user.id, lang)
    await call.message.answer(TEXTS["start"][lang])
    await call.message.answer(TEXTS["menu"][lang], reply_markup=get_menu(lang))
    await call.answer()

@dp.message()
async def select_service(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    for key in SERVICES:
        if message.text == SERVICES[key][lang]:
            await state.update_data(service=key)
            await message.answer(
                f"💰 {PRICES[key]}\n\n{TEXTS['confirm'][lang]}",
                reply_markup=get_confirm_kb(lang)
            )
            return

@dp.message(lambda m: m.text in TEXTS["cancel"].values())
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS["menu"][lang], reply_markup=get_menu(lang))

@dp.message(lambda m: m.text in TEXTS["continue"].values())
async def continue_order(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    await state.set_state(Order.photo)
    await message.answer(TEXTS["photo"][lang], reply_markup=ReplyKeyboardRemove())

@dp.message(Order.photo)
async def get_photo(message: Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
    else:
        await message.answer("❌ Faqat rasm yuboring")
        return

    await state.update_data(photo=file_id)
    await state.set_state(Order.comment)
    await message.answer("📝 Izoh yozing:")

@dp.message(Order.comment, F.text)
async def get_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await state.set_state(Order.phone)
    await message.answer("📞 Telefon raqamingizni yuboring:", reply_markup=phone_kb)

@dp.message(Order.phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute(
        "INSERT INTO orders (service, price, comment, phone, status, user_id) VALUES (?, ?, ?, ?, ?, ?)",
        (data["service"], PRICES[data["service"]], data["comment"],
         message.contact.phone_number, "accepted", message.from_user.id)
    )
    conn.commit()
    order_id = cursor.lastrowid

    await bot.send_photo(
        ADMIN_ID,
        data["photo"],
        caption=f"🆕 BUYURTMA #{order_id}\n📌 {data['service']}\n💰 {PRICES[data['service']]}\n📞 {message.contact.phone_number}",
        reply_markup=admin_buttons(order_id)
    )

    lang = get_lang(message.from_user.id)
    await message.answer("✅ Buyurtma qabul qilindi!", reply_markup=get_menu(lang))
    await state.clear()

@dp.callback_query(F.data.startswith("status:"))
async def change_status(call: CallbackQuery):
    _, order_id, status = call.data.split(":")
    cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
    user_id = cursor.fetchone()[0]
    lang = get_lang(user_id)

    cursor.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()

    await bot.send_message(user_id, TEXTS["status_user"][status][lang])
    await call.answer("OK")

# ================== WEBHOOK ==================
async def handle_update(request: web.Request):
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return web.Response(text="OK")

async def healthcheck(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_post(f"/webhook/{TOKEN}", handle_update)
    app.router.add_get("/", healthcheck)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print("Webhook server started")

if __name__ == "__main__":
    asyncio.run(main())
