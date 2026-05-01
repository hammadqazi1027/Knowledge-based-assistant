# 🧠 AI Knowledge Assistant — RAG Pipeline

A beautiful, production-ready **Retrieval-Augmented Generation (RAG)** system built with **Streamlit**, **Zilliz Cloud**, and **Groq LLM**. Features multi-university data isolation, role-based access control (Admin / Teacher / User), ticket tracking, and advanced query optimization.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📄 **Smart Document Upload** | PDF, TXT, DOCX with auto chunking & semantic embedding |
| 🔍 **Hybrid Search** | Multi-query expansion + re-ranking + keyword boosting |
| 💬 **AI-Powered Answers** | Streaming responses with source citations |
| 🏛️ **Multi-University** | Data isolation per university |
| 🔐 **Role-Based Access** | Admin, Teacher, User roles |
| 🎫 **Ticket Tracking** | Query analytics and department classification |
| 📊 **Analytics Dashboard** | Plotly charts for admins |
| 🧠 **Conversation Memory** | Multi-turn chat with context summarization |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Git
- A [Zilliz Cloud](https://zilliz.com) account (free tier available)
- A [Groq](https://console.groq.com) API key (free tier available)

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd rag-pipeline
```

### 2. Create Virtual Environment

> ⚠️ **Never commit the `venv` or `.venv` folder to Git.** It contains ~5GB of dependencies and will break GitHub pushes.

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- `streamlit` — Web UI framework
- `pymilvus` — Zilliz Cloud client
- `sentence-transformers` — Embedding model
- `groq` — LLM API client
- `PyPDF2`, `python-docx` — Document parsers
- `langchain-text-splitters` — Smart chunking
- `bcrypt` — Password hashing
- `plotly` — Analytics charts

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env   # If example exists, or create manually
```

Edit `.env` with your credentials:

```env
# ── Zilliz Cloud ──
ZILLIZ_URI=https://your-cluster.zillizcloud.com
ZILLIZ_TOKEN=your_zilliz_token

# ── Groq LLM ──
GROQ_API_KEY=your_groq_api_key

# ── Optional Settings ──
COLLECTION_NAME=rag_documents
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384
TOP_K_RESULTS=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
LLM_MODEL=llama-3.3-70b-versatile
```

> 💡 **Get free credentials:**
> - Zilliz: [cloud.zilliz.com](https://cloud.zilliz.com) → Create cluster → Copy URI & Token
> - Groq: [console.groq.com](https://console.groq.com) → API Keys → Create Key

### 5. Run the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

---

## 🔐 Demo Credentials

| Role | Username | Password | What They Can Do |
|------|----------|----------|------------------|
| **Super Admin** | `superadmin` | `admin12345` | Full system access (hardcoded) |
| **Admin** | `admin` | `admin123` | Manage users, universities, tickets, analytics |
| **Teacher** | `teacher` | `teacher123` | Upload documents for their university |
| **User** | `user` | `user123` | Ask questions, view tickets |

> 📝 **Self-registration:** Users can create their own accounts on the login page and select their university.

---

## 🏗️ Project Structure

```
rag-pipeline/
├── app.py                      # Main entry point + global CSS
├── config.py                   # Environment config loader
├── auth.py                     # Authentication & user management
├── db.py                       # SQLite document metadata
├── university.py               # University CRUD
├── tickets.py                  # Query ticket tracking
├── vector_store.py             # Zilliz Cloud integration
├── rag_engine.py               # Core RAG pipeline (embed → retrieve → generate)
├── document_processor.py       # PDF/TXT/DOCX parsing & chunking
├── queries.py                  # Centralized DB queries (for instructor review)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Ignores .venv, .env, __pycache__, etc.
├── .env                        # Your secrets (NEVER commit this!)
├── pages/
│   ├── login.py                # Role-based login UI
│   ├── admin_dashboard.py      # Admin: users, universities, tickets, analytics
│   ├── teacher_dashboard.py    # Teacher: document upload & management
│   └── user_dashboard.py       # User: chat with document-grounded answers
└── data/                       # SQLite database (auto-created)
    └── rag_pipeline.db
```

---

## 🛠️ Advanced: Database Query Optimization

All database queries are centralized in `queries.py` for easy instructor review. The file includes:

- **`UserQueries`** — User CRUD with pagination
- **`UniversityQueries`** — University management
- **`DocumentQueries`** — Document metadata with university filtering
- **`TicketQueries`** — Ticket tracking with status filters
- **`QueryOptimizer`** — `EXPLAIN QUERY PLAN`, `ANALYZE`, table stats

Indexes are automatically created on:
- `users(role)`, `users(university_id)`, `users(username)`
- `documents(university_id)`, `documents(doc_name)`, `documents(created_at)`
- `tickets(university_id)`, `tickets(user_id)`, `tickets(status)`, `tickets(department)`

---

## 🧹 Troubleshooting

### Git push fails with "HTTP 408" or "remote end hung up unexpectedly"

**Cause:** The `.venv` folder (~5.5GB) was accidentally committed.

**Fix:**
```bash
# Remove .venv from git tracking (keeps it locally)
git rm -r --cached .venv
git add .gitignore
git commit -m "Remove .venv from git tracking"

# Push again
git push origin main
```

> 💡 `.venv/` is already in `.gitignore`, so it won't be committed again.

### "ModuleNotFoundError: No module named 'streamlit'"

You forgot to activate the virtual environment:
```bash
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

### "Failed to connect to Zilliz Cloud"

1. Check your `ZILLIZ_URI` and `ZILLIZ_TOKEN` in `.env`
2. Ensure your Zilliz cluster is running (not paused)
3. Verify network connectivity: `curl -I https://your-uri.zillizcloud.com`

### "LLM Error" or demo mode responses

Add your `GROQ_API_KEY` to `.env`. Get a free key at [console.groq.com](https://console.groq.com).

---

## 📜 License

MIT License — Built for educational purposes.

---

## 🙏 Credits

- **Embeddings:** [Sentence-Transformers](https://www.sbert.net/) (all-MiniLM-L6-v2)
- **Vector DB:** [Zilliz Cloud](https://zilliz.com) (managed Milvus)
- **LLM:** [Groq](https://groq.com) (Llama 3.3 70B)
- **UI:** [Streamlit](https://streamlit.io)
- **Charts:** [Plotly](https://plotly.com)
