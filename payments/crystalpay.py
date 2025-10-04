import httpx
from config import Config

async def create_crystalpay_invoice(config: Config, amount: float, order_id: str) -> tuple[str | None, str | None]:
    headers = {'Content-Type': 'application/json'}
    data = {
        "auth_login": config.crystalpay_login,
        "auth_secret": config.crystalpay_secret_key,
        "amount": amount,
        "type": "purchase",
        "lifetime": config.payment_timeout_seconds // 60,
        "extra": order_id
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{config.crystalpay_api_url}/invoice/create/", headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                if not result.get('error'):
                    return result.get('url'), result.get('id')
    except Exception:
        return None, None
    return None, None

async def check_crystalpay_invoice(config: Config, invoice_id: str) -> tuple[bool, float]:
    headers = {'Content-Type': 'application/json'}
    data = {
        "auth_login": config.crystalpay_login,
        "auth_secret": config.crystalpay_secret_key,
        "id": invoice_id
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{config.crystalpay_api_url}/invoice/status/", headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                if not result.get('error'):
                    state = result.get('state', '')
                    amount = float(result.get('amount', 0))
                    return state in ['payed', 'paid'], amount
    except Exception:
        return False, 0
    return False, 0