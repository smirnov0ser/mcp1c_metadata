import os
from MetadataReturner import MetadataReturner

def test_search_metadata():
    parser = MetadataReturner("C:\AI\mcp1c_metadata_files")
    # Получение списка конфигураций
    configs = parser.get_config_summaries()
    print("CONFIGS:")
    print(parser.to_json(configs))
    # Вызов поиска по первой конфигурации (всегда один вызов)
    config_name = "упп"
    results = parser.search_metadata("Документ.КоммерческоеПредложение", find_usages=False, limit=5, config=config_name)
    print("SEARCH RESULTS:")
    print(parser.to_json(results))


if __name__ == "__main__":
    test_search_metadata()
