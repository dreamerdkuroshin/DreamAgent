"""
backend/services/bot_service.py
CRUD operations for the platform Bots and Conversation bridging.
"""
from sqlalchemy.orm import Session
from backend.core.models import Bot, Conversation
import uuid

def create_bot(db: Session, name: str, platform: str, token: str, personality: str = "") -> Bot:
    bot = db.query(Bot).filter(Bot.token == token).first()
    if bot:
        return bot
    
    bot = Bot(
        id=str(uuid.uuid4()),
        name=name,
        platform=platform,
        token=token,
        personality=personality or "You are a helpful AI assistant."
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return bot

def get_bots(db: Session):
    return db.query(Bot).all()

def get_bot(db: Session, bot_id: str):
    return db.query(Bot).filter(Bot.id == bot_id).first()

def get_bot_by_token(db: Session, token: str):
    return db.query(Bot).filter(Bot.token == token).first()

def update_bot(db: Session, bot_id: str, data: dict):
    bot = get_bot(db, bot_id)
    if not bot:
        return None
    for k, v in data.items():
        if hasattr(bot, k) and k != "id":
            setattr(bot, k, v)
    db.commit()
    db.refresh(bot)
    return bot

def delete_bot(db: Session, bot_id: str):
    bot = get_bot(db, bot_id)
    if bot:
        db.delete(bot)
        db.commit()
        return True
    return False

def get_or_create_bot_conversation(db: Session, bot_id: str, platform_user_id: str) -> Conversation:
    """Gets or creates the Chat History mapping for a specific user talking to this bot.
    Uses the dedicated bot_id column for true multi-bot memory isolation."""
    conv = db.query(Conversation).filter(
        Conversation.is_bot == 1,
        Conversation.bot_id == bot_id,
        Conversation.platform_user_id == str(platform_user_id)
    ).first()
    
    if not conv:
        conv = Conversation(
            bot_id=bot_id,
            title=f"Chat {platform_user_id}",
            is_bot=1,
            platform_user_id=str(platform_user_id)
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        
    return conv
