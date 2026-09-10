# User-facing error messages

The audit of every message a person can be shown when something fails, and the
two rules it enforces. Produced by task-397; this file replaces
`ERROR_HANDLING_BEST_PRACTICES.md`, which described an error envelope
(`{error: {code, message, request_id}}`) the API never shipped and recommended
putting a request id on screen — the opposite of rule 1.

## The two rules

**Rule 1 — a displayed message carries no technical detail.** No exception name,
no HTTP status, no stack, no function, file, module, bucket or table name, no
internal identifier, no raw text from a library or from the OS. Every one of
those is a fact for whoever fixes the bug, so it goes to a log.

**Rule 2 — a message says what to do, and only when there is something to do.**
A failure the reader caused names the way out (`error.invalidCredentials`,
`upload.reject.tooLarge`). A failure they did not cause must not suggest an
action that cannot work: a local file the app could not open showed "Check your
connection and try again" with no network anywhere in the path.

Corollary, and the reason rule 1 is not merely about taste: **a displayed message
becomes an App Store Connect screenshot.** It can never carry a user's file name
(which is the title of their note), an e-mail address, or an account identifier.

## Where the text lives

One path, from task-359, and nothing else is allowed:

1. The server emits a **stable code**, never prose meant for a screen. A typed
   refusal sends `detail` as an object — `{"error_code": "...", "message": "..."}`
   — which `parseErrorResponse` turns into `HttpError.code`.
2. `mobile/src/lib/getFriendlyErrorMessage.ts` maps that code to a catalogue key
   and resolves it **at call time**, so the sentence is in the reader's current
   language rather than the one the app started in.
3. The 11 catalogues in `mobile/src/i18n/` hold the text.

`getFriendlyErrorMessage` returns `t(key)` or the caller's `fallback` on every
branch. The thrown text is only ever *matched against*; it is never returned.
That is what makes rule 1 structural rather than a thing to re-verify: the only
way an API `detail`, an S3 XML body or a `TypeError` can reach a screen is a call
site that reads `error.message` itself.

**A hardcoded English string in a component is a defect**, even a correct one:
ten readers out of eleven get it in the wrong language.

## What was wrong, and what it is now

### The trigger — "Technical details" on the share confirmation screen

A beta tester reported the block as "beaucoup trop technique pour un user". It
rendered `stage=put_rejected · status=403 · s3=SignatureDoesNotMatch · bytes=…`
under a label, with a hint asking the reader to quote it in a report.

Deleted, not reshaped. `upload.diagnostics.title` and `upload.diagnostics.hint`
are gone from all 11 catalogues, and the diagnostics line now goes to
`console.error` in `presignedUpload.ts`. Nothing was lost: the line still exists,
in the place where the person who reads it works.

The single sentence it sat under was the second half of the defect. It said
"This file could not be sent. Check your connection and try again." for all three
ways a transfer can fail — including `read_file`, where nothing was ever sent.
It is now one sentence per stage:

| Stage | Key | Says |
| --- | --- | --- |
| `read_file` | `upload.transferFailed.read` | Open it in the app it came from, then share it again |
| `put_network` | `upload.transferFailed.network` | Check your connection and try again |
| `put_rejected` | `upload.transferFailed.rejected` | Try importing it again |

### Mobile call sites that rendered a raw message

| Location | Was | Verdict | Now |
| --- | --- | --- | --- |
| `app/share-confirmation.tsx` | `upload.diagnostics.*` block | Rule 1 | Deleted; diagnostics to `console.error` |
| `src/services/presignedUpload.ts` | one sentence for three stages, `readonly detail` on the error | Rules 1 + 2 | `STAGE_MESSAGE_KEYS`, no `detail` field |
| `src/contexts/ShareIntentContext.tsx` | `uploadDiagnostics` in the intake state; 3 hardcoded English fallbacks | Rules 1 + 3 | Field removed; `share.saveLinkFailed` / `share.saveContentFailed` / `share.importFileFailed` |
| `src/components/StartupErrorScreen.tsx` | name, message, stack of the exception behind a "Show technical details" toggle | Rule 1 | Props reduced to `onRetry`; both nets already log the cause |
| `app/bug-report.tsx` | `error.message` from the API; the ticket UUID shown on success | Rule 1 | `getFriendlyErrorMessage` with `bugReport.submitFailed`; UUID deleted |
| `app/(tabs)/search.tsx` | `err instanceof Error ? err.message : …` | Rule 1 | `getFriendlyErrorMessage` with `search.failed` |
| `src/services/purchaseService.ts` → `app/paywall.tsx` | the RevenueCat SDK's own `error.message` in an alert | Rule 1 | `PurchaseFailureCode`, six codes, five sentences |
| `src/services/sharedContentService.ts` | three English throws, one quoting `file.mimeType` | Rules 1 + 3 | `validateSharedAudioFile` in `types/sharedContent.ts` |
| `src/services/bugReportService.ts` | `throw new Error("Upload failed with status " + status)` | Rule 1 | `BugReportAttachmentError`, code `ATTACHMENT_UPLOAD_FAILED`, detail logged |
| `src/components/SocialAuthButtons.tsx` | "Failed to obtain Google ID token", "Failed to obtain Apple identity token" | Rule 1 | `auth.google.failed` / `auth.apple.failed` |
| `src/lib/getFriendlyErrorMessage.ts` | default was `common.error`, the single word "Error" | Rule 2 | `error.unexpected`, which says it is on us and worth retrying |

Six call sites called `getFriendlyErrorMessage` with no `fallback`, so an
unrecognised failure read as the generic sentence where a specific one existed:
`(auth)/login.tsx`, `(auth)/register.tsx`, `settings/delete-account.tsx`,
`settings/reading-language.tsx`, `onboarding/language.tsx`,
`hooks/useMediaDetailPolling.ts`. Each now passes one.

`isActionableError` was deleted — no callers, and the distinction it drew is the
one the catalogue already makes by wording.

### API refusals that echoed an exception

Each of these put `str(exc)` or French prose on the wire. The exception now goes
to a log and the answer carries a code or a neutral sentence.

| Location | Was | Now |
| --- | --- | --- |
| `media.py` `InvalidUrlError` | `str(exc)` — the parser's account of the URL | `{"error_code": "INVALID_URL"}` → `error.invalidUrl` |
| `media.py` `UnsupportedUrlError` | `str(exc)` | `{"error_code": "UNSUPPORTED_URL"}` → `error.unsupportedUrl` |
| `media.py` `ResolutionError` | `Resolver 'X' failed: <raw exception>` | "This shared content could not be read" |
| `media.py` `PATCH` `ValueError` | `Folder <uuid> not found` | "This change was refused" |
| `media.py` folder resolution | `Folder not found: <uuid>` | "Folder not found" |
| `folders.py` × 3 | `str(e)` — ids, the depth ceiling, "does not belong to this user" | `REJECTED_FOLDER_DETAIL` |
| `engagements.py` | `str(exc)` | "Subject not found" |
| `artifacts.py` `ArtifactTypeNotEnabledError` | `str(exc)` — internal enum member and scope | `{"error_code": "INVALID_ARTIFACT_TYPE"}` |
| `auth.py` reading language | `Supported: ['ar', 'de', …]`, a Python list repr | comma-joined |
| `health.py` | `Service unhealthy: <boto exception>` | "Service unhealthy" |
| `feeds.py` `_raise_service_error` | `exc.message`, up to an expat `SAXParseException` naming a line and column in someone else's XML | one neutral sentence per `FeedServiceError`, code on the wire |
| `podcast_search.py` × 12, `podcasts.py` × 2 | French prose, `str(e)`, "Erreur lors de la recherche dans Podcast Index" | English, no exception text, no provider name |
| `podcast_search.py` insufficient credits | French fallback sentence, taken from the submission's own `message` field | `{"error_code": "INSUFFICIENT_MINUTES"}` → `error.outOfMinutes` |

## Left as they are, and why

- **`error.network`** — "Network error. Please check your connection and try
  again." Names no technology and the action works. The defect was never this
  sentence; it was showing it when no network was involved.
- **`quotaError.ts`** — builds its sentence client-side from `t()` plus the
  figures the backend sent (`minutes_needed`, `period_end`, `has_plan`). It does
  not go through `getFriendlyErrorMessage` on purpose: those figures are what
  make the refusal specific instead of generic.
- **`media.py` internal-contract refusals** — `Malformed upload_key: it must end
  with the uploaded file name`, `Invalid share_type: …`, `Field 'text' is
  required …`, the MIME-type refusal on `/upload-url`. These name request fields,
  which is right: only a client sending a malformed body can reach them, the app
  validates every one of them first, and no screen renders them.
- **`media.py` raw-content 404** — `RawContentNotAvailableError`'s text is
  neutral English with nothing technical in it.
- **`account.py:48`** — `detail=str(exc)[:500]` is a **log field**, not an
  HTTPException detail. The 500 answers "Account deletion failed. Please try
  again."
- **`revenucat_webhook.py`, `apify_webhook.py`** — a provider reads these, not a
  person.
- **`error_message` on jobs and artifacts** — the workers write things like
  `s3_download_failed: ClientError: …` there, and that is fine: no response model
  exposes the field and no screen reads it. `GET /api/media/{id}` dropped it
  (see the note at `media.py:635`); the client renders `error_code` through the
  catalogue. There is no `user_message` anywhere in `media_summarizer/`.
- **`settings/interface-language.tsx`** — hardcoded English pseudo-localisation
  copy, `__DEV__`-only, documented in place.
- **Confirmation dialogs and a11y labels that echo the reader's own title**
  (`mediaActions.deleteBody`, `folderActions.deleteBody`, `media.movedToNamed`,
  `search.openFolderA11y`, `unsortedReview.discardA11y`). The
  never-a-file-name rule belongs to *error* messages: naming what is about to be
  deleted is the whole point of a confirmation. `deleteAccount.emailA11y` shows
  our privacy contact address, not the reader's.

## Checking it stays true

- `getFriendlyErrorMessage` must keep returning only `t(key)` or `fallback`. A
  branch that returns `errorMessage` reopens every leak at once.
- No call site may read `error.message` for display. `grep -rn "\.message" mobile/app mobile/src`
  should only find state objects whose message came from `t()` or from
  `getFriendlyErrorMessage`.
- The 11 catalogues must hold the same key set. `tsc` catches a *missing* key
  (`Catalog = Record<TranslationKey, string> & Record<string, string>`) but not an
  extra one, so a removal has to be applied to all 11 by hand. Arabic carries 51
  extra keys legitimately: its plural categories (`.zero`, `.two`, `.few`,
  `.many`).
- A new API refusal sends a code, not a sentence to display.
