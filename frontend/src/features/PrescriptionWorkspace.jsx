import React,{useEffect,useMemo,useState} from 'react';
import { AlertTriangle, ArrowLeft, BookOpen, Check, ChevronDown, ClipboardCheck, Download, Eye, FileText, LoaderCircle, ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react';
import {Badge,EmptyState,Notice} from '../components/Status.jsx';
import ImageEvidence from '../components/ImageEvidence.jsx';
import {confirmTranscription,formatEngine,request,saveJSON} from '../lib/api.js';
export default function PrescriptionWorkspace({detail,onReviewed,onDeleted}){
 const [editing,setEditing]=useState(false),[audit,setAudit]=useState([]);
 const [transcript,setTranscript]=useState(''),[tab,setTab]=useState('transcription'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[references,setReferences]=useState({}),[openReference,setOpenReference]=useState({});
 useEffect(()=>{setTranscript(detail?.corrected_text||detail?.original_text||'');setTab(detail?.reviewer_confirmed?'findings':'transcription');setError('');setReferences({});setEditing(false)},[detail?.id,detail?.reviewer_confirmed]);
 useEffect(()=>{if(!detail?.id)return;let active=true;request('/prescriptions/'+encodeURIComponent(detail.id)+'/audit').then(v=>{if(active)setAudit(v.events||[])}).catch(()=>{if(active)setAudit([])});return()=>{active=false}},[detail?.id,detail?.updated]);
 const report=detail?.report||{},medications=report.medications||[],issues=report.issues||[];
 const reviewed=!!detail?.reviewer_confirmed;
 const verify=async()=>{if(!transcript.trim()){setError('Review and correct the transcription before confirming.');return}setBusy(true);setError('');
  try{await confirmTranscription(detail.id,transcript);setEditing(false);await onReviewed()}catch(e){setError(e.message)}finally{setBusy(false)}};
 const remove=async()=>{if(!window.confirm('Permanently delete this prescription and image?'))return;setBusy(true);try{await request('/prescriptions/'+encodeURIComponent(detail.id),{method:'DELETE'});await onDeleted()}catch(e){setError(e.message)}finally{setBusy(false)}};
 const lookup=async(name)=>{if(!name||references[name])return;setOpenReference(o=>({...o,[name]:true}));
  try{const value=await request('/reference?medicine='+encodeURIComponent(name));setReferences(r=>({...r,[name]:value}))}catch(e){setReferences(r=>({...r,[name]:{status:'REFERENCE_UNAVAILABLE',reason:e.message}}))}};
 if(!detail)return <EmptyState icon={FileText} title="No prescription selected" description="Open a prescription from records to begin."/>;
 return <div className="stack-lg">
  <div className="review-heading"><div className="review-file-icon"><FileText size={23}/></div><div><h2>{detail.filename}</h2><p>Analysis ID · {detail.id.slice(0,8)} · {formatEngine(detail.engine)}</p></div>
   <Badge tone={reviewed?'teal':'amber'}>{reviewed?'Transcription confirmed':'Review required'}</Badge>
   <button className="button button-ghost review-export" onClick={()=>saveJSON('medsafe-'+detail.id.slice(0,8)+'.json',detail)}><Download size={17}/> Export report</button></div>
  <div className="workflow-progress"><div className="workflow-stage is-complete"><span><Check size={14}/></span><strong>01 · OCR recognition</strong></div>
   <div className={'workflow-stage '+(reviewed?'is-complete':'is-current')}><span>{reviewed?<Check size={14}/>:2}</span><strong>02 · Human confirmation</strong></div>
   <div className={'workflow-stage '+(reviewed?'is-current':'is-upcoming')}><span>3</span><strong>03 · Safety review</strong></div></div>
  <div className="review-grid">
   <section className="surface preview-surface"><div className="section-top"><div><h3>Original prescription</h3><p>Source image for manual cross-checking</p></div><Eye size={19} className="muted-icon"/></div>
     <div className="preview-frame"><ImageEvidence src={detail.image_url}
       width={detail.ocr?.width} height={detail.ocr?.height}
       regions={detail.ocr?.regions||[]} alt="Uploaded prescription; compare against OCR text"/></div>
     {detail.ocr?.preprocessing?.quality?.warnings?.length>0&&<div className="image-quality-flags">
      <strong>Image-quality diagnostics (not clinical confidence)</strong>
      {detail.ocr.preprocessing.quality.warnings.map((warning,i)=><span key={i}>{warning.replaceAll('_',' ')}</span>)}
     </div>}
     <div className="preview-footer"><span>OCR: <strong>{formatEngine(detail.engine)}</strong>{detail.ocr?.processing_seconds!=null?' · '+detail.ocr.processing_seconds+' seconds':''}{detail.ocr?.preprocessing?.mode&&detail.ocr.preprocessing.mode!=='none'?' · '+detail.ocr.preprocessing.mode.replaceAll('_',' '):''}</span><Badge tone="amber">Image text unverified</Badge></div>
   </section>
   <section className="surface findings-surface"><div className="tabs" role="tablist" aria-label="Prescription review sections">
    <button role="tab" aria-selected={tab==='transcription'} className={tab==='transcription'?'active':''} onClick={()=>setTab('transcription')}>Transcription</button>
    <button role="tab" aria-selected={tab==='findings'} disabled={!reviewed||editing} className={tab==='findings'?'active':''} onClick={()=>setTab('findings')}>Safety findings {reviewed&&<span className="tab-count">{issues.length}</span>}</button></div>
    {tab==='transcription'?<div className="tab-body">
      <div className="editor-heading"><h3>Verify extracted text</h3><p>Compare every medicine, administered dose, frequency and patient detail with the source image.</p></div>
      <label className="form-label" htmlFor="transcription">Corrected prescription transcription</label>
      <textarea id="transcription" className="transcription-editor" spellCheck={false} value={transcript} onChange={e=>setTranscript(e.target.value)} maxLength={12000} readOnly={reviewed&&!editing}/>
      <div className="editor-footer"><span>{transcript.length} / 12,000 characters</span><span>OCR confidence is not clinical confidence</span></div>
      {reviewed&&!editing?<Notice type="info">A confirmed transcript is locked until you choose to revise it. Each revision is recorded in the local audit timeline.</Notice>:<Notice type="warning">By confirming, you verify only the written text—not medicine identity, dose appropriateness or clinical safety.</Notice>}
      {error&&<Notice type="error">{error}</Notice>}
      {reviewed&&!editing&&<button className="button button-ghost button-full" onClick={()=>{setEditing(true);setTab('transcription')}}>Revise confirmed transcription</button>}
      {(!reviewed||editing)&&<button className="button button-primary button-full" onClick={verify} disabled={busy||!transcript.trim()}>
       {busy?<LoaderCircle className="spin" size={18}/>:<ClipboardCheck size={18}/>} {editing?'Confirm revised transcription and recalculate findings':'Confirm transcription and run safety screen'}</button>}
    </div>:<div className="tab-body">
      <Notice type="warning">Clinical clearance is unavailable. All findings are advisory and require a qualified professional.</Notice>
      <div className="findings-summary"><div className="finding-number">{issues.length}</div><div><strong>Screening observations</strong><p>Across {medications.length} medication entries. No autonomous treatment decision.</p></div></div>
      <div className="findings-list">{issues.length?issues.map((issue,index)=><div className={'finding-item '+(issue.severity==='BLOCK'?'finding-block':'')} key={index}>
       <AlertTriangle size={18}/><div><strong>{issue.code?.replaceAll('_',' ')||'Review observation'}</strong><p>{issue.message}</p><small>{issue.medicine_index?'Medication '+issue.medicine_index+' · ':''}{issue.severity||'REVIEW'}</small></div></div>):
      <div className="no-clearance">No extracted warnings were recorded. This does <strong>not</strong> establish clinical safety.</div>}</div>
      <div className="medication-section"><h3>Medication-by-medication evidence</h3>
        {medications.map((med,i)=>{const f=med.extraction?.fields||{},name=f.medicine||'Unidentified medicine';
         return <div className="medication-card" key={i}><div className="medication-top"><div><span className="med-number">MEDICATION {i+1}</span><h4>{name}</h4></div><Badge tone="amber">Needs clinician</Badge></div>
         <div className="field-summary">{[['Dose',f.dose],['Frequency',f.frequency],['Age',f.age],['Weight',f.weight],['Route',f.route]].map(([label,value])=><div key={label}><small>{label}</small><strong>{value||'Not provided'}</strong></div>)}</div>
         <div className="rule-summary"><div><small>Reviewed dosage rule</small><strong>{med.reviewed_dose_rule?.status?.replaceAll('_',' ')||'NOT EVALUATED'}</strong></div>
          <div><small>Age validation</small><strong>{med.reviewed_age_rule?.status?.replaceAll('_',' ')||'UNABLE TO VALIDATE'}</strong></div></div>
         <button className="text-link" onClick={()=>{setOpenReference(o=>({...o,[name]:!o[name]}));lookup(name)}}><BookOpen size={16}/> {openReference[name]?'Hide':'Find'} label evidence <ChevronDown size={15}/></button>
         {openReference[name]&&<div className="evidence-box"><strong>Reference lookup</strong><p>Status: {references[name]?.status||'Fetching label information…'}</p>
          <p>Drug labels are informational evidence. No recommended dose is inferred automatically without qualified rule review.</p>
          {(references[name]?.dailymed||[]).map((item,i)=><p key={'dm'+i}><a target="_blank" rel="noopener noreferrer" href={item.url}>DailyMed: {item.title} ↗</a> · Search candidate, not confirmed product identity</p>)}
          {(references[name]?.openfda||[]).map((item,i)=><div className="source-section" key={'fda'+i}><p><a target="_blank" rel="noopener noreferrer" href={item.url}>openFDA label candidate ↗</a></p>{Object.entries(item.label_sections_UNVERIFIED_FOR_PRODUCT||{}).map(([heading,section])=><details key={heading}><summary>{heading.replaceAll('_',' ')}</summary><p>{section}</p></details>)}</div>)}
          {med.reviewed_dose_rule?.source_url&&<p><a target="_blank" rel="noopener noreferrer" href={med.reviewed_dose_rule.source_url}>Open qualified-review source ↗</a></p>}</div>}
        </div>})}
      </div>
    </div>}
   </section>
  </div>
  <section className="surface audit-panel"><div className="section-top"><div><h3>Transcription audit trail</h3><p>Revision events with timestamped SHA-256 text hashes. Entries are deleted with the prescription.</p></div></div><div className="audit-events">{audit.map(event=><div key={event.event_id} className="audit-event"><span className="audit-dot"/><div><strong>{event.action?.replaceAll('_',' ')}</strong><p>{event.event_time?new Date(event.event_time).toLocaleString('en-GB'):'—'} · {event.after_sha256?.slice(0,12)}…</p></div></div>)}</div></section>
  <div className="workspace-footer"><div><ShieldAlert size={20}/><p><strong>Research use only.</strong> Never prescribe, dispense or make treatment decisions solely from these results.</p></div>
   <button className="button button-danger-ghost" onClick={remove} disabled={busy}><Trash2 size={16}/> Delete record</button></div>
 </div>;
}
