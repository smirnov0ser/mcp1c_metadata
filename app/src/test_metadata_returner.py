import os
from MetadataReturner import MetadataReturner

def test_search_metadata_nomenclature():
    test_file_path = "C:\D\AI\ypp2\Report\ОтчетПоКонфигурации.txt"
    cache_file_path = 'C:\D\AI\ypp2\metadata_tree_test.json'

    # Удаляем старый кэш, чтобы гарантировать свежую сборку дерева для теста
    if os.path.exists(cache_file_path):
       os.remove(cache_file_path)
    
    parser = MetadataReturner(test_file_path, cache_file_path)
    
    results = parser.search_metadata("Номенклатура", find_usages= False, limit=1)
    print(parser.to_json(results))  
    

if __name__ == "__main__":
    test_search_metadata_nomenclature()
