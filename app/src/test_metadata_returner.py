import os
import json
from metadata_returner import MetadataReturner

def test_search_metadata():
    # Пути к каталогам
    input_dir = "C:\\AI\\mcp1c_metadata_files"  # Каталог с входными JSON-файлами
    dist_dir = "C:\\AI\\mcp1c_metadata_files\\mcp1c_metadata_dist"    # Каталог для сохранения результатов
    
    print(f"Инициализация MetadataReturner с каталогами:")
    print(f"  Input: {input_dir}")
    print(f"  Dist: {dist_dir}")
    
    # Создание экземпляра с двумя каталогами
    parser = MetadataReturner(
        metadata_input_dir=input_dir,
        metadata_dist_dir=dist_dir
    )
 
    # Получение списка конфигураций
    print("Получение списка конфигураций...")
    configs = parser.get_config_summaries()
    print("CONFIGS:")
    print(parser.to_json(configs))
    
    # Вызов поиска по первой конфигурации (всегда один вызов)
    config_name = "упп"
    
    # Тест 1: Обычный поиск без find_usages
    print("=== ТЕСТ 1: Обычный поиск ===")
    results = parser.search_metadata("Справочник.Валюты", find_usages=False, limit=1, config=config_name)
    print("SEARCH RESULTS:")
    print(parser.to_json(results))
    
    # Тест 2: Поиск с find_usages = true
    print("\n=== ТЕСТ 2: Поиск с find_usages = true ===")
    usage_results = parser.search_metadata("Справочник.Валюты", find_usages=True, limit=1, config=config_name)
    print("USAGE RESULTS:")
    print(parser.to_json(usage_results))
    
    # Сохраняем результаты в JSON файл в каталоге dist
    output_data = {
        "configs": configs,
        "search_results": results,
        "usage_results": usage_results
    }
    
    output_file = os.path.join(dist_dir, "test_metadata_returner_results.json")
    print(f"Сохранение результатов в файл: {output_file}")
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"Результаты успешно сохранены в файл: {output_file}")
    except Exception as e:
        print(f"Ошибка при сохранении результатов: {e}")

if __name__ == "__main__":
    print("Запуск тестов MetadataReturner")
    test_search_metadata()
    print("Тесты завершены")
