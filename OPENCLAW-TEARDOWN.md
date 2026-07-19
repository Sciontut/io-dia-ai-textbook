# 🦞 OPENCLAW-TEARDOWN.md
## Architecture Harvest — `openclaw/openclaw` → JARVIS / Learning Bridge

*Source: shallow clone @ 2026-07-18 · 472MB monorepo · docs read: architecture, agent-workspace, memory, agent-loop, soul, standing-orders, heartbeat, skills/obsidian*

The single biggest takeaway: **OpenClaw's "OS" is mostly markdown files plus one long-lived process.** The magic is disciplined file conventions + a gateway loop.

---

## 1. The Gateway — one daemon to rule everything

- **Exactly one Gateway per host** — a single control plane (WS on 127.0.0.1:18789) owns all state: channels, clients, nodes, canvas.
- **First frame must be `connect`** — anything else is a hard close. Strict handshakes everywhere.
- **Typed frames**: `{type:"req"|"res"|"event"}` validated against JSON Schema.
- **Idempotency keys required on side-effecting methods** with a dedupe cache — safe retries by construction.
- **Events are never replayed** — clients refresh on gaps. Massively simplifies the server.
- **Device pairing with signed challenge nonces** — non-local connects need explicit approval.
- The Gateway serves an **agent-editable Canvas** directory — how agent-driven live dashboards work.

**→ Learning Bridge mapping:** the Phase 3 FastAPI backend should be this shape. Mission Control is already the "web admin client."

## 2. The Workspace — "treat it as memory"

File contract injected into every session: AGENTS.md (operating instructions + standing orders) · SOUL.md (persona) · USER.md · IDENTITY.md · TOOLS.md · HEARTBEAT.md · BOOT.md · MEMORY.md (curated long-term) · memory/YYYY-MM-DD.md (daily working layer) · skills/ · canvas/.

Key doctrine:
- *"The model only remembers what gets saved to disk; there is no hidden state."*
- MEMORY.md stays compact (bootstrap budget ~20k chars/file, 60k total; truncated at injection if over).
- Only load MEMORY.md in private main sessions, never shared contexts.
- **Memory flush before compaction**: a silent turn saves important context to files before summarization.
- **Dreaming** (opt-in): scheduled scoring pass promotes qualified daily-note items into MEMORY.md with a DREAMS.md audit trail for human review.

## 3. The Agent Loop — serialize everything

RPC accepted (returns runId immediately) → per-session queue + optional global lane → workspace + bootstrap files injected → file-based session write lock → three streams (assistant / tool / lifecycle) → SQLite transcript, timeout enforced.

Hook system: `before_prompt_build`, `before_tool_call` (can block), `after_tool_call`, `tool_result_persist`, `session_start/end` — guardrails, audit, injection defense without touching core logic.

## 4. SOUL.md doctrine

Persona file carries real weight because it's injected every session. Short beats long, sharp beats vague, no corporate rules, no "Great question!" openers, opinions required. Treated like code: iterated, pinned, evaluated.

## 5. Standing Orders — the autonomy pattern

Each program grants scoped authority: **Authority · Trigger · Approval gate · Escalation · What-NOT-to-do**. Standing orders define WHAT is authorized; cron defines WHEN; escalation defines WHERE autonomy ends. Memory records approval context but never enforces — enforcement lives in config/sandboxing.

**→ Technodrome's constitutional constraint ("describe market state only, never advise or execute") is a standing order with a hard scope boundary — the same pattern generalized.**

## 6. Security posture

- Inbound DMs = **untrusted input**, always.
- Workspace is default cwd, NOT a sandbox — real sandboxing available when isolation matters.
- Remote access: Tailscale first, SSH tunnel second, raw exposure never without the runbook.
- Secrets never in the workspace repo; workspace itself in a **private** git repo as memory backup.
- `openclaw doctor` — self-diagnostic surfacing risky config. Build a `jarvis doctor` early.

## 7. Bonus finds

- They ship an **Obsidian skill** using the official `obsidian` CLI (Obsidian 1.12.7+, Settings → General → Command line interface) — a second bridge path beside the REST API.
- Memory backends pluggable: builtin SQLite hybrid search → QMD → LanceDB → Honcho. The pgvector plan sits on this maturity curve.
- `memory-wiki` plugin: provenance-rich knowledge layer with claims, contradiction tracking, Obsidian-friendly workflows.
- Importers exist for `~/.claude/projects/*/memory` — the ecosystems interoperate.

## 8. Build order implied

1. **Files only, zero code:** AGENTS.md + USER.md + IDENTITY.md beside MEMORY.md/SOUL.md. ✅ DONE — ratified in the vault 2026-07-18.
2. FastAPI WS gateway skeleton — connect handshake, req/res/event frames, one `agent` method with bootstrap injection.
3. Per-session queue + SQLite transcripts + three streams wired to Mission Control's Chat/Feed/Logs tabs.
4. Hooks, memory flush, scheduled dreaming over the vault, standing-order cron programs → Discord delivery.
5. Always: workspace in private git; secrets outside it; Tailscale for anything remote.

*Harvested by JARVIS · filed under Learning Bridge R&D · Blue Shadow Studios*
