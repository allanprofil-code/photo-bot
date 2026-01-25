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

# ================= ENV (SOZLAMALAR) =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLICK_TOKEN = os.getenv("CLICK_TOKEN")   # Faqat CLICK token qoldi
ADMIN_ID = os.getenv("ADMIN_ID")
SUPPORT_LINK = os.getenv("SUPPORT_LINK") 
VIDEO_ID = os.getenv("VIDEO_ID")         

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
    provider TEXT,
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
    # --- OFERTA (Qisqa va Londa) ---
    "offer_short": {
        "uz": "✅ <b>Til tanlandi!</b>\n\nBotdan foydalanish orqali siz <a href='https://docs.google.com/document/d/1UR_EzfBfMsqc_hDMuRLtzKFcvVSVC95K7Eb_Wx_4HrI/edit?usp=sharing'>Ommaviy oferta</a> va <a href='https://docs.google.com/document/d/18ejaQJ_TUW1781JB3ii7RSe8--i_DCUM/edit?usp=sharing'>Maxfiylik siyosati</a> shartlariga rozilik bildirasiz.",
        
        "ru": "✅ <b>Язык выбран!</b>\n\nИспользуя бот, вы соглашаетесь с условиями <a href='https://docs.google.com/document/d/1UR_EzfBfMsqc_hDMuRLtzKFcvVSVC95K7Eb_Wx_4HrI/edit?usp=sharing'>Публичной оферты</a> и <a href='https://docs.google.com/document/d/18ejaQJ_TUW1781JB3ii7RSe8--i_DCUM/edit?usp=sharing'>Политики конфиденциальности</a>.",
        
        "en": "✅ <b>Language selected!</b>\n\nBy using the bot, you agree to the <a href='https://docs.google.com/document/d/1UR_EzfBfMsqc_hDMuRLtzKFcvVSVC95K7Eb_Wx_4HrI/edit?usp=sharing'>Public Offer</a> and <a href='https://docs.google.com/document/d/18ejaQJ_TUW1781JB3ii7RSe8--i_DCUM/edit?usp=sharing'>Privacy Policy</a>.",
        
        "qq": "✅ <b>Til tańlandı!</b>\n\nBottan paydalanıw arqalı siz <a href='https://docs.google.com/document/d/1UR_EzfBfMsqc_hDMuRLtzKFcvVSVC95K7Eb_Wx_4HrI/edit?usp=sharing'>Ommaviy oferta</a> hám <a href='https://docs.google.com/document/d/18ejaQJ_TUW1781JB3ii7RSe8--i_DCUM/edit?usp=sharing'>Qupıyalılıq siyasatı</a> shártlerine razılıq bildiresiz.",
        
        "kk": "✅ <b>Тіл таңдалды!</b>\n\nБотты пайдалану арқылы сіз <a href='https://docs.google.com/document/d/1UR_EzfBfMsqc_hDMuRLtzKFcvVSVC95K7Eb_Wx_4HrI/edit?usp=sharing'>Оферта</a> және <a href='https://docs.google.com/document/d/18ejaQJ_TUW1781JB3ii7RSe8--i_DCUM/edit?usp=sharing'>Құпиялылық саясаты</a> шарттарымен келісесіз."
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
        "uz": "✅ To'lov qabul qilindi!\n\n📂 <b>Iltimos, sifat buzilmasligi uchun rasmni FAYL (Document) ko'rinishida yuboring:</b>",
        "ru": "✅ Оплата принята!\n\n📂 <b>Пожалуйста, отправьте фото как ФАЙЛ (Документ), чтобы не потерять качество:</b>",
        "en": "✅ Payment accepted!\n\n📂 <b>Please send the photo as a FILE (Document) to preserve quality:</b>",
        "qq": "✅ Tólem qabıl etildi!\n\n📂 <b>Sapa buzılmawı ushın súwretti ilaji barınsha FAYL (Document) retinde jiberiń:</b>",
        "kk": "✅ Төлем қабылданды!\n\n📂 <b>Сапасы бұзылмас үшін суретті ФАЙЛ (Құжат) ретінде жіберіңіз:</b>"
    },
    "send_comment": {
        "uz": "📝 Izoh yozing (nima qilish kerak?):", "ru": "📝 Напишите комментарий (что нужно сделать?):", "en": "📝 Write a comment:", "qq": "📝 Izoh jazıń (ne qılıw kerek?):", "kk": "📝 Пікір жазыңыз:"
    },
    "send_phone": {
        "uz": "📞 Telefon raqamingizni yuboring:", "ru": "📞 Отправьте номер телефона:", "en": "📞 Send your phone number:", "qq": "📞 Telefon nomerińizdi jiberiń:", "kk": "📞 Телефон нөміріңізді жіберіңіз:"
    },
    "accepted": {
        "uz": "⏳ Buyurtma qabul qilindi! Tez orada aloqaga chiqamiz.", "ru": "⏳ Заказ принят! Скоро свяжемся.", "en": "⏳ Order accepted!", "qq": "⏳ Buyırtpa qabıl etildi! Tez arada baylanısqa shıǵamız.", "kk": "⏳ Тапсырыс қабылданды!"
    },
    "working": { "uz": "⚙️ Ishlanmoqda", "ru": "⚙️ В работе", "en": "⚙️ In progress", "qq": "⚙️ Islenip atır", "kk": "⚙️ Орындалуда" },
    "done": { "uz": "✅ Tayyor", "ru": "✅ Готово", "en": "✅ Done", "qq": "✅ Tayyar", "kk": "✅ Дайын" },
    "video_btn": { "uz": "🎬 Video Qo'llanma", "ru": "🎬 Видео инструкция", "en": "🎬 Video Tutorial", "qq": "🎬 Video Qollanba", "kk": "🎬 Видео Нұсқаулық" },
    "admin_btn": { "uz": "👨‍💻 Admin / Support", "ru": "👨‍💻 Админ / Поддержка", "en": "👨‍💻 Admin / Support", "qq": "👨‍💻 Admin / Járden", "kk": "👨‍💻 Әкімші / Қолдау" },
    "no_video": { "uz": "⚠️ Video hali yuklanmagan.", "ru": "⚠️ Видео еще не загружено.", "en": "⚠️ Video not uploaded yet.", "qq": "⚠️ Video ele júklenbegen.", "kk": "⚠️ Видео әлі жүктелмеген." }
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
    buttons.append([KeyboardButton(text=TEXTS["video_btn"][lang]), KeyboardButton(text=TEXTS["admin_btn"][lang])])
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
    # Til tanlash menyusi
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"), InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en"), InlineKeyboardButton(text="🇺🇿 Qaraqalpaqsha", callback_data="lang_qq")], 
        [InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang_kk")]
    ])
    await m.answer(TEXTS["choose_lang"]["uz"], reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(c: CallbackQuery):
    lang = c.data.split("_")[1]
    set_lang(c.from_user.id, lang)
    
    # 1. Qisqa Oferta matni (havolalar bilan)
    await c.message.answer(TEXTS["offer_short"][lang], parse_mode="HTML", disable_web_page_preview=True)
    
    # 2. Asosiy Menyu
    await c.message.answer(TEXTS["menu"][lang], reply_markup=menu_kb(lang))
    await c.answer()

# ================= VIDEO & ADMIN HANDLERS =================
@dp.message(lambda m: any(m.text == txt["uz"] or m.text == txt["ru"] or m.text == txt["qq"] for txt in [TEXTS["video_btn"], TEXTS["admin_btn"]]))
async def extra_buttons(m: Message):
    lang = get_lang(m.from_user.id)
    if m.text == TEXTS["video_btn"][lang]:
        if VIDEO_ID:
            try:
                await m.answer_video(video=VIDEO_ID, caption=TEXTS["video_btn"][lang])
            except:
                await m.answer(TEXTS["no_video"][lang])
        else:
            await m.answer("📹 Video instruktsiya tez orada yuklanadi.")
    elif m.text == TEXTS["admin_btn"][lang]:
        link = SUPPORT_LINK if SUPPORT_LINK else "https://t.me/admin"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👨‍💻 Admin", url=link)]])
        await m.answer(TEXTS["admin_btn"][lang], reply_markup=kb)

# ================= 1. XIZMAT TANLASH & TO'LOV =================
@dp.message(lambda m: any(m.text in conf["names"].values() for conf in SERVICES_CONFIG.values()))
async def select_service(m: Message, state: FSMContext):
    # Agar Click tokeni bo'lmasa, ogohlantirish
    if not CLICK_TOKEN:
        await m.answer("⚠️ Click token ulanmagan.")
        return

    lang = get_lang(m.from_user.id)
    selected_service = next((k for k, v in SERVICES_CONFIG.items() if v["names"][lang] == m.text), None)
    
    if not selected_service:
        return

    price = SERVICES_CONFIG[selected_service]["price"]
    label = SERVICES_CONFIG[selected_service]["names"][lang]
    
    await state.update_data(service=selected_service, price=price)

    # To'g'ridan-to'g'ri Invoice yuboramiz (Tanlash shart emas)
    try:
        await bot.send_invoice(
            chat_id=m.chat.id,
            title=TEXTS["invoice_title"][lang],
            description=f"{TEXTS['invoice_desc'][lang]}: {label}",
            payload=f"pay_{selected_service}",
            provider_token=CLICK_TOKEN,
            currency="UZS",
            prices=[LabeledPrice(label=label, amount=price)],
            start_parameter="pay",
            is_flexible=False  
        )
        await state.set_state(Order.waiting_payment)
    except Exception as e:
        await m.answer(f"Xatolik: {e}")

# ================= 2. PRE-CHECKOUT =================
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# ================= 3. TO'LOV SUCCESS =================
@dp.message(F.successful_payment)
async def successful_payment_handler(m: Message, state: FSMContext):
    lang = get_lang(m.from_user.id)
    await m.answer(TEXTS["after_pay"][lang], parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Order.file)

# ================= 4. FAYL & MA'LUMOTLAR =================
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

    cur.execute("INSERT INTO orders(user_id, service, amount, provider, comment, phone, status, file_id) VALUES(?,?,?,?,?,?,?,?)",
                (m.from_user.id, service_name, amount, "Click", data["comment"], phone, "paid_accepted", data["file_id"]))
    db.commit()
    order_id = cur.lastrowid

    file_status = "🖼 Rasm (Siquvda)" if data['file_type'] == "photo" else "📂 Fayl (Original)"
    caption = (
        f"🆕 BUYURTMA #{order_id}\n"
        f"💰 {int(amount)} UZS (Click)\n"
        f"👤 {m.from_user.full_name}\n"
        f"🛠 {service_name}\n"
        f"📦 {file_status}\n"
        f"📝 {data['comment']}\n"
        f"📞 {phone}"
    )
    
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
