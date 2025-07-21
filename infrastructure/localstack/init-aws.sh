#!/bin/bash

# Création des buckets S3
echo "Création des buckets S3..."
awslocal s3 mb s3://media-summarizer-audio
awslocal s3 mb s3://media-summarizer-transcripts
awslocal s3 mb s3://media-summarizer-summaries

# Création des files SQS
echo "Création des files SQS..."
awslocal sqs create-queue --queue-name rss-resolution-queue
awslocal sqs create-queue --queue-name audio-download-queue
awslocal sqs create-queue --queue-name transcription-queue
awslocal sqs create-queue --queue-name summarization-queue
awslocal sqs create-queue --queue-name email-notification-queue

# Configuration de SES (Simple Email Service)
echo "Configuration de SES..."
awslocal ses verify-email-identity --email-address noreply@media-summarizer.com

echo "Initialisation AWS terminée!"