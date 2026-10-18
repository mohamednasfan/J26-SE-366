"""
Phase 8 - SHAP Explainability
=====================================================================
Uses SHAP (SHapley Additive exPlanations) to explain the XGBoost model.
Answers Research Question 4: "Which drug chemical features drive dangerous interactions?"

Generates:
  1. Global Summary Plot: Top Morgan fingerprint bits overall.
  2. Waterfall Plot: Explanation for a specific drug pair (e.g. 1st in test set).

Outputs:
    figures/shap_summary.png
    figures/shap_waterfall.png

Usage:
    python src/08_shap_explain.py
"""

import os
import joblib
import numpy as np
import shap
import matplotlib.pyplot as plt
from tqdm import tqdm

SPLIT_DIR = os.path.join("data", "splits")
MODEL_DIR = "models"
FIG_DIR   = "figures"

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def main():
    print("=" * 60)
    print("  DDI Research - Phase 8: SHAP Explainability")
    print("=" * 60)

    ensure_dir(FIG_DIR)

    model_path = os.path.join(MODEL_DIR, "xgboost_model.pkl")
    if not os.path.exists(model_path):
        print(f"ERROR: {model_path} not found.")
        print("Run: python src/05_train_classical.py first.")
        return

    print("[Load] Reading XGBoost model and test data...")
    xgb_model = joblib.load(model_path)
    X_test = np.load(os.path.join(SPLIT_DIR, "test_X.npy"))
    
    # SHAP can be slow, so we take a sample of the test set for global explanation
    sample_size = min(1000, len(X_test))
    np.random.seed(42)
    idx = np.random.choice(len(X_test), sample_size, replace=False)
    X_sample = X_test[idx]

    print(f"[SHAP] Calculating TreeSHAP values for {sample_size} samples...")
    # Use TreeExplainer for XGBoost (much faster than KernelExplainer)
    explainer = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_sample)

    # Note: For pair features (4096 dim), bit i and bit i+2048 represent the 
    # same chemical substructure (one on drug A, one on drug B). 
    feature_names = [f"FP_Bit_{i}" for i in range(4096)]

    # 1. Global Summary Plot
    print(f"[Plot] Generating Global Summary Plot...")
    plt.figure()
    shap.summary_plot(shap_values, X_sample, feature_names=feature_names, show=False)
    summary_path = os.path.join(FIG_DIR, "shap_summary.png")
    plt.savefig(summary_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"  Saved -> {summary_path}")

    # 2. Local Waterfall Plot (for the first instance in our sample)
    print(f"[Plot] Generating Local Waterfall Plot...")
    
    # explainer(X) returns an Explanation object which waterfall plot requires in newer SHAP versions
    explanation = explainer(X_sample[0:1]) 
    
    plt.figure()
    shap.waterfall_plot(explanation[0], max_display=10, show=False)
    waterfall_path = os.path.join(FIG_DIR, "shap_waterfall.png")
    plt.savefig(waterfall_path, bbox_inches='tight', dpi=300)
    plt.close()
    print(f"  Saved -> {waterfall_path}")

    print("\n" + "=" * 60)
    print("  SHAP analysis complete.")
    print(f"Next step: python src/09_visualize.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
