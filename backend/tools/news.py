import logging
import json
import asyncio
import nest_asyncio
import urllib.parse
from datetime import datetime, timezone
import feedparser

# External libraries
try:
    from langdetect import detect
except ImportError:
    def detect(text): return "en"

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    pass

from backend.tools.base import Tool
from backend.llm.universal_provider import universal_provider

logger = logging.getLogger(__name__)

# Apply nest_asyncio to allow asyncio.run() inside async environment
nest_asyncio.apply()

# Initialize global models lazily to avoid startup delay
_MODEL = None
_MODEL_LOCK = asyncio.Lock()

async def get_embedding_model():
    # Fix 5: Disable heavy embedding model load for Fast Mode (which is default now)
    return None

# All 195 countries
COUNTRIES_195 = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", 
    "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", 
    "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", 
    "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", 
    "Comoros", "Congo (Congo-Brazzaville)", "Costa Rica", "Côte d'Ivoire", "Croatia", "Cuba", "Cyprus", "Czechia", 
    "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", 
    "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", 
    "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", 
    "Guyana", "Haiti", "Holy See", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", 
    "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan", 
    "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", 
    "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", 
    "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", 
    "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", 
    "Oman", "Pakistan", "Palau", "Palestine State", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", 
    "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", 
    "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", 
    "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", 
    "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", 
    "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", 
    "Tunisia", "Turkiye", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", 
    "United States of America", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", 
    "Zambia", "Zimbabwe"
]

REGION_MAP = {
    "European Union": {"Germany", "France", "Italy", "Spain", "Netherlands", "Belgium", "Poland", "Sweden", "Austria", "Greece"},
    "G7": {"United States of America", "Japan", "Germany", "United Kingdom", "France", "Italy", "Canada"},
    "GCC": {"Saudi Arabia", "United Arab Emirates", "Qatar", "Kuwait", "Oman", "Bahrain"},
    "ASEAN": {"Indonesia", "Thailand", "Vietnam", "Singapore", "Malaysia", "Philippines", "Cambodia", "Laos", "Myanmar", "Brunei"},
    "BRICS": {"Brazil", "Russia", "India", "China", "South Africa", "Iran", "Egypt", "Ethiopia", "United Arab Emirates"}
}

def get_country_flag(country_name):
    # Mapping for quick flag lookup
    flags = {
        "United States of America": "🇺🇸", "US": "🇺🇸", "USA": "🇺🇸",
        "China": "🇨🇳", "Russia": "🇷🇺", "India": "🇮🇳", "Japan": "🇯🇵",
        "United Kingdom": "🇬🇧", "UK": "🇬🇧", "Germany": "🇩🇪", "France": "🇫🇷",
        "Israel": "🇮🇱", "Iran": "🇮🇷", "Ukraine": "🇺🇦", "Saudi Arabia": "🇸🇦",
        "North Korea": "🇰🇵", "South Korea": "🇰🇷", "Canada": "🇨🇦", "Australia": "🇦🇺"
    }
    return flags.get(country_name, "🌍")

def format_group_name(countries):
    if not countries: return "Global"
    
    # Check for region matches
    country_set = set(countries)
    for region, members in REGION_MAP.items():
        if country_set.issubset(members) and len(countries) >= 3:
            return f"{get_country_flag(countries[0])} {region}"
            
    if len(countries) == 1:
        return f"{get_country_flag(countries[0])} {countries[0]}"
    if len(countries) <= 3:
        return f"{get_country_flag(countries[0])} " + ", ".join(countries)
    return f"{get_country_flag(countries[0])} {countries[0]} +{len(countries)-1}"

RSS_FEEDS = {
    "Global": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "US": "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
    "Asia": "http://feeds.bbci.co.uk/news/world/asia/rss.xml",
    "Europe": "http://feeds.bbci.co.uk/news/world/europe/rss.xml",
    "Middle East": "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml"
}

# Source quality mapping lookup
QUALITY_MAP = {
    "bbc": 1.0,
    "reuters": 1.0,
    "ap": 1.0,
    "aljazeera": 0.9,
    "nytimes": 0.9,
    "cnn": 0.8,
    "foxnews": 0.6
}

# Minimum articles needed before considering a source "successful"
MIN_ARTICLES_THRESHOLD = 3

def clean_search_query(query: str, region: str = "") -> str:
    """Remove filler words and optimize query for news search engines."""
    filler_words = {
        "now", "give", "me", "about", "latest", "recent", "today",
        "show", "tell", "get", "find", "search", "the", "some", "in",
        "please", "can", "you", "what", "is", "are", "of", "for",
        "whats", "what's", "happening", "going", "on",
    }
    words = query.lower().split()
    cleaned = [w for w in words if w not in filler_words]
    # If everything was filler and we have a region, use that
    if not cleaned and region:
        cleaned = [region.lower()]
    # Ensure "news" is in the query for better search results
    if cleaned and not any(w in ["news", "headlines", "update", "updates"] for w in cleaned):
        cleaned.append("news")
    result = " ".join(cleaned).strip()
    return result if result else query


async def fetch_rss(feed_url: str):
    try:
        def parse():
            import feedparser
            return feedparser.parse(feed_url)
        feed = await asyncio.to_thread(parse)
        articles = []
        for entry in feed.entries[:10]: # Top 10 from each feed
            articles.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", "")[:300],
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": feed_url
            })
        return articles
    except Exception as e:
        logger.warning(f"Error fetching RSS {feed_url}: {e}")
        return []


async def fetch_google_news_rss(query: str):
    """Reliable Google News RSS feed fetcher — much more stable than HTML scraping."""
    try:
        def parse():
            encoded = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[:8]:
                title = entry.get("title", "")
                source_name = "Google News"
                # Google News RSS titles often end with " - Source Name"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source_name = parts[1].strip() if len(parts) > 1 else "Google News"

                # Extract plain text from summary (it's often HTML)
                raw_summary = entry.get("summary", "")
                try:
                    from bs4 import BeautifulSoup
                    summary = BeautifulSoup(raw_summary, "html.parser").get_text()[:300]
                except Exception:
                    summary = raw_summary[:300]

                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": source_name
                })
            return articles
        return await asyncio.to_thread(parse)
    except Exception as e:
        logger.warning(f"Error fetching Google News RSS {query}: {e}")
        return []


async def fetch_bing_news(query: str):
    """Bing News Scraper with multiple selector patterns for resilience."""
    try:
        def scrape():
            import requests
            from bs4 import BeautifulSoup
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36"
            }
            url = f"https://www.bing.com/news/search?q={urllib.parse.quote(query)}&form=NSBABR"
            req = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(req.text, "html.parser")

            articles = []

            # Strategy 1: Try multiple known Bing card selectors
            items = []
            selector_attempts = [
                ("div", {"class": "news-card"}),
                ("div", {"class": "card-with-cluster"}),
                ("a",   {"class": "news-card"}),
                ("div", {"data-type": "news"}),
            ]
            for tag, attrs in selector_attempts:
                items = soup.find_all(tag, attrs)[:8]
                if items:
                    break

            # Strategy 2: CSS multi-selector fallback
            if not items:
                items = soup.select(
                    "div.news-card, a.news-card, "
                    "div[data-type='news'], .card-with-cluster, "
                    ".t_t, .caption"
                )[:8]

            for item in items[:6]:
                a_tag = item.find("a", class_="title") or item.find("a")
                if not a_tag:
                    continue
                title = a_tag.text.strip()
                link = a_tag.get("href", "")
                if not title or len(title) < 10:
                    continue

                snippet = (
                    item.find("div", class_="snippet")
                    or item.find("p")
                    or item.find("div", class_="caption")
                )
                summary = snippet.text.strip() if snippet else ""

                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": "",
                    "source": "Bing News"
                })
            return articles
        return await asyncio.to_thread(scrape)
    except Exception as e:
        logger.warning(f"Error fetching Bing News {query}: {e}")
        return []

async def fetch_ddg_news(query: str):
    try:
        def req():
            try:
                import time, random
                from ddgs import DDGS
                time.sleep(random.uniform(1.5, 3.5))  # anti-rate-limit
                with DDGS() as ddgs:
                    results = ddgs.news(query, max_results=5) # User Request: max articles = 5
                    return list(results) if results else []
            except Exception as inner_e:
                logger.warning(f"DDGS failure: {inner_e}")
                return []
                
        data = await asyncio.to_thread(req)
        articles = []
        for r in data:
            articles.append({
                "title": r.get("title", ""),
                "summary": r.get("body", ""),
                "link": r.get("url", ""),
                "published": r.get("date", ""),
                "source": r.get("source", "DuckDuckGo News")
            })
        return articles
    except Exception as e:
        logger.warning(f"Error fetching DDG {query}: {e}")
        return []

import time

CACHE = {}

def get_cached(query):
    item = CACHE.get(query)
    if not item: return None
    # Expire after 1 hour (3600s)
    if time.time() - item.get("time", 0) > 3600:
        return None
    return item.get("data")

def set_cache(query, data):
    CACHE[query] = {
        "data": data,
        "time": time.time()
    }

async def fetch_google_news(query: str):
    """Fallback scraper when DDGS fails."""
    try:
        def scrape():
            import requests
            from bs4 import BeautifulSoup
            
            headers = {"User-Agent": "Mozilla/5.0"}
            url = f"https://news.google.com/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            req = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(req.text, "html.parser")
            
            articles = []
            for item in soup.find_all("article")[:5]: # User Request: MAX_ARTICLES = 5
                a_tag = item.find("a")
                if not a_tag: continue
                title = a_tag.text.strip()
                href = a_tag.get("href", "")
                link = f"https://news.google.com{href[1:]}" if href.startswith(".") else href
                
                divs = item.find_all("div")
                summary = divs[0].text.strip() if divs else ""
                
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": "", 
                    "source": "Google News"
                })
            return articles
            
        return await asyncio.to_thread(scrape)
    except Exception as e:
        logger.warning(f"Error fetching Google News {query}: {e}")
        return []


def filter_by_language(articles: list, filter_langs: list) -> list:
    """
    Filters articles by a list of acceptable languages.
    Always accepts English as universal fallback.
    If fewer than 3 articles match, pads with English-language articles.

    filter_langs: list of BCP-47 language codes to include (e.g. ['hi', 'ja'])
    """
    # English is always allowed (global news is mostly English)
    accepted = set(filter_langs) | {"en"}

    matched = []
    english_fallbacks = []

    for article in articles:
        text = (article.get("title", "") + " " + article.get("summary", "")).strip()
        if not text:
            continue
        try:
            lang = detect(text)
        except Exception:
            lang = "en"

        if lang in accepted and lang != "en":
            matched.append(article)
        elif lang == "en":
            english_fallbacks.append(article)

    if len(matched) >= 3:
        logger.info(f"[LangFilter] {len(matched)} articles in {filter_langs}, using them.")
        return matched

    # Pad with English when not enough native-language articles
    logger.info(
        f"[LangFilter] Only {len(matched)} native articles; "
        f"padding with {len(english_fallbacks)} English fallbacks."
    )
    return matched + english_fallbacks


async def llm_extract_facts_perspectives(cluster_articles, user_lang="en"):
    cluster_articles = cluster_articles[:6]
    # LLM extraction of facts and perspectives
    text_corpus = "\n".join([f"- SOURCE_URL: {a['link']} TITLE: {a['title']}\n  SUMMARY: {a['summary']}" for a in cluster_articles])
    
    prompt = f"""
    Analyze the following news articles about a single event.
    
    🔴 LANGUAGE LOCK: You MUST write ALL output ONLY in this language: '{user_lang}'.
    Do NOT mix languages. Do NOT output in English if the requested language is different.
    If the articles are in a different language, still write the entire output in: '{user_lang}'.

    STRICT RULES:
    - ALL facts must be verifiable from the source articles. Do NOT invent or infer facts.
    - Use NEUTRAL, FACTUAL language only. Do NOT use framing like "Western dominance",
      "aggression", "regime", or any politically loaded terms.
    - For any stance or claim by a country or organization, prefix it with:
        "Reported stance: ..." or "According to [source]: ..."
    - Do NOT express personal or editorial opinions.
    - Each fact must list ALL source URLs that support it in a 'sources' array.
    - Each perspective must list ALL source URLs in a 'sources' array.
    - 'evidence_count' for each fact MUST equal the exact number of items in its 'sources' array.
    - Entity types must be one of: "country" or "organization".

    Extract:
    1. Verified facts (details corroborated across multiple reports). Associate the exact 'SOURCE_URL'.
    2. RAW national/organization perspectives. Identify EVERY country or organization mentioned
       as having a stance. Associate the exact 'SOURCE_URL' for EACH.

    Articles:
    {text_corpus}

    Return ONLY a valid JSON object in this exact format (no extra keys):
    {{
      "event_title": "A short, neutral title for the event",
      "facts": [
         {{
           "fact": "...",
           "sources": ["url1", "url2"],
           "confidence": "high",
           "evidence_count": 2
         }}
      ],
      "raw_perspectives": [
         {{
           "entity_type": "country",
           "country": "Country Name",
           "view": "Reported stance: ...",
           "sources": ["url1", "url2"]
         }}
      ]
    }}
    """
    try:
        # Wrap LLM call with a timeout so it doesn't stall the pipeline
        res = await asyncio.wait_for(universal_provider.complete(prompt), timeout=20.0)
        res_cleaned = res.strip()
        if "```json" in res_cleaned:
            res_cleaned = res_cleaned.split("```json")[-1].split("```")[0].strip()
        elif "```" in res_cleaned:
            res_cleaned = res_cleaned.split("```")[-1].split("```")[0].strip()
        
        data = json.loads(res_cleaned)
        
        # Fast Mode / Load Reductions bypass embeddings entirely
        # Directly format facts to reduce LLM overhead
        validated_facts = []
        for f in data.get("facts", []):
            raw_sources = f.get("sources", [])
            if isinstance(raw_sources, str):
                raw_sources = [raw_sources] if raw_sources else []
            f["sources"] = raw_sources
            f.pop("source", None)
            f["evidence_count"] = max(1, len(f["sources"]))
            f["confidence"] = "high"
            validated_facts.append(f)
        
        data["facts"] = validated_facts
        
        # Deterministic Perspective Grouping bypassed for extreme speed (Fix 5)
        raw_p = data.get("raw_perspectives", [])
        if not raw_p:
            data["groups"] = []
            return data
            
        groups = []
        for p in raw_p:


            p_sources = p.get("sources", [])
            if isinstance(p_sources, str): p_sources = [p_sources] if p_sources else []
            entity_type = p.get("entity_type", "country")
            groups.append({
                "countries": [p.get("country", "")],
                "entities": [{"type": entity_type, "name": p.get("country", "")}],
                "view": p.get("view", ""),
                "sources": p_sources
            })

        # Final formatting for groups
        final_groups = []
        for g in groups:
            src_count = len(g["sources"])
            final_groups.append({
                "label": format_group_name(g["countries"]),
                "entities": g["entities"],
                "view": g["view"],
                "sources": g["sources"],
                "strength": "strong" if src_count >= 3 else ("medium" if src_count == 2 else "weak")
            })

        # Ensure Global is always present if not found
        if not any("Global" in g["label"] for g in final_groups):
             global_srcs = list(set([a["link"] for a in cluster_articles[:2]]))
             final_groups.insert(0, {
                 "label": "🌍 Global",
                 "entities": [{"type": "organization", "name": "Global"}],
                 "view": "Broad international coverage of this event.",
                 "sources": global_srcs,
                 "strength": "medium" if len(global_srcs) >= 2 else "weak"
             })

        data["groups"] = final_groups
        return data
    except Exception as e:
        logger.warning(f"Failed LLM extraction: {e}")
        fallback_link = cluster_articles[0].get("link", "")
        fallback_sources = [fallback_link] if fallback_link else []
        return {
            "event_title": cluster_articles[0].get("title", "Event"),
            "facts": [{
                "fact": cluster_articles[0].get("summary", "")[:100],
                "sources": fallback_sources,
                "evidence_count": len(fallback_sources),
                "confidence": "low"
            }],
            "groups": [{
                "label": "🌍 Global",
                "entities": [{"type": "organization", "name": "Global"}],
                "view": "Reported stance: Diverse international sources are covering this event.",
                "sources": fallback_sources,
                "strength": "weak"
            }]
        }

def calculate_score(query: str, article: dict, cluster_size: int) -> float:
    # Keyword match
    q_words = set((query or "").lower().split())
    text_words = set((article.get("title", "") + " " + article.get("summary", "")).lower().split())
    keyword_match = len(q_words.intersection(text_words)) / max(1, len(q_words)) if q_words else 0.5
    
    # Recency
    recency_score = 0.8
    if article.get("published"):
        recency_score = 1.0
        
    # Quality
    source = article.get("source", "").lower()
    source_quality = 0.5
    for k, v in QUALITY_MAP.items():
        if k in source:
            source_quality = v
            break
            
    # Diversity bonus based on cluster size
    diversity_bonus = min(1.0, cluster_size * 0.1)
    
    # Normalizing cluster size
    norm_cluster_size = min(1.0, cluster_size / 5.0)
    
    score = (
        keyword_match * 0.3 +
        recency_score * 0.25 +
        source_quality * 0.15 +
        diversity_bonus * 0.1 +
        norm_cluster_size * 0.2
    )
    return score

class NewsAnalystTool(Tool):
    def run(self, input_data: str) -> str:
        # Avoid issues where the event loop is already running in modern FastAPI
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # nest_asyncio handles this
                return loop.run_until_complete(self.arun(input_data))
        except RuntimeError:
            pass
            
        return asyncio.run(self.arun(input_data))
        
    async def arun(self, input_data: str) -> str:
        try:
            query = str(input_data).strip()
            if not query:
                return "Error: Empty query provided."

            # ── Smart language intent parsing ────────────────────────────────────
            # Rule: "in hindi" = OUTPUT language directive, not search language
            # Rule: country name = SOURCE language to search from
            #
            # Examples:
            #   "Japanese news in Hindi"  → search_langs=["ja","en"], output_lang="hi"
            #   "India news"              → search_langs=["hi","en"], output_lang="hi"
            #   "give me latest news"     → search_langs=["en"],      output_lang="en"

            OUTPUT_LANG_PHRASES = {
                "in hindi": "hi",  "in english": "en",  "in japanese": "ja",
                "in french": "fr", "in spanish": "es",  "in arabic": "ar",
                "in urdu": "ur",   "in chinese": "zh",  "in german": "de",
                "in korean": "ko", "in portuguese": "pt",
            }

            output_lang = None
            clean_query = query.lower()
            for phrase, lang_code in OUTPUT_LANG_PHRASES.items():
                if phrase in clean_query:
                    output_lang = lang_code
                    # Strip the directive from the query used for searching
                    clean_query = clean_query.replace(phrase, "").strip()
                    break

            # Detect language of the query itself
            detected_query_lang = "en"
            try:
                detected_query_lang = detect(query)
            except Exception:
                pass

            # Determine output language: explicit directive wins, else query language
            if output_lang is None:
                output_lang = detected_query_lang

            # Determine search languages: query lang + any country's primary language
            search_langs = [detected_query_lang]
            # Always include English for maximum coverage
            if "en" not in search_langs:
                search_langs.append("en")

            # Use English version of query for searching when output lang differs
            search_query = clean_query if clean_query else query

            # Auto Mode detection + ISO Aliases map
            COUNTRY_ALIASES = {
                "japan": ("Japan", "ja"), "जापान": ("Japan", "ja"), "japon": ("Japan", "ja"),
                "india": ("India", "hi"), "भारत": ("India", "hi"), "bharat": ("India", "hi"),
                "china": ("China", "zh"), "चीन": ("China", "zh"), "chine": ("China", "zh"),
                "germany": ("Germany", "de"), "जर्मनी": ("Germany", "de"), "deutschland": ("Germany", "de"),
                "france": ("France", "fr"), "फ्रांस": ("France", "fr"),
                "russia": ("Russia", "ru"), "रूस": ("Russia", "ru"),
                "usa": ("United States", "en"), "america": ("United States", "en"), "अमेरिका": ("United States", "en"),
                "uk": ("United Kingdom", "en"), "england": ("United Kingdom", "en"),
                "israel": ("Israel", "he"), "इस्राइल": ("Israel", "he"), "इजरायल": ("Israel", "he"),
                "ukraine": ("Ukraine", "uk"), "यूक्रेन": ("Ukraine", "uk")
            }

            mode = "multi"
            region = ""
            
            # 1. Check robust aliases
            for alias, (normalized_name, iso_code) in COUNTRY_ALIASES.items():
                if alias in clean_query:
                    mode = "country"
                    region = normalized_name
                    if iso_code not in search_langs:
                        search_langs.append(iso_code)
                    # Normalize the search query by swapping alias for english name
                    search_query = search_query.lower().replace(alias, normalized_name)
                    break
                    
            # 2. Fallback to full 195 list
            if mode == "multi":
                for c in COUNTRIES_195:
                    if c.lower() in clean_query:
                        mode = "country"
                        region = c
                        break

            logger.info(
                f"[NewsAnalyst] Query: '{query}', Mode: {mode}, Region: '{region}', "
                f"output_lang: '{output_lang}', search_langs: {search_langs}"
            )

            # ── Clean the search query for better search engine results ──────────
            search_query = clean_search_query(search_query, region)
            logger.info(f"[NewsAnalyst] Cleaned search query: '{search_query}'")

            # ── Fetch data with both original + English queries ──────────────────
            search_queries = list(dict.fromkeys([
                search_query,
                *([] if detected_query_lang == "en" else [f"{search_query}"]),
            ]))
            # For country mode, also add "<country> latest news" variant
            if mode == "country" and region:
                search_queries.append(f"{region} latest news")

            logger.info(f"[NewsAnalyst] Search queries: {search_queries}")

            # ── Fetch data using Multi-Source Aggregation Strategy ──────────────
            articles = []

            async def try_gnews_rss():
                tasks = [fetch_google_news_rss(q) for q in search_queries]
                res_list = await asyncio.gather(*tasks, return_exceptions=True)
                flat = []
                for r in res_list:
                    if isinstance(r, list): flat.extend(r)
                return flat

            async def try_bing_news():
                tasks = [fetch_bing_news(q) for q in search_queries]
                res_list = await asyncio.gather(*tasks, return_exceptions=True)
                flat = []
                for r in res_list:
                    if isinstance(r, list): flat.extend(r)
                return flat

            async def try_gnews():
                tasks = [fetch_google_news(q) for q in search_queries]
                res_list = await asyncio.gather(*tasks, return_exceptions=True)
                flat = []
                for r in res_list:
                    if isinstance(r, list): flat.extend(r)
                return flat

            async def try_ddg():
                ddg_tasks = []
                for q in search_queries:
                    ddg_tasks.append(fetch_ddg_news(q))
                    if mode == "multi":
                        ddg_tasks.append(fetch_ddg_news(f"{q} global world international news"))
                        ddg_tasks.append(fetch_ddg_news(f"{q} Asia Africa Europe America"))
                res_list = await asyncio.gather(*ddg_tasks, return_exceptions=True)
                flat = []
                for r in res_list:
                    if isinstance(r, list): flat.extend(r)
                return flat
                
            async def try_rss():
                rss_tasks = []
                for key, url in RSS_FEEDS.items():
                    if mode == "multi" or (mode == "country" and region and region.lower() in key.lower()):
                        rss_tasks.append(fetch_rss(url))
                res_list = await asyncio.gather(*rss_tasks, return_exceptions=True)
                flat = []
                for r in res_list:
                    if isinstance(r, list): flat.extend(r)
                return flat

            def progress(msg):
                # FIX 2: Stream Progress events
                from backend.core.worker_state import WorkerState
                from backend.core.task_queue import redis_conn
                # Attempt to extract context if running inside worker
                try:
                    for task_id, info in WorkerState._states.items():
                        if info.get("status") == "running" or info.get("status") == "pending":
                            redis_conn.rpush(f"task:{task_id}:events", json.dumps({"type": "token", "content": f"\n[{msg}]\n"}))
                except: pass
                
            progress("Fetching news sources...")

            # ── Aggregation strategy: try sources until we have enough articles ──
            # Google News RSS is most reliable, so it goes first
            sources = [try_gnews_rss, try_bing_news, try_ddg, try_gnews, try_rss]
            seen_titles_early = set()
            for source_func in sources:
                try:
                    result = await source_func()
                    if result:
                        for a in result:
                            t = a.get("title", "").strip().lower()
                            if t and t not in seen_titles_early:
                                articles.append(a)
                                seen_titles_early.add(t)
                        logger.info(f"[NewsAnalyst] {source_func.__name__} returned {len(result)} articles, total now: {len(articles)}")
                except Exception as e:
                    logger.warning(f"[NewsAnalyst] {source_func.__name__} failed: {e}")
                # Break once we have enough articles
                if len(articles) >= MIN_ARTICLES_THRESHOLD:
                    break
                    
            print({
                "intent": "news",
                "input_lang": detected_query_lang,
                "output_lang": output_lang,
                "search_langs": search_langs,
                "fetched_count": len(articles)
            })
                
            if not articles:
                cached = get_cached(search_query)
                if cached:
                    return cached
                return "No live news found for your query. Please try again with different keywords."
                
            # Deduplicate
            unique_articles = []
            seen_titles = set()
            for a in articles:
                if a["title"] not in seen_titles and len(a.get("summary", "")) > 10:
                    unique_articles.append(a)
                    seen_titles.add(a["title"])
                    
            if not unique_articles:
                return "No unique news articles found. Try again with a more specific query."

            # 🔴 LANGUAGE FILTER: Must run BEFORE clustering to prevent language bleed
            unique_articles = filter_by_language(unique_articles, search_langs)
            logger.info(f"[NewsAnalyst] {len(unique_articles)} articles after language filtering.")

            if not unique_articles:
                return "No recent news found for your query. Try searching in English for broader results."
            
            # Disable embedding-based clusters for extreme speed
            top_clusters = [{"articles": unique_articles, "embeddings": [], "score": 1.0}]
            
            progress("Analyzing news perspectives...")
            # Process cluster with LLM (Hard timeout protection Fix 4)
            try:
                llm_tasks = [asyncio.wait_for(llm_extract_facts_perspectives(c["articles"], output_lang), timeout=40.0) for c in top_clusters]
                extracted_results = await asyncio.gather(*llm_tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"[News Tool] LLM Extract Timeout: {e}")
                extracted_results = [Exception(f"Timeout: {e}")]
                
            progress("Formatting report...")
            
            output_clusters = []
            for i, c in enumerate(top_clusters):
                ext = extracted_results[i]
                if isinstance(ext, Exception):
                    continue
                ext["sources"] = [{"title": a["title"][:50] + "...", "url": a["link"]} for a in c["articles"][:3] if a["link"]]
                output_clusters.append(ext)
                
            # Result formatting
            result_json = {
                "type": "news_cluster",
                "mode": mode,
                "region": region,
                "query": query,
                "clusters": output_clusters
            }
            
            # Add structured JSON to allow frontend to intercept and render UI
            md_lines = []
            
            # Partial Success Mode header
            if len(articles) < 5:
                md_lines.append("⚠️ **Live data limited. Showing best available sources.**\n")
            
            md_lines.append(f"```json:news_cluster\n{json.dumps(result_json, indent=2)}\n```\n")
            md_lines.append(f"## 📰 News Analyst Report: {query}")
            for c in output_clusters:
                md_lines.append(f"### {c.get('event_title', 'Event')}")
                md_lines.append(f"**Facts:**\n" + "\n".join([f"- {f.get('fact', '')} (Confidence: {f.get('confidence', 'N/A')})" for f in c.get('facts', [])]))
                md_lines.append(f"**Perspectives:**")
                for g in c.get('groups', []):
                    md_lines.append(f"- {g['label']}: {g['view']}")
                md_lines.append(f"**Sources:**\n" + "\n".join([f"- 🔗 [{s['title']}]({s['url']})" for s in c.get('sources', [])]))
                md_lines.append("\n---\n")
                
            final_report = "\n".join(md_lines)
            set_cache(search_query, final_report)
            return final_report
            
        except Exception as e:
            logger.error(f"[NewsAnalyst] Failed: {e}", exc_info=True)
            return f"Error executing internal News Analyst tool: {str(e)}"
