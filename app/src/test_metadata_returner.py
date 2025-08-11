import os
from MetadataReturner import MetadataReturner

def test_search_metadata_nomenclature():
    test_file_path = "ОтчетПоКонфигурации.txt"
    cache_file_path = 'metadata_tree.json'

    # Удаляем старый кэш, чтобы гарантировать свежую сборку дерева для теста
    #if os.path.exists(cache_file_path):
    #   os.remove(cache_file_path)
    
    parser = MetadataReturner(test_file_path, cache_file_path)
    
    print("--- Searching for 'Документ.упЗапросУсловийПеревозки' ---")
    results = parser.search_metadata("Номенклатура", find_usages= False, limit=10)
    #print(parser.to_json(results))  
    

if __name__ == "__main__":
    test_search_metadata_nomenclature()
