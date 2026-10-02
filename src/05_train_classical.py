"""
Phase 5 - Train Classical Models (LR, RF, XGBoost)
=====================================================================
Trains three classical machine learning models on the standard train split:
  1. Logistic Regression (Baseline)
  2. Random Forest
  3. XGBoost

Evaluates them on BOTH the standard test set and the zero-shot test set.
Saves the models and a CSV of evaluation metrics.

Outputs:
    models/lr_model.pkl
    models/rf_model.pkl
    models/xgb_model.pkl
    results/classical_metrics.csv

Usage:
    python src/05_train_classical.py
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, accuracy_score, precision_score, recall_score
from tqdm import tqdm

SPLIT_DIR   = os.path.join("data", "splits")
MODEL_DIR   = "models"
RESULTS_DIR = "results"

RANDOM_SEED = 42


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def load_split(name):
    X = np.load(os.path.join(SPLIT_DIR, f"{name}_X.npy"))
    y = np.load(os.path.join(SPLIT_DIR, f"{name}_y.npy"))
    return X, y


def evaluate_model(model, X, y, model_name, split_name):
    """Calculate and return a dictionary of evaluation metrics."""
    y_pred_proba = model.predict_proba(X)[:, 1]
    y_pred = model.predict(X)

    return {
        "Model": model_name,
        "Split": split_name,
        "AUC-ROC": roc_auc_score(y, y_pred_proba),
        "AUC-PR": average_precision_score(y, y_pred_proba),
        "F1": f1_score(y, y_pred),
        "Precision": precision_score(y, y_pred),
        "Recall": recall_score(y, y_pred),
        "Accuracy": accuracy_score(y, y_pred)
    }


def main():
    print("=" * 60)
    print("  DDI Research - Phase 5: Train Classical Models")
    print("=" * 60)

    ensure_dir(MODEL_DIR)
    ensure_dir(RESULTS_DIR)

    # 1. Load Data
    print("[Load] Reading data splits...")
    try:
        X_train, y_train = load_split("train")
        X_test,  y_test  = load_split("test")
        X_zs,    y_zs    = load_split("zeroshot")
    except FileNotFoundError as e:
        print(f"ERROR: Could not find split files. {e}")
        print("Run: python src/04_split.py first.")
        return

    print(f"  Train : {X_train.shape}")
    print(f"  Test  : {X_test.shape}")
    print(f"  Zero  : {X_zs.shape}")

    # 2. Define Models
    models = {
        "Logistic Regression": LogisticRegression(
            C=1.0, max_iter=1000, random_state=RANDOM_SEED, n_jobs=-1
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=20, random_state=RANDOM_SEED, n_jobs=-1
        ),
        "XGBoost": XGBClassifier(
            n_estimators=500, learning_rate=0.05, random_state=RANDOM_SEED, 
            n_jobs=-1, eval_metric="logloss"
        )
    }

    all_results = []

    # 3. Train and Evaluate
    for name, clf in models.items():
        print(f"\n[Train] {name}...")
        
        # Train
        clf.fit(X_train, y_train)
        
        # Save Model
        model_path = os.path.join(MODEL_DIR, f"{name.lower().replace(' ', '_')}_model.pkl")
        joblib.dump(clf, model_path)
        print(f"  Saved to {model_path}")

        # Evaluate on Standard Test
        res_test = evaluate_model(clf, X_test, y_test, name, "Standard Test")
        all_results.append(res_test)
        print(f"  Standard Test AUC-ROC: {res_test['AUC-ROC']:.4f}")

        # Evaluate on Zero-Shot Test
        res_zs = evaluate_model(clf, X_zs, y_zs, name, "Zero-Shot Test")
        all_results.append(res_zs)
        print(f"  Zero-Shot Test AUC-ROC: {res_zs['AUC-ROC']:.4f}")

    # 4. Save Results
    results_df = pd.DataFrame(all_results)
    out_csv = os.path.join(RESULTS_DIR, "classical_metrics.csv")
    results_df.to_csv(out_csv, index=False)

    print("\n" + "=" * 60)
    print("  TRAINING SUMMARY (CLASSICAL)")
    print("=" * 60)
    print(results_df.to_string(index=False))
    print(f"\n  Metrics saved -> {out_csv}")
    print(f"\nNext step: python src/06_train_gnn.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
