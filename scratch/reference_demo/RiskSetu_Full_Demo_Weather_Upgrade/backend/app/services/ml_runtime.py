"""Optional runtime for a locally trained experimental landslide classifier.

No synthetic model is bundled. If ml/artifacts/landslide_model.joblib exists,
RiskSetu can expose its experimental probability while keeping the transparent
risk score as the operational prototype fallback.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

ARTIFACT = Path(__file__).resolve().parents[3] / "ml" / "artifacts" / "landslide_model.joblib"
_bundle = None
_load_error = None


def _load():
    global _bundle,_load_error
    if _bundle is not None or _load_error is not None: return
    try:
        import joblib
        if ARTIFACT.exists(): _bundle=joblib.load(ARTIFACT)
        else: _load_error="No trained artifact installed"
    except Exception as exc:
        _load_error=str(exc)


def predict(features: dict[str, Any]) -> dict[str, Any]:
    _load()
    if not _bundle:
        return {"available":False,"probability":None,"model_status":_load_error or "Unavailable"}
    names=_bundle.get("features") or []
    try:
        row=[float(features[name]) for name in names]
    except (KeyError,TypeError,ValueError):
        return {"available":False,"probability":None,"model_status":"Required ML features are incomplete"}
    try:
        model=_bundle["model"]; probability=float(model.predict_proba([row])[0][1])
        meta=_bundle.get("metadata") or {}
        return {"available":True,"probability":round(probability,3),"model_status":"EXPERIMENTAL","metrics":meta}
    except Exception as exc:
        return {"available":False,"probability":None,"model_status":f"Model error: {exc}"}
