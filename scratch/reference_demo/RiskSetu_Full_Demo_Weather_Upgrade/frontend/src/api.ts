import {createClient, type SupabaseClient} from '@supabase/supabase-js';
const BASE=import.meta.env.VITE_API_URL||'';
export let token=sessionStorage.getItem('risksetu-token')||'';
export let supabase:SupabaseClient|null=null;
export function setToken(value:string){token=value;value?sessionStorage.setItem('risksetu-token',value):sessionStorage.removeItem('risksetu-token')}
export async function configureAuth(url:string,key:string){
  if(!url||!key)return;
  supabase=createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true}});
  const {data}=await supabase.auth.getSession();if(data.session)setToken(data.session.access_token);
  supabase.auth.onAuthStateChange((_event,session)=>setToken(session?.access_token||''));
}
export class ApiError extends Error{constructor(message:string,public status:number){super(message)}}
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const headers=new Headers(init.headers);if(token)headers.set('Authorization',`Bearer ${token}`);
  if(init.body&&!(init.body instanceof FormData))headers.set('Content-Type','application/json');
  const r=await fetch(BASE+path,{signal:AbortSignal.timeout(path.includes('briefing')?60000:30000),...init,headers});
  if(!r.ok){const body=await r.json().catch(()=>({detail:r.statusText}));throw new ApiError(typeof body.detail==='string'?body.detail:'Please check the entered values',r.status)}
  return r.json();
}
export const post=<T,>(path:string,body:unknown={})=>api<T>(path,{method:'POST',body:JSON.stringify(body)});
export async function mediaUrl(id:string){
  const r=await fetch(BASE+'/api/media/'+id,{headers:{Authorization:`Bearer ${token}`}});
  if(!r.ok)throw new Error('Unable to load evidence');
  if(r.headers.get('content-type')?.includes('application/json'))return (await r.json()).url as string;
  return URL.createObjectURL(await r.blob());
}
export function subscribe(onChange:()=>void){
  const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  // Authenticated event stream carries invalidation types, never incident or user data.
  async function connect(){
    try{
      const response=await fetch(BASE+'/api/events',{headers:{Authorization:`Bearer ${token}`},signal:controller.signal});
      if(!response.ok||!response.body)throw new Error('Stream unavailable');
      onChange();const reader=response.body.getReader();const decoder=new TextDecoder();let pending='';
      while(!controller.signal.aborted){const chunk=await reader.read();if(chunk.done)break;pending+=decoder.decode(chunk.value,{stream:true});
        let end;while((end=pending.indexOf('\n\n'))>=0){const event=pending.slice(0,end);pending=pending.slice(end+2);if(event.startsWith('data:')&&!event.includes('connected'))onChange()}}
    }catch{/* Retry with backoff; normal HTTP actions remain available. */}
    if(!controller.signal.aborted)timer=setTimeout(connect,15000);
  }
  void connect();
  const channel=supabase?.channel('risksetu-updates').on('postgres_changes',{event:'*',schema:'public'},onChange).subscribe();
  return ()=>{controller.abort();clearTimeout(timer);if(channel)void supabase?.removeChannel(channel)};
}
