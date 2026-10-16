from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import shap


class DDIPredictor:
    EXCLUDED_DRUGS = {
        "DB00515", "DB00526", "DB00958", "DB11630", "DB13145"
    }

    def __init__(self):
        self.component_dir = Path(__file__).resolve().parents[1]

        self.model = joblib.load(
            self.component_dir / "models/random_forest.joblib"
        )
        self.cold_start_model = joblib.load(
            self.component_dir / "models/cold_start/random_forest.joblib"
        )

        with open(
            self.component_dir
            / "evaluation/results/selected_thresholds.json",
            encoding="utf-8-sig"
        ) as file:
            self.threshold = float(
                json.load(file)["thresholds"]["Random Forest"]
            )

        with open(
            self.component_dir / "results/cold_start/rf_settings.json",
            encoding="utf-8",
        ) as file:
            self.cold_start_threshold = float(
                json.load(file)["selected_threshold"]
            )

        with np.load(
            self.component_dir / "data/processed/drug_fingerprints.npz"
        ) as saved:
            self.fingerprints = {
                str(drug_id): fp.copy()
                for drug_id, fp in zip(
                    saved["drug_ids"], saved["fingerprints"]
                )
            }

        self.catalogue = pd.read_csv(
            self.component_dir / "data/processed/drug_name_catalogue.csv",
            dtype={"drug_id": str}
        )

        self.catalogue = self.catalogue[
            self.catalogue["drug_id"].isin(self.fingerprints)
            & ~self.catalogue["drug_id"].isin(self.EXCLUDED_DRUGS)
        ].copy()

        if self.catalogue["drug_id"].duplicated().any():
            raise ValueError("Duplicate drug IDs in the catalogue.")

        self.names = self.catalogue.set_index("drug_id")[
            "display_name"
        ].to_dict()

        if self.model.n_features_in_ != 4096:
            raise ValueError("Unexpected model feature count.")
        if self.cold_start_model.n_features_in_ != 4096:
            raise ValueError("Unexpected cold-start model feature count.")
        self.explainer = shap.TreeExplainer(self.model)
        self.cold_start_explainer = shap.TreeExplainer(self.cold_start_model)

    def search(self, query, limit=10):
        query = str(query).strip()
        if not query:
            return []

        limit = max(1, min(int(limit), 50))

        matches = self.catalogue[
            self.catalogue["display_name"].str.contains(
                query, case=False, regex=False, na=False
            )
            | self.catalogue["drug_id"].str.contains(
                query, case=False, regex=False, na=False
            )
        ]

        return matches[
            ["drug_id", "display_name", "selection_label"]
        ].head(limit).to_dict("records")

    def predict(self, drug1_id, drug2_id, top_k=10, mode="standard"):
        if mode not in {"standard", "cold_start"}:
            raise ValueError("mode must be 'standard' or 'cold_start'.")

        if not isinstance(drug1_id, str) or not isinstance(drug2_id, str):
            raise ValueError("Drug IDs must be strings.")

        drug1_id = drug1_id.strip().upper()
        drug2_id = drug2_id.strip().upper()

        if drug1_id == drug2_id:
            raise ValueError("Select two different drugs.")

        if not isinstance(top_k, int) or not 1 <= top_k <= 4096:
            raise ValueError("top_k must be between 1 and 4096.")

        for drug_id in [drug1_id, drug2_id]:
            if drug_id in self.EXCLUDED_DRUGS:
                raise ValueError(f"{drug_id}: unresolved structure.")
            if drug_id not in self.names:
                raise ValueError(f"{drug_id}: unsupported catalogue selection.")

        a = self.fingerprints[drug1_id].astype(np.int8)
        b = self.fingerprints[drug2_id].astype(np.int8)

        x = np.concatenate(
            [a + b, np.abs(a - b)]
        ).reshape(1, -1)

        model = (
            self.cold_start_model
            if mode == "cold_start"
            else self.model
        )
        threshold = (
            self.cold_start_threshold
            if mode == "cold_start"
            else self.threshold
        )
        explainer = (
            self.cold_start_explainer
            if mode == "cold_start"
            else self.explainer
        )

        positive_column = list(model.classes_).index(1)
        score = float(
            model.predict_proba(x)[0, positive_column]
        )

        explanation = explainer(x)
        shap_values = np.asarray(explanation.values)
        values = shap_values[0, :, positive_column]
        base = float(
            np.asarray(explanation.base_values)[0, positive_column]
        )

        if not np.isclose(base + values.sum(), score, atol=1e-6):
            raise RuntimeError("Explanation reconstruction failed.")

        top = np.argsort(np.abs(values))[-top_k:][::-1]

        return {
            "drug1_id": drug1_id,
            "drug1_name": self.names[drug1_id],
            "drug2_id": drug2_id,
            "drug2_name": self.names[drug2_id],
            "model": f"{mode}_random_forest",
            "interaction_flag": bool(score >= threshold),
            "model_score": score,
            "threshold": threshold,
            "prediction_mode": mode,
            "severity": None,
            "intended_use": "research_prototype",
            "explanation": {
                "method": "Tree SHAP; model probability contribution",
                "units": "probability",
                "base_value": base,
                "total_contribution": float(values.sum()),
                "omitted_contribution": float(
                    values.sum() - values[top].sum()
                ),
                "top_features": [
                    {
                        "feature_group": (
                            "fingerprint_sum" if i < 2048
                            else "fingerprint_absolute_difference"
                        ),
                        "bit_index": int(i % 2048),
                        "feature_value": int(x[0, i]),
                        "contribution": float(values[i])
                    }
                    for i in top
                ]
            }
        }


if __name__ == "__main__":
    predictor = DDIPredictor()
    print("Predictor loaded successfully.")
    print("Metformin search:")
    print(json.dumps(predictor.search("metformin"), indent=2))