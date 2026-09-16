# Security Policy

## Supported Versions

agentcost is currently in alpha development (`0.x`). Security fixes are provided for the latest published release only.

| Version | Supported |
| ------- | --------- |
| Latest `0.x` release | Yes |
| Older `0.x` releases | No |

If a vulnerability is fixed, users should upgrade to the newest available release as soon as possible.

## Reporting a Vulnerability

Please do not open a public GitHub issue for security vulnerabilities.

To report a vulnerability, use one of these private channels:

- GitHub private vulnerability reporting, if available on the repository: <https://github.com/yunaremaia/agentcost/security/advisories/new>
- Email the maintainer at <yunare@gmail.com>

Please include as much detail as you can safely share:

- A description of the issue and affected behavior
- Steps to reproduce or a minimal proof of concept
- The affected agentcost version, Python version, and operating system
- Any known impact, workarounds, or suggested fixes

The maintainer will review the report, follow up if more information is needed, and coordinate a fix before public disclosure when appropriate.

## Security Measures

agentcost is a local CLI tool that reads agent log files and calculates token usage and cost. The project follows these security practices:

- Keeps the runtime dependency surface small
- Avoids collecting or transmitting user data by default
- Treats log input as untrusted data
- Uses pull requests and automated tests for changes
- Encourages responsible disclosure for security issues

Contributors should never commit API keys, tokens, passwords, private logs, or other secrets. If a secret is accidentally exposed, rotate it immediately and remove it from history where possible.

## Dependencies

Dependency vulnerabilities are handled by reviewing security advisories, updating affected packages, and releasing a patched version when the issue affects agentcost users.

For dependency-related reports, include the vulnerable package name, affected version range, advisory link if available, and whether the vulnerable code path is reachable through agentcost.
