import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../js/solo_recipe_catalog.js',import.meta.url),'utf8');
class E {
 constructor(tag){Object.assign(this,{tagName:tag,children:[],style:{},dataset:{},_text:'',_value:undefined,disabled:false});}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');} set textContent(v){this.children=[];this._text=String(v);}
 get value(){return this._value ?? (this.tagName==='select'?(this.children.find(c=>c.selected)||this.children[0])?.value||'':'');} set value(v){this._value=v;}
 get options(){return this.children;}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 replaceChildren(...nodes){this.children=[];this._value=undefined;this.append(...nodes);}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this);}
 addEventListener(){} focus(){}
 querySelectorAll(q){return this.children.flatMap(c=>[...(q===c.tagName?[c]:[]),...c.querySelectorAll(q)]);}
 click(){if(!this.disabled)return this.onclick?.();}
}
function harness(){
 const document={createElement:t=>new E(t),body:new E('body')},state={calls:[],alerts:[]};
 const c={document,Map,Set,Number,String,Array,Math,Promise,encodeURIComponent,requestAnimationFrame:fn=>fn(),
 activeView:'scenes',activeCollection:'child',componentPage:{scene:0,outfit:0},activeLibraryCollection:{scene:'',outfit:''},selectedComponentIds:new Set(['selected-a','selected-b']),
 componentCollections:{scene:[{collection_id:'parent',name:'Backdrops',parent_id:''},{collection_id:'child',name:'Flat',parent_id:'parent'}],outfit:[]},libraryCollections:{scene:[{collection_id:'pack-1',name:'Favorites'},{collection_id:'pack-2',name:'Another'}],outfit:[]},
 action(text){const b=new E('button');b.textContent=text;return b;},makeSelect(options,value){const s=new E('select');for(const [v,t] of options){const o=new E('option');o.value=v;o.textContent=t;s.append(o);}s.value=value;return s;},
 collectionModal(title){const overlay=new E('div'),card=new E('section'),h=new E('strong');h.textContent=title;card.append(h);overlay.append(card);document.body.append(overlay);return{card,overlay,close:()=>overlay.remove()};},
 libraryCollectionAccent:()=> '#63e6a4',libraryCollectionLabel:k=>k==='scene'?'Scenes':'Looks',refreshLibraryCollectionKind:async()=>{},load:async()=>{},catalogStatus(){},alert:s=>state.alerts.push(s),
 request:async(url,opts)=>{const body=JSON.parse(opts.body);state.calls.push({url,body});if(url==='/library-collections'){c.libraryCollections.scene.push({collection_id:'created',name:body.name});return{collection:{collection_id:'created'}};}return{values:2,folder_id:'child',assets:2};}};
 vm.createContext(c);
 for(const [start,end] of [
 ['async function showBulkComponentCollectionEditor(kind)', '\nasync function showWardrobeBulkCollectionEditor'],
 ['function showComponentLogImporter(kind', '\nasync function showLogImporter'],
 ['async function showLogImporter(', '\nasync function showImportHistory'],
 ['function showBulkCollectionEditor()', '\nfunction showBulkComponentHomeEditor'],
 ['function showAssetBuilder()', '\nfunction showOutfitLogImporter'],
 ]) vm.runInContext(source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start))),c);
 c.currentComponentKind=()=>c.activeView==='scenes'?'scene':'outfit';
 return{c,state,document};
}
const btn=(root,label)=>root.querySelectorAll('button').find(e=>e.textContent===label);
{
 const h=harness();await h.c.showBulkCollectionEditor();const modal=h.document.body.children.at(-1);
 assert.ok(modal.textContent.includes('COLLECT 2 SCENES'));assert.ok(!modal.textContent.includes('MOVE'));
 modal.querySelectorAll('input').filter(e=>e.type==='checkbox')[0].checked=true;
 modal.querySelectorAll('input').find(e=>e.placeholder==='New Scenes Collection').value='New set';await btn(modal,'+ CREATE').click();
 assert.equal(modal.querySelectorAll('input').filter(e=>e.type==='checkbox'&&e.checked).length,2);
 await btn(modal,'ADD TO COLLECTIONS').click();const call=h.state.calls.at(-1);assert.equal(call.url,'/library-collections/bulk');assert.deepEqual(call.body.asset_ids,['selected-a','selected-b']);assert.deepEqual(call.body.collection_ids,['pack-1','created']);assert.equal(call.body.kind,'scene');
}
for(const kind of ['scene','outfit']){
 const h=harness();h.c.activeView=kind==='scene'?'scenes':'outfits';await h.c.showLogImporter(kind);const modal=h.document.body.children.at(-1);assert.ok(modal.textContent.includes(`IMPORT ${kind.toUpperCase()} LOG`));
 const textarea=modal.querySelectorAll('textarea')[0],selects=modal.querySelectorAll('select');
 if(kind==='outfit'){selects[0].value='__new__';selects[0].onchange();const newCat=modal.querySelectorAll('input').find(e=>e.placeholder==='New category name…');newCat.value='Custom';newCat.oninput();}
 const picker=modal.querySelectorAll('input').find(e=>e.type==='file');picker.files=[{name:'Local.txt',text:async()=> 'one\ntwo'}];await picker.onchange();assert.equal(textarea.value,'one\ntwo');
 const submit=btn(modal,`IMPORT ${kind.toUpperCase()} LOG`);assert.equal(submit.disabled,false);await submit.click();
 const call=h.state.calls.at(-1);assert.equal(call.url,'/component-assets/import');assert.equal(call.body.kind,kind);assert.equal(call.body.parent,kind==='scene'?'Backdrops':'Custom');assert.equal(call.body.subcategory,kind==='scene'?'Flat':'');assert.equal(call.body.text,'one\ntwo');assert.equal(call.body.log_name,'Local');assert.equal(h.state.alerts.length,0);
}
{
 const h=harness();h.c.showAssetBuilder();const modal=h.document.body.children.at(-1);assert.ok(modal.textContent.includes('BUILD SCENE ASSETS'));const textarea=modal.querySelectorAll('textarea')[0];textarea.value='flat lavender';textarea.oninput();assert.equal(btn(modal,'BUILD SCENE ASSETS').disabled,false);await btn(modal,'BUILD SCENE ASSETS').click();assert.equal(h.state.calls.at(-1).body.parent,'Backdrops');
}
console.log('Component organization frontend: collection routing, selected IDs, create-and-add, both file importers, and manual builder passed');
