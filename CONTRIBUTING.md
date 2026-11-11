# Contributing to POS Project

Thank you for your interest! Maintained by [Shawn Mutogo](https://github.com/swoet).

## Getting Started

1. Fork and clone the repository.
2. Create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Copy `backend/.env.example` to `backend/.env` and fill in your credentials.
4. Start the services:
   ```bash
   docker-compose up -d
   ```
5. Run backend tests:
   ```bash
   cd backend && pytest --cov=. -v
   ```

## Commit Format

```
feat: add barcode scanner support
fix: correct tax calculation for discounted items
test: add sales reconciliation integration test
security: rotate JWT signing key on startup
docs: update Docker setup instructions
```

## Code Style

- Python: PEP 8, type hints required on all public functions.
- TypeScript: follow the existing ESLint config in `admin_frontend/`.

## Security

Never commit `.env` files. Store secrets in environment variables only.
Report vulnerabilities via [private advisory](https://github.com/swoet/POS-Project/security/advisories/new).