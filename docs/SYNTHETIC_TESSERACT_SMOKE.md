# Reproducible development smoke run — 60 synthetic prescription pages

The app's synthetic-data generator produced 400 fictional pages with 60 assigned to a held-out synthetic test split. A **real local Tesseract binary** (not an OCR mock) was run on those 60 pages through Pillow grayscale + autocontrast with `--psm 6`.

| Metric | Local synthetic development result |
|---|---:|
| CER | 0.5152% |
| WER | 3.0182% |
| Medicine exact field match | 66.67% (40/60) |
| Dose exact field match | 98.33% (59/60) |
| Mean OCR-only runtime | 0.2012 sec/image |
| 95th-percentile OCR-only runtime | 0.2324 sec/image |

**Not thesis acceptance evidence.** The pages contain synthetic, computer-typeset text with random blurring, rotation and illumination. Their generator-derived labels are not independently human-verified; no measured clinical overdose/age results or full pipeline timings are present. The models and real handwritten prescription images are different.

The full per-image development report is supplied separately as `MedSafe_AI_Synthetic_Tesseract_Smoke_60.json` in the ChatGPT conversation; the repository records **aggregate results only**.

Run the full thesis benchmark independently with `python -m backend.app.research.benchmark` and the `--engines` and `--preprocess` options on independently annotated real held-out images.
