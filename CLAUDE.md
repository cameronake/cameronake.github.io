# Portfolio — CLAUDE.md

Personal portfolio website for Cameron Ake (HMC sophomore, CS/Math joint major), targeting SWE and data science internships.

---

## Planning & Timeline

- Summer 2026 internship: ~10 weeks starting late May 2026
- Available for portfolio work: ~1–2 hours/day alongside the internship
- **Goal: 5 projects live by end of summer**
- Interest areas for new projects: AI engineering, machine learning, Bayesian reasoning, finance, LLMs/Claude API, MCMC — open to anything in these neighborhoods

---

## Project Inventory

| Project | Status | Demo page | Skills highlighted |
|---------|--------|-----------|-------------------|
| Ticket to Ride GA (`ttr-project/`) | Complete | `ttr-demo.html` | Genetic algorithms, Python, game simulation, AI/search, Pyodide/JS |
| Bayesian Optimization (`bo-project/`) | Next up | `bo-demo.html` | GP regression, Bayesian inference, MCMC-adjacent, NumPy, interactive viz |
| Neural Networks from Scratch | Card only (no demo) | — | Backpropagation, pure Python, MNIST |
| ARF random forest (`arf-project/`) | Low priority / likely drop | None | ML fundamentals, from-scratch impl |
| Project 5 | TBD | TBD | TBD |

ARF covers skills already shown by TTR; preference is to build new projects rather than invest further in ARF.

See `ttr-project/CLAUDE.md` for TTR implementation details.
See `bo-project/CLAUDE.md` for Bayesian Optimization math, demo structure, and technical approach.

---

## File Structure

```
Portfolio/
├── index.html              # Main landing page
├── styles.css              # Shared stylesheet
├── ttr-demo.html           # TTR live demo (5-tab layout)
├── data/                   # Pre-computed JS data files for ttr-demo.html
│   ├── greedy4.js / greedy40.js / linear40.js / quad40.js / elite40.js
│   └── compare.js
├── assets/
│   ├── cameron-ake-resume.pdf
│   └── cameron-ake-transcript.pdf
├── ttr-project/            # TTR source + bot run data
│   ├── CLAUDE.md           # TTR implementation notes (detailed)
│   └── Code/               # Python GA source (TTR.py, HeuristicPlayer.py, …)
└── arf-project/            # Random forest / decision tree (low priority)
```

---

## Design Principles

- **Clean and minimal** — no heavy frameworks, no cluttered layouts
- Internship-audience-first: readable, professional, technical depth without being overwhelming
- `styles.css` is shared across all pages; keep it consistent

---

## Hosting

- Target: **GitHub Pages** (static, free)
- No backend server — all interactivity must be client-side (Pyodide, vanilla JS, lightweight JS libs)
- PDF assets (resume, transcript) served as static files
