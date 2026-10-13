"""central ui helpers.

everything the bot says goes through here so the look stays consistent:
- sc()   -> lowercase + small caps (commands, urls, @mentions, code stay normal)
- bar()  -> modern progress bar
- card() -> tree style message card (single line breaks only)
"""

import html
import re

_SMALL_CAPS = str.maketrans({
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ',
    'v': 'ᴠ', 'w': 'ᴡ', 'y': 'ʏ', 'z': 'ᴢ',
})

# parts of a text that must never be converted
_PROTECTED = re.compile(
    r'(`[^`]*`'                      # markdown inline code
    r'|&[a-zA-Z#0-9]+;'              # html entities
    r'|https?://\S+'                 # urls
    r'|@\w+'                         # @mentions
    r'|\{[^{}]*\}'                   # {placeholders}
    r'|(?<![\w/])/[A-Za-z0-9_]+)'    # /commands
)
_TAG = re.compile(r'(<[^>]+>)')
_CODE_OPEN = re.compile(r'^<(code|pre)(\s|>)', re.I)
_CODE_CLOSE = re.compile(r'^</(code|pre)>', re.I)


def _convert(chunk: str) -> str:
    out = []
    for part in _PROTECTED.split(chunk):
        if not part:
            continue
        if _PROTECTED.fullmatch(part):
            out.append(part)
        else:
            out.append(part.lower().translate(_SMALL_CAPS))
    return ''.join(out)


def sc(text) -> str:
    """lowercase + small caps. html tags, <code>/<pre> content, commands,
    urls, @mentions and {placeholders} are left untouched."""
    if text is None:
        return ''
    text = str(text)
    out = []
    depth = 0
    for part in _TAG.split(text):
        if not part:
            continue
        if part.startswith('<') and part.endswith('>') and _TAG.fullmatch(part):
            if _CODE_OPEN.match(part):
                depth += 1
            elif _CODE_CLOSE.match(part):
                depth = max(0, depth - 1)
            out.append(part)
        elif depth:
            out.append(part)
        else:
            out.append(_convert(part))
    return ''.join(out)


_MD_MARKS = re.compile(r'(\*\*|__|--|~~|\|\|)')


def esc(value) -> str:
    """escape a dynamic value (filename, error text...) so neither the html
    nor the markdown half of the default parse mode can mangle it."""
    s = html.escape(str(value), quote=False)
    s = s.replace('`', "'")
    return _MD_MARKS.sub(lambda m: m.group(0)[0] + '\u200b' + m.group(0)[1:], s)


def bar(percent, width: int = 12) -> str:
    """modern progress bar: ▰▰▰▰▱▱▱▱"""
    try:
        percent = float(percent)
    except (TypeError, ValueError):
        percent = 0.0
    percent = max(0.0, min(100.0, percent))
    filled = int(round(width * percent / 100))
    return '▰' * filled + '▱' * (width - filled)


def card(title, rows=None, percent=None, note=None, icon='', footer=None) -> str:
    """tree style card, single line breaks only.

    rows: list of (label, value) -> value rendered in <code>
          or (label, value, True) -> value inserted as raw html
    percent: shows a progress bar line under the title
    note: small italic line at the bottom
    footer: raw html line at the bottom (already formatted)
    """
    head = f"{icon} " if icon else ''
    lines = [f"<b>{head}{sc(title)}</b>"]

    if percent is not None:
        try:
            shown = f"{float(percent):.1f}".rstrip('0').rstrip('.')
        except (TypeError, ValueError):
            shown = '0'
        lines.append(f"{bar(percent)} <b>{shown}%</b>")

    rows = [r for r in (rows or []) if r]
    for i, row in enumerate(rows):
        glyph = '╰' if i == len(rows) - 1 else '├'
        label, value = row[0], row[1]
        raw = len(row) > 2 and row[2]
        value = value if raw else f"<code>{esc(value)}</code>"
        lines.append(f"{glyph} {sc(label)} › {value}")

    if note:
        lines.append(f"<i>{sc(note)}</i>")
    if footer:
        lines.append(footer)
    return '\n'.join(lines)


def title_only(text, icon='') -> str:
    """bold one liner status message"""
    head = f"{icon} " if icon else ''
    return f"<b>{head}{sc(text)}</b>"


def status(text, icon='') -> str:
    """bold headline + nothing else (alias kept for readability)"""
    return title_only(text, icon)


def tree(lines) -> str:
    """turn plain lines into a tree: ├ a / ├ b / ╰ c (text passed through sc)"""
    lines = [l for l in lines if l]
    out = []
    for i, line in enumerate(lines):
        glyph = '╰' if i == len(lines) - 1 else '├'
        out.append(f"{glyph} {sc(line)}")
    return '\n'.join(out)
