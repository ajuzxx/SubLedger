# SubLedger

A production-grade, modular **SaaS Subscription & Billing Backend** built with **Django**, **Django REST Framework (DRF)**, **PostgreSQL**, and **uv**.

[![Repository](https://img.shields.io/badge/GitHub-SubLedger-blue)](https://github.com/ajuzxx/SubLedger)
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-green.svg)](https://www.djangoproject.com/)
[![Tests](https://img.shields.io/badge/Tests-42%20passed-brightgreen.svg)]()

---

## Table of Contents
- [Architecture & Design](#architecture--design)
- [Tech Stack](#tech-stack)
- [Quickstart & Setup](#quickstart--setup)
- [Running with Docker](#running-with-docker)
- [API Reference](#api-reference)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Swagger & OpenAPI Documentation](#swagger--openapi-documentation)
- [Running Automated Tests](#running-automated-tests)
- [Business Rules & Guarantees](#business-rules--guarantees)
- [Assumptions](#assumptions)
- [Limitations](#limitations)

---

## Architecture & Design

SubLedger separates responsibilities across explicit layers to maintain financial accuracy, data integrity, and testability:
1. **Views & ViewSets (`billing/views.py`):** Handle HTTP transport, JWT authentication, and RBAC authorization.
2. **Serializers (`billing/serializers.py`):** Validate input payloads and serialize output objects.
3. **Service Layer (`billing/services/`):** Orchestrates all business transactions, prevents race conditions with pessimistic locking (`select_for_update`), snapshots pricing, and writes ledger entries.
4. **Data Models (`billing/models.py`):** Defines relational schema, constraints, and validators in PostgreSQL.
5. **Append-Only Ledger (`LedgerEntry`):** Ensures an immutable audit log of all financial events.

> For complete Mermaid ERD diagrams, sequence flows, and pattern documentation, see [DESIGN.md](DESIGN.md).

---

## Tech Stack
* **Language & Runtime:** Python 3.13
* **Framework:** Django 6.1 + Django REST Framework (DRF)
* **Database:** PostgreSQL 16
* **Authentication:** JWT (`djangorestframework-simplejwt`)
* **API Documentation:** OpenAPI 3.0 via `drf-spectacular` (Swagger & ReDoc)
* **Package Manager:** `uv`
* **Containerization:** Docker & Docker Compose

---

## Quickstart & Setup

### 1. Prerequisites
* Python 3.13+ installed
* [`uv`](https://docs.astral.sh/uv/) package manager installed
* Docker Desktop installed and running

### 2. Clone the Repository
```bash
git clone https://github.com/ajuzxx/SubLedger.git
cd SubLedger
```

### 3. Configure Environment Variables
Copy the template `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure `.env` matches your environment:
```env
SECRET_KEY=your-secure-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=subledger
DB_USER=subledger_user
DB_PASSWORD=subledger_password
DB_HOST=localhost
DB_PORT=5433
```

### 4. Start PostgreSQL with Docker
```bash
docker compose up -d db
```

### 5. Install Dependencies with `uv`
```bash
uv sync
```

### 6. Run Database Migrations
```bash
uv run python manage.py migrate
```

### 7. Seed User Roles & Groups
```bash
uv run python manage.py setup_roles
```
This automatically registers the three RBAC groups: `Admin`, `Billing Manager`, and `Viewer`.

### 8. Create a Superuser / Test Users
```bash
uv run python manage.py createsuperuser
```

### 9. Start the Development Server
```bash
uv run python manage.py runserver
```
Backend is now running at `http://127.0.0.1:8000/`.

---

## Running with Docker

To build and run the entire stack (PostgreSQL + Django Web App) inside Docker:
```bash
docker compose up --build
```
The Django application will be reachable at `http://localhost:8000/`.

---

## API Reference

### Authentication (JWT)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/token/` | Obtain access & refresh token pair |
| `POST` | `/api/token/refresh/` | Refresh an expired access token |
| `POST` | `/api/token/verify/` | Verify token validity |

### Core Billing Resources
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET`, `POST` | `/api/plans/` | List all plans / Create a new plan |
| `GET`, `PATCH`, `DELETE` | `/api/plans/{id}/` | Retrieve, update, or delete a plan |
| `GET`, `POST` | `/api/customers/` | List customers / Register a new customer |
| `GET`, `PATCH`, `DELETE` | `/api/customers/{id}/`| Retrieve, update, or delete a customer |
| `GET`, `POST` | `/api/subscriptions/` | List subscriptions / Create subscription |
| `GET`, `PATCH`, `DELETE` | `/api/subscriptions/{id}/`| Retrieve, update, or cancel a subscription |
| `GET`, `POST` | `/api/invoices/` | List invoices / Generate a new invoice |
| `GET`, `PATCH` | `/api/invoices/{id}/` | Retrieve invoice details |
| `GET`, `POST` | `/api/payments/` | List payments / Process a payment attempt |
| `GET` | `/api/payments/{id}/` | Retrieve payment attempt details |

---

## Role-Based Access Control (RBAC)

SubLedger enforces role-based authorization via `BillingRolePermission`:

| Role | Read (GET) | Create (POST) | Update (PUT/PATCH) | Delete (DELETE) |
| :--- | :---: | :---: | :---: | :---: |
| **Admin** | ✅ | ✅ | ✅ | ✅ |
| **Billing Manager** | ✅ | ✅ | ✅ | ❌ (403 Forbidden) |
| **Viewer** | ✅ | ❌ (403) | ❌ (403) | ❌ (403 Forbidden) |
| **Anonymous (Unauthenticated)** | ❌ (401) | ❌ (401) | ❌ (401) | ❌ (401 Unauthorized) |

---

## Swagger & OpenAPI Documentation

Interactive API documentation is automatically generated via OpenAPI 3.0:
* **Swagger UI:** [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)
* **ReDoc UI:** [http://127.0.0.1:8000/api/redoc/](http://127.0.0.1:8000/api/redoc/)
* **OpenAPI Raw Schema:** [http://127.0.0.1:8000/api/schema/](http://127.0.0.1:8000/api/schema/)

---

## Running Automated Tests

SubLedger includes a comprehensive test suite (42 automated tests) covering services, API endpoints, and RBAC security:

```bash
uv run python manage.py test billing
```

Test coverage includes:
* **Service Unit Tests:** Inactive plan rejection, duplicate subscription prevention, price snapshotting, overpayment prevention, partial vs full payment status transitions.
* **Role-Based Permission Tests:** Verification that Admins, Managers, Viewers, and Anonymous clients receive correct status codes (`200`, `201`, `204`, `401`, `403`).
* **API Integration Tests:** End-to-end payload validation, database mutations, and ledger entry creation.

---

## Business Rules & Guarantees

1. **Price Integrity:** Plan `price` must be greater than or equal to $0.01$.
2. **Subscription Isolation:** A customer cannot hold two active subscriptions to the same plan simultaneously.
3. **Price Snapshotting:** Invoices snapshot the plan's current price at generation time; future plan price adjustments do not alter already issued invoices.
4. **Billing Period Uniqueness:** An invoice cannot be generated twice for the same subscription and billing period.
5. **Overpayment Prevention:** Payments exceeding the remaining invoice balance (`amount_due - amount_paid`) are rejected with `HTTP 400`.
6. **Concurrency Safety:** Invoice payments utilize pessimistic database locks (`select_for_update`) to prevent race conditions from concurrent payment attempts.
7. **Append-Only Ledger:** Financial entries (`invoice_created`, `payment_success`, `payment_failure`) are immutable records that are never modified or deleted.

---

## Assumptions

1. **Single Currency per Invoice:** Payment currency must strictly match the invoice currency (no automatic runtime foreign exchange conversion).
2. **Single Active Subscription per Plan:** A customer can subscribe to multiple distinct plans, but cannot have more than one active subscription for the same plan.
3. **Idempotent Payment Provider References:** Each external payment attempt provider reference (e.g. Stripe charge ID) is unique and cannot be reused.
4. **Synchronous Payment Processing:** Payment attempts are processed immediately upon receipt via `POST /api/payments/`.

---

## Limitations

1. **Scheduler Integration:** Subscriptions do not automatically trigger recurring invoice generation via a background worker (e.g. Celery / cron); invoices are generated on-demand via the `/api/invoices/` endpoint or service call.
2. **Payment Gateway Webhooks:** External webhooks (Stripe/Razorpay) are simulated via the payment processing endpoint rather than direct signature-verified HTTP listeners.
3. **Automated Refunds:** The ledger supports `refund` entry types, but reverse credit-memo flows are managed operationally rather than through an automated one-click refund state machine.
