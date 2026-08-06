import os
import re
import asyncio
import difflib
import logging
from datetime import datetime
from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import database as db

# ----------------- Sozlamalar -----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suhbat bosqichlari (ConversationHandler uchun)
CHOOSE_PRODUCT, ENTER_QUANTITY, ENTER_REGION, ENTER_ADDRESS, ENTER_PHONE, CONFIRM = range(6)
CHOOSE_SPECIFIC_MATCH = 407

# Sotuvchi ro'yxatdan o'tish bosqichlari
SELLER_NAME, SELLER_PHONE, SELLER_REGION, SELLER_HAS_VEHICLE, SELLER_VEHICLE_TYPE, SELLER_CAPACITY = range(100, 106)

# Sotuvchi mahsulot qo'shish bosqichlari
SP_NAME, SP_TYPE, SP_PRICE, SP_QUANTITY, SP_DESC, SP_PHOTO, SP_ADDRESS, SP_LOCATION, SP_REGIONS, SP_TUMANS = range(200, 210)
SP_FREE_TEXT = 210

# Haydovchi ro'yxatdan o'tish bosqichlari
DRV_NAME, DRV_PHONE, DRV_VEHICLE, DRV_NUMBER, DRV_CAPACITY, DRV_REGION, DRV_TUMAN, DRV_LOCATION = range(300, 308)

# Haydovchi yuk olish bosqichlari (tonna/gektar → qayta sotish miqdori → narx → rasm)
CLAIM_SET_TONNAGE = 399
CLAIM_SET_PRICE = 400
CLAIM_SET_PHOTO = 402
CLAIM_SET_RESALE_QTY = 403

# Haydovchi tarozi natijasini kiritish bosqichi
ENTER_WEIGHT = 401
ENTER_WEIGHT_PHOTO = 405

# Fermer to'g'ridan-to'g'ri miqdor kiritish bosqichi
FARMER_ENTER_WEIGHT = 404
FARMER_ENTER_PRICE = 406

# Kombayn egasi ro'yxatdan o'tish bosqichlari
COMBINE_NAME, COMBINE_PHONE, COMBINE_REGION = range(600, 603)

# Kombayn texnikasi qo'shish bosqichlari
CL_MODEL, CL_PRICE, CL_COVERAGE, CL_PHOTO, CL_ADDRESS = range(610, 615)

# Kombayn egasi silos elonini joylashtirish bosqichlari
CS_PRICE, CS_QUANTITY, CS_PHOTO, CS_ADDRESS, CS_LOCATION, CS_REGIONS, CS_TUMANS = range(620, 627)

# Haydovchi "Mashinada sotiladi" elonini joylashtirish bosqichlari
DS_PRICE, DS_QUANTITY, DS_PHOTO, DS_ADDRESS = range(630, 634)

# Fermer jadvalga qo'lda qator qo'shish bosqichlari
ML_VEHICLE, ML_PHONE, ML_PRICE = range(640, 643)
ML_TONNA_ENTRY = 643

# Admin: katalogga element qo'shish bosqichlari (urug'lar, vetapteka, o'g'itlar)
CAT_CATEGORY, CAT_NAME, CAT_COMPANY, CAT_DESC, CAT_PRICE, CAT_UNIT = range(500, 506)

# O'zbekiston viloyatlari ro'yxati (yetkazib berish hududi tanlash uchun)
def fmt_money(n):
    """Sonni 1000-lik guruhlarga probel bilan formatlaydi (masalan 520000 -> '520 000').
    Butun caption matniga .replace(',', ' ') qilishdan farqli o'laroq, bu FAQAT sonni formatlaydi —
    manzil yoki izohdagi haqiqiy vergullarni buzmaydi."""
    try:
        if isinstance(n, float) and n == int(n):
            n = int(n)
        return f"{n:,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(n)


REGIONS = [
    "Toshkent shahri", "Toshkent viloyati", "Andijon", "Farg'ona", "Namangan",
    "Samarqand", "Buxoro", "Navoiy", "Qashqadaryo", "Surxondaryo",
    "Jizzax", "Sirdaryo", "Xorazm", "Qoraqalpog'iston"
]

# Har bir viloyat uchun tumanlar (qo'shni tumanlarni aniq tanlash uchun)
TUMANLAR = {
    "Toshkent shahri": [
        "Bektemir", "Chilonzor", "Mirzo Ulug'bek", "Mirobod", "Olmazor", "Sergeli",
        "Shayxontohur", "Uchtepa", "Yakkasaroy", "Yashnobod", "Yunusobod", "Yangihayot"
    ],
    "Toshkent viloyati": [
        "Bekobod", "Bo'ka", "Bo'stonliq", "Chinoz", "Qibray", "Ohangaron", "Oqqo'rg'on",
        "Parkent", "Piskent", "Quyi Chirchiq", "O'rta Chirchiq", "Yuqori Chirchiq",
        "Yangiyo'l", "Zangiota", "Toshkent tumani"
    ],
    "Andijon": [
        "Andijon shahri", "Andijon tumani", "Asaka", "Baliqchi", "Bo'z", "Buloqboshi",
        "Izboskan", "Jalaquduq", "Xo'jaobod", "Qo'rg'ontepa", "Marhamat", "Oltinko'l",
        "Paxtaobod", "Shahrixon", "Ulug'nor", "Xonobod"
    ],
    "Farg'ona": [
        "Farg'ona shahri", "Marg'ilon", "Qo'qon", "Farg'ona tumani", "Bag'dod", "Beshariq",
        "Buvayda", "Dang'ara", "Furqat", "Oltiariq", "Quva", "Quvasoy", "Rishton",
        "So'x", "Toshloq", "Uchko'prik", "O'zbekiston", "Yozyovon"
    ],
    "Namangan": [
        "Namangan shahri", "Namangan tumani", "Chortoq", "Chust", "Kosonsoy",
        "Mingbuloq", "Norin", "Pop", "To'raqo'rg'on", "Uychi", "Uchqo'rg'on",
        "Yangiqo'rg'on", "Davlatobod"
    ],
    "Samarqand": [
        "Samarqand shahri", "Samarqand tumani", "Bulung'ur", "Ishtixon", "Jomboy",
        "Kattaqo'rg'on", "Qo'shrabot", "Narpay", "Nurobod", "Oqdaryo", "Payariq",
        "Pastdarg'om", "Paxtachi", "Toyloq", "Urgut"
    ],
    "Buxoro": [
        "Buxoro shahri", "Buxoro tumani", "G'ijduvon", "Jondor", "Kogon", "Olot",
        "Peshku", "Qorako'l", "Qorovulbozor", "Romitan", "Shofirkon", "Vobkent"
    ],
    "Navoiy": [
        "Navoiy shahri", "Zarafshon", "Karmana", "Konimex", "Navbahor", "Nurota",
        "Qiziltepa", "Tomdi", "Uchquduq", "Xatirchi"
    ],
    "Qashqadaryo": [
        "Qarshi shahri", "Shahrisabz", "G'uzor", "Qamashi", "Qarshi tumani", "Kasbi",
        "Kitob", "Koson", "Mirishkor", "Muborak", "Nishon", "Chiroqchi",
        "Dehqonobod", "Yakkabog'", "Ko'kdala"
    ],
    "Surxondaryo": [
        "Termiz shahri", "Termiz tumani", "Angor", "Boysun", "Denov", "Jarqo'rg'on",
        "Muzrabot", "Oltinsoy", "Qiziriq", "Qumqo'rg'on", "Sariosiyo", "Sherobod",
        "Sho'rchi", "Uzun", "Bandixon"
    ],
    "Jizzax": [
        "Jizzax shahri", "Arnasoy", "Baxmal", "Do'stlik", "Forish", "G'allaorol",
        "Sharof Rashidov", "Yangiobod", "Zafarobod", "Zarbdor", "Mirzacho'l",
        "Paxtakor", "Zomin"
    ],
    "Sirdaryo": [
        "Guliston shahri", "Guliston tumani", "Boyovut", "Mirzaobod", "Oqoltin",
        "Sardoba", "Sayxunobod", "Sirdaryo tumani", "Xovos", "Yangiyer"
    ],
    "Xorazm": [
        "Urganch shahri", "Urganch tumani", "Xiva", "Bog'ot", "Gurlan", "Hazorasp",
        "Xonqa", "Qo'shko'pir", "Shovot", "Yangiariq", "Yangibozor"
    ],
    "Qoraqalpog'iston": [
        "Nukus shahri", "Nukus tumani", "Amudaryo", "Beruniy", "Chimboy", "Ellikqal'a",
        "Kegeyli", "Mo'ynoq", "Qanliko'l", "Qorao'zak", "Qo'ng'irot", "Shumanay",
        "Taxtako'pir", "To'rtko'l", "Xo'jayli"
    ],
}

# Farg'ona vodiysi — naval (kg hisobida) mahsulotlar faqat shu hududlarga yetkaziladi
VALLEY_REGIONS = ["Andijon", "Farg'ona", "Namangan"]


def _normalize_tuman_text(text):
    return (text or "").lower().replace("'", "").replace("’", "").replace("`", "")


def detect_tuman(region, text):
    """Erkin matn ichidan (masalan fermerning yozgan manzilidan) shu viloyatga tegishli
    tuman nomini avtomatik aniqlashga harakat qiladi — aniq mos kelmasa, imlo xatolariga
    chidamli bo'lish uchun taxminiy (fuzzy) moslikni ham sinaydi. Topilsa, tuman nomini qaytaradi."""
    if not region or not text or region not in TUMANLAR:
        return None
    norm_text = _normalize_tuman_text(text)
    norm_map = {_normalize_tuman_text(t): t for t in TUMANLAR[region]}

    for norm_t, orig in norm_map.items():
        if norm_t in norm_text:
            return orig

    for word in norm_text.split():
        if len(word) < 4:
            continue
        matches = difflib.get_close_matches(word, norm_map.keys(), n=1, cutoff=0.72)
        if matches:
            return norm_map[matches[0]]
    return None


def get_neighbor_tumans(region, tuman):
    """Rasmiy qo'shnichilik ma'lumoti bo'lmagani uchun, 'qo'shni tumanlar' sifatida
    shu viloyatdagi barcha tumanlar ishlatiladi (amalda ular geografik yaqin)."""
    return TUMANLAR.get(region, [])


def build_viloyat_picker_keyboard():
    """Qaysi viloyatning tumanlarini ko'rishni tanlash uchun (bitta-bittalab navigatsiya)"""
    buttons = [[InlineKeyboardButton(r, callback_data=f"pick_viloyat:{idx}")] for idx, r in enumerate(REGIONS)]
    buttons.append([InlineKeyboardButton("✅ Tanlashni yakunlash", callback_data="regions_done")])
    buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="regions_cancel")])
    return InlineKeyboardMarkup(buttons)


def build_tuman_toggle_keyboard(viloyat, selected):
    """Berilgan viloyatning tumanlarini ko'p tanlovli ro'yxatda ko'rsatadi — tanlanganlari ✅ bilan"""
    tumanlar = TUMANLAR.get(viloyat, [])
    buttons = []
    for idx, t in enumerate(tumanlar):
        key = f"{viloyat}|{t}"
        mark = "✅ " if key in selected else "⬜ "
        buttons.append([InlineKeyboardButton(f"{mark}{t}", callback_data=f"toggle_tuman:{idx}")])
    buttons.append([InlineKeyboardButton("➕ Yana boshqa viloyatdan qo'shish", callback_data="add_more_viloyat")])
    buttons.append([InlineKeyboardButton("✅ Tayyor", callback_data="regions_done")])
    buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="regions_cancel")])
    return InlineKeyboardMarkup(buttons)

# Referal tizimi — do'st taklif qilinganda kuzatiladi, lekin endi avtomatik chegirma berilmaydi


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📢 E'lon berish")],
            [KeyboardButton("🌾 Fermerlar ulgurji (naval)")],
            [KeyboardButton("🚛 Mashinada sotiladi")],
            [KeyboardButton("📦 Qopli silos")],
            [KeyboardButton("📝 Ro'yxatdan o'tish")],
            [KeyboardButton("📊 Mening jadvalim")],
            [KeyboardButton("☎️ Aloqa"), KeyboardButton("🎁 Do'stni taklif qilish")],
            [KeyboardButton("🌱 Urug'lar"), KeyboardButton("💊 Vetapteka")],
            [KeyboardButton("🧪 Mineral o'g'itlar"), KeyboardButton("🚜 Kombaynlar")],
        ],
        resize_keyboard=True
    )


def registration_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🌾 Fermer va dehqonlar")],
            [KeyboardButton("🚚 Haydovchilar")],
            [KeyboardButton("📦 Qopli sotuvchilar")],
            [KeyboardButton("🚜 Kombayn egalari")],
            [KeyboardButton("⬅️ Bosh menyu")],
        ],
        resize_keyboard=True
    )


def combine_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🔍 Kombaynlarni ko'rish")],
            [KeyboardButton("🌾 Silos manbalarini ko'rish")],
            [KeyboardButton("⬅️ Bosh menyu")],
        ],
        resize_keyboard=True
    )


def combine_owner_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Texnika qo'shish")],
            [KeyboardButton("📋 Mening texnikam")],
            [KeyboardButton("🌾 Silos joyi e'lon qilish")],
            [KeyboardButton("📋 Mening silos elonlarim")],
            [KeyboardButton("⬅️ Bosh menyu")],
        ],
        resize_keyboard=True
    )


def vetapteka_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💉 Preparatlar")],
            [KeyboardButton("🌿 Biostimulyatorlar")],
            [KeyboardButton("⬅️ Bosh menyu")],
        ],
        resize_keyboard=True
    )


def driver_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📦 Yangi yuklar")],
            [KeyboardButton("📋 Mening e'lonlarim")],
            [KeyboardButton("🚛 Mashinada sotish e'lonim")],
            [KeyboardButton("📋 Mening savdo elonlarim")],
            [KeyboardButton("⬅️ Bosh menyu")],
        ],
        resize_keyboard=True
    )


def seller_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Mahsulot qo'shish")],
            [KeyboardButton("📦 Mening mahsulotlarim")],
            [KeyboardButton("📋 Menga tushgan buyurtmalar")],
            [KeyboardButton("⚖️ Miqdor kiritish")],
            [KeyboardButton("📊 Mening jadvalim")],
            [KeyboardButton("➕ Jadvalga yozish")],
            [KeyboardButton("✅ Pul oldim (belgilash)")],
            [KeyboardButton("⬅️ Bosh menyu")],
        ],
        resize_keyboard=True
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup([["❌ Bekor qilish"]], resize_keyboard=True)


def yes_no_keyboard():
    return ReplyKeyboardMarkup([["✅ Ha"], ["❌ Yo'q"]], resize_keyboard=True)


def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Raqamni yuborish", request_contact=True)], ["❌ Bekor qilish"]],
        resize_keyboard=True
    )


def regions_keyboard():
    buttons = [[r] for r in REGIONS]
    buttons.append(["❌ Bekor qilish"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def valley_regions_keyboard():
    buttons = [[r] for r in VALLEY_REGIONS]
    buttons.append(["❌ Bekor qilish"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def package_type_keyboard():
    return ReplyKeyboardMarkup(
        [["📦 Qopli (dona hisobida)"], ["🌾 Naval (kg hisobida)"], ["❌ Bekor qilish"]],
        resize_keyboard=True
    )


# ----------------- Asosiy buyruqlar -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Referal orqali kirganini tekshirish: /start <taklif_qilgan_id>
    existing_user = db.get_user(user.id)
    referred_by = None
    if not existing_user and context.args:
        try:
            ref_id = int(context.args[0])
            if ref_id != user.id:
                referred_by = ref_id
        except ValueError:
            pass

    is_new = existing_user is None
    db.get_or_create_user(user.id, referred_by)

    if is_new and referred_by:
        try:
            await context.bot.send_message(
                chat_id=referred_by,
                text=f"🎉 {user.first_name} sizning havolangiz orqali botga qo'shildi!"
            )
        except Exception as e:
            logger.error(f"Referal egasiga xabar yuborishda xatolik: {e}")

    text = (
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "Yem-xashak yetkazib berish botiga xush kelibsiz.\n"
        "Bu yerdan silos, somon va beda buyurtma qilishingiz mumkin — "
        "biz O'zbekiston bo'ylab yetkazib beramiz.\n\n"
        "Quyidagi menyudan tanlang 👇"
    )

    # Agar allaqachon rolga ega bo'lsa (fermer/sotuvchi, haydovchi, kombayn egasi) — darhol o'z paneliga tushiradi
    seller = db.get_seller_by_telegram_id(user.id)
    driver = db.get_driver_by_telegram_id(user.id)
    combine_owner = db.get_combine_owner_by_telegram_id(user.id)

    if seller:
        text += "\n\n📊 Siz fermer/sotuvchi sifatida ro'yxatdan o'tgansiz — pastdagi panelingiz ochiq."
        reply_markup = seller_menu_keyboard()
    elif driver:
        text += "\n\n🚚 Siz haydovchi sifatida ro'yxatdan o'tgansiz — pastdagi panelingiz ochiq."
        reply_markup = driver_menu_keyboard()
    elif combine_owner:
        text += "\n\n🚜 Siz kombayn egasi sifatida ro'yxatdan o'tgansiz — pastdagi panelingiz ochiq."
        reply_markup = combine_owner_menu_keyboard()
    else:
        reply_markup = main_menu_keyboard()

    await update.message.reply_text(text, reply_markup=reply_markup)



async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = db.get_active_products()
    if not products:
        await update.message.reply_text("Hozircha mahsulotlar mavjud emas.")
        return
    text = "📦 <b>Mavjud mahsulotlar:</b>\n\n"
    for _id, name, unit, price in products:
        text += f"• {name} — {price:,} so'm / {unit}\n"
    text = text.replace(",", " ")
    await update.message.reply_text(text, parse_mode="HTML")


# ----------------- Katalog: Urug'lar, Vetapteka, Mineral o'g'itlar -----------------

CATALOG_LABELS = {
    "uruglar": "🌱 Urug'lar",
    "preparat": "💉 Preparatlar",
    "biostimulyator": "🌿 Biostimulyatorlar",
    "ogit": "🧪 Mineral o'g'itlar",
}

CATALOG_ICONS = {
    "uruglar": "🌱",
    "preparat": "💉",
    "biostimulyator": "🌿",
    "ogit": "🧪",
}


async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    items = db.get_catalog_items(category)
    label = CATALOG_LABELS.get(category, category)
    if not items:
        await update.message.reply_text(f"{label} ro'yxati hozircha bo'sh.")
        return

    text = f"{label}:\n\n"
    for _id, name, company, description, price, unit in items:
        line = f"• <b>{name}</b>"
        if company:
            line += f" ({company})"
        if price:
            line += f" — {price:,} so'm/{unit}".replace(",", " ")
        if description:
            line += f"\n   {description}"
        text += line + "\n\n"

    text += "🛒 Buyurtma qilish uchun quyidagi tugmani bosing:"

    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i+3500], parse_mode="HTML")

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Buyurtma berish", callback_data="catalog_order_start")]])
    await update.message.reply_text("Buyurtma berish uchun bosing:", reply_markup=kb)


async def show_seeds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_catalog(update, context, "uruglar")


async def vetapteka_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💊 Vetapteka bo'limi — kerakli ro'yxatni tanlang:",
        reply_markup=vetapteka_menu_keyboard()
    )


async def show_preparats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_catalog(update, context, "preparat")


async def show_biostimulyators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_catalog(update, context, "biostimulyator")


async def show_fertilizers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_catalog(update, context, "ogit")


# ----------------- Admin: katalogga element qo'shish -----------------

async def catalog_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return ConversationHandler.END

    buttons = [[v] for v in CATALOG_LABELS.values()]
    buttons.append(["❌ Bekor qilish"])
    await update.message.reply_text(
        "Qaysi bo'limga element qo'shmoqchisiz?",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return CAT_CATEGORY


async def catalog_choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    category = next((k for k, v in CATALOG_LABELS.items() if v == text), None)
    if not category:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return CAT_CATEGORY

    context.user_data["cat_item"] = {"category": category}
    await update.message.reply_text(
        "Nomini kiriting (masalan: Pioneer P0216, yoki mahsulot nomi):",
        reply_markup=cancel_keyboard()
    )
    return CAT_NAME


async def catalog_enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_item"]["name"] = update.message.text
    await update.message.reply_text("Firma/ishlab chiqaruvchi nomi (agar yo'q bo'lsa \"-\" yozing):")
    return CAT_COMPANY


async def catalog_enter_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["cat_item"]["company"] = None if text.strip() == "-" else text
    await update.message.reply_text(
        "Qisqa tavsif kiriting (nav xususiyati, ta'siri va h.k.; kerak bo'lmasa \"-\" yozing):"
    )
    return CAT_DESC


async def catalog_enter_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["cat_item"]["description"] = None if text.strip() == "-" else text
    await update.message.reply_text("Narxi (so'mda; noma'lum bo'lsa \"-\" yozing):")
    return CAT_PRICE


async def catalog_enter_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    price = None
    if text != "-":
        try:
            price = int(text.replace(" ", ""))
        except ValueError:
            await update.message.reply_text("Iltimos, faqat raqam kiriting yoki \"-\" yozing.")
            return CAT_PRICE

    context.user_data["cat_item"]["price"] = price

    if price is None:
        # Narx yo'q bo'lsa, buyurtma qilib bo'lmaydi — o'lchov birligini so'rashning hojati yo'q
        return await catalog_finish(update, context)

    await update.message.reply_text(
        "O'lchov birligi qanday? (masalan: dona, kg, quti, litr, paket)"
    )
    return CAT_UNIT


async def catalog_enter_unit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cat_item"]["unit"] = update.message.text.strip() or "dona"
    return await catalog_finish(update, context)


async def catalog_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = context.user_data["cat_item"]
    db.add_catalog_item(
        item["category"], item["name"], item["company"], item["description"],
        item.get("price"), item.get("unit", "dona")
    )

    label = CATALOG_LABELS.get(item["category"], item["category"])
    note = "" if item.get("price") else "\n⚠️ Narx kiritilmagani uchun bu element hozircha buyurtma qilib bo'lmaydi, faqat ma'lumot sifatida ko'rinadi."
    await update.message.reply_text(
        f"✅ Qo'shildi: {item['name']} → {label}{note}",
        reply_markup=main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = db.get_user_orders(update.effective_user.id)
    if not orders:
        await update.message.reply_text("Sizda hali buyurtmalar yo'q.")
        return
    text = "📋 <b>So'nggi buyurtmalaringiz:</b>\n\n"
    for oid, product, qty, unit, total, status, created in orders:
        text += (
            f"#{oid} — {product} ({qty} {unit})\n"
            f"Summa: {total:,} so'm | Holat: {status}\n"
            f"Sana: {created}\n\n"
        ).replace(",", " ")
    await update.message.reply_text(text, parse_mode="HTML")


async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☎️ Savol yoki takliflar uchun biz bilan bog'laning:\n"
        "Telefon: +998 XX XXX XX XX\n"
        "Ish vaqti: har kuni 08:00 - 20:00"
    )


async def referral_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_or_create_user(user.id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user.id}"
    referral_count = db.count_referrals(user.id)

    text = (
        "🎁 <b>Do'stlaringizni taklif qiling!</b>\n\n"
        f"Sizning havolangiz:\n{link}\n\n"
        "Do'stingiz shu havola orqali botga kirib ro'yxatdan o'tsin.\n\n"
        f"Siz taklif qilgan do'stlar soni: {referral_count}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ----------------- Sotuvchi ro'yxatdan o'tish -----------------

async def seller_register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = db.get_seller_by_telegram_id(update.effective_user.id)
    if existing:
        status = existing[5]
        if status != "tasdiqlangan":
            # Eski (tuzatishdan oldingi) yozuv — avtomatik tasdiqlangan holatga o'tkazamiz
            db.set_seller_status(existing[0], "tasdiqlangan")
        await update.message.reply_text(
            "Siz allaqachon ro'yxatdan o'tgansiz. Sotuvchi panelidan foydalaning.",
            reply_markup=seller_menu_keyboard()
        )
        return ConversationHandler.END

    context.user_data["is_farmer_shortcut"] = False
    await update.message.reply_text(
        "🏪 Sotuvchi sifatida ro'yxatdan o'tish.\n\n"
        "Do'kon/omborxona nomini kiriting:",
        reply_markup=cancel_keyboard()
    )
    return SELLER_NAME


async def farmer_register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = db.get_seller_by_telegram_id(update.effective_user.id)
    if existing:
        status = existing[5]
        if status != "tasdiqlangan":
            db.set_seller_status(existing[0], "tasdiqlangan")
        await update.message.reply_text(
            "Siz allaqachon ro'yxatdan o'tgansiz. Panelingizdan foydalaning.",
            reply_markup=seller_menu_keyboard()
        )
        return ConversationHandler.END

    context.user_data["is_farmer_shortcut"] = True
    await update.message.reply_text(
        "🌾 Fermer/dehqon sifatida ro'yxatdan o'tish — bor-yo'g'i 3 ta savol!\n\n"
        "Ism-familiyangizni (yoki ferma nomini) kiriting:",
        reply_markup=cancel_keyboard()
    )
    return SELLER_NAME


async def seller_enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["seller"] = {"shop_name": update.message.text}
    await update.message.reply_text("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
    return SELLER_PHONE


async def seller_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data["seller"]["phone"] = phone
    await update.message.reply_text(
        "Qaysi hududda (viloyatda) faoliyat yuritasiz?",
        reply_markup=regions_keyboard()
    )
    return SELLER_REGION


async def seller_enter_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in REGIONS:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return SELLER_REGION

    context.user_data["seller"]["region"] = text

    # Fermer tezkor yo'li — yuk mashinasi savolisiz, darhol yakunlaydi
    if context.user_data.get("is_farmer_shortcut"):
        context.user_data["seller"]["vehicle_type"] = None
        context.user_data["seller"]["capacity_tons"] = None
        context.user_data["seller"]["delivers_self"] = 0
        return await finish_seller_registration(update, context)

    await update.message.reply_text(
        "🚛 Sizda yuk mashina bormi? Ulgurji (5-10 tonna) sotib, o'zingiz yetkazib bera olasizmi?",
        reply_markup=yes_no_keyboard()
    )
    return SELLER_HAS_VEHICLE


async def seller_has_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "✅ Ha":
        await update.message.reply_text(
            "Mashinangiz turi qanday? (masalan: Isuzu, KAMAZ, treyler)",
            reply_markup=cancel_keyboard()
        )
        return SELLER_VEHICLE_TYPE
    elif text == "❌ Yo'q":
        context.user_data["seller"]["vehicle_type"] = None
        context.user_data["seller"]["capacity_tons"] = None
        context.user_data["seller"]["delivers_self"] = 0
        return await finish_seller_registration(update, context)
    else:
        await update.message.reply_text("Iltimos, tugmalardan birini tanlang.")
        return SELLER_HAS_VEHICLE


async def seller_vehicle_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["seller"]["vehicle_type"] = update.message.text
    await update.message.reply_text("Mashinangiz necha tonna yuk ko'tara oladi? (masalan: 10)")
    return SELLER_CAPACITY


async def seller_capacity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        capacity = float(update.message.text.replace(",", "."))
        if capacity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to'g'ri son kiriting (masalan: 10).")
        return SELLER_CAPACITY

    context.user_data["seller"]["capacity_tons"] = capacity
    context.user_data["seller"]["delivers_self"] = 1
    return await finish_seller_registration(update, context)


async def finish_seller_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = context.user_data["seller"]
    user = update.effective_user
    seller_id = db.register_seller(
        user.id, seller["shop_name"], seller["phone"], seller["region"],
        vehicle_type=seller.get("vehicle_type"),
        capacity_tons=seller.get("capacity_tons"),
        delivers_self=seller.get("delivers_self", 0),
    )

    await update.message.reply_text(
        "✅ Ro'yxatdan muvaffaqiyatli o'tdingiz! Endi mahsulot qo'sha olasiz.",
        reply_markup=seller_menu_keyboard()
    )

    if ADMIN_CHAT_ID:
        vehicle_line = (
            f"Mashina: {seller['vehicle_type']} ({seller['capacity_tons']} tonna)\n"
            if seller.get("delivers_self") else "Yuk mashinasi: yo'q\n"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"🏪 <b>Yangi sotuvchi ro'yxatdan o'tdi (avtomatik tasdiqlangan)</b>\n\n"
                    f"Do'kon: {seller['shop_name']}\n"
                    f"Telefon: {seller['phone']}\n"
                    f"Hudud: {seller['region']}\n"
                    f"{vehicle_line}"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Adminga sotuvchi xabarini yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def handle_seller_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, seller_id = query.data.split(":")
    seller_id = int(seller_id)
    seller = db.get_seller_by_id(seller_id)
    if not seller:
        await query.edit_message_text("Sotuvchi topilmadi.")
        return

    telegram_id = seller[1]
    shop_name = seller[2]

    if action == "approve_seller":
        db.set_seller_status(seller_id, "tasdiqlangan")
        await query.edit_message_text(f"✅ Tasdiqlandi: {shop_name}")
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text="🎉 Tabriklaymiz! Sotuvchi sifatida tasdiqlandingiz.",
                reply_markup=seller_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Sotuvchiga xabar yuborishda xatolik: {e}")
    else:
        db.set_seller_status(seller_id, "rad etilgan")
        await query.edit_message_text(f"❌ Rad etildi: {shop_name}")
        try:
            await context.bot.send_message(chat_id=telegram_id, text="Afsuski, arizangiz rad etildi.")
        except Exception as e:
            logger.error(f"Sotuvchiga xabar yuborishda xatolik: {e}")


# ----------------- Sotuvchi paneli -----------------

async def seller_panel_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sotuvchi ekanligini tekshiradi; eski (kutilmoqda) holatdagilarni avtomatik tasdiqlaydi"""
    seller = db.get_seller_by_telegram_id(update.effective_user.id)
    if not seller:
        await update.message.reply_text(
            "Bu bo'lim faqat ro'yxatdan o'tgan sotuvchilar uchun. Avval \"📝 Ro'yxatdan o'tish\" bo'limidan "
            "\"📦 Qopli sotuvchilar\" yoki \"🌾 Fermer va dehqonlar\" tugmasini bosing.",
            reply_markup=main_menu_keyboard()
        )
        return None
    if seller[5] != "tasdiqlangan":
        db.set_seller_status(seller[0], "tasdiqlangan")
        seller = db.get_seller_by_telegram_id(update.effective_user.id)
    return seller


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bosh menyu:", reply_markup=main_menu_keyboard())


async def registration_menu_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Ro'yxatdan o'tish — qaysi bo'lim sifatida ro'yxatdan o'tmoqchisiz?",
        reply_markup=registration_menu_keyboard()
    )


async def elon_berish_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'📢 E'lon berish' bosilganda — foydalanuvchining roliga qarab (fermer/sotuvchi, haydovchi,
    kombayn egasi) mos e'lon berish tugmalarini ko'rsatadi. Tugma bosilgach, mavjud
    ConversationHandler'lar (o'zlarining aniq matn entry_point'lari orqali) avtomatik ishga tushadi."""
    user_id = update.effective_user.id
    seller = db.get_seller_by_telegram_id(user_id)
    driver = db.get_driver_by_telegram_id(user_id)
    combine_owner = db.get_combine_owner_by_telegram_id(user_id)

    buttons = []
    if seller:
        buttons.append([KeyboardButton("➕ Mahsulot qo'shish")])
    if driver:
        buttons.append([KeyboardButton("🚛 Mashinada sotish e'lonim")])
    if combine_owner:
        buttons.append([KeyboardButton("➕ Texnika qo'shish")])
        buttons.append([KeyboardButton("🌾 Silos joyi e'lon qilish")])

    if not buttons:
        await update.message.reply_text(
            "E'lon berish uchun avval ro'yxatdan o'tishingiz kerak — "
            "\"📝 Ro'yxatdan o'tish\" bo'limidan mos turingizni tanlang.",
            reply_markup=registration_menu_keyboard()
        )
        return

    buttons.append([KeyboardButton("⬅️ Bosh menyu")])
    await update.message.reply_text(
        "📢 Qanday e'lon bermoqchisiz? Tugmalardan birini tanlang:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


async def seller_add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = await seller_panel_guard(update, context)
    if not seller:
        return ConversationHandler.END
    context.user_data["seller_id"] = seller[0]
    context.user_data["seller_delivers_self"] = seller[8]  # 0 = fermer (yer egasi), 1 = o'z mashinasi bor
    context.user_data["seller_region"] = seller[4]

    if not seller[8]:
        # Fermer/yer egasi — eng qisqa yo'l: avval rasm, keyin hammasi bitta xabarda
        context.user_data["sp"] = {"name": "Silos", "package_type": "gektar", "unit": "gektar"}
        await update.message.reply_text(
            "🌾 Yer/silos e'loni beramiz — atigi 2 qadam!\n\n"
            "1) 📷 Avval rasmni yuboring (yer yoki silos rasmi):",
            reply_markup=cancel_keyboard()
        )
        return SP_PHOTO

    await update.message.reply_text(
        "Mahsulot nomini kiriting (masalan: Silos):",
        reply_markup=cancel_keyboard()
    )
    return SP_NAME


def parse_free_listing_text(text):
    """'10 gektar 500 som Farg'ona Qo'shtepa tel 90 582 7775' kabi erkin xabarni tahlil qiladi.
    Gektar/kg/dona miqdorini, narxini, telefonni va qolgan qismini manzil sifatida ajratadi."""
    result = {"quantity": None, "unit": None, "price": None, "phone": None, "address": None}
    working = text

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*gektar", working, re.IGNORECASE)
    if m:
        result["quantity"] = float(m.group(1).replace(",", "."))
        result["unit"] = "gektar"
        working = working[:m.start()] + working[m.end():]
    else:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*kg\b", working, re.IGNORECASE)
        if m:
            result["quantity"] = float(m.group(1).replace(",", "."))
            result["unit"] = "kg"
            working = working[:m.start()] + working[m.end():]
        else:
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*dona", working, re.IGNORECASE)
            if m:
                result["quantity"] = float(m.group(1).replace(",", "."))
                result["unit"] = "dona"
                working = working[:m.start()] + working[m.end():]

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*so\S*", working, re.IGNORECASE)
    if m:
        result["price"] = int(float(m.group(1).replace(",", ".")))
        working = working[:m.start()] + working[m.end():]

    m = re.search(r"tel\S*\s*([\d\s\-\+]{7,})", working, re.IGNORECASE)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        if digits:
            if len(digits) == 9:
                digits = "998" + digits
            result["phone"] = "+" + digits
        working = working[:m.start()] + working[m.end():]

    result["address"] = " ".join(working.split())
    return result


async def sp_enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sp"] = {"name": update.message.text}

    if not context.user_data.get("seller_delivers_self"):
        # Yuk mashinasi yo'q — bu fermer/dehqon, yerini gektar hisobida e'lon qiladi
        context.user_data["sp"]["package_type"] = "gektar"
        context.user_data["sp"]["unit"] = "gektar"
        await update.message.reply_text(
            "🌾 Siz yer egasi sifatida ro'yxatdagansiz — mahsulot **gektar** hisobida e'lon qilinadi "
            "(hali o'rilmagan maydon, haydovchi o'zi o'rib olib ketadi).\n\n"
            "1 kg silos narxini va necha gektar joyingiz borligini BITTA xabarda, alohida qatorlarda "
            "kiriting:\n\nMasalan:\n500\n8",
            reply_markup=cancel_keyboard()
        )
        return SP_PRICE

    await update.message.reply_text(
        "Mahsulot turi qanday?\n\n"
        "📦 Qopli — dona hisobida sotiladi, butun respublika bo'ylab yetkaziladi\n"
        "🌾 Naval — kilogramm hisobida (sochilma), faqat Farg'ona vodiysi bo'ylab yetkaziladi",
        reply_markup=package_type_keyboard()
    )
    return SP_TYPE


async def sp_choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📦 Qopli (dona hisobida)":
        context.user_data["sp"]["package_type"] = "qopli"
        context.user_data["sp"]["unit"] = "dona"
    elif text == "🌾 Naval (kg hisobida)":
        context.user_data["sp"]["package_type"] = "naval"
        context.user_data["sp"]["unit"] = "kg"
    else:
        await update.message.reply_text("Iltimos, tugmalardan birini tanlang.")
        return SP_TYPE

    unit = context.user_data["sp"]["unit"]
    await update.message.reply_text(
        f"Narxini va mavjud miqdorni ({unit} hisobida) BITTA xabarda, alohida qatorlarda kiriting:\n\n"
        "Masalan:\n350000\n20",
        reply_markup=cancel_keyboard()
    )
    return SP_PRICE


async def sp_enter_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [l.strip() for l in update.message.text.split("\n") if l.strip()]
    if len(lines) != 2:
        await update.message.reply_text(
            "Iltimos, aynan 2 qatorda yozing: narx, keyin miqdor.\nMasalan:\n350000\n20"
        )
        return SP_PRICE
    try:
        price = int(lines[0].replace(" ", ""))
        qty = float(lines[1].replace(",", "."))
        if price <= 0 or qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Raqamlar noto'g'ri. Iltimos, qaytadan urinib ko'ring.\nMasalan:\n350000\n20"
        )
        return SP_PRICE
    context.user_data["sp"]["price"] = price
    context.user_data["sp"]["quantity"] = qty
    await update.message.reply_text(
        "📷 Mahsulot/maydon rasmini yuboring (xaridor va haydovchilar ko'rishi uchun).\n"
        "Rasm yubormoqchi bo'lmasangiz \"-\" deb yozing.",
        reply_markup=cancel_keyboard()
    )
    return SP_PHOTO


async def sp_enter_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file_id = None
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.strip() == "-":
        photo_file_id = None
    else:
        await update.message.reply_text("Iltimos, rasm yuboring yoki \"-\" deb yozing.")
        return SP_PHOTO

    context.user_data["sp"]["photo_file_id"] = photo_file_id

    if "price" not in context.user_data["sp"]:
        # Fermer/yer egasi uchun soddalashtirilgan yo'l — endi hammasi bitta xabarda
        await update.message.reply_text(
            "2) ✍️ Endi hammasini BITTA xabarda yozing: necha gektar, narxi, manzilingiz, telefon raqamingiz.\n\n"
            "Masalan:\n"
            "10 gektar 500 som Farg'ona Qo'shtepa tel 90 582 7775"
        )
        return SP_FREE_TEXT

    await update.message.reply_text(
        "Aniq manzilingizni va sifat haqida qisqa izohni BITTA xabarda, alohida qatorlarda kiriting "
        "(manzil — haydovchi yukni olib ketishi uchun kerak):\n\n"
        "Masalan:\n"
        "Uychi tumani\n"
        "Quruq, yangi o'rilgan\n\n"
        "(Izoh yozmasangiz, faqat manzilni kiriting.)"
    )
    return SP_ADDRESS


async def sp_free_text_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parsed = parse_free_listing_text(update.message.text)
    if not parsed["quantity"] or not parsed["price"]:
        await update.message.reply_text(
            "Tushunolmadim — iltimos, gektar va narxni ham kiriting.\n\n"
            "Masalan:\n10 gektar 500 som Farg'ona Qo'shtepa tel 90 582 7775"
        )
        return SP_FREE_TEXT

    sp = context.user_data["sp"]
    sp["quantity"] = parsed["quantity"]
    sp["price"] = parsed["price"]
    sp["address"] = parsed["address"] or context.user_data.get("seller_region", "")
    sp["description"] = None

    if parsed["phone"]:
        db.update_seller_phone(context.user_data["seller_id"], parsed["phone"])

    await sp_finalize(context, update.effective_user.id, update.effective_chat.id)
    return ConversationHandler.END



async def sp_enter_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [l.strip() for l in update.message.text.split("\n") if l.strip()]
    address = lines[0] if lines else update.message.text.strip()
    description = "\n".join(lines[1:]) if len(lines) > 1 else None
    context.user_data["sp"]["address"] = address
    context.user_data["sp"]["description"] = description
    location_kb = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📍 Joylashuvni yuborish", request_location=True)],
            ["🗺 Hududlarni o'zim tanlayman"],
            ["⏭ O'tkazib yuborish"],
        ],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "Xabar qayerdagi haydovchilarga borishini belgilang:\n\n"
        "📍 Joylashuvni yuborish — faqat 25-30 km atrofdagilarga\n"
        "🗺 Hududlarni o'zim tanlayman — o'zingiz istagan viloyatlarga\n"
        "⏭ O'tkazib yuborish — avtomatik (turi bo'yicha)",
        reply_markup=location_kb
    )
    return SP_LOCATION


async def sp_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    has_location = update.message.location is not None
    is_skip = update.message.text == "⏭ O'tkazib yuborish"
    is_region_select = update.message.text == "🗺 Hududlarni o'zim tanlayman"

    if is_region_select:
        context.user_data["posting_flow"] = "sp"
        context.user_data["selected_tumans"] = set()
        await update.message.reply_text(
            "Qo'shni tumanlarni tanlaysiz — avval viloyatni tanlang, so'ng o'sha viloyatning "
            "tumanlarini belgilaysiz. Kerak bo'lsa, boshqa viloyatdan ham tuman qo'shishingiz mumkin.",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(
            "Qaysi viloyat?", reply_markup=build_viloyat_picker_keyboard()
        )
        return SP_REGIONS

    if not has_location and not is_skip:
        await update.message.reply_text("Iltimos, variantlardan birini tanlang.")
        return SP_LOCATION

    latitude = update.message.location.latitude if has_location else None
    longitude = update.message.location.longitude if has_location else None
    await sp_finalize(context, update.effective_user.id, update.effective_chat.id, latitude=latitude, longitude=longitude)
    context.user_data.clear()
    return ConversationHandler.END


async def sp_finalize(context: ContextTypes.DEFAULT_TYPE, user_telegram_id, chat_id,
                       latitude=None, longitude=None, target_regions=None, target_tumans=None):
    sp = context.user_data["sp"]
    address = sp["address"]

    sp_id = db.add_seller_product(
        context.user_data["seller_id"], sp["name"], sp["unit"], sp["price"], sp["quantity"],
        address, package_type=sp.get("package_type", "naval"), photo_file_id=sp.get("photo_file_id"),
        latitude=latitude, longitude=longitude, description=sp.get("description")
    )

    type_labels = {
        "qopli": "📦 Qopli (respublika bo'ylab)",
        "naval": "🌾 Naval (faqat vodiy bo'ylab)",
        "gektar": "🌾 Gektar (haydovchi olib ketadi)",
    }
    type_label = type_labels.get(sp.get("package_type"), sp.get("package_type"))
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ Qo'shildi: {sp['name']} — {fmt_money(sp['quantity'])} {sp['unit']}, narxi {fmt_money(sp['price'])} so'm\n"
            f"Turi: {type_label}"
        ),
        reply_markup=seller_menu_keyboard()
    )

    # Kim xabar olishini aniqlash: 1) ozi tanlagan tumanlar, 2) ozi tanlagan viloyatlar, 3) koordinata,
    # 4) manzildan avtomatik aniqlangan tuman (+ shu viloyatdagi qoshni tumanlar), 5) faqat oz viloyati
    seller = db.get_seller_by_telegram_id(user_telegram_id)
    shop_name = seller[2] if seller else "?"
    region = sp.get("region") or (seller[4] if seller else "")
    ptype = sp.get("package_type")
    if target_tumans:
        driver_ids = db.get_drivers_by_tumans(target_tumans)
    elif target_regions:
        driver_ids = db.get_drivers_by_regions(target_regions)
    elif latitude is not None and longitude is not None:
        driver_ids = db.get_drivers_near(latitude, longitude, max_km=30)
    elif ptype == "qopli":
        driver_ids = db.get_all_approved_drivers()
    elif ptype in ("naval", "gektar"):
        detected_tuman = detect_tuman(region, address)
        if detected_tuman:
            neighbor_tumans = get_neighbor_tumans(region, detected_tuman)
            driver_ids = db.get_drivers_by_tumans(neighbor_tumans)
        elif region:
            driver_ids = db.get_drivers_by_regions([region])
        else:
            driver_ids = db.get_drivers_by_regions(VALLEY_REGIONS)
    else:
        driver_ids = db.get_drivers_by_regions([region]) if region else db.get_all_approved_drivers()

    caption = (
        f"🆕 <b>Yangi yuk e'lon qilindi!</b>\n\n"
        f"<b>{sp['name']}</b> — {fmt_money(sp['quantity'])} {sp['unit']}\n"
        f"Narxi: {fmt_money(sp['price'])} so'm/{sp['unit']}\n"
        f"Turi: {type_label}\n"
        f"Sotuvchi: {shop_name}\n"
        f"Hudud: {region}\n"
        f"Manzil: {address}\n\n"
        "\"📦 Yangi yuklar\" bo'limidan ko'rib, olishingiz mumkin."
    )
    photo_id = sp.get("photo_file_id")
    for drv_tg_id in driver_ids:
        try:
            if photo_id:
                await context.bot.send_photo(chat_id=drv_tg_id, photo=photo_id, caption=caption, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=drv_tg_id, text=caption, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Haydovchi {drv_tg_id} ga yangi elon xabarini yuborishda xatolik: {e}")

    context.user_data.clear()


async def handle_viloyat_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, idx = query.data.split(":")
    idx = int(idx)
    viloyat = REGIONS[idx]
    context.user_data["current_viloyat"] = viloyat
    selected = context.user_data.get("selected_tumans", set())

    flow = context.user_data.get("posting_flow")
    next_state = SP_TUMANS if flow == "sp" else CS_TUMANS

    try:
        await query.edit_message_text(
            f"{viloyat} — tumanlarni tanlang:",
            reply_markup=build_tuman_toggle_keyboard(viloyat, selected)
        )
    except Exception:
        pass
    return next_state


async def handle_tuman_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, idx = query.data.split(":")
    idx = int(idx)
    viloyat = context.user_data.get("current_viloyat")
    tumanlar = TUMANLAR.get(viloyat, [])
    if idx >= len(tumanlar):
        return
    tuman = tumanlar[idx]
    key = f"{viloyat}|{tuman}"

    selected = context.user_data.get("selected_tumans", set())
    if key in selected:
        selected.discard(key)
    else:
        selected.add(key)
    context.user_data["selected_tumans"] = selected

    try:
        await query.edit_message_reply_markup(reply_markup=build_tuman_toggle_keyboard(viloyat, selected))
    except Exception:
        pass


async def handle_add_more_viloyat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    flow = context.user_data.get("posting_flow")
    prev_state = SP_REGIONS if flow == "sp" else CS_REGIONS
    try:
        await query.edit_message_text(
            "Yana qaysi viloyatdan tuman qo'shmoqchisiz?",
            reply_markup=build_viloyat_picker_keyboard()
        )
    except Exception:
        pass
    return prev_state


async def handle_regions_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.message.reply_text("Bekor qilindi.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def handle_regions_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected = context.user_data.get("selected_tumans", set())
    if not selected:
        await query.answer("Kamida bitta tumanni tanlang.", show_alert=True)
        flow = context.user_data.get("posting_flow")
        return SP_REGIONS if flow == "sp" else CS_REGIONS
    await query.answer()

    flow = context.user_data.get("posting_flow")
    # "viloyat|tuman" kalitlaridan faqat tuman nomlarini ajratib olamiz
    target_tumans = [key.split("|", 1)[1] for key in selected]
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if flow == "sp":
        await sp_finalize(context, user_id, chat_id, target_tumans=target_tumans)
    elif flow == "cs":
        await cs_finalize(context, user_id, chat_id, target_tumans=target_tumans)
    else:
        context.user_data.clear()
    return ConversationHandler.END


async def seller_my_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = await seller_panel_guard(update, context)
    if not seller:
        return
    products = db.get_seller_products(seller[0])
    if not products:
        await update.message.reply_text("Sizda hali mahsulot yo'q. \"➕ Mahsulot qo'shish\" orqali qo'shing.")
        return
    await update.message.reply_text("📦 <b>Sizning mahsulotlaringiz:</b>", parse_mode="HTML")
    type_notes = {"qopli": "📦 qopli", "naval": "🌾 naval", "gektar": "🌾 gektar (yer)"}
    for _id, name, unit, price, qty, address, claimed, package_type, photo_id in products:
        status_note = " (🚛 haydovchi oldi)" if claimed else (" (o'chirilgan)" if qty <= 0 else "")
        type_note = type_notes.get(package_type, package_type)
        photo_note = " 📷" if photo_id else ""
        price_unit = "kg" if package_type == "gektar" else unit
        text = f"• {name} — {qty} {unit} mavjud, narxi {fmt_money(price)} so'm/{price_unit} | {type_note}{status_note}{photo_note}"
        await update.message.reply_text(text)


async def seller_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = await seller_panel_guard(update, context)
    if not seller:
        return
    orders = db.get_seller_orders(seller[0])
    if not orders:
        await update.message.reply_text("Sizga hali buyurtma tushmagan.")
        return
    text = "📋 <b>Sizga tushgan buyurtmalar:</b>\n\n"
    for oid, name, phone, product, qty, unit, total, region, address, status, created in orders:
        text += (
            f"#{oid} | {status} | {created}\n"
            f"{name} | {phone}\n"
            f"{product} — {qty} {unit} — {fmt_money(total)} so'm\n"
            f"{region}, {address}\n\n"
        )
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i+3500], parse_mode="HTML")


async def seller_transaction_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = await seller_panel_guard(update, context)
    if not seller:
        return

    farmer_name, rows = db.get_farmer_transactions_flat(seller[0])

    lines = [
        f"📊 <b>{farmer_name}</b>",
        "🟡 = 3-5 kun to'lanmagan | 🔴 = 5 kundan ko'p to'lanmagan (qora ro'yxat)",
    ]

    if not rows:
        lines.append("")
        lines.append("Hali hech kim yukingizni olmagan — birinchi haydovchi yukni olgach, shu yerda ko'rinadi.")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    lines.append("")
    lines.append("<pre>№  Mashina      Tel           Narx/kg    Kg      Summa        Toldi</pre>")

    total_kg = 0.0
    total_summa = 0
    total_paid = 0
    blacklist_red = []
    blacklist_yellow = []
    flagged_vehicles = set()

    for idx, r in enumerate(rows, start=1):
        unit, quantity, price = r["unit"], r["quantity"], r["price"]
        payment, confirmed, created_at = r["payment"], r["confirmed"], r["created_at"]
        vehicle_number, phone, driver_id = r["vehicle_number"], r["phone"], r["driver_id"]

        is_tonna = unit == "tonna"
        kg = quantity * 1000 if is_tonna else quantity
        price_per_kg_base = price / 1000 if is_tonna else price
        summa = payment if payment is not None else round(price_per_kg_base * kg)
        price_per_kg = round(summa / kg) if kg else 0

        total_kg += kg
        total_summa += summa
        pay_mark = "✅" if confirmed else "❌"
        if confirmed:
            total_paid += summa

        veh_key = (vehicle_number or "—").strip().upper()

        debt_level = None
        debt_days = None
        if not confirmed and created_at:
            try:
                created_dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M")
                days_passed = (datetime.now() - created_dt).days
                if days_passed >= 5:
                    debt_level, debt_days = "qizil", days_passed
                elif days_passed >= 3:
                    debt_level, debt_days = "sariq", days_passed
            except ValueError:
                pass

        # Boshqa fermerlar oldida ham qarzi bormi — FAQAT shu viloyat ichida, va FAQAT botdan
        # ro'yxatdan o'tgan haydovchilar uchun tekshiriladi (qo'lda yozilgan qatorlar uchun
        # haydovchi bot tizimida ro'yxatdan o'tmagan bo'lishi mumkin, shuning uchun bu tekshiruv o'tkazib yuboriladi)
        if driver_id:
            other_debts = db.get_driver_debts(driver_id, exclude_listing_id=r["id"], region=seller[4])
            if other_debts:
                worst = max(other_debts, key=lambda d: d["days"])
                if debt_level != "qizil" and (debt_level is None or worst["level"] == "qizil"):
                    debt_level, debt_days = worst["level"], worst["days"]

        if debt_level and veh_key not in flagged_vehicles:
            flagged_vehicles.add(veh_key)
            entry = f"🚛 {vehicle_number or '—'} ({phone or '—'}) — {debt_days} kun"
            if debt_level == "qizil":
                blacklist_red.append(entry)
            else:
                blacklist_yellow.append(entry)

        veh_mark = "🔴" if debt_level == "qizil" else ("🟡" if debt_level == "sariq" else "  ")
        row = (
            f"{idx:<3}{veh_mark}{(vehicle_number or '—'):<12}{(phone or '—'):<14}"
            f"{price_per_kg:>8,}  {kg:>6,.0f}  {summa:>10,}   {pay_mark}"
        ).replace(",", " ")
        lines.append(f"<pre>{row}</pre>")

    lines.append("")
    lines.append(
        f"<b>JAMI:</b> {total_kg:,.0f} kg | {total_summa:,} so'm "
        f"(qabul qilingan: {total_paid:,} so'm)".replace(",", " ")
    )

    if blacklist_red:
        lines.append("")
        lines.append("🔴 <b>Qora ro'yxat (5+ kun to'lanmagan):</b>\n" + "\n".join(blacklist_red))
    if blacklist_yellow:
        lines.append("")
        lines.append("🟡 <b>Diqqat (3-5 kun to'lanmagan):</b>\n" + "\n".join(blacklist_yellow))

    text = "\n".join(lines)
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i+3500], parse_mode="HTML")


# ----------------- Fermer jadvalga qo'lda qator qo'shish -----------------
# (Haydovchi elonni botdan "olib" bormasdan, to'g'ridan-to'g'ri kelib silos olganda ishlatiladi)

async def ml_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = await seller_panel_guard(update, context)
    if not seller:
        return ConversationHandler.END
    context.user_data["ml"] = {"seller_id": seller[0], "region": seller[4]}
    await update.message.reply_text(
        "➕ Haydovchi keldi — quyidagi 3 ma'lumotni BITTA xabarda, har birini yangi qatorda yozing:\n\n"
        "Mashina raqami\n"
        "Telefon raqami\n"
        "1 kg narxi (so'mda)\n\n"
        "Masalan:\n"
        "01 A 123 AA\n"
        "+998901234567\n"
        "480\n\n"
        "Bot avtomatik qora ro'yxatni tekshiradi. Kg keyinroq, tarozidan tortgandan so'ng kiritiladi.",
        reply_markup=cancel_keyboard()
    )
    return ML_VEHICLE


async def ml_enter_combined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    parts = [p.strip() for p in raw.replace(",", "\n").split("\n") if p.strip()]
    if len(parts) != 3:
        await update.message.reply_text(
            "Iltimos, aynan 3 qatorda yozing: mashina raqami, telefon raqami, 1 kg narxi.\n"
            "Masalan:\n01 A 123 AA\n+998901234567\n480"
        )
        return ML_VEHICLE

    vehicle_number, phone, price_text = parts
    try:
        price = int(price_text.replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "3-qatordagi narx noto'g'ri — faqat raqam bo'lishi kerak. Qaytadan urinib ko'ring.\n"
            "Masalan:\n01 A 123 AA\n+998901234567\n480"
        )
        return ML_VEHICLE

    ml = context.user_data["ml"]

    # Darhol qora ro'yxatni tekshiramiz — mashina raqami bo'yicha, shu viloyat ichida
    debts = db.get_vehicle_debts(vehicle_number, ml["region"])
    red_debts = [d for d in debts if d["level"] == "qizil"]
    yellow_debts = [d for d in debts if d["level"] == "sariq"]

    db.add_manual_ledger_entry(ml["seller_id"], vehicle_number, phone, price, ml["region"])

    if red_debts:
        worst = max(red_debts, key=lambda d: d["days"])
        warning = (
            f"⛔ <b>DIQQAT — QORA RO'YXAT!</b>\n"
            f"Bu mashina ({vehicle_number}) {ml['region']} viloyatida {worst['days']} kundan beri "
            f"{worst['farmer_name']}ga {worst['amount']:,} so'm qarzdor. Ehtiyot bo'ling!"
        ).replace(",", " ")
    elif yellow_debts:
        worst = max(yellow_debts, key=lambda d: d["days"])
        warning = (
            f"🟡 Diqqat: bu mashina ({vehicle_number}) {worst['days']} kundan beri "
            f"{worst['farmer_name']}ga qarzdor."
        )
    else:
        warning = "✅ Bu mashina qora ro'yxatda emas — toza."

    await update.message.reply_text(
        f"{warning}\n\n"
        "Yozildi. Endi yukni tarozi punktiga yuboring — haydovchi tortib, kilogramini telefon orqali "
        "aytgach, \"⚖️ Miqdor kiritish\" orqali kiriting.",
        parse_mode="HTML",
        reply_markup=seller_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def driver_register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = db.get_driver_by_telegram_id(update.effective_user.id)
    if existing:
        status = existing[7]
        if status != "tasdiqlangan":
            db.set_driver_status(existing[0], "tasdiqlangan")
        await update.message.reply_text(
            "Siz allaqachon ro'yxatdan o'tgansiz.",
            reply_markup=driver_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🚚 Haydovchi sifatida ro'yxatdan o'tish.\n\n"
        "Siz dehqon/fermerlardan yem-xashak yukini olib, o'z narxingiz bilan mijozlarga sotasiz.\n\n"
        "Ism-familiyangizni kiriting:",
        reply_markup=cancel_keyboard()
    )
    return DRV_NAME


async def driver_enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["driver"] = {"full_name": update.message.text}
    await update.message.reply_text("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
    return DRV_PHONE


async def driver_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data["driver"]["phone"] = phone
    await update.message.reply_text(
        "Mashinangiz turi qanday? (masalan: Isuzu, KAMAZ, Damas)",
        reply_markup=cancel_keyboard()
    )
    return DRV_VEHICLE


async def driver_enter_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["driver"]["vehicle_type"] = update.message.text
    await update.message.reply_text(
        "Mashinangiz davlat raqami qanday? (masalan: 01 A 123 AA)",
        reply_markup=cancel_keyboard()
    )
    return DRV_NUMBER


async def driver_enter_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["driver"]["vehicle_number"] = update.message.text
    await update.message.reply_text("Mashinangiz necha tonna yuk ko'tara oladi? (masalan: 8)")
    return DRV_CAPACITY


async def driver_enter_capacity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        capacity = float(update.message.text.replace(",", "."))
        if capacity <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to'g'ri son kiriting (masalan: 8).")
        return DRV_CAPACITY
    context.user_data["driver"]["capacity_tons"] = capacity
    await update.message.reply_text(
        "Qaysi hududda asosan ishlaysiz? (mijozlarga shu hududda sotasiz)",
        reply_markup=regions_keyboard()
    )
    return DRV_REGION


async def driver_enter_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in REGIONS:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return DRV_REGION

    context.user_data["driver"]["region"] = text
    tumanlar = TUMANLAR.get(text, [])
    buttons = [[t] for t in tumanlar]
    buttons.append(["⏭ O'tkazib yuborish"])
    await update.message.reply_text(
        "Qaysi tumanda (yoki shaharda) yashaysiz? Bu sizga yaqin e'lonlarni aniqroq topishga yordam beradi:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return DRV_TUMAN


async def driver_enter_tuman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    region = context.user_data["driver"]["region"]
    tumanlar = TUMANLAR.get(region, [])
    if text != "⏭ O'tkazib yuborish" and text not in tumanlar:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return DRV_TUMAN

    context.user_data["driver"]["tuman"] = None if text == "⏭ O'tkazib yuborish" else text

    location_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Joylashuvimni yuborish", request_location=True)], ["⏭ O'tkazib yuborish"]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "📍 Joylashuvingizni yuborsangiz, sizga faqat **25-30 km atrofingizdagi** yangi yuklar "
        "haqida xabar keladi (uzoqdagilar haqida xabar kelmaydi). "
        "Yubormasangiz, barcha yangi yuklar haqida xabar kelaveradi.",
        reply_markup=location_kb
    )
    return DRV_LOCATION


async def driver_enter_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    has_location = update.message.location is not None
    is_skip = update.message.text == "⏭ O'tkazib yuborish"
    if not has_location and not is_skip:
        await update.message.reply_text("📍 Joylashuvni yuboring yoki \"⏭ O'tkazib yuborish\" tugmasini bosing.")
        return DRV_LOCATION

    d = context.user_data["driver"]
    user = update.effective_user
    driver_id = db.register_driver(
        user.id, d["full_name"], d["phone"], d["vehicle_type"],
        d["vehicle_number"], d["capacity_tons"], d["region"]
    )

    if d.get("tuman"):
        db.update_driver_tuman(driver_id, d["tuman"])

    if has_location:
        db.update_driver_location(driver_id, update.message.location.latitude, update.message.location.longitude)
        loc_note = " (joylashuvingiz saqlandi — endi faqat yaqin yuklar haqida xabar olasiz)"
    else:
        loc_note = ""

    await update.message.reply_text(
        f"✅ Ro'yxatdan muvaffaqiyatli o'tdingiz!{loc_note} Endi yuklarni ko'ra olasiz.",
        reply_markup=driver_menu_keyboard()
    )

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"🚚 <b>Yangi haydovchi ro'yxatdan o'tdi (avtomatik tasdiqlangan)</b>\n\n"
                    f"Ism: {d['full_name']}\nTelefon: {d['phone']}\n"
                    f"Mashina: {d['vehicle_type']} ({d['vehicle_number']}, {d['capacity_tons']} tonna)\n"
                    f"Hudud: {d['region']}" + (f", {d['tuman']} tumani" if d.get("tuman") else "")
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Adminga haydovchi xabarini yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def handle_driver_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, driver_id = query.data.split(":")
    driver_id = int(driver_id)
    driver = db.get_driver_by_id(driver_id)
    if not driver:
        await query.edit_message_text("Haydovchi topilmadi.")
        return

    telegram_id = driver[1]
    full_name = driver[2]

    if action == "approve_driver":
        db.set_driver_status(driver_id, "tasdiqlangan")
        await query.edit_message_text(f"✅ Tasdiqlandi: {full_name}")
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text="🎉 Tabriklaymiz! Haydovchi sifatida tasdiqlandingiz. "
                     "Endi \"📦 Yangi yuklar\" bo'limidan dehqonlarning mahsulotini ko'rib, olishingiz mumkin.",
                reply_markup=driver_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Haydovchiga xabar yuborishda xatolik: {e}")
    else:
        db.set_driver_status(driver_id, "rad etilgan")
        await query.edit_message_text(f"❌ Rad etildi: {full_name}")
        try:
            await context.bot.send_message(chat_id=telegram_id, text="Afsuski, arizangiz rad etildi.")
        except Exception as e:
            logger.error(f"Haydovchiga xabar yuborishda xatolik: {e}")


# ----------------- Haydovchi paneli: yuklarni ko'rish va olish -----------------

async def driver_panel_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = db.get_driver_by_telegram_id(update.effective_user.id)
    if not driver:
        await update.message.reply_text(
            "Bu bo'lim faqat ro'yxatdan o'tgan haydovchilar uchun. Avval \"📝 Ro'yxatdan o'tish\" bo'limidan "
            "\"🚚 Haydovchilar\" tugmasini bosing.",
            reply_markup=main_menu_keyboard()
        )
        return None
    if driver[7] != "tasdiqlangan":
        db.set_driver_status(driver[0], "tasdiqlangan")
        driver = db.get_driver_by_telegram_id(update.effective_user.id)
    return driver


# ----------------- Haydovchi "Mashinada sotiladi" elonini joylashtirish -----------------

async def ds_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = await driver_panel_guard(update, context)
    if not driver:
        return ConversationHandler.END
    context.user_data["ds"] = {"driver_id": driver[0], "region": driver[6]}
    await update.message.reply_text(
        "🚛 \"Mashinada sotiladi\" elonini joylashtiramiz — sizda hozir sotishga tayyor silos bo'lsa, "
        "shu yerdan mijozlarga e'lon qilasiz. Mijoz sizni tanlab, botdan to'g'ridan-to'g'ri buyurtma beradi.\n\n"
        "1 kg narxini va necha kg borligini BITTA xabarda, alohida qatorlarda kiriting:\n\n"
        "Masalan:\n"
        "550\n"
        "3000",
        reply_markup=cancel_keyboard()
    )
    return DS_PRICE


async def ds_enter_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [l.strip() for l in update.message.text.split("\n") if l.strip()]
    if len(lines) != 2:
        await update.message.reply_text(
            "Iltimos, aynan 2 qatorda yozing: narx, keyin miqdor.\nMasalan:\n550\n3000"
        )
        return DS_PRICE
    try:
        price = int(lines[0].replace(" ", ""))
        qty = float(lines[1].replace(",", "."))
        if price <= 0 or qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Raqamlar noto'g'ri. Iltimos, qaytadan urinib ko'ring.\nMasalan:\n550\n3000"
        )
        return DS_PRICE
    context.user_data["ds"]["price"] = price
    context.user_data["ds"]["quantity"] = qty
    await update.message.reply_text(
        "📷 Silos rasmini yuboring (mijozlar ko'rishi uchun).\n"
        "Rasm yubormoqchi bo'lmasangiz \"-\" deb yozing.",
        reply_markup=cancel_keyboard()
    )
    return DS_PHOTO


async def ds_enter_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file_id = None
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.strip() == "-":
        photo_file_id = None
    else:
        await update.message.reply_text("Iltimos, rasm yuboring yoki \"-\" deb yozing.")
        return DS_PHOTO
    context.user_data["ds"]["photo_file_id"] = photo_file_id
    await update.message.reply_text(
        "Manzilingizni va sifat haqida qisqa izohni kiriting (alohida qatorlarda):\n\n"
        "Masalan:\n"
        "Chust tumani\n"
        "Quruq, yangi o'rilgan\n\n"
        "(Izoh yozmasangiz, faqat manzilni kiriting.)"
    )
    return DS_ADDRESS


async def ds_enter_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ds = context.user_data["ds"]
    lines = [l.strip() for l in update.message.text.split("\n") if l.strip()]
    address = lines[0] if lines else update.message.text.strip()
    description = "\n".join(lines[1:]) if len(lines) > 1 else None
    db.add_driver_silos_listing(
        ds["driver_id"], ds["price"], ds["quantity"], address, ds["region"],
        photo_file_id=ds.get("photo_file_id"), description=description
    )
    await update.message.reply_text(
        f"✅ E'loningiz joylandi: {ds['quantity']} kg, {ds['price']:,} so'm/kg.\n"
        "Endi mijozlar buni \"🚛 Mashinada sotiladi\" bo'limidan ko'rib, botdan to'g'ridan-to'g'ri "
        "sizga buyurtma bera oladi.".replace(",", " "),
        reply_markup=driver_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def driver_my_silos_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = await driver_panel_guard(update, context)
    if not driver:
        return
    listings = db.get_driver_silos_listings_for_driver(driver[0])
    if not listings:
        await update.message.reply_text("Sizda hali savdo e'loni yo'q.")
        return
    await update.message.reply_text("🚛 <b>Sizning savdo e'lonlaringiz:</b>", parse_mode="HTML")
    for lst_id, price, qty, photo_id, address, region, active in listings:
        status_note = "faol" if active else "tugagan"
        photo_note = " 📷" if photo_id else ""
        text = f"• {fmt_money(price)} so'm/kg — {qty} kg | {region}, {address} | {status_note}{photo_note}"
        await update.message.reply_text(text)


async def ask_browse_region(update: Update, section: str, prompt_text: str):
    """Uchala bo'lim (ulgurji/mashinada/qopli) uchun umumiy: respublika yoki aniq viloyat tanlash"""
    buttons = [[InlineKeyboardButton("🇺🇿 Respublika bo'ylab (hammasi)", callback_data=f"browse_region:{section}:ALL")]]
    row = []
    for r in REGIONS:
        row.append(InlineKeyboardButton(r, callback_data=f"browse_region:{section}:{r}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    await update.message.reply_text(prompt_text, reply_markup=InlineKeyboardMarkup(buttons))


async def browse_driver_silos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_browse_region(
        update, "mashinada",
        "🚛 Mashinada sotiladi — qayerdan qidiraylik?"
    )


async def show_driver_silos_results(send_target, context: ContextTypes.DEFAULT_TYPE, region=None):
    """Mijozlar uchun: haydovchilarning 'Mashinada sotiladi' elonlari — bot orqali buyurtma beriladi.
    Qora ro'yxatdagi haydovchilarning elonlari bu yerda ko'rinmaydi."""
    listings = db.get_active_driver_silos_listings(region=region)
    if not listings:
        await send_target.reply_text("Bu hududda hozircha faol savdo e'lonlari yo'q.")
        return

    scope_note = f"({region})" if region else "(respublika bo'ylab)"
    await send_target.reply_text(
        f"🚛 Mashinada sotiladi {scope_note} — eng arzonidan boshlab. "
        "O'zingizga yoqqan haydovchidan buyurtma berishingiz mumkin:"
    )
    for lst_id, driver_id, price, qty, photo_id, address, lst_region, drv_name, drv_phone, veh_num, description in listings:
        sifat_line = f"\nSifati: {description}" if description else ""
        caption = (
            f"🚛 <b>Silos</b> — {fmt_money(price)} so'm/kg\n"
            f"Mavjud: {fmt_money(qty)} kg\n"
            f"Hudud: {lst_region}\n"
            f"Manzili: {address or lst_region}{sifat_line}\n"
            f"Sotuvchi (haydovchi): {drv_name}\n"
            f"Tel: {drv_phone or '—'}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Shu haydovchidan buyurtma berish", callback_data=f"order_driver_silos:{lst_id}")
        ]])
        if photo_id:
            try:
                await send_target.reply_photo(photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=kb)
                continue
            except Exception as e:
                logger.error(f"Haydovchi silos rasmini yuborishda xatolik: {e}")
        await send_target.reply_text(caption, parse_mode="HTML", reply_markup=kb)


async def order_driver_silos_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijoz 'Shu haydovchidan buyurtma berish' tugmasini bosganda, buyurtma jarayoniga to'g'ridan-to'g'ri kiradi"""
    query = update.callback_query
    await query.answer()

    _, listing_id = query.data.split(":")
    listing_id = int(listing_id)
    listing = db.get_driver_silos_listing_by_id(listing_id)
    if not listing or not listing[7]:
        await query.message.reply_text("Kechirasiz, bu e'lon endi faol emas.")
        return ConversationHandler.END

    lst_id, driver_id, price, qty, photo_id, address, region, active, drv_tg_id, drv_name, drv_phone, veh_num = listing

    context.user_data["order"] = {
        "product_name": "Silos", "unit": "kg", "price": price, "type": "driver_silos",
        "package_type": "naval", "listing_id": lst_id, "driver_id": driver_id, "max_quantity": qty,
    }
    await query.message.reply_text(
        f"Nechta kg silos kerak? (mavjud: {qty} kg)",
        reply_markup=cancel_keyboard()
    )
    return ENTER_QUANTITY


async def browse_qopli_silos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_browse_region(
        update, "qopli",
        "📦 Qopli silos — qayerdan qidiraylik?"
    )


async def show_qopli_results(send_target, context: ContextTypes.DEFAULT_TYPE, region=None):
    """Mijozlar uchun: do'kon/sotuvchilarning qopli silos elonlari — bot orqali buyurtma beriladi"""
    listings = db.get_active_qopli_listings(region=region)
    if not listings:
        await send_target.reply_text("Bu hududda hozircha faol qopli silos e'lonlari yo'q.")
        return

    scope_note = f"({region})" if region else "(respublika bo'ylab)"
    await send_target.reply_text(
        f"📦 Qopli silos {scope_note} — eng arzonidan boshlab. "
        "O'zingizga yoqqan sotuvchidan buyurtma berishingiz mumkin:"
    )
    for sp_id, seller_id, tg_id, shop_name, name, unit, price, qty, lst_region, address, photo_id, phone, description in listings:
        sifat_line = f"\nSifati: {description}" if description else ""
        caption = (
            f"📦 <b>{name}</b> — {fmt_money(price)} so'm/{unit}\n"
            f"Mavjud: {fmt_money(qty)} {unit}\n"
            f"Hudud: {lst_region}\n"
            f"Manzili: {address or lst_region}{sifat_line}\n"
            f"Sotuvchi: {shop_name}\n"
            f"Tel: {phone or '—'}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Shu sotuvchidan buyurtma berish", callback_data=f"order_qopli:{sp_id}")
        ]])
        if photo_id:
            try:
                await send_target.reply_photo(photo=photo_id, caption=caption, parse_mode="HTML", reply_markup=kb)
                continue
            except Exception as e:
                logger.error(f"Qopli mahsulot rasmini yuborishda xatolik: {e}")
        await send_target.reply_text(caption, parse_mode="HTML", reply_markup=kb)


async def order_qopli_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mijoz 'Shu sotuvchidan buyurtma berish' tugmasini bosganda, buyurtma jarayoniga to'g'ridan-to'g'ri kiradi"""
    query = update.callback_query
    await query.answer()

    _, sp_id = query.data.split(":")
    sp_id = int(sp_id)
    listing = db.get_seller_product_by_id(sp_id)
    if not listing or listing[7] or (listing[5] is not None and listing[5] <= 0):
        await query.message.reply_text("Kechirasiz, bu e'lon endi faol emas.")
        return ConversationHandler.END

    _id, seller_id, name, unit, price, qty, address, claimed, seller_tg_id, shop_name, region, package_type, photo_id = listing

    context.user_data["order"] = {
        "product_name": name, "unit": unit, "price": price, "type": "qopli_listing",
        "package_type": "qopli", "sp_id": sp_id, "seller_id": seller_id, "max_quantity": qty,
    }
    await query.message.reply_text(
        f"Nechta {unit} {name} kerak? (mavjud: {qty} {unit})",
        reply_markup=cancel_keyboard()
    )
    return ENTER_QUANTITY


async def browse_loads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_browse_region(
        update, "ulgurji",
        "🌾 Fermerlar ulgurji (naval) — qayerdan qidiraylik?"
    )


async def show_loads_results(send_target, context: ContextTypes.DEFAULT_TYPE, user_id: int, region=None):
    driver = db.get_driver_by_telegram_id(user_id)
    is_approved_driver = driver is not None and driver[7] == "tasdiqlangan"

    loads = db.get_available_farmer_loads(region=region)
    combine_silos = db.get_active_combine_silos_listings(region=region)

    if not loads and not combine_silos:
        await send_target.reply_text("Bu hududda hozircha mavjud yuklar yo'q.")
        return

    combined = []
    for sp_id, shop_name, phone, lst_region, product_name, unit, price, qty, address, package_type, photo_id, description in loads:
        price_unit = "kg" if package_type == "gektar" else unit
        combined.append({
            "source": "farmer", "sort_price": price, "sp_id": sp_id, "shop_name": shop_name,
            "phone": phone, "region": lst_region, "product_name": product_name, "unit": unit,
            "price": price, "price_unit": price_unit, "qty": qty, "address": address,
            "package_type": package_type, "photo_id": photo_id, "description": description,
        })
    for lst_id, price, qty, photo_id, address, lst_region, owner_id, owner_name, owner_phone, description in combine_silos:
        combined.append({
            "source": "combine", "sort_price": price, "price": price, "qty": qty,
            "photo_id": photo_id, "address": address, "region": lst_region,
            "owner_name": owner_name, "owner_phone": owner_phone, "description": description,
        })

    combined.sort(key=lambda x: x["sort_price"])

    scope_note = f"({region})" if region else "(respublika bo'ylab)"
    await send_target.reply_text(
        f"🌾 Fermerlar ulgurji {scope_note} — eng arzonidan boshlab, narxi, rasmi va manziliga qarab tanlang:"
    )

    for item in combined:
        if item["source"] == "farmer":
            package_type = item["package_type"]
            type_icon = "📦" if package_type == "qopli" else "🌾"
            qty_label = "gektar" if package_type == "gektar" else item["unit"]
            text = (
                f"{type_icon} <b>{item['product_name']}</b> — {fmt_money(item['qty'])} {qty_label}\n"
                f"Narxi: {fmt_money(item['price'])} so'm/{item['price_unit']}\n"
                f"Manzili: {item['address'] or item['region']}\n"
                f"Tel: {item['phone']}"
            )
            if is_approved_driver:
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🚛 Bu yukni olaman", callback_data=f"claim_load:{item['sp_id']}")
                ]])
            else:
                kb = None
        else:
            qty_note = f"{fmt_money(item['qty'])} gektar" if item["qty"] is not None else "miqdor noma'lum"
            text = (
                f"🚜 <b>Silos</b> — {qty_note}\n"
                f"Narxi: {fmt_money(item['price'])} so'm/kg\n"
                f"Manzili: {item['address'] or item['region']}\n"
                f"Tel: {item['owner_phone'] or '—'}"
            )
            kb = None

        photo_id = item["photo_id"]
        if photo_id:
            try:
                await send_target.reply_photo(photo=photo_id, caption=text, parse_mode="HTML", reply_markup=kb)
                continue
            except Exception as e:
                logger.error(f"Rasm yuborishda xatolik: {e}")
        await send_target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def browse_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'🌾 Fermerlar ulgurji' / '🚛 Mashinada sotiladi' / '📦 Qopli silos' uchun hudud tanlangach ishlaydi"""
    query = update.callback_query
    await query.answer()
    _, section, region_raw = query.data.split(":", 2)
    region = None if region_raw == "ALL" else region_raw

    if section == "ulgurji":
        await show_loads_results(query.message, context, update.effective_user.id, region=region)
    elif section == "mashinada":
        await show_driver_silos_results(query.message, context, region=region)
    elif section == "qopli":
        await show_qopli_results(query.message, context, region=region)


async def claim_load_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    driver = db.get_driver_by_telegram_id(update.effective_user.id)
    if not driver:
        await query.answer("Faqat ro'yxatdan o'tgan haydovchilar yuk olishi mumkin.", show_alert=True)
        return ConversationHandler.END
    if driver[7] != "tasdiqlangan":
        db.set_driver_status(driver[0], "tasdiqlangan")
        driver = db.get_driver_by_telegram_id(update.effective_user.id)

    _, sp_id = query.data.split(":")
    sp_id = int(sp_id)
    sp = db.get_seller_product_by_id(sp_id)
    if not sp or sp[7] == 1:
        await query.answer("Kechirasiz, bu yuk allaqachon band qilingan.", show_alert=True)
        return ConversationHandler.END

    load_region = sp[10]

    # Qizil (5+ kun) qarzi bo'lgan haydovchi shu VILOYAT ichida yangi yuk ololmaydi —
    # avval o'sha viloyatdagi eski qarzini yopishi kerak (boshqa viloyatdagi qarz bu yerga ta'sir qilmaydi)
    debts = db.get_driver_debts(driver[0], region=load_region)
    red_debts = [d for d in debts if d["level"] == "qizil"]
    if red_debts:
        total_debt = sum(d["amount"] for d in red_debts)
        worst = max(red_debts, key=lambda d: d["days"])
        await query.answer(
            f"⛔ Sizda {load_region} viloyatida {worst['days']} kundan beri to'lanmagan qarz bor "
            f"({worst['farmer_name']}, {total_debt:,} so'm). Yangi yuk olishdan oldin avval qarzingizni yoping."
            .replace(",", " "),
            show_alert=True
        )
        return ConversationHandler.END

    context.user_data["claim"] = {"sp_id": sp_id, "driver_id": driver[0]}
    product_name, unit, base_price, available_qty, package_type = sp[2], sp[3], sp[4], sp[5], sp[11]

    if package_type == "gektar":
        price_note = f"bazaviy narx: {base_price:,} so'm/kg (yer maydoni gektar bilan o'lchanadi)".replace(",", " ")
    else:
        price_note = f"bazaviy narx: {base_price:,} so'm/{unit}".replace(",", " ")

    await query.message.reply_text(
        f"'{product_name}' — mavjud: {available_qty} {unit}, {price_note}\n\n"
        f"Necha {unit} olmoqchisiz?",
        reply_markup=cancel_keyboard()
    )
    return CLAIM_SET_TONNAGE


async def claim_load_set_tonnage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    claim = context.user_data.get("claim")
    if not claim:
        await update.message.reply_text("Xatolik yuz berdi, qaytadan urinib ko'ring.", reply_markup=driver_menu_keyboard())
        return ConversationHandler.END

    sp = db.get_seller_product_by_id(claim["sp_id"])
    if not sp or sp[7] == 1:
        await update.message.reply_text("Kechirasiz, bu yuk allaqachon band qilingan.", reply_markup=driver_menu_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

    available_qty, unit, package_type = sp[5], sp[3], sp[11]
    try:
        tonnage = float(update.message.text.replace(",", "."))
        if tonnage <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to'g'ri son kiriting (masalan: 5).")
        return CLAIM_SET_TONNAGE

    if tonnage > available_qty:
        await update.message.reply_text(
            f"Kechirasiz, faqat {available_qty} {unit} mavjud. Kamroq miqdor kiriting."
        )
        return CLAIM_SET_TONNAGE

    claim["tonnage"] = tonnage
    claim["farmer_unit"] = unit

    if package_type == "gektar":
        await update.message.reply_text(
            f"🌾 Siz {tonnage} gektar yer sotib olyapsiz. Bu yerdan taxminan "
            "necha KG silos olib chiqib, mijozlarga sotmoqchisiz? (masalan: 25000)",
            reply_markup=cancel_keyboard()
        )
        return CLAIM_SET_RESALE_QTY

    await update.message.reply_text(
        f"Siz mijozga qancha narxda sotmoqchisiz? (1 {unit} uchun, so'mda)",
        reply_markup=cancel_keyboard()
    )
    return CLAIM_SET_PRICE


async def claim_load_set_resale_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    claim = context.user_data.get("claim")
    if not claim:
        await update.message.reply_text("Xatolik yuz berdi, qaytadan urinib ko'ring.", reply_markup=driver_menu_keyboard())
        return ConversationHandler.END

    try:
        resale_qty = float(update.message.text.replace(",", "."))
        if resale_qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to'g'ri son kiriting (masalan: 25000).")
        return CLAIM_SET_RESALE_QTY

    claim["resale_quantity"] = resale_qty
    claim["resale_unit"] = "kg"

    await update.message.reply_text(
        "Siz mijozga qancha narxda sotmoqchisiz? (1 kg uchun, so'mda)",
        reply_markup=cancel_keyboard()
    )
    return CLAIM_SET_PRICE


async def claim_load_set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sell_price = int(update.message.text.replace(" ", ""))
        if sell_price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return CLAIM_SET_PRICE

    claim = context.user_data.get("claim")
    if not claim:
        await update.message.reply_text("Xatolik yuz berdi, qaytadan urinib ko'ring.", reply_markup=driver_menu_keyboard())
        return ConversationHandler.END

    claim["sell_price"] = sell_price
    await update.message.reply_text(
        "📷 Mahsulotning rasmini yuboring (xaridorlar ko'rishi uchun).\n"
        "Rasm yubormoqchi bo'lmasangiz \"-\" deb yozing.",
        reply_markup=cancel_keyboard()
    )
    return CLAIM_SET_PHOTO


async def claim_load_set_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    claim = context.user_data.get("claim")
    if not claim:
        await update.message.reply_text("Xatolik yuz berdi, qaytadan urinib ko'ring.", reply_markup=driver_menu_keyboard())
        return ConversationHandler.END

    photo_file_id = None
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.strip() == "-":
        photo_file_id = None
    else:
        await update.message.reply_text("Iltimos, rasm yuboring yoki \"-\" deb yozing.")
        return CLAIM_SET_PHOTO

    listing_id = db.claim_farm_load(
        claim["sp_id"], claim["driver_id"], claim["tonnage"], claim["sell_price"],
        resale_quantity=claim.get("resale_quantity"), resale_unit=claim.get("resale_unit"),
        photo_file_id=photo_file_id
    )
    if not listing_id:
        await update.message.reply_text(
            "Kechirasiz, bu miqdor endi mavjud emas.", reply_markup=driver_menu_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END

    sell_price = claim["sell_price"]
    listing = db.get_driver_listing_by_id(listing_id)
    unit = listing[4]
    listed_qty = listing[5]
    farmer_payment = listing[18]
    farmer_tg_id = listing[16]
    farmer_name = listing[17]
    farmer_region = listing[11]
    driver_full = db.get_driver_by_id(claim["driver_id"])
    driver_name, vehicle_type, vehicle_number = driver_full[2], driver_full[4], driver_full[8]

    await update.message.reply_text(
        f"✅ {claim['tonnage']} {claim['farmer_unit']} sizga biriktirildi! Endi mijozlar {listed_qty} {unit} "
        f"miqdorida, {sell_price:,} so'm/{unit} narxda sizdan buyurtma berishlari mumkin.\n\n"
        f"Fermerga to'lashingiz kerak bo'lgan summa: {farmer_payment:,} so'm".replace(",", " "),
        reply_markup=driver_menu_keyboard()
    )

    try:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Pulni oldim", callback_data=f"confirm_payment:{listing_id}")
        ]])

        warning = ""
        other_debts = db.get_driver_debts(claim["driver_id"], exclude_listing_id=listing_id, region=farmer_region)
        if other_debts:
            total_debt = sum(d["amount"] for d in other_debts)
            worst = max(other_debts, key=lambda d: d["days"])
            icon_title = "🔴 DIQQAT — QORA RO'YXAT" if worst["level"] == "qizil" else "🟡 DIQQAT"
            warning = (
                f"\n\n{icon_title} <b>(🚛 {vehicle_number})!</b>\n"
                f"Bu haydovchi {farmer_region} viloyatidagi boshqa {len(other_debts)} ta fermerga jami "
                f"{total_debt:,} so'm qarzdor (eng eskisi: {worst['days']} kun, {worst['farmer_name']}). Ehtiyot bo'ling!"
            ).replace(",", " ")

        await context.bot.send_message(
            chat_id=farmer_tg_id,
            text=(
                f"🚛 <b>Yukingizdan qism olindi</b>\n\n"
                f"Haydovchi: {driver_name}\n"
                f"Mashina: {vehicle_type} ({vehicle_number})\n"
                f"Miqdor: {claim['tonnage']} {unit}\n"
                f"To'lanishi kerak: {farmer_payment:,} so'm\n\n"
                "Pulni qo'lga olganingizda quyidagi tugmani bosing:"
                f"{warning}"
            ).replace(",", " "),
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception as e:
        logger.error(f"Fermerga xabar yuborishda xatolik: {e}")

    # Adminga ham xuddi shu tugma bilan xabar boradi — u ham to'lovni tasdiqlay oladi
    if ADMIN_CHAT_ID:
        try:
            admin_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Pulni oldim (admin)", callback_data=f"confirm_payment:{listing_id}")
            ]])
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"🚛 <b>Yuk olindi — nazorat uchun</b>\n\n"
                    f"Fermer: {farmer_name}\n"
                    f"Haydovchi: {driver_name} ({vehicle_type}, {vehicle_number})\n"
                    f"Miqdor: {claim['tonnage']} {unit}\n"
                    f"Fermerga to'lanishi kerak: {farmer_payment:,} so'm\n\n"
                    "Agar fermer o'zi tasdiqlolmasa, shu yerdan siz ham tasdiqlashingiz mumkin:"
                ).replace(",", " "),
                parse_mode="HTML",
                reply_markup=admin_kb
            )
        except Exception as e:
            logger.error(f"Adminga xabar yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def handle_payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, listing_id = query.data.split(":")
    listing_id = int(listing_id)
    listing = db.get_driver_listing_by_id(listing_id)
    if not listing:
        await query.edit_message_text("E'lon topilmadi.")
        return

    farmer_tg_id = listing[16]
    is_admin = ADMIN_CHAT_ID and str(update.effective_user.id) == str(ADMIN_CHAT_ID)
    if update.effective_user.id != farmer_tg_id and not is_admin:
        await query.answer("Bu sizga tegishli emas. Faqat fermer yoki admin tasdiqlay oladi.", show_alert=True)
        return

    db.confirm_payment(listing_id)
    farmer_payment = listing[18]
    confirmed_by = "Admin" if is_admin else "Fermer"
    await query.edit_message_text(
        f"✅ To'lov qabul qilingani tasdiqlandi: {farmer_payment:,} so'm ({confirmed_by} tomonidan)".replace(",", " ")
    )

    # Agar admin tasdiqlagan bo'lsa, fermerga ham xabar beramiz
    if is_admin and farmer_tg_id:
        try:
            await context.bot.send_message(
                chat_id=farmer_tg_id,
                text=f"✅ Admin sizning nomingizdan to'lovni tasdiqladi: {farmer_payment:,} so'm".replace(",", " ")
            )
        except Exception as e:
            logger.error(f"Fermerga to'lov tasdiqlash xabarini yuborishda xatolik: {e}")

    driver_tg_id_row = db.get_driver_by_id(listing[1])
    if driver_tg_id_row:
        try:
            await context.bot.send_message(
                chat_id=driver_tg_id_row[1],
                text="✅ To'lov qabul qilingani tasdiqlandi. Rahmat!"
            )
        except Exception as e:
            logger.error(f"Haydovchiga to'lov tasdiqlash xabarini yuborishda xatolik: {e}")


async def my_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    driver = await driver_panel_guard(update, context)
    if not driver:
        return
    listings = db.get_driver_listings_for_driver(driver[0])
    if not listings:
        await update.message.reply_text("Sizda hali e'lonlar yo'q. \"📦 Yangi yuklar\" orqali yuk oling.")
        return

    for lst_id, name, unit, qty, sell_price, region, status, est_qty, actual_weight, weight_status, package_type, weight_photo in listings:
        weight_line = ""
        kb = None
        if weight_status == "kutilmoqda" and actual_weight is None and not weight_photo:
            weight_line = f"\n⚖️ Og'irlik hali kiritilmagan (taxminiy: {est_qty} {unit})"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("📷 Og'irlik rasmini yuborish", callback_data=f"enter_weight:{lst_id}")
            ]])
        elif weight_status == "kutilmoqda" and actual_weight is None and weight_photo:
            weight_line = "\n📷 Rasm fermerga yuborildi — u miqdorni kiritishini kutmoqda"
        elif weight_status == "tasdiqlangan":
            weight_line = f"\n✅ Og'irlik fermer tomonidan kiritildi: {actual_weight} {unit}"
        elif weight_status == "bahsli":
            weight_line = "\n⚠️ Fermer og'irlikka rozi bo'lmadi — admin bilan bog'laning."

        type_note = "📦 qopli (respublika bo'ylab)" if package_type == "qopli" else "🌾 naval (vodiy bo'ylab)"
        text = (
            f"{name} — {qty} {unit} qoldi, narxi {sell_price:,} so'm/{unit} | {status} | {type_note}"
            f"{weight_line}"
        ).replace(",", " ")
        await update.message.reply_text(text, reply_markup=kb)


# ----------------- Tarozi natijasini kiritish va fermer tasdiqlashi -----------------

async def enter_weight_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, listing_id = query.data.split(":")
    listing_id = int(listing_id)
    listing = db.get_driver_listing_by_id(listing_id)
    if not listing:
        await query.message.reply_text("E'lon topilmadi.")
        return ConversationHandler.END

    driver_tg_id = listing[14]
    if update.effective_user.id != driver_tg_id:
        await query.answer("Bu sizning e'loningiz emas.", show_alert=True)
        return ConversationHandler.END

    context.user_data["weight_listing_id"] = listing_id
    await query.message.reply_text(
        "📷 Yuk/tarozi og'irligi ko'rsatilgan rasmni yuboring — bu fermerga yuboriladi, "
        "u o'zi rasmga qarab aniq miqdorni kiritadi.",
        reply_markup=cancel_keyboard()
    )
    return ENTER_WEIGHT_PHOTO


async def enter_weight_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Iltimos, rasm yuboring.")
        return ENTER_WEIGHT_PHOTO

    weight_photo_file_id = update.message.photo[-1].file_id
    listing_id = context.user_data.get("weight_listing_id")
    db.set_weight_photo_only(listing_id, weight_photo_file_id)
    listing = db.get_driver_listing_by_id(listing_id)
    (_, drv_id, seller_id, product_name, unit, qty, est_qty, actual_weight, weight_status,
     base_price, sell_price, region, pickup_address, status, driver_tg_id, driver_name,
     farmer_tg_id, farmer_name, farmer_payment, payment_confirmed, vehicle_number,
     package_type, weight_photo) = listing

    await update.message.reply_text(
        "✅ Rasm fermerga yuborildi. U ko'rib chiqib, miqdorni kiritishi bilan sizga xabar boradi.",
        reply_markup=driver_menu_keyboard()
    )

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏️ Miqdorini kiritish", callback_data=f"farmer_weight:{listing_id}")
    ]])
    caption = (
        f"⚖️ <b>Yuk og'irligi rasmi keldi</b>\n\n"
        f"Haydovchi ({driver_name}) sizning {product_name} yukingizni tortdi va rasmini yubordi.\n"
        f"Taxminiy: {est_qty} {unit}\n\n"
        "Rasmga qarab (yoki haydovchi bilan telefon orqali gaplashib) aniq miqdorni kiriting:"
    )
    try:
        await context.bot.send_photo(
            chat_id=farmer_tg_id, photo=weight_photo_file_id, caption=caption,
            parse_mode="HTML", reply_markup=kb
        )
    except Exception as e:
        logger.error(f"Fermerga tarozi rasmini yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def handle_weight_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, listing_id, confirmed = query.data.split(":")
    listing_id = int(listing_id)
    confirmed = confirmed == "1"

    listing = db.get_driver_listing_by_id(listing_id)
    if not listing:
        await query.edit_message_text("E'lon topilmadi.")
        return

    farmer_tg_id = listing[16]
    if update.effective_user.id != farmer_tg_id:
        await query.answer("Bu sizga tegishli emas.", show_alert=True)
        return

    db.confirm_listing_weight(listing_id, confirmed)
    driver_tg_id = listing[14]
    actual_weight = listing[7]
    unit = listing[4]

    if confirmed:
        await query.edit_message_text(f"✅ Siz tasdiqladingiz: {actual_weight} {unit}")
        driver_msg = f"✅ Fermer tarozi natijasini tasdiqladi: {actual_weight} {unit}."
    else:
        await query.edit_message_text("❌ Siz rozi bo'lmadingiz. Admin bilan bog'lanamiz.")
        driver_msg = "⚠️ Fermer tarozi natijasiga rozi bo'lmadi. Iltimos, admin bilan bog'laning."

    try:
        await context.bot.send_message(chat_id=driver_tg_id, text=driver_msg)
    except Exception as e:
        logger.error(f"Haydovchiga xabar yuborishda xatolik: {e}")

    if not confirmed and ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"⚠️ Bahsli tarozi natijasi: e'lon #{listing_id}. "
                     "Fermer va haydovchi bilan bog'lanib, masalani hal qiling."
            )
        except Exception as e:
            logger.error(f"Adminga bahs xabarini yuborishda xatolik: {e}")


# ----------------- Fermer: haydovchi telefon/rasm orqali aytgan miqdorni o'zi kiritadi -----------------

async def farmer_weight_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = await seller_panel_guard(update, context)
    if not seller:
        return

    pending = db.get_unweighed_listings_for_seller(seller[0])
    pending_manual = db.get_pending_manual_entries_for_seller(seller[0])

    if not pending and not pending_manual:
        await update.message.reply_text("Hozircha miqdor kutayotgan yuklar yo'q.")
        return

    await update.message.reply_text(
        "Quyidagi yuklar uchun og'irlik hali kiritilmagan. "
        "Haydovchi tarozida tortib, sizga telefon orqali aytgach, shu yerdan kiriting:"
    )
    for lst_id, product_name, unit, est_qty, driver_name, vehicle_number, phone, weight_photo in pending:
        text = (
            f"{product_name} — taxminiy {est_qty} {unit}\n"
            f"Haydovchi: {driver_name} ({vehicle_number or '—'})\n"
            f"Telefon: {phone or '—'}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ Miqdorini kiritish", callback_data=f"farmer_weight:{lst_id}")
        ]])
        if weight_photo:
            try:
                await update.message.reply_photo(photo=weight_photo, caption=text, reply_markup=kb)
                continue
            except Exception as e:
                logger.error(f"Rasm yuborishda xatolik: {e}")
        await update.message.reply_text(text, reply_markup=kb)

    for mid, vehicle_number, phone, price_per_kg, created_at in pending_manual:
        text = (
            f"🚛 {vehicle_number or '—'} (qo'lda yozilgan)\n"
            f"Telefon: {phone or '—'}\n"
            f"Narx: {price_per_kg:,} so'm/kg".replace(",", " ")
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✏️ Kilogramini kiritish", callback_data=f"manual_weight:{mid}")
        ]])
        await update.message.reply_text(text, reply_markup=kb)


async def manual_weight_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, entry_id = query.data.split(":")
    entry_id = int(entry_id)
    entry = db.get_manual_entry_by_id(entry_id)
    if not entry:
        await query.message.reply_text("Yozuv topilmadi.")
        return ConversationHandler.END
    context.user_data["manual_weight_entry_id"] = entry_id
    await query.message.reply_text(
        f"🚛 {entry[2]} — necha kg silos oldi? (masalan: 2500):",
        reply_markup=cancel_keyboard()
    )
    return ML_TONNA_ENTRY


async def manual_weight_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kg = float(update.message.text.replace(",", "."))
        if kg <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to'g'ri son kiriting (masalan: 2500).")
        return ML_TONNA_ENTRY

    entry_id = context.user_data.get("manual_weight_entry_id")
    total_sum = db.set_manual_entry_weight(entry_id, kg)
    if total_sum is None:
        await update.message.reply_text("Xatolik yuz berdi.", reply_markup=seller_menu_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ Kiritildi: {kg:,.0f} kg. Jami summa: {total_sum:,} so'm".replace(",", " "),
        reply_markup=seller_menu_keyboard()
    )
    context.user_data.clear()
    await seller_transaction_report(update, context)
    return ConversationHandler.END


async def mark_paid_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    seller = await seller_panel_guard(update, context)
    if not seller:
        return
    bot_rows, manual_rows = db.get_unpaid_entries_for_seller(seller[0])
    if not bot_rows and not manual_rows:
        await update.message.reply_text("Hammasi to'langan — hali pul kutayotgan yozuv yo'q. ✅")
        return

    await update.message.reply_text("Pul olganingiz haydovchini tanlang:")
    for lst_id, vehicle_number, payment, quantity, unit in bot_rows:
        amount = payment if payment is not None else 0
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Pulni oldim", callback_data=f"mark_paid_bot:{lst_id}")
        ]])
        await update.message.reply_text(
            f"🚛 {vehicle_number or '—'} — {amount:,} so'm".replace(",", " "), reply_markup=kb
        )
    for mid, vehicle_number, total_sum in manual_rows:
        amount = total_sum if total_sum is not None else 0
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Pulni oldim", callback_data=f"mark_paid_manual:{mid}")
        ]])
        await update.message.reply_text(
            f"🚛 {vehicle_number or '—'} — {amount:,} so'm".replace(",", " "), reply_markup=kb
        )


async def mark_paid_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, listing_id = query.data.split(":")
    db.confirm_payment(int(listing_id))
    await query.edit_message_text("✅ To'lov qabul qilingani belgilandi.")


async def mark_paid_manual_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, entry_id = query.data.split(":")
    db.confirm_manual_payment(int(entry_id))
    await query.edit_message_text("✅ To'lov qabul qilingani belgilandi.")


def _is_admin(actor_tg_id):
    return bool(ADMIN_CHAT_ID) and str(actor_tg_id) == str(ADMIN_CHAT_ID)


async def delete_seller_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_admin(update.effective_user.id):
        await query.answer("Bu faqat admin uchun.", show_alert=True)
        return
    _, sp_id = query.data.split(":")
    db.deactivate_seller_product(int(sp_id))
    await query.answer("O'chirildi.")
    await query.edit_message_text("🗑 E'lon admin tomonidan o'chirildi.")


async def delete_driver_silos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_admin(update.effective_user.id):
        await query.answer("Bu faqat admin uchun.", show_alert=True)
        return
    _, lst_id = query.data.split(":")
    db.deactivate_driver_silos_listing(int(lst_id))
    await query.answer("O'chirildi.")
    await query.edit_message_text("🗑 E'lon admin tomonidan o'chirildi.")


async def delete_combine_listing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_admin(update.effective_user.id):
        await query.answer("Bu faqat admin uchun.", show_alert=True)
        return
    _, lst_id = query.data.split(":")
    db.deactivate_combine_listing(int(lst_id))
    await query.answer("O'chirildi.")
    await query.edit_message_text("🗑 E'lon admin tomonidan o'chirildi.")


async def delete_combine_silos_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_admin(update.effective_user.id):
        await query.answer("Bu faqat admin uchun.", show_alert=True)
        return
    _, lst_id = query.data.split(":")
    db.deactivate_combine_silos_listing(int(lst_id))
    await query.answer("O'chirildi.")
    await query.edit_message_text("🗑 E'lon admin tomonidan o'chirildi.")


async def admin_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/elonlar — faqat admin uchun: barcha faol e'lonlarni korsatadi, har biriga ochirish tugmasi bilan"""
    if not _is_admin(update.effective_user.id):
        return

    sp_rows = db.get_available_farmer_loads()
    ds_rows = db.get_active_driver_silos_listings()
    cs_rows = db.get_active_combine_silos_listings()
    cl_rows = db.get_active_combine_listings()

    total = len(sp_rows) + len(ds_rows) + len(cs_rows) + len(cl_rows)
    if total == 0:
        await update.message.reply_text("Hozircha faol e'lonlar yo'q.")
        return

    await update.message.reply_text(f"🗑 <b>Barcha faol e'lonlar ({total} ta):</b>", parse_mode="HTML")

    for sp_id, shop_name, phone, region, product_name, unit, price, qty, address, package_type, photo_id, description in sp_rows:
        text = (
            f"🌾 [Fermer] {product_name} — {fmt_money(qty)} {unit}, {fmt_money(price)} so'm/{unit}\n"
            f"{shop_name} | {phone} | {region}, {address}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_sp:{sp_id}")]])
        await update.message.reply_text(text, reply_markup=kb)

    for lst_id, driver_id, price, qty, photo_id, address, region, drv_name, drv_phone, veh_num, description in ds_rows:
        text = (
            f"🚛 [Haydovchi] Silos — {fmt_money(qty)} kg, {fmt_money(price)} so'm/kg\n"
            f"{drv_name} ({veh_num}) | {drv_phone} | {region}, {address}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_ds:{lst_id}")]])
        await update.message.reply_text(text, reply_markup=kb)

    for lst_id, price, qty, photo_id, address, region, owner_id, owner_name, owner_phone, description in cs_rows:
        qty_note = f"{qty} gektar" if qty is not None else "miqdor noma'lum"
        text = (
            f"🚜 [Kombayn silos] — {qty_note}, {fmt_money(price)} so'm/kg\n"
            f"{owner_name} | {owner_phone} | {region}, {address}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_csl:{lst_id}")]])
        await update.message.reply_text(text, reply_markup=kb)

    for lst_id, model, price, photo_id, address, region, owner_name, owner_phone, coverage in cl_rows:
        text = (
            f"🚜 [Kombayn texnika] {model} — {fmt_money(price)} so'm/gektar\n"
            f"{owner_name} | {owner_phone} | {region}, {address}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_cl:{lst_id}")]])
        await update.message.reply_text(text, reply_markup=kb)


async def farmer_weight_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, listing_id = query.data.split(":")
    listing_id = int(listing_id)
    listing = db.get_driver_listing_by_id(listing_id)
    if not listing:
        await query.message.reply_text("E'lon topilmadi.")
        return ConversationHandler.END

    farmer_tg_id = listing[16]
    if update.effective_user.id != farmer_tg_id:
        await query.answer("Bu sizga tegishli emas.", show_alert=True)
        return ConversationHandler.END

    context.user_data["farmer_weight_listing_id"] = listing_id
    unit = listing[4]
    await query.message.reply_text(
        f"Haydovchi aytgan miqdorni kiriting ({unit} hisobida, masalan: 5800):",
        reply_markup=cancel_keyboard()
    )
    return FARMER_ENTER_WEIGHT


async def farmer_weight_exit_to_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fermer 'Miqdor kiritish' jarayonida turib '📊 Mening jadvalim' tugmasini bossa —
    bu matn og'irlik sifatida yutilib ketmasin, jarayon to'xtatilib, jadval ochilsin."""
    context.user_data.clear()
    await seller_transaction_report(update, context)
    return ConversationHandler.END


async def farmer_weight_exit_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fermer 'Miqdor kiritish' jarayonida turib '⬅️ Bosh menyu' tugmasini bossa — jarayon to'xtatilsin."""
    context.user_data.clear()
    await update.message.reply_text("Bosh menyu:", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def farmer_weight_exit_to_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fermer biror jarayonda turib '📝 Ro'yxatdan o'tish' tugmasini bossa — jarayon to'xtatilib,
    ro'yxatdan o'tish bo'limi ochilsin (matn yutilib ketmasin)."""
    context.user_data.clear()
    await registration_menu_open(update, context)
    return ConversationHandler.END


async def farmer_weight_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.replace(",", "."))
        if weight <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to'g'ri son kiriting (masalan: 5800).")
        return FARMER_ENTER_WEIGHT

    context.user_data["farmer_weight_value"] = weight
    listing_id = context.user_data.get("farmer_weight_listing_id")
    listing = db.get_driver_listing_by_id(listing_id)
    base_price = listing[9]
    unit = listing[4]

    await update.message.reply_text(
        f"Narxi shu {unit} uchun o'zgarmadimi? Hozirgi narx: {base_price:,} so'm/{unit}.\n"
        f"Agar boshqa narxda kelishgan bo'lsangiz, yangi narxni kiriting, "
        f"aks holda \"-\" deb yozing:".replace(",", " "),
        reply_markup=cancel_keyboard()
    )
    return FARMER_ENTER_PRICE


async def farmer_weight_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    custom_price = None
    if text != "-":
        try:
            custom_price = int(text.replace(" ", ""))
            if custom_price <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Iltimos, to'g'ri narx kiriting yoki \"-\" deb yozing.")
            return FARMER_ENTER_PRICE

    weight = context.user_data.get("farmer_weight_value")
    listing_id = context.user_data.get("farmer_weight_listing_id")
    listing = db.get_driver_listing_by_id(listing_id)
    if not listing:
        await update.message.reply_text("Xatolik yuz berdi.", reply_markup=seller_menu_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

    new_payment = db.farmer_set_weight(listing_id, weight, custom_price=custom_price)
    unit = listing[4]
    driver_tg_id = listing[14]
    driver_name = listing[15]

    payment_note = f"\nTo'lov summasi: {new_payment:,} so'm".replace(",", " ") if new_payment is not None else ""
    await update.message.reply_text(
        f"✅ Miqdor kiritildi: {weight} {unit}{payment_note}",
        reply_markup=seller_menu_keyboard()
    )

    try:
        await context.bot.send_message(
            chat_id=driver_tg_id,
            text=f"✅ Fermer sizning yukingiz miqdorini kiritdi: {weight} {unit}."
        )
    except Exception as e:
        logger.error(f"Haydovchiga xabar yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


# ----------------- Kombaynlar bo'limi -----------------

async def combine_menu_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚜 Kombaynlar bo'limi — kombayn egalari o'z texnikasini rasmi, "
        "1 gektar uchun o'rish narxi va manzili bilan e'lon qiladi. "
        "Fermerlar esa shu yerdan eng mos kombaynni tanlaydi.",
        reply_markup=combine_menu_keyboard()
    )


async def browse_combines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    listings = db.get_active_combine_listings()
    if not listings:
        await update.message.reply_text("Hozircha faol kombayn e'lonlari yo'q.")
        return

    await update.message.reply_text(
        "🚜 Barcha faol kombaynlar — eng arzon narxidan boshlab:"
    )
    for lst_id, model, price, photo_id, address, region, owner_name, owner_phone, coverage in listings:
        coverage_label = "🇺🇿 Respublika bo'ylab" if coverage == "respublika" else "🏞 Vodiy bo'ylab"
        caption = (
            f"<b>{model}</b>\n"
            f"1 gektar uchun narx: {fmt_money(price)} so'm\n"
            f"Xizmat hududi: {coverage_label}\n"
            f"Hudud: {region}\n"
            f"Manzil: {address or 'ko’rsatilmagan'}\n"
            f"Egasi: {owner_name}\n"
            f"Telefon: {owner_phone or '—'}"
        )

        if photo_id:
            try:
                await update.message.reply_photo(photo=photo_id, caption=caption, parse_mode="HTML")
                continue
            except Exception as e:
                logger.error(f"Kombayn rasmini yuborishda xatolik: {e}")
        await update.message.reply_text(caption, parse_mode="HTML")


async def combine_owner_register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = db.get_combine_owner_by_telegram_id(update.effective_user.id)
    if existing:
        status = existing[5]
        if status != "tasdiqlangan":
            db.set_combine_owner_status(existing[0], "tasdiqlangan")
        await update.message.reply_text(
            "Siz allaqachon ro'yxatdan o'tgansiz.",
            reply_markup=combine_owner_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🚜 Kombayn egasi sifatida ro'yxatdan o'tish.\n\nIsm-familiyangizni kiriting:",
        reply_markup=cancel_keyboard()
    )
    return COMBINE_NAME


async def combine_enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["combine_owner"] = {"full_name": update.message.text}
    await update.message.reply_text("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
    return COMBINE_PHONE


async def combine_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number if update.message.contact else update.message.text
    context.user_data["combine_owner"]["phone"] = phone
    await update.message.reply_text(
        "Qaysi hududda asosan ishlaysiz?",
        reply_markup=regions_keyboard()
    )
    return COMBINE_REGION


async def combine_enter_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text not in REGIONS:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return COMBINE_REGION

    d = context.user_data["combine_owner"]
    user = update.effective_user
    owner_id = db.register_combine_owner(user.id, d["full_name"], d["phone"], text)

    await update.message.reply_text(
        "✅ Ro'yxatdan muvaffaqiyatli o'tdingiz! Endi texnika qo'sha olasiz.",
        reply_markup=combine_owner_menu_keyboard()
    )

    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"🚜 <b>Yangi kombayn egasi ro'yxatdan o'tdi (avtomatik tasdiqlangan)</b>\n\n"
                    f"Ism: {d['full_name']}\nTelefon: {d['phone']}\nHudud: {text}"
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Adminga kombayn xabarini yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def handle_combine_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, owner_id = query.data.split(":")
    owner_id = int(owner_id)
    owner = db.get_combine_owner_by_id(owner_id)
    if not owner:
        await query.edit_message_text("Kombayn egasi topilmadi.")
        return

    telegram_id = owner[1]
    full_name = owner[2]

    if action == "approve_combine":
        db.set_combine_owner_status(owner_id, "tasdiqlangan")
        await query.edit_message_text(f"✅ Tasdiqlandi: {full_name}")
        try:
            await context.bot.send_message(
                chat_id=telegram_id,
                text="🎉 Tabriklaymiz! Kombayn egasi sifatida tasdiqlandingiz.",
                reply_markup=combine_owner_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Kombayn egasiga xabar yuborishda xatolik: {e}")
    else:
        db.set_combine_owner_status(owner_id, "rad etilgan")
        await query.edit_message_text(f"❌ Rad etildi: {full_name}")
        try:
            await context.bot.send_message(chat_id=telegram_id, text="Afsuski, arizangiz rad etildi.")
        except Exception as e:
            logger.error(f"Kombayn egasiga xabar yuborishda xatolik: {e}")


async def combine_owner_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner = db.get_combine_owner_by_telegram_id(update.effective_user.id)
    if not owner:
        await update.message.reply_text(
            "Bu bo'lim faqat ro'yxatdan o'tgan kombayn egalari uchun. Avval \"📝 Ro'yxatdan o'tish\" bo'limidan "
            "\"🚜 Kombayn egalari\" tugmasini bosing.",
            reply_markup=main_menu_keyboard()
        )
        return None
    if owner[5] != "tasdiqlangan":
        db.set_combine_owner_status(owner[0], "tasdiqlangan")
        owner = db.get_combine_owner_by_telegram_id(update.effective_user.id)
    return owner


async def combine_add_listing_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner = await combine_owner_guard(update, context)
    if not owner:
        return ConversationHandler.END
    context.user_data["combine_listing"] = {"owner_id": owner[0], "region": owner[4]}
    await update.message.reply_text(
        "Kombayn modeli/turi qanday? (masalan: Case IH, John Deere, Don-1500)",
        reply_markup=cancel_keyboard()
    )
    return CL_MODEL


async def cl_enter_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["combine_listing"]["model"] = update.message.text
    await update.message.reply_text("1 gektar uchun o'rish narxini kiriting (so'mda, masalan: 250000):")
    return CL_PRICE


async def cl_enter_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text.replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, faqat raqam kiriting.")
        return CL_PRICE
    context.user_data["combine_listing"]["price"] = price
    await update.message.reply_text(
        "Qayerda xizmat ko'rsatasiz?",
        reply_markup=ReplyKeyboardMarkup(
            [["🏞 Vodiy bo'ylab (Andijon/Farg'ona/Namangan)"], ["🇺🇿 Respublika bo'ylab"], ["❌ Bekor qilish"]],
            resize_keyboard=True
        )
    )
    return CL_COVERAGE


async def cl_choose_coverage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Respublika" in text:
        coverage = "respublika"
    elif "Vodiy" in text:
        coverage = "vodiy"
    else:
        await update.message.reply_text("Iltimos, tugmalardan birini tanlang.")
        return CL_COVERAGE
    context.user_data["combine_listing"]["coverage"] = coverage
    await update.message.reply_text(
        "📷 Texnikangiz rasmini yuboring (xaridorlar ko'rishi uchun).\n"
        "Rasm yubormoqchi bo'lmasangiz \"-\" deb yozing.",
        reply_markup=cancel_keyboard()
    )
    return CL_PHOTO


async def cl_enter_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file_id = None
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.strip() == "-":
        photo_file_id = None
    else:
        await update.message.reply_text("Iltimos, rasm yuboring yoki \"-\" deb yozing.")
        return CL_PHOTO

    context.user_data["combine_listing"]["photo_file_id"] = photo_file_id
    await update.message.reply_text("Qaysi manzilda ishlaysiz? (tuman, mahalla):")
    return CL_ADDRESS


async def cl_enter_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cl = context.user_data["combine_listing"]
    address = update.message.text
    db.add_combine_listing(
        cl["owner_id"], cl["model"], cl["price"], address, cl["region"],
        photo_file_id=cl.get("photo_file_id"), coverage=cl.get("coverage", "vodiy")
    )
    coverage_label = "Respublika bo'ylab" if cl.get("coverage") == "respublika" else "Vodiy bo'ylab"
    await update.message.reply_text(
        f"✅ Qo'shildi: {cl['model']} — {cl['price']:,} so'm/gektar ({coverage_label})".replace(",", " "),
        reply_markup=combine_owner_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END


async def combine_my_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner = await combine_owner_guard(update, context)
    if not owner:
        return
    listings = db.get_combine_listings_for_owner(owner[0])
    if not listings:
        await update.message.reply_text("Sizda hali texnika e'lonlari yo'q.")
        return
    await update.message.reply_text("🚜 <b>Sizning texnikangiz:</b>", parse_mode="HTML")
    for lst_id, model, price, photo_id, address, region, active, coverage in listings:
        status_note = "faol" if active else "faol emas"
        photo_note = " 📷" if photo_id else ""
        coverage_label = "Respublika bo'ylab" if coverage == "respublika" else "Vodiy bo'ylab"
        text = f"• {model} — {fmt_money(price)} so'm/gektar | {coverage_label} | {region} | {status_note}{photo_note}"
        await update.message.reply_text(text)


# ----------------- Kombayn egasi: silos joyi elonini berish -----------------

async def combine_silos_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner = await combine_owner_guard(update, context)
    if not owner:
        return ConversationHandler.END
    context.user_data["combine_silos"] = {"owner_id": owner[0], "region": owner[4]}
    await update.message.reply_text(
        "🌾 Silos joyi haqida e'lon berish — sizda hozir o'rilgan/o'rilayotgan silos bo'lsa, "
        "shu haqda e'lon berishingiz mumkin (bu faqat reklama, botda sotuv bo'lmaydi).\n\n"
        "Necha gektar joy/silosingiz borligini va 1 kg narxini BITTA xabarda, alohida qatorlarda kiriting:\n\n"
        "Masalan:\n"
        "10\n"
        "500",
        reply_markup=cancel_keyboard()
    )
    return CS_QUANTITY


async def cs_enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [l.strip() for l in update.message.text.split("\n") if l.strip()]
    if len(lines) != 2:
        await update.message.reply_text(
            "Iltimos, aynan 2 qatorda yozing: gektar, keyin 1 kg narxi.\nMasalan:\n10\n500"
        )
        return CS_QUANTITY
    try:
        quantity = float(lines[0].replace(",", "."))
        price = int(lines[1].replace(" ", ""))
        if quantity <= 0 or price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Raqamlar noto'g'ri. Iltimos, qaytadan urinib ko'ring.\nMasalan:\n10\n500"
        )
        return CS_QUANTITY
    context.user_data["combine_silos"]["quantity"] = quantity
    context.user_data["combine_silos"]["price"] = price
    await update.message.reply_text(
        "📷 Silos/dala rasmini yuboring (xaridorlar ko'rishi uchun).\n"
        "Rasm yubormoqchi bo'lmasangiz \"-\" deb yozing.",
        reply_markup=cancel_keyboard()
    )
    return CS_PHOTO


async def cs_enter_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_file_id = None
    if update.message.photo:
        photo_file_id = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.strip() == "-":
        photo_file_id = None
    else:
        await update.message.reply_text("Iltimos, rasm yuboring yoki \"-\" deb yozing.")
        return CS_PHOTO
    context.user_data["combine_silos"]["photo_file_id"] = photo_file_id
    await update.message.reply_text(
        "Aniq manzilni va sifat haqida qisqa izohni kiriting (alohida qatorlarda):\n\n"
        "Masalan:\n"
        "Chust tumani\n"
        "Quruq, yangi o'rilgan\n\n"
        "(Izoh yozmasangiz, faqat manzilni kiriting.)"
    )
    return CS_ADDRESS


async def cs_enter_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [l.strip() for l in update.message.text.split("\n") if l.strip()]
    address = lines[0] if lines else update.message.text.strip()
    description = "\n".join(lines[1:]) if len(lines) > 1 else None
    context.user_data["combine_silos"]["address"] = address
    context.user_data["combine_silos"]["description"] = description
    location_kb = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📍 Joylashuvni yuborish", request_location=True)],
            ["🗺 Hududlarni o'zim tanlayman"],
            ["⏭ O'tkazib yuborish"],
        ],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "Xabar qayerdagi haydovchilarga borishini belgilang:\n\n"
        "📍 Joylashuvni yuborish — faqat 25-30 km atrofdagilarga\n"
        "🗺 Hududlarni o'zim tanlayman — o'zingiz istagan viloyatlarga\n"
        "⏭ O'tkazib yuborish — avtomatik (butun vodiy bo'ylab)",
        reply_markup=location_kb
    )
    return CS_LOCATION


async def cs_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    has_location = update.message.location is not None
    is_skip = update.message.text == "⏭ O'tkazib yuborish"
    is_region_select = update.message.text == "🗺 Hududlarni o'zim tanlayman"

    if is_region_select:
        context.user_data["posting_flow"] = "cs"
        context.user_data["selected_tumans"] = set()
        await update.message.reply_text(
            "Qo'shni tumanlarni tanlaysiz — avval viloyatni tanlang, so'ng o'sha viloyatning "
            "tumanlarini belgilaysiz. Kerak bo'lsa, boshqa viloyatdan ham tuman qo'shishingiz mumkin.",
            reply_markup=ReplyKeyboardRemove()
        )
        await update.message.reply_text(
            "Qaysi viloyat?", reply_markup=build_viloyat_picker_keyboard()
        )
        return CS_REGIONS

    if not has_location and not is_skip:
        await update.message.reply_text("Iltimos, variantlardan birini tanlang.")
        return CS_LOCATION

    latitude = update.message.location.latitude if has_location else None
    longitude = update.message.location.longitude if has_location else None
    await cs_finalize(context, update.effective_user.id, update.effective_chat.id, latitude=latitude, longitude=longitude)
    context.user_data.clear()
    return ConversationHandler.END


async def cs_finalize(context: ContextTypes.DEFAULT_TYPE, user_telegram_id, chat_id,
                       latitude=None, longitude=None, target_regions=None, target_tumans=None):
    cs = context.user_data["combine_silos"]
    address = cs["address"]

    db.add_combine_silos_listing(
        cs["owner_id"], cs["price"], cs.get("quantity"), address, cs["region"],
        photo_file_id=cs.get("photo_file_id"), latitude=latitude, longitude=longitude,
        description=cs.get("description")
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ Silos eloningiz joylandi: {cs['quantity']} gektar, {cs['price']:,} so'mdan.\n"
            "Bu faqat e'lon — mijozlar buni \"🌾 Silos manbalarini ko'rish\" orqali ko'radi va "
            "sizga to'g'ridan-to'g'ri telefon orqali murojaat qiladi (botda sotuv yo'q)."
        ).replace(",", " "),
        reply_markup=combine_owner_menu_keyboard()
    )

    # Kim xabar olishini aniqlash: 1) ozi tanlagan tumanlar, 2) ozi tanlagan viloyatlar, 3) koordinata, 4) butun vodiy (zaxira)
    owner = db.get_combine_owner_by_telegram_id(user_telegram_id)
    owner_name = owner[2] if owner else "?"
    owner_phone = owner[3] if owner else "?"
    if target_tumans:
        driver_ids = db.get_drivers_by_tumans(target_tumans)
    elif target_regions:
        driver_ids = db.get_drivers_by_regions(target_regions)
    elif latitude is not None and longitude is not None:
        driver_ids = db.get_drivers_near(latitude, longitude, max_km=30)
    else:
        driver_ids = db.get_drivers_by_regions(VALLEY_REGIONS)

    caption = (
        f"🆕 <b>Yangi silos e'loni (kombayn egasidan)!</b>\n\n"
        f"🚜 {fmt_money(cs['quantity'])} gektar — {fmt_money(cs['price'])} so'm/kg\n"
        f"Hudud: {cs['region']}\n"
        f"Manzil: {address}\n"
        f"Kombayn egasi: {owner_name} ({owner_phone})\n\n"
        "Bu faqat ma'lumot — botdan olib bo'lmaydi, to'g'ridan-to'g'ri telefon orqali bog'laning."
    )
    photo_id = cs.get("photo_file_id")
    for drv_tg_id in driver_ids:
        try:
            if photo_id:
                await context.bot.send_photo(chat_id=drv_tg_id, photo=photo_id, caption=caption, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=drv_tg_id, text=caption, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Haydovchi {drv_tg_id} ga silos elonini yuborishda xatolik: {e}")

    context.user_data.clear()


async def combine_my_silos_listings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner = await combine_owner_guard(update, context)
    if not owner:
        return
    listings = db.get_combine_silos_listings_for_owner(owner[0])
    if not listings:
        await update.message.reply_text("Sizda hali silos elonlari yo'q.")
        return
    await update.message.reply_text("🌾 <b>Sizning silos elonlaringiz:</b>", parse_mode="HTML")
    for lst_id, price, qty, photo_id, address, region, active in listings:
        status_note = "faol" if active else "tugagan"
        qty_note = f"{qty} gektar" if qty is not None else "miqdor noma'lum"
        photo_note = " 📷" if photo_id else ""
        text = f"• {fmt_money(price)} so'm/kg — {qty_note} | {region}, {address} | {status_note}{photo_note}"
        await update.message.reply_text(text)


async def admin_combines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    pending = db.get_pending_combine_owners()
    if not pending:
        await update.message.reply_text("Kutilayotgan kombayn egalari yo'q.")
        return

    for owner_id, tg_id, full_name, phone, region in pending:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_combine:{owner_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_combine:{owner_id}"),
        ]])
        await update.message.reply_text(
            f"🚜 {full_name}\nTelefon: {phone}\nHudud: {region}",
            reply_markup=kb
        )


# ----------------- Buyurtma jarayoni (ConversationHandler) -----------------

FODDER_CATEGORIES = {
    "🌾 Silos (naval)": ("Silos", "naval"),
    "📦 Silos (qopli)": ("Silos", "qopli"),
    "🌾 Somon": ("Somon", None),
    "🌾 Beda": ("Beda", None),
}


async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    catalog_items = db.get_all_orderable_catalog_items()

    catalog = {}
    buttons = [[label] for label in FODDER_CATEGORIES.keys()]

    for item_id, category, name, company, price, unit in catalog_items:
        icon = CATALOG_ICONS.get(category, "🛒")
        company_note = f" ({company})" if company else ""
        label = f"{icon} {name}{company_note} — {price:,} so'm/{unit}".replace(",", " ")
        catalog[label] = {
            "type": "catalog", "item_id": item_id, "category": category,
            "product_name": name, "unit": unit, "price": price, "package_type": None
        }
        buttons.append([label])

    buttons.append(["❌ Bekor qilish"])
    context.user_data["catalog"] = catalog

    if update.callback_query:
        await update.callback_query.answer()
        target = update.callback_query.message
    else:
        target = update.message

    await target.reply_text(
        "Qaysi mahsulotni buyurtma qilmoqchisiz?",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return CHOOSE_PRODUCT


async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text in FODDER_CATEGORIES:
        product_name, package_type = FODDER_CATEGORIES[text]
        return await select_best_fodder_match(update, context, product_name, package_type)

    catalog = context.user_data.get("catalog", {})
    if text not in catalog:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return CHOOSE_PRODUCT

    item = catalog[text]
    order = {
        "product_name": item["product_name"], "unit": item["unit"],
        "price": item["price"], "type": item["type"],
        "package_type": item.get("package_type"),
    }
    if item["type"] == "driver_listing":
        order["listing_id"] = item["listing_id"]
        order["driver_id"] = item["driver_id"]
        order["max_quantity"] = item["quantity_available"]
    elif item["type"] == "catalog":
        order["item_id"] = item["item_id"]
        order["category"] = item["category"]
    else:
        order["product_id"] = item["product_id"]

    context.user_data["order"] = order

    await update.message.reply_text(
        f"Nechta {item['unit']} {item['product_name']} kerak? (masalan: 2.5)",
        reply_markup=cancel_keyboard()
    )
    return ENTER_QUANTITY


async def select_best_fodder_match(update: Update, context: ContextTypes.DEFAULT_TYPE, product_name: str, package_type):
    """Mijozga shu mahsulot bo'yicha BARCHA mavjud variantlarni (haydovchi e'lonlari va o'zi
    yetkazib beradigan sotuvchilar) narxi va manzili bilan ko'rsatadi — mijoz o'zi eng yaqin va
    qulayini tanlaydi. Eng arzonidan boshlab tartiblanadi."""
    listings = db.get_active_driver_listings()
    driver_matches = [
        l for l in listings
        if product_name.lower() in l[2].lower() and (package_type is None or l[8] == package_type)
    ]
    direct_matches = db.find_direct_sellers_by_product(product_name, package_type)

    options = []
    for lst_id, drv_id, name, unit, qty, sell_price, region, address, ptype in driver_matches:
        driver = db.get_driver_by_id(drv_id)
        drv_name = driver[2] if driver else "?"
        veh_num = driver[8] if driver else ""
        options.append({
            "source": "driver_listing", "name": name, "unit": unit, "price": sell_price,
            "region": region, "address": address, "qty": qty,
            "contact_name": drv_name, "contact_note": veh_num,
            "listing_id": lst_id, "driver_id": drv_id, "package_type": ptype,
        })

    for sp_id, seller_id, tg_id, shop_name, name, unit, price, qty, region, ptype in direct_matches:
        options.append({
            "source": "static", "name": name, "unit": unit, "price": price,
            "region": region, "address": None, "qty": qty,
            "contact_name": shop_name, "contact_note": "",
            "listing_id": None, "driver_id": None, "package_type": ptype,
        })

    if not options:
        products = db.get_active_products()
        prod_matches = [p for p in products if product_name.lower() in p[1].lower()]
        if prod_matches:
            pid, name, unit, price = prod_matches[0]
            context.user_data["order"] = {
                "product_name": name, "unit": unit, "price": price, "type": "static",
                "package_type": None, "product_id": pid,
            }
            await update.message.reply_text(
                f"Nechta {unit} {name} kerak? (masalan: 2.5)",
                reply_markup=cancel_keyboard()
            )
            return ENTER_QUANTITY

        buttons = [[label] for label in FODDER_CATEGORIES.keys()]
        buttons.append(["❌ Bekor qilish"])
        await update.message.reply_text(
            f"Kechirasiz, hozircha {product_name} mavjud emas. Boshqa mahsulotni tanlang:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
        return CHOOSE_PRODUCT

    options.sort(key=lambda o: o["price"])

    matches = {}
    buttons = []
    for opt in options:
        note = f" ({opt['contact_note']})" if opt["contact_note"] else ""
        label = (
            f"{opt['price']:,} so'm/{opt['unit']} — {opt['region']} — "
            f"{opt['contact_name']}{note}"
        ).replace(",", " ")
        matches[label] = opt
        buttons.append([label])
    buttons.append(["❌ Bekor qilish"])

    context.user_data["fodder_matches"] = matches

    await update.message.reply_text(
        f"{product_name} bo'yicha mavjud takliflar (eng arzonidan boshlab) — "
        "o'zingizga yaqin va qulayini tanlang:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )
    return CHOOSE_SPECIFIC_MATCH


async def choose_specific_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    matches = context.user_data.get("fodder_matches", {})

    if text not in matches:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return CHOOSE_SPECIFIC_MATCH

    opt = matches[text]
    if opt["source"] == "driver_listing":
        order = {
            "product_name": opt["name"], "unit": opt["unit"], "price": opt["price"],
            "type": "driver_listing", "package_type": opt["package_type"],
            "listing_id": opt["listing_id"], "driver_id": opt["driver_id"],
            "max_quantity": opt["qty"],
        }
    else:
        order = {
            "product_name": opt["name"], "unit": opt["unit"], "price": opt["price"],
            "type": "static", "package_type": opt["package_type"], "product_id": None,
        }

    context.user_data["order"] = order
    await update.message.reply_text(
        f"Nechta {opt['unit']} {opt['name']} kerak? (masalan: 2.5)",
        reply_markup=cancel_keyboard()
    )
    return ENTER_QUANTITY


async def enter_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".")
    try:
        qty = float(text)
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to'g'ri son kiriting (masalan: 2.5)")
        return ENTER_QUANTITY

    order = context.user_data["order"]

    if order["type"] == "driver_listing" and qty > order["max_quantity"]:
        await update.message.reply_text(
            f"Kechirasiz, faqat {order['max_quantity']} {order['unit']} mavjud. Kamroq miqdor kiriting."
        )
        return ENTER_QUANTITY

    order["quantity"] = qty

    if order.get("package_type") == "naval":
        await update.message.reply_text(
            "🌾 Bu mahsulot naval (kg) turida — faqat Farg'ona vodiysi bo'ylab yetkazib beriladi.\n"
            "Qaysi hududga kerak?",
            reply_markup=valley_regions_keyboard()
        )
    else:
        await update.message.reply_text(
            "Qaysi viloyatga yetkazib berish kerak?",
            reply_markup=regions_keyboard()
        )
    return ENTER_REGION


async def enter_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    order = context.user_data["order"]
    allowed_regions = VALLEY_REGIONS if order.get("package_type") == "naval" else REGIONS

    if text not in allowed_regions:
        await update.message.reply_text("Iltimos, ro'yxatdan tanlang.")
        return ENTER_REGION

    order["region"] = text
    await update.message.reply_text(
        "Aniq manzilingizni kiriting (tuman, mahalla, ko'cha):",
        reply_markup=cancel_keyboard()
    )
    return ENTER_ADDRESS


async def enter_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["address"] = update.message.text
    await update.message.reply_text(
        "Telefon raqamingizni yuboring:",
        reply_markup=phone_keyboard()
    )
    return ENTER_PHONE


async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text

    context.user_data["order"]["phone"] = phone
    order = context.user_data["order"]
    total = round(order["quantity"] * order["price"])
    order["total_price"] = total

    summary = (
        "📝 <b>Buyurtmangizni tasdiqlang:</b>\n\n"
        f"Mahsulot: {order['product_name']}\n"
        f"Miqdor: {order['quantity']} {order['unit']}\n"
        f"Narxi: {fmt_money(order['price'])} so'm/{order['unit']}\n"
        f"Jami: <b>{fmt_money(total)} so'm</b>\n"
        f"Hudud: {order['region']}\n"
        f"Manzil: {order['address']}\n"
        f"Telefon: {phone}\n\n"
        "To'g'rimi?"
    )

    await update.message.reply_text(
        summary,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([["✅ Tasdiqlash"], ["❌ Bekor qilish"]], resize_keyboard=True)
    )
    return CONFIRM


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != "✅ Tasdiqlash":
        return await cancel(update, context)

    order = context.user_data["order"]
    user = update.effective_user

    db.get_or_create_user(user.id)
    is_first_order = not db.has_completed_order(user.id)
    user_record = db.get_user(user.id)

    is_driver_order = order["type"] in ("driver_listing", "driver_silos")
    is_qopli_listing_order = order["type"] == "qopli_listing"

    order_id = db.create_order(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name,
        phone=order["phone"],
        product_name=order["product_name"],
        quantity=order["quantity"],
        unit=order["unit"],
        price=order["price"],
        total_price=order["total_price"],
        region=order["region"],
        address=order["address"],
        driver_id=order.get("driver_id") if is_driver_order else None,
    )

    if is_driver_order:
        if order["type"] == "driver_silos":
            db.reduce_driver_silos_quantity(order["listing_id"], order["quantity"])
        else:
            db.reduce_driver_listing_quantity(order["listing_id"], order["quantity"])
    elif is_qopli_listing_order:
        db.reduce_seller_product_quantity(order["sp_id"], order["quantity"])

    confirm_text = (
        f"✅ Buyurtmangiz qabul qilindi! Raqami: #{order_id}\n\n"
        "Tez orada operator siz bilan bog'lanadi. Rahmat! 🙏"
    )

    await update.message.reply_text(confirm_text, reply_markup=main_menu_keyboard())

    # Referal bildirishnomasi: agar bu mijozning birinchi buyurtmasi bo'lsa va u taklif qilingan bo'lsa
    if is_first_order and user_record and user_record[1] and not user_record[3]:
        referrer_id = user_record[1]
        db.mark_referral_rewarded(user.id)
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text="🎉 Sizning do'stingiz birinchi buyurtmasini berdi!"
            )
        except Exception as e:
            logger.error(f"Referal xabarini yuborishda xatolik: {e}")

    # Adminga xabar yuborish
    if ADMIN_CHAT_ID:
        admin_text = (
            f"🆕 <b>Yangi buyurtma #{order_id}</b>\n\n"
            f"Mijoz: {user.full_name} (@{user.username or '—'})\n"
            f"Mahsulot: {order['product_name']} — {order['quantity']} {order['unit']}\n"
            f"Jami: {fmt_money(order['total_price'])} so'm\n"
            f"Hudud: {order['region']}\n"
            f"Manzil: {order['address']}\n"
            f"Telefon: {order['phone']}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Adminga xabar yuborishda xatolik: {e}")

    if is_driver_order:
        # Bu buyurtma to'g'ridan-to'g'ri haydovchining o'z e'loniga tegishli — faqat o'shanga xabar boradi
        driver = db.get_driver_by_id(order["driver_id"])
        if driver:
            driver_tg_id = driver[1]
            try:
                await context.bot.send_message(
                    chat_id=driver_tg_id,
                    text=(
                        f"🆕 <b>Yangi buyurtma #{order_id} (sizning e'loningizga)</b>\n\n"
                        f"Mahsulot: {order['product_name']} — {order['quantity']} {order['unit']}\n"
                        f"Sotish narxi: {fmt_money(order['price'])} so'm/{order['unit']}\n"
                        f"Jami: {fmt_money(order['total_price'])} so'm\n"
                        f"Manzil: {order['region']}, {order['address']}\n"
                        f"Mijoz telefoni: {order['phone']}"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Haydovchiga xabar yuborishda xatolik: {e}")
    elif is_qopli_listing_order:
        # Bu buyurtma to'g'ridan-to'g'ri sotuvchining o'z e'loniga tegishli — faqat o'shanga xabar boradi
        seller = db.get_seller_by_id(order["seller_id"])
        seller_tg_id = seller[1] if seller else None
        if seller_tg_id:
            try:
                await context.bot.send_message(
                    chat_id=seller_tg_id,
                    text=(
                        f"🆕 <b>Yangi buyurtma #{order_id} (sizning e'loningizga)</b>\n\n"
                        f"Mahsulot: {order['product_name']} — {order['quantity']} {order['unit']}\n"
                        f"Narxi: {fmt_money(order['price'])} so'm/{order['unit']}\n"
                        f"Jami: {fmt_money(order['total_price'])} so'm\n"
                        f"Manzil: {order['region']}, {order['address']}\n"
                        f"Mijoz telefoni: {order['phone']}"
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Sotuvchiga xabar yuborishda xatolik: {e}")
    elif order["type"] == "catalog":
        # Urug', preparat, biostimulyator, o'g'it — bevosita admin orqali bajariladi, sotuvchi qidirilmaydi
        pass
    else:
        # Shu hududda mos mahsulotni sotadigan (o'zi yetkazib beradigan) sotuvchilarga xabar berish
        matching_sellers = db.find_sellers_by_region_and_product(order["region"], order["product_name"])
        for seller_id, seller_tg_id, shop_name, seller_phone, seller_price, seller_qty, delivers_self, vehicle_type, capacity_tons in matching_sellers:
            delivery_note = ""
            if delivers_self and capacity_tons and capacity_tons >= order["quantity"]:
                delivery_note = f"\n🚛 Siz o'zingiz ({vehicle_type}, {capacity_tons} tonna) yetkazib bera olasiz."
            seller_text = (
                f"🆕 <b>Yangi buyurtma #{order_id} (sizning hududingizda)</b>\n\n"
                f"Mahsulot: {order['product_name']} — {order['quantity']} {order['unit']}\n"
                f"Hudud: {order['region']}\n"
                f"Manzil: {order['address']}\n"
                f"Mijoz telefoni: {order['phone']}\n\n"
                f"Sizda mavjud: {seller_qty} {order['unit']}{delivery_note}"
            )
            try:
                await context.bot.send_message(chat_id=seller_tg_id, text=seller_text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Sotuvchi {seller_id} ga xabar yuborishda xatolik: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bekor qilindi. Bosh menyuga qaytdingiz.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


# ----------------- Admin buyruqlari -----------------

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    orders = db.get_all_orders(15)
    if not orders:
        await update.message.reply_text("Hali buyurtmalar yo'q.")
        return

    text = "📋 <b>So'nggi 15 ta buyurtma:</b>\n\n"
    for oid, name, phone, product, qty, unit, total, region, address, status, created in orders:
        text += (
            f"#{oid} | {status} | {created}\n"
            f"{name} | {phone}\n"
            f"{product} — {qty} {unit} — {fmt_money(total)} so'm\n"
            f"{region}, {address}\n\n"
        )

    # Telegram xabar uzunligi cheklangani uchun bo'lib yuboramiz
    for i in range(0, len(text), 3500):
        await update.message.reply_text(text[i:i+3500], parse_mode="HTML")


async def admin_sellers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    pending = db.get_pending_sellers()
    if not pending:
        await update.message.reply_text("Kutilayotgan sotuvchilar yo'q.")
        return

    for seller_id, tg_id, shop_name, phone, region in pending:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_seller:{seller_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_seller:{seller_id}"),
        ]])
        await update.message.reply_text(
            f"🏪 {shop_name}\nTelefon: {phone}\nHudud: {region}",
            reply_markup=kb
        )


async def admin_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    pending = db.get_pending_drivers()
    if not pending:
        await update.message.reply_text("Kutilayotgan haydovchilar yo'q.")
        return

    for driver_id, tg_id, full_name, phone, vehicle_type, capacity, region, vehicle_number in pending:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_driver:{driver_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_driver:{driver_id}"),
        ]])
        await update.message.reply_text(
            f"🚚 {full_name}\nTelefon: {phone}\nMashina: {vehicle_type} ({vehicle_number}, {capacity} tonna)\nHudud: {region}",
            reply_markup=kb
        )


async def admin_unpaid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return

    rows = db.get_all_unpaid_transactions()
    if not rows:
        await update.message.reply_text("Hozircha to'lanmagan tranzaksiyalar yo'q. 🎉")
        return

    for listing_id, farmer_name, driver_name, vehicle_number, product_name, qty, unit, payment, created_at in rows:
        days_passed = None
        if created_at:
            try:
                days_passed = (datetime.now() - datetime.strptime(created_at, "%Y-%m-%d %H:%M")).days
            except ValueError:
                pass
        urgency = " 🔴" if days_passed is not None and days_passed >= 3 else ""

        text = (
            f"Fermer: {farmer_name}\n"
            f"Haydovchi: {driver_name} ({vehicle_number or '—'})\n"
            f"{product_name} — {qty} {unit}\n"
            f"Summa: {payment:,} so'm{urgency}\n"
            f"Sana: {created_at}"
            + (f" ({days_passed} kun o'tgan)" if days_passed is not None else "")
        ).replace(",", " ")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Pulni oldim (admin)", callback_data=f"confirm_payment:{listing_id}")
        ]])
        await update.message.reply_text(text, reply_markup=kb)


# ----------------- Botni ishga tushirish -----------------

async def run_cleanup_once(bot):
    """Bitta safar tozalashni bajaradi va agar biror narsa ochirilgan bolsa, adminga xabar beradi."""
    counts = db.cleanup_old_listings(days=2)
    total = sum(counts.values())
    if total > 0:
        logger.info(f"Avtomatik tozalash: {total} ta eski e'lon o'chirildi ({counts})")
        if ADMIN_CHAT_ID:
            try:
                await bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=(
                        f"🗑 Avtomatik tozalash: {total} ta 2 kundan eski e'lon o'chirildi.\n"
                        f"Fermer: {counts['seller_products']}, Haydovchi: {counts['driver_silos']}, "
                        f"Kombayn texnika: {counts['combine_tech']}, Kombayn silos: {counts['combine_silos']}"
                    )
                )
            except Exception as e:
                logger.error(f"Adminga tozalash xabarini yuborishda xatolik: {e}")


async def periodic_cleanup_loop(app):
    """APScheduler/JobQueue'ga bog'liq bo'lmagan, sof asyncio asosidagi doimiy tsikl —
    har 24 soatda bir marta ishga tushib, 2 kundan eski e'lonlarni avtomatik o'chiradi.
    Bu usul hech qanday qo'shimcha kutubxona talab qilmaydi, shu sababli har doim ishlaydi."""
    await asyncio.sleep(60)  # bot ishga tushgandan 1 daqiqa keyin birinchi tekshiruv
    while True:
        try:
            await run_cleanup_once(app.bot)
        except Exception as e:
            logger.error(f"Avtomatik tozalash tsiklida xatolik: {e}")
        await asyncio.sleep(86400)  # keyingi tekshiruv — 24 soatdan keyin


async def post_init(app):
    """Bot ishga tushgandan keyin avtomatik chaqiriladi — fon tozalash tsiklini ishga tushiradi."""
    asyncio.create_task(periodic_cleanup_loop(app))


def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi! .env faylini tekshiring.")

    db.init_db()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    order_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(order_start, pattern="^catalog_order_start$"),
            CallbackQueryHandler(order_driver_silos_start, pattern="^order_driver_silos:"),
            CallbackQueryHandler(order_qopli_start, pattern="^order_qopli:"),
        ],
        states={
            CHOOSE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_product)],
            CHOOSE_SPECIFIC_MATCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_specific_match)],
            ENTER_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_quantity)],
            ENTER_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_region)],
            ENTER_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_address)],
            ENTER_PHONE: [MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, enter_phone)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    seller_register_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📦 Qopli sotuvchilar$"), seller_register_start),
            MessageHandler(filters.Regex("^🌾 Fermer va dehqonlar$"), farmer_register_start),
        ],
        states={
            SELLER_NAME: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_enter_name),
            ],
            SELLER_PHONE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, seller_enter_phone),
            ],
            SELLER_REGION: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_enter_region),
            ],
            SELLER_HAS_VEHICLE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_has_vehicle),
            ],
            SELLER_VEHICLE_TYPE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_vehicle_type),
            ],
            SELLER_CAPACITY: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, seller_capacity),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    seller_product_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Mahsulot qo'shish$"), seller_add_product_start)],
        states={
            SP_NAME: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sp_enter_name),
            ],
            SP_TYPE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sp_choose_type),
            ],
            SP_PRICE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sp_enter_price),
            ],
            SP_PHOTO: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, sp_enter_photo),
            ],
            SP_FREE_TEXT: [
                MessageHandler(filters.Regex("^📊 Mening jadvalim$"), farmer_weight_exit_to_table),
                MessageHandler(filters.Regex("^⬅️ Bosh menyu$"), farmer_weight_exit_to_main),
                MessageHandler(filters.Regex("^📝 Ro'yxatdan o'tish$"), farmer_weight_exit_to_registration),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sp_free_text_value),
            ],
            SP_ADDRESS: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sp_enter_address),
            ],
            SP_LOCATION: [MessageHandler((filters.LOCATION | filters.TEXT) & ~filters.COMMAND, sp_finish)],
            SP_REGIONS: [
                CallbackQueryHandler(handle_viloyat_pick, pattern="^pick_viloyat:"),
                CallbackQueryHandler(handle_regions_done, pattern="^regions_done$"),
                CallbackQueryHandler(handle_regions_cancel, pattern="^regions_cancel$"),
            ],
            SP_TUMANS: [
                CallbackQueryHandler(handle_tuman_toggle, pattern="^toggle_tuman:"),
                CallbackQueryHandler(handle_add_more_viloyat, pattern="^add_more_viloyat$"),
                CallbackQueryHandler(handle_regions_done, pattern="^regions_done$"),
                CallbackQueryHandler(handle_regions_cancel, pattern="^regions_cancel$"),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    driver_register_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚚 Haydovchilar$"), driver_register_start)],
        states={
            DRV_NAME: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, driver_enter_name),
            ],
            DRV_PHONE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, driver_enter_phone),
            ],
            DRV_VEHICLE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, driver_enter_vehicle),
            ],
            DRV_NUMBER: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, driver_enter_number),
            ],
            DRV_CAPACITY: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, driver_enter_capacity),
            ],
            DRV_REGION: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, driver_enter_region),
            ],
            DRV_TUMAN: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, driver_enter_tuman),
            ],
            DRV_LOCATION: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.LOCATION | filters.TEXT) & ~filters.COMMAND, driver_enter_location),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    claim_load_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(claim_load_start, pattern="^claim_load:")],
        states={
            CLAIM_SET_TONNAGE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, claim_load_set_tonnage),
            ],
            CLAIM_SET_RESALE_QTY: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, claim_load_set_resale_qty),
            ],
            CLAIM_SET_PRICE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, claim_load_set_price),
            ],
            CLAIM_SET_PHOTO: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, claim_load_set_photo),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    enter_weight_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(enter_weight_start, pattern="^enter_weight:")],
        states={
            ENTER_WEIGHT_PHOTO: [MessageHandler(filters.PHOTO, enter_weight_photo)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    farmer_weight_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(farmer_weight_start, pattern="^farmer_weight:")],
        states={
            FARMER_ENTER_WEIGHT: [
                MessageHandler(filters.Regex("^📊 Mening jadvalim$"), farmer_weight_exit_to_table),
                MessageHandler(filters.Regex("^⬅️ Bosh menyu$"), farmer_weight_exit_to_main),
                MessageHandler(filters.Regex("^📝 Ro'yxatdan o'tish$"), farmer_weight_exit_to_registration),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, farmer_weight_value),
            ],
            FARMER_ENTER_PRICE: [
                MessageHandler(filters.Regex("^📊 Mening jadvalim$"), farmer_weight_exit_to_table),
                MessageHandler(filters.Regex("^⬅️ Bosh menyu$"), farmer_weight_exit_to_main),
                MessageHandler(filters.Regex("^📝 Ro'yxatdan o'tish$"), farmer_weight_exit_to_registration),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, farmer_weight_price),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    ml_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Jadvalga yozish$"), ml_start)],
        states={
            ML_VEHICLE: [
                MessageHandler(filters.Regex("^📊 Mening jadvalim$"), farmer_weight_exit_to_table),
                MessageHandler(filters.Regex("^⬅️ Bosh menyu$"), farmer_weight_exit_to_main),
                MessageHandler(filters.Regex("^📝 Ro'yxatdan o'tish$"), farmer_weight_exit_to_registration),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ml_enter_combined),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    manual_weight_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(manual_weight_start, pattern="^manual_weight:")],
        states={
            ML_TONNA_ENTRY: [
                MessageHandler(filters.Regex("^📊 Mening jadvalim$"), farmer_weight_exit_to_table),
                MessageHandler(filters.Regex("^⬅️ Bosh menyu$"), farmer_weight_exit_to_main),
                MessageHandler(filters.Regex("^📝 Ro'yxatdan o'tish$"), farmer_weight_exit_to_registration),
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_weight_value),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    catalog_add_conv = ConversationHandler(
        entry_points=[CommandHandler("yangimalumot", catalog_add_start)],
        states={
            CAT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, catalog_choose_category)],
            CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, catalog_enter_name)],
            CAT_COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, catalog_enter_company)],
            CAT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, catalog_enter_desc)],
            CAT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, catalog_enter_price)],
            CAT_UNIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, catalog_enter_unit)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    combine_register_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚜 Kombayn egalari$"), combine_owner_register_start)],
        states={
            COMBINE_NAME: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, combine_enter_name),
            ],
            COMBINE_PHONE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.CONTACT | filters.TEXT) & ~filters.COMMAND, combine_enter_phone),
            ],
            COMBINE_REGION: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, combine_enter_region),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    combine_listing_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Texnika qo'shish$"), combine_add_listing_start)],
        states={
            CL_MODEL: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_enter_model),
            ],
            CL_PRICE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_enter_price),
            ],
            CL_COVERAGE: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_choose_coverage),
            ],
            CL_PHOTO: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, cl_enter_photo),
            ],
            CL_ADDRESS: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cl_enter_address),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    combine_silos_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🌾 Silos joyi e'lon qilish$"), combine_silos_start)],
        states={
            CS_QUANTITY: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cs_enter_quantity),
            ],
            CS_PHOTO: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, cs_enter_photo),
            ],
            CS_ADDRESS: [
                MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cs_enter_address),
            ],
            CS_LOCATION: [MessageHandler((filters.LOCATION | filters.TEXT) & ~filters.COMMAND, cs_finish)],
            CS_REGIONS: [
                CallbackQueryHandler(handle_viloyat_pick, pattern="^pick_viloyat:"),
                CallbackQueryHandler(handle_regions_done, pattern="^regions_done$"),
                CallbackQueryHandler(handle_regions_cancel, pattern="^regions_cancel$"),
            ],
            CS_TUMANS: [
                CallbackQueryHandler(handle_tuman_toggle, pattern="^toggle_tuman:"),
                CallbackQueryHandler(handle_add_more_viloyat, pattern="^add_more_viloyat$"),
                CallbackQueryHandler(handle_regions_done, pattern="^regions_done$"),
                CallbackQueryHandler(handle_regions_cancel, pattern="^regions_cancel$"),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    driver_silos_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚛 Mashinada sotish e'lonim$"), ds_start)],
        states={
            DS_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ds_enter_price)],
            DS_PHOTO: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, ds_enter_photo)],
            DS_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ds_enter_address)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Bekor qilish$"), cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", admin_orders))
    app.add_handler(CommandHandler("sellers", admin_sellers))
    app.add_handler(CommandHandler("drivers", admin_drivers))
    app.add_handler(CommandHandler("tolovlar", admin_unpaid))
    app.add_handler(CommandHandler("elonlar", admin_listings))
    app.add_handler(CommandHandler("kombaynlar", admin_combines))
    app.add_handler(order_conv)
    app.add_handler(seller_register_conv)
    app.add_handler(seller_product_conv)
    app.add_handler(driver_register_conv)
    app.add_handler(combine_register_conv)
    app.add_handler(combine_listing_conv)
    app.add_handler(combine_silos_conv)
    app.add_handler(driver_silos_conv)
    app.add_handler(claim_load_conv)
    app.add_handler(enter_weight_conv)
    app.add_handler(farmer_weight_conv)
    app.add_handler(ml_conv)
    app.add_handler(manual_weight_conv)
    app.add_handler(MessageHandler(filters.Regex("^✅ Pul oldim \\(belgilash\\)$"), mark_paid_list))
    app.add_handler(CallbackQueryHandler(mark_paid_bot_callback, pattern="^mark_paid_bot:"))
    app.add_handler(CallbackQueryHandler(mark_paid_manual_callback, pattern="^mark_paid_manual:"))
    app.add_handler(CallbackQueryHandler(delete_seller_product_callback, pattern="^del_sp:"))
    app.add_handler(CallbackQueryHandler(delete_driver_silos_callback, pattern="^del_ds:"))
    app.add_handler(CallbackQueryHandler(delete_combine_listing_callback, pattern="^del_cl:"))
    app.add_handler(CallbackQueryHandler(delete_combine_silos_callback, pattern="^del_csl:"))
    app.add_handler(CallbackQueryHandler(browse_region_callback, pattern="^browse_region:"))
    app.add_handler(catalog_add_conv)
    app.add_handler(CallbackQueryHandler(handle_seller_approval, pattern="^(approve_seller|reject_seller):"))
    app.add_handler(CallbackQueryHandler(handle_driver_approval, pattern="^(approve_driver|reject_driver):"))
    app.add_handler(CallbackQueryHandler(handle_combine_approval, pattern="^(approve_combine|reject_combine):"))
    app.add_handler(CallbackQueryHandler(handle_weight_confirmation, pattern="^confirm_weight:"))
    app.add_handler(CallbackQueryHandler(handle_payment_confirmation, pattern="^confirm_payment:"))
    app.add_handler(MessageHandler(filters.Regex("^📝 Ro'yxatdan o'tish$"), registration_menu_open))
    app.add_handler(MessageHandler(filters.Regex("^📢 E'lon berish$"), elon_berish_router))
    app.add_handler(MessageHandler(filters.Regex("^☎️ Aloqa$"), contact_info))
    app.add_handler(MessageHandler(filters.Regex("^📦 Mening mahsulotlarim$"), seller_my_products))
    app.add_handler(MessageHandler(filters.Regex("^📋 Menga tushgan buyurtmalar$"), seller_my_orders))
    app.add_handler(MessageHandler(filters.Regex("^📊 Mening jadvalim$"), seller_transaction_report))
    app.add_handler(MessageHandler(filters.Regex("^⚖️ Miqdor kiritish$"), farmer_weight_list))
    app.add_handler(MessageHandler(filters.Regex("^📦 Yangi yuklar$"), browse_loads))
    app.add_handler(MessageHandler(filters.Regex("^📋 Mening e'lonlarim$"), my_listings))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Bosh menyu$"), back_to_main))
    app.add_handler(MessageHandler(filters.Regex("^🎁 Do'stni taklif qilish$"), referral_info))
    app.add_handler(MessageHandler(filters.Regex("^🌱 Urug'lar$"), show_seeds))
    app.add_handler(MessageHandler(filters.Regex("^💊 Vetapteka$"), vetapteka_open))
    app.add_handler(MessageHandler(filters.Regex("^💉 Preparatlar$"), show_preparats))
    app.add_handler(MessageHandler(filters.Regex("^🌿 Biostimulyatorlar$"), show_biostimulyators))
    app.add_handler(MessageHandler(filters.Regex("^💉 Preparatlar$"), show_preparats))
    app.add_handler(MessageHandler(filters.Regex("^🌿 Biostimulyatorlar$"), show_biostimulyators))
    app.add_handler(MessageHandler(filters.Regex("^🧪 Mineral o'g'itlar$"), show_fertilizers))
    app.add_handler(MessageHandler(filters.Regex("^🚜 Kombaynlar$"), combine_menu_open))
    app.add_handler(MessageHandler(filters.Regex("^🌾 Fermerlar ulgurji \\(naval\\)$"), browse_loads))
    app.add_handler(MessageHandler(filters.Regex("^🚛 Mashinada sotiladi$"), browse_driver_silos))
    app.add_handler(MessageHandler(filters.Regex("^📦 Qopli silos$"), browse_qopli_silos))
    app.add_handler(MessageHandler(filters.Regex("^📋 Mening savdo elonlarim$"), driver_my_silos_listings))
    app.add_handler(MessageHandler(filters.Regex("^🔍 Kombaynlarni ko'rish$"), browse_combines))
    app.add_handler(MessageHandler(filters.Regex("^🌾 Silos manbalarini ko'rish$"), browse_loads))
    app.add_handler(MessageHandler(filters.Regex("^📋 Mening texnikam$"), combine_my_listings))
    app.add_handler(MessageHandler(filters.Regex("^📋 Mening silos elonlarim$"), combine_my_silos_listings))

    # 2 kundan eski elonlarni avtomatik ochirish — post_init orqali (yuqorida) fon rejimida ishga tushadi,
    # hech qanday qoshimcha kutubxona (APScheduler) talab qilmaydi

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
