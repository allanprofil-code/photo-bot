import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, Update,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = "https://photo-bot-rm8n.onrender.com"
ADMIN_IDS = [123456789]  # 🔴 O'ZINGIZNI ADMIN ID QILING

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ================== STATES ==================

class Order(StatesGroup):
    waiting_photo = State()
    comment = State()

# ================== TEXTS ==================

TEXTS = {
    "menu": {
        "qq": "Xızmetti tańlań:",
        "uz": "Xizmatni tanlang:",
        "ru": "Выберите услугу:",
        "en": "Choose a service:",
        "kk": "Қызметті таңдаңыз:"
    },
    "confirm": {
        "qq": "Davom etemizbe?",
        "uz": "Davom etamizmi?",
        "ru": "Продолжаем?",
        "en": "Shall we continue?",
        "kk": "Жалғастырамыз ба?"
    },
    "continue": {
        "qq": "✅ Davom etemiz",
        "uz": "✅ Davom etamiz",
        "ru": "✅ Продолжить",
        "en": "✅ Continue",
        "kk": "✅ Жалғастыру"
    },
    "cancel": {
        "qq": "❌ Biykarlaw",
        "uz": "❌ Bekor qilish",
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "kk": "❌ Болдырмау"
    },
    "send_photo": {
        "qq": "📷 Foto yáki fayl jiberiń",
        "uz": "📷 Rasm yoki fayl yuboring",
        "ru": "📷 Отправьте фото или файл",
        "en": "📷 Send photo or file",
        "kk": "📷 Фото немесе файл жіберіңіз"
    },
    "admin_menu": {
        "qq": "🛠 Admin panel",
        "uz": "🛠 Admin panel",
        "ru": "🛠 Админ панель",
        "en": "🛠 Admin panel",
        "kk": "🛠 Admin панелі"
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

# ================== HELPERS ==================

def get_lang(user_id: int) -> str:
    return "uz"  # 🔧 xohlasangiz DB bilan qilamiz

def get_menu(lang):
    kb = [
        [KeyboardButton(text="📸 Foto xizmat")],
    ]
    if lang:
        pass
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_confirm_kb(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS["continue"][lang])],
            [KeyboardButton(text=TEXTS["cancel"][lang])]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# ================== USER HANDLERS ==================

@dp.message(F.text == "/start")
async def start(message: Message):
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS["menu"][lang], reply_markup=get_menu(lang))

@dp.message(F.text == "📸 Foto xizmat")
async def select_service(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    await message.answer(
        f"💰 Narx: 10 000 so'm\n\n{TEXTS['confirm'][lang]}",
        reply_markup=get_confirm_kb(lang)
    )

@dp.message(lambda m: m.text in TEXTS["continue"].values())
async def confirm_order(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    await state.set_state(Order.waiting_photo)
    await message.answer(TEXTS["send_photo"][lang], reply_markup=ReplyKeyboardRemove())

@dp.message(lambda m: m.text in TEXTS["cancel"].values())
async def cancel_order(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS["menu"][lang], reply_markup=get_menu(lang))

# ================== PHOTO OR FILE ==================

@dp.message(Order.waiting_photo)
async def get_photo_or_file(message: Message, state: FSMContext):
    file_id = None

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        await message.answer("❌ Iltimos, foto yoki fayl yuboring")
        return

    await state.update_data(file_id=file_id)
    await state.set_state(Order.comment)
    await message.answer("✍️ Izoh yozing (yoki - deb yuboring)")

@dp.message(Order.comment, F.text)
async def finish_order(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    for admin in ADMIN_IDS:
        await bot.send_message(
            admin,
            f"🆕 Yangi buyurtma\n"
            f"👤 @{message.from_user.username}\n"
            f"💬 Izoh: {message.text}"
        )
        await bot.send_document(admin, data["file_id"])

    await message.answer("✅ Buyurtma yuborildi")

# ================== ADMIN ==================

@dp.message(F.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS["admin_menu"][lang])

# ================== WEBHOOK ==================

async def telegram_webhook(request):
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return web.Response(text="OK")

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    print("Webhook set")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

# ================== APP ==================

app = web.Application()
app.router.add_post(WEBHOOK_PATH, telegram_webhook)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    print("Webhook server started")
    web.run_app(app, host="0.0.0.0", port=10000)
