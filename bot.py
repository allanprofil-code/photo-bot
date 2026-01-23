import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    Update, LabeledPrice, PreCheckoutQuery, ContentType
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN") # YANGI: To'lov tokeni
ADMIN_ID = os.getenv("ADMIN_ID")

BASE_URL = os.getenv("BASE_URL")
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
    amount INTEGER,
    comment TEXT,
    phone TEXT,
    status TEXT,
    file_id TEXT
)
""")
db.commit()

# ================= NARXLAR (TIYINDA) =================
# Telegramda 1 so'm = 100 tiyin.
# 50 000 so'm bo'lishi uchun 5 000 000 yozish kerak.
PRICES = {
    "restore": {"label": "Foto Restavratsiya", "amount": 5000000}, # 50 000 so'm
    "4k":      {"label": "4K / 8K Sifat",     "amount": 3000000}, # 30 000 so'm
    "video":   {"label": "Video Montaj",      "amount": 8000000}, # 80 000 so'm
}

# ================= TEXTS =================
TEXTS = {
    "choose_lang": {"uz": "🌐 Tilni tanlang", "ru": "🌐 Выберите язык"},
    "menu": {"uz": "📸 Xizmatni tanlang:", "ru": "📸 Выберите услугу:"},
    "pay_btn": {"uz": "💸 To'lov qilish", "ru": "💸 Оплатить"},
    "after_pay": {"uz": "✅ To'lov qabul qilindi!\nEndi rasm yoki faylni yuboring:", "ru": "✅ Оплата принята!\nТеперь отправьте фото или файл:"},
    "send_comment": {"uz": "📝 Izoh yozing:", "ru": "📝 Напишите комментарий:"},
    "send_phone": {"uz": "📞 Telefon raqamingizni yuboring:", "ru": "📞 Отправьте номер телефона:"},
    "accepted": {"uz": "⏳ Buyurtma qabul qilindi!", "ru": "⏳ Заказ принят!"},
    "cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"}
}

SERVICES_NAMES = {
    "restore": {"uz": "📷 Foto restavratsiya (50k)", "ru": "📷 Реставрация фото (50k)"},
    "4k":      {"uz": "🖼 4K / 8K qilish (30k)",     "ru": "🖼 4K / 8K (30k)"},
    "video":   {"uz": "🎞 Video qilish (80k)",        "ru": "🎞 Видео (80k)"}
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
    # Faqat 2 ta til qoldirdim soddalik uchun, xohlasangiz qo'shing
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SERVICES_NAMES[k][lang])] for k in SERVICES_NAMES],
        resize_keyboard=True
    )

def admin_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Qabul (Accepted)", callback_data=f"s:{order_id}:accepted")],
        [InlineKeyboardButton(text="⚙️ Ishlanmoqda (Working)", callback_data=f"s:{order_id}:working")],
        [InlineKeyboardButton(text="✅ Tayyor (Done)", callback_data=f"s:{order_id}:done")]
    ])

# ================= FSM =================
class Order(StatesGroup):
    waiting_payment = State() # To'lov kutilmoqda
    file = State()
    comment = State()
    phone = State()

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="O'zbekcha 🇺🇿", callback_data="lang_uz"),
         InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru")]
    ])
    await m.answer("Tilni tanlang / Выберите язык:", reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(c: CallbackQuery):
    lang = c.data.split("_")[1]
    set_lang(c.from_user.id, lang)
    await c.message.answer(TEXTS["menu"][lang], reply_markup=menu_kb(lang))
    await c.answer()

# ================= 1. XIZMAT TANLASH VA INVOICE YUBORISH =================
@dp.message(lambda m: any(m.text in v.values() for v in SERVICES_NAMES.values()))
async def send_invoice_handler(m: Message, state: FSMContext):
    lang = get_lang(m.from_user.id)
    
    # Qaysi xizmat ekanligini aniqlaymiz
    service_key = next(k for k, v in SERVICES_NAMES.items() if v[lang] == m.text)
    price_info = PRICES[service_key]

    await state.update_data(service=service_key, price=price_info["amount"])
    
    # Invoice yuboramiz
    await bot.send_invoice(
        chat_id=m.chat.id,
        title=SERVICES_NAMES[service_key][lang],
        description="Xizmat uchun to'lov",
        payload=f"pay_{service_key}", # Yashirin ma'lumot
        provider_token=PAYMENT_TOKEN,
        currency="UZS",
        prices=[LabeledPrice(label=price_info["label"], amount=price_info["amount"])],
        start_parameter="pay",
        photo_url="https://cdn-icons-png.flaticon.com/512/2331/2331966.png", # Rasm (ixtiyoriy)
        photo_height=512, photo_width=512, photo_size=512
    )
    await state.set_state(Order.waiting_payment)

# ================= 2. TO'LOVNI TEKSHIRISH (PRE-CHECKOUT) =================
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    # Bu yerda to'lovni ruxsat beramiz (agar tovar qolmagan bo'lsa False qaytarish mumkin)
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# ================= 3. TO'LOV MUVAFFAQIYATLI O'TDI =================
@dp.message(F.successful_payment)
async def successful_payment_handler(m: Message, state: FSMContext):
    lang = get_lang(m.from_user.id)
    
    # Bazaga yoki logga yozish mumkin: m.successful_payment.total_amount
    await m.answer(TEXTS["after_pay"][lang], reply_markup=ReplyKeyboardRemove())
    
    # Endi buyurtma jarayonini davom ettiramiz
    await state.set_state(Order.file)

# ================= 4. FILE, COMMENT, PHONE =================
@dp.message(Order.file, F.photo | F.document)
async def get_file(m: Message, state: FSMContext):
    if m.photo:
        file_id = m.photo[-1].file_id
        file_type = "photo"
    else:
        file_id = m.document.file_id
        file_type = "document"

    await state.update_data(file_id=file_id, file_type=file_type)
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
    phone = m.contact.phone_number
    amount_human = data['price'] / 100 # Tiyinni so'mga aylantiramiz

    cur.execute("""
    INSERT INTO orders(user_id, service, amount, comment, phone, status, file_id)
    VALUES(?,?,?,?,?,?,?)
    """, (m.from_user.id, data["service"], amount_human, data["comment"],
          phone, "paid_accepted", data["file_id"]))
    db.commit()
    order_id = cur.lastrowid

    # Admin xabari
    caption_text = (
        f"🆕 <b>YANGI BUYURTMA #{order_id}</b>\n"
        f"✅ <b>TO'LOV QILINGAN:</b> {int(amount_human)} so'm\n\n"
        f"👤 <b>Mijoz:</b> <a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>\n"
        f"🛠 <b>Xizmat:</b> {data['service']}\n"
        f"📝 <b>Izoh:</b> {data['comment']}\n"
        f"📞 <b>Tel:</b> {phone}"
    )

    try:
        if data['file_type'] == "photo":
            await bot.send_photo(chat_id=int(ADMIN_ID), photo=data['file_id'], caption=caption_text, parse_mode="HTML", reply_markup=admin_kb(order_id))
        else:
            await bot.send_document(chat_id=int(ADMIN_ID), document=data['file_id'], caption=caption_text, parse_mode="HTML", reply_markup=admin_kb(order_id))
    except Exception as e:
        await bot.send_message(int(ADMIN_ID), f"Xatolik: {e}\n{caption_text}")

    await m.answer(TEXTS["accepted"][lang], reply_markup=menu_kb(lang))
    await state.clear()

# ================= ADMIN ACTIONS =================
@dp.callback_query(F.data.startswith("s:"))
async def status(c: CallbackQuery):
    _, oid, st = c.data.split(":")
    # Bazada statusni yangilaymiz
    cur.execute("UPDATE orders SET status=? WHERE id=?", (st, oid))
    db.commit()
    await c.answer("Status yangilandi!")
    # Ixtiyoriy: Mijozga xabar yuborish logikasini shu yerga qo'shish mumkin

# ================= SERVER =================
async def webhook_handler(request):
    try:
        data = await request.json()
        upd = Update.model_validate(data)
        await dp.feed_update(bot, upd)
        return web.Response(text="OK")
    except:
        return web.Response(text="Error", status=500)

async def home_handler(request):
    return web.Response(text="Bot is running with Payments!")

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
app.router.add_post(WEBHOOK_PATH, webhook_handler)
app.router.add_get('/', home_handler)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)
