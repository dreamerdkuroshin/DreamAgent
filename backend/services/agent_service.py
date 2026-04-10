from sqlalchemy.orm import Session
from backend.core import models
import uuid


def get_agents(db: Session):
    return db.query(models.Agent).order_by(models.Agent.created_at.desc()).all()


def get_agent(db: Session, agent_id: str):
    return db.query(models.Agent).filter(models.Agent.id == agent_id).first()


def infer_provider(model_name: str) -> str:
    m = model_name.lower()
    if m.startswith("gpt-"): return "openai"
    if m.startswith("claude-"): return "claude"
    if "gemini" in m: return "gemini"
    if "deepseek" in m: return "deepseek"
    if "qwen" in m: return "qwen"
    if "grok" in m: return "groq"
    if "mistral" in m or "mixtral" in m: return "mistral"
    if "ernie" in m: return "ernie"
    if "amazon-nova" in m: return "nova"
    if "jamba" in m: return "jamba"
    if "cohere" in m: return "cohere"
    if "nimo" in m: return "nimo"
    if "zhipu" in m: return "zhipuai"
    if "minimax" in m: return "minimax"
    if "hermes" in m: return "together"
    if "replit" in m: return "replit"
    if "perplexity" in m: return "perplexity"
    if "ollama" in m: return "ollama"
    return "openai"


def create_agent(db: Session, agent_data: dict):
    model_name = agent_data.get("model", "gpt-4o-mini")
    provider = agent_data.get("provider", infer_provider(model_name))
    agent = models.Agent(
        id=agent_data.get("id", str(uuid.uuid4())),
        name=agent_data.get("name", "Unnamed Agent"),
        type=agent_data.get("type", "Worker"),
        model_name=model_name,
        provider=provider,
        status=agent_data.get("status", "idle"),
        description=agent_data.get("description", ""),
        system_prompt=agent_data.get("system_prompt", ""),
        capabilities=agent_data.get("capabilities", {}),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def update_agent(db: Session, agent_id: str, agent_data: dict):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        return None
    for key, value in agent_data.items():
        if hasattr(agent, key) and key != "id":
            if key == "model":
                agent.model_name = value
            else:
                setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent_id: str):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if agent:
        # Cascade manually for safety
        db.query(models.Memory).filter(models.Memory.agent_id == agent_id).delete(synchronize_session=False)
        db.query(models.Task).filter(models.Task.agent_id == agent_id).delete(synchronize_session=False)
        convs = db.query(models.Conversation).filter(models.Conversation.agent_id == agent_id).all()
        for c in convs:
            db.query(models.Message).filter(models.Message.conversation_id == c.id).delete(synchronize_session=False)
            db.query(models.Memory).filter(models.Memory.conversation_id == c.id).delete(synchronize_session=False)
            db.delete(c)
        db.delete(agent)
        db.commit()
        return True
    return False


def delete_all_agents(db: Session):
    """
    Fix #7: Delete in correct order including Conversations, Memory, and Messages
    to prevent orphaned records.
    """
    try:
        # Order: Memory → Messages → Conversations → Tasks → Agents
        db.query(models.Memory).delete(synchronize_session=False)
        db.query(models.Message).delete(synchronize_session=False)
        db.query(models.Conversation).delete(synchronize_session=False)
        db.query(models.Task).delete(synchronize_session=False)
        db.query(models.Agent).delete(synchronize_session=False)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
