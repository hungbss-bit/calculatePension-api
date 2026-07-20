# Privacy Policy for calculatePension

## Data processed
The API receives information required to estimate a pension, such as date of
birth, sex, intended pension month, and social-insurance contribution history.

## Purpose
Data is processed only to calculate and return the requested pension estimate.

## Storage
The reference implementation does not persist request bodies or calculation
results. Production operators should keep this default or document any change.

## Logging
Do not log full request bodies in production. Redact dates of birth, salary
history, API keys, and other personal information from application and proxy
logs.

## Sharing
The API does not sell or share submitted data. Hosting and infrastructure
providers may process traffic only to operate the service under the operator's
agreements.

## Security
Use HTTPS, an API key or stronger authentication, secret rotation, rate limits,
access controls, and encrypted backups where applicable.

## Contact
Replace this section with the production operator's legal name, contact email,
jurisdiction, retention period, and deletion-request process before publication.
