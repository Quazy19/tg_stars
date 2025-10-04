import aiosqlite
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

class Repository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_or_create_user(self, telegram_id: int, username: str) -> aiosqlite.Row:
        cursor = await self.db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        if not user:
            await self.db.execute(
                "INSERT INTO users (telegram_id, username) VALUES (?, ?)",
                (telegram_id, username)
            )
            await self.db.commit()
            cursor = await self.db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user = await cursor.fetchone()
        return user

    async def get_user_by_id_or_username(self, user_input: str) -> Optional[aiosqlite.Row]:
        params = (user_input,)
        query = "SELECT * FROM users WHERE telegram_id = ?" if user_input.isdigit() else "SELECT * FROM users WHERE username = ?"
        cursor = await self.db.execute(query, params)
        return await cursor.fetchone()
    
    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
        return await cursor.fetchone()

    async def update_user_block_status(self, user_id: int, is_blocked: bool) -> None:
        await self.db.execute("UPDATE users SET is_blocked = ? WHERE telegram_id = ?", (int(is_blocked), user_id))
        await self.db.commit()

    async def update_user_balance(self, user_id: int, amount: float, operation: str = 'add') -> None:
        op_char = '+' if operation == 'add' else '-'
        await self.db.execute(f"UPDATE users SET balance = balance {op_char} ? WHERE telegram_id = ?", (amount, user_id))
        await self.db.commit()

    async def update_user_discount(self, user_id: int, discount: Optional[float]) -> None:
        await self.db.execute("UPDATE users SET discount = ? WHERE telegram_id = ?", (discount, user_id))
        await self.db.commit()
        
    async def get_all_users_for_broadcast(self) -> List[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT telegram_id FROM users WHERE is_blocked = 0")
        return await cursor.fetchall()
        
    async def is_user_blocked(self, user_id: int) -> bool:
        cursor = await self.db.execute("SELECT is_blocked FROM users WHERE telegram_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row and row['is_blocked'] == 1

    async def get_total_stars_bought(self, user_id: int) -> int:
        cursor = await self.db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM purchase_history WHERE user_id = ? AND purchase_type = 'stars'",
            (user_id,)
        )
        return (await cursor.fetchone())[0]

    async def get_total_top_up(self, user_id: int) -> float:
        cursor = await self.db.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE user_id = ? AND status = 'paid'", (user_id,))
        return (await cursor.fetchone())[0]

    async def mark_old_payments_as_expired(self, user_id: int) -> None:
        fifteen_minutes_ago = (datetime.utcnow() - timedelta(minutes=15)).isoformat()
        await self.db.execute(
            "UPDATE payments SET status = 'expired' WHERE user_id = ? AND status = 'pending' AND created_at <= ?",
            (user_id, fifteen_minutes_ago)
        )
        await self.db.commit()

    async def get_active_payment(self, user_id: int) -> Optional[aiosqlite.Row]:
        cursor = await self.db.execute(
            "SELECT * FROM payments WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        return await cursor.fetchone()

    async def create_payment(self, order_id: str, user_id: int, message_id: int, amount_rub: float, payment_system: str, invoice_url: Optional[str] = None, external_invoice_id: Optional[str] = None) -> None:
        await self.db.execute(
            "INSERT INTO payments (uuid, user_id, message_id, amount, payment_system, invoice_url, external_invoice_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (order_id, user_id, message_id, amount_rub, payment_system, invoice_url, external_invoice_id)
        )
        await self.db.commit()

    async def update_payment_status(self, order_id: str, new_status: str) -> bool:
        cursor = await self.db.execute(
            "UPDATE payments SET status = ? WHERE uuid = ? AND status = 'pending'",
            (new_status, order_id)
        )
        await self.db.commit()
        return cursor.rowcount > 0
        
    async def get_user_payments_page(self, user_id: int, page: int, page_size: int) -> List[aiosqlite.Row]:
        offset = (page - 1) * page_size
        cursor = await self.db.execute(
            "SELECT uuid, amount, created_at, status, payment_system FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, page_size, offset)
        )
        return await cursor.fetchall()
        
    async def count_user_payments(self, user_id: int) -> int:
        cursor = await self.db.execute("SELECT COUNT(*) FROM payments WHERE user_id = ?", (user_id,))
        return (await cursor.fetchone())[0]
        
    async def get_all_pending_payments(self) -> List[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT * FROM payments WHERE status = 'pending'")
        return await cursor.fetchall()

    async def process_successful_payment(self, order_id: str) -> Optional[Dict[str, Any]]:
        async with self.db.execute("BEGIN") as cursor:
            await cursor.execute("SELECT * FROM payments WHERE uuid = ?", (order_id,))
            payment = await cursor.fetchone()

            if not payment or payment["status"] != 'pending':
                return None
            
            await cursor.execute("UPDATE payments SET status = 'paid' WHERE uuid = ?", (order_id,))
            amount = float(payment["amount"])
            await cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (amount, payment["user_id"]))
        await self.db.commit()
        return dict(payment)

    async def add_purchase_to_history(self, user_id: int, p_type: str, desc: str, amount: int, cost: float, profit: float = 0) -> None:
        await self.db.execute(
            "INSERT INTO purchase_history (user_id, purchase_type, item_description, amount, cost, profit) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, p_type, desc, amount, cost, profit)
        )
        await self.db.commit()

    async def get_promo_by_code(self, code: str) -> Optional[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT * FROM promo_codes WHERE code = ? AND is_active = 1", (code,))
        return await cursor.fetchone()

    async def check_promo_usage_by_user(self, user_id: int, promo_id: int) -> bool:
        cursor = await self.db.execute("SELECT 1 FROM promo_history WHERE user_id = ? AND promo_code_id = ?", (user_id, promo_id))
        return await cursor.fetchone() is not None

    async def activate_promo_for_user(self, user_id: int, promo: aiosqlite.Row) -> None:
        await self.db.execute("UPDATE promo_codes SET current_uses = current_uses + 1 WHERE id = ?", (promo['id'],))
        await self.db.execute("INSERT INTO promo_history (user_id, promo_code_id) VALUES (?, ?)", (user_id, promo['id']))
        if promo['promo_type'] == 'discount':
            await self.update_user_discount(user_id, promo['value'])
        else:
            await self.update_user_balance(user_id, promo['value'], 'add')
        await self.db.commit()

    async def create_promo_code(self, code: str, p_type: str, value: float, max_uses: int = None, expires_at: str = None) -> None:
        await self.db.execute(
            "INSERT INTO promo_codes (code, promo_type, value, max_uses, expires_at, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (code, p_type, value, max_uses, expires_at)
        )
        await self.db.commit()

    async def get_active_promo_codes(self) -> List[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT code FROM promo_codes WHERE is_active = 1")
        return await cursor.fetchall()
        
    async def get_all_promo_codes(self) -> List[aiosqlite.Row]:
        cursor = await self.db.execute("SELECT code FROM promo_codes")
        return await cursor.fetchall()
        
    async def delete_promo_code(self, code: str) -> None:
        await self.db.execute("DELETE FROM promo_codes WHERE code = ?", (code,))
        await self.db.commit()
        
    async def delete_expired_promos(self) -> None:
        now_utc_iso = datetime.utcnow().isoformat()
        await self.db.execute("DELETE FROM promo_codes WHERE expires_at IS NOT NULL AND expires_at < ?", (now_utc_iso,))
        await self.db.commit()
    
    async def get_setting(self, key: str) -> Optional[str]:
        cursor = await self.db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row['value'] if row else None

    async def get_multiple_settings(self, keys: List[str]) -> Dict[str, str]:
        placeholders = ','.join('?' for _ in keys)
        cursor = await self.db.execute(f"SELECT key, value FROM settings WHERE key IN ({placeholders})", keys)
        rows = await cursor.fetchall()
        return {r['key']: r['value'] for r in rows}

    async def update_setting(self, key: str, value: Any) -> None:
        await self.db.execute("UPDATE settings SET value = ? WHERE key = ?", (str(value), key))
        await self.db.commit()

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