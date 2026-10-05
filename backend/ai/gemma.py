import os
import json
import re
import httpx
from typing import Dict, Any, List, Optional, Set, Tuple
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are a software architecture assistant for Code2UML AI.
Answer ONLY using the supplied structured architecture information.

Key Rules:
1. Do not invent classes, relationships, endpoints, or behavior that are not present in the supplied context.
2. Distinguish direct vs indirect dependencies: Only state that A directly depends on B if A directly injects or references B. (e.g., If Controller injects Service, and Service injects Repository, Controller does NOT directly depend on Repository).
3. If asked about components, frameworks, authentication, payment services, or database vendors not present in the context, explicitly state: "Not found in the analyzed architecture / cannot be determined from the code."
4. If asked about runtime method-body behavior, error handling logic, or database query results (e.g., what happens when an ID is not found), explicitly state that internal runtime method-body behavior cannot be determined from the extracted static architecture metadata.
5. If any class is not found in the extracted architecture, explicitly state that it does not exist in the analyzed files.
6. Keep your explanations precise, structured, and helpful for software engineers."""

DEFAULT_GEMMA_MODEL = "gemma-4-26b-a4b-it"
INTERACTIONS_API_URL = "https://generativelanguage.googleapis.com/v1/interactions"


def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes basic Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


class GemmaArchitect:
    """
    Handles architectural question-answering using Gemma open models.
    Uses Google's official v1 Interactions API as the primary interface,
    with generateContent compatibility fallback, OpenAI-compatible endpoint support,
    and an explicit deterministic intent routing rules engine.
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
        raw_url = (
            os.getenv("GEMMA_API_URL")
            or os.getenv("OLLAMA_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or ""
        ).strip()
        
        # Normalize local Ollama / OpenAI-compatible endpoint URL
        if raw_url:
            raw_url = raw_url.rstrip("/")
            if raw_url.endswith(":11434"):
                raw_url += "/v1/chat/completions"
            elif raw_url.endswith("/v1"):
                raw_url += "/chat/completions"
        self.api_url = raw_url
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
        """Send question and structured architecture context to Gemma model with deterministic fallback & post-check."""
        self._refresh_config()
        context_summary = self._prepare_context(architecture_data)

        # If no key or URL is configured, use the deterministic rule-based architect assistant
        if not self.is_configured():
            return {
                "answer": self._deterministic_answer(question, architecture_data),
                "model": "Deterministic engine",
                "note": "To enable live Gemma LLM inference, configure GEMINI_API_KEY in your .env file."
            }

        try:
            # 1. Custom or OpenAI-compatible URL (e.g. Ollama, OpenRouter, Groq, vLLM)
            if self.api_url:
                res = await self._call_openai_compatible_api(question, context_summary)
            else:
                # 2. Google AI Studio (Official v1 Interactions API with generateContent fallback)
                res = await self._call_google_interactions_api(question, context_summary)

            # Post-check validation: check if answer mentions classes not in architecture
            answer_text = res.get("answer", "")
            verified_answer = self._validate_and_post_check_answer(answer_text, architecture_data)
            res["answer"] = verified_answer
            res["model"] = f"Gemma ({self.model_name})"
            return res

        except Exception as e:
            # Graceful error handling - never crash the app or architecture viewer
            return {
                "answer": self._deterministic_answer(question, architecture_data),
                "model": "Deterministic engine",
                "error": str(e)
            }

    def _validate_and_post_check_answer(self, answer: str, arch: Dict[str, Any]) -> str:
        """Post-check model output: any class name in the answer that does not exist gets an inline warning."""
        all_class_names = {c.get("name") for c in arch.get("classes", []) if c.get("name")}
        
        # Ignored standard language keywords & types
        ignored = {
            "String", "Long", "Integer", "Double", "Boolean", "List", "Set", "Map", "Optional",
            "Void", "Object", "Class", "Spring", "SpringBoot", "Controller", "Service", "Repository",
            "Entity", "DTO", "Java", "PostgreSQL", "MySQL", "H2", "Oracle", "MongoDB", "MariaDB",
            "REST", "HTTP", "JSON", "GET", "POST", "PUT", "DELETE", "PATCH", "JPA", "Hibernate",
            "Architecture", "Assistant", "Gemma", "Code2UML", "Table", "Id", "RequestMapping"
        }

        # Find potential class names (PascalCase words with length >= 4)
        tokens = set(re.findall(r'\b[A-Z][a-zA-Z0-9_]{3,}\b', answer))
        hallucinations = []

        for token in tokens:
            if token in ignored or token in all_class_names:
                continue
            # Check if token is a plural or suffix variation
            if token.endswith("s") and token[:-1] in all_class_names:
                continue
            if token.endswith("es") and token[:-2] in all_class_names:
                continue
            # If it ends with Controller, Service, Repository, Entity, DTO, Request, Response but not present:
            if any(token.endswith(suffix) for suffix in ["Controller", "Service", "ServiceImpl", "Repository", "Entity", "DTO", "Request", "Response", "Filter", "Config"]):
                hallucinations.append(token)

        if hallucinations:
            warnings_str = ", ".join([f"`{h}`" for h in sorted(list(set(hallucinations)))])
            return answer + f"\n\n> ⚠️ **Verification Note**: Class(es) {warnings_str} mentioned in this response were not found in the extracted project architecture."
        return answer

    def _prepare_context(self, arch: Dict[str, Any]) -> str:
        """Create a clean, privacy-conscious textual representation of the architecture metadata."""
        diag = arch.get("diagnostics", {})
        db_info = arch.get("database_info", {})
        auth_info = arch.get("auth_info", {})

        lines = [
            f"Project: {arch.get('project', 'Spring Boot Project')}",
            f"Summary: {json.dumps(arch.get('summary', {}), indent=2)}",
            f"Diagnostics: Total files={diag.get('total_files_discovered', 0)}, AST parsed={diag.get('parsed_ast_count', 0)}, Fallback parsed={diag.get('parsed_fallback_count', 0)}, Failed={diag.get('failed_count', 0)}, Coverage={diag.get('coverage_percentage', 100.0)}%",
            f"Database Detected: {db_info.get('vendor', 'Unknown')} (Evidence: {', '.join(db_info.get('evidence', [])) or 'None'})",
            f"Authentication Detected: {auth_info.get('detected', False)} (Components: {', '.join(auth_info.get('components', [])) or 'None'})",
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
        headers = {"Content-Type": "application/json"}
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
            return {"answer": answer, "model": self.model_name, "api": "OpenAI-Compatible"}

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
                                return {"answer": interaction_obj["message"]["content"], "model": self.model_name, "api": "Google v1 Interactions API"}
                            if "content" in interaction_obj:
                                return {"answer": interaction_obj["content"], "model": self.model_name, "api": "Google v1 Interactions API"}
                    if "candidates" in data and data["candidates"]:
                        parts = data["candidates"][0].get("content", {}).get("parts", [])
                        if parts:
                            return {"answer": parts[0].get("text", ""), "model": self.model_name, "api": "Google v1 Interactions API"}
                    if "text" in data:
                        return {"answer": data["text"], "model": self.model_name, "api": "Google v1 Interactions API"}
            except Exception:
                pass

            # Fallback: generateContent endpoint (v1)
            clean_model = self.model_name.replace("models/", "")
            generate_url = f"https://generativelanguage.googleapis.com/v1/models/{clean_model}:generateContent?key={self.api_key}"
            prompt = f"{SYSTEM_PROMPT}\n\n=== ARCHITECTURE CONTEXT ===\n{context}\n\n=== USER QUESTION ===\n{question}"
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
                    return {"answer": parts[0].get("text", "No response generated."), "model": self.model_name, "api": "Google Generative Language API"}

            return {"answer": "Received empty response from Gemma model.", "model": self.model_name, "api": "Google Generative Language API"}

    def _deterministic_answer(self, question: str, arch: Dict[str, Any]) -> str:
        """
        Explicit Intent Routing Engine.
        Answers all questions deterministically using strictly the extracted architecture metadata.
        """
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
        relationships = arch.get("relationships", [])
        db_info = arch.get("database_info", {})
        auth_info = arch.get("auth_info", {})

        if not classes:
            classes = list(controllers) + list(services) + list(service_interfaces) + list(repositories) + list(entities) + list(dtos)

        class_name_map = {c["name"].lower(): c["name"] for c in classes if "name" in c}
        all_class_names = [c["name"] for c in classes if "name" in c]

        def resolve_class_name(query_term: str) -> Tuple[Optional[str], Optional[str]]:
            """Resolves a class name using exact match, case-insensitive, or closest fuzzy match."""
            clean = query_term.strip("`'\" ,.?")
            clean_lower = clean.lower()
            if clean_lower in class_name_map:
                return class_name_map[clean_lower], None
            
            # Fuzzy match
            candidates = []
            for name in all_class_names:
                dist = levenshtein_distance(clean_lower, name.lower())
                if dist <= 3 or clean_lower in name.lower() or name.lower() in clean_lower:
                    candidates.append((dist, name))
            if candidates:
                candidates.sort(key=lambda x: x[0])
                return None, candidates[0][1]
            return None, None

        ignored_query_tokens = {
            "what", "which", "where", "when", "why", "how", "does", "do", "did", "is", "are", "was", "were",
            "can", "could", "should", "would", "list", "show", "explain", "tell", "who", "give", "find",
            "describe", "check", "get", "post", "put", "delete", "patch", "options", "head", "the", "this",
            "that", "these", "those", "all", "any", "some", "every", "no", "not", "yes", "java", "spring",
            "boot", "framework", "project", "database", "vendor", "authentication", "security", "entities",
            "entity", "repositories", "repository", "services", "service", "controllers", "controller",
            "endpoints", "endpoint", "packages", "package", "types", "type", "classes", "class",
            "interfaces", "interface", "methods", "method", "fields", "field", "models", "model",
            "components", "component", "filters", "filter", "handlers", "handler", "application", "app",
            "flow", "call", "calls", "hierarchy", "code", "file", "files", "overall", "datasource",
            "api", "rest", "http", "json", "sql", "jwt", "id", "url", "uri", "jpa", "dto", "dtos", "crud", "rdbms", "db"
        }

        # ----------------------------------------------------------------------
        # Fast-path Intent: Runtime / Internal Method-Body Query
        # ----------------------------------------------------------------------
        runtime_keywords = ["what happens when", "finds no user", "if user not found", "runtime exception", "method body", "execution", "internal logic", "finds no"]
        if any(kw in q for kw in runtime_keywords):
            return "This internal runtime method-body behavior cannot be determined from the extracted static architecture metadata.\n\n*Based on analyzed files.*"

        # Extract referenced classes in question
        extracted_classes_in_query: List[str] = []
        missing_classes_in_query: List[Tuple[str, Optional[str]]] = []

        # Find candidate PascalCase tokens in question
        words = re.findall(r'\b[A-Za-z0-9_]+\b', question)
        for w in words:
            if len(w) >= 3 and w.lower() not in ignored_query_tokens:
                exact, closest = resolve_class_name(w)
                if exact and exact not in extracted_classes_in_query:
                    extracted_classes_in_query.append(exact)
                elif not exact and closest and (w[0].isupper() or any(w.lower().endswith(s) for s in ["service", "controller", "repository", "entity", "dto", "repo", "impl", "gateway"])):
                    missing_classes_in_query.append((w, closest))
                elif not exact and any(w.lower().endswith(s) for s in ["controller", "service", "repository", "entity", "dto", "repo", "impl", "gateway"]):
                    missing_classes_in_query.append((w, None))

        # If question is asking about an absent feature or component
        if "payment" in q and not any("payment" in c.lower() for c in all_class_names):
            return "No such component was detected in the analyzed architecture.\n\n*Based on analyzed files.*"

        # Check for non-existent class error
        if missing_classes_in_query and not extracted_classes_in_query:
            missing_tokens = []
            for m_name, sug in missing_classes_in_query:
                if sug:
                    missing_tokens.append(f"Class `{m_name}` was not found in the analyzed architecture. Did you mean `{sug}`?")
                else:
                    missing_tokens.append(f"Class `{m_name}` was not found in the analyzed architecture.")
            return "\n\n".join(missing_tokens) + "\n\n*Based on analyzed files.*"

        # ----------------------------------------------------------------------
        # Intent 1: Greeting
        # ----------------------------------------------------------------------
        greeting_words = ["hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"]
        if q in greeting_words or any(q.startswith(g) for g in ["hello", "hi ", "hey "]):
            return (
                f"Hello! I'm your Spring Boot architecture assistant for **{arch.get('project', 'your project')}**.\n\n"
                f"You can ask me about request flows, dependency chains, endpoints, database configuration, authentication, or specific component interactions.\n\n"
                f"*Based on analyzed files: {summary.get('total_types', len(classes))} types across {summary.get('packages', len(arch.get('packages', [])))} packages.*"
            )

        # ----------------------------------------------------------------------
        # Intent 2: Help
        # ----------------------------------------------------------------------
        if q in ["help", "what can you do", "help me", "commands", "how to use"]:
            sample_ctrl = controllers[0].get("name", "UserController") if controllers else "Controller"
            sample_srv = services[0].get("name", "UserService") if services else "Service"
            sample_repo = repositories[0].get("name", "UserRepository") if repositories else "Repository"
            return (
                f"### 💡 How to explore the architecture of **{arch.get('project', 'your project')}**:\n\n"
                f"You can ask natural questions like:\n"
                f"1. **Request Flow**: `Explain the request flow for {sample_ctrl}`\n"
                f"2. **Dependency Check**: `Does {sample_ctrl} depend on {sample_repo}?`\n"
                f"3. **Endpoints Catalog**: `List all REST endpoints in {sample_ctrl}`\n"
                f"4. **Database & Auth**: `Which database vendor is used?` or `Is there an authentication component?`\n"
                f"5. **Implementers**: `Who implements {sample_srv}?`\n"
                f"6. **Entities & Repositories**: `What database entities and repositories are present?`\n\n"
                f"*Based on analyzed files.*"
            )

        # ----------------------------------------------------------------------
        # Intent 3: Entities & Repositories list
        # (Must take precedence before generic database vendor check!)
        # ----------------------------------------------------------------------
        if ("entit" in q and "repositor" in q) or ("database entities" in q) or ("entities and repositories" in q):
            lines = [f"### 📦 Database Entities & Repositories ({len(entities)} Entities, {len(repositories)} Repositories):\n"]
            evidence_files = []
            
            lines.append("#### 📦 Domain Entities:")
            if entities:
                for e in entities:
                    evidence_files.append(e.get("file", f"{e.get('name')}.java"))
                    fields = ", ".join([f"{f.get('name')}: {f.get('type')}{' (@Id)' if f.get('is_id') else ''}" for f in e.get("fields", [])])
                    lines.append(f"- **{e.get('name')}** (Table: `{e.get('table_name', 'default')}`) | Fields: {fields or 'None'}")
            else:
                lines.append("- *No domain entities detected.*")

            lines.append("\n#### 🗄️ Repositories:")
            if repositories:
                for r in repositories:
                    evidence_files.append(r.get("file", f"{r.get('name')}.java"))
                    managed = r.get("managed_entity") or "Entity"
                    lines.append(f"- **{r.get('name')}** (Extends: `{r.get('extends', 'JpaRepository')}`, Manages: `{managed}`)")
            else:
                lines.append("- *No repositories detected.*")

            ev_str = ", ".join(list(dict.fromkeys(evidence_files))[:6])
            lines.append(f"\n*Based on analyzed files: {ev_str}.*")
            return "\n".join(lines)

        # ----------------------------------------------------------------------
        # Intent 4: Database Vendor & Driver Detection
        # ----------------------------------------------------------------------
        db_keywords = ["database vendor", "which database", "what database", "db vendor", "datasource", "rdbms", "database is used", "database used"]
        if any(kw in q for kw in db_keywords):
            if db_info and db_info.get("detected") and db_info.get("vendor"):
                evidence_list = db_info.get("evidence", [])
                ev_str = "\n".join([f"- {e}" for e in evidence_list]) if evidence_list else "- Configuration found in build and properties files."
                return (
                    f"### 🗄️ Database Configuration:\n\n"
                    f"The detected database vendor is **{db_info.get('vendor')}**.\n\n"
                    f"**Evidence from analyzed files:**\n{ev_str}\n\n"
                    f"*Based on analyzed files: pom.xml / application configuration.*"
                )
            else:
                return (
                    "The database vendor is not determinable from the analyzed files.\n\n"
                    "(No database driver dependency or JDBC URL found in pom.xml, build.gradle, or application.properties/yml).\n\n"
                    "*Based on analyzed files.*"
                )

        # ----------------------------------------------------------------------
        # Intent 5: Authentication & Security Detection
        # ----------------------------------------------------------------------
        auth_keywords = ["authentication", "auth component", "security component", "jwt", "oauth", "login", "security filter", "userdetailsservice", "is there an auth"]
        if any(kw in q for kw in auth_keywords) and not ("endpoint" in q or "route" in q):
            if auth_info and auth_info.get("detected"):
                lines = ["### 🔒 Authentication & Security Components Detected:\n"]
                if auth_info.get("components"):
                    lines.append(f"- **Security Classes / Filters**: {', '.join([f'`{c}`' for c in auth_info.get('components', [])])}")
                if auth_info.get("dependencies"):
                    lines.append(f"- **Security Libraries**: {', '.join([f'`{d}`' for d in auth_info.get('dependencies', [])])}")
                if auth_info.get("evidence"):
                    lines.append("\n**Evidence from analyzed files:**")
                    for ev in auth_info.get("evidence", []):
                        lines.append(f"- {ev}")
                lines.append("\n*Based on analyzed files.*")
                return "\n".join(lines)
            else:
                return (
                    "No authentication component detected in the analyzed files.\n\n"
                    "(Note: this only covers the analyzed files in the uploaded archive).\n\n"
                    "*Based on analyzed files.*"
                )

        # ----------------------------------------------------------------------
        # Intent 6: Implementers of an Interface
        # ----------------------------------------------------------------------
        if "who implements" in q or "implementations of" in q or "implementers of" in q or ("implements" in q and len(extracted_classes_in_query) == 1):
            target_iface = extracted_classes_in_query[0] if extracted_classes_in_query else None
            if not target_iface:
                # Find interface in question
                for si in service_interfaces + [c for c in classes if c.get("is_interface")]:
                    if si.get("name", "").lower() in q:
                        target_iface = si.get("name")
                        break

            if target_iface:
                implementers = []
                evidence_files = []
                for c in classes:
                    for imp in c.get("implements", []):
                        if target_iface in imp or imp in target_iface:
                            implementers.append(c)
                            evidence_files.append(c.get("file"))
                            break

                if implementers:
                    lines = [f"### ⚙️ Implementers of `{target_iface}` ({len(implementers)} found):\n"]
                    for impl in implementers:
                        stereo = f" (@{impl.get('type')})" if impl.get('type') else ""
                        lines.append(f"- **`{impl.get('name')}`**{stereo} in file `{impl.get('file')}`")
                    ev_str = ", ".join(evidence_files)
                    lines.append(f"\n*Based on analyzed files: {ev_str}.*")
                    return "\n".join(lines)
                else:
                    return f"No direct implementing classes for `{target_iface}` were detected in the analyzed codebase.\n\n*Based on analyzed files.*"

        # ----------------------------------------------------------------------
        # Intent 7: Who Depends On X (Reverse Dependencies)
        # ----------------------------------------------------------------------
        if "who depends on" in q or "who calls" in q or "who uses" in q or "dependents of" in q:
            target = extracted_classes_in_query[0] if extracted_classes_in_query else None
            if not target:
                for c in classes:
                    if c.get("name", "").lower() in q:
                        target = c.get("name")
                        break
            if target:
                dependents = []
                evidence_files = []
                for rel in relationships:
                    if rel.get("target") == target:
                        src_name = rel.get("source")
                        src_obj = next((c for c in classes if c.get("name") == src_name), None)
                        dependents.append((src_name, rel.get("type"), rel.get("description", "")))
                        if src_obj and src_obj.get("file"):
                            evidence_files.append(src_obj.get("file"))

                if dependents:
                    lines = [f"### 🔗 Components that depend on `{target}` ({len(dependents)} found):\n"]
                    for src, r_type, r_desc in dependents:
                        lines.append(f"- **`{src}`** (relationship: `{r_type}` - {r_desc})")
                    ev_str = ", ".join(list(dict.fromkeys(evidence_files))[:5])
                    lines.append(f"\n*Based on analyzed files: {ev_str}.*")
                    return "\n".join(lines)
                else:
                    return f"No analyzed component directly depends on `{target}`.\n\n*Based on analyzed files.*"

        if not endpoints:
            endpoints = [ep for c in controllers for ep in c.get("endpoints", [])]

        # ----------------------------------------------------------------------
        # Intent 7.5: Connected Repositories for Controller
        # ----------------------------------------------------------------------
        if ("repositor" in q and "controller" in q and ("connect" in q or "what" in q or "which" in q or "depend" in q)) and len(extracted_classes_in_query) < 2:
            target_ctrl = extracted_classes_in_query[0] if (extracted_classes_in_query and any(c.get("name") == extracted_classes_in_query[0] for c in controllers)) else (controllers[0].get("name") if len(controllers) == 1 else None)
            if target_ctrl:
                ctrl_obj = next((c for c in controllers if c.get("name") == target_ctrl), None)
                ctrl_file = ctrl_obj.get("file", f"{target_ctrl}.java") if ctrl_obj else f"{target_ctrl}.java"
                
                # Check downstream paths to repositories
                connected_repos = []
                for r in repositories:
                    r_name = r.get("name")
                    # Build adjacency graph
                    adj = {}
                    for rel in relationships:
                        adj.setdefault(rel.get("source"), []).append(rel.get("target"))
                        if rel.get("type") == "implements":
                            adj.setdefault(rel.get("target"), []).append(rel.get("source"))
                    # BFS
                    queue = [[target_ctrl]]
                    visited = {target_ctrl}
                    found_path = None
                    while queue:
                        curr = queue.pop(0)
                        if curr[-1] == r_name:
                            found_path = curr
                            break
                        for nxt in adj.get(curr[-1], []):
                            if nxt not in visited:
                                visited.add(nxt)
                                queue.append(curr + [nxt])
                    if found_path:
                        connected_repos.append((r_name, found_path))

                if connected_repos:
                    lines = [f"### 🗄️ Repositories connected to `{target_ctrl}`:\n"]
                    for r_name, path in connected_repos:
                        if len(path) == 2:
                            lines.append(f"- `{target_ctrl}` directly depends on `{r_name}`.")
                        else:
                            path_str = " ➔ ".join([f"`{n}`" for n in path])
                            lines.append(f"- `{target_ctrl}` does **not** directly depend on `{r_name}`. It connects indirectly via:\n  {path_str}")
                    lines.append(f"\n*Based on analyzed files: {ctrl_file}.*")
                    return "\n".join(lines)
                else:
                    return f"`{target_ctrl}` does not connect to any repository in the analyzed architecture.\n\n*Based on analyzed files.*"

        # ----------------------------------------------------------------------
        # Intent 8: Dependency Path & Direct vs Indirect Query
        # ----------------------------------------------------------------------
        if ("depend" in q or "connect" in q or "path" in q) and len(extracted_classes_in_query) >= 2:
            src_name = extracted_classes_in_query[0]
            tgt_name = extracted_classes_in_query[1]

            # Build adjacency graph
            adj: Dict[str, List[Tuple[str, str]]] = {}
            for r in relationships:
                adj.setdefault(r.get("source"), []).append((r.get("target"), r.get("type")))
                # If relationship is implements, allow traversal from interface to implementer
                if r.get("type") == "implements":
                    adj.setdefault(r.get("target"), []).append((r.get("source"), "implemented by"))

            # Check direct dependency
            direct_rel = next((r for r in relationships if r.get("source") == src_name and r.get("target") == tgt_name), None)
            
            # BFS for shortest dependency path
            queue = [[src_name]]
            visited = {src_name}
            found_path: Optional[List[str]] = None

            while queue:
                curr_path = queue.pop(0)
                last_node = curr_path[-1]
                if last_node == tgt_name:
                    found_path = curr_path
                    break
                for nxt, _ in adj.get(last_node, []):
                    if nxt not in visited:
                        visited.add(nxt)
                        queue.append(curr_path + [nxt])

            src_file = next((c.get("file") for c in classes if c.get("name") == src_name), f"{src_name}.java")
            tgt_file = next((c.get("file") for c in classes if c.get("name") == tgt_name), f"{tgt_name}.java")

            if direct_rel:
                return (
                    f"Yes. `{src_name}` directly depends on `{tgt_name}`.\n\n"
                    f"- Relationship type: `{direct_rel.get('type')}` ({direct_rel.get('description', '')})\n\n"
                    f"*Based on analyzed files: {src_file}, {tgt_file}.*"
                )
            elif found_path:
                path_str = " ➔ ".join([f"`{n}`" for n in found_path])
                return (
                    f"No. `{src_name}` does **not** directly depend on `{tgt_name}`.\n\n"
                    f"However, there is an indirect dependency path:\n{path_str}\n\n"
                    f"*Based on analyzed files: {src_file}, {tgt_file}.*"
                )
            else:
                return (
                    f"No. `{src_name}` does not depend on `{tgt_name}` (neither directly nor indirectly).\n\n"
                    f"*Based on analyzed files: {src_file}, {tgt_file}.*"
                )

        # ----------------------------------------------------------------------
        # Intent 9: Runtime / Internal Method-Body Query
        # ----------------------------------------------------------------------
        runtime_keywords = ["what happens when", "finds no user", "if user not found", "runtime exception", "method body", "execution", "internal logic"]
        if any(kw in q for kw in runtime_keywords):
            return "This internal runtime method-body behavior cannot be determined from the extracted static architecture metadata.\n\n*Based on analyzed files.*"

        # ----------------------------------------------------------------------
        # Intent 10: Request Flow & Chain Traversal
        # ----------------------------------------------------------------------
        if "flow" in q or "request" in q or "call hierarchy" in q:
            target_ctrl = extracted_classes_in_query[0] if extracted_classes_in_query else None
            if not target_ctrl and controllers:
                target_ctrl = controllers[0].get("name")

            if target_ctrl:
                ctrl_obj = next((c for c in controllers if c.get("name") == target_ctrl), None)
                if ctrl_obj:
                    lines = [f"### 🔄 Request Flow for `{target_ctrl}`:\n"]
                    lines.append(f"1. **Controller Layer**: `{target_ctrl}` handles incoming HTTP requests (Base path: `{ctrl_obj.get('base_path', 'None')}`).")
                    
                    deps = ctrl_obj.get("dependencies", [])
                    if deps:
                        lines.append(f"2. **Service Layer**: `{target_ctrl}` delegates business logic to {', '.join([f'`{d}`' for d in deps])}.")
                        
                        # Find downstream services and repositories
                        downstream_repos = set()
                        for d in deps:
                            s_obj = next((s for s in services if s.get("name") == d or d in s.get("implements", [])), None)
                            if s_obj:
                                for s_dep in s_obj.get("dependencies", []):
                                    if any(r.get("name") == s_dep for r in repositories):
                                        downstream_repos.add(s_dep)

                        if downstream_repos:
                            lines.append(f"3. **Persistence Layer**: Downstream service calls repositories: {', '.join([f'`{r}`' for r in downstream_repos])}.")
                            
                            downstream_entities = set()
                            for r_name in downstream_repos:
                                r_obj = next((r for r in repositories if r.get("name") == r_name), None)
                                if r_obj and r_obj.get("managed_entity"):
                                    downstream_entities.add(r_obj.get("managed_entity"))
                            if downstream_entities:
                                lines.append(f"4. **Database / Entities**: Repositories persist and query domain entities: {', '.join([f'`{e}`' for e in downstream_entities])}.")
                    
                    lines.append(f"\n*Based on analyzed files: {ctrl_obj.get('file')}.*")
                    return "\n".join(lines)

        # ----------------------------------------------------------------------
        # Intent 11: Endpoints List & Service Handler Query
        # ----------------------------------------------------------------------
        if "endpoint" in q or "api" in q or "route" in q:
            # Check if asking specifically which service handles an endpoint or path
            matching_path_eps = []
            for ep in endpoints:
                if ep.get("path", "").lower() in q or ep.get("path", "").rstrip("/").lower() in q:
                    matching_path_eps.append(ep)

            if ("service" in q or "handler" in q) and matching_path_eps:
                lines = [f"### 🌐 Endpoint Handling for `{matching_path_eps[0].get('path')}`:\n"]
                for ep in matching_path_eps:
                    ctrl_name = ep.get("controller")
                    ctrl_obj = next((c for c in controllers if c.get("name") == ctrl_name), None)
                    deps = ctrl_obj.get("dependencies", []) if ctrl_obj else []
                    deps_str = ", ".join([f"`{d}`" for d in deps]) if deps else "None (direct processing)"
                    lines.append(f"- **Endpoint**: `{ep.get('http_method')}` `{ep.get('path')}`")
                    lines.append(f"- **Controller**: `{ctrl_name}.{ep.get('method_name')}()`")
                    lines.append(f"- **Handling / Delegated Service(s)**: {deps_str}")
                lines.append("\n*Based on analyzed files.*")
                return "\n".join(lines)

            target_ctrl = extracted_classes_in_query[0] if extracted_classes_in_query else None
            filtered_eps = [ep for ep in endpoints if ep.get("controller") == target_ctrl] if target_ctrl else endpoints

            lines = [f"### 🌐 REST Endpoints ({len(filtered_eps)} found):\n"]
            for ep in filtered_eps:
                lines.append(f"- `{ep.get('http_method')}` **{ep.get('path')}** → `{ep.get('controller')}.{ep.get('method_name')}()` : `{ep.get('return_type')}`")
            
            lines.append("\n*Based on analyzed files.*")
            return "\n".join(lines)

        # ----------------------------------------------------------------------
        # Intent 12: Architecture Observations / Issues
        # ----------------------------------------------------------------------
        if "issue" in q or "observation" in q or "anti-pattern" in q or "problem" in q or "code smell" in q:
            observations = arch.get("observations", [])
            if observations:
                lines = ["### 🔍 Architecture Observations & Potential Issues:\n"]
                for obs in observations:
                    sev_icon = "⚠️" if obs.get("severity") == "warning" else "ℹ️"
                    lines.append(f"- {sev_icon} {obs.get('message')}")
                lines.append("\n*Based on analyzed files.*")
                return "\n".join(lines)
            else:
                return "No architectural anti-patterns or issues were detected in the analyzed architecture.\n\n*Based on analyzed files.*"

        # ----------------------------------------------------------------------
        # Intent 13: Architecture Overview / Summary
        # ----------------------------------------------------------------------
        if any(kw in q for kw in ["overview", "summary", "stats", "count", "project", "structure", "classes", "types"]):
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
                f"*Based on analyzed files.*"
            )

        # ----------------------------------------------------------------------
        # Fallback: Helpful response with dynamic examples (Never dump full overview)
        # ----------------------------------------------------------------------
        sample_ctrl = controllers[0].get("name", "Controller") if controllers else "Controller"
        sample_srv = services[0].get("name", "Service") if services else "Service"
        sample_repo = repositories[0].get("name", "Repository") if repositories else "Repository"
        return (
            f"I analyzed **{arch.get('project', 'your project')}** with {summary.get('total_types', len(classes))} types across {summary.get('packages', len(arch.get('packages', [])))} packages.\n\n"
            f"Here are 3 example questions you can ask about this project:\n"
            f"1. `Explain the request flow for {sample_ctrl}`\n"
            f"2. `Does {sample_ctrl} directly depend on {sample_repo}?`\n"
            f"3. `What database entities and repositories are present?`\n\n"
            f"*Based on analyzed files.*"
        )
