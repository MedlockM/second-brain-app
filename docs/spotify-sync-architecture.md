# Spotify Sync Architecture

This document describes the infrastructure architecture for the Spotify Sync feature, which automatically processes podcast episodes from users' Spotify playlists.

## Overview

The Spotify Sync feature follows a serverless, event-driven architecture that is consistent between development and production environments. The main difference is in how the components are deployed and executed.

---

## Development Architecture (LocalStack)

In development, we use **LocalStack** to emulate AWS services. Lambda functions are deployed as zip packages and triggered by emulated EventBridge and SQS.

```mermaid
flowchart TB
    subgraph LocalStack["LocalStack (Docker)"]
        subgraph EventBridge["EventBridge"]
            EB_RULE[/"spotify-sync-schedule<br/>rate(1 minute)"/]
        end
        
        subgraph Lambda["Lambda Functions"]
            DISPATCHER["spotify-sync-dispatcher<br/>(Python 3.11, zip)"]
            WORKER["spotify-sync-worker<br/>(Python 3.11, zip)"]
        end
        
        subgraph SQS["SQS Queues"]
            SYNC_QUEUE[["spotify-sync-queue"]]
            DOWNLOAD_QUEUE[["audio-download-queue"]]
        end
        
        subgraph DynamoDB["DynamoDB Tables"]
            USERS[(users)]
            FOLLOWS[(spotify_playlist_follows)]
            JOBS[(processing_jobs)]
        end
    end
    
    subgraph External["External APIs"]
        SPOTIFY_API["Spotify API"]
        PODCAST_INDEX["PodcastIndex API"]
    end
    
    subgraph Processing["Processing Pipeline (Docker)"]
        DOWNLOAD_WORKER["download-worker"]
        WHISPER["whisper"]
        SUMMARIZE["summarize-worker"]
        QUIZ["quiz-worker"]
        EMAIL["email-worker"]
    end

    %% Event Flow
    EB_RULE -->|"Triggers every minute"| DISPATCHER
    DISPATCHER -->|"Scan enabled follows"| FOLLOWS
    DISPATCHER -->|"Send job per user"| SYNC_QUEUE
    
    SYNC_QUEUE -->|"Event Source Mapping"| WORKER
    WORKER -->|"Get user data"| USERS
    WORKER -->|"Get playlist follows"| FOLLOWS
    WORKER -->|"Fetch recently played"| SPOTIFY_API
    WORKER -->|"Lookup podcast feed"| PODCAST_INDEX
    WORKER -->|"Create processing job"| JOBS
    WORKER -->|"Submit episode"| DOWNLOAD_QUEUE
    
    DOWNLOAD_QUEUE --> DOWNLOAD_WORKER
    DOWNLOAD_WORKER --> WHISPER
    WHISPER --> SUMMARIZE
    SUMMARIZE --> QUIZ
    QUIZ --> EMAIL

    style LocalStack fill:#f5f5f5,stroke:#333
    style EventBridge fill:#ff9900,stroke:#333,color:#000
    style Lambda fill:#ff9900,stroke:#333,color:#000
    style SQS fill:#ff4f8b,stroke:#333,color:#fff
    style DynamoDB fill:#4053d6,stroke:#333,color:#fff
    style External fill:#e8f5e9,stroke:#333
    style Processing fill:#e3f2fd,stroke:#333
```

### Dev Environment Details

| Component | Implementation | Notes |
|-----------|---------------|-------|
| EventBridge | LocalStack emulation | `rate(1 minute)` schedule |
| Lambda Functions | Zip packages (21 MB) | Built via `deploy_lambdas_localstack.sh` |
| SQS | LocalStack emulation | Event source mapping enabled |
| DynamoDB | LocalStack emulation | Persistent via volume mount |
| Processing Workers | Docker containers | Run via docker-compose |

### Deployment Commands (Dev)

```bash
# Start LocalStack and apply Terraform
docker-compose --env-file .env.dev -f docker-compose.dev.yml up -d localstack
docker-compose --env-file .env.dev -f docker-compose.dev.yml up terraform

# Deploy Lambda functions
./scripts/deploy_lambdas_localstack.sh

# Start processing workers
docker-compose --env-file .env.dev -f docker-compose.dev.yml up -d \
  download-worker whisper summarize-worker quiz-worker email-worker
```

---

## Production Architecture (AWS)

In production, we use native AWS services. Lambda functions are deployed as **Docker container images** stored in ECR for better performance and dependency management.

```mermaid
flowchart TB
    subgraph AWS["AWS Cloud"]
        subgraph EventBridge["Amazon EventBridge"]
            EB_RULE[/"spotify-sync-schedule<br/>cron(0 4 * * ? *)"/]
        end
        
        subgraph Lambda["AWS Lambda"]
            DISPATCHER["spotify-sync-dispatcher<br/>(Container Image, 256 MB)"]
            WORKER["spotify-sync-worker<br/>(Container Image, 512 MB)"]
        end
        
        subgraph ECR["Amazon ECR"]
            LAMBDA_IMAGE[["media-summarizer-lambda:latest"]]
        end
        
        subgraph SQS["Amazon SQS"]
            SYNC_QUEUE[["spotify-sync-queue"]]
            SYNC_DLQ[["spotify-sync-dlq"]]
            DOWNLOAD_QUEUE[["audio-download-queue"]]
        end
        
        subgraph DynamoDB["Amazon DynamoDB"]
            USERS[(users)]
            FOLLOWS[(spotify_playlist_follows)]
            JOBS[(processing_jobs)]
        end
        
        subgraph CloudWatch["Amazon CloudWatch"]
            LOGS[/"Lambda Logs"/]
            ALARMS[/"DLQ Alarms"/]
        end
        
        subgraph ECS["Amazon ECS / Fargate"]
            DOWNLOAD_WORKER["download-worker"]
            WHISPER["whisper-worker"]
            SUMMARIZE["summarize-worker"]
            QUIZ["quiz-worker"]
            EMAIL["email-worker"]
        end
        
        subgraph S3["Amazon S3"]
            AUDIO[("audio bucket")]
            TRANSCRIPTS[("transcripts bucket")]
            SUMMARIES[("summaries bucket")]
        end
    end
    
    subgraph External["External APIs"]
        SPOTIFY_API["Spotify API"]
        PODCAST_INDEX["PodcastIndex API"]
    end

    %% Lambda Image Source
    LAMBDA_IMAGE -.->|"Image source"| DISPATCHER
    LAMBDA_IMAGE -.->|"Image source"| WORKER

    %% Event Flow
    EB_RULE -->|"Triggers daily at 4 AM UTC"| DISPATCHER
    DISPATCHER -->|"Scan enabled follows"| FOLLOWS
    DISPATCHER -->|"Send job per user"| SYNC_QUEUE
    
    SYNC_QUEUE -->|"Event Source Mapping"| WORKER
    SYNC_QUEUE -->|"Failed messages"| SYNC_DLQ
    WORKER -->|"Get user data"| USERS
    WORKER -->|"Get playlist follows"| FOLLOWS
    WORKER -->|"Fetch recently played"| SPOTIFY_API
    WORKER -->|"Lookup podcast feed"| PODCAST_INDEX
    WORKER -->|"Create processing job"| JOBS
    WORKER -->|"Submit episode"| DOWNLOAD_QUEUE
    
    DISPATCHER -->|"Logs"| LOGS
    WORKER -->|"Logs"| LOGS
    SYNC_DLQ -->|"Alert on messages"| ALARMS
    
    DOWNLOAD_QUEUE --> DOWNLOAD_WORKER
    DOWNLOAD_WORKER --> AUDIO
    DOWNLOAD_WORKER --> WHISPER
    WHISPER --> TRANSCRIPTS
    WHISPER --> SUMMARIZE
    SUMMARIZE --> SUMMARIES
    SUMMARIZE --> QUIZ
    QUIZ --> EMAIL

    style AWS fill:#232f3e,stroke:#ff9900,color:#fff
    style EventBridge fill:#ff9900,stroke:#333,color:#000
    style Lambda fill:#ff9900,stroke:#333,color:#000
    style ECR fill:#ff9900,stroke:#333,color:#000
    style SQS fill:#ff4f8b,stroke:#333,color:#fff
    style DynamoDB fill:#4053d6,stroke:#333,color:#fff
    style CloudWatch fill:#ff4f8b,stroke:#333,color:#fff
    style ECS fill:#ff9900,stroke:#333,color:#000
    style S3 fill:#3f8624,stroke:#333,color:#fff
    style External fill:#e8f5e9,stroke:#333,color:#000
```

### Prod Environment Details

| Component | Implementation | Notes |
|-----------|---------------|-------|
| EventBridge | Native AWS | `cron(0 4 * * ? *)` - Daily at 4 AM UTC |
| Lambda Functions | Container Images (ECR) | Faster cold starts, better dependency management |
| SQS | Native AWS with DLQ | Dead Letter Queue for failed messages |
| DynamoDB | Native AWS | On-demand capacity mode |
| Processing Workers | ECS Fargate | Auto-scaling based on queue depth |
| Monitoring | CloudWatch | Logs, metrics, and alarms |

### Deployment Commands (Prod)

```bash
# Build and push Lambda container image
docker build -t media-summarizer-lambda:latest -f infrastructure/docker/lambda.Dockerfile .
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag media-summarizer-lambda:latest <account>.dkr.ecr.<region>.amazonaws.com/media-summarizer-lambda:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/media-summarizer-lambda:latest

# Apply Terraform
cd infrastructure/terraform/aws
terraform init
terraform apply -var="ecr_repository_url=<account>.dkr.ecr.<region>.amazonaws.com/media-summarizer-lambda"
```

---

## Key Differences: Dev vs Prod

| Aspect | Development | Production |
|--------|-------------|------------|
| **EventBridge Schedule** | `rate(1 minute)` | `cron(0 4 * * ? *)` (daily) |
| **Lambda Packaging** | Zip files (21 MB) | Container images (ECR) |
| **Lambda Cold Start** | Slower (LocalStack limitation) | Fast (AWS optimized) |
| **Dead Letter Queues** | Optional | Configured with alarms |
| **Monitoring** | Docker logs | CloudWatch Logs + Alarms |
| **Processing Workers** | Docker Compose | ECS Fargate |
| **AWS Endpoint** | `http://localhost:4566` | Native AWS endpoints |

---

## Data Flow Summary

1. **EventBridge** triggers the **Dispatcher Lambda** on schedule
2. **Dispatcher** scans `spotify_playlist_follows` for enabled playlists
3. **Dispatcher** sends one SQS message per user to `spotify-sync-queue`
4. **SQS Event Source Mapping** triggers **Worker Lambda** for each message
5. **Worker** fetches the user's recently played episodes from Spotify API
6. **Worker** filters episodes by listen threshold (80%+)
7. **Worker** looks up podcast feed URLs via PodcastIndex API
8. **Worker** creates processing jobs and submits to `audio-download-queue`
9. **Processing Pipeline** handles download → transcription → summarization → quiz → email

---

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/deploy_lambdas_localstack.sh` | Deploy Lambdas to LocalStack (dev) |
| `infrastructure/docker/lambda.Dockerfile` | Lambda container image (prod) |
| `infrastructure/terraform/localstack/main.tf` | LocalStack infrastructure (dev) |
| `infrastructure/terraform/aws/spotify_sync.tf` | AWS infrastructure (prod) |
| `media_summarizer/workers/spotify_sync/dispatcher.py` | Dispatcher Lambda handler |
| `media_summarizer/workers/spotify_sync/worker.py` | Worker Lambda handler |