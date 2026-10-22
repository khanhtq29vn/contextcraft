"""Shared pytest fixtures for the ContextCraft test suite.

Builds a realistic, multi-language synthetic repository in `tmp_path` containing:
- Core domain models (`src/auth/models.py`) imported across the codebase
- Service implementation (`src/auth/jwt_service.py`) with docstrings, multi-line bodies,
  and an embedded OpenAI API key to test secret scrubbing
- API routes (`src/api/routes.py`) importing the auth service and models
- TypeScript client (`src/frontend/client.ts`) with interfaces and classes
- Unimported leaf utilities (`src/utils/helpers.py`) to test PageRank centrality ranking
- `.gitignore` rules, ignored files, and binary assets
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    """Create and return a synthetic multi-file repository for testing."""
    repo = tmp_path / "synthetic_repo"
    repo.mkdir(parents=True, exist_ok=True)

    # 1. .gitignore
    (repo / ".gitignore").write_text(
        "# Ignore build & logs\nignored_dir/\n*.log\nsecret_notes.txt\n",
        encoding="utf-8",
    )

    # 2. README.md & pyproject.toml
    (repo / "README.md").write_text(
        "# Synthetic Auth Service\n\n"
        "Architecture overview for token verification and API routing.\n"
        "- **Core Models:** `src/auth/models.py`\n"
        "- **JWT Service:** `src/auth/jwt_service.py`\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "synthetic-auth"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    # 3. Core module: src/auth/models.py (heavily imported across repo)
    auth_dir = repo / "src" / "auth"
    auth_dir.mkdir(parents=True, exist_ok=True)
    (auth_dir / "__init__.py").write_text(
        "from src.auth.models import AuthConfig, TokenPayload, UserClaims\n",
        encoding="utf-8",
    )
    (auth_dir / "models.py").write_text(
        '"""Core authentication domain models shared across services."""\n\n'
        "from __future__ import annotations\n\n"
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class AuthConfig:\n"
        '    """Configuration parameters for JWT verification."""\n\n'
        "    issuer: str\n"
        "    audience: str\n"
        "    ttl_seconds: int = 3600\n\n\n"
        "@dataclass(frozen=True)\n"
        "class UserClaims:\n"
        '    """Authenticated user identity claims extracted from a verified token."""\n\n'
        "    user_id: str\n"
        "    email: str\n"
        "    roles: tuple[str, ...]\n\n"
        "    def has_permission(self, required_role: str) -> bool:\n"
        '        """Return True if the user holds `required_role` or admin rights."""\n'
        "        normalized = required_role.strip().lower()\n"
        "        held = {r.strip().lower() for r in self.roles}\n"
        '        if "admin" in held:\n'
        "            return True\n"
        "        return normalized in held\n\n\n"
        "@dataclass(frozen=True)\n"
        "class TokenPayload:\n"
        '    """Raw decoded JWT token payload container."""\n\n'
        "    raw_token: str\n"
        "    claims: UserClaims\n"
        "    issued_at: int\n"
        "    expires_at: int\n",
        encoding="utf-8",
    )

    # 4. Service module: src/auth/jwt_service.py (imports models, includes fake secret)
    (auth_dir / "jwt_service.py").write_text(
        '"""JWT token verification and issuance service."""\n\n'
        "from __future__ import annotations\n\n"
        "import hashlib\n"
        "import hmac\n"
        "from src.auth.models import AuthConfig, TokenPayload, UserClaims\n\n"
        '# Intentional test credential that must be scrubbed by SecretSanitizer\n'
        'OPENAI_API_KEY = "sk-proj-1234567890abcdefghijklmnopQRSTUV"\n\n\n'
        "class JWTAuthService:\n"
        '    """Handles cryptographic JWT signing, verification, and revocation."""\n\n'
        "    def __init__(self, config: AuthConfig, signing_key: str) -> None:\n"
        '        """Initialize the service with `AuthConfig` and HMAC signing key."""\n'
        "        self.config = config\n"
        "        self._signing_key = signing_key.encode('utf-8')\n"
        "        self._revoked_tokens: set[str] = set()\n\n"
        "    def verify_token(self, token: str, current_timestamp: int) -> TokenPayload:\n"
        '        """Verify JWT signature and expiration timestamp, returning `TokenPayload`."""\n'
        "        if not token or '.' not in token:\n"
        '            raise ValueError("Malformed JWT token string")\n'
        "        if token in self._revoked_tokens:\n"
        '            raise PermissionError("Token has been explicitly revoked")\n'
        "        parts = token.split('.')\n"
        "        if len(parts) != 3:\n"
        '            raise ValueError("Expected header.payload.signature segments")\n'
        "        header_b64, payload_b64, signature_hex = parts\n"
        "        message = f'{header_b64}.{payload_b64}'.encode('utf-8')\n"
        "        expected_sig = hmac.new(self._signing_key, message, hashlib.sha256).hexdigest()\n"
        "        if not hmac.compare_digest(expected_sig, signature_hex):\n"
        '            raise PermissionError("Invalid JWT cryptographic signature")\n'
        "        claims = UserClaims(user_id=payload_b64, email='user@example.com', roles=('member',))\n"
        "        expires = current_timestamp + self.config.ttl_seconds\n"
        "        return TokenPayload(raw_token=token, claims=claims, issued_at=current_timestamp, expires_at=expires)\n\n"
        "    def revoke_token(self, token: str) -> bool:\n"
        '        """Add `token` to the in-memory revocation denylist."""\n'
        "        cleaned = token.strip()\n"
        "        if not cleaned:\n"
        "            return False\n"
        "        already_revoked = cleaned in self._revoked_tokens\n"
        "        self._revoked_tokens.add(cleaned)\n"
        "        return not already_revoked\n",
        encoding="utf-8",
    )

    # 5. API module: src/api/routes.py (imports JWTAuthService and models)
    api_dir = repo / "src" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / "routes.py").write_text(
        '"""HTTP route handlers for user authentication and profile access."""\n\n'
        "from __future__ import annotations\n\n"
        "from typing import Any\n"
        "from src.auth.jwt_service import JWTAuthService\n"
        "from src.auth.models import AuthConfig, TokenPayload, UserClaims\n\n\n"
        "def authenticate_request(\n"
        "    service: JWTAuthService,\n"
        "    authorization_header: str,\n"
        "    timestamp: int,\n"
        ") -> UserClaims:\n"
        '    """Extract Bearer token from header and return verified `UserClaims`."""\n'
        "    if not authorization_header.startswith('Bearer '):\n"
        '        raise PermissionError("Missing Bearer prefix in Authorization header")\n'
        "    raw_token = authorization_header[len('Bearer '):].strip()\n"
        "    payload: TokenPayload = service.verify_token(raw_token, current_timestamp=timestamp)\n"
        "    if payload.expires_at < timestamp:\n"
        '        raise PermissionError("Token has expired")\n'
        "    return payload.claims\n\n\n"
        "def get_user_profile_ handler(\n"
        "    service: JWTAuthService,\n"
        "    authorization_header: str,\n"
        "    timestamp: int,\n"
        ") -> dict[str, Any]:\n"
        '    """Return serialized profile dictionary for an authenticated user."""\n'
        "    claims = authenticate_request(service, authorization_header, timestamp)\n"
        "    is_admin = claims.has_permission('admin')\n"
        "    return {\n"
        "        'user_id': claims.user_id,\n"
        "        'email': claims.email,\n"
        "        'roles': list(claims.roles),\n"
        "        'is_admin': is_admin,\n"
        "        'issuer': service.config.issuer,\n"
        "    }\n".replace("get_user_profile_ handler", "get_user_profile_handler"),
        encoding="utf-8",
    )

    # 6. TypeScript module: src/frontend/client.ts
    fe_dir = repo / "src" / "frontend"
    fe_dir.mkdir(parents=True, exist_ok=True)
    (fe_dir / "client.ts").write_text(
        "/** Frontend API client for authentication endpoints. */\n\n"
        "export interface AuthResponse {\n"
        "  userId: string;\n"
        "  email: string;\n"
        "  roles: string[];\n"
        "}\n\n"
        "export class AuthApiClient {\n"
        "  private readonly baseUrl: string;\n\n"
        "  constructor(baseUrl: string) {\n"
        "    this.baseUrl = baseUrl.replace(/\\/+$/, '');\n"
        "  }\n\n"
        "  public async fetchProfile(bearerToken: string): Promise<AuthResponse> {\n"
        "    const endpoint = `${this.baseUrl}/api/profile`;\n"
        "    const headers: Record<string, string> = {\n"
        "      Authorization: `Bearer ${bearerToken}`,\n"
        "      Accept: 'application/json',\n"
        "    };\n"
        "    if (!bearerToken) {\n"
        "      throw new Error('Bearer token is required');\n"
        "    }\n"
        "    return { userId: endpoint, email: headers.Accept, roles: ['member'] };\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    # 7. Unimported peripheral leaf utility: src/utils/helpers.py
    utils_dir = repo / "src" / "utils"
    utils_dir.mkdir(parents=True, exist_ok=True)
    (utils_dir / "helpers.py").write_text(
        '"""Miscellaneous string and formatting leaf utilities."""\n\n'
        "from __future__ import annotations\n\n"
        "import re\n\n\n"
        "def slugify_label(text: str) -> str:\n"
        '    """Convert arbitrary text into a lowercase URL-safe slug."""\n'
        "    cleaned = re.sub(r'[^a-zA-Z0-9]+', '-', text.strip().lower())\n"
        "    cleaned = re.sub(r'-{2,}', '-', cleaned)\n"
        "    return cleaned.strip('-')\n\n\n"
        "def format_byte_size(num_bytes: int) -> str:\n"
        '    """Format an integer byte count into a human-readable string."""\n'
        "    if num_bytes < 1024:\n"
        "        return f'{num_bytes} B'\n"
        "    kb = num_bytes / 1024.0\n"
        "    if kb < 1024.0:\n"
        "        return f'{kb:.1f} KiB'\n"
        "    mb = kb / 1024.0\n"
        "    return f'{mb:.2f} MiB'\n",
        encoding="utf-8",
    )

    # 8. Ignored directory & log file (must be skipped by RepositoryScanner)
    ignored_dir = repo / "ignored_dir"
    ignored_dir.mkdir(parents=True, exist_ok=True)
    (ignored_dir / "skip_me.py").write_text("SHOULD_NOT_BE_SCANNED = True\n", encoding="utf-8")
    (repo / "debug.log").write_text("2026-01-01 INFO debug log line\n", encoding="utf-8")

    # 9. Binary file (must be detected and skipped as binary)
    assets_dir = repo / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "logo.dat").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00")

    return repo
