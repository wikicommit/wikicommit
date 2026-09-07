# WikiCommit — 技術スタック・フェーズ別実装スコープ

> **対応DesignDoc**: 元 §12・§14

---

## 12. 技術スタック一覧

| レイヤー | 技術選択 | 備考 |
|---|---|---|
| **ページ生成** | Claude Code Skills（ユーザー自身の LLM 契約で実行） | MVP の実装形態 |
| **SSG（公開）** | Quartz v5 | WikiLink ネイティブ対応。本体は npm 配布ではなく git submodule で取り込む。設定は `quartz.config.yaml`（YAML） |
| **品質ゲート** | lychee + markdownlint-cli2 + カスタム Python（wikicommit-merge から呼び出し） | ルールベースは API キー不要 |
| **全文検索（ブラウザ）** | Quartz v5 標準の検索プラグイン（FlexSearch ベース） | 静的サイト上のブラウザ検索。全フェーズ |
| **全文検索（Skills / ローカル）** | FTS5 trigram（SQLite 3.38+） | CJK 対応・外部依存なし（Python 標準の `sqlite3` で利用可能）。Phase 3 で `wikicommit-ask` / `wikicommit-search` Skill が grep から移行して採用。クロスリンガル検索はエージェントによるクエリ翻訳（原語 + 翻訳語で複数回検索）で実現し、埋め込みベースのセマンティック検索には依らない |
| **全文検索（ホスト型 MCP サーバー）** | FTS5 trigram（SQLite 3.38+） | Phase 3 と同一実装を Phase 5 以降のホスト型 MCP サーバーでも再利用（複数リポジトリ横断検索用。Phase 3 の自己ホスト MCP は撤回。Phase 4 は Tauri デスクトップがローカル git を直接操作するため、複数リポジトリ横断検索が必要になる Phase 5 まで不要） |
| **ベクトル検索** | LanceDB + multilingual-e5-base（候補・未着手） | Phase 3 では依存の重さ（torch/sentence-transformers 等の追加・モデルダウンロード・再エンベディングのインデックス管理）を理由に採用を見送り、FTS5 trigram + エージェントによるクエリ翻訳で代替した。導入するかどうかは将来 Phase での再検討課題（フェーズ未確定） |
| **MCP サーバー** | Python（FastMCP）または TypeScript | Phase 5 でホスト型として公開（複数リポジトリを横断して検索するため、単一リポジトリの Git チェックアウトの外に出る必要がある）。Phase 3 の自己ホスト版は撤回 |
| **コンパニオンアプリ（デスクトップ）** | Tauri（Rust + WebView） | Phase 4。PC 専用。ローカルの git チェックアウトを直接操作するため、ネイティブバイナリの配布が容易な Tauri を採用（Electron より軽量・ローカルの Claude Code をサブプロセス実行する構成と相性が良い） |
| **テキスト抽出** | Anthropic 公式 Skills（pdf / docx / pptx / xlsx）+ markitdown（フォールバック） | 自作しない |
| **リンク検証** | lychee | 外部リンク検証（sources URL・本文中 https:// リンク）。WikiLink 検証は `wikicommit-merge` 内インライン Python が担当 |
| **スキーマ検証** | Schema.org 公式バリデーター / Google Rich Results Test | JSON-LD 生成後に検証 |
| **GPG/SSH 署名** | Git 2.34+（SSH）→ Sigstore（将来） | MVP では署名しない。レビューの記録はレビュー追跡 Issue の Close と `Reviewed-by:` トレーラーで行う（Issue #313 以前は「PR Approve のみ」と書いていた。[DesignDoc-architecture.md](DesignDoc-architecture.md) §13.9 の注記） |

---

## 14. フェーズ別実装スコープ

### Phase 1: 手動開発環境

**実装対象**:

- `.wikicommit/` ディレクトリ構造・`config.yml`
- `.wikicommit/schema/*.md`（Person / Place / Organization / Event / HowTo / DefinedTerm / default）
- `.wikicommit/scripts/`（基本検証スクリプト）
  - `validate_frontmatter.py`（必須フィールド・型チェック）
  - `check_orphans.py`（孤立ページ・重複検出）
- 簡易 SKILL.md（`wikicommit-init` / `wikicommit-generate` の手順定義）と Skill 内スクリプト（`init.py` / `add_source.py`）
- `install.sh`（プロジェクトの `.claude/skills/` に Skills を展開。`~/.claude/skills/` へのグローバルインストールは行わない）

**スコープ外**:

- SSG・公開
- 残りの Python スクリプト（Phase 2 へ）
- `wikicommit-merge` Skill（Phase 2 へ）
- `npx skills add` 対応（Phase 3 へ）

#### Phase 1 実装順序と依存関係

成果物間の依存関係に基づく推奨実装順序。

```
[Step 1] .wikicommit/config.yml テンプレート確定
  └─ 依存なし。config.yml の構造がスキーマ・スクリプトの前提になる。

[Step 2] .wikicommit/schema/*.md（7型）
  └─ config.yml が確定していれば書ける。
     Person / Place / Organization / Event / HowTo / DefinedTerm / default の順。

[Step 3] .wikicommit/scripts/validate_frontmatter.py
  └─ スキーマ定義（§5）が確定してから実装する。
     実行時に .wikicommit/schema/default.md と型スキーマファイルを読み込み、
     frontmatter.required を結合して必須フィールドリストを構築する。
     フィールドのハードコードなし：schema/*.md を変更するだけでバリデーションルールが更新される。
     フォーマット検証ルール（YYYY-MM-DD・sha256: 等）は DesignDoc-ScriptSpec.md に定義済み。

[Step 4] .wikicommit/scripts/check_orphans.py
  └─ WikiLink パターン [[Type/slug]] が確定していれば実装できる。
     Step 3 と並列実装可能。
     Phase 1 で先行実装する理由: Phase 2 の wikicommit-merge が品質ゲートとして使用するため。

[Step 5] .claude/skills/wikicommit-init/SKILL.md + scripts/init.py
  └─ Step 1〜4 の成果物が確定してから書く。
     init.py が展開するテンプレートの内容が確定している必要がある。

[Step 6] .claude/skills/wikicommit-generate/SKILL.md + scripts/add_source.py
  └─ ソース管理ファイル形式（DesignDoc-data.md §4.3）が確定していれば書ける。

[Step 7] .claude/skills/wikicommit-generate/SKILL.md（ページ生成部）
  └─ Step 2（スキーマテンプレート）と Step 6（ソース管理ファイルの形式）の両方が確定してから書く。
     多段生成アルゴリズムは DesignDoc-skills.md §11.6 を参照。
```

#### Phase 1 で先に決めておく設計事項

SKILL.md の実装前に合意が必要な決定事項。

| 決定事項 | 選択肢 | 推奨 | 根拠 |
|---|---|---|---|
| SKILL.md・スキーマファイルの記述言語 | 日本語 or 英語 | 英語 | 多言語 Wiki を前提とし、Schema.org 標準・複数エージェント対応に合わせる |
| ファイル境界プロトコル | `---FILE: path---` / `---END FILE---` | nashsu 形式を採用 | 複数実装で実績あり。パース失敗が局所化できる |
| 既存ページの更新条件 | タイトル一致 or slug 一致 | slug 一致（ファイル名） | タイトルは言語・表記揺れで変わりうる |
| 型非対応の扱い | default にフォールバック or スキップ | default にフォールバック | ページ化しないよりデータ保全を優先 |
| スキャン PDF の扱い | エラーで中断 or OCR Skill を呼ぶ | OCR Skill へのフォールバック | 研究資料・議事録などスキャンPDF混入は想定内 |

### Phase 2: GitHub レビュー・CI 整備

**追加実装**:

- `.wikicommit/scripts/` 残りスクリプト
  - `check_wikilinks.py`（WikiLink 参照先存在確認・removed ページへのリンク検出）
  - `check_expires.py`（`expires_at` 期限切れ検出）
  - `check_translation_status.py`（`source_commit` 陳腐化検出・未翻訳ページ検出）
  - `check_ingest_freshness.py`（ingest ハッシュずれ検出）
- `.claude/skills/wikicommit-merge/` SKILL.md（品質チェック + ブランチ + PR + マージ + レビュー追跡 Issue の作成。当初は「後レビュー用 PR」だったが Issue #313 で置き換えた）
- Quartz v5 設定（WikiLink 解決・全文検索）
- `review_status` バナー（Quartz カスタムコンポーネント）
- JSON-LD 埋め込み（Quartz プラグインとして実装。ページの `properties:` ブロック〈Issue #495〉の値を型ごとの決め打ちマッピングで JSON-LD へ流し込む）
- GitHub Pages デプロイ自動化（`.github/workflows/deploy.yml`）— main マージをトリガーに Quartz ビルド → GitHub Pages 公開
- SKILL.md の整備（`wikicommit-generate` の多段生成アルゴリズムを `DesignDoc-skills.md §11.6` 仕様に合わせて完成させる。`wikicommit-init` の簡易版も同様に整備する）
- Ingest テーマ設定・チェックポリシー
  - `config.yml` に `theme` フィールドを追加（`wikicommit-init` が対話的に設定。空 Enter でスキップ可）
  - `wikicommit-generate` パス 2（分析）で `theme` に基づくエンティティ単位の `action: exclude` 判定を実装（`DesignDoc-skills.md §11.6`）。`theme` 未設定時は判定なし（既存挙動を維持）
  - ソース管理ファイル body に `## Summary`（自動生成・毎回上書き）/ `## User Notes`（人間手書き・上書きしない）の 2 見出し構成を導入し、除外理由をサマリに記録
  - ソース管理ファイル `status` に `excluded`（全エンティティ除外）を追加（`DesignDoc-data.md §4.3`）

### Phase 3: Skill 化・OSS 配布

**追加実装**:

- 全 Skills 完成（`wikicommit-init` / `ingest` / `merge` / `review` / `fix` / `remove` / `ask` / `search` / `status`）
- Skill 内スクリプト（`scripts/`）完成・テンプレート整備
- Phase 3 E2E 検証（全 Skill + `install.sh` / `npx skills add` 導線の実証）
- OSS 公開（E2E 検証完了後。`dev/todo.md` の指摘を受け、E2E 検証を前提条件として明示）
  - `install.sh`（curl インストール）を引き続き提供
  - `npx skills add wikicommit/wikicommit` 対応を追加（agentskills.io 標準準拠）
  - agentskills.io 標準準拠：全 SKILL.md に YAML frontmatter（`name`, `description`）を付与
  - リポジトリを private → public に切り替える
- Anthropic Skills Marketplace への掲載申請（OSS 公開＝ public 化後。掲載要件の調査と実際の登録を別 Issue に分離する — 調査は登録に先行し、コードへの影響がないため public 化を待たず並行着手できる）
- 全文検索基盤（FTS5 trigram SQLite）— `wikicommit-ask` / `wikicommit-search` Skill が grep から移行し、MCP を介さず直接クエリする（自己ホスト MCP サーバーは撤回。単一リポジトリの検索・参照は Skills が担うため冗長と判断）。クロスリンガル検索はエージェントによるクエリ翻訳で実現する。埋め込みベースのセマンティック検索（LanceDB + multilingual-e5-base）は依存が重いため Phase 3 スコープ外とし、将来 Phase での再検討課題とする
- `wikicommit-collect` Skill — `config.yml` の `theme` に基づくローカルフォルダ・Web からの関連ソース候補探索。Claude Code のネイティブ Web 検索・既存 Skills を活用（専用クローラは自作しない）。著作権・ライセンスリスクを踏まえ、候補を `.wikicommit/source/` へ登録する前に人間の承認を必須とする（`DesignDoc-skills.md §11.2`）
- `wikicommit-quiz` Skill — `wikicommit-ask` の派生スキル。Wiki 全体から難易度別クイズを生成し会話内に出力する（ファイル書き出しなし。`DesignDoc-skills.md §11.2`）
- `wikicommit-document` Skill — 当初は `wikicommit-ask` の派生スキルとして、特定の概念・用語についてまとめ文書を生成し `.wikicommit/exports/<topic-slug>.md` にローカル書き出しする設計だった（`wiki/` の一次情報とは別の派生文書として品質ゲート対象外・`/wikicommit-merge` は呼ばない）。Karpathy の LLM Wiki gist との比較で「探索成果が wiki に蓄積される経路がない」ギャップが判明したことを受け、`wikicommit-synthesize` に改名し、出力先を `.wikicommit/entity/` 直下（一次情報・品質ゲート対象・`/wikicommit-merge` でPR化可能）に変更した。`exports/` という仮置きの概念自体を廃止し、出自は `derived_from`（`translated_from`/`source_commit` パターンの複数ソース版）フロントマターで表す（Issue #283。`DesignDoc-skills.md §11.2`、`DesignDoc-data.md §3.1・§4.2`）
- `wikicommit-translate` Skill（Issue #280）— 対話実行の翻訳生成 Skill。原文全文 + `DefinedTerm/` 用語定義を LLM コンテキストに注入して翻訳ページを生成し、`translated_from` / `source_commit` / `translated_at` を付与してローカル書き出しする（Git 操作は行わない）。1ページ単体モードと、`check_translation_status.py` の `UNTRANSLATED` + `STALE` 件数が5件を超える場合に確認を挟む一括モードを持つ（`DesignDoc-pipeline.md §6.4`、`DesignDoc-skills.md §11.2`）

> **`wikicommit-translate.yml`（main マージ起点の無人トリガー）は Phase 3 スコープ外・Phase 4 へ移動**: 1ページあたりの翻訳処理内容自体は上記の対話実行 `wikicommit-translate` Skill として Phase 3 で提供済み（Issue #280）。Phase 4 に残っているのは「main マージを検知して人間の介在なしに同じ処理を呼び出す」トリガー部分のみ。mainマージをトリガーに人間の介在なしで LLM を呼ぶ無人実行が前提だが、Phase 1–3 の Skills はすべて Claude Code 上での対話的実行（人間が `/wikicommit-xxx` を叩く）を前提としており、無人実行の仕組みを持たない。無人実行を可能にする `claude-code-action`（GitHub Actions 上で SKILL.md をそのまま実行）は Phase 4 で導入される計画だったため、`wikicommit-translate.yml` もその基盤に合わせて Phase 4 に据え置く。当時の計画は `dev/roadmap-phase4-5.md` にある（公開対象外 — `docs/README.md` §3）。

<!-- -->

> **GitLab 対応は Phase 3 スコープ外・Phase 4 へ移動**: `wikicommit-merge` の `gh` CLI 依存部分（PR 作成・auto-merge・ポーリング・close）を GitLab（`glab`）にも対応させる件は、OSS 版である Phase 3 では行わない。GitLab は self-hosted・企業内クローズド利用が主戦場であり、Commons（Phase 5）の発見機構（`wikicommit.json` + GitHub トピック `wikicommit`。[DesignDoc-data.md §5.6](DesignDoc-data.md) 参照）に乗らないため、OSS 版が目指す Commons 成長には寄与しない。Phase 3 は GitHub 限定のまま据え置く。Phase 4 側の当時の計画は `dev/roadmap-phase4-5.md` にある（公開対象外 — `docs/README.md` §3）。

<!-- -->

> **`.wikicommit/schema/` レジストリは作らない**: 型定義（`.wikicommit/schema/custom/*.md` 等）をコミュニティで共有する専用レジストリ（軽量版・本格版いずれも）は設けない。`.wikicommit/schema/*.md` は各リポジトリの平文ファイルであり、他者の公開 WikiCommit リポジトリを直接閲覧してコピーする形の共有は現状のままで既に可能。中央レジストリを立てず GitHub 標準の発見手段（検索・トピック）に委ねる方針は、Commons のフェデレーション設計（信頼を強制せず読者の判断に委ねる。[DesignDoc-data.md §5.6](DesignDoc-data.md)）とも整合する。発見性を高めたくなった場合は Commons（Phase 4 の `wikicommit.json` + GitHub トピック `wikicommit`、Phase 5 のクローラー + 静的インデックス）が同じ役割を担うため、型定義専用の仕組みを別途二重に作る必要はない。

<!-- -->

> **既存ページの事後的な型再分類の仕組みは未着手・着手フェーズ未確定（2026-08-04時点）**: `check_schema_coverage.py`（`wikicommit-schema-propose`の検出源）は「`type:`値に対応する専用スキーマファイルが存在するか」のみを判定する。そのため「型ファイル自体は存在するが、そのページに選ばれた型が内容的に誤っている」ケース（例: 固有名詞を持つソフトウェア製品が、より適切な`SoftwareApplication`ではなく汎用的な`DefinedTerm`に分類されてしまう）は検出対象外になる構造的な限界がある。`wikicommit-schema-propose`自体も新規スキーマファイルの追加のみを行い、既存ページの`type:`フィールドを書き換えて再分類する機能は持たない。`ai-driven-dev-wiki`パイロットで実際に確認された（`dev/pilot-ai-driven-dev-wiki.md`参照）。対応するには、既存ページ（特にDefinedTermのような適用範囲の広い型）を対象に内容から適切な型を再判定し、型変更＋本文の再構成をPR化する新規Skill（または`wikicommit-schema-propose`の拡張）が必要になると見込まれるが、実装コストが大きいため Phase 3 の OSS 公開スコープには含めない。着手するフェーズは未確定。 なお Issue #578 の再生成モード（`/wikicommit-generate --regenerate`）はこれとは別物で、対象は「型は正しいが中身が古い」ページであり、型再分類（「型自体が誤っている」ページが対象）は明示的にスコープ外としている — 再生成は既存ページの型を前提とする操作のため Pass 2b（動的型追加）も走らせない。同様に、`granularity` の変更に伴うページの分割・統合も再生成の対象外（「どのページが存在すべきか」自体が変わる操作であり、ページ起点の再生成では表現できない）— こちらも着手フェーズ未確定として本節に併記しておく。

<!-- -->

> **gap-driven な探索の自動ループは未着手・着手フェーズ未確定（2026-08-31時点）**: 「Purpose を定義し、Knowledge Gap を検出し、自動で再探索して Knowledge Model を更新する」という閉ループの構想がある。Issue #672 はそのうち**判断を人間に残す部分だけ**を取り、`/wikicommit-collect` に俯瞰ステップ（Step 3.5）を置いた — Wiki の現状を 3 本の読み取り専用スクリプトで俯瞰し、着眼点を最大 5 件提案して人間が選び、それがその実行の research guidance になる。着眼点は 1 回の実行の中だけで生き、ファイルには残らない。
>
> **残りを自動化するには、少なくとも 2 つの独立した設計判断が要る**。(1) `Purpose` に相当する第一級フィールドの新設 — `theme`（内容スコープ）・`.wikicommit/source-policy.md`（ソース方針）に続く 3 つ目の設定になる。Issue #564 が「他に書く場所が無くて `theme` に押し込んだのが実害だった」と結論している以上、恒久化するならそれ自体を独立に設計する必要がある。(2) スロット単位のギャップ検出（各ページの `properties:` のどのキーが未充足か）— Issue #553 が「埋められないキーは省略する」と決めたため、**未充足であることがページ上に存在しない**。測るにはページ側ではない別の場所に充足表を持つ必要がある。
>
> あわせて、`build_survey_view.py` に「単一の薄いソースだけに支えられたページ」を出す `--sources` を足す案も見送っている（`dev/pilot-saitama-wiki.md`・`dev/pilot-decameron-wiki.md` で多数観測された、着眼点として強い信号だが、スクリプト変更を伴う）。`ORPHAN:` の出自表示（Issue #570）が部分的に代替する。

### Phase 4 以降

Phase 4（Tauri デスクトップアプリ・SaaS 版）と Phase 5（Commons）のスコープは **2026-08-31 に保留**とした（到達目標を「OSS として広く使われること」ではなく「ポートフォリオとして仕上げ、その後で段階的に紹介していく」に置き直したため）。Phase 3.1 で一区切りとし、着手するかどうか・着手するとして何を作るかは未定である。保留にした時点までの計画は非公開の開発記録 `dev/roadmap-phase4-5.md` に切り出してある（公開対象外 — `docs/README.md` §3）。
