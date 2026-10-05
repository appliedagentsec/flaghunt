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

## Reporting a vulnerability

If you find a way for an agent to escape the sandbox, reach the network, or
read secrets it shouldn't, please don't open a public issue. Report it
privately through GitHub's "Report a vulnerability" button on this repo's
Security tab. I'll aim to reply within a week and will credit you in the fix
unless you'd rather stay anonymous.
