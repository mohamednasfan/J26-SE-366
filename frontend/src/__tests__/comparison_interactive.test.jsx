import React from 'react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';

vi.mock('../lib/api.js', async original=>{
 const real=await original();
 return {...real,request:vi.fn()};
});
import {request} from '../lib/api.js';
import OCRComparison from '../features/OCRComparison.jsx';

afterEach(()=>{cleanup();vi.resetAllMocks()});

const example=(text,detected)=>({
 status:'COMPLETED',text,elapsed_seconds:0.27,region_count:2,warnings:['OCR_NOT_VERIFIED'],
 extraction:{field_coverage:{detected,possible:5},
  medications:[{index:1,candidate_only:false,fields:{medicine:text.includes('Beta')?'Beta':'Alpha',dose:'10 mg'},missing_fields:['frequency','age','route']}]},
 reference_metrics:null
});

describe('live four-engine comparison interactions',()=>{
 it('runs all engines and switches the displayed transcription and extracted fields',async()=>{
  request.mockResolvedValue({
   schema:'medsafe.ocr_comparison.v2',completed_engines:2,n_engines:4,
   preprocessing:{mode:'none'},reference_used:false,engines:{
    tesseract:example('Medicine: Alpha\nDose: 10 mg',2),
    easyocr:{status:'UNAVAILABLE',reason:'Optional OCR package is missing.'},
    paddleocr:example('Medicine: Beta\nDose: 10 mg',2),
    craft_trocr:{status:'UNAVAILABLE',reason:'Notebook 44 checkpoint missing'}
   }
  });
  const file=new File(['%PDF-sample'],'fictional.pdf',{type:'application/pdf'});
  render(<OCRComparison embedded initialFile={file}/>);
  fireEvent.click(screen.getByRole('button',{name:/run four-model comparison/i}));
  expect(await screen.findByText('Results on this prescription')).toBeTruthy();
  expect(screen.getByText(/Medicine: Alpha/)).toBeTruthy();
  expect(screen.getByText(/No verified transcription provided/)).toBeTruthy();
  const switcher=screen.getByRole('group',{name:'Inspect OCR engine results'});
  fireEvent.click(within(switcher).getByRole('button',{name:'PaddleOCR'}));
  expect(screen.getByText(/Medicine: Beta/)).toBeTruthy();
  fireEvent.click(within(switcher).getByRole('button',{name:'CRAFT + TrOCR'}));
  expect(screen.getByText(/Notebook 44 checkpoint missing/)).toBeTruthy();
  expect(request).toHaveBeenCalledTimes(1);
  const payload=request.mock.calls[0][1].body;
  expect(payload.get('file').name).toBe('fictional.pdf');
  expect(payload.get('reference_text')).toBeNull();
 });
});
