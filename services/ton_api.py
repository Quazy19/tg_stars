import httpx
from config import Config

async def get_ton_balance(wallet_address: str) -> tuple[float, str | None]:
    if not wallet_address or "сюда" in wallet_address:
        return 0.0, 'Адрес кошелька не настроен'

    address_str = str(wallet_address)
    if address_str.startswith('Address<') and address_str.endswith('>'):
        address_str = address_str[8:-1]  

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://toncenter.com/api/v2/getAddressBalance?address={address_str}")
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    balance_nano = int(data['result'])
                    balance_ton = balance_nano / 1_000_000_000
                    return balance_ton, None
                else:
                    return 0.0, data.get('error', 'API Toncenter вернуло ошибку')
            else:
                return 0.0, f'Ошибка HTTP: {response.status_code}'
    except Exception as e:

        return 0.0, str(e)
