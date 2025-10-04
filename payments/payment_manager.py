import time
import random

from config import Config

class PaymentManager:
    def __init__(self, config: Config):
        self.config = config

    def generate_order_id(self) -> str:
        timestamp = int(time.time())
        random_num = random.randint(1000, 9999)
        return f"starbot-{timestamp}-{random_num}"