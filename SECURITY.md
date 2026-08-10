# Security Policy

## Scope

`calculatePension-api` V1.0 is an estimation API. It is not the official system for adjudicating social-insurance benefits.

## Reporting a vulnerability

Do not publish credentials, citizen records, Social Insurance Book numbers, or exploit details in public issues.

Until a dedicated security contact is configured, report suspected vulnerabilities privately to the repository owner through a private GitHub channel. Replace this instruction with an official security contact before public production launch.

## Sensitive data rules

- Never commit real BHXH records or personally identifiable information.
- Never commit API keys, tokens, passwords, certificates, or private keys.
- Logs must not contain full Social Insurance Book numbers or submitted histories.
- `calculation_id` is the identifier for a calculation; `temporary_id` is not a database primary key.
