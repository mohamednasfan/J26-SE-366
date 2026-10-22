import React from 'react';
import { AlertCircle, CheckCircle2, Info, ShieldAlert } from 'lucide-react';
export function Badge({tone='neutral',children}) {return <span className={'badge badge-'+tone}>{children}</span>}
export function EmptyState({icon:Icon=Info,title,description,action}) {
 return <div className="empty-state"><div className="empty-icon"><Icon size={26}/></div><h3>{title}</h3><p>{description}</p>{action}</div>
}
export function Notice({type='info',children}) {
 const Icon=type==='error'?AlertCircle:type==='warning'?ShieldAlert:CheckCircle2;
 return <div className={'notice notice-'+type} role={type==='error'?'alert':'status'}><Icon size={19}/><div>{children}</div></div>;
}
export function StatCard({icon:Icon,label,value,hint,tone='blue'}) {
 return <article className="stat-card"><div className={'stat-icon tone-'+tone}><Icon size={21}/></div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-hint">{hint}</div></article>;
}
