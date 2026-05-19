# Privacy Policy

**Media Summarizer**
**Last updated:** 2026-05-19
**Effective date:** 2026-05-19

## 1. Introduction

Media Summarizer ("we", "us", "our") operates the Media Summarizer mobile application (the "Service"). This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our Service.

By using the Service, you agree to the collection and use of information in accordance with this policy.

## 2. Information We Collect

### 2.1 Account Information

When you create an account, we collect:

- **Email address** - used for authentication, account recovery, and service communications
- **Password** - stored in hashed form; we never store or have access to your plaintext password

### 2.2 User-Submitted Content

When you use the Service, we collect:

- **URLs you share** - web articles, podcast episodes, YouTube videos, and other media links you submit for processing
- **Source application metadata** - which app you shared from (e.g., Safari, YouTube, Spotify)

### 2.3 Generated Content

The Service creates and stores:

- **Transcripts** - text transcriptions of audio/video content
- **Summaries** - AI-generated summaries of your submitted media
- **Notes** - AI-generated study notes
- **Quizzes** - AI-generated flashcards and quiz questions

### 2.4 Usage Data

We automatically collect:

- **App usage analytics** - screens visited, features used, session duration
- **Device information** - device model, operating system version, app version
- **Crash reports** - error logs to improve app stability

### 2.5 Information We Do NOT Collect

- We do not collect location data
- We do not access your contacts, photos, or camera (except photo library access if you explicitly attach an image)
- We do not collect financial or payment information directly (handled by Apple/Google)
- We do not collect health, fitness, or biometric data

## 3. How We Use Your Information

We use your information for the following purposes:

| Purpose | Data Used |
|---------|-----------|
| Provide the Service | Email, URLs, generated content |
| Authentication | Email, password hash |
| Content processing | Submitted URLs, transcripts |
| AI artifact generation | Transcripts |
| Service improvement | Usage analytics, crash reports |
| Account communications | Email address |

## 4. How We Process Your Data

### 4.1 Transcription

Audio and video content from your submitted URLs is transcribed using **Deepgram**, a third-party speech-to-text service. Deepgram processes audio data to produce text transcripts. Deepgram's privacy policy applies to their processing of this data. Deepgram does not retain audio data after transcription is complete.

### 4.2 AI Generation

Transcripts and extracted text are processed by **OpenAI** GPT models to generate summaries, notes, and quizzes. OpenAI processes text data according to their API data usage policy. When using the API, OpenAI does not use submitted data to train their models.

### 4.3 Data Flow Summary

```
User submits URL -> Our backend fetches content -> Deepgram transcribes audio
-> OpenAI generates artifacts -> Results stored in our infrastructure
```

## 5. Data Storage and Security

### 5.1 Infrastructure

All data is stored on **Amazon Web Services (AWS)** infrastructure:

- **DynamoDB** - account data, media metadata, artifact content
- **S3** - transcript files, processed content
- **SQS** - job processing queues (transient, messages deleted after processing)

### 5.2 Security Measures

- All data in transit is encrypted via TLS 1.2+
- Data at rest is encrypted using AWS-managed encryption keys
- Authentication tokens are stored securely on-device using platform-native secure storage (iOS Keychain / Android Keystore)
- Passwords are hashed using industry-standard algorithms before storage
- Access to production infrastructure is restricted and audited

### 5.3 Data Location

Our infrastructure is hosted in AWS regions within the United States. By using the Service, you consent to your data being transferred to and processed in the United States.

## 6. Data Sharing and Third Parties

We share data with the following third-party services solely for the purpose of providing the Service:

| Service | Data Shared | Purpose |
|---------|-------------|---------|
| Deepgram | Audio content from URLs | Transcription |
| OpenAI | Text content, transcripts | AI artifact generation |
| Amazon Web Services | All stored data | Infrastructure hosting |

We do NOT:

- Sell your personal data to third parties
- Share your data for advertising purposes
- Allow third parties to use your data for their own purposes beyond providing our Service
- Use your data for cross-app tracking

## 7. Data Retention

- **Account data** - retained as long as your account is active
- **Submitted URLs and generated artifacts** - retained as long as your account is active
- **Usage analytics** - retained for up to 12 months, then aggregated or deleted
- **Crash reports** - retained for up to 6 months

After account deletion, all your data is permanently removed within 30 days, except where retention is required by law.

## 8. Your Rights

You have the following rights regarding your data:

### 8.1 Access

You can view all your submitted media, generated artifacts, and account information directly within the app.

### 8.2 Deletion

- **Individual items** - you can delete any media item and its associated artifacts at any time
- **Account deletion** - you can request full account deletion, which removes all your data from our systems within 30 days

### 8.3 Data Export

You can request an export of all your data (submitted URLs, transcripts, generated artifacts) by contacting us at the address below.

### 8.4 Correction

You can update your email address through the app's account settings.

### 8.5 Withdrawal of Consent

You can stop using the Service at any time. Deleting your account removes your data as described above.

## 9. Children's Privacy

The Service is not intended for children under the age of 13 (or the applicable age of digital consent in your jurisdiction). We do not knowingly collect personal information from children. If we become aware that a child has provided us with personal information, we will take steps to delete such information.

## 10. Changes to This Policy

We may update this Privacy Policy from time to time. We will notify you of material changes by:

- Posting the updated policy within the app
- Updating the "Last updated" date at the top of this document
- Sending an email notification for significant changes

Your continued use of the Service after changes are posted constitutes acceptance of the updated policy.

## 11. Contact Us

If you have questions about this Privacy Policy or wish to exercise your data rights, please contact us at:

**Email:** privacy@mediasummarizer.com

## 12. Additional Disclosures

### For California Residents (CCPA)

- We do not sell personal information
- We do not use personal information for cross-context behavioral advertising
- You have the right to know, delete, and opt-out as described in this policy

### For European Residents (GDPR)

- Legal basis for processing: contract performance (providing the Service) and legitimate interests (analytics, security)
- You have additional rights including data portability and the right to lodge a complaint with a supervisory authority
- Data transfers outside the EEA are protected by Standard Contractual Clauses

### For Australian Residents (Privacy Act 1988)

- We handle personal information in accordance with the Australian Privacy Principles
- You may lodge a complaint with the Office of the Australian Information Commissioner
