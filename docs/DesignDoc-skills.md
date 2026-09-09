# WikiCommit — Skills 設計（MVP）

> **対応DesignDoc**: 元 §11  
> スクリプト詳細仕様は [DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) を参照。

---

## 11. Skills 設計（MVP）

MVP の初期対応エージェントは **Claude Code のみ** とする。

### 11.0 WikiCommit が採用する実装モデル：エージェントネイティブ型

LLM Wiki ツールの実装には大きく 2 種類がある（出典: `dev/research/27_llm_wiki_schema_generation_prompt_research.md` §1）。

**API 直接呼び出し型**（nashsu/llm_wiki・atomicstrata/llm-wiki-compiler・tuirk/Kompl 等）
: TypeScript / Python 等のアプリケーションが LLM API を直接呼ぶ。多段生成の制御（「まず分析、次に生成、最後にレビュー」）はすべてアプリのコードが担う。LLM は呼ばれたら答えるだけ。

**エージェントネイティブ型**（WikiCommit・nvk/llm-wiki・wastedcode/memex 等）
: アプリのコードを持たず、SKILL.md に手順を記述する。Claude Code などのエージェントが SKILL.md を読み込み、LLM 自身が次の行動を判断しながら実行する。反復・リトライ・ツール選択はエージェント側に委ねられる。

**WikiCommit は後者（エージェントネイティブ型）** を採用する。これは SKILL.md の書き方に直接影響する。

| 比較軸 | エージェントネイティブ型 | API 直接呼び出し型 |
|---|---|---|
| **実行制御の担い手** | エージェント（Claude Code 等） | アプリコード（TypeScript / Python） |
| **手順の記述先** | SKILL.md / AGENTS.md | コード内（関数・クラス） |
| **ツール選択** | エージェントが自律判断 | コードがハードコード |
| **リトライ制御** | エージェントが判断 | コードが明示的に実装 |
| **マルチステップフロー** | エージェントが動的に組み立て | コードが順序を固定 |
| **出力形式の契約** | SKILL.md に明示が必要（エージェントは自由に動くため） | コードが出力をパース・強制 |
| **再現性・網羅性** | スクリプト委譲を SKILL.md に明示すれば保証できる（§11.5） | コード構造上、常に決定論的 |
| **LLM 推論をユーザーが持ち込むか** | 両方で可能（独立した軸） | 同左 |
| **導入コスト** | SKILL.md を書くだけ | アプリ実装が必要 |
| **デバッグ** | エージェントの動作を観察 | コードをステップ実行 |
| **Phase 4: SaaS** | `workflow_dispatch` API で GitHub Actions を起動し claude-code-action を実行。PR フローと自然に統合できる。非同期・GitHub 依存・ランナー起動レイテンシあり。**公式ドキュメントで `.claude/skills/` の SKILL.md が明示的にサポートされており、Phase 1–3 の SKILL.md をそのまま利用可能**（要 `actions/checkout`） | サーバーサイドで Claude API を直接呼ぶ。SKILL.md をシステムプロンプトに転用。低レイテンシだが自前インフラ管理が必要 |
| **Phase 4: Tauri デスクトップアプリ** | Tauri（Rust + WebView、PC 専用）からローカルの Claude Code をサブプロセス実行。追加インフラ不要・ユーザー自身の LLM 契約をそのまま使える・低レイテンシ。Phase 1–3 の設計をほぼそのまま継承できる | デスクトップアプリから Claude API を直接呼ぶ。SKILL.md をシステムプロンプトに転用 |
| **代表実装** | WikiCommit / nvk/llm-wiki / wastedcode/memex | nashsu/llm_wiki / atomicstrata / Kompl |

- API 直接呼び出し型の実装を参考にする際、その多段生成フローをそのまま SKILL.md に写す必要はない。パスの細かい制御はエージェントが自律的に行える。
- SKILL.md には「何を達成してほしいか」と「守るべき制約」を記述し、実行順序の細部はエージェントに委ねる設計が適切。
- ただし nashsu の `---FILE: path---` 境界プロトコルのような**出力形式の契約**は明示する。エージェントがどう実行するかは自由でも、何を出力するかは決定論的に定める必要がある。

### 11.1 Skill の配置

| 用途 | 配置先 | 管理方針 |
|---|---|---|
| WikiCommit 開発リポジトリの正本 | `.claude/skills/<skill-name>/` | WikiCommit 本体で更新する唯一の正本 |
| wiki リポジトリへのインストール | `.claude/skills/<skill-name>/` | `/wikicommit-init` 実行前にユーザーが配置。Git 管理・`claude-code-action` が参照 |

`~/.claude/skills/`（グローバル）へのインストールは不要。Skills は常にプロジェクトの `.claude/skills/` に配置し、リポジトリで Git 管理する。

#### インストールフロー

```
[Step 1] .claude/skills/ に WikiCommit Skills を配置（下記 2 経路のいずれか）

  npx skills add wikicommit/wikicommit        install.sh
  （agentskills.io 標準・要 Node.js）          （要 bash・Node.js 不要）
  ・--skill <name> で個別指定                  ・git clone --depth 1 した後、
  ・--all / 引数なしの対話選択に対応             対象 wiki リポジトリのルートで実行
  ・metadata.internal: true の 2 Skill は      ・コピー元 = clone 先の .claude/skills/
    一括インストールから自動除外                 コピー先 = $(pwd)/.claude/skills/
                    │                                  │
                    └────────────────┬─────────────────┘
                                     ↓
              <wiki リポジトリ>/.claude/skills/wikicommit-*/
         （Git 管理下。~/.claude/skills/ へのグローバル配置は行わない）
                                     ↓
              Claude Code がプロジェクト Skill として認識
                                     ↓
[Step 2] /wikicommit-init を実行（init.py）
                                     ↓
  .wikicommit/       config.yml（primary_lang・theme を対話設定）
                     schema/（base_types を展開 + theme 駆動の型提案 #490）
                     source/path・source/url・entity/assets・entity/<primary_lang>
                     scripts/（品質チェック用 Python スクリプト一式）
  リポジトリルート    .lychee.toml・.markdownlint.json・.gitignore
  .github/workflows/ review-issue-close-sync.yml（Quartz 選択に関わらず常に配布）
    └ --quartz 時      quartz.config.yaml・package.json・quartz-plugins/ 等
    └ --quartz-pages 時 deploy.yml（Pages への自動公開はこのフラグでのみ有効化）
```

Step 1 の配置方法は 2 つ提供する：

| 方法 | コマンド | 用途 |
|---|---|---|
| **npx skills add**（エコシステム標準・推奨） | `npx skills add wikicommit/wikicommit` | agentskills.io 標準準拠。Node.js が必要 |
| **install.sh**（シンプル・Node.js 不要） | `git clone --depth 1 https://github.com/wikicommit/wikicommit.git /tmp/wikicommit && cd <wiki リポジトリ> && bash /tmp/wikicommit/install.sh` | wikicommit を任意の場所に clone し、対象の wiki リポジトリのルートで実行する |

`install.sh` は実行時のカレントディレクトリ（wiki リポジトリのルート）に `.claude/skills/` をプロジェクトレベルで展開する（`~/.claude/skills/` へのグローバルインストールは行わない）。`install.sh` 自身は `SCRIPT_DIR/.claude/skills`（＝ clone した wikicommit リポジトリ本体）をコピー元、`$(pwd)/.claude/skills`（＝実行時のカレントディレクトリ）をコピー先とする実装のため、wikicommit の clone 先と対象 wiki リポジトリが別ディレクトリでも問題なく動作する。

> **`--depth 1` を付ける理由（2026-07-28 実測）**: フル clone は `.git`（履歴込み）だけで約 46MB になる一方、現在の HEAD のファイルツリーは 6.6MB、`install.sh` が実際に使う `.claude/skills/` は 3MB しかない（wikicommit-dev2 での実測値。過去に Issue #81 でルート直下の Quartz 自己公開設定一式を削除した経緯等が履歴に残っており、その分も含めて肥大化している）。`--depth 1` は最新コミットのスナップショットのみを取得する標準オプションで、追加の複雑さなしに約 46MB→7MB まで削減できる。`.claude/skills/` だけに絞る `--filter=blob:none --sparse` + `sparse-checkout`（3MB まで削減可能）は git 2.25+ が必要な高度な機能で、一般ユーザー向け案内としては複雑さが見合わないと判断し採用しない。

<!-- -->

> **単体 curl インストールは提供しない（p3-023 / #158 で検討・不採用）**: `curl -sSL <url> | bash` で `install.sh` 単体をパイプ実行する方式も検討したが、`install.sh` が自分自身と同じディレクトリにある `.claude/skills/`（wikicommit リポジトリ本体）を相対パスで探す実装のため、単一ファイルとして取得した場合は `.claude/skills/` が見つからずエラー終了し実現できない（`BASH_SOURCE[0]` がファイルパスを持たないため）。tarball 取得による代替実装も検討したが、Node.js 不要という利点は `git clone` 方式でも同様に得られる一方、単体 curl 化のためだけに `install.sh` へフォールバック処理を追加するコストに見合わないと判断し、上表の 2 方式に一本化した。単体コマンドでのインストール体験は `npx skills add` 側に譲る。

`npx skills add` は Vercel Labs が npm パッケージとして配布する Skills 管理 CLI（`vercel-labs/skills`）。Claude Code・Cursor・Codex など 40+ エージェントに対応する。

#### 配置方式と `--copy`（Issue #555）

`npx skills add` は、**2 つ以上のエージェント（正確には 2 つ以上の異なる skills ディレクトリ）を同時に対象にした場合**、Skill の実体を `<project>/.agents/skills/<name>/` に置き、各エージェントのエントリ（`<project>/.claude/skills/<name>` を含む）をそこへの**相対シンボリックリンク**にする（本節「`npx skills add` 仕様確認結果」項目7）。この配置は WikiCommit の前提と 2 箇所で噛み合わない:

1. **host → container の境界をまたげない**。`dev/pilot-ai-driven-dev-wiki-round5.md` で、ホスト側にこの方式で配置してから devcontainer を作成したところ、コンテナ内から Skills が認識されなかった。round2〜round4 のパイロットは `install.sh`（`cp` による実体コピー）で同じ「ホスト側に配置 → devcontainer に持ち込む」手順を採っており一度も起きていないため、シンボリックリンク方式に切り替えたことが分水嶺である。**正確な機構は特定していない**（ホスト OS 側でのリンク作成失敗か、bind mount でのリンク変換不良か）。実務上は下記 2 つの回避策のどちらでも解消するため、切り分け自体は未実施のままとする。
2. **Git 管理の前提と食い違う**。本節冒頭のとおり「Skills は常にプロジェクトの `.claude/skills/` に配置し、リポジトリで Git 管理する」「`claude-code-action` が参照する」のが WikiCommit の前提だが、シンボリックリンクのままコミットすると、リンク先である `.agents/skills/` も併せてコミットしない限り clone 先でリンク切れになる（`skills-lock.json` はリンクの解決には関与しない）。また `skills-lock.json` は `--copy` の使用有無を記録しないため、`experimental_install` による復元は配置方式の指定なし（＝対象エージェントが複数ならシンボリックリンク）で行われる（本節「`npx skills add` 仕様確認結果」項目3）。

**方針**: ドキュメント（README・`README_ja.md`）が案内する `npx skills add` のコマンド例には **`--copy` を付ける**。`--copy` は上記 2 点の両方に同時に効き、結果として `install.sh`（実体コピー）と同じ配置になるため、2 つのインストール方法の間で「インストール後の `.claude/skills/` がどうなっているか」を揃えられる。コピー方式では対象エージェントごとに独立した実体が作られる（`.agents/skills/` 側の実体は、対象に universal エージェントが含まれない限り作られない）。Skill は SKILL.md と小さな `scripts/` のみで構成され合計 3MB 程度（本節冒頭の実測値）のため、Claude Code を対象とする通常の使い方であればこの重複コストは問題にならない。**ただし `--all`（＝ `--skill '*' --agent '*' -y`）と `--copy` を組み合わせてはいけない** — コピー方式は、シンボリックリンク方式が持つ「プロジェクトに存在しないエージェントディレクトリは作らない」というスキップ判定を経ないため、対応する約 50 個すべてのエージェントディレクトリに全 Skill の実体コピーが作られる（実測: 空プロジェクトに対し既定の `--all` はトップレベル 4 エントリ・48K、`--all --copy` は 57 ディレクトリ・908K）。README の一括インストール例は `--skill '*' --agent claude-code -y --copy` としてエージェントを明示する（`--skill '*'` は `--all` と同じく内部限定 Skill を除外するため、対象集合は変わらない）。

**方針（補足）**: `--copy` は既定の挙動を上書きするものであり、`npx skills add` の側でこの既定が将来変わる可能性がある。したがって「`--copy` があるから境界問題は起きない」と考えず、devcontainer / GitHub Codespaces のようにファイルシステム境界をまたぐ環境では、**コンテナに入った後にインストールする**という手順上の指針も併せて案内する（round5 で実際に有効だった回避策であり、原因の特定を待たずに書ける）。両者は排他ではなく、重ねて適用してよい。

#### Windows 対応方針

Skills 本体（`.wikicommit/scripts/*.py` 等）は Claude Code の Bash ツール経由で実行される。Claude Code 自体が Windows では WSL または Git Bash（Git for Windows 同梱）を前提としているため、Skills 側で追加のクロスプラットフォーム対応は不要と判断する。`.py` スクリプトは Python + `hashlib` + git subprocess ベースで bash 依存がなく、Git Bash・WSL のいずれからでも動作する（Python 自体はどちらのシェルからも呼び出し可能）。

> この結論は **SKILL.md に明記された呼び出し方（Bash ツールからの直接実行）に従う場合に限る**（Issue #239）。大量ファイル対応等で agent が SKILL.md の指示を離れて独自の Python `subprocess` ラッパーを即興で書いた場合はこの限りではない。特に `npx` は Windows では `.cmd` シムのため、`subprocess.run(['npx', ...], shell=False)` は `FileNotFoundError` になる（`shell=True` またはフルパス指定が必要）。WikiCommit 本体側で将来 Windows 向けの補助スクリプトを書く場合も同様の注意が必要。

Windows 固有の考慮が必要なのは、Claude Code / Skills が使える状態になる前に人間が直接ターミナルで実行する `install.sh`（Step 1 のブートストラップ）のみである。これは bash 専用スクリプト（`set -euo pipefail`・配列・`${BASH_SOURCE[0]}` 等）で PowerShell / cmd.exe から直接実行できないが、Claude Code 自体を使うのに元々 Git Bash / WSL が必要という前提に乗る形で足りるため、PowerShell 版の用意や Python 実装への置き換えといった追加対応は行わない。

#### `npx skills add` 仕様確認結果（Issue #132・`vercel-labs/skills` ソース調査 + Issue #555・実機検証）

「詳細は Phase 3 で確認」としていた項目（本節冒頭）の確認結果。ソース: `vercel-labs/skills` の `src/skills.ts`・`src/blob.ts`・`src/skill-lock.ts`（2026-07 時点）。

> **項目 3・4 はソースコード調査のみに基づいており、実機挙動と食い違っていた（Issue #555）。** 2026-08-18 のパイロット（`dev/pilot-ai-driven-dev-wiki-round5.md`）で初めて実際に `npx skills add` を実行したところ、ロックファイルの位置が記載と異なることが判明し、記載になかった「`.claude/skills/<name>` は既定でシンボリックリンク」という挙動も見つかった。以下の各項目は、実機検証（`skills` CLI v1.5.23 / 2026-08-28 再確認）を反映した記述に更新済み。**この節を根拠にする際は、ソース調査のみの項目と実機確認済みの項目を区別すること** — 記載が古いまま実害が出た前例が既に1件ある。

1. **リポジトリの読み取り方法**: 追加のマニフェストファイルは不要。`.claude/skills/<name>/SKILL.md`（`name`・`description` フィールドを持つ YAML frontmatter）が存在すれば、優先ディレクトリ一覧（`skills/`・`.claude/skills/` 等。`src/skills.ts` の `AGENT_PROJECT_SKILL_DIRS`）の 1 つとして深さ2までの探索で自動検出される。WikiCommit の既存構成（`.claude/skills/<name>/SKILL.md`）はそのまま要件を満たしている
2. **`--skill <name>` の名前解決**: `SKILL.md` frontmatter の `name:` フィールドと完全一致（大文字小文字は正規化）。WikiCommit の全 SKILL.md は `name:` を設定済みのため追加対応不要
3. **ロックファイル**（実機検証で訂正・Issue #555）: プロジェクトレベルのインストールでは、**インストール先プロジェクトのルート直下に `skills-lock.json`** が生成される（`~/.agents/.skill-lock.json` 等ホームディレクトリへのグローバル保存ではない — こちらは `-g` / `--global` を付けたグローバルインストール側の話であり、`npx skills add <repo>` の既定であるプロジェクトインストールでは作られない。実機で `~/.agents/` 自体が存在しないことを確認済み）。記録されるのは skill ごとの `source` / `sourceType` / `skillPath` / `computedHash` で、**`--copy` を使ったかどうかは記録されない** — したがって `experimental_install` によるロックファイルからの復元は既定の配置方式（シンボリックリンク）で行われる。いずれにせよ提供側リポジトリ（WikiCommit）が用意すべきファイルではない
4. **private リポジトリ対応**: 対応している。`GITHUB_TOKEN` / `GH_TOKEN` 環境変数、なければ `gh auth token`（`gh` CLI ログイン）の順でトークンを解決し、GitHub Trees API に Bearer 認証で問い合わせる（`src/blob.ts` の `fetchRepoTree`）。匿名リクエストは public リポジトリに対してのみ機能し（60 req/hr の IP レート制限あり）、private リポジトリは 401/404 を返すためトークンで自動リトライされる。**ただし取得経路はこれ 1 本ではない（実機検証で補足・Issue #555）**: Trees API + `raw.githubusercontent.com` によるブロブ取得（`tryBlobInstall`）が第一経路で、これが失敗した場合（API 到達不能・認証不足等）と、`<repo>@<ref>` のように ref を固定した場合は `git clone --depth=1`（`gh` CLI 経由 → HTTPS → SSH の順にフォールバック）へ切り替わる。2026-08-18 のパイロットで観測された「一時ディレクトリへの clone」はこの第二経路であり、Trees API 経路の記載自体が誤りだったわけではなく、記載が第二経路を含んでいなかった。clone は `--depth=1` の shallow clone であってフルクローンではない。`wikicommit-dev2` は private だが、動作確認自体は OSS 公開後の public リポジトリで行う方針（本 Issue 実装メモに既記載）は変更不要
5. **`.claude-plugin/marketplace.json` 等の追加マニフェスト**: `npx skills add` 単体では不要。Anthropic 自身の Plugin マーケットプレイス掲載（Issue #135・下記参照）では `.claude-plugin/plugin.json`（マーケットプレイス自体を自前運営する場合のみ `marketplace.json` も）が必要
6. **内部限定 Skill の除外機構（今回利用）**: SKILL.md frontmatter に `metadata:\n  internal: true` を付与すると、`npx skills add <repo>`（Skill 名を指定しない一括インストール）から除外される。`--skill <name>` で名指しされた場合や `INSTALL_INTERNAL_SKILLS=1` 環境変数を立てた場合は対象になる。WikiCommit 本体開発専用の `implement-issue`・`review-and-merge`（`install.sh` の配布対象一覧にも含まれていない）にこのフラグを付与し、`npx skills add wikicommit/wikicommit` の一括インストール時に配布対象の 15 Skill（`install.sh` と同一集合）のみが入る状態に揃えた（実機検証でも `Found 15 skills` と表示され、内部限定 2 件が除外されることを確認済み。Issue #555。この件数は記載当時 12 だったが、その後 Skill を追加した分だけ増えている — `install.sh` の `SKILLS` 配列が正）
7. **`.claude/skills/` への配置方式（実機検証で追加・Issue #555）**: 配置方式は「シンボリックリンク」と「コピー」の2つで、`--copy` なしの既定は**対象エージェントの数で分岐する** — 異なる skills ディレクトリを持つエージェントを2つ以上対象にした場合はシンボリックリンク方式（Skill の実体を `<project>/.agents/skills/<name>/` へ書き、各エージェントのエントリを `../../.agents/skills/<name>` への**相対シンボリックリンク**にする）、対象が1つだけの場合（選択画面で Claude Code のみを選んだ場合など）は指定の有無に関わらずコピー方式になる。コピー方式では対象エージェントディレクトリごとに独立した実体が書かれ、`.agents/skills/` へは何も書かれない（対象に universal エージェントが含まれる場合のみ、その1つとして作られる） — したがって `--copy` は「複製を1つ増やす」オプションではなく「canonical 集約をやめて各エージェントに実体を配る」オプションである。あわせて、コピー方式はシンボリックリンク方式が持つ「プロジェクトに未作成のエージェントディレクトリはスキップする」判定を経ないため、`--agent '*'`（`--all`）との併用は対応エージェント全数分の実体コピーを作る（§11.1「配置方式と `--copy`」の実測値を参照）。この方式が WikiCommit の前提と噛み合わない2つの場面（コンテナ境界・Git 管理）と、それに対する方針も同節を参照

#### Anthropic Plugin マーケットプレイス掲載要件の調査結果（Issue #135）

「詳細は Phase 3 で確認」としていた項目（本節冒頭）の確認結果。ソース: `code.claude.com/docs/en/plugins`・`/en/plugins-reference`・`github.com/anthropics/claude-plugins-official`（2026-07 時点）。

1. **「Skills 専用マーケットプレイス」は存在しない**: Anthropic 公式ドキュメント上、Skill は Claude Code の **Plugin システムの 1 コンポーネント種別**（他に agents・hooks・MCP servers 等）として扱われ、配布単位は常に「Plugin」。掲載も Skill 単体ではなく `.claude-plugin/plugin.json` を持つ Plugin 単位で行う。DesignDoc 初版の「Anthropic Skills Marketplace」という呼称は不正確だったため、本節を「公式 Plugin マーケットプレイス」に読み替える
2. **公式マーケットプレイスは 2 系統**:
   - `claude-plugins-official`: Anthropic 自身が厳選する公式マーケットプレイス。**申請フォームは存在せず、掲載可否は Anthropic の裁量**。Claude Code 初回起動時に自動登録される
   - `claude-plugins-community`（`anthropics/claude-plugins-community`）: 第三者提出をレビュー後に掲載する公開コミュニティマーケットプレイス。**本 Issue が対象とすべきはこちら**
3. **申請手順（`claude-plugins-community`）**:
   - 個人開発者（Team/Enterprise 組織なし）: Console フォーム [platform.claude.com/plugins/submit](https://platform.claude.com/plugins/submit)
   - Team/Enterprise 組織あり: claude.ai フォーム [claude.ai/admin-settings/directory/submissions/plugins/new](https://claude.ai/admin-settings/directory/submissions/plugins/new)（組織 Owner はデフォルトでアクセス権あり）
   - WikiCommit は個人開発のため Console フォームを使う想定
4. **提出前チェック**: `claude plugin validate <path>` をローカルで実行する。レビューパイプラインは同一チェック + 自動安全性審査を実行する。`--strict` を付けると警告もエラー扱いになるが、提出時に必須なのは無印の `validate` の PASS（`✔ Validation passed with warnings` でも可）
5. **承認後の反映**: 承認された Plugin は `anthropics/claude-plugins-community` の `marketplace.json` に特定コミット SHA で pin され、以後のコミットに応じて CI が自動でその pin を更新する。カタログは夜間同期のため、承認からインストール可能になるまで遅延がありうる（掲載確認はカタログの `marketplace.json` を検索する）
6. **前提条件**: リポジトリが public であること（`anthropics/claude-plugins-community` からコミット SHA 参照するため）。WikiCommit は Tier 7（#151 リポジトリの public 化）が前提条件になる
7. **p3-011（`npx skills add`）との重複確認**: 重複なし。`npx skills add` は vercel-labs 製の別 CLI・別エコシステム（agentskills.io 標準）であり、Anthropic 公式の Plugin マーケットプレイスとは無関係の並行した配布経路。両者とも既存の `.claude/skills/<name>/SKILL.md` レイアウトをそのまま使えるが、**Plugin マーケットプレイス側だけ `.claude-plugin/plugin.json` という追加マニフェストが必須**という差分がある
8. **リポジトリ側の対応（本 Issue のスコープで実施済み）**: リポジトリルートに `.claude-plugin/plugin.json` を追加した。`skills` フィールドに `.claude/skills/<name>/` を 15 個（`install.sh` の配布対象と同一集合。記載当時は 12 個）明示的に配列で列挙することで、ディレクトリ構造を変更せず・`implement-issue`/`review-and-merge`（内部限定 Skill）を含めずに済んでいる（`skills` フィールドは「デフォルトの `skills/` スキャンに追加」する仕様のため、個別パスを列挙すれば任意のサブセットだけを対象にできる）。`version` フィールドは当初意図的に未設定としていた（開発が活発な Phase 3 中はコミット SHA バージョニングを採用し、正式リリース時に semver 付与へ切り替えるかは後で判断するという保留）が、**Issue #577 で「付与する」と決着させ `0.1.0` を設定した**。決め手は claude-plugins-community への掲載（本項の主題）を視野に入れており、掲載時には `claude plugin validate` が `version` 未指定を warning にするため、どのみち必要になること。なお `version` を明示するとピン留めになり bump を忘れると更新が静かに止まる一方、省略しておけば SHA フォールバックにより配布 push のたびに自動で新版として検知される、という逆転（省略の方が更新が届きやすい）が存在する点には注意する — この副作用は「版を上げるときは `_version.py`・`plugin.json`・`CHANGELOG.md`・`.claude/skills/wikicommit-init/CHANGELOG.md` の 4 箇所をまとめて更新する」という運用と、前二者の同期を強制する `tests/test_version_sync.py`・後二者の一致を強制する `tests/test_changelog_sync.py` で受け止める（4 つ目は 3 つ目のコピーで、Issue #713 以降 `/wikicommit-update` がそこを読む。更新箇所の正本は `CHANGELOG.md` 冒頭）。同 Issue で決めたもう一つの source of truth（`.wikicommit/scripts/_version.py`。インストール先の wiki リポジトリまで届く唯一の情報源で、`config.yml` の `wikicommit_version`・ページの `generated_with` / `translated_with` の値はすべてここから読む）については `docs/DesignDoc-data.md` §3.3・§4.1 を参照。`claude plugin validate .` は記載当時 warning 2 件（`version` 未指定・リポジトリ直下の `CLAUDE.md` は Plugin コンテキストとしてロードされない旨）のみで PASS 済みだった（前者は Issue #577 の `version` 付与で解消）。後者は WikiCommit 開発リポジトリとしての `CLAUDE.md` の役割上想定内（Plugin へのコンテキスト提供は Skill 経由で行う設計のため元々整合している）

#### Skills エコシステムの構成

```
Anthropic
  ├─ agentskills.io 標準を策定（SKILL.md 形式・frontmatter 仕様）
  ├─ github.com/anthropics/skills — 公式 Skills リポジトリ（pdf / docx / pptx / xlsx 等）
  ├─ claude-plugins-official — Anthropic 自身が厳選する公式 Plugin マーケットプレイス（申請不可・裁量制）
  └─ claude-plugins-community — 第三者提出をレビュー後に掲載する公開 Plugin マーケットプレイス（Issue #135 が調査対象）

Vercel Labs
  └─ vercel-labs/skills — agentskills.io 標準の CLI 実装（npx skills add。Anthropic 公式 Plugin マーケットプレイスとは別経路）

WikiCommit
  ├─ npx skills add wikicommit/wikicommit でインストール可能にすることが Phase 3 の目標
  └─ .claude-plugin/plugin.json（本 Issue で追加）経由で claude-plugins-community への掲載申請が可能な状態
```

Anthropic 公式 Skills（pdf 等）のインストールも同じ CLI で行う：

```bash
npx skills add https://github.com/anthropics/skills --skill pdf
```

Claude Code は `.claude/skills/` 配下の `SKILL.md` をプロジェクト Skill として認識する。`.claude/commands/` はスラッシュコマンド用の別機構であり、WikiCommit の Skills は配置しない。`.claude/skills/` は Claude Code 固有の連携層であり、Wiki・設定・スキーマなどの中核データは引き続き `.wikicommit/` に置く。

#### agentskills.io 標準への準拠

Anthropic・OpenAI・Google・Microsoft・Cursor が採用する業界標準（agentskills.io）では、SKILL.md の先頭に YAML frontmatter が必須となっている。WikiCommit の SKILL.md もこの形式に準拠する。

```markdown
---
name: wikicommit-generate
description: Register a source file or URL and generate WikiCommit wiki pages locally (no Git)
---

## 処理フロー
...
```

`npx skills add` による配布時に標準非準拠の SKILL.md は認識されない可能性があるため、全 Skill に frontmatter を付与すること。

### 11.2 Skills 一覧

#### Skill 間の関係

下表の各 Skill がどう繋がるかの全体像。書き込み系の Skill はいずれもローカル書き出しまでで止まり、Git 操作は `wikicommit-merge` に集約される（`wikicommit-schema-propose` のみ例外的に自分で PR を作る）。

```
/wikicommit-init … .wikicommit/ 一式・schema/・ワークフローを生成（最初に 1 回）
                                    ↓
─── 書き込み系（ローカル書き出しのみ・Git 操作なし）────────────────────

  /wikicommit-collect ──呼び出し──→ /wikicommit-generate
    （テーマから候補探索・            （ソース登録 + ページ生成）
      人間が選択したものだけ登録）
  /wikicommit-translate   原文ページ → 翻訳ページ
  /wikicommit-synthesize  既存 entity/ ページ群 → 合成ページ（derived_from）
  /wikicommit-fix         Issue の指摘 / 直接指示 → 既存ページを修正
  /wikicommit-remove      status: removed を付与
  /wikicommit-review      経路B: review_status: reviewed を書き込み
                                    ↓
─── /wikicommit-merge（Git 操作はここに集約）──────────────────────────

  品質チェック → ブランチ → PR → squash merge → main
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ↓                           ↓                           ↓
  レビュー追跡 Issue          生成失敗 Issue              deploy.yml
  （label: wikicommit-       （label: wikicommit-        （Quartz v5 →
    review。pending な          generation-failure。       GitHub Pages）
    ページごとに 1 件）          可視化専用）
        ↓
  人間が Close ──→ review-issue-close-sync.yml
                     → review_status: reviewed に書き換え → 自動マージ
        ↑
  Close する経路は 2 通り: GitHub の Web/モバイル UI から直接 Close /
  /wikicommit-review（経路A。内容を確認したうえで gh issue close）
  指摘がある場合は先に /wikicommit-fix <issue-url> で修正 →
  /wikicommit-merge でマージ → その後に Close（fix 自身は Close しない）

─── 読み取り専用（Git 操作なし・PR も作らない）─────────────────────────

  /wikicommit-search   キーワード検索（FTS5 trigram）
  /wikicommit-ask      RAG スタイルの質問応答（内部で search と同じ索引を使う）
  /wikicommit-quiz     クイズ生成（同上）
  /wikicommit-status   健全性チェック（孤立・未審査・期限切れ・陳腐化 等）
  /wikicommit-serve    npm run preview / build のラッパー

─── 独立した PR 経路（auto-merge しない・人間レビュー必須）─────────────

  /wikicommit-schema-propose → schema/<Type>.md を追加する PR を単独で作成
    （Pass 2b〈#315〉がその場での型追加を担うようになったため、
      本 Skill の役割は事後検出の安全網に変わった）
```

| Skill | コマンド | 実装概要 |
|---|---|---|
| `wikicommit-init` | `/wikicommit-init` | `.wikicommit/` のディレクトリ構造・スキーマを生成。Skills のデフォルト設定を埋め込みから生成する（外部テンプレートリポジトリ依存なし）。theme 入力が非空の場合、theme 文だけから明らかに（obviously）必要と判断できる Schema.org 標準型に限定して型提案を行う（Issue #490。旧 Issue #286 をIssue #404 が廃止した後の限定復活。`wikicommit-collect`・`wikicommit-generate` Pass 2b との役割分担は `docs/DesignDoc-data.md` §3.3 参照） |
| `wikicommit-generate` | `/wikicommit-generate <path\|url>` / `/wikicommit-generate --regenerate <page\|--type <Type>\|--all>` | ソースを `.wikicommit/source/` に登録し、そのままページ生成まで実行。Git 操作は行わない。ハッシュを計算し管理ファイル（`.md`）を生成または更新。ディレクトリ指定時はファイルごとに個別生成。`--regenerate` は既存ページを現在の生成ルールで作り直す**ページ起点**のモード（Issue #578）— 対象ページの `sources` を再取得し Pass 2・Pass 2b を飛ばして Pass 3・Pass 4 のみを実行、`review_status` を `pending` に戻す。`status: retracted` のソース（Issue #737）だけは再取得せず落として作り直し、ページの `sources[]` からもそのエントリを外す（Issue #744。全件が `retracted` なページは作り直す材料が無いためスキップし `/wikicommit-remove` へ誘導する）。新規 Skill にせずオプションにしたのは Pass 1/3/4 を通常生成と共有するため（差分は「Pass 2 を飛ばす」「`review_status` を戻す」「対象の指定方法」に限られる）。詳細は `docs/DesignDoc-pipeline.md` §6.1 |
| `wikicommit-merge` | `/wikicommit-merge` | `.wikicommit/` 配下の未コミット変更を対象に品質チェックを実行し、ブランチ作成・PR 作成・マージ・レビュー追跡 Issue 生成（Issue #313）まで行う |
| `wikicommit-review` | `/wikicommit-review <page>` | frontmatter 補完・sources チェック・整合性チェック（`validate_frontmatter.py` を呼び出す）を行い、`sources` を再取得して独立した事実確認を実施し観点ごとの所見を人間に提示した上でレビュー完了を記録する（Issue #313・#455。全文再掲はソースが取得できない場合や人間が希望した場合のみのフォールバック）。記録方法はページの経路で分岐: 対応するレビュー追跡Issue（`wikicommit-review`ラベル）があれば経路Aのページとみなし `gh issue close` する（`review-issue-close-sync.yml` が `review_status: reviewed` への書き換え・自動マージまで行う）。無ければ経路Bのページとみなし `review_status: reviewed` をローカルに書き込み、その後 `/wikicommit-merge` を呼ぶことで `reviewed` 状態のまま自動マージされる |
| `wikicommit-fix` | `/wikicommit-fix <issue-url>` / `/wikicommit-fix <page-path\|published-page-url> "<fix instruction>"` | フィードバック（Issueの本文+コメント、またはフリーテキスト指示）・対象ページ・sources 元文書をコンテキストとして LLM に渡し、修正案を提示。人間確認後 `/wikicommit-merge` で PR 作成（Issue #454。ページパス直接指定・公開Wiki URL指定にも対応）。対象ページが翻訳ページ（`translated_from` あり）で、指摘が翻訳固有ではなく内容由来（原文にも影響しうる）と判定した場合、修正対象を原文ページへリダイレクトするか確認する（Issue #529。リダイレクトしてもIssueへのリンクバックは同じIssue番号のまま）。マージ完了後に元 Issue へ返す完了コメント（Step 7）は、**Step 2 で特定した対象ページの `lang`**（＝報告者が実際に読んだページ）で描画する — リダイレクトが働いて原文ページを直した場合も、読んだページは変わらないためこちらに従う（Issue #824。Issue #808 の `primary_lang` を置き換えた。追跡 Issue 本文が `primary_lang` を採る Issue #773 とは読み手が違うため答えも違う。`docs/DesignDoc-pipeline.md` §6.2 の該当コールアウト参照） |
| `wikicommit-remove` | `/wikicommit-remove <page>` | status: removed を付与する（ローカル変更）。翻訳ページも同時処理。その後 `/wikicommit-merge` で PR 作成 |
| `wikicommit-ask` | `/wikicommit-ask <question>` | `.wikicommit/entity/` を検索し、LLM が回答を生成。MCP なしで知識参照を可能にする |
| `wikicommit-search` | `/wikicommit-search <query> [--lang <lang>] [--no-expand]` | `.wikicommit/entity/` をキーワード検索し、結果を列挙する。クエリ語は同義語・上位語・略語へ拡張され（Issue #581。`--no-expand` で無効化）、さらに `config.yml` の対象言語ごとに翻訳して言語ごとに逐次検索し、結果をマージする（Issue #582。`translated_from` で結ばれた同一ページは1件に集約し、抑制された他言語版は `(also in: <lang>)` として表示する。`--lang` 明示時は言語をまたぐ fan-out をスキップ＝オプトアウト手段を兼ねる。ただし `<lang>` への翻訳は止めない）。対象言語は `config.yml` に加えて `.wikicommit/entity/` 直下に実在する言語ディレクトリも含める（全クエリが `--lang` を伴うため、含めないと未設定言語のページが端から届かなくなる）。`--limit` は言語数に関わらず言語ごと10件・マージ後10件まで |
| `wikicommit-status` | `/wikicommit-status` | 未処理ファイル数・未審査ページ数・孤立ページ数・wanted ページ数・Type セグメント取り違え数・スキーマファイル未整備の型数・expires_at 期限切れ数を表示。`check_orphans.py` / `check_wanted_pages.py` / `check_expires.py` / `check_ingest_freshness.py` / `check_translation_status.py` / `check_derivation_freshness.py` を呼び出して集計するほか、`check_actions_pr_permission.py`（Issue #478）でGitHub Actions PR権限設定も、`check_property_wikilink_reinforcement.py`（Issue #539）で型テンプレートのproperty-value WikiLink補強の非対称性も、`check_recurring_characters.py`（Issue #560）で `properties.character` にプレーンテキストのまま埋もれた登場人物も、`check_unlinked_entity_mentions.py`（Issue #561）で実在するページを指すのにリンクされていない `properties:` 値も、`check_installed_type_usage.py`（Issue #565）でページが 0 件のインストール済み型・祖先型に落ちている可能性も、`check_self_referential_tags.py`（Issue #571）でページ自身の title/type を繰り返すだけのタグも、`check_retracted_sources.py`（Issue #737）で人間が取り下げたソースになお立っているページも、`check_schema_coverage.py`（Issue #575）で専用スキーマファイルが無いまま使われている `type:` 値も確認する |
| `wikicommit-collect`（Phase 3〜） | `/wikicommit-collect` | `config.yml` の `theme` に基づき、ローカルフォルダおよび Web から未取り込みの関連ソース候補を探索し一覧提示する。引数なし（research guidance が渡されなかった）実行では、探索の前に Step 3.5（俯瞰ステップ）が走る（Issue #672。`wikicommit-synthesize` の Step 0〈Issue #586〉と同型のものを探索側に置いたもの）— `build_survey_view.py`・`check_wanted_pages.py`・`check_orphans.py` の 3 本を呼んで Wiki の現状を俯瞰し、着眼点を最大 5 件提案して人間が選ぶ。選ばれた着眼点はそのまま Step 2 が保持する research guidance になり（`theme` を置き換えない）、Step 4/5 がそれを使う。合流点は既存であり新しい概念は要らない。`theme` は Wiki 全体の内容スコープ（Issue #564 がその役割に限定した）であり、1 回の探索の方向づけとしては粗すぎる — 方向づけの受け口自体は元からあったが、そこに何を打てばよいかを知る手段が collect の中に無く、引数なし実行が毎回同じ広さで探して既に厚い領域の候補を繰り返し拾っていた。**自動探索にはしない**: 判断するのは人間で、俯瞰は材料を出すだけである（Issue #586 と同じく idea support であって品質ゲートではない）。何も選ばれなければ何も探索せず停止し、非対話実行でも停止する（`/wikicommit-collect <guidance>` と明示すれば俯瞰を飛ばせる）。却下された着眼点はどこにも永続化しない — Step 8 が `source-policy.md` の `rejected:` に書くのは「人間が却下したソース URL」であって着眼点ではなく、混ぜない。`--index <url>` だけが渡された場合は guidance が空なので発動する（`--index` は探索の入口であって着眼点ではない）。`TYPE_MISMATCH:` は着眼点の候補にしない（実体は在りリンク 1 語の誤りで、要求される行動が `WANTED:` と正反対。Issue #563）。`/wikicommit-status` を丸ごと呼ぶこともしない（`check_ingest_freshness.py` が管理ファイルを書き換える副作用を持ち、探索の前に副作用を起こす理由が無い）。Claude Code のネイティブ Web 検索・既存 Skills を活用し専用クローラは自作しない。Web 探索は theme の抽象度そのままの広いクエリ 1 本ではなく、6 つのパス（theme の具体語・`filetype:pdf`・既登録ソースのホストへの `site:`・`theme`／`source-policy.md` が名指しする発信元への `site:`・`check_wanted_pages.py` の `WANTED:` を検索語にするパス・リポジトリホスト）からなるクエリ群として投げる（Issue #666。1 パスあたり最大 5 本・1 実行あたり最大 20 本。広いクエリ 1 本が返すのは分布のヘッドであり、theme が名指しする個人ブログ・小さな OSS リポジトリ等のテールには構造的に到達しないため。探索履歴は永続化せず、各パスは実行のたびに Wiki の現在の状態から導出される）。候補提示直後、候補群のタイトル・要約を俯瞰して `installed schema/` 外の Schema.org 標準型が明確に良い適合先と判断した場合、`wikicommit-generate` Pass 2b の対話実行時と同じ Enter ベース承認 UX で型を提案し、承認されれば `.wikicommit/schema/<Type>.md` をその場で新規作成する（Issue #489。候補提示自体が対話的なためバッチ実行特有の「確認が取れずデフォルト却下」問題が起こらない — Pass 2b 自身は非対話実行検出時に別の自動承認経路を持つ〈Issue #507〉が、`wikicommit-collect` のこのステップは常に対話実行される前提のため対象外）。`.wikicommit/source-policy.md` の `index_only:`（またはコマンド引数 `--index <url>`）に該当するページは候補にせず、**その参照節から一次資料 URL を掘って候補に流し込む**（Issue #570。索引ページ自身は決して登録しない — 本文を読んで「何を書くか」を決めると、そのページが `sources:` に無いため Pass 4 の照合も帰属表示も効かない無帰属の二次的著作物になる）。候補は人間が確認・選択した分のみ `.wikicommit/source/` に登録（`wikicommit-generate` を内部呼び出し）。著作権・ライセンスリスクを踏まえ、登録前の人間承認を必須とする |
| `wikicommit-quiz`（Phase 3〜） | `/wikicommit-quiz [--topic <keyword>] [--lang <lang>] [--difficulty=easy\|medium\|hard]` | `.wikicommit/entity/` 全体から `wikicommit-search` 相当の検索で関連ページを収集し、LLM がクイズを生成して会話内に出力する。ファイル書き出しは行わない。`--topic` 指定時は `wikicommit-search` と同じクエリ語拡張（Issue #581）・クロスリンガル検索（Issue #582。`--lang` でオプトアウト）を行う — 同一ページの複数言語版が両方ヒットすると同じ事実についての設問が2問できてしまうため、重複排除はここでは必須。出題・解説の言語は `--topic` の言語（省略時は `primary_lang`）に固定し、grounding ページの言語に引きずられない。`--topic` 省略時の分岐（`primary_lang` 配下からランダムサンプリング）はクエリ自体が存在しないため対象外 |
| `wikicommit-synthesize`（Phase 3〜） | `/wikicommit-synthesize [<topic>]` | 指定した概念・用語について `wikicommit-ask` と同様に関連ページを収集し、LLM が新規ページを合成する。`generate` が外部ソースから作るのに対し、こちらは既存 `entity/` ページ群から作る（Issue #283。`wikicommit-document` からの改名・全面改訂）。出力先は **`.wikicommit/view/<lang>/<slug>.md`**（Issue #675。旧 `.wikicommit/entity/<lang>/<Type>/<slug>.md` から移動。旧来の `.wikicommit/exports/` という仮置き概念は Issue #283 が既に廃止済み）で、品質ゲート対象・`/wikicommit-merge` でPR化可能な点は変わらない。**`type:` を持たず**、代わりに任意の `kind`（`practice` / `landscape` / `comparison` / `pattern` / `timeline` / `debate` の 6 値。「複数ページを見て何をするか」を表し、Schema.org 型の「何についてか」とは直交する）を持つ — 型選択ステップは削除され、同じ topic の 2 回の実行が別々のパスに解決される問題（Issue #545）も構造的に消えた。公開先は `content/<lang>/View/<slug>.md`、WikiLink は `[[View/<slug>]]`（`View` は予約 Type セグメント。言語を先頭に保つことで breadcrumbs / language-switcher / explorer の 3 プラグインが無改修で済む）。詳細は `docs/DesignDoc-data.md` §4.5.1。出自は `derived_from`（`{path, source_commit}` の配列）フロントマターに記録し、`sources` は書かない。本文生成後・書き出し前に、`wikicommit-generate` Pass 4 と同型のレビューサブエージェント（Step 5.5）がgrounding ページ群と照合する（Issue #674。3 つの生成経路のうち合成だけが検証を持たなかった。返却形式は §4.6 のエージェント間 JSON をそのまま使い、`source_file` には grounding ページのパスが入る。再試行は `generate.max_retries` を流用し、上限超過時は書き出さずに停止・報告する。grounding ページ同士の食い違いは `page_at_fault: "other"` と同じ扱いで FAIL にせず完了報告に列挙する）。grounding set には `derived_from` を持つページを入れない（同 Issue。合成ページを通常ページの 1 段上に留める。索引からは除外しないため `/wikicommit-search` からは引き続き見つかる）。grounding のうち `review_status: pending` のページは本文生成の前に列挙して伝える（警告でありゲートではない）。書き出し後、そのページの言語の view index（`.wikicommit/view/<lang>/index.md`）を `rebuild_index.py` で再構築する（Issue #547。Issue #675 以降は Type 別ではなく言語別）。引数なしで実行した場合は Step 0（俯瞰モード。Issue #586）が先行し、`build_survey_view.py` が返す Wiki 全体の縮約ビュー（各ページの title/type/tags/`properties.description`/`##` 見出し/発リンク + リンクグラフ由来のハブ・タグ集計）から、複数ページを横断して初めて見える着眼点を最大5件提案する（他 Skill 群と同じ 5 件閾値）。人間が選んだ着眼点がそのまま `<topic>` として Step 1 以降に合流し、選ばれなかった候補はどこにも永続化しない。候補提示は非決定論的（実行ごとに結果が変わる）であり、品質ゲートではなく着想支援である |
| `wikicommit-serve`（Phase 3〜） | `/wikicommit-serve [--build]` | `npm run preview` / `npm run build`（Quartz v5 のローカルビルド・プレビューサーバー）の薄いラッパー。Git 操作を行わない読み取り専用 Skill（Issue #276。`wikicommit-review` との名称衝突解消のため Issue #381 で `wikicommit-preview` から改名）。`quartz.config.yaml`（`/wikicommit-init --quartz`）の存在が前提。既存の `package.json` に WikiCommit のビルドスクリプトがマージされていない場合はその旨を案内して停止する |
| `wikicommit-translate`（Phase 3〜） | `/wikicommit-translate <page> [--lang <target>]` / `/wikicommit-translate` | 原文ページ全文 + `DefinedTerm/` 用語定義 + 原語↔訳語の対応表（対象言語の `DefinedTerm` ページの `title` のみ。Issue #554）を LLM コンテキストに注入して翻訳を生成し、`translated_from` / `source_commit` / `translated_at` を付与してローカル書き出しする（Git 操作は行わない。Issue #280）。引数なしの一括モードは作業リストを `DefinedTerm` 型のペアが先頭に来るよう並べ替えた上で（Issue #554。用語集を先に確定させてから本文を訳すため）、`check_translation_status.py` の `UNTRANSLATED` + `STALE` 件数が5件を超える場合、確認の上でその順序の先頭5件のみ処理できる（`wikicommit-generate` / `wikicommit-collect` と同じ閾値）。`--lang` 省略時は `config.yml` の `translation.targets` 全言語を対象にする（空配列の場合はエラー終了） |
| `wikicommit-update`（Phase 3.1〜） | `/wikicommit-update` | インストール済みの配布物とリポジトリを同期し、結果を PR にする（Issue #713）。`wikicommit-schema-propose` と同じく**自前で PR を作り auto-merge しない** — 孤児の削除と `review` ファイルの差分適用はどちらも人間の判断であり、PR がその確認の場になる。処理は 9 段（版の突き合わせ → `check_distribution_freshness.py` によるドリフト検出 → `init.py --no-overwrite` による `overwrite` の適用 → 孤児削除の確認 → `review` の差分提示 → `wikicommit_version` の刻印 → 検証 → PR → 報告）。**`.claude/skills/` 自体の更新は Skill の外に置く** — 自分の SKILL.md を書き換えても実行中のエージェントは古い指示を持ったままになるため、`npx skills add` は人間が先に実行する前提とし、SKILL.md 冒頭でそれを案内する。`wikicommit-init --update` にしなかったのは、`wikicommit-init/SKILL.md` が既に 539 行あり、Skill 起動のたび全文がコンテキストに載る（§11.9）ため — 「無から作る」と「既にあるものを突き合わせて人間に見せる」は指示の性質が違い、フラグにすると init を叩くたびに使わない指示を運ぶことになる。**3-way merge は行わない**（配布リポジトリが単一コミットの積み重ねで base が復元できない。`docs/DesignDoc-data.md` §3.3）ため、`review` の扱いは 2-way diff + 人間の判断が上限になる。`quartz.config.yaml` の提示ではリポジトリ固有キー（`pageTitle` / `pageTitleSuffix` / `locale` / `baseUrl` / `links` / `theme` / `translation.*`。うち `pageTitle` / `pageTitleSuffix` / `locale` / `links` は init が `{...}` プレースホルダを置換して書くため、テンプレート側にはプレースホルダが残っている — 取り込ませると `{LOCALE}` がそのまま config に入り、YAML がロケール文字列ではなくマッピングとして読む）を差分の文脈に並べない — 検出条件を二重に持つのではなく、新しく現れたキーを見せるときに周辺のユーザー自身の設定でそれを埋もれさせないための緩和策である |
| `wikicommit-schema-propose`（Phase 3〜） | `/wikicommit-schema-propose` | `check_schema_coverage.py` で `.wikicommit/schema/` に専用ファイルのない `type:` 値を検出し（Issue #285）、Schema.org 標準型として実在すれば標準型ファイル、実在しなければ `custom/` 型ファイルを新規追加する PR を作成する。ブランチ名 `wikicommit/schema-propose-<Type>` で重複提案を防止。`.wikicommit/schema/` への書き込みが唯一の役目で、既存ファイルの編集・削除は不可。他の PR 作成系 Skill と異なり **auto-merge しない**（人間レビュー必須）。`wikicommit-generate` Pass 2b（Issue #315）がその場での型追加を主経路として担うようになったため、本 Skill の役割は事後の安全網（Pass 2b 以前に生成済みのページの救済等）に変わった |

### 11.3 Skill ディレクトリの構造

各 Skill は `SKILL.md` と、Skill のみが使う `scripts/` サブディレクトリで構成する。

```
.claude/skills/
├── wikicommit-init/
│   ├── SKILL.md
│   └── scripts/
│       ├── init.py          # ディレクトリ構造・テンプレート展開
│       └── templates/       # 生成するファイルのテンプレート
│           ├── config.yml
│           └── schema/
├── wikicommit-generate/
│   ├── SKILL.md
│   └── scripts/
│       └── add_source.py    # 管理ファイルのパス計算・ハッシュ・生成・status 更新
├── wikicommit-merge/
│   └── SKILL.md             # 品質チェック呼び出し + git 操作がメインのため scripts/ なし
└── wikicommit-remove/
    ├── SKILL.md
    └── scripts/
        └── remove_page.py   # frontmatter への status: removed 付与
```

SKILL.md の記述例（`wikicommit-generate`）:

```markdown
# wikicommit-generate

WikiCommit ソース登録 + Wiki ページ生成 Skill。Git 操作は行わない。

## 前提 Skill（テキスト抽出）

以下の Skill が未インストールの場合、処理前にインストールを案内してください：
- PDF: `npx skills add https://github.com/anthropics/skills --skill pdf`
...

## 処理フロー

1. 引数からソース種別を判定し、.wikicommit/source/ に管理ファイルを登録または更新する
2. pending / outdated な管理ファイルを読み込み、source.path / source.url に基づいてソースを取得する
3. 拡張子に応じた Skill でテキスト抽出し、ページ生成（多段生成アルゴリズム §11.6）を実行する
...
```

### 11.4 将来のマルチエージェント対応

MVP では Claude Code のみを対応対象とする。`.wikicommit/schema/` は将来の全エージェントで共通利用できるように維持し、他エージェントへの対応時はそのエージェントが要求する配置場所に薄い連携ファイルを追加する。

| エージェント | エントリポイント |
|---|---|
| Claude Code | Skill 定義（`.wikicommit/schema/` を参照） |
| GitHub Copilot | 任意の既存プロジェクト設定（`.wikicommit/schema/` を参照） |
| その他 | エージェント固有の設定ファイル → `.wikicommit/schema/` を参照 |

### 11.5 スクリプト委譲パターン

Skill のプロンプト（SKILL.md）は LLM への指示であり、決定論的な操作・全ファイル走査・グラフ解析のような**再現性・網羅性が必要な操作**を LLM だけで行うと漏れや誤差が生じる。このような操作はスクリプトに委譲し、Claude Code が Bash ツール経由で呼び出す。

スクリプトの置き場所は **呼び出し元** で決まる：

| 呼び出し元 | 置き場所 | 理由 |
|---|---|---|
| Skills のみ | `.claude/skills/<name>/scripts/` | Skill ディレクトリと一緒に配布 |
| 複数 Skills から呼ぶ | `.wikicommit/scripts/` | リポジトリで Git 管理されるため全 Skill から参照可能 |

#### Skill 内スクリプト（`.claude/skills/<name>/scripts/`）

決定論的なファイル操作・パス計算・YAML 編集など、LLM に任せると再現性が下がる操作を担う。

| Skill | スクリプト | 役割 |
|---|---|---|
| `wikicommit-init` | `scripts/init.py` | ディレクトリ構造作成・`templates/` からのファイル展開 |
| `wikicommit-init` | `scripts/print_next_steps.py` | 「次のステップ」案内文の組み立て（Issue #350。3 変種のほぼ同一な散文を SKILL.md に重複させないため） |
| `wikicommit-init` | `scripts/_root_outputs.py` | ルート生成物の宣言的な一覧。上記 2 スクリプトが共有する単一の情報源で、`init.py` の verbatim コピーと `print_next_steps.py` の `git add` 案内の両方をここから組み立てる（Issue #642。下記コールアウト参照） |
| `wikicommit-generate` | `scripts/add_source.py` | 管理ファイルのパス計算・SHA-256・生成・status 更新・ソースの同一性判定（URL: Issue #572／ファイルパス: Issue #573）・`source.license` の初期値決定（既知ドメイン対応表と `--license`。Issue #558。`docs/DesignDoc-data.md` §4.3）・登録時の partial extraction 通知（`partial_extraction_note()`。Issue #715 — 静的取得で本文は取れるが一部が黙って落ちる URL 形〈GitHub の Issue / PR スレッド〉を、ブロックせず登録時に一度だけ知らせる。ShareAlike 通知と同じ形）。`--license-for-url` は同じ対応表を引くだけの読み取り専用モードで、**この 1 モードに限り `wikicommit-collect` からも呼ばれる**（Issue #646。下記コールアウト参照） |
| `wikicommit-remove` | `scripts/remove_page.py` | frontmatter への `status: removed` / `removed_at` 付与 |
| `wikicommit-ask` | `scripts/resolve_source_cache_path.py` | `--include-source`（Issue #470）専用。`sources[].url` から `.wikicommit/source/url/` 配下を実走査して一致する ソース管理ファイルを特定し、その実パスから scratch-path を導出して `.wikicommit/.cache/ingest-fetch/` 内のキャッシュファイルを解決する。URL から `add_source.py` の `url_to_filename()` を再計算する方式は Issue #191 以前の旧フラット命名の管理ファイル（自動移行されない）で実際の scratch-path と食い違うため、実ファイルを走査して特定する方式を採る。**登録側の `add_source.py` も同じ走査方式に移行した** — `process_url()` が Issue #572 で（`find_mgmt_file_for_url()`）、`process_file()` が Issue #573 で（`find_mgmt_file_for_path()`。`type: path` 側は導出が拡張子を捨てていたため `paper.pdf` と `paper.docx` が衝突し、しかも `SKIP` で止まらず既存管理ファイルを `status: outdated` に書き換えていた）— それまでは導出ファイル名の存在有無を同一性キーにしていたため、クエリ文字列で区別される URL（YouTube の `?v=` 等）が同じ名前に解決されて未登録のまま `SKIP`／別 URL に対する `RECHECK` を返していた。参照側だけが `source.url` を正としていた非対称を解消したもので、2スクリプトは同じ「ファイル名を再計算せず `source.url` で照合する」規約を共有する（実装は共有せず各自に持つ — `add_source.py` は `.wikicommit/scripts/` からの import を一切持たない自己完結スクリプトであり、`remove_page.py` が `normalize_entity_prefix()` を複製しているのと同じ理由による） |

#### 共有スクリプト（`.wikicommit/scripts/`）

`/wikicommit-init` が生成し、リポジトリで Git 管理される。複数 Skills から呼ばれる。

| Skill | 委譲するスクリプト | 理由 |
|---|---|---|
| `wikicommit-merge` | `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_orphans.py` | 品質ゲートとして変更ファイル全件を網羅的に検証するため |
| `wikicommit-review` | `validate_frontmatter.py` | frontmatter 補完前の検証に使う。経路A・経路Bいずれのページに対しても使用する（Issue #313 — 経路Aのページも `wikicommit-review` の対象になった） |
| `wikicommit-status` | `check_orphans.py` / `check_wanted_pages.py` / `check_expires.py` / `check_ingest_freshness.py` / `check_translation_status.py` / `check_derivation_freshness.py` | 全ファイル走査・有向グラフ解析・日付比較・翻訳陳腐化検出／未翻訳検出・合成ページ陳腐化検出を正確に行うため。`check_wanted_pages.py` は Type セグメント取り違え（`TYPE_MISMATCH`）の分離も担う（Issue #563） |
| `wikicommit-status` | `check_distribution_freshness.py` | インストール済みの配布物がテンプレートと一致しているかを全件走査で突き合わせるため（Issue #712）。`.wikicommit/scripts/`・`quartz-plugins/`・2 つの workflow・`*.cjs` は WikiCommit 自身の配布ペイロードであり再 init で更新されるが、**そのリポジトリが更新を要するかを知る手段が無かった** — パイロット 3 件が同一の旧版を抱えていたことは、clone して手で突き合わせて初めて分かった。分類（`update` 列）は `_root_outputs.py` が唯一の情報源で、`init.py` のコピーと`print_next_steps.py` の `git add` 案内も同じ列から導かれる |
| `wikicommit-status` | `check_review_coverage.py` | レビュー記録（`.wikicommit/review/`）を全ページ走査で突き合わせ、集計・未レビュー・抜取候補・失効を出すため（Issue #750）。`record_review.py` が書いたものを読む唯一の主体であり、これが無ければ記録ツリーは常に空のまま残る受け皿になる（Issue #553）。閾値も自動化も持たない — `RISKY:` / `COVERAGE:` を人が読んで `--regenerate` を叩けばループは閉じる |
| `wikicommit-status` | `check_run_records.py` | 実行 1 回を単位とする記録を読み戻すため（Issue #790）。既存の記録層はすべて成果物（ファイル・ソース・ページ・レビュー）を単位としており、**実行が完走したか**・**どれだけかかったか**を答えられる層が 1 つも無かった。とくに前者は、途中で死んだ実行が残す状態が Issue #567 の「まだ順番が来ていない滞留」と見え方が同じで、ガード C（Issue #574）・`rules_version` 不一致（Issue #752）に至ってはファイルを 1 つも変えずに止まるため git に痕跡がゼロになる。`record_run.py` が書いたものを読む唯一の消費者であり、これが無ければ記録ツリーは常に空のまま残る受け皿になる（Issue #553） |
| `wikicommit-status` | `check_retracted_sources.py` | 人間が取り下げたソース（`status: retracted`）を `sources[]` に持つページを全ページ走査で列挙するため（Issue #737）。取り下げは再登録・再取り込みを構造的に止めるが、既に書かれたページには何も起こらない — その差を埋める経路が他に無い。**行動ではなく報告に留める**（`review_status` を戻す案は Issue #724 の規範と噛み合わず、戻しても何が失われたかは伝わらない）。どの経路〈`--regenerate`〈Issue #744 が取り下げたソースを落として作り直す挙動を入れた〉/ `/wikicommit-fix` / `/wikicommit-remove`〉を採るかは人間の判断であり、各所見に「そのページに残っている他のソースの件数」を添えることがその判断材料になる |
| `wikicommit-status` | `check_actions_pr_permission.py` | "Allow GitHub Actions to create and approve pull requests" 設定の再確認を `gh api` 経由で決定論的に行うため（Issue #478。この委譲先だけが `.wikicommit/` 配下の走査ではなく `gh` CLI 呼び出しを要する） |
| `wikicommit-status` | `check_schema_coverage.py` | `type:` 値に対応する専用スキーマファイルが無いページ（＝ `default.md` へのフォールバック下で生成され、その型の `granularity`・`properties:` 候補・本文テンプレートが適用されていないページ）を全ページ走査で継続的に可視化するため（Issue #575。`wikicommit-generate` の Completion Notice は生成時の1回きり、`validate_frontmatter.py` の WARNING は変更ファイルにしか届かず、スキーマファイルを後から動かした場合の検知経路が無かった） |
| `wikicommit-status` | `check_property_wikilink_reinforcement.py` | `.wikicommit/schema/` 全型テンプレートの `properties:` キーについて Schema.org RANGE 分類（`check_schema_org_type.py --show-range` と同じロジック）を機械的に突き合わせるため（Issue #539。Issue #523 が手動監査で発見した非対称性の再発検出を自動化） |
| `wikicommit-status` | `check_recurring_characters.py` | `properties.character` のプレーンテキスト値を全ページ横断で集計するため（Issue #560）。`ShortStory.md`/`Book.md` が下す「この登場人物は独立ページに値するか」の判断を後から見直す仕組みが無く、しかも `check_wanted_pages.py` は WikiLink しか読まないためプレーンテキストの名前は wanted page として計上すらされない（Issue #318 の限界が `properties:` の値にも同じように効く）。作品をまたぐ再登場は 1 回の生成実行の中からは見えないため、事後の横断集計でしか拾えない |
| `wikicommit-status` | `check_unlinked_entity_mentions.py` | エンティティ型を range に持つ `properties:` キーの値を既存ページと突き合わせるため（Issue #561）。`check_wanted_pages.py` の鏡像 — あちらが「リンクはあるが実体がない」を見るのに対し、こちらは「実体はあるがリンクされていない」を見る。生成時の判断が取り込み順序に引きずられて割れても、`action: update` はそのページ自身のソースが再 ingest された時にしか起きないため自然には回復しない |
| `wikicommit-status` | `check_installed_type_usage.py` | インストール済みスキーマファイルと実際の `type:` 使用状況を全ページ走査で突き合わせるため（Issue #565）。`check_schema_coverage.py` の対 — あちらは「使われている型にファイルが無い」を見るが、逆（ファイルが在るのに使われない）はどのゲートにも掛からなかった。祖先型は常に技術的に正しいため、インストール済みの具体型が選ばれなくても品質チェックはすべて通る |
| `wikicommit-status` | `check_self_referential_tags.py` | ページ自身の `title`／`type` を繰り返すだけのタグを全ページ走査で検出するため（Issue #571）。Issue #275 が散文で明示的に禁じたにもかかわらず再発しており、生成時の指示だけに依存して検出手段が無いルールは drift する。`title`／`type` との文字列比較で決定論的に判定できる |
| `wikicommit-search` | `search_index.py` | FTS5 trigram インデックスの構築・bm25 ランキング・スニペット生成には SQLite クエリが必要なため（Phase 3〜。Grep ベースの Phase 1 実装から移行済み） |
| `wikicommit-translate` | `check_translation_status.py` / `rebuild_index.py` | 前者は一括モードの対象件数（`UNTRANSLATED` + `STALE`）算出に全ページ走査・翻訳有無判定を正確に行う必要があるため。後者は `index.md` 更新を「全ソース/ペア処理後に1回」という手順としてLLMの記憶に委ねていたことによる更新漏れ対策（Issue #406。`wikicommit-generate` と共有） |
| `wikicommit-synthesize` | `build_survey_view.py` | 引数なしの俯瞰モード（Issue #586）で、Wiki 全体を1つのコンテキストに収まる縮約ビューへ落とすため。「全体を俯瞰する」以上、走査の網羅性そのものが機能の前提であり、SKILL.md のプローズ（grep の羅列）に委ねると取りこぼしが黙って結果を損なう。スクリプトは判断を行わない — 縮約ビューから着眼点を選ぶのは LLM の仕事で、そちらは本質的に非決定論的 |
| `wikicommit-synthesize` | `rebuild_index.py` | 合成ページを書き出しただけでは view インデックス（言語別。Issue #675）に載らず、合成ページはどのソースからも生成されない（`derived_from` のみを持つ）ため `wikicommit-generate` が走る契機自体が無いリポジトリでは無期限に未掲載のまま残るため（Issue #547）。他 2 Skill と異なり、書き出した 1 ディレクトリのみを引数に指定して呼ぶ（`.wikicommit/view/<lang>`） |
| `wikicommit-generate` / `wikicommit-review` / `wikicommit-synthesize` | `.wikicommit/review-rules.md`（スクリプトではなくデータだが、委譲の構造は同じ） | レビュー規律を 3 箇所で言い直さないため（Issue #752）。移すのは「何を検査するか」だけで、段取りは各 Skill に残る。`_root_outputs.py` に `update: overwrite` で登録し、リポジトリ側からの編集を許さない — 許すと Wiki が自分のレビューを黙って弱められる |
| `wikicommit-generate` / `wikicommit-translate` / `wikicommit-synthesize` / `wikicommit-merge` | `record_run.py` | 実行 1 回につき 1 ファイルを開いて閉じるため（Issue #790）。対象をこの 4 つに絞る基準は「途中で死んだときに、中途半端な状態と『まだ順番が来ていない』状態が区別できなくなるもの」であり、`fix` / `remove`（単発かつ小さく差分そのものが結果）・`collect`（対話前提）・読み取り専用 Skill（状態を変えない）は入らない。開始と終了の打刻を LLM の記憶に委ねる形だが、**忘れても壊れない** — 開始があって終了が無い記録が、そのまま「完走しなかった」の答えになる（Issue #750 の `page_content_hash: ""` と同じ形）。記録は git で追跡しない点だけが Issue #750 と逆で、ローテーションが可能になり `wikicommit-merge` が無改修で済む |
| `wikicommit-generate` / `wikicommit-review` / `wikicommit-synthesize` / `review-issue-close-sync.yml` | `record_review.py` | レビュー 1 件を不変ファイルとして書き出すため（Issue #750）。判定は LLM が下し、ファイル手術はスクリプトが行う（Issue #474）。`source_quote` の除去・`page_content_hash` の計算・`reviewed_sources` の収集を呼び出し側の指示遵守に委ねないことが要点で、とくに `page_content_hash` は `reset_review_on_content_change.py` の 6 フィールド無視リストを **import** して使う（複製すると drift し、drift は「誤った鮮度を黙って報告する記録」として現れる） |
| `wikicommit-generate` | `check_schema_org_type.py --list-type-names` / `check_schema_org_type.py --describe` / `check_schema_org_type.py --list-installed-hierarchy` / `check_schema_coverage.py` / `rebuild_index.py` / `check_extraction_quality.py` / `reconcile_ingest_status.py` | 前 2 つと `check_schema_coverage.py` は Pass 2b の型の要否判断用で、`--list-type-names` が約 933 型の**名前だけ**をプリロードし、そこから絞り込んだ候補の説明文を `--describe` が引く（Issue #315。旧 #285 の `better_type_candidate` 検出用途を置き換え。2 段階にしたのは Issue #798 — この一覧が果たしているのは想起であって存在保証ではなく〈実在は候補承認後の `--type` が決定論的に確かめる〉、想起には誰も検討していない 928 型の説明文が要らないため。147 KB → 約 14 KB）。あわせて未スキーマ化 type 文字列一覧で収束を誘導する。`--list-installed-hierarchy` は Pass 2c にインストール済み型同士の祖先／子孫関係を渡すため（Issue #565。祖先型は常に当てはまるため、関係を示さないと粗い型が既定で選ばれる — 語彙から決定論的に導ける情報なのでモデルの記憶に委ねない）。`rebuild_index.py` は全ソース処理後の `index.md` 更新を決定論的スクリプトに委譲し、長い多段生成の末尾でLLMが更新を忘れるリスクを排除するため（Issue #406）。`check_extraction_quality.py` は「非空だが無意味」な抽出結果（既知JS-shellドメイン・低情報密度）および「取得能力の不足による partial extraction」（Issue #574）の判定を、LLMの主観的判断ではなく決定論的ロジックに委ねるため（Issue #425。ただし判定結果の扱いは3ガードで異なり、既知JS-shellドメインはそのソースをブロック、取得能力の不足は処理全体を停止、低情報密度は人間に続行可否を確認する警告である — Issue #562・#574）。`reconcile_ingest_status.py` は `status: pending` の管理ファイルのうち内容が既に公開ページの `sources` に使われているものを検出・是正するため（Issue #474。詳細は本節末尾の callout 参照） |
| `wikicommit-update` | `check_distribution_freshness.py` / `rebuild_index.py` / `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_orphans.py` | 前者はドリフト検出そのものを担い（Issue #712 で`wikicommit-status` と共有する共通スクリプトとして新設済み。呼び出し元が 2 Skill になるため §11.5 の規則どおり`.wikicommit/scripts/` に置かれている）、残りは更新後の検証に使う。`wikicommit-init/scripts/init.py` も`--no-overwrite`（`overwrite` の適用）・`--update-version`（版の刻印）・`--add-config-keys`（欠落キーの加算）の3 経路で呼ぶ — こちらは Skill 内スクリプトへの越境呼び出しにあたるが、`add_source.py --license-for-url`（Issue #646）と違い**同じ Skill が持つ設定ファイル生成のロジックそのもの**であり、複製すると `_root_outputs.py` の `update` 列が唯一の情報源であるという Issue #712 の前提が崩れる |
| `wikicommit-schema-propose` | `check_schema_coverage.py` / `check_schema_org_type.py` | schema/ 未カバー type の網羅的集計、および型・プロパティが Schema.org 語彙に実在するかの決定論的検証（オフライン・遅延生成、Git管理下の`.wikicommit/schemaorg-vocab.json`。Issue #319）が必要なため（Issue #285） |
| `wikicommit-collect` | `check_extraction_quality.py`（`check-domain` のみ。`check-fetch-capability`〈Issue #574〉・`check-density` は候補提示ステップでは使わない — 前者は取得を実際に行う Pass 1 の関心事、後者は取得後にしか判定できないため） | Web候補提示ステップで、既知JS-shellドメインの候補を `wikicommit-generate` と同じ判定ロジックで事前に除外するため（Issue #425） |
| `wikicommit-collect` | `check_wanted_pages.py`（`WANTED:` 行のみ。`TYPE_MISMATCH:` は対象外 — 実体は別 Type に在るので欠けているものが無く、必要なのは新しいソースではなくリンク 1 語の修正であるため） | Web候補探索で「この Wiki が WikiLink で参照しているのに実体ページが無い概念」を検索語として使うため（Issue #666）。「Wiki に何が欠けているか」は既に決定論的に計算されており、それを探索の入力に回していないだけだった — 新機構を作らずに Purpose → Knowledge Gap → Source の転換を最小の形で実装したものにあたる。取得失敗・`WANTED:` 0 件のときは黙って飛ばし実行をブロックしない（複数ある探索パスの 1 つに過ぎないため）。**限界**: `WANTED:` が持つ slug は言語中立な英語識別子（Issue #193）であり、非英語 Wiki では原語の検索語に一致しないことがある |
| `wikicommit-collect` | `build_survey_view.py` / `check_orphans.py`、および `check_wanted_pages.py`（Step 3.5 では上記の探索語用途とは別に、`WANTED:` を着眼点の根拠として読む） | Step 3.5 の俯瞰ステップで、Wiki の現状を 1 つのコンテキストに収まる形で読むため（Issue #672）。3 本はそれぞれ別の問いに答える — `build_survey_view.py` は「何があるか」（`TYPE:` 件数・`HUB:`・`TAG:`・各ページの見出しと発リンク。1〜2 ページしかない型が手つかずの領域として見える）、`check_wanted_pages.py` の `WANTED:` は「Wiki 自身が書きたいと表明した穴」、`check_orphans.py` の `ORPHAN:` は出自ソース付き（Issue #570）なので「1 ページしか作っていないソース」＝薄い領域が見える。いずれも読み取り専用で、スクリプトの新設も変更もしない。`build_survey_view.py` はこれにより `wikicommit-synthesize` 専用ではなくなった |
| `wikicommit-collect` | `wikicommit-generate/scripts/add_source.py --license-for-url`（Skill 内スクリプトへの唯一の越境呼び出し。下記コールアウト参照） | Web候補提示ステップで、登録時に記録されるのと同じ既知ライセンスを候補行に併記するため（Issue #646。ShareAlike の警告を登録の 1 段手前へ前倒しする〈Issue #570〉） |

> **ルート生成物の一覧は 1 つに保つ（Issue #642）**: `init.py` が書き出すルートレベルのファイルと、`print_next_steps.py` がユーザーに提示する `git add` 案内は、長らく互いに独立した 2 つの手動リストだった（`wikicommit-init/SKILL.md` の散文を数えれば 3 つ）。この構造の実害は仮定の話ではない — Issue #434 で追加された `install-local-plugins.cjs` が `init.py` にだけ入り案内から漏れた結果、`--quartz --quartz-pages` で init した全リポジトリで初回 push の GitHub Pages ビルドが `postinstall` の MODULE_NOT_FOUND により必ず失敗した（Issue #556。パイロット 2 例で再現）。
>
> Issue #556 は逆向きの回帰テスト（案内どおりに `git add` した後に未追跡ファイルが残らないことの検証。`tests/test_smoke_local.py`）でこの**検知**を自動化したが、2 つのリストを手で同期させる構造そのものは残っていた。Issue #642 は `.claude/skills/wikicommit-init/scripts/_root_outputs.py` に宣言的な一覧を置き、**リストを 1 本に減らす**方を採った。`print_next_steps.py` はここから `git add` 行を組み立て、`init.py` は verbatim コピーが可能なエントリ（`template` フィールドを持つもの）をこの一覧から駆動する。
>
> **「init.py が書き出す ＝ ユーザーがコミットする」に収まらない 3 種の例外を、呼び出し側の特殊分岐ではなく一覧上で表現できることが要件だった**: (1) `.gitmodules` / `quartz` は案内には出るが誰も生成しない（ユーザーが `git submodule add` する。`origin="submodule"`）、(2) `.wikicommit/schemaorg-vocab.json` は型提案ステップが実際にネットワークへ出たときにしか存在しない（`condition="vocab_cache"`。`git add` は存在しない pathspec でコマンド全体が異常終了するため、無条件に並べると基盤ファイルのコミットごと落ちる）、(3) `package-lock.json` は `npm install` の副産物であり、同じ理由で `git add` 行から意図的に外して別コマンドとして案内する（`in_git_add=False`。Issue #556）。
>
> **SKILL.md の散文（3 つ目のリスト）は自動生成の対象にしない**。SKILL.md は Skill 起動のたびに全文がコンテキストに載る静的な指示書であり、生成する主体が存在しない。代わりに `tests/test_root_outputs.py` が、Quartz 限定の生成物が散文にすべて現れることを検証する — Issue #556 のドリフトが属したのはまさにこのクラスである。全変種で生成されるエントリ（`.gitignore`・`.wikicommit/entity/`・`review-issue-close-sync.yml`）は SKILL.md 中でパスとして現れず別の言葉で説明されているため、この検証の対象外としている。
>
> **`init.py` の生成処理そのものを一覧から駆動するのは verbatim コピーに限る**。`config.yml` と `quartz.config.yaml` はプレースホルダー置換、`schema`/`scripts`/`quartz-plugins` はディレクトリツリー、`entity`/`source` は `.gitkeep` 付きディレクトリ作成であり、いずれも一覧には載るが（`template=None`）生成コードは `init.py` に残る。

#### 委譲関係の全体像

上の 2 表を、スクリプト側から「どの Skill に呼ばれるか」で見た図。同じスクリプトが複数の Skill から呼ばれる箇所が、`.wikicommit/scripts/`（共有）と `.claude/skills/<name>/scripts/`（Skill 内）を分ける判断基準そのものになっている。

```
.wikicommit/scripts/（共有・/wikicommit-init が配布・Git 管理下）
────────────────────────────────────────────────────────────────────────
validate_frontmatter.py ─────────────┬── merge
                                     └── review
check_wikilinks.py ────────────────────── merge
check_raw_html.py ─────────────────────── merge
check_orphans.py ────────────────────┬── merge
                                     ├── status
                                     └── collect（Step 3.5 の俯瞰）
check_wanted_pages.py ───────────────┬── status
                                     └── collect（WANTED: のみ・探索語として／Step 3.5 の俯瞰）
check_expires.py ──────────────────────── status
check_derivation_freshness.py ─────────── status
check_ingest_freshness.py ─────────────── status   ※唯一 .md を書き換える（副作用あり）
check_distribution_freshness.py ─────┬── status   ※唯一 .claude/skills/ 側を読む
                                     └── update
check_retracted_sources.py ────────────── status   ※source/ と entity/・view/ を突き合わせる
check_review_coverage.py ──────────────── status   ※.wikicommit/review/ を読む唯一の消費者
record_run.py ───────────────────────┬── generate
                                     ├── translate
                                     ├── synthesize
                                     └── merge      ※唯一 .wikicommit/run/（git 追跡外）へ書く
check_run_records.py ────────────────── status   ※.wikicommit/run/ を読む唯一の消費者
record_review.py ────────────────────┬── generate（Pass 4。PASS と discarded の両方）
                                     ├── review    （Step 5）
                                     ├── synthesize（Step 5.5）
                                     └── review-issue-close-sync.yml（kind: human）
check_actions_pr_permission.py ────────── status   ※唯一 gh を呼ぶ
check_property_wikilink_reinforcement.py ─ status   ※唯一 schema/ の型テンプレート自体が走査対象
check_translation_status.py ─────────┬── status
                                     └── translate（一括モードの対象件数算出）
rebuild_index.py ────────────────────┬── generate
                                     └── translate
reconcile_ingest_status.py ────────────── generate
check_extraction_quality.py ─────────┬── generate（check-domain + check-density）
                                     └── collect （check-domain のみ）
check_schema_coverage.py ────────────┬── generate（Pass 2c の収束誘導）
                                     └── schema-propose（検出源）
check_schema_org_type.py ────────────┬── generate（Pass 2b/2c/3）
                                     └── schema-propose
build_survey_view.py ────────────────┬── synthesize（俯瞰モード）
                                     └── collect （Step 3.5 の俯瞰）
search_index.py ─────────────────────┬── search
                                     ├── ask
                                     ├── quiz（--topic 指定時のみ）
                                     └── synthesize

.claude/skills/<name>/scripts/（Skill 内。原則その Skill しか呼ばない）
────────────────────────────────────────────────────────────────────────
wikicommit-init/scripts/init.py ───────────┬── init
                                           └── update（--no-overwrite / --update-version /
                                                       --add-config-keys の 3 経路）
wikicommit-init/scripts/_root_outputs.py ──┬── init.py（verbatim コピーの駆動）
                                           └── print_next_steps.py（git add 案内）
wikicommit-generate/scripts/add_source.py ─┬── generate
                                           └── collect（--license-for-url のみ。唯一の越境）
wikicommit-remove/scripts/remove_page.py
wikicommit-ask/scripts/resolve_source_cache_path.py   ※--include-source 専用
```

> **`add_source.py --license-for-url` — Skill 内スクリプトへの唯一の越境呼び出し（Issue #646）**: 本節冒頭の置き場所の規則（呼び出し元が 1 Skill なら `.claude/skills/<name>/scripts/`、複数なら `.wikicommit/scripts/`）に対する、意図的な 1 件の例外である。`wikicommit-collect` が `wikicommit-generate` の Skill 内スクリプトを直接呼ぶ。
>
> **`.wikicommit/scripts/` へ移さなかった理由**: 移すべき実体は `KNOWN_SOURCE_LICENSES`（登録可能ドメイン → SPDX 識別子の対応表）とそれを引く 2 関数だが、`add_source.py` は `.wikicommit/scripts/` からの import を一切持たない自己完結スクリプトである（上表の `resolve_source_cache_path.py` の行が述べる既存の制約。`remove_page.py` が `normalize_entity_prefix()` を複製しているのと同じ理由による）。したがって共有モジュール化には (a) この制約を壊す、(b) 対応表を 2 か所に複製する、のどちらかが要る。(b) は「登録時に記録される値」と「候補提示で見せる値」が食い違いうるという、この機能が防ごうとしているものそのものを作り込む（食い違ったときの見え方が最悪 — 人間は提示された条件で承認し、記録されるのは別の条件になる）。(a) は 1 モードのために既存の設計制約を壊す。
>
> **代わりに読み取り専用の照会モードを足した**。`--license-for-url <url>` は対応表を引いて `LICENSE: <id>`／`LICENSE: <id> (share-alike)`／`UNKNOWN: <url>` のいずれかを出し、常に exit 0 で、何も書き込まない。対応表は 1 つのまま、呼び出し側は 1 行のコマンドで済む。`tests/test_add_source.py` は照会結果と、同じ URL を実際に登録した管理ファイルの `source.license` が一致することを検証しており、2 経路の drift を CI で止める。
>
> **越境そのものの前例はある** — `wikicommit-collect` Step 8 は既に `wikicommit-generate` の SKILL.md（Step 0）を名指しで実行しており、この 2 Skill の間には元から依存関係がある。本 Issue が足したのは新しい依存ではなく、その依存の粒度が SKILL.md からスクリプト 1 本へ下りたことである。
>
> **候補提示は「不明」を書かない**（Issue #646 の 2 つ目の完了条件）。対応表が持つのは、そのサイトが自サイトのコンテンツ全体に対して明示しているライセンスだけ（初期値は Wikimedia 系 8 ドメイン）なので、実際の候補の大半は `UNKNOWN` になる。ほぼ全行に「ライセンス: 不明」が付くと読み手はその行を読み飛ばすようになり、`wikicommit-collect` は同じ理由（ほぼ常に空になるステップを独立させない）で Type Proposal を Step 7 に畳み込んでいる。代わりに候補一覧の前置きに 1 度だけ「ライセンスは確認済みのサイトにのみ表示され、無表示は『条件を把握していない』であって『制約が無い』ではない」と書く。`sources[].license` が不明をフィールドごと省略して表す（空文字列で表さない）のと同じ線引きを、提示側でも保つ。

**スクリプト委譲が不要な Skills**（Claude Code のツールで十分）:

| Skill | 理由 |
|---|---|
| `wikicommit-fix` | Issue 読み込み → LLM 修正案生成 → wikicommit-merge 呼び出し |

SKILL.md での記述例（`wikicommit-status`）:

```markdown
## 処理フロー

1. `python .wikicommit/scripts/check_orphans.py` を実行し、孤立ページ数を取得する
2. `python .wikicommit/scripts/check_expires.py` を実行し、expires_at 期限切れページを取得する
3. `python .wikicommit/scripts/check_ingest_freshness.py` を実行し、outdated な管理ファイルを取得する
4. `.wikicommit/source/` を走査して `status: pending` の管理ファイル数を集計する
5. 結果を整形して表示する
```

---

### 11.6 wikicommit-generate の多段生成アルゴリズム

公開実装の調査（nashsu/llm_wiki・atomicstrata/llm-wiki-compiler・tuirk/Kompl 等）から、**一発生成より多段生成の方が失敗の局所化と再試行が容易**であることが明確になった。WikiCommit の ingest フローを以下の 4 パスで設計する。

#### パスフロー

各パスの入出力と分岐の全体像。パスの区切り自体は SKILL.md の内部構造であり、ユーザー向け出力に露出させない（§11.8）。

```
/wikicommit-generate <path|url>
  ↓ add_source.py … ソース種別判定・hash 計算・管理ファイルの新規作成 / 更新
pending / outdated な .wikicommit/source/**/*.md を 1 件ずつ順次処理

[Pass 1] テキスト抽出
  ├─ type: url/wikicommit → ガードB check_extraction_quality.py check-domain
  │    （既知 JS-shell ドメイン）── 一致 ──→ status: failed（抽出を試みない）
  ├─ 拡張子別ルーティング（pdf/docx/pptx/xlsx は公式 Skill 優先、
  │    未インストール時は markitdown へ自動フォールバック。
  │    URL は add_source.py --fetch-url が独自 UA 付きで markitdown API を呼ぶ）
  ├─ 抽出結果が空 / 読み取り不能 ──────────→ status: failed
  └─ ガードA check-density（低情報密度）───→ status: failed
  ↓ extracted_tokens を管理ファイルに書き込み

[Pass 2a] サマリ作成
  ├─ summary（primary_lang で記述。## Summary に上書き）
  ├─ ソース言語と primary_lang の不一致を検出（情報提供のみ・挙動は変わらない）
  └─ source-as-entity 判定 … ソース文書自身も独立した「作品」ならエンティティ候補に追加

[Pass 2b] 型の要否判断（ソース 1 件につき 1 回）
  │  check_schema_org_type.py --list-type-names（約 933 型の名前）と照合し、
  │  絞った候補の説明文だけを --describe で引いて（Issue #798）、
  │  installed schema/ の外に明確に良い適合先があるか判断（ゼロ件が通常の結果）
  ├─ 対話実行   → Enter ベース承認 [y/N]（既定 N）
  └─ 非対話実行 → さらに厳格な閾値を適用 → 通過分のみプロンプトなしで自動承認
  ↓ 承認分のみ .wikicommit/schema/<Type>.md を新規作成（追加のみ・既存は編集不可）
    却下分はどこにも永続化しない（この実行の Completion Notice にのみ列挙）

[Pass 2c] エンティティ抽出（LLM → 分析 JSON）
  │  2b で追加された型を含めて .wikicommit/schema/ を再走査してから実行
  ├─ action: create / update ──→ Pass 3 へ（update は既存ページも文脈に渡す）
  ├─ action: ambiguous ───────→ スキップ・型の確定をユーザーに要求
  └─ action: exclude ─────────→ スキップ（theme 不一致・確認なしで自動）

[Pass 3] ページ生成（LLM → ---FILE: path--- / ---END FILE--- 境界プロトコル）
  ↓
[Pass 4] ソース整合性レビュー（レビューサブエージェント）
  ├─ PASS ─→ ローカルに書き出し → 管理ファイルの status / generated_pages を更新
  └─ FAIL ─→ issues[].instruction を渡して Pass 3 を再実行（最大 max_retries 回）
       └─ 上限超過 → failed_pages に記録し、そのページは書き出さない
  ↺ 次の管理ファイルへ（Pass 1 に戻る）

全ソース処理後に 1 回だけ実行
  rebuild_index.py            … 全 Type ディレクトリの index.md を引数なしで再構築
  reconcile_ingest_status.py  … pending のまま取り残された管理ファイルを generated に是正
  Completion Notice           … ambiguous / exclude / 新規追加した型 / 却下した型 /
                                 failed_pages / 言語不一致 / source-entity ページを列挙
  ↓
/wikicommit-merge へ（Git 操作はここから。generate 自体は Git に一切触れない）
```

#### コンテキスト予算 — 固定 51K と、5 件ガードの二重の役割（Issue #796・#798）

`/wikicommit-generate` は**ソースを 1 件も読む前に**メイン文脈へ固定のオーバーヘッドを積む。2026-09-09 実測（Issue #798 の 2 段階化を反映）:

| メイン文脈に積まれるもの | 実測 | 概算トークン |
|---|---|---|
| `wikicommit-generate/SKILL.md` 全文（Skill 起動のたびに全文が載る。§11.9） | 191,168 B | 約 47K |
| Schema.org 型名一覧（`check_schema_org_type.py --list-type-names`。1 実行 1 回） | 13,441 B | 約 3.4K |
| **固定小計** | | **約 51K** |
| 抽出テキスト全文（パス 2a・ソースごと） | 40,442 B/件（日本語 Wikipedia 記事 1 本の実測） | 約 10K × 件数 |
| 生成ページ本文（パス 3 がパス 4 のために保持） | ページ数ぶん | 累積 |

**固定分の 92% は SKILL.md である。** かつては型一覧が 44%（147,421 B・約 37K トークン）を占めていたが、Issue #798 が 2 段階化して 13,441 B へ落とした — あの一覧が果たしていたのは**想起**であって存在保証ではなく（実在は候補承認後の `--type` が決定論的に確かめる）、想起には誰も検討していない 928 型の説明文が要らないためである。残る削減対象は SKILL.md 自身（進行的開示・サブエージェント化）であり、着手未定。

**5 件ガードは 2 つの役割を同時に果たしている。** Issue #567 がパス 1 に置いた「1 回の収集が 5 件を超えたら人間に確認する」というガードは、**1 回の処理量を人間が制御する**ために設けられたものだが、結果として**コンテキスト予算も律速している** — 上の表の可変分（1 件あたり約 15K）に掛かる係数がその件数だからである。

このことを明記しておかないと、**将来ガードを緩める判断がコンテキスト側の帰結を見落とす**。5 件を 10 件にする変更は「1 回の処理量が増える」だけに見えるが、実際には必要コンテキストが約 51K + 75K から約 51K + 150K へ動く。

**Issue #798 以降、200K 環境でも 5 件が通る。** Claude Code の Opus 既定は 200K であり（2026-09 時点。Sonnet 5 / Fable はネイティブ 1M、Opus は `[1m]` サフィックスで 1M。プラン依存）、5 件処理は約 126K（63%）で収まる — 2 段階化前は約 154K（77%）に達して auto-compact 圏内に入っていた。**したがって 200K の上限が 5 件ガード自身の上限を下回る状態は解消しており、ガードの答え（「全件」か「先頭 5 件」か）とコンテキストの許容量が初めて一致する。**

**それでも compaction の壊れ方は変わらない**ので、上限を超える運用は引き続き避ける。compaction 後に再添付されるのは**各 Skill の先頭 5,000 トークンだけ**であり、`wikicommit-generate/SKILL.md` ではおよそ 105〜117 行目（3.5〜4 バイト/トークン換算）まで — Step 0 までしか残らず、パス 1〜4 と Completion Notice は全部その外側にある。**エージェントは残りの手順を持たないまま実行を続け、出力は一見正常に見える。**

Issue #797 の checkpoint はこの状態を間接的に可視化する（打点の欠落として現れる）が、**同 Issue 自身が「分割前は Pass 2 以降の打点指示も同じ 5,000 トークンの外側にある」という非対称を既知の限界として記録している** — つまり compaction が起きた実行では打点指示ごと落ちうるため、検出は保証されない。

利用者向けの式・推奨件数・公式ドキュメントへのリンクは `README.md` / `README_ja.md` の Requirements → Context window が正本である（`CLAUDE.md` は公開スナップショットに含まれないため、公開側だけを読む利用者に届く場所を正本にした）。

#### パス設計

```
[パス 1] テキスト抽出
  ソースのファイル種別に応じた Skill でテキストを Markdown に変換する。
  変換結果が空または読み取り不能の場合は処理を中断し、ユーザーに案内する。
  type: url/wikicommit ソースは変換前に既知JS-shellドメインチェック（ガードB）を通す。
  変換成功後、全ソース種別で低情報密度チェック（ガードA）を通す（Issue #425。詳細後述）。

[パス 2] 分析（LLM → JSON）— 内部で 2a/2b/2c の3段階に分かれる（Issue #315）
  2a: 抽出テキスト全体からサマリを作成する
  2b: サマリを俯瞰し、installed schema/ 外の Schema.org 標準型が明確に良い適合先なら
      その場で人間の Enter ベース承認を得て .wikicommit/schema/<Type>.md を新規作成する
      （対話実行時。非対話実行時は、より厳格な閾値をクリアした候補に限り人間確認なしで
      自動承認する — Issue #507）
  2c: .wikicommit/schema/ の型リスト（2b で追加された型を含む）を LLM に渡し、
      「何をページ化するか」を JSON で返させる。実際のページ本文はここでは生成しない。

[パス 3] ページ生成（LLM → ファイル境界プロトコル）
  パス 2 の JSON の entities リストを元に Wiki ページを生成する。
  出力は ---FILE: path--- / ---END FILE--- 境界プロトコルで構造化する。
  エンティティごとの実行順序・並列化・リトライ戦略はエージェントに委ねる。

[パス 4] ソース整合性レビュー（レビューサブエージェント）
  生成ページの各主張をソース元文書と照合する。
  FAIL のページは再生成（最大 max_retries 回。DesignDoc-data.md §4.6 形式の issues[].instruction を
  再生成プロンプトに明示的に渡す。Issue #452）または failed_pages に記録して書き出しをスキップする。
```

> **Pass 4 の FAIL 後処理の可視性・フィードバック配線を修正（Issue #452）**: `action: update` のエンティティが `max_retries` 超過で FAIL した場合、従来は管理ファイルの `failed_pages`/`## Failure Reason` にのみ記録され、ページ本体・Completion Notice のいずれからも見えなかった（`ai-driven-dev-wiki` パイロットで実際に発生 — 既存ページが古いまま無期限に取り残された）。加えて Pass 4 手順4は "regenerate the page" としか書いておらず、レビューサブエージェントの判定（`docs/DesignDoc-data.md` §4.6 のエージェント間 JSON、`issues[].instruction` が本来の修正指示）が次の再生成プロンプトに配線されていなかった。本 Issue で (1) Pass 4 手順1がサブエージェントに §4.6 形式での返却を明示的に要求し、(2) 手順4がその `issues` をPass 3 再生成プロンプトへ明示的に渡すよう変更し、(3) `failed_pages` が1件以上ある管理ファイルを Completion Notice で個別列挙する（`ambiguous`/`exclude`/新規schema追加/primary_lang不一致と同じ扱いに揃える）よう変更した。あわせて `wikicommit-merge` SKILL.md に新規 Step 9（Generate Generation-Failure Tracking Issues）を追加し、`.wikicommit/source/` 配下で `failed_pages` が空でない管理ファイルを専用ラベル（`wikicommit-generation-failure`）でレビューIssue化する仕組みを、既存のレビュー追跡Issue（Step 8、Issue #313）と同じ全件走査・マーカー埋め込みパターンで拡張した（詳細は `docs/DesignDoc-pipeline.md` §6.2 該当箇所、`.claude/skills/wikicommit-merge/SKILL.md` Step 9 参照）。

<!-- -->

> **#429/#430/#442 適用後も残っていた3パターンに対応（Issue #451）**: `ai-driven-dev-wiki` パイロットで、Issue #429（帰属精度）・#430（単一ベンダー偏重）・#442（証拠拘束）の3件がすべてマージ済みの状態で生成した新規リポジトリに対し、別LLM（ChatGPT）によるレビューで、既存3件のいずれの検証観点にも正確には一致しない不正確さが3件見つかった: (1) 本文中の具体的事実（公開日）が誤っており、しかもその事実を裏付けるはずの文書自体が `sources` に含まれていなかった — Pass 4 手順1の「key claims」というくくりが本文中の個別の日付・固有名詞的事実まで一貫して検証しきれていなかった、(2) 「用語を命名した」ことと「手法自体を発明した」ことの混同 — `sources` は揃っており #442 が想定する証拠欠如ケースではなく、#429 の帰属チェック（誰の言葉かの取り違え）とも異なる第三のパターン、(3) 複数の具体的実装（GitHub Spec Kit・Red Hat・Junie・Kiro・OpenSpec等）が同一の広い概念を異なる形で体現している場合に、そのうち1つ（最も詳細だったもの）を無条件に一般定義として先出ししていた — 帰属自体は明示されているため #429 の「無帰属の単一ソース定式化」には該当せず、対象が「ベンダー」ではなく「特定の実装パターン」である点で #430 とも異なる。対応として (1) Pass 4 手順1に「granular fact verification」（個別の具体的事実の逐一検証・`sources` に実在しない引用文書の `MISSING_SOURCE` 判定）を追加、(2) Pass 3・Pass 4 手順1の両方に「naming vs. inventing」チェックを追加（#429 の帰属チェックが「誰の言葉か」を検証するのに対し、こちらは「命名」と「発明」という行為の種類の取り違えを検証する別軸）、(3) `DefinedTerm.md`（配布テンプレート・このリポジトリ自身の `.wikicommit/schema/` 双方）の `granularity` と Pass 3 に「複数の具体的実装の代表性」ルールを追加（#430 の主定義選定＝起源の軸とは独立した、公平な提示順序の軸）。3件とも Pass 4 の既存の番号付きチェックリスト項目を増やさず、既存項目（Pass 4 手順1・Pass 3 の該当箇所）に太字見出し付き段落として追記する形で実装した — `wikicommit-generate` SKILL.md 内・`wikicommit-merge` SKILL.md（Issue #452 参照）双方から Pass 4 の各手順番号への相互参照が複数箇所に存在するため、新規の番号付き手順を挿入して既存の参照を破壊しない設計判断。

<!-- -->

> **孫引き出典（secondary citation）パターンが #451 導入後も再発（Issue #473）**: `ai-driven-dev-wiki`（round2）を別セッションエージェントがレビューしたところ、`en/Person/simon-willison.md`（および ja 翻訳）が「2025年3月19日の投稿」への言及・引用を含む一方、その3月19日記事自体は当該ページの `sources` に含まれていなかった（`sources` には5月1日の記事のみが記載されていた）。Issue #451 の granular fact verification・MISSING_SOURCE チェック（Pass 4 手順1）はまさにこの種の不整合を防ぐ目的で追加されたものだが、再発した。原因は検証観点自体の欠如ではなく、既存の MISSING_SOURCE チェックが「ページが引用する具体的な文書が `sources` に実在するか」を問う設計であるところ、レビューサブエージェントが「現在の `sources`（5月1日の記事）がその3月19日記事について言及している」ことを以て実質的な裏付けありと誤って判定しうる余地が残っていた点にある — 現在の `sources` がある文書に言及していることと、その言及されている文書自体が `sources` として個別に取り込まれていることは別の事実であり、後者のみが MISSING_SOURCE 判定における「実在」の基準であるべきだった。対応として (1) Pass 3 に「Secondary citation discipline」を追加し、現在のソースが言及するに留まる別文書（孫引き元）の日付・タイトル等の個別詳細をページ本文の確定事実として書かないよう明文化し、(2) Pass 4 手順1の MISSING_SOURCE チェックに「Secondary citation dates/titles」を追加し、「現在のソースがその文書に言及している」ことは MISSING_SOURCE 判定における十分条件にならないと明示した。実際の生成トレース（Pass 2/3 の LLM 出力ログ）の再現・実 LLM による再生成検証は本 Issue の対応範囲では実施していない（Issue 本文の完了条件のうち、指示文補強〈上記〉のみを実施し、生成過程の再現・再発防止の実地確認は当該環境での live 実行を要するため後続の課題として残す）。

<!-- -->

> **Pass 4完了後もソース管理ファイルのstatus/generated_pagesが書き戻されないケース（Issue #474）**: `ai-driven-dev-wiki`（round2）の別セッションレビューで、実際にページ生成に使われた8件のソース管理ファイル（GitHub Copilot関連4件・OpenAI Codex関連2件・Spec Kit PDF・arXiv論文1件）が `status: pending`・`generated_pages: []`・`## Summary` なしのまま放置されていることが判明した。該当ソースのhashは公開済みページの `sources` に実際に使われており内容自体は正確だが、`wikicommit-status` 等で監査すると「未処理」に見えてしまう。Issue #406（index.md更新のスクリプト委譲）・Issue #452（failed_pagesの可視性配線）と同じ「長い多段生成の末尾でLLMが特定ファイルへの書き戻しを失念する」系統の不具合と位置づけた。
>
> 当初は2段構えのSKILL.md instruction（Pass 4手順7に他ファイルの`status`/`generated_pages`も対象に含める「Batch-wide scope」を追加し、それでも取りこぼした場合の安全網として全ソース処理後にgrepベースの「Ingest Status Reconciliation Safety Net」を新設）で対応したが、`/code-review --fix`（PR #481）の多角的レビューで、この instruction ベースの設計自体に複数の実害あるバグが指摘された: 最も重大だったのは、`check_ingest_freshness.py` が `status: outdated` に遷移させる際に `source.hash` を意図的に**変更しない**（前回生成時点の参照点として保持する）ため、grep一致は「ページが最新化された証拠」ではなく「ソース変更前に生成済みだった証拠」でしかなく、outdatedファイルを安全網の対象に含めると再処理が必要という正しいシグナルを誤って握りつぶしてしまう、という設計上の欠陥だった。加えて「Batch-wide scope」は現在処理中のソースの無関係な他エンティティの成否を、別ファイルの`status`（`## Failure Reason`の記述内容まで含む）に取り違えて適用しうる交差汚染のリスクがあり、grepベースの安全網も `type: url` の未フェッチソース（`source.hash: ""`）に対して事実上ワイルドカード一致してしまう欠陥があった。
>
> これらはいずれも「一部の状態（`status: pending`のみ・`generated`という単一の結果のみ）に限定すれば完全に決定論的に判定できる操作を、instructionとして表現したことで非決定論的な失敗モードを持ち込んでしまった」という共通の原因に帰着したため、最終的に `.wikicommit/scripts/reconcile_ingest_status.py`（`rebuild_index.py` と同型のスクリプト委譲）に切り出した。このスクリプトは `status: pending` の管理ファイルのみを対象とし（`outdated` は明示的に対象外とし、前述の staleness マスキングを構造的に防ぐ）、`source.hash` が空の場合はスキップし（ワイルドカード一致を防ぐ）、一致した場合は常に `status: generated` のみを設定する（`partial`/`excluded`/`failed` はPass 2/4のエンティティ単位の結果が必要でその場限りの情報のため遡って推定しない）。当初「この照合はディスク上の情報だけから全ステータス値を一意に再構築できる決定論的操作ではない」という理由でスクリプト化を見送っていたが、実際にスクリプトが担う範囲（`status: pending` → `generated` の単一値のみ）はその限界の外にあり、`rebuild_index.py`（Issue #406）と同種の完全に決定論的な操作だったと判明した。`.claude/skills/wikicommit-generate/SKILL.md` Pass 4 手順7は元の単一ファイルスコープに戻し、他ファイルの反映は全てこのスクリプトに一本化している。#473 と同様、実際の生成過程の再現・複数ソース統合ケースでの再生成検証は本 Issue の対応範囲では実施していない。

<!-- -->

> **再生成モード（`--regenerate`）はパス 2 を実行しない（Issue #578）**: 既に生成済みのページを現在のスキーマテンプレート・生成ルールで作り直す場合、対象ページの frontmatter が `type`・`title`・slug・`lang` をすべて持っているため、「何をページ化するか」は既に確定しており、パス 2 が決めることが残っていない。パス 2b（動的型追加）も走らせない — 再生成は既存ページの型を前提とする操作であり、型自体の妥当性を問い直す操作ではない。したがってパス構成は `パス 1（再取得）→ パス 3（生成）→ パス 4（レビュー）` になる。パス 1 の再取得は `sources` の全件を対象とするが、`status: retracted` のソースだけは取得せず落とす（Issue #744。`docs/DesignDoc-pipeline.md` §6.1）。
>
> ソース起点（ソース管理ファイルを再処理する）ではなく**ページ起点**を採ったのは粒度のため: 1 つのソースが複数の型のページを生成している場合、ソース起点の再処理は無関係な型のページまで巻き込む。Wiki ページは `sources:` に自身の出自（`path`/`url` + `hash`）を全件持っているため、ページを起点にそのページの `sources` を再取得してそのページだけを作り直せる（複数ソースからマージされたページも `sources` に全件並んでいるため成立する）。
>
> 新規 Skill にせず `wikicommit-generate` のオプションにしたのは、パス 1 / パス 3 / パス 4 を通常の生成とそのまま共有するため — 独立した Skill にすると指示が大量に重複する一方、実際の差分は「パス 2 を飛ばす」「`review_status` を `pending` に戻す」「対象の指定方法（引数が**ソースではなくページ**を指す）」の 3 点に限られる。引数の意味が同じ位置で変わる点は、`--regenerate` があるかどうかで判別し、かつ引数が `.wikicommit/entity/` 配下に解決しない場合はエラーで停止する（パスの形から意図を推測しない — 打ち間違えたソースパスが「成功に見える no-op」になるのを防ぐため）。
>
> 対象の選別・件数ガード・キャッシュ利用・ハッシュ不一致時の扱い・ソース管理ファイルへの書き戻しの要否（いずれも Issue #578 の「検討事項」として実装時に決めた項目）は `docs/DesignDoc-pipeline.md` §6.1 の「再生成モード」節を参照。

#### パス 2: 分析 JSON 形式

```json
{
  "summary": "本文書は CompanyA の技術ブログ記事。山田太郎氏の紹介と Project Alpha の概要を含む。なお「雑談先のXX社」への言及はテーマ（社内技術ナレッジ）と無関係のため除外した。",
  "entities": [
    {
      "type": "schema:Person",
      "title": "山田太郎",
      "slug": "yamada-taro",
      "lang": "ja",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": null
    },
    {
      "type": "schema:Organization",
      "title": "CompanyA",
      "slug": "companya",
      "lang": "ja",
      "action": "update",
      "existing_path": ".wikicommit/entity/ja/Organization/companya.md",
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": null
    },
    {
      "type": "schema:Organization",
      "title": "雑談先のXX社",
      "slug": "xx-company",
      "lang": "ja",
      "action": "exclude",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "exclude_reason": "theme_mismatch",
      "exclude_note": "個人的な取引先であり社内技術ナレッジのテーマと無関係"
    },
    {
      "type": "schema:Person",
      "title": "鈴木花子",
      "slug": "suzuki-hanako",
      "lang": "ja",
      "action": "exclude",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "exclude_reason": "privacy",
      "exclude_note": "ソースに名前が出る審議会委員。非公人であり entity-policy.md の方針に該当"
    },
    {
      "type": "schema:DefinedTerm",
      "title": "キリマンジャロコーヒー",
      "slug": "kilimanjaro-coffee",
      "lang": "ja",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": "産地の標高（1,600〜2,000m）の記載があったが DefinedTerm.md の recommended フィールドに受け皿がないため本文にのみ記載"
    },
    {
      "type": "schema:Organization",
      "title": "スターバックス",
      "slug": "starbucks",
      "lang": "ja",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": null,
      "coverage_gap_note": null
    },
    {
      "type": "schema:GovernmentService",
      "title": "児童手当",
      "slug": "child-allowance",
      "lang": "ja",
      "action": "create",
      "existing_path": null,
      "ambiguous": false,
      "alternatives": [],
      "expires_at": "2026-07-01",
      "coverage_gap_note": null
    }
  ]
}
```

- `summary` はソース全体の 2〜3 文要約（`config.yml` の `theme` が空でも常に生成する）。ソース管理ファイル body の `## Summary` に書き込まれる（§4.3・`DesignDoc-data.md`）。言語は `primary_lang` とする（Issue #314 — 従来この指定がなかったため、`summary` 自体は結果的に `primary_lang` で書かれる一方、`exclude_note`/`coverage_gap_note` にはエージェントのセッション言語が漏れ込み、同一 `## Summary` 内で言語が混在する不具合が実際に発生した）。`## Summary` に反映される付記フィールド（`exclude_note`・`coverage_gap_note`）はすべてこの `summary` と同じ言語（＝ `primary_lang`）で統一する。**見出しラベル自体（`## Summary`・`## User Notes`）は本文の言語（`primary_lang`）に関わらず常に固定の英語**（Issue #405 — `primary_lang: en` パイロットで本文は正しく英語なのに見出しラベルだけ `## サマリ`/`## ユーザーメモ` と日本語固定になっていたことが判明。ソース管理ファイルは内部管理ファイルでありローカライズ対象外という判断。詳細は `docs/DesignDoc-data.md` §4.3）
- `lang` はパス 2 実行前に `.wikicommit/config.yml` の `primary_lang` を読んで全エンティティに設定する。**この設定はソース文書自体の言語に関わらず常に行われる**（意図的な既存設計）——`primary_lang: ja` のリポジトリに英語ソースを ingest しても、生成されるページの `lang` は `en` にはならず `ja` になる（内容は要約・翻訳された上で統合される）。この暗黙の挙動に気づかないまま運用が進むと、例えば翻訳品質を実在する外国語原文と突き合わせて検証するような用途で、比較対象のはずのページ自体が既にその原文を読んで書かれてしまっており検証が無効化される、といった問題が起こりうる（`Paperwork-Navigator-wikicommit-pilot` で実際に発生。Issue #336）。この問題自体（`lang` を `primary_lang` に固定する仕様）を変更する対応ではなく、Pass 2a がソース言語と `primary_lang` の明らかな不一致を検出した場合に Completion Notice で一言注記する形で可視化する（`.claude/skills/wikicommit-generate/SKILL.md` Pass 2a・Completion Notice 参照）
- `action: update` かつ `existing_path` がある場合は、既存ページを LLM コンテキストに追加してから生成する（既存情報を失わず新情報を統合）
- `ambiguous: true` のエンティティはページ生成をスキップし、コンソールに記録してユーザーに型の確定を求める
- `action: exclude`（Phase 2〜）はページ化しないと判断したエンティティ。`exclude_reason` は現状 **`theme_mismatch` / `privacy` の 2 値**（Issue #667）で、`exclude_note`（除外理由の説明文。`## Summary` に反映される。`summary` と同じ言語＝ `primary_lang` で書く。Issue #314）を伴う。いずれも人間の確認なしに自動でページ生成をスキップする。2 つは互いの変種ではなく独立した別軸の理由であり、判定も別々に行う:
  - `theme_mismatch`: `config.yml` の `theme` に照らして無関係（**関連性**の軸）。`theme` が空文字列の場合、LLM に**この判定だけを**行わせない（off-subject を理由とする除外が消えるだけで、`exclude` 全体を禁じるのではない — 下の `privacy` は別軸として引き続き効く。`/wikicommit-init` の既定は空の `theme` であり、ここで `exclude` 自体を禁じると entity-policy を設定した Wiki で許容性の判定が丸ごと黙って無効化される）
  - `privacy`: `.wikicommit/entity-policy.md` が書いてよくないと定めたもの（**許容性**の軸。`exclude_living_persons` スイッチと散文本文の両方が入力になる。`docs/DesignDoc-data.md` §3.5）。ファイルが無い・スイッチ off・散文が空のいずれでもこの判定自体を行わせない。**両方の理由が同じエンティティに当てはまる場合は `privacy` を記録する** — Wiki の主題が変わっても残る側の理由であるため

  `copyright` は **enum に加えず予約のまま据え置く**（Issue #667）。ソース側で保護期間・ライセンスを確認して取り込む設計になっている以上、エンティティ単位で「著作権を理由にページを作らない」と判断する場面がほとんど残らず、消費者を得ないまま並べると Issue #553 が `inDefinedTermSet` について指摘した「受け皿だけ存在して常に空のまま残る」形になる
- `slug` は言語中立な英語識別子とする（CLAUDE.md の WikiLink 節）ため、日本語発音の音写ではなく以下の優先順位で決定する（Issue #193）:
  1. 普通名詞・概念語 → 英訳した slug にする（例: `キリマンジャロコーヒー` → `kilimanjaro-coffee`。`kirimanjaro-koohii` のような音写は不可）
  2. 固有名詞（人名・組織名・地名等）で英語圏に確立された原綴りがあるもの → その原綴りを使う（例: `スターバックス` → `starbucks`。`sutaabakkusu` は不可）
  3. 上記いずれにも該当しない固有名詞 → ローマ字表記でよい（例: `山田太郎` → `yamada-taro`）
- `expires_at` はソース本文が明示的な期限（申請締切・有効期限・年度区切り等）を述べている場合のみ `YYYY-MM-DD` を設定する。それ以外は `null`（Issue #279 — Pass 2 がこの候補を出力しないために `expires_at` frontmatter が実運用でほぼ使われない状態になっていた）。日付を推測・逆算しない。複数の期限が併記されている場合（最後の `schema:GovernmentService` の例のように支給時期ごとに締切が異なる等）は、そのうち最も早い日付を採用する — この値は再チェックを促すためのフィールドであり、遅すぎるより早すぎる方が安全という判断（詳細は日付選定を含め `.claude/skills/wikicommit-generate/SKILL.md` Pass 2 のルール一覧を参照）。Pass 3 はこの値を非 null のときのみページの `expires_at` frontmatter に書き込み、`null` のときは既存ページの `expires_at`（あれば）を変更しない。Pass 4（ソース整合性レビュー）は `expires_at` も他の主張と同様にソースとの照合対象に含める。
- `coverage_gap_note`（Issue #284）は、そのエンティティの型スキーマファイルの `properties:` ブロック（Issue #495）に受け皿がないドメイン固有の具体的な属性（対象年齢・道具・管轄自治体等）がソース本文に含まれていた場合のみ、単一の文字列として設定する（`exclude_note` と同じく配列にしない。1エンティティで複数の属性が不足していても1文にまとめる）。`create`/`update` エンティティのみが対象で、`exclude`/`ambiguous` エンティティには設定しない。何も不足がなければ `null`（通常はこちらが大半を占める想定）。1件以上存在する場合、`summary` と同じタイミングで管理ファイルの `## Summary` に追記される（エンティティごとに1文）。`summary` と同じ言語（＝ `primary_lang`）で書く（Issue #314）。スキーマファイル（`.wikicommit/schema/`）への書き込みは一切行わない — 本フィールドは証拠収集のみを目的とし、ページ本文には従来通りその情報を書く（`## Summary` の記載場所自体は `docs/DesignDoc-data.md` §4.3 の ソース管理ファイルフォーマット参照）。
- 最後の `schema:GovernmentService` の例は、Pass 2b（下記）でこのソース向けに承認・新規作成された型を Pass 2c がそのまま使ってエンティティを生成した結果を示す。このエンティティが指すのは制度そのもの（対象者・支給額・支給時期）であり、**申請の手順は別の主題**である — 同じソースが手順も述べているなら、それは別の型の 2 つ目のエンティティになる（Issue #569。`docs/DesignDoc-data.md` §5.4・本節 Pass 2c の該当ルール）。この例を「1 ページに対して `GovernmentService` が正解で `HowTo` が不正解」と読まないこと。`better_type_candidate`/`better_type_rationale`（Issue #285 が導入したフィールド）はこの変更（Issue #315）で不要になったため削除した — 詳細は下記「Pass 2b: 型の要否判断」を参照。

> **レビュー規律は SKILL.md ではなく `.wikicommit/review-rules.md` にある（Issue #752）**: パス 4 の「何を検査するか」は、以前は `wikicommit-generate` Pass 4・`wikicommit-review` Step 4 手順 3・`wikicommit-synthesize` Step 5.5 の 3 箇所に書かれていた（実測 27KB ≒ 6,800 トークン）。**3 箇所は既に食い違っており**、Pass 4 だけが持つ検査（ソース間の食い違い・1 ホップのページ間矛盾・命名 vs 発明・孫引き出典）は `wikicommit-review` に無く、逆に `wikicommit-review` だけがモデルの自己申告と `generated_by` の突き合わせを持っていた — どちらが正しいかは誰も決めていなかった。
>
> Issue #552 の「共通化しない」決定と矛盾しない。あの決定の論拠は「**短い文面**を各自が持つ方が総コストで優る」であり、27KB は短くない。同じ判断基準を当てはめ直した結果である。
>
> **移したのは「何を検査するか」だけで、段取りは各 Skill に残る** — Pass 4 の step 4〜8（リトライ・`failed_pages`・書き出し・`reset_review_on_content_change.py`・`status` 更新）・`wikicommit-review` Step 5・`wikicommit-synthesize` の grounding set 構築は動いていない。`tests/test_review_rules_single_source.py` が両方向を CI で固定する（規律が SKILL.md に書き戻されていないこと・段取りが Skill から消えていないこと）。
>
> **両側から守る**。ルールファイル（受け手側）は「証拠として扱ってよいのは `SOURCE` と印されたブロックのみ」と定め、SKILL.md（渡し手側）は「サブエージェントに渡すのはページ・抽出テキスト**全文**・1 ホップ先の 3 つに限る」と定める。プロンプトを組み立てるのは Pass 3 でそのページを**自分で書いたエージェント**であり、そのコンテキストには渡すべきでないもの（Pass 2a の `summary`・Pass 2c の分析 JSON・前ラウンドの判定）が揃っている。**証拠拘束ルール（Issue #442）はこれを止められない** — あれが禁じているのは「自分の**世界知識**で判定すること」であり、`summary` は世界知識ではないのでこのルールをすり抜ける。それでいて literal source text でもない。要約に対する照合は、ソースに対する照合ではない。
>
> **`rules_version` の echo 検証**: SKILL.md は機構として全文がコンテキストに載るが、別ファイルはエージェントが Read を選ぶ必要がある。読まなければレビューは「ページをソースと照合する」だけに落ち、**しかも出力は正常に見える**。ルールファイルの frontmatter に `rules_version` を置き、サブエージェントが返す JSON にそれを含めることを必須にして orchestrator が照合する。欠落・不一致なら 1 度だけ起動し直し、それでも駄目なら**処理全体を停止して報告する**（`generate.max_retries` を消費させない・`failed_pages` に落とさない。Issue #574 のガード C と同じ扱い — 環境・指示の問題であってページの欠陥ではなく、ページ側に記録すると誤った記録が残る〈Issue #567〉）。`wikicommit-review` はサブエージェントを使わないため echo 検証が効かず、この限界はルールファイルと SKILL.md の両方に明記してある（Issue #752 検討事項 4）。
>
> **ファイルが無い既存リポジトリは処理を停止する**（同 検討事項 1 の (b)）。`.wikicommit/review-rules.md` は `_root_outputs.py` に `update: overwrite` で登録されており再 init で配布されるが、`npx skills add` で Skills だけ更新したリポジトリには無い。SKILL.md に最小限の規律を残す案 (a) は、まさに解消したはずの「2 箇所に同じ規律がある」状態を作り直すため採らない。**Issue #750 以降、fail-open は明確に悪化している** — 黙って劣化したレビューが、レビューが行われたと主張する記録まで書くことになる。停止時は `/wikicommit-init --no-overwrite` を案内する。
>
> **`update: overwrite` は意図的で、`*-policy.md` 2 つとは逆である**。あちらは人間が書くファイル（Issue #564 / #667）で `review`。こちらは WikiCommit の規律であり、編集可能にすると Wiki が自分のレビューを黙って弱められる。`review-policy.md` という名前を採らなかったのも同じ理由で、`*-policy.md` という接尾辞は「ここに自分の方針を書いてよい」という誤ったシグナルになる。

#### パス 2b: 型の要否判断（Issue #315）

パス 2a（サマリ作成）とパス 2c（エンティティ抽出）の間に挟まる、ソース1件につき1回だけ実行するステップ。旧方式（Issue #285 の `better_type_candidate`/`better_type_rationale`）は「`installed schema/` 内の型より明確に良い適合先がある」という判断を分析 JSON のフィールドとして記録するだけで、実際の型追加は別セッションで `wikicommit-schema-propose` を実行して初めて反映される設計だった。この間接性が実害を生んだ: `llm-agent-research-wiki` パイロットで、`/wikicommit-generate` の Completion Notice が報告した `better_type_candidate` を後から拾おうとしたところ、`wikicommit-schema-propose` の検出源 `check_schema_coverage.py` は「既に `installed schema/` 内の型（この場合 `schema:DefinedTerm`）で生成済みのページ」を検出対象にできず、情報が構造的に失われた（詳細は `Issues/registered/p3-112-schema-type-selection-inline-proposal.md`（非公開の開発リポジトリ側の記録））。

Pass 2b はこれを「その場で解決する」設計に変更する:

1. パス 2a のサマリと、`check_schema_org_type.py --list-type-names`（1 実行 1 回プリロードする約 933 型の**名前**の一覧。絞った候補の説明文は `--describe` で引く。Issue #798）を基に、`installed schema/` 外の Schema.org 標準型がこのソースの内容に明確に良く適合するか判断する（`installed schema/` に既にあるファイルは候補から除外。このバッチ内で既に追加された型も除外）。ゼロ件が通常の結果であり、無理に候補を出す必要はない。
2. 候補があれば、対話実行かどうかで分岐する（Issue #507。判定方法自体は流用の既存の自己申告ロジック）: 対話実行なら `wikicommit-init` の theme 駆動提案（Issue #286。Issue #404 で `wikicommit-init` 側は廃止済み）と同じ Enter ベース UX で人間に個別確認する（デフォルト N）。非対話実行（サブエージェント経由等）なら、Enter プロンプト自体を表示せず、`wikicommit-init`（Issue #490）・`wikicommit-collect`（Issue #489）と同じ「実ソース内容から明確に断定できる場合のみ」というこの手順の閾値よりさらに厳格な閾値をその候補に追加適用し、クリアした候補のみデフォルト **Y** としてプロンプトなしで承認する（クリアしない候補は却下）。
3. 承認された型（対話承認・非対話自動承認のいずれも）は `check_schema_org_type.py --type <Type> --property <Prop1> ...` で `recommended` プロパティ候補を検証した上で、`.wikicommit/schema/<Type>.md` を標準型フォーマット（§5.2・`DesignDoc-data.md`）でその場でローカルに新規作成する。`wikicommit-generate` の「Git 操作なし・schema/ 不可侵」契約に対する、旧 `wikicommit-init` theme 駆動提案（Issue #286）と同じ「追加のみ可・既存ファイル編集不可」の narrow exception。PR は経由しない — 通常の `.wikicommit/entity/`・`.wikicommit/source/` の変更と同じバッチとして `wikicommit-merge` が後で拾う（`.claude/skills/wikicommit-merge/SKILL.md` Step 2 item 4・Step 5）。非対話自動承認された型にschemaファイル自体への特別なマーカーは残さない（Issue #507。Completion Noticeにのみ明記する）。
4. 却下・候補なしの型はどこにも永続化しない（意図的 — 間接的な警告機構自体が今回の問題の根源だったため）。事後の救済は `wikicommit-schema-propose`（下記・変わらず存続）の役目とする。

パス 2c は、パス 2b で追加された型を含めて `.wikicommit/schema/` を再走査してから実行する。

> **固有名詞エンティティに対する閾値の部分的な緩和（Issue #447）**: 上記ステップ1の閾値（「明確に良く適合する」場合のみ提案する）は意図的に保守的だが、この保守性が**十分な材料（ソース本文）がある場面でもPass 2bに新型提案を見送らせる**副作用を生んでいたことが2件のパイロットで確認された。`ai-driven-dev-wiki` パイロットでは `DefinedTerm/claude-code.md`（Claude Code というソフトウェア製品）が `schema:SoftwareApplication` ではなく `schema:DefinedTerm` として生成され、`llm-agent-research-wiki` パイロット（en 20ページ中8ページ、4割）では `DefinedTerm/gaia.md` 等のベンチマーク/データセット群が `schema:Dataset` ではなく `schema:DefinedTerm` として生成されていた。原因は `DefinedTerm.md` の `granularity`（「ドメイン固有の用語・概念」）が実質的に何にでも技術的に適用できてしまう受け皿であり、この「技術的に表現できてしまう」という事実自体が新型提案を見送る理由になっていた点にある。
>
> 対応方針として、Init時点のtheme駆動型提案（Issue #286、Issue #404で廃止済み）を復活させる案を検討したが、本Issue（#447）の文脈では不採用とした——旧仕組みは**ソースを1件も読んでいない段階**でtheme文の1〜2文だけを根拠にしており実質ほぼ発火しなかった記録が残っている一方、今回の問題は逆に**十分な材料がある状態でもPass 2bが見送った**ケースであり、問題の所在が異なる（Init側を戻しても本Issueの問題は解消しない）。なお、Init時点の型提案自体は後日 Issue #490 が別の理由（非対話バッチ実行では Pass 2b 自身の Enter 確認がデフォルト却下されてしまう問題）で、判定バーをさらに厳格化した限定的な形で復活させている（`docs/DesignDoc-data.md` §3.3）——これは本Issueが不採用としたのと同じ仕組みの単純な巻き戻しではなく、別問題への別解として独立に導入されたものである。
>
> 採用した対応は、Pass 2bのステップ2（`.claude/skills/wikicommit-generate/SKILL.md`）に「named-entity パターン」の追加ルールを設けることに限定した: 候補エンティティが抽象的な用語・概念・方法論ではなく、固有名詞を持つ具体的な対象（ソフトウェア製品・研究データセット/ベンチマーク・創作物・規格等、分野を問わない）である場合、`DefinedTerm` で技術的に表現できることは新型提案を見送る十分な理由にならないと明記した。抽象概念（例: 対応する標準型のない "vibe coding" のような方法論）に対する保守的な閾値自体は変更していない——閾値全体を緩めるのではなく、named-entity パターンに限定した部分的な緩和である。あわせて `DefinedTerm.md` の `granularity` ルールにも、DefinedTermが抽象概念の受け皿であり固有名詞を持つ具体的エンティティの第一選択ではないことを明記した（`.claude/skills/wikicommit-init/scripts/templates/schema/DefinedTerm.md`）。
>
> 既存ページ（`claude-code.md` 等）を実際に別の型へ再分類する仕組み自体は本Issueのスコープ外とした——`check_schema_coverage.py` は「`type:` 値に対応する専用スキーマファイルが存在するか」のみを判定するため、型ファイル自体は存在するが選ばれた型が内容的に誤っているケースは検出対象外という構造的な限界があり、対応には型変更＋本文再構成をPR化する新規Skill（または `wikicommit-schema-propose` の拡張）が必要になると見込まれる。実装コストの大きさから Phase 3 の OSS 公開スコープには含めず、着手フェーズ未確定の将来検討課題として [DesignDoc-phases.md](DesignDoc-phases.md) Phase 3 節に記録した。

<!-- -->

> **物語ソースの登場人物を Person ページへ昇格させる経路を定義（Issue #560）**: `wikicommit/decameron-wiki`（it/en/ja 各 174 ページ、全 100 話）で、`Person/` に存在するのは枠物語の語り手 10 人と実在・伝説上の歴史人物だけであり、各説話の主人公（Federigo degli Alberighi・Griselda・Ser Ciappelletto・Calandrino 等）は**一切 Person ページ化されず `properties.character` にプレーンテキストで列挙されるのみ**だった。当初の「実在性バイアス」仮説（実在人物のみが Person 候補に挙がる）は実データで反証されている — 同一の Wikipedia 概要記事・同一の ingest から `ShortStory/ser-ciappelletto.md` 等は生成されているのに、Ciappelletto 自身の Person ページは生まれていない。分かれ目は登場回数でも実在性でもなく、**そのソースがその人物を「単独で紹介される対象」として書いているか「ある物語のなかの誰か」として書いているか**という語り口の違いだった。
>
> 根本原因は、既存のルールが**抑制方向にしか働かない**ことにある。`ShortStory.md`/`Book.md` の `character` 行（「独立ページに値する場合のみ WikiLink」）・`Person.md` の independent-subject 判定（「付随的言及は不可」）・Pass 3 の Property-value WikiLinks（Issue #496。参照先の型のバーを満たさない付随的言及にリンクを強制しない）はいずれも「作らない」側の判断材料しか与えず、**物語ソースにおいて登場人物を昇格させる経路が一つも定義されていなかった**。`Person.md` の `granularity` が除外条件を 3 行にわたって列挙する一方、包含側は抽象的な 1 行しか持たないという非対称が、その形での現れである。
>
> **決定した線引き**は 2 本立てで、いずれも「1 作品あたり最大 1 ページ + 再登場人物」に上限が付く（対応方針 5 が懸念した「100 話 × 数人 = 数百ページ」という過剰ページ化は、「名前のある登場人物すべて」を昇格対象にした場合の話であり、この線引きは取らない）:
>
> - **軸 A（単一作品の主人公）**: その作品が**丸ごとその人物についての話である**なら、その人物は independent subject である。物語はその人物が何をし、どう置かれているかという独立した事実を述べており、それは他の Person ページに適用しているバーそのものである。架空であることは関係しない（`schema:Person` は公式に架空人物も含む。`dev/pilot-akechi-kogoro-wiki.md` で確認済み）。一方、その作品の筋書きの中で動くだけの脇役は昇格しない
> - **軸 B（作品をまたぐ再登場）**: このWikiが扱う 2 件以上の作品に登場する名前は、独立ページ候補として再評価する。再登場は単一の作品からは得られない「この人物は 1 つの筋書きを超えて存在する」という証拠である
>
> **反映先**: 軸 A は `Person.md` の `granularity`（包含側の非対称を埋める）、軸 B は `ShortStory.md`/`Book.md` の `character` 行。**Pass 2c 側に独立した指示は足していない**（対応方針 3 を採らなかった） — Pass 2c は既に「各スキーマファイルの `wikicommit.granularity` ルール」をコンテキストとして受け取るため（本節「SKILL.md への記述指針」パス 2 参照）、型テンプレートに書けばそのまま抽出判断に届く。ルールの持ち主である型の側に置く方が、同じ内容を 2 か所に持つより整合する。
>
> **軸 B は型テンプレートだけでは実行できない**点が、対応方針 4（検出スクリプト）を併せて採った理由である。Pass 2c が受け取る既存ページ情報は「タイトル + パス」であって、他の作品ページの `properties.character` の中身ではない — 再登場は 1 回の生成実行の中からは原理的に見えない。`check_recurring_characters.py`（`docs/DesignDoc-ScriptSpec.md`）が事後に横断集計し、`wikicommit-status` Step 7 が報告する。`Person` ページが既に在るのにプレーンテキストのままの値は、要求される行動（リンクにする）が `RECURRING`（ページを作る）と正反対であるため、`check_unlinked_entity_mentions.py`（Issue #561）の担当として切り分けてある。`check_property_wikilink_reinforcement.py` が Issue #523 の手動監査を自動化したのと同じ関係にある。
>
> **`akechi-kogoro-wiki` との整合**（Issue #560 の完了条件）: あちらでは脇役（予審判事・容疑者・刑事）まで含め 14 件の Person ページが成立していた。ソース構成の違いがこれを説明する — akechi は青空文庫の**各作品の全文**を ingest しており、全文は登場人物それぞれについて独立した事実（役割・行動）を十分に述べる。一方 decameron は全 100 話を 1 本の Wikipedia 概要記事で賄い、全文ソースは 8 件に留まる。概要記事のあらすじの中では、登場人物は「筋書きの中の誰か」としてしか現れない。この差は上記の「語り口」仮説と整合し、決定した線引きとも矛盾しない（全文ソースなら軸 A のバーは自然に満たされ、概要ソースでも「その話が誰についての話か」は述べられているため主人公は拾える）。ただしこれはパイロット記録からの推定であり、両リポジトリの生成トレースを突き合わせた検証ではない。
>
> **過剰ページ化を招かないことの実地確認は本 Issue の対応範囲では行っていない**（実 LLM による `decameron-wiki` 相当規模の再実行を要するため、パイロット第 2 弾での確認に回す。Issue #560 の完了条件が明示的にこれを許容している）。既存パイロットへの遡及適用も行わない。

<!-- -->

> **存命の個人については記述範囲を絞る（Issue #668）**: `Person.md` の `granularity` に、存命の個人のページはその人が自ら公表したもの（著作・発言・自称する役職）に寄せ、経歴・所属歴・生年月日といった一次資料での裏取りが要る事実はソースが述べていても書かない、というルールを追加した。**新しい仕組みではなく既存の器にそのまま載る** — 同ファイルは既に「家族関係のプロパティ（`spouse`/`children`）・身体的属性（`height`/`weight`）はソースが述べていても書かない」という同型のルールを持っており（Issue #495 が型レベル `excluded` を廃止した際に自然文へ移したもの）、今回はその判断を、誤りのコストが最も高い対象へ広げただけである。
>
> **Issue #473 が起きたのはまさにここだった** — `en/Person/simon-willison.md` が `sources` に無い記事の日付と内容を確定事実として書いていた（孫引き出典）。あの対応は Pass 3 / Pass 4 への指示補強、すなわち「書くなら裏を取れ」という規律であって、「そもそも書く量を減らす」ではない。本ルールは後者を担う。
>
> **`properties:` のキーは削っていない**。テンプレートは `affiliation` / `jobTitle` / `birthDate` を候補キーとして提示し続ける — 故人・歴史上の人物には引き続き有効であり、書かないと決めた項目は Issue #553 が Pass 3 に入れた「埋められないキーは省略する」ルールでキーごと落ちる（空文字列は残らない）。**一方、本文テンプレートの `## Background` には但し書きが要った** — 節の指示が "chronological activities, affiliations, and roles" のままでは、`granularity` と同じファイルの中で反対のことを Pass 3 に指示することになる（Issue #552 が `TechArticle.md` について記録した「同一ファイル内の矛盾」と同じ形であり、`properties:` と違って Issue #553 のような受け皿が本文側には無い）。`DefinedTerm.md` の `## When It Applies` が「他の 2 種類では丸ごと省く」と placeholder 自身に書いているのと同じ形を採った。
>
> **`.wikicommit/entity-policy.md`（Issue #689）との分担**: あちらは「そもそもページを作るか」という型をまたぐ**許容性**の判断で、`exclude_living_persons` は既定 off。こちらは「作るとして何を書くか」という型スコープの**記述範囲**で、常に効く。両方入れても重複しない — 前者が off の Wiki でも後者は働く。`granularity` の該当箇条書きがこの分担を 1 文で述べ、そのファイル名を名指しする（配布物から参照してよいのは利用者のリポジトリに実在するパスであり、`docs/`・`Issues/`・`dev/` を禁じる §11.9 の対象ではない）。
>
> **既存ページへの遡及適用は行わない**（本ドキュメント群が一貫して採る「新旧混在を許容する」方針）。既に経歴・所属歴を書いているページは `/wikicommit-fix` か `/wikicommit-generate --regenerate --type Person` が走るまで残る。どのページが対象かは `generated_with` の `grep` と `CHANGELOG.md` の記述をセットで見て人間が決める（`docs/DesignDoc-data.md` §3.3）。`Organization.md` への同種のルール（実体が個人〜数名の組織）は、型テンプレートではなく上記の許容性の側で扱う。

<!-- -->
<!-- -->

> **ソース文書自体をentity候補に含める「source entity」判断を追加（Issue #475）**: 従来のPass 2は「ソース文書内で言及されているエンティティ」のみを抽出対象とし、ソース文書自体を候補に含めなかった。`ai-driven-dev-wiki-round1` パイロットでは arXiv 論文ソースに対して `schema:ScholarlyArticle` 型の実体ページが生成されていたが、同じソースを扱った `round2` ではこれが再現されず、論文内の個別概念（`DefinedTerm` 等）のみが抽出された——ソース管理ファイルの `## Summary` には論文の要旨等の重要な情報が既に書かれているにもかかわらず、読者向けの公開Wikiには一切反映されないという非対称が生じていた。ソース文書自体が独立した識別性（著者・発行日・引用可能なタイトル）を持つ「作品」である場合、それ自体を `schema:ScholarlyArticle`・`schema:Report` 等のentityとしてページ化した方が、読者にとっての発見可能性・他ページからの引用可能性が高いと判断した。
>
> 新しい仕組みは作らず、既存のPass 2a/2b/2c/3の指示を拡張する形で実装した: (1) Pass 2aに、ソース文書自体が独立した引用可能な「作品」としての識別性（タイトル・著者・発行日・DOI/URL等）を持つかを判断する基準を追加した（該当例: arXiv論文・公式ベンダーブログの製品発表・公式レポート/whitepaper・ニュース記事。非該当例: 個人ブログの技術解説記事〈識別性が薄い〉、行政の事務手続きページ〈「作品」ではなく「情報」寄り〉）。該当すればソース文書自体が追加のentity候補としてPass 2b/2cに流れ込む——ソース内の言及エンティティの抽出を置き換えるものではない。(2) Pass 2bの型の要否判断（Issue #315の動的型追加メカニズム）にこの候補もそのまま乗せ、デフォルトschemaに `ScholarlyArticle` 等を新規追加することはしない。(3) Pass 3に、生成されたsource entityページへの自然な言及をWikiLinkとして本文に含めてよい旨を追記した——`sources:`（hash付き、監査・鮮度検証用）の役割は変更せず、2つの仕組みを混在させない設計とした。
>
> `slug`・型解決・生成順序（`existing_path` 機構）は既存ロジックをそのまま流用する。Pass 4のソース整合性レビューも当面は既存の個別事実逐一検証（Issue #451）で対応し、論文・ニュース記事等のメタデータ専用検証（DOI解決等）は本Issueのスコープ外とした。source entityページの本文がソース管理ファイルの `## Summary` と内容的に重複することは許容し、デデュープ機構は導入しない。既存パイロット（`ai-driven-dev-wiki-round1`）に既に存在する `ScholarlyArticle` ページへの遡及適用は行わない——本Issueの対象は新規生成分のみ。`title` は原則 `<primary_lang>` で書くという既存の全エンティティ共通ルール（Issue #314等）に対する狭い例外として、source entityの `title` のみは原文どおりの言語で保持する（本文・`lang` フィールドは通常通り `<primary_lang>`）——引用可能性がこの仕組みの目的である以上、タイトル自体を翻訳すると実在の作品名と一致しなくなり目的を損なうため（`/code-review --fix` によるレビューで指摘・修正。詳細は `.claude/skills/wikicommit-generate/SKILL.md` Pass 2c該当ルール参照）。

#### パス 3: ファイル境界プロトコル

nashsu/llm_wiki と同形式。LLM に以下の形式で返させる。

```
---FILE: .wikicommit/entity/ja/Person/yamada-taro.md---
---
title: "山田太郎"
type: "schema:Person"
...
---

（本文）
---END FILE---
---FILE: .wikicommit/entity/ja/Organization/companya.md---
...
---END FILE---
```

Markdown の自由文形式よりパース失敗を局所化できる。1 ファイルのパース失敗が他ファイルに波及しない。

> **値リスト内で WikiLink とプレーンテキストが割れるのは、生成時点でのページの存在有無が判断に混入したため（Issue #561）**: `wikicommit/decameron-wiki` の `Book/decameron.md` は `character` に 10 人の語り手を並べているが、WikiLink 化されているのは 8 人だけで、`Filostrato`・`Panfilo` の 2 人はプレーンテキストのまま残っていた。この 2 人のページは**実在する**。各ページの `sources` を突き合わせると分かれ目が完全に一致する — WikiLink 化された 8 人は Book ページと同じ ingest（`it.wikipedia.org/wiki/Decameron`）で生成され、残る 2 人は後の ingest（`.../Giornata_prima/Introduzione`）で生成されている。値リスト内の並び順（WikiLink 8 件のあとにプレーン 2 件）もこの説明と整合する。`wikicommit/saitama-city-wiki` の `GovernmentService` 6 ページの `provider`（WikiLink 化されたのは 1/6 のみ）でも、別リポジトリ・別 property で同じ形が再現している。
>
> **これは判断が曖昧だったのではなく、Pass 3 が名指しで禁じている基準がそのまま使われた**ケースである。同節は "Do not let \"the target page doesn't exist yet\" stop you from writing the WikiLink" と明示している。Issue #340 が参照先不在を ERROR から WARNING へ緩めたのは「まだ無い概念を WikiLink 化せず地の文で書く」という萎縮を避けるためであり、その緩和の意図が `properties:` 値については効いていなかった。Issue #523 が扱ったのは**property 間**の非対称（`author` と `publisher`）だが、こちらは**同一 property の同一値リスト内**で、RANGE 分類・型・エンティティとしての資格がすべて同じ 10 人が 8 対 2 に割れている — `check_property_wikilink_reinforcement.py` はテンプレートの `properties:` キーを見るスクリプトであり生成されたページの値は見ないため、この形は検出範囲外だった。
>
> **対応は 2 本立て**（対応方針 1 + 2）。(1) Pass 3 に**値リスト単位**のチェックポイントを追加した — 既存の指示はエンティティ単位で書かれておりリスト全体を見渡す視点が無かったため、「リスト内で WikiLink とプレーンが混在するなら、プレーン側は参照先の型の independent-subject バーを満たさないという理由でなければならない。ページの存在有無は理由にならない」を明記した。(2) `check_unlinked_entity_mentions.py`（`docs/DesignDoc-ScriptSpec.md`）を新設し `wikicommit-status` Step 8 から呼ぶ。一度書かれた値を見直す経路が無い（`action: update` はそのページ自身のソースが再 ingest された時にしか起きない）以上、事後の検出が要る。
>
> **対応方針 3（既存ページ一覧を Pass 3 のコンテキストに明示的に渡す）は採らなかった** — 「存在しないページにもリンクを書け」というルールが守られていればそもそも不要な情報であり、渡すこと自体が「存在を確認してから書く」という、まさに今回問題になった読み方を追認しかねない。**対応方針 4（修正経路）は `/wikicommit-fix` に決めた**。機械的な一括置換スクリプトは用意しない — 値がページのタイトルと一致することは根拠であって証明ではなく（同名の別主体がありうる）、`properties:` への自動書き込みをヘルスチェックの責務に含めるべきでもない。既存パイロットへの遡及修正も行わない（対応方針 5）。
>
> **検出スクリプトの担当（Issue #561 の完了条件）**: Issue #560 と共有する基盤であるため、担当を次のように分けた — 「ページが**無い**名前が複数作品に再登場する」（昇格候補）は `check_recurring_characters.py`（Issue #560、`character` に限定。作品の同一性という概念を要するため）、「ページが**在る**のにリンクされていない」はエンティティ型を range に持つ全 `properties:` キーを対象とする本スクリプト（Issue #561）。要求される行動が正反対（ページを作る／リンクにする）であることが分割の基準であり、`check_wanted_pages.py` の `WANTED`/`TYPE_MISMATCH` の分割（Issue #563）と同じ考え方に立つ。Issue #560 の実装は当初 `character` に限った `UNLINKED` 所見も出していたが、本 Issue で二重報告を避けるため後者へ移した。

<!-- -->

> **`properties:` 値の WikiLink 化（Issue #496）は RANGE 分類のみを入力とする、型テンプレートによらない一律ルール（Issue #523 で明確化）**: Pass 3 は `properties:` の各キーについて、`check_schema_org_type.py --show-range`（パス 2b 実行時に既にキャッシュ済み）が返す RANGE 分類（Entity-only / DataType-only / Mixed）に基づき、値を `[[Type/slug]]` 形式で書くかプレーンな値のまま書くかを判断する（詳細な判断基準は `docs/DesignDoc-data.md` §4.1 の該当コールアウト、実装は `.claude/skills/wikicommit-generate/SKILL.md` Pass 3「Property-value WikiLinks」参照）。この判断基準は RANGE 分類のみで決まり、`.wikicommit/schema/<Type>.md` の `granularity` プロース補強や、`properties:` のプレースホルダーが `""` ではなく `"[[Type/slug]]"` の形で書かれているかとは独立である — `Issues/registered/p3-205-property-wikilink-publisher-inconsistency.md`（Issue #523 の起票元（非公開の開発リポジトリ側の記録））が、`BlogPosting`/`NewsArticle` の `author`（`granularity` が明示的に補強）と `publisher`（同一の Entity-only 分類だが補強なし）とで実際のWikiLink化結果が割れた実例を記録している（2ページの突合による確認であり、統計的な有意差の検証ではない）。型テンプレート側の個別 property 名指し補強は、そのテンプレートの著者が特に重要・リスト形式になりやすい等の理由で人間の可読性のために書いた注記であり、ルールの適用範囲を示すものではない。`publisher`（`BlogPosting.md`・`NewsArticle.md`）に加え、他の標準型テンプレートを同じ基準（`--show-range` で Entity-only/Mixed だが補強なし）で横断確認したところ同型のパターンが複数見つかったため、`Organization.md` の `foundingLocation`・`Person.md` の `affiliation`・`Place.md` の `containedInPlace`・`Event.md` の `organizer`/`performer` にも Issue #523 で補強を追加した。今後型テンプレートを新規追加・改訂する際も、特定 property だけを補強したことが他の同分類 property の適用除外だと誤読されないよう注意する。

#### テキスト抽出 Skill ルーティング

研究調査（Anthropic 公式 Skills の採用状況・MarkItDown の業界収束）に基づく推奨マッピング。

| ファイル種別 | 使用 Skill | 備考 |
|---|---|---|
| `.md` / `.txt` | 直接読み込み（Skill 不要） | — |
| `.pdf`（テキスト型） | Anthropic 公式 `pdf`（優先）、未インストール時は `markitdown[pdf]` に自動フォールバック | `pdf` は137K インストール実績・テーブル/暗号化対応。フォールバックの経緯は本節末尾の Issue #242 callout 参照 |
| `.pdf`（スキャン型） | `ocr-and-documents`（NousResearch） | Marker-PDF による 90 言語 OCR |
| `.docx` | Anthropic 公式 `docx`（優先）、未インストール時は `markitdown` に自動フォールバック | tracked changes・コメント対応。フォールバックの経緯は本節末尾の Issue #268 callout 参照 |
| `.pptx` | Anthropic 公式 `pptx`（優先）、未インストール時は `markitdown` に自動フォールバック | 内部で MarkItDown を採用済み。フォールバックは Issue #268 callout 参照 |
| `.xlsx` | Anthropic 公式 `xlsx`（優先）、未インストール時は `markitdown` に自動フォールバック | openpyxl ベース。フォールバックは Issue #268 callout 参照 |
| `.epub` | `ebook-extractor`（フォールバックなし） | ebooklib + BeautifulSoup。`markitdown` では等価にカバーできないためフォールバック非対応（Issue #268） |
| URL（Webページ・PDF等への直リンク含む） | `markitdown`（Python パッケージ。Claude Skill ではない）を `add_source.py --fetch-url` 経由でPython APIとして呼び出す（Issue #527。詳細は本節末尾の callout 参照） | 指定 URL のみ取得し、本文中のリンク先への追加取得は行わない（Issue #166）。`markitdown` はHTTPレスポンスのContent-Type（mimetype・charset）に基づき変換方式・文字コードを判定するため、URL が直接 PDF 等を指す場合も追加の `type: path` 登録なしで処理できる |
| URL（YouTube 動画） | 同上（`markitdown`）**＋ `youtube-transcript-api`**（追加の Python パッケージ） | 未導入だと `markitdown` は字幕（`### Transcript`）を例外も警告もなく落とし、タイトル・キーワード・Runtime・概要欄だけを返す（Issue #574）。Pass 1 のガードC（`check_extraction_quality.py check-fetch-capability`）が取得前にこれを検出して処理を停止し `pip install youtube-transcript-api` を案内する。対象は `youtube.com`/`youtu.be`/`m.youtube.com`（リダイレクト後に `https://www.youtube.com/watch?…` へ着地する形式）のみで、`music.youtube.com` はリダイレクトせず変換器自体が適用されないためガードBの既知不可ドメイン扱い。`/shorts/<id>`・`/playlist`・チャンネルページも変換器が適用されないため、取得後に `### Video Metadata` の有無を確認して `status: failed` とする（Pass 1 手順6）。パッケージ導入済みで字幕が無い動画は失敗扱いにせず Completion Notice にロールアップする |
| その他 | `markitdown`（フォールバック） | 20 種類以上をカバー |

未インストールの Skill・パッケージが必要な場合は処理前にユーザーへインストールコマンドを案内して中断する。

> **`max_retries` 超過を人間が判断で許す実運用（Issue #571）**: `dev/pilot-saitama-wiki.md` で `AdministrativeArea/urawa-ward.md` だけが `generate.max_retries: 2` を超える 3 回目の修正を受けた。設計どおりなら `failed_pages` に入れてページを破棄すべき場面である。実行者の理由は「1 箇所の記述が広すぎるというだけで中核となる区のページを丸ごと失うほうが明らかに損失が大きい」。
>
> **判断は妥当だが、設計が想定していなかった**。`max_retries` は「何度やっても直らないページを諦める」ための上限だが、urawa-ward の 3 巡目は**毎回別の欠陥**が見つかっていた（3 巡目は駅周辺の店舗に関する記述が出典より広かった）— これは収束していないのではなく、レビューが働いている状態である。
>
> **対応方針 (a) を採る**（対話実行中の人間による超過を許容し、明記する）。(b)「同じ欠陥の繰り返しと毎回別の欠陥を区別して扱いを分ける」・(c)「破棄ではなく問題箇所を落として残りを書き出す選択肢を足す」はいずれも Pass 4 の複雑さに見合わない。Pass 4 手順5 に、リトライが**新しい**欠陥を出し続けている場合に限り、破棄する前に人間へもう 1 回試すか尋ねてよいことを明記した。**非対話実行では自分の判断で延長しない**、**同じ形で落ち続けるページは延長しない**の 2 点を条件として付す。

<!-- -->

> **表形式ソース（CSV/XLSX）の扱い（Issue #568）**: 表形式は過去のどのパイロットも扱ったことのない形状で、`dev/pilot-saitama-wiki.md` が初めて検証した。**取り込み自体は問題なく成功している**（オープンデータポータルの `resource_download/` が XLSX を直接返し、`markitdown` が Markdown 表に変換。403 等もなく URL 登録だけで完了）。**読み取り精度も完璧**で、別セッションのレビューが全集計値を再計算して一致を確認している。問題は抽出の**対象選定**と、生成されたページの**抽象度**の 2 点にある。
>
> **(i) 独立性の判定は行数ではなく列の内容で行う**。236 施設 45 指定管理者の指定管理者一覧（6 列）から生成されたのは 5 ページのみで、施設エンティティは 1 件も抽出されなかった。原因は `Organization.md` の「独立した事実がない組織は作らない」というルールを「1 行 ＝ incidental」と解釈したことにある — ルールの文言は行数ではなく事実の有無を問うており、実際この解釈は 13 施設・8 施設を受託する中規模 6 者も落としていた。**散文では「言及の厚み」が独立性の代理指標として機能するが、表では全行が同じ厚み（1 行）になるためこの代理指標が壊れる**。行が自分自身の属性を複数持つ（所在地・規模・期間・区分等）なら独立した事実であり、名前と 1 つの対応関係しか持たない行はそうではない。**1 つの主体が複数行を占める場合はその主体自身の行をまとめて読む** — 同じ対応関係の繰り返しは 1 つの対応関係のままだが、それらの行が主体に規模・幅・広がり（何件・どの期間・どの区分）を与えるなら、それはその主体についての属性である。落とされた中規模 6 者はこちらに当たり（13 施設・8 施設という規模・期間の幅・選定方法の別が指定管理者自身について述べられている）、一方の施設側はどの列も施設自身については何も述べていないため落ちる。表全体の行数そのものは判定に関係しない。
>
> **(ii) 記述的情報を持たない対応表からは実体ページを作らない**（対応方針 2 の (a) を既定とし、(c) を情報の行き先とする）。saitama の CSV は 6 列（施設名／施設数／指定管理者／指定期間（年）／選定／所管課）のみで、**施設が何か・どこにあるかは一切書かれていない**。そこからページを作っても「誰が・いつまで管理するか」しか書けず、それは施設についての事実ではなく契約についての事実である。関係の行き先は 2 つ: 相手側のページが既に在れば `action: update` で記録し、無ければ記録しない（表自体は `sources` と `content/sources/` の公開ページから引き続き辿れる）。一方、**表が何についての表かという概念**（制度・事業・区分）は通常は実体を持つエンティティであり、集計値はそのページに**性格づけとして**書く（件数・偏り・幅）— 行を散文化して並べるのではなく。
>
> なお「もっと多く抽出せよ」が常に正しいわけではない点に注意する。5 ページという結果自体は素材の**種類**から見て妥当であり、素材量（236 施設）の少なさによるものではない。
>
> **(iii) Issue #337 の Pass 3 指示は表形式には効いていなかった**ため、例示を追加した。`DefinedTerm/designated-administrator-system.md` は定義部が簡潔で正確な一方、続く 15 行が表データの散文化になっており、うち 1 行は所管課 18 課を延々と列挙していた。数値はすべて正確だが定義ではない。契約データは数年で陳腐化する一方 `expires_at` は未設定であり、転記はページに**追跡されない期限**を静かに持ち込む。
>
> **1 ソースあたりのエンティティ数の上限は導入しない**（対応方針 4）。saitama パイロットは事前に「上限ガードの追加等が必要か」を観察項目に挙げていたが、実測は**逆に少なすぎた**（236 施設 → 5 ページ）。上限ガードは不要と判断し、経緯の記録に留める。
>
> **「CSV 先行 → 後発ソースが `action: update` で統合」の再検証は次のパイロットに残す**（Issue #568 の完了条件）。このパイロットでは施設エンティティが 1 件も抽出されなかったため検証自体が成立せず、後から Wikipedia 由来で生成された `StadiumOrArena/nack5-stadium-omiya.md` の `sources` にも opendata URL は含まれていない（二重生成は起きておらず重複チェックは PASS）。**なお上記 (ii) の既定の下では、記述的情報を持たない対応表について「CSV 先行」という運用自体が成立しない** — CSV は実体ページを作らず、後発ソースが作ったページに `action: update` で関係を足す向きになる。再検証すべきは、**列に実際の属性を持つ表**（施設一覧に所在地・規模・開設年が含まれるような）を先に取り込んだ場合であり、次のパイロットの確認項目として記録する。実 LLM 実行を要するため本 Issue では実施していない。

<!-- -->

> **プログラミング言語ソースコード（`.kt`/`.py`/`.ts` 等）の扱いについて（Issue #337）**: 上表では独立した行を設けず「その他 → `markitdown`」に含めたままとした。`Paperwork-Navigator-wikicommit-pilot` パイロットで `.kt` ファイルを ingest した際、抽出自体（`markitdown` フォールバック経由）は成功し意味不明な出力にもならなかった — 問題があったのは抽出手段ではなく、生成されたページが `DefinedTerm.md` テンプレートの「1段落の精密な定義」という抽象度を大幅に超え、内部関数名・正規表現ロジックまで転記された実装ドキュメントに近い内容になっていた点だった。つまり原因はテキスト抽出ルーティングではなく Pass 3（ページ生成）側がソースの詳細度をそのまま転記してしまうことにあったため、本 Issue の対応は抽出ルーティング表の変更ではなく `.claude/skills/wikicommit-generate/SKILL.md` Pass 3 に「スキーマが想定する抽象度をソースの詳細度に関わらず遵守する」指示を追加する形で行った（Pass 3 の該当箇所参照）。抽出ルーティング自体は現状のフォールバックで機能しているため変更不要と判断した。
>
> **URL の抽出手段について**: 当初の調査（本節冒頭）では `jina-reader` を推奨マッピングとしていたが、実装（`.claude/skills/wikicommit-generate/SKILL.md` Pass 1）は当初 Claude Code 標準の WebFetch ツールを直接使う設計を採用した（追加 Skill のインストールが不要でシンプルなため）。しかし WebFetch は「小型モデルによる要約」を返す仕様であり、Pass 1 の「verbatim 保存」前提と矛盾すること・大きいページが要約されてしまい hash がページ更新検知として機能しないことが `coffee-knowledge-wiki` パイロットで判明した（Issue #189）。そのため URL 抽出経路を `markitdown` CLI の直接実行（決定論的・要約なし）に切り替えた。`markitdown` は JS 実行不可・ログイン必須ページ非対応という制約があるが、これは WebFetch と同程度以下であり実害はない。
>
> **上記「実害はない」の訂正（Issue #425）**: `ai-driven-dev-wiki` パイロットで、JS実行前提のSPAサイト（`x.com`）を `markitdown` で取得した際、失敗ではなく「非空だが実質無意味」なシェル（ナビゲーション・ログインプロンプトのみ、ページ本文を含まない）が返り、Pass 1 の当時の抽出失敗判定（空/読み取り不能のみを検出）をすり抜けて `status: generated` として成功記録されてしまうケースが実際に確認された。つまり「JS実行不可」という制約は、単に取得できないだけでなく「一見成功したように見えるが中身のない記録が残る」という、より発見しづらい実害を伴っていた。`check_extraction_quality.py`（`docs/DesignDoc-ScriptSpec.md`）の既知JS-shellドメインチェック・低情報密度チェックの2ガードで対処済み（詳細は `docs/DesignDoc-pipeline.md` §6.1 の該当 callout、および下記のテキスト抽出 Skill ルーティング表末尾の説明を参照）。
>
> **上記2ガードの強度を分離（Issue #562）**: 当初は2ガードとも `status: failed` として同じ強度で扱っていたが、`dev/pilot-saitama-wiki.md` で日本語Wikipedia・市公式サイトHTML・統計PDFの計8件中4件が低情報密度チェック（ガードA）の誤検知となり、実行者が4件すべてを手で上書きして続行していたことが判明した（すでに「必ず上書きされる警告」として運用されており、設計と実運用が乖離していた）。原因は2つある: (1) `text.split()` による空白分割が、分かち書きしない日本語の地の文とパーセントエンコードされたリンク先URLを1トークンに融合させ、URL判定が地の文もろとも捨てていた実装バグ（URL境界でのトークン化・CJK文字の重み付け・URLのパーセントデコードで修正した）、(2) ガードAが本来検出したいJSシェル（ナビリンクの羅列＋埋め込みJSON/JS状態）が、リンクの多い正当な行政サイトや数値の多い統計資料とテキスト形状のレベルでほぼ区別がつかないという、汎用ヒューリスティックとしての精度の限界（これは閾値調整では解けない）。(2) を踏まえ、ガードAの `LOW_DENSITY:` を blocking から「人間に続行可否を確認する警告」に降格し、非対話実行時のみ従来どおり `status: failed` とする設計に改めた（Issue #507 と同じ論点。誤検知の代償は1ソース分の再実行だが、真の空シェルを人間確認なしに通す代償は幻覚ページであるため）。ガードB（`check-domain`）は確認済みドメインに対する決定論的判定なので blocking のまま変更していない — 精度の異なる2ガードを同じ強度で扱っていたこと自体が設計の混同だった、という整理になる。`wikicommit-collect` はガードBのみを使うため影響を受けない。
>
> **Wikimedia系ドメインでの403エラー対策 — `markitdown` CLI直接実行からPython API経由への変更（Issue #527）**: `markitdown <url>` のようにURLを直接渡す実装（Issue #189）は、`markitdown` 内部の HTTP クライアント（Python `requests`）が送る既定 User-Agent を Wikipedia・Wikisource 等の Wikimedia 系ドメインが `403 Forbidden` で拒否するという問題を抱えていた（`dev/pilot-arsene-lupin-wiki.md` の事前調査で発見・wikicommit-devセッションで再現・裏付け確認）。curlで検証したところ、空User-Agentおよび`python-requests`系の既定UAのみが403で拒否され、`WikiCommit/1.0`のような単純な独自UA文字列を送るだけで解決することを確認した（ブラウザ偽装は不要）。
>
> 恒久対応として、当初は「`curl`でWikiCommit独自UAを付けてローカルファイルにフェッチ→`markitdown`でローカル変換」という2段構えを実装したが、`/code-review --fix`の多角的レビューで、この方式には実害のある文字コード退行バグがあることが指摘された: `markitdown`はHTTPレスポンスを直接処理する場合、Content-Typeヘッダの`charset`パラメータを文字コード判定の権威的シグナルとして使うが、いったんローカルファイルに落としてから変換する経路ではこのHTTPヘッダの情報が失われ、`charset_normalizer`による統計的推測のみにフォールバックする。`<meta charset>`タグを持たず、文字コードをHTTPヘッダのみで宣言している非UTF-8サイト（レガシーな政府・組織サイト等によくあるパターン）で実際に文字化けを再現・確認した（例: windows-1252で書かれたフランス語テキストの`œ`が化ける）。これは同じ段落が主張する「genuinely verbatim」というhash write-backの前提を壊す重大な問題だった。
>
> 対応として`curl`前処理案を撤回し、`markitdown`のPython API（`MarkItDown(requests_session=...)`）にWikiCommit独自User-Agentを設定した`requests.Session`を渡す方式（Issue本文が挙げていたもう一方の選択肢）に切り替えた。`.claude/skills/wikicommit-generate/scripts/add_source.py`に`--fetch-url`モードを追加し、この呼び出しをスクリプトに委譲した（`docs/DesignDoc-skills.md`§11.5のスクリプト委譲パターンに従う——URLフェッチという決定論的操作をSKILL.mdのプロース手順として再現させるより、`add_source.py`の既存の`--check-hash`/`--write-hash`と同じ場所にコードとして一度だけ実装する方が確実なため）。この方式ならUser-Agentだけが変わり、`markitdown`が本来行うHTTPレスポンスに基づく変換方式・文字コードの自動判定（Content-Typeのmimetype・charset）は`markitdown`に直接URLを渡していた場合と全く同じに保たれる——Issue #189がURL直接ディスパッチに期待していた「追加の`type: path`登録が不要」という性質はもちろん、文字コード判定の正確性も含めて失われていない。詳細な手順は `.claude/skills/wikicommit-generate/SKILL.md` Pass 1、フロー図は `docs/DesignDoc-pipeline.md` §6.1 参照。
>
> **`.pdf`（テキスト型）の抽出手段について（Issue #242）**: 上表は当初 `pdf` Skill を唯一の抽出手段としていたが、`npx skills add` 側の上流バグ（[vercel-labs/skills#744](https://github.com/vercel-labs/skills/issues/744)、[#851](https://github.com/vercel-labs/skills/issues/851)。`~/.agents/skills/` にインストールされ `.claude/skills/` へのシンボリックリンクが作られない）により `pdf` Skill が事実上インストール不能なケースがあることが `ai-industry-pulse-wiki` パイロットで判明した。そのため実装（`.claude/skills/wikicommit-generate/SKILL.md` Pass 1）は `.pdf`（テキスト型）を `pdf` Skill 優先・`markitdown[pdf]`（`[pdf]` extra 付き）フォールバックの2段構えに変更した。この型に限り、本節末尾の「未インストールの Skill・パッケージが必要な場合は処理前にユーザーへインストールコマンドを案内して中断する」という一般則の例外として、`pdf` Skill が未インストール・未認識でも処理を中断せず `markitdown` CLI へ自動フォールバックする（`markitdown` 自体が未インストールの場合は従来通り中断する）。
>
> **`.docx`/`.pptx`/`.xlsx`/`.epub`/画像ファイルへの適用範囲（Issue #268）**: Issue #242 の2段構えフォールバックは `npx skills add` の上流バグ一般に対する対策であり、`pdf` Skill 固有の問題ではない。そのため他の Anthropic 公式 Skill（`docx`・`pptx`・`xlsx`）も原理的に同じ上流バグの影響を受けうる。`markitdown` は `.docx`・`.pptx`・`.xlsx` を追加 extra なしの標準インストール（`pip install markitdown`）で等価にカバーできるため、この3型には `.pdf` と同じパターン（対応する公式 Skill 優先・`markitdown` CLI フォールバック）を適用した（`.claude/skills/wikicommit-generate/SKILL.md` Pass 1・Prerequisite Skills テーブル）。一方 `.epub`（`ebook-extractor` 固有の抽出）と画像ファイル（OCR 固有の抽出）は `markitdown` で等価にカバーできないため、フォールバックを追加しない判断とした。これらの型は Skill が未インストール・未認識の場合、本節末尾の一般則どおり処理を中断してインストールコマンドを案内する（上流バグの影響を受けても回避手段がないため、ユーザーに手動インストールを促すほかない）。

#### SKILL.md への記述指針

```markdown
## 処理フロー

### パス 1: テキスト抽出
source.path の拡張子を確認し、上記ルーティングテーブルに従って適切な Skill を呼び出す。
.md / .txt はそのまま Read ツールで読み込む。
抽出テキストが空でない場合、概算トークン数（簡易概算で可。例: 文字数 ÷ 4）を計算し、管理ファイルの `extracted_tokens` に書き込む（実行のたびに無条件で上書き）。

### パス 2: 分析
事前に `.wikicommit/config.yml` を読んで `primary_lang` と `theme` を取得する。
以下の情報を LLM に渡す：
- 抽出テキスト（全文）
- .wikicommit/schema/ に存在するファイル名一覧（型候補）
- 各型の `粒度ルール`（スキーマファイルから抜粋）
- .wikicommit/entity/<primary_lang>/ の既存ページ一覧（タイトル + パス）
- 管理ファイル body の `## User Notes`（あれば）
- .wikicommit/config.yml の `theme`（空でなければ、theme と無関係なエンティティを `action: exclude` にするよう指示する）

返却形式: §11.6 の分析 JSON 形式。`lang` フィールドには取得した `primary_lang` を設定するよう指示する。必ず JSON のみを返すよう指示する。
返却された `summary` を管理ファイル body の `## Summary` に上書きする（`## User Notes` は変更しない）。

### パス 3: ページ生成
entities のうち `action: create` / `update` のエンティティについて、対応する .wikicommit/schema/*.md の template を読み込み、
ファイル境界プロトコルで返させる。action: update の場合は既存ページを追加コンテキストとして渡す。
`action: exclude` のエンティティはページ生成せずスキップする（既にパス 2 の summary に理由が記録済み）。
実行順序・並列化・リトライ戦略はエージェントに委ねる。失敗したエンティティは failed_pages に記録し
ローカル書き出しから除外する（成功したエンティティのみをローカルに書き出す）。

### パス 4: レビュー
生成した各ページに対してレビューサブエージェントを起動する。
FAIL の場合は再生成（max_retries 回）、上限超過は failed_pages に記録して PR から除外する。
```

### 11.7 自由記述テキストを Bash コマンドライン引数として渡す際の設計ルール

SKILL.md はエージェント（Claude Code）への指示書であり、実際に Bash コマンド文字列を組み立てて実行するのはエージェント自身である（§11.0）。GitHub Issue のタイトル・本文、`wikicommit-init` の `theme` プロンプト回答のように、SKILL.md の記述者が内容を制御できない自由記述テキストを CLI 引数に埋め込む手順を SKILL.md に書く場合、そのテキストにシェルメタ文字（`` ` ``・`$(...)`・`!`・`"` 等）が含まれていると、単純な `--flag "<text>"` のダブルクォート埋め込みではコマンドインジェクションが理論上成立しうる（Issue #375。`wikicommit-init` の `--theme "<theme text>"`・`implement-issue` の `--title "<Issue タイトル>"` で実際に指摘された）。

**ルール**: このような自由記述テキストを CLI 引数として渡す箇所は、必ず区切り文字をクォートしたヒアドキュメント（`<<'EOF'` ... `EOF`）経由のコマンド置換 `"$(cat <<'EOF' ... EOF)"` で渡す。ヒアドキュメントの区切り文字をクォートすると、ヒアドキュメント本文はシェルによる変数展開・コマンド置換の対象外になり、テキスト中にシェルメタ文字が含まれていても安全に扱える。この形式は `gh pr create --body` 等で元々 Skills 共通の慣習として使われていたもので、本ルールはそれを他の CLI 引数（`--title`・`--theme` 等）にも一般化したものであり、単一行の値・複数行の値のどちらでも同じ書き方で機能する（副次的な利点として、値が `=`-joined の1シェル単語になるため、`-` で始まるテキストが別オプションとして誤解釈される argparse の既知の問題も同時に回避できる）。

一方、`<lang>`・`<default branch>` のように、SKILL.md 記述者ではなく上流のスクリプト・コマンド（`validate_frontmatter.py`・`gh repo view` 等）による実在検証・形式検証を経た制約付き識別子は、このルールの対象外とする（本ルールが対象とするのは検証を経ていない自由記述テキストのみ）。除外の基準は「値が何らかのスクリプト・コマンドによって決定論的に検証されているか」であり、「一見システムが生成した識別子に見えるか」ではない — `<Type>`・`<slug>` は当初この除外例に挙げられていたが、Issue #398 の精査で誤りだったと判明したため以下の通り訂正した。

> **`<Type>`・`<slug>` は原則として除外例に含めない（Issue #398 による訂正）**: `wikicommit-merge` のレビュー追跡 Issue タイトル（`--title "Review: <Type>/<slug> (<lang>)"`）で使われる `<Type>`・`<slug>` を検証したところ、`validate_frontmatter.py` は `type` フィールドが `schema:` プレフィックスで始まることしか検証しておらずプレフィックス以降の文字列には制約がなく、`<slug>` に至ってはページのファイル名がそのまま使われるだけで文字種を強制する仕組みがパイプライン上どこにも存在しないことが分かった。両者とも「上流のスクリプト・コマンドによる実在検証・形式検証」を経ていないため、この除外基準を満たさない。該当箇所は `wikicommit-merge` SKILL.md でヒアドキュメントパターンに修正済み。例外的に除外基準を満たす `<Type>` は、`wikicommit-schema-propose` の標準型パスのように `check_schema_org_type.py --type <Type>` の実在検証を経ており、かつ検証対象の語彙（Schema.org）自体が英数字 CamelCase 識別子のみで構成されると分かっている場合に限る（同 Skill のカスタム型パスの `<Type>` は命名規約への準拠を LLM が指示に基づき確認するのみで決定論的なスクリプト検証を経ないため、この限りでは除外対象にならない）。
>
> **候補 URL も対象である（Issue #646 による追記）**: `wikicommit-collect` が候補 URL を CLI 引数として埋め込む 2 箇所（step 5 の `check_extraction_quality.py check-domain`、step 6 の `add_source.py --license-for-url`）も本ルールの対象であり、ヒアドキュメントパターンに修正済み。候補 URL は Web 検索の結果、あるいは step 5.5 が第三者の参考文献リストから verbatim に取り出したものであり、上流のスクリプトが形式を検証した値ではない — 「検証を経ていない自由記述テキスト」という本ルールの適用基準にそのまま当たる。
>
> **URL は一見「制約付き識別子」に見えるため、除外例と取り違えやすい**。実際には `&` を含む URL（`…/w/index.php?title=X&oldid=1` のような普通の permalink）が引用符なしで埋め込まれると、シェルが `&` で分割して前半をバックグラウンド実行し、後半をコマンドとして実行する。`check-domain` 側では、バックグラウンド実行の終了コード 0 が `OK:` と読まれ、**この Wiki が除外すると決めたドメインが候補として通る**（ブロックの目的そのものが無効化される）。Issue #398 が「一見システムが生成した識別子に見えるか」ではなく「何らかのスクリプト・コマンドによって決定論的に検証されているか」を基準とせよと訂正したのと、同じ取り違えである。
>
> **検索クエリの除外は撤回した（Issue #398 による訂正）**: 当初は `.wikicommit/scripts/search_index.py query "<query>"` のような検索クエリ埋め込みについて、「呼び出し先がローカルの読み取り専用スクリプトに閉じているため `--title`/`--theme` とは被害範囲が異なる」という理由で本ルールの対象外としていた。しかしこの判断はコマンドインジェクションが実際にどの段階で起こるかを取り違えていた: `$(...)` やバッククォートによるコマンド置換は、そのシェルコマンド行が組み立てられた時点でシェル自身によって評価されるのであって、その後どのプログラム（読み取り専用スクリプトかどうか）に引数が渡されるかとは無関係である。つまり呼び出し先を read-only なローカルスクリプトに限定しても、シェルコマンド行の組み立て自体に無防備なテキストが埋め込まれていれば、そのテキストに含まれるシェルメタ文字は呼び出し先のプログラムを経由せずシェル上で直接実行されてしまい、`--title`/`--theme` と全く同じ被害が起こりうる（実機検証済み）。この訂正を受け、`wikicommit-ask`・`wikicommit-search`・`wikicommit-quiz`・`wikicommit-synthesize` の検索クエリ埋め込みはすべてヒアドキュメントパターンに修正済み。

### 11.8 ユーザー向け出力から内部の手順番号・設計語彙を排除するルール

SKILL.md の手順（`### Step N`・`#### Pass N` 等の見出しや、`Route A`/`Route B` のような設計上の呼称）は、あくまでエージェント自身がその Skill をどう実行するかを記述した内部構造であり、ユーザーがそれを知っている前提は成り立たない（§11.0 のエージェントネイティブ型設計そのものが、これらをユーザーへの説明契約ではなく実行順序の記述として導入したものであるため）。ところが `dev/pilot-ai-driven-dev-wiki-round3.md` の実行で、`/wikicommit-review` が「Do these findings look correct to you, so I can proceed to Step 5 (recording the review)?」という確認メッセージをそのままユーザーに提示し、ユーザーが「Step 5 が何を指すか分からない」と気づく事例が発生した（Issue #492）。原因を辿ると、`wikicommit-review` の Guidance After Completion テンプレート自体が `[Route A page — ...]`/`[Route B page — ...]` という内部呼称をラベルとしてそのまま出力する設計になっていた、`wikicommit-generate` の Completion Notice が他 Skill（`wikicommit-merge`）の内部手順番号に直接言及していた、といった具体例が複数見つかった。

**ルール**: ユーザーに向けた確認プロンプト・完了メッセージ（Guidance After Completion・Completion Notice・Next steps 等、ユーザーが読むことを前提にした出力全般）は、以下の3種の内部語彙をそのまま露出させず、現在の状態と次に取るべきアクションを平易な言葉で説明する。SKILL.md の記述者は、手順の内部構造を指す語彙と、ユーザーに見せる語彙を明確に分けて書くこと — 例えば「このページには追跡 Issue があり、Close したので自動マージされます」のように、`Route A`/`Route B` のラベルではなく、そのラベルが表す実際の状態を直接説明する。

| 対象語彙 | 例 | ユーザーに届かない理由 |
|---|---|---|
| 内部手順番号 | `Step N` / `Pass N`（`Pass 2b` 等の枝番を含む） | §11.6 に定義があるが、`docs/` は配布スナップショットに含まれない |
| 設計語彙 | `Route A` / `Route B` | 同上。§11.0 のエージェントネイティブ型設計では実行順序の細部はエージェントに委ねる前提であり、`Pass 2b` という区切り自体がユーザーへの契約ではない |
| **内部トラッカー参照** | `Issue #NNN` / `PR #NNN` | 参照先が private リポジトリの Issue であり、**公開後も追跡手段が存在しない**。ユーザーから見れば `Pass 2b` と同程度に意味不明で、追跡不能な分だけ悪い（Issue #588） |

内部トラッカー参照を落とすことによる設計トレーサビリティの喪失は、**フェンスの外側（エージェント向けの説明文）に残す**ことで補う — 実際、大半の箇所は既にテンプレート外の導入文に同じ Issue 番号を書いており、情報自体は失われない。

**テンプレート本文とエージェント向け指示を同じフェンス内に混在させない**。`wikicommit-generate` の Completion Notice には、ユーザーに表示するフェンス済みテンプレートの**内側**に「Do not describe this as "reviewed before merge" to the user」というエージェント宛の指示が書かれていた例がある（Issue #588 で修正）。テンプレート本文と、そのテンプレートをどう使うかの指示との境界が崩れた状態であり、本ルールが求める分離がフェンスの内外というレベルで守られていない。

**例外**: 読み手が開発者・レビュアーである成果物（GitHub の PR ボディ等）はこの限りではない。例えば `wikicommit-schema-propose` の PR Description Template（§11.6 参照）内の `<path from Step 1, one per line, up to 5>` はこの例外に該当する。**`wikicommit-merge` が生成するレビュー追跡 Issue の本文は例外に該当しない** — Issue #313 の設計意図そのものとして「Claude Code のセッションを持たない読者が GitHub 上で直接 Close するだけでレビューに参加できる」ことを狙ったものであり、読み手は開発者ではなく Wiki の読者であるため。「Issue 本文だから例外」ではなく「読み手が誰か」で判定する。

#### CI による再発検出（`tools/check_skill_user_facing_vocabulary.py`。Issue #588）

**本ルールは散文だけでは維持できていなかった**。§11.8 を制定した Issue #492 の後、Issue #539 が `wikicommit-status` の結果表示テンプレートに `(informational — see Step 5)` という新たな漏れを持ち込んでいる。制定後に新規の違反が通った以上、非ブロッキングの警告では目的を果たさないと判断し、**検出時に exit 1 を返すブロッキングチェック**として新設した（当時の同種のチェック — `check_skill_md_lines.py`・`check_skill_invocation_mode.py` — はいずれも非ブロッキングであり、この点だけ前例から外れる）。配置は Issue #660 で `dev/scripts/` から `tools/` へ移した。`.github/workflows/test.yml` に配線済み。

**走査対象は `.claude/skills/wikicommit-*/SKILL.md` のフェンス済みコードブロックのうち、info string が無いか `markdown`/`md`/`text` のもの**（＝ Skill がユーザーへそのまま出力するブロック）。`bash`/`json`/`yaml` 等はコマンド・データ形式でありユーザー向け散文ではないためスキップする。

**例外の指定方法**: フェンスの直前の行に理由付きの HTML コメントを置く。理由が空のマーカーはそれ自体がエラーになる — 例外を足すたびに、上表の判定基準（読み手は誰か）を意識的に言い直させるため。

```markdown
<!-- skill-vocabulary-exception: PR body; its reader is the developer or reviewer deciding whether to merge -->
```

現時点の適用先は2つ: `wikicommit-schema-propose` の PR ボディ（読み手が開発者・レビュアー）と、`wikicommit-generate` の再生成モードのパス構成図（**そもそもユーザーに出力されないブロック**であり、エージェント向けの説明図）。後者が示すとおり、マーカーの意味は「開発者向け成果物である」より一段広く「**このブロックはユーザー向け出力ではない**」である。

**既知の限界**: 本チェックはフェンス済みテンプレートしか見ない。Issue #492 が実際に踏んだ漏れは、`/wikicommit-review` が手順指示の散文中にある「Step 5」という記述を読んでエージェントが**自分の言葉で**確認質問を組み立てた際に混入したものであり、テンプレートに存在しない文言であるため**このチェックでは検出できない**。散文指示側のガードレールは引き続き必要であり、CI はそれを置き換えるものではなく補完するものである。

本ルールの適用漏れは、Skill の実装時・改訂時に完了メッセージ・確認プロンプトのテンプレート文字列を書く箇所であれば毎回チェック対象になる — 他の横断ルール（§11.7 等）と同様、新しい該当箇所を追加する際はこのルールを踏まえること。なお §11.7 は同じ「横断ルールが散文のみ」という構造的問題を抱えており（Issue #398 が事後精査で複数の適用漏れ・除外基準の誤りを発見した実績がある）、同種の CI 化は本 Issue のスコープ外として別 Issue に残す。

### 11.9 配布物から開発リポジトリのパスを参照しないルール

`install.sh` が配布する 15 Skill（`.claude/skills/wikicommit-*/` の SKILL.md および `scripts/`）と、`wikicommit-init` がユーザーの wiki リポジトリへ展開する `scripts/templates/` のペイロード（`.wikicommit/scripts/*.py`・`quartz.config.yaml`・`.github/workflows/*.yml` になる）は、いずれも本リポジトリの `docs/`・`Issues/`・`dev/` を持たないリポジトリに着地する（`Issues/` は公開リポジトリにも含まれない — 開発リポジトリ側にのみ存在する記録である）。したがってこれらのディレクトリへのパス参照は、配布先では**原理的に追跡できない**（Issue #549）。

実測では配布 15 Skill の SKILL.md だけで 83 箇所あり、そのすべてが「このファイルを読め」という命令形ではなく括弧内の出典注記（設計根拠）だったため、参照先が無くても Skill の実行自体は失敗していなかった。それでも実害は 3 つある: (1) SKILL.md は Skill 起動のたびに全文がエージェントのコンテキストに読み込まれるため、追跡不能なパス文字列を毎回のコンテキストで運び続ける、(2) OSS 利用者が設計根拠を追おうとしても追えない（`Issues/`・`dev/pilot-*.md` はホワイトリスト上フェーズに関わらず配布しないため、永久に追えない）、(3) LLM エージェントが参照先を読もうとして失敗し、無関係な探索に時間を使う。

**ルール**: 配布物の中に `docs/DesignDoc-*.md`・`Issues/`・`dev/` へのパスを書かない。`docs/` プレフィックスを外した素の `DesignDoc-data.md §4.2` のような書き方も同じく不可（同じ未配布ファイルを指しており、配布先では同様に追跡できないため）。設計根拠を残したい場合は次のいずれかにする:

- **GitHub Issue 番号のみを残す**（`Issue #523` 等）。短く、public 化後は GitHub 上で誰でも引ける
- **要点を1文で内在化する**。参照先の内容を知らないとエージェントが判断できない場合はこちら（結果として短くなるとは限らないが、追跡不能なパスを残すよりは良い）
- **注記ごと削除する**。指示自体が SKILL.md 内で完結しており、参照先が「なぜそうなっているか」を示すだけの場合はこれで十分（大半がこれに当たる）

相対パスを絶対 URL（`https://github.com/wikicommit/wikicommit/blob/main/docs/...`）へ書き換える案は採らない — 追跡可能性は上がるが文字数がさらに増え、(1) のコンテキスト消費に逆行するため。

逆方向（`docs/DesignDoc-*.md` から SKILL.md への参照）は開発リポジトリ内に閉じているため本ルールの対象外であり、既存の多数の参照もそのまま維持する。追跡の担い手を「配布物 → docs」の双方向から「docs → 配布物」の一方向に寄せる、という整理になる。

`tools/check_distributed_path_refs.py`（`docs/DesignDoc-TestSpec.md` L9）が CI で blocking の回帰ガードとして走り、再混入をその場で止める。
