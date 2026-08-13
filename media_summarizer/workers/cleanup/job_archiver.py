import json
import logging
import os
from datetime import datetime

import boto3
from boto3.dynamodb.types import TypeDeserializer

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
deserializer = TypeDeserializer()
ARCHIVE_BUCKET = os.environ.get("ARCHIVE_BUCKET")

# One structured summary line per invocation. It is the source of the two
# CloudWatch metrics behind the silent-failure tripwire (task-242):
# JobArchiverRemoveRecords and JobArchiverObjectsArchived, extracted by the log
# metric filters in modules/platform/pipeline_alerts.tf.
#
# The §1.5 incident was an archiver invoked 144 times that never wrote an
# object, and it stayed invisible because nothing compared "REMOVE events seen"
# with "objects written". These two counters are that comparison.
BATCH_SUMMARY_EVENT = "job_archiver.batch_completed"


def emit_batch_summary(remove_records, archived, failed):
    """Write the invocation summary as one pure-JSON stdout line.

    Deliberately `print` and not `logger.info`: the CloudWatch metric filters
    use a JSON pattern (`{ $.event = "job_archiver.batch_completed" }`), which
    only matches log events that are valid JSON on their own. The Lambda
    logging formatter prefixes `[INFO] RequestId...` to logger output, which
    would make the event unparseable and the metric silently empty -- exactly
    the class of failure this metric exists to catch.
    """
    print(
        json.dumps(
            {
                "event": BATCH_SUMMARY_EVENT,
                "remove_records": remove_records,
                "archived": archived,
                "failed": failed,
            }
        )
    )


def deserialize(image):
    """Convert DynamoDB format to Python dict."""
    d = {}
    for key in image:
        d[key] = deserializer.deserialize(image[key])
    return d

def lambda_handler(event, context):
    """
    Process DynamoDB Stream events and archive deleted items to S3.
    """
    records = event.get("Records", [])

    if not ARCHIVE_BUCKET:
        logger.error("ARCHIVE_BUCKET environment variable not set")
        # Every record in this batch is a deletion that will never be archived:
        # report it as a gap so the tripwire fires instead of the batch being
        # dropped in silence.
        emit_batch_summary(
            remove_records=sum(
                1 for r in records if r.get("eventName") == "REMOVE"
            ),
            archived=0,
            failed=len(records),
        )
        return {"statusCode": 500, "body": "Configuration error"}

    logger.info(f"Processing {len(records)} records")

    archived_count = 0
    remove_records = 0
    failed_count = 0

    for record in records:
        try:
            # Only process REMOVE events
            if record["eventName"] != "REMOVE":
                continue

            remove_records += 1

            # Check if it's a TTL deletion
            # AWS documentation says: "Records deleted by TTL contain the following field in the userIdentity:
            # "userIdentity": { "type": "Service", "principalId": "dynamodb.amazonaws.com" }
            user_identity = record.get("userIdentity", {})
            principal_id = user_identity.get("principalId")
            
            # We archive ALL deletions for audit purposes, not just TTL
            is_ttl = principal_id == "dynamodb.amazonaws.com"
            
            # Get the old image (the deleted item)
            old_image = record["dynamodb"].get("OldImage")
            if not old_image:
                logger.warning("No OldImage found in record")
                failed_count += 1
                continue
                
            # Deserialize to Python dict
            item = deserialize(old_image)
            job_id = item.get("id", "unknown")
            
            # Create archive path: YYYY/MM/DD/job_id.json
            # Use UTC for consistency
            now = datetime.utcnow()
            key = f"{now.year}/{now.month:02d}/{now.day:02d}/{job_id}.json"
            
            # Add metadata about deletion
            archive_data = {
                "job_data": item,
                "archived_at": now.isoformat(),
                "deletion_type": "TTL" if is_ttl else "MANUAL",
                "deletion_reason": "DynamoDB Stream Event"
            }
            
            # Upload to S3
            s3.put_object(
                Bucket=ARCHIVE_BUCKET,
                Key=key,
                Body=json.dumps(archive_data, default=str),
                ContentType="application/json"
            )
            
            archived_count += 1
            logger.info(f"Archived job {job_id} to s3://{ARCHIVE_BUCKET}/{key}")
            
        except Exception as e:
            failed_count += 1
            logger.error(f"Error processing record: {e}")
            # We don't raise here to allow other records in the batch to be processed

    logger.info(f"Successfully archived {archived_count} jobs")
    emit_batch_summary(
        remove_records=remove_records,
        archived=archived_count,
        failed=failed_count,
    )
    return {"statusCode": 200, "body": json.dumps(f"Archived {archived_count} jobs")}
