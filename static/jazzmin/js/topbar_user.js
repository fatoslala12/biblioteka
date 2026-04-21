(function ($) {
  function detectRoleLabel(username) {
    var uname = (username || "").toLowerCase();
    if (uname.indexOf("admin") !== -1 || uname.indexOf("root") !== -1) {
      return "Administrator";
    }

    var hasGroups =
      $('#jazzy-sidebar a[href*="/admin/auth/group/"]').length > 0 ||
      $("#jazzy-sidebar a:contains('Grupe')").length > 0;
    var hasUsers = $('#jazzy-sidebar a[href*="/admin/accounts/user/"]').length > 0;
    if (hasGroups && hasUsers) return "Administrator";

    return "Staf";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function findAdminNotificationNavTarget() {
    var selectors = [
      "#jazzy-navbar ul.navbar-nav.ms-auto",
      "#jazzy-navbar ul.navbar-nav.ml-auto",
      ".app-header.navbar ul.navbar-nav.ms-auto",
      ".app-header.navbar ul.navbar-nav.ml-auto",
      ".main-header.navbar ul.navbar-nav.ms-auto",
      ".main-header.navbar ul.navbar-nav.ml-auto",
      "#jazzy-navbar .navbar-nav.ms-auto",
      "#jazzy-navbar .navbar-nav.ml-auto",
      ".app-header ul.navbar-nav.ms-auto",
      ".app-header ul.navbar-nav.ml-auto",
    ];
    var i;
    for (i = 0; i < selectors.length; i++) {
      var $el = $(selectors[i]).first();
      if ($el.length) return $el;
    }
    var $withUser = $("#jazzy-navbar ul.navbar-nav").filter(function () {
      return $(this).find(".nav-item.dropdown").length > 0;
    }).first();
    if ($withUser.length) return $withUser;
    var $last = $("#jazzy-navbar ul.navbar-nav").last();
    if ($last.length) return $last;
    return $(".app-header ul.navbar-nav").last();
  }

  function injectAdminNotificationBell() {
    var $nav = findAdminNotificationNavTarget();
    if (!$nav.length || $("#slAdminNotifBellWrap").length) return;

    var $li = $("<li>").addClass("nav-item align-items-center d-flex").attr("id", "slAdminNotifBellWrap");
    var $btn = $("<button>")
      .attr({
        type: "button",
        id: "slAdminNotifBellBtn",
        "aria-label": "Notifications",
        "aria-expanded": "false",
      })
      .html('<i class="fas fa-bell" aria-hidden="true"></i>');
    var $badge = $("<span>").attr("id", "slAdminNotifBadge").hide();
    $btn.append($badge);

    var $panel = $("<div>").attr({ id: "slAdminNotifPanel", role: "dialog", "aria-label": "Notifications" });
    $panel.append(
      '<div class="sl-admin-notif-head"><span>Notifications</span><span id="slAdminNotifUnreadHead" class="sl-admin-notif-unread-head" style="display:none;"></span></div>'
    );
    var $scroll = $("<div>").addClass("sl-admin-notif-scroll");
    $panel.append($scroll);
    var $footer = $('<div class="p-2 border-top bg-light small d-flex flex-column gap-1"></div>');
    $footer.append(
      '<a href="#" id="slAdminNotifAllAdmin" class="btn btn-sm btn-primary font-weight-bold">View all (admin)</a>'
    );
    $panel.append($footer);

    $li.append($btn).append($panel);
    $nav.prepend($li);

    function renderUnreadBadge(unread) {
      var $headUnread = $("#slAdminNotifUnreadHead");
      var count = Number(unread || 0);
      if (count > 0) {
        var t = count > 99 ? "99+" : String(count);
        $badge.text(t).show();
        $headUnread.text(t + " unread").show();
        $btn.attr("title", t + " unread notifications");
      } else {
        $badge.hide();
        $headUnread.hide();
        $btn.attr("title", "No unread notifications");
      }
    }

    function closePanel() {
      $panel.removeClass("sl-open");
      $btn.attr("aria-expanded", "false");
    }

    function openPanel() {
      $panel.addClass("sl-open");
      $btn.attr("aria-expanded", "true");
    }

    $btn.on("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      if ($panel.hasClass("sl-open")) closePanel();
      else openPanel();
    });

    $(document).on("click.slAdminNotif", function () {
      closePanel();
    });
    $li.on("click", function (e) {
      e.stopPropagation();
    });
    $(document).on("keydown.slAdminNotif", function (e) {
      if (e.key === "Escape") closePanel();
    });

    fetch("/_staff-notif-badge/", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    })
      .then(function (r) {
        if (r.status === 403 || r.status === 401) {
          $li.remove();
          return null;
        }
        if (!r.ok) throw new Error("badge");
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        var unread = Number(data.unread || 0);
        renderUnreadBadge(unread);

        $("#slAdminNotifAllAdmin").attr("href", data.admin_changelist || "#");

        $scroll.empty();
        var rows = data.preview || [];
        if (!rows.length) {
          $scroll.append(
            '<div class="p-4 text-center text-muted small">No notifications yet.</div>'
          );
          return;
        }
        rows.forEach(function (n) {
          var href = escapeHtml(n.mark_read_url || n.change_url || "#");
          var title = escapeHtml(n.title || "");
          var body = escapeHtml((n.body || "").slice(0, 160));
          var kind = escapeHtml(n.kind || "");
          var who = escapeHtml(n.username || "");
          var unreadClass = n.unread ? " sl-admin-notif-row-unread" : "";
          var unreadDot = n.unread ? '<span class="sl-admin-notif-dot" title="Unread"></span>' : "";
          var when = escapeHtml(n.created_at || "");
          var tooltip = escapeAttr(title + (who ? " - " + who : ""));
          var row =
            '<a class="sl-admin-notif-row' + unreadClass + '" href="' +
            href +
            '" title="' + tooltip + '">' +
            '<span class="sl-admin-notif-title-wrap">' + unreadDot + '<span class="sl-admin-notif-title">' + title + "</span></span>" +
            (body ? '<small class="sl-admin-notif-body">' + body + "</small>" : "") +
            '<small class="sl-admin-notif-meta">' +
            (kind ? '<span class="sl-admin-notif-kind">' + kind + "</span>" : "") +
            (who ? '<span class="sl-admin-notif-user">@' + who + "</span>" : "") +
            '<span class="sl-admin-notif-time">' + when + "</span>" +
            "</small></a>";
          $scroll.append(row);
        });
        $scroll.off("click.slMarkRead").on("click.slMarkRead", ".sl-admin-notif-row", function () {
          var $row = $(this);
          if (!$row.hasClass("sl-admin-notif-row-unread")) return;
          $row.removeClass("sl-admin-notif-row-unread");
          $row.find(".sl-admin-notif-dot").remove();
          unread = Math.max(0, unread - 1);
          renderUnreadBadge(unread);
        });
      })
      .catch(function () {
        $li.remove();
      });
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

    if ($defaultUser.length) {
      $defaultUser.show();
    }

    var roleLabel = detectRoleLabel(username);
    var $sidebarUser = $("#jazzy-sidebar .user-panel .info a").first();
    if ($sidebarUser.length) {
      $sidebarUser.text(roleLabel);
      $sidebarUser.attr("title", "Përdoruesi: " + (username || "—"));
    }

    injectAdminNotificationBell();
    window.setTimeout(injectAdminNotificationBell, 260);
    window.setTimeout(injectAdminNotificationBell, 900);
  });
})(jQuery);
