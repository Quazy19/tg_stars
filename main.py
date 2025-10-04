import asyncio
import json
import logging
import sys
import shutil
import os
from datetime import datetime, timedelta

import pytz
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config, load_config
from database import init_db, get_db_connection
from handlers.user import get_user_router
from handlers.admin import get_admin_router
from middlewares.access import AccessMiddleware
from services.repository import Repository
from services.fragment_sender import FragmentSender
from services.fragment_auth import FragmentAuth
from payments.cryptobot import check_cryptopay_signature
from payments.payment_manager import PaymentManager
from payments.lolzteam import check_lzt_payment_status
from payments.crystalpay import check_crystalpay_invoice


async def cryptopay_webhook(request: web.Request):
    bot: Bot = request.app["bot"]
    repo: Repository = request.app["repo"]
    config: Config = request.app["config"]

    signature = request.headers.get("Crypto-Pay-API-Signature")
    raw_body = await request.read()
    
    if not signature or not check_cryptopay_signature(config, raw_body, signature):
        logging.warning("CryptoPay Webhook: Invalid signature received.")
        return web.Response(status=403, text="Invalid signature")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        logging.error("CryptoPay Webhook: Invalid JSON received.")
        return web.Response(status=400, text="Invalid JSON")

    if data.get("update_type") != "invoice_paid":
        return web.Response(status=200, text="OK")

    payload = data.get("payload")
    if not payload or not (order_id := payload.get("order_id")):
        return web.Response(status=400, text="OK")

    payment_info = await repo.process_successful_payment(order_id)
    if not payment_info:
        return web.Response(status=200, text="OK")

    logging.info(f"Successfully processed CryptoBot payment for order_id {order_id}.")
    try:
        user = await repo.get_user(payment_info['user_id'])
        await bot.edit_message_text(
            chat_id=payment_info["user_id"],
            message_id=payment_info["message_id"],
            text=f"✅ Платеж успешно выполнен!\n\n💰 Сумма: {payment_info['amount']:.2f}₽\n💳 Ваш новый баланс: {user['balance']:.2f}₽",
            reply_markup=None
        )
    except Exception as e:
        logging.error(f"CryptoPay Webhook: Failed to edit notification for user {payment_info['user_id']}: {e}")
            
    return web.Response(status=200, text="OK")

async def monitor_payments(bot: Bot, repo: Repository, config: Config):
    logging.info("Payment monitor started.")
    while True:
        try:
            pending_payments = await repo.get_all_pending_payments()
            
            for payment in pending_payments:
                order_id = payment['uuid']
                user_id = payment['user_id']
                message_id = payment['message_id']
                created_at = datetime.fromisoformat(payment['created_at'])

                if datetime.utcnow() > created_at + timedelta(seconds=config.payment_timeout_seconds):
                    status_was_updated = await repo.update_payment_status(order_id, 'expired')
                    if status_was_updated:
                        logging.info(f"Payment {order_id} for user {user_id} has expired. Status updated.")
                        try:
                            await bot.edit_message_text(
                                chat_id=user_id, 
                                message_id=message_id, 
                                text="❌ Время оплаты истекло. Счет был отменен.",
                                reply_markup=None
                            )
                        except Exception:
                            pass
                    continue

                payment_system = payment['payment_system']
                if payment_system in ['lzt', 'crystalpay']:
                    is_paid = False
                    if payment_system == 'lzt':
                        is_paid, _ = await check_lzt_payment_status(config, order_id)
                    elif payment_system == 'crystalpay':
                        invoice_id = payment['external_invoice_id']
                        if invoice_id:
                            is_paid, _ = await check_crystalpay_invoice(config, invoice_id)

                    if is_paid:
                        payment_info = await repo.process_successful_payment(order_id)
                        if payment_info:
                            logging.info(f"Successfully processed {payment_system} payment for order_id {order_id}.")
                            try:
                                user = await repo.get_user(payment_info['user_id'])
                                await bot.edit_message_text(
                                    chat_id=payment_info["user_id"],
                                    message_id=payment_info["message_id"],
                                    text=f"✅ Платеж успешно выполнен!\n\n💰 Сумма: {payment_info['amount']:.2f}₽\n💳 Ваш новый баланс: {user['balance']:.2f}₽",
                                    reply_markup=None
                                )
                            except Exception as e:
                                logging.error(f"Monitor: Failed to edit notification for user {payment_info['user_id']}: {e}")
        
        except Exception as e:
            logging.error(f"Error in payment monitor: {e}")
        
        await asyncio.sleep(20)


async def backup_database(bot: Bot, config: Config):
    if not os.path.exists(config.database_path):
        return

    timestamp = datetime.now(pytz.timezone('Europe/Moscow')).strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = f"backup_{timestamp}.db"
    
    try:
        shutil.copy(config.database_path, backup_path)
        document = FSInputFile(backup_path)
        caption = f"Ежедневный бэкап базы данных\n{timestamp} МСК"
        
        for admin_id in config.admin_ids:
            try:
                await bot.send_document(chat_id=admin_id, document=document, caption=caption)
            except Exception as e:
                logging.error(f"Failed to send backup to admin {admin_id}: {e}")
    except Exception as e:
        logging.error(f"Failed to create or send database backup: {e}")
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)

async def start_bot():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    config = load_config()
    if not config.admin_ids or not config.bot_token:
        logging.critical("ADMIN_IDS or BOT_TOKEN is not set.")
        sys.exit(1)
    
    required_fragment_fields = [
        'fragment_hash', 'fragment_address', 'fragment_wallets', 
        'fragment_public_key', 'wallet_seed', 'api_ton'
    ]
    missing_fields = [field for field in required_fragment_fields if not getattr(config, field)]
    if missing_fields:
        logging.critical(f"Fragment configuration incomplete. Missing: {', '.join(missing_fields)}")
        sys.exit(1)
    
    required_cookies = ['stel_ssid', 'stel_dt', 'stel_ton_token', 'stel_token']
    missing_cookies = [cookie for cookie in required_cookies if not config.fragment_cookies.get(cookie)]
    if missing_cookies:
        logging.critical(f"Fragment cookies incomplete. Missing: {', '.join(missing_cookies)}")
        sys.exit(1)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    
    db_connection = await get_db_connection(config.database_path)
    await init_db(config.database_path)
    
    repo = Repository(db_connection)
    fragment_sender = FragmentSender(config, bot)
    payment_manager = PaymentManager(config)

    dp["repo"] = repo
    dp["config"] = config
    dp["fragment_sender"] = fragment_sender
    dp["payment_manager"] = payment_manager

    dp.update.outer_middleware(AccessMiddleware(repo, config))

    admin_router = get_admin_router(config.admin_ids)
    user_router = get_user_router()
    dp.include_router(admin_router)
    dp.include_router(user_router)
    
    app = web.Application()
    app["bot"] = bot
    app["repo"] = repo
    app["config"] = config
    app.router.add_post("/webhook/cryptopay", cryptopay_webhook)
    
    fragment_auth = FragmentAuth(config)
    
    async def refresh_fragment_token():
        await fragment_auth.refresh_token_if_needed(repo)
    
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Europe/Moscow'))
    scheduler.add_job(backup_database, 'cron', hour=0, minute=0, kwargs={'bot': bot, 'config': config})
    scheduler.add_job(refresh_fragment_token, 'interval', hours=1)
    scheduler.start()
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    
    monitor_task = asyncio.create_task(monitor_payments(bot, repo, config))
    
    try:
        await asyncio.gather(
            dp.start_polling(bot),
            site.start()
        )
    finally:
        monitor_task.cancel()
        await bot.session.close()
        await runner.cleanup()
        await db_connection.close()

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")