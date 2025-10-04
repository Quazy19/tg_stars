from aiogram.fsm.state import State, StatesGroup

class TopupCryptoPayStates(StatesGroup):
    waiting_for_amount = State()

class TopupLztStates(StatesGroup):
    waiting_for_amount = State()
    
class TopupCrystalPayStates(StatesGroup):
    waiting_for_amount = State()

class PromoUserStates(StatesGroup):
    waiting_for_code = State()
    
class BuyStarsGiftStates(StatesGroup):
    waiting_for_recipient = State()
    waiting_for_gift_amount = State()

class BuyStarsSelfStates(StatesGroup):
    waiting_for_self_amount = State()

class BuyStarsConfirmStates(StatesGroup):
    waiting_for_confirm = State()
    waiting_for_gift_confirm = State()

class BuyPremiumStates(StatesGroup):
    waiting_for_gift_recipient = State()
    waiting_for_self_plan = State()
    waiting_for_gift_plan = State()
    waiting_for_self_confirm = State()
    waiting_for_gift_confirm = State()

class CalculatorStates(StatesGroup):
    waiting_for_stars_amount = State()
    waiting_for_rub_amount = State()