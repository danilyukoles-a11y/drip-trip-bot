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

    async def send_and_wait(self, text: str = None, click_msg=None, click_text: str = None) -> list:
        """Send a message or click an inline button, wait for bot response(s).

        Uses min_id tracking to only read NEW messages after our action.
        For inline buttons: pass click_msg (the message object) and click_text (button text).
        For text/commands: pass text.
        Returns a list of messages from the bot, sorted oldest-first.
        """
        for attempt in range(config.MAX_RETRIES + 1):
            try:
                # Remember last message ID BEFORE sending
                last_id = await self._get_last_msg_id()

                if click_msg and click_text:
                    # Click inline button by its text on the message
                    await click_msg.click(text=click_text)
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
            except Exception as e:
                print(f"  Error: {type(e).__name__}: {e}")
                if attempt < config.MAX_RETRIES:
                    await asyncio.sleep(2)
                else:
                    break

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
            responses = await self.send_and_wait(click_msg=parent_message, click_text=trigger["text"])
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
                    "skip_reason": f"NAV: {btn_text}",
                    "children": [],
                })
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
                node["children"].append({
                    "trigger": {"type": "reply", "text": btn_text},
                    "text": "",
                    "media": None,
                    "reply_keyboard": [],
                    "inline_keyboard": [],
                    "skipped": True,
                    "skip_reason": f"NAV: {btn_text}",
                    "children": [],
                })
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
