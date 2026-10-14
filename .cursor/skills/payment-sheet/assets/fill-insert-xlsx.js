/* Fill a payment xlsx that inserts previous-claim rows; does not rewrite layout.
 * Loads the project xlsx ZIP, patches Invoice cell values, drops extra sheet 2 if present.
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
    if (!re.test(sheet)) throw new Error("模板缺少格子 " + addr);
    return sheet.replace(re, function (_, open, attrs) {
      return open + keepStyle(attrs) + (extraAttrs || "") + ">" + inner + "</c>";
    });
  }

  function setText(sheet, addr, value) {
    const inner = '<is><t xml:space="preserve">' + xmlEscape(value) + "</t></is>";
    return replaceCell(sheet, addr, inner, ' t="inlineStr"');
  }

  function setNumber(sheet, addr, value) {
    const n = Number(value);
    const raw = Number.isInteger(n) ? String(n) : String(n);
    return replaceCell(sheet, addr, "<v>" + raw + "</v>");
  }

  function clearCell(sheet, addr) {
    const re = new RegExp('(<c r="' + addr + '")([^>]*?)(?:/>|>[\\s\\S]*?</c>)');
    if (!re.test(sheet)) throw new Error("模板缺少格子 " + addr);
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

  function previousLines(p) {
    const currentNo = Number(p.payment_no) || 1;
    const lines = [];
    (p.previous_claims || []).forEach(function (c) {
      if (!c || typeof c !== "object") return;
      const amt = money(c.amount);
      if (amt == null) return;
      const pn = Number(c.payment_no) || 0;
      if (pn && pn >= currentNo) return;
      if (!pn && currentNo <= 1) return;
      const name = String(c.name || "Previously certified").trim() || "Previously certified";
      lines.push({ name: name, amount: amt });
    });
    return lines;
  }

  function shiftRowNum(n, fromRow, delta) {
    return n >= fromRow ? n + delta : n;
  }

  function shiftSheet(xml, fromRow, delta) {
    if (delta <= 0) return xml;
    xml = xml.replace(/<row r="(\d+)"/g, function (_, n) {
      return '<row r="' + shiftRowNum(Number(n), fromRow, delta) + '"';
    });
    xml = xml.replace(/<c r="([A-Z]+)(\d+)"/g, function (_, col, n) {
      return '<c r="' + col + shiftRowNum(Number(n), fromRow, delta) + '"';
    });
    xml = xml.replace(/<mergeCell ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"/g, function (_, a, r1, b, r2) {
      return (
        '<mergeCell ref="' +
        a +
        shiftRowNum(Number(r1), fromRow, delta) +
        ":" +
        b +
        shiftRowNum(Number(r2), fromRow, delta) +
        '"'
      );
    });
    xml = xml.replace(/<f>([^<]*)<\/f>/g, function (_, inner) {
      const shifted = inner.replace(/([A-Z]+)(\d+)/g, function (__, col, n) {
        return col + shiftRowNum(Number(n), fromRow, delta);
      });
      return "<f>" + shifted + "</f>";
    });
    xml = xml.replace(/<dimension ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"/g, function (_, a, r1, b, r2) {
      return (
        '<dimension ref="' +
        a +
        r1 +
        ":" +
        b +
        shiftRowNum(Number(r2), fromRow, delta) +
        '"'
      );
    });
    return xml;
  }

  function shiftCalc(xml, fromRow, delta) {
    if (delta <= 0) return xml;
    return xml.replace(/<c r="([A-Z]+)(\d+)"/g, function (_, col, n) {
      return '<c r="' + col + shiftRowNum(Number(n), fromRow, delta) + '"';
    });
  }

  function retargetRow(rowXml, oldR, newR) {
    rowXml = rowXml.replace(new RegExp('<row r="' + oldR + '"'), '<row r="' + newR + '"');
    return rowXml.replace(new RegExp(' r="([A-Z]+)' + oldR + '"', "g"), function (_, col) {
      return ' r="' + col + newR + '"';
    });
  }

  function insertPreviousRows(sheet, extra) {
    if (extra <= 0) return sheet;
    const re36 = /<row r="36"[^>]*>[\s\S]*?<\/row>/;
    const m = sheet.match(re36);
    if (!m) throw new Error("template missing row 36");
    const template = m[0];
    sheet = shiftSheet(sheet, 37, extra);
    let extras = "";
    for (let i = 0; i < extra; i++) extras += retargetRow(template, 36, 37 + i);
    const anchor = sheet.match(re36);
    if (!anchor) throw new Error("row 36 missing after shift");
    const at = sheet.indexOf(anchor[0]) + anchor[0].length;
    return sheet.slice(0, at) + extras + sheet.slice(at);
  }

  function ensureMerge(sheet, ref) {
    if (sheet.indexOf('<mergeCell ref="' + ref + '"/>') !== -1) return sheet;
    const m = sheet.match(/<mergeCells count="(\d+)">/);
    if (!m) throw new Error("template missing mergeCells");
    const n = Number(m[1]) + 1;
    sheet = sheet.replace(m[0], '<mergeCells count="' + n + '">');
    return sheet.replace("</mergeCells>", '<mergeCell ref="' + ref + '"/></mergeCells>');
  }

  function applyPayload(sheet, p) {
    const paymentNo = Number(p.payment_no) || 1;
    sheet = setText(sheet, "B1", "PAYMENT NO: " + paymentNo);
    sheet = setNumber(sheet, "Q19", paymentNo);

    const period = Number(p.period_count);
    if (Number.isFinite(period) && period > 0) sheet = setNumber(sheet, "P23", period);

    function text(addr, val) {
      const s = val == null ? "" : String(val).trim();
      sheet = s ? setText(sheet, addr, s) : clearCell(sheet, addr);
    }

    text("C2", p.project_name);
    text("C3", p.division);
    text("C4", p.vendor_name);
    text("C11", p.vendor_name);
    text("C5", p.work_package);
    text("C6", p.vendor_ref);
    text("C7", p.po_number);
    text("C12", p.contact_name);
    text("C13", p.contact_mobile);
    text("C14", p.office_phone);
    text("K12", p.office_address);
    text("C19", p.billing_entity);
    text("B22", p.nodes_overview);

    if (p.vat_note_pct == null || p.vat_note_pct === "") {
      sheet = clearCell(sheet, "D8");
      sheet = clearCell(sheet, "D9");
    } else {
      const note = "(CNY exclude " + p.vat_note_pct + "% VAT)";
      sheet = setText(sheet, "D8", note);
      sheet = setText(sheet, "D9", note);
    }

    const code = String(p.division_code || "").trim();
    if (!code) sheet = clearCell(sheet, "B19");
    else if (/^-?\d+(\.\d+)?$/.test(code)) sheet = setNumber(sheet, "B19", Number(code));
    else text("B19", code);

    let poVal = money(p.po_value_excl_tax);
    let contractVal = money(p.contract_value_excl_tax);
    if (poVal == null) poVal = contractVal;
    if (contractVal == null) contractVal = poVal;
    sheet = poVal == null ? clearCell(sheet, "C8") : setNumber(sheet, "C8", poVal);
    sheet = contractVal == null ? clearCell(sheet, "C9") : setNumber(sheet, "C9", contractVal);

    const variations = money(p.variations_to_date);
    sheet = setNumber(sheet, "I30", variations == null ? 0 : variations);

    const prevLines = previousLines(p);
    const extra = Math.max(0, prevLines.length - 1);
    sheet = insertPreviousRows(sheet, extra);
    const currentRow = 37 + extra;
    let prevSum = 0;
    prevLines.forEach(function (line, i) {
      const row = 36 + i;
      sheet = setText(sheet, "B" + row, line.name);
      sheet = setNumber(sheet, "Q" + row, line.amount);
      prevSum += line.amount;
    });

    const claimName = String(p.claim_node || "").trim();
    const claimAmt = money(p.claim_amount_excl_tax);
    sheet = claimName ? setText(sheet, "B" + currentRow, claimName) : clearCell(sheet, "B" + currentRow);
    sheet = claimAmt == null ? clearCell(sheet, "Q" + currentRow) : setNumber(sheet, "Q" + currentRow, claimAmt);

    sheet = setNumber(sheet, "Q" + (41 + extra), prevSum);
    prevLines.forEach(function (_, i) {
      sheet = ensureMerge(sheet, "B" + (36 + i) + ":M" + (36 + i));
    });
    return { sheet: sheet, extra: extra };
  }

  function stripSheet2Workbook(xml) {
    return xml.replace(/<sheet name="Advance Payment Schedule"[^/]*\/>/, "");
  }

  function stripSheet2Rels(xml) {
    return xml.replace(
      /<Relationship Id="rId2" Type="http:\/\/schemas.openxmlformats.org\/officeDocument\/2006\/relationships\/worksheet" Target="worksheets\/sheet2.xml"\/>/,
      ""
    );
  }

  function stripSheet2Ctypes(xml) {
    return xml.replace(/<Override PartName="\/xl\/worksheets\/sheet2.xml"[^/]*\/>/, "");
  }

  function stripSheet2Calc(xml) {
    return xml.replace(/<c r="[^"]+" i="4"[^/]*\/>/g, "");
  }

  async function fillInsertRowsXlsx(templateBytes, payload) {
    if (typeof JSZip === "undefined") {
      throw new Error("缺少 JSZip（.claim-assets/jszip.min.js）");
    }
    const zip = await JSZip.loadAsync(templateBytes);
    const sheetPath = "xl/worksheets/sheet1.xml";
    if (!zip.file(sheetPath)) throw new Error("模板缺少 Invoice 工作表");
    let sheet = await zip.file(sheetPath).async("string");
    const patched = applyPayload(sheet, payload);
    zip.file(sheetPath, patched.sheet);

    const wb = zip.file("xl/workbook.xml");
    if (wb) zip.file("xl/workbook.xml", stripSheet2Workbook(await wb.async("string")));
    const rels = zip.file("xl/_rels/workbook.xml.rels");
    if (rels) zip.file("xl/_rels/workbook.xml.rels", stripSheet2Rels(await rels.async("string")));
    const ctypes = zip.file("[Content_Types].xml");
    if (ctypes) zip.file("[Content_Types].xml", stripSheet2Ctypes(await ctypes.async("string")));
    const calc = zip.file("xl/calcChain.xml");
    if (calc) {
      let calcXml = stripSheet2Calc(await calc.async("string"));
      calcXml = shiftCalc(calcXml, 37, patched.extra);
      zip.file("xl/calcChain.xml", calcXml);
    }

    zip.remove("xl/worksheets/sheet2.xml");
    zip.remove("xl/worksheets/_rels/sheet2.xml.rels");
    zip.remove("xl/printerSettings/printerSettings2.bin");

    return zip.generateAsync({
      type: "blob",
      mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      compression: "DEFLATE"
    });
  }

  root.fillInsertRowsXlsx = fillInsertRowsXlsx;
})(typeof window !== "undefined" ? window : this);
