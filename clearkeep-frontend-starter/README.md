# ClearKeep Frontend Starter (Next.js + Tailwind)

A minimal starter UI to exercise the backend flows:
- Parishioner creation
- Sacrament creation (auto-links Transactions & Calendar)
- Lists for Transactions and Calendar events

## Quick start
```bash
# from this folder
cp .env.local.example .env.local
# (edit NEXT_PUBLIC_API_BASE if your backend isn't at 127.0.0.1:8000)
npm i
npm run dev
# open http://localhost:3000
```

## Structure
- `app/` — Next.js App Router
- `components/Nav.tsx` — top navigation
- `lib/api.ts` — tiny fetch helpers wired to `NEXT_PUBLIC_API_BASE`
- `lib/types.ts` — API types used by the views
- `styles/globals.css` — Tailwind base

> This is a modest starter you can grow. Add auth, routing guards, design system, etc.
