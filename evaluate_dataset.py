"""Usage: python evaluate_dataset.py labeled_predictions.jsonl output.json"""
import json,sys
from medsafe.evaluation import evaluate_jsonl
if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('Usage: python evaluate_dataset.py labeled_predictions.jsonl output.json')
    report=evaluate_jsonl(sys.argv[1]);open(sys.argv[2],'w',encoding='utf-8').write(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
