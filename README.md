# SubLedger

A simplified, production-grade SaaS Billing & Subscription Backend built with Django REST Framework (DRF) and PostgreSQL.

## Features & Architecture
- **Plans & Subscriptions Management**: Flexible billing cycles, active status validation, duplicate prevention.
- **Invoicing & Ledger**: Plan-price snapshotting at invoice generation, immutable append-only ledger entries.
- **Payment Processing**: Balance verification to prevent overpayments, status tracking (paid, partially paid, failed).
- **Dockerized PostgreSQL**: Containerized database setup with isolated persistent storage.

## Tech Stack
- **Framework**: Django & Django REST Framework (DRF)
- **Database**: PostgreSQL 16 (via Docker)
- **Package Manager**: `uv`

## Quickstart

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ajuzxx/SubLedger.git
   cd SubLedger
   ```

2. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```

3. **Start PostgreSQL with Docker:**
   ```bash
   docker compose up -d
   ```

4. **Install dependencies with `uv`:**
   ```bash
   uv sync
   ```

5. **Run Migrations:**
   ```bash
   uv run python manage.py migrate
   ```

6. **Start the Development Server:**
   ```bash
   uv run python manage.py runserver
   ```
