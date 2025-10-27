from aiogram.fsm.state import State, StatesGroup

class AdminSettingsStates(StatesGroup):
    waiting_for_start_text = State()
    waiting_for_purchase_text = State()
    waiting_for_support_contact = State()
    waiting_for_channel_forward = State()

class AdminUserManagementStates(StatesGroup):
    waiting_for_user = State()
    user_menu = State()
    giving_balance_amount = State()
    giving_balance_confirm = State()
    taking_balance_amount = State()
    taking_balance_confirm = State()

class PromoStates(StatesGroup):
    menu = State()
    create_choose_name = State()
    create_input_name = State()
    create_choose_type = State()
    create_input_sum = State()
    create_choose_limit = State()
    create_input_uses = State()
    create_input_time = State()
    delete_choose = State()
    show_active = State()
    show_stats = State()

class PriceStates(StatesGroup):
    menu = State()
    stars_show = State()
    stars_input = State()
    stars_confirm = State()
    premium_choose = State()
    premium_show = State()
    premium_input = State()
    premium_confirm = State()

class BroadcastConstructorStates(StatesGroup):
    waiting_for_initial_post = State()
    menu = State()
    editing_text = State()
    editing_media = State()
    adding_button_text = State()
    adding_button_url = State()