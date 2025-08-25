# 🤖 AI Chatbot - Fintech FAQ Assistant

A production-ready AI chatbot application that provides intelligent responses to fintech-related questions using Retrieval-Augmented Generation (RAG). Built with FastAPI, Next.js, PostgreSQL, Pinecone, and OpenAI.

## 🚀 Features

- **Hybrid Intent Classification**: Fast heuristics + LLM fallback for accurate intent detection
- **RAG Pipeline**: Vector search, multi-stage ranking, and answer verification
- **Session Management**: Persistent chat history with user authentication
- **Real-time Chat**: Optimistic UI updates and responsive design
- **Source Citations**: Transparent answer sources with confidence scoring
- **User Feedback**: Thumbs up/down system for response quality
- **Production Ready**: Comprehensive error handling, monitoring, and security

## 📋 Prerequisites

Before running this application, ensure you have:

- **Python 3.11+** installed
- **Node.js 18+** and npm installed
- **PostgreSQL 15+** database
- **Docker** (optional, for database)
- **Git** for version control

### Required API Keys

You'll need the following API keys:

1. **OpenAI API Key** - For LLM responses and embeddings
2. **Pinecone API Key** - For vector search and storage
3. **Pinecone Index** - Your vector database index name

## 🛠️ Local Development Setup

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd ai-chatbot
```

### 2. Backend Setup

#### Install Python Dependencies

```bash
cd backend
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Database Setup

This project uses **PostgreSQL 15**. By default, the database runs on **localhost:5433** (so it won't clash with Postgres on 5432).

**Option A: Using Docker (Recommended)**

```bash
# Start PostgreSQL 15 mapped to host port 5433
docker volume create pgdata
docker run --name local-pg \
  -e POSTGRES_DB=chatdb \
  -e POSTGRES_USER=rag \
  -e POSTGRES_PASSWORD=ragpw \
  -p 5433:5432 \
  -v pgdata:/var/lib/postgresql/data \
  -d postgres:15
```

**Option B: Local PostgreSQL**

1. Install PostgreSQL 15.
2. Create role and database:

   ```bash
   createuser -s rag
   createdb -O rag chatdb
   psql -d chatdb -c "ALTER USER rag WITH PASSWORD 'ragpw';"
   ```

#### Environment Configuration

Create a `.env` file in the **root directory** (same level as backend/ and frontend/ folders):

```bash
# Database (using port 5433)
DATABASE_URL=postgresql+psycopg2://rag:ragpw@localhost:5433/chatdb

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key-here
PINECONE_INDEX=your-pinecone-index-name
PINECONE_HOST=https://your-pinecone-host

# JWT Authentication
JWT_SECRET=dev-super-secret-change-me
JWT_ALG=HS256
JWT_EXPIRE_MIN=60
```

#### Run Database Migrations

```bash
# Make sure you're in the backend directory with venv activated
alembic upgrade head
```

#### Check Database Connectivity

```bash
psql "postgresql://rag:ragpw@127.0.0.1:5433/chatdb" -c "SELECT now();"
```

**Notes**

- Repo defaults to **port 5433**. If you change the Docker port mapping, also update `DATABASE_URL`.
- Always run `alembic upgrade head` after pulling new migrations.
- Quick health check (with backend running):

  ```bash
  curl -s http://localhost:8000/healthz | jq
  ```

#### Start the Backend Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

**Backend Development Tips**

```bash
# Run with debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload

# Run on different port
uvicorn app.main:app --reload --port 8001

# Check if backend is healthy
curl http://localhost:8000/healthz

# View API documentation
open http://localhost:8000/docs
```

### 3. Frontend Setup

#### Install Node.js Dependencies

```bash
cd frontend
npm install
```

#### Environment Configuration

Create a `.env.local` file in the `frontend` directory:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional: Environment
NEXT_PUBLIC_ENVIRONMENT=development
```

#### Start the Frontend Development Server

```bash
# Development mode
npm run dev

# Or production build
npm run build
npm start
```

The frontend will be available at `http://localhost:3000`

### 4. Test Conversations

Try these example queries to test the system:

- **Simple greeting**: "Hello, how are you?"
- **Fintech question**: "How do I open an account?"
- **Specific query**: "How do I reset my password?"

## 🔧 Development Workflow

### Backend Development

```bash
cd backend
source venv/bin/activate

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests (if available)
pytest

# Database migrations
alembic revision --autogenerate -m "Description of changes"
alembic upgrade head
```

### Frontend Development

```bash
cd frontend

# Development mode with hot reload
npm run dev

# Build for production
npm run build
```

### Database Management

```bash
# Create new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solution**:

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# If not running, start it
docker start local-pg

# Or check your local PostgreSQL service
sudo systemctl status postgresql

# Test database connection
psql "postgresql://rag:ragpw@127.0.0.1:5433/chatdb" -c "SELECT now();"
```

#### 2. Missing Dependencies

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

#### 3. Environment Variables Not Loading

**Error**: `DATABASE_URL not found`

**Solution**:

- Ensure `.env` file exists in the `backend` directory
- Check file permissions
- Verify variable names match exactly

#### 4. Frontend API Connection Issues

**Error**: `Failed to fetch from API`

**Solution**:

- Verify backend is running on `http://localhost:8000`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Ensure CORS is properly configured

#### 5. Pinecone Connection Issues

**Error**: `Pinecone connection failed`

**Solution**:

- Verify `PINECONE_API_KEY` is correct
- Check `PINECONE_INDEX` exists
- Ensure `PINECONE_HOST` is correct for your region

### Port Conflicts

If ports are already in use:

```bash
# Check what's using port 8000
lsof -i :8000

# Check what's using port 3000
lsof -i :3000

# Kill the process or use different ports
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
npm run dev -- -p 3001
```

