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

### Share Confirmation (ingestion starts on arrival — task-378)
- [ ] The card shows a spinner without any tap: the submission left on arrival
- [ ] The card footer turns into a checkmark ("Processing started") once accepted
- [ ] The screen does **not** auto-dismiss on a share, whatever the outcome
- [ ] The folder row is still usable while the card shows a spinner
- [ ] Tapping Save closes the screen and leaves exactly one item in the inbox
- [ ] Tapping X removes the item — gone from the inbox and from Search
- [ ] Tapping X while offline shows "Could not remove it" with a working retry
- [ ] A local import (file picker, camera) still submits on Save and auto-dismisses

### Sharing a note (task-380 — needs a fresh EAS build, not an OTA update)
- [ ] iOS: sharing a note from **Apple Notes** opens the confirmation screen with its text
- [ ] Android: sharing a note from **Google Keep** does the same
- [ ] Android (Samsung device): sharing a note from **Samsung Notes** does the same
- [ ] The preview label reads "Note" — the words "WhatsApp" and "message" appear nowhere
- [ ] The preview icon is a document, not a speech bubble
- [ ] The top bar reads "Save Note"
- [ ] Once processed, the title is the note's own first line (a Markdown `# Heading` loses its `#`)
- [ ] Exporting the same note to `.txt`, then `.md`, then `.rtf` and sharing each one: all three are accepted, and their content reads as text with accents and paragraphs intact
- [ ] A text file debits nothing: the minutes gauge on Account is unchanged after the three imports
- [ ] iOS: sharing a **locked** note shows "This note has no text to save…" and the screen stays open
- [ ] A note longer than 50,000 characters is refused with the two figures in the sentence
- [ ] A 0-byte `.txt` is refused before any transfer; a whitespace-only `.txt` fails with "This document could not be read…"
- [ ] A note holding text **and** a photo presents exactly one item — never a blank screen that closes itself
- [ ] Selecting several files at once and sharing them presents exactly one, and one the app can handle
- [ ] The paywall shows a "Notes" chip, a "TXT MD RTF" chip, and a "A note or a text file / Free" cost row
- [ ] Sharing a **voice note** from WhatsApp still says audio, not note

### Validation
- [ ] Invalid URL shows validation error banner (red)
- [ ] Empty share shows appropriate error message
- [ ] Error banner has visible retry link

### Typing a link in from the "+" menu (task-379)
- [ ] "+" on Home offers "Paste a link" above the file and photo rows
- [ ] The dialog opens *after* the sheet has finished closing (no dead modal on iOS)
- [ ] The field has focus on opening, and the keyboard is the URL one (`/`, `.com`)
- [ ] Nothing is auto-capitalised and nothing is auto-corrected while typing
- [ ] A long press in the field offers the system Paste, and pasting works
- [ ] The keyboard rises without covering the field or the two buttons
- [ ] Add is disabled while the field is empty
- [ ] `just some words` is refused under the field, the dialog stays open, the text
      is kept, and no item appears in the inbox after a pull-to-refresh
- [ ] A URL pasted with a sentence around it is accepted, and only the URL is sent
- [ ] `example.com/article` is accepted and sent as `https://example.com/article`
- [ ] On Add: the dialog closes, the confirmation screen opens, and the card shows
      a spinner then a checkmark — processing started before any tap on Save
- [ ] The folder row is usable while that spinner is running
- [ ] Save closes the screen and leaves exactly one item (no second job)
- [ ] X removes the item, both while it is processing and once it is done
- [ ] Cancel, then "+" → "Paste a link" again: the field is empty, not a leftover draft
- [ ] With the interface language set to Arabic, the address stays left-to-right

---

## 3. Media Detail Screen

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

## 4. AI Artifacts (AC#5)

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

## 5. Search Screen

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

## 6. Tab Bar

### Touch Targets (AC#2)
- [ ] Tab bar height is 64px (comfortable touch zone)
- [ ] Each tab icon + label is centered and tappable
- [ ] Active tab shows primary color (amber)
- [ ] Inactive tabs show muted color

---

## 7. General UX Criteria

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
