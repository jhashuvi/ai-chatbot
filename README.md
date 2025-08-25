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

**Option A: Using Docker (Recommended)**

```bash
# Start PostgreSQL with Docker
docker run --name ai-chatbot-db \
  -e POSTGRES_DB=chatbot \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -d postgres:15

# Wait a few seconds for database to start
sleep 5
```

**Option B: Local PostgreSQL**

1. Install PostgreSQL on your system
2. Create a database named `chatbot`
3. Update the `DATABASE_URL` in your environment variables

#### Environment Configuration

Create a `.env` file in the `backend` directory:

```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/chatbot

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key-here
PINECONE_INDEX=your-pinecone-index-name
PINECONE_HOST=https://your-pinecone-host

# JWT Authentication
JWT_SECRET=your-super-secret-jwt-key-here
JWT_ALG=HS256
JWT_EXPIRE_MIN=60

# Optional: Development settings
SQL_ECHO=true
LOG_LEVEL=INFO
```

#### Run Database Migrations

```bash
# Make sure you're in the backend directory with venv activated
alembic upgrade head
```

#### Start the Backend Server

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend will be available at `http://localhost:8000`

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

## 🧪 Testing the Application

### 1. Health Check

Visit the backend health endpoint:

```
http://localhost:8000/healthz
```

You should see a response indicating the service is healthy.

### 2. API Documentation

Access the interactive API documentation:

```
http://localhost:8000/docs
```

### 3. Chat Interface

Open your browser and navigate to:

```
http://localhost:3000
```

You should see the chat interface with:

- Welcome screen for new conversations
- Sidebar for session management
- Authentication modal (if not logged in)

### 4. Test Conversations

Try these example queries to test the system:

- **Simple greeting**: "Hello, how are you?"
- **Fintech question**: "What are the transfer limits?"
- **Specific query**: "How do I reset my password?"
- **Vague query**: "What's the limit?" (should trigger abstention)

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

# Linting
npm run lint

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
docker start ai-chatbot-db

# Or check your local PostgreSQL service
sudo systemctl status postgresql
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

### Debug Mode

Enable debug logging by setting in your `.env`:

```bash
LOG_LEVEL=DEBUG
SQL_ECHO=true
```

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

## 📁 Project Structure

```
ai-chatbot/
├── backend/
│   ├── app/
│   │   ├── clients/          # External API clients (OpenAI, Pinecone)
│   │   ├── models/           # Database models
│   │   ├── repositories/     # Data access layer
│   │   ├── routers/          # API endpoints
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic (Intent, RAG, Chat)
│   │   ├── config.py         # Configuration management
│   │   ├── database.py       # Database connection
│   │   └── main.py           # FastAPI application
│   ├── alembic/              # Database migrations
│   ├── requirements.txt      # Python dependencies
│   └── .env                  # Environment variables
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js app directory
│   │   ├── components/       # React components
│   │   ├── lib/              # Utilities and API client
│   │   └── types/            # TypeScript type definitions
│   ├── package.json          # Node.js dependencies
│   └── .env.local            # Frontend environment variables
└── README.md                 # This file
```

## 🔐 Security Notes

- Never commit API keys or secrets to version control
- Use strong JWT secrets in production
- Regularly update dependencies for security patches
- Enable HTTPS in production environments
- Implement proper rate limiting for production use

## 🚀 Production Deployment

For production deployment, see the AWS deployment architecture in the project documentation or refer to the deployment guide.

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the logs for error messages
3. Verify all environment variables are set correctly
4. Ensure all services (PostgreSQL, backend, frontend) are running

## 📄 License

[Add your license information here]

---

**Happy coding! 🎉**
