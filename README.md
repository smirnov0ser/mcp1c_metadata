## Назначение:  
Сервис, в который ИИ обратится, когда нужно получить метаданные конфигурации - например список реквизитов или имя регистра по синониму  

**Область использования:**  
1. ИИ агенты в браузере, с использованием расширения MCP SuperAssistant  
2. ИИ агенты в IDE, например Cursor или Void 
Сам сервис запускается в Docker 

## Быстрый запуск:
docker run -it -p [ВнешнийПорт]:8000 -v [ПутьККаталогу]:/app/metadata  smirnov0ser/mcp1c_metadata:latest  

Параметры:  
[ВнешнийПорт] - Порт для обращения к сервису  
[ПутьККаталогу] - путь, где лежит файл "ОтчетПоКонфигурации.txt" - выгруженный из конфигурации 1С  

Например:  
docker run -it -p 8007:8000 -v C:/ERP/Report:/app/metadata mcp1c_metadata:latest

## Настройки ИИ:
**Инструкция для ИИ:**  
If you use configuration metadata, check its existence and structure using 'metadatasearch'  
  Use the full name in service, for example Example: 'Справочники.Номенклатура'. Set limit 1 for the first call  
  Use find_usages = true only if you need to find where an object is used  

**Пример mcp.json для указания в настрйоках MCP серверов:**  
{  
    "mcpServers": {    
      "mcp1c_metadata": {  
      "url": "http://localhost:8007/mcp",  
      "connection_id": "mcp1c_metadata_001"  
    }  
  }  
}  

## Сборка и запуск своего образа:  
**Сборка докер образа:**  
cd [Каталог]  
docker build -t [ИмяОбраза]:latest .  

Параметры:  
[Каталог] - каталог с проектом  
[ИмяОбраза] - имя нового или обновляемого образа  

Например:  
cd C:\mcp1c_metadata  
docker build -t mcp1c_metadata:latest .

**Запуск контейнера:**  
Аналогичен запуску контйнера быстрого варианта, но "smirnov0ser/mcp1c_metadata" заменяется на [ИмяОбраза] из шага сборки

Например:  
docker run -it -p 8007:8000 -v C:/ERP/Report:/app/metadata mcp1c_metadata:latest 
