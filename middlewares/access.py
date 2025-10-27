from typing import Callable, Dict, Any, Awaitable
from aiogram import types
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import TelegramObject

from config import Config
from services.repository import Repository

class AccessMiddleware(BaseMiddleware):
    def __init__(self, repo: Repository, config: Config):
        self.repo = repo
        self.config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        if user.id in self.config.bot.admin_ids:
            return await handler(event, data)

        maintenance_mode = await self.repo.get_setting('maintenance_mode')
        if maintenance_mode == '1':
            if isinstance(event, types.Message):
                await event.answer("🛠️ Бот на техническом обслуживании.")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("🛠️ Бот на техническом обслуживании.", show_alert=True)
            return

        if await self.repo.is_user_blocked(user.id):
            return

        return await handler(event, data)