"""Local SQLite application history. Store only in trusted local installation."""
from __future__ import annotations
import os,sqlite3,uuid,json
from pathlib import Path
from datetime import datetime,timezone
DATA=Path(os.getenv('MEDSAFE_DATA_DIR',Path(__file__).resolve().parent.parent/'runtime_data'))

def connect():
    DATA.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA/'medsafe.db')
    db.row_factory=sqlite3.Row
    db.execute('''CREATE TABLE IF NOT EXISTS prescriptions (
        id TEXT PRIMARY KEY, created TEXT NOT NULL, updated TEXT NOT NULL,
        filename TEXT NOT NULL, status TEXT NOT NULL, engine TEXT NOT NULL,
        original_text TEXT NOT NULL, corrected_text TEXT NOT NULL DEFAULT '',
        image_name TEXT NOT NULL, ocr_json TEXT NOT NULL, report_json TEXT NOT NULL DEFAULT '{}',
        reviewer_confirmed INTEGER NOT NULL DEFAULT 0)''')
    db.commit()
    return db

def create(filename,ext,engine,ocr):
    pid=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute('''INSERT INTO prescriptions (id,created,updated,filename,status,engine,original_text,image_name,ocr_json)
                      VALUES (?,?,?,?,?,?,?,?,?)''',
                   (pid,now,now,filename,'REVIEW_REQUIRED',engine,ocr['text'],pid+ext,json.dumps(ocr)))
    return pid

def get(pid):
    with connect() as db:
        row=db.execute('SELECT * FROM prescriptions WHERE id=?',(pid,)).fetchone()
    return dict(row) if row else None

def rows():
    with connect() as db:
        result=db.execute('SELECT id,created,updated,filename,status,engine,reviewer_confirmed FROM prescriptions ORDER BY created DESC LIMIT 150').fetchall()
    return [dict(x) for x in result]

def update(pid,text,report):
    with connect() as db:
        db.execute('''UPDATE prescriptions SET corrected_text=?,reviewer_confirmed=1,report_json=?,status=?,updated=? WHERE id=?''',
                   (text,json.dumps(report),'REVIEWED_WITH_UNRESOLVED_CLINICAL_CHECKS',datetime.now(timezone.utc).isoformat(),pid))

def delete(pid):
    row=get(pid)
    if not row:return False
    with connect() as db:db.execute('DELETE FROM prescriptions WHERE id=?',(pid,))
    (DATA/row['image_name']).unlink(missing_ok=True)
    return True
