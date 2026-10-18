"""
Phase 4 - Train / Validation / Test / Zero-Shot Split
=====================================================================
Creates 4 non-overlapping data splits from the featurized dataset:

  1. Train       (70%)  - All models train on this
  2. Val         (10%)  - Hyperparameter tuning (not used in final eval)
  3. Standard Test (10%) - Normal test: model saw these drug types before
  4. Zero-Shot Test(10%) - Held-out drugs: model NEVER saw these during training

The Zero-Shot split is the key research novelty.
A random 15% of unique drugs are held out entirely before any splitting.
Any pair that contains a held-out drug is placed in zero-shot test only.

Outputs (all in data/splits/):
    train_X.npy, train_y.npy, train_pairs.csv
    val_X.npy,   val_y.npy,   val_pairs.csv
    test_X.npy,  test_y.npy,  test_pairs.csv
    zeroshot_X.npy, zeroshot_y.npy, zeroshot_pairs.csv
    split_summary.json  ← statistics for reproducibility

Usage:
    python src/04_split.py
"""

import os
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PROC_DIR   = os.path.join("data", "processed")
SPLIT_DIR  = os.path.join("data", "splits")

FEAT_FILE  = os.path.join(PROC_DIR, "features.npz")
LABEL_FILE = os.path.join(PROC_DIR, "labels.npy")
PAIRS_FILE = os.path.join(PROC_DIR, "pairs.csv")

ZEROSHOT_DRUG_FRAC = 0.15   # fraction of unique drugs held out entirely
RANDOM_SEED        = 42


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def save_split(name, X, y, pairs, split_dir):
    np.save(os.path.join(split_dir, f"{name}_X.npy"), X)
    np.save(os.path.join(split_dir, f"{name}_y.npy"), y)
    pairs.to_csv(os.path.join(split_dir, f"{name}_pairs.csv"), index=False)
    pos = int(y.sum())
    neg = int((y == 0).sum())
    print(f"  {name:15s}: {len(X):>7,} pairs  |  pos={pos:,}  neg={neg:,}")


def main():
    print("=" * 60)
    print("  DDI Research - Phase 4: Data Splitting")
    print("=" * 60)

    ensure_dir(SPLIT_DIR)

    # ── Load featurized data ──
    if not os.path.exists(FEAT_FILE):
        print(f"ERROR: {FEAT_FILE} not found.  Run: python src/03_featurize.py first.")
        return

    print("[Load] Reading feature matrix and labels...")
    X      = np.load(FEAT_FILE)["X"]
    y      = np.load(LABEL_FILE)
    pairs  = pd.read_csv(PAIRS_FILE)
    assert len(X) == len(y) == len(pairs), "Dimension mismatch in loaded data."
    print(f"  Total pairs : {len(X):,}  |  Features: {X.shape[1]}")
    print(f"  Positives   : {y.sum():,}  |  Negatives: {(y==0).sum():,}")

    # ─────────────────────────────────────────────────────
    # Step 1 - Identify Zero-Shot held-out drugs
    # ─────────────────────────────────────────────────────
    all_drugs = sorted(set(pairs["drug1"].tolist() + pairs["drug2"].tolist()))
    np.random.seed(RANDOM_SEED)
    n_holdout = max(1, int(len(all_drugs) * ZEROSHOT_DRUG_FRAC))
    holdout_drugs = set(np.random.choice(all_drugs, size=n_holdout, replace=False))

    print(f"\n[Zero-Shot] Holding out {n_holdout:,} / {len(all_drugs):,} drugs "
          f"({ZEROSHOT_DRUG_FRAC*100:.0f}%)")

    # A pair is zero-shot if EITHER drug is in holdout set
    is_zeroshot = pairs.apply(
        lambda r: r["drug1"] in holdout_drugs or r["drug2"] in holdout_drugs,
        axis=1
    ).values

    # ─────────────────────────────────────────────────────
    # Step 2 - Separate zero-shot from trainable pairs
    # ─────────────────────────────────────────────────────
    zs_mask     = is_zeroshot
    normal_mask = ~is_zeroshot

    X_zs,  y_zs,  p_zs  = X[zs_mask],     y[zs_mask],     pairs[zs_mask].reset_index(drop=True)
    X_norm, y_norm, p_norm = X[normal_mask], y[normal_mask], pairs[normal_mask].reset_index(drop=True)

    print(f"  Normal pairs    : {len(X_norm):,}")
    print(f"  Zero-shot pairs : {len(X_zs):,}")

    # ─────────────────────────────────────────────────────
    # Step 3 - Split normal pairs -> Train / Val / Test
    # (70% train, 12.5% val, 12.5% test of normal subset)
    # ─────────────────────────────────────────────────────
    X_train_val, X_test, y_train_val, y_test, p_train_val, p_test = train_test_split(
        X_norm, y_norm, p_norm, test_size=0.125, random_state=RANDOM_SEED, stratify=y_norm
    )
    X_train, X_val, y_train, y_val, p_train, p_val = train_test_split(
        X_train_val, y_train_val, p_train_val,
        test_size=0.143,   # ~10% of total normal pairs
        random_state=RANDOM_SEED,
        stratify=y_train_val
    )

    # ─────────────────────────────────────────────────────
    # Step 4 - Save all splits
    # ─────────────────────────────────────────────────────
    print("\n[Splits] Saving...")
    save_split("train",    X_train, y_train, p_train, SPLIT_DIR)
    save_split("val",      X_val,   y_val,   p_val,   SPLIT_DIR)
    save_split("test",     X_test,  y_test,  p_test,  SPLIT_DIR)
    save_split("zeroshot", X_zs,    y_zs,    p_zs,    SPLIT_DIR)

    # Save held-out drug list for reference
    holdout_df = pd.DataFrame({"drug": sorted(holdout_drugs)})
    holdout_df.to_csv(os.path.join(SPLIT_DIR, "zeroshot_drugs.csv"), index=False)

    # Save summary JSON for reproducibility
    summary = {
        "random_seed"       : RANDOM_SEED,
        "zeroshot_frac"     : ZEROSHOT_DRUG_FRAC,
        "n_holdout_drugs"   : n_holdout,
        "n_total_drugs"     : len(all_drugs),
        "feature_dim"       : int(X.shape[1]),
        "splits": {
            "train"    : {"n": len(X_train),  "pos": int(y_train.sum())},
            "val"      : {"n": len(X_val),    "pos": int(y_val.sum())},
            "test"     : {"n": len(X_test),   "pos": int(y_test.sum())},
            "zeroshot" : {"n": len(X_zs),     "pos": int(y_zs.sum())}
        }
    }
    with open(os.path.join(SPLIT_DIR, "split_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # ─────────────────────────────────────────────────────
    # Verification: ensure no zero-shot drug appears in train
    # ─────────────────────────────────────────────────────
    train_drugs = set(p_train["drug1"]) | set(p_train["drug2"])
    leaked = holdout_drugs & train_drugs
    if leaked:
        print(f"\n  WARNING: {len(leaked)} zero-shot drugs found in training set! "
              f"This should not happen. Check the split logic.")
    else:
        print(f"\n  VERIFIED: Zero-shot drugs have zero overlap with training set.")

    print("\n" + "=" * 60)
    print("  SPLIT SUMMARY")
    print("=" * 60)
    total = len(X)
    for sname, sdata in summary["splits"].items():
        pct = sdata["n"] / total * 100
        print(f"  {sname:10s}: {sdata['n']:>7,} pairs  ({pct:4.1f}% of total)")
    print(f"\n  All splits saved -> {SPLIT_DIR}/")
    print(f"\nNext step: python src/05_train_classical.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
