# ClearKeep — Working Agreement (Assistant Process Contract)

**Purpose:** Make every change safe, auditable, and consistent.

## Hard Gates (every message)
1) **Single-Step Lock** — Exactly *one actionable step* per message.
2) **Read-First Gate (for code)** — Assistant fetches files and shows tiny unique **anchors with citations** before any patch. **No anchor = no patch.**
3) **Accept/Block Gate** — Assistant waits for **“next”** or **“blocked: …”** before proceeding.
4) **One-File Rule** — Patches change **one file only** (full copy-paste); new files are allowed when needed.
5) **Acceptance Check** — Each step includes a short success check.
6) **Canonicals** — Paths under `C:\ckchurch1`; timezone **Asia/Manila**; prefer provided launcher scripts; no env/driver changes when services already run.
7) **Continuity Guard** — If files can’t be fetched or anchors don’t match, Assistant **halts** and requests a fresh sync (no guessing).
8) **STATUS.md** — Treated as source-of-truth for head/version.

## Message Header (appears on every actionable reply)
