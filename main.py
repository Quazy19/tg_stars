import asyncio
import logging
import sys
import shutil
import os
from datetime import datetime

import pytz
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from database import init_db, get_db_connection
from handlers.user import get_user_router
from handlers.admin import get_admin_router
from middlewares.access import AccessMiddleware
from services.repository import Repository
from services.fragment_sender import FragmentSender
from services.fragment_auth import FragmentAuth
from utils.payment_checker import PaymentChecker

async def backup_database(bot: Bot, config):
    if not os.path.exists(config.database_path):
        return

    timestamp = datetime.now(pytz.timezone('Europe/Moscow')).strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = f"backup_{timestamp}.db"
    
    try:
        shutil.copy(config.database_path, backup_path)
        document = FSInputFile(backup_path)
        caption = f"Ежедневный бэкап базы данных\n{timestamp} МСК"
        
        for admin_id in config.bot.admin_ids:
            try:
                await bot.send_document(chat_id=admin_id, document=document, caption=caption)
            except Exception as e:
                logging.error(f"Failed to send backup to admin {admin_id}: {e}")
    except Exception as e:
        logging.error(f"Failed to create or send database backup: {e}")
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)

def check_payment_systems(config):
    enabled_systems = {}
    
    if config.lolz.api_key and config.lolz.user_id:
        enabled_systems['lolz'] = True
        logging.info("Платежная система Lolz включена.")
    else:
        logging.warning("Платежная система Lolz отключена: не указан LOLZ_API_KEY или LOLZ_USER_ID.")
        
    if config.cryptobot.api_key:
        enabled_systems['cryptobot'] = True
        logging.info("Платежная система CryptoBot включена.")
    else:
        logging.warning("Платежная система CryptoBot отключена: не указан CRYPTOBOT_API_KEY.")
        
    if config.xrocet.api_key:
        enabled_systems['xrocet'] = True
        logging.info("Платежная система xRocet включена.")
    else:
        logging.warning("Платежная система xRocet отключена: не указан XROCET_API_KEY.")
        
    if config.crystalpay.login and config.crystalpay.secret:
        enabled_systems['crystalpay'] = True
        logging.info("Платежная система CrystalPay включена.")
    else:
        logging.warning("Платежная система CrystalPay отключена: не указан CRYSTALPAY_LOGIN или CRYSTALPAY_SECRET.")
        
    return enabled_systems

async def start_bot():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    config = load_config()
    
    if not config.bot.admin_ids or not config.bot.bot_token:
        logging.critical("ADMIN_IDS или BOT_TOKEN не указаны. Выход.")
        sys.exit(1)

    bot = Bot(token=config.bot.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    enabled_payment_systems = check_payment_systems(config)

    db_connection = await get_db_connection(config.database_path)
    await init_db(config.database_path)
    
    repo = Repository(db_connection)
    fragment_sender = FragmentSender(config, bot)

    dp["repo"] = repo
    dp["config"] = config
    dp["fragment_sender"] = fragment_sender
    dp["enabled_payment_systems"] = enabled_payment_systems

    dp.update.outer_middleware(AccessMiddleware(repo, config))

    admin_router = get_admin_router(config.bot.admin_ids)
    user_router = get_user_router()
    dp.include_router(admin_router)
    dp.include_router(user_router)
    
    fragment_auth = FragmentAuth(config)
    
    async def refresh_fragment_token():
        await fragment_auth.refresh_token_if_needed(repo)
    
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
    scheduler.add_job(backup_database, 'cron', hour=0, minute=0, kwargs={'bot': bot, 'config': config})
    scheduler.add_job(refresh_fragment_token, 'interval', hours=1)
    scheduler.start()
    
    payment_checker = PaymentChecker(bot, repo, config, enabled_payment_systems)
    payment_checker_task = asyncio.create_task(payment_checker.start_checking())
    
    try:
        await dp.start_polling(bot)
    finally:
        payment_checker_task.cancel()
        scheduler.shutdown()
        await bot.session.close()
        await db_connection.close()

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен!")