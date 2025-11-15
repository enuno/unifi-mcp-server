---
description: Build and test Docker image locally
allowed-tools:
  - Bash(docker:*)
  - Read
  - Write
author: project
version: 1.0.0
---

Build the Docker image locally and verify it works.

Execute the following steps:

1. Check if Dockerfile exists; if not, offer to create one
2. Build the Docker image: `docker build -t unifi-mcp-server:local .`
3. Display the build output and any warnings
4. List the image size and layers
5. Optionally run the container with test environment variables

Report back with:

- Build success/failure status
- Image size
- Any build warnings or errors
- Suggestions for optimization if needed
