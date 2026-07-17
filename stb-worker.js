// Pyodide Web Worker for the Systematic Trading Backtester.
// Mirrors bo-worker.js: load the runtime + packages, fetch the Python modules
// into the VFS, then service compute requests off the main thread.
//
// The price panel is loaded once via importScripts (data/prices.js defines the
// DATA_PRICES global) and handed to Python as JSON, so it is never re-shipped
// per request. Heavy jobs (walk-forward, sweeps) stream progress messages.

importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js');

let pyodide = null;

async function initPyodide() {
  self.postMessage({ type: 'status', msg: 'Loading Python runtime…' });
  pyodide = await loadPyodide();

  // The engine is pure NumPy (pandas is only used offline in fetch_data.py),
  // so we load just NumPy — markedly faster cold-start than pulling pandas too.
  self.postMessage({ type: 'status', msg: 'Loading NumPy…' });
  await pyodide.loadPackage('numpy');

  self.postMessage({ type: 'status', msg: 'Loading backtester modules…' });
  const [statsCode, btCode] = await Promise.all([
    fetch('./stb-project/stats.py', { cache: 'no-cache' }).then(r => r.text()),
    fetch('./stb-project/backtester.py', { cache: 'no-cache' }).then(r => r.text()),
  ]);
  pyodide.FS.writeFile('/stats.py', statsCode);
  pyodide.FS.writeFile('/backtester.py', btCode);
  await pyodide.runPythonAsync('import sys; sys.path.insert(0, "/"); import stats, backtester');

  self.postMessage({ type: 'status', msg: 'Loading market data…' });
  importScripts('./data/prices.js'); // defines DATA_PRICES
  pyodide.globals.set('_panel_json', JSON.stringify(DATA_PRICES));
  await pyodide.runPythonAsync(
    'import json as _json; backtester.set_panel(_json.loads(_panel_json))'
  );

  // Progress bridge: Python orchestrators call this from their loops.
  pyodide.globals.set('_progress', (done, total, phase) =>
    self.postMessage({ type: 'progress', done, total, phase })
  );

  // Hand the page some metadata for populating selectors (in case it wants it).
  const meta = {
    tickers: DATA_PRICES.tickers,
    pairs: DATA_PRICES.pairs,
    meta: DATA_PRICES.meta,
    dates: [DATA_PRICES.dates[0], DATA_PRICES.dates[DATA_PRICES.dates.length - 1]],
  };
  self.postMessage({ type: 'ready', meta });
}

// Run a Python orchestrator that takes a spec dict and returns a JSON string.
async function runSpec(pyFunc, spec, withProgress) {
  pyodide.globals.set('_spec_json', JSON.stringify(spec));
  const call = withProgress
    ? `backtester.${pyFunc}(_spec, progress=_progress)`
    : `backtester.${pyFunc}(_spec)`;
  const resultJson = await pyodide.runPythonAsync(`
import json as _json
_spec = _json.loads(_spec_json)
_json.dumps(${call})
`);
  return JSON.parse(resultJson);
}

const HANDLERS = {
  run_backtest:     { fn: 'backtest_from_spec',     progress: false, ok: 'backtest_result',     err: 'backtest_error' },
  run_cointegration:{ fn: 'cointegration_from_spec', progress: false, ok: 'cointegration_result', err: 'cointegration_error' },
  run_walkforward:  { fn: 'walkforward_from_spec',  progress: true,  ok: 'walkforward_result',  err: 'walkforward_error' },
  run_sweep:        { fn: 'sweep_from_spec',        progress: true,  ok: 'sweep_result',        err: 'sweep_error' },
};

self.onmessage = async function (e) {
  const { type, data } = e.data;

  if (type === 'init') {
    try {
      await initPyodide();
    } catch (err) {
      self.postMessage({ type: 'error', msg: String(err) });
    }
    return;
  }

  const h = HANDLERS[type];
  if (!h) return;
  try {
    const result = await runSpec(h.fn, data, h.progress);
    self.postMessage({ type: h.ok, result });
  } catch (err) {
    self.postMessage({ type: h.err, msg: String(err) });
  }
};
