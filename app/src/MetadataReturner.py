import json
import os
import time
from typing import List, Dict, Any, Optional

class MetadataReturner:
    def __init__(self, metadata_dir: Optional[str] = None):
        # Only JSON-based metadata is supported
        self.singular_to_plural = self._get_type_mappings()
        self.plural_to_singular = {v: k for k, v in self.singular_to_plural.items()}

        # User-provided directory for metadata files (optional)
        self.user_metadata_dir = metadata_dir

        # Discover available prepared metadata files
        self.metadata_dirs = self._get_metadata_dirs()
        self.base_name_to_path: Dict[str, str] = self._discover_metadata_files(self.metadata_dirs)
        self.loaded_json_by_base: Dict[str, Dict[str, Any]] = {}

        # Build and persist configs index for fast listing
        self.config_index_path = self._get_config_index_path()
        self.precomputed_config_summaries = self._build_and_persist_config_index()

    def _get_type_mappings(self) -> Dict[str, str]:
        return {
            "Справочник": "Справочники", "Документ": "Документы", "Перечисление": "Перечисления",
            "Отчет": "Отчеты", "Обработка": "Обработки", "ПланВидовХарактеристик": "ПланыВидовХарактеристик",
            "ПланСчетов": "ПланыСчетов", "РегистрСведений": "РегистрыСведений",
            "РегистрНакопления": "РегистрыНакопления", "БизнесПроцесс": "БизнесПроцессы",
            "Задача": "Задачи", "Константа": "Константы", "ОбщийМодуль": "ОбщиеМодули",
            "Подсистемы": "Подсистемы"
        }

    def _load_json_metadata(self, file_path: str) -> Dict[str, Any]:
        # Use utf-8-sig to gracefully handle BOM if present
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)

    def _get_metadata_dirs(self) -> List[str]:
        # If user provided a directory, use it; otherwise use ./app/metadata relative to project root
        if self.user_metadata_dir:
            return [self.user_metadata_dir]
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        target_dir = os.path.join(project_root, 'app', 'metadata')
        return [target_dir]

    def _discover_metadata_files(self, dirs: List[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        index_filename = 'metadata_configs_index.json'
        for d in dirs:
            try:
                for entry in os.listdir(d):
                    if entry.startswith('.'):
                        continue
                    full_path = os.path.join(d, entry)
                    if os.path.isfile(full_path):
                        base, ext = os.path.splitext(entry)
                        if ext.lower() == '.json' and entry.lower() != index_filename.lower():
                            # Prefer first occurrence; later duplicates are ignored
                            if base not in mapping:
                                mapping[base] = full_path
            except FileNotFoundError:
                continue
        # Do not raise here; handled gracefully upstream
        return mapping

    def _get_config_index_path(self) -> str:
        # Store index in the highest-priority existing directory
        target_dir = self.metadata_dirs[0] if self.metadata_dirs else os.getcwd()
        return os.path.join(target_dir, 'metadata_configs_index.json')

    def _build_and_persist_config_index(self) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        for base_name, path in self.base_name_to_path.items():
            try:
                data = self.loaded_json_by_base.get(base_name)
                if data is None:
                    data = self._load_json_metadata(path)
                    self.loaded_json_by_base[base_name] = data
                summaries.append({
                    'file': base_name,
                    'Имя': data.get('Имя', ''),
                    'Синоним': data.get('Синоним', ''),
                    'Версия': data.get('Версия', ''),
                })
            except Exception:
                continue
        try:
            with open(self.config_index_path, 'w', encoding='utf-8') as f:
                json.dump({'configs': summaries}, f, ensure_ascii=False, indent=2)
        except Exception:
            # Non-fatal if we cannot persist
            pass
        return summaries

    def _normalize_path(self, path: str) -> str:
        if '.' in path:
            type_part, name_part = path.split('.', 1)
        else:
            type_part = path
            name_part = None

        if type_part.endswith('Ссылка'):
            type_part = type_part[:-6]

        singular_type = self.plural_to_singular.get(type_part, type_part)

        if name_part:
            # Check if original type was a valid type, if not, it's part of the name
            if singular_type not in self.singular_to_plural:
                 return path # It's not a type we can normalize, return as is.
            return f"{singular_type}.{name_part}"
        else:
            return singular_type

    def search_metadata(self, query: str, find_usages: bool = False, limit: int = 5, config: Optional[str] = None) -> Dict[str, Any]:
        # Reset last info
        self._last_info = None

        # Select target configuration file
        target_base = self._resolve_config_base(config)
        if not target_base:
            # Build human-readable text with available configurations and return error status
            info = self.get_last_info()
            message = (info or {}).get("message", "")
            configs = (info or {}).get("configs", []) or []
            text = self._format_configs_info(message, configs)
            return {"status": "error", "result": {"text": text}}
        try:
            if target_base not in self.loaded_json_by_base:
                self.loaded_json_by_base[target_base] = self._load_json_metadata(self.base_name_to_path[target_base])

            # Normalize query to singular type (e.g., Документы.* -> Документ.*)
            normalized_query = self._normalize_path(query)

            start_time = time.time()
            results_list = self._search_in_json(self.loaded_json_by_base[target_base], normalized_query, limit)
            end_time = time.time()
            print(f"JSON search took: {end_time - start_time:.4f} seconds. Found {len(results_list)} objects.")
            return {"status": "success", "result": results_list}
        except Exception as e:
            return {"status": "error", "result": {"text": str(e)}}

    def to_json(self, data: Any) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False) 

    # --- JSON search helpers ---
    def _object_matches_query(self, obj: Dict[str, Any], lower_query: str) -> bool:
        fields_to_check = [
            obj.get("Имя", ""),
            obj.get("Синоним", ""),
            obj.get("ПолноеИмя", ""),
            obj.get("ПредставлениеОбъекта", ""),
            obj.get("РасширенноеПредставлениеОбъекта", ""),
            obj.get("ПредставлениеСписка", ""),
            obj.get("РасширенноеПредставлениеСписка", "")
        ]
        for value in fields_to_check:
            if isinstance(value, str) and lower_query in value.lower():
                return True
        return False

    def _search_in_json(self, root: Any, query: str, limit: int) -> List[Dict[str, Any]]:
        lower_query = query.lower()
        results: List[Dict[str, Any]] = []

        def traverse(node: Any):
            if len(results) >= limit:
                return
            if isinstance(node, dict):
                # Treat any dict with name-like fields as a potential metadata object
                if any(k in node for k in ("ПолноеИмя", "Имя", "Синоним")):
                    if self._object_matches_query(node, lower_query):
                        results.append(node)
                        if len(results) >= limit:
                            return
                for _, v in node.items():
                    if isinstance(v, (dict, list)):
                        traverse(v)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)

        traverse(root)
        return results

    # --- Config listing ---
    def get_config_summaries(self) -> List[Dict[str, Any]]:
        # Try to read from persisted index for speed
        try:
            if os.path.exists(self.config_index_path):
                with open(self.config_index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'configs' in data and isinstance(data['configs'], list):
                        return data['configs']
        except Exception:
            pass
        # Fallback to in-memory precomputed summaries
        return list(self.precomputed_config_summaries)

    def get_last_info(self, clear: bool = True) -> Optional[Dict[str, Any]]:
        info = getattr(self, '_last_info', None)
        if clear:
            self._last_info = None
        return info

    def _resolve_config_base(self, config: Optional[str]) -> Optional[str]:
        # Prepare summaries and helpers
        summaries = self.get_config_summaries()
        summaries_by_base: Dict[str, Dict[str, Any]] = {s.get('file'): s for s in summaries if isinstance(s, dict) and s.get('file')}
        file_to_base: Dict[str, str] = {os.path.basename(path).lower(): base for base, path in self.base_name_to_path.items()}

        def build_available() -> List[Dict[str, Any]]:
            return [
                {"file": base, "Имя": summaries_by_base.get(base, {}).get('Имя', ''), "Синоним": summaries_by_base.get(base, {}).get('Синоним', '')}
                for base in sorted(self.base_name_to_path.keys())
            ]

        # If not specified: use single file if only one; otherwise store guidance
        if not config:
            if len(self.base_name_to_path) == 1:
                return next(iter(self.base_name_to_path.keys()))
            if len(self.base_name_to_path) == 0:
                self._last_info = {
                    "message": "Не найдены конфигурации. Поместите *.json в каталог ./app/metadata",
                    "configs": []
                }
            else:
                self._last_info = {
                    "message": "Найдено несколько конфигураций. Укажите параметр 'config' (имя файла без расширения)",
                    "configs": build_available()
                }
            return None

        cfg_lower = config.lower()
        # Exact by base name (file without extension)
        for bn in self.base_name_to_path.keys():
            if bn.lower() == cfg_lower:
                return bn
        # Exact by file name with extension
        if cfg_lower in file_to_base:
            return file_to_base[cfg_lower]
        # Exact by Имя or Синоним
        for s in summaries:
            if not isinstance(s, dict):
                continue
            if s.get('Имя', '').lower() == cfg_lower or s.get('Синоним', '').lower() == cfg_lower:
                base = s.get('file')
                if base and base in self.base_name_to_path:
                    return base
        # Substring matches across base, file, Имя, Синоним
        candidates: List[str] = []
        for base_name, path in self.base_name_to_path.items():
            file_name = os.path.basename(path)
            s = summaries_by_base.get(base_name, {})
            name = s.get('Имя', '')
            synonym = s.get('Синоним', '')
            haystacks = [base_name.lower(), file_name.lower(), name.lower(), synonym.lower()]
            if any(cfg_lower in h for h in haystacks if h):
                candidates.append(base_name)
        if not candidates:
            self._last_info = {
                "message": f"Конфигурация по параметру '{config}' не найдена.",
                "configs": build_available()
            }
            return None
        if len(candidates) > 1:
            self._last_info = {
                "message": f"Найдено несколько конфигураций по параметру '{config}'. Уточните параметр 'config'",
                "configs": build_available()
            }
            return None
        return candidates[0]

    def _format_configs_info(self, message: str, configs: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        if configs:
            for c in configs:
                if isinstance(c, dict):
                    file_name = c.get("file", "")
                    name = c.get("Имя", "")
                    synonym = c.get("Синоним", "")
                    line = f"- {file_name}: {name} — {synonym}".strip()
                    lines.append(line)
        else:
            lines.append("- (конфигурации не найдены)")
        text = message
        if lines:
            text += "\n\nДоступные конфигурации:\n" + "\n".join(lines)
        return text