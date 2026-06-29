import os
import requests

REQUEST_TIMEOUT = 60


class TelegramAPI:

    def __init__(self, bot_token):

        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.file_url = f"https://api.telegram.org/file/bot{bot_token}"

    # ============================================
    # BASIC MESSAGE
    # ============================================

    def send_text(self, chat_id, text, thread_id=None):

        try:
            data = {
                "chat_id": chat_id,
                "text": text
            }

            if thread_id is not None:
                data["message_thread_id"] = thread_id

            r = requests.post(
                f"{self.api_url}/sendMessage",
                data=data,
                timeout=REQUEST_TIMEOUT
            )

            return r.ok

        except Exception as e:
            print("❌ send_text:", e)
            return False

    # ============================================
    # SEND PHOTO
    # ============================================

    def send_photo(self, chat_id, photo_path, caption="", thread_id=None):

        try:
            data = {
                "chat_id": chat_id,
                "caption": caption
            }

            if thread_id is not None:
                data["message_thread_id"] = thread_id

            with open(photo_path, "rb") as photo:
                r = requests.post(
                    f"{self.api_url}/sendPhoto",
                    data=data,
                    files={"photo": photo},
                    timeout=REQUEST_TIMEOUT
                )

            return r.ok

        except Exception as e:
            print("❌ send_photo:", e)
            return False
    # ============================================
    # SEND MEDIA GROUP
    # ============================================

    def send_media_group(self, chat_id, media):

        try:

            data = {
                "chat_id": chat_id,
                "media": media
            }

            r = requests.post(
                f"{self.api_url}/sendMediaGroup",
                data=data,
                timeout=REQUEST_TIMEOUT
            )

            return r.ok

        except Exception as e:
            print("❌ send_media_group:", e)
            return False

    # ============================================
    # GET FILE INFO
    # ============================================

    def get_file(self, file_id):

        try:

            r = requests.get(
                f"{self.api_url}/getFile",
                params={
                    "file_id": file_id
                },
                timeout=REQUEST_TIMEOUT
            )

            data = r.json()

            if not data["ok"]:
                return None

            return data["result"]

        except Exception as e:
            print("❌ get_file:", e)
            return None

    # ============================================
    # DOWNLOAD TELEGRAM FILE
    # ============================================

    def download_file(
        self,
        file_id,
        save_path
    ):

        file_info = self.get_file(file_id)

        if not file_info:
            return False

        file_path = file_info["file_path"]

        url = f"{self.file_url}/{file_path}"

        try:

            r = requests.get(
                url,
                timeout=REQUEST_TIMEOUT
            )

            if not r.ok:
                return False

            with open(save_path, "wb") as f:
                f.write(r.content)

            return True

        except Exception as e:
            print("❌ download_file:", e)
            return False

    # ============================================
    # SEND DOCUMENT
    # ============================================

    def send_document(
        self,
        chat_id,
        file_path,
        caption=""
    ):

        try:

            with open(file_path, "rb") as f:

                r = requests.post(
                    f"{self.api_url}/sendDocument",
                    data={
                        "chat_id": chat_id,
                        "caption": caption
                    },
                    files={
                        "document": f
                    },
                    timeout=REQUEST_TIMEOUT
                )

            return r.ok

        except Exception as e:
            print("❌ send_document:", e)
            return False

    # ============================================
    # SEND ACTION
    # ============================================

    def send_action(
        self,
        chat_id,
        action="upload_photo"
    ):

        try:

            requests.post(
                f"{self.api_url}/sendChatAction",
                data={
                    "chat_id": chat_id,
                    "action": action
                },
                timeout=REQUEST_TIMEOUT
            )

        except:
            pass

    # ============================================
    # DELETE MESSAGE
    # ============================================

    def delete_message(
        self,
        chat_id,
        message_id
    ):

        try:

            r = requests.post(
                f"{self.api_url}/deleteMessage",
                data={
                    "chat_id": chat_id,
                    "message_id": message_id
                },
                timeout=REQUEST_TIMEOUT
            )

            return r.ok

        except Exception as e:
            print("❌ delete_message:", e)
            return False

    # ============================================
    # GET UPDATES
    # ============================================

    def get_updates(
        self,
        offset=None,
        timeout=30
    ):

        try:

            params = {
                "timeout": timeout
            }

            if offset:
                params["offset"] = offset

            r = requests.get(
                f"{self.api_url}/getUpdates",
                params=params,
                timeout=timeout + 10
            )

            return r.json()

        except Exception as e:
            print("❌ get_updates:", e)
            return {
                "ok": False
            }

    # ============================================
    # LIST IMAGES
    # ============================================

    def send_inventory(
        self,
        chat_id,
        folder="img"
    ):

        if not os.path.exists(folder):

            self.send_text(
                chat_id,
                "📂 img folder not found."
            )
            return

        files = sorted(os.listdir(folder))

        pngs = [
            f for f in files
            if f.lower().endswith(".png")
        ]

        if not pngs:

            self.send_text(
                chat_id,
                "📂 Inventory is empty."
            )
            return

        total = 0

        for img in pngs:

            path = os.path.join(
                folder,
                img
            )

            caption = os.path.splitext(img)[0]

            self.send_photo(
                chat_id,
                path,
                caption
            )

            total += 1

        self.send_text(
            chat_id,
            f"📦 Inventory\n\nTotal Images : {total}"
        )