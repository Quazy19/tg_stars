import logging
import time
from typing import Dict, Any
from config.config import load_config

try:
    from lolzteam import LolzteamApi
    OFFICIAL_LIB_AVAILABLE = True
except ImportError:
    OFFICIAL_LIB_AVAILABLE = False
    print("Официальная библиотека lolzteam не установлена. Используется HTTP API.")

logger = logging.getLogger(__name__)
config = load_config()

class LolzPaymentOfficial:
    
    def __init__(self):
        if not OFFICIAL_LIB_AVAILABLE:
            raise ImportError("Библиотека lolzteam не установлена")
            
        self.api_key = config.lolz.api_key
        self.user_id = config.lolz.user_id
        self.api = LolzteamApi(token=self.api_key)
        
    async def create_invoice(self, amount: float) -> Dict[str, Any]:
        try:
            response = self.api.market.payments.create_invoice(
                currency="rub",
                amount=int(amount),
                payment_id=f"bot_payment_{int(time.time())}",
                comment="Пополнение баланса бота",
                url_success="https://lolz.live/",
                merchant_id=int(self.user_id),
                lifetime=900,
                additional_data=f"user_payment_{int(time.time())}",
                is_test=False
            )
            
            if response and hasattr(response, 'invoice'):
                invoice_data = response.invoice
                
                return {
                    "success": True,
                    "invoice_id": str(invoice_data.invoice_id),
                    "payment_url": invoice_data.url,
                    "amount": amount,
                    "expires_at": invoice_data.expires_at
                }
            else:
                logger.error(f"Неожиданный ответ от API: {response}")
                return {
                    "success": False,
                    "error": "Неожиданный ответ от API"
                }
                
        except Exception as e:
            logger.error(f"Ошибка создания инвойса через официальную библиотеку: {e}")
            return {
                "success": False,
                "error": f"Ошибка API: {str(e)}"
            }
    
    async def check_payment_status(self, invoice_id: str) -> Dict[str, Any]:
        try:
            response = self.api.market.payments.get_invoice(invoice_id=int(invoice_id))
            
            if response and hasattr(response, 'invoice'):
                invoice_data = response.invoice
                status = invoice_data.status
                
                return {
                    "success": True,
                    "status": "paid" if status == "paid" else "pending",
                    "lolz_status": status,
                    "paid_date": getattr(invoice_data, 'paid_date', None),
                    "amount": getattr(invoice_data, 'amount', None),
                    "payer_user_id": getattr(invoice_data, 'payer_user_id', None)
                }
            else:
                return {
                    "success": False,
                    "error": "Инвойс не найден"
                }
                
        except Exception as e:
            logger.error(f"Ошибка проверки статуса через официальную библиотеку: {e}")
            return {
                "success": False,
                "error": f"Ошибка API: {str(e)}"
            }