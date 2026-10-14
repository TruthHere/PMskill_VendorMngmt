/* Fill a client payment xlsx from template-profile (engine=cells).
 * ZIP-patches cell values; does not rewrite layout.
 */
(function (root) {
  function xmlEscape(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&apos;");
  }

  function keepStyle(attrs) {
    const m = String(attrs || "").match(/\bs="(\d+)"/);
    return m ? ' s="' + m[1] + '"' : "";
  }

  function replaceCell(sheet, addr, inner, extraAttrs) {
    const re = new RegExp('(<c r="' + addr + '")([^>]*?)(?:/>|>[\\s\\S]*?</c>)');
    if (!re.test(sheet)) return null;
    return sheet.replace(re, function (_, open, attrs) {
      return open + keepStyle(attrs) + (extraAttrs || "") + ">" + inner + "</c>";
    });
  }

  function insertCell(sheet, addr, inner, extraAttrs) {
    const m = String(addr).match(/^([A-Z]+)(\d+)$/);
    if (!m) throw new Error("坏格子 " + addr);
    const row = m[2];
    const rowRe = new RegExp('(<row r="' + row + '"[^>]*>)([\\s\\S]*?)(</row>)');
    const hit = sheet.match(rowRe);
    if (!hit) throw new Error("模板缺少第 " + row + " 行（格子 " + addr + "）");
    if (hit[2].indexOf('r="' + addr + '"') !== -1) return sheet;
    const cell = "<c r=\"" + addr + "\"" + (extraAttrs || "") + ">" + inner + "</c>";
    return sheet.replace(rowRe, hit[1] + hit[2] + cell + hit[3]);
  }

  function setText(sheet, addr, value) {
    const inner = '<is><t xml:space="preserve">' + xmlEscape(value) + "</t></is>";
    return replaceCell(sheet, addr, inner, ' t="inlineStr"') || insertCell(sheet, addr, inner, ' t="inlineStr"');
  }

  function setNumber(sheet, addr, value) {
    const n = Number(value);
    const raw = Number.isInteger(n) ? String(n) : String(n);
    const inner = "<v>" + raw + "</v>";
    return replaceCell(sheet, addr, inner) || insertCell(sheet, addr, inner);
  }

  function clearCell(sheet, addr) {
    const re = new RegExp('(<c r="' + addr + '")([^>]*?)(?:/>|>[\\s\\S]*?</c>)');
    if (!re.test(sheet)) return sheet;
    return sheet.replace(re, function (_, open, attrs) {
      return open + keepStyle(attrs) + "/>";
    });
  }

  function money(v) {
    if (v === null || v === undefined || v === "") return null;
    if (typeof v === "number" && Number.isFinite(v)) return v;
    const n = Number(String(v).replace(/[,¥￥\s]|CNY|RMB/g, ""));
    return Number.isFinite(n) ? n : null;
  }

  function payloadValue(p, spec) {
    const raw = p[spec.from];
    if (raw === null || raw === undefined || raw === "") return null;
    if (spec.format) return String(spec.format).replace("{value}", String(raw));
    return raw;
  }

  function writeCell(sheet, addr, kind, value) {
    if (value === null || value === undefined || value === "") return clearCell(sheet, addr);
    if (kind === "money") {
      const n = money(value);
      return n == null ? clearCell(sheet, addr) : setNumber(sheet, addr, n);
    }
    if (kind === "number") return setNumber(sheet, addr, value);
    if (kind === "auto") {
      const code = String(value).trim();
      if (!code) return clearCell(sheet, addr);
      if (/^-?\d+(\.\d+)?$/.test(code)) return setNumber(sheet, addr, Number(code));
      return setText(sheet, addr, code);
    }
    return setText(sheet, addr, String(value));
  }

  function applyProfile(sheet, p, profile) {
    (profile.writes || []).forEach(function (spec) {
      if (!spec || !spec.cell) return;
      sheet = writeCell(sheet, spec.cell, spec.type || "text", payloadValue(p, spec));
    });
    const vat = profile.vat || {};
    const pct = p[vat.from || "vat_note_pct"];
    const fmt = vat.format || "(CNY exclude {value}% VAT)";
    (vat.cells || []).forEach(function (addr) {
      if (pct == null || pct === "") sheet = clearCell(sheet, addr);
      else sheet = setText(sheet, addr, String(fmt).replace("{value}", String(pct)));
    });
    const prevCell = (profile.previously_certified || {}).cell;
    if (prevCell) {
      let sum = 0;
      const currentNo = Number(p.payment_no) || 1;
      (p.previous_claims || []).forEach(function (c) {
        if (!c) return;
        const pn = Number(c.payment_no) || 0;
        if (pn && pn >= currentNo) return;
        if (!pn && currentNo <= 1) return;
        const amt = money(c.amount);
        if (amt != null) sum += amt;
      });
      sheet = setNumber(sheet, prevCell, sum);
    }
    const claim = profile.claim_amount || {};
    if (claim.name_cell) {
      const name = String(p.claim_node || "").trim();
      sheet = name ? setText(sheet, claim.name_cell, name) : clearCell(sheet, claim.name_cell);
    }
    const claimAmt = claimMoney(p, profile);
    if (claim.amount_cell) {
      sheet = claimAmt == null ? clearCell(sheet, claim.amount_cell) : setNumber(sheet, claim.amount_cell, claimAmt);
    }
    const extraAmountCells = claim.amount_cells || [];
    extraAmountCells.forEach(function (addr) {
      if (!addr || addr === claim.amount_cell) return;
      sheet = claimAmt == null ? clearCell(sheet, addr) : setNumber(sheet, addr, claimAmt);
    });
    const fileCells = profile.support_file_cells || [];
    const lines = Array.isArray(p.support_file_lines) ? p.support_file_lines : [];
    fileCells.forEach(function (addr, i) {
      const text = String(lines[i] || "").trim();
      sheet = text ? setText(sheet, addr, text) : clearCell(sheet, addr);
    });
    const totals = profile.running_totals || {};
    const prev = previousSum(p);
    const certified = totals.includes_this_claim ? prev + (claimAmt || 0) : prev;
    if (totals.certified_to_date_cell) sheet = setNumber(sheet, totals.certified_to_date_cell, certified);
    if (totals.remaining_cell) {
      const contract = money(p[totals.contract_from || "contract_value_excl_tax"]);
      if (contract == null) sheet = clearCell(sheet, totals.remaining_cell);
      else sheet = setNumber(sheet, totals.remaining_cell, contract - certified);
    }
    return sheet;
  }

  function amountTax(profile) {
    const raw = String((profile && profile.amount_tax) || ((profile && profile.form) || {}).amount_tax || "excl").toLowerCase();
    return raw === "incl" || raw === "incl_tax" || raw === "含税" ? "incl" : "excl";
  }

  function claimMoney(p, profile) {
    if (amountTax(profile) === "incl") return money(p.claim_amount_incl_tax != null ? p.claim_amount_incl_tax : p.claim_amount);
    return money(p.claim_amount_excl_tax != null ? p.claim_amount_excl_tax : p.claim_amount);
  }

  function previousSum(p) {
    let sum = 0;
    const currentNo = Number(p.payment_no) || 1;
    (p.previous_claims || []).forEach(function (c) {
      if (!c) return;
      const pn = Number(c.payment_no) || 0;
      if (pn && pn >= currentNo) return;
      if (!pn && currentNo <= 1) return;
      const amt = money(c.amount);
      if (amt != null) sum += amt;
    });
    return sum;
  }

  function localName(tag) {
    const m = String(tag).match(/}([^}]+)$/);
    return m ? m[1] : tag;
  }

  async function fillXlsxFromProfile(templateBytes, payload, profile) {
    if (typeof JSZip === "undefined") {
      throw new Error("缺少 JSZip（.claim-assets/jszip.min.js）");
    }
    profile = profile || {};
    const zip = await JSZip.loadAsync(templateBytes);
    const wbFile = zip.file("xl/workbook.xml");
    const relsFile = zip.file("xl/_rels/workbook.xml.rels");
    if (!wbFile || !relsFile) throw new Error("模板不是可填的 Excel");
    let workbook = await wbFile.async("string");
    let rels = await relsFile.async("string");

    const ridToTarget = {};
    rels.replace(/<Relationship\b([^>]*)\/>/g, function (whole, attrs) {
      const id = (attrs.match(/\bId="([^"]+)"/) || [])[1];
      const target = (attrs.match(/\bTarget="([^"]+)"/) || [])[1];
      if (id) ridToTarget[id] = target;
      return whole;
    });

    const dropNames = {};
    (profile.drop_sheets || []).forEach(function (n) { dropNames[n] = true; });
    const sheets = [];
    workbook.replace(/<sheet\b([^>]*)\/>/g, function (whole, attrs) {
      const name = (attrs.match(/\bname="([^"]+)"/) || [])[1] || "";
      const rid = (attrs.match(/\br:id="([^"]+)"/) || attrs.match(/\bid="([^"]+)"/) || [])[1];
      const target = (ridToTarget[rid] || "").replace(/\\/g, "/");
      const part = target.charAt(0) === "/" ? target.slice(1) : "xl/" + target.replace(/^\//, "");
      sheets.push({ name: name, rid: rid, part: part });
      return whole;
    });

    sheets.forEach(function (sh) {
      if (!dropNames[sh.name]) return;
      workbook = workbook.replace(new RegExp('<sheet name="' + sh.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + '"[^/]*\\/>'), "");
      rels = rels.replace(new RegExp('<Relationship Id="' + sh.rid + '"[^/]*\\/>'), "");
      zip.remove(sh.part);
      const relPart = sh.part.replace(/\/([^/]+)$/, "/_rels/$1.rels");
      zip.remove(relPart);
    });

    zip.file("xl/workbook.xml", workbook);
    zip.file("xl/_rels/workbook.xml.rels", rels);

    let invoicePart = null;
    if (profile.invoice_sheet) {
      sheets.forEach(function (sh) {
        if (sh.name === profile.invoice_sheet && !dropNames[sh.name]) invoicePart = sh.part;
      });
    }
    if (!invoicePart) {
      sheets.forEach(function (sh) {
        if (!invoicePart && !dropNames[sh.name]) invoicePart = sh.part;
      });
    }
    if (!invoicePart || !zip.file(invoicePart)) throw new Error("模板缺少要填的工作表");
    let sheet = await zip.file(invoicePart).async("string");
    sheet = applyProfile(sheet, payload, profile);
    zip.file(invoicePart, sheet);

    const ctypes = zip.file("[Content_Types].xml");
    if (ctypes) {
      let xml = await ctypes.async("string");
      sheets.forEach(function (sh) {
        if (!dropNames[sh.name]) return;
        const part = sh.part.charAt(0) === "/" ? sh.part : "/" + sh.part;
        xml = xml.replace(new RegExp('<Override PartName="' + part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + '"[^/]*\\/>'), "");
      });
      zip.file("[Content_Types].xml", xml);
    }

    return zip.generateAsync({
      type: "blob",
      mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      compression: "DEFLATE"
    });
  }

  root.fillXlsxFromProfile = fillXlsxFromProfile;
})(typeof window !== "undefined" ? window : this);
