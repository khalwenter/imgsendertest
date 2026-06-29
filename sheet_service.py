import time
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
# GOOGLE SHEETS CONNECT (FIXED)
# =========================

gc = gspread.service_account(filename=CREDS_PATH)  # ❌ removed timeout
sheet_url = load_sheet_url()
sh = gc.open_by_url(sheet_url)

sheet1 = sh.worksheet("Customers")
sheet2 = sh.worksheet("Orders")
sheet3 = sh.worksheet("Tg-Analytics")


# =========================
# SAFE RETRY WRAPPER
# =========================

def safe_retry(fn, retries=3, delay=2):
    last_err = None

    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            time.sleep(delay)

    raise last_err


# =========================
# ORDER ID (FAST + SAFE)
# =========================

def generate_order_id():

    def task():
        values = sheet1.get("B2:B")

        nums = []

        for row in values:
            if not row:
                continue

            v = str(row[0]).strip()

            if v.startswith("ORD"):
                try:
                    nums.append(int(v.replace("ORD", "")))
                except:
                    pass

        next_number = max(nums, default=0) + 1
        return f"ORD{next_number:06d}"

    return safe_retry(task)


def order_exists(order_id):

    def task():
        values = sheet1.get("B2:B")
        order_id = str(order_id).strip()

        return any(
            row and str(row[0]).strip() == order_id
            for row in values
        )

    return safe_retry(task)


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
# ANALYTICS SHEET
# =========================

def get_analytics(date1=None, date2=None):

    ws = sheet3

    if date1 == "today":
        date1 = datetime.now().strftime("%d/%m/%y")

    date1 = date1 or ""
    date2 = date2 or ""

    def task():

        ws.update(
            "B1:C1",
            [[date1, date2]],
            value_input_option="USER_ENTERED"
        )

        time.sleep(1)

        values = ws.batch_get(["B2", "B3", "B4"])

        total_package = values[0][0][0] if values[0] and values[0][0] else "0"
        total_revenue = values[1][0][0] if values[1] and values[1][0] else "0"
        total_shirt = values[2][0][0] if values[2] and values[2][0] else "0"

        return {
            "start_date": date1,
            "end_date": date2,
            "total_package": total_package,
            "total_revenue": total_revenue,
            "total_shirt": total_shirt,
        }

    return safe_retry(task)


# =========================
# OPTIONAL
# =========================

def mark_order_cancelled(order_id):
    try:
        return True
    except Exception as e:
        print("❌ CANCEL UPDATE ERROR:", e)
        raise