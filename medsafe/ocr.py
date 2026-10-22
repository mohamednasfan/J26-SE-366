"""Research prescription OCR with optional existing fine-tuned TrOCR checkpoint.

TrOCR confidence is intentionally unavailable: an unreviewed prediction can
never clear a clinical safety check merely because a checkpoint exists.
"""
from io import BytesIO
import statistics
import os
import shutil
import difflib
import re
from PIL import Image, ImageOps, UnidentifiedImageError
try:
    import pytesseract
    from pytesseract import Output
    from pathlib import Path
    _tesseract_candidates = [
        Path(__file__).resolve().parent.parent / 'runtime_tools' / 'tesseract' / 'tesseract.exe',
        Path(os.getenv('TESSERACT_CMD', '')) if os.getenv('TESSERACT_CMD') else None,
        Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe'),
        Path(r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'),
    ]
    for _candidate in _tesseract_candidates:
        if _candidate and _candidate.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(_candidate)
            break
except ImportError:
    pytesseract = None
    Output = None


def tesseract_executable() -> str | None:
    """Return the configured/detected Tesseract executable, if available."""
    if pytesseract is None:
        return None
    configured = getattr(pytesseract.pytesseract, 'tesseract_cmd', None)
    if configured and configured != 'tesseract' and Path(configured).is_file():
        return str(Path(configured))
    for candidate in _tesseract_candidates if '_tesseract_candidates' in globals() else []:
        if candidate and candidate.is_file():
            return str(candidate)
    return shutil.which('tesseract')

MAX_IMAGE_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 15_000_000


def decode_image(data: bytes) -> Image.Image:
    if not data or len(data)>MAX_IMAGE_BYTES:
        raise ValueError('Image is empty or exceeds 8 MiB limit.')
    try:
        with Image.open(BytesIO(data)) as im:
            if im.format not in ('JPEG','PNG','WEBP'):
                raise ValueError('Only JPEG, PNG or WEBP images are allowed.')
            im = ImageOps.exif_transpose(im)
            if im.width<64 or im.height<32:
                raise ValueError('Image dimensions too small for meaningful OCR.')
            if im.width*im.height>15_000_000:
                raise ValueError('Image pixel count exceeds limit.')
            return im.convert('RGB')
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc:
        raise ValueError('Invalid or unsafe image format.') from exc


def _tesseract(image: Image.Image) -> dict:
    if pytesseract is None:
        raise RuntimeError('pytesseract is not installed; install requirements-product.txt for the baseline engine.')
    processed=ImageOps.autocontrast(ImageOps.grayscale(image))
    try:
        data=pytesseract.image_to_data(processed,config='--psm 6',output_type=Output.DICT)
        transcript=pytesseract.image_to_string(processed,config='--psm 6').strip()
    except (pytesseract.TesseractNotFoundError,RuntimeError) as exc:
        raise RuntimeError('Tesseract executable unavailable; install the OCR dependency.') from exc
    conf=[]
    for word,score in zip(data['text'],data['conf']):
        if not str(word).strip():continue
        try: s=float(score)
        except (TypeError,ValueError):continue
        if 0<=s<=100:conf.append(s/100)
    transcript = _normalize_ocr_labels(transcript)
    return {'text':transcript,'confidence':round(statistics.mean(conf),3) if conf else 0.0,
            'engine':'tesseract','confident_token_count':sum(c>=.85 for c in conf),
            'confidence_is_calibrated':False, 'region_count':None,
            'segmentation_method':'tesseract_full_page_layout'}


def _normalize_ocr_labels(transcript: str) -> str:
    """Repair only near-miss structured labels, never medication content.

    Baseline OCR commonly emits `Dawe`, `Poute`, or a replacement character
    before `age`. Normalizing the label lets the conservative extractor inspect
    the value while preserving the OCR text as review evidence.
    """
    labels = ('medicine', 'medication', 'drug', 'name', 'dose', 'dosage',
              'amount', 'frequency', 'freq', 'schedule', 'age', 'route',
              'weight', 'strength')
    output=[]
    for raw in transcript.splitlines():
        line=raw.strip()
        if not line:
            output.append(raw); continue
        match=re.match(r'^([^:;,]{2,24})(\s*[:;,]\s*)(.*)$', line)
        if not match:
            output.append(raw); continue
        candidate=match.group(1).strip().lower().replace('\ufffd','').strip()
        best=max(labels, key=lambda label: difflib.SequenceMatcher(None,candidate,label).ratio())
        score=difflib.SequenceMatcher(None,candidate,best).ratio()
        if score >= 0.55:
            output.append(f'{best}: {match.group(3).strip()}')
        else:
            output.append(raw)
    return '\n'.join(output).strip()


def _trocr(image: Image.Image) -> dict:
    from .segments import propose_text_regions
    from .trocr import infer_regions
    regions,locations=propose_text_regions(image)
    if not regions:
        return {'text':'','confidence':None,'engine':'trocr_notebook44_finetuned',
                'confident_token_count':None,'confidence_is_calibrated':False,
                'region_count':0,'segmentation_method':'opencv_layout_proposals',
                'warnings':['NO_TEXT_REGIONS_DETECTED']}
    words=infer_regions(regions)
    if len(words)!=len(regions):
        raise RuntimeError('OCR model returned a different number of predictions than text-region inputs; no result accepted.')
    # Reconstruct reading lines from region coordinates; joining each crop with
    # a newline would split 'Medicine: ExampleDrug' into invalid fields.
    placed=[]
    for label, box in zip(words,locations):
        if label.strip():
            placed.append((label.strip(),box,(box['y1']+box['y2'])/2,max(1,box['y2']-box['y1'])))
    lines=[]
    for word,box,cy,bh in sorted(placed,key=lambda v:v[2]):
        # Never join different prescription rows solely because a large
        # bounding region overlaps them. Tall fallback tiles remain review-only.
        matches=[line for line in lines if abs(line['center']-cy)<=max(9,min(line['height'],bh)*0.4)]
        if matches:
            line=matches[0]
            line['tokens'].append((box['x1'],word))
            n=len(line['tokens'])
            line['center']=(line['center']*(n-1)+cy)/n
            line['height']=max(line['height'],bh)
        else:
            lines.append({'center':cy,'height':bh,'tokens':[(box['x1'],word)]})
    lines.sort(key=lambda row:row['center'])
    transcript='\n'.join(' '.join(label for x,label in sorted(line['tokens'])) for line in lines)
    uncertain_tiles=sum(b.get('proposal_kind')=='REVIEW_TILE_FROM_MERGED_CONTOUR' for b in locations)
    review_predictions=[{'region_index':i+1,'text_candidate':word,
                         'box':box,'geometry_verified':False}
                        for i,(word,box) in enumerate(zip(words,locations))]
    return {'text':transcript,'confidence':None,
            'engine':'trocr_notebook44_finetuned','confident_token_count':None,
            'confidence_is_calibrated':False,'region_count':len(regions),'detected_line_count':len(lines),
            'segmentation_method':'opencv_layout_proposals',
            'warnings':['CROP_SEGMENTATION_UNVERIFIED','TROCR_VALIDATION_NOT_CLINICAL']+
                       (['MERGED_REGION_TILES_REQUIRE_REVIEW'] if uncertain_tiles else []),
            'uncertain_geometry_region_count':uncertain_tiles,
            'region_predictions_for_review':review_predictions,
            'region_coordinates':locations}


def ocr_image(data: bytes, *, engine: str='auto') -> dict:
    image=decode_image(data)
    if engine not in ('auto','trocr','tesseract'):
        raise ValueError('Unknown OCR engine. Choose auto, trocr or tesseract.')
    if engine=='auto':
        from .trocr import checkpoint_status, ModelNotReady
        import os
        state=checkpoint_status()
        # An explicitly selected, incomplete checkpoint must never be hidden by fallback.
        if os.getenv('MEDSAFE_TROCR_MODEL_DIR') and not state['ready_for_load']:
            raise ModelNotReady('Configured TrOCR model folder is missing required checkpoint files.')
        engine='trocr' if state['ready_for_load'] else 'tesseract'
    if engine=='trocr':
        return _trocr(image)
    return _tesseract(image)
