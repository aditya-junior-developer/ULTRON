import { app, BrowserWindow, ipcMain, Notification, shell } from 'electron';
import { spawn, type ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { createServer } from 'node:net';
import { request as httpRequest } from 'node:http';

let agent: ChildProcess | undefined;
let session: {base:string;token:string;mode:'local'} | undefined;
let mainWindow: BrowserWindow | undefined;
if(process.env.ULTRON_DESKTOP_DATA_DIR){mkdirSync(process.env.ULTRON_DESKTOP_DATA_DIR,{recursive:true});app.setPath('userData',process.env.ULTRON_DESKTOP_DATA_DIR);}
const locked=app.requestSingleInstanceLock();
if(!locked) app.quit();
app.on('second-instance',()=>{mainWindow?.show();mainWindow?.focus();});

async function freePort(): Promise<number> {
  return new Promise((resolve,reject)=>{const s=createServer();s.listen(0,'127.0.0.1',()=>{const address=s.address();if(!address||typeof address==='string')return reject(new Error('Port allocation failed'));const port=address.port;s.close(()=>resolve(port));});s.on('error',reject);});
}
async function localStatus(port:number,path:string,token?:string):Promise<number>{
  return new Promise((resolve,reject)=>{const request=httpRequest({host:'127.0.0.1',port,path,method:'GET',headers:token?{Authorization:`Bearer ${token}`}:{},timeout:1000},response=>{response.resume();resolve(response.statusCode||0);});request.on('error',reject);request.on('timeout',()=>request.destroy(new Error('Readiness timeout')));request.end();});
}
async function startAgent() {
  const port=await freePort();const token=randomBytes(32).toString('base64url');
  const base=`http://127.0.0.1:${port}`;
  const executable=app.isPackaged?join(process.resourcesPath,'agent','ultron-agent','ultron-agent.exe'):(process.env.ULTRON_PYTHON||'python');
  if(app.isPackaged&&!existsSync(executable))throw new Error('Bundled desktop agent is missing. Rebuild the Windows package.');
  agent=spawn(executable,app.isPackaged?['--port',String(port)]:['-m','ultron','--port',String(port)],{
    env:{...process.env,ULTRON_SESSION_TOKEN:token,ULTRON_DATA_DIR:join(app.getPath('userData'),'data'),ULTRON_PARENT_PID:String(process.pid)},
    stdio:['ignore','pipe','pipe'],windowsHide:true,
  });
  let exited=false;let failure='';
  agent.on('error',()=>{exited=true;failure='Agent could not start. Set ULTRON_PYTHON to the installed virtual environment Python.';});
  agent.on('exit',code=>{exited=true;failure=`Local agent exited (${code}). Verify Python dependencies.`;if(session)mainWindow?.webContents.send('agent-exit');});
  // Session stdout intentionally discarded: it contains the ephemeral authentication token.
  agent.stdout?.resume();agent.stderr?.on('data',()=>{});
  for(let n=0;n<150;n++){
    if(exited)throw new Error(failure);
    try{if(await localStatus(port,'/health')===200&&await localStatus(port,'/settings',token)===200){session={base,token,mode:'local'};return;}}catch{}
    await new Promise(r=>setTimeout(r,200));
  }
  agent.kill();throw new Error('Agent did not become ready within 30 seconds.');
}

app.whenReady().then(async()=>{
  if(!locked)return;
  let failure='';const readiness=startAgent().catch(e=>{failure=(e as Error).message;});
  mainWindow=new BrowserWindow({width:1380,height:900,minWidth:430,minHeight:650,backgroundColor:'#080c14',title:'ULTRON',
    webPreferences:{preload:join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
  mainWindow.removeMenu();
  mainWindow.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  mainWindow.webContents.on('will-navigate',e=>e.preventDefault());
  mainWindow.webContents.session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  function trusted(event:Electron.IpcMainInvokeEvent){if(event.sender!==mainWindow?.webContents)throw new Error('Untrusted IPC sender');}
  ipcMain.handle('session',async event=>{trusted(event);await readiness;if(!session)throw new Error(failure||'Agent unavailable');return session;});
  ipcMain.handle('external',(event,url:string)=>{trusted(event);const parsed=new URL(url);if(parsed.protocol!=='https:'||parsed.username||parsed.password)throw new Error('Only HTTPS links are supported');return shell.openExternal(url);});
  ipcMain.handle('notify',(event,title:string,body:string)=>{trusted(event);if(typeof title!=='string'||typeof body!=='string')throw new Error('Invalid notification');if(Notification.isSupported())new Notification({title:title.slice(0,100),body:body.slice(0,300)}).show();});
  if(app.isPackaged)await mainWindow.loadFile(join(process.resourcesPath,'web','index.html'));
  else await mainWindow.loadFile(resolve(app.getAppPath(),'../web/dist/index.html'));
});
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{if(session)fetch(session.base+'/stop',{method:'POST',headers:{Authorization:`Bearer ${session.token}`}}).catch(()=>{});agent?.kill();});
process.on('exit',()=>agent?.kill());
