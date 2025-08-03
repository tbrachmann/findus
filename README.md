# findus – Chat with Gemini

findus is a Django-powered chat application that integrates Google Gemini 2.5 Flash-Lite to deliver AI conversations and on-the-fly grammar feedback.
Each conversation is stored separately, making it easy to revisit past chats, while a modern responsive interface keeps the experience pleasant on desktop and mobile.

---

## ✨ Features

| Category | Details |
|----------|---------|
| **Gemini API integration** | Sends user prompts to Google Gemini 2.5 Flash-Lite and streams back answers. |
| **Conversation management** | Each chat is grouped under a `Conversation` record with its own URL (`/conversation/<id>/`). |
| **Grammar / spelling analysis** | Asynchronously calls Gemini a second time to analyse the user’s text and displays feedback next to the original bubble. |
| **Responsive UI** | Flex-box chat layout, mobile-first design, dark-on-light colour scheme. |
| **Real-time UX** | Typing indicator, automatic scrolling, grammar results appear without page refresh. |
| **Code quality** | Pre-commit hooks run **Black**, **Flake8**, and **Mypy** on every commit. |

---

## ⚙️ Installation

```bash
# 1. Clone repo
git clone https://github.com/<your-org>/findus.git
cd findus

# 2. Install latest Python (≥3.13) e.g. via Homebrew
brew install python

# 3. Create & activate a virtualenv
/opt/homebrew/bin/python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## 🔐 Configuration

The app needs a Gemini API key:

```bash
export GEMINI_API_KEY="AIzaSyBPnGE-TZLfhBDpZRRtr03TR91sZriQTxg"
```

Alternatively set it in `findus/settings.py` or an `.env` file (remember to keep secrets out of git).

---

## 🚀 Usage

```bash
# Run database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

Open http://127.0.0.1:8000/ – a new conversation is created automatically.
Use **+ New Conversation** in the header to start additional threads.

---

## 🛠 Development

### Pre-commit hooks

```bash
# one-time install
pre-commit install
```

On every commit the following run automatically:

1. **Black** – auto-formats code (`line-length = 88`)
2. **Flake8** – linting (`max-line-length = 100`, ignores `E203,W503`)
3. **Mypy** – static typing (`strict`, Django stubs enabled)

Run manually with:

```bash
pre-commit run --all-files
```

### Running tests (placeholder)

```bash
pytest
```

---

## 🧰 Tech Stack

- Python 3.13
- Django 5.2
- Google GenAI client (`google-genai`)
- HTML / CSS / Vanilla JS (no front-end framework)
- SQLite (default) – easily swap for Postgres/MySQL in `settings.py`
- Pre-commit + Black + Flake8 + Mypy for code quality

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
