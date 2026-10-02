# ⚡ Code2UML AI

> **Deterministic Spring Boot Architecture Visualizer & Privacy-Conscious Gemma AI Explainer**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python)](https://python.org)
[![Mermaid.js](https://img.shields.io/badge/Mermaid.js-10.x-ff3670.svg)](https://mermaid.js.org/)
[![Gemma AI](https://img.shields.io/badge/Gemma-2--9b--it-8e75ff.svg)](https://ai.google.dev/gemma)
[![Tests](https://img.shields.io/badge/Tests-14%20Passed-brightgreen.svg)]()

---

## 📌 Problem

Understanding medium-to-large Spring Boot codebases is time-consuming and cognitively demanding. Developers often spend hours tracing dependency injection graphs, tracking down REST endpoints across controllers, mapping JPA entity relationships, and documenting architecture diagrams manually. Furthermore, uploading proprietary enterprise source code to cloud LLMs violates security and privacy policies.

## 💡 Solution

**Code2UML AI** bridges deterministic static code analysis with private AI intelligence:
1. **100% Local Code Parsing**: Analyzes Java files locally on the server using AST and deterministic token parsing.
2. **Instant Mermaid Diagrams**: Automatically maps Controllers, Services, Repositories, Entities, and DTOs with constructor/field dependency flows, REST routes, and JPA entity management.
3. **Privacy-Focused Gemma Architecture Assistant**: The AI never reads raw source code. Only high-level structured architectural metadata is provided to Gemma, preventing code leakage while enabling natural language architectural questions.

---

## 🏗️ Architecture & How It Works

```
┌────────────────────────────────────────────────────────┐
│                   BROWSER / CLIENT                     │
│  - Drag & Drop ZIP Upload                              │
│  - Interactive Pan/Zoom Mermaid.js Architecture Viewer │
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
│     - Repository-to-Entity Mapping                     │
│  4. Mermaid Architecture Generator (Subgraphs & Flow)  │
│  5. Gemma AI Assistant (Google Gemini / OpenAI / Rule) │
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
* **Diagramming**: Mermaid.js (flowchart TD with layer subgraphs and custom component styling)
* **Frontend**: Vanilla JavaScript (ES6+), HTML5, Modern Dark CSS with responsive grid
* **AI Provider**: Gemma (`gemma-2-9b-it` / `gemma-2-27b-it` via Google AI Studio or OpenAI-compatible local/cloud endpoints like Ollama, vLLM, Groq)

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

## 🧪 Running Tests

Run the full automated test suite:
```powershell
$env:PYTHONPATH="C:\sem5\code2uml"
python -m pytest tests -v
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the web application UI |
| `GET` | `/api/health` | Backend status and AI configuration check |
| `POST` | `/api/analyze` | Accepts multipart ZIP upload, returns architecture JSON and Mermaid string |
| `POST` | `/api/analyze/sample` | Instantly analyzes the included sample Spring Boot project |
| `POST` | `/api/chat` | Receives `{ question, architecture }` and returns Gemma explanation |

---

## 📦 Sample Project Architecture

Included in `sample-project/`:
* `DemoApplication` (`@SpringBootApplication`)
* `UserController` (`@RestController`, `@RequestMapping("/api/users")`, 4 endpoints)
* `UserService` (Interface)
* `UserServiceImpl` (`@Service`, injects `UserRepository`)
* `UserRepository` (`@Repository`, `JpaRepository<User, Long>`)
* `User` (`@Entity`, `@Table`)
* `UserDTO` (Data Transfer Object)

---

## 🔮 Limitations & Future Work

* **Current Focus**: Tailored specifically for Java and Spring Boot ecosystems.
* **Future Work**:
  - Support for Maven multi-module monorepos (`pom.xml` aggregation).
  - Microservices communication detection via `WebClient` / `@FeignClient`.
  - Spring Cloud Gateway / Kafka topic producer & consumer architecture detection.
  - Interactive diagram-to-code jumping via IDE extensions.
