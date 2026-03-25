(function () {
  function markIncidentRows() {
    var rows = document.querySelectorAll(".app-audit.model-auditentry.change-list #result_list tbody tr");
    rows.forEach(function (row) {
      var incidentBadge = row.querySelector(".sl-audit-badge-incident");
      if (incidentBadge) {
        row.classList.add("sl-audit-row-incident");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", markIncidentRows);
  } else {
    markIncidentRows();
  }
})();
