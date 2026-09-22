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

> **symlink 配置のリポジトリでは `.agents/` が追跡対象になる（Issue #948）**: 上の 2 点目（Git 管理の前提と食い違う）は「シンボリックリンクのままコミットすると、リンク先である `.agents/` も併せてコミットしない限り clone 先でリンク切れになる」と述べているが、**その「併せてコミットする」を実際に行う主体はどれも `.agents` を知らなかった**。`/wikicommit-update` Step 8 の `git add` は 12 個のパスを列挙しながら `.agents` と `skills-lock.json` を含まず、`/wikicommit-init` 側の選択的な列挙（`_root_outputs.py` 由来）にも無かった。
>
> **したがって、symlink 配置を選んだリポジトリにとって `.agents/` はビルド成果物ではなく Skills の実体そのものであり、追跡対象である。** `.claude/skills/<name>` はそこへの相対シンボリックリンクにすぎないので、`.claude` だけをコミットすると**リンクだけのツリー**が clone に届く。`skills-lock.json` はインストールした内容の記録でありリンクの解決には関与しないため、どちらか一方で代替できない別のパスである。
>
> 両者は `_root_outputs.py` に `origin="install"` / `update="skip"` / `compare="none"` で載る — `.claude` と同じ答えで、理由も同じ（init.py が書くものでも、refresh するものでも、比較するものでもない）。あわせて `may_be_absent` を持つ: `install.sh` で入れたリポジトリには `skills-lock.json` が無く、実体コピー配置には `.agents` が無いため、**`git add` の abort-on-missing にそのまま当たる**。init 側の印字は既定が `git add -A` なので（Issue #842）この問題を持たず、影響するのは既存リポジトリ向けに残した選択的な列挙だけで、そこには「無いものは落とせ」という caveat が submodule のパス（`.gitmodules` / `quartz`）と同じ 1 文で両者を覆う。`/wikicommit-update` 側は元から同趣旨のコメントを持っていたため、パスを 2 つ足すだけで済んでいる。
>
> **`--copy` へ移行して `.agents` を消す案は、この Issue では採らない**。移行すると `.claude/skills/` が実体になり `.agents/` は孤児として残るため、**既に symlink 配置でコミット済みのパイロット 2 件**（saitama / decameron）に対しては別途の移行手順が要る。Skill 側は現実の配置を扱えなければならない、というのが先である。

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
6. **内部限定 Skill の除外機構（今回利用）**: SKILL.md frontmatter に `metadata:\n  internal: true` を付与すると、`npx skills add <repo>`（Skill 名を指定しない一括インストール）から除外される。`--skill <name>` で名指しされた場合や `INSTALL_INTERNAL_SKILLS=1` 環境変数を立てた場合は対象になる。WikiCommit 本体開発専用の内部限定 Skill 2 本（`install.sh` の配布対象一覧にも含まれていない）にこのフラグを付与し、`npx skills add wikicommit/wikicommit` の一括インストール時に配布対象の 15 Skill（`install.sh` と同一集合）のみが入る状態に揃えた（実機検証でも `Found 15 skills` と表示され、内部限定 2 件が除外されることを確認済み。Issue #555。この件数は記載当時 12 だったが、その後 Skill を追加した分だけ増えている — `install.sh` の `SKILLS` 配列が正）
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
8. **リポジトリ側の対応（本 Issue のスコープで実施済み）**: リポジトリルートに `.claude-plugin/plugin.json` を追加した。`skills` フィールドに `.claude/skills/<name>/` を 15 個（`install.sh` の配布対象と同一集合。記載当時は 12 個）明示的に配列で列挙することで、ディレクトリ構造を変更せず・内部限定 Skill 2 本を含めずに済んでいる（`skills` フィールドは「デフォルトの `skills/` スキャンに追加」する仕様のため、個別パスを列挙すれば任意のサブセットだけを対象にできる）。`version` フィールドは当初意図的に未設定としていた（開発が活発な Phase 3 中はコミット SHA バージョニングを採用し、正式リリース時に semver 付与へ切り替えるかは後で判断するという保留）が、**Issue #577 で「付与する」と決着させ `0.1.0` を設定した**。決め手は claude-plugins-community への掲載（本項の主題）を視野に入れており、掲載時には `claude plugin validate` が `version` 未指定を warning にするため、どのみち必要になること。なお `version` を明示するとピン留めになり bump を忘れると更新が静かに止まる一方、省略しておけば SHA フォールバックにより配布 push のたびに自動で新版として検知される、という逆転（省略の方が更新が届きやすい）が存在する点には注意する — この副作用は「版を上げるときは `_version.py`・`plugin.json`・`CHANGELOG.md`・`.claude/skills/wikicommit-init/CHANGELOG.md` の 4 箇所をまとめて更新する」という運用と、前二者の同期を強制する `tests/test_version_sync.py`・後二者の一致を強制する `tests/test_changelog_sync.py` で受け止める（4 つ目は 3 つ目のコピーで、Issue #713 以降 `/wikicommit-update` がそこを読む。更新箇所の正本は `CHANGELOG.md` 冒頭）。同 Issue で決めたもう一つの source of truth（`.wikicommit/scripts/_version.py`。インストール先の wiki リポジトリまで届く唯一の情報源で、`config.yml` の `wikicommit_version`・ページの `generated_with` / `translated_with` の値はすべてここから読む）については `docs/DesignDoc-data.md` §3.3・§4.1 を参照。`claude plugin validate .` は記載当時 warning 2 件（`version` 未指定・リポジトリ直下の `CLAUDE.md` は Plugin コンテキストとしてロードされない旨）のみで PASS 済みだった（前者は Issue #577 の `version` 付与で解消）。後者は WikiCommit 開発リポジトリとしての `CLAUDE.md` の役割上想定内（Plugin へのコンテキスト提供は Skill 経由で行う設計のため元々整合している）

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

#### `description` の書き方 — 「何をするか」と「いつ使うか」の両方を書く（Issue #912）

公式ガイダンス（`skill-creator`）は `description` を **triggering の唯一の機構**と位置づけ、"All "when to use" info goes here, not in the body" と明記し、さらに「Claude は Skill を **undertrigger** しがちなので description は少し **pushy** に書け」としている。

**この規則が当たるのは、モデルが自律起動しうる Skill だけである。** WikiCommit の配布 17 Skill のうち 9 件は `disable-model-invocation: true` を持ち、人間が `/wikicommit-xxx` と打つことでしか起動しない — その 9 件では description の triggering 機能がそもそも働かないので、「いつ使うか」を書いても誰も読まない。**次に標準と突き合わせる人が「17 件中 9 件が違反している」と読まないよう、ここに記録しておく。**

| | 件数 | 扱い |
|---|---|---|
| `disable-model-invocation: true` を持つ | 9（`collect` / `fix` / `init` / `reconcile` / `remove` / `review` / `schema-propose` / `synthesize` / `update`） | **対象外。** モデルが自律起動しないので triggering は働かない |
| 持たない配布 Skill | 8（`ask` / `generate` / `merge` / `quiz` / `search` / `serve` / `status` / `translate`） | **対象。** 「いつ使うか」を書く |

**かつて後者は読み取り専用の 5 件とちょうど一致していた。その一致は Issue #945 で崩れた** — 書き込み系である `generate` / `merge` / `translate` の 3 本が対象側へ移ったためである。**これは「読み取り専用だけが自律起動してよい」という規則に例外を 3 つ作ったのではなく、規則の立て方が誤っていたことの訂正である。**

フラグは 2 つの仕事を兼ねていた — (i) 通りすがりの依頼で自律発火しないこと、(ii) 副次的に、人以外のあらゆる起動経路を塞ぐこと。**(ii) は意図されたものではなく、無人運用の経路を丸ごと消す** — 公式ドキュメントが挙げるのは description 一致による自律ロード・**サブエージェントへのプリロード**・**スケジュール実行の発火**の 3 つであり、加えて Skill ツールからの明示起動も（フラグを持つ Skill がモデルに一覧表示されないという別の機構の帰結として）塞がる。残るのは人が `/name` と打つ経路だけである。結果として `dev/` の無人運用の手順書 2 本が原理的に成立しない状態にあり、そのことは実行するまで誰も気づかなかった。(i) は description（全リポジトリに届く）と `skillOverrides`（リポジトリごと・運用者が持つ）が担い、フラグが残るのは**無人経路そのものを一切望まない Skill** に限る（`collect` は登録前の人間承認が設計の中核であり、`fix` / `remove` は `merge` 経由で PR を作る側である）。

#### 自律起動を絞る手段は 2 層あり、所有者が違う（Issue #945）

フラグを外した 3 本について、(i) を担うのは次の 2 つである。**フラグが配布物（`npx skills add` が上書きする）にあったのに対し、下段はそのリポジトリ自身の設定にあり、運用者が持ち続けられる。**

| 層 | 手段 | 届く先 |
|---|---|---|
| ① | `description` を絞る | **全リポジトリ**。`npx skills add` で既存の Wiki にも届く |
| ② | `.claude/settings.json` の `skillOverrides` | **そのリポジトリだけ**。新規リポジトリへ配る経路は Issue #953 |

`skillOverrides` の取りうる値は 4 つで、**軸が「Claude への見せ方を絞る」方向にしかない**（フラグを設定で打ち消すことはできない）:

| 値 | Listed to Claude | `/` メニュー | モデルが起動できるか |
|---|---|---|---|
| `on`（既定・未記載時） | 名前と description | あり | できる |
| `name-only` | 名前のみ | あり | **できる** |
| `user-invocable-only` | 隠す | あり | できない |
| `off` | 隠す | なし | できない |

**新規リポジトリには `name-only` を配る**（Issue #953）。`user-invocable-only` を採らないのは、無人実行したい運用者が `on` に戻す必要があり、その瞬間に保護が全部外れる（全か無かのスイッチになる）ため。`name-only` は説明文＝自律トリガーの主機構だけを隠して名指しの起動経路を残すので、無人実行は切替なしで通る。

**このリポジトリ自身（`wikicommit-dev2`）は `user-invocable-only` にしてある。** ここには無人実行の必要が無く（クラウド自動化が使うのは `implement-issue` と `review-and-merge` である）、最も強い設定を選んでも失うものが無い一方、dev2 は最も多くのエージェントセッションが走り常に未コミットの変更がある場所だからである。

**したがって、説明文が唯一の防御になるのは②が届かない既存リポジトリである。** Issue #945 の trigger eval が測ったのはその状態（設定なし）にあたる。

**pushy さは読み取り専用の 5 件でも一様ではない。** 誤起動の代償が違うためである。`ask` / `quiz` / `search` / `status` は読み取りしかせず、`.wikicommit/` が無ければ Skill 自身が止まるので強めに振ってよい — とくに `search` と `status` は「`grep` で代替できそうに見える」形をしており、公式が名指しする undertrigger（"Claude only consults skills for tasks it can't easily handle on its own"）にいちばん当たる。**`serve` だけは例外で、`npm run build` を実際に走らせる** ので、ページの内容を答えるためではなくプレビューが実際に要るときに呼べ、と書き分けてある。

**書き込み系の 3 本は向きが逆で、pushy に振ってはならない。** `generate` / `merge` / `translate` のリスクは undertrigger ではなく **overtrigger** であり（誤起動するとページが生成され、続けて `merge` が発火すればデフォルトブランチへマージされて公開される）、しかも上記②が届かないリポジトリでは description が唯一の防御である。3 本とも「いつ使うか」に加えて**いつ使わないか**を明示し、代わりに呼ぶべき読み取り専用の Skill を名指ししている。

**呼び出し元の Skill を「閉じた集合」として列挙しない（Issue #967）。** `merge` の description はかつて「`wikicommit-generate` / `wikicommit-translate` / `wikicommit-synthesize` / `wikicommit-fix` / `wikicommit-remove` / `wikicommit-review` の後にのみ使え」と 6 本を名指ししていた。**`wikicommit-reconcile` がそこから漏れていた** — 同 Skill は `.wikicommit/source/` の `status` を書き換えて未コミットの変更を作り、自分の Notes で `/wikicommit-merge` を後続として名指ししているのに、である。

**これは線引きではなく列挙漏れだった。** 列挙された 6 本のうち 4 本（`synthesize` / `fix` / `remove` / `review`）は `reconcile` と同じ `disable-model-invocation: true` を持つので、フラグは選定基準になっていない（本節の 9 本の一覧を参照）。基準は「未コミットのローカル変更を作るか」であり、`reconcile` はそれを作る。

**そして漏れたのは構造による。** `reconcile` は Issue #874 で**既に存在していた**状態で Issue #945 が description を書いており、それでも漏れた — 全 Skill の一覧が手元にある人間が、書いているまさにその瞬間に落としている。**列挙は Skill が 1 本増えるたびに古くなる一方、古くなったことを知らせるものが何も無い。**

**しかも肯定節の閉じた列挙は、否定節に出てくる Skill 名とは働きが違う。** `generate` / `translate` の description も他 Skill を名指しするが、それは「代わりにこれを呼べ」という**代替案**であり、古くなっても指し先が消えるだけである。肯定節の閉じた列挙は**この Skill 自身の起動条件**なので、古くなると正当な起動を打ち消す。

**ただし、実挙動として抑止していたことは測定では示せなかった。** reconcile 起点の問い（"the sources are back in the queue — commit that"）は旧文面で **0/3**、**新文面でも 0/3** である（`dev/skill-trigger-evals/results-2026-09-18.md`）。起動しないこと自体は実挙動だが、**列挙が原因ではない** — 外しても通らない。したがって上の 4 つの論拠（これが線引きではなく列挙漏れだったこと・漏れが構造によること・肯定節の閉じた列挙はこの Skill 自身の起動条件であること・CI では守れないこと）は列挙をやめる根拠として独立に立っており、trigger eval が与えたのは回帰確認（negative は 1/30 のまま・positive は悪化していない）だけである。**これは器の想定どおりでもある**: 20 問 × 3 回で 3 文中 1 節の語句差を裁定することはできず、eval にできるのは回帰確認であって A/B の優劣判定ではない。

**CI では守れない。** 「書き込み系 Skill とは何か」は frontmatter からも本文の grep からも導けない（後者の実測では `init` / `schema-propose` / `status` / `serve` / `collect` が引っかかる — 案内を印字する側・自前で PR を作る側・読み取り専用・`generate` へ委譲する側であって、列挙すべきものではない）。テストを置けば**同期すべきリストが 2 本になるだけ**で、「新しい Skill が増えたときに気づかない」という原因そのものは残る。逆向きのテスト（他 Skill 名が N 個以上現れたら fail）も採らない — 閾値が恣意的であり、かつ否定節には他 Skill 名が正当に現れうるので、肯定節と否定節を機械的に分ける必要が出て、文面の書き方に依存する脆いテストになる。

**したがって列挙をやめ、性質で述べる**（"the uncommitted changes another wikicommit Skill left under `.wikicommit/`"）。具体性を上げたい場合は `wikicommit-status` が採っている **"and more" 型の開いた列挙**に倣い、閉じた集合の形を使わない。

**`description` にコロンに続く空白（`:` ＋ スペース）を書いてはならない。** frontmatter はクォートされていない裸のスカラーなので、その並びがあると YAML はそこをマッピングとして読み、**frontmatter 全体がパースできなくなる** — `granularity` の箇条書きが同じ理由で壊れたのと同じ罠である（Issue #649）。区切りが要るならダッシュ（`—`）を使う。`tests/test_skill_descriptions.py` が全 Skill について CI で止める。

#### 書き換えが効いたかを trigger eval で実測した（Issue #926）

上の 5 件は手書きであり、**効いたかどうかは Issue #912 の時点では測っていなかった**。`skill-creator` の `scripts/run_eval.py`（trigger eval）でそれを測り、結果を `dev/skill-trigger-evals/` に置いた。対象は 5 件のうち**自律起動しなかったときの損失が大きい 3 件**（`ask` / `search` / `status`）で、`quiz` / `serve` は自律起動を維持したまま今回は測る予算を割かない — この線引きは後から動かせる。

| Skill | passed | positive（trigger すべき） | negative（trigger すべきでない） |
|---|---|---|---|
| `wikicommit-search` | 20/20 | 30/30 trigger | 0/30 trigger |
| `wikicommit-status` | 20/20 | 30/30 trigger | 0/30 trigger |
| `wikicommit-ask` | 16/20 | 30/30 trigger | 10/30 trigger |

**positive は 3 件とも 30/30 であり、90 回の試行で undertrigger は 1 件も起きていない。** 公式が最も警告する方向については、手書きの書き換えは効いている。落ちた 4 件はすべて `ask` の negative（overtrigger）で、うち 2 件は `search` の領分を指す言い回しである — **`run_eval.py` は対象の 1 Skill だけを合成コマンドとして提示するため、曖昧性解消（`search` と `ask` のどちらを選ぶか）は原理的に測れない**。この 2 件は測定器の制約であり、description の欠陥と断定できない。

`improve_description.py` の出力は同じクエリ集合で 20/20（positive を 1 件も失わず negative 4 件が 0/3 に）だったが、**本 Issue では採用しない** — 生成文が `:` ＋ スペースを持ちこのリポジトリの frontmatter 規約（上記）に違反すること、overtrigger へ最適化する向きが undertrigger のリスクと非対称であること、配布物の description 差し替えは測定の範囲を超えることによる。数字と 4 つの理由は `dev/skill-trigger-evals/results-2026-09-14.md` にある。再検討は Issue #937 で行い、結論は次の 4 段である。

**再検討の結論: 差し替えない（Issue #937）。** 決め手になったのは上の 4 理由そのものではなく、その手前の勘定 — **生成文の禁止節が買うものが、測定に現れるより小さい** — だった。後段の `Do not use when wiki pages are raw material for some other job` は 8 つの活動を名指しするが、そのうち editing / translating / generating / reviewing / reorganizing の 5 つが指す Skill（`fix` / `translate` / `generate` / `review` / `synthesize`・`reconcile`）はいずれも `disable-model-invocation: true` であり、**モデルは元から自律起動しない** — そこで `ask` を抑えても代わりに起動するものが無く、undertrigger の面積だけが増える。auditing（`status`）も、その領分の negative 3 件は現行の手書き文で既に通っている。実際に落ちている 1 件に効くのは quizzing / drilling だけである。あわせて生成文は「prefer this over answering from your own knowledge」に `whenever the subject is one the wiki covers` という条件を足しているが、**カバーしているかは検索して初めて分かる**ので起動の判断材料にならず、これも undertrigger 側に働く。overtrigger の代償が「余計な Skill が 1 回読まれる」に留まるのに対し、undertrigger の代償は `ask` の存在理由そのもの（出典付きでこの Wiki の記述から答える）であり、非対称は採らない側に倒れている — **これは同ファイルの理由 3 と同じ非対称だが、当てはめる先が「4 件の overtrigger を消す禁止節」から「実際には 1 件にしか噛まない禁止節」へ変わる。**

> **上の勘定の前提は Issue #945 で一部動いた。結論は再検討していない。** 5 つのうち `translate` と `generate` は`disable-model-invocation` を失ったので、「モデルは元から自律起動しない」はこの 2 つについては偽になった — 禁止節が買うものは 1 件（quizzing / drilling）より増えている。それでも差し替えないという結論を本 Issue では動かさない: 生成文はこの repo の frontmatter 規約（コロン + 空白を含まない）に違反したままであり、`ask` の測定を伴わずに文面を変えればIssue #937 が退けた「測らずに最適化する」形に戻る。**再開の条件は変わっていない** — 枠づけの無い positive をクエリ集合に足して測り直したときである。

**ただし勘定はこの 1 文で閉じない — 実在する利得が 1 件残る。** 上の勘定が覆うのは raw-material の 1 文だけで、生成文の後段には禁止文が 3 つある。lookup / inventory の 1 文が消す 2 件は `dev/skill-trigger-evals/results-2026-09-14.md` が測定器の制約として既に退けているが、**外部仕様の 1 文**（`Do not use for questions about external specifications, standards, APIs, libraries, or general software documentation`）が消す 1 件（`what does the schema.org spec say about the Person type?`・2/3）は、同ファイルが「境界の緩さとして実在する」と記録した真の overtrigger である。**この決定はその利得を取りに行かない。** 本 Issue が決めたのは生成文を丸ごと採るかであり、外部仕様の 1 文だけを現行の手書き文へ足すかは別の問いとして残る — 足すなら足した後の文でもう一度測ることになる（上の 20/20 は生成文**全体**についての数字であり、1 文だけを移植した文についての数字ではない）。この残りを書かずに済ませると、次に同じ数字を見た人が「真の overtrigger 2 件のうち 1 件が勘定に出てこない」ところから再検討をやり直すことになる。

**クエリ集合は人がレビューした（同 Issue。公式の "bad eval queries lead to bad descriptions" に対する立場の表明として記録する）。** 結果、**positive 10 件がすべて「この Wiki では」「according to this wiki」「based on the wiki」と明示的に枠づけられている**という偏りが見つかった。禁止節はその領域に一切触れないため、「positive を 1 件も失っていない」はこのクエリ集合ではほぼ同語反復である — 禁止節が実際に噛むのは枠づけの無い自然な質問（「quality gate ってどう動くの？」）であり、そこは 1 件も試していない。**したがって 20/20 は、差し替えの根拠として読める数字ではない。** クエリ集合自体を直すかは別の問いであり、ここでは行わない（`dev/skill-trigger-evals/README.md` の「この器で測れないもの」に、公式の指示から外れている旨は既に記録してある）。

**`quiz` / `serve` は引き続き測らない。** 差し替えないと決めた以上 `quiz` の数字は判断に効かず、そのクエリ集合も同じ著者が書くことになるので上の偏りをそのまま持ち込む。再開の条件は上と同じ — クエリ集合に枠づけの無い positive を足したときである。

**クエリ集合は `dev/` に置き、配布物には入れない。** trigger eval のクエリ集合は**標準が置き場所を定めていない**（位置を固定しているのは `evals/evals.json` の方だけ）ため、Skill ディレクトリの外に置いても標準準拠を崩さない。`install.sh` / `dev/scripts/snapshot_push.sh` / `.claude-plugin/plugin.json` はいずれも変更していない。

**測定文脈は「空のディレクトリ」ではない。** `/wikicommit-init` は `CLAUDE.md` を配らないが `.wikicommit/` は配るので、利用者の実際の形は「`.wikicommit/` を持ち `CLAUDE.md` を持たないリポジトリ」である。空ディレクトリで測ると数字が構造的に潰れる（実測で `search` の positive は 30 回中 1 回しか trigger せず、応答は「ここは wiki リポジトリではない」だった）。再現手順とこの環境固有の制約（`claude -p` を 2 つ以上同時に走らせると即座に失敗するため `--num-workers 1` が必須）は `dev/skill-trigger-evals/README.md` にある。

#### `evals/evals.json`（behavioral eval）は入れない（Issue #926）

**理由は「測れない」ではない。「測るべきものは既に決定論的に測っており、残りは `expectations` の器に合わない」である。**

trigger eval と behavioral eval は別の機構である — 前者は `[{"query", "should_trigger"}]` を読み Skill 本体を**実行せず** description が読ませるかだけを見る一方、後者は `evals/evals.json` を読み Skill を実行して `expectations` の通過率を見る。`run_eval.py` は `evals.json` を 1 行も読まない。

このリポジトリは検証を決定論的スクリプトへ押し出す方針（§11.5 のスクリプト委譲パターン・Issue #474）を徹底してきたため、behavioral eval だけが拾える残りが構造的に小さい。実例として、Issue #911 が `wikicommit-generate/SKILL.md` を 831 → 200 行に割ったとき「エージェントが本当に pass ファイルを読んだか」が新しい未検証点になったが、同じ Issue が `record_run.py checkpoint --token` を入れ、**スクリプトが自分でそのファイルを開いて `pass_token` と突き合わせる**形にしたため、LLM を回さずに答えが出る。同型のものが各所にある（`validate_frontmatter.py`・`check_*.py` 群・`review-rules.md` の `rules_version` echo 照合）。

したがって `evals.json` に残るのは決定論的に書けない部分だけであり、それは定義上**生成品質**である — すなわち Issue #669（`chain_of_thought` のレビュー品質）・#798（型名一覧 2 段階化後の Pass 2b の recall）・#892（サブエージェント化の A/B）が求めているものである。**この 3 件は trigger eval でも behavioral eval でも解けない**（`expectations` が測るのは「出力が所定の性質を持つか」であり、#798 が要るのは「ゼロ件が正常な結果である非決定論的判定の recall が落ちたか」で、器が違う）。**標準の手段は別の問題を解く道具であり、3 件の見送りは標準を使っていないことによるものではない。**

### 11.2 Skills 一覧

#### Skill 間の関係

下表の各 Skill がどう繋がるかの全体像。書き込み系の Skill はいずれもローカル書き出しまでで止まり、Git 操作は `wikicommit-merge` に集約される（`wikicommit-schema-propose` のみ例外的に自分で PR を作る）。**このうち `generate` / `merge` / `translate` の 3 本は、人が `/name` と打つ以外にモデルからも起動できる**（Issue #945。無人実行の経路がこの 3 本で閉じるため。他の書き込み系 Skill は `disable-model-invocation: true` を持ち続ける。§11.1 参照）。

```
/wikicommit-init … .wikicommit/ 一式・schema/・ワークフローを生成（最初に 1 回）
                                    ↓
─── 書き込み系（ローカル書き出しのみ・Git 操作なし）────────────────────

  /wikicommit-collect ──呼び出し──→ /wikicommit-generate
    （テーマから候補探索・            （ソース登録 + ページ生成）
      人間が選択したものだけ登録）
  /wikicommit-translate   原文ページ → 翻訳ページ
  /wikicommit-synthesize  既存 entity/ ページ群 → 合成ページ（derived_from）
  /wikicommit-reconcile   ポリシー・型テンプレート・生成ルールの変更後、対象ソースの
                          管理ファイルを status: pending に戻す（生成はしない。
                          次の /wikicommit-generate が既存の収集条件で拾う）
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
  /wikicommit-update         → インストール済み配布物と同期する PR を単独で作成
    （孤児の削除と review ファイルの差分適用はどちらも人間の判断であり、
      PR がその確認の場になる。Issue #713）
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
| `wikicommit-reconcile`（Phase 3.1〜） | `/wikicommit-reconcile --source <path\|url>\|--type <Type>\|--all` | ポリシー（`theme` / `entity-policy.md` / `source-policy.md`）・型テンプレート・生成ルールの変更を既存ページへ届けるため、対象ソースの管理ファイルを `status: pending` に戻す（Issue #874）。**生成は行わない** — 次の `/wikicommit-generate` が既存の収集条件でそれを拾う。ページ 1 枚を決める入力 6 種のうち 3 種（ポリシー・型テンプレート・生成ルール）だけがキューを持たず、それらを読むのはいずれも Pass 2c であり、Pass 2c を通る入口は**ソースの内容が変わったときにしか開かない**（`--regenerate` は Pass 2c を実行しない。Issue #578）。とくにスイッチを **off に戻す**経路は既存のどのコマンドでも到達できない — `status: excluded` のソースは `/wikicommit-generate <url>` が `HASH_MATCH` で「変更なし」と報告し、`<path>` は `SKIP` で Pass 1 にも届かず、引数なしは収集対象外であり、**3 経路とも出力は成功系**である。検出は行わず**人間が対象を宣言する**（変えたのは本人であり、機械が言える新情報はスイッチが on であることの 1 ビットだけ。1 回きりの設定変更イベントに常設のヘルスチェックを置かない）。書き戻しは `set_frontmatter_field.py --require` で現在値を確認してから、人間の承認を経て行う。`check_ingest_freshness.py`（検出 → `status: outdated` → generate が拾う）と同じ形の一般化であり、`wikicommit-generate` は 1 行も変更しない |
| `wikicommit-schema-propose`（Phase 3〜） | `/wikicommit-schema-propose` | `check_schema_coverage.py` で `.wikicommit/schema/` に専用ファイルのない `type:` 値を検出し（Issue #285）、Schema.org 標準型として実在すれば標準型ファイル、実在しなければ `custom/` 型ファイルを新規追加する PR を作成する。ブランチ名 `wikicommit/schema-propose-<Type>` で重複提案を防止。`.wikicommit/schema/` への書き込みが唯一の役目で、既存ファイルの編集・削除は不可。他の PR 作成系 Skill と異なり **auto-merge しない**（人間レビュー必須）。`wikicommit-generate` Pass 2b（Issue #315）がその場での型追加を主経路として担うようになったため、本 Skill の役割は事後の安全網（Pass 2b 以前に生成済みのページの救済等）に変わった |

### 11.3 Skill ディレクトリの構造

各 Skill は `SKILL.md` と、Skill のみが使う `scripts/` サブディレクトリ、そして SKILL.md 本体から出した指示ファイルを置く `references/` で構成する（Issue #911）。この 3 つは Anthropic の Skill anatomy（`scripts/` / `references/` / `assets/`）に揃えたもので、`references/` に置くのは**進行的開示の第 3 層**（必要になったときだけ読む bundled resource）である。

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
│   ├── references/          # SKILL.md 本体から出した指示（読むのは必要になったときだけ）
│   │   ├── pass1-extract.md          # Pass 1 ＋ Pass 2a
│   │   ├── pass2b-type.md            # Pass 2b
│   │   ├── pass2c-entities.md        # Pass 2c
│   │   ├── pass3-generate.md         # Pass 3
│   │   ├── pass4-review.md           # Pass 4
│   │   ├── completion-notice.md      # 実行の終わりに読む（record_run.py end を持つ）
│   │   ├── regenerate.md             # --regenerate のときだけ読む
│   │   └── text-extraction-routing.md # Pass 1 が読む拡張子別ルーティング表
│   └── scripts/
│       └── add_source.py    # 管理ファイルのパス計算・ハッシュ・生成・status 更新
├── wikicommit-merge/
│   └── SKILL.md             # 品質チェック呼び出し + git 操作がメインのため scripts/ なし
└── wikicommit-remove/
    ├── SKILL.md
    └── scripts/
        └── remove_page.py   # frontmatter への status: removed 付与
```

> **`references/` に置く条件は「SKILL.md 本体に無くても実行が壊れない」ことではなく、「入口によっては一度も読まれない」ことである**（Issue #911）。`references/completion-notice.md` はソースを処理する実行なら必ず読むが、Step 0 で止まる実行と `--regenerate` では 1 バイトも読まれない — 出す理由は総量の削減ではなく、**起動のたびに丸ごと載る量**を下げることにある（§11.6 の「訂正（Issue #892）」以降の議論と同じ区別）。
>
> **配布は何も変わらない。** `install.sh` は `find "${skill_src}" -type f` の再帰コピーであり、`.claude-plugin/plugin.json` は Skill **ディレクトリ**を列挙するため、サブディレクトリは自動的に配布に乗る。`tests/test_skill_distribution_list_sync.py` が同期を強制するのは Skill の**一覧**であって Skill 内のファイル構成ではない。
>
> **`tools/check_skill_md_lines.py` の 2 本立ての指標も無改修である** — `instruction_files()` は `rglob("*.md")` なので `references/` 配下も指示の総面積に数え、本体だけが下がる。これは意図した挙動であり、Issue #887 が「本体 ↓ / 総面積 →」を対で読ませるために指標を 2 本にした理由そのものである。
>
> **一方、走査を自前で持っていた 1 本は広げる必要があった。** `tests/test_review_rules_single_source.py` は Skill ディレクトリの**直下だけ**を `glob("*.md")` で歩いており、その理由を「手順をディレクトリ 1 段深くに置く Skill は今は無い」と docstring に明記していた — **`references/` を作ることがその前提を偽にする**。直さなければ、Issue #752 が 1 ファイルへ集約したレビュー規律が `references/regenerate.md` に書き戻されても CI は緑のままになる（そして Regeneration Mode は Pass 4 に到達する）。現在は同じ `check_skill_md_lines.instruction_files()` を import している。**新しく `references/` を使う Skill を足すときは、走査を自前で持つ箇所が他にないかを先に確認する** — 分割が指標や検査の射程を黙って縮めるのは、Issue #887 が `tools/` の 2 本について、Issue #911 がここについて、それぞれ踏んだ同じ形である。
>
> **pass ファイル 5 本は `record_run.py` の `EXPECTED_PASSES` と 1 対 1 である（Issue #911）**。名前空間を新設せず checkpoint のパス名（Issue #797）をそのまま使うため、**`--token` の照合先がファイル名で引ける**。各ファイルの frontmatter が `pass_token` を持ち、`record_run.py` が**自分でディスクからそのファイルを開いて**突き合わせる — 照合先のパスを引数で受け取らないことが第三者性の根拠であり、呼び出し側がファイルを指定できるなら自分で書いたファイルを指せてしまう。`PASS_FILE_DIR` はこの Issue で `passes` から `references` へ変えた（`--token` の消費者がまだ 1 つも無かった、位置を動かせる唯一の窓だった）。
>
> **保証するのは「そのファイルを開いた」ことに徹する。** トークンは内容のハッシュではなく手で置く不透明な値で、ファイルを編集しても上げる必要はない — ハッシュにすると編集のたびに書き換えが要り、忘れると偽の不一致で `checkpoint` が exit 1 になって実行が止まる（誤りの向きが安全側でない）。**ファイルを開いたが従わなかった場合は検出できない**（トークン行だけ grep することは防げない）。これは `review-rules.md` の `rules_version` echo がサブエージェント境界でしか成立しないのと対をなす限界であり、こちらは同一エージェントでもスクリプトが第三者として開くぶんだけ強い。
>
> **指示の総面積は下がらない。** `SKILL.md` 本体は 831 行 → 200 行（162,291 B → 約 29,000 B）になったが、`references/` 配下も `check_skill_md_lines.py` の surface に数えるため合計はむしろ増える（移した先の前置き・TOC と、本体に残るポインタの分）。**目的は総量ではなく「起動のたびに丸ごと載る量」である** — §11.6 の「訂正（Issue #892）」以降の区別そのものであり、進行的開示がサブエージェント化と違って公式ガイダンスが超過時の処方として名指ししている手でもある。
>
> **compaction に対してはこの形のほうが強い。** 再添付されるのは各 Skill の先頭 5,000 トークンだけなので、本体が約 29,000 B に下がった結果**窓が本体のほぼ全体を覆う**（サブエージェント化では親が窓の何倍にもなり、これは成り立たない）。あわせて、checkpoint の打点指示が各 pass のファイルへ移ったため、**打点指示が本体の冒頭から長い実行の末尾まで生き延びる必要がなくなった** — Issue #797 が「分割前は Pass 2 以降の打点指示も 5,000 トークンの外側にある」と既知の限界に挙げていたものが、ここで解消する。
>
> **20,000 B を超える reference ファイルには TOC を置く。** 公式ガイダンスは 300 行を閾値に挙げるが、このリポジトリの指示散文は 1 行 40〜170 B とばらつくため行数は読む量をほとんど言わない（Issue #887 が size 指標に対して同じ訂正を行っている）。

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

スクリプトの置き場所は **ブートストラップと所有権** で決まる：

| 置き場所 | 何が置かれるか |
|---|---|
| `.claude/skills/<name>/scripts/` | `.wikicommit/scripts/` に依存**できない**もの（`wikicommit-init` の 4 本 — そのディレクトリを作る側である）と、その Skill だけのものとして意図的に自己完結させたもの |
| `.wikicommit/scripts/` | それ以外。リポジトリで Git 管理されるため全 Skill から参照でき、共有モジュール（`_wikilink.py` / `_frontmatter.py` / `_schemaorg_vocab.py`）を import できる |

> **この表は「呼び出し元が 1 Skill なら Skill 内・複数なら共有」ではない — かつてそう書かれていたが、実態と食い違っていた（Issue #947）**: 共有側を全数えすると、**呼び出し元が 1 Skill だけの共有スクリプトが 14 本**ある（`wikicommit-status` のみ 12・`wikicommit-fix` のみ 1・`wikicommit-generate` のみ 1）。最後の 1 本が `reconcile_ingest_status.py` で、**同じ Skill から、Pass 4 の直後に**呼ばれる。旧ルールが例外として扱っていた形は、例外ではなく多数派だった。
>
> **Skill 内が硬い制約なのは `wikicommit-init` の 4 本だけである。** あれらは `.wikicommit/scripts/` を**作る**側なので、そこに依存できない。残る 3 本の理由は同じ強さを持たない:
>
> | Skill 内スクリプト | 理由 | 状態 |
> |---|---|---|
> | `add_source.py` | frontmatter を自前パースし真に自己完結だが、**そうする理由はどこにも書かれていない** | 慣行 |
> | `remove_page.py` | 下記の自己矛盾した理由 | 崩れている |
> | `resolve_source_cache_path.py` | **`sys.path.insert(0, ".wikicommit/scripts")` で `_frontmatter` を import している** | 反例 |
>
> **`remove_page.py` に書かれていた複製理由（「サブプロセスとして実行され、呼び出し元の cwd から `.wikicommit/scripts/` が解決できるとは限らない」）は成立しない。** 全 SKILL.md の呼び出しは `python .claude/skills/<skill>/scripts/<x>.py` という**リポジトリルート相対**であり、cwd がルートでなければ Python が起動する前にコマンド自体が落ちる — **cwd への同じ仮定を、同じコマンドラインの 1 語手前で既に置いている**。理由の文言は訂正したが、**複製そのものは残してある**（誤った理由を正すことと、それに基づいて書かれたコードを書き換えることは別の判断であり、後者は独立に決められる）。
>
> **判断基準は「写しが何本増えるか」である。** `build_onehop_context.py`（Issue #947）は `WIKILINK_RE`・エンティティ / view 走査・`parse_wiki_path`・frontmatter 読み・クロス言語解決一式を要し、Skill 内に置いて import を避けると **Issue #677 が集約したばかりのものの 3 つ目の写し**を作ることになる。Skill 内に置いて import する形は、共有側に置くのと結果が同じで木をまたぐ import が 1 本増えるだけである。したがって共有側に置いた。
>
> **版ずれ（Issue #930）は判定材料にならない。** どちらの置き場でも効き、どちらも #930 が危険とした「静かに変わる」形を含む — Skill 内 + import で版ずれが `ImportError` になるのは symbol が消えたか改名されたときだけであり、古い `_wikilink.py` が `WIKILINK_RE` を**名前はそのままに別の文字クラスで**持っていれば import は通って結果だけが黙って変わる。共有側には `wikicommit-generate` Step 0 の `check_distribution_freshness.py --only .wikicommit/scripts` という検出が既にあるが、非ブロッキングの警告であり置き場所を決めるほどの差にはならない。

#### Skill 内スクリプト（`.claude/skills/<name>/scripts/`）

決定論的なファイル操作・パス計算・YAML 編集など、LLM に任せると再現性が下がる操作を担う。

| Skill | スクリプト | 役割 |
|---|---|---|
| `wikicommit-init` | `scripts/init.py` | ディレクトリ構造作成・`templates/` からのファイル展開 |
| `wikicommit-init` | `scripts/print_next_steps.py` | 「次のステップ」案内文の組み立て（Issue #350。3 変種のほぼ同一な散文を SKILL.md に重複させないため） |
| `wikicommit-init` | `scripts/_root_outputs.py` | ルート生成物の宣言的な一覧。上記 2 スクリプトが共有する単一の情報源で、`init.py` の verbatim コピーと `print_next_steps.py` の `git add` 案内の両方をここから組み立てる（Issue #642。下記コールアウト参照） |
| `wikicommit-generate` | `scripts/add_source.py` | 管理ファイルのパス計算・SHA-256・生成・status 更新・ソースの同一性判定（URL: Issue #572／ファイルパス: Issue #573）・`source.license` の初期値決定（既知ドメイン対応表と `--license`。Issue #558。`docs/DesignDoc-data.md` §4.3）・登録時の partial extraction 通知（`partial_extraction_note()`。Issue #715 — 静的取得で本文は取れるが一部が黙って落ちる URL 形〈GitHub の Issue / PR スレッド〉を、ブロックせず登録時に一度だけ知らせる。ShareAlike 通知と同じ形）。`--license-for-url` は同じ対応表を引くだけの読み取り専用モードで、**この 1 モードに限り `wikicommit-collect` からも呼ばれる**（Issue #646。下記コールアウト参照）。`--check-path-cache` / `--path-cache-path` は `type: path` の抽出テキストキャッシュの有効性確認と置き場の印字（Issue #885。前者は read-only で `source.hash` に一切触れない — `type: path` のそれは生ファイルのハッシュであり、キャッシュのハッシュで上書きすると `check_ingest_freshness.py` の鮮度判定が壊れる。`docs/DesignDoc-pipeline.md` §6.1） |
| `wikicommit-remove` | `scripts/remove_page.py` | frontmatter への `status: removed` / `removed_at` 付与 |
| `wikicommit-ask` | `scripts/resolve_source_cache_path.py` | `--include-source`（Issue #470）専用。**`--type url` / `--type path` の 2 モードを持つ**（後者は Issue #885 で追加）。`--type url` は `sources[].url` から `.wikicommit/source/url/` 配下を実走査して一致する ソース管理ファイルを特定し、その実パスから scratch-path を導出して `.wikicommit/.cache/ingest-fetch/` 内のキャッシュファイルを解決する。`--type path` は同じ実走査を `.wikicommit/source/path/`（`source.path` で照合）に対して行い、`.wikicommit/.cache/extract-path/` 内の**抽出テキスト**キャッシュを解決する — こちらは管理ファイルの相対パスを**末尾の `.md` ごと**使う（`raw/paper.pdf.md`。Issue #573 の衝突回避をそのまま継ぐため。落として付け直すとあの衝突が戻る）。`type: path` 側を足した理由は、同 `--include-source` がそれまで生ファイルを Read しており、`.docx`/`.pptx`/`.xlsx`/`.epub`/スキャン画像では読めないテキストになるという限界を自ら抱えていたことにある（キャッシュがあればそこが解消し、無ければ従来の限界に戻る）。`.md`/`.txt` のソースはキャッシュを持たないため常に後者の経路になる（`docs/DesignDoc-pipeline.md` §6.1）。**両モードとも、キャッシュを探す前に管理ファイルの `status` を見る** — `retracted`（Issue #737）なら `RETRACTED: <識別子> (<管理ファイルのパス>)` を印字して **exit code 2** を返す（Issue #918）。exit 1 に畳めないのは、あちらが既に 2 つの意味を畳んでおり、かつ `type: path` の経路では呼び出し側が exit 1 を**生ファイルを読む**ことで答えるためで、キャッシュを持たない取り下げ済みソースが素通りする。順序も同じ理由で、後に置くと「たまたまキャッシュがあるソースだけ」を守ることになる。読むのは `retracted` だけである（他の `status` 値は取り込み処理の状態であって文書への評価ではない）。URL から `add_source.py` の `url_to_filename()` を再計算する方式は Issue #191 以前の旧フラット命名の管理ファイル（自動移行されない）で実際の scratch-path と食い違うため、実ファイルを走査して特定する方式を採る。**登録側の `add_source.py` も同じ走査方式に移行した** — `process_url()` が Issue #572 で（`find_mgmt_file_for_url()`）、`process_file()` が Issue #573 で（`find_mgmt_file_for_path()`。`type: path` 側は導出が拡張子を捨てていたため `paper.pdf` と `paper.docx` が衝突し、しかも `SKIP` で止まらず既存管理ファイルを `status: outdated` に書き換えていた）— それまでは導出ファイル名の存在有無を同一性キーにしていたため、クエリ文字列で区別される URL（YouTube の `?v=` 等）が同じ名前に解決されて未登録のまま `SKIP`／別 URL に対する `RECHECK` を返していた。参照側だけが `source.url` を正としていた非対称を解消したもので、2スクリプトは同じ「ファイル名を再計算せず `source.url` で照合する」規約を共有する（実装は共有せず各自に持つ — `add_source.py` は `.wikicommit/scripts/` からの import を一切持たない自己完結スクリプトである。なお `remove_page.py` の複製も長らく同じ理由づけを掲げていたが、そちらの理由は成立しないことが分かっている〈Issue #947。本節冒頭のコールアウト〉ため、根拠として引かない） |

#### 共有スクリプト（`.wikicommit/scripts/`）

`/wikicommit-init` が生成し、リポジトリで Git 管理される。複数 Skills から呼ばれる。

| Skill | 委譲するスクリプト | 理由 |
|---|---|---|
| `wikicommit-merge` | `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_orphans.py` | 品質ゲートとして変更ファイル全件を網羅的に検証するため |
| `wikicommit-review` | `validate_frontmatter.py` | frontmatter 補完前の検証に使う。経路A・経路Bいずれのページに対しても使用する（Issue #313 — 経路Aのページも `wikicommit-review` の対象になった） |
| `wikicommit-status` | `check_orphans.py` / `check_wanted_pages.py` / `check_expires.py` / `check_ingest_freshness.py` / `check_translation_status.py` / `check_derivation_freshness.py` | 全ファイル走査・有向グラフ解析・日付比較・翻訳陳腐化検出／未翻訳検出・合成ページ陳腐化検出を正確に行うため。`check_wanted_pages.py` は Type セグメント取り違え（`TYPE_MISMATCH`）の分離も担う（Issue #563） |
| `wikicommit-status` / `wikicommit-generate` / `wikicommit-merge` | `check_distribution_freshness.py` | インストール済みの配布物がテンプレートと一致しているかを全件走査で突き合わせるため（Issue #712）。後 2 者は Step 0 で `--only .wikicommit/scripts` に絞って呼び、**テンプレート側の写しを実行する**（Issue #930。`.claude/skills/` と `.wikicommit/scripts/` は別々のコマンドで更新されるため、古いかもしれない側から検出器を呼ぶと検出器自身が版ずれで落ちる。止めずに警告するだけで、対象を 2 Skill に絞る基準も含め `docs/DesignDoc-ScriptSpec.md` の該当コールアウト参照）。`.wikicommit/scripts/`・`quartz-plugins/`・2 つの workflow・`*.cjs` は WikiCommit 自身の配布ペイロードであり再 init で更新されるが、**そのリポジトリが更新を要するかを知る手段が無かった** — パイロット 3 件が同一の旧版を抱えていたことは、clone して手で突き合わせて初めて分かった。分類（`update` 列）は `_root_outputs.py` が唯一の情報源で、`init.py` のコピーと`print_next_steps.py` の `git add` 案内も同じ列から導かれる |
| `wikicommit-status` / `wikicommit-merge` | `check_review_coverage.py` | 前者はレビュー記録（`.wikicommit/review/`）を全ページ走査で突き合わせ、集計・未レビュー・抜取候補・失効を出すため（Issue #750）。後者は `--discarded-reason` を呼び、生成失敗トラッキング Issue の理由欄を `result: discarded` の最新記録から取るため（Issue #969 — Pass 4 step 7 が `## Failure Reason` を `partial` 分岐で削除するため、管理ファイルだけを読むと理由が構造的に必ず `unknown` になる）。`record_review.py` が書いたものを読む唯一の主体であり、これが無ければ記録ツリーは常に空のまま残る受け皿になる（Issue #553）。閾値も自動化も持たない — `RISKY:` / `COVERAGE:` を人が読んで `--regenerate` を叩けばループは閉じる |
| `wikicommit-status` | `check_run_records.py` | 実行 1 回を単位とする記録を読み戻すため（Issue #790）。既存の記録層はすべて成果物（ファイル・ソース・ページ・レビュー）を単位としており、**実行が完走したか**・**どれだけかかったか**を答えられる層が 1 つも無かった。とくに前者は、途中で死んだ実行が残す状態が Issue #567 の「まだ順番が来ていない滞留」と見え方が同じで、ガード C（Issue #574）・`rules_version` 不一致（Issue #752）に至ってはファイルを 1 つも変えずに止まるため git に痕跡がゼロになる。`record_run.py` が書いたものを読む唯一の消費者であり、これが無ければ記録ツリーは常に空のまま残る受け皿になる（Issue #553） |
| `wikicommit-status` / `wikicommit-review` / `wikicommit-fix` | `check_retracted_sources.py` | 前者は人間が取り下げたソース（`status: retracted`）を `sources[]` に持つページを全ページ走査で列挙するため（Issue #737）。後 2 者は `--list` を呼び、ソース文書を取得する**前に**取り下げ済みのものを証拠集合から外すため（Issue #928 — この 2 経路は `resolve_source_cache_path.py` を経由せず直接取りに行くので、Issue #918 のガードが構造的に届かない。とくに `wikicommit-review` は「人が信用できないと判断した文書に忠実であること」を根拠にページを通していた）。新しいスクリプトを作らずここに足したのは、判定（識別子 → 管理ファイル）が既にこのファイルにあり、同一性キーの規則〈Issue #572 / #573〉の写しを増やさないためである。取り下げは再登録・再取り込みを構造的に止めるが、既に書かれたページには何も起こらない — その差を埋める経路が他に無い。**行動ではなく報告に留める**（`review_status` を戻す案は Issue #724 の規範と噛み合わず、戻しても何が失われたかは伝わらない）。どの経路〈`--regenerate`〈Issue #744 が取り下げたソースを落として作り直す挙動を入れた〉/ `/wikicommit-fix` / `/wikicommit-remove`〉を採るかは人間の判断であり、各所見に「そのページに残っている他のソースの件数」を添えることがその判断材料になる |
| `wikicommit-status` | `check_actions_pr_permission.py` | "Allow GitHub Actions to create and approve pull requests" 設定の再確認を `gh api` 経由で決定論的に行うため（Issue #478。この委譲先だけが `.wikicommit/` 配下の走査ではなく `gh` CLI 呼び出しを要する） |
| `wikicommit-status` | `check_schema_coverage.py` | `type:` 値に対応する専用スキーマファイルが無いページ（＝ `default.md` へのフォールバック下で生成され、その型の `granularity`・`properties:` 候補・本文テンプレートが適用されていないページ）を全ページ走査で継続的に可視化するため（Issue #575。`wikicommit-generate` の Completion Notice は生成時の1回きり、`validate_frontmatter.py` の WARNING は変更ファイルにしか届かず、スキーマファイルを後から動かした場合の検知経路が無かった） |
| `wikicommit-status` | `check_property_wikilink_reinforcement.py` | `.wikicommit/schema/` 全型テンプレートの `properties:` キーについて Schema.org RANGE 分類（`check_schema_org_type.py --show-range` と同じロジック）を機械的に突き合わせるため（Issue #539。Issue #523 が手動監査で発見した非対称性の再発検出を自動化） |
| `wikicommit-status` | `check_schema_files.py` | 書かれた schema ファイル自体を検証するものが 1 つも無かったため（Issue #889）。`.wikicommit/schema/` に置かれるファイルの出所は 3 系統（配布テンプレート・実行時に Skill が書いた型・人間の手書き）あり、**CI の 4 本のテストが守れるのは 1 つ目だけ**である一方、schema ファイルは書かれた後どの Skill も編集できない（narrow exception は追加のみ可）。道具は全部あった — property の検証は `check_schema_org_type.py`、祖先の解決は `_schemaorg_vocab.py`、`provenance` を読む関数は `check_installed_type_usage.py` にある — 使う主体がいなかっただけである。`check_property_wikilink_reinforcement.py` とは同じディレクトリを走査するが問う内容が逆で、あちらは「テンプレートがもっと述べるべきか」（望ましさ）、こちらは「そもそも動く形で書かれているか」（壊れている）。`wikicommit-merge` の品質ゲートには入れない — 壊れた schema ファイルが 1 つあるだけで既存リポジトリがマージ不能になり、しかも直せるのはどの Skill も触れないファイルを開く人間だけである |
| `wikicommit-status` | `check_recurring_characters.py` | `properties.character` のプレーンテキスト値を全ページ横断で集計するため（Issue #560）。`ShortStory.md`/`Book.md` が下す「この登場人物は独立ページに値するか」の判断を後から見直す仕組みが無く、しかも `check_wanted_pages.py` は WikiLink しか読まないためプレーンテキストの名前は wanted page として計上すらされない（Issue #318 の限界が `properties:` の値にも同じように効く）。作品をまたぐ再登場は 1 回の生成実行の中からは見えないため、事後の横断集計でしか拾えない |
| `wikicommit-status` | `check_unlinked_entity_mentions.py` | エンティティ型を range に持つ `properties:` キーの値を既存ページと突き合わせるため（Issue #561）。`check_wanted_pages.py` の鏡像 — あちらが「リンクはあるが実体がない」を見るのに対し、こちらは「実体はあるがリンクされていない」を見る。生成時の判断が取り込み順序に引きずられて割れても、`action: update` はそのページ自身のソースが再 ingest された時にしか起きないため自然には回復しない |
| `wikicommit-status` | `check_installed_type_usage.py` | インストール済みスキーマファイルと実際の `type:` 使用状況を全ページ走査で突き合わせるため（Issue #565）。`check_schema_coverage.py` の対 — あちらは「使われている型にファイルが無い」を見るが、逆（ファイルが在るのに使われない）はどのゲートにも掛からなかった。祖先型は常に技術的に正しいため、インストール済みの具体型が選ばれなくても品質チェックはすべて通る |
| `wikicommit-status` | `check_self_referential_tags.py` | ページ自身の `title`／`type` を繰り返すだけのタグを全ページ走査で検出するため（Issue #571）。Issue #275 が散文で明示的に禁じたにもかかわらず再発しており、生成時の指示だけに依存して検出手段が無いルールは drift する。`title`／`type` との文字列比較で決定論的に判定できる |
| `wikicommit-search` | `search_index.py` | FTS5 trigram インデックスの構築・bm25 ランキング・スニペット生成には SQLite クエリが必要なため（Phase 3〜。Grep ベースの Phase 1 実装から移行済み） |
| `wikicommit-translate` | `check_translation_status.py` / `rebuild_index.py` | 前者は一括モードの対象件数（`UNTRANSLATED` + `STALE`）算出に全ページ走査・翻訳有無判定を正確に行う必要があるため。後者は `index.md` 更新を「全ソース/ペア処理後に1回」という手順としてLLMの記憶に委ねていたことによる更新漏れ対策（Issue #406。`wikicommit-generate` と共有） |
| `wikicommit-synthesize` | `build_survey_view.py` | 引数なしの俯瞰モード（Issue #586）で、Wiki 全体を1つのコンテキストに収まる縮約ビューへ落とすため。「全体を俯瞰する」以上、走査の網羅性そのものが機能の前提であり、SKILL.md のプローズ（grep の羅列）に委ねると取りこぼしが黙って結果を損なう。スクリプトは判断を行わない — 縮約ビューから着眼点を選ぶのは LLM の仕事で、そちらは本質的に非決定論的 |
| `wikicommit-synthesize` | `rebuild_index.py` | 合成ページを書き出しただけでは view インデックス（言語別。Issue #675）に載らず、合成ページはどのソースからも生成されない（`derived_from` のみを持つ）ため `wikicommit-generate` が走る契機自体が無いリポジトリでは無期限に未掲載のまま残るため（Issue #547）。他 2 Skill と異なり、書き出した 1 ディレクトリのみを引数に指定して呼ぶ（`.wikicommit/view/<lang>`） |
| `wikicommit-generate` / `wikicommit-review` / `wikicommit-synthesize` | `.wikicommit/review-rules.md`（スクリプトではなくデータだが、委譲の構造は同じ） | レビュー規律を 3 箇所で言い直さないため（Issue #752）。移すのは「何を検査するか」だけで、段取りは各 Skill に残る。`_root_outputs.py` に `update: overwrite` で登録し、リポジトリ側からの編集を許さない — 許すと Wiki が自分のレビューを黙って弱められる |
| `wikicommit-init` / `wikicommit-collect` / `wikicommit-generate` / `wikicommit-schema-propose` | `.wikicommit/schema-authoring.md`（同じくデータ） | 型ファイルの書き込み手順を 4 箇所で言い直さないため（Issue #886。§11.5 の「複数 Skill に重複した手順は共有データファイルへ一本化する」の 2 例目）。移すのは手順だけで、**判定**（提案の閾値・承認 UX・`provenance` の値）は各 Skill に残る — 4 経路の役割分担は証拠の強さの違いによるものであり、そこを統合すると「ソースを読む前に断定できるか」と「ソース本文から断定できるか」が同じバーになる。配布は `review-rules.md` と同形（`update: overwrite`）。読むのは**候補が承認された時点**であり、ファイルが無い場合はその候補だけを却下して報告する（実行は止めない） |
| `wikicommit-generate` / `wikicommit-translate` / `wikicommit-synthesize` / `wikicommit-merge` | `record_run.py` | 実行 1 回につき 1 ファイルを開いて閉じるため（Issue #790）。対象をこの 4 つに絞る基準は「途中で死んだときに、中途半端な状態と『まだ順番が来ていない』状態が区別できなくなるもの」であり、`fix` / `remove`（単発かつ小さく差分そのものが結果）・`collect`（対話前提）・読み取り専用 Skill（状態を変えない）は入らない。開始と終了の打刻を LLM の記憶に委ねる形だが、**忘れても壊れない** — 開始があって終了が無い記録が、そのまま「完走しなかった」の答えになる（Issue #750 の `page_content_hash: ""` と同じ形）。記録は git で追跡しない点だけが Issue #750 と逆で、ローテーションが可能になり `wikicommit-merge` が無改修で済む |
| `wikicommit-generate` / `wikicommit-review` / `wikicommit-synthesize` / `review-issue-close-sync.yml` | `record_review.py` | レビュー 1 件を不変ファイルとして書き出すため（Issue #750）。判定は LLM が下し、ファイル手術はスクリプトが行う（Issue #474）。`source_quote` の除去・`page_content_hash` の計算・`reviewed_sources` の収集を呼び出し側の指示遵守に委ねないことが要点で、とくに `page_content_hash` は `reset_review_on_content_change.py` の 6 フィールド無視リストを **import** して使う（複製すると drift し、drift は「誤った鮮度を黙って報告する記録」として現れる） |
| `wikicommit-generate` | `check_schema_org_type.py --list-type-names` / `check_schema_org_type.py --describe` / `check_schema_org_type.py --list-installed-hierarchy` / `check_schema_coverage.py` / `rebuild_index.py` / `check_extraction_quality.py` / `reconcile_ingest_status.py` | 前 2 つと `check_schema_coverage.py` は Pass 2b の型の要否判断用で、`--list-type-names` が約 933 型の**名前だけ**をプリロードし、そこから絞り込んだ候補の説明文を `--describe` が引く（Issue #315。旧 #285 の `better_type_candidate` 検出用途を置き換え。2 段階にしたのは Issue #798 — この一覧が果たしているのは想起であって存在保証ではなく〈実在は候補承認後の `--type` が決定論的に確かめる〉、想起には誰も検討していない 928 型の説明文が要らないため。147 KB → 約 14 KB）。あわせて未スキーマ化 type 文字列一覧で収束を誘導する。`--list-installed-hierarchy` は Pass 2c にインストール済み型同士の祖先／子孫関係を渡すため（Issue #565。祖先型は常に当てはまるため、関係を示さないと粗い型が既定で選ばれる — 語彙から決定論的に導ける情報なのでモデルの記憶に委ねない）。`rebuild_index.py` は全ソース処理後の `index.md` 更新を決定論的スクリプトに委譲し、長い多段生成の末尾でLLMが更新を忘れるリスクを排除するため（Issue #406）。`check_extraction_quality.py` は「非空だが無意味」な抽出結果（既知JS-shellドメイン・低情報密度）および「取得能力の不足による partial extraction」（Issue #574）の判定を、LLMの主観的判断ではなく決定論的ロジックに委ねるため（Issue #425。ただし判定結果の扱いは3ガードで異なり、既知JS-shellドメインはそのソースをブロック、取得能力の不足は処理全体を停止、低情報密度は人間に続行可否を確認する警告である — Issue #562・#574）。`reconcile_ingest_status.py` は `status: pending` の管理ファイルのうち内容が既に公開ページの `sources` に使われているものを検出・是正するため（Issue #474。詳細は本節末尾の callout 参照） |
| `wikicommit-generate` | `build_onehop_context.py` | Pass 4 の check 8 が要る 1 ホップ近傍を、散文ではなくスクリプトで組み立てるため（Issue #947）。指示は片側にしか書かれておらず、outbound 側を埋めた使い捨ての正規表現が `-` を含まない文字クラスを持っていたため、Issue #193 のケバブケース slug に**完全に不一致になった** — **例外にならず集合が静かに縮むだけ**で、実測では 27 件中 24 件で内容が変わった。`WIKILINK_RE` は `_wikilink.py` にあり 4 本のスクリプトが既にこれを使っている（Issue #474 が名指しした形そのもの）。抽出だけでなく 3 つの skip 判定・クロス言語フォールバック・outbound 優先の dedup・5 件上限まで委譲する — いずれも**集合を縮める操作**であり同じ性質を持つため。`--regenerate` も同じスクリプトを呼ぶ |
| `wikicommit-update` | `check_distribution_freshness.py` / `rebuild_index.py` / `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_orphans.py` | 前者はドリフト検出そのものを担い（Issue #712 で`wikicommit-status` と共有する共通スクリプトとして新設済み。呼び出し元が 2 Skill になるため §11.5 の規則どおり`.wikicommit/scripts/` に置かれている）、残りは更新後の検証に使う。`wikicommit-init/scripts/init.py` も`--no-overwrite`（`overwrite` の適用）・`--update-version`（版の刻印）・`--add-config-keys`（欠落キーの加算）の3 経路で呼ぶ — こちらは Skill 内スクリプトへの越境呼び出しにあたるが、`add_source.py --license-for-url`（Issue #646）と違い**同じ Skill が持つ設定ファイル生成のロジックそのもの**であり、複製すると `_root_outputs.py` の `update` 列が唯一の情報源であるという Issue #712 の前提が崩れる |
| `wikicommit-reconcile` | `set_frontmatter_field.py` | 管理ファイルの `status` を `pending` に書き戻す（Issue #874）。新しいスクリプトを足さずに済むのは、同スクリプトがパス非依存（frontmatter ブロックを持つ任意のファイルを受ける）であり、`--require KEY=VALUE` で現在値を確認してから書く冪等な経路を既に持つためである。**検出用のスクリプトは新設しない** — ポリシー変更の判定器は Pass 2c 自身であり、もう一度呼べないことだけが問題だった |
| `wikicommit-schema-propose` | `check_schema_coverage.py` / `check_schema_org_type.py` | schema/ 未カバー type の網羅的集計、および型・プロパティが Schema.org 語彙に実在するかの決定論的検証（オフライン・遅延生成、Git管理下の`.wikicommit/schemaorg-vocab.json`。Issue #319）が必要なため（Issue #285） |
| `wikicommit-generate` / `wikicommit-collect` | `read_policy.py` | ポリシーファイルの本文が「配布時の記入例のままか」は配布した本文が手元にある以上バイト比較で決まるのに、2 つの SKILL.md の 4 箇所に散った同じ散文が LLM にそれを判定させていたため（Issue #844。Issue #474 が名指しした「決定論的に判定できる操作を instruction にする」形）。しかも両ファイルの記入例はすべて除外を促す内容なので、誤適用は常に「書かれるはずだったものが書かれない」方向にしか働かない。スクリプトは記入例と HTML コメントを落とすだけで、散文の解釈は引き続き LLM が行う |
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
> **印字される `git add` の既定は `-A` であり、この一覧はその横に置くフォールバックになった（Issue #842）**。`git add` は存在しない pathspec を渡されると**コマンド全体を中断する**（実測: exit 128・staged 0 件）一方、印字される列挙には `.gitmodules` と `quartz` という**誰も生成しないパス**（`origin="submodule"`。ユーザーが `git submodule add` する）が常に載っていた。つまり**印字されたコマンドは、印字された状態のリポジトリでは verbatim に実行できない** — `tests/test_smoke_local.py` がその 2 パスを取り除いてから add することで通っていたことが、その証拠である。Quartz を後回しにしたユーザーが案内どおり打つと基盤ファイルのコミットが丸ごと落ち、Issue #86 がこのステップを足して防いだ状態に戻る。`.gitignore` は `init.py` 自身が書く（`--quartz` では Quartz セクションを追記する）ため、**新規リポジトリでは列挙と `-A` の結果が一致する**。
>
> **列挙が本当に効く場面は既存リポジトリへの後入れ 1 つだけ**（§3.1 の `docs/DesignDoc-data.md`）なので、そこへ降ろした — 既定を `-A` にし、「WikiCommit と無関係な未追跡ファイルがあるなら `git status --short` で確認するか、以下を個別に stage する」という注記として `build_git_add()` の出力をそのまま再利用する。副次的に `condition="vocab_cache"` と `in_git_add=False`（`package-lock.json`）は既定の経路では不要になるが、**どちらも機構ごと残す** — 注記側の列挙では依然として abort しうるうえ、後者は「これは決定であって漏れではない」を記録するフィールドであり（Issue #556 の再発防止）、削るとその記録が失われる。
>
> **`-A` が列挙と一致するのは「この Wiki のために作ったリポジトリ」に限る**。`.gitignore` は `_root_outputs.py` 上 `update="review"`（＝`always_skip_existing`）であり、**既にあるリポジトリに後入れした場合 `init.py` はこれを書かない**（`--quartz` の Quartz セクションを追記するだけ）。したがって `node_modules/`・`.wikicommit/.cache/`・`.wikicommit/run/` はignore されておらず、同じ案内の 1 番目が走らせる `npm install` の後に `-A` を打つと `node_modules/` が丸ごとコミットに入る。`print_next_steps.py` はリポジトリではなくフラグだけを受け取る設計（`--gitignore-skipped` に相当するフラグは無い）ため、分岐ではなく**注記で伝える** — 併せて、後入れ向けに残した列挙が `.gitmodules` / `quartz` を含む以上そちらは依然 abort しうることも、その場で明示する（`wikicommit-update` SKILL.md が同じ理由で同じ注記を出している）。
>
> **`tests/test_smoke_local.py` の Issue #556 回帰テストは検証先を注記側の列挙へ向け直した**。既定が `-A` になると「案内どおり add した後に未追跡ファイルが残らない」は定義上つねに真であり何も守らないが、ドリフトが残りうるのは列挙の側なのでテスト自体は価値を保つ。既定が `-A` であること自体は別のテストが固定する。
>
> **submodule の扱いは実測した**。作業ツリーが汚れているだけ（submodule 内に未追跡ファイルがある）でポインタが動いていない場合、リポジトリルートの `git add -A` は**何も stage しない**。ポインタが実際に動いている場合のみ `quartz` が stage される — 初回コミットではそれが望ましい側である。
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
                                     ├── update
                                     ├── generate（Step 0。--only .wikicommit/scripts）
                                     └── merge   （同上。呼ぶのはテンプレート側の写し）
check_retracted_sources.py ──────────┬── status     ※source/ と entity/・view/ を突き合わせる
                                     ├── review     （--list。ソース取得の前）
                                     └── fix        （同上）
check_review_coverage.py ────────────┬── status   ※.wikicommit/review/ を読む唯一の消費者
                                     └── merge   （--discarded-reason。生成失敗 Issue の理由欄）
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
set_frontmatter_field.py ────────────┬── review      （reviewed_by を落とす）
                                     └── reconcile   （status を pending へ戻す。Issue #874）
check_extraction_quality.py ─────────┬── generate（check-domain + check-density）
                                     └── collect （check-domain のみ）
read_policy.py ──────────────────────┬── generate（Step 0 / Pass 2c 用の方針読み込み）
                                     └── collect （Step 2.5）
check_schema_coverage.py ────────────┬── generate（Pass 2c の収束誘導）
                                     └── schema-propose（検出源）
check_schema_org_type.py ────────────┬── generate（Pass 2b/2c/3）
                                     └── schema-propose
build_survey_view.py ────────────────┬── synthesize（俯瞰モード）
                                     └── collect （Step 3.5 の俯瞰）
build_onehop_context.py ───────────────── generate（Pass 4 / --regenerate。check 8 の近傍）
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
wikicommit-ask/scripts/resolve_source_cache_path.py   ※--include-source 専用（--type url/path）
```

> **`add_source.py --license-for-url` — Skill 内スクリプトへの唯一の越境呼び出し（Issue #646）**: 本節冒頭の置き場所の規則（呼び出し元が 1 Skill なら `.claude/skills/<name>/scripts/`、複数なら `.wikicommit/scripts/`）に対する、意図的な 1 件の例外である。`wikicommit-collect` が `wikicommit-generate` の Skill 内スクリプトを直接呼ぶ。
>
> **`.wikicommit/scripts/` へ移さなかった理由**: 移すべき実体は `KNOWN_SOURCE_LICENSES`（登録可能ドメイン → SPDX 識別子の対応表）とそれを引く 2 関数だが、`add_source.py` は `.wikicommit/scripts/` からの import を一切持たない自己完結スクリプトである（上表の `resolve_source_cache_path.py` の行が述べる既存の制約。**慣行であって硬い制約ではない** — その区別は本節冒頭のコールアウト〈Issue #947〉を参照）。したがって共有モジュール化には (a) この制約を壊す、(b) 対応表を 2 か所に複製する、のどちらかが要る。(b) は「登録時に記録される値」と「候補提示で見せる値」が食い違いうるという、この機能が防ごうとしているものそのものを作り込む（食い違ったときの見え方が最悪 — 人間は提示された条件で承認し、記録されるのは別の条件になる）。(a) は 1 モードのために既存の設計制約を壊す。
>
> **代わりに読み取り専用の照会モードを足した**。`--license-for-url <url>` は対応表を引いて `LICENSE: <id>`／`LICENSE: <id> (share-alike)`／`UNKNOWN: <url>` のいずれかを出し、常に exit 0 で、何も書き込まない。対応表は 1 つのまま、呼び出し側は 1 行のコマンドで済む。`tests/test_add_source.py` は照会結果と、同じ URL を実際に登録した管理ファイルの `source.license` が一致することを検証しており、2 経路の drift を CI で止める。
>
> **越境そのものの前例はある** — `wikicommit-collect` Step 8 は既に `wikicommit-generate` の SKILL.md（Step 0）を名指しで実行しており、この 2 Skill の間には元から依存関係がある。本 Issue が足したのは新しい依存ではなく、その依存の粒度が SKILL.md からスクリプト 1 本へ下りたことである。
>
> **候補提示は「不明」を書かない**（Issue #646 の 2 つ目の完了条件）。対応表が持つのは、そのサイトが自サイトのコンテンツ全体に対して明示しているライセンスだけ（初期値は Wikimedia 系 8 ドメイン）なので、実際の候補の大半は `UNKNOWN` になる。ほぼ全行に「ライセンス: 不明」が付くと読み手はその行を読み飛ばすようになり、`wikicommit-collect` は同じ理由（ほぼ常に空になるステップを独立させない）で Type Proposal を Step 7 に畳み込んでいる。代わりに候補一覧の前置きに 1 度だけ「ライセンスは確認済みのサイトにのみ表示され、無表示は『条件を把握していない』であって『制約が無い』ではない」と書く。`sources[].license` が不明をフィールドごと省略して表す（空文字列で表さない）のと同じ線引きを、提示側でも保つ。

**スクリプト委譲が不要な Skills**: **現在は 1 つも無い**。この表はかつて `wikicommit-fix`（Issue 読み込み → LLM 修正案生成 → `wikicommit-merge` 呼び出し）だけを挙げていたが、同 Skill はその後 `reset_review_on_content_change.py`（Issue #724）を呼ぶようになり、Issue #928 で `check_retracted_sources.py --list` が加わって空になった。**表ごと消さずに残すのは、この分類が誤りだったからではなく、そこに居られる Skill が実際に居なくなったからである** — 次に「この Skill はツールだけで足りる」と判断する人が、同じ検討を一からやり直さずに済むよう、その判断が成り立たなくなった経緯を残す。書き込み系の Skill が決定論的な状態の読み書きを 1 つも持たずに済むことは、結果として無かった。

SKILL.md での記述例（`wikicommit-status`）:

```markdown
## 処理フロー

1. `python .wikicommit/scripts/check_orphans.py` を実行し、孤立ページ数を取得する
2. `python .wikicommit/scripts/check_expires.py` を実行し、expires_at 期限切れページを取得する
3. `python .wikicommit/scripts/check_ingest_freshness.py` を実行し、outdated な管理ファイルを取得する
4. `.wikicommit/source/` を走査して `status: pending` の管理ファイル数を集計する
5. 結果を整形して表示する
```

#### 複数 Skill に重複した手順は共有データファイルへ一本化する（Issue #875）

上の委譲はいずれも「決定論的な操作をスクリプトへ」という軸だが、**スクリプトにできない手順（LLM が読む散文）が複数の Skill に複製されている**場合の判断基準は別に要る。Issue #752 が `.wikicommit/review-rules.md` で採った形がその最初の実例であり、Issue #875 が同じ基準を 2 度目に当てはめた。

**基準は Issue #552 が置いたものをそのまま使う** — 「**短い**文面を各自が持つ方が総コストで優る」。裏返せば、短くない文面は各自が持つべきではない。実測して線を引く:

| 重複している手順 | サイト数 | 合計 | 判断 |
|---|---|---|---|
| レビュー規律（何を検査するか） | 3 | 約 27KB | 一本化済み（Issue #752 → `.wikicommit/review-rules.md`） |
| 型ファイルの**書き込み手順** | 4 | 20,031 B | **一本化する**（Issue #875 の方針 A → `.wikicommit/schema-authoring.md`） |
| レビューの**振り付け**（渡すもの・echo 照合・`record_review.py` の呼び方） | 3 | 約 39KB | 保留 — 各 Skill 固有の状態に絡み、全部は出せない（Issue #875 の保留 C） |
| 型ファイル書き込みの**譲れない 3 点**（property 検証・`Boundary —`・`provenance`） | 4 | 各 1 行 | **各サイトに残す** — 短いので基準の逆側 |

**分けるのは「手順」と「判定」の線である。** 型提案の 4 経路（`wikicommit-init` の theme 駆動・`wikicommit-collect` の Type Proposal・`wikicommit-generate` Pass 2b・`wikicommit-schema-propose`）が共有しているのは書き込み手順だけで、提案の閾値・承認 UX・`provenance` の値はサイトごとに違う。`docs/DesignDoc-data.md` §3.3 が「証拠の強さと実行タイミングの違いによる役割分担」として正当化しているのは**後者だけ**であり、前者が 4 本あることは説明していない。

**行き先が `.wikicommit/` のデータファイルになるのは、読み手が複数の Skill ディレクトリにまたがるときだけである。** 読み手が 1 つなら、その Skill ディレクトリ内のファイルでよい（Issue #875 の方針 B が `--regenerate` の手順を `.claude/skills/wikicommit-generate/` 配下のファイルへ出すのがこれにあたる（Issue #911 以降の置き場は `references/regenerate.md`））。どちらも**配布リストの同期を必要としない** — `install.sh` は `find -type f` で再帰コピーし、`.claude-plugin/plugin.json` は Skill **ディレクトリ**を列挙するため、`tests/test_skill_distribution_list_sync.py` が強制する 6 箇所の同期は Skill を増やしたときにだけ発生する。

**「読んだこと」の検証は、読み手がサブエージェントのときにしか成立しない。** `review-rules.md` の `rules_version` echo が働くのは、サブエージェントが返す JSON を orchestrator が照合できるためで、**同じエージェントが読む共有ファイルでは自己申告に退化する**。その場合は読書ではなく**成果物**を検証する側に回る（型ファイルであれば property の実在・`granularity` の箇条書きが文字列としてパースされるか・`Boundary` 行の有無）。

**ファイルが無いときに実行を止めるかは、その経路に必ず到達するかで決まる。** `review-rules.md` は全実行が到達し、進めると劣化したレビューが自分をレビューとして記録してしまうため、実行の最初に確認して無ければ止める。型追加はゼロ件が通常の結果であり、進めてもエンティティがインストール済みの型に落ちるだけ（候補ゼロの通常ケースと同じ結果）で、`check_schema_coverage.py` / `check_installed_type_usage.py` が既に報告するため、**候補が承認された時点で確認し、その候補だけを却下して報告する**。

> `.wikicommit/schema-authoring.md` は Issue #886 で実在するようになり、上の委譲表に行を足した（それまで足さなかったのは、Issue #553 が禁じた「受け皿だけ先に配る」形になるため）。**`rules_version` 相当は置いていない** — 上記のとおり読み手が同じエージェントなので echo は自己申告に退化する。実測は 4 サイト合計 20,031 B → 共有ファイル 10,652 B ＋ 各サイトの呼び出しで、削減分は主に `granularity` の規律が 4 本から 1 本になったことによる。

---

#### 非対話実行が人間の判断に当たったときの扱い（Issue #910）

非対話実行（サブエージェント経由・無人実行）が人間にしか下せない判断に当たる箇所は、このリポジトリに 6 通りに散っていた。**方針を 1 箇所で述べる場所が無いこと自体が問題だった** — 次に非対話分岐を書く人が 7 通り目を足すのを止めるものが無い（Issue #552 / #571 / #722 が繰り返し扱ってきた形）。

| 扱い | 使う場面 | 実例 |
|---|---|---|
| **決めない**（情報提供のみ） | そもそも判断を要さない。報告するだけ | 言語不一致（Issue #336）・partial extraction（Issue #715） |
| **自動で決める** | 証拠が最も強く、かつ事後の確認経路がある | Pass 2b の厳格閾値による自動承認（Issue #507。`wikicommit-merge` の PR レビューが事後の確認） |
| **既定を決めておく** | 待つ先が無いか、既定が明らかに安全側で、かつ取り返しがつく | Step 0 のポリシー確認（登録せず報告）・5 件ガード（(b) 先頭 5 件）・`wikicommit-merge` の warning 続行確認（中断） |
| **保留する** | **人間が見れば答えが変わりうる**判断で、かつ保留したものが後から拾われる経路がある | ガード A の `LOW_DENSITY:`・Pass 2b の閾値未達・`ambiguous` |
| **失敗にする** | 決定論的な判定。人間が見ても答えが変わらない | ガード B・抽出結果が空／読み取り不能・YouTube の URL 形式違い |
| **処理全体を停止する** | 環境の問題であってソースの問題ではない | ガード C（Issue #574）・`rules_version` 不一致（Issue #752） |

**保留の適用条件は「保留したものが後から拾われる経路が存在すること」である。** 無いところには当たらない — `wikicommit-init` の対話プロンプト（`exclude_living_persons`。Issue #837）は 1 回きりでファイルを作る操作なので待つ先が無く、フィールドの欠如も `false` として扱われるため「未決」を表現できない。既定値で進んで `NOTE:` を出す扱いを変えない。

**保留の実現方法は粒度で 2 つに分かれる**（`docs/DesignDoc-data.md` §4.3・`docs/DesignDoc-pipeline.md` §6.1）:

| 粒度 | 実現方法 |
|---|---|
| ソース単位（ガード A・Pass 2b） | **`status` を書き換えずそこで止める**。既存の収集条件にそのまま乗るので、新しい `status` 値もスクリプトも要らない。理由は `## Deferred Reason` に書く |
| エンティティ単位（`ambiguous`） | ソースは `partial` へ進むので、`ambiguous_entities` に**待っていることを記録する**。収集条件には乗せず、解除は `/wikicommit-reconcile` |

**「保留する」は「永続化する」ではない。** Issue #315 が旧 `better_type_candidate` を消した理由（「later, maybe としか言わない間接的な信号」が問題の根源だった）は今も有効であり、保留は候補を記録するのではなく**そのソースの処理を進めない**だけである。次の実行が同じソースを同じ状態から読み直し、同じ候補に到達する。

**そして、この方針が呼び出し側のループ設計に掛かる。** サブエージェントの中は定義上ずっと非対話なので、保留が無い状態でバッチをサブエージェントに委ねると、ガード A の誤検知（saitama 実測で 8 件中 4 件）がそのまま `status: failed` になり、**しかもそれはどの報告にも現れなかった**（Pass 1 は `failed` を収集せず、`check_ingest_freshness.py` は触らず、`wikicommit-merge` Step 9 は `failed_pages` を見ていたため Pass 1 の失敗では発火しなかった）。Issue #910 はその最後の穴も塞いだ — Step 9 が `status: failed` も対象にし、`wikicommit-status` Step 15 が `failed` / `excluded` / 保留 / `ambiguous` をそれぞれ数える。

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
| 抽出テキスト全文（パス 2a・ソースごと） | 40,442 B/件（日本語 Wikipedia 記事 1 本を `add_source.py --fetch-url` で実抽出。2026-09-02 実測） | 約 10K × 件数 |
| 生成ページ本文（パス 3 がパス 4 のために保持） | ページ数ぶん | 累積 |

**固定分の 92% は SKILL.md である。** かつては型一覧が 44%（147,421 B・約 37K トークン）を占めていたが、Issue #798 が 2 段階化して 13,441 B へ落とした — あの一覧が果たしていたのは**想起**であって存在保証ではなく（実在は候補承認後の `--type` が決定論的に確かめる）、想起には誰も検討していない 928 型の説明文が要らないためである。残る削減対象は SKILL.md 自身（進行的開示・サブエージェント化）である — **前者は Issue #894 が実施した**（Completion Notice と Prerequisite Skills を別ファイルへ。ただし下記のとおり減るのは本体だけで、この 51K という固定オーバーヘッド自体は減らない）。後者は着手未定。

**5 件ガードは 2 つの役割を同時に果たしている。** Issue #567 がパス 1 に置いた「1 回の収集が 5 件を超えたら人間に確認する」というガードは、**1 回の処理量を人間が制御する**ために設けられたものだが、結果として**コンテキスト予算も律速している** — 上の表の可変分（1 件あたり約 15K）に掛かる係数がその件数だからである。

このことを明記しておかないと、**将来ガードを緩める判断がコンテキスト側の帰結を見落とす**。5 件を 10 件にする変更は「1 回の処理量が増える」だけに見えるが、実際には必要コンテキストが約 51K + 75K から約 51K + 150K へ動く。

**Issue #798 以降、200K 環境でも 5 件が通る。** Claude Code の Opus 既定は 200K であり（2026-09 時点。Sonnet 5 / Fable はネイティブ 1M、Opus は `[1m]` サフィックスで 1M。プラン依存）、5 件処理は約 126K（63%）で収まる — 2 段階化前は約 154K（77%）に達して auto-compact 圏内に入っていた。**したがって 200K の上限が 5 件ガード自身の上限を下回る状態は解消しており、ガードの答え（「全件」か「先頭 5 件」か）とコンテキストの許容量が初めて一致する。**

**それでも compaction の壊れ方は変わらない**ので、上限を超える運用は引き続き避ける。compaction 後に再添付されるのは**各 Skill の先頭 5,000 トークンだけ**である（`code.claude.com/docs/en/skills`。**これは Claude Code というハーネスの挙動であって、モデルの性質でも agentskills.io 標準の一部でもない** — §11.1 のとおり標準が共有するのは SKILL.md の形式と frontmatter までで、コンテキスト管理は各ハーネスの実装である。したがってバージョンで変わりうるし、他エージェントでは別の壊れ方をする。**この数字を配布物の設計閾値や CI のガードに焼き込まないこと** — 根拠だけが残って前提が消えるのは、§11.9 の冒頭が扱っているのと同じ失敗である）。`wikicommit-generate/SKILL.md` ではおよそ 105〜117 行目（3.5〜4 バイト/トークン換算）まで — Step 0 までしか残らず、パス 1〜4 と Completion Notice は全部その外側にある。**エージェントは残りの手順を持たないまま実行を続け、出力は一見正常に見える。**

Issue #797 の checkpoint はこの状態を間接的に可視化する（打点の欠落として現れる）が、**同 Issue 自身が「分割前は Pass 2 以降の打点指示も同じ 5,000 トークンの外側にある」という非対称を既知の限界として記録している** — つまり compaction が起きた実行では打点指示ごと落ちうるため、検出は保証されない。

> **数字の更新（2026-09-13 実測。上の表と本文は当時の値のまま残す）**: `wikicommit-generate/SKILL.md` は **191,168 B → 162,291 B（約 40K トークン）** に下がり、**起動のたびに必ず載る量は約 51K → 約 43K** になった。**下げたのは 1 本ではなく 3 本である** — #886（型ファイルの書き込み手順を `.wikicommit/schema-authoring.md` へ）・#887（`--regenerate` を別ファイルへ。Issue #911 以降は `references/regenerate.md`）・#894（Completion Notice と Prerequisite Skills を別ファイルへ）。上の表の 191,168 B は 2026-09-09 のスナップショットであり、その後 199,621 B まで伸びてから 3 本で削られている（#894 単独の寄与は 182,209 → 159,998 B）。
>
> **一方、1 回の実行が要する総量は約 49K であり、51K からほとんど下がっていない。** 上の「この 51K という固定オーバーヘッド自体は減らない」は今も正しい — SKILL.md 自身が **Neither is optional** と書いているとおり、`references/text-extraction-routing.md`（4,949 B）と `references/completion-notice.md`（20,116 B）は**ソースを処理する実行なら必ず読む**（合計 25,065 B ＝ 約 6K トークン）。減ったのは**先に載る量**だけであり、Issue #892 が目的をそちらに置き直したのはこの区別による。**`README.md` / `README_ja.md` は両方を書く**（固定 49K のうち 43K が最初のソースを読む前に載る）— 利用者が契約を選ぶときに要るのは 49K の側である。
>
> **可変分の係数は実測で約 22K/件であり、上の表の 15K の 1.5 倍である。** 30 件を 1 回で処理し完了時に 1M の約 70%（約 703K）だった実行からの逆算で、固定 49K を差し引くと (703 − 49) ÷ 30 ＝ 約 21.8K/件になる。15K は日本語 Wikipedia 記事 1 本の値であり、**実運用の混在ワークロードはそれより重い**。壁は **200K で約 7 件・1M で約 43 件**になる。
>
> **したがって「Issue #798 以降、200K 環境でも 5 件が通る」は成り立つが、余裕は上の記述より小さい** — 22K/件では 5 件処理が約 159K（80%）で、2 段階化前の水準に戻る。#798 が改善したのは固定分であり、可変分の係数が想定より大きかった分をそこで食っている。
>
> **5 件ガードの二役のうちコンテキスト側は、ループを呼び出し側へ出す運用では拘束しない**（Issue #892 のコメントで確定）。1 回の呼び出しが 5 件に収まる限り、上の「将来ガードを緩める判断がコンテキスト側の帰結を見落とす」という警告が当たるのは、**呼び出し側が同一コンテキストでループした場合**である。

利用者向けの式・推奨件数・公式ドキュメントへのリンクは `README.md` / `README_ja.md` が正本である（`CLAUDE.md` は公開スナップショットに含まれないため、公開側だけを読む利用者に届く場所を正本にした）。**README 側は 1 節で完結する** — Requirements → Context window が、式・1 件あたりを変数として見せる表・5 件ガードの位置づけ・compaction で何が起きるか・モデル設定ドキュメントへのリンクを持つ。かつてはここに導出を置く 2 節目（`Context window in detail` /「コンテキスト長（詳細）」）があったが、README にその深さは要らないと判断して削除した — **固定分の内訳とこの数字の経緯を持つのは本節である**。

#### 固定 51K の内訳と、下げられるもの / 下げられないもの（Issue #875）

SKILL.md の 199,420 B を区画ごとに測ると、**入口によって読まれない区画がある**。

| 入口 | 要る分 | 死重 |
|---|---|---|
| `/wikicommit-generate <src>` | 180,039 | 10% |
| `/wikicommit-generate`（引数なし） | 168,964 | 15% |
| `/wikicommit-generate --regenerate` | 118,897 | **40%**（Step 0・Pass 2a/2b/2c・Completion Notice を読まない） |

主経路で落とせるのは `--regenerate` の区画（19,381 B ＝ 9.7%）だけである。**Pass 単位でファイルを割っても主経路では 0%** — 通常実行は全 Pass を通るので、読まない部分が存在しない。Completion Notice は 20,116 B のうち 95% が条件分岐だが、各 Pass が走行中にリストを積む指示を持つため、末尾だけ遅延読み込みしても読む順が変わるだけで総量は減らない。

> **その区画は実際に出した（Issue #887）**: `--regenerate` の手順は `.claude/skills/wikicommit-generate/references/regenerate.md` にあり、`SKILL.md` 側には分岐とそのファイルを読む指示だけが残る（`SKILL.md` は 195,097 B → 176,864 B。上の表の 199,420 B は Issue #875 時点の測定で、その後の変更で縮んでいる — この節に 2 つの「移動前」が並ぶのはそのためである）。**Skill は割っていない** — Pass 1 / 3 / 4 は通常生成と共有しており、Issue #578 が新規 Skill にしなかった論拠は今も成立する。ファイルを割る理由になるのは、単位が違い（ソース起点 vs ページ起点）モード排他だからである。**読まなければ手順が無いので必ず止まる**ため、読み飛ばしが静かな失敗にならない（Issue #886 の共有データファイルとはこの点で非対称であり、あちらは「候補を却下して続行」だが、こちらは「停止して報告」である）。
>
> **同時に `tools/check_skill_md_lines.py` の単位と測定対象を変えた**。分割すると同じ内容がそのまま残っているのに 1,129 行 → 1,063 行になり、行数だけを測るガードは「改善した」と報告する — **測定対象を変えないまま分割すると指標が実態を追わなくなる**ため、2 つを同じ変更に入れた。現在は指標が 2 本ある: **指示の総面積**（Skill ディレクトリ配下の指示 `.md` 全件のバイト数。既定 40,000 B）と **`SKILL.md` 本体**（行 ＋ バイト。既定 500 行 ＝ Anthropic のガイダンスの値と単位のまま）。対で読むと「本体 ↓ / 総面積 →」がそのまま「分割した」を意味し、片方だけでは読めなかった状態が読めるようになる。閾値の根拠は**トークン費用の代理指標**（約 4 バイト/トークンで約 10K トークン）と**実測分布の自然な gap**（閾値の下で最大 28,777 B・上で最小 41,223 B）の 2 方向からで、**compaction の窓には置いていない** — この節の冒頭が既にその線を引いている理由そのものである。
>
> 行数が代理指標として歪んでいたことも実測で確認した: `.md` の密度は 41〜166 B/line と **4.0 倍**ばらつき、`wikicommit-status` は `wikicommit-init` の 75% のバイト数を持ちながら 500 行ガードを通っていた。バイトに変えた結果、同 Skill は「行数は OK・総面積は超過」として現れる。
>
> **ただしこの指標は「別ファイルに出す」と「別コンテキストへ渡す」を区別しない。** 前者は同じ会話に読み込まれ、後者は読み込まれないため、**サブエージェント化した Skill はこの指標上、実際より高く出る**。静的には区別できず（ファイルを見ても書き手の意図は分からない）、frontmatter のマーカーで区別する案は消費者が居ないうちは配らない（Issue #553）ので、指標は変えずスクリプトの docstring に注記を置いた。
>
> **そして Completion Notice と Prerequisite Skills も出した — 上の「総量は減らない」は撤回しない（Issue #894）**: 直前の段落が Completion Notice について「末尾だけ遅延読み込みしても読む順が変わるだけで総量は減らない」と書いたのは**総量については正しく、いまも正しい**。会話に読み込まれる量は 1 バイトも減っていない（`check_skill_md_lines.py` の surface は 203,344 B → 208,039 B と**増えた** — 移した先の前置きと、本体に残したポインタの分である）。
>
> 成立しなくなったのは、目的をそこに置いたときだけである。目的を「**SKILL.md 本体が、起動のたびに丸ごと読まれる状態をやめる**」と置き直すと（Issue #892 がサブエージェント化の側についてそう置き直した。その結論は下記のとおり「採らない」である）、同じ問いに対して進行的開示は答えを持つ:
>
> | | 行 | バイト |
> |---|---|---|
> | 分割前（Issue #885 後） | 1,091 | 182,209 |
> | 分割後 | **826** | **159,998** |
>
> 出したのは 2 区画で、どちらも**入口によっては一度も読まれない**: Completion Notice（20,116 B。Step 0 で止まる実行・`--regenerate`）と Prerequisite Skills（4,949 B。Pass 1 だけが読む拡張子別ルーティング表であり、`--regenerate` や処理対象 0 件の実行では Pass 1 に到達しない）。**Pass 1〜4 までは広げていない** — そこは Issue #892 のサブエージェント化と同じ区画を対象にするため、両方を採ると片方が無駄になる。
>
> **compaction に対してはこちらの方が強い**。本節冒頭が記録しているとおり、再添付されるのは各 Skill の先頭 5,000 トークンだけで、Completion Notice の 20,116 B は**丸ごと消えて誰も気づかない**。ポインタ 1 行にすればそれは窓に残るので読み直せる — **ただしポインタの置き場が設計上の要点になる**。末尾にだけ置くと窓の外に落ち、いまとまったく同じ壊れ方をするため、Processing Flow（窓の内側）に表として置いた（3.5 B/トークン換算の厳しい側でも窓に入ることを実測で確認済み）。サブエージェント化ではこれは解けない — 親が窓の何倍にもなるためである。
>
> **`record_run.py end` を `references/completion-notice.md` の側に置いたことが、読み忘れの検出を兼ねる**。本体に残すと、ファイルを読み忘れた実行は記録が正常に閉じたまま報告だけが 1 行も出ず、それを言うものがどこにも無い。移した先に置けば、読み忘れは**開いたままの記録**として残り `/wikicommit-status` が `INCOMPLETE_RUN:` を出す（Issue #790 が `ended_at` の空を「完走しなかった」の答えと定義したのと同じ形）。
>
> **`## Notes`（書き込み権限の契約）は本体に残した**。7 行 994 B で小さいことに加え、あれはファイル末尾にあり**元から窓の外**なので、出しても入れてもポインタか要約のどちらかを窓に置かなければ届かない。そして窓に届いている必要がある半分（「Git 操作を行わない」）は既に L9 の 1 行目の説明文にあり、残る半分（`.wikicommit/schema/` への narrow exception）を行使できるのは Pass 2b だけで、そこが compaction で落ちていれば行使する主体自体が無い。したがって移す利得が無い。
>
> **指標は本 Issue のために変えていない**。surface が増えたのは上記のとおりで、本体の縮小が見えるのは Issue #887 が同じ行に本体の行数・バイト数を併記するようにしたおかげである（`SKILL.md 1091 lines` → `SKILL.md 826 lines`）。あの変更が無ければ、この Issue は指標の上で完全に不可視だった。
>
> **そして Pass 本体まで広げた — 本体は 831 行 → 200 行になった（Issue #911）**: 5 つの Pass が `references/pass1-extract.md`・`pass2b-type.md`・`pass2c-entities.md`・`pass3-generate.md`・`pass4-review.md` へ出て、`SKILL.md` に残ったのは header / Usage・Processing Flow・Step 0・index/reconcile・Notes とポインタである（162,291 B → 約 29,000 B）。**上の「総量は減らない」はここでも撤回しない** — surface はむしろ増える。減ったのは**起動のたびに丸ごと載る量**であり、#894 が目的をそこへ置き直した区別がそのまま効いている。
>
> **compaction に対する効き方が、ここで質的に変わる。** 本体が約 29,000 B なら再添付の窓（先頭 5,000 トークン）が本体のほぼ全体を覆うため、#894 が「ポインタの置き場が設計上の要点になる」と書いた条件が、ポインタ 1 行ではなく本体丸ごとで満たされる。副次的に **Issue #797 が既知の限界に挙げていた非対称が消える** — 打点の指示が各 Pass のファイルへ移り、本体の冒頭から長い実行の末尾まで生き延びる必要がなくなった。
>
> **`--token` はこの形でしか成立しない**（`docs/DesignDoc-ScriptSpec.md` の `record_run.py` の節・§11.3）。同一エージェントへの分割では「読んだと自分に申告する」だけになるが、`record_run.py` が第三者としてそのファイルを開いて `pass_token` を突き合わせるので、「パスファイルを読まずに即興で実行した」が検出できる。Issue #890 が「消費者が 1 つも無い」と問題にしていた `--token` と pass ファイルの置き場は、ここで両方とも消費者を得た。
>
> **そして #892 の再判断トリガー 4（本 Issue が着手されないまま 831 行のまま留まった場合）は解消した。** 残る 2 件（`wikicommit-init` 796 行・`wikicommit-merge` 773 行）は超過したままであり、同じ手が効くことを確認したうえで別 Issue とする。

**コンテキストの「ピーク」を下げられる案はサブエージェント化だけである。** Skill を割ってもコンテキストは累積するのでピークは下がらず、各 Skill の前置きが重複する分だけ増える。サブエージェントは別コンテキストなので、親には戻り値しか載らない。前例は既に 2 つある（`generate` Pass 4 と `synthesize` Step 5.5 のレビューサブエージェント）。

**その場合の切り口は圧縮率ではなく「ファイルが書かれる瞬間」に置く。** そこで切れば受け渡し形式は既にあり（管理ファイル・scratch・schema ファイル・ページ）、**新しい scratch 形式を作らずに済む**。副次的に再開可能性が付き、Issue #797 の `checkpoint` の打点位置と境界が一致する。

> **訂正（Issue #892）**: 本段落はかつて、この切り口の根拠を「`docs/DesignDoc-data.md` §4.6 が『ディスクにも Git にも残さない』と定義した分析 JSON の永続化に抵触しない」と書いていた。**これは誤りである** — §4.6 は「**LLM レビューのフィードバック形式**（エージェント間 JSON）」の節であり、そこで永続化を禁じられているのは **Pass 4 のレビュー JSON**（`result` / `issues[]`）である。Pass 2c の**分析 JSON**（`entities[]`）の永続化を禁じる記述は、`docs/` と SKILL.md を通じて 1 件も存在しない。したがって次段落の「Pass 2c ｜ Pass 3 は割れない」も、**禁止によるものではない** — 割れば新しい scratch 形式を作ることになり、かつ #875 が理由 3 で挙げた「Pass 2c → Pass 3 の間には分析 JSON に載らない文脈がある」（**載っていないものが何かを誰も知らない**）という測れない劣化を招くため、割らないという判断である。書かれている前提が偽であると、次に読む人がそれを根拠に別の判断を下す — 本ドキュメント群が繰り返し扱ってきた「書かれていない前提は drift する」（Issue #722・#552・#571）の、**書かれている前提が偽である**版にあたる。

**ただし Pass 2c ｜ Pass 3 だけは割らない。** そこは `## Generation Notes` に落としたもの（`exclude` と `coverage_gap_note`）は書くが、Pass 3 が要る「これから作るものの一覧」は書かない — **記録が残るのは否定側だけ**である（上の訂正のとおり、書けないのではなく書く先を新設しないという判断である）。したがって単位は次の 4 つになる。

| | 中身 | 抽出テキストの読み込み |
|---|---|---|
| 親 | Step 0（登録・対話）、収集と 5 件ガード、**Pass 2b の承認と schema 書き込み**、リトライ制御、`status` 更新、Completion Notice | 0 回 |
| 単位 A | Pass 1 ＋ Pass 2a → scratch を書き、`{path, hash, ガード判定, summary}` を返す | 1 回目 |
| 単位 B | Pass 2c ＋ Pass 3 → scratch を読み、管理ファイル body とページを書く | 2 回目 |
| 単位 C | Pass 4 → scratch とページを読み、判定 JSON を返す（既存） | 3 回目 |

Pass 2b が親に来るのは、summary だけで判断でき本文が要らない（同 Pass が "grounded in the Pass 2a summary" と明記）うえ、人間の `[y/N]` がそこにあるためである。**本文の読み込みが 3 回になるのは対話のときだけ**で、非対話実行では単位 A と B を融合できるため現在（親 1 ＋ Pass 4 サブ 1 ＝ 2 回）と同じ回数のまま、親のピークだけが 126K → 約 19K に落ちる。

**Issue #875 はこれを採らないと決めた。** 理由は 3 つ: (1) Issue #798 の後、5 件処理は 200K 環境で 126K（63%）に収まっておりピークがいま問題ではない、(2) **Pass 3 が門番である** — 抽出テキスト全文を要するのは Pass 2a / 2c / 3 / 4 で、Pass 3 を親に残すと親は本文を読まねばならず他を全部サブエージェントにしても可変費は 1 バイトも減らない。そして Pass 3 は圧縮率が最悪で人間が内容を見る判断も最も効く、(3) Pass 2c → Pass 3 の間には分析 JSON に載らない文脈があり、同じ品質が出るかを測る eval 基盤がこのリポジトリに無い（Issue #669 と同じ理由）。**再判断の条件は、5 件ガード（Issue #567）を緩めたくなったとき、または 1 実行が 200K に収まらなくなったときである。**

**前提条件が 1 つ足りない**: `type: path` は抽出テキストをキャッシュに書いていない（scratch を書くのは `type: url`/`wikicommit` だけ）ため、単位 B と C が読む先が無い。これはサブエージェント化の採否と独立に成立する欠落として Issue #885 に切り出した。

**対話性の判定も同時に直す必要がある**: SKILL.md は対話性を自己申告で判定し、その文言は `non-interactive/subagent-driven` である。つまり現在の設計は「サブエージェントの中に居る ＝ 非対話」と**定義している**ので、Pass を素朴にサブエージェント化すると、親が対話セッションで動いていても内側は必ず非対話と自己判定し、schema ファイルに `provenance: generate-auto`（恒久スタンプ。どの Skill も後から書き換えられない）が刻まれる。上の 4 単位構成は Pass 2b を親に置くのでこれを踏まないが、判定を親が 1 回行って渡す形にすること自体は、どの構成でも必要になる。

> **目的を「肥大化そのもの」へ置き直しても、やはり採らない（Issue #892）**: 上の #875 の判断は**ピーク**を目的にしたときのものであり、その論法は「5 件処理が 200K に収まっているうちはピークが拘束しない」に立っている。Issue #892 は目的を **SKILL.md 本体が起動のたびに丸ごと載ること**へ置き直して同じ問いを立て直したが、**結論は同じく「採らない」になった**（2026-09-13 に確定）。**#875 の判断は上書きしない** — 目的が違えば論拠も再判断の条件も違うため、2 つを並べて残す。
>
> 根拠は 3 つで、うち 2 つは #875 の時点では存在しなかった。
>
> 1. **公式ガイダンスが、超過時の処方として進行的開示を名指ししている。** `skill-creator` の Skill Writing Guide は「500 行に近づいたら、**階層をもう 1 層足し、次にどこを読めばよいかのポインタを明示せよ**」と書いており、公式の progressive disclosure は 3 層（Metadata / SKILL.md body `<500 lines ideal` / Bundled resources — As needed）である。**サブエージェント化は肥大化への対処としてガイダンスのどこにも現れない**（禁じられてはいない）。#892 は「500 行ガイドラインに届く唯一の手」を最強の論拠に据えていたが、同じ区画を動かす進行的開示も同じだけ削る
> 2. **ループ／バッチ処理を呼び出し側の責務と決めたため、コンテキストの論拠がスコープから消えた。** 相談の途中で実運用が 30 件一括であることが判明し、一度は「#875 の理由 (1) が偽になった」という判断につながった（実測から 1 件あたり約 22K・壁は 200K で約 7 件。上記「数字の更新」のコールアウト）。しかし**ループは `wikicommit-generate` の外で解く**と決めたため、1 回の呼び出しは 5 件ガードの範囲に収まり、固定オーバーヘッドの削減（サブエージェント化の唯一の測れる便益）は再び非拘束になった
> 3. **残る便益は実在するが測れない。** 工程分担の構造的強制と、暗黙の結合が受け渡し契約として表に出ることは実在する利得だが、それを確かめる A/B は「1 対の実行では差が偶然でありうる」という弱い証拠にしかならない。一方コストは確実で、とりわけ**単位 B（65,893 B）の契約漏れは黙って劣化する**。Issue #669 が `chain_of_thought` について採った基準（効果を測る手段が無い一方でコスト増は確実に発生する）がそのまま当たる
>
> **数字でも進行的開示のほうが小さい。** 831 行に対し、4 単位構成の親は 427 行（71,235 B）、進行的開示を Pass まで広げると**約 214 行（約 26,000 B）**。逆転するのは、振り付け（6,047 B / 30 行 × 2 単位）がポインタより高いためである。**compaction についても同じ向きになる** — 約 26,000 B なら再添付の窓が本体のほぼ全体を覆う一方、4 単位構成の親は窓の 3〜4 倍で収まらない。
>
> **再判断のトリガーは #875 のそれとは別である**（あちらは「5 件ガードを緩めたくなったとき／1 実行が 200K に収まらなくなったとき」）。#892 の側は次の 4 つ。
>
> 1. 呼び出し側の解決が**同一コンテキストでのループ**に落ち着いた場合（コンテキストが再び拘束する）
> 2. 進行的開示の後も SKILL.md が 500 行を超えて**再び成長した**場合 — 削減 3 本の −385 行に対し、通常の機能追加 2 本（#903 / #905）が 48 時間で +33 行を戻した実測がある
> 3. 暗黙の結合 2 件（ガード A の対話性が自己申告であること・Pass 2c → Pass 3 の受け渡しが分析 JSON に載っていないこと）が実害として現れた場合
> 4. ~~**Issue #911 が着手されないまま、SKILL.md が 831 行のまま留まった場合**~~ — **解消済み（Issue #911）**。`wikicommit-generate/SKILL.md` は 200 行（約 29,000 B）になり、根拠 1 が立っていた「代替案が同じだけ削る」は実測で成立した。**残る 2 件は超過したままである** — `check_skill_md_lines.py` は `init` と `merge` を引き続き `over 500` として報告し、同スクリプトは WARNING どまりで `exit=0` なので CI は通る。`wikicommit-generate` で同じ手が効くことが確認できたので、残り 2 つは別 Issue で扱う（`wikicommit-init` は `CHANGELOG.md` / `changelog/` という配布ペイロードを抱えており事情が違う）。以下は当時の記述:
>
> **Issue #911 が着手されないまま、SKILL.md が 831 行のまま留まった場合** — 根拠 1 は「代替案が同じだけ削る」ことに立っており、**その代替案はこの判断の時点でまだ入っていない**。決着したのは方針であって状態ではない: 本 Issue のクローズ時点で `tools/check_skill_md_lines.py` は `generate` 831 行・`init` 796 行・`merge` 773 行の 3 件を `over 500` として報告し、**しかも同スクリプトは WARNING どまりで `exit=0` なので CI は通る**。採らないと決めた案の代替が実装されないまま、超過だけが静かに続きうる

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
  "summary": "本文書は CompanyA の技術ブログ記事。山田太郎氏の紹介と Project Alpha の概要を含む。",
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
      "existing_path": ".wikicommit/entity/ja/Person/suzuki-hanako.md",
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

- `summary` はソース全体の 2〜3 文要約（`config.yml` の `theme` が空でも常に生成する）。ソース管理ファイル body の `## Summary` に書き込まれる（§4.3・`DesignDoc-data.md`）。言語は `primary_lang` とする（Issue #314 — 従来この指定がなかったため、`summary` 自体は結果的に `primary_lang` で書かれる一方、`exclude_note`/`coverage_gap_note` にはエージェントのセッション言語が漏れ込み、同一 `## Summary` 内で言語が混在する不具合が実際に発生した）。付記フィールド（`exclude_note`・`coverage_gap_note`）は `## Summary` ではなく **`## Generation Notes`** に書かれる（Issue #831 — `## Summary` は `content/sources/` の公開ページに載る唯一の節であり、そこへ除外理由を追記していたために実在の人物名と内部識別子が読者に届いていた）。言語はこの `summary` と同じ（＝ `primary_lang`）で統一する。**見出しラベル自体（`## Summary`・`## Generation Notes`・`## User Notes`）は本文の言語（`primary_lang`）に関わらず常に固定の英語**（Issue #405 — `primary_lang: en` パイロットで本文は正しく英語なのに見出しラベルだけ `## サマリ`/`## ユーザーメモ` と日本語固定になっていたことが判明。見出しラベルは機械が照合する識別子でありローカライズ対象外という判断。詳細は `docs/DesignDoc-data.md` §4.3）
- `lang` はパス 2 実行前に `.wikicommit/config.yml` の `primary_lang` を読んで全エンティティに設定する。**この設定はソース文書自体の言語に関わらず常に行われる**（意図的な既存設計）——`primary_lang: ja` のリポジトリに英語ソースを ingest しても、生成されるページの `lang` は `en` にはならず `ja` になる（内容は要約・翻訳された上で統合される）。この暗黙の挙動に気づかないまま運用が進むと、例えば翻訳品質を実在する外国語原文と突き合わせて検証するような用途で、比較対象のはずのページ自体が既にその原文を読んで書かれてしまっており検証が無効化される、といった問題が起こりうる（`Paperwork-Navigator-wikicommit-pilot` で実際に発生。Issue #336）。この問題自体（`lang` を `primary_lang` に固定する仕様）を変更する対応ではなく、Pass 2a がソース言語と `primary_lang` の明らかな不一致を検出した場合に Completion Notice で一言注記する形で可視化する（`.claude/skills/wikicommit-generate/SKILL.md` Pass 2a・Completion Notice 参照）
- `action: update` かつ `existing_path` がある場合は、既存ページを LLM コンテキストに追加してから生成する（既存情報を失わず新情報を統合）
- **`existing_path` は `action: exclude` のエントリにも設定する（Issue #876）**。照合は `action: update` のための既存ページ走査と同一で、`(lang, Type, slug)` は Pass 2c がそのエンティティに付けた値そのものである。**生成側はページを削除しない**（削除経路は `/wikicommit-remove` だけ）ため、今回除外されたエンティティに前回以前の実行が作ったページが公開されたまま残ることがあり、それを名指しする主体が他にいなかった。`## Generation Notes` が記録するのはエンティティの**タイトル**であり、ファイル名は言語中立な英語 slug で、その導出規則（普通名詞は英訳／確立した原綴り／それ以外はローマ字。Issue #193）は**逆算できない** — `primary_lang` が英語でない Wiki（このポリシーが実際に効いた `wikicommit/saitama-city-wiki`〈ja〉・`wikicommit/decameron-wiki`〈it〉がまさにそれ）では、人は `title:` を grep することになる。**機械はそのエンティティに名前を付けた副産物として答えを既に持っている。**
  - **このフィールドは `exclude` では情報であり、何も駆動しない。** `create`/`update` では Pass 3 が既存ページを読む分岐を駆動するが、Pass 3 はその 2 つしか処理しないため、`exclude` の `existing_path` は読み込みも書き込みも起こさない。**暗黙にせず明記する**（書かれていない前提は drift する）
  - 報告先は **Completion Notice と `## Generation Notes` の両方**。どちらも既存の行への追記であり、新しい報告ブロックは 1 つも足さない。前者は人が対処を決める瞬間の出力（Issue #452 が `failed_pages` に対して採った形）、後者は管理ファイルに残る写しで、`_write_source_page()` のホワイトリスト外なので非公開のまま（Issue #831 の線引きを崩さない）
  - **報告は断定しない。** 述べるのは「このページは在り、今回の実行は作りも更新もしなかった」までである — 3 件のソースに支えられたページの 1 件が今回 off-theme と判定されただけ、という形は普通に起こるため、除外は削除の根拠にならない（`check_installed_type_usage.py` の `ANCESTOR_FALLBACK:` が「示唆であって断定ではない」と自ら書いているのと同じ姿勢）。強さは `exclude_reason` で分け、`/wikicommit-remove` を指すのは `privacy` グループのみ。**自動削除は行わない** — ポリシーが決めるのは「作らない」であって「消す」ではなく、削除は不可逆で、`removed_reason` の選択も人間の判断に属する
  - `wikicommit-status` の常設チェックは置かない（Issue #867 が却下した「1 回きりのイベントに常設チェックを置く」形の再現になる。大半のページの正しい対処は「残す」であり、所見が消えない）。**`--regenerate` では発火しない** — 同モードは Pass 2c を実行しないため（Issue #578）、この報告はソース起点の実行にしか現れず、入口は `/wikicommit-reconcile`（Issue #874）が `status` を戻して合流させる経路である
- `ambiguous: true` のエンティティはページ生成をスキップし、コンソールに記録してユーザーに型の確定を求める
- `action: exclude`（Phase 2〜）はページ化しないと判断したエンティティ。`exclude_reason` は現状 **`theme_mismatch` / `privacy` の 2 値**（Issue #667）で、`exclude_note`（除外理由の説明文。`## Generation Notes` に反映される〈Issue #831〉。`summary` と同じ言語＝ `primary_lang` で書く。Issue #314）を伴う。いずれも人間の確認なしに自動でページ生成をスキップする。2 つは互いの変種ではなく独立した別軸の理由であり、判定も別々に行う:
  - `theme_mismatch`: `config.yml` の `theme` に照らして無関係（**関連性**の軸）。`theme` が空文字列の場合、LLM に**この判定だけを**行わせない（off-subject を理由とする除外が消えるだけで、`exclude` 全体を禁じるのではない — 下の `privacy` は別軸として引き続き効く。`/wikicommit-init` の既定は空の `theme` であり、ここで `exclude` 自体を禁じると entity-policy を設定した Wiki で許容性の判定が丸ごと黙って無効化される）
  - `privacy`: `.wikicommit/entity-policy.md` が書いてよくないと定めたもの（**許容性**の軸。`exclude_living_persons` スイッチと散文本文の両方が入力になる。`docs/DesignDoc-data.md` §3.5）。ファイルが無い・スイッチ off・散文が空のいずれでもこの判定自体を行わせない。**両方の理由が同じエンティティに当てはまる場合は `privacy` を記録する** — Wiki の主題が変わっても残る側の理由であるため

  `copyright` は **enum に加えず予約のまま据え置く**（Issue #667）。ソース側で保護期間・ライセンスを確認して取り込む設計になっている以上、エンティティ単位で「著作権を理由にページを作らない」と判断する場面がほとんど残らず、消費者を得ないまま並べると Issue #553 が `inDefinedTermSet` について指摘した「受け皿だけ存在して常に空のまま残る」形になる
- **ソースがすれ違いに引用しただけの文書は、そもそも `entities` に出さない（Issue #968）**。ソースが別の話を書きながら 1 回だけ名前を出した文書（対比のための引用・関連研究の 1 行・参考文献リストの項目）はエンティティではない。逆に、ソースがその文書ないしそれが引用されている事実を**自分の主題として**扱っている場合（タイトルか中心的な主張がそれについてである）は通常のエンティティであり、他のルールがそのまま適用される。**両側を対にして書く** — 片側にしか書かれない境界は片側にしか適用されない（Issue #550 が `granularity` について残した教訓の、1 段手前での再現）。
  - 判定は `.wikicommit/review-rules.md` の check 1 / check 4 と**同じ主題性のテスト**を 1 段早く当てるだけである。**判別がつかない場合は passing mention 側に倒して抽出しない** — これは好みではなく、check 4 が同じ引き分けを同じ側に倒すためである。Pass 2c だけが不明瞭なケースで寛容だと、その差分がそのまま「抽出 → 生成 → 却下 → 記録 → 再実行」の無駄な 1 周を**構造的に保証する**
  - **登録の有無は判定に持ち込まない。** ソース登録簿（`.wikicommit/source/`）は Pass 2c のコンテキストに元から入っておらず、本ルールも走査を求めない。その文書が別途登録されていれば、そのソース自身の実行がページを作る。本ソースが寄与しなくなることは損失に見えるが、passing mention である以上そこに書ける事実は元から無い
  - **Pass 2a の source-as-entity 判定（Issue #475）とは別物である。** あちらは「ソース文書**自身**をページ化するか」、こちらは「ソースが**引用した別の文書**をページ化するか」。`wikicommit/ai-driven-dev-wiki` の arXiv 2602.06310 では 1 回の実行で両方が発火し、前者は正しく後者は誤っていた
  - **非抽出は痕跡を残さない。これは受け入れる。** `action: exclude` なら `## Generation Notes` と Completion Notice に 1 行残る（Issue #831 / #876）のに対し、抽出しないことは無言である。3 つ目の `exclude_reason` を足せば記録は残るが、この軸は関連性でも許容性でもなく**証拠**であり、消費者のいない enum を配ることは Issue #553 が禁じた形にあたる。**露出が限定的なのは片方向だけであり、だからこそ過剰適用してはならない。** passing mention を正しく落とす側は、どのみち Pass 4 が却下していたページが 1 段手前で消えるに留まる。一方、ソースが本当に主題として扱っている文書を誤って落とす側は対称ではない — そのページはレビューを通ったはずであり、`exclude_note` も Completion Notice の行も残さずに消えるうえ、書かれなかったページは orphan でも wanted page でもないのでどのヘルスチェックにも現れない。無言であることの代償は、限定的でない側に寄っている。引き分けの倒し方は**本当に判別がつかない場合に限り**、タイトルか中心的な主張がその文書についてであれば抽出する
  - **抽出・執筆・レビューの 3 段が同じ境界を持つことになるが、これは Issue #552 の「共通ルールを個別の場所で言い直さない」に反しない。** 3 段が下している判断は別物である — Pass 2c は**エンティティを作るか**、Pass 3 は**本文に別文書の日付・タイトルを確定事実として書くか**（Issue #473 の Secondary citation discipline。**残す**）、Pass 4 は**FAIL にするか**。同じ命題の言い換えではなく、同じ境界を 3 つの異なる決定に当てている（`review-rules.md` の check 1 と check 4 が意図的に対になっているのと同じ関係）
- `slug` は言語中立な英語識別子とする（CLAUDE.md の WikiLink 節）ため、日本語発音の音写ではなく以下の優先順位で決定する（Issue #193）:
  1. 普通名詞・概念語 → 英訳した slug にする（例: `キリマンジャロコーヒー` → `kilimanjaro-coffee`。`kirimanjaro-koohii` のような音写は不可）
  2. 固有名詞（人名・組織名・地名等）で英語圏に確立された原綴りがあるもの → その原綴りを使う（例: `スターバックス` → `starbucks`。`sutaabakkusu` は不可）
  3. 上記いずれにも該当しない固有名詞 → ローマ字表記でよい（例: `山田太郎` → `yamada-taro`）
- `expires_at` はソース本文が明示的な期限（申請締切・有効期限・年度区切り等）を述べている場合のみ `YYYY-MM-DD` を設定する。それ以外は `null`（Issue #279 — Pass 2 がこの候補を出力しないために `expires_at` frontmatter が実運用でほぼ使われない状態になっていた）。日付を推測・逆算しない。複数の期限が併記されている場合（最後の `schema:GovernmentService` の例のように支給時期ごとに締切が異なる等）は、そのうち最も早い日付を採用する — この値は再チェックを促すためのフィールドであり、遅すぎるより早すぎる方が安全という判断（詳細は日付選定を含め `.claude/skills/wikicommit-generate/SKILL.md` Pass 2 のルール一覧を参照）。Pass 3 はこの値を非 null のときのみページの `expires_at` frontmatter に書き込み、`null` のときは既存ページの `expires_at`（あれば）を変更しない。Pass 4（ソース整合性レビュー）は `expires_at` も他の主張と同様にソースとの照合対象に含める。
- `coverage_gap_note`（Issue #284）は、そのエンティティの型スキーマファイルの `properties:` ブロック（Issue #495）に受け皿がないドメイン固有の具体的な属性（対象年齢・道具・管轄自治体等）がソース本文に含まれていた場合のみ、単一の文字列として設定する（`exclude_note` と同じく配列にしない。1エンティティで複数の属性が不足していても1文にまとめる）。`create`/`update` エンティティのみが対象で、`exclude`/`ambiguous` エンティティには設定しない。何も不足がなければ `null`（通常はこちらが大半を占める想定）。1件以上存在する場合、`summary` と同じタイミングで管理ファイルの `## Generation Notes` に書かれる（エンティティごとに1文。Issue #831 — 以前は `## Summary` に追記していたが、そこは公開される唯一の節であり内部識別子が読者に届いていた）。`summary` と同じ言語（＝ `primary_lang`）で書く（Issue #314）。スキーマファイル（`.wikicommit/schema/`）への書き込みは一切行わない — 本フィールドは証拠収集のみを目的とし、ページ本文には従来通りその情報を書く（`## Generation Notes` の記載場所自体は `docs/DesignDoc-data.md` §4.3 の ソース管理ファイルフォーマット参照）。
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
返却された `summary` を管理ファイル body の `## Summary` に上書きし、`exclude_note`/`coverage_gap_note` は `## Generation Notes` に分けて書く（`## User Notes` は変更しない。Issue #831）。

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

SKILL.md はエージェント（Claude Code）への指示書であり、実際に Bash コマンド文字列を組み立てて実行するのはエージェント自身である（§11.0）。GitHub Issue のタイトル・本文、`wikicommit-init` の `theme` プロンプト回答のように、SKILL.md の記述者が内容を制御できない自由記述テキストを CLI 引数に埋め込む手順を SKILL.md に書く場合、そのテキストにシェルメタ文字（`` ` ``・`$(...)`・`!`・`"` 等）が含まれていると、単純な `--flag "<text>"` のダブルクォート埋め込みではコマンドインジェクションが理論上成立しうる（Issue #375。`wikicommit-init` の `--theme "<theme text>"` を含む 2 箇所で実際に指摘された）。

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

> **実行時に生成された散文の側は、検出する仕組みを作らないと決めた（Issue #863）**: 上の限界は、フェンス済みテンプレートに 1 文字も書かれていない文言 — エージェントがその場で組み立てた散文 — には原理的に届かない、というものである。Issue #831 が実際に踏んだのはこちら側で、Pass 2c が実行時に書いた散文に `.wikicommit/entity-policy.md`・`exclude_living_persons`・`SoftwareApplication.md` の `properties:` といった内部識別子が混ざり、公開サイトへ出ていた。**この失敗クラスを検出する仕組みは作らない。**
>
> **理由の第一は、検出が効きすぎることである**。候補の識別子（`.wikicommit/` で始まるパス・`exclude_living_persons` 等の設定キー名・`granularity`・`generated_with`・`primary_lang`・`/wikicommit-*`・`Pass N`・`Step N`・`properties:`・`review_status`）を、このリポジトリ自身の Wiki の本文（frontmatter を除く）に当てると **9 ページ中 6 ページが点灯し、6 件とも誤検知ではなく書くのが正しい記述だった**（`byollm.md`・`orphan-page.md`・`quality-gate.md`・`review-status.md`・`script-delegation-pattern.md`・`wikilink.md`）。母数から `index.md` を外しているのは、それがビルド生成のナビゲーションページであり、`collect_entity_pages()` が既定でこれを走査対象から除いているためである — 本文の散文を見るチェックはこの既定に従う（`check_orphans.py`・`search_index.py`・`check_self_referential_tags.py` 等）。`include_index=True` を渡す 3 箇所（`rebuild_index.py`・`check_wikilinks.py`・`check_wanted_pages.py`）はいずれもリンク・索引の帳簿を見るものであり、本文を読む側ではない。なお現ツリーの `index.md` は Issue #678 より前の書式（`[[DefinedTerm/review-status]] — review_status`）のまま残っているため走査すれば `review_status` に一致するが、`rebuild_index.py` は現在 `- [[Type/slug]]` だけを書くので、再構築すれば一致は消える — 数え直す際はここで取り違えないこと。`review-status.md` は `review_status` を定義するページであり、その語を書くことがそのページの仕事である。`orphan-page.md` は「`.wikicommit/entity/` 内でどのページからも参照されていないページ」と説明しており、パスを書かなければ定義にならない。
>
> **識別子は文字列としては確かに文脈に依存しない**（列挙でき、検出も効く）。効かないのはその次で、**検出したものが欠陥かどうかを識別子の側が何も語らない** — 判定に要るのは「そのページの主題がその識別子か」であり、それは文字列からは分からない。Issue #552 / #550 が `granularity` のプローズ整合検査について到達した限界（正規表現は肯定・否定の文脈を区別できない）と、形は違うが同じ壁である。
>
> **非ブロッキングに落としても解けない**。6/9 は `check_orphans.py` の `ORPHAN:` のような「報告するがブロックしない」形が耐えられる水準を超えており、Issue #562（低情報密度ガードの降格）・#760（`RISKY:` を standing 1 件に絞る）・#867（`POLICY_DRIFT:` の 1 行を退ける）がいずれも到達した「**常時点灯する所見は読まれなくなる**」に正面から当たる。しかもこのリポジトリに固有の偏りではない — ソフトウェア・設定・ファイルパスを主題に含む Wiki は同じように点灯する。
>
> **そして実害を出した経路は既に閉じている**。LLM が**自分の実行について**散文を書く箇所はパイプライン上 2 つで、**どちらも公開されない**。1 つは Pass 2c の `exclude_note` / `coverage_gap_note` で、これがまさに Issue #831 で `## Generation Notes` へ移り、`_write_source_page()` のホワイトリストにより非公開になった箇所である。もう 1 つは Pass 1 / 3 / 4 が書く `## Failure Reason`（「このソースの抽出に失敗した」等）で、同じホワイトリストが最初から `## User Notes` と並べて公開対象外にしている — `wikicommit-generate/SKILL.md` 自身の Issue #831 の注記がこの 2 つを並べて名指ししている。残る 2 経路（Pass 3 のページ本文・Pass 2a の `## Summary`）が書くのは**ソースについて**であって実行についてではなく、そこに内部識別子が現れるのはソースがそれに言及している場合 — すなわち上記 6 件と同じ正当な記述の場合にほぼ限られる。Pass 3 の「そのソースが何を言っていないかを本文に書かない」というルール（Issue #571）が、この実行について書くことを既に禁じている。
>
> **生成時の指示（Pass 3 / Pass 2c への追記）も足さない**。§11.8 と Issue #571 に続く 4 度目の言い換えになり、`wikicommit-generate/SKILL.md` は §11.6 の実測で `/wikicommit-generate` の固定オーバーヘッド約 51K トークンのうち**約 47K** を占めている。Issue #722 が「証拠拘束の言い直しを 4 度目として足さない — 足すのは行動の側だけ」と決めたのと同じ理由である。**この段落は、同じ提案が「見落とし」として再び立つのを防ぐために置いてある。**

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
