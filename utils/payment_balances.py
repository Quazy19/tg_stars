import logging
from typing import Dict, Any
from config import Config
from payments.lolz_payment import LolzPayment
from payments.cryptobot_payment import CryptoBotPayment
from payments.xrocet_payment import XRocetPayment
from payments.crystalpay_payment import CrystalPayPayment
from services.repository import Repository

logger = logging.getLogger(__name__)

class PaymentSystemBalances:
    
    def __init__(self, config: Config, repo: Repository):
        self.config = config
        self.repo = repo

    async def get_lolz_balance(self) -> Dict[str, Any]:
        try:
            stats = await self.repo.get_payments_stats()
            lolz_revenue = stats.get('methods', {}).get('lolz', {}).get('paid_revenue', 0.0)
            return {"success": True, "balance": f"{lolz_revenue:.2f}", "currency": "RUB", "note": f"Выручка: {lolz_revenue:.2f} ₽"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_cryptobot_balance(self) -> Dict[str, Any]:
        try:
            payment_handler = CryptoBotPayment()
            balance_result = await payment_handler.get_balance()
            if balance_result["success"]:
                balances = balance_result["balances"]
                total_rub = balance_result.get("total_rub_equivalent", 0.0)
                balance_text = "\n".join([f"{currency}: {data['total']:.4f}" for currency, data in balances.items() if data["total"] > 0])
                return {"success": True, "balance": balance_text or "0.00", "currency": "Multi", "note": f"≈ {total_rub:.2f} ₽"}
            else:
                return {"success": False, "error": balance_result.get("error", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_xrocet_balance(self) -> Dict[str, Any]:
        try:
            stats = await self.repo.get_payments_stats()
            xrocet_revenue = stats.get('methods', {}).get('xrocet', {}).get('paid_revenue', 0.0)
            payment_handler = XRocetPayment(self.config.xrocet.api_key)
            ton_rate = await payment_handler.get_toncoin_to_rub_rate()
            ton_equivalent = xrocet_revenue / ton_rate if ton_rate > 0 else 0
            return {"success": True, "balance": f"{ton_equivalent:.4f}", "currency": "TON", "note": f"≈ {xrocet_revenue:.2f} ₽"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_crystalpay_balance(self) -> Dict[str, Any]:
        try:
            payment_handler = CrystalPayPayment(self.config.crystalpay.login, self.config.crystalpay.secret)
            balance_result = await payment_handler.get_balance() 
            if balance_result["success"]:
                 return {"success": True, "balance": balance_result.get("balance", "0"), "currency": balance_result.get("currency", "BTC"), "note": f"На шлюзе: {balance_result.get('balance', '0')} {balance_result.get('currency', 'BTC')}"}
            else:
                stats = await self.repo.get_payments_stats()
                crystal_revenue = stats.get('methods', {}).get('crystalpay', {}).get('paid_revenue', 0.0)
                return {"success": True, "balance": f"{crystal_revenue:.2f}", "currency": "RUB", "note": f"Выручка: {crystal_revenue:.2f} ₽"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_all_balances(self) -> Dict[str, Dict[str, Any]]:
        return {
            "lolz": await self.get_lolz_balance(),
            "cryptobot": await self.get_cryptobot_balance(),
            "xrocet": await self.get_xrocet_balance(),
            "crystalpay": await self.get_crystalpay_balance()
        }