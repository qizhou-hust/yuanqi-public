const fs=require('fs');const path=require('path');const crypto=require('crypto');const {pathToFileURL}=require('url');
const {chromium}=require('C:/Users/AAA/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root=process.argv[2]?path.resolve(process.argv[2]):__dirname;const out=process.argv[3]?path.resolve(process.argv[3]):path.join(root,'browser-qa');fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:/Users/AAA/AppData/Local/Google/Chrome/Application/chrome.exe'});const records=[];
try{for(const [name,width,height] of [['desktop',1600,1100],['mobile',430,960]]){
 const page=await browser.newPage({viewport:{width,height},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const local=pathToFileURL(path.join(root,'index.html'));local.search='qa=1';await page.goto(local.href,{waitUntil:'load'});await page.waitForFunction(()=>document.getElementById('qa-result').textContent.length>10);
 const result=JSON.parse(await page.locator('#qa-result').textContent());result.playwright_page_errors=errors;result.browser_version=browser.version();
 if(!result.passed)result.overflow_diagnostic=await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1&&e.clientWidth>0&&!e.closest('.table-wrap')).slice(0,20).map(e=>({tag:e.tagName,id:e.id,cls:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right,text:e.textContent.slice(0,70)})));
 await page.screenshot({path:path.join(out,name+'-overview.png')});
 if(name==='desktop'){
  for(const id of ['math','units','library','workflow','roadmap']){await page.locator('#'+id).screenshot({path:path.join(out,name+'-'+id+'.png')});}
 }else{await page.locator('#library').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,name+'-library.png')});}
 result.local_resources_only=await page.evaluate(()=>performance.getEntriesByType('resource').every(r=>r.name.startsWith('file:')||r.name.startsWith('data:')));
 records.push({name,...result});await page.close();
}
const content=fs.readFileSync(path.join(root,'index.html'),'utf8');const missingLinks=[...content.matchAll(/href="([^"#]+)"/g)].map(m=>m[1]).filter(h=>!h.startsWith('http:')&&!h.startsWith('https:')&&!h.startsWith('data:')).filter(h=>!fs.existsSync(path.resolve(root,h.split('#')[0])));
const summary={schema:'gearbase.report-browser-qa/1',headless:true,mouse_used:false,html_sha256:crypto.createHash('sha256').update(Buffer.from(content,'utf8')).digest('hex'),producer_sha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),missing_local_links:missingLinks,passed:missingLinks.length===0&&records.every(r=>r.passed&&r.playwright_page_errors.length===0&&r.local_resources_only),records};
fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(summary,null,2)+'\n');console.log(JSON.stringify(summary,null,2));if(!summary.passed)process.exitCode=1;
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
