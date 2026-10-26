# Security

Origins Launcher is a prerelease project. There is no promised support period or
security-response deadline. Install only builds whose source and publisher you
trust, and keep macOS and Steam updated.

The launcher runs downloaded Windows software with your user account's access.
A Wine prefix separates configuration and files; it is **not a security sandbox**.
The project does not collect Steam credentials or upload diagnostic reports.

## Report a vulnerability

Email **[security@xr0.io](mailto:security@xr0.io)** with the subject
`OriginsLauncher security report`, or use **Security → Report a vulnerability**
on [this repository's Security page](https://github.com/Dr-Smth/OriginsLauncher/security)
when that option is available. Keep vulnerability details out of public issues.
Do not send Steam credentials, account tokens, signing
keys, personal logs, game files or exploitable user data.

GitHub's private vulnerability-reporting feature sends the report to the
maintainers without creating a public issue. If that option is unavailable,
use the email address above. See
[GitHub's reporting documentation](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).

Include affected source/build versions, the impact, a minimal reproduction using
synthetic data and any proposed fix. Download verification, archive extraction,
path containment, process ownership and diagnostic redaction are security-relevant
areas. Maintainers should follow [Releasing](docs/RELEASING.md) when preparing a fix.

The maintainer will review reports and coordinate any fix and disclosure with the
reporter where possible. This prerelease does not offer a bug bounty or guarantee
a response deadline. An email address in this policy does not establish encrypted
email support; ask for a suitable transfer method before sending sensitive material.

Do not disable Gatekeeper, antivirus or other macOS protections to investigate a
blocked download. Verify the source, signature and release checksum first.
