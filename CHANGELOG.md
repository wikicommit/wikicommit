# Changelog

WikiCommit 自身（Skills と、それが展開するテンプレート一式）の変更履歴。

配布リポジトリ（`wikicommit/wikicommit`）は開発履歴を持ち込まない単一コミットの
積み重ねであり、`git log` は毎回同じ同期コミットしか示さない。したがってこのファイルが、
利用者が「前回インストールした版から何が変わったか」を知る唯一の手段になる。

あわせて、既存の Wiki ページを作り直すべきかを人間が判断するための情報源でもある。
ページの `generated_with` を `grep` すれば古い版で生成されたページは列挙できるが、
版の粒度は型より粗く、1 つの型テンプレートだけを変更して版を上げても全ページが
等しく「古い」と見える。この粗さを埋めるのがここの記述であり、両者はセットで機能する。
**型テンプレート（`.wikicommit/schema/<Type>.md`）やページ生成ルールを変更した版では、
「どの型を、どう変更したか」を必ず書くこと。**

版を上げるときは以下の 3 箇所をまとめて更新する（前二者の同期は
`tests/test_version_sync.py` が CI で強制する）:

1. `.claude/skills/wikicommit-init/scripts/templates/scripts/_version.py` の `VERSION`
2. `.claude-plugin/plugin.json` の `version`
3. このファイルの新しいエントリ

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)、
版番号は [Semantic Versioning](https://semver.org/lang/ja/) に従う。

## [Unreleased]

## [0.2.0] - 2026-09-01

### Added

- **合成ページを `.wikicommit/view/` へ分離し、Schema.org 型ではなく `kind` を持たせた**
  （Issue #675）。`/wikicommit-synthesize` の出力先が `.wikicommit/entity/<lang>/<Type>/<slug>.md`
  から `.wikicommit/view/<lang>/<slug>.md`（**Type セグメントを持たない**）に変わり、
  `content/<lang>/View/<slug>.md` として公開され、`[[View/<slug>]]` で参照できる。
  `.wikicommit/entity/` には性質の異なる 2 種類が同居していた — 外部ソース文書に照合できる
  一次知識（`sources` + hash）と、Wiki 自身のページにしか照合できない二次知識
  （`derived_from`）である。この違いはページの主題ではなく**何に照合できるか**にあり、
  同じ型ディレクトリに混ざっていると読者には区別が見えなかった。
  view ページは **`type:` を持たない** — Schema.org は事物をモデル化する語彙であり、
  「適用条件・前提・失敗モード・根拠の種類」を持つものは事物のクラスではなく**読み方**
  だからである。代わりに任意の `kind`（`practice` / `landscape` / `comparison` / `pattern` /
  `timeline` / `debate`）を持ち、これは「複数ページを見て何をするか」を表す。各 kind は
  `Boundary`（`landscape` は数を書かない、`comparison` は優劣を判定しない等）を持ち、
  Step 5.5 のレビューサブエージェントがこれを検査する — 検査が無ければ `kind` は誰も見ない
  ラベルになって drift するため。**`kind` はパスに出さない**（kind の選択ミスがファイルの
  位置を動かすと Issue #545 と同じ壊れ方になる）。副次的に、型選択ステップが丸ごと消えた
  ことで、同じ topic の 2 回の実行が別々のパスに解決される Issue #545 の問題自体が
  構造的に消えた。`_wikilink.py` に `VIEW_DIR` / `VIEW_TYPE_SEGMENT` / `VIEW_KINDS` /
  `parse_view_path()` / `collect_view_pages()` を追加し、各スクリプトが走査するかどうかを
  1 本ずつ決める（除外側は `tests/test_view_tree.py` が固定する — 除外の理由はツリーの
  中身に依存せず常に成り立つため、後の変更が両ツリー走査に差し替えてもエラーにはならず、
  対処できない所見が増えるだけになるため）。`rebuild_index.py` に言語別 index モード、
  `build_survey_view.py` に `--include-view` を追加。**既存の合成ページは自動移行しない**
  （`entity/` に残ったまま従来どおり動く）。詳細は `docs/DesignDoc-data.md` §4.5.1

- `/wikicommit-collect` を引数なしで実行すると、探索の前に **Wiki 全体を俯瞰して着眼点を選ぶ**
  ステップ（Step 3.5）が走るようになった（Issue #672）。`build_survey_view.py`（何があるか）・
  `check_wanted_pages.py` の `WANTED:`（Wiki 自身が書きたいと表明した穴）・`check_orphans.py` の
  `ORPHAN:`（出自ソース付きなので薄い領域が見える）の 3 本を読み、着眼点を最大 5 件提案する。
  人間が選んだものがその実行の research guidance になり（`theme` を置き換えない）、以降の探索が
  それを使う。`theme` は Wiki 全体の内容スコープであり 1 回の探索の方向づけとしては粗すぎるが、
  方向づけを書くには Wiki の現状を見る必要があり、その手段が collect の中に無かった — 結果、
  引数なし実行は毎回同じ広さで探し、既に厚い領域の候補を繰り返し拾っていた。`/wikicommit-synthesize`
  の俯瞰モード（Issue #586）と同型のステップを探索側に置いたもので、合流点（research guidance）は
  既存であり新しい概念は要らない。**自動探索にはしない** — 判断するのは人間で、俯瞰は材料を出す
  だけである。何も選ばれなければ何も探索せずに停止し、非対話実行でも停止する
  （`/wikicommit-collect <guidance>` と明示すれば俯瞰を飛ばせる）。俯瞰ステップは何も書かず、
  却下された着眼点はどこにも残らない

- 公開サイトのトップページに、**読者向けのサイト説明を言語ごとに 1 本ずつ**置けるようになった
  （Issue #671）。`config.yml` にトップレベルの `site_description`（言語コード → 1〜3 文の
  文字列）を書くと、`convert_wikilinks.py` の `load_site_description()` がこれを読み、
  `generate_root_index()` が言語選択リストの各行にその言語の説明を添える
  （`- [ja](./ja/) — ...`）。言語が 1 つだけの Wiki では「Wiki トップ」リンクの直下に 1 行。
  Issue #670 が取り除いた `theme` の表示に代わるものだが、**`theme` とは宛先が違う**
  （あちらは LLM に内容スコープを伝える 1 本の文字列、こちらは読者に読ませる文）ため、
  2 つを同期させる規約は置かない — 片方から他方を導出すると Issue #564 が解いた混在に戻る。
  フロントマター経由でバナーに描かせず**本文に書く**のは、値が言語ごとのマッピングで単一
  文字列に収まらないことと、説明を各言語のリンク直下に置けばキャプション自体が不要になり
  バナー i18n の 2 ロケール制約に引っかからないことによる。対象言語は実ページを持つ言語のみ
  （`existing_lang_targets()` の既存の安全弁をそのまま踏襲。Issue #190）。**人間が書く**
  フィールドで、`/wikicommit-init` に対話プロンプトは増やさず、テンプレートには
  コメントアウトした記入例のみを置く（キー自体は配らない。Issue #553）。既存リポジトリへの
  遡及付与は行わず、フィールドが無ければ従来どおりの出力になる

- `check_self_referential_tags.py` を追加し、`/wikicommit-status` の Step 10 から呼ぶようにした
  （Issue #571）。ページ自身の `title` と同じタグ（そのページ自身としか括れない）と、`type` と
  同じタグ（`type:` が既に述べている）を報告する。Issue #275 が散文で禁じたにもかかわらず
  再発しており、検出手段が無いルールは drift する。照合は正規化後の**完全一致**のみで、
  部分一致は見ない（`見沼田んぼ` というページの `見沼` タグは有用な方であるため）。
  警告のみで、マージも健全性判定もブロックしない
- `/wikicommit-collect` が**索引ページを参照節から掘れる**ようになった（Issue #570）。
  `.wikicommit/source-policy.md` の `index_only:`（ドメイン単位）またはコマンド引数
  `--index <url>` で指定したページは候補にならず、その引用・外部リンク節から一次資料 URL を
  取り出して候補に流し込む。**索引ページ自身は決して登録しない**のが (a) と (b) を分ける境界
  で、本文を読んで「何を書くか」を決めると、そのページが `sources:` に無いため Pass 4 の
  出典照合も帰属表示も効かず、無帰属の二次的著作物になる。あわせて Step 2 の guidance の
  例示（`"search mainly on Wikipedia"` → `site:wikipedia.org`）を差し替え、百科事典を名指し
  する guidance はどちらの意味かを確かめてから動くようにした
- ShareAlike ライセンスのソースを登録したとき、登録メッセージがその旨を一度知らせるように
  した（Issue #570）。`sources` が**全件** ShareAlike のページは `/wikicommit-generate` の
  Completion Notice にも列挙される（義務が付くのはソースではなくページであるため）。
  一律禁止にはしない — 一次資料が存在しない対象（神社の由緒・地域の文化的概念等）は必ず
  残るため、義務を負うページを意図的に少数に絞ることが目的
- `check_orphans.py` の `ORPHAN:` 行にそのページの `sources` を添えた（Issue #570）。
  孤立の次に問う価値があるのは「どのソースが作ったか」であり、「骨格ソース先行なら orphan に
  なりにくい」という**検証すべき仮説**を運用中に確かめられるようにする
- `.wikicommit/source-policy.md` を新設した（Issue #564）。「**どんなソースを取り込むか**」を書く
  ファイルで、`config.yml` の `theme`（「何についての Wiki か」＝ 取り込み済みのソースから
  どのエンティティをページ化するか）とは別の問いに答える。これまで置き場が無かったため
  ソース方針は `theme` に押し込まれ、主経路（`/wikicommit-generate <path|url>` の直接実行）では
  一切読まれないまま、Pass 2c のエンティティ除外判定にノイズとして混入していた。
  `/wikicommit-init` が空のテンプレートを配布し、再実行しても上書きしない。**ファイルが無い
  既存リポジトリは従来どおり動く**（本文が空ならプローズ方針は無いものとして扱う）。
  フロントマターに `exclude_domains`（`check_extraction_quality.py` の組み込みリストと和集合。
  組み込み側を無効化することはできない）と `rejected`（検討して却下したソース。
  `/wikicommit-collect` が却下直後に理由付きで追記する — これが無いと自由探索は同じ候補を
  毎回再提案する）を持つ。`exclude_domains` の各エントリはスキーム・パス・ポート・先頭 `www.` を
  除去してから**完全一致**で比較する（`example.com` は `blog.example.com` に一致しない）。
  `/wikicommit-merge` はこのファイルの変更を検出・コミットする（追記が未コミットのまま残ると
  記録として機能しないため）
- `check_installed_type_usage.py` を追加し、`/wikicommit-status` の Step 9 から呼ぶようにした
  （Issue #565）。`check_schema_coverage.py` の対で、**スキーマファイルが在るのにページが 0 件**
  （`UNUSED`。`provenance: default` の型は対象外）と、**より具体的な子孫型がインストール済みなのに
  祖先型でページが書かれている**（`ANCESTOR_FALLBACK`。示唆であって断定ではない）を報告する。
  あるパイロットでは `Park.md`・`Museum.md` を承認済みでインストールしていながら公園 7 件・
  博物館 2 件が素の `Place` として生成され、`Place` にはスキーマファイルがあるため既存の
  ゲートは 0 件を報告し続けていた。警告のみで、マージも健全性判定もブロックしない
- `check_schema_org_type.py` に `--list-installed-hierarchy` を追加した（Issue #565）。
  `.wikicommit/schema/` にインストール済みの型それぞれについて、**インストール済みの祖先型のみ**を
  近い順に出力する。`wikicommit-generate` Pass 2c がこれをコンテキストに含める
- `check_unlinked_entity_mentions.py` を追加し、`/wikicommit-status` の Step 8 から呼ぶようにした
  （Issue #561）。エンティティ型を range に持つ `properties:` キーの値が、**実在するページを指すのに
  プレーンテキストで書かれている**ものを報告する。`check_wanted_pages.py`（リンクはあるが実体がない）の
  鏡像にあたる。あるパイロットでは、1 つの値リストに並ぶ 10 人のうち、Book ページと同じ ingest で
  ページが作られた 8 人だけが WikiLink 化され、後の ingest でページが作られた 2 人がプレーンテキストの
  まま残っていた（同一 property・同一型・同一の資格で、分かれ目は取り込み順序だけ）。修正は
  `/wikicommit-fix <page-path>` で行う — 機械的な一括置換はしない。警告のみで、マージも
  健全性判定もブロックしない
- `check_recurring_characters.py` を追加し、`/wikicommit-status` の Step 7 から呼ぶようにした
  （Issue #560）。作品ページの `properties.character` にプレーンテキストで列挙された登場人物を
  全ページ横断で集計し、2 件以上の作品に再登場するのに `Person` ページを持たない名前
  （`RECURRING`）と、既に `Person` ページがあるのにリンクされていない名前（`UNLINKED`）を
  報告する。プレーンテキストの名前は `check_wanted_pages.py` からは見えない（WikiLink しか
  読まないため）ので、これまでどこにも現れなかった。警告のみで、マージも健全性判定も
  ブロックしない

- `/wikicommit-generate --regenerate` を追加した（Issue #578）。既存の Wiki ページを、現在の
  スキーマテンプレート・生成ルールで作り直すページ起点のモード。対象ページの `sources` を
  再取得し、Pass 2・Pass 2b を飛ばして Pass 3・Pass 4 のみを実行する。再生成されたページの
  `review_status` は `pending` に戻る（人間が一度も読んでいない内容にレビュー済みの証明を
  引き継がせないため）
- ライセンス表示の②層（サイト全体）と④層（README）に着地点を与えた（Issue #645。①層＝
  ページ単位の帰属は Issue #558 で実装済み）。②層は `convert_wikilinks.py` が生成する
  ルート `content/index.md` と `content/sources/index.md` に「利用条件はページごとに異なり、
  サイト全体に単一のライセンスは無い。各ページの出典欄を見よ」という注意書きを出す形にした
  — Quartz の footer プラグインは `links`（ラベル → URL）しか受け取らず散文を出せないこと、
  フッターにリンクだけ置く案も `baseUrl` が `<owner>.github.io/<repo>` になる GitHub Pages の
  プロジェクトページでちょうど壊れることによる。文面は `primary_lang` に応じて日本語／英語。
  登録ソースが 0 件でも表示する（「この Wiki がどう作られているか」の記述であるため）。
  ④層は `wikicommit-init` の Next steps（`_LICENSING_STEP`）に README 用の項目を足し、
  そのまま貼れる推奨文面まで提示する形にした — README.md は display-only（エージェントが
  編集しない）方針のため、自動生成・自動追記は行わない

- `/wikicommit-collect` の候補提示に、登録時に記録されるのと同じ既知ライセンスを併記する
  ようになった（Issue #646）。`add_source.py` に読み取り専用の `--license-for-url` を足し、
  `wikicommit-collect` Step 6 がこれを引く。ShareAlike のソースについては「このソースだけから
  作ったページは同じライセンスで提供する義務を負う」旨も添える — 登録時の警告（Issue #570）を、
  まだ断れる 1 段手前へ前倒しするもの。**対応表に無いドメインには何も書かない**（対応表は
  自サイト全体にライセンスを明示しているサイトしか持たないため大半が該当し、ほぼ全行に付く
  注記は読み飛ばされる）。代わりに候補一覧の前置きで「ライセンスは確認済みのサイトにのみ表示
  され、無表示は『条件を把握していない』であって『制約が無い』ではない」と 1 度だけ述べる。

- `/wikicommit-synthesize` にソース整合性レビュー（Step 5.5）を追加した（Issue #674）。ページを書く
  3 経路のうち、合成だけが検証を持っていなかった — `/wikicommit-generate` は Pass 4 で外部ソース文書と、
  `/wikicommit-translate` は原文ページと照合する一方、合成は「grounding ページ本文に無い主張を書くな」
  という 1 文だけが防護だった。**合成ページは 3 経路の中で最も検証が要る側にある**: `sources` を持たず
  `derived_from` のみを持つため、読者が内容を確かめる唯一の道が grounding ページを辿ることである。
  Pass 4 と同型のレビューサブエージェントを挟み、FAIL 時は `issues[].instruction` を再生成プロンプトへ
  渡す。再試行は `generate.max_retries` を流用し（専用キーは新設しない）、上限超過時は書き出さずに停止して
  報告する。grounding ページ同士の食い違いは FAIL にせず完了報告に列挙する（この Skill は grounding ページを
  書き換える権限を持たないため、FAIL にすると正しい合成を作り直しては同じ指摘を受けることを繰り返す）
- 同じく `/wikicommit-synthesize` で、grounding のうち `review_status: pending` のページを本文生成の前に
  列挙するようになった（Issue #674。文言は `/wikicommit-ask` の ⚠️ と揃える）。**警告でありゲートではない** —
  生成バッチ直後の Wiki は全ページが `pending` であり、そこで止めると最も有用な場面で使えなくなる
- 同じく、grounding set から `derived_from` を持つページ（＝他の合成ページ）を除外するようになった
  （Issue #674）。「合成ページは通常ページの 1 段上にしかない」という不変条件が成立し、
  `check_derivation_freshness.py` が陳腐化を完全に捉えられるようになる。**索引からは除外しない** —
  `/wikicommit-search` / `/wikicommit-ask` からは引き続き合成ページが見つかる

### Changed

- **CI の課金分数削減策の効果を実測し、残っていた採否を確定した**（Issue #641。文書のみの変更で
  ワークフロー定義は変えていない）。Issue #591 は Actions 無料枠が枯渇して CI を 1 度も回せない
  状態で適用されたため、効果が机上の見積もりのままだった。枠のリセット後に測定した結果:
  **1 run あたりの課金分数は中央値 9 分 → 5 分・平均 12.1 分 → 4.72 分**（削減後の成功 run 25 件）。
  `Issues/` のみを変更した PR では 2 ジョブのいずれも起動せず（workflow run 0 件・check-run 0 件）、
  かつ `mergeable_state` が `clean` でマージをブロックしないことも実 PR で確認した。
  あわせて 2 件の判断を確定している — **`node_modules` の `actions/cache` は採用しない**
  （`npm ci` の合計は 77 秒しかない一方、キャッシュ対象は圧縮後 394 MB／非圧縮 1.3 GB で、
  リポジトリのキャッシュ枠 10 GB に対しエントリ 1 つで約 4% を占め、ロックファイル更新のたびに
  エントリが増えて他のキャッシュを追い出すうえ、更新した run はかえって遅くなる）、
  **spending limit は引き上げない**（削減後は同じ run 数なら月あたり約 1,100 分の見込みで
  無料枠 2,000 分に収まる。再評価は run 数がおよそ 2 倍になった時点）。
  測定方法と数値は `docs/DesignDoc-TestSpec.md` L8 に記録した

- **「レビューは分割可能でなければならない」を設計原則として立てた**（Issue #676。文書のみの変更で
  コードは変えていない）。`docs/DesignDoc-architecture.md` に §1.6 として追加し、`README` 両言語の
  冒頭をこれに合わせた（開発リポジトリ側のプロジェクト指示・要件定義も同じ内容に揃えている）。**LLM は 1 人が読める
  速さを超えてページを生成するため、レビューがバッチ単位でしか進められない設計では生成が速いほど
  詰まる** — レビューの単位をページ 1 枚に固定する（1 ページ ＝ 1 レビュー追跡 Issue ＝ 1 Close）
  ことがそれを避ける条件である。既存の §1.5「段階的信頼形成」がゲートの**順序**（縦）を述べるのに
  対し、§1.6 は単位の**分割**（横）を述べる。
  これは実装済みの設計に理由を付ける変更である — レビュー追跡 Issue をページ単位にした理由は
  `docs/DesignDoc-pipeline.md` §6.2 に「GitHub が PR 作成者本人の Approve を許可しないから」という
  経緯としてのみ記録されており、PRD が「設計の核心」と呼ぶものが DesignDoc 側では制約への回避策として
  書かれていた。経緯の記述はそのまま残し、そこへ §1.6 への参照を足している。
  あわせて **WikiCommit が提供するのは「単位」までで、「担当者」の割り当ては持たない**ことを明記した
  （assignee・優先キュー・レビュアー募集はいずれも仕組みとして存在しない）

- **ブラウザタブ・OGP のタイトルにサイト名が載るようにした**（Issue #679）。
  `/wikicommit-init --quartz` が生成する `quartz.config.yaml` の `pageTitleSuffix` に
  `" - <リポジトリのディレクトリ名>"` を埋めるようにした（`pageTitle` と同じ置換機構）。
  Quartz 本体の `Head.tsx` は `<title>` を「そのページの frontmatter `title` + この suffix」
  だけで組み立てており、`pageTitle` はここに一切入らない（届くのは左サイドバーと OGP の
  `og:site_name` だけ）。suffix が空だったため、**トップページのタブが `Wiki` としか
  表示されないだけでなく、全ページのタブ・`og:title`・`twitter:title` にサイト名が
  出ていなかった** — どのページを共有してもリンクカードの見出しが `Sources`・`山田太郎`
  のままになる。トップの `title: "Wiki"` 自体は変更していない（suffix が入れば
  `Wiki - <サイト名>` になり、報告された実害はそれで消えるため）。
  **既存リポジトリには自動では効かない**（`quartz.config.yaml` は再 init で上書きしない）。
  手で直す場合は 1 行を書き換えるだけで同じ結果になる:

  ```yaml
  pageTitle: "decameron-wiki"
  pageTitleSuffix: " - decameron-wiki"
  ```

  先頭の半角スペースを忘れるとタブが `Wiki- decameron-wiki` になる。ページの再生成は
  不要（ビルド設定の変更であり `generated_with` の対象ではない）

- **トップページの「テーマ:」表示をやめた**（Issue #670）。サイト概要ブロックの 3 行目に出ていた
  `テーマ: <config.yml の theme>` を廃止し、`convert_wikilinks.py` の `load_theme()`・
  `content/index.md` の `wikicommit_theme` フロントマター・バナー i18n の `siteSummaryTheme`・
  SCSS の `.wikicommit-site-summary__theme` をいずれも削除した。廃止の理由は「訳されていない」
  ことではなく、**そもそも読者向けに書かれた文ではない**こと — `theme` は LLM 向けの内容スコープ
  指示（読む主体は `wikicommit-generate` Pass 2c と `wikicommit-collect`）であり、値が 1 本しか
  ないため書かれた言語のまま全読者に届き、しかも Issue #564 が `.wikicommit/source-policy.md` へ
  分離したはずのソース選定方針が混在しがちで、生成器への命令文がそのままトップページに出ていた。
  **総ページ数・レビュー済み件数は残す**（数値は言語に依存しないため、この問題を持たない）。
  `config.yml` の `theme` の値自体は書き換えない（LLM 向けの値としては引き続き有効）。既存の
  公開サイトへの遡及対応も不要 — `content/index.md` はビルドのたび全上書きされるため、次回の
  デプロイでこの行は自然に消える。読者向けのサイト説明を持たせるのは後続の Issue #671 の担当で、
  受け皿だけを残さない（Issue #553）ために i18n キーごと削除してある

- 公開 Wiki の入口 2 箇所に出る「レビュー済み」表示を、**数字を残したまま状態の説明に
  置き換えた**（Issue #664）。トップページのサイト概要バナー（`Reviewed: 0`）と俯瞰ページの
  Totals（`- **Reviewed**: 0 / 486 (0%)`）は正直さの表明として設計したものだが、初見の読者には
  「誰も関心を持っていないプロジェクト」に読め、同じ数字が意図と逆に働いていた。しかも
  トップページは俯瞰ページへリンクしているため、読者は続けて両方を見る。ラベルを
  `Human-reviewed` / `人によるレビュー済み` に改め、それぞれの直下に「ページは LLM が
  生成した時点で公開される。この数字は、そのうち人が内容を確認した件数である」という
  1 行の説明を添えた。**数字は隠していない**（隠すと `Reviewed: 0` を出すという当初の判断
  そのものを裏切る）。**参加の呼びかけ・リンクは加えていない** — この Wiki は外部レビュアーを
  募らないため、参加できない相手への呼びかけになる。俯瞰ページの型別テーブルの列見出しは
  単独で読まれることがないため据え置いた

- **レビュー済みページに、そのレビューをした人を表示するようになった**（Issue #663）。
  `review-issue-close-sync.yml` がレビュー追跡 Issue を Close した人の GitHub login を
  `reviewed_by` フロントマターへ書き（`review_status` を書き換えるのと同じコミット）、
  `WikiCommitBanner` がそれを GitHub プロフィールへのリンクとして表示する。これまで
  レビュアーは `Reviewed-by:` コミットトレーラーとして git 履歴に残るだけで、公開サイトの
  読者には見えなかった — `reviewed` バッジが「レビューされた」とは言うが「誰の判断か」を
  言わず、信頼ラダーの上段が単なるフラグに見えていた。**フィールドを持たない既存の
  `reviewed` ページは、レビュアー名なしの従来どおりの表示にフォールバックする**
  （空のラベルも `unknown` も出さない — 未レビューページの `generated_at`/`generated_by` が
  `unknown` を出すのとは扱いが異なり、レビュアーの欠落は正常な状態であるため）。
  遡及付与は行わない。経路 B（`/wikicommit-review` がローカルで `reviewed` を書く）と、
  この workflow を配置していない Wiki でもフィールドは付かない。**既知の限界**: 一度書かれた
  `reviewed_by` を消す経路は無いため、経路 A でレビュー済みのページが `pending` に戻り
  （`--regenerate` や手動の書き戻し）、その後に経路 B で再レビューされると、前回のレビュアー名が
  そのまま表示される

- 記事系 3 型（`ScholarlyArticle` / `NewsArticle` / `BlogPosting`）の「その文書の主張を書く節」を
  **`## Key Points` に統一し、1 主張 1 箇条書きにした**（Issue #673）。`ScholarlyArticle` だけが
  `## Key Contributions` を名乗り、3 型とも指示が `in list or prose form`（散文でもよい）だった —
  この 2 つが揃うと、散文からは主張を 1 件ずつ取り出せず、型をまたいで探すこともできない。
  箇条書きの中身にも 2 つの規律を課した: その文書自身が述べていることに限る（他文書から引いた
  だけの日付・数値を確定事実として書かない。Issue #473）、根拠が見た目より狭い場合はその箇条書き
  自身にそう書く（単一のデータセット・単一の取材源・著者自身の経験・自社製品のドキュメント等）。
  **新しいスクリプトもプロパティも足していない** — `build_survey_view.py` が既に各ページの `##`
  見出しを抽出しているため（Issue #586）、見出しが 1 つに揃った時点で `/wikicommit-synthesize` の
  俯瞰モードがこの節を横断シグナルとして使える。**この変更以前に生成した記事系 3 型のページは
  作り直す価値がある**（`/wikicommit-generate --regenerate --type ScholarlyArticle` 等）。
  既存ページの `## Key Contributions` は書き換えないので、そのまま残る

- `Person.md` の型テンプレートに、**存命の個人についての記述範囲を絞る** `granularity` ルールを
  追加した（Issue #668）。その人が自ら公表したもの（著作・発言・自称する役職）に記述を寄せ、
  経歴・所属歴・生年月日といった一次資料での裏取りが要る事実は、ソースが述べていても書かない。
  既存の「家族関係・身体的属性は書かない」ルールと同じ判断を、誤りのコストが最も高い場所へ
  広げたもの（Issue #473 — `sources` に無い記事の日付と内容を確定事実として書いた人物ページ）。
  あわせて本文テンプレートの `## Background` にも同じ但し書きを置いた — 節の指示が
  「chronological activities, affiliations, and roles」のままでは、`granularity` と同じファイルの
  中で反対のことを指示してしまうため（Issue #552 が `TechArticle.md` で記録した矛盾と同じ形）。
  **`properties:` のキーは削っていない** — `affiliation` / `jobTitle` / `birthDate` は故人・
  歴史上の人物には引き続き有効な候補キーであり、書かないと決めた項目は Issue #553 の
  「埋められないキーは省略する」ルールでキーごと落ちる。**この変更以前に生成した存命の個人の
  `Person` ページは作り直す価値がある**（`/wikicommit-generate --regenerate --type Person`）。
  ページを作るかどうか自体は別軸で、`.wikicommit/entity-policy.md` の
  `exclude_living_persons`（既定 off）が扱う

- 配布する全 11 の `base_types` の型テンプレートに、その型が**何でないか**を述べる境界ルール
  （`Boundary` で始まる `granularity` 箇条書き）を 1 件ずつ追加した（Issue #550）。境界を述べて
  いる型ほど選ばれやすくなるため、これまで `HowTo` / `Place` / `Event` / `Book` / `ShortStory`
  のように境界を持たない型が一方的に選ばれにくくなっていた。**型選択の傾向は変わるが、
  この変更が効くのは新規生成時のみで、既存ページには `--regenerate` でも反映されない** —
  境界ルールが働くのは型選択（Pass 2c）であり、再生成は既存ページの型を所与として Pass 2c を
  実行しないため。型の再分類は引き続きスコープ外
- `wikicommit-generate` Pass 2b が実行時に新しい型を追加する際の `granularity` 執筆指示を
  追加した（Issue #552）。何を書くかに加え、SKILL.md 自身の他のルール（特に Pass 2a の
  source-as-entity 判定）と矛盾する記述を書かないことを明示した。追加された型の `granularity`
  は Completion Notice に全文表示される。既存のスキーマファイルは変更しない
- `DefinedTerm.md` の型テンプレートに、実践・手法を書くための指針を追加した（Issue #551）。
  `granularity` に「現象・問題」「仕組み・構成要素」「実践・手法」の 3 分類と、3 番目にだけ
  意味を持つ 4 項目（適用条件・前提・失敗モード・根拠の強さ）を明記し、本文テンプレートに
  `## When It Applies` セクション（他の 2 種類では丸ごと省く）を追加した。
  **このテンプレート変更以前に生成した `DefinedTerm` ページのうち、実践・手法を扱うものは
  作り直す価値がある**（`/wikicommit-generate --regenerate --type DefinedTerm`）
- `HowTo.md` の `granularity` に、`tool` / `supply` が空でも HowTo であることを明記した
  （Issue #551）。この 2 プロパティのレシピ・DIY 寄りの見た目が `HowTo` を選ばない理由として
  働いていた、という観察への対応。型の意味自体は変えていないため既存ページの再生成は不要
- `DefinedTerm.md` の型テンプレートから `properties:` の `inDefinedTermSet` と `termCode` を
  削除した（Issue #553）。前者は適合する値（`DefinedTermSet` エンティティか、それを指す URL）を
  Wiki 側で用意する手段が無く、後者はその前者を失うと錨を失うため、どちらも埋めようのない
  空プレースホルダーとして生成ページに残り続けていた（あるパイロットでは `DefinedTerm` 43 ページ中
  14 ページが `inDefinedTermSet` を持ち、値が入っているのは 0 件）。代わりに `granularity` へ
  受け皿を明示した — 分類体系への所属は `tags` に、体系そのものの説明は本文に書く。
  **既存ページの `inDefinedTermSet` / `termCode` は妥当なキーのまま残る**（`validate_frontmatter.py`
  は Schema.org の `domainIncludes` に対して検証し、テンプレートのキー一覧とは照合しない）ため
  遡及的な削除は不要だが、**分類体系を扱う `DefinedTerm` ページは作り直す価値がある**
  （`/wikicommit-generate --regenerate --type DefinedTerm`）
- `config.yml` の `theme` の役割を**内容スコープのみ**に限定した（Issue #564）。
  `/wikicommit-init` の対話プロンプトが「主題を書く。どのソースを使うかは書かない」と明示し、
  `config.yml` テンプレートのコメントも同様に改めた。**既存リポジトリの `theme` に
  ソース方針が混在していても自動移行はしない** — `.wikicommit/source-policy.md` へ手で移すと、
  主経路でも読まれるようになり、あわせてエンティティ除外判定からノイズが消える
- `/wikicommit-generate` の Step 0 が、ソースを登録する前に `.wikicommit/source-policy.md` を
  読むようになった（Issue #564）。方針に明らかに反する引数は、どの行と衝突するかを述べて
  確認を求める（黙って登録も、独断での拒否もしない）。`/wikicommit-collect` も Step 2.5 で
  同じファイルを読み、候補の常設フィルタとして使う（引数の guidance は 1 回の実行を
  絞り込むもので、常設方針を黙って上書きはしない）
- 型スキーマの `granularity` が「この場合は別の型に譲れ」と書いている場合、`wikicommit-generate`
  Pass 2c がそれに従うようになった（Issue #569）。あるパイロットでは `GovernmentService.md` が
  "Prefer schema:HowTo when the source's substance is an ordered set of steps..." と明記していながら
  `GovernmentService` 6 件 / `HowTo` 0 件になり、うち 1 件は「ごみの出し方マニュアル」から
  番号付きの手順をそのまま再現していた。**型間の優先関係は `granularity` に書き続ける**
  （専用キーは新設しない — 譲るかどうかの判定は機械化できず、キーを足しても評価するのは
  結局 LLM のため）。あわせて `granularity` を書く 4 経路（`wikicommit-init` の theme 駆動提案・
  `wikicommit-collect` の Type Proposal・Pass 2b・`wikicommit-schema-propose`）すべてに、
  別のインストール済み型が適切な置き場ならその型名を挙げて書くことを明記した
- **1 ソースから型の異なる複数エンティティを切り出してよい**ことを Pass 2c に明示した
  （Issue #569）。「あるモノ」と「それを使う手順」の両方を扱うソースは両方を抽出してよい。
  上記のごみ出しのケースは「収集サービス本体（`GovernmentService`）」と「粗大ごみの出し方
  （`HowTo`）」に分割すべきだった。**この 2 つはいずれも新規生成にしか効かない** —
  `/wikicommit-generate --regenerate` は Pass 2c を実行せず対象ページの型を所与とするため、
  既存ページの型を変えることも 1 ページを 2 つに分けることもできない。型の再分類とページの
  分割/統合は引き続きスコープ外（Issue #447・#565 と同じ判断）
- `wikicommit-generate` Pass 3 に 2 つのルールを追加した（Issue #571）。**中身が無い見出しは出さない**
  — 本文 239 字のページで 2 つの見出しがいずれも冒頭段落の前半・後半の再掲になっていた。
  テンプレートの見出しは「よく裏付けられたページがとる形」であって、埋める書式ではない。
  **ソースが何を書いていなかったかを本文に書かない** — 「出典とした観光サイトには沿革の記述が
  ない」は読者向けページではなくこの実行についてのメモであり、運用者向けの実行レポートに回す（`coverage_gap_note` はソースが**述べている**属性に `properties:` の受け皿が無い場合のフィールドであり、意味が逆なので流用しない）。
  ただし**内容の確度に関する注記は本文に残す**（「出典が伝承として記している」等）。
  **Pass 3 の変更なので既存ページにも `--regenerate` で反映される**
- `wikicommit-generate` Pass 4 手順5 に、リトライが**毎回別の**欠陥を出し続けている場合に限り、
  対話実行中の人間へ `max_retries` 超過を尋ねてよいことを明記した（Issue #571）。上限は
  「何度やっても直らないページを諦める」ためのものだが、毎回別の欠陥が出るのは収束していない
  のではなくレビューが働いている状態である。非対話実行では延長せず、同じ形で落ち続ける
  ページも延長しない
- 表形式ソース（CSV/XLSX）に対する `wikicommit-generate` の指示を追加した（Issue #568）。
  **独立性の判定は行数ではなく列の内容で行う** — 散文では「言及の厚み」が独立性の代理指標に
  なるが、表では全行が同じ厚み（1 行）になるためこの代理指標が壊れる。行が自分自身の属性を
  複数持つなら独立した事実であり、名前と 1 つの対応関係しか持たない行はそうではない。
  **記述的情報を持たない対応表からは実体ページを作らない** — 関係は相手側のページが既に在れば
  `action: update` で記録し、集計値は「その表が何についての表か」という概念のページに
  性格づけとして書く（行を散文化して並べない）。あわせて Issue #337 の「スキーマが想定する
  抽象度を遵守する」という Pass 3 指示に、表の転記という失敗の形を例示として加えた。
  **転記の是正（Pass 3）は既存ページにも `--regenerate` で反映されるが、
  抽出の対象選定（Pass 2c）は反映されない** — 再生成はどのページが存在すべきかを問い直さないため、
  作られなかった実体ページは作られないままで、不要だったページも残る
- `/wikicommit-generate` が処理対象に集めるソースの条件と順序を変えた（Issue #567）。`status: partial` は
  「一部が生成失敗した（再実行で成功しうる）」と「一部が `theme` 不一致で除外された（同じ `theme` なら
  毎回同じ判断になる）」を同じ値で表しており、後者は何度実行しても `partial` に戻る。**`partial` は
  `failed_pages` が非空のものだけを収集する**ようにした（新しい `status` 値は足していない）。
  あわせて 5 件ガードの選定順序を「一度も生成されていないソース（`last_generated_at` なし）を先に」へ
  変更した（正確には (1) `outdated` (2) 一度も生成されていない (3) 残り、の 3 段 — 既に公開された
  ページのソースが変わった状態は「欠けている」ではなく「誤っている」ため backlog の前に置く）。
  処理対象の提示も「未フェッチ」「フェッチ済みだが未生成」「再処理待ち」の 3 つに分けた。
  収集条件を変えたことで `partial` かつ `failed_pages` が空の URL ソースが「キューに入っている」
  という `SKIP` の前提を失うため、`add_source.py` の `process_url()` もこの状態に対して
  `RECHECK` を返すようにした（そうしないと、その URL は鮮度を再確認する経路を持たなくなる）。
  あるパイロットでは `partial` 8 件（全件が除外由来で、しかも意図どおりの挙動）が枠を占め続け、
  一度も処理されていない 23 件がその後ろで滞留していた。**既存リポジトリへの遡及処理は不要**
  （`failed_pages` が空の `partial` は次回実行時に単に収集されなくなるだけ）。なお `ambiguous` 由来の `partial` も
  `failed_pages` が空のため同様に収集対象から外れる — 型を確定したらソースを名指しで再実行する
- `/wikicommit-status` に「登録済みだが一度も処理されていないソース」の件数を追加した（Issue #567）。
  失敗ではなく単に順番が来ていないものなので、トラッキング Issue 化ではなく集計に留める
- `wikicommit-generate` Pass 4 が**矛盾の検出**を行うようになった（Issue #566）。設計上の品質ゲート表は
  以前から「ページ間矛盾検出」を Pass 4 の責務として挙げていたが、実装は 1 ページ × そのページ自身の
  `sources` の照合しか行っておらず、他のページを見る手順がどこにも無かった。追加したのは 2 つ:
  (1) **ソース間の食い違い** — ページが 2 件以上の `sources` を持つとき、ソース同士が食い違っていれば
  「その事実の主題をその文書自身の主題として扱っている方」を採る（一覧・目録の類は、その項目を主題と
  する文書より弱い証拠）。(2) **WikiLink 1 ホップ以内のページ間矛盾** — 既存の参照先／参照元ページを
  合計 5 件まで追加コンテキストとして渡す。相手ページ側が誤っていそうな場合は FAIL にせず
  Completion Notice に報告する（Pass 4 は相手ページのソースも権限も持たないため）。
  **バッチをまたいだ矛盾は届かない**（リポジトリ全体走査は将来の課題として記録した）。
  **複数ソースを持つページ・相互にリンクし合うページは作り直す価値がある**
- `wikicommit-generate` Pass 2c に「複数のインストール済み型が当てはまるなら最も具体的な型を選ぶ」
  ルールを追加した（Issue #565）。祖先型は常に当てはまる（公園を `Place` として書くのは誤りではなく
  粒度が粗いだけ）ため、指示が無いと広く馴染みのある型が既定で選ばれていた。あわせて
  `Place.md`（子孫 208 型）・`Organization.md`（166 型）・`Event.md`（35 型）の `granularity` に
  「より具体的な型がインストールされているなら譲る」旨を追記した。**この変更が効くのは新規生成時のみで、既存ページには
  `--regenerate` でも反映されない** — 型選択は Pass 2c であり、再生成は既存ページの型を所与として
  Pass 2c を実行しないため。既存ページの型の再分類自体も引き続きスコープ外（ディレクトリ移動と
  全 WikiLink の Type セグメント書き換えを伴うため）
- `wikicommit-generate` Pass 3 に「`properties:` の値リストを書き終えたら読み返す」ルールを追加した
  （Issue #561）。リスト内で WikiLink とプレーンテキストが混在する場合、プレーン側は「その entity が
  参照先の型の independent-subject バーを満たさない」という理由でなければならず、**参照先ページが
  まだ存在しないことは理由にならない**ことを明記した（この点は元から名指しで禁じられていたが、
  値ごとの判断としてしか書かれておらずリスト全体を見渡す視点が無かった）。**物語・行政サービス系など、
  1 つのエンティティが複数の ingest にまたがって言及される Wiki のページは作り直す価値がある**
- `check_recurring_characters.py` の `UNLINKED` 所見を `check_unlinked_entity_mentions.py` へ移した
  （Issue #561）。「ページが無い名前の再登場」（ページを作る）と「ページが在るのに未リンク」
  （リンクにする）は要求される行動が正反対のため、スクリプトとカウントを分けた。前者の
  `SUMMARY:` 行は `recurring=N` のみになった
- 物語ソースの登場人物を `Person` ページへ昇格させる判断基準を型テンプレートに明記した
  （Issue #560）。既存のルールは「作らない」側の条件しか与えておらず、各説話の主人公が
  `properties.character` のプレーンテキストのまま埋もれていた（あるパイロットでは全 100 話の
  主人公が 1 人も `Person` ページを持たなかった）。`Person.md` の `granularity` に「その作品が
  丸ごとその人物についての話であるなら independent subject である（架空か実在かは無関係）」を、
  `ShortStory.md` / `Book.md` の `character` 行に「他の作品ページにも同じ名前があるなら
  独立ページ候補として再評価する」を追加した。**昇格は 1 作品あたり最大 1 ページ + 再登場人物に
  限られ、名前のある登場人物すべてを対象にはしない。昇格そのものは新規生成時にしか働かない** —
  どのページが存在すべきかを決めるのは Pass 2c であり、再生成はそれを実行しない。既存の作品ページの
  `character` を WikiLink 化する側（Pass 3）は `--regenerate` で反映される
- `wikicommit-generate` Pass 3 のページ生成ルールに「埋められない `properties:` キーは
  空のまま残さず省略する」を追加した（Issue #553）。旧文面は「テンプレートの空プレースホルダーを
  写すな」としか述べておらず、値を決められないキーをどうするかを述べていなかったため、
  Pass 3 は埋めるでも消すでもなく素通りさせていた。既存ページが既に値を持つキーは
  `action: update` でも消さない（「このソースが触れていない」は「空である」ではない）

### Removed

- **`config.yml` の `review:` ブロックを削除した**（Issue #669）。`review.auto_merge` と
  `review.chain_of_thought` はどちらも Phase 1 の初期設計から据え置かれたまま、値を読む箇所が
  `.claude/skills/*/SKILL.md` にも `.wikicommit/scripts/*.py` にも 1 つも無かった
  （`auto_merge` で grep に当たるのは GitHub 側の `allow_auto_merge`〈Issue #456〉という
  名前が似ているだけの別物）。両方を消した結果ブロックが空になるため、ブロックごと削除している。
  **実害は「読まれない設定がある」ことではなく、読まれると誤解されることにあった** —
  「`Person` 型だけ `auto_merge: false` にすれば自動マージが止まる」という前提から始まった
  設計相談が、型別分岐以前にグローバルなゲート自体が存在しないため成立しなかった。実際の
  マージ条件は「品質チェックの blocking が全て PASS」だけである。`auto_merge` は信頼ラダー
  （`pending` でも公開する 2 値設計）に第 3 の状態を持ち込むため、必要になった時点で独立に
  設計する。`chain_of_thought` は、レビュー品質を測る手段がリポジトリに無く、有効にして
  良くなったかを誰も判定できない一方でコスト増は確実に生じるため、同じく削除した
  （意図は `docs/DesignDoc-data.md` §3.3 のコールアウトに残してある）。
  **既存リポジトリの `config.yml` は書き換わりません**（再 init は `config.yml` を丸ごと
  スキップするため）。誰も読まない値なので害はなく、手で消す必要もありません

### Fixed

- **経路 B の再レビュー後に、前回のレビュアー名が残らないようにした**（Issue #705）。
  `reviewed_by`（レビュー追跡 Issue を Close した人の GitHub login。Issue #663）を**消す経路が
  どこにも無かった**ため、次の並びで、実際にはその版を見ていない人の名前が公開されていた —
  (1) 経路 A でレビューされ `reviewed_by: alice` が付く、(2) `--regenerate` または人間の手編集で
  `review_status` が `pending` に戻る（**このとき `reviewed_by: alice` は残る**）、
  (3) 経路 B（`/wikicommit-review`）で再レビューされ、`review_status` **だけ**が `reviewed` に
  書き換わる、(4) 公開ページが alice をレビュー者として表示する。
  `set_frontmatter_field.py` に **`--unset KEY`** を追加し（`--set` と同じ行単位の操作で、
  キーが無ければ no-op。`--set` を伴わない `--unset` 単独の呼び出しも受け付ける）、経路 B が
  `review_status: reviewed` を書く同じ呼び出しで `reviewed_by` を消すようにした。`--require` は
  `--set` と `--unset` の両方へ一括して掛かるため、1 回の呼び出しが 1 ページに対する 1 つの
  原子的な書き換えである、という既存の契約は変わらない。
  再生成（`--regenerate`）も `reviewed_by` を残さないが、こちらは `--unset` を使わない —
  Pass 3 がページ全体を書き直すため、出力に含めなければそれで消える。**ただし無変更時の弁が
  `review_status: reviewed` を維持した場合は `reviewed_by` も維持する**（名前だけを落とすと、
  弁が守ろうとしている「実際に人間がレビューした版のままである」という事実を片側だけ壊すため）。
  経路 A（`review-issue-close-sync.yml`）は無条件 `--set` で元から自己修復するため変更なし。
  **既存ページの遡及修正は行わない** — 既に古い `reviewed_by` を抱えたページは、次に経路 A で
  再レビューされるか `/wikicommit-fix` で直すまで残る。

- Type 別インデックスの各行が公開サイトでタイトルの重複（`Adaptive Context Compaction —
  Adaptive Context Compaction`）になっていたのを修正した（Issue #678）。`rebuild_index.py` が
  `[[Type/slug]] — {title}` という行を書く一方、`convert_wikilinks.py` は WikiLink を
  **参照先ページの `title`** で描画するため、両者が重なっていた。Type 別インデックスは Wiki を
  回遊する主要な入口の 1 つであり、全型・全言語の全行がこの形になっていた。行を
  `- [[Type/slug]]` の箇条書きにする（**接尾辞を落とすだけでは足りない** — 各行は空行を挟まない
  連続行であり、配布する `quartz.config.yaml` は `hard-line-breaks` を無効で出荷しているため
  CommonMark が 1 段落に畳む。接尾辞は偶然その区切りとして働いており、マーカーなしで落とすと
  リンクの文字列同士が空白 1 個で隣接した 1 本の長い行になる。`convert_wikilinks.py` が書き出す
  他の一覧はすべて元から `- [{title}]({link})` を書いている）。あわせて `remove_page.py` の
  `remove_index_entry()` が先頭のリストマーカーを任意扱いにし、新旧 3 形式すべての行に
  一致するようにした。**リポジトリ上で生の Markdown として読んだときにタイトルが
  読めなくなることは受け入れる** — その読み手は運用者であって読者ではなく、同じディレクトリの
  ファイル名が slug を持っている。掲載順（slug 昇順）・除外規則（`status: removed`・`title`
  欠落）は変更していない。**遡及移行は不要**（次に該当 Type ディレクトリで
  `rebuild_index.py` が走った時点で是正される。全型を即座に揃えるなら引数なしで 1 回実行する。
  公開サイトへの反映は次のデプロイを待つ）

- `check_wikilinks.py` の被リンクインデックスが、**リポジトリの祖先ディレクトリのどれかが
  `assets` という名前だと空になっていた**のを修正した（Issue #677）。同スクリプトは絶対パスの
  `entity_dir` を作る一方、`assets/` の除外をそのフルパスに対して適用していた。失われるのは
  削除フローが依拠する参照切れ WikiLink の警告そのもので、**エラーにならず件数が減るだけ**の
  ため `/wikicommit-remove` → `/wikicommit-merge` は正常に完了したように見える。あわせて、
  同じ走査条件が 18 箇所に独立して書かれ `assets/` の判定が 3 通りの意味論に割れていた状態を
  `_wikilink.py` の `collect_entity_pages()` / `is_entity_asset()` に集約した — 正しい実装は
  同じファイルの `build_slug_type_index()` に既にあり、そこが名指しでこの誤りを警告していた。
  `assets/` は `entity/` 直下の 1 つだけを指す最も狭い定義に統一している
  （`validate_frontmatter.py` / `check_raw_html.py` は対象が「ディスク上の全 `.md`」であるため
  移行対象外。`convert_wikilinks.py` の `generate_overview_page()` は Type 取り違え判定を
  共有の `other_types_for_slug()` へ寄せた）

- `/wikicommit-collect` が候補 URL を CLI 引数へ埋め込む 2 箇所（step 5 の `check-domain`・
  step 6 のライセンス照会）をヒアドキュメントパターンに修正した（Issue #646。
  `docs/DesignDoc-skills.md` §11.7）。`&` を含む URL（`…/w/index.php?title=X&oldid=1` のような
  普通の permalink）が引用符なしだとシェルに分割され、前半がバックグラウンド実行・後半が
  コマンドとして実行される。`check-domain` 側ではバックグラウンド実行の終了コード 0 が `OK:` と
  読まれ、**この Wiki が除外すると決めたドメインが候補として通る**

- `check_wikilinks.py` を引数なしで実行したとき、`.wikicommit/entity/` 配下の全ページを
  対象にするようにした（Issue #571）。従来は何も検査せず `OK: 0 files checked, 0 errors,
  0 warnings` を出して終了コード 0 で終わっており、**正常なチェックの成功と区別がつかない
  出力**だった。`wikicommit-merge` は常に `--changed` を渡すため差分スコープの挙動は変わらない

- 型テンプレートの `granularity` 各行のうち、`(Issue #NNN)` を行末以外に含む 3 行が、
  YAML のコメント記号として解釈されて途中で切り捨てられていたのを修正した（`DefinedTerm.md`
  で最大 714 文字が欠落）。該当行を引用符で囲み、`tests/test_schema_template_boundary_rules.py`
  に再発防止のテストを追加した

- `/wikicommit-init` の再実行（既存リポジトリに対しては常に `--no-overwrite` が付く）で
  `.wikicommit/scripts/` が更新されるようにした（Issue #647）。従来はツリーごとスキップされる
  ため、新しい版の Skills をインストールして再 init しても `.wikicommit/scripts/_version.py` が
  初回 init の版のまま残り、**新しい Skills が生成したページに古い版が刻印されていた**
  （`generated_with` / `translated_with`）。刻印が無いこと（Issue #577 の「この機能追加より前に
  作られた」）は無害だが、誤った刻印はこのフィールドの唯一の用途 — この CHANGELOG と `grep` を
  突き合わせて再生成すべきページを選ぶこと — に対して能動的に誤った答えを返す。
  `.wikicommit/scripts/` は Skills が呼ぶ共通スクリプト＝配布物であり、`--no-overwrite` が守る
  ユーザーのファイル（`config.yml`・`schema/`・`entity/` のページ・ルート直下の設定ファイル）
  とは所有者が異なる、という線引きに従う。`config.yml` の `wikicommit_version`（＝初期化された版）
  は従来どおり更新されない。**再 init 時に `.wikicommit/scripts/` の差分がコミット対象に現れる**
  ようになる点に注意（意図した変更であり、通常どおりレビューしてコミットしてよい）
  なお `.wikicommit/schema/` は引き続き refresh されない（人間の直接編集を許す唯一の領域のため）。
  型テンプレートを変更した版へ上げた場合、再 init だけでは版だけが先に進み、以後生成される
  ページは旧テンプレート由来でありながら新しい `generated_with` を持つ。**型テンプレートを
  変更した版では、再 init に加えて `.wikicommit/schema/` の差分を手で取り込むこと。**

- `quartz-plugins/` の `.ts` / `.tsx` コメントに残っていた開発リポジトリパス参照
  （`docs/DesignDoc-*.md`）10 箇所を削除し、`wikicommit-explorer` / `wikicommit-properties` /
  `wikicommit-sources` を再ビルドして `dist/` を `src/` と同期させた（Issue #644。Issue #549 で
  意図的にスコープ外とした最後の層）。配布先には `docs/` が存在しないためこれらの参照は
  原理的に追跡できない。設計根拠として残す価値のあるものは Issue 番号のみを残し、それ以外は
  文意を 1 文に内在化するか削除した。あわせて `dev/scripts/check_distributed_path_refs.py` の
  `DEFERRED_DIRS` 機構を削除し、`quartz-plugins/` も他の配布物と同じ `ERROR` 対象に一本化した
  （`SUMMARY:` から `deferred=` が消える）。あわせて `.map` を `TEXT_SUFFIXES` に加えた —
  バンドラは `dist/*.js` からコメントの大半を落とす一方 `.js.map` の `sourcesContent` は
  `src/` をそのまま抱えるため、`.map` を見ないと「`src/` は直したが再ビルドし忘れた」が
  無言で通る（今回の 10 箇所も 3 プラグイン全ての `.map` に載っていたのに対し、
  `dist/*.js` に残っていたのは 1 プラグインだけだった）

## [0.1.0] - 2026-08-29

WikiCommit に版番号を導入した最初のエントリ（Issue #577）。これ以前の変更は
`git tag` も版文字列も存在しなかったため、ここには記載しない。

### Added

- WikiCommit 自身のバージョン `0.1.0` を定義した。source of truth は
  `.wikicommit/scripts/_version.py`（インストール先まで届く）と
  `.claude-plugin/plugin.json` の `version`（Claude Code の plugin 機構が読む）の 2 箇所
- `/wikicommit-init` が `.wikicommit/config.yml` に `wikicommit_version` を刻印するようになった
  （そのリポジトリがどの版で初期化されたかの記録）
- `/wikicommit-generate` `/wikicommit-synthesize` が生成ページの frontmatter に `generated_with`、
  `/wikicommit-translate` が翻訳ページに `translated_with` を書き込むようになった
  （そのページがどの版で生成・翻訳されたかの記録）
- `validate_frontmatter.py` が `generated_with` / `translated_with` を検証するようになった
  （任意フィールド。存在する場合のみ、空文字列を ERROR とする）
- このファイル（`CHANGELOG.md`）を新設した

### Notes

- 型テンプレートおよびページ生成ルールの変更はこの版には含まれない。したがって
  **この版を理由に既存ページを再生成する必要はない**
- 既存の Wiki リポジトリ・既存のページへの遡及付与は行わない。`wikicommit_version` /
  `generated_with` / `translated_with` の欠如は「この機能追加より前に作られた」ことを意味する
