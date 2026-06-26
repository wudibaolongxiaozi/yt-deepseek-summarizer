"""
YouTube CC subtitle extractor.

Downloads subtitles from a YouTube video and copies plain text to clipboard.
Priority: manual subtitles > auto-generated; zh-Hans > zh-CN > zh > en.

Usage:
    python subtitle_extractor.py "https://www.youtube.com/watch?v=..."

Dependencies:
    pip install yt-dlp pyperclip
"""

import sys
import os
import re
import tempfile
import subprocess

import pyperclip

LANG_PRIORITY = ["zh-Hans", "zh-CN", "zh", "en"]


def _try_download(url: str, lang: str, auto: bool, workdir: str) -> str | None:
    """Download subs for one (lang, type) combo. Returns file path or None."""
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-auto-subs" if auto else "--write-subs",
        "--sub-langs", lang,
        "--convert-subs", "vtt",
        "--no-warnings",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir)
    if result.returncode != 0:
        return None

    for fname in os.listdir(workdir):
        if lang.lower() in fname.lower() and fname.endswith((".vtt", ".srt")):
            return os.path.join(workdir, fname)
    return None


def extract_text(filepath: str) -> str:
    """Extract plain text from VTT / SRT, removing timestamps and metadata."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line == "WEBVTT":
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        if line.startswith(("NOTE", "Kind:", "Language:")):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = line.strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def download_subs(url: str) -> tuple[str, str, str]:
    """Download subtitles for a YouTube URL.

    Returns:
        (text, lang, type) where type is 'manual' or 'auto-generated'.
    """
    with tempfile.TemporaryDirectory(prefix="yt_subs_") as tmpdir:
        final_path = None
        chosen_lang = None
        chosen_type = None

        for lang in LANG_PRIORITY:
            # Manual first
            print(f"Trying manual subtitles ({lang})...", end=" ", flush=True)
            path = _try_download(url, lang, auto=False, workdir=tmpdir)
            if path:
                final_path = path
                chosen_lang = lang
                chosen_type = "manual"
                print("OK")
                break
            print("not found")

            # Then auto-generated
            print(f"Trying auto-generated subtitles ({lang})...", end=" ", flush=True)
            path = _try_download(url, lang, auto=True, workdir=tmpdir)
            if path:
                final_path = path
                chosen_lang = lang
                chosen_type = "auto-generated"
                print("OK")
                break
            print("not found")

        if not final_path:
            raise RuntimeError("No suitable subtitles found.")

        text = extract_text(final_path)
        if not text.strip():
            raise RuntimeError("Subtitle file is empty.")

        return text, chosen_lang, chosen_type


def get_video_title(url: str) -> str:
    """Get YouTube video title via yt-dlp."""
    result = subprocess.run(
        ["yt-dlp", "--get-title", url],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0 or not result.stdout.strip():
        return "deepseek_reply"
    return result.stdout.strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: python subtitle_extractor.py <youtube_url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Fetching subtitles for: {url}")

    text, lang, sub_type = download_subs(url)
    pyperclip.copy(text)
    print(f"Copied to clipboard — {len(text)} chars, {lang} ({sub_type})")


if __name__ == "__main__":
    main()
