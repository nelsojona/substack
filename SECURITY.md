# Security Policy

## Reporting a Vulnerability

The Substack to Markdown CLI team takes security issues seriously. We appreciate your efforts to responsibly disclose your findings and will make every effort to acknowledge your contributions.

To report a security vulnerability, please follow these steps:

1. **DO NOT** create a public GitHub issue for the vulnerability.
2. Message findings to me on Github @nelsojona. If possible, encrypt your message with our PGP key (available upon request).
3. Include the following information in your report:
   - Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
   - Full paths of source file(s) related to the manifestation of the issue
   - The location of the affected source code (tag/branch/commit or direct URL)
   - Any special configuration required to reproduce the issue
   - Step-by-step instructions to reproduce the issue
   - Proof-of-concept or exploit code (if possible)
   - Impact of the issue, including how an attacker might exploit the issue

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine the affected versions.
2. Audit code to find any potential similar problems.
3. Prepare fixes for all releases still under maintenance.
4. Release the fixes as soon as possible.

## Comments on This Policy

If you have suggestions on how this process could be improved, please submit a pull request.
