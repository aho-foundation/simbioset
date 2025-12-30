# AgREE Agent: Агентная система для дополнения графа знаний

## Обзор

AgREE (Agentic Reasoning for Knowledge Graph Completion on Emerging Entities) - это агентная система для автоматического дополнения графа знаний новыми сущностями и связями. Система реализует подход, описанный в статье [AgREE: Agentic Reasoning for Knowledge Graph Completion on Emerging Entities](https://arxiv.org/pdf/2508.04118).

## Архитектура

### Основные компоненты

1. **AgREEAgent** (`api/kb/agree_agent.py`)
   - Главный агентный модуль
   - Управляет итеративным поиском информации
   - Генерирует триплеты для дополнения графа знаний

2. **SymbioticService** (`api/storage/symbiotic_service.py`)
   - Сервис для работы с симбиотическими связями
   - Создание, поиск и управление связями между организмами

3. **Промпт** (`api/prompts/agree_agent.txt`)
   - Шаблон для LLM reasoning
   - Генерация триплетов на основе найденной информации

## Рабочий процесс

### 1. Итеративный поиск информации

Агент выполняет следующие шаги:

1. **Проверка существования организма**
   - Ищет организм в БД по названию
   - Если не найден - создает новый

2. **Классификация организма**
   - Использует `classify_organism_role` для определения трофического уровня
   - Определяет биохимические роли и метаболические пути

3. **Итеративный поиск** (до `max_iterations` раз):
   - Генерирует поисковый запрос
   - Выполняет веб-поиск через `WebSearchService`
   - Анализирует найденную информацию через LLM
   - Генерирует триплеты (организм → связь → организм/экосистема)
   - Оценивает достаточность информации
   - Если недостаточно - продолжает поиск

4. **Создание триплетов**
   - Сохраняет симбиотические связи в `symbiotic_relationships`
   - Связывает организмы с экосистемами через `organism_ecosystems`

### 2. Генерация триплетов

Триплеты генерируются в формате:
```
(организм1, тип_связи, организм2)
(организм, роль, экосистема)
```

**Типы связей:**
- `mutualism` - мутуализм
- `commensalism` - комменсализм
- `parasitism` - паразитизм
- `competition` - конкуренция
- `neutral` - нейтральное взаимодействие

**Уровни взаимодействия:**
- `intra_organism` - внутри организма (микробиом)
- `inter_organism` - между организмами
- `ecosystem` - на уровне экосистемы

## API

### Endpoint: `/api/kb/agree/complete`

**Метод:** `POST`

**Тело запроса:**
```json
{
  "organism_name": "пчела",
  "organism_type": "животное",
  "context": "опыляет цветы"
}
```

**Ответ:**
```json
{
  "success": true,
  "organism_id": "org_...",
  "triplets_created": ["symb_1", "symb_2"],
  "iterations": 3,
  "final_info": {
    "known_info": {...},
    "retrieved_info_count": 9
  }
}
```

## Использование

### Программное использование

```python
from api.kb.agree_agent import AgREEAgent
from api.storage.symbiotic_service import SymbioticService
from api.storage.organism_service import OrganismService
from api.storage.ecosystem_service import EcosystemService

# Создаем сервисы
symbiotic_service = SymbioticService(db_manager)
organism_service = OrganismService(db_manager)
ecosystem_service = EcosystemService(db_manager)

# Создаем агента
agent = AgREEAgent(
    symbiotic_service=symbiotic_service,
    organism_service=organism_service,
    ecosystem_service=ecosystem_service,
)

# Запускаем дополнение графа знаний
result = await agent.complete_knowledge_for_organism(
    organism_name="пчела",
    organism_type="животное",
    context="опыляет цветы"
)
```

### HTTP запрос

```bash
curl -X POST http://localhost:8000/api/kb/agree/complete \
  -H "Content-Type: application/json" \
  -d '{
    "organism_name": "пчела",
    "organism_type": "животное",
    "context": "опыляет цветы"
  }'
```

## Интеграция с существующими сервисами

AgREE Agent интегрируется с:

- **detect.organism_detector** - для обнаружения организмов в тексте
- **classify.organism_classifier** - для классификации организмов
- **detect.web_search** - для веб-поиска информации
- **storage.organism_service** - для работы с организмами
- **storage.ecosystem_service** - для работы с экосистемами
- **storage.symbiotic_service** - для работы с симбиотическими связями

## Оценка достаточности информации

Агент считает информацию достаточной, если найдены:

1. Научное название организма
2. Трофический уровень
3. Хотя бы одна симбиотическая связь
4. Экосистема обитания

Если информация недостаточна, агент продолжает поиск до достижения `max_iterations`.

## Ограничения

- Максимальное количество итераций поиска: 5 (по умолчанию)
- Зависимость от качества веб-поиска
- Требуется LLM для reasoning и генерации триплетов

## Будущие улучшения

- [ ] Кэширование результатов поиска
- [ ] Поддержка batch-обработки нескольких организмов
- [ ] Улучшенная оценка достаточности информации
- [ ] Поддержка различных источников информации (не только веб-поиск)
- [ ] Метрики качества дополнения графа знаний

## Ссылки

- [AgREE: Agentic Reasoning for Knowledge Graph Completion on Emerging Entities](https://arxiv.org/pdf/2508.04118)
- [Документация по графу знаний](./holistic_model.md)
- [API документация](./README.md)
