# Writing a challenge

Each challenge is a folder with a `challenge.yaml` and the files the agent
gets. The flag is stored only as a SHA-256 hash. The plaintext flag and your
reference solution live in a private folder outside the repo.

## 1. Scaffold it

```bash
uv run flaghunt challenge new hidden-message \
  --name "Hidden Message" --category forensics --difficulty easy
```

You'll be asked for the flag without it being shown, which keeps it out of
your shell history. This creates:

```
challenges/hidden-message/
├── challenge.yaml          id, name, category, difficulty, flag hash
└── files/                  put the player's files here

~/Documents/flaghunt-private/hidden-message/    (never commit)
├── NOTES.md                the flag, intended solution, how you made the files
└── solve.sh                your reference solution
```

Set `FLAGHUNT_PRIVATE_DIR` to keep private files somewhere else.

## 2. Build it

- Put the player's files in `files/` and list each one under `files:` in
  `challenge.yaml`.
- Write the `description`. Give enough context to start, but don't name the
  technique.
- Note in `NOTES.md` how you made the files, so you can regenerate them later.

## 3. Write the reference solution

`solve.sh` runs inside the sandbox with the challenge files in the current
directory (`/work`). Any other files in your private folder are copied to
`/tmp/solution`. The script must print the flag. Use only tools the sandbox
has (see `sandbox/Dockerfile`), because agents get the same environment.

## 4. Check it

```bash
uv run flaghunt challenge check hidden-message    # or --all
```

This validates the YAML and files, warns if the flag sits in plain text,
then runs `solve.sh` in a fresh sandbox and confirms it prints the correct
flag. A challenge isn't done until this passes.

## 5. Calibrate it

```bash
uv run flaghunt run --agent examples/grep_agent.py:GrepAgent --challenge hidden-message
uv run flaghunt run --agent agents/local-qwen3.5-9b.yaml --challenge hidden-message
```

| Difficulty | Rough meaning |
|---|---|
| easy | One to three standard commands once you know what to look for |
| medium | You have to recognize a technique or write a short script |
| hard | Several chained steps or real analysis |

Relabel after a few models have attempted it.

## Rules

- Self-contained files only. Nothing may need network access.
- No real malware, real credentials, or data about real people or
  organisations.
- Categories: `crypto`, `forensics`, `rev`, `web`, `pwn`, `misc`.
- Keep a challenge's files under 20 MB in total.
