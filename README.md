# DDI Prediction Research Pipeline

This repository contains the complete machine learning pipeline for predicting Drug-Drug Interactions (DDI) using both Classical ML and Graph Neural Networks (GNN). It specifically evaluates **zero-shot generalization** to unseen drug pairs and uses **SHAP** for interpretability.

## Research Questions Addressed
1. Which ML model (LR, RF, XGBoost, GNN) best predicts DDIs?
2. Does a GNN outperform traditional ML by using graph structure?
3. How well do models generalize to completely unseen drug pairs (zero-shot)?
4. Which chemical features drive dangerous interactions (SHAP)?

## Project Structure
```text
ddi-prediction/
├── backend/                  # FastAPI health and prediction endpoints
├── components/s2_ddi_prediction/
│   ├── preprocessing/        # Pair validation and negative sampling
│   ├── features/             # Morgan fingerprints
│   ├── models/               # LR, RF, XGBoost, and GNN model factories
│   ├── evaluation/           # Shared classification metrics
│   ├── explainability/       # SHAP integration boundary
│   └── api/                  # Component-level API package
├── data/                     # Local datasets and generated features
├── src/                      # Backward-compatible pipeline scripts
├── models/                   # Saved trained models
├── results/                  # Evaluation metrics CSVs
└── figures/                  # Generated plots for the paper
```

## Setup Instructions

1. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: For GPU acceleration, install the CUDA version of PyTorch separately).*

2. **Run the pipeline in order:**
   ```bash
   python src/01_download_data.py       # Download raw data
   python src/02_preprocess.py          # Clean and generate negative samples
   python src/03_featurize.py           # PubChem SMILES -> Morgan Fingerprints
   python src/04_split.py               # Create standard and zero-shot splits
   python src/05_train_classical.py     # Train LR, RF, XGBoost
   python src/06_train_gnn.py           # Train Graph Neural Network
   python src/07_evaluate.py            # Compile unified results
   python src/08_shap_explain.py        # Generate SHAP explanations
   python src/09_visualize.py           # Generate paper figures
   ```

3. **Run the API after training a model:**
   ```bash
   uvicorn backend.main:app --reload
   ```
   `GET /health` reports whether the configured model exists. `POST /predict`
   accepts `drug1_smiles` and `drug2_smiles`; it returns HTTP 503 until a
   trained model is available at `DDI_MODEL_PATH` (or the default model path).

4. **Run focused tests:**
   ```bash
   pytest tests/test_s2_components.py -q
   ```

## Key Methodology
- **Features:** 2048-bit Morgan Fingerprints (RDKit) derived from canonical SMILES (PubChem).
- **Negative Sampling:** 1:1 ratio of positive (interacting) to randomly sampled negative (non-interacting) pairs.
- **Zero-Shot Test:** 15% of unique drugs are held out *entirely* before splitting. Any pair containing these drugs forms the zero-shot test set, proving the model can generalize to novel chemical entities.
