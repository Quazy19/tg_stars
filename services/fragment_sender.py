import base64
import re
import logging
import httpx
import traceback
import json
from aiogram import Bot
from tonutils.client import TonapiClient
from tonutils.wallet import WalletV4R2
from config import Config
from .ton_api import get_ton_balance

def fix_base64_padding(b64_string: str) -> str:
    missing_padding = len(b64_string) % 4
    if missing_padding:
        b64_string += '=' * (4 - missing_padding)
    return b64_string

class FragmentSender:
    def __init__(self, config: Config, bot: Bot):
        self.config = config
        self.bot = bot
        self.url = f"https://fragment.com/api?hash={self.config.fragment_hash}"
        self.base_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://fragment.com",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "X-Requested-With": "XMLHttpRequest",
        }
        logging.info("FragmentSender initialized")

    async def _send_ton_transaction(self, recipient_addr, amount, payload, comment_template):
        try:
            if not self.config.api_ton:
                logging.critical("API_TON is not set in .env file!")
                return False
            
            client = TonapiClient(api_key=self.config.api_ton, is_testnet=False)
            
            if not self.config.wallet_seed:
                logging.critical("WALLET_SEED is not set in .env file!")
                return False
                
            wallet, _, _, _ = WalletV4R2.from_mnemonic(client, self.config.wallet_seed.split())
            sender_address = wallet.address
            logging.info(f"Wallet loaded successfully: {sender_address}")

        except Exception as e:
            logging.error(f"Failed to initialize wallet: {e}")
            return False

        amount_decimal = float(amount) / 1_000_000_000
        current_balance, balance_error = await get_ton_balance(str(sender_address))

        if balance_error:
            logging.error(f"Could not check TON wallet balance: {balance_error}")
            return False
        
        if current_balance < amount_decimal:
            logging.critical(f"Insufficient funds. Required: {amount_decimal:.4f} TON, Available: {current_balance:.4f} TON.")
            error_text = (
                f"<b>⚠️ Недостаточно средств на кошельке!</b>\n\n"
                f"Не удалось совершить покупку.\n"
                f"<b>Требуется:</b> <code>{amount_decimal:.4f} TON</code>\n"
                f"<b>В наличии:</b> <code>{current_balance:.4f} TON</code>\n\n"
                f"Пожалуйста, пополните кошелек: <code>{sender_address}</code>"
            )
            for admin_id in self.config.admin_ids:
                try:
                    await self.bot.send_message(admin_id, error_text)
                except Exception as e:
                    logging.error(f"Failed to send low balance notification to admin {admin_id}: {e}")
            return False
        
        if not recipient_addr or not amount or not payload:
            logging.error("Transaction failed: Missing recipient, amount, or payload.")
            return False
        
        try:
            decoded_bytes = base64.b64decode(fix_base64_padding(payload))
            decoded_text = ''.join(chr(b) if 32 <= b < 127 else ' ' for b in decoded_bytes)
            clean_text = re.sub(r'\s+', ' ', decoded_text).strip()
            
            match = re.search(comment_template, clean_text)
            final_text = match.group(0) if match else clean_text
            logging.info(f"Transaction body: {final_text}")
            
            tx_hash = await wallet.transfer(
                destination=recipient_addr,
                amount=amount_decimal,
                body=final_text,
            )
            logging.info(f"Transaction sent successfully: {tx_hash}")
            return True
            
        except Exception as e:
            logging.error(f"TON transaction failed: {e}")
            return False

    async def send_stars(self, username: str, quantity: int) -> bool:
        logging.info(f"Starting stars purchase: {quantity} stars for @{username}")
        
        try:
            async with httpx.AsyncClient(
                cookies=self.config.fragment_cookies, 
                headers=self.base_headers,
                timeout=30.0
            ) as client:
                
                headers_step1 = self.base_headers.copy()
                headers_step1["Referer"] = "https://fragment.com/stars"
                data_step1 = {"query": username, "method": "searchStarsRecipient"}
                
                response_step1 = await client.post(self.url, data=data_step1, headers=headers_step1)
                response_step1.raise_for_status()
                json_step1 = response_step1.json()
                
                if not json_step1.get("ok", True):
                    logging.error(f"Fragment API error in step 1: {json_step1.get('error')}")
                    return False
                
                recipient = json_step1.get("found", {}).get("recipient")
                if not recipient:
                    logging.error(f"Recipient not found for username: {username}")
                    await self._notify_admins(f"❌ Пользователь @{username} не найден на Fragment")
                    return False

                headers_step2 = self.base_headers.copy()
                headers_step2["Referer"] = f"https://fragment.com/stars/buy?query={username}"
                data_step2 = {"recipient": recipient, "quantity": quantity, "method": "initBuyStarsRequest"}

                response_step2 = await client.post(self.url, data=data_step2, headers=headers_step2)
                response_step2.raise_for_status()
                json_step2 = response_step2.json()
                
                if not json_step2.get("ok", True):
                    logging.error(f"Fragment API error in step 2: {json_step2.get('error')}")
                    await self._notify_admins(f"❌ Ошибка инициализации покупки звёзд: {json_step2.get('error')}")
                    return False
                
                req_id = json_step2.get("req_id")
                if not req_id:
                    logging.error(f"Failed to get req_id: {json_step2.get('error')}")
                    return False
                
                headers_step3 = self.base_headers.copy()
                headers_step3["Referer"] = f"https://fragment.com/stars/buy?recipient={recipient}&quantity={quantity}"
                data_step3 = {
                    "address": self.config.fragment_address,
                    "chain": "-239",
                    "walletStateInit": self.config.fragment_wallets,
                    "publicKey": self.config.fragment_public_key,
                    "features": ["SendTransaction", {"name": "SendTransaction", "maxMessages": 255}],
                    "maxProtocolVersion": 2,
                    "platform": "iphone",
                    "appName": "Tonkeeper",
                    "appVersion": "5.0.14",
                    "transaction": "1",
                    "id": req_id,
                    "show_sender": "0",
                    "method": "getBuyStarsLink"
                }

                response_step3 = await client.post(self.url, data=data_step3, headers=headers_step3)
                response_step3.raise_for_status()
                json_step3 = response_step3.json()

                if not (json_step3.get("ok") and "transaction" in json_step3):
                    error_msg = json_step3.get("error", "Unknown error")
                    logging.error(f"Failed to get transaction data from Fragment: {error_msg}")
                    await self._notify_admins(f"❌ Ошибка получения данных транзакции: {error_msg}")
                    return False
                
                tx = json_step3["transaction"]["messages"][0]
                addr, amount, payload = tx["address"], tx["amount"], tx["payload"]

                comment_template = rf"{quantity} Telegram Stars.*"
                success = await self._send_ton_transaction(addr, amount, payload, comment_template)
                
                if success:
                    logging.info(f"Successfully sent {quantity} stars to @{username}")
                
                return success

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error during stars purchase for @{username}: {e.response.status_code}")
            await self._notify_admins(f"❌ HTTP ошибка при покупке звёзд для @{username}: {e.response.status_code}")
            return False
        except Exception as e:
            logging.error(f"Stars purchase failed for @{username}: {e}")
            await self._notify_admins(f"❌ Ошибка покупки звёзд для @{username}: {str(e)}")
            return False

    async def _notify_admins(self, message: str):
        for admin_id in self.config.admin_ids:
            try:
                await self.bot.send_message(admin_id, f"🔗 <b>Fragment уведомление</b>\n\n{message}")
            except Exception as e:
                logging.error(f"Failed to notify admin {admin_id}: {e}")

    async def send_premium(self, username: str, months: int) -> bool:
        logging.info(f"Starting premium purchase: {months} months for @{username}")
        
        try:
            async with httpx.AsyncClient(
                cookies=self.config.fragment_cookies, 
                headers=self.base_headers,
                timeout=30.0
            ) as client:
                
                headers_step1 = self.base_headers.copy()
                headers_step1["Referer"] = "https://fragment.com/premium"
                data_step1 = {"query": username, "months": months, "method": "searchPremiumGiftRecipient"}
                
                response_step1 = await client.post(self.url, data=data_step1, headers=headers_step1)
                response_step1.raise_for_status()
                json_step1 = response_step1.json()
                
                if not json_step1.get("ok", True):
                    logging.error(f"Fragment API error in premium step 1: {json_step1.get('error')}")
                    return False
                
                recipient = json_step1.get("found", {}).get("recipient")
                if not recipient:
                    logging.error(f"Premium recipient not found for username: {username}")
                    await self._notify_admins(f"❌ Пользователь @{username} не найден для премиума")
                    return False
                
                headers_step2 = self.base_headers.copy()
                headers_step2["Referer"] = f"https://fragment.com/premium/gift?query={username}"
                data_step2 = {"recipient": recipient, "months": months, "method": "initGiftPremiumRequest"}

                response_step2 = await client.post(self.url, data=data_step2, headers=headers_step2)
                response_step2.raise_for_status()
                json_step2 = response_step2.json()
                
                if not json_step2.get("ok", True):
                    logging.error(f"Fragment API error in premium step 2: {json_step2.get('error')}")
                    await self._notify_admins(f"❌ Ошибка инициализации покупки премиума: {json_step2.get('error')}")
                    return False
                
                req_id = json_step2.get("req_id")
                if not req_id:
                    logging.error(f"Failed to get premium req_id: {json_step2.get('error')}")
                    return False
                
                headers_step3 = self.base_headers.copy()
                headers_step3["Referer"] = f"https://fragment.com/premium/gift?recipient={recipient}&months={months}"
                data_step3 = {
                    "address": self.config.fragment_address,
                    "chain": "-239",
                    "walletStateInit": self.config.fragment_wallets,
                    "publicKey": self.config.fragment_public_key,
                    "features": ["SendTransaction", {"name": "SendTransaction", "maxMessages": 255}],
                    "maxProtocolVersion": 2,
                    "platform": "iphone",
                    "appName": "Tonkeeper",
                    "appVersion": "5.0.14",
                    "transaction": "1",
                    "id": req_id,
                    "show_sender": "0",
                    "method": "getGiftPremiumLink"
                }

                response_step3 = await client.post(self.url, data=data_step3, headers=headers_step3)
                response_step3.raise_for_status()
                json_step3 = response_step3.json()

                if not (json_step3.get("ok") and "transaction" in json_step3):
                    error_msg = json_step3.get("error", "Unknown error")
                    logging.error(f"Failed to get premium transaction data from Fragment: {error_msg}")
                    await self._notify_admins(f"❌ Ошибка получения данных транзакции премиума: {error_msg}")
                    return False

                tx = json_step3["transaction"]["messages"][0]
                addr, amount, payload = tx["address"], tx["amount"], tx["payload"]
                
                comment_template = r"Telegram.*Ref\s*#\S+"
                success = await self._send_ton_transaction(addr, amount, payload, comment_template)
                
                if success:
                    logging.info(f"Successfully sent {months} months premium to @{username}")
                
                return success

        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error during premium purchase for @{username}: {e.response.status_code}")
            await self._notify_admins(f"❌ HTTP ошибка при покупке премиума для @{username}: {e.response.status_code}")
            return False
        except Exception as e:
            logging.error(f"Premium purchase failed for @{username}: {e}")
            await self._notify_admins(f"❌ Ошибка покупки премиума для @{username}: {str(e)}")

            return False
