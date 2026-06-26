"""
DeepSeek CDP automation via Playwright.

Connects to a running Edge browser (--remote-debugging-port=9222),
navigates to DeepSeek Chat, pastes clipboard content, sends, waits,
extracts the reply (excluding thinking chain), cleans citation artifacts,
and returns the result.

Usage (standalone):
    python deepseek_automation.py [--title FILENAME]

Or import:
    from deepseek_automation import run_deepseek_automation
    reply = run_deepseek_automation(title="My Video")
"""

import time
import subprocess
import os
import re
import argparse
import sys

from playwright.sync_api import sync_playwright

DEEPSEEK_URL = "https://chat.deepseek.com/"
DESKTOP = os.path.join(os.environ["USERPROFILE"], "Desktop")
CDP_URL = "http://127.0.0.1:9222"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --bg: #fafaf8;
    --text: #1a1a1a;
    --muted: #6b6b6b;
    --border: #e5e5e0;
    --accent: #2563eb;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.85;
    max-width: 720px; margin: 60px auto; padding: 0 24px;
  }}
  h1 {{ font-size: 1.5em; margin: 1.2em 0 .4em; }}
  h2 {{ font-size: 1.2em; margin: 1em 0 .3em; color: var(--accent); }}
  h3 {{ font-size: 1.05em; margin: .8em 0 .2em; }}
  p  {{ margin: .6em 0; }}
  ul, ol {{ margin: .4em 0 .4em 1.5em; }}
  li {{ margin: .15em 0; }}
  li > p {{ margin: .2em 0; }}
  strong {{ font-weight: 600; }}
  em {{ font-style: italic; }}
  blockquote {{
    border-left: 3px solid var(--accent);
    padding-left: 16px; margin: .8em 0;
    color: var(--muted);
  }}
  hr {{ border: none; border-top: 1px solid var(--border); margin: 1.5em 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: .8em 0; font-size: .92em; }}
  th, td {{ border: 1px solid var(--border); padding: 8px 12px; text-align: left; }}
  th {{ background: #f0f0ec; font-weight: 600; }}
  code {{ background: #eee; padding: 1px 5px; border-radius: 4px; font-size: .9em; }}
  pre {{ background: #2d2d2d; color: #f8f8f2; padding: 16px; border-radius: 8px; overflow-x: auto; margin: .8em 0; }}
  pre code {{ background: none; padding: 0; }}
</style>
</head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>"""


# ═══════════════════════════════════════════════════════════
#  Clipboard
# ═══════════════════════════════════════════════════════════

def _read_clipboard() -> str:
    ps_cmd = (
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "Get-Clipboard"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True, encoding="utf-8", timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(f"Get-Clipboard failed: {result.stderr}")
    return result.stdout


# ═══════════════════════════════════════════════════════════
#  Text cleanup
# ═══════════════════════════════════════════════════════════

def _clean_text(text: str) -> str:
    """Remove DeepSeek citation artifacts and orphaned punctuation."""
    text = re.sub(r'-\d{1,3}-', '', text)
    text = re.sub(r'\n?-+\s*\n-*\s*\n?\s*\d{1,3}\s*\n?', '\n', text)
    text = re.sub(r'-(\s*\n)', r'\1', text)
    text = re.sub(r'\n-\s*\d{1,3}\s*\n', '\n', text)
    text = re.sub(r'\n-\s*\n', '\n', text)
    text = re.sub(r'-\s*$', '', text)
    text = re.sub(r'\n([。，、；：）\)])\s*\n', r'\1\n', text)
    text = re.sub(r'\n([。，、；：）\)])\s*$', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' +$', '', text, flags=re.MULTILINE)
    return text.strip()


# ═══════════════════════════════════════════════════════════
#  Markdown → HTML
# ═══════════════════════════════════════════════════════════

def _md_to_html(text: str) -> str:
    """Convert Markdown-ish text to HTML."""
    lines = text.split('\n')
    out = []
    list_tag = None
    in_paragraph = False
    in_table = False
    table_rows = []

    def flush_paragraph():
        nonlocal in_paragraph
        if in_paragraph:
            out.append('</p>')
            in_paragraph = False

    def flush_list():
        nonlocal list_tag
        if list_tag:
            out.append(f'</{list_tag}>')
            list_tag = None

    def flush_table():
        nonlocal in_table, table_rows
        if in_table and table_rows:
            out.append('<table>')
            out.append('<thead><tr>')
            for cell in table_rows[0]:
                out.append(f'<th>{cell}</th>')
            out.append('</tr></thead><tbody>')
            for row in table_rows[1:]:
                out.append('<tr>')
                for cell in row:
                    out.append(f'<td>{cell}</td>')
                out.append('</tr>')
            out.append('</tbody></table>')
        in_table = False
        table_rows = []

    def _is_header(line: str) -> bool:
        s = line.strip()
        if s.startswith(('#', '##', '###')):
            return True
        if re.match(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF]', s):
            return True
        if re.match(r'^[一二三四五六七八九十]、', s):
            return True
        return False

    def _inline(text: str) -> str:
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        return text

    for line in lines:
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_list()
            flush_table()
            continue

        m = re.match(r'^(#{1,3})\s+(.+)', stripped)
        if m:
            flush_paragraph(); flush_list(); flush_table()
            level = len(m.group(1))
            out.append(f'<h{level}>{_inline(m.group(2))}</h{level}>')
            continue

        if re.match(r'^[-*_]{3,}$', stripped):
            flush_paragraph(); flush_list(); flush_table()
            out.append('<hr>')
            continue

        if '|' in stripped and not stripped.startswith('>'):
            cells = [c.strip() for c in stripped.split('|') if c.strip()]
            if cells:
                if all(re.match(r'^[-:]+$', c) for c in cells):
                    continue
                flush_paragraph(); flush_list()
                if not in_table:
                    in_table = True
                table_rows.append(cells)
            continue

        m_ul = re.match(r'^[-*+]\s+(.*)', stripped)
        if m_ul:
            flush_paragraph(); flush_table()
            if list_tag != 'ul':
                flush_list()
                out.append('<ul>')
                list_tag = 'ul'
            out.append(f'<li>{_inline(m_ul.group(1))}</li>')
            continue

        m_ol = re.match(r'^(\d+)\.\s+(.*)', stripped)
        if m_ol:
            flush_paragraph(); flush_table()
            if list_tag != 'ol':
                flush_list()
                out.append('<ol>')
                list_tag = 'ol'
            out.append(f'<li>{_inline(m_ol.group(2))}</li>')
            continue

        if stripped.startswith('> '):
            flush_paragraph(); flush_list(); flush_table()
            out.append(f'<blockquote>{_inline(stripped[2:])}</blockquote>')
            continue

        if _is_header(stripped):
            flush_paragraph(); flush_list(); flush_table()
            out.append(f'<h2>{_inline(stripped)}</h2>')
            continue

        flush_list(); flush_table()
        if not in_paragraph:
            out.append('<p>')
            in_paragraph = True
        out.append(f'{_inline(stripped)} ')

    flush_paragraph()
    flush_list()
    flush_table()

    return '\n'.join(out)


# ═══════════════════════════════════════════════════════════
#  DeepSeek page operations
# ═══════════════════════════════════════════════════════════

def _extract_answer(page) -> str:
    """Extract final reply from DeepSeek page, excluding thinking chain."""
    answer_parts = []
    all_md = page.locator(".ds-markdown").all()
    thinking = page.locator("[class*=think]").all()

    thinking_texts = set()
    for t in thinking:
        try:
            txt = t.inner_text().strip()
            if txt:
                thinking_texts.add(txt[:100])
        except Exception:
            pass

    for blk in all_md:
        try:
            txt = blk.inner_text().strip()
        except Exception:
            continue
        if not txt:
            continue
        if any(txt[:100] == tt for tt in thinking_texts):
            continue
        answer_parts.append(txt)

    if answer_parts:
        return _clean_text("\n\n".join(answer_parts))

    longest = ""
    for blk in all_md:
        try:
            txt = blk.inner_text()
            if len(txt) > len(longest):
                longest = txt
        except Exception:
            pass
    return _clean_text(longest)


def _find_or_open_page(browser):
    """Find existing DeepSeek page or create a new one with textarea ready."""
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "deepseek.com" in pg.url:
                try:
                    pg.wait_for_selector("textarea", timeout=2000)
                    print("复用已有 DeepSeek 页面")
                    return pg
                except Exception:
                    print("已有页面输入框不可用，重新打开 ...")
                    pg.close()
                    break

    print(f"新建页面: {DEEPSEEK_URL}")
    page = browser.contexts[0].new_page()
    page.goto(DEEPSEEK_URL, wait_until="domcontentloaded")
    page.wait_for_selector("textarea", timeout=15000)
    return page


# ═══════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════

def run_deepseek_automation(title: str = "clipboard_save") -> str:
    """Run the full DeepSeek automation pipeline.

    Reads clipboard, sends to DeepSeek via CDP, waits 30s for reply,
    extracts + cleans the answer, saves .html + .txt to Desktop.

    Returns the cleaned reply text.
    """
    prompt_text = _read_clipboard()
    if not prompt_text.strip():
        raise RuntimeError("剪贴板为空，请先复制要发送的内容。")
    print(f"剪贴板内容: {len(prompt_text)} chars")

    with sync_playwright() as p:
        print(f"正在连接 Edge (CDP: {CDP_URL}) ...")
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            print(f"无法连接 Edge，请确认已启动: msedge --remote-debugging-port=9222")
            raise RuntimeError(str(e)) from e

        page = _find_or_open_page(browser)
        time.sleep(0.5)

        print("   填入剪贴板内容 ...")
        textarea = page.locator("textarea").first
        textarea.fill(prompt_text)
        time.sleep(0.3)

        print("   发送 ...")
        page.locator("textarea").first.press("Enter")

        print("等待 30 秒 (DeepSeek 生成回复) ...")
        time.sleep(30)

        print("   提取回复内容 ...")
        reply = _extract_answer(page)
        if not reply:
            reply = "[无法提取回复内容]"
        print(f"   提取到 {len(reply)} chars")
        print("   完成（浏览器保持运行）")

    # Save
    safe = re.sub(r'[\\/:*?"<>|]', '_', title).strip().rstrip('.')
    if len(safe) > 120:
        safe = safe[:120]

    html_body = _md_to_html(reply)
    html = HTML_TEMPLATE.format(title=safe, body=html_body)
    html_path = os.path.join(DESKTOP, f"{safe}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML → {html_path}")

    txt_path = os.path.join(DESKTOP, f"{safe}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(reply)
    print(f"TXT  → {txt_path}")

    return reply


# ═══════════════════════════════════════════════════════════
#  CLI entry
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="DeepSeek CDP automation")
    parser.add_argument("--title", default="clipboard_save",
                        help="Output filename (without extension)")
    args = parser.parse_args()

    try:
        run_deepseek_automation(title=args.title)
    except RuntimeError as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
