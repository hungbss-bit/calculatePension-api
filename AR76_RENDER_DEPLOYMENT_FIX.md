# AR-76 — Render Deployment Fix

## Root cause
The Render build succeeded, but the existing Render Web Service is configured with the manual Start Command:

`gunicorn your_application.wsgi`

This is not a command for this FastAPI/ASGI application, and `gunicorn` is not installed in requirements.txt. The resulting error is:

`bash: gunicorn: command not found`

## Correct Start Command

Use exactly:

`uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Do not use:

`gunicorn your_application.wsgi`

## Important
`render.yaml` already contains the correct startCommand. If the existing Render service still shows the old command, update the service's Start Command in the Render Dashboard (or redeploy the Blueprint so render.yaml is applied). Simply pushing render.yaml to an existing manually configured service may not replace its saved Start Command.

## Environment variables
Keep:
- API_KEY = the secret used by GPT Action
- REQUIRE_API_KEY = true
- AUTH_DIAGNOSTICS_ENABLED = false
- MAX_REQUEST_BODY_BYTES = 2097152

## Health check
`/health`

## Expected runtime
FastAPI ASGI application:
`app.main:app`
