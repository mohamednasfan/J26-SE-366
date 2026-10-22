# Archived four-engine OCR benchmark — verified alignment (780 image cohort)

**Source:** user-provided `MedSafe_AI.zip`. Recomputed from the `original` image variant in each engine's recorded `testing_results.csv`.

| Model | Case-insensitive micro CER | Micro WER | Medicine exact match |
|---|---:|---:|---:|
| Tesseract | 61.2753% | 128.7342% | 7.5641% (59/780) |
| EasyOCR | 54.5951% | 111.6456% | 10.3846% (81/780) |
| PaddleOCR | 17.5911% | 56.3291% | 45.1282% (352/780) |
| TrOCR (historical experiment) | 58.4615% | 142.1519% | 13.2051% (103/780) |

All engines share **780 image IDs, 4,940 reference characters and 790 reference words**, with **zero mismatched gold medicine labels** across the archived CSVs.

**Computation:** strip and casefold each gold/prediction. Micro CER = sum Levenshtein character edits / sum reference characters. Micro WER = sum token edits / sum reference words. Medicine accuracy uses case-insensitive, whitespace-normalized exact match. CER/WER may exceed 100% when insertions are numerous.

**Interpretation:** This is evidence of a historic comparative study, **not** a validated production checkpoint or full-prescription evaluation. The archived TrOCR row predates later corrected Notebook 44 fine-tuning, and does not represent that trained model. No age, dosage, overdose, latency acceptance or leakage-free independent validation is established here.

**Next steps in code:** `python -m backend.app.research.benchmark path/to/human_verified_test.jsonl` runs identical images through all four selectable engines and emits full-coverage, ground-truth-gated metrics. Use qualified clinical review of actual drug limits separately.
