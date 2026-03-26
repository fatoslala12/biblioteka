(function ($) {
  function detectRoleLabel(username) {
    var uname = (username || "").toLowerCase();
    if (uname.indexOf("admin") !== -1 || uname.indexOf("root") !== -1) {
      return "Administrator";
    }

    // Heuristic: users that can view group/user management are admins.
    var hasGroups =
      $('#jazzy-sidebar a[href*="/admin/auth/group/"]').length > 0 ||
      $("#jazzy-sidebar a:contains('Grupe')").length > 0;
    var hasUsers = $('#jazzy-sidebar a[href*="/admin/accounts/user/"]').length > 0;
    if (hasGroups && hasUsers) return "Administrator";

    return "Staf";
  }

  $(function () {
    var username = "";
    var $defaultUser = $("#jazzy-navbar .nav-item.dropdown").first();
    if ($defaultUser.length) {
      username = ($defaultUser.find("a.nav-link[title]").attr("title") || "").trim();
      if (!username) {
        username = ($defaultUser.find(".dropdown-header").first().text() || "").trim();
      }
      if (!username) {
        username = ($defaultUser.find("a.nav-link").first().text() || "").trim();
      }
    }
    if (!username) {
      username = ($("#jazzy-sidebar .user-panel .info a").first().text() || "").trim();
    }

    // Keep Jazzmin default topbar user dropdown visible on all viewports.
    if ($defaultUser.length) {
      $defaultUser.show();
    }

    // In sidebar user panel, show user type instead of username.
    var roleLabel = detectRoleLabel(username);
    var $sidebarUser = $("#jazzy-sidebar .user-panel .info a").first();
    if ($sidebarUser.length) {
      $sidebarUser.text(roleLabel);
      $sidebarUser.attr("title", "Përdoruesi: " + (username || "—"));
    }

  });

  /* Lucide SVG icons – më të holla se FontAwesome */
  (function () {
    var faToLucide = {
      "fa-th-large": "layout-dashboard", "fa-tachometer-alt": "layout-dashboard",
      "fa-user-shield": "shield", "fa-id-card": "id-card", "fa-book": "book-open",
      "fa-barcode": "barcode", "fa-pen-nib": "pen-line", "fa-tags": "tags",
      "fa-building": "building", "fa-hashtag": "hash", "fa-inbox": "inbox",
      "fa-exchange-alt": "arrow-left-right", "fa-calendar-check": "calendar-check",
      "fa-envelope": "mail", "fa-bullhorn": "megaphone", "fa-calendar-alt": "calendar",
      "fa-video": "video", "fa-receipt": "receipt", "fa-cash-register": "wallet",
      "fa-sliders-h": "sliders", "fa-list-ol": "list-ordered",
      "fa-chevron-right": "chevron-right", "fa-plus-circle": "plus-circle", "fa-bars": "menu"
    };
    function getLucide(el) {
      var c = (el.className || "").split(/\s+/);
      for (var i = 0; i < c.length; i++)
        if (c[i].indexOf("fa-") === 0 && faToLucide[c[i]]) return faToLucide[c[i]];
      return null;
    }
    function run() {
      document.querySelectorAll("#jazzy-sidebar .nav-icon.fas, #jazzy-sidebar .nav-icon.far, #jazzy-sidebar .nav-icon.fa").forEach(function (el) {
        var name = getLucide(el);
        if (name) {
          el.setAttribute("data-lucide", name);
          el.className = (el.className || "").replace(/\bfa[sr]?\b|fa-[\w-]+/g, "").trim() + " sl-lucide-icon";
          el.style.fontSize = "0";
        }
      });
      if (window.lucide && lucide.createIcons) lucide.createIcons();
    }
    if (window.lucide) {
      run();
      lucide.createIcons();
    } else {
      var s = document.createElement("script");
      s.src = "https://unpkg.com/lucide@latest/dist/umd/lucide.min.js";
      s.onload = function () { run(); if (window.lucide) lucide.createIcons(); };
      document.head.appendChild(s);
    }
  })();
})(jQuery);

