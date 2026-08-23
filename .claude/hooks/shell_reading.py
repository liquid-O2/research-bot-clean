"""Read a shell command only as far as it can be read without running it.

Every false denial this guard produced came from asking more of this module
than a shell command can answer. A heredoc body, an unexpanded variable, a `cd`
and a quoted greater-than sign each made it name a file the command never
touched. So it answers three questions and no more. Is this only a read? Does
it unambiguously name the files it changes? Would it hide an engage call?
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
from typing import Sequence

READONLY_COMMANDS = frozenset({
    "cat", "find", "grep", "head", "ls", "pwd", "readlink", "rg", "stat",
    "tail", "test", "wc", "diff", "echo", "which", "file", "du", "df",
})
READONLY_GIT = frozenset({"diff", "log", "show", "status", "branch", "blame"})


@dataclass(frozen=True)
class WriteScan:
    """What a tool call can change: nothing, named paths, or something opaque."""

    kind: str
    paths: tuple[str, ...] = ()


def command_words(command: str) -> list[str] | None:
    """Split a shell command, or None when it cannot be parsed."""
    try:
        return shlex.split(command)
    except ValueError:
        return None


IN_PLACE = frozenset({"-i", "--in-place"})
# These take a mode or an owner before their paths.
MODE_FIRST = frozenset({"chmod", "chown", "install", "truncate"})
MUTATORS = frozenset({"rm", "mv", "cp", "touch", "mkdir", "rmdir", "install",
                      "truncate", "chmod", "chown", "ln", "shred", "unlink"})


def simple_words(command: str) -> list[str] | None:
    """Return one command's words, or None when the shell would do more than run it.

    A token that is or begins with a shell operator means redirection, piping,
    substitution or chaining, and then this guard cannot say what runs or where
    its paths land. Quoted text is safe, because splitting already consumed the
    quotes: `printf 'x > y'` yields one word holding a greater-than sign, not a
    redirect.
    """
    words = command_words(command)
    if words is None or not words:
        return None
    if any(word.startswith(OPERATORS) or word in OPERATORS for word in words):
        return None
    return words


def readonly_command(command: str) -> bool:
    """Report whether a command only reads, so it needs no route.

    Deliberately conservative. Misreading a read as a change costs an engaged
    session and nothing else, so the allowlist stays small and exact.
    """
    words = simple_words(command)
    if words is None:
        return False
    executable = Path(words[0]).name
    if executable == "sed":
        return not IN_PLACE.intersection(words)
    if executable in READONLY_COMMANDS:
        return True
    return executable == "git" and len(words) > 1 and words[1] in READONLY_GIT


def mutation_paths(command: str) -> tuple[str, ...]:
    """Return the paths an unambiguous mutating command names, if any.

    Only for a single plain command whose verb is a known mutator. Anything the
    shell would expand, redirect or chain returns nothing, and the caller then
    requires the method rather than guessing at a filename. That asymmetry is
    the point: a missed ownership check costs a little, and a refusal aimed at a
    file the command never touched costs the session.
    """
    words = simple_words(command)
    if words is None or Path(words[0]).name not in MUTATORS:
        return ()
    arguments = [word for word in words[1:] if not word.startswith("-")]
    if Path(words[0]).name in MODE_FIRST and arguments:
        arguments = arguments[1:]
    return tuple(arguments)


OPERATORS = (">", "<", "|", "&", ";", "$", "`", "(", ")")
OPERATOR_TOKENS = frozenset({">", ">>", "<", "<<", "|", "||", "&", "&&", ";"})
ENGAGE_SCRIPT = "method_guard" + ".py"
ENGAGE_VERB = "eng" + "age"


def shell_tokens(command: str) -> list[str] | None:
    """Split a command, keeping shell operators as their own tokens.

    Quoting is honoured, so text that merely mentions an operator or a command
    name inside a quoted argument or a heredoc body stays one ordinary word.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def first_command(command: str) -> list[str]:
    """Return the words of the first command, before any shell operator."""
    tokens = shell_tokens(command)
    if tokens is None:
        return []
    words: list[str] = []
    for token in tokens:
        if token in OPERATOR_TOKENS:
            break
        words.append(token)
    return words


def invokes_engage(words: Sequence[str]) -> bool:
    """Report whether these words actually run the guard's engage verb."""
    pairs = zip(words, words[1:])
    return any(Path(word).name == ENGAGE_SCRIPT and following == ENGAGE_VERB
               for word, following in pairs)


def bare_engage(command: str) -> bool:
    """Report whether this is an engage call that will print into the transcript.

    Such a call is always permitted. It is how a session obtains the method, so
    requiring the method first is circular, and it deadlocked the session that
    wrote this rule.
    """
    return invokes_engage(first_command(command)) and simple_words(command) is not None


def hidden_engage(command: str) -> bool:
    """Report whether an engage call would be kept out of the transcript.

    The whole guarantee is that the method's exact text enters the session. A
    redirect or a pipe sends the packet somewhere else and leaves a summary
    behind, and the digest record cannot tell the difference. It was bypassed
    exactly this way, repeatedly, by the session that built it.

    Only the first command counts, so a heredoc or a quoted string that merely
    names the verb is not a call. A wrapper script could still hide the output;
    this closes the accident, not a determined workaround.
    """
    return invokes_engage(first_command(command)) and simple_words(command) is None


def scan_command(command: str) -> WriteScan:
    """Classify one shell command as a read, a named change, or an opaque one.

    The guard used to parse every command for the paths it writes. It cannot. A
    heredoc body, a shell variable, a `cd`, and a greater-than sign inside a
    quoted string each made it name a file the command never touched, and it
    refused real work six times in one session. It now reads paths only from a
    command simple enough to be unambiguous, and requires the method for the
    rest.
    """
    if readonly_command(command):
        return WriteScan("none")
    paths = mutation_paths(command)
    return WriteScan("paths", paths) if paths else WriteScan("opaque")
