import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"

const locales: Record<string, typeof enUS> = {
  "en-US": enUS,
  "ja-JP": jaJP,
}

export function i18n(locale: string) {
  return locales[locale] || enUS
}
