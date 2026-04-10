from backend.core.models import Message

def get_recent_messages(db, conversation_id: int, limit: int = 10):
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
