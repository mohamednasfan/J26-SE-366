import React from 'react';
import OCRComparison from './OCRComparison.jsx';
import { Activity, BookOpen, BrainCircuit, CheckCircle2, Database, Gauge, ShieldAlert, Target } from 'lucide-react';
import {Badge,Notice} from '../components/Status.jsx';
const titles={tesseract:['Tesseract','OCR baseline'],easyocr:['EasyOCR','Neural OCR recognizer'],paddleocr:['PaddleOCR','Document understanding'],trocr:['TrOCR + CRAFT','Handwriting recognition pipeline']};
const targets=[
 ['Character error rate','≤ 10%','CER'],['Medicine name accuracy','≥ 90%','Exact field match'],['Dosage field accuracy','≥ 90%','Exact field match'],
 ['Overdose precision & recall','≥ 85%','Independent alert labels'],['Age-check accuracy','≥ 85%','Independent age labels'],['Processing speed','≤ 10s','Per-image GPU benchmark']
];
export default function Research({research={},models={},historical={},benchmarks={}}){
 const installed=models.benchmark_engines||{};
 return <div className="stack-lg">
   <div className="research-banner"><div className="research-banner-icon"><BrainCircuit size={27}/></div>
    <div><h2>Reproducible OCR evaluation</h2><p>Four engines, shared held-out images and human-verified references. Model installation does not imply validated accuracy.</p></div>
    <Badge tone="amber">Independent results required</Badge></div>
   <OCRComparison/>
   {historical.n_aligned_images>0&&<section className="surface"><div className="section-top"><div><h3>Archived four-engine comparison</h3><p>{historical.n_aligned_images} matching original-variant medicine-word images · earlier experiment, not final trained checkpoint</p></div><Badge tone="amber">Historical baseline</Badge></div>
    <div className="table-scroll"><table className="data-table"><thead><tr><th>OCR engine</th><th>Character error</th><th>Word error</th><th>Medicine accuracy</th></tr></thead>
    <tbody>{Object.entries(historical.engines||{}).map(([name,metrics])=><tr key={name}><td><strong>{name==='trocr_historical'?'TrOCR (historical)':name.charAt(0).toUpperCase()+name.slice(1)}</strong></td>
      <td>{(metrics.micro_CER*100).toFixed(2)}%</td><td>{(metrics.micro_WER*100).toFixed(2)}%</td><td><span className="target-number">{(metrics.medicine_accuracy*100).toFixed(2)}%</span> <small>({metrics.correct}/780)</small></td></tr>)}</tbody></table></div>
    <div className="research-evidence-note">These matched word-image measurements come from the archived Kaggle-dataset experiment; they do not assess age, administered doses, or the later Notebook 44 fine-tuned TrOCR model.</div>
   </section>}
   <section className="surface"><div className="section-top"><div><h3>Current held-out benchmark</h3><p>Results appear when a human-verified test manifest has been evaluated by all selected OCR engines</p></div><Badge tone={benchmarks.status==='HUMAN_VERIFIED_TEST'?'teal':'amber'}>{benchmarks.status==='HUMAN_VERIFIED_TEST'?'Human-verified cohort':'No verified run configured'}</Badge></div>
   {Object.keys(benchmarks.engines||{}).length>0?<div className="table-scroll"><table className="data-table"><thead><tr><th>Engine</th><th>Coverage</th><th>CER</th><th>Medicine name</th><th>95th-percentile time</th></tr></thead>
   <tbody>{Object.entries(benchmarks.engines).map(([name,item])=><tr key={name}><td>{name}</td><td>{(Number(item.coverage||0)*100).toFixed(0)}%</td><td>{item.metrics?.ocr?.CER!=null?(item.metrics.ocr.CER*100).toFixed(2)+'%':'Not verified'}</td>
    <td>{item.metrics?.fields?.medicine?.accuracy!=null?(item.metrics.fields.medicine.accuracy*100).toFixed(2)+'%':'Not verified'}</td>
    <td>{item.timing?.p95_s!=null?item.timing.p95_s+' s':'—'}</td></tr>)}</tbody></table></div>:
    <div className="research-evidence-note">No independent benchmark JSON is loaded in this installation. Run <code>python -m backend.app.research.benchmark</code> with human-reviewed test images, then configure MEDSAFE_BENCHMARK_RESULTS.</div>}
   </section>
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
