import requests
import re
import os
import time

from datetime import datetime
from collections import defaultdict

from sheet_service import (
    save_package,
    save_shirt_details,
    generate_order_id,
    order_exists
)

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


# ============================================
# UTIL
# ============================================

def count_digits(s):
    return sum(c.isdigit() for c in str(s))


def extract_price(line):
    m = re.search(r'(\$[\d.]+|[\d.]+\$)', line)
    return m.group(0) if m else ""


# ============================================
# TELEGRAM
# ============================================

def get_updates():
    global last_update_id

    params = {"timeout": 30}
    if last_update_id:
        params["offset"] = last_update_id

    try:
        r = requests.get(f"{API_URL}/getUpdates", params=params, timeout=REQUEST_TIMEOUT)
        return r.json()
    except Exception as e:
        print("❌ GET UPDATES ERROR:", e)
        return {"ok": False}


def send_text(chat_id, text, thread_id=None):
    try:
        data = {"chat_id": chat_id, "text": text}

        if thread_id:
            data["message_thread_id"] = thread_id

        r = requests.post(
            f"{API_URL}/sendMessage",
            data=data,
            timeout=REQUEST_TIMEOUT
        )
        return r.ok
    except Exception as e:
        print("❌ SEND ERROR:", e)
        return False


def send_log_to_source(text):
    send_text(SOURCE_CHAT_ID, text, SOURCE_THREAD_ID)


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


def send_images(shirt_lines, chat_id):

    grouped = {}
    sent = 0

    print("📤 START SENDING IMAGES...")

    # =========================
    # GROUP SHIRTS
    # =========================
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

    # =========================
    # SEND IMAGES WITH LOG
    # =========================
    for shirt_id, sizes in grouped.items():

        print(f"➡️ Processing shirt: {shirt_id}")

        img_path = os.path.join("img", f"{shirt_id}.png")

        print(f"📂 Checking file: {img_path}")

        if not os.path.exists(img_path):
            print(f"⚠️ Missing image: {shirt_id}")
            continue

        caption = " ".join([f"{k} {v}" for k, v in sizes.items()])

        try:
            print(f"📸 Sending image: {shirt_id}")

            with open(img_path, "rb") as img:
                r = requests.post(
                    f"{API_URL}/sendPhoto",
                    data={"chat_id": chat_id, "caption": caption},
                    files={"photo": img},
                    timeout=REQUEST_TIMEOUT
                )

            if r.ok:
                print(f"✅ Sent: {shirt_id}")
                sent += 1
            else:
                print(f"❌ Telegram failed: {r.text}")

        except Exception as e:
            print(f"❌ IMAGE ERROR ({shirt_id}):", e)

    print(f"🏁 IMAGE SENDING DONE | TOTAL SENT: {sent}")

    return sent

# ============================================
# SHEET SAVE
# ============================================

def save_sheets(parsed):

    for i in range(SHEET_RETRY):
        try:
            save_package(parsed)
            save_shirt_details(parsed)
            return True
        except Exception as e:
            print(f"❌ SHEET ERROR {i+1}:", e)
            time.sleep(SHEET_RETRY_DELAY)

    return False


# ============================================
# FORMAT MESSAGE (KHMER OUTPUT)
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
# MAIN PROCESS
# ============================================

def process():

    global last_update_id

    data = get_updates()
    if not data.get("ok"):
        return

    for u in data["result"]:

        try:
            last_update_id = u["update_id"] + 1

            msg = u.get("message") or u.get("channel_post") or u.get("edited_message")
            if not msg:
                continue

            chat_id = msg.get("chat", {}).get("id")
            thread_id = msg.get("message_thread_id")
            text = msg.get("text") or msg.get("caption") or ""

            if chat_id != SOURCE_CHAT_ID or thread_id != SOURCE_THREAD_ID:
                continue

            cmd = text.lower()

            if not (cmd.startswith("new") or cmd.startswith("cancel")):
                continue

            parsed = parse_message(text)
            if not parsed:
                continue

            # =========================
            # ORDER LOGIC
            # =========================

            if parsed["order_type"] == "new":

                parsed["order_id"] = generate_order_id()
                parsed["cancel_on"] = ""

                send_log_to_source(
                    f"✅ NEW ORDER\nID: {parsed['order_id']}\nName: {parsed['name']}"
                )

            elif parsed["order_type"] == "cancel":

                if not order_exists(parsed["cancel_on"]):

                    send_log_to_source(
                        f"❌ Order {parsed['cancel_on']} not found"
                    )
                    print(f"❌ Order {parsed['cancel_on']} not found")
                    continue

                parsed["order_id"] = generate_order_id()

                send_log_to_source(
                    f"⚠️ CANCEL ORDER\nCancel On: {parsed['cancel_on']}\nNew ID: {parsed['order_id']}\nName: {parsed['name']}"
                )

            else:
                parsed["order_id"] = "TEMP"
                parsed["cancel_on"] = ""

            # =========================
            # OUTPUT
            # =========================

            total_qty = count_total_qty(parsed["shirts"])
            msg_text = format_message(parsed, total_qty)

            tg_ok = send_text(TARGET_CHAT_ID, msg_text)
            img_count = send_images(parsed["shirts"], TARGET_CHAT_ID)
            sheet_ok = save_sheets(parsed)

            # =========================
            # FINAL LOG (CONSOLE)
            # =========================

            print("\n━━━━━━━━━━━━━━━━━━━━")
            print("📦 ORDER DONE")
            print(f"ID     : {parsed['order_id']}")
            print(f"Name   : {parsed['name']}")
            print(f"TG     : {'✅' if tg_ok else '❌'}")
            print(f"Images : {img_count}")
            print(f"Sheet  : {'✅' if sheet_ok else '❌'}")
            print("━━━━━━━━━━━━━━━━━━━━\n")

        except Exception as e:
            print("❌ PROCESS ERROR:", e)


# ============================================
# LOOP
# ============================================

def main():

    print("🤖 Bot running...")

    while True:
        try:
            process()
            time.sleep(2)
        except Exception as e:
            print("❌ LOOP ERROR:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()