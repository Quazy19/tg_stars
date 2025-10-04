import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, types
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

        if user.id in self.config.admin_ids:
            return await handler(event, data)

        settings = await self.repo.get_multiple_settings(['maintenance_mode'])

        if settings.get('maintenance_mode') == '1':
            if isinstance(event, types.Message):
                await event.answer("🛠️ Бот находится на техническом обслуживании. Пожалуйста, попробуйте позже.")
            elif isinstance(event, types.CallbackQuery):
                await event.answer("🛠️ Бот находится на техническом обслуживании.", show_alert=True)
            return

        is_blocked = await self.repo.is_user_blocked(user.id)
        if is_blocked:
            return

        return await handler(event, data)