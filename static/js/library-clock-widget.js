(function () {
  "use strict";

  var root = document.querySelector(".sl-lib-clock");
  if (!root) return;

  var OPEN_H = parseInt(root.dataset.openHour || "8", 10);
  var CLOSE_H = parseInt(root.dataset.closeHour || "19", 10);
  var holidays = [];
  try {
    var holidaysEl = document.getElementById("sl-lcw-holidays-data");
    holidays = holidaysEl ? JSON.parse(holidaysEl.textContent) : [];
  } catch (e) {
    holidays = [];
  }

  var MONTHS_SQ = [
    "Janar", "Shkurt", "Mars", "Prill", "Maj", "Qershor",
    "Korrik", "Gusht", "Shtator", "Tetor", "Nëntor", "Dhjetor",
  ];
  var DAYS_DATA = [
    { name: "E Hënë", jsDay: 1, open: true, hours: "08:00 – 19:00" },
    { name: "E Martë", jsDay: 2, open: true, hours: "08:00 – 19:00" },
    { name: "E Mërkurë", jsDay: 3, open: true, hours: "08:00 – 19:00" },
    { name: "E Enjte", jsDay: 4, open: true, hours: "08:00 – 19:00" },
    { name: "E Premte", jsDay: 5, open: true, hours: "08:00 – 19:00" },
    { name: "E Shtunë", jsDay: 6, open: false, hours: "Mbyllur" },
    { name: "E Diel", jsDay: 0, open: false, hours: "Mbyllur" },
  ];

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function isHoliday(date) {
    var m = date.getMonth() + 1;
    var d = date.getDate();
    for (var i = 0; i < holidays.length; i++) {
      if (holidays[i][0] === m && holidays[i][1] === d) return true;
    }
    return false;
  }

  function isWeekend(date) {
    var wd = date.getDay();
    return wd === 0 || wd === 6;
  }

  function isClosedDay(date) {
    return isWeekend(date) || isHoliday(date);
  }

  function isOpenNow(now) {
    if (isClosedDay(now)) return false;
    var mins = now.getHours() * 60 + now.getMinutes();
    return mins >= OPEN_H * 60 && mins < CLOSE_H * 60;
  }

  function dayProgress(now) {
    if (isClosedDay(now)) return 0;
    var total = (CLOSE_H - OPEN_H) * 60;
    var elapsed = (now.getHours() - OPEN_H) * 60 + now.getMinutes() + now.getSeconds() / 60;
    if (elapsed < 0) return 0;
    return Math.min(100, (elapsed / total) * 100);
  }

  function timeLeft(now) {
    var rem = CLOSE_H * 60 - (now.getHours() * 60 + now.getMinutes());
    if (rem <= 0) return null;
    var rh = Math.floor(rem / 60);
    var rm = rem % 60;
    return rh > 0 ? rh + "h " + rm + "min deri në mbyllje" : rm + " min deri në mbyllje";
  }

  function timeToOpen(now) {
    var minsSoFar = now.getHours() * 60 + now.getMinutes();
    var rem = OPEN_H * 60 - minsSoFar;
    if (rem <= 0) return null;
    var rh = Math.floor(rem / 60);
    var rm = rem % 60;
    return rh > 0 ? "Hapet pas " + rh + "h " + rm + "min" : "Hapet pas " + rm + " minutash";
  }

  function rotHand(id, deg, cx, cy, len, tailLen) {
    var el = root.querySelector("#" + id);
    if (!el) return;
    var r = (deg * Math.PI) / 180;
    el.setAttribute("x1", cx - tailLen * Math.sin(r));
    el.setAttribute("y1", cy + tailLen * Math.cos(r));
    el.setAttribute("x2", cx + len * Math.sin(r));
    el.setAttribute("y2", cy - len * Math.cos(r));
  }

  function drawHourMarks() {
    var g = root.querySelector("#sl-lcw-hour-marks");
    if (!g || g.childNodes.length) return;
    for (var i = 0; i < 12; i++) {
      var angle = (i * 30 * Math.PI) / 180;
      var r1 = 61;
      var r2 = i % 3 === 0 ? 52 : 57;
      var x1 = 70 + r1 * Math.sin(angle);
      var y1 = 70 - r1 * Math.cos(angle);
      var x2 = 70 + r2 * Math.sin(angle);
      var y2 = 70 - r2 * Math.cos(angle);
      var line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", x1);
      line.setAttribute("y1", y1);
      line.setAttribute("x2", x2);
      line.setAttribute("y2", y2);
      line.setAttribute("stroke", i % 3 === 0 ? "rgba(201,168,76,.9)" : "rgba(255,255,255,.35)");
      line.setAttribute("stroke-width", i % 3 === 0 ? "2" : "1");
      line.setAttribute("stroke-linecap", "round");
      g.appendChild(line);
    }
  }

  function renderWeekGrid() {
    var grid = root.querySelector("#sl-lcw-week-grid");
    if (!grid) return;
    var now = new Date();
    var todayJs = now.getDay();
    var hol = isHoliday(now);
    grid.innerHTML = DAYS_DATA.map(function (d) {
      var isToday = d.jsDay === todayJs;
      var isTodayClosed = isToday && (!d.open || hol);
      var shortName = d.name.replace("E ", "");
      var hours = isTodayClosed && d.open ? "Mbyllur (pushim)" : d.hours;
      var cardClass = "sl-lcw-day-card " + (d.open && !(isToday && hol) ? "sl-lcw-open" : "sl-lcw-closed-day");
      if (isToday) cardClass += " sl-lcw-today-card";
      return (
        '<div class="' + cardClass + '">' +
        '<div class="sl-lcw-dc-name">' + shortName + "</div>" +
        '<div class="sl-lcw-dc-hours">' + hours + "</div>" +
        (isToday ? '<div class="sl-lcw-today-badge">SOT</div>' : "") +
        "</div>"
      );
    }).join("");
  }

  function tick() {
    var now = new Date();
    var h = now.getHours();
    var m = now.getMinutes();
    var s = now.getSeconds();
    var wknd = isWeekend(now);
    var hol = isHoliday(now);
    var closed = wknd || hol;
    var open = isOpenNow(now);

    rotHand("sl-lcw-h-hour", (h % 12) * 30 + m * 0.5 + s / 120, 70, 70, 36, 0);
    rotHand("sl-lcw-h-min", m * 6 + s * 0.1, 70, 70, 50, 0);
    rotHand("sl-lcw-h-sec", s * 6, 70, 70, 52, 8);

    var digital = root.querySelector("#sl-lcw-digital-time");
    if (digital) {
      digital.textContent = pad(h) + ":" + pad(m) + ":" + pad(s);
    }
    var dateLine = root.querySelector("#sl-lcw-date-line");
    if (dateLine) {
      var DAYS_SQ = ["E Diel", "E Hënë", "E Martë", "E Mërkurë", "E Enjte", "E Premte", "E Shtunë"];
      dateLine.textContent =
        DAYS_SQ[now.getDay()] + ", " + now.getDate() + " " + MONTHS_SQ[now.getMonth()] + " " + now.getFullYear();
    }

    var fill = root.querySelector("#sl-lcw-prog-fill");
    var pstat = root.querySelector("#sl-lcw-prog-status");
    var ptxt = root.querySelector("#sl-lcw-prog-status-text");
    var prog = root.querySelector("#sl-lcw-prog-title");

    if (!fill || !pstat || !ptxt || !prog) return;

    if (closed) {
      fill.style.width = "0%";
      pstat.className = "sl-lcw-prog-status sl-lcw-prog-closed";
      ptxt.textContent = wknd
        ? "Biblioteka është e mbyllur sot — fundjavë."
        : "Pushim zyrtar — biblioteka e mbyllur (" + now.getDate() + " " + MONTHS_SQ[now.getMonth()] + ").";
      prog.textContent = "Progresi i ditës";
    } else {
      var p = dayProgress(now);
      fill.style.width = p + "%";
      prog.textContent = "Progresi i ditës punës";
      if (open) {
        var tl = timeLeft(now);
        pstat.className = "sl-lcw-prog-status sl-lcw-prog-open";
        ptxt.textContent = "Biblioteka është e hapur tani" + (tl ? " — " + tl : "");
      } else if (p >= 100) {
        pstat.className = "sl-lcw-prog-status sl-lcw-prog-closed";
        ptxt.textContent = "Biblioteka u mbyll sot në " + pad(CLOSE_H) + ":00";
      } else {
        var tt = timeToOpen(now);
        pstat.className = "sl-lcw-prog-status sl-lcw-prog-before";
        ptxt.textContent = tt || "Hapet në " + pad(OPEN_H) + ":00";
      }
    }
  }

  drawHourMarks();
  renderWeekGrid();
  tick();
  setInterval(tick, 1000);
  setInterval(renderWeekGrid, 60000);
})();
