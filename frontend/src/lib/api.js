const BASE = '/api';
export async function request(path, options = {}) {
  const response = await fetch(BASE + path, { credentials: 'same-origin', ...options });
  const type = response.headers.get('content-type') || '';
  const data = type.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof data === 'object' ? (data.detail || data.message || 'Request failed') : data;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}
export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('en-GB', {
    day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit'
  }).format(date);
}
export const formatEngine = value => ({
  tesseract:'Tesseract',gemini_demo:'Gemini demo OCR',easyocr:'EasyOCR',paddleocr:'PaddleOCR',craft_trocr:'CRAFT + TrOCR'
}[value] || value || 'Unknown');
export async function uploadPrescription(file,engine,preprocess='none') {
  const payload=new FormData(); payload.append('file',file);
  return request('/prescriptions?engine='+encodeURIComponent(engine)+'&preprocess='+encodeURIComponent(preprocess),{method:'POST',body:payload});
}
export async function confirmTranscription(id,corrected_text) {
  return request('/prescriptions/'+encodeURIComponent(id)+'/review',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({corrected_text,reviewer_confirmed:true})
  });
}
export function saveJSON(filename,data) {
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;
  document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
}
