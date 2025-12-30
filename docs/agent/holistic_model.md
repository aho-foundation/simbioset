# Холистическая модель организмов и экосистем

## Обзор

В системе реализована холистическая модель, которая рассматривает организмы и экосистемы как взаимосвязанные и взаимозависимые сущности. Ключевая концепция: **организм = маленькая экосистема**, а **экосистема = большой организм**.

## Философские основы

### Принцип холизма

Холизм в биологии и экологии предполагает, что:

1. **Организм = маленькая экосистема**
   - Каждый организм содержит внутреннюю экосистему (микробиом, эндосимбионты)
   - Организм не может существовать изолированно от своих симбионтов
   - Внутренние взаимодействия определяют функционирование организма

2. **Экосистема = большой организм**
   - Экосистема имеет собственный метаболизм и гомеостаз
   - Экосистема функционирует как единое целое
   - Симбиотические связи создают устойчивую систему

3. **Вложенность и множественная принадлежность**
   - Экосистемы могут быть вложенными (экосистема внутри экосистемы)
   - Организм может быть частью нескольких экосистем одновременно
   - Симбиотические связи существуют на разных уровнях

## Архитектура данных

### Схема базы данных

#### Таблица `ecosystems`

Экосистема как большой организм с метаболизмом и гомеостазом:

```sql
CREATE TABLE IF NOT EXISTS ecosystems (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    location TEXT,
    parent_ecosystem_id TEXT,  -- Для вложенных экосистем
    scale TEXT CHECK (scale IN (
        'molecular',      -- Молекулярный уровень (внутри клетки)
        'cellular',       -- Клеточный уровень
        'tissue',         -- Тканевый уровень
        'organ',          -- Органный уровень (микробиом органа)
        'organism',       -- Организменный уровень (микробиом организма)
        'micro_habitat',  -- Микро-среда обитания (улей, гнездо)
        'habitat',        -- Среда обитания (лес, озеро)
        'landscape',      -- Ландшафтный уровень
        'regional',       -- Региональный уровень
        'continental',    -- Континентальный уровень
        'global',         -- Глобальный уровень (биосфера)
        'planetary'       -- Планетарный уровень
    )),
    metabolic_characteristics TEXT,  -- JSON с характеристиками метаболизма
    homeostasis_indicators TEXT,  -- JSON с показателями гомеостаза
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_ecosystem_id) REFERENCES ecosystems(id) ON DELETE SET NULL
);
```

**Ключевые поля:**
- `metabolic_characteristics` - характеристики метаболизма экосистемы (циклы веществ, потоки энергии)
- `homeostasis_indicators` - показатели гомеостаза (устойчивость, баланс)
- `parent_ecosystem_id` - поддержка вложенных структур
- `scale` - масштаб экосистемы (12 уровней: от молекулярного до планетарного)

**Система масштабов (12 уровней):**
1. `molecular` - молекулярный уровень (внутри клетки, органеллы)
2. `cellular` - клеточный уровень (клетка как экосистема)
3. `tissue` - тканевый уровень (ткань как экосистема)
4. `organ` - органный уровень (микробиом органа: кишечник, кожа, легкие)
5. `organism` - организменный уровень (микробиом организма, эндосимбионты)
6. `micro_habitat` - микро-среда обитания (улей, гнездо, нора, дупло)
7. `habitat` - среда обитания (лес, озеро, поле, степь, болото)
8. `landscape` - ландшафтный уровень (несколько сред, экологический комплекс)
9. `regional` - региональный уровень (область, край, несколько ландшафтов)
10. `continental` - континентальный уровень (континент, крупный регион)
11. `global` - глобальный уровень (биосфера Земли)
12. `planetary` - планетарный уровень (планета как экосистема)

#### Таблица `organisms`

Организм как маленькая экосистема с внутренней экосистемой (микробиом):

```sql
CREATE TABLE IF NOT EXISTS organisms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    scientific_name TEXT,
    type TEXT CHECK (type IN ('растение', 'животное', 'гриб', 'бактерия', 'микроорганизм', 'другое')),
    trophic_level TEXT CHECK (trophic_level IN ('producer', 'primary_consumer', 'secondary_consumer', 'tertiary_consumer', 'decomposer', 'omnivore', 'unknown')),
    biochemical_roles TEXT,  -- JSON массив
    metabolic_pathways TEXT,  -- JSON массив
    internal_ecosystem_id TEXT,  -- Внутренняя экосистема организма (микробиом)
    paragraph_id TEXT,
    context TEXT,
    classification_confidence REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paragraph_id) REFERENCES paragraphs(id) ON DELETE CASCADE,
    FOREIGN KEY (internal_ecosystem_id) REFERENCES ecosystems(id) ON DELETE SET NULL
);
```

**Ключевые поля:**
- `internal_ecosystem_id` - ссылка на внутреннюю экосистему организма (микробиом, эндосимбионты)
- `biochemical_roles` - биохимические роли в обмене веществ
- `metabolic_pathways` - метаболические пути

#### Таблица `organism_ecosystems`

Связь организмов с экосистемами (многие ко многим):

```sql
CREATE TABLE IF NOT EXISTS organism_ecosystems (
    organism_id TEXT NOT NULL,
    ecosystem_id TEXT NOT NULL,
    role_in_ecosystem TEXT,  -- Роль организма в этой экосистеме
    interaction_type TEXT,  -- Тип взаимодействия (symbiotic, parasitic, competitive, neutral)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organism_id, ecosystem_id),
    FOREIGN KEY (organism_id) REFERENCES organisms(id) ON DELETE CASCADE,
    FOREIGN KEY (ecosystem_id) REFERENCES ecosystems(id) ON DELETE CASCADE
);
```

**Особенности:**
- Организм может быть частью нескольких экосистем одновременно
- Каждая связь имеет свою роль и тип взаимодействия

#### Таблица `symbiotic_relationships`

Симбиотические связи на разных уровнях:

```sql
CREATE TABLE IF NOT EXISTS symbiotic_relationships (
    id TEXT PRIMARY KEY,
    organism1_id TEXT NOT NULL,
    organism2_id TEXT NOT NULL,
    relationship_type TEXT CHECK (relationship_type IN ('mutualism', 'commensalism', 'parasitism', 'competition', 'neutral')),
    description TEXT,
    biochemical_exchange TEXT,  -- JSON с описанием биохимического обмена
    ecosystem_id TEXT,  -- Экосистема, в которой происходит взаимодействие
    level TEXT CHECK (level IN ('intra_organism', 'inter_organism', 'ecosystem')),
    strength REAL DEFAULT 0.5,  -- Сила связи (0.0-1.0)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organism1_id) REFERENCES organisms(id) ON DELETE CASCADE,
    FOREIGN KEY (organism2_id) REFERENCES organisms(id) ON DELETE CASCADE,
    FOREIGN KEY (ecosystem_id) REFERENCES ecosystems(id) ON DELETE SET NULL,
    CHECK (organism1_id != organism2_id)
);
```

**Уровни взаимодействия:**
- `intra_organism` - внутри организма (микробиом, эндосимбионты)
- `inter_organism` - между организмами
- `ecosystem` - на уровне экосистемы

## Примеры использования

### Пример 1: Организм с микробиомом

```python
# Создаем экосистему микробиома
microbiome_ecosystem = ecosystem_service.create_ecosystem(
    name="Микробиом кишечника человека",
    scale="micro",
    description="Бактериальная экосистема кишечника",
    metabolic_characteristics={
        "primary_functions": ["переваривание", "синтез витаминов", "иммунная защита"],
        "energy_flow": "органические вещества → метаболиты"
    }
)

# Создаем организм человека
human_organism = organism_service.save_organisms_for_paragraph(
    paragraph_id="para_123",
    organisms=[{
        "name": "человек",
        "scientific_name": "Homo sapiens",
        "type": "животное",
        "internal_ecosystem_id": microbiome_ecosystem,  # Связь с микробиомом
        "trophic_level": "omnivore"
    }]
)
```

### Пример 2: Вложенные экосистемы

```python
# Глобальная экосистема
biosphere = ecosystem_service.create_ecosystem(
    name="Биосфера",
    scale="global"  # Глобальный уровень
)

# Региональная экосистема
forest = ecosystem_service.create_ecosystem(
    name="Смешанный лес",
    scale="habitat",  # Среда обитания
    parent_ecosystem_id=biosphere,  # Вложена в биосферу
    location="Московская область"
)

# Микробиом дерева
tree_microbiome = ecosystem_service.create_ecosystem(
    name="Микробиом корней дуба",
    scale="organ",  # Органный уровень (корни как орган)
    parent_ecosystem_id=forest  # Вложена в лес
)
```

### Пример 3: Множественная принадлежность

```python
# Организм может быть частью нескольких экосистем
bee = organism_service.save_organisms_for_paragraph(
    paragraph_id="para_456",
    organisms=[{
        "name": "пчела",
        "scientific_name": "Apis mellifera",
        "type": "животное",
        "trophic_level": "primary_consumer"
    }]
)

# Пчела в улье (социальная экосистема)
hive_ecosystem = ecosystem_service.create_ecosystem(
    name="Улей",
    scale="micro_habitat"  # Микро-среда обитания
)
ecosystem_service.link_organism_to_ecosystem(
    organism_id=bee[0],
    ecosystem_id=hive_ecosystem,
    role_in_ecosystem="опылитель",
    interaction_type="symbiotic"
)

# Пчела в лесу (региональная экосистема)
ecosystem_service.link_organism_to_ecosystem(
    organism_id=bee[0],
    ecosystem_id=forest,
    role_in_ecosystem="опылитель",
    interaction_type="symbiotic"
)
```

### Пример 4: Симбиотические связи на разных уровнях

```python
# Внутри организма (микробиом)
symbiotic_service.create_relationship(
    organism1_id="human",
    organism2_id="lactobacillus",
    relationship_type="mutualism",
    level="intra_organism",
    ecosystem_id=microbiome_ecosystem,
    biochemical_exchange={
        "human_provides": ["питательные вещества", "среда обитания"],
        "bacteria_provides": ["витамины", "защита от патогенов"]
    }
)

# Между организмами
symbiotic_service.create_relationship(
    organism1_id="bee",
    organism2_id="flower",
    relationship_type="mutualism",
    level="inter_organism",
    ecosystem_id=forest,
    biochemical_exchange={
        "bee_provides": ["опыление"],
        "flower_provides": ["нектар", "пыльца"]
    }
)
```

## API и сервисы

### EcosystemService

Сервис для работы с экосистемами:

```python
from api.storage.ecosystem_service import EcosystemService

ecosystem_service = EcosystemService(db_manager)

# Создание экосистемы
ecosystem_id = ecosystem_service.create_ecosystem(
    name="Лес",
    scale="local",
    location="Московская область"
)

# Связывание организма с экосистемой
ecosystem_service.link_organism_to_ecosystem(
    organism_id="org_123",
    ecosystem_id=ecosystem_id,
    role_in_ecosystem="продуцент",
    interaction_type="symbiotic"
)

# Получение организмов в экосистеме
organisms = ecosystem_service.get_organisms_in_ecosystem(ecosystem_id)

# Получение экосистем для организма
ecosystems = ecosystem_service.get_ecosystems_for_organism("org_123")
```

### OrganismService

Сервис для работы с организмами (обновлен для поддержки внутренних экосистем):

```python
from api.storage.organism_service import OrganismService

organism_service = OrganismService(db_manager)

# Сохранение организма с внутренней экосистемой
organism_ids = organism_service.save_organisms_for_paragraph(
    paragraph_id="para_123",
    organisms=[{
        "name": "человек",
        "internal_ecosystem_id": microbiome_ecosystem_id,  # Ссылка на микробиом
        "trophic_level": "omnivore"
    }]
)
```

### Детекторы

#### EcosystemDetector

Обнаруживает экосистемы в тексте, используя данные локализации:

```python
from api.detect.ecosystem_scaler import detect_ecosystems
from api.detect.localize import extract_location_and_time

# Извлекаем локализацию из текста
location_data = extract_location_and_time(
    "В лесу Московской области обитают различные организмы."
)

# Обнаруживаем экосистемы, передавая данные локализации
ecosystems = await detect_ecosystems(
    "В лесу обитают различные организмы. Микробиом кишечника помогает переваривать пищу.",
    location_data=location_data
)
# Вернет:
# [
#   {"name": "лес", "scale": "local", "location": "Московская область", ...},
#   {"name": "микробиом кишечника", "scale": "micro", ...}
# ]
```

**Особенности:**
- Автоматически использует данные локализации из `extract_location_and_time`
- Если локализация не указана в тексте, но извлечена детектором - использует её
- Передает временные ссылки для контекста

#### OrganismDetector

Обнаруживает организмы с учетом холизма:

```python
from api.detect.organism_detector import detect_organisms

organisms = await detect_organisms(
    "Человек с микробиомом кишечника взаимодействует с лесом."
)
# Вернет организмы, включая упоминания их внутренних экосистем
```

## Интеграция с классификацией

### Обновленные промпты

Промпты для LLM обновлены для учета холизма:

1. **`organism_detector.txt`** - учитывает, что организм = экосистема
2. **`organism_classifier.txt`** - классифицирует с учетом внутренних экосистем
3. **`ecosystem_scaler.txt`** - обнаруживает экосистемы как организмы

### Автоматическая классификация

При сохранении параграфа автоматически:

1. Обнаруживаются организмы и экосистемы
2. Классифицируются организмы по биологической роли
3. Определяются внутренние экосистемы (микробиом)
4. Устанавливаются связи организм-экосистема
5. Выявляются симбиотические связи на разных уровнях

## Преимущества холистической модели

1. **Реалистичное представление**
   - Учитывает, что организм не может существовать изолированно
   - Отражает реальную сложность экосистем

2. **Множественная принадлежность**
   - Организм может быть частью нескольких экосистем
   - Учитывает сезонные миграции, жизненные циклы

3. **Вложенность**
   - Поддержка вложенных структур (микробиом → организм → экосистема)
   - Иерархическое представление

4. **Симбиотические связи**
   - Связи на разных уровнях (внутри организма, между организмами, на уровне экосистемы)
   - Биохимический обмен веществ

5. **Метаболизм и гомеостаз**
   - Экосистема как организм с метаболизмом
   - Показатели гомеостаза для устойчивости

## Применение в проекте

Холистическая модель используется для:

1. **Поиска симбиотических связей**
   - Поиск взаимовыгодных взаимодействий
   - Анализ биохимического обмена

2. **Проектирования симбиотических взаимодействий**
   - Моделирование новых связей
   - Оптимизация существующих

3. **Анализа экосистем**
   - Изучение метаболизма экосистем
   - Мониторинг гомеостаза

4. **Исследования микробиомов**
   - Внутренние экосистемы организмов
   - Взаимодействия внутри организма

## Заключение

Холистическая модель позволяет более точно и реалистично представлять сложные биологические и экологические системы, учитывая их взаимосвязи и взаимозависимости на разных уровнях организации.

