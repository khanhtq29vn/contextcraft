# Security Policy

## Supported Versions

We actively maintain and provide security updates for the latest minor release of **ContextCraft**:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :white_check_mark: |

## Built-In Security Guarantees

`ContextCraft` is designed as a **local-first, zero-telemetry compiler**:
1. **No External Data Transmission:** `ContextCraft` never uploads your source code or repository metadata to any external server.
2. **Pre-AST Secret Scrubbing (`SecretSanitizer`):** By default, API keys (`sk-proj-...`, `sk-ant-...`, `AKIA...`, `ghp_...`, `AIza...`), PEM private key blocks, `.env` secrets, and high-entropy credentials are automatically scrubbed before AST parsing and output emission.

## Web Playground Filesystem Access

The web API restricts local repository requests to `CONTEXTCRAFT_WEB_ROOT`, or
the server's working directory when that variable is unset. Relative paths are
resolved from this root; absolute paths must also be inside it. Paths that
resolve outside the root, including escaping symlinks, receive HTTP 403.
GitHub repositories are cloned into a fixed directory within a temporary
workspace, separate from the local repository root.

Set the root before starting the server and include only files you intend web
clients to access. The playground has no authentication; keep it bound to
localhost unless access is controlled separately. Secret redaction does not
replace access control and can be disabled by an API request.

The CLI and SDK accept caller-selected repository directories without the web
API's root restriction.

## Reporting a Vulnerability

We take the security of `ContextCraft` and our users' codebases seriously. If you discover a security vulnerability (for example, a path-traversal issue in the web playground, a regex denial-of-service in the parser/sanitizer, or a bypass in secret scrubbing), **please do not report it via a public GitHub issue.**

Instead, please report it privately using **GitHub Private Vulnerability Reporting**:

1. Navigate to the [**Security** tab of `khanhtq29vn/contextcraft`](https://github.com/khanhtq29vn/contextcraft/security).
2. Click **"Report a vulnerability"** to open a private security advisory.
3. Provide a concise description and minimal reproduction steps.

We will acknowledge receipt of your report within **48 hours** and work with you to validate, patch, and credit your discovery.