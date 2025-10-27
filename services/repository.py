import aiosqlite
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class Repository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    # --- User Methods ---
    async def get_or_create_user(self, telegram_id: int, username: str, first_name: str = None, last_name: str = None) -> aiosqlite.Row:
        user = await self.get_user(telegram_id)
        if not user:
            await self.db.execute(
                "INSERT INTO users (telegram_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                (telegram_id, username, first_name, last_name)
            )
            await self.db.commit()
            user = await self.get_user(telegram_id)
        return user

    async def get_user_by_id_or_username(self, user_input: str) -> Optional[aiosqlite.Row]:
        query = "SELECT * FROM users WHERE telegram_id = ?" if user_input.isdigit() else "SELECT * FROM users WHERE username = ?"
        cursor = await self.db.execute(query, (user_input,))
        return await cursor.fetchone()
    
    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
        return await cursor.fetchone()

    async def update_user_block_status(self, user_id: int, is_blocked: bool):
        await self.db.execute("UPDATE users SET is_blocked = ? WHERE telegram_id = ?", (int(is_blocked), user_id))
        await self.db.commit()

    async def update_user_balance(self, user_id: int, amount: float, operation: str = 'add'):
        op_char = '+' if operation == 'add' else '-'
        await self.db.execute(f"UPDATE users SET balance = balance {op_char} ? WHERE telegram_id = ?", (amount, user_id))
        await self.db.commit()

    async def update_user_discount(self, user_id: int, discount: Optional[float]):
        await self.db.execute("UPDATE users SET discount = ? WHERE telegram_id = ?", (discount, user_id))
        await self.db.commit()
        
    async def get_all_users_for_broadcast(self) -> List[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT telegram_id FROM users WHERE is_blocked = 0")
        return await cursor.fetchall()
        
    async def is_user_blocked(self, user_id: int) -> bool:
        cursor = await self.db.execute("SELECT is_blocked FROM users WHERE telegram_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row and row['is_blocked'] == 1

    # --- Purchase History & Stars Methods ---
    async def get_total_stars_bought(self, user_id: int) -> int:
        cursor = await self.db.execute("SELECT COALESCE(SUM(amount), 0) FROM purchase_history WHERE user_id = ? AND purchase_type = 'stars'", (user_id,))
        return (await cursor.fetchone())[0]

    async def add_purchase_to_history(self, user_id: int, p_type: str, desc: str, amount: int, cost: float, profit: float = 0):
        await self.db.execute(
            "INSERT INTO purchase_history (user_id, purchase_type, item_description, amount, cost, profit) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, p_type, desc, amount, cost, profit)
        )
        await self.db.commit()

    # --- Payment Methods ---
    async def create_payment(self, user_id: int, payment_method: str, amount: float, fee_amount: float, total_amount: float, invoice_id: str, expires_at: datetime, crypto_asset: str = None, message_id: int = None, chat_id: int = None, payload_id: str = None):
        await self.db.execute(
            "INSERT INTO payments (user_id, payment_method, amount, fee_amount, total_amount, invoice_id, payload_id, crypto_asset, expires_at, message_id, chat_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, payment_method, amount, fee_amount, total_amount, invoice_id, payload_id, crypto_asset, expires_at, message_id, chat_id)
        )
        await self.db.commit()

    async def get_pending_payments(self) -> List[Dict]:
        cursor = await self.db.execute("SELECT * FROM payments WHERE status = 'pending' AND expires_at > CURRENT_TIMESTAMP")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_payment_status(self, invoice_id: str, status: str) -> bool:
        cursor = await self.db.execute("UPDATE payments SET status = ? WHERE invoice_id = ? AND status != ?", (status, invoice_id, status))
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_user_active_payment(self, user_id: int) -> Optional[Dict]:
        cursor = await self.db.execute("SELECT * FROM payments WHERE user_id = ? AND status = 'pending' AND expires_at > CURRENT_TIMESTAMP ORDER BY created_at DESC LIMIT 1", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
        
    async def get_payment_by_invoice_id(self, invoice_id: str) -> Optional[Dict]:
        cursor = await self.db.execute("SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
        
    async def process_successful_payment(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        async with self.db.execute("BEGIN") as cursor:
            await cursor.execute("SELECT * FROM payments WHERE invoice_id = ? AND status = 'pending'", (invoice_id,))
            payment = await cursor.fetchone()
            if not payment:
                return None
            await cursor.execute("UPDATE payments SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
            await cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (payment["amount"], payment["user_id"]))
        await self.db.commit()
        return dict(payment)

    # --- Promo Methods ---
    async def get_promo_by_code(self, code: str) -> Optional[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT * FROM promo_codes WHERE code = ? AND is_active = 1", (code,))
        return await cursor.fetchone()

    async def check_promo_usage_by_user(self, user_id: int, promo_id: int) -> bool:
        cursor = await self.db.execute("SELECT 1 FROM promo_history WHERE user_id = ? AND promo_code_id = ?", (user_id, promo_id))
        return await cursor.fetchone() is not None

    async def activate_promo_for_user(self, user_id: int, promo: aiosqlite.Row):
        await self.db.execute("UPDATE promo_codes SET current_uses = current_uses + 1 WHERE id = ?", (promo['id'],))
        await self.db.execute("INSERT INTO promo_history (user_id, promo_code_id) VALUES (?, ?)", (user_id, promo['id']))
        if promo['promo_type'] == 'discount':
            await self.update_user_discount(user_id, promo['value'])
        else:
            await self.update_user_balance(user_id, promo['value'], 'add')
        await self.db.commit()

    # --- Settings Methods ---
    async def get_setting(self, key: str) -> Optional[str]:
        cursor = await self.db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row['value'] if row else None

    async def get_multiple_settings(self, keys: List[str]) -> Dict[str, str]:
        placeholders = ','.join('?' for _ in keys)
        cursor = await self.db.execute(f"SELECT key, value FROM settings WHERE key IN ({placeholders})", keys)
        rows = await cursor.fetchall()
        return {r['key']: r['value'] for r in rows}

    async def update_setting(self, key: str, value: Any):
        await self.db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (str(key), str(value)))
        await self.db.commit()

    # --- Stats Methods ---
    async def get_bot_statistics(self) -> Dict[str, int]:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        queries = {
            "total_users": "SELECT COUNT(id) FROM users",
            "month_users": f"SELECT COUNT(id) FROM users WHERE created_at >= '{month_ago}'",
            "day_stars": f"SELECT COALESCE(SUM(amount), 0) FROM purchase_history WHERE purchase_type = 'stars' AND created_at >= '{today_start}'",
            "month_stars": f"SELECT COALESCE(SUM(amount), 0) FROM purchase_history WHERE purchase_type = 'stars' AND created_at >= '{month_ago}'",
            "total_stars": "SELECT COALESCE(SUM(amount), 0) FROM purchase_history WHERE purchase_type = 'stars'"
        }
        results = {}
        for key, query in queries.items():
            cursor = await self.db.execute(query)
            results[key] = (await cursor.fetchone())[0]
        return results

    async def get_profit_statistics(self) -> Dict[str, float]:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        queries = {
            "day_profit": f"SELECT COALESCE(SUM(profit), 0) FROM purchase_history WHERE created_at >= '{today_start}'",
            "month_profit": f"SELECT COALESCE(SUM(profit), 0) FROM purchase_history WHERE created_at >= '{month_ago}'",
            "total_profit": "SELECT COALESCE(SUM(profit), 0) FROM purchase_history",
            "day_revenue": f"SELECT COALESCE(SUM(cost), 0) FROM purchase_history WHERE created_at >= '{today_start}'",
            "month_revenue": f"SELECT COALESCE(SUM(cost), 0) FROM purchase_history WHERE created_at >= '{month_ago}'",
            "total_revenue": "SELECT COALESCE(SUM(cost), 0) FROM purchase_history"
        }
        results = {}
        for key, query in queries.items():
            cursor = await self.db.execute(query)
            results[key] = float((await cursor.fetchone())[0])
        return results

    async def get_payments_stats(self, days: int = None) -> dict:
        base_query = "SELECT COUNT(*) as total_payments, COALESCE(SUM(amount), 0) as total_revenue, payment_method, status FROM payments "
        
        if days:
            date_filter = f"WHERE created_at >= datetime('now', '-{days} days')"
            query = base_query + date_filter + " GROUP BY payment_method, status"
        else:
            query = base_query + " GROUP BY payment_method, status"
        
        cursor = await self.db.execute(query)
        rows = await cursor.fetchall()
        
        stats = {'total_payments': 0, 'total_revenue': 0.0, 'paid_payments': 0, 'paid_revenue': 0.0, 'methods': {}}
        
        for row in rows:
            method, status, payments, revenue = row['payment_method'], row['status'], row['total_payments'], row['total_revenue']
            if method not in stats['methods']:
                stats['methods'][method] = {'total_payments': 0, 'total_revenue': 0.0, 'paid_payments': 0, 'paid_revenue': 0.0}
            
            stats['methods'][method]['total_payments'] += payments
            stats['methods'][method]['total_revenue'] += revenue
            stats['total_payments'] += payments
            stats['total_revenue'] += revenue
            
            if status == 'paid':
                stats['methods'][method]['paid_payments'] += payments
                stats['methods'][method]['paid_revenue'] += revenue
                stats['paid_payments'] += payments
                stats['paid_revenue'] += revenue
        return stats