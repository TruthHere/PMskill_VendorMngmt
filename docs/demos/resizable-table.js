(function () {
  function ensureColgroup(table, widths) {
    let colgroup = table.querySelector("colgroup");
    if (!colgroup) {
      colgroup = document.createElement("colgroup");
      table.insertBefore(colgroup, table.firstChild);
    }
    colgroup.replaceChildren();
    widths.forEach((w) => {
      const col = document.createElement("col");
      col.style.width = w + "px";
      colgroup.appendChild(col);
    });
    return colgroup;
  }

  function colWidth(cols, index, th) {
    const parsed = parseFloat(cols[index].style.width);
    if (!Number.isNaN(parsed) && parsed > 0) return parsed;
    return th.getBoundingClientRect().width;
  }

  function setColWidth(table, cols, index, width) {
    const next = Math.max(48, Math.round(width));
    cols[index].style.width = next + "px";
    table.style.width = Array.from(cols).reduce((sum, col) => {
      const w = parseFloat(col.style.width);
      return sum + (Number.isNaN(w) ? 80 : w);
    }, 0) + "px";
    return next;
  }

  function initResizableTable(table) {
    const raw = table.getAttribute("data-col-widths");
    if (!raw) return;
    const widths = raw.split(",").map((n) => Math.max(48, parseInt(n.trim(), 10) || 80));
    const colgroup = ensureColgroup(table, widths);
    const cols = colgroup.querySelectorAll("col");
    const headerRow = table.querySelector(".head-row");
    if (!headerRow) return;

    table.style.width = widths.reduce((sum, w) => sum + w, 0) + "px";

    headerRow.querySelectorAll("th").forEach((th, i) => {
      if (i >= cols.length || th.querySelector(".col-resizer")) return;
      const grip = document.createElement("span");
      grip.className = "col-resizer";
      grip.title = "拖动调节列宽";
      th.appendChild(grip);

      const startDrag = (e) => {
        if (e.button !== undefined && e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();

        const startX = e.clientX;
        const startW = colWidth(cols, i, th);
        grip.classList.add("is-active");
        document.body.classList.add("col-resizing");

        if (grip.setPointerCapture && e.pointerId !== undefined) {
          try { grip.setPointerCapture(e.pointerId); } catch (_) {}
        }

        const onMove = (ev) => {
          ev.preventDefault();
          setColWidth(table, cols, i, startW + ev.clientX - startX);
        };

        const onUp = (ev) => {
          grip.classList.remove("is-active");
          document.body.classList.remove("col-resizing");
          grip.removeEventListener("pointermove", onMove);
          grip.removeEventListener("pointerup", onUp);
          grip.removeEventListener("pointercancel", onUp);
          document.removeEventListener("pointermove", onMove);
          document.removeEventListener("pointerup", onUp);
          if (grip.releasePointerCapture && ev.pointerId !== undefined) {
            try { grip.releasePointerCapture(ev.pointerId); } catch (_) {}
          }
        };

        grip.addEventListener("pointermove", onMove);
        grip.addEventListener("pointerup", onUp);
        grip.addEventListener("pointercancel", onUp);
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
      };

      grip.addEventListener("pointerdown", startDrag);
    });
  }

  document.querySelectorAll("table[data-col-widths]").forEach(initResizableTable);
})();
