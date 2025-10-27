import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from typing import Dict

from services.repository import Repository
from payments.lolz_payment import LolzPayment
from payments.cryptobot_payment import CryptoBotPayment
from payments.xrocet_payment import XRocetPayment
from payments.crystalpay_payment import CrystalPayPayment
from config import Config

logger = logging.getLogger(__name__)

class PaymentChecker:
    
    def __init__(self, bot: Bot, repo: Repository, config: Config, enabled_systems: Dict[str, bool]):
        self.bot = bot
        self.repo = repo
        self.config = config
        self.enabled_systems = enabled_systems
        self.is_running = False
        self.payment_handlers = {
            "lolz": LolzPayment(),
            "cryptobot": CryptoBotPayment(),
            "xrocet": XRocetPayment(self.config.xrocet.api_key),
            "crystalpay": CrystalPayPayment(self.config.crystalpay.login, self.config.crystalpay.secret)
        }
    
    async def start_checking(self):
        self.is_running = True
        logger.info("Запущена автоматическая проверка платежей")
        
        while self.is_running:
            try:
                await self.check_pending_payments()
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Ошибка в процессе проверки платежей: {e}")
                await asyncio.sleep(30)
    
    async def check_pending_payments(self):
        try:
            pending_payments = await self.repo.get_pending_payments()
            for payment in pending_payments:
                if self.enabled_systems.get(payment['payment_method']):
                    await self.process_single_payment(payment)
        except Exception as e:
            logger.error(f"Ошибка получения ожидающих платежей: {e}")
    
    async def process_single_payment(self, payment: dict):
        try:
            payment_method, invoice_id = payment['payment_method'], payment['invoice_id']
            payload_id = payment.get('payload_id')
            
            expires_at = datetime.fromisoformat(payment['expires_at'])
            if datetime.now() > expires_at:
                if await self.repo.update_payment_status(invoice_id, "expired"):
                    await self.notify_user_payment_expired(payment['user_id'], invoice_id)
                return
            
            payment_handler = self.payment_handlers.get(payment_method)
            if not payment_handler: return

            check_id = payload_id if payment_method == "cryptobot" and payload_id else invoice_id
            
            status_result = {}
            if payment_method == "xrocet":
                 status = await payment_handler.check_payment(check_id)
                 status_result = {"success": True, "status": status}
            else:
                status_result = await payment_handler.check_payment_status(check_id)
            
            if not status_result.get("success"):
                logger.error(f"Ошибка проверки статуса {invoice_id}: {status_result.get('error')}")
                return
            
            if status_result.get("status") == "paid":
                processed_payment = await self.repo.process_successful_payment(invoice_id)
                if processed_payment:
                    logger.info(f"Платеж {invoice_id} успешно обработан, зачислено {processed_payment['amount']} ₽")
                    await self.notify_user_payment_success(processed_payment['user_id'], processed_payment['amount'], invoice_id)
                    await self._notify_admin_payment_success(processed_payment)

        except Exception as e:
            logger.error(f"Ошибка обработки платежа {payment.get('invoice_id', 'unknown')}: {e}")

    async def _notify_admin_payment_success(self, payment: dict):
        try:
            user = await self.repo.get_user(payment['user_id'])
            if not user:
                return

            method_names = {
                "lolz": "🔥 Lolz", 
                "cryptobot": "🤖 CryptoBot", 
                "xrocet": "🚀 xRocet", 
                "crystalpay": "💎 CrystalPay"
            }
            payment_system_name = method_names.get(payment['payment_method'], payment['payment_method'].capitalize())
            
            log_text = (
                f"<b>✅ Новое пополнение!</b>\n\n"
                f"👤 <b>Пользователь:</b> @{user['username']} (<code>{user['telegram_id']}</code>)\n"
                f"💳 <b>Способ:</b> {payment_system_name}\n\n"
                f"💰 <b>Сумма:</b> {payment['amount']:.2f} ₽\n"
                f"💸 <b>Комиссия:</b> {payment.get('fee_amount', 0.0):.2f} ₽\n"
                f"📈 <b>Итого:</b> {payment.get('total_amount', payment['amount']):.2f} ₽\n\n"
                f"🏦 <b>Новый баланс:</b> {user['balance']:.2f} ₽"
            )

            for admin_id in self.config.bot.admin_ids:
                try:
                    await self.bot.send_message(admin_id, log_text)
                except Exception as e:
                    logger.error(f"Не удалось отправить лог пополнения админу {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при создании лога для админа: {e}")
    
    async def notify_user_payment_success(self, user_id: int, amount: float, invoice_id: str):
        try:
            from keyboards.user_kb import get_main_menu_only_keyboard
            payment_data = await self.repo.get_payment_by_invoice_id(invoice_id)
            user_data = await self.repo.get_user(user_id)
            message_text = (f"✅ <b>Платеж успешно обработан!</b>\n\n"
                            f"💰 На ваш баланс зачислено: <b>{amount:.2f} ₽</b>\n"
                            f"💳 Текущий баланс: <b>{user_data['balance']:.2f} ₽</b>\n"
                            f"📄 ID платежа: <code>{invoice_id}</code>")
            
            if payment_data and payment_data.get('message_id') and payment_data.get('chat_id'):
                try:
                    await self.bot.edit_message_text(text=message_text, chat_id=payment_data['chat_id'], message_id=payment_data['message_id'], reply_markup=get_main_menu_only_keyboard())
                except Exception:
                    await self.bot.send_message(user_id, message_text, reply_markup=get_main_menu_only_keyboard())
            else:
                await self.bot.send_message(user_id, message_text, reply_markup=get_main_menu_only_keyboard())
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об успехе {user_id}: {e}")
    
    async def notify_user_payment_expired(self, user_id: int, invoice_id: str):
        try:
            from keyboards.user_kb import get_main_menu_only_keyboard
            payment_data = await self.repo.get_payment_by_invoice_id(invoice_id)
            if payment_data and payment_data.get('message_id') and payment_data.get('chat_id'):
                await self.bot.edit_message_text(text=f"⏰ <b>Время действия счета истекло</b>\n\n📄 ID счета: <code>{invoice_id}</code>", chat_id=payment_data['chat_id'], message_id=payment_data['message_id'], reply_markup=get_main_menu_only_keyboard())
        except Exception:
            pass
    
    def stop_checking(self):
        self.is_running = False
        logger.info("Автоматическая проверка платежей остановлена")
