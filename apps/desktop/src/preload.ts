import { contextBridge, ipcRenderer } from 'electron';
contextBridge.exposeInMainWorld('ultron',Object.freeze({
  session:()=>ipcRenderer.invoke('session'),
  openExternal:(url:string)=>ipcRenderer.invoke('external',url),
  notify:(title:string,body:string)=>ipcRenderer.invoke('notify',title,body),
}));
