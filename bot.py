import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import asyncio
import sqlite3

# ================== SOZLAMALAR ==================
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ================== DATABASE ==================
conn = sqlite3.connect("orders.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT,
    price TEXT,
    comment TEXT,
    phone TEXT,
    status TEXT
)
""")
conn.commit()
try:
    cursor.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER")
    conn.commit()
except:
    pass
# ================== NARXLAR ==================
PRICES = {
    "📷 Foto restavratsiya": "50 000 so‘m",
    "🖼 4K / 8K qilish": "30 000 so‘m",
    "🎞 Video qilish": "80 000 so‘m",
}

# ================== FSM ==================
class Order(StatesGroup):
    photo = State()
    comment = State()
    phone = State()

# ================== MENYULAR ==================
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

# ================== ADMIN TUGMALARI ==================
def admin_buttons(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Qabul qilindi", callback_data=f"status:{order_id}:accepted")],
            [InlineKeyboardButton(text="⚙️ Ishlanmoqda", callback_data=f"status:{order_id}:working")],
            [InlineKeyboardButton(text="✅ Tayyor", callback_data=f"status:{order_id}:done")],
        ]
    )

# ================== HANDLERLAR ==================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📸 Xizmatni tanlang:", reply_markup=menu)

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
    await message.answer("❌ Bekor qilindi", reply_markup=menu)

@dp.message(F.text == "✅ Davom etamiz")
async def confirm(message: Message, state: FSMContext):
    await state.set_state(Order.photo)
    await message.answer("📷 Rasmni yuboring:", reply_markup=ReplyKeyboardRemove())

@dp.message(Order.photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
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
        (
            data["service"],
            PRICES[data["service"]],
            data["comment"],
            message.contact.phone_number,
            "⏳ Qabul qilindi",
            message.from_user.id
        )
    )
    conn.commit()

    order_id = cursor.lastrowid   # 🔥 MANA SHU QATOR MUHIM

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=data["photo"],
        caption=(
            f"🆕 BUYURTMA #{order_id}\n\n"
            f"📌 Xizmat: {data['service']}\n"
            f"💰 Narx: {PRICES[data['service']]}\n"
            f"📝 Izoh: {data['comment']}\n"
            f"📞 Telefon: {message.contact.phone_number}\n"
            f"📊 Holat: ⏳ Qabul qilindi"
        ),
        reply_markup=admin_buttons(order_id)
    )

    await message.answer("✅ Buyurtma qabul qilindi!", reply_markup=menu)
    await state.clear()
# ================== STATUS O‘ZGARTIRISH ==================
@dp.callback_query(lambda c: c.data.startswith("status:"))
async def change_status(callback: types.CallbackQuery):
    _, order_id, new_status = callback.data.split(":")

    status_map = {
        "accepted": "⏳ Buyurtmangiz qabul qilindi",
        "working": "⚙️ Buyurtmangiz ishlanmoqda",
        "done": "✅ Buyurtmangiz tayyor!"
    }

    status_db = {
        "accepted": "⏳ Qabul qilindi",
        "working": "⚙️ Ishlanmoqda",
        "done": "✅ Tayyor"
    }

    cursor.execute(
        "SELECT user_id FROM orders WHERE id = ?",
        (order_id,)
    )
    user_id = cursor.fetchone()[0]

    cursor.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (status_db[new_status], order_id)
    )
    conn.commit()

    await callback.message.edit_caption(
        callback.message.caption.split("📊 Holat:")[0] +
        f"📊 Holat: {status_db[new_status]}"
    )

    await bot.send_message(user_id, status_map[new_status])
    await callback.answer("Mijozga yuborildi ✅")

from aiohttp import web
import asyncio

async def healthcheck(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get("/", healthcheck)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

async def main():
    await start_web()
    await dp.start_polling(bot)
# ================== START ==================
async def main():
    await start_web()
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())




