#!/usr/bin/env python3
"""
Integration Test Suite
Runs both unit tests and browser integration tests to verify full system functionality.
"""
import sys
import subprocess
import os


def run_unit_tests():
    """Run Django unit tests."""
    print("🧪 Running Django unit tests...")
    result = subprocess.run(
        [sys.executable, "manage.py", "test"], capture_output=True, text=True
    )

    if result.returncode == 0:
        print("✅ Unit tests passed")
        return True
    else:
        print("❌ Unit tests failed:")
        print(result.stdout)
        print(result.stderr)
        return False


def run_playwright_tests():
    """Run Playwright browser integration tests."""
    print("\n🎭 Running Playwright integration tests...")

    # Check if server is running
    try:
        import requests

        response = requests.get("http://127.0.0.1:8000/", timeout=5)
        server_running = True
    except:
        server_running = False

    if not server_running:
        print("❌ Django server not running at http://127.0.0.1:8000/")
        print("   Start server with: uv run python manage.py runserver")
        return False

    result = subprocess.run(
        [sys.executable, "playwright_integration_test.py"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✅ Playwright integration tests passed")
        return True
    else:
        print("❌ Playwright integration tests failed:")
        print(result.stdout)
        print(result.stderr)
        return False


def main():
    """Run complete integration test suite."""
    print("🚀 INTEGRATION TEST SUITE")
    print("=" * 50)

    # Set environment for testing
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'findus.settings')

    all_passed = True

    # Run unit tests
    if not run_unit_tests():
        all_passed = False

    # Run Playwright tests
    if not run_playwright_tests():
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("   System is ready for deployment")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("   Please fix issues before merging")
        sys.exit(1)


if __name__ == "__main__":
    main()
