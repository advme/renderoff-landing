#!/usr/bin/env python3
"""A small Markdown subset, enough for writing blog posts.

Deliberately not a full CommonMark implementation — it covers what a post
actually needs and nothing else:

    ## Heading            h2 through h4
    **bold**  *italic*  `code`
    [text](url)
    ![alt](src)          alone on a line becomes a figure with a caption
    - item / 1. item     lists
    > quote              blockquote
    ```lang ... ```      fenced code block
    ---                  horizontal rule

Everything is HTML-escaped before any markup is applied, so raw HTML in a post
is shown as text rather than injected into the page. That is the right default
for content coming through a web form.

This module is the single source of truth for rendering: tools/build.py uses it
to generate pages, and the admin server's /api/preview endpoint uses it to draw
the live preview, so the two can never disagree.
"""

import html
import re

__all__ = ["render", "summarise", "reading_time"]

_CODE_SPAN = re.compile(r"`([^`]+)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;)?\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\*\w])\*([^*\n]+)\*(?!\*)|(?<![_\w])_([^_\n]+)_(?!\w)")

_HEADING = re.compile(r"^(#{2,4})\s+(.*)$")
_ULI = re.compile(r"^[-*]\s+(.*)$")
_OLI = re.compile(r"^\d+[.)]\s+(.*)$")
_QUOTE = re.compile(r"^&gt;\s?(.*)$")
_HR = re.compile(r"^(?:-{3,}|\*{3,})$")
_FENCE = re.compile(r"^```\s*([A-Za-z0-9+#-]*)\s*$")
_IMAGE_ONLY = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;)?\)$")


def _inline(text):
    """Inline formatting. Input must already be HTML-escaped."""
    stash = []

    def keep(match):
        stash.append("<code>%s</code>" % match.group(1))
        return "\x00%d\x00" % (len(stash) - 1)

    # Code spans win over everything else inside them.
    text = _CODE_SPAN.sub(keep, text)

    text = _IMAGE.sub(
        lambda m: '<img src="%s" alt="%s" loading="lazy">' % (m.group(2), m.group(1)),
        text)
    text = _LINK.sub(_render_link, text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(
        lambda m: "<em>%s</em>" % (m.group(1) if m.group(1) is not None else m.group(2)),
        text)

    for i, code in enumerate(stash):
        text = text.replace("\x00%d\x00" % i, code)
    return text


def _render_link(match):
    label, href = match.group(1), match.group(2)
    # Only allow schemes that are safe to put in an href.
    lowered = href.lower()
    if ":" in lowered.split("/")[0] and not lowered.startswith(
            ("http:", "https:", "mailto:", "#", "/")):
        return html.escape(match.group(0))
    external = lowered.startswith(("http:", "https:"))
    extra = ' target="_blank" rel="noopener noreferrer"' if external else ""
    return '<a href="%s"%s>%s</a>' % (href, extra, label)


def _figure(alt, src, caption):
    caption = caption or alt
    out = '<figure class="post__figure"><img src="%s" alt="%s" loading="lazy">' % (src, alt)
    if caption:
        out += "<figcaption>%s</figcaption>" % _inline(caption)
    return out + "</figure>"


def render(source):
    """Markdown subset -> HTML string."""
    if not source:
        return ""

    text = html.escape(str(source).replace("\r\n", "\n").replace("\r", "\n"))
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        fence = _FENCE.match(stripped)
        if fence:
            lang = fence.group(1)
            i += 1
            body = []
            while i < n and not _FENCE.match(lines[i].strip()):
                body.append(lines[i])
                i += 1
            i += 1  # closing fence
            cls = ' class="language-%s"' % lang if lang else ""
            out.append("<pre><code%s>%s</code></pre>" % (cls, "\n".join(body)))
            continue

        if _HR.match(stripped):
            out.append("<hr>")
            i += 1
            continue

        heading = _HEADING.match(stripped)
        if heading:
            level = len(heading.group(1))
            out.append("<h%d>%s</h%d>" % (level, _inline(heading.group(2)), level))
            i += 1
            continue

        image_only = _IMAGE_ONLY.match(stripped)
        if image_only:
            out.append(_figure(image_only.group(1), image_only.group(2),
                               image_only.group(3)))
            i += 1
            continue

        if _QUOTE.match(stripped):
            body = []
            while i < n and _QUOTE.match(lines[i].strip()):
                body.append(_QUOTE.match(lines[i].strip()).group(1))
                i += 1
            out.append("<blockquote><p>%s</p></blockquote>"
                       % _inline(" ".join(body).strip()))
            continue

        if _ULI.match(stripped) or _OLI.match(stripped):
            ordered = bool(_OLI.match(stripped))
            pattern = _OLI if ordered else _ULI
            items = []
            while i < n and pattern.match(lines[i].strip()):
                items.append(_inline(pattern.match(lines[i].strip()).group(1)))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>"
                       % (tag, "".join("<li>%s</li>" % it for it in items), tag))
            continue

        # Paragraph: consume until a blank line or the start of another block.
        body = []
        while i < n and lines[i].strip():
            candidate = lines[i].strip()
            if body and (_HEADING.match(candidate) or _ULI.match(candidate)
                         or _OLI.match(candidate) or _QUOTE.match(candidate)
                         or _HR.match(candidate) or _FENCE.match(candidate)
                         or _IMAGE_ONLY.match(candidate)):
                break
            body.append(candidate)
            i += 1
        out.append("<p>%s</p>" % _inline("<br>".join(body) if len(body) > 1
                                         else body[0]))

    return "\n".join(out)


def summarise(source, limit=180):
    """First paragraph as plain text, for meta descriptions and cards."""
    if not source:
        return ""
    for block in str(source).replace("\r\n", "\n").split("\n\n"):
        block = block.strip()
        if not block or block.startswith(("#", ">", "!", "```", "---")):
            continue
        plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block)
        plain = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", plain)
        plain = re.sub(r"[*_`#]", "", plain).strip()
        plain = " ".join(plain.split())
        if not plain:
            continue
        if len(plain) <= limit:
            return plain
        return plain[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return ""


def reading_time(source):
    words = len(re.sub(r"[#*_`>\[\]()!-]", " ", str(source or "")).split())
    return max(1, round(words / 220))


if __name__ == "__main__":
    import sys
    print(render(sys.stdin.read()))
