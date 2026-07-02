import time


# ============================================
# USER STATES
# ============================================

# Structure:
#
# user_states = {
#
#     123456789: {
#         "mode": "waiting_photo",
#         "created": 1720000000,
#         "data": {}
#     }
#
# }

user_states = {}


# ============================================
# TIMEOUT
# ============================================

STATE_TIMEOUT = 600   # 10 minutes


# ============================================
# CLEAN EXPIRED STATES
# ============================================

def cleanup_states():

    now = time.time()

    expired = []

    for user_id, state in user_states.items():

        created = state.get("created", now)

        if now - created > STATE_TIMEOUT:
            expired.append(user_id)

    for uid in expired:
        del user_states[uid]


# ============================================
# CREATE / UPDATE STATE
# ============================================

def set_state(user_id, mode, data=None):

    cleanup_states()

    if data is None:
        data = {}

    user_states[user_id] = {

        "mode": mode,

        "created": time.time(),

        "data": data

    }


# ============================================
# GET STATE
# ============================================

def get_state(user_id):

    cleanup_states()

    return user_states.get(user_id)


# ============================================
# GET MODE
# ============================================

def get_mode(user_id):

    state = get_state(user_id)

    if not state:
        return None

    return state["mode"]


# ============================================
# GET DATA
# ============================================

def get_data(user_id):

    state = get_state(user_id)

    if not state:
        return {}

    return state["data"]


# ============================================
# UPDATE DATA
# ============================================

def update_data(user_id, **kwargs):

    state = get_state(user_id)

    if not state:
        return

    state["data"].update(kwargs)

    state["created"] = time.time()


# ============================================
# CLEAR STATE
# ============================================

def clear_state(user_id):

    if user_id in user_states:
        del user_states[user_id]


# ============================================
# CHECK ACTIVE
# ============================================

def has_state(user_id):

    cleanup_states()

    return user_id in user_states


# ============================================
# CANCEL CURRENT OPERATION
# ============================================

def cancel(user_id):

    clear_state(user_id)


# ============================================
# AVAILABLE MODES
# ============================================
# ============================================
# ANALYTICS
# ============================================

MODE_WAITING_ANALYTICS_DATE = "waiting_analytics_date"


# ============================================
# IMAGE
# ============================================

MODE_WAITING_PHOTO = "waiting_photo"

MODE_WAITING_IMAGE_NAME = "waiting_image_name"


# ============================================
# DELETE IMAGE
# ============================================

MODE_WAITING_DELETE_NAME = "waiting_delete_name"

MODE_WAITING_DELETE_CONFIRM = "waiting_delete_confirm"


# ============================================
# RENAME IMAGE
# ============================================

MODE_WAITING_RENAME_OLD = "waiting_rename_old"

MODE_WAITING_RENAME_NEW = "waiting_rename_new"


# ============================================
# ADD STOCK
# ============================================

MODE_WAITING_ADDSTOCK_ITEM = "waiting_addstock_item"

MODE_WAITING_ADDSTOCK_SIZE = "waiting_addstock_size"

MODE_WAITING_ADDSTOCK_QTY = "waiting_addstock_qty"


# ============================================
# REMOVE STOCK
# ============================================

MODE_WAITING_REMOVESTOCK_ITEM = "waiting_removestock_item"

MODE_WAITING_REMOVESTOCK_SIZE = "waiting_removestock_size"

MODE_WAITING_REMOVESTOCK_QTY = "waiting_removestock_qty"
MODE_WAITING_ADD_IMAGE = "waiting_add_image"
MODE_WAITING_ADD_ITEM_ID = "waiting_add_item_id"
MODE_WAITING_ADD_NAME = "waiting_add_name"
MODE_WAITING_ADD_SIZE_STOCK = "waiting_add_size_stock"


MODE_WAITING_DELETESTOCK_ITEM = "waiting_deletestock_item"
MODE_WAITING_DELETESTOCK_SIZE = "waiting_deletestock_size"

# ============================================
# DEBUG
# ============================================

def print_states():

    print("\n========== ACTIVE STATES ==========")

    if not user_states:

        print("No active users.")

    else:

        for uid, state in user_states.items():

            print(uid)

            print(" Mode :", state["mode"])

            print(" Data :", state["data"])

            print()

    print("===================================\n")


