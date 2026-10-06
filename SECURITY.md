# Security and scope

Flaghunt is a defensive research and education project. It measures how well
AI agents solve capture-the-flag challenges in an isolated sandbox.

## What the harness does and doesn't do

- Agents only ever act inside a disposable container started with
  `--network none`, `--cap-drop ALL` and `no-new-privileges`, as an
  unprivileged user, with CPU, memory and process limits.
- Model API calls are made by the harness on the host. API keys are never
  passed into the sandbox, and transcripts are scrubbed of anything that looks
  like a key before they are saved.
- Challenges are self-contained files that ship with the repo. The harness
  has no feature for pointing an agent at a real host or network, and
  contributions that add one will not be accepted.

## Rules for using and contributing

- Only run agents against challenges in this repo or targets you own or have
  written permission to test.
- New challenges must be self-contained and must not include real malware,
  real credentials, or data about real people or organisations.
- Store flags only as SHA-256 hashes (`flaghunt hash-flag 'flaghunt{...}'`).

## Supported versions

Only the latest commit on `main` is supported. Fixes are not backported.

## Reporting a vulnerability

If you find a way for an agent to escape the sandbox, reach the network, read
secrets it shouldn't, or tamper with results, please don't open a public issue.
Report it privately through GitHub's vulnerability reporting:

https://github.com/appliedagentsec/flaghunt/security/advisories/new

Include what you did, what happened, and the steps to reproduce it.

What to expect:

- A reply within 7 days confirming the report was received.
- An assessment within 14 days: whether it's a vulnerability, how severe it
  is, and the plan for a fix.
- Coordinated disclosure: the advisory is published once a fix is on `main`,
  normally within 90 days of the report.
- Credit in the advisory and the fix, unless you'd rather stay anonymous.
