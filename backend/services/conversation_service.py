from sqlalchemy.orm import Session

from sqlalchemy import func
from backend.core import models


def get_conversations(db: Session, agent_id: str = None):
    query = db.query(models.Conversation)
    if agent_id:
        query = query.filter(models.Conversation.agent_id == agent_id)
    return query.order_by(models.Conversation.updated_at.desc()).all()


def create_conversation(db: Session, agent_id: str, title: str = "New Conversation"):
    conversation = models.Conversation(agent_id=agent_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def update_conversation_timestamp(db: Session, conv_id: int):
    """Fix #6: Use func.now() to actually trigger the onupdate hook."""
    db.query(models.Conversation).filter(models.Conversation.id == conv_id).update(
        {"updated_at": func.now()}, synchronize_session=False
    )
    db.commit()


def get_messages(db: Session, conv_id: int):
    return (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conv_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )


def create_message(db: Session, conversation_id: int, role: str, content: str, provider: str = None, model: str = None):
    message = models.Message(conversation_id=conversation_id, role=role, content=content, provider=provider, model=model)
    db.add(message)
    
    # Auto-rename generic titles to match the user's first message
    conv = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if conv and role == "user":
        msg_count = db.query(models.Message).filter(models.Message.conversation_id == conversation_id).count()
        if msg_count == 0 or conv.title in ["New Conversation", "New Chat"]:
            snippet = content[:40].strip()
            if len(content) > 40:
                 snippet += "..."
            conv.title = snippet

    db.query(models.Conversation).filter(models.Conversation.id == conversation_id).update(
        {"updated_at": func.now()}, synchronize_session=False
    )
    db.commit()
    db.refresh(message)
    return message


def delete_conversation(db: Session, conv_id: int):
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if conv:
        db.query(models.Memory).filter(models.Memory.conversation_id == conv_id).delete(synchronize_session=False)
        db.query(models.Message).filter(models.Message.conversation_id == conv_id).delete(synchronize_session=False)
        db.delete(conv)
        db.commit()
        return True
    return False


def delete_all_conversations(db: Session):
    """Fix #8: Delete in correct order — Memory → Message → Conversation (Tasks stay, they are agent-linked)."""
    try:
        db.query(models.Memory).delete(synchronize_session=False)
        db.query(models.Message).delete(synchronize_session=False)
        db.query(models.Conversation).delete(synchronize_session=False)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
