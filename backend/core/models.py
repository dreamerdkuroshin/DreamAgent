from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import os

from backend.core.database import Base

# Use pgvector only when using PostgreSQL runtime
_USE_PGVECTOR = os.environ.get("ACTIVE_DB_DIALECT") == "postgresql"
if _USE_PGVECTOR:
    try:
        from pgvector.sqlalchemy import Vector as _Vector
        _EMBEDDING_COL = lambda: Column(_Vector(1536))
    except Exception:
        _EMBEDDING_COL = lambda: Column(JSON, nullable=True)
else:
    # Fallback: store embedding as JSON when pgvector or Postgres is unavailable
    _EMBEDDING_COL = lambda: Column(JSON, nullable=True)

class ApiKey(Base):
    __tablename__ = "api_keys"
    service = Column(String, primary_key=True)
    key = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserProvider(Base):
    """Stores the specific API key a user has provided for a service (OpenAI, Groq, etc)"""
    __tablename__ = "user_providers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True, default="local")
    provider = Column(String, index=True) # e.g. 'openai', 'groq'
    api_key_encrypted = Column(Text) # Fernet encrypted
    is_verified = Column(Boolean, default=False)
    sync_status = Column(String, default="PENDING") # PENDING, SYNCING, READY, FAILED
    last_sync_error = Column(Text, nullable=True)
    models_hash = Column(String, nullable=True) # Hash of sorted canonical models list
    last_checked = Column(DateTime, default=datetime.utcnow)
    
    models = relationship("UserModelCache", back_populates="provider_record", cascade="all, delete-orphan")

class UserModelCache(Base):
    """Stores the dynamically discovered models specific to the user's API key"""
    __tablename__ = "user_model_cache"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_provider_id = Column(Integer, ForeignKey("user_providers.id", ondelete="CASCADE"), index=True)
    model_id = Column(String) # e.g. 'gpt-4o'
    label = Column(String)    # e.g. 'GPT-4O'
    tags = Column(String, nullable=True)     # e.g. 'Powerful,Fast'
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    provider_record = relationship("UserProvider", back_populates="models")

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String, index=True) # provider name (google, slack, etc)
    user_id = Column(String, index=True)
    bot_id = Column(String, index=True)
    
    access_token = Column(Text)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    scope = Column(Text, nullable=True)         # e.g. "gmail calendar drive"
    provider = Column(String, nullable=True)     # Canonical provider name
    key_version = Column(String, default="v1")   # Encryption key version for rotation
    token_json = Column(Text, nullable=True)     # Encrypted raw fallback payload
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UsageStat(Base):
    __tablename__ = "usage_stats"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tokens = Column(Integer)
    cost = Column(Float)
    model = Column(String)

class Agent(Base):
    __tablename__ = "agents"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    type = Column(String)
    model_name = Column("model", String) # Renamed attribute slightly to avoid keyword issues, mapped to 'model'
    provider = Column(String, default="openai")
    status = Column(String, default="idle")
    description = Column(Text)
    system_prompt = Column(Text)
    capabilities = Column(JSON, default=dict)
    task_count = Column(Integer, default=0)
    conversation_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="agent", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="agent", cascade="all, delete-orphan")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)
    
    # --- Multi-Bot Isolation Columns ---
    is_bot = Column(Integer, default=0) # 1 if this is a platform bot conversation (e.g. Telegram)
    bot_id = Column(String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=True)
    platform_user_id = Column(String, nullable=True) # User ID provided by the external platform
    
    title = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    bot = relationship("Bot", back_populates="conversations")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"))
    role = Column(String)
    content = Column(Text)
    model = Column(String, nullable=True)
    provider = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"))
    title = Column(String)
    description = Column(Text)
    status = Column(String, default="pending")
    priority = Column(String, default="medium")
    result = Column(Text, nullable=True)
    retries = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="tasks")

class Memory(Base):
    __tablename__ = "memory"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)
    
    # --- Multi-Bot Isolation Columns ---
    bot_id = Column(String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=True)
    platform_user_id = Column(String, nullable=True)
    
    content = Column(Text)
    category = Column(String)
    embedding = _EMBEDDING_COL()
    summary = Column(Text, nullable=True)
    
    # ── Advanced Scoping & Human-Like Memory Metrics ──
    scope = Column(String, default="personal") # global, agent, personal, core
    importance = Column(Float, default=0.5)    # Decays over time
    confidence = Column(Float, default=1.0)    # Confidence in fact accuracy
    access_count = Column(Integer, default=1)  # Increases reinforcement
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    bot = relationship("Bot", back_populates="memories")

class Bot(Base):
    __tablename__ = "bots"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    platform = Column(String) # telegram, discord, whatsapp
    token = Column(String, unique=True, index=True)
    personality = Column(Text, default="You are a helpful assistant.")
    embedding_provider = Column(String, default="local") # local, openai, gemini
    is_running = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversations = relationship("Conversation", back_populates="bot", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="bot", cascade="all, delete-orphan")


class TaskHistory(Base):
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    bot_id = Column(String, index=True)

    goal = Column(Text)
    plan = Column(JSON)
    result = Column(JSON)

    success = Column(Integer, default=0) # 1 for True
    created_at = Column(DateTime, default=datetime.utcnow)


class InstalledTool(Base):
    __tablename__ = "installed_tools"
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    bot_id = Column(String, index=True)
    tool_id = Column(String, index=True)

class AgentContext(Base):
    __tablename__ = "agent_context"
    user_id = Column(String, primary_key=True)
    bot_id = Column(String, primary_key=True)
    context = Column(JSON)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BuildSession(Base):
    """Tracks every builder-generated project for history, resume, and analytics."""
    __tablename__ = "build_sessions"

    id = Column(String, primary_key=True)  # e.g. session_abc12345
    user_id = Column(String, index=True, default="local_user")
    bot_id = Column(String, index=True, default="local_bot")

    project_name = Column(String, default="Untitled Project")
    project_type = Column(String)  # ecommerce | dashboard | landing | blog | portfolio
    design = Column(String)       # modern | luxury | colorful | simple
    
    version = Column(Integer, default=1)
    status = Column(String, default="idle") # idle | building | updating | completed | failed
    
    has_backend = Column(Integer, default=0)  # 0=static, 1=full-stack
    features = Column(JSON, default=dict)     # {auth, payment, dashboard}

    file_count = Column(Integer, default=0)
    path = Column(String) # Root directory

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("BuildVersion", back_populates="session", cascade="all, delete-orphan", order_by="BuildVersion.version")


class BuildVersion(Base):
    """Tracks individual version snapshots for a build session."""
    __tablename__ = "build_versions"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, ForeignKey("build_sessions.id", ondelete="CASCADE"), index=True)
    version = Column(Integer)
    path = Column(Text)
    message = Column(Text)        # e.g. "added dark mode", "initial build"
    is_active = Column(Integer, default=1)  # 1 = active, 0 = inactive
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("BuildSession", back_populates="versions")

class BuildTelemetry(Base):
    __tablename__ = "build_telemetry"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String, index=True)
    event_type = Column(String)  # update_success, update_fail, rollback, deploy_success, deploy_fail
    fix_attempts = Column(Integer, default=0) # Track how many iterations the Fixer Agent took
    created_at = Column(DateTime, default=datetime.utcnow)
