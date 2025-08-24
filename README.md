# ClearKeep Church Backend (CKChurch1)

This is the backend foundation of **ClearKeep Church (CKChurch)** — a modern, modular financial management and service-tracking system built for parish offices.

Powered by **FastAPI**, **PostgreSQL**, and **Alembic**, this backend currently supports:

---

## ✅ Core Features

### 🎯 Transactions
- Tracks income and expenses
- Supports payment methods (cash, gcash, check, bank, other)
- Optional `reference_no` field for receipts, GCash refs, etc.

### 🗂️ Categories
- Link transactions to custom categories (e.g., Sacraments, Utilities, Donations)

### 👤 Parishioners
- Masterlist of people associated with transactions (e.g., for sacraments, donations)
- Linked to transactions via `parishioner_id`

---

## 🧱 Tech Stack

- **FastAPI** – Modern, async Python web framework
- **SQLAlchemy** – ORM for relational database mapping
- **Alembic** – Database migrations and schema versioning
- **PostgreSQL** – Dockerized database
- **Uvicorn** – ASGI server
- **Pydantic** – Schema validation

---

## 📁 Directory Structure

```plaintext
backend/
├── app/
│   ├── api/            # FastAPI routers
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic DTOs
│   ├── services/       # DB logic
│   └── main.py         # FastAPI entrypoint
├── alembic/            # Migrations
├── alembic.ini         # Alembic config
├── requirements.txt    # Python deps
└── .env                # Database URL
