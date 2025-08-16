#!/bin/bash

# Deploy script for Media Summarizer horizontal scaling infrastructure
# This script packages the Lambda function and deploys the Terraform infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/infrastructure/terraform"
LAMBDA_DIR="$PROJECT_ROOT/infrastructure/scaling"

# Default values
AWS_REGION=${AWS_REGION:-"us-east-1"}
ENVIRONMENT=${ENVIRONMENT:-"production"}
PROJECT_NAME=${PROJECT_NAME:-"media-summarizer"}

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    log_info "Checking dependencies..."

    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi

    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform is not installed. Please install it first."
        exit 1
    fi

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi

    # Check if zip is installed
    if ! command -v zip &> /dev/null; then
        log_error "zip is not installed. Please install it first."
        exit 1
    fi

    log_info "All dependencies are available."
}

check_aws_credentials() {
    log_info "Checking AWS credentials..."

    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials are not configured. Please run 'aws configure' first."
        exit 1
    fi

    log_info "AWS credentials are configured."
}

package_lambda() {
    log_info "Packaging Lambda function..."

    cd "$LAMBDA_DIR"

    # Create temporary directory for Lambda package
    TEMP_DIR=$(mktemp -d)

    # Copy Lambda function
    cp scaling_controller.py "$TEMP_DIR/"

    # Install dependencies in temp directory
    pip install boto3 -t "$TEMP_DIR/" --quiet

    # Create zip file
    cd "$TEMP_DIR"
    zip -r "$TERRAFORM_DIR/scaling_controller.zip" . --quiet

    # Cleanup
    rm -rf "$TEMP_DIR"

    log_info "Lambda function packaged successfully."
}

build_and_push_docker_images() {
    log_info "Building and pushing Docker images..."

    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

    # Login to ECR
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_URI"

    cd "$PROJECT_ROOT"

    # Build ephemeral worker image
    log_info "Building ephemeral worker image..."
    docker build -f infrastructure/docker/ephemeral-worker.Dockerfile -t "$PROJECT_NAME-ephemeral-worker" .

    # Check if ECR repository exists, create if it doesn't
    if ! aws ecr describe-repositories --repository-names "$PROJECT_NAME-ephemeral-worker" --region "$AWS_REGION" &> /dev/null; then
        log_info "Creating ECR repository..."
        aws ecr create-repository --repository-name "$PROJECT_NAME-ephemeral-worker" --region "$AWS_REGION"
    fi

    # Tag and push image
    docker tag "$PROJECT_NAME-ephemeral-worker:latest" "$ECR_URI/$PROJECT_NAME-ephemeral-worker:latest"
    docker push "$ECR_URI/$PROJECT_NAME-ephemeral-worker:latest"

    log_info "Docker images built and pushed successfully."
}

deploy_terraform() {
    log_info "Deploying Terraform infrastructure..."

    cd "$TERRAFORM_DIR"

    # Initialize Terraform
    terraform init

    # Validate configuration
    terraform validate

    # Plan deployment
    log_info "Creating Terraform plan..."
    terraform plan \
        -var="aws_region=$AWS_REGION" \
        -var="environment=$ENVIRONMENT" \
        -var="project_name=$PROJECT_NAME" \
        -var="vpc_id=${VPC_ID:-$(get_default_vpc)}" \
        -var="subnet_ids=[$(get_public_subnets)]" \
        -var="openai_api_key=${OPENAI_API_KEY}" \
        -out=tfplan

    # Apply if plan is successful
    if [ $? -eq 0 ]; then
        log_info "Applying Terraform configuration..."
        terraform apply tfplan

        if [ $? -eq 0 ]; then
            log_info "Terraform deployment completed successfully."

            # Display outputs
            log_info "Infrastructure outputs:"
            terraform output
        else
            log_error "Terraform apply failed."
            exit 1
        fi
    else
        log_error "Terraform plan failed."
        exit 1
    fi
}

get_default_vpc() {
    aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region "$AWS_REGION"
}

get_public_subnets() {
    VPC_ID=${VPC_ID:-$(get_default_vpc)}
    aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=map-public-ip-on-launch,Values=true" \
        --query "Subnets[*].SubnetId" \
        --output text \
        --region "$AWS_REGION" | tr '\t' ','
}

test_deployment() {
    log_info "Testing deployment..."

    # Get Lambda function name from Terraform output
    LAMBDA_FUNCTION_NAME=$(terraform output -raw lambda_function_name 2>/dev/null || echo "$PROJECT_NAME-scaling-controller")

    # Test Lambda function
    log_info "Testing scaling controller Lambda function..."
    aws lambda invoke \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --payload '{"action":"scale","source":"manual_test"}' \
        --region "$AWS_REGION" \
        /tmp/lambda_response.json

    if [ $? -eq 0 ]; then
        log_info "Lambda function test successful."
        cat /tmp/lambda_response.json
        rm -f /tmp/lambda_response.json
    else
        log_warn "Lambda function test failed, but this might be expected if no messages are in queues."
    fi
}

cleanup() {
    log_info "Cleaning up temporary files..."
    rm -f "$TERRAFORM_DIR/scaling_controller.zip"
    rm -f "$TERRAFORM_DIR/tfplan"
}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Deploy Media Summarizer horizontal scaling infrastructure"
    echo ""
    echo "Options:"
    echo "  -r, --region REGION      AWS region (default: us-east-1)"
    echo "  -e, --environment ENV    Environment name (default: production)"
    echo "  -p, --project PROJECT    Project name (default: media-summarizer)"
    echo "  --vpc-id VPC_ID         VPC ID (default: default VPC)"
    echo "  --skip-docker           Skip Docker build and push"
    echo "  --skip-test             Skip deployment testing"
    echo "  --destroy               Destroy infrastructure instead of deploying"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  OPENAI_API_KEY          OpenAI API key (required)"
    echo "  VPC_ID                  VPC ID for deployment"
    echo "  SUBNET_IDS              Comma-separated list of subnet IDs"
    echo ""
    echo "Example:"
    echo "  $0 --region us-west-2 --environment staging"
}

# Parse command line arguments
SKIP_DOCKER=false
SKIP_TEST=false
DESTROY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -p|--project)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --vpc-id)
            VPC_ID="$2"
            shift 2
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-test)
            SKIP_TEST=true
            shift
            ;;
        --destroy)
            DESTROY=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required environment variables
if [ -z "$OPENAI_API_KEY" ] && [ "$DESTROY" = false ]; then
    log_error "OPENAI_API_KEY environment variable is required."
    exit 1
fi

# Main execution
main() {
    log_info "Starting Media Summarizer scaling infrastructure deployment..."
    log_info "Region: $AWS_REGION"
    log_info "Environment: $ENVIRONMENT"
    log_info "Project: $PROJECT_NAME"

    if [ "$DESTROY" = true ]; then
        log_info "Destroying infrastructure..."
        cd "$TERRAFORM_DIR"
        terraform destroy \
            -var="aws_region=$AWS_REGION" \
            -var="environment=$ENVIRONMENT" \
            -var="project_name=$PROJECT_NAME" \
            -var="vpc_id=${VPC_ID:-$(get_default_vpc)}" \
            -var="subnet_ids=[$(get_public_subnets)]" \
            -var="openai_api_key=dummy" \
            -auto-approve
        log_info "Infrastructure destroyed."
        exit 0
    fi

    check_dependencies
    check_aws_credentials

    # Package Lambda function
    package_lambda

    # Build and push Docker images (unless skipped)
    if [ "$SKIP_DOCKER" = false ]; then
        build_and_push_docker_images
    else
        log_warn "Skipping Docker build and push."
    fi

    # Deploy infrastructure
    deploy_terraform

    # Test deployment (unless skipped)
    if [ "$SKIP_TEST" = false ]; then
        test_deployment
    else
        log_warn "Skipping deployment testing."
    fi

    # Cleanup
    cleanup

    log_info "Deployment completed successfully!"
    log_info ""
    log_info "Next steps:"
    log_info "1. Configure your application to use the deployed queues"
    log_info "2. Monitor CloudWatch alarms and metrics"
    log_info "3. Test the scaling behavior by submitting jobs"
}

# Trap to cleanup on exit
trap cleanup EXIT

# Run main function
main
