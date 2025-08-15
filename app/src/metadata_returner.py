import json
import logging
import os
import time
from typing import List, Dict, Any, Optional

# Logger is created in __init__ method

class MetadataReturner:
    """
    Класс для загрузки и поиска по метаданным конфигурации 1С в JSON-формате.
    Поддерживает разделение каталогов на входные данные (input) и скомпилированные артефакты (dist):
    - Входные JSON-файлы читаются из каталога input
    - Индекс конфигураций `metadata_configs_index.json` сохраняется в каталоге dist
    :param metadata_input_dir: Путь к каталогу с исходными JSON-метаданными. Если не указан,
        берётся из переменной окружения `INPUT_METADATA_DIR`, либо по умолчанию `/app/metadata_src`.
    :param metadata_dist_dir: Путь к каталогу для сохранения скомпилированных данных (индекс и пр.). Если не указан,
        берётся из переменной окружения `DIST_METADATA_DIR`, либо по умолчанию `/app/metadata_dist`.
    """

    def __init__(
        self,
        metadata_input_dir: Optional[str] = None,
        metadata_dist_dir: Optional[str] = None,
    ):
        # Create default logger - use root logger to avoid conflicts
        self.logger = logging.getLogger()
        
        # Only JSON-based metadata is supported
        self.singular_to_plural = self._get_type_mappings()
        self.plural_to_singular = {v: k for k, v in self.singular_to_plural.items()}

        # Directories
        self.user_metadata_input_dir = metadata_input_dir
        self.user_metadata_dist_dir = metadata_dist_dir

        # Discover available prepared metadata files
        self.metadata_dir = self._get_input_metadata_dir()
        self.logger.info(f"Каталог метаданных: {self.metadata_dir}")
        
        self.base_name_to_path: Dict[str, str] = self._discover_metadata_files(
            [self.metadata_dir]
        )
        self.logger.info(f"Найдено файлов метаданных: {len(self.base_name_to_path)}")
        if self.base_name_to_path:
            self.logger.info(f"Файлы: {list(self.base_name_to_path.keys())}")
        
        self.loaded_json_by_base: Dict[str, Dict[str, Any]] = {}

        # Build and persist configs index for fast listing
        self.config_index_path = self._get_config_index_path()
        self.logger.info(f"Путь к индексу конфигураций: {self.config_index_path}")
        
        try:
            self.precomputed_config_summaries = self._build_and_persist_config_index()
            self.logger.info(f"Индекс конфигураций построен успешно, найдено: {len(self.precomputed_config_summaries)}")
        except Exception as e:
            self.logger.warning(f"Не удалось построить индекс конфигураций: {e}")
            self.precomputed_config_summaries = []
        
        self.logger.info("MetadataReturner initialization completed")

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

    def _get_input_metadata_dir(self) -> str:
        """
        Возвращает путь каталога, в котором ищутся входные JSON-файлы метаданных.
        Приоритет:
        1) Параметр конструктора `metadata_input_dir`
        2) Переменная окружения `INPUT_METADATA_DIR`
        3) Иначе локальный путь `./metadata_src` (относительно корня проекта)
        """
        if self.user_metadata_input_dir:
            self.logger.debug(f"Используется каталог из параметра: {self.user_metadata_input_dir}")
            return self.user_metadata_input_dir

        env_dir = os.getenv("INPUT_METADATA_DIR")
        if env_dir:
            self.logger.debug(f"Используется каталог из переменной окружения: {env_dir}")
            return env_dir

        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        default_dir = os.path.join(project_root, "metadata_src")
        self.logger.debug(f"Используется каталог по умолчанию: {default_dir}")
        self.logger.debug(f"Текущий рабочий каталог: {os.getcwd()}")
        self.logger.debug(f"Путь к файлу: {__file__}")
        self.logger.debug(f"Корень проекта: {project_root}")
        
        # Check if directory exists
        if os.path.exists(default_dir):
            self.logger.info(f"Каталог по умолчанию существует: {default_dir}")
        else:
            self.logger.warning(f"Каталог по умолчанию НЕ существует: {default_dir}")
            
        return default_dir

    def _discover_metadata_files(self, dirs: List[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        index_filename = 'metadata_configs_index.json'
        for d in dirs:
            try:
                if not os.path.exists(d):
                    self.logger.warning(f"Каталог не существует: {d}")
                    continue
                if not os.path.isdir(d):
                    self.logger.warning(f"Путь не является каталогом: {d}")
                    continue
                    
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
            except (FileNotFoundError, PermissionError, OSError) as e:
                self.logger.warning(f"Ошибка при доступе к каталогу {d}: {e}")
                continue
        # Do not raise here; handled gracefully upstream
        self.logger.debug(f"Найдено файлов метаданных: {len(mapping)}")
        if mapping:
            self.logger.debug(f"Файлы: {list(mapping.keys())}")
        else:
            self.logger.warning("НЕ НАЙДЕНО файлов метаданных!")
            
        return mapping

    def _get_config_index_path(self) -> str:
        """
        Возвращает путь к файлу индекса конфигураций в каталоге dist.
        Приоритет выбора каталога dist:
        1) Параметр конструктора `metadata_dist_dir`
        2) Переменная окружения `DIST_METADATA_DIR`
        3) Иначе локальный путь `./metadata_dist` (относительно корня проекта)
        """
        dist_dir = self.user_metadata_dist_dir or os.getenv("DIST_METADATA_DIR")
        if not dist_dir:
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            )
            dist_dir = os.path.join(project_root, "metadata_dist")
        try:
            os.makedirs(dist_dir, exist_ok=True)
        except Exception:
            # Не фатально, но попробуем fallback в текущий каталог
            dist_dir = os.getcwd()
        return os.path.join(dist_dir, "metadata_configs_index.json")

    def _build_and_persist_config_index(self) -> List[Dict[str, Any]]:
        summaries: List[Dict[str, Any]] = []
        
        self.logger.info(f"Начинаю построение индекса конфигураций. Доступно файлов: {len(self.base_name_to_path)}")
        
        if not self.base_name_to_path:
            self.logger.warning("Нет доступных файлов метаданных для построения индекса")
            return summaries
            
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
            except Exception as e:
                self.logger.debug(f"Не удалось обработать файл '{path}': {e}")
                continue
        
        try:
            with open(self.config_index_path, 'w', encoding='utf-8') as f:
                json.dump({'configs': summaries}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # Non-fatal if we cannot persist
            self.logger.warning(
                f"Не удалось сохранить индекс конфигураций '{self.config_index_path}': {e}"
            )
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

        self.logger.info(f"=== search_metadata called ===")
        self.logger.info(f"Query: {query}, find_usages: {find_usages}, limit: {limit}, config: {config}")
        self.logger.info(f"Available metadata files: {len(self.base_name_to_path)}")

        result: Dict[str, Any] = {}
        try:
            # Check if we have any metadata files available
            if not self.base_name_to_path:
                self.logger.error("No metadata files available")
                result = {
                    "_call_params": {
                        "query": query,
                        "find_usages": find_usages,
                        "limit": limit,
                        "config": config,
                        "timestamp": time.time()
                    },
                    "status": "error", 
                    "result": {"text": "Нет доступных файлов метаданных. Убедитесь, что в каталоге ./metadata_src есть JSON-файлы с метаданными конфигураций 1С."}
                }
                return result
                
            # Select target configuration file
            target_base = self._resolve_config_base(config)
            if not target_base:
                # Build human-readable text with available configurations and return error status
                info = self.get_last_info()
                message = (info or {}).get("message", "")
                configs = (info or {}).get("configs", []) or []
                text = self._format_configs_info(message, configs)
                result = {"status": "error", "result": {"text": text}}
                return result

            if target_base not in self.loaded_json_by_base:
                self.loaded_json_by_base[target_base] = self._load_json_metadata(self.base_name_to_path[target_base])

            # Normalize query to singular type (e.g., Документы.* -> Документ.*)
            normalized_query = self._normalize_path(query)

            start_time = time.time()
            results_list = self._search_in_json(
                self.loaded_json_by_base[target_base], normalized_query, limit
            )
            end_time = time.time()
            
            # If find_usages is True, search for usages of found objects
            if find_usages and results_list:
                usage_start_time = time.time()
                usage_results = self._find_object_usages(self.loaded_json_by_base[target_base], results_list)
                usage_end_time = time.time()
                # Add call parameters at the top of the result
                result = {
                    "_call_params": {
                        "query": query,
                        "find_usages": find_usages,
                        "limit": limit,
                        "config": config,
                        "timestamp": time.time()
                    },
                    "status": "success", 
                    "result": usage_results
                }
                
                return result
            
            # Add call parameters at the top of the result
            result = {
                "_call_params": {
                    "query": query,
                    "find_usages": find_usages,
                    "limit": limit,
                    "config": config,
                    "timestamp": time.time()
                },
                "status": "success", 
                "result": results_list
            }
            
            return result
        except Exception as e:
            # Ошибка поиска по метаданным
            # Add call parameters at the top of the result
            result = {
                "_call_params": {
                    "query": query,
                    "find_usages": find_usages,
                    "limit": limit,
                    "config": config,
                    "timestamp": time.time()
                },
                "status": "error", 
                "result": {"text": str(e)}
            }
            
            return result

    def to_json(self, data: Any) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False) 

    # --- JSON search helpers ---
    def _object_matches_query_fields(self, obj: Dict[str, Any], lower_query: str, fields: List[str]) -> bool:
        """Check if object matches query using only specified fields"""
        for field in fields:
            value = obj.get(field, "")
            if isinstance(value, str) and lower_query in value.lower():
                return True
        return False

    def _rank_results_by_accuracy(self, results: List[Dict[str, Any]], query: str, lower_query: str, search_fields: List[str]) -> List[Dict[str, Any]]:
        """Rank results by accuracy: exact matches first, then substring matches"""
        exact_matches = []
        substring_matches = []
        
        for obj in results:
            is_exact = False
            for field in search_fields:
                value = obj.get(field, "")
                if isinstance(value, str):
                    # Check for exact match (case-insensitive)
                    if value.lower() == lower_query:
                        is_exact = True
                        break
                    # Check for exact match at word boundaries
                    words = value.lower().split()
                    if lower_query in words:
                        is_exact = True
                        break
            
            if is_exact:
                exact_matches.append(obj)
            else:
                substring_matches.append(obj)
        
        # Return exact matches first, then substring matches
        return exact_matches + substring_matches

    def _search_in_json(self, root: Any, query: str, limit: int) -> List[Dict[str, Any]]:
        lower_query = query.lower()
        all_results: List[Dict[str, Any]] = []
        
        # Fields to search in
        search_fields = ["ПолноеИмя", "Имя", "Синоним", "ПредставлениеОбъекта", 
                        "РасширенноеПредставлениеОбъекта", "ПредставлениеСписка", 
                        "РасширенноеПредставлениеСписка"]

        def traverse(node: Any):
            if isinstance(node, dict):
                # Only search in objects with "ПолноеИмя" property
                if "ПолноеИмя" in node:
                    # Check if object matches query using specified fields
                    if self._object_matches_query_fields(node, lower_query, search_fields):
                        all_results.append(node)
                for _, v in node.items():
                    if isinstance(v, (dict, list)):
                        traverse(v)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)

        traverse(root)
        
        # Rank results by accuracy: exact matches first, then substring matches
        ranked_results = self._rank_results_by_accuracy(all_results, query, lower_query, search_fields)
        
        # Apply limit after ranking
        return ranked_results[:limit]

    def _find_object_usages(self, root: Any, objects_to_find: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find all usages of specified objects in the JSON structure, searching only in 'Тип' fields"""
        # List to store all usage structures directly
        all_usage_structures = []
        
        # Extract full names of objects to search for
        target_full_names = {obj.get("ПолноеИмя", "") for obj in objects_to_find if obj.get("ПолноеИмя")}
        
        def traverse_and_find_usages(node: Any, path: List[str] = None, parent_info: Dict[str, Any] = None):
            if path is None:
                path = []
            if parent_info is None:
                parent_info = {}
                
            if isinstance(node, dict):
                current_path = path.copy()
                
                # Check if current node contains any of the target objects in 'Тип' field
                if ("Тип" in node and isinstance(node["Тип"], str)):
                    # Split by comma to handle multiple types
                    types = [t.strip() for t in node["Тип"].split(",")]
                    if any(t in target_full_names for t in types):
                        # Found a usage - build the structure
                        usage_structure = self._build_usage_structure(node, current_path, parent_info)
                        if usage_structure:
                            all_usage_structures.append(usage_structure)
                
                # Check if this node could be a parent (has ПолноеИмя)
                if "ПолноеИмя" in node:
                    current_parent_info = {
                        "ПолноеИмя": node.get("ПолноеИмя", ""),
                        "Имя": node.get("Имя", ""),
                        "path": current_path.copy()
                    }
                else:
                    current_parent_info = parent_info
                
                # Recursively traverse nested structures
                for key, value in node.items():
                    if isinstance(value, (dict, list)):
                        new_path = current_path + [key]
                        traverse_and_find_usages(value, new_path, current_parent_info)
                        
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    if isinstance(item, (dict, list)):
                        new_path = path + [str(i)]
                        traverse_and_find_usages(item, new_path, parent_info)
        
        traverse_and_find_usages(root)
        
        # Group usage structures by top-level parent object
        return self._group_usage_structures_by_parent(all_usage_structures)

    def _group_usage_structures_by_parent(self, usage_structures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group usage structures by top-level parent object, combining objects with the same ПолноеИмя."""
        grouped_results = {}
        
        for usage_structure in usage_structures:
            for top_level_key, objects_list in usage_structure.items():
                if isinstance(objects_list, list) and len(objects_list) > 0:
                    # Create a unique key for the top-level parent
                    parent_key = top_level_key
                    
                    if parent_key not in grouped_results:
                        grouped_results[parent_key] = {}
                    
                    # Merge objects with the same ПолноеИмя
                    for obj in objects_list:
                        full_name = obj.get("ПолноеИмя", "")
                        if full_name not in grouped_results[parent_key]:
                            grouped_results[parent_key][full_name] = obj.copy()
                        else:
                            # Merge properties from objects with the same ПолноеИмя
                            existing_obj = grouped_results[parent_key][full_name]
                            for key, value in obj.items():
                                if key not in ["ПолноеИмя", "Имя"]:  # Skip these fields
                                    if key in existing_obj:
                                        # If property already exists, extend the list
                                        if isinstance(existing_obj[key], list) and isinstance(value, list):
                                            existing_obj[key].extend(value)
                                        elif isinstance(existing_obj[key], list):
                                            existing_obj[key].append(value)
                                        elif isinstance(value, list):
                                            existing_obj[key] = [existing_obj[key]] + value
                                        else:
                                            existing_obj[key] = [existing_obj[key], value]
                                    else:
                                        # If property doesn't exist, add it
                                        existing_obj[key] = value
        
        # Convert grouped results back to the expected format
        result = []
        for top_level_key, objects_dict in grouped_results.items():
            result.append({top_level_key: list(objects_dict.values())})
        
        return result

    def _build_usage_structure(self, current_node: Dict[str, Any], path: List[str], parent_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build a usage structure showing where the object is used, similar to JSON configuration structure."""
        
        # Try to find the parent object
        if parent_info and parent_info.get("ПолноеИмя"):
            # We have parent information
            parent_full_name = parent_info["ПолноеИмя"]
            parent_name = parent_info["Имя"]
            
            # Determine the top-level key for the parent
            parent_top_level_key = "Объекты"  # Default fallback
            if parent_full_name:
                parts = parent_full_name.split(".")
                if len(parts) > 1:
                    singular_type = parts[0]
                    parent_top_level_key = self.singular_to_plural.get(singular_type, singular_type + "и")
                elif parts:
                    parent_top_level_key = parts[0] + "и"
            
            # Find the property name from the path to determine where to place the current node
            property_name = self._extract_property_name_from_path(path)
            
            # Create the parent object entry with the current node in the appropriate property
            parent_object_entry = {
                "ПолноеИмя": parent_full_name,
                "Имя": parent_name
            }
            
            # Add the current node to the appropriate property
            if property_name:
                parent_object_entry[property_name] = [{
                    "Имя": current_node.get("Имя", "")
                }]
            
            # Create result structure for this parent
            result = {}
            result[parent_top_level_key] = [parent_object_entry]
            return result
        else:
            # No parent info - create structure for the target object itself
            target_type = current_node.get("Тип", "")
            parts = target_type.split(".")
            if len(parts) >= 2:
                main_object_node = {
                    "ПолноеИмя": target_type,
                    "Имя": parts[-1]
                }
            else:
                main_object_node = {
                    "ПолноеИмя": target_type,
                    "Имя": target_type
                }

            # Determine the top-level key
            top_level_key = "Объекты"  # Default fallback
            if main_object_node.get("ПолноеИмя"):
                parts = main_object_node["ПолноеИмя"].split(".")
                if len(parts) > 1:
                    singular_type = parts[0]
                    top_level_key = self.singular_to_plural.get(singular_type, singular_type + "и")
                elif parts:
                    top_level_key = parts[0] + "и"

            # Create the main object entry
            object_entry = {
                "ПолноеИмя": main_object_node.get("ПолноеИмя", ""),
                "Имя": main_object_node.get("Имя", "")
            }

            # Create result structure
            result = {}
            result[top_level_key] = [object_entry]
            return result

    def _extract_property_name_from_path(self, path: List[str]) -> Optional[str]:
        """Extract meaningful property name from the path, ignoring numeric indices."""
        if not path:
            return None
            
        # Look for the property name in the path, ignoring numeric indices
        for path_element in reversed(path):
            if (path_element and 
                not path_element.isdigit() and 
                path_element not in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"] and
                len(path_element) > 1):  # Avoid single character paths
                return path_element
        
        # If we still don't have a meaningful property name, try to look deeper
        for i in range(len(path) - 2, -1, -1):
            path_element = path[i]
            if (path_element and 
                not path_element.isdigit() and 
                path_element not in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"] and
                len(path_element) > 1):
                return path_element
        
        return None

    # --- Config listing ---
    def get_config_summaries(self) -> List[Dict[str, Any]]:
        """
        Возвращает список кратких сведений о доступных конфигурациях.
        Сначала пытается прочитать скомпилированный индекс из каталога dist,
        при ошибке — возвращает предрассчитанный в памяти список.
        :return: Список словарей с полями `file`, `Имя`, `Синоним`, `Версия`.
        """
        try:
            if os.path.exists(self.config_index_path):
                with open(self.config_index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if (
                        isinstance(data, dict)
                        and "configs" in data
                        and isinstance(data["configs"], list)
                    ):
                        return data["configs"]
        except Exception as e:
            self.logger.debug(
                f"Не удалось прочитать индекс конфигураций '{self.config_index_path}': {e}"
            )
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
        
        self.logger.debug(f"Доступные конфигурации: {list(self.base_name_to_path.keys())}")
        self.logger.debug(f"Запрошенная конфигурация: {config}")

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
                    "message": "Не найдены конфигурации. Поместите *.json в каталог ./metadata_src",
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