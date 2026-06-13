importScripts('https://cdn.jsdelivr.net/pyodide/v0.27.0/full/pyodide.js');

let pyodide = null;

async function initPyodide() {
  self.postMessage({ type: 'status', msg: 'loading python runtime…' });
  pyodide = await loadPyodide();

  self.postMessage({ type: 'status', msg: 'fetching game files…' });
  const noCache = { cache: 'no-cache' };
  const [ttrCode, heuristicCode, randomCode, connectionRoutesText, ticketRoutesText] = await Promise.all([
    fetch('./ttr-project/Code/TTR.py', noCache).then(r => r.text()),
    fetch('./ttr-project/Code/HeuristicPlayer.py', noCache).then(r => r.text()),
    fetch('./ttr-project/Code/RandomPlayer.py', noCache).then(r => r.text()),
    fetch('./ttr-project/Code/txt_storage/newconnectionroutes.txt', noCache).then(r => r.text()),
    fetch('./ttr-project/Code/txt_storage/routes.txt', noCache).then(r => r.text()),
  ]);

  // Write all files to / so TTR.py's relative imports and open() calls resolve correctly
  pyodide.FS.writeFile('/HeuristicPlayer.py', heuristicCode);
  pyodide.FS.writeFile('/RandomPlayer.py', randomCode);
  pyodide.FS.mkdir('/txt_storage');
  pyodide.FS.writeFile('/txt_storage/newconnectionroutes.txt', connectionRoutesText);
  pyodide.FS.writeFile('/txt_storage/routes.txt', ticketRoutesText);

  pyodide.FS.writeFile('/TTR.py', ttrCode);

  self.postMessage({ type: 'status', msg: 'initializing game engine…' });
  await pyodide.runPythonAsync('import os, sys; os.chdir("/"); sys.path.insert(0, "/")');
  await pyodide.runPythonAsync('from TTR import *');

  self.postMessage({ type: 'ready' });
}

async function runGame(botWeights) {
  pyodide.globals.set('_weights_in', pyodide.toPy(botWeights));

  const resultJson = await pyodide.runPythonAsync(`
import json, re

c_deck, t_deck, face_ups, discard = initialize_decks()
_connections, CITIES_local, board = initialize_connections_cities_board()
colors_list = list(NUMCOLORS.keys())
player_colors = ['RED', 'BLUE', 'GREEN', 'YELLOW']

bots = [
    HeuristicPlayer(color, c_deck, t_deck, colors_list, CITIES_local, False, False, list(w))
    for color, w in zip(player_colors, _weights_in)
]

raw = bots_play_game(bots, c_deck, face_ups, t_deck, board, discard)

def parse_tickets(tickets):
    result = []
    if isinstance(tickets, dict):
        for route, achieved in tickets.items():
            a, b = route
            result.append({'route': a + ' → ' + b, 'achieved': bool(achieved)})
    elif isinstance(tickets, str):
        for entry in tickets.split(';'):
            if ':' in entry:
                route_part, ach = entry.rsplit(':', 1)
                cities = re.findall(r"'([^']+)'", route_part)
                if len(cities) == 2:
                    result.append({'route': cities[0] + ' → ' + cities[1], 'achieved': ach.strip() == 'True'})
    return result

output = []
for w, score, has_longest, tickets in raw:
    output.append({
        'weights': [float(x) for x in w],
        'score': int(score),
        'longestRoute': bool(has_longest),
        'tickets': parse_tickets(tickets)
    })

json.dumps(output)
`);

  return JSON.parse(resultJson);
}

async function runBreedCycle(weightsScores, selectionMode, elitePct, learningRate) {
  pyodide.globals.set('_ws_in', pyodide.toPy(weightsScores));
  pyodide.globals.set('_selection_mode', selectionMode);
  pyodide.globals.set('_elite_pct', elitePct);
  pyodide.globals.set('_learning_rate', learningRate);

  const resultJson = await pyodide.runPythonAsync(`
import json

weights_scores_list = [[list(ws['weights']), ws['score']] for ws in _ws_in]
bred = breed_cycle(weights_scores_list, selection_mode=_selection_mode, elite_pct=_elite_pct, lr=_learning_rate)

output = [{'weights': [float(x) for x in b[0]], 'isChild': bool(b[1])} for b in bred]
json.dumps(output)
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

  if (type === 'run_game') {
    try {
      const result = await runGame(data.botWeights);
      self.postMessage({ type: 'game_result', result });
    } catch (err) {
      self.postMessage({ type: 'game_error', msg: String(err) });
    }
  }

  if (type === 'run_breed_cycle') {
    try {
      const result = await runBreedCycle(data.weightsScores, data.selectionMode, data.elitePct, data.learningRate);
      self.postMessage({ type: 'breed_result', result });
    } catch (err) {
      self.postMessage({ type: 'breed_error', msg: String(err) });
    }
  }
};
