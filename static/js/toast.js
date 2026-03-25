/**
 * Smart Library — Toast Notifications
 * Usage: SLToast.success('U ruajt!'); SLToast.error('Gabim');
 */
(function () {
  var container = null;
  var defaultDuration = 5000;

  function ensureContainer() {
    if (container) return container;
    container = document.getElementById('sl-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'sl-toast-container';
      container.setAttribute('role', 'region');
      container.setAttribute('aria-label', 'Njoftime');
      document.body.appendChild(container);
    }
    return container;
  }

  var icons = {
    success: '✓',
    error: '✕',
    warning: '!',
    info: 'ⓘ'
  };

  var titles = {
    success: 'U krye',
    error: 'Gabim',
    warning: 'Kujdes',
    info: 'Njoftim'
  };

  function show(type, message, options) {
    options = options || {};
    var duration = options.duration !== undefined ? options.duration : defaultDuration;
    var title = options.title || titles[type];
    var id = 'sl-toast-' + Date.now() + '-' + Math.random().toString(36).slice(2);

    var el = document.createElement('div');
    el.className = 'sl-toast sl-toast-' + type;
    el.id = id;
    el.setAttribute('role', 'alert');
    el.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
    if (duration > 0) el.setAttribute('data-duration', duration >= 7000 ? 'long' : (duration <= 3500 ? 'short' : 'normal'));

    el.innerHTML =
      '<span class="sl-toast-icon" aria-hidden="true">' + (icons[type] || icons.info) + '</span>' +
      '<div class="sl-toast-body">' +
        '<div class="sl-toast-title">' + escapeHtml(title) + '</div>' +
        '<div class="sl-toast-message">' + escapeHtml(message) + '</div>' +
      '</div>' +
      '<button type="button" class="sl-toast-close" aria-label="Mbyll">×</button>' +
      (duration > 0 ? '<div class="sl-toast-progress"></div>' : '');

    var c = ensureContainer();
    c.appendChild(el);

    function remove() {
      el.setAttribute('data-exit', '');
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 300);
    }

    el.querySelector('.sl-toast-close').addEventListener('click', remove);

    if (duration > 0) {
      var t = setTimeout(remove, duration);
      el.addEventListener('mouseenter', function () { clearTimeout(t); });
      el.addEventListener('mouseleave', function () { t = setTimeout(remove, 1800); });
    }

    return id;
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  window.SLToast = {
    success: function (msg, opts) { return show('success', msg, opts); },
    error: function (msg, opts) { return show('error', msg, opts); },
    warning: function (msg, opts) { return show('warning', msg, opts); },
    info: function (msg, opts) { return show('info', msg, opts); },
    show: show
  };
})();
