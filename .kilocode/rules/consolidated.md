# 🔧 Консолидированные правила разработки

## 🔄 Main Rules
- НЕ делать `git commit` без просьбы
- все изменения проверять mypy, pytest
- дописывать новую патч-версию с изменением в CHANGELOG.md при успешном завершении

## 🏗️ Architecture & Code Quality
- **Single Responsibility**: Одна функция = одна ответственность
- **Pure Functions**: Предсказуемые, тестируемые функции
- **Composition > Inheritance**: Переиспользование через композицию
- **Explicit > Implicit**: Явные зависимости и побочные эффекты
- **Extended thinking**: Включай для сложных задач кодирования

## 🎯 Philosophy
- **KISS**: Максимальная простота - сложность = баги
- **DRY**: Переиспользование > создание нового
- **YAGNI**: Решаем текущие проблемы, не гадаем о будущих
- **Fail Fast**: Ошибки должны быть видны сразу

## 🔍 Workflow поиска (против гниения)
```bash
1. grep_search — точные символы/строки
2. codebase_search — семантика/функциональность
3. read_file — изучение найденного
4. Только потом создание нового
```

## 🤖 Sonnet 4.5 Agent Workflow
- **Parallel exploration**: Множественные спекулятивные поиски одновременно
- **Batch file reading**: Несколько файлов для контекста сразу
- **Incremental focus**: Несколько задач параллельно, не все сразу
- **State preservation**: Сохранение прогресса в файлах между сессиями

## 📊 Truth Sources
- **Доверяй только тестам** - E2E, интеграционные, unit
- **Измеряй, не гадай** - метрики > предположения
- **Верифицируй утверждения** - 🤷 для недоказанного
- **Rollback при регрессии** - новые ошибки = откат, помечай его 🚑

## 🧠 Anti-Context-Decay Protocol
🤖 Research: "Lost in the Middle" - критичная информация В НАЧАЛО
- **Structure**: 🎯→✅→🔧→📝 (цель→действие→код→результат)
- **Cognition**: Несколько связанных задач параллельно (Sonnet 4.5 improvement)
- **Memory**: ТОЛЬКО пользовательские предпочтения
- **Visual**: Маркеры для быстрого сканирования
- **Context tracking**: Модель отслеживает использование токенов автоматически

## 📝 Documentation (обязательно)
```
CHANGELOG.md — новая версия сверху
features.md — изменения функциональности
docs/progress/<timestamp>-название.md — отчет о сессии
```

## 🎭 Communication Style
- **Язык**: Русский для общения, английский для кода
- **Уровень**: Экспертный, без "разжевывания"
- **Формат**: Конкретные решения → быстрая реализация
- **Concise & direct**: Факты вместо многословия
- **Fact-based**: Точные отчеты о прогрессе

## 🔒 Security & Performance
- **Input validation**: Клиент И сервер
- **XSS protection**: Санитизация HTML
- **JWT**: + refresh tokens
- **Bundle**: < 500KB gzipped
- **LCP**: < 2.5s, **FID**: < 100ms

## 📝 Descriptive Coding
- **Add comments**: Код должен быть качественно описан
- **Add doctests**: Примеры для стабильности
- **TODO and FIXME**: Оставлять и решать задачи
- **Less noise**: Без капса и эмоджи в комментариях кода
- **No dummy code**: Не добавлять заглушки с комментариями типа "in a real implementation" или "now is simple inthe future we will" или "In production, this would", давать полноценную реализацию

## ⚡ SolidJS Patterns
IMPORTANT: follow biomejs linter rules!

### ⚡ Quick Quality Gates
```
- [ ] Нет async createEffect
- [ ] Props через props.*, НЕ деструктуризация
- [ ] createResource для async + initialValue
- [ ] Логи лаконичные (НЕ дампы объектов)
- [ ] props.data из route.load может быть Promise!
- [ ] npm run fix && npm run format && npm run typecheck
```

### 🚫 НИКОГДА не делай
```typescript
// ❌ ASYNC createEffect - ломает гидрацию
createEffect(async () => await fetchData())

// ❌ Деструктуризация PROPS - теряет реактивность
const { data } = props // ❌ НЕТ!
const Component = ({ data }: Props) => {} // ❌ НЕТ!

// ❌ Window в init - SSR error
const [width] = createSignal(window.innerWidth)

// ❌ Нестабильные ключи
{ id: Math.random(), text: 'Item' }

// ❌ JSX в пропсах - вызывает гидрационный мисматч!
<Component header={<h2>{title}</h2>} /> // ПЛОХО!
<Row3 header={<div>{text}</div>} />     // ПЛОХО!

// ❌ ИЗБЫТОЧНАЯ МЕМОИЗАЦИЯ (Главная Ошибка!)
const simpleValue = createMemo(() => props.data || []) // ПЛОХО!
const isActive = createMemo(() => status() === 'active') // ПЛОХО!
const finalData = createMemo(() => ssrData || clientData) // ПЛОХО!
const result = createMemo(() => condition ? a : b) // ПЛОХО!

// ❌ createResource для перезапроса SSR данных - показывает индикатор загрузки
const [data] = createResource(() => 'key', () => loadData())

// ❌ typeof window для клиентского рендера - ненадежно для гидрации
<Show when={typeof window !== 'undefined'}>
```

### ✅ Правильные паттерны

#### Props реактивность
```typescript
// ✅ ВСЕГДА props.*
const Component = (props: Props) => {
  return <div>{props.data}</div> // Реактивно!
}

// ✅ В функциях тоже props.*
createEffect(() => console.log(props.loading))
```

#### Async данные
```typescript
// ✅ ЕДИНСТВЕННЫЙ способ - createResource
const [data] = createResource(
  () => params(),
  async (params) => loadData(params),
  { initialValue: props.data?.items } // SSR данные
)
```

#### 🚨 SSR + гидрация (КРИТИЧНО!)
```typescript
// ❌ НИКОГДА - props.data может быть Promise в SolidStart!
const routeData = () => props.data
const items = routeData()?.featuredShouts // ОШИБКА если Promise!

// ✅ ПРАВИЛЬНО - createResource для разрешения Promise
export default function Page(props: RouteSectionProps<Data>) {
  const [routeData] = createResource(
    () => props.data,
    async (data) => data instanceof Promise ? await data : data,
    {
      // ✅ КРИТИЧНО: initialValue для стабильной гидрации
      initialValue: typeof props.data === 'object' && !('then' in props.data)
        ? props.data
        : { items: [], users: [] } // Fallback структура
    }
  )

  return <Show when={routeData()}>{/* контент */}</Show>
}

// ✅ ПРЯМОЕ использование SSR данных (БЕЗ createResource)
export default function Page(props: RouteSectionProps<Data>) {
  const { setItems } = useContext()

  // ✅ Добавляем SSR данные в контекст синхронно
  if (props.data?.items?.length) {
    setItems(props.data.items)
  }

  return <Component items={props.data?.items || []} />
}
```

#### 🛡️ Клиентский рендер без гидрационных мисматчей
```typescript
// ✅ isServer для детекта SSR
<Show when={!isServer}>
  <ClientOnlyComponent />
</Show>
```

#### Effects правильно
```typescript
// ✅ Async в onMount (клиентский)
onMount(async () => {
  const data = await fetchData()
  setData(data)
})

// ✅ Циклические зависимости с defer
createEffect(on(
  () => feed()[props.slug],
  (data) => { if (data) setProcessed(data) },
  { defer: true }
))
```

### 🔧 Быстрые исправления
1. **`const { data } = props`** → `props.data`
2. **JSX в пропсах** → встроить в компонент
3. **typeof window** → `onMount()` флаг
4. **createResource для SSR** → прямое `props.data`
5. **избыточный createMemo** → простые функции

### 🚨 ЗОЛОТОЕ ПРАВИЛО МЕМОИЗАЦИИ
**Если операция занимает меньше 1мс - используй простую функцию!**

**🎯 createMemo только если:** циклы + фильтрация + >1мс

### 💡 Мемоизация (НЕ как React)
```typescript
// ✅ createMemo ТОЛЬКО для дорогих операций
const filtered = createMemo(() =>
  items().filter(fn).sort(fn).map(fn) // Циклы!
)

// ❌ Простые операции - используй функции
const name = () => user()?.name // Автореактивно!
const sum = () => a() + b()
const isActive = () => status() === 'active'
```

### 🎯 GraphQL паттерны
```typescript
// ✅ Кешируемые загрузчики
export const loadData = () => createCacheableLoader(query, {}, true)

// ✅ Приватные данные БЕЗ кеша
export const loadPrivate = (client) => async () => {
  if (!client) return undefined
  return await client.query(query).toPromise()
}
```

### 🚨 SolidStart роутинг (КРИТИЧНО!)
```typescript
// ⚠️ КРИТИЧНО: route.load ТОЛЬКО для SSR!
export const route = {
  load: async ({ params }) => {
    // Выполняется ТОЛЬКО на сервере
    // НЕ вызывается при клиентском роутинге!
    return await loadData(params.slug)
  }
}

// ❌ НИКОГДА не рассчитывай на route.load для клиентских переходов
export default function Page(props: RouteSectionProps<Data>) {
  // При клиентском роутинге props.data НЕ обновляется!
  // Нужен createResource с отслеживанием параметров URL
}

// ✅ ПРАВИЛЬНО - createResource для клиентских переходов
const [data] = createResource(
  () => ({ slug: params.slug, data: props.data }), // Отслеживаем изменения slug
  async ({ slug, data }) => {
    // Если slug изменился - загружаем новые данные
    if (slug && slug !== prevSlug) {
      return await loadData(slug)
    }
    // Иначе используем SSR данные
    return data instanceof Promise ? await data : data
  }
)
```

### 🩺 Диагностика гидрации
**Error: Hydration Mismatch** → Ищи:
1. **JSX в пропсах** (`header={<h2>`)
2. **createResource без initialValue**
3. **typeof window проверки**
4. **Promise в props.data без обработки**
5. **route.load ожидание при клиентском роутинге**

## 🐍 Python Standards

### 📋 Code Style
- **Python 3.12+** required
- **Line length**: 120 characters max
- **Type hints**: Required for all functions
- **Docstrings**: Required for public methods
- **Ruff**: linting and formatting
- **MyPy**: typechecks

### 🧪 Testing
- **Pytest** for testing
- **85%+ coverage** required
- Test both positive and negative cases
- Mock external dependencies

### ✅ Good Examples
```python
# Good example
async def create_reaction(
    session: Session,
    author_id: int,
    reaction_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Create a new reaction.

    Args:
        session: Database session
        author_id: ID of the author creating the reaction
        reaction_data: Reaction data

    Returns:
        Created reaction data

    Raises:
        ValueError: If reaction data is invalid
    """
    if not reaction_data.get("kind"):
        raise ValueError("Reaction kind is required")

    reaction = Reaction(**reaction_data)
    session.add(reaction)
    session.commit()

    return reaction.dict()
```

### 🔒 Security
- **SQL injection**: Используй ORM, не raw SQL
- **Environment variables**: Никогда не хардкодь секреты

### 📊 Performance
- **Async/await**: Для I/O операций
- **Database**: Используй connection pooling
- **Caching**: Redis для частых запросов
- **Monitoring**: Логируй метрики производительности

### 🚫 Anti-patterns
```python
# ❌ НЕ делай
def bad_function(data):  # Нет типов
    return data.get('key')  # Нет обработки ошибок

# ❌ НЕ используй raw SQL
query = f"SELECT * FROM users WHERE id = {user_id}"  # SQL injection!

# ❌ НЕ хардкодь конфиги
DATABASE_URL = "postgresql://user:pass@localhost/db"  # В .env!
```

### 📝 Commit Messages
Follow [Conventional Commits](https://conventionalcommits.org/):
```
feat: add user authentication
fix: resolve database connection issue
docs: update API documentation
test: add tests for reaction system
refactor: improve GraphQL resolvers
```

### Final Checks
```sh
uv run ruff check . --fix
uv run ruff format --line-length 120
uv run mypy .
```

## 🎨 CSS Modules

### ✅ Правильно
```scss
// Component.module.scss
.localClass {
  color: red;
  @extend .baseClass; // DRY
}
```

```typescript
// Component.tsx
import styles from './Component.module.scss'
export const Component = () => (
  <div class={styles.localClass}>Content</div>
)
```

### 🚫 Избегай
```typescript
// ❌ НЕ inline стили
<div style="color: red;">Bad</div>

// ❌ НЕ глобальные без нужды
:global(.some-class) { /* избегай */ }
```

### 🔧 Структура
```
src/components/Button/
├── Button.tsx
├── Button.module.scss
└── index.ts
```

### 📱 Responsive Design
```scss
// Mobile-first подход
.component {
  padding: 1rem;

  @media (min-width: 768px) {
    padding: 2rem;
  }

  @media (min-width: 1024px) {
    padding: 3rem;
  }
}
```

### 🎯 Performance
- **CSS Modules**: Автоматическое минифицирование
- **Critical CSS**: Инлайн критических стилей
- **Lazy Loading**: Загрузка стилей по требованию
- **Tree Shaking**: Удаление неиспользуемых стилей

### 🔧 Variables & Mixins
```scss
// variables.scss
:root {
  --primary-color: #007bff;
  --spacing-unit: 1rem;
  --border-radius: 4px;
}

// mixins.scss
@mixin button-base {
  padding: var(--spacing-unit);
  border-radius: var(--border-radius);
  border: none;
  cursor: pointer;
}
