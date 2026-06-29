import subprocess
import time
import os
from datetime import datetime

# ============================
# CONFIG
# ============================

SCRIPT = "imgsender.py"

CHECK_INTERVAL = 5          # seconds
MAX_RUNTIME = 3600          # restart every 1 hour (prevent memory leak)
LOG_FILE = "bot_supervisor.log"


# ============================
# LOGGER
# ============================

def log(text):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {text}"

    print(line)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ============================
# MAIN LOOP
# ============================

while True:

    log("=" * 60)
    log("🚀 Starting imgsender.py")

    start_time = time.time()

    process = subprocess.Popen(
        ["python", SCRIPT]
    )

    try:

        while True:

            # process exited?
            if process.poll() is not None:

                log(f"❌ Bot exited with code {process.returncode}")
                break

            runtime = time.time() - start_time

            # restart every X hours
            if runtime > MAX_RUNTIME:

                log("♻ Maximum runtime reached.")
                log("Stopping bot...")

                process.kill()
                process.wait()

                break

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:

        log("Stopping supervisor...")

        process.kill()
        process.wait()

        break

    except Exception as e:

        log(f"Supervisor Error: {e}")

        try:
            process.kill()
            process.wait()
        except:
            pass

    log("Restarting in 5 seconds...")
    time.sleep(5)