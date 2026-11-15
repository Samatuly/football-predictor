# Development notes

The plugin rules live in `skills/_shared/accuracy-rules.md`; the skills read them.
Claude Code does not load a root-level `CLAUDE.md` from a plugin (`claude plugin validate` warns about it), so there is none here.

Checks before committing:

```bash
python -m unittest discover -s core/tests
claude plugin validate .
```

The `elo_poisson` core runs without external packages: `python core/predict.py --help`. The default `dixon_coles` model needs `numpy`.
