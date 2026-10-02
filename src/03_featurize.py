"""
Phase 3 - Featurization (Morgan Fingerprints via PubChem)
=====================================================================
For every drug name in the combined dataset:
  1. Query PubChem REST API to get the canonical SMILES string
  2. Convert SMILES -> 2048-bit Morgan Fingerprint using RDKit
  3. For each drug pair: concatenate both fingerprints -> 4096-dim vector

Outputs:
    data/processed/features.npz   ← X matrix  (N_pairs × 4096)
    data/processed/labels.npy     ← y vector   (N_pairs,)
    data/processed/pairs.csv      ← drug1, drug2, label (successful pairs only)
    data/processed/drug_smiles.csv← cache of drug->SMILES lookups

Usage:
    python src/03_featurize.py

Note:
    PubChem API has a rate limit of ~5 requests/sec.
    The script uses a local cache so re-runs are instant.
    Expect ~15-40 minutes on first run for large datasets.
"""

import os
import time
import json
import requests
import numpy as np
import pandas as pd
from tqdm import tqdm

# RDKit
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, DataStructs
    RDKIT_OK = True
except ImportError:
    print("ERROR: rdkit not installed.  Run: pip install rdkit")
    raise

PROC_DIR    = os.path.join("data", "processed")
IN_CSV      = os.path.join(PROC_DIR, "combined.csv")
SMILES_CSV  = os.path.join(PROC_DIR, "drug_smiles.csv")
OUT_FEAT    = os.path.join(PROC_DIR, "features.npz")
OUT_LABELS  = os.path.join(PROC_DIR, "labels.npy")
OUT_PAIRS   = os.path.join(PROC_DIR, "pairs.csv")

FP_RADIUS   = 2        # Morgan radius (2 = ECFP4 - standard in drug research)
FP_BITS     = 2048     # Fingerprint size
PAIR_DIM    = FP_BITS * 2   # 4096 for a drug pair

PUBCHEM_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}/property/IsomericSMILES/JSON"
API_DELAY   = 0.25     # seconds between PubChem calls to stay under rate limit


# ─────────────────────────────────────────────
# SMILES Cache
# ─────────────────────────────────────────────

def load_smiles_cache():
    if os.path.exists(SMILES_CSV):
        df = pd.read_csv(SMILES_CSV)
        cache = dict(zip(df["drug"], df["smiles"]))
        print(f"[Cache] Loaded {len(cache):,} drug->SMILES entries from cache.")
        return cache
    return {}


def save_smiles_cache(cache):
    df = pd.DataFrame([{"drug": k, "smiles": v} for k, v in cache.items()])
    df.to_csv(SMILES_CSV, index=False)


# ─────────────────────────────────────────────
# PubChem Lookup
# ─────────────────────────────────────────────

def fetch_smiles(drug_name: str) -> str | None:
    """
    Query PubChem by drug name. Returns canonical SMILES or None.
    Handles network errors gracefully.
    """
    url = PUBCHEM_URL.format(requests.utils.quote(drug_name))
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            props = data.get("PropertyTable", {}).get("Properties", [])
            if props:
                return props[0].get("IsomericSMILES") or props[0].get("SMILES")
        return None
    except Exception:
        return None


def get_smiles_for_all(drug_names, cache):
    """
    Look up SMILES for every unique drug name using cache + PubChem API.
    Updates cache in-place and saves periodically.
    """
    missing = [d for d in drug_names if d not in cache]
    print(f"[PubChem] {len(drug_names):,} unique drugs | "
          f"{len(drug_names) - len(missing):,} cached | "
          f"{len(missing):,} to fetch")

    if not missing:
        return cache

    save_interval = 500
    for i, drug in enumerate(tqdm(missing, desc="Fetching SMILES", unit="drug")):
        smiles = fetch_smiles(drug)
        cache[drug] = smiles   # None if lookup failed
        time.sleep(API_DELAY)

        if (i + 1) % save_interval == 0:
            save_smiles_cache(cache)
            tqdm.write(f"  [Cache] Saved at {i+1} / {len(missing)}")

    save_smiles_cache(cache)
    n_found = sum(1 for v in cache.values() if v is not None)
    print(f"[PubChem] Done. Found SMILES for {n_found:,} / {len(drug_names):,} drugs.")
    return cache


# ─────────────────────────────────────────────
# Morgan Fingerprint
# ─────────────────────────────────────────────

def smiles_to_fingerprint(smiles: str) -> np.ndarray | None:
    """
    Convert a SMILES string to a NumPy binary array (Morgan fingerprint).
    Returns None if SMILES is invalid.
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=FP_RADIUS, nBits=FP_BITS)
        arr = np.zeros((FP_BITS,), dtype=np.float32)
        DataStructs.ConvertToNumpyArray(fp, arr)
        return arr
    except Exception:
        return None


# ─────────────────────────────────────────────
# Featurize All Pairs
# ─────────────────────────────────────────────

def build_feature_matrix(pairs_df, smiles_cache, fp_cache):
    """
    For each row in pairs_df (drug1, drug2, label):
    - Look up fingerprint for drug1 and drug2
    - Concatenate -> 4096-dim feature vector
    Returns X (N × 4096), y (N,), and successful_pairs DataFrame
    """
    X_rows   = []
    y_vals   = []
    good_idx = []

    skipped_no_smiles  = 0
    skipped_bad_smiles = 0

    print(f"\n[Featurize] Building feature matrix for {len(pairs_df):,} pairs...")
    for i, row in enumerate(tqdm(pairs_df.itertuples(index=False), total=len(pairs_df),
                                 desc="Featurizing pairs", unit="pair")):
        d1, d2, label = str(row.drug1), str(row.drug2), int(row.label)

        s1 = smiles_cache.get(d1)
        s2 = smiles_cache.get(d2)

        if s1 is None or s2 is None:
            skipped_no_smiles += 1
            continue

        # Use fingerprint cache (avoids re-computing for repeated drugs)
        if d1 not in fp_cache:
            fp_cache[d1] = smiles_to_fingerprint(s1)
        if d2 not in fp_cache:
            fp_cache[d2] = smiles_to_fingerprint(s2)

        fp1 = fp_cache[d1]
        fp2 = fp_cache[d2]

        if fp1 is None or fp2 is None:
            skipped_bad_smiles += 1
            continue

        # Pair vector: concatenate both fingerprints
        X_rows.append(np.concatenate([fp1, fp2]))
        y_vals.append(label)
        good_idx.append(i)

    if not X_rows:
        raise RuntimeError("No valid drug pairs featurized. Check SMILES cache and drug names.")

    X = np.array(X_rows, dtype=np.float32)
    y = np.array(y_vals, dtype=np.int32)

    print(f"\n[Featurize] Done.")
    print(f"  Feature matrix shape : {X.shape}  (pairs × {PAIR_DIM}-dim fingerprint)")
    print(f"  Successful pairs     : {len(X):,}")
    print(f"  Skipped (no SMILES)  : {skipped_no_smiles:,}")
    print(f"  Skipped (bad SMILES) : {skipped_bad_smiles:,}")

    successful_pairs = pairs_df.iloc[good_idx].reset_index(drop=True)
    return X, y, successful_pairs


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  DDI Research - Phase 3: Featurization")
    print("=" * 60)

    # Check feature matrix already exists
    if os.path.exists(OUT_FEAT) and os.path.exists(OUT_LABELS):
        data = np.load(OUT_FEAT)
        print(f"[Skip] Feature matrix already exists: shape={data['X'].shape}")
        print(f"  Delete {OUT_FEAT} to re-featurize.")
        print(f"\nNext step: python src/04_split.py")
        return

    # Load combined dataset
    if not os.path.exists(IN_CSV):
        print(f"ERROR: {IN_CSV} not found. Run: python src/02_preprocess.py first.")
        return

    df = pd.read_csv(IN_CSV)
    print(f"[Load] Combined dataset: {len(df):,} pairs")
    print(f"  Label distribution: {df['label'].value_counts().to_dict()}")

    # Get all unique drugs
    all_drugs = list(set(df["drug1"].tolist() + df["drug2"].tolist()))
    all_drugs = [str(d).strip().lower() for d in all_drugs]

    # SMILES lookups
    smiles_cache = load_smiles_cache()
    smiles_cache = get_smiles_for_all(all_drugs, smiles_cache)

    # Fingerprint cache (computed once per drug)
    fp_cache = {}

    # Build feature matrix
    X, y, good_pairs = build_feature_matrix(df, smiles_cache, fp_cache)

    # Save outputs
    np.savez_compressed(OUT_FEAT, X=X)
    np.save(OUT_LABELS, y)
    good_pairs.to_csv(OUT_PAIRS, index=False)

    print("\n" + "=" * 60)
    print("  FEATURIZATION SUMMARY")
    print("=" * 60)
    print(f"  Features saved  -> {OUT_FEAT}   shape={X.shape}")
    print(f"  Labels saved    -> {OUT_LABELS}  shape={y.shape}")
    print(f"  Pairs saved     -> {OUT_PAIRS}   rows={len(good_pairs):,}")
    print(f"\nNext step: python src/04_split.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
