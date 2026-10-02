import os
import re
from typing import List, Dict, Any, Optional, Tuple

try:
    import javalang
    HAS_JAVALANG = True
except ImportError:
    HAS_JAVALANG = False


class JavaParsedFile:
    def __init__(self, file_path: str, relative_path: str):
        self.file_path = file_path
        self.relative_path = relative_path
        self.package: str = ""
        self.imports: List[str] = []
        self.types: List[Dict[str, Any]] = []


def clean_annotation_name(anno_str: str) -> str:
    """Extract clean annotation name like 'RestController' from '@RestController' or '@org.springframework.web...'"""
    s = anno_str.strip()
    if s.startswith("@"):
        s = s[1:]
    s = s.split("(")[0].strip()
    if "." in s:
        s = s.split(".")[-1]
    return s


def parse_annotation_attribute_string(attr_str: str) -> Dict[str, Any]:
    """Parse annotation attribute content inside parentheses e.g. 'name = \"users\", schema = \"public\"'."""
    attrs: Dict[str, Any] = {}
    if not attr_str or not attr_str.strip():
        return attrs

    content = attr_str.strip()

    # Case 1: Simple single value e.g. ("/api/users") or ("users")
    if "=" not in content:
        val = content.strip().strip('"\'')
        attrs["value"] = val
        return attrs

    # Case 2: Key-value pairs e.g. name = "users", strategy = GenerationType.IDENTITY
    pairs = re.findall(r'([A-Za-z0-9_]+)\s*=\s*([^,]+)', content)
    for k, v in pairs:
        key = k.strip()
        val = v.strip().strip('"\'')
        attrs[key] = val
        if key in ["value", "path"] and "value" not in attrs:
            attrs["value"] = val

    return attrs


def extract_ast_annotation_attributes(anno: Any) -> Dict[str, Any]:
    """Extract dictionary of attributes from a javalang Annotation AST node."""
    attrs: Dict[str, Any] = {}
    if anno is None or not hasattr(anno, "element") or anno.element is None:
        return attrs

    element = anno.element

    # Helper to resolve AST expression to string
    def resolve_val(node: Any) -> Any:
        if node is None:
            return ""
        if hasattr(node, "value"):
            v = str(node.value)
            return v.strip('"\'')
        if hasattr(node, "member"):
            qualifier = getattr(node, "qualifier", "")
            return f"{qualifier}.{node.member}" if qualifier else node.member
        if hasattr(node, "name"):
            return getattr(node, "name", "")
        if isinstance(node, list):
            return [resolve_val(x) for x in node]
        return str(node).strip('"\'')

    # Single literal or expression e.g. @RequestMapping("/api/users")
    if hasattr(element, "value") or hasattr(element, "member") or hasattr(element, "name"):
        val = resolve_val(element)
        attrs["value"] = val
        return attrs

    # List of ElementValuePair / MemberValuePair
    if isinstance(element, list):
        for item in element:
            if hasattr(item, "name") and hasattr(item, "value"):
                k = item.name
                v = resolve_val(item.value)
                attrs[k] = v
                if k in ["value", "path"]:
                    attrs["value"] = v
            else:
                attrs["value"] = resolve_val(item)
    elif hasattr(element, "name") and hasattr(element, "value"):
        k = element.name
        v = resolve_val(element.value)
        attrs[k] = v
        if k in ["value", "path"]:
            attrs["value"] = v

    return attrs


class JavaParser:
    """
    Deterministic Java source code parser combining AST parsing via javalang
    with a robust regex/text-based fallback for modern Java constructs.
    """

    @classmethod
    def parse_file(cls, file_path: str, relative_path: str = "") -> JavaParsedFile:
        parsed = JavaParsedFile(file_path, relative_path or file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return parsed

        # Try javalang AST first
        if HAS_JAVALANG:
            try:
                tree = javalang.parse.parse(content)
                cls._parse_with_ast(tree, content, parsed)
                if parsed.types:
                    return parsed
            except Exception:
                # Fall back gracefully to regex parser
                pass

        cls._parse_with_regex(content, parsed)
        return parsed

    @classmethod
    def _parse_with_ast(cls, tree: Any, content: str, parsed: JavaParsedFile):
        if tree.package:
            parsed.package = tree.package.name

        if tree.imports:
            for imp in tree.imports:
                parsed.imports.append(imp.path)

        for path, node in tree.filter(javalang.tree.TypeDeclaration):
            is_interface = isinstance(node, javalang.tree.InterfaceDeclaration)
            is_enum = isinstance(node, javalang.tree.EnumDeclaration)
            if is_enum:
                continue

            annotations = []
            annotation_attributes = {}

            if node.annotations:
                for anno in node.annotations:
                    aname = clean_annotation_name(anno.name)
                    annotations.append(aname)
                    attrs = extract_ast_annotation_attributes(anno)
                    annotation_attributes[aname] = attrs

            # Extends
            extends_val = None
            if hasattr(node, "extends") and node.extends:
                if isinstance(node.extends, list):
                    if len(node.extends) > 0:
                        extends_val = cls._extract_type_name(node.extends[0])
                else:
                    extends_val = cls._extract_type_name(node.extends)

            # Implements
            implements_list = []
            if hasattr(node, "implements") and node.implements:
                for imp in node.implements:
                    implements_list.append(cls._extract_type_name(imp))

            type_info: Dict[str, Any] = {
                "name": node.name,
                "is_interface": is_interface,
                "is_record": False,
                "annotations": annotations,
                "annotation_attributes": annotation_attributes,
                "extends": extends_val,
                "implements": implements_list,
                "fields": [],
                "constructors": [],
                "methods": [],
                "declared_methods": [],
                "endpoints": [],
            }

            # Fields
            if hasattr(node, "fields") and node.fields:
                for field in node.fields:
                    ftype = cls._extract_type_name(field.type)
                    fannos = []
                    fattrs = {}
                    is_id = False
                    for a in (field.annotations or []):
                        aname = clean_annotation_name(a.name)
                        fannos.append(aname)
                        attrs = extract_ast_annotation_attributes(a)
                        fattrs[aname] = attrs
                        if aname == "Id":
                            is_id = True

                    for declarator in field.declarators:
                        type_info["fields"].append({
                            "name": declarator.name,
                            "type": ftype,
                            "annotations": fannos,
                            "annotation_attributes": fattrs,
                            "is_id": is_id
                        })

            # Constructors
            if hasattr(node, "constructors") and node.constructors:
                for ctor in node.constructors:
                    params = []
                    for param in (ctor.parameters or []):
                        ptype = cls._extract_type_name(param.type)
                        params.append({"name": param.name, "type": ptype})
                    type_info["constructors"].append({
                        "parameters": params,
                        "annotations": [clean_annotation_name(a.name) for a in (ctor.annotations or [])]
                    })

            # Methods & Endpoints
            if hasattr(node, "methods") and node.methods:
                for meth in node.methods:
                    mreturn = cls._extract_type_name(meth.return_type) if meth.return_type else "void"
                    mparams = []
                    param_sig_parts = []
                    for param in (meth.parameters or []):
                        ptype = cls._extract_type_name(param.type)
                        mparams.append({
                            "name": param.name,
                            "type": ptype
                        })
                        param_sig_parts.append(f"{ptype} {param.name}")

                    mannos = []
                    mattrs = {}
                    for a in (meth.annotations or []):
                        aname = clean_annotation_name(a.name)
                        mannos.append(aname)
                        mattrs[aname] = extract_ast_annotation_attributes(a)

                    sig = f"{meth.name}({', '.join(param_sig_parts)}): {mreturn}"
                    method_obj = {
                        "name": meth.name,
                        "return_type": mreturn,
                        "parameters": mparams,
                        "signature": sig,
                        "annotations": mannos,
                        "annotation_attributes": mattrs
                    }

                    type_info["methods"].append(meth.name)
                    type_info["declared_methods"].append(method_obj)

                    # Only check REST endpoints for controllers / methods with Spring Web mapping annotations
                    endpoint = cls._extract_endpoint_from_ast_method(meth, node.name, type_info)
                    if endpoint:
                        type_info["endpoints"].append(endpoint)

            parsed.types.append(type_info)

    @classmethod
    def _extract_type_name(cls, type_node: Any) -> str:
        if type_node is None:
            return ""
        if isinstance(type_node, str):
            return type_node
        name = getattr(type_node, "name", "")
        arguments = getattr(type_node, "arguments", None)
        if arguments:
            arg_names = []
            for arg in arguments:
                if hasattr(arg, "type"):
                    arg_names.append(cls._extract_type_name(arg.type))
                elif hasattr(arg, "name"):
                    arg_names.append(arg.name)
            if arg_names:
                return f"{name}<{', '.join(arg_names)}>"
        return name

    @classmethod
    def _extract_endpoint_from_ast_method(cls, meth: Any, class_name: str, class_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mapping_map = {
            "GetMapping": "GET",
            "PostMapping": "POST",
            "PutMapping": "PUT",
            "DeleteMapping": "DELETE",
            "PatchMapping": "PATCH",
            "RequestMapping": "REQUEST",
        }
        for anno in (meth.annotations or []):
            aname = clean_annotation_name(anno.name)
            if aname in mapping_map:
                http_method = mapping_map[aname]
                attrs = extract_ast_annotation_attributes(anno)
                subpath = attrs.get("value") or attrs.get("path") or ""

                # Base path from class @RequestMapping
                class_req_mapping = class_info.get("annotation_attributes", {}).get("RequestMapping", {})
                base_path = class_req_mapping.get("value") or class_req_mapping.get("path") or ""

                if base_path and not base_path.startswith("/"):
                    base_path = "/" + base_path
                if subpath and not subpath.startswith("/"):
                    subpath = "/" + subpath

                full_path = (base_path.rstrip("/") + subpath) if (base_path or subpath) else "/"
                if not full_path.startswith("/"):
                    full_path = "/" + full_path

                return {
                    "http_method": http_method if http_method != "REQUEST" else "ALL",
                    "path": full_path,
                    "method_name": meth.name,
                    "return_type": cls._extract_type_name(meth.return_type) if meth.return_type else "void",
                    "controller": class_name,
                }
        return None

    @classmethod
    def _parse_with_regex(cls, content: str, parsed: JavaParsedFile):
        # Remove comments
        cleaned_content = re.sub(r'//.*?\n', '\n', content)
        cleaned_content = re.sub(r'/\*.*?\*/', '', cleaned_content, flags=re.DOTALL)

        # Package
        pkg_match = re.search(r'package\s+([a-zA-Z0-9_.]+)\s*;', cleaned_content)
        if pkg_match:
            parsed.package = pkg_match.group(1)

        # Imports
        for imp_match in re.finditer(r'import\s+(?:static\s+)?([a-zA-Z0-9_.*]+)\s*;', cleaned_content):
            parsed.imports.append(imp_match.group(1))

        # Type declaration regex
        type_pattern = re.compile(
            r'((?:@\w+(?:\([^)]*\))?\s*)*)'  # Annotations
            r'(?:public|protected|private|abstract|static|final|\s)*'
            r'(class|interface|record)\s+'
            r'([A-Za-z0-9_]+)'  # Name
            r'(?:<[^>]+>)?'      # Generics
            r'(?:\s+extends\s+([A-Za-z0-9_., <>]+))?'  # Extends
            r'(?:\s+implements\s+([A-Za-z0-9_., <>]+))?'  # Implements
            r'\s*\{',
            re.MULTILINE
        )

        for match in type_pattern.finditer(cleaned_content):
            raw_annos, kind, name, extends_str, implements_str = match.groups()
            is_interface = (kind == "interface")
            is_record = (kind == "record")

            annotations = []
            annotation_attributes = {}
            if raw_annos:
                for anno_match in re.finditer(r'@([A-Za-z0-9_]+)(?:\(([^)]*)\))?', raw_annos):
                    aname = anno_match.group(1)
                    annotations.append(aname)
                    attr_str = anno_match.group(2)
                    annotation_attributes[aname] = parse_annotation_attribute_string(attr_str) if attr_str else {}

            extends_val = extends_str.strip() if extends_str else None
            implements_list = [i.strip() for i in implements_str.split(",")] if implements_str else []

            type_info: Dict[str, Any] = {
                "name": name,
                "is_interface": is_interface,
                "is_record": is_record,
                "annotations": annotations,
                "annotation_attributes": annotation_attributes,
                "extends": extends_val,
                "implements": implements_list,
                "fields": [],
                "constructors": [],
                "methods": [],
                "declared_methods": [],
                "endpoints": [],
            }

            # Parse fields
            field_pattern = re.compile(
                r'((?:@\w+(?:\([^)]*\))?\s*)*)'
                r'(?:private|protected|public)?\s*(?:final\s+)?'
                r'([A-Za-z0-9_<>,\s]+?)\s+([A-Za-z0-9_]+)\s*(?:=\s*[^;]+)?\s*;',
                re.MULTILINE
            )
            for f_match in field_pattern.finditer(cleaned_content):
                f_annos_raw, f_type, f_name = f_match.groups()
                f_type = f_type.strip()
                if f_type in ["return", "throw", "package", "import", "class", "interface"]:
                    continue

                f_annos = []
                f_attrs = {}
                is_id = False
                if f_annos_raw:
                    for a_m in re.finditer(r'@([A-Za-z0-9_]+)(?:\(([^)]*)\))?', f_annos_raw):
                        aname = a_m.group(1)
                        f_annos.append(aname)
                        attr_str = a_m.group(2)
                        f_attrs[aname] = parse_annotation_attribute_string(attr_str) if attr_str else {}
                        if aname == "Id":
                            is_id = True

                type_info["fields"].append({
                    "name": f_name.strip(),
                    "type": f_type,
                    "annotations": f_annos,
                    "annotation_attributes": f_attrs,
                    "is_id": is_id
                })

            # Constructor regex
            ctor_pattern = re.compile(
                rf'(?:public|protected|private)?\s*{name}\s*\(([^)]*)\)\s*(?:throws\s+[^{{]+)?\s*\{{',
                re.MULTILINE
            )
            for c_match in ctor_pattern.finditer(cleaned_content):
                params_raw = c_match.group(1).strip()
                params = []
                if params_raw:
                    for p in params_raw.split(","):
                        p = p.strip()
                        parts = p.split()
                        if len(parts) >= 2:
                            p_type = parts[-2]
                            p_name = parts[-1]
                            params.append({"name": p_name, "type": p_type})
                type_info["constructors"].append({
                    "parameters": params,
                    "annotations": []
                })

            # Method regex
            method_pattern = re.compile(
                r'((?:@\w+(?:\([^)]*\))?\s*)*)'  # Annotations
                r'(?:public|protected|private|static|final|abstract|\s)*'
                r'([A-Za-z0-9_<>,\s]+)\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)\s*(?:throws\s+[^{{;]+)?\s*[{;]',
                re.MULTILINE
            )
            mapping_map = {
                "GetMapping": "GET",
                "PostMapping": "POST",
                "PutMapping": "PUT",
                "DeleteMapping": "DELETE",
                "PatchMapping": "PATCH",
                "RequestMapping": "REQUEST",
            }
            for m_match in method_pattern.finditer(cleaned_content):
                m_annos_raw, m_return, m_name, m_params_raw = m_match.groups()
                m_return = m_return.strip()
                if m_return in ["return", "throw", "package", "import", "class", "interface", "new"]:
                    continue

                m_annos = []
                m_attrs = {}
                if m_annos_raw:
                    for a_m in re.finditer(r'@([A-Za-z0-9_]+)(?:\(([^)]*)\))?', m_annos_raw):
                        aname = a_m.group(1)
                        m_annos.append(aname)
                        attr_str = a_m.group(2)
                        m_attrs[aname] = parse_annotation_attribute_string(attr_str) if attr_str else {}

                m_params = []
                param_sig_parts = []
                if m_params_raw and m_params_raw.strip():
                    for p in m_params_raw.split(","):
                        p = p.strip()
                        parts = p.split()
                        if len(parts) >= 2:
                            ptype = parts[-2]
                            pname = parts[-1]
                            m_params.append({"name": pname, "type": ptype})
                            param_sig_parts.append(f"{ptype} {pname}")

                sig = f"{m_name}({', '.join(param_sig_parts)}): {m_return}"
                method_obj = {
                    "name": m_name,
                    "return_type": m_return,
                    "parameters": m_params,
                    "signature": sig,
                    "annotations": m_annos,
                    "annotation_attributes": m_attrs
                }

                type_info["methods"].append(m_name)
                type_info["declared_methods"].append(method_obj)

                for anno_name, http_method in mapping_map.items():
                    if anno_name in m_annos:
                        subpath = m_attrs.get(anno_name, {}).get("value") or m_attrs.get(anno_name, {}).get("path") or ""
                        class_req_mapping = annotation_attributes.get("RequestMapping", {})
                        base_path = class_req_mapping.get("value") or class_req_mapping.get("path") or ""

                        if base_path and not base_path.startswith("/"):
                            base_path = "/" + base_path
                        if subpath and not subpath.startswith("/"):
                            subpath = "/" + subpath

                        full_path = (base_path.rstrip("/") + subpath) if (base_path or subpath) else "/"
                        if not full_path.startswith("/"):
                            full_path = "/" + full_path

                        type_info["endpoints"].append({
                            "http_method": http_method if http_method != "REQUEST" else "ALL",
                            "path": full_path,
                            "method_name": m_name,
                            "return_type": m_return,
                            "controller": name
                        })

            parsed.types.append(type_info)
