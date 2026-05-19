# Screenshot Specifications

## Required Sizes

### iOS (App Store Connect)

| Device Class | Size (pixels) | Aspect Ratio | Required |
|-------------|---------------|--------------|----------|
| 6.7" Display (iPhone 15 Pro Max) | 1290 x 2796 | 9:19.5 | Yes |
| 6.5" Display (iPhone 14 Plus) | 1284 x 2778 | 9:19.5 | Yes |
| 5.5" Display (iPhone 8 Plus) | 1242 x 2208 | 9:16 | Yes (for backward compat) |

- Minimum 3 screenshots, maximum 10 per device class
- Target: 6 screenshots per class
- Format: PNG or JPEG (no alpha channel)
- No iPhone frame bezels required (Apple renders them automatically in preview)

### Android (Google Play Console)

| Device Class | Size (pixels) | Aspect Ratio | Required |
|-------------|---------------|--------------|----------|
| Phone | 1080 x 1920 (min) to 3840 x 2160 (max) | 9:16 recommended | Yes (min 2, max 8) |
| 7" Tablet | 1200 x 1920 recommended | variable | Optional (recommended) |
| 10" Tablet | 1920 x 1200 recommended | variable | Optional (recommended) |

- Minimum 2 screenshots for phone, recommended 6-8
- Format: PNG or JPEG
- Max file size: 8 MB per image

## Screens to Capture

Target 6 screenshots for both platforms, capturing the core user journey.

### Screenshot 1: Share Flow (Entry Point)

**Screen**: Android Share Sheet / iOS Share Extension showing Media Summarizer as a target
**Caption**: "Share from any app to start learning"
**Notes**: Show the share sheet with a recognizable source app (e.g., YouTube or Chrome) in the background. Highlight that Media Summarizer appears in the share targets.

### Screenshot 2: Inbox / Media Library

**Screen**: Main inbox view with several media items in different states (processing, ready)
**Caption**: "Your personal media library, always organized"
**Notes**: Show a mix of content types (podcast, article, YouTube video) with status indicators. Include at least 4-5 items to show the library feels alive.

### Screenshot 3: Media Detail with Transcript

**Screen**: Media detail view showing a completed transcription
**Caption**: "Full transcripts of any audio or video"
**Notes**: Show a podcast or YouTube video with its transcript visible. Include media metadata (title, source, duration) at the top.

### Screenshot 4: Summary View

**Screen**: Summary artifact view (either short or detailed)
**Caption**: "AI summaries that capture what matters"
**Notes**: Show a well-structured summary with clear headings/sections. The content should look digestible and scannable.

### Screenshot 5: Flashcards

**Screen**: Flashcard view showing a Q/A card
**Caption**: "Flashcards to remember what you learn"
**Notes**: Show an active flashcard with a question visible. If possible, hint at the deck/stack of remaining cards.

### Screenshot 6: Search

**Screen**: Search view with results displayed
**Caption**: "Find anything in your knowledge base"
**Notes**: Show a search query with relevant results across different media types. Demonstrate that the library is searchable.

## Optional Additional Screenshots (7-8)

### Screenshot 7: Notes View

**Screen**: Structured notes artifact
**Caption**: "Structured notes, auto-generated"
**Notes**: Show the notes view with key points and organized structure.

### Screenshot 8: Multi-Platform Sources

**Screen**: Inbox showing variety of source platforms (Spotify, YouTube, TikTok icons)
**Caption**: "Works with all your favorite platforms"
**Notes**: Emphasize the breadth of supported sources with recognizable platform indicators.

## Design Guidelines

### Visual Consistency

- Use the app's primary brand color (#fcf9f6 background, accent colors per the design system)
- All screenshots should use the same device frame style (or no frame, consistent choice)
- Use realistic but curated content (not lorem ipsum)
- Show the app in "light mode" (the default `userInterfaceStyle`)

### Content Guidelines

- Use English-language content in all screenshots
- Avoid copyrighted content in visible text (use public domain or synthetic examples)
- Podcast examples: use popular genres but not specific celebrity podcasts
- Article examples: use generic tech/science topics
- Ensure no personal data (emails, names) is visible

### Caption Style

- Short, action-oriented phrases (5-8 words)
- Focus on user benefit, not feature name
- Consistent font, size, and positioning across all screenshots
- Place captions above or below the device frame (not overlapping UI)

### Background

- Clean, solid color or subtle gradient backgrounds
- Consistent across all screenshots in the set
- Brand-aligned: warm neutrals or the app's accent palette

## Production Workflow

1. Set up a demo account with curated content across all media types
2. Capture raw screenshots at native resolution on target devices (or simulator)
3. Apply consistent framing, captions, and backgrounds using a design tool (Figma recommended)
4. Export at exact required pixel sizes for each platform
5. Name files following the convention in `RELEASE-HANDOFF.md`
6. QA against the checklist in `QA-CHECKLIST.md`
