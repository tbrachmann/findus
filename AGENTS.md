please check the @README.md for instructions on how to:
* run the server
* run tests
* add new features

run the server with `uv run uvicorn findus.asgi:application --reload`

since we're in development mode, you don't need to add error handling at every location that could throw an error. instead of doing a very general `try: .... except Exception as e` block - just let the error be thrown so it can help you debug.

please make sure all new features are covered by tests, and make sure that all tests are passing before committing.

where possible use native async methods instead of async_to_sync or sync_to_async.
only skip mypy checks if there is no other alternative.
never use --no-verify on git commits
