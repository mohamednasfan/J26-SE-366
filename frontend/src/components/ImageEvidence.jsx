import React,{useMemo,useState} from 'react';
import { Eye, EyeOff, ScanLine } from 'lucide-react';

/**
 * Original-source preview with strictly unverified OCR geometry overlays.
 * SVG and image share their intrinsic coordinates, avoiding hardcoded boxes.
 * Text recognition scores/boxes here are never treated as clinical evidence.
 */
export default function ImageEvidence({src,width,height,regions=[],alt='Original prescription image'}){
 const [show,setShow]=useState(true);
 const boxes=useMemo(()=>{
  if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)return [];
  return (regions||[]).flatMap((region,index)=>{
   const b=region?.box;
   if(!Array.isArray(b)||b.length!==4||!b.every(Number.isFinite))return [];
   const x1=Math.max(0,Math.min(width,b[0])),y1=Math.max(0,Math.min(height,b[1]));
   const x2=Math.max(0,Math.min(width,b[2])),y2=Math.max(0,Math.min(height,b[3]));
   if(x2<=x1||y2<=y1)return [];
   return [{x1,y1,x2,y2,index:index+1,text:String(region.text||'Unverified region').slice(0,180)}];
  })
 },[height,regions,width]);
 return <div className="source-image-workspace">
  <div className="source-image-toolbar">
   <div><ScanLine size={16}/><span>{boxes.length} proposed OCR region{boxes.length===1?'':'s'}</span></div>
   <button className="image-overlay-toggle" type="button" disabled={!boxes.length}
    aria-pressed={show} onClick={()=>setShow(v=>!v)}>
    {show?<EyeOff size={15}/>:<Eye size={15}/>}
    {show?'Hide regions':'Show regions'}
   </button>
  </div>
  <div className="source-image-canvas">
   <img src={src} alt={alt}/>
   {show&&boxes.length>0&&<svg viewBox={'0 0 '+width+' '+height}
      preserveAspectRatio="xMidYMid meet" className="region-overlay"
      role="img" aria-label={boxes.length+' unverified OCR region outlines'}>
    {boxes.map(box=><g key={box.index}>
      <rect x={box.x1} y={box.y1} width={box.x2-box.x1} height={box.y2-box.y1}
       fill="rgba(75,99,233,0.10)" stroke="#4663f0"
       strokeWidth={Math.max(1.5,width/450)} rx={Math.max(1,width/700)}/>
      <title>{'Region '+box.index+': '+box.text}</title>
    </g>)}
   </svg>}
  </div>
  {boxes.length>0&&<p className="source-image-note">Colored rectangles show automatically proposed text regions, not verified medicine locations.</p>}
 </div>;
}
