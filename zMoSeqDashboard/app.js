/* MoSeq Dashboard v0.1 — no external runtime dependencies. */
(() => {
  'use strict';
  const C = window.MoSeqCore;
  const $ = id => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const colors = ['#587582','#17998e','#e4a34b','#8c78b0','#d17589','#548db7','#8e9a40','#b5774c'];
  const state = {data:null, selected:new Set(), sources:[], sourceId:'', exportId:null, loading:0};
  const noteMemory = new Map();
  const viewMemory=new Map();
  const savedViews=new Map(),viewNames=new Map();
  let savingSession=false,dashboardClosed=false;
  const viewKey=data=>C.fingerprint(data.text)+data.name;
  let workspace='treatments',combinations=[],heatSvg=null,heatRows=[];
  const viewData=()=>workspace==='combined'?C.combine(state.data,combinations):state.data;
  const plotIds=()=>workspace==='combined'?combinations.map(c=>c.id):ordered();
  let activeNotes = null;
  const note = (kind,id) => activeNotes?.notes[kind][id] || {label:'',comment:''};
  const groupLabel = g => note('groups',g.id).label || g.name;
  const syllableLabel = id => combinations.find(c=>c.id===id)?.label || note('syllables',id).label || 'Syllable '+id;
  let toastTimer, dragDepth = 0;
  const factor = () => $('units').value === 'percent' ? 100 : 1;
  const unitLabel = () => factor() === 100 ? 'Syllable Usage %' : 'Syllable Usage (fraction)';
  const format = n => n == null ? '—' : Number(n.toPrecision(5)).toString();
  const prettyName = name => name.replace(/^MOS-VIZ1_usage_bysubject_?/i,'').replace(/\.(txt|tsv|csv)$/i,'').replace(/_/g,' ') || name;
  const ordered = () => state.data ? state.data.ids.filter(id => state.selected.has(id)) : [];
  const color = i => colors[i] || `hsl(${(i*137.508)%360} 45% 45%)`;
  function element(tag, text, className) {
    const node = document.createElement(tag); if (text != null) node.textContent=text; if(className) node.className=className; return node;
  }
  function svgNode(tag, attrs={}, text) {
    const node = document.createElementNS(NS,tag);
    for(const [k,v] of Object.entries(attrs)) node.setAttribute(k,String(v));
    if(text!=null)node.textContent=text; return node;
  }
  function toast(message) {clearTimeout(toastTimer);(document.querySelector('dialog[open]')||document.body).append($('toast'));$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,4500);}
  function error(message) {$('error').textContent=message;$('error').hidden=!message;}
  function download(text,name,type='text/tab-separated-values;charset=utf-8') {
    const url=URL.createObjectURL(new Blob([text],{type})); const a=element('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
  }
  function filename(suffix) {return (state.data?.name||'moseq').replace(/\.[^.]+$/,'').replace(/[^a-z0-9._-]/gi,'_')+'_'+suffix;}
  function sourceMenu() {
    const select=$('dataset');select.replaceChildren();
    select.append(new Option(state.sources.length?'Select a dataset…':'No data files found',''));
    for(const s of state.sources) select.append(new Option(s.name,s.id));
    select.value=state.sourceId;
  }
  function addSources(sources) {for(const s of sources){const i=state.sources.findIndex(x=>x.id===s.id);if(i>=0)state.sources[i]=s;else state.sources.push(s);}sourceMenu();}
  async function loadSource(id, settings, importedNotes) {
    if(state.data)viewMemory.set(viewKey(state.data),JSON.parse(JSON.stringify(captureSettings())));
    const ticket=++state.loading;const src=state.sources.find(s=>s.id===id);
    state.sourceId=id;state.data=null;activeNotes=null;state.selected.clear();error('');render();
    if(!src)return;
    $('source-note').textContent='Reading '+src.name+'…';
    try {
      if(src.file?.size>20*1024*1024)throw new Error('Choose a text file smaller than 20 MB.');
      const text = src.text != null ? src.text : src.file ? await src.file.text() : await fetchText('/api/data?name='+encodeURIComponent(src.name));
      if(ticket!==state.loading)return;
      state.data=C.parse(text,src.name);
      let restored=false;
      const remembered=viewMemory.get(C.fingerprint(text)+src.name);
      if(!settings&&remembered)settings=remembered;
      if(src.kind==='live'&&!settings){
        try{
          const response=await fetch('/api/session?name='+encodeURIComponent(src.name),{cache:'no-store'});
          if(response.ok){const saved=await response.json();
            if(ticket!==state.loading)return;
            if(saved.app!=='MoSeq Dashboard'||saved.version!=='0.1'||saved.dataset?.name!==src.name||C.fingerprint(saved.dataset.text)!==C.fingerprint(text))throw new Error('The saved session belongs to an older or different raw file. Open it manually to inspect that snapshot.');
            if(saved.notes)C.validateNotes(saved.notes,state.data);
            settings=saved.settings;importedNotes=saved.notes;restored=true;
          }else if(response.status!==404)throw new Error('Saved session could not be read.');
        }catch(err){error('Session was not restored: '+err.message);}
      }
      if(ticket!==state.loading)return;
      applySettings(settings||{selected:C.top(state.data),units:'percent'});
      const blank=C.blankNotes(state.data),noteKey=JSON.stringify(blank.dataset);
      if(importedNotes&&(!noteMemory.get(noteKey)?.dirty||confirm('Replace unsaved notes for this dataset with the saved session notes?')))noteMemory.set(noteKey,{notes:C.validateNotes(importedNotes,state.data),dirty:false});
      if(!noteMemory.has(noteKey))noteMemory.set(noteKey,{notes:blank,dirty:false});
      activeNotes=noteMemory.get(noteKey);
      state.selected=new Set(settings ? settings.selected.filter(id=>state.data.ids.includes(String(id))).map(String) : C.top(state.data));
      const key=viewKey(state.data);viewNames.set(key,state.data.name);
      if(!savedViews.has(key)||src.kind==='session'||restored)savedViews.set(key,JSON.stringify(captureSettings()));
      $('syllable-search').value='';
      $('source-note').textContent=src.kind==='live'?'Live local folder · refresh to read edits':src.kind==='snapshot'?'Included snapshot · select your folder to read edits':src.kind==='session'?'Restored session · contains its own dataset':'Selected local file · read in memory';
      render();
      if(restored)toast('Matching session restored from data_MoSeq_raw.');
    } catch(e) {if(ticket!==state.loading)return;state.data=null;activeNotes=null;error(`${src.name}: ${e.message}`);$('source-note').textContent='File could not be loaded. Choose another source.';render();}
  }
  async function fetchText(url) {const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error('Cannot read local source: '+r.status);return r.text();}
  async function scanLocal(keep=true) {
    const previous=state.sources.find(s=>s.id===state.sourceId)?.name;
    try {
      const result=JSON.parse(await fetchText('/api/files'));
      if(!Array.isArray(result.files))throw new Error('Invalid local catalog.');
      state.sources=state.sources.filter(s=>s.kind!=='live'&&s.kind!=='snapshot');
      addSources(result.files.map(name=>({id:'live:'+name,name,kind:'live'})));
      const chosen=state.sources.find(s=>s.kind==='live'&&s.name===previous)||state.sources.find(s=>s.kind==='live');
      $('refresh-data').hidden=false;
      if(chosen)await loadSource(chosen.id,keep&&chosen.name===previous&&state.data?settings():undefined);
      else {state.sourceId='';await loadSource('');$('source-note').textContent='No TXT, TSV or CSV files in data_MoSeq_raw. Add files, then refresh.';}
      sourceMenu();
    }catch(e){error('Local folder refresh unavailable. Keep the Python launcher running, or use Open a data file. '+e.message);}
  }
  function captureSettings(){return {selected:ordered(),units:$('units').value,scale:$('scale').value,columns:$('columns').value,points:$('points').checked,workspace,combinations,heat:{level:$('heat-level').value,palette:$('heat-palette').value,low:$('heat-low').value,mid:$('heat-mid').value,high:$('heat-high').value,cellWidth:$('heat-width').value,cellHeight:$('heat-height').value}};}
  const settings=captureSettings;
  function applySettings(s){
    if(!s||!Array.isArray(s.selected))throw new Error('Invalid session settings.');
    $('units').value=s.units==='raw'?'raw':'percent';$('scale').value=s.scale==='individual'?'individual':'shared';$('columns').value=['2','3','4'].includes(s.columns)?s.columns:'3';$('points').checked=s.points!==false;
    combinations=Array.isArray(s.combinations)?s.combinations.map(c=>{if(typeof c.id!=='string'||!c.id.startsWith('combined-')||typeof c.label!=='string'||!c.label.trim()||c.label.length>100)throw new Error('Invalid saved combination.');return {id:c.id,label:c.label,ids:c.ids};}):[];
    C.combine(state.data,combinations);workspace=['treatments','combined','heatmaps'].includes(s.workspace)?s.workspace:'treatments';
    $('heat-level').value=s.heat?.level==='animals'?'animals':'groups';$('heat-palette').value=[...$('heat-palette').options].some(o=>o.value===s.heat?.palette)?s.heat.palette:'teal';
    $('heat-width').value=Math.max(8,Math.min(120,Number(s.heat?.cellWidth)||36));$('heat-height').value=Math.max(12,Math.min(90,Number(s.heat?.cellHeight)||32));
    for(const [key,defaultValue] of [['low',0],['mid',factor()===100?5:.05],['high',factor()===100?10:.1]])$('heat-'+key).value=Number.isFinite(Number(s.heat?.[key]))?s.heat[key]:defaultValue;
  }
  function render() {
    const d=state.data;
    $('dataset-name').textContent=d?prettyName(d.name):'No dataset loaded';
    $('dataset-file').textContent=d?d.name+' · '+d.records.length.toLocaleString()+' observation rows':'Select a valid usage-by-subject file to begin.';
    $('animal-count').textContent=d?d.subjects.size:'—';$('group-count').textContent=d?d.groups.length:'—';$('syllable-count').textContent=d?d.ids.length:'—';
    $('save-session').disabled=!d;$('export-summary').disabled=!d||!state.selected.size;
    $('notes-button').disabled=!d;updateNotesStatus();
    $('warnings').textContent=d?d.warnings.join(' '):'';$('warnings').hidden=!d?.warnings.length;
    $('legend').replaceChildren();
    if(d)d.groups.forEach((g,i)=>{const item=element('span'),swatch=element('i',null,'swatch');swatch.style.background=color(i);const n=note('groups',g.id);item.append(swatch,document.createTextNode(groupLabel(g)));item.title=[`Original: ${g.name} (group ${g.id})`,n.comment].filter(Boolean).join('\n');$('legend').append(item);});
    renderSyllables();renderCharts();
  }
  function renderSyllables(){
    const list=$('syllable-list');list.replaceChildren();$('selection-count').textContent=state.selected.size+' selected';
    if(!state.data){list.append(element('p','Load a dataset to choose syllables.','side-hint'));return;}
    const filter=$('syllable-search').value.trim().toLowerCase();
    const ids=state.data.ids.filter(id=>id.includes(filter));
    if(!ids.length)list.append(element('p','No matching syllable IDs.','side-hint'));
    for(const id of ids){
      const label=element('label',null,'syllable-option'),check=element('input');check.type='checkbox';check.checked=state.selected.has(id);check.dataset.syllable=id;
      check.addEventListener('change',()=>{check.checked?state.selected.add(id):state.selected.delete(id);$('selection-count').textContent=state.selected.size+' selected';$('export-summary').disabled=!state.selected.size;renderCharts();});
      const mean=C.statistics([...state.data.syllables.get(id).values()]).mean;
      const n=note('syllables',id);label.title=[n.label,n.comment].filter(Boolean).join('\n');label.append(check,element('span','Syllable '+id+(n.label?' · '+n.label:'')),element('small',mean==null?'no values':format(mean*100)+'%'));list.append(label);
    }
  }
  function bounds(allSeries){
    let min=0,max=0;
    for(const s of allSeries)for(const g of s){if(g.mean!=null){min=Math.min(min,g.mean-(g.sem||0));max=Math.max(max,g.mean+(g.sem||0));}if($('points').checked)for(const a of g.animals)if(a.value!=null)max=Math.max(max,a.value);}
    if(max===0&&min===0)max=factor()===100?1:0.01;
    const raw=(max-min)/4;const power=Math.pow(10,Math.floor(Math.log10(raw)));const norm=raw/power;
    const step=(norm<=1?1:norm<=2?2:norm<=2.5?2.5:norm<=5?5:10)*power;
    return {min:Math.floor(min/step)*step,max:Math.ceil(max*1.06/step)*step,step};
  }
  function chart(id,groups,range){
    const width=Math.max(380,groups.length*84+95),height=285,left=73,right=14,top=35,bottom=70;
    const pw=width-left-right,ph=height-top-bottom,y=v=>top+(range.max-v)/(range.max-range.min)*ph,zero=y(0);
    const svg=svgNode('svg',{xmlns:NS,viewBox:`0 0 ${width} ${height}`,role:'img','aria-label':`${state.data.name}, syllable ${id}, mean plus or minus SEM, ${unitLabel()}`});
    svg.append(svgNode('title',{},`${state.data.name} · Syllable ${id} ${note('syllables',id).label} · ${unitLabel()} · Mean ± SEM`));
    svg.append(svgNode('rect',{width,height,fill:'#ffffff'}));
    svg.append(svgNode('text',{x:left,y:13,fill:'#617982','font-size':10,'font-family':'Arial, sans-serif'},unitLabel()+' · mean ± SEM'));
    svg.append(svgNode('text',{transform:`translate(25 ${top+ph/2}) rotate(-90)`,'text-anchor':'middle',fill:'#405c67','font-size':11,'font-family':'Arial, sans-serif'},unitLabel()));
    svg.append(svgNode('path',{d:`M ${left} ${top} V ${height-bottom} H ${width-right}`,stroke:'#000000','stroke-width':1,fill:'none'}));
    for(let t=range.min,count=0;t<=range.max+range.step/100&&count<12;t+=range.step,count++){
      svg.append(svgNode('line',{x1:left,x2:width-right,y1:y(t),y2:y(t),stroke:Math.abs(t)<range.step/100?'#000000':'#e7eef0','stroke-width':1}));
      svg.append(svgNode('text',{x:left-8,y:y(t)+3,'text-anchor':'end',fill:'#000000','font-size':10,'font-family':'Arial, sans-serif'},format(Math.abs(t)<range.step/100?0:t)));
    }
    groups.forEach((g,i)=>{
      const x=left+pw/groups.length*(i+.5),bw=Math.min(44,pw/groups.length*.55);
      if(g.mean!=null){
        const bar=svgNode('rect',{x:x-bw/2,y:y(g.mean),width:bw,height:Math.max(0,zero-y(g.mean)),fill:color(i),stroke:'#45606b','stroke-opacity':.45,'stroke-width':.7,rx:1,opacity:.87});
        bar.append(svgNode('title',{},`${groupLabel(g)}: mean ${format(g.mean)}, SEM ${format(g.sem)}, n=${g.n}`));svg.append(bar);
        if(g.sem!=null){const hi=y(g.mean+g.sem),lo=y(g.mean-g.sem);svg.append(svgNode('path',{d:`M ${x} ${hi} V ${lo} M ${x-7} ${hi} H ${x+7} M ${x-7} ${lo} H ${x+7}`,stroke:'#263f4b','stroke-width':1.3,fill:'none'}));}
        if($('points').checked)g.animals.forEach((a,j)=>{if(a.value==null)return;const jitter=(((j*7)%11)/10-.5)*bw*.68;const dot=svgNode('circle',{cx:x+jitter,cy:y(a.value),r:2.8,fill:color(i),stroke:'#fff','stroke-width':.8,opacity:.95});const n=note('animals',a.subject);dot.append(svgNode('title',{},`Animal ${a.subject}${n.label?' · '+n.label:''} · ${g.name}: ${format(a.value)}${n.comment?'\n'+n.comment:''}`));svg.append(dot);});
      }else svg.append(svgNode('text',{x,y:zero-9,'text-anchor':'middle',fill:'#7b8991','font-size':10},'No data'));
      const display=groupLabel(g);
      const label=svgNode('text',{x,y:height-bottom+18,'text-anchor':'middle',fill:'#405c67','font-size':10,'font-family':'Arial, sans-serif'},display.length>18?display.slice(0,16)+'…':display);label.append(svgNode('title',{},[display,`Original: ${g.name} (group ${g.id})`,note('groups',g.id).comment].filter(Boolean).join('\n')));svg.append(label);
      svg.append(svgNode('text',{x,y:height-bottom+33,'text-anchor':'middle',fill:'#7c9098','font-size':9,'font-family':'Arial, sans-serif'},`n=${g.n}`));
    });
    const definition=combinations.find(c=>c.id===id);
    svg.append(svgNode('text',{x:left,y:height-8,fill:'#7a9098','font-size':8,'font-family':'Arial, sans-serif'},`${definition?'Sum: '+definition.ids.join(' + '):'Syllable '+id} · ${state.data.name}`));
    if(groups.length>4)svg.style.minWidth=width+'px';return svg;
  }
  function renderCharts(){
    document.querySelectorAll('[data-workspace]').forEach(b=>{b.classList.toggle('active-nav',b.dataset.workspace===workspace);b.setAttribute('aria-pressed',String(b.dataset.workspace===workspace));});
    $('combined-controls').hidden=workspace!=='combined';$('heatmap-controls').hidden=workspace!=='heatmaps';
    document.querySelector('.plot-heading h2').firstChild.textContent=workspace==='combined'?'Combined syllable comparisons ':workspace==='heatmaps'?'Syllable heatmap ':'Syllable comparisons ';
    document.querySelector('.plot-heading p').textContent=workspace==='heatmaps'?'Colors = usage. Gray = missing. Each file has its own syllable definitions.':'Bars = mean ± SEM. Dots = animals. Each file has its own syllable definitions.';
    for(const id of ['scale','columns'])$(id).closest('.control').hidden=workspace==='heatmaps';
    $('points').closest('label').hidden=workspace==='heatmaps';
    $('export-summary').disabled=!state.data||!plotIds().length;
    if(workspace==='heatmaps'){renderHeatmap();return;}
    const area=$('charts');area.replaceChildren();area.style.setProperty('--cols',$('columns').value);
    const ids=state.data?plotIds():[];$('plot-count').textContent=state.data?`${ids.length} shown`:'';
    if(!ids.length){const empty=element('div',null,'empty-state');empty.append(element('span','▥','empty-icon'),element('h2',state.data?'Choose the syllables you want to compare.':'Your data, one syllable at a time.'),element('p',state.data?'Use the checkboxes on the left, or select Top 6 to get started.':'Choose an included file, select your data folder, or drop in a usage-by-subject table.'));area.append(empty);return;}
    const all=ids.map(id=>C.series(viewData(),id,factor()));const shared=bounds(all);
    ids.forEach((id,index)=>{
      const groups=all[index],card=element('article',null,'chart-card');card.dataset.syllable=id;
      const head=element('div',null,'card-header');head.append(element('h3',syllableLabel(id)),element('small',prettyName(state.data.name)));card.append(head);
      const annotation=note('syllables',id);
      const combination=combinations.find(c=>c.id===id);
      if(combination)card.append(element('p','Sum of syllables '+combination.ids.join(' + '),'note-badge'));
      if(annotation.label||annotation.comment){const badge=element('p',annotation.label?'Syllable '+id:'Comment attached','note-badge');badge.title=annotation.comment;card.append(badge);}
      const scroll=element('div',null,'chart-scroll');const svg=chart(id,groups,$('scale').value==='shared'?shared:bounds([groups]));scroll.append(svg);card.append(scroll);
      const values=element('div',null,'bar-values');
      values.append(element('p',unitLabel()+' · mean ± SEM','bar-values-heading'));
      const table=element('table');table.setAttribute('aria-label','Mean and SEM by treatment for '+syllableLabel(id));
      const body=element('tbody');
      groups.forEach((g,i)=>{const row=element('tr'),label=element('th'),swatch=element('i',null,'swatch');label.scope='row';label.title=`Original: ${g.name} (group ${g.id})`;swatch.style.background=color(i);label.append(swatch,document.createTextNode(groupLabel(g)));row.append(label,element('td',g.mean==null?'No data':format(g.mean)+' ± '+(g.sem==null?'N/A':format(g.sem))),element('td','n='+g.n));body.append(row);});
      table.append(body);values.append(table);card.append(values);
      const noSem=groups.filter(g=>g.n<2).map(groupLabel);
      card.append(element('div',noSem.length?'SEM unavailable (n < 2): '+noSem.join(', '):'All available animals · sample SEM','sample-note'));
      const foot=element('div',null,'card-footer'),prism=element('button','Prism table','prism'),save=element('button','Save SVG');
      prism.setAttribute('aria-label','Prism table for syllable '+id);save.setAttribute('aria-label','Save SVG for syllable '+id);
      prism.addEventListener('click',()=>openExport(id));save.addEventListener('click',()=>download(exportFigure(svg,id),filename(`syllable_${id}_${factor()===100?'percent':'fraction'}.svg`),'image/svg+xml;charset=utf-8'));
      const notes=element('button',combination?'Remove combination':'Note');notes.setAttribute('aria-label',combination?'Remove '+combination.label:'Annotate syllable '+id);notes.addEventListener('click',()=>{if(combination){combinations=combinations.filter(c=>c.id!==id);renderCharts();}else openNotes('syllables',id);});foot.append(prism,notes,save);card.append(foot);area.append(card);
    });
  }
  function heatData(){
    if(!state.data)return {columns:[],rows:[]};
    const individuals=$('heat-level').value==='animals';
    const columns=individuals?state.data.groups.flatMap(g=>g.subjects.map(subject=>({label:(note('animals',subject).label||subject)+' · '+groupLabel(g),original:subject,group:g}))):state.data.groups.map(g=>({label:groupLabel(g),original:g.name,group:g}));
    const rows=ordered().map(id=>({id,label:syllableLabel(id),values:individuals?columns.map(c=>{const v=state.data.syllables.get(id).get(c.original);return v==null?null:v*factor();}):C.series(state.data,id,factor()).map(g=>g.mean)}));
    return {columns,rows};
  }
  function renderHeatmap(){
    const area=$('charts');area.replaceChildren();heatSvg=null;heatRows=[];
    const {columns,rows}=heatData();$('plot-count').textContent=rows.length+' syllables';
    $('heat-svg').disabled=$('heat-table').disabled=!rows.length;
    if(!rows.length){area.append(element('p','Select syllables in the sidebar to build a heatmap.','empty-state'));return;}
    const low=Number($('heat-low').value),mid=Number($('heat-mid').value),high=Number($('heat-high').value);
    if(['low','mid','high'].some(k=>$('heat-'+k).value==='')||![low,mid,high].every(Number.isFinite)||!(low<mid&&mid<high)){
      $('heat-status').textContent='Enter three finite thresholds with Low < Midpoint < High.';$('heat-svg').disabled=$('heat-table').disabled=true;return;
    }
    $('heat-status').textContent=`${unitLabel()}. Values ≤ ${format(low)} use the low color; ≥ ${format(high)} use the high color. Gray = missing. No clustering or row normalization.`;
    const palettes={teal:['#fff9e9','#76c8ae','#00645e'],purple:['#fff9ed','#bc9cd4','#502079'],'blue-red':['#285f9e','#faf8f3','#b73249'],'pink-blue':['#FF2CDF','#0014FF'],'cyan-pink':['#00E1FD','#FC007A'],'green-blue':['#00FF5B','#0014FF'],'yellow-red':['#FFE53B','#FF2525'],'ivory-pink':['#fff9e9','#FF005B'],...window.MOSEQ_PALETTES};
    const colors=palettes[$('heat-palette').value];
    function shade(v){if(v==null)return '#cbd0d4';const position=Math.max(0,Math.min(1,v<=mid ? .5*(v-low)/(mid-low):.5+.5*(v-mid)/(high-mid)))*(colors.length-1),index=Math.min(colors.length-2,Math.floor(position)),t=position-index,a=colors[index],b=colors[index+1];const rgb=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16));return 'rgb('+rgb(a).map((n,i)=>Math.round(n+(rgb(b)[i]-n)*t)).join(',')+')';}
    const left=210,cellW=Number($('heat-width').value),cellH=Number($('heat-height').value),top=cellW<18?90:145,width=Math.max(650,left+rows.length*cellW+25);
    const individuals=$('heat-level').value==='animals',rowY=[],bands=[];let cursor=top;
    columns.forEach((c,i)=>{
      if(individuals&&(i===0||c.group.id!==columns[i-1].group.id)){
        if(i)cursor+=10;
        bands.push({y:cursor,group:c.group});cursor+=26;
      }else if(!individuals&&i)cursor+=6;
      rowY.push(cursor);cursor+=cellH;
    });
    const height=cursor+88;
    $('heat-width-value').value=cellW+' px';$('heat-height-value').value=cellH+' px';
    const svg=svgNode('svg',{xmlns:NS,viewBox:`0 0 ${width} ${height}`,width,height,role:'img','aria-label':state.data.name+' usage heatmap'});
    svg.append(svgNode('rect',{width,height,fill:'#fff'}),svgNode('text',{x:18,y:23,'font-size':15,'font-family':'Arial',fill:'#172e3d'},prettyName(state.data.name)+' · '+($('heat-level').value==='animals'?'Individual animals':'Treatment means')),svgNode('text',{x:18,y:42,'font-size':10,'font-family':'Arial',fill:'#627580'},state.data.name+' · '+unitLabel()));
    rows.forEach((r,j)=>{const label=svgNode('text',{transform:`translate(${left+j*cellW+cellW/2} ${top-9}) rotate(${cellW<18?-90:-45})`,'font-size':cellW<18?8:10,'font-family':'Arial',fill:'#172e3d'},cellW<18?r.id:r.label.length>25?r.label.slice(0,23)+'…':r.label);label.append(svgNode('title',{},r.label+' · Syllable '+r.id));svg.append(label);});
    bands.forEach(b=>{
      const index=state.data.groups.findIndex(g=>g.id===b.group.id),heading=groupLabel(b.group)+' · '+b.group.subjects.length+' animals';
      svg.append(svgNode('rect',{x:18,y:b.y,width:width-36,height:22,fill:'#edf3f5',rx:3,'data-treatment-header':b.group.id}),svgNode('rect',{x:18,y:b.y,width:4,height:22,fill:color(index)}));
      const label=svgNode('text',{x:29,y:b.y+15,'font-size':11,'font-family':'Arial','font-weight':700,fill:'#172e3d'},heading.length>80?heading.slice(0,78)+'…':heading);label.append(svgNode('title',{},heading));svg.append(label);
    });
    columns.forEach((c,i)=>{const display=individuals?(note('animals',c.original).label?c.original+' · '+note('animals',c.original).label:c.original):c.label;const label=svgNode('text',{x:left-10,y:rowY[i]+cellH/2+4,'text-anchor':'end','font-family':'Arial','font-size':11,fill:'#172e3d'},display.length>28?display.slice(0,26)+'…':display);label.append(svgNode('title',{},c.label+' · Original: '+c.original));svg.append(label);});
    rows.forEach((r,j)=>r.values.forEach((v,i)=>{const cell=svgNode('rect',{x:left+j*cellW,y:rowY[i],width:cellW,height:cellH,fill:shade(v),stroke:'#fff','stroke-width':.7,'data-syllable':r.id,'data-row':i});cell.append(svgNode('title',{},`${r.label} (syllable ${r.id}) · ${columns[i].label}: ${v==null?'Missing':format(v)+' '+unitLabel()}`));svg.append(cell);}));
    const legendY=cursor+23;
    for(let i=0;i<180;i++)svg.append(svgNode('rect',{x:left+i,y:legendY,width:1.1,height:12,fill:shade(low+(high-low)*i/179)}));
    for(const [v,x] of [[low,left],[mid,left+180*(mid-low)/(high-low)],[high,left+180]])svg.append(svgNode('text',{x,y:legendY+28,'text-anchor':'middle','font-size':10,'font-family':'Arial',fill:'#405c67'},format(v)));
    svg.append(svgNode('text',{x:left,y:legendY+48,'font-size':10,'font-family':'Arial',fill:'#405c67'},unitLabel()+' · gray = missing'));
    const wrap=element('div',null,'heatmap-card');wrap.append(svg);area.append(wrap);heatSvg=svg;
    heatRows=[['dataset','units','group','treatment','animal',...rows.map(r=>'Syllable '+r.id)],...columns.map((c,i)=>[state.data.name,unitLabel(),c.group.id,c.group.name,$('heat-level').value==='animals'?c.original:'',...rows.map(r=>r.values[i])])];
  }
  document.querySelectorAll('[data-workspace]').forEach(b=>b.addEventListener('click',()=>{workspace=b.dataset.workspace;renderCharts();}));
  $('add-combination').addEventListener('click',()=>{
    if(!state.data)return;const ids=ordered(),label=$('combination-name').value.trim();
    if(ids.length<2||!label){$('combination-status').textContent='Select at least two syllables and enter a name.';return;}
    combinations.push({id:'combined-'+Date.now().toString(36)+'-'+combinations.length,label,ids});$('combination-name').value='';$('combination-status').textContent='Added '+label+'. Save your session to keep this combination.';renderCharts();
  });
  for(const id of ['heat-level','heat-palette','heat-low','heat-mid','heat-high'])$(id).addEventListener('change',renderCharts);
  for(const id of ['heat-width','heat-height'])$(id).addEventListener('input',renderCharts);
  $('heat-square').addEventListener('click',()=>{const size=Math.max(12,Math.min(90,Number($('heat-width').value)));$('heat-width').value=size;$('heat-height').value=size;renderCharts();});
  $('heat-reset-size').addEventListener('click',()=>{$('heat-width').value=36;$('heat-height').value=32;renderCharts();});
  $('units').addEventListener('change',()=>{const multiplier=factor()===100?100:.01;for(const k of ['low','mid','high'])$('heat-'+k).value=Number($('heat-'+k).value)*multiplier;renderCharts();});
  $('heat-auto').addEventListener('click',()=>{const values=heatData().rows.flatMap(r=>r.values).filter(v=>v!=null),high=values.length?Math.max(...values):factor()===100?1:.01;$('heat-low').value=0;$('heat-high').value=high||1;$('heat-mid').value=Number($('heat-high').value)/2;renderCharts();});
  $('heat-svg').addEventListener('click',()=>{if(heatSvg)download(new XMLSerializer().serializeToString(heatSvg),filename('heatmap.svg'),'image/svg+xml');});
  $('heat-table').addEventListener('click',()=>download(C.tsv(heatRows),filename('heatmap_values.tsv')));
  function exportFigure(svg,id){
    const copy=svg.cloneNode(true),{width,height}=svg.viewBox.baseVal;
    const lines=syllableLabel(id).match(/.{1,40}(?:\s|$)|.{1,40}/g)||['Syllable '+id];
    const headingHeight=lines.length*19+28,content=svgNode('g',{transform:`translate(0 ${headingHeight})`});
    while(copy.firstChild)content.append(copy.firstChild);
    copy.setAttribute('viewBox',`0 0 ${width} ${height+headingHeight}`);
    copy.append(svgNode('rect',{width,height:height+headingHeight,fill:'#fff'}),content);
    lines.forEach((line,i)=>copy.append(svgNode('text',{x:18,y:22+i*19,fill:'#172e3d','font-size':15,'font-weight':700,'font-family':'Arial, sans-serif'},line.trim())));
    if(note('syllables',id).label)copy.append(svgNode('text',{x:18,y:22+lines.length*19,fill:'#127c78','font-size':10,'font-family':'Arial, sans-serif'},'Syllable '+id));
    const combined=combinations.find(c=>c.id===id);
    if(combined)copy.append(svgNode('text',{x:18,y:22+lines.length*19,fill:'#127c78','font-size':9,'font-family':'Arial, sans-serif'},'Sum of syllables '+combined.ids.join(' + ')));
    return new XMLSerializer().serializeToString(copy);
  }
  function renderTable(rows){const table=element('table'),head=element('thead'),body=element('tbody');const tr=element('tr');for(const title of rows[0]){const th=element('th',title);th.scope='col';tr.append(th);}head.append(tr);for(const row of rows.slice(1)){const line=element('tr');for(const value of row)line.append(element('td',value==null?'':String(value)));body.append(line);}table.append(head,body);return table;}
  function openExport(id){
    state.exportId=id;const raw=C.prism(viewData(),id,factor());
    $('export-title').textContent=syllableLabel(id)+' · Prism table';$('export-context').textContent=state.data.name+' — '+unitLabel()+'. Animal IDs sorted within each group; no pairing across treatments.'+(combinations.find(c=>c.id===id)?' Sum of syllables: '+combinations.find(c=>c.id===id).ids.join(' + '):'');
    $('export-preview').replaceChildren(renderTable(raw.rows));$('export-text').value=raw.text;
    $('export-stats').replaceChildren(renderTable([['Treatment','n','Mean','Sample SD','SEM'],...C.series(viewData(),id,factor()).map(g=>[g.name,g.n,format(g.mean),format(g.sd),format(g.sem)])]));
    $('export-dialog').showModal();
  }
  async function filesSelected(files,fromFolder){
    const valid=[...files].filter(f=>/\.(txt|tsv|csv)$/i.test(f.name));
    if(!valid.length){error('No TXT, TSV or CSV data files were selected.');return;}
    const sources=valid.sort((a,b)=>C.compare(a.name,b.name)).map(file=>({id:'file:'+(file.webkitRelativePath||file.name),name:file.webkitRelativePath||file.name,file,kind:'file'}));
    if(fromFolder)state.sources=state.sources.filter(s=>s.kind!=='file');
    addSources(sources);$('dataset').value=sources[0].id;await loadSource(sources[0].id);
  }
  $('dataset').addEventListener('change',()=>loadSource($('dataset').value));
  $('folder-button').addEventListener('click',()=>$('folder-input').click());$('file-button').addEventListener('click',()=>$('file-input').click());
  $('folder-input').addEventListener('change',e=>{filesSelected(e.target.files,true);e.target.value='';});$('file-input').addEventListener('change',e=>{filesSelected(e.target.files,false);e.target.value='';});
  $('refresh-data').addEventListener('click',()=>scanLocal());
  $('syllable-search').addEventListener('input',renderSyllables);
  $('select-all').addEventListener('click',()=>{if(!state.data)return;state.data.ids.filter(id=>id.includes($('syllable-search').value.trim())).forEach(id=>state.selected.add(id));render();});
  $('clear-selection').addEventListener('click',()=>{state.selected.clear();render();});$('top-six').addEventListener('click',()=>{if(!state.data)return;state.selected=new Set(C.top(state.data));render();});
  $('top-twenty').addEventListener('click',()=>{if(!state.data)return;state.selected=new Set(C.top(state.data,20));render();});
  for(const id of ['units','scale','columns','points'])$(id).addEventListener('change',renderCharts);
  $('export-summary').addEventListener('click',()=>download(C.summary(viewData(),plotIds(),factor()),filename(workspace+'_summary_'+(factor()===100?'percent':'fraction')+'.tsv')));
  $('download-table').addEventListener('click',()=>download($('export-text').value,filename(`syllable_${state.exportId}_${factor()===100?'percent':'fraction'}_Prism.tsv`)));
  $('download-records').addEventListener('click',()=>download(C.animalExport(viewData(),state.exportId,factor()),filename(`syllable_${state.exportId}_animal_records.tsv`)));
  $('copy-table').addEventListener('click',async()=>{
    try{if(!navigator.clipboard?.writeText)throw new Error('Fallback');await navigator.clipboard.writeText($('export-text').value);toast('Copied individual animal values. Paste into a Prism Column table.');}
    catch {const text=$('export-text');text.closest('details').open=true;text.focus();text.select();let copied=false;try{copied=document.execCommand('copy');}catch{}toast(copied?'Copied individual animal values.':'Text selected. Press Ctrl+C (or Command+C) to copy.');}
  });
  async function saveSession(){
    if(!state.data||savingSession)return false;
    savingSession=true;
    const key=viewKey(state.data),current=activeNotes,payload={app:'MoSeq Dashboard',version:'0.1',dataset:{name:state.data.name,text:state.data.text},settings:settings(),notes:activeNotes.notes},notesSnapshot=JSON.stringify(activeNotes.notes),viewSnapshot=JSON.stringify(payload.settings);
    try{
      if(location.protocol==='http:'&&state.sources.some(s=>s.kind==='live'&&s.name===state.data.name)){
        const response=await fetch('/api/session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
        if(!response.ok)throw new Error(await response.text());
        toast('Session saved beside the raw file in data_MoSeq_raw. It will reopen with this dataset.');
      }else{download(JSON.stringify(payload,null,2),filename('session.json'),'application/json');toast('Session downloaded. Use the Python launcher to save directly beside raw files.');}
      if(JSON.stringify(current.notes)===notesSnapshot)current.dirty=false;updateNotesStatus();
      savedViews.set(key,viewSnapshot);return true;
    }catch(err){error('Session was not saved: '+err.message);return false;}
    finally{savingSession=false;}
  }
  $('save-session').addEventListener('click',saveSession);
  $('open-session').addEventListener('click',()=>$('session-input').click());
  $('session-input').addEventListener('change',async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;try{if(file.size>25*1024*1024)throw new Error('Session file is too large.');const saved=JSON.parse(await file.text());if(saved.app!=='MoSeq Dashboard'||saved.version!=='0.1'||typeof saved.dataset?.name!=='string'||typeof saved.dataset?.text!=='string'||!Array.isArray(saved.settings?.selected))throw new Error('Not a supported v0.1 session.');const parsed=C.parse(saved.dataset.text,saved.dataset.name);if(saved.notes)C.validateNotes(saved.notes,parsed);const id='session:'+saved.dataset.name;addSources([{id,...saved.dataset,kind:'session'}]);$('dataset').value=id;await loadSource(id,saved.settings,saved.notes);toast('Session restored.');}catch(err){error('Could not restore session: '+err.message);}});
  function updateNotesStatus(){const count=activeNotes?['syllables','animals','groups'].reduce((n,k)=>n+Object.keys(activeNotes.notes[k]).length,0):0;$('notes-count').textContent=count?`(${count}${activeNotes.dirty?'*':''})`:activeNotes?.dirty?'*':'';$('notes-status').textContent=activeNotes?.dirty?'Unsaved changes — save a notes file or session':`${count} note(s) in this dataset`;}
  function noteTargets(){
    const kind=$('note-kind').value;
    if(kind==='syllables')return state.data.ids.map(id=>[id,'Syllable '+id]);
    if(kind==='groups')return state.data.groups.map(g=>[g.id,`Group ${g.id} · ${g.name}`]);
    return [...state.data.subjects].sort((a,b)=>C.compare(a[0],b[0])).map(([id,group])=>[id,`Animal ${id} · ${state.data.groups.find(g=>g.id===group).name}`]);
  }
  function fillNoteTargets(id){$('note-id').replaceChildren(...noteTargets().map(([value,label])=>new Option(label,value)));if(id!=null)$('note-id').value=id;fillNoteFields();}
  function fillNoteFields(){const n=note($('note-kind').value,$('note-id').value);$('note-label').value=n.label;$('note-comment').value=n.comment;}
  function openNotes(kind='syllables',id){if(!state.data)return;$('notes-context').textContent=state.data.name;$('note-kind').value=kind;fillNoteTargets(id);renderNotesList();updateNotesStatus();$('notes-dialog').showModal();}
  function commitNote(){
    const kind=$('note-kind').value,id=$('note-id').value;if(!id||!activeNotes)return;
    const label=$('note-label').value.trim(),comment=$('note-comment').value.trim(),old=note(kind,id);
    if(label===old.label&&comment===old.comment)return;
    if(label||comment)activeNotes.notes[kind][id]={label,comment};else delete activeNotes.notes[kind][id];
    activeNotes.dirty=true;updateNotesStatus();
  }
  function renderNotesList(){
    $('notes-list').replaceChildren();let count=0;
    for(const kind of ['syllables','animals','groups'])for(const [id,n] of Object.entries(activeNotes.notes[kind]).sort((a,b)=>C.compare(a[0],b[0]))){count++;const row=element('div',null,'note-entry'),copy=element('div');copy.append(element('strong',`${kind==='syllables'?'Syllable':kind==='animals'?'Animal':'Group'} ${id}${n.label?' · '+n.label:''}`));if(n.comment)copy.append(element('p',n.comment));const edit=element('button','Edit');edit.addEventListener('click',()=>{$('note-kind').value=kind;fillNoteTargets(id);});row.append(copy,edit);$('notes-list').append(row);}
    if(!count)$('notes-list').append(element('p','No annotations yet. Choose a syllable, animal or group above.','sidecar-explanation'));
  }
  $('notes-button').addEventListener('click',()=>openNotes());$('note-kind').addEventListener('change',()=>fillNoteTargets());$('note-id').addEventListener('change',fillNoteFields);
  for(const id of ['note-label','note-comment'])$(id).addEventListener('input',commitNote);
  $('apply-note').addEventListener('click',()=>{commitNote();renderNotesList();render();toast('Note applied in this session. Save the notes file to keep it.');});
  $('delete-note').addEventListener('click',()=>{$('note-label').value='';$('note-comment').value='';commitNote();renderNotesList();render();});
  $('notes-dialog').addEventListener('close',()=>{render();});
  $('save-notes').addEventListener('click',()=>{commitNote();download(JSON.stringify(activeNotes.notes,null,2),activeNotes.notes.dataset.filename.replace(/\.[^.]+$/,'')+'.moseq-notes.json','application/json');activeNotes.dirty=false;updateNotesStatus();toast('Notes file downloaded. Keep it beside the matching raw data.');});
  $('load-notes').addEventListener('click',()=>$('notes-input').click());
  $('notes-input').addEventListener('change',async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;try{if(file.size>2*1024*1024)throw new Error('Notes file is too large.');const input=JSON.parse(await file.text()),notes=C.validateNotes(input,state.data);if(activeNotes.dirty&&!confirm('Replace unsaved notes for this dataset with the selected notes file?'))return;activeNotes.notes=notes;activeNotes.dirty=false;fillNoteFields();renderNotesList();render();toast('Matching notes loaded.');}catch(err){toast('Notes not loaded: '+err.message);}});
  function unsavedDatasets(){
    const names=new Set();
    for(const [key,value] of viewMemory)if(JSON.stringify(value)!==savedViews.get(key)&&(!state.data||key!==viewKey(state.data)))names.add(viewNames.get(key)||'Previous dataset');
    if(state.data&&JSON.stringify(captureSettings())!==savedViews.get(viewKey(state.data)))names.add(state.data.name);
    for(const entry of noteMemory.values())if(entry.dirty)names.add(entry.notes.dataset.filename);
    return [...names];
  }
  function showCloseStatus(){
    const unsaved=unsavedDatasets();
    $('close-dashboard-message').textContent=unsaved.length?'There are unsaved notes or session settings in the datasets below. Save the current session, or keep working to save another dataset.':'Ready to close. The local launcher will stop; you can then close this browser tab.';
    $('unsaved-datasets').replaceChildren(...unsaved.map(name=>element('li',name)));
    $('save-before-close').hidden=!unsaved.length;$('save-before-close').disabled=!state.data||savingSession;
    $('confirm-close-dashboard').textContent=unsaved.length?'Close without saving':'Close dashboard';
  }
  $('close-dashboard').addEventListener('click',()=>{showCloseStatus();$('close-dashboard-status').textContent='';$('close-dashboard-dialog').showModal();});
  $('save-before-close').addEventListener('click',async()=>{
    $('save-before-close').disabled=true;$('confirm-close-dashboard').disabled=true;
    const success=await saveSession();showCloseStatus();$('confirm-close-dashboard').disabled=false;
    $('close-dashboard-status').textContent=success?'Current session saved. Save any other listed datasets before closing.':'Save failed. The dashboard is still running. Keep working to resolve the error or try again.';
  });
  $('confirm-close-dashboard').addEventListener('click',async()=>{
    if(savingSession){$('close-dashboard-status').textContent='Wait for the session save to finish.';return;}
    $('confirm-close-dashboard').disabled=true;
    try{
      const local=location.protocol==='http:'&&['127.0.0.1','localhost'].includes(location.hostname);
      if(local){const response=await fetch('/api/shutdown',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok)throw new Error('The launcher did not accept the close request. Restart it once to load the updated version.');await response.json();}
      dashboardClosed=true;clearTimeout(toastTimer);$('close-dashboard-dialog').close();
      const panel=element('section',null,'empty-state');panel.style.margin='12vh auto';panel.style.maxWidth='600px';panel.append(element('h1','Dashboard closed'),element('p',local?'The Python server has stopped. You can close this browser tab.':'You can close this browser tab. No Python server was running in this mode.'));
      document.body.replaceChildren(panel);
    }catch(err){$('close-dashboard-status').textContent='Could not close the launcher: '+err.message;$('confirm-close-dashboard').disabled=false;}
  });
  window.addEventListener('beforeunload',e=>{if(!dashboardClosed&&(savingSession||unsavedDatasets().length)){e.preventDefault();e.returnValue='';}});
  for(const name of ['help','about'])$(name+'-button').addEventListener('click',()=>$(name+'-dialog').showModal());
  document.querySelectorAll('.close-dialog').forEach(b=>b.addEventListener('click',()=>b.closest('dialog').close()));
  document.addEventListener('dragenter',e=>{if([...e.dataTransfer.types].includes('Files')){e.preventDefault();dragDepth++;$('drop-overlay').hidden=false;}});
  document.addEventListener('dragleave',()=>{dragDepth=Math.max(0,dragDepth-1);if(!dragDepth)$('drop-overlay').hidden=true;});
  document.addEventListener('dragover',e=>{if([...e.dataTransfer.types].includes('Files'))e.preventDefault();});
  document.addEventListener('drop',e=>{e.preventDefault();dragDepth=0;$('drop-overlay').hidden=true;if(e.dataTransfer.files.length)filesSelected(e.dataTransfer.files,false);});
  addSources((window.MOSEQ_CATALOG || []).map(s=>({...s,id:'snapshot:'+s.name,kind:'snapshot'})));
  if(location.protocol==='http:'&&['127.0.0.1','localhost'].includes(location.hostname))scanLocal(false);
  else if(state.sources.length){state.sourceId=state.sources[0].id;sourceMenu();loadSource(state.sourceId);}
  else render();
})();
