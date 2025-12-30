# RAG и Long-term Memory: Лучшие практики для двух графов

## Архитектура двух графов

В системе существует два взаимосвязанных графа:

### 1. Граф концептуальных узлов (Concept Nodes Graph)
- **Структура**: Дерево сообщений/концептов (`knowledge_nodes`)
- **Назначение**: Структурированное хранение диалогов, вопросов, фактов
- **Связи**: Parent-child иерархия через `node_children`
- **Векторизация**: Параграфы связаны через `node_id` → FAISS поиск

### 2. Граф симбиотических связей (Symbiotic Relationships Graph)
- **Структура**: Граф организмов и их связей (`organisms` → `symbiotic_relationships` → `organisms/ecosystems`)
- **Назначение**: Биологические знания о взаимодействиях
- **Связи**: Типизированные связи (mutualism, commensalism, parasitism, competition)
- **Метаданные**: Уровни взаимодействия (intra_organism, inter_organism, ecosystem)

## Проблема: Разделение знаний

**Текущая ситуация:**
- Векторный поиск работает только с параграфами (текстовый контент)
- Граф симбиотических связей хранится отдельно (структурированные данные)
- Нет связи между текстовым контекстом и биологическими знаниями

**Последствия:**
- RAG не использует структурированные знания о организмах
- Long-term memory не учитывает биологические связи
- Контекст для LLM не включает граф симбиотических связей

## Решение: Hybrid RAG с Graph-Augmented Retrieval

### 1. Двухэтапный RAG Pipeline

```python
async def hybrid_rag_retrieval(
    query: str,
    session_id: str,
    location: Optional[str] = None,
    ecosystem_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hybrid RAG: векторный поиск + граф симбиотических связей
    
    Returns:
        {
            "text_context": [...],  # Параграфы из векторного поиска
            "graph_context": {...},  # Граф симбиотических связей
            "organisms": [...],  # Найденные организмы
            "relationships": [...]  # Связанные отношения
        }
    """
    # Этап 1: Векторный поиск параграфов
    paragraphs = await vector_search(query, session_id, top_k=10)
    
    # Этап 2: Извлечение организмов из найденных параграфов
    organisms = extract_organisms_from_paragraphs(paragraphs)
    
    # Этап 3: Расширение через граф симбиотических связей
    graph_context = expand_via_symbiotic_graph(organisms, depth=2)
    
    # Этап 4: Объединение контекста
    return combine_contexts(paragraphs, graph_context)
```

### 2. Graph-Augmented Context Builder

**Принцип**: Используем граф симбиотических связей для расширения векторного поиска.

```python
class SimbioticGraphContextBuilder:
    """Строитель контекста с использованием графа симбиотических связей."""
    
    async def build_context(
        self,
        query: str,
        paragraphs: List[Paragraph],
        max_organisms: int = 10,
        relationship_depth: int = 2,
    ) -> str:
        """
        Строит контекст, объединяя векторный поиск и граф симбиотических связей.
        
        Args:
            query: Поисковый запрос
            paragraphs: Найденные параграфы из векторного поиска
            max_organisms: Максимальное количество организмов для расширения
            relationship_depth: Глубина обхода графа связей
        
        Returns:
            Объединенный контекст для LLM
        """
        # 1. Извлекаем организмы из найденных параграфов
        organisms = self._extract_organisms_from_paragraphs(paragraphs)
        
        # 2. Находим связанные организмы через граф
        related_organisms = self._expand_via_graph(
            organisms, 
            depth=relationship_depth
        )
        
        # 3. Получаем симбиотические связи
        relationships = self._get_relationships_for_organisms(
            organisms + related_organisms
        )
        
        # 4. Формируем структурированный контекст
        context_parts = []
        
        # Текстовый контекст из параграфов
        context_parts.append("### Текстовый контекст:")
        for para in paragraphs[:5]:
            context_parts.append(f"- {para.content[:500]}")
        
        # Граф симбиотических связей
        context_parts.append("\n### Симбиотические связи:")
        for rel in relationships[:10]:
            org1 = self._get_organism_name(rel['organism1_id'])
            org2 = self._get_organism_name(rel['organism2_id'])
            context_parts.append(
                f"- {org1} --[{rel['relationship_type']}]--> {org2}"
            )
        
        return "\n".join(context_parts)
```

### 3. Long-term Memory Strategy

**Проблема**: Как сохранять знания в долгосрочной памяти?

**Решение**: Трехуровневая память:

#### Уровень 1: Эпизодическая память (Episodic Memory)
- **Хранение**: Параграфы с временными метками
- **Использование**: Векторный поиск по времени и контенту
- **Пример**: "Вчера пользователь упоминал пчел в лесу"

#### Уровень 2: Семантическая память (Semantic Memory)
- **Хранение**: Граф симбиотических связей
- **Использование**: Структурированные знания о организмах
- **Пример**: "Пчелы опыляют цветы (mutualism)"

#### Уровень 3: Процедурная память (Procedural Memory)
- **Хранение**: Паттерны взаимодействий в графе концептуальных узлов
- **Использование**: Повторяющиеся вопросы, решения, факты
- **Пример**: "Пользователь часто спрашивает о симбиозе"

### 4. Интеграция двух графов

**Ключевая идея**: Связываем параграфы с организмами через `ecosystem_id` и `metadata`.

```python
# При сохранении параграфа
paragraph.metadata = {
    "organisms": ["org_1", "org_2"],  # Ссылки на организмы
    "ecosystem_id": "eco_1",  # Ссылка на экосистему
    "relationships": ["symb_1", "symb_2"]  # Ссылки на связи
}

# При поиске
def enhanced_retrieval(query: str):
    # 1. Векторный поиск
    paragraphs = vector_search(query)
    
    # 2. Извлекаем организмы из metadata
    organism_ids = extract_organism_ids(paragraphs)
    
    # 3. Расширяем через граф
    related_paragraphs = find_paragraphs_by_organisms(organism_ids)
    
    return paragraphs + related_paragraphs
```

## Рекомендации по реализации

### 1. Расширение Paragraph metadata

```python
# При сохранении параграфа добавляем ссылки на организмы
paragraph.metadata = {
    "organism_ids": ["org_1", "org_2"],
    "ecosystem_id": "eco_1",
    "relationship_ids": ["symb_1"],
    "node_id": "node_123"  # Связь с концептуальным узлом
}
```

### 2. Graph Traversal для RAG

```python
def graph_traversal_rag(
    query: str,
    start_organisms: List[str],
    max_depth: int = 2,
) -> List[Paragraph]:
    """
    Обходит граф симбиотических связей для поиска релевантных параграфов.
    """
    visited = set()
    relevant_paragraphs = []
    
    def traverse(organism_id: str, depth: int):
        if depth > max_depth or organism_id in visited:
            return
        
        visited.add(organism_id)
        
        # Находим параграфы, связанные с организмом
        paragraphs = find_paragraphs_by_organism(organism_id)
        relevant_paragraphs.extend(paragraphs)
        
        # Находим связанные организмы
        relationships = get_relationships_for_organism(organism_id)
        for rel in relationships:
            other_org = rel['organism2_id'] if rel['organism1_id'] == organism_id else rel['organism1_id']
            traverse(other_org, depth + 1)
    
    for org_id in start_organisms:
        traverse(org_id, 0)
    
    return relevant_paragraphs
```

### 3. Hybrid Search: Vector + Graph

```python
async def hybrid_search(
    query: str,
    session_id: str,
    vector_weight: float = 0.7,
    graph_weight: float = 0.3,
) -> List[Paragraph]:
    """
    Комбинирует векторный поиск и графовый обход.
    """
    # Векторный поиск
    vector_results = await vector_search(query, session_id, top_k=20)
    
    # Извлекаем организмы
    organisms = extract_organisms(vector_results)
    
    # Графовый обход
    graph_results = graph_traversal_rag(query, organisms, max_depth=2)
    
    # Объединяем и ранжируем
    combined = combine_and_rank(
        vector_results, 
        graph_results,
        vector_weight=vector_weight,
        graph_weight=graph_weight
    )
    
    return combined[:10]
```

### 4. Long-term Memory через Graph Embeddings

**Идея**: Используем графовые эмбеддинги для долгосрочной памяти.

```python
def create_graph_embedding(organism_id: str) -> np.ndarray:
    """
    Создает эмбеддинг организма на основе его позиции в графе.
    """
    # Получаем соседей в графе
    neighbors = get_relationships_for_organism(organism_id)
    
    # Создаем текстовое представление графа
    graph_text = f"Organism: {get_organism_name(organism_id)}\n"
    graph_text += "Relationships:\n"
    for rel in neighbors:
        other_org = get_organism_name(rel['organism2_id'])
        graph_text += f"  - {rel['relationship_type']} with {other_org}\n"
    
    # Векторизуем
    return create_embedding(graph_text)
```

## Практические рекомендации

### ✅ DO (Делай)

1. **Используй оба графа для RAG**
   - Векторный поиск для текстового контекста
   - Граф симбиотических связей для структурированных знаний

2. **Связывай параграфы с организмами**
   - Добавляй `organism_ids` в `paragraph.metadata`
   - Используй `ecosystem_id` для фильтрации

3. **Расширяй контекст через граф**
   - При нахождении организма в параграфе - ищи связанные организмы
   - Используй граф для объяснения связей

4. **Кэшируй графовые запросы**
   - Граф симбиотических связей меняется редко
   - Кэшируй результаты обхода графа

### ❌ DON'T (Не делай)

1. **Не дублируй информацию**
   - Не храни текстовое описание организма и в параграфе, и в графе
   - Используй ссылки (`organism_id`)

2. **Не игнорируй граф при RAG**
   - Векторный поиск не знает о биологических связях
   - Всегда расширяй через граф

3. **Не смешивай уровни абстракции**
   - Параграфы = текстовый контент
   - Граф = структурированные знания
   - Не пытайся хранить граф в параграфах

## Пример реализации

См. `api/kb/graph_augmented_rag.py` (будущий файл) для полной реализации.

## Ссылки

- [AgREE Agent](./agree_agent.md) - агентная система для дополнения графа
- [Holistic Model](./holistic_model.md) - холистическая модель организмов
- [Storage Analysis](./storage_analysis.md) - анализ хранилища
