#!/bin/bash

echo "Setting up Dead Letter Queues..."

# Créer les DLQ
awslocal sqs create-queue --queue-name audio-download-dlq
awslocal sqs create-queue --queue-name transcription-dlq
awslocal sqs create-queue --queue-name summarization-dlq
awslocal sqs create-queue --queue-name email-notification-dlq

# Obtenir les ARNs des DLQ
DOWNLOAD_DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url http://localhost:4566/000000000000/audio-download-dlq --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
TRANSCRIPTION_DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url http://localhost:4566/000000000000/transcription-dlq --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
SUMMARIZATION_DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url http://localhost:4566/000000000000/summarization-dlq --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)
EMAIL_DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url http://localhost:4566/000000000000/email-notification-dlq --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

# Configurer les redrive policies (après 3 échecs, envoyer vers DLQ)
# Configurer les politiques de redirection vers DLQ
awslocal sqs set-queue-attributes \
    --queue-url http://localhost:4566/000000000000/audio-download-queue \
    --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DOWNLOAD_DLQ_ARN\\\",\\\"maxReceiveCount\\\":3}\"}"

awslocal sqs set-queue-attributes \
    --queue-url http://localhost:4566/000000000000/transcription-queue \
    --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$TRANSCRIPTION_DLQ_ARN\\\",\\\"maxReceiveCount\\\":3}\"}"

awslocal sqs set-queue-attributes \
    --queue-url http://localhost:4566/000000000000/summarization-queue \
    --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$SUMMARIZATION_DLQ_ARN\\\",\\\"maxReceiveCount\\\":3}\"}"

awslocal sqs set-queue-attributes \
    --queue-url http://localhost:4566/000000000000/email-notification-queue \
    --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$EMAIL_DLQ_ARN\\\",\\\"maxReceiveCount\\\":3}\"}"

echo "✅ Dead Letter Queues configured successfully!"
