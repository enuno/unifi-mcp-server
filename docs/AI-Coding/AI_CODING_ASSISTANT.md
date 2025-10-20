# AI Coding Assistant Guidelines for UniFi MCP Server

This document provides essential guidelines and project-specific standards for AI coding assistants contributing to the UniFi MCP Server project. Adhering to these practices ensures consistency, quality, and effective collaboration between human and AI developers.

## Generic Rules and Guidelines

All AI assistants must follow a set of standardized practices to maintain repository hygiene and streamline development workflows. These generic rules are essential for any project and form the foundation for more specific instructions.

### Core Principles

- **Clarity and Consistency:** Code and documentation should be clear, concise, and consistent with the project's existing style.
- **Safety and Security:** Mutating operations must require explicit confirmation. Sensitive data, such as API keys and credentials, must never be hardcoded and should be managed through environment variables or a secure secrets management system.
- **Modularity and Reusability:** Design components to be modular and reusable. For instance, API request logic should be centralized in helper functions to avoid code duplication.

### Standard Project Files

The following table outlines the key Markdown files that should be present in a well-structured, AI-assisted project. These files provide critical context and guidance for both human and AI contributors.

| File Name | Description |
| :--- | :--- |
| `README.md` | Provides a high-level overview of the project, setup instructions, and essential context. |
| `AGENTS.md` | A centralized file detailing universal rules, do's and don'ts, and expected workflows for all AI coding agents. |
| `.aiignore` | Specifies files and directories that AI tools should exclude from their analysis or code generation. |
| `CONTRIBUTING.md` | Outlines guidelines for contributing, including review protocols and code documentation practices. |
| `SECURITY.md` | Details security policies, including instructions for handling sensitive data and managing access for all contributors. |
| `API.md` | Comprehensive API documentation to inform all agents of architectural conventions, endpoints, and protocol standards. |

## Project-Specific Coding Standards

These standards are tailored to the UniFi MCP Server project and build upon the generic guidelines. All AI-generated code must conform to these project-specific conventions.

### Project Overview

The goal of this project is to develop a Model Context Protocol (MCP) server that exposes the UniFi Network API as a set of programmable tools. This will enable AI agents and other applications to interact with UniFi network controllers in a standardized way.

### Key Technologies and Dependencies

The project leverages the following key technologies:

- **Python:** The primary programming language (version 3.10 or higher).
- **FastMCP:** The core library for building the MCP server.
- **uv:** For Python package and virtual environment management.
- **httpx/requests:** For making HTTP requests to the UniFi Network API.
- **Docker:** For containerization and simplified deployment.

### Code Structure and Conventions

The project follows a structure similar to the reference implementation from `sirkirby/unifi-network-mcp` [1]. Key structural conventions are outlined below:

> The server merges settings from **environment variables**, an optional `.env` file, and `src/config/config.yaml` (listed in order of precedence).

- **Configuration:** Configuration should be managed through a combination of environment variables, a `.env` file for local development, and a default `config.yaml` file. This provides flexibility for different environments.
- **API Interaction:** All interactions with the UniFi Network API should be encapsulated within a dedicated helper function. This function will handle request signing, error handling, and response parsing, ensuring a single, reliable point of interaction with the API.
- **Tool and Resource Definitions:** MCP tools and resources should be defined using the `@mcp.tool()` and `@mcp.resource()` decorators from the FastMCP library. Resource URIs should follow a logical and consistent naming scheme, such as `sites://{site_id}/devices`.
- **Asynchronous Operations:** Where appropriate, use `async` functions for I/O-bound operations, such as making API calls, to improve performance.

### Development and Testing

For local development and testing, the following steps should be followed, as inspired by the `makewithdata.tech` guide [2]:

1.  **Initialize the Environment:** Use `uv` to create a virtual environment and install the necessary dependencies.
2.  **Run the Server:** Start the MCP server in development mode using a command like `uv run mcp dev main.py`. This will enable the MCP Inspector, a valuable tool for debugging.
3.  **Testing:** The MCP Inspector, available at `http://localhost:5173`, should be used to test tool and resource implementations interactively.

### References

[1] sirkirby. (2025). *unifi-network-mcp*. GitHub. Retrieved from [https://github.com/sirkirby/unifi-network-mcp](https://github.com/sirkirby/unifi-network-mcp)

[2] King, Z. (2025, March 30). *Build a MCP Server for AI Access to UniFi Networks (Goose or Claude)*. MakeWithData. Retrieved from [https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access](https://www.makewithdata.tech/p/build-a-mcp-server-for-ai-access)


