import React,{useMemo,useState} from 'react';
import { ArrowRight, FileSearch, FileText, Search, Trash2 } from 'lucide-react';
import {Badge,EmptyState} from '../components/Status.jsx';
import {request,formatDate,formatEngine} from '../lib/api.js';
export default function Library({records=[],open,onDeleted,go}){
 const [search,setSearch]=useState(''),[filter,setFilter]=useState('all'),[busy,setBusy]=useState('');
 const filtered=useMemo(()=>records.filter(row=>(row.filename||'').toLowerCase().includes(search.toLowerCase())&&
  (filter==='all'||(filter==='reviewed'?!!row.reviewer_confirmed:!row.reviewer_confirmed))),[records,search,filter]);
 const remove=async(row)=>{if(!window.confirm('Permanently delete this prescription and stored image?'))return;
  setBusy(row.id);try{await request('/prescriptions/'+encodeURIComponent(row.id),{method:'DELETE'});await onDeleted()}catch(e){window.alert(e.message)}finally{setBusy('')}};
 return <section className="surface library-surface">
  <div className="section-top"><div><h3>Prescription records <span className="count-chip">{records.length}</span></h3><p>Only locally stored research records appear here.</p></div></div>
  <div className="library-toolbar"><label className="search-field"><Search size={18}/><input aria-label="Search prescriptions" placeholder="Search prescriptions by filename…" value={search} onChange={e=>setSearch(e.target.value)}/></label>
   <div className="segmented" role="group" aria-label="Review filter">{[['all','All'],['pending','Awaiting review'],['reviewed','Reviewed']].map(([id,label])=><button key={id} className={filter===id?'current':''} onClick={()=>setFilter(id)}>{label}</button>)}</div></div>
  {filtered.length?<div className="table-scroll"><table className="data-table"><thead><tr><th>Prescription</th><th>Engine</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
   <tbody>{filtered.map(row=><tr key={row.id}><td><div className="file-cell"><span className="file-icon"><FileText size={18}/></span><div><strong>{row.filename||'Prescription'}</strong><small>ID {String(row.id).slice(0,8)}</small></div></div></td>
   <td>{formatEngine(row.engine)}</td><td><Badge tone={row.reviewer_confirmed?'teal':'amber'}>{row.reviewer_confirmed?'Text reviewed':'Review required'}</Badge></td>
   <td>{formatDate(row.created)}</td><td><div className="row-actions"><button onClick={()=>open(row.id)} className="table-action">Review <ArrowRight size={15}/></button><button disabled={busy===row.id} className="danger-icon icon-button" aria-label={'Delete '+row.filename} onClick={()=>remove(row)}><Trash2 size={16}/></button></div></td></tr>)}</tbody></table></div>:
   <EmptyState icon={FileSearch} title={records.length?'No matching prescriptions':'No prescriptions stored'} description={records.length?'Adjust your search or review filter.':'Start by uploading a prescription.'} action={!records.length?<button className="button button-primary" onClick={()=>go('new')}>Create analysis</button>:null}/>}
 </section>;
}
