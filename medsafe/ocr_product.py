"""CRAFT text detection + the project's existing Notebook 44 fine-tuned TrOCR.

The research checkpoint must be mounted locally. No silent pretrained fallback,
model download, or claim that OCR constitutes clinical verification.
"""
from __future__ import annotations
from functools import lru_cache
from io import BytesIO
import os
from pathlib import Path
from PIL import Image, ImageOps
from .ocr import decode_image, _tesseract, tesseract_executable

from .trocr import configured_checkpoint, checkpoint_status, _load_model

_RESEARCH_MODEL = configured_checkpoint()
MODEL_ID = str(_RESEARCH_MODEL) if _RESEARCH_MODEL else 'NOTEBOOK44_CHECKPOINT_NOT_CONFIGURED'
MODEL_LOAD_ID = MODEL_ID

class OCRUnavailable(RuntimeError):
    pass


def status():
    import importlib.util, shutil
    try:
        import torch
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        torch_installed = True
    except ImportError:
        device = 'not installed'
        torch_installed = False
    checkpoint=checkpoint_status()
    craft_available=importlib.util.find_spec('easyocr') is not None
    transformers_available=importlib.util.find_spec('transformers') is not None
    trocr_ready=bool(checkpoint.get('ready_for_load') and craft_available and transformers_available and torch_installed)
    return {
        'default': 'tesseract', 'detector': 'Tesseract full-page OCR',
        'benchmark_engines': {
            'tesseract': tesseract_executable() is not None,
            'easyocr': importlib.util.find_spec('easyocr') is not None,
            'paddleocr': importlib.util.find_spec('paddleocr') is not None and importlib.util.find_spec('paddle') is not None,
            'trocr': trocr_ready,
            'craft_trocr': trocr_ready,
        },
        'recognizer': str(configured_checkpoint() or 'NOTEBOOK44_CHECKPOINT_NOT_CONFIGURED'),
        'notebook44_checkpoint':checkpoint, 'torch_installed': torch_installed,
        'craft_installed': craft_available,
        'transformers_installed': transformers_available,
        'tesseract_installed': tesseract_executable() is not None,
        'device': device,
        'weights_loaded': _recognizer.cache_info().currsize > 0,
        'checkpoint_downloaded_automatically': False,
        'craft_detector_weights_may_download_at_first_use': craft_available,
        'clinical_accuracy_validated': False,
    }


@lru_cache(maxsize=1)
def _craft():
    try:
        import easyocr
        import torch
        return easyocr.Reader(['en'], gpu=torch.cuda.is_available(), detector=True, recognizer=False, verbose=False)
    except Exception as exc:
        raise OCRUnavailable('CRAFT detector could not load. Install requirements-ocr.txt and allow first-run CRAFT weights download. ' + str(exc)[:250]) from exc


@lru_cache(maxsize=1)
def _recognizer():
    """Use exactly the same Notebook 44 checkpoint as the research API."""
    state=checkpoint_status()
    if not state['ready_for_load']:
        raise OCRUnavailable(
            'Notebook 44 fine-tuned TrOCR checkpoint is unavailable. '
            +str(state.get('reason') or state.get('missing_files') or 'Missing model files')
        )
    path=configured_checkpoint()
    try:
        return _load_model(str(path.resolve()))
    except Exception as exc:
        raise OCRUnavailable('Notebook 44 checkpoint loading failed: '+str(exc)[:260]) from exc


def _boxes(image):
    import numpy as np
    reader = _craft()
    # EasyOCR returns horizontal boxes [x_min, x_max, y_min, y_max];
    # use the original full-page image, never fixed coordinates.
    horizontal, freeform = reader.detect(np.asarray(image), min_size=12, text_threshold=0.55,
                                         low_text=0.3, link_threshold=0.35)
    raw = horizontal[0] if horizontal else []
    width, height = image.size
    boxes = []
    for bounds in raw:
        if len(bounds) != 4: continue
        x1,x2,y1,y2 = [int(round(float(v))) for v in bounds]
        pad = max(3, round((y2-y1) * 0.12))
        x1,x2 = max(0,x1-pad), min(width,x2+pad)
        y1,y2 = max(0,y1-pad), min(height,y2+pad)
        if x2-x1<9 or y2-y1<9:continue
        boxes.append((x1,y1,x2,y2))
    # Rotated text polygons from CRAFT are supported by their safe axis-aligned
    # bounding rectangles; they remain UNVERIFIED proposals.
    for polygon in (freeform[0] if freeform else []):
        if len(polygon)<3:continue
        xs=[float(p[0]) for p in polygon]; ys=[float(p[1]) for p in polygon]
        x1,y1,x2,y2=max(0,int(min(xs))-3),max(0,int(min(ys))-3),min(width,int(max(xs))+4),min(height,int(max(ys))+4)
        if x2-x1>=9 and y2-y1>=9:boxes.append((x1,y1,x2,y2))
    # Approximate deduplication, no medicine name heuristics or template coordinates.
    kept=[]
    for b in sorted(boxes,key=lambda b:(b[1],b[0])):
        if any(_iou(b,other)>0.87 for other in kept):continue
        kept.append(b)
    return kept[:256]


def _iou(a,b):
    x1,y1,x2,y2=max(a[0],b[0]),max(a[1],b[1]),min(a[2],b[2]),min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    area=lambda r:max(0,r[2]-r[0])*max(0,r[3]-r[1])
    return inter/max(1,area(a)+area(b)-inter)


def _sequence(boxes):
    # Page ordering is based on dynamic geometry; no hand-entered page template.
    order=sorted(range(len(boxes)),key=lambda k:((boxes[k][1]+boxes[k][3])/2,boxes[k][0]))
    rows=[]
    for k in order:
        x1,y1,x2,y2=boxes[k]
        cy=(y1+y2)/2; height=y2-y1
        nearest=None
        for row in rows:
            if abs(cy-row['cy'])<=min(height,row['height'])*0.33:
                nearest=row;break
        if nearest is None:
            rows.append({'cy':cy,'height':height,'indices':[k]})
        else:
            nearest['indices'].append(k)
            nearest['cy']=(nearest['cy']*(len(nearest['indices'])-1)+cy)/len(nearest['indices'])
    rows.sort(key=lambda r:r['cy'])
    return [sorted(r['indices'],key=lambda k:boxes[k][0]) for r in rows]


def _trocr_lines(image:Image.Image, boxes):
    import torch
    processor, model, device = _recognizer()
    texts=[]
    batch_size=4 if device=='cuda' else 1
    with torch.inference_mode():
        for start in range(0,len(boxes),batch_size):
            crops=[]
            for box in boxes[start:start+batch_size]:
                crop=image.crop(box).convert('RGB')
                # Give TrOCR a small, dynamic margin and a larger raster. This
                # improves thin handwritten strokes without using fixed page
                # coordinates or altering the recorded source geometry.
                margin=max(4, round(min(crop.size) * 0.08))
                crop=ImageOps.expand(crop, border=margin, fill='white')
                scale=max(1, min(3, round(160 / max(1, crop.height))))
                if scale > 1:
                    crop=crop.resize((crop.width*scale, crop.height*scale), Image.Resampling.LANCZOS)
                crops.append(crop)
            pixels=processor(images=crops,return_tensors='pt').pixel_values.to(device)
            ids=model.generate(pixels,max_new_tokens=96,num_beams=2,early_stopping=True)
            texts += [t.strip() for t in processor.batch_decode(ids,skip_special_tokens=True)]
    return texts


@lru_cache(maxsize=1)
def _easy_reader():
    import easyocr
    import torch
    return easyocr.Reader(['en'], gpu=torch.cuda.is_available(), verbose=False)


@lru_cache(maxsize=1)
def _paddle_reader():
    from paddleocr import PaddleOCR
    return PaddleOCR(
        lang='en', use_doc_orientation_classify=False,
        use_doc_unwarping=False, use_textline_orientation=False,
        enable_mkldnn=False,
    )


def _paddle_regions(pages):
    """Normalize PaddleOCR 3.x result objects and numpy polygon arrays."""
    import math
    regions = []
    for page in pages or []:
        raw = getattr(page, 'json', None)
        data = raw() if callable(raw) else raw if isinstance(raw, dict) else page
        if not isinstance(data, dict):
            continue
        data = data.get('res', data)
        if not isinstance(data, dict):
            continue
        texts = data.get('rec_texts')
        polys = data.get('rec_polys')
        if polys is None or len(polys) == 0:
            polys = data.get('dt_polys')
        if polys is None or len(polys) == 0:
            polys = data.get('rec_boxes')
        scores = data.get('rec_scores')
        if texts is None or polys is None:
            continue
        for offset, text in enumerate(texts):
            if offset >= len(polys):
                break
            polygon = polys[offset]
            if polygon is None or len(polygon) == 0:
                continue
            # PaddleOCR can emit either 4-point polygons or [x1,y1,x2,y2].
            try:
                if len(polygon) == 4 and all(
                    isinstance(v, (int, float)) or not hasattr(v, '__len__') for v in polygon
                ):
                    x1, y1, x2, y2 = [int(float(v)) for v in polygon]
                else:
                    xs = [int(float(point[0])) for point in polygon]
                    ys = [int(float(point[1])) for point in polygon]
                    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            except (ValueError, TypeError, IndexError):
                continue
            if x2 <= x1 or y2 <= y1:
                continue
            score = None
            if scores is not None and offset < len(scores):
                try:
                    value = float(scores[offset])
                    if math.isfinite(value) and 0 <= value <= 1:
                        score = value
                except (TypeError, ValueError):
                    pass
            regions.append({
                'id': len(regions)+1, 'text': str(text).strip(),
                'box': [x1, y1, x2, y2],
                'verified': False, 'confidence': score,
            })
    return regions


def recognize(data:bytes,engine='craft_trocr'):
    image=decode_image(data)
    if engine=='tesseract':
        raw=_tesseract(image)
        return {'text':raw['text'],'engine':'tesseract','regions':[], 'boxes':[],
                'warnings':['TESSERACT_BASELINE_NOT_HANDWRITING_OPTIMIZED','OCR_NOT_VERIFIED'],
                'confidence':None,'width':image.width,'height':image.height}
    if engine == 'easyocr':
        try:
            import numpy as np
            items = _easy_reader().readtext(
                np.asarray(image), detail=1, paragraph=False
            )
        except Exception as exc:
            raise OCRUnavailable(
                'EasyOCR engine unavailable: ' + str(exc)[:250]
            ) from exc
        regions=[]
        for idx,(polygon,text,confidence) in enumerate(items,1):
            xs=[int(p[0]) for p in polygon]; ys=[int(p[1]) for p in polygon]
            regions.append({
                'id': idx, 'text': text.strip(),
                'box': [min(xs),min(ys),max(xs),max(ys)], 'verified':False,
                'confidence':float(confidence) if confidence is not None else None,
            })
        return {
            'text':'\n'.join(r['text'] for r in regions if r['text']).strip(),
            'engine':'easyocr','regions':regions,'boxes':[r['box'] for r in regions],
            'warnings':['EASYOCR_TEXT_UNVERIFIED','MODEL_CONFIDENCE_NOT_CLINICALLY_CALIBRATED'],
            'confidence':None,'width':image.width,'height':image.height,
        }
    if engine == 'paddleocr':
        try:
            import numpy as np
            result = _paddle_reader().predict(np.asarray(image))
            regions = _paddle_regions(result)
        except Exception as exc:
            raise OCRUnavailable(
                'PaddleOCR engine unavailable: ' + str(exc)[:250]
            ) from exc
        return {
            'text':'\n'.join(r['text'] for r in regions if r['text']).strip(),
            'engine':'paddleocr','regions':regions,'boxes':[r['box'] for r in regions],
            'warnings':['PADDLEOCR_TEXT_UNVERIFIED','MODEL_CONFIDENCE_NOT_CLINICALLY_CALIBRATED'],
            'confidence':None,'width':image.width,'height':image.height,
        }
    if engine!='craft_trocr':raise ValueError('Unsupported engine. Choose craft_trocr, easyocr, paddleocr, or tesseract.')
    # Never return an apparently successful empty OCR result when the
    # required fine-tuned recognition checkpoint is not installed.
    if not checkpoint_status().get('ready_for_load'):
        raise OCRUnavailable('Notebook 44 fine-tuned TrOCR checkpoint is missing or incomplete')
    boxes=_boxes(image)
    if not boxes:
        return {'text':'','engine':engine,'regions':[],'boxes':[],
                'warnings':['NO_CRAFT_REGIONS_DETECTED','OCR_NOT_VERIFIED','MANUAL_TRANSCRIPTION_REQUIRED'],
                'confidence':None,'width':image.width,'height':image.height}
    preds=_trocr_lines(image,boxes)
    if len(preds)!=len(boxes):raise OCRUnavailable('OCR region-prediction count mismatch; refusing incomplete result')
    lines=_sequence(boxes)
    text='\n'.join(' '.join(preds[idx] for idx in line if preds[idx]) for line in lines).strip()
    ordered=[idx for line in lines for idx in line]
    regions=[{'id':idx+1,'reading_order':position+1,'text':preds[idx],
              'box':list(boxes[idx]),'verified':False}
             for position,idx in enumerate(ordered)]
    return {'text':text,'engine':engine,'regions':regions,
            'boxes':[r['box'] for r in regions], 'warnings':['CRAFT_BOXES_UNVERIFIED','TROCR_TEXT_UNVERIFIED',
                                                           'TOKEN_CONFIDENCE_UNCALIBRATED'],
            'confidence':None,'width':image.width,'height':image.height}
