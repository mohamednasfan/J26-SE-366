/** Presentation-only grouping. Backend BLOCK and clinical abstention stay unchanged. */
const MISSING=/^MISSING_(MEDICINE|DOSE|FREQUENCY|AGE|ROUTE|WEIGHT|STRENGTH)$/;
const REVIEWED_FLAGS=new Set(['REVIEWED_RULE_THRESHOLD_EXCEEDED','REVIEWED_AGE_RANGE_FLAG']);
const CONFLICTS=new Set(['CONFLICTING_FIELDS','CONFLICTING_PRESCRIPTION_DETAILS','DUPLICATE_FIELD','DUPLICATE_MEDICATION_REGIMEN','REVIEWED_RULE_REGISTRY_UNAVAILABLE']);
const DIAGNOSTICS=new Set(['LOW_OCR_CONFIDENCE','OCR_CANDIDATE_NEEDS_CONFIRMATION','OCR_EXTRACTION_UNRESOLVED']);
const FIELD_LABELS={medicine:'medicine name',dose:'administered dose',frequency:'frequency',age:'patient age',route:'route',weight:'weight',strength:'strength'};
export const issueTitle=issue=>(issue?.code||'REVIEW_REQUIRED').replaceAll('_',' ').toLowerCase().replace(/^./,s=>s.toUpperCase());

export function groupReviewFindings(raw=[]){
 const issues=Array.isArray(raw)?raw.filter(i=>i&&typeof i==='object'):[];
 const missing=new Map();
 const conflicts=[],reviewedFlags=[],reviewItems=[],diagnostics=[],notes=[];
 for(const issue of issues){
  const code=String(issue.code||''),match=code.match(MISSING);
  if(match){
   const index=Number(issue.medicine_index)||1;
   if(!missing.has(index))missing.set(index,{medicine_index:index,fields:[],issues:[]});
   const entry=missing.get(index),field=match[1].toLowerCase();
   if(!entry.fields.includes(field))entry.fields.push(field);
   entry.issues.push(issue);
  }else if(REVIEWED_FLAGS.has(code)){
   reviewedFlags.push(issue);
  }else if(CONFLICTS.has(code)||code.startsWith('CONFLICTING_')||code.startsWith('DUPLICATE_')){
   conflicts.push(issue);
  }else if(DIAGNOSTICS.has(code)){
   diagnostics.push(issue);
  }else if(issue.severity==='BLOCK'||code.startsWith('INVALID_')){
   reviewItems.push(issue);
  }else{
   notes.push(issue);
  }
 }
 return {missing:[...missing.values()].sort((a,b)=>a.medicine_index-b.medicine_index),
         conflicts,reviewedFlags,reviewItems,diagnostics,notes,
         total:issues.length};
}
export function missingFieldPhrase(fields=[]){return fields.map(f=>FIELD_LABELS[f]||f).join(', ')}
