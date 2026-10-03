# スクリプト仕様書

> **バージョン**: 0.2（Draft）
> **作成日**: 2026-06-23
> **対応DesignDoc**: [DesignDoc-skills.md](DesignDoc-skills.md) §11.5
>
> このファイルは**いま何が仕様か**を書く。各判断の経緯（以前の挙動・採らなかった案・実測の記録・Issue 番号ごとの議論）は [history/DesignDoc-ScriptSpec.md](history/DesignDoc-ScriptSpec.md) の同じ見出しの下にある。

`.wikicommit/scripts/` に配置する Python スクリプトの仕様。Skills（SKILL.md）から呼ばれる共通インフラ。

---

## 共通規則

- **実行環境**: Python 3.11+
- **作業ディレクトリ**: リポジトリルート（スクリプト内パスはすべてリポジトリルートからの相対パス）
- **終了コード**: `0` = 成功・warning のみ、`1` = blocking エラーあり
- **stdout**: 構造化出力行（`ERROR:` / `WARNING:` / `OK:` / `SUMMARY:` / `ORPHAN:` / `DUPLICATE:` / `WANTED:` / `TYPE_MISMATCH:` / `STALE:` / `OUTDATED:` / `EXPIRED:` / `MISSING_SOURCE:` / `UNTRANSLATED:` / `UNCOVERED:` / `page:` 等）。Skills がパースする。
- **stderr**: スクリプト実行時の予期しないエラー（Python 例外・ファイルアクセス失敗等）
- **出力の言語**: stdout・stderr に出る文字列はすべて英語で書く。読み手は運用者とエージェントであって読者ではないため、管理ファイルの見出しと同じく固定の英語とする。コメント・docstring は日本語のまま据え置く（読み手が開発者であり `docs/` と揃う）。公開ページに出る読者向けラベル（`convert_wikilinks.py` の `ROOT_INDEX_LABELS` / `OVERVIEW_LABELS` / `SOURCE_*_LABELS`）はこの規則の対象外で、`primary_lang` で切り替わる。`tools/check_script_output_language.py` が CI で blocking の回帰ガードとして走るが、`print()` の引数しか見ないため、`_frontmatter.py` のようにメッセージを戻り値として返すスクリプトは手作業で確認する

---

## `.wikicommit/entity/` の走査は `_wikilink.py` に集約する

`.wikicommit/entity/**/*.md` を走査して `assets/` と `index.md` を除く、という判断は `_wikilink.py` の 2 つの関数に集約し、各スクリプトは走査ループを自前で書かない。独立に書かれた写しは `assets/` の判定で意味論が割れやすい。とくに `"assets" in page.parts` を絶対パスに適用すると、**リポジトリの祖先ディレクトリのどれかが `assets` という名前のとき全ページがスキップされる**。この誤りはエラーにならず件数が減るだけなので気づかれない（`check_wikilinks.py` の被リンクインデックスなら、削除フロー〈`docs/DesignDoc-pipeline.md` §6.5〉が依拠する参照切れ WikiLink の警告が黙って消え、`/wikicommit-remove` → `/wikicommit-merge` は正常に完了したように見える）。

| 関数 | 役割 |
|---|---|
| `is_entity_asset(page, entity_dir)` | `page` が `entity_dir` **直下**の `assets/` 配下かを返す。判定は必ず `entity_dir` からの相対パスに対して行い、`page.parts` には触れない |
| `collect_entity_pages(entity_dir=ENTITY_DIR, *, include_index=False)` | 上記の `assets/` と `index.md` を除いた全ページを sorted で返す |

**`assets/` の意味論は最も狭い定義とする**。`docs/DesignDoc-data.md` §3.1 が `.wikicommit/entity/assets/` を全言語共通の単一の置き場と定義しており、`<lang>/assets/` のようなものは仕様上存在しない。緩い定義（配下の任意セグメント）を採ると `assets` という名前の Type やスラッグを将来禁じることになる。

**`include_index=True` を渡すのは 3 箇所**: `rebuild_index.py`（最後のページが削除された Type ディレクトリは `index.md` しか残らないため、それ自体を見つける必要がある）・`check_wikilinks.py` の被リンク走査（`rebuild_index.py` が各ページの WikiLink を index に書くため、そこへのリンクは削除対象ページへの実在する参照である）・`check_wanted_pages.py`（index も走査する。「陳腐化した index のエントリを『誰かが書いてほしいページ』と数えるべきか」は走査の集約とは別の問いであり、この引数では決めない）。

**`validate_frontmatter.py` と `check_raw_html.py` はこの関数を使わない**。この 2 本は `assets/` も `index.md` も除外せず全ファイルを検証する（前者は `index.md` の `sources` 必須を明示的に免除する分岐まで持つ）。対象は「グラフ・集計の対象となる本文ページ」ではなく「ディスク上の全 `.md`」であり、巻き込むとこのヘルパーの意味が薄まる。

**ページの同一性と WikiLink 解決も同じ理由で `_wikilink.py` に置く**。`load_primary_lang()`・`page_lang()`・`is_removed()`・`link_target_path()`・`type_slug_from_wiki_path()`・`extract_wikilinks()`、そして**フォールバックの順序そのもの**である `resolve_wikilink()` がここにある。WikiLink を解決するスクリプトはこれらを import し、フォールバックの順序を自前のループに書き直さない（`load_primary_lang()` も複製しない）。

`convert_wikilinks.py` の `is_in_assets()` は別に持つ — publish 側で `output_dir` に対しても使われる（stale cleanup・`sync_assets()`）ため、entity ツリー専用の `collect_entity_pages()` では置き換えられない。同ファイルの `generate_overview_page()` の Type 取り違え判定は共有の `other_types_for_slug()` を使う（index を引数で受け取る設計なので、`page_stats` が既に持つ `type_raw` から index を組み立てるだけで走査は増えない）。

---

## `.wikicommit/view/` を走査するかはスクリプトごとに決める

view ツリー（`.wikicommit/view/<lang>/<slug>.md`。Wiki 自身のページを根拠とする二次知識。`docs/DesignDoc-data.md` §4.5.1）は entity ツリーとは別の入力である。`_wikilink.py` が `VIEW_DIR` / `VIEW_TYPE_SEGMENT` / `VIEW_KINDS` / `parse_view_path()` / `collect_view_pages()` / `view_page_path()` を持ち、各スクリプトは走査するかどうかを 1 本ずつ決める。

| 扱い | スクリプト | 理由 |
|---|---|---|
| 含める | `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_wanted_pages.py` / `check_expires.py` / `check_translation_status.py` / `search_index.py` / `rebuild_index.py` / `convert_wikilinks.py` | view ページも読者に公開されるページであり、リンクし・検索され・索引に載り・鮮度を持つ |
| 主消費者 | `check_derivation_freshness.py` | `derived_from` を持つページの主な置き場は view ツリーである。**entity ツリーの走査も続ける** — view ツリーができる前に書かれた合成ページはそこに残る（自動移行しない） |
| 含める（所見は entity ページにしか出ない） | `check_retracted_sources.py` | view ページは `sources[]` を持たないので直接は一致しないが、走査対象から外さない — 走査の対象と所見の有無は別の話であり、除外すると「view ページは見ていない」という事実が読む側から消える |
| 除外 | `check_recurring_characters.py` / `check_unlinked_entity_mentions.py`（`properties:` 前提）・`check_schema_coverage.py` / `check_installed_type_usage.py`（`type:` 前提）・`reconcile_ingest_status.py`（`sources[].hash` 前提）・`check_orphans.py`（view ページは生まれつき被リンクゼロ） | いずれも view ページが持たないフィールドを読むか、全件が所見になる |
| 既定で除外・`--include-view` で包含 | `build_survey_view.py` | 分析をさらに分析することを避ける。着眼点が実際に grounding するのはその下の entity ページである |
| どちらも走査しない | `record_run.py`・`check_run_records.py` | 対象は `.wikicommit/run/` であり、ページを 1 枚も読まない |
| 両方を受け付ける（走査はしない） | `reset_review_on_content_change.py`・`record_review.py` | ツリーを歩かず引数のページだけを見るため上の 3 分類には当たらないが、受け付ける接頭辞は `.wikicommit/entity/` と `.wikicommit/view/` の両方である。呼び出し元の `wikicommit-fix` が両ツリーを対象に取るため、entity だけに絞るとその半分が黙って素通りする |

**除外側は `tests/test_view_tree.py` が固定している**。除外の理由はツリーの中身に依存せず常に成り立つため、後の変更が `collect_entity_pages()` を両ツリー走査に差し替えても**エラーにはならず**、対処できない所見が増えるだけになる。

---

## merge の blocking な 3 本は status が全ページに走らせる

blocking な（exit 1 を返す）ページ検査はスクリプト 4 本・所見 5 分類ある。`wikicommit-merge` は `check_orphans.py` 以外の 3 本を**変更ファイルにだけ**走らせる — 引数なしにすると、そのバッチが触れていないページの既存のエラーでバッチ全体が止まるためである。そのため、一度書かれたページに 3 本を走らせ続けるのは `/wikicommit-status` の Step 3 が担う。

| blocking な所見 | `/wikicommit-merge` | `/wikicommit-status` |
|---|---|---|
| `check_orphans.py` `DUPLICATE:` | 落ちる（唯一 unscoped で呼ばれる） | 報告される |
| `check_wikilinks.py` — Type セグメント取り違え | 素通り | `check_wanted_pages.py` の `TYPE_MISMATCH:` |
| `check_wikilinks.py` — `status: removed` ページへのリンク | 素通り | Step 3 が報告する |
| `validate_frontmatter.py` ERROR | 素通り | 同上 |
| `check_raw_html.py` ERROR | 素通り | 同上 |

下 3 行はいずれも**書かれた後に壊れうる**。`type:` と `properties:` の検証は `.wikicommit/schemaorg-vocab.json` と `.wikicommit/schema/` を参照するので、語彙を取り直したり型テンプレートを取り込んだりすれば通っていたページが ERROR になる。経路 A のページは `pending` のまま公開されるので、生 HTML が残れば公開サイトで実行されうる。削除フローの非対称設計（削除 PR は warning のみ）は、消し残った参照を後から誰かが報告することを前提にしている。

**規則**:

- **専用のスクリプトは作らない**。status の Step 3 が 3 本を呼ぶ。集約用のスクリプトは ERROR 行を拾うためだけの層になり、`check_wanted_pages.py` を広げる案は 1 カテゴリしか埋めない
- **status が拾うのは `ERROR:` 行だけ**。`check_wikilinks.py` の WARNING は未解決リンクで `WANTED:` と同じ内容であり、他の 2 本の WARNING は情報提供である。3 本すべてに `--errors-only` を足すことはしない
- **Type セグメント取り違えの二重報告は `check_wikilinks.py --skip-type-mismatch` で除く**（同スクリプトの節）。SKILL.md に文言で除外させない
- **exit 1 は status の失敗ではなく所見として扱う**。SKILL.md がそう明記する（`check_ingest_freshness.py` の副作用の注記と同じ形）
- **表示は 1 行に畳む**（`Blocking errors merge does not re-check: <N>`。1 件以上なら ERROR 行をその下に並べる）。ほぼ常に 0 の行を足す代償を抑えるため 3 行にはしない。この行は healthy 判定を止める — 実際の欠陥で、直し方が行に書いてあり、ほぼ常に 0 なので healthy に到達できなくなることはない（2026-09-29 にパイロット 2 件〈522 ページ・2,042 ページ〉へ unscoped で走らせた実測で、3 本とも ERROR 0）

**`/wikicommit-update` Step 7 の全ページ走査は残す**。配布物を取り込むときに、所見が取り込み前からあったものかどうかの判定にこの走査が要るため。

---

## スクリプト一覧

| スクリプト | 役割 | 終了コード 1 の条件 |
|---|---|---|
| `validate_frontmatter.py` | フロントマター必須フィールド・型・許可値の検証 | blocking エラーあり |
| `check_wikilinks.py` | WikiLink 参照先の存在確認・removed ページへのリンク検出・Type セグメント取り違えの検出 | blocking エラーあり |
| `check_raw_html.py` | ページ本文中の生 HTML タグ検出 | blocking エラーあり |
| `check_orphans.py` | 孤立ページ・重複ページの検出 | 重複あり |
| `check_wanted_pages.py` | 被参照だが実体のない wanted page の検出（`check_orphans.py` の対）・Type セグメント取り違えの分離 | なし（常に 0） |
| `check_expires.py` | `expires_at` 期限切れ検出 | なし（常に 0） |
| `check_translation_status.py` | 翻訳の陳腐化検出・未翻訳ページ検出 | なし（常に 0） |
| `check_derivation_freshness.py` | `wikicommit-synthesize` 出力ページ（`derived_from`）の陳腐化検出 | なし（常に 0） |
| `check_ingest_freshness.py` | ingest ハッシュずれ検出 | なし（常に 0） |
| `check_distribution_freshness.py` | インストール済み配布物とテンプレートの差分検出（古い・欠落・孤児。読み取り専用） | なし（常に 0） |
| `read_policy.py` | ポリシーファイルが実際に述べている散文方針の抽出（記入例・HTML コメントを除去。読み取り専用） | なし（常に 0） |
| `match_index_only.py` | `source-policy.md` の `index_only:`（ドメインとページの 2 形）に URL が該当するかの判定（読み取り専用） | なし（常に 0） |
| `match_existing_names.py` | Pass 2c が抽出したエンティティの名前を、既存ページの `title` / `aliases` と照合（読み取り専用） | 標準入力が JSON のリストでない（exit 2） |
| `search_index.py` | FTS5 trigram 検索インデックスの構築・クエリ（`wikicommit-search`・`wikicommit-ask` 共有） | SQLite が trigram トークナイザ非対応、または `.wikicommit/entity/` が存在しない |
| `check_schema_coverage.py` | `.wikicommit/schema/` に専用ファイルのない `type:` 値の集計（`wikicommit-generate`・`wikicommit-schema-propose`・`wikicommit-status` 共有） | なし（常に 0） |
| `check_schema_org_type.py` | Schema.org 語彙に対する型・プロパティの実在検証、型名一覧の取得と候補型の説明文の取得（2 段階）（`wikicommit-generate`・`wikicommit-schema-propose` 共有） | 型が語彙に存在しない、プロパティが型（祖先型含む）に属さない、語彙の取得・パースに失敗、または `--type`/`--list-type-names`/`--describe`/`--list-installed-hierarchy` のいずれも未指定 |
| `build_survey_view.py` | Wiki 全体を1つのコンテキストに収まる縮約ビューへ落とす（`wikicommit-synthesize` の俯瞰モードと `wikicommit-collect` の Step 3.5 が共有。`--include-view` を渡さない限り view ツリーは対象外） | なし（常に 0） |
| `build_onehop_context.py` | Pass 4 の check 8 が要る 1 ホップ近傍の組み立て（`wikicommit-generate` の Pass 4 と `--regenerate` が共有） | `--page-path` が entity / view ツリーの外を指す |
| `rebuild_index.py` | Type ディレクトリの `index.md`、および view ツリーの言語別 `index.md` を決定論的に再構築（`wikicommit-generate`・`wikicommit-translate`・`wikicommit-synthesize`・`wikicommit-organize`・`wikicommit-update` 共有） | なし（常に 0） |
| `check_extraction_quality.py` | 既知JS-shellドメイン判定（ブロッキング）・取得能力の事前チェック（ブロッキング）・抽出テキストの低情報密度判定（警告）（`wikicommit-generate`・`wikicommit-collect` 共有） | ドメインが既知不可リストに一致（`check-domain`）、必要な追加パッケージが未導入（`check-fetch-capability`）、抽出テキストが低密度（`check-density`）、または対象ファイルが読み込めない |
| `reconcile_ingest_status.py` | `status: pending` のソース管理ファイルのうち内容が既に公開ページの `sources` に使われているものを検出し `status: generated` に是正（意図して requeue されたファイルは 3 つの条件が守る） | なし（常に 0） |
| `reset_review_on_content_change.py` | 内容が書き換わった `reviewed` ページを `pending` へ戻し `reviewed_by` を落とす（`wikicommit-generate` Pass 4・`wikicommit-fix` 共有） | 引数が entity/view ツリーの外を指す、ページが存在しない、frontmatter がパースできない |
| `record_review.py` | レビュー 1 件を `.wikicommit/review/` 配下の不変ファイルとして記録（`wikicommit-generate` Pass 4・`wikicommit-review`・`wikicommit-synthesize`・`review-issue-close-sync.yml` 共有） | 引数が entity/view ツリーの外を指す、`--kind ai` に `--model` が無い、`--result` が `discarded` 以外なのにページが存在しない、JSON が壊れている、書き込みに失敗 |
| `check_review_coverage.py` | レビュー記録の集計・未レビュー／抜取候補／失効の列挙（`wikicommit-status` 専用） | なし（常に 0） |
| `record_run.py` | 実行 1 回を 1 ファイルとして記録（`start` で開き `end` で閉じる。4 つの書き込み系 Skill が共有） | 引数不正、`end` に渡されたパスが存在しない、`--outcome` の値が整数でない、frontmatter が読めない |
| `driver.py` | 多段の Skill の工程の順序を持つ（`start` / `next` / `done` / `status` / `check-merge` / `abandon`。`wikicommit-generate` と `wikicommit-merge`） | `done` が受け付けなかった（今の工程でない・確認に失敗・トークンが合わない）、`check-merge` が止めた。使い方の誤り・壊れた工程の定義は exit 2 |
| `check_run_records.py` | 直近の実行と完走しなかった実行の報告（`wikicommit-status` 専用） | なし（常に 0） |
| `check_retracted_sources.py` | 人間が取り下げたソース（`status: retracted`）を `sources[]` に持つページの検出（`wikicommit-status`）と、取り下げ済みソースの一覧（`--list`。`wikicommit-review` / `wikicommit-fix` がソースを読む前のガードに使う） | なし（常に 0） |
| `check_actions_pr_permission.py` | "Allow GitHub Actions to create and approve pull requests" リポジトリ設定の確認（`wikicommit-status` 専用） | なし（常に 0） |
| `check_recurring_characters.py` | `properties.character` にプレーンテキストで列挙された登場人物のうち、複数作品に再登場するが Person ページを持たないものの検出（`wikicommit-status` 専用） | なし（常に 0） |
| `check_self_referential_tags.py` | ページ自身の `title`／`type` を繰り返すだけのタグの検出（`wikicommit-status` 専用） | なし（常に 0） |
| `check_installed_type_usage.py` | インストール済みスキーマファイルのうちページが 0 件のもの・より具体的な子孫型がインストール済みなのに祖先型でページが書かれているものの検出（`check_schema_coverage.py` の対。`wikicommit-status` 専用） | なし（常に 0） |
| `check_unlinked_entity_mentions.py` | エンティティ型を range に持つ `properties:` キーの値が、実在するページを指すのにプレーンテキストで書かれているものの検出（`check_wanted_pages.py` の鏡像。`wikicommit-status` 専用） | なし（常に 0） |
| `check_property_wikilink_reinforcement.py` | 型テンプレートの Entity-only/Mixed な `properties:` キーのうち、WikiLink化への補強（`granularity` 言及・`[[Type/slug]]` プレースホルダー）を持たないものの検出（`wikicommit-status` 専用） | なし（常に 0） |
| `check_schema_files.py` | 書かれた型ファイル自体が動く形になっているかの検証（`wikicommit-status` 専用） | なし（常に 0） |
| `check_name_collisions.py` | 同じ名前（タイトル・別名）に答える複数ページの検出。`.wikicommit/relations.yml` で判断済みの組を外す（`wikicommit-status`・`wikicommit-relate` 共有） | なし（常に 0） |
| `check_groups.py` | `.wikicommit/groups/<Type>.yml` の検証・型ごとの未分類 / stale の件数、`--type` で未分類ページの一覧（`wikicommit-status`・`wikicommit-organize` 共有） | なし（常に 0） |
| `record_relation.py` | 人が決めたページ同士の関係を `.wikicommit/relations.yml` に 1 項目追記（`wikicommit-relate` 専用） | 引数不正・存在しないページ・ファイルがリストとして読めない（何も書かない） |
| `merge_pages.py` | 「同一」のページの統合の計画・記録・確認（`plan` / `record` / `check`。`wikicommit-generate --regenerate --merge` 専用） | 統合を許さない（判断の記録が無い・翻訳・`manual` ソース・ハッシュの食い違い等）、`check` で未完了の部分がある |
| `rewrite_merged_links.py` | `merged_into` をたどって、吸収されたページへの WikiLink を残すページへ書き換える（同上。`rename_page.py` も使う） | なし（常に 0） |
| `rename_page.py` | 系列の版の名前を年で修飾する改名（`plan` / `apply`。slug と title・翻訳・リンク・ソース管理ファイル・index を追随させる。`wikicommit-relate` 専用） | 改名を許さない（翻訳・合成ページ・`primary_lang` 以外・年の形式・新しい slug が使用済み等。何も書かない） |

---

## build_onehop_context.py

### 目的

Pass 4 の check 8（WikiLink 1 ホップ以内のページ間矛盾）は、レビューサブエージェントへ渡す追加コンテキストとして「このページが指す既存ページ」＋「このページを指すページ」を要求する。この集合を組み立てるのが本スクリプトである。

**散文の指示で LLM に抽出させない。** 完全に決定論的に判定できる操作を instruction として表現すると、実行のたびに即興の正規表現が書かれる。たとえば `\[\[([A-Za-z0-9_/]+)\]\]` は `-` を含まないため、英語のケバブケースの slug（`vibe-coding` 等）への発リンクに**完全に不一致になる**。しかもこの誤りは例外にならず、**集合が静かに縮むだけで出力は正常に見える**。

**WikiLink の抽出は `_wikilink.py` の `WIKILINK_RE` を使う**（`extract_wikilinks()`）。Type 部（PascalCase・ハイフン無し）と slug 部（`[A-Za-z0-9_-]+`・ハイフン有り）を別のクラスで扱い、同ファイルのコメントがその理由を述べている。`check_orphans.py`・`build_survey_view.py`・`check_wanted_pages.py`・`check_wikilinks.py` も同じものを使う。

**抽出だけでなく組み立て全体を受け持つ。** 3 つの skip 判定（`index.md` / `status: removed` / レビュー対象ページの翻訳）・クロス言語フォールバック・outbound 優先の dedup・5 件上限もここで決定論的に行う — これらはいずれも**集合を縮める操作**であり、同じ「静かに変わる」性質を持つ。

### 置き場所が `.wikicommit/scripts/` である理由

呼び出し元は `wikicommit-generate` だけだが、`.wikicommit/scripts/` に置く（`docs/DesignDoc-skills.md` §11.5「置き場所の判断基準」）。決め手は写しの数である — 本スクリプトが要するのは `WIKILINK_RE`・エンティティ / view 走査・`parse_wiki_path`・frontmatter 読み・クロス言語解決一式であり、Skill 内に置いて import を避けると `_wikilink.py` に集約したものの写しを作ることになる。共有側に置けば写しは 0 本で、呼び出し元が 1 Skill だけの他の共有スクリプトと同じ形に収まる。

### 使用場面

- `wikicommit-generate` Skill：Pass 4 step 1（`references/pass4-review.md`）
- `wikicommit-generate --regenerate`：同じ step（`references/regenerate.md` step 3）。再生成モードでもページのパスは変わらないため、lang / Type / slug も 1 ホップの両方向も通常生成と同一であり、**同じスクリプトを同じ形で呼ぶ**

### コマンド

```bash
python .wikicommit/scripts/build_onehop_context.py --page-path "$(cat <<'EOF'
<そのページが持つはずのリポジトリルート相対パス>
EOF
)" [--repo-root <path>] [--max-pages N] <<'PAGE'
<Pass 3 が生成したページ本文（frontmatter を含む）>
PAGE
```

**`--page-path` はそのファイルを読まない。** lang / Type / slug の識別にのみ使い、パスが存在しなくてよい。これは避けて通れない要件である — `references/pass3-generate.md` の item 6 が **"Do not write to disk yet; Pass 4 reviews first"** と定めており、書き出すのは Pass 4 step 6 であるため:

| `action` | Pass 4 時点のディスク |
|---|---|
| `create` | **存在しない** |
| `update` | **古い版がある** — 読むと、いま生成した版ではなく**前の版**の発リンクを取る |

後者が特に悪い。ページのパスを走査して本文を読む実装にすると、**本スクリプトが直そうとしているのと同じ「静かに違う集合を返す」形**を別の場所に作り直すことになる。

**本文は stdin** で渡し、シェル引数に載せない（`resolve_source_cache_path.py` が識別子を stdin から読むのと同じ理由 — ページ本文はそれ自体が自由記述であり、かつ長い）。`--page-path` 側は `<Type>` と `<slug>` が Pass 2 のソース読解に由来し検証されていないため、`docs/DesignDoc-skills.md` §11.7 のヒアドキュメント形式で渡す。

### 処理フロー

1. `--page-path` から `(lang, Type, slug)` を導出する（`parse_wiki_path()` → `parse_view_path()` の順。どちらにも解決できなければ stderr に `ERROR:` を出して exit 1 — 打ち間違えたパスが「近傍 0 件」として黙って通るのを防ぐ）
2. stdin の本文から `extract_wikilinks()`（＝ `WIKILINK_RE`）で `[[Type/slug]]` を出現順に取り、`resolve_wikilink()` で解決する。解決順序は `docs/DesignDoc-pipeline.md` §6.4 のクロス言語フォールバック（同 lang → `primary_lang` → 未解決）。**未解決のリンクは何も言わずに落とす** — まだ誰も書いていないページを指すことは正常かつ非ブロッキングであり、それを報告するのは `check_wanted_pages.py` の仕事である
3. 両ツリーを走査し、本文に `[[<Type>/<slug>]]` を含むページを inbound として集める（`Grep` ではなく共有の走査 + `WIKILINK_RE`。outbound と同じ抽出を使うため）
4. 3 つの skip 判定を適用する（下記）。**レビュー対象ページ自身は両方向から除外する**
5. outbound → inbound の順に並べ、両方向に現れるページは **outbound 優先で 1 件に畳む**
6. **畳んだ後に** `--max-pages`（既定 5）で切る
7. `PAGE:` 行と `SUMMARY:` 行を出力する

### 3 つの skip 判定

| 対象 | 理由 |
|---|---|
| `index.md` | `rebuild_index.py` が各ページ自身の WikiLink を Type インデックスに書くため inbound 側が必ずヒットする。かつインデックスはそれ自体では何の事実も述べない |
| `status: removed` のページ | 公開されないため、読者に見える形で生きているページと食い違いようがない |
| レビュー対象ページの翻訳（`translated_from` がそれを指すページ） | そこでの食い違いは翻訳の陳腐化であり、`check_translation_status.py` が `STALE` として既に報告している |

**翻訳の判定は `normalize_entity_prefix()` を通す。** 古い翻訳ページは `translated_from` に旧 `.wikicommit/wiki/` プレフィックスを持ったまま残る（新旧混在を許容する方針のため自動移行されない）ので、生の文字列比較にすると**そうしたページが skip されずレビュアーに渡る**。

### 出力フォーマット

```
PAGE: .wikicommit/entity/ja/DefinedTerm/vibe-coding.md (outbound)
PAGE: .wikicommit/view/ja/agent-loop.md (outbound)
PAGE: .wikicommit/entity/ja/DefinedTerm/spec-driven-development.md (inbound)
SUMMARY: outbound=2, inbound=1, skipped=1, capped=false
```

**パスだけを出して終わってはならない。** 隣接ページが 0 件であることは正常な結果（新規の孤立ページ）だが、出力が空であれば「近傍が無かった」と「抽出が何も返さなかった」が区別できない — **本スクリプトが消そうとしている静かな縮みを、新しい境界にそのまま作り直すことになる**。`check_run_records.py` が 0 件のときに `NOTE:` を出すのと同じ理由である。したがって:

- パス行は `PAGE:` を接頭辞に持ち、その向き（`outbound` / `inbound`）を添える
- 最後に `SUMMARY: outbound=<N>, inbound=<N>, skipped=<N>, capped=<true|false>` を必ず 1 行出す。**`skipped` と `capped` がある理由は、3 つの skip 判定と 5 件上限がどちらも集合を縮める操作だから**である — それが効いたことが出力に現れなければ、縮んだ集合と元から小さい集合が再び見分けられなくなる
- 対象ページが 0 件でも `SUMMARY:` は出す（exit code は 0）

### view ツリーも対象に含める

entity ページは `[[View/<slug>]]` を張れ（`View` は予約 Type セグメント）、`link_target_path()` は view ツリーを解決する。check 8 が見るのは「ページ間矛盾」であり、view ページも矛盾しうる相手である。view ページ自身をレビュー対象に取ることもできる。

### 既知の限界

`references/pass4-review.md` が述べている 2 つをそのまま引き継ぐ。**同一バッチ内では、あるページは自分より先に生成された兄弟しか見られない**ため、ペアが片側からしか照合されない（あるいは全くされない）ことがある。**異なるバッチで生成された 2 ページ間の矛盾は原理的に届かない。** リポジトリ全体走査が両方への答えであり、意図的に作られていない。

**既に書かれたレビュー記録は書き換えない**（記録は不変）。近傍の集合が足りなかった過去のレビュー記録について**再レビューを促す仕組みは作らない** — `STALE_REVIEW:` はページかソースが変わったときに出るものであり、「レビューの入力が足りなかった」はそこに乗らない。

### 終了コード

- `0`: 近傍を出力した（0 件を含む）
- `1`: `--page-path` が entity / view ツリーの外を指している

---

## build_survey_view.py

### 目的

`/wikicommit-synthesize` を引数なしで実行した場合（俯瞰モード）、「何について書くか」自体を Wiki 全体から見つける必要がある。Wiki の全文は1つのコンテキストに入らないため、本スクリプトは各ページを「横断的な構造を担う数行」— `title`・`type`・`tags`・`properties.description`・`##` 見出し・発リンク — に縮約し、リンクグラフから算出した集計（ハブ・タグ・型）を添えて出力する。

**なぜ `properties.description` だけでは足りないか**: `description` は設計上「2〜3文の要約に収める」と決まっている（`docs/DesignDoc-data.md` §4.1）ため、本文にしか現れないパターン — まさに俯瞰モードが狙う着眼点 — は description のみの縮約では構造的に見えない。`##` 見出しは、本文のうち「何を扱っているか」を名指しする最も安価な部分である。リンクグラフはそれ以上に重要で、「複数の Place ページが1人の Person を経由して繋がっている」は**どの1ページの本文についての記述でもなく**、ページ同士の間にしか存在しない — 全ページを同時に見るビューだけが見つけられる。

**なぜスクリプトなのか**（SKILL.md のプローズではなく）: 「全体を俯瞰する」以上、全ページ走査の網羅性そのものが機能の前提であり、取りこぼしは黙って結果を損なう（`docs/DesignDoc-skills.md` §11.5 のスクリプト委譲パターン）。一方でスクリプトは**判断を行わない** — 縮約ビューから着眼点を選ぶのは LLM の仕事であり、そちらは本質的に非決定論的である。

**本文全体を読む案（チャンク分割 + サブエージェントの map-reduce）は採らない**。実行のたび Wiki 全文を読むコストに加え、横断パターンの証拠が2つのチャンクに分かれると双方のサブエージェントが「単独では平凡」として落とす分割ロスがあり、狙っている対象そのものに直撃する。将来の拡張余地として残し、その際は全ページ走査による矛盾検出（バッチをまたぐページ間矛盾。`docs/DesignDoc-pipeline.md` §7）と分割戦略・返却形式を共有する。

### 使用場面

- `wikicommit-synthesize` Skill：Step 0（俯瞰モード。`<topic>` が省略された場合のみ）
- `wikicommit-synthesize` Skill：Step 3（`--pages`。根拠ページの候補を、本文を読む前に選別する。下記）
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。research guidance が渡されなかった場合のみ）。同じ縮約ビューを別の問いに使う — synthesize が「既存ページから何を書けるか」を探すのに対し、collect は「何が足りていないか」を探すため、`check_wanted_pages.py` の `WANTED:` と `check_orphans.py` の `ORPHAN:`（出自ソース付き）を併せて読む

### コマンド

```
python .wikicommit/scripts/build_survey_view.py [--lang <lang>|all] [--max-pages N] [--limit N]
```

- `--lang`: ページを列挙する言語（既定は `config.yml` の `primary_lang`）。`all` で全言語。翻訳ページは同じ内容を別の言語で述べ直したものなので、既定では列挙しない（コンテキストを消費するだけになる）。**ただしリンクグラフは常に全言語から構築する** — WikiLink は言語を持たないため、1言語分の発リンクしか数えないと全ハブが過小評価される
- `--max-pages`: 列挙するページ数の上限（既定 300、`0` で無制限）。超過分は切り捨て、`TRUNCATED:` 行で明示する
- `--limit`: ランキング（`HUB:` / `TAG:`）1つあたりの件数（既定 20）

### `--pages` — 名指ししたページだけを縮約する

```
python .wikicommit/scripts/build_survey_view.py --pages <path> [<path> ...]
```

`/wikicommit-synthesize` Step 3 は、検索候補（数十件）のうち「テーマを主題として扱っているか」を**本文を読む前に**判定する。判定に使うのは title・`properties.description`・`##` 見出しで、1 ページ数行である。これをエージェントに各ファイルを読ませて拾わせると、候補数十件分の本文を結局読むことになり、選別を前に置いた意味が消える。取り出しは決定論的な操作なので、既存の縮約ロジックを候補だけに適用するモードとして持つ。

- 名指しした順に `PAGE:` を出し、`HUB:` / `TAG:` / `TYPE:` / `TRUNCATED:` は出さない。backlinks はリンクグラフ全体から数える
- **view ツリーも解決する**（`--include-view` の有無に関わらず）。候補に view ページが混ざるのは正常であり、それを落とすのが呼び出し側の仕事だからである
- `PAGE:` 行の末尾に `path=<パス>` を付け、翻訳ページ（`translated_from`）には `translation`、合成ページ（view ページ、または `derived_from` を持つ entity ページ）には `synthesized` を付ける。**判定は frontmatter から行う** — `grep -l "^derived_from:"` では本文中に YAML 例として `derived_from:` を引用しただけのページにも一致する
- 解決できないパス（存在しない・`status: removed`・両ツリーの外）は `MISSING:` として 1 行ずつ出す。黙って落とすと、主題外と判定した候補と区別できない
- 最後に `SUMMARY: pages=<N>, missing=<N>` を出す。終了コードは常に 0

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
PAGE: Place/minuma | 見沼田んぼ | backlinks=12 | sources=3 | tags=治水,農業 | links=Event/minuma-reclamation,Place/minuma-tsusenbori
  DESC: 江戸時代に干拓された低湿地帯。
  HEADINGS: 歴史 / 治水との関係 / 現在
HUB: Place/minuma 12
TAG: 治水 7
```

`sources=N` はそのページの `sources[]` のエントリ数である。`/wikicommit-collect` Step 3.5 が「中心概念が 1 本の資料にしか立っていない」ことを着眼点の材料にするためのもので、`check_orphans.py` の `ORPHAN:` が出自付きで「端が薄い」を出すのと対になる。**翻訳ページ（親から継承する）と view ページ（`derived_from` であって `sources` ではない）では区画ごと省く** — `0` は「ソースが無い」と読めるため。**`HUB:` 行には置かない** — `HUB:` はキー単位で、そこに出すと「どのページの `sources[]` を代表させるか」の判定がもう 1 箇所要る。`HUB:` に出るキーには必ず対応する `PAGE:` 行がある（`hubs` は `listed_keys` でフィルタされる）ので、単位の不一致を作らずに同じ情報が届く。frontmatter の読み取りは `title` / `tags` と同じ 1 回に相乗りし、走査は増えない。数字の意味と決定事項の全体は `docs/DesignDoc-publish.md` §8.8.1「ハブ行のソース件数と、同じソースに立つハブ」にある（経緯は `docs/history/DesignDoc-publish.md` の同じ見出し）。

### 終了コード

- 常に `0`（読み取り専用のレポート。読み込めないページ・フロントマターが壊れているページは stderr の `WARNING:` として報告し、そのページのみスキップする）

---

## check_extraction_quality.py

### 目的

`wikicommit-generate` Pass 1 の抽出失敗判定は、抽出テキストが空または読み取り不能な場合だけでなく、JS 実行が前提の SPA サイト等を静的フェッチ手段（`markitdown`・`curl`）で取得した際に生じる「非空だが無意味」な抽出結果（ナビゲーション・ログインプロンプト・埋め込み JSON 状態等のシェルのみで、実際のページ内容を含まない）も扱う必要がある。本スクリプトはそのための3つの決定論的チェックを提供する:

- `check-domain`（ガードB・即効性）: 抽出を試みる前に、URLのドメインが「静的フェッチでは空シェルを返すことが確認済み」の既知不可ドメインかどうかを判定する。`x.com`/`twitter.com`/`music.youtube.com`（YouTube Music は `www.youtube.com` へリダイレクトしないため `markitdown` の `YouTubeConverter` が適用されず、「お使いのブラウザ向けに最適化されていません」の185文字程度のシェルしか返さない）を初期エントリとする。精度は高いが、確認済みドメインしかカバーしない。
- `check-fetch-capability`（ガードC・取得能力の事前チェック）: 抽出を試みる前に、URLのホストが「完全な抽出に追加の Python パッケージを要する」既知ホストかどうかを判定し、要する場合はそのパッケージが実際に import 可能かを確認する。初期エントリは YouTube 系ホスト（`youtube.com`/`youtu.be`/`m.youtube.com` — この3ホストはリダイレクト解決後にいずれも `https://www.youtube.com/watch?…` に着地し、バイト単位で同一の抽出結果になる〈2026-08-27 の実測〉）と `youtube_transcript_api`。`music.youtube.com` はリダイレクトしないため `YouTubeConverter` 自体が適用されず、パッケージを入れても解決しない — こちらはガードB（`KNOWN_JS_SHELL_DOMAINS`）の担当。判定はホスト単位であり、同じホスト上の `/watch?v=…` と `/shorts/<id>`・`/playlist`・チャンネルページを区別しない（後者も `YouTubeConverter` の前方一致要件を満たさず抽出できないが、ガードCは「そのホストが要するパッケージが導入済みか」しか保証しない — 残りは `wikicommit-generate` Pass 1 手順6の抽出結果の形状チェックが担う）。
- `check-density`（ガードA・汎用安全網）: 抽出後のテキストに対し、自然文らしい文字がどの程度の割合を占めるかを判定する。ドメインを問わない一般的なヒューリスティックで、ガードBがカバーしない未知のケースを拾う代わりに精度は低い。

ガードCが独立した軸として必要な理由: `markitdown` の `YouTubeConverter` は `youtube_transcript_api` が未導入だと `IS_YOUTUBE_TRANSCRIPT_CAPABLE = False` となり、**例外も警告も出さずに** `### Transcript` セクションごと出力から落とす。残るのはタイトル・キーワード・Runtime・概要欄で、これらは実際の自然文であるため、空シェルでも低密度でもない — ガードAの比率は字幕なしでも閾値 0.3 を大きく上回り、閾値の調整では区別できない（長さではなく文字種で判定する設計そのものによる）。ガードBの既知不可ドメインに `youtube.com` を加えるのも、「静的フェッチで空シェルしか返さないことが確認済みのドメイン」という定義に反する（字幕込みなら十分な内容が取れる）。つまりこれは「空シェル」でも「低密度」でもなく **partial extraction** であり、取得後のテキストを見る限り検出しようがない。取得前に「取得能力があるか」を確かめる別軸のチェックが要る。

事前チェックにする理由: 取得後に `### Transcript` の有無だけを見ても、「パッケージ未導入」と「その動画に字幕が存在しない」を区別できない。前者はユーザーが一度直せば済む環境の問題、後者はそのソース固有の事実であり、扱いを変える必要がある（`wikicommit-generate` Pass 1 は前者で処理全体を停止して `pip install` を案内し、後者は `status: failed` にせず Completion Notice にロールアップする）。事前チェックであればこの曖昧さが構造的に発生しない。

**3つのガードの強度は同じではない**。ガードCはガードBと同じくブロッキングだが、失敗の意味が異なる — ガードBはそのソースを `status: failed` にして次のソースへ進むのに対し、ガードCは**処理全体を停止する**（`markitdown --version` の Prerequisite チェックと同じ扱い。環境の問題であってソースの問題ではないため、`status: failed` として記録してはならない）。ガードBの `BLOCKED:` は確認済みドメインに対する決定論的判定であり、`wikicommit-generate` Pass 1 はこれをブロッキング（`status: failed`）として扱う。ガードAの `LOW_DENSITY:` はテキスト形状のヒューリスティックにすぎず、Pass 1 はこれを**人間に続行可否を確認する警告**として扱う（非対話実行時のみ `status: failed`。詳細は `docs/DesignDoc-pipeline.md` §6.1・`.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。本スクリプト自身の終了コードは両者とも `1` のままで、強度の違いは呼び出し側の扱いにある。

3つのガードは排他ではなく、`wikicommit-generate` Pass 1 で順に適用される（`.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。`check-domain` は `wikicommit-collect` の候補提示ステップからも、既知不可ドメインを候補から事前に除外する目的で呼ばれる。

**このスクリプトが扱わない partial extraction がある**。ガードC が扱うのは「必要なパッケージを入れれば `markitdown` が完全に取れる」種類の欠落だけであり、`importlib.util.find_spec()` による判定はその前提の上に立っている。GitHub の Issue / PR URL は本文が取れてコメントだけが黙って落ちるが、必要なのはパッケージではなく別の取得経路なので、この前提を満たさない — ガードC を一般化すると exit 1 の意味（処理全体を止めて `pip install` を案内する）が端的に誤りになる。ガードB は「空シェル」の定義に反し（本文は取れている）、ガードA は落ちているものが自然文なので形状で区別できない（比率は閾値を余裕を持って上回る）。

したがってこの失敗クラスは**本スクリプトではなく `add_source.py` の登録時通知**が扱う（`partial_extraction_note()` / `PARTIAL_EXTRACTION_URL_NOTES`。ブロックせず・`status` を変えず・登録時に一度だけ知らせる）。**ここに 4 つ目のガードを足さないこと** — ガードは Pass 1 の分岐を左右するものであり、ブロックしない判定を同じ場所に置くと、精度の異なるガードを同じ強度で扱う混同を作ることになる。次に 3 例目が出たときの判断手順は `docs/DesignDoc-pipeline.md` §6.1 にある。

### 使用場面

- `wikicommit-generate` Skill：Pass 1（`type: url`/`wikicommit` ソースの抽出前に `check-domain` → `check-fetch-capability`、全ソース種別の抽出成功後に `check-density`）
- `wikicommit-collect` Skill：Web候補提示ステップで `check-domain` を呼び、既知不可ドメインの候補を事前に除外する

### コマンド

```
python .wikicommit/scripts/check_extraction_quality.py check-domain <url>
python .wikicommit/scripts/check_extraction_quality.py check-fetch-capability <url>
python .wikicommit/scripts/check_extraction_quality.py check-density [<file>]
```

`check-density` は `<file>` を省略した場合、標準入力からテキストを読む（抽出テキストがファイルとして永続化されていないソース向け。詳細は `.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。この分岐の対象は `.md` / `.txt` のソースだけである — 他のソースの抽出結果は `.wikicommit/.cache/`（`type: path` は `extract-path/`）に残るのでファイル経路を通る一方、`.md` / `.txt` は生ファイルが抽出テキストそのものなので意図的にキャッシュせず、抽出テキストはその実行のコンテキストにしか存在しない。（`type: manual` はここには現れない — 管理ファイルの `source.type` は `path` / `url` / `wikicommit` のみで、`manual` はページ側の `sources[]` にしか現れる値であり、Pass 1 の抽出対象にならない。）

### 処理フロー（`check-domain`）

1. URLからホスト名を抽出する（`www.` プレフィックス・ポート番号は正規化して除去）
2. スクリプト内にハードコードされた `KNOWN_JS_SHELL_DOMAINS` 集合（初期値: `x.com`, `twitter.com`）に一致するか確認する。一致すれば `BLOCKED:` を出力して終了する
3. `.wikicommit/source-policy.md` の `wikicommit.exclude_domains`（`docs/DesignDoc-data.md` §3.4）を読み、**組み込みリストとの和集合**として同じ判定を行う。一致すれば `BLOCKED:`（組み込み側とは別のメッセージ。どちらのリストで落ちたかを呼び出し側が区別できる）を出力して終了する
4. どちらにも一致しなければ `OK:` を出力する

新しいドメインをこの集合に追加する場合は、実際に空シェルが返ることを確認した上で追加すること（未確認のまま追加すると、本来は正常に取得できるドメインの抽出を無条件にスキップしてしまう）。

`exclude_domains` の各エントリは `_domain_of()` と同じ形（スキーム・パス・ポート・先頭 `www.` を除去し小文字化）に正規化してから**完全一致**で比較する（`example.com` は `blog.example.com` に一致しない）。正規化しないと、人間が `rejected:` の `url:` に倣って `https://example.com/` のように書いた場合に一致せず、ファイル上は除外されているのに実際には取得され続ける。ファイルが無い・フロントマターが壊れている・値がリストでない、のいずれも「追加ドメインなし」として扱い、組み込みリストによる判定は必ず生き残る — ただしフロントマターのパースに失敗した場合のみ stderr に `WARNING:` を出す（`wikicommit-collect` がこのファイルの `rejected:` に追記する以上、追記ミス 1 回で `exclude_domains` 全体が無言で無効化されうるため。stdout の `BLOCKED:`/`OK:` 契約は変えない）。

### 処理フロー（`check-fetch-capability`）

1. URLからホスト名を抽出する（`check-domain` と同じ `_domain_of()`。`www.` プレフィックス・ポート番号は正規化して除去）
2. スクリプト内にハードコードされた `_FETCH_CAPABILITY_REQUIREMENTS`（ホスト → `(import 名, pip 名, 未導入時に欠ける内容)`）に一致するか確認する。一致しなければ `OK:` を出力して終了する
3. 一致した場合、`importlib.util.find_spec()` でそのパッケージが import 可能かを確認する。可能なら `OK:`、不可能なら `MISSING_PACKAGE:`（`pip install <pip 名>` を含む）を出力する

ホストは完全一致で判定するため、同じサイトが到達可能な別名をすべて列挙する必要がある（`youtube.com`/`youtu.be`/`m.youtube.com` の3形式は `markitdown` がリダイレクト解決後の最終URLで変換器を選ぶため、いずれもバイト単位で同一の抽出結果になることを実測確認済み〈2026-08-27〉。`music.youtube.com` だけはリダイレクトしないため対象外 — 上記「目的」節参照）。

### 処理フロー（`check-density`）

1. テキストをトークン化する。空白区切りに加え、**URL の境界でもトークンを切る**（スキーム付き `https://…`・プロトコル相対 `//upload.wikimedia.org/…`・裸の `www.…`）。空白だけで切ると、分かち書きしない日本語では地の文とパーセントエンコードされたリンク先URLが1つの巨大トークンに融合し、次の手順のURL判定が地の文もろとも捨ててしまう。空白で単語を区切る言語ではURLは元から独立したトークンなので、これは結果を変えない。また URL 自体は空白・Markdown のリンク/引用区切り文字に加え、**CJK 文字・全角記号でも終端する** — URI は ASCII のみで構成されるため実在のリンク先を途中で切ってしまうことはなく、逆にこれがないと分かち書きしない日本語では裸の URL（Markdown リンクと違い `)` で終わらない）が後続の地の文を丸ごと飲み込み、同じ融合が起きる
2. URL トークンは無条件に「非自然文的トークン」とする。それ以外のトークンは、以下のいずれかに該当する場合に「非自然文的トークン」と判定する:
   - `{`・`}`・`<`・`>`・`;`・`=` のいずれかを含む
   - `"` を2個以上、または `` ` `` を含む
   - 上記に該当せず、前後の記号を除去した中核部分の英字比率が70%未満
3. 各トークンの文字数を重みとして、「自然文的トークン」の文字数の割合（`natural-language character ratio`）を計算する（トークン数ではなく文字数で重み付けすることで、単語間にスペースを持たないCJK言語〈日本語等〉が不当に低く判定されることを防ぐ）。文字数の数え方には2つの正規化を入れている:
   - CJK 文字は `CJK_CHAR_WEIGHT`（3）文字分として数える。CJK 文字1字が担う情報量はラテン文字1字よりはるかに多く（`extracted_tokens` の概算がラテン文字4字≒1トークンと見積もるのに対し、CJK は1字≒1トークン）、同じ重みで数えると同じリンク密度の同等な散文でも日本語だけが不当に低く出るため。この重みは CJK を含まないテキスト（ガードAが本来捕まえるべき ASCII の JS/ナビシェル）には定義上まったく影響しない
   - URL トークンはパーセントデコードした長さで数える。`%E3%81%95` は日本語1文字が転送エンコードで9文字に膨らんだものにすぎず、そのまま数えると日本語ページへのリンクが英語ページへの同じリンクの9倍のマークアップに見えてしまうため
4. 比率が `LOW_DENSITY_THRESHOLD`（0.3）未満であれば `LOW_DENSITY:`、以上であれば `OK:` を出力する。`LOW_DENSITY:` の場合は、非自然文と判定された文字の内訳（`links` / `numbers/tables` / `other markup` の割合）を同じ行に添える — 人間が続行可否を判断する材料として、リンクが多いだけの正当なページ・統計表・実際のスクリプトシェルを見分けられるようにするため

**既知の限界: 数表密度**: 統計表・数値中心の資料（国勢調査の結果概要・統計書等）は、非自然文の正体がリンクではなく数値と表の `|` 記号であるため、手順1のURL境界トークン化では比率が回復しない。これは汎用ヒューリスティックとしての精度の限界であり、追加の検出ロジックは設けない — ガードAが警告どまりであること（上記）と、手順4の内訳が `numbers/tables` 優位として表示されることで、人間が続行を判断できる。`check_wanted_pages.py` の「地の文言及は対象外」と同じ種類の、意図して残した限界である。

### 出力フォーマット

```
MISSING_PACKAGE: youtube.com requires the youtube-transcript-api package to extract the video's transcript (without it, only the title, keywords, runtime and description are extracted — the video's actual content is missing). Install it with: pip install youtube-transcript-api
OK: youtube.com: youtube_transcript_api is installed
OK: example.com needs no extra extraction package
BLOCKED: x.com is a known JS-rendering-required domain; static fetch (markitdown/curl) has been confirmed to sometimes return an empty content shell with no meaningful text.
OK: example.com is not a known JS-shell domain
LOW_DENSITY: .wikicommit/.cache/ingest-fetch/x.com/karpathy-status-1886192184808149383.md (natural-language character ratio: 0.09, threshold: 0.3) — extracted text looks like boilerplate/markup rather than real content. non-prose breakdown: links 12%, numbers/tables 3%, other markup 85%.
OK: .wikicommit/.cache/ingest-fetch/example.com/article.md (natural-language character ratio: 0.72)
```

### 終了コード

- `check-domain`: `0` = 組み込みの既知不可ドメインにも `source-policy.md` の `exclude_domains` にも一致しない、`1` = どちらかに一致する
- `check-fetch-capability`: `0` = 追加パッケージ不要、または必要なパッケージが導入済み、`1` = 必要なパッケージが未導入。`1` は呼び出し側にとって「処理全体を停止して `pip install` を案内する」シグナルであり、そのソースを `status: failed` にするシグナルではない
- `check-density`: `0` = 低密度でない、`1` = 低密度、またはファイルが読み込めない。`1` は呼び出し側にとって警告であってブロッキングではない（上記「3つのガードの強度は同じではない」参照）

---

## validate_frontmatter.py

### 目的

`.wikicommit/entity/` 配下の Wiki ページが、フロントマター仕様を満たしているかを検証する。

### 使用場面

- `wikicommit-merge` Skill：品質ゲートとして変更ファイルのみを対象に実行
- `wikicommit-review` Skill：手動ページ（経路 B）のレビュー前チェック
- `wikicommit-status` Skill：Step 3。引数なしで全ページに対して実行し、`ERROR:` 行だけを拾う（冒頭の「merge の blocking な 3 本は status が全ページに走らせる」節）

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
| `type` | string | `schema:` プレフィックスで始まること。`custom/` プレフィックスを持たず（`type_name` が `custom/` で始まらず）、かつ Schema.org 語彙（`.wikicommit/schemaorg-vocab.json`）にも実在しない場合は ERROR（誤字・命名規約違反等の検出。`custom/` プレフィックスを持つ型、および語彙が取得できない場合はこの検証をスキップする — 前者は Schema.org 語彙に存在しないことが正規の設計であるため、後者は §5.2 の `properties:` フォーマット検証と同じ理由で非ブロッキングとする）。`.wikicommit/schema/<Type>.md` というローカルファイルが実際に存在するかどうかとは独立の判定であり、両者は食い違いうる — ローカルファイルがなければ `resolve_type_schema()` 側の別の WARNING（「スキーマファイルが見つかりません」）も同時に出る。この ERROR はキャッシュの鮮度にも影響される点に注意: `.wikicommit/schemaorg-vocab.json` は TTL を持たず手動削除でのみ再取得されるため（`_schemaorg_vocab.py`）、Schema.org 側で新しく追加された型を使ったページは、そのリポジトリのキャッシュが再取得されるまで本 ERROR で `wikicommit-merge` がブロックされ続ける。対処はキャッシュファイルを手動削除して再実行すること。**あわせて、ページのファイルパスと `type:` の一致も検証する**: `.wikicommit/entity/<lang>/<Type>/<slug>.md` に置かれたページの `type:` は `schema:<Type>` でなければならず、custom 型では `custom/` サブパスを含む（`schema:custom/Decision` は `.wikicommit/entity/<lang>/custom/Decision/` に置く。`_wikilink.py` の `parse_wiki_path()` がパスから `(lang, type, slug)` を導出する）。不一致は ERROR。`<lang>/<Type>/<slug>.md` の形に解決できないファイル（`.wikicommit/entity/` 直下に置かれたページ、旧 `.wikicommit/wiki/` プレフィックスのままのページ）はこの検証の対象外とし、何も報告しない（新旧混在を許容する方針）。`type:` 自体が欠落している・`schema:` プレフィックスを持たない場合も、それぞれ別に報告済みのため重ねて報告しない |
| `sources` | list | 1件以上（翻訳ページは除く） |
| `review_status` | string | `pending` / `reviewed` のいずれか（それ以外の値は ERROR）。省略時は WARNING（`pending` として扱う） |
| `expires_at` | string | `YYYY-MM-DD` 形式。`generated_at` と両方あり、`expires_at <= generated_at` なら WARNING（生成した時点で既に過ぎている日付は「この日を過ぎたら読み直せ」という予定として働かず、`check_expires.py` が生成直後から EXPIRED を出す。多くは文書の経緯にある第三者宛ての締切〈各国政府へのコメント期限等〉を取り違えたもの。判断を要さず決まるので指示文ではなくここで見る。手書き・旧版のページにもありうるので ERROR にはしない。`/wikicommit-generate --regenerate` は `expires_at` を保つので、直すのは人の手である） |
| `wikidata` | string | `wd:Q` で始まること |
| `tags` | list | 各要素は string |
| `generated_at` | string | `YYYY-MM-DD` 形式 |
| `generated_by` | string | 空文字列不可 |
| `generated_with` | string | 空文字列不可。このページを生成した WikiCommit 自身の版（任意フィールドで、欠如は「`generated_with` を書くようになる前に生成された」ことを意味する。semver パターンへの照合は行わない — モデル ID を正規化表に照合しないのと同じ理由） |

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
| （全要素） | `license` | 任意。存在する場合は空でない文字列（空文字列は ERROR。「不明」はフィールドごと省略して表す）。値の中身は検証しない — SPDX 語彙への照合もソースの実際の条件との突合も行わない（`docs/DesignDoc-publish.md` §8.10） |

#### `properties:` のフォーマット

`properties:` が存在し、かつ dict 型以外（文字列・リスト等）であれば ERROR。存在しない、または YAML 上「値なし」（`properties:` の下に何も書かれていない。パース結果は `None`）の場合は「型固有プロパティなし」として扱い ERROR にしない。

dict であれば、各キーについて以下を検証する（`properties:` が存在しないページでも、型固有プロパティの平置き検出〈後述〉のために 1〜5 の型解決自体は常に行う）:

1. ページの `type:` が `schema:` プレフィックスを持たない場合は検証をスキップ（`type` 自体のフォーマットエラーとして別途報告済み）。
2. `type:` の型名（`schema:` プレフィックスを除いた部分）が `custom/` で始まる場合は検証をスキップ — カスタム型は Schema.org 語彙に存在しないため、`properties:` の妥当性は `wikicommit-schema-propose` の PR レビュー時に人間が確認する（`docs/DesignDoc-data.md` §5.3）。
3. `.wikicommit/schemaorg-vocab.json`（`_schemaorg_vocab.py` 経由。`check_schema_org_type.py` と共有）を読み込む。取得できない場合（未コミット・削除後未再生成・ネットワーク不通等）は、`properties:` に1件以上キーがあるページに限り WARNING を1件出力し、`properties:` の検証・平置き検出の両方をこの実行ではスキップする（ブロッキングにしない — ネットワーク不調やキャッシュ未生成でマージが止まるのを避けるため）。
4. 型が語彙に存在しない場合は ERROR（`type` フィールドに対する ERROR — 上記「Wiki ページ共通フィールド」表の `type` 行と同じ検証をここで実行する。誤字・命名規約違反等で `.wikicommit/schema/<誤った型名>.md` というローカルファイルさえ存在すれば `resolve_type_schema()` は WARNING すら出さずに通過してしまうため、`properties:` を検証する `validate_schema_properties()` 側でも独立に検証する）。この場合、`properties:` の各キー検証・下記のトップレベル平置き検出のいずれも実行せず打ち切る（型の祖先チェーンが解決できないため、いずれも判定不能）。
5. 型が語彙に存在する場合、`properties:` の各キーが `rdfs:subClassOf` による祖先チェーンを含めて型の `domainIncludes` に属するかを検証する。属さない、またはキー自体が Schema.org 語彙に存在しない場合は ERROR。

**トップレベルへの平置き検出**: 上記 1〜3・5 で型が解決できた場合（4 で ERROR になった場合を除く）、`properties:` の中身とは別に、フロントマターのトップレベルに存在するキーのうち構造的フィールド一覧（`title`/`lang`/`type`/`sources`/`tags`/`review_status`/`expires_at`/`generated_at`/`generated_by`/`generated_with`/`wikidata`/`sameAs`/`aliases`/`properties`/`translated_from`/`source_commit`/`translated_at`/`translated_by`/`translated_with`/`translator_notes`/`derived_from`/`status`/`removed_at`/`removed_reason`/`merged_into`）に含まれないものを走査し、それが実際にそのページの型（祖先型含む）に属する Schema.org プロパティである場合は ERROR とする（例: `description:` をトップレベルに平置きしたページ。`properties:` へのネストが必須という設計を LLM や人間の書き忘れから機械的に守るためのガード）。型に属さない、または Schema.org 語彙に存在しないキーは対象外（無関係な独自フィールドを誤検知しないため）。

#### 翻訳ページ追加フィールド（`translated_from` が存在するページ）

| フィールド | 必須/任意 | フォーマット制約 |
|---|---|---|
| `translated_from` | 必須 | リポジトリルートからの相対パス（例: `.wikicommit/entity/ja/Person/yamada-taro.md`）。対象ファイルが実在すること（旧 `.wikicommit/wiki/` プレフィックスのままの値も `_wikilink.py` の `resolve_stored_entity_path()` 経由で解決を試みる。`docs/DesignDoc-data.md` §3.1「旧ディレクトリ名 `.wikicommit/wiki/` の後方互換」参照） |
| `source_commit` | 必須 | 40文字の git コミットハッシュ（`[0-9a-f]{40}`）、または空文字列（`wikicommit-translate` は原文ページに commit が無い場合〈生成直後でまだ `wikicommit-merge` されていない等〉、空文字列のまま書き込む。`check_translation_status.py` はこれを正しく `STALE` として検知する） |
| `translated_at` | 任意 | `YYYY-MM-DD` 形式 |
| `translated_by` | 任意 | 空文字列不可（`generated_by` と同じフォーマット制約。翻訳実行モデル ID） |
| `translated_with` | 任意 | 空文字列不可（`generated_with` と同じフォーマット制約。この翻訳を生成した WikiCommit 自身の版） |
| `translator_notes` | 任意 | list 型（各要素は string）。各要素の内容自体（`YYYY-MM-DD: <note>` 形式）に対する機械検証は行わない（`## User Notes` と同じ、フリーテキストの人間/LLM向けメモのため） |

#### 合成ページ追加フィールド（`derived_from` が存在するページ）

| フィールド | 必須/任意 | フォーマット制約 |
|---|---|---|
| `derived_from` | 必須 | list 型・1件以上の要素が必要 |
| `derived_from[].path` | 必須 | リポジトリルートからの相対パス。対象ファイルが実在すること（`translated_from` と同じく旧 `.wikicommit/wiki/` プレフィックス値も解決を試みる） |
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
- `wikicommit-status` Skill：Step 3。引数なし・`--skip-type-mismatch` 付きで全ページに対して実行し、`ERROR:` 行だけを拾う（冒頭の「merge の blocking な 3 本は status が全ページに走らせる」節）

### コマンド

```
python .wikicommit/scripts/check_wikilinks.py [--changed <path>... [--deleted <path>...]] [--skip-type-mismatch]
```

- `--changed`: 追加・変更されるファイル（WikiLink の参照先を検証する対象）
- `--deleted`: `status: removed` を新たに付与するファイル（被リンクの残存を確認する対象）
- **引数なし**: `.wikicommit/entity/` 配下の全ページ（`assets/` を除く）を検査対象にする。`--changed` 相当だが、**同一コミット内新規追加の例外は無効**にする — あの例外は「参照先はまだ存在しないがこの変更が追加する」という意味であり、対象集合が「既にディスク上にある全ページ」であるときには意味を持たない。有効なままだと全リンクがその分岐を通り、`<primary_lang>` にしか存在しないページへの他言語ページからのリンクが「翻訳ページ未作成」の WARNING を出さずに黙って通ってしまう（このモードが出しうる 2 種類の WARNING の片方が原理的に出なくなる）。`status: removed` ページへのリンクは通常の存在確認経路が同じ ERROR を出す。引数なしで `OK: 0 files checked` を出して終わる実装にはしない — 正常なチェックの成功と区別がつかない。`--deleted` は引数なしモードでは空のまま — 「この変更でこれらのファイルが removed になる」という意味は差分の中にしか存在せず、差分の外に対応物が無い。既に `status: removed` を持つページは `--changed` 側から辿られる。引数なしモードでは、**自身が `status: removed` のページはリンク元として検査しない** — 公開されないページの発リンクは何も壊さず、報告しても誰も二度と編集しないので消えない所見になる（A を削除した後で A が指す B を削除すると、以後 A に ERROR が残り続ける）。`wikicommit-merge` は常に `--changed` を渡すため、差分スコープの挙動はこの分岐の影響を受けない
- `--skip-type-mismatch`: Type セグメント取り違えの ERROR（下記）を出さない。その所見は `check_wanted_pages.py` が `TYPE_MISMATCH:` として報告しているため、両方を走らせる `wikicommit-status` が同じ所見を 2 回出さないためのフラグである。WARNING にも落とさない — 実在するページを「存在しない」と言うことになり、この分岐が避けようとしている誤りそのものになる。**落とすのは `<Type>/<slug>` がどの言語にも実在しない場合に限る** — それが `check_wanted_pages.py` が `TYPE_MISMATCH:` を出す条件であり、第 3 の言語や removed ページとしてだけ実在する場合は向こうが黙るので、ここの ERROR が唯一の報告になる。`status: removed` へのリンクの ERROR はフラグに関わらず出る。`wikicommit-merge` はこのフラグを渡さない（merge では引き続きブロックする）。重複の除去を SKILL.md の散文（メッセージの文言での除外）に委ねないのは、決定論的に判定できるものを指示に書くことになり、文言が変わると黙って二重報告に戻るためである

### 処理フロー

1. `--changed` の各ファイルから `[[Type/slug]]` パターンを抽出する
2. 各 WikiLink について以下を検証する:
   - `<lang>` の決定: チェック対象ファイルの `lang` フィールドを基準言語とする
   - 参照先の解決順序（`[[Type/slug]]` に lang は含まれないため以下の順で検索）:
     1. `.wikicommit/entity/<lang>/<Type>/<slug>.md` が存在すれば OK
     2. 上記が存在せず、`.wikicommit/config.yml` の `primary_lang` での `.wikicommit/entity/<primary_lang>/<Type>/<slug>.md` が存在する場合 → WARNING のみ（翻訳ページ未作成）
     3. いずれの言語にも存在せず、**同じ slug のページが別の Type に実在する** → **ERROR**（実在する Type を名指しする。詳細は下記）
     4. いずれの言語・いずれの Type にも存在しない → **WARNING**（ERROR にしない — ブロックすると LLM・人間の双方が「まだ無い概念は WikiLink 化せず地の文のまま書く」を選びがちになり、複数ソースで繰り返し言及される一般概念がページ化されないまま埋もれる。集計は `check_wanted_pages.py` が別途担う）
   - 参照先ページの `status` が `removed` か → removed の場合は ERROR（変更なし。CLAUDE.md の orphan 検出の非対称設計が指す、削除フローの順序制約回避のための意図的なブロック）
   - 例外: `--changed` 内に同じ `<lang>/<Type>/<slug>` で新規追加されるファイルが存在する場合は上記 ERROR / WARNING としない（同一コミット内の新規追加ページへのリンク）
3. `--deleted` が指定された場合、削除対象ページへの被リンクを `.wikicommit/entity/` 全体から検索する → 残存する被リンクがあれば WARNING

#### Type セグメントの取り違え

`[[Type/slug]]` は Type セグメントと slug の**両方**が一致して初めて解決するため、slug は合っているが Type だけを間違えた WikiLink は「参照先が存在しない」として扱われる。しかし実体はリポジトリに在るので、正しい対処は新規ページの作成ではなく**リンク 1 語の修正**であり、上記 4.（WARNING）とは行動が正反対になる。両者はメッセージ上まったく区別がつかず、`check_wanted_pages.py` に至っては「これから作るべきページ」として提示してしまう（そのとおりに作れば内容の重複した 2 ページができ、`check_orphans.py` の重複判定は `type` が違うため検出しない）。

そのため、未解決 WikiLink を検出した時点で `.wikicommit/entity/` を全 Type 横断で走査し、同じ slug を持つページが別の Type に実在すれば **ERROR** として報告する。`wikicommit-merge` をブロックする点は既存の `status: removed` へのリンクと同じ。

- **4. を WARNING にした理由と衝突しない**: 4. が ERROR を避ける理由は、ブロックすると書き手が「まだ無い概念は WikiLink 化せず地の文で書く」という回避行動を取り、繰り返し言及される概念がページ化されないまま埋もれることにあった。このケースにはその回避行動が存在しない — 参照先は既にページを持っており「まだ無い概念」ではないため、WikiLink 化をやめる動機が生まれない。実在しない slug への WikiLink は WARNING のまま変わらない。
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

blocking ケースは `status: removed` へのリンクと「別 Type に同名 slug が実在する未解決 WikiLink」の 2 つである（終了コードは `total_errors > 0` で `1`）。

---

## check_raw_html.py

### 目的

Wiki ページ本文（frontmatter を除く）に生 HTML タグ（`<script>`・`<iframe>` 等）が混入していないかを検証する。CLAUDE.md・`docs/DesignDoc-publish.md` §8.6 が定める「画像・動画・YouTube の埋め込みは標準 Markdown 構文 `![alt](path-or-url)` のみで行う」という設計の下では、ページ本文が生 HTML タグを必要とする正当なユースケースは存在しない。一方 Quartz コアは `remarkRehype(..., { allowDangerousHtml: true })` を常時有効にしており、`enableInHtmlEmbed`（Obsidian Flavored Markdown プラグインのオプション）の値に関わらず生 HTML を常にそのまま HTML 出力へ通す。経路A（`docs/DesignDoc-pipeline.md` §6.3）では `review_status: pending` の LLM 生成ページが人間レビュー前に一旦 main マージ・公開されるため、ingest 元文書に埋め込まれた悪意ある HTML（間接プロンプトインジェクション等）や LLM のハルシネーションで生 `<script>`/`<iframe>` がページ本文に混入すると、レビュー前に公開サイトで実行されうる。本スクリプトはこれを `wikicommit-merge` のブロッキング品質ゲートとして防ぐ。

### 使用場面

- `wikicommit-merge` Skill：品質ゲートとして変更ファイルを対象に実行
- `wikicommit-status` Skill：Step 3。引数なしで全ページに対して実行し、`ERROR:` 行だけを拾う（冒頭の「merge の blocking な 3 本は status が全ページに走らせる」節）

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
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。research guidance が渡されなかった場合のみ）。`ORPHAN:` 行のみを使い、`DUPLICATE:` 行は使わない — 両ページとも実在するので欠けているものが無く、新しいソースでは解消しないため。**このとき終了コード 1（重複あり）は失敗ではない**: `wikicommit-merge` が同じ終了コードをブロッキングとして扱うのは重複がマージを止めるからであり、俯瞰とは無関係

### コマンド

```
python .wikicommit/scripts/check_orphans.py
```

### 定義

**orphan（孤立ページ）**: `.wikicommit/entity/` 内のどのページからも `[[Type/slug]]` 形式でリンクされていないページ。

`ORPHAN:` 行にはそのページの `sources`（`path`／`url`／`author`）を添える。孤立の次に問う価値があるのは「どのソースが作ったか」であり、「他に 1 ページも作っていないソース由来のページが孤立しやすい」という仮説（1 リポジトリの観察に基づく。構造を述べるソースは定義上あらゆるページにリンクする側なので半ば同語反復でもある）は、出自を印字することでそもそも検証が可能になる。`sources` を持たないページは `(no sources)` と出す。

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

`.wikicommit/entity/` 全体を走査し、`[[Type/slug]]` で参照されているが、どの言語にも実体ページが存在しない slug（wanted page）を集計する。あわせて、実体が無いのは Type セグメントの取り違えが原因である（同じ slug が別 Type に実在する）ものを `TYPE_MISMATCH` として分離する。`check_orphans.py` と対になる設計: orphan が「被リンクゼロのページ」を検出するのに対し、本スクリプトは「リンクはあるが実体がないページ」を検出する。`check_wikilinks.py` は「参照先ページが存在しない」を WARNING にとどめるので、その集計・可視化を本スクリプトが担う。

### 使用場面

- `wikicommit-status` Skill：知識ベース全体の健全性確認
- `wikicommit-collect` Skill：Web候補探索のクエリ群のうち 1 パス分の検索語として（`WANTED:` 行のみを使い `TYPE_MISMATCH:` 行は使わない — 後者は実体が別 Type に在るので欠けているものが無く、必要なのは新しいソースではなくリンク 1 語の修正であるため）。取得失敗・`WANTED:` 0 件のときは黙って飛ばし、実行をブロックしない
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ）。同じ `WANTED:` 行を、探索語ではなく「Wiki 自身が書きたいと表明した穴」として着眼点の根拠に読む。引数なし実行では上の探索語用途と同じ実行の中で両方が要るが、両者の間に `.wikicommit/entity/` へ書き込む手順は無いため、Step 3.5 が読んだ出力を Step 5 が再利用する（走査は 1 回でよい）

### コマンド

```
python .wikicommit/scripts/check_wanted_pages.py
```

引数なし。常に `.wikicommit/entity/` 配下の全 `.md` ファイル（`assets/` を除く）を対象とする。

### 処理フロー

1. `.wikicommit/entity/` 配下の全ページから `[[Type/slug]]` パターンを抽出し、`Type/slug` をキーに参照元ページのパスを集計する（同一ページから同じキーへの複数回のリンクは1件として数える）
2. 同時に、`.wikicommit/entity/<lang>/<Type>/<slug>.md` が存在する全ての `Type/slug` キーを、言語を問わず「実体あり」として集計する（`status: removed` のページも実体ありとして扱う — 削除済みページへのリンクは `check_wikilinks.py` の ERROR ケースの管轄であり、本スクリプトの対象外）
3. 参照されているが実体なしの `Type/slug` のうち、**同じ slug が別の Type に実在するもの**を `TYPE_MISMATCH` として分離して報告する。判定は `check_wikilinks.py` と同じ `_wikilink.py` の共有関数（`build_slug_type_index()` / `other_types_for_slug()`）で行うため、除外規則（`index.md`・`status: removed` ページを候補にしない）・探索範囲（言語を問わない）も同一になる
4. 残りを wanted page として報告する

`TYPE_MISMATCH` を `WANTED` に混ぜない理由は、**両者が要求する行動が正反対だから**である。`WANTED:` は「これから書くべきページ」の一覧として `wikicommit-status` に集計されるが、Type 違いのものはそのとおりに作ると既存ページと内容の重複した 2 ページができ、しかも `check_orphans.py` の重複判定（同一 lang 内の title + type 一致）は `type` が異なるため検出しない。正しい対処は参照側のリンクの Type セグメントを直すことで、実体を作ることではない。

既知の限界: WikiLink 構文が一度も使われていない地の文言及（太字のみ等）は対象外。

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

`wikicommit-synthesize` が出力したページの `derived_from`（`{path, source_commit}` の配列）各エントリについて、出自ページの `source_commit` と現在 HEAD コミットを比較し、陳腐化した合成ページを検出する。`check_translation_status.py` の `STALE`/`MISSING_SOURCE` ロジック（単一の `translated_from`/`source_commit`）を配列用に切り出した別スクリプト（翻訳陳腐化スクリプトに依存させないため、`check_translation_status.py` を改修せず別に持つ）。

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

## read_policy.py

### 目的

`.wikicommit/source-policy.md` と `.wikicommit/entity-policy.md` は、本文全体をコメントアウトした記入例として配布される。設計（`docs/DesignDoc-data.md` §3.4・§3.5）は「本文が空・またはテンプレートのコメントのままなら散文方針は無いものとして扱う」と定めており、その判定を本スクリプトが行う。読む側の SKILL.md は「いま読んだ本文が配布時のコメントのままか」を LLM に判定させない — 完全に決定論的に判定できる操作を instruction として表現すると、非決定論的な失敗モードを持ち込む。

**しかも誤りの向きが片側に寄っている**。両ファイルの記入例はすべて「除外を促す」内容（一次資料を優先する・個人ブログを取り込まない・非公人・実在の未成年者・係争中の事案）であり、誤適用は常に「書かれるはずだったものが書かれない」方向にしか働かない（実例は `docs/DesignDoc-data.md` §3.5）。

### 判定規則 — 「HTML コメントは方針ではない」

本スクリプトが適用する規則は「配布時の記入例か」より単純で、**どの版が配布したかに依存しない**:

両テンプレートは記入例を HTML コメントに入れており、どちらも「自分の方針を書いたらこのコメントを消せ」と本文自身が指示している。人が書く方針は普通の散文である。したがってコメントを除去し、残ったものが方針である。**どの版で初期化されたリポジトリにも移行は要らない** — どの版の本文もコメントだからである。

`<!-- wikicommit:example ... -->` は配布した記入例を明示的に識別するマーカーで、コメント除去だけでも結果は同じだが、(1)「これは WikiCommit のものであって利用者のものではない」を grep 可能にし、(2) 本文が全部コメントだった場合を「空」ではなく「コメントの中にある」と報告する 2 つの理由（マーカー付きの記入例か、利用者が自分で開いたコメントか）に分けられる。**ただしマーカー付きの記入例が「誰も触っていない」のか「`<!--` を消さずにその場で書き換えた」のかは区別できない** — 両者はディスク上で同じ形になり、区別するには配布した版と突き合わせることになって、規則を版に依存させないという上の決定と衝突する。そのため両方の `NONE:` とも「コメントの中の方針は読まれない」ことを述べる文言にしてある。黙って無視される方針は本スクリプトが消そうとしている失敗そのものだからである。

### 使用場面

- `wikicommit-generate` Skill：Step 0（`source-policy.md`）・処理フロー冒頭（`entity-policy.md`）
- `wikicommit-collect` Skill：Step 2.5（`source-policy.md`）

### コマンド

```
python .wikicommit/scripts/read_policy.py <policy-file>
```

### 処理フロー

1. ファイルが無い・読めない場合は `NONE:` を出して終了する（**エラー終了しない** — 方針が読めないことを、無いことと同じ形で報告する。呼び出し側がどう失敗したかで分岐しなくて済む）
2. 先頭の YAML frontmatter を落とす。**frontmatter には一切触れない** — `exclude_domains` は `check_extraction_quality.py` が、`exclude_living_persons` はそれを適用する側が、`rejected:` / `index_only` は `wikicommit-generate` Step 0 が、それぞれ独立に読む
3. `<!-- wikicommit:example ... -->` を除去する。これで空になれば「記入例のまま」
4. 残りから HTML コメントをすべて除去する
5. 何か残れば `POLICY:` 行に続けてその散文を出力し、残らなければ `NONE:` と理由を出力する

### 出力フォーマット

```
POLICY: .wikicommit/source-policy.md
Prefer primary sources.
Do not take in personal blogs.
```

```
NONE: .wikicommit/source-policy.md states no prose policy — the body is still the worked example this file ships with — if you wrote your policy inside that comment, move it outside the <!-- --> so it is read
NONE: .wikicommit/entity-policy.md states no prose policy — the body is empty
NONE: .wikicommit/source-policy.md states no prose policy — every line of the body is inside an HTML comment
NONE: .wikicommit/source-policy.md is not present, so there is no prose policy
```

### 既知の限界

**方針をコメントの中に書いた場合は届かない**。上記の 1 つ目・3 つ目の `NONE:` がその状態を名指しするが、それを読むのは実行の出力であり、人が見ていなければ気づかれない。**配布時の記入例をその場で書き換えた場合（`<!-- wikicommit:example` を残したまま中身を書き換えた場合）と、誰も触っていない場合は、ディスク上で同じ形になるため区別できない** — どちらの版が配布したかに依存しない規則を採った以上これは原理的な限界であり、1 つ目の `NONE:` は区別できない旨を両方書く形にしてある。`check_distribution_freshness.py` に `UNTOUCHED:` 相当の所見を足すことはしない — 両ファイルは `compare="frontmatter_keys"` で本文を見ない設計（本文はユーザーのものなのでバイト差分は常に点灯する）であり、しかも記入例のままであることは init 直後の**大半のリポジトリで正常な状態**なので、足せば常時点灯して読まれなくなる所見になる。

**`config.yml` は対象外**。コメント 25 行は純粋に人間向けで、LLM が使うのは `theme` / `primary_lang` / `max_retries` / `base_types` の**値だけ**である。`config.yml` のコメントは方針として誤適用されうる散文ではないため、同じ欠陥を持たない（値だけを返すスクリプトに委譲してもトークンの節約は小さく、読む Skill がほぼ全部なので変更面積が最大になる）。

**`.wikicommit/review-rules.md` も対象外**。あちらは `update: overwrite` で WikiCommit 自身の規律を持ち、記入例ではない。

### 終了コード

- 常に `0`（読み取り専用のレポート。ファイルが無い・読めない場合も含む）

---

## match_index_only.py

### 目的

`.wikicommit/source-policy.md` の `index_only:` に URL が該当するかを判定する。エントリは 2 形あり、形が意味を決める — パスが無ければ**ドメイン**（そのホスト全体）、パスがあれば**ページ**（その 1 ページ）。この照合は `wikicommit-collect` Step 5 と `wikicommit-generate` Step 0 の両方が要る。2 か所の散文に書くと別々にずれる余地があるため、決定論的な照合をここに 1 つだけ置く。設計判断の全体は `docs/DesignDoc-data.md` §3.4「`index_only`」。

### 使用場面

- `wikicommit-collect` Skill：Step 2.5（`list-pages`。能動的に掘るページのエントリを得る）・Step 5（`match`。検索結果を Step 5.5 へ振り分ける）
- `wikicommit-generate` Skill：Step 0（`match`。引数の URL が索引なら登録前に確認を求める）

### コマンド

```
python .wikicommit/scripts/match_index_only.py match <url>
python .wikicommit/scripts/match_index_only.py list-pages
```

### 正規化

| エントリ | 正規化 | 照合 |
|---|---|---|
| ドメイン | スキーム・ポート・先頭 `www.` を落とし小文字化 | ホストの完全一致（サブドメインは覆わない。`exclude_domains` と同じ） |
| ページ | 上に加えフラグメント・末尾スラッシュを落とし、パスとクエリをパーセントデコード。**クエリは保持** | ホストとパス＋クエリの完全一致 |

正規化後にホスト以外が何も残らないエントリがドメインである。

### 出力フォーマット

```
INDEX_ONLY: https://github.com/example/awesome-foo/ (matches https://github.com/example/awesome-foo, page)
OK: https://github.com/example/some-tool is not listed under index_only
PAGE: https://github.com/example/awesome-foo
SUMMARY: index_only_pages=1
```

ファイルが無い・キーが無い・値がリストでない場合は該当なしとして扱う。**ファイルが在るのにパースできない場合は stderr に `WARNING:` を出す**（`check_extraction_quality.py` が `exclude_domains` について採るのと同じ理由 — `rejected:` への追記ミス 1 回で一覧全体が黙って無効化されないため）。

### 終了コード

- 常に `0`（接頭辞が答えである）

---

## match_existing_names.py

### 目的

Pass 2c は「型と slug が同じ既存ページがある」ときに `action: update` にするが、それだけでは、既存ページが**別名**として持つ名前で別のソースがその概念を呼ぶと、新しいページが作られる（例: `function-calling` と、別名 "Function calling" を持つ `tool-use-design-pattern` の並存）。型テンプレートの「別名は別ページにせず `aliases` に書け」は書く側の規則であり、照合する側にも対応する規則が要る — 片側にしか書かれない境界は片側にしか効かない。本スクリプトがその照合を行う。

照合は決定論的に書けるので、指示文ではなくスクリプトにする。副次的に、既存ページの別名を LLM のコンテキストへ載せる必要も無くなる。

### 使用場面

- `wikicommit-generate` Pass 2c（`references/pass2c-entities.md`）。slug による `existing_path` の判定の直後に 1 回呼ぶ

### コマンド

```
python .wikicommit/scripts/match_existing_names.py [--lang <lang>] <<'JSON'
[{"title": "<title>", "type": "schema:<Type>", "aliases": ["..."]}, ...]
JSON
```

`--lang` の既定は `primary_lang`。エンティティの `aliases` は任意。

### 処理フロー

1. `.wikicommit/entity/<lang>/` の全ページ（`index.md`・`status: removed` を除く）の `title` と `aliases` を、`normalize_name()`（NFKC・casefold・連続空白の単一化。`check_unlinked_entity_mentions.py` / `check_recurring_characters.py` と共有）で正規化して索引にする。型はパスから取る
2. 各エンティティの `title` と `aliases` を同じ正規化で引き、同じ型のページと他の型のページに分ける
3. 同じ型が 1 件なら `SAME`、2 件以上なら `AMBIGUOUS`、他の型の一致は `OTHER_TYPE`（`SAME` と併記しうる）、どれも無ければ `NONE`

### 決定事項

| 論点 | 決定 |
|---|---|
| 照合の強さ | **正規化後の文字列一致のみ**。意味が近いだけの名前は一致としない — 同義かどうかは人がページを見て判断する |
| 型が違う一致 | `update` にしない（型をまたいで書き換えない）。Completion Notice に候補として出す |
| 複数ページへの一致 | どちらにも `update` しない。Completion Notice に出す（統合するかは人の判断） |
| 対象の言語 | `primary_lang` のみ。原文は `primary_lang` で書かれ、翻訳ページは `aliases` を持たない（`/wikicommit-translate` が写さない） |
| 一致したが別物（同名の別の版・号・同名異人） | 判断は LLM に任せる（年・版・報告書番号の食い違いはソースに書かれている）。**その判断を `## Generation Notes` と Completion Notice に既存ページのパスとともに残す** — 例外を黙って通すと照合を入れた意味が半分失われる（`wikicommit/world-of-work-wiki` の ILO 報告書 3 本は別ページが正しかったが、系列であることを人が知る経路が無かった） |
| `properties:` による決定論的な補助 | 入れない。`datePublished` 等が既存ページに書かれている保証が無く、書かれていない場合に何も言えない判定を足すことになる |
| LLM のコンテキスト | 既存ページの別名は渡さない。照合をスクリプトが行うので、既存ページ一覧は「タイトル＋パス」で足りる |

### 出力フォーマット

```
SAME: 0 "Function calling" -> .wikicommit/entity/en/DefinedTerm/tool-use-design-pattern.md (matched alias "Function calling")
AMBIGUOUS: 1 "Tool use" -> <path>, <path> (same type; several pages answer to this name)
OTHER_TYPE: 2 "Claude Code" -> .wikicommit/entity/en/SoftwareApplication/claude-code.md (type SoftwareApplication, not DefinedTerm)
NONE: 3 "Vibe coding"
SUMMARY: entities=4, same=1, ambiguous=1, other_type=1
```

### 終了コード

- `0`: 照合した（一致の有無に関わらず）
- `2`: 標準入力が JSON のリストでない

**既存の重複ページは扱わない**。既に並存しているページは、人が統合するまで残る（`check_name_collisions.py` が報告する）。

---

## check_distribution_freshness.py

### 目的

インストール済みの配布物が、`wikicommit-init` Skill が現在同梱しているテンプレートと一致しているかを報告する。命名は `check_ingest_freshness.py` / `check_derivation_freshness.py` と同じ「記録されたものが今も最新か」の系譜だが、**副作用を持たない**（`check_ingest_freshness.py` と異なり管理ファイルを書き換えない）。

wiki リポジトリの中身は 3 種類に分かれ、性質の違う更新パターンに対応する。

| 中身 | 例 | 更新のされ方 |
|---|---|---|
| ユーザーが書いたもの | `entity/`・`config.yml`・`schema/` | 触らない（人間が判断する） |
| WikiCommit 自身の配布ペイロード | `.wikicommit/scripts/`・`quartz-plugins/`・2 つの workflow・`*.cjs` | 再 init で更新される |
| 別経路で生成されるもの | `quartz/`・`package-lock.json` | 対象外 |

2 番目は再 init（と `/wikicommit-update`）で更新されるが、それを走らせなければ古い版で init したリポジトリは古い workflow・古いプラグイン `dist/`・古いビルドスクリプトを黙って使い続ける。本スクリプトは**そのリポジトリが更新を要するかを見る側**を担う。

**分類表は持たない**。どのパスがどの扱いかは `.claude/skills/wikicommit-init/scripts/_root_outputs.py` の `update` 列が唯一の情報源であり、`init.py` のコピーと `print_next_steps.py` の `git add` 案内も同じ列から導かれる。ここに 2 つ目のリストを持つと、その列が消したドリフトを作り直すことになる。

### 使用場面

- `wikicommit-status` Skill：Step 11（Step 4 と同じく、ページ単位の集計ではなくインストールの状態を見るチェック）
- `wikicommit-generate` / `wikicommit-merge` Skill：Step 0（`--only .wikicommit/scripts`。実行開始時の版ずれ検査。下記「2 つの配布物の版ずれを、実行の開始時に見る」）

### コマンド

```
python .wikicommit/scripts/check_distribution_freshness.py [--variant <none|quartz_only|quartz_pages>] [--repo-root <path>] [--only <path>]
```

`--variant` 省略時は自動判定する（`quartz.config.yaml` があれば quartz、加えて `.github/workflows/deploy.yml` があれば quartz_pages）。判定に記録された設定を使わないのは、それを記録している場所が無いためで、代わりに各フラグが実際に足すファイルそのものを見る。

`--only <path>` は `_root_outputs.py` の 1 エントリだけに絞る（下記「2 つの配布物の版ずれを、実行の開始時に見る」）。**`--only` の値がどのエントリにも一致しない場合は `WARNING:` を出す** — 黙って 0 件を返すと、打ち間違いが「差分なし」と区別できなくなり、このフラグが捕まえようとしている silent wrong answer をこのフラグ自身が作ることになる。**実在するエントリでも、このスクリプトが比較しないもの（`update: skip`・テンプレートを持たないもの）を名指した場合は同じく `WARNING:` を出す** — 出力は文字どおり同じ「クリーンな `SUMMARY:`」であり、区別する材料が読み手に無いため（`quartz_pages` 変種では 9 エントリがこれに当たる）。したがって呼び出し側は `OUTDATED:` だけでなく `MISSING:` / `ORPHAN:` / `WARNING:` も報告する（両 SKILL.md がこれを明記する）。あわせて `--only` 指定時は `VERSION:` 行を出さない（`synced` は再 init しただけのリポジトリで古いまま残るため、全体レポートの中でバイト比較と並んでいるぶんには無害だが、1 行だけの検査では最も目立つ出力が誤っていることになる）。

**2 つの配布物の版ずれを、実行の開始時に見る**: WikiCommit がユーザーのリポジトリに置くものは 2 つあり、**別々のコマンドで更新される** — 指示書（`.claude/skills/`）は人間が `npx skills add` を叩き、道具（`.wikicommit/scripts/`）は `/wikicommit-update` または `/wikicommit-init --no-overwrite` が更新する。片方だけ更新すると「新しい指示書 ＋ 古い道具」になる。版ずれの現れ方は 3 通りで、危ないのは 3 番目だけである:

| 指示書が変わった内容 | 古い道具の反応 |
|---|---|
| 新しいオプションを付けて呼ぶ | `unrecognized arguments` で落ちる → その場で分かる |
| 新しいスクリプトを呼ぶ | ファイルが無い → その場で分かる |
| **既存のオプションの参照先だけが変わった** | **落ちるとは限らず、落ちても見当違いの場所を指す**（例: 古い `record_run.py --token` が手順書の旧ディレクトリを見て、正しく読んだ実行を `token: missing` と記録する） |

規則:

- **検出は本スクリプトの generic な比較で行い、版ずれ専用の検出器を作らない**。この比較は**自分自身が古くても正しく報告できる** — 比較の基準（`_root_outputs.py` とテンプレート本体）がどちらも新しい側にあるためである。特定の期待（定数・パス・フォーマット）を埋め込んだスクリプトは自分の陳腐化を診断できない（古い版は新しい期待を知らない）
- **呼ぶのはテンプレート側の写しであり、`.wikicommit/scripts/` の写しではない**（両 SKILL.md がこれを明記する）。後者は**まさに古いかもしれない半分**であり、そこから呼ぶと `--only` が `unrecognized arguments` で落ちて、検出器自身が上表の 1 行目になる。テンプレート側の写しはそれを呼ぶ SKILL.md と常に同じスナップショットから来る（両方 `npx skills add` が更新する）。`/wikicommit-update` Step 2 も同じフォールバックを持つ。**一般則として、検出器もそれを呼ぶ指示も `npx skills add` が更新する側に置く**。したがって `record_run.py start` の中に検査を入れることもしない — 古い半分に同梱された検出器は、必要なときに限って発火しない
- **止めない。警告に留める**。差分があることは分かっても、その差分が今回の実行に効くかが機械には分からない。版ずれの大半は無害（無関係なスクリプトにオプションが 1 つ増えただけ等）であり、そこで generate を止めるのは防ごうとしている失敗より悪い（`wikicommit-generate` の `review-rules.md` 検査が停止するのは、帰結が既知かつ全面的だからである）
- **対象は `wikicommit-generate` と `wikicommit-merge` の 2 つ**。基準は依存するスクリプトの本数ではなく**位置**である。generate は主経路の**最も早い地点**で、中断コストがほぼゼロで、`--token` / `checkpoint` という期待を引数に埋め込む呼び出しを持つ唯一の Skill でもある。merge は**全書き込み経路の合流点**（`fix` / `remove` / `review` / `translate` / `synthesize` / `reconcile` はすべて最後にここへ来る）で、品質ゲートを走らせる既定ブランチ手前の最後の門である。残りを外すのは全部 merge に合流するからである。merge 側の版ずれの誤りの向きは generate 側と逆で、古い品質ゲートは**落とすべきものを通す**（偽陰性）。generate → merge を続けて叩くと同じ検査が 2 回走るが、黙っている場合は何も出力しないので実害は薄い
- **`--only .wikicommit/scripts` に絞る理由は報告の関連性であり、速度ではない**（全体を比較しても LLM 推論の隣では無視できる）。実行開始時に `quartz-plugins`・workflow・`*.cjs` の版ずれを報告しても、読み手はいまその場で何もできず（帰結は公開サイトと CI であって今回の実行ではない）、`review` 側（`config.yml`・`schema/`）は差分があるのが正常な場合すらある。読まれない行を hot path に増やさない
- **帰結を述べる文は `.wikicommit/scripts` の `OUTDATED:` にのみ付ける**（`_consequence(path)`。`quartz-plugins` の帰結は「公開サイトが古い」であって「記録が誤る」ではない）。**その文は帰結を述べて終わり、対処のコマンドを名指ししない** — この検査を走らせる呼び出し元には `/wikicommit-update` 自身（Step 2・Step 7）が含まれ、Step 7 ではいま走った更新が効かなかったことの報告なので、同じコマンドを勧めると失敗した操作の再試行を指示することになる。対処の指示は各 SKILL.md が文脈付きで持つ。`--only` の有無で文を分岐させることも、`--caller` フラグで分岐させることもしない — 前者は `--only` を付けない `/wikicommit-status`（案内が正しい）と `/wikicommit-update` Step 7（案内が誤り）が同じ側に落ちるので条件として成立せず、後者は 1 文の分岐のために受け皿を配ることになる。`tests/test_check_distribution_freshness.py` が、行が帰結を述べることとコマンドを名指ししないことの両方を固定する
- **`VERSION: synced=` を版ずれの信号に使ってはならない**。`synced` を書き換えるのは `/wikicommit-update` だけで、`/wikicommit-init --no-overwrite` は `.wikicommit/scripts/` を必ず更新する一方 `config.yml` は wholesale でスキップする。**再 init で正しく同期したリポジトリでも `synced` は古いまま残る**ため、ずれていないのにずれていると報告する。バイト比較にはこの誤検知が無く、同一版内の未リリース差分まで捉える
- **README の更新手順だけでは足りない**。README を読むのはインストールする人であって、そのリポジトリで後から `/wikicommit-generate` を叩く人ではなく、無人実行・サブエージェント経由ではそこに読む人がそもそもいない。実行の開始時に機械が見る検査が要るのはこのためである
- **開発リポジトリでは再現できない**。ここでは `.wikicommit/scripts` がテンプレートへのシンボリックリンクであり、2 つの半分が同じファイルなので構造上ずれようがない。`tests/test_check_distribution_freshness.py` の該当テストが一時ディレクトリに実ツリーを組み立てるのはこのためである

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
| `.gitignore` | init が `--quartz` 時に Quartz セクションを追記する |

常に出ている警告は読まれなくなり、差分検出全体が無視されるようになればこの仕組みが機能しない。したがって `review` は**加算的なシグナルでのみ報告する**: テンプレートにあってローカルに無いもの。値を変えたこと・散文を書き換えたことは報告しない。

`compare` の値（`_root_outputs.py` の `COMPARISONS`）:

| `compare` | 何を見るか | 対象 |
|---|---|---|
| `bytes` | バイト一致 | 上記 5 つ以外の全て |
| `yaml_keys` | テンプレートにあってローカルに無い YAML キー | `config.yml`・`quartz.config.yaml` |
| `frontmatter_keys` | 同、frontmatter の `wikicommit:` 直下 | ポリシーファイル 2 つ |
| `lines` | 同、空行とコメントを除いた行 | `.gitignore` |
| `none` | 比較しない | `update: skip` のみ |

**`lines` の簡約は `_root_outputs.py` 側にも写しがある**。`init.py` / `print_next_steps.py` が「このリポジトリの `.gitignore` に WikiCommit のパターンが揃っているか」を判定するのに同じ包含判定を要するが、**Skill 内スクリプトから `.wikicommit/scripts/` を import することはできない**（`add_source.py` が同ディレクトリからの import を 1 つも持たない設計制約と同じ。`docs/DesignDoc-skills.md` §11.5）。`remove_page.py` が `normalize_entity_prefix()` を複製しているのと同じ扱いとし、2 つの写しを許容する。**簡約そのもの（空行とコメントを落とす）は同一だが、2 つは同じ答えを返す関数ではない** — `_root_outputs.py` 側は (1) 報告が対処の手順を兼ねるため行の順序を保ち、(2) **variant に応じて `gitignore-quartz.txt` も要求集合に含める**（`content/` / `.quartz-cache/` / `quartz/public/`）。こちら側は下記「既知の限界」のとおり `templates/.gitignore` しか見ないため、`--quartz` リポジトリで Quartz 側のパターンが欠けていても `OUTDATED` にはならない。片方を他方に寄せて統合しないこと。

**キーの比較は再帰的に行う（ドット区切りのパス）**。`quartz.config.yaml` のトップレベルキーは `configuration`/`layout`/`plugins` の 3 つで今後増えないため、トップレベルのみの比較では意図した用途（例: `configuration:` の下の `pageTitleSuffix`）に対して恒久的に何も報告しない。

**テンプレート側の `{NAME}` プレースホルダーは比較前に無害化する**。YAML はクォートされていない `{THEME}` をフロー マッピングとして読むため、`theme: {THEME}` は「`theme.THEME` という入れ子キー」に見え、実際の値を持つ config.yml には当然そのキーが無い。無害化しないと、**init 直後のリポジトリが自分の `config.yml` と `quartz.config.yaml` を永久に `OUTDATED` として報告する**。`options: {}` のような本物の空マッピングは正規表現に一致しないためそのまま解釈される。**置換先は空文字列ではなく素のスカラー**にする — プレースホルダーは常に裸で書かれているとは限らず、`config.yml` の 1 行目は `wikicommit_version: "{VERSION}"` とクォートの内側にあるため、`""` で置換すると引用符が 4 つ並んで**テンプレート全体が YAML として読めなくなる**。そうなるとテンプレート側のキー集合が空になり、`テンプレート − ローカル` も空になるので、比較が止まっているのに正常な結果に見える。テンプレート側のパースに失敗した場合は `WARNING:` を 1 行出す（空のキー集合は「上流で何も増えていない」と見分けがつかないため）。

**リストへも降りる**（`_key_paths()`）。キーで止めると `plugins` 以下が `plugins` の 1 本のパスに畳まれ、プラグインの追加・削除・ローカルビルドへの差し替えも、`layout.byPageType.*.exclude` への項目追加も、既存リポジトリに一切報告されない。**取り込むべき項目を列挙するのではなくリストそのものを比較する** — 列挙は 1 つ欠けると静かに落ちる。降下には 3 つの制約がある:

| 制約 | 内容 | 外したときに何が起きるか |
|---|---|---|
| 1 | **加算のみ**（テンプレート − ローカル） | 減算方向にすると、ユーザーが足したものを全部報告する |
| 2 | **位置ではなく識別子で照合する**（スカラーは値そのもの、マッピングは `source` の値） | 上流がプラグインを 1 本足した瞬間にすべての要素がずれる |
| 3 | **リスト要素のマッピングの内側へは降りない** | `enabled` を見ると giscus を意図的に有効化したリポジトリが誤検知になり、`options` を見るとフッターの `{REPO_URL}` がテンプレート側でプレースホルダーのままなので必ず差分になる |

したがって `plugins` について見るのは**どのプラグインが在るか**だけで、`enabled` / `order` / `options` は見ない。**識別子は `source` のみとし、`name` / `id` を推測で足さない** — テンプレート群でマッピングのリストは `plugins` 1 本だけであり、2 つ目の候補は消費者のいない受け皿になる。識別子を持たない要素は**比較せず飛ばす**（劣化の向きが沈黙であり、ノイズにはならない）。

`_key_paths()` は `yaml_keys` / `json_keys` / `frontmatter_keys` の 3 モードが共有するが、加算的比較はテンプレート側が持つものしか報告しないため、テンプレート側にリストが無ければリスト降下は何も変えない（`config.yml` では `schema.base_types` が上流で基本型を足したときに報告される）。

### `quartz.config.yaml` の 2 つは、テンプレート比較では原理的に答えられない

上のリスト降下でも届かない 2 点がある。**テンプレート側が `{LOCALE}` / `{REPO_URL}` というプレースホルダーであり、照合すべき上流の literal が存在しない**ためである。一方その正解は init が**既存の決定論的な関数で計算している**。したがって問いは「テンプレートと違うか」ではなく「**いま init が書くとしたら、この値になるか**」になる。

| 検査 | 正解の出どころ | 報告する形 |
|---|---|---|
| `configuration.locale` の**言語サブタグ** | `quartz_locale_for(config.yml の translation.primary_lang)` | `configuration.locale is en-US, but translation.primary_lang is it, which init writes as it-IT` |
| フッターの `links.GitHub` | `git remote get-url origin` を `owner/repo` に正規化したもの | `the footer's links.GitHub points at jackyzha0/quartz, not at this repository (wikicommit/decameron-wiki)` |

**`locale` は言語サブタグだけを比較する。** 地域サブタグは `init.py` 自身のコメントが「A wiki that wants a regional variant edits the one line by hand」と書いている正当な手編集であり、そこまで比較すると `en-GB` を選んだ利用者を毎回叱ることになる。**リモートの URL 形式も同様に利用者のものである** — SSH 形式（`git@github.com:owner/repo.git`）と HTTPS 形式を別のリポジトリと読むと、SSH で clone した Wiki が軒並み点灯する。末尾の `.git` とスラッシュも落としてから比較する。

**`pageTitle` / `pageTitleSuffix` は同じ扱いにしない。** ディレクトリ名由来の値は init の**既定値**であって正解ではなく、Wiki が表示名を変えるのは正当な編集である。比較すると利用者を叱る側に倒れるため、これは手作業として残る。

**置き場はこのスクリプト側であり、`_root_outputs.py` にフィールドを足さない。** あの一覧は `init.py` と `print_next_steps.py` も読むが、どちらも「値の検査」を使わない — 3 消費者のうち 1 つしか読まないフィールドを共有リストへ入れることになる。同ファイルには既に同型の前例がある（`_consequence(path)` が `.wikicommit/scripts` だけに帰結の 1 文を付けている）。同じくパスで分岐する小さなディスパッチとして書く。

**どちらも `OUTDATED:` 行として出す**（新しい接頭辞を足さない — `wikicommit-status` / `wikicommit-update` 側の読み取りを変えずに済む）。そのため**1 エントリが複数の `OUTDATED:` 行を出しうる**: 加算的なキー比較と値の検査は同じファイルについて別の問いに答えており、1 行に畳むと一方が他方を隠す。`SUMMARY:` の `outdated` は行数を数える。

`quartz_locale_for()` は `.claude/skills/wikicommit-init/scripts/init.py` にある。**Skill が未インストールなら 2 検査とも黙って飛ばす** — `_load_root_outputs()` と同じ非ブロッキングな劣化であり、`primary_lang` が読めない・`locale` が無い・`GitHub` エントリが無い（init が `links: {}` に潰した場合を含む）・remote が無い、のいずれでも同様である。

**Skill は在るのに `init.py` が読めない場合だけは黙らない。** そこへ到達した時点で「未インストール」は消えている（`check()` が自分の `WARNING:` を出して先に return する）ので、残る原因は WikiCommit 自身の問題 — 壊れた `init.py`、または `quartz_locale_for()` を持たない古い Skill ツリー — であり、症状は**検査が止まったまま `SUMMARY: outdated=0` が「同期済み」の顔をする**ことだけになる。`_yaml_keys()` がテンプレートのパース失敗に対して採っているのと同じ扱いで、どの検査が走らなかったかを `WARNING:` で述べる。**関数は属性として取り出してから呼ぶ** — 属性が無いだけで `AttributeError` を投げると、検査 1 本のために**レポート全体が traceback で落ち**、このスクリプトの「終了コードは常に 0」という契約が破れる（`npx skills add` と `/wikicommit-init` が 2 つのツリーを別々に更新する以上、版ずれはこのファイル自身が `_SCRIPTS_CONSEQUENCE` で想定している状態である）。**このとき止まるのは `locale` の検査だけで、フッターの検査は走る** — あちらが読むのはローカルの config とこのリポジトリ自身の remote だけで、`init.py` に依存しないためである。

### ORPHAN は `overwrite` のツリーにのみ報告する

`copy_tree` は削除を行わないため、上流でリネームされたスクリプトは旧名のまま残る。これを `ORPHAN:` として報告するが、**対象は `update: overwrite` のツリーに限る** — `.wikicommit/schema/` は `review` であり、テンプレートに無いファイルはユーザーが書いたカスタム型か Pass 2b が追加した型であって孤児ではない。ここを区別しないと `ORPHAN:` 行が正反対の 2 つを意味することになる。

削除は行わない（誤検出時の被害が非対称に大きいため、削除は後続の update フローが人間の確認を取って行う）。

### 劣化の仕方

| 状況 | 挙動 |
|---|---|
| `wikicommit-init` が未インストール | `WARNING:` を 1 行出し `SUMMARY:` 全 0 で終了（`check_property_wikilink_reinforcement.py` が語彙を引けないときと同じ非ブロッキングな劣化）。`.wikicommit/scripts/` は wiki リポジトリにコミットされるが `.claude/skills/` は別途インストールするものなので、無いことは十分あり得る |
| `wikicommit-init` が `.agents/skills/` にだけある（Codex 単独配置） | **未インストールとは扱わない**。Skill ツリーは `_skill_tree.py` の探索順（`.claude/skills` → `.agents/skills`）で引く。`.claude/skills/` 固定にすると、Skill が在るのに別の場所にあることを「無い」と区別できず、上の行の劣化に黙って落ちる |
| `wikicommit_version` が無い | `synced=unknown` と表示する。版は読者向けの情報であり比較を左右しないため、それ以外は通常どおり動く（`wikicommit_version` を書くようになる前に init されたリポジトリが該当） |
| `update` が未知の値 | `review` として扱う。`npx skills add` は `.claude/skills/` を更新するが `.wikicommit/scripts/` は次の init まで古いままなので、**古いスクリプトが新しいリストを読む**組み合わせが起こりうる。表示するラベルも `review` に正規化する — 適用していない扱いを名乗らせないため |

### 出力フォーマット

```
VERSION: synced=0.2.0, installed=0.3.0
OUTDATED: quartz-plugins (overwrite) — 6 file(s) differ from the template
OUTDATED: .wikicommit/source-policy.md (review) — the template has wikicommit: key(s) this file lacks: index_only
OUTDATED: quartz.config.yaml (review) — the template has key(s) this file lacks: layout.byPageType.folder.exclude[comments], layout.byPageType.tag.exclude[comments], plugins[../quartz-plugins/wikicommit-graph]
OUTDATED: quartz.config.yaml (review) — configuration.locale is en-US, but translation.primary_lang is it, which init writes as it-IT
OUTDATED: quartz.config.yaml (review) — the footer's links.GitHub points at jackyzha0/quartz, not at this repository (wikicommit/decameron-wiki)
MISSING: .wikicommit/entity-policy.md (review) — not present locally
ORPHAN: .wikicommit/scripts/check_old_name.py — no counterpart in the template
SUMMARY: outdated=5, missing=1, orphan=1
```

`quartz.config.yaml` が 3 行を占めているのが上記「1 エントリが複数の `OUTDATED:` 行を出しうる」の実例である（リスト要素の欠落・`locale`・フッターのリンク）。

### 既知の限界

`.gitignore` の比較対象は `templates/.gitignore` のみで、`--quartz` 時に追記される `templates/gitignore-quartz.txt` は見ない。後者に追加されたパターンは報告されない。

**`configuration.ignorePatterns` はこのファイルで唯一「ユーザーの内容判断」を持つリストであり、既知の誤検知候補である**。ユーザーが `private` を公開したくて消した場合、既存の 1 行の中に 1 項目が増える形で点灯し続ける。それでも対象に含めるのは 2 つの理由による: (1) `.gitignore` の `compare: lines` が既に同じ性質（ユーザーが消した行を報告し続ける）を受け入れている前例がある、(2) 除外すると小さな列挙を持つことになり、上流が `configuration` にリストを足したときに覆われない。

**ローカル側にしか無いエントリは、どの設計でも構造的に検出できない**。`quartz.config.yaml` のフッターに残っている Discord 行がこれにあたる — 見るには減算比較が要るが、それはユーザーが足したものを全部報告する向きであり、上記の制約 1 が退けたものである。**1 行の手作業として残す**。プラグインの `enabled` / `options` の上流変更も同じく沈黙に留める（制約 3）。

`package.json` は `review` かつバイト比較のため、**init 前から自前の `package.json` を持っていたリポジトリでは毎回 `OUTDATED` が出続ける** — `init.py` はその場合コピーをスキップするので、テンプレートと一致することが構造的にありえない。それでも加算的比較に移さない。加算的比較には `scripts.postinstall` のような既存キーの**値**の変更が原理的に見えず、新しい `*.cjs` が `postinstall` から呼ばれず全 Pages ビルドが失敗する種類の変更を検出できなくなる。軸はこう置く — **ローカルが設計上テンプレートから乖離するファイルは加算的に、テンプレートが全体にわたって正本であるファイルはバイトで比較する**。`quartz.config.yaml` が前者、`package.json` が後者である。

### 終了コード

- 常に `0`（報告のみ、ブロッキングしない）

---

## search_index.py

### 目的

`.wikicommit/entity/` を SQLite FTS5（`trigram` トークナイザ）でインデックス化し、全文検索を提供する。単語境界のない CJK（日本語・中国語）も分かち書きなしで検索できる。`wikicommit-search`・`wikicommit-ask` の両 Skill から共有される（`docs/DesignDoc-skills.md` §11.5）。

### 使用場面

- `wikicommit-search` Skill：キーワード検索
- `wikicommit-ask` Skill：`wikicommit-search` 経由で内部利用
- `wikicommit-synthesize` / `wikicommit-quiz` Skill：関連ページの収集（いずれも `--expand` 経由）

### コマンド

```
python .wikicommit/scripts/search_index.py build
python .wikicommit/scripts/search_index.py query "<query>" [--lang <lang>] [--limit N]
python .wikicommit/scripts/search_index.py query --expand "<語>|<語>" --expand "<語>" [--lang <lang>] [--limit N]
```

`query` は位置引数（空白区切り・暗黙 AND）か `--expand`（複数指定可）のいずれか一方を取る。両方指定・どちらも未指定はいずれもエラー（終了コード 1）— 同じ語に対して 2 つの異なる意味論を持つため、黙って統合すると呼び出し側が指定していない検索を行うことになる。

### `build` サブコマンド

1. `.wikicommit/entity/**/*.md` を走査する（`index.md` と `status: removed` のページは対象外）
2. 各ページから `title`・`lang`・`type`・`tags`・`review_status`・本文（frontmatter を除いた Markdown 全文）・`aliases`（ソースの原語の表記が別名にしか残らない場合があり、翻訳先に無い言語ではそこが唯一の置き場になるため）を抽出する。frontmatter が YAML として解析できない、またはマッピング型でない場合はそのページ全体をインデックス対象から除外する（`status: removed` かどうか判定できないページを誤って検索可能にしないための安全側の挙動）
3. `.wikicommit/.cache/` の中に一意な名前の一時ファイルを作り、そこへ FTS5 仮想テーブル（`tokenize="trigram"`）を作成し投入する。`path`・`lang`・`type`・`review_status` は `UNINDEXED`（全文検索対象外・フィルタ／表示用）。同じファイルに `meta` テーブル（`key`, `value`）を作り、ページ集合の fingerprint（下記）を `key = 'fingerprint'` で記録する
4. すべてをコミットして接続を閉じてから、`os.replace()` で一時ファイルを `search_index.sqlite3` に置き換える（原子的な置き換え。差分更新はしない）。途中で失敗した場合は一時ファイルを消し、既存のインデックスには触れない — 既存ファイルに対して `DROP` → `INSERT` すると、途中で落ちたときに空か途中までのインデックスが残り、fingerprint を持つせいで「最新」と判定されてしまうため。2 つのプロセスが同時に作り直しても、それぞれ別の一時ファイルに書くので壊れない（最後に置き換えた方が残る）
5. `.wikicommit/.cache/` が存在しない場合は作成する。Git 管理対象外（`.gitignore` に `.wikicommit/.cache/` を追加済み）
6. SQLite が `trigram` トークナイザ（SQLite 3.34+、3.38+ 推奨）に対応しない場合、エラーメッセージを出力し終了コード 1 で終了する（一時ファイルは残さず、既存のインデックスにも触れない）

**fingerprint**: `collect_pages()` と同じページ集合（entity ＋ view、`assets/` と `index.md` を除く）について、`(パス, st_mtime_ns, st_size)` を 1 行ずつ並べた列の SHA-256（先頭にインデックスの形式番号 `INDEX_FORMAT` を混ぜる — ページが 1 つも変わっていなくても、列や索引の仕方を変えた版のスクリプトが古い形式のインデックスを使い続けないため。`_build()` の出力の形を変えたら上げる）。ページの追加・削除・編集をすべて捕まえる（削除すると集合から 1 行消える。最新 mtime だけを比べる形では削除を捕まえられない）。`git pull`・`/wikicommit-fix`・`/wikicommit-remove`・Close 同期による `review_status` の書き換えもファイルが変わるので同じように拾う。読むのは `stat()` だけでページの中身は読まない（判定は `query` のたびに走るため）。`git checkout` や clone で mtime だけが変わると中身が同じでも作り直すが、誤りは「全件の作り直しの分だけ余計にかかる」側に倒れるので受け入れる

### `query` サブコマンド

1. 現在のページ集合の fingerprint を計算し、インデックスの `meta` テーブルに記録された値と比べる。インデックスが無い・`meta` テーブルが無い（fingerprint を持たない古い形式）・読めない・値が違う、のいずれでも先に作り直してから検索する。既存のインデックスを作り直したときは `NOTE: search index was stale (<理由>); rebuilding` を 1 行出す（`SUMMARY:` 行の形式は変えない — 呼び出し側は `hits=` を読んでいる）。fingerprint を読む接続は作り直しの前に閉じる（Windows では開いているファイルに対する `os.replace()` が失敗するため）。別プロセスが同時に開いていて置き換えに失敗した場合は、一時ファイルを消し、`WARNING:` を出して古いインデックスのまま検索する（検索は止めない）

   **鮮度は `query` 自身が確かめる**。generate / translate / synthesize の最後に `build` を呼ばせる形は採らない — 指示に頼る形で手順の末尾が落ちうるうえ、`git pull`・`/wikicommit-fix`・`/wikicommit-remove`・Close 同期には届かない（古いインデックスでの 0 件は「Wiki にその知識が無い」と区別できない）。**`query` のたびに必ず作り直すこともしない** — search / ask は言語ごとに `query` を何回か呼ぶので 1 回の実行で数秒かかる
2. `MATCH` 演算子で全文検索する。MATCH 式の組み立ては指定形式で分かれる:
   - **位置引数**: 空白区切りの各語を個別にフレーズクエリとしてクォートし、暗黙の AND で連結する（ユーザー入力をそのまま FTS5 クエリ構文として解釈すると `-`・`"` 等でクエリ構文エラーになりうるため語ごとにクォートする。クエリ全体を単一フレーズにすると隣接した語順の完全一致でしか検索できなくなるため、キーワード検索として機能するよう語ごとに分割する）
   - **`--expand`**: 各 `--expand` の値を `|` で分割して 1 グループとし（各語は前後の空白を除去し、内部の連続空白も 1 個の半角空白に潰す — 複数語の語は 1 つの隣接フレーズとして扱う一方、語の中に改行が残ると `SUMMARY:` 行が複数行に割れて、行単位で `hits=` を読む呼び出し側が値を取り落とすため）、**グループ内は OR・グループ間は AND** の式を組み立てる（`("児童手当" OR "子ども手当") AND ("申請手続き")`）。各語のクォート・`"` の `""` エスケープは位置引数と同一のルールで行う。単一語のグループも含め**すべてのグループを括弧で囲み、明示的な `AND` で連結する** — FTS5 は括弧で囲んだ式と裸のフレーズの並置（`("a" OR "b") "c"`）も、括弧同士の並置も構文エラーとするため、グループが 1 つでも存在する時点で明示的な演算子が必須になる。空白区切りの語を空文字列に潰す・分割記号 `|` 自体を語に含める、といったケースは扱わない（前者は落とし、後者は現実的な検索語に現れないため専用のエスケープ構文を設けない）
   - `trigram` トークナイザは3文字未満の連続文字列からはトークンを作れないため、3文字未満の語はどのページの本文とも絶対に一致しない（クエリ構文エラーにはならず、常に無条件で不一致になる）。この判定は Skill 側（LLM）に委ねず本スクリプトが行う（`docs/DesignDoc-skills.md` §11.5 のスクリプト委譲パターンに従う）。警告の文言は指定形式と、**グループ内に 3 文字以上の語が残るかどうか**で 3 通りに分かれる:

     | 状況 | 出力 | 挙動 |
     |---|---|---|
     | 位置引数の 3 文字未満の語 | `WARNING: query term "<term>" has <N> character(s); trigram search requires at least 3 and this term cannot match anything` | 式から落とさない（FTS5 の暗黙 AND がその語の寄与を無視するため、結果としてヒットは残る） |
     | `--expand` グループ内に 3 文字以上の語が 1 つ以上残る | `WARNING: expand term "<term>" ... so it was dropped — its group still matches via: <残った語>` | その語のみを落とす。グループは残った語で機能する（短い原語を長い同義語で救済できるのは拡張の副次的な利点であり、死んだクエリと同じ文言で警告すると誤解を招く） |
     | `--expand` グループ全体が 3 文字未満の語のみ | `WARNING: expand group "<a>\|<b>" has no term of at least 3 character(s); ... so this group was dropped and no longer narrows the search` | **グループごと落とす**。グループは AND で連結されるため、何にも一致しないオペランドを残すとクエリ全体が 0 件になる。落とす方が位置引数の挙動（暗黙 AND が短い語の寄与を無視する）と整合する一方、その概念が検索を絞らなくなるため、文言でその旨を明示する |
     | `--expand` 指定はあるが**残ったグループが 1 つもない**（全グループが空・または全語が 3 文字未満） | `WARNING: no usable --expand term remains; the search has no terms at all and cannot match anything (this is not a wiki-coverage result)` | MATCH 式が空フレーズ `""` になり **`hits` は必ず 0** になる。上のグループ単位の警告だけでは「検索が広がった」としか読めず実際と正反対になるため、グループ単位の警告に加えてこの行を出す（`--expand ""` のように 1 行も警告が出ないケースも同時に塞ぐ）。呼び出し側は「Wiki に無い」ではなく「検索が成立していない」と扱う |

     警告はいずれも `hits` の値に関係なく検索実行前に出力し、終了コードにも影響しない
3. `bm25()` に列重みベクトル `(path=0.0, title=10.0, lang=0.0, type=0.0, tags=0.0, review_status=0.0, body=1.0, aliases=10.0)` を渡し、`title` と `aliases`（ページの別名）のヒットを `body` ヒットより優先してランク付けする。`aliases` 列を末尾に置くのは、`snippet()` が列番号 6 で `body` を指しているため
4. `--lang` 指定時はその言語のページのみに絞り込む
5. `--limit`（デフォルト 10）件まで、`path`・`title`・`type`・`lang`・`review_status`・本文スニペット（`snippet()`、trigram トークン換算で前後 32 文字程度）を出力する

### 出力フォーマット（`query`）

```
MATCH: .wikicommit/entity/ja/Person/yamada-taro.md | title=山田太郎 | type=schema:Person | lang=ja | review_status=pending
  ...CompanyA のシニア**エンジニア**。機械学習システムの...
SUMMARY: query="エンジニア", hits=3
```

`SUMMARY:` の `query=` は指定形式で内容が変わる。位置引数では生のクエリをダブルクォートで囲んで出力する。`--expand` では**実際に実行した MATCH 式**をそのまま出力する（引用符を自前で含むため外側のクォートは付けない。落とされた語は式に現れない）:

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

`.wikicommit/entity/**/*.md` を走査し、`type:` フロントマターの値が `.wikicommit/schema/` に専用のスキーマファイルを持たない（`default.md` へのフォールバックのみで表現されている）ページを検出する。`wikicommit-generate` Pass 2 のコンテキスト注入（型文字列の再利用誘導）と、`wikicommit-schema-propose` の検出源の両方から使われる。

### 使用場面

- `wikicommit-generate` Skill：Pass 2 のプロンプトに「未スキーマ化のまま使われている type 文字列一覧」を含めるため
- `wikicommit-schema-propose` Skill：型ファイル追加提案の検出源として
- `wikicommit-status` Skill：Step 6（定期ヘルスチェック）

**`wikicommit-status` から呼ぶ理由**: `default.md` へのフォールバック自体は §5.4 が定める正規の挙動だが、フォールバックするとその型の `granularity`・`properties:` 候補キー・本文テンプレートが丸ごと適用されなくなる。にもかかわらず、生成されたページは一見正常で `validate_frontmatter.py` の必須フィールド検証も通る（`default.md` の required だけが適用されるため）。`validate_frontmatter.py` の WARNING は `wikicommit-merge` が**変更ファイルにのみ**実行するので、**壊れる契機（`.wikicommit/schema/` の編集・移動・削除）と検証の契機（ページの変更）が一致しない**。本スクリプトは全ページを毎回走査するので、「今この瞬間に何ページが影響下にあるか」を直接見せられる。

`validate_frontmatter.py` の当該 WARNING は ERROR に格上げしない。専用ファイルを持たない型は正常系であり、ブロックすると古いページを持つ既存リポジトリが軒並みマージ不能になる。スキーマファイルの移動・削除を git 履歴から追うこともしない — 経路を追う分だけ複雑で、しかも最初からファイルが無いケース（古い版で init したリポジトリ）を拾えない。

### コマンド

```
python .wikicommit/scripts/check_schema_coverage.py
```

引数なし。常に `.wikicommit/entity/` 配下の全 `.md` ファイル（`index.md` と `status: removed` のページを除く）を対象とする。

### 処理フロー

1. 対象ページごとに `type:` フロントマターを読む
2. `schema:` プレフィックスで始まらない値はこのスクリプトの対象外（`validate_frontmatter.py` の関心事）として無視する
3. `schema:` プレフィックスを除いた型名（例: `schema:Person` → `Person`、`schema:custom/Decision` → `custom/Decision`）に対応する `.wikicommit/schema/<型名>.md` が存在するか確認する。`default.md` へのフォールバックが効くかどうかは判定に使わない — `default.md` が存在していても、型固有のファイルがなければ「未カバー」として扱う（これが本スクリプトの検出対象そのものであるため）
4. 型文字列は完全一致でのみ集計する。正規化・fuzzy matching は行わない（決定論的に保つための意図的な単純化。同じ概念が複数の型文字列に分かれたまま残りうるという既知の限界が伴う）

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

Schema.org の公式機械可読語彙ダンプ（`https://schema.org/version/latest/schemaorg-current-https.jsonld`）に対して、型・プロパティが実在するかを検証する。`wikicommit-generate` Pass 2b（その場での型提案・追加）と `wikicommit-schema-propose`（事後検出）が生成する型ファイル提案の、決定論的な裏付けとして使う。検証できるのは「型・プロパティが実在するか」という**存在の正しさ**のみで、「このWikiの内容に意味的にふさわしいか」という**適合性の判断**は LLM と人間レビューに委ねる。

### 使用場面

- `wikicommit-generate` Skill：Pass 2b のプロンプトに Schema.org 型名の一覧をプリロードし（`--list-type-names`）、絞り込んだ候補の説明文だけを引くため（`--describe`）。Pass 2b の型・プロパティ実在検証にも使う（`--type`/`--property`）。Pass 3 が `properties:` の値を WikiLink 化すべきか判断する材料にも使う（`--show-range`）。Pass 2b が新規型の候補プロパティを選ぶ際、型が持ちうるプロパティ一覧を閲覧する材料にも使う（`--list-properties`）
- `wikicommit-schema-propose` Skill：型・プロパティの実在検証（`--type`/`--property`）。Step 4（標準型パス）が候補プロパティを選ぶ際の閲覧にも使う（`--list-properties`）

語彙の読み込み・キャッシュ（`.wikicommit/schemaorg-vocab.json`）・`domainIncludes`/`rangeIncludes`/`rdfs:subClassOf` 継承チェーン判定・DataType 判定のロジックは `.wikicommit/scripts/_schemaorg_vocab.py`（`_frontmatter.py`/`_wikilink.py` と同じ、複数スクリプトが import する共有モジュール）にある。`validate_frontmatter.py` の `properties:` フィールド検証（同スクリプトの節を参照）もこのモジュールを共有し、CLI としての本スクリプトとロジックが乖離しないようにしている。本スクリプト自身は CLI 引数のパース・出力整形のみを担う薄いラッパー。

### コマンド

```
python .wikicommit/scripts/check_schema_org_type.py --type <TypeName> [--property <PropertyName>]... [--show-range]
python .wikicommit/scripts/check_schema_org_type.py --type <TypeName> --list-properties
python .wikicommit/scripts/check_schema_org_type.py --list-type-names
python .wikicommit/scripts/check_schema_org_type.py --describe <TypeName>...
python .wikicommit/scripts/check_schema_org_type.py --list-installed-hierarchy
```

`--type` / `--list-type-names` / `--describe` / `--list-installed-hierarchy` のいずれか 1 つを指定する。すべて省略した場合はエラー（`--list-properties` 単独指定時は「`--list-properties` には `--type` の指定が必要です」という専用のエラーメッセージになる）。優先順位: `--list-type-names` が指定されていれば他の全フラグを無視してこのモード。次に `--describe`、次に `--list-installed-hierarchy` が指定されていれば同様に他の全フラグを無視してこのモード。次に `--type` + `--list-properties` が指定されていればこのモード（`--property`/`--show-range` は無視）。それ以外は `--type`（+ 任意で `--property`/`--show-range`）の既存の検証モード。

### 保存先（Git管理下）

`.wikicommit/schemaorg-vocab.json` に遅延生成する（`search_index.py` が初回クエリ時にインデックスを作るのと同じ形）。取得元 URL は上記の公式配布 URL に固定。TTL・自動更新は設けない — Schema.org 語彙の改訂頻度は低く、古い内容の実害は「新しい型が使えない」程度に留まるため。

`search_index.sqlite3` 等の `.wikicommit/.cache/`（`.gitignore` 除外）配下のファイルとは異なり、本ファイルは `.wikicommit/.cache/` の外（`.wikicommit/schemaorg-vocab.json`）に置き、Git 管理対象とする。理由: `search_index.sqlite3` は作り直せる使い捨てキャッシュ（消しても実害ゼロ）だが、本ファイルはネットワーク取得コストのある準静的な参照データであり、削除すると次回実行時にネットワーク取得が再発生する。`.cache/` という名前が与える「気軽に消してよい」という印象と実際の性質が食い違う。副次的な効果として、クローン直後から使え、複数人・複数マシン間でのネットワーク取得の重複コストも避けられる。

再生成したい場合はユーザーが `.wikicommit/schemaorg-vocab.json` を手動削除して再実行する。Git管理下にあるため、再生成後の差分は他の追跡ファイルと同様に通常のコミット・PRレビューを経て反映される（`wikicommit-merge` が `.wikicommit/schemaorg-vocab.json` の新規作成を検出しコミットに含める。`.claude/skills/wikicommit-merge/SKILL.md` Step 2 参照）。`--type`/`--list-type-names`/`--describe`/`--show-range`/`--list-properties` のどの呼び出しもこの同じファイルを共有する。`rangeIncludes`/`is_datatype`・property の `comment` を含まない旧形式のキャッシュは手動削除不要 ── `_schemaorg_vocab.py` の `load_or_build_index()` が `_is_well_shaped_index()` でこの形状不一致を自動検出し、再取得・再構築する（各 `types` エントリに `is_datatype`、各 `properties` エントリに `range`/`comment` キーが揃っているかまで検証する。外側の `{"types": dict, "properties": dict}` の型だけでは、旧形式のキャッシュを誤って正常として受理してしまい、`--show-range` が黙って何も報告しなくなる、`--list-properties` の説明列が常に空になる、または `is_in_datatype_lineage()` がキー欠落を `is_datatype: false` と誤認して DataType 型をエンティティ型として誤分類する、という複数のサイレント劣化を招くため）。

### 処理フロー（`--type`/`--property`/`--show-range`）

1. キャッシュ（なければ語彙ダンプを取得して構築）から型一覧・プロパティ一覧（`schema:domainIncludes` によるプロパティ→型の対応、`schema:rangeIncludes` によるプロパティ→値の型の対応、`rdfs:subClassOf` による型の祖先チェーン、各型の `is_datatype` フラグ〈`@type` に `schema:DataType` を直接含むか〉）を読み込む
2. `--type` の型が語彙に実在するか確認する
3. `--property` ごとに、そのプロパティが語彙に実在し、かつ `--type`（またはその祖先型のいずれか）の `domainIncludes` に含まれるかを確認する。`--type` 自体が実在しない場合、プロパティの所属判定はできないためその `--property` もすべて ERROR とする
4. `--show-range` が指定されている場合、所属確認に成功した（`OK:` を出力した）`--property` ごとに、`RANGE:` 行を追加出力する。所属確認に失敗した `--property` には出力しない（報告する範囲がないため）。分類は3通り: `rangeIncludes` の候補全てが非 DataType（＝リンク可能なエンティティ型のみ）・候補全てが DataType（`is_datatype` を直接持つか、`rdfs:subClassOf` の祖先チェーンのいずれかが持つ場合。例: `URL` は直接タグを持たないが `subClassOf: Text` 経由で DataType）・両方混在。`rangeIncludes` 自体が宣言されていないプロパティは何も出力しない。この判定はブロッキングではない（`errors`/終了コードに一切影響しない、情報提供のみの行）

### 処理フロー（`--type` + `--list-properties`）

新しい型スキーマファイルを書く際に「この型が Schema.org 上でどんな property を持ちうるか」を一覧するための、オンデマンド表示モード。全型分の全 property 一覧を静的ファイルとして事前生成・保存する方式（`.wikicommit/schema/template/` 等）は採らない — `.wikicommit/schemaorg-vocab.json` という単一の情報源と二重管理になるうえ、全property入りのテンプレートはスキーマ層が本来持つ「絞り込みによる認知負荷低減」という目的と衝突するため。

1. `--type` の型が語彙に実在するか確認する。実在しなければ ERROR を1行出力して終了する（`--property` 検証モードと異なり `checked`/`errors` のカウントは行わない — このモードは検証ではなく一覧表示のため）
2. 実在すれば、語彙全体の property を走査し、その `schema:domainIncludes` が `--type`（またはその祖先型のいずれか。`rdfs:subClassOf` チェーンを `--property` の所属判定と同じロジックで走査）と交差するものを全て集める
3. 集めた property をアルファベット順に並べ、1行ずつ「property名・宣言型（自身か祖先か。`domainIncludes` が実際にどの祖先を指しているか。複数祖先にまたがる場合はカンマ区切りで全て列挙）・`rangeIncludes` のエンティティ型候補（DataType除外後。候補なしは `-`）・一行説明（`rdfs:comment`）」をタブ区切りで出力する

#### 処理フロー（`--list-installed-hierarchy`）

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

### 処理フロー（`--list-type-names` / `--describe`）— 型の想起は 2 段階

キャッシュから型名だけをアルファベット順に出力する（`--list-type-names`。**説明文を付けない**）。続けて、そこから絞り込んだ候補について `--describe <TypeName>...` が型名 + 一行説明（`rdfs:comment`）をタブ区切りで出力する。

**分ける理由は、この一覧が果たしているのが想起であって存在保証ではないため**である。型が実在するかは候補が承認された後の `--type <Type> --property ...` が決定論的に確かめており、一覧の役目は「モデルが思いつかない型を候補に上げさせる」ことに尽きる。想起には、誰も検討していない型の説明文は要らない。全型の名前 + 説明は数万トークンに及ぶのでプリロードせず、名前だけを渡す（利用者向けのコンテキスト量の数字は `README.md` の Requirements → Context window が正本）。全型の説明文を一括で出すモードは持たない — 呼び出し元の無いモードを配らず、プリロードすべきでない高価な経路を仕様に残さないため。同じ需要は `--describe` がオンデマンドで満たす。

**`--describe` は語彙に無い名前を ERROR にする**。黙って落とすと、段階 1 が実在する名前だけを渡している以上「戻ってこなかった名前＝モデルの創作」であることが承認ステップまで伝わらない。1 件でも該当すれば終了コード 1 を返すが、実在した分は通常どおり出力する（呼び出し側が有効な候補だけで進めるため）。

**説明文を落としたことによる型提案の recall への影響は測れない**（eval 基盤が無い）。壊れ方が軽いこと（型提案は元々ゼロ件が通常の結果で、`wikicommit-schema-propose` と `check_schema_coverage.py` が事後の安全網として残る）を根拠にしている。

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

Type ディレクトリの `index.md`（1 行 1 件の `- [[Type/slug]]` 箇条書き）と、view ツリーの言語別 `index.md`（`.wikicommit/view/<lang>/index.md`。1 行 1 件の `- [[View/<slug>]]` 箇条書き）を、ディレクトリを実際にスキャンして決定論的に再構築する。この更新を SKILL.md の「全ソース/ペア処理後に1回だけ」という手順として LLM エージェントの記憶に委ねると、長い多段生成の末尾に置かれた手順はソース件数が多いバッチほど実行し忘れられる。本スクリプトへの委譲により、対象ディレクトリを指定しさえすれば取りこぼしが構造的に起こらない。

### 使用場面

- `wikicommit-generate` Skill：全ソース処理後、`index.md` 更新ステップとして引数なしで呼び出す（ドライバーの `workflow.yaml`。`--regenerate` の `workflow-regenerate.yaml` も同じ — 再生成は `title` を変えうる）
- `wikicommit-translate` Skill：全 `(原文ページ, target言語)` ペア処理後、`index.md` 更新ステップとして引数なしで呼び出す
- `wikicommit-synthesize` Skill：view ページを書き出した直後、view ツリーの言語ディレクトリ `.wikicommit/view/<lang>` 1 件のみを引数に指定して呼び出す。generate・translate が引数なしで全ディレクトリを走査するのは「長いバッチの末尾で対象ディレクトリの追跡を取りこぼさないため」であり、1 ページしか書かず `<lang>` が確定している本 Skill にはその理由が当てはまらない。引数指定にすることで、対話実行される本 Skill の副作用が該当ディレクトリの外へ広がらない
- `wikicommit-organize` Skill：`.wikicommit/groups/<Type>.yml` を書いて `check_groups.py` で検証した後、その型の `.wikicommit/entity/<lang>/<Type>` ディレクトリを実在する言語すべてについて引数に指定して呼び出す（グループの見出しは index にしか現れないため、書き換わるのは各 `index.md` だけである）
- `wikicommit-update` Skill：配布物を同期した後の検証ステップの先頭で引数なしで呼び出す（書式やフロントマターの変更を全 index に一度に反映する）
- `rename_page.py`（`wikicommit-relate` の改名）：スクリプトとしてではなく `rebuild_index()` を import して、改名で動いたページの Type ディレクトリを再構築する

### コマンド

```
python .wikicommit/scripts/rebuild_index.py [<type-dir>...]
```

- 引数なし: `.wikicommit/entity/` 配下で、`.md` ファイルを直接含むディレクトリ（`<lang>/<Type>/` 以深。ネストした custom 型も対象）と、`.wikicommit/view/` 直下の言語ディレクトリ（`<lang>/`）で `.md` ファイルを直接含むものをすべて自動検出して再構築する（entity 側を先に、それぞれパス順）。過去の実行が書いた `index.md` しか残っていないディレクトリも対象に含める — 最後のページが `/wikicommit-remove` で削除された Type ディレクトリはページを1つも持たないため、「ページを持つディレクトリ」だけを検出対象にすると、その `index.md` が二度と再構築されず古い一覧のまま残り続ける（view の言語ディレクトリも同じ）
- 引数あり: 指定したディレクトリのみ再構築する。受け付けるのは Type ディレクトリ（例: `.wikicommit/entity/ja/Person`、ネスト custom 型は `.wikicommit/entity/ja/custom/Decision`）と view ツリーの言語ディレクトリ（例: `.wikicommit/view/ja`）の 2 形。view ツリーは `<lang>/` のちょうど 1 階層だけを受け付け、`.wikicommit/view/` そのものやその下の深いパスは解決できないディレクトリとして WARNING でスキップする

### 処理フロー

1. 対象ディレクトリごとに、まず `.wikicommit/view/<lang>/` として解析し、当たれば下の「view ツリーの言語別 index」の手順で書く。当たらなければ `.wikicommit/entity/<lang>/<Type>/` として解析する（`<Type>` はネスト custom 型の場合 `/` を含みうる）。ディレクトリが存在しない、またはどちらの形としても解決できない場合は WARNING を出して当該ディレクトリをスキップする（他の対象ディレクトリの処理は継続する）
2. ディレクトリ直下の `*.md`（`index.md` を除く）を走査し、各ページの frontmatter を読む。frontmatter のパースに失敗したページ、`title` フィールドがないページは WARNING を出して index.md への掲載から除外する。`status: removed` のページも除外する（サイレント。孤立検出等と同じ既存の除外方針）
3. 残ったページをファイル名（slug）の昇順でソートする
4. `index.md` を書き出す:
   - frontmatter: `title`（そのディレクトリの `<Type>` の末尾セグメントのみ。例: `custom/Decision` → `"Decision"`。`"<Type> Index"` ではなく bare Type name を使う）・`lang`・`type`（`schema:<Type>` の完全形）・`review_status: reviewed`・`comments: false`

     `review_status: reviewed` は `convert_wikilinks.py` の `generate_root_index()`・`_write_source_page()`・`_write_sources_index()`・`_write_source_dir_index()` が同じ理由で行っているスタンプと同じもの: `index.md` はビルド生成のナビゲーションページであって LLM が書いた Wiki コンテンツではないため、`WikiCommitBanner` の未レビュー警告を表示すべきでない（同コンポーネントはフィールドが無い場合 `pending` にフォールバックする — LLM 生成ページで書き漏れた場合に安全側へ倒すための意図的な設計であり、これ自体は変えない）。`index.md` は `wikicommit-merge` のレビュー追跡 Issue の対象外でもあるので、バナーを出すと読者が対応する Issue を探しても存在しない。

     除外の判定を `WikiCommitBanner` 側（`fileData.slug === "index"` 等）に置かない。同コンポーネントは Quartz のスラッグ命名規約に依存しない方針を明示している（`docs/DesignDoc-publish.md` §8）ため、書き出す側でフィールドを持たせる。

     `comments: false` も同じ理由で書き出す側が持つ。giscus のコメント欄は全ページの `afterBody` に描画されるが、index には読者が応答する内容が無く、プラグインはこのキーを持つページを飛ばす。
   - body: 各ページ1行、`- [[<Type>/<slug>]]` の箇条書き（slug 昇順）。**タイトルを接尾辞として付けない**（下記「行にタイトルを付けない理由」）
   - 既存の `index.md` があれば全体を上書きする（差分マージではなく毎回フルスキャンからの再構築。手書きの前文等があっても保持しない）。したがって書式やフロントマターの変更は、次に `/wikicommit-generate`・`/wikicommit-translate`・`/wikicommit-synthesize` が走った Type ディレクトリから順に反映され、一括移行の仕組みは要らない（全型を即座に揃えたい場合は引数なしで 1 回実行すれば足りる）
5. 対象ディレクトリすべての処理後、`SUMMARY:` 行を1行出力する

**行にタイトルを付けない理由**: `convert_wikilinks.py` の `convert_file()` は WikiLink を**参照先ページの `title`** で描画するため、`[[Type/slug]] — {title}` という行は公開サイト上でタイトルの重複になる。同じファイルが 2 つの文脈で読まれ、片方でだけ重複する:

| 読み手 | `[[Person/yamada-taro]] — 山田太郎` の見え方 |
|---|---|
| リポジトリ上（GitHub・エディタ） | GitHub は `[[...]]` を描画しないため、接尾辞がタイトルを伝える唯一の要素になる |
| 公開サイト（Quartz） | WikiLink が参照先の `title` に置き換わるため `山田太郎 — 山田太郎` になる |

**生表示でタイトルが読めなくなることは受け入れる** — slug は言語中立の英語識別子であり非英語 Wiki では可読性が落ちるが、(a) その情報は同じディレクトリのファイル名そのものが持ち、(b) この読み手は運用者であって読者ではなく、(c) 代償として読者向けの主要な回遊面すべてに重複が出続けることの方が大きい。`convert_wikilinks.py` が書き出す他の一覧（`_write_sources_index()` / `_write_source_dir_index()` / `generate_overview_page()`）はいずれも素の Markdown リンク `[{title}]({link})` を書いており、この問題を持たない。

**行は箇条書き（先頭の `-` + 空白）にする**。インデックスの各行は空行を挟まない連続行であり、CommonMark はこれを 1 つの段落に畳む — 配布する `quartz.config.yaml` は `hard-line-breaks` プラグインを `enabled: false` で出荷しているため、ソフト改行は `<br>` にならない。マーカーが無いと、リンクの文字列同士が空白 1 個で隣接した 1 本の長い行になる。

**publish 時に `convert_file()` 側で接尾辞を strip する形は採らない**。インデックス本文の書式を書く側と publish 側が「行のどこからどこまでがタイトルか」まで知る状態を作り、`rebuild_index.py` が書式を変えた瞬間に strip が黙って効かなくなる（drift）。

**インデックス本文の書式を読み取るコードは 1 箇所ある**: `wikicommit-remove` の `remove_page.py` の `remove_index_entry()` は、`index.md` を全面再構築するのではなく該当行だけを行頭アンカーの正規表現で落とす（`main()` から呼ばれる）。同関数は先頭のリストマーカーを任意扱いにしてあり、`- [[Type/slug]]`（現行）・`[[Type/slug]]`・`[[Type/slug]] — Title`（いずれも旧書式。既存リポジトリには残りうる）の 3 形式すべてに一致する。参照するのは行頭の WikiLink までであり、行の残りには依存しない（`.*` で捨てる）ので、上の drift の形には当たらない。**行の書式を変える際はここも併せて見ること** — 一致しなくなっても例外にはならず、`status: removed` のページを指す行が残り、次の `/wikicommit-merge` が `check_wikilinks.py` の「`status: removed` のページへのリンクです」ERROR でブロックされる形でしか現れない。同関数は行を落とした後、下に空行しか残らない `##` 見出し（次の `##` 見出しかファイル末尾まで）も併せて落とす — グループファイルを持つ型の index は `## <表示名>` で区切られ、`rebuild_index.py` はページの無い節（グループ・未分類とも）を出さないため、最後の 1 ページを消した節の見出しだけが次の再構築まで公開されるのを防ぐ。`index.md` を `rebuild_index.py` で再構築することはしない — 旧書式の行やフロントマターまで書き直す差分が削除 PR に混ざり、Skill 側のスクリプトから利用者リポジトリの `.wikicommit/scripts/` への依存も増えるため、触れるのは消した行と空になった見出しに限る。

**他のチェックには影響しない**: `check_orphans.py` は `index.md` をリンク元として明示的にスキップするため孤立判定は変わらず、`search_index.py` の `build` は `index.md` を索引対象から除外するため検索結果も変わらない。`check_wikilinks.py` は引数なしモードでインデックスの WikiLink も検証するが、リンクは実在ページのディレクトリ走査から生成されるため構成上必ず解決する（`WIKILINK_RE` は行内の部分一致であり、リストマーカーの有無に左右されない）。

### グループファイルを持つ型

`.wikicommit/groups/<Type>.yml`（`docs/DesignDoc-data.md` §4.5.3）がある型では、本文を `## <表示名>` の見出しで分ける。グループはファイルの順、各グループ内は slug 順、ページが 1 件も無いグループは見出しごと省き、どのグループにも無いページは最後の未分類の見出し（ja「未分類」・en「Unclassified」、ファイルの `unclassified_label` が優先）の下に置く。表示名は index の `lang` で選ぶ。ファイルが無い型は見出しの無い 1 列である。ファイルが不正なときは `WARNING:` を出して見出し無しで書く（ビルドを止めない。詳細は `check_groups.py`）。書き換えるのは `index.md` だけで、ページには触れない。

### view ツリーの言語別 index

view ページは Type を持たず `.wikicommit/view/<lang>/` の直下に並ぶ（`docs/DesignDoc-data.md` §4.5.1）ので、view ツリーの index は Type ごとではなく言語ごとに 1 枚であり、`.wikicommit/view/<lang>/index.md` に書く。走査・除外・並び順・全上書き・冪等性は Type の index と同じで（処理フローの 2・3 と 4 の最後の項目）、違うのは書き出す内容だけである:

| 項目 | Type の index | view の言語別 index |
|---|---|---|
| frontmatter の `title` | `<Type>` の末尾セグメント | `"View"`（予約 Type セグメントの名前。言語によらず同じ） |
| frontmatter の `type` | `schema:<Type>` | **書かない** — view ツリーのページは `type:` を持たず、`validate_frontmatter.py` は持つページを ERROR にする |
| frontmatter のその他 | `lang`・`review_status: reviewed`・`comments: false` | 同じ |
| 本文の行 | `- [[<Type>/<slug>]]` | `- [[View/<slug>]]`（公開時に `content/<lang>/View/<slug>.md` を指す） |
| 見出しによる区切り | グループファイルがあれば `## <表示名>` | **無い**。常に slug 順の 1 列で、`.wikicommit/groups/` も読まない |

書き出す例（ja に view ページが 2 件）:

```markdown
---
title: "View"
lang: ja
review_status: reviewed
comments: false
---

- [[View/agent-loops]]
- [[View/context-compaction]]
```

**`kind` で見出しを分けない**。`kind` は任意フィールドなので、分けるなら `kind` を持たないページの受け皿の見出しが要り、多くの場合小さい view ツリーに見出しを足す利得より読む順序を乱す損の方が大きい。index の形に依存する箇所は無いので、後から足しても契約は変わらない。

ページが 1 件も無い（すべて `status: removed` か `title` 無しになった）言語ディレクトリでも、frontmatter だけの `index.md` を書く。

### 出力フォーマット

```
OK: .wikicommit/entity/ja/Person/index.md rebuilt (3 pages)
OK: .wikicommit/view/ja/index.md rebuilt (2 pages)
WARNING: .wikicommit/entity/ja/Place: directory not found, skipped
SUMMARY: rebuilt=2
```

### 終了コード

- 常に `0`（`wikicommit-merge` の品質ゲートではなくワークフロー手順の一部のため、個別ディレクトリの解決失敗はブロッキングにしない）

---

## reconcile_ingest_status.py

### 目的

`status: pending` のまま放置されている ソース管理ファイルのうち、実はその `source.hash` が既に公開ページの `sources[]` に使われているもの（＝内容は既に取り込まれているのに、そのソース自身の管理ファイルへの書き戻しだけが行われなかったもの）を検出し、`status: generated`・`generated_pages`・`last_generated_at` を書き戻す。複数の関連ソースが同一エンティティのページを共同更新すると、そのうち一部の管理ファイルが `status: pending`・`generated_pages: []` のまま取り残されうる。

この照合・書き戻しを SKILL.md の instruction（散文指示 + grep）にしない。対象は `status: pending` のみとし、**`outdated` は明示的に対象外**とする — `check_ingest_freshness.py` は `outdated` のファイルの `source.hash` を書き換えずに残す（前回生成時点の参照点として機能させるため）ので、同じ hash 一致判定を適用すると「ソースが変更され再処理が必要」という正しいシグナルを「既に反映済み」と誤認して握りつぶす。一致した場合は常に `status: generated` のみを設定する（`partial`/`excluded`/`failed` への遡及推定は行わない — それらは Pass 2/4 のエンティティ単位の結果が必要で、その場限りの情報のため後から再構築できない）。

**意図して requeue された `pending` を黙って取り消さない**。ポリシー・型テンプレート・生成ルールの変更を既存ページへ届ける経路は、そのソースを `status: pending` に戻して次の `/wikicommit-generate` に Pass 2c をもう一度通させることであり（`--regenerate` は Pass 2c を実行しない）、`/wikicommit-reconcile` がそれを行う。`add_source.py` が `outdated` なファイルのハッシュ一致を見て `pending` へ戻す経路も同じ形をしている。requeue されたファイルは、ページを作ったソースなら hash が定義上そのページの `sources[]` に現れるので、ハッシュ一致だけで判定すると generate が実行の最後に本スクリプトを呼んだ時点で `generated` へ書き戻される（しかも出力は成功系の `RECONCILED:`）。5 件ガードと組み合わさると、処理されなかった残りが二度と拾われなくなる。**3 つの requeue 起点を守るのはそれぞれ別の条件であり、1 つのコードから他の 2 つは見えない**:

| requeue の起点 | 何が守るか |
|---|---|
| `generated` / `partial`（ページが作られていた） | **`generated_pages` が非空ならスキップ**。ページを作った以上 hash は必ず引用されているので、ハッシュ一致条件では落ちない |
| `excluded`（ページを 1 枚も作っていない） | **ハッシュ一致条件**。1 枚も作っていない以上その hash はどのページの `sources[]` にも現れない |
| `excluded`（以前のゆるいポリシーではページを作っていた） | **`last_generated_at` を持てばスキップ**。Pass 4 の `excluded` 分岐は `generated_pages` を書かない一方、以前の実行が作ったページはディスクに残る（生成経路にページを消す手段は無い）ので、上の 2 つを**両方すり抜ける**。ポリシーを厳しくして requeue → 全件除外 → 緩めて再び requeue、という往復で普通に到達する |

**`last_generated_at` の条件が問うのは「一度でも実行を完走したか」である**。`add_source.py` は管理ファイルの新規作成時に `last_generated_at:` を**空の値で**書き、これを埋めるのは完走した実行だけなので、日付が入っていることは「この `pending` はその完走より後に、意図して書かれた」ことを意味する。本スクリプトが救う形（別の管理ファイルの実行がページを書き、こちらは一度も書き戻されていない）は構造上ここが空である（`tests/test_reconcile_ingest_status.py` がこの両立を固定する）。

**新しい `status` 値（`requeued` 等）は足さない** — `status` を読む全消費者（Pass 1 の収集条件・`add_source.py` の分岐・`check_ingest_freshness.py` の `CHECKABLE_STATUSES`・`wikicommit-status` の集計）に分岐が増える。**generate が本スクリプトを呼ぶのをやめることもしない**（取り残された `pending` が残る）。

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
3. 対象ファイルの `generated_pages` が非空の場合はスキップする（上記「目的」の表）
4. 対象ファイルが `last_generated_at` を持つ場合はスキップする（同上）
5. 対象ファイルの `source.hash` が空文字列・未設定の場合はスキップする（`type: url` ソースが Pass 1 でまだフェッチされていない場合に発生しうる。空文字列を許すと事実上すべてのページに一致してしまうため）
6. 1で構築したマップにこのhashが存在すれば、一致したページパスを重複排除・昇順ソートした上で、`status: generated`・`generated_pages`（一致したページパスのYAML flow-styleリスト）・`last_generated_at`（実行日）を書き戻す。`## Failure Reason` セクションが存在すれば削除する（Pass 4 手順7の `generated` 分岐と同じ扱い）
7. 全管理ファイル処理後、`SUMMARY:` 行を1行出力する

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

信頼ラダーの上段（`review_status: reviewed` と、そこに添えられる `reviewed_by` の実名）は「この文章を人間が読んだ」という主張である。ページの文章を書き換える経路は、その主張も動かさなければならない。

| 経路 | `review_status` |
|---|---|
| `action: create` | `pending` |
| `--regenerate` | `pending`（理由を明記して `action: update` の規則を上書き） |
| `wikicommit-translate` | `pending`（無条件） |
| `wikicommit-synthesize` | `pending`（無条件） |
| **`wikicommit-generate` Pass 3 の `action: update`** | **本スクリプトが決める**（内容が変わったときだけ `pending`） |
| **`wikicommit-fix`** | **本スクリプトが決める**（定義上内容が変わるので常に `pending`） |

`wikicommit-fix` は特に重要である — `/wikicommit-fix` は「レビュー済みの内容が誤っていた」から起動されるものであり、しかも公開ページの報告リンクは `review_status` に関わらず常時表示されるため、`reviewed` なページの誤りを読者が報告するのは**設計上の主経路**である。戻さなければ、そのレビューが見落としたからこそ書き直された文章にレビュアーの実名が付き続ける。加えて `wikicommit-merge` Step 8 は `pending` のページにしか追跡 Issue を作らないため、`reviewed` のまま更新されたページは**恒久的に再レビューされない終端状態**になる。

### 「常に戻す」を採らない理由

無条件に戻すと、取り込みを続ける Wiki ではページが `reviewed` と `pending` を往復し、そのたびに追跡 Issue が立つ。レビュー負荷が青天井になり `reviewed` が到達不能になる — 信頼ラダーの価値は上段に**届くこと**にも依存している。代わりに、再生成モードの unchanged-output valve（`docs/DesignDoc-pipeline.md` §6.1）と同じ形を採り、**内容が変わったかどうか**で判定する。規則は 1 つで足りる: `action: update` では bookkeeping だけの更新が普通にあるため条件付きになり、`wikicommit-fix` では定義上必ず内容が変わるため常に発火する — 同じ規則が入力の違いで別々に振る舞うだけであり、経路ごとに別の規則を書かない。

### 使用場面

- `wikicommit-generate` Skill：Pass 4 step 6（ページ書き出しの直後、書き出した全ページを 1 回の呼び出しで渡す）
- `wikicommit-fix` Skill：Step 5 item 4（Edit 実行の直後、書き込んだページごとに 1 回）

### コマンド

```
python .wikicommit/scripts/reset_review_on_content_change.py <page>...
```

`<page>` は `.wikicommit/entity/` または `.wikicommit/view/` 配下のページ（旧 `.wikicommit/wiki/` 接頭辞も受け付ける。`index.md` は下記の処理フロー 2 のとおり除外する）。**両ツリーを受け付けることが要件である** — `wikicommit-fix` はどちらの接頭辞も対象に取り、view ページも `review_status` と追跡 Issue を持つため、entity ツリーだけを見るとその半分が黙って素通りする。

### 内容フィールドと bookkeeping フィールドの線引き

無視するのは以下の 6 つだけで、**それ以外の frontmatter フィールドと本文はすべて内容として扱う**（再生成モードの valve が 5 フィールドだけを無視するのと同じ ignore リスト方式を広げたもの）。判定は「人間のレビューが要るか否か」を左右するため、知らないフィールドは安全側＝内容として数える。

| 扱い | フィールド |
|---|---|
| **内容**（変われば `pending` に戻す） | 本文、`title`、`tags`、`properties.*`、`expires_at`、および上記以外の全フィールド |
| **bookkeeping**（無視する） | `generated_at` / `generated_by` / `generated_with`、`review_status`、`reviewed_by`、**`sources[]`（追加・`hash` 更新・`license` 補完を含む）** |

**`sources[]` を bookkeeping 側に置くことがこの方針の要である。** `action: update` はほぼ必ずソースを追記する（それがこの分岐の目的である）ため、`sources` の変化を内容とみなすと本スクリプトは「常に戻す」に潰れ、上で退けたはずの負荷の懸念がそのまま現実化する。人間がレビューしたのは記述であり、同じ記述に裏づけが 1 件増えることはその判断を無効にしない。

`expires_at` は内容側に残す — Pass 4 がこれを他の主張と同様にソースとの照合対象にしている以上、検証対象の主張である。`translator_notes`（`wikicommit-fix` Step 5 が追記する翻訳固有の申し送り）は性質上 bookkeeping 寄りに見えるが、同じ Edit で本文も変わっているのが通常なので実質的な差が出ず、ignore リストを増やさない側に倒してある。

### 処理フロー

1. 引数が `.wikicommit/entity/` / `.wikicommit/view/` / 旧 `.wikicommit/wiki/` のいずれの配下でもなければ ERROR（誤ったパスが黙って no-op になるのを防ぐ）
2. `index.md` は `SKIP:`。`rebuild_index.py` がビルド生成のナビゲーションページとして書き出し、まさにその理由で `review_status: reviewed` を刻む唯一のページである — 人間のレビューを経ていない `reviewed` がここだけは正当であり、降格させると `wikicommit-merge` Step 8 が index を追跡 Issue の対象外にしている以上**戻す経路が無いまま公開サイトに未レビューバナーが出続ける**。他の全走査スクリプトと同じ除外である（`wikicommit-fix` の公開 URL 逆引きは `**/*.md` を glob するため index も候補に入りうる）
3. 作業ツリー側のページを読み frontmatter と本文に分ける。パースできなければ ERROR
4. `review_status` が `reviewed` でなければ `SKIP:`（降格すべき主張が無い）
5. `git show HEAD:<path>` で前版を取得する。**比較先を HEAD にする**ことで、同一バッチ内で未コミットのまま 2 回更新された場合も正しく振る舞う（HEAD は依然として人間がレビューしえた最後の版である）。追跡されていなければ `SKIP:` — 新規作成は元から `pending` であり、比較すべき前版が存在しない。取得結果は**バイト列で受け取り、作業ツリー側の読み込みと同じ規則で自前でデコードする**（`utf-8-sig` ＋ 改行コードの正規化）— `subprocess` の `text=True` に任せるとロケール依存のコーデックになり、非 UTF-8 ロケール（Windows ネイティブ Python の cp932 / cp1252 等）では非 ASCII ページで `UnicodeDecodeError` が実行全体を途中で落とし、latin-1 系ロケールでは例外にすらならず文字化けした HEAD 版と突き合わせて全ページが無条件に降格する。BOM を落とすのも同じ対称性のためで、落とさないと HEAD 側だけ `---` 始まりと認識されず「frontmatter 無し・本文＝ファイル全体」に見えるため、1 文字も変えていないページが「内容が変わった」と判定される（`_frontmatter.py` がスクリプト間の BOM 扱いの食い違いを実バグとして名指ししているのと同じ種類の非対称である）
6. bookkeeping を除いた frontmatter フィールドを突き合わせ、本文は改行コードと前後の空行のみ正規化して比較する（内容の差は吸収しない）。HEAD 側の frontmatter が読めない場合は stderr に `WARNING:` を出したうえで**内容が変わったものとして扱う** — 誤って戻す代償は追跡 Issue が 1 件増えることだが、誤って維持する代償は人間が読んでいない文章に署名が残ることである
7. 一致すれば `UNCHANGED:`（何も書き換えない）。異なれば `set_frontmatter_field.py` の `apply_frontmatter_fields()` を in-process で呼び、`review_status: pending` を設定して `reviewed_by` を落とし `RESET:` を出す（「`reviewed_by` は常に `review_status` に従わせる」という規範。1 回の呼び出しで両方を行う）

### プローズの手順にしない理由

完全に決定論的に判定できる操作を SKILL.md の instruction として書くと、非決定論的な失敗モードを持ち込む。しかも本件は「人間のレビューが要るか否か」を左右する判定であり、再生成モードの valve が同じ理由で比較を意味的同一性ではなくテキスト一致にしているのと同じ配慮が要る。

### 既知の限界

`properties.description` が 1 文変わった場合と句読点だけが変わった場合を区別しない。テキスト一致で判定する以上これは避けられず、再生成モードの valve も同じ割り切りをしている。**既に陳腐化した `reviewed` を抱えたページを遡って探すことはしない** — 次にそのページが更新されるか人間が直すまで残る。

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

`wikicommit-generate` Pass 4 が生成した全ページに掛ける検査の判定を、ページ単位のディレクトリに**レビュー単位の不変ファイル**として書き出す（設計判断は `docs/DesignDoc-data.md` §4.8）。

**判定は LLM が下し、ファイル手術はスクリプトが行う**。`set_frontmatter_field.py` / `reset_review_on_content_change.py` と同じ形だが、こちらは**既存ファイルを一切読まず・書き換えず、新規作成のみ**を行う。

### 使用場面

- `wikicommit-generate` Pass 4：書き出したページと、`failed_pages` に落ちたページの両方
- `wikicommit-review` Step 5：追跡 Issue を Close した経路・ローカルに書いた経路の両方
- `wikicommit-synthesize` Step 5.5：PASS・retry 上限超過の両方
- `wikicommit-translate` Step 4 item 5：PASS・retry 上限超過の両方（`stage: translate-check`）
- `.github/workflows/review-issue-close-sync.yml`：`review_status` を書き換えるのと同じコミットで。Close した本人の最新コメントを `--note-file` で渡し、記録の散文本文にする（選別と injection 上の扱いは `docs/DesignDoc-data.md` §4.8 参照）

### コマンド

```
python .wikicommit/scripts/record_review.py <page> \
    --kind ai|human --stage generate-pass4|review-skill|synthesize-step5.5|translate-check|issue-close \
    --result pass|fail|discarded [--attempts N] \
    [--model "<model ID>"] [--reviewer "<GitHub login>"] \
    [--skill-blob <hash>] [--json <path>|-] \
    [--note <text>] [--note-file <path>] [--sources-from <mgmt file>]... \
    [--reviewed-at YYYY-MM-DD]
```

`--skill-blob` に渡すのは `.wikicommit/review-rules.md`（レビュー規律の正本）の blob hash である（`rules_version` との役割の違いは `docs/DesignDoc-data.md` §4.8 参照）。

`<page>` は `.wikicommit/entity/` または `.wikicommit/view/` 配下のページ（旧 `.wikicommit/wiki/` 接頭辞も受け付け、記録は `entity/` 配下に寄せる — 記録はページについてのものであり、後から `git mv` したリポジトリの履歴が 2 つに割れないようにするため）。**ディスク上に存在しなくてよい** — `result: discarded` がまさにその場合である。

### 処理フロー

1. 引数が上記 2 ツリーの外を指していれば ERROR（誤ったパスが黙って no-op になるのを防ぐ）。`--kind ai` に `--model` が無い場合も ERROR — モデルに帰属できない判定は、この記録ツリーが可能にしようとしている偏りの測定に使えない
2. `--json` から §4.6 の JSON を読む（`-` で標準入力、省略で findings なし）
3. `issues[]` を `FINDING_FIELDS`（`round` / `type` / `claim` / `source_file` / `source_lines` / `instruction` / `page_at_fault`）に射影する。**`source_quote` は呼び出し側が渡してきても落ちる**。`round` が無い場合は 1 を補う。`source_file` の**空文字列は残す** — `wikicommit-synthesize` の `MISSING_SOURCE` は定義上どの grounding ページも当てはまらないため意図的に空にするので、キーごと落とすと「呼び出し側が入れ忘れた」と区別できなくなる
4. `page_content_hash` を計算する。無視リストは `reset_review_on_content_change.py` の `BOOKKEEPING_FIELDS` を **import** する（複製しない）。正規化は「内容フィールドを `yaml.safe_dump(sort_keys=True)` したもの + 本文を同スクリプトと同じ規則で正規化したもの」の SHA-256。`--result discarded` では空文字列
5. `reviewed_sources` を、ページの `sources[]`（view ページは `derived_from`）から取る。`--sources-from` が指定されていればそちらを優先する（ページが存在しない `discarded` 用）。翻訳ページは `sources` を持たないので `{path: translated_from, source_commit}` の 1 要素を組み立てる（`page_evidence_entries()`。`check_review_coverage.py` の失効判定も同じ関数を import して使い、記録側と読み取り側で「このページの証拠」の定義が割れないようにしている）。`--stage translate-check --result discarded` のときは読まず空にする — ディスクにあるのは古い翻訳であり、その `source_commit` は今回照合した原文の版ではない
6. `.wikicommit/review/<ページパスから .wikicommit/ と .md を落としたもの>/<YYYYMMDD>-<HHMMSS>-<kind>.md` に新規作成する。同名が存在すれば `-2`、`-3`… を付す（**上書きは契約上あり得ない**）

### 出力フォーマット

```
RECORDED: .wikicommit/review/entity/ja/Person/yamada-taro/20260905-142233-ai.md (page=.wikicommit/entity/ja/Person/yamada-taro.md, result=pass, attempts=2, findings=1)
```

### 終了コード

- `0`: 記録を 1 件書いた
- `1`: 引数不正、entity/view ツリーの外、ページが存在しない（`discarded` 以外）、JSON が読めない／壊れている、書き込み失敗

### `page_at_fault` は検証も消費もされていない

`page_at_fault` は `FINDING_FIELDS` の射影に乗って記録されるが、**値を検証する箇所も読む主体も無い**。仕様の値は `under-review` / `other` の 2 値で、`review-rules.md` の返却形式の節（Part 1 rule 4）が `type` と同じ形でこれを列挙している — 値を書くモデルが従うのは返却形式の節に列挙された値であり、そこに無い値の仕様は守られにくい。

**本スクリプトに検証は足さない**。値を書くのはレビューサブエージェントで、警告が出る先は `record_review.py` を実行する orchestrator であり、両者は別のコンテキストにいるので警告は誰の行動も変えない。argparse の `choices` による強制も使えない（値は `--json` の中にあり、強制は「記録を書かない」か「フィールドを落とす」のどちらかで、いずれも仕様外の値より悪い）。記録は受け取った値をそのまま持つので、drift が残っているかは記録を数えれば分かる。

**`this` / `self` 等の仕様外の値を `under-review` へ正規化もしない**。仕様が静かに 4 値になる。**既存の記録は書き換えない**（記録は不変）。`RISKY:` は findings を `page_at_fault` を見ずに数える（告発した側が載り、告発された側は載らない）が、告発先を引くには `page_at_fault` と `source_file` が信頼できる必要があるので、いまは使わない。

---

## check_review_coverage.py

### 目的

`record_review.py` が書いた記録を読み戻す。**消費者が同時に存在すること**が要件である — 読む主体が無ければ、記録ツリーは常に空のまま残る受け皿になる。

4 つの問いに答える: どれだけレビューされたか（`SUMMARY:` / `COVERAGE:`）、**今の本文を判定した記録が何も無いのはどれか**（`UNREVIEWED:`）、**人が読むならどれか**（`RISKY:`）、**どの判定がもう当てはまらないか**（`STALE_REVIEW:`）。

1 つ目には `human_notes` が含まれる — standing な human 記録のうち、**散文本文を持つ件数**である。数えるのは**有無であって中身ではない**（一語のコメントも長文も 1 件）。

**すべての行が「standing な記録」1 件を読む** — そのページを**今の姿のまま判定した最新の記録**である（`page_content_hash` が非空のもの。`result: discarded` の記録は空ハッシュを持ち、ディスク上の本文について何も述べていないので standing にならない）。「このページの記録」の定義を行ごとに変えない。kind の別だけが行ごとに違う（`ai_reviewed` / `COVERAGE:` は AI、`human_reviewed` は human、`RISKY:` は kind を問わず、`STALE_REVIEW:` / `RETRACTED_EVIDENCE:` は AI）。唯一の例外は `SUMMARY: findings=` で、こちらは「この Wiki の一生でレビューが何件捕まえたか」という歴史的な量として全記録を合算する（破棄された判定の findings も数える）。

### 使用場面

- `wikicommit-status` Skill：Step 13
- `wikicommit-merge` Skill：Step 9（`--discarded-reason`。生成失敗トラッキング Issue の理由欄）

### コマンド

```
python .wikicommit/scripts/check_review_coverage.py
python .wikicommit/scripts/check_review_coverage.py --discarded-reason <page>...
```

引数なしの既定モードは `.wikicommit/entity/` + `.wikicommit/view/` の全ページと `.wikicommit/review/` を対象とする。

### `--discarded-reason` — 破棄されたページの理由を引く

`wikicommit-merge` Step 9 の生成失敗トラッキング Issue は、理由をソース管理ファイルの `## Failure Reason` から取るが、Pass 4 step 7 は**その節を `partial` 分岐で削除する**（`failed` ではないため）。そして `partial` こそが**普通の失敗の形**である — 1 ソースから複数エンティティを切り出す設計上、全件失敗は例外的である。理由は同じ実行が `.wikicommit/review/` に書いた `result: discarded` の記録に完全な形で残っているので、Step 9 はそれを本モードで引く。

本モードは指定された各ページについて、**`result: discarded` の最新 1 件**を探して findings を印字する。`standing_review()` が `discarded` を意図的に飛ばすのとちょうど逆で、それがここで欲しいものである — `failed_pages` に載るページは書き出されていないので、破棄された記録だけが理由を語る。

**Step 9 のインライン Python に走査を書かない。** 最新の判定は `record_sort_key()` が正であり（**素のファイル名の辞書順ではない** — 同一秒の衝突サフィックス `-2` が `-` < `.` のため未サフィックスより前に来る）、そのキーを共有しない実装は誤った「最新」を拾う。既存スクリプトに照会モードを足す形は `check_retracted_sources.py --list` と同型である。

**印字するのは `type` / `source_lines` / `instruction` の 3 つに限る。**

| フィールド | 扱い | 理由 |
|---|---|---|
| `round` | **記録が 2 ラウンド以上を持つときだけ印字する** | 破棄された記録は全ラウンドをフラットに持ち（`docs/DesignDoc-data.md` §4.8）、ラウンドごとに別の欠陥であることが普通なので、番号が無いと複数回の試行が同時並行の問題に読める。1 ラウンドしか無い通常の記録では出さない |
| `type` | 印字する | 所見の種類 |
| `source_lines` | 印字する（**何に対する行番号かを添える**） | 単独では読めない |
| `instruction` | **verbatim で印字する** | 下記 |
| `source_file` | **印字しない** | 下記 |
| `claim` | 印字しない | 長く、`instruction` と内容が重なる |
| `page_at_fault` | 印字しない | `discarded` に至る所見には現れない（`other` は FAIL しない） |

**`source_file` を印字しない理由**: 多くは `.wikicommit/.cache/ingest-fetch/…` という **gitignored なマシンローカルのキャッシュ**を指しており、別の clone・別のマシン・キャッシュ削除後には存在しない。ただし**どの種類のファイルか**は言う価値があるので、Pass 4 の check 8 と同じ判別子（`.wikicommit/entity/` ないし `.wikicommit/view/` 配下なら別のページ、それ以外ならソースの抽出テキスト）で `at lines <N-M> of the extracted source text` / `... of another page` と添える。

**`instruction` を verbatim にする理由**: この文は再生成プロンプトに渡すために書かれたものであって読者向けではなく、命令形で書かれている（`docs/DesignDoc-skills.md` §11.8 の「読み手が誰か」で判定する軸に当たる）。それでも要約しないのは、要約とは**この step が下していない判断を書き直すこと**であり、しかもこの記録の価値はその具体性そのものだからである。記録ツリーは人が読める形で設計されており、この文はページが存在しない理由について現存する最も具体的な記述である。

**記録が無い場合は `unknown` と書かない。** `NO_RECORD:` を返し、Step 9 は「理由は記録されていない」と書く。記録ツリーを持つ前の失敗と、`.wikicommit/review/` を持たない古いリポジトリがこれに当たる — **「理由が分からない」と「理由が記録されていない」は別のことであり**、後者は読み手に探しに行かなくてよいと伝える。

**`partial` 分岐が `## Failure Reason` を削除する設計は変えない**。変えれば Step 9 は記録を引かずに済むが、「`partial` は `failed` ではないので失敗理由を残さない」という Pass 4 の整理を崩し、**同じ情報を 2 箇所に持つ**ことになる。

出力:

```
REASON: .wikicommit/entity/en/ScholarlyArticle/x.md (recorded 2026-09-18, attempts=1)
  MISSING_SOURCE at lines 160-166 of the extracted source text: The source only characterises ...
NO_RECORD: .wikicommit/entity/en/Person/y.md
ERROR: .wikicommit/source/url/example.com/a.md: expected a page under .wikicommit/entity/ or .wikicommit/view/
SUMMARY: pages=3, with_reason=1
```

**引数は `.wikicommit/entity/` / `.wikicommit/view/`（および旧 `.wikicommit/wiki/`）配下でなければ `ERROR:` を出して次へ進む。** `record_review.py` / `reset_review_on_content_change.py` と同じ契約であり、理由も同じ — 誤ったパスを `NO_RECORD:` として返すと、Step 9 がそれを「理由は記録されていない」という**答え**として Issue に書く。素通しもできない: `record_dir_for()` は `.wikicommit/` を**長さで**削ぐため、その接頭辞を持たないパスは黙って別のディレクトリに解決し、接頭辞より短いパスは `ValueError` を投げる。

**ページを 1 件も渡さない呼び出しは正常であり、`pages=0` と答える。** Step 9 の 2 つ目の対象（Pass 1 で失敗した `status: failed` のソース）は `failed_pages` が空なので、呼び出し側の展開はフラグだけを残す — そこで argparse の usage エラー（exit 2）を返すと、常に 0 という契約が破れるうえ、呼び出し側からは「この版にこのモードが無い」と区別が付かない。

終了コードは既定モードと同じく常に `0`。記録が 1 件も無いことは失敗ではなく、`failed_pages` の 1 エントリが壊れていることも残りのページの理由を巻き添えにしない。

### 処理フロー

1. `.wikicommit/review/` が無ければ全 0 と `NOTE:` を出して終了する — 「まだ一度もレビューを記録していない」と「全部 0 だった」は別の状態であり、区別せずに 0 だけを出すと後者に見える
2. 各ページの記録ファイルを `record_review.py` の `record_sort_key()` 順（＝時刻順）に読む。**素のファイル名の辞書順ではない** — 同一秒の衝突サフィックス（`...-ai-2.md`）は `-` が `.` より小さいため `...-ai.md` の**前**に来るので、辞書順で最後のファイルを取ると「その秒の最も古い記録」を最新として拾う。書き手（採番）と読み手（最新の判定）が同じキーを共有する
3. **standing な記録（kind を問わない）が 1 件も無ければ** `UNREVIEWED:`。ほとんどの場合それは「記録が 1 件も無い」ことだが、**記録はあるが全件が `result: discarded` だった**場合も含む — 破棄された判定は捨てられた下書きを見たものであり、ディスク上の本文について何も述べていない（`action: update` のエンティティで Pass 4 が `max_retries` を使い切ると既存ページはディスクに残ったまま `discarded` が記録されるので、この状態は普通に生じる）。後者では行に注記を添えて状態を区別する — 全件が `result: discarded` なら `(<N> record(s) exist, but every one was discarded; none judged the page as it now stands)`、そうでなければ `(<N> record(s) exist, but none carries a page_content_hash, so none judged the page as it now stands)`。**注記の理由は `result` から読む**（standing でなくした空ハッシュからではない）— 両者は `record_review.py` が書くものについては一致するが、このツリーは人間が手で書けることを意図しているため、`page_content_hash` を持たない手書きの記録を「破棄された」と言うと、存在しなかった破棄を探しに行かせることになる。専用の `DISCARDED_ONLY:` 行は足さない — 2 つの状態は「誰かがこのページを見なければならない」という同じ行動を要求するので 1 本の一覧でよく、`wikicommit-status` Step 17 はカテゴリごとに必ず 1 行を描画するので、ほぼ常に 0 の行を恒久的に足すことになる
4. **書き出されたページを判定した最新の記録 1 件**（kind を問わず `page_content_hash` が非空のもの。`standing_review()`）を見て、その `attempts >= 2` または findings が 1 件以上あれば `RISKY:` — **これが抜取の設計図**である（下記「`RISKY:` は履歴ではなく『今立っている判定』1 件だけを見る」）
5. **書き出されたページを実際に判定した最新の `kind: ai` 記録**（`page_content_hash` が非空のもの。`standing_verdict()`）について失効を判定する。`result: discarded` の記録は対象にしない — Pass 4 step 5 は `action: update` のエンティティに対しても `discarded` を記録し、そのとき既存ページはそのまま残る一方 `reviewed_sources` は `--sources-from`（＝取り込もうとしていたソース）から作られるので、ページ側に無いのが当然のソースと突き合わせて `source no longer on the page` を永久に報告し、しかも本当に有効な直前の判定を隠してしまう。突き合わせるのは機械が見た `reviewed_sources` なので AI の記録だけを見る:
   - `page_content_hash` を再計算して不一致なら `STALE_REVIEW:`（`page content changed since <日付>`）。空ハッシュ（`discarded`）はスキップ。**不一致でも、統合によるリンクの書き換えだけの差なら失効と数えない** — `.wikicommit/relations.yml` の統合の項目（`pages` と `merged_into`）から（吸収したページ, リンクが今指すページ）の組を作り（統合の連鎖 A → B → C は A と B・C の双方に組を作る）、組ごとに現在の本文（frontmatter を含む）の `[[Type/new]]` を `[[Type/old]]` に全置換した版を `record_review.py` の `compute_content_hash()` で計算し、どれかが一致すれば失効としない。部分的な置換は試さないので、統合前から両方にリンクしていたページは `STALE_REVIEW:` に出る（既知の限界）。`relations.yml` が無い・読めない場合は組を作らず、素のハッシュ比較になる。判定は `matches_recorded_content()` にまとめ、公開時のバナー（`convert_wikilinks.py`）も同じ関数を使う — 両者が食い違うと、`/wikicommit-status` が失効と言うページに公開側が判定を表示する
   - `reviewed_sources` の各エントリを現在のページの `sources[]` / `derived_from` と識別子（`url` / `path`）で突き合わせ、`hash` / `source_commit` が変わっていれば `STALE_REVIEW:`（`source changed: <識別子>`）、ページから消えていれば `source no longer on the page: <識別子>`
   - `reviewed_sources` に `status: retracted` のソースが含まれていれば `RETRACTED_EVIDENCE:`
6. `SUMMARY:` と、モデルごとの `COVERAGE:` を出す。`ai_reviewed` / `human_reviewed` と `COVERAGE:` の `pages` / `findings` / `attempts>=2` はいずれも standing な記録から数える（「レビュー済み」の分子は「今の本文を判定した記録があるページ」でなければ、カバレッジがそのまま過大表明になる）。`COVERAGE:` の 4 つ目の数（`<N> discarded`）だけは別で、**そのページの最新の AI 記録が `result: discarded` であり、かつそれをこのモデルが書いたページ数**を数える — standing な記録には現れない「投げ捨てられた試行」を、カバレッジを水増ししない位置に置き、`COVERAGE:` が静かな `RISKY:` と食い違って見えるのではなく、なぜ静かなのかを自分で説明するためのもの（新しい行ではなく既存行の 1 列なので Step 17 の行数は変わらない）。**モデルごとの最新ではなくページごとの最新で判定する** — この数は「`RISKY:` が黙っている理由」を説明するために在るので、後から別のレビューが今の本文を判定していれば説明すべき沈黙自体が無く、追い越された破棄は数えない

**`STALE_REVIEW:` がノイズにならないことは構造から言える** — Pass 4 は再生成のたびに走り直すので、失効するのは実質 `wikicommit-fix` で直したページと、ソースが変わったページだけである。統合の `rewrite_merged_links.py` が書き換えたページは、上の照合で外れる。

**`RISKY:` は履歴ではなく「今立っている判定」1 件だけを見る**。記録は不変で削除もされないため、全記録にわたって `max(attempts)` と findings 件数を集計すると、一度でもリトライされた・一度でも指摘を受けたページはその後どれだけクリーンに再レビューされても永久に `RISKY:` から外れず、取り込みを続ける Wiki ではこの一覧が Wiki 全体へ収束して何も選別しなくなる。「2 回目でようやく通った」という履歴は消えない — Pass 4 は 1 レビューにつき 1 記録を書き、その記録自身が `attempts` を持つ（全ラウンドの findings も `round` 付きでフラットに載る。`docs/DesignDoc-data.md` §4.8）ので、2 回目で通ったページの記録がそのまま standing な判定である。落ちるのは**より新しいレビューが現在の本文を判定した後**だけであり、それはその履歴がページを説明しなくなった時点そのものである。

**kind は問わない**（`standing_verdict()` ではなく `standing_review()` を使う）。`/wikicommit-review` は人間の判定にも `--result fail` と findings を書けるため、`kind: ai` に限ると人間の指摘が一度も `RISKY:` に出ない。人がそのページを読んで `result: pass` を記録すれば、その記録が standing になって結果として一覧から外れる — 別の規則ではなく、同じ規則が一様に適用された帰結である。「最後の人間レビュー以降に絞る」独立した機構は持たない（人間レビューが一度も無い Wiki では全記録の集計と同じに退化するうえ、人間が読んだことを抑制シグナルに使えるかは実データが無いと決められない）。

**2 つの基準は独立していない**: 手順 4 は `attempts >= 2` **または** findings >= 1 という OR だが、AI の記録では finding が出れば FAIL して再生成され `attempts` が増え、finding が無ければリトライする理由が無いので、実質 `attempts >= 2` 単独で動く（2026-09-12 に 1 リポジトリ・28 ページで数えた実測では `RISKY:` の全件が `attempts >= 2` と一致した）。findings 側が独立に効く経路は 2 つある: (1) `page_at_fault: "other"` しか持たないページ（非ブロッキングで `result: PASS` のまま `issues[]` に載る）、(2) **人間のレビュー** — `wikicommit-review` Step 5 は再生成ループを持たず常に `--attempts 1` で記録するため、`--result fail` の記録は必ず `attempts == 1` かつ findings > 0 になる（`tests/test_check_review_coverage.py::test_a_human_finding_makes_a_page_risky` が固定している）。**それでも OR を維持し、`attempts` と findings で扱いを分けない** — 片方を落とせばこの 2 経路（とくに人間の findings）が消える。

**`RETRACTED_EVIDENCE:` と `check_retracted_sources.py` は二重報告ではない**。あちらは「取り下げ済みソースを `sources[]` になお持つ**ページ**」を報告する。こちらが言えるのは、`reviewed_sources` にしか無い情報 — **その取り下げ済みソースが、判定を下した時点で証拠として使われていたのか**（前者は判定自体が撤回された証拠に依っていたことを意味し、レビュー後に足された場合は意味しない）。

**`kind: human` の `discarded` は現時点で到達しない**（`--result discarded` を書く呼び出し元は `--kind ai` だけである）が、`human_reviewed` も standing で数える — 挙動は変わらず、AI と human で数え方の非対称を残さないためである。

**記録は読み方を変えるだけで、1 バイトも書き換えない**（記録は不変）。

### 出力フォーマット

```
SUMMARY: pages=95, ai_reviewed=93, human_reviewed=12, human_notes=5, findings=27, models=2
COVERAGE: claude-opus-5[1m] 83 pages, 24 findings, 9 pages with attempts>=2, 1 discarded
UNREVIEWED: .wikicommit/entity/ja/Place/x.md
UNREVIEWED: .wikicommit/entity/ja/Place/u.md (2 record(s) exist, but every one was discarded; none judged the page as it now stands)
RISKY: .wikicommit/entity/ja/Place/y.md (attempts=3, findings=2)
STALE_REVIEW: .wikicommit/entity/ja/Person/z.md (page content changed since 2026-09-05)
STALE_REVIEW: .wikicommit/entity/ja/Place/w.md (source changed: https://example.com/a)
RETRACTED_EVIDENCE: .wikicommit/entity/ja/Place/v.md (the review of 2026-09-05 rested on https://example.com/b, since retracted)
```

### `human_notes` — 経路 A の Close に一言が来たかを数える

`review-issue-close-sync.yml` は Close した本人の最新コメントを記録の散文本文にする。**コメントが 1 件も無ければ本文なしの記録を書く** — 沈黙して閉じるのは正常な閉じ方であり、失敗ではない。

**数える理由**: コメントが来ても来なくても、ワークフローの全ステップ・`review_status`・`reviewed_by`・`deploy.yml` の再ビルド・公開バナーの読了行・`human_reviewed` の計上は同一で、違いは記録の散文本文が空であることだけである。`docs/DesignDoc-pipeline.md` §6.3 自身が「委任された Close 権限は機械では担保できない」と認めており、`Read by <login>` はこのプロジェクトの中心的な主張である。`reviewed_by` も `Reviewed-by:` トレーラーも「誰が閉じたか」しか言わず、**記録の散文本文だけが「読んだ」ことの痕跡**になる。`human_reviewed` だけでは、その件数が何かに裏づけられているかを読めない。

**`kind: ai` の本文は数えない。** あちらは Pass 4 の非ブロッキングな観察であって人の読了の痕跡ではなく、混ぜると 1 つの数が 2 つの別のものを指す。

**一方、数えるのは経路 A に限らない** — 本節が経路 A を主題にするのは動機がそこにあるためであって、判定は `kind` だけを見る。`/wikicommit-review`（経路 B。`stage: review-skill`）もレビュアーの一言を `--note` で書き込むため、その記録も本文を持てば同じく 1 件と数える。**この数を見て「追跡 Issue がコメント付きで Close された件数」と読まないこと** — 正しい読みは「standing な human 記録のうち本文を持つ件数」であり、経路の内訳が要るなら記録の `stage` を見る。

**置き場が `COVERAGE:` ではなく `SUMMARY:` なのは構造による。** `COVERAGE:` は `standing_ai.get("model")` で束ねた**モデル別**の行だが、`kind: human` の記録は `model` を持たない（`record_review.py` は human に `reviewer` を書き、`--model` を必須にするのは `--kind ai` の側だけである）— 載せる先が無い。`SUMMARY:` は既に `human_reviewed` を持っており、数えたいのはその内訳である。行は増えず、キーが 1 つ増えるだけである。

**記録ツリーが無い場合の早期 return にも同じキーを出す。** 片方にしか出ないキーは、読み手にとって「0 なのか、この版には無いのか」が区別できない。

**数えるのは有無であって、観察の中身を構造化しない**。frontmatter のキーも語彙も増やさず、per-page 行にもしない（Step 17 の行数は変わらない）。

**Close 時に 1 ビットを取る仕掛け（ラベル等）は保留であって否定ではない。** 採らない理由は `docs/DesignDoc-pipeline.md` §6.3 にある。再開の条件は「AI と人間の一致率を読む主体が実在したとき」であり、そのときには本キーが溜めた件数が最初の材料になる。

**公開側には出さない。** 俯瞰ページの読了件数は `convert_wikilinks.py` がページ frontmatter の `review_status` から数えており、記録の本文を一切見ていない。これは運用者向けの数である。

### 既知の限界

**`human_notes` が答えないもの**:

1. **一語のコメントも長文も同じ 1 件である。** 測れるのは「**依頼が届いたか**」であって「読まれたか」ではない
2. **`RISKY:` の選定が機能しているかは測れない。** それに要るのは件数ではなく**本文の中身と `RISKY:` の対応**であり、人が読んで初めて分かる
3. **「引っかかった」は記録されない。** `review-issue-close-sync.yml` は `--result pass` を固定で渡す（`docs/DesignDoc-pipeline.md` §6.3）

**孤児の記録は報告しない**。ページが削除されても記録は残す方針のため、実在しないページの記録が蓄積する。報告するか放置するかは実データが溜まってから決める — 今それを足すと、誰も求めていないものと引き換えに毎回 1 行増える。

**閾値・合否判定・自動化は入れない**。実測が無い状態で決めた閾値は推測にすぎない。人が `RISKY:` / `COVERAGE:` を読んで `/wikicommit-generate --regenerate` を叩けばループは人力で閉じる。

### 終了コード

- 常に `0`（情報提供のみ、ブロッキングしない）

---

## record_run.py

### 目的

このリポジトリの記録層のうち、git 履歴・ソース管理ファイル・レビュー記録・追跡 Issue は**いずれも成果物を単位にしている**（ファイル・ソース 1 件・レビュー 1 件・ページ 1 枚）。本スクリプトは**実行 1 回を単位とする記録**を書き、それらが答えられない次の 3 つに答える。

| 問い | 成果物単位の層が答えられない理由 |
|---|---|
| ページはいつ生成されたか | `generated_at` は日付。コミット時刻は**マージ**時刻。レビュー記録のファイル名の秒は Pass 4 が**見終わった**時刻で、リトライが入れば数分ずれる |
| 実行は完走したか | 途中で死ぬと一部が `pending`・一部が `generated` で止まり、「まだ順番が来ていない滞留」と**見え方が同じ**。ガード C・`rules_version` 不一致はファイルを 1 つも変えずに止まるため git に痕跡がゼロ |
| どれだけかかったか | どこにも無い |

**`generated_at` を日時に変えてもページ単位の精度にはならない** — Pass 3 はファイル境界プロトコルで複数ページを 1 回の出力にまとめて書くため、秒を打ってもバッチの全ページが同じ値を共有する。**ページ単位の点の時刻はそもそも存在せず、存在する単位は実行である。**

### git で追跡しない

レビュー記録（git で追跡する）とは逆に、実行記録は追跡しない。レビュー記録を追跡する理由は、いずれも実行記録には当てはまらない。

| レビュー記録を追跡する理由 | 実行記録は |
|---|---|
| Wiki の歴史全体にわたる**測定**が目的（測定は遡って作れない） | 消費者は「直近の実行」「未完走の実行」しか見ず、歴史を必要としない |
| 公開ページの表示に使う | 何も表示しない。`convert_wikilinks.py` はこのツリーを歩かない |
| 判定そのものがページの信頼に関わる | 実行の外形であり、Wiki の知識ではない |

追跡する代償は実在する: generate のたびに 1 ファイルが PR へ混ざり、**git では削除に意味がないため保持期間を決められない**。追跡しないことで、ローテーションが可能になり、`wikicommit-merge` は実行記録を扱わずに済み、lychee / markdownlint のスコープにも入らない（`git diff` に一切現れないため）。

**`.wikicommit/.cache/` には入れない**。あそこは再構築できる派生データ（`search_index.sqlite3`）の置き場であり、実行記録は再構築できない（`schemaorg-vocab.json` を `.cache/` の外に置くのと同じ理由 — 「気軽に消してよい」という名前の含意と実際の性質を揃える）。

代わりに諦めるもの（いずれも受け入れる）: クラウドセッションの記録は VM とともに消える（その実行の未コミット成果物も同時に消えるので整合する）、clone 先からは見えない、「このページはいつ作られたか」は**区間**としてしか答えられない — ただし上記のとおり点の時刻はそもそも存在しないので、追跡しても得られるのは区間だけである。

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
ended_at: "2026-09-07T11:05:12+09:00"   # 空文字列なら「閉じられなかった」（halt は閉じるので値を持つ）
model: "claude-opus-5[1m]"
wikicommit_version: "0.3.0"
args: ["https://example.com/article"]
sources: [".wikicommit/source/url/example.com/article.md"]
pages: [".wikicommit/entity/ja/Place/minuma.md"]
passes:                                  # 空リストなら「打点なし」
  - {pass: pass1-extract, at: "2026-09-07T10:44:02+09:00", token: unchecked,
     source: ".wikicommit/source/url/example.com/article.md"}
  - {pass: pass2b-type, at: "2026-09-07T10:51:37+09:00", token: ok,
     source: ".wikicommit/source/url/example.com/article.md"}
outcome: {generated: 12, failed: 1, excluded: 2}
halted_reason: ""
---
```

**本文は常に空である。** 他の `.md` 記録（`## Summary`・`## Failure Reason`・レビュー記録の散文）はいずれも frontmatter で表せないものを本文に持つが、実行記録は全項目がスカラーかリストで本文に書くことがない。形式は JSON ではなく他の記録に揃えて `.md` にする。空いているから何か書く、を誘わないため、本文を持たないことをここに明記する。

**`ended_at` の空文字列が「閉じられなかった」の信号である**（レビュー記録の `page_content_hash: ""` が「ページが書かれなかった」を表すのと同じ形）。長い多段フローの末尾で終了の打刻を忘れることはありうるが、**ここでは直す必要がない** — 開始があって終了が無い記録は、そのまま問い 2 の答えの片方になる。

**ただし問い 2（実行は完走したか）はこのフィールド 1 つでは決まらない**。halt の 2 経路（ガード C・`rules_version` 不一致）は `end --halted-reason` で記録を**閉じる**ため `ended_at` を持つ。読み手側の述語は `check_run_records.py` の `finished_normally()`（閉じていて、かつ halt していない）である（同スクリプトの節「halt して閉じた実行も `INCOMPLETE_RUN:` に出る」）。**新しい消費者を書くときに `ended_at` だけを見ないこと**。

**誤りの向きが重要である**: 打刻忘れは完走した実行を未完走として報告するだけで、逆は起こらない。偽の「未完走」は 1 回の確認で済む一方、偽の「完走」はこの記録が答えるべき唯一の問いを黙って葬る。**`end` が `--run <path>` を必須とし、同じ Skill の未完了記録を推測で閉じないのも同じ理由**である — 推測は前のセッションで本当に死んだ実行を閉じ、その信号を消す。

`end` と `checkpoint` は read-modify-write である（レビュー記録は意図的にこの形を避け、新規作成のみを行う）。ここで安全なのは一般化しない理由による: 実行記録は本文もコメントも持たないため YAML の round-trip で失うものが無い（コメントを持つ `config.yml` に同じことをすると記入例を丸ごと失う）。

### `checkpoint` — 実行の**どこまで**を残す

**`wikicommit-generate` の打点は `driver.py` が書く。** 工程の定義で `stamp: true` の工程が `done` で完了したとき、ドライバーが `make_stamp()` で同じ形の打点を `passes` に足す。打点は工程の**入口**ではなく**完了**の時刻になり、トークンの照合は `done` で行われて合わなければ工程を完了にしない（下記の「exit 1 は実行を止めない」「`token:` の 4 値を読む機械は無い」という限界は、ドライバー経由の実行では当たらない — 照合の失敗が、その工程を完了にしない理由として実際に使われる）。`record_run.py checkpoint` 自体は、ドライバーを使わない呼び出し元のために動く。記録の開き方も `open_record()` を共有するので、`check_run_records.py` は両方を同じように読む。

`ended_at` が答えるのは実行**全体**の生死だけで、その内側で何が起きたかには答えない。打点は残りの 2 つに答える:

| 問い | 打点が答えること |
|---|---|
| どこで止まったか | **最後に到達したパスが残る**。ガード C・`rules_version` 不一致は**ファイルを 1 つも変えずに止まる**ため、run 記録が唯一の痕跡である |
| パスが丸ごと飛ばされたか | **打点の欠落として検出**する。長い多段フローの末尾で手順が落ちる失敗は、決定論的スクリプトへ委譲しても、委譲したスクリプトを呼ぶ手順そのものが落ちれば同じ形で再発する。打点はその 1 段外側に立つ |

#### 照合の第三者はスクリプト自身である

単一エージェントでは「自分が読んだと自分に申告する」だけになり何も検証しない（`rules_version` の echo 検証が成立するのは、サブエージェントが JSON を返し orchestrator がそれを照合するという 2 者がいる場合に限られる）。

`--token` を渡すと `record_run.py` が `<Skill ツリー>/<skill>/references/<pass>.md`（Skill ツリーは `.claude/skills` → `.agents/skills` の順に探す。どちらかの写しが裏づければ `ok`）を**自分でディスクから開いて** frontmatter の `pass_token` と突き合わせる。**照合先のパスは引数で受け取らない** — 呼び出し側がファイルを指定できるなら、自分で書いたファイルを指すこともできてしまい、第三者性が消える。

| 失敗 | 検出 |
|---|---|
| パスが丸ごと飛ばされた | **打点の欠落**（`MISSING_PASS:` / `never ran`） |
| どこで止まったか | **最後の打点** |
| パスファイルを開かずに即興で実行した | **トークン不一致**（`token: mismatch`・exit 1） |
| ファイルは開いたが従わなかった | **検出不能**（`rules_version` と同じ限界。トークン行だけ grep することは防げない） |

`--token` を渡さず `--pass` だけで打点することもでき、上表の上 2 行はそれで成立する。

**トークンが照合できなかった場合も打点は書かれる**（`token: mismatch` / `token: missing`）うえで exit 1 を返す。書かずに落ちると「そのパスは始まってすらいない」という別の（そして誤った）話になるため。

**そして exit 1 は実行を止めない。** `SKILL.md` がその契約を明記している — `missing`（照合先が無い。配布物の版ずれ・インストールの破損）も `mismatch`（逸脱）も、実行を止めるのが正しい場面が無いためである。前者は環境の問題でありページにもソースにも欠陥は無く、後者は既に打点として記録されている。

**`token:` の 4 値を読む機械は無い**（`check_run_records.py` は `token` を読まず、`MISSING_PASS:` が見るのは打点の**有無**だけである）。したがって `record_run.py checkpoint` 経由では、照合の失敗が届く先は exit 1 だけであり、それを受け取るのは照合の対象であるエージェント自身である。上の契約はこの exit 1 を無効化するので、`mismatch` は記録されるが誰にも報告されない。**`token:` に消費者を与える（`/wikicommit-status` が人間に報告する）のは、`token: mismatch` を持つ記録が実在してから**にする — 報告の形も閾値も実測なしに決めることになるため。

#### 打点の粒度と、Pass 2a に打たない理由

`wikicommit-generate` の `EXPECTED_PASSES` は `pass1-extract` / `pass2b-type` / `pass2c-entities` / `pass3-generate` / `pass4-review` の 5 つで、**ソース 1 件につき 1 周**打つ（`--source` がその周回の対象を持つ）。パス単位だけにするとソース 3 件目で止まったことが分からない — パス名は繰り返し現れるので、`--source` が無いと 1 件目で死んだ実行と区別が付かない。

**Pass 2a には打たない**。Pass 1 の抽出と地続きに無条件で走り、分岐も停止経路も持たないため、そこに打点しても Pass 1 の打点が示す位置以上のことは分からない一方、ソースごとに read-modify-write が 1 回増える。

`--pass` は `EXPECTED_PASSES` に対して検証する。打ち間違いを通すと**未知のパスが 1 つ増え、同時に本物のパスが「実行されなかった」ように見える** — 1 つのミスが 2 つの誤った所見になり、しかもどちらも実際の問題ではない。

`--regenerate` の実行では期待集合が `pass1-extract` / `pass3-generate` / `pass4-review` の 3 つに狭まる（同モードは Pass 2 を実行しない。`docs/DesignDoc-pipeline.md` §6.1）。判定は記録自身の `args` を読んで行う — 呼び出し側に再申告させない。

#### read-modify-write のコスト

打点も `end` と同じ read-modify-write であるため、ソース件数 × パス数だけ回数が増える。RMW を許す根拠（実行記録は本文もコメントも持たないので YAML の round-trip で失うものが無い）は回数によらず成立し、実行時間の大半は LLM 推論であるため相対的な影響は無い。

#### 既知の限界: compaction は打点の指示を落としうる

打点忘れの誤りの向きは `ended_at` と同じで安全側である（打たなければ「実行されていない」と報告され、逆は起こらない）。ただしこれは**打点の指示がコンテキストに残っていること**に依存する — context compaction が指示を落としたまま実行が続けば、実際には走ったパスが `MISSING_PASS:` として報告される（偽陽性）。SKILL.md 側にも同じ限界を明記してある。

**クラウドセッションでは記録が VM とともに消える**。そして無人実行こそ compaction をいちばん踏む経路であり、**検証手段がいちばん検証したい環境で残らない**。git 追跡対象にはしない（上記「git で追跡しない」）代わりに、`wikicommit-generate` の Completion Notice が打点の要約を 1 行出す（PR 本文経由でそこだけは残る）。

### 記録しないもの

| 除外 | 理由 |
|---|---|
| コスト・トークン数 | その実行を回した運用者自身の契約・課金の事情であり、この記録の対象である実行の**外形**ではない |
| ページ本文・抽出テキスト・LLM の出力 | ページ自身と管理ファイルが既に持っている |
| 個々の判断（除外理由・findings・却下した型候補） | `## Summary` と `.wikicommit/review/` の担当。ここは実行の**外形**だけを持つ |
| スクリプト単位の実行時間 | 時間の大半は LLM 推論でスクリプトの外にある。安い決定論的部分だけを測ることになる |

### ローテーション

書き込み時（`start`）に、新しい順で `KEEP_RECORDS`（50）件を残して残りを削除する。順序は `run_sort_key()` が決める — ファイル名は `<YYYYMMDD>-<HHMMSS>` で始まるので素の辞書順でもほぼ時刻順になるが、同一秒の衝突サフィックス（`...-generate-2.md`）は `-` が `.` より小さいため未サフィックスの名前より**前**に来る。素の辞書順で回すとその秒の最も新しい記録から先に消え、`check_run_records.py` が最後の 1 件を `LAST_RUN:` に採ると最も古い記録を拾う。`record_review.py` が `record_sort_key()` を書き手と読み手で共有しているのと同じ理由で、こちらも同じキーを共有する。**未完了の記録も例外にしない** — ディレクトリを有界に保つことが目的であり、末尾から落ちるほど古い実行は対処対象ではなくなっている。削除に失敗しても実行は止めない（後始末が、それが付随する実行を道連れにしてはならない）。件数で回すのは 1 ファイルが数百バイトだからで、日数の判定に時計を持ち込む必要が無い。

**採番は壁時計に依存させない**。`allocate_run_path()` は**そのディレクトリに既にある最新記録まで切り上げてから採番する**（`record_review.py` の `allocate_record_path()` とまったく同じ形。決定の全体は `docs/DesignDoc-data.md` §4.8）— ホストが時計を後方へ動かすコンテナでは、`datetime.now()` のスタンプをそのまま使うと連続する 2 件が逆順のスタンプを得て、ローテーションが最新の実行を削除しうる。**採番はファイル名ではなくスタンプを見る**（`next_seq()`）— skill スラッグは `run_sort_key()` の一部ではないため、`generate` の隣へ切り上げた `merge` の記録が空いている `<stamp>-merge.md` を取ると**同値になり**、安定ソートである `sorted()` は `LAST_RUN:` の選択もこのローテーションの削除対象も `glob()` の順に委ねてしまう。同じ理由で、ローテーションがそのスタンプの seq 1 を削って空けた未サフィックスの名前も再利用しない（再利用すると最新の実行が最古の位置に着地する）。

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

## driver.py

### 目的

多段の Skill の**工程の順序**をエージェントの記憶からスクリプトへ移す（設計の全体と、捏造に耐えないことを受け入れる理由は `docs/DesignDoc-skills.md` §11.0「多段の Skill の進行はドライバーが持つ — 判断はエージェントが持つ」）。エージェントは `next` が返す 1 工程だけを行い、`done` で報告する。ドライバーはその工程の確認スクリプトでディスクを見て、通れば記録して次を返し、通らなければ同じ工程を返す。

**エンジンは WikiCommit 固有の知識を持たない。** 工程の並び・結果の値・完了の確認は Skill ごとの工程の定義（`<skill>/workflow.yaml`）と確認スクリプト（`<skill>/scripts/workflow_checks.py`）にあり、保存は `record_run.py` に任せる。`tests/test_driver.py` がエンジンのコードにパス・`status` の値・パスの名前が現れないことを固定する。

### コマンド

```
python .wikicommit/scripts/driver.py start --workflow <skill>/workflow.yaml --model <id> [--arg <a>]... [--non-interactive]
python .wikicommit/scripts/driver.py next <run>
python .wikicommit/scripts/driver.py done <run> --step <id> [--item <item>] [--outcome <o>] [--answer <a>]
    [--token <t>] [--reason <why>] [--add NAME=VALUE]... [--touched PATH]... [--page PATH]... [--count KEY=VALUE]...
python .wikicommit/scripts/driver.py status [--stop-hook]
python .wikicommit/scripts/driver.py check-merge [<changed file>...]
python .wikicommit/scripts/driver.py abandon <run> --reason <why>
```

出力はすべて JSON（stdout）。`start` / `next` / `done` は同じ形で「今の工程」を返す — `step`・`type`・`item`・`instructions`・`also_read`・`outcomes`（または `human` 工程の `ask`・`choices`）・`then`（次に実行するコマンドの雛形）・`notes`（ドライバーが自分で実行したスクリプトの出力。版ずれの警告など、利用者に伝えるもの）。実行が終われば `step: null` と `finished` または `halted_reason`。

### 工程の定義

| キー | 意味 |
|---|---|
| `skill` | 実行記録の `skill`（`record_run.py` の `SKILLS` のいずれか） |
| `record_sources` | 実行が終わったとき、この名前の一覧を実行記録の `sources` に書く |
| `steps[].type` | `agent`（エージェントが手順ファイルを読んで行う）・`human`（エージェントが人に尋ねる）・`script`（ドライバーが実行する） |
| `when` | コマンド。exit 0 ならこの工程を行い、1 なら飛ばす（飛ばしたこともログに残す） |
| `instructions` / `also_read` | 手順ファイル（Skill ディレクトリ相対）。frontmatter に `pass_token` があれば、`done --token` がそれと一致しないと完了にしない |
| `outcomes` | `done --outcome` が取れる値と、その意味 |
| `check` | 完了の確認。exit 0 で完了、それ以外は理由を返して同じ工程のまま |
| `ends_item_on` / `halts_on` / `finishes_on` | その結果で、この項目の残りの工程を飛ばす／実行を止める（`--reason` 必須）／実行を正常に終える |
| `check_on_halt` | `halts_on` の結果でも `check` を実行する（既定では halt は確認を飛ばす。止まる前に保留を書く工程が、その保留を確認させるためのもの） |
| `adds` | `done --add NAME=VALUE` で延ばせる一覧 |
| `produces` / `finish_if_empty` | `script` 工程の stdout の `ITEM:` 行を一覧にする／空なら実行を正常に終える |
| `for_each` + 入れ子の `steps` | 一覧の項目ごとに入れ子の工程を繰り返す |
| `stamp` | 完了時に実行記録の `passes` にも打点する（`check_run_records.py` の `MISSING_PASS:` がこれを読む） |
| `non_interactive` | `human` 工程では誰もいないときの答え。`agent` 工程では、工程の中で人に尋ねる箇所の非対話時の扱いを文で書き、ドライバーが工程とともに渡す |

コマンドは引数のリストで、リポジトリルートからシェルを介さずに実行する。`{python}`・`{skill_dir}`・`{run}`・`{item}`・`{outcome}` が置き換わる。確認スクリプトが `TOUCHED: <path>` を出すと、そのファイルは実行の `touched` に加わる（`check-merge` が読む）。

### 状態 — ドライバーは状態を持たない

状態はすべて実行記録の `driver:` キーにある: 工程の定義のパスとハッシュ、対話か否か、一覧、ログ（工程・項目・時刻・結果・答え・照合の結果）、確認に失敗した回数、触れたファイル、実行の状態（`running` / `finished` / `halted` / `abandoned`）。**次の工程は呼ばれるたびにログをリプレイして決める**ので、compaction の後も新しいセッションでも `next` を呼べば同じ工程が返る。条件やスクリプトを実行する前に記録を保存する — スクリプトは記録を自分で読むため、1 つ前の工程が作った一覧は、その時点でディスクに無ければならない。

`done` は**今の工程にしか**受け付けない（別の工程・順番を飛ばした報告は、今の工程を返して断る）。確認に `MAX_CHECK_FAILURES`（3）回続けて失敗すると、`next` は `blocked: true` を返し、止めて人に報告するよう指示する。

実行中に工程の定義が変わった場合（Skill を更新した場合）は、ハッシュの違いを `notes` の警告として伝えて記録のログのまま続ける。ログにある工程が定義から消えていれば、続けられないので `abandon` して始め直すよう返す。

### 終わり方と `check_run_records.py`

| 終わり方 | 実行記録 | `check_run_records.py` |
|---|---|---|
| 最後の工程が完了 / `finishes_on` / `finish_if_empty` | `ended_at` を書き、`halted_reason` は空 | 正常に完走 |
| `halts_on`・`script` 工程の失敗 | `ended_at` と `halted_reason` | `INCOMPLETE_RUN:`（halt は正常な完走ではない） |
| `abandon` | 同上（`abandoned: <理由>`） | `INCOMPLETE_RUN:` |
| 報告されないまま | `ended_at` が空 | `INCOMPLETE_RUN:` |

### `check-merge`

開いたまま（`running`）の実行のうち、`touched` が変更されたファイル（引数、無ければ `git status --porcelain`）と重なるものがあれば exit 1 で止める。**止めるのは「未完了の実行があるか」であって「すべての変更がドライバーを経たか」ではない** — ドライバーを使わない経路（`fix` / `remove` / `review` / 手編集）の変更と、終わった実行（完走・halt・abandon）の変更は通す。実行記録は git で追跡しないので、merge を実行したマシンの実行しか見えない。

### `abandon`

死んだセッションの実行を閉じる。触れたファイルのうちまだ変更されているものを `left_behind` として返す — **黙って通さず、黙って消しもしない**。人が判断してから実行する（`/wikicommit-merge` の案内もそう書く）。

### `status --stop-hook`

Claude Code / Codex の Stop フックから呼ぶ。開いた実行があれば `{"decision": "block", "reason": ...}` を返し、無ければ何も出さない。同じ停止の試みの中での 2 回目（ペイロードの `stop_hook_active`）は通す。

### 終了コード

- `0`: 成功（`done` が受け付けた・`check-merge` が止めなかった・`start` / `next` / `status` / `abandon`）
- `1`: `done` が受け付けなかった、`check-merge` が止めた
- `2`: 使い方の誤り・工程の定義が読めない・実行記録が無い

---

## check_run_records.py

### 目的

`record_run.py` が書いた記録を読み戻す。**消費者が同時に存在すること**が要件である — 読む主体が無ければ、記録ツリーは常に空のまま残る受け皿になる。

| 行 | 答える問い |
|---|---|
| `LAST_RUN:` | 直近の実行はいつ・どの Skill・どれだけかかって・いくつのパスを踏んで・何を produce したか |
| `INCOMPLETE_RUN:` | **正常に完走しなかった**実行はどれか — 閉じられなかったもの（`ended_at` が空）と、halt が閉じたもの（`halted_reason` が非空）の両方。`halted_reason` と halt までの所要時間を添え、打点があれば**どこまで到達したか**も添える |
| `MISSING_PASS:` | **正常に完走したのに打点の無いパスがある**実行はどれか |

**3 行とも `wikicommit-status` Step 14 が読み、Step 17 が 1 行ずつ表示する**。`tests/test_run_record_surface_wiring.py` が、このスクリプトが stdout に出す全接頭辞を SKILL.md が参照していることを CI で固定する（書く側と読む側が別ファイルにあり、片方だけ足しても何も壊れないため）。

**`MISSING_PASS:` は所見であって断定ではない** — `check_installed_type_usage.py` の `ANCESTOR_FALLBACK:` と同じ姿勢を採る。全ソースが Pass 1 でブロックされた・全件が既に最新だった、といった場合には Pass 2 以降に何もすることが無く、そこで終わるのは正常である。この行が言うのは「完走したが飛ばしたものがある」ことまでで、それ自体は不具合を意味しない。**正常に完走していない実行はこの行に出さない** — 既に `INCOMPLETE_RUN:` が報告しており、そこには欠落の明白な理由がある。二重に出すと、片方（"finished, but"）が偽になる。

**`passes` キーを持たない記録については、パスについて何も出力しない**。打点を持たない古い形式の記録がこれに当たり、報告のしようがない。

**一方 `passes: []`（打点が 1 つも無い）は報告する**。2 つは別の状態であり、`start` が空リストを**明示的に**書くのはまさにそれを区別するためである。判定は `records_passes()` が `passes` キーの有無で行う — 「打点が 1 件以上あるか」で門番をすると両方が同じ側に落ち、context compaction が全部の打点指示を落とした最悪のケースだけが報告されなくなる。

**ただし zero-stamp の記録は「その実行が実際に何かをした」ことが記録から読めるときだけ報告する**（`work_recorded()`。`sources` / `pages` が非空、または `outcome` に 0 でない値がある）。門番が要るのは、**打点ゼロで完走するのが正常かつ最も普通な経路が実在する**ためである — 引数なしの `/wikicommit-generate` は処理対象の管理ファイルが 1 件も無ければ「No management files to process」と言って終了し（Pass 1 手順 2）、最新状態の Wiki ではそれが通常の結末になる。無条件に報告すると大半の実行でこの行が点灯し、常時点灯する行は読まれなくなる。Step 0 で止まった実行も `sources` / `pages` / `outcome` のいずれも記録していないため、専用の規則なしにこの門番で落ちる。

**報告する行は、その門番が受け付けた形を必ず名指しする**（`_work_summary()`）。zero-stamp の行が印字されるのは「記録が仕事を示しているから」であり、その根拠が現れる場所はこの節しか無い — したがって `work_recorded()` が work と認める形を `_work_summary()` がdescribe できなければ、この行が出す最も強い所見が根拠を 1 つも述べずに印字される。整ったリスト・マッピングだけを数えると、手編集の記録が持ちうる緩い形（リストの位置にスカラー・マッピングでない `outcome`。`work_recorded()` はこれを意図的に work として受け付ける）がちょうどそこに落ちる。`tests/test_check_run_records.py` が「`work_recorded()` が真なら `_work_summary()` は非空」を組み合わせ全体に対する不変条件として固定する — 2 つは別の関数であり、他に両者を結び付けるものが無いため。

**打点しない Skill に対する誤検知は構造的に起こらない**。`expected_passes()` は `EXPECTED_PASSES` に無い Skill に対して `()` を返し、報告の条件は `missing_passes()` が非空であることを要求するため、`wikicommit-translate` / `wikicommit-synthesize` / `wikicommit-merge` の `passes: []` は行を 1 本も出さない。将来 `EXPECTED_PASSES` に Skill を追加したときに初めてこの軸が効きはじめる。

**`LAST_RUN:` は 1 件のみ**。答える問いは「いま走らせたものが何かに到達したか」であって履歴ではなく、しかも履歴はローテーションで有界であるため、長い一覧は完全な窓ではなく恣意的な窓を報告することになる。**未完了の記録は全件を列挙する** — 個別に対処できるものであり、件数はローテーションが既に抑えている。

**halt して閉じた実行も `INCOMPLETE_RUN:` に出る**。halt の 2 経路（ガード C・`rules_version` 不一致）は `record_run.py end --halted-reason` で記録を**閉じる**ため `ended_at` を持つ。`ended_at` を「完走したか」の代理指標にすると、halt は完走側に落ち、`MISSING_PASS:` に偽の "finished" として出るか（Pass 2c 以降に到達しないのは halt の意味そのものであって「飛ばした」ではない）、`EXPECTED_PASSES` を持たない Skill では 1 行も出ない。したがって `finished_normally()` が「閉じていて、かつ halt していない」を判定し、`INCOMPLETE_RUN:` と `MISSING_PASS:` の両方をそこから導く — `MISSING_PASS:` 側から halt を外す分岐は書かない（同じ述語から自動的に落ちる）。判定材料は `halted_reason` だけなので、`EXPECTED_PASSES` を持たない Skill の halt も同じ 1 行が覆う。

**`HALTED_RUN:` は設けない**。(1) 述語が 2 つになり、手編集で `halted_reason` を持ち `ended_at` が空の記録は両方の行に出るため優先規則が要る、(2) `wikicommit-status` Step 17 の run 行が増え、しかもほぼ常に 0 の行になる、(3) 意味の上でも 3 行は「直近」「正常に完走しなかった」「正常に完走したが飛ばした」に答えており、halt は 2 番目に属する。**`end --halted-reason` が `ended_at` を書かない形にもしない** — やることは同じなのに halt までの所要時間が失われる。ガード C の halt（取得前・即座）と `rules_version` 不一致の halt（Pass 4 到達後）は経過時間が桁違いであり、そこが読めなくなる代償に見合わない。

**代償は「打刻忘れ」と「halt」の区別が `halted_reason` だけに依ることである**。ただし両者を分ける値は元からそれしかなく、しかも行に載っている — `describe_incomplete()` は `ended_at` の有無で文面を分け、halt では `halted: <理由> (<経過時間>)`、閉じられなかった記録では `no ended_at` と述べる（両方に当てはまる手編集の記録は両方を述べる）。`describe_last()` も halt に 1 語添える — `LAST_RUN:` は 1 件しか出ないため、そこに halt が来たときに「5 分かかった実行」としか読めないままにしない。

**打刻忘れもここに出る**。これは欠陥ではなく `record_run.py` の「誤りの向き」の帰結として受け入れる。

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
INCOMPLETE_RUN: 2026-09-05 14:03 wikicommit-generate (no ended_at — reached pass2b-type; pass2c-entities, pass3-generate, pass4-review never ran)
INCOMPLETE_RUN: 2026-09-05 16:20 wikicommit-generate (halted: missing package: youtube-transcript-api (20s) — reached pass1-extract; pass2b-type, pass2c-entities, pass3-generate, pass4-review never ran)
MISSING_PASS: 2026-09-06 09:10 wikicommit-generate (finished, but pass4-review left no stamp)
SUMMARY: runs=7, incomplete=2, missing_pass=1
```

`INCOMPLETE_RUN:` の 2 行は同じ行の 2 つの形である — 上が閉じられなかった記録（`ended_at` が空）、下が halt が閉じた記録（`halted_reason` が非空）。後者だけが halt までの所要時間を持つ。

打点が 1 つも無い（`passes: []`）実行の行は形が変わる — 飛ばされたのが 1 パスではなく全部であることを、5 つのパスを一つずつ飛ばしたかのように列挙せずに述べ、報告する根拠（その実行が記録している仕事）を添える:

```
MISSING_PASS: 2026-09-06 09:10 wikicommit-generate (finished but stamped no pass at all — the record holds 3 source(s), 12 page(s), generated=12; pass1-extract, pass2b-type, pass2c-entities, pass3-generate, pass4-review never ran)
```

ディレクトリが無い・記録が 1 件も無い場合は `SUMMARY: runs=0, incomplete=0, missing_pass=0` と `NOTE:` を出す — 「まだ一度も実行が記録されていない」と「全部の実行が完走した」は別の状態であり、0 だけを出すと後者に見える。読めない記録は stderr に `WARNING:` を出して飛ばす（黙って落とすと、ここで唯一高めに誤るべき数である未完了件数を過少に報告することになる）。

### 既知の限界

**記録は git で追跡されないため、この報告はそのチェックアウトに限られる** — clone 先は 1 件も見えず、クラウドセッションの記録は VM とともに消える。ここが 0 であることは「このマシンに記録が無い」を意味し、「実行されていない」を意味しない。

**打点の欠落は、パスが走らなかったことの間接的な証拠にすぎない**。指示が context compaction で落ちれば、走ったパスも打点を残さない（`record_run.py` の同名の節を参照）。誤りの向きは安全側 — 本当に飛ばされたパスが「走った」と報告されることはない — だが、`MISSING_PASS:` の偽陽性はありうる。

**zero-stamp の報告は `end` が仕事を記録していることに依存する**。compaction が打点の指示を落とす実行では、同じく末尾にある `end` の `--source` / `--page` / `--outcome` も落ちうる — フラグを 1 つも付けずに閉じられた記録は `work_recorded()` が偽になり、報告されない。`end` 自体が呼ばれなければ `ended_at` が空になり `INCOMPLETE_RUN:` が拾うため、**取りこぼしが残るのは「`end` は呼ばれたがフラグが全部落ちた」という 1 通りに絞られる**。指示上は `end` とそのフラグが同じ 1 行にあるため、この組み合わせは起こりにくい。**`wikicommit-status` Step 14 の説明はこの取りこぼしを明記する** — `missing_pass=0` が「パスを飛ばしていない」ことの証明ではない、と運用者が読む側に書いておく必要があるのは、`docs/` が配布されないためである。

halt した実行は `halted_reason` を持つため、`MISSING_PASS:` の門番（zero-stamp 側を含む）に到達しない。

### 終了コード

- 常に `0`（報告のみ、ブロッキングしない）

---

## check_retracted_sources.py

### 目的

`status: retracted` は、人間が登録済みのソースを読み、内容が信用できないと判断して以後の取り込み対象から外したことを表す。この値を書くと**そのソースが再び取り込まれることは構造的に止まる**（`add_source.py` が `RETRACTED` を返して再登録せず、`check_ingest_freshness.py` が `outdated` へ書き戻さない）が、**既にそのソースから書かれたページには何も起こらない** — それらは `sources[]` にそのソースを持ったまま、何の印も付かずに残る。本スクリプトはその穴を、**行動ではなく報告で**塞ぐ。

「報告に留める」ことは意図的な決定である:

- **`review_status` を `pending` に戻さない**。`pending` への降格は「内容が実際に変わったか」を決定論的スクリプト（`reset_review_on_content_change.py`）が判定する規範であり、取り下げでは**内容が変わらない** — 変わるのはその内容の根拠であり、同じ機構では表現できない
- **戻しても何が失われたかは伝わらない**。追跡 Issue のテンプレートは `sources` の妥当性を問わないため、`pending` は「読み直せ」とは言うが「何を直せ」を言わない

そのページに対して既存 3 経路のどれを使うかは人間の判断であり、本スクリプトの役目はその判断材料を出すことに尽きる: 残りのソースで作り直すなら `/wikicommit-generate --regenerate`（取り下げたソースを落として作り直す。残りが 1 件以上あることが条件。ただし再生成モードは `sources[].type: manual` を 1 件でも持つページを除外する一方、この「残り件数」は `manual` エントリを 1 件として数えるため、残りが `manual` のみのページは `/wikicommit-fix` に回る）、記述を手で直すなら `/wikicommit-fix`、ページごと下ろすなら `/wikicommit-remove`。**所見に添える「残りのソース件数」がこの選択を決める数**である。

### 使用場面

- `wikicommit-status` Skill：Step 12（既定モード）
- `wikicommit-review` Skill：Step 4 item 1（`--list`。ソース文書を取得する前）
- `wikicommit-fix` Skill：Step 3（同上）

### コマンド

```
python .wikicommit/scripts/check_retracted_sources.py
python .wikicommit/scripts/check_retracted_sources.py --list
```

既定モードは引数なしで、`.wikicommit/source/` と、`.wikicommit/entity/` + `.wikicommit/view/` の全体を対象とする。`--list` は `.wikicommit/source/` だけを走査し、ページを 1 枚も読まない。

### 処理フロー

1. `.wikicommit/source/**/*.md` を走査し、`status: retracted` な管理ファイルの `source.path` / `source.url` を「取り下げられた識別子 → 管理ファイルのパス」の対応表にする。**識別子をキーにするのは、それが `add_source.py` の同一性判定が使うキーであり、かつページの `sources[]` エントリが持つ値そのものだからである** — 導出された管理ファイル名をキーにすると、旧命名規則で作られた管理ファイル（自動移行しない）を取りこぼす
2. 取り下げが 1 件も無ければ `SUMMARY: retracted_sources=0, affected_pages=0` を出して即座に終了する。この 0 を「該当ページ 0 件」と区別できるよう、両方の数を出す — 何も取り下げていない Wiki と、取り下げたが影響ページが無い Wiki は別の状態である
3. `.wikicommit/entity/` と `.wikicommit/view/` の全ページ（`index.md`・`status: removed` を除く）の `sources[]` を読み、上記の識別子に一致するものを `RETRACTED_SOURCE:` として報告する。行には**そのページに残っている他のソースの件数**を添える — 何をすべきか（残りで作り直せるか、ページごと下ろすほかないか）を決めるのはこの数である

### `--list` — 参照側 2 経路のためのガード

手順 1 の対応表をそのまま印字して終わる（手順 2〜3 は行わない）。`wikicommit-review` / `wikicommit-fix` が、ページの `sources[]` を取得しに行く**前に**実行ごと 1 回呼び、返ってきた識別子と自分の `sources[]` を突き合わせる。

**別のスクリプトを作らずここに置く理由**は `docs/DesignDoc-data.md` §4.3「`retracted`」の参照側のガードにある（要点: 判定は既にこのファイルにあり、同一性キーの規則の写しを増やさない。§11.5 の置き場所の規則もこれで満たされる）。**ルックアップにはしない** — 識別子を受け取って 1 件を答える形は `check_*` の「走査して報告する」という形から外れる。突き合わせは呼び出し側が行う。

**出力は `resolve_source_cache_path.py` の `RETRACTED:` 行と同じ形にする**（`RETRACTED: <識別子> (<管理ファイルのパス>)`）。参照側 3 経路が同じ形を読むことになり、かつ管理ファイルのパスは人間が書いた `## Retraction Reason` の在り処である — 何が起きたかの唯一の説明はそこにしかない。

**終了コードは既定モードと同じく常に 0 である**。取り下げが 1 件でもあることを終了コードで伝えない — あちら（`resolve_source_cache_path.py`）が exit 2 を使うのは識別子 1 件への問い合わせだからで、こちらは一覧であり、`check_*` の契約（常に 0）に揃える。

**呼び出し側はこのモードが無い場合に止まってはならない**。`.wikicommit/scripts/` が古いリポジトリには存在せず、その場合の劣化は「取り下げ済みソースのガードが無い」だけである。ただし無言で劣化させず、その旨を報告して続行する（`docs/DesignDoc-data.md` §4.3）。

### view ツリーの扱い

走査対象に**含める**が、view ページは `sources[]` を持たず `derived_from` のみを持つため、直接一致することはない。それでも除外しないのは、走査の対象と所見の有無が別の話であり、除外すると「view ページは見ていない」という事実が読む側から消えるためである。

**間接的な影響（取り下げられたソースに立つ entity ページを grounding にしている view ページ）は本スクリプトの対象外**とする。`derived_from` を辿るのは `check_derivation_freshness.py` の役目である。**ただしそのカバレッジは条件付きである** — あちらが発火するのは grounding ページが**実際に書き換えられた**ときであり、取り下げはページを 1 バイトも変えない。したがってカバーされるのは「人が取り下げに対処した後」（`--regenerate` で grounding ページが変わる → view ページが STALE）だけで、**grounding ページが取り下げ済みソースに立ったまま誰も何もしていない状態には届かない**。それでも対象外にする理由は別にある（`docs/DesignDoc-data.md` §4.3。要点: 2 ホップの間接のために `status` の解釈者を増やすより、直接の半分をこのスクリプトが grounding ページ自身として名指しする方が、人は 1 ホップ手前で同じ情報を受け取れる）。この条件付きであることを書かずに済ませると、次に読む人が「あれが見ている」と読む。

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

`--list`:

```
RETRACTED: https://example.com/listing (.wikicommit/source/url/example.com/listing.md)
RETRACTED: raw/report-2019.pdf (.wikicommit/source/path/raw/report-2019.pdf.md)
SUMMARY: retracted_sources=2
```

`--list` で該当なしの場合は `SUMMARY: retracted_sources=0` のみ（`affected_pages` はページを読んでいないので出さない — 0 と書くと走査した結果に見える）。

### 終了コード

- 常に `0`（警告のみ、ブロッキングしない）。`--list` も同じ

---

## check_actions_pr_permission.py

### 目的

"Allow GitHub Actions to create and approve pull requests"（Settings → Actions → General → Workflow permissions）リポジトリ設定が有効かを確認する。`review-issue-close-sync.yml` の `Commit and open PR` ステップはこの設定に依存しており、無効なまま放置されると自動マージが失敗する。`wikicommit-init` はこの設定をベストエフォートで自動有効化しようと試みるが、その試行が失敗しても通常の操作では痕跡が残らない — 失敗が顕在化するのはレビュー追跡Issueをcloseした数日後、しかもGitHub Actionsのログの中という運用者・読者どちらの目にも普段触れない場所でしかない。本スクリプトは `wikicommit-status` の定期実行のたびにこの設定を再確認することで、ドリフトを事故ではなく能動的に検知できるようにする。

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
2. `gh auth status` が失敗する場合、設定を確認できない旨を `WARNING`（`SUMMARY: enabled=unknown`）として出力する（沈黙させない — 本スクリプトが塞ぐのは「失敗が検知できないこと」であり、確認不能をサイレントスキップすると同じ穴を繰り返すことになる）
3. `gh repo view --json nameWithOwner -q .nameWithOwner` でリポジトリを特定できない場合も同様に `WARNING`（`SUMMARY: enabled=unknown`）
4. `gh api repos/{owner}/{repo}/actions/permissions/workflow` を呼び出す。呼び出し自体が失敗した場合（権限不足等）も `WARNING`（`SUMMARY: enabled=unknown`）
5. レスポンスJSONが解析できない場合も `WARNING`（`SUMMARY: enabled=unknown` — レスポンスの中身を確認できない以上、真偽いずれかを断定しない）
6. 解析できた場合、`can_approve_pull_request_reviews` が `true` なら `OK`（`SUMMARY: enabled=true`）。`false` なら `WARNING`（`SUMMARY: enabled=false`）とし、有効化コマンド（`gh api -X PUT repos/{owner}/{repo}/actions/permissions/workflow -F can_approve_pull_request_reviews=true -f default_workflow_permissions=<同レスポンスの値をそのまま再送>`）をメッセージに含める

**読み取り専用**（`wikicommit-init` の Step 3 と異なり、この設定を自動修復しない）: `wikicommit-status` は定期ヘルスチェックであり、ユーザーの目に触れないままリポジトリ設定を書き換えるのは踏み込みすぎである。有効化コマンド自体は `wikicommit-init` Step 3 と同じ `gh api -X PUT ...` をそのまま提示する。

### 出力フォーマット

```
OK: acme/example-wiki: "Allow GitHub Actions to create and approve pull requests" is enabled
SUMMARY: enabled=true
```

```
WARNING: acme/example-wiki: "Allow GitHub Actions to create and approve pull requests" is disabled, so review-issue-close-sync.yml cannot auto-merge after a review tracking Issue is closed. Enable it with: gh api -X PUT repos/acme/example-wiki/actions/permissions/workflow -F can_approve_pull_request_reviews=true -f default_workflow_permissions=write
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

型テンプレートの Entity-only/Mixed な `properties:` キーのうち、WikiLink 化への補強を持たないものを検出する（`docs/DesignDoc-skills.md` §11.6「`properties:` 値の WikiLink 化」）。同じ分類の property の一方だけが補強されている非対称（例: `author` は補強されているが `publisher` はされていない）は、`check_schema_org_type.py --show-range` の RANGE 分類と「型テンプレートが property を名指しで補強しているか」を突き合わせれば機械的に見つかる。本スクリプトはこの照合を自動化する。

「補強」の定義は 2 つの形である: (1) `wikicommit.granularity` のプローズに、property 名を単語境界付きで言及し**かつリンク化を指し示す**（property 名を取り除いた残りに `[[` または `link` を含む。大文字小文字を区別しないため `WikiLink`・`linked` も該当する。property 名自体を手掛かりに数えないのは、`originalMediaLink` のように名前に `link` を含む property が自分の名前だけで条件を満たしてしまうのを防ぐため）箇条書きがある、または (2) `properties:` のプレースホルダー値（文字列またはリストの要素）に `[[...]]` という WikiLink トークンが既に含まれている。いずれも持たない Entity-only/Mixed な property を `UNREINFORCED` として報告する。

**言及だけでは補強とみなさない**: 正規表現は文脈を見ないため、言及だけを条件にすると**その property を否定する散文でも補強と判定される**（例: 「`tool` と `supply` は物理的な手順向けで空になることが多い。書かずに置け」という箇条書きが `HowTo.tool` / `HowTo.supply` を報告から消す）。散文が property に言及する必要がある限り、言及のみの判定では避けられない。**それでも判定は肯定・否定を見分けられない**。「`tool` の値はリンクにするな」と書けば依然として補強と判定される（正規表現に文脈は解けない）。縮めたのは誤判定の範囲であって、種類ではない。取りこぼす側の劣化（リンク化を促す意図の箇条書きが `[[`・`link` のどちらも含まない言い回しで書かれていた場合、`UNREINFORCED` として報告される）は、非ブロッキングな気づきが1行増えるだけであり安全側に倒れている。

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
3. `properties:` が dict であることを確認し（そうでなければこのファイルはスキップする）、`wikicommit.granularity` から検査に使える箇条書き（文字列のもの）を集める。文字列でない箇条書き・リストでない `granularity` は WARNING を出した上で対象外にする（`granularity_strings()`。下記「コロンを含む `granularity` 箇条書き」。WARNING は `properties:` を持つファイルにのみ出る — この WARNING の役目は直後の `UNREINFORCED:` が誤検出であることを説明することであり、`properties:` が無ければ説明すべき所見自体が生まれない）
4. `properties:` の各キーについて、`check_schema_org_type.py --show-range` と同じ RANGE 分類ロジック（`_schemaorg_vocab.py` の `entity_range_candidates()`）でエンティティ型候補を取得する。語彙に存在しない、またはエンティティ型候補が空（DataType-only、または `rangeIncludes` 自体が未宣言）の場合はスキップする
5. 残ったキー（Entity-only/Mixed）について、上記の「補強」定義（`granularity` 言及または `properties:` 値中の `[[...]]` トークン）を満たすか確認する
6. 満たさない場合、`UNREINFORCED:` として報告する

**コロンを含む `granularity` 箇条書きは検査から外れる — 黙って外さない**: クォートされていない YAML リスト項目にトップレベルの `key: value` 形状が現れると、YAML はそれをスカラーではなく単一キーのマッピングとして読む。`is_reinforced()` はプローズを走査する以上、文字列でない箇条書きを扱えない。扱えないことが出力に現れないと、型テンプレートの著者が property 名をその箇条書きの中で補強していても `UNREINFORCED` の誤検出になり、しかも報告を見た人間がテンプレートを読むと補強は確かに書いてあるため、スクリプトの誤りではなく人間の見落としに見える。だから WARNING で外したことを述べる。

**箇条書きをマッピングから文字列に復元して検査することはしない**。コロンを含む箇条書きは `granularity` を読むあらゆる消費者にとっての落とし穴であり、直すべき場所は型スキーマファイル自身である。ここで復元すると、直すべき形そのものを隠してしまう。

**`.wikicommit/schema/` に置かれるファイルの出所は3系統あり、CI が守れるのは1つだけ**: 配布テンプレートは `tests/test_schema_template_boundary_rules.py` が「全 `granularity` 箇条書きが文字列としてパースされること」を強制する。一方、`wikicommit-generate` Pass 2b / `wikicommit-schema-propose` が実行時に書いた型ファイルと、人間が直接手書きした型ファイル（`provenance: manual`）はそのテストの射程外にある。そのため予防は**書く側**にも置き、`granularity` を書く4経路（`wikicommit-init` の型提案・`wikicommit-collect` の Type Proposal・`wikicommit-generate` Pass 2b・`wikicommit-schema-propose`）が承認時に読む `.wikicommit/schema-authoring.md` が「箇条書きは文字列としてパースされる形で書く（`Boundary — …`。`Boundary: …` は不可、`#` も不可）」を明記する。各 SKILL.md に 1 行ずつ残るのは `Boundary —` の一点のみで、空白を伴う `#` の危険は共有ファイル側にしかない — **4 経路の SKILL.md を grep してこの規律が消えたと読まないこと**。既にコロンで書かれた箇条書きは、この WARNING を見た人間が `.wikicommit/schema/` を直接編集するまで残る。

### 出力フォーマット

```
UNREINFORCED: Organization.foundingLocation (.wikicommit/schema/Organization.md) — range includes linkable entity type(s): Place. No granularity line points toward linking it, and no [[Type/slug]] placeholder in properties:.
SUMMARY: unreinforced=1
```

該当なしの場合:

```
SUMMARY: unreinforced=0
```

検査対象から外れた `granularity` 箇条書きがある場合（`UNREINFORCED:` の直前に出るため、誤検出であることがその場で読み取れる）:

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

この取りこぼしは他のどのチェックにも掛からない。`check_wanted_pages.py` は `[[Type/slug]]` 形式の WikiLink しか読まないため、プレーンテキストの名前は wanted page として計上すらされない（「WikiLink 構文が一度も使われていない言及は対象外」という同スクリプトの限界が、`properties:` の値についても同じように効く）。`check_orphans.py` は既に存在するページへの被リンクの話であって無関係。結果として、複数の話の主人公である人物が同一のプレーンテキストとして何度も独立に列挙されるだけで、ページを 1 つも持たないことが起こる。

本スクリプトが出す所見は `RECURRING` の 1 種類のみ — 同じ名前が 2 件以上の作品にプレーンテキストで現れ、どの言語にも `Person` ページが無い場合。ページを作る（または「この人物はプレーンテキストのままにする」と一度決める）ことを促す。作品をまたぐ再登場は、単一の作品からは得られない「この人物は 1 つの筋書きを超えて存在する」という証拠そのものである。

**既に `Person` ページがある名前は本スクリプトの担当ではない** — 書くべきページは無く、値を WikiLink にすればよいだけであり、要求される行動が正反対だからである。こちらは `check_unlinked_entity_mentions.py` が `character` に限らずエンティティ型を range に持つ全ての `properties:` キーについて報告する。本スクリプトもページの存在は読むが、それは昇格候補の一覧からその名前を外すためだけに使う。

**軸の限定**: 本スクリプトが扱えるのは作品をまたぐ再登場だけである。1 作品にしか登場しないが、その作品が丸ごとその人物についての話である主人公は 1 ページにしか現れないため、横断集計では原理的に検出できない — こちらは生成時に `Person.md` の `granularity` が下す判断であり、事後のチェックの担当ではない。

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
3. あわせて、`Person` 型のページについて `title` と `aliases` の各値を正規化したものから `Person/<slug>` への索引を作る（言語を問わない。slug は言語中立であるため、どの言語のページでもその名前に答えられる）。`aliases` も索引に含めるのは、`title` だけで突き合わせると「よりフォーマルな形でページ化されている」人物（`Person/ser-ciappelletto`・title `"Ser Ciappelletto"` に対して、作品側はプレーンテキストの `Ciappelletto`）が `RECURRING` として報告され、既にページがある人物について「ページを作れ」と促してしまうため — `check_wanted_pages.py` の `TYPE_MISMATCH` が防いでいるのと同じ種類の重複であり、しかも title が異なるため `check_orphans.py` の重複ページ判定にも掛からない
4. 名前の突き合わせは NFKC 正規化 + casefold + 連続空白の単一化で行う（`check_orphans.py` が重複ページ判定でタイトルに適用しているものと同じ正規化）
5. 作品の同一性は**ファイルパスではなく `<Type>/<slug>`** で数える。1 つの物語の it/en/ja 版は 1 件であり、そうしないと多言語 Wiki は登場人物全員を「再登場」として報告してしまう
6. `Person` ページがある名前は除外し、無く 2 件以上の作品に現れる名前を `RECURRING` として報告する

### 既知の限界

- **同名の別人を区別しない**。名前とページの突き合わせは正規化した `title`／`aliases` の一致で行うため、無関係な同名人物は 1 人として読まれる。警告のみの出力であり、`check_wanted_pages.py` が自身の限界について採っているのと同じ許容度とする
- **作品をまたがない主人公は検出しない**（上記）
- **既にページがある名前は検出しない**（上記。`check_unlinked_entity_mentions.py` の担当）
- **再登場の計数はプレーンテキストで書かれた作品しか数えない**。ページがまだ無い人物について、ある作品が既に `[[Person/slug]]` と書いている場合、その作品は閾値に算入されない（リンク 1 件 + プレーンテキスト 1 件では何も報告されない）。両者を突き合わせるにはプレーンテキストの名前から slug を導く必要があるが、slug の決定規則（英語識別子・種別に応じた英訳／原綴り／ローマ字）は逆算できるものではないため行わない。宙に浮いたリンク自体は `check_wanted_pages.py` の所見であり、`Person` ページが作られた時点でプレーンテキスト側は `check_unlinked_entity_mentions.py` が拾う

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

`check_wanted_pages.py` の鏡像。あちらが「リンクはあるが実体がない」を検出するのに対し、本スクリプトは**「実体はあるがリンクされていない」**を検出する。

Pass 3 は `properties:` の値を WikiLink にするかどうかを Schema.org の RANGE 分類のみで決め、その指示は「参照先ページが未作成であることを理由に WikiLink を諦めるな」と**名指しで**述べている。それでも、同じ property の値リストのうち、先にページが書かれていた値だけが WikiLink 化され、後からページが作られた値がプレーンテキストのまま残ることがある — 分かれ目は取り込み順序だけである。

しかも自然には回復しない。`action: update` はそのページ自身を対象とするソースが再 ingest されたときにしか起きないため、後から参照先のページを作った ingest には参照元のページを見直す理由が無い。他のチェックにも掛からない — `check_wikilinks.py` は書かれた WikiLink しか見ず、`check_orphans.py` は参照先ページが他ページから被リンクを持つ場合に取りこぼす。

対象は `properties:` の値に限り、本文の地の文は扱わない（`check_wanted_pages.py` と同じ限界）。`properties:` の値は定義上「短く構造化された値」であり、これが既存ページとの機械的な突き合わせを成立させている。

### 使用場面

- `wikicommit-status` Skill：Step 8

### コマンド

```
python .wikicommit/scripts/check_unlinked_entity_mentions.py
```

引数なし。常に `.wikicommit/entity/` 配下の全 `.md`（`assets/` と `index.md` を除く）を対象とする。

### 処理フロー

1. `_schemaorg_vocab.py` の `load_or_build_index()` で Schema.org 語彙を読む。取得できない場合は WARNING を 1 行出して `SUMMARY: unlinked=0` で終了する（`check_property_wikilink_reinforcement.py`・`validate_frontmatter.py` の `properties:` 検証と同じ非ブロッキングな劣化）
2. 全ページの frontmatter を読み（`status: removed` は対象外）、正規化した `title`・`aliases` の各値・`slug` から `(型, slug)` への索引を作る。`slug` も索引に含めるのは、英語で書かれた Wiki では値と slug が一致しうるため（他言語では値は Wiki の言語で書かれ、slug は言語中立な英語識別子であるため一致しないのが普通）
3. 各ページの `properties:` の各キーについて `entity_range_candidates()`（`check_schema_org_type.py --show-range` と同じロジック）を引き、エンティティ型候補が空なら飛ばす（DataType のみ ＝ プレーンテキストが正しい形）。語彙に無いキーも飛ばす（`validate_frontmatter.py` の関心事）
4. 値のうち WikiLink を含まないプレーン文字列を正規化して索引を引く
5. **型も一致することを要求する** — 見つかったページの型が、その property のエンティティ型候補そのものか、その下位型（`ancestors()` で判定）でなければ一致とみなさない。`genre: "Comedy"` が `Person/comedy` で答えられてしまうのを防ぐ
6. 自ページ自身への一致は除外し、残りを `UNLINKED` として報告する

### 修正の経路

`/wikicommit-fix <page-path> "<instruction>"` で参照元ページを個別に直す。**機械的な一括置換のスクリプトは用意しない**: 値がページのタイトルと一致することは根拠であって証明ではなく（同名の別主体がありうる）、`properties:` への自動書き込みをヘルスチェックの責務に含めるべきでもない。

### 既知の限界

- **同名の別主体を区別しない**。突き合わせは正規化した `title`／`aliases`／`slug` の一致で行うため、無関係な同名の主体は 1 つとして読まれる。型の一致も要求するため精度は上がるが、なくなりはしない。警告のみの出力であり、`check_wanted_pages.py` が自身の限界について採っているのと同じ許容度とする
- **カスタム型は参照先になれない**。`schema:custom/` プレフィックスを持つ型は Schema.org 語彙に存在しないため、その型が property の range を満たすかを判定する手段が無い。一方、**参照元としては通常どおり走査する** — range 分類は property 名だけで決まり参照元ページ自身の型を一切参照しないため、`custom/Tale` の `character` は `ShortStory` の `character` と全く同じに判定される（`validate_frontmatter.py`・`check_property_wikilink_reinforcement.py` はカスタム型を丸ごとスキップするが、あちらが検証するのはキーが**その型の** `domainIncludes` に属するかであり、まさにその部分がカスタム型では答えられない。本スクリプトはそこを見ない）。カスタム型の `properties:` キーは機械検証を受けないため独自の名前がありうるが、語彙に無いキーは他の未知の property と同じく単に飛ばされる
- **本文の地の文は対象外**（上記）

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

`check_schema_coverage.py` の対。あちらが「使われている `type:` にスキーマファイルが無い」を検出するのに対し、本スクリプトは**「スキーマファイルが在るのにページが無い」**を検出する。

`Park.md`・`Museum.md` をインストールした Wiki でも、公園や博物館が素の `Place` として生成されることがある — 型ファイルを追加したのと同じバッチでも起こる。その間 `check_schema_coverage.py` は 0 件を報告し続ける。`Place` にはスキーマファイルがあるためである。

原因は手違いではなく構造にある。Schema.org 上 `Park`・`Museum` は `Place` の子孫型なので、公園を `Place` として書くことは**誤りではなく、粒度が粗いだけ**である。そして祖先型は常に利用可能で、常により馴染みがあり、常に技術的に正しい。同じ力学が、型を**提案する**段（Pass 2b）でも、インストール済みの型を**選ぶ**段（Pass 2c）でも働く。

2 種類の所見を出す。強度が意図的に異なる。

| 所見 | 条件 | 読み方 |
|---|---|---|
| `UNUSED` | 型ファイルがあるのにページが 0 件 | 型の判断自体が誤っていたか、生成がその型に手を伸ばしていないか。`provenance: default` の型は対象外 — Wiki の主題に関わらず一律配布されるため、0 件であること自体に情報が無い。`provenance` が**無い**ファイルは `provenance` を書くようになる前に作られたことを意味するため、`config.yml` の `schema.base_types` が代わりの判断材料になる（そうしないと、それ以前に初期化された Wiki は配布された基本型を丸ごと報告してしまう） |
| `ANCESTOR_FALLBACK` | ある型にページがあり、その子孫型もインストール済み | **示唆であって断定ではない**。`Park.md` を持つ Wiki にも公園でない `Place` ページは当然ある。「見る価値がある」程度に読む |

いずれもブロッキングではない。どの型がその主題に合うかは判断であり、本スクリプトにそれを下す手段は無い — 粗くなっているかもしれない場所を指すことしかできない。

**既存ページの型の再分類は本スクリプトのスコープ外**である。型変更はディレクトリ移動と、そのページを指す全 WikiLink の Type セグメント書き換えを伴う（`docs/DesignDoc-data.md` §5.5）。本チェックの目的は、次のバッチが正しい粒度で生成されるよう早期にパターンを捕まえることにある。

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

`tags` は「複数ページを横断して同じ概念で括る」ためのフィールドである（`docs/DesignDoc-data.md` §4.1）。ページ自身の `title` と同じタグはそのページ自身としか括れず、`type` と同じタグは `type:` フィールドが既に述べていることの繰り返しになる。どちらも生成時の指示で禁じているが、指示だけでは再発する（例: `Place/minuma-tanbo.md` の `tags: [見沼田んぼ, ...]`）。

生成時の指示だけに依存し**検出手段が無い**ルールは drift する。本スクリプトはその検出手段である（`check_property_wikilink_reinforcement.py` と同じ位置づけ）。

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

---

## check_schema_files.py

### 目的

`.wikicommit/schema/` の型ファイル自体が動く形で書かれているかを検証する。

`.wikicommit/schema/` に置かれるファイルの出所は 3 系統あり、**CI が守れるのは 1 つだけである**:

| 出所 | `provenance` | CI の検証 |
|---|---|---|
| 配布テンプレート | `default` | ⭕ `tests/test_schema_template_*.py` |
| 実行時に Skill が書いた型 | `init-theme` / `collect` / `generate-interactive` / `generate-auto` / `schema-propose` | ❌ |
| 人間が直接手書きした型 | `manual` | ❌ |

しかも**書かれた後どの Skill も編集できない**（型を書くことを許す narrow exception は「追加のみ可」）。壊れた形で書かれたものは、人間が `.wikicommit/schema/` を直接開くまで残る。

検査に使う道具は既存のものを使う — property の検証は `check_schema_org_type.py`、祖先の解決は `_schemaorg_vocab.py`、`provenance` を読む関数は `check_installed_type_usage.py` の `provenance_of()` にある。本スクリプトはそれらをファイルに対して走らせる主体である。

### 使用場面

- `wikicommit-status` Skill：Step 5（`check_property_wikilink_reinforcement.py` と同じステップ。走査対象のディレクトリが同じであり、新しい番号を挿むと以降 13 ステップの参照を全部書き換えることになる）

**`check_property_wikilink_reinforcement.py` と統合はしない**。走査は 2 回になるが、問う内容が逆である — あちらの所見は「テンプレートがもっと述べるべきか」という**望ましさ**であり、`description` のように常に出ることを承知で残している行を持つ。こちらは「そもそも動く形で書かれているか」という**壊れている**の報告で、1 件でも出れば見る価値がある。1 つの `SUMMARY:` に混ぜると、後者が前者の既知のノイズに埋もれる。

### コマンド

```
python .wikicommit/scripts/check_schema_files.py
```

引数なし。`.wikicommit/schema/**/*.md` 全体を対象とする。**読み取り専用**で、`wikicommit-merge` の品質ゲートには入れない（下記）。

### 所見の種類

| 所見 | 条件 |
|---|---|
| `BAD_PROPERTY` | `properties:` のキーが Schema.org 語彙に実在しない、またはその型（祖先型を含む）の `domainIncludes` に属さない。**ページ側の `properties:` には `validate_frontmatter.py` が同じ検証をしている**が、そのページが生成された元のテンプレートに対してはこれが唯一の検証である |
| `MAPPING_BULLET` | `granularity` の箇条書きが、クォートされていない `": "` によってマッピングに化けている。文字列で絞り込む全消費者がその箇条書きを飛ばす |
| `TRUNCATED_BULLET` | `granularity` の生の行にクォートされていない、空白を伴う `#` があり、YAML のコメントとして行の残りが落ちている。**これは他の何も気づけない唯一の形である** — 値は文字列のままなので一見正常で、欠けた半分は単に無い |
| `NO_BOUNDARY` | `Boundary` で始まる箇条書きが 1 本も無い（`granularity` が空の場合は対象外 — 規則が 0 本であることと、規則があるのに境界が無いことは別である）。**マッピングに化けた箇条書きはそのキーを見る** — `Boundary with X: ...` のような形に `MAPPING_BULLET` に加えて「`Boundary` で始まる箇条書きが無い」と述べれば、そこに在るものを無いと言うことになる |
| `BAD_PROVENANCE` | `provenance` が 7 値のいずれでもない。**欠如は報告しない**（下記） |
| `NO_BASE` | `wikicommit.base` が無い（`default.md` は対象外 — 型ではなくフォールバックであり、設計上持たない） |
| `NO_WIKICOMMIT_BLOCK` | `wikicommit:` ブロックそのものが無い（上記のフィールドはいずれもその中にあるため、探す場所が無い） |
| `TYPE_PATH_MISMATCH` | `type:` がファイルパスから導かれる型名と食い違う。型を決めるのはパスの導出だけ（§5.1）なので、食い違えばそのファイルは**何も定義していない**。ページ側には `validate_frontmatter.py` の同じ検証がある |
| `UNKNOWN_TYPE` | `type:` とパスが一致しており、かつその型名が Schema.org 語彙に実在しない（多くは綴りの誤りで、そのファイルはどの型にも解決されない）。**一致している場合にのみ報告する** — 食い違っている場合は `TYPE_PATH_MISMATCH` が直すべき 1 点を既に述べており、そこでパス由来の型名を挙げると、そのファイルが書いていない文字列を `type:` の値として引用することになる。`properties:` の有無に依存しない — 型名の誤りはそのファイルが何も定義しないことの原因そのものであり、突き合わせる property が無くても同じだけ沈黙する |
| `NO_RATIONALE` | カスタム型に `wikicommit.rationale` が無い。語彙の外にある型では、その散文が「なぜこの型が存在するか」の唯一の恒久的な記録である |
| `NO_FRONTMATTER` / `UNPARSEABLE` | frontmatter が無い、またはパースできない。**1 件にまとめて早期 return する** — そうしないと他の全検査が同じ 1 つの原因から発火する。共有パーサは「frontmatter が無いこと」を非エラーとして扱う（大半の `.md` は持たないため）が、型ファイルはその例外で、frontmatter がその定義そのものである |

### 報告しないもの

- **`provenance` の欠如**。不在は「`provenance` を書くようになる前に作られた」ことを意味するため、報告すれば古いリポジトリ全件が正しい状態について点灯する
- **`default.md`** の `base` と `type`（上記）
- **カスタム型の property と `base` の突き合わせ**。定義上語彙の外にあり、照合先が無い。語彙を要さない検査のみ走る — 値が解決するかではなくフィールドが在るかを問う `NO_BASE` / `NO_RATIONALE` は引き続き働く
- **`granularity` の散文の妥当性**。規則が**正しいか**はここでは判定できない。見るのは形だけである

### `in_distributed_templates` — 実データで決めた所見の範囲

`SUMMARY:` は `files` / `findings` に加えて `in_distributed_templates`（`provenance: default` のファイルに出た件数）を出し、非ゼロなら `NOTE:` 行を添える。**`provenance: default` のファイルに出た所見は「誰かが書き間違えた」ではなく「このリポジトリが古いテンプレートの写しを持っている」を意味する** — これらの規約（`Boundary` の箇条書き・YAML 文字列の規律）のいくつかは、テンプレートが最初に配られた後で足されたものである。対処は上流の差分を取り込むことであり、それは `check_distribution_freshness.py` が同じファイルについて報告する。テンプレートを手で直すと次の同期で元に戻る。

**`provenance: default` を丸ごと除外しない**。古い写しだけが壊れたまま残る実害（例: 上流では修正済みの `TRUNCATED_BULLET` で、規則の後半が黙って消えている）が見えなくなる。代わりに件数を分けて、どちらが自分の書いたものかを読み手が 1 行で判別できるようにする（常時点灯すると読まれなくなる問題への対処を、所見を隠すのではなく数を読めるようにすることで行う）。

### 既知の限界

- **`provenance` を持たないファイルは `default` 側に数えられない**。値が無ければ古い配布テンプレートか古い実行時ファイルかを区別する手段が無いため、リポジトリ側として数える
- **人間が `default` のファイルを手編集して壊した場合も `in_distributed_templates` に数えられる**（規約どおり `provenance` は編集で変えないため）。件数の分け方はテンプレートの版の古さを代理指標にしており、手編集はその代理が外れる唯一のケースである
- **`granularity` が YAML のフロースタイル（`granularity: [a, b]`）で書かれている場合、`TRUNCATED_BULLET` は何も見ない**。生の行走査はハイフンと空白で始まる行を探すため。パース済みの値を見る他の検査は通常どおり働く
- **散文の妥当性は判定しない**（上記）

### 出力フォーマット

```
NO_BOUNDARY: .wikicommit/schema/Park.md, provenance: collect — no granularity bullet begins with `Boundary` — ...
TRUNCATED_BULLET: .wikicommit/schema/DefinedTerm.md, provenance: default — granularity bullet 3 carries an unquoted ` #`, which opens a YAML comment and drops the rest of the line. ...
SUMMARY: files=14, findings=15, in_distributed_templates=13
NOTE: findings on a `provenance: default` file mean this repository holds an older copy of a distributed template, ...
```

`.wikicommit/schema/` が無い、または型ファイルが 1 件も無い場合は `SUMMARY: files=0, findings=0` と `NOTE:` を出す。Schema.org 語彙が引けない場合は `WARNING:` を 1 行出して**property の検査だけを飛ばす**（`check_property_wikilink_reinforcement.py` と同じ非ブロッキングな劣化）。語彙を要さない検査は通常どおり走る。

### 終了コード

- 常に `0`（報告のみ、ブロッキングしない）

**`wikicommit-merge` の品質ゲートに入れない**。壊れた schema ファイルを 1 つ持っているだけで既存リポジトリがマージ不能になる。`validate_frontmatter.py` の `type:` 検証が ERROR なのは、そこがページ側であり `wikicommit-generate` がその場で直せるからであり、こちらの対処はどの Skill も触れないファイルを人間が開くことである。

---

## record_relation.py / check_name_collisions.py

`/wikicommit-relate` が使う 2 本。設計判断の全体（関係の語彙・置き場所・形式）は `docs/DesignDoc-data.md` §4.5.2 にある。

### record_relation.py

```
python .wikicommit/scripts/record_relation.py --relation same|broader|related|distinct|series \
    --page <Type/slug> [--page ...] [--broader <Type/slug>] [--note <text> | --note-file <path>] [--today YYYY-MM-DD]
```

`.wikicommit/relations.yml`（トップレベルの YAML リスト）の末尾に 1 項目を**テキストとして追記する**。既存の内容は読んで検証するだけで書き直さない（人のコメント・手直しを保つため）。無ければ説明のコメント付きで作る。

検証（いずれかに当たれば何も書かず exit 1）: 各ページ（`--broader` を含む）が `<Type>/<slug>` の形で `.wikicommit/entity/` のいずれかの言語に実在すること・同じページの重複なし・`same` / `related` / `distinct` / `series` は 2 ページ以上で `--broader` を持たない（`series` の `--page` は系列の順〈古い順〉に渡す。順序は検証しない）・`broader` は `--broader` を持ち、それが `--page` に含まれず、`--page` が 1 つ以上・既存ファイルが YAML のリスト（または空）としてパースできること。

出力 `RECORDED: .wikicommit/relations.yml (relation=<r>, pages=<N>, items in file=<N>)`。拒否時は `ERROR:`。

### check_name_collisions.py

```
python .wikicommit/scripts/check_name_collisions.py
```

言語ディレクトリごとに、`index.md` と `status: removed` を除く全 entity ページのタイトルと別名を `normalize_name()` で正規化し、2 ページ以上が答える名前を `COLLISION:` として出す。**`.wikicommit/relations.yml` の最初の読み手である** — どの関係であれ同じ項目に挙がったページの組（`pages` と `broader`）は外し、その数を `judged_pairs_skipped` に数える。同じ型のタイトル同士の一致は `check_orphans.py` の `DUPLICATE:` の担当として外す。関係ファイルが読めない・リストでない場合は stderr に `WARNING:` を出して判断なしとして扱い（衝突は全部出る — 誤る向きをそちらに倒す）、`pages` を持たない項目は `WARNING:` を出して飛ばす。

```
COLLISION: "Function calling" (en) — DefinedTerm/function-calling (title), DefinedTerm/tool-use-design-pattern (alias)
SUMMARY: collisions=1, judged_pairs_skipped=0, relations=0
```

終了コード: 常に `0`（報告のみ。`/wikicommit-merge` の品質ゲートには入れない — 入れると既存の Wiki がマージ不能になる）。

---

## check_groups.py

### 目的

`.wikicommit/groups/<Type>.yml`（`docs/DesignDoc-data.md` §4.5.3）を読み、未分類のページ・実在しない slug・読めないファイルを報告する。読み込みと検証は `_groups.py` にあり、`rebuild_index.py` と `convert_wikilinks.py` も同じものを import する。

### コマンド

```
python .wikicommit/scripts/check_groups.py
python .wikicommit/scripts/check_groups.py --type <Type> [--limit N]
```

- **引数なし**（`/wikicommit-status` Step 10）: グループファイルごとに `TYPE:` を 1 行、読めないファイルには `ERROR:` を出す。**グループファイルを持たない型は報告しない** — 全型が常に点灯する行は読まれなくなる
- **`--type`**（`/wikicommit-organize`）: `GROUP:`（キー・件数・表示名・criterion）、`STALE_MEMBER:`、`UNCLASSIFIED:`（`build_survey_view.py --pages` にそのまま渡せるパス。`--limit` 件まで、超えた分は `TRUNCATED:`）。ファイルが無ければ `NOTE:` を出し、全ページを未分類として列挙する

ページは slug 単位で数える（グループファイルは全言語に効くため、翻訳はまとめて 1 件）。列挙するパスは `primary_lang` の原文を優先する。`index.md` と `status: removed` は数えない。**閾値は置かない。**

### 検証

`_groups.py` の `parse_group_file()` が次を `ERROR:` にし、1 つでもあればファイル全体を使わない（半分だけ適用しない）: YAML として読めない・マッピングでない、トップレベル・グループ内の未知のキー（`page:` のような書き損じを拾う）、キーが英小文字・数字・ハイフン以外、`label` / `unclassified_label` が「言語 → 空でない文字列」でない、`pages` が文字列のリストでない、**同じ slug が 2 つのグループにある**。

### 出力フォーマット

```
TYPE: DefinedTerm groups=3, grouped=3, unclassified=1, stale=1
ERROR: .wikicommit/groups/Place.yml: page `minuma` is in both `nature` and `history` — a page belongs to one group
SUMMARY: types=1, unclassified=1, stale=1, errors=1
```

```
GROUP: practice | pages=2 | label=en: Practices, ja: 実践・手法 | criterion=Something the reader does
STALE_MEMBER: deleted-page (group gone) — no live DefinedTerm page has this slug
UNCLASSIFIED: .wikicommit/entity/en/DefinedTerm/loose-one.md
SUMMARY: type=DefinedTerm, pages=4, unclassified=1, stale=1, errors=0
```

### 終了コード

- 常に `0`（報告であり品質ゲートではない。不正なファイルは全読み手が「グループ無し」として扱うので、直るまでの間も何も壊れない）

---

## merge_pages.py / rewrite_merged_links.py

`/wikicommit-generate --regenerate <残すページ> --merge <吸収するページ> [...]` が使う 2 本。設計判断の全体は `docs/DesignDoc-data.md` §4.5.2 の「統合」の節にある。本文の書き直し（Pass 3 / 4）はエージェントが行い、統合に関わる**決定論的な部分**をこの 2 本が持つ。

### merge_pages.py

```
python .wikicommit/scripts/merge_pages.py plan   --into <page> --absorb <page> [--absorb ...]
python .wikicommit/scripts/merge_pages.py record --into <page> --absorb <page> [--absorb ...] [--today YYYY-MM-DD]
python .wikicommit/scripts/merge_pages.py check  --into <page> --absorb <page> [--absorb ...]
```

ページはリポジトリルートからのパス（`primary_lang` の原文）で渡す。

- **`plan`** — 統合してよいかを確かめ、関わるものを出す。拒否（exit 1・何も書かない）するのは、ページが無い・`status: removed`・`primary_lang` 以外・翻訳・合成ページ・view ページ、`relations.yml` の `same` 項目が残すページと吸収する各ページを組で挙げていない、`type: manual` のソースがある（再取得できない — `--regenerate` が同じ理由でそのページを飛ばす）、同じソースが 2 つのハッシュで記録されている（一方のページが古い版から書かれている）、のいずれか

  ```
  KEEP: .wikicommit/entity/en/DefinedTerm/tool-use.md
  ABSORB: .wikicommit/entity/en/DefinedTerm/function-calling.md
  TRANSLATION: .wikicommit/entity/ja/DefinedTerm/function-calling.md (of .wikicommit/entity/en/DefinedTerm/function-calling.md)
  SOURCE: url https://a.example/x sha256:aa
  ALIAS: Function calling
  SUMMARY: absorb=1, translations=1, sources=2, aliases=1
  ```

  `SOURCE:` は全ページのソースの和集合（`type` と `url` / `path` で同一とみなす）。`ALIAS:` は**統合由来の別名** — 吸収するページの title と aliases、続けてその翻訳の title。残すページの title と同じものを除き、`normalize_name()` で重複を除く。Pass 4 はこれを「今回足した別名」から除く
- **`record`** — `plan` と同じ検証の後、`relations.yml` に統合の項目を追記する。追記は `record_relation.py` の `append_record()` を import して行う（ファイルの書き方の規則を 1 か所に保つ）

  ```yaml
  - relation: same
    pages: [DefinedTerm/tool-use, DefinedTerm/function-calling]
    merged_into: DefinedTerm/tool-use
    merged_aliases: [Function calling, Function call, 関数呼び出し]
    merged_at: '2026-10-02'
  ```

  吸収するページを取り下げる**前に**実行する（`plan` は取り下げ済みのページを拒否する）
- **`check`** — 統合が最後まで行われたかを確かめる。統合の項目がある・残すページの `aliases` が `merged_aliases` を全部持つ・吸収した各ページとその翻訳が `status: removed` かつ `merged_into` が残すページ・どの live ページも吸収したページへリンクしていない。足りないものを 1 行ずつ出して exit 1、揃っていれば `TOUCHED:` 行（取り下げたページと `relations.yml`）と `OK:` を出す。ドライバーの `merge-absorb` 工程の完了確認（`workflow_checks.py check-merge`）がこれを呼ぶ

### rewrite_merged_links.py

```
python .wikicommit/scripts/rewrite_merged_links.py [--dry-run]
```

対応表はディスクから作る — `status: removed` かつ `merged_into` を持つページ 1 枚ごとに `<その Type/slug> → <merged_into の Type/slug>`。連鎖（A → B → C）は最後までたどる。次の 3 つは書き換えず stderr に `WARNING:` を出す: その Type/slug がどこかの言語でまだ live（リンクがそこで解決する）、取り下げられた版が別々の先を指す、たどると循環する。

entity と view の全 live ページ（`index.md` を除く — `rebuild_index.py` が作り直す）について、`WIKILINK_RE` に当たる `[[Type/old]]` を `[[Type/new]]` に置き換える。frontmatter も対象（`properties:` の値の WikiLink）。リンク以外は 1 文字も変えず、`review_status` も変えない。

```
REWRITTEN: .wikicommit/entity/en/Person/x.md (2 link(s))
SUMMARY: merged=1, pages=1, links=2
```

**公開時に張り替えない理由**: `check_wikilinks.py` は `status: removed` のページへのリンクをブロックする（削除は警告・removed へのリンクは阻止という非対称）。公開時に張り替えると、ディスク上の removed ページへのリンクを許す例外をそこに作ることになる。

終了コード: 常に `0`。

---

## rename_page.py

`/wikicommit-relate` が `series` を記録する前に、各版の名前を同じ規則で修飾する。設計判断は `docs/DesignDoc-data.md` §4.5.2 の「系列と改名」の節にある。

```
python .wikicommit/scripts/rename_page.py plan  --page <page> --year YYYY [--base-title LANG=NAME ...]
python .wikicommit/scripts/rename_page.py apply --page <page> --year YYYY [--base-title LANG=NAME ...] [--today YYYY-MM-DD]
```

ページはリポジトリルートからのパス（`primary_lang` の原文）で渡す。修飾は slug の末尾の `-<年>` と、title の末尾の `（<年>）`（`ja` / `zh`）または 半角スペースと `(<年>)`（他の言語）。slug が既に `-<年>` で終わればそのまま、title が既に同じ年の修飾で終われば付け直さない（冪等）。`--base-title` は言語ごとに「年を足す前の名前」を与える（無い言語は現在の title）。翻訳（`translated_from` が原文を指す live なページ）も同じ規則で修飾する。

拒否（exit 1・何も書かない）: ページが無い・`status: removed`・`primary_lang` 以外・翻訳・合成ページ・view ページ、`--year` が 4 桁でない、新しい slug のファイルがどこかの言語に既にある、`relations.yml` に追記できない。

- **`plan`** — 何も書かずに変更を出す

  ```
  RENAME: .wikicommit/entity/ja/CreativeWork/ilo-report-v.md -> .wikicommit/entity/ja/CreativeWork/ilo-report-v-2025.md
  TITLE: ja "仕事の未来報告書" -> "仕事の未来報告書（2025）"
  SUMMARY: pages=2, slug_changed=yes
  ```

  変更が無ければ `UNCHANGED:` を出す
- **`apply`** — slug が変わらなければ、各言語のページの title を書き換えるだけ。slug が変わるときは統合の部品を使う: `relations.yml` に `relation: same` ＋ `merged_into` ＋ `renamed_at` の項目を追記（`record_relation.append_record()`）→ 各言語で新しい slug のページを書く（翻訳は `translated_from` を新しい原文へ）→ 古いページに `status: removed` / `removed_at` / `removed_reason: merged` / `merged_into: <新しいパス>` → `rewrite_merged_links.py` → ソース管理ファイルの `generated_pages` の古いパスの行を新しいパスに（その行だけ）→ 触れた型ディレクトリの `index.md` を作り直す。追加で出す行は `WROTE:` / `REMOVED:` / `REWRITTEN:` / `SOURCE_FILE:`、`.wikicommit/groups/<Type>.yml` が古い slug を挙げていれば `GROUPS:`（書き換えない）

title を書き換えたページは `review_status: pending` にし `reviewed_by` を消す（翻訳も同じ）。レビュー記録は移さない。`relations.yml` の項目は統合の項目と同じ形なので、`check_review_coverage.py` はリンクを書き換えたページを `STALE_REVIEW:` に数えない。

終了コード: `0` = 完了（または変更なし）、`1` = 拒否。
