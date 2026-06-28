import subprocess
import time

while True:
    print("=" * 60)
    print("Starting imgsender.py...")
    print("=" * 60)

    try:
        process = subprocess.Popen(
            ["python", "imgsender.py"]
        )

        process.wait()

        print(f"Bot exited with code {process.returncode}")

    except Exception as e:
        print("Supervisor Error:", e)

    print("Restarting in 5 seconds...")
    time.sleep(5)   