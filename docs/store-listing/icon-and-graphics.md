# Icon and Graphic Assets Specification

## App Icon

### Requirements

| Platform | Size | Format | Notes |
|----------|------|--------|-------|
| iOS (App Store) | 1024 x 1024 px | PNG, no alpha, no rounded corners | Apple applies corner radius automatically |
| Android (Play Store) | 512 x 512 px | PNG, 32-bit with alpha | Google applies adaptive icon masking |
| Android Adaptive Icon (foreground) | 108 x 108 dp (432 x 432 px at xxxhdpi) | PNG with alpha | Must work within safe zone (66 x 66 dp center) |
| Android Adaptive Icon (background) | 108 x 108 dp | PNG or color | Solid color: #fcf9f6 (as configured in app.config.ts) |

### Design Brief

**Concept**: The icon should communicate "knowledge capture" and "media transformation" at a glance.

**Direction A (recommended)**: A stylized brain or neural network motif combined with a share/input arrow, suggesting content flowing into organized knowledge. Clean, modern, flat design with subtle depth.

**Direction B**: An open book or notebook with a play button or audio waveform integrated, representing the transformation of media into readable knowledge.

**Color Palette**:
- Primary: Warm accent color (to stand out on both light and dark home screens)
- Background: Clean, not cluttered (#fcf9f6 warm white or a complementary tone)
- Avoid: Pure white backgrounds (disappear on iOS light mode), overly complex gradients

**Style Guidelines**:
- Flat or semi-flat design (subtle shadows acceptable, no heavy skeuomorphism)
- Must be recognizable at 29x29 px (smallest iOS usage: Settings icon)
- No text in the icon (app name is shown separately by the OS)
- No photographs or screenshots inside the icon
- Single focal element, not a collage

### Current Placeholder Assets

Located in the mobile project:
- `mobile/assets/icon.png` - Main icon placeholder
- `mobile/assets/adaptive-icon.png` - Android adaptive foreground placeholder
- `mobile/assets/splash.png` - Splash screen placeholder

These must be replaced with final production assets before store submission.

## Feature Graphic (Google Play Only)

### Requirements

| Asset | Size | Format | Notes |
|-------|------|--------|-------|
| Feature Graphic | 1024 x 500 px | PNG or JPEG | Displayed at the top of the Play Store listing |

### Design Brief

**Purpose**: The feature graphic is the banner at the top of the Google Play listing. It should communicate the app's value proposition visually in a single glance.

**Concept**: A clean composition showing the transformation flow - media sources on one side (podcast waveform, video play button, article icon) flowing through the app into organized outputs (summary card, flashcard, notes). Keep it minimal and uncluttered.

**Requirements**:
- Do not rely on text (it may be cropped or shown at small sizes)
- If text is included, limit it to the app name or a 3-4 word tagline
- Ensure the design works when cropped to different aspect ratios (Google may crop it)
- Use brand colors consistently with the icon

**What to avoid**:
- Screenshots of the app (use the screenshot slots for that)
- Dense text or feature lists
- Low contrast that becomes unreadable at small sizes

## Splash Screen

### Requirements

| Platform | Recommendation |
|----------|---------------|
| iOS | Use a centered logo/icon on brand background color |
| Android | Same approach; configured via `splash` in app.config.ts |

**Current config** (from app.config.ts):
- Background color: `#fcf9f6`
- Resize mode: `contain`
- Image: `mobile/assets/splash.png`

**Design**: Centered app icon (or simplified version) on the warm white background. No text needed - the splash screen displays briefly during app startup.

## Asset Delivery Checklist

| Asset | File | Size | Status |
|-------|------|------|--------|
| iOS App Icon | `mobile/assets/icon.png` | 1024x1024 | Placeholder - needs production design |
| Android Adaptive Foreground | `mobile/assets/adaptive-icon.png` | 432x432+ | Placeholder - needs production design |
| Android Adaptive Background | (color defined in app.config.ts) | -- | Set to #fcf9f6 |
| Play Store Icon | `docs/store-listing/assets/icon-512.png` | 512x512 | Not yet created |
| Feature Graphic | `docs/store-listing/assets/feature-graphic.png` | 1024x500 | Not yet created |
| Splash Screen | `mobile/assets/splash.png` | Variable | Placeholder - needs production design |

## File Naming Convention

All final production assets should be placed in `docs/store-listing/assets/` with the following names:

```
assets/
  icon-1024.png          # iOS App Store icon (1024x1024)
  icon-512.png           # Google Play Store icon (512x512)
  adaptive-fg.png        # Android adaptive icon foreground
  feature-graphic.png    # Google Play feature graphic (1024x500)
  splash.png             # Splash screen source image
```

After design approval, copy the appropriate files to `mobile/assets/` to replace the placeholders.
