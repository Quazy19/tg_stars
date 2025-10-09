import os
from dataclasses import dataclass
from typing import List, Dict
from dotenv import load_dotenv, find_dotenv
import logging

logging.basicConfig(level=logging.INFO)

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
    wallet_seed: str 
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
    dotenv_path = find_dotenv(path, usecwd=True)
    if dotenv_path:
        logging.info(f"Configuration: Found and loading .env file at: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path)
    else:
        logging.warning("Configuration: .env file not found. Relying on system environment variables.")

    admin_ids_str_raw = os.getenv("ADMIN_IDS")
    bot_token_raw = os.getenv("BOT_TOKEN")
    
    admin_ids_str = admin_ids_str_raw if admin_ids_str_raw is not None else ""
    
    admin_ids_list = []
    if admin_ids_str:
        clean_str = admin_ids_str.replace(' ', '').replace(';', ',').replace('|', ',')
        parts = [part.strip() for part in clean_str.split(',') if part.strip()]
        
        for part in parts:
            try:
                admin_ids_list.append(int(part))
            except ValueError:
                logging.warning(f"Configuration Warning: Invalid non-integer ADMIN_ID skipped: '{part}'")
    
    if admin_ids_list:
        logging.info(f"DEBUG: ADMIN_IDS (Parsed) = {admin_ids_list}")
            
    
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
        bot_token=bot_token_raw,
        database_path=os.getenv("DATABASE_PATH", "database.db"),
        img_url_main=os.getenv("IMG_URL_MAIN"),
        img_url_stars=os.getenv("IMG_URL_STARS"),
        img_url_premium=os.getenv("IMG_URL_PREMIUM"),
        img_url_profile=os.getenv("IMG_URL_PROFILE"),
        img_url_calculator=os.getenv("IMG_URL_CALCULATOR"),
        welcome_description=os.getenv("WELCOME_DESCRIPTION", "").replace("\\n", "\n"),
        api_ton=os.getenv("API_TON"),
        wallet_seed=wallet_seed_str, 
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
