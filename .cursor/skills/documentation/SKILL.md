---
name: documentation
description: Turn existing code into clear, accurate, developer-usable documentation with minimal fluff. Produce docs that help someone understand, use, maintain, and extend the code safely, including grounded Markdown diagrams that explain architecture, flows, and relationships in the codebase. Use when documenting repositories, packages, modules, functions, adding docstrings, creating README files, explaining architecture, or generating API documentation.
---

## When to Use
Use this skill when you need to:
- Document a repository, package, module, class, or function
- Add or upgrade docstrings, README, or API docs
- Explain architecture, data flow, and key decisions
- Produce usage examples and integration guidance
- Document CLI tools, configs, environment variables, and deployment steps
- Generate Markdown diagrams relevant to the codebase, such as architecture, sequence, flow, dependency, entity, and state diagrams

## Inputs You Expect
Ask for (or infer from context) the minimum needed:
- Code files (or snippets) and project structure
- Entry points (main, CLI, server start, notebook, etc.)
- Key configs (env vars, YAML/JSON, secrets placeholders)
- Intended audience (internal engineers, OSS users, beginners, etc.)
- Any constraints (style guide, docstring format, frameworks, deployment targets)

If you don't have the whole repo, document only what you can see, and mark assumptions clearly.

## Outputs You Produce
Depending on the request, produce one or more:
- `README.md` (project-level)
- `docs/` pages (architecture, API, guides)
- Docstrings in-code (Google/Numpy style)
- `CONTRIBUTING.md`
- `CHANGELOG.md` notes (if asked)
- Inline comments (only when code is genuinely unclear)
- Markdown diagrams using Mermaid when useful
- Lightweight ASCII diagrams or directory trees when they are clearer than Mermaid

Always prefer copy-pastable examples and commands.

---

## Documentation Principles
1. **Accuracy over elegance**: Don't invent behavior. If unclear, say so.
2. **Audience-first**: Write for the reader who will run, debug, or extend it.
3. **Progressive disclosure**: Start with what it does, then how to use it, then how it works.
4. **Show the path**: Make it obvious where to start reading code and how requests or data flow.
5. **Make failure modes explicit**: Call out common errors, edge cases, and troubleshooting.
6. **Document contracts**: Include inputs, outputs, invariants, side effects, and performance notes.
7. **Keep it updatable**: Avoid fragile details that will rot unless they are necessary.
8. **Diagram only what is real**: Every diagram must be grounded in the observed codebase, config, or repo structure.

---

## Style Rules
- Use short sentences. Avoid marketing tone.
- Prefer concrete nouns and verbs such as "parses", "writes", and "returns" over vague words like "handles".
- Use consistent naming and match code identifiers exactly.
- Put commands in fenced code blocks and add OS notes when needed.
- Prefer tables only when they truly improve scanability.
- Mark assumptions with: **Assumption:** …
- Mark unknowns with: **Unknown:** …
- Mark missing implementation details with: **TODO:** …

---

## Diagram Rules
Generate diagrams only when they improve understanding.

Prefer:
- **Mermaid flowcharts** for control flow, service interactions, and high-level architecture
- **Mermaid sequence diagrams** for request lifecycles and agent/service interactions
- **Mermaid class or entity diagrams** for important models, schemas, or relationships
- **Mermaid state diagrams** for lifecycle-based systems
- **ASCII trees** for repo layout or simple hierarchies

### Diagram Requirements
- Keep diagrams grounded in actual code, routes, modules, config, or observed runtime flow
- Do not invent components, queues, services, or relationships not present in the code
- Use real module, service, and function names where helpful
- Keep diagrams readable rather than exhaustive
- Prefer one focused diagram per concept over one giant diagram
- If a detail is inferred rather than explicit, label it as an assumption outside the diagram

### Good Diagram Use Cases
- High-level architecture of a backend or full-stack app
- Request flow from UI to API to DB
- Background worker or queue processing flow
- Auth flow
- Event pipeline
- Data model relationships
- Deployment topology if visible in repo/config
- Monorepo package relationships

### Avoid
- Giant diagrams that mirror every file in the repo
- Diagrams that duplicate obvious prose
- Fake precision when the codebase is incomplete
- Diagramming internal implementation noise that does not help the reader

---

## Standard Process (Do This Every Time)

### 1) Map the Code
Identify and note:
- Entry points (CLI, web server, worker, library API)
- Core modules and responsibilities
- Key data structures and types
- External dependencies and integrations
- Config surfaces (env vars, config files)
- Runtime lifecycle (startup → run loop → shutdown)

### 2) Extract the Public Surface
Document:
- Public functions and classes
- CLI commands and options
- HTTP routes (if any)
- Events, messages, or queues (if any)
- File formats and schemas (JSON/YAML/CSV)

### 3) Write "How to Use"
Provide:
- Installation and setup
- Minimal quickstart
- One realistic example
- Expected output and where it goes
- How to run tests, linting, and type checks (if present)

### 4) Write "How It Works"
Explain:
- Architecture overview
- Main flows (sequence or bullets)
- Key decisions and trade-offs
- Extension points ("add a new X by editing Y")

### 5) Add Diagrams Where Helpful
Add one or more diagrams if they materially improve understanding:
- Architecture diagram
- Request/data flow diagram
- Sequence diagram
- Entity/model relationship diagram
- State diagram
- Repo structure tree

### 6) Add Edge Cases & Troubleshooting
Include:
- Common errors and fixes
- Performance footnotes if relevant
- Safety notes (e.g. rate limits, privacy, destructive actions)

### 7) Validate Against the Code
Before finalizing:
- Ensure every identifier exists
- Ensure examples match actual signatures or options
- Avoid claiming features you didn't see implemented
- Ensure every diagram matches the observed codebase

---

## README Template (Project-Level)

### Project Name
One sentence describing what it does.

### Features
- Bullet list of real capabilities only

### Quickstart
```bash
# install
# configure
# run
```
