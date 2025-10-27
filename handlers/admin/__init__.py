from aiogram import Router, F
from . import panel, user_management, promos, price_control, settings, broadcast, fragment_status

def get_admin_router(admin_ids: list[int]) -> Router:
    router = Router()
    router.message.filter(F.from_user.id.in_(admin_ids))
    router.callback_query.filter(F.from_user.id.in_(admin_ids))
    
    router.include_router(panel.router)
    router.include_router(user_management.router)
    router.include_router(promos.router)
    router.include_router(price_control.router)
    router.include_router(settings.router)
    router.include_router(broadcast.router)
    router.include_router(fragment_status.router)
    
    return router