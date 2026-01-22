import os
import asyncio
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
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

# ================== SOZLAMALAR ==================
# Agar .env fayl bo'lmasa, tokenlarni shu yerga qo'lda yozib test qilishingiz mumkin
TOKEN = os.getenv("TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN or not ADMIN_ID:
    print("Xatolik: TOKEN yoki ADMIN_ID topilmadi!")
    exit()

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== DATABASE ==================
# check_same_thread=False - asinxron botda xatolik bermasligi uchun kerak
conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

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

# Users jadvali til sozlamalari uchun
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language TEXT
)
""")
conn.commit()

# ================== TARJIMALAR VA MATNLAR ==================
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
    "menu_text": {
        "qq": "📸 Xızmetti tańlań:",
        "uz": "📸 Xizmatni tanlang:",
        "ru": "📸 Выберите услугу:",
        "en": "📸 Select service:",
        "kk": "📸 Қызметті таңдаңыз:"
    }
}

def get_lang(user_id):
    cursor.execute("SELECT language FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "uz"

def set_lang(user_id, lang):
    cursor.execute("INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)", (user_id, lang))
    conn.commit()

# ================== NARXLAR ==================
PRICES = {
    "📷 Foto restavratsiya": "50 000 so‘m",
    "🖼 4K / 8K qilish": "30 000 so‘m",
    "🎞 Video qilish": "80 000 so‘m",
}

# ================== FSM (Holatlar) ==================
class Order(StatesGroup):
    photo = State()
    comment = State()
    phone = State()

# ================== KLAVIATURALAR ==================
menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=s)] for s in PRICES.keys()],
    resize_keyboard=True
)

confirm_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Davom etamiz")],
        [KeyboardButton(text="❌ Bekor qilish")]
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

def admin_buttons(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Qabul qilindi", callback_data=f"status:{order_id}:accepted")],
            [InlineKeyboardButton(text="⚙️ Ishlanmoqda", callback_data=f"status:{order_id}:working")],
            [InlineKeyboardButton(text="✅ Tayyor", callback_data=f"status:{order_id}:done")],
        ]
    )

# ================== HANDLERLAR (MANTIQ) ==================

# 1. Start bosilganda til tanlash chiqadi
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    # Foydalanuvchi tilini tekshiramiz, agar yangi bo'lsa standart 'uz'
    await message.answer(TEXTS["choose_lang"]["uz"], reply_markup=lang_kb)

# 2. Til tanlangandan keyin menyu chiqadi
@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def change_lang(call: CallbackQuery):
    lang = call.data.split("_")[1]
    set_lang(call.from_user.id, lang)
    
    await call.message.answer(TEXTS["start"][lang])
    await call.message.answer(TEXTS["menu_text"][lang], reply_markup=menu)
    await call.answer()

# 3. Xizmat tanlash
@dp.message(F.text.in_(PRICES.keys()))
async def select_service(message: Message, state: FSMContext):
    await state.update_data(service=message.text)
    await message.answer(
        f"💰 Narx: {PRICES[message.text]}\n\nDavom etamizmi?",
        reply_markup=confirm_kb
    )

@dp.message(F.text == "❌ Bekor qilish")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    user_lang = get_lang(message.from_user.id)
    await message.answer("❌ Bekor qilindi", reply_markup=menu)

@dp.message(F.text == "✅ Davom etamiz")
async def confirm(message: Message, state: FSMContext):
    await state.set_state(Order.photo)
    await message.answer("📷 Rasmni yuboring:", reply_markup=ReplyKeyboardRemove())

@dp.message(Order.photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    # Eng yuqori sifatdagi rasmni olamiz (-1)
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(Order.comment)
    await message.answer("📝 Izoh yozing (nima qilish kerak?):")

@dp.message(Order.comment, F.text)
async def get_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text)
    await state.set_state(Order.phone)
    await message.answer("📞 Telefon raqamingizni yuboring:", reply_markup=phone_kb)

@dp.message(Order.phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    phone = message.contact.phone_number

    # Bazaga yozish
    cursor.execute(
        "INSERT INTO orders (service, price, comment, phone, status, user_id) VALUES (?, ?, ?, ?, ?, ?)",
        (data["service"], PRICES[data["service"]], data["comment"], phone, "⏳ Qabul qilindi", user_id)
    )
    conn.commit()
    
    order_id = cursor.lastrowid

    # Adminga yuborish
    try:
        await bot.send_photo(
            chat_id=int(ADMIN_ID),
            photo=data["photo"],
            caption=(
                f"🆕 BUYURTMA #{order_id}\n\n"
                f"👤 User: {message.from_user.full_name}\n"
                f"📌 Xizmat: {data['service']}\n"
                f"💰 Narx: {PRICES[data['service']]}\n"
                f"📝 Izoh: {data['comment']}\n"
                f"📞 Telefon: {phone}\n"
                f"📊 Holat: ⏳ Qabul qilindi"
            ),
            reply_markup=admin_buttons(order_id)
        )
    except Exception as e:
        print(f"Adminga yuborishda xatolik: {e}")

    await message.answer("✅ Buyurtma qabul qilindi! Tez orada aloqaga chiqamiz.", reply_markup=menu)
    await state.clear()

# ================== STATUS O‘ZGARTIRISH (ADMIN) ==================
@dp.callback_query(lambda c: c.data.startswith("status:"))
async def change_status(callback: types.CallbackQuery):
    try:
        _, order_id, new_status = callback.data.split(":")

        status_map = {
            "accepted": "⏳ Buyurtmangiz qabul qilindi",
            "working": "⚙️ Buyurtmangiz ustida ishlanmoqda",
            "done": "✅ Buyurtmangiz tayyor!"
        }

        status_db_text = {
            "accepted": "⏳ Qabul qilindi",
            "working": "⚙️ Ishlanmoqda",
            "done": "✅ Tayyor"
        }

        # User ID ni olish
        cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        result = cursor.fetchone()
        
        if not result:
            await callback.answer("Buyurtma topilmadi!", show_alert=True)
            return

        user_id = result[0]

        # Bazada yangilash
        cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status_db_text[new_status], order_id))
        conn.commit()

        # Admin xabarini yangilash (Caption)
        current_caption = callback.message.caption
        if "📊 Holat:" in current_caption:
            new_caption = current_caption.split("📊 Holat:")[0] + f"📊 Holat: {status_db_text[new_status]}"
            if new_caption != current_caption:
                await callback.message.edit_caption(caption=new_caption, reply_markup=admin_buttons(order_id))

        # Mijozga xabar yuborish
        await bot.send_message(user_id, status_map[new_status])
        await callback.answer("Mijozga xabar yuborildi ✅")
    
    except Exception as e:
        await callback.answer(f"Xatolik: {e}", show_alert=True)

# ================== WEB SERVER (Render/Heroku uchun) ==================
async def healthcheck(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get("/", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server {port}-portda ishga tushdi")

# ================== MAIN ==================
async def main():
    # Web server va Botni parallel ishga tushirish
    await asyncio.gather(
        start_web(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi")
