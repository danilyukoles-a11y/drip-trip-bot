# Telegram Bot Crawler — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Побудувати Python-скрипт, який автоматично обходить Telegram-бота `@Vape_Rivne_Bot` і зберігає повне дерево навігації (тексти, кнопки, callback_data) у JSON + Markdown.

**Architecture:** Один скрипт на Telethon, який авторизується як звичайний користувач, відправляє `/start`, рекурсивно натискає кнопки (inline напряму, reply через скид стану `/start`) і записує кожен екран як вузол дерева. Блеклист захищає від небезпечних дій (оформлення замовлень, оплата).

**Tech Stack:** Python, Telethon, python-dotenv

**Spec:** `docs/superpowers/specs/2026-04-03-telegram-bot-crawler-design.md`

---

## File Structure

| Файл | Відповідальність |
|---|---|
| `crawler/config.py` | Константи: бот, глибина, затримки, блеклист, навігаційні патерни |
| `crawler/crawler.py` | Основна логіка: авторизація, рекурсивний обхід, збір даних |
| `crawler/exporter.py` | Генерація JSON та Markdown з дерева вузлів |
| `crawler/requirements.txt` | Залежності |
| `crawler/.env.example` | Шаблон credentials |
| `crawler/.gitignore` | Ігнорувати .env, .session |
| `output/` | Директорія для результатів (створюється скриптом) |

---

## Task 1: Project scaffolding

**Files:**
- Create: `crawler/requirements.txt`
- Create: `crawler/.env.example`
- Create: `crawler/.gitignore`

- [ ] **Step 1: Create `crawler/requirements.txt`**

```
telethon==1.37.0
python-dotenv==1.1.0
```

- [ ] **Step 2: Create `crawler/.env.example`**

```
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
```

- [ ] **Step 3: Create `crawler/.gitignore`**

```
.env
*.session
__pycache__/
```

- [ ] **Step 4: Install dependencies**

Run: `pip install -r crawler/requirements.txt`
Expected: Successfully installed telethon, python-dotenv

- [ ] **Step 5: Commit**

```bash
git add crawler/requirements.txt crawler/.env.example crawler/.gitignore
git commit -m "chore: scaffold crawler project"
```

---

## Task 2: Configuration module

**Files:**
- Create: `crawler/config.py`

- [ ] **Step 1: Create `crawler/config.py`**

```python
import os
from dotenv import load_dotenv

_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_DIR, ".env"))

# Telegram credentials
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")
SESSION_NAME = "crawler_session"

# Target bot
BOT_USERNAME = "Vape_Rivne_Bot"

# Crawling limits
MAX_DEPTH = 6
DELAY_BETWEEN_ACTIONS = 1.5        # seconds
RESPONSE_TIMEOUT = 10               # seconds
MULTI_MESSAGE_WAIT = 2              # seconds
MAX_RETRIES = 2

# Unsafe button patterns (case-insensitive substring match)
# These buttons are recorded but NOT clicked
UNSAFE_PATTERNS = [
    "замовлен", "оформ", "підтверд",
    "оплат", "сплат", "liqpay", "pay",
    "видалити все", "очистити",
]

# Navigation button patterns (case-insensitive)
# Exact match for short words, substring for longer phrases
# These buttons are recorded but NOT clicked
NAV_PATTERNS_EXACT = ["назад", "back", "◀️", "⬅️", "↩️"]
NAV_PATTERNS_SUBSTRING = ["головне меню", "на початок", "main menu", "меню"]

# Reset commands to try when returning to initial state (for reply keyboards)
RESET_COMMANDS = ["/start", "/menu", "Меню"]

# Output paths (relative to project root, i.e. parent of crawler/)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "bot_structure.json")
OUTPUT_MD = os.path.join(OUTPUT_DIR, "bot_structure.md")
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile crawler/config.py`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add crawler/config.py
git commit -m "feat: add crawler configuration module"
```

---

## Task 3: Core crawler logic

**Files:**
- Create: `crawler/crawler.py`

This is the main module. It handles:
- Telethon client setup and auth
- Button classification (safe / unsafe / nav / url)
- Screen hashing for deduplication
- Recursive tree traversal
- FloodWaitError handling

- [ ] **Step 1: Create `crawler/crawler.py` — imports and helpers**

```python
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime

from telethon import TelegramClient, events, errors
from telethon.tl.types import (
    ReplyKeyboardMarkup,
    ReplyInlineMarkup,
    KeyboardButtonCallback,
    KeyboardButtonUrl,
    KeyboardButtonRequestPhone,
    KeyboardButtonRequestGeoLocation,
    KeyboardButtonSwitchInline,
    KeyboardButton,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config


def is_unsafe(text: str) -> bool:
    """Check if button text matches unsafe patterns."""
    lower = text.lower()
    return any(p in lower for p in config.UNSAFE_PATTERNS)


def is_nav(text: str) -> bool:
    """Check if button text matches navigation patterns."""
    lower = text.lower().strip()
    if lower in config.NAV_PATTERNS_EXACT:
        return True
    return any(p in lower for p in config.NAV_PATTERNS_SUBSTRING)


def hash_buttons(inline_buttons: list, reply_buttons: list) -> str:
    """Create a hash from button set for deduplication.
    
    Only uses button texts and callback_data, NOT message text
    (which may contain dynamic content).
    """
    parts = []
    for btn in inline_buttons:
        parts.append(f"i:{btn['text']}:{btn.get('callback_data', '')}")
    for btn in reply_buttons:
        parts.append(f"r:{btn}")
    raw = "|".join(sorted(parts))
    return hashlib.md5(raw.encode()).hexdigest()


def extract_inline_buttons(message) -> list:
    """Extract inline keyboard buttons from a message."""
    buttons = []
    if message.reply_markup and isinstance(message.reply_markup, ReplyInlineMarkup):
        for row in message.reply_markup.rows:
            for btn in row.buttons:
                entry = {"text": btn.text}
                if isinstance(btn, KeyboardButtonCallback):
                    entry["callback_data"] = btn.data.decode("utf-8", errors="replace")
                    entry["type"] = "callback"
                elif isinstance(btn, KeyboardButtonUrl):
                    entry["url"] = btn.url
                    entry["type"] = "url"
                elif isinstance(btn, KeyboardButtonSwitchInline):
                    entry["switch_inline_query"] = btn.query
                    entry["type"] = "switch_inline"
                else:
                    entry["type"] = "other"
                buttons.append(entry)
    return buttons


def extract_reply_buttons(message) -> list:
    """Extract reply keyboard buttons from a message."""
    buttons = []
    if message.reply_markup and isinstance(message.reply_markup, ReplyKeyboardMarkup):
        for row in message.reply_markup.rows:
            for btn in row.buttons:
                if isinstance(btn, KeyboardButtonRequestPhone):
                    buttons.append({"text": btn.text, "type": "request_contact"})
                elif isinstance(btn, KeyboardButtonRequestGeoLocation):
                    buttons.append({"text": btn.text, "type": "request_location"})
                else:
                    buttons.append({"text": btn.text, "type": "text"})
    return buttons


def extract_media_info(message) -> dict | None:
    """Extract media type and caption without downloading."""
    if message.photo:
        return {"type": "photo", "caption": message.text or ""}
    elif message.video:
        return {"type": "video", "caption": message.text or ""}
    elif message.document:
        return {"type": "document", "caption": message.text or ""}
    elif message.sticker:
        return {"type": "sticker", "caption": ""}
    return None
```

- [ ] **Step 2: Add the main crawler class**

Append to `crawler/crawler.py`:

```python
class BotCrawler:
    def __init__(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.client = TelegramClient(
            os.path.join(script_dir, config.SESSION_NAME),
            config.API_ID,
            config.API_HASH,
        )
        self.bot_entity = None
        self.visited_hashes: set[str] = set()
        self.stats = {
            "total_screens": 0,
            "total_buttons": 0,
            "skipped_unsafe": 0,
            "skipped_nav": 0,
            "max_depth_reached": 0,
            "timeouts": 0,
            "reset_failures": 0,
        }

    async def start(self):
        """Connect and authorize."""
        await self.client.start(phone=config.PHONE)
        self.bot_entity = await self.client.get_entity(config.BOT_USERNAME)
        print(f"Connected. Target bot: @{config.BOT_USERNAME}")

    async def _get_last_msg_id(self) -> int:
        """Get ID of the last message in the chat with the bot."""
        async for msg in self.client.iter_messages(self.bot_entity, limit=1):
            return msg.id
        return 0

    async def _collect_new_messages(self, after_id: int) -> list:
        """Collect messages from the bot that arrived after after_id."""
        responses = []
        async for msg in self.client.iter_messages(
            self.bot_entity, limit=20, min_id=after_id
        ):
            # Only messages FROM the bot (not our own)
            if msg.sender_id == self.bot_entity.id:
                responses.append(msg)
        return responses

    async def send_and_wait(self, text: str = None, callback_data: bytes = None, message=None) -> list:
        """Send a message or click a button, wait for bot response(s).
        
        Uses min_id tracking to only read NEW messages after our action.
        Returns a list of messages from the bot, sorted oldest-first.
        """
        for attempt in range(config.MAX_RETRIES + 1):
            try:
                # Remember last message ID BEFORE sending
                last_id = await self._get_last_msg_id()

                if callback_data and message:
                    await message.click(data=callback_data)
                elif text:
                    await self.client.send_message(self.bot_entity, text)
                else:
                    return []

                # Wait for bot to respond
                await asyncio.sleep(config.DELAY_BETWEEN_ACTIONS)
                responses = await self._collect_new_messages(last_id)

                # If no responses yet, wait longer and retry once
                if not responses:
                    await asyncio.sleep(config.MULTI_MESSAGE_WAIT)
                    responses = await self._collect_new_messages(last_id)
                elif len(responses) > 0:
                    # Got responses — wait briefly for potential follow-ups
                    await asyncio.sleep(0.5)
                    responses = await self._collect_new_messages(last_id)

                if responses:
                    responses.sort(key=lambda m: m.date)
                    return responses

                if attempt < config.MAX_RETRIES:
                    print(f"  No response, retry {attempt + 1}/{config.MAX_RETRIES}...")
                    await asyncio.sleep(2)

            except errors.FloodWaitError as e:
                wait_time = e.seconds + 5
                print(f"  FloodWait: sleeping {wait_time}s...")
                await asyncio.sleep(wait_time)

        self.stats["timeouts"] += 1
        return []

    async def reset_state(self) -> bool:
        """Try to reset bot to initial state for reply keyboard navigation."""
        for cmd in config.RESET_COMMANDS:
            responses = await self.send_and_wait(text=cmd)
            if responses:
                # Check if we got a reply keyboard back (sign of main menu)
                for msg in responses:
                    reply_btns = extract_reply_buttons(msg)
                    if reply_btns:
                        return True
        self.stats["reset_failures"] += 1
        return False

    async def crawl_node(self, trigger: dict, depth: int, parent_message=None) -> dict:
        """Crawl a single node and its children recursively.
        
        Args:
            trigger: How we got here (button text, type, callback_data)
            depth: Current depth in the tree
            parent_message: The message containing the button we clicked
        """
        # Send action based on trigger type
        if trigger["type"] == "command":
            responses = await self.send_and_wait(text=trigger["text"])
        elif trigger["type"] == "inline" and parent_message:
            cb_data = trigger.get("callback_data", "").encode("utf-8")
            responses = await self.send_and_wait(callback_data=cb_data, message=parent_message)
        elif trigger["type"] == "reply":
            responses = await self.send_and_wait(text=trigger["text"])
        else:
            responses = []

        if not responses:
            return {
                "trigger": trigger,
                "text": "",
                "media": None,
                "reply_keyboard": [],
                "inline_keyboard": [],
                "skipped": True,
                "skip_reason": "TIMEOUT",
                "children": [],
            }

        # Use the last message (usually the one with buttons)
        # but collect text from all messages
        all_text = "\n---\n".join(
            msg.text or msg.message or "" for msg in responses if msg.text or msg.message
        )
        primary_msg = responses[-1]  # Last message typically has buttons

        inline_btns = extract_inline_buttons(primary_msg)
        reply_btns_raw = extract_reply_buttons(primary_msg)
        reply_btn_texts = [b["text"] for b in reply_btns_raw]
        media = extract_media_info(primary_msg)

        # If primary has no buttons, check other messages
        if not inline_btns and not reply_btns_raw:
            for msg in responses:
                inline_btns = extract_inline_buttons(msg)
                reply_btns_raw = extract_reply_buttons(msg)
                reply_btn_texts = [b["text"] for b in reply_btns_raw]
                if inline_btns or reply_btns_raw:
                    primary_msg = msg
                    break

        # Count buttons
        self.stats["total_buttons"] += len(inline_btns) + len(reply_btns_raw)
        self.stats["total_screens"] += 1

        # Build node
        node = {
            "trigger": trigger,
            "text": all_text,
            "media": media,
            "reply_keyboard": [b for b in reply_btns_raw],
            "inline_keyboard": inline_btns,
            "skipped": False,
            "skip_reason": None,
            "children": [],
        }

        # Check deduplication
        btn_hash = hash_buttons(inline_btns, reply_btn_texts)
        if btn_hash in self.visited_hashes and (inline_btns or reply_btns_raw):
            node["skip_reason"] = "DUPLICATE"
            return node
        self.visited_hashes.add(btn_hash)

        # Check depth limit
        if depth >= config.MAX_DEPTH:
            node["skip_reason"] = "MAX_DEPTH"
            self.stats["max_depth_reached"] += 1
            return node

        # Crawl inline button children
        for btn in inline_btns:
            btn_text = btn["text"]

            # Skip URL buttons
            if btn.get("type") == "url":
                continue

            # Skip switch_inline buttons
            if btn.get("type") == "switch_inline":
                continue

            # Skip non-callback buttons
            if btn.get("type") != "callback":
                continue

            # Check nav patterns
            if is_nav(btn_text):
                self.stats["skipped_nav"] += 1
                continue

            # Check unsafe patterns
            if is_unsafe(btn_text):
                self.stats["skipped_unsafe"] += 1
                node["children"].append({
                    "trigger": {
                        "type": "inline",
                        "text": btn_text,
                        "callback_data": btn.get("callback_data", ""),
                    },
                    "text": "",
                    "media": None,
                    "reply_keyboard": [],
                    "inline_keyboard": [],
                    "skipped": True,
                    "skip_reason": f"UNSAFE: {btn_text}",
                    "children": [],
                })
                continue

            # Crawl this button
            child_trigger = {
                "type": "inline",
                "text": btn_text,
                "callback_data": btn.get("callback_data", ""),
            }
            print(f"{'  ' * depth}[inline] {btn_text} [{btn.get('callback_data', '')}]")
            child = await self.crawl_node(child_trigger, depth + 1, primary_msg)
            node["children"].append(child)

        # Crawl reply button children
        for btn in reply_btns_raw:
            btn_text = btn["text"]

            # Skip special button types
            if btn.get("type") in ("request_contact", "request_location"):
                self.stats["skipped_unsafe"] += 1
                node["children"].append({
                    "trigger": {"type": "reply", "text": btn_text},
                    "text": "",
                    "media": None,
                    "reply_keyboard": [],
                    "inline_keyboard": [],
                    "skipped": True,
                    "skip_reason": f"UNSAFE: {btn['type']}",
                    "children": [],
                })
                continue

            # Check nav patterns
            if is_nav(btn_text):
                self.stats["skipped_nav"] += 1
                continue

            # Check unsafe patterns
            if is_unsafe(btn_text):
                self.stats["skipped_unsafe"] += 1
                node["children"].append({
                    "trigger": {"type": "reply", "text": btn_text},
                    "text": "",
                    "media": None,
                    "reply_keyboard": [],
                    "inline_keyboard": [],
                    "skipped": True,
                    "skip_reason": f"UNSAFE: {btn_text}",
                    "children": [],
                })
                continue

            # Reset bot state before clicking reply button
            print(f"{'  ' * depth}[reply] {btn_text}")
            reset_ok = await self.reset_state()
            if not reset_ok:
                node["children"].append({
                    "trigger": {"type": "reply", "text": btn_text},
                    "text": "",
                    "media": None,
                    "reply_keyboard": [],
                    "inline_keyboard": [],
                    "skipped": True,
                    "skip_reason": "RESET_FAILED",
                    "children": [],
                })
                continue

            child_trigger = {"type": "reply", "text": btn_text}
            child = await self.crawl_node(child_trigger, depth + 1)
            node["children"].append(child)

        return node

    async def crawl(self) -> dict:
        """Main entry point. Returns the full tree."""
        print(f"Starting crawl of @{config.BOT_USERNAME}...")
        print(f"Max depth: {config.MAX_DEPTH}, delay: {config.DELAY_BETWEEN_ACTIONS}s")
        print()

        root = await self.crawl_node(
            trigger={"type": "command", "text": "/start"},
            depth=0,
        )

        result = {
            "bot": f"@{config.BOT_USERNAME}",
            "crawled_at": datetime.now().isoformat(),
            "stats": self.stats,
            "tree": root,
        }

        return result

    async def stop(self):
        """Disconnect the client."""
        await self.client.disconnect()
```

- [ ] **Step 3: Add the `main()` entry point**

Append to `crawler/crawler.py`:

```python
async def main():
    # Ensure output dir exists
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    crawler = BotCrawler()
    await crawler.start()

    try:
        result = await crawler.crawl()

        # Save JSON
        with open(config.OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nJSON saved: {config.OUTPUT_JSON}")

        # Save Markdown
        from exporter import generate_markdown
        md = generate_markdown(result)
        with open(config.OUTPUT_MD, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Markdown saved: {config.OUTPUT_MD}")

        # Print stats
        print(f"\n--- Stats ---")
        for k, v in result["stats"].items():
            print(f"  {k}: {v}")

    finally:
        await crawler.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Verify syntax**

Run: `python -m py_compile crawler/crawler.py`
Expected: No output (success)

- [ ] **Step 5: Commit**

```bash
git add crawler/crawler.py
git commit -m "feat: add core crawler logic with recursive traversal"
```

---

## Task 4: Markdown exporter

**Files:**
- Create: `crawler/exporter.py`

- [ ] **Step 1: Create `crawler/exporter.py`**

```python
"""Generate Markdown report from crawler JSON tree."""


def _breadcrumb(path: list[str]) -> str:
    """Build breadcrumb string like '/start -> Каталог -> POD-системи'."""
    return " → ".join(path)


def _format_trigger(trigger: dict) -> str:
    """Format trigger info for display."""
    t = trigger.get("type", "?")
    text = trigger.get("text", "")
    cb = trigger.get("callback_data", "")
    if cb:
        return f"`{text}` [{cb}]"
    return f"`{text}`"


def _walk_tree(node: dict, path: list[str], lines: list, unsafe_table: list, depth: int = 0):
    """Recursively walk the tree and build markdown lines."""
    trigger = node.get("trigger", {})
    trigger_text = trigger.get("text", "/start")
    current_path = path + [trigger_text]

    # Section header with breadcrumb
    level = min(depth + 2, 6)  # h2 to h6
    lines.append(f"{'#' * level} {_breadcrumb(current_path)}")
    lines.append("")

    # Skipped node
    if node.get("skipped"):
        reason = node.get("skip_reason", "unknown")
        lines.append(f"**⚠️ SKIPPED:** {reason}")
        lines.append("")

        if "UNSAFE" in (reason or ""):
            unsafe_table.append({
                "button": trigger_text,
                "callback_data": trigger.get("callback_data", ""),
                "reason": reason,
                "path": _breadcrumb(current_path),
            })
        return

    # Message text
    text = node.get("text", "")
    if text:
        for line in text.split("\n"):
            lines.append(f"> {line}")
        lines.append("")

    # Media
    media = node.get("media")
    if media:
        lines.append(f"📎 **Media:** {media['type']}" + (f" — {media['caption']}" if media.get('caption') else ""))
        lines.append("")

    # Reply keyboard
    reply_kb = node.get("reply_keyboard", [])
    if reply_kb:
        btn_texts = []
        for btn in reply_kb:
            if isinstance(btn, dict):
                t = btn.get("text", "")
                if btn.get("type") in ("request_contact", "request_location"):
                    t += f" ⚠️({btn['type']})"
                btn_texts.append(f"`{t}`")
            else:
                btn_texts.append(f"`{btn}`")
        lines.append(f"**Reply:** {' | '.join(btn_texts)}")
        lines.append("")

    # Inline keyboard
    inline_kb = node.get("inline_keyboard", [])
    if inline_kb:
        btn_texts = []
        for btn in inline_kb:
            text_part = btn.get("text", "")
            cb = btn.get("callback_data", "")
            url = btn.get("url", "")
            if url:
                btn_texts.append(f"`{text_part}` [URL: {url}]")
            elif cb:
                btn_texts.append(f"`{text_part}` [{cb}]")
            else:
                btn_texts.append(f"`{text_part}`")
        lines.append(f"**Inline:** {' | '.join(btn_texts)}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Recurse into children
    for child in node.get("children", []):
        _walk_tree(child, current_path, lines, unsafe_table, depth + 1)


def generate_markdown(data: dict) -> str:
    """Generate full Markdown report from crawler result."""
    stats = data.get("stats", {})
    lines = []

    # Header
    lines.append(f"# Реверс-інжинірінг {data.get('bot', '?')}")
    lines.append(f"> Зібрано: {data.get('crawled_at', '?')} | "
                 f"Екранів: {stats.get('total_screens', 0)} | "
                 f"Кнопок: {stats.get('total_buttons', 0)} | "
                 f"Пропущено (unsafe): {stats.get('skipped_unsafe', 0)}")
    lines.append("")

    # Stats table
    lines.append("## Статистика")
    lines.append("")
    lines.append("| Параметр | Значення |")
    lines.append("|---|---|")
    for k, v in stats.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    # Tree
    lines.append("## Дерево навігації")
    lines.append("")

    unsafe_table = []
    tree = data.get("tree", {})
    _walk_tree(tree, [], lines, unsafe_table)

    # Unsafe buttons summary
    if unsafe_table:
        lines.append("## ⚠️ Пропущені кнопки (unsafe)")
        lines.append("")
        lines.append("| Кнопка | Callback | Шлях | Причина |")
        lines.append("|--------|----------|------|---------|")
        for entry in unsafe_table:
            lines.append(
                f"| {entry['button']} | {entry['callback_data']} | "
                f"{entry['path']} | {entry['reason']} |"
            )
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 2: Verify syntax**

Run: `python -m py_compile crawler/exporter.py`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add crawler/exporter.py
git commit -m "feat: add JSON-to-Markdown exporter"
```

---

## Task 5: Integration test — dry run

**Purpose:** Verify the whole pipeline works before running against the real bot.

- [ ] **Step 1: User fills in `.env` with real credentials**

Copy `crawler/.env.example` to `crawler/.env` and fill in `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`.

- [ ] **Step 2: Run the crawler**

Run: `python crawler/crawler.py` (from project root DEV_P_13/)

First run will prompt for Telegram auth code interactively.

Expected:
- Console output showing crawled buttons as they're visited
- `output/bot_structure.json` created
- `output/bot_structure.md` created
- Stats printed at the end

- [ ] **Step 3: Validate JSON output**

Run: `python -c "import json; d=json.load(open('output/bot_structure.json', encoding='utf-8')); print(f'Screens: {d[\"stats\"][\"total_screens\"]}, Buttons: {d[\"stats\"][\"total_buttons\"]}')"` (from project root)

Expected: Valid JSON, reasonable counts (screens > 10, buttons > 20)

- [ ] **Step 4: Review Markdown output**

Open `output/bot_structure.md` and verify:
- Header with stats
- Tree with breadcrumbs
- Unsafe buttons table at the end

- [ ] **Step 5: Commit output (optional)**

```bash
git add output/bot_structure.json output/bot_structure.md
git commit -m "data: crawler results for @Vape_Rivne_Bot"
```

---

## Task 6: Post-crawl — manual walkthrough of unsafe buttons

**Not automated.** User manually:

1. Opens `output/bot_structure.md`
2. Finds the "Пропущені кнопки (unsafe)" table
3. Goes to `@Vape_Rivne_Bot` in Telegram
4. Clicks each unsafe button manually
5. Documents the results (screenshots, notes)
6. Adds findings to a separate file `output/manual_additions.md`
