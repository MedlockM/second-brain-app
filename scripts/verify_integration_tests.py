#!/usr/bin/env python3
"""
Verification script for integration test strategy implementation.

This script verifies that all components required for the integration test
strategy are working correctly:
1. HTTPx async test server
2. Real Docker Whisper service connection
3. LocalStack services
4. Stripe test API connectivity
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"📁 Loaded environment variables from {env_file}")
    else:
        print("⚠️  .env file not found, using environment variables only")
except ImportError:
    print("⚠️  python-dotenv not available, using environment variables only")

# Set up test environment
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


async def test_httpx_server():
    """Test HTTPx async test server functionality."""
    print("🧪 Testing HTTPx async test server...")

    try:
        from media_summarizer.tests.utils.httpx_test_server import (
            httpx_test_server,
            HTTPXTestClient,
            load_test_rss_feed
        )

        # Test server creation and basic functionality
        async with httpx_test_server(host="127.0.0.1", port=8002) as server:
            # Add test content
            rss_content = load_test_rss_feed()
            server.add_rss_feed("/test-feed.xml", rss_content)

            audio_content = b"test audio data"
            server.add_audio_file("/test-audio.mp3", audio_content)

            # Test HTTP client
            async with HTTPXTestClient(base_url=server.base_url) as client:
                # Test RSS feed
                rss_response = await client.get("/test-feed.xml")
                assert rss_response.status_code == 200
                assert "xml" in rss_response.headers.get('content-type', '').lower()

                # Test audio file
                audio_response = await client.get("/test-audio.mp3")
                assert audio_response.status_code == 200
                assert "audio" in audio_response.headers.get('content-type', '').lower()

                # Test 404
                not_found_response = await client.get("/nonexistent")
                assert not_found_response.status_code == 404

        print("✅ HTTPx async test server working correctly")
        return True

    except Exception as e:
        print(f"❌ HTTPx test server failed: {e}")
        return False


def test_whisper_connection():
    """Test real Docker Whisper service connection."""
    print("🧪 Testing Docker Whisper service connection...")

    try:
        from media_summarizer.tests.utils.real_whisper_client import (
            check_whisper_connection,
            create_real_whisper_client
        )

        # Test connection
        if check_whisper_connection():
            print("✅ Docker Whisper service is available and responsive")

            # Test client creation
            client = create_real_whisper_client()
            if client.is_available():
                print("✅ Real Whisper client created successfully")
                return True
            else:
                print("❌ Whisper client created but service not available")
                return False
        else:
            print("⚠️  Docker Whisper service not available (may need docker-compose up)")
            return False

    except Exception as e:
        print(f"❌ Whisper connection test failed: {e}")
        return False


def test_localstack_services():
    """Test LocalStack services connectivity."""
    print("🧪 Testing LocalStack services...")

    try:
        import boto3
        from botocore.exceptions import ClientError

        # Test S3
        s3_client = boto3.client(
            "s3",
            endpoint_url="http://localhost:4566",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )

        # Try to list buckets
        s3_client.list_buckets()
        print("✅ LocalStack S3 service working")

        # Test SQS
        sqs_client = boto3.client(
            "sqs",
            endpoint_url="http://localhost:4566",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )

        # Try to list queues
        sqs_client.list_queues()
        print("✅ LocalStack SQS service working")

        # Test SES
        ses_client = boto3.client(
            "ses",
            endpoint_url="http://localhost:4566",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )

        # Try to verify email address (this might fail but shows service is available)
        try:
            ses_client.verify_email_identity(EmailAddress="test@example.com")
        except ClientError:
            pass  # Expected in test environment

        print("✅ LocalStack SES service working")

        return True

    except Exception as e:
        print(f"❌ LocalStack services test failed: {e}")
        print("💡 Make sure LocalStack is running: docker-compose -f docker-compose.dev.yml up -d")
        return False


def test_stripe_connectivity():
    """Test Stripe API connectivity."""
    print("🧪 Testing Stripe API connectivity...")

    try:
        import stripe
        import requests

        # Check if test API key is available
        stripe_api_key = os.environ.get("STRIPE_TEST_API_KEY")
        if not stripe_api_key:
            print("⚠️  STRIPE_TEST_API_KEY not found in environment")
            print("💡 Make sure it's set in your .env file or environment variables")
            return False

        print(f"✅ Found Stripe test API key: {stripe_api_key[:7]}...")

        # Test network connectivity to Stripe
        try:
            response = requests.get("https://api.stripe.com", timeout=5)
            print("✅ Stripe API network connectivity working")
        except Exception as e:
            print(f"❌ Stripe API network connectivity failed: {e}")
            return False

        # Configure Stripe with test key
        stripe.api_key = stripe_api_key

        # Try to retrieve account (this validates the API key)
        try:
            account = stripe.Account.retrieve()
            print("✅ Stripe test API key is valid")
            return True
        except stripe.error.AuthenticationError:
            print("❌ Stripe test API key is invalid")
            return False
        except Exception as e:
            print(f"❌ Stripe API test failed: {e}")
            return False

    except ImportError:
        print("❌ Stripe library not available")
        return False
    except Exception as e:
        print(f"❌ Stripe connectivity test failed: {e}")
        return False


def test_integration_imports():
    """Test that all integration test modules can be imported."""
    print("🧪 Testing integration test imports...")

    modules_to_test = [
        "media_summarizer.tests.utils.base_test_classes",
        "media_summarizer.tests.utils.httpx_test_server",
        "media_summarizer.tests.utils.real_whisper_client",
        "media_summarizer.tests.integration.workflows.test_credit_management_workflow",
        "media_summarizer.tests.integration.workflows.test_podcast_submission_workflow",
        "media_summarizer.tests.integration.workflows.test_transcription_summarization_workflow",
        "media_summarizer.tests.integration.workflows.test_podcast_workflow_components",
    ]

    failed_imports = []

    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except Exception as e:
            print(f"❌ {module_name}: {e}")
            failed_imports.append(module_name)

    if failed_imports:
        print(f"❌ {len(failed_imports)} modules failed to import")
        return False
    else:
        print("✅ All integration test modules imported successfully")
        return True


async def run_all_tests():
    """Run all verification tests."""
    print("🚀 Starting integration test strategy verification...\n")

    test_results = {}

    # Test imports first
    test_results["imports"] = test_integration_imports()
    print()

    # Test HTTPx server
    test_results["httpx_server"] = await test_httpx_server()
    print()

    # Test Whisper connection
    test_results["whisper"] = test_whisper_connection()
    print()

    # Test LocalStack
    test_results["localstack"] = test_localstack_services()
    print()

    # Test Stripe
    test_results["stripe"] = test_stripe_connectivity()
    print()

    # Summary
    print("=" * 60)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 60)

    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)

    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.upper():20} {status}")

    print("-" * 60)
    print(f"TOTAL: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Integration test strategy implementation is working correctly")
        print("\n💡 You can now run integration tests with confidence:")
        print("   pytest media_summarizer/tests/integration/ -v")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} tests failed")
        print("❌ Some components need attention before running integration tests")
        print("\n🔧 Troubleshooting steps:")

        if not test_results.get("localstack"):
            print("   - Start LocalStack: docker-compose -f docker-compose.dev.yml up -d")
        if not test_results.get("whisper"):
            print("   - Check Whisper service: docker-compose -f docker-compose.dev.yml logs whisper")
        if not test_results.get("stripe"):
            print("   - Set STRIPE_TEST_API_KEY in your environment")
        if not test_results.get("imports"):
            print("   - Install dependencies: uv pip install -e '.[dev]'")

    return passed_tests == total_tests


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Verification failed with unexpected error: {e}")
        sys.exit(1)
