# Examples

Runnable, **dev-only** helpers and scripts. These are **not** part of the
`aqara_u200_ble` library API — the library never reads the environment, prompts,
or persists secrets. In production (e.g. Home Assistant) the consumer injects
credentials from its own secure storage and constructs a `CloudAuthManager`
directly.

| File | What it does |
| --- | --- |
| [`auth_from_env.py`](auth_from_env.py) | Build a `CloudAuthManager` from environment variables (a `.env` convenience for local runs). |
| [`real_lock_unlock.py`](real_lock_unlock.py) | End-to-end lock/unlock against a real U200 using your own `.env` credentials. |
| [`run_real_lock_unlock.py`](run_real_lock_unlock.py) | Runner variant driving the flow over a Bumble/HCI transport. |

> Secrets policy: credentials live only in a local, git-ignored `.env`. Never
> commit real values (Constitution Principle I).
