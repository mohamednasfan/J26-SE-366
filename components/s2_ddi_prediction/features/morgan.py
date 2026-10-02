"""Morgan fingerprint generation with explicit validation."""

from __future__ import annotations

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, DataStructs
except ImportError as exc:  # pragma: no cover - depends on environment
    raise ImportError("RDKit is required for Morgan fingerprints") from exc


def fingerprint_from_smiles(
    smiles: str, radius: int = 2, n_bits: int = 2048
) -> np.ndarray:
    """Return a binary Morgan fingerprint for one valid SMILES string."""
    if not isinstance(smiles, str) or not smiles.strip():
        raise ValueError("smiles must be a non-empty string")
    if radius < 0 or n_bits <= 0:
        raise ValueError("radius must be non-negative and n_bits must be positive")

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError("Invalid SMILES string")

    fingerprint = AllChem.GetMorganFingerprintAsBitVect(
        molecule, radius=radius, nBits=n_bits
    )
    result = np.zeros(n_bits, dtype=np.float32)
    DataStructs.ConvertToNumpyArray(fingerprint, result)
    return result


def pair_fingerprint(
    first_smiles: str, second_smiles: str, radius: int = 2, n_bits: int = 2048
) -> np.ndarray:
    """Concatenate two fingerprints into the model's pair representation."""
    return np.concatenate(
        [
            fingerprint_from_smiles(first_smiles, radius, n_bits),
            fingerprint_from_smiles(second_smiles, radius, n_bits),
        ]
    )
