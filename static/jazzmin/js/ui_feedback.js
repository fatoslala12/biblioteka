(function () {
  function normalizeMessage(raw) {
    const text = (raw || "").toString().trim();
    if (!text) return "Ndodhi një problem i papritur. Ju lutem provoni përsëri.";

    const map = [
      [/method not allowed/i, "Kjo veprimtari nuk lejohet nga sistemi."],
      [/gabim gjatë verifikimit/i, "Nuk u verifikuan dot të dhënat. Kontrolloni fushat dhe provoni përsëri."],
      [/gabim i papritur/i, "Ndodhi një problem i përkohshëm. Provoni përsëri pas pak."],
      [/nuk u gjet/i, "Të dhënat që kërkuat nuk u gjetën. Kontrolloni informacionin dhe provoni përsëri."],
      [/nuk u krijua/i, "Nuk u ruajt veprimi. Kontrolloni fushat dhe provoni përsëri."],
      [/nuk u ruajt/i, "Nuk u ruajt veprimi. Kontrolloni fushat dhe provoni përsëri."],
      [/nuk u huazua/i, "Huazimi nuk u krye. Kontrolloni gjendjen e kopjeve dhe datat."],
      [/s’ka kopje|s'ka kopje/i, "Nuk ka kopje të lira për këtë titull në këtë moment."],
      [/titulli është i zënë/i, "Titulli është i zënë për datat e zgjedhura."],
    ];
    for (let i = 0; i < map.length; i += 1) {
      if (map[i][0].test(text)) return map[i][1];
    }
    return text;
  }

  function titleFor(type) {
    if (type === "success") return "U krye me sukses";
    if (type === "warning") return "Kujdes";
    if (type === "danger") return "Veprimi nuk u krye";
    return "Njoftim";
  }

  function iconFor(type) {
    if (type === "success") return "✓";
    if (type === "warning") return "!";
    if (type === "danger") return "✕";
    return "i";
  }

  function show(alertEl, type, message) {
    if (!alertEl) return;
    const safeType = type || "info";
    const text = normalizeMessage(message);
    alertEl.style.display = "block";
    alertEl.className = "alert alert-" + safeType;
    alertEl.innerHTML =
      '<div style="display:flex;align-items:flex-start;gap:10px;">' +
      '<span style="display:inline-flex;width:24px;height:24px;border-radius:999px;align-items:center;justify-content:center;font-weight:900;background:rgba(255,255,255,.55);">' +
      iconFor(safeType) +
      "</span>" +
      '<div><div style="font-weight:900;line-height:1.2;">' +
      titleFor(safeType) +
      '</div><div style="font-weight:700;line-height:1.35;">' +
      text +
      "</div></div></div>";
  }

  function hide(alertEl) {
    if (!alertEl) return;
    alertEl.style.display = "none";
  }

  window.SLFeedback = {
    show: show,
    hide: hide,
    normalizeMessage: normalizeMessage,
  };
})();
