---
owner_decision: ok
---

# Benchmark : Feedback Intake Tools for V1 User Feature Requests

## Owner Validation

**Decision**: canny (voir documentation pour une implémentation correcte)
**Validated at**: _(date ISO a remplir par l'owner)_

---

## Recommendation

**Primary recommendation: Canny.io (Free tier)** — the only major dedicated feedback tool offering a genuinely usable free tier with JWT SSO on all plans, unlimited feedback posts, API access, custom domain (Core at $19/mo when needed), and a mobile WebView widget with SSO. For a solo dev pre-launch with <1000 users, Canny Free covers all core needs (feedback submission, voting, status management, basic roadmap) with zero monthly cost and a clear upgrade path.

**Alternative: Sleekplan (Indie Free tier)** — offers unlimited feedback items, feedback board + changelog on the free tier, an embeddable widget, and a very affordable upgrade to Business ($38/mo) for JWT SSO + custom domain + API. Best fallback if Canny's 25-tracked-user limit becomes constraining before budget allows the $19/mo Core tier.

---

## Section 1 — Brief produit reformule

### Why we need this now

Percole (the app, validated in task-115) is in pre-launch V1. Once on App Store and Play Store, user feedback will arrive through scattered channels: App Store reviews, email, social DMs, informal messages. Without a structured feedback channel:

- We cannot identify the most-requested features (mass signal vs. loud minorities)
- We cannot close the feedback loop ("you asked for X, we shipped X")
- We cannot let users vote on each other's ideas to reveal real priorities
- We cannot communicate a transparent public roadmap

### Blocking features for V1 launch

The feedback tool is NOT blocking V1 launch itself (the app ships without it), but it IS blocking the ability to run an informed V1.5/V2 prioritization cycle. Ideally, the feedback board URL goes live in the app within the first week post-launch.

### Minimum requirements

1. Users submit a feature request in <=3 taps from the app (external link to web board acceptable)
2. Users vote on others' ideas
3. Owner can triage, label, comment, change status (Under review / Planned / In progress / Shipped / Declined)
4. Public roadmap showing statuses

---

## Section 2 — Methode

### 12 evaluation criteria (scored 1-5)

| # | Criterion | Scoring guideline |
|---|-----------|-------------------|
| 1 | Cost (V1 stage, <=1000 users) | Free >= 4, <= 20 EUR/mo >= 3, > 50 EUR/mo <= 2 |
| 2 | Submission friction | <3 taps + no account creation = 5; account required = 3; clunky = 1 |
| 3 | Voting system | Nominative 1-vote/user with retract = 5; limited = 3; no voting = 1 |
| 4 | Public roadmap | Clear UI with statuses + filter + branding = 5; basic = 3; none = 1 |
| 5 | SSO / login integration | JWT custom on free/low tier = 5; paid-only SSO = 3; no SSO = 1 |
| 6 | Branding & custom domain | Free tier domain + colors = 5; paid only = 3; impossible = 1 |
| 7 | API + data portability | Full REST API on free = 5; paid-only = 3; no API = 1 |
| 8 | Notifications | Webhooks + Slack/Discord + email = 5; email only = 3; none = 1 |
| 9 | GDPR & hosting | EU datacenter + DPA + user deletion = 5; US-only with DPA = 3; no compliance = 1 |
| 10 | Mobile integration | WebView widget with SSO = 5; responsive web link = 3; desktop-only = 1 |
| 11 | Future-proof (scale to 100k) | Reasonable tier scaling = 5; price explodes = 2; no scaling = 1 |
| 12 | Reputation / track record | Used by known startups, stable company = 5; niche/new = 3; pivot risk = 1 |

### Tools evaluated (9 total)

1. Canny.io
2. Featurebase.app
3. Frill.co
4. Sleekplan
5. Upvoty
6. FeedBear
7. GitHub Discussions
8. Discord forum channels + vote bot
9. Nolt (additional discovery during research)

### Biases explicitly avoided

- No "Canny is the default" assumption — competitors have caught up significantly in 2024-2025
- No "free tools (GH Discussions/Discord) are good enough" assumption — they have real structural limits
- Strong weight on free tier + custom domain viability for solo dev with limited budget

---

## Section 3 — Tableau comparatif synthetique

| Criterion | Canny Free | Featurebase Free | Frill ($25/mo) | Sleekplan Indie (Free) | Upvoty ($15/mo) | FeedBear ($19/mo) | GitHub Discussions | Discord + Bot |
|-----------|-----------|-----------------|---------------|----------------------|----------------|------------------|-------------------|---------------|
| 1. Cost | 5 (free) | 5 (free) | 3 ($25/mo) | 5 (free) | 3 ($15/mo) | 3 ($19/mo) | 5 (free) | 5 (free) |
| 2. Submission friction | 4 | 4 | 4 | 4 | 4 | 4 | 2 | 2 |
| 3. Voting system | 5 | 5 | 5 | 5 | 5 | 4 | 2 | 2 |
| 4. Public roadmap | 4 | 5 | 5 | 3 | 4 | 4 | 1 | 1 |
| 5. SSO / login | 5 | 1 | 4 | 2 | 5 | 2 | 1 | 1 |
| 6. Branding & domain | 2 | 2 | 4 | 2 | 5 | 2 | 1 | 1 |
| 7. API + portability | 5 | 1 | 4 | 2 | 4 | 2 | 4 | 1 |
| 8. Notifications | 5 | 3 | 4 | 3 | 4 | 3 | 2 | 3 |
| 9. GDPR & hosting | 4 | 5 | 4 | 4 | 3 | 3 | 3 | 3 |
| 10. Mobile integration | 5 | 3 | 3 | 4 | 3 | 3 | 2 | 3 |
| 11. Future-proof | 4 | 4 | 3 | 4 | 4 | 3 | 5 | 2 |
| 12. Reputation | 5 | 5 | 3 | 3 | 3 | 2 | 5 | 3 |
| **TOTAL** | **53** | **43** | **46** | **41** | **47** | **35** | **33** | **27** |

### Score justifications (key differentiators)

**Canny Free (53/60)**:
- SSO=5: JWT token SSO available on ALL plans including Free (unique among competitors)
- API=5: Full REST API on Free tier (posts, votes, comments, users — all paginated)
- Mobile=5: Dedicated mobile WebView URL (`webview.canny.io?boardToken=X&ssoToken=Y`) with SSO
- Notifications=5: Discord, Slack, email, webhooks all on Free
- Branding=2: No custom domain on Free (requires Core $19/mo); Canny branding shown
- Roadmap=4: Available on Free but basic; advanced roadmap features on Pro

**Featurebase Free (43/60)**:
- GDPR=5: Built in EU, SOC 2 + GDPR compliant
- SSO=1: SSO only on Enterprise tier ($99/seat/mo) — deal-breaker for free/low-budget use
- API=1: API only on Professional tier ($59/seat/mo)
- Reputation=5: Used by n8n, Ghost, Raycast, Elementor, Lovable, OpenSea, HackerRank

**Upvoty ($15/mo) (47/60)**:
- Branding=5: Custom domain + custom CSS/HTML on all plans (even $15)
- SSO=5: Custom SSO on all plans
- API=4: API available on all plans
- Cost=3: No free tier, $15/mo minimum

**Sleekplan Indie Free (41/60)**:
- Cost=5: Free forever with unlimited feedback items
- SSO=2: JWT SSO only on Business tier ($38/mo)
- API=2: REST API only on Business tier ($38/mo)
- Mobile=4: Embeddable widget works in WebView, even on free tier
- Roadmap=3: Roadmap module only on Starter ($13/mo) and above

---

## Section 4 — Fiches detaillees des finalistes (Top 3)

---

### Finaliste 1 : Canny.io

#### Pricing (accessed 2026-06-08)

| Tier | Price | Key limits |
|------|-------|-----------|
| Free | $0/mo | 25 tracked users, 5 managers, unlimited posts, unlimited boards |
| Core | $19/mo (annual) | 100+ tracked users, custom domain, content translations, private boards |
| Pro | $79/mo (annual) | 10 managers, remove branding, custom statuses, custom fields, PM integrations |
| Business | Custom | 5000+ tracked users, enterprise SSO (Okta/OIDC), CRM integrations |

**Source**: https://canny.io/pricing (accessed 2026-06-08)

**Important**: "Tracked user" = someone who has given feedback (created post, voted, or commented). The 25-user limit on Free means up to 25 unique people can interact. For a soft launch with <100 early active users, this is viable for the first weeks/months; upgrade to Core ($19/mo) when crossing 25 active feedback participants.

#### Free tier exact limits

- 25 tracked users (voters/posters/commenters)
- 5 admin/manager seats
- Unlimited posts/ideas
- Unlimited boards
- API + webhooks included
- SSO (JWT token) included
- Discord/Slack/email notifications included
- Changelog included
- Widget included
- NO custom domain (uses `your-company.canny.io`)
- NO branding removal (Canny logo visible)
- NO private boards
- NO custom statuses (default: Open / Under review / Planned / In progress / Complete / Closed)

#### User flow description (submit idea + vote)

**From mobile app (WebView integration)**:
1. User taps "Feature Requests" in app settings/menu
2. App opens a WebView loading `https://webview.canny.io?boardToken=BOARD_TOKEN&ssoToken=JWT_TOKEN&theme=auto`
3. User is automatically authenticated (no login required) — sees their name/avatar
4. Board shows list of existing ideas sorted by votes
5. To vote: tap the upvote arrow on any post (1 tap)
6. To submit: tap "Create post" button → title + description fields → submit (3 taps total)

**From direct link (fallback)**:
1. User opens `feedback.percole.app` (custom domain, Core tier) or `percole.canny.io` (Free tier)
2. If SSO token is passed via redirect URL, user is auto-identified
3. Same board experience as above

#### Admin panel description

- Dashboard showing all posts across boards with filters (status, board, tag, segment)
- Each post: title, description, vote count, voter list, comments, internal comments (Core+), status dropdown, category, tags, owner assignment
- Bulk actions: merge duplicate posts, change status, add tags
- Status change triggers email notification to all voters
- Analytics: post activity over time, vote trends
- Roadmap view: drag-and-drop kanban of posts by status

#### Custom fields (configurable)

- Default statuses: Open, Under review, Planned, In progress, Complete, Closed
- Custom statuses: Pro tier only
- Tags: unlimited, custom-created
- Categories: unlimited, custom-created
- Custom fields (Pro): text, number, dropdown — attached to posts
- Board categories for multi-product organization

#### SSO integration doc

- **URL**: https://developers.canny.io/install/widget/sso
- **Method**: HS256 JWT signed with private SSO key from Canny dashboard
- **Payload fields**: `id` (required), `name` (required), `email` (required), `avatarURL` (optional)
- **Libraries**: Node.js (`jsonwebtoken`), Python, Ruby, Go, PHP, Java, C#
- **Available on**: All plans including Free

#### API / data export doc

- **URL**: https://developers.canny.io/api-reference
- **Auth**: Secret API key as POST parameter
- **Endpoints**: Posts (CRUD + status change), Votes (list/create/delete), Comments (list/create/delete), Users (list/create/delete), Boards, Categories, Tags, Changelog, Webhooks
- **Export**: Paginate through all posts + votes + comments for full data export (JSON)
- **Available on**: All plans including Free

#### Known products using Canny

Ahrefs, ClickUp, Mercury, CircleCI, Typeform, Strapi, Appcues, tl;dv, getimg.ai, Sticker Mule, Hive, Document360, Akiflow, Docusaurus (live example of embedded widget)

---

### Finaliste 2 : Sleekplan

#### Pricing (accessed 2026-06-08)

| Tier | Price | Key limits |
|------|-------|-----------|
| Indie (Free) | $0/mo | 1 seat, feedback board + changelog, 500K pageviews/mo, 300 emails/mo, no roadmap, no SSO, no API, no custom domain |
| Starter | $13/mo (annual) | 3 seats, roadmap + CSAT + NPS + surveys, all integrations, 1000 AI credits, no custom domain, no SSO, no API |
| Business | $38/mo (annual) | 10 seats, custom domain, JWT SSO, REST API, webhooks, branding removal, advanced analytics |
| Enterprise | Custom | SAML SSO, unlimited seats |

**Source**: https://sleekplan.com/pricing/ (accessed 2026-06-08)

#### Free tier exact limits

- 1 admin seat
- Unlimited feedback items
- Unlimited subscribers/tracked users
- 500K pageviews/month
- Feedback board + Changelog only (no roadmap)
- 300 email credits/month
- NO custom domain
- NO branding removal
- NO SSO (JWT or SAML)
- NO REST API or webhooks
- NO integrations (Slack, Jira, etc.)
- GDPR compliant, 99.99% uptime

#### User flow description

**Widget integration**:
1. Sleekplan provides a JavaScript widget embeddable in any web page
2. Widget shows feedback board inline (sidebar or full-page)
3. Users can submit ideas and vote directly within the widget
4. On mobile: widget is responsive but no dedicated mobile WebView URL like Canny

**Standalone board**:
1. `your-company.sleekplan.com` (or custom domain on Business tier)
2. Users browse, vote, submit without separate login (if widget is used with SSO on Business)
3. Simple submission: title + category dropdown + description

#### Admin panel description

- Unified dashboard: feedback, changelog, roadmap (if enabled), surveys
- Post management: status change, internal discussion, merge duplicates, tags
- AI auto-categorization on higher tiers
- Slack notifications (Starter+)

#### SSO integration

- **Available on**: Business tier ($38/mo) only — JWT SSO
- **Method**: JWT token signed with private key, passed via widget initialization
- **Doc**: https://sleekplan.com/docs/ (SSO section)

#### API / data export

- **Available on**: Business tier ($38/mo) only
- **Type**: REST API + webhooks
- **Capabilities**: CRUD on feedback items, voters, comments

#### Known products using Sleekplan

No publicly named major customers found. Marketing claims "95K+ monthly feedback signals" and "1.3M+ monthly users" across all customers. Used primarily by indie developers and small SaaS companies.

---

### Finaliste 3 : Upvoty

#### Pricing (accessed 2026-06-08)

| Tier | Price | Key limits |
|------|-------|-----------|
| Power | $15/mo | 1 project, unlimited boards/users, custom domain, custom CSS/HTML, SSO, API, all integrations |
| Super | $25/mo | Same as Power (unclear differentiation on pricing page) |
| Hyper | $49/mo | Unlimited projects, everything else same |

**Source**: https://upvoty.com/pricing/ (accessed 2026-06-08)

**No free tier** — 14-day free trial only.

#### First paid tier details ($15/mo Power)

- Unlimited boards
- Unlimited users
- Custom domain included
- Custom HTML/CSS (full branding control)
- Custom SSO
- API access
- All integrations
- Moderation, tags, segmentation, custom fields
- Roadmap + Changelog
- Vote on behalf, post on behalf
- AI merge (duplicate detection)

#### User flow description

**Standalone board**:
1. User visits `feedback.percole.app` (custom domain)
2. If SSO token passed, user auto-identified
3. Browse existing ideas sorted by votes
4. Vote: click upvote button (1 click)
5. Submit: click "Add suggestion" → title + description + optional category → submit

**Widget**:
1. Upvoty offers a widget embed (JavaScript)
2. Can be loaded in WebView for mobile integration
3. SSO token passed at initialization

#### Admin panel description

- Board management with statuses, tags, assignments
- Moderation queue (approve posts before public)
- Vote-on-behalf and post-on-behalf
- Custom fields on submission form
- Notification center (notify all voters of status change)
- Roadmap view with estimated launch dates

#### SSO integration

- **Available on**: All plans ($15+)
- **Method**: Custom SSO token (likely JWT-based, similar pattern to Canny)
- **Doc**: Available in Upvoty help center

#### API / data export

- **Available on**: All plans ($15+)
- **Capabilities**: Not extensively documented publicly; basic CRUD operations

#### Known products using Upvoty

No major publicly-listed customers found. Primarily used by indie makers and small SaaS products. Less brand recognition than Canny or Featurebase.

---

## Section 5 — Recommandation

### Primary: Canny.io (Free tier to start, Core $19/mo when needed)

**Justification**:

1. **Only dedicated tool with JWT SSO on Free tier** — this is the single most differentiating factor. Canny lets you identify users from your app without any monthly cost. Competitors (Sleekplan, Featurebase, FeedBear) lock SSO behind $38-99/mo tiers.

2. **Full API on Free** — critical for future data portability. If we ever migrate to another tool, all posts/votes/comments are exportable via REST API at zero cost.

3. **Dedicated mobile WebView URL** — `webview.canny.io?boardToken=X&ssoToken=Y` is purpose-built for mobile embedding. Competitors offer only responsive web pages or generic widget iframes.

4. **Proven at scale** — used by ClickUp, Ahrefs, Mercury, CircleCI, Typeform. Zero pivot risk for a company this established (founded 2017, profitable, 10k+ companies).

5. **Discord + Slack + email notifications on Free** — immediate notification pipeline without paying.

6. **Clear upgrade path** — when we pass 25 tracked users (likely within first 1-2 months post-launch), Core at $19/mo unlocks custom domain + 100 tracked users. Pro at $79/mo for branding removal when we want to white-label.

**Trade-offs accepted**:
- 25 tracked user limit on Free (acceptable for soft launch; upgrade to $19/mo is cheap)
- No custom domain on Free (uses `percole.canny.io` — perfectly acceptable for V1)
- Canny branding visible on Free (not a dealbreaker for early stage)
- US-hosted (Canny is US-based; GDPR compliant with DPA but no EU datacenter option)

### Alternative: Upvoty ($15/mo)

**When to prefer Upvoty over Canny**:
- If the 25 tracked user limit on Canny Free is hit immediately and $19/mo for Core feels wrong value (Upvoty at $15/mo gives unlimited users + custom domain + SSO + branding control)
- If white-labeling (full branding removal) is required from day 1
- If custom CSS/HTML theming is important to match the app's design language exactly

**Trade-offs**:
- No free tier (always $15/mo minimum)
- Smaller company, fewer notable customers, slightly higher pivot risk
- Less polished documentation and smaller community

### Why NOT the other tools

| Tool | Primary disqualification |
|------|-------------------------|
| Featurebase | SSO locked behind Enterprise ($99/seat/mo); API locked behind Professional ($59/seat/mo). Free tier is essentially a support inbox, not a feedback board with integration capabilities. |
| Frill | No free tier ($25/mo minimum); branding removal costs +$100/mo extra. SSO on all paid plans is good, but the cost floor is too high for a solo pre-launch project. |
| Sleekplan | Free tier has no SSO, no API, no custom domain, no integrations. Business ($38/mo) needed for JWT SSO — too expensive vs. Canny Free. |
| FeedBear | No free tier; SSO only on Business ($99/mo); no public API documented. |
| GitHub Discussions | No native voting (only emoji reactions as workaround); no roadmap view; no status management; no SSO; public-only (repo must be public). Structural mismatch with the use case. |
| Discord forum channels | No structured voting; conversation fragments across threads; no roadmap; no status tracking; no data export; moderation overhead. Complementary to a feedback board but not a replacement. |

---

## Section 6 — Plan d'integration V1

### Where to surface the feedback link in the mobile app

**Recommended placement**: Two entry points:
1. **Settings screen** → "Feature Requests" row (persistent, always accessible)
2. **Profile/Account screen** → "Help us improve Percole" card (optional, for discoverability)

The link opens an in-app WebView (React Native `WebView` component) loading the Canny mobile widget URL.

### Technical implementation

#### Phase 1 (launch week, Free tier, zero backend work):

```
URL: https://webview.canny.io?boardToken=BOARD_TOKEN&ssoToken={generated_token}&theme=auto
```

**Backend endpoint needed**: `GET /api/v1/feedback/token`
- Authenticates the current user (existing JWT auth middleware)
- Generates a Canny SSO token (HS256 JWT) containing:
  - `id`: user's DynamoDB user ID
  - `name`: user's display name
  - `email`: user's email
  - `avatarURL`: user's avatar URL (if available)
- Signs with Canny's private SSO key (stored in Secrets Manager alongside other secrets)
- Returns `{ "url": "https://webview.canny.io?boardToken=XXX&ssoToken=YYY&theme=auto" }`

**Mobile side**:
- Settings row "Feature Requests" → calls `GET /api/v1/feedback/token` → opens WebView with returned URL
- WebView renders the Canny board; user is auto-authenticated
- Total user taps: 1 (tap "Feature Requests") + 0 (auto-loads board) = immediate access

#### Phase 2 (post 25 tracked users, upgrade to Core $19/mo):

- Configure custom domain `feedback.percole.app` in Canny dashboard (CNAME DNS record)
- Update the backend endpoint to return the custom domain URL
- Enable private boards if needed for internal/beta features

#### Phase 3 (post scale, if needed):

- Upgrade to Pro ($79/mo) for branding removal + custom statuses
- Or migrate to self-hosted (Fider/Astuto) if cost becomes unreasonable at scale

### URL custom

- **Free tier**: `percole.canny.io` (board visible at this URL)
- **Core tier**: `feedback.percole.app` (custom domain via CNAME)

### SSO automation

SSO is fully automated via the backend endpoint described above. The user never sees a login screen on the feedback board — they are silently authenticated via the JWT token generated from their existing session.

### DNS configuration needed

When upgrading to Core ($19/mo):
```
CNAME feedback.percole.app → cname.canny.io
```

### Secrets to add

Add to `infrastructure/terraform/terraform.tfvars` → `secret_payload`:
```
CANNY_SSO_PRIVATE_KEY=<key from Canny dashboard>
CANNY_BOARD_TOKEN=<board token from Canny dashboard>
```

### Discord notification setup

In Canny dashboard → Integrations → Discord:
- Connect to the Percole Discord server (from task-118)
- Route new posts to `#feature-requests` channel
- Route status changes to `#product-updates` channel

---

## Section 7 — Decision

_(Section reserved for owner validation. Do not fill.)_

---

## Appendix A — Pricing URLs (accessed 2026-06-08)

| Tool | Pricing URL | Date accessed |
|------|------------|---------------|
| Canny.io | https://canny.io/pricing | 2026-06-08 |
| Featurebase | https://www.featurebase.app/pricing | 2026-06-08 |
| Frill | https://frill.co/pricing | 2026-06-08 |
| Sleekplan | https://sleekplan.com/pricing/ | 2026-06-08 |
| Upvoty | https://upvoty.com/pricing/ | 2026-06-08 |
| FeedBear | https://www.feedbear.com/pricing | 2026-06-08 |

## Appendix B — Additional reference URLs

| Resource | URL |
|----------|-----|
| Canny API docs | https://developers.canny.io/api-reference |
| Canny SSO (JWT) docs | https://developers.canny.io/install/widget/sso |
| Canny mobile widget docs | https://developers.canny.io/install/widget/mobile |
| Canny customers | https://canny.io/customers |
| Featurebase API docs | https://docs.featurebase.app/rest-api/ |
| Featurebase customers | https://www.featurebase.app/customers |
| Sleekplan integrations | https://sleekplan.com/integrations/ |
