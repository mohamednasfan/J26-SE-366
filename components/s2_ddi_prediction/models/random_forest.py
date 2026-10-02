"""Random-forest classifier."""

from sklearn.ensemble import RandomForestClassifier


def create_model(random_state: int = 42) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200, max_depth=20, random_state=random_state, n_jobs=-1
    )
