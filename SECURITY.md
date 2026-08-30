# Security

## Supported versions

Security fixes are provided for the latest release.

## URL fetching

OG Audit fetches URLs supplied by the operator and resources referenced by those pages. By default it rejects URL credentials, non-HTTP schemes, and addresses resolving to private, loopback, link-local, multicast, reserved, or unspecified networks. Every redirect target is validated again.

`--allow-private` disables network target protection and is intended only for trusted local development URLs. Do not expose a wrapper around this option to untrusted users.

DNS rebinding cannot be completely prevented by hostname pre-validation alone. Run untrusted audits inside a network sandbox with egress rules.

## Reporting a vulnerability

Please report vulnerabilities privately to [@iconcode_support](https://t.me/iconcode_support). Do not include secrets or customer data in a public issue.
