# Aqara BLE

Autonomous control of Aqara Bluetooth Low Energy locks from Python — no app, no
phone — reconstructed by reverse-engineering the official application's observed
behaviour. The **U200** is the fully solved reference device.

## Goals

- Document the Aqara BLE + cloud protocol precisely enough to reproduce it.
- Provide a cross-platform Python library that exposes the lock's full operation
  surface.
- Enable a native Home Assistant integration (the primary target).
- Make porting to other Aqara-family devices a methodical, repeatable process.

## Start here

- **[docs/](docs/README.md)** — the documentation entry point (understand · port ·
  diagnose).
- **[docs/architecture.md](docs/architecture.md)** — how it works end to end and
  the transversal-vs-device Layer Map.
- **[docs/porting-guide.md](docs/porting-guide.md)** — the numbered process to
  bring a new device online, with the CRC and login obstacles solved up front.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Spec-Driven Development workflow and the
  secret-hygiene rules.

## Secrets — non-negotiable

No real secret, capture, or app source ever enters this repository. Credentials
and device identifiers live only in a local, git-ignored `.env` (see
[`.env.example`](.env.example)); raw captures live under a git-ignored `captures/`
tree. See Constitution Principle I in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## License

See [LICENSE](LICENSE).
