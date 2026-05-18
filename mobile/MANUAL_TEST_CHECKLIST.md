# Manual Test Checklist - Share-First Flow UX

This checklist validates the mobile UX for the share-first flow across the app.
Test on at least one small viewport (320px width, e.g. iPhone SE) and one standard viewport (390-430px, e.g. iPhone 15 / Pixel 7).

## Test Devices

| Device | Screen Width | Status |
|--------|-------------|--------|
| Small viewport (iPhone SE / 320px equivalent) | 320px | [ ] Tested |
| Standard viewport (iPhone 15 / Pixel 7 / 390-430px) | 390-430px | [ ] Tested |

---

## 1. Inbox Screen

### Layout & Touch Targets
- [ ] No horizontal overflow on 320px viewport
- [ ] Greeting text is visible and not truncated
- [ ] Daily Digest button is fully tappable with one thumb (min 56px height)
- [ ] Each media item card is large enough to tap comfortably (min 56px)
- [ ] Media type badges are readable at 11px
- [ ] Time labels ("2h ago") are visible
- [ ] Source domain text does not overflow card bounds

### Processing States
- [ ] Items with "pending" status show spinner and "Pending" label
- [ ] Items with "classifying" status show "Classifying" label
- [ ] Items with "transcribing" status show "Transcribing" label
- [ ] Items with "completed" status have NO processing footer (clean card)
- [ ] Items with "failed" status show error styling (red container)
- [ ] Polling updates items in real-time (within 5 seconds)

### Pull-to-Refresh
- [ ] Pull down triggers refresh animation
- [ ] Refresh completes and updates list
- [ ] Error during refresh shows friendly message

### Empty State
- [ ] Empty inbox shows share hint with icon
- [ ] Text is centered and readable

---

## 2. Share Entry Flow (AC#3)

### Share from External App
- [ ] Sharing a URL from Safari/Chrome opens share confirmation screen
- [ ] Transition animation is smooth (slide from bottom)
- [ ] URL preview card shows the shared URL
- [ ] Domain is extracted and displayed correctly
- [ ] Close (X) button is tappable (44px)
- [ ] Save button is tappable (48px minimum height)

### Share Confirmation
- [ ] Tapping Save submits the URL
- [ ] Loading spinner appears on Save button during submission
- [ ] Success checkmark animation plays after submission
- [ ] Screen auto-dismisses after 1.5s on success
- [ ] Returning to inbox shows the new item (optimistic or after fetch)

### Validation
- [ ] Invalid URL shows validation error banner (red)
- [ ] Empty share shows appropriate error message
- [ ] Error banner has visible retry link

### Offline Share (AC#6)
- [ ] With airplane mode ON, sharing a URL shows "Queued for sync" overlay
- [ ] Queued link icon (cloud-offline) is displayed
- [ ] "Will be submitted when you reconnect" hint is visible
- [ ] Screen auto-dismisses after queued confirmation

---

## 3. Offline/Network Behavior (AC#6)

### Offline Banner
- [ ] When device goes offline, banner appears in inbox: "You are offline"
- [ ] Banner shows count of queued links (e.g. "2 links queued for sync")
- [ ] When no items queued, shows "Shared links will be saved and synced..."
- [ ] Banner disappears when connectivity returns

### Sync on Reconnect
- [ ] After going back online, queued items are submitted automatically
- [ ] "Syncing X queued links..." banner appears briefly
- [ ] Successfully synced items appear in the inbox list
- [ ] Failed sync items are retried (up to 5 times)

---

## 4. Media Detail Screen

### Layout
- [ ] Back button is tappable (44px + hitSlop)
- [ ] Share button is tappable (44px + hitSlop)
- [ ] Hero title uses large display text (32px)
- [ ] Metadata chips (source, date, duration) are readable
- [ ] No horizontal overflow on 320px viewport

### Transcription Status (AC#4)
- [ ] Pending transcript shows "Transcript processing will start soon"
- [ ] Extracting shows "Extracting audio content..." with spinner
- [ ] Transcribing shows "Transcribing audio to text..." with spinner
- [ ] Ready transcript shows green checkmark and "Transcript is ready"
- [ ] Failed transcript shows red icon and "Transcript processing failed"
- [ ] Failed transcript shows "Refresh status" retry button (48px min height)
- [ ] Tapping retry refreshes the status from the server

### Processing Failed Banner (AC#4)
- [ ] When processing_job.status is "failed", red banner is visible
- [ ] Banner shows error message from backend (or generic fallback)
- [ ] "Refresh" button in banner is tappable (48px)
- [ ] Tapping Refresh re-fetches media status

---

## 5. AI Artifacts (AC#5)

### Artifacts Toggle
- [ ] Yellow "AI Artifacts" toggle button is visible (48px min height)
- [ ] Tapping toggles expansion with smooth animation
- [ ] Auto-expands when media status is "ready_for_artifacts" or "completed"

### Generate Actions
- [ ] Each artifact row (Summary, Flashcards, Learning Notes) has icon + label
- [ ] "Generate" button is visible for idle artifacts when media is ready
- [ ] Generate button meets 48px minimum height
- [ ] Tapping Generate shows "Queued" state immediately (optimistic)
- [ ] "Queued" transitions to "Generating..." with spinner (via polling)
- [ ] "Generating..." transitions to "Ready" with green checkmark

### Ready State
- [ ] Ready artifacts show green checkmark badge
- [ ] "View" button appears next to ready artifacts
- [ ] View button is tappable

### Failed State
- [ ] Failed artifacts show "Failed" text in red
- [ ] "Retry" button is visible and tappable
- [ ] Tapping Retry re-triggers generation

### Non-Blocking
- [ ] Generating one artifact does not block generating another
- [ ] User can scroll and interact while artifacts generate
- [ ] Leaving and returning to the screen preserves artifact states

---

## 6. Search Screen

### Touch Targets
- [ ] Search input field is 48px height
- [ ] Clear (X) button has adequate hitSlop (>= 8px)
- [ ] Filter chips are 40px height with 48px min width
- [ ] Result cards are large enough to tap comfortably

### No Horizontal Overflow
- [ ] Filter chip row scrolls horizontally without overflow
- [ ] Result cards fit within screen bounds on 320px viewport
- [ ] Long URLs in cards truncate properly (numberOfLines)

---

## 7. Tab Bar

### Touch Targets (AC#2)
- [ ] Tab bar height is 64px (comfortable touch zone)
- [ ] Each tab icon + label is centered and tappable
- [ ] Active tab shows primary color (amber)
- [ ] Inactive tabs show muted color

---

## 8. General UX Criteria

### One-Handed Usability (AC#2)
- [ ] Primary actions (Save, Generate, Retry) are in thumb-reach zone (lower 2/3)
- [ ] Navigation (Back, Close) is accessible without stretching
- [ ] Tab bar is at the bottom for easy thumb access
- [ ] No critical actions require reaching to top corners

### Viewport Equivalence (AC#1)
- [ ] All screens render correctly on 320px width (no cut-off content)
- [ ] All screens render correctly on 430px width (no excessive whitespace)
- [ ] Text remains legible at all supported sizes
- [ ] Cards and lists use full available width (responsive margins)

### Accessibility
- [ ] All interactive elements have accessibilityLabel
- [ ] All buttons have accessibilityRole="button"
- [ ] Error states are announced (not just visual)
- [ ] Focus order follows visual layout
