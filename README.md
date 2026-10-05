# ⚡ Code2UML AI

> **Deterministic Spring Boot Architecture Visualizer & Privacy-Conscious Gemma AI Explainer**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python)](https://python.org)
[![Mermaid.js](https://img.shields.io/badge/Mermaid.js-10.x-ff3670.svg)](https://mermaid.js.org/)
[![Gemma AI](https://img.shields.io/badge/Gemma-4--26b--a4b--it-8e75ff.svg)](https://ai.google.dev/gemma)
[![Tests](https://img.shields.io/badge/Tests-50%20Passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

---

## 📌 Problem

Understanding medium-to-large Spring Boot codebases is time-consuming and cognitively demanding. Developers often spend hours tracing dependency injection graphs, tracking down REST endpoints across controllers, mapping JPA entity relationships, and documenting architecture diagrams manually. Furthermore, uploading proprietary enterprise source code to cloud LLMs violates security and privacy policies.

## 💡 Solution

**Code2UML AI** bridges deterministic static code analysis with private AI intelligence:
1. **100% Local Code Parsing**: Analyzes Java files locally on the server using AST and deterministic token parsing.
2. **Instant Mermaid Diagrams**: Automatically maps Controllers, Services, Repositories, Entities, and DTOs with constructor/field dependency flows, REST routes, and JPA entity management.
3. **Dual Views**: Switch between **Architecture View** (layered subgraphs with optional 'uses' edges) and formal **UML Class Diagram** view (`classDiagram` notation with stereotypes, fields, methods, realization, and dependency notes).
4. **Architecture Observations Engine**: Rule-based anti-pattern detection highlighting direct entity exposure in controller endpoints, layer skipping, and unimplemented service interfaces.
5. **Privacy-Focused Gemma Architecture Assistant**: The AI never reads raw source code. Only high-level structured architectural metadata is provided to Gemma, preventing code leakage while enabling natural language architectural questions.

---

## 🏗️ Architecture & How It Works

```
┌────────────────────────────────────────────────────────┐
│                   BROWSER / CLIENT                     │
│  - Drag & Drop ZIP Upload                              │
│  - Interactive Pan/Zoom Mermaid.js Architecture Viewer │
│  - Architecture View vs UML Class View Switcher        │
│  - Structural vs Full ('uses') Diagram Edge Toggle     │
│  - REST Endpoints Catalog & Component Inspector        │
│  - Gemma Architecture Q&A Chat                         │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP Multipart / JSON
                            ▼
┌────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND                      │
│                                                        │
│  1. Safe ZIP Extraction (Zip-Slip & Bomb Protection)  │
│  2. Java AST & Regex Parser (javalang + fallback)      │
│  3. Spring Boot Architecture Analyzer                  │
│     - @RestController / @Controller                    │
│     - @Service / @Repository / @Entity / @Table        │
│     - Constructor & Field Injection Detection          │
│     - Endpoints (@GetMapping, @PostMapping, etc.)      │
│     - Repository-to-Entity Mapping & Deduplication     │
│     - Rule-based Architecture Observations Detector    │
│  4. Mermaid Generators (Architecture & UML Class)      │
│  5. Gemma AI Assistant (Google v1 Interactions API /   │
│     OpenAI-compatible / Deterministic Offline Engine) │
└────────────────────────────────────────────────────────┘
```

---

## 🛡️ Privacy Model

* **Local Static Analysis**: All `.java` files in the uploaded ZIP are extracted into an isolated temporary directory, parsed locally, and deleted immediately upon completion.
* **No Raw Code Upload**: Raw Java source code, business logic algorithms, and proprietary internal implementations are **never** transmitted to any external AI API.
* **Metadata-Only AI Context**: If Gemma AI Q&A is invoked, only structured architectural summaries (class names, layer types, endpoints, and dependency links) are provided to the model.
* **Offline Fallback Included**: When run completely without API keys, Code2UML AI uses a built-in deterministic architecture rules engine to answer questions locally.

---

## 💻 Tech Stack

* **Backend**: Python 3.12, FastAPI, Uvicorn, Pydantic v2
* **Analysis**: `javalang` AST + Deterministic Tokenizer Fallback (supports Java 8 through Java 21+)
* **Diagramming**: Mermaid.js 10.x (flowchart TD with layer subgraphs, UML class diagrams, custom component styling, and safe HTML entity rendering)
* **Frontend**: Vanilla JavaScript (ES6+), HTML5, Modern Dark CSS with responsive grid
* **AI Provider**: Google Gemma (`gemma-4-26b-a4b-it` via Google AI Studio / Google v1 Interactions API or OpenAI-compatible local/cloud endpoints like Ollama, vLLM, Groq)

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.10+
* Git (optional)

### 2. Installation
```powershell
cd c:\sem5\code2uml
pip install -r backend\requirements.txt
```

For browser end-to-end testing with Playwright:
```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium
```

### 3. Configure Environment Variables (Optional)
Copy `.env.example` to `.env`:
```powershell
cp backend\.env.example backend\.env
```
Edit `backend/.env`:
```env
# Option 1: Google AI Studio (Gemini & Gemma API)
# Get key from https://aistudio.google.com/ (Either GEMINI_API_KEY or GEMMA_API_KEY works)
GEMINI_API_KEY=your_api_key_here
# Gemma Model Identifier (Default: gemma-4-26b-a4b-it, or gemma-4-31b-it / gemma-2-9b-it)
GEMMA_MODEL=gemma-4-26b-a4b-it

# Option 2: Local Ollama / OpenAI-compatible endpoint
# GEMMA_API_URL=http://localhost:11434/v1/chat/completions
# GEMMA_MODEL=gemma2:9b
```
*(Note: If no API key is provided, the application will automatically run with the built-in deterministic architecture offline engine!)*

### 4. Run the Application
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

---

## ☁️ Deployment on Render

This repository includes a `render.yaml` blueprint and a `Dockerfile` for effortless deployment on [Render](https://render.com):

1. Fork or push this repository to GitHub.
2. In Render, select **New +** $\rightarrow$ **Blueprint** and connect your repository.
3. Add your `GEMINI_API_KEY` (optional) in Environment Variables.
4. Click **Apply** — Render automatically installs dependencies and starts Uvicorn.

---

## 🧪 Running Tests

Run the full test suite (35 unit, integration, robustness, fuzzing, benchmark, and browser tests):
```powershell
pytest -v
```

Tests include:
* **Golden Sample Fixture Analysis**: Asserts exact detection of 7 types (5 classes, 2 interfaces), 10 deduplicated relationships, 6 distinct packages, and 4 REST endpoints.
* **Mermaid & UML Generation**: Validates syntax, default vs full diagram strings, controller endpoint caps, and formal `classDiagram` notation.
* **Gemma Grounding**: Validates exact responses for database vendor queries, absent components, direct vs indirect dependencies, writeup queries, and privacy boundaries.
* **Browser Automation (Playwright)**: End-to-end testing of sample project loading, 5 toggles without syntax error bombs, UML tab switching, catalog formatting, chat Q&A, and error states (empty ZIP, corrupt ZIP, missing Java files).
* **Parser Robustness & Modern Java**: Verifies multi-encoding support (UTF-8 BOM, Latin-1 / CP-1252), comment/string fake annotation stripping, Java 14+ records, Lombok injection patterns, and multi-module layout test-directory pruning.
* **Fuzzing & Fault Recovery**: Validates graceful fallback recovery on corrupted Java sources without crashing.
* **Performance Benchmark**: Asserts that 200 Spring Boot files are parsed and mapped in < 4.0 seconds (typically ~1.5s).

---

## 📋 Supported Constructs

Code2UML AI supports a wide range of real-world Spring Boot architectural constructs, verified by automated test suites:

| Category | Supported & Tested Constructs |
|---|---|
| **Stereotypes & Roles** | `@SpringBootApplication`, `@RestController`, `@Controller`, `@Service`, `@Repository`, `@Component`, `@Configuration`, `@ControllerAdvice`, `@RestControllerAdvice`, `@FeignClient`, `@Mapper` |
| **Dependency Injections** | Constructor injection (`public Foo(Bar bar)`), Lombok `@RequiredArgsConstructor` / `@AllArgsConstructor` / `@Data` with `final` fields, Field injection (`@Autowired`, `@Inject`, `@Resource`), Setter injection (`@Autowired setBar(Bar bar)`) |
| **REST Endpoints** | `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping`, `@RequestMapping` (supports array paths `{"/v1", "/v2"}` and explicit `method = RequestMethod.*`) |
| **Persistence / Repositories** | `JpaRepository<T, ID>`, `CrudRepository<T, ID>`, `PagingAndSortingRepository<T, ID>`, `MongoRepository<T, ID>`, `@Entity`, `@Table(name = "...")`, `@Id`, `@GeneratedValue`, `@MappedSuperclass`, `@Embeddable`, `@Document` |
| **Java Language Features** | Standard classes, abstract classes, interfaces, Java 14+ `record` declarations, inner/nested static classes, multi-package architectures with identical class names |
| **Encodings & Resiliency** | UTF-8, UTF-8 with BOM (`utf-8-sig`), ISO-8859-1 (Latin-1) / Windows-1252 (`cp1252`), full comment/string constant isolation |

---

## ⚡ Performance & Scalability Benchmark

Code2UML AI static analysis is built purely in Python using AST traversals and compiled regex tokenizers with zero network latency or AI overhead:

* **Throughput**: >130 Java source files analyzed per second on standard consumer hardware.
* **Benchmark Test**: A 200-class multi-package Spring Boot project is parsed, analyzed, cross-referenced, and diagrammed in **~1.5 seconds** (enforced by automated CI threshold `< 4.0s`).

---

## 🔍 Known Limitations & Diagnostic Tracking

Code2UML AI embraces honest, transparent diagnostics:
* **Java-First Static Analysis**: AST analysis is focused on Java files (`.java`). Alternative JVM files (`.kt`, `.groovy`, `.scala`) in the archive are detected and recorded in the **Diagnostics Banner** as unsupported languages rather than silently dropped.
* **Size & DoS Caps**: To protect shared hosting and public endpoints, extraction is capped at:
  * Maximum 100MB uncompressed archive size
  * Maximum 2,000 files in ZIP archive
  * Maximum 1,000 `.java` files analyzed per run
  * Maximum 2MB per individual source file
* **Multi-Module Layouts**: Maven and Gradle multi-module root layouts are automatically discovered and traversed, while unit/integration test directories (`src/test`, `/test/`) are cleanly pruned from architectural diagrams.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the web application UI |
| `GET` | `/api/health` | Backend status and AI configuration check |
| `POST` | `/api/analyze` | Accepts multipart ZIP upload, returns architecture JSON, `mermaid`, `mermaid_full`, and `mermaid_uml` |
| `POST` | `/api/analyze/sample` | Instantly analyzes the included sample Spring Boot project |
| `POST` | `/api/chat` | Receives `{ question, architecture }` and returns Gemma explanation |

---

## 📦 Sample Golden Test Fixture

Included in `sample-project/`:
* `DemoApplication` (`@SpringBootApplication`, role `application`)
* `UserController` (`@RestController`, `@RequestMapping("/api/users")`, 4 endpoints: `GET /api/users`, `GET /api/users/{id}`, `POST /api/users`, `DELETE /api/users/{id}`)
* `UserService` (`interface`, role `service_interface`, 4 declared methods)
* `UserServiceImpl` (`@Service`, role `service`, implements `UserService`, injects `UserRepository`)
* `UserRepository` (`interface`, role `repository`, extends `JpaRepository<User, Long>`, manages `User`, declared query method `findByEmail`)
* `User` (`@Entity`, `@Table(name = "users")`, fields with `@Id`, `@GeneratedValue(strategy = GenerationType.IDENTITY)`)
* `UserDTO` (role `dto`, fields `name`, `email`)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — see the [LICENSE](LICENSE) file for details.

