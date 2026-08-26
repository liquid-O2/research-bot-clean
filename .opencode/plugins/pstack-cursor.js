import { spawnSync } from "node:child_process"
import { existsSync, readdirSync, readFileSync, statSync, mkdirSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { basename, dirname, extname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = "/workspace"
const SKIP_NAMES = new Set(["cursor-pstack"])
const STATE_DIR = join(ROOT, ".opencode", "state")
const WAKE_COUNT = 12
const START_NUDGE =
  "pstack-lab. You are in /poteto-mode. " +
  "Fire task for playbook leaves. poteto-agent for code delegates. " +
  "generalPurpose when a skill names it. explore for read-only search. " +
  "Parent is Grok. Hard specified work is openai/gpt-5.6-sol. " +
  "You write MEMORY.md notes. The human does not. Unslop the reply."

function parseMdc(raw, filePath) {
  const name = basename(filePath, extname(filePath))
  const m = String(raw).match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!m) {
    return {
      name,
      filePath,
      alwaysApply: false,
      globs: [],
      description: "",
      body: String(raw).trim(),
      mode: "manual",
    }
  }
  const fm = m[1]
  const body = m[2].trim()
  let alwaysApply = false
  let description = ""
  let globs = []
  for (const line of fm.split(/\r?\n/)) {
    const am = line.match(/^alwaysApply:\s*(true|false)\s*$/i)
    if (am) alwaysApply = am[1].toLowerCase() === "true"
    const dm = line.match(/^description:\s*(.*)$/)
    if (dm) description = dm[1].replace(/^["']|["']$/g, "").trim()
    const gm = line.match(/^globs:\s*(.*)$/)
    if (gm) {
      const rest = gm[1].trim()
      if (rest.startsWith("[")) {
        globs = rest
          .slice(1, -1)
          .split(",")
          .map((s) => s.replace(/^[\s"']+|[\s"']+$/g, ""))
          .filter(Boolean)
      } else if (rest) {
        globs = rest.split(",").map((s) => s.replace(/^[\s"']+|[\s"']+$/g, "")).filter(Boolean)
      }
    }
  }
  if (globs.length === 0) {
    const block = fm.match(/^globs:\s*\n((?:[ \t]+-[ \t]+.+\n?)+)/m)
    if (block) {
      globs = block[1]
        .split("\n")
        .map((l) => l.replace(/^[ \t]+-[ \t]+/, "").replace(/^["']|["']$/g, "").trim())
        .filter(Boolean)
    }
  }
  let mode = "manual"
  if (alwaysApply) mode = "always"
  else if (globs.length) mode = "glob"
  else if (description) mode = "agent"
  return { name, filePath, alwaysApply, globs, description, body, mode }
}

function globToRegExp(glob) {
  let g = String(glob).trim().replace(/\\/g, "/")
  if (!g) return null
  if (!g.includes("/")) g = "**/" + g
  const re = g
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*\*/g, "\0")
    .replace(/\*/g, "[^/]*")
    .replace(/\0/g, ".*")
    .replace(/\?/g, "[^/]")
  return new RegExp("^" + re + "$")
}

function globMatch(globs, filePath) {
  const norm = String(filePath).replace(/\\/g, "/")
  const base = basename(norm)
  for (const g of globs) {
    const re = globToRegExp(g)
    if (!re) continue
    if (re.test(norm) || re.test(base)) return true
    const idx = norm.indexOf("/.cursor/") >= 0 ? -1 : 0
    void idx
    if (norm.endsWith("/" + g.replace(/^\*\*\//, ""))) return true
  }
  return false
}

function walkMdc(dir, out) {
  if (!dir || !existsSync(dir)) return
  let entries
  try {
    entries = readdirSync(dir, { withFileTypes: true })
  } catch {
    return
  }
  for (const ent of entries) {
    if (ent.name.startsWith(".")) continue
    const p = join(dir, ent.name)
    if (ent.isDirectory()) {
      walkMdc(p, out)
      continue
    }
    if (!ent.isFile()) continue
    if (!ent.name.endsWith(".mdc")) continue
    out.push(p)
  }
}

function loadRules(projectDir) {
  const dirs = [
    join(homedir(), ".cursor", "rules"),
    join(ROOT, ".cursor", "plugins", "pstack-lab", "rules"),
    join(projectDir, ".cursor", "rules"),
    join(projectDir, ".opencode", "rules"),
  ]
  const byName = new Map()
  for (const dir of dirs) {
    const files = []
    walkMdc(dir, files)
    for (const file of files) {
      const name = basename(file, ".mdc")
      if (SKIP_NAMES.has(name)) continue
      let raw = ""
      try {
        raw = readFileSync(file, "utf8")
      } catch {
        continue
      }
      byName.set(name, parseMdc(raw, file))
    }
  }
  return [...byName.values()]
}

function extractPaths(args) {
  const paths = []
  if (!args || typeof args !== "object") return paths
  for (const key of ["filePath", "file_path", "path", "target", "targetFile"]) {
    const v = args[key]
    if (typeof v === "string" && v) paths.push(v)
  }
  if (Array.isArray(args.paths)) {
    for (const v of args.paths) if (typeof v === "string" && v) paths.push(v)
  }
  return paths
}

function mentioned(rule, text) {
  const t = String(text || "").toLowerCase()
  if (!t) return false
  if (t.includes("@" + rule.name.toLowerCase())) return true
  if (t.includes(rule.name.toLowerCase() + ".mdc")) return true
  return false
}

function selectRules(rules, { paths, prompt }) {
  const always = []
  const globbed = []
  const requested = []
  const catalog = []
  for (const rule of rules) {
    if (rule.mode === "always") {
      always.push(rule)
      continue
    }
    if (rule.mode === "glob") {
      if (paths.some((p) => globMatch(rule.globs, p))) globbed.push(rule)
      continue
    }
    if (rule.mode === "agent") {
      catalog.push(rule)
      if (mentioned(rule, prompt)) requested.push(rule)
      continue
    }
    if (mentioned(rule, prompt)) requested.push(rule)
  }
  return { always, globbed, requested, catalog }
}

function formatRules(selected) {
  const blocks = []
  const seen = new Set()
  for (const group of [selected.always, selected.globbed, selected.requested]) {
    for (const rule of group) {
      if (seen.has(rule.name)) continue
      seen.add(rule.name)
      blocks.push(`## ${rule.name}\n${rule.body}`)
    }
  }
  if (selected.catalog.length) {
    const lines = selected.catalog
      .filter((r) => !seen.has(r.name))
      .map((r) => `- ${r.name}: ${r.description}`)
    if (lines.length) {
      blocks.push(
        "## Agent-requested rules\nNot injected. Open the matching `.mdc` if the description fits.\n" +
          lines.join("\n"),
      )
    }
  }
  if (!blocks.length) return ""
  return "# Cursor rules in force\n\n" + blocks.join("\n\n")
}

function lastingNotes(raw) {
  const lines = String(raw)
    .split("\n")
    .filter((line) => line.startsWith("- "))
  const kept = lines.filter((line) => !line.includes(" COMPACT session "))
  return kept.slice(-WAKE_COUNT)
}

function ledger(args) {
  try {
    const r = spawnSync("/usr/bin/python3", [join(ROOT, "tools", "memory_ledger.py"), ...args], {
      cwd: ROOT,
      encoding: "utf8",
      timeout: 8000,
      env: { ...process.env, PATH: "/usr/bin:/bin:" + (process.env.PATH || "") },
    })
    if (r.status !== 0) return ""
    return (r.stdout || "").trim()
  } catch {
    return ""
  }
}

function memoryBlock() {
  const notes = lastingNotes(ledger(["tail", "40"]))
  if (!notes.length) {
    return "MEMORY.md wake empty. Run python3 tools/memory_ledger.py recall yourself."
  }
  return "MEMORY.md wake:\n" + notes.join("\n")
}

function ensureStateDir() {
  try {
    mkdirSync(STATE_DIR, { recursive: true })
  } catch {
    /* ignore */
  }
}

function claudeAdvise(prompt) {
  const args = ["-p", String(prompt || ""), "--output-format", "text"]
  const r = spawnSync("claude", args, {
    cwd: ROOT,
    encoding: "utf8",
    timeout: 600000,
    maxBuffer: 8 * 1024 * 1024,
    env: {
      ...process.env,
      PATH: "/home/algo/.local/bin:/usr/bin:/bin:" + (process.env.PATH || ""),
    },
  })
  const out = ((r.stdout || "") + (r.stderr ? "\n" + r.stderr : "")).trim()
  if (r.error) {
    return { ok: false, text: "claude_advisor could not start: " + r.error.message }
  }
  if (r.status !== 0) {
    return { ok: false, text: "claude_advisor exited " + String(r.status) + "\n" + out }
  }
  return { ok: true, text: out || "(empty Claude reply)" }
}

function selftest() {
  const always = parseMdc(
    "---\ndescription: x\nalwaysApply: true\n---\n\n# Body\nOK\n",
    "/tmp/akita.mdc",
  )
  if (always.mode !== "always" || always.body.indexOf("OK") < 0) throw new Error("always")
  const glob = parseMdc(
    "---\ndescription: py\nglobs: \"*.py, engine/**/*.py\"\nalwaysApply: false\n---\n\nPY\n",
    "/tmp/py.mdc",
  )
  if (glob.mode !== "glob" || !globMatch(glob.globs, "engine/foo.py")) throw new Error("glob")
  const manual = parseMdc("# Manual\nHI\n", "/tmp/legacy.mdc")
  if (manual.mode !== "manual") throw new Error("manual")
  const agent = parseMdc("---\ndescription: REST API\n---\n\nAPI\n", "/tmp/api.mdc")
  if (agent.mode !== "agent") throw new Error("agent")
  const selected = selectRules(
    [always, glob, manual, agent],
    { paths: ["engine/foo.py"], prompt: "see @legacy" },
  )
  if (selected.always.length !== 1) throw new Error("select always")
  if (selected.globbed.length !== 1) throw new Error("select glob")
  if (!selected.requested.some((r) => r.name === "legacy")) throw new Error("select manual")
  const skip = SKIP_NAMES.has("cursor-pstack")
  if (!skip) throw new Error("skip")
  process.stdout.write("pstack-cursor selftest ok\n")
}

export const PstackCursor = async ({ directory }) => {
  const projectDir = directory || ROOT
  const sessionPaths = new Set()
  const sessionPrompt = { text: "" }
  let wake = ""
  let woke = false

  const rules = loadRules(projectDir)
  ensureStateDir()
  try {
    writeFileSync(
      join(STATE_DIR, "rules-loaded.json"),
      JSON.stringify(
        rules.map((r) => ({ name: r.name, mode: r.mode, file: r.filePath })),
        null,
        2,
      ),
    )
  } catch {
    /* ignore */
  }

  return {
    tool: {
      claude_advisor: {
        description:
          "Ask Claude Code (Max plan CLI) for advisor or architect advice. Use for poteto-mode Fable seats: how explainer, judgment, why synthesizer, architect advice. Blocks until Claude exits. Do not use for implementation.",
        args: {
          prompt: {
            type: "string",
            description: "The advice request. Include the plan, files, and the question. Not a request to write the code.",
          },
        },
        async execute(args) {
          const result = claudeAdvise(args?.prompt || "")
          return result.text
        },
      },
    },
    event: async ({ event }) => {
      if (event?.type === "session.created") {
        wake = START_NUDGE + "\n\n" + memoryBlock()
        woke = false
        sessionPaths.clear()
      }
    },
    "tool.execute.before": async (input, output) => {
      for (const p of extractPaths(output?.args || input)) {
        sessionPaths.add(p)
      }
    },
    "chat.message": async (input) => {
      const parts = input?.message?.parts || input?.parts || []
      const texts = []
      for (const part of parts) {
        if (part && typeof part.text === "string") texts.push(part.text)
      }
      if (typeof input?.text === "string") texts.push(input.text)
      if (texts.length) sessionPrompt.text = texts.join("\n")
    },
    "experimental.chat.system.transform": async (_input, output) => {
      if (!Array.isArray(output.system)) return
      if (!wake) wake = START_NUDGE + "\n\n" + memoryBlock()
      const selected = selectRules(rules, {
        paths: [...sessionPaths],
        prompt: sessionPrompt.text,
      })
      const block = formatRules(selected)
      if (block) output.system.push(block)
      if (!woke) {
        output.system.push(wake)
        woke = true
      }
    },
    "experimental.session.compacting": async (input, output) => {
      const session = input?.sessionID || "opencode"
      ledger([
        "checkpoint",
        `- session: ${session}\n- transcript record: compact-opencode\n- trigger: compacting\n`,
      ])
      if (Array.isArray(output.context)) {
        output.context.push("Context compacting. Re-ground from MEMORY.md.\n\n" + memoryBlock())
      }
    },
  }
}

try {
  const here = fileURLToPath(import.meta.url)
  const invoked = process.argv[1] ? resolve(process.argv[1]) : ""
  if (here === invoked) selftest()
} catch {
  /* ignore */
}
