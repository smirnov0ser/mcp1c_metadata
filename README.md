**Назначение:**  
Сервис, в который ИИ обратится, когда нужно получить метаданные конфигурации - например список реквизитов или имя регистра по синониму  

**Область использования:**  
1. ИИ агенты в браузере, с использованием расширения MCP SuperAssistant  
2. ИИ агенты в IDE, например Cursor или Void

**Сборка докер образа:**  
cd [Каталог]  
docker build -t [ИмяОбраза]:latest .  
  
[Каталог] - каталог с проектом  
[ИмяОбраза] - имя нового или обновляемого образа  

Например:  
cd C:\mcp1c_metadata  
docker build -t mcp1c_metadata:latest .

**Запуск контейнера:**  
docker run -it -p [ВнешнийПорт]:8000 -v [ПутьККаталогу]:/app/metadata [Имяобраза]:latest  

[ВнешнийПорт] - Порт для обращения к сервису  
[ПутьККаталогу] - путь, где лежит файл "ОтчетПоКонфигурации.txt" - выгруженный из конфигурации 1С
[ИмяОбраза] - имя нового или обновляемого образа  

Например:  
docker run -it -p 8007:8000 -v C:/ERP/Report:/app/metadata mcp1c_metadata:latest 


**Инструкция для ИИ:**  
If you use configuration metadata, check its existence and structure using 'mcp1c_metadata'  

**Пример mcp.json:**  
{  
    "mcpServers": {    
      "mcp1c_metadata": {  
      "url": "http://localhost:8007/mcp",  
      "connection_id": "mcp1c_metadata_001"  
    }  
  }  
}  
