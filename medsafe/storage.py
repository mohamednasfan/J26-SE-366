"""Local SQLite repository with explicit transactions and immutable review events.

Single-user, loopback-only research data store. This is NOT encrypted multi-tenant
patient-record storage and must never be Internet-exposed without security redesign.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3
import uuid

DATA=Path(os.getenv('MEDSAFE_DATA_DIR',Path(__file__).resolve().parent.parent/'runtime_data'))

def _now():
    return datetime.now(timezone.utc).isoformat()

def _digest(text):
    return sha256(str(text).encode('utf-8')).hexdigest()

@contextmanager
def connect():
    DATA.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA/'medsafe.db',timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('''CREATE TABLE IF NOT EXISTS prescriptions (
        id TEXT PRIMARY KEY, created TEXT NOT NULL, updated TEXT NOT NULL,
        filename TEXT NOT NULL, status TEXT NOT NULL, engine TEXT NOT NULL,
        original_text TEXT NOT NULL, corrected_text TEXT NOT NULL DEFAULT '',
        image_name TEXT NOT NULL, ocr_json TEXT NOT NULL, report_json TEXT NOT NULL DEFAULT '{}',
        reviewer_confirmed INTEGER NOT NULL DEFAULT 0)''')
    db.execute('''CREATE TABLE IF NOT EXISTS review_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        prescription_id TEXT NOT NULL,
        event_time TEXT NOT NULL,
        action TEXT NOT NULL,
        before_sha256 TEXT,
        after_sha256 TEXT,
        FOREIGN KEY(prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
    )''')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def create(filename,ext,engine,ocr):
    pid=str(uuid.uuid4());now=_now()
    with connect() as db:
        db.execute('''INSERT INTO prescriptions
            (id,created,updated,filename,status,engine,original_text,image_name,ocr_json)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (pid,now,now,filename,'REVIEW_REQUIRED',engine,ocr['text'],pid+ext,
             json.dumps(ocr,ensure_ascii=False)))
        db.execute('''INSERT INTO review_events
            (prescription_id,event_time,action,after_sha256) VALUES (?,?,?,?)''',
            (pid,now,'OCR_CREATED_UNVERIFIED',_digest(ocr['text'])))
    return pid

def get(pid):
    with connect() as db:
        result=db.execute('SELECT * FROM prescriptions WHERE id=?',(pid,)).fetchone()
        return dict(result) if result else None

def rows():
    with connect() as db:
        rows=db.execute('''SELECT id,created,updated,filename,status,engine,reviewer_confirmed
            FROM prescriptions ORDER BY created DESC LIMIT 150''').fetchall()
        return [dict(row) for row in rows]

def update(pid,text,report):
    now=_now()
    with connect() as db:
        previous=db.execute('SELECT corrected_text,reviewer_confirmed FROM prescriptions WHERE id=?',(pid,)).fetchone()
        if not previous:raise KeyError('Prescription not found')
        action='TRANSCRIPTION_REVISED' if previous['reviewer_confirmed'] else 'TRANSCRIPTION_CONFIRMED'
        db.execute('''UPDATE prescriptions SET corrected_text=?,reviewer_confirmed=1,
            report_json=?,status=?,updated=? WHERE id=?''',
            (text,json.dumps(report,ensure_ascii=False),
             'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS',now,pid))
        db.execute('''INSERT INTO review_events
            (prescription_id,event_time,action,before_sha256,after_sha256)
            VALUES (?,?,?,?,?)''',
            (pid,now,action,_digest(previous['corrected_text']) if previous['reviewer_confirmed'] else None,
             _digest(text)))

def audit(pid):
    with connect() as db:
        exists=db.execute('SELECT 1 FROM prescriptions WHERE id=?',(pid,)).fetchone()
        if not exists:return None
        events=db.execute('''SELECT event_id,event_time,action,before_sha256,after_sha256
            FROM review_events WHERE prescription_id=? ORDER BY event_id DESC''',(pid,)).fetchall()
        return [dict(row) for row in events]

def delete(pid):
    row=get(pid)
    if not row:return False
    with connect() as db:
        db.execute('DELETE FROM review_events WHERE prescription_id=?',(pid,))
        db.execute('DELETE FROM prescriptions WHERE id=?',(pid,))
    (DATA/row['image_name']).unlink(missing_ok=True)
    return True
