# Testing Guide

## Overview

This project includes comprehensive testing at multiple levels:

1. **Unit Tests** - Django test suite covering models, views, and services
2. **Integration Tests** - Playwright browser automation testing end-to-end functionality
3. **Continuous Integration** - Automated testing on GitHub Actions

## Quick Start

```bash
# Install test dependencies
make install

# Run all tests
make test

# Run specific test types
make test-unit          # Unit tests only
make test-integration   # Browser tests only (requires running server)
```

## Integration Test Details

The Playwright integration test (`playwright_integration_test.py`) verifies:

- ✅ **Homepage Loading** - Redirects to login correctly
- ✅ **User Authentication** - Login form and user authentication
- ✅ **Language Selection** - Handles "Choose Language" page automatically
- ✅ **Chat Interface** - Finds message input and send functionality
- ✅ **Message Processing** - Sends test messages with grammar errors
- ✅ **Database Updates** - Verifies conversations, messages, and language proficiency changes
- ✅ **Language Analysis** - Confirms background grammar analysis is working

### Test Messages

The integration test sends these messages to verify grammar analysis:
```
1. "Hello! I go to store yesterday."
2. "I have three cat at home."
3. "They is very friendly animals."
```

### Expected Results

After running the integration test, you should see:
- 3/3 messages sent successfully
- New conversation created (+1)
- Messages stored in database (+2)
- Language proficiency metrics updated
- Grammar accuracy score improved

## Continuous Integration

### GitHub Actions Workflow

The `.github/workflows/test.yml` file runs:

1. **Setup**: PostgreSQL with pgvector, Python 3.13, UV dependencies
2. **Install**: Playwright browsers and project dependencies
3. **Test**: Unit tests followed by integration tests
4. **Cleanup**: Upload screenshots on failure for debugging

### Required Secrets

Set these in your GitHub repository secrets:
- `GEMINI_API_KEY` - Your Google Gemini API key for AI testing

### Local CI Simulation

```bash
# Simulate the CI environment locally
export DATABASE_URL="postgresql://test_user:test_password@localhost:5432/test_db"
export GEMINI_API_KEY="your_api_key_here"
export DJANGO_ALLOW_ASYNC_UNSAFE="true"

# Run the same commands as CI
uv run python manage.py migrate
uv run python manage.py test
uv run python manage.py runserver &
uv run python playwright_integration_test.py
```

## Debugging Test Failures

### Playwright Screenshots

Integration test failures automatically capture screenshots:
- Local: `/tmp/playwright_screenshots/`
- CI: Uploaded as GitHub Actions artifacts

### Common Issues

1. **Server Not Running**: Integration tests require Django server at `localhost:8000`
2. **Database Connection**: Ensure PostgreSQL with pgvector is available
3. **Browser Dependencies**: Run `uv run playwright install chromium` if browser fails
4. **API Keys**: Set `GEMINI_API_KEY` for AI service tests

### Manual Testing

```bash
# Test database connection
uv run python manage.py dbshell

# Test Gemini API integration
uv run python manage.py shell
>>> from chat.ai_service import ai_service
>>> ai_service.test_connection()

# Test pgvector functionality
uv run python manage.py test_pgvector
```

## Best Practices

1. **Always run tests before committing**
2. **Update tests when adding new features**
3. **Check CI results on pull requests**
4. **Use `make test` for complete verification**
5. **Add unit tests for new models/services**
6. **Update integration tests for UI changes**
