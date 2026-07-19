# 🤖 JARVIS-2.0-BUILD-GUIDE.md
## The Telegram Voice Assistant — Intent, Orchestration & Everything Still Missing

*Built from the Mia/JARVIS n8n walkthrough (video transcript + workflow screenshots), adapted to the Scion stack. The importable workflow is `jarvis-2.0-n8n-workflow.json` — structure validated (19 nodes, 0 errors).*

---

## The architecture

```
Telegram Trigger (message)
   └─ Switch: audio / text / error
        ├─ audio → Get Voice File → Speech-to-Text (Whisper) ─┐
        └─ text ─────────────────────────────────────────────┤
                                                   Normalize → {text, chatId}
                                                        │
                                            ┌─ JARVIS SUPERVISOR (Tools Agent) ─┐
                                            │  Claude Sonnet · Window Memory(10) │
                                            │  read_gmail · send_gmail           │
                                            │  get_calendar · set_calendar       │
                                            │  calculator · web_search           │
                                            └────────────┬───────────────────────┘
                              ┌──────────────────────────┴──────────────────┐
                    Send Text Reply                              Personality Chain
                    (facts → Telegram)                     (Claude Haiku, JARVIS wit)
                                                                     │
                                                          ElevenLabs TTS (HTTP)
                                                                     │
                                                          Send Voice Reply (audio)
```

The signature move: **the supervisor's factual output ships as text immediately**, while a second, cheaper model reads that same output and generates only a 1–2 sentence spoken quip that explicitly does NOT repeat the facts. Text carries information; voice carries character.

## Adaptations vs the video

| Video | Yours | Why |
|-------|-------|-----|
| OpenAI chat model | Claude Sonnet (supervisor) + Claude Haiku (personality) | Anthropic-first; Haiku keeps the quip fast/cheap |
| Airtable contacts/tasks | Gmail + Google Calendar tools | Those credentials already exist |
| Ad-hoc persona prompt | SOUL.md doctrine baked into both prompts | Constitution-governed; markets describe-only |
| No send guardrails | Explicit-intent gates on send_gmail / set_calendar | AGENTS.md approval-gate discipline, in-prompt |

## Setup sequence

### 0. Wake n8n
Log into n8n.cloud → confirm `sciontut.n8n.cloud` is running → `https://sciontut.n8n.cloud/healthz` must answer. Trial expired? Resume a plan or self-host (`docker run -it --rm -p 5678:5678 n8nio/n8n`).

### 1. Telegram bot (5 min)
Message **@BotFather** → `/newbot` → name it → copy token → n8n Credentials → new **Telegram API** credential → paste. Send the bot one "hi".

### 2. Remaining credentials
| Credential | Used by | Notes |
|-----------|---------|-------|
| Anthropic API | both Claude model nodes | console.anthropic.com |
| OpenAI API | Speech-to-Text node | Whisper for Telegram voice notes |
| Google OAuth2 (Gmail) | read_gmail, send_gmail | n8n guides OAuth |
| Google OAuth2 (Calendar) | get_calendar, set_calendar | same flow |
| SerpAPI | web_search | free tier fine |
| ElevenLabs (HTTP custom auth) | ElevenLabs TTS | header `xi-api-key: <key>` as custom-auth credential |

### 3. Import
Workflows → **Import from File** → `jarvis-2.0-n8n-workflow.json` → attach credentials → in **ElevenLabs TTS**, replace `YOUR_VOICE_ID` with a voice ID from your ElevenLabs library.

### 4. The `$fromAI()` wiring (already done — don't break it)
Every tool parameter uses `$fromAI('name', 'description', 'type')` — the supervisor fills these dynamically at runtime. Adding tools later: follow the same pattern; sharp `toolDescription`s are the router's eyes.

### 5. Test sequence
1. Text: "What's on my calendar tomorrow?" → text reply + voice note that does NOT repeat the events
2. Voice note: "Hey JARVIS, any unread emails this week?" → full audio branch
3. Web: "Weather in San Francisco — umbrella?" → web_search
4. Math: "12 fixtures at $85/day for 3 weeks?" → calculator
5. Guardrail: "Email John the quote" without John's address → supervisor should ASK, not invent
6. Flip **Active** — JARVIS is always-on

## Construction impact

| Subsystem | Was | Becomes |
|-----------|-----|--------|
| Channel trigger (Telegram) | 10% | 90% on activation |
| Intent router / supervisor | 35% | 80% |
| Email agent | 25% | 70% — read free, send gated |
| Calendar agent | 25% | 70% |
| Orchestration (n8n) | 15% | 85% once instance wakes |

Overall: ~55% → **~75%**. Remaining to 2.0: vault/memory tool inside n8n, contact + expense agents, wake-word on the local loop.

## Growth notes

- **Sub-workflow pattern:** when tools multiply, split domains into separate workflows called via the workflow tool — the multi-agent ecosystem from the infographic.
- **Voice swap:** the ElevenLabs node is just HTTP — when the DGX Spark hosts Kokoro behind FastAPI, point this node at your own endpoint and the cloud voice becomes sovereign too.
- **Email channel variant:** same graph, email trigger — a straight line to a Blue Shadow Studios client-facing assistant.

*Filed under Learning Bridge R&D · the delegation layer takes shape.*
