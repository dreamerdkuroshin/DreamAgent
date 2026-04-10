"""
backend/core/fast_replies.py

Zero-latency template replies for instant casual messages.
No LLM. No memory. No agent. Pure Python lookup — ~0ms.
"""
import random

_PATTERNS = [
    # build website wizard
    (["build website", "build a website", "create website", "create a website", "make website", "make a website"],
     ["💬 USER-FRIENDLY PROMPT\nGot it 👍 I’ll build your website.\n\nJust tell me a few things (simple choices):\n\n1. 🎨 Design style:\n- Clean & modern (like Apple)\n- Luxury (premium look)\n- Colorful & fun\n- Simple/basic\n\n2. ⚙️ Features you want:\n(You can pick multiple)\n- 🛒 Sell products (shopping + payment)\n- 🔐 Login / user accounts\n- 📊 Dashboard (admin panel)\n- 📝 Blog or content pages\n\n3. 🧠 How powerful should it be?\n- Simple website (fast, no backend)\n- Full app (with database + login)"]),

    # wtf / broken
    (["wtf", "wtaf", "wth", "what the f", "what tf"],
     ["yeah bro that looks cooked 💀 what broke?",
      "damn 😬 what exploded?",
      "lol wtf happened 💀 spill",
      "yo that's cooked 💀 what's broken?"]),

    # broken / not working
    (["broken", "not working", "doesn't work", "isn't working", "stopped working", "not work"],
     ["damn 😬 what exactly broke?",
      "hmm that's off 🤔 what part isn't working?",
      "aight let's fix it — what's not working?",
      "oof 💀 what broke this time?"]),

    # what u doing / wyd / what are you doing
    (["what u doing", "what r u doing", "what are u doing", "what you doing",
      "what are you doing", "wyd", "watcha doing", "whatcha doing",
      "what u up to", "what r u up to", "what are u up to", "what you up to"],
     ["just chilling in the system 😎 what's up?",
      "vibing 👾 what do you need?",
      "running on electrons rn 💡 what's good?",
      "being a whole AI bro 😂 what u need?"]),

    # how are you / how u doing
    (["how r u", "how are u", "how u doing", "how you doing", "how are you", "how u been", "how you been", "u good", "you good", "u okay", "you okay", "u ok", "you ok"],
     ["I'm built different bro 😎 always good",
      "running smooth 🚀 what about you?",
      "all systems go 💯 u?",
      "never better bro 😄 what's up?"]),

    # u there / you there / r u there
    (["u there", "you there", "r u there", "are u there", "hello?", "anyone there"],
     ["yo I'm here 👀 what's up?",
      "present 🫡 what you need?",
      "yeah I'm here 😄 go ahead",
      "always here bro 👾 what's good?"]),

    # greetings
    (["hello", "hi", "hey", "heyy", "heyyy", "sup", "what's up", "whats up", "yo", "what's good", "whats good", "what's popping"],
     ["yo 😄 what's good?",
      "hey hey 👋 what's up?",
      "yo what's the vibe today 😎",
      "sup 👋 what you need?"]),

    # lol / lmao / 💀
    (["lol", "lmao", "lmfao", "haha", "hahaha"],
     ["lmao fr 💀",
      "😂 bro stop",
      "dead 💀💀",
      "lol same energy 😂"]),

    # bruh / bro
    (["bruh", "bro,", "bro.", "bro!", "bro?", "bro "],
     ["bro 💀 fr?",
      "bruh 😭",
      "nah bro 💀",
      "bro what 😂"]),

    # thanks / ty
    (["thanks", "thank you", "thx", "ty", "appreciate"],
     ["no cap anytime 😎",
      "bet 👍",
      "anytime bro 💯",
      "always 🤝"]),

    # ok / bet / cool
    (["ok", "okay", "cool", "got it", "aight", "alright", "bet", "say less"],
     ["bet 👍",
      "say less 🤙",
      "copy that 💯",
      "aight 🤝"]),

    # nice / fire / W
    (["nice", "great", "awesome", "sick", "fire", "lit", "goated", "w ", " w"],
     ["fr fr 🔥",
      "W 💯",
      "lesgo 🚀",
      "no cap that's fire 🔥"]),

    # bye
    (["bye", "goodbye", "cya", "later", "ttyl", "peace"],
     ["peace ✌️",
      "later bro 👋",
      "cya 🤙",
      "bet, peace 😎"]),

    # idk / idc
    (["idk", "i don't know", "idк", "idc", "i don't care"],
     ["fair enough 🤷",
      "same tbh 💀",
      "mood 😭",
      "relatable ngl"]),
]

_FALLBACKS = [
    "yo 😄 what's up?",
    "say what now? 👀",
    "hm 🤔 go on",
    "aight what you need 😎",
    "talk to me 👂",
    "I'm listening 👾",
    "real talk, what's up? 🤙",
]


def get_instant_reply(text: str) -> str:
    """Return a zero-latency template reply. No LLM. No imports. ~0ms."""
    t = text.lower().strip().rstrip("?!.")
    for keywords, replies in _PATTERNS:
        if any(k in t for k in keywords):
            return random.choice(replies)
    return random.choice(_FALLBACKS)
