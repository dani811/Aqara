# Tasks: Ventana de escucha post-comando

- [X] T001 `session.py`: params `listen_after`/`on_report` en wrapper e interno; report_queue en on_report_notify; loop de escucha tras la primera respuesta (ff62 descifrado + ff64/ff92 crudo).
- [X] T002 `client.py`: `U200Client.listen(seconds)` (keepalive no-actuante + ventana, colecta (channel,hex)).
- [X] T003 `cli.py`: `aqara listen --seconds N` imprime los frames (o "nada").
- [X] T004 Tests: reenvío por ff64/ff92 (fake extra_reports); `listen_after=0` no reenvía; sin callback no rompe; firma compat actualizada; dispatch CLI.
- [X] T005 Docs/CHANGELOG 0.9.0; `pytest`/`ruff`/`mypy` verdes; merge `--no-ff`.
