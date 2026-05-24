# Consular AI — Institutional Citizen-Attention Platform

> **Working product name:** **ConsulAI** (white-label engine: **GovGrounded**)
> **Initial deployment:** Embassy of Colombia in Costa Rica
> **Category:** Government-grade, retrieval-grounded WhatsApp citizen-attention platform — *not a chatbot*.

This repository contains the **complete design, architecture, and commercial strategy** for a
production-ready institutional WhatsApp AI assistant that automates consular citizen support using
**only approved official information**, with traceability, human escalation, and full auditability.

The design deliberately prioritizes **reliability over creativity**. Every citizen-facing answer is
**grounded in an approved, versioned knowledge base**; ungrounded generation is structurally
prevented, not merely discouraged.

---

## Document Index

| # | Section | File |
|---|---------|------|
| 1 | Executive Overview | [docs/01-executive-overview.md](docs/01-executive-overview.md) |
| 2 | System Architecture (with Mermaid diagrams) | [docs/02-system-architecture.md](docs/02-system-architecture.md) |
| 3 | Government / Institutional Safety Design | [docs/03-safety-design.md](docs/03-safety-design.md) |
| 4 | WhatsApp Conversation Design | [docs/04-conversation-design.md](docs/04-conversation-design.md) |
| 5 | Knowledge Base Strategy | [docs/05-knowledge-base-strategy.md](docs/05-knowledge-base-strategy.md) |
| 6 | Admin Dashboard Design | [docs/06-admin-dashboard.md](docs/06-admin-dashboard.md) |
| 7 | Technical Stack Recommendations | [docs/07-technical-stack.md](docs/07-technical-stack.md) |
| 8 | Scalability Strategy (multi-tenant SaaS) | [docs/08-scalability.md](docs/08-scalability.md) |
| 9 | Pricing Strategy | [docs/09-pricing.md](docs/09-pricing.md) |
| 10 | Security & Compliance | [docs/10-security-compliance.md](docs/10-security-compliance.md) |
| 11 | Implementation Roadmap | [docs/11-roadmap.md](docs/11-roadmap.md) |
| 12 | Competitive Advantage Strategy | [docs/12-competitive-advantage.md](docs/12-competitive-advantage.md) |
| 13 | Suggested Commercial Branding | [docs/13-branding.md](docs/13-branding.md) |
| 14 | Risks & Failure Points | [docs/14-risks.md](docs/14-risks.md) |

---

## The One-Paragraph Pitch

> ConsulAI is an institutional citizen-attention platform that lets an embassy answer thousands of
> repetitive consular questions on WhatsApp — 24/7, in multiple languages — using **only the
> embassy's own approved documents**. Unlike a generic chatbot, every answer cites its source, low-
> confidence questions are escalated to a human officer, and administrators get a full audit trail
> and analytics dashboard. It deploys in weeks, not months, and is licensed annually per institution.

---

## Design Principles (non-negotiable)

1. **Grounded or silent.** If the answer is not in the approved knowledge base above a confidence
   threshold, the system does **not** answer — it escalates or defers. No free-form generation.
2. **Every answer is traceable.** Each response links to the source document, version, and chunk.
3. **Humans stay in control.** Officers can take over any conversation, disable any answer, and
   approve all content before it goes live.
4. **Audit everything.** Immutable logs of every message, retrieval, decision, and admin action.
5. **Buildable by a small team.** Managed services over bespoke infrastructure. No moon-shot
   architecture. A 2–4 person team can ship the MVP.

---

## Open Questions for the Embassy (answer before build)

These materially affect scope and pricing — see each section for where they land:

1. **Languages at launch?** (Assumed: Spanish + English; Portuguese/French as Phase 2.)
2. **WhatsApp Business API approval** — already obtained, or do we run onboarding? (Meta verification
   can take 2–4 weeks and is the critical-path long pole.)
3. **On-premise / sovereign hosting** required now or later? (Affects stack — see §7, §10.)
4. **Existing procurement / infosec compliance baseline** we must satisfy?
5. **CRM / ticketing integration** needed (e.g., handoff into an existing case system)?

## Assumptions Baked Into This Design

- First deployment is the Colombian Embassy in Costa Rica.
- The platform will expand to other embassies/consulates and public institutions.
- The goal is a commercial, annual-license SaaS with a clear path to a public-sector AI company.
- Practical, buildable architecture is preferred over theoretical sophistication.

## Roadmap Upgrade Modules (scoped in §11)

Live human-handoff with SLA tracking · WhatsApp voice-note transcription · citizen-demand analytics ·
document expiration/version monitoring · AI moderation + answer-approval workflows · multi-consulate
instance management · sovereign-hosting compatibility.
