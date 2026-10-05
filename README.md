# ⚡ Code2UML AI

> **Deterministic Spring Boot architecture visualizer with an optional Gemma-powered assistant.**
> The code determines the architecture. Gemma explains it.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-46E3B7?logo=render&logoColor=white)](https://code2uml.onrender.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Mermaid.js](https://img.shields.io/badge/Mermaid.js-10.x-ff3670.svg)](https://mermaid.js.org/)
[![Gemma](https://img.shields.io/badge/Gemma-open--weight-8e75ff.svg)](https://ai.google.dev/gemma)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/shraddhaa09/code2uml)

**Live demo:** [code2uml.onrender.com](https://code2uml.onrender.com/) · **Source:** [github.com/shraddhaa09/code2uml](https://github.com/shraddhaa09/code2uml)

> ⚠️ The hosted demo is a public deployment. **Use the built-in sample project and do not upload proprietary or sensitive source code.** For private code, run it locally (see [Quick Start](#quick-start)).

## Contents

- [Problem](#problem)
- [Solution](#solution)
- [Try it](#try-it)
- [Architecture](#architecture)
- [Privacy and data flow](#privacy-and-data-flow)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Running with local Gemma (Ollama)](#running-with-local-gemma-ollama)
- [Deployment on Render](#deployment-on-render)
- [Running tests](#running-tests)
- [Supported constructs](#supported-constructs)
- [Performance](#performance)
- [Known limitations](#known-limitations)
- [API endpoints](#api-endpoints)
- [Sample fixture](#sample-fixture)
- [Project layout](#project-layout)
- [Contributing](#contributing)
- [License](#license)

## Problem

Understanding a medium-to-large Spring Boot codebase is slow. Developers trace dependency-injection graphs by hand, hunt for REST endpoints across controllers, map JPA entities to repositories, and draw architecture diagrams manually. Many teams also cannot send proprietary source code to a hosted LLM, which rules out the obvious "paste it into a chatbot" shortcut.

## Solution

Code2UML AI extracts the architecture from the code with deterministic static analysis, and only then lets an optional model explain what was extracted.

1. **Deterministic parsing.** Java files are parsed with `javalang` (AST) and a regex/tokenizer fallback. No model is involved in extraction.
2. **Mermaid diagrams.** Controllers, services, repositories, entities and DTOs are mapped with constructor and field dependency flows, REST routes and JPA entity management.
3. **Two views.** A layered **Architecture View** (optional "uses" edges, plus a focus view on a single controller) and a formal **UML Class View** (`classDiagram` notation with stereotypes, fields, methods, realization and dependency notes).
4. **Architecture Observations.** Rule-based findings: entities exposed directly by controller endpoints, layer skipping, and service interfaces with no implementation.
5. **Analysis Coverage.** A diagnostics panel reports how many files were parsed by the AST, how many by the fallback, and which failed, so partial results are not presented as complete.
6. **Architecture Assistant.** A deterministic engine answers questions about endpoints, dependencies, request flow, entities and repositories, authentication and the database vendor, and says "not detected" when nothing is found. Every answer is labeled with the engine that produced it. With a Gemma key configured, free-form questions go to Gemma, which receives structured architecture metadata rather than source code.

## Try it

1. Open the [live demo](https://code2uml.onrender.com/) (or your local instance) and click **Try Sample Project**.
2. Read the **Architecture Observations** bar.
3. Open the **Endpoints** tab.
4. Click the suggested question **UserController → UserRepository?**
5. Ask: *"Is there an authentication component?"* The sample has none, so the assistant reports that nothing was detected in the analyzed files.
6. Use **Copy Mermaid** to export the diagram for your own docs.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                   BROWSER / CLIENT                     │
│  - Drag & Drop ZIP Upload                              │
│  - Interactive Pan/Zoom Mermaid.js Architecture Viewer │
│  - Architecture View vs UML Class View Switcher        │
│  - Full / Focus diagram scope, 'uses' edge toggle      │
│  - REST Endpoints Catalog & Component Inspector        │
│  - Analysis Coverage panel                             │
│  - Architecture Assistant chat                         │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP Multipart / JSON
                            ▼
┌────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND                      │
│                                                        │
│  1. Safe ZIP extraction (zip-slip & zip-bomb checks)   │
│  2. Java parsing (javalang AST + regex/tokenizer       │
│     fallback)                                          │
│  3. Spring Boot architecture analyzer                  │
│     - Stereotypes, injection, endpoints                │
│     - Repository-to-entity mapping & deduplication     │
│     - Rule-based architecture observations             │
│  4. Mermaid generators (architecture & UML class)      │
│  5. Assistant: deterministic engine, or Gemma          │
│     (Google AI Studio / OpenAI-compatible endpoint)   │
└────────────────────────────────────────────────────────┘
```

## Privacy and data flow

Code2UML AI is **privacy-conscious by design**, not private by default. Where your data goes depends on how you run it:

| Mode | Analysis runs on | Model runs on | What leaves your machine |
|---|---|---|---|
| Local + local Gemma (Ollama) | Your machine | Your machine | Nothing |
| Local + hosted Gemma API | Your machine | Provider (e.g. Google AI Studio) | The structured architecture summary, not source code |
| Public Render demo | The Render server | Provider, if a key is configured | The uploaded ZIP goes to the server; the summary goes to the provider |

How the implementation handles your files:

- **Extraction.** Uploaded ZIPs are extracted into an isolated temporary directory, parsed, and deleted after processing.
- **Source code is not sent to a model.** The assistant receives structured metadata (class names, layer roles, endpoints and dependency links), not Java source or method bodies. Class and endpoint names can still reveal structure, so use the local mode for sensitive projects.
- **Offline by default.** With no API key configured, nothing is sent to any AI provider and the deterministic engine answers locally.
- **No compliance claims.** This project makes no GDPR, SOC 2 or similar compliance claims.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2 |
| Analysis | `javalang` AST with a deterministic regex/tokenizer fallback |
| Diagramming | Mermaid.js 10.x (flowchart with layer subgraphs, UML class diagrams) |
| Frontend | Vanilla JavaScript (ES6+), HTML5, dark-theme CSS |
| AI | Google Gemma via [Google AI Studio](https://aistudio.google.com/), or any OpenAI-compatible endpoint (Ollama, vLLM, Groq) |

Gemma is an **open-weight** model family: the weights can be downloaded and run where you choose. Open-weight is not necessarily the same as open source, so check the license of the Gemma version you use. This project's own code is MIT-licensed.

## Quick start

### 1. Prerequisites

- Python 3.10 or newer
- Git

### 2. Install

```bash
git clone https://github.com/shraddhaa09/code2uml.git
cd code2uml
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
```

For browser end-to-end tests (Playwright):

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
```

### 3. Configure (optional)

The app works with no configuration, using the deterministic engine. To enable Gemma, copy the example file and edit it:

```bash
cp backend/.env.example backend/.env      # Windows: copy backend\.env.example backend\.env
```

```env
# Option 1: Google AI Studio (Gemini API key; Gemma models are served through it)
# Get a key at https://aistudio.google.com/  (GEMINI_API_KEY or GEMMA_API_KEY works)
GEMINI_API_KEY=your_api_key_here
# Pick a model identifier from the list in AI Studio. Default:
GEMMA_MODEL=gemma-4-26b-a4b-it

# Option 2: Local Ollama / OpenAI-compatible endpoint (see the Ollama section below)
# GEMMA_API_URL=http://localhost:11434/v1/chat/completions
# GEMMA_MODEL=gemma2:9b

# Optional: set to "hosted" on a public deployment to show the hosted-demo warning
# DEPLOYMENT_MODE=hosted
```

Never commit `.env` or any API key.

### 4. Run

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Running with local Gemma (Ollama)

This keeps both analysis and model inference on your machine.

1. Install [Ollama](https://ollama.com/).
2. Pull a Gemma model: `ollama pull gemma2:9b`
3. In `backend/.env`, set:
   ```env
   GEMMA_API_URL=http://localhost:11434/v1/chat/completions
   GEMMA_MODEL=gemma2:9b
   ```
4. Start the app as above and ask a free-form question. Answers should be labeled with the Gemma model name.

## Deployment on Render

The repository includes a `render.yaml` Blueprint and a `Dockerfile`.

1. Click **Deploy to Render** above, or fork the repo and choose **New + → Blueprint** in the [Render dashboard](https://dashboard.render.com/).
2. Set environment variables: `GEMINI_API_KEY` (optional), `GEMMA_MODEL`, and `DEPLOYMENT_MODE=hosted`.
3. Apply the Blueprint. The service exposes `/api/health` for health checks.

Free-tier Render services spin down when idle, so the first request after a quiet period can be slow. The hosted demo at [code2uml.onrender.com](https://code2uml.onrender.com/) runs on a paid instance. On Render, the app runs on the server and Gemma inference is an external API call; the app does not run the model itself.

## Running tests

```bash
pytest -v
```

The suite covers:

- **Golden sample.** Exact detection of 7 types (5 classes, 2 interfaces), 10 deduplicated relationships, 6 packages and 4 REST endpoints.
- **Mermaid and UML generation.** Syntax validity, default vs full diagrams, endpoint caps and `classDiagram` notation.
- **Assistant grounding.** Database vendor queries, absent components, direct vs indirect dependencies and privacy boundaries.
- **Browser automation (Playwright).** Sample loading, diagram toggles, UML tab switching, catalog formatting, chat Q&A and error states (empty ZIP, corrupt ZIP, no Java files).
- **Parser robustness.** UTF-8 BOM, Latin-1/CP-1252 encodings, fake annotations inside comments and strings, Java 14+ records, Lombok injection patterns and multi-module layouts.
- **Fuzzing and fault recovery.** Corrupted Java sources fall back gracefully without crashing.
- **Performance.** A 200-file project must be analyzed in under 4 seconds.

## Supported constructs

Verified by the automated tests:

| Category | Supported constructs |
|---|---|
| **Stereotypes and roles** | `@SpringBootApplication`, `@RestController`, `@Controller`, `@Service`, `@Repository`, `@Component`, `@Configuration`, `@ControllerAdvice`, `@RestControllerAdvice`, `@FeignClient`, `@Mapper` |
| **Dependency injection** | Constructor injection; Lombok `@RequiredArgsConstructor` / `@AllArgsConstructor` / `@Data` with `final` fields; field injection (`@Autowired`, `@Inject`, `@Resource`); setter injection |
| **REST endpoints** | `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping`, `@RequestMapping` (array paths and explicit `method = RequestMethod.*`) |
| **Persistence** | `JpaRepository`, `CrudRepository`, `PagingAndSortingRepository`, `MongoRepository`, `@Entity`, `@Table`, `@Id`, `@GeneratedValue`, `@MappedSuperclass`, `@Embeddable`, `@Document` |
| **Java language** | Classes, abstract classes, interfaces, Java 14+ `record` declarations, nested static classes, identical class names across packages |
| **Encodings** | UTF-8, UTF-8 with BOM, ISO-8859-1, Windows-1252; comments and string constants are isolated from annotation detection |

Anything not listed here is not claimed to be supported.

## Performance

Analysis is pure Python (AST traversal plus compiled regex tokenizers) with no network calls or model inference.

- On my development machine a 200-class multi-package project is parsed, analyzed, cross-referenced and diagrammed in about 1.5 seconds, with throughput above 130 files per second. A pytest threshold of 4.0 seconds guards against regressions.
- These numbers come from generated test projects, not large production repositories. Your results will vary with hardware and project shape.

## Known limitations

- **Java-first.** Kotlin, Groovy and Scala sources are detected and recorded in the diagnostics as unsupported, not silently dropped.
- **Static analysis limits.** Relationships created dynamically or indirectly (reflection, runtime configuration, some custom meta-annotations) can be missed.
- **Upload caps** (to protect shared hosting): 50MB upload, 100MB uncompressed, 2,000 files per archive, 1,000 `.java` files analyzed per run, 2MB per source file.
- **Multi-module projects.** Maven and Gradle multi-module layouts are traversed, but only files present in the uploaded archive are analyzed. Test directories (`src/test`) are excluded from diagrams.
- **Model answers can be wrong.** Gemma receives structured data, which narrows what it must infer, but grounding is a constraint, not a correctness guarantee. Each answer states which engine produced it.
- **Coverage is parse coverage.** "100% Deterministic Coverage" means every file in the archive was parsed deterministically. It does not mean every architectural relationship was found.

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the web application UI |
| `GET` | `/api/health` | Backend status and AI configuration check |
| `POST` | `/api/analyze` | Accepts a multipart ZIP upload, returns architecture JSON, `mermaid`, `mermaid_full` and `mermaid_uml` |
| `POST` | `/api/analyze/sample` | Analyzes the included sample Spring Boot project |
| `POST` | `/api/chat` | Receives `{ question, architecture }` and returns an answer labeled with its engine |

## Sample fixture

Included in `sample-project/`:

- `DemoApplication` (`@SpringBootApplication`)
- `UserController` (`@RestController`, `@RequestMapping("/api/users")`, 4 endpoints: `GET /api/users`, `GET /api/users/{id}`, `POST /api/users`, `DELETE /api/users/{id}`)
- `UserService` (interface, 4 declared methods)
- `UserServiceImpl` (`@Service`, implements `UserService`, injects `UserRepository`)
- `UserRepository` (extends `JpaRepository<User, Long>`, declares `findByEmail`)
- `User` (`@Entity`, `@Table(name = "users")`)
- `UserDTO` (fields `name`, `email`)

## Project layout

```
code2uml/
├── backend/            # FastAPI app, analyzer, Mermaid generators, assistant
├── sample-project/     # Golden sample Spring Boot fixture
├── tests/              # Unit, integration, fuzz, benchmark and browser tests
├── Dockerfile
├── render.yaml         # Render Blueprint
├── requirements-dev.txt
├── LICENSE
└── README.md
```

## Contributing

Issues and pull requests are welcome, including as part of Hacktoberfest.

1. Fork the repo and create a branch.
2. Add or update tests for any parser or analyzer change. Keep the golden sample passing.
3. Run `pytest -v` before opening a pull request.
4. Do not claim support for a construct in the README unless a test proves it.

## License

Released under the [MIT License](LICENSE).