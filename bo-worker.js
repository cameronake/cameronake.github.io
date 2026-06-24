importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js');

let pyodide = null;

async function initPyodide() {
  self.postMessage({ type: 'status', msg: 'Loading Python runtime…' });
  pyodide = await loadPyodide();

  self.postMessage({ type: 'status', msg: 'Loading NumPy…' });
  await pyodide.loadPackage('numpy');

  self.postMessage({ type: 'status', msg: 'Loading BO module…' });
  const boCode = await fetch('./bo-project/bo.py', { cache: 'no-cache' }).then(r => r.text());
  pyodide.FS.writeFile('/bo.py', boCode);
  await pyodide.runPythonAsync('import sys; sys.path.insert(0, "/"); import bo');

  self.postMessage({ type: 'ready' });
}

async function runBoStep(data) {
  const { X_train, y_train, X_grid, length_scale, signal_var, noise_var,
          acq_type, kappa, xi } = data;

  pyodide.globals.set('_X_train',      pyodide.toPy(X_train));
  pyodide.globals.set('_y_train',      pyodide.toPy(y_train));
  pyodide.globals.set('_X_grid',       pyodide.toPy(X_grid));
  pyodide.globals.set('_length_scale', length_scale);
  pyodide.globals.set('_signal_var',   signal_var);
  pyodide.globals.set('_noise_var',    noise_var);
  pyodide.globals.set('_acq_type',     acq_type);
  pyodide.globals.set('_kappa',        kappa);
  pyodide.globals.set('_xi',           xi);

  const resultJson = await pyodide.runPythonAsync(`
import json, numpy as np
result = bo.bo_step(
    np.array(_X_train, dtype=float),
    np.array(_y_train, dtype=float),
    np.array(_X_grid,  dtype=float),
    _length_scale, _signal_var, _noise_var,
    _acq_type, _kappa, _xi
)
json.dumps(result)
`);

  return JSON.parse(resultJson);
}

self.onmessage = async function(e) {
  const { type, data } = e.data;

  if (type === 'init') {
    try {
      await initPyodide();
    } catch (err) {
      self.postMessage({ type: 'error', msg: String(err) });
    }
    return;
  }

  if (type === 'bo_step') {
    try {
      const result = await runBoStep(data);
      self.postMessage({ type: 'bo_result', result });
    } catch (err) {
      self.postMessage({ type: 'bo_error', msg: String(err) });
    }
  }
};
