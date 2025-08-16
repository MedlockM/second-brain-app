"""
Lambda function for controlling horizontal scaling of Fargate workers.
This function is triggered by CloudWatch alarms when SQS queues have messages.
"""
import json
import logging
import os
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CLUSTER_NAME = os.environ.get("CLUSTER_NAME", "media-summarizer-cluster")
TASK_DEFINITION_ARN = os.environ.get("TASK_DEFINITION_ARN")
SUBNET_IDS = os.environ.get("SUBNET_IDS", "").split(",")
SECURITY_GROUP_IDS = os.environ.get("SECURITY_GROUP_IDS", "").split(",")
MAX_PARALLEL_WORKERS = int(os.environ.get("MAX_PARALLEL_WORKERS", "15"))
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

# Queue configurations with their priorities
QUEUE_CONFIGS = {
    "audio-download-queue": {
        "priority": 1,
        "task_definition": os.environ.get("DOWNLOAD_TASK_DEFINITION_ARN"),
        "worker_type": "download"
    },
    "transcription-queue": {
        "priority": 2,
        "task_definition": os.environ.get("WHISPER_TASK_DEFINITION_ARN"),
        "worker_type": "whisper"
    },
    "summarization-queue": {
        "priority": 3,
        "task_definition": os.environ.get("SUMMARIZATION_TASK_DEFINITION_ARN"),
        "worker_type": "summarization"
    },
    "email-notification-queue": {
        "priority": 4,
        "task_definition": os.environ.get("EMAIL_TASK_DEFINITION_ARN"),
        "worker_type": "email"
    }
}

# Initialize AWS clients
ecs_client = boto3.client("ecs", region_name=AWS_REGION)
sqs_client = boto3.client("sqs", region_name=AWS_REGION)
cloudwatch_client = boto3.client("cloudwatch", region_name=AWS_REGION)


def get_queue_url(queue_name: str) -> Optional[str]:
    """Get SQS queue URL by name."""
    try:
        response = sqs_client.get_queue_url(QueueName=queue_name)
        return response["QueueUrl"]
    except ClientError as e:
        logger.error(f"Failed to get queue URL for {queue_name}: {e}")
        return None


def get_queue_message_count(queue_url: str) -> int:
    """Get approximate number of visible messages in queue."""
    try:
        response = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["ApproximateNumberOfMessages"]
        )
        return int(response["Attributes"]["ApproximateNumberOfMessages"])
    except ClientError as e:
        logger.error(f"Failed to get message count for queue {queue_url}: {e}")
        return 0


def get_running_tasks_count(cluster_name: str, family_prefix: str) -> int:
    """Get number of running tasks for a specific task family."""
    try:
        response = ecs_client.list_tasks(
            cluster=cluster_name,
            desiredStatus="RUNNING"
        )

        if not response["taskArns"]:
            return 0

        # Describe tasks to get task definition ARNs
        tasks_response = ecs_client.describe_tasks(
            cluster=cluster_name,
            tasks=response["taskArns"]
        )

        # Count tasks that match our task definition family
        count = 0
        for task in tasks_response["tasks"]:
            task_def_arn = task["taskDefinitionArn"]
            if family_prefix in task_def_arn:
                count += 1

        return count
    except ClientError as e:
        logger.error(f"Failed to get running tasks count: {e}")
        return 0


def calculate_workers_needed(queue_length: int, running_tasks: int) -> int:
    """Calculate how many new workers are needed."""
    # Don't launch more workers if we already have enough running
    if running_tasks >= queue_length:
        return 0

    # Calculate needed workers, respecting max limit
    needed_workers = min(queue_length - running_tasks, MAX_PARALLEL_WORKERS - running_tasks)
    return max(0, needed_workers)


def launch_fargate_task(task_definition_arn: str, worker_type: str, queue_name: str) -> bool:
    """Launch a single Fargate task."""
    try:
        # Get queue URL for the worker
        queue_url = get_queue_url(queue_name)
        if not queue_url:
            logger.error(f"Could not get queue URL for {queue_name}")
            return False

        # Task overrides with environment variables
        overrides = {
            "containerOverrides": [
                {
                    "name": f"media-summarizer-{worker_type}",
                    "environment": [
                        {"name": "WORKER_TYPE", "value": worker_type},
                        {"name": "QUEUE_URL", "value": queue_url},
                        {"name": "QUEUE_NAME", "value": queue_name},
                        {"name": "AWS_DEFAULT_REGION", "value": AWS_REGION},
                        {"name": "EPHEMERAL_MODE", "value": "true"}
                    ]
                }
            ]
        }

        response = ecs_client.run_task(
            cluster=CLUSTER_NAME,
            taskDefinition=task_definition_arn,
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": SUBNET_IDS,
                    "securityGroups": SECURITY_GROUP_IDS,
                    "assignPublicIp": "ENABLED"
                }
            },
            overrides=overrides,
            tags=[
                {"key": "WorkerType", "value": worker_type},
                {"key": "QueueName", "value": queue_name},
                {"key": "LaunchMode", "value": "ephemeral"},
                {"key": "ManagedBy", "value": "scaling-controller"}
            ]
        )

        task_arn = response["tasks"][0]["taskArn"]
        logger.info(f"Successfully launched task {task_arn} for {worker_type} worker")
        return True

    except ClientError as e:
        logger.error(f"Failed to launch Fargate task for {worker_type}: {e}")
        return False


def process_queue_scaling(queue_name: str, config: Dict) -> Dict:
    """Process scaling for a specific queue."""
    queue_url = get_queue_url(queue_name)
    if not queue_url:
        return {
            "queue_name": queue_name,
            "status": "error",
            "message": f"Could not get queue URL for {queue_name}"
        }

    # Get current queue length
    queue_length = get_queue_message_count(queue_url)

    # Get task definition ARN for this worker type
    task_definition_arn = config.get("task_definition")
    if not task_definition_arn:
        return {
            "queue_name": queue_name,
            "status": "error",
            "message": f"No task definition configured for {queue_name}"
        }

    # Get currently running tasks for this worker type
    running_tasks = get_running_tasks_count(CLUSTER_NAME, config["worker_type"])

    # Calculate workers needed
    workers_needed = calculate_workers_needed(queue_length, running_tasks)

    logger.info(f"Queue {queue_name}: {queue_length} messages, {running_tasks} running tasks, {workers_needed} workers needed")

    if workers_needed == 0:
        return {
            "queue_name": queue_name,
            "status": "no_action",
            "queue_length": queue_length,
            "running_tasks": running_tasks,
            "workers_needed": 0
        }

    # Launch required workers
    launched_count = 0
    failed_count = 0

    for i in range(workers_needed):
        if launch_fargate_task(task_definition_arn, config["worker_type"], queue_name):
            launched_count += 1
        else:
            failed_count += 1

    return {
        "queue_name": queue_name,
        "status": "scaling_executed",
        "queue_length": queue_length,
        "running_tasks": running_tasks,
        "workers_needed": workers_needed,
        "launched_count": launched_count,
        "failed_count": failed_count
    }


def send_cloudwatch_metrics(results: List[Dict]):
    """Send custom metrics to CloudWatch for monitoring."""
    try:
        metric_data = []

        for result in results:
            queue_name = result["queue_name"]

            # Queue length metric
            if "queue_length" in result:
                metric_data.append({
                    "MetricName": "QueueLength",
                    "Dimensions": [
                        {"Name": "QueueName", "Value": queue_name}
                    ],
                    "Value": result["queue_length"],
                    "Unit": "Count"
                })

            # Running tasks metric
            if "running_tasks" in result:
                metric_data.append({
                    "MetricName": "RunningTasks",
                    "Dimensions": [
                        {"Name": "QueueName", "Value": queue_name}
                    ],
                    "Value": result["running_tasks"],
                    "Unit": "Count"
                })

            # Launched tasks metric
            if "launched_count" in result:
                metric_data.append({
                    "MetricName": "LaunchedTasks",
                    "Dimensions": [
                        {"Name": "QueueName", "Value": queue_name}
                    ],
                    "Value": result["launched_count"],
                    "Unit": "Count"
                })

        if metric_data:
            cloudwatch_client.put_metric_data(
                Namespace="MediaSummarizer/Scaling",
                MetricData=metric_data
            )
            logger.info(f"Sent {len(metric_data)} metrics to CloudWatch")

    except ClientError as e:
        logger.error(f"Failed to send CloudWatch metrics: {e}")


def lambda_handler(event, context):
    """
    Main Lambda handler for scaling control.

    Expected event format:
    {
        "source": "aws.cloudwatch",
        "detail-type": "CloudWatch Alarm State Change",
        "detail": {
            "alarmName": "media-summarizer-queue-messages",
            "state": {
                "value": "ALARM"
            }
        }
    }

    Or direct invocation with:
    {
        "action": "scale",
        "queues": ["queue-name"] (optional, defaults to all queues)
    }
    """
    logger.info(f"Scaling controller invoked with event: {json.dumps(event)}")

    try:
        # Handle CloudWatch alarm trigger
        if event.get("source") == "aws.cloudwatch":
            alarm_state = event.get("detail", {}).get("state", {}).get("value")
            if alarm_state != "ALARM":
                logger.info(f"Alarm state is {alarm_state}, no scaling action needed")
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "No scaling action needed"})
                }

        # Determine which queues to process
        queues_to_process = event.get("queues", list(QUEUE_CONFIGS.keys()))

        # Sort queues by priority
        sorted_queues = sorted(
            [(name, QUEUE_CONFIGS[name]) for name in queues_to_process if name in QUEUE_CONFIGS],
            key=lambda x: x[1]["priority"]
        )

        results = []
        total_launched = 0

        # Process each queue
        for queue_name, config in sorted_queues:
            result = process_queue_scaling(queue_name, config)
            results.append(result)

            if "launched_count" in result:
                total_launched += result["launched_count"]

            # Respect global max workers limit
            if total_launched >= MAX_PARALLEL_WORKERS:
                logger.info(f"Reached maximum parallel workers limit ({MAX_PARALLEL_WORKERS})")
                break

        # Send metrics to CloudWatch
        send_cloudwatch_metrics(results)

        # Prepare response
        response_body = {
            "message": "Scaling operation completed",
            "total_workers_launched": total_launched,
            "max_workers_limit": MAX_PARALLEL_WORKERS,
            "results": results
        }

        logger.info(f"Scaling operation completed: {json.dumps(response_body)}")

        return {
            "statusCode": 200,
            "body": json.dumps(response_body)
        }

    except Exception as e:
        logger.error(f"Error in scaling controller: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "message": "Scaling operation failed"
            })
        }
