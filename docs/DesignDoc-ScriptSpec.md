# スクリプト仕様書

> **バージョン**: 0.2（Draft）
> **作成日**: 2026-06-23
> **対応DesignDoc**: [DesignDoc-skills.md](DesignDoc-skills.md) §11.5

`.wikicommit/scripts/` に配置する Python スクリプトの仕様。Skills（SKILL.md）から呼ばれる共通インフラ。

---

## 共通規則

- **実行環境**: Python 3.11+
- **作業ディレクトリ**: リポジトリルート（スクリプト内パスはすべてリポジトリルートからの相対パス）
- **終了コード**: `0` = 成功・warning のみ、`1` = blocking エラーあり
- **stdout**: 構造化出力行（`ERROR:` / `WARNING:` / `OK:` / `SUMMARY:` / `ORPHAN:` / `DUPLICATE:` / `WANTED:` / `TYPE_MISMATCH:` / `STALE:` / `OUTDATED:` / `EXPIRED:` / `MISSING_SOURCE:` / `UNTRANSLATED:` / `UNCOVERED:` / `page:` 等）。Skills がパースする。
- **stderr**: スクリプト実行時の予期しないエラー（Python 例外・ファイルアクセス失敗等）
- **出力の言語**: stdout・stderr に出る文字列はすべて英語で書く（Issue #770）。読み手は運用者とエージェントであって読者ではないため、Issue #405 が管理ファイルの見出しについて下したのと同じ判断で固定の英語とする。コメント・docstring は日本語のまま据え置く（読み手が開発者であり `docs/` と揃う）。公開ページに出る読者向けラベル（`convert_wikilinks.py` の `ROOT_INDEX_LABELS` / `OVERVIEW_LABELS` / `SOURCE_*_LABELS`）はこの規則の対象外で、`primary_lang` で切り替わる。`tools/check_script_output_language.py` が CI で blocking の回帰ガードとして走るが、`print()` の引数しか見ないため、`_frontmatter.py` のようにメッセージを戻り値として返すスクリプト（同ファイル自身は英語化済みだが、走査には掛からない形である）は手作業で確認する

---

## `.wikicommit/entity/` の走査は `_wikilink.py` に集約する（Issue #677）

`.wikicommit/entity/**/*.md` を走査して `assets/` と `index.md` を除く、という同じ判断が **18 箇所**に独立して書かれており、`assets/` の判定だけで **3 通りの意味論**に割れていた。うち `check_wikilinks.py` の被リンクインデックス構築は**実際に壊れていた** — 同スクリプトは絶対パスの `entity_dir`（`Path.cwd() / ENTITY_DIR`）を作る一方、`"assets" in wiki_page.parts` をそのフルパスに適用していたため、**リポジトリの祖先ディレクトリのどれかが `assets` という名前だと全ページがスキップされ、被リンクインデックスが空になる**。失われるのは削除フロー（`docs/DesignDoc-pipeline.md` §6.5）が依拠する参照切れ WikiLink の警告そのもので、**エラーにならず件数が減るだけ**なので `/wikicommit-remove` → `/wikicommit-merge` は正常に完了したように見える。

このケースは `_wikilink.py` の `build_slug_type_index()` が既に名指しで警告し、同関数では正しく修正済みだった — **正しい実装が同じファイルにあるのに、隣のループがコピー元の誤った形を保持していた**。

`_wikilink.py` に 2 つの関数を置き、全走査をそこへ寄せた:

| 関数 | 役割 |
|---|---|
| `is_entity_asset(page, entity_dir)` | `page` が `entity_dir` **直下**の `assets/` 配下かを返す。判定は必ず `entity_dir` からの相対パスに対して行い、`page.parts` には触れない |
| `collect_entity_pages(entity_dir=ENTITY_DIR, *, include_index=False)` | 上記の `assets/` と `index.md` を除いた全ページを sorted で返す |

**`assets/` の意味論は最も狭い定義に統一した**。`docs/DesignDoc-data.md` §3.1 が `.wikicommit/entity/assets/` を全言語共通の単一の置き場と定義しており、`<lang>/assets/` のようなものは仕様上存在しない。緩い定義（配下の任意セグメント）を採ると `assets` という名前の Type やスラッグを将来禁じることになる。

**`include_index=True` を渡すのは 3 箇所**: `rebuild_index.py`（最後のページが削除された Type ディレクトリは `index.md` しか残らないため、それ自体を見つける必要がある）・`check_wikilinks.py` の被リンク走査（`rebuild_index.py` が各ページの WikiLink を index に書くため、そこへのリンクは削除対象ページへの実在する参照である）・`check_wanted_pages.py`（集約前の挙動をそのまま保つ。「陳腐化した index のエントリを『誰かが書いてほしいページ』と数えるべきか」は走査の集約とは別の問いであるため、本 Issue では動かさない）。

**`validate_frontmatter.py` と `check_raw_html.py` は移行対象外**。この 2 本は `assets/` も `index.md` も除外せず全ファイルを検証する（前者は `index.md` の `sources` 必須を明示的に免除する分岐まで持つ）。対象は「グラフ・集計の対象となる本文ページ」ではなく「ディスク上の全 `.md`」であり、巻き込むとこのヘルパーの意味が薄まる。

`convert_wikilinks.py` の `is_in_assets()` はそのまま残す — publish 側で `output_dir` に対しても使われる（stale cleanup・`sync_assets()`）ため、entity ツリー専用の `collect_entity_pages()` では置き換えられない。同ファイルの `generate_overview_page()` は Type 取り違え判定を独自に持っていたが、`other_types_for_slug()` は index を引数で受け取る設計なので共有関数へ寄せた（走査は増えない — `page_stats` が既に持つ `type_raw` から index を組み立てるだけ）。

**既存リポジトリへの遡及適用は行わない**。`.wikicommit/scripts/` は `init.py` が展開する配布物であり、変更が届くのは新規 init するリポジトリのみ（本ドキュメント群が繰り返し採る「新旧混在を許容する」方針）。上記のバグは「リポジトリの祖先ディレクトリ名に `assets` が含まれる」場合にのみ発火するため、既存リポジトリで実際に踏んでいる可能性は低い。

---

## `.wikicommit/view/` を走査するかはスクリプトごとに決める（Issue #675）

view ツリー（`.wikicommit/view/<lang>/<slug>.md`。Wiki 自身のページを根拠とする二次知識。`docs/DesignDoc-data.md` §4.5.1）は entity ツリーとは別の入力である。`_wikilink.py` が `VIEW_DIR` / `VIEW_TYPE_SEGMENT` / `VIEW_KINDS` / `parse_view_path()` / `collect_view_pages()` / `view_page_path()` を持ち、各スクリプトは走査するかどうかを 1 本ずつ決める。

| 扱い | スクリプト | 理由 |
|---|---|---|
| 含める | `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_wanted_pages.py` / `check_expires.py` / `check_translation_status.py` / `search_index.py` / `rebuild_index.py` / `convert_wikilinks.py` | view ページも読者に公開されるページであり、リンクし・検索され・索引に載り・鮮度を持つ |
| 主消費者 | `check_derivation_freshness.py` | `derived_from` を持つページの主な置き場が view ツリーになった。**entity ツリーの走査は続ける** — 本 Issue 以前に書かれた合成ページはそこに残る（自動移行しない） |
| 含める（所見は entity ページにしか出ない） | `check_retracted_sources.py` | view ページは `sources[]` を持たないので直接は一致しないが、走査対象から外さない — 走査の対象と所見の有無は別の話であり、除外すると「view ページは見ていない」という事実が読む側から消える（Issue #737） |
| 除外 | `check_recurring_characters.py` / `check_unlinked_entity_mentions.py`（`properties:` 前提）・`check_schema_coverage.py` / `check_installed_type_usage.py`（`type:` 前提）・`reconcile_ingest_status.py`（`sources[].hash` 前提）・`check_orphans.py`（view ページは生まれつき被リンクゼロ） | いずれも view ページが持たないフィールドを読むか、全件が所見になる |
| 既定で除外・`--include-view` で包含 | `build_survey_view.py` | 分析をさらに分析することを避ける。着眼点が実際に grounding するのはその下の entity ページである |
| どちらも走査しない | `record_run.py`・`check_run_records.py` | 対象は `.wikicommit/run/` であり、ページを 1 枚も読まない（Issue #790） |
| 両方を受け付ける（走査はしない） | `reset_review_on_content_change.py`・`record_review.py` | ツリーを歩かず引数のページだけを見るため上の 3 分類には当たらないが、受け付ける接頭辞は `.wikicommit/entity/` と `.wikicommit/view/` の両方である。呼び出し元の `wikicommit-fix` が両ツリーを対象に取るため、entity だけに絞るとその半分が黙って素通りする（Issue #724） |

**除外側は `tests/test_view_tree.py` が固定している**。除外の理由はツリーの中身に依存せず常に成り立つため、後の変更が `collect_entity_pages()` を両ツリー走査に差し替えても**エラーにはならず**、対処できない所見が増えるだけになる。

---

## スクリプト一覧

| スクリプト | 役割 | 終了コード 1 の条件 |
|---|---|---|
| `validate_frontmatter.py` | フロントマター必須フィールド・型・許可値の検証 | blocking エラーあり |
| `check_wikilinks.py` | WikiLink 参照先の存在確認・removed ページへのリンク検出・Type セグメント取り違えの検出 | blocking エラーあり |
| `check_raw_html.py` | ページ本文中の生 HTML タグ検出（Issue #377） | blocking エラーあり |
| `check_orphans.py` | 孤立ページ・重複ページの検出 | 重複あり |
| `check_wanted_pages.py` | 被参照だが実体のない wanted page の検出（`check_orphans.py` の対）・Type セグメント取り違えの分離 | なし（常に 0） |
| `check_expires.py` | `expires_at` 期限切れ検出 | なし（常に 0） |
| `check_translation_status.py` | 翻訳の陳腐化検出・未翻訳ページ検出 | なし（常に 0） |
| `check_derivation_freshness.py` | `wikicommit-synthesize` 出力ページ（`derived_from`）の陳腐化検出 | なし（常に 0） |
| `check_ingest_freshness.py` | ingest ハッシュずれ検出 | なし（常に 0） |
| `check_distribution_freshness.py` | インストール済み配布物とテンプレートの差分検出（古い・欠落・孤児。読み取り専用） | なし（常に 0） |
| `search_index.py` | FTS5 trigram 検索インデックスの構築・クエリ（`wikicommit-search`・`wikicommit-ask` 共有） | SQLite が trigram トークナイザ非対応、または `.wikicommit/entity/` が存在しない |
| `check_schema_coverage.py` | `.wikicommit/schema/` に専用ファイルのない `type:` 値の集計（`wikicommit-generate`・`wikicommit-schema-propose`・`wikicommit-status` 共有） | なし（常に 0） |
| `check_schema_org_type.py` | Schema.org 語彙に対する型・プロパティの実在検証、型名一覧の取得と候補型の説明文の取得（2 段階。Issue #798）（`wikicommit-generate`・`wikicommit-schema-propose` 共有） | 型が語彙に存在しない、プロパティが型（祖先型含む）に属さない、語彙の取得・パースに失敗、または `--type`/`--list-type-names`/`--describe`/`--list-installed-hierarchy` のいずれも未指定 |
| `build_survey_view.py` | Wiki 全体を1つのコンテキストに収まる縮約ビューへ落とす（`wikicommit-synthesize` の俯瞰モード〈Issue #586〉と `wikicommit-collect` の Step 3.5〈Issue #672〉が共有。`--include-view` を渡さない限り view ツリーは対象外。Issue #675） | なし（常に 0） |
| `rebuild_index.py` | Type ディレクトリの `index.md`、および view ツリーの言語別 `index.md` を決定論的に再構築（`wikicommit-generate`・`wikicommit-translate`・`wikicommit-synthesize` 共有。Issue #406・#547・#675） | なし（常に 0） |
| `check_extraction_quality.py` | 既知JS-shellドメイン判定（ブロッキング）・取得能力の事前チェック（ブロッキング。Issue #574）・抽出テキストの低情報密度判定（警告。Issue #562）（`wikicommit-generate`・`wikicommit-collect` 共有。Issue #425） | ドメインが既知不可リストに一致（`check-domain`）、必要な追加パッケージが未導入（`check-fetch-capability`）、抽出テキストが低密度（`check-density`）、または対象ファイルが読み込めない |
| `reconcile_ingest_status.py` | `status: pending` のソース管理ファイルのうち内容が既に公開ページの `sources` に使われているものを検出し `status: generated` に是正（Issue #474） | なし（常に 0） |
| `reset_review_on_content_change.py` | 内容が書き換わった `reviewed` ページを `pending` へ戻し `reviewed_by` を落とす（`wikicommit-generate` Pass 4・`wikicommit-fix` 共有。Issue #724） | 引数が entity/view ツリーの外を指す、ページが存在しない、frontmatter がパースできない |
| `record_review.py` | レビュー 1 件を `.wikicommit/review/` 配下の不変ファイルとして記録（`wikicommit-generate` Pass 4・`wikicommit-review`・`wikicommit-synthesize`・`review-issue-close-sync.yml` 共有。Issue #750） | 引数が entity/view ツリーの外を指す、`--kind ai` に `--model` が無い、`--result` が `discarded` 以外なのにページが存在しない、JSON が壊れている、書き込みに失敗 |
| `check_review_coverage.py` | レビュー記録の集計・未レビュー／抜取候補／失効の列挙（`wikicommit-status` 専用。Issue #750） | なし（常に 0） |
| `record_run.py` | 実行 1 回を 1 ファイルとして記録（`start` で開き `end` で閉じる。4 つの書き込み系 Skill が共有。Issue #790） | 引数不正、`end` に渡されたパスが存在しない、`--outcome` の値が整数でない、frontmatter が読めない |
| `check_run_records.py` | 直近の実行と完走しなかった実行の報告（`wikicommit-status` 専用。Issue #790） | なし（常に 0） |
| `check_retracted_sources.py` | 人間が取り下げたソース（`status: retracted`）を `sources[]` に持つページの検出（`wikicommit-status` 専用。Issue #737） | なし（常に 0） |
| `check_actions_pr_permission.py` | "Allow GitHub Actions to create and approve pull requests" リポジトリ設定の確認（`wikicommit-status` 専用。Issue #478） | なし（常に 0） |
| `check_recurring_characters.py` | `properties.character` にプレーンテキストで列挙された登場人物のうち、複数作品に再登場するが Person ページを持たないものの検出（`wikicommit-status` 専用。Issue #560） | なし（常に 0） |
| `check_self_referential_tags.py` | ページ自身の `title`／`type` を繰り返すだけのタグの検出（`wikicommit-status` 専用。Issue #571） | なし（常に 0） |
| `check_installed_type_usage.py` | インストール済みスキーマファイルのうちページが 0 件のもの・より具体的な子孫型がインストール済みなのに祖先型でページが書かれているものの検出（`check_schema_coverage.py` の対。`wikicommit-status` 専用。Issue #565） | なし（常に 0） |
| `check_unlinked_entity_mentions.py` | エンティティ型を range に持つ `properties:` キーの値が、実在するページを指すのにプレーンテキストで書かれているものの検出（`check_wanted_pages.py` の鏡像。`wikicommit-status` 専用。Issue #561） | なし（常に 0） |
| `check_property_wikilink_reinforcement.py` | 型テンプレートの Entity-only/Mixed な `properties:` キーのうち、WikiLink化への補強（`granularity` 言及・`[[Type/slug]]` プレースホルダー）を持たないものの検出（`wikicommit-status` 専用。Issue #539） | なし（常に 0） |

---

## build_survey_view.py

### 目的

`/wikicommit-synthesize` を引数なしで実行した場合（俯瞰モード。Issue #586）、「何について書くか」自体を Wiki 全体から見つける必要がある。Wiki の全文は1つのコンテキストに入らないため、本スクリプトは各ページを「横断的な構造を担う数行」— `title`・`type`・`tags`・`properties.description`・`##` 見出し・発リンク — に縮約し、リンクグラフから算出した集計（ハブ・タグ・型）を添えて出力する。

**なぜ `properties.description` だけでは足りないか**: `description` は設計上「2〜3文の要約に収める」と決まっている（`docs/DesignDoc-data.md` §4.1）ため、本文にしか現れないパターン — まさに俯瞰モードが狙う着眼点 — は description のみの縮約では構造的に見えない。`##` 見出しは、本文のうち「何を扱っているか」を名指しする最も安価な部分である。リンクグラフはそれ以上に重要で、「複数の Place ページが1人の Person を経由して繋がっている」は**どの1ページの本文についての記述でもなく**、ページ同士の間にしか存在しない — 全ページを同時に見るビューだけが見つけられる。

**なぜスクリプトなのか**（SKILL.md のプローズではなく）: 「全体を俯瞰する」以上、全ページ走査の網羅性そのものが機能の前提であり、取りこぼしは黙って結果を損なう（`docs/DesignDoc-skills.md` §11.5 のスクリプト委譲パターン）。一方でスクリプトは**判断を行わない** — 縮約ビューから着眼点を選ぶのは LLM の仕事であり、そちらは本質的に非決定論的である。

**本文全体を読む案（チャンク分割 + サブエージェントの map-reduce）は採らなかった**。実行のたび Wiki 全文を読むコストに加え、横断パターンの証拠が2つのチャンクに分かれると双方のサブエージェントが「単独では平凡」として落とす分割ロスがあり、狙っている対象そのものに直撃する。将来の拡張余地として残し、その際は全ページ走査による矛盾検出（バッチをまたぐページ間矛盾。`docs/DesignDoc-pipeline.md` §7）と分割戦略・返却形式を共有する。

### 使用場面

- `wikicommit-synthesize` Skill：Step 0（俯瞰モード。`<topic>` が省略された場合のみ）
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。research guidance が渡されなかった場合のみ。Issue #672）。同じ縮約ビューを別の問いに使う — synthesize が「既存ページから何を書けるか」を探すのに対し、collect は「何が足りていないか」を探すため、`check_wanted_pages.py` の `WANTED:` と `check_orphans.py` の `ORPHAN:`（出自ソース付き。Issue #570）を併せて読む。本スクリプト側の変更は不要だった

### コマンド

```
python .wikicommit/scripts/build_survey_view.py [--lang <lang>|all] [--max-pages N] [--limit N]
```

- `--lang`: ページを列挙する言語（既定は `config.yml` の `primary_lang`）。`all` で全言語。翻訳ページは同じ内容を別の言語で述べ直したものなので、既定では列挙しない（コンテキストを消費するだけになる）。**ただしリンクグラフは常に全言語から構築する** — WikiLink は言語を持たないため、1言語分の発リンクしか数えないと全ハブが過小評価される
- `--max-pages`: 列挙するページ数の上限（既定 300、`0` で無制限）。超過分は切り捨て、`TRUNCATED:` 行で明示する
- `--limit`: ランキング（`HUB:` / `TAG:`）1つあたりの件数（既定 20）

### 処理フロー

1. `.wikicommit/entity/**/*.md` を走査する（`assets/`・`index.md`・`status: removed` のページ、および `<lang>/<Type>/<slug>.md` の形に解決できないファイルは除外）
2. 各ページの frontmatter から `title`・`type`・`tags`・`properties.description` を、本文から `##` 以下の見出しと `[[Type/slug]]` の発リンクを取得する。見出しの抽出はフェンス付きコードブロックを除去してから行う（例示中のコメント行をページの節として読まないため）
3. リンクグラフを `Type/slug` キー単位で構築する（言語を問わない。自己リンクは被リンクに数えない）
4. `--lang` で列挙対象を絞り、**被リンク数の降順**に並べる — `--max-pages` で切る場合に、Wiki の構造を担うページではなく単なるアルファベット順の一部が残るのを避けるため
5. `SURVEY:` / `TRUNCATED:` / `TYPE:` / `PAGE:`（+ `DESC:` / `HEADINGS:`）/ `HUB:` / `TAG:` を出力する

`DESC:` は 160 文字、`HEADINGS:` は 8 件、`title` は 80 文字で打ち切る。各レコードは1行であるため、値に含まれる改行は空白に潰す（潰さないと1レコードが不正な2行に割れる）。

### 出力フォーマット

```
SURVEY: pages=83, types=12, lang=ja, all_langs=en,ja
TYPE: Place 24
TYPE: AdministrativeArea 11
PAGE: Place/minuma | 見沼田んぼ | backlinks=12 | tags=治水,農業 | links=Event/minuma-reclamation,Place/minuma-tsusenbori
  DESC: 江戸時代に干拓された低湿地帯。
  HEADINGS: 歴史 / 治水との関係 / 現在
HUB: Place/minuma 12
TAG: 治水 7
```

### 終了コード

- 常に `0`（読み取り専用のレポート。読み込めないページ・フロントマターが壊れているページは stderr の `WARNING:` として報告し、そのページのみスキップする）

---

## check_extraction_quality.py

### 目的

`wikicommit-generate` Pass 1 の抽出失敗判定は従来「抽出テキストが空または読み取り不能」の場合のみ `status: failed` としており、JS実行が前提のSPAサイト等を静的フェッチ手段（`markitdown`・`curl`）で取得した際に生じる「非空だが無意味」な抽出結果（ナビゲーション・ログインプロンプト・埋め込みJSON状態等のシェルのみで、実際のページ内容を含まない）を検知できなかった（Issue #425）。本スクリプトはこれを補う3つの決定論的チェックを提供する:

- `check-domain`（ガードB・即効性）: 抽出を試みる前に、URLのドメインが「静的フェッチでは空シェルを返すことが確認済み」の既知不可ドメインかどうかを判定する。`x.com`/`twitter.com`/`music.youtube.com`（Issue #574 — YouTube Music は `www.youtube.com` へリダイレクトしないため `markitdown` の `YouTubeConverter` が適用されず、「お使いのブラウザ向けに最適化されていません」の185文字程度のシェルしか返さない）を初期エントリとする。精度は高いが、確認済みドメインしかカバーしない。
- `check-fetch-capability`（ガードC・取得能力の事前チェック。Issue #574）: 抽出を試みる前に、URLのホストが「完全な抽出に追加の Python パッケージを要する」既知ホストかどうかを判定し、要する場合はそのパッケージが実際に import 可能かを確認する。初期エントリは YouTube 系ホスト（`youtube.com`/`youtu.be`/`m.youtube.com` — この3ホストはリダイレクト解決後にいずれも `https://www.youtube.com/watch?…` に着地し、実測でバイト単位で同一の抽出結果になる）と `youtube_transcript_api`。`music.youtube.com` はリダイレクトしないため `YouTubeConverter` 自体が適用されず、パッケージを入れても解決しない — こちらはガードB（`KNOWN_JS_SHELL_DOMAINS`）の担当。判定はホスト単位であり、同じホスト上の `/watch?v=…` と `/shorts/<id>`・`/playlist`・チャンネルページを区別しない（後者も `YouTubeConverter` の前方一致要件を満たさず抽出できないが、ガードCは「そのホストが要するパッケージが導入済みか」しか保証しない — 残りは `wikicommit-generate` Pass 1 手順6の抽出結果の形状チェックが担う）。
- `check-density`（ガードA・汎用安全網）: 抽出後のテキストに対し、自然文らしい文字がどの程度の割合を占めるかを判定する。ドメインを問わない一般的なヒューリスティックで、ガードBがカバーしない未知のケースを拾う代わりに精度は低い。

ガードCが独立した軸として必要な理由（Issue #574）: `markitdown` の `YouTubeConverter` は `youtube_transcript_api` が未導入だと `IS_YOUTUBE_TRANSCRIPT_CAPABLE = False` となり、**例外も警告も出さずに** `### Transcript` セクションごと出力から落とす。残るのはタイトル・キーワード・Runtime・概要欄で、これらは実際の自然文であるため、空シェルでも低密度でもない — 実測でガードAの比率は字幕ありで 0.93、字幕なしで 0.90、タイトル+Runtime のみの最小ケースでも 0.75 であり、閾値 0.3 をどう調整しても区別できない（長さではなく文字種で判定する設計そのものによる）。ガードBの既知不可ドメインに `youtube.com` を追加する案も、「静的フェッチで空シェルしか返さないことが確認済みのドメイン」という定義に反する（字幕込みなら十分な内容が取れる）ため採らなかった。つまりこれは「空シェル」でも「低密度」でもなく **partial extraction** であり、取得後のテキストを見る限り検出しようがない。取得前に「取得能力があるか」を確かめる別軸のチェックが要る。

事前チェックにする理由: 取得後に `### Transcript` の有無だけを見ても、「パッケージ未導入」と「その動画に字幕が存在しない」を区別できない。前者はユーザーが一度直せば済む環境の問題、後者はそのソース固有の事実であり、扱いを変える必要がある（`wikicommit-generate` Pass 1 は前者で処理全体を停止して `pip install` を案内し、後者は `status: failed` にせず Completion Notice にロールアップする）。事前チェックであればこの曖昧さが構造的に発生しない。

**3つのガードの強度は同じではない**（Issue #562・#574）。ガードCはガードBと同じくブロッキングだが、失敗の意味が異なる — ガードBはそのソースを `status: failed` にして次のソースへ進むのに対し、ガードCは**処理全体を停止する**（`markitdown --version` の Prerequisite チェックと同じ扱い。環境の問題であってソースの問題ではないため、`status: failed` として記録してはならない）。ガードBの `BLOCKED:` は確認済みドメインに対する決定論的判定であり、`wikicommit-generate` Pass 1 はこれをブロッキング（`status: failed`）として扱う。ガードAの `LOW_DENSITY:` はテキスト形状のヒューリスティックにすぎず、Pass 1 はこれを**人間に続行可否を確認する警告**として扱う（非対話実行時のみ従来どおり `status: failed`。詳細は `docs/DesignDoc-pipeline.md` §6.1・`.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。本スクリプト自身の終了コードは両者とも `1` のままで、強度の違いは呼び出し側の扱いにある。

3つのガードは排他ではなく、`wikicommit-generate` Pass 1 で順に適用される（`.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。`check-domain` は `wikicommit-collect` の候補提示ステップからも、既知不可ドメインを候補から事前に除外する目的で呼ばれる。

**このスクリプトが扱わない partial extraction がある（Issue #715）**。ガードC が扱うのは「必要なパッケージを入れれば `markitdown` が完全に取れる」種類の欠落だけであり、`importlib.util.find_spec()` による判定はその前提の上に立っている。GitHub の Issue / PR URL は本文が取れてコメントだけが黙って落ちるが、必要なのはパッケージではなく別の取得経路なので、この前提を満たさない — ガードC を一般化すると exit 1 の意味（処理全体を止めて `pip install` を案内する）が端的に誤りになる。ガードB は「空シェル」の定義に反し（本文は取れている）、ガードA は落ちているものが自然文なので形状で区別できない（実測 0.37〜0.53 で閾値を余裕を持って上回る）。

したがってこの失敗クラスは**本スクリプトではなく `add_source.py` の登録時通知**が扱う（`partial_extraction_note()` / `PARTIAL_EXTRACTION_URL_NOTES`。ブロックせず・`status` を変えず・登録時に一度だけ知らせる）。**ここに 4 つ目のガードを足さないこと** — ガードは Pass 1 の分岐を左右するものであり、ブロックしない判定を同じ場所に置くと、精度の異なる 2 ガードを同じ強度で扱っていた Issue #562 の混同を作り直すことになる。詳細と、次に 3 例目が出たときの判断手順は `docs/DesignDoc-pipeline.md` §6.1 の該当コールアウトを参照。

### 使用場面

- `wikicommit-generate` Skill：Pass 1（`type: url`/`wikicommit` ソースの抽出前に `check-domain` → `check-fetch-capability`、全ソース種別の抽出成功後に `check-density`）
- `wikicommit-collect` Skill：Web候補提示ステップで `check-domain` を呼び、既知不可ドメインの候補を事前に除外する

### コマンド

```
python .wikicommit/scripts/check_extraction_quality.py check-domain <url>
python .wikicommit/scripts/check_extraction_quality.py check-fetch-capability <url>
python .wikicommit/scripts/check_extraction_quality.py check-density [<file>]
```

`check-density` は `<file>` を省略した場合、標準入力からテキストを読む（抽出テキストがファイルとして永続化されていないソース種別向け。詳細は `.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。

### 処理フロー（`check-domain`）

1. URLからホスト名を抽出する（`www.` プレフィックス・ポート番号は正規化して除去）
2. スクリプト内にハードコードされた `KNOWN_JS_SHELL_DOMAINS` 集合（初期値: `x.com`, `twitter.com`）に一致するか確認する。一致すれば `BLOCKED:` を出力して終了する
3. `.wikicommit/source-policy.md` の `wikicommit.exclude_domains`（Issue #564。`docs/DesignDoc-data.md` §3.4）を読み、**組み込みリストとの和集合**として同じ判定を行う。一致すれば `BLOCKED:`（組み込み側とは別のメッセージ。どちらのリストで落ちたかを呼び出し側が区別できる）を出力して終了する
4. どちらにも一致しなければ `OK:` を出力する

新しいドメインをこの集合に追加する場合は、実際に空シェルが返ることを確認した上で追加すること（未確認のまま追加すると、本来は正常に取得できるドメインの抽出を無条件にスキップしてしまう）。

`exclude_domains` の各エントリは `_domain_of()` と同じ形（スキーム・パス・ポート・先頭 `www.` を除去し小文字化）に正規化してから**完全一致**で比較する（`example.com` は `blog.example.com` に一致しない）。正規化しないと、人間が `rejected:` の `url:` に倣って `https://example.com/` のように書いた場合に一致せず、ファイル上は除外されているのに実際には取得され続ける。ファイルが無い・フロントマターが壊れている・値がリストでない、のいずれも「追加ドメインなし」として扱い、組み込みリストによる判定は必ず生き残る — ただしフロントマターのパースに失敗した場合のみ stderr に `WARNING:` を出す（`wikicommit-collect` がこのファイルの `rejected:` に追記する以上、追記ミス 1 回で `exclude_domains` 全体が無言で無効化されうるため。stdout の `BLOCKED:`/`OK:` 契約は変えない）。

### 処理フロー（`check-fetch-capability`）

1. URLからホスト名を抽出する（`check-domain` と同じ `_domain_of()`。`www.` プレフィックス・ポート番号は正規化して除去）
2. スクリプト内にハードコードされた `_FETCH_CAPABILITY_REQUIREMENTS`（ホスト → `(import 名, pip 名, 未導入時に欠ける内容)`）に一致するか確認する。一致しなければ `OK:` を出力して終了する
3. 一致した場合、`importlib.util.find_spec()` でそのパッケージが import 可能かを確認する。可能なら `OK:`、不可能なら `MISSING_PACKAGE:`（`pip install <pip 名>` を含む）を出力する

ホストは完全一致で判定するため、同じサイトが到達可能な別名をすべて列挙する必要がある（`youtube.com`/`youtu.be`/`m.youtube.com` の3形式は `markitdown` がリダイレクト解決後の最終URLで変換器を選ぶため、いずれもバイト単位で同一の抽出結果になることを実測確認済み。`music.youtube.com` だけはリダイレクトしないため対象外 — 上記「目的」節参照）。

### 処理フロー（`check-density`）

1. テキストをトークン化する。空白区切りに加え、**URL の境界でもトークンを切る**（スキーム付き `https://…`・プロトコル相対 `//upload.wikimedia.org/…`・裸の `www.…`）。空白だけで切ると、分かち書きしない日本語では地の文とパーセントエンコードされたリンク先URLが1つの巨大トークンに融合し、次の手順のURL判定が地の文もろとも捨ててしまう（Issue #562）。空白で単語を区切る言語ではURLは元から独立したトークンなので、この変更は結果を変えない。また URL 自体は空白・Markdown のリンク/引用区切り文字に加え、**CJK 文字・全角記号でも終端する** — URI は ASCII のみで構成されるため実在のリンク先を途中で切ってしまうことはなく、逆にこれがないと分かち書きしない日本語では裸の URL（Markdown リンクと違い `)` で終わらない）が後続の地の文を丸ごと飲み込み、同じ融合が再発する
2. URL トークンは無条件に「非自然文的トークン」とする。それ以外のトークンは、以下のいずれかに該当する場合に「非自然文的トークン」と判定する:
   - `{`・`}`・`<`・`>`・`;`・`=` のいずれかを含む
   - `"` を2個以上、または `` ` `` を含む
   - 上記に該当せず、前後の記号を除去した中核部分の英字比率が70%未満
3. 各トークンの文字数を重みとして、「自然文的トークン」の文字数の割合（`natural-language character ratio`）を計算する（トークン数ではなく文字数で重み付けすることで、単語間にスペースを持たないCJK言語〈日本語等〉が不当に低く判定されることを防ぐ）。文字数の数え方には Issue #562 で2つの正規化を入れている:
   - CJK 文字は `CJK_CHAR_WEIGHT`（3）文字分として数える。CJK 文字1字が担う情報量はラテン文字1字よりはるかに多く（`extracted_tokens` の概算がラテン文字4字≒1トークンと見積もるのに対し、CJK は1字≒1トークン）、同じ重みで数えると同じリンク密度の同等な散文でも日本語だけが不当に低く出るため。この重みは CJK を含まないテキスト（ガードAが本来捕まえるべき ASCII の JS/ナビシェル）には定義上まったく影響しない
   - URL トークンはパーセントデコードした長さで数える。`%E3%81%95` は日本語1文字が転送エンコードで9文字に膨らんだものにすぎず、そのまま数えると日本語ページへのリンクが英語ページへの同じリンクの9倍のマークアップに見えてしまうため
4. 比率が `LOW_DENSITY_THRESHOLD`（0.3）未満であれば `LOW_DENSITY:`、以上であれば `OK:` を出力する。`LOW_DENSITY:` の場合は、非自然文と判定された文字の内訳（`links` / `numbers/tables` / `other markup` の割合）を同じ行に添える — 人間が続行可否を判断する材料として、リンクが多いだけの正当なページ・統計表・実際のスクリプトシェルを見分けられるようにするため（Issue #562）

> **既知の限界: 数表密度**（Issue #562）: 統計表・数値中心の資料（国勢調査の結果概要・統計書等）は、非自然文の正体がリンクではなく数値と表の `|` 記号であるため、手順1のURL境界トークン化では比率が回復しない（saitama パイロットの実測で 0.112 / 0.080 のまま変化なし）。これは実装の欠陥ではなく汎用ヒューリスティックとしての精度の限界であり、追加の検出ロジックは設けない — ガードAが警告どまりであること（上記）と、手順4の内訳が `numbers/tables` 優位として表示されることで、人間が続行を判断できる。`check_wanted_pages.py` の「地の文言及は対象外」と同じ種類の、意図して残した限界である。

### 出力フォーマット

```
MISSING_PACKAGE: youtube.com requires the youtube-transcript-api package to extract the video's transcript (without it, only the title, keywords, runtime and description are extracted — the video's actual content is missing). Install it with: pip install youtube-transcript-api
OK: youtube.com: youtube_transcript_api is installed
OK: example.com needs no extra extraction package
BLOCKED: x.com is a known JS-rendering-required domain; static fetch (markitdown/curl) has been confirmed to sometimes return an empty content shell with no meaningful text. See docs/DesignDoc-pipeline.md §6.1 (Issue #425).
OK: example.com is not a known JS-shell domain
LOW_DENSITY: .wikicommit/.cache/ingest-fetch/x.com/karpathy-status-1886192184808149383.md (natural-language character ratio: 0.09, threshold: 0.3) — extracted text looks like boilerplate/markup rather than real content. non-prose breakdown: links 12%, numbers/tables 3%, other markup 85%.
OK: .wikicommit/.cache/ingest-fetch/example.com/article.md (natural-language character ratio: 0.72)
```

### 終了コード

- `check-domain`: `0` = 組み込みの既知不可ドメインにも `source-policy.md` の `exclude_domains` にも一致しない、`1` = どちらかに一致する
- `check-fetch-capability`: `0` = 追加パッケージ不要、または必要なパッケージが導入済み、`1` = 必要なパッケージが未導入。`1` は呼び出し側にとって「処理全体を停止して `pip install` を案内する」シグナルであり、そのソースを `status: failed` にするシグナルではない（Issue #574）
- `check-density`: `0` = 低密度でない、`1` = 低密度、またはファイルが読み込めない。`1` は呼び出し側にとって警告であってブロッキングではない（上記「3つのガードの強度は同じではない」参照）

---

## validate_frontmatter.py

### 目的

`.wikicommit/entity/` 配下の Wiki ページが、フロントマター仕様を満たしているかを検証する。

### 使用場面

- `wikicommit-merge` Skill：品質ゲートとして変更ファイルのみを対象に実行
- `wikicommit-review` Skill：手動ページ（経路 B）のレビュー前チェック

### コマンド

```
python .wikicommit/scripts/validate_frontmatter.py [<path>...]
```

- 引数なし: `.wikicommit/entity/` 配下の全 `.md` ファイルを対象
- 引数あり: 指定ファイルのみ対象（複数指定可）

### 処理フロー

1. 対象ファイルの YAML frontmatter を読み込む
2. `type` フィールドから型名を取得する（例: `schema:Person` → `Person`、`schema:custom/Decision` → `custom/Decision`）
3. 対応するスキーマファイルを特定する:
   - `schema:Person` → `.wikicommit/schema/Person.md`
   - `schema:custom/Decision` → `.wikicommit/schema/custom/Decision.md`
   - スキーマファイルが存在しない場合 → `.wikicommit/schema/default.md` で代替
4. `.wikicommit/schema/default.md` の `wikicommit.frontmatter.required` と、型スキーマの `wikicommit.frontmatter.required` を結合して必須フィールドリストを構築する（型スキーマの required は default の required に追加する。上書きしない）
5. 必須フィールドリストの各フィールドが frontmatter に存在するか検証する。以下の例外を適用する:
   - 翻訳ページ（`translated_from` あり）は `sources` の必須を免除する（ソース情報は `translated_from` で辿った親ページから継承するため）
   - 合成ページ（`derived_from` あり）も同様に `sources` の必須を免除する（ソース情報は `derived_from` が表すため。`wikicommit-synthesize` の出力）
   - `index.md`（ファイル名が `index.md`）は `sources` の必須を免除する（`wikicommit-generate` が自動生成するシステムページのため）
6. `review_status` フィールドが frontmatter に存在しない場合、WARNING を出力する（`pending` として扱う）。`review_status` は必須フィールドリストに含まれないため手順 5 では検出されない。この手順で明示的に処理する。
7. 以下のフォーマット検証ルールを、フィールドが存在する場合に適用する

### フォーマット検証ルール

必須・任意を問わず、フィールドが frontmatter に存在する場合に適用するフォーマット検証。

#### Wiki ページ共通フィールド

| フィールド | 型 | フォーマット制約 |
|---|---|---|
| `title` | string | 空文字列不可 |
| `lang` | string | ISO 639-1 2文字コード（`[a-z]{2}` の正規表現） |
| `type` | string | `schema:` プレフィックスで始まること。`custom/` プレフィックスを持たず（`type_name` が `custom/` で始まらず）、かつ Schema.org 語彙（`.wikicommit/schemaorg-vocab.json`）にも実在しない場合は ERROR（Issue #512。誤字・命名規約違反等の検出。`custom/` プレフィックスを持つ型、および語彙が取得できない場合はこの検証をスキップする — 前者は Schema.org 語彙に存在しないことが正規の設計であるため、後者は §5.2 の `properties:` フォーマット検証と同じ理由で非ブロッキングとする）。`.wikicommit/schema/<Type>.md` というローカルファイルが実際に存在するかどうかとは独立の判定であり、両者は食い違いうる — ローカルファイルがなければ `resolve_type_schema()` 側の別の WARNING（「スキーマファイルが見つかりません」）も同時に出る。この ERROR はキャッシュの鮮度にも影響される点に注意: `.wikicommit/schemaorg-vocab.json` は TTL を持たず手動削除でのみ再取得されるため（`_schemaorg_vocab.py`）、Schema.org 側で新しく追加された型を使ったページは、そのリポジトリのキャッシュが再取得されるまで本 ERROR で `wikicommit-merge` がブロックされ続ける。対処はキャッシュファイルを手動削除して再実行すること。**あわせて、ページのファイルパスと `type:` の一致も検証する**（Issue #545）: `.wikicommit/entity/<lang>/<Type>/<slug>.md` に置かれたページの `type:` は `schema:<Type>` でなければならず、custom 型では `custom/` サブパスを含む（`schema:custom/Decision` は `.wikicommit/entity/<lang>/custom/Decision/` に置く。`_wikilink.py` の `parse_wiki_path()` がパスから `(lang, type, slug)` を導出する）。不一致は ERROR。`<lang>/<Type>/<slug>.md` の形に解決できないファイル（`.wikicommit/entity/` 直下に置かれたページ、Issue #477 以前の `.wikicommit/wiki/` プレフィックスのままのページ）はこの検証の対象外とし、何も報告しない（新旧混在を許容する方針）。`type:` 自体が欠落している・`schema:` プレフィックスを持たない場合も、それぞれ別に報告済みのため重ねて報告しない |
| `sources` | list | 1件以上（翻訳ページは除く） |
| `review_status` | string | `pending` / `reviewed` のいずれか（それ以外の値は ERROR）。省略時は WARNING（`pending` として扱う） |
| `expires_at` | string | `YYYY-MM-DD` 形式 |
| `wikidata` | string | `wd:Q` で始まること |
| `tags` | list | 各要素は string |
| `generated_at` | string | `YYYY-MM-DD` 形式 |
| `generated_by` | string | 空文字列不可 |
| `generated_with` | string | 空文字列不可。このページを生成した WikiCommit 自身の版（Issue #577。任意フィールドで、欠如は「この機能追加より前に生成された」ことを意味する。semver パターンへの照合は行わない — モデル ID を正規化表に照合しないのと同じ理由） |

#### `sources` 各要素のフォーマット

`type` フィールドの存在確認・許可値チェックを最初に行い、未定義または許可値以外の場合は ERROR（以降のフィールド検証はスキップ）。

| source.type | フィールド | フォーマット制約 |
|---|---|---|
| （全要素） | `type` | `path` / `url` / `wikicommit` / `manual` のいずれか。未定義または許可値以外は ERROR |
| `path` | `path` | リポジトリ内に実在するパス |
| `path` | `hash` | `sha256:` プレフィックス |
| `url` | `url` | `https://` で始まること |
| `url` | `hash` | `sha256:` プレフィックス |
| `wikicommit` | `url`, `hash` | 同上 |
| `manual` | `author` | 非空文字列 |
| `manual` | `created_at` | `YYYY-MM-DD` 形式 |
| （全要素） | `license` | 任意。存在する場合は空でない文字列（空文字列は ERROR。「不明」はフィールドごと省略して表す）。値の中身は検証しない — SPDX 語彙への照合もソースの実際の条件との突合も行わない（Issue #558。`docs/DesignDoc-publish.md` §8.10） |

#### `properties:` のフォーマット（Issue #495）

`properties:` が存在し、かつ dict 型以外（文字列・リスト等）であれば ERROR。存在しない、または YAML 上「値なし」（`properties:` の下に何も書かれていない。パース結果は `None`）の場合は「型固有プロパティなし」として扱い ERROR にしない。

dict であれば、各キーについて以下を検証する（`properties:` が存在しないページでも、型固有プロパティの平置き検出〈後述〉のために 1〜5 の型解決自体は常に行う）:

1. ページの `type:` が `schema:` プレフィックスを持たない場合は検証をスキップ（`type` 自体のフォーマットエラーとして別途報告済み）。
2. `type:` の型名（`schema:` プレフィックスを除いた部分）が `custom/` で始まる場合は検証をスキップ — カスタム型は Schema.org 語彙に存在しないため、`properties:` の妥当性は `wikicommit-schema-propose` の PR レビュー時に人間が確認する（`docs/DesignDoc-data.md` §5.3）。
3. `.wikicommit/schemaorg-vocab.json`（`_schemaorg_vocab.py` 経由。`check_schema_org_type.py` と共有）を読み込む。取得できない場合（未コミット・削除後未再生成・ネットワーク不通等）は、`properties:` に1件以上キーがあるページに限り WARNING を1件出力し、`properties:` の検証・平置き検出の両方をこの実行ではスキップする（ブロッキングにしない — ネットワーク不調やキャッシュ未生成でマージが止まるのを避けるため）。
4. 型が語彙に存在しない場合は ERROR（Issue #512。`type` フィールドに対する ERROR — 上記「Wiki ページ共通フィールド」表の `type` 行と同じ検証をここで実行する。誤字・命名規約違反等で `.wikicommit/schema/<誤った型名>.md` というローカルファイルさえ存在すれば `resolve_type_schema()` は WARNING すら出さずに通過してしまうため、`properties:` を検証する `validate_schema_properties()` 側でも独立に検証する）。この場合、`properties:` の各キー検証・下記のトップレベル平置き検出のいずれも実行せず打ち切る（型の祖先チェーンが解決できないため、いずれも判定不能）。
5. 型が語彙に存在する場合、`properties:` の各キーが `rdfs:subClassOf` による祖先チェーンを含めて型の `domainIncludes` に属するかを検証する。属さない、またはキー自体が Schema.org 語彙に存在しない場合は ERROR。

**トップレベルへの平置き検出**: 上記 1〜3・5 で型が解決できた場合（4 で ERROR になった場合を除く）、`properties:` の中身とは別に、フロントマターのトップレベルに存在するキーのうち構造的フィールド一覧（`title`/`lang`/`type`/`sources`/`tags`/`review_status`/`expires_at`/`generated_at`/`generated_by`/`generated_with`/`wikidata`/`sameAs`/`aliases`/`properties`/`translated_from`/`source_commit`/`translated_at`/`translated_by`/`translated_with`/`translator_notes`/`derived_from`/`status`/`removed_at`/`removed_reason`/`merged_into`）に含まれないものを走査し、それが実際にそのページの型（祖先型含む）に属する Schema.org プロパティである場合は ERROR とする（例: `description:` をトップレベルに平置きしたページ。`properties:` へのネストが必須という Issue #495 の設計を LLM や人間の書き忘れから機械的に守るためのガード）。型に属さない、または Schema.org 語彙に存在しないキーは対象外（無関係な独自フィールドを誤検知しないため）。

#### 翻訳ページ追加フィールド（`translated_from` が存在するページ）

| フィールド | 必須/任意 | フォーマット制約 |
|---|---|---|
| `translated_from` | 必須 | リポジトリルートからの相対パス（例: `.wikicommit/entity/ja/Person/yamada-taro.md`）。対象ファイルが実在すること（Issue #477 以前に書かれた `.wikicommit/wiki/` プレフィックスのままの値も `_wikilink.py` の `resolve_stored_entity_path()` 経由で解決を試みる。`docs/DesignDoc-data.md` §3.1 の該当コールアウト参照） |
| `source_commit` | 必須 | 40文字の git コミットハッシュ（`[0-9a-f]{40}`）、または空文字列（Issue #409 — `wikicommit-translate` は原文ページに commit が無い場合〈生成直後でまだ `wikicommit-merge` されていない等〉、空文字列のまま書き込む。`check_translation_status.py` はこれを正しく `STALE` として検知する） |
| `translated_at` | 任意 | `YYYY-MM-DD` 形式 |
| `translated_by` | 任意 | 空文字列不可（`generated_by` と同じフォーマット制約。翻訳実行モデル ID。Issue #453） |
| `translated_with` | 任意 | 空文字列不可（`generated_with` と同じフォーマット制約。この翻訳を生成した WikiCommit 自身の版。Issue #577） |
| `translator_notes` | 任意 | list 型（各要素は string）。各要素の内容自体（`YYYY-MM-DD: <note>` 形式）に対する機械検証は行わない（`## User Notes` と同じ、フリーテキストの人間/LLM向けメモのため。Issue #524） |

#### 合成ページ追加フィールド（`derived_from` が存在するページ）

| フィールド | 必須/任意 | フォーマット制約 |
|---|---|---|
| `derived_from` | 必須 | list 型・1件以上の要素が必要 |
| `derived_from[].path` | 必須 | リポジトリルートからの相対パス。対象ファイルが実在すること（`translated_from` と同じく Issue #477 以前の `.wikicommit/wiki/` プレフィックス値も解決を試みる） |
| `derived_from[].source_commit` | 必須 | 40文字の git コミットハッシュ（`[0-9a-f]{40}`）、または空文字列（`source_commit` と同じ理由。`wikicommit-synthesize` が出自ページ未コミット時に空文字列を書き込む。`check_derivation_freshness.py` が `STALE` として検知する） |

#### 削除ページ追加フィールド（`status: removed` が存在するページ）

| フィールド | 必須/任意 | フォーマット制約 |
|---|---|---|
| `status` | — | `removed` のみ（他の値は frontmatter エラー） |
| `removed_at` | 必須 | `YYYY-MM-DD` 形式 |
| `removed_reason` | 任意 | `obsolete` / `merged` / `gdpr` のいずれか |
| `merged_into` | `removed_reason: merged` 時は必須 | 指定ファイルがリポジトリ内に実在すること |

### 出力フォーマット

```
ERROR: .wikicommit/entity/ja/Person/yamada-taro.md: title: required field is missing
ERROR: .wikicommit/entity/ja/Person/yamada-taro.md: sources[0].hash: is missing the `sha256:` prefix
WARNING: .wikicommit/entity/ja/Person/yamada-taro.md: review_status: not set (treated as pending)
OK: 12 files validated, 0 errors, 1 warnings
```

### 終了コード

- `0`: エラーなし（warning のみを含む）
- `1`: ERROR が 1 件以上

---

## check_wikilinks.py

### 目的

変更ファイル内の `[[Type/slug]]` 形式の WikiLink を解析し、参照先の存在確認と `status: removed` ページへのリンク検出を行う。

### 使用場面

- `wikicommit-merge` Skill：品質ゲートとして変更ファイルを対象に実行

### コマンド

```
python .wikicommit/scripts/check_wikilinks.py [--changed <path>... [--deleted <path>...]]
```

- `--changed`: 追加・変更されるファイル（WikiLink の参照先を検証する対象）
- `--deleted`: `status: removed` を新たに付与するファイル（被リンクの残存を確認する対象）
- **引数なし**: `.wikicommit/entity/` 配下の全ページ（`assets/` を除く）を検査対象にする（Issue #571）。`--changed` 相当だが、**同一コミット内新規追加の例外は無効**にする — あの例外は「参照先はまだ存在しないがこの変更が追加する」という意味であり、対象集合が「既にディスク上にある全ページ」であるときには意味を持たない。有効なままだと全リンクがその分岐を通り、`<primary_lang>` にしか存在しないページへの他言語ページからのリンクが「翻訳ページ未作成」の WARNING を出さずに黙って通ってしまう（このモードが出しうる 2 種類の WARNING の片方が原理的に出なくなる）。`status: removed` ページへのリンクは通常の存在確認経路が同じ ERROR を出す。従来は `OK: 0 files checked, 0 errors, 0 warnings` を出して終了コード 0 で終わっており、**正常なチェックの成功と区別がつかない出力**だった（他の多くのスクリプトは引数なしで全ファイルを対象にするため、このスクリプトだけが逆の挙動でもあった）。`--deleted` は引数なしモードでは空のまま — 「この変更でこれらのファイルが removed になる」という意味は差分の中にしか存在せず、差分の外に対応物が無い。既に `status: removed` を持つページは従来どおり `--changed` 側から辿られる。`wikicommit-merge` は常に `--changed` を渡すため、差分スコープの挙動は変わらない

### 処理フロー

1. `--changed` の各ファイルから `[[Type/slug]]` パターンを抽出する
2. 各 WikiLink について以下を検証する:
   - `<lang>` の決定: チェック対象ファイルの `lang` フィールドを基準言語とする
   - 参照先の解決順序（`[[Type/slug]]` に lang は含まれないため以下の順で検索）:
     1. `.wikicommit/entity/<lang>/<Type>/<slug>.md` が存在すれば OK
     2. 上記が存在せず、`.wikicommit/config.yml` の `primary_lang` での `.wikicommit/entity/<primary_lang>/<Type>/<slug>.md` が存在する場合 → WARNING のみ（翻訳ページ未作成）
     3. いずれの言語にも存在せず、**同じ slug のページが別の Type に実在する** → **ERROR**（Issue #563。実在する Type を名指しする。詳細は下記）
     4. いずれの言語・いずれの Type にも存在しない → **WARNING**（Issue #340。旧 ERROR。ブロックすると LLM・人間の双方が「まだ無い概念は WikiLink 化せず地の文のまま書く」を選びがちになり、複数ソースで繰り返し言及される一般概念がページ化されないまま埋もれる問題があったため緩和した。集計は `check_wanted_pages.py` が別途担う）
   - 参照先ページの `status` が `removed` か → removed の場合は ERROR（変更なし。CLAUDE.md の orphan 検出の非対称設計が指す、削除フローの順序制約回避のための意図的なブロック）
   - 例外: `--changed` 内に同じ `<lang>/<Type>/<slug>` で新規追加されるファイルが存在する場合は上記 ERROR / WARNING としない（同一コミット内の新規追加ページへのリンク）
3. `--deleted` が指定された場合、削除対象ページへの被リンクを `.wikicommit/entity/` 全体から検索する → 残存する被リンクがあれば WARNING

#### Type セグメントの取り違え（Issue #563）

`[[Type/slug]]` は Type セグメントと slug の**両方**が一致して初めて解決するため、slug は合っているが Type だけを間違えた WikiLink は「参照先が存在しない」として扱われる。しかし実体はリポジトリに在るので、正しい対処は新規ページの作成ではなく**リンク 1 語の修正**であり、上記 4.（Issue #340 の WARNING）とは行動が正反対になる。両者はメッセージ上まったく区別がつかず、`check_wanted_pages.py` に至っては「これから作るべきページ」として提示してしまう（そのとおりに作れば内容の重複した 2 ページができ、`check_orphans.py` の重複判定は `type` が違うため検出しない）。

そのため、未解決 WikiLink を検出した時点で `.wikicommit/entity/` を全 Type 横断で走査し、同じ slug を持つページが別の Type に実在すれば **ERROR** として報告する。`wikicommit-merge` をブロックする点は既存の `status: removed` へのリンクと同じ。

- **Issue #340 の緩和と衝突しない**: #340 が ERROR を避けた理由は、ブロックすると書き手が「まだ無い概念は WikiLink 化せず地の文で書く」という回避行動を取り、繰り返し言及される概念がページ化されないまま埋もれることにあった。このケースにはその回避行動が存在しない — 参照先は既にページを持っており「まだ無い概念」ではないため、WikiLink 化をやめる動機が生まれない。実在しない slug への WikiLink は WARNING のまま変わらない。
- **探索範囲は言語を問わない**: `check_orphans.py` の orphan 判定が既に言語を問わず slug 単位で照合している前例に倣う。Type セグメントの正誤は、そのページがどの言語ディレクトリにあるかとは独立に決まる。
- **複数の Type に実在する場合は全件を列挙する**: どれを意図したかはスクリプトには判定できず、候補を全部見せる方が人間が 1 手で選べる。
- **候補から除外するページが 2 種類ある**: `index.md`（`rebuild_index.py` が全 Type に生成するシステムページで、slug の一致に意味が無い）と `status: removed` のページ（そこへリンクを付け替えても `status: removed` へのリンクという別の ERROR になるだけで、「使えるページが無い」という 4. の報告の方が正確）。
- 判定ロジック（`build_slug_type_index()` / `other_types_for_slug()`）は `_wikilink.py` に置き、`check_wanted_pages.py` と共有する。独立に実装するとドリフトする、というのが `_wikilink.py` 自体の存在理由。

**既知の偽陽性と回避手段**: 同じ slug を別々の Type で正当に使いたい場合（`Organization/apple` と `DefinedTerm/apple` のように、綴りが同じで別物のエンティティ）、後から書く方の WikiLink はこの ERROR に当たる。スクリプトには両者を区別する手立てが無い（区別できるならそもそも取り違え自体が起きない）ため、これは意図した挙動として受け入れる。回避手段は 2 つあり、いずれも通常の運用の範囲に収まる: (1) 参照先ページを**同じバッチで作成する** — 同一コミット内で新規追加されるページへのリンクは既存の例外規則によりそもそもこのチェックに到達しない、(2) slug を区別できるものに変える（`apple-inc` と `apple-fruit` 等）。ERROR メッセージが断定形ではなく「Type セグメントの誤りの可能性」と書かれているのはこのためである。

### 出力フォーマット

```
WARNING: .wikicommit/entity/ja/Person/yamada-taro.md: [[Place/nonexistent]] → page does not exist
ERROR: .wikicommit/entity/ja/Person/yamada-taro.md: [[Place/tokyo]] → links to a page with status: removed
ERROR: .wikicommit/entity/ja/GovernmentService/ward-office.md: [[Organization/saitama-city]] → this page does not exist, but the same slug exists at AdministrativeArea/saitama-city.md (the Type segment may be wrong)
WARNING: .wikicommit/entity/ja/Place/tokyo.md (being changed to status: removed): a backlink remains (.wikicommit/entity/ja/Person/yamada-taro.md)
OK: 3 files checked, 2 errors, 2 warnings
```

### 終了コード

- `0`: ERROR なし（WARNING のみを含む）
- `1`: ERROR が 1 件以上

Issue #340 で「参照先ページが存在しない」ケースを ERROR から WARNING に変更したため、blocking ケースは一度 `status: removed` へのリンクのみになった。Issue #563 でそこに「別 Type に同名 slug が実在する未解決 WikiLink」が加わっている。終了コードの仕組み自体（`total_errors > 0` で `1`）は一貫して変更していない。

---

## check_raw_html.py

### 目的

Wiki ページ本文（frontmatter を除く）に生 HTML タグ（`<script>`・`<iframe>` 等）が混入していないかを検証する。CLAUDE.md・`docs/DesignDoc-publish.md` §8.6 が定める「画像・動画・YouTube の埋め込みは標準 Markdown 構文 `![alt](path-or-url)` のみで行う」という設計の下では、ページ本文が生 HTML タグを必要とする正当なユースケースは存在しない。一方 Quartz コアは `remarkRehype(..., { allowDangerousHtml: true })` を常時有効にしており、`enableInHtmlEmbed`（Obsidian Flavored Markdown プラグインのオプション）の値に関わらず生 HTML を常にそのまま HTML 出力へ通す。経路A（`docs/DesignDoc-pipeline.md` §6.3）では `review_status: pending` の LLM 生成ページが人間レビュー前に一旦 main マージ・公開されるため、ingest 元文書に埋め込まれた悪意ある HTML（間接プロンプトインジェクション等）や LLM のハルシネーションで生 `<script>`/`<iframe>` がページ本文に混入すると、レビュー前に公開サイトで実行されうる（Issue #377）。本スクリプトはこれを `wikicommit-merge` のブロッキング品質ゲートとして防ぐ。

### 使用場面

- `wikicommit-merge` Skill：品質ゲートとして変更ファイルを対象に実行

### コマンド

```
python .wikicommit/scripts/check_raw_html.py               # 全ファイル
python .wikicommit/scripts/check_raw_html.py <path>...     # 指定ファイルのみ
```

- 引数なし: `.wikicommit/entity/` 配下の全 `.md` ファイルを対象
- 引数あり: 指定ファイルのみ対象（複数指定可）

### 処理フロー

1. 対象ファイルの YAML frontmatter を除いた本文を取得する（frontmatter 自体は検証対象外。frontmatter の解析に失敗したファイルは WARNING を出力してスキップする — 構造的な frontmatter エラー自体は `validate_frontmatter.py` の責務のため）
2. 本文からコードフェンス（バッククォート3つ、または `~~~`）とインラインコード（バッククォートで囲んだ範囲）で囲まれた範囲を除外する。これらは Markdown がエスケープされた地の文として描画するため、`allowDangerousHtml` の影響を受けず実害がない（例: HowTo ページがコード例として `<script>` を紹介していても検出対象にしない）
3. 残った本文に対し、`<tag ...>` / `</tag>` 形式の HTML タグを走査する
4. CommonMark オートリンク（`<https://example.com>`・`<user@example.com>` 等）はタグ名の直後に `:`/`@` が続くため HTML タグのパターンに一致せず、自然に除外される（`wikicommit-generate` Pass 3 のベア URL 対応で明示的に使われる記法のため誤検知させない）
5. 1件でも検出したら、そのタグ（120文字を超える場合は切り詰め）を含む ERROR を出力する

タグの許可リスト（例: `<br>` のみ許可する等）は持たない — 「危険なタグだけ禁止」ではなく「生 HTML自体を一切禁止」という設計判断のため（`docs/DesignDoc-publish.md` §8.6「生 HTML の扱い方針」参照）。この設計上、`a<b>c` のような（コードフェンス外の）不等式チェーンを誤検知する可能性があるが、fail-safe なブロッキングゲートとして許容する既知の限界とする。

### 出力フォーマット

```
ERROR: .wikicommit/entity/ja/Person/yamada-taro.md: raw HTML tag detected: <script>
ERROR: .wikicommit/entity/ja/Person/yamada-taro.md: raw HTML tag detected: </script>
OK: 1 files checked, 2 errors
```

エラーなしの場合:

```
OK: 3 files checked, 0 errors
```

### 終了コード

- `0`: ERROR なし
- `1`: ERROR が 1 件以上

---

## check_orphans.py

### 目的

WikiLink グラフを解析して、孤立ページ（被リンクゼロ）と重複ページを検出する。

### 使用場面

- `wikicommit-merge` Skill：品質ゲートとして実行
- `wikicommit-status` Skill：知識ベース全体の健全性確認
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。research guidance が渡されなかった場合のみ。Issue #672）。`ORPHAN:` 行のみを使い、`DUPLICATE:` 行は使わない — 両ページとも実在するので欠けているものが無く、新しいソースでは解消しないため。**このとき終了コード 1（重複あり）は失敗ではない**: `wikicommit-merge` が同じ終了コードをブロッキングとして扱うのは重複がマージを止めるからであり、俯瞰とは無関係

### コマンド

```
python .wikicommit/scripts/check_orphans.py
```

### 定義

**orphan（孤立ページ）**: `.wikicommit/entity/` 内のどのページからも `[[Type/slug]]` 形式でリンクされていないページ。

`ORPHAN:` 行にはそのページの `sources`（`path`／`url`／`author`）を添える（Issue #570）。孤立の次に問う価値があるのは「どのソースが作ったか」であり、`wikicommit/saitama-city-wiki` の監査ではorphan 6 件すべてが「他に 1 ページも作っていないソース」由来である一方、対象全体の構造を述べる 2 ソース由来のページは全域で到達可能だった。ただし 1 リポジトリの観察であり、構造を述べるソースは定義上あらゆるページにリンクする側なので半ば同語反復でもある — **検証すべき仮説**であり、出自を印字することがそもそも検証を可能にする。`sources` を持たないページは `(no sources)` と出す。

クロス言語解決: `[[Type/slug]]` はスラッグのみを含む（lang を含まない）。スクリプトは `[[Type/slug]]` が `.wikicommit/entity/` 配下のいずれかの言語で `<Type>/<slug>.md` として存在するかをスラッグ単位で照合する。`ja/Person/yamada-taro.md` と `en/Person/yamada-taro.md` は同一スラッグとして扱い、いずれかにリンクがあれば両ページとも「リンクあり」と判定する。

以下は orphan の対象外とする：

- `<Type>/index.md`（タイプ別インデックスページ。命名規約: `.wikicommit/entity/<lang>/<Type>/index.md`）
- `status: removed` のページ

**重複ページ**: 同一 `lang` 内で `type` と `title`（NFKC 正規化・小文字化・連続空白の単一スペース化後）が完全一致するページが複数存在する。

### 出力フォーマット

```
ORPHAN: .wikicommit/entity/ja/Person/yamada-taro.md (sources: raw/paper-2024.pdf)
DUPLICATE: .wikicommit/entity/ja/Person/yamada-hanako.md <-> .wikicommit/entity/ja/Person/hanako-yamada.md (title: "山田花子")
SUMMARY: orphans=1, duplicates=1
```

エラーなしの場合:

```
SUMMARY: orphans=0, duplicates=0
```

### 終了コード

- `0`: 重複なし（orphan は終了コードに影響しない）
- `1`: 重複あり

---

## check_wanted_pages.py

### 目的

`.wikicommit/entity/` 全体を走査し、`[[Type/slug]]` で参照されているが、どの言語にも実体ページが存在しない slug（wanted page）を集計する。あわせて、実体が無いのは Type セグメントの取り違えが原因である（同じ slug が別 Type に実在する）ものを `TYPE_MISMATCH` として分離する（Issue #563）。`check_orphans.py` と対になる設計: orphan が「被リンクゼロのページ」を検出するのに対し、本スクリプトは「リンクはあるが実体がないページ」を検出する。Issue #340 で `check_wikilinks.py` の「参照先ページが存在しない」ケースが ERROR から WARNING に緩和されたことに伴い、その集計・可視化を担う。

### 使用場面

- `wikicommit-status` Skill：知識ベース全体の健全性確認
- `wikicommit-collect` Skill：Web候補探索のクエリ群のうち 1 パス分の検索語として（Issue #666。`WANTED:` 行のみを使い `TYPE_MISMATCH:` 行は使わない — 後者は実体が別 Type に在るので欠けているものが無く、必要なのは新しいソースではなくリンク 1 語の修正であるため）。取得失敗・`WANTED:` 0 件のときは黙って飛ばし、実行をブロックしない
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。Issue #672）。同じ `WANTED:` 行を、探索語ではなく「Wiki 自身が書きたいと表明した穴」として着眼点の根拠に読む。引数なし実行では上の探索語用途と同じ実行の中で両方が要るが、両者の間に `.wikicommit/entity/` へ書き込む手順は無いため、Step 3.5 が読んだ出力を Step 5 が再利用する（走査は 1 回でよい）

### コマンド

```
python .wikicommit/scripts/check_wanted_pages.py
```

引数なし。常に `.wikicommit/entity/` 配下の全 `.md` ファイル（`assets/` を除く）を対象とする。

### 処理フロー

1. `.wikicommit/entity/` 配下の全ページから `[[Type/slug]]` パターンを抽出し、`Type/slug` をキーに参照元ページのパスを集計する（同一ページから同じキーへの複数回のリンクは1件として数える）
2. 同時に、`.wikicommit/entity/<lang>/<Type>/<slug>.md` が存在する全ての `Type/slug` キーを、言語を問わず「実体あり」として集計する（`status: removed` のページも実体ありとして扱う — 削除済みページへのリンクは `check_wikilinks.py` の ERROR ケースの管轄であり、本スクリプトの対象外）
3. 参照されているが実体なしの `Type/slug` のうち、**同じ slug が別の Type に実在するもの**を `TYPE_MISMATCH` として分離して報告する（Issue #563）。判定は `check_wikilinks.py` と同じ `_wikilink.py` の共有関数（`build_slug_type_index()` / `other_types_for_slug()`）で行うため、除外規則（`index.md`・`status: removed` ページを候補にしない）・探索範囲（言語を問わない）も同一になる
4. 残りを wanted page として報告する

`TYPE_MISMATCH` を `WANTED` に混ぜない理由は、**両者が要求する行動が正反対だから**である。`WANTED:` は「これから書くべきページ」の一覧として `wikicommit-status` に集計されるが、Type 違いのものはそのとおりに作ると既存ページと内容の重複した 2 ページができ、しかも `check_orphans.py` の重複判定（同一 lang 内の title + type 一致）は `type` が異なるため検出しない。正しい対処は参照側のリンクの Type セグメントを直すことで、実体を作ることではない。

既知の限界（Issue #318 に明記済み）: WikiLink 構文が一度も使われていない地の文言及（太字のみ等）は対象外。

### 出力フォーマット

```
WANTED: DefinedTerm/hotpotqa (referenced by 3 pages: .wikicommit/entity/ja/DefinedTerm/react.md, ...)
page: DefinedTerm/hotpotqa
TYPE_MISMATCH: Organization/saitama-city has no page, but the same slug exists at AdministrativeArea/saitama-city.md (referenced by 1 pages: .wikicommit/entity/ja/GovernmentService/ward-office.md)
page: Organization/saitama-city
SUMMARY: wanted=1, type_mismatch=1
```

`page:` 行は `wikicommit-status` が集計に使用する（`WANTED:` / `TYPE_MISMATCH:` のどちらの直後にも現れるため、直前の行の種別で振り分ける）。

### 終了コード

- 常に `0`（警告のみ）

---

## check_expires.py

### 目的

`expires_at` フィールドが現在日付以前（`expires_at ≤ today`）のページを検出する。当日も期限切れとして扱うことで、担当者が当日中に対応できる。再審査が必要なページを定期的に発見するための警告用スクリプト。

### 使用場面

- `wikicommit-status` Skill（定期実行または手動実行。品質ゲートには含めない）

### コマンド

```
python .wikicommit/scripts/check_expires.py [--today=YYYY-MM-DD]
```

- `--today`: テスト用。省略時はシステム日付を使用

### 出力フォーマット

```
EXPIRED: .wikicommit/entity/ja/Person/yamada-taro.md (expires_at: 2026-06-01, today: 2026-06-23)
page: .wikicommit/entity/ja/Person/yamada-taro.md
SUMMARY: expired=1
```

`page:` 行は `wikicommit-status` が集計に使用する。

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）

---

## check_translation_status.py

> **命名の経緯（Issue #280）**: 当初 `check_translation_freshness.py` という名称だったが、「freshness（陳腐化）」は「存在するものが最新か」を問う語であり、`STALE`（翻訳はあるが原文更新に追従していない）・`MISSING_SOURCE`（翻訳はあるが原文が消えた）はこの定義に収まる。一方で本 Issue が追加した `UNTRANSLATED`（そもそも翻訳が1つも存在しない）は「存在するかどうか」という別種の問いであり、`freshness` という名前がこれを検出するのは実態と合わないため `check_translation_status.py` に改名した（分割ではなく改名を選んだ理由は、ページ走査ロジックの重複を避けるため）。

### 目的

翻訳ページの `source_commit` と親ページの現在 HEAD コミットを比較して陳腐化した翻訳を検出し、あわせて原文ページのうち `config.yml` の `translation.targets` に対する翻訳がまだ1つも存在しないものを検出する。

### 使用場面

- `wikicommit-status` Skill（定期実行または手動実行。品質ゲートには含めない）
- `wikicommit-translate` Skill（一括モードの対象件数算出。`UNTRANSLATED` の件数を `check_translation_status.py` の STALE 件数と合算してガード閾値と比較する）

### コマンド

```
python .wikicommit/scripts/check_translation_status.py
```

### 処理フロー

1. `translated_from` フィールドを持つページ（＝翻訳ページ）を `.wikicommit/entity/` から列挙
2. 各ページの `source_commit` を取得
3. `git log -1 --format=%H -- <translated_from>` で親ページの現在 HEAD を取得
4. `source_commit` と HEAD が一致しない → STALE として報告

`translated_from` で指定されたファイルが存在しない場合は `MISSING_SOURCE` として報告する。

1. `.wikicommit/config.yml` の `translation.primary_lang` と `translation.targets` を読む（`targets` が空配列の場合、この工程はスキップし `untranslated` は常に 0 になる）
2. `translated_from` を **持たない**（＝原文の）ページを `.wikicommit/entity/` から列挙する（`index.md` と `status: removed` のページは対象外。既存の `check_orphans.py` / `check_expires.py` と同じ除外方針）
3. 各原文ページについて、`targets` の各言語ごとに `.wikicommit/entity/<target>/<Type>/<slug>.md` が存在するか確認する（ページ自身の `lang` と一致する `target` はスキップ — 自分自身との比較を避けるため）
4. 存在しなければ `UNTRANSLATED` として報告する（1つの原文ページに対して複数の `target` が未翻訳の場合、`target` ごとに1行ずつ報告する）

### 出力フォーマット

```
STALE: .wikicommit/entity/en/Person/yamada-taro.md (source_commit: abc123, parent HEAD: def456)
page: .wikicommit/entity/en/Person/yamada-taro.md
MISSING_SOURCE: .wikicommit/entity/en/Person/yamada-jiro.md (translated_from: .wikicommit/entity/ja/Person/yamada-jiro.md)
page: .wikicommit/entity/en/Person/yamada-jiro.md
UNTRANSLATED: .wikicommit/entity/ja/Person/suzuki-ichiro.md (target: en)
page: .wikicommit/entity/ja/Person/suzuki-ichiro.md
SUMMARY: stale=1, missing_source=1, untranslated=1
```

`page:` 行は `wikicommit-status` が集計に使用する。

### 終了コード

- 常に `0`（警告のみ）

---

## check_derivation_freshness.py

### 目的

`wikicommit-synthesize`（Issue #283）が出力したページの `derived_from`（`{path, source_commit}` の配列）各エントリについて、出自ページの `source_commit` と現在 HEAD コミットを比較し、陳腐化した合成ページを検出する。`check_translation_status.py` の `STALE`/`MISSING_SOURCE` ロジック（単一の `translated_from`/`source_commit`）を配列用に切り出した新規スクリプト（既存スクリプトの改修ではなく新設。翻訳陳腐化スクリプトへの改修依存を作らないための設計判断）。

### 使用場面

- `wikicommit-status` Skill（定期実行または手動実行。品質ゲートには含めない）

### コマンド

```
python .wikicommit/scripts/check_derivation_freshness.py
```

### 処理フロー

1. `derived_from` フィールドを持つページ（＝合成ページ）を `.wikicommit/entity/` から列挙
2. 各ページの `derived_from` の各エントリについて:
   - `path` が実在するか確認する。存在しなければ `MISSING_SOURCE` として報告する
   - 実在する場合、`git log -1 --format=%H -- <path>` で現在 HEAD を取得し、エントリの `source_commit` と比較する。一致しなければ `STALE` として報告する
3. 1ページが複数エントリを持ち、複数エントリが STALE/MISSING_SOURCE の場合、該当エントリごとに1行ずつ出力する（同一ページに対する `page:` 行の重複出力は許容 — `check_expires.py` 等の既存スクリプト群の集計パターンに倣う）

### 出力フォーマット

```
STALE: .wikicommit/entity/ja/DefinedTerm/kilimanjaro-coffee.md (derived_from: .wikicommit/entity/ja/Person/yamada-taro.md, source_commit: abc123, current HEAD: def456)
page: .wikicommit/entity/ja/DefinedTerm/kilimanjaro-coffee.md
MISSING_SOURCE: .wikicommit/entity/ja/DefinedTerm/kilimanjaro-coffee.md (derived_from: .wikicommit/entity/ja/Person/removed-person.md)
page: .wikicommit/entity/ja/DefinedTerm/kilimanjaro-coffee.md
SUMMARY: stale=1, missing_source=1
```

`page:` 行は `wikicommit-status` が集計に使用する。

### 終了コード

- 常に `0`（警告のみ）

---

## check_ingest_freshness.py

### 目的

`.wikicommit/source/` 管理ファイルの `source.hash` と実ファイルの現在の SHA-256 を比較し、ソースが変更されたことを検出する。

### 使用場面

- `wikicommit-status` Skill（定期実行または手動実行。品質ゲートには含めない）

### コマンド

```
python .wikicommit/scripts/check_ingest_freshness.py [<ingest-file>...]
```

- 引数なし: `.wikicommit/source/` 配下の全管理ファイルを対象
- 引数あり: 指定した管理ファイルのみ

### 処理フロー

1. `source.type == path` の管理ファイルを対象（`url` / `wikicommit` はスキップ。URL の鮮度検出は本スクリプトのスコープ外であり、`wikicommit-generate` 再実行時にユーザーが手動で URL を再フェッチして hash を更新することが唯一の検知手段）
2. `source.path` のファイルで SHA-256 を計算（`sha256sum` コマンドまたは `hashlib`）
3. `source.hash`（`sha256:` 除いた部分）と比較
4. 不一致 → OUTDATED として報告し、管理ファイルの `status` を `outdated` に書き換える

> **⚠ サイドエフェクトあり（読み取り専用ではない）**: このスクリプトはローカルの管理ファイルを書き換える。`/wikicommit-status` から呼ばれた場合も同様にファイルが変更され `git status` に現れる。変更を main へ反映するには `/wikicommit-merge` を実行すること。意図しない変更を避けたい場合は実行前に `git stash` で退避する。

### 出力フォーマット

```
OUTDATED: .wikicommit/source/path/raw/paper-2024.pdf.md (source: raw/paper-2024.pdf)
page: .wikicommit/source/path/raw/paper-2024.pdf.md
SUMMARY: outdated=1, ok=3
```

`page:` 行は `wikicommit-status` が集計に使用する。

### 終了コード

- 常に `0`（警告のみ）

---

## check_distribution_freshness.py

### 目的

インストール済みの配布物が、`wikicommit-init` Skill が現在同梱しているテンプレートと一致しているかを報告する（Issue #712）。命名は `check_ingest_freshness.py` / `check_derivation_freshness.py` と同じ「記録されたものが今も最新か」の系譜だが、**副作用を持たない**（`check_ingest_freshness.py` と異なり管理ファイルを書き換えない）。

wiki リポジトリの中身は 3 種類に分かれ、性質の違う更新パターンに対応する。

| 中身 | 例 | 更新のされ方 |
|---|---|---|
| ユーザーが書いたもの | `entity/`・`config.yml`・`schema/` | 触らない（人間が判断する） |
| WikiCommit 自身の配布ペイロード | `.wikicommit/scripts/`・`quartz-plugins/`・2 つの workflow・`*.cjs` | 再 init で更新される |
| 別経路で生成されるもの | `quartz/`・`package-lock.json` | 対象外 |

Issue #712 以前は 2 番目が 1 番目と同じ扱いだったため、1 つ前の版で init したリポジトリは古い workflow・古いプラグイン `dist/`・古いビルドスクリプトを黙って使い続け、それを知る手段は clone して手で突き合わせることしか無かった（パイロット 3 件が実際に同一の旧版を抱えていた）。init 側は Issue #712 で更新されるようになり、本スクリプトは**そのリポジトリが更新を要するかを見る側**を担う。

**分類表は持たない**。どのパスがどの扱いかは `.claude/skills/wikicommit-init/scripts/_root_outputs.py` の `update` 列が唯一の情報源であり、`init.py` のコピーと `print_next_steps.py` の `git add` 案内も同じ列から導かれる。ここに 2 つ目のリストを持つことは、その列が消したドリフトを作り直すことになる（Issue #642 と同じ理由）。

### 使用場面

- `wikicommit-status` Skill：Step 11（Step 4 と同じく、ページ単位の集計ではなくインストールの状態を見るチェック）

### コマンド

```
python .wikicommit/scripts/check_distribution_freshness.py [--variant <none|quartz_only|quartz_pages>] [--repo-root <path>]
```

`--variant` 省略時は自動判定する（`quartz.config.yaml` があれば quartz、加えて `.github/workflows/deploy.yml` があれば quartz_pages）。判定に記録された設定を使わないのは、それを記録している場所が無いためで、代わりに各フラグが実際に足すファイルそのものを見る。

### 比較の仕方（`update` 列ごと）

| `update` | 比較 | 報告 |
|---|---|---|
| `overwrite` | バイト一致（ファイル／ツリー） | `OUTDATED:`・`MISSING:`・`ORPHAN:` |
| `review` | 下表の `compare` に従う | `OUTDATED:`・`MISSING:` |
| `skip` | 比較しない | なし |

**`review` をバイト差分で報告してはいけない**。`review` に分類したファイルのうち 5 つは、**どのリポジトリでも永久にバイト一致しない**:

| ファイル | 一致しない理由 |
|---|---|
| `.wikicommit/config.yml` | テンプレートが `{VERSION}`・`{TARGETS}`・`{PRIMARY_LANG}`・`{THEME}` を持ち init が置換する |
| `quartz.config.yaml` | 同上（`{PAGE_TITLE}`・`{PAGE_TITLE_SUFFIX}`・`{REPO_URL}`） |
| `.wikicommit/source-policy.md`・`.wikicommit/entity-policy.md` | 本文がコメントアウトした記入例であり「自分で書いたら消せ」と本文自身が指示している |
| `.gitignore` | init が `--quartz` 時に Quartz セクションを追記する（**Issue #712 の実装中に実測で判明した。Issue 本文の分類表はこれをバイト比較側に置いていた**） |

常に出ている警告は読まれなくなる — Issue #562 が低情報密度ガードを blocking から降格した理由がまさにこれであり、差分検出全体が無視されるようになればこの仕組みが機能しない。したがって `review` は**加算的なシグナルでのみ報告する**: テンプレートにあってローカルに無いもの。値を変えたこと・散文を書き換えたことは報告しない。

`compare` の値（`_root_outputs.py` の `COMPARISONS`）:

| `compare` | 何を見るか | 対象 |
|---|---|---|
| `bytes` | バイト一致 | 上記 5 つ以外の全て |
| `yaml_keys` | テンプレートにあってローカルに無い YAML キー | `config.yml`・`quartz.config.yaml` |
| `frontmatter_keys` | 同、frontmatter の `wikicommit:` 直下 | ポリシーファイル 2 つ |
| `lines` | 同、空行とコメントを除いた行 | `.gitignore` |
| `none` | 比較しない | `update: skip` のみ |

> **キーの比較は再帰的に行う（ドット区切りのパス）**。Issue 本文は「トップレベルキー」としていたが、同じ Issue が挙げている実例 `pageTitleSuffix`（Issue #679）は `configuration:` の下にある。`quartz.config.yaml` のトップレベルキーは `configuration`/`layout`/`plugins` の 3 つで今後増えないため、トップレベルのみの比較では**この機能が意図した用途に対して恒久的に何も報告しない**。
>
> **テンプレート側の `{NAME}` プレースホルダーは比較前に無害化する**。YAML はクォートされていない `{THEME}` をフロー マッピングとして読むため、`theme: {THEME}` は「`theme.THEME` という入れ子キー」に見え、実際の値を持つ config.yml には当然そのキーが無い。無害化しないと、**init 直後のリポジトリが自分の `config.yml` と `quartz.config.yaml` を永久に `OUTDATED` として報告する**（実装中に clean init に対して実行して発見した）。`options: {}` のような本物の空マッピングは正規表現に一致しないためそのまま解釈される。**置換先は空文字列ではなく素のスカラー**にする — プレースホルダーは常に裸で書かれているとは限らず、`config.yml` の 1 行目は `wikicommit_version: "{VERSION}"` とクォートの内側にあるため、`""` で置換すると引用符が 4 つ並んで**テンプレート全体が YAML として読めなくなる**。そうなるとテンプレート側のキー集合が空になり、`テンプレート − ローカル` も空になるので、**`config.yml` は上流で増えたキーを永久に報告しない** — 比較が止まっているのに正常な結果に見える。なお、テンプレート側のパースに失敗した場合は `WARNING:` を 1 行出す（空のキー集合は「上流で何も増えていない」と見分けがつかないため）。

### ORPHAN は `overwrite` のツリーにのみ報告する

`copy_tree` は削除を行わないため、上流でリネームされたスクリプトは旧名のまま残る（Issue #583）。これを `ORPHAN:` として報告するが、**対象は `update: overwrite` のツリーに限る** — `.wikicommit/schema/` は `review` であり、テンプレートに無いファイルはユーザーが書いたカスタム型か Pass 2b が追加した型であって孤児ではない。ここを区別しないと `ORPHAN:` 行が正反対の 2 つを意味することになる。

削除は行わない（本 Issue のスコープ外。誤検出時の被害が非対称に大きいため、削除は後続の update フローが人間の確認を取って行う）。

### 劣化の仕方

| 状況 | 挙動 |
|---|---|
| `wikicommit-init` が未インストール | `WARNING:` を 1 行出し `SUMMARY:` 全 0 で終了（`check_property_wikilink_reinforcement.py` が語彙を引けないときと同じ非ブロッキングな劣化）。`.wikicommit/scripts/` は wiki リポジトリにコミットされるが `.claude/skills/` は別途インストールするものなので、無いことは十分あり得る |
| `wikicommit_version` が無い | `synced=unknown` と表示する。版は読者向けの情報であり比較を左右しないため、それ以外は通常どおり動く（Issue #577 より前に init されたリポジトリが該当） |
| `update` が未知の値 | `review` として扱う。`npx skills add` は `.claude/skills/` を更新するが `.wikicommit/scripts/` は次の init まで古いままなので、**古いスクリプトが新しいリストを読む**組み合わせが起こりうる。表示するラベルも `review` に正規化する — 適用していない扱いを名乗らせないため |

### 出力フォーマット

```
VERSION: synced=0.2.0, installed=0.3.0
OUTDATED: quartz-plugins (overwrite) — 6 file(s) differ from the template
OUTDATED: .wikicommit/source-policy.md (review) — the template has wikicommit: key(s) this file lacks: index_only
MISSING: .wikicommit/entity-policy.md (review) — not present locally
ORPHAN: .wikicommit/scripts/check_old_name.py — no counterpart in the template
SUMMARY: outdated=2, missing=1, orphan=1
```

### 既知の限界

`.gitignore` の比較対象は `templates/.gitignore` のみで、`--quartz` 時に追記される `templates/gitignore-quartz.txt` は見ない。後者に追加されたパターンは報告されない。

`package.json` は `review` かつバイト比較のため（Issue #712 の分類表どおり）、**init 前から自前の `package.json` を持っていたリポジトリでは毎回 `OUTDATED` が出続ける** — `init.py` はその場合コピーをスキップするので、テンプレートと一致することが構造的にありえない。上記 5 ファイルと同じ「常時点灯」の形だが、扱いを変えていない理由は 2 つある: (1) 大半のリポジトリはテンプレートをそのまま受け取るため一致し、点灯が普遍的ではない（`.gitignore` は `--quartz` の全リポジトリで必ず点灯する点が決定的に異なる）、(2) この点灯は実際に行動を促す — Issue #556 は新しい `*.cjs` が `package.json` の `postinstall` から呼ばれず全 Pages ビルドが失敗した事例であり、「テンプレートの `package.json` が変わった」は取り込むべきものがあるという正しいシグナルである。加算的比較へ移す（テンプレートに増えた `scripts` エントリだけを見る）ことは可能だが、実測の裏付けが無いまま Issue の分類から離れるため見送った。

### 終了コード

- 常に `0`（報告のみ、ブロッキングしない）

---

## search_index.py

### 目的

`.wikicommit/entity/` を SQLite FTS5（`trigram` トークナイザ）でインデックス化し、全文検索を提供する。単語境界のない CJK（日本語・中国語）も分かち書きなしで検索できる。`wikicommit-search`・`wikicommit-ask` の両 Skill から共有される（`docs/DesignDoc-skills.md` §11.5）。

### 使用場面

- `wikicommit-search` Skill：キーワード検索
- `wikicommit-ask` Skill：`wikicommit-search` 経由で内部利用
- `wikicommit-synthesize` / `wikicommit-quiz` Skill：関連ページの収集（いずれも `--expand` 経由。Issue #581）

### コマンド

```
python .wikicommit/scripts/search_index.py build
python .wikicommit/scripts/search_index.py query "<query>" [--lang <lang>] [--limit N]
python .wikicommit/scripts/search_index.py query --expand "<語>|<語>" --expand "<語>" [--lang <lang>] [--limit N]
```

`query` は位置引数（空白区切り・暗黙 AND）か `--expand`（複数指定可）のいずれか一方を取る。両方指定・どちらも未指定はいずれもエラー（終了コード 1）— 同じ語に対して 2 つの異なる意味論を持つため、黙って統合すると呼び出し側が指定していない検索を行うことになる。

### `build` サブコマンド

1. `.wikicommit/entity/**/*.md` を走査する（`index.md` と `status: removed` のページは対象外）
2. 各ページから `title`・`lang`・`type`・`tags`・`review_status`・本文（frontmatter を除いた Markdown 全文）を抽出する。frontmatter が YAML として解析できない、またはマッピング型でない場合はそのページ全体をインデックス対象から除外する（`status: removed` かどうか判定できないページを誤って検索可能にしないための安全側の挙動）
3. `.wikicommit/.cache/search_index.sqlite3` に FTS5 仮想テーブル（`tokenize="trigram"`）を作成し投入する。`path`・`lang`・`type`・`review_status` は `UNINDEXED`（全文検索対象外・フィルタ／表示用）
4. 実行のたびにテーブルを `DROP` してから全件再構築する（差分更新なし）
5. `.wikicommit/.cache/` が存在しない場合は作成する。Git 管理対象外（`.gitignore` に `.wikicommit/.cache/` を追加済み）
6. SQLite が `trigram` トークナイザ（SQLite 3.34+、3.38+ 推奨）に対応しない場合、エラーメッセージを出力し終了コード 1 で終了する（インデックスファイルは残さない）

### `query` サブコマンド

1. `.wikicommit/.cache/search_index.sqlite3` が存在しない場合、先に `build` を自動実行する
2. `MATCH` 演算子で全文検索する。MATCH 式の組み立ては指定形式で分かれる:
   - **位置引数**: 空白区切りの各語を個別にフレーズクエリとしてクォートし、暗黙の AND で連結する（ユーザー入力をそのまま FTS5 クエリ構文として解釈すると `-`・`"` 等でクエリ構文エラーになりうるため語ごとにクォートする。クエリ全体を単一フレーズにすると隣接した語順の完全一致でしか検索できなくなるため、キーワード検索として機能するよう語ごとに分割する）
   - **`--expand`**（Issue #581）: 各 `--expand` の値を `|` で分割して 1 グループとし（各語は前後の空白を除去し、内部の連続空白も 1 個の半角空白に潰す — 複数語の語は 1 つの隣接フレーズとして扱う一方、語の中に改行が残ると `SUMMARY:` 行が複数行に割れて、行単位で `hits=` を読む呼び出し側が値を取り落とすため）、**グループ内は OR・グループ間は AND** の式を組み立てる（`("児童手当" OR "子ども手当") AND ("申請手続き")`）。各語のクォート・`"` の `""` エスケープは位置引数と同一のルールで行う。単一語のグループも含め**すべてのグループを括弧で囲み、明示的な `AND` で連結する** — FTS5 は括弧で囲んだ式と裸のフレーズの並置（`("a" OR "b") "c"`）も、括弧同士の並置も構文エラーとするため、グループが 1 つでも存在する時点で明示的な演算子が必須になる。空白区切りの語を空文字列に潰す・分割記号 `|` 自体を語に含める、といったケースは扱わない（前者は落とし、後者は現実的な検索語に現れないため専用のエスケープ構文を設けない）
   - `trigram` トークナイザは3文字未満の連続文字列からはトークンを作れないため、3文字未満の語はどのページの本文とも絶対に一致しない（クエリ構文エラーにはならず、常に無条件で不一致になる）。この判定は Skill 側（LLM）に委ねず本スクリプトが行う（`docs/DesignDoc-skills.md` §11.5 のスクリプト委譲パターンに従う）。警告の文言は指定形式と、**グループ内に 3 文字以上の語が残るかどうか**で 3 通りに分かれる:

     | 状況 | 出力 | 挙動 |
     |---|---|---|
     | 位置引数の 3 文字未満の語 | `WARNING: query term "<term>" has <N> character(s); trigram search requires at least 3 and this term cannot match anything` | 式から落とさない（FTS5 の暗黙 AND がその語の寄与を無視するため、結果としてヒットは残る） |
     | `--expand` グループ内に 3 文字以上の語が 1 つ以上残る | `WARNING: expand term "<term>" ... so it was dropped — its group still matches via: <残った語>` | その語のみを落とす。グループは残った語で機能する（短い原語を長い同義語で救済できるのは拡張の副次的な利点であり、死んだクエリと同じ文言で警告すると誤解を招く） |
     | `--expand` グループ全体が 3 文字未満の語のみ | `WARNING: expand group "<a>\|<b>" has no term of at least 3 character(s); ... so this group was dropped and no longer narrows the search` | **グループごと落とす**。グループは AND で連結されるため、何にも一致しないオペランドを残すとクエリ全体が 0 件になる。落とす方が位置引数の挙動（暗黙 AND が短い語の寄与を無視する）と整合する一方、その概念が検索を絞らなくなるため、文言でその旨を明示する |
     | `--expand` 指定はあるが**残ったグループが 1 つもない**（全グループが空・または全語が 3 文字未満） | `WARNING: no usable --expand term remains; the search has no terms at all and cannot match anything (this is not a wiki-coverage result)` | MATCH 式が空フレーズ `""` になり **`hits` は必ず 0** になる。上のグループ単位の警告だけでは「検索が広がった」としか読めず実際と正反対になるため、グループ単位の警告に加えてこの行を出す（`--expand ""` のように 1 行も警告が出ないケースも同時に塞ぐ）。呼び出し側は「Wiki に無い」ではなく「検索が成立していない」と扱う |

     警告はいずれも `hits` の値に関係なく検索実行前に出力し、終了コードにも影響しない
3. `bm25()` に列重みベクトル `(path=0.0, title=10.0, lang=0.0, type=0.0, tags=0.0, review_status=0.0, body=1.0)` を渡し、`title` ヒットを `body` ヒットより優先してランク付けする
4. `--lang` 指定時はその言語のページのみに絞り込む
5. `--limit`（デフォルト 10）件まで、`path`・`title`・`type`・`lang`・`review_status`・本文スニペット（`snippet()`、trigram トークン換算で前後 32 文字程度）を出力する

### 出力フォーマット（`query`）

```
MATCH: .wikicommit/entity/ja/Person/yamada-taro.md | title=山田太郎 | type=schema:Person | lang=ja | review_status=pending
  ...CompanyA のシニア**エンジニア**。機械学習システムの...
SUMMARY: query="エンジニア", hits=3
```

`SUMMARY:` の `query=` は指定形式で内容が変わる。位置引数では従来どおり生のクエリをダブルクォートで囲んで出力する。`--expand` では**実際に実行した MATCH 式**をそのまま出力する（引用符を自前で含むため外側のクォートは付けない。落とされた語は式に現れない）:

```
SUMMARY: query=("子ども手当" OR "児童手当") AND ("申請手続き"), hits=1
```

引数そのものではなく式を出すのは、語がグループへ組み直され短い語が落とされた後の形こそが実際に走った検索であり、`wikicommit-search` のように「どの語がこのヒットを生んだか」を人間に見せる呼び出し側が必要とするのはそちらだからである。

### 終了コード

- `0`: 成功（ヒット 0 件でも成功）
- `1`: SQLite が trigram トークナイザ非対応、`.wikicommit/entity/` が存在しない、または `query` の検索語指定が矛盾している（位置引数と `--expand` の同時指定・どちらも未指定）。`query` 実行時に SQLite ライブラリレベルのエラー（DB ロック競合・キャッシュファイル破損等）が発生した場合も同様に `1`

---

## check_schema_coverage.py

### 目的

`.wikicommit/entity/**/*.md` を走査し、`type:` フロントマターの値が `.wikicommit/schema/` に専用のスキーマファイルを持たない（`default.md` へのフォールバックのみで表現されている）ページを検出する。`wikicommit-generate` Pass 2 のコンテキスト注入（型文字列の再利用誘導）と、`wikicommit-schema-propose`（Issue #285）の検出源の両方から使われる。

### 使用場面

- `wikicommit-generate` Skill：Pass 2 のプロンプトに「未スキーマ化のまま使われている type 文字列一覧」を含めるため
- `wikicommit-schema-propose` Skill：型ファイル追加提案の検出源として
- `wikicommit-status` Skill：Step 6（定期ヘルスチェック。Issue #575）

> **`wikicommit-status` から呼ぶ理由（Issue #575）**: `default.md` へのフォールバック自体は §5.4 が定める正規の挙動だが、フォールバックするとその型の `granularity`・`properties:` 候補キー・本文テンプレートが丸ごと適用されなくなる。にもかかわらず、生成されたページは一見正常で `validate_frontmatter.py` の必須フィールド検証も通る（`default.md` の required だけが適用されるため）。
>
> 問題は、これが起きたことを**継続的に見せる経路が無かった**ことにある。`wikicommit-generate` はそのページを生成した実行の Completion Notice でしか報告せず（Issue #575 でこの報告自体を追加した）、`validate_frontmatter.py` の WARNING は `wikicommit-merge` が**変更ファイルにのみ**実行するため、スキーマファイルを後から移動・リネーム・削除した場合、そのコミット以降に変更されないページは二度と再検証されない。**壊れる契機（`.wikicommit/schema/` の編集）と検証の契機（ページの変更）が一致しない**ため、両者はすれ違い続ける。本スクリプトは全ページを毎回走査するので、「今この瞬間に何ページが影響下にあるか」を直接見せられる。
>
> `validate_frontmatter.py` の当該 WARNING は**現状維持**とする（ERROR に格上げしない）。専用ファイルを持たない型は正常系であり、ブロックすると Pass 2b〈Issue #315〉以前に生成されたページを持つ既存リポジトリが軒並みマージ不能になる。スキーマファイルの移動・削除を git 履歴から追う案も採らない — 本スクリプトが「結果として今どうなっているか」を直接見るのに対し経路を追う分だけ複雑で、しかも最初からファイルが無いケース（古い版で init したリポジトリ）を拾えない。

### コマンド

```
python .wikicommit/scripts/check_schema_coverage.py
```

引数なし。常に `.wikicommit/entity/` 配下の全 `.md` ファイル（`index.md` と `status: removed` のページを除く）を対象とする。

### 処理フロー

1. 対象ページごとに `type:` フロントマターを読む
2. `schema:` プレフィックスで始まらない値はこのスクリプトの対象外（`validate_frontmatter.py` の関心事）として無視する
3. `schema:` プレフィックスを除いた型名（例: `schema:Person` → `Person`、`schema:custom/Decision` → `custom/Decision`）に対応する `.wikicommit/schema/<型名>.md` が存在するか確認する。`default.md` へのフォールバックが効くかどうかは判定に使わない — `default.md` が存在していても、型固有のファイルがなければ「未カバー」として扱う（これが本スクリプトの検出対象そのものであるため）
4. 型文字列は完全一致でのみ集計する。正規化・fuzzy matching は行わない（決定論的に保つための意図的な単純化。同じ概念が複数の型文字列に分かれたまま残りうるという既知の限界が伴う。Issue #285）

スキーマファイルの探索は `type:` からのパス導出のみで、ディレクトリを型名で走査する処理は存在しない。したがって `.wikicommit/schema/standard/Person.md` のようにサブディレクトリへ移動されたファイルは「無い」ものとして `UNCOVERED:` に現れる（`docs/DesignDoc-data.md` §5.1）。この場合 `wikicommit-schema-propose` を実行すると `.wikicommit/schema/Person.md` を新規作成するため**同じ型の定義ファイルが2つ並ぶ**（実際に効くのは新規作成された `.wikicommit/schema/Person.md` のみで、サブディレクトリへ移動された方は引き続き読まれない）。正しい対処は移動したファイルを元の位置へ戻すことで、`wikicommit-status` の Step 6 はこの注意を添えて報告する。

### 出力フォーマット

```
UNCOVERED: schema:Game (12 pages, e.g. .wikicommit/entity/ja/Game/tag.md)
UNCOVERED: schema:custom/Recipe (3 pages, e.g. .wikicommit/entity/ja/custom/Recipe/curry.md)
SUMMARY: unschemaed_types=2
```

エラーなしの場合:

```
SUMMARY: unschemaed_types=0
```

### 終了コード

- 常に `0`（情報提供のみ、ブロッキングしない）

---

## check_schema_org_type.py

### 目的

Schema.org の公式機械可読語彙ダンプ（`https://schema.org/version/latest/schemaorg-current-https.jsonld`）に対して、型・プロパティが実在するかを検証する。`wikicommit-generate` Pass 2b（Issue #315。その場での型提案・追加）と `wikicommit-schema-propose`（Issue #285。事後検出）が生成する型ファイル提案の、決定論的な裏付けとして使う。検証できるのは「型・プロパティが実在するか」という**存在の正しさ**のみで、「このWikiの内容に意味的にふさわしいか」という**適合性の判断**は LLM と人間レビューに委ねる。

### 使用場面

- `wikicommit-generate` Skill：Pass 2b のプロンプトに Schema.org 型名の一覧をプリロードし（`--list-type-names`）、絞り込んだ候補の説明文だけを引くため（`--describe`）。Pass 2b の型・プロパティ実在検証にも使う（`--type`/`--property`）。Pass 3 が `properties:` の値を WikiLink 化すべきか判断する材料にも使う（`--show-range`。Issue #496）。Pass 2b が新規型の候補プロパティを選ぶ際、型が持ちうるプロパティ一覧を閲覧する材料にも使う（`--list-properties`。Issue #497）
- `wikicommit-schema-propose` Skill：型・プロパティの実在検証（`--type`/`--property`）。Step 4（標準型パス）が候補プロパティを選ぶ際の閲覧にも使う（`--list-properties`）

語彙の読み込み・キャッシュ（`.wikicommit/schemaorg-vocab.json`）・`domainIncludes`/`rangeIncludes`/`rdfs:subClassOf` 継承チェーン判定のロジックは `.wikicommit/scripts/_schemaorg_vocab.py`（`_frontmatter.py`/`_wikilink.py` と同じ、複数スクリプトが import する共有モジュール）に切り出されている（Issue #495、`rangeIncludes`/DataType 判定は Issue #496 で追加）。`validate_frontmatter.py` の `properties:` フィールド検証（同スクリプトの節を参照）もこのモジュールを共有し、CLI としての本スクリプトとロジックが乖離しないようにしている。本スクリプト自身は CLI 引数のパース・出力整形のみを担う薄いラッパー。

### コマンド

```
python .wikicommit/scripts/check_schema_org_type.py --type <TypeName> [--property <PropertyName>]... [--show-range]
python .wikicommit/scripts/check_schema_org_type.py --type <TypeName> --list-properties
python .wikicommit/scripts/check_schema_org_type.py --list-type-names
python .wikicommit/scripts/check_schema_org_type.py --describe <TypeName>...
python .wikicommit/scripts/check_schema_org_type.py --list-installed-hierarchy
```

`--type` / `--list-type-names` / `--describe` / `--list-installed-hierarchy` のいずれか 1 つを指定する。すべて省略した場合はエラー（`--list-properties` 単独指定時は「`--list-properties` には `--type` の指定が必要です」という専用のエラーメッセージになる）。優先順位: `--list-type-names` が指定されていれば他の全フラグを無視してこのモード。次に `--describe`、次に `--list-installed-hierarchy` が指定されていれば同様に他の全フラグを無視してこのモード（Issue #798・#565）。次に `--type` + `--list-properties` が指定されていればこのモード（`--property`/`--show-range` は無視）。それ以外は `--type`（+ 任意で `--property`/`--show-range`）の既存の検証モード。

### 保存先（Git管理下・Issue #319）

`.wikicommit/schemaorg-vocab.json` に遅延生成する（`search_index.py` の「初回クエリ時に build を自動実行する」パターンと同じ）。取得元 URL は上記の公式配布 URL に固定。TTL・自動更新は設けない — Schema.org 語彙の改訂頻度は低く、古い内容の実害は「新しい型が使えない」程度に留まるため。

`search_index.sqlite3` 等の `.wikicommit/.cache/`（`.gitignore` 除外）配下のファイルとは異なり、本ファイルは `.wikicommit/.cache/` の外（`.wikicommit/schemaorg-vocab.json`）に置き、Git 管理対象とする。理由: `search_index.sqlite3` は実行のたびに全件再構築される真の使い捨てキャッシュ（消しても実害ゼロ）だが、本ファイルはネットワーク取得コストのある準静的な参照データであり、削除すると次回実行時に毎回ネットワーク取得が再発生する。`.cache/` という名前が与える「気軽に消してよい」という印象と実際の性質が食い違っていたため、`llm-agent-research-wiki` パイロットでの指摘（`Issues/registered/p3-117-schemaorg-vocab-cache-placement.md`（非公開の開発リポジトリ側の記録））を受けてGit管理下に切り出した。副次的な効果として、クローン直後から使え、複数人・複数マシン間でのネットワーク取得の重複コストも避けられる。

再生成したい場合はユーザーが `.wikicommit/schemaorg-vocab.json` を手動削除して再実行する。Git管理下にあるため、再生成後の差分は他の追跡ファイルと同様に通常のコミット・PRレビューを経て反映される（`wikicommit-merge` が `.wikicommit/schemaorg-vocab.json` の新規作成を検出しコミットに含める。`.claude/skills/wikicommit-merge/SKILL.md` Step 2 参照）。`--type`/`--list-type-names`/`--describe`/`--show-range`/`--list-properties` のどの呼び出しもこの同じファイルを共有する。`rangeIncludes`/`is_datatype`（Issue #496 で追加されたキー）・property の `comment`（Issue #497 で追加されたキー）を含まない旧形式のキャッシュは手動削除不要 ── `_schemaorg_vocab.py` の `load_or_build_index()` が `_is_well_shaped_index()` でこの形状不一致を自動検出し、再取得・再構築する（各 `types` エントリに `is_datatype`、各 `properties` エントリに `range`/`comment` キーが揃っているかまで検証する。外側の `{"types": dict, "properties": dict}` の型だけでは、旧形式のキャッシュを誤って正常として受理してしまい、`--show-range` が黙って何も報告しなくなる、`--list-properties` の説明列が常に空になる、または `is_in_datatype_lineage()` がキー欠落を `is_datatype: false` と誤認して DataType 型をエンティティ型として誤分類する、という複数のサイレント劣化を招くため）。

### 処理フロー（`--type`/`--property`/`--show-range`）

1. キャッシュ（なければ語彙ダンプを取得して構築）から型一覧・プロパティ一覧（`schema:domainIncludes` によるプロパティ→型の対応、`schema:rangeIncludes` によるプロパティ→値の型の対応、`rdfs:subClassOf` による型の祖先チェーン、各型の `is_datatype` フラグ〈`@type` に `schema:DataType` を直接含むか〉）を読み込む
2. `--type` の型が語彙に実在するか確認する
3. `--property` ごとに、そのプロパティが語彙に実在し、かつ `--type`（またはその祖先型のいずれか）の `domainIncludes` に含まれるかを確認する。`--type` 自体が実在しない場合、プロパティの所属判定はできないためその `--property` もすべて ERROR とする
4. `--show-range` が指定されている場合、所属確認に成功した（`OK:` を出力した）`--property` ごとに、`RANGE:` 行を追加出力する。所属確認に失敗した `--property` には出力しない（報告する範囲がないため）。分類は3通り: `rangeIncludes` の候補全てが非 DataType（＝リンク可能なエンティティ型のみ）・候補全てが DataType（`is_datatype` を直接持つか、`rdfs:subClassOf` の祖先チェーンのいずれかが持つ場合。例: `URL` は直接タグを持たないが `subClassOf: Text` 経由で DataType）・両方混在。`rangeIncludes` 自体が宣言されていないプロパティは何も出力しない。この判定はブロッキングではない（`errors`/終了コードに一切影響しない、情報提供のみの行）

### 処理フロー（`--type` + `--list-properties`）

新しい型スキーマファイルを書く際に「この型が Schema.org 上でどんな property を持ちうるか」を一覧するための、オンデマンド表示モード（Issue #497）。933型分の全 property 一覧を静的ファイルとして事前生成・保存する方式（`.wikicommit/schema/template/` 等）は不採用とした — `.wikicommit/schemaorg-vocab.json`（Issue #319）という単一の情報源と二重管理になるうえ、全property入りのテンプレートはスキーマ層が本来持つ「絞り込みによる認知負荷低減」という目的（Issue #495 が型レベルの `recommended` を廃止した理由と同根）と衝突するため。

1. `--type` の型が語彙に実在するか確認する。実在しなければ ERROR を1行出力して終了する（`--property` 検証モードと異なり `checked`/`errors` のカウントは行わない — このモードは検証ではなく一覧表示のため）
2. 実在すれば、語彙全体の property を走査し、その `schema:domainIncludes` が `--type`（またはその祖先型のいずれか。`rdfs:subClassOf` チェーンを `--property` の所属判定と同じロジックで走査）と交差するものを全て集める
3. 集めた property をアルファベット順に並べ、1行ずつ「property名・宣言型（自身か祖先か。`domainIncludes` が実際にどの祖先を指しているか。複数祖先にまたがる場合はカンマ区切りで全て列挙）・`rangeIncludes` のエンティティ型候補（DataType除外後。候補なしは `-`）・一行説明（`rdfs:comment`）」をタブ区切りで出力する

#### 処理フロー（`--list-installed-hierarchy`。Issue #565）

`.wikicommit/schema/` にインストール済みの Schema.org 標準型（`type:` が `schema:` で始まり `custom/` でないもの。`default.md` は `type:` を持たないため自然に除外される）を走査し、各型について**インストール済みの祖先型のみ**を近い順に並べてタブ区切りで出力する。祖先が無い型も `-` として出力するため、出力はインストール済み型の名簿を兼ねる。

Pass 2c は型候補一覧と各型の `granularity` を受け取るが、そこには `Park` が `Place` の一種であるという情報が無い。祖先型は常に当てはまる（公園を `Place` として書くのは誤りではなく粒度が粗いだけ）ため、広く馴染みのある型が既定で選ばれる。この関係は語彙から決定論的に導けるので、モデルの記憶に委ねずここで計算する。

```
Museum<TAB>Place
Park<TAB>Place
Person<TAB>-
Place<TAB>-
SUMMARY: installed_types=4
```

**間に挟まる非インストール型は名前を出さない**（`Park` が `CivicStructure` 経由で `Place` の子孫であっても、`CivicStructure.md` が無ければ `Place` だけを出す）。Pass 2c が選べるのはインストール済みの型だけであり、選べない型を提示しても迷わせるだけであるため。

### 処理フロー（`--list-type-names` / `--describe`）— 型の想起は 2 段階（Issue #798）

キャッシュから型名だけをアルファベット順に出力する（`--list-type-names`。**説明文を付けない**）。続けて、そこから絞り込んだ候補について `--describe <TypeName>...` が型名 + 一行説明（`rdfs:comment`）をタブ区切りで出力する。

**分けた理由は、この一覧が果たしているのが想起であって存在保証ではないため**である。型が実在するかは候補が承認された後の `--type <Type> --property ...` が決定論的に確かめており、一覧の役目は「モデルが思いつかない型を候補に上げさせる」ことに尽きる。想起には、誰も検討していない 928 型の説明文は要らない。

| | 実測 |
|---|---|
| 旧 `--list-types`（全 933 型の名前 + 説明） | 147,421 B（約 37K トークン） |
| `--list-type-names`（名前のみ） | 13,441 B（約 3.4K トークン） |
| `--describe` 3 件 | 170 B |
| **合計** | **約 14 KB（−90%）** |

これは `/wikicommit-generate` の固定オーバーヘッドをソース件数によらず約 84K → 約 51K トークンに下げる（`README.md` の Requirements → Context window が正本）。

**`--list-types` は残さず削除した**（Issue #798 の検討事項 5）。3 Skill が 2 段階へ移った時点で呼び出し元が 0 になり、「どの Skill も使っていないが配布はされているモード」を仕様に残すことは、Issue #553 が確立した「消費者のいない受け皿を配らない」に反する。しかも残せば、プリロードすべきでないと決めたばかりの高価な経路を仕様書が宣伝し続けることになる。同じ需要は `--describe` がオンデマンドで満たす。

**`--describe` は語彙に無い名前を ERROR にする**（同 検討事項 6）。黙って落とすと、段階 1 が 933 件の実在する名前を渡している以上「戻ってこなかった名前＝モデルの創作」であることが承認ステップまで伝わらない。1 件でも該当すれば終了コード 1 を返すが、実在した分は通常どおり出力する（呼び出し側が有効な候補だけで進めるため）。

**この削減は測れない**（同 検討事項 1）。説明文を落として型提案の recall が落ちたかを判定する eval 基盤はこのリポジトリに無く、Issue #669 が `chain_of_thought` を実装せず削除したときと同じ状況にある（削減は確実・品質劣化は判定不能）。壊れ方が軽いこと（型提案は元々ゼロ件が通常の結果で、`wikicommit-schema-propose` と `check_schema_coverage.py` が事後の安全網として残る）を根拠に採ったうえで、**次のパイロットの観察項目**として「`provenance` が `init-theme` / `collect` / `generate-interactive` / `generate-auto` の型が実際に生まれるか」を記録する — それが recall を落としていないことの唯一の間接的な証拠になる。

### 出力フォーマット（`--type`/`--property`）

```
OK: schema:Game exists in the Schema.org vocabulary
OK: typicalAgeRange belongs to schema:Game (or one of its ancestor types)
ERROR: jurisdiction belongs to neither schema:Game nor any of its ancestor types
SUMMARY: type=schema:Game, checked=3, errors=1
```

### 出力フォーマット（`--type`/`--property` + `--show-range`）

```
OK: schema:Person exists in the Schema.org vocabulary
OK: affiliation belongs to schema:Person (or one of its ancestor types)
RANGE: affiliation references entity types only (candidates: Organization). Write the value as [[Type/slug]] when it names an entity that exists (or should exist) as its own page
OK: description belongs to schema:Person (or one of its ancestor types)
RANGE: description mixes entity types and data types (entity candidates: TextObject / data type candidates: Text). Write the value as [[Type/slug]] only when it names an entity that exists (or should exist) as its own page
SUMMARY: type=schema:Person, checked=2, errors=0
```

### 出力フォーマット（`--type` + `--list-properties`）

```
affiliation<TAB>Person<TAB>Organization<TAB>An organization that this person is affiliated with...
alumniOf<TAB>Person<TAB>EducationalOrganization, Organization<TAB>An organization that the person is an alumni of.
birthDate<TAB>Person<TAB>-<TAB>Date of birth.
birthPlace<TAB>Person<TAB>Place<TAB>The place where the person was born.
description<TAB>Thing<TAB>TextObject<TAB>A description of the item.
name<TAB>Thing<TAB>-<TAB>The name of the item.
SUMMARY: type=schema:Person, properties=81
```

### 出力フォーマット（`--list-type-names`）

```
CreativeWork
Game
Thing
SUMMARY: types=933
```

### 出力フォーマット（`--describe`）

```
Park<TAB>A park.
Museum<TAB>A museum.
ERROR: schema:NotARealType does not exist in the Schema.org vocabulary
SUMMARY: described=2, errors=1
```

（`<TAB>` はタブ文字 1 個を表す表記。実際の出力はタブ区切り。）

### 終了コード

- `0`: `--type` の型（および指定した全 `--property`）が実在・所属確認済み。または `--list-type-names`/`--describe`（全件実在）/`--list-properties` が完了。`--show-range` の有無は終了コードに影響しない
- `1`: 型が存在しない、プロパティが存在しない/所属しない、`--describe` に語彙へ無い名前が含まれる、`--list-properties` が `--type` なしで指定された、語彙の取得・パースに失敗、または `--type`/`--list-type-names`/`--describe`/`--list-installed-hierarchy` のいずれも指定されなかった

---

## rebuild_index.py

### 目的

Type ディレクトリの `index.md`（1 行 1 件の `- [[Type/slug]]` 箇条書き）を、ディレクトリを実際にスキャンして決定論的に再構築する。従来この更新は `wikicommit-generate`/`wikicommit-translate` の SKILL.md が「全ソース/ペア処理後に1回だけ」という手順としてLLMエージェントの記憶に委ねており、長い多段生成の末尾に置かれた「最後にこれも忘れずに」という位置づけの手順だったため、ソース件数が多いバッチほど実行し忘れるリスクがあった（Issue #406）。本スクリプトへの委譲により、対象ディレクトリを指定しさえすれば取りこぼしが構造的に起こらなくなる。

### 使用場面

- `wikicommit-generate` Skill：全ソース処理後、`index.md` 更新ステップとして呼び出す
- `wikicommit-translate` Skill：全 `(原文ページ, target言語)` ペア処理後、`index.md` 更新ステップとして呼び出す
- `wikicommit-synthesize` Skill：合成ページを書き出した直後、そのページの Type ディレクトリ 1 件のみを引数に指定して呼び出す（Issue #547）。他 2 Skill が引数なしで全 Type ディレクトリを走査するのは「長いバッチの末尾で対象ディレクトリの追跡を取りこぼさないため」であり、1 ページしか書かず `<lang>`/`<Type>` が確定している本 Skill にはその理由が当てはまらない。引数指定にすることで、対話実行される本 Skill の副作用が該当ディレクトリの外へ広がらない

### コマンド

```
python .wikicommit/scripts/rebuild_index.py [<type-dir>...]
```

- 引数なし: `.wikicommit/entity/` 配下で、`.md` ファイルを直接含むディレクトリ（`<lang>/<Type>/` 以深。ネストした custom 型も対象）をすべて自動検出して再構築する。過去の実行が書いた `index.md` しか残っていないディレクトリも対象に含める — 最後のページが `/wikicommit-remove` で削除された Type ディレクトリはページを1つも持たないため、「ページを持つディレクトリ」だけを検出対象にすると、その `index.md` が二度と再構築されず古い一覧のまま（かつ Issue #580 以前の `review_status` なしの frontmatter のまま）残り続ける
- 引数あり: 指定した Type ディレクトリ（例: `.wikicommit/entity/ja/Person`、ネスト custom 型は `.wikicommit/entity/ja/custom/Decision`）のみ再構築する

### 処理フロー

1. 対象ディレクトリごとに、ディレクトリパスを `.wikicommit/entity/<lang>/<Type>/` として解析する（`<Type>` はネスト custom 型の場合 `/` を含みうる）。ディレクトリが存在しない、または `.wikicommit/entity/` 配下の `<lang>/<Type>` 形式として解決できない場合は WARNING を出して当該ディレクトリをスキップする（他の対象ディレクトリの処理は継続する）
2. ディレクトリ直下の `*.md`（`index.md` を除く）を走査し、各ページの frontmatter を読む。frontmatter のパースに失敗したページ、`title` フィールドがないページは WARNING を出して index.md への掲載から除外する。`status: removed` のページも除外する（サイレント。孤立検出等と同じ既存の除外方針）
3. 残ったページをファイル名（slug）の昇順でソートする
4. `index.md` を書き出す:
   - frontmatter: `title`（そのディレクトリの `<Type>` の末尾セグメントのみ。例: `custom/Decision` → `"Decision"`。Issue #320 — `"<Type> Index"` ではなく bare Type name を使う）・`lang`・`type`（`schema:<Type>` の完全形）・`review_status: reviewed`（Issue #580）

     `review_status: reviewed` は `convert_wikilinks.py` の `generate_root_index()`・`_write_source_page()`・`_write_sources_index()`・`_write_source_dir_index()` が既に同じ理由で行っているスタンプと同じもの: `index.md` はビルド生成のナビゲーションページであって LLM が書いた Wiki コンテンツではないため、`WikiCommitBanner` の未レビュー警告を表示すべきでない（同コンポーネントはフィールドが無い場合 `pending` にフォールバックする — LLM 生成ページで書き漏れた場合に安全側へ倒すための意図的な設計であり、これ自体は変更しない）。Type 別インデックスは `convert_wikilinks.py` ではなく本スクリプトが生成し、しかも root index や source ページと違って `.wikicommit/entity/` 配下に実体を持つため、この慣習の適用対象から構造的に外れていた。

     除外の判定を `WikiCommitBanner` 側（`fileData.slug === "index"` 等）に置く案は採らない。同コンポーネントは Quartz のスラッグ命名規約に依存しない方針を明示している（`docs/DesignDoc-publish.md` §8）ため、書き出す側でフィールドを持たせる方が一貫する。なお `index.md` は `wikicommit-merge` のレビュー追跡 Issue の対象外でもあるため、バナーを見た読者が対応する Issue を探しても存在しない、という点でも表示は誤りだった。

     **既存リポジトリの是正**: 本スクリプトは対象ディレクトリの `index.md` を毎回フルスキャンから全上書きするため、次回 `/wikicommit-generate`・`/wikicommit-translate`・`/wikicommit-synthesize` が走った Type ディレクトリから順に自動的に是正される。一括移行の仕組みは用意しない — 全 Type を即座に是正したい場合は引数なしの `python .wikicommit/scripts/rebuild_index.py` を 1 回実行すれば足りる。
   - body: 各ページ1行、`- [[<Type>/<slug>]]` の箇条書き（slug 昇順）。**タイトルを接尾辞として付けない**（Issue #678。下記コールアウト参照）
   - 既存の `index.md` があれば全体を上書きする（差分マージではなく毎回フルスキャンからの再構築。手書きの前文等があっても保持しない）
5. 対象ディレクトリすべての処理後、`SUMMARY:` 行を1行出力する

> **行にタイトルを付けない理由（Issue #678）**: `convert_wikilinks.py` の `convert_file()` は WikiLink を**参照先ページの `title`** で描画するため、`[[Type/slug]] — {title}` という行は公開サイト上で `Adaptive Context Compaction — Adaptive Context Compaction` のようにタイトルの重複になる。Type 別インデックスは Wiki を回遊する主要な入口の 1 つであり、全型・全言語の**全行**がこの形になっていた。
>
> **この接尾辞は無意味に置かれたものではない**。同じファイルが 2 つの文脈で読まれ、片方でだけ重複する:
>
> | 読み手 | `[[Person/yamada-taro]] — 山田太郎` の見え方 |
> |---|---|
> | リポジトリ上（GitHub・エディタ） | GitHub は `[[...]]` を描画しないため、接尾辞がタイトルを伝える唯一の要素になる |
> | 公開サイト（Quartz） | WikiLink が参照先の `title` に置き換わるため `山田太郎 — 山田太郎` になる |
>
> この非対称は `rebuild_index.py` 単体を読んでも `convert_wikilinks.py` 単体を読んでも見えない。**生表示でタイトルが読めなくなることは受け入れる** — slug は言語中立の英語識別子（Issue #193）であり非英語 Wiki では可読性が落ちるが、(a) その情報は同じディレクトリのファイル名そのものが持ち、(b) この読み手は運用者であって読者ではなく、(c) 代償として読者向けの主要な回遊面すべてに重複が出続けることの方が大きい。
>
> なお `convert_wikilinks.py` が書き出す他の一覧（`_write_sources_index()` / `_write_source_dir_index()` / `generate_overview_page()`）はいずれも素の Markdown リンク `[{title}]({link})` を書いており、この問題を持たない。WikiLink を使っているのは Type 別インデックスだけである。
>
> **接尾辞を落とすだけでは足りず、行を箇条書き（先頭の `-` + 空白）にする**。インデックスの各行は空行を挟まない連続行であり、CommonMark はこれを 1 つの段落に畳む — 配布する `quartz.config.yaml` は `hard-line-breaks` プラグインを `enabled: false` で出荷しているため、ソフト改行は `<br>` にならない。つまり公開ページ側では**元から**全行が 1 段落に連結されており、接尾辞の `{title}` とその前の em dash が偶然その区切りとして働いていた。マーカーを付けずに接尾辞だけ落とすと、リンクの文字列同士が空白 1 個で隣接した 1 本の長い行になる（`BYOLLM ファイル境界プロトコル OKF（Open Knowledge Format） 孤立ページ …`）— 読者向けの主要な回遊面を直そうとして別の形で読めなくすることになる。`convert_wikilinks.py` が書き出す他の一覧（下記）が例外なく `- [{title}]({link})` を書いているのはこれと同じ理由であり、Type 別インデックスだけがマーカーを持っていなかった。
>
> **インデックス本文の書式を読み取るコードは 1 箇所ある**: `wikicommit-remove` の `remove_page.py` の `remove_index_entry()` は、`index.md` を全面再構築するのではなく該当行だけを行頭アンカーの正規表現で落とす（`main()` から呼ばれる）。同関数は先頭のリストマーカーを任意扱いにしてあり、`- [[Type/slug]]`（現行）・`[[Type/slug]]`・`[[Type/slug]] — Title`（いずれも旧書式。既存リポジトリは遡及移行しないため残る）の 3 形式すべてに一致する。**行の書式を変える際はここも併せて見ること** — 一致しなくなっても例外にはならず、`status: removed` のページを指す行が残り、次の `/wikicommit-merge` が `check_wikilinks.py` の「`status: removed` のページへのリンクです」ERROR でブロックされる形でしか現れない。
>
> **他のチェックには影響しない**（実装時に確認済み）: `check_orphans.py` は `index.md` をリンク元として明示的にスキップするため孤立判定は変わらず、`search_index.py` の `build` は `index.md` を索引対象から除外するため検索結果も変わらない。`check_wikilinks.py` は引数なしモードでインデックスの WikiLink も検証するが、リンクは実在ページのディレクトリ走査から生成されるため構成上必ず解決する（`WIKILINK_RE` は行内の部分一致であり、リストマーカーの有無に左右されない）。
>
> **採らなかった案**: publish 時に `convert_file()` 側で接尾辞を strip する（`is_index` を渡す）。両方の読み手を満たせて、`rewrite_relative_links()`・`flatten_custom_type()`（Issue #576）という publish 時変換の前例にも乗るが、**インデックス本文の書式を書く側と publish 側が「行のどこからどこまでがタイトルか」まで knowing する状態**を作り、`rebuild_index.py` が書式を変えた瞬間に strip が黙って効かなくなる。これはこのリポジトリが繰り返し踏んできた drift の形そのものである（Issue #114・#487・#677）。上記の `remove_index_entry()` も書式を知る 2 つ目の箇所ではあるが、参照するのは行頭の WikiLink までであり、行の残りには一切依存しない（`.*` で捨てる）ため、この drift の形には当たらない。
>
> **遡及移行は不要**。本スクリプトは対象ディレクトリの `index.md` を毎回フルスキャンから全上書きするため、次に `/wikicommit-generate`・`/wikicommit-translate`・`/wikicommit-synthesize` が走った Type ディレクトリから順に是正される（Issue #580 のスタンプ追加時と同じ経路）。全型を即座に揃えたい場合は引数なしの `python .wikicommit/scripts/rebuild_index.py` を 1 回実行すれば足りる。公開サイトへの反映は次のデプロイを待つ。

### 出力フォーマット

```
OK: .wikicommit/entity/ja/Person/index.md rebuilt (3 pages)
WARNING: .wikicommit/entity/ja/Place: directory not found, skipped
SUMMARY: rebuilt=1
```

### 終了コード

- 常に `0`（`wikicommit-merge` の品質ゲートではなくワークフロー手順の一部のため、個別ディレクトリの解決失敗はブロッキングにしない）

---

## reconcile_ingest_status.py

### 目的

`status: pending` のまま放置されている ソース管理ファイルのうち、実はその `source.hash` が既に公開ページの `sources[]` に使われているもの（＝内容は既に取り込まれているのに、そのソース自身の管理ファイルへの書き戻しだけが行われなかったもの）を検出し、`status: generated`・`generated_pages`・`last_generated_at` を書き戻す（Issue #474）。`ai-driven-dev-wiki`（round2）パイロットで、複数の関連ソースが同一エンティティのページを共同更新した際、そのうち一部の管理ファイルが `status: pending`・`generated_pages: []` のまま取り残される事例が確認された。

当初はこの照合・書き戻しを `wikicommit-generate` SKILL.md の instruction（LLMへの散文指示 + grep）として実装したが、`/code-review --fix` の多角的レビューで、この instruction ベースの設計自体が複数の実害あるバグを抱えていることが判明した（詳細は `docs/DesignDoc-skills.md` §11.6 の Issue #474 callout を参照）。最も重大だったのは、`status: outdated` のファイルは `check_ingest_freshness.py` が意図的に `source.hash` を書き換えずに残す（前回生成時点の参照点として機能させるため）ため、`outdated` ファイルに対して同じ hash 一致判定を適用すると、「ソースが変更され再処理が必要」という正しいシグナルを「既に反映済み」と誤認して握りつぶしてしまう欠陥だった。本スクリプトはこの反省を踏まえ、`status: pending` のみを対象とし（`outdated` は明示的に対象外）、一致した場合は常に `status: generated` のみを設定する（`partial`/`excluded`/`failed` への遡及推定は行わない — それらは Pass 2/4 のエンティティ単位の結果が必要で、その場限りの情報のため後から再構築できない）。

### 使用場面

- `wikicommit-generate` Skill：全ソース処理後、`index.md` 更新（`rebuild_index.py`）に続けて呼び出す

### コマンド

```
python .wikicommit/scripts/reconcile_ingest_status.py [--today=YYYY-MM-DD]
```

`--today` はテスト用（`check_expires.py` と同じ慣習）。省略時はシステム日付を使う。

### 処理フロー

1. `.wikicommit/entity/**/*.md`（`index.md` を除く）を走査し、各ページの `sources[].hash`（`sha256:` プレフィックスを除いた16進文字列）から「hash → そのhashを引用しているページパスのリスト」のマップを構築する
2. `.wikicommit/source/**/*.md` を走査し、`status: pending` の管理ファイルのみを対象にする（`pending` 以外は対象外。特に `outdated` は上記の理由により明示的に除外する）
3. 対象ファイルの `source.hash` が空文字列・未設定の場合はスキップする（`type: url` ソースが Pass 1 でまだフェッチされていない場合に発生しうる。空文字列を許すと事実上すべてのページに一致してしまうため）
4. 1で構築したマップにこのhashが存在すれば、一致したページパスを重複排除・昇順ソートした上で、`status: generated`・`generated_pages`（一致したページパスのYAML flow-styleリスト）・`last_generated_at`（実行日）を書き戻す。`## Failure Reason` セクションが存在すれば削除する（Pass 4 手順7の `generated` 分岐と同じ扱い。Issue #408）
5. 全管理ファイル処理後、`SUMMARY:` 行を1行出力する

### 出力フォーマット

```
RECONCILED: .wikicommit/source/url/github.blog/copilot-agent-mode.md (status: pending -> generated, generated_pages: .wikicommit/entity/en/Organization/github.md)
page: .wikicommit/source/url/github.blog/copilot-agent-mode.md
SUMMARY: reconciled=1
```

該当なしの場合:

```
SUMMARY: reconciled=0
```

### 終了コード

- 常に `0`（`wikicommit-merge` の品質ゲートではなくワークフロー手順の一部のため）

---

## reset_review_on_content_change.py

### 目的

信頼ラダーの上段（`review_status: reviewed` と、Issue #663 以降そこに添えられる `reviewed_by` の実名）は「この文章を人間が読んだ」という主張である。ところがページを書き込む 6 経路のうち 2 つが、その主張を動かさないまま文章だけを差し替えていた（Issue #724）。

| 経路 | `review_status` |
|---|---|
| `action: create` | `pending` |
| `--regenerate` | `pending`（理由を明記して `action: update` の規則を上書き） |
| `wikicommit-translate` | `pending`（無条件） |
| `wikicommit-synthesize` | `pending`（無条件） |
| **`wikicommit-generate` Pass 3 の `action: update`** | **`reviewed` を維持していた** |
| **`wikicommit-fix`** | **規則が無く、触れていなかった** |

後者の方が鋭い — `/wikicommit-fix` は「レビュー済みの内容が誤っていた」から起動されるものであり、しかも公開ページの報告リンクは `review_status` に関わらず常時表示される（Issue #245）ため、`reviewed` なページの誤りを読者が報告するのは**設計上の主経路**である。結果として、そのレビューが見落としたからこそ書き直された文章に、レビュアーの実名が付き続けていた。

加えて `wikicommit-merge` Step 8 は `pending` のページにしか追跡 Issue を作らないため、更新された `reviewed` ページは**恒久的に再レビューされない終端状態**になっていた。

### 「常に戻す」を採らない理由

無条件に戻すと、取り込みを続ける Wiki ではページが `reviewed` と `pending` を往復し、そのたびに追跡 Issue が立つ。レビュー負荷が青天井になり `reviewed` が到達不能になる — 信頼ラダーの価値は上段に**届くこと**にも依存している。代わりに、再生成モードの unchanged-output valve（`docs/DesignDoc-pipeline.md` §6.1）と同じ形を採り、**内容が変わったかどうか**で判定する。規則は 1 つで足りる: `action: update` では bookkeeping だけの更新が普通にあるため条件付きになり、`wikicommit-fix` では定義上必ず内容が変わるため常に発火する — 同じ規則が入力の違いで別々に振る舞うだけであり、経路ごとに別の規則を書かない。

### 使用場面

- `wikicommit-generate` Skill：Pass 4 step 6（ページ書き出しの直後、書き出した全ページを 1 回の呼び出しで渡す）
- `wikicommit-fix` Skill：Step 5 item 4（Edit 実行の直後、書き込んだページごとに 1 回）

### コマンド

```
python .wikicommit/scripts/reset_review_on_content_change.py <page>...
```

`<page>` は `.wikicommit/entity/` または `.wikicommit/view/` 配下のページ（Issue #477 以前の `.wikicommit/wiki/` 接頭辞も受け付ける。`index.md` は下記の処理フロー 2 のとおり除外する）。**両ツリーを受け付けることが要件である** — `wikicommit-fix` は Issue #675 以降どちらの接頭辞も対象に取り、view ページも `review_status` と追跡 Issue を持つため、entity ツリーだけを見るとその半分が黙って素通りする。

### 内容フィールドと bookkeeping フィールドの線引き

無視するのは以下の 6 つだけで、**それ以外の frontmatter フィールドと本文はすべて内容として扱う**（再生成モードの valve が 5 フィールドだけを無視するのと同じ ignore リスト方式を広げたもの）。判定は「人間のレビューが要るか否か」を左右するため、知らないフィールドは安全側＝内容として数える。

| 扱い | フィールド |
|---|---|
| **内容**（変われば `pending` に戻す） | 本文、`title`、`tags`、`properties.*`、`expires_at`、および上記以外の全フィールド |
| **bookkeeping**（無視する） | `generated_at` / `generated_by` / `generated_with`、`review_status`、`reviewed_by`、**`sources[]`（追加・`hash` 更新・`license` 補完を含む）** |

**`sources[]` を bookkeeping 側に置くことがこの方針の要である。** `action: update` はほぼ必ずソースを追記する（それがこの分岐の目的である）ため、`sources` の変化を内容とみなすと本スクリプトは「常に戻す」に潰れ、上で退けたはずの負荷の懸念がそのまま現実化する。人間がレビューしたのは記述であり、同じ記述に裏づけが 1 件増えることはその判断を無効にしない。

`expires_at` は内容側に残す — Pass 4 がこれを他の主張と同様にソースとの照合対象にしている（Issue #279）以上、検証対象の主張である。`translator_notes`（`wikicommit-fix` Step 5 が追記する翻訳固有の申し送り）は性質上 bookkeeping 寄りに見えるが、同じ Edit で本文も変わっているのが通常なので実質的な差が出ず、ignore リストを増やさない側に倒してある。

### 処理フロー

1. 引数が `.wikicommit/entity/` / `.wikicommit/view/` / 旧 `.wikicommit/wiki/` のいずれの配下でもなければ ERROR（誤ったパスが黙って no-op になるのを防ぐ）
2. `index.md` は `SKIP:`。`rebuild_index.py` がビルド生成のナビゲーションページとして書き出し、まさにその理由で `review_status: reviewed` を刻む唯一のページである（Issue #580）— 人間のレビューを経ていない `reviewed` がここだけは正当であり、降格させると `wikicommit-merge` Step 8 が index を追跡 Issue の対象外にしている以上**戻す経路が無いまま公開サイトに未レビューバナーが出続ける**。他の全走査スクリプトと同じ除外である（`wikicommit-fix` の公開 URL 逆引きは `**/*.md` を glob するため index も候補に入りうる）
3. 作業ツリー側のページを読み frontmatter と本文に分ける。パースできなければ ERROR
4. `review_status` が `reviewed` でなければ `SKIP:`（降格すべき主張が無い）
5. `git show HEAD:<path>` で前版を取得する。**比較先を HEAD にする**ことで、同一バッチ内で未コミットのまま 2 回更新された場合も正しく振る舞う（HEAD は依然として人間がレビューしえた最後の版である）。追跡されていなければ `SKIP:` — 新規作成は元から `pending` であり、比較すべき前版が存在しない。取得結果は**バイト列で受け取り、作業ツリー側の読み込みと同じ規則で自前でデコードする**（`utf-8-sig` ＋ 改行コードの正規化）— `subprocess` の `text=True` に任せるとロケール依存のコーデックになり、非 UTF-8 ロケール（Windows ネイティブ Python の cp932 / cp1252 等）では非 ASCII ページで `UnicodeDecodeError` が実行全体を途中で落とし、latin-1 系ロケールでは例外にすらならず文字化けした HEAD 版と突き合わせて全ページが無条件に降格する。BOM を落とすのも同じ対称性のためで、落とさないと HEAD 側だけ `---` 始まりと認識されず「frontmatter 無し・本文＝ファイル全体」に見えるため、1 文字も変えていないページが「内容が変わった」と判定される（`_frontmatter.py` がスクリプト間の BOM 扱いの食い違いを実バグとして名指ししているのと同じ種類の非対称である）
6. bookkeeping を除いた frontmatter フィールドを突き合わせ、本文は改行コードと前後の空行のみ正規化して比較する（内容の差は吸収しない）。HEAD 側の frontmatter が読めない場合は stderr に `WARNING:` を出したうえで**内容が変わったものとして扱う** — 誤って戻す代償は追跡 Issue が 1 件増えることだが、誤って維持する代償は人間が読んでいない文章に署名が残ることである
7. 一致すれば `UNCHANGED:`（何も書き換えない）。異なれば `set_frontmatter_field.py` の `apply_frontmatter_fields()` を in-process で呼び、`review_status: pending` を設定して `reviewed_by` を落とし `RESET:` を出す（Issue #705 の「`reviewed_by` は常に `review_status` に従わせる」という既存の規範。1 回の呼び出しで両方を行う）

### プローズの手順にしない理由

完全に決定論的に判定できる操作を SKILL.md の instruction として書くと、非決定論的な失敗モードを持ち込む（Issue #474）。しかも本件は「人間のレビューが要るか否か」を左右する判定であり、再生成モードの valve が同じ理由で比較を意味的同一性ではなくテキスト一致にしているのと同じ配慮が要る。

### 既知の限界

`properties.description` が 1 文変わった場合と句読点だけが変わった場合を区別しない。テキスト一致で判定する以上これは避けられず、再生成モードの valve も同じ割り切りをしている。**既に陳腐化した `reviewed` を抱えた既存ページへの遡及適用も行わない**（本ドキュメント群が一貫して採る「新旧混在を許容する」方針）— 次にそのページが更新されるか人間が直すまで残る。

### 出力フォーマット

```
RESET: .wikicommit/entity/ja/Place/minuma.md: content changed since HEAD (body, properties); review_status reviewed -> pending, reviewed_by dropped
UNCHANGED: .wikicommit/entity/ja/Person/yamada-taro.md: content matches HEAD; review_status kept as reviewed
SKIP: .wikicommit/view/ja/agent-loop.md: review_status is not reviewed; nothing to demote
SKIP: .wikicommit/entity/ja/Place/index.md: index page (build-generated); nothing to demote
SUMMARY: reset=1, unchanged=1, skipped=2, errors=0
```

### 終了コード

- `0`: 正常終了（戻した／変わっていない／対象外、のいずれも正常系）
- `1`: 引数が entity/view ツリーの外を指している / ページが存在しない / 作業ツリー側の frontmatter がパースできない。1 件が ERROR でも残りのページの処理は続行する

---

## record_review.py

### 目的

`wikicommit-generate` Pass 4 は生成した全ページに 8 種類の検査を掛けながら、その判定を 1 バイトも残していなかった（Issue #750。詳細と設計判断は `docs/DesignDoc-data.md` §4.8）。本スクリプトはその判定を、ページ単位のディレクトリに**レビュー単位の不変ファイル**として書き出す。

**判定は LLM が下し、ファイル手術はスクリプトが行う**（Issue #474）。`set_frontmatter_field.py` / `reset_review_on_content_change.py` と同じ形だが、こちらは**既存ファイルを一切読まず・書き換えず、新規作成のみ**を行う。

### 使用場面

- `wikicommit-generate` Pass 4：書き出したページと、`failed_pages` に落ちたページの両方
- `wikicommit-review` Step 5：追跡 Issue を Close した経路・ローカルに書いた経路の両方
- `wikicommit-synthesize` Step 5.5：PASS・retry 上限超過の両方
- `.github/workflows/review-issue-close-sync.yml`：`review_status` を書き換えるのと同じコミットで。Close した本人の最新コメントを `--note-file` で渡し、記録の散文本文にする（Issue #762。選別と injection 上の扱いは `docs/DesignDoc-data.md` §4.8 参照）

### コマンド

```
python .wikicommit/scripts/record_review.py <page> \
    --kind ai|human --stage generate-pass4|review-skill|synthesize-step5.5|issue-close \
    --result pass|fail|discarded [--attempts N] \
    [--model "<model ID>"] [--reviewer "<GitHub login>"] \
    [--skill-blob <hash>] [--json <path>|-] \
    [--note <text>] [--note-file <path>] [--sources-from <mgmt file>]... \
    [--reviewed-at YYYY-MM-DD]
```

`--skill-blob` に渡すのは `.wikicommit/review-rules.md` の blob hash である（Issue #752 — 規律がそのファイルへ移ったため。`rules_version` との役割の違いは `docs/DesignDoc-data.md` §4.8 参照）。

`<page>` は `.wikicommit/entity/` または `.wikicommit/view/` 配下のページ（Issue #477 以前の `.wikicommit/wiki/` 接頭辞も受け付け、記録は `entity/` 配下に寄せる — 記録はページについてのものであり、後から `git mv` したリポジトリの履歴が 2 つに割れないようにするため）。**ディスク上に存在しなくてよい** — `result: discarded` がまさにその場合である。

### 処理フロー

1. 引数が上記 2 ツリーの外を指していれば ERROR（誤ったパスが黙って no-op になるのを防ぐ）。`--kind ai` に `--model` が無い場合も ERROR — モデルに帰属できない判定は、この記録ツリーが可能にしようとしている偏りの測定に使えない
2. `--json` から §4.6 の JSON を読む（`-` で標準入力、省略で findings なし）
3. `issues[]` を `FINDING_FIELDS`（`round` / `type` / `claim` / `source_file` / `source_lines` / `instruction` / `page_at_fault`）に射影する。**`source_quote` は呼び出し側が渡してきても落ちる**。`round` が無い場合は 1 を補う。`source_file` の**空文字列は残す** — `wikicommit-synthesize` の `MISSING_SOURCE` は定義上どの grounding ページも当てはまらないため意図的に空にする（Issue #674）ので、キーごと落とすと「呼び出し側が入れ忘れた」と区別できなくなる
4. `page_content_hash` を計算する。無視リストは `reset_review_on_content_change.py` の `BOOKKEEPING_FIELDS` を **import** する（複製しない）。正規化は「内容フィールドを `yaml.safe_dump(sort_keys=True)` したもの + 本文を同スクリプトと同じ規則で正規化したもの」の SHA-256。`--result discarded` では空文字列
5. `reviewed_sources` を、ページの `sources[]`（view ページは `derived_from`）から取る。`--sources-from` が指定されていればそちらを優先する（ページが存在しない `discarded` 用）
6. `.wikicommit/review/<ページパスから .wikicommit/ と .md を落としたもの>/<YYYYMMDD>-<HHMMSS>-<kind>.md` に新規作成する。同名が存在すれば `-2`、`-3`… を付す（**上書きは契約上あり得ない**）

### 出力フォーマット

```
RECORDED: .wikicommit/review/entity/ja/Person/yamada-taro/20260905-142233-ai.md (page=.wikicommit/entity/ja/Person/yamada-taro.md, result=pass, attempts=2, findings=1)
```

### 終了コード

- `0`: 記録を 1 件書いた
- `1`: 引数不正、entity/view ツリーの外、ページが存在しない（`discarded` 以外）、JSON が読めない／壊れている、書き込み失敗

---

## check_review_coverage.py

### 目的

`record_review.py` が書いた記録を読み戻す（Issue #750）。**消費者が同時に存在すること**が要件である（Issue #553）— 読む主体が無ければ、記録ツリーは常に空のまま残る受け皿になる。

4 つの問いに答える: どれだけレビューされたか（`SUMMARY:` / `COVERAGE:`）、**今の本文を判定した記録が何も無いのはどれか**（`UNREVIEWED:`）、**人が読むならどれか**（`RISKY:`）、**どの判定がもう当てはまらないか**（`STALE_REVIEW:`）。

**すべての行が「standing な記録」1 件を読む**（Issue #766）— そのページを**今の姿のまま判定した最新の記録**である。kind の別だけが行ごとに違う（`ai_reviewed` / `COVERAGE:` は AI、`human_reviewed` は human、`RISKY:` は kind を問わず、`STALE_REVIEW:` / `RETRACTED_EVIDENCE:` は AI）。唯一の例外は `SUMMARY: findings=` で、こちらは歴史的な量として全記録を合算する。

### 使用場面

- `wikicommit-status` Skill：Step 13

### コマンド

```
python .wikicommit/scripts/check_review_coverage.py
```

引数なし。`.wikicommit/entity/` + `.wikicommit/view/` の全ページと `.wikicommit/review/` を対象とする。

### 処理フロー

1. `.wikicommit/review/` が無ければ全 0 と `NOTE:` を出して終了する — 「まだ一度もレビューを記録していない」と「全部 0 だった」は別の状態であり、区別せずに 0 だけを出すと後者に見える
2. 各ページの記録ファイルを `record_review.py` の `record_sort_key()` 順（＝時刻順）に読む。**素のファイル名の辞書順ではない** — 同一秒の衝突サフィックス（`...-ai-2.md`）は `-` が `.` より小さいため `...-ai.md` の**前**に来るので、辞書順で最後のファイルを取ると「その秒の最も古い記録」を最新として拾う。書き手（採番）と読み手（最新の判定）が同じキーを共有する
3. **standing な記録（kind を問わない）が 1 件も無ければ** `UNREVIEWED:`。ほとんどの場合それは「記録が 1 件も無い」ことだが、**記録はあるが全件が `result: discarded` だった**場合も含む（Issue #766）— 破棄された判定は捨てられた下書きを見たものであり、ディスク上の本文について何も述べていない。後者では行に注記を添えて状態を区別する — 全件が `result: discarded` なら `(<N> record(s) exist, but every one was discarded; none judged the page as it now stands)`、そうでなければ `(<N> record(s) exist, but none carries a page_content_hash, so none judged the page as it now stands)`。**注記の理由は `result` から読む**（standing でなくした空ハッシュからではない）— 両者は `record_review.py` が書くものについては一致するが、このツリーは人間が手で書けることを意図している（Issue #750）ため、`page_content_hash` を持たない手書きの記録を「破棄された」と言うと、存在しなかった破棄を探しに行かせることになる
4. **書き出されたページを判定した最新の記録 1 件**（kind を問わず `page_content_hash` が非空のもの）を見て、その `attempts >= 2` または findings が 1 件以上あれば `RISKY:` — **これが抜取の設計図**である（Issue #760。下記コールアウト参照）
5. **書き出されたページを実際に判定した最新の `kind: ai` 記録**（`page_content_hash` が非空のもの）について失効を判定する。`result: discarded` の記録は空ハッシュを持ち、ディスク上のページについて何も述べていないため対象にしない — Pass 4 step 5 は `action: update` のエンティティに対しても`discarded` を記録し、そのとき既存ページはそのまま残る一方 `reviewed_sources` は `--sources-from`（＝取り込もうとしていたソース）から作られるので、ページ側に無いのが当然のソースと突き合わせて`source no longer on the page` を永久に報告し、しかも本当に有効な直前の判定を隠してしまう:
   - `page_content_hash` を再計算して不一致なら `STALE_REVIEW:`（`page content changed since <日付>`）。空ハッシュ（`discarded`）はスキップ
   - `reviewed_sources` の各エントリを現在のページの `sources[]` / `derived_from` と識別子（`url` / `path`）で突き合わせ、`hash` / `source_commit` が変わっていれば `STALE_REVIEW:`（`source changed: <識別子>`）、ページから消えていれば `source no longer on the page: <識別子>`
   - `reviewed_sources` に `status: retracted` のソース（Issue #737）が含まれていれば `RETRACTED_EVIDENCE:`
6. `SUMMARY:` と、モデルごとの `COVERAGE:` を出す。`ai_reviewed` / `human_reviewed` と `COVERAGE:` の `pages` / `findings` / `attempts>=2` はいずれも standing な記録から数える。`COVERAGE:` の 4 つ目の数（`<N> discarded`）だけは別で、**そのページの最新の AI 記録が `result: discarded` であり、かつそれをこのモデルが書いたページ数**を数える — standing な記録には現れない「投げ捨てられた試行」を、カバレッジを水増ししない位置に置くためのもの。**モデルごとの最新ではなくページごとの最新で判定する** — この数は「`RISKY:` が黙っている理由」を説明するために在るので、後から別のレビューが今の本文を判定していれば説明すべき沈黙自体が無く、追い越された破棄は数えない

**`STALE_REVIEW:` がノイズにならないことは構造から言える** — Pass 4 は再生成のたびに走り直すので、失効するのは実質 `wikicommit-fix` で直したページと、ソースが変わったページだけである。

> **`RISKY:` は履歴ではなく「今立っている判定」1 件だけを見る（Issue #760）**: 当初この行はそのページの**全記録**にわたって `max(attempts)` と findings 件数を集計していた。記録は不変で削除もされない（Issue #750 の設計の中核）ため、**一度でもリトライされた・一度でも指摘を受けたページは、その後どれだけクリーンに再レビューされても永久に `RISKY:` から外れない**。取り込みを続ける Wiki ではこの一覧が Wiki 全体へ収束していき、そうなった時点で何も選別していない — Issue #562 が低情報密度ガードを blocking から降格させたときと同じ力学である。
>
> **これは新しい方針の持ち込みではなく、同じ `main()` が既に持っていた 3 通りのうちどれに寄せるかの選択だった**。`COVERAGE:` は最新の AI 記録 1 件だけを見、`STALE_REVIEW:` / `RETRACTED_EVIDENCE:` は `standing_verdict()`（書き出されたページを判定した最新の AI 記録）を見る一方、`RISKY:` だけが全記録を見ていた。**Issue #760 の案 (b)（最新の判定のみ）を採る**。
>
> **Issue #760 が (b) の弱点として挙げた「『2 回目でようやく通った』という履歴が消える」は成立しない**。Pass 4 は 1 レビューにつき 1 記録を書き、その記録自身が `attempts` を持つ（全ラウンドの findings も `round` 付きでフラットに載る。`docs/DesignDoc-data.md` §4.8）。したがって 2 回目で通ったページの記録がそのまま standing な判定であり、`attempts: 2` は引き続き報告される — 落ちるのは**より新しいレビューが現在の本文を判定した後**だけであり、それはその履歴がページを説明しなくなった時点そのものである。
>
> **kind は問わない**（`standing_verdict()` ではなく新設の `standing_review()` を使う）。Issue #760 検討事項 1 が指摘するとおり `/wikicommit-review` は人間の判定にも `--result fail` と findings を書けるため、`kind: ai` に限ると人間の指摘が一度も `RISKY:` に出ないという、旧実装より悪い取りこぼしになる。**`STALE_REVIEW:` 側は `standing_verdict()`（AI のみ）のまま変えていない** — あちらが突き合わせるのは機械が見た `reviewed_sources` であり、Issue #760 のスコープ外である。
>
> **`result: discarded` の記録は数えない**（同 検討事項 2）。`page_content_hash` が空の記録は書き出されなかったページについての判定であり、ディスク上のページについて何も述べていない — `standing_review()` がそれを飛ばすことで、この論点は案 (b) と同時に決まる。
>
> **案 (c)（最後の人間レビュー以降に絞る）は独立した機構としては採らない**（同 検討事項 3）。人間レビューが一度も無い Wiki では (a) と同じに退化するうえ、「人間が読んだことを RISKY の抑制シグナルとして使えるか」は実データを見ないと決められない、と Issue #760 自身が述べている。ただし人間の記録も**後続のレビューとして普通に standing になりうる**ため、人がそのページを読んで `result: pass` を記録すれば結果として一覧から外れる — 新しい規則ではなく、同じ規則が一様に適用された帰結である。
>
> **`SUMMARY: findings=` は意図的に累積のまま**とする。あちらが答えるのは「この Wiki の一生でレビューが何件捕まえたか」という歴史的な量であり、現在の状態ではない。
>
> **既存の記録への遡及処理は行わない**（記録の不変性は Issue #750 の設計の中核）。変わるのは読み方だけであり、記録は 1 バイトも書き換えない。
>
> **閾値は導入していない**。本 Issue が問うたのは「どの記録を見るか」であって「何件から警告するか」ではない（下記「閾値・合否判定・自動化は入れない」はそのまま有効）。

**`RETRACTED_EVIDENCE:` と `check_retracted_sources.py` は二重報告ではない**（Issue #750 検討事項 7）。あちらは「取り下げ済みソースを `sources[]` になお持つ**ページ**」を報告する。こちらが言えるのは、`reviewed_sources` にしか無い情報 — **その取り下げ済みソースが、判定を下した時点で証拠として使われていたのか**（前者は判定自体が撤回された証拠に依っていたことを意味し、レビュー後に足された場合は意味しない）。

> **`discarded` の記録しか持たないページを、数えるのをやめて名指しする（Issue #766）**: Issue #760 が `RISKY:` を standing な判定 1 件に絞った結果、**`result: discarded` の記録しか持たないページがどの per-page 行にも現れなくなった** — `UNREVIEWED:` は「記録が 1 件も無い」ページだけを見ており、`RISKY:` も `STALE_REVIEW:` も破棄された記録を飛ばすためである。一方 `SUMMARY: ai_reviewed` と `COVERAGE:` は `latest_by_kind()` を使っており破棄された記録を飛ばさないので、**そのページは「レビュー済み」として数えられながら、ディスク上の本文を判定した記録は 1 件も無い**という状態になっていた。`COVERAGE:` が「1 pages with attempts>=2」と言うのに対応する `RISKY:` がどこにも無い、という食い違いも同じ原因である。到達経路は仮定ではない — `action: update` のエンティティで Pass 4 が `max_retries` を使い切ると既存ページはディスクに残ったまま `discarded` が記録され、そのページが記録ツリー導入より前に生成されていれば他の記録を持たない。
>
> **原因は 1 つで、`main()` が「このページの記録」を 3 通りの別々の定義で読んでいたことにある**。Issue #760 が `RISKY:` を standing へ寄せた後も、集計と `UNREVIEWED:` だけが「最新の AI 記録（判定していなくてもよい）」「記録が存在するか」という別の規則のまま取り残されていた。したがって採ったのは**定義を 1 本にすること**であり、Issue #766 が並べた案の (a)＋(b)＋(d) の組み合わせにあたる。
>
> | 案 | 採否 | 理由 |
> |---|---|---|
> | (a) `ai_reviewed` から除く | **採用** | 「レビュー済み」の分子は「今の本文を判定した記録があるページ」でなければ、カバレッジがそのまま過大表明になる |
> | (b) `UNREVIEWED:` に出す | **採用**（注記付き） | 下記 |
> | (c) `DISCARDED_ONLY:` 行を足す | 不採用 | 下記 |
> | (d) `COVERAGE:` も飛ばす | **採用**（`discarded` 列付き） | 下記 |
>
> **(b) と (c) は「行が出ないこと」を直す 2 案であり、決め手は per-page 行ではなく `wikicommit-status` Step 17 の側にある**。per-page 行はヒットが 0 なら 1 行も出ないので、`DISCARDED_ONLY:` を足すこと自体は静かである。しかし Step 17 はカテゴリごとに**必ず 1 行**を描画するため、(c) は「ほぼ常に 0」の 6 行目をレビューカバレッジ表示に恒久的に足すことになる（Issue #562 が名指しした、常時点灯する所見が読まれなくなる力学の裏返し — こちらは常時 0 の行が読まれなくなる）。(b) の弱点として Issue #766 が挙げた「`UNREVIEWED:` の現在の意味（記録が 1 件も無い）と食い違う」は、**行に注記を添えることで引き受けた**: 2 つの状態は「誰かがこのページを見なければならない」という同じ行動を要求するので 1 本の一覧でよく、注記があれば読み手は破棄が繰り返された方を区別して原因を追える。**注記を持つのは後者だけ**（`tests/test_check_review_coverage.py` が両方向を固定する）。
>
> **(d) の弱点（破棄された判定がモデル別の集計から丸ごと落ちる）は、`COVERAGE:` に 4 つ目の数を足して引き受けた**。`<N> discarded` は「そのページの最新の AI 記録が破棄されており、それを書いたのがこのモデルだったページ数」であり、standing な 3 つの数とは性質が違うことがその位置で分かる。これがあると、**`COVERAGE:` が静かな `RISKY:` と食い違って見えるのではなく、なぜ静かなのかを自分で説明する**。新しい行ではなく既存行の 1 列なので Step 17 の行数は 5 のまま変わらない。`SUMMARY: findings=` は Issue #766 のスコープ外の指示どおり**累積のまま**（破棄された判定の findings も数え続ける）であり、`COVERAGE:` に揃えていない。
>
> **`kind: human` の `discarded` は現時点で到達しない**（`--result discarded` を書く呼び出し元は `wikicommit-generate` Pass 4 と `wikicommit-synthesize` Step 5.5 の 2 つだけで、どちらも `--kind ai`）。それでも `human_reviewed` も standing で数えるようにしたのは、**挙動が 1 ビットも変わらない**一方で、Issue #766 が「構造上ある歪み」と名指しした非対称が残らないためである。
>
> **既存の記録への遡及処理は行わない**（記録の不変性は Issue #750 の設計の中核）。変わるのは読み方だけで、記録は 1 バイトも書き換えない。**閾値も導入していない**。

### 出力フォーマット

```
SUMMARY: pages=95, ai_reviewed=93, human_reviewed=12, findings=27, models=2
COVERAGE: claude-opus-5[1m] 83 pages, 24 findings, 9 pages with attempts>=2, 1 discarded
UNREVIEWED: .wikicommit/entity/ja/Place/x.md
UNREVIEWED: .wikicommit/entity/ja/Place/u.md (2 record(s) exist, but every one was discarded; none judged the page as it now stands)
RISKY: .wikicommit/entity/ja/Place/y.md (attempts=3, findings=2)
STALE_REVIEW: .wikicommit/entity/ja/Person/z.md (page content changed since 2026-09-05)
STALE_REVIEW: .wikicommit/entity/ja/Place/w.md (source changed: https://example.com/a)
RETRACTED_EVIDENCE: .wikicommit/entity/ja/Place/v.md (the review of 2026-09-05 rested on https://example.com/b, since retracted)
```

### 既知の限界

**孤児の記録は報告しない**（Issue #750 検討事項 3）。ページが削除されても記録は残す方針のため、実在しないページの記録が蓄積する。報告するか放置するかは実データが溜まってから決める — 今それを足すと、誰も求めていないものと引き換えに毎回 1 行増える。

**閾値・合否判定・自動化は入れない**。実測が無い状態で決めた閾値は推測にすぎない。人が `RISKY:` / `COVERAGE:` を読んで `/wikicommit-generate --regenerate`（Issue #578）を叩けばループは人力で閉じる。

### 終了コード

- 常に `0`（情報提供のみ、ブロッキングしない）

---

## record_run.py

### 目的

このリポジトリの記録層は 4 つあり、**そのすべてが成果物を単位にしている** — git 履歴はファイル、ソース管理ファイルはソース 1 件、レビュー記録（Issue #750）はレビュー 1 件、追跡 Issue はページ 1 枚。**実行 1 回を単位とする記録が無い**ため、次の 3 つに答えられなかった（Issue #790）。

| 問い | 既存の層が答えられない理由 |
|---|---|
| ページはいつ生成されたか | `generated_at` は日付。コミット時刻は**マージ**時刻。レビュー記録のファイル名の秒は Pass 4 が**見終わった**時刻で、リトライが入れば数分ずれる |
| 実行は完走したか | 途中で死ぬと一部が `pending`・一部が `generated` で止まり、Issue #567 が扱った「まだ順番が来ていない滞留」と**見え方が同じ**。ガード C（Issue #574）・`rules_version` 不一致（Issue #752）はファイルを 1 つも変えずに止まるため git に痕跡がゼロ |
| どれだけかかったか | どこにも無い |

**`generated_at` を日時に変えてもページ単位の精度にはならない** — Pass 3 はファイル境界プロトコルで複数ページを 1 回の出力にまとめて書くため、秒を打ってもバッチの全ページが同じ値を共有する。**ページ単位の点の時刻はそもそも存在せず、存在する単位は実行である。**

### git で追跡しない（Issue #750 とは逆）

レビュー記録を追跡した 3 つの理由は、いずれも実行記録には当てはまらない。

| Issue #750 が追跡された理由 | 実行記録は |
|---|---|
| Wiki の歴史全体にわたる**測定**が目的（測定は遡って作れない） | 消費者は「直近の実行」「未完走の実行」しか見ず、歴史を必要としない |
| 公開ページの表示に使う（Issue #751） | 何も表示しない。`convert_wikilinks.py` はこのツリーを歩かない |
| 判定そのものがページの信頼に関わる | 実行の外形であり、Wiki の知識ではない |

追跡する代償は実在する: generate のたびに 1 ファイルが PR へ混ざり、**git では削除に意味がないため保持期間を決められない**。追跡しないことで、ローテーションが可能になり、`wikicommit-merge` は無改修で済み、lychee / markdownlint のスコープ確認も要らない（`git diff` に一切現れないため）。

**`.wikicommit/.cache/` には入れない**。あそこは再構築できる派生データ（`search_index.sqlite3`）の置き場であり、実行記録は再構築できない。Issue #319 が `schemaorg-vocab.json` をそこから出したのは、この鏡像の理由（「気軽に消してよい」という名前の含意と実際の性質のずれ）による。

代わりに諦めるもの（いずれも受け入れる）: クラウドセッションの記録は VM とともに消える（その実行の未コミット成果物も同時に消えるので整合する）、clone 先からは見えない、「このページはいつ作られたか」は**区間**としてしか答えられない — ただし上記のとおり点の時刻はそもそも存在しないので、追跡しても得られるのは区間だけだった。

### 使用場面

`wikicommit-generate` / `wikicommit-translate` / `wikicommit-synthesize` / `wikicommit-merge` の 4 つ。基準は「**途中で死んだときに、中途半端な状態と『まだ順番が来ていない』状態が区別できなくなるもの**」であり、`fix` / `remove`（単発かつ小さく差分そのものが結果）・`collect`（対話前提で人間が見ている）・読み取り専用 Skill（状態を変えないため「完走したか」を問う意味がない）は対象外。

### コマンド

```
python .wikicommit/scripts/record_run.py start --skill <skill> [--model "<model ID>"] [--arg <arg>]...
python .wikicommit/scripts/record_run.py checkpoint <run-record-path> --pass <name>
    [--token <token>] [--source <path>]
python .wikicommit/scripts/record_run.py end <run-record-path> [--source <path>]... [--page <path>]...
    [--outcome KEY=VALUE]... [--halted-reason "<reason>"]
```

`--outcome` のキーは Skill ごとに異なってよい（`merge` はページを書かないため、共通の語彙に寄せると片側で常に 0 のキーを配ることになる）。値は整数のみ。

### 記録のフォーマット（`.wikicommit/run/<YYYYMMDD>-<HHMMSS>-<skill>.md`）

```yaml
---
skill: wikicommit-generate
started_at: "2026-09-07T10:42:33+09:00"
ended_at: "2026-09-07T11:05:12+09:00"   # 空文字列なら「完走しなかった」
model: "claude-opus-5[1m]"
wikicommit_version: "0.3.0"
args: ["https://example.com/article"]
sources: [".wikicommit/source/url/example.com/article.md"]
pages: [".wikicommit/entity/ja/Place/minuma.md"]
passes:                                  # Issue #797。空リストなら「打点なし」
  - {pass: pass1-extract, at: "2026-09-07T10:44:02+09:00", token: unchecked,
     source: ".wikicommit/source/url/example.com/article.md"}
  - {pass: pass2b-type, at: "2026-09-07T10:51:37+09:00", token: ok,
     source: ".wikicommit/source/url/example.com/article.md"}
outcome: {generated: 12, failed: 1, excluded: 2}
halted_reason: ""
---
```

**本文は常に空である。** 他の `.md` 記録（`## Summary`・`## Failure Reason`・レビュー記録の散文）はいずれも frontmatter で表せないものを本文に持つが、実行記録は全項目がスカラーかリストで本文に書くことがない。JSON も検討したが**他の記録に形を揃える**方を採った。空いているから何か書く、を誘わないため、本文を持たないことをここに明記する。

**`ended_at` の空文字列が「完走しなかった」の信号である**（Issue #750 が `page_content_hash: ""` を「ページが書かれなかった」と定義したのと同じ形）。長い多段フローの末尾で終了の打刻を忘れるのは Issue #406 / #452 / #474 が繰り返し踏んだクラスだが、**ここでは直す必要がない** — 開始があって終了が無い記録は、そのまま問い 2 の答えになる。

**誤りの向きが重要である**: 打刻忘れは完走した実行を未完走として報告するだけで、逆は起こらない。偽の「未完走」は 1 回の確認で済む一方、偽の「完走」はこの記録が答えるべき唯一の問いを黙って葬る。**`end` が `--run <path>` を必須とし、同じ Skill の未完了記録を推測で閉じないのも同じ理由**である — 推測は前のセッションで本当に死んだ実行を閉じ、その信号を消す。

`end` はこのファイル唯一の read-modify-write であり、Issue #750 が意図的に避けた形である。ここで安全なのは一般化しない理由による: 実行記録は本文もコメントも持たないため YAML の round-trip で失うものが無い（`config.yml` はまさにそれでコメント記入例を丸ごと失った。Issue #713）。

### `checkpoint` — 実行の**どこまで**を残す（Issue #797）

`ended_at` が答えるのは実行**全体**の生死だけで、その内側で何が起きたかには答えない。空いていた 2 つの問いはどちらもこのリポジトリが実際に払ったコストである:

| 問い | checkpoint 以前 | checkpoint 後 |
|---|---|---|
| どこで止まったか | `ended_at` が空、としか言えない。ガード C（Issue #574）・`rules_version` 不一致（Issue #752）は**ファイルを 1 つも変えずに止まる**ため run 記録が唯一の痕跡で、その痕跡が位置を持たなかった | **最後に到達したパスが残る** |
| パスが丸ごと飛ばされたか | 検出不能。Issue #406 / #452 / #474 は同一のクラス（長い多段フローの末尾で手順が落ちる）で、**3 件とも公開済みパイロットを人が手で監査して初めて見つかった** | **打点の欠落として検出** |

3 件とも解決策は「決定論的スクリプトへの委譲」だったが、**委譲したスクリプトを呼ぶ手順そのものが落ちた場合は同じ形で再発する**。打点はその 1 段外側に立つ。

#### 照合の第三者はスクリプト自身である

Issue #752 が `rules_version` の echo 検証を成立させられたのは、サブエージェントが JSON を返し orchestrator がそれを照合するという **2 者**がいたためで、同 Issue 自身が「`wikicommit-review` はサブエージェントを使わないため echo 検証が効かない」と限界を明記している。単一エージェントでは「自分が読んだと自分に申告する」だけになり何も検証しない。

`--token` を渡すと `record_run.py` が `.claude/skills/<skill>/passes/<pass>.md` を**自分でディスクから開いて** frontmatter の `pass_token` と突き合わせる。**照合先のパスは引数で受け取らない** — 呼び出し側がファイルを指定できるなら、自分で書いたファイルを指すこともできてしまい、第三者性が消える。

| 失敗 | 検出 |
|---|---|
| パスが丸ごと飛ばされた | **打点の欠落**（`MISSING_PASS:` / `never ran`） |
| どこで止まったか | **最後の打点** |
| パスファイルを開かずに即興で実行した | **トークン不一致**（`token: mismatch`・exit 1） |
| ファイルは開いたが従わなかった | **検出不能**（`rules_version` と同じ限界。トークン行だけ grep することは防げない） |

**`--token` は SKILL.md のパス分割（進行的開示）を前提とする**が、本機能はその分割に依存しない — パスファイルが無い段階では `--token` を渡さず `--pass` だけで打点し、上表の上 2 行はそれで成立する。3 行目だけが分割後に効くようになる。

**トークンが照合できなかった場合も打点は書かれる**（`token: mismatch` / `token: missing`）うえで exit 1 を返す。書かずに落ちると「そのパスは始まってすらいない」という別の（そして誤った）話になるため。

#### 打点の粒度と、Pass 2a に打たない理由

`wikicommit-generate` の `EXPECTED_PASSES` は `pass1-extract` / `pass2b-type` / `pass2c-entities` / `pass3-generate` / `pass4-review` の 5 つで、**ソース 1 件につき 1 周**打つ（`--source` がその周回の対象を持つ）。パス単位だけにするとソース 3 件目で止まったことが分からない — パス名は繰り返し現れるので、`--source` が無いと 1 件目で死んだ実行と区別が付かない。

**Pass 2a には打たない**。Pass 1 の抽出と地続きに無条件で走り、分岐も停止経路も持たないため、そこに打点しても Pass 1 の打点が示す位置以上のことは分からない一方、ソースごとに read-modify-write が 1 回増える。

`--pass` は `EXPECTED_PASSES` に対して検証する。打ち間違いを通すと**未知のパスが 1 つ増え、同時に本物のパスが「実行されなかった」ように見える** — 1 つのミスが 2 つの誤った所見になり、しかもどちらも実際の問題ではない。

`--regenerate` の実行では期待集合が `pass1-extract` / `pass3-generate` / `pass4-review` の 3 つに狭まる（同モードは Pass 2 を実行しない。`docs/DesignDoc-pipeline.md` §6.1）。判定は記録自身の `args` を読んで行う — 呼び出し側に再申告させない。

#### read-modify-write のコスト（実測）

`end` は Issue #790 が「このファイル唯一の read-modify-write」としていたが、打点も同じ形を採るため回数が増える。**ソース 5 件 × パス 5 つ ＝ 25 回で実測 1.27 秒（1 回あたり約 51 ms）、記録ファイルは約 2.5 KB。** Issue #790 が RMW を許した根拠（実行記録は本文もコメントも持たないので YAML の round-trip で失うものが無い）は回数によらず成立し、実行時間の大半は LLM 推論であるため相対的な影響は無い。

#### 既知の限界: compaction は分割前の Pass 2 以降の打点指示を落としうる

打点忘れの誤りの向きは `ended_at` と同じで安全側である（打たなければ「実行されていない」と報告され、逆は起こらない）。ただしこれは**打点の指示がコンテキストに残っていること**に依存する — 分割前の `wikicommit-generate/SKILL.md` では Pass 2 以降の打点指示がファイル冒頭から遠く、context compaction がそれを落としたまま実行が続きうる。その場合、実際には走ったパスが `MISSING_PASS:` として報告される（偽陽性）。この非対称は SKILL.md のパスごとの分割が入るまで残る。SKILL.md 側にも同じ限界を明記してある。

**クラウドセッションでは記録が VM とともに消える**（Issue #790 が明記した代償）。そして無人実行こそ compaction をいちばん踏む経路であり、**検証手段がいちばん検証したい環境で残らない**。git 追跡対象にする案は Issue #790 が理由を挙げて退けているため蒸し返さず、代わりに `wikicommit-generate` の Completion Notice が打点の要約を 1 行出す（PR 本文経由でそこだけは残る）。

### 記録しないもの

| 除外 | 理由 |
|---|---|
| コスト・トークン数 | Issue #784 が配布物から実測課金額を落としたばかりであり、同じカテゴリ |
| ページ本文・抽出テキスト・LLM の出力 | ページ自身と管理ファイルが既に持っている |
| 個々の判断（除外理由・findings・却下した型候補） | `## Summary` と `.wikicommit/review/` の担当。ここは実行の**外形**だけを持つ |
| スクリプト単位の実行時間 | 時間の大半は LLM 推論でスクリプトの外にある。安い決定論的部分だけを測ることになる |

### ローテーション

書き込み時（`start`）に、新しい順で `KEEP_RECORDS`（50）件を残して残りを削除する。順序は `run_sort_key()` が決める — ファイル名は `<YYYYMMDD>-<HHMMSS>` で始まるので素の辞書順でもほぼ時刻順になるが、同一秒の衝突サフィックス（`...-generate-2.md`）は `-` が `.` より小さいため未サフィックスの名前より**前**に来る。素の辞書順で回すとその秒の最も新しい記録から先に消え、`check_run_records.py` が最後の 1 件を `LAST_RUN:` に採ると最も古い記録を拾う。`record_review.py` が `record_sort_key()` を書き手と読み手で共有しているのと同じ理由で、こちらも同じキーを共有する。**未完了の記録も例外にしない** — ディレクトリを有界に保つことが目的であり、末尾から落ちるほど古い実行は対処対象ではなくなっている。削除に失敗しても実行は止めない（後始末が、それが付随する実行を道連れにしてはならない）。件数で回すのは 1 ファイルが数百バイトだからで、日数の判定に時計を持ち込む必要が無い。

### 出力フォーマット

```
RUN_STARTED: .wikicommit/run/20260907-104233-generate.md (skill=wikicommit-generate, started_at=2026-09-07T10:42:33+09:00)
NOTE: pass this path back to `record_run.py end` when the run finishes.
CHECKPOINT: .wikicommit/run/20260907-104233-generate.md (pass=pass1-extract, token=unchecked, source=.wikicommit/source/url/example.com/article.md)
RUN_ENDED: .wikicommit/run/20260907-104233-generate.md (ended_at=2026-09-07T11:05:12+09:00, elapsed=22m39s)
```

### 終了コード

- `0`: 記録を開いた／打点した／閉じた
- `1`: 引数不正（未知の `--skill`・`--outcome` が整数でない・`--pass` がその Skill のパスでない）、`checkpoint`／`end` に渡されたパスが存在しない、`--token` がパスファイルの `pass_token` と一致しない（打点自体は書かれる）、frontmatter が読めない、書き込みに失敗

---

## check_run_records.py

### 目的

`record_run.py` が書いた記録を読み戻す。**消費者が同時に存在すること**が要件である（Issue #553）— 読む主体が無ければ、記録ツリーは常に空のまま残る受け皿になる。

| 行 | 答える問い |
|---|---|
| `LAST_RUN:` | 直近の実行はいつ・どの Skill・どれだけかかって・いくつのパスを踏んで・何を produce したか |
| `INCOMPLETE_RUN:` | 完走しなかった実行はどれか（`halted_reason` があれば添え、打点があれば**どこまで到達したか**も添える） |
| `MISSING_PASS:` | **完走したのに打点の無いパスがある**実行はどれか（Issue #797） |

**`MISSING_PASS:` は所見であって断定ではない** — `check_installed_type_usage.py` の `ANCESTOR_FALLBACK:` と同じ姿勢を採る。全ソースが Pass 1 でブロックされた・全件が既に最新だった、といった場合には Pass 2 以降に何もすることが無く、そこで終わるのは正常である。この行が言うのは「完走したが飛ばしたものがある」ことまでで、それ自体は不具合を意味しない。**完走していない実行はこの行に出さない** — 既に `INCOMPLETE_RUN:` が報告しており、そこには欠落の明白な理由がある。二重に出すと、片方（"finished, but"）が偽になる。

**打点を 1 つも持たない記録については、パスについて何も出力しない**。Issue #797 以前に書かれた記録は `passes` キー自体を持たず、打点しない Skill の記録は空リストを持つ — どちらも報告のしようがなく、黙っているのが唯一正直な出力である。`start` が空リストを明示的に書くのは、この 2 状態を区別するためである。

**`LAST_RUN:` は 1 件のみ**。答える問いは「いま走らせたものが何かに到達したか」であって履歴ではなく、しかも履歴はローテーションで有界であるため、長い一覧は完全な窓ではなく恣意的な窓を報告することになる。**未完了の記録は全件を列挙する** — 個別に対処できるものであり、件数はローテーションが既に抑えている。

**打刻忘れもここに出る**。これは欠陥ではなく上記の「誤りの向き」の帰結として受け入れる。

### 使用場面

- `wikicommit-status` Skill：Step 14

### コマンド

```
python .wikicommit/scripts/check_run_records.py
```

引数なし。読み取り専用で、記録を削除も更新もしない（ローテーションは書き手の担当であり、新しい記録を開く瞬間に行う — 報告する側が証拠を消してはならない）。

### 出力フォーマット

```
LAST_RUN: 2026-09-07 10:42 wikicommit-generate (22m39s, 5 pass(es), generated=12 failed=1)
INCOMPLETE_RUN: 2026-09-05 14:03 wikicommit-generate (no ended_at — halted: rules_version mismatch — reached pass2b-type; pass2c-entities, pass3-generate, pass4-review never ran)
MISSING_PASS: 2026-09-06 09:10 wikicommit-generate (finished, but pass4-review left no stamp)
SUMMARY: runs=7, incomplete=1, missing_pass=1
```

ディレクトリが無い・記録が 1 件も無い場合は `SUMMARY: runs=0, incomplete=0, missing_pass=0` と `NOTE:` を出す — 「まだ一度も実行が記録されていない」と「全部の実行が完走した」は別の状態であり、0 だけを出すと後者に見える。読めない記録は stderr に `WARNING:` を出して飛ばす（黙って落とすと、ここで唯一高めに誤るべき数である未完了件数を過少に報告することになる）。

### 既知の限界

**記録は git で追跡されないため、この報告はそのチェックアウトに限られる** — clone 先は 1 件も見えず、クラウドセッションの記録は VM とともに消える。ここが 0 であることは「このマシンに記録が無い」を意味し、「実行されていない」を意味しない。

**打点の欠落は、パスが走らなかったことの間接的な証拠にすぎない**。指示が context compaction で落ちれば、走ったパスも打点を残さない（`record_run.py` の同名の節を参照）。誤りの向きは安全側 — 本当に飛ばされたパスが「走った」と報告されることはない — だが、`MISSING_PASS:` の偽陽性は SKILL.md のパス分割が入るまで残る。

### 終了コード

- 常に `0`（報告のみ、ブロッキングしない）

---

## check_retracted_sources.py

### 目的

`status: retracted`（Issue #737）は、人間が登録済みのソースを読み、内容が信用できないと判断して以後の取り込み対象から外したことを表す。この値を書くと**そのソースが再び取り込まれることは構造的に止まる**（`add_source.py` が `RETRACTED` を返して再登録せず、`check_ingest_freshness.py` が `outdated` へ書き戻さない）が、**既にそのソースから書かれたページには何も起こらない** — それらは `sources[]` にそのソースを持ったまま、何の印も付かずに残る。本スクリプトはその穴を、**行動ではなく報告で**塞ぐ。

「報告に留める」ことは意図的な決定である（Issue #737）:

- **`review_status` を `pending` に戻す案は Issue #724 の規範と噛み合わない**。あちらは「内容が実際に変わったか」を決定論的スクリプト（`reset_review_on_content_change.py`）に委譲し、人間のレビューが要るか否かを非決定論的な判定に委ねないと明記した。取り下げでは**内容が変わらない** — 変わるのはその内容の根拠であり、同じ機構では表現できない
- **戻しても何が失われたかは伝わらない**。追跡 Issue のテンプレートは `sources` の妥当性を問わない（Issue #737 の出発点そのもの）ため、`pending` は「読み直せ」とは言うが「何を直せ」を言わない

そのページに対して既存 3 経路のどれを使うかは人間の判断であり、本スクリプトの役目はその判断材料を出すことに尽きる（Issue #713 が `/wikicommit-update` で採ったのと同じ形）: 残りのソースで作り直すなら `/wikicommit-generate --regenerate`（Issue #744 が取り下げたソースを落として作り直す挙動を入れた。残りが 1 件以上あることが条件。ただし再生成モードは `sources[].type: manual` を 1 件でも持つページを除外する一方、この「残り件数」は `manual` エントリを 1 件として数えるため、残りが `manual` のみのページは `/wikicommit-fix` に回る）、記述を手で直すなら `/wikicommit-fix`、ページごと下ろすなら `/wikicommit-remove`。**所見に添える「残りのソース件数」がこの選択を決める数**である。

### 使用場面

- `wikicommit-status` Skill：Step 12

### コマンド

```
python .wikicommit/scripts/check_retracted_sources.py
```

引数なし。`.wikicommit/source/` と、`.wikicommit/entity/` + `.wikicommit/view/` の全体を対象とする。

### 処理フロー

1. `.wikicommit/source/**/*.md` を走査し、`status: retracted` な管理ファイルの `source.path` / `source.url` を「取り下げられた識別子 → 管理ファイルのパス」の対応表にする。**識別子をキーにするのは、それが `add_source.py` の同一性判定（Issue #572 / #573）が使うキーであり、かつページの `sources[]` エントリが持つ値そのものだからである** — 導出された管理ファイル名をキーにすると、旧命名規則で作られた管理ファイル（自動移行しない）を取りこぼす
2. 取り下げが 1 件も無ければ `SUMMARY: retracted_sources=0, affected_pages=0` を出して即座に終了する。この 0 を「該当ページ 0 件」と区別できるよう、両方の数を出す — 何も取り下げていない Wiki と、取り下げたが影響ページが無い Wiki は別の状態である
3. `.wikicommit/entity/` と `.wikicommit/view/` の全ページ（`index.md`・`status: removed` を除く）の `sources[]` を読み、上記の識別子に一致するものを `RETRACTED_SOURCE:` として報告する。行には**そのページに残っている他のソースの件数**を添える — 何をすべきか（残りで作り直せるか、ページごと下ろすほかないか）を決めるのはこの数である

### view ツリーの扱い

走査対象に**含める**が、view ページは `sources[]` を持たず `derived_from` のみを持つため、直接一致することはない。それでも除外しないのは、走査の対象と所見の有無が別の話であり、除外すると「view ページは見ていない」という事実が読む側から消えるためである。

**間接的な影響（取り下げられたソースに立つ entity ページを grounding にしている view ページ）は本スクリプトの対象外**とする。`derived_from` を辿るのは `check_derivation_freshness.py` の役目であり、そちらは grounding ページが実際に書き換えられた時点で発火する。

### 出力フォーマット

```
RETRACTED_SOURCE: .wikicommit/entity/ja/Place/minuma.md: sources[] still names https://example.com/listing (retracted in .wikicommit/source/url/example.com/listing.md); 2 other source(s) remain on this page
page: .wikicommit/entity/ja/Place/minuma.md
SUMMARY: retracted_sources=1, affected_pages=1
```

該当なしの場合:

```
SUMMARY: retracted_sources=0, affected_pages=0
```

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）

---

## check_actions_pr_permission.py

### 目的

"Allow GitHub Actions to create and approve pull requests"（Settings → Actions → General → Workflow permissions）リポジトリ設定が有効かを確認する。`review-issue-close-sync.yml`（Issue #313）の `Commit and open PR` ステップはこの設定に依存しており、無効なまま放置されると自動マージが失敗する（Issue #403）。`wikicommit-init` はこの設定をベストエフォートで自動有効化しようと試みるが、その試行が失敗しても通常の操作では痕跡が残らない — 失敗が顕在化するのはレビュー追跡Issueをcloseした数日後、しかもGitHub Actionsのログの中という運用者・読者どちらの目にも普段触れない場所でしかない（Issue #478）。本スクリプトは `wikicommit-status` の定期実行のたびにこの設定を再確認することで、ドリフトを事故ではなく能動的に検知できるようにする。

`.wikicommit/scripts/` の中で唯一 `gh` を呼ぶスクリプトである（他の全スクリプトは `.wikicommit/` 配下のファイルシステム走査のみ）。

### 使用場面

- `wikicommit-status` Skill：Step 4（他の6スクリプトとは異なり、ページ単位の集計ではなく単一のリポジトリ設定確認）

### コマンド

```
python .wikicommit/scripts/check_actions_pr_permission.py
```

引数なし。

### 処理フロー

1. `.github/workflows/review-issue-close-sync.yml` が存在しなければ、この設定を必要としないリポジトリと判断し `OK`（`SUMMARY: enabled=n/a`）で即終了する
2. `gh auth status` が失敗する場合、設定を確認できない旨を `WARNING`（`SUMMARY: enabled=unknown`）として出力する（沈黙させない — 「検知できないこと」自体が Issue #478 の問題であるため、確認不能をサイレントスキップすると同じ穴を繰り返すことになる）
3. `gh repo view --json nameWithOwner -q .nameWithOwner` でリポジトリを特定できない場合も同様に `WARNING`（`SUMMARY: enabled=unknown`）
4. `gh api repos/{owner}/{repo}/actions/permissions/workflow` を呼び出す。呼び出し自体が失敗した場合（権限不足等）も `WARNING`（`SUMMARY: enabled=unknown`）
5. レスポンスJSONが解析できない場合も `WARNING`（`SUMMARY: enabled=unknown` — レスポンスの中身を確認できない以上、真偽いずれかを断定しない）
6. 解析できた場合、`can_approve_pull_request_reviews` が `true` なら `OK`（`SUMMARY: enabled=true`）。`false` なら `WARNING`（`SUMMARY: enabled=false`）とし、有効化コマンド（`gh api -X PUT repos/{owner}/{repo}/actions/permissions/workflow -F can_approve_pull_request_reviews=true -f default_workflow_permissions=<同レスポンスの値をそのまま再送>`）をメッセージに含める

**読み取り専用**（`wikicommit-init` の Step 3 と異なり、この設定を自動修復しない）: `wikicommit-status` は定期ヘルスチェックであり、ユーザーの目に触れないままリポジトリ設定を書き換えるのは踏み込みすぎと判断した。有効化コマンド自体は `wikicommit-init` Step 3 と同じ `gh api -X PUT ...` をそのまま提示する。

### 出力フォーマット

```
OK: acme/example-wiki: "Allow GitHub Actions to create and approve pull requests" is enabled
SUMMARY: enabled=true
```

```
WARNING: acme/example-wiki: "Allow GitHub Actions to create and approve pull requests" is disabled, so review-issue-close-sync.yml cannot auto-merge after a review tracking Issue is closed (Issue #403). Enable it with: gh api -X PUT repos/acme/example-wiki/actions/permissions/workflow -F can_approve_pull_request_reviews=true -f default_workflow_permissions=write
SUMMARY: enabled=false
```

```
OK: review-issue-close-sync.yml is not present, so this check does not apply
SUMMARY: enabled=n/a
```

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）

---

## check_property_wikilink_reinforcement.py

### 目的

Issue #523 は `BlogPosting.md`/`NewsArticle.md` の `publisher`（`author` と同一の Entity-only 分類だが補強なし）という非対称性を `check_schema_org_type.py --show-range` による手動照合で発見・修正し、同じ照合を他の標準型テンプレートに広げたところ `Organization.md` の `foundingLocation`・`Person.md` の `affiliation`・`Place.md` の `containedInPlace`・`Event.md` の `organizer`/`performer` にも同型の非対称性が見つかった（`docs/DesignDoc-skills.md` §11.6 Pass 3「Property-value WikiLinks」の該当コールアウト参照）。この照合は一度限りの手動監査であり、`--show-range` は「型テンプレートが property を名指しで補強しているか」と「その property の RANGE 分類」を機械的に突き合わせられるだけの情報を既に持っていたにもかかわらず、これを自動化するスクリプトが存在しなかった。本スクリプトはこの照合を自動化する（Issue #539）。

「補強」の定義は Issue #523 が実際に適用した2つの形をそのまま踏襲する: (1) `wikicommit.granularity` のプローズに、property 名を単語境界付きで言及し**かつリンク化を指し示す**（property 名を取り除いた残りに `[[` または `link` を含む。大文字小文字を区別しないため `WikiLink`・`linked` も該当する。property 名自体を手掛かりに数えないのは、`originalMediaLink` のように名前に `link` を含む property が自分の名前だけで条件を満たしてしまうのを防ぐため）箇条書きがある、または (2) `properties:` のプレースホルダー値（文字列またはリストの要素）に `[[...]]` という WikiLink トークンが既に含まれている。いずれも持たない Entity-only/Mixed な property を `UNREINFORCED` として報告する。

> **言及だけでは補強とみなさない（Issue #650）**: (1) は当初 property 名への言及のみを条件としていたが、正規表現は文脈を見ないため、**その property を否定する散文でも補強と判定されていた**。Issue #550 では `HowTo` の境界ルールの末尾「…the service, tool, or concept they operate on」が `HowTo.tool` を、Issue #551 では「`tool` と `supply` は物理的な手順向けで空になることが多い。書かずに置け」という箇条書きが `HowTo.tool` と `HowTo.supply` を、それぞれ報告から消していた。1件目は言い換えで解消できたが、2件目はその2つの property を名指しすることが箇条書きの目的そのものであるため言い換えができない — 散文が property に言及する必要がある限り、言及のみを条件とする判定では避けられない誤判定である。
>
> **この誤判定を消しても、判定は肯定・否定を見分けられるようにはならない**。「`tool` の値はリンクにするな」と書けば依然として補強と判定される（正規表現に文脈は解けない。Issue #550 / #551 が「既知の衝突パターンの機械的検査」を採らなかったのと同じ限界）。本 Issue が縮めたのは誤判定の範囲であって、種類ではない。取りこぼす側の劣化（リンク化を促す意図の箇条書きが `[[`・`link` のどちらも含まない言い回しで書かれていた場合、`UNREINFORCED` として報告される）は、非ブロッキングな気づきが1行増えるだけであり安全側に倒れている。
>
> Issue #523 が実際に書いた補強はすべてこの条件を満たすため、既存の配布テンプレートには回帰が無い（`HowTo.tool` / `HowTo.supply` の2件が報告に戻り、他は変化しない）。

ブロッキングにはしない — `wikicommit-generate` Pass 3 の一律ルール（`docs/DesignDoc-skills.md` §11.6）が、テンプレートの補強の有無に関わらずすべての Entity-only/Mixed property に同じ WikiLink 判断を適用するため、本スクリプトの検出結果は「何かが壊れている証拠」ではなく、あくまで人間向けの気づきの提供に留まる。`description` はほぼ全ての型で Mixed 分類（`TextObject`）になるため、このwikiの慣習（`docs/DesignDoc-data.md` §4.1 — `properties.description` は2〜3文の要約に留め、WikiLink化を想定しない）と関わらず、実質的にほぼ常に `UNREINFORCED` として現れる — これは想定されたノイズであり、追いかけるべき不具合ではない。

カスタム型（`type:` が `schema:custom/` プレフィックスを持つ）は Schema.org 語彙に存在しないため対象外（`check_schema_coverage.py` と同じ除外方針）。`default.md` は `type:` を持たないため自然に除外される。

### 使用場面

- `wikicommit-status` Skill：Step 5（他の6スクリプトとは異なり、`.wikicommit/entity/` のページ単位ではなく `.wikicommit/schema/` の型テンプレート単位のチェック）

### コマンド

```
python .wikicommit/scripts/check_property_wikilink_reinforcement.py
```

引数なし。常に `.wikicommit/schema/**/*.md` 全体を対象とする。

### 処理フロー

1. `.wikicommit/schema/**/*.md` を走査する
2. 各ファイルの `type:` が `schema:` プレフィックスを持ち、かつ `custom/` で始まらない場合のみ対象とする（それ以外はスキップ）
3. `properties:` が dict であることを確認し（そうでなければこのファイルはスキップする）、`wikicommit.granularity` から検査に使える箇条書き（文字列のもの）を集める。文字列でない箇条書き・リストでない `granularity` は WARNING を出した上で対象外にする（`granularity_strings()`。Issue #649。下記コールアウト参照。WARNING は `properties:` を持つファイルにのみ出る — この WARNING の役目は直後の `UNREINFORCED:` が誤検出であることを説明することであり、`properties:` が無ければ説明すべき所見自体が生まれない）
4. `properties:` の各キーについて、`check_schema_org_type.py --show-range` と同じ RANGE 分類ロジック（`_schemaorg_vocab.py` の `entity_range_candidates()`）でエンティティ型候補を取得する。語彙に存在しない、またはエンティティ型候補が空（DataType-only、または `rangeIncludes` 自体が未宣言）の場合はスキップする
5. 残ったキー（Entity-only/Mixed）について、上記の「補強」定義（`granularity` 言及または `properties:` 値中の `[[...]]` トークン）を満たすか確認する
6. 満たさない場合、`UNREINFORCED:` として報告する

> **コロンを含む `granularity` 箇条書きは検査から外れる — 黙って外さない（Issue #649）**: クォートされていない YAML リスト項目にトップレベルの `key: value` 形状が現れると、YAML はそれをスカラーではなく単一キーのマッピングとして読む。`is_reinforced()` はプローズを走査する以上、文字列でない箇条書きを扱えない。問題はそこではなく、**扱えないことが出力に現れなかった**ことにある — 型テンプレートの著者が property 名をその箇条書きの中で補強していても、コロンを含んでいたというだけで補強が無かったことになり、`UNREINFORCED` の誤検出になる。しかも報告を見た人間がテンプレートを読むと補強は確かに書いてあるため、スクリプトの誤りではなく人間の見落としに見える。
>
> **箇条書きをマッピングから文字列に復元して検査する案（Issue #649 の対応方針 2）は採らない**。コロンを含む箇条書きは `granularity` を読むあらゆる消費者にとっての落とし穴であり、直すべき場所は型スキーマファイル自身である。ここで復元すると、直すべき形そのものを隠してしまう。
>
> **`.wikicommit/schema/` に置かれるファイルの出所は3系統あり、CI が守れるのは1つだけ**: 配布テンプレートは `tests/test_schema_template_boundary_rules.py` が「全 `granularity` 箇条書きが文字列としてパースされること」を強制する（Issue #550）。一方、`wikicommit-generate` Pass 2b / `wikicommit-schema-propose` が実行時に書いた型ファイルと、人間が直接手書きした型ファイル（`provenance: manual`）はそのテストの射程外にある。そのため予防は**書く側**にも置き、`granularity` を書く4経路すべて（`wikicommit-init` の型提案・`wikicommit-collect` の Type Proposal・`wikicommit-generate` Pass 2b・`wikicommit-schema-propose`）の SKILL.md が「箇条書きは文字列としてパースされる形で書く（`Boundary — …`。`Boundary: …` は不可、`#` も不可）」を明記する。**既存の利用者リポジトリへの遡及対応は行わない**（本ドキュメント群で繰り返し採っている「新旧混在を許容する」方針）— 既にコロンで書かれた箇条書きは、この WARNING を見た人間が `.wikicommit/schema/` を直接編集するまで残る。

### 出力フォーマット

```
UNREINFORCED: Organization.foundingLocation (.wikicommit/schema/Organization.md) — range includes linkable entity type(s): Place. No granularity line points toward linking it, and no [[Type/slug]] placeholder in properties:.
SUMMARY: unreinforced=1
```

該当なしの場合:

```
SUMMARY: unreinforced=0
```

検査対象から外れた `granularity` 箇条書きがある場合（Issue #649。`UNREINFORCED:` の直前に出るため、誤検出であることがその場で読み取れる）:

```
WARNING: .wikicommit/schema/Person.md: wikicommit.granularity[0] parsed as dict rather than a string (a colon inside the bullet was probably read as a YAML mapping). That bullet is excluded from the check, so a property reinforced there can be reported as UNREINFORCED. Replace the colon separator with an em dash (—)
UNREINFORCED: Person.affiliation (.wikicommit/schema/Person.md) — range includes linkable entity type(s): Organization. No granularity line points toward linking it, and no [[Type/slug]] placeholder in properties:.
SUMMARY: unreinforced=1
```

Schema.org 語彙の取得に失敗した場合（ネットワーク不通・キャッシュ未生成等。`validate_frontmatter.py` の `properties:` 検証と同じ理由でブロッキングにしない）:

```
WARNING: the Schema.org vocabulary could not be loaded, so this check was skipped: <error>
SUMMARY: unreinforced=0
```

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）

---

## check_recurring_characters.py

### 目的

`ShortStory.md` / `Book.md` の `granularity` は「独立ページに値する登場人物は `[[Person/slug]]` でリンクし、それ以外はプレーンテキストで列挙する」と指示するが、**一度下したその判断を後から見直す仕組みが無い**。昇格されなかった登場人物は、その人物が登場するすべての作品ページで裸の文字列のまま残り続ける。

この取りこぼしは既存のどのチェックにも掛からない。`check_wanted_pages.py` は `[[Type/slug]]` 形式の WikiLink しか読まないため、プレーンテキストの名前は wanted page として計上すらされない（Issue #318 が明記した「WikiLink 構文が一度も使われていない言及は対象外」という限界が、`properties:` の値についても同じように効く）。`check_orphans.py` は既に存在するページへの被リンクの話であって無関係。結果として `wikicommit/decameron-wiki` は健全な数字を返し続け、その裏で 4 話の主人公である Calandrino が「Calandrino」という同一のプレーンテキストとして 4 回独立に列挙されるだけで、ページを 1 つも持っていなかった（Issue #560）。

本スクリプトが出す所見は `RECURRING` の 1 種類のみ — 同じ名前が 2 件以上の作品にプレーンテキストで現れ、どの言語にも `Person` ページが無い場合。ページを作る（または「この人物はプレーンテキストのままにする」と一度決める）ことを促す。作品をまたぐ再登場は、単一の作品からは得られない「この人物は 1 つの筋書きを超えて存在する」という証拠そのものである。

**既に `Person` ページがある名前は本スクリプトの担当ではない** — 書くべきページは無く、値を WikiLink にすればよいだけ（Issue #496）であり、要求される行動が正反対だからである。こちらは `check_unlinked_entity_mentions.py`（Issue #561）が `character` に限らずエンティティ型を range に持つ全ての `properties:` キーについて報告する。本スクリプトもページの存在は読むが、それは昇格候補の一覧からその名前を外すためだけに使う。

**軸の限定**: 本スクリプトが扱えるのは Issue #560 の言う軸 B（作品をまたぐ再登場）だけである。軸 A（1 作品にしか登場しないが、その作品が丸ごとその人物についての話である主人公）は 1 ページにしか現れないため、横断集計では原理的に検出できない — こちらは生成時に `Person.md` の `granularity` が下す判断であり、事後のチェックの担当ではない。

### 使用場面

- `wikicommit-status` Skill：Step 7

### コマンド

```
python .wikicommit/scripts/check_recurring_characters.py
```

引数なし。常に `.wikicommit/entity/` 配下の全 `.md`（`assets/` と `index.md` を除く）を対象とする。

### 処理フロー

1. 対象ページの frontmatter を読む。`status: removed` のページは対象外（既存の除外方針と同じ）
2. `PERSON_VALUED_PROPERTIES`（現状 `character` のみ）の下の文字列値を集める。値が `[[Type/slug]]` 形式そのものである場合はスキップする（ルールが求めている状態そのものであるため）。定数を増やしてよいのは「プレーンテキストのままであることが正規の結果でもある」という同じ性質を持つキーに限る
3. あわせて、`Person` 型のページについて `title` と `aliases` の各値を正規化したものから `Person/<slug>` への索引を作る（言語を問わない。slug は言語中立であるため、どの言語のページでもその名前に答えられる）。`aliases` も索引に含めるのは、`title` だけで突き合わせると「よりフォーマルな形でページ化されている」人物（`Person/ser-ciappelletto`・title `"Ser Ciappelletto"` に対して、作品側はプレーンテキストの `Ciappelletto`）が `RECURRING` として報告され、既にページがある人物について「ページを作れ」と促してしまうため — `check_wanted_pages.py` の `TYPE_MISMATCH`（Issue #563）が防いでいるのと同じ種類の重複であり、しかも title が異なるため `check_orphans.py` の重複ページ判定にも掛からない
4. 名前の突き合わせは NFKC 正規化 + casefold + 連続空白の単一化で行う（`check_orphans.py` が重複ページ判定でタイトルに適用しているものと同じ正規化）
5. 作品の同一性は**ファイルパスではなく `<Type>/<slug>`** で数える。1 つの物語の it/en/ja 版は 1 件であり、そうしないと多言語 Wiki は登場人物全員を「再登場」として報告してしまう
6. `Person` ページがある名前は除外し、無く 2 件以上の作品に現れる名前を `RECURRING` として報告する

### 既知の限界

- **同名の別人を区別しない**。名前とページの突き合わせは正規化した `title`／`aliases` の一致で行うため、無関係な同名人物は 1 人として読まれる。警告のみの出力であり、`check_wanted_pages.py` が自身の限界について採っているのと同じ許容度とする
- **軸 A は検出しない**（上記）
- **既にページがある名前は検出しない**（上記。`check_unlinked_entity_mentions.py` の担当）
- **再登場の計数はプレーンテキストで書かれた作品しか数えない**。ページがまだ無い人物について、ある作品が既に `[[Person/slug]]` と書いている場合、その作品は閾値に算入されない（リンク 1 件 + プレーンテキスト 1 件では何も報告されない）。両者を突き合わせるにはプレーンテキストの名前から slug を導く必要があるが、slug の決定規則（英語識別子・種別に応じた英訳／原綴り／ローマ字。Issue #193）は逆算できるものではないため行わない。宙に浮いたリンク自体は `check_wanted_pages.py` の所見であり、`Person` ページが作られた時点でプレーンテキスト側は `check_unlinked_entity_mentions.py` が拾う

### 出力フォーマット

```
RECURRING: "Calandrino" appears as plain text in 4 work(s) but has no Person page (ShortStory/calandrino-and-niccolosa, ShortStory/calandrino-and-the-heliotrope, ...)
SUMMARY: recurring=1
```

該当なしの場合:

```
SUMMARY: recurring=0
```

`page:` 行は出力しない（所見の単位がページではなく人物名であり、各所見の行が該当作品を自分で列挙するため。`check_schema_coverage.py` の `UNCOVERED:` と同じ扱い）。

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）

---

## check_unlinked_entity_mentions.py

### 目的

`check_wanted_pages.py` の鏡像。あちらが「リンクはあるが実体がない」を検出するのに対し、本スクリプトは**「実体はあるがリンクされていない」**を検出する（Issue #561）。

Pass 3 は `properties:` の値を WikiLink にするかどうかを Schema.org の RANGE 分類のみで決め（Issue #496）、その指示は「参照先ページが未作成であることを理由に WikiLink を諦めるな」と**名指しで**述べている。それにもかかわらず `wikicommit/decameron-wiki` の `Book/decameron.md` は、`character` に並ぶ 10 人の語り手のうち、**同じ ingest で先にページが書かれた 8 人だけが WikiLink 化され、後の ingest でページが作られた 2 人がプレーンテキストのまま**になっていた。同一 property・同一値リスト・同一型・同一の資格で、分かれ目は取り込み順序だけである。

しかも自然には回復しない。`action: update` はそのページ自身を対象とするソースが再 ingest されたときにしか起きないため、後から `Person/filostrato` を作った ingest には Book ページを見直す理由が無い。既存のチェックにも掛からない — `check_wikilinks.py` は書かれた WikiLink しか見ず、`check_orphans.py` は参照先ページが他ページから被リンクを持つ場合（実際に持っていた）に取りこぼす。

対象は `properties:` の値に限り、本文の地の文は扱わない。地の文についての Issue #318 の限界はそのまま残る — 一方 `properties:` の値は定義上「短く構造化された値」（Issue #495）であり、これが既存ページとの機械的な突き合わせを成立させている。

### 使用場面

- `wikicommit-status` Skill：Step 8

### コマンド

```
python .wikicommit/scripts/check_unlinked_entity_mentions.py
```

引数なし。常に `.wikicommit/entity/` 配下の全 `.md`（`assets/` と `index.md` を除く）を対象とする。

### 処理フロー

1. `_schemaorg_vocab.py` の `load_or_build_index()` で Schema.org 語彙を読む。取得できない場合は WARNING を 1 行出して `SUMMARY: unlinked=0` で終了する（`check_property_wikilink_reinforcement.py`・`validate_frontmatter.py` の `properties:` 検証と同じ非ブロッキングな劣化）
2. 全ページの frontmatter を読み（`status: removed` は対象外）、正規化した `title`・`aliases` の各値・`slug` から `(型, slug)` への索引を作る。`slug` も索引に含めるのは、英語で書かれた Wiki では値と slug が一致しうるため（他言語では値は Wiki の言語で書かれ、slug は言語中立な英語識別子であるため〈Issue #193〉一致しないのが普通）
3. 各ページの `properties:` の各キーについて `entity_range_candidates()`（`check_schema_org_type.py --show-range` と同じロジック）を引き、エンティティ型候補が空なら飛ばす（DataType のみ ＝ プレーンテキストが正しい形）。語彙に無いキーも飛ばす（`validate_frontmatter.py` の関心事）
4. 値のうち WikiLink を含まないプレーン文字列を正規化して索引を引く
5. **型も一致することを要求する** — 見つかったページの型が、その property のエンティティ型候補そのものか、その下位型（`ancestors()` で判定）でなければ一致とみなさない。`genre: "Comedy"` が `Person/comedy` で答えられてしまうのを防ぐ
6. 自ページ自身への一致は除外し、残りを `UNLINKED` として報告する

### 修正の経路

`/wikicommit-fix <page-path> "<instruction>"` で参照元ページを個別に直す。**機械的な一括置換のスクリプトは用意しない**（Issue #561 の対応方針 4 に対する判断）: 値がページのタイトルと一致することは根拠であって証明ではなく（同名の別主体がありうる）、`properties:` への自動書き込みをヘルスチェックの責務に含めるべきでもない。既存の公開済みパイロットリポジトリへの遡及修正も行わない（同 5。運用者が `wikicommit-fix` で個別対応する）。

### 既知の限界

- **同名の別主体を区別しない**。突き合わせは正規化した `title`／`aliases`／`slug` の一致で行うため、無関係な同名の主体は 1 つとして読まれる。型の一致も要求するため精度は上がるが、なくなりはしない。警告のみの出力であり、`check_wanted_pages.py` が自身の限界について採っているのと同じ許容度とする
- **カスタム型は参照先になれない**。`schema:custom/` プレフィックスを持つ型は Schema.org 語彙に存在しないため、その型が property の range を満たすかを判定する手段が無い。一方、**参照元としては通常どおり走査する** — range 分類は property 名だけで決まり参照元ページ自身の型を一切参照しないため、`custom/Tale` の `character` は `ShortStory` の `character` と全く同じに判定される（`validate_frontmatter.py`・`check_property_wikilink_reinforcement.py` はカスタム型を丸ごとスキップするが、あちらが検証するのはキーが**その型の** `domainIncludes` に属するかであり、まさにその部分がカスタム型では答えられない。本スクリプトはそこを見ない）。カスタム型の `properties:` キーは機械検証を受けないため独自の名前がありうるが、語彙に無いキーは他の未知の property と同じく単に飛ばされる
- **本文の地の文は対象外**（上記。Issue #318 の限界）

### 出力フォーマット

```
UNLINKED: .wikicommit/entity/it/Book/decameron.md: properties.character "Filostrato" exists as Person/filostrato but is not written as a WikiLink
page: .wikicommit/entity/it/Book/decameron.md
SUMMARY: unlinked=1
```

該当なしの場合:

```
SUMMARY: unlinked=0
```

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）

---

## check_installed_type_usage.py

### 目的

`check_schema_coverage.py` の対。あちらが「使われている `type:` にスキーマファイルが無い」を検出するのに対し、本スクリプトは**「スキーマファイルが在るのにページが無い」**を検出する（Issue #565）。

`wikicommit/saitama-city-wiki` は `Park.md`・`Museum.md` を人間の承認を経てインストールしていたにもかかわらず、公園 7 件・博物館 2 件を素の `Place` として生成していた — しかも**型ファイルを追加したのと同じバッチ**で（型リストが古かったのではない）。その間 `check_schema_coverage.py` は 0 件を報告し続けた。`Place` にはスキーマファイルがあるためである。

原因は手違いではなく構造にある。Schema.org 上 `Park`・`Museum` は `Place` の子孫型なので、公園を `Place` として書くことは**誤りではなく、粒度が粗いだけ**である。そして祖先型は常に利用可能で、常により馴染みがあり、常に技術的に正しい。Issue #447 が `DefinedTerm` について発見したのと同じ力学が、型を**提案する**段（Pass 2b。#447 の対象）ではなく、インストール済みの型を**選ぶ**段（Pass 2c）で働いている。

2 種類の所見を出す。強度が意図的に異なる。

| 所見 | 条件 | 読み方 |
|---|---|---|
| `UNUSED` | 型ファイルがあるのにページが 0 件 | 型の判断自体が誤っていたか、生成がその型に手を伸ばしていないか。`provenance: default` の型は対象外 — Wiki の主題に関わらず一律配布されるため、0 件であること自体に情報が無い。`provenance` が**無い**ファイルはその機能追加（Issue #519）より前に作られたことを意味するため、`config.yml` の `schema.base_types` が代わりの判断材料になる（そうしないと、それ以前に初期化された Wiki は配布された基本型を丸ごと報告してしまう） |
| `ANCESTOR_FALLBACK` | ある型にページがあり、その子孫型もインストール済み | **示唆であって断定ではない**。`Park.md` を持つ Wiki にも公園でない `Place` ページは当然ある。「見る価値がある」程度に読む |

いずれもブロッキングではない。どの型がその主題に合うかは判断であり、本スクリプトにそれを下す手段は無い — 粗くなっているかもしれない場所を指すことしかできない。

**既存ページの型の再分類は本スクリプト（および Issue #565）のスコープ外**である（Issue #447 も同じ判断をしている）。型変更はディレクトリ移動と、そのページを指す全 WikiLink の Type セグメント書き換えを伴う（`docs/DesignDoc-data.md` §5.5）。本チェックの目的は、次のバッチが正しい粒度で生成されるよう早期にパターンを捕まえることにある。

### 使用場面

- `wikicommit-status` Skill：Step 9

### コマンド

```
python .wikicommit/scripts/check_installed_type_usage.py
```

引数なし。`.wikicommit/schema/` と `.wikicommit/entity/` の全体を対象とする。

### 処理フロー

1. `.wikicommit/schema/` が無ければ即座に `SUMMARY: unused=0, ancestor_fallback=0` で終了する。Schema.org 語彙が取得できない場合も WARNING を 1 行出して同じく終了する（`check_property_wikilink_reinforcement.py` と同じ非ブロッキングな劣化）
2. `installed_standard_types()`（`_schemaorg_vocab.py`）でインストール済みの標準型を集める。**ファイル名ではなく `type:` を読む** — 型を解決するのはファイル名ではなくパス導出であり（§5.1）、両者が食い違うファイルは宣言されている方に数えるべきであるため。カスタム型（`schema:custom/`）は語彙に存在せず継承チェーンに置けないため対象外
3. `.wikicommit/entity/` の全ページ（`index.md`・`status: removed` を除く）を `type:` 別に数える。言語は問わない
4. ページ 0 件の型のうち、`provenance: default` でも「`provenance` が無く、かつ `config.yml` の `schema.base_types` に含まれる」でもないものを `UNUSED` として報告する。`config.yml` が読めない場合は空集合として扱う — 古いリポジトリで `UNUSED` の行が数本増えるだけで済み、報告としては安全な側に倒れる
5. ページが 1 件以上ある型について `installed_descendants()` を引き、インストール済みの子孫型があれば `ANCESTOR_FALLBACK` として報告する（`Park` が `CivicStructure` 経由で `Place` の子孫であるような間接的な関係も含む）

`UNUSED` と `ANCESTOR_FALLBACK` は排他である（ページ 0 件の型が何かの上に乗っていることはありえない）。

### 出力フォーマット

```
UNUSED: schema:Park (.wikicommit/schema/Park.md, provenance: collect) — no page uses this schema file
ANCESTOR_FALLBACK: schema:Place has 7 page(s), but the more specific schema:Museum, schema:Park is also installed (the granularity may be too coarse)
SUMMARY: unused=1, ancestor_fallback=1
```

該当なしの場合:

```
SUMMARY: unused=0, ancestor_fallback=0
```

`page:` 行は出力しない（所見の単位がページではなく型であるため。`check_schema_coverage.py` の `UNCOVERED:` と同じ扱い）。

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）

---

## check_self_referential_tags.py

### 目的

`tags` は「複数ページを横断して同じ概念で括る」ためのフィールドである（`docs/DesignDoc-data.md` §4.1・Issue #275）。ページ自身の `title` と同じタグはそのページ自身としか括れず、`type` と同じタグは `type:` フィールドが既に述べていることの繰り返しになる。どちらも Issue #275 が散文で明示的に禁じたが、**その後のパイロットで両方とも再発した**（`Place/minuma-tanbo.md` の `tags: [見沼田んぼ, ...]`、`Place/saitama-shintoshin.md` の `tags: [さいたま新都心, ...]`、および型と実質重複するカテゴリタグ 5 件）。

生成時の指示だけに依存し**検出手段が無い**ルールは drift する。`check_property_wikilink_reinforcement.py`（Issue #539）が「一度限りの手動監査を自動化する」のと同じ位置づけである。

### 使用場面

- `wikicommit-status` Skill：Step 10

### コマンド

```
python .wikicommit/scripts/check_self_referential_tags.py
```

引数なし。`.wikicommit/entity/` 配下の全 `.md`（`assets/`・`index.md`・`status: removed` を除く）を対象とする。

### 処理フロー

1. 各ページの `tags` を読む（リストでなければスキップ）
2. `title` と一致するタグを `TITLE_ECHO`、`type` と一致するタグを `TYPE_ECHO` として報告する（`TITLE_ECHO` が優先 — 自分の型と同じ題のページを二重に報告しない）
3. `type` の照合対象は「型名（`custom/Decision`）」「その末尾セグメント（`Decision`）」「`type:` の値そのもの（`schema:custom/Decision`）」の 3 形と、それぞれの**語分割形**。語分割は大文字境界・ハイフン・アンダースコア・空白で行うため、`GovernmentService`・`government-service`・`government service` は同じ型の 3 通りの綴りとして一致する（大文字境界の分割は `(?<=[a-z0-9])(?=[A-Z])` に限定し、`HTMLPage` のような頭字語の連続は分割しない）

### 照合は正規化後の完全一致に限る

NFKC・casefold・連続空白の単一化を経た**完全一致**のみを見て、部分一致は見ない。タイトルの一部を含むだけのタグは、たいてい有用な方だからである — `見沼田んぼ` というページの `見沼` タグはその地域の他のページと括るためのものであり、まさに tags の目的そのものである。これを報告すると、このチェック自体が無視されるよう人を訓練してしまう。

### 既知の限界

**Wiki 自身の言語で書かれた型タグは検出しない**。`schema:Museum` のページの `博物館` タグは `museum` と同じく型の重複だが、それを見るには Schema.org 語彙の翻訳が要る — WikiCommit はそれを持たず、意図的に持たない（型名は言語中立の識別子である）。英語 Wiki は両方をカバーし、それ以外はタイトル側のみになる。

### 出力フォーマット

```
TITLE_ECHO: .wikicommit/entity/ja/Place/minuma-tanbo.md: tag "見沼田んぼ" repeats the page title (it can only group the page with itself)
page: .wikicommit/entity/ja/Place/minuma-tanbo.md
TYPE_ECHO: .wikicommit/entity/en/Person/yamada-taro.md: tag "person" repeats the page type (the type: field already says this)
page: .wikicommit/entity/en/Person/yamada-taro.md
SUMMARY: title_echo=1, type_echo=1
```

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）
