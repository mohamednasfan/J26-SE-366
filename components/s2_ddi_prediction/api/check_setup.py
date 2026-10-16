from pathlib import Path

component_dir = Path(__file__).resolve().parents[1]

files = {
    "Model": "models/structure_sensitivity/standard/xgboost.ubj",
    "Thresholds": "evaluation/results/selected_thresholds.json",
    "Fingerprints": "data/processed/drug_fingerprints.npz",
    "Drug names": "data/processed/drug_name_catalogue.csv",
}

for name, relative_path in files.items():
    path = component_dir / relative_path
    print(f"{'FOUND' if path.is_file() else 'MISSING'}: {name}")