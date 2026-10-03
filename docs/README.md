# 設計ドキュメントについて

WikiCommit の設計記録です。読む前に 4 点と、作業別の索引（§5）。

## 1. 整備された仕様書ではなく、開発中の設計記録です

日本語で書かれた、開発しながらの判断の記録です。「なぜそうなっているか」「何を検討して何を採らなかったか」を残すことを目的にしており、外部向けに整えた仕様書ではありません。実装が先に進んで記述が追いついていない箇所がありえます。**実装と食い違う場合は実装が正しい**と考えてください。

各ドキュメントの役割は次のとおりです。「参照頻度」は WikiCommit 自体を開発するときにどれだけ読むかの目安で、読む順序を決める手がかりになります。9 件とも公開ツリーに含まれています（`history/` も含む。§4）。

| ファイル | 内容 | 参照頻度 |
|---|---|---|
| [DesignDoc-architecture.md](DesignDoc-architecture.md) | §0 目的と位置づけ、§1 設計原則、§2 全体アーキテクチャ、§13 主要な設計決定、§15 既存実践との対応 | 低（方針確認時のみ） |
| [DesignDoc-data.md](DesignDoc-data.md) | §3 リポジトリ構造、§4 データ設計、§5 スキーマ層 | 高（全 Skill 実装で参照） |
| [DesignDoc-pipeline.md](DesignDoc-pipeline.md) | §6 パイプライン実装、§7 品質ゲート概要 | 最高（各 Skill の処理フロー参照） |
| [DesignDoc-skills.md](DesignDoc-skills.md) | §11 Skills 設計（MVP） | 高（Phase 1 の中心） |
| [DesignDoc-publish.md](DesignDoc-publish.md) | §8 公開・配信層、§9 検索エンジン、§10 MCP サーバー | 低（§8 は Phase 2、§9 は Phase 3 以降、§10 は Phase 5 以降・ホスト型のみ） |
| [DesignDoc-phases.md](DesignDoc-phases.md) | §12 技術スタック、§14 フェーズ別スコープ（Phase 1-3） | 中（判断基準として参照） |
| [DesignDoc-CISpec.md](DesignDoc-CISpec.md) | CI ワークフロー詳細仕様（§7 の詳細版） | 中（CI 実装時） |
| [DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) | Python スクリプト詳細仕様（§11.5 の詳細版） | 中（スクリプト実装時） |
| [DesignDoc-TestSpec.md](DesignDoc-TestSpec.md) | 開発時のテスト・Lint 基盤（CISpec とは別軸のランタイム外テスト） | 中（テスト基盤の変更時） |

## 2. `Issue #NNN` は非公開のトラッカーを指します

本文には `Issue #NNN` という参照が多数あります（公開している設計ドキュメント全体で **1,000 箇所を超え、ユニークな番号は 200 以上**あります。これは下限として書いています — 実装が進むほど増えるため、正確な数を書くとその時点で古くなります）。これらは **WikiCommit を開発している非公開リポジトリの Issue トラッカー**を指しており、公開リポジトリ `wikicommit/wikicommit` では解決できません（公開はファイルツリーのスナップショットとして行われるため、Issue は移りません）。

番号を書き換えずに残しているのは、それが「どの記述がどの検討に由来するか」を区別する識別子として機能しているためです。同じ Issue 番号が複数のドキュメントに現れていれば、それらは同じ判断の別の側面を述べています。**番号はリンクではなく、記述同士を束ねるラベルとして読んでください。**

## 3. 公開リポジトリに存在しないファイルへの参照があります

本文には `Issues/`・`dev/` 配下・`CLAUDE.md`・`CONTRIBUTING.md`・`.github/workflows/test.yml` へのパス参照があります。いずれも WikiCommit を開発している非公開リポジトリ側のファイルで、公開ツリーには含まれません。**いずれも「非公開の開発記録に基づく」と読んでください。**

パス表記のまま残しているのは、書き換えると何を根拠に判断したかが読み取れなくなるためです — §2 の Issue 番号と同じく、リンクではなくラベルとして読んでください。

パイロット（`dev/pilot-*.md`）への言及が多いのは、この設計の多くが実際に Wiki を作ってみて分かったことに由来するためです。ログ自体は公開していませんが、**そこで何が起きたかは、それを引用している側の記述に書いてあります** — 「`saitama` で 83 ページ中 49 ページが Wikipedia のみを出典としていた」のような具体的な観測は、参照元を読まなくても分かるように本文に書き出す方針を採っています。

## 4. 仕様の現在形と経緯を分けています（`history/`）

`DesignDoc-*.md` は 1 ファイルずつ、**いま何が仕様か**（何がどう動くか・守るべき不変条件・判断基準）を書く本文と、**経緯**（以前はこうだった・何を採らなかったか・実測の記録・どの Issue で決めたか）を書く [history/](history/) に分けています。分割済みのファイルは冒頭にその旨を書いており、経緯は `history/<同じファイル名>.md` の**同じ見出し**の下にあります。本文の節から同じ見出しを引けば経緯にたどり着きます。本文と history が食い違う場合は本文が正です（history は書かれた時点の記録であり、古くなった記述も直さずに残します）。

分けた理由は、実装・レビューのたびに読まれるのが「いま何が仕様か」なのに、経緯が本文の半分近くを占めて毎回一緒に読まれていたことです（2026-10-01 時点で開発セッションが毎回読み込む 4 本だけで約 1.43MB）。経緯そのものは同じ議論をやり直さずに済むために残しています。

| 決めたこと | 内容 | 理由 |
|---|---|---|
| 置き場 | `history/<DesignDoc 名>.md` に、節見出しを本文と揃えて移す | 移行が機械的で、本文の節との対応が保たれる。Issue ごとのファイル（ADR 形式）は数百ファイルになり、`Issues/` と `git log` に任せる形は実装時に決めたことが DesignDoc にしか書かれていないため失われる |
| 公開範囲 | `history/` も公開ツリーに含める | 隠すべき内容が無く、§2・§3 の読み方（Issue 番号とパスはラベルとして読む）がそのまま当てはまる |
| 本文に残すもの | 誤った代替案を封じる短い理由 | 消すとエージェントがもっともらしい別の手を取りうるため。経緯ではなく仕様の一部として扱う |
| 進め方 | pipeline → data → skills → publish → ScriptSpec の順に 1 ファイル 1 PR | 並列作業との衝突を避けるため。書き方の規則は `CONTRIBUTING.md` にあり、分割済みのファイルは `tools/check_designdoc_issue_refs.py` が本文の Issue 番号にラチェットを掛ける |
| `@` 読み込み | `CLAUDE.md` は DesignDoc を `@` で読み込まず、§5 の索引を置く。分割の完了を待たずに行った | 毎回全文を読ませる代わりに、作業に当たる節だけを読ませるため。見出しは分割で変わらないので、索引は分割の前後で同じ節を指す |

分割の記録:

| ファイル | 分割前 | 分割後の本文 | history |
|---|---|---|---|
| [DesignDoc-pipeline.md](DesignDoc-pipeline.md) | 219,709 B（`Issue #` 282 箇所） | 86,970 B（`Issue #` 3 箇所。うち約 30KB はレビュー追跡 Issue のテンプレート本文） | [history/DesignDoc-pipeline.md](history/DesignDoc-pipeline.md) |
| [DesignDoc-data.md](DesignDoc-data.md) | 408,071 B（`Issue #` 549 箇所） | 235,043 B（`Issue #` 0 箇所） | [history/DesignDoc-data.md](history/DesignDoc-data.md) |
| [DesignDoc-skills.md](DesignDoc-skills.md) | 387,410 B（`Issue #` 539 箇所） | 280,775 B（`Issue #` 0 箇所。大半は §11.2 の Skill 一覧と §11.5 の委譲表で、どちらも現在の仕様） | [history/DesignDoc-skills.md](history/DesignDoc-skills.md) |
| [DesignDoc-publish.md](DesignDoc-publish.md) | 290,616 B（`Issue #` 353 箇所） | 215,786 B（`Issue #` 0 箇所。§8.7.1 のグラフ・§8.8.1 の俯瞰ページはコールアウトの判断の多くが現在の仕様だったため、本文の節として書き直した） | [history/DesignDoc-publish.md](history/DesignDoc-publish.md) |
| [DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) | 390,606 B（`Issue #` 418 箇所） | 342,289 B（`Issue #` 0 箇所。大半はスクリプトごとの入出力・出力フォーマット・終了コードで、どれも現在の仕様。コールアウトの判断の多くも現在の規則だったため、本文の段落として書き直した） | [history/DesignDoc-ScriptSpec.md](history/DesignDoc-ScriptSpec.md) |

## 5. 作業別の索引 — どの作業でどの節を読むか

開発セッションは DesignDoc を自動では読み込みません（`CLAUDE.md` が読み込むのはこのファイルだけです）。作業を始める前に下の表で当たる節を引き、**その節だけ**を読んでください。1 つの作業に複数の行が当たることは普通にあります。

**引き方**: 見出しの行番号を出してから、その範囲だけを読みます。

```bash
grep -n '^#\{2,4\} ' docs/DesignDoc-data.md          # 節の一覧と行番号（コードブロック内の見本の見出しも混ざる）
sed -n '685,891p' docs/DesignDoc-data.md              # §4.3 だけを読む
```

ScriptSpec はスクリプトごとに `## <スクリプト名>` の節を持つので（2 本で 1 節を共有するもの〈`## record_relation.py / check_name_collisions.py` 等〉もある）、`grep -n '^## .*<名前>' docs/DesignDoc-ScriptSpec.md` で引けます。分割前のファイル（§4 の分割の記録に無いもの）は節の中に経緯のコールアウトを含むので、節が長ければ `>` で始まらない段落を先に読みます。経緯が要るとき（「なぜこうなっているか」「前に何を退けたか」を確かめるとき）だけ `history/` の同じ見出しを読みます。

| 作業 | 読む節 |
|---|---|
| 目的・課題・外部での位置づけを確かめる | architecture §0 |
| 設計原則・書き込み権限・信頼ラダーの位置づけを確かめる | architecture §1・§2.1・§13 |
| フェーズのスコープ・技術スタックを確かめる | phases §12・§14 |
| `/wikicommit-init` と配布物（何を配り、再 init で何が更新されるか） | data §3.1・§3.3（`_root_outputs.py` の `update` 列）、skills §11.1、ScriptSpec `check_distribution_freshness.py` |
| `config.yml` / `source-policy.md` / `entity-policy.md` | data §3.3・§3.4・§3.5、ScriptSpec `read_policy.py`・`match_index_only.py` |
| ページの frontmatter（共通フィールド・`properties:`・翻訳・合成・削除） | data §4.1・§4.2・§4.4・§4.5、ScriptSpec `validate_frontmatter.py` |
| ソース管理ファイル（`.wikicommit/source/`）と `status` の遷移 | data §4.3、ScriptSpec `reconcile_ingest_status.py`・`check_ingest_freshness.py` |
| view・ページ同士の関係・グループ分け | data §4.5.1・§4.5.2・§4.5.3、ScriptSpec `record_relation.py`・`check_name_collisions.py`・`check_groups.py`・`merge_pages.py`・`rename_page.py` |
| 型テンプレート（`.wikicommit/schema/`）と型の選択 | data §5.1〜§5.5、ScriptSpec `check_schema_org_type.py`・`check_schema_coverage.py`・`check_schema_files.py`・`check_installed_type_usage.py` |
| `/wikicommit-generate` の生成工程（Pass 1〜4・ガード・保留・`--regenerate`） | pipeline §6.1、skills §11.6、§11.5 の「非対話実行が人間の判断に当たったときの扱い」、ScriptSpec `check_extraction_quality.py`・`driver.py` |
| レビュー規律（Pass 4 / synthesize / translate の照合）とレビュー記録 | pipeline §7（チェック種別・機械レビューが評価しないもの）、data §4.6・§4.8、ScriptSpec `record_review.py`・`check_review_coverage.py`・`build_onehop_context.py` |
| `/wikicommit-merge`・品質ゲート・レビュー追跡 Issue のテンプレート | pipeline §6.2・§7、CISpec |
| `review_status` と人のレビュー（経路 A / B・Close 同期） | pipeline §6.3、ScriptSpec `reset_review_on_content_change.py` |
| 翻訳 | pipeline §6.4、data §4.2、ScriptSpec `check_translation_status.py` |
| 削除・取り下げ | pipeline §6.5、data §4.3（`retracted`）・§4.5、ScriptSpec `check_retracted_sources.py` |
| 検索・`/wikicommit-ask` | pipeline §6.6、publish §9、ScriptSpec `search_index.py` |
| コミットトレーラー | pipeline §6.7 |
| Skill を足す・SKILL.md を書き換える | skills §11.0〜§11.3・§11.7〜§11.9、TestSpec L5・L7・L9・L10・L14〜L16 |
| `.wikicommit/scripts/` のスクリプトを足す・変える | ScriptSpec 共通規則・スクリプト一覧・当該スクリプトの節、skills §11.5（置き場所の規則） |
| 実行記録・ドライバー | skills §11.0、ScriptSpec `driver.py`・`record_run.py`・`check_run_records.py` |
| 公開サイト（Quartz・プラグイン・バナー・俯瞰ページ） | publish §8 |
| テスト・lint・CI | TestSpec、CISpec |

この表は節の見出しを指しており、DesignDoc の分割（§4）で見出しは変わりません。節を足したり見出しを変えたりしたら、この表も直してください。

`@` 読み込みをやめた記録（2026-10-01）: 開発セッションが最初に読み込む量は、`CLAUDE.md` と DesignDoc 4 本（data・pipeline・skills・ScriptSpec）の 1,294,325 B から、`CLAUDE.md` とこのファイルの 38,437 B になりました（約 1/34）。§4 の分割より先に行ったのは、残りの分割作業のセッション自体がこの読み込みでコンテキストを圧迫していたためです。代わりに、必要な節を読み忘れる余地が生まれます — `implement-issue` / `review-and-merge` の手順が着手前にこの索引を引くよう求めているのはそのためです。
