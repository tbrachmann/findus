# findus – Chat with Gemini

findus is an **async Django-powered** chat application that integrates Google Gemini 2.5 Flash-Lite to deliver AI conversations and on-the-fly grammar feedback.
Each conversation is stored separately, making it easy to revisit past chats, while a modern responsive interface keeps the experience pleasant on desktop and mobile.

---

## ✨ Features

| Category | Details |
|----------|---------|
| **Async Django architecture** | Built with Django's native async views and async ORM for superior performance and concurrency. |
| **Gemini API integration** | Sends user prompts to Google Gemini 2.5 Flash-Lite using async HTTP calls. |
| **Conversation management** | Each chat is grouped under a `Conversation` record with its own URL (`/conversation/<id>/`). |
| **Grammar / spelling analysis** | Background grammar analysis using `asyncio.create_task()` for true non-blocking processing. |
| **Responsive UI** | Flex-box chat layout, mobile-first design, dark-on-light colour scheme. |
| **Enhanced markdown rendering** | Powered by `marked.js` with syntax highlighting via `highlight.js` and secure rendering via `DOMPurify`. |
| **Real-time UX** | Typing indicator, automatic scrolling, grammar results appear without page refresh. |
| **Code quality** | Pre-commit hooks run **Black**, **Flake8**, and **Mypy** on every commit. |

---

## ⚙️ Installation

This project uses **UV** for fast dependency management and Python environment handling.

### Prerequisites
- Python ≥3.13
- [UV](https://docs.astral.sh/uv/) - Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Node.js ≥18 - For building frontend markdown renderer assets

### Setup
```bash
# 1. Clone repo
git clone https://github.com/<your-org>/findus.git
cd findus

# 2. Install Python (if needed) and sync dependencies
# UV will automatically manage Python version and virtual environment
uv sync

# 3. Install Node.js dependencies for frontend assets
npm install

# Alternative: Install specific Python version with UV
uv python install 3.13
```

### UV Commands Reference
```bash
# Sync dependencies (equivalent to pip install -r requirements.txt)
uv sync

# Add new dependency
uv add package-name

# Add dev dependency
uv add --dev package-name

# Run commands in the UV environment
uv run python manage.py migrate
uv run python manage.py runserver

# Activate the UV-managed virtual environment (optional)
source .venv/bin/activate
```

---

## Environment Configuration

Sensitive settings such as API keys are **not** hard-coded in the
repository. Instead they are loaded from an environment file at runtime.

1. Copy the provided template and edit it locally
   ```bash
   cp .env.example .env
   ```
2. Obtain your **Google Gemini** API key from
   https://ai.google.dev/
3. Open the new `.env` file and replace the placeholder:
   ```text
   GEMINI_API_KEY=your_real_api_key_here
   ```

The `.env` file is listed in `.gitignore`, so your credentials will **never**
be committed to version control.

---

## 🚀 Usage

```bash
# Run database migrations
uv run python manage.py migrate

# Build frontend assets (markdown renderer)
npm run build

# Start the async development server with ASGI
uv run python manage.py runserver
# Note: Django's development server automatically uses ASGI when async views are detected

# Or start with uvicorn for better async performance (recommended)
uv run uvicorn findus.asgi:application --reload --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/ – a new conversation is created automatically.
Use **+ New Conversation** in the header to start additional threads.

---

## 🛠 Development

### Pre-commit hooks

```bash
# one-time install
uv run pre-commit install
```

On every commit the following run automatically:

1. **Black** – auto-formats code (`line-length = 88`)
2. **Flake8** – linting (`max-line-length = 100`, ignores `E203,W503`)
3. **Mypy** – static typing (`strict`, Django stubs enabled)

Run manually with:

```bash
uv run pre-commit run --all-files
```

### Running tests

```bash
uv run python manage.py test
```

The test suite includes comprehensive async tests covering:
- Async view functionality
- Background task processing
- AI service integration (mocked)
- Database operations with async ORM

---

## 🧰 Tech Stack

- Python 3.13 managed with **UV** (fast dependency management)
- **Django 5.2 with ASGI** (async views and ORM)
- **Asyncio** for background task processing
- Pydantic AI with Google GenAI client (`google-genai`)
- HTML / CSS / Vanilla JS (no front-end framework)
- SQLite (default) with `CONN_MAX_AGE: 0` for async compatibility
- Pre-commit + Black + Flake8 + Mypy for code quality

### Async Architecture Benefits

- **Better Concurrency**: Handles many more concurrent requests without blocking threads
- **Non-blocking Background Tasks**: Grammar analysis runs asynchronously using `asyncio.create_task()`
- **Improved Performance**: Async ORM queries don't block the event loop
- **Modern Django Patterns**: Uses Django's built-in async support rather than sync/async adapters

---

## 🚀 Deployment

### ASGI Server Requirements

Since this application uses Django's async views, it requires an **ASGI server** for deployment (not WSGI). Popular options include:

```bash
# Using Uvicorn (recommended for development/testing)
uv add uvicorn
uv run uvicorn findus.asgi:application --host 0.0.0.0 --port 8000

# Using Daphne (Django's reference ASGI server)
uv add daphne
uv run daphne -b 0.0.0.0 -p 8000 findus.asgi:application

# Using Gunicorn with Uvicorn workers (recommended for production)
uv add gunicorn "uvicorn[standard]"
uv run gunicorn findus.asgi:application -w 4 -k uvicorn.workers.UvicornWorker
```

### Production Considerations

- Configure `ALLOWED_HOSTS` in settings.py
- Set `DEBUG = False` for production
- Use environment variables for `SECRET_KEY`, `GEMINI_API_KEY`, and `LOGFIRE_KEY`
- Consider using PostgreSQL instead of SQLite for better async performance
- The database is configured with `CONN_MAX_AGE: 0` for async compatibility

---

## 🤝 Contributing

1. Fork the repo & create your branch: `git checkout -b feature/awesome`
2. Make changes, commit (`pre-commit` will format & lint automatically)
3. Push and open a Pull Request.
   Describe the motivation and link to any relevant issues.
4. A maintainer will review, request changes if necessary, and merge.

Please follow the established code style (Black) and keep functions & views typed where possible. Binary files (> 500 kB) should not be committed unless essential.

---

## 📄 License

MIT © Toby Brachmann
See `LICENSE` for details.
