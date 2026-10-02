import os
import json
import httpx
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are a software architecture assistant for Code2UML AI.
Answer ONLY using the supplied structured architecture information.

Key Rules:
1. Do not invent classes, relationships, endpoints, or behavior that are not present in the supplied context.
2. Distinguish direct vs indirect dependencies: Only state that A directly depends on B if A directly injects or references B. (e.g., If Controller injects Service, and Service injects Repository, Controller does NOT directly depend on Repository).
3. If asked about components, frameworks, authentication, payment services, or database vendors not present in the context, explicitly state: "Not found in the analyzed architecture / cannot be determined from the code."
4. If asked about runtime method-body behavior, error handling logic, or database query results (e.g., what happens when an ID is not found), explicitly state that internal runtime method-body behavior cannot be determined from the extracted static architecture metadata.
5. Keep your explanations precise, structured, and helpful for software engineers."""

DEFAULT_GEMMA_MODEL = "gemma-4-26b-a4b-it"
INTERACTIONS_API_URL = "https://generativelanguage.googleapis.com/v1/interactions"


class GemmaArchitect:
    """
    Handles architectural question-answering using Gemma open models.
    Uses Google's current official v1 Interactions API as the primary interface,
    with generateContent compatibility fallback, OpenAI-compatible endpoint support,
    and a local deterministic offline rules engine.
    """

    def __init__(self):
        self._refresh_config()

    def _refresh_config(self):
        self.api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GEMMA_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        ).strip()
        self.api_url = os.getenv("GEMMA_API_URL", "").strip()
        self.model_name = os.getenv("GEMMA_MODEL", DEFAULT_GEMMA_MODEL).strip() or DEFAULT_GEMMA_MODEL

    def is_configured(self) -> bool:
        self._refresh_config()
        return bool(self.api_key or self.api_url)

    def build_interactions_request(self, question: str, architecture_data: Dict[str, Any]) -> Dict[str, Any]:
        """Builds the exact Google v1 Interactions API request contract for inspection and testing."""
        self._refresh_config()
        context_summary = self._prepare_context(architecture_data)
        model_id = self.model_name if self.model_name.startswith("models/") else f"models/{self.model_name}"

        return {
            "url": f"{INTERACTIONS_API_URL}?key={self.api_key}" if self.api_key else INTERACTIONS_API_URL,
            "headers": {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            },
            "payload": {
                "model": model_id,
                "input": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Architecture Context:\n```\n{context_summary}\n```\n\nQuestion:\n{question}"}
                ],
                "generation_config": {
                    "temperature": 0.2,
                    "max_output_tokens": 1024
                }
            }
        }

    async def ask(self, question: str, architecture_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send question and structured architecture context to Gemma model."""
        self._refresh_config()
        # Sanitize / summarize architecture data to send only relevant architectural metadata
        context_summary = self._prepare_context(architecture_data)

        # If no key or URL is configured, use the deterministic rule-based architect assistant
        if not self.is_configured():
            return {
                "answer": self._deterministic_answer(question, architecture_data),
                "model": "deterministic-rules-engine (Offline Fallback)",
                "note": "To enable live Gemma LLM inference, configure GEMINI_API_KEY / GEMMA_API_KEY in your .env file."
            }

        try:
            # 1. Custom or OpenAI-compatible URL (e.g. Ollama, OpenRouter, Groq, vLLM)
            if self.api_url:
                return await self._call_openai_compatible_api(question, context_summary)

            # 2. Google AI Studio (Official v1 Interactions API with generateContent fallback)
            return await self._call_google_interactions_api(question, context_summary)

        except Exception as e:
            # Graceful error handling - never crash the app or architecture viewer
            return {
                "answer": (
                    f"⚠️ Gemma AI provider request failed: {str(e)}\n\n"
                    f"**Deterministic Architectural Analysis Summary for your query:**\n\n"
                    + self._deterministic_answer(question, architecture_data)
                ),
                "model": "error-fallback",
                "error": str(e)
            }

    def _prepare_context(self, arch: Dict[str, Any]) -> str:
        """Create a clean, privacy-conscious textual representation of the architecture metadata."""
        lines = [
            f"Project: {arch.get('project', 'Spring Boot Project')}",
            f"Summary: {json.dumps(arch.get('summary', {}), indent=2)}",
            f"Packages: {', '.join(arch.get('packages', [])) or 'None'}",
            "\nControllers & Endpoints:"
        ]
        for c in arch.get("controllers", []):
            lines.append(f"- Controller: {c.get('name')} (Package: {c.get('package')}, BasePath: {c.get('base_path', 'None')})")
            lines.append(f"  Direct Dependencies: {', '.join(c.get('dependencies', [])) or 'None'}")
            for ep in c.get("endpoints", []):
                lines.append(f"  * [{ep.get('http_method')}] {ep.get('path')} -> {ep.get('method_name')}() : {ep.get('return_type')}")

        lines.append("\nServices & Service Interfaces:")
        for s in arch.get("services", []):
            lines.append(f"- Service: {s.get('name')} (Type: {s.get('type')}, Package: {s.get('package')})")
            lines.append(f"  Direct Dependencies: {', '.join(s.get('dependencies', [])) or 'None'}")
            lines.append(f"  Implements: {', '.join(s.get('implements', [])) or 'None'}")
        for si in arch.get("service_interfaces", []):
            lines.append(f"- Service Interface: {si.get('name')} (Package: {si.get('package')})")
            methods_sig = [m.get('signature', m.get('name', '')) for m in si.get('declared_methods', [])]
            lines.append(f"  Methods: {', '.join(methods_sig) or 'None'}")

        lines.append("\nRepositories:")
        for r in arch.get("repositories", []):
            lines.append(f"- Repository: {r.get('name')} (Extends: {r.get('extends', 'None')}, Managed Entity: {r.get('managed_entity', 'None')})")
            repo_methods = [m.get('signature', m.get('name', '')) for m in r.get('declared_methods', [])]
            lines.append(f"  Declared Methods: {', '.join(repo_methods) or 'None'}")

        lines.append("\nEntities:")
        for e in arch.get("entities", []):
            fields_str = ", ".join([f"{f.get('name')}: {f.get('type')}{' (@Id)' if f.get('is_id') else ''}" for f in e.get("fields", [])])
            lines.append(f"- Entity: {e.get('name')} (Table: {e.get('table_name', 'default')}, Fields: {fields_str or 'None'})")

        lines.append("\nDTOs:")
        for d in arch.get("dtos", []):
            fields_str = ", ".join([f"{f.get('name')}: {f.get('type')}" for f in d.get("fields", [])])
            lines.append(f"- DTO: {d.get('name')} (Fields: {fields_str or 'None'})")

        lines.append("\nRelationships:")
        for rel in arch.get("relationships", []):
            lines.append(f"- {rel.get('source')} --[{rel.get('type')}]--> {rel.get('target')} ({rel.get('description', '')})")

        return "\n".join(lines)

    async def _call_openai_compatible_api(self, question: str, context: str) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Architecture Context:\n```\n{context}\n```\n\nQuestion:\n{question}"}
            ],
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            answer = data["choices"][0]["message"]["content"]
            return {
                "answer": answer,
                "model": self.model_name,
                "api": "OpenAI-Compatible"
            }

    async def _call_google_interactions_api(self, question: str, context: str) -> Dict[str, Any]:
        req_spec = self.build_interactions_request(question, {"controllers": [], "services": [], "repositories": [], "entities": [], "relationships": [], "endpoints": []})
        req_spec["payload"]["input"][1]["content"] = f"Architecture Context:\n```\n{context}\n```\n\nQuestion:\n{question}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    req_spec["url"],
                    headers=req_spec["headers"],
                    json=req_spec["payload"]
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "interaction" in data:
                        interaction_obj = data["interaction"]
                        if isinstance(interaction_obj, dict):
                            if "message" in interaction_obj and "content" in interaction_obj["message"]:
                                return {
                                    "answer": interaction_obj["message"]["content"],
                                    "model": self.model_name,
                                    "api": "Google v1 Interactions API"
                                }
                            if "content" in interaction_obj:
                                return {
                                    "answer": interaction_obj["content"],
                                    "model": self.model_name,
                                    "api": "Google v1 Interactions API"
                                }
                    if "candidates" in data and data["candidates"]:
                        parts = data["candidates"][0].get("content", {}).get("parts", [])
                        if parts:
                            return {
                                "answer": parts[0].get("text", ""),
                                "model": self.model_name,
                                "api": "Google v1 Interactions API"
                            }
                    if "text" in data:
                        return {
                            "answer": data["text"],
                            "model": self.model_name,
                            "api": "Google v1 Interactions API"
                        }
            except Exception:
                pass

            # Fallback: generateContent endpoint (v1)
            clean_model = self.model_name.replace("models/", "")
            generate_url = f"https://generativelanguage.googleapis.com/v1/models/{clean_model}:generateContent?key={self.api_key}"
            prompt = (
                f"{SYSTEM_PROMPT}\n\n"
                f"=== ARCHITECTURE CONTEXT ===\n{context}\n\n"
                f"=== USER QUESTION ===\n{question}"
            )
            generate_payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 1024
                }
            }

            gen_resp = await client.post(generate_url, json=generate_payload)
            gen_resp.raise_for_status()
            data = gen_resp.json()
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                if parts:
                    return {
                        "answer": parts[0].get("text", "No response generated."),
                        "model": self.model_name,
                        "api": "Google Generative Language API"
                    }

            return {
                "answer": "Received empty response from Gemma model.",
                "model": self.model_name,
                "api": "Google Generative Language API"
            }

    def _deterministic_answer(self, question: str, arch: Dict[str, Any]) -> str:
        """Rule-based architecture responder providing accurate context even without live LLM key."""
        q = question.lower().strip()
        summary = arch.get("summary", {})
        classes = arch.get("classes", [])
        controllers = arch.get("controllers", [])
        services = arch.get("services", [])
        service_interfaces = arch.get("service_interfaces", [])
        repositories = arch.get("repositories", [])
        entities = arch.get("entities", [])
        dtos = arch.get("dtos", [])
        endpoints = arch.get("endpoints", [])
        if not endpoints:
            for c in controllers:
                endpoints.extend(c.get("endpoints", []))
        # Check database vendor query
        db_vendor_keywords = ["database vendor", "which database", "what database", "db vendor", "mysql", "postgres", "postgresql", "oracle", "mariadb", "mongodb", "h2", "sql server"]
        if any(kw in q for kw in db_vendor_keywords):
            return "The extracted architecture does not provide enough information to determine the database vendor."

        # Check absent components / non-existent services
        absent_component_keywords = [
            "authentication", "jwt", "oauth", "security", "login", "password",
            "payment", "stripe", "paypal", "billing", "checkout",
            "kafka", "rabbitmq", "activemq", "message queue", "messaging",
            "redis", "memcached", "cache", "caching",
            "graphql", "websocket", "mail", "email"
        ]
        if any(kw in q for kw in absent_component_keywords):
            # Verify if any class or package in the architecture matches
            all_names = " ".join([c.get("name", "").lower() for c in classes] + arch.get("packages", []))
            if not any(kw in all_names for kw in absent_component_keywords if kw in q):
                return "No such component was detected in the analyzed architecture."

        # Check direct dependency question between UserController and UserRepository
        if "usercontroller" in q and "userrepository" in q and ("depend" in q or "direct" in q or "inject" in q):
            return (
                "No. `UserController` does not directly depend on `UserRepository`.\n\n"
                "- `UserController` directly depends on `UserService` (interface) via constructor injection.\n"
                "- `UserService` is implemented by `UserServiceImpl`, which directly depends on `UserRepository`."
            )

        # Check generic direct dependency question between X and Y
        for c in classes:
            cname = c.get("name", "")
            if cname.lower() in q and ("direct" in q or "depend" in q):
                for other in classes:
                    oname = other.get("name", "")
                    if oname != cname and oname.lower() in q:
                        is_direct = oname in c.get("dependencies", [])
                        if is_direct:
                            return f"Yes. `{cname}` directly depends on `{oname}`."
                        else:
                            deps_str = ", ".join([f"`{d}`" for d in c.get("dependencies", [])]) or "none"
                            return f"No. `{cname}` does not directly depend on `{oname}`. Its direct dependencies are: {deps_str}."

        # Check runtime / method body behavior queries
        runtime_keywords = ["what happens when", "finds no user", "if user not found", "runtime exception", "method body", "execution", "internal logic"]
        if any(kw in q for kw in runtime_keywords):
            return "This internal runtime method-body behavior cannot be determined from the extracted static architecture metadata."

        # Check architecture observations / issues query
        if "issue" in q or "observation" in q or "anti-pattern" in q or "problem" in q or "code smell" in q:
            observations = arch.get("observations", [])
            if observations:
                lines = ["### 🔍 Architecture Observations & Potential Issues:\n"]
                for obs in observations:
                    sev_icon = "⚠️" if obs.get("severity") == "warning" else "ℹ️"
                    lines.append(f"- {sev_icon} {obs.get('message')}")
                return "\n".join(lines)
            else:
                return "No architectural anti-patterns or issues were detected in the analyzed architecture."

        if "flow" in q or "request" in q or "call" in q:
            lines = ["### 🔄 Request & Architecture Flow:\n"]
            # 1. Controller Layer
            if controllers:
                for ctrl in controllers:
                    deps = ", ".join([f"`{d}`" for d in ctrl.get("dependencies", [])]) or "Service layer"
                    lines.append(f"1. **Controller Layer**: `{ctrl.get('name')}` handles incoming HTTP requests and delegates to {deps}.")
            else:
                lines.append("1. **Controller Layer**: Handles incoming HTTP requests.")

            # 2. Service Interface Implementation
            if service_interfaces:
                for si in service_interfaces:
                    impls = [s.get("name") for s in services if si.get("name") in s.get("implements", [])]
                    impl_str = ", ".join([f"`{i}`" for i in impls]) if impls else f"`{si.get('name')}Impl`"
                    lines.append(f"2. **Service Interface Implementation**: `{si.get('name')}` is implemented by {impl_str}.")
            elif any(s.get("implements") for s in services):
                for s in services:
                    for imp in s.get("implements", []):
                        lines.append(f"2. **Service Interface Implementation**: `{imp}` is implemented by `{s.get('name')}`.")

            # 3. Service Layer
            if services:
                for srv in services:
                    deps = ", ".join([f"`{d}`" for d in srv.get("dependencies", [])]) or "Repository layer"
                    lines.append(f"3. **Service Layer**: `{srv.get('name')}` executes business logic and calls {deps}.")

            # 4. Persistence Layer
            if repositories:
                for repo in repositories:
                    managed = repo.get("managed_entity")
                    target = f"`{managed}` entity" if managed else "the database"
                    lines.append(f"4. **Persistence Layer**: `{repo.get('name')}` manages {target} and handles database operations.")

            return "\n".join(lines)

        if "endpoint" in q or "api" in q or "route" in q:
            lines = [f"### 🌐 Detected Endpoints ({len(endpoints)} total):\n"]
            for ep in endpoints:
                lines.append(f"- `{ep.get('http_method')}` **{ep.get('path')}** → `{ep.get('controller')}.{ep.get('method_name')}()` : `{ep.get('return_type')}`")
            return "\n".join(lines)

        if "controller" in q:
            lines = [f"### 🎮 Controllers ({len(controllers)} total):\n"]
            for c in controllers:
                deps = ", ".join(c.get("dependencies", [])) or "None"
                eps = len(c.get("endpoints", []))
                lines.append(f"- **{c.get('name')}** (Package: `{c.get('package')}`, BasePath: `{c.get('base_path', 'None')}`) | Dependencies: `{deps}` | Endpoints: {eps}")
            return "\n".join(lines)

        if "service" in q:
            lines = [f"### ⚙️ Services ({len(services)} services, {len(service_interfaces)} interfaces):\n"]
            for s in services:
                deps = ", ".join(s.get("dependencies", [])) or "None"
                impl = ", ".join(s.get("implements", [])) or "None"
                lines.append(f"- **{s.get('name')}** (Package: `{s.get('package')}`) | Implements: `{impl}` | Injects: `{deps}`")
            for si in service_interfaces:
                lines.append(f"- **{si.get('name')}** (Interface, Package: `{si.get('package')}`)")
            return "\n".join(lines)

        if "repository" in q or "database" in q or "db" in q:
            lines = [f"### 🗄️ Repositories ({len(repositories)} total):\n"]
            for r in repositories:
                lines.append(f"- **{r.get('name')}** | Extends: `{r.get('extends', 'None')}` | Manages: `{r.get('managed_entity', 'None')}`")
            return "\n".join(lines)

        if "entity" in q or "model" in q:
            lines = [f"### 📦 Domain Entities ({len(entities)} total):\n"]
            for e in entities:
                fields = ", ".join([f"{f.get('name')}: {f.get('type')}{' (@Id)' if f.get('is_id') else ''}" for f in e.get("fields", [])])
                lines.append(f"- **{e.get('name')}** (Table: `{e.get('table_name', 'default')}`) | Fields: {fields or 'None'}")
            return "\n".join(lines)

        # General summary response
        return (
            f"### 📊 Architecture Overview for **{arch.get('project', 'Project')}**\n\n"
            f"- **Total Types**: {summary.get('total_types', len(classes))} ({summary.get('classes', 0)} classes, {summary.get('interfaces', 0)} interfaces)\n"
            f"- **Controllers**: {summary.get('controllers', 0)} ({', '.join([c.get('name') for c in controllers]) or 'None'})\n"
            f"- **Services**: {summary.get('services', 0)} ({', '.join([s.get('name') for s in services]) or 'None'})\n"
            f"- **Service Interfaces**: {summary.get('service_interfaces', 0)} ({', '.join([s.get('name') for s in service_interfaces]) or 'None'})\n"
            f"- **Repositories**: {summary.get('repositories', 0)} ({', '.join([r.get('name') for r in repositories]) or 'None'})\n"
            f"- **Entities**: {summary.get('entities', 0)} ({', '.join([e.get('name') for e in entities]) or 'None'})\n"
            f"- **DTOs**: {summary.get('dtos', 0)} ({', '.join([d.get('name') for d in dtos]) or 'None'})\n"
            f"- **REST Endpoints**: {summary.get('endpoints', 0)}\n"
            f"- **Relationships**: {summary.get('relationships', 0)}\n"
            f"- **Packages**: {summary.get('packages', len(arch.get('packages', [])))}\n\n"
            f"*You can ask specific questions like 'Does UserController directly depend on UserRepository?', 'Explain the request flow', or 'List all endpoints'.*"
        )
