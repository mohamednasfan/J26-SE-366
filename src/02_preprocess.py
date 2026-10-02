"""
Phase 2 - Data Preprocessing
=====================================================================
Loads all downloaded raw datasets, standardises column names,
generates negative samples (non-interacting pairs), merges everything
into one balanced dataset, and writes:

    data/processed/combined.csv   ← main dataset for all downstream steps

Usage:
    python src/02_preprocess.py
"""

import os
import random
import pandas as pd
import numpy as np

RAW_DIR  = "data"
PROC_DIR = os.path.join("data", "processed")
OUT_CSV  = os.path.join(PROC_DIR, "combined.csv")

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def canonical_pair(a, b):
    """Return a sorted tuple so (A,B) and (B,A) are the same pair."""
    return (min(a, b), max(a, b))


# ─────────────────────────────────────────────
# Loaders - one per raw dataset
# ─────────────────────────────────────────────

def load_biosnap():
    path = os.path.join(RAW_DIR, "biosnap.csv")
    if not os.path.exists(path):
        print("[BIOSNAP] File not found - skipping.")
        return pd.DataFrame()

    df = pd.read_csv(path)
    print(f"[BIOSNAP] Raw shape: {df.shape}   Columns: {list(df.columns)}")

    # Detect and standardise column names
    cols = [c.lower().strip() for c in df.columns]
    df.columns = cols

    # Try to find drug pair columns
    drug_cols = [c for c in cols if any(k in c for k in ["drug", "chem", "compound", "node"])]
    if len(drug_cols) >= 2:
        d1, d2 = drug_cols[0], drug_cols[1]
    elif len(cols) >= 2:
        d1, d2 = cols[0], cols[1]
    else:
        print("[BIOSNAP] Cannot identify drug columns - skipping.")
        return pd.DataFrame()

    out = pd.DataFrame({
        "drug1": df[d1].astype(str).str.strip().str.lower(),
        "drug2": df[d2].astype(str).str.strip().str.lower(),
        "label": 1,
        "source": "biosnap"
    })
    print(f"[BIOSNAP] Loaded {len(out):,} positive interaction pairs.")
    return out


def load_drugbank():
    path = os.path.join(RAW_DIR, "drugbank.csv")
    if not os.path.exists(path):
        print("[DrugBank] File not found - skipping.")
        return pd.DataFrame()

    df = pd.read_csv(path)
    print(f"[DrugBank] Raw shape: {df.shape}   Columns: {list(df.columns)}")

    cols = [c.lower().strip() for c in df.columns]
    df.columns = cols

    # Common column name patterns from various DrugBank mirrors
    label_col = next((c for c in cols if "label" in c or "interaction" in c or "class" in c), None)
    drug_cols  = [c for c in cols if any(k in c for k in ["drug", "name", "id", "compound"])]

    if len(drug_cols) >= 2:
        d1, d2 = drug_cols[0], drug_cols[1]
    elif len(cols) >= 2:
        d1, d2 = cols[0], cols[1]
    else:
        print("[DrugBank] Cannot identify drug columns - skipping.")
        return pd.DataFrame()

    if label_col:
        raw_labels = df[label_col].astype(str).str.lower().str.strip()
        label = raw_labels.apply(
            lambda x: 0 if any(k in x for k in ["0", "safe", "no interact", "non"]) else 1
        )
    else:
        label = 1  # All rows are interactions if no label column

    out = pd.DataFrame({
        "drug1": df[d1].astype(str).str.strip().str.lower(),
        "drug2": df[d2].astype(str).str.strip().str.lower(),
        "label": label,
        "source": "drugbank"
    })
    print(f"[DrugBank] Loaded {len(out):,} pairs  "
          f"(positive={out['label'].sum():,}, "
          f"negative={(out['label']==0).sum():,})")
    return out


def load_twosides():
    path = os.path.join(RAW_DIR, "twosides.csv")
    if not os.path.exists(path):
        print("[TWOSIDES] File not found - skipping (optional dataset).")
        return pd.DataFrame()

    # TWOSIDES is large - read only what we need
    try:
        df = pd.read_csv(path, nrows=200_000)   # cap at 200k rows for speed
    except Exception as e:
        print(f"[TWOSIDES] Read error: {e} - skipping.")
        return pd.DataFrame()

    print(f"[TWOSIDES] Raw shape (capped): {df.shape}   Columns: {list(df.columns)}")
    cols = [c.lower().strip() for c in df.columns]
    df.columns = cols

    drug_cols = [c for c in cols if "drug" in c or "stitch" in c]
    if len(drug_cols) >= 2:
        d1, d2 = drug_cols[0], drug_cols[1]
    else:
        d1, d2 = cols[0], cols[1]

    out = pd.DataFrame({
        "drug1": df[d1].astype(str).str.strip().str.lower(),
        "drug2": df[d2].astype(str).str.strip().str.lower(),
        "label": 1,
        "source": "twosides"
    })
    print(f"[TWOSIDES] Loaded {len(out):,} positive pairs.")
    return out


# ─────────────────────────────────────────────
# Negative Sampling
# ─────────────────────────────────────────────

def generate_negatives(positive_df, neg_ratio=1.0):
    """
    For every positive (interacting) pair, generate one random non-interacting pair.
    We randomly sample pairs from the known drug list that do NOT appear in the
    positive set - these are assumed to be safe/non-interacting.

    neg_ratio: how many negatives per positive (1.0 = balanced dataset)
    """
    pos_set = set(
        canonical_pair(r.drug1, r.drug2)
        for r in positive_df.itertuples()
    )
    drugs = list(set(positive_df["drug1"].tolist() + positive_df["drug2"].tolist()))
    n_neg = int(len(positive_df) * neg_ratio)

    print(f"\n[Negatives] Generating {n_neg:,} negative pairs from {len(drugs):,} unique drugs...")

    negatives = []
    attempts  = 0
    max_attempts = n_neg * 20

    while len(negatives) < n_neg and attempts < max_attempts:
        a = random.choice(drugs)
        b = random.choice(drugs)
        if a == b:
            attempts += 1
            continue
        pair = canonical_pair(a, b)
        if pair not in pos_set:
            pos_set.add(pair)   # avoid duplicating this negative later
            negatives.append({"drug1": pair[0], "drug2": pair[1], "label": 0, "source": "synthetic"})
        attempts += 1

    neg_df = pd.DataFrame(negatives)
    print(f"[Negatives] Generated {len(neg_df):,} negative pairs  "
          f"(coverage: {len(neg_df)/n_neg*100:.1f}%)")
    return neg_df


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    ensure_dir(PROC_DIR)

    print("=" * 60)
    print("  DDI Research - Phase 2: Preprocessing")
    print("=" * 60)

    # 1. Load all raw datasets
    dfs = []
    for loader in [load_biosnap, load_drugbank, load_twosides]:
        df = loader()
        if df is not None and len(df) > 0:
            dfs.append(df)

    if not dfs:
        print("\n ERROR: No data files found in data/")
        print("  -> Run: python src/01_download_data.py  first.\n")
        return

    # 2. Merge all positives
    all_positive = pd.concat(dfs, ignore_index=True)
    all_positive = all_positive[all_positive["label"] == 1].copy()

    # Canonicalise pair order to remove A-B / B-A duplicates
    all_positive[["drug1", "drug2"]] = all_positive.apply(
        lambda r: pd.Series(canonical_pair(r["drug1"], r["drug2"])), axis=1
    )
    before = len(all_positive)
    all_positive = all_positive.drop_duplicates(subset=["drug1", "drug2"])
    print(f"\n[Merge] Combined positives: {before:,} -> {len(all_positive):,} after dedup")

    # 3. Collect pre-labeled negatives from DrugBank (if any)
    pre_neg = pd.concat(dfs, ignore_index=True)
    pre_neg = pre_neg[pre_neg["label"] == 0].copy()
    if len(pre_neg) > 0:
        pre_neg[["drug1", "drug2"]] = pre_neg.apply(
            lambda r: pd.Series(canonical_pair(r["drug1"], r["drug2"])), axis=1
        )
        pre_neg = pre_neg.drop_duplicates(subset=["drug1", "drug2"])
    print(f"[Merge] Pre-labeled negatives: {len(pre_neg):,}")

    # 4. Generate synthetic negatives to reach 1:1 ratio
    n_needed = max(0, len(all_positive) - len(pre_neg))
    if n_needed > 0:
        syn_neg = generate_negatives(all_positive, neg_ratio=n_needed / len(all_positive))
        all_negative = pd.concat([pre_neg, syn_neg], ignore_index=True) if len(pre_neg) > 0 else syn_neg
    else:
        all_negative = pre_neg.sample(n=len(all_positive), random_state=RANDOM_SEED)

    # 5. Final combined dataset
    combined = pd.concat([all_positive, all_negative], ignore_index=True)
    combined  = combined.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    # Save
    combined.to_csv(OUT_CSV, index=False)

    # Summary
    print("\n" + "=" * 60)
    print("  PREPROCESSING SUMMARY")
    print("=" * 60)
    print(f"  Total pairs     : {len(combined):,}")
    print(f"  Positive (1)    : {(combined['label']==1).sum():,}  ({(combined['label']==1).mean()*100:.1f}%)")
    print(f"  Negative (0)    : {(combined['label']==0).sum():,}  ({(combined['label']==0).mean()*100:.1f}%)")
    print(f"  Unique drugs    : {len(set(combined['drug1']) | set(combined['drug2'])):,}")
    print(f"\n  Saved -> {OUT_CSV}")
    print(f"\nNext step: python src/03_featurize.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
