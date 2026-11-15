# Заметки для разработки

Правила плагина живут в `skills/_shared/accuracy-rules.md` — их читают скиллы.
`CLAUDE.md` в корне плагина Claude Code не загружает (предупреждение `claude plugin validate`), поэтому его здесь нет.

Проверки перед коммитом:

```bash
python -m unittest discover -s core/tests
claude plugin validate .
```

Ядро запускается без внешних пакетов: `python core/predict.py --help`.
