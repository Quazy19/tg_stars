import hashlib
import hmac
import time
import logging
from typing import Tuple

import httpx

from config import Config

API_URL = "https://pay.crypt.bot/api/"
DEFAULT_RATE = 95.0

async def get_usdt_rub_rate(config: Config) -> float:
    api_token = config.cryptopay_token
    if not api_token:
        logging.warning("CryptoPay token not provided. Using default rate.")
        return DEFAULT_RATE

    headers = {
        "Crypto-Pay-API-Token": api_token
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}getExchangeRates", headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                rates = data["result"]
                for rate in rates:
                    if rate["source"] == "USDT" and rate["target"] == "RUB":
                        return float(rate["rate"])
    except Exception as e:
        logging.error(f"Failed to get exchange rates from CryptoBot: {e}")
    
    logging.warning(f"Falling back to default USDT-RUB rate: {DEFAULT_RATE}")
    return DEFAULT_RATE

async def create_cryptopay_invoice(config: Config, user_id: int, amount_rub: float, exchange_rate: float) -> Tuple[str, str]:
    api_token = config.cryptopay_token
    if not api_token:
        raise ValueError("CryptoPay API token is not configured.")

    amount_usd = round(amount_rub / exchange_rate, 2)
    
    headers = {
        "Content-Type": "application/json",
        "Crypto-Pay-API-Token": api_token
    }
    
    payload = {
        "asset": "USDT",
        "amount": str(amount_usd),
        "description": f"Пополнение баланса для пользователя {user_id}",
        "order_id": f"{user_id}_{int(time.time())}",
        "currency_type": "fiat",
        "fiat": "USD",
        "expires_in": 900
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_URL}createInvoice", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            result = data.get("result")
            return result.get('pay_url'), payload['order_id']
        else:
            raise Exception(f"CryptoPay API error: {data.get('error')}")

def check_cryptopay_signature(config: Config, request_body: bytes, signature_from_header: str) -> bool:
    api_token = config.cryptopay_token
    if not api_token:
        return False
        
    secret_key = hashlib.sha256(api_token.encode('utf-8')).digest()
    
    calculated_signature = hmac.new(
        key=secret_key, 
        msg=request_body, 
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(calculated_signature, signature_from_header)