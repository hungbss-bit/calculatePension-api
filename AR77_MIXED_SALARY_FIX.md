# AR77 — Mixed State + Employer Salary Fix

## Scope
This release is a minimal correction on top of V1.0.6/AR75. Existing correct behavior is preserved.

## Root cause found from O_Quy1/O_Quy2
For a mixed profile, the API correctly calculated the State average over the prescribed window, but then weighted that State average by only the State months having an included monetary basis. This excluded the 26 pre-01/1995 months from the State weight.

Official O_Quy2 requires:
- State duration: 277 months.
- Pre-01/1995: 26 months count toward duration but are excluded from the average-basis calculation.
- State averaging window: 60 months (01/2011–12/2015).
- State average: 9,006,800 VND/month.
- State equivalent: 9,006,800 × 277 = 2,494,883,600 VND.
- Employer duration: 126 months.
- Employer adjusted total: 993,404,250 VND.
- Combined average: (2,494,883,600 + 993,404,250) / 403 = 8,655,801 VND/month.
- Pension: 8,655,801 × 73% = 6,318,735 VND/month.
- One-time retirement allowance: 0.

## Preservation rule
For State-only profiles such as B_HUONG1, the previous weighting behavior is unchanged. The full-State-duration weighting is activated only when State salary and employer VND salary coexist in the same calculation.

## Deployment
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health: `/health`
