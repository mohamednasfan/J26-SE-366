"""Archived and current benchmarks must never hide multi-medicine dosing errors."""
import io
import json
from PIL import Image
from backend.app.research.benchmark import run_benchmark

def test_multi_medication_synthetic_benchmark_abstains_and_scores_both(tmp_path,monkeypatch):
    image=Image.new("RGB",(160,70),"white")
    data=io.BytesIO()
    image.save(data,format="PNG")
    (tmp_path/"sample.png").write_bytes(data.getvalue())
    (tmp_path/"manifest.jsonl").write_text(json.dumps({
        "image_id":"synthetic-test-two","image_path":"sample.png",
        "gold_transcript":"Medicine: SYNTHMED-01\nDose: 10 mg\nMedicine: SYNTHMED-02\nDose: 20 mg",
        "gold":{"medicine":"SYNTHMED-01 | SYNTHMED-02",
                "dose":"10 mg | 20 mg"},
        "synthetic_rule":{"max_single_mg":15,"max_daily_mg":25,
                          "min_age_years":12,"max_age_years":65},
        "gold_alert":True,"gold_age_flag":False
    })+"\n",encoding="utf-8")
    monkeypatch.setattr("backend.app.research.benchmark.recognize",lambda data,engine:{
        "text":"Medicine: SYNTHMED-01\nDose: 10 mg\nFrequency: BID\nAge: 30\n"
               "Medicine: SYNTHMED-02\nDose: 20 mg\nFrequency: daily",
        "warnings":["MOCK_ONLY"],
    })
    out=run_benchmark(tmp_path/"manifest.jsonl",engines=["tesseract"],require_human=False)
    sample=out["engines"]["tesseract"]["predictions"][0]
    assert sample["fields"]["medicine"]=="SYNTHMED-01 | SYNTHMED-02"
    assert sample["fields"]["dose"]=="10 mg | 20 mg"
    assert sample["dose_screen"]=="ABSTAIN"
    assert sample["age_screen"]=="ABSTAIN"
    assert out["engines"]["tesseract"]["dose_alert_evaluated_n"]==0
