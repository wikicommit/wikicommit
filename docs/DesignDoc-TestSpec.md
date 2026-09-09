# テスト・Lint 仕様書

> **バージョン**: 0.1（Draft）
> **作成日**: 2026-07-06
> **対応DesignDoc**: [DesignDoc-CISpec.md](DesignDoc-CISpec.md)（ランタイム品質ゲート）とは別軸

[DesignDoc-CISpec.md](DesignDoc-CISpec.md) は `wikicommit-merge` が Wiki ページに対して実行するランタイムの品質ゲートを定義する。本書はそれとは別に、**WikiCommit 本体（Python スクリプト・Skills・quartz-plugins）を開発する際のテスト・Lint 基盤**の現状と整備方針を定義する。対象は `tests/`・`.github/workflows/test.yml`・`.claude/skills/*/scripts/`・（配布テンプレート内の）`quartz-plugins/` など。

---

## 現状

> 見出しの日付は落とした。この表は起票時点のスナップショットではなく、項目が片付くたびに
> 更新され続けている（最新の追記は Issue #770）。一方で本書の他の節は 2026-07-06 の
> 起票時のまま残っている箇所があり、`docs/README.md` §1 の断り書きがそちらに掛かる。

| 対象 | 状態 | 備考 |
|---|---|---|
| CI での pytest 実行 | ✅ 済み | `.github/workflows/test.yml` が `pull_request` / `push: main` で `pytest tests/` を実行（Issue #80）。Issue #591 で `checks` ジョブへ統合（[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。Python バージョンは代表 1 バージョン（3.11）のみ（Issue #216。[L6](#l6-ci-job-数削減と-concurrency-設定-対応済みissue-216)） |
| `.wikicommit/scripts/` の check 系 6 本のユニットテスト | ✅ 済み | `tests/test_check_*.py` / `test_validate_frontmatter.py`（Issue #80） |
| テンプレートミラー同期検証 | ✅ 済み | `tests/test_template_mirror_sync.py` が `.wikicommit/schema/` と `.wikicommit/scripts/` について、git 管理ファイル一覧とバイト内容を canonical ⇔ `.claude/skills/wikicommit-init/scripts/templates/` 間で突き合わせる（`read_bytes()` 直接比較。Issue #73 の再発防止）。`.markdownlint.json` は矛盾のないキー単位比較で対応済み（Issue #90。[L4](#l4-markdownlintjson-の同期検証-対応済みissue-90) 参照）。`quartz-plugins/` は Issue #81 で root コピーが削除され唯一のコピーとなったため対象外 |
| `init.py`（wikicommit-init）のユニットテスト | ✅ 済み | `tests/test_init.py`（Issue #88・PR #95）。[T2](#t2-initpy--add_sourcepy-のユニットテスト-対応済みissue-88) |
| `add_source.py`（wikicommit-generate）のユニットテスト | ✅ 済み | `tests/test_add_source.py`（Issue #88・PR #95）。[T2](#t2-initpy--add_sourcepy-のユニットテスト-対応済みissue-88) |
| ローカル完結スモークテスト | ✅ 済み | `tests/test_smoke_local.py`（Issue #92）。一時ディレクトリ上で init → `git add` 案内どおりのステージまでを実行し、`git status --porcelain` が空になることまで検証する（`--quartz` 経路の逆向き検証は Issue #556 で追加）。当初 T1 が代替対象としていた重量級 E2E（Issue #82）は Issue #714 で廃止。[T1](#t1-ローカル完結スモークテスト-対応済みissue-92) |
| quartz-plugins（wikicommit-banner・wikicommit-jsonld）のテストフレームワーク | ✅ 済み | 各プラグインに vitest を devDependency として導入し、`.github/workflows/test.yml` に `quartz-plugins-test` ジョブを追加（Issue #93）。プラグイン追加に伴いマトリクスを 1 job 内ループへ統合済み（Issue #216）。さらに `quartz-plugins-lint` と併せて単一の `quartz-plugins` ジョブへ統合済み（Issue #591。[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。[T3](#t3-quartz-plugins-への-vitest-導入-対応済みissue-93)・[L6](#l6-ci-job-数削減と-concurrency-設定-対応済みissue-216) 参照 |
| markdownlint-cli2 の CI 組み込み | ✅ 済み | `.github/workflows/test.yml` に `markdownlint` ジョブを追加し、`docs/**/*.md` と `README.md` を対象に blocking で実行（Issue #89。Issue #591 で `checks` ジョブへ統合。[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。`dev/`・`Issues/` を対象外とする判断は Issue #89 実装時の暫定メモに留まっていたため、Issue #108 で正式な設計判断として本書に明記した。[L1](#l1-markdownlint-cli2-の-ci-組み込み) |
| `.wikicommit/scripts/` ・ `.claude/skills/*/scripts/` の Python linter | ✅ 済み | `pyproject.toml` の `dev` 依存に `ruff` を追加し、`.github/workflows/test.yml` に `ruff check .` ジョブを追加（Issue #91。Issue #591 で `checks` ジョブへ統合。[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。配布テンプレートのミラー（`.claude/skills/wikicommit-init/scripts/templates/scripts/`）は `.wikicommit/scripts/` と内容が完全一致することが `test_template_mirror_sync.py` で保証されているため、二重検知を避けるため `[tool.ruff].extend-exclude` で対象から除外した。[L2](#l2-python-linterruffの導入-対応済みissue-91) |
| quartz-plugins の TypeScript linter | ✅ 済み | 各プラグインに `eslint` + `typescript-eslint` を devDependency として導入し、`package.json` に `lint` スクリプトを追加。`.github/workflows/test.yml` に `quartz-plugins-lint` ジョブを追加（Issue #94）。`quartz-plugins-test` と併せて単一の `quartz-plugins` ジョブへ統合済み（Issue #591。[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。既存 `src/` は型チェック無し（non type-checked）の `tseslint.configs.recommended` でエラーなくパスしたため、ルールの個別無効化は不要だった。マトリクスは 1 job 内ループへ統合済み（Issue #216。[L3](#l3-quartz-plugins-への-eslint-導入-対応済みissue-94)・[L6](#l6-ci-job-数削減と-concurrency-設定-対応済みissue-216)） |
| `.markdownlint.json` の同期検証 | ✅ 済み | ルート直下（Issue #89 で `MD040: false` と `MD024.siblings_only: true` を追加）と配布テンプレートの 2 箇所に存在し、Issue #89 時点で内容が乖離した（配布テンプレートは Wiki ページ向けのため据え置き）。テンプレート側のキーがルート側と矛盾しないことを検証するテストを追加した。[L4](#l4-markdownlintjson-の同期検証-対応済みissue-90) |
| SKILL.md（LLM 駆動部分）の判断品質 eval | ⛔ 廃止 | ハーネス（Issue #103）を Issue #714 で削除した。導入・再設計の Issue の中でしか実行されず、通常の開発フローでは一度も走らなかった。[S1](#s1-skillmd-eval-ハーネス-廃止issue-714) |
| SKILL.md description のトリガー精度検証 | ⛔ 廃止 | ハーネス（Issue #104）を Issue #714 で削除した。S1 と同じ理由。[S2](#s2-description-のトリガー精度の検証-廃止issue-714) |
| SKILL.md 行数上限チェック（lint） | ✅ 済み | `.github/workflows/test.yml` の `checks` ジョブが `tools/check_skill_md_lines.py` を非 blocking で実行（Issue #111。専用ジョブ `skill-md-line-count` からの統合は Issue #591。[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。[L5](#l5-skillmd-行数上限チェック-対応済みissue-111) |
| quartz-plugins 間の `LANG_SEGMENT_RE` 同期検証 | ✅ 済み | `wikicommit-breadcrumbs` / `wikicommit-language-switcher` / `wikicommit-explorer` の 3 プラグインは独立 npm パッケージでワークスペース共有がなく、`.wikicommit/entity/<lang>/` の `<lang>` セグメント判定正規表現をそれぞれ個別に複製している。`tests/test_quartz_plugins_lang_segment_sync.py` が 3 ファイルの正規表現リテラルが byte 単位で一致することを検証し drift を検知する（ランタイム共有はビルドインフラの釣り合いが取れないため見送り。Issue #228） |
| コミットトレーラーのモデル ID がプレースホルダーであることの検証 | ✅ 済み | `tests/test_commit_trailer_placeholders.py` が `.claude/skills/*/SKILL.md`・`CLAUDE.md`・`CONTRIBUTING.md`・`docs/DesignDoc-pipeline.md` の `Co-Authored-By`/`Generated-By`/`Reviewed-By-AI` 行を走査し、`<...>` を除いた残りにモデル名リテラルが残っていないことを検証する（Issue #559。リテラルに戻ると `git log` 上のモデル情報が実行モデルと食い違うが、トレーラーは見た目では正誤が判別できないため機械検知する） |
| 新規 Skill 追加時の `disable-model-invocation` 要否チェック（lint） | ✅ 済み | `.github/workflows/test.yml` の `checks` ジョブ（専用ジョブ `skill-invocation-mode` からの統合は Issue #591。[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）が `tools/check_skill_invocation_mode.py` を非 blocking で実行し、`disable-model-invocation: true` が未設定の SKILL.md を一覧表示（要否そのものの機械判定はしない。Issue #234）。`CONTRIBUTING.md`「SKILL.md を変更する場合の追加手順」にも判断基準を明記。[L7](#l7-skill-追加時の-disable-model-invocation-要否チェック-対応済みissue-234) |
| 配布物内の開発リポジトリパス参照チェック（lint） | ✅ 済み | `.github/workflows/test.yml` の `checks` ジョブが `tools/check_distributed_path_refs.py` を **blocking** で実行し、配布物（`install.sh` が配る 15 Skill と `wikicommit-init` の `scripts/templates/` ペイロード）に `docs/DesignDoc-*.md`・`Issues/`・`dev/` へのパス参照があると失敗させる（Issue #549）。[L9](#l9-配布物内の開発リポジトリパス参照チェック-対応済みissue-549) |
| ルート生成物一覧の単一情報源化と、その不変条件の検証 | ✅ 済み | `init.py` の生成物と `print_next_steps.py` の `git add` 案内は、`.claude/skills/wikicommit-init/scripts/_root_outputs.py` という 1 つの宣言的な一覧から組み立てられる（Issue #642。この一覧は init.py の verbatim コピーも駆動するため、ルート生成物の追加は 1 箇所の編集で済む）。`tests/test_root_outputs.py` が一覧自体の不変条件（variant の妥当性・パスの一意性・宣言したテンプレートの実在・`git add` から意図的に外したパス〈`package-lock.json`〉と条件付きパス〈`.wikicommit/schemaorg-vocab.json`〉の扱い）と、**生成できない 3 つ目の一覧である SKILL.md の散文**が Quartz 限定の生成物を漏らしていないことを検証する。実際に init.py を走らせて案内どおりの `git add` 後に未追跡ファイルが残らないことの検証は `tests/test_smoke_local.py`（Issue #556）が引き続き担う |
| ユーザー向け出力テンプレートへの内部語彙混入チェック（lint） | ✅ 済み | `.github/workflows/test.yml` の `checks` ジョブが `tools/check_skill_user_facing_vocabulary.py` を **blocking** で実行し、`.claude/skills/wikicommit-*/SKILL.md` のユーザー向けフェンス済みテンプレートに `Step N`/`Pass N`・`Route A`/`Route B`・`Issue #NNN`/`PR #NNN` が混入していると失敗させる（Issue #588。`docs/DesignDoc-skills.md` §11.8）。[L10](#l10-ユーザー向け出力テンプレートへの内部語彙混入チェック-対応済みissue-588) |
| 配布スクリプトのコンソール出力言語チェック（lint） | ✅ 済み | `.github/workflows/test.yml` の `checks` ジョブが `tools/check_script_output_language.py` を **blocking** で実行し、`.claude/skills/**/scripts/*.py` の `print()` 出力に日本語が含まれていると失敗させる（Issue #770。`docs/DesignDoc-ScriptSpec.md`「共通規則」）。[L11](#l11-配布スクリプトのコンソール出力言語チェック-対応済みissue-770) |
| Skill の出力に日本語固定が残っていないかのチェック（lint） | ✅ 済み | `.github/workflows/test.yml` の `checks` ジョブが `tools/check_skill_output_language.py` を **blocking** で実行し、`.claude/skills/wikicommit-*/SKILL.md` の全行（散文・フェンス双方）から日本語の文末記号・鉤括弧（`。、？！「」`）を検出する（Issue #808。[L12](#l12-skill-の出力に日本語固定が残っていないかのチェック-対応済みissue-808)） |

---

## テスト戦略

### T1. ローカル完結スモークテスト（✅ 対応済み・Issue #92）

**目的**: 配布漏れ（Issue #86 のような `.claude/skills/`・`.wikicommit/{config.yml,schema/,scripts/}` が一度もコミットされない不具合）を、GitHub 到達性・待ち時間なしに CI（PR 単位）で即検知する。

当初この節は、同種の不具合が重量級 E2E（`run_e2e.sh`。Issue #82）でしか気づけていないことを前提に、その軽量な代替として書かれていた。**その前提は事実として誤っていた** — 実際に配布漏れを見つけたのは E2E ではなくパイロット運用であり（Issue #556 の `install-local-plugins.cjs` は decameron / saitama が発見した）、当の E2E 自身が同じファイルを `git add` リストから落としていた。E2E は Issue #714 で廃止した（下記 S1・S2 と同じ理由）。

**スコープ**: 一時ディレクトリに `git init` した使い捨てローカルリポジトリ上で、`init.py` → `add_source.py` 相当の呼び出し → `wikicommit-merge` のコミット手順相当（品質チェックの外部ツール呼び出し・GitHub API 呼び出しは含まない）を実行し、以下を assert する。

- `.claude/skills/` が `git status` 上で追跡対象（untracked のまま放置されない）になっていること
- `.wikicommit/config.yml`・`.wikicommit/schema/`・`.wikicommit/scripts/` が同様に追跡対象であること
- 生成された ソース管理ファイル・Wiki ページが正しいパスに存在すること

**除外**: LLM 呼び出し（ページ生成・レビューサブエージェント）・実際の GitHub API 呼び出し（PR 作成・auto-merge）・lychee 等の外部通信を伴うチェック。**廃止した E2E が固有に担っていた領域（`review-issue-close-sync.yml` の実挙動・Pages の実公開・`gh pr merge` の `mergeStateStatus` ポーリング）に自動テストの代替は無い** — いずれも実績としてはパイロット運用が先に不具合を見つけている（Issue #403・#544・#456）。

**配置**: `tests/test_smoke_local.py`（pytest から `subprocess` で `git`・対象スクリプトを呼び出す構成）。`git add` 案内どおりにステージした後 `git status --porcelain` が空になることまで検証する（非 `--quartz` 経路は Issue #92 の当初実装から、`--quartz` / `--quartz-pages` 経路の逆向き検証は Issue #556 で追加）。

### T2. `init.py` / `add_source.py` のユニットテスト（✅ 対応済み・Issue #88）

ハッシュ計算・ソース管理ファイルの `status` 遷移・ディレクトリ生成という決定論的ロジックにテストが 1 つもなかった。[DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) 相当の粒度で以下の関数を対象に `tests/test_init.py` / `tests/test_add_source.py` を追加した（PR #95）。

| ファイル | 対象関数 | assert 対象 |
|---|---|---|
| `.claude/skills/wikicommit-generate/scripts/add_source.py` | `sha256_file` | 既知内容のファイルに対する `sha256:` 値の正確性 |
| 同上 | `mgmt_path_for_file` / `mgmt_path_for_url` | ソース管理ファイルの生成先パス計算（[DesignDoc-data.md](DesignDoc-data.md) §4.3 のパス規則） |
| 同上 | `parse_frontmatter_status` / `update_frontmatter_status` | `status` 遷移 `pending → generated → partial → outdated → failed`（[DesignDoc-data.md](DesignDoc-data.md) §4.3 の状態表） |
| 同上 | `process_file` / `process_url` | 新規登録（hash 計算・`pending` 作成）／ハッシュ一致時のスキップ／ハッシュ一致かつ既存 `status: outdated` → `pending` へ復帰（ハッシュが元に戻った場合）／ハッシュ不一致時は `status: outdated` に設定（hash 値は更新せず据え置き）／既に `outdated` の状態でさらにハッシュ不一致 → 変更なし |
| `.claude/skills/wikicommit-init/scripts/init.py` | `main` | `.wikicommit/`・`.claude/skills/` のディレクトリ構造がテンプレート通りに生成されること／既存ファイルは上書きせずスキップすること（CLAUDE.md に記載の「既存ファイルスキップ判定はファイルの存在有無のみを見る」仕様の回帰防止） |

### T3. quartz-plugins への vitest 導入（✅ 対応済み・Issue #93）

`i18n` ロケール選択・`review_status` バナー描画・JSON-LD の frontmatter マッピングが無テストで、Issue #62（JSON-LD 埋め込みプラグインが Quartz v5 のプラグインローダーにより無効化される）のような不具合が実デプロイまで発覚しなかった前例がある。

**注意**: `quartz-plugins/` の canonical コピーは Issue #81 でリポジトリルートから削除済み。唯一のコピーは配布テンプレート `.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-banner/` と `.../wikicommit-jsonld/` 配下にある。vitest の導入・実行もこのパスを対象にした。

| プラグイン | 対象 | assert 対象 |
|---|---|---|
| `wikicommit-banner` | `src/i18n/index.ts` + `src/i18n/locales/*.ts` | ロケール選択（`i18n("ja-JP")` / `i18n("en-US")`）・未対応ロケール（例: `fr-FR`）や未指定時の `en-US` フォールバック |
| 同上 | `src/components/WikiCommitBanner.tsx` | `review_status: pending`（未設定時のデフォルト含む） / `reviewed` それぞれでのバナー表示分岐・`generated_at` / `generated_by` の表示（未設定時は `unknown` ラベルにフォールバック） |
| `wikicommit-jsonld` | `src/index.tsx` | frontmatter → JSON-LD プロパティのマッピング（[DesignDoc-publish.md](DesignDoc-publish.md) §8.3 の対応表。`sameAs`/`wikidata` 変換・型固有フィールド・`status: removed` やカスタム型での `null` 返却・XSS エスケープを含む）・`htmlPlugins()` / `externalResources().additionalHead` 経由での出力（Issue #62 の再発防止） |

`preact-render-to-string`（`wikicommit-banner` のみ）を追加の devDependency として導入し、コンポーネントの描画結果を HTML 文字列として assert した。CI（`.github/workflows/test.yml`。導入当初は `quartz-plugins-test` ジョブのプラグインごとのマトリクス、Issue #216 で 1 ジョブ内ループへ、Issue #591 で `quartz-plugins` ジョブへ統合）はテンプレートディレクトリ内に `cd` し、`npm ci && npm test` を実行する（配布物のためリポジトリルートの `package.json` には依存を追加していない）。

> **i18n の選択キーは `frontmatter.lang` 優先に変更済み（Issue #378）**: 本 Issue（#93）の時点では、i18n の実際の選択キーは `cfg.locale`（Quartz サイト全体設定）のみで、ページの `lang` frontmatter を直接読んでいなかった。日英混在 Wiki では `en/` の翻訳ページにもサイト全体設定の言語（例: `ja-JP`）のキャプションが表示される不具合があったため、Issue #378 で `wikicommit-banner`・`wikicommit-sources` の両方に `resolveLocale(frontmatterLang, cfgLocale)`（`src/i18n/index.ts`）を追加し、`frontmatter.lang` → `cfg.locale` → `en-US` の優先順位でロケールを解決するよう変更した。

<!-- -->

> **`tsup.config.ts` の共有化・`noExternal` 絞り込み・`quartz-plugins-test`/`quartz-plugins-lint` ジョブのガード追加（Issue #379）**: `wikicommit-banner`・`wikicommit-jsonld`・`wikicommit-sources` の3プラグインが個別にコピーしていた `SINGLETON_EXTERNALS`（Quartz 本体とシングルトン共有すべき preact 等の一覧）と共通の `defineConfig` オプションを `quartz-plugins/_shared/tsup.base.ts`（npm パッケージではない、相対 import 専用の共有モジュール）に切り出し、各プラグインの `tsup.config.ts` はそこから `baseTsupOptions` を spread する形に変更した。あわせて `wikicommit-banner`・`wikicommit-sources` の `noExternal: [/.*/]`（tsup/esbuild の実装上 `external: SINGLETON_EXTERNALS` を無効化してしまう設定。実測は tsup v8.5.1）を `wikicommit-jsonld`（Issue #186 で先に修正済み）と同じ `["preact", "preact/jsx-runtime"]` に絞った。`wikicommit-banner`/`wikicommit-sources` にも `wikicommit-jsonld/src/build.test.ts`（Issue #186）と同型の `build.test.ts` を追加し、実際に `npx tsup` を実行して `dist/index.js` に bare `import ... from "preact"` が残らないことを検証する。各プラグインの `tsconfig.json` は `tsup.config.ts` を `include` から `exclude` に移した（`_shared/tsup.base.ts` が各プラグインの `rootDir` の外にあるため、`tsc --noEmit` の対象に含めると TS6059 になる。ビルド自体は tsup が独自の esbuild ベースのローダーで `tsup.config.ts` を読み込むため無関係）。副作用として、`.github/workflows/test.yml` の `quartz-plugins-test`/`quartz-plugins-lint` ジョブが `quartz-plugins/*/` glob でプラグインディレクトリを動的検出する既存ロジック（Issue #235）に対し、`_shared/`（`package.json` を持たない）を誤って対象に含めないよう `package.json` の有無で skip するガードを追加した。`wikicommit-breadcrumbs`・`wikicommit-explorer`・`wikicommit-language-switcher`・`wikicommit-search` の4プラグインは同じ `noExternal: [/.*/]` を今も使っているが Issue #379 のスコープ外のため未対応（`Issues/p3-142-remaining-quartz-plugins-noexternal-drift.md` として起票）。

---

## Linter戦略

### L1. markdownlint-cli2 の CI 組み込み

**済み（Issue #89、Issue #134 で `CONTRIBUTING.md` を追加）**。`.github/workflows/test.yml` に `markdownlint` ジョブを追加し、`npx markdownlint-cli2 "docs/**/*.md" "README.md" "CONTRIBUTING.md"` を blocking で実行する。[DesignDoc-CISpec.md](DesignDoc-CISpec.md) の「常に warning のみ（Phase 2）」という blocking/warning 分類はランタイム品質ゲートの話であり、開発リポジトリ自体の CI（本書のスコープ）とは別軸のため blocking とした。

対象パスは `docs/`・`README.md`・`CONTRIBUTING.md` のみとした。`dev/`（研究メモ・PRD ドラフト）と `Issues/`（過去の Issue ドラフト。実体は GitHub Issues 側にあり本書の対象外）は既存設定でのスタイル逸脱が計 300 件超と広範であり、このリポジトリの正本ドキュメントではないため対象外とした。`CONTRIBUTING.md` は外部貢献者が最初に読むドキュメントであり `README.md` と同様の性質のため対象に含めた。なお Issue #660 は `dev/research/` を `docs/research/` へ移し、`docs/**/*.md` のうち `docs/research/**` だけを `.markdownlint-cli2.jsonc` の `ignores` で対象外にしていたが、その後 research/ を公開しない判断に至り `dev/research/` へ戻した（着手前調査を凍結した記録であり、実装が始まる前に何を信じていたかを残すもので、現行の設計・実装とは別物であるため）。`dev/` は元から lint 対象外なので、`ignores` 専用だった `.markdownlint-cli2.jsonc` は不要になり削除した（ルール本体は従前どおり `.markdownlint.json` 側にあり、この設定ファイルが無くても `markdownlint-cli2` はそちらを読む）。既存の逸脱を解消するため `.markdownlint.json` に `MD040: false`（コードフェンスの言語指定省略を許容。ディレクトリツリー・疑似コードの記述が多いため）と `MD024: { "siblings_only": true }`（`DesignDoc-ScriptSpec.md` のようにスクリプトごとに「目的」「使用場面」等の同名見出しが繰り返される構成を許容）を追加した。さらに `docs/DesignDoc-phases.md`・`docs/DesignDoc-data.md`・`docs/DesignDoc-ScriptSpec.md` の MD012（余分な空行）・MD032（リスト前後の空行）・MD036（見出し代わりの強調）はドキュメント内容を変えない範囲で直接修正した。

### L2. Python linter（ruff）の導入（✅ 対応済み・Issue #91）

`.wikicommit/scripts/`・`.claude/skills/*/scripts/` の Python コードに、ハッシュ計算・ソース管理ファイルの `status` 遷移という決定論的ロジックを持つにもかかわらず、スタイル・未使用変数・型崩れを検知する仕組みが現状皆無だった。`pyproject.toml` の `[project.optional-dependencies].dev` に `ruff` を追加し、`.github/workflows/test.yml` に `ruff check .` を実行する `ruff` ジョブを追加した。

デフォルトルールセット（`E`/`F` 系）で `ruff check .` を実行したところ、`validate_frontmatter.py`（`.wikicommit/scripts/` と配布テンプレートの両方）のプレースホルダーなし f-string 1 件と、`tests/test_check_ingest_freshness.py` の未使用変数 1 件が検出されたため修正した。ルールセット自体の個別無効化は不要だった。

配布テンプレートのミラー（`.claude/skills/wikicommit-init/scripts/templates/scripts/`）は `tests/test_template_mirror_sync.py` により `.wikicommit/scripts/` とバイト単位で内容が一致することが保証されているため、同一の違反を二重に報告するだけで検知漏れの防止には寄与しない。`[tool.ruff].extend-exclude` でこのミラーディレクトリを除外した。`tests/` は lint 対象に含めた（決定論的なテストコードであり、通常の Python コードと同様にスタイル・未使用変数の検知が有用なため）。

### L3. quartz-plugins への ESLint 導入（✅ 対応済み・Issue #94）

`i18n` ロケール選択・`review_status` バナー描画・JSON-LD の frontmatter マッピングのロジックが lint なしで書かれており、Issue #62 のような不具合の再発予防に寄与する。対象は T3 と同じく配布テンプレート配下（`.../templates/quartz-plugins/wikicommit-banner/`・`.../wikicommit-jsonld/`）。

各プラグインに `eslint` と `typescript-eslint` を devDependency として追加し、`eslint.config.js`（flat config）で `tseslint.configs.recommended`（non type-checked）を適用。`package.json` に `"lint": "eslint ."` を追加し、`.github/workflows/test.yml` に T3 と同形の `quartz-plugins-lint`（マトリクス）ジョブを追加した。既存 `src/` は追加ルールの無効化なしでパスした。型チェックは既存の `typecheck`（`tsc --noEmit`）スクリプトと役割が重複するため、type-aware なルール（`parserOptions.project` を要する構成）は導入しなかった。

### L4. `.markdownlint.json` の同期検証（✅ 対応済み・Issue #90）

ルート直下（`.markdownlint.json`）と配布テンプレート（`.claude/skills/wikicommit-init/scripts/templates/.markdownlint.json`）の 2 箇所に存在する。Issue #89 でルート側にのみ `MD040: false` と `MD024.siblings_only: true` を追加したため、2026-07-06 時点で内容が乖離している。ルート側はこのリポジトリ自身の `docs/`・`README.md`（設計ドキュメント・ディレクトリツリーや疑似コードを多用）向けの調整であり、配布テンプレート側は利用者の `.wikicommit/entity/**/*.md`（LLM が生成する Wiki ページ）向け（対象ルールは [DesignDoc-CISpec.md](DesignDoc-CISpec.md) の `.markdownlint.json` 設定方針で MD041・MD013・MD033 の 3 件のみと定義済み）であるため、両者が同一である必然性はない。

Issue #90 では byte 単位の完全一致ではなく、`tests/test_template_mirror_sync.py::test_markdownlint_template_rules_do_not_contradict_canonical` として、テンプレート側の各キーがルート側にも存在し値が一致すること（矛盾のないこと）のみを検証する形で実装した。ルート側だけの追加ルール（`MD040`・`MD024`）は意図的な乖離として許容し、テンプレート側のルールが誤って上書き・削除・変更された場合にのみ検知する。

### L5. SKILL.md 行数上限チェック（✅ 対応済み・Issue #111）

Anthropic 公式の skill-creator（SKILL.md を作成・改善・評価するためのメタスキル）は、SKILL.md を 500 行以内（目安）に収め、決定論的な繰り返し処理は `scripts/` に切り出すことを推奨している。WikiCommit も [DesignDoc-skills.md](DesignDoc-skills.md) §11.5 のスクリプト委譲パターンで同種の方針を採るが、行数の逸脱を機械的に検知する仕組みがなかった。

`.claude/skills/*/SKILL.md` の行数を計測し、500 行を超える場合に WARNING を出す軽量スクリプト（`tools/check_skill_md_lines.py`。`wc -l` ベース）を追加した。`.github/workflows/test.yml` で非 blocking で実行する（「目安」であり厳格な仕様ではないため blocking にはしない）。導入当初は専用の `skill-md-line-count` ジョブだったが、Issue #591 で `checks` ジョブへ統合した（[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。

2026-07-07 時点の最大は `wikicommit-merge`（272行）で当時は超過していなかったが、Phase 2 以降の Skill 追加（`wikicommit-review`・`wikicommit-fix`・`wikicommit-remove`・`wikicommit-ask`・`wikicommit-search`・`wikicommit-status`）に備えた早期警告として導入した。

**運用**: L1〜L4 と同様に毎 PR 自動実行（`.claude/skills/*/SKILL.md` を変更する PR で自動的にトリガーされる）。判定は機械的だが blocking ではないため、レビュアーが CI の Checks 欄に出た WARNING に気づいた上で「`scripts/`・`references/` へ切り出すべきか」を都度判断する。継続的なメンテナンス作業は不要。

### L6. CI job 数削減と concurrency 設定（✅ 対応済み・Issue #216）

`test.yml` が `pull_request` / `push (main)` の二重トリガーで 1 run あたり matrix 込み 18 jobs（pytest ×3 Python バージョン、`quartz-plugins-test` ×6 プラグイン、`quartz-plugins-lint` ×6 プラグイン、他 3 job）を並列実行していた。各 job の実処理は 15〜30 秒程度だが、GitHub Actions の課金は job 実行時間を 1 分単位で切り上げるため実質 1 job = 1 分としてカウントされ、高頻度な PR/マージサイクルではジョブ数がそのままコストになる。以下の対応で 1 run あたり 6 jobs まで削減した（この見直しに至った経緯と消費量の実測は `dev/ci-cost-notes.md`）。

1. **matrix のループ統合**: `quartz-plugins-test` / `quartz-plugins-lint` の 6 プラグイン matrix（各 6 jobs、計 12 jobs）を、それぞれ 1 job 内でプラグインディレクトリを bash ループして `npm ci && npm test`（または `npm run lint`）を実行する形に統合した（12 jobs → 2 jobs）。`actions/setup-node` の `cache-dependency-path` はグロブパターン（`.../quartz-plugins/*/package-lock.json`）を渡すことで全プラグイン分の lock file をキャッシュキーに含められるため、matrix 撤去後もキャッシュは機能する。
2. **pytest の Python バージョン matrix を代表 1 バージョンに削減**: `["3.11", "3.12", "3.13"]`（3 jobs）から `pyproject.toml` の `requires-python = ">=3.11"` の下限に合わせた `"3.11"` 単独（1 job）に絞った。**トレードオフ**: 3.12/3.13 固有の非互換（将来 3.11 で削除予定の非推奨 API 等）を CI で検知できなくなる。WikiCommit の `.wikicommit/scripts/`・`.claude/skills/*/scripts/` は標準ライブラリ（`hashlib`・`pathlib`・`subprocess` 等）と `pyyaml` のみに依存する薄いスクリプト群であり、バージョン間の挙動差が生じる可能性が低いこと、複数バージョン CI は `matrix.python-version` 1 行を戻すだけでいつでも復元できることから、Actions minutes 節約を優先し単一バージョンとした。下限（3.11）を代表に選んだのは、新しいバージョンでのみ通り古い環境で失敗する非互換（`match` 文の対象拡大等、新しい構文機能の意図しない使用）の方が、逆方向（3.11 は通るが 3.13 で deprecated warning が出る等)より実害が大きいと判断したため。
3. **concurrency 設定の追加**: `group: ${{ github.workflow }}-${{ github.ref }}` + `cancel-in-progress: ${{ github.event_name == 'pull_request' }}` を追加し、同一 PR への連続 push で古い run を自動キャンセルする。`cancel-in-progress` を `pull_request` イベントに限定したのは、`push (main)` は `github.ref` が常に `refs/heads/main` で固定されるため、無条件にすると連続 squash merge 時に先発の post-merge run が後発の push でキャンセルされ、マージ後にしか顕在化しない不具合の検証漏れが起こりうるため。

`push (main)` / `pull_request` の二重トリガー自体の削除は本 Issue のスコープでは見送った（squash merge 後にのみ失敗するケースを見逃すリスクがあるため）。`wikicommit-merge` がページ単位で後レビュー PR を作成する設計（[DesignDoc-pipeline.md §6.2](DesignDoc-pipeline.md)）による run 頻度の高さ自体も、Issue #195 で意図的に上限を撤廃した仕様のため変更していない。今回の対応後も Actions minutes 消費が改善しない場合は、これらの再検討を行う。

### L7. Skill 追加時の disable-model-invocation 要否チェック（✅ 対応済み・Issue #234）

Issue #215（`Issues/registered/p3-062-skill-invocation-mode-audit.md`）で副作用のある書き込み系 Skill に `disable-model-invocation: true` を付与し、Claude Code の自動発火判定から除外する運用を確立したが、この判断基準を将来追加される新規 Skill にも適用させる仕組みがなかった（CI にも `CONTRIBUTING.md` にも言及がなく、追加を忘れても誰も気づけない）。

以下の2点で対応した:

1. **lint（非 blocking）**: `.claude/skills/*/SKILL.md` の frontmatter を走査し、`disable-model-invocation: true` が未設定のものを一覧表示する軽量スクリプト（`tools/check_skill_invocation_mode.py`）を追加した。`.github/workflows/test.yml` で非 blocking で実行する（導入当初は専用の `skill-invocation-mode` ジョブ。Issue #591 で `checks` ジョブへ統合。[L8](#l8-ci-ジョブ構成の集約によるコスト削減-対応済みissue-591)）。副作用の有無の判定自体は人間の判断を要するため、スクリプトは機械的に「あるべきか」を判定せず、単に現状の一覧を出すのみに留めた（Issue #234 の対応方針案どおり）
2. **ドキュメント化**: `CONTRIBUTING.md`「SKILL.md を変更する場合の追加手順」に、新規 SKILL.md 追加時は副作用の有無に応じて `disable-model-invocation` の要否を検討する旨と、上記 lint の一覧に現れた場合の確認を促す文言を追加した

**運用**: L5 と同様に毎 PR 自動実行される。判定は機械的な一覧表示に留まるため、レビュアーが CI の Checks 欄の出力を見て、新規 Skill が意図して未設定になっているか（読み取り専用等）を都度判断する。

### L8. CI ジョブ構成の集約によるコスト削減（✅ 対応済み・Issue #591）

`test.yml` のジョブ数が増え、1 run あたりの課金分数が無視できない水準に達したため、ジョブ構成を見直して 7 ジョブ → 2 ジョブに削減した。GitHub Actions は**ジョブ単位で分単位に切り上げて**課金するため、実処理の短いジョブを並べること自体がコストになる。

> **CI コストの運用記録は非公開の開発記録（`dev/ci-cost-notes.md`）に置いた** — 無料枠の使い切りとその見分け方・spending limit の扱い・実測した課金分数・private リポジトリの分数がどのアカウントに課金されるかは、開発アカウント固有の事情であり設計判断そのものではないため。本節に残したのはジョブ構成の設計とそのトレードオフである。

#### 採用した削減策

以下の 3 点を適用した。

1. **`paths-ignore` の追加**: `Issues/**` と `dev/**/*.md` のみの変更で 7 ジョブすべてが起動していた。`main` への push 117 件のうち 40 件（34%）が該当する。これらのパスがどのジョブからも参照されないことは確認済み（markdownlint の対象は `docs/`・`README.md`・`CONTRIBUTING.md` のみ〈L1〉、ruff は Python のみ、pytest は全テストが `tmp_path` 上で動き実リポジトリの `Issues/` ツリーを読まない、`check_skill_*` は `.claude/skills/` のみ、quartz-plugins は `templates/quartz-plugins/` のみ）。**`dev/` 全体を除外してはいけない** — `dev/scripts/*.py`・`tools/*.py` が ruff / pytest の対象であるため。（この判断は当初、廃止した 2 つの検証ハーネス〈S1・S2 と旧 E2E〉が将来 CI に載りうることも理由に挙げていた。Issue #714 で両者を削除したが、結論そのものは `dev/scripts/*.py` を理由として変わらない。）
2. **短いジョブ 5 本の 1 ジョブ統合**: `pytest` / `ruff` / `markdownlint` / `check_skill_md_lines` / `check_skill_invocation_mode` は実時間の合計が 1.5 分未満にもかかわらず 5 分課金されていた。L6 が matrix 統合で採った「`set -e` で即終了させず、各チェックの失敗を記録してループを継続し、最後にまとめて `exit` する」パターンをそのまま流用し、`checks` ジョブに統合した（前方のチェックの失敗で後続が未検証のままスキップされる後退を避けるため）。依存インストール（`pip install -e '.[dev]'` / `npm ci`）も同じ仕組みで包んでいる — 独立したステップに切り出すと、片方のインストールが失敗しただけでジョブがそこで打ち切られ、統合前は別ジョブとして走っていた無関係なチェック（例: pip 失敗時の markdownlint、npm 失敗時の pytest / ruff）まで未検証になるため。
3. **quartz-plugins の 2 ジョブ統合**: `quartz-plugins-test` と `quartz-plugins-lint` はそれぞれ全プラグインに対して `npm ci` を実行しており、同一の依存インストールが 1 run あたり「プラグイン数 × 2」回走っていた（Issue #591 適用時点では 8 プラグイン・16 回。プラグイン数はジョブ内のループが動的検出するため増減する〈Issue #235〉。現在は 9 — 内訳は `dev/ci-cost-notes.md`）。1 ジョブに統合して「プラグイン数 × 1」回に半減した。あるプラグインの `npm test` が失敗しても同プラグインの `npm run lint` は実行する（統合前の独立性を維持）。`npm ci` 自体が失敗したプラグインのみ、test / lint をまとめてスキップする。

結果としてジョブ数は 7 → 2 になった。

#### トレードオフ

- **チェック一覧の粒度が落ちる**。PR の Checks 欄で 7 つのチェックが個別に緑/赤で見えていたものが 2 つになる。どのチェックが落ちたかは `::group::` と `::error::` のアノテーションで判別する。
- **PR フィードバックまでの実時間は伸びる**。統合により test と lint が直列になるため。GitHub Actions の課金はジョブごとの実行時間の合計であり並列度では減らないため、課金分数の観点では統合が有利という判断。
- **`paths-ignore` でスキップされた run は「成功」ではなく「未実行」になる**。ブランチ保護で required status check に指定すると PR がマージできなくなる（GitHub の既知の落とし穴）。本リポジトリは GitHub Free の private リポジトリで branch protection 自体が利用できない（`GET /repos/{o}/{r}/branches/main/protection` が `403 Upgrade to GitHub Pro or make this repository public to enable this feature` を返す）ため現状は問題にならないが、public 化または GitHub Pro へ移行した際はこの前提が変わる。`test.yml` のコメントにも同じ注意を残した。
- `paths-ignore` は「**変更ファイルが全て一致したときにスキップ**」という意味であり、`Issues/` 46 件 + `docs/` 1 ファイルのような混在コミットではスキップされない。これは安全側の挙動でありそのままとする。

#### 見送った案

- **`node_modules` 自体の `actions/cache` 導入**: 起票時点ではキャッシュ復元が `npm ci` より速いかを実測できていないため見送った（当時は CI 自体が回せず実測できなかった。事情は `dev/ci-cost-notes.md`）。その後に実測し、**採用しないと確定した**（Issue #641。実測値は `dev/ci-cost-notes.md`）。
- **`push`（main）側の `cancel-in-progress` を有効にする**: L6 で「各コミットの検証結果を残す」ために意図的に `false` にしたものであり、削減幅（8 月の cancelled は 7 件）に対して失うものが大きい。
- **spending limit の引き上げ**: 上記 3 点を入れた後の残りに対して判断する → 実測の結果、**採らない**と確定した（Issue #641。この判断は開発アカウント固有の課金事情に依るため、根拠は `dev/ci-cost-notes.md` に置いた）。
- **リポジトリの public 化**: Issue #151 で「`wikicommit-dev2` は private のまま、`wikicommit/wikicommit` へスナップショット push する」と確定済みであり方針と衝突する。
- **セルフホストランナー**: GitHub-hosted の分数を一切消費しないため原理的には根本解消しうるが、CI が「開発機の電源が入っているときだけ動く」ものになり管理コストも増える。上記 3 点で足りるかを先に見てから再検討する → 実測の結果、当面は現状の構成で足りる見込みとなったため引き続き見送る（Issue #641。実測値は `dev/ci-cost-notes.md`）。

### L9. 配布物内の開発リポジトリパス参照チェック（✅ 対応済み・Issue #549）

`install.sh` が配る 15 Skill と、`wikicommit-init` がユーザーの `.wikicommit/` へ展開する `scripts/templates/` のペイロードは、いずれも `docs/`・`Issues/`・`dev/` を持たないリポジトリに着地する。それらへのパス参照は配布先で原理的に追跡できず、SKILL.md の場合は Skill 起動のたびに全文がエージェントのコンテキストへ読み込まれるコストも払い続けることになる（Issue #549 の実測で SKILL.md だけで 83 箇所）。

`tools/check_distributed_path_refs.py` がこれを機械的に検出する。L5・L7 と異なり **blocking**（ERROR があれば exit 1）とした — 「目安」や「人間の判断を要する要否」ではなく、「配布先に存在しないパスを書いた」という機械的に判定できる誤りであり、再混入をその場で止めるのが目的の回帰ガードであるため。

判定の細部:

- `docs/` は実際の内容（`DesignDoc-*.md` のみ）に合わせて絞り込む。`wikicommit-collect` の候補一覧が例示する `docs/notes/meeting-0512.md` のような、ユーザー側の架空パスを誤検出しないため。`docs/` プレフィックスの有無は問わない — 素の `DesignDoc-data.md §4.2` も同じ未配布ファイルを指しており配布先では同様に追跡できないため、プレフィックス付きの形だけを見ると簡単に迂回できてしまう
- 逆方向（`docs/DesignDoc-*.md` から SKILL.md への参照）は開発リポジトリ内に閉じているため対象外。追跡の担い手を「docs → 配布物」の一方向に寄せる、という整理
- `.claude/skills/implement-issue`・`review-and-merge`（配布対象外の内部 Skill）と `node_modules/` は走査対象外
- `scripts/templates/quartz-plugins/` も他の配布物と同じ `ERROR` 対象である（Issue #644）。導入当初は `DEFERRED:` として出力するだけで `errors` にはカウントしていなかった — `dist/` がコミット済みのビルド成果物であり `src/` だけを直すと両者が食い違うため、プラグイン単位の再ビルドを伴う対応を Issue #644 として切り出していた。同 Issue で 10 箇所の参照を削除し、対象 3 プラグイン（`wikicommit-explorer`・`wikicommit-properties`・`wikicommit-sources`）を `npm ci && npm run build` で再ビルドして `dist/` を `src/` と同期させたため、`DEFERRED_DIRS`・`is_deferred()`・`SUMMARY:` の `deferred=` を削除して一本化した。参照を消す作業は「`src/` を直して再ビルドする」までが一組であり、これを担保するため `.map` も `TEXT_SUFFIXES` に加えている — `.js.map` の `sourcesContent` は `src/` の各ファイルをそのまま抱える一方、バンドラは `dist/*.js` からコメントの大半を落とすため、実際に配布される唯一の写しが `.map` だけということが多い（Issue #644 で削除した 10 箇所も、3 プラグイン全ての `.map` に載っていたのに対し `dist/*.js` に残っていたのは 1 プラグインだけだった）。`dist/*.js` しか見ないと、再ビルドし忘れが無言で通る

---

### L10. ユーザー向け出力テンプレートへの内部語彙混入チェック（✅ 対応済み・Issue #588）

`docs/DesignDoc-skills.md` §11.8 は、Skill がユーザーに見せる出力に内部手順番号（`Step N`/`Pass N`）・設計語彙（`Route A`/`Route B`）・内部トラッカー参照（`Issue #NNN`/`PR #NNN`）を露出させないことを定めている。いずれもユーザーの手元には届かない — `docs/` は配布スナップショットに含まれず、Issue 番号に至っては参照先が private リポジトリで公開後も追跡手段が無い。

**散文だけでは維持できていなかった**。§11.8 を制定した Issue #492 の後に、Issue #539 が `wikicommit-status` の結果表示テンプレートへ `(informational — see Step 5)` という新たな漏れを持ち込んでいる。制定後に新規の違反が通った以上、L5・L7 と同じ非 blocking の警告では目的を果たさないため、L9 と同じく **blocking**（exit 1）とした。

`tools/check_skill_user_facing_vocabulary.py` が `.claude/skills/wikicommit-*/SKILL.md` のフェンス済みコードブロックのうち、info string が無いか `markdown`/`md`/`text` のもの（＝ Skill がユーザーへそのまま出力するブロック）を走査する。`bash`/`json`/`yaml` 等はコマンド・データ形式でありユーザー向け散文ではないためスキップする。例外はフェンス直前の行に理由付きの HTML コメント（`<!-- skill-vocabulary-exception: <理由> -->`）を置いて明示し、理由が空のマーカーはそれ自体をエラーとする — 例外を足すたびに §11.8 の判定基準（読み手は誰か）を意識的に言い直させるため。

**既知の限界**: フェンス済みテンプレートしか見ない。Issue #492 が実際に踏んだ漏れは、エージェントが手順指示の散文中の「Step 5」を読んで**自分の言葉で**確認質問を組み立てた際に混入したものであり、テンプレートに存在しない文言のため本チェックでは検出できない。散文側のガードレールを置き換えるものではなく補完するものである。

`tests/test_check_skill_user_facing_vocabulary.py` がスクリプト自体の挙動（検出パターン・info string による除外・例外マーカー・ネストしたフェンス・未終端フェンス）に加えて、**実際の `.claude/skills/` が検出 0 件であること**も検証する。

---

### L11. 配布スクリプトのコンソール出力言語チェック（✅ 対応済み・Issue #770）

`docs/DesignDoc-ScriptSpec.md`「共通規則」は、配布される Python スクリプトが stdout・stderr へ出す文字列を英語で書くと定めている。読み手は `/wikicommit-status`・`/wikicommit-merge` を実行する運用者と、その出力を読んで次の行動を決めるエージェント自身であって、Wiki の読者ではない — Issue #405 が管理ファイルの見出しについて下したのと同じ判断である。加えて診断メッセージは「機械可読な出力は翻訳しない」という国際化の定石が最もよく当てはまる類型で、エラー文字列はそのまま検索エンジンと Issue に貼られるため、訳すと同じ問題を踏んだ人同士が同じ文字列に辿り着けなくなる。

**方針が無い間に新旧が割れていた**。Issue #770 の時点で、`print()` に日本語を含むスクリプトが 20 本・英語のみが 15 本あり、分かれ目は役割でも読み手でもなく執筆時期だった。`set_frontmatter_field.py` と `reset_review_on_content_change.py` に至っては、本体の構造化出力が英語で argparse 由来の引数エラーだけが日本語という混在状態にあった。L9・L10 と同じく **blocking**（exit 1）とする。

`tools/check_script_output_language.py` が `ast` で `.claude/skills/**/scripts/*.py` を解析し、`print()` の引数に現れる文字列リテラル（f-string の定数部・`+` による連結を含む）に CJK があれば ERROR にする。`grep` ではなく `ast` を使うのは、日本語のまま据え置くコメント・docstring を巻き込まないためである。補間される値は対象にしない — 実行時にページのタイトルや他モジュールの例外文が入るだけで、スクリプト自身が書いたメッセージではない。

**既知の限界**: `print()` の引数しか見ない。メッセージを**戻り値として返す**スクリプト（`_frontmatter.py` がその形で、エラー文を呼び出し側へ渡し、そちらが出力する。同ファイル自身の文字列は Issue #770 で英語化済みだが、そこに日本語が戻ってもこの走査には掛からない）はこの走査では拾えず、手作業での確認になる。公開ページに出る読者向けラベル（`convert_wikilinks.py` の `ROOT_INDEX_LABELS` / `OVERVIEW_LABELS` / `SOURCE_*_LABELS`）も同じ理由で走査対象外だが、こちらは日本語であることが正しい層であり、限界ではなく設計である。

`tests/test_check_script_output_language.py` がスクリプト自体の挙動（`print()` リテラル・f-string 定数部の検出、補間値・コメント・docstring・非 `print()` リテラルの除外、`scripts/` 以外のディレクトリの非走査）に加えて、**実際の `.claude/skills/` が検出 0 件であること**も検証する。

### L12. Skill の出力に日本語固定が残っていないかのチェック（✅ 対応済み・Issue #808）

Issue #770・#772・#773 は同じ問いに 3 回答えており、答えは毎回**「言語は読み手に従う」**である — 運用者・エージェント向けの診断は固定英語（#770）、読者・報告者向けは Wiki の `primary_lang`（#773）、配布物そのものは英語（#772）。**このどれからも「SKILL.md に日本語を直書きする」は出てこない**が、Issue #808 はそういう箇所を 6 件見つけた。規則は「誰かがたまたま見たとき」にしか働いていなかったことになる。L9〜L11 と同じく **blocking**（exit 1）とする。

とりわけ鋭いのは `wikicommit-fix` Step 7 の Issue コメントで、**読み手は公開ページの報告リンクから Issue を立てた任意の読者**である。しかも同 Skill は `gh issue close` を意図的に行わない設計なので、コメントが読めなければ報告者は何をすべきか分からず Issue が開いたまま残る。イタリア語 Wiki の報告者に日本語のコメントが返っていた。

**この箇所の言語は Issue #824 でさらに絞り込まれ、`primary_lang` ではなく Step 2 で特定した対象ページの `lang`（＝報告者が実際に読んだページ）になった** — `targets` を持つ Wiki では両者が食い違い、翻訳ページの報告者には `primary_lang` でも届かないため。上段の「読者・報告者向けは `primary_lang`」は追跡 Issue 本文（#773）についての要約であり、この Skill にはそのまま当てはまらない。本チェック自体の対象（SKILL.md に日本語を直書きしないこと）はどちらの決定にも依存しない。

`tools/check_skill_output_language.py` が `.claude/skills/wikicommit-*/SKILL.md` の**全行**を走査する。L10 と違ってフェンスに限定しない — Issue #808 の 6 件のうちフェンス内にあったのは 1 件だけで、残る 5 件は通常の指示散文に置かれた引用文字列だった。内部限定 Skill（`implement-issue` / `review-and-merge`）を除く線引きは L10 と共有する。

**検出するのは CJK ではなく日本語の文末記号・鉤括弧（`。、？！「」`）である。** SKILL.md には正当な日本語の**例示**（ページタイトル・エンティティ名・検索語・ソースからの引用）が多数あり、CJK の有無では `"生年を1981年に修正して"`（例示の引数）と `"対象言語がありません。"`（実際に出力するエラー文）を区別できない。文末記号なら区別できる — 出力される日本語の散文はそれを持ち、タイトルや検索語は持たない。Issue #808 の 6 件に対して実測すると、**例示への誤検出 0 件で 5 件を検出**する。CJK 一律で判定すると SKILL.md 内の例示が全部エラーになり、Issue #562 が低情報密度ガードについて記録した「常時点灯する所見は読まれなくなる」を初日から踏むことになる。

例外は行内または直前の非空行に理由付きの HTML コメント（`<!-- skill-language-exception: <理由> -->`）を置いて明示し、理由が空のマーカーはそれ自体をエラーとする（L10 と同じ規約）。現在の例外は 3 件で、いずれも英語の文の中に引用された日本語の例示である。

**マーカーは行単位で照合するため、フェンス内の行はフェンスの外からは免除できない**（直前の非空行がフェンスの開始行ではなく同じブロックの別の行になるため）。マーカーをフェンスの中に置けば検出は止まるが、ここでのフェンスは Skill がそのまま出力するテンプレートなので、コメントごと読者に印字される。フェンス内では例外を足すのではなく、日本語の文末記号を持たない形へ例示を書き換える（ページタイトル・検索語はそのままで通る）。L10 がこの縁を持たないのは、あちらのマーカーがフェンスの開始行の直前に置かれブロック全体を覆うためである。

**既知の限界**: 文末記号を持たない日本語の**ラベル**は見えない。Issue #808 の `要確認:`（`OK` の隣に出す所見ラベル）がまさにそれで、行の意味を理解しない限り周囲の例示と区別できない。L10 が散文について記録しているのと同じクラスの限界であり、CI は規則が黙って腐る範囲を狭めるものであって塞ぐものではない。**配布テンプレート（`templates/`）も走査対象外**とする — そこには方針として日本語のまま据え置くもの（Python スクリプトのコメント・docstring〈#770〉、`ja-JP.ts` のロケール文字列）があり、日本語であることが正しい層である。

`tests/test_check_skill_output_language.py` がスクリプト自体の挙動（散文・フェンス双方の検出、鉤括弧、例示の非検出、行内／直前行の例外マーカー、理由なしマーカー、内部限定 Skill の非走査）に加えて、**実際の `.claude/skills/` が検出 0 件であること**も検証する。

---

## Skill（SKILL.md）品質保証（LLM 駆動部分）

T1〜T3・L1〜L5 はすべて決定論的コード（Python スクリプト・quartz-plugins・行数のような機械計測可能な指標）が対象で、SKILL.md 自体（LLM が指示に従って実行する部分）の判断品質を検証する仕組みが存在しない。特に `wikicommit-generate` の多段生成アルゴリズム（[DesignDoc-skills.md](DesignDoc-skills.md) §11.6：分析 JSON → ファイル境界プロトコル → レビュー）や `wikicommit-merge` の品質チェック結果に基づく続行判断のような、LLM の判断がそのまま成果物品質に直結する箇所は、pytest の assert では検証できない。

Anthropic 公式の skill-creator が採用する「with-skill 実行 → アサーション採点 → pass_rate 集計」という eval 手法を参考に、S1・S2 を **T1〜T3・L1〜L5 とは別軸の非ブロッキング運用** として導入していたが、**どちらも Issue #714 で廃止した**（経緯は下記「[S1・S2 を廃止した理由](#s1s2-を廃止した理由)」）。以下は当時の設計と、廃止に至った記録である。

**当時、非ブロッキングとした理由**（この選択自体が、下記「なぜ回らなかったか」の 3 番目の原因になった）:

- 採点自体に LLM 呼び出し（または人間レビュー）を要し、実行結果が非決定的なため、PR ごとの CI で pass/fail を機械的にブロックすると不安定になる
- LLM 呼び出しコスト（API 料金・実行時間）が pytest と比べて高い
- 検証対象が「コードが仕様通り動くか」ではなく「LLM がプロンプト通りに妥当な判断をするか」であり、既存の blocking 品質ゲートとは性質が異なる

### S1. SKILL.md eval ハーネス（⛔ 廃止・Issue #714）

Issue #103 で導入し、Issue #714 で削除した。`wikicommit-generate` / `wikicommit-merge` / `wikicommit-search` の SKILL.md 本文を変更した PR で、サンドボックス上でサブエージェントに実際に生成させ、出力を `cases.json` のアサーションと照合する非ブロッキングな手動ハーネスだった。

### S2. description のトリガー精度の検証（⛔ 廃止・Issue #714）

Issue #104 で導入し（Issue #233 で対象を読み取り系 5 Skill へ再設計、Issue #311 で `wikicommit-preview` を追加）、Issue #714 で S1 とともに削除した。`description` frontmatter を変更した PR で、should-trigger / should-not-trigger の各プロンプトに対して意図した Skill が起動するかを判定する手動ハーネスだった。

### S1・S2 を廃止した理由

**削除ではなく記録として残す。** 「LLM 駆動部分の検証を試みて、強制力のない手動ハーネスは回らないと分かった」こと自体が、次に同じものを作ろうとする人にとって必要な情報である。

#### 実測: 導入・再設計の Issue の中でしか実行されていない

`results/` にあった 15 件すべての出自を辿ると、生成したのは**ハーネス自身を作り替えた Issue** だけだった。

| results の日付 | 生成した Issue | その Issue の主題 |
|---|---|---|
| 2026-07-07 | #112 | S1 ハーネスの導入 |
| 2026-07-08 | #113 | S2 ハーネスの導入 |
| 2026-07-17 | #253 | S2 の対象再設計 |
| 2026-07-23 | #322 | S2 の対象追加（`wikicommit-preview`） |

残る 3 件は既存 results のリネーム移動であり、新規実行ではない。**「SKILL.md を変更したので走らせた」という実行は 1 件も無い。** 2026-07-23 は運用が止まった日ではなく、ハーネス保守の最後の Issue が閉じた日である。

以降 `.claude/skills/*/SKILL.md` を変更したコミットは 113 件、うち `description:` を変更した（＝ S2 の実行を推奨する条件そのものの）コミットは 14 件あるが、新しい `results/` は 1 件も無い。その結果、削除時点で中身は現行実装と合っていなかった — 旧パス `.wikicommit/wiki/` が 29 箇所（Issue #477 で改名済み）、`.wikicommit/ingest/` が 4 箇所（#476）、旧見出し `## サマリ` が 4 箇所（#405）、`wikicommit-merge` の 5 ケース中 2 件が Issue #313 で廃止した「後レビュー用 PR」を検証していた。

#### なぜ回らなかったか

4 つが重なっている。いずれも「担当者が忘れた」ではなく構造の問題である。

1. **強制力がない。しかも同じリストの中でこれだけが例外だった。** `CONTRIBUTING.md`「SKILL.md を変更する場合の追加手順」は 4 項目あり、行数チェック・パス参照チェック・`disable-model-invocation` の 3 つはすべて *CI で自動実行*。S1・S2 だけが「マージ前に手動実行することを推奨」だった
2. **実装ワークフローに接続されていなかった。** 毎回の Issue 実装を駆動しているのは `implement-issue` / `review-and-merge` の 2 Skill だが、どちらも `eval` という文字列を 1 つも含まない。`CONTRIBUTING.md` は外部貢献者が最初に読む文書であって、実装中に読まれる文書ではない — **書いた場所と実行される場所がずれていた**
3. **CI に載せられない構造だった。** S1・S2 の pass / fail は LLM の判断であり、本書自身が非ブロッキングと明言していた。落ちても止まらないものは走らせる動機が弱く、1 と合わせると強制力を持たせる経路が設計上ふさがっていた
4. **起動コストが「PR 直前に回すもの」の水準を超えていた。** S1 はサンドボックスを作って実際に生成させ 1 件ずつ照合し、S2 は 91 プロンプトをまとめて判定させる。結果は pass_rate という「次に何をすべきか自明でない」形で返る

一方パイロット運用は、同じ LLM 実行コストで「生成された Wiki のこのページが実際に誤っている」という具体的な Issue に直結する。**同じ予算を張る先としてパイロットが上位互換になっていた**のが実態である。

#### これは「消費者のいない受け皿」をテスト側でやっていた

このリポジトリは同じ形を繰り返し名指しし、そのたびに削除してきた（Issue #553 の `inDefinedTermSet`、#669 の `auto_merge` / `chain_of_thought`、#552 の誰も検証しない `granularity`、#649 の誰も見ないラベル）。S1・S2 は**器（`cases.json`・`trigger-eval.json`・README の実行手順）を作り、それを走らせる工程を作らなかった**ケースであり、同じ形をテストの側で踏んでいる。

決定的な傍証がある。Issue #669 が `chain_of_thought` を実装せず削除した第 1 の理由は「**レビュー品質の eval 基盤がこのリポジトリに無いため、有効にして良くなったかを誰も判定できない**」だった。S1 はまさにその基盤として作られたものであり、**後の判断がその存在を自分で「無い」と数えている。**

#### 直して使い続ける案を採らなかった理由

`git add` リストを単一の情報源から生成し、Pages 失敗を abort に変え、ケースを現行実装に合わせて再実行する — それでも上記 1・2・3 は何も解決しない。**強制力と workflow への接続を同時に作らない限り同じ状態に戻る。** 将来 LLM 駆動部分の eval を再び作るなら、ハーネスより先にその 2 つを設計すること。

---

## 実装優先順位（提案）

> **全項目が済んでいる**（取り消し線がその印）。着手順の記録として残しているだけで、
> ここから読み取るべき未着手の作業は無い。本文の `T1` / `L4` 等のアンカーはこの表の
> 各節を指しており、参照先としては現役である。

| 優先度 | 項目 | 理由 |
|---|---|---|
| ~~1~~ | ~~T2（`init.py` / `add_source.py` ユニットテスト）~~ | Issue #88 で対応済み |
| ~~2~~ | ~~L1（markdownlint-cli2 CI 組み込み）~~ | Issue #89 で対応済み |
| ~~2~~ | ~~L4（`.markdownlint.json` 同期検証）~~ | Issue #90 で対応済み |
| ~~3~~ | ~~L2（ruff 導入）~~ | Issue #91 で対応済み |
| ~~4~~ | ~~T1（ローカル完結スモークテスト）~~ | Issue #92 で対応済み（`tests/test_smoke_local.py`。`--quartz` 経路の逆向き検証は Issue #556 で追加） |
| ~~5~~ | ~~T3（quartz-plugins への vitest 導入）~~ | Issue #93 で対応済み |
| ~~5~~ | ~~L3（quartz-plugins への ESLint 導入）~~ | Issue #94 で対応済み |
| ~~6~~ | ~~L5（SKILL.md 行数上限チェック）~~ | Issue #111 で対応済み |
| ~~7~~ | ~~S1（SKILL.md eval ハーネス）~~ | Issue #103 で対応済み → Issue #714 で廃止 |
| ~~8~~ | ~~S2（description トリガー精度検証）~~ | Issue #104 で対応済み → Issue #714 で廃止 |
| ~~9~~ | ~~L6（CI job 数削減と concurrency 設定）~~ | Issue #216 で対応済み |
