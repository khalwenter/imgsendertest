import time
import json
import os
import gspread
from datetime import datetime
from google.auth.transport.requests import AuthorizedSession

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

gc = gspread.service_account(filename=CREDS_PATH)



sheet_url = load_sheet_url()
sh = gc.open_by_url(sheet_url)

sheet1 = sh.worksheet("tCustomers")
sheet2 = sh.worksheet("tOrders")
sheet3 = sh.worksheet("tTg-Analytics")
sheet4 = sh.worksheet("tInventory")
sheet5 = sh.worksheet("tStock_Log")

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




INVENTORY_CACHE = None
INVENTORY_CACHE_TIME = 0

def get_inventory_grouped():

    global INVENTORY_CACHE, INVENTORY_CACHE_TIME

    now = time.time()

    # refresh every 30 seconds
    if INVENTORY_CACHE and now - INVENTORY_CACHE_TIME < 30:
        return INVENTORY_CACHE

    records = sheet4.get("A2:C")  # only needed columns

    grouped = {}

    for r in records:
        if len(r) < 3:
            continue

        name = str(r[0]).strip().upper()
        size = str(r[1]).strip().upper()
        stock = int(r[2] or 0)

        if not name:
            continue

        grouped.setdefault(name, {"sizes": {}})
        grouped[name]["sizes"][size] = grouped[name]["sizes"].get(size, 0) + stock

    INVENTORY_CACHE = grouped
    INVENTORY_CACHE_TIME = now

    return grouped



def restore_stock_from_order(order):

    for line in order["shirts"]:

        tokens = line.split()
        name = tokens[0].upper()

        pairs = list(zip(tokens[1::2], tokens[2::2]))

        for size, qty in pairs:
            if qty.isdigit():
                update_stock(
    name,
    size.upper(),
    int(qty),
    order_id=order.get("order_id", "")
)


# =========================
# INVENTORY
# =========================

def get_inventory(img_folder="img"):
    items = []

    for file in os.listdir(img_folder):
        if not file.endswith(".png"):
            continue

        name = file.replace(".png", "")
        path = os.path.join(img_folder, file)

        items.append({
            "name": name,
            "path": path,
            "size_mb": os.path.getsize(path) / (1024 * 1024)
        })

    return items

def get_item_sizes(name):

    def task():

        records = sheet4.get_all_records()

        sizes = []

        for row in records:

            if str(row["name"]).upper() == name.upper():

                sizes.append({
                    "size": row["size"],
                    "stock": int(row["stock"]),
                    "price": row["price"]
                })

        return sizes

    return safe_retry(task)




def inventory_text():

    grouped = get_inventory_grouped()

    text = "📦 Inventory\n\n"

    low_stock = []
    normal_stock = []

    for name, data in grouped.items():

        lines = []

        has_negative = False

        for size, stock in sorted(data["sizes"].items()):

            if stock < 0:

                has_negative = True

                lines.append(
                    f"🔴 {size} = {stock}"
                )

            elif stock == 0:

                lines.append(
                    f"🟠 {size} = {stock}"
                )

            else:

                lines.append(
                    f"🟢 {size} = {stock}"
                )

        block = (
            f"{name}\n"
            + "\n".join(lines)
            + "\n"
        )

        if has_negative:
            low_stock.append(block)
        else:
            normal_stock.append(block)

    if low_stock:

        text += "⚠️ NEED RESTOCK\n\n"

        text += "\n".join(low_stock)

        text += "\n"

    if normal_stock:

        text += "━━━━━━━━━━━━━━\n\n"

        text += "\n".join(normal_stock)

    return text


def get_order_shirts(order_id):

    def task():

        rows = sheet2.get("A2:G")  # IMPORTANT FIX

        shirts = []

        for r in rows[1:]:  # skip header

            if len(r) < 6:
                continue

            if str(r[1]).strip() == str(order_id).strip():  # order_id column

                shirt = r[3]
                size = r[4]
                qty = r[5]

                shirts.append(f"{shirt} {size} {qty}")

        if not shirts:
            raise Exception("Order not found")

        return {"shirts": shirts}

    return safe_retry(task)


def find_inventory_row(name, size):

    values = sheet4.get("A2:C")  # ONLY needed columns

    for i, row in enumerate(values, start=2):

        if len(row) < 3:
            continue

        sheet_name = str(row[0]).strip().lower()
        sheet_size = str(row[1]).strip().upper()

        if sheet_name == name.lower() and sheet_size == size.upper():
            return i, row

    return None, None

def update_stock(name, size, qty_change, order_id=""):

    row_index, row = find_inventory_row(name, size)

    if not row:
        raise Exception(f"Stock row not found : {name} {size}")

    current_stock = int(row[2] or 0)
    new_stock = current_stock + qty_change

    sheet4.update(
        f"C{row_index}:F{row_index}",
        [[
            new_stock,
            None,
            None,
            datetime.now().isoformat()
        ]]
    )

    stock_status = "INIT_ADD" if order_id == "INIT" else (
        "instock" if qty_change > 0 else "outstock"
    )

    append_stock_log(
        name=name,
        size=size,
        stock=qty_change,   # ✅ ONLY DELTA
        stock_status=stock_status,
        order_id=order_id
    )

    return new_stock
 
# =========================
# STOCK LOG
# =========================

def append_stock_log(name, size, stock, stock_status, order_id=""):

    def task():
        now = datetime.now().isoformat()

        print("🔥 WRITING TO SHEET5")

        sheet5.append_row(
            [
                name.lower(),
                size.upper(),
                stock,
                stock_status,
                now,
                now
            ],
            value_input_option="USER_ENTERED"
        )

        print("✅ SHEET5 WRITE SUCCESS")

    try:
        safe_retry(task)
    except Exception as e:
        print("❌ SHEET5 FAILED:", e)