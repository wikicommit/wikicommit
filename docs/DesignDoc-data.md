# WikiCommit — リポジトリ構造・データ設計・スキーマ層

> **対応DesignDoc**: 元 §3・§4・§5
>
> このファイルは**いま何が仕様か**を書く。各判断の経緯（以前の挙動・採らなかった案・実測の記録・Issue 番号ごとの議論）は [history/DesignDoc-data.md](history/DesignDoc-data.md) の同じ見出しの下にある。

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
│   ├── relations.yml           # ページ同士の関係の判断記録（1 判断 ＝ 1 項目。/wikicommit-relate が追記する）
│   ├── groups/                 # 型ごとのページのグループ分け（<Type>.yml。/wikicommit-organize が書く。§4.5.3）
│   ├── run/                    # 実行記録（1 実行 ＝ 1 ファイル。git 追跡外・ローテーションあり）
│   ├── guides/                 # 人が一度だけ手でたどる手順書（1 タスク 1 ファイル・英語）
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
│   ├── settings.json           # skillOverrides（init.py が 3 キーだけをマージする）
│   └── skills/                 # Skills の正本（Claude Code が直接読み込む）
│       ├── wikicommit-init/
│       │   └── SKILL.md
│       ├── wikicommit-generate/
│       │   └── SKILL.md
│       └── ...（他 Skill）
```

既存リポジトリに対して `/wikicommit-init` を実行する場合、既存のファイルは移動・複製せずに保持し、`.wikicommit/` のみを追加する。Wiki ページの `sources.path` は `src/auth.py` のように既存ファイルを直接参照する。

`.claude/skills/` は Claude Code が固定配置を要求するため、`.wikicommit/` の外に置くプラットフォーム連携層とする。

#### `entity/assets/` の公開経路とファイル名規約

`.wikicommit/entity/assets/` は全言語共通の画像・添付ファイルの唯一の置き場である。`convert_wikilinks.py` の `sync_assets()` が配下の全ファイルを `content/assets/` へミラーし（元ファイルを消すと次回実行で `content/assets/` からも消える）、Quartz v5 の builtin `Assets` emitter が `public/` へコピーする（`quartz.config.yaml` の変更は不要）。

- ページからの参照は `.wikicommit/entity/<lang>/<Type>/<slug>.md` から見た相対パス（例: `![alt](../../assets/diagram.png)`）で書く（`docs/DesignDoc-publish.md` §8.6）。カスタム型ページは公開時に `custom/` セグメントが落ちて 1 段浅くなるが、`convert_wikilinks.py` の `rewrite_relative_links()` が吸収するので、本文は常に `.wikicommit/entity/` から見た相対パスで書けばよい（§5.3）
- **ファイル名**は小文字英数字・`-`・`_`・`.` を推奨し、**スペース・大文字・`&`・`%`・`?`・`#`・`<>:"|*` を使わない**。`Assets` emitter は `slugifyFilePath()` を通して出力名を決めるため、これらを含む名前は公開側で別名になり本文の相対パスと食い違う（`My Diagram.png` → `my-diagram.png`、`a&b.png` → `a-and-b.png`、`50%.png` → `50-percent.png`）。文字種以外にも、`_index.png` は `index.png` に、**親ディレクトリ名と同じ名前のファイル**（`assets/foo/foo.png`、トップレベルの `assets/assets.png` も）は `index.png` になる。非 ASCII・アンダースコア・複数ドットはそのまま通る
- `sync_assets()` はこの規則を移植した `quartz_asset_slug()` で公開名を先読みし、`content/` 起点のパス（`assets/<name>`）で判定して、食い違う場合にのみ `WARNING` を出す（ブロックしない）
- `assets/` 配下に `.md` を置くと、`Assets` emitter が除外するため添付ではなく通常のページとして描画される（`convert_wikilinks.py` のページ走査からは除外されるので二重には書き出されない）

#### README が 1 つも無いリポジトリにだけ README.md を作る

init は既存の README.md を編集しない。**GitHub が表示する位置（ルート・`.github/`・`docs/`）のどこにも、拡張子・大文字小文字を問わず README が無いときだけ**、固定の英語テンプレートにリポジトリ名を埋めて作る（LLM が書いた文章を含まないので基盤コミットにそのまま乗る）。

- ライセンスの節は `print_next_steps.py` が示す貼り付け用の文面と同じ定数（`_root_outputs.README_LICENSE_TEXT`）から作る
- 公開サイトへのリンクは Pages の `html_url` が分かる SKILL.md step 3 まで待ち、`--quartz-pages` のときだけ置いた目印を `init.py --finish-readme` が差し替える（得られなければ目印を消す）。差し込みは**同じ実行で作った README に限る**
- `_root_outputs.py` では `update: skip`・`condition: readme_created`（選択的な `git add` の列挙に入るのは作った実行だけ）。既存リポジトリでも README が無ければ次の再 init で作られる
- 読者向けの説明は見出しを置かずコメントだけにし、`theme` は流用しない（§3.3）

#### `.claude/settings.json` の `skillOverrides`

`/wikicommit-init` は `wikicommit-generate` / `wikicommit-merge` / `wikicommit-translate` の 3 本を **`name-only`** として書き込む（無人実行の経路を閉じる 3 本であり、`disable-model-invocation` を持たないため、通りすがりの依頼での自律起動を絞る）。自律起動を絞る 2 層のうち新規リポジトリ側にあたる。

| 層 | 手段 | 届く先 |
|---|---|---|
| ① | `description` を絞る | **全リポジトリ**。`npx skills add` で既存の Wiki にも届く |
| ② | この `skillOverrides` | **これ以降に init したリポジトリだけ**（遡及しない） |

- **既存の Wiki を「保護されている」と読まない** — そこでは説明文が唯一の防御である（`docs/DesignDoc-skills.md` §11.1）
- **`user-invocable-only` を採らない**。無人実行したい運用者が `on` に戻すと全 Skill の自律トリガーが復活する全か無かのスイッチになる。`name-only` は名指しの起動経路を残すので無人実行は切替なしで通る
- **既に値があるキーには一切触らない**（`--no-overwrite` の有無に関わらず）。ファイルのコピーではなく**キー単位のマージ**であり、`init.py` に専用の経路を持つ。`permissions` / `env` / `hooks` 等の利用者のキーもそのまま保つ
- **JSON として読めない場合は何も書かず `WARNING:` を出す**（上書きすれば設定を失い、黙って進めば無い保護を有るものとして報告する）
- 差分検出は `check_distribution_freshness.py` の `json_keys` で、**値ではなくキーだけを見る**（`"wikicommit-generate": "on"` は運用者の意図した状態であり `OUTDATED` にしない）
- `settings.local.json` には書かない（`.gitignore` 済みでクラウド／Routine に届かず、優先順位も逆である）
- このリポジトリ自身（wikicommit-dev2）は `user-invocable-only` であり、上の既定とは別である

#### 旧ディレクトリ名 `.wikicommit/wiki/` の後方互換

中核コンテンツディレクトリは `.wikicommit/entity/` である（旧名 `.wikicommit/wiki/`）。自動リネームは行わず新旧混在を許容する。この方針は、ページの frontmatter やレビュー追跡 Issue の本文に**文字列として埋め込まれた**旧パス（例: `translated_from: .wikicommit/wiki/ja/Person/yamada-taro.md`）にも及ぶ — これらは自動移行されず、ディレクトリを `git mv` で移した後も残る。消費する側はすべてこの後方互換を実装する:

- `.wikicommit/scripts/_wikilink.py` の `normalize_entity_prefix()` / `resolve_stored_entity_path()`（`validate_frontmatter.py`・`check_translation_status.py`・`check_derivation_freshness.py` が使用）
- `convert_wikilinks.py` の `normalize_wiki_rel()`（`generated_pages[]` 用）
- `WikiCommitSources.tsx`・`WikiCommitBanner.tsx` の `entityPathToRelativePath()`（パッケージが独立ビルドのため各自に複製）。旧プレフィックスに加えて `custom/` のフラット化も吸収する — 突き合わせ先の `relativePath` は `content/` 相対で `custom/` を含まず、直さないと custom 型の翻訳ページの sources 継承・原文リンク・`derived_from[].path` 解決が黙って効かなくなる
- `remove_page.py`（`.wikicommit/scripts/`）— `_wikilink.py` の `normalize_entity_prefix()` を import して使う
- `review-issue-close-sync.yml` のマーカー解決ロジック、`wikicommit-merge` / `wikicommit-review` SKILL.md のトラッキング Issue マーカー照合手順

新しい消費箇所を追加する際はこの一覧に加える。

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

wikicommit-dev2（このリポジトリ自身）は private のため GitHub Pages を有効化できず、Quartz 自己公開設定一式（`quartz.config.yaml`・`.github/workflows/deploy.yml`・`quartz/` submodule・`quartz-plugins/`）はルートに置かない。配布用テンプレート（`.claude/skills/wikicommit-init/scripts/templates/`）には影響しないため、`/wikicommit-init --quartz` は引き続きユーザーの wiki リポジトリに対して正しく動作する。**このリポジトリ自身に対して `/wikicommit-init --quartz` を再実行しないこと** — `init.py` の既存ファイルスキップ判定はファイルの存在有無のみを見るため、削除済みの上記ファイルは無条件に復元されてしまう。

このリポジトリの `.wikicommit/` は**テスト用の足場だけ**である — templates へのシンボリックリンク 3 本（`scripts`・`schema`・`review-rules.md`）と、ネットワークを使わないテストのための語彙キャッシュ（`schemaorg-vocab.json`）。足場を残す理由（テストが配布先と同じ `.wikicommit/scripts/` の配置で実行する）は `tests/test_template_mirror_sync.py` の docstring にある。ドッグフーディングの実データ（`config.yml`・`entity/`・`source/`）は置かない — **ドッグフーディングはパイロット（`wikicommit/ai-driven-dev-wiki` 等）で行う**。したがってこのリポジトリで `/wikicommit-*` を名指しで呼んでも、`config.yml` が無いので各 Skill の前提確認で止まる（古いデータで答えることはない）。

### 3.3 `.wikicommit/config.yml` の構造

```yaml
wikicommit_version: "0.1.0"     # このリポジトリを最後に同期した WikiCommit の版。
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
                                  # .wikicommit/source-policy.md に書く（§3.4）。
                                  # 例: "社内エンジニア組織の技術ナレッジベース。個人のブログ的な話題は対象外。"

site_description: {}             # 読者に見せるこの Wiki の紹介文。言語コード → 1〜3 文の文字列。
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

`theme` は `/wikicommit-init` 実行時に対話的に設定する（空 Enter でスキップ可）。単体では何もしないフィールドで、`wikicommit-generate` のテーマ判定チェックポリシー（§4.3・`DesignDoc-pipeline.md` §6.1）が読み取って利用する。**役割は内容スコープに限る**（§3.4 参照）。さらに `theme` が答えるのは**関連性**（この Wiki の主題と関係があるか）に限られ、**許容性**（関係があっても書いてよいか）は `.wikicommit/entity-policy.md` が持つ（§3.5 参照）。同じ Pass 2c が両方を読み同じ `action: exclude` を出すが、軸が独立しているため一方が他方を代替しない — 主題のど真ん中にいる存命の人物は関連性が最大でもなお除外したいことがある。

#### `review:` ブロックは置かない

`config.yml` に `review:` ブロック（`review.auto_merge` / `review.chain_of_thought`）は無い。どちらも読む消費者が無く、マージ条件は `docs/DesignDoc-pipeline.md` §7 の「経路 A: 品質チェック全 blocking PASS」だけで、設定による分岐点はどこにも無い。マージを設定で止める機能は信頼ラダーに第 3 の状態を持ち込むため、必要になった時点で独立に設計する（「作らない」側で止める経路は `.wikicommit/entity-policy.md`。§3.5）。既存リポジトリの `config.yml` に残るキーは誰も読まないので書き換えない。

#### `wikicommit_version` — 最後に同期した版

- 版の source of truth は 2 箇所 — `.claude/skills/wikicommit-init/scripts/templates/scripts/_version.py`（`.wikicommit/scripts/_version.py` として展開され、**インストール先まで届く唯一の情報源**）と `.claude-plugin/plugin.json` の `version`。両者の一致は `tests/test_version_sync.py` が CI で強制する。`git tag` は版の担い手にしない。`pyproject.toml` の `version` とは無関係で、揃える規約は置かない
- 値の意味は**最後に同期した版**。初回 init が刻印し、`/wikicommit-update` が同期の完了時に `init.py --update-version` で書き換える。**書き換えはその行だけのテキストレベルで行い、YAML の round-trip はしない**（コメントアウトした記入例が落ちるため）
- 欠如は「この機能追加より前に作られ、まだ一度も update していない」ことを意味する。遡及付与はしない（最初の `/wikicommit-update` で刻印される）
- 差分の検知・配布物の更新・ページ再生成の起点であり、利用者への変更伝達手段は `CHANGELOG.md` である

#### 再 init で何が更新され何が守られるか

再 init の挙動は `_root_outputs.py` の `update` 列が宣言的に決め、`init.py` はそこからコピーのフラグを導く（`overwrite` → `always_overwrite=True`、`review` / `skip` → `always_skip_existing=True`。両方が渡されたら `always_skip_existing` を優先する）。

| `update` | 対象 | 再 init の挙動 |
|---|---|---|
| `overwrite` | `.wikicommit/scripts/`・`.wikicommit/review-rules.md`・`.wikicommit/schema-authoring.md`・`.wikicommit/guides/`・`quartz-plugins/`・`deploy.yml`・`review-issue-close-sync.yml`・`prebuild-symlinks.cjs`・`repair-plugin-builds.cjs`・`install-local-plugins.cjs` | `--no-overwrite` の有無に関わらず更新される |
| `review` | `config.yml`・`quartz.config.yaml`・`schema/`・`package.json`・`.lychee.toml`・`.markdownlint.json`・`.gitignore`・`report.md`・ポリシーファイル 2 つ | 既存ファイルには一切触れない |
| `skip` | `entity/`・`view/`・`source/`・`.claude/`・`quartz/`・`.gitmodules`・`package-lock.json`・`schemaorg-vocab.json`・`README.md`（無いときだけ作る） | 同上（かつ差分報告の対象外） |

- 線引きは所有権による — WikiCommit 自身の配布ペイロードは更新し、利用者が書いたもの（`config.yml`・`schema/`・ページ）は守る。`.wikicommit/scripts/` を丸ごと更新するので、`_version.py` だけが新しくスクリプトが古いという不整合は起きない
- **`review` と `skip` は init の挙動としては同一**で、違うのは `check_distribution_freshness.py` が差分を報告するかどうかだけである。ポリシーファイルが `review` なのは frontmatter のキーが上流で増えるため
- **孤児は残る**。`copy_tree` は削除しないので、上流でリネームされたファイルの旧名は `overwrite` のツリーでも残る。`check_distribution_freshness.py` が `ORPHAN:` として報告し、削除は人間が行う
- **`.wikicommit/schema/` は refresh されない**ため、型テンプレートだけを変えた版へ上げると版だけが先に進む（その後のページは旧テンプレートで作られても `generated_with: <新版>` を持つ）。差分は `check_distribution_freshness.py` がバイト比較で報告し、取り込むかどうかは人間が決める（人間の直接編集を許す唯一の領域であるため）

#### `theme` と `site_description`

- **`theme` は LLM 向けの内部フィールドであり、読者向けの表示には使わない**。読むのは `wikicommit-generate` Pass 2c と `wikicommit-collect` に限られる。読者向けのサイト説明が要るなら `theme` を流用せず `site_description` に書く（`docs/DesignDoc-publish.md` §8.8）
- `site_description` は**言語コード → 1〜3 文の文字列**のマッピングで、公開サイトのトップページで各言語のリンクの直下に 1 行ずつ描画される。`theme` とは宛先が違うので**同期させる規約は置かず**、両方が空でも動く
- **人間が書く**。`/wikicommit-init` は聞かず、テンプレートはコメントアウトした記入例だけを置いて**キー自体は配らない**。LLM に翻訳させる経路も作らない
- 欠如・壊れた値（マッピングでない・値が文字列でない）は落として無効扱いにし、出力は従来どおりになる。値の内部の改行・連続空白は単一の空白に潰す（言語ごとの箇条書き 1 行に埋め込まれるため）

#### 型提案の 3 経路と書き込み手順

Schema.org 標準型を足す提案は 3 経路にあり、**判定の厳しさは証拠の強さで分かれる**:

| 経路 | 証拠 | 判定 |
|---|---|---|
| `wikicommit-init` の obvious-type judgment（`theme` が非空のとき） | `theme` の 1 文のみ・ソース登録前 | 最も厳格 — `theme` 文から自信を持って断定できる型だけを提案する（例: 「AI 駆動開発ツールのナレッジベース」なら `schema:SoftwareApplication`） |
| `wikicommit-collect` の Type Proposal | 候補タイトル・検索要約 | 候補提示が元々対話的 |
| `wikicommit-generate` Pass 2b | ソース文書全文 | 主経路・最高精度（§5.4。候補はすべて保留にし、繰り返しの後にまとめて尋ねる。非対話実行では尋ねない） |

- 3 経路とも型の追加には人間の回答を要し、`.wikicommit/schema/` に既にある型は提案しない（同一のスキップ判定なので互いに排他的な設計は要らない）。init の提案は Pass 2b と同じく `check_schema_org_type.py` による検証・Enter ベース承認・追加のみ可の書き込み例外を使う。漏れたケースの安全網は `wikicommit-schema-propose`（事後検出）
- **分かれているのは判定だけで、書き込み手順は 1 本である**。`.wikicommit/schema-authoring.md`（`update: overwrite`）が手順を持ち、各経路はそれを読んで自分の `provenance` を渡す。**譲れない 3 点**（property を `check_schema_org_type.py` で検証する・`granularity` に `Boundary —` を 1 本入れる・`provenance` は自分の値を刻む）は各サイトに 1 行ずつ残す。ファイルが無い場合は**その候補だけを却下して報告し、実行は止めない**（`docs/DesignDoc-skills.md` §11.5）

#### `targets` は手動で設定してよい

`targets` を設定すれば `/wikicommit-translate` がそのとおりに翻訳ページを生成する。翻訳がまだ無い言語については、`convert_wikilinks.py` の `existing_lang_targets()` が実ページの無い `target` をルート `content/index.md` の言語選択リンクから除外するので、デッドリンクは生じない。

### 3.4 `.wikicommit/source-policy.md`（ソース選定方針）

「**どんなソースを取り込むか**」を書くファイル。`config.yml` の `theme`（「何についての Wiki か」＝ 取り込み済みのソースからどのエンティティをページ化するか）とは別の問いに答える。

ソース方針を `theme` に書かない。`theme` を読む主体のうち、ソース方針が効くのは任意経路の `wikicommit-collect` だけであり、主経路の `wikicommit-generate` Pass 2c はエンティティ単位の判定なので、ソース方針はそこではノイズとして混入するだけになる。主経路の `/wikicommit-generate <path|url>` でソース方針を読むのは、このファイルを読む Step 0 である。

#### フォーマット

`.wikicommit/schema/*.md` と同じ形式（機械可読なフロントマター + 散文の指示）を採る。スキーマファイルの設計思想（§5.1 —「LLM 指示書と品質ゲート仕様書を兼ねる」・ディレクトリに置くだけで有効になる Convention over Configuration）がそのまま当てはまるため。`config.yml` のフィールドにしないのは、中身の大半が散文であり、YAML の値として持つには収まりが悪いからである。

```markdown
---
wikicommit:
  exclude_domains: []   # このWikiが取り込まないと決めたドメイン
  rejected: []          # 検討して却下したソース（url / reason / date〈任意〉）
  index_only: []        # 読むが登録しないドメイン・ページ（下記）
---

一次資料（行政の公式サイト・オープンデータ・査読論文）を優先する。
個人ブログ・商業的な広告・特定店舗の宣伝は取り込まない。
対象全体の構造を述べる資料を最初に1件取り込み、以降はそこへの肉付けとして進める。
```

**フロントマターのキーに新しいスクリプトは要らない**。`exclude_domains` は既存の `check_extraction_quality.py check-domain` が読み、残りは Skill の指示ファイルとして読まれる。`wikicommit-init` が空のテンプレート（本文はコメントアウトした記入例のみ）を配布し、再実行しても上書きしない（`update: review`）。**ファイルが無い既存リポジトリは従来どおり動く**。

#### 記入例と利用者の方針を機械が区別する（`read_policy.py`）

本文が空、またはテンプレートの記入例のままなら、散文方針は無いものとして扱う（空の `theme` がエンティティ判定を無効にするのと同じ）。**この判定は LLM にさせず、`read_policy.py`（`docs/DesignDoc-ScriptSpec.md`）が決定論的に行う** — 本文から記入例と HTML コメントを落として返し、3 つの読み手（`wikicommit-generate` Step 0 / 処理フロー冒頭、`wikicommit-collect` Step 2.5）はファイルを直接読む代わりにこれを呼ぶ。`entity-policy.md`（§3.5）も同じスクリプトで読む。

- **フロントマターには触れない** — `exclude_domains` / `index_only` / `rejected` / `exclude_living_persons` はそれぞれの読み手が独立に読む
- **判定規則は「HTML コメントは方針ではない」であり、どの版が配布したかに依存しない**。したがって既存リポジトリへの移行は要らない
- `<!-- wikicommit:example ... -->` のマーカーは「これは WikiCommit のもの」を grep 可能にし、本文に内容があったのにコメント除去で全部消えた場合を「空」ではなく「全部コメントの中にある」と報告するために使う（記入例を `<!--` を消さずに書き換えた場合に、方針が黙って無視されないため）
- フロントマターに `template_untouched: true` のようなフラグは置かない — 消し忘れると自分で書いた方針が黙って無効になる
- 判定を誤ると、記入例はすべて除外を促す内容なので、「書かれるはずだったものが書かれない」向きにだけ、出力上の区別なく効く。これが LLM に判定させない理由である

#### 消費者

| キー / 部位 | 読む主体 | 何をするか |
|---|---|---|
| 本文（散文） | `wikicommit-generate` Step 0 | 登録前に、引数のソースが方針に明らかに反するなら**どの行と衝突するかを述べて確認を求める**（黙って登録しない・独断で拒否もしない） |
| 本文（散文） | `wikicommit-collect` Step 2.5 → 4/5/6 | 候補の常設フィルタ |
| `exclude_domains` | `check_extraction_quality.py check-domain` | 組み込みリストとの**和集合**（下記） |
| `exclude_domains` | `wikicommit-generate` Step 0 | 引数のホストが該当する場合、登録前に確認を求める（下記） |
| `rejected` | `wikicommit-collect` Step 2.5 → 5 | 該当 URL の候補を落とす |
| `rejected` | `wikicommit-generate` Step 0 | 引数の URL が該当する場合、その `reason` を引用して確認を求める |
| `index_only` | `wikicommit-collect` Step 5 / 5.5 | 該当するページ自身は候補にせず、リンクの列挙から一次資料を掘る。ページのエントリは自分から見に行く（下記。照合は `match_index_only.py`） |
| `index_only` | `wikicommit-generate` Step 0 | 引数の URL が該当する場合、登録前に確認を求める（照合は `match_index_only.py`） |

#### `exclude_domains` と `KNOWN_JS_SHELL_DOMAINS` の合成は和集合（完了条件）

スクリプト側の `KNOWN_JS_SHELL_DOMAINS`は「静的フェッチで空シェルを返すことが確認済み」という**全リポジトリ共通の事実**を持つ。一方 `exclude_domains` は**そのリポジトリの決定**を持つ。両者を和集合とし、**リポジトリ側から組み込みリストを上書き（取得可能に戻す）ことはできない** — 設定で戻しても実際に取得できるようにはならないため。

ファイルが無い・読めない・フロントマターが壊れている・値がリストでない、のいずれも「追加ドメインなし」として扱う。ソース選定方針が、全 URL 取得の手前で走る抽出ガードを道連れに壊せてはならない。ただし**無言で fail-open してはならない** — `wikicommit-collect` がこのファイルの `rejected:` に追記する以上、追記ミス 1 回で `exclude_domains` 全体が無言で無効化されうるため、フロントマターのパースに失敗した場合は stderr に `WARNING:` を出す（stdout の `BLOCKED:`/`OK:` 契約は変えない）。

各エントリは `_domain_of()` と同じ形（スキーム・パス・ポート・先頭 `www.` を除去し小文字化）に正規化してから**完全一致**で比較する。正規化は、人間が同じフロントマター内の `rejected:` の `url:` に倣って `https://example.com/` と書いた場合に一致しない（＝ファイル上は除外されているのに取得され続ける）ことを防ぐためのもので、サブドメインまでは覆わない（`example.com` は `blog.example.com` に一致しない）— 組み込みリストが `music.youtube.com` を個別に持つのと同じく、意図するホストを列挙する。

**`exclude_domains` の一致を Pass 1 だけに任せない**。Pass 1 のブロックは `status: failed` + `## Failure Reason` を残し、さらに `wikicommit-merge` Step 9 が `wikicommit-generation-failure` の追跡 Issue を立てる — 静的取得が本当にできないドメインにはそれが正しい記録だが、「この Wiki が要らないと決めた」ドメインには誤った記録になる（要らないソースの管理ファイルが残り、直せという Issue まで立つ）。そのため `wikicommit-generate` Step 0 は、引数のホストが `exclude_domains` に該当する場合、散文方針との衝突と同じ扱いで**登録前に**確認を求める。

#### `rejected` は誰が書くか（完了条件）

**`wikicommit-collect` が、人間が却下した直後に追記する**（Step 8）。対象は `[Web]` 候補のうち人間が明示的に却下したものに限り、理由を 1 行聞いてから書く。理由を言わない場合は書かない — 理由のないエントリは、後から読んだ人がまだ有効か判断できず、無いより悪い。`[Local]` 候補は将来の検索で再浮上しないため対象外。**追記のみ可**（既存エントリの編集・削除、他キー・本文への書き込みは不可）で、これは `wikicommit-collect` Step 7 / `wikicommit-generate` Pass 2b が `.wikicommit/schema/` に対して持つ narrow exception と同じ形である。人間が手で書くこともできる。

**Pass 2b が却下した型候補をどこにも永続化しない設計（§5.4）とは対象が異なる**ため衝突しない:

| | Pass 2b が永続化しないもの | ここで残すもの |
|---|---|---|
| 対象 | 却下された**型候補** | 却下された**ソース URL** |
| 再現性 | 次回同じソースを読めば同じ判断が再現できる | 「これは要らない」という人間の判断は、ソースを読み直しても再現しない |
| 残す弊害 | 「後で拾える」という誤った期待を生み、実際には拾われず情報が消える | 無い（再提案されないだけ） |
| 必要なもの | 再現 | **記憶** |

`rejected` はリポジトリ固有の「以前除外した」記憶を置く場所である。

#### `index_only` — 読むが登録しないドメイン・ページ

`/wikicommit-collect` が、このエントリに該当するページを**リンクの列挙から一次資料を掘るためだけに読み、そのページ自身は候補にしない**。コマンド引数 `--index <url>` はその場限りの同じ指定である。

**境界がこの位置にある理由**が本質である。索引ページを読んで「**何を書くか**」を決めるのは危険で、表現・構成が生成物に漏れうるうえ、そのページは `sources:` に無いため **Pass 4 の出典照合が漏れを検出できず、帰属表示も付かない** — 結果として「無帰属の二次的著作物」になり、ソースとして明記して表示を付けるより**法的に悪い**。一方、索引ページを読んで「**どの URL を取りに行くか**」を決めるのは安全である。参照文献リストは事実の列挙であり、そこから一次資料を自分で取得して書けば ShareAlike 義務は発生しない。したがって**リンクの列挙部分だけを読み、散文部分は読まない** — 記事を要約しない、節見出しや各項目の一言説明を候補の説明に持ち込まない。**キュレーション（どのリンクを載せたか）を採用することは許容する** — awesome リストのように選別そのものが索引の価値である場合があるためで、使うのはリンクの選択であって記述ではない。既存の research guidance（「〜を**ソースとして**優先せよ」）ではこの「読むが登録しない」を表現できないので、百科事典を名指しする guidance はどちらの意味かを確かめてから動く。

**エントリの形が意味を決める**（キーは 1 つ）:

| エントリ | 範囲 | 検索結果に出てきたとき（受動） | 自分から見に行く（能動） |
|---|---|---|---|
| パスが無い（ドメイン） | そのホスト全体 | 採掘へ回す | しない |
| パスがある（ページ） | そのページだけ | 採掘へ回す | する（guidance に関係する節があるときだけ） |

分かれ目は**取得先の URL が 1 つに決まるかどうか**である。ワイルドカードは入れない。別キー（`index_pages:` 等）も、`index:` + `rejected:` の組み合わせも採らない（後者は書き忘れると索引ページ自体が候補になる）。

- **照合は `match_index_only.py`**（`docs/DesignDoc-ScriptSpec.md`）が一手に持つ。collect Step 5 と generate Step 0 の 2 か所の散文で照合しない。正規化はドメインがホストの完全一致、ページはスキーム・先頭 `www.`・フラグメント・末尾スラッシュを落としパスをパーセントデコードして比較する。**クエリは保持して完全一致で比べる**（`index.php?title=X` のようにクエリがページを名指すサイトで、落とすと 1 ページが全ページに広がる）
- **常設の索引を毎回丸ごと掘らない**。collect Step 5.5 はページのエントリについて見出しの構造だけを見て guidance に関係する節を選び、無ければ掘らずにその旨を 1 行報告する。**索引由来の候補は実行全体で 20 件まで**とし、切ったことを件数付きで報告する（索引ごとではなく実行全体の上限。どれを残すかは並び順ではなく関連性で決める）
- **collect はページのエントリを追記しない**（索引の選定は人間が明示的に行う）。取得キャッシュ（`.wikicommit/.cache/collect-index/`）は毎回取り直す

#### `/wikicommit-generate` Step 0 も読む

`/wikicommit-generate <url>` の引数が `index_only` に該当する場合、Step 0 は `exclude_domains` / `rejected` と同じ形で該当を名指しし、**登録前に確認を求める**。確認のメッセージには `/wikicommit-collect --index <url>` という後続経路をコマンド名ごと添える（`--index` は collect の引数であり generate には無い）。

| | Step 0 の確認 | Pass 1 のガード |
|---|---|---|
| `exclude_domains` | あり | あり（`check-domain`） |
| `rejected` | あり | なし |
| `index_only` | あり | なし |

- **塞がない。ここが `exclude_domains` との違いである** — 一次資料が存在しない対象のために百科事典記事を明示登録する運用は残す（下の「推奨する組み合わせ」(3)）。求めているのは、それが偶然ではなく判断であることだけである
- **`check-domain` に和集合しない**。あれはブロックであり、和集合にすると `status: failed` の管理ファイルと追跡 Issue が残るうえ、登録してよい場合が実在する `index_only` を `exclude_domains` より強くブロックすることになる。読まなければ `index_only` のドメインは素通りして取得されページが生成されるので、Step 0 が唯一の確認点である

#### 推奨する組み合わせ

(1) 骨格は一次資料から取る、(2) 百科事典は索引として使う（`index_only`）、(3) 一次資料が存在しない対象だけ百科事典記事をソースとして明示登録する。3 案は排他ではない。ネット上に一次資料が無い対象（神社の由緒・地域の文化的概念など）は必ず残るため、**「百科事典を一律禁止」という運用不能なルールにはしない** — ShareAlike 義務を負うページを意図的に少数に絞ることが目的である。この方針は `source-policy.md` テンプレートの本文コメントと README に書いてある。

「骨格ソース先行」は検証中の仮説であり、それを運用中に確かめられるよう `check_orphans.py` の `ORPHAN:` 行は出自（そのページの `sources`）を添える。

#### コピーレフト系ソースの警告

`add_source.py` が既知ドメイン対応表（`KNOWN_SOURCE_LICENSES`）または `--license` から得たライセンスがコピーレフト系（`is_share_alike()`）なら、登録時のメッセージに一度だけその旨を添える。あわせて `wikicommit-generate` の Completion Notice が、`sources` が**全件**コピーレフトのページを列挙する（義務が付きうるのはソースではなくページであるため）。

- 照合は `SHARE_ALIKE_LICENSE_PREFIXES` との大文字小文字を無視した**前方一致**で、現在の接頭辞は `cc-by-sa`/`cc-sa`/`gfdl`/`odbl`/`cc-by-nc-sa`/`gpl`/`agpl`/`lgpl`/`mpl`/`epl`/`cddl`/`osl`/`sspl`/`eupl`/`cpl`/`ms-rl`
- **弱いコピーレフト（LGPL / MPL / EPL / CDDL）も一律で入れる** — リンク境界もファイル境界も散文には対応物が無い
- **末尾にハイフンを付けない** — 値は自由記述であり、`GPLv3` や素の `GPL` は普通の綴りである
- **足しすぎより足りない方を恐れる**。足した接頭辞はいずれも実際にコピーレフトなので、余計に出ても注意書きが 1 行増えるだけだが、足りなければ利用者が義務に気づかないまま公開する（取り返しのつかない側）
- 表に足すのは**本文の条項で確認したものだけ**である（評判では足さない。「よく使われるか」も基準にしない）。`ms-rl` は族単位の `ms-` にしない（`MS-PL` は permissive）
- **CeCILL は足さない（既知の沈黙）**。`CeCILL` / `CeCILL-C` はコピーレフトだが `CeCILL-B` は permissive で、前方一致では両立しない。テストがこの沈黙を固定している。`mpl` が `mplus`（permissive なフォントライセンス）に一致する既知の誤検知は、誤りの向きが安全側なので直さない
- 表が表すのは**ライセンスの性質**であって、そのページが二次的著作物に当たるかの判断ではない（WikiCommit はその問いに答えない。`docs/DesignDoc-publish.md` §8.10）。したがって注意書きは「負いうる。確認すること」と書き、断定しない
- `KNOWN_SOURCE_LICENSES` に `github.com` のような任意のライセンスが混在するドメインは足さない（自サイトのコンテンツ全体に明示しているライセンスのみを持つ表である）
- 識別子名（`is_share_alike()`）と `--license-for-url` の `(share-alike)` マーカーは、`wikicommit-collect` の出力の契約なので据え置く
- 既に登録済みのソースには遡って警告しない（`add_source.py` は新規作成時にしか `license` を書かない）。Completion Notice の列挙は次にそのページを生成したときに効く

#### 現時点でキーを置かないもの

`license_map`（ドメイン→ライセンス対応表）は、**このファイルが行き先である**ことを決めたうえで、**その消費者と同時に追加する**。空のキーだけを先に配ると「受け皿だけ存在して常に空のまま残る」ためである。`add_source.py` の `KNOWN_SOURCE_LICENSES` は当面そのまま据え置く。

#### `theme` の narrow（完了条件）

`theme` の役割は内容スコープに限る。`config.yml` テンプレートのコメントと `wikicommit-init` の対話プロンプトは「主題を書く。どのソースを使うかは書かない」と明示する。既存リポジトリの `theme` に混在しているソース方針は自動移行しない。

### 3.5 `.wikicommit/entity-policy.md`（エンティティ許容方針）

「**そのエンティティについて書いてよいか**」を書くファイル。`config.yml` の `theme`（「この Wiki の主題と関係があるか」）とは別の問いに答える。`.wikicommit/source-policy.md` : `source/` :: `.wikicommit/entity-policy.md` : `entity/` という対応になる。

**止める場所はマージではなく生成である**。「ページを作らない」は既存の機構（Pass 2c の `action: exclude`）がそのまま使え、`exclude_reason` の enum（`theme_mismatch` / `privacy` / `copyright`）に収まる。マージを止める形（型別の `auto_merge: false` 等）は採らない — 信頼ラダーは `pending` でも main にマージして公開しバナーを出す 2 値設計であり（`docs/DesignDoc-publish.md` §8.4）、「公開前に人間レビューを挟む」は第 3 の状態の導入になる（§3.3「置かないフィールド」）。

#### なぜ新しいファイルが要るのか

**型テンプレートの `granularity` には書けない**。「存命の個人はページ化しない」は型をまたぐ — 人物は `Person` だけでなく、実体が個人〜数名の `Organization`・`Event` の主催者・`ShortStory` の `character` にも現れる。ところが `.wikicommit/schema/` は LLM から「追加のみ可・既存ファイルの編集不可」であり、**既存の型ファイルに後から書き足す経路がどの Skill にも存在しない**（§5.2「`granularity` の境界ルールは片側にしか書けない」が既に踏んだ壁と同一）。加えて Pass 2b が実行時に新しい型を足すため、将来足される型には書きようがない。横断ルールを `granularity` で維持するのは原理的に不可能である。

**`theme` に混ぜてもいけない**。両者は同じ Pass 2c に読まれ同じ `action: exclude` を出すため、一見「1 つの問いを 2 ファイルに割る」という §3.4 の逆に見えるが、実際には別軸である:

| | 問い | 例 |
|---|---|---|
| `theme` | **関連性** — この Wiki の主題と関係があるか | さいたまの区の記事から人物を除外 |
| `entity-policy.md` | **許容性** — 関係があっても、書いてよいか | 主題の中心にいる存命の人物 |

主題のど真ん中にいる存命の人物は関連性が最大でもなお除外したい。2 つは独立に効くため、`theme` に混ぜれば別軸の方針が丸ごとノイズとして混入する（§3.4 がソース方針について避けたのと同じ形）。`exclude_reason` の enum が `theme_mismatch` / `privacy` / `copyright` と分かれているのはこの軸の分離のためである。

**`theme` を新ファイルへ移すことはしない**。1 行のスカラーで YAML に収まり `wikicommit-init` の対話で設定される値であり、`source-policy.md` を独立ファイルにした理由（「中身の大半が散文であり YAML の値として持つには収まりが悪い」）が当てはまらない。両方に「こちらは関連性・こちらは許容性」と明記する形で足りる。

#### フォーマット

`.wikicommit/source-policy.md` と同じ「機械可読フロントマター + 散文」を採る。

```markdown
---
wikicommit:
  exclude_living_persons: false   # 存命の個人についてページを作らない
---

（コメントアウトした記入例。散文本文が実質の方針）
```

**キーは `exclude_living_persons` の 1 つだけにする**（消費者と同時にキーを足し、受け皿だけ先に配らない）。とくに名指しの例外リスト（`living_person_exceptions: []` 等）を**構造化キーとして持たせない**: `source-policy.md` のキーはいずれも正規化後の完全一致（ホスト・URL）という決定論的な照合を持つのに対し、人物の例外はエンティティ名での照合になり曖昧一致に頼らざるを得ない。フロントマターは決定論的な値・散文は LLM が読む判断材料、という役割分担を崩さないため、例外は散文側に書く。

**「非公人」を 2 つ目のスイッチにもしない**。実際にリスクを分けているのは存命性ではなく公人性の軸だが、「存命か」も「公人か」も等しく LLM 判断であり、スイッチを 2 つ並べると組み合わせの意味を説明する必要が出る。スイッチは 1 つに保ち、公人の例外と故人の非公人は散文で書く。

散文本文は、**記入例のままなら方針は無いものとして扱う — その判定は `read_policy.py` が行う**（§3.4「記入例と利用者の方針を機械が区別する」）。**ファイルが無い既存リポジトリは従来どおり動く**。フロントマターが壊れている場合は配布時の既定（スイッチ off・散文なし）として扱うが、**ファイルが在るのにパースできなかった場合は無言で fail-open してはならない** — 手編集 1 回のミスで方針全体が黙って無効化されうるうえ、こちらには組み込みリストのような後ろ盾が無い。`wikicommit-generate` はその場で `WARNING:` を出し、Completion Notice にも再掲する。**ファイルが無い場合は警告しない**（全実行に無意味な警告が出るため）。

#### `exclude_living_persons` は init が 1 問だけ聞く

`/wikicommit-init` はこのスイッチだけを聞き（`theme` と同じく Skill が聞いて `init.py` にフラグで渡す）、空 Enter は `false`。非対話実行では聞かず `NOTE:` を出す。散文は従来どおり init 後に書く場所として名前を挙げるに留める。`--update-theme` 相当の上書き経路は作らない（`entity-policy.md` は `update: review` でファイル全体が利用者の編集対象であり、1 行の変更は手で足りる）。

**聞く理由**: 散文は実行のたびに読み直されるので後から書けば次の実行から効くが、スイッチは既定値を持ち無言で作用し、**どちらの向きにも既に起きたことには届かない**:

| 既定のまま生成したあとで設定を変えると | 何が起きるか |
|---|---|
| `false` で生成 → ページが出来ている | `--regenerate` は Pass 2c を実行しない（`docs/DesignDoc-pipeline.md` §6.1）ためページは残る。`/wikicommit-remove` で下ろす |
| `true` で生成 → 除外されている | 同じソースを再登録しても `HASH_MATCH:` で止まる。`/wikicommit-reconcile` で戻す |

両方とも取り返しがつかないので「安全な既定を選ぶ」が成立せず、利用者が実際に決めた値を使うしかない。

**質問文は「誰が対象外か」を必ず併記する** — スイッチが切っているのは `living` だが、実際にリスクを分けているのは公人性であり、書かない質問文は歴史上の人物まで巻き込む過剰除外を誘発する。

**既定を `true` にしない理由**（次に同じ提案が出たときに再検討し直さずに済むよう残す）:

1. **スイッチは代理指標であり、両方向に外れる** — 故人の非公人は覆えず、存命の公人は覆いすぎる。既定 on にすると覆いすぎだけが全 Wiki に広がる
2. **チームの社内ドキュメント（`dev/PRD.md` §3 のセグメント 2）を黙って壊す** — 社内 Wiki で同僚のページを持つことは正当な主用途である
3. **除外理由が実名付きで公開サイトに出る経路があれば逆効果になる**（除外の記録は `## Generation Notes` に書き、公開される `## Summary` には書かない。§4.3）
4. **既定 off でも無防備ではない** — `Person.md` の `granularity` に常時有効の記述範囲制限（存命の個人は本人が公表したものに限る）がある

**常設の検出器は置かない**。「`exclude_living_persons: true` かつ `Person/` にページが実在する」は判定できるが、大半のページの正しい行動は「残す」なので、正しく対処しても所見が消えず常時点灯する。変えたのは本人であり、機械が言える新情報はスイッチが on であることだけである。

#### 消費者は Pass 2c のみ

| 部位 | 読む主体 | 何をするか |
|---|---|---|
| `exclude_living_persons` | `wikicommit-generate` Pass 2c | true なら、ソースが存命と示す個人のエンティティを `action: exclude` / `exclude_reason: privacy` にする |
| 本文（散文） | `wikicommit-generate` Pass 2c | 散文が名指しするカテゴリを同じ形で除外する。人物に限らない（係争中の事案・自組織の未公開情報等） |

`theme` が空でもこの判定は行う — 2 つは独立した軸であり、`/wikicommit-init` の既定が空の `theme` である以上、`theme` が空なら `exclude` 自体を禁じるという読み方をすると、entity-policy を設定した Wiki で許容性の判定が丸ごと黙って無効化される（`docs/DesignDoc-skills.md` §11.6 の `exclude_reason` 節・`wikicommit-generate` Pass 2c の該当箇所）。

`theme` と同じく人間確認なしで自動適用され、管理ファイルの `## Generation Notes` と Completion Notice に記録される（§4.3 参照）。**両方の理由が同じエンティティに当てはまる場合は `privacy` を記録する** — Wiki の主題が変わっても残る側の理由であるため。

**`wikicommit-synthesize` と `wikicommit-collect` は対象外とする**。前者は既存ページから合成するためポリシーを迂回しうるが、まだ読まない（器と主経路を先に確定させる）。後者はソース選定の話であり、必要なら人間が `source-policy.md` に書けば済むため器を増やさない。

#### 散文本文が担う範囲（配布テンプレートの記入例）

**除外カテゴリを増やすのに新しいキーは要らない**。散文本文は Pass 2c が自由記述として読むため、`exclude_living_persons` 以外の判断はすべてここに書ける。配布テンプレートのコメントアウトした記入例に挙げる価値があるのは以下の 4 つで、いずれも**存命スイッチでは覆えない**か、覆えても理由が別である:

| カテゴリ | 根拠 | 存命スイッチとの関係 |
|---|---|---|
| **非公人（public figure でない実在の個人）** | 行政文書には審議会委員名簿・事業者名・陳情者名が普通に入る | **覆えない**。故人の非公人（地域史料に出てくる一般住民）が漏れる一方、存命の公人は覆いすぎる |
| **実在の未成年者** | 学校・地域行事を扱う Wiki が踏む | 存命なら覆えるが、スイッチ off の Wiki では丸ごと漏れる |
| **係争中の事案・進行中の事件** | `Event` 型。事実が流動的で、誤りが名誉毀損になりうる。`expires_at`は「古くなる」を扱うが「今書くべきでない」は扱わない | 覆えない（`Person` 型ではない） |
| **自組織の未公開情報** | `dev/PRD.md` §3 のセグメント 2（チームの社内ドキュメント）が最初に必要とするもの | 覆えない |

**あわせて「除外しすぎない」ことも記入例に書く**。これは仮定の話ではない — `wikicommit/saitama-city-wiki` は `theme` による除外だけで `Person` 型が 0 ページになり、太田道灌（1486 年没）・井沢弥惣兵衛（1738 年没）・児玉南柯（1830 年没）という**書いて何の問題もない歴史上の人物**まで巻き込んでいた。落ちた 4 人のうち存命の公人は 1 人だけであり、パイロット自身がこの結果を「よしとするか検討の余地がある」と記録している。カテゴリを足すほどこの方向に効くため、記入例には「公人・歴史上の人物を巻き込みすぎないこと」を必ず併記する。

#### entity-policy に入れないもの

| カテゴリ | 既にある器 |
|---|---|
| 商業的な宣伝・個人ブログ | `.wikicommit/source-policy.md`（テンプレートの記入例に既にある） |
| 著作権 | ほぼソース側で解決する。`wikicommit-collect` は候補に ⚠️ を出し、`sources[].license` とコピーレフト系ソースの警告（§3.4）がある |
| 医療・法律・金融の「助言」に読める記述 | エンティティの存否ではなく記述範囲。`granularity` と `expires_at` |

**`exclude_reason: copyright` は予約のまま据え置く**。ソース側で保護期間・ライセンスを確認して取り込む設計になっている以上、エンティティ単位で「著作権を理由にページを作らない」と判断する場面がほとんど残らない。消費者を得ないまま `theme_mismatch` / `privacy` の隣に並べると、「受け皿だけ存在して常に空のまま残る」形になる。

#### 既存ページには遡及しない

`--regenerate` は Pass 2c を実行しない（`docs/DesignDoc-pipeline.md` §6.1）ため、既に存在するページはポリシーを書いても消えない。生成側は何も削除せず、ページを削除する経路は `/wikicommit-remove`（`removed_reason: gdpr` 等）だけである。**プライバシーが理由のポリシーで「書いたのに既存ページが残る」は誤解を招きやすい**ため、テンプレートの散文コメントと Completion Notice の両方に明示する。

- **スイッチや散文を変えた結果を既存ソースへ届ける経路は `/wikicommit-reconcile`** である。対象ソースの管理ファイルを `status: pending` に戻し、次の `/wikicommit-generate` が Pass 2c をもう一度通す。**off に戻した場合にこそ要る** — `status: excluded` のソースは他のどのコマンドでも到達できない（`<url>` は `HASH_MATCH`、`<path>` は `SKIP`、引数なしは収集対象外で、3 経路とも出力は成功系）
- **どのページが対象外になったかは機械が名指しする**: Pass 2c は `action: exclude` のエントリにも `existing_path` を解決し、Completion Notice と `## Generation Notes` の両方がそのパスを添える。報告は断定しない（「このページは在り、今回の実行は作りも更新もしなかった」まで — 複数ソースに支えられたページの 1 件が除外されただけ、は普通に起こる）。自動削除もしない（`/wikicommit-remove` を指すのは `privacy` グループのみ。`docs/DesignDoc-skills.md` §11.6）

**手順書は `.wikicommit/guides/applying-entity-policy-to-existing-pages.md`** にある（`/wikicommit-reconcile --all` → `/wikicommit-generate` の 1 本と、それが済ませないもの）。ガイド棚に置くのは、ポリシーファイルが `update: review` かつ `compare: frontmatter_keys` のため本文の変更が既存リポジトリに届かない一方、ガイドは `update: overwrite` で届くためである。

#### 配布と取り込み

- `_root_outputs.py` に 1 行で載り、init の配布・`git add` 案内・再実行での保護（`update: review`）が揃う（`source-policy.md` と同じ）
- `wikicommit-merge` Step 2 / Step 5 に取り込む。人間が手編集した内容がコミットされないと意味がないため（`source-policy.md` が専用の pathspec を持つのと同じ理由）。`policy_files` 一覧（実行記録）が 2 ファイルを 1 つの一覧で扱う — ステージの仕方が同一であり、下流で区別する必要が無いため。`source-policy.md` と同様、この `.md` は Wiki ページではないため `changed_md` 一覧に入れてはならない（`validate_frontmatter.py` 等が落ちる）

---

## 4. データ設計

### 4.1 Wiki ページのフロントマター

フロントマターは **共通フィールド**（トップレベルに平置き）と **型固有プロパティ**（`properties:` にネスト）の 2 層構造。前者はページ解決に必須の構造的フィールド・WikiCommit 独自のブックキーピング情報・型に依存せず全ページ共通の識別子フィールドで、Schema.org 語彙に対する機械検証の対象外。後者は Schema.org 型固有のプロパティで、`validate_frontmatter.py` が `type:` の指す型（祖先型を含む）の `domainIncludes` に対して機械検証する（§5.2・`docs/DesignDoc-ScriptSpec.md` 参照）。

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
reviewed_by: "octocat"              # 任意: レビュー追跡 Issue を Close した人の GitHub login。
                                    # review-issue-close-sync.yml が review_status と同じコミットで書く

# ── LLM 生成メタデータ（wikicommit-generate が設定・任意）────────────
generated_at: "2026-06-17"          # 任意: ページ生成日（YYYY-MM-DD）。review_status バナーで表示
generated_by: "claude-sonnet-4-6"   # 任意: 生成に使用した LLM モデル ID。review_status バナーで表示
generated_with: "0.1.0"             # 任意: このページを生成した WikiCommit 自身の版

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

`properties:` に何を入れるか／入れないか: `tags`/`wikidata`/`sameAs`/`aliases` は語彙としては Schema.org 寄りだが、`wikicommit-jsonld` プラグインが型に関わらず一律で読む「WikiCommit 全ページ共通の識別子フィールド」であり、型ごとに変わる `properties:` 側とは性質が異なるためトップレベルに残す。翻訳ページの `translated_from`/`source_commit`/`translated_at`/`translated_by`/`translated_with`/`translator_notes`、合成ページの `derived_from`、削除ページの `status`/`removed_at`/`removed_reason`/`merged_into` も同じ理由でトップレベルに残す。`properties:` に書けるのは、情報源が単一の事実として明示している、短く構造化された値（日付・固有名詞・URL・他エンティティへの参照）に限る。複数文にまたがる説明・文脈・因果関係・複数事実の統合が必要な内容は、対応する property 名が Schema.org 上に存在していても本文に書く（`properties.description` 自体も 2〜3 文の要約に収め、詳細な経緯は本文見出しに譲る。`.claude/skills/wikicommit-generate/SKILL.md` Pass 3 参照）。

**ソースが自分で宣言しているリストに当たるキーは、その宣言を写す**（例: ScholarlyArticle の `keywords` ＝ 論文の Keywords 節〈`Index Terms`・`Key words`・`CCS Concepts` を含む〉）。宣言の全項目を同じ順・同じ表記で書き、生成側が語を選び直したり足したりしない。宣言が無ければキーごと省く。項目はソースの言語のまま写す（ページ本文は `primary_lang` で書くが、論文名と同じく訳さない）。`action: update`（`--regenerate` を含む）でも「このソースが触れていないキーは既存の値を残す」規則の対象外で、ページの全ソースから作り直し、どれも宣言していなければ既存の値を消す（残すと除きたい主題語がそのまま残り、Pass 4 で落ちる）。内容から選んだ主題語は `tags:` に書く（JSON-LD の `keywords` は `tags` から作られ、`properties.keywords` は公開ページで書誌情報と並んで表示されるだけなので、読み手はそこに書かれた語を論文自身のものと受け取る）。arXiv の分野分類のようにサイトが付けた分類は宣言ではない。リスト値の欄は「内容から代表的な語を選ぶ」作業として受け取られやすく、上の一般規則だけでは止まらなかったため、型に依存しない形で `references/pass3-generate.md` の「`properties:` vs. body placement」の直後に書き、型テンプレート（`ScholarlyArticle.md` の `granularity`）にも 1 行置く（§5.2「型間の優先関係は `granularity` に書く」末尾の対照と同じく、型テンプレートだけでは従われない）。Pass 4 も照合する — 宣言に無い項目・宣言の無いソースに対する `keywords` は `HALLUCINATION`、宣言の項目を落としたことは欠陥にしない（`review-rules.md` Part 2 の 2）。

**ページ本文に H1 を置かない**: Wiki ページの本文（frontmatter 以降）は段落または `##` 見出しから始め、`# <タイトル>` という H1 行を置かない。タイトルは frontmatter の `title` が持ち、Quartz の既定レイアウトが `ArticleTitle` として描画するため、本文の H1 は見出しを二重にする。`.wikicommit/schema/` の全型テンプレート（`default.md` 含む）の本文部が H1 を持たないことがこの慣習の実体であり、テンプレート本文を経由せずに本文を組み立てる `wikicommit-synthesize` と、`wikicommit-generate` Pass 3 は禁止を明記している（指示を消すだけでは LLM が H1 を書き戻す余地が残る）。各型テンプレートの本文冒頭に注記を書く形は採らない — テンプレート本文は生成ページの雛形としてそのままコピーされるため、注記が生成ページへ漏れる。`tests/test_schema_template_no_h1.py` が全型テンプレートに H1 が無いことを検証する。

#### `tags`

`tags` はページを横断した絞り込み・検索補助のための自由記述ラベルであり、`type`（分類）や `title`（ページ自身の識別）とは役割が異なる。付与のルールは `wikicommit-generate` Pass 3（`docs/DesignDoc-skills.md` §11.6）の指示に明記し、LLM の自己裁量に委ねない:

- ページ自身の `title` と同一・類似の語を含めない（例: `title: "認可保育所"` に `tags: [認可保育所]`）
- `type` が表す分類と重複する語を避ける（例: `schema:Person` に `tags: [person]`）
- 複数ページを横断して意味のある概念（分野・カテゴリ・技術要素等）のみをタグ化する
- ベンダー・製品名を含むタグは、概念が実際にそのベンダー固有かを確かめる。ベンダーが出典の一つに過ぎない業界一般語には付けない（例: "context engineering" に `anthropic-tooling`）

既に生成済みのタグは遡及修正しない（`/wikicommit-fix` で個別に直す）。

#### `generated_with` / `translated_with`

そのページを生成（翻訳）した WikiCommit 自身の版。`wikicommit-generate` Pass 3 / `wikicommit-translate` が `.wikicommit/scripts/_version.py`（§3.3）から読んで書き出し時にスタンプする。`config.yml` の `wikicommit_version`（リポジトリを最後に同期した版）とは意味が違うのでキー名を分ける。

- **用途は「作り直すべきページを人間が選ぶ」ことに限られる**。型単位で古いページを判定する機械的な検出機構は設けず、`generated_with` を `grep` して列挙する。版の粒度は型より粗いので、実際にどのページを作り直すかは `CHANGELOG.md` の記述と組で決まる
- `validate_frontmatter.py` は「存在する場合に空文字列不可」だけを検証し、semver への照合はしない（形式検証は将来の正しい値を拒否する側にしか働かない。モデル ID を正規化表に照合しないのと同じ。`docs/DesignDoc-pipeline.md` §6.7）
- 欠如は「この機能追加より前に生成された」を意味する。遡及付与しない

#### `sources[].license`

各ソースの利用条件を記録する任意フィールド。値は自由記述の短い文字列で、SPDX 識別子があればそれ（`CC-BY-SA-4.0`）、無ければ短い語句（`all-rights-reserved`）。`hash` と同じくソース管理ファイル（§4.3）の `source.license` が正であり、ページ側は Pass 3 が生成時に転記したコピーである。公開サイトでは `WikiCommitSources` が出典リンクの直後にライセンス名を併記し、「このページは出典を要約・再構成したものである」という固定文言を表示する（`docs/DesignDoc-publish.md` §8.10）。

- **不明を空文字列で表さない** — 不明ならフィールドごと省略する。`validate_frontmatter.py` は空文字列を ERROR とする（「記録されている」と「不明」が区別できなくなるため）。フィールドが無いことは「制約が無い」ではなく「WikiCommit は知らない」を意味する
- 値の中身は機械検証しない（SPDX 語彙への照合もソースの実際の条件との突合もしない）。WikiCommit はライセンスの当否を判断しない（`docs/DesignDoc-publish.md` §8.10）

#### `aliases` — ソースの原語の表記を残す

`/wikicommit-generate` はソースの言語に関わらず `primary_lang` で書くため、ソース固有の用語・名前は `primary_lang` へ正規化され、翻訳で訳し戻しても元の表記に戻る保証が無い。そこで Pass 3 は、**抽出テキストがそのエンティティの名前・用語を `primary_lang` 以外の言語で逐語的に書いている場合**にその表記を `aliases` に入れ、Pass 4 が照合し、翻訳が使う。

| 論点 | 決定 | 理由 |
|---|---|---|
| 条件 | **抽出テキストが書いているか**で判定し、`source.lang` を条件にしない | `--regenerate` は Pass 2a を通らず、`source.lang` は未記録のことが多い。複数言語が混ざったソースにも同じ規則で当てられる |
| 何を入れるか | 逐語の表記だけ。訳語・音写・推測した表記は入れない | 翻訳が採用する値であり、推測が入ると翻訳の誤りをソースの権威で固定する |
| 件数 | 1 エンティティにつき **1 言語 1 表記**。`title` と同じ文字列は入れない | 別名はリダイレクト URL として公開されるため面積を抑える |
| Pass 4 の照合範囲 | **既存ページに無かった別名（今回の差分）だけ** | `action: update` では過去のソースの本文が取れないことがあり、全別名を照合すると正しい別名が FAIL になる |
| 翻訳での優先順位 | `translator_notes` ＞ 原文ページの**翻訳先言語の**別名 ＞ DefinedTerm 対応表 ＞ 翻訳者自身の訳 | 対応表は翻訳ページの `title` から作られるので、用語ページが揃えば他ページの訳語も揃う |
| 別名の言語判定 | translate の LLM が文字列から判断し、**確信が無ければ使わない** | 誤判定しても対応表か翻訳者の訳に戻るだけで安全側に倒れる |
| 翻訳ページの `aliases` | **原文ページの `aliases` を写さない** | `alias-redirects` が別名ごとにサイト直下のスラッグを作るので、同じ別名を持つと同じ URL を取り合う |
| 検索 | `search_index.py` が `aliases` を `title` と同じ重みで索引する | 翻訳先に無い言語では別名が原語の表記の唯一の置き場になる |
| レビュー状態 | `aliases` は内容側（`reset_review_on_content_change.py` の bookkeeping に加えない） | 別名はリダイレクト URL とプロパティ欄として公開される記述である |

ソースの言語で原文ページを作る形や、翻訳にソースの抽出テキストを渡す形は採らない（前者は `translated_from` と `primary_lang` の前提を作り直すことになり、後者は抽出キャッシュが gitignore されているうえ原文ページに無い内容が翻訳に紛れ込む）。守備範囲は名前・用語だけで、本文の言い回しは対象外。`--regenerate` は Pass 3 を通るので、再生成したページから付く。

#### `reviewed_by`

レビュー追跡 Issue を Close した人の GitHub login。`review-issue-close-sync.yml` が `review_status` を `reviewed` に書き換えるのと**同じコミットで**書き、公開ページの `WikiCommitBanner` が表示する。

- **git 履歴ではなく frontmatter に置く** — `Reviewed-by:` トレーラーは公開サイトの読者に見えず、`WikiCommitBanner` は frontmatter しか読まない設計であり、ラベル 1 つのために `convert_wikilinks.py` へ git 読み取りを持ち込まない
- **値は login であって表示名ではない** — 安定した識別子で、`https://github.com/<login>` へのリンクをそのまま組み立てられる
- `validate_frontmatter.py` は「存在する場合に空文字列不可」だけを検証する（login の形には照合しない）
- **欠如は正常な状態である** — この機能より前にレビューされたページ、経路 B（`wikicommit-review`）でレビューされたページ、`review-issue-close-sync.yml` を置いていない Wiki では付かない。バナーはレビュアー名なしの表示にフォールバックし、`unknown` 等は出さない
- **`reviewed_by` の扱いは常に `review_status` に従う**: 経路 B（`wikicommit-review` Step 5）は `review_status: reviewed` を書く同じ `set_frontmatter_field.py` 呼び出しで `--unset reviewed_by` する（ローカル実行では認証済みの login を得られないので書かせない。残すと前回の経路 A のレビュアーが新しいレビューの主として表示される）。`--regenerate` は Pass 3 がページ全体を書き直すので出力に含めなければ消えるが、無変更時の弁が `review_status: reviewed` を維持した場合は `reviewed_by` も維持する。経路 A は無条件の `--set` で上書きするので自己修復する

#### `properties:` の値を WikiLink 化する判断基準

例の `affiliation: "[[Organization/companya]]"` は、Schema.org の `rangeIncludes`（その property の値が取りうる型）に基づく判断の結果である。`rangeIncludes` は property ごとに、リンク可能なエンティティ型（例: `affiliation` → `Organization`）・DataType（`Text`/`Number`/`Boolean`/`Date`/`URL` 等。例: `sameAs` → `URL`）・両方の混在（例: `jobTitle` → `DefinedTerm` または `Text`。`description` → `TextObject`〈`subClassOf: MediaObject` であり DataType ではない〉または `Text`）のいずれかを宣言する。

- `check_schema_org_type.py --show-range`（`_schemaorg_vocab.py` の `entity_range_candidates()` / `is_in_datatype_lineage()`）がこの分類を機械的に照会する。DataType 判定は `rdfs:subClassOf` の祖先チェーンを辿る（`URL` は `subClassOf: Text` 経由で DataType）
- `wikicommit-generate` Pass 3 は、エンティティ型候補の property の値が独立ページとして存在する（べき）エンティティを指す場合に `[[Type/slug]]` で書く。判断は **RANGE 分類だけ**で決まり、型テンプレートの `granularity` が特定の property を名指しで補強しているかどうかとは独立である（補強は可読性のための注記で、適用範囲を示さない。`docs/DesignDoc-skills.md` §11.6 Pass 3）
- `validate_frontmatter.py` は値が WikiLink 形式であることを強制しない（`domainIncludes` 検証はキーの所属のみ）
- 参照先ページがまだ無くても WikiLink を書いてよい — `check_wikilinks.py`（未解決は WARNING）・`check_orphans.py`・`check_wanted_pages.py` はファイル全体を生テキストとして `WIKILINK_RE` でスキャンするので、`properties:` 内の WikiLink も本文中と同じ扱いを受ける

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
translated_by: "claude-sonnet-4-6"  # 任意: 翻訳実行モデル ID。generated_by と同じ自己申告パターン
translated_with: "0.1.0"           # 任意: この翻訳を生成した WikiCommit 自身の版（generated_with の対）
translator_notes:  # 任意: 次回の全文再翻訳が保持すべき翻訳固有の手直しメモ
  - "2026-06-22: Keep 'Senior Engineer' for jobTitle, not 'Chief Engineer' — confirmed against the company's official English title list."

properties:
  description: "Senior engineer at CompanyA..."
  affiliation: "[[Organization/companya]]"
---

Taro Yamada is a senior engineer at CompanyA...

## Background
...
```

`translator_notes`は `/wikicommit-translate` の全文再翻訳（`docs/DesignDoc-pipeline.md` §6.4）が既存の翻訳を一切コンテキストに渡さない完全ブラインドな設計であることに由来する。原文が別件で更新されて再翻訳が走ると、翻訳ページのみに加えた手直し（`/wikicommit-fix` 経由）は黙って上書きされて消える — この防止策として、ソース管理ファイルの `## User Notes`（§4.3。`wikicommit-generate` が読むが上書きしない、実証済みのパターン）を翻訳ページに横展開したもの。任意フィールドでありフロントマターの必須項目ではない（`validate_frontmatter.py` の必須フィールドチェックには影響しない。フォーマット制約は `docs/DesignDoc-ScriptSpec.md` §「翻訳ページ追加フィールド」参照）。値は文字列のリストで、各要素は `YYYY-MM-DD: <note>` 形式（先頭に日付を付ける。複数エントリが同じ論点に触れる場合、より新しい日付のエントリを優先する — 明示的な削除・上書きは行わず、常に末尾に追記する）。

`## User Notes`（本文の Markdown 見出しセクション）ではなく `translator_notes`（フロントマールのリストフィールド）という異なる形式を採用した理由（`/code-review --fix` のレビューで指摘。当初は `## Translator Notes` という本文見出しセクションとして実装していたが撤回した）:

- **公開範囲**: `.wikicommit/entity/` の Wiki ページ本文は `convert_wikilinks.py` により選別なくそのまま `content/` へ書き出され、読者に公開される。`## User Notes` はソース管理ファイル（`.wikicommit/source/`）に置かれ、そこから公開ページを作る `_write_source_page()` が描画する節を**ホワイトリストで限定している**ため公開されない一方（`translator_notes` をフロントマターに置くという結論は変わらない）、翻訳ページの本文に同じパターンを置くと、翻訳プロセスの内部メモ（「'Chief Engineer'ではなく'Senior Engineer'を維持」等）がそのまま読者向けページに表示されてしまう。
- **本文を読む全ての下流機能への意図しない漏洩**: 本文見出しセクションのままだと、`search_index.py`（FTS5全文インデックスが本文全体を対象とするため、メモ中の「不採用にした訳語」が検索結果に紛れ込む）・`wikicommit-ask`（本文をLLMコンテキストに注入する設計のため、読者への回答にメモの内容が漏れ得る）・`wikicommit-review`（本文の主張をソース文書と逐一照合するため、翻訳プロセスに関するメモをソース未収載の主張と誤判定しかねない）のいずれにも、本文と区別する仕組みが無い。フロントマターのフィールドであればこれらはいずれも影響を受けない（frontmatterを対象にしないため）。
- **`translated_by`/`translated_at`/`source_commit` との一貫性**: これらは既にフロントマタートップレベルの WikiCommit 独自ブックキーピングフィールド（Schema.org 語彙とは無関係なため `properties:` に入れない）であり、`translator_notes` も同種の性質を持つ。同じ場所に置くことで一貫性が保たれる。

#### 合成ページのフロントマター（`derived_from`）

`/wikicommit-synthesize`（`generate` が外部ソースから、`synthesize` は既存 `entity/` ページ群から新規ページを作る）が出力するページのフロントマター仕様。`derived_from` フィールドの有無が、この合成ページと通常ページを区別する判定基準（`translated_from` と同じ位置付け）。

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

```yaml
---
source:
  type: path                              # path | url | wikicommit
  path: raw/paper-2024.pdf
  hash: sha256:abc123def456...
  license: CC-BY-SA-4.0                   # 任意。不明なら値なしの空欄
  lang: ja                                # 任意。抽出テキストの主言語（ISO 639-1）。Pass 2a が書く。登録時は空欄

schema: schema:Person    # LLM へのヒント（省略時は LLM が自動判断）
status: generated        # pending | generated | partial | excluded | outdated | failed
last_generated_at: "2026-06-22"
extracted_tokens: 3200    # パス1（テキスト抽出）完了時の抽出テキストの概算トークン数（簡易概算で可。例: 文字数 ÷ 4）。再実行のたびに上書き
generated_pages:
  - .wikicommit/entity/ja/Person/yamada-taro.md
  - .wikicommit/entity/ja/Organization/companya.md
failed_pages: []
# ambiguous_entities:     # 任意。status: partial かつ型が確定できないエンティティが
#   - title: ...          # あるときのみ書かれ、他のどの結末に到達した時点でもフィールドごと消える。
#     type: ...           # この例は status: generated なので存在しない（受け皿だけ配らない）
#     alternatives: [...]
---

## Summary

（自動生成・`wikicommit-generate` パス 2 実行のたびに上書き）このソースの内容を 2〜3 文で要約する。
**この節にはソースの内容だけを書く** — 今回の実行がそれをどう扱ったかは下の
`## Generation Notes` に分ける（公開されるのは `## Summary` だけである）。
例: "本文書は CompanyA の技術ブログ記事。山田太郎氏の紹介と Project Alpha の概要を含む。"

## Generation Notes

（自動生成・`wikicommit-generate` パス 2c が書く。該当が 1 件も無ければ節ごと作らない）
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

（人間にしか下せない判断に当たって保留し、その実行の中で答えが得られなかったときのみ存在。
`wikicommit-generate` が書き、そのソースが他のどの結末に到達した時点でも削除する
——`## Failure Reason` と同じ一時セクションであり、同じく `primary_lang` に関わらず英語で書く）
なぜ止まったかを 1〜数文で記録する。**`status` は書き換えない**（`pending` / `outdated` のまま）ため、
ソースはキューに残り、人がいる次の実行がそのまま拾って、繰り返しの後に人間に尋ねる。
実行の途中で書かれ、同じ実行の最後の質問で答えが得られれば、その後の処理で消える。
例: "LOW_DENSITY: ... (natural-language character ratio: 0.11, threshold: 0.3) —
non-prose breakdown: links 12%, numbers/tables 71%, other markup 17%."

## Retraction Reason

（`status: retracted` のときのみ存在。**人間が手で書く** — Skill は書かない）
このソースを取り下げた理由を1〜数文で記録する。理由コードの enum は持たない（下記「`retracted`」）。
例: "The 2019 figures in this listing contradict the city's own published statistics;
confirmed with the publisher that the page was never corrected."
```

`status` の遷移：

| status | 意味 | 設定タイミング |
|---|---|---|
| `pending` | 管理ファイル作成済み・未生成（または再生成待ち） | `wikicommit-generate` 実行時（新規登録、またはハッシュ不一致による再登録） |
| `generated` | 1 件以上のページを生成し、生成失敗も `ambiguous` も無い（ポリシー除外は混ざっていてよい）・ハッシュ一致 | `wikicommit-generate` 完了時（失敗なし） |
| `partial` | 生成失敗または `ambiguous`（型確定待ち）のエンティティが残っている。**`failed_pages` の空／非空で区別する** — 非空は再試行で、空は人が型を確定すれば進む（下記「`partial` と収集条件」） | `wikicommit-generate` 完了時（部分失敗、または ambiguous あり） |
| `excluded` | 全エンティティが除外され、生成ページが 0 件（除外理由は問わない — `theme` 不一致・`entity-policy.md` の許容性方針のどちらでもこの値になる） | `wikicommit-generate` 完了時（`action: exclude` による全除外。`failed` とは異なりページ生成自体は試みていない） |
| `outdated` | ソースが変更された（ハッシュ不一致） | `check_ingest_freshness.py`（`wikicommit-status` Skill）が自動検出して書き換える |
| `failed` | 全ページ生成試行したが失敗 | `wikicommit-generate` 失敗時（`## Failure Reason` に理由を記録） |
| `retracted` | 取得は完全だったが**内容が信用できない**と判断され、以後の取り込み対象から外された | **人間が手で書く**（`## Retraction Reason` に理由を記録。下記「`retracted`」） |

テーマ判定（エンティティ単位の `action: exclude`）は `config.yml` の `theme` が空なら無効で、全エンティティを生成する。詳細は `DesignDoc-skills.md` §11.6。

#### 管理ファイルのパスと同一性

- **ディレクトリ**は識別子の形で分ける — ローカルの相対パスなら `path/`、URL なら `url/`（URL が PDF 等のファイルを指していても `type: url`）。`source.type` の値（`path` / `url`）も同じ語彙で、`type: path` は必須フィールド `path`、`type: url` は `url` と対になる
- **`type: path`** は実ファイルパスをそのままミラーし、**元の拡張子を保持して `.md` を付け足す**（`raw/paper.pdf` → `.wikicommit/source/path/raw/paper.pdf.md`）。拡張子を置き換えると `paper.pdf` と `paper.docx` が衝突する
- **`type: url`** はホスト名をディレクトリ、URL パス部分をファイル名にする（`add_source.py` の `url_to_filename()`）。パスを持たない URL は `<host>/index.md` ではなく **`<host>.md`**（`<host>/` ディレクトリの兄弟）になる — 実パスが `/index` の URL と衝突しないため。**クエリは捨てずにサニタイズして stem に含める**（`watch?v=abc` → `watch-v-abc`。クエリでコンテンツを識別するサイトで異なる URL が衝突しないため）
- **同一性キーは導出ファイル名ではなく `source.path` / `source.url`** である。`add_source.py` の `process_file()` / `process_url()` は `.wikicommit/source/` 配下を実走査し（`find_mgmt_file_for_path()` / `find_mgmt_file_for_url()`）、一致する管理ファイルを探してから `SKIP` / `RECHECK` 等を判定する（参照側の `resolve_source_cache_path.py` と同じ方式）。これにより旧命名規則で作られた管理ファイルも二重登録にならず、導出規則を変えても既存リポジトリが壊れない。自動リネームはせず、新旧の命名の混在を許容する（必要なら `git mv` で手動移行できる）
- **トラッキングパラメータ**（`utm_*`・`fbclid`・`gclid` 等）は、ファイル名導出と同一性比較の**内部でのみ**除去し、残りのクエリをキー順にソートする（フラグメントも除去）。`source.url` にはユーザーが渡した URL をそのまま書く。ホスト・パスの正規化（`youtu.be/<id>` と `youtube.com/watch?v=<id>` の同一視等）はサイト固有の知識を要するので行わない
- **ファイル名が長すぎる場合**（導出名が `_MAX_STEM_BYTES` を超える）は切り詰めて `-<sha8>`（`source.path` / 正規化後 URL のハッシュ）を付す。同一性は走査で決まるので影響しない
- **導出先が別のソースに占有されていた場合**は、既存ファイルを一切書き換えず `-<sha8>` を付した代替パスに退避し、その旨を登録結果のメッセージに明示する（黙って別名にしない。URL は利用者が変えられないので ERROR で止めない）
- トップレベルは `.wikicommit/source/` だけを見る（`check_ingest_freshness.py` / `reconcile_ingest_status.py` / `wikicommit-generate` の走査）。旧 `.wikicommit/ingest/` に残る管理ファイルは `git mv .wikicommit/ingest .wikicommit/source` で移すまで見えない。`wikicommit-merge` の新規ソースファイル検出は再帰 glob（`.wikicommit/source/**/*.md`）なので深さに依存しない
- 公開サイトでは `convert_wikilinks.py` の `generate_source_pages()` が全管理ファイルを走査し、管理ファイル 1 つにつき `content/sources/` に公開ページ 1 つを作る（`generated_pages` で逆引きが要らない）

**語彙**: `.wikicommit/source/` 配下のファイルは「ソース管理ファイル」（source management file）と呼び、Python の内部識別子は `mgmt_*` 系にする（`convert_wikilinks.py` では `source_dir` / `source_root` が `.wikicommit/entity/` を指しているため `source_*` にしない）。次の "ingest" は**統一漏れではなく据え置いた層**であり、変えない:

| 据え置く対象 | 理由 |
|---|---|
| 動詞用法（「ingest した」「同じ ingest で」等） | 処理を指す語として正しい |
| `.wikicommit/.cache/ingest-fetch/` | 変えると既存キャッシュが失効し全 URL ソースの再フェッチが起きる |
| `check_ingest_freshness.py` / `reconcile_ingest_status.py` というファイル名と、その役割を述べる語 | `copy_tree` は削除しないので、リネームすると配布済みリポジトリに旧ファイルが孤児として残る。「取り込み処理の鮮度／状態」と読めば正しい |
| レビュー追跡 Issue のマーカー `<!-- wikicommit-ingest: ... -->` | GitHub 側に永続化済みで、変えると既存の Issue との照合が外れて重複起票する |

#### 本文の節

- **見出しラベル（`## Summary` / `## Generation Notes` / `## User Notes` / `## Failure Reason` / `## Deferred Reason` / `## Retraction Reason`）は `primary_lang` に関わらず固定の英語**である。機械が照合する識別子であってローカライズしない。旧見出し（`## サマリ` 等）の管理ファイルは自動リネームしない
- `## Summary` の本文は `primary_lang` で書く。**`## Summary` だけが公開される**（`_write_source_page()` が公開する節は**ホワイトリスト**: `type` / `original` / `status` / `license` /（取り下げ時のみ）`## Retraction Reason` / `## Summary` / `generated_pages`）。新しい節は何もしなくても非公開になる。`## Summary` を機械が読むのは `parse_summary_section()` の 1 箇所で、次の `##` 見出しで止まる
- **除外理由と `coverage_gap_note` は `## Generation Notes` に書き、`## Summary` に書かない** — `## Summary` は公開されるので、書けば `entity-policy.md` が「作らない」と決めた人物の実名と除外理由、内部の識別子が読者に届く。言語は `primary_lang` のまま。フロントマターにはしない（集計する消費者が無い）。古い管理ファイルの `## Summary` に混ざった追記は機械的に分離できず、引数なしの実行は `excluded` / 除外のみのソースを収集しないので、手で編集するかソースを名指しで再実行して直す
- **`## Failure Reason`** は `status: failed` のときだけ存在し、失敗理由を常に英語で書く（運用者向けのデバッグ情報）。再試行で `generated` / `partial` / `excluded` に遷移したら削除する（解消済みの理由が現在の状態と矛盾しないため）

#### `source.license`

`add_source.py` は管理ファイルの**新規作成時に**`source.license` を書く。値は「明示指定（`--license "<identifier>"`）> 既知ドメイン対応表 > 空欄」の優先順で決まる。

- 対応表 `KNOWN_SOURCE_LICENSES` は「確認済みのものだけを決定論的な表に持つ」パターンで、そのサイトが自サイトのコンテンツ全体に明示しているライセンスだけを登録可能ドメイン単位で持つ（Wikimedia 系: `wikipedia.org` 等 → `CC-BY-SA-4.0`、`wikinews.org` → `CC-BY-2.5`、`wikidata.org` → `CC0-1.0`）。照合はホストの左ラベルを順に落として行う（`ja.wikipedia.org` → `wikipedia.org`）
- **既存の管理ファイルは書き換えない**（人が直した値を機械が壊さない）。変えたいときは管理ファイルを直接編集する。`type: path` にはドメインが無いので、`--license` か手編集だけが入り口である
- **LLM に推定させない** — ライセンスは文書の外にある法的事実であり、確認していないものを推定値で埋めると記録があること自体が確認済みに見える。不明なら空欄のまま残し、`wikicommit-generate` Step 0 が「不明であること」と値の入れ方を伝える

#### `source.lang`

`wikicommit-generate` の Pass 2a が抽出テキストを全文読む際に、**主として書かれている言語を ISO 639-1 で 1 つ**答え、その場で書く。`add_source.py` は登録時に空の `lang:` を置く。消費者は 2 つ — 俯瞰ページの言語別集計（`docs/DesignDoc-publish.md` §8.8.1。ホスト数と違い言語数は有界なので切り詰めを生き延びる集約になる）と、公開ソースページ（`content/sources/`）の 1 行である。

- **欠如は「まだ記録されていない」だけを意味する**。`mul` や「判定不能」の値は置かない（置けば欠如の意味が割れる）。「まだ処理していない」と「記録が始まる前に処理された」の区別は値ではなく `last_generated_at` の有無で付け、俯瞰ページは両者を別の行に出す。未記録は隠さず 1 行として出す
- LLM の判断でよい — ライセンスと違い言語はテキストそのものの性質で、いま読んだテキストが証拠になる。`<html lang>`・`Content-Language` 等の決定論的な経路は採らない（自己申告でよく誤り、`type: path` と PDF には無く、値の出所が 2 つになる）
- 厳密には「抽出テキストの言語」である（`source.hash` が持つのと同じ曖昧さ）
- **書き込み点は Pass 2a** で、Pass 4 に到達しない経路（保留・失敗）でも分かった言語を失わない。Pass 1 で保留したソースは言語が分からないまま残る。Completion Notice の言語不一致の通知はその場の通知として別に残す
- ページの `sources[]` へは転記しない。値はコードのまま表示し、言語名へローカライズしない。`/wikicommit-status` の所見にはしない（多言語であることは欠陥ではない）
- **公開ソースページは `license` 行の隣に `Language: <code>` の 1 行を出す**（`convert_wikilinks.py` の `_write_source_page()`）。`## Summary` は `primary_lang` で書かれるため、これが無いと `primary_lang` と違う言語のソースが `primary_lang` のソースに見える。ホスト名からは言語を導けないので「URL を見れば分かる」は理由にならない
  - **記録があれば `primary_lang` と同じ言語でも常に出す**。違うときだけ出すと行の存在そのものが「この出典は要注意」という印になり、「`primary_lang` でない ＝ 劣る」と読まれる。全ページに同じ形で出せば行は事実として読まれる
  - **未記録なら行を省く**（`license` と同じ）。**俯瞰ページが未記録を 1 行として出すのと判断が違う** — 俯瞰側が未記録を出すのは分布を誤らせないためで、1 ページ単位には誤らせる分布が無い。「未記録」はソースの性質ではなく「記録が始まる前に処理された」というパイプラインの経緯しか述べず、遡及付与しないので古い Wiki では大半のページに並んで雑音になる。経緯を知りたい読者には俯瞰ページの「未記録」行がある
  - YAML 1.1 で `False` と読まれる `lang: no`（ノルウェー語）の正規化は `_normalize_source_lang()` 1 か所に置き、集計とページの両方がそれを通る
- **文字列でない値（`False` を除く）は未記録として扱う** — リスト（`[ja, en]`）・YAML 1.1 で `True` と読まれる `yes` / `on`・数値は「1 つのコード」の規則に反しており、言語を記録していない。公開ソースページでは行を省き、俯瞰ページの集計では値を持たない管理ファイルと同じ規則（`last_generated_at` の有無。`status: excluded` は日付が無くても「未記録」）で「未処理」か「未記録」に数える。判定は `_normalize_source_lang()` の 1 か所で、集計とページは食い違わない
  - **文字列化して出さない** — `['ja', 'en']` や `true` が読者向けのページと集計の行に載る
  - **「不正な値」の行を別に立てない** — 欠如の意味を割らないのと同じ理由で、値の種類を増やさない。この値は LLM が規則を破ったときにしか生じず、Pass 2a の再実行（`/wikicommit-reconcile`・強制リチェック）が上書きする
  - **書き込み点に検査を足さない** — Pass 2a の指示はすでに「ISO 639-1 のコードを 1 つだけ」と言っており、書き込みはスクリプトを通らない。読む側が未記録として扱う以上、不正な値が残っても読者には何も出ず、検査を足しても既存の管理ファイルに残る値には効かない
- 遡及付与しない。`status: generated` のソースは収集されないので、`/wikicommit-generate <url>` の強制リチェックか `/wikicommit-reconcile` を経るまで空のまま残る

#### `retracted` — 登録済みソースを取り下げる

取得は完全だが**内容が信用できない**と人が判断したソースは、管理ファイルに `status: retracted` と `## Retraction Reason` を**人が手で書く**。Skill は書かない。証拠拘束の下で機械はソースを疑えない（ソースは判定の基準であって対象ではない）ので、これは外部知識を持ち込める人間にしか言えない判断である。

| status | 何が起きたか | 判定者 |
|---|---|---|
| `failed` | 取得できなかった | 機械（3 ガード） |
| `excluded` | 取得できたが、書くべきエンティティが 1 件も無かった（ソースへの評価ではない） | 機械（`theme` / `entity-policy.md`） |
| `retracted` | 取得できたが、**内容が信用できない** | **人間のみ** |

- **管理ファイルを残すことが要点である** — 同一性走査がその URL・パスを拾うので、同じソースの再登録を構造的に止められる。ソースを削除する形（理由が commit message にしか残らず、同じ URL がまた登録される）や `source-policy.md` の `rejected:` を登録済みにも効かせる形（あれは候補段階の記憶で、既存の管理ファイルは Pass 1 が拾い続ける）は採らない。値の名前も `rejected` にしない（層が違う）
- **理由は散文で残し、理由コードの enum を足さない**（理由で分岐する消費者がいない）。ライセンスの誤認による取り下げも同じ機構に乗り、公開を急いで止める必要があれば `/wikicommit-remove` が担う
- **既に生成されたページには触れず、報告に留める**。`review_status` を `pending` に戻さない — 内容は変わらず根拠が変わるだけなので決定論的に扱えず、戻しても何を直すべきかは伝わらない。対処は人が選ぶ: 残りのソースで作り直すなら `/wikicommit-generate --regenerate`（取り下げたソースとその `sources[]` エントリを落として作り直す）、記述を手で直すなら `/wikicommit-fix`、ページごと下ろすなら `/wikicommit-remove`。`check_retracted_sources.py`（`docs/DesignDoc-ScriptSpec.md`）が `retracted` なソースを `sources[]` に持つページを残り件数付きで列挙し、`wikicommit-status` Step 12 が報告する
- `status` の値に機械的な検証は無い（`validate_frontmatter.py` はソース管理ファイルを検証しない）

**取り込み側のガード**:

1. `check_ingest_freshness.py` は `retracted` を `CHECKABLE_STATUSES` から外す（含めるとソースファイルを 1 バイト触っただけで `outdated` に戻り、収集対象へ復帰する）。`add_source.py` の `process_file()` も hash 比較より前に返す
2. `add_source.py` は `SKIP: already registered` ではなく結果コード **`RETRACTED:`** を返し、`## Retraction Reason` を引用して人に伝える（`process_url()` / `process_file()` とも）
3. 公開サイトの source ページは**残して取り下げを表示する**（`_write_source_page()` が取り下げの明示と `## Retraction Reason` を描画する）。「使っていたが取り下げた」は公開されるべき記録であり、`status: removed` のページを書き出さないのとは要求が逆である

**参照側のガード**（ソースの内容を読む 3 経路）:

| 経路 | ガード |
|---|---|
| `/wikicommit-ask --include-source` | `resolve_source_cache_path.py` が `RETRACTED:` 行と **exit code 2** で答え、`type: path` / `type: url` の両経路が分岐する。exit 1 には畳まない（`type: path` では exit 1 に生ファイルを読んで答えるので素通りする）。`status` の確認はキャッシュ探索より前に置き、読むのは `retracted` だけ |
| `wikicommit-review` Step 4 item 1 | `check_retracted_sources.py --list` で取り下げ分を**証拠集合から外して続ける**（止めない） |
| `wikicommit-fix` Step 3 | 同上 |

- **止めない理由**: review をブロックすると信頼ラダーに第 3 の状態を持ち込む。`reviewed` が述べるのは「人が読んで引っかからなかった」であってソースの妥当性ではない
- 外して照合すると「取り下げられた文書だけに立っていた記述」が 1 件ずつ現れる — 人が `--regenerate` / `--fix` / `--remove` を選ぶのに要る粒度である。所見は「ページが誤っている」ではなく「この記述は取り下げ済みのソースだけに立っていた」と書く
- 残りが 0 件なら既存の分岐に落ちる（review は item 4 の全文フォールバック、fix は Step 3 item 5 の警告と確認）
- 判定は**取得の前**に置く（取得後に外すと取り下げ済みの本文がコンテキストに載る）。掛けるのは `sources` 経路だけで、**`sources` の解決後**に掛ける（翻訳ページは親から継承するため）。`derived_from` 経路と `wikicommit-synthesize` の grounding には掛けない（読むのは `entity/` のページで `status` を持たない。grounding ページ自身は `check_retracted_sources.py` が名指しする）
- 新しいスクリプトは作らず `check_retracted_sources.py` に `--list` を持たせる（判定は既にそこにあり、同一性キーの規則の写しを増やさない。突き合わせは Skill 側）。`resolve_source_cache_path.py` は元から管理ファイルを走査するので、`status` の判定を 1 行ずつ許容する複製として持つ
- `--list` を実行できない古い `.wikicommit/scripts/` では**警告して続行する**（この機能以前の挙動に戻るだけで、取り下げが無い Wiki では no-op）
- `wikicommit-fix` は、Issue のコメントが「このソースが誤っている」と言っている場合に `wikicommit-review` Step 4 item 5 と同じ案内（人が `retracted` を手で書く）をする

#### 保留 — `status` に値を足さずに表現する

「人間が見れば答えが変わりうる判断」に当たったとき、**対話・非対話を問わず、そのソースについて何も進めない**。`status` は `pending` / `outdated` のまま据え置き、理由を `## Deferred Reason` に書いて次のソースへ進む。ソースごとの繰り返しが終わった後、人がいればその実行の中で保留分をまとめて尋ね、答えが得られたソースだけを Pass 1〜4 にもう一度通す（答えは実行記録の一覧に置き、同じ実行の中で使い切る。仕組みは `docs/DesignDoc-skills.md` §11.5「保留した質問は繰り返しの後にまとめて尋ねる」）。人がいない実行・答えなかった保留は、次の人がいる実行が既存の収集条件でそのまま拾って尋ねる。

- **答えを管理ファイルに書かない** — 答えはその実行の中で使い切るので、新しいフィールドは要らない。実行をまたいで答えを持ち越す形を採ると、ガード A の「続行する」を記録する場所が要り、次の実行で同じ警告にまた当たって保留になる

- **新しい `status` 値（`deferred` 等）は足さない** — `status` の消費者（Pass 1 の収集条件・`add_source.py` の分岐・`check_ingest_freshness.py` の `CHECKABLE_STATUSES`・`wikicommit-status` の集計・`reconcile_ingest_status.py`）すべてに分岐が増える。進めないことがそのまま表現になる
- **例外**: 強制リチェック（`RECHECK:`）で到達した場合は `status` が `generated` / `failed` / `excluded` のままでどの収集条件にも拾われないので、`pending` に戻す（`/wikicommit-reconcile` と同じ requeue）
- `extracted_tokens` は書かれないが、**`source.hash` は既に書かれている**（`type: url` はフェッチ直後の `--write-hash`、`type: path` は登録時）。書き戻して消してはならない（抽出キャッシュと食い違う）。`reconcile_ingest_status.py` が保留を `generated` へ戻さないのは、空のハッシュではなくハッシュの突き合わせによる（初回の保留はどの `sources[]` もそのハッシュを引用せず、再取り込みや requeue は `generated_pages` / `last_generated_at` を持つのでスキップされる）

| 保留する | 理由 |
|---|---|
| ガード A の `LOW_DENSITY:` | テキスト形状のヒューリスティックで、リンクの多い正当な資料と区別できない |
| Pass 2b の厳格閾値を外れた型候補 | 型がふさわしいかは人間の判断で、declined にすると祖先型で書かれて再分類の手が無い |
| `NETWORK_UNAVAILABLE:` | 人ではなくネットワークを待つ。対話実行でも保留し、強制リチェック由来でも `pending` に戻さない（`source.hash` は変わっていない）。連続 2 件で処理全体を停止する（`docs/DesignDoc-skills.md` §11.5） |
| `action: update` のページの既存ソースが取得できない（`ERROR:`） | 取得できる環境を待つ。Pass 1 が新しい `source.hash` を書いた後なので、強制リチェック由来なら `pending` に戻す |

**決定論的な判定は保留しない** — ガード B（既知 JS シェルドメイン）・抽出結果が空／読み取り不能・YouTube の URL 形式違いは `status: failed` が正しい。ガード C（取得能力不足）は処理全体を停止する。**`excluded` は全エンティティがポリシーで除外された場合にだけ使い**、取得できなかった・レビューできなかったソースに使わない（`excluded` は収集されないので、キューから静かに落ちる）。

既に `status: failed` になったソースは `/wikicommit-reconcile` では戻せない（`failed` を意図的にスキップする）。`type: url` は `/wikicommit-generate <url>` が `RECHECK:` として強制再フェッチし、`type: path` は `status` を `pending` に書き戻してから再実行する。

#### `partial` と収集条件

Pass 1 が収集するのは `status` が `pending` / `outdated`、および **`partial` かつ `failed_pages` が非空**のソースである。

- `partial` は「誰かが何かすれば進む」状態に絞られている: `failed_pages` が非空なら再試行、空なら **ambiguous（型確定待ち）**である
- **ポリシー除外だけが残ったソースは `generated`** になる（Pass 4 手順 7 の第 1 分岐は「`failed_pages` 無し・`ambiguous: true` 無し・少なくとも 1 件がページを生成した」）。全件除外（成功ゼロ）は `excluded`。Wiki が書かないと決めたものを書かなかったのは設計どおりの完了であり、`partial` と名乗ると「部分的に止まっている」と読者に伝わる。除外の記録は `## Generation Notes` と Completion Notice が持つので失われない。`excluded_entities` フロントマターは足さない（区別を要する消費者が無い）
- **ambiguous は収集しない** — 読み直しても同じエンティティが同じ `ambiguous: true` を返すだけで、人が決めた型はどこにも記録されない。Pass 4 手順 7 の `partial` 分岐が `ambiguous_entities`（`{title, type, alternatives}` の配列。他の分岐ではフィールドごと消す）を書き、待ちが実行をまたいで見えるようにし、`wikicommit-status` がソースとエンティティを名指しする。解除は `/wikicommit-reconcile --source <path|url>`、または型を確定した後にソースを名指しで再実行する（引数指定の経路は `status` を問わず処理する）
- 古いリポジトリに残る除外のみの `partial` は自動では直らない。管理ファイルの frontmatter だけで閉じる述語（`status: partial`・`failed_pages` が空・`ambiguous_entities` が無い）と `set_frontmatter_field.py --require` で書き換えるコマンドを `CHANGELOG.md` に書いてある（`/wikicommit-reconcile` はページを書き直すので勧めない）

**5 件ガードの選定順序**: (1) `status: outdated`、(2) 一度も生成されていない（`last_generated_at` なし）、(3) 残り、の 3 段で、それぞれパス昇順。`outdated` が先なのは、公開済みのページの内容が**誤っている**状態だからである（未処理のソースは**欠けている**だけ）。処理対象の提示も「未フェッチ」「フェッチ済みだが未生成」「再処理待ち」に分ける（`source.hash` の空／非空が前 2 者を分ける）。`wikicommit-status` は「登録済みだが一度も処理されていないソース」を、失敗ではなく順番待ちとして集計に加える。

薄いソースで生成済みのページに対して、より良い未処理ソースがあることの検出は行わない（未処理ソースの内容と既存ページの主題の突き合わせは決定論的スクリプトの範囲を超える）。未処理ソースが放置されない状態を作ることで間接的に解消する。

### 4.4 `sources` フィールドの種別

| type | 必須フィールド | CI 検証 |
|---|---|---|
| `path` | `path`, `hash` | hash と `path` が指す現物を比較 |
| `url` | `url`, `hash` | hash でページ更新を検知（任意） |
| `wikicommit` | `url`, `hash` | hash でフェデレーション更新を検知 |
| `manual` | `author`, `created_at` | hash 検証なし。作成者を記録 |

`license` は全種別に共通する任意フィールド。上表の必須フィールドには含まれず、CI 検証も値の存在・形式のいずれも要求しない（空文字列のみ ERROR。§4.1「`sources[].license`」）。

### 4.5 削除ページのフロントマター追加フィールド

```yaml
status: removed                    # 削除済みフラグ（review_status とは別フィールド）
removed_at: "2026-06-21"
removed_reason: obsolete           # obsolete / merged / gdpr
merged_into: .wikicommit/entity/ja/DefinedTerm/new-page.md  # merged の場合のみ
```

### 4.5.1 `.wikicommit/view/` — 二次知識の層

知識には性質の異なる 2 種類があり、置き場を分ける。

| | 照合先 | 書く主体 |
|---|---|---|
| 一次知識（`.wikicommit/entity/`） | 外部ソース文書（`sources` + hash） | `wikicommit-generate` |
| 二次知識（`.wikicommit/view/`） | Wiki 自身のページ（`derived_from`） | `wikicommit-synthesize` |

**この違いはページの主題ではなく「何に照合できるか」にある**。主題が世界に実在する実践でも、`sources` を持たず `derived_from` だけを持ち、どの 1 文も 1 つのソース文書に還元できないページは二次知識である。

分ける理由は 3 つある。(1) **読者に区別が見える** — 同じ型ディレクトリに一次と二次が混ざらない。(2) **型選択の非決定性が無くなる** — 二次知識に Schema.org 型を選ばせると、同じ topic の 2 回の実行が別の型ディレクトリに割れうる。(3) **型が本来表せないものを型で代用しない** — Schema.org は事物をモデル化する語彙であり、「適用条件・前提・失敗モード・根拠の種類」を持つものは事物のクラスではなく**読み方**である。読み方は `type:` ではなく `kind`（下記）で表す。

#### 置き場所と公開先

| | パス |
|---|---|
| ディスク | `.wikicommit/view/<lang>/<slug>.md`（**Type セグメントを持たない**） |
| 公開 | `content/<lang>/View/<slug>.md` |
| WikiLink | `[[View/<slug>]]` |

**`content/view/<lang>/...` にはしない**。`wikicommit-breadcrumbs` / `wikicommit-language-switcher` / `wikicommit-explorer` の 3 プラグインは先頭セグメントが言語であることを `LANG_SEGMENT_RE = /^[a-z]{2}$/` で前提にしており（この複製の同期は CI が強制する）、言語を先頭に保てば 3 プラグインとも無改修で済む。ディスク上と publish 側のパスがずれる点は、`custom/` を publish 時にフラット化する（§5.3）のと同じ形である。

`WIKILINK_RE` は `View` を特別扱いしない（Type セグメントの文字クラスに一致する）。`View` は**予約名前空間**として解決側で分岐する — Schema.org 語彙に `View` 型は存在しないため、インストール済み型と衝突しない。

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

**`kind` は任意フィールドとする**。先に受け皿だけ作ると空のまま残る。**`kind` が空のページが溜まること自体が「新しい kind を足すべき」という証拠**になる。保留する kind は `lineage`（因果・派生の連鎖）と `process`（横断する手順の流れ）で、どちらも既存 kind の `Boundary` に違反しないため急がない。

**kind を後から足すときの生成規則**: kind の正体は「grounding ページ間の**どの関係を使うか**」である。この形で並べると抜けが機械的に見える — 同一主題への複数の記述（`practice`）／同型の少数を並べて差分（`comparison`）／多数に繰り返し現れる共通の形（`pattern`）／時間順（`timeline`）／因果・派生の連鎖（保留）／同一の問いへの対立（`debate`）／近傍全体の地図（`landscape`）／横断する手順の流れ（保留）。増やしすぎない歯止めとして、**プラグインが既に機械的に見せている関係は kind にしない**（「1 つの `Person` が複数の `Place` に関わっている」は `backlinks` と `wikicommit-graph` が描いている）。追加の判定基準は「**その kind が無いと既存 kind の `Boundary` に違反するページが生まれるか**」— `pattern` は無ければ `comparison` に分類されるが `comparison` の `Boundary`（差分の提示に留める）に正面から違反するため採用した。

**kind はパスに出さない**。`[[View/comparison/slug]]` は `WIKILINK_RE` 的には通るが、kind の選択ミスがファイルの位置を動かし、どの WikiLink からも到達できない場所に解決される。kind が駆動するのは以下で、いずれもパスに影響しない: (1) `wikicommit-synthesize` の俯瞰モードの着眼点提案（`build_survey_view.py` の出力と対応が付き、提案が網羅的になる）、(2) 本文生成（kind の記述と `Boundary` をプロンプトに入れる）、(3) 同 Skill の grounding 照合ステップにおける `Boundary` 検査。**(3) が無いと kind は誰も見ないラベルになって drift する**（§5.2 の `granularity` と同じ失敗）ため、これは kind を持つことの条件である。view ツリーの index は kind でグルーピングしていない — `kind` が任意である以上どのグルーピングにも「kind の無いページ」の受け皿が要り、通常小さいツリーに対して見出しを増やす価値が読み順を乱す不利益に見合わないため。後から足してもページの契約は変わらない。

**`landscape` が数を書かない理由**: build 生成の overview ページ（`docs/DesignDoc-publish.md` §8.8.1）が総ページ数・レビュー済み比率・被リンク上位・型別集計・wanted / orphan・情報源の内訳を毎ビルド正確に再計算している。LLM が本文に「83 ページ」と書けば翌日には古くなり、検出する仕組みが無い。数が要るならそちらへリンクする。

#### スクリプトの走査対象

`ENTITY_DIR` と同じく `VIEW_DIR` / `VIEW_TYPE_SEGMENT` / `VIEW_KINDS` / `parse_view_path()` / `collect_view_pages()` / `view_page_path()` は `_wikilink.py` に置く。各スクリプトは「view ツリーを含めるか」を 1 本ずつ決める加算的な分岐になる。

| 扱い | スクリプト |
|---|---|
| 含める | `validate_frontmatter.py`（view ページ専用ルールで分岐）・`check_wikilinks.py`（`[[View/x]]` の解決と view ページからの発リンク検査）・`check_raw_html.py`・`check_wanted_pages.py`・`check_expires.py`・`check_translation_status.py`・`search_index.py`・`rebuild_index.py`（Type 別ではなく**言語別** index の新モード）・`convert_wikilinks.py`（第 2 の入力ツリー） |
| 主消費者 | `check_derivation_freshness.py`（view ツリーが主対象。entity ツリーも走査する — view ツリー導入前に書かれた合成ページはそこに残るため） |
| 除外 | `check_recurring_characters.py`・`check_unlinked_entity_mentions.py`（`properties:` 前提）／`check_schema_coverage.py`・`check_installed_type_usage.py`（`type:` 前提）／`reconcile_ingest_status.py`（`sources[].hash` 前提）／`check_orphans.py`（view ページは生まれつき被リンクゼロ） |
| 既定で除外・フラグで包含 | `build_survey_view.py`（`--include-view`）。view の分析をさらに分析することを避けるため。着眼点が実際に grounding するのはその下の entity ページである |

**除外側は `tests/test_view_tree.py` が固定している**。除外の理由（読むフィールドが無い・全件 orphan になる）はツリーの中身に依存せず常に成り立つため、後の変更が `collect_entity_pages()` を両ツリー走査に差し替えても**エラーにはならず**、対処できない所見が増えるだけになる — 報告が無視されるようになる典型的な壊れ方であり、テストで止める。

スクリプト以外の変更箇所: `wikicommit-merge` の変更検出 glob 2 箇所と `git add`・レビュー追跡 Issue の全ページ走査・`review-issue-close-sync.yml` のマーカー解決（`.wikicommit/view/<lang>/<slug>.md` を追加で受け付ける。これが無いと view ページの追跡 Issue は Close できても `reviewed` に反映されない）・`remove_page.py`（view ページの翻訳探索と言語別 index からのエントリ削除）・`_root_outputs.py` と `init.py`（ディレクトリ作成）・`wikicommit-fix`（ページパス指定と公開 URL 逆引き）。

#### 本文中の相対リンク

view ページの本文が書く相対リンク（画像・添付）は、**公開後の姿でそのまま書く** — `../../assets/<name>`、つまり entity ページが書くのと同じ形になる。`content/<lang>/View/` は `content/<lang>/<Type>/` と同じ深さだからである。`convert_wikilinks.py` の `rewrite_relative_links()` は view ページに対して意図的に no-op にしてある（この関数が扱うのは 1 つのツリー内での深さの変化であり、`.wikicommit/view/` と `.wikicommit/entity/assets/` という別ルートの兄弟ツリー間の対応付けは別の問題である）。WikiLink（`[[Type/slug]]`・`[[View/<slug>]]`）はパスを持たないため影響を受けない。

#### 移行

**自動移行しない**（新旧混在を許容する）。view ツリー導入前の `derived_from` ページは `entity/` に残ったまま従来どおり動き、新規の合成のみが view ツリーへ行く。手で移す場合は `git mv` + `type:` 削除 + `kind:` 追加 + 参照側 WikiLink の書き換えで、`build_slug_type_index()` が view ページも索引するため、書き換え忘れた `[[custom/Practice/<slug>]]` は「ページが存在しません」ではなく `View/<slug>` に実在すると名指しする ERROR になる（TYPE_MISMATCH と同じ扱い）。**移行するとその Wiki のカスタム型ファイルが使われなくなる**（`check_installed_type_usage.py` が `UNUSED` として報告する）。kind に移した以上それが正しい状態だが、スキーマファイルを消すかは運用者の判断とする。

#### 根拠ページ（grounding set）の選び方

合成ページの根拠は、**`primary_lang` だけを広く検索し、本文を読む前に選び、既定 30 件で切る**。

| 段 | 動作 |
|---|---|
| 検索 | **`primary_lang` だけ**で `--limit max(40, N)`。テーマは `primary_lang` に翻訳してから検索する |
| 選別 | 候補を `build_survey_view.py --pages` で title・description・見出しに縮約し、**本文を読む前に**「テーマを主題として扱っているか」で選ぶ |
| 上限 | 既定 30。`--max-grounding N` で変えられる |

**上限にかかったことを見せる**（見えないと、上限で切った場合と元から少なかった場合が区別できず、`pattern` の「事例数と該当ページを必ず明示」とも矛盾する）。選別後に「主題として扱っているページ M 件のうち N 件を根拠にする」を本文を読む前に表示し、上限で切ったページは完了報告に列挙して `--max-grounding` での再実行を案内する。俯瞰モードでは着眼点の一覧に既定の上限と変え方を添え、各着眼点の元になったページ数も併記する。

**`primary_lang` だけを検索する理由**: 原文は必ず `primary_lang` で書かれており（`/wikicommit-generate` はソースの言語に関わらず `primary_lang` で書き、他言語のページは `translated_from` を持つ翻訳である）、`targets` の言語でヒットするのは原文の翻訳だけで根拠の情報は増えない。翻訳を根拠にすると、(1) 合成ページを別の言語の翻訳から書く、(2) 翻訳が原文より古ければ古い内容を根拠にする、(3) `derived_from` が翻訳を指すので原文の更新を `check_derivation_freshness.py` が検出しない。言い回しの違いは `--expand`（同義語・略語）が埋める。`/wikicommit-ask`・`/wikicommit-search`・`/wikicommit-quiz` は多言語で検索する（読者に自分の言語の版を返すのが目的であり、原文を根拠に書く synthesize とは目的が違う）。`primary_lang` 以外の言語で書かれた原文（手書き・途中で `primary_lang` を変えた Wiki）は候補から外れるが、まれであり受け入れる。

**選別の基準は新設しない**。「主題として扱っているか／すれ違いに触れているだけか」は `review-rules.md` の check 1 / check 4 と Pass 2c（§5.4）が使っている軸であり、判別がつかなければ落とす側に倒す（根拠が多いほどレビューが「どこかに似た記述がある」で PASS に倒れやすく、根拠の過大主張の方が危険である）。**`--max-grounding` を上げても選別は外れない**。

**上限を外さず 30 の 1 値にした理由**: 根拠ページ 1 件は Step 4 と Step 5.5 のレビューの両方に全文載り、`derived_from` に 1 行増える（陳腐化の報告も比例して増える）。上限は「既定で異常な量にならないための安全弁」として残し、関係の薄いページを落とす役目は選別に任せる。**`kind` ごとに既定値を変えない** — パイロット Wiki で上限を撤廃して書かれた `comparison` はエージェント 17 種を比べて数十件を根拠にしており、「`comparison` は 8 件」のような kind 別の値はこの 1 例で外れた。同じ例では、ページ間の食い違い（3 ページにまたがる記述）を指摘できたのは食い違う両方が根拠に入っていたからで、5 件ではほぼ確実に片方が落ちる。30 は現時点では実例 1 件からの推測であり、今後の合成ページの `derived_from` の件数を見て見直す。**無制限は用意しない**（`search_index.py` は `--limit` をそのまま SQL の `LIMIT` に渡すので `0` は 0 件を意味する。必要なら大きな数を指定する）。俯瞰の `--max-pages`（既定 300）とは兼用しない — 着眼点を探すために見るページ数と 1 枚の根拠にするページ数は桁が違う。合計 100 件前後を超えそうなときは本文を読む前にその旨を伝えるが、止めない。

**俯瞰モードが名指ししたページは候補に加える**（テーマの文言で検索し直すだけだと、「`TAG:` が 20 ページに出ている」ことを理由に提案した `pattern` の根拠が検索上位だけになる）。名指しされたページも同じ選別・翻訳除外・合成ページ除外を通す。

**合成ページは根拠から外す**（選別の前に適用する）。判定は `build_survey_view.py --pages` が frontmatter から行う。

**残した論点**: `derived_from` が増える分 `check_derivation_freshness.py` の報告が増えることは受け入れ、問題になったらページ単位にまとめる対処を別に扱う。合成ページが長くなることもこの変更では制限しない（1 ページ ＝ 1 レビューの設計上、読み通せない長さは人のレビューを止めるが、長さの目安は実際の分布を見てから決める）。既存の合成ページの `derived_from` は見直さない（遡及しない）。

#### 検討したが採らなかった案

- **層名を `analysis` / `synthesis` にする** — どちらも kind の一種としても読める（分析・合成）。兄弟ディレクトリはすべて「中身を名指す名詞」（`source/` / `entity/` / `schema/` / `assets/`）であり、`view` は DB の VIEW（導出・非権威・再計算可能）の含意が層の性質と一致し、成果物自体を名指す。`lens` は道具を指すので半歩ずれ、`study` は kind に読め、`derived` は形容詞で兄弟から浮く
- **kind をパスに出す** — 選択ミスがファイルの位置を動かす（上記）
- **結論を書く kind（`thesis` / `essay`）を作る** — 結論は定義上どの grounding ページも述べていない主張であり、`wikicommit-synthesize` の grounding 照合と正面から衝突する。特殊分岐が 3 箇所（照合モード・バナー・レビュー観点）必要になるのは設計に合っていない印である。由来の無い主張が要るなら、人間が `sources[].type: manual` で署名して書く（`author` と `created_at` を必須とし hash 検証を持たない既存の仕組み）
- **章・順序の原始概念（`chapter:` / `next` / `prev` / `position:`）を入れる** — 複数の kind を並べた文書は、既定では 1 ページの節として書けばよく、章を分けたい場合も「読む順に本文で列挙し `derived_from` に記録したもう 1 枚の view ページ」で足りる。順序付きの next / prev は Quartz に無く、作るなら過去いちばん壊れてきた領域（Quartz のナビゲーション）に手を入れることになる
- **JSON-LD に固定型（`schema:Article` 等）を出す** — 捻り出した型は何も表さない（上記）
- **Skill 名を `wikicommit-view` に改名する** — (1) `/wikicommit-view` は `/wikicommit-review` の部分文字列であり、紛らわしい（`wikicommit-serve` がその名前なのも同じ理由）、(2) Skill 名は動詞（行為）・成果物は名詞という対応が既にある（`wikicommit-generate` は entity ページを作るが `wikicommit-entity` ではない）、(3) "view" は動詞だと読み取り専用に読めるが、この Skill は書き込む、(4) `install.sh` の `SKILLS` 配列・`plugin.json`・README ×2・CLAUDE.md・docs の表（`test_skill_distribution_list_sync.py` が一致を強制）を変えるうえ、既にインストール済みの Wiki に `wikicommit-synthesize/` が孤児として残る（スクリプト名を据え置くのと同じ理由。§4.3）
- **既存の合成ページを自動移行する** — 上記「移行」

### 4.5.2 `.wikicommit/relations.yml` — ページ同士の関係

WikiCommit はソースごとにページを作り、既存ページとの照合は「型と slug が同じ」か、生成時の名前の完全一致に限られる。したがって**別のソースが同じ概念を別の名前で呼べば、ページはその分だけ分かれる**。文字列が重ならない同義語は機械的に照合できず、「同じか、上位と下位か」は人にしか決められない。決めたことを残さなければ検出は同じ組を何度も候補に挙げるので、`/wikicommit-relate` が人の判断を聞いて記録する（「紛らわしいが別物」も記録する）。

`/wikicommit-relate` が行うのは**記録まで**である。「同一」の統合（本文の生成・WikiLink の書き換え・吸収されたページの取り下げ）は下記「統合」の別操作であり、記録済みの「同一」を後から統合できる。系列（同じ名前の別の版）を記録する前の名前の修飾（改名）は下記「系列と改名」の節。

#### 関係の語彙はシソーラスの規格に揃える

| 関係 | ISO 25964 | SKOS | 置き場所 |
|---|---|---|---|
| `same`（同一） | USE / UF | `prefLabel` / `altLabel` | 最終的には**ページ側**（1 ページに統合し、他の名前は `aliases`）。それまでは関係ファイル |
| `broader`（上位と下位） | BT / NT（種類・部分・実例） | `broader` / `narrower` | 関係ファイル |
| `related`（関連） | RT | `related` | 関係ファイル |
| `distinct`（別物） | （無し） | （無し。Wikidata の P1889 different from に相当） | 関係ファイル |
| `series`（系列） | （無し） | （無し。Wikidata の P179 part of the series に相当） | 関係ファイル。`pages` を系列の順（古い順）に並べる |

**同一だけ単位が違う** — 1 つの概念の複数の名前であり、他の 4 つは別々のページの間の関係である。WikiCommit では「ページ ＝ 概念」「`title` ＝ `prefLabel`」「`aliases` ＝ `altLabel`」が既に成り立っているので、同一は最後にはページに畳まれる。

**「同じ名前の別物」は 2 種類ある。** 無関係な同名は `distinct`、同じ系列の別の版・別の回は `series` である。後者を `distinct` として記録すると系列であるという事実が失われる。系列は上位下位（系列を上位に置く `broader`）では表さない — 上位に置くページが要るが、系列そのものを述べるソースが無ければそのページは根拠の無いページになる。系列はページを持たず、`series` の項目だけで表す。

**判断は `same` に倒さない。** 上位と下位を同一として統合すると狭い方の独自の内容が薄まり戻しにくい一方、同一を別ページのまま置いても重複が残るだけで後から統合できる。Skill の質問はこれを明記する。

#### 関係をページの frontmatter に持たせない

- 関連・別物は対称な関係で、両方のページに書くと食い違う余地が生まれる
- 関係を足すだけでページの内容が変わった扱いになり、`reset_review_on_content_change.py`が `pending` に戻す。bookkeeping 側に足すなら Pass 3 の `action: update` がそれを保つ規則が要る
- 関係はページの中身ではなくページ同士の間の事実である（SKOS でも ConceptScheme は概念の外に立つ）

**view を関係の保存先にしない。** view は LLM が書き grounding 照合を受ける散文だが、関係は人の判断でありどのページの本文にも書かれていない。検出スクリプトが読むには構造化されたデータが要り、「別物」は読者向けの知識でもない。view は関係ファイルを**入力として使う側**に回りうる（`landscape` ＝ ConceptScheme）が、その読み手は今回入れていない。

#### 形式 — 1 ファイル・1 判断 1 項目・追記のみ

```yaml
# .wikicommit/relations.yml — トップレベルの YAML リスト
- relation: broader              # same | broader | related | distinct | series
  broader: DefinedTerm/tool-use  # broader のみ。上位のページ
  pages: [DefinedTerm/function-calling]
  decided_at: '2026-10-01'
  note: '...'                    # 任意。人の言葉での理由
```

| 論点 | 決定 | 理由 |
|---|---|---|
| 1 ファイルか分割か | **1 ファイル**（`.wikicommit/relations.yml`） | 追記中心なので同時編集の衝突は小さいと見る。衝突しても行単位の追記同士であり解消は容易 |
| 書き方 | `record_relation.py` が**テキストとして末尾に追記する**（YAML の round-trip で書き直さない） | 人が書いたコメントや手で直した項目を壊さない（`config.yml` を round-trip で書き直さないのと同じ理由。§3.3）。追記前にファイル全体がリストとしてパースできることを確かめ、できなければ何も書かない — 壊れた後ろに追記すると壊れ目が埋もれる |
| 識別子 | **`<Type>/<slug>`**（言語中立） | WikiLink と同じ形で、1 項目が全言語の版を覆う。パスは言語ごとに違う |
| 判断の修正 | 人が項目を編集・削除する | Skill は追加しかしない。判断を上書きする機械的な規則を置かない |
| `same` の残るページ・統合で足す別名 | **統合を実行したときに別の項目として追記する**（`merged_into` / `merged_aliases` / `merged_at`） | 判断の項目は判断した時点のもの、統合の項目は実行した時点のものであり、追記のみの規則を崩さない。下記「統合」の節 |

**最初の読み手は `check_name_collisions.py` の 1 つである。** どの関係であれ、同じ項目に挙がったページの組（`pages` と `broader`）は衝突候補から外れる。この読み手は 5 種類の関係をすべて同じように使う（判断済みの組を外す）ので、**どの種類も読み手の無い受け皿にはならない**。種類ごとに読み分ける消費者 — 公開側の「上位の概念」「関連する概念」のナビゲーション、JSON-LD の `skos:broader` / `skos:related`、統合 — は、それが入るときに足す。

#### 検出は警告であってゲートではない

候補は**タイトル×別名・別名×別名・型の違うタイトル×タイトル**の正規化後の一致（`normalize_name()`）で、言語ディレクトリごとに見る。`check_orphans.py` の `DUPLICATE:` に足さない — あれは `/wikicommit-merge` をブロックし、既存の Wiki がマージ不能になる。同じ型のタイトル同士は従来どおり `DUPLICATE:` の担当として外す。`/wikicommit-status` が 1 行（`Name collisions`）として数え、healthy の判定は止めない — 名前を共有する 2 ページが 1 つの概念かは人の判断であり、別物が名前を共有するのは正当だからである。行を増やすことは「常時点灯する行は読まれなくなる」に当たりうるが、判断を記録すれば消える所見であり、対処の経路（`/wikicommit-relate`）が行に書いてある点で常設の点灯とは違う。

#### 起動の設定

書き込み系なので `disable-model-invocation: true` と `agents/openai.yaml` の `policy.allow_implicit_invocation: false` を持ち、description に「明示的に頼まれたときだけ使え」「いつ使うな」を書く（`docs/DesignDoc-skills.md` §11.1）。非対話実行では何も書かない — すべての結果が人の答えに依るため。

#### 統合 — 「同一」を 1 ページに畳む

```
/wikicommit-generate --regenerate <残すページ> --merge <吸収するページ> [--merge ...]
```

| 論点 | 決定 | 理由 |
|---|---|---|
| 本文をどう作るか | **`--regenerate` を「複数ページ → 1 ページ」に広げる**。残すページを `action: update` で作り直し、吸収するページを文脈として渡す。ソースは全ページの和集合で、Pass 4 はその全件に照合する | Pass 1 / 3 / 4 を通常の再生成と共有するため（`--regenerate` を新規 Skill にしないのと同じ理由） |
| 何が統合を許すか | `merge_pages.py plan` が、`same` の項目が残すページと吸収する各ページを組で挙げていることを確かめる。無ければ止めて `/wikicommit-relate` を案内する | 統合は人の判断の実行であって、機械の判断ではない |
| どちらを残すか | 人が名指しする（最初のページ） | 残る slug と title は人の選択である |
| 統合由来の別名 | 吸収したページの title・aliases と、その翻訳の title。`relations.yml` に**統合の項目**（`relation: same` ＋ `merged_into` ＋ `merged_aliases`）として残す | 下記 |
| WikiLink | `rewrite_merged_links.py` が `merged_into` をたどって `[[Type/old]]` → `[[Type/new]]` に書き換える（本文と `properties:` の値。翻訳ページも含む） | 公開時に張り替えると「removed ページへのリンクはブロック」の非対称に例外を作る |
| 吸収したページ | `remove_page.py --reason merged --merged-into <残すページ>`。翻訳も同じ値で下ろされる | 既存の削除経路をそのまま使う |
| 書き換えたページのレビュー状態 | **保つ** | 変わったのはリンクの指す先だけであり、それは人が同じ概念と判断したページである。周りの記述は変わっていない |
| 書き換えたページの AI レビュー記録 | **失効と数えない**。`check_review_coverage.py`（と公開時の `convert_wikilinks.py`）は、standing な記録の `page_content_hash` が一致しないとき、`relations.yml` の統合の項目ごとに現在の本文の `[[Type/new]]` を `[[Type/old]]` に**全置換で**戻した版のハッシュも試し、一致すれば `STALE_REVIEW:` を出さない。統合が連鎖していれば（A → B → C）その先まで組を作る | レビュー状態を保つのと同じ理由。記録の形式（`page_content_hash`）は変えない。書き換えたページを `pending` に戻すと、人が「同じ概念」と決めたことの結果としてレビューが増える |
| 吸収したページの open な追跡 Issue | Skill は閉じない。完了報告で `/wikicommit-merge` の後に閉じるよう案内する | 生成側は Git・GitHub を操作しない |

**統合由来の別名は、ソースの文字列ではなく人の判断に立っている。** Pass 4 は「今回足した別名」を、そのソースが逐語でその名前を書いているかで照合する（§4.1「`aliases`」。`review-rules.md` の Added aliases）。統合由来の別名にはそれを書くソースが無くて当然なので、照合すれば正しい別名が `HALLUCINATION` で落ちる。そこで**区別は機械的に行う**: `merge_pages.py plan` が `ALIAS:` 行として名前を決定論的に出し、Pass 4 に渡す「今回足した別名」からそれを除く（`references/pass4-review.md` step 1）。同じ名前の一覧を統合の項目の `merged_aliases` に残すので、後から見ても「この別名は統合由来である」が分かる。Pass 3 の「1 言語 1 つまで」もソースが支える別名の数を抑える規則なので、統合由来の別名には掛けない。`review-rules.md` は統合を知らない — 規則が見るのは orchestrator が渡す一覧であり、何を渡すかの側で区別している。

**統合の項目は判断の項目とは別に追記する。** 判断の項目を書き換えないので、ファイルは追記のみのままである。`check_name_collisions.py` はどちらの項目も「判断済みの組」として読む（どのみち吸収したページは `status: removed` で検出から外れる）。

**既知の限界: 統合前から残すページと吸収したページの両方にリンクしていたページは `STALE_REVIEW:` に出る。** 試すのは統合 1 件ごとの全置換 1 通りだけで、部分的な置換の組み合わせは試さないため、元から `[[new]]` だった箇所まで `[[old]]` に戻した版は記録時の本文と一致しない。再レビューで消える。

**既知の限界: 吸収したページの URL は消える。** `status: removed` のページは公開サイトにビルドされず、リダイレクトも置かない。統合由来の別名は残すページの `aliases` に入り、別名はサイト直下のリダイレクトになる（`alias-redirects`）ので、古い**名前**からは残すページへ着くが、古い**スラッグの URL** には着かない。外部からのリンク・ブックマークは切れる。

**他にも残るもの**: 吸収したページを `derived_from` に挙げる view ページは書き換えない（パスはソフト削除で残る。作り直すかは人が決める）。残すページの翻訳は原文が変わったので `check_translation_status.py` が `STALE` として報告し、`/wikicommit-translate` が追随する。

#### 系列と改名 — 同じ名前の別の版を年で修飾する

`/wikicommit-relate` で `series` を選ぶと、記録の前に各版の名前を同じ規則で修飾する（`rename_page.py`）。

| 論点 | 決定 | 理由 |
|---|---|---|
| 系列の表し方 | **ページにしない**。`relations.yml` の `series` の項目だけ（`pages` は古い順） | 系列そのものを述べるソースが無ければ、系列ページは根拠の無いページになる |
| 修飾 | **年**。slug は末尾に `-<年>`、title は末尾に `（<年>）`（`ja` / `zh`）か 半角スペースと `(<年>)`（他の言語） | 型をまたいで使える唯一の修飾である（報告書番号・版・回は型によって有ったり無かったりする） |
| 規則の置き場所 | 新しい版を作るときは Pass 2c（`references/pass2c-entities.md`）、既存のページを直すときは `rename_page.py` | 規則は型をまたぐ。インストール済みの型テンプレートは init 後に編集しない |
| 修飾の無い既存ページ | **改名する**（系列ページへ転用しない） | 系列をページにしないため、転用先が無い |
| 改名の仕組み | **統合の部品を使う**。新しい slug のページを全言語で書き、古いページを `removed_reason: merged` ＋ `merged_into` で下ろし、`relations.yml` に `relation: same` ＋ `merged_into` ＋ `renamed_at` の項目を追記し、`rewrite_merged_links.py` でリンクを書き換える。ソース管理ファイルの `generated_pages` も新しいパスに向け、型の index を作り直す | 改名は「古い識別子を新しい識別子に畳む」統合の特殊な場合であり、リンクの書き換え・翻訳の追随・書き換えたページの AI レビュー記録を失効と数えない扱い（上記「統合」）がそのまま当てはまる。`removed_reason` に値を足すと、それを読む全経路（検証・削除・公開）に分岐が要る |
| 改名したページのレビュー状態 | **title を書き換えたページは `pending` に戻す**（`reviewed_by` も消す。翻訳も同じ）。slug だけが変わり title が変わらないページは触らない（翻訳は `translated_from` だけを書き換える） | title は内容であり、人の確認は読んだ時点の title に掛かっている（`reset_review_on_content_change.py` と同じ原則）。slug はファイル名であり、人が読んだ本文ではない |
| slug が既に年を持つページ | title だけを修飾する。`--base-title` で年を足す前の名前を言語ごとに指定できる | 後から作られた版は slug に年を持ち、title に報告書番号を持つことがある。版ごとに違う語を落として名前を揃えるため |
| 改名したページの AI レビュー記録 | **古い slug の記録を新しいページの記録として読む**。記録は古いパスの下に残す（記録は判定したページのパスを本文に持ち、ファイルは不変であるため移さない）。`check_review_coverage.py` と公開時の `convert_wikilinks.py` は、`relations.yml` の `renamed_at` 付きの項目をたどって（改名の連鎖も含めて）古い slug の記録ディレクトリも読む。title が変わっていれば記録時の本文と一致しないので `STALE_REVIEW:`（理由に改名前の slug を添える）になり、公開側には表示しない。slug だけが変わった（title は既に年を持っていた）なら、原文ページの判定はそのまま立つ。翻訳ページは `translated_from` が新しいパスに変わるので判定は失効し（`STALE_REVIEW:`）、翻訳としても陳腐化と報告される（`check_translation_status.py` の `STALE:`）— `/wikicommit-translate` で更新する。`/wikicommit-review` を新しいページに回せば、新しい記録が standing になって消える | 改名で変わったのは slug と title だけで本文は変わらず、Pass 4 の出典照合の結果は失われていない。記録を読まないと、改名したページは `UNREVIEWED:` に出て「出典照合を一度も受けていない」ように見え、`RISKY:` の手がかり（attempts・findings）も消える。一方 title は内容なので判定は失効として扱う（レビュー状態を `pending` に戻すのと同じ原則）。翻訳ページの判定を改名の連鎖越しに生かす（`translated_from` のパスも戻して比べる）ことはしない — slug が変われば翻訳はどのみち陳腐化と報告され、訳し直しで判定も書き直されるので、生かしても「AI レビューは立っているが翻訳は古い」という食い違った表示になるだけである。改名後に `/wikicommit-review` を回すよう案内するだけにする案は、案内を読まなかった Wiki で同じ見え方が残るため採らない。統合（`renamed_at` の無い項目）はたどらない — 残すページは再生成され、Pass 4 が新しい記録を書く |
| Pass 2c で新しい版を作るとき | 新しい版を年で修飾し、ソースが逐語で使う修飾の無い系列名を `aliases` に残す。既存のページは改名しない | 修飾の無い既存ページと別名が一致して名前の衝突に挙がり、`/wikicommit-relate` で人が `series` と決めるまで残る。生成時に既存ページを改名すると、人の判断なしにページの名前が変わる |

**既知の限界**: 古い slug の URL は消える（統合と同じ）。改名したページの翻訳は原文が変わったので `STALE` として報告される。`.wikicommit/groups/<Type>.yml` が古い slug を挙げていれば `rename_page.py` は `GROUPS:` 行で知らせるだけで書き換えない（グループファイルは `/wikicommit-organize` と人が書くもの）。同じ年に 2 つの版があれば年では区別できず、人が名前を決める。

#### 残した論点

- **公開側の読み手**（ナビゲーション・JSON-LD）は無い

### 4.5.3 `.wikicommit/groups/<Type>.yml` — 型の下のページのグループ分け

大きくなった型は、Type 別 `index.md` でも Explorer の左ペインでも 1 列に並ぶだけで一覧として読めないので、型の中をグループに分ける。他の仕組みはこの用途に合わない — `tags` は型をまたいで括るためのもので語彙が揃わず（§4.1）、`DefinedTerm` には Schema.org の下位型がほぼ無く（§5.3）、`inDefinedTermSet` は置いておらず（§5.2）、view の `kind: landscape` は合成ページであって分類ではない。

**分類はページの外に置く。** 主な用途は「ページが増えてから分類する」ことであり、分類をページの frontmatter に書くと、40 ページを分類した時点で 40 ページすべての内容が変わったことになり、`reviewed` のページは `pending` に戻って追跡 Issue が立ち直る（`reset_review_on_content_change.py`。`tags` は内容側のフィールド）。分類はページの内容ではなく並べ方の問題である。

```yaml
# .wikicommit/groups/DefinedTerm.yml
groups:
  practice:
    label: {ja: 実践・手法, en: Practices}
    criterion: "読者が行う手順や工夫を述べるもの"
    pages: [vibe-coding, spec-driven-development]
  phenomenon:
    label: {ja: 現象・問題, en: Phenomena}
    criterion: "システムや利用者に起きることを名指すもの"
    pages: [context-rot]
unclassified_label: {it: Non classificati}   # 任意。ja / en は組み込みの見出しがある
```

| 項目 | 決定 | 理由 |
|---|---|---|
| 置き場 | `.wikicommit/groups/<Type>.yml`（custom 型は `custom/Decision.yml`） | `.wikicommit/schema/` は LLM から「追加のみ可・既存編集不可」で、何度も書き直す分類と性質が合わない。パスは `type:` から導出し、走査しない（§5.1 と同じ） |
| 振り分けの単位 | slug | slug は言語中立なので 1 ファイルで全言語に効く。翻訳ページは原文と同じグループに入る |
| 表示名 | 言語コード → 文字列（`site_description` と同じ形）。無い言語ではキー | |
| `criterion` | 1 文で残す | 次に `/wikicommit-organize` が未分類ページを振り分けるときの判断材料。無いと前回の意図が失われる |
| 1 ページの所属 | 1 グループまで（重複は検証エラー） | 複数所属を許すと Explorer と index に同じページが 2 回現れる |
| キー | 英小文字・数字・ハイフン | Explorer の仮想フォルダの識別子になる。Quartz は公開時に小文字化するので、大文字小文字だけ違うキーは衝突する |
| 不正なファイル | 全読み手が「ファイル無し」として扱い、`check_groups.py` が `ERROR:` を出す | 書き損じ 1 つでビルドを止めない |
| 配布 | テンプレートに置かない。`_root_outputs.py` に `origin="skill"`・`update="skip"`・`may_be_absent=True` で登録 | 空の受け皿を配らない。init が作らないので、選択的な `git add` の列挙が存在しないパスで中断しないように |
| view ページ | 対象外 | Type を持たない（§4.5.1） |

#### 読み手は 3 つ、ページを書き換えるものは無い

| 読み手 | 何をするか |
|---|---|
| `rebuild_index.py` | グループファイルを持つ型の `index.md` を `## <表示名>` で分け、最後に未分類の見出しを置く。表示名は index の `lang` で選ぶ。ページが 1 件も無いグループは見出しごと省く |
| `convert_wikilinks.py` | `content/wikicommit-groups.json` を書く（公開 slug → グループのキー、言語ごとに解決した表示名）。グループファイルが 1 つも無ければ書かず、前回のビルドが残したものは消す |
| `check_groups.py` | `/wikicommit-status` に型ごとの未分類・stale の件数を、`/wikicommit-organize` に未分類ページの一覧を返す |

**分類しても `.wikicommit/entity/` のページは 1 バイトも変わらない**（`tests/test_groups.py` が固定する）。変わるのは各言語の `index.md` だけで、これはもともとビルド生成のナビゲーションページである。

#### Explorer の仮想フォルダ — frontmatter への注入ではなく別ファイル

publish 時に `content/` のページの frontmatter へ所属グループを注入して Explorer に読ませる形は**成立しない**。Explorer のツリーはブラウザで `contentIndex.json` のエントリから組み立てられ（`wikicommit-explorer.inline.ts`）、Quartz の content index が運ぶのは slug・title・links・tags 等の固定のフィールドだけである。注入したフィールドは Explorer に届かず、消費者のいない受け皿になる。

そこで `convert_wikilinks.py` が `content/` の直下に `wikicommit-groups.json` を書き、Quartz の Assets emitter が `public/` へコピーする。Explorer はこれを 1 回だけ取得し、該当するページを**ツリー上の位置だけ**型フォルダの下の仮想フォルダへ移す。ノードのデータ（＝リンク先の slug）は変えないので、**公開 URL は変わらない** — 出力先のフォルダ自体を分ける案は、分類を変えるたびに URL が変わり外部からのリンクが切れるため採らない。仮想フォルダの slug 区画は `#group-<key>` で、`#` は Quartz の slugify が落とす文字なので実在のページ・フォルダと衝突しない。仮想フォルダはリンクにせず（対応するページが無い）、表示中のページを含むときは開いた状態で描画する。マニフェストが無い（404）のは通常の状態で、そのときツリーは従来どおりに組み立てられる。キーは `convert_wikilinks.py` の `_quartz_slugify_segment()` で公開 slug に揃えて書くので、クライアント側は文字列を比べるだけで済む。

#### 未分類のページ

`/wikicommit-generate` はグループファイルに**書かない**。新しいページは未分類として表示され、溜まったら `/wikicommit-organize` をもう一度実行する。生成のたびに LLM が利用者のファイルを書き換え、しかも `criterion` の解釈がページごとにぶれるため、その場で追記する案は採らない。`/wikicommit-status` はグループファイルを持つ型についてだけ未分類の件数を出し、閾値は置かない（何件から見直すべきかの根拠が無い）。グループファイルを持たない型について何か出すと全型が常に点灯する。

#### 実装時に決めたこと

- **1 回の `/wikicommit-organize` で振り分けるのは未分類ページ 30 件まで。** 人が 1 枚の表として読み、1 件ずつ確かめられる量に抑える。残りは次の実行で拾う
- **型で絞る引数を `build_survey_view.py` に足さない。** `check_groups.py --type` が未分類ページのパスを返し、それを既存の `--pages` に渡せば足りる。`--max-pages` の被リンク順の切り捨ても受けない
- **グループファイルに載っているのに実在しない slug** は `check_groups.py` が `STALE_MEMBER:` として報告し、次の `/wikicommit-organize` で人の承認を得て落とす。読み手（index・Explorer）は黙って無視する
- **`/wikicommit-organize` は自前でブランチと PR を作り、auto-merge しない**（`wikicommit-schema-propose` / `wikicommit-update` と同じ）。`index.md` をディスク上のページから組み直してコミットするので、`.wikicommit/entity/` に未コミットの変更があるときは始めない — 残っていると、PR に含まれないページへのリンクが既定ブランチの index に載る

**既存リポジトリへの遡及は行わない。** グループファイルが無ければ index・公開サイト・`/wikicommit-status` のどれも変わらない。

### 4.6 LLM レビューのフィードバック形式（エージェント間 JSON）

エージェント間でのみ使用。**この JSON そのもの**は PR コメントにも Git にも残さない。

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

本節の JSON そのものは**エージェント間限定**で、フィールド追加は自由である。ただし、そこから `source_quote` を落として**射影したもの**が `.wikicommit/review/**/*.md` の frontmatter に記録され（§4.8）、そちらは**永続化フォーマット**として後方互換の対象になる。本節へフィールドを足すときは、射影側の既に書かれた記録と食い違わないかを確かめる。

**`observations`**: `result: PASS` のまま、FAIL に至らない気づきをプレーン文字列の配列で返してよい（`review-rules.md` Part 1 が定める）。`issues` の中身を増やしも減らしもしない（`page_at_fault: "other"` のエントリは従来どおり `issues` に載る）。記録への落とし方は §4.8。

#### `CONTRADICTION` が指す 3 種類

`type: CONTRADICTION` は性質の異なる 3 つを担う。**何と矛盾しているかの判別は `source_file` の値で行う**。`page_at_fault` は 3 つ目（ページ間矛盾）のエントリにのみ現れる。

| 何と矛盾しているか | `source_file` | 扱い |
|---|---|---|
| そのページ自身のソース文書（帰属の取り違え・命名と発明の混同を含む） | ソース文書のパス／URL | **FAIL** → 再生成 |
| 同じページの**別のソース**（ソース同士が食い違っている） | 採るべきだった側のソースのパス／URL | **FAIL** → 再生成 |
| 同じ Wiki の**別のページ** | 相手ページ（`.wikicommit/entity/` 配下）のパス | `page_at_fault` で下記のとおり分岐 |

3 つ目のページ間矛盾は、**どちらのページが誤っているか**でさらに分かれ、この向きは `page_at_fault` が担う。`under-review`（レビュー中のページが誤っている）なら通常どおり FAIL して再生成する。`other`（相手側が誤っていそう）なら **FAIL にしない** — Pass 4 は 1 ページをそのページ自身のソースに対して再生成するループであり、相手ページのソースも持たなければ相手ページへの権限も持たないため、Completion Notice への報告に留める（`docs/DesignDoc-pipeline.md` §7）。`other` のエントリだけが見つかった場合、`result` は `PASS` であり（エントリ自体は `issues` に載せる）、ページはそのまま書き出される — ここで FAIL にすると、正しいページを再生成しては同じ指摘を受けることを繰り返し、再試行上限で `failed_pages` に落ちて最終的に書き出されない。

`source_file` を「何と矛盾しているか」の判別子にしたのは、`.wikicommit/entity/` 配下のパスかどうかで機械的に分かれ、曖昧にならないため。一方で**どちらのページが誤っているか**は `source_file` からは分からない — どちらの向きでも入る値は相手ページのパスで同一であり、他のどのフィールドも向きを表さない — ため、ページ間矛盾のエントリに限り `page_at_fault` を置く。この JSON はエージェント間限定であるため、**JSON 側のフィールド追加には**後方互換の制約は無い。ただしその射影はディスクと Git に残る — **記録側は後方互換の対象である**。本節にフィールドを足すこと自体は自由だが、それを記録に載せるかどうかは `record_review.py` の射影リスト（`FINDING_FIELDS`）を明示的に変えたときにだけ起こり、既存の記録ファイルと食い違う形にはならない（§4.6 冒頭）。

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

### 4.8 `.wikicommit/review/` レビュー記録のフォーマット

レビューの判定（`wikicommit-generate` Pass 4 の検査を含む）を、ページ単位の記録としてディスクに残す。記録が無いと、1 回目でクリーンに通ったページと、ハルシネーションを指摘されて 2 回目で通ったページがディスク上で同一に見え、残るのは「レビューが救えなかった記録」（`failed_pages`）だけになる。全数の機械検査を記録して勘定に入れることは、読者向けの `reviewed` を弱めずに、実際にやっていることを正確に表す手段である。

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

- **read-modify-write が消える**。このリポジトリは YAML の round-trip で 1 度やられている（`config.yml` のコメント記入例が `yaml.safe_load` + `dump` で全部落ちる）。作成のみなら round-trip 自体が発生しない
- **git のマージが自明**。別ブランチが別レビューを足しても別ファイルなので衝突しない
- **複数観点のレビューエージェントが自然に表現される**（3 観点 ＝ 3 ファイル）
- **人が読める・人が書ける**。較正（人間の指摘と機械の指摘を突き合わせる）には、人が機械のレビューを読める必要がある

ファイル名は `<YYYYMMDD>-<HHMMSS>-<kind>.md`（`<kind>` は `ai` / `human`）。`wikicommit-merge` の一時ブランチ `wikicommit/merge-<YYYYMMDD>-<HHMMSS>` に前例がある。**モデル ID をファイル名に入れてはならない** — 実行中モデルは `claude-opus-5[1m]` のように角括弧を含みうるため、glob を壊す。同一秒の衝突は実用上起こらない（Pass 4 は LLM 呼び出しを挟んで逐次実行される）が、`record_review.py` は 2 件目に `-2` を付す — 上書きは契約上あり得ない。

**ページが削除されても記録は残す**（履歴であるため）。したがって `.wikicommit/review/` は既存ページの厳密なミラーではない。**書き出されなかったページ（`failed_pages`）のディレクトリも作られる** — これが最も価値のある記録なので、これは仕様である。

**`.md` で安全であることは確認済み**: 各所の `rglob("*.md")` はすべてスコープされている（`collect_entity_pages()`・`convert_wikilinks.py`・`check_raw_html.py` / `validate_frontmatter.py` / `check_wikilinks.py`・`markdownlint-cli2 <変更 .md ファイル>`）。唯一の実害候補だった `lychee` も `wikicommit-merge` がパス引数付きで呼んでいる — 無スコープだと記録内の `source_file` URL を毎マージ再検証しに行くところだった。`tests/test_review_record_tree.py` がこの前提を回帰テストとして固定する。

**スタンプは同じディレクトリの最新記録まで切り上げる** — 壁時計は単調ではない（時計を後方へステップさせるコンテナでは、連続して書いた 2 件が逆順のタイムスタンプを得て、古い方が最新として読まれる。記録は不変なので後から気づく契機が無い）。`allocate_record_path()` は、そのディレクトリの最新記録より古いスタンプを受け取ったらそのスタンプまで切り上げてから採番し、stderr に `WARNING:` を出す。ファイル名の形も `record_sort_key()` も変わらない。

- **採番はファイル名ではなくスタンプを見る**（`next_seq()`）。`kind` はソートキーに含まれないので、`ai` 記録の隣へ切り上げた `human` 記録が `<stamp>-human.md` という空き名を取ると 2 件が同値になり、順序がファイルシステム依存に戻る。次の枠は「そのスタンプを持つ既存記録の最大 seq + 1」で決める
- 代償は、切り上げた記録のファイル名が最大でステップ幅ぶん古くなることだけである（日付は記録自身の `reviewed_at` が持つ）
- テストだけを直す・逆転を報告するだけ、の形は採らない（製品側の順序が直らない）
- `record_run.py`（`.wikicommit/run/`）も同じ形で切り上げる。あちらは `run_sort_key()` がローテーションの削除対象も決め、4 つの Skill の実行を 1 ディレクトリに束ねるので、同値とファイル名の再利用がより起きやすい

#### フォーマット — frontmatter ＝ 機械可読 / 本文 ＝ 散文

`.wikicommit/source-policy.md` / `.wikicommit/entity-policy.md` と同じ分担を採る。

```yaml
---
page: .wikicommit/entity/ja/Person/yamada-taro.md
kind: ai                      # ai | human
stage: generate-pass4         # generate-pass4 | review-skill | synthesize-step5.5 | translate-check | issue-close
model: "claude-opus-5[1m]"    # kind: ai のとき。ランタイムの報告どおりに書く
reviewer: "octocat"           # kind: human のとき。GitHub login（`reviewed_by` と同じ理由で表示名ではない）
reviewed_at: "2026-09-05"
skill_blob: "a1b2c3d4e5f6..." # .wikicommit/review-rules.md の blob hash
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
 Pass 4 が PASS と判定しながら述べた観察が入り、無ければ空）
```

**`findings` は本文ではなく frontmatter に置く**。本文に置くと集計スクリプトが散文をパースすることになり、決定論的に扱えるものをパースに委ねることになる。本文は「構造化された居場所が無い散文」専用である。

**`model` と `reviewer` は該当する側だけを書く**。両方を常に置くと、片方は必ず空のまま残る。`reviewer` は経路によっては空になる（`wikicommit-review` はローカル実行であり、認証済みの GitHub login を得る手段が無い。§4.1 の `reviewed_by` と同じ理由）ため、その場合はキーごと省く。`skill_blob` も同様で、`stage: issue-close` には従うべきレビュー規律のファイルが無い（人間が読んだ）ため付かない。

**`skill_blob` が指すのは `.wikicommit/review-rules.md` である**（レビュー規律の唯一の正本であり、「どの版の指示が判定したか」を表す）。`rules_version` とは役割が違い、冗長ではない:

| | 何のため | 誰が扱うか |
|---|---|---|
| `rules_version` | **読んだことの検証** | サブエージェントが返す JSON に echo する |
| `skill_blob` | **どの版が判定したかの記録** | orchestrator が計算して記録に書く |

blob hash は echo させられない（エージェントが計算できない）し、`rules_version` だけでは bump 忘れで嘘の記録になる — その場合 `rules_version` は嘘をつくが blob hash は真のままである。

#### `kind: ai` の本文 — FAIL に至らない観察

`wikicommit-generate` Pass 4 と `wikicommit-synthesize` Step 5.5 は、サブエージェントが返した `observations`（§4.6）を `record_review.py --note-file` で記録の**散文本文**に 1 行 1 件で書く。1 回目で通ったが指摘を受けたページと、何も言われずに通ったページが、ディスク上で同一に見えないようにするためである。`wikicommit-review` はサブエージェントを持たず本文はレビュアーの一言が占めるので、観察は目の前のレビュアーへの報告になる（`review-rules.md` にもそう書いてある）。

- **`issues[]` には載せない** — `check_review_coverage.py` の `RISKY:` は findings が 1 件以上あれば挙げるので、非ブロッキングの観察を入れると抜取の候補が膨らむ。散文本文なら同スクリプトは読まない
- **機械可読にしない**（`severity: blocking | note`・frontmatter の `observations:` 配列のどちらも置かない）。数えたい消費者が無く、観察用の `type` 語彙も無い（`FINDING_FIELDS` は欠陥のためのスキーマである）。数えるには `stage: generate-pass4` の記録のうち本文が非空のものを数えればよい（本文を持つ他の経路は `kind: human` と `stage: issue-close` だけ）。観察が読み切れないほど多いと分かったときに再検討する
- **2 つの限度**: 網羅性は裏口から戻さない（「ソースにはあるがページに無い」は観察にもならない）。無ければ書かない
- 本文は `--note` ではなく `--note-file` で渡す（サブエージェントが返す自由記述をシェルのコマンドラインに載せない）

#### `source_quote` は落とす

`source_quote` は**ソース文書の逐語抜粋**である。ページ本文で引用することと、Wiki 全体にわたって系統的に抜粋を蓄積・保管することは別の行為であり、`sources[].license`が ShareAlike や all-rights-reserved を記録している以上、この Wiki は「ソースの利用条件は事実確認の対象である」という立場を既に取っている。同じ理屈が自分の記録にも掛かる。

落としても目的は達成できる — `source_file` + `source_lines` があれば後から見に行ける。あわせて、**ソース文書の生テキストが記録に入る唯一の経路が消える**ので、プロンプトインジェクションの面積とファイルサイズも同時に縮む。

**落とすのは `record_review.py` の側で行う** — 呼び出し側が渡してきても落ちる形にしてあるので、保証が指示の遵守に依存しない。

**既知の限界**: `type: url` ソースのフェッチ結果は `.wikicommit/.cache/` に置かれ `.gitignore` されているため、引用の復元には再フェッチが要り、ソースが変わっていれば行番号は合わない（下記 `reviewed_sources` があれば「合わない」ことは分かる）。

#### `page_content_hash` — コミット SHA ではなく内容ハッシュ

レビューが有効かどうかは「そのページのどの版を見たか」で決まる。生成直後はページがまだコミットされていないため、コミット SHA は取れない。

**内容ハッシュを採る理由はそれだけではない**。`reset_review_on_content_change.py`が既に「6 フィールド（`generated_at` / `generated_by` / `generated_with` / `review_status` / `reviewed_by` / `sources`）を無視した内容比較」というルールを持っている。**同じ無視リストでハッシュを取れば、「このレビューは今のページにまだ有効か」が決定論的に判定できる**。`record_review.py` はこのリストを `reset_review_on_content_change.py` から **import する**（複製しない）— 2 つの写しは drift し、drift は「誤った鮮度を黙って報告する記録」として現れる。

**捨てられたページ（`result: discarded`）は `page_content_hash: ""` とする**。ページがディスクに書かれないためハッシュが取れない。**空のハッシュは「ページが書かれなかった」を意味する**と定義し、失効判定はこれをスキップする。

#### `reviewed_sources` — レビュー時点のソース版（フルリスト）

レビューの有効性は (ページの版, **ソースの版**) の組で決まる。ページが変わっていなくても、ソースが変わったら判定は無効になる。

ダイジェスト 1 本ではなくフルリストを採る理由が 1 つある — **`check_ingest_freshness.py` は `type: url` を監視しない**（§4.3。URL の鮮度確認は `/wikicommit-generate <url>` の再実行が唯一の手段）。つまり URL ソースについては、**レビュー記録がその時点のソース版を捉える唯一の場所になる**。

view ページは `derived_from[].source_commit` を同じ位置に記録する。ページ frontmatter の `sources[]` との重複に見えるが、あちらは現在の値、こちらは**レビュー時点のスナップショット**であり、翻訳ページの `source_commit` と同じ関係になる。

`result: discarded` ではページが存在しないため、`record_review.py` は `--sources-from <ソース管理ファイル>` から `reviewed_sources` を組み立てる。これが無いと、最も価値のある記録が「どの版のソースがそれを生んだか」を何も言えなくなる。

**翻訳ページ（`stage: translate-check`）は `{path: <translated_from>, source_commit: <source_commit>}` の 1 要素を持つ**。翻訳ページは `sources` を持たず、照合した相手は原文ページだからである。`translated_from` は単一の文字列で `source_commit` は隣のトップレベルフィールドにあるので、1 要素に組み立てる（旧 `.wikicommit/wiki/` 接頭辞は `normalize_entity_prefix()` を通す）。`source_commit` が空文字列（原文が未コミット）でもそのまま記録する — 判定自体は成立しており、どの版と照合したかを言えないだけである。**`translate-check` の `discarded` は `reviewed_sources` を空で持つ** — 訳し直しで上限を超えた場合ディスクにあるのは古い翻訳であり、その `source_commit` は今回照合した原文の版ではない。

**原文の更新は `STALE_REVIEW:` ではなく `check_translation_status.py` の `STALE` が知らせる**。`stale_reasons()` が比べるのは記録の `reviewed_sources` と**そのページ自身の frontmatter の今の値**であり、翻訳ページの `translated_from` / `source_commit` は再翻訳したときしか変わらない — 原文だけが更新されても両側は同じ値のままで、再翻訳されれば新しい `translate-check` 記録が最新になる。原文が変わったとき「訳し直すべき」と「照合が古い」は同時に成り立ち対処も同じ（`/wikicommit-translate`）なので、2 つの行に分けない。翻訳ページの `reviewed_sources` は失効の検出ではなく、照合した原文の版の記録である。翻訳の本文を `/wikicommit-fix` で直した場合は、既存の `page content changed` で `STALE_REVIEW:` に出る。

#### findings は全ラウンドを、フラットに `round:` 付きで持つ

Pass 4 は最大 `generate.max_retries` 回まわり、**各ラウンドで別の指摘が出る**。最終ラウンドの findings だけを記録すると、**1 回失敗して直ったページが `findings: []` になり、いちばん欲しい信号が消える**。

`rounds:` の入れ子ではなくフラットにするのは、集計（総件数・`type` 別・最大 round）がフィルタ 1 回で済むため。`attempts` は別に明示する — 最終ラウンドに findings が無い場合、`max(round)` からは復元できない。

#### 書き込む 5 経路

| 経路 | `stage` | 備考 |
|---|---|---|
| `wikicommit-generate` Pass 4 | `generate-pass4` | **PASS と `failed_pages` 行きの両方**（後者こそ本命） |
| `wikicommit-review` Step 5 | `review-skill` | 実行者に応じて `kind` を `ai` / `human` に振る |
| `wikicommit-synthesize` Step 5.5 | `synthesize-step5.5` | 同じ §4.6 JSON を返す（Pass 4 に倣う） |
| `wikicommit-translate` Step 4 item 5 | `translate-check` | 翻訳ページを原文ページと照合する（下記） |
| `review-issue-close-sync.yml` | `issue-close` | 下記。Close した本人の最新コメントが記録の本文になる |

**`review-issue-close-sync.yml` が人間レビューを記録することが要である**。経路 A は「Claude Code のセッションを持たない人が GitHub の Web/モバイルから Close できる」ための経路であり、**ローカルスクリプトが 1 つも走らない**。記録しないと `kind: human` は `/wikicommit-review` 経由でしか生まれず、人が Close していても集計スクリプトは人間レビュー 0 件と報告する — 「記録が無い」より悪い誤った記録である。同ワークフローは `review_status` を書く**同じコミットで**記録ファイルも書く — 片方だけ成功する状態が存在しない。

5 つ目の経路 `translate-check` は、翻訳ページを原文ページと照合する。

**`wikicommit-fix` は含めない** — あれはレビューではなく編集である（ただしそれが作る失効は `check_review_coverage.py` の `STALE_REVIEW:` が可視化する）。

#### 経路 A — Close コメントが記録の本文になる

`review-issue-close-sync.yml` は、追跡 Issue を **Close した本人（`closed_by`）の最新のコメント 1 件**を記録の散文本文として `record_review.py --note-file` に渡す（経路 B の `--note` と同じ産物を、主経路でも残す）。

- 本人に絞る — 「Close 直前の最後のコメント」は他人のコメントを取り違え、「全コメントの連結」は議論まで混ざる。login は `Resolve closer identity` ステップが既に取得済みで、空なら job を落とすので、記録ステップでは必ず非空である
- **本文はシェルのコマンドラインに一度も載せない**。API のレスポンスをファイルに落とし、埋め込みの Python が login（環境変数から読む）で選別してもう 1 つのファイルへ書く。`--note` や step output には載せない（`${{ }}` で再展開される経路ができる）
- **「最新」は API の並び順に委ねない**。Issue 単位のコメント API は `sort` / `direction` を黙って無視し ID 昇順で返すので、`--paginate` で全件を取り、`created_at`（同秒は `id`）の最大をこちら側で選ぶ
- コメントが無いまま Close されたら本文なしの記録を書く（沈黙して閉じるのは正常）
- **このステップは実行を落とさない** — 取得・選別の失敗は `::warning::` を出して本文なしに劣化する。`review_status` を書き換えた後・コミットする前に位置するので、落とすと Issue は Close 済み・ページは `pending` のまま残り、再試行の経路が無い

#### `wikicommit-translate` — 原文との照合

翻訳の照合は Pass 4 と同型の**独立したサブエージェント**が行う（訳したのと同じコンテキストで読み直さない）。渡すのは翻訳ページ・原文ページ（**これだけが `SOURCE`**）・用語対応表と `translator_notes`（参照資料）に限り、**原文ページのソース文書は渡さない**（原文ページ自身の誤りを翻訳のせいにしないため）。

- 検査の内容は `review-rules.md` の `translate-check` 節（Part 2 は 1・2 のみ「原文が述べているか」と読み替えて適用、訳漏れはこの経路に限り FAIL、対応表の 3 制限、構造の破損は `CONTRADICTION`）にある。`type` は §4.6 の 3 値のまま（加筆は `HALLUCINATION`、意味のずれ・訳漏れ・構造の破損・用語の不一致は `CONTRADICTION`、`source_file` は原文ページのパス）。`OMISSION` は足さない
- FAIL は `issues[].instruction` を渡して `generate.max_retries` 回まで作り直し、**上限を超えたら書き出さない**（`result: discarded`）
- 公開側では「出典と照合」に混ぜない（`docs/DesignDoc-publish.md` §8.8.1）。`convert_wikilinks.py` はこの記録の `stage` を `ai_review_stage` として刻印し、バナーは「原文と照合」と表示する。ルート index の「出典と照合」件数には翻訳ページを数えない
- 既存の翻訳ページには遡及しない（次に訳し直されたページから記録が付く）

#### 読み出しは `check_review_coverage.py`

集計・未レビュー・抜取候補・失効の列挙は `check_review_coverage.py` が行い、`wikicommit-status` が呼ぶ（仕様は `docs/DesignDoc-ScriptSpec.md`）。**閾値・合否判定・自動化は入れない** — 実測が無い状態で決めた閾値は推測にすぎない。人が `RISKY:` / `COVERAGE:` を読んで `/wikicommit-generate --regenerate`を叩けばループは人力で閉じる。

**読み手は 2 つある。** 上記の集計は `wikicommit-status` が読むが、**`result: discarded` の記録には 2 人目の読み手がいる** — `wikicommit-merge` Step 9 の生成失敗トラッキング Issue である。Pass 4 step 7 は `partial` 分岐で `## Failure Reason` を削除する（`failed` ではないため）ので、普通の失敗の形である `partial` では管理ファイルから理由が取れない。`check_review_coverage.py --discarded-reason`（`docs/DesignDoc-ScriptSpec.md` の同スクリプトの節）が `failed_pages` 行きの記録から理由を読み出し、Step 9 に渡す。Pass 4 が PASS したページだけでなく破棄したページも記録するのは、この用途のためでもある。

**この用途のために記録の形は変えない。** 読み出しモードがあるだけで、`FINDING_FIELDS` も射影の規則も同じであり、§4.6 の「本節の JSON そのもの」と「射影したもの」の区別（前者はフィールド追加が自由、後者は後方互換の対象）はそのまま保たれる。**印字しないフィールドがあることは記録しないことを意味しない**: `source_file` は記録には残り続け、Step 9 が印字しないだけである（gitignored なキャッシュを指すため）。

#### 既存リポジトリへの遡及生成は行わない

本ドキュメント群が一貫して採る「新旧混在を許容する」方針どおり、記録の欠如は「この機能追加より前に生成された」ことを意味する。**そして測定は遡って作れない** — 記録が無かった期間は永久に空白である。これは受け入れる代償であり、だからこそ記録を早く始めることに意味がある。

読者向けの表示（バナー・俯瞰ページ）は本節のスコープ外であり、**ページ frontmatter に要約フィールドを足すことはしない** — 表示側は記録ツリーを publish 時に読む形を採る。

---

## 5. スキーマ層の実装

### 5.1 `.wikicommit/schema/*.md` の役割

`.wikicommit/schema/` ディレクトリ自体がドメインプロファイル。ファイル名がタイプ名になる（`.wikicommit/schema/Person.md` → `.wikicommit/entity/*/Person/` ディレクトリが有効）。LLM と CI の両方が読む仕様書として機能する。

Schema.org プロパティの意味・型・制約の定義文は書かない。LLM は Schema.org を学習済みのため、「どれを `properties:` に入れるか」の取捨選択のみ記載する。

`wikicommit.frontmatter.required` は `validate_frontmatter.py` が CI 検証に使う必須フィールドリスト。`default.md` にのみ存在し、全ページ共通の必須フィールド（`title`/`lang`/`type`/`sources`）を定義する。

型スキーマファイルは型レベルの `required` / `recommended` / `excluded` / `custom` の分類を持たない。型固有のプロパティ一覧はテンプレート本体の `properties:` ブロックのキーが表し、「Schema.org 上は存在するが意図的に書かない」という判断は `granularity` に自然文で書く（例: `Person.md` の "Do not record marital/family relationship properties ..."）。**`properties:` 配下の各キーは常に任意項目**であり、`validate_frontmatter.py` が検証するのは値がある場合の Schema.org 語彙適合性だけである。特定のプロパティを必須にする能力は無く、要るならその能力自体を設計し直す。

#### スキーマファイルの配置は `type:` から機械的に導出される

スキーマファイルの探索は `.wikicommit/schema/<type: から schema: を除いた値>.md` というパス導出のみで行われ、ディレクトリを型名で走査する処理はどこにも存在しない。`custom/` は例外ではなく、この規則の帰結にすぎない（`type: "schema:custom/Decision"` の型名自体が `custom/Decision` であるため `.wikicommit/schema/custom/Decision.md` になる）。

したがって、型が増えてきたからと `.wikicommit/schema/standard/Person.md`・`.wikicommit/schema/text/Book.md` のように分類しても、**その型定義はファイルを移動した瞬間に静かに無効化される**。`.wikicommit/schema/` は LLM 書き込み禁止領域であり編集は必ず人間の手で行われるため、これは十分起こりうる操作である。

無効化されると `default.md` へフォールバックし（§5.4。フォールバック自体は正規の設計）、その型の `granularity`・`properties:` 候補キー・本文テンプレートが丸ごと適用されなくなる。それでも生成されたページは一見正常で、`validate_frontmatter.py` の必須フィールド検証も通る（`default.md` の required だけが適用されるため）。この状態は `wikicommit-status` の `check_schema_coverage.py`が「専用スキーマファイルが無いまま使われている `type:` 値」として継続的に報告するが、報告を見て `wikicommit-schema-propose` を実行すると `.wikicommit/schema/<Type>.md` を新規作成するため**同じ型の定義ファイルが2つ並ぶ**（実際に効くのは新しく作られた方のみ）点に注意する。正しい対処は移動したファイルを元の位置へ戻すことである。

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

#### 記事系 3 型は共通の `## Key Points` を持つ

`ScholarlyArticle` / `NewsArticle` / `BlogPosting` の 3 型は、本文に **`## Key Points`** という同じ見出しを持ち、その下を**1 主張 1 箇条書き**で書く。`tests/test_schema_template_key_points.py` が配布テンプレートについてこれを CI で強制する。見出し名が型ごとに違ったり散文で書かれていたりすると、主張を 1 件ずつ取り出せず、型をまたいで探せない — 主張を横断的に整理する（比較する・矛盾を見つける・根拠の強さを並べる）前提がこの 1 段である。

**消費者**:

- **人間の目** — 3 型のどのページを開いても同じ位置に同じ形で主張が並ぶ
- **`build_survey_view.py`** — 各ページの `##` 見出しを抽出しており、`wikicommit-synthesize` の俯瞰モードがこの節の存在を横断シグナルとして使える。新しいスクリプトは要らない

**箇条書きの中身にも 2 つの規律を課す**。(1) その文書自身が述べていることに限る — 他文書から引いただけの主張はその文書の主張であり、日付や数値を確定事実として書かない（孫引きの規律）。(2) 根拠が見た目より狭い場合はその箇条書き自身にそう書く（単一のデータセット・単一の取材源・著者自身の経験・自社製品のドキュメント等）。フィールドは増やさない。

**対象は記事系 3 型のみ**。`ShortStory` / `Book` は作品であって論証ではなく、他の型は「その文書の主張」という概念を持たない。全型に一律で足すと受け皿だけが空のまま残る。上記テストは対象 3 型と**非対象 9 型の両方**を理由付きの定数として持ち、どちらの向きの逸脱も止める。

- **`evidenceOrigin` 相当のプロパティは配布 3 型に足さない**（空プレースホルダーになる。必要な Wiki は §5.3 の経路で自分の型を作る）
- **主張自体をエンティティ化しない**。`schema:Claim` は主張間の関係（支持・反証・限定）を定義しておらず、`custom/Claim` は同一性が定義できない（既存のヘルスチェックは正規化した文字列一致に立つが、命題は正規名を持たず別の言い回しで現れる）
- 旧見出し（`## Key Contributions`）を持つ既存ページはそのまま残る（遡及しない）

#### 配布テンプレートの `properties:` に「埋められないキー」を置かない

配布テンプレートの `properties:` に列挙してよいのは、**そのキーに適合する値を、その Wiki が持っているものだけで書けるキー**に限る。書けないキーを置くと、Pass 3 はそれを埋めることも消すこともできず、空のプレースホルダーが生成ページの frontmatter に残る。

判定基準は 2 条件の連言で、`check_schema_org_type.py --show-range` が返す RANGE 分類から機械的に決まる:

1. `rangeIncludes` のエンティティ型候補に、配布テンプレートに含まれる型が 1 つも無い（＝ `[[Type/slug]]` が解決しうる先が無い）
2. DataType 候補だけでは事実を担えない — 候補が空であるか、唯一の候補が `URL` でありながら同時にエンティティ型候補も宣言されている（その `URL` は「作れないエンティティ」を指す識別子でしかない）

- **`DefinedTerm.md` は `inDefinedTermSet` と `termCode` を持たない**。前者は 2 条件をともに満たし（エンティティ候補は配布されない `DefinedTermSet` のみ、DataType 候補は Wiki 内部の分類体系が持たない `URL` のみ）、後者は前者を外すと錨を失う（"A code that identifies this DefinedTerm within a DefinedTermSet"）。ソース側に実在する分類体系は、`DefinedTerm.md` の `granularity` が示すとおり、所属を `tags` に、体系そのものの説明を本文に書く
- **基準を満たしても残すキーが 2 つある**: `Event.eventStatus`（`EventStatusType` は公開・固定 IRI のメンバーを持つ Enumeration で、Wiki 側に型を作らなくても適合値が書ける）と `Organization.numberOfEmployees`（`QuantitativeValue` は JSON-LD の構造化値として値の形が決まっている）。この 2 件に「WikiLink 化しない」と `granularity` で書くことはしない — `check_property_wikilink_reinforcement.py` の `is_reinforced()` は肯定・否定の文脈を区別しないので、補強済みと誤判定される
- `tests/test_schema_template_property_reachability.py` が判定基準を CI で強制し、除外する 2 件を理由付きの allowlist として持つ（「確認済みのものだけを決定論的な表に持つ」パターン）

**Pass 3 は埋められないキーを省略する**（空文字列を残さない）。`properties:` 配下のキーはすべて任意なので省略は常に妥当であり、空文字列は「ソースがそう述べている」と区別できず、`wikicommit-properties` プラグインが空の行として描画する。全キーを省略した場合は `properties:` キー自体も省略する（値なしの `properties:` は YAML の null になり、やはり空行として描画される）。

このルールが決めるのは**テンプレートが差し出したキーをどう書き出すか**だけであり、**ページが既に持っている値を消すことはない**。`action: update` では、今回のソースが触れていない `properties:` キーの既存値はそのまま残す（「このソースが言及していない」は「記録すべきものが無い」ではない）。テンプレートに無いキー（`termCode` / `inDefinedTermSet` を含む）も、`validate_frontmatter.py` が `domainIncludes` に対して検証するので引き続き妥当なキーであり、既存の値は引き継ぐ。

#### 型間の優先関係は `granularity` に書く（専用キーは設けない）

「この場合は別の型に譲れ」という**型と型の間の優先関係**は、`granularity` の箇条書きとして書く。`wikicommit:` ブロックに専用キー（`defer_to:` 等）は新設しない — 「ソースの実質が読者の行う順序手順かどうか」のような譲る条件は機械判定できず、キーにしても評価するのは結局 Pass 2c の LLM である。

**2 か所で補強する**:

- **書く側**: 型ファイルを書く 4 経路（`wikicommit-init` の obvious-type judgment・`wikicommit-collect` の Type Proposal・`wikicommit-generate` Pass 2b・`wikicommit-schema-propose`。手順は `.wikicommit/schema-authoring.md`）は、「別のインストール済み型がその主題の適切な置き場なら、型名を挙げて `granularity` の 1 ルールとして書く」。`Boundary` ルール（その型が**何でないか**。下記）とは別物で、こちらは「代わりに誰が持つべきか」を述べる。**インストール済みの型しか名指ししない**
- **読む側**: `wikicommit-generate` Pass 2c は「候補型の `granularity` が他の型に譲れと言っており、その型がインストール済みなら従う」。§5.4「最も具体的なインストール済み型を選ぶ」と同じ箇所に置く

**読む側の補強は必須である**。型ファイルに正しく書かれた委譲（例: `GovernmentService.md` の "Prefer `schema:HowTo` when the source's substance is an ordered set of steps the resident performs"）が、Pass 2c に読まれず手順マニュアルが `GovernmentService` として書かれた実例がある — 書いたのは数分前の同じモデルだった。1 ページの粒度が他より極端に大きいのは、1 ページに 2 つの主題が同居している徴候であり、その解き方は §5.4「1 ソースから型の異なる複数エンティティを切り出してよい」にある。
**境界を足すときは型テンプレートだけで済ませず、それを判断する Pass の指示にも書く**。型テンプレートの記述だけでは従われず、Pass 2c の指示へ書き足したら従われた対照がある（§5.4「ソースがすれ違いに引用しただけの文書はエンティティにしない」）。

#### `granularity` の境界ルールは片側にしか書けない

`granularity` の箇条書きには、その型が**何でないか**を述べる境界ルールを書く。配布テンプレートの全 `base_types` は `Boundary —` で始まる箇条書きを 1 件ずつ持ち、`tests/test_schema_template_boundary_rules.py` がこれを CI で強制する。

**境界ルールは構造的に片側にしか書けない**。Pass 2b と `wikicommit-schema-propose` は `.wikicommit/schema/` に「追加のみ可・既存ファイルの編集不可」でしか書き込めないので、新しく追加される型は既存型との境界を自分の `granularity` に書けるが、**その相互の記述を既存型側に書き足す経路はどの Skill にも無い**。型選択は「どちらの型ファイルがその境界に言及しているか」に左右されるので、放っておくと既存の `base_types` 側が一方的に選ばれにくくなる。そこで:

1. **配布テンプレート側で自足させる**。全 `base_types` に、他の型の記述に依存せず単体で成立する境界ルールを書く。相手方の型名を挙げてよいのは相手も必ず配布される `base_types` の場合に限る
2. **区切りは `—` にする**（`Boundary with X: ...` のようにコロン + 空白を使うと YAML のマッピングとしてパースされ、`isinstance(g, str)` で絞り込む消費者〈`check_property_wikilink_reinforcement.py` の `is_reinforced()`〉から見えなくなる）。上記テストが配布テンプレートについて、`check_property_wikilink_reinforcement.py` が実行時に書かれた型ファイルについて非文字列の箇条書きを WARNING で可視化し、`.wikicommit/schema-authoring.md` が「文字列としてパースされる形で書く」ことを明記する（`docs/DesignDoc-ScriptSpec.md` の同スクリプトの節）
3. **Pass 2b が既存型との境界に言及したら Completion Notice で報告する**。既存ファイル編集不可という制約は保ったまま、「相互の記述が相手側に無い」ことを人間が知る経路を作る（人間は `.wikicommit/schema/` を直接編集できる）。非対話実行でも報告する

**採らない案**: 既存型ファイルの `granularity` への追記だけを narrow exception として許す（`.wikicommit/schema/` は LLM 不可侵という原則に穴を空け、追記と既存記述の矛盾を検出できない）／片側だけの境界ルールを機械的に検出する（「型 X に言及しているか」は grep できても「相互の記述が必要か」は判定できない。上のテストは「各型が自分の境界を 1 件持つか」という判定可能な形に置き換えたものである）。

既に片側だけの境界ルールを持つ Wiki は、人間が `.wikicommit/schema/` を直接編集して揃える。

#### Pass 2b が書く `granularity` の内容は誰も検証しない

`granularity` はスキーマファイルの中で**唯一、検証済みの値ではなく自由記述のプローズである**部分であり、下流にそれを検査する仕組みが無い（`check_schema_org_type.py` は型・プロパティの実在だけを、`check_property_wikilink_reinforcement.py` は property 名の言及だけを見る）。一方 Pass 2b が書いた型ファイルは、通常の変更と同じバッチで `wikicommit-merge` が**自動マージする**。

1. **Pass 2b（と `wikicommit-schema-propose` Step 4）の執筆指示**: このソースの実際の内容に即した 1〜3 件・`Boundary` 箇条書きを 1 件含める。**SKILL.md 自身の他のルールと矛盾する記述を書かない**（既知の衝突として Pass 2a の source-as-entity 判定 — 継続更新される living resource は除外する — を名指しする）。**全型に共通するルールを `granularity` で言い直さない** — 一般ルールの言い換えこそが矛盾の生まれ方である
2. **追加された型の `granularity` を Completion Notice に全文表示する** — 検証されず、後から編集もできない文面が人間の目に触れうる唯一の瞬間である

**既知の衝突パターンを機械的に検査しない** — grep は語が現れるかは判定できるが、肯定文脈か否定文脈かを区別できない（「公式文書も対象とする」と「公式文書は対象としない」が同じヒットになる）。言及の有無しか見ない正規表現が文脈を取り違える失敗は `is_reinforced()` で実際に起きている。

既に書かれた矛盾した文面は、人間が `.wikicommit/schema/` を直接編集するまで残る。

#### `wikicommit.provenance` フィールド

`.wikicommit/schema/<Type>.md`（`custom/` 配下も含む）の `wikicommit:` ブロックに、そのファイルがどの経路で作られたかを記録する `provenance` フィールドを持たせる。値は以下の固定 enum のいずれかで、各書き込み箇所がその場で自分の経路に対応する値をスタンプする:

| 値 | 経路 | 人間の確認 |
|---|---|---|
| `default` | `wikicommit-init` の base_types 展開 | なし（無条件展開） |
| `init-theme` | `wikicommit-init` の theme 駆動型提案 | Enter ベース承認あり |
| `generate-interactive` | `wikicommit-generate` Pass 2b、人の承認（ソースごとの繰り返しの後の質問） | Enter ベース承認あり |
| `generate-auto` | `wikicommit-generate` Pass 2b、非対話自動承認。**今後は書かれない**（既存ファイルのために enum に残す。§5.4） | なし |
| `collect` | `wikicommit-collect` の Type Proposal ステップ | Enter ベース承認あり（常に対話実行） |
| `schema-propose` | `wikicommit-schema-propose` | PR レビュー必須（auto-merge しない） |
| `manual` | 人間が `.wikicommit/schema/` を直接編集して作成（Skill を経由しない） | 人間自身が書いた（この行だけ列の意味が異なる — 他の6値が「Skill の提案を人間が承認したか」を表すのに対し、ここでは人間が起案者そのもの） |

このフィールドは一度書いたら値が変わらない恒久スタンプである。Wiki ページ側の `generated_by`/`generated_at` は `action: update` での再生成のたびに書き換わる（`.claude/skills/wikicommit-generate/SKILL.md` Pass 3）ため類似の例ではない — `provenance` が実際に不変である根拠は、スキーマファイル自体が、機械（Skill）からは各 Skill の「追加のみ可・既存ファイルの編集/上書き不可」という narrow exception のもとでしか書き込まれない（§5.1・各 Skill の Pass 2b 等参照）ため、機械が書き込み後にこのフィールドを書き換える経路がそもそも存在しないことにある（人間の直接編集はこの限りではない — 下記 `manual`）。「レビュー済みかどうか」を表す `review_status` のような遷移フィールドではなく「どうやって生まれたか」を表すフィールドであるため、ライフサイクル管理（いつ誰が消す/更新するか）を持たない。

情報提供専用のフィールドであり、`validate_frontmatter.py` 等の CI 検証には接続しない（値の有無・妥当性で `wikicommit-merge` をブロックしない）。監査したい場合は `.wikicommit/schema/**/*.md` を直接 grep すれば足りる。

各書き込み箇所は `.wikicommit/schema/default.md` と `.wikicommit/schema/Person.md` を「固定の書式リファレンス」として参照する（§5.2 冒頭の型スキーマ例もこの2ファイルに準拠）。このとき `Person.md` 自身が持つ `provenance: default` の値をそのままコピーしないこと — それは `init.py` の base_types 展開専用の値であり、各書き込み箇所は上表の自分自身の経路に対応する値を書く。

本機能追加より前に作られた既存のスキーマファイル（配布済みパイロットリポジトリのスキーマファイル）への遡及付与は行わない。`provenance` フィールドの欠如は「この機能追加より前に作られた」ことを意味し、新旧混在を許容する（本ドキュメント各所で踏襲されている既存パターンと同じ）。

**`manual`** は人間がどの Skill も経由せずにスキーマファイルを直接作った経路を指す。書き込み権限ルールが `.wikicommit/schema/` への書き込みを禁じている相手は LLM/Skills であり、人間の直接編集は禁じていない（まだ 1 ページも無い型を先に定義する、等。`wikicommit-schema-propose` は既存ページからの事後検出を起点とするのでこれを代替できない）。

- `provenance` を書かない形にはしない — 欠如は既に「この機能追加より前に作られた」を意味する
- 不変性は規約で担保する: 「どうやって生まれたか」を表すフィールドなので、Skill が作ったファイルを人間が後から手直ししても `provenance` は書き換えない。`manual` を書くのは、ファイル自体を人間が起案したときに限る
- このリポジトリ自身の `.wikicommit/schema`（と `.wikicommit/scripts`）は templates 配下への symlink であり、templates と同一のファイルである（`tests/test_template_mirror_sync.py`）

### 5.3 カスタム型（`.wikicommit/schema/custom/*.md`）

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

#### `custom/` は entity 側では必須、公開サイトには出ない

`custom/` は「カスタム型を入れるフォルダ」ではなく**型名そのものの一部**であり、「この型は Schema.org 語彙に無いので機械検証をスキップせよ」というマーカーである。分岐するのは `validate_frontmatter.py`（語彙に無い型を誤字として ERROR にするガードの唯一の逃げ道）・`check_property_wikilink_reinforcement.py`（RANGE 分類が引けない）・`wikicommit-jsonld` プラグイン（不正な `@type` を出さない）の 3 箇所で、プラグインは frontmatter の `type:` しか持たないので、マーカーは型文字列自体に載っている必要がある。

読者にとって `custom` は内部語彙なので、`convert_wikilinks.py` が **publish 時にのみ**先頭の `custom/` セグメントを落とし、`content/<lang>/<Type>/<slug>.md` として書き出す（`.wikicommit/entity/` と `type:` の値は変えない）。Explorer・パンくず・folder page・URL が一度に揃う。**この食い違いは揃えるべきドリフトではない** — entity 側から外せば誤字のガードが壊れ、content 側に戻せば内部語彙が露出する。

- **ルックアップキーは絶対にフラット化しない**。`flatten_custom_type()` / `flatten_entity_rel()` は出力パスとリンク生成にだけ適用し、`.wikicommit/entity/` の実ファイルを読む箇所（WikiLink の存在確認・`generated_pages[]` の frontmatter 読み取り）は `custom/` を保つ。出力パスは `main()` が一度だけ計算して `convert_file()` と stale cleanup の両方へ渡す（片方だけフラット化すると、書いた直後のファイルを同じ実行内で削除する）
- **本文中の相対パスも書き換える** — 1 段浅くなるので、`rewrite_relative_links()` が WikiLink 変換の**前に**ソースディレクトリ基準の相対リンクを出力ディレクトリ基準へ再計算する
- **フラット化後に同名になる 2 つの型**（将来 Schema.org に同名の型が追加されてインストールされた場合）は、`main()` が全ページの出力パスを先に計算して衝突を検出し、**フラット化されていない側を優先**してもう一方を `WARNING` 付きでスキップする（ビルドは落とさない）。`flatten_custom_type()` が先頭 1 セグメントしか落とさないのは写像を単射に保つため

#### 配布テンプレートにカスタム型を同梱しない

`.claude/skills/wikicommit-init/scripts/templates/schema/custom/` は空（`.gitkeep` のみ）であり、**カスタム型を配布テンプレートに同梱しない。これは方針である**。Schema.org 語彙には「実践ノウハウ」の汎用型（`Practice`・`Technique` 等）が無いが、それでも配布しない:

1. **ターゲットユーザー像（`dev/PRD.md` §3）は実践知に特化していない** — ドメイン一般の Wiki が対象であり、ディレクトリに置けば型が有効になる以上、配った型は全 Wiki で有効になる
2. **カスタム型は `validate_frontmatter.py` の `domainIncludes` 機械検証の対象外である** — 全 Wiki に一律配布する型がその検証を受けないことは、スキーマ一貫性という価値提案を最も広く行き渡る場所で弱める
3. **必要な Wiki が自前で作る経路が既にある** — `wikicommit-schema-propose`（カスタム型を書ける唯一の Skill 経路）と人間による直接編集（`provenance: manual`）。Pass 2b は標準型のみ

**型名は各 Wiki が決めてよい**。多義性（英語 practice は「慣行」「練習」「開業」）が実害になるのは全 Wiki に一律配布する場合だけである。`Practice`・`Pattern`・`Technique`・`Method`・`Approach`・`Guideline`・`Playbook`・`Heuristic` はいずれも Schema.org 語彙に無いので、将来の標準型と衝突するリスクは低い。

**`HowTo` は寄せない・外さない** — 「1 つの成果に向かう順序付きの手順列」の型として正しく働いており（行政手続き等）、`GovernmentService.md` の `granularity` の委譲先でもある。`HowTo.md` の `granularity` は「`tool` / `supply` が空でも HowTo である」ことを明記する。

**`DefinedTerm` の中で実践・手法を書く指針は配布テンプレート側にある**。`DefinedTerm` は「現象・問題」「仕組み・構成要素」「実践・手法」の 3 種類を抱えており、「適用条件・前提・失敗モード・根拠の強さ」が意味を持つのは 3 番目だけである。`DefinedTerm.md` の `granularity` がこの 3 分類と 4 項目を述べ、本文テンプレートが `## When It Applies` セクション（3 番目以外では丸ごと省く）を持つ — 散文だけでは書くかどうかがページごとに揺れるので、本文側にも受け皿を置く。複数の記述を突き合わせた実践の読みは、型ではなく view の `kind: practice`（§4.5.1）で書ける。

#### `wikicommit.rationale`

カスタム型に限り、`wikicommit:` ブロックに `rationale:`（なぜ既存の Schema.org 標準型では表現できず、なぜその `base:` を最も近い親として選んだのかを記す 1〜2 文の自由記述）を持たせる。標準型のスキーマファイルには置かない — 標準型は Schema.org 語彙にその型自体が実在することが選定の根拠であり、散文で補う余地が無いため。

このフィールドは新設の情報ではなく、**既に書かれているが保存先が無かった**情報の置き場である。`wikicommit-schema-propose` の Step 5 は元々「なぜ既存の標準型で代替できないか」を 1〜2 文で書き、それを PR 本文のレビュー観点として提示する手順を持っていた。しかしその文はレビュー用の PR 本文にしか存在せず、マージ後にリポジトリへ残らない。カスタム型は定義上 Schema.org 語彙の外にあり `base:` は「最も近い親型への参照（informational only）」でしかないため、選定理由は §5.5 の段階移行（`deprecated`/`replaced_by` で標準型へ寄せてよいかの判断）や、後からそのカスタム型を見た人間のレビューにとって、後から復元できない一次情報になる。同 Step 5 はこの文をファイル本体にも書くようになり、PR 本文の該当項目はそのコピーになる。

`provenance` と同じく情報提供専用で、CI 検証には接続しない（`validate_frontmatter.py` の検証対象は `.wikicommit/entity/` のページであり、スキーマファイルそのものは検証しない。同スクリプトがスキーマファイルから読むのは `wikicommit.frontmatter.required` だけで〈§5.1〉、`wikicommit:` ブロックの他のキーは一切見ない）。既存のカスタム型スキーマファイルへの遡及付与は行わない — フィールドの欠如は「この機能追加より前に作られた」ことを意味する（`provenance` と同じ扱い）。

**`properties:` 配下の `rationale` とは別物である点に注意する**。上の例の `custom/Decision` は、その型のエンティティが持つプロパティとして `properties.rationale`（その決定を下した理由）を持っている。両者は階層が異なり（`wikicommit:` ブロック vs `properties:` ブロック）、記述する対象も異なる（型の設計判断 vs そのページが記述する事物の属性）。カスタム型のプロパティ名は Schema.org 語彙の機械検証を受けない（本節冒頭）ため、この名前の重複を機械的に避ける仕組みは無く、規約として区別する。

#### カスタム型の命名規約

`.wikicommit/schema/custom/<Name>.md` の `<Name>`（= WikiLink 上の Type セグメント、例: `custom/Decision` の `Decision`）は、標準型（`Person`・`Place`・`Organization`・`Event`・`HowTo`・`DefinedTerm`）と同じ PascalCase・単語文字（英数字・アンダースコア）のみを用い、**ハイフンを含めない**（`Multi-Word` のような命名は不可）。WikiLink 正規表現（`.wikicommit/scripts/_wikilink.py` の `WIKILINK_RE`）の Type セグメントはこの規約に合わせてハイフンを許可しない文字クラスになっており、ハイフンを含む型名を作成すると `[[custom/Multi-Word/slug]]` が存在確認・orphan 判定のいずれからも一致しなくなる。複数単語のカスタム型名が必要な場合は `MultiWord` のように PascalCase で結合する。

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

型選択に関わる追加ルールは本節の以下の 2 つの小節が定める。型ファイル側の書き方 — 「この場合は別の型に譲れ」をどこにどう書くか — は §5.2「型間の優先関係は `granularity` に書く（専用キーは設けない）」を参照。

#### 候補同士が祖先／子孫関係にある場合は最も具体的な型を選ぶ

祖先型は常に当てはまる — Schema.org 上 `Park`・`Museum` は `Place` の子孫なので、公園を `Place` として書くことは誤りではなく粒度が粗いだけである — ため、規則が無ければ広く馴染みのある型が既定で選ばれ、インストール済みの具体的な型が使われないまま品質ゲートも `check_schema_coverage.py` も素通りする（技術的に表現できてしまうことが、より良い型を選ばない理由として働く）。

**規則**: 複数のインストール済み型が当てはまる場合、最も具体的な型（`--list-installed-hierarchy` の鎖で最も下にあるもの）を選ぶ。ただし 2 つの限定が付く。

- **インストール済みの型に限る**。Schema.org には存在するが `.wikicommit/schema/` にファイルが無い型へ手を伸ばすのは Pass 2b の仕事であり、この段の仕事ではない
- **具体性が適合性に優先することはない**。ソースがその主題を公園だと実際に立証していないなら、`Place` が正解であってフォールバックではない

**判断材料は決定論的に渡す**。`check_schema_org_type.py --list-installed-hierarchy`が、インストール済み型それぞれについて**インストール済みの祖先型のみ**を近い順に出力し、Pass 2c がこれをコンテキストに含める。間に挟まる非インストール型（`Park` と `Place` の間の `CivicStructure` 等）は名前を出さない — Pass 2c が選べるのはインストール済みの型だけであり、選べない型を提示しても迷わせるだけであるため。

**受け皿型のテンプレート側にも書く**。`Place.md`（子孫 208 型）・`Organization.md`（166 型）・`Event.md`（35 型）の `granularity` に「より具体的な型がインストールされているなら譲る」旨を追記した。全 `base_types` の子孫型数を機械的に数えた結果、この 3 型だけが桁違いに大きい（次点は `NewsArticle` の 6 型、他は 2 型以下）。`DefinedTerm` も同種の記述を持つ。**この追記は Pass 2c の一律ルールに対する人間可読性の補強であって適用範囲の宣言ではない** — property の WikiLink 化の補強（§4.1）と同じ位置づけであり、記述を持たない型が適用除外になるわけではない。

**取り残しの検出**は `check_installed_type_usage.py`（`docs/DesignDoc-ScriptSpec.md`）が担い、`wikicommit-status` Step 9 が報告する。`check_schema_coverage.py` の対（`check_orphans.py` と `check_wanted_pages.py` が対であるのと同じ関係）。

**既存ページの型の再分類は行わない**。型変更はディレクトリ移動と、そのページを指す全 WikiLink の Type セグメント書き換えを伴い（§5.5）、それを PR 化する新規 Skill（または `wikicommit-schema-propose` の拡張）が必要になる。扱うのは**新規生成時に正しい型が選ばれること**と**取り残しが検出できること**に限る。

#### インストール済みに無い型 — Pass 2b がその場で足す

上のフローは `.wikicommit/schema/` に**既に置かれているファイル**の中から選ぶだけで、Schema.org 語彙全体を探索しない。インストール済みの型で「一応表現できてしまう」場合は `ambiguous` にもならない。この穴は `wikicommit-generate` の Pass 2b（型の要否判断）がその場で塞ぐ: サマリを見てインストール済み外の型が明確に良いと判断すれば、`check_schema_org_type.py` で型・プロパティの実在を検証したうえで Enter ベースの承認（既定 N）を求め、承認されれば `.wikicommit/schema/<Type>.md` を新規作成し（追加のみ可・既存ファイル編集不可の書き込み例外）、続く Pass 2c がその型を直接使う。新しいスキーマファイルは他の変更と同じバッチで `wikicommit-merge` がマージする（既存スキーマファイルの変更は `wikicommit-schema-propose` の非 auto-merge な PR 経由のみ）。

- **候補を別セッションへ引き継ぐ形（警告フィールドに記録して後で拾う）は採らない** — `check_schema_coverage.py` は専用スキーマファイルの無い `type:` しか見ないので、既にインストール済みの型で生成されたページは後から検出できず、情報が構造的に失われる。却下した候補もどこにも永続化しない
- **候補はその場では尋ねず、すべて保留にする**（§4.3「保留」。`status` を動かさず、`## Deferred Reason` に候補の型名と理由を書いて次のソースへ）。人がいれば、ソースごとの繰り返しの後に型ごとに 1 回尋ね、承認・却下を受けたソースを同じ実行の中でもう一度処理する。非対話実行では尋ねない。閾値を超えた候補を無人で自動承認する形は採らない — 自動マージされる PR は事実上読まれず、型ファイルは Skill が編集できず再分類の Skill も無いので自動承認は取り返しがつかない一方、保留の代償はそのソースが次の対話実行まで待つだけである。候補を出すかどうかの閾値は対話・非対話で共通
- `provenance: generate-auto` は今後書かれないが、既存リポジトリに残るので enum から消さない（`check_schema_files.py` の `BAD_PROVENANCE`・`.wikicommit/schema-authoring.md` の `applies_to`・`wikicommit-merge` Step 8 の型確認行・`wikicommit-review` は引き続き受け付ける）
- `wikicommit-schema-propose` は `check_schema_coverage.py` による**事後検出**の安全網として残る

#### 1 ソースから型の異なる複数エンティティを切り出してよい

Pass 2c の分析 JSON の `entities` 配列は元から単一型に制限されていないが、**そのように切り出せることが明示されていなかった**ため、1 つの主題に寄ったソースは 1 エンティティとして出てきやすかった。「あるモノ」と「それを使う手順」の両方を扱うソースは両方を抽出してよい — サービスとその申請手順、ソフトウェア製品とそのセットアップ手順、施設とその入館手続き。§5.2「型間の優先関係は `granularity` に書く」で挙げた `household-waste-disposal` は本来「収集サービス本体（`GovernmentService`）」と「粗大ごみの出し方（`HowTo`）」に分割すべきだった。

ただし**各部分がそれ自体で主題として立つ場合に限る**。このルールを満たすために 2 つ目のエンティティをでっち上げない。

**既存ページへの遡及適用はしない**。`/wikicommit-generate --regenerate` は Pass 2c を実行しない（ページ起点で型を所与とする）ため、既に 2 つの主題を抱えた 1 ページを分割することはできず、型の再分類と同じくスコープ外である（`docs/DesignDoc-pipeline.md` §6.1 の再生成モード節）。

#### ソースがすれ違いに引用しただけの文書はエンティティにしない

ソースが別の話を書きながら 1 回だけ名前を出した文書（対比のための引用・関連研究の 1 行・参考文献リストの項目）は、Pass 2c が `entities` に出さない。逆に、ソースがその文書を**自分の主題として**扱っているものは通常のエンティティである。

**同じ規律は後段にもある** — Pass 3 の Secondary citation discipline と `review-rules.md` の check 4 である。だが後段だけだと、passing mention された文書はエンティティとして切り出され、ページとして書かれ、**レビューで初めて却下される**。却下されたページは `failed_pages` に記録されるので、そのソースは `status: partial` かつ `failed_pages` 非空として Pass 1 の収集条件に毎回一致し、入力が変わらない限り同じエンティティを切り出し・書き・却下し続ける。Pass 2c で切り出さなければ `failed_pages` が空になり、ループは移行作業なしで止まる。

**`exclude` としては表現できない。** `exclude_reason` は `theme_mismatch`（関連性）と `privacy`（許容性）の 2 値であり、本件は**証拠**の軸（根拠となる文書が `sources` に無い）でどちらでもない。Pass 2c は前回のレビュー記録を読まないので、判定が次の実行へ伝わる経路も無い。

決定した 4 点（`docs/DesignDoc-skills.md` §11.6 に判定の文面がある）:

| 論点 | 決定 |
|---|---|
| 判別がつかない場合 | **passing mention 側に倒して抽出しない。** check 4 が同じ引き分けを同じ側に倒すためであり、Pass 2c だけが寛容だとその差分が無駄な 1 周を構造的に保証する |
| 登録簿を見るか | **見ない。** `.wikicommit/source/` は Pass 2c のコンテキストに元から無い。別途登録されていればそのソース自身の実行がページを作る |
| 非抽出の記録 | **残さない**（無言のまま受け入れる）。3 つ目の `exclude_reason` は消費者のいない enum になる。誤りの向きが安全なのは片方向だけである — passing mention を落とす側は「Pass 4 が却下していたページが 1 段手前で消える」に留まるが、主題として扱われている文書を誤って落とす側はレビューを通ったはずのページを無言で失い、書かれなかったページは orphan でも wanted page でもないので検出もされない。引き分けの倒し方は判別がつかない場合に限り、過剰適用しない |
| Pass 3 の規律 | **残す。** 3 段が下している判断は別物であり（作るか／書くか／FAIL にするか）、同じ命題の言い換えではない。「共通ルールを個別の場所で言い直さない」（§5.2）には当たらない |

**Pass 2a の source-as-entity 判定とは別物である** — あちらは「ソース文書**自身**をページ化するか」、こちらは「ソースが**引用した別の文書**をページ化するか」。1 回の実行で両方が発火しうる（論文自身のページは正しく、その論文が対比のために引用した別論文のページは誤り）。

**効果を測る一般的な手段は無い**（抽出精度の eval 基盤がこのリポジトリに無い）。壊れ方が軽いことを根拠に採った。**既存ページへの遡及は行わない**（新旧混在を許容する方針）。既に書かれた passing-mention 由来のページは `/wikicommit-remove` で人が下ろす。

**設計上の目安**: 「書くかどうか」（切り出す・切り出さない・別の型に譲る）の境界は、それを判断する Pass の指示に置く。型テンプレートには「どう書くか」を置き、同じ境界をそこにも書くのは人が読むための補強と位置づける。`granularity` に書くのをやめる、という意味ではない — 片側だけでは足りない。本ルールの導入では、型テンプレート側の境界はそのままに Pass 2c の指示だけを足して、引用されただけの論文が切り出されなくなった対照が 1 つある（1 回ずつの観察であり、「常に効く」とは読まない）。同じ理由で、`/wikicommit-update` で型テンプレートの差分を取り込んでも、それだけで抽出の挙動が変わるとは限らない。

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
