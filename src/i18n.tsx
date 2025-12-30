import type { ParentProps } from 'solid-js'
import { createContext, createResource, createSignal, onMount, useContext } from 'solid-js'
import { createStore } from 'solid-js/store'
import { isServer } from 'solid-js/web'

// Типы для контекста i18n
export type Languages = 'ru' | 'en'
type TranslationMap = Record<string, string>
type TranslationStore = Record<Languages, TranslationMap>

// Создаем контекст i18n
interface I18nContextValue {
  currentLanguage: () => Languages
  setLanguage: (lang: Languages) => void
  t: (key: string) => string
  isLoaded: () => boolean
}

const defaultValue: I18nContextValue = {
  currentLanguage: () => 'ru' as Languages,
  setLanguage: () => {},
  t: (key: string) => key,
  isLoaded: () => false
}

const I18nContext = createContext<I18nContextValue>(defaultValue)

// Провайдер i18n
export function I18nProvider(props: ParentProps) {
  // Функция для определения языка по умолчанию (только для клиента)
  const getDefaultLanguage = (): Languages => {
    if (isServer) return 'ru'

    // Проверяем URL-параметр lang
    const urlParams = new URLSearchParams(window.location.search)
    const langParam = urlParams.get('lang')
    if (langParam === 'en' || langParam === 'ru') {
      return langParam
    }

    // Сначала проверяем localStorage
    const savedLanguage = localStorage.getItem('language') as Languages | null
    if (savedLanguage && (savedLanguage === 'ru' || savedLanguage === 'en')) {
      return savedLanguage
    }

    // По умолчанию используем русский
    return 'ru'
  }

  // Загружаем переводы из public/intl.json
  const [translations, setTranslations] = createStore<TranslationStore>({
    ru: {},
    en: {}
  })

  const [currentLanguage, setCurrentLanguage] = createSignal<Languages>('ru')

  const [isLoaded, setIsLoaded] = createSignal(false)

  // Загружаем файл переводов
  createResource(async () => {
    try {
      const response = await fetch('/intl.json')
      const data = await response.json()

      // В data каждый ключ - это русская строка, а значение - английский перевод
      const ruDict: TranslationMap = {}
      const enDict: TranslationMap = {}

      Object.entries(data).forEach(([key, value]) => {
        ruDict[key] = key // Ключ = значение для русского
        enDict[key] = value as string // Англ. перевод
      })

      setTranslations({
        ru: ruDict,
        en: enDict
      })

      setIsLoaded(true)
      return data
    } catch (error) {
      console.error('Failed to load translations:', error)
      setIsLoaded(true)
      return {}
    }
  })

  // Функция перевода
  const t = (key: string): string => {
    const lang = currentLanguage()

    if (!isLoaded()) {
      return key
    }

    if (translations[lang][key]) {
      return translations[lang][key]
    }

    // Если перевода нет, возвращаем исходный ключ
    return key
  }

  // Функция изменения языка
  const setLanguage = (lang: Languages) => {
    if (!isServer) {
      localStorage.setItem('language', lang)
      const url = new URL(window.location.href)
      if (lang === 'ru') {
        // Для русского языка (по умолчанию) удаляем параметр lang
        url.searchParams.delete('lang')
      } else {
        url.searchParams.set('lang', lang)
      }

      // Заменяем URL без перезагрузки страницы
      window.history.replaceState({}, '', url.toString())
    }
    setCurrentLanguage(lang)
  }

  onMount(() => {
    setCurrentLanguage(getDefaultLanguage())
  })

  return (
    <I18nContext.Provider
      value={{
        currentLanguage,
        setLanguage,
        t,
        isLoaded
      }}
    >
      {props.children}
    </I18nContext.Provider>
  )
}

// Хук для использования контекста i18n
export function useI18n() {
  return useContext(I18nContext)
}

// Компонент для перевода текста
export function T(props: { children: string }) {
  const { t } = useI18n()
  return <>{t(props.children)}</>
}
