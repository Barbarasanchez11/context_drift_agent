# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Credential Handling

This project handles sensitive credentials (LLM API keys, DataHub tokens). The design
explicitly keeps secrets out of source code:

- **All credentials are loaded from environment variables** — never hardcoded.
- The `.env` file (based on `.env.example`) is the only accepted configuration mechanism.
- `.env` is listed in `.gitignore` and must never be committed.
- DataHub tokens (`DATAHUB_TOKEN`) are optional for local development but required in
  production environments with authentication enabled.

If you discover a commit that accidentally included a secret, treat it as compromised
immediately — rotate the key and force-push to purge the history.

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public GitHub issue**.

Report it privately by emailing: **Barbara.sanchez@dataquantum.es**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

You will receive a response within 48 hours. We will coordinate a fix and disclosure
timeline with you.

## Known Scope

- **In scope:** credential leaks, injection via dataset URNs or LLM prompt inputs,
  insecure DataHub API usage.
- **Out of scope:** vulnerabilities in DataHub OSS itself, third-party LLM providers,
  or Docker/infrastructure configuration outside this repo.
