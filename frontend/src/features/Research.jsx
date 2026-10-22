import React from 'react';
import { Activity, BookOpen, BrainCircuit, CheckCircle2, Database, Gauge, ShieldAlert, Target } from 'lucide-react';
import {Badge,Notice} from '../components/Status.jsx';
const titles={tesseract:['Tesseract','OCR baseline'],easyocr:['EasyOCR','Neural OCR recognizer'],paddleocr:['PaddleOCR','Document understanding'],trocr:['TrOCR + CRAFT','Handwriting recognition pipeline']};
const targets=[
 ['Character error rate','≤ 10%','CER'],['Medicine name accuracy','≥ 90%','Exact field match'],['Dosage field accuracy','≥ 90%','Exact field match'],
 ['Overdose precision & recall','≥ 85%','Independent alert labels'],['Age-check accuracy','≥ 85%','Independent age labels'],['Processing speed','≤ 10s','Per-image GPU benchmark']
];
export default function Research({research={},models={}}){
 const installed=models.benchmark_engines||{};
 return <div className="stack-lg">
   <div className="research-banner"><div className="research-banner-icon"><BrainCircuit size={27}/></div>
    <div><h2>Reproducible OCR evaluation</h2><p>Four engines, shared held-out images and human-verified references. Model installation does not imply validated accuracy.</p></div>
    <Badge tone="amber">Independent results required</Badge></div>
   <section className="surface"><div className="section-top"><div><h3>Recognition engines</h3><p>Availability reported by this running environment</p></div></div>
    <div className="research-engines">{Object.entries(titles).map(([id,[name,description]])=><div className="research-engine" key={id}>
    <div className="research-engine-icon"><BrainCircuit size={21}/></div><div><strong>{name}</strong><p>{description}</p></div><Badge tone={installed[id]?'teal':'amber'}>{installed[id]?'Package detected':'Setup required'}</Badge></div>)}</div>
   </section>
   <section className="surface"><div className="section-top"><div><h3>Thesis acceptance criteria</h3><p>Targets below are goals, not measured achievements</p></div><Target className="muted-icon" size={20}/></div>
    <div className="criteria-table table-scroll"><table className="data-table"><thead><tr><th>Metric</th><th>Acceptance criterion</th><th>Evaluation method</th><th>Evidence</th></tr></thead><tbody>
     {targets.map(([name,target,method])=><tr key={name}><td><strong>{name}</strong></td><td><span className="target-number">{target}</span></td><td>{method}</td><td><Badge tone="amber">Not independently verified</Badge></td></tr>)}</tbody></table></div>
   </section>
   <div className="research-bottom"><section className="surface"><div className="section-top"><div><h3>Evaluation protocol</h3><p>Requirements for a defensible research result</p></div></div>
     <ol className="protocol-list"><li><span>1</span> Use identical held-out images and preprocessing configurations for all four engines.</li>
     <li><span>2</span> Confirm image identifiers, ground-truth transcription, dosage fields and independent reviewer IDs.</li>
     <li><span>3</span> Report character and word error, medication/dose accuracy, alert precision and recall.</li>
     <li><span>4</span> Record model versions, inference environment, elapsed time and failure cases.</li></ol>
    </section>
    <section className="surface"><div className="section-top"><div><h3>Clinical safety policy</h3><p>Non-negotiable research safeguards</p></div></div>
     <div className="policy-item"><ShieldAlert size={18}/><span>Only provenance-linked, qualified-reviewer-approved drug rules can produce dosage flags.</span></div>
     <div className="policy-item"><Database size={18}/><span>DailyMed and openFDA search results are source evidence, not automatically trusted dosage limits.</span></div>
     <div className="policy-item"><Activity size={18}/><span>Unverified medicine identity, age or formulation must remain unresolved.</span></div>
     <Notice type="warning">This workspace cannot approve medicines, prescribe or authorize dispensing.</Notice>
    </section></div>
 </div>;
}
