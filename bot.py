import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    Update, LabeledPrice, PreCheckoutQuery
)
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN") 
ADMIN_ID = os.getenv("ADMIN_ID")

BASE_URL = os.getenv("BASE_URL")
# Webhook yo'li
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

# ================= TARJIMALAR =================
TEXTS = {
    "choose_lang": {
        "uz": "🌐 Tilni tanlang", "ru": "🌐 Выберите язык", "en": "🌐 Choose language", "qq": "🌐 Tildi tańlań", "kk": "🌐 Тілді таңдаңыз"
    },
    "menu": {
        "uz": "📸 Xizmatni tanlang:", "ru": "📸 Выберите услугу:", "en": "📸 Select service:", "qq": "📸 Xızmetti tańlań:", "kk": "📸 Қызметті таңдаңыз:"
    },
    "invoice_title": {
        "uz": "To'lov", "ru": "Оплата", "en": "Payment", "qq": "Tólem", "kk": "Төлем"
    },
    "invoice_desc": {
        "uz": "Xizmat uchun to'lovni amalga oshiring",
        "ru": "Пожалуйста, оплатите услугу", "en": "Please pay for the service", "qq": "Xızmet ushın tólemdi ámelge asırıń", "kk": "Қызмет үшін төлем жасаңыз"
    },
    "after_pay": {
        "uz": "✅ To'lov qabul qilindi!\nEndi rasm yoki faylni yuboring:",
        "ru": "✅ Оплата принята!\nТеперь отправьте фото или файл:",
        "en": "✅ Payment accepted!\nNow send the photo or file:",
        "qq": "✅ Tólem qabıl etildi!\nEndi súwret yaki fayldı jiberiń:",
        "kk": "✅ Төлем қабылданды!\nЕнді сурет немесе файл жіберіңіз:"
    },
    "send_comment": {
        "uz": "📝 Izoh yozing:", "ru": "📝 Напишите комментарий:", "en": "📝 Write a comment:", "qq": "📝 Izoh jazıń:", "kk": "📝 Пікір жазыңыз:"
    },
    "send_phone": {
        "uz": "📞 Telefon raqamingizni yuboring:", "ru": "📞 Отправьте номер телефона:", "en": "📞 Send your phone number:", "qq": "📞 Telefon nomerińizdi jiberiń:", "kk": "📞 Телефон нөміріңізді жіберіңіз:"
    },
    "accepted": {
        "uz": "⏳ Buyurtma qabul qilindi!", "ru": "⏳ Заказ принят!", "en": "⏳ Order accepted!", "qq": "⏳ Buyırtpa qabıl etildi!", "kk": "⏳ Тапсырыс қабылданды!"
    },
    "working": { "uz": "⚙️ Ishlanmoqda", "ru": "⚙️ В работе", "en": "⚙️ In progress", "qq": "⚙️ Islenip atır", "kk": "⚙️ Орындалуда" },
    "done": { "uz": "✅ Tayyor", "ru": "✅ Готово", "en": "✅ Done", "qq": "✅ Tayyar", "kk": "✅ Дайын" }
}

SERVICES_CONFIG = {
    "restore": { "price": 100000, "names": { "uz": "📷 Foto restavratsiya (1k)", "ru": "📷 Реставрация фото (1k)", "en": "📷 Photo restoration", "qq": "📷 Foto restavratsiya", "kk": "📷 Фото реставрация" } },
    "4k": { "price": 3000000, "names": { "uz": "🖼 4K / 8K qilish (30k)", "ru": "🖼 4K / 8K (30k)", "en": "🖼 4K / 8K upscale", "qq": "🖼 4K / 8K sapası", "kk": "🖼 4K / 8K жасау" } },
    "video": { "price": 8000000, "names": { "uz": "🎞 Video montaj (80k)", "ru": "🎞 Видео монтаж (80k)", "en": "🎞 Video editing", "qq": "🎞 Video montaj", "kk": "🎞 Видео монтаж" } }
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
    buttons = [[KeyboardButton(text=s["names"][lang])] for s in SERVICES_CONFIG.values()]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Qabul", callback_data=f"s:{order_id}:accepted")],
        [InlineKeyboardButton(text="⚙️ Ishlanmoqda", callback_data=f"s:{order_id}:working")],
        [InlineKeyboardButton(text="✅ Tayyor", callback_data=f"s:{order_id}:done")]
    ])

# ================= FSM =================
class Order(StatesGroup):
    waiting_payment = State()
    file = State()
    comment = State()
    phone = State()

# ================= START =================
@dp.message(CommandStart())
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 UZ", callback_data="lang_uz"), InlineKeyboardButton(text="🇷🇺 RU", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇸 EN", callback_data="lang_en"), InlineKeyboardButton(text="🇿🇦 QQ", callback_data="lang_qq")],
        [InlineKeyboardButton(text="🇰🇿 KK", callback_data="lang_kk")]
    ])
    await m.answer(TEXTS["choose_lang"]["uz"], reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(c: CallbackQuery):
    lang = c.data.split("_")[1]
    set_lang(c.from_user.id, lang)
    await c.message.answer(TEXTS["menu"][lang], reply_markup=menu_kb(lang))
    await c.answer()

# ================= 1. TO'LOV (INVOICE) =================
@dp.message(lambda m: any(m.text in conf["names"].values() for conf in SERVICES_CONFIG.values()))
async def send_invoice_handler(m: Message, state: FSMContext):
    try:
        if not PAYMENT_TOKEN:
            await m.answer("⚠️ To'lov tizimi ulanmagan.")
            return

        lang = get_lang(m.from_user.id)
        selected_service = next((k for k, v in SERVICES_CONFIG.items() if v["names"][lang] == m.text), None)
        
        if not selected_service:
            return

        price = SERVICES_CONFIG[selected_service]["price"]
        label = SERVICES_CONFIG[selected_service]["names"][lang]

        await state.update_data(service=selected_service, price=price)
        
        await bot.send_invoice(
            chat_id=m.chat.id,
            title=TEXTS["invoice_title"][lang],
            description=f"{TEXTS['invoice_desc'][lang]}: {label}",
            payload=f"pay_{selected_service}",
            provider_token=PAYMENT_TOKEN,
            currency="UZS",
            prices=[LabeledPrice(label=label, amount=price)],
            start_parameter="pay",
            is_flexible=False  # ✅ CORRECT
        )
        await state.set_state(Order.waiting_payment)

    except Exception as e:
        await m.answer(f"Xatolik: {e}")
        print(f"ERROR: {e}")

# ================= 2. PRE-CHECKOUT =================
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    try:
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        print(f"Pre-checkout error: {e}")

# ================= 3. SUCCESS =================
@dp.message(F.successful_payment)
async def successful_payment_handler(m: Message, state: FSMContext):
    lang = get_lang(m.from_user.id)
    await m.answer(TEXTS["after_pay"][lang], reply_markup=ReplyKeyboardRemove())
    await state.set_state(Order.file)

# ================= 4. DATA COLLECTION =================
@dp.message(Order.file, F.photo | F.document)
async def get_file(m: Message, state: FSMContext):
    file_id = m.photo[-1].file_id if m.photo else m.document.file_id
    file_type = "photo" if m.photo else "document"
    await state.update_data(file_id=file_id, file_type=file_type)
    await state.set_state(Order.comment)
    await m.answer(TEXTS["send_comment"][get_lang(m.from_user.id)])

@dp.message(Order.comment)
async def get_comment(m: Message, state: FSMContext):
    await state.update_data(comment=m.text)
    await state.set_state(Order.phone)
    await m.answer(TEXTS["send_phone"][get_lang(m.from_user.id)],
                   reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞", request_contact=True)]], resize_keyboard=True))

@dp.message(Order.phone, F.contact)
async def finish(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(m.from_user.id)
    phone = m.contact.phone_number
    amount = data['price'] / 100
    service_name = SERVICES_CONFIG[data["service"]]["names"][lang]

    cur.execute("INSERT INTO orders(user_id, service, amount, comment, phone, status, file_id) VALUES(?,?,?,?,?,?,?)",
                (m.from_user.id, service_name, amount, data["comment"], phone, "paid_accepted", data["file_id"]))
    db.commit()
    order_id = cur.lastrowid

    # Admin xabar
    caption = f"🆕 BUYURTMA #{order_id}\n💰 {int(amount)} UZS\n👤 {m.from_user.full_name}\n🛠 {service_name}\n📝 {data['comment']}\n📞 {phone}"
    
    try:
        if ADMIN_ID:
            admin_id_int = int(ADMIN_ID)
            if data['file_type'] == "photo":
                await bot.send_photo(admin_id_int, data['file_id'], caption=caption, reply_markup=admin_kb(order_id))
            else:
                await bot.send_document(admin_id_int, data['file_id'], caption=caption, reply_markup=admin_kb(order_id))
    except Exception as e:
        print(f"Admin send error: {e}")

    await m.answer(TEXTS["accepted"][lang], reply_markup=menu_kb(lang))
    await state.clear()

# ================= ADMIN STATUS =================
@dp.callback_query(F.data.startswith("s:"))
async def status(c: CallbackQuery):
    _, oid, st = c.data.split(":")
    cur.execute("UPDATE orders SET status=? WHERE id=?", (st, oid))
    db.commit()
    
    cur.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    res = cur.fetchone()
    if res:
        try:
            await bot.send_message(res[0], TEXTS[st][get_lang(res[0])])
        except: pass
    await c.answer("OK")

# ================= WEBHOOK =================
async def webhook_handler(request):
    try:
        data = await request.json()
        await dp.feed_update(bot, Update.model_validate(data))
        return web.Response(text="OK")
    except: return web.Response(text="Error", status=500)

async def home_handler(request):
    return web.Response(text="Bot is running!")

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
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
