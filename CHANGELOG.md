# Changelog

## 0.2.0-beta.7 — 29 October 2026

- Add built-in audio compatibility on Play for exact verified game, FMOD and Wine
  runtime versions. The fix targets crackling and repeated/overlapping dialogue,
  with recoverable pauses when audio production falls behind.
- Preserve unsupported installations and third-party audio mods. Managed changes
  are scoped to Dragon Age, receipt-backed and reversible; interrupted changes
  can be reconciled without replacing game executables, saves or shared audio
  settings.
- Add optional Dragon Age-only **4 GB memory support**, independently of the
  automatic audio fix.
- Document local audio status metadata, conflict handling and validation limits.
- Simplify the main window by removing the 4 GB explanatory subtitle and routine
  successful game-launch message, while retaining errors and setup guidance.

The production audio component and 4 GB support have been tested together on the
M5 Pro MacBook. The user confirmed gameplay and a successful save reload after
restarting, with controls and sound working. The main session's final component
status remained active after about 11 minutes of process uptime, with four
pauses and four resumptions and no permanent cutoff.

A brief audio issue still occurred and cleared itself; its exact timing and
cause are unknown. M1 Air validation remains pending. These results do not claim
that all audio problems are resolved.
