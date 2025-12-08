# Custom Terraform image with AWS CLI for LocalStack provisioning
# This image combines Terraform with AWS CLI to enable:
# 1. Standard Terraform resource provisioning
# 2. AWS CLI commands via null_resource for LocalStack workarounds (EventBridge)

FROM hashicorp/terraform:1.6.6

# Install AWS CLI and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    bash \
    curl \
    jq \
    && pip3 install --no-cache-dir --break-system-packages awscli

# Verify installations
RUN terraform version && aws --version

# Working directory for Terraform files
WORKDIR /workspace

# Default entrypoint runs Terraform
ENTRYPOINT []
CMD ["bash", "-c", "terraform init -upgrade && terraform validate && terraform plan -out=tfplan && terraform apply -auto-approve tfplan"]
