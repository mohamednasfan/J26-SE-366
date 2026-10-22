"""Inference adapter for the existing Notebook 44 fine-tuned TrOCR checkpoint.

A checkpoint is loaded only from explicitly configured local files. The model
is NEVER downloaded implicitly, trained, updated, or claimed clinically tested.
Input regions are automatically generated proposals, NOT verified word boxes.
"""
from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache
from typing import Sequence
from PIL import Image

# Project's *previously existing* fine-tuned model, saved by Notebook 44.
NOTEBOOK44_CHECKPOINT = (
    '/content/drive/MyDrive/MedSafe_AI_Project/02_models/'
    'trocr_finetuned_official_source_dev_notebook44/943e9bd2b5f1a54d/'
    'best_model_DEVELOPMENT_ONLY'
)
_REQUIRED = ('config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
             'processor_config.json', 'preprocessor_config.json')


def configured_checkpoint() -> Path | None:
    raw = os.getenv('MEDSAFE_TROCR_MODEL_DIR', '').strip()
    if raw:
        return Path(raw).expanduser()
    default = Path(NOTEBOOK44_CHECKPOINT)
    return default if default.is_dir() else None


def checkpoint_status() -> dict:
    path = configured_checkpoint()
    if path is None:
        return {'configured': False, 'files_present': False, 'ready_for_load': False,
                'model_name': 'Notebook44 fine-tuned TrOCR (development-only)',
                'reason': 'Mount Drive or set MEDSAFE_TROCR_MODEL_DIR to the fine-tuned model folder.'}
    missing = [name for name in _REQUIRED if not (path / name).is_file()]
    return {'configured': True, 'files_present': not missing,
            'ready_for_load': not missing,
            'model_name': 'Notebook44 fine-tuned TrOCR (development-only)',
            'missing_files': missing, 'weights_verified_by_inference': False}


class ModelNotReady(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_model(model_path: str):
    # Lazy optional heavy dependencies: importing this app must remain fast.
    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except ImportError as exc:
        raise ModelNotReady('Install the optional model dependencies from requirements-model.txt.') from exc
    model_dir = Path(model_path)
    missing = [name for name in _REQUIRED if not (model_dir / name).is_file()]
    if missing:
        raise ModelNotReady('Fine-tuned TrOCR checkpoint incomplete (missing ' + ', '.join(missing) + ').')
    try:
        processor = TrOCRProcessor.from_pretrained(model_path, local_files_only=True)
        model = VisionEncoderDecoderModel.from_pretrained(model_path, local_files_only=True)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model.to(device).eval()
        return processor, model, device
    except (OSError, ValueError, RuntimeError) as exc:
        raise ModelNotReady('The fine-tuned TrOCR checkpoint could not be loaded; verify its files and compatible dependencies.') from exc


def infer_regions(images: Sequence[Image.Image], *, max_new_tokens: int = 64) -> list[str]:
    """Run real model inference. Never silently fall back to a different model."""
    status = checkpoint_status()
    if not status['ready_for_load']:
        raise ModelNotReady(status.get('reason') or 'Missing fine-tuned TrOCR checkpoint files.')
    if len(images) > 384:
        raise ValueError('Maximum 384 proposed text regions per image.')
    if not images:
        return []
    import torch
    path = str(configured_checkpoint().resolve())
    processor, model, device = _load_model(path)
    predictions = []
    batch_size = 4 if device == 'cuda' else 1
    with torch.inference_mode():
        for start in range(0,len(images),batch_size):
            batch = [im.convert('RGB') for im in images[start:start+batch_size]]
            pixels = processor(images=batch, return_tensors='pt').pixel_values.to(device)
            ids = model.generate(pixels, max_new_tokens=max_new_tokens, num_beams=1)
            predictions.extend(x.strip() for x in processor.batch_decode(ids,skip_special_tokens=True))
    return predictions
