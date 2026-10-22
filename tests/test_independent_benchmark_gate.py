"""Independent benchmark must reject undersized unverified cohorts."""
import json
from backend.app.research.benchmark import read_manifest

def test_small_independent_cohort_can_be_loaded_for_pilot_testing(tmp_path):
    image=tmp_path/"rx.png"
    image.write_bytes(b"synthetic-image-for-validation-only")
    manifest=tmp_path/"manifest.jsonl"
    manifest.write_text(json.dumps({
        "image_path":"rx.png","image_id":"case-001",
        "gold_transcript":"Medicine: fictional",
        "gold":{"medicine":"fictional"},
        "human_verified":True,"split":"test","reviewer_id":"reviewer-fixture"
    })+"\n",encoding="utf-8")
    assert len(read_manifest(manifest,require_human=True)) == 1

def test_synthetic_development_allows_small_cohort(tmp_path):
    image=tmp_path/"rx.png"
    image.write_bytes(b"synthetic-image-for-validation-only")
    manifest=tmp_path/"manifest.jsonl"
    manifest.write_text(json.dumps({
        "image_path":"rx.png","image_id":"case-001",
        "gold_transcript":"Medicine: fictional","gold":{"medicine":"fictional"}
    })+"\n",encoding="utf-8")
    assert len(read_manifest(manifest,require_human=False))==1
