import os
import tempfile
from PIL import Image, ImageDraw, ImageFont
import math
from telegram_utils import TelegramAPI

from image_utils import (
    save_inventory_image,
    delete_inventory_image,
    image_exists,
    get_inventory,
    search_inventory,
)

from inventory_state import (
    set_state,
    get_state,
    get_mode,
    get_data,
    update_data,
    clear_state,

    MODE_WAITING_PHOTO,
    MODE_WAITING_IMAGE_NAME,

    MODE_WAITING_DELETE_NAME,
    MODE_WAITING_DELETE_CONFIRM,
)


class InventoryManager:

    def __init__(self, bot_token, img_folder="img"):
        self.telegram = TelegramAPI(bot_token)
        self.img_folder = img_folder
        os.makedirs(self.img_folder, exist_ok=True)

    # ============================================
    # FAST VIEW ALL GRID (OPTIMIZED)
    # ============================================
    def view_all_grid(self, chat_id, thread_id=None):

        import math
        import tempfile
        from PIL import Image, ImageDraw, ImageFont

        items = get_inventory(self.img_folder)

        if not items:
            self.telegram.send_text(chat_id, "📦 Inventory is empty.", thread_id)
            return

        # format data
        images = [{"path": i["path"], "name": i["name"]} for i in items]

        MAX_PER_GRID = 40
        cols = 5
        thumb_w, thumb_h = 250, 200

        # ✅ REAL FONT FIX (important)
        font_size = 25
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()

        def build_grid(chunk, page):

            rows = math.ceil(len(chunk) / cols)

            cell_w = thumb_w
            cell_h = thumb_h + 50   # ✅ space for text

            grid = Image.new(
                "RGB",
                (cols * cell_w, rows * cell_h),
                (255, 255, 255)
            )

            draw = ImageDraw.Draw(grid)

            for i, item in enumerate(chunk):

                r = i // cols
                c = i % cols

                try:
                    img = Image.open(item["path"]).convert("RGB")
                    img.thumbnail((thumb_w, thumb_h))

                    x = c * cell_w
                    y = r * cell_h

                    grid.paste(img, (x, y))

                    # ===== TEXT (NAME) =====
                    name = item["name"]

                    # truncate long names
                    if len(name) > 18:
                        name = name[:18] + "..."

                    text_x = x + 5
                    text_y = y + thumb_h + 10

                    draw.text(
                        (text_x, text_y),
                        name,
                        fill=(0, 0, 0),
                        font=font
                    )

                except Exception as e:
                    print("GRID ERROR:", e)

            temp_path = os.path.join(
                tempfile.gettempdir(),
                f"inventory_grid_{page}.jpg"
            )

            grid.save(temp_path, "JPEG", quality=85)

            self.telegram.send_photo(
                chat_id=chat_id,
                photo_path=temp_path,
                caption=f"📦 Inventory ({len(chunk)} items) | Page {page+1}",
                thread_id=thread_id
            )

        # split into chunks of 40
        chunks = [
            images[i:i + MAX_PER_GRID]
            for i in range(0, len(images), MAX_PER_GRID)
        ]

        for page, chunk in enumerate(chunks):
            build_grid(chunk, page)



    # ============================================
    # SHOW INVENTORY (KEEP ORIGINAL)
    # ============================================
    def show_inventory(self, chat_id, thread_id=None):

        items = get_inventory(self.img_folder)

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

        items = get_inventory(self.img_folder)

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
    # CANCEL
    # ============================================
    def cancel(self, user_id, chat_id, thread_id=None):

        state = get_state(user_id)

        if state:
            data = state.get("data", {})
            temp = data.get("temp_file")

            if temp and os.path.exists(temp):
                os.remove(temp)

        clear_state(user_id)
        self.telegram.send_text(chat_id, "Cancelled", thread_id)