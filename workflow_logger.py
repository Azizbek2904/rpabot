"""📊 Workflow Logger — FINAL | BTEC L6"""
import os,json,csv
from datetime import datetime
D="logs"; F=os.path.join(D,"ops.csv"); S=os.path.join(D,"stats.json")
class WorkflowLogger:
    def __init__(self):
        os.makedirs(D,exist_ok=True)
        if not os.path.exists(F):
            with open(F,'w',newline='',encoding='utf-8') as f: csv.writer(f).writerow(['ts','op','cid','det','st'])
    def log(self,op,cid,det="",st="ok"):
        try:
            with open(F,'a',newline='',encoding='utf-8') as f: csv.writer(f).writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'),op,cid,det,st])
            d=datetime.now().strftime('%Y-%m-%d'); s={}
            if os.path.exists(S):
                with open(S,'r') as f: s=json.load(f)
            if d not in s: s[d]={'t':0,'ok':0,'err':0,'ops':{}}
            s[d]['t']+=1; s[d]['ok' if st=='ok' else 'err']+=1; s[d]['ops'][op]=s[d]['ops'].get(op,0)+1
            with open(S,'w') as f: json.dump(s,f,indent=2)
        except: pass
    def get_today_stats(self):
        try:
            if os.path.exists(S):
                with open(S,'r') as f: return json.load(f).get(datetime.now().strftime('%Y-%m-%d'),{})
        except: return {}
    def get_all_stats(self):
        try:
            if os.path.exists(S):
                with open(S,'r') as f: return json.load(f)
        except: return {}
    def get_operations_log(self,n=50):
        try:
            r=[]
            with open(F,'r',encoding='utf-8') as f:
                for row in csv.DictReader(f): r.append(row)
            return r[-n:]
        except: return []
