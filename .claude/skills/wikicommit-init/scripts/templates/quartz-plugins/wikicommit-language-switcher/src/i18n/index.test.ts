import { describe, expect, it } from "vitest"
import { i18n } from "./index"
import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"

describe("i18n", () => {
  it("selects the ja-JP locale for pages with lang: ja", () => {
    expect(i18n("ja-JP")).toBe(jaJP)
  })

  it("selects the en-US locale for pages with lang: en", () => {
    expect(i18n("en-US")).toBe(enUS)
  })

  it("falls back to en-US for an unsupported locale", () => {
    expect(i18n("fr-FR")).toBe(enUS)
  })

  it("falls back to en-US when no locale is given", () => {
    expect(i18n("")).toBe(enUS)
  })
})
