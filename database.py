import aiosqlite
import logging
from datetime import datetime

async def init_db(database_path: str):
    async with aiosqlite.connect(database_path) as db:
        db.row_factory = aiosqlite.Row
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance REAL DEFAULT 0.0,
                is_admin INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                discount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                payment_method TEXT,
                amount REAL NOT NULL,
                fee_amount REAL,
                total_amount REAL,
                invoice_id TEXT UNIQUE NOT NULL,
                payload_id TEXT,
                crypto_asset TEXT,
                status TEXT DEFAULT 'pending',
                message_id INTEGER,
                chat_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS purchase_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                purchase_type TEXT NOT NULL,
                item_description TEXT NOT NULL,
                amount INTEGER,
                cost REAL NOT NULL,
                profit REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                promo_type TEXT NOT NULL,
                value REAL NOT NULL,
                max_uses INTEGER,
                current_uses INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                promo_code_id INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (promo_code_id) REFERENCES promo_codes(id) ON DELETE CASCADE
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        default_settings = {
            'star_price': '1.8',
            'premium_price_0': '799',
            'premium_price_1': '1499',
            'premium_price_2': '2499',
            'maintenance_mode': '0',
            'start_text': '<b>🖐 Добро пожаловать</b>\n\n🚀 У нас моментальная доставка 24/7\n📱 Без KYC и верификаций\n💰 Оплата любым способом',
            'purchase_success_text': 'Спасибо за покупку ✅\nЗвёзды придут в течении 5 минут ⭐️',
            'news_channel_id': '',
            'news_channel_link': '',
            'force_subscribe': '0',
            'support_contact': '',
            'fragment_token': '',
            'fragment_token_expires_at': '',
            'fragment_token_last_update': '',
            'lolz_fee': '7.0',
            'cryptobot_fee': '5.0',
            'xrocet_fee': '3.0',
            'crystalpay_fee': '4.0'
        }
        
        for key, value in default_settings.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

        await db.commit()
        logging.info("База данных инициализирована с новой схемой.")

async def get_db_connection(database_path: str):
    db = await aiosqlite.connect(database_path)
    db.row_factory = aiosqlite.Row
    return db