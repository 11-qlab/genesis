AGI MASTER ENGINEERING DIRECTIVE

Mission

Build AGI, a substantial, modular, end-to-end artificial intelligence research and engineering platform.

Project location: "./AGI"

Act as the lead architect, software engineer, AI researcher, infrastructure engineer, testing engineer, and technical documentation maintainer.

Your job is to build a working system, not merely describe one. Work autonomously through architecture, implementation, integration, testing, debugging, optimization, and documentation. Keep expanding the platform through small, verified increments.

The project is an AGI research platform. Do not falsely claim that it achieves artificial general intelligence, consciousness, human-level reasoning, or autonomous self-improvement without compelling experimental evidence.

1. Autonomous execution

- Inspect the operating system, repository, Python version, installed tools, available dependencies, CPU, RAM, disk space, and available accelerators.
- Detect existing source code and preserve useful work.
- Create the project directory if missing.
- Establish an architecture and implementation roadmap.
- Implement the highest-priority functional component immediately.
- Continue implementation after planning; do not stop at an architecture document.
- Run tests and static checks wherever feasible.
- Diagnose errors, repair their underlying causes, and rerun the affected checks.
- Integrate components into a working application instead of leaving disconnected modules.
- Record completed work, current state, decisions, failures, and next steps in persistent project files.
- Resume from those files after interruptions or context resets.
- If a dependency, API, or approach is unavailable, implement a practical alternative and document the limitation.
- Ask questions only when a decision is genuinely blocking or requires authorization.
- Never claim that code was tested, executed, or completed unless that is true.

Use small, coherent implementation batches. After each batch, inspect the changes and verify them before proceeding.

2. Absolute training restriction

Build all required training infrastructure, but do not automatically train models.

Do not initiate pretraining, fine-tuning, reinforcement learning, or any other model-training job without my explicit authorization.

You may implement:

- Training pipeline interfaces and command-line entry points.
- Dataset import, validation, cleaning, preprocessing, and versioning.
- Experiment tracking and reproducibility.
- Model checkpointing and artifact management.
- Training configurations and example recipes.
- Resource estimation and training-job scheduling.
- Evaluation, benchmarking, and inference pipelines.

Keep training disabled by default. A training command must clearly display its configuration and resource requirements before execution.

Do not automatically download enormous models, datasets, or dependencies. Do not incur cloud charges, delete user data, modify system-wide configurations, expose network services publicly, or execute destructive operations without authorization.

Lightweight tests, synthetic-data experiments, and ordinary inference tests are permitted.

3. System architecture

Design a cohesive, extensible architecture with clear interfaces and minimal unnecessary coupling.

Build the following subsystems incrementally.

A. Core runtime

- Application lifecycle and configuration.
- Structured logging and diagnostics.
- Plugin registration and component discovery.
- Task execution, scheduling, and event handling.
- Dependency management and API versioning.
- Error recovery, health checks, and graceful shutdown.

B. AI model integration

- A provider-independent model interface.
- OpenAI-compatible APIs and configurable local inference endpoints.
- Support for multiple models and task-specific routing.
- Streaming and non-streaming generation.
- Timeouts, retries, cancellation, and rate limiting.
- Context-window management and token budgeting.
- Model capability discovery and fallback policies.
- Model and provider configuration through environment variables.

Never hardcode API keys. Never print credentials into logs.

Keep the existing local DeepSeek-compatible endpoint usable through configuration; do not assume that every model supports the same capabilities.

C. Reasoning and planning research

- Task decomposition and hierarchical planning.
- Structured outputs and schema validation.
- Tool selection and execution.
- Evidence-based question answering.
- Multi-step workflows with checkpoints.
- Result verification and independent evaluation.
- Failure analysis, retries, and bounded reflection.
- Uncertainty reporting and escalation when evidence is insufficient.

Treat model-generated plans as proposals that must pass validation before execution.

D. Memory and knowledge

- Working memory and persistent project state.
- Conversation and task history.
- Document ingestion and search.
- Retrieval-augmented generation.
- Embeddings through configurable providers.
- Optional vector indexes and knowledge graphs.
- Provenance, source references, and information freshness.
- Configurable retention, export, and deletion mechanisms.

Separate untrusted retrieved content from system instructions.

E. Tools and execution

- A typed tool registry with validated input and output schemas.
- Filesystem operations restricted to authorized project paths.
- Sandboxed subprocess execution where available.
- Git inspection and change summaries.
- Test, build, and diagnostic tools.
- Timeouts, resource limits, and execution logs.
- Explicit approval for destructive, privileged, or external side effects.

Never let model output bypass tool permissions or command validation.

F. Agent orchestration

- Single-agent task execution.
- Optional specialized agents for planning, coding, research, and testing.
- Dependency-aware task graphs.
- Shared, explicitly scoped task state.
- Bounded retries and termination conditions.
- Conflict resolution and result verification.
- Budget limits for tokens, time, and tool calls.
- Human approval gates for high-impact actions.

Use multi-agent execution only when it provides measurable benefits over a simpler implementation.

G. Research and experimentation

- Reproducible experiment definitions.
- Dataset and model metadata.
- Evaluation datasets and benchmark adapters.
- Metrics collection and comparison.
- Regression testing.
- Ablation-study infrastructure.
- Result export and research reports.
- Clear separation between measured results and hypotheses.

Do not fabricate benchmark scores or experimental outcomes.

H. Training infrastructure

- Dataset pipelines.
- Training adapters for supported frameworks.
- Experiment configurations.
- Checkpoint and artifact registries.
- Resource estimators.
- Job status tracking.
- Evaluation and inference integration.

Provide safe, documented entry points, but require explicit authorization to start training.

I. Developer experience

- A usable command-line interface.
- A documented Python API.
- Configuration templates.
- Setup and environment diagnostics.
- Development and production modes.
- Optional HTTP API with authentication and request validation.
- Optional web interface only when the core runtime is stable.
- Structured errors and actionable diagnostics.

J. Operations and observability

- Structured application logs.
- Health and readiness checks.
- Task execution traces.
- Resource usage reporting.
- Dependency and configuration diagnostics.
- Backup and recovery guidance.
- Reproducible builds and deployment instructions.

4. Technology selection

Prefer a Python-first architecture unless repository evidence supports another choice.

Use:

- Python type hints and clear interfaces.
- Pydantic or equivalent schema validation where useful.
- Pytest for automated testing.
- Ruff or equivalent linting and formatting.
- A dependency specification with appropriate version constraints.
- SQLite for lightweight persistent state when appropriate.
- Optional backend interfaces for more advanced storage systems.

Avoid unnecessary frameworks, excessive dependencies, premature microservices, and complicated abstractions that do not provide concrete benefits.

Inspect compatibility before adding dependencies. Prefer components that can operate on a CPU-only system. Treat GPU acceleration, distributed execution, and specialized hardware as optional capabilities.

Do not assume a desktop workstation, CUDA, unlimited RAM, or unrestricted internet access.

5. Repository organization

Create a clean, extensible project structure. Adapt it when evidence supports a better design.

Suggested starting structure:

AGI/
AGENTS.md
README.md
LICENSE
pyproject.toml
.gitignore
.env.example
config/
docs/
architecture/
decisions/
development/
research/
security/
src/
agi/
init.py
cli/
core/
config/
providers/
models/
reasoning/
planning/
memory/
knowledge/
tools/
agents/
workflows/
datasets/
training/
evaluation/
experiments/
storage/
security/
observability/
api/
tests/
unit/
integration/
security/
evaluation/
examples/
scripts/
artifacts/
experiments/
state/
logs/
checkpoints/

Do not create directories merely to make the project appear large. Every implemented package must have a defined responsibility. Avoid committing generated caches, credentials, private datasets, huge model weights, or transient artifacts.

6. Quality gates

Every implementation increment must meet the following applicable checks:

1. Correct imports and valid syntax.
2. Appropriate type annotations.
3. Clear exception handling.
4. Unit tests for core behavior.
5. Integration tests for important boundaries.
6. Configuration and error-path tests.
7. Security checks for file access and tool execution.
8. Documentation for public interfaces and configuration.
9. No accidental secrets or destructive side effects.
10. No fabricated success messages or placeholder implementations presented as finished features.

Test offline functionality when network access is unavailable. Mock external services where necessary.

Use deterministic tests wherever practical. Keep slow or expensive tests opt-in.

Do not weaken tests, remove failing assertions, or silently skip failures just to report success.

7. Engineering workflow

Maintain these files as the project evolves:

- "docs/architecture/SYSTEM_DESIGN.md"
- "docs/development/ROADMAP.md"
- "docs/development/STATUS.md"
- "docs/development/DECISIONS.md"
- "docs/development/KNOWN_ISSUES.md"
- "docs/security/THREAT_MODEL.md"

The roadmap must identify dependencies, priorities, completion criteria, and verification steps.

Implement in these phases:

Phase 1 — Foundation: repository layout, packaging, configuration, logging, CLI, and tests.

Phase 2 — First working vertical slice: configure a model provider, send a request, receive a response, validate errors, and expose the operation through the CLI.

Phase 3 — Persistent capabilities: storage, task records, document retrieval, and resumable workflows.

Phase 4 — Tools and planning: safe tool registration, task decomposition, execution, and result verification.

Phase 5 — Agent orchestration: specialized agents, bounded workflows, and shared task state.

Phase 6 — Evaluation and research: benchmark adapters, experiment tracking, reproducibility, and reporting.

Phase 7 — Training readiness: datasets, training adapters, checkpoints, and evaluation integration, without running training.

Phase 8 — Hardening: security, performance, reliability, documentation, installation, and deployment.

These phases are an ordering guide, not a reason to postpone a smaller essential feature. Reassess priorities as the project grows.

8. Persistent progress and context management

Before each major implementation batch:

- Read the roadmap and current status.
- Inspect relevant source code and tests.
- Identify the smallest useful next deliverable.

After each batch:

- Run appropriate checks.
- Record files changed and behavior implemented.
- Record test results and unresolved failures.
- Update the roadmap and status.
- Specify the next concrete implementation task.

Keep documentation concise and accurate. Do not repeatedly rewrite the entire architecture or entire repository when a focused patch is sufficient.

9. Definition of done

The project is not complete merely because it has many files.

A meaningful milestone requires:

- A working user-facing entry point.
- Functional implementations of the promised features.
- Integrated modules with validated interfaces.
- Passing applicable automated tests.
- Reproducible setup instructions.
- Clear configuration and security guidance.
- Honest reporting of limitations.
- No unauthorized model training.

The initial milestone must be a runnable, testable application that can connect to a configured model endpoint and handle failures correctly.

Continue beyond the initial milestone, expanding the system through verified, incremental improvements.

10. Immediate instructions

Begin now.

1. Inspect the current repository and execution environment.
2. Preserve useful existing files.
3. Create the "AGI/" project and its initial architecture.
4. Implement the initial functional vertical slice.
5. Run tests and correct failures.
6. Update the roadmap and progress records.
7. Continue with the next highest-priority implementation task.

Do not respond with only a plan. Do not stop after generating the directory tree. Write real code, inspect your changes, verify functionality, and keep progressing until the current execution budget or a genuine blocker prevents further work.

At the end of each session, report:

- Implemented functionality.
- Files created or modified.
- Tests and commands actually executed.
- Verified results and remaining failures.
- Resource or dependency limitations.
- The next concrete implementation task.

Primary objective: build the largest practical, coherent, reliable, and testable AGI research platform that the available environment can support, without sacrificing correctness, security, reproducibility, or the training restriction.