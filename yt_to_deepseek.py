"""
YouTube → DeepSeek Summarizer
==============================

Extracts YouTube CC subtitles → sends to DeepSeek for analysis →
outputs a beautifully formatted HTML page on your Desktop.

Usage:
    python yt_to_deepseek.py "https://www.youtube.com/watch?v=VIDEO_ID"

Dependencies:
    pip install -r requirements.txt
    playwright install chromium
"""

import time
import subprocess
import sys
import os
import re
import socket

# ── Imports from sibling modules ──────────────────────────
from subtitle_extractor import download_subs, get_video_title
from deepseek_automation import run_deepseek_automation

import pyperclip

EDGE = os.environ.get("EDGE_PATH", "")
if not EDGE:
    for candidate in [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]:
        if os.path.isfile(candidate):
            EDGE = candidate
            break

CDP_PORT = 9222


def sanitize_filename(name: str) -> str:
    """Replace illegal filename characters."""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.strip().rstrip('.')
    return name or "deepseek_reply"


def ensure_edge_debug():
    """Ensure Edge is running with remote debugging enabled."""
    s = socket.socket()
    s.settimeout(1)
    if s.connect_ex(("127.0.0.1", CDP_PORT)) == 0:
        s.close()
        return
    s.close()

    print("Edge 调试端口未开启，正在启动 ...")
    if EDGE:
        subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"],
                       capture_output=True)
        time.sleep(1)
        subprocess.Popen([EDGE, f"--remote-debugging-port={CDP_PORT}"])
        for _ in range(15):
            time.sleep(1)
            s = socket.socket()
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", CDP_PORT)) == 0:
                s.close()
                print("   调试端口已就绪")
                return
            s.close()
        print("警告: Edge 调试端口未能自动开启，请手动运行:")
        print(f'  "{EDGE}" --remote-debugging-port={CDP_PORT}')
        sys.exit(1)
    else:
        print("未找到 Edge，请手动启动并设置 EDGE_PATH 环境变量。")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python yt_to_deepseek.py <youtube_url>")
        print("Example: python yt_to_deepseek.py \"https://www.youtube.com/watch?v=xxx\"")
        sys.exit(1)

    url = sys.argv[1]

    # ── Ensure Edge is ready ────────────────────────────
    ensure_edge_debug()

    # ── Step 1: get title + subtitles ──────────────────
    print("Fetching video title ...")
    raw_title = get_video_title(url)
    clean_title = sanitize_filename(raw_title)
    print(f"Video: {raw_title}")

    print()
    print("=" * 50)
    print("[1/2] Extracting YouTube subtitles ...")
    print("=" * 50)

    text, lang, sub_type = download_subs(url)
    pyperclip.copy(text)
    print(f"Copied to clipboard — {len(text)} chars, {lang} ({sub_type})")

    time.sleep(0.3)

    # ── Step 2: DeepSeek automation ────────────────────
    print()
    print("=" * 50)
    print("[2/2] DeepSeek analysis (CDP) ...")
    print("=" * 50)

    run_deepseek_automation(title=clean_title)


if __name__ == "__main__":
    main()
