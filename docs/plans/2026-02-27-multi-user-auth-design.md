# Multi-User Authentication & Data Isolation Design

**Date:** 2026-02-27
**Status:** Approved
**Approach:** Streamlit-Native Auth with PostgreSQL

## Problem

The Adaptive Trading Ecosystem dashboard is completely open — no login, no user accounts, no data isolation. Anyone who accesses the URL sees the same data and can control trading operations. For a public-facing platform where users connect their own brokerages, this is unacceptable.

## Requirements

1. Public website — anyone can sign up
2. Email + password authentication with email verification
3. Per-user data isolation — users never see each other's data
4. Encrypted storage of broker API keys (Alpaca, Webull)
5. Admin dashboard for the platform owner

## Architecture

```
Browser Tab → Streamlit Session → Login Gate → User Dashboard
                                      ↓
                              PostgreSQL
                              ├── users (bcrypt passwords)
                              ├── email_verifications (tokens)
                              ├── broker_credentials (Fernet-encrypted keys)
                              └── all existing tables (+ user_id FK)
```

## Database Schema Changes

### New Tables

**users**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK, default uuid4 |
| email | VARCHAR(255) | UNIQUE, indexed |
| password_hash | VARCHAR(255) | bcrypt, 12 rounds |
| display_name | VARCHAR(100) | |
| is_active | BOOLEAN | default True |
| is_admin | BOOLEAN | default False |
| email_verified | BOOLEAN | default False |
| created_at | TIMESTAMP | auto |
| updated_at | TIMESTAMP | auto |

**email_verifications**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| token | VARCHAR(255) | random, unique |
| expires_at | TIMESTAMP | 24h from creation |
| used | BOOLEAN | default False |

**broker_credentials**
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| broker_type | ENUM | ALPACA, WEBULL |
| encrypted_api_key | TEXT | Fernet-encrypted |
| encrypted_api_secret | TEXT | Fernet-encrypted |
| is_paper | BOOLEAN | default True |
| nickname | VARCHAR(100) | e.g. "My Alpaca Paper" |
| created_at | TIMESTAMP | auto |

### Existing Table Modifications

All existing tables gain a `user_id UUID FK → users` column:
- Trade
- TradingModel
- ModelPerformance
- CapitalAllocation
- PortfolioSnapshot
- MarketRegimeRecord
- RiskEvent

## Auth Flow

### Signup
1. User enters email, password, confirm password, display name
2. Validate: email format, password >= 8 chars, passwords match
3. Hash password with bcrypt (12 rounds)
4. Insert user row (email_verified=False)
5. Generate verification token, insert into email_verifications
6. Send verification email via SMTP
7. Show "Check your email to verify" message
8. User can still log in but sees a banner: "Please verify your email"

### Email Verification
1. User clicks link: `{BASE_URL}?verify={token}`
2. Dashboard checks query param on load
3. Lookup token in email_verifications, check not expired/used
4. Set user.email_verified=True, mark token as used
5. Show success message

### Login
1. User enters email + password
2. Lookup user by email
3. Verify bcrypt hash
4. Check is_active=True
5. Set session state: user_id, email, display_name, is_admin, authenticated=True
6. Rerun to show dashboard

### Logout
1. Clear all session state keys
2. Rerun to show login form

## Data Isolation

Hard rule: Every database query includes `WHERE user_id = :current_user_id`.

This is enforced by:
- A helper function `get_user_id()` that reads from session state
- All query functions accept `user_id` parameter
- No query ever runs without a user_id filter (except admin queries)

## Broker Key Encryption

- Algorithm: Fernet (symmetric, from `cryptography` library)
- Key source: `ENCRYPTION_KEY` environment variable
- Flow: user enters API key → encrypt with Fernet → store ciphertext in DB
- Decryption only happens at runtime when initializing broker client
- Key rotation: generate new Fernet key, re-encrypt all credentials

## Admin Dashboard

Accessible only when `user.is_admin == True`. Shows:
- Total users, new signups (7d/30d)
- User list with status (active/inactive, verified/unverified)
- Ability to disable/enable accounts
- Platform-wide trading stats (aggregate, no individual data exposure)

First admin created via CLI script or by setting is_admin=True directly in DB.

## New Files

| File | Purpose |
|------|---------|
| `dashboard/auth.py` | Login/signup forms, password hashing, session mgmt |
| `dashboard/auth_utils.py` | Email sending, token generation, verification |
| `dashboard/broker_settings.py` | UI for managing broker API keys |
| `dashboard/admin.py` | Admin dashboard tab |
| `db/encryption.py` | Fernet encrypt/decrypt helpers |

## Modified Files

| File | Changes |
|------|---------|
| `db/models.py` | Add User, EmailVerification, BrokerCredential models; add user_id FK to existing models |
| `config/settings.py` | Add ENCRYPTION_KEY, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, BASE_URL |
| `dashboard/app.py` | Add auth gate at entry, pass user_id to all data functions, add admin tab |
| `requirements.txt` | Add bcrypt, cryptography |
| `.env.example` | Add new env vars |

## Security Considerations

- Passwords: bcrypt with 12 rounds (industry standard)
- Broker keys: Fernet encryption at rest, key in env var (not DB)
- Session: Streamlit session_state (server-side, not client cookies)
- Email verification: 24h token expiry, single-use
- CORS: Already configured in FastAPI
- Rate limiting: Not in v1, can add later
- 2FA: Not in v1, can add later

## Dependencies Added

- `bcrypt` — password hashing
- `cryptography` — Fernet symmetric encryption for broker keys
