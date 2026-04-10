from backend.llm.selector import get_llm

llm = get_llm("openai")

def summarize_messages(messages):
    text = "\n".join([f"{m.role}: {m.content}" for m in messages])
    
    prompt = f"""
Summarize this conversation into key points:

{text}
"""
    return llm.generate([{"role": "user", "content": prompt}])
