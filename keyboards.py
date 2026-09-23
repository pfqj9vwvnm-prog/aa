from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def subscribe_keyboard(channels) -> InlineKeyboardMarkup:
    """Кнопки-ссылки на каналы + кнопка проверки подписки."""
    builder = InlineKeyboardBuilder()
    for ch in channels:
        username = ch["username"]
        title = ch["title"] or username or ch["identifier"]
        if username:
            url = f"https://t.me/{username.lstrip('@')}"
        else:
            # Приватный канал без username — ссылка не может быть построена
            # автоматически. См. README про приватные каналы.
            url = "https://t.me"
        builder.button(text=f"📢 {title}", url=url)
    builder.button(text="✅ Tekshirish", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()
