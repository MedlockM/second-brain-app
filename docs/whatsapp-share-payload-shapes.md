# WhatsApp Share Payload Shapes - Device Validation

This document captures the expected payload shapes observed from real WhatsApp text and audio shares on Android and iOS. It guides the dispatch logic in the mobile share intent handlers.

## Android Payloads

### Text Message Share (Forward/Share)

When a user long-presses a WhatsApp text message and selects "Share" -> Media Summarizer:

| Field | Value |
|-------|-------|
| Intent action | `android.intent.action.SEND` |
| MIME type | `text/plain` |
| EXTRA_TEXT | Raw message text (e.g., "Hey check this podcast it's amazing") |
| EXTRA_SUBJECT | Usually absent or sender name |
| Source package | `com.whatsapp` or `com.whatsapp.w4b` (Business) |

Notes:
- If the text message contains a URL, `EXTRA_TEXT` will contain the full text including the URL.
- WhatsApp may prepend the sender name in some locales.
- Group messages may include a prefix like "[Group Name]: ".

### Text Message with URL

Same as above but `EXTRA_TEXT` contains an embedded URL:

| Field | Value |
|-------|-------|
| Intent action | `android.intent.action.SEND` |
| MIME type | `text/plain` |
| EXTRA_TEXT | e.g., "Check this out https://example.com/article super interesting" |

### Voice Message Share

When a user long-presses a WhatsApp voice note and selects "Share" -> Media Summarizer:

| Field | Value |
|-------|-------|
| Intent action | `android.intent.action.SEND` |
| MIME type | `audio/ogg` (WhatsApp voice notes use Opus codec in OGG container) |
| EXTRA_STREAM | `content://com.whatsapp.provider.media/...` or temp file URI |
| Filename pattern | `PTT-YYYYMMDD-WAXXXX.opus` (voice note) or `AUD-YYYYMMDD-WAXXXX.opus` |
| Typical size | 10 KB - 16 MB (WhatsApp limit: 16 MB for media) |

Notes:
- The `content://` URI is a temporary provider URI that must be read immediately.
- WhatsApp Business (`com.whatsapp.w4b`) uses the same patterns.
- Older WhatsApp versions may use `.ogg` extension instead of `.opus`.

### Audio File Attachment Share

When a user shares an audio file that was sent as a document/attachment in WhatsApp:

| Field | Value |
|-------|-------|
| Intent action | `android.intent.action.SEND` |
| MIME type | Varies: `audio/mpeg`, `audio/mp4`, `audio/ogg`, `audio/x-m4a` |
| EXTRA_STREAM | `content://com.whatsapp.provider.media/...` |
| Filename pattern | Original filename preserved (e.g., `podcast-episode.mp3`) |

## iOS Payloads

### Text Message Share

When a user long-presses a WhatsApp text message and selects "Share" -> Media Summarizer:

| Field | Value |
|-------|-------|
| NSExtensionItem type | `public.plain-text` (kUTTypePlainText / UTType.plainText) |
| Data | String containing the message text |
| Source | WhatsApp (no bundle ID exposed to share extension) |

Notes:
- iOS share extensions cannot determine the source app identity.
- The text is provided as a raw `String` via `NSItemProvider.loadItem`.

### Text Message with URL

Same as text share, but the string contains an embedded URL:

| Field | Value |
|-------|-------|
| NSExtensionItem type | `public.url` or `public.plain-text` |
| Data | URL object or string with URL |

Notes:
- WhatsApp may provide the URL as a proper `public.url` type if the message is a link-only message.
- If the message has text around the URL, it comes as `public.plain-text`.

### Voice Message Share

When a user long-presses a WhatsApp voice note and selects "Share" -> Media Summarizer:

| Field | Value |
|-------|-------|
| NSExtensionItem type | `public.audio` (UTType.audio) |
| Subtype | `com.apple.m4a-audio` or `public.mpeg-4-audio` |
| Data | File URL to temporary `.m4a` file |
| Filename pattern | `PTT-YYYYMMDD-WAXXXX.m4a` or auto-generated |
| MIME equivalent | `audio/mp4` |
| Typical size | 10 KB - 16 MB |

Notes:
- On iOS, WhatsApp transcodes voice notes to M4A (AAC in MP4 container) before sharing.
- The file is in a temporary directory; the share extension must copy it to the App Group container.
- Older iOS versions of WhatsApp may share as `.opus` in rare cases.

### Audio File Attachment Share

When a user shares an audio file that was sent as a document in WhatsApp:

| Field | Value |
|-------|-------|
| NSExtensionItem type | `public.audio` or `public.data` with audio UTI |
| Subtype | Matches original file (e.g., `public.mp3` for MP3 files) |
| Data | File URL to temporary file |
| Filename pattern | Original filename preserved |

## Dispatch Logic Summary

```
Incoming share payload
  |
  +-- Has audio file attachment? (MIME starts with audio/ or has audio UTI)
  |     |
  |     +-- MIME type supported? --> Route to ingest-shared-content (audio)
  |     +-- MIME type unsupported? --> Show error: "Unsupported audio format"
  |
  +-- Has text content?
        |
        +-- Contains URL? --> Route to ingest-url (existing flow)
        +-- No URL found? --> Route to ingest-shared-content (text)
```

## Known Edge Cases

1. **WhatsApp "View Once" media**: Cannot be shared via the share sheet; no handling needed.
2. **WhatsApp Status shares**: Come as video (`video/mp4`), not handled in this scope.
3. **Multi-file shares**: WhatsApp sends one file at a time; we accept max 1 attachment.
4. **Large voice messages**: WhatsApp limits voice notes to ~16 MB. Our limit is 25 MB to provide headroom.
5. **Network interruption during upload**: The mobile app should show a clear error and allow retry.
6. **Duplicate prevention**: Idempotency keys based on content hash + time window prevent double-ingestion from rapid double-taps or Android intent re-delivery.

## Platform Differences Summary

| Aspect | Android | iOS |
|--------|---------|-----|
| Voice note codec | Opus in OGG | AAC in M4A (transcoded) |
| Voice note extension | `.opus` | `.m4a` |
| Voice note MIME | `audio/ogg` | `audio/mp4` |
| File access | `content://` URI (temporary) | File URL (temporary) |
| Source app detection | Package name available | Not available |
| Text share format | EXTRA_TEXT string | NSItemProvider string |
