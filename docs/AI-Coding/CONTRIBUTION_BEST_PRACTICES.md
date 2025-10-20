# AI/Human Code Contribution Best Practices

Effective collaboration between human and AI developers requires a clear set of best practices for code contribution, access control, and repository management. This document outlines the standards for the UniFi MCP Server project, ensuring a secure, organized, and efficient development environment.

## Access Control and Permissions

A robust access control strategy is fundamental to repository security. The following principles should be applied to manage permissions for all contributors, both human and AI.

- **Principle of Least Privilege:** Grant only the minimum permissions necessary for each contributor to perform their tasks. This minimizes the potential impact of a compromised account or a misconfigured AI agent.
- **Role-Based Access Control (RBAC):** Utilize the RBAC features provided by GitHub to assign roles (e.g., read, write, admin) to contributors based on their responsibilities. For AI agents with code commit rights, their permissions should be carefully scoped and monitored.
- **Regular Audits:** Periodically review access lists to ensure they are up-to-date. Remove unnecessary privileges and offboard contributors who are no longer active on the project.

## Sensitive Data and .gitignore Management

Proper management of sensitive data and repository exclusions is critical to prevent accidental exposure of credentials and to keep the repository clean.

### .gitignore

A comprehensive `.gitignore` file is essential to prevent the accidental commit of sensitive information and unnecessary files. The following table details the types of files that should be included in the `.gitignore` file for this project.

| Category | Examples |
| :--- | :--- |
| **Credentials** | API keys, passwords, and other secrets. These should be managed through environment variables or a secure secrets management system. |
| **Environment Files** | `.env` files containing local development configurations. An `env.example` file should be committed to provide a template. |
| **Python Artifacts** | `__pycache__/`, `*.pyc`, and virtual environment directories (e.g., `.venv/`). |
| **Build Artifacts** | `dist/`, `build/`, and other build-related directories. |
| **IDE and Editor Files** | `.idea/`, `.vscode/`, and other editor-specific configuration files. |

### .aiignore

In addition to the standard `.gitignore` file, an `.aiignore` file should be used to specify files and directories that AI coding assistants should exclude from their analysis and code generation. This can help focus the AI's attention on relevant parts of the codebase and prevent it from modifying sensitive or irrelevant files.

## Repository Hygiene

Maintaining a clean and organized repository is crucial for long-term project health. The following practices contribute to good repository hygiene.

- **Branch Management:** All new features and bug fixes should be developed in separate branches. Branches should be named descriptively (e.g., `feature/add-firewall-rules-tool`, `fix/handle-api-rate-limiting`). Once work is complete and has been merged into the main branch, the feature branch should be deleted.
- **Regular Cleanups:** Periodically, the repository should be cleaned of stale branches, old pull requests, and other obsolete artifacts. This improves clarity and reduces clutter.
- **Archiving and Pruning:** Old experimental outputs, large data files, and other non-essential assets should be archived or pruned from the repository. For large files, consider using Git LFS (Large File Storage) or storing them in a separate object storage service.

By adhering to these contribution best practices, we can foster a collaborative environment that is both productive and secure, enabling human and AI developers to work together effectively to build a high-quality UniFi MCP Server.


