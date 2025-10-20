# AI-Specific Practices for Git Repositories

Collaborating with AI coding assistants introduces new dynamics to the development workflow. To ensure that the integration of AI-generated code enhances productivity without compromising quality, it is essential to adopt a set of Git practices tailored to this new paradigm. This document outlines the AI-specific practices for versioning, repository organization, and documentation for the UniFi MCP Server project.

## Versioning and Review of AI-Generated Code

AI-generated code should be treated with the same level of scrutiny as code written by human developers. A rigorous versioning and review process is critical for maintaining code quality, clarity, and maintainability.

> Treat AI-generated code changes with **the same rigor** as human-created code.

Key practices for versioning and reviewing AI-generated code are summarized in the table below:

| Practice | Description |
| :--- | :--- |
| **Descriptive Commit Messages** | Write clear and descriptive commit messages that explain the purpose and context of each AI-generated change. This is crucial for maintaining a comprehensible project history. |
| **Rigorous Peer Reviews** | Implement a peer review process that includes human developers. When possible, leverage AI-assisted code review tools to catch potential errors, stylistic inconsistencies, and other issues. |
| **Transparency and Auditability** | Maintain transparency about the involvement of AI in the development process. Tagging commits or pull requests as "AI-assisted" can be a useful practice for auditability and for tracking the impact of AI contributions over time. |

## Segregation of Experimental Outputs and Checkpoints

AI development, particularly in the realm of machine learning, often involves experimentation that generates a variety of outputs, such as model checkpoints, datasets, and performance logs. It is important to keep these experimental artifacts separate from the core source code.

- **Dedicated Directories:** Keep AI experiment outputs, model checkpoints, and large generated files in distinct directories, such as `outputs/` or `experiments/`. This prevents cluttering the main development area and simplifies code reviews.
- **.gitignore:** Use the `.gitignore` file to exclude large files, datasets, and other artifacts that should not be versioned directly in the Git repository. This helps keep the repository lightweight and focused on the source code.

By segregating these outputs, you can simplify navigation, speed up code review cycles, and reduce the likelihood of merge conflicts.

## Documentation of Custom Commands and Automation

To maximize the efficiency of AI assistants, it is often beneficial to create custom commands and automation scripts. Clear documentation of these tools is essential for ensuring they are used correctly and consistently by all contributors, both human and AI.

- **Dedicated Directory:** Create a dedicated directory for automation scripts and custom commands, for example, `.claude/commands/`.
- **Markdown Documentation:** Document each command’s purpose, usage, and parameters in Markdown files within this directory.
- **Quick-Reference Guides:** Provide quick-reference guides for common AI workflows, such as `/pr` to automate pull request creation or `/test` to run the test suite.

Well-documented commands facilitate consistent usage and improve collaboration efficiency. Adhering to these AI-specific Git practices will ensure that your repository remains clean, maintainable, and transparent, enabling both human developers and AI assistants to collaborate effectively while minimizing risks and maximizing productivity.


