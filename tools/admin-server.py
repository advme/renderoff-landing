#!/usr/bin/env python3
"""Local dev server for the RENDEROFF site, with changelog saving.

Serves the site exactly like `python3 -m http.server`, and adds a few endpoints
that admin.html uses:

    GET  /api/changelog   current changelog.json
    PUT  /api/changelog   write changelog.json
    GET  /api/posts       current content/posts.json
    PUT  /api/posts       write posts.json, then rebuild the static blog pages
    POST /api/preview     Markdown in, rendered HTML out (for the live preview)
    POST /api/upload      save one image into assets/img/blog/

This exists only so admin.html can save your edits straight to disk. It binds
to 127.0.0.1, so it is not reachable from other machines on your network.

    python3 tools/admin-server.py            # http://127.0.0.1:4321
    python3 tools/admin-server.py --port 8080

Do NOT deploy this file, or admin.html, to your public site. The endpoint has
no authentication because it is only ever meant to listen on localhost.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import markdown as md
import build as builder

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(ROOT, "changelog.json")
POSTS_FILE = os.path.join(ROOT, "content", "posts.json")
UPLOAD_DIR = os.path.join(ROOT, "assets", "img", "blog")
BACKUP_DIR = os.path.join(ROOT, ".changelog-backups")
MAX_BODY = 2 * 1024 * 1024   # 2 MB is far more changelog than anyone needs
MAX_UPLOAD = 12 * 1024 * 1024  # 12 MB per image

# Only formats a browser will actually render inline.
IMAGE_TYPES = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
    "image/webp": ".webp", "image/svg+xml": ".svg",
}


class AdminHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # -- helpers ----------------------------------------------------------

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, code, message):
        body = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # The admin page must never be served from a stale cache.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # -- routing ----------------------------------------------------------

    def _read_body(self, limit=MAX_BODY):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._text(400, "Bad Content-Length")
            return None
        if length <= 0:
            self._text(400, "Empty request body")
            return None
        if length > limit:
            self._text(413, "Payload too large")
            return None
        return self.rfile.read(length)

    def do_POST(self):
        route = self.path.split("?")[0]
        if route == "/api/preview":
            raw = self._read_body()
            if raw is None:
                return
            self._json(200, {"html": md.render(raw.decode("utf-8", "replace"))})
            return
        if route == "/api/upload":
            self._handle_upload()
            return
        self._text(404, "Not found")

    def _handle_upload(self):
        """Save one image posted as a raw body, named by X-Filename."""
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if content_type not in IMAGE_TYPES:
            self._text(415, "Unsupported image type: %s. Use PNG, JPEG, GIF, WebP or SVG."
                       % (content_type or "none"))
            return

        raw = self._read_body(MAX_UPLOAD)
        if raw is None:
            return

        name = safe_filename(self.headers.get("X-Filename") or "image",
                             IMAGE_TYPES[content_type])
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        target = os.path.join(UPLOAD_DIR, name)
        stem, ext = os.path.splitext(name)
        counter = 2
        while os.path.exists(target):
            name = "%s-%d%s" % (stem, counter, ext)
            target = os.path.join(UPLOAD_DIR, name)
            counter += 1

        try:
            with open(target, "wb") as fh:
                fh.write(raw)
        except OSError as exc:
            self._text(500, "Could not save image: %s" % exc)
            return

        rel = "assets/img/blog/%s" % name
        self.log_message("uploaded %s (%d KB)", rel, len(raw) // 1024)
        self._json(200, {"ok": True, "path": rel, "bytes": len(raw)})

    def do_PUT(self):
        route = self.path.split("?")[0]
        if route == "/api/posts":
            self._save_posts()
            return
        if route != "/api/changelog":
            self._text(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._text(400, "Bad Content-Length")
            return

        if length <= 0:
            self._text(400, "Empty request body")
            return
        if length > MAX_BODY:
            self._text(413, "Payload too large")
            return

        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._text(400, "Body is not valid JSON: %s" % exc)
            return

        problem = validate(payload)
        if problem:
            self._text(422, problem)
            return

        try:
            backup = write_atomic(payload)
        except OSError as exc:
            self._text(500, "Could not write changelog.json: %s" % exc)
            return

        entries = len(payload.get("entries", []))
        self.log_message("saved changelog.json (%d entries, backup: %s)", entries, backup)
        self._json(200, {"ok": True, "entries": entries, "backup": backup})

    def _save_posts(self):
        raw = self._read_body()
        if raw is None:
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._text(400, "Body is not valid JSON: %s" % exc)
            return

        problem = validate_posts(payload)
        if problem:
            self._text(422, problem)
            return

        try:
            backup = write_atomic(payload, POSTS_FILE, stem="posts")
        except OSError as exc:
            self._text(500, "Could not write posts.json: %s" % exc)
            return

        # Blog pages are static, so a save is only real once the site rebuilds.
        built, build_error = run_build()
        posts = len(payload.get("posts", []))
        self.log_message("saved posts.json (%d posts, backup: %s)", posts, backup)
        self._json(200, {"ok": True, "posts": posts, "backup": backup,
                         "rebuilt": built, "buildError": build_error})

    def do_GET(self):
        if self.path.split("?")[0] == "/api/posts":
            try:
                with open(POSTS_FILE, "r", encoding="utf-8") as fh:
                    self._json(200, json.load(fh))
            except FileNotFoundError:
                self._json(200, {"posts": []})
            except (OSError, json.JSONDecodeError) as exc:
                self._text(500, "Could not read posts.json: %s" % exc)
            return
        if self.path.split("?")[0] == "/api/changelog":
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as fh:
                    self._json(200, json.load(fh))
            except FileNotFoundError:
                self._json(200, {"apps": [], "entries": []})
            except (OSError, json.JSONDecodeError) as exc:
                self._text(500, "Could not read changelog.json: %s" % exc)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


def validate(payload):
    """Return an error string, or None when the payload is usable."""
    if not isinstance(payload, dict):
        return "Top level must be an object."

    apps = payload.get("apps")
    entries = payload.get("entries")
    if not isinstance(apps, list) or not isinstance(entries, list):
        return "Expected 'apps' and 'entries' to both be arrays."

    app_ids = set()
    for i, app in enumerate(apps):
        if not isinstance(app, dict):
            return "apps[%d] is not an object." % i
        app_id = app.get("id")
        if not isinstance(app_id, str) or not app_id:
            return "apps[%d] needs a non-empty string id." % i
        if app_id in app_ids:
            return "Duplicate app id: %s" % app_id
        app_ids.add(app_id)
        if not isinstance(app.get("name"), str) or not app["name"]:
            return "apps[%d] needs a non-empty name." % i

    seen = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return "entries[%d] is not an object." % i
        for key in ("id", "app", "date"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                return "entries[%d] needs a non-empty '%s'." % (i, key)
        if entry["id"] in seen:
            return "Duplicate entry id: %s" % entry["id"]
        seen.add(entry["id"])
        if entry["app"] not in app_ids:
            return "entries[%d] refers to unknown app '%s'." % (i, entry["app"])
        try:
            datetime.strptime(entry["date"], "%Y-%m-%d")
        except ValueError:
            return "entries[%d] has date '%s'; expected YYYY-MM-DD." % (i, entry["date"])
        if not isinstance(entry.get("notes"), list) or not entry["notes"]:
            return "entries[%d] needs at least one note." % i
        for j, note in enumerate(entry["notes"]):
            if not isinstance(note, dict) or not isinstance(note.get("text"), str):
                return "entries[%d].notes[%d] needs a text string." % (i, j)

    return None


def write_atomic(payload, target=None, stem="changelog"):
    """Back up the current file, then replace it in one atomic rename."""
    target = target or DATA_FILE
    backup_name = ""
    if os.path.exists(target):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_name = "%s-%s.json" % (stem, datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(target, os.path.join(BACKUP_DIR, backup_name))
        prune_backups()

    fd, tmp = tempfile.mkstemp(dir=ROOT, prefix=".changelog-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    return backup_name


def safe_filename(raw, ext):
    """Strip any path information; keep a readable slug plus the real extension."""
    base = os.path.basename(str(raw)).rsplit(".", 1)[0]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()[:60]
    return (slug or "image") + ext


def validate_posts(payload):
    if not isinstance(payload, dict):
        return "Top level must be an object."
    posts = payload.get("posts")
    if not isinstance(posts, list):
        return "Expected 'posts' to be an array."

    seen = set()
    for i, post in enumerate(posts):
        if not isinstance(post, dict):
            return "posts[%d] is not an object." % i
        for key in ("id", "title", "date"):
            if not isinstance(post.get(key), str) or not post[key].strip():
                return "posts[%d] needs a non-empty '%s'." % (i, key)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", post["id"]):
            return ("posts[%d] has id '%s'; use lowercase letters, numbers and "
                    "hyphens only." % (i, post["id"]))
        if post["id"] in seen:
            return "Duplicate post id: %s" % post["id"]
        seen.add(post["id"])
        try:
            datetime.strptime(post["date"], "%Y-%m-%d")
        except ValueError:
            return "posts[%d] has date '%s'; expected YYYY-MM-DD." % (i, post["date"])
        if not isinstance(post.get("body"), str) or not post["body"].strip():
            return "posts[%d] has an empty body." % i
    return None


def run_build():
    """Regenerate the static pages. Returns (ok, error message or '')."""
    import io
    import contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            builder.main_build()
    except Exception as exc:  # a broken build must not lose the saved file
        return False, str(exc)
    return True, ""


def prune_backups(keep=40):
    try:
        files = sorted(
            f for f in os.listdir(BACKUP_DIR)
            if f.endswith(".json")
        )
    except OSError:
        return
    for stale in files[:-keep]:
        try:
            os.unlink(os.path.join(BACKUP_DIR, stale))
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=4321, help="default: 4321")
    parser.add_argument("--host", default="127.0.0.1",
                        help="default: 127.0.0.1 (localhost only)")
    args = parser.parse_args()

    handler = partial(AdminHandler, directory=ROOT)
    server = ThreadingHTTPServer((args.host, args.port), handler)

    print("RENDEROFF admin server")
    print("  site   http://%s:%d/" % (args.host, args.port))
    print("  admin  http://%s:%d/admin.html" % (args.host, args.port))
    print("  saving to %s" % DATA_FILE)
    print("  Ctrl-C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
