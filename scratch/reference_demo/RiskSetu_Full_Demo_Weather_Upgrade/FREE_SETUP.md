# RiskSetu — zero-cost prototype setup

This build is designed to run without paid APIs for the hackathon prototype.

## Free/no-key providers used by default

- Open-Meteo Forecast API: rainfall, forecast and modelled soil moisture
- Open-Meteo Elevation API: Copernicus DEM GLO-90 elevation; RiskSetu derives a screening slope estimate
- Open-Meteo Flood API: GloFAS modelled river-discharge context
- OpenStreetMap + Leaflet: map
- OSRM public routing service: route alternatives
- Browser/PWA notifications and offline queue: no SMS bill

Attribution is required where applicable. Public free endpoints are rate-limited and have no production SLA; they are appropriate for a prototype, not an emergency production service.

## Optional NASA IMERG

NASA GPM IMERG Early Run is optional and remains disabled until PPS credentials are added. Add them only to `backend/.env`:

```env
PPS_USERNAME=your_pps_username
PPS_PASSWORD=your_pps_password
EARTHDATA_TOKEN=your_earthdata_token
```

Do not put secrets in frontend `.env` and do not commit them.

## Historical landslides — free NASA GLC import

The app can import the public NASA Global Landslide Catalog historical CSV for a prototype signal:

```powershell
python scripts\import_nasa_glc.py --download
```

The NASA Open Data export is historical (not a live feed). The importer limits records to the North-East India bounding region unless `--all` is supplied.

## ML

RiskSetu does not ship a fake trained model. The live dashboard uses the transparent multi-hazard v3 score. If you later prepare an aligned labelled CSV, train the experimental model with:

```powershell
python ml\train_model.py your_training_data.csv --output ml\artifacts
```

If `ml/artifacts/landslide_model.joblib` exists, the backend automatically exposes its experimental probability separately from the transparent score.
