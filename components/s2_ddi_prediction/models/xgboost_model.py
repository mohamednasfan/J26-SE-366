"""XGBoost classifier."""

from xgboost import XGBClassifier


def create_model(random_state: int = 42) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=500,
        learning_rate=0.05,
        random_state=random_state,
        n_jobs=-1,
        eval_metric="logloss",
    )
