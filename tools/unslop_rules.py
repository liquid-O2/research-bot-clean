"""Mechanically checkable rules from the unslop skill.

Rule numbers match the numbered list in `.agents/skills/unslop/SKILL.md`, so a
finding can be traced back to the exact upstream rule it came from. Rules that
need human judgement (adding soul, varying rhythm, acknowledging complexity)
are not encoded here; `unslop_lint` reports them as reviewer items instead.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Rule:
    """One mechanically checkable unslop rule."""

    number: int
    name: str
    pattern: re.Pattern[str]
    message: str


AI_VOCABULARY = (
    "additionally", "crucial", "delve", "enduring", "enhance", "fostering",
    "garner", "interplay", "intricate", "landscape", "pivotal", "showcase", "tapestry",
    "testament", "underscore", "vibrant",
)
FANCY_IS = ("serves as", "stands as", "boasts", "features")
CHATBOT_PHRASES = (
    "i hope this helps", "let me know if", "of course", "certainly",
    "found the smoking gun", "great question", "happy to help",
)
SYCOPHANTIC = (
    "you're absolutely right", "you are absolutely right", "great point",
    "excellent question", "that's a great",
)
FILLER = (
    "in order to", "due to the fact that", "it is important to note that",
    "it should be noted that", "needless to say", "at the end of the day",
)
METAPHOR_NOUNS = (
    "substrate", "wedge", "locus", "vantage", "nexus", "bedrock",
    "scaffolding", "modality", "paradigm", "gold-plating", "gold plating",
    "endgame", "north star", "flywheel",
)
JUDGEMENT_ITEMS = (
    "Have opinions, react to the facts instead of listing them neutrally.",
    "Vary sentence rhythm; uniform length reads as machine-made.",
    "Acknowledge complexity where it is real.",
    "Be specific; name the mechanism, the number, or the file.",
)


def word_alternation(words: tuple[str, ...]) -> str:
    """Build a word-boundary alternation that tolerates internal spaces."""
    escaped = sorted((re.escape(word) for word in words), key=len, reverse=True)
    return r"(?<![\w-])(?:" + "|".join(escaped) + r")(?![\w-])"


def phrase_rule(number: int, name: str, words: tuple[str, ...], message: str) -> Rule:
    """Build a case-insensitive rule from a word or phrase list."""
    pattern = re.compile(word_alternation(words), re.IGNORECASE)
    return Rule(number=number, name=name, pattern=pattern, message=message)


PATTERN_RULES: tuple[Rule, ...] = (
    phrase_rule(7, "ai-vocabulary", AI_VOCABULARY,
                "AI vocabulary. Replace with the plain word."),
    phrase_rule(8, "fancy-is", FANCY_IS,
                "Fancy way to say is or has. Say is or has."),
    Rule(9, "not-just-but",
         re.compile(r"(?<![\w-])not (?:just|only)\b[^.!?\n]{1,80}?,?\s+but\b", re.IGNORECASE),
         "The not just X but Y shape. State the point directly."),
    Rule(13, "long-dash", re.compile("\N{EM DASH}|\N{EN DASH}|(?<= )--(?= )"),
         "Dash punctuation. End the sentence or use a comma."),
    Rule(19, "curly-quotes", re.compile("[‘’“”]"),
         "Curly quote. Use a straight quote."),
    phrase_rule(20, "chatbot-phrase", CHATBOT_PHRASES,
                "Stock chatbot phrase. Remove it."),
    phrase_rule(22, "sycophancy", SYCOPHANTIC,
                "Sycophantic opener. Respond directly instead."),
    phrase_rule(23, "filler", FILLER,
                "Filler phrase. Cut it or use the short form."),
    phrase_rule(26, "metaphor-noun", METAPHOR_NOUNS,
                "Abstract metaphor noun. Use the concrete word."),
)
EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002190-\U000021FF\U00002600-\U000027BF\U0000FE0F\U00002B00-\U00002BFF]"
)
