const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('scripts/mobile_photo/upload.js', 'utf8');

function harness(saved = new Map()) {
  const events = {}, messages = [], timers = [];
  const elements = Object.fromEntries(['photo','send','clear','status','details','progress','preview','pickerLabel'].map(id => [id, {
    disabled:false, files:[], value:0, textContent:'', style:{},
    classList:{toggle(){}}, removeAttribute(){}, addEventListener(type, fn) {this[type] = fn;}
  }]));
  const parent = {postMessage: msg => messages.push(msg)};
  let id = 0;
  const context = {
    document:{getElementById:id => elements[id], body:{scrollHeight:220}},
    window:{parent, addEventListener:(type, fn) => events[type] = fn},
    crypto:{randomUUID:() => String(++id)},
    URL:{createObjectURL:() => 'blob:preview', revokeObjectURL(){}},
    Date,
    setTimeout:fn => {timers.push(fn); return timers.length;}, clearTimeout:() => {},
    indexedDB:{open() {
      const request = {};
      queueMicrotask(() => {
        request.result = {close(){}, transaction() {
          const tx = {objectStore:() => ({
            get:key => ({result:saved.get(key)}),
            put:(value,key) => {saved.set(key,value); return {};},
            delete:key => {saved.delete(key); return {};}
          })};
          queueMicrotask(() => tx.oncomplete()); return tx;
        }};
        request.onsuccess();
      }); return request;
    }},
    FileReader:class {readAsDataURL(file) {this.result = 'data:image/jpeg;base64,' + file.data; this.onload();}}
  };
  vm.runInNewContext(source, context);
  return {elements, messages, timers, saved,
    render:args => events.message({source:parent,data:{type:'streamlit:render',disabled:true,args:{scope:'new',disabled:false,...args}}})};
}

test('selection survives disconnected render, explicit send, retry and acknowledgement', async () => {
  const h = harness();
  await h.render({});
  // Streamlit disables standard widgets on a dropped connection.
  assert.equal(h.elements.photo.disabled, false);
  h.elements.photo.files = [{name:'phone.jpg',size:3,type:'image/jpeg',data:'YWJj'}];
  await h.elements.photo.change();
  assert.equal(h.messages.filter(m => m.type === 'streamlit:setComponentValue').length, 0);
  assert.equal(h.elements.send.disabled, false);
  await h.elements.send.click();
  const first = h.messages.at(-1).value;
  h.timers.at(-1)();
  await h.elements.send.click();
  const retry = h.messages.at(-1).value;
  assert.equal(retry.data, first.data);
  assert.notEqual(retry.attempt_id, first.attempt_id);
  await h.render({ack:retry.request_id});
  assert.match(h.elements.status.textContent, /ricevuta dalla web app/);
  assert.equal(h.elements.progress.value, 100);
  assert.equal(h.saved.has('new'), false);
});

test('unsubmitted photo is restored after iframe recreation and never sent automatically', async () => {
  const saved = new Map();
  const a = harness(saved); await a.render({});
  a.elements.photo.files = [{name:'saved.jpg',size:3,type:'image/jpeg',data:'YWJj'}];
  await a.elements.photo.change();
  const b = harness(saved); await b.render({});
  assert.match(b.elements.status.textContent, /recuperata/);
  assert.equal(b.elements.send.disabled, false);
  assert.equal(b.messages.filter(m => m.type === 'streamlit:setComponentValue').length, 0);
  await b.render({scope:'hist:another-dedication'});
  assert.equal(b.elements.send.disabled, true);
});

test('stale local data from an older uploader is discarded', async () => {
  const saved = new Map([['new', {name:'old.jpg', data:'YWJj', scope:'new'}]]);
  const h = harness(saved); await h.render({});
  assert.equal(h.elements.send.disabled, true);
  assert.equal(saved.has('new'), false);
});
