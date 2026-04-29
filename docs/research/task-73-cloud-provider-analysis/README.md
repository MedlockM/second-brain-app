---
owner_decision: ok
---

# Benchmark: Cloud Provider Analysis (AWS vs Alternatives)

## Owner Validation

**Decision**: stay with AWS
**Validated at**: 2026-04-29

---

## Recommendation

**Recommended provider: AWS (stay with current setup)**

For a novice deploying a V1 media processing app with low initial traffic, AWS remains the optimal choice despite its perceived complexity. Here's why:

### Key Decision Factors

1. **Production-ready infrastructure with proven patterns** — The project already uses LocalStack for development, meaning the AWS service patterns (DynamoDB, SQS, S3, ECS/Fargate) are battle-tested in the codebase. Switching providers would require rewriting significant infrastructure code and testing.

2. **Cost-effective at low scale** — AWS free tier covers the initial launch phase generously (25 GB DynamoDB storage, 1M SQS requests, Lambda free tier, etc.). First-year costs estimated at $15-50/month for low traffic (<100 users, <1000 jobs/month).

3. **Mature local development story** — LocalStack provides offline development capability that matches production services. Alternative PaaS providers typically require deployment to test, slowing iteration.

4. **Clear migration path to alternatives** — If cost or complexity becomes problematic after launch, the app can migrate to GCP (similar service model) or containerized PaaS (Railway, Fly.io) without complete rewrites. Starting on PaaS and later needing AWS-level features is harder.

5. **Vendor lock-in is minimal** — Using standard patterns (object storage via S3 API, message queues, NoSQL) means future migration is feasible. The project uses boto3/aiobotocore abstractions that can be swapped.

### Alternative Recommendation for Owner's Consideration

If **simplicity and deployment speed** are absolute priorities over cost optimization and local dev workflow, **Railway** would be the strongest alternative:
- $5-20/month flat pricing (vs AWS pay-as-you-go unpredictability)
- Postgres replaces DynamoDB (simpler mental model for folder/tag hierarchies)
- Native support for background workers and cron jobs
- GitHub integration with preview environments
- **Trade-off**: Requires deploying to test (no LocalStack equivalent); smaller community/ecosystem than AWS

---

## Analysis

### Current Architecture Requirements

Based on codebase inspection:

**Core Services Used:**
- **DynamoDB** (8+ tables): users, processing_jobs, auth_tokens, episode_idempotence, user_episode_submissions, episode_watchers, user_tags, user_folders, media_artifacts, artifact_idempotence, review_schedules, stripe_events, credit_transactions
- **SQS** (6+ queues): audio-download-queue, transcription-queue, summarization-queue, email-notification-queue, episode-completed-events, flashcards-queue, podcastindex-resolution-queue
- **S3** (4+ buckets): audio storage, transcriptions, summaries, flashcards
- **Compute**: ECS/Fargate for API + multiple async workers (download, whisper, summarization, email, events, flashcards, podcastindex resolution, article extraction)
- **Scheduled tasks**: cleanup expired holds, daily/weekly digest generation
- **External integrations**: Redis (for rate limiting PodcastIndex), CloudWatch (logging), Lambda (scheduled tasks)

**Development Requirements:**
- Ability to develop/test fully offline (currently via LocalStack)
- Multiple developer workflows (API testing, worker testing, end-to-end flows)
- CI/CD readiness (not yet implemented but needed for V1)

**V1 Scale Estimation:**
- Launch: <100 users, <1000 media items processed/month
- 6-month target: 500-2000 users, 5000-20000 jobs/month
- Burst scenarios: user shares 10+ items in one session
- Storage: <100 GB (mostly audio/transcripts), growing to 500 GB in year 1

---

## Provider Comparison Matrix

| Criterion | AWS | GCP | Railway | Fly.io | Render | Supabase | Cloudflare | Hetzner |
|-----------|-----|-----|---------|--------|--------|----------|------------|---------|
| **Estimated Monthly Cost (Launch)** | $15-50 | $20-60 | $20-40 | $30-60 | $40-80 | $50-100 | $25-50 | $30-60 |
| **Local Dev Experience** | ⭐⭐⭐⭐⭐ LocalStack | ⭐⭐⭐ Emulators | ⭐⭐ Deploy to test | ⭐⭐ Deploy to test | ⭐⭐ Deploy to test | ⭐⭐⭐⭐ CLI with Docker | ⭐⭐⭐ Wrangler dev | ⭐⭐ Deploy to test |
| **Setup Complexity** | ⭐⭐ High (IAM, VPC, etc.) | ⭐⭐ High | ⭐⭐⭐⭐⭐ Very simple | ⭐⭐⭐⭐ Simple | ⭐⭐⭐⭐ Simple | ⭐⭐⭐⭐ Simple | ⭐⭐⭐ Moderate | ⭐⭐⭐ Moderate |
| **NoSQL Database** | DynamoDB (Pay-per-request) | Firestore (Generous free tier) | Postgres (relational) | Postgres or external | Postgres | Postgres + realtime | D1 (SQLite) | Postgres or external |
| **Message Queue** | SQS (Native) | Cloud Tasks / Pub-Sub | Redis or external | Redis or external | Redis or external | Postgres-based queues | Queues (beta) | Redis or external |
| **Object Storage** | S3 ($0.023/GB) | Cloud Storage ($0.02/GB) | Not included | Not included | Not included | $0.021/GB | R2 ($0.015/GB + zero egress) | Object Storage ($0.015/GB est.) |
| **Async Workers** | ECS Fargate / Lambda | Cloud Run | Native workers | Native apps | Native workers | Edge Functions | Workers | Docker containers |
| **Scheduled Tasks** | EventBridge + Lambda | Cloud Scheduler | Native cron | Native cron | Native cron | pg_cron extension | Cron Triggers | External cron |
| **Vendor Lock-in Risk** | ⭐⭐⭐ Moderate | ⭐⭐⭐ Moderate | ⭐⭐ Low | ⭐⭐ Low | ⭐⭐ Low | ⭐⭐⭐ Moderate | ⭐⭐⭐⭐ High | ⭐ Very low |
| **Community / Docs** | ⭐⭐⭐⭐⭐ Extensive | ⭐⭐⭐⭐ Strong | ⭐⭐⭐ Growing | ⭐⭐⭐⭐ Strong | ⭐⭐⭐ Growing | ⭐⭐⭐⭐ Strong | ⭐⭐⭐⭐ Strong | ⭐⭐ Limited |
| **Scaling Ceiling** | ⭐⭐⭐⭐⭐ Unlimited | ⭐⭐⭐⭐⭐ Unlimited | ⭐⭐⭐ Good | ⭐⭐⭐⭐ Very good | ⭐⭐⭐ Good | ⭐⭐⭐ Good | ⭐⭐⭐⭐ Very good | ⭐⭐⭐⭐ Very good |

---

## Detailed Provider Analysis

### 1. AWS (Current)

**Pros:**
- **Already implemented** — All infrastructure code, LocalStack setup, and worker patterns are working
- **Generous free tier** — DynamoDB (25 GB + 25 RCU/WCU), SQS (1M requests/month), S3 (first 12 months: 5 GB + 20k GET + 2k PUT), Lambda (1M requests + 400k GB-seconds/month)
- **Best local development** — LocalStack provides offline emulation of all services used (DynamoDB, SQS, S3, Lambda, EventBridge)
- **Mature ecosystem** — boto3/aiobotocore are rock-solid, extensive documentation, large community
- **Future-proof** — Can add any AWS service (ML, real-time analytics, CDN, etc.) without architectural changes

**Cons:**
- **Complexity for beginners** — IAM policies, VPC networking, multiple service configuration files (Terraform)
- **Cost unpredictability** — Pay-as-you-go can surprise at scale if not monitored
- **Operational overhead** — Requires CloudWatch monitoring, cost alerts, potentially ECS cluster management

**Cost Breakdown (Low Traffic):**
- DynamoDB: $0 (free tier) → $5-10/month after free tier (pay-per-request)
- SQS: $0 (free tier) → $0.40/1M requests = ~$0.50/month for 1000 jobs/month
- S3: $0 (first year free tier) → $2-5/month for 100 GB storage + requests
- ECS Fargate: $0.04/vCPU-hour × 0.25 vCPU × 730 hours = ~$7/month per worker (if always-on) OR Lambda: $0 (free tier) for intermittent workers
- **Total estimate: $15-50/month** after free tier, scaling with usage

**Migration Effort if Switching FROM AWS:**
- DynamoDB → Postgres: Moderate (schema redesign, query pattern changes)
- SQS → Redis/Postgres queues: Low (message format stays same)
- S3 → Any S3-compatible storage: Very low (s3 API is standard)
- Fargate → Docker containers on PaaS: Low (Dockerfiles already exist)

**Sources:**
- AWS DynamoDB pricing: https://aws.amazon.com/dynamodb/pricing/
- AWS SQS pricing: https://aws.amazon.com/sqs/pricing/
- AWS S3 pricing: https://aws.amazon.com/s3/pricing/
- AWS Fargate pricing: https://aws.amazon.com/fargate/pricing/
- AWS Lambda pricing: https://aws.amazon.com/lambda/pricing/

---

### 2. Google Cloud Platform (GCP)

**Pros:**
- **Similar service model to AWS** — Firestore (NoSQL), Cloud Tasks/Pub-Sub (queues), Cloud Storage (objects), Cloud Run (containers)
- **Generous free tier** — Firestore (1 GB + 50k reads + 20k writes/day), Cloud Run (2M requests/month + 360k GB-seconds), Cloud Storage (5 GB for 12 months)
- **Simpler IAM** — Generally considered easier than AWS IAM
- **Cloud Run advantages** — Automatic HTTPS, built-in CDN, scales to zero (no idle costs)

**Cons:**
- **Requires migration** — All DynamoDB tables → Firestore, SQS → Cloud Tasks, infrastructure rewrite
- **Weaker local development** — Firestore emulator exists but not as mature as LocalStack; Cloud Run requires gcloud CLI or deployment to test fully
- **Firestore query limitations** — Less flexible than DynamoDB for complex access patterns (requires composite indexes)
- **No direct SQS equivalent** — Cloud Tasks is for scheduled/deferred tasks; Pub-Sub is pub-sub (not point-to-point queues)

**Cost Breakdown (Low Traffic):**
- Firestore: $0 (free tier likely covers launch) → $0.06/100k reads + $0.18/100k writes = ~$5-10/month after free tier
- Cloud Tasks: $0.10/1M tasks = ~$0.10/month for 1000 jobs
- Cloud Storage: $0.02/GB = $2/month for 100 GB
- Cloud Run: $0 (free tier covers low traffic) → ~$10-20/month for moderate traffic
- **Total estimate: $20-60/month** after free tier

**Migration Effort if Choosing GCP:**
- High initial investment (2-4 weeks engineering time)
- Ongoing: similar operational complexity to AWS
- Risk: if GCP doesn't fit later, switching again is costly

**Sources:**
- GCP Firestore pricing: https://cloud.google.com/firestore/pricing
- GCP Cloud Run pricing: https://cloud.google.com/run/pricing
- GCP Cloud Storage pricing: https://cloud.google.com/storage/pricing

---

### 3. Railway

**Pros:**
- **Simplest deployment** — `railway up` from CLI, GitHub integration with auto-deploy
- **Predictable pricing** — Usage-based but with monthly minimums ($5 Hobby, $20 Pro)
- **Postgres included** — No need for DynamoDB; use Postgres with proper schema design for folders/tags/jobs
- **Native worker support** — Define services in `railway.json`, automatically scaled
- **Preview environments** — Every PR gets a preview deployment (great for testing)

**Cons:**
- **No LocalStack equivalent** — Must deploy to test; can use Docker Compose locally but it's not the same as Railway's environment
- **Postgres != DynamoDB** — Need to redesign data models (folders/tags become relational); queries change
- **No native object storage** — Must use external S3/R2/Spaces (added cost + complexity)
- **Queue pattern change** — Use Redis queues or Postgres-based job queue (like `pg-boss` or `bull`); requires worker refactor

**Cost Breakdown (Low Traffic):**
- Hobby plan: $5/month minimum (includes 1 vCPU, 0.5 GB RAM per service)
- Postgres database: included in usage
- Redis: $5-10/month (separate service)
- Object storage: external (e.g., Cloudflare R2 at $0.015/GB = $1.50 for 100 GB)
- **Total estimate: $20-40/month** (flat, predictable)

**Migration Effort if Choosing Railway:**
- **High upfront** (3-5 weeks):
  - DynamoDB → Postgres schema design (normalize folders/tags/user relationships)
  - SQS → Redis queue pattern (e.g., Bull.js or Python rq)
  - S3 → External provider integration (e.g., R2, Spaces)
  - Worker refactor for Railway service definitions
- **Ongoing**: Very low (Railway handles infra)

**Developer Experience:**
- ⭐⭐⭐⭐ Simple for deployment, but local testing is Docker Compose (not Railway env)
- Preview envs are excellent for PR testing

**Sources:**
- Railway pricing: https://railway.com/pricing
- Railway docs: https://docs.railway.com/

---

### 4. Fly.io

**Pros:**
- **Excellent global deployment** — Apps deployed to multiple regions, auto-scaled
- **Simple container deployment** — `flyctl launch` detects Dockerfile and deploys
- **Postgres and Redis included** — Managed services available
- **Good performance** — Firecracker VMs are fast and efficient
- **Free tier** — Limited but usable for testing

**Cons:**
- **No LocalStack equivalent** — Deploy to test (can use `flyctl proxy` for debugging)
- **Postgres replaces DynamoDB** — Data model redesign required
- **No native object storage** — Must use external S3/R2/Spaces
- **Queue pattern change** — Use Redis or Postgres-based queues
- **Pricing can escalate** — Pay-as-you-go without clear cost caps

**Cost Breakdown (Low Traffic):**
- Compute: ~$10-20/month for API + workers (depends on uptime)
- Postgres: ~$15/month for managed Postgres (2 GB RAM)
- Redis: ~$10/month
- Object storage: external (R2: $1.50 for 100 GB)
- **Total estimate: $30-60/month**

**Migration Effort if Choosing Fly.io:**
- Similar to Railway (3-5 weeks upfront): Postgres schema, queue refactor, external storage
- Operational: Moderate (need to understand Fly.io regions, scaling config)

**Sources:**
- Fly.io pricing: https://fly.io/pricing
- Fly.io docs: https://fly.io/docs/

---

### 5. Render

**Pros:**
- **Simple deployment** — GitHub integration, auto-deploy, managed databases
- **Good DX** — Web dashboard, logs, metrics built-in
- **Postgres and Redis included** — Managed services with backups
- **Background workers native** — Define workers in `render.yaml`
- **Free tier** — Static sites free; web services have free tier with limitations

**Cons:**
- **No LocalStack equivalent** — Deploy to test
- **Postgres replaces DynamoDB** — Data model redesign required
- **No native object storage** — Must use external S3/R2/Spaces
- **Higher base cost** — $7/month for dev Postgres + $5/month per service minimum
- **Performance concerns** — Some users report slower cold starts than competitors

**Cost Breakdown (Low Traffic):**
- Web service (API): $10-20/month (depends on instance size)
- Workers: $10/month each × 3-5 workers = $30-50/month
- Postgres: $7/month (dev) or $20/month (production)
- Redis: $10/month
- Object storage: external (R2: $1.50 for 100 GB)
- **Total estimate: $40-80/month**

**Migration Effort if Choosing Render:**
- Similar to Railway/Fly.io (3-5 weeks upfront)
- Operational: Low (Render manages infra)

**Sources:**
- Render pricing: https://render.com/pricing
- Render docs: https://render.com/docs

---

### 6. Supabase

**Pros:**
- **Postgres-first** — Excellent Postgres DX, realtime subscriptions, built-in auth
- **Local development** — Supabase CLI with Docker for local stack
- **Object storage included** — Supabase Storage (S3-compatible)
- **Edge Functions** — Serverless functions for workers (Deno runtime)
- **Great for MVP** — Auth + database + storage + functions in one platform

**Cons:**
- **Not designed for heavy async processing** — Edge Functions have execution time limits (not ideal for long transcription jobs)
- **Postgres != DynamoDB** — Data model redesign required
- **Queue pattern limitations** — No native queue; must use Postgres-based job queue or external service
- **Higher cost at scale** — Pro tier is $25/month base + usage; scales quickly
- **Free tier limitations** — Projects pause after 1 week of inactivity (not suitable for production)

**Cost Breakdown (Low Traffic):**
- Pro plan: $25/month base (includes 8 GB database, 100 GB storage, 100k MAUs)
- Edge Functions: $2/1M invocations (beyond free 2M)
- Storage overage: $0.021/GB
- Database overage: $0.125/GB
- **Total estimate: $50-100/month** (higher base, but includes more services)

**Migration Effort if Choosing Supabase:**
- **High upfront** (3-5 weeks):
  - DynamoDB → Postgres schema design
  - Workers → Edge Functions (but need to handle long-running jobs differently)
  - SQS → Postgres job queue (e.g., `pgboss` or `graphile-worker`)
- **Ongoing**: Low (Supabase manages infra)

**Developer Experience:**
- ⭐⭐⭐⭐ Good local dev (Supabase CLI + Docker)
- Best suited for web apps with realtime features, less ideal for heavy background processing

**Sources:**
- Supabase pricing: https://supabase.com/pricing
- Supabase docs: https://supabase.com/docs

---

### 7. Cloudflare (Workers + R2 + D1)

**Pros:**
- **R2 storage** — Zero egress fees (huge cost saver), S3-compatible, $0.015/GB
- **Workers** — Serverless functions at the edge, fast, generous free tier (100k requests/day)
- **D1 database** — SQLite at the edge (beta), cheap ($0.75/1M reads)
- **Global by default** — Workers deployed to 200+ edge locations
- **Excellent for API + static assets** — Built-in CDN, caching, DDoS protection

**Cons:**
- **Not suitable for long-running workers** — Workers have 30-second CPU time limit (not enough for transcription)
- **D1 is beta** — Not production-ready for critical data
- **No native queue** — Queues are in beta; must use external service or workaround
- **Heavy refactor required** — Workers are JavaScript/TypeScript/Rust/etc., not Python-native
- **Database limitations** — D1 is SQLite (not designed for high-concurrency writes)

**Cost Breakdown (Low Traffic):**
- Workers: $5/month (includes 10M requests)
- R2 storage: $0.015/GB = $1.50 for 100 GB + $0 egress
- D1: $0.75/1M reads (beta pricing, may change)
- **Total estimate: $25-50/month** (but significant architectural changes required)

**Migration Effort if Choosing Cloudflare:**
- **Very high upfront** (5-8 weeks):
  - Rewrite API from Python (FastAPI) → JavaScript/TypeScript (Hono, itty-router)
  - Workers cannot run Whisper transcription (30s limit) → need external service
  - DynamoDB → D1 or external database
  - SQS → Cloudflare Queues (beta) or external
- **Not recommended for this project** — Worker execution limits are a deal-breaker for media processing

**Sources:**
- Cloudflare Workers pricing: https://workers.cloudflare.com/
- Cloudflare R2 pricing: https://www.cloudflare.com/products/r2/
- Cloudflare D1 docs: https://developers.cloudflare.com/d1/

---

### 8. Hetzner Cloud + Managed Services

**Pros:**
- **Very cheap VPS** — Starting at €4.15/month for CX11 (1 vCPU, 2 GB RAM)
- **S3-compatible object storage** — Cheap storage with no egress fees within EU
- **Postgres available** — Via self-managed or third-party managed services
- **Full control** — Docker containers, systemd services, whatever you need
- **GDPR-compliant** — EU-based, German hosting

**Cons:**
- **No managed services** — Must self-manage Postgres, Redis, monitoring, backups, security updates
- **No LocalStack equivalent** — Local dev is Docker Compose (not Hetzner env)
- **Operational burden** — You're responsible for server maintenance, scaling, security patches
- **No native queue service** — Must run Redis or use external SQS/RabbitMQ
- **Learning curve** — Requires sysadmin skills (not ideal for novice deployer)

**Cost Breakdown (Low Traffic):**
- CX21 VPS: €5.83/month (2 vCPU, 4 GB RAM) — run API + workers
- Object Storage: €4.95/month (1 TB storage + 1 TB egress included)
- Managed Postgres: ~€20/month (third-party provider like Aiven, Neon)
- Redis: self-hosted on VPS (included in VPS cost)
- **Total estimate: $30-60/month** (€27-50/month)

**Migration Effort if Choosing Hetzner:**
- **High upfront** (4-6 weeks):
  - DynamoDB → Postgres schema design
  - SQS → Redis queue pattern
  - S3 → Hetzner Object Storage (S3-compatible, minimal change)
  - Worker deployment → Docker Compose or systemd services
  - Setup monitoring, backups, security (firewall, SSH keys, fail2ban)
- **Ongoing**: High (you're the sysadmin)

**Not recommended for novice deployer** — Requires infrastructure experience.

**Sources:**
- Hetzner Cloud pricing: https://www.hetzner.com/cloud/
- Hetzner Object Storage: https://www.hetzner.com/storage/object-storage

---

## Developer Experience Comparison

| Aspect | AWS | Railway | Fly.io | Render | Supabase | GCP |
|--------|-----|---------|--------|--------|----------|-----|
| **Local testing** | ⭐⭐⭐⭐⭐ LocalStack (offline) | ⭐⭐ Docker Compose (not Railway env) | ⭐⭐ Deploy to test | ⭐⭐ Deploy to test | ⭐⭐⭐⭐ CLI + Docker | ⭐⭐⭐ Emulators (partial) |
| **Deployment speed** | ⭐⭐⭐ Terraform + Docker (5-10 min) | ⭐⭐⭐⭐⭐ `railway up` (<2 min) | ⭐⭐⭐⭐ `flyctl deploy` (<3 min) | ⭐⭐⭐⭐ Git push (3-5 min) | ⭐⭐⭐⭐ Git push (3-5 min) | ⭐⭐⭐ gcloud deploy (5-10 min) |
| **CI/CD integration** | ⭐⭐⭐⭐⭐ GitHub Actions + AWS CLI | ⭐⭐⭐⭐ GitHub integration | ⭐⭐⭐⭐ GitHub Actions | ⭐⭐⭐⭐ GitHub integration | ⭐⭐⭐⭐ GitHub integration | ⭐⭐⭐⭐ Cloud Build |
| **Debugging** | ⭐⭐⭐⭐ CloudWatch + X-Ray | ⭐⭐⭐ Logs + metrics | ⭐⭐⭐ Logs + metrics | ⭐⭐⭐ Logs + metrics | ⭐⭐⭐ Logs + Postgres Studio | ⭐⭐⭐⭐ Cloud Logging |
| **Preview environments** | ⭐⭐ Manual setup | ⭐⭐⭐⭐⭐ Built-in (per PR) | ⭐⭐⭐ Manual setup | ⭐⭐⭐⭐ Built-in (per PR) | ⭐⭐⭐⭐ Built-in (per branch) | ⭐⭐⭐ Manual setup |
| **Rollback** | ⭐⭐⭐ Manual (Terraform state) | ⭐⭐⭐⭐⭐ One-click | ⭐⭐⭐⭐ CLI rollback | ⭐⭐⭐⭐ One-click | ⭐⭐⭐ CLI rollback | ⭐⭐⭐ gcloud rollback |
| **Observability** | ⭐⭐⭐⭐⭐ CloudWatch, X-Ray, custom metrics | ⭐⭐⭐ Basic logs + metrics | ⭐⭐⭐⭐ Metrics + Grafana | ⭐⭐⭐ Basic logs + metrics | ⭐⭐⭐ Basic logs | ⭐⭐⭐⭐ Cloud Monitoring |
| **Documentation** | ⭐⭐⭐⭐⭐ Exhaustive | ⭐⭐⭐ Growing | ⭐⭐⭐⭐ Strong | ⭐⭐⭐ Growing | ⭐⭐⭐⭐ Strong | ⭐⭐⭐⭐ Strong |

**Key insight:** AWS local development with LocalStack is unmatched — you can test the entire system offline, including DynamoDB, SQS, S3, and Lambda. PaaS alternatives require deploying to test (slower iteration, higher friction for experimentation).

---

## Vendor Lock-in Assessment

### Low Lock-in (Easy to Migrate)
- **S3 → Any S3-compatible storage** (R2, Spaces, Hetzner, etc.) — API is standardized
- **Docker containers → Any container platform** (ECS → Cloud Run → Railway → Fly.io) — Portable
- **Postgres → Postgres** (Railway → Render → Supabase → Managed Postgres) — Portable

### Moderate Lock-in (Migration Effort Required)
- **DynamoDB → Postgres** — Schema redesign, query pattern changes, 2-4 weeks effort
- **SQS → Redis queues / Pub-Sub** — Message format portable, but SDK changes required, 1-2 weeks effort
- **Lambda → Cloud Functions / Edge Functions** — Code portable if not using AWS-specific libraries, 1-2 weeks effort

### High Lock-in (Costly to Migrate)
- **AWS IAM roles → GCP service accounts** — Security model differences, 1-2 weeks effort
- **CloudWatch metrics/logs → Alternative monitoring** — Custom dashboards must be rebuilt
- **Cloudflare Workers → Traditional servers** — Complete rewrite (JavaScript → Python), 5+ weeks effort

**Recommendation:** The project's use of AWS is **moderately locked in** due to DynamoDB. However:
- S3 usage is portable (s3 API is standard)
- SQS patterns are portable (message queues are universal)
- Docker containers are portable
- Switching from DynamoDB to Postgres is the main migration cost (2-4 weeks)

**Mitigation strategy:** Wrap AWS services in abstraction layers (already done: `utils/database_async.py`, `utils/sqs.py`, `utils/s3.py`). This makes future migration easier.

---

## Cost Projection by Provider (6-Month Horizon)

Assumptions:
- Month 1: 50 users, 500 jobs
- Month 6: 1000 users, 10,000 jobs
- Storage: 100 GB → 500 GB
- Compute: Low → Moderate (workers run more frequently)

| Provider | Month 1 | Month 6 | Notes |
|----------|---------|---------|-------|
| **AWS** | $20-30 | $80-150 | Free tier exhausted; pay-per-request scales with usage |
| **GCP** | $25-40 | $90-180 | Similar to AWS; Firestore can be more expensive at scale |
| **Railway** | $20-40 | $50-80 | Flat pricing (Hobby → Pro); predictable |
| **Fly.io** | $30-50 | $70-120 | Scales with compute uptime; less predictable |
| **Render** | $40-80 | $80-150 | Higher base cost; scales with instance count |
| **Supabase** | $50-100 | $100-200 | Higher base ($25/month Pro); scales with database + storage |
| **Hetzner** | $30-50 | $50-80 | Cheap VPS + storage; scales with VPS size only |

**Key insight:** AWS and Railway are most cost-effective at low scale. AWS scales better at high scale (pay-per-request). Railway caps out at moderate scale (need to move to Pro tier or migrate to AWS/GCP).

---

## Migration Plan (If Switching from AWS)

If the owner decides to switch providers after this analysis, here's the recommended migration path:

### Option A: Stay on AWS (Recommended)
**Action:** None required. Optimize current setup:
1. Implement cost monitoring (AWS Cost Explorer, budget alerts)
2. Review DynamoDB table designs for efficiency (avoid hot partitions)
3. Use Lambda for workers instead of Fargate where possible (cost savings for intermittent tasks)
4. Enable S3 Intelligent-Tiering for storage cost optimization

**Timeline:** 1-2 weeks (optimization)
**Risk:** Low (iterative improvements)

---

### Option B: Migrate to Railway (If Simplicity > Cost Optimization)

**Phase 1: Database Migration (2-3 weeks)**
1. Design Postgres schema for users, folders, tags, jobs, artifacts
2. Create migration scripts (DynamoDB → Postgres export/import)
3. Update ORM/query code (`utils/database_async.py` → SQLAlchemy or asyncpg)
4. Test data integrity and performance

**Phase 2: Queue Migration (1-2 weeks)**
1. Set up Redis on Railway
2. Replace SQS SDK calls with Redis queue library (e.g., `arq` for Python)
3. Update worker polling logic
4. Test message delivery and retries

**Phase 3: Storage Migration (1 week)**
1. Integrate Cloudflare R2 or DigitalOcean Spaces (S3-compatible)
2. Update S3 endpoint configuration in `utils/s3.py`
3. Migrate existing S3 objects (or keep AWS S3 initially)
4. Test upload/download flows

**Phase 4: Compute Migration (1-2 weeks)**
1. Define services in `railway.json` (API, workers, cron jobs)
2. Update environment variables for Railway
3. Deploy to Railway staging environment
4. Test end-to-end flows (submit media → process → artifacts)
5. Deploy to Railway production

**Phase 5: Cutover (1 week)**
1. DNS/domain migration
2. Monitor errors and performance
3. Decommission AWS resources (keep backups)

**Total Timeline:** 6-9 weeks
**Risk:** Moderate (schema changes, new queue patterns)

---

### Option C: Migrate to GCP (If AWS Complexity is the Issue)

**Phase 1: Service Mapping (1 week)**
1. DynamoDB → Firestore (design document structure)
2. SQS → Cloud Tasks (simple) or Pub/Sub (fan-out patterns)
3. S3 → Cloud Storage
4. ECS/Fargate → Cloud Run
5. Lambda → Cloud Functions

**Phase 2: Infrastructure as Code (2 weeks)**
1. Rewrite Terraform for GCP (or use Pulumi)
2. Provision Firestore, Cloud Storage buckets, Cloud Run services, Cloud Tasks queues
3. Set up IAM roles and service accounts

**Phase 3: Code Migration (3-4 weeks)**
1. Replace `boto3` with GCP client libraries (`google-cloud-firestore`, `google-cloud-storage`, `google-cloud-tasks`)
2. Update data access patterns for Firestore (document-oriented vs key-value)
3. Refactor worker code for Cloud Run (container-based, similar to Fargate)
4. Test locally with GCP emulators (Firestore, Storage)

**Phase 4: Deployment (1-2 weeks)**
1. Deploy to GCP staging environment
2. Run end-to-end tests
3. Monitor performance and costs
4. Deploy to production, cutover DNS

**Total Timeline:** 7-9 weeks
**Risk:** Moderate (Firestore query patterns differ from DynamoDB)

---

## Final Recommendation Summary

**For a novice deployer with low initial traffic:**

### Primary Recommendation: Stay on AWS
- **Rationale:** Already implemented, best local dev experience, generous free tier, proven patterns, future-proof
- **Action:** Optimize AWS setup (cost monitoring, Lambda where possible, S3 Intelligent-Tiering)
- **Timeline:** 1-2 weeks (optimization)
- **Monthly cost:** $15-50 (launch) → $80-150 (month 6)

### Alternative Recommendation: Railway (if simplicity is paramount)
- **Rationale:** Simplest deployment, predictable pricing, good DX, fast iteration
- **Action:** Migrate from AWS (Postgres schema, Redis queues, R2 storage)
- **Timeline:** 6-9 weeks (migration)
- **Monthly cost:** $20-40 (launch) → $50-80 (month 6)

### Not Recommended:
- **Cloudflare Workers** — 30-second execution limit is incompatible with transcription workers
- **Hetzner self-managed** — Too much operational burden for novice deployer
- **Supabase** — Edge Functions not designed for long-running media processing

---

## Impact on Local Development Workflow

### Current Workflow (AWS + LocalStack)
1. Start LocalStack: `docker-compose up localstack`
2. Provision infra: `docker-compose up terraform`
3. Run API: `docker-compose up api`
4. Run workers: `docker-compose up whisper download-worker summarize-worker`
5. Test end-to-end: Submit media → Poll status → Verify artifacts
6. **All services run offline** — No cloud account required, no deployment latency

**Developer experience:** ⭐⭐⭐⭐⭐ (can iterate in seconds, no cloud costs during dev)

---

### If Migrating to Railway
1. Local development: `docker-compose up` (Postgres, Redis, local workers)
2. **Cannot test Railway-specific features locally** (e.g., auto-scaling, service discovery)
3. Deploy to Railway staging: `railway up` (2-3 minutes)
4. Test on Railway: Submit media → Poll status → Verify artifacts
5. Iterate: Change code → `railway up` → Test again

**Developer experience:** ⭐⭐⭐ (must deploy to test real environment; slower iteration; preview envs help but add friction)

---

### If Migrating to GCP
1. Local development: GCP emulators (Firestore, Storage) via `gcloud`
2. **Emulators not as complete as LocalStack** (Cloud Run must be tested in cloud)
3. Deploy to GCP: `gcloud run deploy` (5-10 minutes)
4. Test on GCP: Submit media → Poll status → Verify artifacts

**Developer experience:** ⭐⭐⭐ (emulators help but not comprehensive; slower than LocalStack)

---

### If Migrating to Fly.io / Render
1. Local development: `docker-compose up` (Postgres, Redis, local workers)
2. Deploy to test: `flyctl deploy` or `git push` (3-5 minutes)
3. **Cannot test platform-specific features locally** (e.g., regions, scaling)

**Developer experience:** ⭐⭐ (deploy-to-test workflow; slower iteration)

---

**Conclusion:** AWS + LocalStack provides the **best local development experience** for this project. Switching to PaaS providers will slow down iteration and require deploying to test, which adds friction for a solo developer.

---

## Sources and References

1. **AWS Pricing:**
   - DynamoDB: https://aws.amazon.com/dynamodb/pricing/
   - SQS: https://aws.amazon.com/sqs/pricing/
   - S3: https://aws.amazon.com/s3/pricing/
   - ECS Fargate: https://aws.amazon.com/fargate/pricing/
   - Lambda: https://aws.amazon.com/lambda/pricing/

2. **GCP Pricing:**
   - Firestore: https://cloud.google.com/firestore/pricing
   - Cloud Run: https://cloud.google.com/run/pricing
   - Cloud Storage: https://cloud.google.com/storage/pricing

3. **PaaS Providers:**
   - Railway: https://railway.com/pricing
   - Fly.io: https://fly.io/pricing
   - Render: https://render.com/pricing
   - Supabase: https://supabase.com/pricing

4. **Alternative Providers:**
   - Cloudflare Workers/R2: https://workers.cloudflare.com/, https://www.cloudflare.com/products/r2/
   - DigitalOcean Spaces: https://www.digitalocean.com/products/spaces
   - Hetzner Cloud: https://www.hetzner.com/cloud/

5. **Local Development Tools:**
   - LocalStack: https://localstack.cloud/
   - Supabase CLI: https://supabase.com/docs/guides/cli
   - Wrangler (Cloudflare): https://developers.cloudflare.com/workers/wrangler/

6. **Project Codebase:**
   - Infrastructure: `/infrastructure/terraform/`
   - Docker Compose: `/docker-compose.dev.yml`
   - Utility modules: `/media_summarizer/utils/database_async.py`, `/media_summarizer/utils/sqs.py`, `/media_summarizer/utils/s3.py`
