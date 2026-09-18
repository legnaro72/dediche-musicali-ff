// The native picker and IndexedDB queue stay independent from Streamlit's
// websocket. No credential or authenticated backend URL is exposed here.
const picker = document.getElementById('photo');
const pickerLabel = document.getElementById('pickerLabel');
const send = document.getElementById('send');
const clear = document.getElementById('clear');
const status = document.getElementById('status');
const details = document.getElementById('details');
const progress = document.getElementById('progress');
const preview = document.getElementById('preview');
const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(['image/jpeg','image/png','image/webp','image/gif','image/heic','image/heif']);
let scope = '', pending = null, busy = false, allowed = true, generation = 0;
let acknowledged = false, timer = null, previewUrl = '';

function newId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
}
function post(type, data) {
  window.parent.postMessage({isStreamlitMessage:true, type, ...data}, '*');
}
function resize() { post('streamlit:setFrameHeight', {height:document.body.scrollHeight + 24}); }
function message(text, percent = progress.value) {
  status.textContent = text; progress.value = percent; resize();
}
function showDetails() {
  details.textContent = pending ? `1 foto pronta · ${(pending.size / 1048576).toFixed(2)} MB · ${pending.name}` : '';
}
function controls() {
  picker.disabled = !allowed || busy;
  pickerLabel.classList.toggle('disabled', picker.disabled);
  send.disabled = !allowed || busy || !pending || acknowledged;
  clear.disabled = busy || !pending;
}
function storage(mode, action) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('ddgpilli-pending-photo', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('photos');
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction('photos', mode);
      const op = action(tx.objectStore('photos'));
      tx.oncomplete = () => { db.close(); resolve(op.result); };
      tx.onerror = () => { db.close(); reject(tx.error); };
      tx.onabort = () => { db.close(); reject(tx.error); };
    };
  });
}
function readBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
function validImage(file) {
  const extension = (file.name.split('.').pop() || '').toLowerCase();
  return ALLOWED_TYPES.has((file.type || '').toLowerCase()) || ['jpg','jpeg','png','webp','gif','heic','heif'].includes(extension);
}
function showPreview(blob) {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(blob); preview.src = previewUrl; preview.style.display = 'block'; resize();
}
function hidePreview() {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = ''; preview.removeAttribute('src'); preview.style.display = 'none';
}

picker.addEventListener('change', async () => {
  const file = picker.files[0];
  if (!file) return;
  if (!file.size || file.size > MAX_BYTES || !validImage(file)) {
    message('Formato non valido o foto superiore a 10 MB. La selezione precedente resta disponibile.', 0);
    picker.value = ''; return;
  }
  const current = ++generation, target = scope;
  busy = true; acknowledged = false; controls(); message('Conservo la foto sul telefono…', 15);
  const candidate = {request_id:newId(), name:file.name, type:file.type,
    size:file.size, blob:file, scope:target, saved_at:Date.now()};
  try {
    await storage('readwrite', store => store.put(candidate, target));
    if (current !== generation) return;
    pending = candidate; showDetails(); showPreview(file);
    message('Foto 1 di 1 pronta. Premi Carica la foto.', 25);
  } catch (_) {
    if (current !== generation) return;
    pending = candidate; showDetails(); showPreview(file);
    message('Foto pronta, ma la memoria locale non è disponibile. Premi Carica senza chiudere la pagina.', 25);
  } finally {
    if (current === generation) { busy = false; controls(); }
  }
});

send.addEventListener('click', async () => {
  if (!pending || busy || acknowledged) return;
  busy = true; controls(); message('Foto 1 di 1 · preparazione…', 40);
  try {
    const data = await readBase64(pending.blob);
    message('Foto 1 di 1 · invio al server…', 70);
    post('streamlit:setComponentValue', {dataType:'json', value:{
      request_id:pending.request_id, attempt_id:newId(), name:pending.name,
      type:pending.type, size:pending.size, data, scope:pending.scope
    }});
    clearTimeout(timer);
    timer = setTimeout(() => {
      busy = false; controls();
      message('Conferma non ricevuta. La foto è ancora disponibile: premi Riprova.', 70);
      send.textContent = 'Riprova caricamento';
    }, 20000);
  } catch (_) {
    busy = false; controls(); message('Lettura non riuscita. La foto resta disponibile per un nuovo tentativo.', 25);
    send.textContent = 'Riprova caricamento';
  }
});

clear.addEventListener('click', async () => {
  const target = scope;
  ++generation; pending = null; acknowledged = false; picker.value = ''; clearTimeout(timer);
  hidePreview(); showDetails(); progress.value = 0; send.textContent = '2. Carica la foto'; controls();
  try { await storage('readwrite', store => store.delete(target)); } catch (_) {}
  message('Selezione locale rimossa. La foto già ricevuta dalla web app resta invariata.', 0);
});

window.addEventListener('message', async event => {
  if (event.source !== window.parent || event.data?.type !== 'streamlit:render') return;
  const args = event.data.args;
  allowed = !args.disabled;
  if (scope !== args.scope) {
    scope = args.scope;
    const current = ++generation, target = scope;
    clearTimeout(timer); pending = null; acknowledged = false; busy = false; picker.value = '';
    hidePreview(); showDetails(); progress.value = 0; send.textContent = '2. Carica la foto'; controls();
    try {
      const stored = await storage('readonly', store => store.get(target));
      if (current !== generation || !stored) return;
      if (!stored.request_id || !stored.blob || !stored.size || stored.scope !== target) {
        try { await storage('readwrite', store => store.delete(target)); } catch (_) {}
        return;
      }
      pending = stored; showDetails(); showPreview(stored.blob);
      message('Foto 1 di 1 recuperata dal telefono. Premi Carica la foto.', 25);
    } catch (_) {}
  }
  if (pending && args.ack === pending.request_id) {
    clearTimeout(timer); busy = false; acknowledged = true; send.textContent = 'Foto caricata';
    try { await storage('readwrite', store => store.delete(scope)); } catch (_) {}
    message('Foto 1 di 1 ricevuta dalla web app. Ora puoi salvare o pubblicare la dedica.', 100);
  } else if (pending && args.error?.request_id === pending.request_id) {
    clearTimeout(timer); busy = false; acknowledged = false; send.textContent = 'Riprova caricamento';
    message(args.error.message + ' La foto resta disponibile.', 25);
  }
  controls();
});

post('streamlit:componentReady', {apiVersion:1});
post('streamlit:setFrameHeight', {height:310});
