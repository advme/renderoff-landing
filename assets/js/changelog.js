/* Renders the public changelog from changelog.json.
   Nodes are built with the DOM API rather than innerHTML so that entry text is
   always treated as text, never as markup. */

(function () {
  'use strict';

  var TAG_LABELS = { new: 'New', improved: 'Improved', fixed: 'Fixed' };

  var listEl = document.querySelector('#changelog-list');
  var filtersEl = document.querySelector('#changelog-filters');
  var statusEl = document.querySelector('#changelog-status');

  var state = { apps: [], entries: [], filter: 'all' };

  function setStatus(message, isError) {
    statusEl.textContent = message || '';
    statusEl.hidden = !message;
    statusEl.classList.toggle('is-error', !!isError);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function appById(id) {
    for (var i = 0; i < state.apps.length; i++) {
      if (state.apps[i].id === id) return state.apps[i];
    }
    return { id: id, name: id, icon: null };
  }

  function formatDate(iso) {
    var parts = String(iso || '').split('-');
    if (parts.length !== 3) return iso || '';
    var d = new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2]));
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('en-GB', {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'
    });
  }

  /* Newest first; ties broken by version so same-day releases stay ordered. */
  function sortEntries(entries) {
    return entries.slice().sort(function (a, b) {
      if (a.date !== b.date) return a.date < b.date ? 1 : -1;
      return String(b.version || '').localeCompare(String(a.version || ''), undefined, { numeric: true });
    });
  }

  function renderEntry(entry) {
    var app = appById(entry.app);

    var article = el('article', 'entry');
    article.id = 'v-' + (entry.id || entry.app + '-' + entry.version);

    var head = el('div', 'entry__head');

    if (app.icon) {
      var icon = document.createElement('img');
      icon.className = 'entry__icon';
      icon.src = app.icon;
      icon.alt = '';
      icon.width = 40;
      icon.height = 40;
      icon.loading = 'lazy';
      head.appendChild(icon);
    }

    var heading = el('div', 'entry__heading');
    var nameRow = el('div', 'entry__name-row');
    nameRow.appendChild(el('h2', 'entry__app', app.name));
    if (entry.version) nameRow.appendChild(el('span', 'entry__version', entry.version));
    heading.appendChild(nameRow);

    var time = el('time', 'entry__date', formatDate(entry.date));
    time.dateTime = entry.date || '';
    heading.appendChild(time);

    head.appendChild(heading);
    article.appendChild(head);

    if (entry.title) article.appendChild(el('h3', 'entry__title', entry.title));

    var notes = Array.isArray(entry.notes) ? entry.notes : [];
    if (notes.length) {
      var ul = el('ul', 'entry__notes');
      notes.forEach(function (note) {
        var li = el('li');
        var tag = note && note.tag;
        if (tag && TAG_LABELS[tag]) {
          li.appendChild(el('span', 'tag tag--' + tag, TAG_LABELS[tag]));
        }
        li.appendChild(document.createTextNode((note && note.text) || ''));
        ul.appendChild(li);
      });
      article.appendChild(ul);
    }

    return article;
  }

  function render() {
    listEl.textContent = '';

    var entries = sortEntries(state.entries).filter(function (e) {
      return state.filter === 'all' || e.app === state.filter;
    });

    if (!entries.length) {
      listEl.appendChild(el('p', 'changelog__empty', 'No updates published yet.'));
      return;
    }

    entries.forEach(function (entry) {
      listEl.appendChild(renderEntry(entry));
    });
  }

  function renderFilters() {
    filtersEl.textContent = '';

    var options = [{ id: 'all', name: 'All apps' }].concat(state.apps);

    options.forEach(function (opt) {
      var btn = el('button', 'filter', opt.name);
      btn.type = 'button';
      btn.setAttribute('aria-pressed', String(state.filter === opt.id));
      btn.addEventListener('click', function () {
        state.filter = opt.id;
        var url = new URL(location.href);
        if (opt.id === 'all') url.searchParams.delete('app');
        else url.searchParams.set('app', opt.id);
        history.replaceState(null, '', url);
        renderFilters();
        render();
      });
      filtersEl.appendChild(btn);
    });
  }

  fetch('changelog.json', { cache: 'no-cache' })
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (data) {
      state.apps = Array.isArray(data.apps) ? data.apps : [];
      state.entries = Array.isArray(data.entries) ? data.entries : [];

      var requested = new URL(location.href).searchParams.get('app');
      if (requested && state.apps.some(function (a) { return a.id === requested; })) {
        state.filter = requested;
      }

      setStatus('');
      renderFilters();
      render();
    })
    .catch(function (err) {
      // The most common cause is opening the file directly from disk, where
      // fetch() is blocked by the browser's file:// origin rules.
      var hint = location.protocol === 'file:'
        ? 'Open the site through a local web server rather than from disk — see README.md.'
        : 'Could not load changelog.json (' + err.message + ').';
      setStatus(hint, true);
      filtersEl.hidden = true;
    });
})();
