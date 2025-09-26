# Setup

please check the @README.md for instructions on how to:
* run the server
* run tests
* add new features

run the server with `uv run uvicorn findus.asgi:application --reload`

# Error Handling

since we're in development mode, you don't need to add error handling at every location that could throw an error. instead of doing a very general `try: .... except Exception as e` block - just let the error be thrown so it can help you debug. Here's an example of what we DON'T want:
```
try:
    something_score: int = do_something()
    return something_score
except Exception as e: # notice how this catches all possible errors? this is hard to debug
    logger.error(f"Failed to do something: {e}")
    return DEFAULT_SOMETHING_SCORE # then you fallback to a default value - again, this makes it hard to debug because everything fails silently and returns defaults
```

what we do want:
```
something_score: int = do_something() # let the errors fly! so we can handle them with bespoke handlers
return something_score
```
or
```
try:
    something_score: int = do_something()
    return something_score
except SomethingException as e: # handling for known error where we have to take some action
    undo_something()
    raise
```

# Testing

please make sure all new features are covered by tests, and make sure that all tests are passing before committing. run all tests with `uv run ./manage.py test` before committing to make sure you haven't broken previous functionality.

# Async-Native Platform

where possible use native async methods instead of async_to_sync or sync_to_async.

# Committing

only skip mypy checks if there is no other alternative.
never use --no-verify on git commits

# Documentation

if you change some sort of configuration like databases, LLMs, or frameworks - please update README.md with your commit. If this change to configuration will mean a change for the deployment process, then make sure it will run on Heroku by updating the Heroku-specific config files.

# Deployment

Deploying means deploying to heroku using `git push heroku main`. Any infra changes should be reflected onto heroku. List what commands you'll run to create that infra.

# Code Style

All code should be DRY. Do not repeat yourself. Extract functions and classes where necessary. When a class contains internal types, you should use dataclasses. When dealing with unstructured JSON, you should use pydantic data models.
