# RENDEROFF — landing page

Static landing page built from the Figma source
[`RENDEROFF Apps`, node `6:711`](https://www.figma.com/design/sqMMWGElCV6USYtTiWaeWG/RENDEROFF-Apps?node-id=6-711).

## Run it

```bash
python3 tools/admin-server.py
```

Then open <http://127.0.0.1:4321>. There is no build step — plain HTML, CSS and
a little vanilla JS.

`python3 -m http.server 4321` also works if you only want to look at the site;
you just will not be able to save from the admin page.

The changelog is loaded with `fetch`, so the site has to be served over HTTP.
Opening `changelog.html` straight from Finder will show an error telling you the
same thing.

## Layout

```
index.html      landing page; markup + inlined SVG icon sprite
orange-timer.html    GENERATED app page — edit content/apps.json, not this
blog.html       GENERATED blog index
blog/*.html     GENERATED posts — edit content/posts.json via admin.html
changelog.html  public changelog, rendered from changelog.json
terms.html      Terms & Conditions (draft — see below)
admin.html      local changelog editor — never deploy this
changelog.json  the changelog data
styles.css      all styling; Figma values noted in comments
assets/css/     admin-only styling
assets/js/      changelog rendering + admin logic
assets/img/     app icons, sized for display (@2x of their 64px slot)
assets/img/source/   original full-resolution exports from Figma
assets/icons/   SVG assets exported from Figma
content/apps.json    app page content
content/posts.json   blog posts (Markdown bodies)
templates/      shared page shell used by the generator
tools/          build script, Markdown renderer, local admin server — never deploy
assets/img/blog/     images uploaded through the blog editor (these DO deploy)
```

## Fidelity notes

Measured against the Figma frame at a 1512px viewport, the rendered page matches
on every structural value: 712px content column, section offsets (187 / 475 /
564 / 653 / 742 / 912), a 993px document height, 64px app icons, and 129x32
buttons.

A few details worth knowing:

- **Fonts.** Figma uses SF Pro for copy and SF Compact Display for app names and
  button labels. macOS chooses between the Text and Display optical variants
  automatically, and its choice at 17px did not match Figma's, which changed
  where paragraphs wrapped. `styles.css` names the variants explicitly
  (`--font-text` / `--font-display` / `--font-compact`) so the line breaks match
  the design. Non-Apple platforms fall back to Inter, loaded from Google Fonts.
- **Line wrapping.** `text-wrap: pretty` re-balanced the headline away from
  Figma's greedy wrap, so the headline is set to `text-wrap: wrap`.
- **Button edges.** The buttons carry a vertical gradient hairline
  (`#3D94EC → #013E7D` blue, `#A6A6A6 → #2F2F2F` grey), taken from the Figma
  stroke rather than the flat border colour the code export reports. It is drawn
  with a padding-box/border-box background pair.
- **Borders and box size.** Figma draws strokes inside the box and CSS draws them
  outside, so button and footer padding is reduced by the border width to keep
  the boxes at exactly 32px and 81px.
- **SF Symbols.** `apple.logo`, `arrow.down.circle.dotted`, and `bell` are font
  glyphs in Figma, not exportable layers. They were exported as SVG and the glyph
  outlines extracted, so they are the real vectors, not redrawn approximations.
- **Image weight.** The Figma exports were 1024px PNGs totalling ~3.6MB for slots
  64px wide. They are resized to @2x (92KB total); originals are in
  `assets/img/source/`.

## Placeholders

The Figma has no link targets, so these need real destinations (marked `TODO` in
`index.html`):

- `write me` — currently `mailto:hello@renderoff.com`, an invented address
- `about` — anchors to the intro section
- `blog`, `changelog`, `t&c` — `#`
- both `Download` buttons and both `Notify Me` buttons — `#`


## Terms & Conditions (`terms.html`)

Not designed in Figma — built to match the landing page's system (same 712px
column, header, footer and type scale). Body copy is set at 17px/26px rather
than the landing page's 17px/20px, because the tighter leading is right for a
few short paragraphs and punishing across a long document.

### Read this before publishing

**This is a draft, and I am not a lawyer.** It follows the conventional shape
for a small EU-based Mac/iOS app business, but it has not been reviewed by
anyone qualified and it makes assumptions about your business that may be wrong.
Have an Estonian lawyer read it.

Three things need doing:

1. **Fill in every highlighted field.** Placeholders are wrapped in
   `<span class="ph">` and render with a yellow highlight so none can be missed:
   legal entity name, registry code, address, VAT number, contact addresses,
   payment provider, refund window, and the liability cap.
2. **Write a Privacy Policy.** Section 13 references one and treats it as part
   of the terms, but it does not exist yet. Under GDPR you need it.
3. **Remove the draft banner** — the `.legal__notice` block in `terms.html` and
   its rule in `styles.css`.

### Assumptions baked into the wording

Change these if they do not match reality: that you trade as an Estonian OÜ;
that you sell both through the App Store and directly; that you offer free
trials; and that you are willing to give goodwill refunds on direct purchases.

### Points that were handled deliberately

- **The 14-day withdrawal right.** EU consumers get 14 days to withdraw, but
  digital content is exempt once download begins with the customer's express
  consent and acknowledgement (Art. 16(m), Directive 2011/83/EU). Section 8
  relies on that exemption, which only holds if you actually collect that
  consent at checkout. Make sure your checkout does.
- **Reverse engineering.** A blanket ban is unenforceable in the EU, so the
  restriction is carved back for decompilation permitted under Art. 6 of
  Directive 2009/24/EC.
- **Liability.** EU law does not let you exclude liability against consumers
  wholesale, so the cap carves out death and personal injury, fraud, gross
  negligence and intent, product liability, and anything else non-excludable.
- **The EU ODR platform is not referenced.** It shut down on 20 July 2025, so
  section 20 points to the Estonian Consumer Disputes Committee instead. Many
  T&C templates still cite the dead ODR link — do not copy that.
- **Apple as third-party beneficiary.** Section 4.3 includes the acknowledgement
  Apple requires for App Store distribution, including that Apple provides no
  support for your apps.


## Changelog

`changelog.html` renders from `changelog.json`. Nothing is hard-coded into the
page, so publishing an update means editing that one file — by hand, or through
the admin page.

### Publishing an update

```bash
python3 tools/admin-server.py
```

Open <http://127.0.0.1:4321/admin.html>, fill in the form, press **Save**. That
writes `changelog.json` directly. Then deploy the site as usual.

The **Update log** field takes one item per line. Prefix a line with `New:`,
`Improved:` or `Fixed:` to give it a coloured badge; lines without a prefix
render as plain notes. Add an app under **Apps** before posting updates for it.

If the admin server is not running, **Save** fails loudly and tells you to use
**Download JSON** instead — it never silently discards your edits.

### Data shape

```json
{
  "apps":    [{ "id": "orange-timer", "name": "Orange Timer", "icon": "assets/img/orange-timer.png" }],
  "entries": [{
    "id": "ot-1-2-0", "app": "orange-timer", "version": "1.2.0",
    "date": "2026-08-18", "title": "Menu bar countdown",
    "notes": [{ "tag": "new", "text": "..." }]
  }]
}
```

Entries sort newest-first by `date`, with `version` breaking ties, so the order
in the file does not matter. `tag` is `new`, `improved`, `fixed` or `null`.
Filtering by app is in the URL (`changelog.html?app=locky-mocky`), so links to a
single app's history are shareable.

### Safety

The server validates before it writes: unknown app references, malformed dates,
duplicate ids and bad JSON are all rejected with a message, and the existing
file is left untouched. Each successful save copies the previous file into
`.changelog-backups/` (last 20 kept) and then replaces `changelog.json` in one
atomic rename, so an interrupted write cannot truncate it.

**The seed entries in `changelog.json` are samples.** Delete them before you go
live.

## Deploying

The site is static — upload it to any host. But **do not upload the authoring
tools**: `admin.html`, `assets/js/admin.js`, `assets/css/admin.css` and
`tools/`. The save endpoint has no authentication because it is only ever meant
to listen on `127.0.0.1`. `.deployignore` lists everything to leave behind; it
is a checklist, not a file any tool reads automatically.


## App pages

Each shipped app gets its own page — `orange-timer.html` and so on. They exist
mainly to be found: the landing page can only rank for the brand, while a
dedicated page can rank for what the app actually does. They are also where a
€15 purchase gets justified, and they give you a canonical URL for the App
Store's support and marketing fields.

**These pages are generated. Do not edit the HTML** — your changes will be
overwritten. Edit `content/apps.json` and rebuild:

```bash
python3 tools/build.py
```

`--check` reports what would change without writing, which is useful in CI or a
pre-deploy hook.

### Why a build step

The header and footer were previously copy-pasted into every page; adding the
changelog link meant editing three files and it was about to become six. The
generator keeps one copy of the site chrome in `templates/base.html` and pours
per-app content into it.

The output is plain static HTML with no client-side rendering. That is
deliberate — rendering these pages from JSON in the browser, the way the
changelog does, would undermine the search indexing that is the main reason they
exist. The changelog can get away with it because nobody needs to find it via
Google.

The build also warns if an app has a page but is missing from `changelog.json`,
so the two lists cannot drift apart silently.

### Content conventions

- `[[double brackets]]` render with the yellow placeholder highlight, the same
  marker the Terms page uses. Remove the brackets once a value is confirmed.
- `{apple}` renders the Apple logo glyph from the icon sprite.
- A screenshot with `"src": null` renders a sized placeholder box telling you
  what to drop in. Real images go in `assets/img/shots/`.
- `"draft": true` shows the placeholder banner at the top of the page. Set it to
  `false` once the copy and screenshots are yours.

### Adding another app

Copy the `orange-timer` block in `content/apps.json`, change the `id` (it
becomes the filename), rewrite the content, and run the build. Then add the app
in `admin.html` so you can post updates for it, and link the new page from the
relevant row in `index.html`.


## Blog

`blog.html` lists posts; each post is generated as `blog/<slug>.html`. Like the
app pages these are real static HTML, not client-rendered, so they can be
indexed and shared.

### Writing a post

```bash
python3 tools/admin-server.py
```

Open <http://127.0.0.1:4321/admin.html> and switch to the **Blog** tab. Write,
press **Save**. The save writes `content/posts.json` *and rebuilds the static
pages*, so the post is live on the local site immediately — then deploy as
usual.

Tick **Keep as draft** to hold a post back. Drafts are not built at all: no
page, no index entry, nothing to stumble across. Untick and save, and the page
appears; re-tick and save, and the page is deleted again.

### Formatting

The body is Markdown. Supported:

| | |
|---|---|
| `##` `###` `####` | headings |
| `**bold**` `*italic*` `` `code` `` | inline |
| `[text](url)` | links — external ones get `target="_blank"` automatically |
| `![alt](path)` | images; alone on a line it becomes a figure with a caption |
| `- item` / `1. item` | lists |
| `> quote` | blockquote |
| ` ``` ` | fenced code block |
| `---` | divider |

The toolbar inserts all of these, and ⌘B / ⌘I / ⌘K work on the selection. The
right-hand pane is a live preview.

**Raw HTML in a post is escaped, not rendered.** That is deliberate: content
arriving through a web form should never be able to inject markup into the page.
`javascript:` links are rejected the same way.

### Images

Three ways to add one, all of which save into `assets/img/blog/`:

- **Drag an image straight onto the editor** — it uploads and inserts the
  Markdown at your cursor
- **Image…** in the toolbar opens a file picker
- **Upload…** next to the Cover image field sets the post's cover

Filenames are slugified and stripped of any path information, and collisions get
a numeric suffix rather than overwriting. Only PNG, JPEG, GIF, WebP and SVG are
accepted, up to 12 MB.

### One Markdown parser, not two

`tools/markdown.py` renders posts at build time, and the admin's live preview
calls `POST /api/preview` to render through *that same module*. There is no
second implementation in JavaScript, so the preview cannot drift away from what
actually gets published.

### Safety

Same guarantees as the changelog: posts are validated before anything is
written (slug format, date format, duplicate slugs, empty bodies), the previous
file is backed up to `.changelog-backups/`, and the write is an atomic rename.
If the rebuild fails after a successful save, the admin says so explicitly
rather than reporting success.
