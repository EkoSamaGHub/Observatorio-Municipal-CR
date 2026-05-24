# 10. Security & Compliance

Security is a sales requirement, not just an engineering one — a government procurement office will
audit this before signing. The platform is built to pass that review.

## 10.1 Data protection & encryption

- **In transit**: TLS 1.2+ everywhere (citizen↔Meta is end-to-end on WhatsApp; Meta↔platform and all
  internal hops over TLS). HSTS on the dashboard.
- **At rest**: encrypted databases, object storage, and backups (cloud-managed KMS or self-managed
  keys for sovereign tiers).
- **Data minimization**: store only what's needed. Hash/pseudonymize citizen phone numbers
  (`wa_contact_hash`) where full numbers aren't required; avoid collecting sensitive personal data —
  the assistant is instructed not to solicit it and to escalate cases that require it.
- **Field-level encryption** for any sensitive stored content; PII redaction in logs/analytics.

## 10.2 Secrets management

- No secrets in code or repos; all via a secrets manager (cloud KMS/Secrets Manager or Vault for
  sovereign).
- Rotation policy for API keys (Meta, LLM providers, DB); short-lived credentials where possible.
- Separate credentials per environment (dev/staging/prod) and per tenant where isolation requires.
- Access to secrets is least-privilege and audited.

## 10.3 Privacy (GDPR-style + local law)

The deployment touches Colombian and Costa Rican data-protection regimes; design to the stricter
GDPR-style baseline so we satisfy most jurisdictions:

| Principle | Implementation |
|---|---|
| Lawful basis & notice | Onboarding notice that the channel is automated/official, what's stored, and how to reach a human; per-tenant configurable. |
| Purpose limitation | Data used only for citizen attention; not for model training; not shared cross-tenant. |
| Data minimization | Collect/store the minimum; pseudonymize contacts. |
| Retention | Configurable per institution's records policy; automatic purge of conversation data after the retention window (audit log retained per legal requirement). |
| Data subject rights | Tooling to export/delete a citizen's data on request (right to access/erasure), scoped to legal retention. |
| Processor terms | DPAs with sub-processors (Meta, LLM, cloud); **no citizen data used to train third-party models** (contractually enforced; use providers' no-training/zero-retention options). |
| Residency | Regional hosting; sovereign/on-prem option for strict residency (§8). |

## 10.4 Government procurement concerns (anticipate & answer)

| Concern | Our answer / artifact |
|---|---|
| Where is data hosted / residency? | Regional hosting; dedicated/sovereign tier available; documented data-flow diagram. |
| Is citizen data used to train AI? | No — contractual no-training, zero-retention provider settings, documented. |
| Vendor lock-in? | Provider abstraction (LLM swappable), standard Postgres, data export tooling, exit plan. |
| Business continuity / exit | Backups, runbooks, documented offboarding + full data export; escrow option for source if required. |
| Accessibility | Dashboard WCAG AA; conversation flows in plain language. |
| Auditability | Immutable audit log, exportable; per-answer traceability. |
| Security posture | Documented controls, pen-test on request, vulnerability management, incident-response plan; path to ISO 27001 / SOC 2 as the company matures. |
| Liability for wrong answers | Grounded-only design + disclaimers + human escalation + audit trail; defined in contract with shared-responsibility model. |

## 10.5 Auditability

- **Immutable, append-only audit log** (no UPDATE/DELETE for app role; retention-locked storage):
  every citizen message, AI decision (intent, retrieval, confidence, sources, model+version), every
  admin action (approve, disable, takeover, config/threshold change, user/role change), with actor,
  timestamp, IP, and before/after.
- **Per-answer traceability**: reconstruct exactly why any answer was produced, against the document
  version live at that moment.
- **Exportable** for legal/records requests in standard formats; tamper-evidence (hash chaining)
  available for high-assurance tiers.

## 10.6 Role-based access control

- RBAC per §6.4 (viewer/editor/officer/approver/admin) + vendor super-admin with **break-glass**
  access that is time-boxed, reason-logged, and alerted.
- **MFA mandatory** for all dashboard users; **SSO/SAML/OIDC** for government identity integration.
- Least privilege; separation of duties (upload ≠ approve) where required; periodic access reviews.
- Session timeouts, IP allow-listing option for admin access.

## 10.7 API security

- Webhook **signature verification** (Meta HMAC) on every inbound call; reject unsigned/invalid.
- Authn/authz on all dashboard/admin APIs (JWT/session + RBAC checks server-side, never trust client).
- Input validation everywhere; output encoding to prevent XSS in the dashboard; parameterized queries
  (no SQL injection); strict CORS; security headers.
- **Tenant authorization checks** on every data access (defense-in-depth atop RLS); automated tests
  asserting cross-tenant access is impossible.
- Secrets/keys never logged; structured logs scrubbed of PII and credentials.

## 10.8 Rate limiting & abuse prevention

| Vector | Control |
|---|---|
| Spam / flooding by a citizen | Per-contact token-bucket rate limit; progressive backoff; temporary mute with notice. |
| Cost-exhaustion attack | Per-tenant quotas + alerts; answer cache; cap LLM calls/min per tenant. |
| Prompt injection / jailbreak | Input guardrails, structural isolation, output filters, no tools (see §3). |
| Malicious uploads (dashboard) | File-type/size validation, malware scan, sandboxed parsing, OCR isolation. |
| Credential attacks | MFA, lockout, anomaly alerts, audit. |
| Webhook abuse / replay | Signature verify + dedupe by message id + idempotency keys. |
| Data scraping via dashboard | RBAC, rate limits on export, audit of exports. |

## 10.9 Secure SDLC & operations

- IaC (Terraform) for reproducible, reviewable infra; least-privilege cloud IAM.
- CI with dependency scanning (SCA), secret scanning, SAST; container image scanning.
- Staging environment mirroring prod; no prod data in dev.
- Incident-response plan with severities, on-call, citizen/embassy notification path, and post-mortems.
- Regular backups with **tested** restores; documented RPO/RTO targets per tier.
- Vulnerability management with patch SLAs; periodic third-party penetration test as the company
  matures toward SOC 2 / ISO 27001.
