#!/usr/bin/env python3
"""Generate the per-app pages from content/apps.json.

    python3 tools/build.py            # write <app-id>.html for every app
    python3 tools/build.py --check    # report what would change, write nothing

Output is plain static HTML with no client-side rendering, because these pages
exist mainly to be indexed by search engines. The shared header and footer come
from templates/base.html so there is one copy of the site chrome, not one per
page.

Conventions the content file relies on:
  [[value]]   renders with the yellow placeholder highlight (.ph)
  {apple}     renders the Apple logo glyph from the icon sprite
"""

import argparse
import html
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content", "apps.json")
TEMPLATE = os.path.join(ROOT, "templates", "base.html")
ICON_DIR = os.path.join(ROOT, "assets", "icons")
CHANGELOG = os.path.join(ROOT, "changelog.json")
POSTS = os.path.join(ROOT, "content", "posts.json")
BLOG_DIR = os.path.join(ROOT, "blog")

SPRITE_ICONS = [("apple", "apple-logo.svg"),
                ("download", "download-arrow.svg"),
                ("bell", "bell.svg")]


# ----------------------------------------------------------------- helpers --

def esc(text):
    return html.escape(str(text if text is not None else ""), quote=True)


def rich(text):
    """Escape, then expand the [[placeholder]] and {apple} conventions."""
    out = esc(text)
    out = re.sub(r"\[\[(.+?)\]\]", r'<span class="ph">\1</span>', out)
    out = out.replace(
        "{apple}",
        '<svg class="apple" aria-hidden="true"><use href="#i-apple"/></svg>')
    return out


def plain(text):
    """Same conventions, stripped — for <title> and meta tags."""
    out = re.sub(r"\[\[(.+?)\]\]", r"\1", str(text or ""))
    return esc(out.replace("{apple}", "").replace("  ", " ").strip())


def build_sprite():
    symbols = []
    for name, filename in SPRITE_ICONS:
        path = os.path.join(ICON_DIR, filename)
        with open(path, "r", encoding="utf-8") as fh:
            svg = fh.read()
        viewbox = re.search(r'viewBox="([^"]+)"', svg).group(1)
        body = re.search(r">(<path.*?)</svg>", svg, re.S).group(1)
        symbols.append(
            '<symbol id="i-%s" viewBox="%s">%s</symbol>' % (name, viewbox, body))
    return "\n".join(symbols)


# ------------------------------------------------------------- page pieces --

def render_hero(app):
    actions = app.get("actions", {})
    parts = ['<section class="app-hero">']
    parts.append(
        '<img class="app-hero__icon" src="%s" alt="" width="96" height="96">'
        % esc(app["icon"]))
    parts.append('<div class="app-hero__text">')
    parts.append('<h1 class="app-hero__name">%s</h1>' % rich(app["name"]))
    parts.append('<p class="app-hero__tagline">%s</p>' % rich(app["tagline"]))
    parts.append("</div>")
    parts.append("</section>")

    if app.get("summary"):
        parts.append('<p class="app-summary">%s</p>' % rich(app["summary"]))

    parts.append('<div class="app-actions">')
    if actions.get("buy_url"):
        parts.append(
            '<a class="btn btn--download" href="%s">'
            '<svg class="btn__icon" aria-hidden="true"><use href="#i-download"/></svg>'
            '<span>%s</span></a>'
            % (plain(actions["buy_url"]), rich(actions.get("buy_label", "Buy"))))
    if actions.get("trial_url"):
        parts.append('<a class="btn btn--quiet" href="%s"><span>%s</span></a>'
                     % (plain(actions["trial_url"]),
                        rich(actions.get("trial_label", "Download trial"))))
    parts.append("</div>")

    if actions.get("trial_note"):
        parts.append('<p class="app-actions__note">%s</p>'
                     % rich(actions["trial_note"]))

    reqs = app.get("requirements") or []
    if reqs:
        rows = "".join("<dt>%s</dt><dd>%s</dd>" % (rich(k), rich(v))
                       for k, v in reqs)
        parts.append('<dl class="app-req">%s</dl>' % rows)

    return "\n".join(parts)


def render_screenshots(app):
    shots = app.get("screenshots") or []
    if not shots:
        return ""

    parts = ['<section class="app-shots" aria-label="Screenshots">']
    for i, shot in enumerate(shots, 1):
        # "compact" frames a small utility window at its natural size on a
        # backdrop, instead of upscaling it to the full column width.
        compact = shot.get("display") == "compact"
        klass = "shot shot--compact" if compact else "shot"
        display_w = shot.get("display_width") or shot.get("width")

        parts.append('<figure class="%s">' % klass)
        if compact:
            parts.append('<div class="shot__stage">')

        if shot.get("src"):
            style = ' style="max-width:%spx"' % esc(display_w) if compact else ""
            parts.append(
                '<img src="%s" alt="%s" width="%s" height="%s" loading="lazy"%s>'
                % (esc(shot["src"]), esc(shot.get("alt", "")),
                   esc(shot.get("width", "")), esc(shot.get("height", "")), style))
        else:
            style = "aspect-ratio:%s/%s" % (esc(shot.get("width", 16)),
                                            esc(shot.get("height", 10)))
            if compact:
                style += ";max-width:%spx;width:100%%" % esc(display_w)
            parts.append(
                '<div class="shot__placeholder" style="%s">'
                '<span class="shot__label">Screenshot %d</span>'
                '<span class="shot__hint">Save your %s&times;%s image as '
                '<code>%s</code></span></div>'
                % (style, i, esc(shot.get("width", "")), esc(shot.get("height", "")),
                   esc(shot.get("expected_path", "assets/img/shots/…"))))

        if compact:
            parts.append('</div>')
        if shot.get("caption"):
            parts.append('<figcaption>%s</figcaption>' % rich(shot["caption"]))
        parts.append("</figure>")
    parts.append("</section>")
    return "\n".join(parts)


def render_features(app):
    features = app.get("features") or []
    if not features:
        return ""
    items = []
    for f in features:
        items.append(
            '<div class="feature"><h2 class="feature__title">%s</h2>'
            '<p class="feature__text">%s</p></div>'
            % (rich(f.get("title", "")), rich(f.get("text", ""))))
    return ('<section class="app-features">%s</section>' % "".join(items))


def render_pricing(app):
    pricing = app.get("pricing")
    if not pricing:
        return ""
    parts = ['<section class="app-pricing" id="pricing">']
    parts.append('<div class="app-pricing__head">')
    parts.append('<span class="app-pricing__price">%s</span>' % rich(pricing.get("price", "")))
    parts.append('<span class="app-pricing__unit">%s</span>' % rich(pricing.get("unit", "")))
    parts.append("</div>")

    includes = pricing.get("includes") or []
    if includes:
        parts.append('<ul class="app-pricing__list">%s</ul>'
                     % "".join("<li>%s</li>" % rich(i) for i in includes))
    if pricing.get("note"):
        parts.append('<p class="app-pricing__note">%s</p>' % rich(pricing["note"]))

    actions = app.get("actions", {})
    if actions.get("buy_url"):
        parts.append(
            '<a class="btn btn--download" href="%s">'
            '<svg class="btn__icon" aria-hidden="true"><use href="#i-download"/></svg>'
            '<span>%s</span></a>'
            % (plain(actions["buy_url"]), rich(actions.get("buy_label", "Buy"))))
    parts.append("</section>")
    return "\n".join(parts)


def render_faq(app):
    faq = app.get("faq") or []
    if not faq:
        return ""
    items = []
    for item in faq:
        items.append(
            '<details class="faq"><summary>%s</summary><p>%s</p></details>'
            % (rich(item.get("q", "")), rich(item.get("a", ""))))
    return ('<section class="app-faq"><h2 class="app-section-title">Questions</h2>%s</section>'
            % "".join(items))


def render_footer_links(app):
    email = app.get("support_email")
    parts = ['<section class="app-tail">']
    parts.append(
        '<p><a href="changelog.html?app=%s">See what changed in each update &rarr;</a></p>'
        % esc(app["id"]))
    if email:
        clean = plain(email)
        parts.append('<p>Something not working? Write to %s and a person will reply.</p>'
                     % ('<a href="mailto:%s">%s</a>' % (clean, rich(email))))
    parts.append("</section>")
    return "\n".join(parts)


def render_structured_data(app):
    """SoftwareApplication markup, so search results can show price directly."""
    pricing = app.get("pricing") or {}
    price = re.sub(r"[^\d.]", "", plain(pricing.get("price", ""))) or "0"
    payload = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": plain(app["name"]),
        "applicationCategory": "UtilitiesApplication",
        "operatingSystem": "macOS",
        "description": plain(app.get("seo", {}).get("description", "")),
        "offers": {
            "@type": "Offer",
            "price": price,
            "priceCurrency": "EUR",
        },
    }
    return ('<script type="application/ld+json">%s</script>'
            % json.dumps(payload, ensure_ascii=False))


def render_draft_banner(app):
    if not app.get("draft"):
        return ""
    note = app.get("draft_note") or (
        "The copy and screenshots here are drafts — replace them in "
        "<code>content/apps.json</code>.")
    return (
        '<div class="legal__notice" role="note"><p><strong>Not ready yet.</strong> '
        '%s Highlighted values still need confirming. Set '
        '<code>"draft": false</code> to hide this box.</p></div>' % note)


def render_app(app, template, sprite):
    seo = app.get("seo", {})
    title = plain(seo.get("title") or ("%s — RENDEROFF" % app["name"]))
    description = plain(seo.get("description") or app.get("summary", ""))

    body = "\n".join(filter(None, [
        '<div class="shell app-page">',
        render_draft_banner(app),
        '<p class="legal__eyebrow"><a href="index.html">&larr; All apps</a></p>',
        render_hero(app),
        render_screenshots(app),
        render_features(app),
        render_pricing(app),
        render_faq(app),
        render_footer_links(app),
        "</div>",
    ]))

    return assemble(template, sprite, title=title, description=description,
                    og_title=plain(app["name"]), body=body,
                    structured_data=render_structured_data(app))


def assemble(template, sprite, title, description, og_title, body,
             structured_data="", base=""):
    page = template
    for key, value in [
        ("{{title}}", title),
        ("{{description}}", description),
        ("{{og_title}}", og_title),
        ("{{structured_data}}", structured_data),
        ("{{sprite}}", sprite),
        ("{{body}}", body),
        ("{{base}}", base),
    ]:
        page = page.replace(key, value)
    return page


# -------------------------------------------------------------------- blog --

def format_date(iso):
    from datetime import datetime
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%-d %B %Y")
    except (ValueError, TypeError):
        return iso or ""


def published(posts):
    """Drafts stay out of the built site entirely."""
    live = [p for p in posts if not p.get("draft")]
    return sorted(live, key=lambda p: (p.get("date", ""), p.get("id", "")),
                  reverse=True)


def post_meta(post):
    bits = ['<time datetime="%s">%s</time>'
            % (esc(post.get("date", "")), esc(format_date(post.get("date"))))]
    minutes = markdown.reading_time(post.get("body", ""))
    bits.append("%d min read" % minutes)
    return '<p class="post__meta">%s</p>' % " &middot; ".join(bits)


def render_post_page(post, template, sprite):
    summary = post.get("summary") or markdown.summarise(post.get("body", ""))
    body_html = markdown.render(post.get("body", ""))

    parts = ['<article class="shell post">']
    parts.append('<p class="legal__eyebrow"><a href="../blog.html">&larr; All posts</a></p>')
    parts.append('<h1 class="post__title">%s</h1>' % esc(post.get("title", "")))
    parts.append(post_meta(post))
    # Only an explicitly written summary becomes a lede. An auto-derived one
    # is just the first paragraph, so showing it would print it twice.
    if post.get("summary"):
        parts.append('<p class="post__lede">%s</p>' % esc(post["summary"]))
    if post.get("cover"):
        parts.append('<figure class="post__cover"><img src="../%s" alt="" loading="lazy"></figure>'
                     % esc(post["cover"]))
    parts.append('<div class="post__body">%s</div>' % body_html)
    parts.append('<p class="post__back"><a href="../blog.html">&larr; All posts</a></p>')
    parts.append("</article>")

    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.get("title", ""),
        "datePublished": post.get("date", ""),
        "description": summary,
        "author": {"@type": "Organization", "name": "RENDEROFF"},
    }
    structured = ('<script type="application/ld+json">%s</script>'
                  % json.dumps(ld, ensure_ascii=False))

    return assemble(template, sprite,
                    title="%s — RENDEROFF" % esc(post.get("title", "")),
                    description=esc(summary),
                    og_title=esc(post.get("title", "")),
                    body="\n".join(parts),
                    structured_data=structured,
                    base="../")


def render_blog_index(posts, template, sprite):
    parts = ['<div class="shell blog-index">']
    parts.append('<p class="legal__eyebrow"><a href="index.html">&larr; Back to RENDEROFF</a></p>')
    parts.append('<h1 class="legal__title">Blog</h1>')
    parts.append('<p class="changelog__lede">Notes on building Mac apps, and on the apps themselves.</p>')

    if not posts:
        parts.append('<p class="changelog__empty">Nothing published yet.</p>')
    else:
        parts.append('<ul class="post-list">')
        for post in posts:
            summary = post.get("summary") or markdown.summarise(post.get("body", ""))
            href = "blog/%s.html" % esc(post["id"])
            parts.append('<li class="post-card">')
            if post.get("cover"):
                parts.append('<a class="post-card__thumb" href="%s" tabindex="-1" aria-hidden="true">'
                             '<img src="%s" alt="" loading="lazy"></a>'
                             % (href, esc(post["cover"])))
            parts.append('<div class="post-card__text">')
            parts.append('<h2 class="post-card__title"><a href="%s">%s</a></h2>'
                         % (href, esc(post.get("title", ""))))
            parts.append(post_meta(post))
            if summary:
                parts.append('<p class="post-card__summary">%s</p>' % esc(summary))
            parts.append("</div></li>")
        parts.append("</ul>")
    parts.append("</div>")

    return assemble(template, sprite,
                    title="Blog — RENDEROFF",
                    description="Notes on building Mac apps, and on the apps themselves.",
                    og_title="RENDEROFF Blog",
                    body="\n".join(parts))


def build_blog(template, sprite, check=False):
    try:
        with open(POSTS, "r", encoding="utf-8") as fh:
            raw = json.load(fh).get("posts", [])
    except FileNotFoundError:
        return 0
    except json.JSONDecodeError as exc:
        print("  ! content/posts.json is not valid JSON: %s" % exc)
        return 0

    posts = published(raw)
    drafts = len(raw) - len(posts)
    changed = 0
    targets = {}

    targets[os.path.join(ROOT, "blog.html")] = render_blog_index(posts, template, sprite)
    for post in posts:
        targets[os.path.join(BLOG_DIR, "%s.html" % post["id"])] = \
            render_post_page(post, template, sprite)

    if not check:
        os.makedirs(BLOG_DIR, exist_ok=True)

    for path, page in targets.items():
        rel = os.path.relpath(path, ROOT)
        existing = None
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                existing = fh.read()
        if existing == page:
            print("  = %s (unchanged)" % rel)
            continue
        changed += 1
        if check:
            print("  ~ %s would change" % rel)
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(page)
        print("  %s %s" % ("+" if existing is None else "~", rel))

    # Remove pages for posts that were deleted or turned back into drafts.
    if os.path.isdir(BLOG_DIR):
        keep = {"%s.html" % p["id"] for p in posts}
        for name in os.listdir(BLOG_DIR):
            if name.endswith(".html") and name not in keep:
                stale = os.path.join(BLOG_DIR, name)
                if check:
                    print("  ~ blog/%s would be removed" % name)
                else:
                    os.unlink(stale)
                    print("  - blog/%s (unpublished)" % name)
                changed += 1

    if drafts:
        print("  %d draft post(s) held back." % drafts)
    return changed


# ------------------------------------------------------------------- main ---

def check_against_changelog(apps):
    """Warn if the two app lists have drifted apart."""
    try:
        with open(CHANGELOG, "r", encoding="utf-8") as fh:
            known = {a["id"] for a in json.load(fh).get("apps", [])}
    except (OSError, json.JSONDecodeError, KeyError):
        return
    for app in apps:
        if app["id"] not in known:
            print("  ! '%s' has a page but is not in changelog.json — "
                  "add it in admin.html so updates can be posted." % app["id"])


def main_build(check=False):
    """Do the work. Importable, so the admin server can rebuild after a save."""
    with open(CONTENT, "r", encoding="utf-8") as fh:
        apps = json.load(fh).get("apps", [])
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        template = fh.read()

    sprite = build_sprite()
    changed = 0

    for app in apps:
        out_path = os.path.join(ROOT, "%s.html" % app["id"])
        page = render_app(app, template, sprite)

        existing = None
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as fh:
                existing = fh.read()

        label = os.path.basename(out_path)
        if existing == page:
            print("  = %s (unchanged)" % label)
            continue

        changed += 1
        if check:
            print("  ~ %s would change" % label)
            continue

        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(page)
        print("  %s %s%s" % ("+" if existing is None else "~", label,
                             "  [draft]" if app.get("draft") else ""))

    changed += build_blog(template, sprite, check=check)
    check_against_changelog(apps)
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="report changes without writing")
    args = parser.parse_args()

    changed = main_build(check=args.check)

    if args.check:
        print("\n%d page(s) would change." % changed)
        return 1 if changed else 0

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
