import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

import database as db
from keyboards import subscribe_keyboard

router = Router(name="user")
logger = logging.getLogger(__name__)

CODE_RE = re.compile(r"^\d{3}$")

# ---------------------------------------------------------- Тексты (UZ) ----

NO_ADS_TEXT = (
    "Assalomu aleykum, hozircha reklama beruvchilar yoq, "
    "agarda sizda kanal yoki botni reklama qilish kerak bolsa, admin @lixuauto"
)

WELCOME_TEXT = (
    "Assalomu aleykum! 🎬\n\n"
    "Film kodini yuboring (3 xonali raqam), men sizga filmni topib beraman.\n"
    "Masalan: 001"
)

SUBSCRIBE_TEXT = (
    "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling, "
    "so'ngra pastdagi \"✅ Tekshirish\" tugmasini bosing 👇"
)

STILL_NOT_SUBSCRIBED_TEXT = (
    "❗️ Siz hali barcha kanallarga obuna bo'lmadingiz. "
    "Obuna bo'lgach, \"✅ Tekshirish\" tugmasini qayta bosing."
)

NOT_FOUND_TEXT = "❌ Bunday kod topilmadi. Kodni tekshirib, qaytadan yuboring."

FALLBACK_TEXT = "Film kodini 3 xonali raqam ko'rinishida yuboring. Masalan: 001"


async def get_missing_channels(bot: Bot, user_id: int):
    """Возвращает список каналов, на которые пользователь ещё не подписан."""
    channels = await db.list_channels()
    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["identifier"], user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception as e:
            # Если бот не может проверить (например, его удалили из канала) —
            # считаем подписку не подтверждённой, чтобы не давать ложный доступ.
            logger.warning(f"Не удалось проверить подписку на {ch['identifier']}: {e}")
            missing.append(ch)
    return missing


@router.message(CommandStart())
async def cmd_start(message: Message):
    await db.add_user(message.from_user.id)

    codes_count = await db.count_codes()
    if codes_count == 0:
        await message.answer(NO_ADS_TEXT)
        return

    missing = await get_missing_channels(message.bot, message.from_user.id)
    if missing:
        await message.answer(SUBSCRIBE_TEXT, reply_markup=subscribe_keyboard(missing))
        return

    await message.answer(WELCOME_TEXT)


@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):
    codes_count = await db.count_codes()
    if codes_count == 0:
        await callback.message.edit_text(NO_ADS_TEXT)
        await callback.answer()
        return

    missing = await get_missing_channels(callback.bot, callback.from_user.id)
    if missing:
        await callback.answer(STILL_NOT_SUBSCRIBED_TEXT, show_alert=True)
        return

    await callback.message.edit_text(WELCOME_TEXT)
    await callback.answer("✅")


@router.message(F.text.regexp(CODE_RE.pattern))
async def handle_code(message: Message):
    await db.add_user(message.from_user.id)

    codes_count = await db.count_codes()
    if codes_count == 0:
        await message.answer(NO_ADS_TEXT)
        return

    missing = await get_missing_channels(message.bot, message.from_user.id)
    if missing:
        await message.answer(SUBSCRIBE_TEXT, reply_markup=subscribe_keyboard(missing))
        return

    row = await db.get_code(message.text)
    if not row:
        await db.bump_stat("failed_searches")
        await message.answer(NOT_FOUND_TEXT)
        return

    await db.bump_stat("successful_searches")
    await db.increment_code_uses(message.text)
    await message.answer_photo(photo=row["photo_file_id"], caption=f"🎬 {row['title']}")


@router.message(F.text)
async def fallback(message: Message):
    await message.answer(FALLBACK_TEXT)
