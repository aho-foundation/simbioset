-- Схема базы данных для системы хранения
-- Расширена для поддержки базы знаний (ConceptNode) и параграфов для FAISS поиска

-- Таблица для хранения узлов знаний (ConceptNode)
-- Хранит структурированное дерево концептов: сообщения, вопросы, факты, решения
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT,
    content TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('question', 'answer', 'fact', 'opinion', 'solution', 'message', 'concept_reference', 'user_observation')),
    category TEXT NOT NULL CHECK (category IN ('threat', 'protection', 'conservation', 'neutral', 'metrics')),
    role TEXT CHECK (role IN ('user', 'assistant', 'system')),
    session_id TEXT,
    concept_node_id TEXT,  -- Reference to original concept node
    timestamp INTEGER NOT NULL,  -- Unix timestamp in milliseconds
    position_x REAL DEFAULT 0.0,
    position_y REAL DEFAULT 0.0,
    position_z REAL DEFAULT 0.0,
    expanded BOOLEAN DEFAULT FALSE,
    selected BOOLEAN DEFAULT FALSE,
    sources TEXT,  -- JSON array of Source objects
    metadata TEXT,  -- JSON для дополнительных полей
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE
);

-- Таблица для хранения связей parent-child между узлами (для быстрого доступа к childrenIds)
-- childrenIds можно вычислять через parent_id, но эта таблица ускоряет обратные запросы
CREATE TABLE IF NOT EXISTS node_children (
    parent_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    child_order INTEGER DEFAULT 0,  -- Порядок дочернего узла
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (parent_id, child_id),
    FOREIGN KEY (parent_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (child_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE
);

-- Индекс для быстрого поиска всех детей узла
CREATE INDEX IF NOT EXISTS idx_node_children_parent ON node_children(parent_id, child_order);
CREATE INDEX IF NOT EXISTS idx_node_children_child ON node_children(child_id);

-- Таблица для хранения параграфов
-- Параграфы - это разбитые на части документы или диалоги для векторного поиска
-- Каждый параграф может быть связан с узлом знания или документом
CREATE TABLE IF NOT EXISTS paragraphs (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    node_id TEXT,  -- Ссылка на узел знания (если параграф из узла)
    document_id TEXT,  -- Ссылка на документ (если параграф из документа)
    document_type TEXT NOT NULL CHECK (document_type IN ('chat', 'knowledge', 'document')),
    author TEXT,
    author_id INTEGER,
    paragraph_index INTEGER,  -- Порядковый номер параграфа в документе/узле
    timestamp INTEGER,  -- Unix timestamp in milliseconds
    -- Поля для классификации и проверки достоверности
    tags TEXT,  -- JSON массив множественных тегов классификации (например: ["ecosystem_vulnerability", "ecosystem_risk"])
    fact_check_result TEXT CHECK (fact_check_result IN ('true', 'false', 'partial', 'unverifiable', 'unknown')),
    fact_check_details TEXT,  -- JSON с деталями проверки
    location TEXT,
    time_reference TEXT,
    ecosystem_id TEXT,  -- Ссылка на основную экосистему параграфа (если относится к конкретной экосистеме)
    metadata TEXT,  -- JSON для дополнительных метаданных
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (ecosystem_id) REFERENCES ecosystems(id) ON DELETE SET NULL
);

-- Таблица для хранения документов (для исходных документов, которые парсятся на параграфы)
-- Поля:
--   id: уникальный идентификатор документа
--   title: название документа
--   content: полное содержимое документа (до парсинга)
--   source_url: URL источника документа
--   metadata: метаданные документа в формате JSON
--   created_at: время создания документа
--   updated_at: время последнего обновления документа
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT,
    content TEXT NOT NULL,
    source_url TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для хранения векторных представлений параграфов (для FAISS поиска)
-- Поля:
--   id: уникальный идентификатор вектора (обычно равен paragraph_id)
--   paragraph_id: ссылка на параграф, к которому принадлежит вектор
--   embedding: векторное представление в бинарном формате (BLOB для FAISS)
--   embedding_dimension: размерность вектора (для валидации)
--   faiss_index_id INTEGER,  -- ID в FAISS индексе (для быстрого поиска)
--   created_at: время создания вектора
--   updated_at: время последнего обновления вектора
CREATE TABLE IF NOT EXISTS vectors (
    id TEXT PRIMARY KEY,
    paragraph_id TEXT NOT NULL,
    embedding BLOB NOT NULL,  -- Нормализованный вектор для косинусного сходства
    embedding_dimension INTEGER NOT NULL,  -- Размерность вектора (обычно 384 для multilingual-MiniLM)
    faiss_index_id INTEGER,  -- ID в FAISS индексе (опционально, для синхронизации)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paragraph_id) REFERENCES paragraphs(id) ON DELETE CASCADE,
    UNIQUE(paragraph_id)  -- Один вектор на параграф
);

-- Таблица для хранения экосистем
-- КОНЦЕПЦИЯ: Экосистема = большой организм (метаболизм, гомеостаз, симбиотические связи)
-- Экосистемы могут быть вложенными (экосистема внутри экосистемы)
-- Поля:
--   id: уникальный идентификатор экосистемы
--   name: название экосистемы
--   description: описание экосистемы
--   location: географическое местоположение
--   parent_ecosystem_id: родительская экосистема (для вложенных структур)
--   scale: масштаб экосистемы (micro, local, regional, global)
--   metabolic_characteristics: JSON с характеристиками метаболизма экосистемы
--   homeostasis_indicators: JSON с показателями гомеостаза
--   created_at: время создания записи
--   updated_at: время последнего обновления
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
        'micro_habitat',  -- Микро-среда обитания (улей, гнездо, нора)
        'habitat',        -- Среда обитания (лес, озеро, поле)
        'landscape',      -- Ландшафтный уровень (несколько сред)
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

-- Таблица для хранения организмов-участников экосистемы
-- КОНЦЕПЦИЯ: Организм = маленькая экосистема (микробиом, симбионты)
-- Поля:
--   id: уникальный идентификатор организма
--   name: название организма (обычное)
--   scientific_name: научное название (латынь)
--   type: тип организма (растение, животное, гриб, бактерия, другое)
--   trophic_level: трофический уровень (producer, primary_consumer, secondary_consumer, tertiary_consumer, decomposer, omnivore)
--   biochemical_roles: JSON массив биохимических ролей
--   metabolic_pathways: JSON массив описаний метаболических путей
--   internal_ecosystem_id: ссылка на внутреннюю экосистему организма (микробиом)
--   paragraph_id: ссылка на параграф, где упомянут организм
--   context: контекст упоминания в тексте
--   classification_confidence: уверенность в классификации (0.0-1.0)
--   created_at: время создания записи
--   updated_at: время последнего обновления
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

-- Таблица для связи организмов с экосистемами (многие ко многим)
-- Организм может быть частью нескольких экосистем одновременно
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

-- Таблица для хранения симбиотических связей между организмами
-- Связи могут быть на разных уровнях: внутри организма (микробиом), между организмами, на уровне экосистемы
CREATE TABLE IF NOT EXISTS symbiotic_relationships (
    id TEXT PRIMARY KEY,
    organism1_id TEXT NOT NULL,
    organism2_id TEXT NOT NULL,
    relationship_type TEXT CHECK (relationship_type IN ('mutualism', 'commensalism', 'parasitism', 'competition', 'neutral')),
    description TEXT,  -- Описание симбиотической связи
    biochemical_exchange TEXT,  -- JSON с описанием биохимического обмена
    ecosystem_id TEXT,  -- Экосистема, в которой происходит взаимодействие
    level TEXT CHECK (level IN ('intra_organism', 'inter_organism', 'ecosystem')),  -- Уровень взаимодействия
    strength REAL DEFAULT 0.5,  -- Сила связи (0.0-1.0)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organism1_id) REFERENCES organisms(id) ON DELETE CASCADE,
    FOREIGN KEY (organism2_id) REFERENCES organisms(id) ON DELETE CASCADE,
    FOREIGN KEY (ecosystem_id) REFERENCES ecosystems(id) ON DELETE SET NULL,
    CHECK (organism1_id != organism2_id)
);

-- Таблица для хранения тегов классификации параграфов
-- Поля:
--   id: уникальный идентификатор тега (обычно равен name)
--   name: название тега (уникальное)
--   description: описание тега (для LLM и пользователей)
--   category: категория тега (например: 'ecosystem', 'threat', 'solution', 'observation')
--   usage_count: количество использований тега
--   examples: JSON массив примеров параграфов с этим тегом (для обучения LLM)
--   is_active: активен ли тег (неактивные теги не предлагаются LLM)
--   created_at: время создания тега
--   updated_at: время последнего обновления
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    category TEXT,
    usage_count INTEGER DEFAULT 0,
    examples TEXT,  -- JSON массив примеров
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для хранения метаданных
-- Поля:
--   id: уникальный идентификатор записи метаданных
--   key: ключ метаданных
--   value: значение метаданных
--   entity_id: идентификатор сущности, к которой относятся метаданные
--   entity_type: тип сущности (document, vector, user, session, node, paragraph)
--   created_at: время создания записи метаданных
--   updated_at: время последнего обновления записи метаданных
CREATE TABLE IF NOT EXISTS metadata (
    id TEXT PRIMARY KEY,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('document', 'vector', 'user', 'session', 'node', 'paragraph')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для улучшения производительности

-- Индексы для таблицы узлов знаний
CREATE INDEX IF NOT EXISTS idx_nodes_parent_id ON knowledge_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON knowledge_nodes(type);
CREATE INDEX IF NOT EXISTS idx_nodes_category ON knowledge_nodes(category);
CREATE INDEX IF NOT EXISTS idx_nodes_session_id ON knowledge_nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_nodes_timestamp ON knowledge_nodes(timestamp);
CREATE INDEX IF NOT EXISTS idx_nodes_created_at ON knowledge_nodes(created_at);
CREATE INDEX IF NOT EXISTS idx_nodes_updated_at ON knowledge_nodes(updated_at);
-- Составной индекс для поиска узлов по сессии и типу
CREATE INDEX IF NOT EXISTS idx_nodes_session_type ON knowledge_nodes(session_id, type);

-- Индексы для таблицы параграфов
CREATE INDEX IF NOT EXISTS idx_paragraphs_node_id ON paragraphs(node_id);
CREATE INDEX IF NOT EXISTS idx_paragraphs_document_id ON paragraphs(document_id);
CREATE INDEX IF NOT EXISTS idx_paragraphs_document_type ON paragraphs(document_type);
CREATE INDEX IF NOT EXISTS idx_paragraphs_ecosystem_id ON paragraphs(ecosystem_id);
CREATE INDEX IF NOT EXISTS idx_paragraphs_location ON paragraphs(location);
-- Индекс для поиска по тегам (используя JSON функции SQLite)
-- SQLite 3.38+ поддерживает JSON_EXTRACT для поиска в JSON массивах
CREATE INDEX IF NOT EXISTS idx_paragraphs_tags ON paragraphs(tags) WHERE tags IS NOT NULL;

-- Индексы для таблицы экосистем
CREATE INDEX IF NOT EXISTS idx_ecosystems_name ON ecosystems(name);
CREATE INDEX IF NOT EXISTS idx_ecosystems_location ON ecosystems(location);
CREATE INDEX IF NOT EXISTS idx_ecosystems_parent_id ON ecosystems(parent_ecosystem_id);
CREATE INDEX IF NOT EXISTS idx_ecosystems_scale ON ecosystems(scale);

-- Индексы для таблицы организмов
CREATE INDEX IF NOT EXISTS idx_organisms_name ON organisms(name);
CREATE INDEX IF NOT EXISTS idx_organisms_scientific_name ON organisms(scientific_name);
CREATE INDEX IF NOT EXISTS idx_organisms_type ON organisms(type);
CREATE INDEX IF NOT EXISTS idx_organisms_trophic_level ON organisms(trophic_level);
CREATE INDEX IF NOT EXISTS idx_organisms_paragraph_id ON organisms(paragraph_id);
CREATE INDEX IF NOT EXISTS idx_organisms_internal_ecosystem_id ON organisms(internal_ecosystem_id);

-- Индексы для таблицы связей организм-экосистема
CREATE INDEX IF NOT EXISTS idx_organism_ecosystems_organism_id ON organism_ecosystems(organism_id);
CREATE INDEX IF NOT EXISTS idx_organism_ecosystems_ecosystem_id ON organism_ecosystems(ecosystem_id);

-- Индексы для таблицы симбиотических связей
CREATE INDEX IF NOT EXISTS idx_symbiotic_relationships_organism1 ON symbiotic_relationships(organism1_id);
CREATE INDEX IF NOT EXISTS idx_symbiotic_relationships_organism2 ON symbiotic_relationships(organism2_id);
CREATE INDEX IF NOT EXISTS idx_symbiotic_relationships_ecosystem ON symbiotic_relationships(ecosystem_id);
CREATE INDEX IF NOT EXISTS idx_symbiotic_relationships_type ON symbiotic_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_symbiotic_relationships_level ON symbiotic_relationships(level);

-- Индексы для таблицы тегов
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);
CREATE INDEX IF NOT EXISTS idx_tags_is_active ON tags(is_active);
CREATE INDEX IF NOT EXISTS idx_tags_usage_count ON tags(usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_paragraphs_fact_check ON paragraphs(fact_check_result);
CREATE INDEX IF NOT EXISTS idx_paragraphs_timestamp ON paragraphs(timestamp);
CREATE INDEX IF NOT EXISTS idx_paragraphs_created_at ON paragraphs(created_at);
-- Составной индекс для поиска параграфов по документу и индексу
CREATE INDEX IF NOT EXISTS idx_paragraphs_doc_index ON paragraphs(document_id, paragraph_index);

-- Индексы для таблицы документов
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at);
CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url);

-- Индексы для таблицы векторов
CREATE INDEX IF NOT EXISTS idx_vectors_paragraph_id ON vectors(paragraph_id);
CREATE INDEX IF NOT EXISTS idx_vectors_faiss_index_id ON vectors(faiss_index_id);
CREATE INDEX IF NOT EXISTS idx_vectors_created_at ON vectors(created_at);
CREATE INDEX IF NOT EXISTS idx_vectors_updated_at ON vectors(updated_at);

-- Индексы для таблицы метаданных
CREATE INDEX IF NOT EXISTS idx_metadata_key ON metadata(key);
CREATE INDEX IF NOT EXISTS idx_metadata_entity_id ON metadata(entity_id);
CREATE INDEX IF NOT EXISTS idx_metadata_entity_type ON metadata(entity_type);
CREATE INDEX IF NOT EXISTS idx_metadata_created_at ON metadata(created_at);
CREATE INDEX IF NOT EXISTS idx_metadata_key_entity_id ON metadata(key, entity_id);

-- Индекс для поиска метаданных по типу сущности и ключу
CREATE INDEX IF NOT EXISTS idx_metadata_type_key ON metadata(entity_type, key);

-- ============================================================================
-- ПРИМЕЧАНИЯ ПО ИСПОЛЬЗОВАНИЮ СХЕМЫ
-- ============================================================================
--
-- 1. УЗЛЫ ЗНАНИЙ (knowledge_nodes):
--    - Хранят структурированное дерево концептов (ConceptNode)
--    - Связь parent-child через parent_id (иерархия)
--    - childrenIds хранятся в таблице node_children для быстрого доступа
--
-- 2. ПАРАГРАФЫ (paragraphs):
--    - Разбитые на части документы или диалоги для векторного поиска
--    - Могут быть связаны с узлом (node_id) или документом (document_id)
--    - Содержат классификацию и проверку достоверности
--
-- 3. ВЕКТОРЫ (vectors):
--    - Векторные представления параграфов для FAISS поиска
--    - Один вектор на параграф (UNIQUE constraint)
--    - embedding хранится как BLOB (бинарные данные)
--    - faiss_index_id для синхронизации с FAISS индексом
--
-- 4. РАБОТА С FAISS:
--    - При создании параграфа создается вектор через SentenceTransformer
--    - Вектор сохраняется в таблице vectors
--    - FAISS индекс строится из векторов для быстрого поиска
--    - Поиск: FAISS находит похожие векторы -> получаем paragraph_id -> получаем параграф
--
-- 5. ПАРСИНГ ДОКУМЕНТОВ И ДИАЛОГОВ:
--    - Документ парсится на параграфы (paragraphs с document_id)
--    - Диалог парсится на параграфы (paragraphs с node_id или document_id, document_type='chat')
--    - Каждый параграф получает embedding и сохраняется в vectors
--    - Узлы знаний могут ссылаться на параграфы через node_id
--
-- 6. МИГРАЦИЯ С JSON:
--    - knowledge_nodes заменяет JSONNodeRepository
--    - paragraphs хранят распарсенные данные для FAISS
--    - vectors обеспечивают векторный поиск
--    - node_children ускоряет доступ к childrenIds