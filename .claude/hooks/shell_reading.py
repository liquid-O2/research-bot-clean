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
from typing import Callable, Sequence

READONLY_GIT = frozenset({"blame", "diff", "log", "show", "status"})


@dataclass(frozen=True)
class WriteScan:
    """What a tool call can change: nothing, named paths, or something opaque."""

    kind: str
    paths: tuple[str, ...] = ()


# These take a mode or an owner before their paths.
MODE_FIRST = frozenset({"chmod", "chown", "install", "truncate"})
MUTATORS = frozenset({"rm", "mv", "cp", "touch", "mkdir", "rmdir", "install",
                      "truncate", "chmod", "chown", "ln", "shred", "unlink"})


def mutation_paths(command: str) -> tuple[str, ...]:
    """Return the paths an unambiguous mutating command names, if any.

    Only for a single plain command whose verb is a known mutator. Anything the
    shell would expand, redirect or chain returns nothing, and the caller then
    requires the method rather than guessing at a filename. That asymmetry is
    the point: a missed ownership check costs a little, and a refusal aimed at a
    file the command never touched costs the session.
    """
    words = plain_command_words(command)
    if words is None or Path(words[0]).name not in MUTATORS:
        return ()
    arguments = [word for word in words[1:] if not word.startswith("-")]
    if Path(words[0]).name in MODE_FIRST and arguments:
        arguments = arguments[1:]
    return tuple(arguments)


ENGAGE_SCRIPT = "method_guard" + ".py"
ENGAGE_VERB = "eng" + "age"
SAFE_SCOPE = re.compile(r"[a-z0-9][a-z0-9-]*\Z")


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


def has_expansion(word: str) -> bool:
    markers = "$`*?[]{}"
    return word.startswith("~") or any(marker in word for marker in markers)


def shell_operator(token: str) -> bool:
    return bool(token) and all(character in "><|&;()" for character in token)


def plain_pipeline(command: str) -> list[list[str]] | None:
    if "\n" in command or "\r" in command:
        return None
    tokens = shell_tokens(command)
    if not tokens:
        return None
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token == "|" and not segments[-1]:
            return None
        if token == "|":
            segments.append([])
            continue
        if shell_operator(token) or has_expansion(token):
            return None
        segments[-1].append(token)
    return segments if segments[-1] else None


def plain_arguments(arguments: Sequence[str]) -> bool:
    return bool(arguments) and all(not word.startswith("-") for word in arguments)


def optional_plain_arguments(arguments: Sequence[str]) -> bool:
    return all(not word.startswith("-") for word in arguments)


def cat_read(arguments: Sequence[str]) -> bool:
    return plain_arguments(arguments)


def ls_read(arguments: Sequence[str]) -> bool:
    letters = frozenset("aAbBcCdDfFgGhHiIklLmNopqQrRsStTuUvwxX1")
    return all(not word.startswith("-") or (len(word) > 1 and set(word[1:]) <= letters)
               for word in arguments)


def wc_read(arguments: Sequence[str]) -> bool:
    allowed = frozenset({"-c", "-l", "-m", "-w", "-L"})
    return bool(arguments) and all(word in allowed or not word.startswith("-")
                                   for word in arguments)


def rg_read(arguments: Sequence[str]) -> bool:
    if arguments and arguments[0] == "--files":
        return all(not word.startswith("-") for word in arguments[1:])
    return plain_arguments(arguments)


def find_read(arguments: Sequence[str]) -> bool:
    if not arguments or arguments[0].startswith("-"):
        return False
    index = 1
    while index < len(arguments):
        token = arguments[index]
        if token == "-print":
            index += 1
            continue
        if token != "-type" or index + 1 >= len(arguments):
            return False
        if arguments[index + 1] not in frozenset("bcdflps"):
            return False
        index += 2
    return True


def sed_read(arguments: Sequence[str]) -> bool:
    if len(arguments) < 3 or arguments[0] != "-n":
        return False
    if re.fullmatch(r"\d+(?:,\d+)?p", arguments[1]) is None:
        return False
    return all(not word.startswith("-") for word in arguments[2:])


def git_read(arguments: Sequence[str]) -> bool:
    if not arguments or arguments[0] not in READONLY_GIT:
        return False
    options = arguments[1:]
    if arguments[0] == "diff":
        return all(word == "--" or not word.startswith("-") for word in options)
    return all(not word.startswith("-") for word in options)


def command_read(arguments: Sequence[str]) -> bool:
    return (len(arguments) == 2 and arguments[0] == "-v"
            and not arguments[1].startswith("-"))


def python_read(arguments: Sequence[str]) -> bool:
    if len(arguments) != 3 or arguments[0] != "tools/memory_ledger.py":
        return False
    if arguments[1] == "tail":
        return arguments[2].isdigit()
    return arguments[1] == "recall" and not arguments[2].startswith("-")


READ_VALIDATORS: dict[str, Callable[[Sequence[str]], bool]] = {
    "cat": cat_read,
    "command": command_read,
    "diff": plain_arguments,
    "file": plain_arguments,
    "find": find_read,
    "git": git_read,
    "ls": ls_read,
    "python3": python_read,
    "rg": rg_read,
    "sed": sed_read,
    "sort": optional_plain_arguments,
    "wc": wc_read,
}


def readonly_command(command: str) -> bool:
    """Report whether every segment has a positive read grammar."""
    segments = plain_pipeline(command)
    if segments is None:
        return False
    for words in segments:
        validator = READ_VALIDATORS.get(Path(words[0]).name)
        if validator is None or not validator(words[1:]):
            return False
    return True


def memory_note(command: str) -> bool:
    words = plain_command_words(command)
    if words is None or len(words) != 4:
        return False
    return (Path(words[0]).name == "python3"
            and words[1:3] == ["tools/memory_ledger.py", "note"]
            and not words[3].startswith("-"))


def first_command(command: str) -> list[str]:
    """Return the words of the first command, before any shell operator."""
    tokens = shell_tokens(command)
    if tokens is None:
        return []
    words: list[str] = []
    for token in tokens:
        if shell_operator(token):
            break
        words.append(token)
    return words


def plain_command_words(command: str) -> list[str] | None:
    if "\n" in command or "\r" in command:
        return None
    tokens = shell_tokens(command)
    if not tokens:
        return None
    if any(shell_operator(token) or has_expansion(token) for token in tokens):
        return None
    return tokens


def invokes_engage(words: Sequence[str]) -> bool:
    if len(words) not in (4, 5) or SAFE_SCOPE.fullmatch(words[3]) is None:
        return False
    repository = Path.cwd()
    guard_paths = {
        (repository / ".codex/hooks" / ENGAGE_SCRIPT).resolve(),
        (repository / ".claude/hooks" / ENGAGE_SCRIPT).resolve(),
    }
    direct = (words[0] in ("python3", "/usr/bin/python3")
              and Path(words[1]).resolve() in guard_paths
              and words[2] == ENGAGE_VERB)
    chunk = len(words) == 4 or (re.fullmatch(r"[0-9]+", words[4]) is not None
                                and int(words[4]) > 0)
    return direct and chunk


def engage_attempt(words: Sequence[str]) -> bool:
    if len(words) < 3 or words[0] not in ("python3", "/usr/bin/python3"):
        return False
    repository = Path.cwd()
    guards = {(repository / client / ENGAGE_SCRIPT).resolve()
              for client in (".codex/hooks", ".claude/hooks")}
    return Path(words[1]).resolve() in guards and words[2] == ENGAGE_VERB


def bare_engage(command: str) -> bool:
    """Report whether this is an engage call that will print into the transcript.

    Such a call is always permitted. It is how a session obtains the method, so
    requiring the method first is circular, and it deadlocked the session that
    wrote this rule.
    """
    words = plain_command_words(command)
    return words is not None and invokes_engage(words)


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
    words = first_command(command)
    return engage_attempt(words) and (plain_command_words(command) is None
                                      or not invokes_engage(words))


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
    if memory_note(command):
        return WriteScan("paths", ("MEMORY.md",))
    paths = mutation_paths(command)
    return WriteScan("paths", paths) if paths else WriteScan("opaque")
