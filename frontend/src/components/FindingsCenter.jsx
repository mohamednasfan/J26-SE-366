import React from 'react';
import {AlertTriangle,ClipboardEdit,Info,ShieldAlert} from 'lucide-react';
import {groupReviewFindings,issueTitle,missingFieldPhrase} from '../lib/findings.js';

export default function FindingsCenter({issues=[],onEdit}){
 const data=groupReviewFindings(issues);
 const item=(issue,index)=><li key={index}><strong>{issueTitle(issue)}: </strong>{issue.message}</li>;
 return <div className="findings-center">
  {data.missing.map(group=><section className="findings-cluster findings-review" key={'missing'+group.medicine_index}>
   <ClipboardEdit size={21}/><div><small>Transcription review · Medication {group.medicine_index}</small>
    <h4>Some prescription details are unresolved</h4>
    <p>Missing or not recognized: <strong>{missingFieldPhrase(group.fields)}</strong>. The source image may not contain these details, or OCR may have missed them.</p>
    <button type="button" className="button button-ghost findings-action" onClick={onEdit}>Check or correct transcription</button>
    <details><summary>Show {group.issues.length} original validation messages</summary><ul>{group.issues.map(item)}</ul></details></div>
  </section>)}
  {data.conflicts.map((issue,i)=><section className="findings-cluster findings-blocking" key={'conflict'+i}>
    <AlertTriangle size={21}/><div><small>Blocking inconsistency</small><h4>{issueTitle(issue)}</h4><p>{issue.message}</p>
    <button className="button button-ghost findings-action" onClick={onEdit}>Review conflicting text</button></div>
  </section>)}
  {data.reviewedFlags.map((issue,i)=><section className="findings-cluster findings-ruleflag" key={'flag'+i}>
    <ShieldAlert size={21}/><div><small>Reviewed-rule warning · {issue.medicine_index?'Medication '+issue.medicine_index:'Prescription'}</small>
    <h4>{issue.code==='REVIEWED_RULE_THRESHOLD_EXCEEDED'?'Amount above a reviewed threshold':'Age outside a reviewed age range'}</h4>
    <p>{issue.message}</p><p><strong>This is not a clinical overdose diagnosis.</strong> A qualified clinician must review the complete prescription.</p></div>
  </section>)}
  {data.reviewItems.map((issue,i)=><section className="findings-cluster findings-review" key={'item'+i}>
    <ClipboardEdit size={21}/><div><small>Needs review</small><h4>{issueTitle(issue)}</h4><p>{issue.message}</p>
    <button type="button" className="button button-ghost findings-action" onClick={onEdit}>Review transcription</button></div>
  </section>)}
  {(data.diagnostics.length>0||data.notes.length>0)&&<div className="findings-technical">
   <details><summary><Info size={17}/> Other notes and OCR limitations ({data.diagnostics.length+data.notes.length})</summary>
    <ul>{[...data.diagnostics,...data.notes].map(item)}</ul></details>
  </div>}
  {!data.total&&<div className="no-clearance">No warnings were recorded. This <strong>does not establish clinical safety.</strong> Human review and source-approved rules are still required.</div>}
  <div className="findings-safety-footer"><ShieldAlert size={17}/><span>When dosing or age evidence is incomplete, validation remains <strong>Unable to validate</strong>, not “safe.”</span></div>
 </div>;
}
