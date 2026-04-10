from sqlalchemy.orm import Session
from backend.core import models
import json

def save_api_key(db: Session, service: str, key: str):
    api_key = db.query(models.ApiKey).filter(models.ApiKey.service == service).first()
    if api_key:
        api_key.key = key
    else:
        api_key = models.ApiKey(service=service, key=key)
        db.add(api_key)
    db.commit()

def get_api_key(db: Session, service: str):
    api_key = db.query(models.ApiKey).filter(models.ApiKey.service == service).first()
    if api_key:
        return api_key.key
    return None

def save_oauth_token(db: Session, service: str, token_dict: dict):
    oauth_token = db.query(models.OAuthToken).filter(models.OAuthToken.service == service).first()
    if oauth_token:
        oauth_token.token_json = json.dumps(token_dict)
    else:
        oauth_token = models.OAuthToken(service=service, token_json=json.dumps(token_dict))
        db.add(oauth_token)
    db.commit()

def get_oauth_token(db: Session, service: str):
    oauth_token = db.query(models.OAuthToken).filter(models.OAuthToken.service == service).first()
    if oauth_token:
        return json.loads(oauth_token.token_json)
    return None

def log_usage(db: Session, tokens: int, model: str, cost: float = 0.0):
    usage = models.UsageStat(tokens=tokens, model=model, cost=cost)
    db.add(usage)
    db.commit()
