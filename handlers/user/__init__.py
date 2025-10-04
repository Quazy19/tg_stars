from aiogram import Router
from middlewares.filters import CheckSubscriptionFilter
from . import start, profile, calculator, purchase_stars, purchase_premium

def get_user_router() -> Router:
    router = Router()
    
    router.message.filter(CheckSubscriptionFilter())
    router.callback_query.filter(CheckSubscriptionFilter())
    
    router.include_router(start.router)
    router.include_router(profile.router)
    router.include_router(calculator.router)
    router.include_router(purchase_stars.router)
    router.include_router(purchase_premium.router)
    return router