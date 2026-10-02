"""
Phase 1 - Data Download Script (Verified Sources)
===================================================================
Downloads DDI datasets from verified, publicly accessible sources:

1. BIOSNAP (ChCh-Miner)  -> Stanford SNAP  (direct .tsv.gz link)
2. DrugBank DDI          -> Mendeley Data  (publicly hosted CSV)
3. TWOSIDES              -> Manual instructions (too large for direct)

All sources are free for academic use.
"""

import os
import io
import gzip
import requests
import pandas as pd

DATA_DIR = "data"


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Created directory: {path}")


def download_biosnap():
    """
    Download BIOSNAP ChCh-Miner DDI dataset from Stanford SNAP.
    Direct .tsv.gz download - no login required.
    ~1,514 drugs, ~48,514 interaction pairs.
    """
    out_csv = os.path.join(DATA_DIR, "biosnap.csv")
    if os.path.exists(out_csv):
        df = pd.read_csv(out_csv)
        print(f"[BIOSNAP] Already exists - {len(df):,} rows. Skipping.")
        return df

    url = "http://snap.stanford.edu/biodata/datasets/10001/files/ChCh-Miner_durgbank-chem-chem.tsv.gz"
    print(f"\n[BIOSNAP] Downloading from Stanford SNAP...")
    print(f"  URL: {url}")

    try:
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()

        # Decompress gzip in memory
        raw = gzip.decompress(r.content)
        text = raw.decode("utf-8")

        # Parse as TSV - columns: Drug1, Drug2 (edge list of interacting pairs)
        df = pd.read_csv(io.StringIO(text), sep="\t", comment="#", header=None)
        df.columns = ["Drug1", "Drug2"] if df.shape[1] == 2 else df.columns

        # All rows are positive interactions - add a label column
        df["label"] = 1

        df.to_csv(out_csv, index=False)
        print(f"  OK Saved {out_csv}  ({len(df):,} interaction pairs)")
        print(f"  Columns: {list(df.columns)}")
        print(df.head(3).to_string(index=False))
        return df

    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def download_drugbank_direct():
    """Download DrugBank dataset directly from Harvard Dataverse (TDC mirror)."""
    out_csv = os.path.join(DATA_DIR, "drugbank.csv")
    if os.path.exists(out_csv):
        df = pd.read_csv(out_csv)
        print(f"[DrugBank] Already exists - {len(df):,} rows. Skipping.")
        return df

    print(f"\n[DrugBank] Downloading directly from TDC Dataverse mirror...")
    import urllib.request
    import shutil
    try:
        # File ID 4139573 corresponds to drugbank.tab in the TDC Dataverse
        url = 'https://dataverse.harvard.edu/api/access/datafile/4139573'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        temp_tab = os.path.join(DATA_DIR, "drugbank.tab")
        with urllib.request.urlopen(req) as response, open(temp_tab, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
            
        # Read the tab-separated file and save it as a standard CSV
        df = pd.read_csv(temp_tab, sep='\t')
        df.to_csv(out_csv, index=False)
        os.remove(temp_tab)
        
        print(f"  OK Saved {out_csv}  ({len(df):,} interaction pairs)")
        return df
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


def download_twosides_direct():
    """Download TWOSIDES dataset directly from Harvard Dataverse (TDC mirror)."""
    out_csv = os.path.join(DATA_DIR, "twosides.csv")
    if os.path.exists(out_csv):
        df = pd.read_csv(out_csv)
        print(f"[TWOSIDES] Already exists - {len(df):,} rows. Skipping.")
        return df

    print(f"\n[TWOSIDES] Downloading directly from TDC Dataverse mirror...")
    import urllib.request
    import shutil
    try:
        # File ID 4139574 corresponds to twosides.csv in the TDC Dataverse
        url = 'https://dataverse.harvard.edu/api/access/datafile/4139574'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(out_csv, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
            
        df = pd.read_csv(out_csv)
        print(f"  OK Saved {out_csv}  ({len(df):,} interaction pairs)")
        return df
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


if __name__ == "__main__":
    print("=" * 55)
    print("  DDI Research - Phase 1: Data Download")
    print("=" * 55)

    ensure_dir(DATA_DIR)

    # 1. BIOSNAP - Direct download (Stanford SNAP)
    biosnap_df = download_biosnap()

    # 2. DrugBank - Direct automated download
    drugbank_df = download_drugbank_direct()

    # 3. TWOSIDES - Direct automated download
    twosides_df = download_twosides_direct()

    # Summary
    print("\n" + "=" * 55)
    print("  DOWNLOAD SUMMARY")
    print("=" * 55)
    for fname in ["biosnap.csv", "drugbank.csv", "twosides.csv"]:
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            df = pd.read_csv(path)
            print(f"  OK  {fname:20s} {len(df):>10,} rows")
        else:
            print(f"  --  {fname:20s} Not downloaded yet (see instructions)")

    print("\nNext step: python src/02_preprocess.py")
    print("=" * 55)
