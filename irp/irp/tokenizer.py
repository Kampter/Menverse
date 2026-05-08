"""Token counting for client-side verification."""

import re
from typing import Optional, List


class TokenCounter:
    """Count tokens client-side for verification against server reports."""

    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize token counter.

        Args:
            encoding_name: tiktoken encoding name (default "cl100k_base" for GPT-4).
        """
        self.encoding_name = encoding_name
        self._encoding = None
        self._tiktoken_available = False
        self._init_tiktoken()

    def _init_tiktoken(self) -> None:
        """Try to load tiktoken encoding."""
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding(self.encoding_name)
            self._tiktoken_available = True
        except (ImportError, Exception):
            self._tiktoken_available = False

    def count(self, text: str) -> int:
        """Count tokens in text. Falls back to approximate counting."""
        if self._tiktoken_available and self._encoding:
            try:
                return len(self._encoding.encode(text))
            except Exception:
                pass
        return self._approximate_count(text)

    def count_messages(self, messages: List[dict]) -> int:
        """Count tokens in a list of chat messages (OpenAI format)."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.count(content)
            elif isinstance(content, list):
                # Multi-modal content
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text", "")
                        if text:
                            total += self.count(text)
            # Add overhead for role and formatting
            total += 3  # Approximate overhead per message
        return total

    def _approximate_count(self, text: str) -> int:
        """
        Approximate token count without tiktoken.

        Rule of thumb:
        - English: ~1 token per 0.75 words
        - Chinese/Japanese: ~1 token per character
        - Code: ~1 token per character
        """
        if not text:
            return 0

        # Count CJK characters (typically 1-2 tokens each)
        cjk_chars = len(re.findall(r"[一-鿿぀-ゟ゠-ヿ]", text))

        # Count words (non-CJK)
        non_cjk = re.sub(r"[一-鿿぀-ゟ゠-ヿ]", " ", text)
        words = len(non_cjk.split())

        # Code/special characters
        code_chars = len(re.findall(r"[^\w\s]", text))

        # Heuristic formula
        estimated = int(cjk_chars * 1.5 + words * 1.3 + code_chars * 0.5)
        return max(1, estimated)

    @property
    def is_exact(self) -> bool:
        """Whether this counter uses exact tiktoken counting."""
        return self._tiktoken_available


def create_counter_for_model(model: str) -> TokenCounter:
    """Create appropriate token counter for a given model."""
    model_lower = model.lower()

    if "gpt-4o" in model_lower or "o1" in model_lower or "o3" in model_lower:
        return TokenCounter("o200k_base")
    elif "gpt-4" in model_lower or "gpt-3.5" in model_lower:
        return TokenCounter("cl100k_base")
    elif "llama-3" in model_lower or "llama3" in model_lower:
        return TokenCounter("cl100k_base")  # Llama 3 uses similar tokenizer
    elif "claude" in model_lower:
        # Claude uses a custom tokenizer, fallback to cl100k_base as approximation
        return TokenCounter("cl100k_base")
    else:
        return TokenCounter("cl100k_base")  # Default
