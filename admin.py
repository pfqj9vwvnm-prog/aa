import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

import database as db
from config import ADMIN_IDS
from handlers.user import CODE_RE

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(ADMIN_IDS))

logger = logging.getLogger(__name__)


class AddCodeStates(StatesGroup):
    waiting_code = State()
    waiting_title = State()
    waiting_photo = State()


# --------------------------------------------------------- /addcode ----

@router.message(F.photo, F.caption.regexp(r"(?i)^/addcode(@\w+)?"))
async def addcode_with_photo(message: Message, state: FSMContext):
    """Вариант в одно действие: фото с подписью "/addcode 001 Название"."""
    caption = message.caption or ""
    parts = caption.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply(
            "Формат при отправке с фото:\n"
            "/addcode <3 цифры> <Название фильма>\n\n"
            "Например: /addcode 001 Форсаж 10"
        )
        return

    _, code, title = parts
    if not CODE_RE.match(code):
        await message.reply("Код должен состоять ровно из 3 цифр, например 001.")
        return

    photo_file_id = message.photo[-1].file_id
    created = await db.add_code(code, title, photo_file_id)
    if created:
        await message.reply(f"✅ Код {code} добавлен: «{title}»")
    else:
        await db.update_code(code, title, photo_file_id)
        await message.reply(f"♻️ Код {code} уже существовал — данные обновлены: «{title}»")
    await state.clear()


@router.message(Command("addcode"))
async def addcode_start(message: Message, state: FSMContext, command: CommandObject):
    """Вариант по шагам: /addcode (без фото) запускает мастер добавления."""
    if command.args:
        parts = command.args.split(maxsplit=1)
        if len(parts) == 2 and CODE_RE.match(parts[0]):
            code, title = parts
            await state.update_data(code=code, title=title)
            await state.set_state(AddCodeStates.waiting_photo)
            await message.answer(
                f"Код: {code}\nНазвание: {title}\n\n"
                "Теперь пришлите фото (постер) для этого фильма."
            )
            return
        await message.answer(
            "Формат: /addcode <3 цифры> <Название>\n"
            "Или просто /addcode — и я спрошу всё по шагам."
        )
        return

    await state.set_state(AddCodeStates.waiting_code)
    await message.answer("Введите 3-значный код (например 001):")


@router.message(AddCodeStates.waiting_code)
async def addcode_get_code(message: Message, state: FSMContext):
    code = (message.text or "").strip()
    if not CODE_RE.match(code):
        await message.answer("Код должен состоять ровно из 3 цифр. Попробуйте снова:")
        return
    await state.update_data(code=code)
    await state.set_state(AddCodeStates.waiting_title)
    await message.answer("Теперь введите название фильма:")


@router.message(AddCodeStates.waiting_title)
async def addcode_get_title(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пришлите название фильма текстом:")
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(AddCodeStates.waiting_photo)
    await message.answer("Отлично! Теперь пришлите фото (постер) для этого фильма:")


@router.message(AddCodeStates.waiting_photo, F.photo)
async def addcode_get_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    code, title = data["code"], data["title"]
    photo_file_id = message.photo[-1].file_id

    created = await db.add_code(code, title, photo_file_id)
    await state.clear()
    if created:
        await message.answer(f"✅ Код {code} добавлен: «{title}»")
    else:
        await db.update_code(code, title, photo_file_id)
        await message.answer(f"♻️ Код {code} уже существовал — данные обновлены: «{title}»")


@router.message(AddCodeStates.waiting_photo)
async def addcode_wrong_photo(message: Message):
    await message.answer("Пришлите именно фото (как изображение, не документом).")


@router.message(Command("cancel"), StateFilter(AddCodeStates))
async def cancel_wizard(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.")


# --------------------------------------------------------- /delcode ----

@router.message(Command("delcode"))
async def delcode(message: Message, command: CommandObject):
    code = (command.args or "").strip()
    if not CODE_RE.match(code):
        await message.answer("Формат: /delcode <3 цифры>\nНапример: /delcode 001")
        return

    ok = await db.delete_code(code)
    if ok:
        await message.answer(f"🗑 Код {code} удалён.")
    else:
        await message.answer(f"Код {code} не найден в базе.")


# ----------------------------------------------------------- /stats ----

@router.message(Command("stats"))
async def stats(message: Message):
    users = await db.count_users()
    codes = await db.count_codes()
    channels = await db.list_channels()
    success = await db.get_stat("successful_searches")
    failed = await db.get_stat("failed_searches")
    top = await db.top_codes(5)

    text = (
        "📊 Статистика бота\n\n"
        f"👥 Пользователей: {users}\n"
        f"🎬 Кодов в базе: {codes}\n"
        f"📢 Обязательных каналов: {len(channels)}\n"
        f"✅ Успешных поисков: {success}\n"
        f"❌ Неудачных поисков: {failed}\n"
    )
    if top:
        text += "\n🔝 Топ кодов по популярности:\n"
        for row in top:
            text += f"  {row['code']} — «{row['title']}» ({row['uses']} раз)\n"

    await message.answer(text)


# ---------------------------------------------------------- Каналы ----

@router.message(Command("addch"))
async def addch(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Формат: /addch @username_канала")
        return

    arg = command.args.strip().split()[0]
    identifier = arg if arg.startswith("@") or arg.startswith("-100") else f"@{arg}"

    try:
        chat = await message.bot.get_chat(identifier)
    except Exception as e:
        await message.answer(
            f"Не удалось получить информацию о канале: {e}\n"
            "Проверьте username и убедитесь, что бот добавлен в канал."
        )
        return

    try:
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat.id, me.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                "⚠️ Бот добавлен, но не является администратором этого канала — "
                "проверка подписки может работать нестабильно. Канал всё равно добавлен."
            )
    except Exception as e:
        logger.warning(f"Не удалось проверить права бота в канале {identifier}: {e}")

    username = f"@{chat.username}" if chat.username else None
    ok = await db.add_channel(str(chat.id), username, chat.title)
    if ok:
        await message.answer(f"✅ Канал «{chat.title}» добавлен в обязательные для подписки.")
    else:
        await message.answer("Этот канал уже есть в списке.")


@router.message(Command("delch"))
async def delch(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Формат: /delch @username_канала")
        return

    arg = command.args.strip().split()[0]
    identifier = arg if arg.startswith("@") else f"@{arg}"
    ok = await db.delete_channel(identifier)
    if ok:
        await message.answer(f"🗑 Канал {identifier} удалён из списка.")
    else:
        await message.answer("Канал с таким username не найден в списке.")


@router.message(Command("ch"))
async def list_channels_cmd(message: Message):
    channels = await db.list_channels()
    if not channels:
        await message.answer("Список обязательных каналов пуст.")
        return

    text = "📢 Обязательные каналы:\n\n"
    for ch in channels:
        text += f"• {ch['title']} ({ch['username'] or ch['identifier']})\n"
    await message.answer(text)
