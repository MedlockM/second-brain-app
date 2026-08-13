#!/usr/bin/env bash
#
# bootstrap_tf_backend.sh — create the S3 state bucket and the DynamoDB lock table
# an environment root needs BEFORE `terraform init` can run against it.
#
# This is the one part of the infrastructure Terraform cannot own: a backend
# cannot create the bucket that holds its own state. It is idempotent, so it is
# safe to re-run.
#
# Why it exists (task-248): prod moved to its own AWS Organizations member
# account, and `media-summarizer-tfstate-lock` in the dev/management account is
# not reachable from there. Each account needs its own bucket AND its own lock
# table; sharing one lock table across accounts would mean granting cross-account
# write access to the thing whose whole job is to be trustworthy.
#
# Usage:
#   AWS_PROFILE=prod scripts/bootstrap_tf_backend.sh
#   AWS_PROFILE=prod scripts/bootstrap_tf_backend.sh eu-west-3
#
# The bucket is named media-summarizer-tfstate-<account-id> so the name is
# derived, never guessed.

set -euo pipefail

REGION="${1:-eu-west-3}"
LOCK_TABLE="media-summarizer-tfstate-lock"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="media-summarizer-tfstate-${ACCOUNT_ID}"

echo "account   ${ACCOUNT_ID}"
echo "region    ${REGION}"
echo "bucket    ${BUCKET}"
echo "lock      ${LOCK_TABLE}"
echo

if aws s3api head-bucket --bucket "${BUCKET}" 2>/dev/null; then
  echo "bucket already exists"
else
  aws s3api create-bucket \
    --bucket "${BUCKET}" \
    --region "${REGION}" \
    --create-bucket-configuration "LocationConstraint=${REGION}" >/dev/null
  echo "bucket created"
fi

# Versioning is the rollback net for every state surgery: any bad `state rm` or
# truncated write is recoverable by restoring an object version.
aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" --region "${REGION}" \
  --versioning-configuration Status=Enabled
echo "versioning enabled"

aws s3api put-bucket-encryption \
  --bucket "${BUCKET}" --region "${REGION}" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'
echo "SSE-S3 encryption enabled"

aws s3api put-public-access-block \
  --bucket "${BUCKET}" --region "${REGION}" \
  --public-access-block-configuration \
  'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
echo "public access blocked"

# The state carries plaintext secrets in a few places, so TLS is not optional.
aws s3api put-bucket-policy \
  --bucket "${BUCKET}" --region "${REGION}" \
  --policy "$(
    cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": ["arn:aws:s3:::${BUCKET}", "arn:aws:s3:::${BUCKET}/*"],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } }
    }
  ]
}
JSON
  )"
echo "insecure-transport denied"

if aws dynamodb describe-table --table-name "${LOCK_TABLE}" --region "${REGION}" >/dev/null 2>&1; then
  echo "lock table already exists"
else
  aws dynamodb create-table \
    --table-name "${LOCK_TABLE}" \
    --region "${REGION}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --table-name "${LOCK_TABLE}" --region "${REGION}"
  echo "lock table created"
fi

echo
echo "backend block for this account:"
cat <<HCL

  backend "s3" {
    bucket         = "${BUCKET}"
    key            = "env/<env>/terraform.tfstate"
    region         = "${REGION}"
    encrypt        = true
    dynamodb_table = "${LOCK_TABLE}"
  }
HCL
