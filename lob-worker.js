// lob-worker.js — Web Worker hosting the WASM matching engine.
//
// Mirrors the message protocol of the Pyodide workers (bo-worker.js), but the
// runtime is the C++ engine compiled to WebAssembly (lob.js / lob.wasm, built
// offline by lob-project/build_wasm.sh) instead of Python.
//
// If lob.js is not present (WASM not built yet), importScripts throws at load
// and the page's worker.onerror falls back to animating DATA_LOB_REPLAY.
//
// Protocol
//   main -> worker: {type:'init'}
//                   {type:'submit', data:{side,price,qty}}
//                   {type:'market', data:{side,qty}}
//                   {type:'cancel', data:{id}}
//                   {type:'step',   data:{n}}
//                   {type:'reset'}
//   worker -> main: {type:'status', msg}
//                   {type:'ready'}
//                   {type:'error',  msg}
//                   {type:'snapshot', result}   // parsed book snapshot

importScripts('./lob.js');   // defines LOBModule (MODULARIZE + EXPORT_NAME)

const MAX_PRICE = 20000;     // ladder bound (ticks); mid ~ 10000 -> ~$100.00
const POOL_CAP  = 200000;
const DEPTH     = 12;        // levels per side in each snapshot

let Module = null;
let api = null;

async function initWasm() {
  self.postMessage({ type: 'status', msg: 'Loading C++ engine (WebAssembly)…' });
  Module = await LOBModule();

  api = {
    reset:    Module.cwrap('lob_reset',        null,     ['number', 'number']),
    submit:   Module.cwrap('lob_submit_limit', 'number', ['number', 'number', 'number']),
    market:   Module.cwrap('lob_market',       null,     ['number', 'number']),
    cancel:   Module.cwrap('lob_cancel',       null,     ['number']),
    step:     Module.cwrap('lob_step_feed',    'number', ['number']),
    snapshot: Module.cwrap('lob_snapshot',     'string', ['number']),
  };

  api.reset(MAX_PRICE, POOL_CAP);
  api.step(400);   // pre-fill so the book opens with realistic depth

  self.postMessage({ type: 'ready' });
  postSnapshot();
}

function postSnapshot() {
  self.postMessage({ type: 'snapshot', result: JSON.parse(api.snapshot(DEPTH)) });
}

self.onmessage = async function (e) {
  const { type, data } = e.data;
  try {
    if (type === 'init') { await initWasm(); return; }
    if (!api) return;

    switch (type) {
      case 'submit': api.submit(data.side, data.price, data.qty); break;
      case 'market': api.market(data.side, data.qty);             break;
      case 'cancel': api.cancel(data.id);                         break;
      case 'step':   api.step(data.n || 1);                       break;
      case 'reset':  api.reset(MAX_PRICE, POOL_CAP); api.step(400); break;
      default: return;
    }
    postSnapshot();
  } catch (err) {
    self.postMessage({ type: 'error', msg: String(err) });
  }
};
