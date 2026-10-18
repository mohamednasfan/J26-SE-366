"""
Phase 7 - Unified Evaluation
=====================================================================
Compiles results from all trained models (LR, RF, XGBoost, GNN) 
and both test sets (Standard, Zero-Shot) into a single unified table.
This script checks that `final_comparison.csv` exists and formats 
the output for easy reading and inclusion in the paper.

Outputs:
    Prints a formatted summary table to console.

Usage:
    python src/07_evaluate.py
"""

import os
import pandas as pd

RESULTS_DIR = "results"
FINAL_CSV   = os.path.join(RESULTS_DIR, "final_comparison.csv")

def main():
    print("=" * 80)
    print("  DDI Research - Phase 7: Unified Evaluation")
    print("=" * 80)

    if not os.path.exists(FINAL_CSV):
        print(f"ERROR: {FINAL_CSV} not found.")
        print("Please ensure you have run both:")
        print("  python src/05_train_classical.py")
        print("  python src/06_train_gnn.py")
        return

    df = pd.read_csv(FINAL_CSV)
    
    # Sort for consistent display
    # We want Standard Test first, then Zero-Shot, and models ordered by complexity
    model_order = {"Logistic Regression": 1, "Random Forest": 2, "XGBoost": 3, "GNN (GraphSAGE)": 4}
    df['Model_Order'] = df['Model'].map(model_order)
    df['Split_Order'] = df['Split'].map({"Standard Test": 1, "Zero-Shot Test": 2})
    
    df = df.sort_values(by=['Split_Order', 'Model_Order']).drop(columns=['Model_Order', 'Split_Order'])
    
    print("\n[Final Results Table]")
    print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    
    # Calculate performance drops
    print("\n[Performance Degradation (Standard -> Zero-Shot)]")
    
    standard = df[df['Split'] == 'Standard Test'].set_index('Model')
    zeroshot = df[df['Split'] == 'Zero-Shot Test'].set_index('Model')
    
    drop = standard[['AUC-ROC', 'F1']] - zeroshot[['AUC-ROC', 'F1']]
    drop.columns = ['AUC Drop', 'F1 Drop']
    
    print(drop.to_string(float_format=lambda x: f"{x:+.4f}"))
    
    print("\n" + "=" * 80)
    print(f"  Unified metrics available in {FINAL_CSV}")
    print(f"Next step: python src/08_shap_explain.py")
    print("=" * 80)

if __name__ == "__main__":
    main()
