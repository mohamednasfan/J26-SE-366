import React,{useRef,useState} from 'react';
import { ArrowRight, CloudUpload, FileImage, Info, LoaderCircle, ShieldCheck, X } from 'lucide-react';
import {Notice} from '../components/Status.jsx';
import OCRComparison from './OCRComparison.jsx';
import {uploadPrescription,formatEngine} from '../lib/api.js';
const TYPES=/\.(png|jpe?g|webp|pdf)$/i;
export default function Upload({models={},onUploaded}){
 const ref=useRef(null);const [file,setFile]=useState(null),[engine,setEngine]=useState('tesseract');
 const [preprocess,setPreprocess]=useState('none'),[analysisMode,setAnalysisMode]=useState('single');
 const [drag,setDrag]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const select=(f)=>{if(!f)return;if(!TYPES.test(f.name)){setError('Choose a PNG, JPG, WEBP, or single-page PDF.');return}if(f.size>12*1024*1024){setError('Maximum file size is 12 MB.');return}setFile(f);setError('')};
 const submit=async()=>{if(!file)return;setBusy(true);setError('');try{const result=await uploadPrescription(file,engine,preprocess);await onUploaded(result.id)}catch(e){setError(e.message)}finally{setBusy(false)}};
 const engines=[['tesseract','Tesseract','Baseline OCR'],['easyocr','EasyOCR','Deep learning OCR'],['paddleocr','PaddleOCR','Document OCR'],['craft_trocr','CRAFT + TrOCR','Detection + handwritten recognition']];
 return <><div className="upload-layout"><section className="surface upload-card">
  <div className="section-top"><div><h3>Upload prescription</h3><p>Use an image or one-page PDF. No text is considered verified until you review it.</p></div><div className="step-label">STEP 01 / 03</div></div>
  <input ref={ref} type="file" accept=".png,.jpg,.jpeg,.webp,.pdf" hidden onChange={e=>select(e.target.files?.[0])}/>
  <div role="button" tabIndex={0} aria-label="Choose a prescription file" onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();ref.current?.click()}}}
   onClick={()=>ref.current?.click()} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)}
   onDrop={e=>{e.preventDefault();setDrag(false);select(e.dataTransfer.files?.[0])}}
   className={'drop-area'+(drag?' dragging':'')}><div className="drop-icon"><CloudUpload size={33}/></div>
   <h3>Drag and drop your prescription</h3><p>or <span>browse files</span> from your computer</p><small>PNG, JPG, WEBP or PDF · Maximum 12 MB</small></div>
  {file&&<div className="selected-file"><FileImage size={20}/><div><strong>{file.name}</strong><small>{(file.size/1024/1024).toFixed(2)} MB · Ready to analyze</small></div><button className="icon-button" aria-label="Remove file" onClick={()=>setFile(null)}><X size={18}/></button></div>}
  <div className="form-label">Choose analysis mode</div>
  <div className="analysis-mode-switch" role="group" aria-label="Analysis mode">
   <button type="button" className={analysisMode==='single'?'active':''} aria-pressed={analysisMode==='single'} onClick={()=>setAnalysisMode('single')}>One OCR engine <small>Review and save a prescription</small></button>
   <button type="button" className={analysisMode==='compare'?'active':''} aria-pressed={analysisMode==='compare'} onClick={()=>setAnalysisMode('compare')}>Compare all four <small>See text, detected fields and timing</small></button>
  </div>
  {analysisMode==='single'&&<><div className="form-label">OCR engine</div><div className="engine-grid">{engines.map(([id,label,description])=><button key={id} type="button" onClick={()=>setEngine(id)}
   className={'engine-option'+(engine===id?' active':'')}><div className="radio-indicator"/><strong>{label}</strong><span>{description}</span>{models.benchmark_engines?.[id==='craft_trocr'?'trocr':id]===false&&<small>Requires local model setup</small>}</button>)}</div></>}
  <label className="form-label" htmlFor="preprocessing-mode">Image preprocessing</label>
  <div className="preprocessing-control">
    <select id="preprocessing-mode" value={preprocess} onChange={e=>setPreprocess(e.target.value)}>
      <option value="none">Original image — no changes (fair baseline)</option>
      <option value="clahe">Contrast enhancement + denoising (CLAHE)</option>
      <option value="adaptive">Adaptive black-and-white threshold</option>
      <option value="deskew_clahe">Automatic deskew + contrast enhancement</option>
    </select>
    <p>Only the OCR input is processed. Your original document remains unchanged for manual verification.</p>
  </div>
  {error&&<Notice type="error">{error}</Notice>}
  {analysisMode==='single'&&<button className="button button-primary submit-upload" disabled={!file||busy} onClick={submit}>{busy?<><LoaderCircle size={19} className="spin"/> Processing image…</>:<>Run OCR analysis <ArrowRight size={19}/></>}</button>}
  {analysisMode==='compare'&&<div className="upload-mode-note"><Info size={17}/><span>Compare all four engines without saving a prescription. Install optional models to enable all results. The comparison accepts files up to 8 MB.</span></div>}
 </section>
 <aside className="upload-aside"><div className="surface"><div className="aside-illustration"><ShieldCheck size={27}/></div><h3>How it works</h3>
  <ol className="process-steps"><li><span>01</span><div><strong>Recognize text</strong><p>The selected OCR engine reads the prescription. Output is unverified.</p></div></li>
   <li><span>02</span><div><strong>Confirm transcription</strong><p>Correct medicine names, quantities, patient age and instructions.</p></div></li>
   <li><span>03</span><div><strong>Inspect safety evidence</strong><p>Check available reviewed-rule flags, uncertainty and supporting references.</p></div></li></ol></div>
   <div className="subtle-info"><Info size={19}/><p>Research prototype. No automatic clinical clearance, dose approval or dispensing.</p></div>
 </aside></div>{analysisMode==='compare'&&<div className="upload-comparison"><OCRComparison initialFile={file} initialMode={preprocess} embedded/></div>}</>;
}
