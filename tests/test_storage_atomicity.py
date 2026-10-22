"""Transactional persistence and aggregate counts stay correct after pagination."""
import json
import pytest

from medsafe import storage


def fake_ocr(text="Medicine: SYNTHMED-01"):
    return {"text":text,"engine":"tesseract","warnings":["TEST_ONLY"]}


def test_upload_writes_original_and_review_event(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA", tmp_path)
    source=b"synthetic image test fixture bytes"
    pid=storage.create_with_image("synthetic.png",".png","tesseract",fake_ocr(),source)
    assert (tmp_path/(pid+".png")).read_bytes()==source
    row=storage.get(pid)
    assert row["filename"]=="synthetic.png"
    assert json.loads(row["ocr_json"])["text"]=="Medicine: SYNTHMED-01"
    assert storage.audit(pid)[0]["action"]=="OCR_CREATED_UNVERIFIED"
    assert not list(tmp_path.glob(".medsafe-*.tmp"))


def test_totals_are_not_limited_to_history_page(tmp_path, monkeypatch):
    monkeypatch.setattr(storage,"DATA",tmp_path)
    ids=[storage.create_with_image(f"synthetic{i}.png",".png","tesseract",
           fake_ocr(f"Medicine: SYNTHMED-{i:02d}"),b"fictional") for i in range(4)]
    assert storage.counts()=={"total":4,"reviewed":0,"pending":4}
    assert len(storage.rows(limit=2,offset=0))==2
    assert len(storage.rows(limit=2,offset=2))==2
    assert len(storage.rows(limit=2,offset=4))==0
    storage.update(ids[0],"Medicine: SYNTHMED-01",{"clinical_clearance":False})
    assert storage.counts()=={"total":4,"reviewed":1,"pending":3}


def test_failed_database_transaction_removes_written_image(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,"DATA",tmp_path)
    def broken_connect():
        raise RuntimeError("simulated database failure")
    monkeypatch.setattr(storage,"connect",broken_connect)
    with pytest.raises(RuntimeError,match="database failure"):
        storage.create_with_image("synthetic.png",".png","tesseract",
                                  fake_ocr(),b"fictional source")
    assert not list(tmp_path.glob("*.png"))
    assert not list(tmp_path.glob(".medsafe-*"))
