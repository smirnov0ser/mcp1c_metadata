import re
import json
import os
import time
from typing import List, Dict, Any, Tuple, Optional

class MetadataReturner:
    def __init__(self, metadata_path: str, cache_path: str = 'metadata_tree.json'):
        self.metadata_path = metadata_path
        self.cache_path = cache_path
        self.singular_to_plural, self.type_map_sub_elements = self._get_type_mappings()
        self.plural_to_singular = {v: k for k, v in self.singular_to_plural.items()}
        self.tree = self._load_or_build_tree()

    def _get_type_mappings(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        s2p = {
            "Справочник": "Справочники", "Документ": "Документы", "Перечисление": "Перечисления",
            "Отчет": "Отчеты", "Обработка": "Обработки", "ПланВидовХарактеристик": "ПланыВидовХарактеристик",
            "ПланСчетов": "ПланыСчетов", "РегистрСведений": "РегистрыСведений",
            "РегистрНакопления": "РегистрыНакопления", "БизнесПроцесс": "БизнесПроцессы",
            "Задача": "Задачи", "Константа": "Константы", "ОбщийМодуль": "ОбщиеМодули",
            "Подсистемы": "Подсистемы"
        }
        sub = {
            "Реквизиты": "Реквизит", "ТабличныеЧасти": "ТабличнаяЧасть",
            "Формы": "Форма", "Команды": "Команда", "Макеты": "Макет", "Значения": "ЗначениеПеречисления"
        }
        return s2p, sub

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

    def _load_or_build_tree(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.cache_path):
            print(f"Loading metadata tree from cache: {self.cache_path}")
            with open(self.cache_path, 'r', encoding='utf-8') as f: return json.load(f)
        
        print("Building metadata tree from source...")
        start_time = time.time()
        lines = self._read_file(self.metadata_path)
        tree = self._build_tree_from_lines(lines)
        end_time = time.time()
        print(f"Tree building took: {end_time - start_time:.4f} seconds.")
        print(f"Saving metadata tree to cache: {self.cache_path}")
        with open(self.cache_path, 'w', encoding='utf-8') as f: json.dump(tree, f, ensure_ascii=False, indent=2)
        return tree

    def _read_file(self, file_path: str) -> List[str]:
        encodings = ['utf-16-le', 'utf-16', 'utf-8', 'cp1251']
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc, errors='replace') as f:
                    return [line.replace('\t', '    ') for line in f.readlines()]
            except (UnicodeDecodeError, FileNotFoundError): continue
        return []

    def _get_indent(self, line: str) -> int:
        return len(line) - len(line.lstrip(' '))

    def _parse_object(self, lines: List[str], start_index: int) -> Tuple[Optional[Dict[str, Any]], int]:
        if start_index >= len(lines): return None, start_index
        first_line = lines[start_index]
        if not first_line.strip().startswith('- '): return None, start_index
        
        full_path = first_line.strip().lstrip('- ')
        normalized_path = self._normalize_path(full_path)
        
        obj = {'full_path': full_path, 'normalized_path': normalized_path, 'properties': {}, 'children': []}
        
        base_indent = self._get_indent(first_line)
        i = start_index + 1
        while i < len(lines):
            line = lines[i]
            indent = self._get_indent(line)
            if indent <= base_indent: break
            
            stripped_line = line.strip()
            if stripped_line.startswith('- '):
                child, end_index = self._parse_object(lines, i)
                if child: obj['children'].append(child)
                i = end_index
                continue
            
            match = re.match(r'^(?P<key>[^:]+):\s*("(?P<value>.*)"\s*)?$', stripped_line)
            if match:
                key, value = match.group('key').strip(), match.group('value')
                if value is None:
                    value_parts = []
                    i += 1
                    while i < len(lines) and self._get_indent(lines[i]) > indent:
                        value_parts.append(lines[i].strip().strip('"'))
                        i += 1
                    value = "\n".join(value_parts)
                    i -= 1
                
                if isinstance(value, str):
                    if ',' in value: # Handle comma-separated list of types
                        types = [t.strip() for t in value.split(',')]
                        normalized_types = [self._normalize_path(t) for t in types if t]
                        normalized_value = ",\n".join(normalized_types)
                        
                        obj['properties'][f"{key}_normalized"] = normalized_value
                    elif '.' in value: # Handle single type
                        # Check if value is a path-like string before normalizing
                        type_part = value.split('.')[0]
                        # Normalize if it looks like a known type, possibly with 'Ссылка'
                        if type_part in self.plural_to_singular or type_part in self.singular_to_plural or type_part.endswith('Ссылка'):
                            normalized_value = self._normalize_path(value)
                            obj['properties'][f"{key}_normalized"] = normalized_value
                
                obj['properties'][key] = value

            i += 1
        return obj, i

    def _build_tree_from_lines(self, lines: List[str]) -> List[Dict[str, Any]]:
        tree, i = [], 0
        while i < len(lines):
            obj, end_index = self._parse_object(lines, i)
            if obj: tree.append(obj)
            i = end_index if end_index > i else i + 1
        return tree

    def _add_all_descendant_paths(self, node: Dict[str, Any], current_node_path: List[str], found_paths: List[List[str]]):
        if 'children' in node and node['children']:
            for child in node['children']:
                child_path = current_node_path + [child['full_path']]
                found_paths.append(child_path)
                self._add_all_descendant_paths(child, child_path, found_paths)

    def _find_all_target_paths_once(self, tree: List[Dict[str, Any]], queries_with_children: set, queries_without_children: set) -> Tuple[List[List[str]], List[List[str]]]:
        paths_with_children_result = []
        paths_without_children_result = []

        def recursive_search(subtree, current_path_prefix):
            for obj in subtree:
                new_path = current_path_prefix + [obj['full_path']]
                obj_normalized_path = obj.get('normalized_path')

                # Check for deep search match first
                if obj_normalized_path in queries_with_children:
                    paths_with_children_result.append(new_path)
                    self._add_all_descendant_paths(obj, new_path, paths_with_children_result)
                # Check for shallow search match
                elif obj_normalized_path in queries_without_children:
                    paths_without_children_result.append(new_path)
                
                # Always continue search down the tree for other potential matches
                if 'children' in obj and obj['children']:
                    recursive_search(obj['children'], new_path)

        recursive_search(tree, [])
        return paths_with_children_result, paths_without_children_result

    def _build_filtered_tree(self, tree: List[Dict[str, Any]], target_paths: List[List[str]], shallow_targets: set) -> List[Dict[str, Any]]:
        filtered_tree = []
        for obj in tree:
            obj_path = obj['full_path']
            is_target = any(obj_path == path[-1] for path in target_paths)
            is_ancestor = any(obj_path in path[:-1] for path in target_paths)

            if is_target or is_ancestor:
                new_obj = {'full_path': obj['full_path']}
                if is_target:
                    new_obj['properties'] = {k: v for k, v in obj.get('properties', {}).items() if not k.endswith('_normalized')}
                
                is_shallow_target = obj_path in shallow_targets

                if obj.get('children') and not is_shallow_target:
                    child_target_paths = [path[path.index(obj_path)+1:] for path in target_paths if obj_path in path and path.index(obj_path) < len(path)-1]
                    if child_target_paths:
                        children = self._build_filtered_tree(obj['children'], child_target_paths, shallow_targets)
                        if children: new_obj['children'] = children
                
                filtered_tree.append(new_obj)
        return filtered_tree

    def _clean_node_recursively(self, node: Dict[str, Any]) -> Dict[str, Any]:
        cleaned_node = {
            'full_path': node['full_path'],
            'properties': {k: v for k, v in node.get('properties', {}).items() if not k.endswith('_normalized')}
        }
        if 'children' in node and node['children']:
            cleaned_node['children'] = [self._clean_node_recursively(child) for child in node['children']]
        return cleaned_node

    def _fuzzy_find_objects(self, tree: List[Dict[str, Any]], query: str, limit: int) -> List[Dict[str, Any]]:
        found_objects = []
        lower_query = query.lower()

        stack = list(tree)
        while stack:
            if len(found_objects) >= limit: # Added limit check here
                break
            obj = stack.pop(0)
            
            props = obj.get('properties', {})
            name = props.get("Имя", "")
            synonym = props.get("Синоним", "")
            object_representation = props.get("ПредставлениеОбъекта", "")
            extended_object_representation = props.get("РасширенноеПредставлениеОбъекта", "")
            list_representation = props.get("ПредставлениеСписка", "")
            extended_list_representation = props.get("РасширенноеПредставлениеСписка", "")
            normalized_path = obj.get("normalized_path", "")

            is_match = (
                lower_query in name.lower() or
                lower_query in synonym.lower() or
                lower_query in object_representation.lower() or
                lower_query in extended_object_representation.lower() or
                lower_query in list_representation.lower() or
                lower_query in extended_list_representation.lower() or
                lower_query in normalized_path.lower()
            )

            # New condition: only match if normalized_path has 1 or zero dots
            if is_match and normalized_path.count('.') <= 1:
                found_objects.append(obj)
            else:
                if 'children' in obj and obj['children']:
                    stack.extend(obj['children'])
        
        return found_objects

    def _fuzzy_find_normalized_paths(self, tree: List[Dict[str, Any]], query: str, limit: int = 5) -> List[str]:
        found_objects = self._fuzzy_find_objects(tree, query, limit)
        return [obj['normalized_path'] for obj in found_objects if 'normalized_path' in obj]

    def search_metadata(self, query: str, find_usages: bool = False, limit: int = 5) -> List[Dict[str, Any]]:
        # Normalize the input query first
        normalized_query = self._normalize_path(query)

        if not find_usages:
            # New direct search logic
            start_time_direct_search = time.time()
            found_objects = self._fuzzy_find_objects(self.tree, normalized_query, limit) # Pass limit here
            cleaned_objects = [self._clean_node_recursively(obj) for obj in found_objects]
            end_time_direct_search = time.time()
            print(f"Direct object search took: {end_time_direct_search - start_time_direct_search:.4f} seconds. Found {len(cleaned_objects)} objects.")
            return cleaned_objects

        # Existing logic to find usages
        # Step 1: Fuzzy find objects and get their normalized_paths.
        start_time_fuzzy = time.time()
        initial_match_paths = self._fuzzy_find_normalized_paths(self.tree, normalized_query) # Limit applied inside _fuzzy_find_normalized_paths
        end_time_fuzzy = time.time()
        
        # Filter for paths that look like "type.name" (exactly one dot)
        specific_object_paths = {path for path in initial_match_paths if path.count('.') == 1}
        # Get single-word paths (e.g., "Справочники")
        single_word_paths = {path for path in initial_match_paths if '.' not in path}

        print(f"Step 1 (Fuzzy Search) took: {end_time_fuzzy - start_time_fuzzy:.4f} seconds. Found {len(initial_match_paths)} total matches. "
              f"{len(specific_object_paths)} are specific objects, {len(single_word_paths)} are general types.")
        
        if not specific_object_paths and not single_word_paths:
            return []

        # Step 2: Use these paths to find the exact target paths for building the tree.
        start_time_exact = time.time()
        
        paths_with_children, paths_without_children = self._find_all_target_paths_once(
            self.tree,
            queries_with_children=specific_object_paths,
            queries_without_children=single_word_paths
        )
        
        end_time_exact = time.time()
        print(f"Step 2 (Exact Path Finding) took: {end_time_exact - start_time_exact:.4f} seconds.")

        # Combine all paths
        all_target_paths = paths_with_children + paths_without_children
        if not all_target_paths:
            return []

        # Identify which full_paths are targets that should NOT have children.
        shallow_targets = {path[-1] for path in paths_without_children}

        # De-duplicate final paths before building the tree
        start_time_build_tree = time.time()
        unique_paths_as_tuples = {tuple(p) for p in all_target_paths}
        final_unique_paths = [list(p) for p in unique_paths_as_tuples]
        
        unique_top_level_paths = {path[0] for path in final_unique_paths}
        top_level_nodes = [obj for obj in self.tree if obj['full_path'] in unique_top_level_paths]
        
        result = self._build_filtered_tree(top_level_nodes, final_unique_paths, shallow_targets)
        end_time_build_tree = time.time()
        print(f"Step 3 (Final Tree Building) took: {end_time_build_tree - start_time_build_tree:.4f} seconds.")
        return result

    def to_json(self, data: List[Dict[str, Any]]) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False) 