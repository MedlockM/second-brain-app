#!/usr/bin/env python3
"""
Start Development/Test Environment

Simple script to start the Docker Compose environment for development and testing.
Supports different profiles: api, workers, full, etc.
"""

import subprocess
import time
import httpx
import sys
import os


def run_command(cmd, description, timeout=60):
    """Run a command with timeout and error handling."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"❌ {description} failed with error: {e}")
        return False


def check_service_health(url, name, timeout=5):
    """Check if a service is healthy."""
    try:
        with httpx.Client() as client:
            response = client.get(url, timeout=timeout)
            if response.status_code == 200:
                print(f"✅ {name} is healthy")
                return True
            else:
                print(f"⚠️  {name} returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ {name} is not accessible: {e}")
        return False


def wait_for_services(max_wait=20):
    """Wait for all services to be healthy."""
    print(f"⏳ Waiting for services to be healthy (max {max_wait}s)...")
    
    services = {
        'LocalStack': 'http://localhost:4566/_localstack/health',
        'API': 'http://localhost:8000/api/v1/health/',
    }
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        all_healthy = True
        
        for name, url in services.items():
            if not check_service_health(url, name):
                all_healthy = False
        
        if all_healthy:
            print("🎉 All services are healthy!")
            return True
        
        print(f"⏳ Waiting... ({int(time.time() - start_time)}s elapsed)")
        time.sleep(10)
    
    print(f"⏰ Services did not become healthy within {max_wait} seconds")
    return False



def setup_localstack_resources():
    """Set up LocalStack resources for E2E testing."""
    print("🔧 Setting up LocalStack resources...")
    
    # LocalStack should automatically run initialization scripts from /docker-entrypoint-initaws.d
    # We just need to wait a bit for the initialization to complete
    print("⏳ Waiting for LocalStack automatic initialization to complete...")
    time.sleep(15)  # Give LocalStack time to run init scripts
    
    # Verify that resources were created by checking a few key resources
    try:
        # Use boto3 to check resources instead of awslocal command
        import boto3
        
        # Check DynamoDB tables
        dynamodb = boto3.client(
            'dynamodb',
            endpoint_url='http://localhost:4566',
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
        
        tables = dynamodb.list_tables()
        required_tables = ['users', 'podcasts', 'episodes', 'credit_transactions', 'processing_jobs']
        missing_tables = [table for table in required_tables if table not in tables['TableNames']]
        
        if missing_tables:
            print(f"⚠️  Some DynamoDB tables not found: {missing_tables}")
            print("   LocalStack may still be initializing - this is normal on first startup")
        else:
            print("✅ All DynamoDB tables found")
        
        # Check S3 buckets
        s3 = boto3.client(
            's3',
            endpoint_url='http://localhost:4566',
            aws_access_key_id='test',
            aws_secret_access_key='test',
            region_name='us-east-1'
        )
        
        buckets = s3.list_buckets()
        bucket_names = [bucket['Name'] for bucket in buckets['Buckets']]
        required_buckets = ['media-summarizer-audio', 'media-summarizer-transcriptions', 'media-summarizer-summaries']
        missing_buckets = [bucket for bucket in required_buckets if bucket not in bucket_names]
        
        if missing_buckets:
            print(f"⚠️  Some S3 buckets not found: {missing_buckets}")
            print("   LocalStack may still be initializing - this is normal on first startup")
        else:
            print("✅ All S3 buckets found")
        
        print("✅ LocalStack resources verification completed")
        return True
        
    except Exception as e:
        print(f"⚠️  Could not verify LocalStack resources: {e}")
        print("   This is normal on first startup - LocalStack will initialize resources automatically")
        return True  # Don't fail the startup


def main():
    """Main function to start development/test environment."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Start development/test environment')
    parser.add_argument('--profile', default='full', 
                       choices=['api', 'workers', 'full', 'infrastructure', 'whisper', 'ephemeral'],
                       help='Docker compose profile to use (default: full)')
    parser.add_argument('--build', action='store_true', 
                       help='Force rebuild of containers')

    
    args = parser.parse_args()
    
    print(f"🚀 Starting Development/Test Environment (profile: {args.profile})")
    print("=" * 50)
    
    # Check if docker-compose.dev.yml exists
    if not os.path.exists("docker-compose.dev.yml"):
        print("❌ docker-compose.dev.yml not found!")
        print("   Make sure you're running this from the project root directory")
        sys.exit(1)
    
    # Stop any existing services
    print("🛑 Stopping any existing services...")
    subprocess.run([
        'docker-compose', '-f', 'docker-compose.dev.yml', 'down', '-v'
    ], capture_output=True)
    
    # Start services with specified profile
    cmd = [
        'docker-compose', '-f', 'docker-compose.dev.yml', 
        '--profile', args.profile, 
        'up', '-d'
    ]
    
    if args.build:
        cmd.append('--build')
    
    if not run_command(cmd, f"Starting Docker services (profile: {args.profile})", timeout=300):
        print("❌ Failed to start Docker services")
        sys.exit(1)
    
    # Wait for services to be healthy
    if not wait_for_services():
        print("❌ Services did not become healthy")
        print("💡 Try running: docker-compose -f docker-compose.dev.yml logs")
        sys.exit(1)
    
    # Set up LocalStack resources
    setup_localstack_resources()
    
    print(f"\n🎉 Development/Test Environment is ready! (profile: {args.profile})")
    print("=" * 50)
    print("📋 Next steps:")
    print("   • Unit tests: pytest media_summarizer/tests/unit/ -v")
    print("   • Integration tests: pytest media_summarizer/tests/integration/ -v") 
    print("   • E2E tests: pytest media_summarizer/tests/end_to_end/ -v")
    print("   • Check service logs: docker-compose -f docker-compose.dev.yml logs")
    print("   • Stop environment: docker-compose -f docker-compose.dev.yml down")
    print("\n🔗 Service URLs:")
    print("   • LocalStack: http://localhost:4566")
    print("   • API: http://localhost:8000")
    print("   • Whisper: http://localhost:8080")


if __name__ == "__main__":
    main()