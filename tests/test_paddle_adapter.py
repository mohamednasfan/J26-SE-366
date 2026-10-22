"""Normalize real PaddleOCR 3.x numpy result shapes without model downloads."""
import numpy as np
from medsafe.ocr_product import _paddle_regions


def test_paddle_numpy_polygons_and_confidence():
    class Result:
        json={
            'res': {
                'rec_texts': ['Medicine: SYNTHMED-01','Dose: 10 mg'],
                'rec_polys': np.array([
                    [[8,12],[176,12],[176,38],[8,38]],
                    [[8,42],[145,42],[145,65],[8,65]],
                ],dtype=np.int32),
                'rec_scores': np.array([.96,.90],dtype=np.float32),
            }
        }
    rows=_paddle_regions([Result()])
    assert len(rows)==2
    assert rows[0]['text']=='Medicine: SYNTHMED-01'
    assert rows[0]['box']==[8,12,176,38]
    assert abs(rows[1]['confidence']-.9)<1e-5
    assert all(row['verified'] is False for row in rows)


def test_paddle_numpy_boxes_fallback_and_bad_confidence():
    class Result:
        json={'res':{
            'rec_texts':['Age: 22 years'],
            'rec_polys':np.empty((0,4,2),dtype=np.int32),
            'rec_boxes':np.array([[10,20,180,40]],dtype=np.int32),
            'rec_scores':np.array([np.nan]),
        }}
    rows=_paddle_regions([Result()])
    assert rows[0]['box']==[10,20,180,40]
    assert rows[0]['confidence'] is None


def test_paddle_missing_geometry_does_not_invent_regions():
    assert _paddle_regions([{'res':{'rec_texts':['Test'], 'rec_polys':[]}}])==[]
