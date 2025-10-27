import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class XRocetPayment:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://pay.xrocket.tg"
        self.headers = {
            "Rocket-Pay-Key": api_key,
            "Content-Type": "application/json"
        }
    
    async def create_invoice(self, amount: float, description: str, payload: str = None) -> Optional[Dict[str, Any]]:
        try:
            toncoin_amount = await self.convert_rub_to_toncoin(amount)
            
            async with aiohttp.ClientSession() as session:
                data = {
                    "amount": toncoin_amount,
                    "currency": "TONCOIN",
                    "description": description,
                    "payload": payload or f"user_payment_{hash(str(amount))}",
                    "expiredIn": 15,
                    "commentsEnabled": False
                }
                
                logger.info(f"Creating xRocket invoice with data: {data}")
                
                async with session.post(
                    f"{self.base_url}/tg-invoices",
                    headers=self.headers,
                    json=data
                ) as response:
                    response_text = await response.text()
                    logger.info(f"xRocket API response status: {response.status}")
                    logger.info(f"xRocket API response: {response_text}")
                    
                    if response.status == 201:
                        result = await response.json()
                        if result.get("success"):
                            invoice_data = result["data"]
                            logger.info(f"xRocket invoice created successfully: {invoice_data['id']}")
                            return {
                                "success": True,
                                "invoice_id": str(invoice_data["id"]),
                                "payment_url": invoice_data["link"],
                                "amount": amount,
                                "toncoin_amount": toncoin_amount
                            }
                        else:
                            logger.error(f"xRocket API returned success=false: {result}")
                            return None
                    else:
                        logger.error(f"xRocket invoice creation failed with status {response.status}: {response_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error creating xRocket invoice: {e}")
            return None
    
    async def check_payment(self, invoice_id: str) -> Optional[str]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/tg-invoices/{invoice_id}",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("success"):
                            invoice_data = result["data"]
                            status = invoice_data.get("status", "active")
                            
                            payments = invoice_data.get("payments", [])
                            if payments:
                                logger.info(f"xRocket payment completed for invoice {invoice_id}")
                                return "paid"
                            elif status == "active":
                                return "pending"
                            else:
                                return "expired"
                        else:
                            logger.error(f"xRocket API returned success=false: {result}")
                            return "pending"
                    else:
                        logger.error(f"Failed to check xRocket payment: {response.status}")
                        return "pending"
                        
        except Exception as e:
            logger.error(f"Error checking xRocket payment: {e}")
            return "pending"
    
    async def get_toncoin_to_rub_rate(self) -> float:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=rub"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        rate = data.get("the-open-network", {}).get("rub", 320.0)
                        logger.info(f"TONCOIN/RUB rate: {rate}")
                        return rate
                    else:
                        logger.warning("Failed to get TONCOIN rate, using fallback")
                        return 320.0
        except Exception as e:
            logger.error(f"Error getting TONCOIN rate: {e}")
            return 320.0
    
    async def convert_rub_to_toncoin(self, rub_amount: float) -> float:
        rate = await self.get_toncoin_to_rub_rate()
        toncoin_amount = rub_amount / rate
        return round(toncoin_amount, 6)