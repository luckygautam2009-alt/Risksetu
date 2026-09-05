from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Location(Model):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class RiskRequest(Location):
    rainfall_24h_mm: float = Field(ge=0, le=3000)
    rainfall_72h_mm: float = Field(ge=0, le=9000)
    soil_moisture_pct: float = Field(ge=0, le=100)
    slope_deg: float = Field(ge=0, le=90)
    historical_landslides: int = Field(default=0, ge=0)
    susceptibility: float = Field(default=.5, ge=0, le=1)
    rainfall_1h: float = Field(default=0, ge=0, le=1000)
    elevation: float = Field(default=0, ge=-500, le=9000)
    vegetation_index: float | None = Field(default=None, ge=-1, le=1)
    citizen_signal_score: float = Field(default=0, ge=0, le=1)

class IncidentCreate(Location):
    type: Literal['Landslide','Slope crack','Road blockage','Flash flood','Heavy rainfall','Falling rocks','Other']
    description: str = Field(min_length=8, max_length=3000)
    severity: Literal['LOW','MODERATE','HIGH','CRITICAL'] = 'MODERATE'
    client_id: str = Field(min_length=10, max_length=100)

class Confirmation(Location):
    confirmation: Literal['YES','NO','UNSURE']

class Verify(Model):
    status: Literal['VERIFIED','REJECTED','RESOLVED']
    notes: str = Field(min_length=5, max_length=2000)

class Dispatch(Model):
    assigned_team: str = Field(min_length=2, max_length=200)
    priority: Literal['LOW','MODERATE','HIGH','CRITICAL'] = 'HIGH'
    instructions: str = Field(min_length=5, max_length=2000)

class Shelter(Location):
    name: str = Field(min_length=3, max_length=200)
    capacity: int = Field(ge=1, le=100000)
    current_occupancy: int = Field(default=0, ge=0)
    contact: str = Field(min_length=3, max_length=150)
    district: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    verified: bool = True
    active: bool = True

class RouteRequest(Model):
    origin: Location
    destination: Location

class RoadUpdate(Location):
    road_identifier: str = Field(min_length=3, max_length=200)
    status: Literal['OPEN','CAUTION','BLOCKED']
    risk_score: float = Field(default=0, ge=0, le=100)
    incident_id: str | None = None

class ProfileUpdate(Model):
    full_name: str = Field(min_length=2, max_length=150)
    preferred_language: Literal['en','hi','as'] = 'en'

class Approval(Model):
    approved: bool

class Login(Model):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)

class Signup(Login):
    full_name: str = Field(min_length=2, max_length=150)

class SOSCreate(Location):
    emergency_type: Literal['MEDICAL','LANDSLIDE','FLOOD','TRAPPED','ACCIDENT','OTHER'] = 'OTHER'
    message: str = Field(default='', max_length=1000)
    location_accuracy: float | None = Field(default=None, ge=0, le=100000)
    client_id: str = Field(min_length=8, max_length=120)
    network_state: str | None = Field(default=None, max_length=40)
    battery_pct: float | None = Field(default=None, ge=0, le=100)

class SOSUpdate(Model):
    status: Literal['ACKNOWLEDGED','DISPATCHED','RESOLVED','CANCELLED']
    notes: str = Field(default='', max_length=2000)
    assigned_officer_id: str | None = None


class OfficerMassAlert(Location):
    radius_m: int = Field(default=500, ge=100, le=10000)
    title: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=5, max_length=1000)
    severity: Literal['WATCH','WARNING','EMERGENCY'] = 'WARNING'
    siren: bool = True
