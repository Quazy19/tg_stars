import httpx
from config import Config

async def check_lzt_payment_status(config: Config, order_id: str) -> tuple[bool, float]:
    headers = {
        'accept': 'application/json',
        'authorization': f'Bearer {config.lzt_token}'
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get('https://prod-api.lzt.market/user/payments', headers=headers)

        if response.status_code == 200:
            data = response.json()
            if 'payments' in data:
                payments_data = data['payments']
                
                if isinstance(payments_data, dict):
                    for _, payment in payments_data.items():
                        if isinstance(payment, dict):
                            payment_data_inner = payment.get('data', {})
                            if isinstance(payment_data_inner, dict) and payment_data_inner.get('comment') == order_id:
                                if payment.get('operation_type') == 'receiving_money' and payment.get('payment_status') == 'success_in':
                                    return True, float(payment.get('incoming_sum', '0.00'))
                                
                elif isinstance(payments_data, list):
                    for payment in payments_data:
                         if isinstance(payment, dict):
                            payment_data_inner = payment.get('data', {})
                            if isinstance(payment_data_inner, dict) and payment_data_inner.get('comment') == order_id:
                                if payment.get('operation_type') == 'receiving_money' and payment.get('payment_status') == 'success_in':
                                    return True, float(payment.get('incoming_sum', '0.00'))

        return False, 0
    except Exception:
        return False, 0

def create_lzt_payment_link(config: Config, amount: float, order_id: str) -> str:
    return f"https://lzt.market/balance/transfer?user_id={config.lzt_user_id}&hold=0&amount={amount}&comment={order_id}"