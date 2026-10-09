import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { createClient } from '@supabase/supabase-js';
import { Activity, ArrowUp, AudioLines, Brain, Check, ChevronRight, CircleStop, Cloud, Cpu, History, MessageSquare, Mic, Monitor, Plus, Search, Settings as SettingsIcon, ShieldCheck, Sparkles, X } from 'lucide-react';
import { API } from './api';
import type { Action, Connection, Message, Settings, Status, Task } from './types';

type Page = 'assistant' | 'tasks' | 'memory' | 'activity' | 'settings';
type Memory = {id: string; content: string};
type Event = {id: string; kind: string; detail: string; created: number};
const links: {page: Page; label: string; icon: typeof Brain}[] = [
  {page:'assistant',label:'Assistant',icon:MessageSquare}, {page:'tasks',label:'Task monitor',icon:Activity},
  {page:'memory',label:'Memory',icon:Brain}, {page:'activity',label:'Activity',icon:History}, {page:'settings',label:'Settings',icon:SettingsIcon},
];

export function Orb({state}: {state: string}) {
  return <div className={`orb-stage ${state}`} aria-label={`ULTRON ${state}`}>
    <div className="orbit orbit-one"/><div className="orbit orbit-two"/>
    <div className="orb"><div className="orb-inner"/><div className="orb-light"/></div>
    <div className="orb-floor"/>
  </div>;
}

function Connect({onConnect}: {onConnect(c: Connection): void}) {
  const [mode,setMode] = useState<'local'|'cloud'>('local');
  const [base,setBase] = useState('http://127.0.0.1:8765');
  const [token,setToken] = useState('');
  const [url,setUrl] = useState(''); const [key,setKey] = useState('');
  const [email,setEmail] = useState(''); const [otp,setOtp] = useState('');
  const [sent,setSent] = useState(false); const [error,setError] = useState(''); const [busy,setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setBusy(true);
    try {
      if (mode === 'local') {
        const parsed = new URL(base);
        if (parsed.protocol !== 'http:' || !['127.0.0.1','localhost'].includes(parsed.hostname)) throw new Error('Local mode requires a loopback HTTP address.');
        const c: Connection = {base,token,mode}; await new API(c).request('/settings'); onConnect(c);
      } else {
        if (new URL(base).protocol !== 'https:' || new URL(url).protocol !== 'https:') throw new Error('Cloud services require HTTPS.');
        const auth = createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}});
        if (!sent) {
          const {error} = await auth.auth.signInWithOtp({email,options:{shouldCreateUser:false}});
          if (error) throw error; setSent(true);
        } else {
          const {data,error} = await auth.auth.verifyOtp({email,token:otp,type:'email'});
          if (error || !data.session) throw error || new Error('No session returned');
          const c:Connection={base,mode,token:data.session.access_token,supabaseUrl:url,supabaseKey:key};
          const registered=await new API(c).request<{device_token:string}>('/devices','POST',{id:crypto.randomUUID(),name:'ULTRON web session',platform:navigator.platform});
          onConnect({...c,deviceToken:registered.device_token});
        }
      }
    } catch(e) { setError(String(e instanceof Error ? e.message : e)); } finally {setBusy(false);}
  }
  return <main className="connect"><div className="brand">U<span>ULTRON</span></div><Orb state="idle"/>
    <h1>Your personal intelligence.</h1><p>Connect your desktop agent or authenticated cloud backend.</p>
    <form className="panel connect-form" onSubmit={submit}>
      <div className="segmented"><button type="button" className={mode==='local'?'selected':''} onClick={()=>{setMode('local');setBase('http://127.0.0.1:8765');}}>Desktop</button><button type="button" className={mode==='cloud'?'selected':''} onClick={()=>{setMode('cloud');setBase('');}}>Cloud</button></div>
      <label>{mode==='local'?'Agent address':'Worker URL'}<input required value={base} onChange={e=>setBase(e.target.value)} placeholder="https://ultron.example.workers.dev"/></label>
      {mode==='local'? <label>Local session token<input type="password" required value={token} onChange={e=>setToken(e.target.value)} autoComplete="off"/></label> : <>
        <label>Supabase URL<input required value={url} onChange={e=>setUrl(e.target.value)}/></label>
        <label>Supabase publishable / anon key<input required value={key} onChange={e=>setKey(e.target.value)}/></label>
        <label>Your registered email<input type="email" required value={email} onChange={e=>setEmail(e.target.value)}/></label>
        {sent&&<label>Email code<input required value={otp} onChange={e=>setOtp(e.target.value)} autoComplete="one-time-code"/></label>}
      </>}
      {error&&<p className="error" role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?'Connecting…': mode==='cloud'&&!sent?'Send sign-in code':'Connect'}<ChevronRight size={16}/></button>
      <small>Tokens remain in memory. ₹0 budget · No paid providers activated.</small>
    </form>
  </main>;
}

export function App() {
  const [connection,setConnection] = useState<Connection>(); const [startup,setStartup] = useState('');
  const [page,setPage] = useState<Page>('assistant'); const [api,setApi] = useState<API>();
  const [settings,setSettings] = useState<Settings>(); const [status,setStatus] = useState<Status>();
  const [tasks,setTasks] = useState<Task[]>([]); const [events,setEvents] = useState<Event[]>([]);
  const [actions,setActions] = useState<Action[]>([]); const [memories,setMemories] = useState<Memory[]>([]);
  const [suggestions,setSuggestions] = useState<string[]>([]); const [messages,setMessages] = useState<Message[]>([]);
  const [conversation,setConversation] = useState<string>(); const [histories,setHistories] = useState<{id:string;title:string}[]>([]);
  const [text,setText] = useState(''); const [busy,setBusy] = useState(false); const [error,setError] = useState('');
  const [screenImage,setScreenImage] = useState<string>();
  const [memoryText,setMemoryText] = useState(''); const [query,setQuery] = useState('');
  const [action,setAction] = useState('reminder'); const [args,setArgs] = useState('{"message":""}');
  const [interval,setIntervalValue] = useState(''); const [schedules,setSchedules] = useState<{id:string;action:string;enabled:number}[]>([]);
  const lastEvent = useRef<string | undefined>(undefined); const bottom = useRef<HTMLDivElement>(null);
  const lastVoice = useRef<string | undefined>(undefined);
  const connect = useCallback((c:Connection)=>{setConnection(c);setApi(new API(c));},[]);
  useEffect(()=>{if(window.ultron) window.ultron.session().then(connect).catch(e=>setStartup(String(e.message)));},[connect]);
  const report = useCallback((e:unknown)=>setError(e instanceof Error ? e.message : String(e)),[]);
  async function perform(path:string,method='POST',body?:unknown) {
    if(!api) return; setError('');
    try { const value=await api.request(path,method,body); await refresh(); return value; } catch(e){report(e);}
  }
  const refresh = useCallback(async()=>{
    if(!api) return;
    const [s,t,e] = await Promise.all([api.request<Status>('/status'),api.request<Task[]>('/tasks'),api.request<Event[]>('/events')]);
    setStatus(s);setTasks(t);setEvents(e);
    if(s.voice.conversation_id&&s.voice.transcript&&lastVoice.current!==s.voice.transcript&&!s.busy){
      const history=await api.request<Message[]>(`/conversations/${s.voice.conversation_id}`);
      setMessages(history);setConversation(s.voice.conversation_id);lastVoice.current=s.voice.transcript;
    }
    const reminder=e.find(item=>item.kind==='reminder');
    if(reminder&&lastEvent.current&&reminder.id!==lastEvent.current) window.ultron?.notify('ULTRON reminder',reminder.detail).catch(()=>{});
    if(reminder) lastEvent.current=reminder.id;
  },[api]);
  useEffect(()=>{
    if(!api) return;
    refresh().catch(report);
    Promise.all([api.request<Settings>('/settings'),api.request<Action[]>('/actions'),api.request<string[]>('/recommendations'),api.request<{id:string;title:string}[]>('/conversations')])
      .then(([s,a,r,h])=>{setSettings(s);setActions(a);setSuggestions(r);setHistories(h);}).catch(report);
    const timer=setInterval(()=>refresh().catch(report),api.connection.mode==='cloud'?15000:3000);return()=>clearInterval(timer);
  },[api,refresh,report]);
  useEffect(()=>{if(!api)return;if(page==='memory')api.request<Memory[]>(`/memories?q=${encodeURIComponent(query)}`).then(setMemories).catch(report);
    if(page==='tasks')api.request<typeof schedules>('/schedules').then(setSchedules).catch(report);
  },[page,query,api,tasks.length,report]);
  useEffect(()=>{bottom.current?.scrollIntoView?.({behavior:'smooth'});},[messages,busy]);
  async function send(e?:FormEvent) {
    e?.preventDefault();if(!api||!text.trim()||busy)return;
    const prompt=text;const image=screenImage;setText('');setScreenImage(undefined);setBusy(true);setError('');setMessages(m=>[...m,{role:'user',content:prompt}]);
    try {const r=await api.request<{conversation_id:string;message:string}>('/chat','POST',{message:prompt,conversation_id:conversation,...(image?{image}:{})});
      setConversation(r.conversation_id);setMessages(m=>[...m,{role:'assistant',content:r.message}]);
      setHistories(await api.request('/conversations')); await refresh();
    }catch(e){report(e);}finally{setBusy(false);}
  }
  async function saveSettings(values:Partial<Settings>) {if(!api)return;setError('');try{setSettings(await api.request('/settings','PATCH',values));await refresh();}catch(e){report(e);}}
  async function exportData(){if(!api)return;try{const data=await api.request('/export');const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='ultron-export.json';a.click();URL.revokeObjectURL(url);}catch(e){report(e);}}
  if(!connection||!api)return <>{startup&&<div className="error startup" role="alert">{startup}</div>}<Connect onConnect={connect}/></>;
  const local=connection.mode==='local';
  const orbState=busy||status?.busy?'thinking':status?.voice.state==='speaking'?'speaking':status?.voice.running?'listening':'idle';
  const pending=tasks.filter(t=>t.status==='awaiting_approval').length;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand">U<span>ULTRON<small>PERSONAL INTELLIGENCE</small></span></div>
      <nav aria-label="Main navigation">{links.map(l=><button key={l.page} className={page===l.page?'active':''} onClick={()=>setPage(l.page)}><l.icon size={18}/><span>{l.label}</span>{l.page==='tasks'&&pending>0&&<b>{pending}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="budget"><ShieldCheck size={17}/><div>Free by design<small>₹0 monthly budget</small></div></div><div className="profile"><span className="profile-avatar">A</span><div>Personal workspace<small>{local?'Windows desktop':'Cloud access'}</small></div><span className="dot"/></div></div>
    </aside>
    <main className="workspace">
      <header className="topbar"><div><span className="eyebrow">YOUR WORKSPACE</span><h2>{links.find(l=>l.page===page)?.label}</h2></div><div className="topbar-actions"><span className="mode-pill"><span className="dot"/>{local?'Desktop agent':'Cloud backend'}</span><button className="stop" onClick={()=>perform('/stop')} title="Cancel tasks, stop voice and disable schedules"><CircleStop size={16}/>Stop all</button></div></header>
      {error&&<div className="alert" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={16}/></button></div>}
      <div className="content">
      {page==='assistant'&&<div className="assistant-grid"><section className="assistant-main">
        <div className="orb-panel"><div className="eyebrow">CONNECTED INTELLIGENCE</div><Orb state={orbState}/><h1>{messages.length?'Here when you need me.':'What shall we do today?'}</h1><p>{orbState==='thinking'?'Working on your request…':orbState==='speaking'?'Speaking · interruption available':orbState==='listening'?'Microphone active · listening locally':'A little less effort. A lot more possibility.'}</p>
          <div className="state-label"><span className="dot"/>{orbState.toUpperCase()}<span className="divider">/</span>{settings?.provider==='auto'?'AUTO MODEL':settings?.provider?.toUpperCase()}</div>
        </div>
        {messages.length===0?<div className="prompt-cards">{['Organize my development tasks','Help me understand my project','Plan my day'].map((p,i)=><button key={p} onClick={()=>setText(p)}><span>{[<Activity size={17}/>,<Cpu size={17}/>,<Sparkles size={17}/>][i]}</span><div>{p}<small>Start a conversation</small></div><ChevronRight size={14}/></button>)}</div>:<div className="chat-log" aria-live="polite">{messages.map((m,i)=><article className={`message ${m.role}`} key={i}><span>{m.role==='assistant'?'U':'YOU'}</span><p>{m.content}</p></article>)}{busy&&<p className="thinking-text">ULTRON is thinking…</p>}<div ref={bottom}/></div>}
        <form className="composer" onSubmit={send}><button type="button" title="New conversation" onClick={()=>{setMessages([]);setConversation(undefined);}}><Plus size={20}/></button><textarea aria-label="Message ULTRON" placeholder="Ask ULTRON anything…" value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}} rows={1}/><button type="button" disabled={!local||!settings?.microphone} className={status?.voice.running?'mic-active':''} aria-label={status?.voice.running?'Stop microphone':'Start microphone'} onClick={()=>perform(status?.voice.running?'/voice/stop':'/voice/start')}><Mic size={20}/></button><button className="send" disabled={busy||!text.trim()} aria-label="Send message"><ArrowUp size={20}/></button></form>
        <div className="composer-caption"><ShieldCheck size={12}/>Sensitive actions require your approval.{local&&<button disabled={!settings?.screen||busy} onClick={async()=>{if(!window.confirm('Capture your screen once? It may contain private data. Sending the next message passes this image to the permitted AI provider.'))return;try{const r=await api.request<{image:string}>('/screen','POST',{approved:true});setScreenImage(r.image);}catch(e){report(e);}}}>Attach screen</button>}{screenImage&&<button onClick={()=>setScreenImage(undefined)}>Remove capture</button>}{busy&&<button onClick={()=>perform('/chat/cancel')}>Cancel request</button>}</div>
        {screenImage&&<small className="muted">Screen attached for the next message only. It will not be archived.</small>}
      </section><aside className="insights">
        <section className="panel"><div className="panel-heading"><h3>System status</h3><span className="eyebrow">LIVE</span></div><StatusLine icon={Monitor} label="Desktop agent" detail={local?'Connected':'Remote · no local control'} good={local}/><StatusLine icon={Cloud} label="Cloud" detail={status?.cloud.signed_in?'Authenticated':status?.cloud.configured?'Configured · sign-in needed':'Not connected'} good={!!status?.cloud.signed_in}/><StatusLine icon={Mic} label="Microphone" detail={status?.voice.running?'Active':settings?.microphone?'Permitted · stopped':'Disabled'} good={!!status?.voice.running}/><StatusLine icon={AudioLines} label="Voice output" detail={settings?.voice_enabled?'Enabled · model required':'Silent'} good={!!settings?.voice_enabled}/>
          {status?.voice.error&&<p className="error">{status.voice.error}</p>}
        </section>
        <section className="panel"><div className="panel-heading"><h3>Model routing</h3><Cpu size={15}/></div><label>Preferred provider<select value={settings?.provider||'auto'} disabled={!local} onChange={e=>saveSettings({provider:e.target.value})}><option value="auto">Automatic · local first</option><option value="ollama">Ollama</option><option value="gemini">Gemini · free tier</option><option value="custom">Custom · verified free</option></select></label><div className="model-card"><span className="model-icon">Q</span><div>{status?.ai.ollama.configured_model||'Local model'}<small>{status?.ai.ollama.models.length?'Models detected':'Local inference unverified'}</small></div></div><small className="muted">Cloud use requires explicit permission and verified free access.</small></section>
        <section className="panel"><div className="panel-heading"><h3>Next steps</h3><Sparkles size={15}/></div>{suggestions.length?suggestions.slice(0,3).map((s,i)=><div className="suggestion" key={s}><span>0{i+1}</span><p>{s}</p></div>):<p className="muted">No configuration suggestions right now.</p>}</section>
        <section className="panel"><h3>Conversations</h3>{histories.slice(0,5).map(h=><button className="history-item" key={h.id} onClick={async()=>{try{setMessages(await api.request(`/conversations/${h.id}`));setConversation(h.id);}catch(e){report(e);}}}>{h.title}</button>)}</section>
      </aside></div>}
      {page==='tasks'&&<><div className="section-intro"><h1>Every action, accounted for.</h1><p>Review the exact arguments before approving. Unconfirmed sensitive actions expire after five minutes.</p></div>
        <section className="panel action-form"><h3>Create a task</h3><label>Action<select value={action} onChange={e=>{setAction(e.target.value);const a=actions.find(a=>a.name===e.target.value);setArgs(JSON.stringify(Object.fromEntries(Object.entries(a?.schema.properties||{}).map(([k,v])=>[k,v.enum?.[0]??(v.type==='integer'?0:'')])),null,2));}}>{actions.map(a=><option key={a.name} value={a.name}>{a.name.replaceAll('_',' ')} · {a.risk}</option>)}</select></label><p className="muted">{actions.find(a=>a.name===action)?.description}</p><label>Arguments (JSON)<textarea value={args} onChange={e=>setArgs(e.target.value)} rows={4}/></label><label>Repeat every N seconds (optional; reminders/read-only tasks)<input type="number" min="60" value={interval} onChange={e=>setIntervalValue(e.target.value)}/></label><button className="primary" onClick={()=>{try{perform(interval?'/schedules':'/tasks','POST',{action,args:JSON.parse(args),...(interval?{interval_seconds:Number(interval)}:{})});}catch(e){report(e);}}}>Create {interval?'schedule':'task'}</button></section>
        {schedules.length>0&&<section className="panel"><h3>Schedules</h3>{schedules.map(s=><div className="list-row" key={s.id}><span>{s.action} · {s.enabled?'enabled':'paused'}</span><button onClick={()=>perform(`/schedules/${s.id}`,'DELETE')}>Remove</button></div>)}</section>}
        <div className="task-list">{tasks.length===0&&<Empty text="No tasks yet. Your approved work will appear here."/>}{tasks.map(t=><section className="panel task" key={t.id}><div className="panel-heading"><h3>{t.action.replaceAll('_',' ')}</h3><span className={`badge ${t.status}`}>{t.status.replaceAll('_',' ')}</span></div><pre>{JSON.stringify(t.args,null,2)}</pre>{t.error&&<p className="error">{t.error}</p>}{t.result!=null&&<details><summary>Execution result</summary><pre>{JSON.stringify(t.result,null,2)}</pre></details>}{t.status==='awaiting_approval'&&<div className="button-row"><button className="primary" onClick={()=>perform(`/tasks/${t.id}/approve`,'POST',{approved:true})}><Check size={15}/>Approve this action</button><button onClick={()=>perform(`/tasks/${t.id}/approve`,'POST',{approved:false})}>Reject</button></div>}{['running','queued'].includes(t.status)&&<button onClick={()=>perform(`/tasks/${t.id}/cancel`)}>Cancel</button>}</section>)}</div></>}
      {page==='memory'&&<><div className="section-intro"><h1>Remember what matters.</h1><p>Memory is explicit and editable. Deletions here affect this connected storage; separate cloud copies must also be removed.</p></div><section className="panel"><label className="search"><Search size={16}/><input aria-label="Search memory" placeholder="Search saved memories" value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Add a memory<textarea value={memoryText} onChange={e=>setMemoryText(e.target.value)} rows={3}/></label><button className="primary" disabled={!memoryText.trim()} onClick={async()=>{if(await perform('/memories','POST',{content:memoryText})){setMemoryText('');setMemories(await api.request('/memories'));}}}>Remember</button></section><div className="memory-grid">{memories.map(m=><section className="panel" key={m.id}><Brain size={18}/><p>{m.content}</p><div className="button-row"><button onClick={async()=>{const content=window.prompt('Correct this memory',m.content);if(content&&await perform(`/memories/${m.id}`,'PATCH',{content}))setMemories(await api.request('/memories'));}}>Edit</button><button onClick={async()=>{if(window.confirm('Delete this saved memory?')&&await perform(`/memories/${m.id}`,'DELETE'))setMemories(await api.request('/memories'));}}>Forget</button></div></section>)}</div>{!memories.length&&<Empty text="Nothing saved yet. Add information you want ULTRON to remember."/>}</>}
      {page==='activity'&&<><div className="section-intro"><h1>A clear record.</h1><p>Significant actions, reminders, failures and permission changes.</p></div><section className="panel">{events.length===0&&<Empty text="No recorded activity yet."/>}{events.map(e=><div className="event" key={e.id}><span className="event-marker"/><div><strong>{e.kind.replaceAll('_',' ')}</strong><p>{e.detail}</p></div><time>{new Date(e.created*1000).toLocaleString()}</time></div>)}</section></>}
      {page==='settings'&&settings&&<SettingsPanel settings={settings} local={local} onSave={saveSettings} perform={perform} api={api} exportData={exportData} report={report}/>}
      </div><footer>ULTRON V1 <span>PRIVATE BY DEFAULT · PERMISSION BEFORE ACTION</span><button onClick={()=>{setConnection(undefined);setApi(undefined);setMessages([]);setStatus(undefined);setSettings(undefined);}}>Disconnect</button></footer>
    </main>
  </div>;
}

function StatusLine({icon:Icon,label,detail,good}:{icon:typeof Brain;label:string;detail:string;good:boolean}){return <div className="status-line"><Icon size={16}/><div>{label}<small>{detail}</small></div><span className={`dot ${good?'':'off'}`}/></div>;}
function Empty({text}:{text:string}){return <div className="empty"><Sparkles size={24}/><p>{text}</p></div>;}

function SettingsPanel({settings:s,local,onSave,perform,api,exportData,report}:{settings:Settings;local:boolean;onSave(v:Partial<Settings>):Promise<void>;perform(path:string,method?:string,body?:unknown):Promise<unknown>;api:API;exportData():Promise<void>;report(e:unknown):void}) {
  const [draft,setDraft]=useState(s); const [secret,setSecret]=useState(''); const [models,setModels]=useState<{name:string}[]>([]);
  const [authEmail,setAuthEmail]=useState('');const [authCode,setAuthCode]=useState('');const [authSent,setAuthSent]=useState(false);
  const [devices,setDevices]=useState<{id:string;name:string;revoked:boolean}[]>([]);
  useEffect(()=>setDraft(s),[s]);
  function field<K extends keyof Settings>(name:K,value:Settings[K]){setDraft(d=>({...d,[name]:value}));}
  async function cloudLogin(){try{const supabase=createClient(s.supabase_url,s.supabase_anon_key,{auth:{persistSession:false,autoRefreshToken:false,detectSessionInUrl:false}});if(!authSent){const {error}=await supabase.auth.signInWithOtp({email:authEmail,options:{shouldCreateUser:false}});if(error)throw error;setAuthSent(true);}else{const {data,error}=await supabase.auth.verifyOtp({email:authEmail,token:authCode,type:'email'});if(error||!data.session)throw error||new Error('Missing session');await perform('/cloud/session','POST',{access_token:data.session.access_token,refresh_token:data.session.refresh_token});setAuthSent(false);setAuthCode('');}}catch(e){report(e);}}
  return <><div className="section-intro"><h1>Your assistant. Your boundaries.</h1><p>Permissions start disabled. Enable only the capabilities you need.</p></div><section className="panel"><h3>Registered devices</h3><button onClick={async()=>{try{setDevices(await api.request(local?'/cloud/devices':'/devices'));}catch(e){report(e);}}}>Load registered devices</button>{devices.map(d=><div className="list-row" key={d.id}><span>{d.name} · {d.revoked?'revoked':'registered'}</span><button disabled={d.revoked} onClick={async()=>{if(window.confirm(`Revoke ${d.name}? Its current device access will stop.`)){await perform((local?'/cloud/devices/':'/devices/')+d.id,'DELETE',{approved:true});setDevices(items=>items.map(item=>item.id===d.id?{...item,revoked:true}:item));}}}>Revoke</button></div>)}</section><div className="settings-grid">
    <section className="panel"><h3>Permissions & privacy</h3>{(['microphone','screen','automation','tool_execution','cloud_ai_allowed','sync_enabled','voice_enabled','learning'] as const).map(k=><label className="toggle-row" key={k}><span>{k.replaceAll('_',' ')}<small>{k==='screen'?'One-time approved captures; no permanent image storage':k==='cloud_ai_allowed'?'Permits sending chat and attached images to configured free providers':k==='sync_enabled'?'Permits approved conversation and memory uploads':k==='automation'?'Allows Windows and isolated browser tools':k==='tool_execution'?'Allows AI to propose actions; sensitive actions still need approval':k==='microphone'?'Local listening starts only when you press the microphone button':k==='learning'?'Learn application and development-command frequencies from approved ULTRON actions only':'Local speech generation'}</small></span><input type="checkbox" disabled={!local} checked={draft[k]} onChange={e=>field(k,e.target.checked)}/></label>)}<p className="muted">Camera capture is not implemented and stays disabled. Learning uses approved action frequencies; it does not passively watch your screen.</p><label>Approved folders (one absolute path per line)<textarea disabled={!local} value={draft.approved_roots.join('\n')} onChange={e=>field('approved_roots',e.target.value.split('\n').filter(Boolean))} rows={3}/></label><label>History retention (days)<input type="number" min="1" max="3650" value={draft.retention_days} onChange={e=>field('retention_days',Number(e.target.value))}/></label></section>
    <section className="panel"><h3>AI providers · ₹0 only</h3><label>Provider<select disabled={!local} value={draft.provider} onChange={e=>field('provider',e.target.value)}>{['auto','ollama','gemini','custom'].map(p=><option key={p}>{p}</option>)}</select></label><label className="toggle-row"><span>Gemini project is Free tier, billing disabled</span><input type="checkbox" disabled={!local} checked={draft.gemini_free_tier_confirmed} onChange={e=>field('gemini_free_tier_confirmed',e.target.checked)}/></label><label>Gemini API key (stored in OS credential manager)<input type="password" disabled={!local} value={secret} onChange={e=>setSecret(e.target.value)} autoComplete="off"/></label><button disabled={!local||!secret} onClick={async()=>{if(await perform('/secrets','POST',{name:'gemini_api_key',value:secret}))setSecret('');}}>Store key securely</button><button disabled={!local} onClick={async()=>{try{setModels(await api.request('/ai/gemini/models'));}catch(e){report(e);}}}>Discover actual Gemini models</button><label>Gemini model<input disabled={!local} list="gemini-models" value={draft.gemini_model} onChange={e=>field('gemini_model',e.target.value)}/><datalist id="gemini-models">{models.map(m=><option key={m.name} value={m.name}/>)}</datalist></label><label>Custom OpenAI-compatible HTTPS endpoint<input disabled={!local} value={draft.custom_endpoint} onChange={e=>field('custom_endpoint',e.target.value)}/></label><label>Local Ollama model<input disabled={!local} value={draft.ollama_model} onChange={e=>field('ollama_model',e.target.value)}/></label><label>Custom model<input disabled={!local} value={draft.custom_model} onChange={e=>field('custom_model',e.target.value)}/></label><label className="toggle-row"><span>Custom endpoint is verified free, with no paid fallback</span><input type="checkbox" disabled={!local} checked={draft.custom_free_confirmed} onChange={e=>field('custom_free_confirmed',e.target.checked)}/></label><small>Save permissions before model discovery. API keys do not prove free quota.</small></section>
    <section className="panel"><h3>Local voice</h3><label>Language<select disabled={!local} value={draft.language} onChange={e=>field('language',e.target.value)}>{['auto','en','hi','hinglish'].map(l=><option key={l}>{l}</option>)}</select></label>{(['whisper_model','voice_model','wake_model'] as const).map(k=><label key={k}>{k.replaceAll('_',' ')} · downloaded local path<input disabled={!local} value={draft[k]} onChange={e=>field(k,e.target.value)}/></label>)}<label>Speech speed<input type="range" min="0.5" max="2" step="0.1" value={draft.speech_rate} onChange={e=>field('speech_rate',Number(e.target.value))}/></label><label>Volume<input type="range" min="0" max="1" step="0.05" value={draft.volume} onChange={e=>field('volume',Number(e.target.value))}/></label><button disabled={!local} onClick={()=>perform('/voice/interrupt')}>Interrupt speech</button><p className="muted">Half-duplex avoids speaker echo. Voice barge-in during playback requires future echo cancellation; the Stop control works immediately.</p></section>
    <section className="panel"><h3>Google integrations</h3><label>Private Desktop OAuth JSON path<input disabled={!local} value={draft.google_client_file} onChange={e=>field('google_client_file',e.target.value)}/></label><div className="scope-options">{['gmail','calendar','drive','people','meet'].map(scope=><label key={scope}><input type="checkbox" disabled={!local} checked={draft.google_scopes.includes(scope)} onChange={e=>field('google_scopes',e.target.checked?[...draft.google_scopes,scope]:draft.google_scopes.filter(v=>v!==scope))}/>{scope}</label>)}</div><div className="button-row"><button disabled={!local} onClick={()=>perform('/google/connect')}>Authorize selected scopes</button><button disabled={!local} onClick={()=>perform('/google/disconnect')}>Disconnect Google</button></div><small>Save first. OAuth testing may require reauthorization. Drive access is limited to files authorized for this app.</small></section>
    <section className="panel"><h3>Cloud & synchronization</h3>{(['supabase_url','supabase_anon_key','cloud_url'] as const).map(k=><label key={k}>{k.replaceAll('_',' ')}<input disabled={!local} value={draft[k]} onChange={e=>field(k,e.target.value)}/></label>)}<label>Registered email<input type="email" value={authEmail} onChange={e=>setAuthEmail(e.target.value)}/></label>{authSent&&<label>Email code<input value={authCode} onChange={e=>setAuthCode(e.target.value)}/></label>}<button disabled={!local||!authEmail} onClick={cloudLogin}>{authSent?'Verify sign-in':'Send cloud sign-in code'}</button><button disabled={!local} onClick={()=>perform('/tasks','POST',{action:'cloud_sync',args:{}})}>Propose cloud sync</button><button disabled={!local} onClick={()=>perform('/cloud/disconnect')}>Sign out of cloud</button><small>Save configuration first. Sync merges records and propagates corrections and deletion tombstones in bounded batches.</small></section>
    <section className="panel"><h3>Data & recovery</h3><button disabled={!local} onClick={()=>{if(window.confirm('Delete learned action frequencies?'))perform('/learning/erase','POST',{approved:true});}}>Delete learning history</button><button onClick={exportData}>Export conversations, memory and activity</button><button className="danger" onClick={()=>{if(window.confirm('Erase this connected database? Cloud copies and recovery snapshots are separate.'))perform('/erase','POST',{approved:true});}}>Erase connected data</button><p className="muted">Existing files are snapshotted before edits. Recovery paths appear in task results. Review generated improvements before installing them.</p></section>
  </div><div className="settings-save"><button className="primary" onClick={()=>onSave(draft)}><Check size={16}/>Save settings</button></div></>;
}
