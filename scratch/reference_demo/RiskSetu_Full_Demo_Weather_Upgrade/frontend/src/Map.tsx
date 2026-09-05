import {useEffect,useState} from 'react';
import {MapContainer,TileLayer,Circle,CircleMarker,Popup,Polyline,useMap} from 'react-leaflet';
import type {Location,Zone,Incident,History,Shelter,Road,Route} from './types';
import 'leaflet/dist/leaflet.css';
export const riskColor=(level:string)=>({LOW:'#22826b',MODERATE:'#cc9b20',HIGH:'#e27b36',CRITICAL:'#ca4550'}[level]||'#68837e');
function Center({center}:{center:Location}){const map=useMap();useEffect(()=>{map.setView([center.latitude,center.longitude],10) },[center,map]);return null}
export interface MapProps {center:Location;zones:Zone[];incidents:Incident[];history?:History[];shelters?:Shelter[];roads?:Road[];routes?:Route[];selectedRoute?:string;onIncident?:(incident:Incident)=>void;large?:boolean}
// UI provider boundary: replace this renderer without changing route scoring or API models.
export function RiskMap({center,zones,incidents,history=[],shelters=[],roads=[],routes=[],selectedRoute,onIncident,large}:MapProps){
 const [layers,setLayers]=useState({risk:true,incidents:true,history:!zones.length&&!!history.length,shelters:true,roads:true,rainfall:false});
 const [tileError,setTileError]=useState(false);
 return <div className={`map-shell ${large?'map-large':''}`}>
  <MapContainer center={[center.latitude,center.longitude]} zoom={10} scrollWheelZoom className="gis-map">
   <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" eventHandlers={{tileerror:()=>setTileError(true),tileload:()=>setTileError(false)}}/>
   <Center center={center}/>
   {layers.risk&&zones.map(z=><Circle key={z.id} center={[z.latitude,z.longitude]} radius={z.radius_m} pathOptions={{color:riskColor(z.risk_level),fillColor:riskColor(z.risk_level),fillOpacity:.19,weight:1.5}}><Popup><b>{z.name} · {z.risk_level}</b><p>{z.risk_score}/100 · {z.data_mode}</p><p>{z.contributing_factors.join(', ')}</p><small>{z.source}</small></Popup></Circle>)}
   {layers.rainfall&&zones.map(z=><Circle key={z.id} center={[z.latitude,z.longitude]} radius={3000} pathOptions={{color:'#388faf',fillOpacity:Math.min(.65,(z.features.rainfall_24h_mm||0)/400),weight:0}}><Popup>{z.name}: {z.features.rainfall_24h_mm??'Unknown'} mm / 24h · {z.data_mode}</Popup></Circle>)}
   {layers.incidents&&incidents.filter(i=>!['RESOLVED','REJECTED'].includes(i.status)).map(i=><CircleMarker key={i.id} center={[i.latitude,i.longitude]} radius={8} pathOptions={{color:'#fff',weight:2,fillColor:riskColor(i.severity),fillOpacity:1}} eventHandlers={{click:()=>onIncident?.(i)}}><Popup><b>{i.type}</b><p>{i.description}</p><p>{i.status} · {i.data_mode}</p></Popup></CircleMarker>)}
   {layers.history&&history.map(h=><CircleMarker key={h.id} center={[h.latitude,h.longitude]} radius={5} pathOptions={{color:'#796796'}}><Popup>{h.district} · {h.event_date}<p>{h.source} · {h.data_mode}</p></Popup></CircleMarker>)}
   {layers.shelters&&shelters.map(s=><CircleMarker key={s.id} center={[s.latitude,s.longitude]} radius={7} pathOptions={{color:'#156e59',fillOpacity:1}}><Popup>{s.name}<p>{s.available_capacity} spaces · {s.data_mode}</p></Popup></CircleMarker>)}
   {layers.roads&&roads.map(r=><CircleMarker key={r.id} center={[r.latitude,r.longitude]} radius={6} pathOptions={{color:r.status==='BLOCKED'?'#bc2c40':'#dd9c28',fillOpacity:1}}><Popup>{r.road_identifier} · {r.status}</Popup></CircleMarker>)}
   {routes.map(r=><Polyline key={r.id} positions={r.coordinates.map(([lon,lat])=>[lat,lon])} pathOptions={{color:r.excluded?'#be4552':r.classification==='SAFEST ROUTE'?'#24725d':'#d29a37',weight:selectedRoute===r.id?7:4,opacity:!selectedRoute||selectedRoute===r.id?1:.4,dashArray:r.data_mode==='MOCK'?'10 7':undefined}}/>)}
   <CircleMarker center={[center.latitude,center.longitude]} radius={7} pathOptions={{color:'white',weight:3,fillColor:'#287bc7',fillOpacity:1}}><Popup>Selected location</Popup></CircleMarker>
  </MapContainer>
  {tileError&&<div className="basemap-error">Basemap unavailable. Hazard overlays remain visible.</div>}
  <div className="map-controls" aria-label="Map layers">{Object.entries(layers).map(([key,value])=><label key={key}><input type="checkbox" checked={value} onChange={()=>setLayers({...layers,[key]:!value})}/>{({risk:'Risk zones',incidents:'Incidents',history:'History',shelters:'Shelters',roads:'Road status',rainfall:'Rainfall'} as Record<string,string>)[key]}</label>)}</div>
  <div className="map-legend"><span><i style={{background:'#22826b'}}/>Low</span><span><i style={{background:'#cc9b20'}}/>Moderate</span><span><i style={{background:'#e27b36'}}/>High</span><span><i style={{background:'#ca4550'}}/>Critical</span></div>
 </div>
}
