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

  // Keep native FontAwesome icons to avoid missing icons on mobile/offline.
})(jQuery);

