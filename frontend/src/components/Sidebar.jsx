import React from 'react';
import { Activity, BookOpen, ClipboardList, FilePlus2, HeartPulse, LayoutDashboard, ShieldCheck, X } from 'lucide-react';
const items=[
  {id:'overview',label:'Overview',icon:LayoutDashboard},
  {id:'new',label:'New analysis',icon:FilePlus2},
  {id:'library',label:'Prescription records',icon:ClipboardList},
  {id:'research',label:'Research & benchmarks',icon:BookOpen},
];
export default function Sidebar({active,onChange,count=0,opened,onClose}) {
 return <>
  {opened&&<button type="button" className="sidebar-backdrop" aria-label="Close menu" onClick={onClose}/>}
  <aside className={'sidebar'+(opened?' is-open':'')}>
   <div className="brand">
    <div className="brand-icon"><HeartPulse size={25}/></div>
    <div><div className="brand-word">MedSafe<span>AI</span></div><div className="brand-caption">PRESCRIPTION INTELLIGENCE</div></div>
    <button className="mobile-close icon-button" aria-label="Close navigation" onClick={onClose}><X size={18}/></button>
   </div>
   <div className="nav-caption">WORKSPACE</div>
   <nav aria-label="Primary navigation" className="side-nav">
    {items.map(({id,label,icon:Icon})=><button key={id} type="button" onClick={()=>onChange(id)}
      aria-current={active===id?'page':undefined} className={'side-link'+(active===id?' selected':'')}>
      <Icon size={19} strokeWidth={1.85}/><span>{label}</span>{id==='library'&&count>0&&<span className="side-count">{count}</span>}
    </button>)}
   </nav>
   <div className="side-bottom">
    <div className="safety-side-card">
     <div className="safety-heading"><ShieldCheck size={20}/> Human-led safety</div>
     <p>OCR transcriptions and medication checks require professional review. Never use this tool for autonomous dispensing.</p>
     <div className="environment"><span className="env-dot"/> LOCAL RESEARCH SYSTEM</div>
    </div>
    <div className="side-profile"><div className="profile-avatar"><Activity size={17}/></div><div><strong>Research workspace</strong><span>MedSafe-AI · Version 1.1</span></div></div>
   </div>
  </aside>
 </>;
}
