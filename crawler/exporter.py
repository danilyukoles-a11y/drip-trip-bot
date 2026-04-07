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
