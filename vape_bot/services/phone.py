"""Нормалізація українських номерів телефонів до єдиного формату.

Єдиний формат: `+380XXXXXXXXX` (12 цифр після +, починається з 380).

Приймає:
- `+380631025583`
- `380631025583`
- `0631025583`
- `+38 063 102 55 83`
- `063 102 55 83`
- `(063) 102-55-83`

Повертає нормалізований рядок або `None` якщо номер не вдається розпізнати
як український мобільний.
"""


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None

    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return None

    if len(digits) == 12 and digits.startswith("380"):
        core = digits
    elif len(digits) == 11 and digits.startswith("80"):
        # рідкісний випадок — "80631025583" без першого "3"
        core = "3" + digits
    elif len(digits) == 10 and digits.startswith("0"):
        core = "38" + digits
    elif len(digits) == 9:
        # 631025583 — без префіксу "0"
        core = "380" + digits
    else:
        return None

    if len(core) != 12 or not core.startswith("380"):
        return None

    return "+" + core
