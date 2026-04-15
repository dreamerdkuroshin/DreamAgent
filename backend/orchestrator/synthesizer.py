"""
backend/orchestrator/synthesizer.py

Response Synthesizer.
Merges partial results, ignores failed steps transparently,
and produces a clean final answer.
"""
import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def enforce_citations(text: str) -> tuple[str, int, int]:
    """
    Programmatic Truth-Grade enforcement.
    Ensures every claim has a [Source: https://...] verifiable link.
    Replaces named-only or protocol-less citations with a warning.
    """
    missing_count = 0
    grouped_count = 0

    if not text:
        return "", 0, 0

    # 1. Regex definitions
    # Valid: [Source: https://...]
    VALID_CITATION_RE = re.compile(r'\[Source:\s*https?://[^\]]+\]', re.IGNORECASE)
    # Invalid markers to strip: (Source: ...), [Source: www...] (missing protocol)
    STRIP_INVALID_RE = re.compile(r'\(Source:\s*[^\)]+\)|\[Source:(?!\s*https?://)[^\]]*\]', re.IGNORECASE)
    
    # 2. Split into sentences (claims)
    raw_parts = re.split(r'([.!?](?:\s+|$))', text)
    
    # 3. Merge citations back to their parent sentences
    merged_claims = []
    i = 0
    while i < len(raw_parts):
        content = raw_parts[i]
        delimiter = raw_parts[i+1] if i+1 < len(raw_parts) else ""
        
        next_text_idx = i + 2
        while next_text_idx < len(raw_parts) and raw_parts[next_text_idx].strip().startswith("[Source:"):
            content += delimiter + raw_parts[next_text_idx]
            delimiter = raw_parts[next_text_idx+1] if next_text_idx+1 < len(raw_parts) else ""
            next_text_idx += 2
        
        merged_claims.append((content, delimiter))
        i = next_text_idx

    final_parts = []
    for content, delimiter in merged_claims:
        if not content.strip():
            final_parts.append(content + delimiter)
            continue
            
        # Clean out invalid naming-only citations or bad formats
        cleaned_content = STRIP_INVALID_RE.sub("", content).strip()
        
        # Check for grouped/multiple URLs within a single citation marker (forbidden)
        # e.g., [Source: https://a.com, https://b.com]
        has_grouped = False
        source_tags = re.findall(r'\[Source:\s*([^\]]+)\]', cleaned_content, re.IGNORECASE)
        for tag in source_tags:
            urls = re.findall(r'https?://', tag, re.IGNORECASE)
            if len(urls) > 1:
                has_grouped = True
                
        # If there's multiple separate [Source: ...] tags in one claim, we also consider it grouped
        if len(VALID_CITATION_RE.findall(cleaned_content)) > 1:
            has_grouped = True

        # Create UX Clickable Elements
        if has_grouped:
            grouped_count += 1
            if "[⚠️ Missing verifiable source URL]" not in cleaned_content:
                cleaned_content += ' [[⚠️ Missing verifiable source URL]](# "This claim could not be verified with a direct source")'
        elif not VALID_CITATION_RE.search(cleaned_content):
            missing_count += 1
            # If no valid URL found, or if grouped (which is forbidden), we flag it
            if "[⚠️ Missing verifiable source URL]" not in cleaned_content:
                cleaned_content += ' [[⚠️ Missing verifiable source URL]](# "This claim could not be verified with a direct source")'
        else:
            # Upgrade the valid citations visually as well:
            # Re-format [Source: <URL>] to [[Source: <URL>]](<URL>)
            def convert_to_markdown_link(match):
                url = match.group(1).strip()
                return f'[[Source: {url}]]({url})'
            cleaned_content = re.sub(r'\[Source:\s*(https?://[^\]]+)\]', convert_to_markdown_link, cleaned_content, flags=re.IGNORECASE)
                
        final_parts.append(cleaned_content + delimiter)
            
    return "".join(final_parts), missing_count, grouped_count


class ResponseSynthesizer:
    async def synthesize(
        self,
        goal: str,
        step_results: List[Dict[str, Any]],  # [{"content": "...", "is_error": bool}, ...]
        context_block: str,
        llm: Any
    ) -> tuple[str, int, int]:
        # Filter successful vs failed
        successful = [r for r in step_results if not r.get("is_error", False)]
        failed_count = len(step_results) - len(successful)

        if not successful:
            logger.warning("[Synthesizer] All steps failed. Returning fallback.")
            return "I was unable to complete this task. All steps encountered errors.", 0, 0

        partial_note = f"\n⚠️ Note: {failed_count} step(s) failed and were excluded." if failed_count > 0 else ""

        step_lines = "\n".join(f"- {r['content']}" for r in successful)
        
        prompt = f"""Goal: {goal}
Context: {context_block}
Completed steps:
{step_lines}
{partial_note}

[CRITICAL INSTRUCTIONS - CITATION MANDATE]
1. Produce a clean, complete final answer based ONLY on the completed steps.
2. CITATION LOCK: Every factual claim MUST carry its original [Source: URL] inline. 
3. NO GROUPING: Do NOT group citations at the end or merge citations across multiple claims.
4. FORBIDDEN: Do not use named citations like "(Source: Google)". Use ONLY the provided URLs.
5. MISSING DATA: If a claim is made but no URL is available in the steps, you MUST append "[⚠️ Missing verifiable source URL]".
6. Maintain the pairing: "Claim text [Source: https://url.com]".
7. Maintain one claim per sentence for clarity."""
        
        try:
            raw_answer = await llm.complete(prompt)
            # Apply programmatic enforcement layer
            return enforce_citations(raw_answer.strip())
        except Exception as e:
            logger.error(f"[Synthesizer] LLM synthesis failed: {e}")
            return "I completed some steps but encountered an error generating the final summary.", 0, 0

# Singleton
synthesizer = ResponseSynthesizer()
