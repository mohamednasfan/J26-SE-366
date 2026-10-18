"""Logistic-regression baseline."""

from sklearn.linear_model import LogisticRegression


def create_model(random_state: int = 42) -> LogisticRegression:
    return LogisticRegression(C=1.0, max_iter=1000, random_state=random_state)
