import logging
from aiogram import Bot, types
from aiogram.enums import ChatMemberStatus
from aiogram.filters import Filter

from config import Config
from keyboards.user_kb import get_subscription_check_kb, SubscribeCallback
from services.repository import Repository

async def show_subscription_prompt(event: types.Message | types.CallbackQuery, channel_link: str):
    text = "Для доступа к боту необходимо подписаться на наш новостной канал."
    kb = get_subscription_check_kb(channel_link)

    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=kb)
    elif isinstance(event, types.CallbackQuery):
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer(text, reply_markup=kb)
        await event.answer()

class CheckSubscriptionFilter(Filter):
    async def __call__(
        self,
        event: types.Message | types.CallbackQuery,
        bot: Bot,
        repo: Repository,
        config: Config
    ) -> bool:
        if isinstance(event, types.CallbackQuery) and event.data == SubscribeCallback(action="check").pack():
            return True

        user = event.from_user

        if user.id in config.bot.admin_ids:
            return True

        settings = await repo.get_multiple_settings(['force_subscribe', 'news_channel_id', 'news_channel_link'])

        if settings.get('force_subscribe') != '1':
            return True

        channel_id = settings.get('news_channel_id')
        channel_link = settings.get('news_channel_link')

        if not channel_id or not channel_link:
            return True

        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user.id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                await show_subscription_prompt(event, channel_link)
                return False
            else:
                return True
        except Exception as e:
            logging.error(f"Could not check subscription for user {user.id} in channel {channel_id}: {e}")
            return True