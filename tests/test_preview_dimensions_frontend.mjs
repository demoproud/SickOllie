import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../js/solo_recipe_catalog.js',import.meta.url),'utf8');
const start=source.indexOf('function catalogPreviewDimensions('), end=source.indexOf('\nasync function ',source.indexOf('function prepareCatalogRunCurrent('));
const writes=[];
const context={CREATIVE_YEARBOOK_OUTPUT_ROOT:'preview-tests',setStudioWidget:(_,name,value)=>writes.push([name,value]),fillCatalogPrompt:()=> 'test photo',resolvePromptYearbookDirectValues:(_,value)=>value,catalogProgress(){},catalogStatus(){},catalogRunLabel:()=> 'test',scheduleCatalogRun(){},stopCatalogRun(){},console};
vm.createContext(context);vm.runInContext(source.slice(start,end),context);
let checks=0;
for(const libraryWide of [false,true])for(const kind of ['prompt','template','outfit','scene','piece']){
 writes.length=0;
 context.catalogRun={items:[{kind}],index:0,libraryWide,directPrompt:false,promptWidth:1440,promptHeight:1920,prompt:{},generation:{},outputs:[],autoQueue:false};
 context.prepareCatalogRunCurrent();
 assert.equal(writes.find(([key])=>key==='custom_width')[1],kind==='scene'?1920:1440);
 assert.equal(writes.find(([key])=>key==='custom_height')[1],kind==='scene'?1440:1920);checks++;
}
for(const [width,height] of [[1600,900],[1024,1024],[400,500]]){
 const dimensions=context.catalogPreviewDimensions({promptWidth:width,promptHeight:height},{kind:'scene'});
 assert.equal(dimensions.width,Math.max(width,height));assert.equal(dimensions.height,Math.min(width,height));checks++;
}
writes.length=0;context.catalogRun={...context.catalogRun,libraryWide:false,directPrompt:true};context.prepareCatalogRunCurrent();assert.ok(!writes.some(([key])=>key==='custom_width'));checks++;
console.log(`Preview dimensions: ${checks} behavior checks passed`);
