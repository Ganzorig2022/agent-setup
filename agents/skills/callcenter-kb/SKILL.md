---
name: callcenter-kb
description: Knowledge-base subsystem of the callcenter project (/Users/dev/QPay/callcenter) — the intent/canonical data model and why variant answers are never served, the DATABASE_URL-beats-DB_* config trap that starved the sandbox KB, pre-rendered TTS audio and its PVC topology, ElevenLabs scoped-key behaviour, and how to verify a CSV export against the live DB. Load before touching kb_entries, the restore/audio/embedding scripts, retrieval ranking, or deploying KB audio.
---

# Callcenter Knowledge Base

Scope: `/Users/dev/QPay/callcenter` (FastAPI + async SQLAlchemy + Postgres/pgvector, branch
`new-build`). Everything here is verified against the live sandbox DB, not inferred.

## 1. Intent and KB share one table — by design

**There is no `intents` table.** `intent_slug` is a `String(100)` column on `kb_entries`
(`app/models/knowledge_base.py`, migration `alembic/versions/intent_20260415_add_intent_fields.py`).
The canonical CSV export carries an `intent_slug` column too. Anyone claiming intents were
"mixed into" the KB is describing the schema as it has existed since April.

Rows are either **canonical** (one per slug, holds the answer that gets served) or **variants**
(alternate phrasings of the same question). A partial unique index
`uq_kb_entries_canonical_intent_slug` enforces one canonical per slug; variants are unconstrained.

### The consequence that surprises people

`app/repositories/kb_repo.py` → `_resolve_to_canonical_scored`:

- keeps only the **first row per intent_slug** (later hits for the same slug are dropped), and
- replaces any matched variant with its slug's canonical.

So **a variant's own `answer` is never served**. A row with `intent_slug` set and a distinct
answer is unreachable content — retrieval can match it, then discards it and answers with the
canonical instead. Rows with a NULL `intent_slug` are exempt: they serve their own answer.

Practical rule: *an intent is a routing bucket, not an answer key.* If two questions need two
different answers, they need two slugs (or no slug). Filing them as variants under one slug
silently buries one of them. When auditing KB content, count variants whose answer differs from
their canonical — that number is your dead-content count.

## 2. The config trap that starved the sandbox KB

`app/core/config.py` → `Settings._assemble_connection_urls` composes the DSN from `DB_*` **only
when `DATABASE_URL` is falsy**:

```python
if not self.DATABASE_URL:
    self.DATABASE_URL = f"postgresql+asyncpg://{...DB_HOST...}"
```

An explicit `DATABASE_URL` in `.env` therefore wins over every `DB_*` value and silently
redirects every script to a different database. This is exactly how the sandbox KB ended up
holding a fraction of the export for months while all the ingest scripts reported success —
they were writing to local dev.

**Rule for any script in this repo that writes KB data:** resolve the DSN yourself from `DB_*`
(or an explicit `--dsn`), never read `settings.DATABASE_URL`, and log the target redacted
*before* connecting. `scripts/restore_kb_from_export.py` and `scripts/generate_kb_audio.py`
both implement this pattern — copy it rather than re-inventing.

Related: `pydantic-settings` precedence is init > **shell env vars** > `.env` file > defaults.
A stale exported shell var beats the file.

## 3. Pre-rendered TTS audio

`scripts/generate_kb_audio.py` renders ElevenLabs MP3 + ulaw 8kHz mono (via `ffmpeg`) into
`static/kb_audio/` and writes `audio_file` on the row. Asterisk plays it as
`sound:kb_audio/kb_<id>`.

Its query deliberately excludes two classes — **do not widen it**:

- **tool-equipped intents** — `call_handler` checks `kb_audio` *before* tool routing, so a
  pre-rendered clip would play instead of running `check_transaction`/refund/settlement/ticket.
- **`greetings`** — a mid-call "Байна уу?" must reach the contextual LLM path, not replay the
  canned welcome.

After any restore that changes answer text, regenerate: the old clip no longer matches the words.

### Deployment topology — the failure mode

`static/kb_audio` is in **both `.gitignore` and `.dockerignore`**, so generated clips reach
neither git nor the image, while the shared sandbox DB references them by name. The files belong
on the `kb-audio-rwx` PVC (NFS, RWX) — backend mounts it at `/app/static/kb_audio`, Asterisk at
`/var/lib/asterisk/sounds/kb_audio`. See `docs/infrastructure/DEVOPS_WEBTIER.md` §7.

When the file is missing, `call_handler` catches the playback error and falls back to the
`noanswer` sound — a caller hears "no answer" for a question the KB can answer perfectly. The
symptom does not point at audio, so check file presence on the PVC early.

Regenerating in-pod works: the image ships `ffmpeg`, `scripts/`, `elevenlabs`, and `asyncpg`, and
`AUDIO_DIR` resolves to the PVC mountpath. Probe writability first (`id`, `ls -ld`, `touch`) —
NFS ignores `fsGroup`, so the mount can be read-only to uid 1000 in practice.

## 4. ElevenLabs scoped keys

A scoped key 401s on any endpoint outside its permissions. `/v1/user` needs `user_read`, which a
TTS-only key will not have — **a 401 there does not mean the key is dead.** Probe with the
endpoint you actually intend to use (a `--limit 1` TTS canary), not with `/v1/user`.

`elevenlabs_provider.text_to_speech` has no try/except and no fallback provider, so a bad key
takes down live TTS for every call, not just clip generation. Verify the key held by the cluster
Secret separately from the local `.env` one — they drift.

## 5. Verifying a CSV export against the live DB

Key on a **full-row signature** — `(intent_slug, question, answer, is_canonical, is_active,
tools_json, category)` — and compare with `collections.Counter` multisets.

Do **not** match on `(intent_slug, normalized_question)`. This export ships duplicate twin rows:
same slug, same question, same answer, one canonical and one not. Any matcher that picks the
first candidate will pair the wrong twin and report a large phantom `is_canonical` mismatch
count. That false alarm has already cost one investigation.

Also check, because a CSV cannot express them: `embedding`, `audio_file`,
`few_shot_examples`, `persona_override`. Compare counts against the pre-write backup in
`backups/kb/` rather than assuming a restore preserved them.

Embeddings: `embedding_service.generate_for_entry()` embeds the **question only** (the answer
arg is kept for signature compatibility). Carried-over vectors from an older vintage share one
HNSW index with fresh ones — use `--reembed-all` to keep a single vintage.

## 6. Operating constraints

`.env` in this repo is denied to Claude's file tools. Read values through a script using
`dotenv_values()` that prints only masked output; hand any `.env` edit to the user as a `!`
command. Sandbox and cluster writes are the user's to execute — write the script, let them run it.
