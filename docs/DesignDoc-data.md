# WikiCommit — リポジトリ構造・データ設計・スキーマ層

> **対応DesignDoc**: 元 §3・§4・§5

---

## 3. リポジトリ構造

### 3.1 Wiki リポジトリ（`/wikicommit-init` が生成）

```
<repository-name>/                  # 新規または既存のリポジトリ
├── README.md                       # 既存リポジトリのファイル（例）
├── raw/                            # ソースドキュメント置き場（例・任意の名前可）
│   └── paper-2024.pdf             # 取り込み元ファイル（例）
├── src/                            # 既存のソースコード（例）
│   └── auth.py                    # 取り込み元ファイル（例）
├── ...                             # その他の既存ファイル・ディレクトリ
├── quartz.config.yaml               # Quartz v5 設定（SSG 選択時。ルートに置く必要あり。YAML 形式）
├── package.json                    # Quartz ビルドスクリプト（SSG 選択時。ルートに置く必要あり）
├── quartz/                         # Quartz v5 本体（SSG 選択時。npm 配布ではなく git submodule で取り込む）
│
├── .wikicommit/
│   ├── config.yml              # ツール設定（翻訳対象言語・レビュー動作）
│   ├── source/                 # ソース管理ファイル（wikicommit-generate が生成）
│   │   ├── path/                # リポジトリ内のファイル（パスをミラー）
│   │   │   ├── README.md.md    # README.md のソース管理ファイル
│   │   │   ├── raw/
│   │   │   │   └── paper-2024.pdf.md   # raw/paper-2024.pdf のソース管理ファイル
│   │   │   └── src/
│   │   │       └── auth.py.md          # src/auth.py のソース管理ファイル
│   │   └── url/                # 外部 URL（ホスト名をディレクトリ、パス+クエリをファイル名にする）
│   │       └── example.com/
│   │           └── blog-article.md
│   ├── schema/                 # タイプ定義（LLM 指示書と品質ゲート仕様書）
│   │   ├── Person.md
│   │   ├── Place.md
│   │   ├── Organization.md
│   │   ├── Event.md
│   │   ├── HowTo.md
│   │   ├── DefinedTerm.md
│   │   ├── default.md          # 専用ファイルを持たない型のフォールバック
│   │   └── custom/             # Schema.org にないカスタム型
│   │       └── Decision.md
│   ├── entity/
│   │   ├── assets/             # 全言語共通の画像・添付ファイル（content/assets/ へミラーされ公開される）
│   │   ├── ja/                 # 原文（最初に作成した言語）
│   │   │   ├── Person/
│   │   │   │   ├── index.md    # タイプ別インデックス（wikicommit-generate が自動生成・更新）
│   │   │   │   └── yamada-taro.md
│   │   │   ├── Place/
│   │   │   ├── Organization/
│   │   │   ├── Event/
│   │   │   ├── HowTo/
│   │   │   └── DefinedTerm/
│   │   └── en/                 # 翻訳（config.yml の targets に応じて生成）
│   │       └── Person/
│   ├── run/                    # 実行記録（1 実行 ＝ 1 ファイル。git 追跡外・ローテーションあり。Issue #790）
│   ├── guides/                 # 人が一度だけ手でたどる手順書（1 タスク 1 ファイル・英語。Issue #846）
│   │   ├── enabling-comments.md
│   │   └── updating-the-quartz-submodule.md
│   └── scripts/                # Skills の共通スクリプト（品質チェック含む）
│       ├── validate_frontmatter.py
│       ├── check_orphans.py
│       ├── check_expires.py
│       ├── check_translation_status.py
│       ├── check_derivation_freshness.py
│       └── check_ingest_freshness.py
│
├── .claude/                    # Claude Code が認識するプロジェクト Skill 配置
│   ├── settings.json           # skillOverrides（init.py が 3 キーだけをマージする。Issue #953）
│   └── skills/                 # Skills の正本（Claude Code が直接読み込む）
│       ├── wikicommit-init/
│       │   └── SKILL.md
│       ├── wikicommit-generate/
│       │   └── SKILL.md
│       └── ...（他 Skill）
```

> **`entity/assets/` の公開経路とファイル名規約（Issue #589）**: `.wikicommit/entity/assets/` は全言語共通の画像・添付ファイルの唯一の置き場であり、`convert_wikilinks.py` の `sync_assets()` が配下の全ファイルを `content/assets/` へミラーする（`.md` のページ変換と同じく、元ファイルを削除すると次回実行で `content/assets/` からも消える stale cleanup 付き。Issue #271 と同じ契約）。Quartz v5 の builtin `Assets` emitter が `content/` 配下の非 `.md` ファイルを `public/` へコピーするため、`quartz.config.yaml` の変更は不要。ページからの参照は `.wikicommit/entity/<lang>/<Type>/<slug>.md` から見た相対パス（例: `![alt](../../assets/diagram.png)`）で書く（`docs/DesignDoc-publish.md` §8.6）。`content/` は `.wikicommit/entity/` のほぼ 1:1 ミラーなので、この相対深さは標準型ページではそのまま成立する。唯一の例外はカスタム型ページで、公開時に `custom/` セグメントが落ちて 1 段浅くなるため相対深さが変わる（例: `.wikicommit/entity/<lang>/custom/<Type>/<slug>.md` からは `../../../assets/diagram.png` と書く）。この差分は `convert_wikilinks.py` の `rewrite_relative_links()` が publish 時に吸収するので、ページ本文は常に `.wikicommit/entity/` から見た相対パスで書けばよい（§5.3）。
>
> **ファイル名規約**: 小文字英数字・`-`・`_`・`.` を推奨し、**スペース・大文字・`&`・`%`・`?`・`#`・`<>:"|*` を使わない**。Quartz の `Assets` emitter は `slugifyFilePath()` を通してから出力名を決めるため、これらを含むファイル名は `public/` 上で別名になり、ページ本文に書いた相対パスと食い違う（実測: `My Diagram.png` → `my-diagram.png`、`a&b.png` → `a-and-b.png`、`50%.png` → `50-percent.png`）。文字種以外に2つの改名規則があることにも注意する — `_index.png` は `index.png` になり、**親ディレクトリ名と同じ名前のファイル**（`assets/foo/foo.png`）は `assets/foo/index.png` になる。一方、非 ASCII（日本語等）とアンダースコア・複数ドットはそのまま通る。`sync_assets()` はこの規則を移植した `quartz_asset_slug()` で公開名を先読みし、入力パスと食い違う場合にのみ WARNING を出す（ブロックはしない）。先読みは `content/` 起点のパス（`assets/<name>`）に対して行う — 「親ディレクトリ名と同名 → `index`」の規則は最後の2セグメントを見るため、トップレベルの `assets/assets.png` は `assets/index.png` になり、`assets/` 起点のパスで判定すると取りこぼす。
>
> なお `Assets` emitter は `**/*.md` を除外するため、`assets/` 配下に `.md` を置くと添付ファイルとしてではなく通常のページとして描画される（`convert_wikilinks.py` のページ走査からは除外されるので、二重に書き出されることはない）。

既存リポジトリに対して `/wikicommit-init` を実行する場合、既存のファイルは移動・複製せずに保持し、`.wikicommit/` のみを追加する。

> **README が 1 つも無いリポジトリにだけ README.md を作る（Issue #1034）**: Issue #282 は「README は既にあることが多く、自動挿入は元の構成を壊しうる」として init が README.md を編集しないと決めた。その理由は README が無い場合には当てはまらないため、**GitHub が表示する位置（ルート・`.github/`・`docs/`）のどこにも、拡張子・大文字小文字を問わず README が無いときだけ**、固定の英語テンプレートにリポジトリ名を埋めて作る。LLM が書いた文章を含まないので基盤コミット（Issue #843）にそのまま乗る。ライセンスの節の文面は `print_next_steps.py` が貼り付け用に示す文面と同じ定数（`_root_outputs.README_LICENSE_TEXT`）から作る。公開サイトへのリンクは Pages の `html_url` が分かる SKILL.md step 3 まで待ち、`--quartz-pages` のときだけ置いた目印を `init.py --finish-readme` が差し替える（得られなければ目印を消す）。差し込みは**同じ実行で作った README に限る** — 前の実行で作られた README は既に利用者のものである。`_root_outputs.py` では `update: skip`・`condition: readme_created`（選択的な `git add` の列挙に入るのは作った実行だけ。元からあった README には利用者の未コミットの編集がありうる）。既存リポジトリでも README が無ければ次の再 init で作られる（`CHANGELOG.md` に記載）。読者向けの説明は見出しを置かずコメントだけにし、`theme` は流用しない（Issue #670）。Wiki ページの `sources.path` は `src/auth.py` のように既存ファイルを直接参照する。
>
> **`.claude/settings.json` の `skillOverrides` — 自律起動を絞る 2 層のうち新規リポジトリ側（Issue #953）**: `/wikicommit-init` は `wikicommit-generate` / `wikicommit-merge` / `wikicommit-translate` の 3 本を **`name-only`** として書き込む。この 3 本は Issue #945 で `disable-model-invocation` を失った — 無人実行の経路がその 3 本で閉じるため — が、同時に通りすがりの依頼でモデルが自律起動しうるようになった。
>
> **2 層の分担は「届く先」で分かれる**（`docs/DesignDoc-skills.md` §11.1）:
>
> | 層 | 手段 | 届く先 |
> |---|---|---|
> | ① | `description` を絞る | **全リポジトリ**。`npx skills add` で既存の Wiki にも届く |
> | ② | この `skillOverrides` | **これ以降に init したリポジトリだけ** |
>
> **したがって、説明文が唯一の防御になるのは既存リポジトリである** — この設定は遡及しない（本ドキュメント群が一貫して採る「新旧混在を許容する」方針）。**既存の Wiki を「保護されている」と読まないこと。**
>
> **`user-invocable-only` を採らない。** 無人実行したい運用者は `on` に戻す必要があり、その瞬間にそのリポジトリの全 Skill で自律トリガーが復活する（全か無かのスイッチになる）。`name-only` は説明文＝自律トリガーの主機構だけを隠して名指しの起動経路を残すので、**無人実行は切替なしで通る**。引き受ける代償は、説明文が担っていた抑止（「明示的に頼まれたときだけ使え」）も同時に消え、残る手掛かりが名前だけになることである。
>
> **既に値があるキーには一切触らない**（`--no-overwrite` の有無に関わらず）。`on` に戻しているのは無人実行を意図した運用者であり、再 init がそれを黙って戻すと**そのリポジトリの無人実行が次から静かに止まる**（しかも出力は成功系になる）。したがってこれは**ファイルのコピーではなくキー単位のマージ**であり、`_root_outputs.py` のフラグ（ファイル単位）では表現できないため `init.py` に専用の経路を持つ。`permissions` / `env` / `hooks` 等、利用者自身の他のキーもそのまま保つ。
>
> **JSON として読めない場合は何も書かず `WARNING:` を出す。** 読めない設定を上書きすると利用者の設定を失う一方、黙って進むと**無い保護を有るものとして報告する**ことになるため、その旨を明示する。
>
> **差分検出は `json_keys`**（`check_distribution_freshness.py`）。**値ではなくキーだけを見る** — `"wikicommit-generate": "on"` は運用者が意図して無人実行している状態であり、それを `OUTDATED` として報告すると、まさにその決定を取り消す方向へ押すことになる。上流が新しい Skill をこの表に足した場合にのみ報告される。
>
> **このリポジトリ自身（wikicommit-dev2）は `user-invocable-only`** であり、上の既定とは別である。ここには無人実行の必要が無く（クラウド自動化が使うのは `implement-issue` と `review-and-merge` である）、最も強い設定を選んでも失うものが無い一方、最も多くのエージェントセッションが走り常に未コミットの変更がある場所だからである。
>
> **`settings.local.json` には書かない。** `.gitignore` 済みでクラウド／Routine に届かず、追跡された `settings.json` より優先順位が上なので、保護の置き場としては逆である。

`.claude/skills/` は Claude Code が固定配置を要求するため、`.wikicommit/` の外に置くプラットフォーム連携層とする。

> **トップレベルディレクトリ名 `.wikicommit/wiki/` → `.wikicommit/entity/`（Issue #477）**: `content/sources/`（Issue #476）の導入により公開サイトが `.wikicommit/wiki/` 由来のentity/conceptページと `.wikicommit/source/` 由来のsourceページの両方から構成されるようになり、中核コンテンツディレクトリが引き続き `wiki/` と名乗ることが「wikiという名前のディレクトリが公開サイト全体の一部でしかない」という矛盾を生んでいたため、Pass 2 の分析JSON（`"entities": [...]`）で既に使われている `entity` という語彙に統一した。移行は自動リネームを行わず新旧混在を許容する（Issue #352 の `repository/`→`path/` 等リネーム時と同じ前例踏襲）。
>
> **`translated_from`/`derived_from[].path`/`generated_pages[]`/Issueマーカーに埋め込まれた旧パス文字列への後方互換**: 上記の「新旧混在を許容する」方針は、ディレクトリそのものの新旧混在だけでなく、ページの frontmatter やレビュー追跡 Issue の本文に**文字列として埋め込まれた**旧パス（例: `translated_from: .wikicommit/wiki/ja/Person/yamada-taro.md`）にも及ぶ — これらの値は自動移行されないため、リポジトリ側がディレクトリを `git mv` で完全移行した後もそのまま残り続ける。これを消費する側のスクリプト・Skill 指示はすべてこの後方互換を実装する必要がある: `.wikicommit/scripts/_wikilink.py` の `normalize_entity_prefix()`/`resolve_stored_entity_path()`（`validate_frontmatter.py`・`check_translation_status.py`・`check_derivation_freshness.py` が使用）、`convert_wikilinks.py` の `normalize_wiki_rel()`（`generated_pages[]` 用）、`WikiCommitSources.tsx`・`WikiCommitBanner.tsx`（Issue #528。両者とも同名の `entityPathToRelativePath()` を独立に複製 — 各 `quartz-plugins/` パッケージがそれぞれ独立ビルドのため、`WikiCommitSources.tsx` の同関数コメントが説明する理由でここも共有関数化していない。Issue #587 で `translatedFromToRelativePath()` から改名した — `WikiCommitSources.tsx` 側が `derived_from[].path` にも同じ変換を適用するようになり、フィールド名ではなく変換内容を表す名前にした。`WikiCommitBanner.tsx` 側の用途は `translated_from` のみのままだが、2つを対で見つけられる状態を保つため同時に改名している）の `entityPathToRelativePath()`（この2つは旧プレフィックスの吸収に加えて、Issue #576 の `custom/` フラット化にも対応する必要がある — 突き合わせ先の `relativePath` は `content/` 相対であり `custom/` を含まないため。ここを直さないと翻訳された custom 型ページの sources 継承と原文ページリンクが**例外にならず黙って**効かなくなる。同じことが `WikiCommitSources.tsx` の `derived_from[].path` 解決にも当てはまる — Issue #587）、`.claude/skills/wikicommit-remove/scripts/remove_page.py` の `normalize_entity_prefix()`（同名だが `_wikilink.py` からのインポートではなく複製 — **この Skill スクリプトを自己完結に保つという慣行による**。かつてここには「サブプロセスとして実行され `.wikicommit/scripts/` が呼び出し元の cwd から解決可能とは限らないため」と書いていたが、**その理由は成立しない**〈Issue #947〉: 全 SKILL.md の呼び出しは `python <Skill ツリー>/<skill>/scripts/<x>.py`（Issue #1021 以降、指示文は Skill ディレクトリ相対で書き、エージェントがリポジトリルートから綴り直して実行する）というリポジトリルート相対であり、cwd への同じ仮定を同じコマンドラインの 1 語手前で既に置いている。`wikicommit-ask` の `resolve_source_cache_path.py` は実際に `sys.path` 経由で import している。複製自体は残してある — 誤った理由を正すことと、それに基づいて書かれたコードを書き換えることは別の判断である。`docs/DesignDoc-skills.md` §11.5 冒頭のコールアウト参照）、`review-issue-close-sync.yml` のマーカー解決ロジック、`wikicommit-merge`/`wikicommit-review` SKILL.md のトラッキングIssueマーカー照合手順。新しい消費箇所を追加する際はこの一覧に加えること。

### 3.2 WikiCommit 開発リポジトリ

WikiCommit 自体の開発には Claude Code を使用する。Skills は `.claude/skills/` に置き、Claude Code が直接読み込むため、別途 `skills/` ディレクトリは作らない。`.claude/skills/` が Skills の正本であり、`install.sh` もここからコピーする。

```
wikicommit/
├── .gitignore
├── .devcontainer/
├── .github/
│   └── workflows/
│       └── test.yml            # pytest を CI で実行
├── .claude/
│   └── skills/                 # Skills の正本（Claude Code が直接読み込む）
│       ├── wikicommit-init/
│       ├── wikicommit-generate/
│       └── ...（他 Skill）
├── LICENSE
├── CONTRIBUTING.md
├── pyproject.toml              # Python 依存（.wikicommit/scripts/ 用）
├── package.json                # Node.js 依存（markdownlint-cli2 のみ。wikicommit-merge の品質ゲートが使用）
├── docs/                       # 設計ドキュメント（DesignDoc-*.md）
├── issues/                     # Phase 別 Issue ドラフト
└── install.sh                  # Skills インストールスクリプト
```

wikicommit-dev2（このリポジトリ自身）は private のため GitHub Pages を有効化できず、Quartz 自己公開設定一式（`quartz.config.yaml`・`.github/workflows/deploy.yml`・`quartz/` submodule・`quartz-plugins/`）は Issue #81 でルートから削除済み。配布用テンプレート（`.claude/skills/wikicommit-init/scripts/templates/`）には影響しないため、`/wikicommit-init --quartz` は引き続きユーザーの wiki リポジトリに対して正しく動作する。**このリポジトリ自身に対して `/wikicommit-init --quartz` を再実行しないこと** — `init.py` の既存ファイルスキップ判定はファイルの存在有無のみを見るため、削除済みの上記ファイルは無条件に復元されてしまう。

### 3.3 `.wikicommit/config.yml` の構造

```yaml
wikicommit_version: "0.1.0"     # このリポジトリを最後に同期した WikiCommit の版（Issue #577・#713）。
                                 # /wikicommit-init が初回に刻印し、以後は /wikicommit-update が
                                 # 同期のたびに書き換える。copier の .copier-answers.yml に相当し、
                                 # 差分検知・配布物更新・ページ再生成の起点になる。
                                 # ユーザーが手で書き換えるフィールドではない

translation:
  targets: []                   # 翻訳対象言語。/wikicommit-init では対話的に聞かない（常に空配列で生成される）。
                                 # 翻訳を使う場合は手動で config.yml を編集する（Phase 3〜: /wikicommit-translate で対話実行、
                                 # Phase 4〜: main マージ起点の無人実行にも同じ値を使う）
  primary_lang: en              # 原文言語。WikiLink クロス言語フォールバックの基準。デフォルトは en。
                                 # 日本語 Wiki を作りたい場合は /wikicommit-init の対話プロンプトで明示的に ja と答える

theme: ""                        # Wiki のテーマ（＝内容スコープ）を自由記述する任意フィールド（Phase 2〜）。
                                  # 空文字列の場合は wikicommit-generate のテーマ判定は無効（全エンティティを従来通り生成）。
                                  # 「何についての Wiki か」を書く。「どんなソースを取り込むか」は別の問いであり
                                  # .wikicommit/source-policy.md に書く（§3.4・Issue #564）。
                                  # 例: "社内エンジニア組織の技術ナレッジベース。個人のブログ的な話題は対象外。"

site_description: {}             # 読者に見せるこの Wiki の紹介文（Issue #671）。言語コード → 1〜3 文の文字列。
                                  # theme とは宛先が違う（あちらは LLM・こちらは読者）ため同期規約は置かない。
                                  # /wikicommit-init はキー自体を配らず、コメントアウトした記入例のみ置く。
                                  # 例:
                                  #   site_description:
                                  #     it: "Una base di conoscenza dedicata al Decameron."
                                  #     ja: "『デカメロン』の知識ベース。"

generate:
  max_retries: 2                # ページ生成失敗時の最大再試行回数

schema:
  base_types: [Person, Place, Organization, Event, HowTo, DefinedTerm, ScholarlyArticle, NewsArticle, BlogPosting, ShortStory, Book]
```

> **`review:` ブロックを削除した（Issue #669）**: `review.auto_merge` と `review.chain_of_thought` はどちらも**消費者が 1 つも存在しない**フィールドだった。`.claude/skills/*/SKILL.md` と `.wikicommit/scripts/*.py` を grep しても値を読む箇所は無く、`auto_merge` で当たるのは GitHub 側のリポジトリ設定 `allow_auto_merge`（Issue #456）という名前が似ているだけの別物だけである。両キーとも Phase 1 の初期設計から据え置かれ、実装が追いついていなかった。両方を消した結果 `review:` ブロックは空になるため、ブロックごと削除した（値なしの `review:` は YAML の null になる）。
>
> **実害は「読まれない設定がある」ことではなく、読まれると誤解されることにある**。Issue #667 の出発点となった相談は「`Person` 型だけ `auto_merge: false` にすれば自動マージが止まる」という前提から始まったが、型別分岐以前にグローバルなゲート自体が存在しないため成立しなかった（§3.5）。実際のマージ条件は `docs/DesignDoc-pipeline.md` §7 の表どおり「経路 A: 品質チェック全 blocking PASS」だけで、設定による分岐点はどこにも無い。Issue #553 が `inDefinedTermSet` について、Issue #564 が `license_map` について確立した「消費者と同時にキーを足す・受け皿だけ先に配らない」という規範の、既存フィールド側での違反にあたる。
>
> **`auto_merge` を実装せず削除した理由**: マージを設定で止める機能は、信頼ラダー（`pending` でも main にマージして公開しバナーを出す 2 値設計。`docs/DesignDoc-publish.md` §8.4）に第 3 の状態を持ち込む。`review_status` の 2 値・レビュー追跡 Issue・`review-issue-close-sync.yml` の全部に分岐が要るため、必要になった時点で独立に設計すべきものであり、名前だけ先に取っておく理由が無い。「作らない」側で止める経路は `.wikicommit/entity-policy.md`（Issue #667。§3.5）が別途用意している。
>
> **`chain_of_thought` も実装せず削除した**（Issue #669 が実装時の判断に委ねた分岐）。意図された機能自体は明確だったが、3 つの理由で削除を採った。(1) **効果を測る手段がこのリポジトリに無い** — レビュー品質の eval 基盤が存在しないため、有効にして良くなったかを誰も判定できない一方、コスト増（1 レビューあたりのトークン）は確実に発生する。受け皿だけ配ることを禁じる規範を、測れない受け皿を実装することで満たしても意味がない。(2) **「LLM レビュー」は 1 箇所ではない** — `wikicommit-generate` Pass 4・`wikicommit-synthesize` Step 5.5・`wikicommit-translate` の翻訳品質チェック・`wikicommit-review` の 4 経路があり、1 つのフラグを配線するにはそれぞれに「ここでの CoT とは何か」を書き足すことになる。SKILL.md は Skill 起動のたび全文がコンテキストに載る（`docs/DesignDoc-skills.md` §11.9）ため、測れない利得に対して指示面積の代償が大きい。(3) 削除は不可逆ではない — 意図は本コールアウトに残るので、必要になった時点で測定手段とセットで再設計できる。
>
> **既存リポジトリの `config.yml` は書き換えない**。`init.py` は `--no-overwrite` 時に `config.yml` を wholesale でスキップするため（下記 `wikicommit_version` の扱いと同じ）、既に配布済みのリポジトリにはキーが残り続ける。誰も読まない値なので害は無く、遡及移行はしない（本ドキュメント群が一貫して採る「新旧混在を許容する」方針）。

<!-- -->

> **`wikicommit_version` の刻印（Issue #577）**: WikiCommit 自身の版は 2 箇所を source of truth とする — `.claude/skills/wikicommit-init/scripts/templates/scripts/_version.py`（`init.py` が `.wikicommit/scripts/_version.py` として展開するため、**インストール先の wiki リポジトリまで届く唯一の情報源**）と `.claude-plugin/plugin.json` の `version`（Claude Code の plugin 機構が読む。配布リポジトリのルートに置かれるため、インストール先には届かない）。両者の同期は `tests/test_version_sync.py` が CI で強制する（`install.sh` と `plugin.json` の配布リスト同期〈Issue #372〉と同じ、生成スクリプト化ではなく内容一致を強制する軽量パターン）。
>
> `git tag` を版の担い手にしない理由は 3 層構造（開発リポジトリ → `git archive` による配布リポジトリ → ユーザーの wiki リポジトリ）にある: 配布リポジトリは開発履歴を引き継がない単一コミットの積み重ねであるため、タグは配布側に別途手で打つ必要があり、開発側の版と独立に管理することになる（片方だけ更新するズレが構造的に起こりうる）。一方 `plugin.json` は `git archive` のホワイトリストに含まれており、開発リポジトリで編集すれば配布側へ自動的に運ばれる。Claude Code の版フォールバック順序（`plugin.json` → marketplace エントリ → git tag → commit SHA）でも `plugin.json` が最優先でありタグは参照すらされないため、`plugin.json` に一本化すればタグは不要になる。
>
> `pyproject.toml` の `version` とは無関係の別物（あちらは開発リポジトリ自身の Python パッケージ宣言。**Issue #788 以降は公開もされている** — `tests/` を動かすのに要るため）。揃え続ける規約は置かない。理由は 3 つで、いずれも版が動いても成り立つ: `packages = []` であり配布される Python パッケージではない、`version` の消費者がリポジトリに 1 つも無い（`importlib.metadata` / `pkg_resources` / `tomllib` のいずれも grep で 0 件）、そして版を上げる契機（型テンプレート・ページ生成ルールの変更）とあのファイルが宣言するもの（テスト・lint の依存）が無関係である。
>
> **そして実際に乖離した。** `pyproject.toml` は `0.1.0` のまま、`_version.py` / `plugin.json` は `0.4.0` へ進んでいる（2026-09-09 時点）。**これは直すべきドリフトではなく、上の決定が想定どおりに働いた結果である** — この節はかつて「現時点でたまたま同じ `0.1.0` だが」と書いており、同じ理由づけが `_version.py` と `tests/test_version_sync.py` にもあったが、一致が消えた時点でその 3 箇所は前半が偽・後半だけが残る形になっていた（Issue #799）。乖離が現実になった後でも成り立つ上の 3 つの理由に書き直してある。あわせて `pyproject.toml` 自身にも同じ趣旨のコメントを置いた — 矛盾に当たる場所（ルート直下の短いファイルの 2〜3 行目が `CHANGELOG.md` の `## [0.4.0]` の隣に並ぶ）と、説明のある場所が一致していないことが、この Issue が起票された経緯そのものだったため。
>
> **既存リポジトリへの遡及付与は行わない**。`init.py` は `--no-overwrite` 時に `config.yml` を wholesale でスキップするため、既に init 済みのリポジトリには刻印されない。本ドキュメント群で繰り返し採られている「新旧混在を許容する」方針に従い、`wikicommit_version` の欠如は「この機能追加より前に作られた」ことを意味するものとして扱う。
>
> **意味を「初期化した版」から「最後に同期した版」へ再定義した（Issue #713）**: Issue #577 はこのフィールドを「差分検知・配布物更新・ページ再生成の起点」と位置づけながら、書き手を初回 init だけに限っていた。再 init は `config.yml` を wholesale でスキップするため値は初回で固まる一方、`_version.py` は再 init のたびに上書きされて消える。結果として、**「前回どこから来たか」を保持する主体がどこにも存在しなかった** — `/wikicommit-update` は「今回何が変わったか」を `CHANGELOG.md` から切り出せず、全履歴を見せるか何も見せないかの二択になる。
>
> 現在は `/wikicommit-update` が同期の完了時にこれを書き換える（`init.py --update-version`。`--update-theme` と同じ、その行だけをテキストレベルで書き換える経路）。**書き換えは YAML の round-trip では行わない** — `config.yml` はコメントアウトした記入例を同梱しており（`site_description` の言語別の例のように、キー自体を配らずコメントだけで形を示すものがある。Issue #671）、`yaml.safe_load` + `yaml.dump` はそれを全部落とす。まだ埋めていないフィールドの唯一の説明書きが、更新のたびに黙って消えることになる。
>
> **失われる「初期化した版」に消費者はいない**。値を読む箇所は grep しても無く、必要なら `git log --diff-filter=A -- .wikicommit/config.yml` で追える。むしろ再定義後の方が git に残る情報は増える — フィールドは値を 1 つしか持てないが、履歴には同期の連鎖と日付が全部残る（CLAUDE.md の GitOps テーゼ「すべての状態変化をコミットとして記録し、監査は `git log` で完結する」とも整合する）。
>
> **`wikicommit_synced_with` を別に新設して 2 つ並べる案は採らなかった**。値がほぼ常に一致する版フィールドが 2 つあると、どちらを読むべきかが実装ごとに割れる。実際に 2 つが食い違うのは「一度も update していないリポジトリ」だけで、それは新定義でも欠如または古い値として表現できる。
>
> **遡及適用は行わない**（上記と同じ）。`wikicommit_version` を持たないリポジトリは、最初の `/wikicommit-update` で初めて刻印される。
>
> **`.wikicommit/scripts/` は再 init で必ず更新される — `config.yml` とは求める挙動が逆である（Issue #647）**: 上の「遡及付与は行わない」は `config.yml` の `wikicommit_version`（＝そのリポジトリが初期化された版）についての話であり、ページの `generated_with` / `translated_with`（＝そのページが生成された版）には当てはまらない。前者は更新されないことが正しく、後者は更新されなければ**誤る**。
>
> ところが両者の値は同じ `_version.py` から読まれ、そのファイルは `init.py` の `copy_tree` が `--no-overwrite` に従って丸ごとスキップする位置にあった。`/wikicommit-init` は既存リポジトリに対して常に `--no-overwrite` を付けて実行される（`wikicommit-init` SKILL.md の処理フロー 1）ため、**新しい版の Skills をインストールして再 init しても `.wikicommit/scripts/_version.py` は初回 init の版のまま残り**、新しい Skills が生成したページに古い版が刻印されていた。刻印が無いこと（Issue #577 が「この機能追加より前に作られた」と定義した状態）は無害だが、誤った刻印は `generated_with` の唯一の用途 — `CHANGELOG.md` と `grep` を突き合わせて再生成すべきページを人間が選ぶこと — に対して能動的に誤った答えを返す。
>
> **採った案**: Issue #647 の案 1（`--no-overwrite` の例外扱い）を、1 ファイルではなく **`.wikicommit/scripts/` ツリー全体**に適用した。`copy_file()` / `copy_tree()` に `always_overwrite` を追加し、スクリプトツリーのコピーのみがこれを渡す。`--no-overwrite` が守るべき対象はユーザーが書いたもの（`config.yml`・`schema/`・`entity/` のページ・ルート直下の設定ファイル）であり、`.wikicommit/scripts/` は Skills が呼ぶ共通の品質ゲートスクリプト＝配布物である、という所有権の線引きに従う（Issue #577 が「配布物の更新」の後続論点として記録していた分岐の、最初の具体例）。`always_skip_existing`（ユーザーのファイルを絶対に壊さない）とはちょうど同じ軸の反対端であり、両者を同時に渡す呼び出しは存在しないが、万一渡された場合は `always_skip_existing` を優先する（保護側を強い規則として残す）。
>
> **`_version.py` 1 ファイルだけを例外にしなかった理由**は Issue #647 自身が挙げている — 版だけが新しくスクリプトは古い、という別種の不整合になる（版が、実体を伴わない更新を主張する）。ツリー全体を更新すればこの矛盾は生じない。ただし `copy_tree` は削除を行わないため、上流でリネームされたスクリプトの旧ファイルは孤児として残り続ける（Issue #583）— 「更新される」ことは「完全なミラーになる」ことを意味しない。
>
> **残る歪み: `.wikicommit/schema/` は refresh されないため、版が型テンプレートより先に進む**。上の「1 ファイルだけを例外にしない」理由（版だけが、実体を伴わない更新を主張する）は、同じく配布物でありながら `--no-overwrite` で保護し続ける `.wikicommit/schema/` にもそのまま当てはまる — しかも本ファイル冒頭の `CHANGELOG.md` の規約が「型テンプレートを変更した版では、どの型をどう変更したかを必ず書く」としているとおり、型テンプレートの変更こそが版を上げる主な理由である。型テンプレートだけを変更した版へ更新して再 init すると、`_version.py` は新しい版を返す一方 `.wikicommit/schema/<Type>.md` は旧版のままであり、その後に生成されたページは**旧テンプレートで作られたにもかかわらず `generated_with: <新版>` を持つ** — `grep` で旧版のページを列挙する運用からは漏れる（Issue #647 が消した誤りと同じ種類の誤りが、向きを変えて残る）。それでもスキーマファイルを上書きしないのは、そこが人間の直接編集を許す唯一の領域（§5.2 の `provenance: manual`）であり、refresh は保護すべきユーザーの判断を消すからである。**したがって型テンプレートを変更した版へ上げたときは、再 init だけでなく `.wikicommit/schema/` の差分を人間が取り込む必要がある** — 配布物の更新一般（インストール済み Skills の版と刻印の比較を含む）は下記のとおり別 Issue のスコープであり、ここではその最初の具体例として歪みの所在だけを記録する。
>
> **採らなかった案（Issue #647 の案 2 — 版の読み取り元を Skill ディレクトリ内へ移す）**: `init.py` が `config.yml` の `wikicommit_version` を刻印する時点でインストール先に届く情報源が必要であるという、`_version.py` を templates 配下に置いた理由（上記）と正面から衝突する。両方に置いて CI で同期を強制する形もありうるが、同期対象が現在の 2 箇所（`_version.py`・`plugin.json`）から 3 箇所に増える一方、案 1 で解決済みの問題を解き直すだけで得るものがない。
>
> **差分の検知（インストール済み Skills の版と刻印の比較）・配布物の更新・スキーマ変更に伴うページ再生成は本フィールドのスコープ外**であり、それぞれ別 Issue とする。`CHANGELOG.md`（Issue #577 で新設。`git archive` のホワイトリストにも追加済み）が、配布リポジトリの `git log` が情報を持たない以上、利用者への唯一の変更伝達手段になる。
>
> **再 init で何が更新され何が守られるかは `_root_outputs.py` の `update` 列が決める（Issue #712）**: 上のコールアウトが `.wikicommit/scripts/` について引いた所有権の線引き（WikiCommit 自身の配布ペイロードであってユーザーが書いたものではない）は、同じ論法がそのまま当てはまる他の配布物にも広げられた。線引きの結果は `update` 列として宣言的に記録され、`init.py` はそこからコピーのフラグを導く（`overwrite` → `always_overwrite=True`、`review` / `skip` → `always_skip_existing=True`）。したがって**「`always_overwrite` は `.wikicommit/scripts/` だけ」という上の記述は、この Issue 以降は当てはまらない**。
>
> | `update` | 対象 | 再 init の挙動 |
> |---|---|---|
> | `overwrite` | `.wikicommit/scripts/`・`.wikicommit/review-rules.md`・`.wikicommit/schema-authoring.md`・`.wikicommit/guides/`・`quartz-plugins/`・`deploy.yml`・`review-issue-close-sync.yml`・`prebuild-symlinks.cjs`・`repair-plugin-builds.cjs`・`install-local-plugins.cjs` | `--no-overwrite` の有無に関わらず更新される |
> | `review` | `config.yml`・`quartz.config.yaml`・`schema/`・`package.json`・`.lychee.toml`・`.markdownlint.json`・`.gitignore`・`report.md`・ポリシーファイル 2 つ | 既存ファイルには一切触れない |
> | `skip` | `entity/`・`view/`・`source/`・`.claude/`・`quartz/`・`.gitmodules`・`package-lock.json`・`schemaorg-vocab.json`・`README.md`（無いときだけ作る。Issue #1034） | 同上（かつ差分報告の対象外） |
>
> **副次的に、`--no-overwrite` にしか守られていなかった 2 つの穴が構造的に塞がった**。`config.yml`（`theme`・`targets` を持つ）と `schema/`（人間の直接編集を許す唯一の領域）はフラグを 1 つも持っておらず、`--no-overwrite` を落とすとどちらも上書きされていた — パイロットの更新手順書が太字で「このフラグだけが唯一の防護である」と警告し、外すと `theme` が消えることを実測付きで記録していたのはこのためである。両者に `review` を割り当てた結果、フラグの有無に関わらず守られる。
>
> **`review` と `skip` は init の挙動としては同一**で、違うのは `check_distribution_freshness.py`（`docs/DesignDoc-ScriptSpec.md`）が差分を報告するかどうかだけである。ポリシーファイル 2 つを `skip` ではなく `review` にしたのは、本文（散文の方針）が完全にユーザーのものである一方 **frontmatter のキーは上流で増える**ため — Issue #570 は `source-policy.md` のテンプレートに `index_only:` を足し、それを読む処理を `/wikicommit-collect` に同時に入れたが、それ以前に init したリポジトリにはこのキーが無く、`skip` にすると差分検出もそれを報告しないので、**消費者だけが入って受け皿が来ない**（Issue #553 が禁じた形の裏返しが更新経路の側で起こる）。
>
> **孤児は残り続ける**。`copy_tree` は削除を行わないため、上流でリネームされたスクリプトの旧名は `overwrite` のツリーでも残る（Issue #583）— 「更新される」ことは「完全なミラーになる」ことを意味しない。`check_distribution_freshness.py` が `ORPHAN:` として報告するに留め、削除は人間が行う。
>
> **`.wikicommit/schema/` は引き続き refresh されない**（`review`）ため、上の「残る歪み」— 型テンプレートだけを変更した版へ上げると版だけが先に進む — はそのまま残る。ただし差分自体は `check_distribution_freshness.py` がバイト比較で報告するようになったので、**取り込むべき差分がある**ことは分かる。取り込むかどうかは、そこが人間の直接編集を許す唯一の領域である以上、引き続き人間の判断である。
>
> **既存リポジトリへの遡及適用は行わない**（本ドキュメント群が繰り返し採る「新旧混在を許容する」方針）。変更が届くのは次に `/wikicommit-init` を実行したリポジトリからである。

`theme` は `/wikicommit-init` 実行時に対話的に設定する（空 Enter でスキップ可）。単体では何もしないフィールドで、`wikicommit-generate` のテーマ判定チェックポリシー（§4.3・`DesignDoc-pipeline.md` §6.1）が読み取って利用する。**役割は内容スコープに限る**（Issue #564。§3.4 参照）。さらに `theme` が答えるのは**関連性**（この Wiki の主題と関係があるか）に限られ、**許容性**（関係があっても書いてよいか）は `.wikicommit/entity-policy.md` が持つ（Issue #667。§3.5 参照）。同じ Pass 2c が両方を読み同じ `action: exclude` を出すが、軸が独立しているため一方が他方を代替しない — 主題のど真ん中にいる存命の人物は関連性が最大でもなお除外したいことがある。

> **`theme` は LLM 向けの内部フィールドであり、読者向けの表示には使わない（Issue #670）**: 読む主体は `wikicommit-generate` Pass 2c と `wikicommit-collect` に限られる。公開サイトのトップページはかつてこの値を「テーマ:」の 1 行として描画していた（Issue #407）が、廃止した — 値は 1 本しかないため書かれた言語のまま全読者に届き、多言語 Wiki では大半の読者に読めない。しかも実際の値には、Issue #564 が `.wikicommit/source-policy.md` へ分離したはずのソース選定方針が混在しがちで、生成器への命令文がそのままトップページに出ていた。多言語化して読者に見せ続ける案は採らない（LLM 側の消費者は 1 本あれば足りる一方、読者向けに書かれていない文を訳す作業になる）。**読者向けのサイト説明が必要なら、読者向けに書かれた別のフィールドとして持つ** — `theme` を流用しない。詳細は `docs/DesignDoc-publish.md` §8.8 参照。

<!-- -->

> **`site_description` — 読者向けのサイト説明（Issue #671）**: 上の `theme` が「読者向けに書かれた別のフィールドとして持つ」と述べたもの。値は**言語コード → 1〜3 文の文字列**のマッピングで、公開サイトのトップページで各言語のリンクの直下に 1 行ずつ描画される（`docs/DesignDoc-publish.md` §8.8）。
>
> **`theme` との違いは宛先である**。`theme` は LLM に内容スコープを伝えるもので 1 本あれば足り、命令形でも構わない。`site_description` は読者に読ませるものなので、**読者の言語ごとに 1 本ずつ**必要で、読める文章でなければならない。Issue #564 が「何についての Wiki か」と「どんなソースを取り込むか」を分離したのと同型の分離であり、**同期させる規約は置かない** — 片方から他方を導出する規約を置けば、Issue #564 が解いた混在に戻る。両方が空でも動く。
>
> **別ファイルにしない理由**は §3.4 が `source-policy.md` について挙げた基準の裏返しである。あちらを独立ファイルにしたのは「中身の大半が散文であり YAML の値として持つには収まりが悪い」ためだが、こちらの値は言語ごと 1〜3 文の短い文字列で、しかも**機械が言語キーで引く**（散文からは引けない）。同じ基準に従えば `config.yml` 側になる。
>
> **人間が書く**。`/wikicommit-init` に対話プロンプトは追加しない（Issue #404 が「何も提案されないためだけの追加ステップ」を嫌ったのと同じ判断で、1 問増やすだけの導入コストに見合わない）。**init が何問聞くかは理由にならない** — Issue #837 は同じ init に 2 問目（`exclude_living_persons`）を足しており、問い数ではなく §3.5 が立てた基準で分かれる: **既定値を持ち無言で作用しどちらの向きにも巻き戻せないスイッチ**は聞かなければ値が決定にならない一方、`site_description` は空でも動き、後から書けば次のビルドで効き、書かなかったことが取り返しのつかない結果を生まない。テンプレートはコメントアウトした記入例のみを置き、**キー自体は配らない**（Issue #553 の「受け皿だけ先に配らない」。消費者は同じ Issue で同時に入っている）。LLM に翻訳させる経路も作らない — `config.yml` は Skill の書き込み対象ではなく、読者に見せる紹介文をどう書くかは人間の判断に属する。
>
> **既存リポジトリへの遡及付与は行わない**（新旧混在を許容する慣例）。フィールドの欠如は「この機能追加より前に作られた」ことを意味し、出力は従来どおりになる。値が壊れている場合（マッピングでない・値が文字列でない）も同様に落として無効扱いとする。値の内部の改行・連続空白は単一の空白に潰す — 公開時は言語ごとの箇条書き 1 行に埋め込まれるため、値が持つ空行は言語選択リストそのものを分断する。

<!-- -->

> **`theme` 駆動の Schema.org 標準型提案ステップは廃止済み（Issue #404。旧 Issue #286 の巻き戻し）→ より保守的な形で限定復活（Issue #490）**: `theme` に非空文字列を入力した場合、`wikicommit-init` は以前、続けて軽量な Schema.org 標準型の提案ステップを実行していた（Issue #286）。`check_schema_org_type.py --list-type-names`（Issue #285。当初は `--list-types` で説明文も併せて取得していたが、Issue #798 で型名の一覧と候補型の説明文〈`--describe`〉の 2 段階に分けた）で取得した Schema.org 型名一覧を `theme` の一文と照らし、基本6型（Person/Place/Organization/Event/HowTo/DefinedTerm）以外に有用そうな標準型があれば Enter ベースで承認/スキップを確認し、承認された型のみ `.wikicommit/schema/<Type>.md` を新規追加する仕組みだった。しかし `theme` 一文だけを根拠とする低確信度の提案であり、0件提案（何も提案しない）が設計上の想定される通常の結果だったため、大半のケースで「何も提案されないためだけの追加ステップ」が `wikicommit-init` フローに挟まっていた。同じ型提案の機能は、実際のソース文書を根拠にその場で判断する `wikicommit-generate` Pass 2b（Issue #315。`docs/DesignDoc-data.md` §5.4・`docs/DesignDoc-skills.md` §11.6）としてより高精度な形で既に存在していたため、`wikicommit-init` 側のステップを削除し型提案を Pass 2b に一本化した。
>
> しかし `dev/pilot-ai-driven-dev-wiki-round3.md` の実行で、`/wikicommit-collect` を経由せず `/wikicommit-generate <url>` で直接ソース登録する運用（CLAUDE.md の主経路）では型提案の「入口」自体が存在せず、型の不足が Pass 2b まで気づかれず、しかも非対話実行（サブエージェント経由）だと Enter 確認が取れずデフォルト却下されて消えてしまうことが判明した（この非対話デフォルト却下自体は、後に Issue #507 が Pass 2b 自身に踏み込んで部分的に解消した — §5.4 の該当コールアウト参照）。そこで Issue #490 は、旧 Issue #286 よりさらに保守的な判定基準（「theme 文から自信を持って断定できる場合のみ」提案する。例: 「AI駆動開発ツールのナレッジベース」というテーマであれば `schema:SoftwareApplication` が必要になることは theme 文だけからでも断定できる）に限定した上でこのステップを復活させた。旧実装との相違点は判定バーの厳格さのみで、仕組み自体（`check_schema_org_type.py` による検証・Enter ベース承認・追加のみ可の書き込み例外）は同一。
>
> 3つの型提案経路（`wikicommit-init` の obvious-type judgment・`wikicommit-collect` の Type Proposal ステップ〈Issue #489〉・`wikicommit-generate` Pass 2b〈Issue #315〉）の役割分担は、証拠の強さと実行タイミングの違いによる: `wikicommit-init` は theme 文一文のみ・ソース登録前という最も弱い証拠しか持たないため判定バーを最も厳格にする一方、`/wikicommit-generate <path|url>` による直接登録という主経路の最初の一手として機能する。`wikicommit-collect` は複数の候補タイトル・Web検索要約という中間的な証拠を持ち、候補提示ステップが元々対話的であるため非対話バッチ実行特有の問題が構造的に起こらない。`wikicommit-generate` Pass 2b は実際のソース文書全文という最も強い証拠を持ち、引き続き主経路・最高精度の判定を担う（Issue #507 以降は非対話実行時にも独自の自動承認経路を持つ — 対話実行前提の他2経路とはこの点で異なる。§5.4 の該当コールアウト参照）。3経路とも「`.wikicommit/schema/` に既にファイルがある型は提案しない」という同一のスキップ判定を共有するため、互いに排他的な設計を必要としない。`wikicommit-schema-propose`（事後検出、Issue #285）はいずれの経路からも漏れたケースの安全網として引き続き存続する。
>
> **分かれているのは判定だけで、書き込み手順は 1 本である（Issue #886）**: 上の役割分担が正当化しているのは**判定**（提案の閾値・実行タイミング・承認 UX・`provenance` に刻む値）であり、`.wikicommit/schema/<Type>.md` を実際に書く手順が 4 経路に複製されていることは何も説明していなかった。実測 20,031 B が 4 本あり、Issue #649 の `granularity` の YAML 文字列規律は 4 箇所へ同じ段落を足す形で対応されていた。現在は `.wikicommit/schema-authoring.md`（`_root_outputs.py` の `update: overwrite`。`review-rules.md` と同形）が手順を持ち、4 経路はそれを読んで自分の `provenance` を渡す。**譲れない 3 点**（property を `check_schema_org_type.py` で検証する・`granularity` に `Boundary —` を 1 本入れる・`provenance` は自分の値を刻む）だけは各サイトに 1 行ずつ残してあり、共有ファイルの Read を飛ばした場合の劣化を「指針が薄い」で止める。ファイルが無い場合は**その候補だけを却下して報告し、実行は止めない** — `review-rules.md` が全実行に到達するのに対し、こちらは型を実際に足すときにしか到達せず、ゼロ件が通常の結果であるため（詳細は `docs/DesignDoc-skills.md` §11.5）。

<!-- -->

> **`targets` の手動設定について（Issue #190 → #280 で状況解消）**: Issue #190 時点では翻訳パイプライン（`DesignDoc-pipeline.md` §6.4）が Phase 4 実装のみで、Phase 1–3 の `wikicommit-generate` には翻訳ステップ自体が存在せず、`targets` を手動設定してもそのページが生成されることはなかった。この状態で `targets: [en, zh]` のように手動設定すると、`convert_wikilinks.py` の `generate_root_index()` がルート `content/index.md` に存在しない言語への言語選択リンクを出力し、公開Wikiにデッドリンクができる問題があった（`coffee-knowledge-wiki` パイロットで実際に確認）。この問題自体は `convert_wikilinks.py` に追加した `existing_lang_targets()`（実ページが1件も存在しない `target` をリンク生成対象から自動的に除外する）で恒久対応済みだったが、そもそも翻訳を生成する手段が Phase 3 に無いことが「手動設定しない」という運用上の推奨につながっていた。Issue #280 で対話実行の `/wikicommit-translate` Skill を追加したことにより、`targets` を設定すればそのとおりに翻訳ページが生成されるようになったため、この推奨は解消した。Phase 3 の間も `targets` を手動設定してよい（`/wikicommit-translate` を実行するまでの間は `existing_lang_targets()` によるデッドリンク自動除外が引き続き安全弁として機能する）。

### 3.4 `.wikicommit/source-policy.md`（ソース選定方針。Issue #564）

「**どんなソースを取り込むか**」を書くファイル。`config.yml` の `theme`（「何についての Wiki か」＝ 取り込み済みのソースからどのエンティティをページ化するか）とは別の問いに答える。

**このファイルが無かったこと自体が実害を生んでいた**。`dev/pilot-saitama-wiki.md` がデプロイした `config.yml` の `theme` は、性質の異なる 2 つを 1 文に混ぜていた — 前半が内容スコープ（「10 区の地理・歴史…を中心に扱う」）、後半がソース方針（「一次資料として…を優先し、個人ブログ・商業的な観光広告…は対象外とする」）。手順書作成時の判断ミスではなく、**他に書く場所が無かった**ためである。そして押し込んだ結果、後半は主経路では一切機能していなかった:

| `theme` の消費者 | 用途 | ソース方針は効くか |
|---|---|---|
| `wikicommit-collect` Step 4–6 | 候補ソースの関連性判断 | 効く。ただし collect は任意経路 |
| `wikicommit-generate` Pass 2c | **エンティティ単位**の `action: exclude` 判定 | **効かない**（ソースは既に取り込み済み） |
| `wikicommit-init` | theme 駆動の型提案（Issue #490） | 無関係 |

CLAUDE.md が主経路とする `/wikicommit-generate <path|url>` の直接実行では、ソース方針を読む主体がどこにも存在しなかった。さらに Pass 2c のエンティティ判定には後半が丸ごとノイズとして混入していた（「個人ブログは対象外」という文が、抽出済みエンティティを除外するかの判断に流れ込む）。

#### フォーマット

`.wikicommit/schema/*.md` と同じ形式（機械可読なフロントマター + 散文の指示）を採る。スキーマファイルの設計思想（§5.1 —「LLM 指示書と品質ゲート仕様書を兼ねる」・ディレクトリに置くだけで有効になる Convention over Configuration）がそのまま当てはまるため。`config.yml` へのフィールド追加としなかったのは、中身の大半が散文であり、YAML の値として持つには収まりが悪いからである。

```markdown
---
wikicommit:
  exclude_domains: []   # このWikiが取り込まないと決めたドメイン
  rejected: []          # 検討して却下したソース（url / reason / date〈任意〉）
---

一次資料（行政の公式サイト・オープンデータ・査読論文）を優先する。
個人ブログ・商業的な広告・特定店舗の宣伝は取り込まない。
対象全体の構造を述べる資料を最初に1件取り込み、以降はそこへの肉付けとして進める。
```

**フロントマターのキーに新しいスクリプトは要らない**。`exclude_domains` は既存の `check_extraction_quality.py check-domain` が読み、残りは Skill の指示ファイルとして読まれる。`wikicommit-init` が空のテンプレート（本文はコメントアウトした記入例のみ）を配布し、再実行しても上書きしない（`.lychee.toml`・`.markdownlint.json` と同じ `always_skip_existing`）。**ファイルが無い既存リポジトリは従来どおり動く**（本ドキュメント群で踏襲されている「新旧混在を許容する」慣例）— 本文が空・またはテンプレートの記入例のままなら散文方針は無いものとして扱う（空の `theme` がエンティティ判定を無効にするのと同じ）。**この判定は `read_policy.py` が決定論的に行う**（Issue #844。下記コールアウト）。

> **記入例と、利用者が書いた方針を機械が区別する（Issue #844）**: 上の「記入例のままなら無いものとして扱う」は、長らく **2 つの SKILL.md に散った 4 箇所の同じ散文**が担っており、いずれも「いま読んだ本文が配布時のコメントのままか」を LLM に判定させていた。**配布した本文は手元にあるのだから、判定するものは何も無い** — Issue #474 が名指しした「完全に決定論的に判定できる操作を instruction として表現する」形の再発である。
>
> **しかも誤りの向きが片側に寄っている**。両ファイルの記入例はすべて除外を促す内容（一次資料を優先する・個人ブログを取り込まない・非公人・実在の未成年者・係争中の事案・自組織の未公開情報）であり、誤適用は常に「書かれるはずだったものが書かれない」方向にしか働かない。しかも出力上は区別がつかない — `exclude_reason: privacy` の除外が 1 件出るか、候補が 1 件落ちるだけである。`wikicommit/saitama-city-wiki` が `theme` による除外だけで `Person` 型 0 ページになり歴史上の人物 3 名まで巻き込んだ実例（§3.5）は、まさにその方向にさらに効く。
>
> 現在は `read_policy.py`（`docs/DesignDoc-ScriptSpec.md`）が本文から記入例と HTML コメントを落として返し、3 つの読み手（`wikicommit-generate` Step 0 / 処理フロー冒頭、`wikicommit-collect` Step 2.5）はファイルを直接読む代わりにこれを呼ぶ。**フロントマターには触れない** — `exclude_domains` / `index_only` / `rejected` / `exclude_living_persons` はそれぞれの読み手が独立に読む。スクリプトが決定論的な部分を、LLM が散文の解釈を担うという分担は `check_extraction_quality.py` と同じで、`docs/DesignDoc-skills.md` §11.5 のスクリプト委譲パターンそのものである。
>
> **判定規則は「HTML コメントは方針ではない」であり、どの版が配布したかに依存しない**。両テンプレートは記入例をコメントに入れ、本文自身が「自分の方針を書いたらこれを消せ」と指示しており、人が書く方針は普通の散文である。**したがって既存リポジトリへの移行は要らない** — そちらの本文もコメントである（両ポリシーファイルは `always_skip_existing` なので再 init でも上書きされず、マーカーは届かないが、規則がマーカーに依存しないため問題にならない）。
>
> `<!-- wikicommit:example ... -->` のマーカーは、コメント除去だけでも結果は同じだが 2 つのことをする: 「これは WikiCommit のものであって利用者のものではない」を grep 可能にし、**名指しする価値のある 1 ケースを名指しする** — 本文に内容があったのにコメント除去で全部消えた場合を「空」ではなく「全部コメントの中にある」と報告する。そこへ至る最もありそうな経路は**記入例を `<!--` を消さずにその場で書き換えた**ことであり、黙って無視される方針はこの変更が消そうとしている失敗そのものだからである。**フロントマターに `template_untouched: true` を置く案は採らなかった** — 消し忘れると自分で書いた方針が黙って無効になり、誤りの向きが現状と同じ側に倒れる。
>
> **量の削減が目的ではない**。実測では `config.yml` + 両ポリシーファイルで約 2.5K トークンであり、`/wikicommit-generate` の固定オーバーヘッド約 51K の 5%、その 51K の 92% は同 Skill の SKILL.md 自身である。次に削るべきはそちらであってここではない。`config.yml` を同じ器に乗せる案も採らない（コメントは人間向けであり、方針として誤適用されうる散文ではないので同じ欠陥を持たない。Issue #713 が意図的に守っている資産でもある）。

#### 消費者

| キー / 部位 | 読む主体 | 何をするか |
|---|---|---|
| 本文（散文） | `wikicommit-generate` Step 0 | 登録前に、引数のソースが方針に明らかに反するなら**どの行と衝突するかを述べて確認を求める**（黙って登録しない・独断で拒否もしない） |
| 本文（散文） | `wikicommit-collect` Step 2.5 → 4/5/6 | 候補の常設フィルタ |
| `exclude_domains` | `check_extraction_quality.py check-domain` | 組み込みリストとの**和集合**（下記） |
| `exclude_domains` | `wikicommit-generate` Step 0 | 引数のホストが該当する場合、登録前に確認を求める（下記） |
| `rejected` | `wikicommit-collect` Step 2.5 → 5 | 該当 URL の候補を落とす |
| `rejected` | `wikicommit-generate` Step 0 | 引数の URL が該当する場合、その `reason` を引用して確認を求める |
| `index_only` | `wikicommit-collect` Step 5 / 5.5 | 該当するページ自身は候補にせず、リンクの列挙から一次資料を掘る。ページのエントリは自分から見に行く（下記。照合は `match_index_only.py`。Issue #1032） |
| `index_only` | `wikicommit-generate` Step 0 | 引数の URL が該当する場合、登録前に確認を求める（Issue #833。照合は `match_index_only.py`。Issue #1032） |

#### `exclude_domains` と `KNOWN_JS_SHELL_DOMAINS` の合成は和集合（完了条件）

スクリプト側の `KNOWN_JS_SHELL_DOMAINS`（Issue #425）は「静的フェッチで空シェルを返すことが確認済み」という**全リポジトリ共通の事実**を持つ。一方 `exclude_domains` は**そのリポジトリの決定**を持つ。両者を和集合とし、**リポジトリ側から組み込みリストを上書き（取得可能に戻す）ことはできない** — 設定で戻しても実際に取得できるようにはならないため。

ファイルが無い・読めない・フロントマターが壊れている・値がリストでない、のいずれも「追加ドメインなし」として扱う。ソース選定方針が、全 URL 取得の手前で走る抽出ガードを道連れに壊せてはならない。ただし**無言で fail-open してはならない** — `wikicommit-collect` がこのファイルの `rejected:` に追記する以上、追記ミス 1 回で `exclude_domains` 全体が無言で無効化されうるため、フロントマターのパースに失敗した場合は stderr に `WARNING:` を出す（stdout の `BLOCKED:`/`OK:` 契約は変えない）。

各エントリは `_domain_of()` と同じ形（スキーム・パス・ポート・先頭 `www.` を除去し小文字化）に正規化してから**完全一致**で比較する。正規化は、人間が同じフロントマター内の `rejected:` の `url:` に倣って `https://example.com/` と書いた場合に一致しない（＝ファイル上は除外されているのに取得され続ける）ことを防ぐためのもので、サブドメインまでは覆わない（`example.com` は `blog.example.com` に一致しない）— 組み込みリストが `music.youtube.com` を個別に持つのと同じく、意図するホストを列挙する。

**`exclude_domains` の一致を Pass 1 だけに任せない**。Pass 1 のブロックは `status: failed` + `## Failure Reason` を残し、さらに `wikicommit-merge` Step 9 が `wikicommit-generation-failure` の追跡 Issue を立てる — 静的取得が本当にできないドメインにはそれが正しい記録だが、「この Wiki が要らないと決めた」ドメインには誤った記録になる（要らないソースの管理ファイルが残り、直せという Issue まで立つ）。そのため `wikicommit-generate` Step 0 は、引数のホストが `exclude_domains` に該当する場合、散文方針との衝突と同じ扱いで**登録前に**確認を求める。

#### `rejected` は誰が書くか（完了条件）

**`wikicommit-collect` が、人間が却下した直後に追記する**（Step 8）。対象は `[Web]` 候補のうち人間が明示的に却下したものに限り、理由を 1 行聞いてから書く。理由を言わない場合は書かない — 理由のないエントリは、後から読んだ人がまだ有効か判断できず、無いより悪い。`[Local]` 候補は将来の検索で再浮上しないため対象外。**追記のみ可**（既存エントリの編集・削除、他キー・本文への書き込みは不可）で、これは `wikicommit-collect` Step 7 / `wikicommit-generate` Pass 2b が `.wikicommit/schema/` に対して持つ narrow exception と同じ形である。人間が手で書くこともできる。

**Issue #315（Pass 2b が却下した型候補をどこにも永続化しないと決めた設計）とは対象が異なる**ため衝突しない:

| | Issue #315 が永続化を避けたもの | ここで残すもの |
|---|---|---|
| 対象 | 却下された**型候補** | 却下された**ソース URL** |
| 再現性 | 次回同じソースを読めば同じ判断が再現できる | 「これは要らない」という人間の判断は、ソースを読み直しても再現しない |
| 残す弊害 | 「後で拾える」という誤った期待を生み、実際には拾われず情報が消える | 無い（再提案されないだけ） |
| 必要なもの | 再現 | **記憶** |

`wikicommit-collect` SKILL.md Step 5 は既にこの問題クラスを "free-exploration guidance that **has no memory of that prior exclusion**" と名指ししていたが、その時点で用意できた解決先はスクリプト内ハードコードだけだった。`rejected` はリポジトリ固有の記憶を置ける最初の場所である。

#### `index_only` — 読むが登録しないドメイン・ページ（Issue #570・#1032）

`/wikicommit-collect` が、このドメイン上のページを**参照節から一次資料を掘るためだけに読み、そのページ自身は候補にしない**。コマンド引数 `--index <url>` はその場限りの同じ指定である。

> **`/wikicommit-generate` Step 0 も読む（Issue #833）**: Issue #570 は消費者を `/wikicommit-collect` Step 5.5 のみと定めたが、**CLAUDE.md が主経路とする `/wikicommit-generate <url>` の直接実行には、これを見る主体がどこにも無かった** — SKILL.md 内の `index_only` の言及は 0 件であり、`dev/pilot-ai-driven-dev-wiki-round6.md` で実際に止まったのは、エージェントが frontmatter を自分で読んで判断しただけの偶然だった。
>
> **読まなかった場合に何が起きるかは決まっている**。`check_extraction_quality.py check-domain` が和集合にするのは組み込みの JS シェル一覧と `exclude_domains` だけなので、`index_only` のドメインは**素通りして取得され、ページが生成される** — 下の「境界がこの位置にある理由」が守ろうとしているものが黙って破られる。
>
> **しかも `exclude_domains` より弱い立場にある**。Issue #564 が Step 0 に確認を入れた理由（Pass 1 のブロックだけに任せると、要らないと決めたドメインに `status: failed` の管理ファイルと修正依頼 Issue が残る）はそのまま当たるうえ、`index_only` には**その Pass 1 のガードすら無い**:
>
> | | Step 0 の確認 | Pass 1 のガード |
> |---|---|---|
> | `exclude_domains` | あり（Issue #564） | あり（`check-domain`） |
> | `rejected` | あり（Issue #564） | なし |
> | `index_only` | **あり（Issue #833）** | なし |
>
> したがって Step 0 は、引数のホストが `index_only` に該当する場合、`exclude_domains` / `rejected` と**同じ形・同じ正規化**（スキーム・パス・ポート・先頭 `www.` を除去し小文字化した完全一致）で該当を名指しし、登録前に確認を求める。確認のメッセージには Issue #570 が設計した後続経路（`/wikicommit-collect --index <url>` が参照節から一次資料を掘る）を添える — ただし `--index` は `/wikicommit-collect` の引数であり `/wikicommit-generate` には無いため、コマンド名ごと書く。
>
> **塞がない。ここが `exclude_domains` との違いである**。下の「推奨する組み合わせ」(3) のとおり「人間が名指しで登録する経路は塞がない」のが Issue #570 の設計であり、一次資料が存在しない対象のために百科事典記事を明示登録する運用は残す必要がある。求めているのは、それが偶然ではなく判断であることだけである。
>
> **`check-domain` に和集合しない**。あれはブロックでありここで欲しいのは確認である。和集合にすると `status: failed` の管理ファイルが残り `wikicommit-merge` Step 9 が追跡 Issue を立てる（Issue #564 が `exclude_domains` について避けたのと同じ「誤った記録」）うえ、**登録してよい場合が実在する** `index_only` を `exclude_domains` より強くブロックすることになり、強度の順序が逆転する。
>
> **ページ URL も書けるようになった — awesome リスト等を常設の索引として使う（Issue #1032）**: `index_only:` は当初ドメインしか表せず、awesome リストを常設で使うには `github.com` を丸ごと指定するしかなかった — それはソースとして登録すべき GitHub の README まで全部巻き込む。`--index <url>` はページ単位だがその実行限りである。欠けていたのは「ページ URL 単位の常設リスト」だった。
>
> **新しいキーは足さず、エントリの形で意味を分ける**。「これは索引であってソースではない」という判断は 1 つであり、それを表すキーも 1 つで足りる:
>
> | エントリ | 範囲 | 検索結果に出てきたとき（受動） | 自分から見に行く（能動） |
> |---|---|---|---|
> | パスが無い（ドメイン） | そのホスト全体 | 採掘へ回す | しない |
> | パスがある（ページ） | そのページだけ | 採掘へ回す | する（guidance に関係する節があるときだけ） |
>
> 分かれ目は「ドメインかページか」ではなく**取得先の URL が 1 つに決まるかどうか**である。ワイルドカードは入れていない — 書いても取得先は決まらず、能動・受動の区別はそのまま残る。**別キー（`index_pages:` 等）と `index:` + `rejected:` の組み合わせは採らなかった**。前者はパス付きの既存エントリとの衝突を避ける利点があったが、公開パイロット 3 件（2026-09-25 確認）に該当エントリが無かった。後者は `rejected:` が URL 単位でドメインを表せず、書き忘れると索引ページ自体が候補になり Issue #570 が防いだ側に倒れる。
>
> **照合はスクリプトへ寄せた**（`match_index_only.py`。`docs/DesignDoc-ScriptSpec.md`）。それまで collect Step 5 と generate Step 0 の 2 か所の散文が照合しており、規則が 2 形に増えると 2 か所が別々にずれる余地が大きくなる — Issue #474 の「決定論的に判定できる操作を instruction にしない」に当たる。正規化はドメインが従来どおり（ホストの完全一致）、ページはスキーム・先頭 `www.`・フラグメント・末尾スラッシュを落とし、パスをパーセントデコードして比較する。**クエリは保持して完全一致で比べる** — `index.php?title=X` のようにクエリがページを名指すサイトで、落とすと 1 ページが全ページに広がる。
>
> **意味の変化が 1 つある**: パス付きのエントリは、従来はパスが捨てられてホスト全体を意味したが、今は 1 ページだけを指す。**黙って狭まる向き**なので `CHANGELOG.md` に書いた。
>
> **常設の索引を毎回丸ごと掘らない**。awesome リストは 100〜500 件のリンクを持ち、Wikipedia 記事の 10 件前後と桁が違う。collect Step 5.5 はページのエントリについて見出しの構造だけを見て research guidance に関係する節を選び、無ければ掘らずにその旨を 1 行報告する（取得した以上「見たが該当しなかった」ことを言う）。それでも多い場合に備え、**索引由来の候補は実行全体で 20 件まで**とし、切ったことを件数付きで報告する。索引ごとの上限にしないのは、読む人にとって問題になるのは最後に何件並ぶかだけだからで、どれを残すかは索引内の並び順ではなく関連性で決める。
>
> **Step 5.5 の文面を索引の種類に依存しない形にした**。「参照節を読め」は Wikipedia の形を前提にしており、awesome リストには参照節という区別が無い。「リンクの列挙部分を読み、散文部分は読まない」に一般化した。**各項目に付いた一言説明は散文であり、候補の説明に持ち込まない**。一方で**キュレーション（どのリンクを載せたか）を採用することは許容する** — Issue #570 の「どの被引用ソースが面白そうかをその記事の枠組みに決めさせない」を緩める判断であり、awesome リストは選別そのものが索引としての価値であるため、登録前レビューでメンテナが認めた。使うのはリンクの選択であって、記述ではない。
>
> **collect はページのエントリを追記しない**（索引の選定は人間が明示的に行うもので、Step 8 が人間の却下を `rejected:` に追記するのとは向きが違う）。取得キャッシュ（`.wikicommit/.cache/collect-index/`）は毎回取り直す。**既存リポジトリへの遡及は行わない**（スクリプトは再 init で届き、テンプレートのコメントは新規リポジトリにのみ届く）。

**境界がこの位置にある理由**が本質である。索引ページを読んで「**何を書くか**」を決めるのは危険で、表現・構成が生成物に漏れうるうえ、そのページは `sources:` に無いため **Pass 4 の出典照合が漏れを検出できず、帰属表示も付かない** — 結果として「無帰属の二次的著作物」になり、ソースとして明記して表示を付ける現状より**法的に悪化する**。一方、索引ページを読んで「**どの URL を取りに行くか**」を決めるのは安全である。参照文献リストは事実の列挙であり、そこから一次資料を自分で取得して書けば ShareAlike 義務は発生しない。したがって**参照リストだけを読み、本文は読まない** — 記事を要約しない、節見出しを候補の説明に持ち込まない、どの被引用ソースが面白そうかをその記事の枠組みに決めさせない。

**既存の `guidance` 引数ではこれを表現できなかった**。`wikicommit-collect` Step 2 の research guidance は「Wikipedia を**ソースとして**優先せよ」しか言えず（SKILL.md の例示自体が `site:wikipedia.org` を優先する形だった）、「読むが登録しない」は別種の指示である。その例示は Issue #570 で差し替え、百科事典を名指しする guidance は**どちらの意味かを確かめてから**動くよう改めた。

**実データが示したこと**: `dev/pilot-saitama-wiki.md` の 83 実ページで、`ja.wikipedia.org/wiki/さいたま市`（28 ページ）と市の区政概要 PDF（14 ページ）が生成した `AdministrativeArea/` 部分は、市＋10 区の 11 ページで**完全に一致した**。**骨格役は Wikipedia である必要がなかった** — 市自身の一次資料が同じ骨格を単独で生成しており、しかも一次資料側には ShareAlike 義務が付かない。Wikipedia が固有にもたらしたのは骨格ではなく「この街に何が在るか」の発見（スタジアム・クラブ・神社・公園・地域の文化的概念等）だった。一方 83 ページ中 49 ページ（59%）が Wikipedia のみを出典とし、うち 30 ページは**単一記事 1 本のみ**から生成されている — ある神社のページは本文 2,561 字で、原典記事より情報量が少なく脚注も一次資料へのリンクも無かった。

**推奨する組み合わせ**（3 案は排他ではない）: (1) 骨格は一次資料から取る、(2) 百科事典は索引として使う（`index_only`）、(3) 一次資料が存在しない対象だけ百科事典記事をソースとして明示登録する。神社の由緒・地域の文化的概念などネット上に一次資料が無い対象は必ず残るため、**「百科事典を一律禁止」という運用不能なルールにはしない** — ShareAlike 義務を負うページを意図的に少数に絞ることが目的である。この方針は `source-policy.md` テンプレートの本文コメントと README に書いた。

**コピーレフト系ソースの警告**（Issue #570 の対応方針 2、Issue #951 で対象を拡張）: `add_source.py` が既知ドメイン対応表（Issue #558）または `--license` から得たライセンスがコピーレフト系（`is_share_alike()`）なら、登録時のメッセージに一度だけその旨を添える。ライセンス値は自由記述なので完全な判定はできないが、対応表が返す値と SPDX の一般的な綴りは覆う。あわせて `wikicommit-generate` の Completion Notice が、`sources` が**全件**コピーレフトのページを列挙する（義務が実際に付くのはソースではなくページであるため）。

> **対象がソフトウェア側のコピーレフトへ広がった（Issue #951）**: 表は当初 `CC-BY-SA`/`CC-SA`/`GFDL`/`ODbL`/`CC-BY-NC-SA` の 5 つで、**Creative Commons 系と ODbL だけ・ソフトウェア側のコピーレフトが 1 つも入っていなかった**。`wikicommit/ai-driven-dev-wiki` で `--license GPL-3.0` として登録した GitHub リポジトリの README は、コピーレフトでありながら 4 つの消費者（`add_source.py` の `--license` 経路と既知ドメイン対応表経路・`--license-for-url`・Completion Notice のページ列挙）のどれからも警告が出なかった。**ライセンス値自体は最後まで正しく運ばれており**（レビュー記録の `reviewed_sources` に `license: GPL-3.0` が載っている）、欠けていたのは警告だけである。現在は `gpl`/`agpl`/`lgpl`/`mpl`/`epl`/`cddl`/`osl`/`sspl` に加え、Issue #958 で足した `eupl`/`cpl`/`ms-rl` を含む（下記コールアウト）。
>
> **弱いコピーレフト（LGPL / MPL / EPL / CDDL）も一律で入れた**。ソフトウェアでは「及ぶ範囲が狭い」ことに意味があるが、リンク境界もファイル境界も散文には対応物が無いため、その区別はここでは働かない。接頭辞照合なので `AGPL-3.0` は `gpl` に前方一致せず `agpl` が別に要る（逆に `LGPL-3.0` も `gpl` では一致しないので、落とすなら明示的な判断になる）。
>
> **末尾にハイフンを付けない**。SPDX 識別子は必ず付くので `gpl-` でも SPDX は覆えるが、この値は自由記述であり `GPLv3` や素の `GPL` は普通に書かれる綴りで、ハイフンを付けるとそのどちらも落ちる。下の非対称がここにもそのまま当たるうえ、`gpl` で始まる permissive なライセンスは無いので広げすぎにもならず、既存の 5 つが元からハイフン無しなのとも揃う。
>
> **Issue #570 が置いた非対称の評価は、ここでは向きが変わる**。あちらは「取りこぼしの劣化は注意書きが出ないで済み、誤った注意書きは出ない側に倒す」と書いていたが、その評価は「誤った注意書き」が実害を持つ場合にのみ成り立つ。ここで足した接頭辞はいずれも**実際にコピーレフト**なので誤った注意書きにはならず、一方で足りない場合の劣化は「利用者が義務に気づかないまま公開する」という、法的に取り返しのつかない側である。
>
> **表が表すのはライセンスの性質であって、そのページが二次的著作物に当たるかの判断ではない**。あるライセンスがコピーレフトかはライセンス自身の事実であり、それを読んで書かれた散文の要約が義務を負うかは別の問いである。WikiCommit はその問いに答えない（`docs/DesignDoc-publish.md` §8.10）ため、**注意書きの文面も「負いうる。確認すること」に弱めた** — 断定は、答えていないことを答えたふりをすることになる。弱めても信号は落ちない（利用者は「このソースはコピーレフトである」という事実を引き続き受け取る）。
>
> **`KNOWN_SOURCE_LICENSES` に `github.com` は足さない**。同表の条件は「そのサイトが自サイトのコンテンツ全体に対して明示しているライセンスのみを持つ」であり、GitHub は 1 ドメインに任意のライセンスが混在するためこれを満たさない。GPL-3.0 が `--license` 経由で入ったのは設計どおりである。
>
> **既に登録済みのソースは書き換えない**。`add_source.py` は新規作成時にしか `license` を書かず（Issue #558）、注意書きも登録時の一度きりなので、遡って警告は出ない。Completion Notice のページ列挙は次にそのページを生成したときに効く。
>
> **識別子の名前（`SHARE_ALIKE_LICENSE_PREFIXES` / `is_share_alike()`）と `--license-for-url` の `(share-alike)` マーカーは据え置く**。中身はコピーレフト系一般だが、マーカーは `wikicommit-collect` の SKILL.md に出力の契約として書かれている。
>
> **残っていた 3 族を足し、1 族は意図的に足さなかった（Issue #958）**: Issue #951 のレビューが挙げた残りである。**3 件とも評判ではなく本文の条項で確認した** — `KNOWN_JS_SHELL_DOMAINS`（Issue #425）が確立した「確認済みのものだけを決定論的な表に持つ」規律がここにも当たるため。
>
> | 接頭辞 | 巻き込む SPDX 識別子 | 本文で確認した根拠 |
> |---|---|---|
> | `eupl` | `EUPL-1.0`/`1.1`/`1.2` の 3 件のみ | **3 版とも "Copyleft clause" を持つ**（permissive な版は存在しない）。`EUPL-1.2` は `Original Work` を "the work **or software**" と定義しており、**この表で最もコードから遠い側の族である** — EU の公的機関がコードに限らない著作物に適用するため、行政文書を取り込む Wiki が実際に当たりうる |
> | `cpl` | `CPL-1.0` の 1 件のみ | ソース形式での配布を "must be made available under this Agreement" と定める。`CPAL-1.0` は `cpa` で始まるため巻き込まない |
> | `ms-rl` | `MS-RL` の 1 件のみ | 本文が "Reciprocal" を明示（ファイル単位のコピーレフト） |
>
> **`CPL` を「現れる見込みが低い」ことを理由に落とさない。** この表の規律は「確認済みのものだけを持つ」であって「よく使われるものだけを持つ」ではない。確認を経た以上、表の長さは規律の形骸化を意味しない — 形骸化するのは確認を省いたときである。
>
> **接頭辞は `ms-` ではなく `ms-rl` である。** SPDX には `MS-PL`（Public）・`MS-LPL`（Limited Public）・`MS-RL` の 3 つがあり、**reciprocal 条項を持つのは `MS-RL` だけ**である。`gpl` / `epl` のような族単位に揃えると permissive な `MS-PL` を巻き込む — **この表で唯一、族が permissive と copyleft に割れている箇所**であり、Issue #958 の起票時には見えていなかった点である。
>
> **CeCILL は足さない。沈黙は漏れではなく決定である。** 前方一致という実装の形が選択肢を縛る: `CeCILL` / `CeCILL-C` はコピーレフトだが `CeCILL-B` は帰属表示のみを求める permissive（§5.3.4。本文で確認済み）であり、`CeCILL-B` は `cecill` で始まるため、**「裸の `CeCILL` を拾う」と「`CeCILL-B` を拾わない」は純粋な前方一致では両立しない**。
>
> | 採らなかった案 | 採らない理由 |
> |---|---|
> | 版ごとに `cecill-1`/`cecill-2`/`cecill-c` を列挙 | **裸の `CeCILL` を取りこぼす**。末尾ハイフン無しの規約（Issue #951）が守ろうとしたのがまさにその自由記述の綴りであり、それを 1 族のために裏返すことになる |
> | `cecill` を足し `cecill-b` を除外リストに置く | `is_share_alike()` が前方一致だけでなくなる。1 族のために 2 つ目の概念を関数に持ち込む代償が、`sources[].license` に CeCILL が現れる見込みに見合わない |
>
> `CeCILL-2.1` / `CeCILL-C` は**permissive 非検出リストには入れない** — あのリストは「permissive である」ことの表明であり、この 2 つはコピーレフトだからである。既知の沈黙であることを述べる独立したテストがその場に固定している。
>
> **既存の誤検知が 1 件見つかったが、直さない。** `mpl` は `mplus`（mplus Font License。permissive）にも前方一致する。誤りの向きが Issue #951 が意図的に選んだ側（注意書きが 1 行余計に出るだけ）であり、フォントのライセンスが `sources[].license` に現れる見込みも低い。ここに記録するのは 2 つの理由による — 次に表を見た人がこれを欠陥として起票し直さないため、そして**「足しすぎの劣化は 1 行で済む」という非対称が、仮定ではなく実例を持つ**ことを残すためである。
>
> **`CHANGELOG.md` は更新しない**（Issue #951 と同じ）。版を上げる契機は型テンプレート・ページ生成ルールの変更である。**既に登録済みのソースにも遡って警告は出ない**（同上）。

**「骨格ソース先行」は検証すべき仮説**（同 3）。saitama で `check_orphans.py` が検出した orphan 6 件すべてが「骨格 2 ソースが 1 ページも作っていない」ページだった一方、1 記事 1 ページだった Wikipedia ソース 8 件のうち 5 件は骨格ソースが既に作ったページへの `action: update` として機能していた。ただし 1 リポジトリの観察であり、**骨格ソースは定義上あらゆるページにリンクする側なので、その由来ページが被リンクを得るのは半ば同語反復**である。次のパイロットで、骨格ソースを意図的に先に入れた場合と入れなかった場合で orphan 率が変わるかを検証する。それを可能にするため `check_orphans.py` の `ORPHAN:` 行に出自（そのページの `sources`）を添えた（同 3 の最後の候補。実装コストが小さく、運用中にも気づける）。

#### 現時点でキーを置かないもの

`license_map`（ドメイン→ライセンス対応表）は、**このファイルが行き先である**ことを決定した上で、**その消費者と同時に追加する**。空のキーだけを先に配ると、Issue #553 が `DefinedTerm.inDefinedTermSet` について示したとおり「受け皿だけ存在して常に空のまま残る」ことになるため。`add_source.py` の `KNOWN_SOURCE_LICENSES`（Issue #558）は当面そのまま据え置く。

`index_only`（読むが登録しないドメイン）も当初はこの節に置いていたが、Issue #570 で消費者（`wikicommit-collect` Step 5.5）と同時に追加したため、上記 §「`index_only` — 読むが登録しないドメイン」へ移した — この節の方針そのものに従った結果であり、例外ではない。

#### `theme` の narrow（完了条件）

`theme` の役割を内容スコープのみに限定し、`config.yml` テンプレートのコメント・`wikicommit-init` の対話プロンプト文言・本節 §3.3 の記述を更新した。プロンプトは「主題を書く。どのソースを使うかは書かない」と明示する。**既存リポジトリの `theme` に混在しているソース方針の自動移行は行わない**（新旧混在を許容する慣例）。副次的に、Pass 2c のエンティティ判定にソース方針が混ざる問題も解消する。

### 3.5 `.wikicommit/entity-policy.md`（エンティティ許容方針。Issue #667）

「**そのエンティティについて書いてよいか**」を書くファイル。`config.yml` の `theme`（「この Wiki の主題と関係があるか」）とは別の問いに答える。`.wikicommit/source-policy.md` : `source/` :: `.wikicommit/entity-policy.md` : `entity/` という対応になる。

出発点は「存命の個人についてページ生成を抑止したい」という要望だったが、当初案（`Person` 型だけ `auto_merge: false` にしてマージを止める）は前提が 2 つ崩れていた。

1. **`review.auto_merge` は消費者のいないフィールドである**。`config.yml` にありながら、これを読む箇所が `.claude/skills/*/SKILL.md` にも `.wikicommit/scripts/*.py` にも 1 つも無い（grep で当たるのは GitHub 側のリポジトリ設定 `allow_auto_merge`〈Issue #456〉という別物だけ）。§3.3 の構造にも載っていない。したがって「false にすれば止まる」は成立せず、型別分岐以前にグローバルなゲート自体が存在しない（**このフィールド自体は Issue #669 が配布テンプレートから削除した**。上の記述は当時の状態であり、現在の `config.yml` には `review:` ブロックが無い — 既存リポジトリには残るが、読む主体はやはり存在しない）
2. **マージを止めることは信頼ラダーの前提に触れる**。WikiCommit は `pending` でも main にマージして公開しバナーを出す設計であり（`docs/DesignDoc-publish.md` §8.4）、「公開前に人間レビューを挟む」は第 3 の状態の導入になる。`review_status` の 2 値・レビュー追跡 Issue・`review-issue-close-sync.yml` の全部に分岐が要る

**そこで、止める場所をマージではなく生成に置いた**。「ページを作らない」なら既存の機構（Pass 2c の `action: exclude`）がそのまま使え、`exclude_reason` の enum は `docs/DesignDoc-skills.md` が最初から「現状は `theme_mismatch` のみ。将来 `privacy` / `copyright` 等を追加予定」と予約していた。

#### なぜ新しいファイルが要るのか

**型テンプレートの `granularity` には書けない**。「存命の個人はページ化しない」は型をまたぐ — 人物は `Person` だけでなく、実体が個人〜数名の `Organization`・`Event` の主催者・`ShortStory` の `character` にも現れる。ところが `.wikicommit/schema/` は LLM から「追加のみ可・既存ファイルの編集不可」であり、**既存の型ファイルに後から書き足す経路がどの Skill にも存在しない**（§5.2「`granularity` の境界ルールは片側にしか書けない」が既に踏んだ壁と同一）。加えて Pass 2b が実行時に新しい型を足すため、将来足される型には書きようがない。横断ルールを `granularity` で維持するのは原理的に不可能である。

**`theme` に混ぜてもいけない**。両者は同じ Pass 2c に読まれ同じ `action: exclude` を出すため、一見「1 つの問いを 2 ファイルに割る」という §3.4 の逆に見えるが、実際には別軸である:

| | 問い | 例 |
|---|---|---|
| `theme` | **関連性** — この Wiki の主題と関係があるか | さいたまの区の記事から人物を除外 |
| `entity-policy.md` | **許容性** — 関係があっても、書いてよいか | 主題の中心にいる存命の人物 |

主題のど真ん中にいる存命の人物は関連性が最大でもなお除外したい。2 つは独立に効くため、`theme` に混ぜれば Issue #564 が直したのと同じ「別軸の方針が丸ごとノイズとして混入する」形を再発させる。`exclude_reason` の enum が最初から `theme_mismatch` / `privacy` / `copyright` と分かれて予約されていること自体、この軸の分離が想定されていたことを示す。

**`theme` を新ファイルへ移すことはしない**。1 行のスカラーで YAML に収まり `wikicommit-init` の対話で設定される値であり、Issue #564 が `source-policy.md` を独立ファイルにした理由（「中身の大半が散文であり YAML の値として持つには収まりが悪い」）が当てはまらない。両方に「こちらは関連性・こちらは許容性」と明記する形で足りる。

#### フォーマット

`.wikicommit/source-policy.md` と同じ「機械可読フロントマター + 散文」を採る。

```markdown
---
wikicommit:
  exclude_living_persons: false   # 存命の個人についてページを作らない
---

（コメントアウトした記入例。散文本文が実質の方針）
```

**キーは `exclude_living_persons` の 1 つだけにする**。Issue #553（`inDefinedTermSet`）と Issue #564（`license_map`）が繰り返し確立した「消費者と同時にキーを足す・受け皿だけ先に配らない」に従う。とくに名指しの例外リスト（`living_person_exceptions: []` 等）を**構造化キーとして持たせない**: `source-policy.md` の 3 キーはいずれも正規化後の完全一致（ホスト・URL）という決定論的な照合を持つのに対し、人物の例外はエンティティ名での照合になり曖昧一致に頼らざるを得ない。フロントマターは決定論的な値・散文は LLM が読む判断材料、という既存の役割分担を崩さないため、例外は散文側に書く。

**「非公人」を 2 つ目のスイッチにもしない**。実際にリスクを分けているのは存命性ではなく公人性の軸だが、「存命か」も「公人か」も等しく LLM 判断であり、スイッチを 2 つ並べると組み合わせの意味を説明する必要が出る。スイッチは 1 つに保ち、公人の例外と故人の非公人は散文で書く。

既定値は `false`（`theme: ""`・`exclude_domains: []`・`rejected:` と同じく、配布時は inert）。散文本文についても同じで、**本文が記入例のままなら方針は無いものとして扱う — その判定は `read_policy.py` が行う**（Issue #844。§3.4 の該当コールアウト）。**ファイルが無い既存リポジトリは従来どおり動く**（本ドキュメント群が踏襲する「新旧混在を許容する」慣例）。フロントマターが壊れている場合も配布時の既定（スイッチ off・散文なし）として扱うが、**ファイルが在るのにパースできなかった場合は無言で fail-open してはならない** — §3.4 が `exclude_domains` について確立したのと同じ理由（手編集 1 回のミスで方針全体が黙って無効化される）に加え、こちらは組み込みリストのような後ろ盾が無い。`wikicommit-generate` はその場で `WARNING:` を出し、Completion Notice にも再掲する。**ファイルが無い場合は警告しない** — 「この機能追加より前に作られた」ことを意味するだけであり、全実行に無意味な警告が出ることになるため。

> **このスイッチは `/wikicommit-init` が 1 問だけ聞く（Issue #837）**: Pass 2c は 2 つの独立した軸（`theme` ＝ 関連性 / このファイル ＝ 許容性）を読み、どちらも同じ `action: exclude` を出すのに、**init が聞くのは片方だけだった**。この非対称に理由は書かれていなかった。
>
> **散文とスイッチでは「後から書けばよい」の成り立ち方が違う**。`wikicommit-init` SKILL.md は 2 つのポリシーファイルを「init 後に書く場所として名前を挙げるに留め、いま開かせない」と明示的に決めており、**散文についてはそれで正しい**（散文は実行のたびに読み直されるので、後から書けば次の実行から効く）。スイッチは既定値を持ち無言で作用する点が違い、しかも**どちらの向きにも既に起きたことには届かない**:
>
> | 既定のまま生成したあとで設定を変えると | 何が起きるか |
> |---|---|
> | `false` で生成 → ページが出来ている | `--regenerate` は Pass 2c を実行しない（`docs/DesignDoc-pipeline.md` §6.1）ため**ページは残る**。`/wikicommit-remove` で 1 枚ずつ下ろすしかない |
> | `true` で生成 → 除外されている | 同じソースを再登録しても `HASH_MATCH:` で Pass 2〜4 に進まないため**ページは作られない**。管理ファイルを手で `pending` に戻すしかない |
>
> **したがって「安全な既定を選ぶ」という論法が成立しない** — 片方だけが取り返しのつかない既定なら安全側に倒せばよいが、両方とも取り返しがつかない。残る答えは「利用者が実際に決めた値を使う」しかない。しかも既定が効く窓は init 直後の最初の `/wikicommit-generate` であり、Issue #570 の骨格ソース先行仮説が正しければ**被リンクの中心になるページ群**にちょうど掛かる。
>
> 実装は `theme` と同じ形（Skill が聞き、`init.py` にフラグで渡す）。聞くのは**スイッチだけ**で散文は従来どおり init 後の案内に留め、空 Enter は `false`（現行の挙動・既存の全リポジトリ・この Skill の他の Enter ベース確認の既定 N と一致）。非対話実行では聞かず `NOTE:` を出す（Issue #507 の分岐・Issue #825 の伝え方）。**`--update-theme` 相当の上書き経路は作らない** — `entity-policy.md` は `update: review` であり、`config.yml` と違ってファイル全体が利用者の編集対象なので、1 行の変更は手で足りる。
>
> **質問文は「誰が対象外か」を必ず併記する**。スイッチが切っているのは `living` だが、実際にリスクを分けているのは公人性であり、テンプレート自身がそう書いている。`wikicommit/saitama-city-wiki` では `theme` だけで人物を排した結果 `Person` 型が 0 ページになり、本文が繰り返し名指ししている歴史上の人物 3 名（1486 年・1738 年・1830 年没）まで巻き込んだ — 落ちた 4 人のうち存命の公人は 1 人だけだった。これを書かない質問文は同じ過剰除外を自分で誘発する。
>
> **既定を `true` にしない理由（4 つ。次に同じ提案が出たときに再検討し直さずに済むよう記録する）**:
>
> 1. **スイッチは代理指標であり、テンプレート自身が両方向に外れると認めている** — 故人の非公人（地域史料の一般住民）は覆えず、存命の公人は覆いすぎる。Issue #667 が 2 つ目のスイッチ（公人性）を拒んだ理由そのものであり、**弱い側の代理指標を既定 on にすると覆いすぎだけが全 Wiki に広がる**
> 2. **`dev/PRD.md` §3 のセグメント 2（チームの社内ドキュメント）を黙って壊す** — 社内 Wiki で同僚のページを持つことは正当な主用途であり、private リポジトリなら公開の害も無い
> 3. **除外理由が実名付きで公開サイトに出る経路が生きている間は、逆効果になる**（Issue #831 が扱った形）。既定を on にすると、プライバシー保護のための設定が全 Wiki でプライバシー漏洩を増やす
> 4. **既定 off でも無防備ではない** — Issue #668 が `Person.md` の `granularity` に常時有効の記述範囲制限（存命の個人は本人が公表したものに限る）を入れており、Issue #473 が実際に踏んだ害はそちらが受け止めている
>
> **既存リポジトリへの遡及は行わない**（新旧混在を許容する慣例）。既に init 済みのリポジトリは `false` のまま残り、再 init でも上書きされない。**スイッチを変えた結果を既存ページへ届ける経路は `/wikicommit-reconcile` である**（Issue #874）。同 Skill が対象ソースの管理ファイルを `status: pending` に戻し、次の `/wikicommit-generate` が Pass 2c をもう一度通す — ポリシーを読む場所は Pass 2c だけであり、`--regenerate` はそれを実行しない。**on にした場合だけでなく、off に戻した場合にこそ効く**: `status: excluded` のソースは既存のどのコマンドでも到達できず（`<url>` は `HASH_MATCH`、`<path>` は `SKIP`、引数なしは収集対象外で、3 経路とも出力は成功系）、それ以前は管理ファイルを手で書き換えるしかなかった。
>
> **常設の検出器は置かない**。「`exclude_living_persons: true` かつ `Person/` にページが実在する」は決定論的に判定できるが、`check_retracted_sources.py` と同型ではない — あちらは両側が証拠（人間が `retracted` と書いた特定のソース／ページがその識別子を挙げている）であるのに対し、こちらの右辺は「そのページが `Person` である」でしかなく、**正しい対処をとっても所見が消えない**（大半のページの正しい行動は「残す」である）。しかも発火するのはスイッチを変えた直後だけであり、1 回きりのイベントに常設のチェックを置くと常時点灯する所見になる（Issue #562 / #760 と同じ力学）。したがって対象は人間が宣言する — **変えたのは本人であり、機械が言える新情報はスイッチが on であることの 1 ビットだけである**。
>
> **on にした場合、既存ページは再生成しても消えない**。ページを削除する経路は `/wikicommit-remove` だけで、生成側は何も削除しない。**どのページが対象外になったかは機械が名指しする**（Issue #876）: Pass 2c は `action: exclude` のエントリにも `existing_path` を解決し、Completion Notice と `## Generation Notes` の両方がそのパスを添える。かつてここは「人が突き合わせる」と書いていたが、`## Generation Notes` が持つのはエンティティの**タイトル**であり、ファイル名は言語中立な英語 slug でその導出は逆算できない（Issue #193）ため、`primary_lang` が英語でない Wiki では `title:` の grep になっていた — 機械はその答えを、エンティティに名前を付けた副産物として既に持っている。**報告は断定しない**（「このページは在り、今回の実行は作りも更新もしなかった」までを述べる — 複数ソースに支えられたページの 1 件が今回除外されただけ、という形は普通に起こる）し、**自動削除も行わない**（`/wikicommit-remove` を指すのは `privacy` グループのみ。`docs/DesignDoc-skills.md` §11.6）。

#### 消費者は Pass 2c のみ

| 部位 | 読む主体 | 何をするか |
|---|---|---|
| `exclude_living_persons` | `wikicommit-generate` Pass 2c | true なら、ソースが存命と示す個人のエンティティを `action: exclude` / `exclude_reason: privacy` にする |
| 本文（散文） | `wikicommit-generate` Pass 2c | 散文が名指しするカテゴリを同じ形で除外する。人物に限らない（係争中の事案・自組織の未公開情報等） |

`theme` が空でもこの判定は行う — 2 つは独立した軸であり、`/wikicommit-init` の既定が空の `theme` である以上、`theme` が空なら `exclude` 自体を禁じるという読み方をすると、entity-policy を設定した Wiki で許容性の判定が丸ごと黙って無効化される（`docs/DesignDoc-skills.md` §11.6 の `exclude_reason` 節・`wikicommit-generate` Pass 2c の該当箇所）。

`theme` と同じく人間確認なしで自動適用され、管理ファイルの `## Generation Notes` と Completion Notice に記録される（Issue #831 — 以前は `## Summary` に書いていたが、そこは `content/sources/` へ公開される唯一の節であり、**書かないと決めた人物の実名と除外理由がそのまま読者に届いていた**。§4.3 参照）。**両方の理由が同じエンティティに当てはまる場合は `privacy` を記録する** — Wiki の主題が変わっても残る側の理由であるため。

**`wikicommit-synthesize` と `wikicommit-collect` は対象外とする**。前者は既存ページから合成するためポリシーを迂回しうるが、別 Issue とする（本 Issue で器と主経路を確定させてから広げる）。後者はソース選定の話であり、必要なら人間が `source-policy.md` に書けば済むため器を増やさない。

#### 散文本文が担う範囲（配布テンプレートの記入例）

**除外カテゴリを増やすのに新しいキーは要らない**。散文本文は Pass 2c が自由記述として読むため、`exclude_living_persons` 以外の判断はすべてここに書ける。配布テンプレートのコメントアウトした記入例に挙げる価値があるのは以下の 4 つで、いずれも**存命スイッチでは覆えない**か、覆えても理由が別である:

| カテゴリ | 根拠 | 存命スイッチとの関係 |
|---|---|---|
| **非公人（public figure でない実在の個人）** | 行政文書には審議会委員名簿・事業者名・陳情者名が普通に入る | **覆えない**。故人の非公人（地域史料に出てくる一般住民）が漏れる一方、存命の公人は覆いすぎる |
| **実在の未成年者** | 学校・地域行事を扱う Wiki が踏む | 存命なら覆えるが、スイッチ off の Wiki では丸ごと漏れる |
| **係争中の事案・進行中の事件** | `Event` 型。事実が流動的で、誤りが名誉毀損になりうる。`expires_at`（Issue #279）は「古くなる」を扱うが「今書くべきでない」は扱わない | 覆えない（`Person` 型ではない） |
| **自組織の未公開情報** | `dev/PRD.md` §3 のセグメント 2（チームの社内ドキュメント）が最初に必要とするもの | 覆えない |

**あわせて「除外しすぎない」ことも記入例に書く**。これは仮定の話ではない — `wikicommit/saitama-city-wiki` は `theme` による除外だけで `Person` 型が 0 ページになり、太田道灌（1486 年没）・井沢弥惣兵衛（1738 年没）・児玉南柯（1830 年没）という**書いて何の問題もない歴史上の人物**まで巻き込んでいた。落ちた 4 人のうち存命の公人は 1 人だけであり、パイロット自身がこの結果を「よしとするか検討の余地がある」と記録している。カテゴリを足すほどこの方向に効くため、記入例には「公人・歴史上の人物を巻き込みすぎないこと」を必ず併記する。

#### entity-policy に入れないもの

| カテゴリ | 既にある器 |
|---|---|
| 商業的な宣伝・個人ブログ | `.wikicommit/source-policy.md`（テンプレートの記入例に既にある） |
| 著作権 | ほぼソース側で解決済み。小説パイロット 3 件（`akechi-kogoro` / `arsene-lupin` / `decameron`）はいずれも取り込み前に保護期間満了を確認しており、`wikicommit-collect` は候補に ⚠️ を出し、`sources[].license` と ShareAlike 警告（Issue #558 / #570）がある |
| 医療・法律・金融の「助言」に読める記述 | エンティティの存否ではなく記述範囲。`granularity` と `expires_at` |

**`exclude_reason: copyright` は予約のまま据え置く**。ソース側で保護期間・ライセンスを確認して取り込む設計になっている以上、エンティティ単位で「著作権を理由にページを作らない」と判断する場面がほとんど残らない。消費者を得ないまま `theme_mismatch` / `privacy` の隣に並べると、Issue #553 が `inDefinedTermSet` について指摘した「受け皿だけ存在して常に空のまま残る」形になる。

#### 既存ページには遡及しない

`--regenerate` は Pass 2c を実行しない（`docs/DesignDoc-pipeline.md` §6.1）ため、既に存在する存命人物のページはポリシーを書いても消えない。本ドキュメント群が一貫して採る「新旧混在を許容する」方針どおりだが、**プライバシーが理由のポリシーで「書いたのに既存ページが残る」は誤解を招きやすい**ため、テンプレートの散文コメントと Completion Notice の両方に明示し、削除は既存経路（`/wikicommit-remove`、`removed_reason: gdpr`）であることを併記する。

**手順書は `.wikicommit/guides/applying-entity-policy-to-existing-pages.md` にある（Issue #867）**。中身は「手順」ではなく `/wikicommit-reconcile --all` → `/wikicommit-generate` の 1 本と、それが済ませないもの（既存ページは消えない・対象ページの突き合わせは人手・スイッチが構造的に見えない置き場・除外しすぎない・常設の検出器が無い理由）である。ガイド棚（`.wikicommit/guides/`。Issue #846）を選んだ決め手は配布経路の非対称で、ポリシーファイル 2 つは `update: review` かつ `compare: frontmatter_keys` のため**本文だけを変えても既存リポジトリに 1 件も届かず差分としても報告されない**一方、ガイドは `update: overwrite` なので再 init と `/wikicommit-update` で届く。残る限界も同じところにある — 既存リポジトリにはガイド本体は届くが、そのリポジトリの `entity-policy.md` は上記の 1 文を持たないため、そこから辿る導線が無い（新旧混在を許容する慣例どおり受け入れる）。

#### 配布と取り込み

- `_root_outputs.py` に 1 行追加した。Issue #642 により、init の配布・`git add` 案内・`always_skip_existing` 保護がこれで揃う（`source-policy.md` と同じく、再実行で上書きしない）
- `wikicommit-merge` Step 2 / Step 5 に取り込む。人間が手編集した内容がコミットされないと意味がないため（`source-policy.md` が専用の pathspec を持つのと同じ理由）。既存の `<policy file>` 変数は `<policy files>` に改め、2 ファイルを 1 変数で扱う — ステージの仕方が同一であり、下流で区別する必要が無いため。`source-policy.md` と同様、この `.md` は Wiki ページではないため `<changed .md files>` に入れてはならない（`validate_frontmatter.py` 等が落ちる）

---

## 4. データ設計

### 4.1 Wiki ページのフロントマター

フロントマターは **共通フィールド**（トップレベルに平置き）と **型固有プロパティ**（`properties:` にネスト）の 2 層構造（Issue #495）。前者はページ解決に必須の構造的フィールド・WikiCommit 独自のブックキーピング情報・型に依存せず全ページ共通の識別子フィールドで、Schema.org 語彙に対する機械検証の対象外。後者は Schema.org 型固有のプロパティで、`validate_frontmatter.py` が `type:` の指す型（祖先型を含む）の `domainIncludes` に対して機械検証する（§5.2・`docs/DesignDoc-ScriptSpec.md` 参照）。

```yaml
---
# ── 共通フィールド（全ページ必須 or 推奨。properties: の機械検証対象外）──────
title: "山田太郎"                    # 必須: ページ識別・表示
lang: ja                             # 必須: ISO 639-1 言語コード
type: "schema:Person"                # 必須: Schema.org 型識別子（OKF v0.1 唯一の必須フィールド）
tags: [engineer, ml]                 # 推奨: タグ検索・絞り込み

# ── 出自・整合性フィールド────────────────────────────────────────────
sources:
  - type: path                       # path / url / wikicommit / manual
    path: raw/paper-2024.pdf
    hash: sha256:abc123def456...     # wikicommit-generate 時に自動計算
  - type: url
    url: https://example.com/article
    hash: sha256:def456...
    license: CC-BY-SA-4.0            # 任意。ソース管理ファイルの source.license を転記したもの

# ── 審査状態フィールド────────────────────────────────────────────────
review_status: pending               # pending / reviewed（省略時は pending）
expires_at: "2027-06-21"            # 任意: この日付を過ぎると wikicommit-status が warning 表示
reviewed_by: "octocat"              # 任意: レビュー追跡 Issue を Close した人の GitHub login（Issue #663）。
                                    # review-issue-close-sync.yml が review_status と同じコミットで書く

# ── LLM 生成メタデータ（wikicommit-generate が設定・任意）────────────
generated_at: "2026-06-17"          # 任意: ページ生成日（YYYY-MM-DD）。review_status バナーで表示
generated_by: "claude-sonnet-4-6"   # 任意: 生成に使用した LLM モデル ID。review_status バナーで表示
generated_with: "0.1.0"             # 任意: このページを生成した WikiCommit 自身の版（Issue #577）

# ── 外部識別子（Commons / Linked Data 連携）─────────────────────────
wikidata: "wd:Q12345"               # 任意: Wikidata QID
sameAs:
  - "https://orcid.org/0000-0001-2345-6789"
aliases: ["Taro Yamada", "たろう"]

# ── 型固有プロパティ（.wikicommit/schema/Person.md の properties: で定義。
#    Schema.org の domainIncludes に対して validate_frontmatter.py が機械検証）──
properties:
  description: "CompanyA のシニアエンジニア。機械学習システムの開発に携わる。"
  affiliation: "[[Organization/companya]]"
  jobTitle: "シニアエンジニア"
  birthDate: "1980-01-01"
---

山田太郎は CompanyA に勤務するシニアエンジニア...

## 経歴
2005年 CompanyA 入社。[[Event/project-alpha]] のリードエンジニアを務め...
```

> **`tags` フィールドの位置づけ**（Issue #275）: `tags` はページを横断した絞り込み・検索補助のための自由記述ラベルであり、`type`（Schema.org 型による分類）や `title`（ページ自身の識別）とは役割が異なる。分類体系そのものではなく、複数ページを横断して同じ概念で括りたいときに使う（例: `tags: [engineer, ml]` は「エンジニア」「機械学習」という横断的な属性を表し、`type: schema:Person`（人物であること）や `title: "山田太郎"`（誰であるか）とは重複しない情報を持つ）。付与時は以下のルールを適用する:
>
> - ページ自身の `title` と同一・類似の語を `tags` に含めない（自己言及的で情報量ゼロになるため。例: `title: "認可保育所"` のページに `tags: [認可保育所, ...]` を付けない）
> - `type` が表す分類と重複する語を避ける（例: `type: schema:Person` のページに `tags: [person, 人物]` を付けない。すでに `type` が担っている情報のため）
> - 複数ページを横断して意味のある概念（分野・カテゴリ・技術要素等）のみをタグ化する
> - タグが特定ベンダー・製品名を含む場合、その概念が実際にそのベンダー固有のものであるかを確認する（Issue #430）。あるベンダーが「この用語に言及した資料の出典の一つ」に過ぎず、概念自体がそのベンダー固有ではない（業界一般語・他の主体が提唱した概念等）場合、そのベンダー名をタグにしない（例: "context engineering" は Anthropic が言及した資料の一つを ingest したとしても Anthropic 固有の概念ではないため `tags: [anthropic-tooling]` を付けない）
>
> この判定は `wikicommit-generate` の Pass 3（ページ生成、`docs/DesignDoc-skills.md` §11.6）の指示に明記し、LLM の自己裁量に委ねない。`childcare-procedures-wiki` パイロットで実際に生成された自己言及タグ（Issue #19）は個別に `wikicommit-fix`（PR #20）で修正済みであり、本 Issue の対応範囲は生成時ルールの明文化に留める。他パイロットで既に生成済みの同種のタグを遡及的に一括修正することはしない（各リポジトリの運用者が必要に応じて `wikicommit-fix` で個別対応する）。ベンダー名タグの誤付与（Issue #430）についても同様に、`ai-driven-dev-wiki` パイロットで実際に発生した `context-engineering.md`／`context-rot.md` の `tags: [anthropic-tooling]` は当該パイロットリポジトリ側で個別修正する対象とし、本ドキュメントの対応範囲は生成時ルールの明文化に留める。
>
> **`generated_with` / `translated_with`（Issue #577）**: そのページを生成（翻訳）した WikiCommit 自身の版を記録する任意フィールド。値は `.wikicommit/scripts/_version.py`（インストール先まで届く唯一の版の情報源。§3.3 の該当コールアウト参照）から読み、`wikicommit-generate` Pass 3 / `wikicommit-translate` がページ書き出し時にスタンプする。`config.yml` の `wikicommit_version`（＝このリポジトリが初期化された版）とは意味が異なるため、キー名を分けている。
>
> **用途は「作り直すべきページを人間が選ぶ」ことに限られる**。型テンプレートやページ生成ルールを更新しても既存ページは古いルールのまま残るが、「どのページが古いか」を型単位で判定する機械的な検出機構は設けない方針のため、`generated_with` を `grep` して古い版のページを列挙する形が専用スクリプトの代替になる。ただし版の粒度は型より粗く、`Person.md` だけを変更して版を上げても全ページが等しく「古い」と見えるため、実際にどのページを作り直すべきかは `CHANGELOG.md` の記述に依存する — この 2 つはセットで初めて機能する。
>
> `validate_frontmatter.py` は `generated_by` と同じく「フィールドが存在する場合に空文字列不可」だけを検証する。semver パターンへの照合は行わない（モデル ID を正規化表に照合しない〈`docs/DesignDoc-pipeline.md` §6.7〉のと同じ理由 — 形式検証は将来の正しい値を拒否する側にしか働かない）。**既存ページへの遡及付与は行わない**。フィールドの欠如は「この機能追加より前に生成された」ことを意味する。
>
> **`sources[].license`（Issue #558）**: 各ソースの利用条件を記録する任意フィールド。値は自由記述の短い文字列で、SPDX 識別子が存在するものはそれ（`CC-BY-SA-4.0`・`CC0-1.0`）、無いものは短い語句（`Saitama City website terms of use`・`all-rights-reserved`）を書く。`hash` と同じくソース管理ファイル（§4.3）の `source.license` が正であり、ページ側の値は `wikicommit-generate` Pass 3 が生成時に転記したコピーである（`hash` が「鮮度の検証」のために両方に置かれているのと同じ構造）。公開サイトでは `WikiCommitSources` が出典リンクの直後にライセンス名を併記し、あわせて「このページは出典を要約・再構成したものである」という固定文言を表示する（`docs/DesignDoc-publish.md` §8.10）。
>
> **不明を空文字列で表さない**: 値が不明な場合はフィールドごと省略する。`validate_frontmatter.py` は空文字列を ERROR とする — 空文字列を許すと、公開サイト側で「ライセンスが記録されている」と「不明」が区別できなくなるため。フィールドが無いことは「制約が無い」ではなく「WikiCommit は知らない」を意味する。
>
> 値の中身に対する機械検証は行わない（SPDX 語彙への照合も、ソースの実際の条件との突合もしない）。WikiCommit の責務は記録する場所を用意して記録された内容を表示することに限られ、ライセンスの当否は判断しない（`docs/DesignDoc-publish.md` §8.10「WikiCommit が法的判断を代行しない線引き」）。既存の公開済みリポジトリへの遡及付与も行わない（同節）。

`properties:` に何を入れるか／入れないか（Issue #495）: `tags`/`wikidata`/`sameAs`/`aliases` は語彙としては Schema.org 寄りだが、`wikicommit-jsonld` プラグインが型に関わらず一律で読む「WikiCommit 全ページ共通の識別子フィールド」であり、型ごとに変わる `properties:` 側とは性質が異なるためトップレベルに残す。翻訳ページの `translated_from`/`source_commit`/`translated_at`/`translated_by`/`translated_with`/`translator_notes`（Issue #524）、合成ページの `derived_from`、削除ページの `status`/`removed_at`/`removed_reason`/`merged_into` も同じ理由でトップレベルに残す。`properties:` に書けるのは、情報源が単一の事実として明示している、短く構造化された値（日付・固有名詞・URL・他エンティティへの参照）に限る。複数文にまたがる説明・文脈・因果関係・複数事実の統合が必要な内容は、対応する property 名が Schema.org 上に存在していても本文に書く（`properties.description` 自体も 2〜3 文の要約に収め、詳細な経緯は本文見出しに譲る。`.claude/skills/wikicommit-generate/SKILL.md` Pass 3 参照）。

> **`reviewed_by`（Issue #663）**: レビュー追跡 Issue を Close した人の GitHub login を記録する任意フィールド。`review-issue-close-sync.yml` が `review_status` を `reviewed` に書き換えるのと**同じコミットで**書き込み、公開ページの `WikiCommitBanner` がこれを表示する。
>
> **git 履歴ではなく frontmatter に置く理由**: 誰がレビューしたかは既に `Reviewed-by:` コミットトレーラーとして git 履歴に残っている（§6.7）が、**公開サイトの読者はそれを見る手段を持たない**。結果として `reviewed` バッジは「レビューが行われた」とは言うが「誰の判断か」を言わず、信頼ラダー（`pending` → `reviewed`）の上段が単なるフラグに見える — `docs/DesignDoc-pipeline.md` §6.3 の遷移表が「承認者を表示」と定めていたのに対し、実装は状態を出しているだけだった。値の取得元としては git 履歴から引く案もあったが、`WikiCommitBanner` は frontmatter しか読まない設計であり（`WikiCommitSources` ともども `.wikicommit/schema/` すら読まない）、ラベル 1 つのために `convert_wikilinks.py` へ git 読み取りを持ち込むことになるため採らなかった。
>
> **値は login であって表示名ではない**。トレーラーは `Reviewed-by: <表示名> <<login>@users.noreply.github.com>` の形で両方を持つが、frontmatter に入れるのは login のみとする — 安定した識別子であり、`https://github.com/<login>` というプロフィールへのリンクをバナーがそのまま組み立てられる。表示名は本人がいつでも変更でき、ページ側のコピーだけが古くなる。
>
> `validate_frontmatter.py` は `generated_by` と同じく「フィールドが存在する場合に空文字列不可」だけを検証する。login の形（`[A-Za-z0-9-]`）への照合は行わない — モデル ID を正規化表に照合しないのと同じ理由（§6.7）で、形式検証は将来の正しい値を拒否する側にしか働かない。
>
> **遡及付与は行わない**。この機能追加より前にレビューされたページはフィールドを持たず、バナーはレビュアー名なしの現行表示にフォールバックする（空のラベルや `unknown` プレースホルダーは出さない — 未レビューページの `generated_at`/`generated_by` が `unknown` を出すのとは扱いが異なる。生成ページは必ず生成を経ているため値の欠落は埋めるべき穴だが、レビュアーの欠落は**正常な状態**である）。経路 B（`wikicommit-review` がローカルで `reviewed` を書く）や、`review-issue-close-sync.yml` を配置していない Wiki でも同様にフィールドは付かない。
>
> **`reviewed_by` を消す経路（Issue #705）**: このフィールドを書く主体は `review-issue-close-sync.yml` だけなので、`review_status` が `reviewed` から離れるとき（`/wikicommit-generate --regenerate` が `pending` に戻す場合や、再レビューのために人間が手で `pending` に書き戻す場合 — `docs/DesignDoc-pipeline.md` §6.2 が未決事項として残した操作）に、かつては値を消す経路がどこにも無かった。`pending` の間はバナーが `reviewed` 分岐に入らないため表示されないが、**その後そのページが経路 B で再レビューされると、経路 B は `review_status` しか書かないため、前回の経路 A のレビュアーが新しいレビューの主として表示される**という穴があった。
>
> Issue #705 で `set_frontmatter_field.py` に `--unset KEY`（キーが無ければ no-op）を追加し、**経路 B（`wikicommit-review` Step 5）が `review_status: reviewed` を書く同じ呼び出しで `reviewed_by` を消す**ようにして解消した。`--require` は `--set` と `--unset` の両方へ一括で掛かるため、1 回の呼び出しが 1 ページに対する 1 つの原子的な書き換えである、という契約は変わらない。**経路 B に login を書かせる案は採っていない** — 経路 B はローカル実行であり、GitHub の認証済み login を得る手段が無い（git の author は自己申告であり、Issue #663 が login を選んだ理由と噛み合わない）。
>
> **再生成（`--regenerate`）も同様に `reviewed_by` を残さない**が、こちらは `--unset` を使わない — Pass 3 がページ全体を書き直すため、出力に含めなければそれで消える。**ただし無変更時の弁が `review_status: reviewed` を維持した場合は `reviewed_by` も維持する**: そこで名前だけを落とすと、「このページは実際に人間がレビューした版のままである」という弁が守ろうとしている事実を片側だけ壊すことになる。`reviewed_by` の扱いは常に `review_status` の扱いに従わせる。
>
> **経路 A（`review-issue-close-sync.yml`）は変更していない** — `review_status` を書き換えた後に`--require` なしの無条件 `--set` で `reviewed_by` を上書きするため、元から自己修復する。**既存の公開済みリポジトリの遡及修正も行わない**（本ドキュメント群が一貫して採る「新旧混在を許容する」方針）。既に古い `reviewed_by` を抱えたページは、次に経路 A で再レビューされるか、人間が `/wikicommit-fix` で直すまで残る。

**ページ本文に H1 を置かない（Issue #546）**: Wiki ページの本文（frontmatter 以降）は段落または `##` 見出しから始め、`# <タイトル>` という H1 行を置かない。ページのタイトルは frontmatter の `title` が持ち、Quartz の既定レイアウトがそれを `ArticleTitle` コンポーネントとしてページ見出しに描画するため、本文の H1 は公開ページ上で見出しを二重にする。`.wikicommit/schema/` の全型テンプレート（`default.md` 含む）の本文部が H1 を1つも持たないことがこの慣習の実体であり、`wikicommit-generate` / `wikicommit-translate` の出力はテンプレートに従うため自然に守られていた。一方 `wikicommit-synthesize` はテンプレート本文を経由せず本文を組み立てる唯一の Skill で、その SKILL.md Step 5 が「`<topic>` を文書先頭の見出しにする」と明示的に指示していたため、`.wikicommit/entity/` 配下で本文に H1 を持つページが 1 件だけ生まれていた（`dev/pilot-ai-driven-dev-wiki-round5.md`）。Issue #546 でこの指示を禁止形に置き換え、あわせて `wikicommit-generate` Pass 3 にも同じ禁止を明記した — 指示を消すだけでは、慣習がテンプレートの実物にしか書かれていない以上 LLM が H1 を書き戻す余地が残るため。

明文化の場所をこの節（frontmatter 仕様の近傍）にしたのは、この慣習が本質的に「タイトルは frontmatter の `title` が持つ／本文は持たない」という役割分担の裏返しだからである。各型テンプレートの本文冒頭にコメントとして書く案は採らなかった — テンプレートの本文は生成ページの雛形としてそのままコピーされるため、注記が生成ページ側へ漏れる。`tests/test_schema_template_no_h1.py` が全型テンプレートに H1 が無いことを CI で検証し、慣習の実体そのものの回帰を止める。レンダリング結果（公開サイトでの見出し二重化）の目視確認は本リポジトリに Quartz 本体が無いため（Issue #81）未実施であり、実害の有無に関わらず「ページ本文の構造が Skill によって不揃いになること自体を避ける」ことが本ルールの根拠である。

> **`properties:` の値を WikiLink 化する判断基準（Issue #496）**: 上の例の `affiliation: "[[Organization/companya]]"` は単なる書いてよい例示ではなく、Schema.org の `rangeIncludes`（その property の値が取りうる型）に基づく体系的な判断の結果である。`rangeIncludes` は property ごとに、リンク可能なエンティティ型（例: `affiliation` → `Organization`）・単純なスカラー値を表す DataType（`Text`/`Number`/`Boolean`/`Date`/`URL` 等。例: `sameAs` → `URL`）・両方の混在（例: `jobTitle` → `DefinedTerm` または `Text`。`description` → `TextObject`〈名前に反しエンティティ型 — `subClassOf: MediaObject` であり DataType ではない〉または `Text`）のいずれかを宣言している。`.wikicommit/scripts/check_schema_org_type.py --show-range`（`_schemaorg_vocab.py` の `entity_range_candidates()`／`is_in_datatype_lineage()` を使用）がこの分類を機械的に照会できる ── DataType 判定は `@type` に `schema:DataType` を直接持つ型だけでなく、`rdfs:subClassOf` の祖先チェーンを辿った間接的な DataType 系列（`URL` は直接タグを持たないが `subClassOf: Text` 経由で DataType）も含める。`wikicommit-generate` Pass 3 がエンティティ型候補と判定された property の値について、それが独立ページとして存在する（べき）エンティティを指す場合に `[[Type/slug]]` 形式で書くかどうかを判断する（詳細な判断基準は `docs/DesignDoc-skills.md` §11.6 Pass 3 参照）。これは生成時の判断であり、`validate_frontmatter.py` は property の値が WikiLink 形式であることを強制しない（Issue #495 の `domainIncludes` 検証はキーの所属のみを検証し、値の形式は対象外）。
>
> 参照先ページがまだ存在しなくても WikiLink を書いてよい ── `check_wikilinks.py`（未解決リンクは WARNING、Issue #340）・`check_orphans.py`・`check_wanted_pages.py`（WANTED ページとして追跡）はいずれもファイル全体を生テキストとして `WIKILINK_RE` でスキャンしており、frontmatter と本文を区別しないため、frontmatter の `properties:` 内に書かれた WikiLink も本文中の WikiLink と全く同じ扱いを受ける（この3スクリプトへの変更は本 Issue では不要だった）。

### 4.2 翻訳ページのフロントマター

`translated_from` フィールドの有無が原文と翻訳を区別する唯一の判定基準。

```yaml
---
title: "Taro Yamada"
lang: en
type: "schema:Person"
tags: [engineer, ml]
translated_from: .wikicommit/entity/ja/Person/yamada-taro.md  # 直接の親ページ
source_commit: abc123def456abc123def456abc123def456abc123de  # 翻訳元の親ページのコミットハッシュ（40文字）
translated_at: "2026-06-21"
translated_by: "claude-sonnet-4-6"  # 任意: 翻訳実行モデル ID。generated_by と同じ自己申告パターン（Issue #453）
translated_with: "0.1.0"           # 任意: この翻訳を生成した WikiCommit 自身の版（Issue #577。generated_with の対）
translator_notes:  # 任意（Issue #524）: 次回の全文再翻訳が保持すべき翻訳固有の手直しメモ
  - "2026-06-22: Keep 'Senior Engineer' for jobTitle, not 'Chief Engineer' — confirmed against the company's official English title list."

properties:
  description: "Senior engineer at CompanyA..."
  affiliation: "[[Organization/companya]]"
---

Taro Yamada is a senior engineer at CompanyA...

## Background
...
```

`translator_notes`（Issue #524）は `/wikicommit-translate` の全文再翻訳（`docs/DesignDoc-pipeline.md` §6.4）が既存の翻訳を一切コンテキストに渡さない完全ブラインドな設計であることに由来する。原文が別件で更新されて再翻訳が走ると、翻訳ページのみに加えた手直し（`/wikicommit-fix` 経由）は黙って上書きされて消える — この防止策として、ソース管理ファイルの `## User Notes`（§4.3。`wikicommit-generate` が読むが上書きしない、実証済みのパターン）を翻訳ページに横展開したもの。任意フィールドでありフロントマターの必須項目ではない（`validate_frontmatter.py` の必須フィールドチェックには影響しない。フォーマット制約は `docs/DesignDoc-ScriptSpec.md` §「翻訳ページ追加フィールド」参照）。値は文字列のリストで、各要素は `YYYY-MM-DD: <note>` 形式（先頭に日付を付ける。複数エントリが同じ論点に触れる場合、より新しい日付のエントリを優先する — 明示的な削除・上書きは行わず、常に末尾に追記する）。

`## User Notes`（本文の Markdown 見出しセクション）ではなく `translator_notes`（フロントマールのリストフィールド）という異なる形式を採用した理由（`/code-review --fix` のレビューで指摘。当初は `## Translator Notes` という本文見出しセクションとして実装していたが撤回した）:

- **公開範囲**: `.wikicommit/entity/` の Wiki ページ本文は `convert_wikilinks.py` により選別なくそのまま `content/` へ書き出され、読者に公開される。`## User Notes` はソース管理ファイル（`.wikicommit/source/`）に置かれ、そこから公開ページを作る `_write_source_page()` が描画する節を**ホワイトリストで限定している**ため公開されない一方（Issue #831 — この根拠はかつて「管理ファイルは非公開・内部管理用だから」と書かれていたが、Issue #476 が管理ファイル 1 件につき公開ページ 1 枚を作るようにした時点で偽になっていた。`translator_notes` をフロントマターに置くという結論は変わらない）、翻訳ページの本文に同じパターンを置くと、翻訳プロセスの内部メモ（「'Chief Engineer'ではなく'Senior Engineer'を維持」等）がそのまま読者向けページに表示されてしまう。
- **本文を読む全ての下流機能への意図しない漏洩**: 本文見出しセクションのままだと、`search_index.py`（FTS5全文インデックスが本文全体を対象とするため、メモ中の「不採用にした訳語」が検索結果に紛れ込む）・`wikicommit-ask`（本文をLLMコンテキストに注入する設計のため、読者への回答にメモの内容が漏れ得る）・`wikicommit-review`（本文の主張をソース文書と逐一照合するため、翻訳プロセスに関するメモをソース未収載の主張と誤判定しかねない）のいずれにも、本文と区別する仕組みが無い。フロントマターのフィールドであればこれらはいずれも影響を受けない（frontmatterを対象にしないため）。
- **`translated_by`/`translated_at`/`source_commit` との一貫性**: これらは既にフロントマタートップレベルの WikiCommit 独自ブックキーピングフィールド（Issue #495。Schema.org 語彙とは無関係なため `properties:` に入れない）であり、`translator_notes` も同種の性質を持つ。同じ場所に置くことで一貫性が保たれる。

#### 合成ページのフロントマター（`derived_from`）

`/wikicommit-synthesize`（Issue #283。`generate` が外部ソースから、`synthesize` は既存 `entity/` ページ群から新規ページを作る）が出力するページのフロントマター仕様。`derived_from` フィールドの有無が、この合成ページと通常ページを区別する判定基準（`translated_from` と同じ位置付け）。

```yaml
---
title: "Synthesized Topic"
lang: ja
type: "schema:DefinedTerm"
review_status: pending
generated_at: "2026-07-19"
generated_by: "claude-sonnet-5"
derived_from:
  - path: .wikicommit/entity/ja/Person/yamada-taro.md
    source_commit: abc123def456abc123def456abc123def456abc123de
  - path: .wikicommit/entity/ja/Organization/companya.md
    source_commit: def456abc123def456abc123def456abc123def456ab
---
```

`derived_from` は `translated_from`/`source_commit`（単一の出自元パス＋コミットハッシュ）パターンを複数ソースに拡張したもので、`{path, source_commit}` の配列を取る。`sources` との関係も `translated_from` と同じ扱い: `derived_from` を持つページは `sources` の必須を免除する（出自は `derived_from` が表すため）。各エントリの `source_commit` が指す出自ページが後から更新された・削除されたことの検出は `check_derivation_freshness.py`（`STALE`/`MISSING_SOURCE` を出力。`check_translation_status.py` の `STALE`/`MISSING_SOURCE` ロジックを配列用に切り出した新規スクリプト）が行う。詳細は `docs/DesignDoc-ScriptSpec.md` を参照。

### 4.3 `.wikicommit/source/` 管理ファイルのフォーマット

`/wikicommit-generate` が生成するソース管理ファイル。ソース 1 つに対して 1 ファイル。

| ソース種別 | コマンド例 | 管理ファイル生成先 |
|---|---|---|
| リポジトリ内のファイル | `/wikicommit-generate raw/paper-2024.pdf` | `.wikicommit/source/path/raw/paper-2024.pdf.md` |
| リポジトリ内のファイル | `/wikicommit-generate src/auth.py` | `.wikicommit/source/path/src/auth.py.md` |
| 外部 URL | `/wikicommit-generate https://example.com/article` | `.wikicommit/source/url/example.com/article.md` |

> **`type: path` の導出規則が元の拡張子を保持すること・同一性キーが `source.path` であること**（Issue #573）: `mgmt_path_for_file()` は当初 `Path.with_suffix(".md")` で拡張子を**置き換えて**いたため、`raw/paper.pdf` と `raw/paper.docx` が同じ `.wikicommit/source/path/raw/paper.md` に解決されていた。`type: url` 側（Issue #572）が衝突時に `SKIP` を返して止まるのに対し、`type: path` 側は既存管理ファイルとのハッシュ不一致経路に入り、**既存管理ファイルを `status: outdated` に書き換えて `UPDATED` を返す**。結果として、(1) `paper.docx` はどこにも登録されないまま出力上は成功に見え、(2) 変更されていない `paper.pdf` が「ソースが変更された」と誤マークされ、(3) 次の `/wikicommit-generate` 実行で PDF の方が再処理される、という条件なしの silent wrong-source が成立していた（`check_ingest_freshness.py` が `source.hash` を意図的に保持する設計とも噛み合わず、`outdated` の意味が「ソースが変わった」ではなくなる）。同名・拡張子違いのファイルが並ぶケース（`report.pdf` と `report.docx`・`slides.pptx` と `slides.pdf`・`auth.py` と `auth.pyi`）は珍しくなく、`--include "**/*"` によるディレクトリ一括登録では個々のファイル名を意識しないまま踏みうる。
>
> 対応は Issue #572 と同じ2本立て。(1) 導出規則を「拡張子を置き換える」から「元の拡張子を保持して `.md` を付け足す」に変更した（`raw/paper.pdf` → `.wikicommit/source/path/raw/paper.pdf.md`）。管理ファイルパスがソースパスと1対1に対応するため衝突が構造的に起こらなくなり、管理ファイルを見ただけで元ソースの種別も分かる。(2) `process_file()` の同一性判定を導出ファイル名から `source.path` の実走査（`find_mgmt_file_for_path()`）に移した。
>
> **`type: url` 側（Issue #572）と違い、この導出規則の変更は既存リポジトリの全 `type: path` 管理ファイルの導出結果を変える**（URL 側はクエリを持たない URL の導出名が変わらない後方互換な変更だった）。それでも自動リネームは行わず新旧混在を許容する（§4.3 冒頭の URL ディレクトリ構造の注記・Issue #191/#192 と同じ方針）— (2) の同一性走査が拡張子なしの旧命名を拾うため、旧名のまま再登録しても二重登録にならず、既存の `status` 遷移（ハッシュ一致で `outdated` → `pending`、不一致で `outdated`）も旧名の管理ファイル自身に対して正しく働く。必要であれば `git mv` で手動移行できる。
>
> **ファイル名が長すぎる場合**: 拡張子を置き換えるのではなく `.md` を付け足す方式は導出名が元のファイル名より 3 バイト長くなるため、ファイル名自体がファイルシステムの 255 バイト上限に近いソースでは書き込みが `OSError` になりうる。URL 側（`url_to_filename()`）と同じく、導出名が上限（`_MAX_STEM_BYTES`）を超える場合はファイル名を切り詰めて `-<sha8>`（`source.path` のハッシュ）を付す。同一性判定が導出名の再計算ではなく `source.path` の走査になったため、この切り詰めは同一性に影響しない。
>
> **導出先が別の `source.path` に占有されていた場合**: 同一性走査で見つからず、かつ導出先に別ソースの管理ファイルがある場合（例: 旧命名で登録された `raw/paper.pdf` の管理ファイル `raw/paper.md` があるところへ、拡張子なしの実ファイル `raw/paper` を登録した場合）は、既存ファイルを一切書き換えず `-<sha8>` を付した代替パスに退避し、その旨を登録結果のメッセージに明示する（Issue #572 の URL 側と同じ扱い）。
>
> **`.wikicommit/source/` ディレクトリ名・`source.type` の値について**（Issue #352。旧 `repository`/`urls` ディレクトリ・旧 `type: file` からの改名）: 両者を貫く唯一の軸は「コンテンツの種類（PDFかHTMLか等）」ではなく「ソースをどう識別するか — ローカルの相対パスか、URLか」であるべきと整理し、`repository/` → `path/`・`urls/` → `url/`・`source.type: file` → `source.type: path` に統一した（判定基準は常に識別子の文字列形状のみで、URLがPDF等のファイルを指していても `type: path` にはならず `type: url` のまま — この判定ロジック自体は変更していない）。`type: file` は必須フィールド `path` とペアになっており（`type` 名とフィールド名が不一致）、一方 `type: url` は必須フィールド `url` とペアになっていた（一致）。`file` → `path` への改名によりこの非対称が解消され、`sources[].path`（既存フィールド名）とも語彙が揃う。
>
> **`url/` の階層構造**（Issue #191）: ホスト名をディレクトリ、URL パス部分をファイル名にする（`add_source.py` の `url_to_filename()`）。`.wikicommit/source/path/` が実ファイルパスをそのままミラーする設計に合わせ、サイトをまたいで管理ファイルが平坦に並び見分けづらくなる問題を避けるため。パスを持たない URL（例: `https://example.com`）は `<host>.md`（`<host>/` ディレクトリの兄弟ファイル）になる。**既存リポジトリの移行**: 自動リネームは行わない。旧フラット命名（例: `example-com-article.md`）の管理ファイルはそのまま残り、新規登録分のみ新しい階層形式になる（両形式が混在することを許容する）。必要であれば `git mv` で手動移行できる（Issue #192 の非 ASCII パーセントエンコーディング対応時と同じ方針）。**`wikicommit-merge` への影響**: 新規ソースファイル検出（[DesignDoc-pipeline.md §6.2](DesignDoc-pipeline.md) ステップ2の3.）は `git status --porcelain -- ".wikicommit/source/**/*.md"` という再帰 glob を既に使っており、ディレクトリの深さ変化に対して変更不要であることを確認済み。
>
> **クエリ文字列の保持と、同一性キーが `source.url` であること**（Issue #572）: `url_to_filename()` は当初クエリ（`?`）をフラグメント（`#`）ごと捨てていたため、クエリでコンテンツを識別するサイト（YouTube の `?v=`・WordPress の `?p=`・論文サイトの `?paperId=` 等）では**異なる URL がすべて同じ管理ファイルパスに解決されていた**。`/wikicommit-collect` で選んだ複数の YouTube 動画を登録したところ1本しか登録されず、残りが `SKIP: already registered` を返す（出力上は成功に見えて実際は未登録）という形で発覚した。さらに危険な派生として、1本目が `status: generated` に到達した後に別動画を登録すると `RECHECK` が返り、Pass 1 が管理ファイルの `source.url`（＝**古い方の動画**）を再フェッチして成功として報告する silent wrong-source が成立していた。
>
> 対応は2本立てで、どちらか一方では不十分だった。(1) `url_to_filename()` がクエリを捨てずサニタイズして stem に含める（`watch?v=abc` → `watch-v-abc`。クエリを持たない URL の導出結果は変わらないため後方互換）。長いトークン付きクエリで stem がファイル名長の上限（255バイト）を超える場合は、正規化後 URL の SHA-256 先頭8桁を付して切り詰める。(2) **同一性判定をファイル名から `source.url` に移す** — `process_url()` は `.wikicommit/source/url/` 配下を実走査し、`source.url` が一致する管理ファイルを探してから `SKIP`/`RECHECK` を判定する。これは参照側の `resolve_source_cache_path.py`（Issue #470）が先に採っていた方式と同じで、登録側だけが導出ファイル名を同一性キーとして使い続けていた構図を解消するもの（`docs/DesignDoc-skills.md` §11.5）。(1) だけではサニタイズによる名前の潰れ・切り詰め後の衝突が残るため、(2) が将来の同種の衝突すべてに対する安全網として独立に必要になる。
>
> 同一性走査を入れたことで**既存リポジトリの自動移行が不要になった**: 旧フラット命名（Issue #191 以前）・旧パーセントエンコード命名（Issue #192 以前）・本 Issue 以前にクエリを落として作られた管理ファイルのいずれも走査でヒットするため、`git mv` しなくても二重登録にならない（ファイル名導出ロジックを今後変更しても既存リポジトリが壊れない、という副次的な性質も得られる）。登録されないまま失われていた2本目以降の URL は、単に `/wikicommit-generate` を再実行すれば新しい導出名で正しく登録される。
>
> **トラッキングパラメータの正規化**: `utm_*`・`fbclid`・`gclid` 等の既知トラッキングパラメータは、ファイル名導出と同一性比較の**内部でのみ**除去し、残りのクエリをキー順にソートする（フラグメントも除去する）。`source.url` frontmatter にはユーザーが渡した URL をそのまま書く（hash・来歴の verbatim 性は変えない）。クエリを丸ごと落としていた旧実装が `article?utm_source=x` と `article` を偶然 dedup していた望ましい挙動を、意図的な仕様として維持するため。denylist は完全にはならないが、取りこぼしの劣化は「管理ファイルが2つできる」で済み silent wrong-source にはならない。ホスト・パスの正規化は行わない — 同一コンテンツを別形式の URL で登録した場合（`https://youtu.be/<id>` と `https://www.youtube.com/watch?v=<id>`）に二重取り込みになる「別名重複」は、サイト固有の知識を要するため本 Issue の対象外とした。
>
> **導出先が別 URL に占有されていた場合**: 同一性走査で見つからず、かつ導出先に別 URL の管理ファイルが既にある場合（サニタイズによる名前の潰れ・切り詰め後の衝突）は、`-<sha8>` を付した代替パスに退避し、退避したことを登録結果のメッセージに明示する（黙って別名にしない）。ERROR で止める案は、ユーザー側に打てる手が無い（URL を変えられない）ため採らなかった。
>
> **ベアドメインが `<host>/index.md` ではなく `<host>.md` である理由**（Issue #213）: 当初は `<host>/index.md` としていたが、実際にパスが `/index` である URL（`https://example.com/index`。静的サイトのディレクトリインデックスページによくあるパターン）もサニタイズ後に同じ `index.md` へ解決され、異なる 2 つの URL が同一の管理ファイルパスに衝突していた（`process_url()` は既存ファイルの有無だけで CREATED/SKIP を判定するため、後から登録した方が `SKIP: already registered` と誤判定され登録されない）。ベアドメインを `<host>/` ディレクトリと同階層の `<host>.md` に置くことで、実パスを持つ URL（常に `<host>/` の一段下に解決される）とは構造的に衝突し得なくした。
>
> **トップレベルディレクトリ名 `.wikicommit/ingest/` → `.wikicommit/source/`（Issue #476）**: `sources:` フロントマターフィールド・`WikiCommitSources` Quartz コンポーネント・（本 Issue で新設した）`content/sources/` 公開ページと語彙が既に「source」に統一されている一方、「ingest」だけがパイプライン動詞（取り込む、という処理）由来の名前として浮いていたため、トップレベルディレクトリ自体も `source/` に統一した。Issue #352 が行った `repository/`→`path/`・`urls/`→`url/` というサブディレクトリ名の改名とは別軸（あちらは「コンテンツの種類ではなく識別子の形状で分ける」という命名基準の統一、こちらは「ingest という処理動詞ではなく source という語彙で全体を揃える」という統一）。移行は自動リネームを行わず新旧混在を許容する — 同じ前例（`repository/`→`path/` 等）を踏襲する形だが、今回はトップレベルディレクトリそのものの改名であるため、`check_ingest_freshness.py`/`reconcile_ingest_status.py`/`wikicommit-generate` の pending 管理ファイル走査は `.wikicommit/source/` のみを見る（サブディレクトリ改名だった Issue #352 は同じ `.wikicommit/ingest/` 配下の `rglob("*.md")` が新旧両方のサブディレクトリを自動的に拾えたが、トップレベル改名ではその前提が成り立たない）。既存リポジトリで `.wikicommit/ingest/` に登録済みの管理ファイルは、`git mv .wikicommit/ingest .wikicommit/source` で手動移行するまでこれらのスクリプトから見えなくなる。公開Wiki側では、この改名と同じ Issue #476 で `content/<lang>/sources.md`（Wiki ページの `sources:` frontmatter から逆引きする集約ページ、旧 Issue #194/#212）を廃止し、`.wikicommit/source/` を主として全件走査して管理ファイル 1 つにつき `content/sources/` 配下に公開ページ 1 つを生成する方式（`generated_pages` フィールドが既に管理ファイル側にあるため逆引きが不要になる）に置き換えた。詳細は `.wikicommit/scripts/convert_wikilinks.py` の `generate_source_pages()` を参照（このドキュメント群には他に専用の節がない）。
>
> **語彙の統一と、意図的に据え置いた層（Issue #583）**: 上記の改名後も "ingest" という文字列は各所に残っていた。Issue #583 はそのうち **`.wikicommit/source/` 配下のファイルを指す「名詞」としての用法だけ**を `source` 語彙へ寄せ、それ以外は据え置いた。具体的には、プローズの「ingest management file」/「ingest 管理ファイル」/「取り込み管理ファイル」を「source management file」/「ソース管理ファイル」に統一し、Python の内部識別子（`ingest_file`/`ingest_rel`/`ingest_path`/`ingest_root`/`ingest_dir`/`ingest_path_for_file`/`ingest_path_for_url`/`find_ingest_file_for_*` 等）を `mgmt_*` 系にリネームした（`convert_wikilinks.py` が既に `mgmt_file`/`mgmt_rel` を使っており、`source_dir`/`source_root` は同ファイルで**別の対象**〈`.wikicommit/entity/`〉を指しているため、`source_*` ではなく `mgmt_*` を採った）。
>
> **以下は「やり残し」ではなく、変更しないと決めた層である**。統一漏れと誤認して手を出すと、配布済みリポジトリの破損や重複 Issue 起票を招く:
>
> | 据え置いた対象 | 理由 |
> |---|---|
> | 動詞用法（`ingested` / `ingesting` / 「ingest した」「ingest 時に」「再 ingest された」、および「ある1回の取り込み」を指す名詞用法「同じ ingest で」「後の ingest が」） | 本コールアウト自身が認めるとおり ingest はパイプライン動詞由来の語であり、動詞・処理としては現在も正しい |
> | `.wikicommit/.cache/ingest-fetch/` | `.gitignore` 配下で壊れはしないが、変更すると既存キャッシュが1回失効し全 URL ソースの再フェッチが発生する。得られる一貫性に見合わない |
> | `check_ingest_freshness.py` / `reconcile_ingest_status.py` というファイル名 | `init.py` の `copy_tree` は既存ファイルを削除しないため、リネームすると**配布済みリポジトリの `.wikicommit/scripts/` に旧ファイルが孤児として残り続ける**。かつ両者とも「取り込み*処理*の鮮度／状態」という動詞用法として読めば現在の名前で正しい |
> | 上記スクリプトの役割を述べる語（`check_ingest_freshness.py` の argparse `metavar="<ingest-file>"`・`description`、および `CLAUDE.md`・`DesignDoc-CISpec.md`・`DesignDoc-ScriptSpec.md`・`DesignDoc-phases.md` の「ingest ハッシュずれ検出」） | スクリプト名を据え置く以上、その説明文だけ変えると逆に食い違う |
> | レビュー追跡 Issue のマーカー `<!-- wikicommit-ingest: ... -->`（`wikicommit-merge` Step 9） | GitHub 側に永続化済み。変更すると既存の open な `wikicommit-generation-failure` Issue との照合が外れ、**重複起票する** |
>
> 既存パイロットリポジトリへの遡及適用は行わない。スクリプトのファイル名は据え置き対象のため変わらず、プローズ・内部識別子の変更は配布物の挙動に影響しない。

```yaml
---
source:
  type: path                              # path | url | wikicommit
  path: raw/paper-2024.pdf
  hash: sha256:abc123def456...
  license: CC-BY-SA-4.0                   # 任意（Issue #558）。不明なら値なしの空欄
  lang: ja                                # 任意（Issue #989）。抽出テキストの主言語（ISO 639-1）。Pass 2a が書く。登録時は空欄

schema: schema:Person    # LLM へのヒント（省略時は LLM が自動判断）
status: generated        # pending | generated | partial | excluded | outdated | failed
last_generated_at: "2026-06-22"
extracted_tokens: 3200    # パス1（テキスト抽出）完了時の抽出テキストの概算トークン数（簡易概算で可。例: 文字数 ÷ 4）。再実行のたびに上書き
generated_pages:
  - .wikicommit/entity/ja/Person/yamada-taro.md
  - .wikicommit/entity/ja/Organization/companya.md
failed_pages: []
# ambiguous_entities:     # 任意（Issue #910）。status: partial かつ型が確定できないエンティティが
#   - title: ...          # あるときのみ書かれ、他のどの結末に到達した時点でもフィールドごと消える。
#     type: ...           # この例は status: generated なので存在しない（受け皿だけ配らない。Issue #553）
#     alternatives: [...]
---

## Summary

（自動生成・`wikicommit-generate` パス 2 実行のたびに上書き）このソースの内容を 2〜3 文で要約する。
**この節にはソースの内容だけを書く** — 今回の実行がそれをどう扱ったかは下の
`## Generation Notes` に分ける（Issue #831。公開されるのは `## Summary` だけである）。
例: "本文書は CompanyA の技術ブログ記事。山田太郎氏の紹介と Project Alpha の概要を含む。"

## Generation Notes

（自動生成・`wikicommit-generate` パス 2c が書く。該当が 1 件も無ければ節ごと作らない。Issue #831）
除外したエンティティ（`theme` 不一致・`entity-policy.md` の許容性方針のいずれも）と
`coverage_gap_note` を 1 エンティティ 1 文で記録する。運用者向けであり公開されない。
例: "「雑談先のXX社」(theme_mismatch): 個人的な取引先であり社内技術ナレッジのテーマと無関係。"

## User Notes

（任意・人間が手書き。`wikicommit-generate` は上書きしない）LLM への追加指示を書く欄。
例: "著者情報のみ抽出し、実験結果はページ化しないこと"

## Failure Reason

（`status: failed` のときのみ存在。`wikicommit-generate` が失敗発生時に上書き作成し、
再試行して `failed` 以外の status に遷移した際は削除する）このソースが `status: failed`
になった理由を1〜数文で記録する。
例: "Text extraction failed: markitdown returned empty output for this PDF."

## Deferred Reason

（非対話実行が人間にしか下せない判断に当たって保留したときのみ存在。Issue #910。
`wikicommit-generate` が書き、そのソースが他のどの結末に到達した時点でも削除する
——`## Failure Reason` と同じ一時セクションであり、同じく `primary_lang` に関わらず英語で書く）
なぜ止まったかを 1〜数文で記録する。**`status` は書き換えない**（`pending` / `outdated` のまま）ため、
ソースはキューに残り、次の対話実行がそのまま拾って人間に尋ねる。
例: "LOW_DENSITY: ... (natural-language character ratio: 0.11, threshold: 0.3) —
non-prose breakdown: links 12%, numbers/tables 71%, other markup 17%."

## Retraction Reason

（`status: retracted` のときのみ存在。**人間が手で書く** — Skill は書かない。Issue #737）
このソースを取り下げた理由を1〜数文で記録する。理由コードの enum は持たない（下記コールアウト参照）。
例: "The 2019 figures in this listing contradict the city's own published statistics;
confirmed with the publisher that the page was never corrected."
```

> **見出しラベル（`## Summary` / `## Generation Notes` / `## User Notes` / `## Failure Reason`）は `primary_lang` に関わらず常に固定の英語（Issue #405）**: 見出しラベルは機械が照合する識別子であって読者が読む散文ではないため、ローカライズしない（本文＝`summary` フィールドの内容は Issue #314 の設計通り `primary_lang` で書く。ローカライズされないのは見出しラベルのみ）。`primary_lang: en` のパイロットで、本文は正しく英語で書かれているのに見出しラベルだけ `## サマリ`/`## ユーザーメモ` と日本語固定になっていたことが判明し、常に固定の英語見出しに統一する方針を採った。既存リポジトリで旧見出し（`## サマリ`/`## ユーザーメモ`）のまま生成済みの管理ファイルに対する自動リネームは行わない — `.wikicommit/source/` の階層構造移行（§4.3 冒頭のURLディレクトリ構造の注記参照）と同じ「新旧両形式の混在を許容する」方針を踏襲し、新規生成・次回上書き分のみ新しい見出しになる。`## Failure Reason` はこの命名規則に揃えた新設セクション（Issue #408。旧設計では `status: failed` の理由がコンソール出力のみで消え、`wikicommit-status` や別セッションから確認する手段が無かった）で、失敗理由の本文自体は `## Summary`/`exclude_note` 等と異なり常に英語で書く（`primary_lang` に連動しない） — 失敗理由は開発者・運用者向けのデバッグ情報であり、読者向け要約とは性質が異なるため。`## Failure Reason` は `status: failed` のときのみ存在する一時的なセクションで、再試行が成功し `status` が `generated`/`partial`/`excluded` のいずれかに遷移したら削除する（解消済みの失敗理由が残り続けて現在の状態と矛盾するのを防ぐため。`.claude/skills/wikicommit-generate/SKILL.md` Pass 1・Pass 3・Pass 4 参照）。
>
> **`## Generation Notes` — 除外理由と `coverage_gap_note` の行き先（Issue #831）**: この 2 つはかつて `## Summary` に追記されていた（Issue #284 / #314）。当時の前提は「ソース管理ファイルは内部用」であり、**その前提は Issue #476 が壊した** — 管理ファイル 1 件につき公開ページ 1 枚を `content/sources/` に作るようにし、`_write_source_page()` が `## Summary` をそのまま載せるようになったためである。前提が偽になったのに追記の行き先が変わらなかった。
>
> **実害は 2 つある**。(a) `exclude_living_persons`（Issue #667）は「その人のページを作らない」ためのスイッチだが、**その適用結果が実名付きで公開サイトに出ていた** — 方針が守ろうとしているものと正面から逆を向く。`wikicommit/ai-driven-dev-wiki` のスモーク 5 本のうち 4 本で発火し、実人数は 11 名だった（記事の共著者・論文の著者を含む）。(b) `.wikicommit/entity-policy.md`・`exclude_living_persons`・`SoftwareApplication.md` の `properties:` といった**内部の識別子が読者向け出力に出ていた**（`docs/DesignDoc-skills.md` §11.8 と同型だが、あちらは SKILL.md のテンプレートが対象なので `tools/check_skill_user_facing_vocabulary.py` の射程外である）。
>
> **`_write_source_page()` は無改修でよい。** 同関数は公開する節を**ホワイトリスト**で持っており（`type` / `original` / `status` / `license` /（取り下げ時のみ）`## Retraction Reason` / `## Summary` / `generated_pages`）、`## User Notes` と `## Failure Reason` は描画しない — **新しい節は何もしなくても非公開になる**。`## Summary` を機械が読むのは `parse_summary_section()` の 1 箇所だけで、同関数の正規表現は次の見出し（`##` 始まりの行）で止まるため、中身を分けても壊れるものが無い。
>
> **本文の節にした理由**: `## Failure Reason` が完全に同型の前例である（Pass が自動で書き、運用者が読み、機械消費者を持たず、公開されない）。フロントマターにする案（`translator_notes` の前例）も成立し「エンティティ名 + `exclude_reason` + 理由」を 1 文に潰さずに済むが、集計する主体を同時に作らなければ空の受け皿が増えるだけになる（Issue #553）。必要になった時点で移せる。
>
> **言語は動かさない**。`exclude_note` / `coverage_gap_note` が `primary_lang` で書かれている理由は、同じ `## Summary` 内で `summary` と言語が混ざるのを防ぐことだった（Issue #314）。別の節に出せばその理由は消えるので、`## Failure Reason` に揃えて固定の英語にする選択もありうるが、**本 Issue では動かさない**（変更点を 1 つに絞る）。見出しラベル自体は上記のとおり固定の英語。
>
> **採らなかった案**: `_write_source_page()` が `## Summary` を出さない（公開ソースページから要約が消え、Issue #476 が `content/sources/` を作った意義が失われる）／追記の文面から実名と内部識別子を落とすよう Pass 2c に指示する（運用者が「誰が落ちたか」を読めなくなり、かつ LLM の指示遵守に依存する）／除外の事実自体は公開し実名だけ伏せる（透明性の価値はありうるが、それは俯瞰ページの集計〈Issue #585 / #769〉の領分であり混ぜない）。
>
> **既存の管理ファイルへの遡及移行は行わない**（本ドキュメント群が一貫して採る方針）。`## Summary` 内で要約と追記が区切られていないため**後から機械的には分離できず**、1 ファイルずつ LLM に読ませることになる。**そして引数なしの `/wikicommit-generate` も自然には直さない** — 全エンティティを除外したソースは `status: excluded`、一部だけ除外したソースは `failed_pages` が空の `status: partial` で止まり、Pass 1 の収集条件（`pending`/`outdated`、および `failed_pages` が非空の `partial`。Issue #567）はそのどちらも拾わない。追記が残っているのはまさにこの 2 状態のファイルであるから、放置すれば公開されたままになる。直すには `## Summary` を手で編集するか、そのソースを名指しで再実行する（`/wikicommit-generate <path|url>`。引数指定の経路は `status` を問わず処理する）。
>
> **`source.license` の埋め方（Issue #558）**: `add_source.py` は管理ファイルの新規作成時に `source.license` を書き出す。値は「明示指定（`--license "<identifier>"`）> 既知ドメイン対応表 > 空欄」の優先順で決まる。対応表（`KNOWN_SOURCE_LICENSES`）は `check_extraction_quality.py` の `KNOWN_JS_SHELL_DOMAINS` と同じ「確認済みのものだけを決定論的な表に持つ」パターンで、そのサイトが自サイトのコンテンツ全体に対して明示しているライセンスのみを登録可能ドメイン単位で持つ（初期値は Wikimedia 系: `wikipedia.org`/`wikisource.org`/`wiktionary.org`/`wikibooks.org`/`wikiquote.org`/`wikivoyage.org` → `CC-BY-SA-4.0`、`wikinews.org` → `CC-BY-2.5`、`wikidata.org` → `CC0-1.0`）。照合はホストの左ラベルを順に落としながら行うため、`it.wikipedia.org` も `ja.wikipedia.org` も `wikipedia.org` のエントリに一致する。
>
> **既存の管理ファイルは書き換えない**。`--license` も対応表も新規作成時にしか働かず、登録済みの管理ファイルの `license` を上書きすることはない（人間が手で直した値を機械が壊さないため）。値を変えたい場合は管理ファイルを直接編集する。`type: path` のソースにはドメインが無いため、対応表は効かず `--license` か手編集のみが値の入り口になる。
>
> **LLM に推定させない**: 抽出テキストからライセンスを推定する経路（Issue #558 の対応方針 2(b)）は採らなかった。ソースのライセンスは事実確認の対象であり、確認していないものを推定値で埋めると、記録があること自体が確認済みの証拠であるかのように見えてしまうため。対応表に無いドメインは空欄のまま残り、`wikicommit-generate` の Step 0 が「不明であること」と値の入れ方をユーザーに伝える。
>
> **`source.lang` — 抽出テキストの主言語（Issue #989）**: `wikicommit-generate` の Pass 2a が抽出テキストを全文読む際に、**主として書かれている言語を ISO 639-1 で 1 つ**答え、その場で `source.lang` に書く。`add_source.py` は登録時に空の `lang:` を置く（言語は登録時には分からない。空のキーを置くのはフィールドの存在を伝えるためと、Pass 2a が既存の行を埋めるだけで済むようにするためで、消費者＝俯瞰ページの言語別集計が同じ変更で入っているので受け皿だけ配る形〈Issue #553〉には当たらない）。
>
> **出発点は運用中の訴えである** — `wikicommit/ai-driven-dev-wiki` に英語以外のソースを足していく過程で、どのソースが何語かを知る手段がどこにも無いことが分かった。2026-09-21 の公開サイト（`primary_lang: en`・511 ページ・URL ソース 284 件）では 66 ホスト中**少なくとも 19 ホストが非英語**（`ja` 11・`zh` 4・`ko` 4・`de` 推定 1）で、それらは 1〜3 件の裾にいるため俯瞰ページのホスト別表（`OVERVIEW_HOST_LIMIT = 20`）で 11 ホストが切り落とされていた。**ホスト数は青天井だが言語数は有界**なので、言語別集計は切り詰めを生き延びる唯一の集約になる。しかもホスト名から言語は導けない（`toss.tech` が韓国語であることはそのドメインを知る人間にしか分からない）。**先行する測定は正反対の結論を出していた** — 起票の初稿は手元のクローン（URL ソース 164 件・41 ホスト・非英語 0）を測って「全パイロットで 1 行になる」と書いたが、それは多言語化より前のスナップショットであり、増えた 25 ホストのうち 19 が非英語だった。どのスナップショットを測るかで答えが反転することの記録として残す。
>
> **判断の性質を変えた**。Issue #336 の判断は「`primary_lang` と明白に違うか」を旗立てるだけで、微妙なものは旗を立てなかった。これをそのまま永続化すると**欠如が「同じ」と「微妙」の 2 つを指す**（Issue #519 / #577 が繰り返し避けてきた形）。「主としてどの言語か」は外国語の固有名詞や引用が混ざっていても答えられるので微妙の行が消え、**欠如は「まだ記録されていない」1 つの意味だけを持つ**。`mul` や「判定不能」の値は置かない — 置けば欠如の意味が再び割れる。
>
> **`source.license` が LLM 推定を禁じた（上記）こととは区別できる**。ライセンスは文書の**外**にある法的事実で、確認には別の表示を読む必要がある。言語は**テキストそのものの性質**であり、LLM がいま読んだテキストがそのまま証拠になる — 証拠拘束ルール（Issue #442）の下でも証拠の外に出ていない。決定論的な経路（`<html lang>`・`Content-Language`）は採らない: 自己申告でよく誤っており、`type: path` と PDF には無く、LLM 判断と併存させると値の出所が 2 つになる。`check_extraction_quality.py` の `CJK_CHAR_WEIGHT` も文字クラスの重みであって `ja` と `zh` を分けられない。
>
> **厳密には「文書の言語」ではなく「抽出テキストの言語」である**（partial extraction〈Issue #574 / #715〉では両者がずれうる）。それでも `source:` の下に置くのは、`source.hash` が既に同じ曖昧さを持つからである（`type: url` は抽出テキスト、`type: path` は生ファイルのハッシュ。Issue #885）。
>
> **書き込み点は Pass 2a である**（判断と書き込みが同じ手順にあれば drift しない）。Pass 4 手順 7 に寄せると、Pass 2b の保留（Issue #910）や `status: failed` のように Pass 4 に到達しない経路で、既に分かっている言語が失われる。**Pass 1 での保留（ガード A）では言語は分からない**（Pass 2a に到達しない）— 正しい挙動であり、そのソースは未記録のままキューに残る。Completion Notice の不一致ロールアップ（Issue #336）は残す — 永続化とその場の通知は別の役目である。
>
> **ページの `sources[]` へは転記しない**。`license` が転記されたのは公開ページの出典ボックス（`WikiCommitSources.tsx`）が frontmatter しか読まないためで、本フィールドの消費者は管理ファイルを直接読む俯瞰ページ 1 本である（`docs/DesignDoc-publish.md` §8.8.1）。値は ISO 639-1 のコードのまま表示し、言語名へのローカライズはしない（すれば全ラベル辞書に言語名の対応表が要る）。**`/wikicommit-status` にも足さない** — 多言語であること自体は欠陥ではなく、常時点灯する所見になる（Issue #562 / #864 / #867）。公開ソースページ（`_write_source_page()`）に 1 行足すかは本 Issue では決めない — `## Summary` が `primary_lang` で書かれるため日本語ソースのページが全編英語に見えるという実例があり、「読者は URL で分かる」という理由で閉じてはならない。
>
> **遡及付与は行わない**（新旧混在を許容する慣例）。しかも `extracted_tokens` と違い**再実行でも付くとは限らない** — `status: generated` のソースは Pass 1 の収集条件に乗らないため、`/wikicommit-generate <url>` の強制リチェックか `/wikicommit-reconcile` の requeue を経るまで空のまま残る。導入直後の `ai-driven-dev-wiki` では URL ソース 284 件すべてが未記録になる。**したがって俯瞰ページは未記録を隠さず 1 行として出す** — 隠すと、英語ソースだらけの Wiki が記録済みの少数の言語だけでできているように見える。

`status` の遷移：

| status | 意味 | 設定タイミング |
|---|---|---|
| `pending` | 管理ファイル作成済み・未生成（または再生成待ち） | `wikicommit-generate` 実行時（新規登録、またはハッシュ不一致による再登録） |
| `generated` | 1 件以上のページを生成し、生成失敗も `ambiguous` も無い（ポリシー除外は混ざっていてよい。Issue #992）・ハッシュ一致 | `wikicommit-generate` 完了時（失敗なし） |
| `partial` | 生成失敗または `ambiguous`（型確定待ち）のエンティティが残っている。**`failed_pages` の空／非空で区別する**（Issue #567）— 非空は再試行で、空は人が型を確定すれば進む。Issue #992 より前は一部除外もここに来ていた（下記コールアウト参照） | `wikicommit-generate` 完了時（部分失敗、または ambiguous あり） |
| `excluded` | 全エンティティが除外され、生成ページが 0 件（除外理由は問わない — `theme` 不一致・`entity-policy.md` の許容性方針のどちらでもこの値になる。Issue #667） | `wikicommit-generate` 完了時（`action: exclude` による全除外。`failed` とは異なりページ生成自体は試みていない） |
| `outdated` | ソースが変更された（ハッシュ不一致） | `check_ingest_freshness.py`（`wikicommit-status` Skill）が自動検出して書き換える |
| `failed` | 全ページ生成試行したが失敗 | `wikicommit-generate` 失敗時（`## Failure Reason` に理由を記録。Issue #408） |
| `retracted` | 取得は完全だったが**内容が信用できない**と判断され、以後の取り込み対象から外された | **人間が手で書く**（`## Retraction Reason` に理由を記録。Issue #737。下記コールアウト参照） |

> **`retracted` — 登録済みソースを取り下げる（Issue #737）**: 登録済みのソースが誤っていると分かっても、それを記録して以後使わないようにする経路がどこにも無かった。`/wikicommit-remove` はページ専用（`remove_page.py` は `.wikicommit/source/` を 1 度も参照しない）、`wikicommit-fix` は本文を直す Skill で `sources` を編集せず、`source-policy.md` の `rejected:` は**どちらの消費者も登録の手前でしか働かない**（`/wikicommit-collect` Step 5 が候補を落とし、`/wikicommit-generate` Step 0 が登録前に確認を求める）ため、既に管理ファイルがあるソースには効かない。
>
> **これは偶然ではなく構造による**。証拠拘束ルール（Issue #442）は機械に「ソース文書の literal text だけで判定せよ」と命じており、**その規律の下ではソースを疑うことは定義上できない** — ソースは判定の基準であって判定の対象ではない。Issue #566 の「ソース間の食い違いでは主題を自分の主題として扱っている側を採る」が唯一の例外だが、2 件以上のソースが同じ事実について食い違っている場合にしか働かず、単一ソースの誤り・全ソースが同じ誤りを共有する場合には届かない。したがって「このソースは誤っている」は、証拠拘束が機械に禁じている外部知識を持ち込める**人間にしか言えない**判断である（Issue #723 が害とレビュアー固有の知識について確立したのとまったく同じ理由）。既存の 3 ガード（Issue #425 / #574 / #715）は**取得が壊れている**ソースを検出するもので、**取得は完全だが内容が誤っている**ソースは対象外である。
>
> **`excluded` / `failed` との違いは「判定の主体」で分かれる**:
>
> | status | 何が起きたか | 判定者 |
> |---|---|---|
> | `failed` | 取得できなかった | 機械（3 ガード） |
> | `excluded` | 取得できたが、書くべきエンティティが 1 件も無かった | 機械（`theme` / `entity-policy.md`） |
> | `retracted` | 取得できたが、**内容が信用できない** | **人間のみ** |
>
> `excluded` は**ソースへの評価ではない**（ソースは正しいが、そこに現れるエンティティがこの Wiki の対象外だった）。`failed` は**取得**の問題である。`retracted` だけが人間にしか書けない値であり、これは証拠拘束の下で機械がソースを疑えないことの、`status` の並びにおける現れである。
>
> **採らなかった 2 案**（決め手は**再登録の防止**である。管理ファイルが残れば `add_source.py` の同一性走査〈`find_mgmt_file_for_url()` / `find_mgmt_file_for_path()`。Issue #572 / #573〉がその URL・パスを拾うので、同じソースが後からもう一度登録されることを**構造的に**止められる — これは新しい `status` 値に固有の利点で、他の 2 案には無い）:
>
> - **(a) ソースを削除して再生成**: 「なぜ消えたか」が commit message にしか残らず、半年後に同じ URL がまた登録されるのを何も止めない。しかも `.wikicommit/source/` が「このリポジトリが何を見たか」の記録である以上、見て捨てた事実だけが消える
> - **(c) `source-policy.md` の `rejected:` を登録済みにも効かせる**: あのリストは候補を落とすためのもので、既存の管理ファイルはそのまま残り Pass 1 が拾い続ける。加えて既に生成されたページに対して何をすべきかを何も言わない
>
> **値の名前を `rejected` にしない**。`source-policy.md` の `rejected:` は**候補段階**の記憶であり、同じ語を別の層で別の意味に使うと後から読む人が混同する（このリポジトリが `ingest` / `source` の語彙統一〈Issue #583〉で払ったコストと同じ形）。
>
> **理由は散文で残し、理由コードを足さない**。`## Failure Reason`（Issue #408）と同じ形で `## Retraction Reason` セクションを置く。`removed_reason` のような enum（`inaccurate` / `license` / …）は**足さない** — Issue #553 / #564 が繰り返し確立した「消費者と同時にキーを足す・受け皿だけ先に配らない」に反するためである。本 Issue の範囲では機械は報告しかしないので、理由で分岐する消費者がいない（`entity-policy.md` が enum ではなく散文を人間に書かせているのと同じ論法）。ライセンス条件の読み違い・保護期間の誤認による取り下げ（Issue #558 / #570 が登録時の記録と警告を扱う一方、登録後に判明した場合の経路が無い）も同じ機構に乗る — 内容の誤りと違い公開を止める緊急性がありうるが、それは `/wikicommit-remove` が既に担う。理由によって取るべき行動が違うことは、機械が分岐する理由にはならない。
>
> **既に生成されたページには触れない（報告に留める）**。`ORPHAN` / `page_at_fault: "other"` / `coverage_gap_note` と同じ「報告するがブロックしない」形を採る。`review_status` を `pending` に戻す案を採らない理由が 2 つある: (1) **Issue #724 の規範と噛み合わない** — あちらは「内容が実際に変わったか」を決定論的スクリプト（`reset_review_on_content_change.py`）に委譲し、「人間のレビューが要るか否かを非決定論的な判定に委ねない」と明記した。ソースの取り下げでは**内容が変わらない**（変わるのはその内容の根拠である）ため、同じスクリプトでは扱えず判定も決定論的にならない。(2) **戻しても何が失われたかは伝わらない** — 追跡 Issue のテンプレートは `sources` の妥当性を問わない（まさに本 Issue の出発点）ため、`pending` は「読み直せ」とは言うが「何を直せ」を言わない。取り下げの実行そのものは既存 3 経路の組み合わせで足り、新しい削除機構は要らない: 残りのソースで作り直すなら `/wikicommit-generate --regenerate`（取り下げたソースとその `sources[]` エントリを落として作り直す。**この挙動は Issue #744 が入れたものであり、Issue #737 の時点では `sources:` の全エントリを再取得する設計だったため、この経路は実際には機能していなかった**）、記述を手で直すなら `/wikicommit-fix`、ページごと下ろすなら `/wikicommit-remove`。**どれを使うかは人間の判断**であり、機械は差分を出すに留める（Issue #713 が `/wikicommit-update` で採ったのと同じ形）。`check_retracted_sources.py`（`docs/DesignDoc-ScriptSpec.md`）が `retracted` なソースを `sources[]` に持つページを列挙し、`wikicommit-status` Step 12 が報告する。
>
> **実装が必ず当たる 3 つの穴**（いずれも上記の決定から直接は出てこない）:
>
> 1. **`check_ingest_freshness.py` が取り下げを黙って解除する**。同スクリプトは `type: path` の hash 比較で `generated` / `partial` を `outdated` に書き換える（副作用あり）。`retracted` を対象に含めると、**ソースファイルを 1 バイト触っただけで `outdated` に戻り、Pass 1 の収集対象へ復帰する**。`reconcile_ingest_status.py` が `outdated` を意図的に対象外にした（Issue #474）のと同型の除外を `CHECKABLE_STATUSES` に明記してある（`add_source.py` の `process_file()` も hash 比較より前に返すことで同じ穴を塞ぐ）
> 2. **`add_source.py` が `SKIP: already registered` を返して黙って何もしない**。`process_url()` の分岐は `generated` / `failed` / `excluded` を `RECHECK`、`partial` を `failed_pages` で分け、**それ以外をすべて `SKIP` に落とす** — `retracted` がここに落ちると「既に登録済み」としか言われず、**なぜ使えないのかが伝わらない**。新しい結果コード `RETRACTED:` を返し、`## Retraction Reason` を引用して人間に伝える（`process_file()` 側も同様）
> 3. **公開サイトの source ページは残して取り下げを表示する**。`generate_source_pages()` は全管理ファイルを `content/sources/` へミラーする。**これは残すのが正しい** — 「この Wiki はこのソースを使っていたが取り下げた」は公開されるべき記録であり、GitOps（すべての状態変化をコミットとして記録する）とも整合する。`status: removed` なページを `content/` に一切書き出さない（Issue #271）のとは**要求が逆**であることに注意する（あちらは直接 URL でアクセスできる状態を消すのが目的だった）。したがって必要なのは削除ではなく**表示の追加**であり、`_write_source_page()` が取り下げの明示と `## Retraction Reason` を描画する
>
> **4 つ目の穴は参照側にある。Issue #918 がそのうち 1 経路を塞ぎ、Issue #928 が残り 2 経路を塞いだ**（後者は次の段落）。上の 3 つはいずれも取り込み側の穴であり、`/wikicommit-ask --include-source`（Issue #470）が取り下げ済みソースのキャッシュを読んで**回答の根拠として注入する**ことは誰も止めていなかった。取り込み側のガードは登録と再キューを止めるだけであり、既に書かれたページはそのソースに忠実なので `validate_frontmatter.py` も Pass 4 も通り、`check_retracted_sources.py` が報告するのは**ページ**であってその場で組み立てられている回答ではない。`resolve_source_cache_path.py` が `RETRACTED:` 行と **exit code 2** で答え、`wikicommit-ask` の 2 経路（`type: path` / `type: url`）がそれを分岐する。**exit 1 に畳めない** — あちらは既に 2 つの意味を畳んでおり、しかも `type: path` の経路では呼び出し側が exit 1 を**生ファイルを読む**ことで答えるため、キャッシュを持たない取り下げ済みソースがそのまま素通りする。同じ理由で `status` の確認は**キャッシュを探すより前**に置く。**読むのは `retracted` だけ**であり、他の `status` 値を読むと参照側に `status` 語彙全体の解釈者がもう 1 つ生まれる（Issue #553）。`type: manual` は管理ファイルを持たないため対象外である。
>
> **参照側の経路は 3 つあり、ガードの形は 2 通りに分かれる（Issue #928）**: Issue #918 が塞いだのは `/wikicommit-ask --include-source` だけで、**ソースの内容を読む経路は他に 2 つある** — `wikicommit-review` Step 4 item 1 と `wikicommit-fix` Step 3 が、どちらも `sources[]` を再取得して読む。この 2 つは `resolve_source_cache_path.py` を経由せず Read ツール・WebFetch・抽出 Skill で直接取りに行くため、#918 のガードは構造的に届かない。
>
> **`wikicommit-review` の穴が最も鋭い**。あの Skill が行うのは「ページがソースに忠実か」の照合であり、取り下げ済みソースを基準に据えると、**人が「信用できない」と判断した文書に忠実であることを根拠にページを通す**。証拠拘束ルール（Issue #442）の下で機械はソースを疑えないので、`review-rules.md` の検査を厚くしても届かない — check 1 はまさにそのとおりに動く。**そして矛盾は 1 ファイルの中で閉じていた**: 同じ SKILL.md の Step 4 item 5 は、レビュアーがソースの誤りを指摘した場合に「その管理ファイルに `status: retracted` と `## Retraction Reason` を人が手で書く」と案内している（Issue #743 / #737）。取り下げを書けと言い、次の実行でそれを黙って無視していた。
>
> **止めない。取り下げ分を証拠集合から外して続ける。** 3 択のうち「ブロックする」を採らない理由は Issue #737 の決定そのものである — あちらは既存ページへの影響を報告に留め、どの経路（`--regenerate` / `--fix` / `--remove`）を採るかを人間の判断として残した。review をブロックすると、そのページは人が対処するまで `reviewed` に到達できなくなり、信頼ラダーに第 3 の状態を裏口から持ち込む（Issue #669 / #740 が繰り返し退けた形）。**`reviewed` が述べるのは「人が読んで引っかからなかった」（Issue #800）であってソースの妥当性ではない**ので、取り下げを承知で確認した人の署名は嘘にならない。
>
> **外すことが買うのは、今どこにも無い情報である**。証拠集合を狭めて check 1 を走らせると、**「取り下げられた文書だけに立っていた記述」が 1 件ずつ現れる**。`check_retracted_sources.py` が言えるのは「このページがそれを名指ししている」までで、ページのどの文がそれに依存していたかは言えない — そして `--regenerate` / `--fix` / `--remove` を選ぶのに人が必要としているのはその粒度である。**ただし所見は「ページが誤っている」ではなく「この記述は取り下げ済みのソースだけに立っていた」と書く** — 前者の書き方は本文を削る方へレビュアーを押し、`--regenerate` が正しい経路である場合にそれを潰す。
>
> **残りが 0 件の場合は既存の分岐にそのまま落ちる**。`wikicommit-review` は照合の基準が消えるので item 4 の全文フォールバック（`type: manual` と同じ扱い）、`wikicommit-fix` は Step 3 item 5（ソースが 1 件も得られなければ警告して続行可否を人に聞く。ガードを item 3 として挿したため旧 item 4 から繰り下がった）である。**どちらも新しい分岐を作らない** — 残り件数で分ける形は `/wikicommit-generate --regenerate`（Issue #744）が既に採っており、`check_retracted_sources.py` が所見に残り件数を添えているのもその判断のためである。
>
> **判定は取得の前に置く**。取得後に外すと、ネットワーク 1 往復を払ううえ**取り下げ済みの本文がコンテキストに載り**、その後の「使うな」が指示の遵守に依存する。`resolve_source_cache_path.py` が `status` をキャッシュ探索より前に置いたのと同じ理由である。
>
> **掛ける対象は `sources` 経路だけで、`sources` の解決が終わった後に掛ける**。翻訳ページは自分の `sources` を持たず親から継承するため、先に掛けると翻訳ページで素通りする。逆に `derived_from` 経路（`wikicommit-review` item 1 の 2 番目・`wikicommit-synthesize` の grounding）には掛けない — 読む対象が `.wikicommit/entity/` のページであり `status` を持つものが無い。ガードが半端に掛かった状態にならないよう、掛けない側も明記する。
>
> **新しいスクリプトは作らない — `check_retracted_sources.py` に `--list` を足す**。2 経路が要るのは「識別子 → 取り下げ済みか」だけで、`resolve_source_cache_path.py` がやっているキャッシュパスの解決ではない。そしてその判定は既に `.wikicommit/scripts/` にある（`collect_retracted_sources()` が識別子 → 管理ファイルの対応表を 1 走査で返す）。理由は 3 つ: (1) §11.5 の置き場所の規則を自動的に満たし、Issue #646 が唯一の例外として記録した越境を増やさない、(2) **同一性キーの規則（`source.path` / `source.url` であって導出ファイル名ではない。Issue #572 / #573）の写しを増やさない** — このリポジトリは `_wikilink.py`（Issue #677）でこの種の複製の代償を実際に払っている、(3) どのみち `.wikicommit/source/` 全体を 1 回走査するので、ソースごとに呼ぶ形は何も買わない（Issue #646 が `wikicommit-collect` で候補あたりの subprocess 回数を予算として扱ったのと同じ配慮）。**形も崩れない** — `--list` は「走査して報告する」ままで、突き合わせは Skill 側が行う。
>
> **`resolve_source_cache_path.py` はこれに寄せない**。あちらはキャッシュパスの導出に管理ファイルを引く必要が元からあり、取り下げ判定はその走査に 2 行足しただけである。寄せると走査が 2 回になる。`status` が `retracted` かの判定が 2 箇所に残るが 1 行ずつであり、許容する複製とする。
>
> **`wikicommit-fix` には入口も無かったので同時に足す**。Issue #743 は追跡 Issue に「ソース自体が誤っている」を問う項目を入れ、それを読むのは `/wikicommit-fix <issue-url>` だが、同 SKILL.md に取り下げの言及は 1 件も無かった（ガードも入口も無い）。結果として、コメントが「このソースが誤っている」と言っている場合、Step 4 の「裏づけられない修正はしない」により**「ソース文書で裏づけられませんでした」と言って何もしない** — 間違いではないが、正しい答えは「これはページの修正ではなく取り下げの話である」である。`wikicommit-review` Step 4 item 5 と同じ案内（人が手で書く・Skill は書かない）を置く。**ガードと入口は衝突しない** — ガードは既に書かれた `status` を読み、入口は Issue のコメントを読む。コメントが来た時点ではまだ `retracted` は書かれていないので、時系列で交わらない。
>
> **`--list` が実行できない場合は警告して続行する（止めない）**。`.wikicommit/scripts/` が古いリポジトリではこのモードが無く、`review-rules.md` の欠如（Issue #888 が実行を止めると決めた）とは扱いが違う — あちらはレビュー規律そのものが失われるのに対し、こちらは**この変更より前の挙動に戻るだけ**であり、取り下げが 1 件も無い Wiki では元から no-op である。ただし無言では劣化させない（`check_extraction_quality.py` が `source-policy.md` のパース失敗で採ったのと同じ形）。
>
> **`wikicommit-synthesize` は対象外だが、Issue #928 が挙げた理由は成り立たない**。あの Skill の grounding は `entity/` のページでありソースではないため、`status` を読む対象が無い。**ただし「間接的な影響は `check_derivation_freshness.py` の担当」という線引きは正確ではない** — 同スクリプトが発火するのは grounding ページが**実際に書き換えられた**ときであり、取り下げはページを 1 バイトも変えない。したがってあれがカバーするのは「人が取り下げに対処した後」（`--regenerate` で grounding ページが変わる → view ページが STALE）だけで、**grounding ページが取り下げ済みソースに立ったまま誰も何もしていない状態には届かない**。それでも対象外にする理由は別にある: カバーするには synthesize が各 grounding ページの `sources[]` を読んで `status` を解釈することになり、2 ホップの間接のために参照側に 3 つ目の `status` 解釈者が生まれる（Issue #553）一方、その直接の半分は `check_retracted_sources.py` が既に grounding ページ自身を名指ししており、人は同じ情報を 1 ホップ手前で受け取れる。
>
> **既存の公開済みリポジトリへの遡及適用は行わない**（新旧混在を許容する方針）。変更が届くのは次に Skills を更新したリポジトリからである。
>
> **`status` に値を足すことに対する機械的な検証は要らない**。`validate_frontmatter.py` が検証するのは `.wikicommit/entity/` のページであり、**ソース管理ファイルの `status` にはそもそも検証が 1 つも存在しない**。値を足すのに検証側の変更は不要である代わり、誤った値を書いても誰も止めない。
>
> **報告の入口（追跡 Issue・報告リンクの文面）は本 Issue に含めない** — 受け皿の無いまま文面だけ足すと、報告されても何もできない状態を作る（順序として受け皿が先である）。**既存の公開済みリポジトリへの遡及適用も行わない**（新旧混在を許容する方針）。

<!-- -->

> **保留は `status` に値を足さずに表現する（Issue #910）**: 非対話実行（サブエージェント経由・無人実行）が「人間が見れば答えが変わりうる判断」に当たったとき、**そのソースについて何も進めない**。`status` は `pending` / `outdated` のまま据え置き、理由を `## Deferred Reason` に書いてそのソースを飛ばす。ソースはキューに残るので、次の対話実行が既存の収集条件でそのまま拾い、人間に尋ねる。**例外が 1 つある** — 強制リチェック（`RECHECK:`）で到達した場合、`status` は `generated` / `failed` / `excluded` のままでありどの収集条件にも拾われないので、この場合だけ `pending` に戻す（`/wikicommit-reconcile` と同じ requeue）。なお `extracted_tokens` は書かれない（Pass 1 手順6 に到達しないため）が、**`source.hash` は既に書かれている** — `type: url` はフェッチ直後の `--write-hash` が、`type: path` は登録時の `add_source.py` が書く。書き戻して消してはならない（抽出キャッシュと食い違う）。
>
> **新しい `status` 値（`deferred` 等）は足さない。** `status` を読む消費者は Pass 1 の収集条件・`add_source.py` の分岐・`check_ingest_freshness.py` の `CHECKABLE_STATUSES`・`wikicommit-status` の集計・`reconcile_ingest_status.py` の 5 つあり、値を足すとすべてに分岐が増える（Issue #567 が `partial` について「新しい `status` 値は足さない」と決めたのと同じ理由）。保留は「進めない」ことなので、**進めないことがそのまま表現になる**。
>
> **保留するのは 2 つだけである** — ガード A の `LOW_DENSITY:`（テキスト形状のヒューリスティックであり、Issue #562 自身が「リンクの多い正当な行政サイトや統計資料と区別がつかない」と書いている。saitama パイロットの実測で 8 件中 4 件が誤検知）と、Pass 2b の厳格閾値を外れた型候補（型がその主題にふさわしいかは人間の判断であり、declined にすると祖先型でページが書かれて後から再分類する手が無い。Issue #447 / #565 が両方ともスコープ外と明言している）。**決定論的な判定は保留しない** — ガード B（既知 JS シェルドメイン）・抽出結果が空／読み取り不能・YouTube の URL 形式違いは、人間が見ても答えが変わらないので `status: failed` のままが正しい。ガード C（取得能力不足）は環境の問題なので処理全体を停止する扱い（Issue #574）を変えない。**ネットワークの不在（`NETWORK_UNAVAILABLE:`。Issue #1020）も保留するが、理由が違う** — 人間の判断を待つのではなくネットワークを待つので、対話実行でも保留し、強制リチェック由来でも `pending` に戻さない（取得していないので `source.hash` は変わっておらず、失われたものが無い）。連続 2 件で処理全体を停止する（`docs/DesignDoc-skills.md` §11.5）。
>
> **`reconcile_ingest_status.py` が保留を黙って `generated` へ戻すことはない。** ただし守っているのは**ハッシュの突き合わせ**であって、空のハッシュではない — 上記のとおり保留時点で `source.hash` は既に書かれている。初回の保留はページを 1 枚も作っていないので、そのハッシュをどの `sources[]` も引用しておらず一致しない。再取り込みでの保留は前回の `generated_pages` が非空なので同スクリプトがスキップし、強制リチェック由来で `pending` に戻した場合も `generated_pages` と `last_generated_at` を持つので同じくスキップする。
>
> **エンティティ単位の保留（`ambiguous`）だけはこの形に収まらない。** ソースは実際にページを作っているので、何をしても `status: partial` へ進む。そこで Pass 4 手順7 の `partial` 分岐が `ambiguous_entities` を書く（`{title, type, alternatives}` の配列。他の 3 分岐ではフィールドごと消す）。**書いても収集条件には乗せない** — 同じソースを読み直せば同じエンティティが同じ `ambiguous: true` を返すだけで、人間が決めた型はどこにも記録されないため、Issue #567 が off-`theme` 除外について取り除いた滞留を名前を変えて作り直すことになる。フィールドが買うのは**待ちが実行をまたいで見えること**であり、`wikicommit-status` がソースとエンティティを名指しする。解除は `/wikicommit-reconcile --source <path|url>`（Issue #874）で、保留側と同じ経路である。
>
> **既存リポジトリへの遡及は行わない**（新旧混在を許容する慣例）。既に `status: failed` になっているソースは人が手で戻すまで残る — `/wikicommit-reconcile` は `status: failed` を意図的にスキップするため、この経路では戻せない（`type: url` は `/wikicommit-generate <url>` が `RECHECK:` として強制再フェッチする。`type: path` は `status` を `pending` に書き戻してから再実行する）。
>
> **`partial` は再試行に意味がある状態と、無い状態を同居させている（Issue #567）**: 上表の `partial` の定義は「一部生成失敗**または**一部テーマ不一致で除外」であり、性質の異なる 2 つを 1 つの値にまとめている。
>
> - **再試行に意味がある**: 一部エンティティの生成が失敗した（`failed_pages` が非空）。再実行すれば成功しうる
> - **再試行に意味がない**: 一部エンティティが `theme` 不一致で `exclude` された（`failed_pages` が空）。**同じ `theme` で再実行すれば毎回同じ判断が下る**ので、何度実行しても `partial` に戻る
>
> この 2 分法は `failed_pages` の空／非空だけを見るため、**`ambiguous: true` のエンティティによる `partial` を後者に巻き込む**（Pass 4 手順7の最後の分岐は ambiguous でも `partial` になり、ambiguous なエンティティは `failed_pages` に入らない）。ambiguous は人間が型を確定すれば解決しうる状態なので本来は前者に属するが、管理ファイル上で両者を区別する情報が無い。型を確定した後はソースを名指しで再実行する（`/wikicommit-generate <path|url>`。引数指定の経路は `status` を問わず処理する）— `wikicommit-generate` の Completion Notice の ambiguous 一覧にもこの案内を書いている。
>
> `wikicommit/saitama-city-wiki` の `partial` 8 件は**全件が後者**であり、しかも区の記事から人物を除外するという `theme` どおりの意図した挙動で、不具合ですらなかった。それでも `wikicommit-generate` Pass 1 は毎回それを処理対象として収集し、**一度も処理されていない 23 件がその後ろで滞留した**（登録 70 件の内訳は `generated` 37 / `partial` 8 / `pending` 23 / `failed` 2）。実害は「未処理が残ること」自体ではなく、**専用の良質なソースが登録済み・未処理のまま、その実体のページが別の薄いソースだけから生成されていた**ことにある（ある施設のページは本文 204 字で、出典の観光ポータルには沿革の記述が無いと自ら宣言していた一方、その施設の Wikipedia 記事は登録済み・未処理のまま残っていた。同型が 9 件）。
>
> **新しい `status` 値は足さない**（Issue #567 の対応方針 1(b)）。`failed_pages` が既にこの区別を持っているため、値を増やさずに Pass 1 の収集条件を「`partial` かつ `failed_pages` が非空」に変更すれば足りる。**遡及適用は不要** — 既存リポジトリの `failed_pages` が空の `partial` は、次回実行時に単に収集されなくなるだけで、ファイルへの書き換えは一切要らない。
>
> あわせて 5 件ガードの**選定順序**を変更した。パス昇順のみだと、既に着手済みのファイルが毎回同じ枠を占めうる — 1 回の処理量を人間が制御するというガードの目的が、枠の中身が変わらないことで果たされなくなる。(1) `status: outdated`、(2) 一度も生成されていない（`last_generated_at` なし）、(3) 残り、の 3 段でパス昇順とする。`outdated` を backlog の前に置くのは意味が違うため — 既に公開されているページのソースが変わった状態であり、サイト上の内容が**誤っている**。未処理のソースは**欠けている**だけである。backlog を飢えさせる心配も無い: ソースが実際に変わったときにしか `outdated` にならず、この段は小さく、勝手に埋め戻らない。処理対象の提示も「未フェッチ」「フェッチ済みだが未生成」「再処理待ち」の 3 つに分けて見せる（`source.hash` の空／非空が前 2 者を分ける）。`wikicommit-status` は「登録済みだが一度も処理されていないソース」の件数を集計に加える — 失敗ではなく**単に順番が来ていない**ものなので、Issue #452 のようなトラッキング Issue 化ではなく集計に留める。
>
> **除外のみの `partial` を `generated` へ移した — 同居の片方が解けた（Issue #992）**: 上の分析のうち「再試行に意味がない」側、すなわちポリシー除外（`theme_mismatch` / `privacy`）だけが残ったソースは、**Issue #992 以降 `status: generated` になる**。`status` の消費者を全数えすると（Pass 1 の収集条件・`add_source.py` の `process_url()` / `process_file()`・`check_ingest_freshness.py`・`reconcile_ingest_status.py`・`/wikicommit-reconcile`・`/wikicommit-merge` Step 9・`/wikicommit-status`）、`partial`（`failed_pages` 空）を `generated` にしても挙動を変えるものは 1 つも無く、**変わるのは公開サイトに出る文字列（`content/sources/` の各ページと俯瞰ページの `status` 別表）だけ**だった。そこで `partial` と名乗ることは「部分的に止まっている」と読者に伝えるが、実態は Wiki が書かないと決めたものを書かなかった — 設計どおりの完了である。**新しい `status` 値は足さない**（上の判断と同じ。区別のために分岐を必要とする消費者が 1 つも無い）。`excluded_entities` フロントマターも足さない — `ambiguous_entities` が正当化されたのは機械が 2 つの意味を区別できず実際に困っていたからで、除外側にその困りは無い（Issue #553）。除外の記録は `## Generation Notes` と Completion Notice のまま（Issue #831 / #876）であり、Pass 2c が `status` と独立に書くので失われない。
>
> Pass 4 手順7の第 1 分岐は「`failed_pages` 無し・`ambiguous: true` 無し・**少なくとも 1 件がページを生成した**」になった。最後の条件が、全件除外（成功ゼロ）を第 1 分岐から外して `excluded` に残す。結果として `partial` ＋ 空の `failed_pages` は、新しい管理ファイルでは **ambiguous の型確定待ちだけ**を意味し、`partial` は「誰かが何かすれば進む」状態に絞られる。**収集条件そのものは変えていない**（ambiguous を収集しないという Issue #910 の決定は据え置き）。変わったのは理由づけである。
>
> **既存リポジトリは自動では変わらない** — Pass 1 は `failed_pages` が空の `partial` を収集しないため、次の実行でも直らない。`/wikicommit-reconcile` は勧めない（`--all` では直したい `partial` だけを選べず、requeue → generate は Pass 2a〜4 を全部走らせてページを書き直し、`review_status` が `pending` に戻り追跡 Issue が立ち直る。しかも今日のポリシーで `generated` に着地する保証が無い）。代わりに、管理ファイルの frontmatter だけで閉じる述語（`status: partial`・`failed_pages` が空・`ambiguous_entities` が無い）と、それを `set_frontmatter_field.py --require` で書き換えるコマンドを `CHANGELOG.md` に書いた。移行スクリプトを配布物に足さないのは 1 回きりのイベントに恒久的なファイルを残すことになるため（Issue #867 と同じ形）、`/wikicommit-reconcile` にモードを足さないのはあの Skill の契約が「キューに戻す」でありこれはその逆だからである。**caveat**: Issue #910 より前の管理ファイルは `ambiguous_entities` を持たないので ambiguous 由来の `partial` もこの述語に一致するが、それらは既に「Entities awaiting a type」に出ていない（フィールドが無いので読めない）ため、新たに失われるものは無い。
>
> **既知の副作用**: 「`partial` かつ `failed_pages` 空かつ `ambiguous_entities` 無し ＝ 除外あり」という導出は成り立たなくなる。この導出を使う消費者は現在ゼロであり、現れた時点で `excluded_entities` を足す判断になる。「1 件成功 + 10 件除外」も `generated` になるが、境目は `generated_pages` の空／非空であって恣意的ではなく、除外件数は Completion Notice が `existing_path` まで名指しして列挙している。
>
> **「薄いソースで生成済みのページに対する未処理の良質ソース」の検出はスコープ外**とする。上記の施設のケースを機械的に検出するには、未処理ソースの内容と既存ページの主題を突き合わせる必要があり、決定論的スクリプトの範囲を超える（`docs/DesignDoc-skills.md` §11.5）。未処理ソースが放置されない状態を作ることで間接的に解消する方針を採る。

<!-- -->

> **テーマ判定は Phase 2〜**（`config.yml` の `theme` が空の場合は無効・全エンティティ従来通り生成）。判定の詳細（エンティティ単位の `action: exclude`）は `DesignDoc-skills.md` §11.6 を参照。

### 4.4 `sources` フィールドの種別

| type | 必須フィールド | CI 検証 |
|---|---|---|
| `path` | `path`, `hash` | hash と `path` が指す現物を比較 |
| `url` | `url`, `hash` | hash でページ更新を検知（任意） |
| `wikicommit` | `url`, `hash` | hash でフェデレーション更新を検知 |
| `manual` | `author`, `created_at` | hash 検証なし。作成者を記録 |

`license` は全種別に共通する任意フィールド（Issue #558）。上表の必須フィールドには含まれず、CI 検証も値の存在・形式のいずれも要求しない（空文字列のみ ERROR。§4.1 の該当コールアウト参照）。

### 4.5 削除ページのフロントマター追加フィールド

```yaml
status: removed                    # 削除済みフラグ（review_status とは別フィールド）
removed_at: "2026-06-21"
removed_reason: obsolete           # obsolete / merged / gdpr
merged_into: .wikicommit/entity/ja/DefinedTerm/new-page.md  # merged の場合のみ
```

### 4.5.1 `.wikicommit/view/` — 二次知識の層（Issue #675）

`.wikicommit/entity/` には性質の異なる 2 種類が同居していた。

| | 照合先 | 書く主体 |
|---|---|---|
| 一次知識 | 外部ソース文書（`sources` + hash） | `wikicommit-generate` |
| 二次知識 | Wiki 自身のページ（`derived_from`） | `wikicommit-synthesize` |

**この違いはページの主題ではなく「何に照合できるか」にある**。`wikicommit/ai-driven-dev-wiki` の `entity/en/custom/Practice/parallel-coding-agents.md` は主題こそ世界に実在する実践だが、`sources` を持たず `derived_from` 7 件のみで、外部文書に直接照合する手段が無い。`## How It Works` さえ複数の記述を突き合わせた読みで組み立てられており、どの 1 文も 1 つのソース文書に還元できない。

同居していることの実害は 3 つあった。(1) **読者に区別が見えない** — 出典ボックス（Issue #587）は個別ページを開けば出自を示すが、ナビゲーション上は一次と二次が同じ型ディレクトリに混ざっている。(2) **型選択が非決定的である** — Issue #545 は、同じ topic に対する 2 回の実行が `entity/en/custom/Practice/...` と `entity/en/Practice/...` に割れ、どの WikiLink からも到達できない場所に解決された事例を記録している。(3) **型が本来表せないものを表そうとしている** — Issue #551 が調査したとおり Schema.org 全 933 型に「実践ノウハウ」の汎用型は無い。Schema.org は事物をモデル化する語彙であり、「適用条件・前提・失敗モード・根拠の種類」を持つものは事物のクラスではなく**読み方**だからである。`custom/Practice` はその読み方を型で代用したもので、`granularity` の全項目が「何であるか」ではなく「どう書くか」の規則になっていたことがそれを裏付けている。

#### 置き場所と公開先

| | パス |
|---|---|
| ディスク | `.wikicommit/view/<lang>/<slug>.md`（**Type セグメントを持たない**） |
| 公開 | `content/<lang>/View/<slug>.md` |
| WikiLink | `[[View/<slug>]]` |

**`content/view/<lang>/...` にはしない**。`wikicommit-breadcrumbs` / `wikicommit-language-switcher` / `wikicommit-explorer` の 3 プラグインは先頭セグメントが言語であることを `LANG_SEGMENT_RE = /^[a-z]{2}$/` で前提にしており（Issue #228 がこの複製の同期を CI で強制している）、言語を先頭に保てば 3 プラグインとも無改修で済む。ディスク上と publish 側のパスがずれる点は、`custom/` を publish 時にフラット化する Issue #576 と同じ前例に乗る。

`WIKILINK_RE` は変更していない（`View` は Type セグメントの文字クラスに既に一致する）。`View` は**予約名前空間**として解決側で分岐する — Schema.org 語彙に `View` 型は存在しないため、インストール済み型と衝突しない。

#### フロントマター

`type:` を持たない。必須は `title` / `lang` / `derived_from`、任意で `kind` / `review_status` / `generated_at` / `generated_by` / `generated_with`。`sources:` は書かない（`type:` と `sources:` はいずれも `validate_frontmatter.py` の ERROR）。

```yaml
---
title: "エージェントループの実践"
lang: ja
kind: practice                     # 任意。下記 6 値のいずれか
review_status: pending
generated_at: "2026-09-01"
generated_by: "claude-opus-5"
generated_with: "0.1.0"
derived_from:
  - path: .wikicommit/entity/ja/Person/yamada-taro.md
    source_commit: abc123def456abc123def456abc123def456abc123de
---
```

**JSON-LD は出さない**。`@type` の無い JSON-LD は出せない以上、出すなら固定値を `wikicommit-jsonld` に定数として持たせるしかないが、そこで捻り出した型は何も表さない。

型を持たせないことは**機構を減らす**方向に効く — `wikicommit-synthesize` の型選択ステップが丸ごと消え、書き出し前の「既存ファイルが一次コンテンツか合成ページか」の分岐も単純化され（view ツリーにはこの Skill の出力しか無い）、`check_schema_coverage.py` / `check_installed_type_usage.py` のノイズ源にもならない。

#### `kind` — 「複数ページを見て何をするか」の型

Schema.org 型が「何についてか」を表すのに対し、`kind` は「どう見るか」を表す。2 つは直交する。

| kind | 何をするか | Boundary（してはいけないこと） |
|---|---|---|
| `practice` | 1 つの実践について複数の記述を突き合わせ、適用条件・前提・失敗モード・根拠の種類を整理する | 規範的な助言を書かない |
| `landscape` | 領域の全体像・入口。ハブと主要ページへ導く | 新しい主張をしない。**数を書かない**（下記） |
| `comparison` | 同型の複数エンティティを並べて差分を出す | 優劣の判定はしない |
| `pattern` | 多数のページに繰り返し現れる共通の形を示す | 事例数と該当ページを必ず明示する |
| `timeline` | 複数ページの出来事を時間軸で並べる | 個々の出来事の詳細は `Event` ページ側に置く |
| `debate` | 同じ問いに対する主張の分岐と、それぞれの根拠 | 結論を出さない |

**`kind` は任意フィールドとする**。Issue #553 の教義どおり、先に受け皿だけ作ると空のまま残る。**`kind` が空のページが溜まること自体が「新しい kind を足すべき」という証拠**になる。保留する kind は `lineage`（因果・派生の連鎖）と `process`（横断する手順の流れ）で、どちらも既存 kind の `Boundary` に違反しないため急がない。

**kind を後から足すときの生成規則**: kind の正体は「grounding ページ間の**どの関係を使うか**」である。この形で並べると抜けが機械的に見える — 同一主題への複数の記述（`practice`）／同型の少数を並べて差分（`comparison`）／多数に繰り返し現れる共通の形（`pattern`）／時間順（`timeline`）／因果・派生の連鎖（保留）／同一の問いへの対立（`debate`）／近傍全体の地図（`landscape`）／横断する手順の流れ（保留）。増やしすぎない歯止めとして、**プラグインが既に機械的に見せている関係は kind にしない**（「1 つの `Person` が複数の `Place` に関わっている」は `backlinks` と `wikicommit-graph` が描いている）。追加の判定基準は「**その kind が無いと既存 kind の `Boundary` に違反するページが生まれるか**」— `pattern` は無ければ `comparison` に分類されるが `comparison` の `Boundary`（差分の提示に留める）に正面から違反するため採用した。

**kind はパスに出さない**。`[[View/comparison/slug]]` は `WIKILINK_RE` 的には通るが、kind の選択ミスがファイルの位置を動かし Issue #545 と同じ壊れ方を再発させる。kind が駆動するのは以下で、いずれもパスに影響しない: (1) `wikicommit-synthesize` の俯瞰モードの着眼点提案（`build_survey_view.py` の出力と対応が付き、提案が網羅的になる）、(2) 本文生成（kind の記述と `Boundary` をプロンプトに入れる）、(3) 同 Skill の grounding 照合ステップにおける `Boundary` 検査。**(3) が無いと kind は誰も見ないラベルになって drift する**（Issue #552 が `granularity` について扱ったのと同じ失敗）ため、これは kind を持つことの条件である。view ツリーの index は kind でグルーピングしていない — `kind` が任意である以上どのグルーピングにも「kind の無いページ」の受け皿が要り、通常小さいツリーに対して見出しを増やす価値が読み順を乱す不利益に見合わないため。後から足してもページの契約は変わらない。

**`landscape` が数を書かない理由**: build 生成の overview ページ（Issue #585）が総ページ数・レビュー済み比率・被リンク上位・型別集計・wanted / orphan・情報源の内訳を毎ビルド正確に再計算している。LLM が本文に「83 ページ」と書けば翌日には古くなり、検出する仕組みが無い。数が要るならそちらへリンクする。

#### スクリプトの走査対象

`ENTITY_DIR` は Issue #487 で `_wikilink.py` に一本化済みであり、`VIEW_DIR` / `VIEW_TYPE_SEGMENT` / `VIEW_KINDS` / `parse_view_path()` / `collect_view_pages()` / `view_page_path()` も同じ場所に置いた。各スクリプトは「view ツリーを含めるか」を 1 本ずつ決める加算的な分岐になる。

| 扱い | スクリプト |
|---|---|
| 含める | `validate_frontmatter.py`（view ページ専用ルールで分岐）・`check_wikilinks.py`（`[[View/x]]` の解決と view ページからの発リンク検査）・`check_raw_html.py`・`check_wanted_pages.py`・`check_expires.py`・`check_translation_status.py`・`search_index.py`・`rebuild_index.py`（Type 別ではなく**言語別** index の新モード）・`convert_wikilinks.py`（第 2 の入力ツリー） |
| 主消費者 | `check_derivation_freshness.py`（view ツリーが主対象。ただし entity ツリーも走査し続ける — 本 Issue 以前に書かれた合成ページはそこに残るため） |
| 除外 | `check_recurring_characters.py`・`check_unlinked_entity_mentions.py`（`properties:` 前提）／`check_schema_coverage.py`・`check_installed_type_usage.py`（`type:` 前提）／`reconcile_ingest_status.py`（`sources[].hash` 前提）／`check_orphans.py`（view ページは生まれつき被リンクゼロ。Issue #547） |
| 既定で除外・フラグで包含 | `build_survey_view.py`（`--include-view`）。view の分析をさらに分析することを避けるため。着眼点が実際に grounding するのはその下の entity ページである |

**除外側は `tests/test_view_tree.py` が固定している**。除外の理由（読むフィールドが無い・全件 orphan になる）はツリーの中身に依存せず常に成り立つため、後の変更が `collect_entity_pages()` を両ツリー走査に差し替えても**エラーにはならず**、対処できない所見が増えるだけになる — 報告が無視されるようになる典型的な壊れ方であり、テストで止める。

スクリプト以外の変更箇所: `wikicommit-merge` の変更検出 glob 2 箇所と `git add`・レビュー追跡 Issue の全ページ走査・`review-issue-close-sync.yml` のマーカー解決（`.wikicommit/view/<lang>/<slug>.md` を追加で受け付ける。これが無いと view ページの追跡 Issue は Close できても `reviewed` に反映されない）・`remove_page.py`（view ページの翻訳探索と言語別 index からのエントリ削除）・`_root_outputs.py` と `init.py`（ディレクトリ作成）・`wikicommit-fix`（ページパス指定と公開 URL 逆引き）。

#### 本文中の相対リンク

view ページの本文が書く相対リンク（画像・添付）は、**公開後の姿でそのまま書く** — `../../assets/<name>`、つまり entity ページが書くのと同じ形になる。`content/<lang>/View/` は `content/<lang>/<Type>/` と同じ深さだからである。`convert_wikilinks.py` の `rewrite_relative_links()` は view ページに対して意図的に no-op にしてある（この関数が扱うのは 1 つのツリー内での深さの変化であり、`.wikicommit/view/` と `.wikicommit/entity/assets/` という別ルートの兄弟ツリー間の対応付けは別の問題である）。WikiLink（`[[Type/slug]]`・`[[View/<slug>]]`）はパスを持たないため影響を受けない。

#### 移行

**自動移行しない**（本ドキュメント群が繰り返し採る「新旧混在を許容する」方針。Issue #477 等と同じ）。既存の `derived_from` ページは `entity/` に残ったまま従来どおり動き、新規の合成のみが view ツリーへ行く。手で移す場合は `git mv` + `type:` 削除 + `kind:` 追加 + 参照側 WikiLink の書き換えで、`build_slug_type_index()` が view ページも索引するため、書き換え忘れた `[[custom/Practice/<slug>]]` は「ページが存在しません」ではなく `View/<slug>` に実在すると名指しする ERROR になる（Issue #563 の TYPE_MISMATCH と同じ扱い）。**移行するとその Wiki のカスタム型ファイルが使われなくなる**（`check_installed_type_usage.py` が `UNUSED` として報告する）。kind に移した以上それが正しい状態だが、スキーマファイルを消すかは運用者の判断とする。

#### 検討したが採らなかった案

- **層名を `analysis` / `synthesis` にする** — どちらも kind の一種としても読める（分析・合成）。兄弟ディレクトリはすべて「中身を名指す名詞」（`source/` / `entity/` / `schema/` / `assets/`）であり、`view` は DB の VIEW（導出・非権威・再計算可能）の含意が層の性質と一致し、成果物自体を名指す。`lens` は道具を指すので半歩ずれ、`study` は kind に読め、`derived` は形容詞で兄弟から浮く
- **kind をパスに出す** — Issue #545 の壊れ方の再発（上記）
- **結論を書く kind（`thesis` / `essay`）を作る** — 結論は定義上どの grounding ページも述べていない主張であり、`wikicommit-synthesize` の grounding 照合（Issue #674）と正面から衝突する。特殊分岐が 3 箇所（照合モード・バナー・レビュー観点）必要になるのは設計に合っていない印である。由来の無い主張が要るなら、人間が `sources[].type: manual` で署名して書く（`author` と `created_at` を必須とし hash 検証を持たない既存の仕組み）
- **章・順序の原始概念（`chapter:` / `next` / `prev` / `position:`）を入れる** — 複数の kind を並べた文書は、既定では 1 ページの節として書けばよく、章を分けたい場合も「読む順に本文で列挙し `derived_from` に記録したもう 1 枚の view ページ」で足りる。順序付きの next / prev は Quartz に無く、作るなら過去いちばん壊れてきた領域（Issue #332 / #382 / #426 / #443 / #449）に手を入れることになる
- **JSON-LD に固定型（`schema:Article` 等）を出す** — 捻り出した型は何も表さない（上記）
- **Skill 名を `wikicommit-view` に改名する** — (1) `/wikicommit-view` は `/wikicommit-review` の部分文字列であり、Issue #381 が `wikicommit-preview` → `wikicommit-serve` の改名を行った理由がまさに `wikicommit-review` との衝突である、(2) Skill 名は動詞（行為）・成果物は名詞という対応が既にある（`wikicommit-generate` は entity ページを作るが `wikicommit-entity` ではない）、(3) "view" は動詞だと読み取り専用に読めるが、この Skill は書き込む、(4) `install.sh` の `SKILLS` 配列・`plugin.json`・README ×2・CLAUDE.md・docs の表（`test_skill_distribution_list_sync.py` が一致を強制）を変えるうえ、既にインストール済みの Wiki に `wikicommit-synthesize/` が孤児として残る（Issue #583 がスクリプト名を据え置いた理由と同じ）
- **既存の合成ページを自動移行する** — 上記「移行」

### 4.6 LLM レビューのフィードバック形式（エージェント間 JSON）

エージェント間でのみ使用。**この JSON そのもの**は PR コメントにも Git にも残さない。

> **ただし「何も残らない」ではない — 射影が永続化される（Issue #750）**: 本節の JSON から `source_quote` を落として射影したものが `.wikicommit/review/**/*.md` の frontmatter に記録される（§4.8）。したがって次の 2 つは**別物として扱う**:
>
> | | 扱い |
> |---|---|
> | 本節の JSON そのもの | **エージェント間限定のまま**。フィールド追加は引き続き自由 |
> | `.wikicommit/review/**/*.md` の frontmatter | **永続化フォーマット**。本節から射影したもので、後方互換の対象 |
>
> 永続化するのは本節の JSON ではなく、本節から**射影したもの**である。この区別を落とすと、次に本節へフィールドを足す人が「制約は無い」と読んで、既に書かれた記録ファイルと食い違う形を入れることになる（書かれていない前提は drift する — Issue #722 が明文化し、#552 / #571 が実例）。

```json
{
  "result": "PASS | FAIL",
  "issues": [
    {
      "type": "HALLUCINATION | CONTRADICTION | MISSING_SOURCE",
      "claim": "問題のある主張の引用",
      "source_file": "raw/paper-2024.pdf",
      "source_lines": "L34-L41",
      "source_quote": "原文の該当箇所",
      "instruction": "修正指示",
      "page_at_fault": "under-review | other"
    }
  ]
}
```

#### `CONTRADICTION` が指す 3 種類（Issue #566）

`type: CONTRADICTION` は当初「元文書と矛盾する」ケースだけを想定していたが、現在は性質の異なる 3 つを担っている。**何と矛盾しているかの判別は `source_file` の値で行う**。`page_at_fault` は 3 つ目（ページ間矛盾）のエントリにのみ現れる。

| 何と矛盾しているか | `source_file` | 扱い |
|---|---|---|
| そのページ自身のソース文書（帰属の取り違え・命名と発明の混同を含む。Issue #429・#451） | ソース文書のパス／URL | **FAIL** → 再生成 |
| 同じページの**別のソース**（ソース同士が食い違っている。Issue #566） | 採るべきだった側のソースのパス／URL | **FAIL** → 再生成 |
| 同じ Wiki の**別のページ**（Issue #566） | 相手ページ（`.wikicommit/entity/` 配下）のパス | `page_at_fault` で下記のとおり分岐 |

3 つ目のページ間矛盾は、**どちらのページが誤っているか**でさらに分かれ、この向きは `page_at_fault` が担う。`under-review`（レビュー中のページが誤っている）なら通常どおり FAIL して再生成する。`other`（相手側が誤っていそう）なら **FAIL にしない** — Pass 4 は 1 ページをそのページ自身のソースに対して再生成するループであり、相手ページのソースも持たなければ相手ページへの権限も持たないため、Completion Notice への報告に留める（`docs/DesignDoc-pipeline.md` §7 の該当コールアウト）。`other` のエントリだけが見つかった場合、`result` は `PASS` であり（エントリ自体は `issues` に載せる）、ページはそのまま書き出される — ここで FAIL にすると、正しいページを再生成しては同じ指摘を受けることを繰り返し、再試行上限で `failed_pages` に落ちて最終的に書き出されない。

`source_file` を「何と矛盾しているか」の判別子にしたのは、`.wikicommit/entity/` 配下のパスかどうかで機械的に分かれ、曖昧にならないため。一方で**どちらのページが誤っているか**は `source_file` からは分からない — どちらの向きでも入る値は相手ページのパスで同一であり、他のどのフィールドも向きを表さない — ため、ページ間矛盾のエントリに限り `page_at_fault` を置く。この JSON はエージェント間限定であるため、**JSON 側のフィールド追加には**後方互換の制約は無い。ただし Issue #750 以降、その射影がディスクと Git に残る — **記録側は後方互換の対象である**。本節にフィールドを足すこと自体は自由だが、それを記録に載せるかどうかは `record_review.py` の射影リスト（`FINDING_FIELDS`）を明示的に変えたときにだけ起こり、既存の記録ファイルと食い違う形にはならない（上のコールアウトの表を参照）。

### 4.7 `wikicommit.json`（Commons 発見可能性用）

リポジトリルートに配置。Commons Phase 0 の実装（Phase 4 で導入）。

```json
{
  "name": "owner/my-wiki",
  "domain": "medical/internal-medicine",
  "language": ["ja", "en"],
  "type_list": ["schema:Person", "schema:MedicalCondition"],
  "trust_level": "experimental",
  "schema_version": "1.0"
}
```

---

### 4.8 `.wikicommit/review/` レビュー記録のフォーマット（Issue #750）

`wikicommit-generate` Pass 4 は生成した**全ページ**に 8 種類の検査（証拠拘束〈#442〉・個別事実の逐一検証と命名 vs 発明〈#451〉・孫引き出典〈#473〉・帰属の取り違えと無帰属の単一ソース定式化〈#429〉・ソース間の食い違いと 1 ホップのページ間矛盾〈#566〉）を掛けながら、その判定を 1 バイトも残していなかった。結果として、**1 回目でクリーンに通ったページと、ハルシネーションを指摘されて 2 回目で通ったページが、ディスク上で完全に同一に見える**。残るのは `failed_pages`（＝一度も書き出されなかったページ）だけで、これは「レビューが機能した記録」ではなく「レビューが救えなかった記録」である。

**過大表明と過小表明が同時に起きている点が本節の出発点である**。読者向けバナーが `reviewed` の意味を実態より強く主張しているのは事実だが、逆向きの誤差もある — 実際にやっている全数の機械検査が、記録が無いために勘定に入っていない。過大表明の直し方は「弱める」だけではなく「実際にやっていることを足す」でもあり、後者のほうが正直で、しかも弱めていない。

#### 置き場所と単位

```text
.wikicommit/review/entity/ja/Person/yamada-taro/
├── 20260905-142233-ai.md      ← generate Pass 4
├── 20260907-091510-ai.md      ← wikicommit-review（別モデル）
└── 20260908-103302-human.md   ← 人間

.wikicommit/review/view/ja/agent-loop/
└── 20260906-201144-ai.md      ← synthesize Step 5.5
```

**1 レビュー ＝ 1 ファイル ＝ 不変**。書いたら二度と編集しない。1 ファイルへの追記より優れている点が 4 つある:

- **read-modify-write が消える**。このリポジトリは YAML の round-trip で 1 度やられている（`config.yml` のコメント記入例が `yaml.safe_load` + `dump` で全部落ちる。Issue #713）。作成のみなら round-trip 自体が発生しない
- **git のマージが自明**。別ブランチが別レビューを足しても別ファイルなので衝突しない
- **複数観点のレビューエージェントが自然に表現される**（3 観点 ＝ 3 ファイル）
- **人が読める・人が書ける**。較正（人間の指摘と機械の指摘を突き合わせる）には、人が機械のレビューを読める必要がある

ファイル名は `<YYYYMMDD>-<HHMMSS>-<kind>.md`（`<kind>` は `ai` / `human`）。`wikicommit-merge` の一時ブランチ `wikicommit/merge-<YYYYMMDD>-<HHMMSS>` に前例がある。**モデル ID をファイル名に入れてはならない** — 実行中モデルは `claude-opus-5[1m]` のように角括弧を含みうる（Issue #559 が実データで観測した表記）ため、glob を壊す。同一秒の衝突は実用上起こらない（Pass 4 は LLM 呼び出しを挟んで逐次実行される）が、`record_review.py` は 2 件目に `-2` を付す — 上書きは契約上あり得ない。

> **スタンプは同じディレクトリの最新記録まで切り上げる — 壁時計は単調ではない（Issue #991）**: どの記録が「いま立っている」かはこのファイル名順が決め（`standing_review()` / `standing_verdict()` / `latest_discarded()` と `check_review_coverage.py` の全集計が読む）、その順序は `datetime.now()` から来ていた。**ホストが時計を後方へステップさせるコンテナでは、連続して書いた 2 件が逆順のタイムスタンプを得る** — WSL2 上の devcontainer で実測すると、24 秒間に 4 回・1 回あたり 0.49〜0.58 秒だけ realtime が後退していた（`CLOCK_MONOTONIC` と対比して確認）。逆転すると**古い方の記録が最新として読まれる**。
>
> **しかも何も警告されない。** 記録は不変であり（本節の設計の中核）、後から気づく契機がどこにも無い。発覚したのは `tests/test_check_review_coverage.py::test_discarded_reason_takes_the_newest_discard` がフル実行で断続的に落ちたこと（3 回に 1 回。負荷が高いほど落ちやすく、これは 2 回の起動の間隔が伸びて窓が広がることと整合する）による — **`record_sort_key()` も採番も与えられた入力に対しては正しく、誤っていたのは入力の側だった**。
>
> 現在は `allocate_record_path()` が、**そのディレクトリに既にある最新記録より古いスタンプを受け取った場合、そのスタンプまで切り上げてから採番する**。既存の「同一秒なら `-2`」の機構をそのまま使うため、**文書化されたファイル名の形も `record_sort_key()` も変わらず、既存の記録もそのまま読める**。切り上げが働いたときは stderr に `WARNING:` を出す。
>
> **採番はファイル名ではなくスタンプを見る**（`next_seq()`）。`kind` は `record_sort_key()` の一部ではないため、`ai` 記録の隣へ切り上げた `human` 記録は `<stamp>-human.md` という空いている名前を取り、**2 件が同値になる** — §4.8 冒頭の例のとおり 1 ページのディレクトリに `ai` と `human` が同居するのが通常の形である。`load_records()` の `sorted()` は安定ソートなので、同値のキーは順序を `glob()` の返す順（ファイルシステム依存）に委ねてしまい、切り上げが消そうとした恣意性がそのまま戻る。したがって次の枠は「そのスタンプを持つ既存記録の最大 seq + 1」として決める。
>
> **代償は、切り上げられた記録のファイル名が書かれた瞬間より最大でステップ幅ぶん古くなること**である。有界であり、日付は記録自身の `reviewed_at` が持つ。引き換えに消えるのは「どのレビューが現在のものか」という、**この記録ツリーが存在する理由そのものの問い**に対する無言の誤答である。
>
> **採らなかった案**: (a) 環境起因として受け入れる — flaky なテストが残り、製品側の脆さも残る。(b) テストだけ直す（書き込みの間にタイムスタンプの単調性を注入する） — テストは緑になるが**製品側の前提は変わらず**、テストが守っていた契約を守れない条件下で守れているように見せることになる。(d) 逆転を検出して報告するだけ — 変更は小さいが**順序は直らない**ので、上に挙げた 4 つの読み手は誤った記録を指し続ける。本対応は (c)（記録に単調な順序を持たせる）を採り、(d) の警告をその副産物として併せ持つ形である。
>
> **`record_run.py` にも同じ欠陥があり、同じ形で直した**（`.wikicommit/run/` の `<YYYYMMDD>-<HHMMSS>-<skill>.md`）。あちらでは影響がもう一段重い — `run_sort_key()` は `LAST_RUN:` が報告する記録を選ぶだけでなく、**ローテーションがどれを削除するかも決める**ため、後方ステップは最古ではなく最新の実行を消しうる。**同値の問題もあちらの方が起きやすい**: `.wikicommit/run/` は 4 つの Skill の実行を 1 つのディレクトリに束ねており、skill スラッグは `run_sort_key()` の一部ではないため、主経路そのものである `generate` → `merge` がちょうどこの形に当たる。加えて、ローテーションがそのスタンプの seq 1 を削ると未サフィックスの名前が空くため、ファイル名で採番すると次の実行がそこを再利用して**最古の位置に着地する**（`LAST_RUN:` から落ち、次の削除対象になる）。

**ページが削除されても記録は残す**（履歴であるため）。したがって `.wikicommit/review/` は既存ページの厳密なミラーではない。**書き出されなかったページ（`failed_pages`）のディレクトリも作られる** — これが最も価値のある記録なので、これは仕様である。

**`.md` で安全であることは確認済み**: 各所の `rglob("*.md")` はすべてスコープされている（`collect_entity_pages()`・`convert_wikilinks.py`・`check_raw_html.py` / `validate_frontmatter.py` / `check_wikilinks.py`・`markdownlint-cli2 <変更 .md ファイル>`）。唯一の実害候補だった `lychee` も `wikicommit-merge` がパス引数付きで呼んでいる — 無スコープだと記録内の `source_file` URL を毎マージ再検証しに行くところだった。`tests/test_review_record_tree.py` がこの前提を回帰テストとして固定する。

#### フォーマット — frontmatter ＝ 機械可読 / 本文 ＝ 散文

`.wikicommit/source-policy.md` / `.wikicommit/entity-policy.md` と同じ分担を採る。

```yaml
---
page: .wikicommit/entity/ja/Person/yamada-taro.md
kind: ai                      # ai | human
stage: generate-pass4         # generate-pass4 | review-skill | synthesize-step5.5 | issue-close
model: "claude-opus-5[1m]"    # kind: ai のとき。ランタイムの報告どおりに書く（Issue #559）
reviewer: "octocat"           # kind: human のとき。GitHub login（Issue #663 と同じ理由で表示名ではない）
reviewed_at: "2026-09-05"
skill_blob: "a1b2c3d4e5f6..." # .wikicommit/review-rules.md の blob hash（Issue #752）
wikicommit_version: "0.2.0"
page_content_hash: "sha256:ab12..."
reviewed_sources:
  - type: url
    url: "https://example.com/a"
    hash: "sha256:cd34..."
attempts: 2
result: pass                  # pass | fail | discarded
findings:
  - round: 1
    type: MISSING_SOURCE      # HALLUCINATION | CONTRADICTION | MISSING_SOURCE
    claim: "2025年3月19日の投稿で…"
    source_file: "https://example.com/a"
    source_lines: "L34-L41"
    instruction: "当該文書は sources に無い。日付を落とす"
---

（散文本文。kind: human では人が書いた一言・気づきが入る。kind: ai では
 Pass 4 が PASS と判定しながら述べた観察が入り、無ければ空。Issue #834）
```

**`findings` は本文ではなく frontmatter に置く**。本文に置くと集計スクリプトが散文をパースすることになり、Issue #474 が名指しした失敗モード（決定論的に扱えるものを instruction／パースに委ねる）に入る。本文は「構造化された居場所が無い散文」専用である。

> **`kind: ai` の本文は「FAIL に至らない観察」の置き場でもある（Issue #834）**: Issue #750 が直したのは「1 回目で通ったページと、指摘を受けて 2 回目で通ったページがディスク上で同一に見える」ことだった。**1 段小さいスケールの同じ形が残っていた** — 1 回目で通ったが**指摘を受けた**ページと、1 回目で何も言われずに通ったページが、やはり同一に見える。`wikicommit/ai-driven-dev-wiki` のスモークで、Pass 4 が `featureList` の記述について実際に指摘を述べたページの記録が `attempts: 1 / result: pass / findings: []` だった。指摘はそのセッションのコンソールにしか存在せず失われている。Issue #722 が `MISSING_SOURCE` について名指しした形（判断は下されているのに拾う経路が無い）と同一で、あちらが FAIL に至る判断を拾ったのに対し、こちらは **FAIL に至らない判断**である。
>
> **受け皿は既に 4 層とも揃っており、落ちていたのは指示だけだった** — §4.6 の JSON は `result` と `issues[]` を独立に持てる（`page_at_fault: "other"` が `result: PASS` のまま `issues[]` に載る実例。Issue #566）、`record_review.py` の射影は `result` を見ない、本文には `--note` / `--note-file` がある、そして `review-rules.md` Part 1 が `result` と観察の関係を述べていなかった。現在は同ファイルが `observations`（プレーン文字列の配列。`result` は `PASS` のままで、`issues` の中身を増やしも減らしもしない — `page_at_fault: "other"` のエントリは従来どおり `issues` に載る）として返す形を定め、`wikicommit-generate` Pass 4 と `wikicommit-synthesize` Step 5.5 がそれを `--note-file` で本文に落とす。**`review-rules.md` に書くことで 3 経路とも一度に述べるようになる**（Issue #752 の一本化の効果がそのまま出た箇所である）。ただし**記録に落ちるのはサブエージェントを使う 2 経路だけである** — `wikicommit-review` はサブエージェントを持たず、その記録の本文は既にレビュアーが書く一言が占めているため、同経路では目の前のレビュアーへの報告が行き先になる（ルールファイル側にもそう明記した）。
>
> **`issues[]` には載せない**。`check_review_coverage.py` の `RISKY:` は standing な記録が `attempts >= 2` **または** findings を 1 件以上持てば挙げるため、非ブロッキングの観察を `issues[]` に入れると**この一覧が膨らむ**。`RISKY:` は Issue #800 が定めた抜取（AI 全件・人間は一部）の選定の設計図であり、その選定規則の実測（Issue #765）はまだ着手前である — **測定の途中で測定対象の定義を変えることになる**。散文本文なら同スクリプトは読まないので、何も汚さずに記録だけが残る（人が `.wikicommit/review/` を開けば読める。Issue #750 が 1 レビュー 1 ファイルの理由に「人が読める・人が書ける」を挙げたとおり）。**`check_review_coverage.py` は無改修である。**
>
> **`severity: blocking | note` を `issues[]` のエントリに足す案は、今は採らない**（将来これが正解になりうる）。enum を足すには消費者を同時に決める必要があり（Issue #553）、その消費者＝`RISKY:` の数え方こそ Issue #765 が測ろうとしているものである。**Issue #765 の後に再検討する。**
>
> **2 つの限度が、これをノイズにしないための条件である**: (1) **網羅性は裏口から戻さない** — Part 1 の 2（Completeness is not a criterion）は一切動かしておらず、「ソースにはあるがページに無い」は観察にもならない。書けるのはページが**述べていること**についての気づきに限る。(2) **無ければ書かない** — 毎ページに数行ずつ付くと `.wikicommit/review/` を読む人が読み飛ばすようになる（Issue #562 が低情報密度ガードについて踏んだ力学）。
>
> **`--note` ではなく `--note-file` を使う**。観察はサブエージェントが返す自由記述であり、シェルのコマンドラインに載せないのが既存の規範である（`review-issue-close-sync.yml` が Close コメントについて同じ判断をした。Issue #762）。**`rules_version` は 2 → 3 に上げた。**

**`model` と `reviewer` は該当する側だけを書く**。両方を常に置くと、片方は必ず空のまま残る — Issue #553 が `inDefinedTermSet` について禁じた形である。`reviewer` は経路によっては空になる（`wikicommit-review` はローカル実行であり、認証済みの GitHub login を得る手段が無い。Issue #705 と同じ理由）ため、その場合はキーごと省く。`skill_blob` も同様で、`stage: issue-close` には従うべきレビュー規律のファイルが無い（人間が読んだ）ため付かない。

**`skill_blob` が指すのは `.wikicommit/review-rules.md` である**（Issue #752 で確定。Issue #750 の時点では「レビューを実行した SKILL.md」としていたが、規律がそのファイルへ移ったため、「どの版の指示が判定したか」を表すのはそちらになった）。`rules_version`（同 Issue）とは役割が違い、冗長ではない:

| | 何のため | 誰が扱うか |
|---|---|---|
| `rules_version` | **読んだことの検証** | サブエージェントが返す JSON に echo する |
| `skill_blob` | **どの版が判定したかの記録** | orchestrator が計算して記録に書く |

blob hash は echo させられない（エージェントが計算できない）し、`rules_version` だけでは bump 忘れで嘘の記録になる — その場合 `rules_version` は嘘をつくが blob hash は真のままである。

> **観察は機械可読にしない — 散文本文のままとする（Issue #866）**: 上のコールアウトが入れた `observations` を `issues[]` のエントリとして持ち、`severity: blocking | note` で `RISKY:` から切り分けるか、が Issue #834 のクローズ時の宿題として残っていた。**採らない。**
>
> **#834 が直した実害は、既に直っている。** 観察がそのセッションのコンソールにしか存在せず失われる、という形は散文本文への記録で解消済みであり、#866 が残して問うていたのは「それを**数えられる**ようにするか」だけである。
>
> **そして数えたい消費者が 1 つも存在しない。** 観察は `rules_version: 3` で入ったため、**この判断の時点で観察を含む記録は 1 件も無い** — パイロット（`wikicommit/ai-driven-dev-wiki`）の 29 記録は `rules_version: 1` であり、このリポジトリ自身の `.wikicommit/review/` は 0 件である。1 ページあたり何件出るのかを誰も知らない状態で、その集計方法と閾値を先に決めることになる。Issue #553 が繰り返し確立した「消費者と同時にキーを足す・受け皿だけ先に配らない」そのものであり、Issue #669 が `chain_of_thought` について採った基準（効果を測る手段が無い一方でコストは確実に発生する）も同じ向きに当たる。
>
> **`severity` を足しても、#866 が挙げた 3 つの便益のうち 1 つしか得られない。** 件数は取れるが、**種類別の集計には観察用の `type` 語彙が要る** — `HALLUCINATION` / `CONTRADICTION` / `MISSING_SOURCE` はいずれも欠陥の種類を表す語であり「言い方が粗い」を入れる箱が無く、足せば 2 つ目の enum になって同じ規範に再び当たる。別軸の抜取候補は `wikicommit-status` の行を 1 本増やすことになり、Issue #864 が「列を足して行数を保つ」を選び Issue #867 が `POLICY_DRIFT:` の 1 行を退けた力学に正面から当たる。加えて `FINDING_FIELDS` の 7 つのうち `claim` / `source_file` / `source_lines` / `instruction` / `page_at_fault` は観察では常に空になる — このスキーマは欠陥のためのものであって、観察に合っていない。
>
> **数えるための設備（記録の frontmatter に `observations:` を配列のまま持つ形）も、いまは入れない。** `issues[]` を汚さずに件数だけを取れる中間の形ではあるが、**入れても観察の記録は 1 件も増えない** — 足りないのは設備ではなくデータである。
>
> **測り直すのに実装は要らない。** `--note-file` に渡す観察は 1 行 1 件で本文に書かれるため、`stage: generate-pass4` の記録のうち本文が非空のものを数えれば「何ページに何件」が分かる（本文を持つ他の経路は `kind: human` と `stage: issue-close` だけなので、切り分けは効く）。**再開の条件は「`rules_version: 3` 以降の記録が実在し、その観察が読み切れないほど多いと分かったとき」**であり、そのときには本 Issue が最後まで欠いていた実データが最初から揃っている。

#### `source_quote` は落とす

`source_quote` は**ソース文書の逐語抜粋**である。ページ本文で引用することと、Wiki 全体にわたって系統的に抜粋を蓄積・保管することは別の行為であり、`sources[].license`（Issue #558 / #570）が ShareAlike や all-rights-reserved を記録している以上、この Wiki は「ソースの利用条件は事実確認の対象である」という立場を既に取っている。同じ理屈が自分の記録にも掛かる。

落としても目的は達成できる — `source_file` + `source_lines` があれば後から見に行ける。あわせて、**ソース文書の生テキストが記録に入る唯一の経路が消える**ので、プロンプトインジェクションの面積とファイルサイズも同時に縮む。

**落とすのは `record_review.py` の側で行う** — 呼び出し側が渡してきても落ちる形にしてあるので、保証が指示の遵守に依存しない。

**既知の限界**: `type: url` ソースのフェッチ結果は `.wikicommit/.cache/` に置かれ `.gitignore` されているため、引用の復元には再フェッチが要り、ソースが変わっていれば行番号は合わない（下記 `reviewed_sources` があれば「合わない」ことは分かる）。

#### `page_content_hash` — コミット SHA ではなく内容ハッシュ

レビューが有効かどうかは「そのページのどの版を見たか」で決まる。生成直後はページがまだコミットされていないため、コミット SHA は取れない。

**内容ハッシュを採る理由はそれだけではない**。`reset_review_on_content_change.py`（Issue #724）が既に「6 フィールド（`generated_at` / `generated_by` / `generated_with` / `review_status` / `reviewed_by` / `sources`）を無視した内容比較」というルールを持っている。**同じ無視リストでハッシュを取れば、「このレビューは今のページにまだ有効か」が決定論的に判定できる**。`record_review.py` はこのリストを `reset_review_on_content_change.py` から **import する**（複製しない）— 2 つの写しは drift し、drift は「誤った鮮度を黙って報告する記録」として現れる。

**捨てられたページ（`result: discarded`）は `page_content_hash: ""` とする**。ページがディスクに書かれないためハッシュが取れない。**空のハッシュは「ページが書かれなかった」を意味する**と定義し、失効判定はこれをスキップする。

#### `reviewed_sources` — レビュー時点のソース版（フルリスト）

レビューの有効性は (ページの版, **ソースの版**) の組で決まる。ページが変わっていなくても、ソースが変わったら判定は無効になる。

ダイジェスト 1 本ではなくフルリストを採る理由が 1 つある — **`check_ingest_freshness.py` は `type: url` を監視しない**（§4.3。URL の鮮度確認は `/wikicommit-generate <url>` の再実行が唯一の手段）。つまり URL ソースについては、**レビュー記録がその時点のソース版を捉える唯一の場所になる**。

view ページは `derived_from[].source_commit` を同じ位置に記録する。ページ frontmatter の `sources[]` との重複に見えるが、あちらは現在の値、こちらは**レビュー時点のスナップショット**であり、翻訳ページの `source_commit` と同じ関係になる。

`result: discarded` ではページが存在しないため、`record_review.py` は `--sources-from <ソース管理ファイル>` から `reviewed_sources` を組み立てる。これが無いと、最も価値のある記録が「どの版のソースがそれを生んだか」を何も言えなくなる。

#### findings は全ラウンドを、フラットに `round:` 付きで持つ

Pass 4 は最大 `generate.max_retries` 回まわり、**各ラウンドで別の指摘が出る**（Issue #571 のパイロットでは 3 回とも別の欠陥だった）。最終ラウンドの findings だけを記録すると、**1 回失敗して直ったページが `findings: []` になり、いちばん欲しい信号が消える**。

`rounds:` の入れ子ではなくフラットにするのは、集計（総件数・`type` 別・最大 round）がフィルタ 1 回で済むため。`attempts` は別に明示する — 最終ラウンドに findings が無い場合、`max(round)` からは復元できない。

#### 書き込む 4 経路

| 経路 | `stage` | 備考 |
|---|---|---|
| `wikicommit-generate` Pass 4 | `generate-pass4` | **PASS と `failed_pages` 行きの両方**（後者こそ本命） |
| `wikicommit-review` Step 5 | `review-skill` | 実行者に応じて `kind` を `ai` / `human` に振る |
| `wikicommit-synthesize` Step 5.5 | `synthesize-step5.5` | 同じ §4.6 JSON を返す（Issue #674 が Pass 4 に倣った） |
| `review-issue-close-sync.yml` | `issue-close` | 下記。Close した本人の最新コメントが記録の本文になる（Issue #762） |

**`review-issue-close-sync.yml` が人間レビューを記録することが要である**。Issue #313 の設計意図は「Claude Code のセッションを持たない人が GitHub の Web/モバイルから Close できる」ことであり、**その経路にはローカルスクリプトが 1 つも走らない**。記録しないと `kind: human` は `/wikicommit-review` 経由でしか生まれず、**集計スクリプトは `human_reviewed=0` と報告し続ける — 実際には人が 12 ページ Close していても**。これは「記録が無い」より悪く、Issue #567 が `partial` について指摘した「誤った記録が残る」そのものである。同ワークフローは `review_status` を書く**同じコミットで**記録ファイルも書く — 片方だけ成功する状態が存在しない。

> **経路 A の Close コメントが記録の本文になる（Issue #762）**: Issue #740 は追跡 Issue の主たる依頼を「このページから何を受け取ったかを一言書いて Close する」に変えた。その一言は `review_status` が 2 値であるがゆえに**フィールドには収まらない**産物であり、記録の散文本文だけが受け皿になる。ところが経路 B（`/wikicommit-review` Step 5）は `--note` で渡す一方、**経路 A は渡しておらず、同じ産物が入口によって残ったり残らなかったりしていた** — しかも Issue #313 の設計上、経路 A のほうが主経路である。
>
> **どのコメントを採るか**: **Close した本人（`closed_by`）の最新のコメント 1 件**。「Close 直前の最後のコメント」は、他人が別件で直前に書いた場合にそれを取り違える。「全コメントを連結」は修正依頼・議論まで混ざり、「その人が受け取ったもの」ではなくなる。本人に絞る識別コストは**ゼロである** — `Resolve closer identity` ステップが Issue #403 の対応として既に login をライブ再取得しており、空なら `::error::` で job を落とすため、記録ステップに到達した時点で login は必ず非空である（`closed_by` が空の場合の扱いが本 Issue の範囲に入らないのはこのため）。
>
> **本文はシェルのコマンドラインに一度も載せない**。コメントは第三者が書ける自由記述であり、このワークフローがファイル冒頭で全ステップに課している方針（`github.event.*` を `run:` へ `${{ }}` で直接展開せず `env:` を経由する）と同じ理由が当てはまる。API のレスポンスをファイルに落とし、埋め込みの Python が login（環境変数から読む）で選別してもう 1 つのファイルへ書き、`record_review.py --note-file` に渡す — `${{ }}` 展開もシェル再展開も一度も経ない。`--note` に渡す形は採らない（コマンドラインに載るため）。値を step output に載せる形も採らない（`${{ steps.*.outputs.* }}` として再展開される経路ができるため）。
>
> **コメントが 1 件も無いまま Close された場合は本文なしの記録を書く**（`--note-file` を渡さない）。沈黙して閉じるのは正常な閉じ方であり、失敗ではない — この変更以前とまったく同じ結果になる。
>
> **「最新」の判定は API の並び順に委ねない**。`GET /repos/{owner}/{repo}/issues/{issue_number}/comments` が受け付けるのは `since` / `per_page` / `page` だけであり、**`sort` / `direction` はリポジトリ単位のエンドポイント**（`/repos/{owner}/{repo}/issues/comments`）のパラメータである — 渡しても黙って無視され、応答は既定の **ID 昇順（古い順）**になる。したがって `direction=desc` を付けて先頭で一致したものを採る形は、**Close 本人の最も古いコメント**を記録する（「あとで読みます」を書いてから本題を書いて閉じた場合、前者が残る）。`per_page=100` の 1 ページ目も、昇順である以上「最も古い 100 件」であって直近 100 件ではない。そこで `--paginate` で全件を取り、`created_at`（同秒は `id`）の最大をこちら側で選ぶ。ページ 1 枚の追跡 Issue では実質 1 リクエストのままであり、サーバー側の並び順という文書化されていない挙動に依存しなくなる。
>
> **このステップは実行を落とさない**。取得も選別も失敗しうるが、いずれも `::warning::` を出して本文なしに劣化する。ここは `review_status` を作業ツリー上で書き換えた後・それをコミットする前に位置するため、job を落とすと **Issue は Close 済み・ページは `pending` のまま**残り、この workflow は `issues: closed` でしか起動しないので再試行の経路が無い。付加的な産物が、それを載せる本体を道連れにしてはならない。
>
> **Close コメントの回収・集計 UI は引き続きスコープ外**（Issue #740 が排した範囲）。ここで決めたのは記録の置き場だけである。**既存の Close 済み Issue への遡及も行わない**。

**`wikicommit-translate` の翻訳品質チェックは含めない**（§4.6 形式で返しておらず、含めるにはマッピングの設計が要る）。**`wikicommit-fix` も含めない** — あれはレビューではなく編集である（ただしそれが作る失効は `check_review_coverage.py` の `STALE_REVIEW:` が可視化する）。

#### 読み出しは `check_review_coverage.py`

集計・未レビュー・抜取候補・失効の列挙は `check_review_coverage.py` が行い、`wikicommit-status` が呼ぶ（仕様は `docs/DesignDoc-ScriptSpec.md`）。**閾値・合否判定・自動化は入れない** — 実測が無い状態で決めた閾値は推測にすぎない。人が `RISKY:` / `COVERAGE:` を読んで `/wikicommit-generate --regenerate`（Issue #578）を叩けばループは人力で閉じる。

**読み手は 2 つある（Issue #969）。** 上記の集計は `wikicommit-status` が読むが、**`result: discarded` の記録には 2 人目の読み手がいる** — `wikicommit-merge` Step 9 の生成失敗トラッキング Issue である。同 Step は理由をソース管理ファイルの `## Failure Reason` から取るが、Pass 4 step 7 はその節を `partial` 分岐で削除する（`failed` ではないため。Issue #408）。そして `partial` こそが普通の失敗の形であるため、**Step 9 が最も多く立てる Issue では理由欄が構造的に必ず `unknown` になっていた**。

**書く側は最初からそう設計されていて、読む側だけが繋がっていなかった。** 上の「`failed_pages` 行きの記録こそ本命」という設計判断（Pass 4 が PASS したページと破棄したページの両方を記録する理由）は、まさにこの用途を先取りしていた — Issue #452（Step 9 を作った Issue）が Issue #750 より前に入ったため、当時は読む先が存在しなかっただけである。現在は `check_review_coverage.py --discarded-reason` が両者を繋ぐ（`docs/DesignDoc-ScriptSpec.md` の同スクリプトの節）。

**この用途のために記録の形は変えていない。** 足したのは読み出しモードだけであり、`FINDING_FIELDS` も射影の規則も 1 バイトも動いていない — 上の「本節の JSON そのもの」と「射影したもの」の区別（前者はフィールド追加が自由、後者は後方互換の対象）はそのまま保たれる。**印字しないフィールドがあることは記録しないことを意味しない**: `source_file` は記録には残り続け、Step 9 が印字しないだけである（gitignored なキャッシュを指すため）。

#### 既存リポジトリへの遡及生成は行わない

本ドキュメント群が一貫して採る「新旧混在を許容する」方針どおり、記録の欠如は「この機能追加より前に生成された」ことを意味する。**そして測定は遡って作れない** — 記録が無かった期間は永久に空白である。これは受け入れる代償であり、だからこそ記録を早く始めることに意味がある。

読者向けの表示（バナー・俯瞰ページ）は本節のスコープ外であり、**ページ frontmatter に要約フィールドを足すことはしない** — 表示側は記録ツリーを publish 時に読む形を採る。

---

## 5. スキーマ層の実装

### 5.1 `.wikicommit/schema/*.md` の役割

`.wikicommit/schema/` ディレクトリ自体がドメインプロファイル。ファイル名がタイプ名になる（`.wikicommit/schema/Person.md` → `.wikicommit/entity/*/Person/` ディレクトリが有効）。LLM と CI の両方が読む仕様書として機能する。

Schema.org プロパティの意味・型・制約の定義文は書かない。LLM は Schema.org を学習済みのため、「どれを `properties:` に入れるか」の取捨選択のみ記載する。

`wikicommit.frontmatter.required` は `validate_frontmatter.py` が CI 検証に使う必須フィールドリスト。`default.md` にのみ存在し、全ページ共通の必須フィールド（`title`/`lang`/`type`/`sources`）を定義する。

> **型レベルの `required`/`recommended`/`excluded`/`custom` を廃止した経緯（Issue #495）**: `properties:` ネスト化以前は型スキーマファイルにも `wikicommit.frontmatter.{required,recommended,excluded,custom}` という分類があったが、実装調査の結果、型レベルの `required` は全型で常に空配列、`custom` は全型で一字一句同じ固定リストであり、`recommended`/`excluded` は Pass 2b/Pass 3 のプロンプト材料としてのみ使われ `validate_frontmatter.py` からは一切参照されていなかったことが判明した。つまり機械検証に接続されておらず、認知的負荷を下げる効果も限定的だった。`properties:` ネスト化によって「型固有のプロパティ一覧」というrecommendedが担っていた実質的な役割はテンプレート本体の `properties:` ブロックのキー一覧がそのまま代替し、`excluded` が唯一持っていた実質的な情報（Schema.org 上は存在するが意図的に書かない、という判断）は `granularity` の箇条書きに自然文として移した（例: `Person.md` の "Do not record marital/family relationship properties (spouse, children) or physical attributes (height, weight) even when the source states them"）。型レベル `required` は実際には一度も使われていなかった（全型で空配列）が、これは「特定の `properties.<key>` を必須にする」という能力自体が今後も存在しないことを意味する — `properties:` 配下の各キーは常に任意項目であり、値の有無ではなく値がある場合の Schema.org 語彙適合性のみを `validate_frontmatter.py` が検証する（§5.2）。特定プロパティを必須にしたいケースが将来生じた場合は、この能力自体を再設計する別 Issue が必要になる。

#### スキーマファイルの配置は `type:` から機械的に導出される（Issue #575）

スキーマファイルの探索は `.wikicommit/schema/<type: から schema: を除いた値>.md` というパス導出のみで行われ、ディレクトリを型名で走査する処理はどこにも存在しない。`custom/` は例外ではなく、この規則の帰結にすぎない（`type: "schema:custom/Decision"` の型名自体が `custom/Decision` であるため `.wikicommit/schema/custom/Decision.md` になる）。

したがって、型が増えてきたからと `.wikicommit/schema/standard/Person.md`・`.wikicommit/schema/text/Book.md` のように分類しても、**その型定義はファイルを移動した瞬間に静かに無効化される**。`.wikicommit/schema/` は LLM 書き込み禁止領域であり編集は必ず人間の手で行われるため、これは十分起こりうる操作である（Issue #575 の発見契機そのもの）。

無効化されると `default.md` へフォールバックし（§5.4。フォールバック自体は正規の設計）、その型の `granularity`・`properties:` 候補キー・本文テンプレートが丸ごと適用されなくなる。それでも生成されたページは一見正常で、`validate_frontmatter.py` の必須フィールド検証も通る（`default.md` の required だけが適用されるため）。この状態は `wikicommit-status` の `check_schema_coverage.py`（Issue #575）が「専用スキーマファイルが無いまま使われている `type:` 値」として継続的に報告するが、報告を見て `wikicommit-schema-propose` を実行すると `.wikicommit/schema/<Type>.md` を新規作成するため**同じ型の定義ファイルが2つ並ぶ**（実際に効くのは新しく作られた方のみ）点に注意する。正しい対処は移動したファイルを元の位置へ戻すことである。

### 5.2 `.wikicommit/schema/*.md` のフォーマット

キーはすべて英語とする。Schema.org は英語ベースであり、多言語 Wiki および複数エージェント対応のため言語中立な形式を採用する。

フロントマターは、ページ instance（§4.1）と同じく **共通フィールド**（トップレベルに平置き）と **型固有プロパティ**（`properties:` にネスト）の 2 層構造をテンプレートとしてそのまま体現する。`properties:` に列挙するのは、その型で妥当と思われる Schema.org プロパティを人間または Pass 2b（`wikicommit-generate` の動的型追加ステップ）が選んで空文字列（または空リスト）で列挙したもの — フォーマルな「推奨」ラベルを伴わない単なる出発点であり、この選択自体（および各 Wiki ページの本文で何を書くか）が WikiCommit におけるスキーマ設計の実質的なポイントになる。`expires_at`/`generated_at`/`generated_by`/`wikidata`/`sameAs`/`aliases` はテンプレートに含めない（`review_status` と同じ扱い）— `generated_at`/`generated_by` は Pass 3/4 がページ生成完了後に機械的にスタンプする値でテンプレートに書く主体が存在せず、`expires_at` は `validate_frontmatter.py` が「フィールドが存在する場合」に `YYYY-MM-DD` 形式を検証するため空文字列プレースホルダーを残すとフォーマットエラーになる（Pass 3 は非 null のときのみ書き込む設計と整合させる）。

**`default.md`**（全型に共通する必須フィールドを定義。`properties:` を持たない — Schema.org の `base:` を持たないフォールバック型のため）:

```markdown
---
wikicommit:
  frontmatter:
    required: [title, lang, type, sources]
  granularity: []
title: ""
type: ""
lang: ""
sources: []
review_status: pending
---

(2-3 paragraph overview of the subject)

## Details
(key information about the subject)
```

**型スキーマ**（`Person.md` 等）:

```markdown
---
wikicommit:
  base: https://schema.org/Person
  provenance: default
  granularity:
    - Create a new page for any person mentioned by full name independently
    - Use WikiLink in body text for simple mentions (e.g., "affiliated with")
    - Do not record marital/family relationship properties (spouse, children) or physical attributes (height, weight) even when the source states them — out of scope for this wiki's purpose
title: ""
type: "schema:Person"
lang: ""
sources: []
tags: []

properties:
  description: ""
  affiliation: ""
  jobTitle: ""
  birthDate: ""
---

(2-3 paragraph overview of the person)

## Background
(chronological activities, affiliations, and roles)

## Works & Achievements
(major works, projects, awards)
```

`properties:` 配下の各キーは `validate_frontmatter.py` がそのページの `type:`（祖先型を含む継承チェーン）の `domainIncludes` に対して機械検証する（`.wikicommit/schemaorg-vocab.json` を参照。`check_schema_org_type.py` と同じロジックを `_schemaorg_vocab.py` で共有）。存在しないプロパティ名・所属しない型を書くと `wikicommit-merge` の品質ゲートで ERROR になる。

#### 記事系 3 型は共通の `## Key Points` を持つ（Issue #673）

`ScholarlyArticle` / `NewsArticle` / `BlogPosting` の 3 型は、本文に **`## Key Points`** という同じ見出しを持ち、その下を**1 主張 1 箇条書き**で書く。`tests/test_schema_template_key_points.py` が配布テンプレートについてこれを CI で強制する。

**統一前は名前も形式も揃っていなかった**。`ScholarlyArticle` だけが `## Key Contributions` を名乗り、3 型とも指示の末尾が `in list or prose form`（リストでも散文でもよい）だった。この 2 つはどちらも単独では無害に見えるが、**両方が揃って「その Wiki が持っている主張は突き合わせられない」という状態を作っていた** — 散文で書かれた節からは主張を 1 件ずつ取り出せず、型ごとに見出し名が違えばそもそも型をまたいで探せない。Issue #550 が境界ルールについて指摘した「片側にしか書かれない」構造と同じものが、ここでは見出し名の側で起きていた。

**新しい機構を作る前にこの 1 段が要る**。主張を横断的に整理する（比較する・矛盾を見つける・根拠の強さを並べる）には、まず主張が 1 件ずつ取り出せる形で書かれていなければならない。

**消費者は既に 2 つとも存在する**（Issue #553 の「消費者と同時に受け皿を足す」を満たす）:

- **人間の目** — 3 型のどのページを開いても同じ位置に同じ形で主張が並ぶ
- **`build_survey_view.py`** — 同スクリプトは既に各ページの `##` 見出しを抽出しており（Issue #586）、見出しが 1 つに揃った時点で `wikicommit-synthesize` の俯瞰モードがこの節の存在を横断シグナルとして使えるようになる。**新しいスクリプトは要らない**

**箇条書きの中身にも 2 つの規律を課す**。(1) その文書自身が述べていることに限る — 他文書から引いただけの主張はその文書の主張であり、日付や数値を確定事実として書かない（Issue #473 の孫引き出典と同じ規律を、節の指示として前倒ししたもの）。(2) 根拠が見た目より狭い場合はその箇条書き自身にそう書く（単一のデータセット・単一の取材源・著者自身の経験・自社製品のドキュメント等）。後者は `wikicommit/ai-driven-dev-wiki` の `custom/Practice`（人間が手書きした型。`provenance: manual`）が `properties.evidenceOrigin` と `## Evidence` 節で既に実装している方向を、**フィールドを増やさずに**指示へ反映したものである。

**対象は記事系 3 型のみ**。`ShortStory` / `Book` は作品であって論証ではなく、`Person` / `Place` / `Organization` / `Event` / `HowTo` / `DefinedTerm` はそもそも「その文書の主張」という概念を持たない。全型に一律で足すと、Issue #553 が `inDefinedTermSet` について示した「受け皿だけ存在して常に空のまま残る」形になる。上記テストは対象 3 型と**非対象 9 型の両方**を理由付きの定数として持ち、どちらの向きの逸脱も止める。

**`evidenceOrigin` 相当のプロパティは配布 3 型に足さない**。同じ理由（空プレースホルダー）であり、必要な Wiki が自分で型を作る経路は既にある（§5.3「配布テンプレートにカスタム型を同梱しない」）。

**主張自体をエンティティ化する案は採らなかった**。`schema:Claim` は Schema.org に実在するが固有プロパティが 3 つしかなく、公式の `rdfs:comment` 自身が「現時点で Schema.org は主張間の関係を一切定義していない」と述べている — 横断整理の価値がある部分（支持・反証・限定）にちょうど語彙の裏付けが無い。`custom/Claim` にすると**同一性が定義できない**という別の壁に当たる: 既存のヘルスチェック群（`check_unlinked_entity_mentions.py` / `check_recurring_characters.py` / `check_orphans.py` の重複判定）はすべて正規化した文字列一致に立っているが、命題は正規名を持たず、同じ主張が複数の文書に別の言い回しで現れる。`granularity` の「独立した主題か」という判定も事物向けで命題には効かない。将来この方向へ進むとしても、itemize が無ければ入力自体が存在しない。

**既存ページへの遡及適用は行わない**（本ドキュメント群が繰り返し採る「新旧混在を許容する」方針）。`## Key Contributions` を持つ既存ページはそのまま残る。

#### 配布テンプレートの `properties:` に「埋められないキー」を置かない（Issue #553）

配布テンプレートの `properties:` に列挙してよいのは、**そのキーに適合する値を、その Wiki が持っているものだけで書けるキー**に限る。書けないキーを置くと、Pass 3 はそれを埋めることも消すこともできず、空のプレースホルダーがそのまま生成ページの frontmatter に残る。`dev/pilot-ai-driven-dev-wiki-round5.md` の `DefinedTerm` 43 ページでは、`inDefinedTermSet` を持つ 14 ページの**全件**が空だった（`dev/pilot-saitama-wiki.md` でも同じ形で再現している）。

判定基準は 2 条件の連言で、`check_schema_org_type.py --show-range` が返す RANGE 分類から機械的に決まる:

1. `rangeIncludes` のエンティティ型候補に、配布テンプレートに含まれる型が 1 つも無い（＝ `[[Type/slug]]` が解決しうる先が無い）
2. DataType 候補だけでは事実を担えない — 候補が空であるか、唯一の候補が `URL` でありながら同時にエンティティ型候補も宣言されている（その `URL` は「作れないエンティティ」を指す識別子でしかなく、値そのものにはならない）

**`DefinedTerm.md` から `inDefinedTermSet` と `termCode` を削除した**（Issue #553 の対応方針 1）。前者は上記 2 条件をともに満たす: エンティティ候補は `DefinedTermSet` のみで配布テンプレートに無く、`base_types` へ足す判断は Issue #551 が「配布テンプレートにカスタム型を同梱しない」で示した理由（ドメインを問わない配布物に、大半の Wiki で意味を持たない型を一律で足さない）がそのまま当てはまる。DataType 候補は `URL` のみで、Wiki の内部にしか存在しない分類体系はその URL を持たない。後者は `Text` 型なので形式上は書けるが、Schema.org の定義が "A code that identifies this DefinedTerm **within a DefinedTermSet**" であり、前者を外すと錨を失う — 実際にこのリポジトリ自身の Wiki ページでは `termCode` の値が slug の反復（`termCode: "orphan-page"`）になっており、Issue #275 が `tags` について禁じた自己言及と同じ形で情報量ゼロだった。

ソース側に実在する分類体系を取りこぼさないため、**`DefinedTerm.md` の `granularity` に受け皿を明示した** — 分類体系への所属は `tags` に、体系そのものの説明は本文に書く。`tags` は元々「複数ページを横断して同じ概念で括る」ためのフィールド（§4.1・Issue #275）であり、分類体系の membership はその定義にそのまま収まる。

**棚卸しの結果**（配布テンプレート 11 型・全 `properties:` キーを上記基準で機械的に走査した）: 上記 2 条件を満たすキーは他に 2 つある。いずれも**残す**判断とした。

| キー | 状況 | 残す理由 |
|---|---|---|
| `Event.eventStatus` | `rangeIncludes` は `EventStatusType` のみ（DataType 候補なし） | `EventStatusType` は Schema.org の Enumeration であり、メンバーは公開・固定された IRI（`https://schema.org/EventCancelled` 等）である。Wiki 側に型を作らなくても適合値が書けるため、条件 1・2 を形式的に満たしても「書けないキー」ではない |
| `Organization.numberOfEmployees` | `rangeIncludes` は `QuantitativeValue` のみ（DataType 候補なし） | JSON-LD では構造化値（ネストしたオブジェクト）として表現するのが本来の形であり、値の形が決まっている。同上 |

この 2 件に `granularity` の説明を足すことは**意図的に見送った**。`check_property_wikilink_reinforcement.py` の `is_reinforced()` は property 名の言及に加えてリンク化を指し示す手掛かり（`[[` または `link`）を同じ箇条書きに要求するだけで、肯定・否定の文脈は区別しない（Issue #650）（§「Pass 2b が書く `granularity` の内容は誰も検証しない」の「対応方針 3 を採らなかった」節と同じ限界）ため、「この property は WikiLink 化しない」と書くと（`WikiLink` の語自体が手掛かりに一致するため）、補強が無いのに補強済みと判定される逆向きの偽シグナルになる。代わりに、この 2 件が生む空プレースホルダーは下記の Pass 3 側の変更が引き受ける。

**Pass 3 の「空プレースホルダーを写さない」ルールを強化した**（Issue #553 の完了条件 3）。旧文面は「写すな」としか述べておらず、**値を決められないキーをどうするか**を述べていなかったため、Pass 3 は埋めるでも消すでもなく素通りさせていた。新文面は「埋められないキーは省略する」と明示する — `properties:` 配下のキーはすべて任意であり特定キーを必須にする能力自体が存在しない（Issue #495）ので、省略は常に妥当である。一方、空文字列を残すと「ソースがそう述べている（空である）」と区別がつかず、`wikicommit-properties` プラグインが公開ページに空の行として描画する。

このルールが決めるのは**テンプレートが差し出したキーをどう書き出すか**だけであり、**ページが既に持っている値を消すことはない**。`action: update` では、今回のソースが触れていない`properties:` キーの既存値はそのまま残す（`expires_at` と同じで、「このソースが言及していない」は「記録すべきものが無い」ではない）。テンプレートから削除されたキー（上記の `termCode` / `inDefinedTermSet`）も同様で、既存ページの値は書き換えずに引き継ぐ — 下記のとおりこれらは今後も妥当なキーであり続けるため。あわせて、全キーが省略された場合は `properties:` キー自体も省略する: 値なしの `properties:` は YAML の null になり、`wikicommit-properties` プラグインがこれをもう 1 行の空行として描画してしまい、このルールが避けようとしている結果そのものになる。

**既存ページへの遡及適用は行わない**（本ドキュメント群が繰り返し採っている「新旧混在を許容する」方針）。このリポジトリ自身の Wiki ページを含め、既に `termCode` / `inDefinedTermSet` を持つページはそのまま残る — `validate_frontmatter.py` の `properties:` 検証は Schema.org の `domainIncludes` に対して行われ、配布テンプレートの `properties:` 一覧とは照合しない（§5.2 冒頭のとおり、テンプレートの `properties:` は「推奨」ラベルを伴わない単なる出発点である）ため、これらのキーは今後も妥当なキーであり続ける。値の形（`inDefinedTermSet` にプレーンテキストが入っている）は `validate_frontmatter.py` の検証対象外であり、この Issue では扱わない。

`tests/test_schema_template_property_reachability.py` が上記の判定基準を CI で強制する。除外する 2 件は理由付きの allowlist として同テストに持たせ、新しく「埋められないキー」を配布テンプレートへ足すと落ちるようにしてある（`check_extraction_quality.py` の `KNOWN_JS_SHELL_DOMAINS` と同じ「確認済みのものだけを決定論的な表に持つ」パターン）。

#### 型間の優先関係は `granularity` に書く（専用キーは設けない。Issue #569）

「この場合は別の型に譲れ」という**型と型の間の優先関係**は、`granularity` の箇条書きとして書く。`wikicommit:` ブロックに専用キー（`defer_to:` 等）は新設しない。

判断の分かれ目は、**譲るかどうかの判定が機械化できるか**にある。できない — 「ソースの実質が読者の行う順序手順かどうか」は語彙照会でも正規表現でも決まらず、結局 LLM が判断する。キーを機械可読にしても、そのキーに書かれた条件文を評価するのは依然 LLM である。フォーマットを増やす対価に見合わない（Issue #553 が `inDefinedTermSet` について確立した「消費者と同時にキーを足す」という基準にも合わない — このキーの消費者は結局 Pass 2c のプローズ読解になる）。

代わりに **2 か所で補強する**（Issue #569 の対応方針 1 の (a)＋(c)）:

- **書く側**: `wikicommit-init` の obvious-type judgment（Issue #490）・`wikicommit-collect` の Type Proposal（Issue #489）・`wikicommit-generate` Pass 2b（Issue #315）・`wikicommit-schema-propose`（Issue #285）の 4 経路すべてに、「別のインストール済み型がその主題の適切な置き場なら、型名を挙げて `granularity` の 1 ルールとして書く」ことを明記した。`Boundary` ルール（その型が**何でないか**。Issue #550）とは別物である — `Boundary` は「その型ではない」、こちらは「代わりに誰が持つべきか」を述べる。**インストール済みの型しか名指ししない** — 無い型を指す行は実行しようがない
- **読む側**: `wikicommit-generate` Pass 2c に「候補型の `granularity` が他の型に譲れと言っており、その型がインストール済みなら従う」を明記した。Issue #565 の「最も具体的なインストール済み型を選ぶ」と**同じ箇所**に置いてある（Issue #569 の対応方針 2。両者とも Pass 2c の型選択に追加ルールを入れるものであり、実装を分散させない）

**発見の経緯**: `dev/pilot-saitama-wiki.md` の重点検証項目「`schema:HowTo` と `schema:GovernmentService` のどちらが選ばれるか」の実測結果は **GovernmentService 6 件 / HowTo 0 件**だった。`GovernmentService.md` の `granularity` は "Prefer `schema:HowTo` when the source's substance is an ordered set of steps the resident performs" と明記しており、`GovernmentService/household-waste-disposal.md` の出典は「家庭ごみの**出し方マニュアル**」で、原典は番号付きの手順（コールセンターに電話予約 → 予約番号を控える → 手数料納付券を受け取る → シールを貼る → 朝 8 時 30 分までに出す）であり、ページもそのまま順序手順として再現していた。**ルールは矛盾させられたのではなく、単に読まれなかった（あるいは重み付けされなかった）**。

`Issues/p3.1-009`（非公開の開発リポジトリ側の記録）（Pass 2b が書いた `granularity` が SKILL.md 自身のルールと矛盾する問題）とは別の失敗である点に注意する。ここでは `granularity` の内容は正しく、SKILL.md とも矛盾していない。

**そして、このルールを書いたのは LLM 自身である**。`GovernmentService.md` は配布テンプレートに含まれず、`wikicommit-init` の型提案ステップで LLM がその場で書いたものであり、その数分後の Pass 2c で同じモデルが従わなかった。型ファイルに書いたルールが守られないなら、4 経路が `granularity` を書く工程そのものの意味が薄れる — これが「読む側」の補強を必須にした理由である。

結果として 6 ページに 3 つの異質な性質が同居していた: 窓口・チャネルの所在案内 2 件、届出制度の要件表 3 件、手順マニュアル 1 件（本文 48 行。他ページの 2〜3 倍の粒度）。**この粒度差そのものが、1 ページに 2 つの主題が同居している徴候である**。

その同居をどう解くかは型選択ではなくエンティティ抽出側の話であり、§5.4「1 ソースから型の異なる複数エンティティを切り出してよい（Issue #569）」で扱う。

> **2 例目がある（Issue #970）**: この節の根拠は当初、「従われなかった」という 1 件の否定的な観察だけだった。その後、別の境界（引用されただけの論文をページにしない）で、型テンプレートの記述はそのままに Pass 2c の指示へ書き足したところ、他の条件を変えずに従われるようになった対照が 1 つ取れている。詳細と限界（両側 1 回ずつ・Pass 2c の非決定性）は §5.4「ソースがすれ違いに引用しただけの文書はエンティティにしない（Issue #968）」の末尾にある。**境界を足すときは型テンプレートだけで済ませず、それを判断する Pass の指示にも書く。**

#### Issue #490（theme 駆動型提案）の初の成功実例

上記の `GovernmentService.md` の `wikicommit.provenance` は **`init-theme`** だった。つまりこの型は `/wikicommit-init` の theme 駆動型提案（Issue #490。§3.3 参照）が人間の Enter ベース承認を経て追加したものであり、Pass 2b ではない。theme 文の「市が提供する行政手続き（ごみの出し方、住民異動届等の窓口業務）を中心に扱う」から、**ソースを 1 件も読む前に**型の必要性が断定できた形になる。

`GovernmentService` は過去のどのパイロットも生成できなかった型で（`docs/DesignDoc-skills.md` §11.6 の分析 JSON 例に登場しながら実生成例が無かった）、これが初の実例である。**Issue #490 は成功しており、Issue #569 はその成果を否定するものではない** — 追加された型が使われ、そのうえで型が書いたルールが守られなかった、という次の段階の問題である。

**既存ページの再分類はスコープ外**とする（Issue #447・#565 と同じ判断）。型変更はディレクトリ移動と全 WikiLink の Type セグメント書き換えを伴う（§5.5）。本 Issue が扱うのは新規生成時に正しく選ばれることに限る。

#### `granularity` の境界ルールは片側にしか書けない（Issue #550）

`granularity` の箇条書きには、その型が**何でないか**を述べる境界ルールを書く。配布テンプレートの全 `base_types` は `Boundary` で始まる箇条書きを1件ずつ持ち、`tests/test_schema_template_boundary_rules.py` がこれを CI で強制する。

**この規約が必要になるのは、境界ルールが構造的に片側にしか書かれないため**である。`wikicommit-generate` Pass 2b（Issue #315）と `wikicommit-schema-propose`（Issue #285）はいずれも `.wikicommit/schema/` に対して「追加のみ可・既存ファイルの編集/上書き不可」という narrow exception のもとでしか書き込めない（§5.2 の `provenance` 節が「一度書いたら値が変わらない恒久スタンプ」の根拠として挙げているのと同じ制約）。したがって:

- 新しく追加される型が、既存型との境界を自分の `granularity` に書くことはできる
- **その相互の記述を既存型側に書き足す経路は、どの Skill にも存在しない**

`dev/pilot-ai-driven-dev-wiki-round5.md` では、Pass 2b が実行時に生成した `TechArticle.md` が `HowTo` との境界を述べる一方、配布テンプレートの `HowTo.md` は自分の境界を一切述べていなかった。型選択は「どちらの型ファイルがその境界に言及しているか」に左右されるため、この非対称は動的に型が追加されるたびに蓄積し、既存の `base_types` 側が一方的に選ばれにくくなる。Issue #523 が property-value WikiLink 補強で扱ったのと同型の非対称性である。

**対応は2本立て**（Issue #550 の対応方針 1 + 2）:

1. **配布テンプレート側で自足させる**。全 `base_types` に、他の型の記述に依存せず単体で成立する境界ルールを書いた。相手方の型名を挙げてよいのは相手も必ず配布される `base_types` の場合に限る — 動的に追加される型（`TechArticle` 等）は存在しないリポジトリがあるため、その型名に依存した書き方はしない。あわせて、既存の3件（`BlogPosting`/`NewsArticle`/`ScholarlyArticle` の `Boundary with X: ...`）がコロン+空白によって YAML のマッピングとしてパースされ、`isinstance(g, str)` で絞り込む Python 側の消費者（`check_property_wikilink_reinforcement.py` の `is_reinforced()`）から不可視になっていた問題を修正した（区切りを `—` に変更）。上記テストの第2の検証がこの再発を止める — ただし守れるのは**配布テンプレートだけ**であり、実行時に書かれた型ファイル（Pass 2b・`wikicommit-schema-propose`）と人間の手書き（`provenance: manual`）は射程外に残る。そちらは `check_property_wikilink_reinforcement.py` が非文字列の箇条書きに WARNING を出して可視化し、`granularity` を書く4経路が読む `.wikicommit/schema-authoring.md` が「文字列としてパースされる形で書く」ことを明記する形で扱う（Issue #649。当初は 4 経路の SKILL.md それぞれに同じ段落を置いていたが、Issue #886 が共有ファイルへ一本化した — 各 SKILL.md に 1 行ずつ残るのは `Boundary —` の一点のみで、空白を伴う `#` の危険は共有ファイル側にしかない。`docs/DesignDoc-ScriptSpec.md` の同スクリプトの節）。
2. **Pass 2b が既存型との境界に言及したら Completion Notice で報告する**。既存ファイル編集不可という制約自体は維持したまま、「相互の記述が相手側に無い」ことを人間が知る経路だけを作る。人間は `.wikicommit/schema/` を直接編集できる（CLAUDE.md の書き込み制限は LLM/Skills のみを対象とする）ため、報告さえ届けば対処できる。非対話実行でも報告する — その場で読む人はいないが、報告しなければこの欠落はどこにも痕跡を残さない。

**採らなかった案**: (a) 既存型ファイルの `granularity` への追記のみを narrow exception として許可する — 実効性は最も高いが、「`.wikicommit/schema/` は LLM 不可侵」という設計原則に穴を空けることになり、追記が既存記述と矛盾しても検出する手段が無い（Issue #552 が扱う「Pass 2b の書いた `granularity` の内容は誰も検証しない」問題を、編集可能な範囲まで広げてしまう）。(b) 片側だけの境界ルールを機械的に検出するチェックを `wikicommit-status` に追加する — `granularity` は自由記述のプローズであり、「型 X に言及しているか」は grep できても「相互の記述が必要か」は機械判定できない。上記1のテストは「各型が自分の境界を1件持つか」という判定可能な形に問題を置き換えたものであり、相互性そのものを検証するものではない。

**既存リポジトリのスキーマファイルへの遡及適用は行わない**（本ドキュメント群で繰り返し採られている「新旧混在を許容する」方針）。既に片側だけの境界ルールを持つ Wiki は、人間が `.wikicommit/schema/` を直接編集して揃える。

#### Pass 2b が書く `granularity` の内容は誰も検証しない（Issue #552）

`granularity` はスキーマファイルの中で**唯一、検証済みの値ではなく自由記述のプローズである**部分であり、しかも下流にそれを検査する仕組みが1つも無い:

- `validate_frontmatter.py` は `wikicommit.frontmatter.required` しか読まない（§5.1）
- `check_schema_org_type.py` が検証するのは型・プロパティが Schema.org 語彙に実在するかだけで、文面は対象外
- `check_property_wikilink_reinforcement.py`（Issue #539）は `granularity` を読むが、property 名が言及されているかを見るだけである

一方で `wikicommit-generate` Pass 2b が書いた型ファイルは、通常の `.wikicommit/entity/`・`.wikicommit/source/` の変更と同じバッチで `wikicommit-merge` が**自動マージする**。Issue #507 以降は非対話実行での自動承認経路もあるため、人間の Enter 確認すら挟まらずに書かれた文面がそのまま恒久的に残りうる。**人間レビューが必須の経路（`wikicommit-schema-propose`）の方が `granularity` の書き方に関する指示が手厚く、自動マージされる経路（Pass 2b）の方が指示が無い**という逆転が起きていた。

`dev/pilot-ai-driven-dev-wiki-round5.md` では、Pass 2b が生成した `TechArticle.md` の `granularity` が「official product documentation … all qualify」と述べる一方、同じ SKILL.md の Pass 2a（source-as-entity 判定、Issue #475 / #479）は「継続更新される living resource（公式文書・行政の手続きページ・Wikipedia 記事）は除外する」と明示していた。同一 SKILL.md が定めるルールと、その SKILL.md が実行時に書き出した型定義とが正面から食い違っている状態である。その実行では担当エージェントが Pass 2a を優先したため実害は出なかったが、**矛盾はその場のアドホックな判断で解消されており、次回同じ状況で同じ判断が下る保証はない**。

**対応（Issue #552 の対応方針 1 + 2）**:

1. **Pass 2b に `granularity` の執筆指示を追加した**（対応方針 1）。何を書くか（このソースの実際の内容に即した 1〜3 件・`Boundary` 箇条書きを1件含める〈Issue #550 の規約〉）に加え、**SKILL.md 自身の他のルールと矛盾する記述を書かないこと**を明示し、既知の衝突（Pass 2a の source-as-entity 判定）を名指しした。あわせて「全型に共通するルールを `granularity` で言い直さない」ことも明記している — 一般ルールの言い換えこそが矛盾の生まれ方だったため。同じ no-contradiction 節を `wikicommit-schema-propose` Step 4 にも入れた（あちらは人間レビュー必須だが、同じ文面を書きうる立場は変わらない）。
2. **追加された型の `granularity` を Completion Notice に全文表示する**（対応方針 2）。検証されず・後から編集もできない文面が、人間の目に触れうる唯一の瞬間がここであるため。非対話実行ではその場で読む人はいないが、実行の出力には残る。

**共通化はしなかった**。`wikicommit-generate` と `wikicommit-schema-propose` は独立に配布される別 Skill であり、片方が他方の SKILL.md を読む形にすると、参照先の存在を前提にした上に実行時のファイル読み込みが1回増える。SKILL.md は Skill 起動のたびに全文がコンテキストに載る（`docs/DesignDoc-skills.md` §11.9）ため、短い文面を各自が持つ方が総コストで優る — `remove_page.py` が `normalize_entity_prefix()` を import ではなく複製している（§3.1）のと同じ判断である。

**対応方針 3（既知の衝突パターンの機械的検査）は採らなかった**。grep は「living resource 系の語が `granularity` に現れるか」は判定できるが、**それが肯定文脈か否定文脈かを区別できない** — 「公式文書もページ化の対象とする」と「公式文書はページ化の対象としない」が同じヒットになる。この「言及の有無しか見ない正規表現が文脈を取り違える」失敗は `check_property_wikilink_reinforcement.py` の `is_reinforced()` で実際に2回連続して起きており（Issue #550 / #551 の PR レビュー。`Issues/p3.1-039-is-reinforced-mention-false-positive.md`（非公開の開発リポジトリ側の記録））、同じ形の検査を新設する根拠が無い。プローズ全般の整合検査が機械化できないことは Issue #550 §「採らなかった案」でも同じ結論に達している。

**既存の矛盾した型ファイルへの遡及対応は行わない**（本ドキュメント群で繰り返し採られている「新旧混在を許容する」方針）。パイロットの `TechArticle.md` のような既に書かれた文面は、人間が `.wikicommit/schema/` を直接編集するまで残る — 上記の Completion Notice は新規に追加される型にしか働かない。

#### `wikicommit.provenance` フィールド（Issue #519）

`.wikicommit/schema/<Type>.md`（`custom/` 配下も含む）の `wikicommit:` ブロックに、そのファイルがどの経路で作られたかを記録する `provenance` フィールドを持たせる。値は以下の固定 enum のいずれかで、各書き込み箇所がその場で自分の経路に対応する値をスタンプする:

| 値 | 経路 | 人間の確認 |
|---|---|---|
| `default` | `wikicommit-init` の base_types 展開 | なし（無条件展開） |
| `init-theme` | `wikicommit-init` の theme 駆動型提案（Issue #490） | Enter ベース承認あり |
| `generate-interactive` | `wikicommit-generate` Pass 2b、対話実行 | Enter ベース承認あり |
| `generate-auto` | `wikicommit-generate` Pass 2b、非対話自動承認（Issue #507） | なし |
| `collect` | `wikicommit-collect` の Type Proposal ステップ（Issue #489） | Enter ベース承認あり（常に対話実行） |
| `schema-propose` | `wikicommit-schema-propose`（Issue #285） | PR レビュー必須（auto-merge しない） |
| `manual` | 人間が `.wikicommit/schema/` を直接編集して作成（Skill を経由しない。Issue #548） | 人間自身が書いた（この行だけ列の意味が異なる — 他の6値が「Skill の提案を人間が承認したか」を表すのに対し、ここでは人間が起案者そのもの） |

このフィールドは一度書いたら値が変わらない恒久スタンプである。Wiki ページ側の `generated_by`/`generated_at` は `action: update` での再生成のたびに書き換わる（`.claude/skills/wikicommit-generate/SKILL.md` Pass 3）ため類似の例ではない — `provenance` が実際に不変である根拠は、スキーマファイル自体が、機械（Skill）からは各 Skill の「追加のみ可・既存ファイルの編集/上書き不可」という narrow exception のもとでしか書き込まれない（§5.1・各 Skill の Pass 2b 等参照）ため、機械が書き込み後にこのフィールドを書き換える経路がそもそも存在しないことにある（人間の直接編集はこの限りではない — 下記 `manual` のコールアウト参照）。「レビュー済みかどうか」を表す `review_status` のような遷移フィールドではなく「どうやって生まれたか」を表すフィールドであるため、ライフサイクル管理（いつ誰が消す/更新するか）を持たない。

> **`manual` — 人間が直接手書きした経路（Issue #548）**: CLAUDE.md の書き込み権限ルールが `.wikicommit/schema/` への書き込みを禁じている相手は **LLM/Skills** であり、人間が自分でこのディレクトリを編集することは元から禁じていない。`dev/pilot-ai-driven-dev-wiki-round5.md` では、まだ 1 ページも存在しない型を先に定義したいという理由で、人間がどの Skill も経由せず `custom/Practice.md` を直接作成した。この操作自体は正当だが、対応する `provenance` 値が enum に無かったため、パイロット側が独自に `manual` と書いていた（enum のどの値にも当たらない文字列が `.wikicommit/schema/**/*.md` の grep 監査に混ざる、という形で顕在化した）。上表はこの実際に書かれた値をそのまま enum に採り入れたものである。
>
> **`provenance` を書かない**という選択肢（Issue #548 の対応方針 2）は採らなかった。フィールドの欠如は既に「この機能追加より前に作られた」ことを意味しており（下記）、そこに「人間が手で作った」という第二の意味を重ねると、欠如を見たときにどちらなのか区別できなくなるため。人間の直接編集を非推奨とし `wikicommit-schema-propose` 経由に一本化する案（同 3）も採らなかった — 同 Skill は `check_schema_coverage.py` による事後検出（＝その型を使ったページが既に存在すること）を起点とするため、上記の「まだ 1 ページも存在しない型を先に定義したい」というケースはそもそも検出対象にならず、代替経路として成立しない。
>
> `manual` は他の 6 値と 1 点だけ性質が異なる: 他の 6 値がいずれも機械（Skill）による書き込みを指すのに対し、`manual` だけは人間による書き込みを指す。この違いにより、上段の不変性の根拠（機械には書き換え経路が無い）は `manual` の書き込みそのものをカバーしない。ただし「人間はファイルを後から編集できる」こと自体は `provenance` の値に依存せず、人間は `schema-propose` 等で作られたファイルも同じように手編集できる — つまり不変性は、機械的な保証ではなくこの規約によって担保される: 「どうやって生まれたか」を表すフィールドである以上、Skill が作ったファイルを人間が後から手直ししても `provenance` は書き換えない（生まれた経路は変わらないため）。`manual` を書くのは、そのファイル自体を人間が起案したときに限る。

情報提供専用のフィールドであり、`validate_frontmatter.py` 等の CI 検証には接続しない（値の有無・妥当性で `wikicommit-merge` をブロックしない）。監査したい場合は `.wikicommit/schema/**/*.md` を直接 grep すれば足りる。

各書き込み箇所は `.wikicommit/schema/default.md` と `.wikicommit/schema/Person.md` を「固定の書式リファレンス」として参照する（§5.2 冒頭の型スキーマ例もこの2ファイルに準拠）。このとき `Person.md` 自身が持つ `provenance: default` の値をそのままコピーしないこと — それは `init.py` の base_types 展開専用の値であり、各書き込み箇所は上表の自分自身の経路に対応する値を書く。

本機能追加より前に作られた既存のスキーマファイル（配布済みパイロットリポジトリのスキーマファイル）への遡及付与は行わない。`provenance` フィールドの欠如は「この機能追加より前に作られた」ことを意味し、新旧混在を許容する（本ドキュメント各所で踏襲されている既存パターンと同じ）。

> **このリポジトリ自身の `.wikicommit/schema/*.md` は対象外（`Issues/` 草案 `p3-216-schema-mirror-drift-issue523.md`（非公開の開発リポジトリ側の記録）。GitHub Issue 未登録）**: 上記の「既存ファイルへの遡及付与は行わない」は、`.wikicommit/schema/` が `.claude/skills/wikicommit-init/scripts/templates/schema/` の手動コピーだった時代（この対象外化を導入した当初）を前提にした記述だった。手動コピー運用は「テンプレートだけ直して root への反映を忘れる」drift（Issue #71/72/73/74、直近では Issue #523/#536 由来のドリフト）を繰り返し招いたため、この対応で `.wikicommit/schema`（および `.wikicommit/scripts`）を templates 配下への symlink に置き換えた。symlink 化後は root 側は独立したファイル実体ではなく templates と文字通り同一のファイルになるため、`provenance: default` を含む templates 側の内容がそのまま見える（詳細は `tests/test_template_mirror_sync.py` のモジュール docstring参照）。

### 5.3 カスタム型（`.wikicommit/schema/custom/*.md`）

> **`custom/` は `.wikicommit/entity/` では必須、`content/`（公開サイト）には存在しない — この非対称は意図的である（Issue #576）**: `custom/` は「カスタム型を入れるフォルダ」ではなく**型名そのものの一部**であり（スキーマファイルの位置は §5.1 のとおり `type:` からのパス導出のみで決まる）、この接頭辞が担う唯一の役割は「この型は Schema.org 語彙に無いので機械検証をスキップせよ」というマーカーである。実際に分岐しているのは `validate_frontmatter.py`（Issue #512 の「語彙に無い型＝誤字」ERROR に対する唯一の逃げ道）・`check_property_wikilink_reinforcement.py`（RANGE 分類が引けないため）・`wikicommit-jsonld` プラグイン（不正な `@type` を出さないため）の3箇所で、3つ目が効いている以上このマーカーはスキーマファイル内のフィールドではなく**型文字列自体**に載っている必要がある（publish 側のプラグインは `.wikicommit/schema/` を一切読まず、frontmatter の `type:` 文字列しか持たない）。
>
> 一方 `.wikicommit/entity/` が型名をディレクトリツリーへそのままミラーする結果、この機械検証用のマーカーが Explorer の左パネル・パンくず・Quartz の folder page・URL にも「フォルダ」として現れていた。読者にとって `custom` は完全に内部語彙であり意味を持たない。そこで `convert_wikilinks.py` が**publish 時にのみ**先頭の `custom/` セグメントを落とし、`content/<lang>/<Type>/<slug>.md` として書き出す（`.wikicommit/entity/` のディレクトリと `type:` の値は一切変更しない）。この位置で切ることで上記4つの表示面が一度に揃い、Issue #512 のガードもそのまま残る。
>
> **したがって「entity 側は `custom/` 必須／content 側は無し」という食い違いは、どちらかに揃えるべきドリフトではない**。揃えようとすると、entity 側から外せば `rebuild_index.py` が `type: schema:Decision` を書いて `validate_frontmatter.py` が落ち（Issue #512 のガードが壊れる）、content 側に戻せば読者に内部語彙が再び露出する。
>
> **実装上の要点**（`convert_wikilinks.py`）: `custom/` はエンティティへのルックアップキーと出力パスの両方に使われるため、**前者は絶対にフラット化してはいけない**。`flatten_custom_type()` / `flatten_entity_rel()` は出力パスとリンク生成にのみ適用し、`.wikicommit/entity/` の実ファイルを読む箇所（WikiLink の存在確認・`generated_pages[]` の frontmatter 読み取り）は `custom/` を保ったまま使う。出力パスは `main()` が一度だけ計算して `convert_file()` と stale cleanup の書き込み集合の両方へ渡す — 片方だけフラット化すると、書いた直後のファイルを同じ実行内で削除してしまう（Issue #271）。
>
> **本文中の相対パスも同時に書き換える**。ページが1段浅くなるため、`![alt](../../../assets/diagram.png)` のような素の Markdown リンク（WikiLink 変換の対象外）はそのままでは壊れる。`rewrite_relative_links()` が WikiLink 変換の**前に**（変換後の本文には既に出力ディレクトリ基準のリンクが混ざるため）ソースディレクトリ基準の相対リンクを出力ディレクトリ基準へ再計算する。Issue #589 でローカル画像が実際に公開サイトへ届くようになったため、これは潜在的な問題ではなくフラット化と同時に顕在化する実害だった。
>
> **フラット化後に同名となる2つの型の扱い**: カスタム型は定義上 Schema.org 語彙に存在しない名前なので、インストール済み標準型と衝突することは現時点では起こり得ない。ただし将来 Schema.org 側に同名の型が追加されて後からインストールされる可能性はゼロではないため、`main()` は全ページの出力パスを先に計算して衝突を検出し、**フラット化されていない側を常に優先**して、フラット化された側を `WARNING` 付きでスキップする（ビルド全体を失敗させない — 対処は型名の変更でありスクリプトではなく作者の仕事のため）。`flatten_custom_type()` が先頭1セグメントしか落とさないのも、写像を単射に保って2つの異なる型が同じ出力パスに解決されないようにするためである。

Schema.org にない型はカスタム型として定義する。Schema.org ベース型と異なり、プロパティの意味・型・制約を明示的に記載する（LLM がカスタム型の詳細を学習していないため）。カスタム型は Schema.org 語彙に存在しないため、`properties:` 配下のキーは `validate_frontmatter.py` の domainIncludes 機械検証の対象外（`type:` が `schema:custom/` プレフィックスを持つページは無条件でスキップされる）— プロパティの妥当性は `wikicommit-schema-propose` の PR レビュー時に人間が確認する。

```markdown
---
wikicommit:
  base: https://schema.org/CreativeWork   # closest parent type (reference)
  provenance: schema-propose
  rationale: "Schema.org has no type for an internal decision record; CreativeWork is the closest parent but does not carry the decision-specific properties below."
  granularity:
    - Create a new page for each independent decision
title: ""
type: "schema:custom/Decision"
sources: []
tags: []

properties:
  description: ""          # one- or two-sentence summary of the decision
  decidedAt: ""            # decision date (ISO 8601)
  decidedBy: ""            # decision maker ([[Person/xxx]] format)
  rationale: ""            # reasoning behind the decision
---

(summary of the decision)

## Rationale
(reasoning behind the decision)
```

カスタム型を書き込む Skill 経路は `wikicommit-schema-propose` の Step 5 のみ（他の 3 Skill の型提案はいずれも Schema.org 標準型に限られる）であるため、Skill 由来のカスタム型の `provenance` は常に `schema-propose` になる。人間が直接手書きした場合は `manual`（§5.2 の enum 一覧参照）。

#### 配布テンプレートにカスタム型を同梱しない（Issue #551）

`.claude/skills/wikicommit-init/scripts/templates/schema/custom/` は空（`.gitkeep` のみ）であり、**カスタム型を配布テンプレートに同梱した前例は無い。これは偶然ではなく方針である**。

問いが具体的な形で立ったのは Issue #551 である。`dev/pilot-ai-driven-dev-wiki-round5.md` の 135 ページの Wiki で、実践的なテクニック（ループの回し方・ファイル横断の fan-out・敵対的レビューの差し込み等）がいずれも `DefinedTerm` として生成され、`HowTo` は 0 件だった。Schema.org 語彙（全 933 型）を調べると、**「実践ノウハウ」に対応する汎用型は存在しない** — 型名に `practice`/`technique`/`method`/`procedure`/`guideline` を含む型は 15 件あるが、内訳は医療領域 10 件（`MedicalGuideline`・`SurgicalProcedure` 等）と商取引・計測 5 件（`PaymentMethod`・`DeliveryMethod` 等）で、汎用の `Practice`・`Technique` は無い。ノウハウを実体としてモデル化しているのは `MedicalGuideline`（`evidenceLevel`・`evidenceOrigin` を持つ）だけで、その設計は医療領域の外へ一般化されていない。round5 のパイロットは実際に `custom/Practice` を手書きし、`MedicalGuideline` から `evidenceOrigin` を借りて合成ページを生成することで実用的な結果を得ている。

それでも**配布はしない**。判断の根拠は 3 つある:

1. **`dev/PRD.md` §3 のターゲットユーザー像は実践知に特化していない**。4 セグメント（個人の調査メモ・創作物／チームの社内ドキュメント／AI インフラの知識ソース／非技術者）はいずれもドメイン一般であり、コアバリュー（§4.1）も「レビューを構造化して信頼できる知識を作る」ことであって実践知の記録ではない。実際のパイロットも保育手続き・コーヒー・さいたま市・アルセーヌ・ルパン・デカメロン・AI 駆動開発と多岐にわたり、`custom/Practice/` ディレクトリが意味を持たない Wiki の方が多い。Convention over Configuration（ディレクトリにファイルを置けば型が有効）は、置いた型が全 Wiki で有効になることも同時に意味する。
2. **カスタム型は `validate_frontmatter.py` の `domainIncludes` 機械検証の対象外である**（本節冒頭）。全 Wiki に一律配布する型がその検証を受けないことは、PRD §4.3 が掲げる「スキーマ一貫性が保証された知識層」という価値提案を、最も広く行き渡る場所で弱める。標準型だけを配り、語彙の外に出る判断は各 Wiki が自分の文脈で行う、という現在の分担が理にかなっている。
3. **必要な Wiki が自前で作る経路は既に 3 つある** — `wikicommit-generate` Pass 2b（Issue #315。ただし標準型のみ）・`wikicommit-schema-propose`（Issue #285。カスタム型を書ける唯一の Skill 経路）・人間による直接編集（`provenance: manual`、Issue #548）。round5 のパイロットが実際に採ったのは 3 番目で、成功している。配布しないことで失われる能力は無く、増えるのは各 Wiki が一度型を作る手間だけである。

**型名の議論もここで閉じる**。Issue #551 は候補を 4 つ比較していた（`Practice`／`Pattern`／`Technique`／`Guideline`。`Recommendation` は `schema:Recommendation` が実在するため除外）。多義性が実害になるのは全 Wiki に一律配布する場合に限られる — 英語 practice は「慣行」「練習」「開業・事務所（medical practice / law practice）」の多義であり、医療・法務ドメインの Wiki では誤読される。配布しない以上、型名はその Wiki の文脈が多義性を解消するため各 Wiki が自由に決めてよく、WikiCommit 側が中立な名前を選ぶ必要は無い。なお `Practice`・`Pattern`・`Technique`・`Method`・`Approach`・`Guideline`・`Playbook`・`Heuristic` はいずれも Schema.org 語彙に存在しないため、将来の標準型と名前が衝突するリスクは低い（`.wikicommit/schemaorg-vocab.json` で確認済み）。

**採らなかった案**: (a) `HowTo.md` を実践ノウハウ寄りに設計し直す（`properties:` からレシピ寄りの `supply`/`tool` を外す）— `HowTo` は `childcare-procedures-wiki` で行政手続きに実際に使われており、「1 つの成果に向かう順序付きの手順列」の型として正しく働いている。実践ノウハウはその形をしていないというだけであり、動いているケースを壊してまで寄せる理由が無い。(b) `HowTo` を `base_types` から外す — 同じ理由で不可。加えて `GovernmentService.md` の `granularity` が明示的に `HowTo` へ委譲しており（Issue #569）、外すとその委譲先が消える。

**現状維持で残る唯一の欠落は「`DefinedTerm` の中で実践・手法をどう書くか」の指針が無かったこと**であり、これは配布テンプレート側で埋めた。`DefinedTerm` は Schema.org に汎用型が無い結果として「現象・問題」「仕組み・構成要素」「実践・手法」の 3 種類を同時に抱えており、「適用条件・前提・失敗モード・根拠の強さ」が意味を持つのは 3 番目だけである。`DefinedTerm.md` の `granularity` にこの 3 分類と 4 項目を明記し、本文テンプレートに `## When It Applies` セクション（3 番目以外では丸ごと省く旨を併記）を追加した — 型を増やさずにテンプレートが促す形にしたもので、`granularity` の散文だけでは「書くかどうかがページごとに揺れる」という Issue #551 が指摘した問題そのものが残るため、本文側にも受け皿を置いている。あわせて `HowTo.md` の `granularity` に「`tool`/`supply` が空でも HowTo である」ことを明記した（この 2 プロパティのレシピ・DIY 寄りの見た目が `HowTo` を選ばない理由として働いていた、という round5 の観察に対する、型の意味を変えない範囲での対応）。

**`HowTo` が使われない原因はこれ 1 つではない**。`dev/pilot-saitama-wiki.md` でも `HowTo` は 0 件だったが、そちらは適した型が無かったのではなく、`GovernmentService.md` の `granularity` が明示的に `HowTo` へ委譲しているのに従われなかったケースで、失敗モードが異なる（Issue #569）。両者は同じ結果に至るため、片方だけ直しても `HowTo` は使われるようにはならない。なお Issue #550 が全 `base_types` に追加した境界ルールは、`HowTo` 側に「選ぶ理由」を初めて明文化したものであり、本節の対応と同じ方向に働く。

#### `wikicommit.rationale`（Issue #548）

カスタム型に限り、`wikicommit:` ブロックに `rationale:`（なぜ既存の Schema.org 標準型では表現できず、なぜその `base:` を最も近い親として選んだのかを記す 1〜2 文の自由記述）を持たせる。標準型のスキーマファイルには置かない — 標準型は Schema.org 語彙にその型自体が実在することが選定の根拠であり、散文で補う余地が無いため。

このフィールドは新設の情報ではなく、**既に書かれているが保存先が無かった**情報の置き場である。`wikicommit-schema-propose` の Step 5 は元々「なぜ既存の標準型で代替できないか」を 1〜2 文で書き、それを PR 本文のレビュー観点として提示する手順を持っていた。しかしその文はレビュー用の PR 本文にしか存在せず、マージ後にリポジトリへ残らない。カスタム型は定義上 Schema.org 語彙の外にあり `base:` は「最も近い親型への参照（informational only）」でしかないため、選定理由は §5.5 の段階移行（`deprecated`/`replaced_by` で標準型へ寄せてよいかの判断）や、後からそのカスタム型を見た人間のレビューにとって、後から復元できない一次情報になる。同 Step 5 はこの文をファイル本体にも書くようになり、PR 本文の該当項目はそのコピーになる。

`provenance` と同じく情報提供専用で、CI 検証には接続しない（`validate_frontmatter.py` の検証対象は `.wikicommit/entity/` のページであり、スキーマファイルそのものは検証しない。同スクリプトがスキーマファイルから読むのは `wikicommit.frontmatter.required` だけで〈§5.1〉、`wikicommit:` ブロックの他のキーは一切見ない）。既存のカスタム型スキーマファイルへの遡及付与は行わない — フィールドの欠如は「この機能追加より前に作られた」ことを意味する（`provenance` と同じ扱い）。

**`properties:` 配下の `rationale` とは別物である点に注意する**。上の例の `custom/Decision` は、その型のエンティティが持つプロパティとして `properties.rationale`（その決定を下した理由）を持っている。両者は階層が異なり（`wikicommit:` ブロック vs `properties:` ブロック）、記述する対象も異なる（型の設計判断 vs そのページが記述する事物の属性）。カスタム型のプロパティ名は Schema.org 語彙の機械検証を受けない（本節冒頭）ため、この名前の重複を機械的に避ける仕組みは無く、規約として区別する。

#### カスタム型の命名規約

`.wikicommit/schema/custom/<Name>.md` の `<Name>`（= WikiLink 上の Type セグメント、例: `custom/Decision` の `Decision`）は、標準型（`Person`・`Place`・`Organization`・`Event`・`HowTo`・`DefinedTerm`）と同じ PascalCase・単語文字（英数字・アンダースコア）のみを用い、**ハイフンを含めない**（`Multi-Word` のような命名は不可）。WikiLink 正規表現（`.wikicommit/scripts/_wikilink.py` の `WIKILINK_RE`）の Type セグメントはこの規約に合わせてハイフンを許可しない文字クラスになっており、ハイフンを含む型名を作成すると `[[custom/Multi-Word/slug]]` が存在確認・orphan 判定のいずれからも一致しなくなる（Issue #114）。複数単語のカスタム型名が必要な場合は `MultiWord` のように PascalCase で結合する。

### 5.4 型選択フロー

```
ingest 時にドメインの候補リストをプロンプトに渡す
  ↓
LLM が文書内容を見て最適な型を選択
  ↓ 確信が持てない場合
{"type": "schema:Organization", "ambiguous": true, "alternatives": ["schema:Person"]}
  → human がレビューキューで型を確定する
  ↓ 確信がある場合
.wikicommit/schema/カスタム型 → .wikicommit/schema/標準型 の順で照合
  → 一致するファイルがあればそのルールを適用
  → なければ .wikicommit/schema/default.md にフォールバック
```

型選択後、Schema.org に対してバリデーションを実行する（LLM のハルシネーション対策。LLM 生成 schema.org マークアップの 40〜50% が非準拠であるという調査結果に基づく）。

型選択に関わる追加ルールは本節の以下の 2 つの小節（Issue #565・#569）が定める。型ファイル側の書き方 — 「この場合は別の型に譲れ」をどこにどう書くか — は §5.2「型間の優先関係は `granularity` に書く（専用キーは設けない。Issue #569）」を参照。

#### 候補同士が祖先／子孫関係にある場合は最も具体的な型を選ぶ（Issue #565）

上のフローは「`.wikicommit/schema/` に置かれているファイルの中から選ぶ」としか述べておらず、**候補同士が祖先／子孫関係にある場合にどちらを選ぶか**を規定していなかった。祖先型は常に当てはまる — Schema.org 上 `Park`・`Museum` は `Place` の子孫なので、公園を `Place` として書くことは**誤りではなく粒度が粗いだけ**である — ため、広く馴染みのある型が既定で選ばれる。

`wikicommit/saitama-city-wiki` では `Park.md`・`Museum.md` が人間の承認を経てインストールされていたにもかかわらず、公園 7 件・博物館 2 件が素の `Place` として生成された。**しかも型ファイルを追加したのと同じバッチで**（`Park.md` と `Place` に落ちた公園ページの `generated_at` はすべて同日）、「型リストが古かった」という説明は成り立たない。品質ゲートは全て通り、`check_schema_coverage.py` も 0 件を報告し続けた（`Place` にはスキーマファイルがあるため）。

これは Issue #447 が `DefinedTerm` について発見した力学と同一である。#447 の分析が述べる「技術的に表現できてしまうという事実自体が新型提案を見送る理由になっていた」という構造が、型を**提案する**段（Pass 2b。#447 の対象）だけでなく、インストール済みの型を**選ぶ**段（Pass 2c）でも働く。

**規則**: 複数のインストール済み型が当てはまる場合、最も具体的な型（`--list-installed-hierarchy` の鎖で最も下にあるもの）を選ぶ。ただし 2 つの限定が付く。

- **インストール済みの型に限る**。Schema.org には存在するが `.wikicommit/schema/` にファイルが無い型へ手を伸ばすのは Pass 2b の仕事であり、この段の仕事ではない
- **具体性が適合性に優先することはない**。ソースがその主題を公園だと実際に立証していないなら、`Place` が正解であってフォールバックではない

**判断材料は決定論的に渡す**。`check_schema_org_type.py --list-installed-hierarchy`（Issue #565）が、インストール済み型それぞれについて**インストール済みの祖先型のみ**を近い順に出力し、Pass 2c がこれをコンテキストに含める。間に挟まる非インストール型（`Park` と `Place` の間の `CivicStructure` 等）は名前を出さない — Pass 2c が選べるのはインストール済みの型だけであり、選べない型を提示しても迷わせるだけであるため。

**受け皿型のテンプレート側にも書く**。`Place.md`（子孫 208 型）・`Organization.md`（166 型）・`Event.md`（35 型）の `granularity` に「より具体的な型がインストールされているなら譲る」旨を追記した。全 `base_types` の子孫型数を機械的に数えた結果、この 3 型だけが桁違いに大きい（次点は `NewsArticle` の 6 型、他は 2 型以下）。`DefinedTerm` は Issue #447 が既に同種の記述を持つ。**この追記は Pass 2c の一律ルールに対する人間可読性の補強であって適用範囲の宣言ではない** — Issue #523 が property の WikiLink 化補強について確立したのと同じ位置づけであり、記述を持たない型が適用除外になるわけではない。

**取り残しの検出**は `check_installed_type_usage.py`（`docs/DesignDoc-ScriptSpec.md`）が担い、`wikicommit-status` Step 9 が報告する。`check_schema_coverage.py` の対（`check_orphans.py` と `check_wanted_pages.py` が対であるのと同じ関係）。

**既存ページの型の再分類は本 Issue のスコープ外**とする（Issue #447 と同じ判断）。型変更はディレクトリ移動と、そのページを指す全 WikiLink の Type セグメント書き換えを伴い（§5.5）、それを PR 化する新規 Skill（または `wikicommit-schema-propose` の拡張）が必要になる。本 Issue が扱うのは**新規生成時に正しい型が選ばれること**と**取り残しが検出できること**に限る。

> **上記フローの構造的な限界と、Pass 2b によるその場での解消（Issue #315。旧 `better_type_candidate` 方式からの変更）**: 上記フローは `.wikicommit/schema/` に**既に置かれているファイル**の中から選ぶだけで、Schema.org 語彙全体（923型規模）を探索しない。`Game.md` や `GovernmentService.md` を誰かが手で置かない限り、LLM は絶対にそれらを選択肢に入れられない — `installed schema/` 内の型で「一応表現できてしまう」場合は `ambiguous: true` にも該当せず、この構造的な穴を素通りする。当初（Issue #285）はこの穴を`better_type_candidate`/`better_type_rationale`という間接的な警告フィールドで塞ごうとした（Pass 2 が Schema.org 型名+説明文の全一覧をプリロードし、`installed schema/` 内の型より明確に良い適合先が見つかった場合に記録するが、ページ生成自体は変わらず `installed schema/` 内の型で行い、実際の型追加は別セッションで `wikicommit-schema-propose` を実行して初めて反映される設計）。しかしこの間接性そのものが問題だと判明した — `llm-agent-research-wiki` パイロットで、`/wikicommit-generate` の Completion Notice が報告した `better_type_candidate` を**別セッション**で拾おうとしたところ、`wikicommit-schema-propose` の検出源である `check_schema_coverage.py` は「実際に使われている `type:` 値のうち専用schemaファイルが無いもの」しか見ないため、既に `installed schema/` 内の型（例: `DefinedTerm`）で生成済みのページはそもそも検出対象にならず、情報が構造的に失われることが分かった（詳細は `Issues/registered/p3-112-schema-type-selection-inline-proposal.md`（非公開の開発リポジトリ側の記録））。
>
> Issue #315 はこれを、`wikicommit-generate` Pass 2 内に「型の要否判断」ステップ（Pass 2b）を新設し、その場で解決する設計に変更した: サマリを見て `installed schema/` 外の型が明確に良いと判断すれば、`check_schema_org_type.py` で型・プロパティの実在を検証した上で Enter ベースの承認を求め、承認されれば `.wikicommit/schema/<Type>.md` をその場でローカルに新規作成し（`wikicommit-init` の theme 駆動提案・Issue #286 と同じ「追加のみ可・既存ファイル編集不可」の書き込み例外を `wikicommit-generate` にも適用）、続くエンティティ抽出（Pass 2c）でその新しい型を直接使ってページを生成する。`better_type_candidate`/`better_type_rationale` フィールドは不要になったため分析JSON形式から削除した。新規schemaファイルは通常の `.wikicommit/entity/`・`.wikicommit/source/` の変更と同じバッチで `wikicommit-merge` が自動マージする（既存schemaファイルの変更は引き続き対象外・`wikicommit-schema-propose` の非auto-mergeなPR経由のみ）。詳細は `docs/DesignDoc-skills.md` §11.6・`.claude/skills/wikicommit-generate/SKILL.md` Pass 2 を参照。
>
> `wikicommit-schema-propose`（Issue #285）自体は廃止せず存続する。役割は「型は検出するが生成には反映しない」主経路から、`check_schema_coverage.py` による**事後検出**（Issue #315 以前に生成済みのページの救済、および Pass 2b で人間が却下したケースの再検討）という補完的な安全網に変わった。
>
> **非対話実行時のデフォルト却下そのものを見直し（Issue #507）**: Issue #315 の Enter ベース承認（デフォルト N）は対話実行を前提としており、Claude Code のサブエージェント経由等の非対話実行では Enter プロンプトに人間の実回答が返らず、常にデフォルト N（却下）に倒れて型が消える問題があった。Issue #489（`wikicommit-collect` の Type Proposal ステップ）・Issue #490（`wikicommit-init` の軽量型提案の限定復活）はこの根本原因に対し、Pass 2b 自体には手を入れず証拠の強さが異なる別の入口を追加する形で対応したが、これは意図的なスコープ限定であり、最も証拠が強い Pass 2b（実ソース文書全文が根拠）自身は非対話実行下で型を取りこぼし続けたままだった。
>
> Issue #507 は Pass 2b 自身に踏み込み、対話実行かどうかを明示的に判定した上で分岐する設計に変更した。対話実行時の閾値・Enter ベース承認（デフォルト N）は変更しない。非対話実行を検出した場合のみ、`wikicommit-init`（Issue #490）・`wikicommit-collect`（Issue #489）と同じ「theme文／候補群からではなく実ソース内容から明確に断定できる場合のみ」という、より厳格な追加の閾値をその候補に適用する。この厳格な閾値をクリアした候補は、Enter プロンプト自体を表示せずデフォルト **Y** として扱い `.wikicommit/schema/<Type>.md` をその場で新規作成する。クリアしない候補はこれまで通り却下扱いとし、却下候補をどこにも永続化しない設計（Issue #315 Step 5）は維持する — 却下候補を後で拾える形で残すこと自体が旧 `better_type_candidate` 方式の問題（本節前段のパイロットでの型情報消失）の再発になるため。非対話実行で自動承認された型は、schema ファイル自体には特別なマーカーを残さず、`wikicommit-merge` が拾う通常の PR レビューが事後の確認機会になる（専用のレビュー追跡 Issue は導入しない）。詳細は `.claude/skills/wikicommit-generate/SKILL.md` Pass 2b・Completion Notice テンプレートを参照。

#### 1 ソースから型の異なる複数エンティティを切り出してよい（Issue #569）

Pass 2c の分析 JSON の `entities` 配列は元から単一型に制限されていないが、**そのように切り出せることが明示されていなかった**ため、1 つの主題に寄ったソースは 1 エンティティとして出てきやすかった。「あるモノ」と「それを使う手順」の両方を扱うソースは両方を抽出してよい — サービスとその申請手順、ソフトウェア製品とそのセットアップ手順、施設とその入館手続き。§5.2「型間の優先関係は `granularity` に書く」で挙げた `household-waste-disposal` は本来「収集サービス本体（`GovernmentService`）」と「粗大ごみの出し方（`HowTo`）」に分割すべきだった。

ただし**各部分がそれ自体で主題として立つ場合に限る**。このルールを満たすために 2 つ目のエンティティをでっち上げない。

**既存ページへの遡及適用はしない**。`/wikicommit-generate --regenerate` は Pass 2c を実行しない（ページ起点で型を所与とする）ため、既に 2 つの主題を抱えた 1 ページを分割することはできず、型の再分類と同じくスコープ外である（`docs/DesignDoc-pipeline.md` §6.1 の再生成モード節）。

#### ソースがすれ違いに引用しただけの文書はエンティティにしない（Issue #968）

ソースが別の話を書きながら 1 回だけ名前を出した文書（対比のための引用・関連研究の 1 行・参考文献リストの項目）は、Pass 2c が `entities` に出さない。逆に、ソースがその文書を**自分の主題として**扱っているものは通常のエンティティである。

**この規律は既に 2 箇所にあったが、どちらもエンティティを切り出した後の段にしかなかった** — Pass 3 の Secondary citation discipline（Issue #473）と `review-rules.md` の check 4（Issue #832）である。結果として、passing mention された文書はエンティティとして切り出され、ページとして書かれ、**レビューで初めて却下される**。却下は正しいが、そこに至るまでに Pass 3 の生成 1 回分が無駄になる。`review-rules.md` の check 1 は「片側にしか書かれない境界は片側にしか適用されない」と自ら書いており、**その教訓が 1 段上でも当たっていた**（Issue #550）。

**しかも 1 回の無駄で終わらない。** `wikicommit/ai-driven-dev-wiki` の arXiv 2602.06310 は、却下されたページが `failed_pages` に記録されるため `status: partial` かつ `failed_pages` 非空となり、Pass 1 の収集条件に**毎回一致する**。入力（ソース本文・`theme`・`entity-policy.md`・型テンプレート）が 1 バイトも変わらないので出力も毎回同じで、実行のたびに同じエンティティを切り出し・同じページを書き・同じ `MISSING_SOURCE` で却下する。Issue #567 は `failed_pages` の空／非空を「再試行に意味があるか」の代理指標として使ったが、**本件はその代理指標が外れる実例**である（意味としては off-`theme` 除外と同じく決定論的に再現するのに、記録先が `failed_pages` なので再試行側に入る）。本ルールが効くと次の実行で `failed_pages` が空になり、そのソースは収集条件から外れる — **移行作業も遡及処理も要らず、ループが自分で止まる**。

**`exclude` としては表現できない。** `exclude_reason` は `theme_mismatch`（関連性）と `privacy`（許容性）の 2 値であり、本件が引っかかるのは**証拠**の軸（根拠となる文書が `sources` に無い）でどちらでもない。加えて Pass 2c は前回のレビュー記録を読まないため、判定が次の実行へ伝わる経路も無い。

決定した 4 点（`docs/DesignDoc-skills.md` §11.6 に判定の文面がある）:

| 論点 | 決定 |
|---|---|
| 判別がつかない場合 | **passing mention 側に倒して抽出しない。** check 4 が同じ引き分けを同じ側に倒すためであり、Pass 2c だけが寛容だとその差分が無駄な 1 周を構造的に保証する |
| 登録簿を見るか | **見ない。** `.wikicommit/source/` は Pass 2c のコンテキストに元から無い。別途登録されていればそのソース自身の実行がページを作る |
| 非抽出の記録 | **残さない**（無言のまま受け入れる）。3 つ目の `exclude_reason` は消費者のいない enum になる（Issue #553）。誤りの向きが安全なのは片方向だけである — passing mention を落とす側は「Pass 4 が却下していたページが 1 段手前で消える」に留まるが、主題として扱われている文書を誤って落とす側はレビューを通ったはずのページを無言で失い、書かれなかったページは orphan でも wanted page でもないので検出もされない。引き分けの倒し方は判別がつかない場合に限り、過剰適用しない |
| Pass 3 の規律 | **残す。** 3 段が下している判断は別物であり（作るか／書くか／FAIL にするか）、同じ命題の言い換えではない。Issue #552 の「共通ルールを個別の場所で言い直さない」には当たらない |

**Pass 2a の source-as-entity 判定（Issue #475）とは別物である** — あちらは「ソース文書**自身**をページ化するか」、こちらは「ソースが**引用した別の文書**をページ化するか」。上記 arXiv ソースでは 1 回の実行で両方が発火し、前者（論文自身のページ）は正しく、後者（対比のために引用された別論文）は誤っていた。

**効果を測る一般的な手段は無い**（Issue #669 / #798 と同じ状況。抽出精度の eval 基盤がこのリポジトリに無い）。壊れ方が軽いことを根拠に採った。**既存ページへの遡及は行わない**（新旧混在を許容する方針）。既に書かれた passing-mention 由来のページは `/wikicommit-remove` で人が下ろす。

> **導入後、交絡の無い対照が 1 つ取れた（Issue #970）**: `wikicommit/ai-driven-dev-wiki` で、上記 arXiv ソースを 2 日続けて処理した。
>
> | 実行 | 本ルール | `ScholarlyArticle.md` の `granularity` | `## User Notes` | 対比のために引用されただけの論文 |
> |---|---|---|---|---|
> | 2026-09-18（0.6.1） | 無し | 同じ境界を既に述べていた | 無し | 切り出され、Pass 4 が却下して `failed_pages` へ |
> | 2026-09-19（0.7.0） | あり | 変更なし | 無し | 切り出されなかった |
>
> 型テンプレートは期間中、パイロット側・配布側とも変わっていない。したがって**動いた変数は本ルールだけである**。そして 9/18 の実行でも、同じ境界（"A paper mentioned only in passing … do not create a page for it"）は Pass 2c の目の前にあった — Pass 2c は各型の `granularity` をコンテキストとして受け取る。
>
> **これは「型テンプレートの `granularity` に書いた境界は、その Pass 自身の指示に書いた境界より弱い」の 2 例目である。** 1 例目は §5.2「型間の優先関係は `granularity` に書く（Issue #569）」で、そこで分かったのは「`granularity` に書いても従われなかった」までだった。対応は書く側と読む側を同時に入れたため、どちらが効いたかは切り分けていない。今回は Pass 側だけを動かしたので、**Pass 側に書けば従われる**ことの直接の証拠になる。
>
> **限界を 2 つ併記する。** (1) 両側とも 1 回ずつの実行であり、Pass 2c は非決定的である。eval 基盤が無いことは変わっておらず、**「常に効く」とは読まない**。言えるのは、1 例目の否定的な観察に、片側だけを動かした対照が 1 つ加わったところまでである。(2) 9/19 の完了通知は本ルールを理由に挙げていたが、それはエージェントの事後説明であって因果の証明ではない。**根拠は対照の組み方（他の変数が動いていないこと）の方にある。**
>
> **次のパイロットの観察項目からは外す。** 新しい事例には「旧ルールの下でも切り出さなかったか」というベースラインが無いため、同じ観察を繰り返しても今回より弱い結果しか得られない。代わりに、**同じ形 — 型テンプレート側のルールが先にあり、後から Pass 側へ移した — が再び現れたときは記録する。** 対照が成立するのはその形のときだけで、稀である。
>
> **考えられる理由（未検証）**: 型スキーマファイルの大半は frontmatter の雛形・`properties:` の候補・本文の節であり、「そのページを書くならどう書くか」を述べている。「書くかどうか」を述べるのは `granularity` の数行だけで、それも型紙の中の 1 項目として、全型分がまとめて Pass 2c のコンテキストに並ぶ（Pass 2c の指示本文とは別の、型ごとの参照資料として読まれる） — #569 の「HowTo に譲れ」も `GovernmentService.md` の中にあった。**上の対照が示すのは「Pass 側に書けば従われた」までで、この理由は確かめていない。**
>
> **設計上の目安**: 「書くかどうか」（切り出す・切り出さない・別の型に譲る）の境界は、それを判断する Pass の指示に置く。型テンプレートには「どう書くか」を置き、同じ境界をそこにも書くのは人が読むための補強と位置づける（Issue #523 が property の WikiLink 化の補強について確立した位置づけと同じ）。**`granularity` に書くのをやめる、という意味ではない** — 片側だけでは足りない、ということである。同じ理由で、`/wikicommit-update` で型テンプレートの差分を取り込んでも、それだけで抽出の挙動が変わるとは限らない。

### 5.5 スキーマの進化とマイグレーション

Breaking な変更は `deprecated` フラグによる段階移行を必須とする。

```yaml
# .wikicommit/schema/Event.md（Incident カスタム型へ移行する場合）
deprecated: true
replaced_by: Incident
```

移行手順:

1. `deprecated: true` を付与した PR をマージ（CI は warning のみ・非ブロッキング）
2. `wikicommit migrate --from Event --to Incident` で移行 PR を自動生成（Phase 2 CLI で実装）
3. 移行 PR をレビュー・マージ（`.wikicommit/entity/` のディレクトリ移動 + WikiLink 一括書き換え）
4. `.wikicommit/schema/Event.md` を削除する PR をマージ

### 5.6 フェデレーション設計

複数の WikiCommit リポジトリ間でのページ相互参照（フェデレーション）の実装方針。

#### 発見

`wikicommit.json` + GitHub トピック `wikicommit` によるリポジトリ発見。Phase 4 で実装。

#### 相互参照

Wikidata QID が付与されているページは QID ベースで参照（URL 変更に強い）。QID なしのページは URL リンクで参照（通常の Markdown リンクと同等）。

#### エンティティ同一性

Wikidata QID を正規の識別子とする。QID のないエンティティは URL 参照のみとし、フォールバック解決は行わない。

#### 信頼伝播

承認者の GitHub アカウントを Git 履歴に記録・表示する。参照先の承認者を信頼するかは読者が判断し、システムは強制しない。
