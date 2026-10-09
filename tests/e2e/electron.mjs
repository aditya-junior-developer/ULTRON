import { _electron as electron } from 'playwright';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import assert from 'node:assert/strict';

const root=resolve('.');const data=await mkdtemp(join(tmpdir(),'ultron-desktop-test-'));
let desktop;let child;
try{
 const flags=process.platform==='linux'?['--no-sandbox','--ozone-platform=headless','--disable-gpu']:[];
 desktop=await electron.launch({args:[join(root,'apps/desktop'),...flags],env:{...process.env,ULTRON_PYTHON:join(root,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),ULTRON_DESKTOP_DATA_DIR:data,...(process.platform==='linux'?{XDG_CACHE_HOME:data,XDG_CONFIG_HOME:data}:{})},timeout:45000});
 child=desktop.process();child.on('exit',(code,signal)=>console.log('Desktop test process exit:',code,signal));
 const page=await desktop.firstWindow({timeout:45000});await page.getByRole('heading',{name:'What shall we do today?'}).waitFor({timeout:30000});
 assert.equal(await page.evaluate(()=>typeof window.require),'undefined');
 assert.equal(await page.evaluate(async()=>{const s=await window.ultron.session();const r=await fetch(s.base+'/settings',{headers:{Authorization:'Bearer '+s.token}});return r.status;}),200);
 await page.getByRole('button',{name:'Memory',exact:true}).click();await page.getByLabel('Add a memory').fill('Desktop IPC and local storage verified');
 await page.getByRole('button',{name:'Remember',exact:true}).click();await page.getByText('Desktop IPC and local storage verified',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 await page.getByRole('button',{name:'Save settings',exact:true}).click();
 await page.waitForTimeout(300);
 assert.equal(await page.getByRole('alert').count(),0,'Settings save failed');
 await desktop.close();desktop=undefined;
 console.log('Electron workflow PASSED: actual desktop window, isolated renderer, authenticated preload session, spawned Python agent, saved memory, settings save, shutdown');
}finally{
 if(desktop&&child&&child.exitCode===null&&child.signalCode===null){
  await Promise.race([desktop.close().catch(()=>{}),new Promise(resolve=>setTimeout(resolve,4000))]);
  if(child.exitCode===null&&child.signalCode===null)child.kill();
 }
 await rm(data,{recursive:true,force:true,maxRetries:10,retryDelay:200});
}
