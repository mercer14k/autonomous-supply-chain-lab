# Security policy

This is a local, single-operator research application. Supported version: current main branch.

Do not use default demo credentials on a network-exposed host. Docker Compose binds only to 127.0.0.1 and keeps PostgreSQL off host ports. Configure separate READ_TOKEN and WRITE_TOKEN values when sharing local access. The browser stores the operator token in session storage; an XSS vulnerability could expose it.

Report vulnerabilities using the repository's GitHub private vulnerability reporting feature once enabled by its owner. If unavailable, contact the repository owner privately; do not publish exploitable details or secrets in an issue. Maintainers should acknowledge reports within seven days; no service-level guarantee is offered.

See docs/security.md for trust boundaries, controls, residual risks, and deployment limitations.
