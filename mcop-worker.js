// mcop-worker.js — Web Worker for Monte Carlo Options Pricing
// Loaded by mcop-demo.html via new Worker('./mcop-worker.js')
// No init/ready handshake needed — pure JS, no Pyodide startup delay

importScripts('./mcop-project/mcop.js');

self.onmessage = function (e) {
  const { type, params } = e.data;
  if (type === 'simulate') {
    try {
      const result = runSimulation(params);
      self.postMessage({ type: 'result', result });
    } catch (err) {
      self.postMessage({ type: 'error', msg: String(err) });
    }
  }
};
