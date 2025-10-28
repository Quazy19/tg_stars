import aiohttp
import logging
import time
from typing import Dict, Any
from config import load_config

logger = logging.getLogger(__name__)
config = load_config()

class LolzPayment:
    
    def __init__(self):
        self.api_key = config.lolz.api_key
        self.user_id = config.lolz.user_id
        self.base_url = "https://prod-api.lzt.market"
        
    async def create_invoice(self, amount: float) -> Dict[str, Any]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "currency": "rub",
                "amount": int(amount),
                "payment_id": f"bot_payment_{int(time.time())}",
                "comment": "Пополнение баланса бота",
                "url_success": "https://lolz.live/",
                "url_callback": "",
                "merchant_id": int(self.user_id),
                "lifetime": 900,
                "additional_data": f"user_payment_{int(time.time())}",
                "is_test": False
            }
            
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    f"{self.base_url}/invoice",
                    headers=headers,
                    json=data
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if "invoice" in result:
                            invoice_data = result["invoice"]
                            
                            return {
                                "success": True,
                                "invoice_id": str(invoice_data.get("invoice_id")),
                                "payment_url": invoice_data.get("url"),
                                "amount": amount,
                                "payment_id": data["payment_id"],
                                "expires_at": invoice_data.get("expires_at")
                            }
                        else:
                            logger.error(f"Неожиданный формат ответа Lolz API: {result}")
                            return {
                                "success": False,
                                "error": "Неожиданный формат ответа API"
                            }
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка создания счета Lolz (статус {response.status}): {error_text}")
                        return {
                            "success": False,
                            "error": f"Ошибка API Lolz: {response.status}"
                        }
                        
        except Exception as e:
            logger.error(f"Исключение при создании счета Lolz: {e}")
            return {
                "success": False,
                "error": "Ошибка соединения с API Lolz"
            }
    
    async def check_payment_status(self, invoice_id: str) -> Dict[str, Any]:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    f"{self.base_url}/invoice/{invoice_id}",
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if "invoice" in result:
                            invoice_data = result["invoice"]
                            status = invoice_data.get("status")
                            
                            return {
                                "success": True,
                                "status": "paid" if status == "paid" else "pending",
                                "lolz_status": status,
                                "paid_date": invoice_data.get("paid_date"),
                                "amount": invoice_data.get("amount"),
                                "payer_user_id": invoice_data.get("payer_user_id")
                            }
                        else:
                            return {
                                "success": False,
                                "error": "Неожиданный формат ответа API"
                            }
                    elif response.status == 404:
                        return {
                            "success": False,
                            "error": "Инвойс не найден"
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка проверки статуса Lolz (статус {response.status}): {error_text}")
                        return {
                            "success": False,
                            "error": f"Ошибка проверки статуса: {response.status}"
                        }
                        
        except Exception as e:
            logger.error(f"Ошибка проверки статуса Lolz: {e}")
            return {
                "success": False,
                "error": "Ошибка соединения с API"
            }
