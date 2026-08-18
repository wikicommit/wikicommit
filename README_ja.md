# WikiCommit

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![CI](https://github.com/wikicommit/wikicommit/actions/workflows/test.yml/badge.svg)](https://github.com/wikicommit/wikicommit/actions/workflows/test.yml)
[![GitHub Stars](https://img.shields.io/github/stars/wikicommit/wikicommit?style=social)](https://github.com/wikicommit/wikicommit)

Git ベースの知識管理プラットフォーム。ソースドキュメントから LLM が Wiki ページを生成し、自動・人間によるレビューを経て静的 Wiki として公開します。SKILL.md 群として実装されており、Claude Code などユーザー自身が契約している LLM 環境上でそのまま動作します。

> **Status**: パイロットリポジトリでの実運用検証を進めており、破壊的変更が入ることがあります。

## できること

- **複数人・非同期レビュー**: 品質チェック通過後に自動マージ・公開し、レビューはページごとに分担して行う。各自が Issue をClose するだけで完了
- **ソース探索から Wiki ページ生成まで自動化**: 未取り込みの関連ソースをローカル・Web から自動探索。PDF・URL・リポジトリ内ファイルを登録すれば Wiki ページを生成
- **GitOps**: すべての変更をコミット・PR として記録。監査・ロールバック・バックアップは `git log` で完結
- **Wiki への質問応答（RAG）**: Wikiページを起点として質問に対して回答。必要なら一次ソースまで遡って引用も可能
- **多言語対応**: 翻訳生成・翻訳陳腐化の自動検知・WikiLink の言語フォールバックまで一貫対応
- **GitHub Pages への自動公開**: main へのマージをトリガーに静的サイトとしてビルド・デプロイ。公開前のローカルプレビューも可能
- **ヘルスチェック**: 孤立ページ・期限切れ・リンク切れ・翻訳陳腐化などを検知

**ユースケース**: 社内技術ドキュメント・製品ナレッジベース・研究ノート・コミュニティ Wiki など、散在したソース（PDF・URL・既存リポジトリのファイル）から構造化された Wiki を継続的に生成・維持したい場合に向いています。

## 目次

- [WikiCommit](#wikicommit)
  - [できること](#できること)
  - [目次](#目次)
  - [基本フロー](#基本フロー)
    - [Step 1: ソース登録 + Wiki ページ生成](#step-1-ソース登録--wiki-ページ生成)
    - [Step 2: 品質チェック・PR 作成・マージ](#step-2-品質チェックpr-作成マージ)
    - [Step 3: マージ後レビュー](#step-3-マージ後レビュー)
  - [技術スタック](#技術スタック)
  - [Requirements](#requirements)
  - [インストール](#インストール)
  - [Skills 一覧](#skills-一覧)
  - [Contributing](#contributing)
  - [License](#license)

## 基本フロー

### Step 1: ソース登録 + Wiki ページ生成

**(Option) 取り込むソースがまだ決まっていない場合**: `/wikicommit-collect` を実行すると、`config.yml` の `theme` に基づいてローカルフォルダおよび Web から未取り込みの関連ソース候補を探索・一覧提示します。著作権・ライセンスリスクを踏まえ、登録は候補を人間が確認・選択した分のみ行われます。選んだソースは以降 `/wikicommit-generate` と同じ扱いになります。

```
/wikicommit-generate <path|url>
```

- `.wikicommit/source/` に管理ファイルを生成（`status: pending`）
- ハッシュを自動計算して記録
- テキスト抽出 → 内容分析 → ページ生成 → ソースとの整合性レビュー、の順に自動実行
- 完了後 → 生成ファイルをワーキングディレクトリに書き出し（Git 操作なし）

### Step 2: 品質チェック・PR 作成・マージ

```
/wikicommit-merge
```

- 品質チェック（frontmatter 検証・WikiLink チェック・生 HTML 検出・外部リンク検証・孤立ページ検出）
- ブランチ作成・PR 作成・自動マージ（GitHub 標準の auto-merge 機能には依存しない実装のため、GitHub Free の private リポジトリでも動作します）
- レビュー追跡 Issue（`wikicommit-review` ラベル）と生成失敗トラッキング Issue（`wikicommit-generation-failure` ラベル）を生成

**(Option) マージ前後の見た目をローカルで確認したい場合**: `/wikicommit-serve [--build]` で Quartz v5 のローカルビルド・プレビューサーバーを起動できます（GitHub Pages のデプロイ完了を待つ必要がありません）。

### Step 3: マージ後レビュー

レビュー追跡 Issue（`wikicommit-review` ラベル。`review_status: pending` のページごとに自動生成）を確認：

- ページ内容がソースと整合しているか
- WikiLink（`[[Type/slug]]`）が正しいか

- **問題なし** → Issue を Close するだけで完了。`review-issue-close-sync.yml` が検知して `review_status: reviewed` に更新・自動マージされる
- **修正が必要** → まず人間が Issue に指摘内容をコメントとして残す。`/wikicommit-fix <issue-url>` が Issue の本文・コメントを踏まえた修正案を AI が提示し、人間の確認後 `/wikicommit-merge` で修正を反映してから Issue を Close する
- **Issue を経由せず、人間が直接ページを作成・編集した場合** → `/wikicommit-review <page>` で frontmatter 補完・ソース整合性チェックを行いレビュー完了を記録した上で `/wikicommit-merge`

`main` へのマージをトリガーに Quartz v5 による静的 Wiki ビルドと GitHub Pages への自動デプロイが行われます。

## 技術スタック

| 用途 | 技術 |
| --- | --- |
| 静的サイト生成 | [Quartz v5](https://quartz.jzhao.xyz/) |
| 構造化データ | [Schema.org](https://schema.org/) |
| 知識表現仕様 | [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)（Open Knowledge Format） |
| 全文検索 | SQLite FTS5（trigram） |
| リンク検証 | [lychee](https://github.com/lycheeverse/lychee) |
| Markdown スタイル | markdownlint-cli2 |

## Requirements

- [Claude Code](https://www.npmjs.com/package/@anthropic-ai/claude-code)（最新版を推奨）
- Python 3.11+（品質チェックスクリプト用）
- [`gh` CLI](https://cli.github.com/)（認証済み。PR 作成・マージに使用）
- Node.js 20+（`markdownlint-cli2` 用）
- [lychee](https://github.com/lycheeverse/lychee)（外部リンク検証用。未インストール時は `/wikicommit-init` が自動インストールを試みる）

> Skills は [agentskills.io](https://agentskills.io) 標準準拠の SKILL.md 群のため、Codex など他の対応コーディングエージェントでも原理的には動作するはずですが、現時点で動作検証を行っているのは Claude Code のみです。

## インストール

```bash
# 方法 1: npx skills add（推奨。agentskills.io 標準準拠。Node.js が必要）
# 引数なしで実行すると対話的な選択画面が開く（黙って全部入るわけではない）
npx skills add wikicommit/wikicommit

# 個別 Skill のみインストールする場合
npx skills add wikicommit/wikicommit --skill wikicommit-generate

# 複数 Skill をまとめて指定する場合（--skill を繰り返す）
npx skills add wikicommit/wikicommit --skill wikicommit-generate --skill wikicommit-merge

# 全 Skill を確認なしで一括インストールする場合（迷ったらこれで問題ありません）
npx skills add wikicommit/wikicommit --all

# 方法 2: install.sh（シンプル・Node.js 不要。wikicommit を任意の場所に clone してから、
# 対象の wiki リポジトリのルートで実行する）
git clone --depth 1 https://github.com/wikicommit/wikicommit.git /tmp/wikicommit
cd /path/to/your-wiki-repo
bash /tmp/wikicommit/install.sh
```

インストール後、Wiki を初期化するリポジトリで実行：

```
/wikicommit-init
```

## Skills 一覧

| # | カテゴリ | コマンド | 説明 |
| --- | --- | --- | --- |
| 1 | 初期化 | `/wikicommit-init` | リポジトリに Wiki を初期化 |
| 2 | 生成・登録 | `/wikicommit-generate <path\|url>` | ソース登録 + Wiki ページ生成 |
| 3 | 生成・登録 | `/wikicommit-collect` | 関連ソース候補を探索（人間承認前提） |
| 4 | 生成・登録 | `/wikicommit-synthesize <topic>` | 既存Wikiページから新規ページを合成（`entity/`に書き込み） |
| 5 | 生成・登録 | `/wikicommit-translate <page> [--lang <target>]` \| `/wikicommit-translate`（一括） | ページを翻訳（ローカル書き出しのみ） |
| 6 | レビュー・品質管理 | `/wikicommit-merge` | 品質チェック・PR 作成・マージ |
| 7 | レビュー・品質管理 | `/wikicommit-review <page>` | ページを検証・レビュー |
| 8 | レビュー・品質管理 | `/wikicommit-fix <issue-url>` \| `/wikicommit-fix <page-path\|published-url> "<指示>"` | ページを AI 補助で修正（Issue / ページパス / 公開URL 起点） |
| 9 | レビュー・品質管理 | `/wikicommit-remove <page>` | ページを削除（PR を作成） |
| 10 | レビュー・品質管理 | `/wikicommit-schema-propose` | 未カバー type を検出し schema ファイルを提案（PR・非auto-merge） |
| 11 | 参照・検索 | `/wikicommit-ask <question>` | Wiki に対して RAG スタイルで質問 |
| 12 | 参照・検索 | `/wikicommit-search <query>` | キーワード検索 |
| 13 | 参照・検索 | `/wikicommit-quiz [--difficulty=easy\|medium\|hard]` | Wiki 内容からクイズを生成 |
| 14 | 運用・プレビュー | `/wikicommit-status` | ヘルスチェック（孤立・未審査・期限切れ） |
| 15 | 運用・プレビュー | `/wikicommit-serve [--build]` | Wiki をローカルでビルド・プレビュー |

---

## License

[Apache License 2.0](LICENSE)
