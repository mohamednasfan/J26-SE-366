# MedSafeAI

MedSafeAI is organized as three independent components:

- `components/s1_prescription_ocr` - prescription OCR
- `components/s2_ddi_prediction` - drug-drug interaction prediction
- `components/s3_side_effect_prediction` - side-effect prediction

The existing datasets, processed arrays, trained models, and evaluation outputs
are now kept in the S2 component:

- Raw inputs: `components/s2_ddi_prediction/data/raw`
- Processed inputs: `components/s2_ddi_prediction/data/processed`
- Model artifacts: `components/s2_ddi_prediction/models`
- Evaluation outputs: `components/s2_ddi_prediction/evaluation/results`

The data-inspection notebook is available at
`notebooks/s2/01_data_inspection.ipynb`.

## S2 demo

Install the dependencies and start the API:

```powershell
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Then open `http://127.0.0.1:8000/`. The S2 screen lets a user search for two
drugs and displays the interaction decision, model score, threshold, and
explanation. It is a research demonstration and not a clinical decision tool.
