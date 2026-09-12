/* Changelog admin — local tool.

   Loads changelog.json, lets you edit it through a form, and PUTs it back via
   the small server in tools/admin-server.py. If that server is not running the
   Save button falls back to telling you to use "Download JSON" instead, so no
   work is ever silently lost. */

(function () {
  'use strict';

  var TAGS = ['new', 'improved', 'fixed'];
  var TAG_LABELS = { new: 'New', improved: 'Improved', fixed: 'Fixed' };

  var data = { apps: [], entries: [] };
  var editingId = null;
  var dirty = false;

  var $ = function (sel) { return document.querySelector(sel); };

  var statusEl = $('#status');
  var dirtyEl = $('#dirty-flag');
  var listEl = $('#entry-list');
  var appListEl = $('#app-list');
  var countEl = $('#entry-count');
  var form = $('#entry-form');
  var appForm = $('#app-form');

  /* ---------------------------------------------------------------- helpers */

  function el(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  }

  function status(msg, kind) {
    statusEl.textContent = msg || '';
    statusEl.hidden = !msg;
    statusEl.className = 'admin-status' + (kind ? ' is-' + kind : '');
    if (msg && kind === 'ok') {
      clearTimeout(status._t);
      status._t = setTimeout(function () { statusEl.hidden = true; }, 4000);
    }
  }

  function setDirty(value) {
    dirty = value;
    dirtyEl.hidden = !value;
  }

  function slug(s) {
    return String(s).toLowerCase().trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function uniqueId(base) {
    var id = base || 'entry';
    var n = 2;
    while (data.entries.some(function (e) { return e.id === id; })) {
      id = base + '-' + n++;
    }
    return id;
  }

  function appById(id) {
    return data.apps.filter(function (a) { return a.id === id; })[0] || null;
  }

  /* Local calendar date, not UTC: toISOString() would roll back a day for
     anyone east of Greenwich posting in the evening. */
  function todayLocal() {
    var d = new Date();
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }

  function formatDate(iso) {
    var p = String(iso || '').split('-');
    if (p.length !== 3) return iso || '';
    var d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    return isNaN(d) ? iso : d.toLocaleDateString('en-GB', {
      day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC'
    });
  }

  /* Text lines <-> note objects. "New: foo" becomes {tag:'new', text:'foo'}. */

  function parseNotes(text) {
    return String(text).split('\n')
      .map(function (line) { return line.trim(); })
      .filter(Boolean)
      .map(function (line) {
        for (var i = 0; i < TAGS.length; i++) {
          var re = new RegExp('^' + TAGS[i] + '\\s*:\\s*', 'i');
          if (re.test(line)) {
            return { tag: TAGS[i], text: line.replace(re, '').trim() };
          }
        }
        return { tag: null, text: line };
      });
  }

  function notesToText(notes) {
    return (notes || []).map(function (n) {
      return n.tag ? TAG_LABELS[n.tag] + ': ' + n.text : n.text;
    }).join('\n');
  }

  function sorted(entries) {
    return entries.slice().sort(function (a, b) {
      if (a.date !== b.date) return a.date < b.date ? 1 : -1;
      return String(b.version || '').localeCompare(String(a.version || ''), undefined, { numeric: true });
    });
  }

  /* ---------------------------------------------------------------- render  */

  function renderAppOptions() {
    var sel = $('#f-app');
    var current = sel.value;
    sel.textContent = '';

    if (!data.apps.length) {
      var opt = el('option', null, 'Add an app first');
      opt.value = '';
      sel.appendChild(opt);
      sel.disabled = true;
      return;
    }

    sel.disabled = false;
    data.apps.forEach(function (app) {
      var o = el('option', null, app.name);
      o.value = app.id;
      sel.appendChild(o);
    });
    if (current) sel.value = current;
  }

  function renderApps() {
    appListEl.textContent = '';

    if (!data.apps.length) {
      appListEl.appendChild(el('p', 'admin-empty', 'No apps yet.'));
      return;
    }

    data.apps.forEach(function (app) {
      var row = el('div', 'admin-row');

      if (app.icon) {
        var img = document.createElement('img');
        img.className = 'admin-row__icon';
        img.src = app.icon;
        img.alt = '';
        img.width = 28;
        img.height = 28;
        img.addEventListener('error', function () { img.style.visibility = 'hidden'; });
        row.appendChild(img);
      }

      var meta = el('div', 'admin-row__meta');
      meta.appendChild(el('strong', null, app.name));
      meta.appendChild(el('span', 'admin-row__sub', app.id));
      row.appendChild(meta);

      var used = data.entries.filter(function (e) { return e.app === app.id; }).length;
      row.appendChild(el('span', 'admin-row__sub', used + (used === 1 ? ' update' : ' updates')));

      var del = el('button', 'admin-link admin-link--danger', 'Remove');
      del.type = 'button';
      del.addEventListener('click', function () {
        if (used) {
          status('Remove the ' + used + ' update(s) for ' + app.name + ' first.', 'error');
          return;
        }
        if (!confirm('Remove ' + app.name + '?')) return;
        data.apps = data.apps.filter(function (a) { return a.id !== app.id; });
        setDirty(true);
        renderAll();
      });
      row.appendChild(del);

      appListEl.appendChild(row);
    });
  }

  function renderEntries() {
    listEl.textContent = '';
    countEl.textContent = data.entries.length
      ? data.entries.length + (data.entries.length === 1 ? ' update' : ' updates')
      : '';

    if (!data.entries.length) {
      listEl.appendChild(el('p', 'admin-empty', 'Nothing published yet.'));
      return;
    }

    sorted(data.entries).forEach(function (entry) {
      var app = appById(entry.app);
      var row = el('div', 'admin-row' + (entry.id === editingId ? ' is-editing' : ''));

      if (app && app.icon) {
        var img = document.createElement('img');
        img.className = 'admin-row__icon';
        img.src = app.icon;
        img.alt = '';
        img.width = 28;
        img.height = 28;
        img.addEventListener('error', function () { img.style.visibility = 'hidden'; });
        row.appendChild(img);
      }

      var meta = el('div', 'admin-row__meta');
      var line = el('div', 'admin-row__line');
      line.appendChild(el('strong', null, app ? app.name : entry.app));
      if (entry.version) line.appendChild(el('span', 'admin-pill', entry.version));
      meta.appendChild(line);

      var sub = formatDate(entry.date) +
        ' · ' + (entry.notes || []).length + ' item' + ((entry.notes || []).length === 1 ? '' : 's') +
        (entry.title ? ' · ' + entry.title : '');
      meta.appendChild(el('span', 'admin-row__sub', sub));
      row.appendChild(meta);

      var edit = el('button', 'admin-link', 'Edit');
      edit.type = 'button';
      edit.addEventListener('click', function () { startEdit(entry.id); });
      row.appendChild(edit);

      var del = el('button', 'admin-link admin-link--danger', 'Delete');
      del.type = 'button';
      del.addEventListener('click', function () {
        if (!confirm('Delete the ' + (entry.version || '') + ' update for ' +
          (app ? app.name : entry.app) + '?')) return;
        data.entries = data.entries.filter(function (e) { return e.id !== entry.id; });
        if (editingId === entry.id) resetForm();
        setDirty(true);
        renderAll();
      });
      row.appendChild(del);

      listEl.appendChild(row);
    });
  }

  function renderAll() {
    renderAppOptions();
    renderApps();
    renderEntries();
  }

  /* ------------------------------------------------------------------ form  */

  function resetForm() {
    editingId = null;
    form.reset();
    $('#f-date').value = todayLocal();
    $('#form-title').textContent = 'Add an update';
    $('#submit-btn').textContent = 'Add update';
    $('#cancel-btn').hidden = true;
    renderEntries();
  }

  function startEdit(id) {
    var entry = data.entries.filter(function (e) { return e.id === id; })[0];
    if (!entry) return;

    editingId = id;
    $('#f-app').value = entry.app;
    $('#f-version').value = entry.version || '';
    $('#f-date').value = entry.date || '';
    $('#f-title').value = entry.title || '';
    $('#f-notes').value = notesToText(entry.notes);

    $('#form-title').textContent = 'Edit update';
    $('#submit-btn').textContent = 'Save changes';
    $('#cancel-btn').hidden = false;
    renderEntries();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  form.addEventListener('submit', function (ev) {
    ev.preventDefault();

    var app = $('#f-app').value;
    if (!app) { status('Add an app before posting an update.', 'error'); return; }

    var notes = parseNotes($('#f-notes').value);
    if (!notes.length) { status('Write at least one line in the update log.', 'error'); return; }

    var payload = {
      app: app,
      version: $('#f-version').value.trim(),
      date: $('#f-date').value,
      title: $('#f-title').value.trim(),
      notes: notes
    };

    if (editingId) {
      data.entries = data.entries.map(function (e) {
        return e.id === editingId ? Object.assign({}, e, payload) : e;
      });
      status('Update edited. Remember to Save.', 'ok');
    } else {
      // id first, so new entries match the key order of existing ones
      data.entries.push(Object.assign(
        { id: uniqueId(slug(app + '-' + (payload.version || payload.date))) },
        payload
      ));
      status('Update added. Remember to Save.', 'ok');
    }

    setDirty(true);
    resetForm();
    renderAll();
  });

  $('#cancel-btn').addEventListener('click', resetForm);

  appForm.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var name = $('#a-name').value.trim();
    if (!name) return;

    var id = slug(name);
    if (appById(id)) { status('An app with that name already exists.', 'error'); return; }

    data.apps.push({ id: id, name: name, icon: $('#a-icon').value.trim() || null });
    appForm.reset();
    setDirty(true);
    renderAll();
    status('App added. Remember to Save.', 'ok');
  });

  /* ------------------------------------------------------------------ save  */

  function serialise() {
    return JSON.stringify(data, null, 2) + '\n';
  }

  $('#save-btn').addEventListener('click', function () {
    status('Saving…');
    fetch('/api/changelog', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: serialise()
    })
      .then(function (res) {
        if (!res.ok) return res.text().then(function (t) { throw new Error(t || 'HTTP ' + res.status); });
        setDirty(false);
        status('Saved to changelog.json', 'ok');
      })
      .catch(function (err) {
        status('Could not save: ' + err.message +
          ' — start tools/admin-server.py, or use Download JSON and replace the file by hand.', 'error');
      });
  });

  $('#download-btn').addEventListener('click', function () {
    var blob = new Blob([serialise()], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'changelog.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  });

  window.addEventListener('beforeunload', function (ev) {
    if (!dirty) return;
    ev.preventDefault();
    ev.returnValue = '';
  });

  /* ------------------------------------------------------------------ boot  */

  fetch('changelog.json', { cache: 'no-cache' })
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (loaded) {
      data.apps = Array.isArray(loaded.apps) ? loaded.apps : [];
      data.entries = Array.isArray(loaded.entries) ? loaded.entries : [];
      resetForm();
      renderAll();
    })
    .catch(function (err) {
      status('Could not load changelog.json (' + err.message +
        '). Starting empty — saving will overwrite the file.', 'error');
      resetForm();
      renderAll();
    });
})();

/* ==========================================================================
   Blog panel

   Posts are Markdown. The live preview is rendered by the server via
   /api/preview so it uses the exact same parser the build uses — there is no
   second Markdown implementation here that could drift out of step.
   ========================================================================== */

(function () {
  'use strict';

  var $ = function (sel) { return document.querySelector(sel); };

  var posts = [];
  var editingId = null;
  var dirty = false;
  var slugTouched = false;
  var activePanel = 'changelog';

  var statusEl = $('#status');
  var dirtyEl = $('#dirty-flag');
  var body = $('#p-body');
  var preview = $('#preview');
  var listEl = $('#post-list');
  var fileInput = $('#file-input');
  var uploadTarget = 'body';

  function status(msg, kind) {
    statusEl.textContent = msg || '';
    statusEl.hidden = !msg;
    statusEl.className = 'admin-status' + (kind ? ' is-' + kind : '');
    if (msg && kind === 'ok') {
      clearTimeout(status._t);
      status._t = setTimeout(function () { statusEl.hidden = true; }, 4000);
    }
  }

  function setDirty(v) { dirty = v; if (v) dirtyEl.hidden = false; }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function slugify(s) {
    return String(s).toLowerCase().trim()
      .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 70);
  }

  function todayLocal() {
    var d = new Date(), p = function (n) { return String(n).padStart(2, '0'); };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }

  function formatDate(iso) {
    var p = String(iso || '').split('-');
    if (p.length !== 3) return iso || '';
    var d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    return isNaN(d) ? iso : d.toLocaleDateString('en-GB',
      { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  }

  /* ------------------------------------------------------------- tabs ---- */

  document.querySelectorAll('.admin-tab').forEach(function (tab) {
    tab.addEventListener('click', function () {
      activePanel = tab.dataset.panel;
      document.querySelectorAll('.admin-tab').forEach(function (t) {
        var on = t === tab;
        t.classList.toggle('is-active', on);
        t.setAttribute('aria-selected', String(on));
      });
      $('#panel-changelog').hidden = activePanel !== 'changelog';
      $('#panel-blog').hidden = activePanel !== 'blog';
      $('#view-link').href = activePanel === 'blog' ? 'blog.html' : 'changelog.html';
      $('#download-btn').hidden = activePanel === 'blog';
    });
  });

  /* ------------------------------------------------- markdown toolbar ---- */

  /* Wrap the selection, or insert a template and place the caret usefully. */
  function surround(before, after, placeholder) {
    var start = body.selectionStart, end = body.selectionEnd;
    var selected = body.value.slice(start, end) || placeholder || '';
    var replacement = before + selected + after;
    body.setRangeText(replacement, start, end, 'end');
    if (!body.value.slice(start, end)) {
      body.selectionStart = start + before.length;
      body.selectionEnd = start + before.length + selected.length;
    }
    body.focus();
    onInput();
  }

  function prefixLines(prefix, ordered) {
    var start = body.selectionStart, end = body.selectionEnd;
    var text = body.value;
    var from = text.lastIndexOf('\n', start - 1) + 1;
    var to = text.indexOf('\n', end);
    if (to === -1) to = text.length;

    var lines = text.slice(from, to).split('\n');
    var out = lines.map(function (line, i) {
      var clean = line.replace(/^(\s*([-*]|\d+[.)])\s+|\s*>\s?|\s*#{2,4}\s+)/, '');
      return (ordered ? (i + 1) + '. ' : prefix) + clean;
    }).join('\n');

    body.setRangeText(out, from, to, 'end');
    body.focus();
    onInput();
  }

  function insertBlock(text) {
    var start = body.selectionStart;
    var before = body.value.slice(0, start);
    var pad = before && !before.endsWith('\n\n') ? (before.endsWith('\n') ? '\n' : '\n\n') : '';
    body.setRangeText(pad + text + '\n\n', start, body.selectionEnd, 'end');
    body.focus();
    onInput();
  }

  var ACTIONS = {
    h2: function () { prefixLines('## '); },
    h3: function () { prefixLines('### '); },
    bold: function () { surround('**', '**', 'bold text'); },
    italic: function () { surround('*', '*', 'italic text'); },
    code: function () { surround('`', '`', 'code'); },
    link: function () {
      var url = prompt('Link address', 'https://');
      if (url) surround('[', '](' + url + ')', 'link text');
    },
    ul: function () { prefixLines('- '); },
    ol: function () { prefixLines('', true); },
    quote: function () { prefixLines('> '); },
    pre: function () { insertBlock('```\ncode here\n```'); },
    hr: function () { insertBlock('---'); }
  };

  document.querySelectorAll('.editor-toolbar [data-md]').forEach(function (btn) {
    btn.addEventListener('click', function () { ACTIONS[btn.dataset.md](); });
  });

  body.addEventListener('keydown', function (ev) {
    if (!(ev.metaKey || ev.ctrlKey)) return;
    var key = ev.key.toLowerCase();
    if (key === 'b') { ev.preventDefault(); ACTIONS.bold(); }
    if (key === 'i') { ev.preventDefault(); ACTIONS.italic(); }
    if (key === 'k') { ev.preventDefault(); ACTIONS.link(); }
  });

  /* ---------------------------------------------------------- preview ---- */

  var previewTimer = null;

  function onInput() {
    setDirty(true);
    var words = body.value.trim() ? body.value.trim().split(/\s+/).length : 0;
    $('#editor-stats').textContent =
      words + (words === 1 ? ' word' : ' words') +
      ' · about ' + Math.max(1, Math.round(words / 220)) + ' min to read';

    clearTimeout(previewTimer);
    previewTimer = setTimeout(renderPreview, 250);
  }

  function renderPreview() {
    if (preview.hidden) return;
    fetch('/api/preview', { method: 'POST', body: body.value })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        preview.innerHTML = data.html;
        // Preview images are written relative to the site root; the admin page
        // sits at the root too, so they resolve as-is.
      })
      .catch(function () { /* preview is a nicety, never block on it */ });
  }

  body.addEventListener('input', onInput);

  $('#preview-toggle').addEventListener('click', function () {
    var on = preview.hidden;
    preview.hidden = !on;
    $('#editor').classList.toggle('editor--split', on);
    this.classList.toggle('is-active', on);
    this.setAttribute('aria-pressed', String(on));
    if (on) renderPreview();
  });

  /* ----------------------------------------------------------- upload ---- */

  function upload(file) {
    if (!file) return Promise.reject(new Error('no file'));
    status('Uploading ' + file.name + '…');
    return fetch('/api/upload', {
      method: 'POST',
      headers: { 'Content-Type': file.type, 'X-Filename': file.name },
      body: file
    }).then(function (res) {
      if (!res.ok) return res.text().then(function (t) { throw new Error(t); });
      return res.json();
    });
  }

  function pickFile(target) {
    uploadTarget = target;
    fileInput.value = '';
    fileInput.click();
  }

  $('#img-upload-btn').addEventListener('click', function () { pickFile('body'); });
  $('#cover-upload-btn').addEventListener('click', function () { pickFile('cover'); });

  fileInput.addEventListener('change', function () {
    var file = fileInput.files[0];
    if (!file) return;
    upload(file).then(function (data) {
      if (uploadTarget === 'cover') {
        $('#p-cover').value = data.path;
      } else {
        insertBlock('![' + file.name.replace(/\.[^.]+$/, '') + '](' + data.path + ')');
      }
      setDirty(true);
      status('Uploaded ' + data.path, 'ok');
    }).catch(function (err) { status('Upload failed: ' + err.message, 'error'); });
  });

  /* Drag an image straight onto the textarea. */
  ['dragenter', 'dragover'].forEach(function (evt) {
    body.addEventListener(evt, function (ev) {
      if (ev.dataTransfer && ev.dataTransfer.types.indexOf('Files') !== -1) {
        ev.preventDefault();
        body.classList.add('is-dropping');
      }
    });
  });
  ['dragleave', 'drop'].forEach(function (evt) {
    body.addEventListener(evt, function () { body.classList.remove('is-dropping'); });
  });
  body.addEventListener('drop', function (ev) {
    var file = ev.dataTransfer && ev.dataTransfer.files[0];
    if (!file || file.type.indexOf('image/') !== 0) return;
    ev.preventDefault();
    upload(file).then(function (data) {
      insertBlock('![' + file.name.replace(/\.[^.]+$/, '') + '](' + data.path + ')');
      setDirty(true);
      status('Uploaded ' + data.path, 'ok');
    }).catch(function (err) { status('Upload failed: ' + err.message, 'error'); });
  });

  /* ------------------------------------------------------------- form ---- */

  $('#p-title').addEventListener('input', function () {
    if (slugTouched || editingId) return;
    $('#p-slug').value = slugify(this.value);
    updateSlugPreview();
  });
  $('#p-slug').addEventListener('input', function () {
    slugTouched = true;
    this.value = slugify(this.value);
    updateSlugPreview();
  });

  function updateSlugPreview() {
    var slug = $('#p-slug').value || '…';
    $('#slug-preview').textContent = 'blog/' + slug + '.html';
  }

  function resetPostForm() {
    editingId = null;
    slugTouched = false;
    $('#post-form').reset();
    $('#p-date').value = todayLocal();
    $('#post-form-title').textContent = 'Write a post';
    $('#post-submit-btn').textContent = 'Add post';
    $('#post-cancel-btn').hidden = true;
    updateSlugPreview();
    onInput();
    renderPosts();
  }

  function startEditPost(id) {
    var post = posts.filter(function (p) { return p.id === id; })[0];
    if (!post) return;
    editingId = id;
    slugTouched = true;
    $('#p-title').value = post.title || '';
    $('#p-date').value = post.date || '';
    $('#p-slug').value = post.id;
    $('#p-summary').value = post.summary || '';
    $('#p-cover').value = post.cover || '';
    $('#p-draft').checked = !!post.draft;
    body.value = post.body || '';
    $('#post-form-title').textContent = 'Edit post';
    $('#post-submit-btn').textContent = 'Save changes';
    $('#post-cancel-btn').hidden = false;
    updateSlugPreview();
    onInput();
    renderPosts();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  $('#post-cancel-btn').addEventListener('click', resetPostForm);

  $('#post-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var slug = slugify($('#p-slug').value);
    if (!slug) { status('The post needs a URL slug.', 'error'); return; }
    if (!body.value.trim()) { status('The post body is empty.', 'error'); return; }

    var clash = posts.some(function (p) { return p.id === slug && p.id !== editingId; });
    if (clash) { status('Another post already uses the slug "' + slug + '".', 'error'); return; }

    var payload = {
      id: slug,
      draft: $('#p-draft').checked,
      title: $('#p-title').value.trim(),
      date: $('#p-date').value,
      cover: $('#p-cover').value.trim() || null,
      summary: $('#p-summary').value.trim(),
      body: body.value
    };

    if (editingId) {
      posts = posts.map(function (p) { return p.id === editingId ? payload : p; });
      status('Post updated. Remember to Save.', 'ok');
    } else {
      posts.push(payload);
      status('Post added. Remember to Save.', 'ok');
    }
    setDirty(true);
    resetPostForm();
  });

  /* ------------------------------------------------------------- list ---- */

  function renderPosts() {
    listEl.textContent = '';
    $('#post-count').textContent = posts.length
      ? posts.length + (posts.length === 1 ? ' post' : ' posts') : '';

    if (!posts.length) {
      listEl.appendChild(el('p', 'admin-empty', 'Nothing written yet.'));
      return;
    }

    posts.slice().sort(function (a, b) {
      return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
    }).forEach(function (post) {
      var row = el('div', 'admin-row' + (post.id === editingId ? ' is-editing' : ''));

      var meta = el('div', 'admin-row__meta');
      var line = el('div', 'admin-row__line');
      line.appendChild(el('strong', null, post.title || '(untitled)'));
      if (post.draft) line.appendChild(el('span', 'admin-pill admin-pill--draft', 'Draft'));
      meta.appendChild(line);
      meta.appendChild(el('span', 'admin-row__sub',
        formatDate(post.date) + ' · blog/' + post.id + '.html'));
      row.appendChild(meta);

      if (!post.draft) {
        var view = el('a', 'admin-link', 'View');
        view.href = 'blog/' + post.id + '.html';
        view.target = '_blank';
        view.rel = 'noopener';
        row.appendChild(view);
      }

      var edit = el('button', 'admin-link', 'Edit');
      edit.type = 'button';
      edit.addEventListener('click', function () { startEditPost(post.id); });
      row.appendChild(edit);

      var del = el('button', 'admin-link admin-link--danger', 'Delete');
      del.type = 'button';
      del.addEventListener('click', function () {
        if (!confirm('Delete "' + (post.title || post.id) + '"?')) return;
        posts = posts.filter(function (p) { return p.id !== post.id; });
        if (editingId === post.id) resetPostForm();
        setDirty(true);
        renderPosts();
      });
      row.appendChild(del);

      listEl.appendChild(row);
    });
  }

  /* ------------------------------------------------------------- save ---- */

  /* The changelog Save button is wired up earlier in this file; when the blog
     panel is showing we take over the same button. */
  $('#save-btn').addEventListener('click', function () {
    if (activePanel !== 'blog') return;
    status('Saving…');
    fetch('/api/posts', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ posts: posts }, null, 2)
    })
      .then(function (res) {
        if (!res.ok) return res.text().then(function (t) { throw new Error(t); });
        return res.json();
      })
      .then(function (data) {
        dirty = false;
        dirtyEl.hidden = true;
        if (data.rebuilt) {
          status('Saved and site rebuilt — ' + data.posts + ' post(s).', 'ok');
        } else {
          status('Saved, but the rebuild failed: ' + (data.buildError || 'unknown') +
            '. Run python3 tools/build.py to see the error.', 'error');
        }
      })
      .catch(function (err) {
        status('Could not save: ' + err.message +
          ' — is tools/admin-server.py running?', 'error');
      });
  }, true);

  /* ------------------------------------------------------------- boot ---- */

  fetch('/api/posts', { cache: 'no-cache' })
    .then(function (r) { return r.ok ? r.json() : { posts: [] }; })
    .then(function (data) {
      posts = Array.isArray(data.posts) ? data.posts : [];
      resetPostForm();
    })
    .catch(function () { resetPostForm(); });
})();
