import json
import os
import gspread
from datetime import datetime

# =========================
# PATH SAFE LOAD
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "google_sheet_url.json")
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")


def load_sheet_url():
    try:
        with open(JSON_PATH, "r") as f:
            data = json.load(f)

        url = data.get("sheet_url")

        if not url:
            raise ValueError("sheet_url missing in JSON")

        print("✅ Sheet URL loaded")
        return url

    except Exception as e:
        print("❌ JSON LOAD ERROR:", e)
        raise


# =========================
# GOOGLE SHEETS CONNECT
# =========================

gc = gspread.service_account(filename=CREDS_PATH)
sheet_url = load_sheet_url()
sh = gc.open_by_url(sheet_url)

sheet1 = sh.worksheet("tCustomers")
sheet2 = sh.worksheet("tOrders")


# ==================================================
# ORDER ID FUNCTIONS (FIXED + SAFE)
# ==================================================

def generate_order_id():
    """
    Generate next Order ID safely
    Format: ORD000001
    """

    try:
        values = sheet1.col_values(2)  # column B = order_id

        nums = []

        for v in values[1:]:  # skip header

            if not v:
                continue

            v = str(v).strip()

            if v.startswith("ORD"):
                try:
                    nums.append(int(v.replace("ORD", "")))
                except:
                    continue

        next_number = max(nums, default=0) + 1

        return f"ORD{next_number:06d}"

    except Exception as e:
        print("❌ GENERATE ORDER ID ERROR:", e)
        raise


def order_exists(order_id):
    """
    Check if order exists in tCustomers
    """

    try:
        values = sheet1.col_values(2)

        order_id = str(order_id).strip()

        return any(str(v).strip() == order_id for v in values if v)

    except Exception as e:
        print("❌ ORDER CHECK ERROR:", e)
        raise


# =========================
# SHEET 1 - CUSTOMERS
# =========================

def save_package(p):

    try:

        total_qty = 0

        for line in p["shirts"]:

            tokens = line.split()

            if len(tokens) < 3:
                continue

            pairs = list(zip(tokens[1::2], tokens[2::2]))

            for size, qty in pairs:

                if qty.isdigit():
                    total_qty += int(qty)

        sheet1.append_row([

            p.get("name", ""),

            # ORDER SYSTEM
            p.get("order_id", ""),
            p.get("cancel_on", ""),

            p.get("address", ""),
            p.get("phone", ""),
            total_qty,
            p.get("price", ""),
            datetime.now().isoformat(),
            p.get("age", ""),
            p.get("gender", ""),
            p.get("ads_source", "")

        ])

    except Exception as e:
        print("❌ SHEET1 ERROR:", e)
        raise


# =========================
# SHEET 2 - ORDERS
# =========================

def save_shirt_details(p):

    try:

        rows = []

        customer = p.get("name", "")
        ts = datetime.now().isoformat()

        for line in p["shirts"]:

            tokens = line.split()

            if len(tokens) < 3:
                continue

            shirt = tokens[0]

            pairs = list(zip(tokens[1::2], tokens[2::2]))

            for size, qty in pairs:

                if qty.isdigit():

                    rows.append([

                        customer,

                        # ORDER SYSTEM
                        p.get("order_id", ""),
                        p.get("cancel_on", ""),

                        shirt,
                        size,
                        int(qty),
                        ts

                    ])

        if rows:
            sheet2.append_rows(rows, value_input_option="USER_ENTERED")

    except Exception as e:
        print("❌ SHEET2 ERROR:", e)
        raise


# =========================
# OPTIONAL: FUTURE SAFE EXTENSION
# =========================

def mark_order_cancelled(order_id):
    """
    OPTIONAL (future upgrade):
    You can later use this to update status column
    """

    try:
        # placeholder for future update logic
        return True

    except Exception as e:
        print("❌ CANCEL UPDATE ERROR:", e)
        raise