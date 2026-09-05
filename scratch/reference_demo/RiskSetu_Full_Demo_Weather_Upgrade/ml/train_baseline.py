"""Training skeleton: expected CSV columns:
rainfall_24h_mm,rainfall_72h_mm,soil_moisture_pct,slope_deg,historical_landslides,susceptibility,label
label: 0/1 landslide occurrence in the chosen prediction horizon.
"""
from train_model import main
if __name__ == '__main__':
    main()
