"""take_screenshots.py: Capture multi-viewport screenshots of Shelf Check demo using headless Chrome."""
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT_DIR = ROOT / "qa" / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Start server
server_proc = subprocess.Popen(
    [str(ROOT / ".venv" / "bin" / "uvicorn"), "server.main:app", "--host", "127.0.0.1", "--port", "8888"],
    cwd=str(ROOT),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

try:
    # Wait for server to be ready
    url = "http://127.0.0.1:8888"
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.3)
    else:
        raise RuntimeError("Server failed to start on port 8888")

    viewports = [
        ("desktop_1920x1080.png", 1920, 1080),
        ("desktop_1440x900.png", 1440, 900),
        ("desktop_1280x720.png", 1280, 720),
        ("mobile_390x844.png", 390, 844),
    ]

    for filename, width, height in viewports:
        out_file = OUT_DIR / filename
        cmd = [
            CHROME,
            "--headless=new",
            f"--window-size={width},{height}",
            "--hide-scrollbars",
            "--virtual-time-budget=2000",
            f"--screenshot={out_file}",
            url,
        ]
        subprocess.run(cmd, check=True)
        print(f"Captured {out_file} ({width}x{height})")

finally:
    server_proc.terminate()
    server_proc.wait()
