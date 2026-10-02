import re
from typing import List, Dict, Set
from backend.analyzer.models import Architecture, ClassInfo, RelationshipInfo


def sanitize_id(name: str) -> str:
    """Ensure Mermaid node IDs are valid alphanumeric strings."""
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)


def sanitize_label(text: str) -> str:
    """Escape characters that break Mermaid string syntax."""
    if not text:
        return ""
    text = text.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
    return text


def escape_uml_generics(text: str) -> str:
    """Convert Java generics like List<User> to Mermaid classDiagram format List~User~."""
    if not text:
        return ""
    return text.replace("<", "~").replace(">", "~")


class MermaidGenerator:
    """Generates clean, readable, professional Mermaid architecture and UML diagrams for Spring Boot projects."""

    @classmethod
    def generate(cls, architecture: Architecture, mode: str = "default") -> str:
        """Generates layered flowchart architecture diagram."""
        lines: List[str] = [
            "flowchart TD",
            "    %% Styles & Theme Definition",
            "    classDef controller fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc",
            "    classDef service fill:#1e293b,stroke:#4ade80,stroke-width:2px,color:#f8fafc",
            "    classDef repository fill:#1e293b,stroke:#a855f7,stroke-width:2px,color:#f8fafc",
            "    classDef entity fill:#1e293b,stroke:#f59e0b,stroke-width:2px,color:#f8fafc",
            "    classDef dto fill:#1e293b,stroke:#94a3b8,stroke-width:1px,stroke-dasharray: 3 3,color:#cbd5e1",
            "    classDef interfaceNode fill:#0f172a,stroke:#38bdf8,stroke-width:1px,stroke-dasharray: 4 4,color:#cbd5e1",
            "    classDef applicationNode fill:#1e293b,stroke:#e11d48,stroke-width:2px,color:#f8fafc",
            "    classDef defaultConfig fill:#1e293b,stroke:#64748b,stroke-width:1px,color:#e2e8f0",
            ""
        ]

        # Group components by layer
        controllers: List[ClassInfo] = []
        services: List[ClassInfo] = []
        repositories: List[ClassInfo] = []
        entities: List[ClassInfo] = []
        dtos: List[ClassInfo] = []
        others: List[ClassInfo] = []

        for c in architecture.classes:
            if c.type == "controller":
                controllers.append(c)
            elif c.type in ["service", "service_interface"]:
                services.append(c)
            elif c.type == "repository":
                repositories.append(c)
            elif c.type == "entity":
                entities.append(c)
            elif c.type == "dto":
                dtos.append(c)
            else:
                others.append(c)

        # Build Subgraph: Controllers
        if controllers:
            lines.append("    subgraph ControllersLayer [🎮 Controllers Layer]")
            for c in controllers:
                nid = sanitize_id(c.name)
                anno_str = f"&laquo;{', '.join(c.annotations[:2])}&raquo;" if c.annotations else "&laquo;Controller&raquo;"
                ep_lines = ""
                if c.endpoints:
                    ep_previews = [f"<b>{ep.http_method}</b> {ep.path}" for ep in c.endpoints[:8]]
                    if len(c.endpoints) > 8:
                        ep_previews.append(f"... +{len(c.endpoints) - 8} more")
                    ep_lines = "<br/>" + "<br/>".join(ep_previews)
                label = f"<b>{sanitize_label(c.name)}</b><br/><small>{sanitize_label(anno_str)}</small>{ep_lines}"
                lines.append(f'        {nid}["{label}"]:::controller')
            lines.append("    end\n")

        # Build Subgraph: Services (including Service Interfaces)
        if services:
            lines.append("    subgraph ServicesLayer [⚙️ Services Layer]")
            for c in services:
                nid = sanitize_id(c.name)
                is_iface = c.is_interface or c.type == "service_interface"
                tag = "&laquo;interface&raquo;" if is_iface else "&laquo;Service&raquo;"
                if c.annotations and not is_iface:
                    tag = f"&laquo;{', '.join(c.annotations[:2])}&raquo;"
                label = f"<b>{sanitize_label(c.name)}</b><br/><small>{sanitize_label(tag)}</small>"
                css_class = "interfaceNode" if is_iface else "service"
                lines.append(f'        {nid}["{label}"]:::{css_class}')
            lines.append("    end\n")

        # Build Subgraph: Repositories
        if repositories:
            lines.append("    subgraph RepositoriesLayer [🗄️ Repositories Layer]")
            for c in repositories:
                nid = sanitize_id(c.name)
                tag = "&laquo;Repository (interface)&raquo;" if c.is_interface else "&laquo;Repository&raquo;"
                ext_str = f"<br/><small>extends {sanitize_label(c.extends)}</small>" if c.extends else ""
                label = f"<b>{sanitize_label(c.name)}</b><br/><small>{sanitize_label(tag)}</small>{ext_str}"
                lines.append(f'        {nid}["{label}"]:::repository')
            lines.append("    end\n")

        # Build Subgraph: Domain Entities
        if entities:
            lines.append("    subgraph EntitiesLayer [📦 Domain Entities]")
            for c in entities:
                nid = sanitize_id(c.name)
                table_str = f"<br/><small>table: {sanitize_label(c.table_name)}</small>" if c.table_name else ""
                label = f"<b>{sanitize_label(c.name)}</b><br/><small>&laquo;Entity&raquo;</small>{table_str}"
                lines.append(f'        {nid}["{label}"]:::entity')
            lines.append("    end\n")

        # Build Subgraph: DTOs (if any)
        if dtos:
            lines.append("    subgraph DTOsLayer [📄 Data Transfer Objects]")
            for c in dtos:
                nid = sanitize_id(c.name)
                label = f"<b>{sanitize_label(c.name)}</b><br/><small>&laquo;DTO&raquo;</small>"
                lines.append(f'        {nid}["{label}"]:::dto')
            lines.append("    end\n")

        # Build Subgraph: Application Entry Point & Config
        if others:
            lines.append("    subgraph ApplicationLayer [🔧 Application Entry Point]")
            for c in others:
                nid = sanitize_id(c.name)
                tag = "&laquo;SpringBootApplication&raquo;" if c.type == "application" else f"&laquo;{c.type}&raquo;"
                css_class = "applicationNode" if c.type == "application" else "defaultConfig"
                label = f"<b>{sanitize_label(c.name)}</b><br/><small>{sanitize_label(tag)}</small>"
                lines.append(f'        {nid}["{label}"]:::{css_class}')
            lines.append("    end\n")

        # Add Relationships
        lines.append("    %% Relationships & Flow")
        written_edges: Set[str] = set()

        for rel in architecture.relationships:
            src = sanitize_id(rel.source)
            tgt = sanitize_id(rel.target)
            if src == tgt:
                continue

            # In default mode, suppress generic entity uses edges (show structural + DTO edges)
            if mode == "default" and rel.type == "uses_entity":
                continue

            edge_key = f"{src}->{tgt}:{rel.type}"
            if edge_key in written_edges:
                continue
            written_edges.add(edge_key)

            if rel.type == "dependency":
                lines.append(f"    {src} --> {tgt}")
            elif rel.type == "implements":
                lines.append(f"    {src} -.->|implements| {tgt}")
            elif rel.type == "extends":
                lines.append(f"    {src} --|>|extends| {tgt}")
            elif rel.type == "manages_entity":
                lines.append(f"    {src} ==>|depends| {tgt}")
            elif rel.type == "uses_dto":
                lines.append(f"    {src} -.->|uses| {tgt}")
            elif rel.type == "uses_entity":
                lines.append(f"    {src} -.->|uses| {tgt}")
            else:
                lines.append(f"    {src} --> {tgt}")

        # If no relationships exist at all, make sure diagram is still valid
        if len(architecture.classes) == 0:
            lines.append("    EmptyProject[\"No Java Classes Detected\"]")

        return "\n".join(lines)

    @classmethod
    def generate_uml(cls, architecture: Architecture) -> str:
        """Generates formal Mermaid classDiagram representing UML classes, methods, and relationships."""
        lines: List[str] = ["classDiagram\n"]

        if not architecture.classes:
            lines.append("    class EmptyProject {\n        <<Empty>>\n    }")
            return "\n".join(lines)

        notes: List[str] = []

        for c in architecture.classes:
            cname = sanitize_id(c.name)
            lines.append(f"    class {cname} {{")

            # 1. Stereotype
            if c.type == "controller":
                lines.append("        <<RestController>>")
            elif c.type == "service":
                lines.append("        <<Service>>")
            elif c.type == "service_interface":
                lines.append("        <<interface>>")
            elif c.type == "repository":
                lines.append("        <<interface>>")
                lines.append("        <<Repository>>")
            elif c.type == "entity":
                lines.append("        <<Entity>>")
            elif c.type == "dto":
                lines.append("        <<DTO>>")
            elif c.type == "application":
                lines.append("        <<SpringBootApplication>>")
            elif c.is_interface:
                lines.append("        <<interface>>")

            # 2. Fields
            # For entities and DTOs: show fields
            if c.type in ["entity", "dto"]:
                for f in c.fields:
                    ftype = escape_uml_generics(f.type)
                    lines.append(f"        +{ftype} {f.name}")
            else:
                # Show injected dependencies as private fields
                for dep in c.dependencies:
                    dep_field_name = dep[:1].lower() + dep[1:]
                    lines.append(f"        -{dep} {dep_field_name}")

            # 3. Methods
            if c.type == "controller":
                for ep in c.endpoints:
                    ret_t = escape_uml_generics(ep.return_type or "void")
                    lines.append(f"        +{ep.method_name}() {ret_t}")
            elif c.declared_methods:
                for m in c.declared_methods:
                    param_strs = [f"{escape_uml_generics(p.type)} {p.name}" for p in m.parameters]
                    params_joined = ", ".join(param_strs)
                    ret_t = escape_uml_generics(m.return_type or "void")
                    lines.append(f"        +{m.name}({params_joined}) {ret_t}")

            lines.append("    }\n")

            # Notes
            if c.type == "repository" and c.extends:
                notes.append(f'    note for {cname} "extends {escape_uml_generics(c.extends)}"')

        if notes:
            lines.extend(notes)
            lines.append("")

        # Relationships
        written_edges: Set[str] = set()

        for rel in architecture.relationships:
            src = sanitize_id(rel.source)
            tgt = sanitize_id(rel.target)
            if src == tgt:
                continue

            # Crucial: DemoApplication has zero outgoing relationships
            if src == "DemoApplication":
                continue

            edge_key = f"{src}->{tgt}:{rel.type}"
            if edge_key in written_edges:
                continue
            written_edges.add(edge_key)

            if rel.type == "implements":
                lines.append(f"    {src} ..|> {tgt} : implements")
            elif rel.type == "manages_entity":
                lines.append(f"    {src} --> {tgt} : depends")
            elif rel.type == "dependency":
                lines.append(f"    {src} --> {tgt} : uses")
            elif rel.type in ["uses_dto", "uses_entity", "uses"]:
                lines.append(f"    {src} ..> {tgt} : uses")
            elif rel.type == "extends":
                lines.append(f"    {src} --|> {tgt} : extends")
            else:
                lines.append(f"    {src} --> {tgt} : uses")

        return "\n".join(lines)
