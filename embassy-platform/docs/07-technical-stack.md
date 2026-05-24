# 7. Technical Stack Recommendations

Selection criteria, in order: **reliability, buildability by a small team, cost efficiency,
maintainability, and a clean path to multi-tenant scale and sovereign hosting.** Bias toward managed
services and boring, proven technology.

## 7.1 Recommended stack (MVP → scale)

| Layer | Recommendation | Why |
|---|---|---|
| **Backend** | **Python + FastAPI** (async) | Best AI/RAG ecosystem, async for webhook/queue I/O, fast to build, easy hiring. (Node/NestJS is a valid alternative if the team is JS-first.) |
| **Workers** | Python workers consuming **Redis Streams** (or **Celery/RQ**, or **SQS** on AWS) | Decouples WhatsApp ingress from AI processing; retries, backpressure, no message loss. |
| **Frontend (dashboard)** | **Next.js (React) + TypeScript + Tailwind + shadcn/ui** | Fast to build a clean, accessible admin UI; SSR/auth-friendly; large talent pool. |
| **Relational DB** | **PostgreSQL** | Single source of truth; transactional; mature; managed everywhere. |
| **Vector DB** | **pgvector (in Postgres)** for MVP; **Qdrant** if/when scale demands | One datastore to operate, transactional consistency with content, native per-tenant row filtering. Migrate to dedicated store only on real scale pressure (§8). |
| **Object storage** | **S3 / Cloudflare R2** | Store original PDFs/forms, versioned, immutable, cheap. R2 has no egress fees. |
| **Cache / queue / rate-limit** | **Redis** | Queue, answer cache, token-bucket rate limiting, session state. |
| **WhatsApp** | **WhatsApp Cloud API (Meta)** directly; **360dialog/Twilio** as BSP option | Cloud API = Meta-hosted, lower cost, official. A BSP simplifies number provisioning/billing and is worth it if the embassy wants a managed onboarding. |
| **LLM (generation)** | **Provider-abstracted**; default **Claude (Anthropic)** for grounded answering + **smaller model for intent/classification** | Strong instruction-following and refusal behavior suits grounded, controlled answers. Abstraction avoids lock-in and enables failover. |
| **Embeddings** | Managed **multilingual embedding model** (e.g., OpenAI `text-embedding-3`, Cohere multilingual, or a strong open model) | Multilingual ES/EN retrieval; pick on eval results + data-residency needs. |
| **Re-ranker** | Cross-encoder (Cohere Rerank or open cross-encoder) or LLM re-rank | Precision boost before generation. |
| **Auth (dashboard)** | **Clerk/Auth0** (fast) or self-hosted **Keycloak** (sovereign-friendly) + SSO/SAML for gov | RBAC, MFA, audit; Keycloak when on-prem/sovereign is required. |
| **Monitoring/observability** | **OpenTelemetry** + **Grafana/Prometheus** or **Better Stack/Datadog**; **Sentry** for errors | Tracing across webhook→queue→AI→send; per-tenant cost/latency dashboards. |
| **Analytics** | App-event tables in Postgres + **Metabase** (self-host) for staff-facing analytics | Cheap, embeddable, no extra vendor; gov-friendly. |
| **Infra/hosting** | MVP: **Railway/Render/Fly.io**. Scale: **AWS/GCP** (managed Postgres, Redis, container service). Sovereign: VPC/on-prem (§10). | Start simple; graduate without rewrite (containers + managed datastores). |
| **IaC / CI-CD** | **Terraform** + **GitHub Actions**, containerized (Docker) | Reproducible, auditable infra; required for gov procurement maturity. |
| **Secrets** | Cloud secrets manager / **Vault** | No secrets in code; rotation; audited access (§10). |
| **Voice notes** (roadmap) | Speech-to-text (Whisper-class / cloud STT) | Transcribe WhatsApp audio → text pipeline. |

## 7.2 LLM provider comparison

| Dimension | **Claude (Anthropic)** | **OpenAI (GPT)** | **Hybrid (recommended)** | **Local / open models** |
|---|---|---|---|---|
| Instruction-following & refusal (grounded, safe answers) | Excellent — strong at "answer only from context / say I don't know" | Excellent | Best of both: route by task | Good→variable; needs tuning |
| Multilingual ES/EN/PT | Strong | Strong | Strong | Varies by model |
| Cost control | Use small model for classify, larger for final answer | Same pattern | Optimized per task & per tenant | Lowest marginal cost; high ops cost |
| Data residency / sovereignty | Cloud (regional options via partners) | Cloud (Azure OpenAI gives regional + gov options) | Mix cloud + local per tenant | **Full sovereignty / on-prem** |
| Operational burden | Low (API) | Low (API) | Medium (abstraction layer) | High (GPU ops, scaling, evals) |
| Lock-in risk | Mitigated by abstraction | Mitigated by abstraction | Lowest | None |

**Recommendation:** Build a **thin provider-abstraction interface** (`generate()`, `classify()`,
`embed()`, `rerank()`) from day one. Default to a **hybrid**: a small/cheap model for intent
classification and a strong model (Claude as default) for grounded answer composition, with a
configured **failover** provider. This gives best quality, cost control, no lock-in, and — crucially
for government deals — the ability to **swap to a sovereign/local model per tenant** (e.g., Azure
OpenAI in-region, or a self-hosted open model) **without changing application code.**

When to consider **local/open models**: a government contract mandating on-prem/air-gapped hosting or
strict data residency. The abstraction means this is a deployment/config change, not a rewrite — but
budget for GPU infrastructure and an ongoing evaluation/ops effort (see §10/§11).

## 7.3 Why not heavier architecture

- **No Kubernetes for MVP** — managed PaaS + containers is enough for the first tenants; k8s/ECS
  arrives only when multi-tenant scale justifies the ops cost.
- **No separate vector DB initially** — pgvector keeps the system to one stateful brain; avoids
  sync/consistency bugs between content and embeddings.
- **No microservices sprawl** — a modular monolith (ingress API, worker, dashboard API) is faster to
  build, debug, and operate for a small team; split out services only when a bottleneck demands it.
- **No bespoke ML training initially** — managed embeddings + RAG + prompt control beat fine-tuning
  for time-to-value and maintainability; revisit fine-tuning/local models for sovereignty or cost at
  scale.

## 7.4 Build vs. buy summary

| Capability | Decision | Rationale |
|---|---|---|
| WhatsApp transport | **Buy** (Meta Cloud API / BSP) | Don't reinvent messaging infra. |
| LLM & embeddings | **Buy** (API), abstracted | Quality + speed; keep swap-ability. |
| RAG orchestration & guardrails | **Build** | This is the product's differentiated core. |
| Admin dashboard | **Build** | Differentiated; institutional workflows. |
| Auth | **Buy** (Clerk/Auth0) or **Keycloak** (sovereign) | Don't build auth. |
| Analytics UI | **Buy/embed** (Metabase) | Cheap, fast. |
| Monitoring | **Buy** (managed) | Reliability without ops overhead. |
