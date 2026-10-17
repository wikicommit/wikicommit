import { createRequire } from 'node:module';
import { classNames } from '@quartz-community/utils/lang';
import { resolveRelative as resolveRelative$1, splitAnchor, slugifyFilePath } from '@quartz-community/utils/path';

createRequire(import.meta.url);
function resolveRelative(current, target) {
  return resolveRelative$1(current, target);
}
function slugifyWikilinkTarget(target) {
  const [rawPath, anchor] = splitAnchor(target);
  if (!rawPath) return anchor;
  const pathWithExt = rawPath.endsWith(".md") ? rawPath : `${rawPath}.md`;
  const slug = slugifyFilePath(pathWithExt);
  return slug + anchor;
}

// src/i18n/locales/en-US.ts
var en_US_default = {
  components: {
    wikicommitProperties: {
      title: "Key facts",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "Tags",
        aliases: "Also known as",
        abstract: "Abstract",
        address: "Address",
        affiliation: "Affiliation",
        applicationCategory: "Category",
        author: "Author",
        birthDate: "Date of birth",
        character: "Characters",
        citation: "Cites",
        containedInPlace: "Located in",
        creator: "Creator",
        datePublished: "Date published",
        description: "Description",
        endDate: "End date",
        eventStatus: "Status",
        featureList: "Features",
        founder: "Founder",
        foundingDate: "Founded",
        foundingLocation: "Place founded",
        genre: "Genre",
        isbn: "ISBN",
        jobTitle: "Job title",
        keywords: "Keywords",
        latitude: "Latitude",
        location: "Location",
        longitude: "Longitude",
        numberOfEmployees: "Number of employees",
        organizer: "Organizer",
        performer: "Performers",
        publisher: "Publisher",
        startDate: "Start date",
        supply: "Materials",
        temporalCoverage: "Period covered",
        tool: "Tools",
        totalTime: "Total time",
        url: "URL",
        variableMeasured: "Variables measured"
      }
    }
  }
};

// src/i18n/locales/ja-JP.ts
var ja_JP_default = {
  components: {
    wikicommitProperties: {
      title: "\u57FA\u672C\u60C5\u5831",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "\u30BF\u30B0",
        aliases: "\u5225\u540D",
        abstract: "\u8981\u65E8",
        address: "\u6240\u5728\u5730",
        affiliation: "\u6240\u5C5E",
        applicationCategory: "\u5206\u985E",
        author: "\u8457\u8005",
        birthDate: "\u751F\u5E74\u6708\u65E5",
        character: "\u767B\u5834\u4EBA\u7269",
        citation: "\u5F15\u7528\u6587\u732E",
        containedInPlace: "\u6240\u5728\u3059\u308B\u5730\u57DF",
        creator: "\u4F5C\u6210\u8005",
        datePublished: "\u767A\u884C\u65E5",
        description: "\u8AAC\u660E",
        endDate: "\u7D42\u4E86\u65E5",
        eventStatus: "\u958B\u50AC\u72B6\u6CC1",
        featureList: "\u6A5F\u80FD",
        founder: "\u5275\u8A2D\u8005",
        foundingDate: "\u8A2D\u7ACB\u65E5",
        foundingLocation: "\u8A2D\u7ACB\u5730",
        genre: "\u30B8\u30E3\u30F3\u30EB",
        isbn: "ISBN",
        jobTitle: "\u8077\u540D",
        keywords: "\u30AD\u30FC\u30EF\u30FC\u30C9",
        latitude: "\u7DEF\u5EA6",
        location: "\u5834\u6240",
        longitude: "\u7D4C\u5EA6",
        numberOfEmployees: "\u5F93\u696D\u54E1\u6570",
        organizer: "\u4E3B\u50AC\u8005",
        performer: "\u51FA\u6F14\u8005",
        publisher: "\u767A\u884C\u8005",
        startDate: "\u958B\u59CB\u65E5",
        supply: "\u6750\u6599",
        temporalCoverage: "\u5BFE\u8C61\u671F\u9593",
        tool: "\u9053\u5177",
        totalTime: "\u6240\u8981\u6642\u9593",
        url: "URL",
        variableMeasured: "\u6E2C\u5B9A\u9805\u76EE"
      }
    }
  }
};

// src/i18n/locales/de-DE.ts
var de_DE_default = {
  components: {
    wikicommitProperties: {
      title: "Eckdaten",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "Tags",
        aliases: "Auch bekannt als",
        abstract: "Zusammenfassung",
        address: "Adresse",
        affiliation: "Zugeh\xF6rigkeit",
        applicationCategory: "Kategorie",
        author: "Autor",
        birthDate: "Geburtsdatum",
        character: "Figuren",
        citation: "Zitiert",
        containedInPlace: "Liegt in",
        creator: "Urheber",
        datePublished: "Ver\xF6ffentlichungsdatum",
        description: "Beschreibung",
        endDate: "Enddatum",
        eventStatus: "Status",
        featureList: "Funktionen",
        founder: "Gr\xFCnder",
        foundingDate: "Gr\xFCndungsdatum",
        foundingLocation: "Gr\xFCndungsort",
        genre: "Genre",
        isbn: "ISBN",
        jobTitle: "Position",
        keywords: "Schl\xFCsselw\xF6rter",
        latitude: "Breitengrad",
        location: "Ort",
        longitude: "L\xE4ngengrad",
        numberOfEmployees: "Anzahl der Mitarbeiter",
        organizer: "Veranstalter",
        performer: "Mitwirkende",
        publisher: "Herausgeber",
        startDate: "Startdatum",
        supply: "Material",
        temporalCoverage: "Erfasster Zeitraum",
        tool: "Werkzeuge",
        totalTime: "Gesamtdauer",
        url: "URL",
        variableMeasured: "Gemessene Variablen"
      }
    }
  }
};

// src/i18n/locales/es-ES.ts
var es_ES_default = {
  components: {
    wikicommitProperties: {
      title: "Datos clave",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "Etiquetas",
        aliases: "Tambi\xE9n conocido como",
        abstract: "Resumen",
        address: "Direcci\xF3n",
        affiliation: "Afiliaci\xF3n",
        applicationCategory: "Categor\xEDa",
        author: "Autor",
        birthDate: "Fecha de nacimiento",
        character: "Personajes",
        citation: "Cita",
        containedInPlace: "Ubicado en",
        creator: "Creador",
        datePublished: "Fecha de publicaci\xF3n",
        description: "Descripci\xF3n",
        endDate: "Fecha de fin",
        eventStatus: "Estado",
        featureList: "Funciones",
        founder: "Fundador",
        foundingDate: "Fecha de fundaci\xF3n",
        foundingLocation: "Lugar de fundaci\xF3n",
        genre: "G\xE9nero",
        isbn: "ISBN",
        jobTitle: "Cargo",
        keywords: "Palabras clave",
        latitude: "Latitud",
        location: "Lugar",
        longitude: "Longitud",
        numberOfEmployees: "N\xFAmero de empleados",
        organizer: "Organizador",
        performer: "Int\xE9rpretes",
        publisher: "Editorial",
        startDate: "Fecha de inicio",
        supply: "Materiales",
        temporalCoverage: "Per\xEDodo cubierto",
        tool: "Herramientas",
        totalTime: "Tiempo total",
        url: "URL",
        variableMeasured: "Variables medidas"
      }
    }
  }
};

// src/i18n/locales/fr-FR.ts
var fr_FR_default = {
  components: {
    wikicommitProperties: {
      title: "Faits essentiels",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "\xC9tiquettes",
        aliases: "\xC9galement connu sous le nom de",
        abstract: "R\xE9sum\xE9",
        address: "Adresse",
        affiliation: "Affiliation",
        applicationCategory: "Cat\xE9gorie",
        author: "Auteur",
        birthDate: "Date de naissance",
        character: "Personnages",
        citation: "Cite",
        containedInPlace: "Situ\xE9 dans",
        creator: "Cr\xE9ateur",
        datePublished: "Date de publication",
        description: "Description",
        endDate: "Date de fin",
        eventStatus: "Statut",
        featureList: "Fonctionnalit\xE9s",
        founder: "Fondateur",
        foundingDate: "Date de fondation",
        foundingLocation: "Lieu de fondation",
        genre: "Genre",
        isbn: "ISBN",
        jobTitle: "Fonction",
        keywords: "Mots-cl\xE9s",
        latitude: "Latitude",
        location: "Lieu",
        longitude: "Longitude",
        numberOfEmployees: "Nombre d'employ\xE9s",
        organizer: "Organisateur",
        performer: "Interpr\xE8tes",
        publisher: "\xC9diteur",
        startDate: "Date de d\xE9but",
        supply: "Fournitures",
        temporalCoverage: "P\xE9riode couverte",
        tool: "Outils",
        totalTime: "Dur\xE9e totale",
        url: "URL",
        variableMeasured: "Variables mesur\xE9es"
      }
    }
  }
};

// src/i18n/locales/it-IT.ts
var it_IT_default = {
  components: {
    wikicommitProperties: {
      title: "Dati principali",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "Tag",
        aliases: "Noto anche come",
        abstract: "Sommario",
        address: "Indirizzo",
        affiliation: "Affiliazione",
        applicationCategory: "Categoria",
        author: "Autore",
        birthDate: "Data di nascita",
        character: "Personaggi",
        citation: "Cita",
        containedInPlace: "Situato in",
        creator: "Creatore",
        datePublished: "Data di pubblicazione",
        description: "Descrizione",
        endDate: "Data di fine",
        eventStatus: "Stato",
        featureList: "Funzionalit\xE0",
        founder: "Fondatore",
        foundingDate: "Data di fondazione",
        foundingLocation: "Luogo di fondazione",
        genre: "Genere",
        isbn: "ISBN",
        jobTitle: "Incarico",
        keywords: "Parole chiave",
        latitude: "Latitudine",
        location: "Luogo",
        longitude: "Longitudine",
        numberOfEmployees: "Numero di dipendenti",
        organizer: "Organizzatore",
        performer: "Interpreti",
        publisher: "Editore",
        startDate: "Data di inizio",
        supply: "Materiali",
        temporalCoverage: "Periodo coperto",
        tool: "Strumenti",
        totalTime: "Tempo totale",
        url: "URL",
        variableMeasured: "Variabili misurate"
      }
    }
  }
};

// src/i18n/locales/pl-PL.ts
var pl_PL_default = {
  components: {
    wikicommitProperties: {
      title: "Kluczowe informacje",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "Tagi",
        aliases: "Znany r\xF3wnie\u017C jako",
        abstract: "Streszczenie",
        address: "Adres",
        affiliation: "Afiliacja",
        applicationCategory: "Kategoria",
        author: "Autor",
        birthDate: "Data urodzenia",
        character: "Postacie",
        citation: "Cytuje",
        containedInPlace: "Po\u0142o\u017Cony w",
        creator: "Tw\xF3rca",
        datePublished: "Data publikacji",
        description: "Opis",
        endDate: "Data zako\u0144czenia",
        eventStatus: "Status",
        featureList: "Funkcje",
        founder: "Za\u0142o\u017Cyciel",
        foundingDate: "Data za\u0142o\u017Cenia",
        foundingLocation: "Miejsce za\u0142o\u017Cenia",
        genre: "Gatunek",
        isbn: "ISBN",
        jobTitle: "Stanowisko",
        keywords: "S\u0142owa kluczowe",
        latitude: "Szeroko\u015B\u0107 geograficzna",
        location: "Miejsce",
        longitude: "D\u0142ugo\u015B\u0107 geograficzna",
        numberOfEmployees: "Liczba pracownik\xF3w",
        organizer: "Organizator",
        performer: "Wykonawcy",
        publisher: "Wydawca",
        startDate: "Data rozpocz\u0119cia",
        supply: "Materia\u0142y",
        temporalCoverage: "Okres obj\u0119ty danymi",
        tool: "Narz\u0119dzia",
        totalTime: "\u0141\u0105czny czas",
        url: "URL",
        variableMeasured: "Mierzone zmienne"
      }
    }
  }
};

// src/i18n/locales/pt-BR.ts
var pt_BR_default = {
  components: {
    wikicommitProperties: {
      title: "Dados principais",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "Etiquetas",
        aliases: "Tamb\xE9m conhecido como",
        abstract: "Resumo",
        address: "Endere\xE7o",
        affiliation: "Afilia\xE7\xE3o",
        applicationCategory: "Categoria",
        author: "Autor",
        birthDate: "Data de nascimento",
        character: "Personagens",
        citation: "Cita",
        containedInPlace: "Localizado em",
        creator: "Criador",
        datePublished: "Data de publica\xE7\xE3o",
        description: "Descri\xE7\xE3o",
        endDate: "Data de t\xE9rmino",
        eventStatus: "Situa\xE7\xE3o",
        featureList: "Recursos",
        founder: "Fundador",
        foundingDate: "Data de funda\xE7\xE3o",
        foundingLocation: "Local de funda\xE7\xE3o",
        genre: "G\xEAnero",
        isbn: "ISBN",
        jobTitle: "Cargo",
        keywords: "Palavras-chave",
        latitude: "Latitude",
        location: "Local",
        longitude: "Longitude",
        numberOfEmployees: "N\xFAmero de funcion\xE1rios",
        organizer: "Organizador",
        performer: "Artistas",
        publisher: "Editora",
        startDate: "Data de in\xEDcio",
        supply: "Materiais",
        temporalCoverage: "Per\xEDodo abrangido",
        tool: "Ferramentas",
        totalTime: "Tempo total",
        url: "URL",
        variableMeasured: "Vari\xE1veis medidas"
      }
    }
  }
};

// src/i18n/locales/ru-RU.ts
var ru_RU_default = {
  components: {
    wikicommitProperties: {
      title: "\u041E\u0441\u043D\u043E\u0432\u043D\u044B\u0435 \u0441\u0432\u0435\u0434\u0435\u043D\u0438\u044F",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "\u0422\u0435\u0433\u0438",
        aliases: "\u0422\u0430\u043A\u0436\u0435 \u0438\u0437\u0432\u0435\u0441\u0442\u0435\u043D \u043A\u0430\u043A",
        abstract: "\u0410\u043D\u043D\u043E\u0442\u0430\u0446\u0438\u044F",
        address: "\u0410\u0434\u0440\u0435\u0441",
        affiliation: "\u041F\u0440\u0438\u043D\u0430\u0434\u043B\u0435\u0436\u043D\u043E\u0441\u0442\u044C",
        applicationCategory: "\u041A\u0430\u0442\u0435\u0433\u043E\u0440\u0438\u044F",
        author: "\u0410\u0432\u0442\u043E\u0440",
        birthDate: "\u0414\u0430\u0442\u0430 \u0440\u043E\u0436\u0434\u0435\u043D\u0438\u044F",
        character: "\u041F\u0435\u0440\u0441\u043E\u043D\u0430\u0436\u0438",
        citation: "\u0426\u0438\u0442\u0438\u0440\u0443\u0435\u0442",
        containedInPlace: "\u0420\u0430\u0441\u043F\u043E\u043B\u043E\u0436\u0435\u043D \u0432",
        creator: "\u0421\u043E\u0437\u0434\u0430\u0442\u0435\u043B\u044C",
        datePublished: "\u0414\u0430\u0442\u0430 \u043F\u0443\u0431\u043B\u0438\u043A\u0430\u0446\u0438\u0438",
        description: "\u041E\u043F\u0438\u0441\u0430\u043D\u0438\u0435",
        endDate: "\u0414\u0430\u0442\u0430 \u043E\u043A\u043E\u043D\u0447\u0430\u043D\u0438\u044F",
        eventStatus: "\u0421\u0442\u0430\u0442\u0443\u0441",
        featureList: "\u0424\u0443\u043D\u043A\u0446\u0438\u0438",
        founder: "\u041E\u0441\u043D\u043E\u0432\u0430\u0442\u0435\u043B\u044C",
        foundingDate: "\u0414\u0430\u0442\u0430 \u043E\u0441\u043D\u043E\u0432\u0430\u043D\u0438\u044F",
        foundingLocation: "\u041C\u0435\u0441\u0442\u043E \u043E\u0441\u043D\u043E\u0432\u0430\u043D\u0438\u044F",
        genre: "\u0416\u0430\u043D\u0440",
        isbn: "ISBN",
        jobTitle: "\u0414\u043E\u043B\u0436\u043D\u043E\u0441\u0442\u044C",
        keywords: "\u041A\u043B\u044E\u0447\u0435\u0432\u044B\u0435 \u0441\u043B\u043E\u0432\u0430",
        latitude: "\u0428\u0438\u0440\u043E\u0442\u0430",
        location: "\u041C\u0435\u0441\u0442\u043E",
        longitude: "\u0414\u043E\u043B\u0433\u043E\u0442\u0430",
        numberOfEmployees: "\u0427\u0438\u0441\u043B\u043E \u0441\u043E\u0442\u0440\u0443\u0434\u043D\u0438\u043A\u043E\u0432",
        organizer: "\u041E\u0440\u0433\u0430\u043D\u0438\u0437\u0430\u0442\u043E\u0440",
        performer: "\u0418\u0441\u043F\u043E\u043B\u043D\u0438\u0442\u0435\u043B\u0438",
        publisher: "\u0418\u0437\u0434\u0430\u0442\u0435\u043B\u044C",
        startDate: "\u0414\u0430\u0442\u0430 \u043D\u0430\u0447\u0430\u043B\u0430",
        supply: "\u041C\u0430\u0442\u0435\u0440\u0438\u0430\u043B\u044B",
        temporalCoverage: "\u041E\u0445\u0432\u0430\u0442\u044B\u0432\u0430\u0435\u043C\u044B\u0439 \u043F\u0435\u0440\u0438\u043E\u0434",
        tool: "\u0418\u043D\u0441\u0442\u0440\u0443\u043C\u0435\u043D\u0442\u044B",
        totalTime: "\u041E\u0431\u0449\u0435\u0435 \u0432\u0440\u0435\u043C\u044F",
        url: "URL",
        variableMeasured: "\u0418\u0437\u043C\u0435\u0440\u044F\u0435\u043C\u044B\u0435 \u043F\u0435\u0440\u0435\u043C\u0435\u043D\u043D\u044B\u0435"
      }
    }
  }
};

// src/i18n/locales/zh-CN.ts
var zh_CN_default = {
  components: {
    wikicommitProperties: {
      title: "\u57FA\u672C\u4FE1\u606F",
      // Display labels for the property keys the distributed type templates
      // list (Issue #1292). A key not listed here — a custom type's, or one
      // Pass 2b added — is shown as its Schema.org name split into words.
      labels: {
        tags: "\u6807\u7B7E",
        aliases: "\u522B\u540D",
        abstract: "\u6458\u8981",
        address: "\u5730\u5740",
        affiliation: "\u6240\u5C5E\u673A\u6784",
        applicationCategory: "\u7C7B\u522B",
        author: "\u4F5C\u8005",
        birthDate: "\u51FA\u751F\u65E5\u671F",
        character: "\u89D2\u8272",
        citation: "\u5F15\u7528\u6587\u732E",
        containedInPlace: "\u6240\u5728\u5730\u533A",
        creator: "\u521B\u5EFA\u8005",
        datePublished: "\u53D1\u5E03\u65E5\u671F",
        description: "\u63CF\u8FF0",
        endDate: "\u7ED3\u675F\u65E5\u671F",
        eventStatus: "\u72B6\u6001",
        featureList: "\u529F\u80FD",
        founder: "\u521B\u59CB\u4EBA",
        foundingDate: "\u6210\u7ACB\u65E5\u671F",
        foundingLocation: "\u6210\u7ACB\u5730\u70B9",
        genre: "\u7C7B\u578B",
        isbn: "ISBN",
        jobTitle: "\u804C\u4F4D",
        keywords: "\u5173\u952E\u8BCD",
        latitude: "\u7EAC\u5EA6",
        location: "\u5730\u70B9",
        longitude: "\u7ECF\u5EA6",
        numberOfEmployees: "\u5458\u5DE5\u4EBA\u6570",
        organizer: "\u4E3B\u529E\u65B9",
        performer: "\u8868\u6F14\u8005",
        publisher: "\u51FA\u7248\u8005",
        startDate: "\u5F00\u59CB\u65E5\u671F",
        supply: "\u6750\u6599",
        temporalCoverage: "\u65F6\u95F4\u8303\u56F4",
        tool: "\u5DE5\u5177",
        totalTime: "\u603B\u65F6\u957F",
        url: "URL",
        variableMeasured: "\u6D4B\u91CF\u53D8\u91CF"
      }
    }
  }
};

// src/i18n/index.ts
var locales = {
  "en-US": en_US_default,
  "ja-JP": ja_JP_default,
  "de-DE": de_DE_default,
  "es-ES": es_ES_default,
  "fr-FR": fr_FR_default,
  "it-IT": it_IT_default,
  "pl-PL": pl_PL_default,
  "pt-BR": pt_BR_default,
  "ru-RU": ru_RU_default,
  "zh-CN": zh_CN_default
};
function i18n(locale) {
  return locales[locale] || en_US_default;
}
var LANG_TO_LOCALE = {
  en: "en-US",
  ja: "ja-JP",
  de: "de-DE",
  es: "es-ES",
  fr: "fr-FR",
  it: "it-IT",
  pl: "pl-PL",
  pt: "pt-BR",
  ru: "ru-RU",
  zh: "zh-CN"
};
function resolveLocale(frontmatterLang, cfgLocale) {
  if (typeof frontmatterLang === "string") {
    const mapped = LANG_TO_LOCALE[frontmatterLang];
    if (mapped) return mapped;
  }
  return cfgLocale ?? "en-US";
}

// src/components/styles/wikicommit-properties.scss
var wikicommit_properties_default = '.wikicommit-properties {\n  margin: 0.5rem 0 1rem;\n  max-width: 34rem;\n  border: 1px solid var(--lightgray);\n  border-radius: 5px;\n  font-size: 0.9rem;\n}\n.wikicommit-properties[open] > .wikicommit-properties-header {\n  border-bottom: 1px solid var(--lightgray);\n}\n.wikicommit-properties .wikicommit-properties-header {\n  display: flex;\n  align-items: center;\n  gap: 0.5rem;\n  padding: 0.4rem 0.8rem;\n  cursor: pointer;\n  user-select: none;\n  list-style: none;\n  color: var(--darkgray);\n  font-weight: 600;\n}\n.wikicommit-properties .wikicommit-properties-header::-webkit-details-marker {\n  display: none;\n}\n.wikicommit-properties .wikicommit-properties-header::before {\n  content: "";\n  display: inline-block;\n  width: 0.5em;\n  height: 0.5em;\n  border-right: 2px solid var(--darkgray);\n  border-bottom: 2px solid var(--darkgray);\n  transform: rotate(-45deg);\n  transition: transform 0.2s ease;\n}\n.wikicommit-properties[open] > .wikicommit-properties-header::before {\n  transform: rotate(45deg);\n}\n.wikicommit-properties .wikicommit-properties-count {\n  margin-left: auto;\n  font-size: 0.75rem;\n  color: var(--gray);\n  font-weight: 400;\n}\n.wikicommit-properties .wikicommit-properties-table {\n  width: 100%;\n  border-collapse: collapse;\n  table-layout: fixed;\n}\n.wikicommit-properties .wikicommit-properties-row {\n  border-bottom: 1px solid var(--lightgray);\n}\n.wikicommit-properties .wikicommit-properties-row:last-child {\n  border-bottom: none;\n}\n.wikicommit-properties .wikicommit-properties-key {\n  width: 35%;\n  padding: 0.35rem 0.8rem;\n  color: var(--darkgray);\n  font-size: 0.85rem;\n  font-weight: 600;\n  text-align: left;\n  vertical-align: top;\n  word-break: break-word;\n}\n.wikicommit-properties .wikicommit-properties-value {\n  padding: 0.35rem 0.8rem;\n  vertical-align: top;\n  word-break: break-word;\n}\n.wikicommit-properties .wikicommit-properties-empty {\n  color: var(--gray);\n  font-style: italic;\n}\n.wikicommit-properties .wikicommit-properties-boolean input[type=checkbox] {\n  pointer-events: none;\n  margin: 0;\n  vertical-align: middle;\n}\n.wikicommit-properties .wikicommit-properties-number {\n  font-family: var(--codeFont);\n  font-size: 0.85em;\n}\n.wikicommit-properties .wikicommit-properties-link {\n  text-decoration: none;\n  color: var(--secondary);\n}\n.wikicommit-properties .wikicommit-properties-link:hover {\n  text-decoration: underline;\n}\n.wikicommit-properties .wikicommit-properties-separator {\n  color: var(--gray);\n}\n.wikicommit-properties .wikicommit-properties-list {\n  display: inline;\n}\n.wikicommit-properties .wikicommit-properties-tags {\n  display: inline-flex;\n}\n.wikicommit-properties .wikicommit-properties-tags .tag-link {\n  display: inline-block;\n  padding: 0.1rem 0.4rem;\n  border-radius: 3px;\n  background: var(--highlight);\n  color: var(--secondary);\n  font-size: 0.85em;\n  text-decoration: none;\n}\n.wikicommit-properties .wikicommit-properties-tags .tag-link:hover {\n  background: var(--secondary);\n  color: var(--light);\n}\n.wikicommit-properties .wikicommit-properties-object code {\n  font-size: 0.85em;\n  padding: 0.1rem 0.3rem;\n  border-radius: 3px;\n  background: var(--highlight);\n  word-break: break-all;\n}';

// src/components/scripts/wikicommitProperties.inline.ts
var wikicommitProperties_inline_default = 'var o=Object.hasOwnProperty;function e(u){return u.document.body.dataset.slug}var C="wikicommit-properties-collapsed:";function A(){return C+e(window)}function n(){let u=document.querySelector("details.wikicommit-properties");if(!u)return;let D=A(),F=localStorage.getItem(D);if(F!==null){let E=F==="true";u.open=!E}let t=()=>{localStorage.setItem(D,String(!u.open))};u.addEventListener("toggle",t),typeof window<"u"&&window.addCleanup&&window.addCleanup(()=>{u.removeEventListener("toggle",t)})}document.addEventListener("nav",()=>{n()});document.addEventListener("render",()=>{n()});\n';
var l;
function S(n2) {
  return n2.children;
}
l = { __e: function(n2, l2, u3, t2) {
  for (var i2, r2, o2; l2 = l2.__; ) if ((i2 = l2.__c) && !i2.__) try {
    if ((r2 = i2.constructor) && null != r2.getDerivedStateFromError && (i2.setState(r2.getDerivedStateFromError(n2)), o2 = i2.__d), null != i2.componentDidCatch && (i2.componentDidCatch(n2, t2 || {}), o2 = i2.__d), o2) return i2.__E = i2;
  } catch (l3) {
    n2 = l3;
  }
  throw n2;
} }, "function" == typeof Promise ? Promise.prototype.then.bind(Promise.resolve()) : setTimeout, Math.random().toString(8);

// node_modules/preact/jsx-runtime/dist/jsxRuntime.mjs
var f2 = 0;
function u2(e2, t2, n2, o2, i2, u3) {
  t2 || (t2 = {});
  var a2, c2, p2 = t2;
  if ("ref" in p2) for (c2 in p2 = {}, t2) "ref" == c2 ? a2 = t2[c2] : p2[c2] = t2[c2];
  var l2 = { type: e2, props: p2, key: n2, ref: a2, __k: null, __: null, __b: 0, __e: null, __c: null, constructor: void 0, __v: --f2, __i: -1, __u: 0, __source: i2, __self: u3 };
  if ("function" == typeof e2 && (a2 = e2.defaultProps)) for (c2 in a2) void 0 === p2[c2] && (p2[c2] = a2[c2]);
  return l.vnode && l.vnode(l2), l2;
}

// src/components/WikiCommitProperties.tsx
var WIKILINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;
var MDLINK_RE = /\[([^\]]*)\]\(([^)]+)\)/g;
var URL_RE = /https?:\/\/[^\s<>]+/g;
var TRAILING_PUNCTUATION_RE = /[.,;:!?。、！？…‘’“”]+$/;
function trimUnbalancedTrailingParen(url) {
  while (url.endsWith(")")) {
    const opens = (url.match(/\(/g) ?? []).length;
    const closes = (url.match(/\)/g) ?? []).length;
    if (closes <= opens) break;
    url = url.slice(0, -1);
  }
  return url;
}
function lookupHref(ctx, slugifiedTarget) {
  return ctx.resolvedLinks[slugifiedTarget] ?? resolveRelative(ctx.slug, slugifiedTarget);
}
function renderTextWithLinks(text, ctx) {
  const segments = [];
  for (const match of text.matchAll(WIKILINK_RE)) {
    const target = match[1];
    const display = match[2] ?? target;
    const href = lookupHref(ctx, slugifyWikilinkTarget(target));
    segments.push({
      start: match.index,
      end: match.index + match[0].length,
      node: /* @__PURE__ */ u2("a", { href, class: "internal internal-link wikicommit-properties-link", children: display })
    });
  }
  for (const match of text.matchAll(MDLINK_RE)) {
    const overlaps = segments.some(
      (s2) => match.index < s2.end && match.index + match[0].length > s2.start
    );
    if (overlaps) continue;
    const display = match[1];
    const href = match[2];
    const isExternal = href.startsWith("http://") || href.startsWith("https://");
    const resolvedHref = isExternal ? href : lookupHref(ctx, href);
    segments.push({
      start: match.index,
      end: match.index + match[0].length,
      node: /* @__PURE__ */ u2(
        "a",
        {
          href: resolvedHref,
          class: classNames(
            isExternal ? "external external-link" : "internal internal-link",
            "wikicommit-properties-link"
          ),
          ...isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {},
          children: display || href
        }
      )
    });
  }
  for (const match of text.matchAll(URL_RE)) {
    const overlaps = segments.some(
      (s2) => match.index < s2.end && match.index + match[0].length > s2.start
    );
    if (overlaps) continue;
    const url = trimUnbalancedTrailingParen(match[0].replace(TRAILING_PUNCTUATION_RE, ""));
    if (url.replace(/^https?:\/\//, "").length === 0) continue;
    segments.push({
      start: match.index,
      end: match.index + url.length,
      node: /* @__PURE__ */ u2(
        "a",
        {
          href: url,
          class: "external external-link wikicommit-properties-link",
          target: "_blank",
          rel: "noopener noreferrer",
          children: url
        }
      )
    });
  }
  if (segments.length === 0) return [text];
  segments.sort((a2, b2) => a2.start - b2.start);
  const result = [];
  let cursor = 0;
  for (const seg of segments) {
    if (seg.start > cursor) {
      result.push(text.slice(cursor, seg.start));
    }
    result.push(seg.node);
    cursor = seg.end;
  }
  if (cursor < text.length) {
    result.push(text.slice(cursor));
  }
  return result;
}
function renderValue(value, ctx) {
  if (value === null || value === void 0) {
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-empty", children: "\u2014" });
  }
  if (typeof value === "boolean") {
    return /* @__PURE__ */ u2("span", { class: classNames("wikicommit-properties-boolean", value ? "is-true" : "is-false"), children: /* @__PURE__ */ u2("input", { type: "checkbox", checked: value, disabled: true }) });
  }
  if (typeof value === "number") {
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-number", children: value });
  }
  if (typeof value === "string") {
    const parts = renderTextWithLinks(value, ctx);
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-text", children: parts });
  }
  if (Array.isArray(value)) {
    const items = value.map((item, idx) => {
      const rendered = renderValue(item, ctx);
      return /* @__PURE__ */ u2(S, { children: [
        idx > 0 && /* @__PURE__ */ u2("span", { class: "wikicommit-properties-separator", children: ", " }),
        rendered
      ] });
    });
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-list", children: items });
  }
  if (typeof value === "object") {
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-object", children: /* @__PURE__ */ u2("code", { children: JSON.stringify(value) }) });
  }
  return String(value);
}
function renderTagList(tags, ctx) {
  const items = tags.map((tag, idx) => {
    const href = resolveRelative(ctx.slug, `tags/${tag}`);
    return /* @__PURE__ */ u2(S, { children: [
      idx > 0 && /* @__PURE__ */ u2("span", { class: "wikicommit-properties-separator", children: ", " }),
      /* @__PURE__ */ u2("a", { href, class: "internal internal-link tag-link", children: tag })
    ] });
  });
  return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-tags", children: items });
}
function humanizeKey(key) {
  const words = key.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2").split(/[\s_-]+/).filter((w2) => w2.length > 0).map((w2) => w2 === w2.toUpperCase() && w2.length > 1 ? w2 : w2.toLowerCase());
  if (words.length === 0) return key;
  const first = words[0];
  words[0] = first.charAt(0).toUpperCase() + first.slice(1);
  return words.join(" ");
}
function labelFor(key, labels) {
  return Object.prototype.hasOwnProperty.call(labels, key) ? labels[key] : humanizeKey(key);
}
var WikiCommitProperties_default = ((opts) => {
  const { collapsed = false } = opts ?? {};
  const Component = (props) => {
    const wcProps = props.fileData?.wikicommitProperties;
    if (!wcProps) return null;
    if (wcProps.showProperties === false) return null;
    if (wcProps.showProperties !== true && wcProps.hideView) return null;
    const properties = wcProps.properties;
    const entries = Object.entries(properties);
    if (entries.length === 0) return null;
    const frontmatter = props.fileData?.frontmatter;
    const t2 = i18n(resolveLocale(frontmatter?.lang, props.cfg?.locale)).components.wikicommitProperties;
    const labels = t2.labels;
    const ctx = {
      slug: props.fileData?.slug ?? "",
      resolvedLinks: wcProps.resolvedLinks ?? {}
    };
    const isCollapsed = wcProps.collapseProperties ?? collapsed;
    return /* @__PURE__ */ u2(
      "details",
      {
        class: classNames(
          props.displayClass,
          "wikicommit-properties",
          "wikicommit-infobox",
          "metadata-container"
        ),
        open: !isCollapsed,
        "data-collapsed": isCollapsed,
        children: [
          /* @__PURE__ */ u2("summary", { class: "wikicommit-properties-header", children: [
            /* @__PURE__ */ u2("span", { class: "wikicommit-properties-title", children: t2.title }),
            /* @__PURE__ */ u2("span", { class: "wikicommit-properties-count", children: entries.length })
          ] }),
          /* @__PURE__ */ u2("table", { class: "wikicommit-properties-table", children: /* @__PURE__ */ u2("tbody", { children: entries.map(([key, value]) => /* @__PURE__ */ u2("tr", { class: "wikicommit-properties-row metadata-property", children: [
            /* @__PURE__ */ u2(
              "th",
              {
                scope: "row",
                class: "wikicommit-properties-key metadata-property-key",
                "data-key": key,
                children: labelFor(key, labels)
              }
            ),
            /* @__PURE__ */ u2("td", { class: "wikicommit-properties-value metadata-property-value", children: key === "tags" && Array.isArray(value) ? renderTagList(value, ctx) : renderValue(value, ctx) })
          ] }, key)) }) })
        ]
      }
    );
  };
  Component.css = wikicommit_properties_default;
  Component.afterDOMLoaded = wikicommitProperties_inline_default;
  return Component;
});

export { WikiCommitProperties_default as WikiCommitPropertiesComponent };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map