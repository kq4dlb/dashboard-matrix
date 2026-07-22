# Security policy

Dashboard Matrix can execute trusted Python plugins and allowlisted Python scripts, and it contains a controlled reverse proxy. Treat its Admin interface as privileged.

- Change the default Admin password immediately.
- Set a long random `DASHBOARD_MATRIX_SESSION_SECRET`.
- Do not expose Admin directly to the public internet.
- Install plugins only from sources you trust.
- Review scripts before placing them in the user script directory.
- Enable proxy sources only for sites you are authorized to retrieve and display.
- Do not configure a proxy to bypass access controls, subscriptions, authentication, or other restrictions.
- Keep the application and its dependencies updated.

For a private security report, contact the project maintainer through the repository rather than publishing credentials or exploit details in a public issue.
