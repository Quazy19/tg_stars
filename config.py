import os
from dataclasses import dataclass
from typing import List, Dict
from dotenv import load_dotenv

@dataclass
class Config:
    admin_ids: List[int]
    bot_token: str
    database_path: str
    img_url_main: str
    img_url_stars: str
    img_url_premium: str
    img_url_profile: str
    img_url_calculator: str
    welcome_description: str
    api_ton: str
    wallet_seed: str  # Изменено с mnemonic: List[str]
    fragment_cookies: Dict[str, str]
    fragment_hash: str
    fragment_public_key: str
    fragment_wallets: str
    fragment_address: str
    cryptopay_token: str
    lzt_token: str
    lzt_user_id: str
    crystalpay_login: str
    crystalpay_secret_key: str
    crystalpay_api_url: str
    ton_wallet_address: str
    min_payment_amount: int
    payment_timeout_seconds: int

def load_config(path: str = ".env"):
    load_dotenv(dotenv_path=path)

    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids_list = [int(admin_id.strip()) for admin_id in admin_ids_str.split(',') if admin_id.strip()]
    
    # Преобразуем MNEMONIC из "слово,слово" в "слово слово"
    mnemonic_str = os.getenv("MNEMONIC", "")
    wallet_seed_str = ' '.join([word.strip() for word in mnemonic_str.split(',') if word.strip()])

    fragment_cookies_dict = {
        'stel_ssid': os.getenv("STEL_SSID"),
        'stel_dt': os.getenv("STEL_DT"),
        'stel_ton_token': os.getenv("STEL_TON_TOKEN"),
        'stel_token': os.getenv("STEL_TOKEN"),
    }

    return Config(
        admin_ids=admin_ids_list,
        bot_token=os.getenv("BOT_TOKEN"),
        database_path=os.getenv("DATABASE_PATH", "database.db"),
        img_url_main=os.getenv("IMG_URL_MAIN"),
        img_url_stars=os.getenv("IMG_URL_STARS"),
        img_url_premium=os.getenv("IMG_URL_PREMIUM"),
        img_url_profile=os.getenv("IMG_URL_PROFILE"),
        img_url_calculator=os.getenv("IMG_URL_CALCULATOR"),
        welcome_description=os.getenv("WELCOME_DESCRIPTION", "").replace("\\n", "\n"),
        api_ton=os.getenv("API_TON"),
        wallet_seed=wallet_seed_str,  # Изменено
        fragment_cookies=fragment_cookies_dict,
        fragment_hash=os.getenv("FRAGMENT_HASH"),
        fragment_public_key=os.getenv("FRAGMENT_PUBLICKEY"),
        fragment_wallets=os.getenv("FRAGMENT_WALLETS"),
        fragment_address=os.getenv("FRAGMENT_ADDRES"),
        cryptopay_token=os.getenv("CRYPTOPAY_TOKEN"),
        lzt_token=os.getenv("LZT_TOKEN"),
        lzt_user_id=os.getenv("LZT_USER_ID"),
        crystalpay_login=os.getenv("CRYSTALPAY_LOGIN"),
        crystalpay_secret_key=os.getenv("CRYSTALPAY_SECRET_KEY"),
        crystalpay_api_url=os.getenv("CRYSTALPAY_API_URL"),
        ton_wallet_address=os.getenv("TON_WALLET_ADDRESS"),
        min_payment_amount=int(os.getenv("MIN_PAYMENT_AMOUNT", 10)),
        payment_timeout_seconds=int(os.getenv("PAYMENT_TIMEOUT_SECONDS", 900))
    )