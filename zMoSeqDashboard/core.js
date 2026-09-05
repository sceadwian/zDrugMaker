/* MoSeq Dashboard v0.1 — pure parsing, descriptive statistics and export logic. */
(function (root) {
  'use strict';
  const compare = (a, b) => String(a).localeCompare(String(b), 'en', {numeric: true});
  function readDelimited(text, delimiter) {
    const rows = []; let row = [], cell = '', quoted = false, closed = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (ch === '"') { quoted = false; closed = true; }
        else cell += ch;
      } else if (ch === '"' && !cell && !closed) quoted = true;
      else if (ch === delimiter) { row.push(cell); cell = ''; closed = false; }
      else if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && text[i + 1] === '\n') i++;
        row.push(cell); if (row.some(x => x.trim() !== '')) rows.push(row);
        row = []; cell = ''; closed = false;
      } else {
        if (closed && ch.trim()) throw new Error('Unexpected text after a quoted field. Check the delimiters.');
        if (!closed) cell += ch;
      }
    }
    if (quoted) throw new Error('Unclosed quoted field in this file.');
    row.push(cell); if (row.some(x => x.trim() !== '')) rows.push(row);
    return rows;
  }
  function parse(text, name = 'Dataset') {
    if (typeof text !== 'string' || text.length > 20 * 1024 * 1024) throw new Error('Choose a text file smaller than 20 MB.');
    const clean = text.replace(/^\uFEFF/, '').trimStart();
    const first = clean.split(/[\r\n]/, 1)[0];
    const rows = readDelimited(clean, first.includes('\t') ? '\t' : ',');
    if (rows.length < 2) throw new Error('The file needs a header and at least one data row.');
    const headers = rows.shift().map(x => x.trim().toLowerCase());
    const required = ['subject', 'group', 'syllable', 'usage', 'treat'];
    if (new Set(headers).size !== headers.length) throw new Error('Duplicate column names are not allowed.');
    const absent = required.filter(x => !headers.includes(x));
    if (absent.length) throw new Error('Missing required columns: ' + absent.join(', ') + '.');
    const columns = Object.fromEntries(required.map(x => [x, headers.indexOf(x)]));
    const groups = new Map(), subjects = new Map(), syllables = new Map(), seen = new Set(), labels = new Map();
    const records = []; let missing = 0;
    rows.forEach((row, index) => {
      const line = index + 2;
      if (row.length !== headers.length) throw new Error(`Data row ${line}: expected ${headers.length} fields, found ${row.length}.`);
      const rec = Object.fromEntries(required.map(x => [x, row[columns[x]].trim()]));
      for (const key of ['subject', 'group', 'syllable', 'treat']) {
        if (!rec[key]) throw new Error(`Data row ${line}: ${key} is blank.`);
        if (/[\r\n\t\x00-\x1f]/.test(rec[key])) throw new Error(`Data row ${line}: ${key} contains control characters.`);
      }
      if (!/^\d+$/.test(rec.syllable) || !Number.isSafeInteger(Number(rec.syllable))) throw new Error(`Data row ${line}: syllable must be a non-negative integer ID.`);
      rec.syllable = String(Number(rec.syllable));
      const key = JSON.stringify([rec.subject, rec.syllable]);
      if (seen.has(key)) throw new Error(`Duplicate subject–syllable record: animal ${rec.subject}, syllable ${rec.syllable}. No rows were merged.`);
      seen.add(key);
      if (subjects.has(rec.subject) && subjects.get(rec.subject) !== rec.group) throw new Error(`Animal ${rec.subject} has conflicting group assignments.`);
      subjects.set(rec.subject, rec.group);
      if (groups.has(rec.group) && groups.get(rec.group).name !== rec.treat) throw new Error(`Group ${rec.group} has conflicting treatment names.`);
      if (labels.has(rec.treat) && labels.get(rec.treat) !== rec.group) throw new Error(`Treatment ${rec.treat} is assigned more than one group ID.`);
      labels.set(rec.treat, rec.group);
      if (!groups.has(rec.group)) groups.set(rec.group, {id: rec.group, name: rec.treat, subjects: new Set()});
      groups.get(rec.group).subjects.add(rec.subject);
      if (/^(?:|na|n\/a|nan|null)$/i.test(rec.usage)) { rec.value = null; missing++; }
      else {
        if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(rec.usage)) throw new Error(`Data row ${line}: usage is not a valid number.`);
        rec.value = Number(rec.usage);
        if (!Number.isFinite(rec.value) || rec.value < 0 || rec.value > 1) throw new Error(`Data row ${line}: usage must be a fraction between 0 and 1. Percentage input is not converted automatically.`);
      }
      if (!syllables.has(rec.syllable)) syllables.set(rec.syllable, new Map());
      syllables.get(rec.syllable).set(rec.subject, rec.value);
      records.push(rec);
    });
    if (!records.some(r => r.value !== null)) throw new Error('No numeric usage observations were found.');
    const orderedGroups = [...groups.values()].sort((a,b) => compare(a.id,b.id)).map(g => ({...g, subjects: [...g.subjects].sort(compare)}));
    const ids = [...syllables.keys()].sort(compare);
    const absentCells = subjects.size * ids.length - records.length;
    const warnings = [];
    if (missing) warnings.push(`${missing} explicitly missing usage value(s) excluded from means and SEM.`);
    if (absentCells) warnings.push(`${absentCells} animal–syllable combination(s) have no row; they remain missing, not zero.`);
    return {name, text, groups: orderedGroups, subjects, syllables, ids, records, warnings, missing, absentCells};
  }
  function statistics(values) {
    let n = 0, mean = 0, m2 = 0;
    for (const value of values) if (value !== null && value !== undefined && Number.isFinite(value)) {
      n++; const delta = value - mean; mean += delta / n; m2 += delta * (value - mean);
    }
    const sd = n > 1 ? Math.sqrt(Math.max(0, m2 / (n - 1))) : null;
    return {n, mean: n ? mean : null, sd, sem: sd === null ? null : sd / Math.sqrt(n)};
  }
  function series(data, id, factor = 1) {
    const map = data.syllables.get(String(id));
    if (!map) throw new Error('Unknown syllable ID.');
    return data.groups.map(g => {
      const animals = g.subjects.map(subject => ({subject, value: map.get(subject) == null ? null : map.get(subject) * factor}));
      return {...g, animals, ...statistics(animals.map(a => a.value))};
    });
  }
  function top(data, limit = 6) {
    return [...data.ids].sort((a,b) => (statistics([...data.syllables.get(b).values()]).mean ?? -1) - (statistics([...data.syllables.get(a).values()]).mean ?? -1) || compare(a,b)).slice(0,limit);
  }
  function safeCell(value) {
    if (value == null) return '';
    let str = String(value);
    if (typeof value === 'string' && /^[=+@-]/.test(str)) str = "'" + str;
    return /[\t\n\r"]/.test(str) ? '"' + str.replace(/"/g,'""') + '"' : str;
  }
  const tsv = rows => rows.map(row => row.map(safeCell).join('\t')).join('\r\n');
  function prism(data, id, factor = 1) {
    const groups = series(data, id, factor);
    const rows = [groups.map(g => g.name)];
    const length = Math.max(...groups.map(g => g.animals.length));
    for (let i=0;i<length;i++) rows.push(groups.map(g => g.animals[i]?.value ?? null));
    return {rows, text: tsv(rows)};
  }
  function summary(data, ids, factor = 1) {
    const units = factor === 100 ? 'percent' : 'fraction';
    const rows = [['dataset','syllable','group','treatment','units','n','mean','sample_SD','SEM']];
    for (const id of ids) for (const g of series(data,id,factor)) rows.push([data.name,id,g.id,g.name,units,g.n,g.mean,g.sd,g.sem]);
    return tsv(rows);
  }
  function animalExport(data, id, factor=1) {
    const rows = [['dataset','syllable','group','treatment','subject','units','usage']];
    for (const g of series(data,id,factor)) for (const a of g.animals) rows.push([data.name,id,g.id,g.name,a.subject,factor===100?'percent':'fraction',a.value]);
    return tsv(rows);
  }
  function fingerprint(text) {
    // Non-security content identity, stable across BOM and Windows/Unix line endings.
    let hash = 0xcbf29ce484222325n;
    const bytes = new TextEncoder().encode(text.replace(/^\uFEFF/,'').replace(/\r\n?/g,'\n'));
    for(const byte of bytes) hash = BigInt.asUintN(64,(hash ^ BigInt(byte))*0x100000001b3n);
    return 'fnv1a64:'+hash.toString(16).padStart(16,'0');
  }
  function blankNotes(data) {
    return {format:'moseq-notes',version:'0.1',dataset:{filename:data.name.split(/[\\/]/).pop(),fingerprint:fingerprint(data.text)},syllables:Object.create(null),animals:Object.create(null),groups:Object.create(null)};
  }
  function validateNotes(input,data) {
    const notes=blankNotes(data);
    if(input?.format!=='moseq-notes'||input.version!=='0.1')throw new Error('This is not a supported MoSeq v0.1 notes file.');
    if(input.dataset?.fingerprint!==notes.dataset.fingerprint||input.dataset?.filename!==notes.dataset.filename)throw new Error('These notes belong to a different file or an edited version of the dataset. Load the matching raw file first.');
    const valid={syllables:new Set(data.ids),animals:new Set(data.subjects.keys()),groups:new Set(data.groups.map(g=>g.id))};
    for(const kind of Object.keys(valid)){
      const entries=input[kind];if(!entries||typeof entries!=='object'||Array.isArray(entries))throw new Error('Invalid notes structure: '+kind);
      for(const [id,note] of Object.entries(entries)){
        if(!valid[kind].has(id))throw new Error(`Unknown ${kind} ID in notes: ${id}`);
        if(!note||typeof note.label!=='string'||typeof note.comment!=='string'||note.label.length>100||note.comment.length>4000)throw new Error('A note contains invalid or oversized fields.');
        if(note.label||note.comment)notes[kind][id]={label:note.label,comment:note.comment};
      }
    }
    return notes;
  }
  function combine(data,definitions){
    const syllables=new Map();
    for(const def of definitions){
      if(!def.id||syllables.has(def.id)||!Array.isArray(def.ids)||def.ids.length<2||new Set(def.ids).size!==def.ids.length||def.ids.some(id=>!data.syllables.has(id)))throw new Error('A combination needs at least two distinct, valid syllables.');
      const values=new Map();
      for(const subject of data.subjects.keys()){
        const parts=def.ids.map(id=>data.syllables.get(id).get(subject));
        values.set(subject,parts.some(v=>v==null)?null:parts.reduce((sum,v)=>sum+v,0));
      }
      syllables.set(def.id,values);
    }
    return {...data,syllables,ids:definitions.map(d=>d.id)};
  }
  const api = {parse,readDelimited,statistics,series,top,prism,summary,animalExport,tsv,compare,fingerprint,blankNotes,validateNotes,combine};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MoSeqCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
