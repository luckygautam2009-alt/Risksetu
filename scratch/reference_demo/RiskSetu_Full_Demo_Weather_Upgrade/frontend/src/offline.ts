import {openDB} from 'idb';
import {api,post,ApiError} from './api';
import type {Incident,SOSEvent} from './types';
export interface PendingReport {id:string;userId:string;body:Record<string,unknown>;file?:File;incidentId?:string;error?:string;createdAt:string}
export interface PendingSOS {id:string;userId:string;body:Record<string,unknown>;serverId?:string;error?:string;createdAt:string;status:'QUEUED_OFFLINE'|'FAILED'}
const db=openDB('risksetu-local',2,{upgrade(db,oldVersion){if(oldVersion<1){db.createObjectStore('reports',{keyPath:'id'});db.createObjectStore('cache')}if(oldVersion<2)db.createObjectStore('sos',{keyPath:'id'})}});
export async function queueReport(report:PendingReport){await(await db).put('reports',report)}
export async function queued(userId:string):Promise<PendingReport[]>{return(await(await db).getAll('reports')).filter((x:PendingReport)=>x.userId===userId)}
export async function queueSOS(item:PendingSOS){await(await db).put('sos',item)}
export async function queuedSOS(userId:string):Promise<PendingSOS[]>{return(await(await db).getAll('sos')).filter((x:PendingSOS)=>x.userId===userId)}
export async function cache(key:string,value:unknown){await(await db).put('cache',{value,savedAt:new Date().toISOString()},key)}
export async function cached<T>(key:string):Promise<{value:T;savedAt:string}|undefined>{return(await db).get('cache',key)}
let syncing=false;
export async function syncReports(userId:string){
 if(syncing)return;syncing=true;
 try{for(const report of await queued(userId)){
  try{
   if(!report.incidentId){const incident=await post<Incident>('/api/incidents',report.body);report.incidentId=incident.id;await queueReport(report)}
   if(report.file){const data=new FormData();data.append('file',report.file);await api(`/api/incidents/${report.incidentId}/media`,{method:'POST',body:data})}
   await(await db).delete('reports',report.id);
  }catch(error){report.error=error instanceof Error?error.message:'Sync failed';await queueReport(report);if(!(error instanceof ApiError)||error.status===401||error.status>=500)break}
 }}finally{syncing=false}
}
export async function syncSOS(userId:string){
 if(!navigator.onLine)return;
 for(const item of await queuedSOS(userId)){
  try{const sent=await post<SOSEvent>('/api/sos',item.body);item.serverId=sent.id;await(await db).delete('sos',item.id)}
  catch(error){item.status='FAILED';item.error=error instanceof Error?error.message:'SOS sync failed';await queueSOS(item);break}
 }
}
