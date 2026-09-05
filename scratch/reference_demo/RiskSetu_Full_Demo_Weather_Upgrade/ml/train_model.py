"""Train an experimental model with held-out evaluation, never claimed operational accuracy."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import precision_score,recall_score,f1_score,roc_auc_score,confusion_matrix,average_precision_score,brier_score_loss

FEATURES=['rainfall_24h_mm','rainfall_72h_mm','soil_moisture_pct','slope_deg','historical_landslides','susceptibility']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv');p.add_argument('--output',default='ml/artifacts');p.add_argument('--split',choices=['temporal','spatial'],default='temporal');p.add_argument('--test-size',type=float,default=.2)
    args=p.parse_args()
    if not .1<=args.test_size<=.5: p.error('test-size must be between 0.1 and 0.5')
    with open(args.csv,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    if len(rows)<20: p.error('At least 20 aligned event/non-event samples required')
    if args.split=='temporal':
        if any(not r.get('event_date') for r in rows): p.error('Temporal split requires event_date for every sample')
        from datetime import date
        for r in rows: date.fromisoformat(r['event_date'])
        rows.sort(key=lambda r:r['event_date'])
        cutoff=rows[int(len(rows)*(1-args.test_size))]['event_date']
        train=np.array([i for i,r in enumerate(rows) if r['event_date']<cutoff]);test=np.array([i for i,r in enumerate(rows) if r['event_date']>=cutoff])
    else:
        if any(not r.get('spatial_group') for r in rows): p.error('Spatial split requires spatial_group for every sample')
        groups=[r['spatial_group'] for r in rows]
        train,test=next(GroupShuffleSplit(n_splits=1,test_size=args.test_size,random_state=42).split(rows,groups=groups))
    X=np.array([[float(r[f]) for f in FEATURES] for r in rows]); y=np.array([int(r['label']) for r in rows])
    if not np.isfinite(X).all(): p.error('Features must be finite and complete')
    if set(y)!={0,1} or set(y[train])!={0,1} or set(y[test])!={0,1}: p.error('Both classes must be present in training and holdout; collect more data')
    model=RandomForestClassifier(n_estimators=300,min_samples_leaf=3,class_weight='balanced',random_state=42,n_jobs=-1)
    model.fit(X[train],y[train]);prob=model.predict_proba(X[test])[:,1];pred=(prob>=.5).astype(int)
    metrics={'split':args.split,'train_samples':len(train),'test_samples':len(test),'threshold':.5,
        'precision':precision_score(y[test],pred,zero_division=0),'recall':recall_score(y[test],pred,zero_division=0),
        'f1':f1_score(y[test],pred,zero_division=0),'roc_auc':roc_auc_score(y[test],prob),
        'average_precision':average_precision_score(y[test],prob),'brier_score':brier_score_loss(y[test],prob),
        'confusion_matrix':confusion_matrix(y[test],pred,labels=[0,1]).tolist(),
        'feature_importance':dict(zip(FEATURES,model.feature_importances_.tolist())),
        'operationally_validated':False,'limitations':'Single holdout. Requires leakage review, independent spatial AND temporal validation, probability calibration and authority assessment.'}
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    joblib.dump({'model':model,'features':FEATURES,'metadata':metrics},output/'landslide_model.joblib')
    (output/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2))

if __name__=='__main__': main()
