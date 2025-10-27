import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CrystalPayPayment:
    def __init__(self, login: str, secret: str):
        self.login = login
        self.secret = secret
        self.base_url = "https://api.crystalpay.io/v3"
    
    async def create_invoice(self, amount: float, description: str = "Пополнение баланса") -> Optional[Dict[str, Any]]:
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "auth_login": self.login,
                    "auth_secret": self.secret,
                    "amount": int(amount),
                    "type": "topup",
                    "lifetime": 15,
                    "currency": "RUB",
                    "description": description,
                    "extra": f"bot_payment_{hash(str(amount))}"
                }
                
                logger.info(f"Creating CrystalPay invoice with data: amount={amount}, description={description}")
                
                async with session.post(
                    f"{self.base_url}/invoice/create/",
                    json=data
                ) as response:
                    response_text = await response.text()
                    logger.info(f"CrystalPay API response status: {response.status}")
                    logger.info(f"CrystalPay API response: {response_text}")
                    
                    if response.status == 200:
                        result = await response.json()
                        if not result.get("error"):
                            invoice_data = result
                            logger.info(f"CrystalPay invoice created successfully: {invoice_data['id']}")
                            return {
                                "success": True,
                                "invoice_id": invoice_data["id"],
                                "payment_url": invoice_data["url"],
                                "amount": amount
                            }
                        else:
                            logger.error(f"CrystalPay API returned error: {result}")
                            return {
                                "success": False,
                                "error": f"CrystalPay error: {result.get('errors', 'Unknown error')}"
                            }
                    else:
                        logger.error(f"CrystalPay invoice creation failed with status {response.status}: {response_text}")
                        return {
                            "success": False,
                            "error": f"API error: {response.status}"
                        }
                        
        except Exception as e:
            logger.error(f"Error creating CrystalPay invoice: {e}")
            return {
                "success": False,
                "error": "Connection error"
            }
    
    async def check_payment_status(self, invoice_id: str) -> Dict[str, Any]:
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "auth_login": self.login,
                    "auth_secret": self.secret,
                    "id": invoice_id
                }
                
                async with session.post(
                    f"{self.base_url}/invoice/info/",
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if not result.get("error"):
                            invoice_data = result
                            status = invoice_data.get("state", "notpayed")
                            
                            return {
                                "success": True,
                                "status": "paid" if status == "payed" else "pending"
                            }
                        else:
                            logger.error(f"CrystalPay API returned error: {result}")
                            return {
                                "success": False,
                                "error": f"API error: {result.get('errors', 'Unknown error')}"
                            }
                    else:
                        logger.error(f"Failed to check CrystalPay payment: {response.status}")
                        return {
                            "success": False,
                            "error": f"API error: {response.status}"
                        }
                        
        except Exception as e:
            logger.error(f"Error checking CrystalPay payment: {e}")
            return {
                "success": False,
                "error": "Connection error"
            }