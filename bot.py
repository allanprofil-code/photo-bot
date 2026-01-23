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
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN") # BotFatherdan olingan Click/Payme tokeni
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

# ================= TARJIMALAR (5 TILDA) =================
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
        "ru": "Пожалуйста, оплатите услугу",
        "en": "Please pay for the service",
        "qq": "Xızmet ushın tólemdi ámelge asırıń",
        "kk": "Қызмет үшін төлем жасаңыз"
    },
    "pay_btn": {
        "uz": "💸 To'lov qilish", "ru": "💸 Оплатить", "en": "💸 Pay", "qq": "💸 Tólew", "kk": "💸 Төлеу"
    },
    "after_pay": {
        "uz": "✅ To'lov qabul qilindi!\nEndi rasm yoki faylni yuboring:",
        "ru": "✅ Оплата принята!\nТеперь отправьте фото или файл:",
        "en": "✅ Payment accepted!\nNow send the photo or file:",
        "qq": "✅ Tólem qabıl etildi!\nEndi súwret yaki fayldı jiberiń:",
        "kk": "✅ Төлем қабылданды!\nЕнді сурет немесе файл жіберіңіз:"
    },
    "cancel": {
        "uz": "❌ Bekor qilish", "ru": "❌ Отмена", "en": "❌ Cancel", "qq": "❌ Biykarlaw", "kk": "❌ Болдырмау"
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
    "working": {
        "uz": "⚙️ Ishlanmoqda", "ru": "⚙️ В работе", "en": "⚙️ In progress", "qq": "⚙️ Islenip atır", "kk": "⚙️ Орындалуда"
    },
    "done": {
        "uz": "✅ Tayyor", "ru": "✅ Готово", "en": "✅ Done", "qq": "✅ Tayyar", "kk": "✅ Дайын"
    }
}

# ================= XIZMATLAR VA NARXLAR =================
# Narxlar tiyinda ko'rsatilgan (1 so'm = 100 tiyin)
SERVICES_CONFIG = {
    "restore": {
        "price": 5000000, # 50 000 so'm
        "names": {
            "uz": "📷 Foto restavratsiya (50k)",
            "ru": "📷 Реставрация фото (50k)",
            "en": "📷 Photo restoration (50k)",
            "qq": "📷 Foto restavratsiya (50k)",
            "kk": "📷 Фото реставрация (50k)"
        }
    },
    "4k": {
        "price": 3000000, # 30 000 so'm
        "names": {
            "uz": "🖼 4K / 8K qilish (30k)",
            "ru": "🖼 4K / 8K (30k)",
            "en": "🖼 4K / 8K upscale (30k)",
            "qq": "🖼 4K / 8K sapası (30k)",
            "kk": "🖼 4K / 8K жасау (30k)"
        }
    },
    "video": {
        "price": 8000000, # 80 000 so'm
        "names": {
            "uz": "🎞 Video montaj (80k)",
            "ru": "🎞 Видео монтаж (80k)",
            "en": "🎞 Video editing (80k)",
            "qq": "🎞 Video montaj (80k)",
            "kk": "🎞 Видео монтаж (80k)"
        }
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
    # Shu tildagi xizmat nomlarini chiqaramiz
    buttons = []
    for s_conf in SERVICES_CONFIG.values():
        buttons.append([KeyboardButton(text=s_conf["names"][lang])])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Qabul (Accepted)", callback_data=f"s:{order_id}:accepted")],
        [InlineKeyboardButton(text="⚙️ Ishlanmoqda (Working)", callback_data=f"s:{order_id}:working")],
        [InlineKeyboardButton(text="✅ Tayyor (Done)", callback_data=f"s:{order_id}:done")]
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
        [InlineKeyboardButton(text="O'zbekcha 🇺🇿", callback_data="lang_uz"),
         InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru")],
        [InlineKeyboardButton(text="English 🇺🇸", callback_data="lang_en"),
         InlineKeyboardButton(text="Qaraqalpaqsha 🇿🇦", callback_data="lang_qq")], # Flag taxminiy
        [InlineKeyboardButton(text="Қазақша 🇰🇿", callback_data="lang_kk")]
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
    lang = get_lang(m.from_user.id)
    
    # Qaysi xizmat tanlanganini aniqlaymiz
    selected_service = None
    for s_key, s_conf in SERVICES_CONFIG.items():
        if s_conf["names"][lang] == m.text:
            selected_service = s_key
            break
            
    if not selected_service:
        return

    price = SERVICES_CONFIG[selected_service]["price"]
    label = SERVICES_CONFIG[selected_service]["names"][lang] # Invoice chekida chiqadigan nom

    await state.update_data(service=selected_service, price=price)
    
    # Invoice yuboramiz (Hamma narsa tanlangan tilda)
    await bot.send_invoice(
        chat_id=m.chat.id,
        title=TEXTS["invoice_title"][lang],
        description=f"{TEXTS['invoice_desc'][lang]}: {label}",
        payload=f"pay_{selected_service}",
        provider_token=PAYMENT_TOKEN,
        currency="UZS",
        prices=[LabeledPrice(label=label, amount=price)],
        start_parameter="pay",
        payload_kwargs={"is_flexible": False}
    )
    await state.set_state(Order.waiting_payment)

# ================= 2. PRE-CHECKOUT =================
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# ================= 3. SUCCESSFUL PAYMENT =================
@dp.message(F.successful_payment)
async def successful_payment_handler(m: Message, state: FSMContext):
    lang = get_lang(m.from_user.id)
    # To'lov muvaffaqiyatli
    await m.answer(TEXTS["after_pay"][lang], reply_markup=ReplyKeyboardRemove())
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
    amount_human = data['price'] / 100 
    service_name = SERVICES_CONFIG[data["service"]]["names"][lang]

    cur.execute("""
    INSERT INTO orders(user_id, service, amount, comment, phone, status, file_id)
    VALUES(?,?,?,?,?,?,?)
    """, (m.from_user.id, service_name, amount_human, data["comment"],
          phone, "paid_accepted", data["file_id"]))
    db.commit()
    order_id = cur.lastrowid

    # Admin xabari
    caption_text = (
        f"🆕 <b>YANGI BUYURTMA #{order_id}</b>\n"
        f"✅ <b>TO'LOV:</b> {int(amount_human)} so'm\n\n"
        f"👤 <b>Mijoz:</b> <a href='tg://user?id={m.from_user.id}'>{m.from_user.full_name}</a>\n"
        f"🛠 <b>Xizmat:</b> {service_name}\n"
        f"📝 <b>Izoh:</b> {data['comment']}\n"
        f"📞 <b>Tel:</b> {phone}\n"
        f"🌐 <b>Til:</b> {lang.upper()}"
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
    cur.execute("UPDATE orders SET status=? WHERE id=?", (st, oid))
    db.commit()
    
    # Mijozga o'z tilida xabar yuborish
    cur.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    res = cur.fetchone()
    if res:
        uid = res[0]
        try:
            user_lang = get_lang(uid)
            await bot.send_message(uid, TEXTS[st][user_lang])
        except:
            pass
            
    await c.answer("Status yangilandi!")

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
    return web.Response(text="Bot is running with 5 Languages & Payments!")

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
