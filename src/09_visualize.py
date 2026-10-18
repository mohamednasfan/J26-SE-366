"""
Phase 9 - Visualization and Results Dashboard
=====================================================================
Generates publication-ready figures for the research paper based on
the final compiled metrics.

Outputs (in figures/):
  - model_comparison.png       (Bar chart of AUC-ROC for all models)
  - zeroshot_degradation.png   (Slope chart showing drop in perf)

Usage:
    python src/09_visualize.py
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

RESULTS_DIR = "results"
FIG_DIR     = "figures"
FINAL_CSV   = os.path.join(RESULTS_DIR, "final_comparison.csv")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def main():
    print("=" * 60)
    print("  DDI Research - Phase 9: Visualization")
    print("=" * 60)

    ensure_dir(FIG_DIR)

    if not os.path.exists(FINAL_CSV):
        print(f"ERROR: {FINAL_CSV} not found.")
        print("Run Phase 7 (evaluate) first.")
        return

    df = pd.read_csv(FINAL_CSV)
    
    # Set plotting style
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({'font.size': 12})
    
    # 1. Model Comparison Bar Chart (Standard Test)
    print("[Plot] Generating Model Comparison (Standard Test)...")
    std_df = df[df['Split'] == 'Standard Test'].sort_values(by='AUC-ROC', ascending=True)
    
    plt.figure(figsize=(8, 5))
    bars = plt.barh(std_df['Model'], std_df['AUC-ROC'], color=sns.color_palette("Blues_r", len(std_df)))
    plt.xlabel('AUC-ROC Score')
    plt.title('Model Performance on Standard Test Set (Known Drugs)')
    plt.xlim(0.5, 1.0) # AUC usually between 0.5 and 1.0
    
    # Add values on bars
    for bar in bars:
        width = bar.get_width()
        plt.text(width + 0.01, bar.get_y() + bar.get_height()/2, f'{width:.3f}', 
                 ha='left', va='center')
                 
    plt.tight_layout()
    comp_path = os.path.join(FIG_DIR, "model_comparison.png")
    plt.savefig(comp_path, dpi=300)
    plt.close()
    print(f"  Saved -> {comp_path}")


    # 2. Zero-Shot Degradation (Slope Chart)
    print("[Plot] Generating Zero-Shot Degradation Chart...")
    
    # Pivot data to have Standard and Zero-Shot side-by-side
    pivot_df = df.pivot(index='Model', columns='Split', values='AUC-ROC').reset_index()
    
    # Reorder models for legend consistency
    model_order = ["Logistic Regression", "Random Forest", "XGBoost", "GNN (GraphSAGE)"]
    pivot_df['Model'] = pd.Categorical(pivot_df['Model'], categories=model_order, ordered=True)
    pivot_df = pivot_df.sort_values('Model')

    plt.figure(figsize=(7, 6))
    
    colors = sns.color_palette("husl", len(pivot_df))
    
    for i, row in pivot_df.iterrows():
        plt.plot(['Standard Test\n(Known Drugs)', 'Zero-Shot Test\n(New Drugs)'], 
                 [row['Standard Test'], row['Zero-Shot Test']], 
                 marker='o', markersize=8, linewidth=2.5, 
                 label=row['Model'], color=colors[i])
                 
    plt.ylabel('AUC-ROC Score')
    plt.title('Generalization to Unseen Drugs (Zero-Shot)')
    plt.legend(title="Model", loc='lower left')
    plt.grid(True, axis='y', linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    deg_path = os.path.join(FIG_DIR, "zeroshot_degradation.png")
    plt.savefig(deg_path, dpi=300)
    plt.close()
    print(f"  Saved -> {deg_path}")

    print("\n" + "=" * 60)
    print("  Visualizations generated successfully.")
    print("  Check the figures/ directory.")
    print("=" * 60)

if __name__ == "__main__":
    main()
