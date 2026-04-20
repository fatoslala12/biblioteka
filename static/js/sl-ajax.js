/**
 * Smart Library — AJAX navigation with skeleton loading
 * Intercepts links to catalog, njoftime, evente, libri i javes
 */
(function () {
  var AJAX_PATHS = ['/catalog/', '/njoftime/', '/evente/', '/libri-i-javes/', '/video/'];

  function isAjaxPath(url) {
    try {
      var path = url.indexOf('http') === 0 ? new URL(url).pathname : url.split('?')[0] || '/';
      return AJAX_PATHS.some(function (p) { return path === p || path.indexOf(p) === 0; });
    } catch (_) { return false; }
  }

  var cardSk = '<div class="rounded-3xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-950"><div class="sl-skeleton sl-skeleton-brand rounded-xl h-5 mb-3" style="width:85%"></div><div class="sl-skeleton sl-skeleton-brand rounded-lg h-4 mb-4" style="width:55%"></div><div class="flex gap-2 mb-4"><span class="sl-skeleton sl-skeleton-brand rounded-full h-6 w-14"></span><span class="sl-skeleton sl-skeleton-brand rounded-full h-6 w-16"></span></div><div class="grid grid-cols-3 gap-3"><div class="sl-skeleton sl-skeleton-brand rounded-2xl h-14"></div><div class="sl-skeleton sl-skeleton-brand rounded-2xl h-14"></div><div class="sl-skeleton sl-skeleton-brand rounded-2xl h-14"></div></div></div>';
  var catalogSkeleton = '<section class="relative"><div class="relative mx-auto max-w-7xl px-4 pt-10 sm:px-6 lg:px-8"><div class="mt-8 grid gap-6 lg:grid-cols-12"><aside class="lg:col-span-3"><div class="sl-skeleton sl-skeleton-brand rounded-3xl h-96"></div></aside><div class="lg:col-span-9"><div class="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">' +
    (cardSk + cardSk + cardSk + cardSk + cardSk + cardSk) +
    '</div></div></div></div></section>';

  var itemSk = '<div class="rounded-3xl border border-slate-200 p-6 dark:border-slate-800"><div class="sl-skeleton sl-skeleton-brand h-40 rounded-2xl mb-4"></div><div class="sl-skeleton sl-skeleton-brand h-5 rounded mb-2" style="width:75%"></div><div class="sl-skeleton sl-skeleton-brand h-4 rounded mb-3" style="width:20%"></div><div class="sl-skeleton sl-skeleton-brand h-4 rounded" style="width:100%"></div></div>';
  var sectionSkeleton = '<section class="mx-auto max-w-7xl px-4 pt-10 sm:px-6 lg:px-8"><div class="rounded-3xl border border-slate-200 bg-white p-10 shadow-sm dark:border-slate-800 dark:bg-slate-950"><div class="sl-skeleton sl-skeleton-brand h-6 rounded mb-2" style="width:6rem"></div><div class="sl-skeleton sl-skeleton-brand h-8 rounded mb-8" style="width:18rem"></div><div class="grid gap-5 md:grid-cols-2">' +
    (itemSk + itemSk + itemSk + itemSk) +
    '</div></div></section>';

  function getSkeleton(path) {
    if (path.indexOf('/catalog') === 0) return catalogSkeleton;
    return sectionSkeleton;
  }

  var container = null;

  function getContainer() {
    if (!container) container = document.getElementById('sl-ajax-container');
    return container;
  }

  function load(url, pushState) {
    var c = getContainer();
    if (!c) return false;

    var path = url.replace(/^https?:\/\/[^/]+/, '') || '/';
    var skeleton = getSkeleton(path);
    c.innerHTML = skeleton;

    var bar = document.getElementById('sl-loading-bar');
    if (bar) bar.classList.add('loading');

    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (r) {
        if (!r.ok) throw new Error('Request failed');
        return r.json();
      })
      .then(function (data) {
        if (bar) bar.classList.remove('loading');
        if (data && data.html) {
          c.innerHTML = data.html;
          if (pushState) history.pushState({ path: path }, '', url);
          if (data.title) document.title = data.title;
          initAjaxLinks(c);
          document.dispatchEvent(new CustomEvent('sl:navigation', { detail: { path: path } }));
        }
      })
      .catch(function () {
        if (bar) bar.classList.remove('loading');
        window.location.href = url;
      });

    return true;
  }

  function initAjaxLinks(root) {
    root = root || document;
    var sel = 'a[href^="/catalog"], a[href^="/njoftime"], a[href^="/evente"], a[href^="/libri-i-javes"], a[href^="/video"]';
    try {
      root.querySelectorAll(sel).forEach(function (a) {
        if (a.target || a.download) return;
        var h = a.getAttribute('href');
        if (h && h.indexOf('http') === 0 && h.indexOf(location.origin) !== 0) return;
        a.classList.add('sl-ajax-link');
      });
      root.querySelectorAll('a[href^="?"]').forEach(function (a) {
        if (a.target || a.download) return;
        if (document.location.pathname.indexOf('/catalog') === 0) a.classList.add('sl-ajax-link');
      });
    } catch (_) {}
  }

  document.addEventListener('click', function (e) {
    var a = e.target.closest('a.sl-ajax-link');
    if (!a) {
      a = e.target.closest('a[href^="/catalog"], a[href^="/njoftime"], a[href^="/evente"], a[href^="/libri-i-javes"], a[href^="/video"], a[href^="?"]');
    }
    if (a && !a.target && !a.download) {
      var href = a.href;
      if (href && href.indexOf(location.origin) === 0 && isAjaxPath(href)) {
        e.preventDefault();
        load(href, true);
      }
    }
  });

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (form.tagName !== 'FORM' || form.method.toLowerCase() !== 'get') return;
    var action = (form.getAttribute('action') || window.location.pathname).split('?')[0];
    if (!isAjaxPath(action)) return;
    e.preventDefault();
    var params = new URLSearchParams(new FormData(form));
    var url = action + (params.toString() ? '?' + params.toString() : '');
    load(url, true);
  });

  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.path) {
      load(window.location.href, false);
    }
  });

  initAjaxLinks(document);
})();
