import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ImageEvidence from '../components/ImageEvidence.jsx';
import Sidebar from '../components/Sidebar.jsx';
import Upload from '../features/Upload.jsx';


describe('OCR source image verification', () => {
  it('can show and hide unverified geometric proposals', () => {
    render(<ImageEvidence
      src="/api/prescriptions/fake-id/image" width={300} height={150}
      regions={[{box:[20,30,150,55],text:'unverified candidate'}]}
      alt="Synthetic prescription"
    />);
    expect(screen.getByRole('img', {name:/unverified OCR region outlines/i})).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name:/hide regions/i}));
    expect(screen.queryByRole('img', {name:/unverified OCR region outlines/i})).toBeNull();
    expect(screen.getByRole('img', {name:'Synthetic prescription'})).toBeTruthy();
  });

  it('does not invent OCR geometry when no region was returned', () => {
    render(<ImageEvidence src="/image.png" width={400} height={200} regions={[]}/>);
    expect(screen.getByRole('button', {name:/hide regions/i}).disabled).toBe(true);
    expect(screen.queryByRole('img',{name:/unverified OCR region outlines/i})).toBeNull();
  });
});


describe('modular workspace navigation', () => {
  it('changes sections through labeled controls', () => {
    const go=vi.fn();
    render(<Sidebar active="overview" onChange={go} count={3}
      opened={false} onClose={()=>{}}/>);
    const current=screen.getByRole('button',{name:/overview/i});
    expect(current.getAttribute('aria-current')).toBe('page');
    fireEvent.click(screen.getByRole('button',{name:/research & benchmarks/i}));
    expect(go).toHaveBeenCalledWith('research');
  });
});


describe('prescription upload safeguards', () => {
  it('keeps the upload disabled until a file is chosen', () => {
    render(<Upload models={{}} onUploaded={()=>{}}/>);
    expect(screen.getByRole('button',{name:/run OCR analysis/i}).disabled).toBe(true);
    const select=screen.getByLabelText('Image preprocessing');
    expect(select.value).toBe('none');
    fireEvent.change(select,{target:{value:'clahe'}});
    expect(select.value).toBe('clahe');
  });
});
