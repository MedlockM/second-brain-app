# Feedback Channels

## Primary: Canny.io Feedback Board

**Board URL (Free tier):** https://second-brain-labs.canny.io
**Board URL (Core tier, custom domain):** https://feedback.percole.app (when upgraded)

### Why Canny

Selected via benchmark task-116 (see `docs/research/task-116-feedback-intake/README.md`).
Key differentiators: JWT SSO on Free tier, full REST API on Free, dedicated mobile WebView URL,
proven at scale (ClickUp, Ahrefs, Mercury, CircleCI, Typeform).

### Board Configuration

- **Subdomain:** `second-brain-labs.canny.io` (Free tier) / `feedback.percole.app` (Core $19/mo, custom domain via CNAME)
- **Branding:** Second Brain Labs / Percole logo, warm-neutral color scheme
- **Statuses (default on Free):**
  - Open
  - Under review
  - Planned
  - In progress
  - Complete
  - Closed

### Seed Ideas (to populate before launch)

1. **Dark mode support** - Status: Under review
2. **Offline reading for summaries** - Status: Planned
3. **Share summaries as PDF** - Status: Open

### SSO Integration

Users accessing the feedback board from the mobile app are automatically authenticated
via Canny JWT SSO. The backend endpoint `GET /api/v1/feedback/token` generates a signed
JWT containing the user's ID, name, and email. The mobile app opens the Canny WebView URL
with the SSO token embedded as a query parameter.

**SSO key location:** `CANNY_SSO_PRIVATE_KEY` in Secrets Manager (runtime secret)
**Board token location:** `CANNY_BOARD_TOKEN` in Secrets Manager (runtime secret)

### Who Responds

- **Owner (solo dev)** triages all incoming feedback
- Target response time: within 48 hours for new posts
- Status updates pushed to all voters via Canny email notifications

### Review Frequency

- **Daily:** Quick scan of new posts, merge duplicates, acknowledge submissions
- **Weekly:** Status review, move items to Planned/In progress as roadmap evolves
- **Monthly:** Roadmap sync, communicate progress to users via Canny changelog

### Mobile Entry Point

The feedback board is accessible from the **Account** tab in the mobile app:
- Menu item: "Feature Requests" (icon: `bulb-outline`)
- Action: Opens the Canny WebView in the system browser with SSO authentication
- Taps to access: 2 (Account tab + Feature Requests row)

### Upgrade Path

| Stage | Tier | Cost | Unlocks |
|-------|------|------|---------|
| Launch (0-25 active feedback users) | Free | $0/mo | SSO, API, basic roadmap |
| Growth (25-100 active users) | Core | $19/mo | Custom domain, 100 tracked users, private boards |
| Scale (100+ active users) | Pro | $79/mo | Remove Canny branding, custom statuses, PM integrations |

### DNS Configuration (when upgrading to Core)

```
CNAME feedback.percole.app -> cname.canny.io
```

### Canny Account Setup Checklist

Manual steps required (cannot be automated):

1. [x] Create Canny account at https://canny.io/signup with Second Brain Labs email
2. [x] Set company subdomain to `second-brain-labs` (account already provisioned at `second-brain-labs.canny.io`)
3. [ ] Create board named "Feature Requests"
4. [ ] Configure SSO: Settings > SSO > Enable JWT SSO > copy private key to `CANNY_SSO_PRIVATE_KEY`
5. [ ] Copy board token: Settings > Board Tokens > copy to `CANNY_BOARD_TOKEN`
6. [ ] Set up Discord notification integration (after task-118 completes)
7. [ ] Seed 3 initial ideas (Dark mode, Offline reading, Share as PDF)
8. [ ] Configure public roadmap view in Canny dashboard
9. [ ] Upload Percole logo for board branding

### Related Documentation

- Benchmark rationale: `docs/research/task-116-feedback-intake/README.md`
- Canny SSO docs: https://developers.canny.io/install/widget/sso
- Canny API docs: https://developers.canny.io/api-reference
- Canny mobile widget: https://developers.canny.io/install/widget/mobile
