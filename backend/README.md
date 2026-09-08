# Omni Cloud Backend

FastAPI service deployed on Huawei Cloud ECS. It keeps the DashScope API key
off Android devices, proxies Qwen Realtime WebSocket events, and creates
short-lived signed upload URLs for private Huawei OBS objects.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
cp ../deploy/.env.example .env
pytest
uvicorn app.main:app --reload
```

The service starts without cloud credentials so `/health` and tests can run,
but login, Realtime, and OBS signing require their corresponding environment
variables.

## API

- `GET /health`
- `POST /api/v1/devices/login`
- `WS /api/v1/realtime`
- `POST /api/v1/uploads/sign`
- `POST /api/v1/uploads/complete`

In production, OBS credentials are read from the ECS metadata endpoint after an
IAM agency is attached to the ECS. `OMNI_OBS_ACCESS_KEY` and
`OMNI_OBS_SECRET_KEY` exist only for local development.
