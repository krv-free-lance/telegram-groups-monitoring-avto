from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.classifier import CATEGORY_TITLES, Category
from app.db import Database
from app.userbot import Monitor

HELP = (
    "Бот мониторинга заявок.\n\n"
    "/chats — отслеживаемые группы\n"
    "/add &lt;ссылка или @username&gt; — добавить группу\n"
    "/remove &lt;id&gt; — убрать группу\n"
    "/stats — статистика заявок\n"
    "/pause, /resume — приостановить/возобновить"
)


def build_router(db: Database, monitor: Monitor, owner_id: int) -> Router:
    router = Router()
    router.message.filter(F.from_user.id == owner_id)
    router.callback_query.filter(F.from_user.id == owner_id)

    @router.message(Command("start", "help"))
    async def start(msg: Message):
        await msg.answer(HELP, parse_mode="HTML")

    @router.message(Command("chats"))
    async def chats(msg: Message):
        rows = await db.list_chats()
        if not rows:
            await msg.answer("Список пуст. Добавьте группу: /add @username")
            return
        lines = [f"• {title} — <code>{cid}</code>" for cid, title, _ in rows]
        await msg.answer("\n".join(lines), parse_mode="HTML")

    @router.message(Command("add"))
    async def add(msg: Message, command: CommandObject):
        if not command.args:
            await msg.answer("Укажите ссылку: /add @username или /add https://t.me/+invite")
            return
        try:
            title = await monitor.add_chat(command.args)
        except Exception as e:  # show any Telegram error to the owner as is
            await msg.answer(f"Не удалось добавить: {e}")
            return
        await msg.answer(f"✅ Добавлено: {title}")

    @router.message(Command("remove"))
    async def remove(msg: Message, command: CommandObject):
        try:
            chat_id = int(command.args or "")
        except ValueError:
            await msg.answer("Укажите id из /chats: /remove -100123…")
            return
        ok = await monitor.remove_chat(chat_id)
        await msg.answer("🗑 Удалено" if ok else "Такой группы нет в списке")

    @router.message(Command("stats"))
    async def stats(msg: Message):
        rows = await db.stats()
        if not rows:
            await msg.answer("Заявок пока нет")
            return
        lines = [
            f"{CATEGORY_TITLES[Category(c)]}: {total} (👍 {yes} / 👎 {no})"
            for c, total, yes, no in rows
        ]
        await msg.answer("\n".join(lines))

    @router.message(Command("pause"))
    async def pause(msg: Message):
        monitor.paused = True
        await msg.answer("⏸ Мониторинг приостановлен")

    @router.message(Command("resume"))
    async def resume(msg: Message):
        monitor.paused = False
        await msg.answer("▶️ Мониторинг возобновлён")

    @router.callback_query(F.data.startswith("lead:"))
    async def feedback(cb: CallbackQuery):
        _, lead_id, status = cb.data.split(":")
        await db.set_status(int(lead_id), status)
        mark = "👍 Отмечено: интересно" if status == "yes" else "👎 Отмечено: не интересно"
        await cb.message.edit_text(
            f"{cb.message.html_text}\n\n<i>{mark}</i>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await cb.answer()

    return router
