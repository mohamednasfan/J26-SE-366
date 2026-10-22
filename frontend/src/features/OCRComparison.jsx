import React, {useEffect,useRef,useState} from 'react';
import { ArrowRight, CheckCircle2, ClipboardCopy, FileImage, LoaderCircle, RefreshCw, ShieldAlert, UploadCloud, XCircle } from 'lucide-react';
import {Badge,Notice} from '../components/Status.jsx';
import {formatEngine,request,saveJSON} from '../lib/api.js';

const MODES=[
  ['none','Original image'],
  ['clahe','Contrast enhancement'],
  ['adaptive','Adaptive threshold'],
  ['deskew_clahe','Deskew + contrast'],
];
const ENGINES=['tesseract','easyocr','paddleocr','craft_trocr'];

export default function OCRComparison(){
 const picker=useRef(null);
 const [file,setFile]=useState(null),[preview,setPreview]=useState('');
 const [mode,setMode]=useState('none'),[busy,setBusy]=useState(false);
 const [error,setError]=useState(''),[result,setResult]=useState(null);
 useEffect(()=>{
   if(!file||file.type==='application/pdf'){setPreview('');return}
   const url=URL.createObjectURL(file);
   setPreview(url);
   return ()=>URL.revokeObjectURL(url);
 },[file]);
 const choose=(selected)=>{
   setResult(null);setError('');
   if(!selected)return;
   if(!/\.(png|jpg|jpeg|webp|pdf)$/i.test(selected.name)){
     setError('Choose a PNG, JPG, WEBP or single-page PDF.');return;
   }
   if(selected.size>8*1024*1024){
     setError('Comparison images must be 8 MB or smaller.');return;
   }
   setFile(selected);
 };
 const compare=async()=>{
   if(!file)return;
   setBusy(true);setError('');setResult(null);
   try{
     const form=new FormData();form.append('file',file);
     const data=await request('/compare?preprocess='+encodeURIComponent(mode),{
       method:'POST',body:form
     });
     setResult(data);
   }catch(exc){setError(exc.message)}
   finally{setBusy(false)}
 };
 return <section className="surface comparison-panel">
  <div className="section-top"><div>
   <h3>Four-engine OCR comparison <Badge tone="teal">Interactive research tool</Badge></h3>
   <p>Run the same image through Tesseract, EasyOCR, PaddleOCR and CRAFT + TrOCR.</p>
  </div></div>
  <div className="comparison-form">
   <div className="comparison-source">
    <input ref={picker} type="file" hidden accept=".png,.jpg,.jpeg,.webp,.pdf"
     onChange={event=>choose(event.target.files?.[0])}/>
    <button type="button" className="comparison-picker" onClick={()=>picker.current?.click()}>
      <div className="comparison-picker-icon">{preview?<img src={preview} alt="Selected prescription preview"/>:<UploadCloud size={25}/>}</div>
      <span><strong>{file?file.name:'Choose an image to compare'}</strong>
      <small>Identical OCR input for all four engines · source not retained</small></span>
      <FileImage size={20}/>
    </button>
   </div>
   <label className="comparison-mode" htmlFor="comparison-mode">Preprocessing
    <select id="comparison-mode" value={mode} onChange={event=>{setMode(event.target.value);setResult(null)}}>
     {MODES.map(([id,label])=><option value={id} key={id}>{label}</option>)}
    </select>
   </label>
   <button className="button button-primary comparison-submit" onClick={compare} disabled={!file||busy}>
    {busy?<LoaderCircle size={18} className="spin"/>:<ArrowRight size={18}/>}
    {busy?'Comparing engines…':'Compare OCR engines'}
   </button>
  </div>
  {error&&<div className="comparison-notice"><Notice type="error">{error}</Notice></div>}
  {result&&<div className="comparison-result" aria-live="polite">
   <div className="comparison-result-header"><div>
    <h4>Comparison results</h4>
    <p>{result.completed_engines} of {result.n_engines} engines completed · {(result.preprocessing?.mode||'none').replaceAll('_',' ')} preparation</p>
   </div><button className="button button-ghost" onClick={()=>saveJSON('medsafe-ocr-comparison.json',result)}>
     Export results</button></div>
   <div className="comparison-cards">
    {ENGINES.map(engine=>{
      const model=result.engines?.[engine]||{};
      const ok=model.status==='COMPLETED';
      return <article className="comparison-card" key={engine}>
       <div className="comparison-card-header">
        <div><strong>{formatEngine(engine)}</strong><small>{model.elapsed_seconds!=null?model.elapsed_seconds+' seconds':'No result'}</small></div>
        <Badge tone={ok?'teal':'amber'}>{ok?'Processed':'Unavailable'}</Badge>
       </div>
       {ok?<div className="comparison-transcript"><pre>{model.text||'No readable text detected'}</pre></div>:
        <div className="comparison-unavailable"><XCircle size={19}/><p>{model.reason||'Engine could not run in this environment.'}</p></div>}
       {ok&&<div className="comparison-card-footer">
        <span>{model.region_count||0} detected regions</span>
        <button className="text-link" onClick={()=>navigator.clipboard?.writeText(model.text||'')}>
         <ClipboardCopy size={14}/> Copy transcription</button>
       </div>}
      </article>;
    })}
   </div>
   <div className="comparison-disclaimer"><ShieldAlert size={18}/>
    This is a transcription comparison, not an accuracy benchmark. Medicine names, age and doses still require independent human-verified ground truth. No result is clinically approved.
   </div>
  </div>}
 </section>
}
