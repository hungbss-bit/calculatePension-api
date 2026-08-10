# AR-75 — Deployment Fix V1.0.6

## Mục tiêu
Khóa cấu hình production V1.0.6 và sửa OpenAPI Action schema để GPTs nhận đúng server Render.

## Production server
`https://calculatepension-api.onrender.com`

## GPT Action
Dùng duy nhất `openapi-calculatePension-V1.0.json`. Schema đã có `servers` và security scheme `X-API-Key`.

## Render
- Runtime: Python
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health: `/health`
- API key environment: `API_KEY`
- `REQUIRE_API_KEY=true`

## Lưu ý
`SCHEMA_V1.0_Deploy.json` là schema dữ liệu triển khai, không phải OpenAPI schema cho GPT Action.
`openapi-calculatePension-V1.0.yaml` là bản YAML tương đương để quản trị.
