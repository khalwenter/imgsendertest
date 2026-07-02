from datetime import datetime
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
import math
from telegram_utils import TelegramAPI

from image_utils import (
    save_inventory_image,
    delete_inventory_image,
    image_exists,
    search_inventory,
)

from sheet_service import (
    get_inventory,
    get_item_sizes,
    update_stock,
    inventory_text,
    sheet4,
    sheet5,
    append_stock_log,
    find_inventory_row,
)

from inventory_state import (
    
    MODE_WAITING_ADD_ITEM_ID,
    MODE_WAITING_ADD_NAME,
    MODE_WAITING_ADD_SIZE_STOCK,
    set_state,
    get_state,
    get_mode,
    get_data,
    update_data,
    clear_state,
    has_state,

    MODE_WAITING_ADD_IMAGE,
    MODE_WAITING_PHOTO,
    MODE_WAITING_IMAGE_NAME,

    MODE_WAITING_DELETE_NAME,
    MODE_WAITING_DELETE_CONFIRM,

    MODE_WAITING_RENAME_OLD,
    MODE_WAITING_RENAME_NEW,

    MODE_WAITING_ADDSTOCK_ITEM,
    MODE_WAITING_ADDSTOCK_SIZE,
    MODE_WAITING_ADDSTOCK_QTY,

    MODE_WAITING_REMOVESTOCK_ITEM,
    MODE_WAITING_REMOVESTOCK_SIZE,
    MODE_WAITING_REMOVESTOCK_QTY,
    MODE_WAITING_ANALYTICS_DATE,
)
import re

def safe_filename(name: str):
    name = name.strip().lower()
    name = re.sub(r'\s+', '_', name)          # spaces → _
    name = re.sub(r'[^a-z0-9_]', '', name)    # remove unsafe chars
    return name

class InventoryManager:

    def __init__(self, bot_token, img_folder="img"):
        self.telegram = TelegramAPI(bot_token)
        self.img_folder = img_folder
        os.makedirs(self.img_folder, exist_ok=True)

    # ============================================
    # FAST VIEW ALL GRID (OPTIMIZED)
    # ============================================
    def view_all_grid(self, chat_id, thread_id=None, size_filter=None):

        rows = sheet4.get_all_values()

        if len(rows) <= 1:
            self.telegram.send_text(chat_id, "📦 Inventory is empty.", thread_id)
            return

        # =========================
        # GROUP DATA
        # =========================
        grouped = {}

        for row in rows[1:]:
            if len(row) < 3:
                continue

            name = row[0].strip()
            size = row[1].strip().upper()
            stock = int(row[2] or 0)

            # filter by size if requested
            if size_filter and size != size_filter.upper():
                continue
            key = name.upper()

            if key not in grouped:
                grouped[key] = {
                    "name": name,
                    "sizes": {},
                    "image": os.path.join(self.img_folder, f"{name.lower()}.png")
                }

            grouped[key]["sizes"][size] = grouped[key]["sizes"].get(size, 0) + stock

        # =========================
        # GRID SETTINGS
        # =========================
        MAX_PER_GRID = 40
        cols = 5
        thumb_w, thumb_h = 250, 200

        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
        except:
            font = ImageFont.load_default()

        items = list(grouped.values())
        if not items:
            self.telegram.send_text(
                chat_id,
                f"❌ No inventory found for size {size_filter.upper()}",
                thread_id
            )
            return
        def build_grid(chunk, page):

            rows = math.ceil(len(chunk) / cols)
            cell_w = thumb_w
            cell_h = thumb_h + 80

            grid = Image.new(
                "RGB",
                (cols * cell_w, rows * cell_h),
                (255, 255, 255)
            )

            draw = ImageDraw.Draw(grid)

            for i, item in enumerate(chunk):

                r = i // cols
                c = i % cols

                x = c * cell_w
                y = r * cell_h

                # =========================
                # IMAGE
                # =========================
                try:
                    if os.path.exists(item["image"]):
                        img = Image.open(item["image"]).convert("RGB")
                        img.thumbnail((thumb_w, thumb_h))
                        grid.paste(img, (x, y))
                except:
                    pass

                # =========================
                # TEXT
                # =========================
                name = item["name"].upper()

                size_text = " | ".join(
                    [f"{s}:{q}" for s, q in item["sizes"].items()]
                )

                draw.text(
                    (x + 5, y + thumb_h + 5),
                    name,
                    fill=(0, 0, 0),
                    font=font
                )

                draw.text(
                    (x + 5, y + thumb_h + 30),
                    size_text,
                    fill=(50, 50, 50),
                    font=font
                )

            temp_path = os.path.join(
                tempfile.gettempdir(),
                f"inventory_grid_{page}.jpg"
            )

            grid.save(temp_path, "JPEG", quality=85)

            self.telegram.send_photo(
                chat_id=chat_id,
                photo_path=temp_path,
                caption=f"📦 Inventory Page {page+1}",
                thread_id=thread_id
            )

        # =========================
        # PAGINATION
        # =========================
        chunks = [
            items[i:i + MAX_PER_GRID]
            for i in range(0, len(items), MAX_PER_GRID)
        ]

        for page, chunk in enumerate(chunks):
            build_grid(chunk, page)


    # ============================================
    # SHOW INVENTORY (KEEP ORIGINAL)
    # ============================================
    def show_inventory(self, chat_id, thread_id=None):

  

        if not items:
            self.telegram.send_text(chat_id, "📦 Inventory is empty.", thread_id)
            return

        total_size = 0

        for item in items:
            total_size += item["size_mb"]

            self.telegram.send_photo(
                chat_id=chat_id,
                photo_path=item["path"],
                caption=item["name"],
                thread_id=thread_id
            )

        self.telegram.send_text(
            chat_id,
            (
                "📦 Inventory Summary\n\n"
                f"Total Images : {len(items)}\n"
                f"Folder Size : {round(total_size,2)} MB"
            ),
            thread_id
        )

    # ============================================
    # ADD IMAGE FLOW
    # ============================================
    def start_add_image(self, user_id, chat_id, thread_id=None):

        set_state(user_id, MODE_WAITING_PHOTO)

        self.telegram.send_text(
            chat_id,
            "📷 Send the shirt image.",
            thread_id
        )

    def receive_photo(self, user_id, chat_id, photos, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_PHOTO:
            return False

        if not photos:
            self.telegram.send_text(chat_id, "❌ No photo detected.", thread_id)
            return True

        file_id = photos[-1]["file_id"]
        temp_path = os.path.join(tempfile.gettempdir(), f"{file_id}.jpg")

        if not self.telegram.download_file(file_id, temp_path):
            self.telegram.send_text(chat_id, "❌ Download failed.", thread_id)
            return True

        update_data(user_id, temp_file=temp_path)
        set_state(user_id, MODE_WAITING_IMAGE_NAME, get_data(user_id))

        self.telegram.send_text(chat_id, "✅ Send image name.", thread_id)

        return True

    def receive_image_name(self, user_id, chat_id, image_name, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_IMAGE_NAME:
            return False

        image_name = image_name.strip().lower()

        if not image_name:
            self.telegram.send_text(chat_id, "❌ Empty name.", thread_id)
            return True

        data = get_data(user_id)
        temp_file = data.get("temp_file")

        if not temp_file or not os.path.exists(temp_file):
            clear_state(user_id)
            self.telegram.send_text(chat_id, "❌ Temp missing.", thread_id)
            return True

        if image_exists(image_name, self.img_folder):

            update_data(user_id, image_name=image_name)
            set_state(user_id, "waiting_replace_confirm", get_data(user_id))

            self.telegram.send_text(
                chat_id,
                f"⚠️ '{image_name}' exists. YES/NO?",
                thread_id
            )
            return True

        save_inventory_image(temp_file, image_name, self.img_folder)

        if os.path.exists(temp_file):
            os.remove(temp_file)

        clear_state(user_id)

        self.telegram.send_text(chat_id, f"✅ Saved {image_name}", thread_id)

        return True

    # ============================================
    # DELETE FLOW
    # ============================================
    def start_delete_image(self, user_id, chat_id, thread_id=None):

        items = get_inventory()

        if not items:
            self.telegram.send_text(chat_id, "📦 Empty.", thread_id)
            return

        text = "🗑 Inventory\n\n"
        for i, item in enumerate(items, 1):
            text += f"{i}. {item['name']}\n"

        set_state(user_id, MODE_WAITING_DELETE_NAME)

        self.telegram.send_text(chat_id, text, thread_id)

    def receive_delete_name(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_DELETE_NAME:
            return False

        name = text.strip().lower()

        if not image_exists(name, self.img_folder):
            self.telegram.send_text(chat_id, "❌ Not found.", thread_id)
            return True

        update_data(user_id, image_name=name)
        set_state(user_id, MODE_WAITING_DELETE_CONFIRM, get_data(user_id))

        self.telegram.send_text(chat_id, f"Delete {name}? YES/NO", thread_id)

        return True

    def receive_delete_confirm(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_DELETE_CONFIRM:
            return False

        ans = text.strip().upper()

        if ans == "NO":
            clear_state(user_id)
            self.telegram.send_text(chat_id, "Cancelled", thread_id)
            return True

        if ans != "YES":
            self.telegram.send_text(chat_id, "YES or NO only", thread_id)
            return True

        data = get_data(user_id)
        delete_inventory_image(data["image_name"], self.img_folder)

        clear_state(user_id)

        self.telegram.send_text(chat_id, "Deleted", thread_id)

        return True

    # ============================================
    # REPLACE CONFIRM
    # ============================================
    def receive_replace_confirm(self, user_id, chat_id, text, thread_id=None):

        state = get_state(user_id)
        if not state or state["mode"] != "waiting_replace_confirm":
            return False

        ans = text.strip().upper()

        if ans == "NO":
            clear_state(user_id)
            self.telegram.send_text(chat_id, "Cancelled", thread_id)
            return True

        if ans != "YES":
            self.telegram.send_text(chat_id, "YES or NO", thread_id)
            return True

        data = get_data(user_id)

        save_inventory_image(data["temp_file"], data["image_name"], self.img_folder)

        clear_state(user_id)

        self.telegram.send_text(chat_id, "Replaced", thread_id)

        return True

    # ============================================
    # SEARCH
    # ============================================
    def search_inventory(self, chat_id, keyword, thread_id=None):

        keyword = keyword.strip()

        if not keyword:
            self.telegram.send_text(chat_id, "Usage: /ស្វែងរក name", thread_id)
            return

        items = search_inventory(keyword, self.img_folder)

        if not items:
            self.telegram.send_text(chat_id, "No image found.", thread_id)
            return

        for item in items:
            self.telegram.send_photo(chat_id, item["path"], item["name"], thread_id)


    # ============================================
    # INVENTORY
    # ============================================

    def show_stock_inventory(self, chat_id, thread_id=None):

        try:

            text = inventory_text()

            if len(text) <= 4000:

                self.telegram.send_text(
                    chat_id,
                    text,
                    thread_id
                )

                return

            # split long message
            while len(text):

                chunk = text[:4000]

                self.telegram.send_text(
                    chat_id,
                    chunk,
                    thread_id
                )

                text = text[4000:]

        except Exception as e:

            self.telegram.send_text(
                chat_id,
                f"❌ {e}",
                thread_id
            )

    # ============================================
# ADD STOCK - START
# ============================================

    def start_add_stock(self, user_id, chat_id, thread_id=None):

        rows = get_inventory()

        if not rows:
            self.telegram.send_text(
                chat_id,
                "📦 Inventory is empty.",
                thread_id
            )
            return

        items = {}

        for row in rows:
            items[row["name"].lower()] = row["name"]

        text = "📦 Select Item\n\n"

        for item_id, name in sorted(items.items()):
            text += f"{item_id} - {name}\n"

        set_state(
            user_id,
            MODE_WAITING_ADDSTOCK_ITEM
        )

        self.telegram.send_text(
            chat_id,
            text,
            thread_id
        )

    # ============================================
# ADD STOCK - RECEIVE ITEM
# ============================================

    def receive_addstock_item(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_ADDSTOCK_ITEM:
            return False
        if text.strip().lower() == "/cancel":
            self.cancel(user_id, chat_id, thread_id)
            return True
        item_name = text.strip().lower()

        sizes = get_item_sizes(item_name)

        if not sizes:

            self.telegram.send_text(
                chat_id,
                "❌ Item not found.",
                thread_id
            )
            return True

        update_data(
            user_id,
            item_name=item_name
        )

        set_state(
            user_id,
            MODE_WAITING_ADDSTOCK_SIZE,
            get_data(user_id)
        )

        msg = f"📦 {item_name.upper()}\n\nAvailable Sizes:\n\n"

        for s in sizes:
            msg += f"{s['size']} (Stock: {s['stock']})\n"

        msg += "\nReply with the size."

        self.telegram.send_text(
            chat_id,
            msg,
            thread_id
        )

        return True

# ============================================
# ADD STOCK - RECEIVE SIZE
# ============================================

    def receive_addstock_size(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_ADDSTOCK_SIZE:
            return False

        size = text.strip().upper()

        data = get_data(user_id)
        item_name = data.get("item_name")

        if not item_name:
            clear_state(user_id)
            self.telegram.send_text(chat_id, "❌ Session expired.", thread_id)
            return True

        sizes = get_item_sizes(item_name)
        valid_sizes = [s["size"].upper() for s in sizes]

        size = size.strip().upper()

        # allow new size, but mark it
        is_new_size = size not in valid_sizes

        update_data(user_id, size=size)
        update_data(user_id, is_new_size=is_new_size)
        
        set_state(
            user_id,
            MODE_WAITING_ADDSTOCK_QTY,
            get_data(user_id)
        )

        self.telegram.send_text(
            chat_id,
            f"📦 {item_name} - {size}\n\nEnter quantity to ADD:",
            thread_id
        )

        return True

# ============================================
# ADD STOCK - RECEIVE QTY (FINAL STEP)
# ============================================

    def receive_addstock_qty(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_ADDSTOCK_QTY:
            return False

        data = get_data(user_id)

        item_name = data.get("item_name")
        size = data.get("size")

        if not item_name or not size:
            self.telegram.send_text(chat_id, "❌ Session expired.", thread_id)
            clear_state(user_id)
            return True

        if not text.isdigit():
            self.telegram.send_text(chat_id, "❌ Invalid quantity.", thread_id)
            return True

        qty = int(text)

        # =========================================
        # SAFE STOCK UPDATE (NO CRASH IF NEW SIZE)
        # =========================================
        try:
            new_stock = update_stock(
                item_name,
                size,
                qty,
                order_id="MANUAL_ADD"
            )

        except Exception as e:

            # =========================
            # SIZE DOES NOT EXIST → CREATE IT
            # =========================
            sheet4.append_row([
                item_name.lower(),
                size.upper(),
                qty,
                "instock",
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ])

            new_stock = qty

            append_stock_log(
                name=item_name.lower(),
                size=size.upper(),
                stock=qty,
                stock_status="instock",
                order_id="MANUAL_ADD_NEW"
            )


        clear_state(user_id)

        self.telegram.send_text(
            chat_id,
            (
                f"✅ Stock Added\n\n"
                f"📦 {item_name.upper()}\n"
                f"📏 {size}\n"
                f"➕ {qty}\n"
                f"📊 Current Stock : {new_stock}"
            ),
            thread_id
        )

        return True


# ============================================
# REMOVE STOCK - START
# ============================================

    def start_remove_stock(self, user_id, chat_id, thread_id=None):

        rows = get_inventory()

        if not rows:
            self.telegram.send_text(
                chat_id,
                "📦 Inventory is empty.",
                thread_id
            )
            return

        items = {}

        for row in rows:
            items[row["name"]] = row["name"]

        text = "🗑 Select Item ID to REMOVE STOCK\n\n"

        for item_id, name in sorted(items.items()):
            text += f"{item_id} - {name}\n"

        set_state(
            user_id,
            MODE_WAITING_REMOVESTOCK_ITEM
        )

        self.telegram.send_text(
            chat_id,
            text,
            thread_id
        )

    def receive_removestock_item(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_REMOVESTOCK_ITEM:
            return False

        item_name = text.strip().lower()

        sizes = get_item_sizes(item_name)

        if not sizes:

            self.telegram.send_text(
                chat_id,
                "❌ Item not found.",
                thread_id
            )
            return True

        update_data(
            user_id,
            item_name=item_name
        )

        set_state(
            user_id,
            MODE_WAITING_REMOVESTOCK_SIZE,
            get_data(user_id)
        )

        msg = f"🗑 {item_name.upper()}\n\nAvailable Sizes:\n\n"

        for s in sizes:
            msg += f"{s['size']} (Stock: {s['stock']})\n"

        msg += "\nReply with size."

        self.telegram.send_text(chat_id, msg, thread_id)

        return True


    def receive_removestock_size(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_REMOVESTOCK_SIZE:
            return False

        size = text.strip().upper()

        data = get_data(user_id)
        item_name = data.get("item_name")

        if not item_name:
            clear_state(user_id)
            self.telegram.send_text(chat_id, "❌ Session expired.", thread_id)
            return True

        sizes = get_item_sizes(item_name)
        valid_sizes = [s["size"].upper() for s in sizes]

        if size not in valid_sizes:

            self.telegram.send_text(
                chat_id,
                f"❌ Invalid size.\nAvailable: {', '.join(valid_sizes)}",
                thread_id
            )
            return True

        update_data(user_id, size=size)

        set_state(
            user_id,
            MODE_WAITING_REMOVESTOCK_QTY,
            get_data(user_id)
        )

        self.telegram.send_text(
            chat_id,
            f"🗑 {item_name} - {size}\n\nEnter quantity to REMOVE:",
            thread_id
        )

        return True


    def receive_removestock_qty(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_REMOVESTOCK_QTY:
            return False

        qty_text = text.strip()

        if not qty_text.isdigit():

            self.telegram.send_text(
                chat_id,
                "❌ Please enter a valid number.",
                thread_id
            )
            return True

        qty = int(qty_text)

        if qty <= 0:

            self.telegram.send_text(
                chat_id,
                "❌ Quantity must be > 0.",
                thread_id
            )
            return True

        data = get_data(user_id)

        item_name = data.get("item_name")
        size = data.get("size")

        if not item_name or not size:

            clear_state(user_id)

            self.telegram.send_text(
                chat_id,
                "❌ Session expired.",
                thread_id
            )

            return True

        try:
            update_stock(item_name, size, -qty)

        except Exception as e:

            self.telegram.send_text(
                chat_id,
                f"❌ Failed:\n{e}",
                thread_id
            )

            return True

        clear_state(user_id)

        self.telegram.send_text(
            chat_id,
            f"✅ Stock Removed\n\n{item_name} - {size} - {qty}",
            thread_id
        )

        return True

    # ============================================
    # CANCEL
    # ============================================
    def cancel(self, user_id, chat_id, thread_id=None):

        state = get_state(user_id)

        # delete temp files if any
        if state:
            data = state.get("data", {})
            temp = data.get("temp_file")

            if temp and os.path.exists(temp):
                try:
                    os.remove(temp)
                except:
                    pass

        clear_state(user_id)

        self.telegram.send_text(
            chat_id,
            "❌ Cancelled. All current operation stopped.",
            thread_id
        )
   # ============================================
    # Analytics Flow
    # ============================================
    def start_analytics(self, user_id, chat_id, metric, thread_id=None):

        set_state(
            user_id,
            MODE_WAITING_ANALYTICS_DATE,
            {
                "metric": metric
            }
        )

        self.telegram.send_text(
            chat_id,
            "📅 សូមបញ្ចូលថ្ងៃ (format: 29/06/26)",
            thread_id
        )

    # ============================================
    # Analytics Flow
    # ============================================
    def receive_analytics_date(self, user_id, chat_id, text, thread_id=None):
    

        if get_mode(user_id) != MODE_WAITING_ANALYTICS_DATE:
            return False

        date_value = text.strip()

        data = get_data(user_id)
        metric = data.get("metric")

        clear_state(user_id)

        try:
            from sheet_service import get_analytics_data  # you will add this

            result = get_analytics_data(date_value, metric)

            self.telegram.send_text(
                chat_id,
                f"📊 Result for {date_value}\n\n{metric}: {result}",
                thread_id
            )

        except Exception as e:
            self.telegram.send_text(
                chat_id,
                f"❌ Error fetching data: {e}",
                thread_id
            )

        return True
    

    def start_add_image(self, user_id, chat_id, thread_id=None):

        set_state(user_id, MODE_WAITING_ADD_IMAGE)

        self.telegram.send_text(
            chat_id,
            "📷 Send product image first",
            thread_id
        )

    def receive_add_image(self, user_id, chat_id, photos, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_ADD_IMAGE:
            return False

        if not photos:
            self.telegram.send_text(chat_id, "❌ No photo", thread_id)
            return True

        file_id = photos[-1]["file_id"]
        temp_path = os.path.join(tempfile.gettempdir(), f"{file_id}.jpg")

        if not self.telegram.download_file(file_id, temp_path):
            self.telegram.send_text(chat_id, "❌ Download failed", thread_id)
            return True

        update_data(user_id, temp_file=temp_path)

        update_data(user_id, temp_file=temp_path)

        set_state(user_id, MODE_WAITING_ADD_NAME, get_data(user_id))

        self.telegram.send_text(
            chat_id,
            "📝 Enter product name",
            thread_id
        )

        return True
    


    def receive_add_name(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_ADD_NAME:
            return False

        name = text.strip()

        update_data(user_id, name=name)

        set_state(user_id, MODE_WAITING_ADD_SIZE_STOCK, get_data(user_id))

        self.telegram.send_text(
            chat_id,
            "📦 Enter sizes + stock like:\nS 10\nM 5\nL 2",
            thread_id
        )

        return True


    def receive_add_size_stock(self, user_id, chat_id, text, thread_id=None):

        if get_mode(user_id) != MODE_WAITING_ADD_SIZE_STOCK:
            return False

        data = get_data(user_id)

        name = data.get("name")
        temp_file = data.get("temp_file")

        if not name:
            clear_state(user_id)
            self.telegram.send_text(chat_id, "❌ Session expired.", thread_id)
            return True

        name = name.strip().lower()

        # =========================
        # PARSE INPUT FLEXIBLY
        # =========================
        tokens = text.replace("\n", " ").split()

        rows = []
        i = 0

        while i < len(tokens) - 1:
            size = tokens[i].upper()
            qty = tokens[i + 1]

            # only accept valid number pairs
            if qty.isdigit():
                rows.append([
                    name,
                    size,
                    int(qty),
                    "",
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ])
                i += 2
            else:
                i += 1  # skip broken token

        # =========================
        # VALIDATION
        # =========================
        if not rows:
            self.telegram.send_text(
                chat_id,
                "❌ Invalid format.\nUse:\nS 10 M 5 L 2",
                thread_id
            )
            return True

        # =========================
        # SAVE IMAGE ONLY WHEN VALID
        # =========================
        filename = safe_filename(name)
        img_path = os.path.join("img", f"{filename}.png")

        if temp_file and os.path.exists(temp_file):
            os.rename(temp_file, img_path)

        # =========================
        # SAVE SHEET
        # =========================
        sheet4.append_rows(rows)

        for row in rows:
            append_stock_log(
                name=row[0],
                size=row[1],
                stock=row[2],
                stock_status="INIT_ADD",
                order_id="ADD_IMAGE"
            )

        clear_state(user_id)

        # =========================
        # RESPONSE
        # =========================
        self.telegram.send_text(
            chat_id,
            (
                f"✅ Created item\n\n"
                f"📦 Name: {name}\n"
                f"📏 Sizes: {len(rows)}\n"
                f"📊 Total Stock: {sum(r[2] for r in rows)}"
            ),
            thread_id
        )

        return True