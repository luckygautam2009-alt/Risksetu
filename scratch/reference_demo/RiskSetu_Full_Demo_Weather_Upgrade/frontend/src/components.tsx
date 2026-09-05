import {useEffect,useRef,type ReactNode} from 'react';
import {X,ArrowUpRight,LoaderCircle} from 'lucide-react';
import type {Provenance,Location} from './types';
export function Badge({value}:{value:string}){return <span className={'badge '+value.toLowerCase().replaceAll('_','-').replaceAll(' ','-')}>{value.replaceAll('_',' ')}</span>}
export function Source({item}:{item:Partial<Provenance>}){return <div className="source"><Badge value={item.data_mode||'UNKNOWN'}/><span>{item.source||'Source unavailable'}{item.updated_at&&<> · {new Date(item.updated_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</>}</span></div>}
export function Empty({title,children}:{title:string;children?:ReactNode}){return <div className="empty"><div className="empty-mark">◇</div><h3>{title}</h3><p>{children}</p></div>}
export function SectionTitle({title,sub,action,onAction}:{title:string;sub?:string;action?:string;onAction?:()=>void}){return <div className="section-title"><div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div>{action&&<button className="text-button" onClick={onAction}>{action}<ArrowUpRight size={16}/></button>}</div>}
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{ref.current?.showModal();return()=>ref.current?.close()},[]);
 return <dialog ref={ref} className="modal" onCancel={onClose}><div className="modal-top"><h2>{title}</h2><button className="icon-button" aria-label="Close" onClick={onClose}><X/></button></div>{children}</dialog>
}
export function Coordinates({value,onChange}:{value:Location;onChange:(value:Location)=>void}){return <div className="form-grid"><label>Latitude<input required type="number" step="any" min="-90" max="90" value={value.latitude} onChange={e=>onChange({...value,latitude:Number(e.target.value)})}/></label><label>Longitude<input required type="number" step="any" min="-180" max="180" value={value.longitude} onChange={e=>onChange({...value,longitude:Number(e.target.value)})}/></label></div>}
export function Busy({busy,children}:{busy:boolean;children:ReactNode}){return <>{busy&&<LoaderCircle size={16} className="spin"/>}{children}</>}
export function ErrorText({error}:{error:string}){return error?<p role="alert" className="error-text">{error}</p>:null}
export const message=(e:unknown)=>e instanceof Error?e.message:'Something went wrong. Please try again.';
export function getGPS():Promise<Location>{return new Promise((resolve,reject)=>{if(!navigator.geolocation)return reject(new Error('Location is not supported'));navigator.geolocation.getCurrentPosition(p=>resolve({latitude:p.coords.latitude,longitude:p.coords.longitude}),e=>reject(new Error(e.message)),{enableHighAccuracy:true,timeout:15000,maximumAge:0})})}
