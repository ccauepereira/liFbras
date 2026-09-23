# LiFbras

LiFbras is a small educational web app for learning and practicing Brazilian Sign Language (Libras). Its mobile-first MVP has three areas: **Aprender** (visual lessons by category), **Praticar** (camera-based practice with basic sign recognition), and **Quiz** (simple exercises).

The stack is a React + Vite PWA, browser-side MediaPipe, and a Python FastAPI API with a small PyTorch classifier. Educational content will use local structured files. The MVP has no database or user accounts.

**Status:** Frontend application shell, initial handout-based learning content, real local camera hand-landmark detection, and a minimal FastAPI foundation are implemented. Sign recognition, quiz logic, and ML have not been added.

## Frontend

```bash
cd frontend
npm install
npm run dev      # development server
npm run build    # production build
npm run lint     # oxlint check
```

Requires Node.js 20+.

## Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

The API health check is available at `http://localhost:8000/api/v1/saude`. The backend currently supports Python 3.10+, and local configuration can be copied from `.env.example` when environment variables need to be changed.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Decisions](docs/DECISIONS.md)
- [Development and Deployment](docs/DEPLOYMENT.md)
- [UI References](docs/UI-REFERENCES.md)
- [UI Specification](docs/UI-SPEC.md)
