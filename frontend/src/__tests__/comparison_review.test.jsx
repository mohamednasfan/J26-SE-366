import React from 'react';
import {describe,expect,it,vi} from 'vitest';
import {fireEvent,render,screen} from '@testing-library/react';
import {groupReviewFindings} from '../lib/findings.js';
import FindingsCenter from '../components/FindingsCenter.jsx';
import OCRComparison from '../features/OCRComparison.jsx';
import Upload from '../features/Upload.jsx';

describe('clear medication warnings',()=>{
 const issues=[
  {code:'MISSING_MEDICINE',severity:'BLOCK',message:'Medicine name not found.',medicine_index:1},
  {code:'MISSING_DOSE',severity:'BLOCK',message:'Dose is missing.',medicine_index:1},
  {code:'MISSING_FREQUENCY',severity:'BLOCK',message:'Frequency is missing.',medicine_index:1},
  {code:'MISSING_AGE',severity:'BLOCK',message:'Age missing.',medicine_index:1},
  {code:'REVIEWED_RULE_THRESHOLD_EXCEEDED',severity:'CAUTION',message:'Reviewed threshold exceeded.',medicine_index:2},
 ];
 it('groups correlated missing text and preserves real reviewed-rule alerts',()=>{
  const result=groupReviewFindings(issues);
  expect(result.missing).toHaveLength(1);
  expect(result.missing[0].fields).toEqual(['medicine','dose','frequency','age']);
  expect(result.reviewedFlags).toHaveLength(1);
  expect(result.total).toBe(5);
 });
 it('shows one review card for multiple missing fields and a separate rule warning',()=>{
  const onEdit=vi.fn();
  render(<FindingsCenter issues={issues} onEdit={onEdit}/>);
  expect(screen.getAllByText(/some prescription details are unresolved/i)).toHaveLength(1);
  expect(screen.getByText(/amount above a reviewed threshold/i)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:/check or correct transcription/i}));
  expect(onEdit).toHaveBeenCalledOnce();
 });
});

describe('comparison workspace',()=>{
 it('requires a source image and can be opened from the upload page',()=>{
  render(<Upload models={{}} onUploaded={()=>{}}/>);
  fireEvent.click(screen.getByRole('button',{name:/compare all four/i}));
  expect(screen.getByRole('button',{name:/run four-model comparison/i}).disabled).toBe(true);
  expect(screen.queryByRole('button',{name:/run OCR analysis/i})).toBeNull();
 });
 it('shows explicit no-reference behavior before any model runs',()=>{
  render(<OCRComparison/>);
  expect(screen.getByText(/one prescription, the same preprocessing/i)).toBeTruthy();
  expect(screen.getByRole('button',{name:/run four-model comparison/i}).disabled).toBe(true);
 });
});
