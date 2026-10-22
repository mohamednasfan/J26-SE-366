import React,{useCallback,useEffect,useState} from 'react';
import { Bell, Menu, Plus, Search, ShieldCheck } from 'lucide-react';
import Sidebar from '../components/Sidebar.jsx';
import { Notice } from '../components/Status.jsx';
import { request } from '../lib/api.js';
import Overview from '../features/Overview.jsx';
import Library from '../features/Library.jsx';
import Upload from '../features/Upload.jsx';
import PrescriptionWorkspace from '../features/PrescriptionWorkspace.jsx';
import Research from '../features/Research.jsx';
const titles={overview:['Overview','Your prescription intelligence workspace'],new:['New analysis','Upload a prescription to begin the verification workflow'],library:['Prescription records','Review and manage your locally stored prescriptions'],workspace:['Prescription review','Verify transcription and inspect evidence-based safety checks'],research:['Research & benchmarks','OCR model availability, evaluation criteria and methodology']};
export default function App(){
 const [page,setPage]=useState('overview'),[menu,setMenu]=useState(false);
 const [records,setRecords]=useState([]),[stats,setStats]=useState({}),[models,setModels]=useState({}),[research,setResearch]=useState({});
 const [detail,setDetail]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[toast,setToast]=useState('');
 const refresh=useCallback(async()=>{try{const [r,s,m,q]=await Promise.all([request('/prescriptions'),request('/stats'),request('/models'),request('/research')]);
  setRecords(r.items||[]);setStats(s||{});setModels(m||{});setResearch(q||{});
 }catch(e){setError(e.message)}},[]);
 useEffect(()=>{refresh()},[refresh]);
 useEffect(()=>{if(!toast)return;const t=setTimeout(()=>setToast(''),4300);return()=>clearTimeout(t)},[toast]);
 const go=(target)=>{setPage(target);setMenu(false);setError('')};
 const open=async(id)=>{setBusy(true);setError('');try{const data=await request('/prescriptions/'+encodeURIComponent(id));setDetail(data);go('workspace')}
 catch(e){setError(e.message)}finally{setBusy(false)}};
 const updated=async(id)=>{await refresh();await open(id)};
 const notify=(message)=>setToast(message);
 const title=titles[page]||titles.overview;
 return <div className="application">
   <Sidebar active={page==='workspace'?'library':page} onChange={go} count={records.length} opened={menu} onClose={()=>setMenu(false)}/>
   <main className="main-panel">
    <header className="topbar">
     <div className="topbar-left"><button className="icon-button menu-toggle" aria-label="Open navigation" onClick={()=>setMenu(true)}><Menu size={21}/></button>
      <span className="breadcrumbs">Workspace</span><span className="crumb-sep">/</span><strong>{title[0]}</strong></div>
     <div className="topbar-actions"><span className="header-mode"><span className="env-dot"/> RESEARCH MODE</span>
      <span className="top-avatar">MS</span></div>
    </header>
    <div className="content">
     <div className="page-heading"><div><div className="page-kicker">MEDSAFE-AI PLATFORM</div><h1>{title[0]}</h1><p>{title[1]}</p></div>
      {page!=='new'&&<button className="button button-primary heading-action" onClick={()=>go('new')}><Plus size={18}/> New analysis</button>}</div>
     {error&&<div className="error-wrap"><Notice type="error">{error}</Notice><button className="text-button" onClick={()=>setError('')}>Dismiss</button></div>}
     {page==='overview'&&<Overview stats={stats} records={records} models={models} go={go} open={open}/>}
     {page==='library'&&<Library records={records} open={open} onDeleted={async()=>{await refresh();notify('Prescription permanently deleted')}} go={go}/>}
     {page==='new'&&<Upload models={models} onUploaded={async id=>{notify('Image processed. Verify the transcription before reviewing results.');await updated(id)}}/>}
     {page==='workspace'&&<PrescriptionWorkspace detail={detail} models={models} onReviewed={async()=>{notify('Transcription confirmed. Safety checks remain advisory.');await updated(detail.id)}} onDeleted={async()=>{await refresh();setDetail(null);go('library')}}/>}
     {page==='research'&&<Research research={research} models={models}/>}
     {busy&&<div className="loading-overlay" role="status">Loading prescription…</div>}
    </div>
   </main>
   {toast&&<div className="toast" role="status"><ShieldCheck size={17}/>{toast}</div>}
  </div>
}
