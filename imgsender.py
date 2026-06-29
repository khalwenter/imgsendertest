import requests
import re
import os
import time
import sys

from datetime import datetime
from collections import defaultdict

from sheet_service import (
    save_package,
    save_shirt_details,
    generate_order_id,
    order_exists
)

from inventory import InventoryManager
from inventory_state import get_mode


# ============================================
# CONFIG
# ============================================

BOT_TOKEN = "8497104307:AAHQiYmehz2ksg-GqdFpvIvAgx6V_PT4weQ"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

SOURCE_CHAT_ID = -1002870542147
SOURCE_THREAD_ID = 473

TARGET_CHAT_ID = -4942287748


REQUEST_TIMEOUT = 60
SHEET_RETRY = 3
SHEET_RETRY_DELAY = 5

last_update_id = 0

inventory = InventoryManager(BOT_TOKEN, img_folder="img")


# ============================================
# LOGGER
# ============================================

def log(text):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {text}")


# ============================================
# TELEGRAM
# ============================================

def send_text(chat_id, text, thread_id=None):
    try:
        data = {
            "chat_id": chat_id,
            "text": text
        }

        if thread_id is not None:
            data["message_thread_id"] = thread_id

        r = requests.post(
            f"{API_URL}/sendMessage",
            data=data,
            timeout=REQUEST_TIMEOUT
        )

        return r.ok

    except Exception as e:
        log(f"❌ SEND TEXT ERROR: {e}")
        return False


def get_updates():
    global last_update_id

    params = {"timeout": 25}

    if last_update_id:
        params["offset"] = last_update_id

    try:
        r = requests.get(
            f"{API_URL}/getUpdates",
            params=params,
            timeout=30
        )

        if r.status_code != 200:
            return {"ok": False, "result": []}

        return r.json()

    except Exception as e:
        log(f"❌ GET UPDATES ERROR: {e}")
        return {"ok": False, "result": []}


# ============================================
# UTIL
# ============================================

def count_digits(s):
    return sum(c.isdigit() for c in str(s))


def extract_price(line):
    m = re.search(r'(\$[\d.]+|[\d.]+\$)', line)
    return m.group(0) if m else ""


# ============================================
# COMMAND PARSER
# ============================================

def parse_command(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return "normal", ""

    first = lines[0].lower()

    if first == "new":
        return "new", ""

    m = re.match(r"cancel\s*:\s*(ORD\d+)", first, re.IGNORECASE)
    if m:
        return "cancel", m.group(1).upper()

    return "normal", ""


# ============================================
# MESSAGE PARSER
# ============================================

def parse_message(text):

    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return None

    order_type, cancel_on = parse_command(text)

    if order_type in ["new", "cancel"]:
        if len(lines) < 2:
            return None
        first = lines[1]
        data_lines = lines[2:]
    else:
        first = lines[0]
        data_lines = lines[1:]

    price = extract_price(first)

    name = re.sub(r'\(.*?\)', '', first)
    name = re.sub(r'(\$[\d.]+|[\d.]+\$)', '', name)
    name = re.sub(r'\s+', ' ', name).strip()

    phone = ""
    address = ""
    shirts = []

    for line in data_lines:
        if count_digits(line) >= 9:
            phone = line
            break

    for line in data_lines:
        if line != phone and count_digits(line) < 9:
            address = line
            break

    for line in data_lines:
        if line != phone and line != address:
            shirts.append(line)

    return {
        "name": name,
        "price": price,
        "shirts": shirts,
        "phone": phone,
        "address": address,
        "order_type": order_type,
        "cancel_on": cancel_on
    }


# ============================================
# IMAGE SENDING
# ============================================

def send_images(shirt_lines, chat_id):

    grouped = {}
    missing = []
    sent = 0

    log("📤 IMAGE PROCESS START")

    for line in shirt_lines:

        tokens = line.split()
        if len(tokens) < 3:
            continue

        shirt_id = tokens[0].lower().replace(" ", "_")
        pairs = list(zip(tokens[1::2], tokens[2::2]))

        if shirt_id not in grouped:
            grouped[shirt_id] = defaultdict(int)

        for size, qty in pairs:
            if qty.isdigit():
                grouped[shirt_id][size] += int(qty)

    for shirt_id, sizes in grouped.items():

        img_path = os.path.join("img", f"{shirt_id}.png")

        if not os.path.exists(img_path):

            fallback_text = " ".join(
                [shirt_id] + [f"{k} {v}" for k, v in sizes.items()]
            )

            missing.append(fallback_text)
            log(f"⚠️ MISSING: {shirt_id}")
            send_text(chat_id, f"(អត់រូប)\n{fallback_text}")
            continue

        caption = " ".join([f"{k} {v}" for k, v in sizes.items()])

        try:
            with open(img_path, "rb") as img:
                r = requests.post(
                    f"{API_URL}/sendPhoto",
                    data={"chat_id": chat_id, "caption": caption},
                    files={"photo": img},
                    timeout=REQUEST_TIMEOUT
                )

            if r.ok:
                sent += 1
                log(f"✅ SENT: {shirt_id}")

        except Exception as e:
            log(f"❌ IMAGE ERROR: {e}")

    log(f"🏁 DONE | SENT={sent} | MISSING={len(missing)}")
    return sent


# ============================================
# SHEETS
# ============================================

def save_sheets(parsed):

    log("💾 SHEETS SAVE")

    for i in range(SHEET_RETRY):
        try:
            save_package(parsed)
            save_shirt_details(parsed)
            log("✅ SHEETS DONE")
            return True

        except Exception as e:
            log(f"❌ SHEET ERROR {i+1}: {e}")
            time.sleep(SHEET_RETRY_DELAY)

    sys.exit(1)


# ============================================
# FORMAT MESSAGE
# ============================================

def format_message(parsed, total_qty):

    return (
        f"📦 កម្មង់ថ្មី:\n"
        f"ឈ្មោះ: {parsed['name']}\n"
        f"កញ្ចប់ ID: {parsed['order_id']}\n"
        f"កញ្ចប់ខុស: {parsed.get('cancel_on','')}\n"
        f"ចំនួនអាវ: {total_qty}\n"
        f"តម្លៃ: {parsed['price']}\n"
        f"អាស័យដ្ឋាន: {parsed['address']}\n"
        f"លេខទូរស័ព្ទ: {parsed['phone']}\n"
    )


def count_total_qty(shirts):

    total = 0

    for line in shirts:
        tokens = line.split()
        if len(tokens) < 3:
            continue

        pairs = list(zip(tokens[1::2], tokens[2::2]))

        for size, qty in pairs:
            if qty.isdigit():
                total += int(qty)

    return total


# ============================================
# MAIN PROCESS (FIXED PROPERLY)
# ============================================

def process():

    global last_update_id

    data = get_updates()

    if not data.get("ok"):
        log("❌ GET UPDATES FAILED")
        return

    updates = data.get("result", [])

    if not updates:
        return  # 🔥 no spam

    log(f"🚀 NEW UPDATE: {len(updates)}")

    for u in updates:

        try:
            update_id = u["update_id"]

            if update_id < last_update_id:
                continue

            last_update_id = update_id + 1

            msg = u.get("message") or u.get("channel_post") or u.get("edited_message")
            if not msg:
                continue

            chat_id = msg.get("chat", {}).get("id")
            thread_id = msg.get("message_thread_id")
            text = msg.get("text") or msg.get("caption") or ""
            photos = msg.get("photo")

            user_id = msg.get("from", {}).get("id", chat_id)
            mode = get_mode(user_id)

            if mode:
                if inventory.receive_analytics_date(user_id, chat_id, text, thread_id): continue
                if inventory.receive_photo(user_id, chat_id, photos, thread_id): continue
                if inventory.receive_image_name(user_id, chat_id, text, thread_id): continue
                if inventory.receive_delete_name(user_id, chat_id, text, thread_id): continue
                if inventory.receive_delete_confirm(user_id, chat_id, text, thread_id): continue
                if inventory.receive_replace_confirm(user_id, chat_id, text, thread_id): continue

            cmd = text.lower().split("@")[0].strip()
            
            if cmd.startswith("/guide"):

                log("📖 GUIDE REQUEST")

                guide_text = (
                    "📖 មគ្គុទេសក៍ប្រើប្រាស់ Bot\n\n"

                    "📦 គ្រប់គ្រងរូបភាព\n"
                    "🖼 /មើលរូប\n"
                    "    • ឆែកមើលរូបទាំងអស់ក្នុងទិន្នន័យ\n\n"

                    "➕ /ថែមរូប\n"
                    "    • បន្ថែមរូបអាវថ្មីទៅក្នុងទិន្នន័យ\n\n"

                    "🗑 /លុបរូប\n"
                    "    • លុបរូបចេញពីទិន្នន័យ\n\n"

                    "🔍 /ស្វែងរក <ឈ្មោះ>\n"
                    "    • ស្វែងរករូបអាវតាមឈ្មោះ\n"
                    "    • ឧទាហរណ៍៖\n"
                    "      /ស្វែងរក a001\n\n"

                    "📊 /analytics\n"
                    "    • មើលស្ថិតិការលក់\n\n"
                    "    ឧទាហរណ៍៖\n"
                    "    /analytics today\n"
                    "    /analytics 29/06/26\n"
                    "    /analytics 28/06/26 29/06/26\n\n"

                    "❌ /cancel\n"
                    "    • បញ្ឈប់ប្រតិបត្តិការដែលកំពុងដំណើរការ\n\n"

                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "💡 ចំណាំ\n"
                    "• Commands អាចប្រើក្នុង Group ឬ Topic បាន\n"
                    "• សម្រាប់ការបន្ថែមរូប Bot នឹងណែនាំជាជំហានៗ\n"
                    "• ថ្ងៃខែឆ្នាំត្រូវប្រើទម្រង់ dd/mm/yy\n"
                )

                send_text(chat_id, guide_text, thread_id)
                continue
                        
            if cmd.startswith("/មើលរូប"):
                inventory.view_all_grid(chat_id, thread_id)
                continue

            if cmd.startswith("/ថែមរូប"):
                inventory.start_add_image(user_id, chat_id, thread_id)
                continue

            if cmd.startswith("/លុបរូប"):
                inventory.start_delete_image(user_id, chat_id, thread_id)
                continue

            if cmd.startswith("/ស្វែងរក"):
                keyword = cmd.replace("/ស្វែងរក", "").strip()
                inventory.search_inventory(chat_id, keyword, thread_id)
                continue

            if cmd.startswith("/cancel"):
                inventory.cancel(user_id, chat_id, thread_id)
                continue

            if cmd.startswith("/analytics"):

                parts = text.strip().split()

                try:

                    if len(parts) == 1:
                        send_text(
                            chat_id,
                            "Usage:\n"
                            "/analytics today\n"
                            "/analytics DD/MM/YY\n"
                            "/analytics DD/MM/YY DD/MM/YY",
                            thread_id,
                        )
                        continue

                    from sheet_service import get_analytics

                    if parts[1].lower() == "today":

                        result = get_analytics("today")

                    elif len(parts) == 2:

                        result = get_analytics(parts[1])

                    elif len(parts) == 3:

                        result = get_analytics(parts[1], parts[2])

                    else:

                        send_text(chat_id, "Invalid command.", thread_id)
                        continue

                    if result["end_date"]:

                        title = f"{result['start_date']} → {result['end_date']}"

                    else:

                        title = result["start_date"]

                    msg = (
                        f"📊 Analytics\n\n"
                        f"📅 {title}\n\n"
                        f"📦 Total Package : {result['total_package']} កញ្ចប់\n"
                        f"💰 Total Revenue : ${result['total_revenue']}\n"
                        f"👕 Total Shirt : {result['total_shirt']} ខោ/អាវ"
                    )

                    send_text(chat_id, msg, thread_id)

                except Exception as e:

                    log(f"❌ ANALYTICS ERROR: {e}")
                    send_text(chat_id, "❌ Failed to fetch analytics.", thread_id)

                continue

            if not (cmd.startswith("new") or cmd.startswith("cancel")):
                continue

            parsed = parse_message(text)
            if not parsed:
                continue

            try:
                parsed["order_id"] = generate_order_id()
            except Exception as e:
                log(f"ORDER ID FAIL: {e}")
                continue

            # ============================================
            # LOG BACK TO SOURCE THREAD
            # ============================================

            send_text(
                chat_id=chat_id,
                text=(
                    "✅ NEW ORDER\n"
                    f"ID: {parsed['order_id']}\n"
                    f"Name: {parsed['name']}"
                ),
                thread_id=thread_id
            )

            total_qty = count_total_qty(parsed["shirts"])
            msg_text = format_message(parsed, total_qty)

            send_text(TARGET_CHAT_ID, msg_text, thread_id)
            send_images(parsed["shirts"], TARGET_CHAT_ID)
            save_sheets(parsed)

        except Exception as e:
            log(f"❌ ERROR: {e}")


# ============================================
# LOOP
# ============================================

def main():

    log("🤖 BOT STARTED")

    while True:
        try:
            process()
        except Exception as e:
            log(f"❌ LOOP ERROR: {e}")

        time.sleep(2)


if __name__ == "__main__":
    main()