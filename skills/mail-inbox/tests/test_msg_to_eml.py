#!/usr/bin/env python3
"""Outlook .msg dropped in 待处理邮件 is converted, then classified like an .eml."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from extract_msg.ole_writer import OleWriter  # noqa: E402

from classify_mail import collect_attachment_meta, get_body_text  # noqa: E402
from msg_to_eml import load_mail, msg_to_eml_bytes  # noqa: E402
from process_drop_folder import process_drop_folder  # noqa: E402


def _utf16(text: str) -> bytes:
    return (text + "\x00").encode("utf-16-le")


def _var_entry(prop_id: int, payload: bytes, prop_type: int = 0x001F) -> bytes:
    return struct.pack("<2HI", prop_type, prop_id, 0) + struct.pack("<2I", len(payload), 0)


def write_sample_msg(path: Path, *, subject: str, body: str, filename: str, payload: bytes) -> None:
    headers = (
        f"Subject: {subject}\r\n"
        "From: vendor@example.com\r\n"
        "Message-ID: <msg-drop-test@example.com>\r\n"
        "Date: Mon, 12 Oct 2026 10:00:00 +0800\r\n"
        "\r\n"
    )
    subject_b = _utf16(subject)
    body_b = _utf16(body)
    header_b = _utf16(headers)
    name_b = _utf16(filename)
    class_b = _utf16("IPM.Note")
    props = b"\x00" * 32
    props += _var_entry(0x001A, class_b)
    props += _var_entry(0x0037, subject_b)
    props += _var_entry(0x1000, body_b)
    props += _var_entry(0x007D, header_b)

    att_props = b"\x00" * 8
    att_props += struct.pack("<2HI", 0x0003, 0x3705, 0) + struct.pack("<I", 1) + b"\x00" * 4
    att_props += _var_entry(0x3707, name_b)
    att_props += _var_entry(0x3701, payload, 0x0102)

    writer = OleWriter()
    writer.addEntry("__properties_version1.0", props)
    writer.addEntry("__substg1.0_001A001F", class_b)
    writer.addEntry("__substg1.0_0037001F", subject_b)
    writer.addEntry("__substg1.0_1000001F", body_b)
    writer.addEntry("__substg1.0_007D001F", header_b)
    writer.addEntry("__nameid_version1.0", storage=True)
    writer.addEntry(["__nameid_version1.0", "__substg1.0_00020102"], b"")
    writer.addEntry(["__nameid_version1.0", "__substg1.0_00030102"], b"")
    writer.addEntry(["__nameid_version1.0", "__substg1.0_00040102"], b"")
    writer.addEntry("__attach_version1.0_#00000000", storage=True)
    writer.addEntry(["__attach_version1.0_#00000000", "__properties_version1.0"], att_props)
    writer.addEntry(["__attach_version1.0_#00000000", "__substg1.0_3707001F"], name_b)
    writer.addEntry(["__attach_version1.0_#00000000", "__substg1.0_37010102"], payload)
    writer.write(path)


def test_convert_keeps_subject_body_and_attachment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "报价.msg"
        payload = b"%PDF-1.4 test"
        write_sample_msg(
            src,
            subject="RFP for Door Package (SupplierA)",
            body="Please submit quotation for the door package.",
            filename="合同.pdf",
            payload=payload,
        )
        msg = load_mail(src)
        subject = msg.get("Subject")
        assert "Door Package" in subject, subject
        assert "quotation" in get_body_text(msg)
        names = [item["filename"] for item in collect_attachment_meta(msg)]
        assert names == ["合同.pdf"], names
        parsed = BytesParser(policy=default).parsebytes(msg_to_eml_bytes(src))
        attached = [part.get_payload(decode=True) for part in parsed.walk() if part.get_filename()]
        assert payload in attached


def test_drop_folder_stages_msg_and_leaves_a_reply() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".skill").mkdir()
        (root / ".skill" / "project.json").write_text("{}", encoding="utf-8")
        drop = root / "待处理邮件"
        drop.mkdir()
        (drop / "备注.txt").write_text("不是邮件", encoding="utf-8")
        write_sample_msg(
            drop / "回信.msg",
            subject="Re: RFP for Door Package",
            body="Latest line: please hold.",
            filename="合同.pdf",
            payload=b"pdf",
        )
        out = process_drop_folder(root)
        assert out["ok"] is True
        by_file = {item["file"]: item for item in out["items"]}
        assert "回信.msg" not in by_file
        reply = by_file["回信.eml"]
        assert reply["status"] == "needs_you"
        assert reply["reason"] == "thread_reply"
        assert (drop / "回信.eml").is_file()
        assert not (drop / "回信.msg").exists()
        assert by_file["备注.txt"]["status"] == "left"
        assert by_file["备注.txt"]["reason"] == "not_eml"


def test_plain_mail_renamed_to_msg_still_reads() -> None:
    raw = (
        "Subject: RFP for Glazing\r\n"
        "From: a@example.com\r\n"
        "\r\n"
        "Please quote.\r\n"
    ).encode("utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "renamed.msg"
        path.write_bytes(raw)
        msg = load_mail(path)
        assert "Glazing" in msg.get("Subject")
        assert path.read_bytes() == raw


if __name__ == "__main__":
    test_convert_keeps_subject_body_and_attachment()
    test_drop_folder_stages_msg_and_leaves_a_reply()
    test_plain_mail_renamed_to_msg_still_reads()
    print(json.dumps({"ok": True}, ensure_ascii=False))
