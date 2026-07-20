# calculatePension API

A FastAPI reference implementation for estimating Vietnam social-insurance
pensions. It is designed for a Custom GPT Action and for ordinary REST clients.

## Scope

Implemented:
- stepped normal retirement age;
- standard, hazardous/special-region, underground-coal, and main
  reduced-capacity pathways;
- 15-year eligibility threshold and 20-year compulsory threshold for the main
  reduced-capacity pathway;
- male/female pension-rate formulas and contribution-duration rounding;
- early-retirement rate reduction for reduced-capacity retirement;
- state-sector, employer-decided, voluntary, and mixed average-basis methods;
- 2026 salary/income adjustment coefficients;
- one-time retirement allowance estimate;
- optional transitional minimum-floor test;
- explicit `manual_review` and `needs_more_data` outcomes.

Deliberately routed to manual review:
- armed-forces-specific status pathways;
- occupational HIV/AIDS pathway;
- especially-hazardous reduced-capacity pathway;
- any case whose classification evidence is not represented in the request.

## Important input convention

`pension_start_month` is the **first month receiving pension**. The API treats
the retirement/employment end date as the final day of the preceding month.

Contribution periods are inclusive. Overlapping months are rejected.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health: `http://127.0.0.1:8000/health`

## Run with Docker

```bash
copy .env.example .env
docker compose up --build
```

## Example request

```bash
curl -X POST "http://127.0.0.1:8000/v1/calculatePension" ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: replace-with-a-long-random-secret" ^
  --data-binary "@examples/request.json"
```

For local development, leaving `API_KEY` unset disables authentication. Do not
use that configuration on a public deployment.

## Connect to a Custom GPT

1. Deploy the API on a public HTTPS domain.
2. Replace `https://YOUR_PUBLIC_HTTPS_DOMAIN` in `openapi-gpt-action.yaml`.
3. In the GPT editor, add an Action and paste/import that schema.
4. Configure API-key authentication using header `X-API-Key`.
5. Paste `gpt-instructions.txt` into the GPT instructions.
6. Host a completed privacy policy and provide its URL if publication requires it.
7. Test eligible, ineligible, missing-data, and manual-review cases.

## Annual maintenance

Before each new benefit year:
1. replace the annual salary and voluntary-income coefficients;
2. update the legal-rule version;
3. regression-test retirement-age and rate rules;
4. publish a dated release and keep the prior coefficient table for audit;
5. review new legislation and implementing guidance.

The built-in coefficient set is 2026. Requests for another coefficient year must
supply both custom coefficient tables.

## Test

```bash
pytest -q
```

## Production hardening

Use HTTPS, API-key rotation or OAuth, rate limiting, request-size limits,
structured audit logs without personal data, encrypted secrets, monitoring, and
a versioned rules database. Do not log raw request bodies.

## Giao diện Swagger UI tiếng Việt

Phiên bản 1.1.0 sử dụng giao diện tiếng Việt tại:

```text
http://127.0.0.1:8000/docs
```

Giao diện tiếng Anh vẫn được giữ tại:

```text
http://127.0.0.1:8000/docs-en
```

Các nhãn thao tác như **Thử nhập dữ liệu**, **Thực hiện**, **Nội dung yêu cầu**,
**Kết quả trả về**, **Các cấu trúc dữ liệu** và mô tả từng trường đã được Việt hóa.
Tên trường JSON như `date_of_birth`, `contributions` và `monthly_basis_vnd` vẫn
được giữ bằng tiếng Anh để không làm thay đổi hợp đồng API và cấu hình ChatGPT
Actions hiện có.

Sau khi thay mã nguồn, hãy dừng máy chủ bằng `Ctrl+C` và chạy lại:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Sau đó nhấn `Ctrl+F5` tại trang `/docs` để trình duyệt tải lại toàn bộ giao diện.


## Triển khai miễn phí lên Render

Phiên bản này có sẵn `render.yaml`, `.python-version`, endpoint
`/privacy-policy` và hướng dẫn `HUONG-DAN-TRIEN-KHAI-RENDER.md`.

Sau khi triển khai, dùng URL HTTPS dạng `https://<service>.onrender.com` làm
server trong GPT Action.
