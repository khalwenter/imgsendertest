import requests
import time
import json

BOT_TOKEN = "7479661726:AAFKFBbOK4dkZRBZ8QkeyrVLcxkkLg8k8go"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

last_update_id = None


def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset

    response = requests.get(f"{API_URL}/getUpdates", params=params)
    return response.json()


def extract_info(update):

    print("\n================ FULL UPDATE ================\n")
    print(json.dumps(update, indent=2, ensure_ascii=False))
    print("\n============================================\n")

    message = update.get("message") or update.get("channel_post")

    if not message:
        print("No message found")
        return

    chat = message.get("chat", {})

    chat_id = chat.get("id")
    chat_type = chat.get("type")
    chat_title = chat.get("title") or chat.get("username") or chat.get("first_name")

    thread_id = message.get("message_thread_id")
    text = message.get("text")

    print("CHAT ID:", chat_id)
    print("CHAT TYPE:", chat_type)
    print("CHAT NAME:", chat_title)
    print("THREAD ID:", thread_id)
    print("TEXT:", text)
    print("--------------------------------------------")


def main():

    global last_update_id

    print("🤖 Listening for Telegram updates...")

    while True:

        try:
            updates = get_updates(last_update_id)

            if "result" not in updates:
                print("Error:", updates)
                time.sleep(3)
                continue

            for update in updates["result"]:

                last_update_id = update["update_id"] + 1

                extract_info(update)

            time.sleep(1)

        except Exception as e:
            print("Error:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()