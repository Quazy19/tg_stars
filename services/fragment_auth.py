import httpx
import logging
from datetime import datetime, timedelta
from config import Config
from services.repository import Repository

class FragmentAuth:
    def __init__(self, config: Config):
        self.config = config
        self.url = f"https://fragment.com/api?hash={self.config.fragment.hash}"
        self.base_headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://fragment.com",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "X-Requested-With": "XMLHttpRequest",
        }

    async def check_auth_status(self) -> bool:
        try:
            async with httpx.AsyncClient(cookies=self.config.fragment.cookies, headers=self.base_headers, timeout=10.0) as client:
                response = await client.get("https://fragment.com/stars")
                return response.status_code == 200 and "login" not in response.url.path
        except Exception as e:
            logging.error(f"Failed to check Fragment auth status: {e}")
            return False

    async def get_wallet_balance(self) -> tuple[float, str | None]:
        try:
            async with httpx.AsyncClient(cookies=self.config.fragment.cookies, headers=self.base_headers, timeout=10.0) as client:
                response = await client.get("https://fragment.com/wallet")
                if response.status_code == 200:
                    return 0.0, "Balance parsing not implemented"
                else:
                    return 0.0, f"HTTP {response.status_code}"
        except Exception as e:
            logging.error(f"Failed to get Fragment wallet balance: {e}")
            return 0.0, str(e)

    async def refresh_token_if_needed(self, repo: Repository) -> bool:
        try:
            token_expires = await repo.get_setting('fragment_token_expires_at')
            if not token_expires:
                return await self._refresh_token(repo)
            
            expires_dt = datetime.fromisoformat(token_expires)
            if datetime.utcnow() >= expires_dt - timedelta(hours=1):
                return await self._refresh_token(repo)
            
            return True
        except Exception as e:
            logging.error(f"Failed to check token expiry: {e}")
            return False

    async def _refresh_token(self, repo: Repository) -> bool:
        try:
            await repo.update_setting('fragment_token_last_update', datetime.utcnow().isoformat())
            logging.info("Fragment token check completed")
            return True
        except Exception as e:
            logging.error(f"Failed to update Fragment token timestamp: {e}")
            return False