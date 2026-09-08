// Execute the shipped inspector in a DOM/transport harness, not a browser.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../js/solo_recipe_catalog.js',import.meta.url),'utf8');
class Element {
 constructor(tag,doc){Object.assign(this,{tagName:tag.toUpperCase(),doc,children:[],style:{},dataset:{},attrs:{},events:{},disabled:false,_text:''});}
 get isConnected(){return this===this.doc.body || !!this.parent?.isConnected;}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 set textContent(v){this.replaceChildren();this._text=String(v);}
 append(...nodes){for(const n of nodes){n.remove();n.parent=this;this.children.push(n);}}
 replaceChildren(...nodes){for(const n of [...this.children])n.remove();this._text='';this.append(...nodes);}
 remove(){if(this.contains(this.doc.activeElement))this.doc.activeElement=this.doc.body;if(this.parent){this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null;}}
 closest(q){return q==='[data-library-inspector]' && this.dataset.libraryInspector ? this : this.parent?.closest(q);}
 contains(n){return n===this || this.children.some(c=>c.contains(n));}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,fn){this.events[k]=fn;}
 querySelectorAll(q){return this.children.flatMap(c=>[...(q==='button'&&c.tagName==='BUTTON'?[c]:[]),...c.querySelectorAll(q)]);}
 querySelector(q){return q===':scope > strong'?this.children.find(c=>c.tagName==='STRONG'):this.querySelectorAll(q)[0];}
 focus(){this.doc.activeElement=this;}
 click(){if(this.disabled)return;this.focus();return this.onclick?.({currentTarget:this,target:this,stopPropagation(){},preventDefault(){}});}
}
function harness(){
 const doc={createElement(tag){return new Element(tag,this);}};doc.body=new Element('body',doc);doc.activeElement=doc.body;
 const state={calls:[],alerts:[],confirm:true,fail:false,refreshFail:false,copy:'',rows:[]};
 const context={document:doc,queueMicrotask,installStudioInteractions(){},recoverTextInputFocus(){},window:{setTimeout(){}},URLSearchParams,Map,Set,Number,String,Array,Math,Promise,requestAnimationFrame:fn=>queueMicrotask(fn),
 collectionModal(title,width){const overlay=doc.createElement('div'),card=doc.createElement('section'),head=doc.createElement('strong');head.textContent=title;card.style.width=width;card.append(head);overlay.append(card);doc.body.append(overlay);return{overlay,card,close:()=>overlay.remove()};},
 action(label){const b=doc.createElement('button');b.textContent=label;return b;},
 request:async(url,opts)=>{state.calls.push({url,opts});if(state.fail)throw Error('transport failed');return url.includes('?')?{prompts:state.rows}:{changed:1,deleted:1};},
 comfyConfirm:async()=>state.confirm,alert:s=>state.alerts.push(s),catalogStatus(){},
 loadPromptPage:async()=>{if(state.refreshFail)throw Error('refresh failed');},load:async()=>{if(state.refreshFail)throw Error('refresh failed');},
 promptAssetRecipe:()=>null,promptAssetSourceText:a=>a.source_value||a.value,promptAssetResolvedText:a=>a.resolved_value||'',promptAssetResolvedSeed:a=>a.seed,
 componentCollectionDisplayName:(_,row)=>row.name,creativeLibraryPreviewUrl:r=>r,copyLibraryValue:async s=>{state.copy=s;return true;},
 selectedPromptIds:new Set(),selectedComponentIds:new Set(),selectedWardrobeIds:new Set(),recipes:[],activeCollection:'',activePromptKind:()=> 'prompt',currentPromptFolderLabel:()=> 'Test Home',promptPageParams:()=>new URLSearchParams('kind=prompt&rating=unrated')};
 for(const name of ['showPromptApply','queuePromptAsset','editPromptAssetCard','openPromptCatalogRunDialog','loadDerivedValue','showComponentCollectionEditor','showLibraryAssetCollectionEditor','openCatalogRunDialogForItem','showDiff','addBuilderItem','loadWardrobeValue','showWardrobeItemEditor','deletePromptAssetPreview'])context[name]=()=>{};
 vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('function collectionModal('),source.indexOf('\nasync function creativeStructureOrder(')),context);
 vm.runInContext(source.slice(source.indexOf('function promptInspectorPlatter('),source.indexOf('\nfunction promptFilterSelect(')),context);
 vm.runInContext(source.slice(source.indexOf('async function deleteComponentThumbnail('),source.indexOf('\nasync function deleteSelectedComponentThumbnails(')),context);
 return{context,doc,state,open(kind,rows,index=0){context.openLibraryInspector({kind,item:rows[index],index,total:rows.length,fetchAt:async n=>rows[n],scopeLabel:'Test scope'});return doc.body.children.at(-1);}};
}
const settle=async()=>{for(let i=0;i<15;i++)await new Promise(r=>setImmediate(r));};
const button=(o,text)=>o.querySelectorAll('button').find(b=>b.textContent===text);
const key=async(o,key,target=o,extra={})=>{o.focus();o.events.keydown({key,target,preventDefault(){},stopPropagation(){},...extra});await settle();};
const item=id=>({prompt_id:id,component_id:id,wardrobe_id:id,name:id,value:'photo '+id,preview_ref:id+'.png',rating:0,seed:0});
let checks=0;
for(const kind of ['prompt','template','outfit','scene','piece']){
 const h=harness(),rows=[item('A'),item('B'),item('C')],o=h.open(kind,rows);await settle();
 assert.equal(o.children[0].style.height,'94vh');assert.equal(o.children[0].style.width,'min(2800px,96vw)');checks++;
 await key(o,'5');assert.equal(rows[0].rating,5);assert.equal(h.state.calls[0].url,`/${['prompt','template'].includes(kind)?'prompt-assets':kind==='piece'?'wardrobe-items':'derived-values'}/A/rating`);checks++;
 assert.equal(h.doc.activeElement,o);checks++;
 await key(o,'0');assert.equal(rows[0].rating,0);checks++;
 await button(o,'→').click();await settle();assert.ok(o.textContent.includes('2 of 3'));checks++;
 h.state.confirm=false;await button(o,'DELETE ASSET').click();await settle();assert.ok(o.textContent.includes('2 of 3'));checks++;
 h.state.confirm=true;h.state.fail=true;await button(o,'DELETE ASSET').click();await settle();assert.ok(o.textContent.includes('2 of 3'));checks++;
 h.state.fail=false;await button(o,'DELETE ASSET').click();await settle();assert.ok(o.textContent.includes('2 of 2'));assert.ok(o.textContent.includes('photo C'));checks++;
 await button(o,'←').click();await settle();assert.ok(o.textContent.includes('photo A'));checks++;
 await button(o,'DELETE ASSET').click();await settle();assert.ok(o.textContent.includes('photo C'));assert.ok(o.textContent.includes('1 of 1'));checks++;
 await button(o,'DELETE ASSET').click();await settle();assert.ok(o.textContent.includes('review scope is empty'));checks++;
}
{
 const h=harness(),rows=[item('A'),item('B')],o=h.open('prompt',rows);await settle();
 await key(o,'5',h.doc.createElement('textarea'));assert.equal(h.state.calls.length,0);await key(o,'5',o,{ctrlKey:true});assert.equal(h.state.calls.length,0);checks+=2;
 await button(o,'COPY ALL').click();assert.ok(h.state.copy.includes('Seed:\n0'));assert.ok(!h.state.copy.includes('Outfit A'));checks++;
 h.state.refreshFail=true;await key(o,'4');assert.equal(rows[0].rating,4);assert.equal(h.state.alerts.length,0);checks++;
 await button(o,'DELETE ASSET').click();await settle();assert.ok(o.textContent.includes('photo B'));checks++;
}
{
 const h=harness(),rows=[item('A')],o=h.open('scene',rows);await settle();
 h.state.confirm=false;await button(o,'DELETE THUMBNAIL').click();await settle();assert.equal(rows[0].preview_ref,'A.png');checks++;
 h.state.confirm=true;h.state.fail=true;await button(o,'DELETE THUMBNAIL').click();await settle();assert.equal(rows[0].preview_ref,'A.png');checks++;
 h.state.fail=false;await button(o,'DELETE THUMBNAIL').click();await settle();assert.equal(rows[0].preview_ref,'');checks++;
}
{
 const h=harness();h.state.rows=[item('A'),item('B'),item('C')];await h.context.openPromptThumbnail(h.state.rows[0]);await settle();const o=h.doc.body.children.at(-1);
 assert.ok(h.state.calls[0].url.includes('include_all=1'));assert.ok(h.state.calls[0].url.includes('rating=unrated'));checks++;
 h.state.rows=[item('C'),item('A'),item('B')];await key(o,'5');await button(o,'→').click();await settle();assert.ok(o.textContent.includes('photo B'));checks++;
}
{
 const h=harness(),o=h.open('prompt',[item('A')]);await settle();o.focus();
 const child=h.context.collectionModal('EDIT');child.overlay.focus();child.close();await settle();assert.equal(h.doc.activeElement,o);checks++;
}
{
 const h=harness(),rows=[item('A'),item('B')],o=h.open('prompt',rows);await settle();const queued=[];
 h.context.queuePromptAsset=(asset,button,position)=>queued.push([asset.prompt_id,button.dataset.queueLabel,position]);
 await button(o,'QUEUE').click();await button(o,'QUEUE NEXT').click();assert.deepEqual(queued,[['A','QUEUE',0],['A','QUEUE NEXT',-1]]);checks++;
 await button(o,'→').click();await settle();await button(o,'QUEUE').click();assert.equal(queued.at(-1)[0],'B');checks++;
}
console.log(`Library Inspector frontend: ${checks} behavior checks passed`);
