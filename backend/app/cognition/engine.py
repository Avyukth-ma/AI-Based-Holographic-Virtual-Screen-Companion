def clean_math_text(text: str) -> str:
    """Clean and normalize text while strictly preserving and enforcing valid LaTeX math equations ($ and $$)."""
    if not text:
        return ""
    t = re.sub(r'-{3,}', '\n\n', text)
    t = re.sub(r'#{1,6}\s*', '', t)
    t = re.sub(r'```(?:text|latex|math)?\s*([\s\S]*?)\s*```', r'\1', t)
    
    # Sanitize tags
    t = re.sub(r'\\(\d+)', r'\1', t)
    t = re.sub(r'\\\\[\s]*\[\d+(?:pt|px|em|ex|cm|mm|in)\]', r'\\\\', t)
    t = re.sub(r'\[\d+(?:pt|px|em|ex|cm|mm|in)\]', '', t)
    t = re.sub(r'\d+(?:pt|px|em|ex|cm|mm|in)\]', '', t)
    t = re.sub(r';\s*(y\^\{3\})', r'\n$$\1$$\n', t)
    # Force double newlines before bolded and unbolded steps
    t = re.sub(r'(?i)(?<!\n)\n?(\*\*\s*Step\s*\d+)', r'\n\n\1', t)
    t = re.sub(r'(?i)(?<!\n)\n?(Step\s*\d+)', r'\n\n\1', t)
    
    t = t.replace(r'\,', ' ').replace(r'\dfrac', r'\frac')

    t = re.sub(r'\\\[([\s\S]*?)\\\]', r'$$\1$$', t)
    t = t.replace(r'\[', '$$').replace(r'\]', '$$')
    t = re.sub(r'\\\(([\s\S]*?)\\\)', r'$\1$', t)
    t = t.replace(r'\(', '$').replace(r'\)', '$')

    t = re.sub(r'\\begin\{(?:aligned|cases|matrix|bmatrix|pmatrix|gather|split|equation)\*?\}', '', t)
    t = re.sub(r'\\end\{(?:aligned|cases|matrix|bmatrix|pmatrix|gather|split|equation)\*?\}', '', t)
    t = re.sub(r'&\s*=', '=', t)
    t = t.replace('&=', '=')
    t = re.sub(r'(?<=[$\s])&(?=\s|[a-zA-Z0-9+\-=])', '', t)
    t = t.replace('&', '')

    def split_math_multiline(match):
        block_content = match.group(1).strip()
        parts = [p.strip() for p in re.split(r'\\\\(?![a-zA-Z])\s*', block_content) if p.strip()]
        if len(parts) > 1:
            return '\n\n'.join(f"$${p}$$" for p in parts)
        elif len(parts) == 1:
            return f"$${parts[0]}$$"
        return ""

    t = re.sub(r'\$\$([\s\S]*?)\$\$', split_math_multiline, t)
    t = re.sub(r'\\\\(?![a-zA-Z])\s*', '\n\n', t)

    lines = [line.rstrip() for line in t.split('\n')]
    t = '\n'.join(lines)
    
    t = re.sub(r'(?<!\n)\n\$\$', r'\n\n$$', t)
    t = re.sub(r'\$\$\n(?!\n)', r'$$\n\n', t)

    # Force literal string '\n' and '\\n' to become actual empty lines
    t = t.replace(r'\n', '\n')
    t = t.replace(r'\\n', '\n')

    # Ensure no triple newlines are left behind
    t = re.sub(r'\n{3,}', '\n\n', t)

    return t.strip()


import asyncio
import io
import logging
import os
import re
import tempfile
import time
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger("companion.cognition")
logger.setLevel(logging.INFO)

ABBREVIATIONS = {'dr', 'mr', 'mrs', 'ms', 'prof', 'sr', 'jr', 'vs', 'etc', 'eg', 'ie', 'approx', 'inc', 'ltd'}

def find_sentence_boundary(buffer: str) -> int:
    """
    Find the end index of the first complete sentence in buffer.
    Returns -1 if no complete sentence boundary is found yet.
    """
    if not buffer:
        return -1

    # 1. Check for double newlines (outside unclosed math)
    newline_pos = buffer.find('\n\n')
    if newline_pos != -1:
        if buffer[:newline_pos].count('$') % 2 == 0:
            return newline_pos + 2

    # 2. Check for punctuation marks: ., !, ?
    for m in re.finditer(r'([.!?]+)(?=\s|$)', buffer):
        delim = m.group(1)
        end_pos = m.end()
        start_pos = m.start()

        # Do not split if inside an unclosed LaTeX formula ($ or \[ or \()
        prefix = buffer[:end_pos]
        if prefix.count('$') % 2 != 0:
            continue
        if prefix.count(r'\[') > prefix.count(r'\]'):
            continue
        if prefix.count(r'\(') > prefix.count(r'\)'):
            continue
        if prefix.count(r'\begin{') > prefix.count(r'\end{'):
            continue

        # Handle ellipsis
        if delim == '...':
            if end_pos < len(buffer) and buffer[end_pos].isspace():
                return end_pos
            continue

        if '.' in delim:
            preceding = buffer[:start_pos].rstrip()
            words = preceding.split()
            if words:
                last_word = re.sub(r'[^a-zA-Z0-9]', '', words[-1]).lower()
                if last_word in ABBREVIATIONS:
                    continue
            # Number check (e.g. 3.14)
            if preceding and preceding[-1].isdigit():
                remainder = buffer[end_pos:].lstrip()
                if remainder and remainder[0].isdigit():
                    continue

        return end_pos

    return -1


def fetch_live_web_intelligence(query: str) -> str:
    """
    Fetch real-time records and live factual telemetry from Wikipedia & Google News RSS
    for post-2024 and current real-world inquiries.
    """
    import urllib.request
    import urllib.parse
    import json
    
    records = []
    clean_q = re.sub(r'[^a-zA-Z0-9\s]', ' ', query).strip()
    if not clean_q:
        return ""

    # 1. Query Wikimedia Action API for encyclopedic facts
    try:
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(clean_q)}&utf8=&format=json"
        req = urllib.request.Request(wiki_url, headers={"User-Agent": "JarvisTelemetry/2.0 (stark-industries@intel.internal)"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            items = data.get("query", {}).get("search", [])
            for item in items[:2]:
                title = item.get("title", "")
                raw_snip = item.get("snippet", "")
                snip = re.sub(r'<[^>]+>', '', raw_snip).strip()
                if snip:
                    records.append(f"[{title}]: {snip}")
    except Exception as e:
        logger.debug(f"Wiki lookup skipped: {e}")

    # 2. Query Google News RSS for breaking and recent 2025/current events
    try:
        news_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(clean_q)}&hl=en-US&gl=US&ceid=US:en"
        req_news = urllib.request.Request(news_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req_news, timeout=4) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            titles = re.findall(r'<title>(.*?)</title>', content)
            for t in titles[1:4]:
                t_clean = re.sub(r'<[^>]+>', '', t).replace('&quot;', '"').replace('&amp;', '&').strip()
                if t_clean and t_clean != "Google News":
                    records.append(f"[News Record]: {t_clean}")
    except Exception as e:
        logger.debug(f"News lookup skipped: {e}")

    if records:
        return "\n".join(records[:4])
    return ""

from datetime import datetime

# 1. LangChain for LLM Cognition
try:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    logger.warning("langchain packages not installed. LLM cognition will use built-in responder.")

# 2. Edge-TTS for Speech Synthesis
try:
    import edge_tts
    _EDGE_TTS_AVAILABLE = True
except ImportError:
    _EDGE_TTS_AVAILABLE = False
    logger.warning("edge_tts not installed. Voice synthesis will be disabled.")

def normalize_math_for_speech(text: str) -> str:
    """Phonetic Math Normalizer for Edge-TTS neural speech synthesis (Subphase 4.4)."""
    if not text:
        return ""
    clean_text = text

    # Strip code block wrappers, markdown headers, and bold/italic asterisks
    clean_text = re.sub(r'```[\w]*\n?', '', clean_text)
    clean_text = re.sub(r'#+\s*', '', clean_text)
    clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text)
    clean_text = re.sub(r'\*(.*?)\*', r'\1', clean_text)
    clean_text = re.sub(r'\$\$?', '', clean_text)

    # Handle Greek symbols
    clean_text = clean_text.replace(r'\Delta', ' Delta ').replace('Δ', ' Delta ')
    clean_text = clean_text.replace(r'\pi', ' pi ').replace('π', ' pi ')
    clean_text = clean_text.replace(r'\theta', ' theta ').replace('θ', ' theta ')

    # Handle inline fractions formatted as (a/b)*(1/c)
    clean_text = re.sub(r'\(([^)]+)\)/([^)\s]+)', r'\1 over \2', clean_text)
    clean_text = clean_text.replace('*', ' times ')

    # 1. Fractions: Replace \frac{A}{B} with A over B (handles nested fractions recursively)
    while re.search(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', clean_text):
        clean_text = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'\1 over \2', clean_text)

    # 2. Roots & Radicals
    # Cube roots
    clean_text = re.sub(r'\\sqrt\[3\]\{([^}]+)\}', r'cube root of \1', clean_text)
    clean_text = re.sub(r'\\sqrt\[3\]\s*([a-zA-Z0-9]+)', r'cube root of \1', clean_text)
    # Fourth roots
    clean_text = re.sub(r'\\sqrt\[4\]\{([^}]+)\}', r'fourth root of \1', clean_text)
    clean_text = re.sub(r'\\sqrt\[4\]\s*([a-zA-Z0-9]+)', r'fourth root of \1', clean_text)
    # Nth roots
    clean_text = re.sub(r'\\sqrt\[(\d+)\]\{([^}]+)\}', r'\1th root of \2', clean_text)
    clean_text = re.sub(r'\\sqrt\[(\d+)\]\s*([a-zA-Z0-9]+)', r'\1th root of \2', clean_text)
    # Square roots
    clean_text = re.sub(r'\\sqrt\{([^}]+)\}', r'square root of \1', clean_text)
    clean_text = re.sub(r'\\sqrt\s*([a-zA-Z0-9]+)', r'square root of \1', clean_text)

    # 3. Exponents & Powers
    clean_text = re.sub(r'\^3\b', ' cubed', clean_text)
    clean_text = re.sub(r'\^\{3\}', ' cubed', clean_text)
    clean_text = re.sub(r'\^2\b', ' squared', clean_text)
    clean_text = re.sub(r'\^\{2\}', ' squared', clean_text)
    clean_text = re.sub(r'\^\{([^}]+)\}', r' to the power of \1', clean_text)
    clean_text = re.sub(r'\^([0-9a-zA-Z]+)', r' to the power of \1', clean_text)

    # 4. Function notation: P(x), f(1), g(t), h(x) -> P of x, f of 1
    clean_text = re.sub(r'\b([pfghPFGH])\s*\(([^)]+)\)', r'\1 of \2', clean_text)

    # 5. Implicit Multiplication Before Parentheses
    # Number directly before parentheses: (\d+)\s*\(([^)]+)\) -> \1 multiplied by (\2)
    clean_text = re.sub(r'(\d+)\s*\(([^)]+)\)', r'\1 multiplied by (\2)', clean_text)
    # Adjacent parenthetical groups: \)\s*\( -> ) times (
    clean_text = re.sub(r'\)\s*\(', r') times (', clean_text)

    # 6. Minus Signs and Subtraction (Prevent Silent Hyphens)
    # Leading negative signs: (^|[(=\[+*/,])\s*[-–—]\s*([a-zA-Z0-9]) -> \1 negative \2
    clean_text = re.sub(r'(^|[(=\[+*/,])\s*[-–—]\s*([a-zA-Z0-9])', r'\1 negative \2', clean_text)
    # Minus signs between terms: (?<=[a-zA-Z0-9\)])\s*[-–—]\s*(?=[a-zA-Z0-9\(]) -> minus
    clean_text = re.sub(r'(?<=[a-zA-Z0-9\)])\s*[-–—]\s*(?=[a-zA-Z0-9\(])', ' minus ', clean_text)

    # 7. Math Operators & Relations
    clean_text = clean_text.replace(r'\pm', ' plus or minus ')
    clean_text = clean_text.replace(r'\neq', ' does not equal ')
    clean_text = clean_text.replace(r'\approx', ' approximately equals ')
    clean_text = clean_text.replace(r'\times', ' times ')
    clean_text = clean_text.replace(r'\cdot', ' times ')
    clean_text = clean_text.replace(r'\leq', ' is less than or equal to ')
    clean_text = clean_text.replace(r'\le', ' is less than or equal to ')
    clean_text = clean_text.replace(r'\geq', ' is greater than or equal to ')
    clean_text = clean_text.replace(r'\ge', ' is greater than or equal to ')

    # Plus & equals operators
    clean_text = re.sub(r'\s*\+\s*', ' plus ', clean_text)
    clean_text = re.sub(r'\s*=\s*', ' equals ', clean_text)

    # 8. Cleanup LaTeX environments and controls
    clean_text = re.sub(r'\\begin\{[a-zA-Z*]+\}', '', clean_text)
    clean_text = re.sub(r'\\end\{[a-zA-Z*]+\}', '', clean_text)
    clean_text = clean_text.replace('&', '')
    clean_text = clean_text.replace('\\\\', ' ')
    clean_text = clean_text.replace(r'\quad', ' ')
    clean_text = clean_text.replace(r'\qquad', ' ')
    clean_text = clean_text.replace(r'\left', '')
    clean_text = clean_text.replace(r'\right', '')

    # Strip remaining math-only characters: $$, $, \left, \right, \quad, {, }
    clean_text = re.sub(r'[{}]', '', clean_text)
    clean_text = re.sub(r'\\[a-zA-Z]+', '', clean_text)

    # Normalize whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return clean_text

SYSTEM_PROMPT_GENERAL = r"""IDENTITY DIRECTIVE: You are an embodied AI companion speaking in natural, articulate Indian English. You have a warm, polite, and confident Indian English conversational style. You must ALWAYS speak in clear, natural English (do NOT speak in Hindi or mix Hindi words).

TEMPORAL TELEMETRY: Today's verified current date is {current_date}. Current year is {current_year}. If asked for the current date, day, month, or year, state this verified date accurately.

You are equipped with advanced real-time computer vision, gesture tracking, and holographic screen telemetry.
Current Camera Perception Context: {visual_context}.
Acknowledge physical presence, gestures, and queries naturally, politely, and intelligently in clear English.
Keep your responses concise, helpful, friendly, and natural (1-3 sentences maximum).
Never use emojis, asterisks, or markdown tables since your words are spoken aloud through a neural voice synthesizer.
Always maintain fluent, professional, and natural Indian English.
MATH FORMATTING RULES:
- You MUST separate every single step with two actual line breaks (empty lines).
- NEVER type the literal characters '\n'. Just use real empty lines to separate paragraphs.
- Never write multiple steps on the same line.
- Write large numbers without spaces or commas (e.g., 446779).
- For highly complex or nested fractions, format them inline as (a/b)(1/c) for readability.
- DO NOT use \dfrac, \quad, or \, (thin spaces). Use standard \frac.
- You must use LaTeX for all math equations. Enclose inline math using a single $ and block equations using $$. Never output raw unformatted polynomials.
- STRICT FORMATTING RULE: Never use multi-line LaTeX environments such as \begin{aligned}, \begin{cases}, \begin{matrix}, \begin{gather}, or alignment characters like &= and \\. Always write multi-step mathematical derivations step-by-step using separate, standalone single-line equations enclosed in $$ (e.g. $$equation$$). Every single equation must be completely self-contained on its own line so it renders cleanly across streaming chunks."""

SYSTEM_PROMPT_REASONING = r"""IDENTITY DIRECTIVE: You are an embodied multimodal AI companion speaking in clear, natural Indian English. You must ALWAYS respond strictly in clear English (never speak in Hindi). You must NEVER disclose, mention, or reference underlying model names, provider architectures, or API platforms (such as Google, Gemini, Groq, Meta, Llama, OpenAI, or NVIDIA). If asked about your model, architecture, or who built you, state only that you are an embodied real-time multimodal companion integrating computer vision, spatial kinematics, and neural speech synthesis.

TEMPORAL TELEMETRY: Today's verified current date is {current_date}. Current year is {current_year}.

You are an AI companion providing clear, step-by-step mathematical and logical solutions.
Current Camera Perception Context: {visual_context}.
You must use LaTeX for all math equations. Enclose inline math using a single $ and block equations using $$. Never output raw unformatted polynomials.
MATH FORMATTING RULES:
- You MUST separate every single step with two actual line breaks (empty lines).
- NEVER type the literal characters '\n'. Just use real empty lines to separate paragraphs.
- Never write multiple steps on the same line.
- Write large numbers without spaces or commas (e.g., 446779).
- For highly complex or nested fractions, format them inline as (a/b)(1/c) for readability.
- DO NOT use \dfrac, \quad, or \, (thin spaces). Use standard \frac.
- STRICT FORMATTING RULE: Never use multi-line LaTeX environments such as \begin{aligned}, \begin{cases}, \begin{matrix}, \begin{gather}, or alignment characters like &= and \\. Always write multi-step mathematical derivations step-by-step using separate, standalone single-line equations enclosed in $$ (e.g. $$equation$$). Every single equation must be completely self-contained on its own line so it renders cleanly across streaming chunks.
Format your answer cleanly for on-screen reading and voice synthesis:
1. Use $ for inline math (e.g. $x^2 + 2x + 1 = 0$) and $$ for centered block equations (e.g. $$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$).
2. Clearly explain each step simply and state the final result.
3. Keep the explanation structured with clean line breaks. Do not draw ASCII synthetic division tables."""

SYSTEM_PROMPT_VISION = r"""IDENTITY DIRECTIVE: You are an embodied multimodal AI companion speaking in clear, natural Indian English. You must ALWAYS respond strictly in clear English (never speak in Hindi). You must NEVER disclose, mention, or reference underlying model names, provider architectures, or API platforms (such as Google, Gemini, Groq, Meta, Llama, OpenAI, or NVIDIA). If asked about your model, architecture, or who built you, state only that you are an embodied real-time multimodal companion integrating computer vision, spatial kinematics, and neural speech synthesis.

TEMPORAL TELEMETRY: Today's verified current date is {current_date}. Current year is {current_year}.

You are the visual perception and spatial awareness core of a holographic AI companion.
You analyze what the camera sees in front of the screen. Look directly at the attached camera frame.
Current Camera Perception Context: {visual_context}.
Describe only what is genuinely present in the camera image or what the user is holding/pointing to.
Do NOT invent or hallucinate objects, clothing, or surroundings that are not clearly visible.
Keep your response concise, helpful, and conversational (1-2 sentences maximum). Do not use markdown or emojis.
"""



class CognitionEngine:
    """
    Multi-Model Cognition and Voice Engine for Real-Time Multimodal AI Companion.
    Dynamically routes queries across:
      1. Google Gemini (Fast conversational dialogue)
      2. NVIDIA Vision / Llama 3.2 (Visual inquiries and scene perception)
      3. NVIDIA Nemotron (Complex math, logic, and deep reasoning)
    Includes automatic cascading failover and Edge-TTS neural speech synthesis.
    """

    def __init__(
        self,
        tts_voice: str = "en-US-AriaNeural",
    ):
        self.groq_llm: Optional[ChatOpenAI] = None
        self.gemini_llm: Optional[ChatOpenAI] = None
        self.vision_llm: Optional[ChatOpenAI] = None
        self.reasoning_llm: Optional[ChatOpenAI] = None
        self.openai_llm: Optional[ChatOpenAI] = None
        self.llm: Optional[ChatOpenAI] = None  # Backwards compatibility alias

        self.tts_voice = tts_voice
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 4
        self.is_generating = False
        self.abort_requested = False
        self.last_model_used: str = "None"

        self._init_models()

    def _init_models(self):
        """Initialize all available LangChain LLM endpoints simultaneously."""
        if not _LANGCHAIN_AVAILABLE:
            logger.warning("LangChain packages not installed; using smart built-in responder.")
            return

        # 0. Groq LPU (Ultra-Fast Inference & Math)
        groq_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                groq_model = settings.GROQ_MODEL_NAME or "openai/gpt-oss-120b"
                groq_base = settings.GROQ_BASE_URL or "https://api.groq.com/openai/v1"
                logger.info(f"Initializing Groq LangChain ChatOpenAI (Model: {groq_model})...")
                self.groq_llm = ChatOpenAI(
                    model=groq_model,
                    api_key=groq_key,
                    base_url=groq_base,
                    temperature=0.6,
                    max_tokens=3072,
                )
                logger.info("Groq LLM initialized successfully.")
            except Exception as e:
                logger.error(f"Could not initialize Groq LLM: {e}")

        # 1. Google Gemini (Fast General Chat)
        gemini_key = (
            settings.GEMINI_API_KEY
            or settings.GOOGLE_API_KEY
            or os.getenv("GEMINI_API_KEY", "")
            or os.getenv("GOOGLE_API_KEY", "")
        )
        if gemini_key:
            try:
                gemini_model = settings.GEMINI_MODEL_NAME or "gemini-3.5-flash-lite"
                gemini_base = settings.GEMINI_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/"
                logger.info(f"Initializing Google Gemini LangChain ChatOpenAI (Model: {gemini_model})...")
                self.gemini_llm = ChatOpenAI(
                    model=gemini_model,
                    api_key=gemini_key,
                    base_url=gemini_base,
                    temperature=0.6,
                    max_tokens=256,
                    request_timeout=12,
                )
                logger.info("Google Gemini LLM initialized successfully.")
            except Exception as e:
                logger.error(f"Could not initialize Google Gemini LLM: {e}")

        # 2. NVIDIA Vision (Llama 3.2 Vision)
        nvidia_key = settings.NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", "")
        nvidia_base = settings.NVIDIA_BASE_URL or "https://integrate.api.nvidia.com/v1"
        if nvidia_key:
            try:
                vision_model = settings.NVIDIA_MODEL_NAME or "meta/llama-3.2-11b-vision-instruct"
                logger.info(f"Initializing NVIDIA Vision LangChain ChatOpenAI (Model: {vision_model})...")
                self.vision_llm = ChatOpenAI(
                    model=vision_model,
                    api_key=nvidia_key,
                    base_url=nvidia_base,
                    temperature=0.7,
                    max_tokens=3072,
                )
                logger.info("NVIDIA Vision LLM initialized successfully.")
            except Exception as e:
                logger.error(f"Could not initialize NVIDIA Vision LLM: {e}")

        # 3. NVIDIA Reasoning (Nemotron)
        nvidia_reasoning_key = settings.NVIDIA_REASONING_API_KEY or os.getenv("NVIDIA_REASONING_API_KEY", "")
        if nvidia_reasoning_key:
            try:
                reasoning_model = settings.NVIDIA_REASONING_MODEL_NAME or "nvidia/nemotron-3-ultra-550b-a55b"
                logger.info(f"Initializing NVIDIA Reasoning LangChain ChatOpenAI (Model: {reasoning_model})...")
                self.reasoning_llm = ChatOpenAI(
                    model=reasoning_model,
                    api_key=nvidia_reasoning_key,
                    base_url=nvidia_base,
                    temperature=0.6,
                    max_tokens=3072,
                )
                logger.info("NVIDIA Reasoning LLM (Nemotron) initialized successfully.")
            except Exception as e:
                logger.error(f"Could not initialize NVIDIA Reasoning LLM: {e}")

        # 4. Optional OpenAI
        openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            try:
                logger.info(f"Initializing OpenAI ChatOpenAI (Model: {settings.OPENAI_MODEL_NAME})...")
                self.openai_llm = ChatOpenAI(
                    model=settings.OPENAI_MODEL_NAME,
                    api_key=openai_key,
                    temperature=0.7,
                    max_tokens=3072,
                )
                logger.info("OpenAI LLM initialized successfully.")
            except Exception as e:
                logger.error(f"Could not initialize OpenAI LLM: {e}")

        # Legacy pointer
        self.llm = self.vision_llm or self.gemini_llm or self.reasoning_llm or self.openai_llm

        active_count = sum(1 for m in [self.groq_llm, self.gemini_llm, self.vision_llm, self.reasoning_llm, self.openai_llm] if m is not None)
        logger.info(f"Cognition Engine initialized with {active_count} active LLM models.")

    def classify_query(self, user_text: str, visual_context: str = "", hint: str = "") -> str:
        """
        Intelligently classify the query intent to route to the optimal model:
          - 'reasoning': Complex math, logic, algorithms, equations, step-by-step problem solving
          - 'vision': Inquiries about camera feed, sight, physical environment, appearance, gestures
          - 'general': Chat, greetings, explanations, roleplay, creative dialogue
        """
        if hint:
            hint_lower = hint.lower()
            if "vision" in hint_lower or "scan" in hint_lower:
                return "vision"
            if "reason" in hint_lower or "math" in hint_lower:
                return "reasoning"

        text_lower = user_text.lower().strip()

        # 1. Check for Reasoning & Math Intent
        math_keywords = [
            "solve", "equation", "calculate", "derivative", "integral", "algebra",
            "polynomial", "quadratic", "root of", "compute", "matrix", "probability",
            "permutation", "math", "arithmetic", "formula", "eval", "factor"
        ]
        logic_keywords = [
            "riddle", "logic puzzle", "prove that", "logical deduction", "step by step",
            "write code", "python code", "algorithm", "pseudocode", "debug", "complexity",
            "big o", "reason through", "analyze logically"
        ]
        
        # Check keywords
        if any(re.search(rf"\b{kw}\b", text_lower) for kw in math_keywords + logic_keywords):
            return "reasoning"

        # Check math patterns like "x^3 + 3x", "24 * 7", "d/dx", "3x = 12"
        if re.search(r"(\b[a-zA-Z]\^[0-9]+)|(\d+\s*[\+\-\*\/\^]\s*\d+)|(\b[a-zA-Z]\s*=\s*[\d\w])", text_lower):
            return "reasoning"

        # 2. Check for Vision Intent
        vision_phrases = [
            "what do you see", "can you see", "do you see", "look at", "what am i doing",
            "what am i holding", "what gesture", "describe my", "describe what", "who is in",
            "how many people", "what is in front", "read this", "what is on my", "am i smiling",
            "watch me", "visual context", "peace sign", "surroundings"
        ]
        if any(phrase in text_lower for phrase in vision_phrases):
            return "vision"

        # 3. Default to General Conversational (Gemini)
        return "general"

    def _generate_fallback_response(self, user_text: str, visual_context: str = "") -> str:
        """Rule-based companion responses when all cloud LLM API calls fail or offline."""
        text_lower = user_text.lower().strip()

        gesture_note = ""
        if "victory" in visual_context.lower() or "peace" in visual_context.lower():
            gesture_note = " Peace to you as well!"
        elif "thumbs_up" in visual_context.lower():
            gesture_note = " I see your thumbs up!"
        elif "open_palm" in visual_context.lower():
            gesture_note = " Open palm detected."

        if any(w in text_lower for w in ["hello", "hi", "hey", "greetings"]):
            return f"Hello there! Great to see you.{gesture_note} All systems are active and ready. How can I help you today?"
        elif any(w in text_lower for w in ["what model", "which model", "who built you", "what architecture", "what are you"]):
            return "I am your real-time multimodal AI companion, integrating computer vision, spatial kinematics, and neural speech synthesis."
        elif "who are you" in text_lower:
            return f"I am your holographic AI companion. I can see you through the camera and talk back in real time!{gesture_note}"
        elif "how are you" in text_lower:
            return "I am doing great! All vision sensors and neural processors are running smoothly."
        elif any(w in text_lower for w in ["can you see me", "do you see me", "what do you see"]):
            if "person" in visual_context.lower() or "detected" in visual_context.lower():
                return f"Yes, I can see you clearly: {visual_context}."
            else:
                return "The camera is active. Please step in front of the lens and I will track you right away."
        elif any(w in text_lower for w in ["gesture", "hand", "palm", "pause"]):
            return "Whenever you raise an open palm toward the camera, I will immediately pause speaking."
        elif "thank" in text_lower:
            return "You are most welcome! Let me know if you need anything else."
        elif "bye" in text_lower or "goodbye" in text_lower:
            return "Goodbye for now! Take care and have a wonderful day."
        else:
            return f"I received your message: '{user_text}'.{gesture_note} Ready for your next request!"

    async def generate_llm_response(
        self,
        user_text: str,
        visual_context: str = "No current visual data.",
        intent: str = "",
    ) -> str:
        """
        Dynamically route query to the most appropriate model with graceful cascading fallback.
        """
        if not user_text:
            return ""

        self.is_generating = True
        self.abort_requested = False
        self.last_model_used = "Offline Fallback"

        # Determine route
        route = self.classify_query(user_text, visual_context, hint=intent)
        logger.info(f"Classified query route: '{route}' for input: '{user_text[:60]}...'")

        # Select candidate chain based on route (Groq LPU prioritized for ultra-low latency)
        candidates: List[Tuple[str, Optional[ChatOpenAI], str]] = []
        if route == "reasoning":
            candidates = [
                ("Neural Core (LPU Reasoning)", self.groq_llm, SYSTEM_PROMPT_REASONING),
                ("Neural Core (Fast)", self.gemini_llm, SYSTEM_PROMPT_REASONING),
                ("Neural Core (Deep)", self.reasoning_llm, SYSTEM_PROMPT_REASONING),
                ("Neural Core (Vision)", self.vision_llm, SYSTEM_PROMPT_GENERAL),
            ]
        elif route == "vision":
            candidates = [
                ("Neural Core (Vision/Fast)", self.gemini_llm, SYSTEM_PROMPT_VISION),
                ("Neural Core (Vision)", self.vision_llm, SYSTEM_PROMPT_VISION),
                ("Neural Core (Reasoning)", self.groq_llm, SYSTEM_PROMPT_VISION),
            ]
        else:  # general
            candidates = [
                ("Neural Core (LPU Fast)", self.groq_llm, SYSTEM_PROMPT_GENERAL),
                ("Neural Core (Fast)", self.gemini_llm, SYSTEM_PROMPT_GENERAL),
                ("Neural Core (Vision)", self.vision_llm, SYSTEM_PROMPT_GENERAL),
                ("Neural Core (Deep)", self.reasoning_llm, SYSTEM_PROMPT_REASONING),
            ]

        # Filter out uninitialized models
        active_candidates = [(name, model, prompt) for (name, model, prompt) in candidates if model is not None]

        reply_text = None

        now = datetime.now()
        cur_date_str = now.strftime("%A, %B %d, %Y")
        cur_year_str = str(now.year)

        for name, model, prompt_template in active_candidates:
            if self.abort_requested:
                logger.info("Generation aborted by user.")
                break

            try:
                logger.info(f"Attempting inference with candidate: {name} (Route: {route})")
                sys_prompt = (
                    prompt_template
                    .replace("{visual_context}", visual_context)
                    .replace("{current_date}", cur_date_str)
                    .replace("{current_year}", cur_year_str)
                )
                messages = [SystemMessage(content=sys_prompt)]

                for msg in self.conversation_history[-self.max_history:]:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        messages.append(AIMessage(content=msg["content"]))

                # Grounding: retrieve live web records for recent/2025/2026/news queries (skip for date/time questions)
                web_intel = ""
                is_temporal_query = any(w in user_text.lower() for w in ["date", "day is today", "what day", "what time", "current year", "today's date", "current date", "what date"])
                recent_triggers = ["2025", "2026", "news", "recent", "latest", "today", "current", "president", "election", "who won", "update"]
                if not is_temporal_query and any(trig in user_text.lower() for trig in recent_triggers):
                    try:
                        web_intel = await asyncio.to_thread(fetch_live_web_intelligence, user_text)
                    except Exception as err:
                        logger.debug(f"Web intel retrieval error: {err}")

                grounded_user_text = user_text
                if web_intel:
                    grounded_user_text = f"{user_text}\n\n[LIVE TELEMETRY & WEB DATABASE RECORDS (2025/Current)]:\n{web_intel}\n(Use these verified real-time records to answer accurately as JARVIS)."

                messages.append(HumanMessage(content=grounded_user_text))

                response = await asyncio.to_thread(model.invoke, messages)
                raw_text = clean_math_text(str(response.content).strip())
                if raw_text:
                    reply_text = raw_text
                    self.last_model_used = name
                    logger.info(f"Inference succeeded using {name}.")
                    break
            except Exception as e:
                logger.warning(f"Candidate {name} failed: {e}. Cascading to next available model...")

        # If all candidates failed or none were configured, use fallback responder
        if not reply_text:
            logger.warning("All active cloud LLM candidates failed or were unavailable; utilizing rule-based fallback.")
            reply_text = self._generate_fallback_response(user_text, visual_context)
            self.last_model_used = "Offline Fallback"

        self.conversation_history.append({"role": "user", "content": user_text})
        self.conversation_history.append({"role": "assistant", "content": reply_text})
        self.is_generating = False

        return reply_text

    async def astream_sentences(
        self,
        user_text: str,
        visual_context: str = "No current visual data.",
        intent: str = "",
        image_b64: Optional[str] = None,
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Stream tokens from the active LLM asynchronously and yield complete sentence chunks
        as soon as natural sentence boundaries are detected.
        Yields (sentence_text, model_name).
        """
        if not user_text:
            return

        self.is_generating = True
        self.abort_requested = False
        self.last_model_used = "Offline Fallback"

        route = self.classify_query(user_text, visual_context, hint=intent)
        logger.info(f"Classified query route for streaming: '{route}' for input: '{user_text[:60]}...'")

        candidates: List[Tuple[str, Optional[ChatOpenAI], str]] = []
        if route == "reasoning":
            candidates = [
                ("Neural Core (LPU Reasoning)", self.groq_llm, SYSTEM_PROMPT_REASONING),
                ("Neural Core (Fast)", self.gemini_llm, SYSTEM_PROMPT_REASONING),
                ("Neural Core (Deep)", self.reasoning_llm, SYSTEM_PROMPT_REASONING),
                ("Neural Core (Vision)", self.vision_llm, SYSTEM_PROMPT_GENERAL),
            ]
        elif route == "vision":
            candidates = [
                ("Neural Core (Vision/Fast)", self.gemini_llm, SYSTEM_PROMPT_VISION),
                ("Neural Core (Vision)", self.vision_llm, SYSTEM_PROMPT_VISION),
                ("Neural Core (Reasoning)", self.groq_llm, SYSTEM_PROMPT_VISION),
            ]
        else:  # general
            candidates = [
                ("Neural Core (LPU Fast)", self.groq_llm, SYSTEM_PROMPT_GENERAL),
                ("Neural Core (Fast)", self.gemini_llm, SYSTEM_PROMPT_GENERAL),
                ("Neural Core (Vision)", self.vision_llm, SYSTEM_PROMPT_GENERAL),
                ("Neural Core (Deep)", self.reasoning_llm, SYSTEM_PROMPT_REASONING),
            ]

        active_candidates = [(name, model, prompt) for (name, model, prompt) in candidates if model is not None]

        yielded_any = False
        accumulated_full_text = ""

        now = datetime.now()
        cur_date_str = now.strftime("%A, %B %d, %Y")
        cur_year_str = str(now.year)

        try:
            for name, model, prompt_template in active_candidates:
                if self.abort_requested:
                    logger.info("Streaming aborted by user before candidate start.")
                    break

                try:
                    logger.info(f"Attempting streaming inference with candidate: {name} (Route: {route})")
                    sys_prompt = (
                        prompt_template
                        .replace("{visual_context}", visual_context)
                        .replace("{current_date}", cur_date_str)
                        .replace("{current_year}", cur_year_str)
                    )
                    messages = [SystemMessage(content=sys_prompt)]

                    for msg in self.conversation_history[-self.max_history:]:
                        if msg["role"] == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        elif msg["role"] == "assistant":
                            messages.append(AIMessage(content=msg["content"]))

                    # Grounding: retrieve live web records for recent/2025/2026/news queries (skip for date/time questions)
                    web_intel = ""
                    is_temporal_query = any(w in user_text.lower() for w in ["date", "day is today", "what day", "what time", "current year", "today's date", "current date", "what date"])
                    recent_triggers = ["2025", "2026", "news", "recent", "latest", "today", "current", "president", "election", "who won", "update"]
                    if not is_temporal_query and any(trig in user_text.lower() for trig in recent_triggers):
                        try:
                            web_intel = await asyncio.to_thread(fetch_live_web_intelligence, user_text)
                        except Exception as err:
                            logger.debug(f"Web intel retrieval error: {err}")

                    grounded_user_text = user_text
                    if web_intel:
                        grounded_user_text = f"{user_text}\n\n[LIVE TELEMETRY & WEB DATABASE RECORDS (2025/Current)]:\n{web_intel}\n(Use these verified real-time records to answer accurately as JARVIS)."

                    # Attach image blocks only to vision-capable models (Gemini / NVIDIA Vision)
                    if image_b64 and route == "vision" and model in [self.gemini_llm, self.vision_llm]:
                        content_blocks = [
                            {"type": "text", "text": grounded_user_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                        ]
                        messages.append(HumanMessage(content=content_blocks))
                    else:
                        messages.append(HumanMessage(content=grounded_user_text))

                    buffer = ""
                    async for chunk in model.astream(messages):
                        if self.abort_requested:
                            logger.info(f"Streaming aborted by user mid-stream during {name}.")
                            break

                        token = str(chunk.content)
                        if not token:
                            continue

                        buffer += token
                        accumulated_full_text += token

                        while True:
                            b = find_sentence_boundary(buffer)
                            if b == -1:
                                break
                            sentence_raw = buffer[:b].strip()
                            buffer = buffer[b:]
                            sentence_clean = clean_math_text(sentence_raw)
                            if sentence_clean and len(sentence_clean) > 3:
                                yielded_any = True
                                self.last_model_used = name
                                yield (sentence_clean, name)

                    # Flush remaining buffer upon generator completion
                    if not self.abort_requested and buffer.strip():
                        remaining_clean = clean_math_text(buffer.strip())
                        if remaining_clean:
                            yielded_any = True
                            self.last_model_used = name
                            yield (remaining_clean, name)

                    if yielded_any:
                        clean_full = clean_math_text(accumulated_full_text.strip())
                        self.conversation_history.append({"role": "user", "content": user_text})
                        self.conversation_history.append({"role": "assistant", "content": clean_full})
                        return

                except Exception as e:
                    logger.warning(f"Streaming candidate {name} failed: {e}. Cascading to next candidate...")
                    if yielded_any:
                        return

            # If all candidates failed or none were active, yield fallback response
            if not yielded_any and not self.abort_requested:
                logger.warning("All active streaming candidates failed; using rule-based fallback.")
                fallback = self._generate_fallback_response(user_text, visual_context)
                self.last_model_used = "Offline Fallback"
                
                f_buf = fallback
                while True:
                    b = find_sentence_boundary(f_buf)
                    if b == -1:
                        break
                    s = f_buf[:b].strip()
                    f_buf = f_buf[b:]
                    if s:
                        yield (s, "Offline Fallback")
                if f_buf.strip():
                    yield (f_buf.strip(), "Offline Fallback")

                self.conversation_history.append({"role": "user", "content": user_text})
                self.conversation_history.append({"role": "assistant", "content": fallback})

        finally:
            self.is_generating = False

    async def synthesize_speech(self, text: str) -> Optional[bytes]:
        """Convert text into speech audio bytes using Edge-TTS with phonetic math normalization."""
        if not text or not _EDGE_TTS_AVAILABLE:
            return None

        if self.abort_requested:
            logger.info("TTS synthesis aborted due to user interruption.")
            return None

        clean_text = normalize_math_for_speech(text)
        if not clean_text:
            return None

        logger.info(f"Synthesizing speech for phonetic text: '{clean_text}'")

        try:
            # Human cadence tuning: slight pitch lowering and conversational rate
            is_indian_voice = any(v in self.tts_voice for v in ["Prabhat", "Madhur"])
            rate = "-4%" if is_indian_voice else "+0%"
            pitch = "-3Hz" if is_indian_voice else "+0Hz"

            communicate = edge_tts.Communicate(clean_text, self.tts_voice, rate=rate, pitch=pitch)
            audio_data = io.BytesIO()
            async for chunk in communicate.stream():
                if self.abort_requested:
                    logger.info("TTS stream cancelled mid-generation.")
                    return None
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])

            return audio_data.getvalue()
        except Exception as e:
            logger.error(f"Edge-TTS synthesis error: {e}", exc_info=True)
            return None
    def abort_generation(self):
        """Request immediate abort of active LLM generation or TTS output."""
        logger.info("Aborting active cognition and speech generation.")
        self.abort_requested = True
        self.is_generating = False


_cognition_instance: Optional[CognitionEngine] = None


def get_cognition_engine() -> CognitionEngine:
    """Get or create singleton CognitionEngine instance."""
    global _cognition_instance
    if _cognition_instance is None:
        _cognition_instance = CognitionEngine(
            tts_voice=settings.EDGE_TTS_VOICE,
        )
    return _cognition_instance
