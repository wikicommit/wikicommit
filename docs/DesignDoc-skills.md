# WikiCommit — Skills 設計（MVP）

> **対応DesignDoc**: 元 §11  
> スクリプト詳細仕様は [DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) を参照。
>
> このファイルは**いま何が仕様か**を書く。各判断の経緯（以前の挙動・採らなかった案・実測の記録・Issue 番号ごとの議論）は [history/DesignDoc-skills.md](history/DesignDoc-skills.md) の同じ見出しの下にある。

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
| **マルチステップフロー** | エージェントが動的に組み立て（長い多段の Skill では順序をドライバーが持つ。下記） | コードが順序を固定 |
| **出力形式の契約** | SKILL.md に明示が必要（エージェントは自由に動くため） | コードが出力をパース・強制 |
| **再現性・網羅性** | スクリプト委譲を SKILL.md に明示すれば保証できる（§11.5） | コード構造上、常に決定論的 |
| **LLM 推論をユーザーが持ち込むか** | 両方で可能（独立した軸） | 同左 |
| **導入コスト** | SKILL.md を書くだけ | アプリ実装が必要 |
| **デバッグ** | エージェントの動作を観察 | コードをステップ実行 |
| **Phase 4: SaaS** | `workflow_dispatch` API で GitHub Actions を起動し claude-code-action を実行。PR フローと自然に統合できる。非同期・GitHub 依存・ランナー起動レイテンシあり。**公式ドキュメントで `.claude/skills/` の SKILL.md が明示的にサポートされており、Phase 1–3 の SKILL.md をそのまま利用可能**（要 `actions/checkout`） | サーバーサイドで Claude API を直接呼ぶ。SKILL.md をシステムプロンプトに転用。低レイテンシだが自前インフラ管理が必要 |
| **Phase 4: Tauri デスクトップアプリ** | Tauri（Rust + WebView、PC 専用）からローカルの Claude Code をサブプロセス実行。追加インフラ不要・ユーザー自身の LLM 契約をそのまま使える・低レイテンシ。Phase 1–3 の設計をほぼそのまま継承できる | デスクトップアプリから Claude API を直接呼ぶ。SKILL.md をシステムプロンプトに転用 |
| **代表実装** | WikiCommit / nvk/llm-wiki / wastedcode/memex | nashsu/llm_wiki / atomicstrata / Kompl |

- API 直接呼び出し型の実装を参考にする際、その多段生成フローをそのまま SKILL.md に写す必要はない。パスの細かい制御はエージェントが自律的に行える。
- SKILL.md には「何を達成してほしいか」と「守るべき制約」を記述する。**実行順序は、工程が少なく短い Skill ではエージェントに委ねるが、長い多段の Skill ではスクリプト（ドライバー）が持つ**（下記「多段の Skill の進行はドライバーが持つ」）。**各工程の中の判断はどちらの場合もエージェントに委ねる。**
- ただし nashsu の `---FILE: path---` 境界プロトコルのような**出力形式の契約**は明示する。エージェントがどう実行するかは自由でも、何を出力するかは決定論的に定める必要がある。

#### 多段の Skill の進行はドライバーが持つ — 判断はエージェントが持つ

長い手順をエージェントの記憶で組み立てると、末尾の工程の抜け・書き戻しの漏れ・結果の受け渡しの欠落・散文でしか書かれていない部分の即興が起きる。そのため `.wikicommit/scripts/driver.py` が工程の**順序**を持つ。エージェントとの接点は CLI で、`next` が次の工程を 1 つだけ JSON で返し、エージェントはその工程の手順ファイルを読んで実行し、`done` で報告する。実行記録（`record_run.py`）は進行を**記録**するが次に何をすべきかは指示しないので、順序の担い手にはならない。

| 役割 | 担い手 |
|---|---|
| 次に何をするか | ドライバー（工程の定義 `workflow.yaml` から、実行記録のログを毎回リプレイして決める。ドライバー自身は状態を持たない） |
| 工程が完了したか | ドライバーがディスクを見て判定する（工程ごとの確認スクリプト）。報告だけでは完了にしない。手順ファイルの `pass_token` もドライバーが自分でファイルを開いて照合し、合わなければ完了にしない |
| 工程の中の判断 | エージェント（手順ファイルを読んで行う） |
| 人への質問 | 工程の定義の `human` 工程。非対話実行では定義が既定の答えを持つ（§11.5「非対話実行が人間の判断に当たったときの扱い」の保留と一致） |
| 記録 | ドライバーが書く。「ここでログを書け」という指示はそれ自体が忘れられる工程になるため、エージェントには書かせない |

**強制の層は 4 つある**: ① `done` は今の工程にしか受け付けない、② 完了はディスクで確かめる、③ `/wikicommit-merge` が、開いたままの実行が触れたファイルを含む変更を止める（`driver.py check-merge`。ハーネスに関係なく効く唯一の点）、④ Stop フック（使えるハーネスでだけ。下記）。③が止めるのは「未完了の実行があるか」であって「すべての変更がドライバーを経たか」ではない — `fix` / `remove` / `review` と手編集はドライバーを使わない正当な経路であり、保留・halt で終わった実行は終わった実行である。実行の記録は git で追跡しないので、③は merge を実行したマシンの実行しか見えない。

**エンジンは WikiCommit 固有の知識を持たない。** パス・`status` の値・パスの名前は各 Skill の工程の定義（`<skill>/workflow.yaml`）と確認スクリプト（`<skill>/scripts/workflow_checks.py`）にある。分岐や完了の条件は YAML に書かず、スクリプトを指定する — 表現力を上げると独自の言語を作ることになるため。保存は `record_run.py`（実行記録の `driver:` キー）に任せるので、`check_run_records.py` はそのまま読める。

**段階 1 ではサブエージェントを使わない。** 各工程はメインのエージェントが行い、ドライバーが決めるのは「次に何をするか」だけである。Pass のサブエージェント化を採らない判断（§11.6）には触れず、Pass 2c → Pass 3 の受け渡しの問題も生じない。

**捏造には耐えない。防ぐのは「忘れる」「飛ばす」であって「偽る」ではない。** エージェントはドライバーと同じサンドボックスでシェルとファイル書き込みの権限を持つので、実行記録の書き換え・工程を行わずに確認が見るファイルを書くこと・`pass_token` の行だけを grep して渡すこと・チェックそのものの書き換えは、いずれも技術的にはできる。**同じ環境にいる限り、スクリプトはエージェントの行為と自分自身の行為を区別できない。** したがってここで作るのは証明ではなく**整合性の確認**であり、それで足りるとする（実際に起きてきた失敗は「抜けた・漏れた・渡し忘れた・即興で誤った」であって「偽った」ではなく、偽るには工程を行うより手間がかかり痕跡が会話と Git の差分に残る。`Reviewed-by` トレーラーを「実害の起点はリポジトリの権限管理に帰着する」と整理した `docs/DesignDoc-pipeline.md` §6.7 と同じ立場）。取り込んだ外部文書によるプロンプトインジェクション（「この工程は完了したものとして記録せよ」）は、②がファイルが実際に書かれたかを見ること、Pass 4 と人のレビューが内容を見ることで、ドライバーの無い場合と同じ水準で防ぐ。ドライバーはこのリスクを増やしも減らしもしない。

**確認の強さは工程によって違う。** Pass 3 はディスクに何も書かない（Pass 4 のレビューの後に書く）ので、その完了はエージェントの報告だけで決まる。Pass 1 の `extracted_tokens` は前回の実行の値が残っていても通る。いずれも「その工程が走ったか」ではなく「走った後に在るはずのものが在るか」を見る確認であり、Pass 3 の出力は次の Pass 4 の確認（管理ファイルの最終 `status`・`generated_pages` の各ページの実在・レビュー記録の存在）が受け止める。Pass 4 の確認が、書き戻しの漏れを工程の時点で止める。

**Stop フック（Claude Code の設定例）**: エージェントが途中で終わろうとしたときに止める補助である。**これに頼らない** — フックが無くても、ドライバーの `next` で続きから再開でき、③の出口で未完了の成果物は止まる。Codex でも Stop フックは使えるが利用者がフックの定義を信頼する手順が要り、Copilot で使えるかは確かめていない。

```json
{
  "hooks": {
    "Stop": [
      {"hooks": [{"type": "command",
                  "command": "python .wikicommit/scripts/driver.py status --stop-hook"}]}
    ]
  }
}
```

`status --stop-hook` は標準入力のペイロードを読み、開いた実行があれば `{"decision": "block", "reason": "..."}` を返す。同じ停止の試みの中での 2 回目（`stop_hook_active`）は通す — 死んだセッションの実行が後のセッションを無限に止め続けないためで、理由の文面が `abandon` の手順を案内する。

工程の順序を外部のフレームワーク（LangGraph 等）に持たせない（フレームワークが LLM を呼ぶ側に立ち、LLM の持ち込みを手放す）。スクリプトが `claude -p` 等を子プロセスで起動する形も採らない（途中で利用者に尋ねられず、ハーネス差の吸収が要り、シェルの時間制限を超える）。ドライバーを使うのは現在 `wikicommit-generate` だけである。

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
                     schema/（base_types を展開 + theme 駆動の型提案）
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

**`--depth 1` を付ける。** `install.sh` が使うのは `.claude/skills/` だけであり、履歴は要らない（フル clone は `.git` だけで数十 MB になる）。`.claude/skills/` だけに絞る `--filter=blob:none --sparse` + `sparse-checkout` は案内しない — git 2.25+ が要り、一般向けの案内としては複雑さが見合わない。

**単体の `curl -sSL <url> | bash` は提供しない。** `install.sh` は自分自身と同じディレクトリにある `.claude/skills/`（wikicommit リポジトリ本体）を相対パスで探すため、単一ファイルとして取得すると `.claude/skills/` が見つからずエラー終了する。単体コマンドでのインストール体験は `npx skills add` 側が担う。

`npx skills add` は Vercel Labs が npm パッケージとして配布する Skills 管理 CLI（`vercel-labs/skills`）。Claude Code・Cursor・Codex など 40+ エージェントに対応する。

#### 配置方式と `--copy`

`npx skills add` は、**2 つ以上のエージェント（正確には 2 つ以上の異なる skills ディレクトリ）を同時に対象にした場合**、Skill の実体を `<project>/.agents/skills/<name>/` に置き、各エージェントのエントリ（`<project>/.claude/skills/<name>` を含む）をそこへの**相対シンボリックリンク**にする（本節「`npx skills add` 仕様確認結果」項目7）。この配置は WikiCommit の前提と 2 箇所で噛み合わない:

1. **host → container の境界をまたげない**。ホスト側にこの方式で配置してから devcontainer を作成すると、コンテナ内から Skills が認識されない（実体コピーの `install.sh` では起きない。機構は特定していない）。
2. **Git 管理の前提と食い違う**。シンボリックリンクのままコミットすると、リンク先の `.agents/skills/` も併せてコミットしない限り clone 先でリンク切れになる。WikiCommit 経由のコミット（`/wikicommit-init`・`/wikicommit-update`）は `.agents/` と `skills-lock.json` もステージするのでこの壊れ方は起きない（下記）。**Windows では今も壊れる**: `core.symlinks=false`（Windows の既定）で clone するとシンボリックリンクがリンク先のパスを書いたテキストファイルになり、`.claude/skills/<name>` が Skill として読めない。`skills-lock.json` は `--copy` の使用有無を記録しないので、`experimental_install` による復元もシンボリックリンクで行われる（項目3）。

**方針**: ドキュメント（README・`README_ja.md`）が案内する `npx skills add` のコマンド例には **`--copy` を付ける**（README の「Why `--copy`?」はコンテナ境界と Windows の 2 点を理由に挙げる）。`--copy` は上記 2 点の両方に効き、`install.sh`（実体コピー）と同じ配置になるため、2 つのインストール方法の間で「インストール後の `.claude/skills/` がどうなっているか」が揃う。コピー方式では対象エージェントごとに独立した実体が作られる（`.agents/skills/` 側の実体は、対象に universal エージェントが含まれない限り作られない）。Skill は SKILL.md と小さな `scripts/` のみで構成され合計 3MB 程度のため、重複コストは問題にならない。**ただし `--all`（＝ `--skill '*' --agent '*' -y`）と `--copy` を組み合わせてはいけない** — コピー方式は「プロジェクトに存在しないエージェントディレクトリは作らない」というスキップ判定を経ないため、対応する約 50 個すべてのエージェントディレクトリに全 Skill の実体コピーが作られる。README の一括インストール例は `--skill '*' --agent claude-code -y --copy` としてエージェントを明示する（`--skill '*'` は `--all` と同じく内部限定 Skill を除外するため、対象集合は変わらない）。

**方針（補足）**: `--copy` は既定の挙動を上書きするものであり、`npx skills add` の既定は将来変わりうる。したがって devcontainer / GitHub Codespaces のようにファイルシステム境界をまたぐ環境では、**コンテナに入った後にインストールする**という手順上の指針も併せて案内する。両者は排他ではなく、重ねて適用してよい。

**symlink 配置のリポジトリでは `.agents/` と `skills-lock.json` が追跡対象である。** そこでは `.agents/` はビルド成果物ではなく Skills の実体そのものであり、`.claude/skills/<name>` はそこへの相対シンボリックリンクにすぎない（`.claude` だけをコミットすると**リンクだけのツリー**が clone に届く）。`skills-lock.json` はインストールした内容の記録でありリンクの解決には関与しないため、どちらか一方で代替できない別のパスである。

- 両者は `_root_outputs.py` に `origin="install"` / `update="skip"` / `compare="none"` で載る（`.claude` と同じ答え — init.py が書くものでも、refresh するものでも、比較するものでもない）
- あわせて `may_be_absent` を持つ。`install.sh` で入れたリポジトリには `skills-lock.json` が無く、実体コピー配置には `.agents` が無いので、選択的な `git add` の列挙にそのまま並べると abort-on-missing に当たる。init の印字は既定が `git add -A` なのでこの問題を持たず、既存リポジトリ向けに残した選択的な列挙には「無いものは落とせ」という caveat が submodule のパス（`.gitmodules` / `quartz`）と同じ 1 文で両者を覆う
- `/wikicommit-update` の `git add` も 2 つのパスを含む
- symlink 配置を `--copy` へ移行して `.agents` を消すことはしない（`.agents/` が孤児として残り、既に symlink 配置でコミット済みのリポジトリには別途の移行手順が要る）。Skill 側は現実の配置を扱えなければならない

#### Windows 対応方針

Skills 本体（`.wikicommit/scripts/*.py` 等）は Claude Code の Bash ツール経由で実行される。Claude Code 自体が Windows では WSL または Git Bash（Git for Windows 同梱）を前提としているため、Skills 側で追加のクロスプラットフォーム対応は不要と判断する。`.py` スクリプトは Python + `hashlib` + git subprocess ベースで bash 依存がなく、Git Bash・WSL のいずれからでも動作する（Python 自体はどちらのシェルからも呼び出し可能）。

この結論は **SKILL.md に明記された呼び出し方（シェルからの直接実行）に従う場合に限る**。大量ファイル対応等でエージェントが SKILL.md の指示を離れて独自の Python `subprocess` ラッパーを即興で書いた場合はこの限りではない。特に `npx` は Windows では `.cmd` シムのため、`subprocess.run(['npx', ...], shell=False)` は `FileNotFoundError` になる（`shell=True` またはフルパス指定が必要）。WikiCommit 本体側で将来 Windows 向けの補助スクリプトを書く場合も同様の注意が必要。

Windows 固有の考慮が必要なのは、Claude Code / Skills が使える状態になる前に人間が直接ターミナルで実行する `install.sh`（Step 1 のブートストラップ）のみである。これは bash 専用スクリプト（`set -euo pipefail`・配列・`${BASH_SOURCE[0]}` 等）で PowerShell / cmd.exe から直接実行できないが、Claude Code 自体を使うのに元々 Git Bash / WSL が必要という前提に乗る形で足りるため、PowerShell 版の用意や Python 実装への置き換えといった追加対応は行わない。

#### `npx skills add` 仕様確認結果

ソース: `vercel-labs/skills` の `src/skills.ts`・`src/blob.ts`・`src/skill-lock.ts`（2026-07 時点）と実機検証（`skills` CLI v1.5.23 / 2026-08-28 再確認）。**項目 3・4・7 は実機で確認した挙動であり、残りはソースコード調査に基づく** — この節を根拠にする際はこの区別を保つこと（ソース調査だけの記載が実機と食い違っていた前例がある）。

1. **リポジトリの読み取り方法**: 追加のマニフェストファイルは不要。`.claude/skills/<name>/SKILL.md`（`name`・`description` フィールドを持つ YAML frontmatter）が存在すれば、優先ディレクトリ一覧（`skills/`・`.claude/skills/` 等。`src/skills.ts` の `AGENT_PROJECT_SKILL_DIRS`）の 1 つとして深さ2までの探索で自動検出される。WikiCommit の構成（`.claude/skills/<name>/SKILL.md`）はそのまま要件を満たしている
2. **`--skill <name>` の名前解決**: `SKILL.md` frontmatter の `name:` フィールドと完全一致（大文字小文字は正規化）。WikiCommit の全 SKILL.md は `name:` を設定済み
3. **ロックファイル**: プロジェクトレベルのインストールでは、**インストール先プロジェクトのルート直下に `skills-lock.json`** が生成される（`~/.agents/.skill-lock.json` 等ホームディレクトリへの保存は `-g` / `--global` のグローバルインストール側の話で、既定のプロジェクトインストールでは作られない）。記録されるのは skill ごとの `source` / `sourceType` / `skillPath` / `computedHash` で、**`--copy` を使ったかどうかは記録されない** — したがって `experimental_install` によるロックファイルからの復元は既定の配置方式（シンボリックリンク）で行われる。提供側リポジトリ（WikiCommit）が用意すべきファイルではない
4. **private リポジトリ対応**: 対応している。`GITHUB_TOKEN` / `GH_TOKEN` 環境変数、なければ `gh auth token`（`gh` CLI ログイン）の順でトークンを解決し、GitHub Trees API に Bearer 認証で問い合わせる（`src/blob.ts` の `fetchRepoTree`）。匿名リクエストは public リポジトリに対してのみ機能し（60 req/hr の IP レート制限あり）、private リポジトリは 401/404 を返すためトークンで自動リトライされる。**取得経路は 2 本ある**: Trees API + `raw.githubusercontent.com` によるブロブ取得（`tryBlobInstall`）が第一経路で、これが失敗した場合（API 到達不能・認証不足等）と、`<repo>@<ref>` のように ref を固定した場合は `git clone --depth=1`（`gh` CLI 経由 → HTTPS → SSH の順にフォールバック）へ切り替わる。clone は shallow clone であってフルクローンではない
5. **`.claude-plugin/marketplace.json` 等の追加マニフェスト**: `npx skills add` 単体では不要。Anthropic 自身の Plugin マーケットプレイス掲載（下記）では `.claude-plugin/plugin.json`（マーケットプレイス自体を自前運営する場合のみ `marketplace.json` も）が必要
6. **内部限定 Skill の除外機構**: SKILL.md frontmatter に `metadata:\n  internal: true` を付与すると、`npx skills add <repo>`（Skill 名を指定しない一括インストール）から除外される。`--skill <name>` で名指しされた場合や `INSTALL_INTERNAL_SKILLS=1` 環境変数を立てた場合は対象になる。WikiCommit 本体開発専用の内部限定 Skill（`install.sh` の配布対象一覧にも含まれていない）にこのフラグを付与し、`npx skills add wikicommit/wikicommit` の一括インストールで入る集合を `install.sh` の配布対象（`SKILLS` 配列が正）と揃えている
7. **`.claude/skills/` への配置方式**: 配置方式は「シンボリックリンク」と「コピー」の2つで、`--copy` なしの既定は**対象エージェントの数で分岐する** — 異なる skills ディレクトリを持つエージェントを2つ以上対象にした場合はシンボリックリンク方式（Skill の実体を `<project>/.agents/skills/<name>/` へ書き、各エージェントのエントリを `../../.agents/skills/<name>` への**相対シンボリックリンク**にする）、対象が1つだけの場合（選択画面で Claude Code のみを選んだ場合など）は指定の有無に関わらずコピー方式になる。コピー方式では対象エージェントディレクトリごとに独立した実体が書かれ、`.agents/skills/` へは何も書かれない（対象に universal エージェントが含まれる場合のみ、その1つとして作られる） — したがって `--copy` は「複製を1つ増やす」オプションではなく「canonical 集約をやめて各エージェントに実体を配る」オプションである。あわせて、コピー方式はシンボリックリンク方式が持つ「プロジェクトに未作成のエージェントディレクトリはスキップする」判定を経ないため、`--agent '*'`（`--all`）との併用は対応エージェント全数分の実体コピーを作る。この方式が WikiCommit の前提と噛み合わない2つの場面（コンテナ境界・Git 管理）と、それに対する方針は §11.1「配置方式と `--copy`」を参照

#### Anthropic Plugin マーケットプレイス掲載要件の調査結果

ソース: `code.claude.com/docs/en/plugins`・`/en/plugins-reference`・`github.com/anthropics/claude-plugins-official`（2026-07 時点）。

1. **「Skills 専用マーケットプレイス」は存在しない**: Anthropic 公式ドキュメント上、Skill は Claude Code の **Plugin システムの 1 コンポーネント種別**（他に agents・hooks・MCP servers 等）として扱われ、配布単位は常に「Plugin」。掲載も Skill 単体ではなく `.claude-plugin/plugin.json` を持つ Plugin 単位で行う
2. **公式マーケットプレイスは 2 系統**:
   - `claude-plugins-official`: Anthropic 自身が厳選する公式マーケットプレイス。**申請フォームは存在せず、掲載可否は Anthropic の裁量**。Claude Code 初回起動時に自動登録される
   - `claude-plugins-community`（`anthropics/claude-plugins-community`）: 第三者提出をレビュー後に掲載する公開コミュニティマーケットプレイス。**WikiCommit が対象とするのはこちら**
3. **申請手順（`claude-plugins-community`）**:
   - 個人開発者（Team/Enterprise 組織なし）: Console フォーム [platform.claude.com/plugins/submit](https://platform.claude.com/plugins/submit)
   - Team/Enterprise 組織あり: claude.ai フォーム [claude.ai/admin-settings/directory/submissions/plugins/new](https://claude.ai/admin-settings/directory/submissions/plugins/new)（組織 Owner はデフォルトでアクセス権あり）
   - WikiCommit は個人開発のため Console フォームを使う想定
4. **提出前チェック**: `claude plugin validate <path>` をローカルで実行する。レビューパイプラインは同一チェック + 自動安全性審査を実行する。`--strict` を付けると警告もエラー扱いになるが、提出時に必須なのは無印の `validate` の PASS（`✔ Validation passed with warnings` でも可）
5. **承認後の反映**: 承認された Plugin は `anthropics/claude-plugins-community` の `marketplace.json` に特定コミット SHA で pin され、以後のコミットに応じて CI が自動でその pin を更新する。カタログは夜間同期のため、承認からインストール可能になるまで遅延がありうる（掲載確認はカタログの `marketplace.json` を検索する）
6. **前提条件**: リポジトリが public であること（`anthropics/claude-plugins-community` からコミット SHA 参照するため）
7. **`npx skills add` との関係**: 重複しない。`npx skills add` は vercel-labs 製の別 CLI・別エコシステム（agentskills.io 標準）であり、Anthropic 公式の Plugin マーケットプレイスとは無関係の並行した配布経路。両者とも既存の `.claude/skills/<name>/SKILL.md` レイアウトをそのまま使えるが、**Plugin マーケットプレイス側だけ `.claude-plugin/plugin.json` という追加マニフェストが必須**という差分がある
8. **リポジトリ側の対応**: リポジトリルートに `.claude-plugin/plugin.json` を置く。`skills` フィールドに `.claude/skills/<name>/` を `install.sh` の配布対象と同一集合で明示的に列挙することで、ディレクトリ構造を変更せず・内部限定 Skill を含めずに済む（`skills` フィールドは「デフォルトの `skills/` スキャンに追加」する仕様のため、個別パスを列挙すれば任意のサブセットだけを対象にできる）。`version` フィールドは設定する（掲載時に `claude plugin validate` が未指定を warning にする）。`version` を明示するとピン留めになり bump を忘れると更新が静かに止まる（省略すれば SHA フォールバックで配布 push のたびに新版として検知される）ので、版を上げるときは `_version.py`・`plugin.json`・`CHANGELOG.md`・`.claude/skills/wikicommit-init/CHANGELOG.md` をまとめて更新し、前二者の同期を `tests/test_version_sync.py`、後二者の一致を `tests/test_changelog_sync.py` が強制する（更新箇所の正本は `CHANGELOG.md` 冒頭）。もう一つの source of truth（`.wikicommit/scripts/_version.py`。インストール先の wiki リポジトリまで届く唯一の情報源で、`config.yml` の `wikicommit_version`・ページの `generated_with` / `translated_with` の値はすべてここから読む）については `docs/DesignDoc-data.md` §3.3・§4.1 を参照。`claude plugin validate .` が出す「リポジトリ直下の `CLAUDE.md` は Plugin コンテキストとしてロードされない」旨の warning は想定内である（Plugin へのコンテキスト提供は Skill 経由で行う設計）

#### Skills エコシステムの構成

```
Anthropic
  ├─ agentskills.io 標準を策定（SKILL.md 形式・frontmatter 仕様）
  ├─ github.com/anthropics/skills — 公式 Skills リポジトリ（pdf / docx / pptx / xlsx 等）
  ├─ claude-plugins-official — Anthropic 自身が厳選する公式 Plugin マーケットプレイス（申請不可・裁量制）
  └─ claude-plugins-community — 第三者提出をレビュー後に掲載する公開 Plugin マーケットプレイス

Vercel Labs
  └─ vercel-labs/skills — agentskills.io 標準の CLI 実装（npx skills add。Anthropic 公式 Plugin マーケットプレイスとは別経路）

WikiCommit
  ├─ npx skills add wikicommit/wikicommit でインストール可能にすることが Phase 3 の目標
  └─ .claude-plugin/plugin.json 経由で claude-plugins-community への掲載申請が可能な状態
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

#### `description` の書き方 — 「何をするか」と「いつ使うか」の両方を書く

公式ガイダンス（`skill-creator`）は `description` を **triggering の唯一の機構**と位置づけ、"All "when to use" info goes here, not in the body" と明記し、さらに「Claude は Skill を **undertrigger** しがちなので description は少し **pushy** に書け」としている。

**この規則が当たるのは、モデルが自律起動しうる Skill だけである。** 配布 Skill のうち `disable-model-invocation: true` を持つものは、Claude Code では人間が `/wikicommit-xxx` と打つことでしか起動しない — そこでは description の triggering 機能が働かないので、「いつ使うか」を書いても Claude Code では誰も読まない。**標準と突き合わせる人が、フラグを持つ Skill を「違反している」と読まないよう、ここに記録しておく。**

| | 件数 | 扱い |
|---|---|---|
| `disable-model-invocation: true` を持つ | 11（`collect` / `fix` / `init` / `organize` / `reconcile` / `relate` / `remove` / `review` / `schema-propose` / `synthesize` / `update`） | **Claude Code では対象外。** モデルが自律起動しないので triggering は働かない。**ただし Codex ではこの除外が成り立たない**（下記） |
| 持たない配布 Skill | 8（`ask` / `generate` / `merge` / `quiz` / `search` / `serve` / `status` / `translate`） | **対象。** 「いつ使うか」を書く |

**フラグの有無は「読み取り専用か」では決まらない。** 書き込み系の `generate` / `merge` / `translate` はフラグを持たない。フラグは 2 つの仕事を兼ねる — (i) 通りすがりの依頼で自律発火しないこと、(ii) 人以外のあらゆる起動経路を塞ぐこと。(ii) は無人運用の経路を丸ごと消す: 公式ドキュメントが挙げるのは description 一致による自律ロード・**サブエージェントへのプリロード**・**スケジュール実行の発火**の 3 つであり、加えて Skill ツールからの明示起動も（フラグを持つ Skill がモデルに一覧表示されないという別の機構の帰結として）塞がる。残るのは人が `/name` と打つ経路だけである。無人実行の経路を閉じる 3 本はこれを持てないので、(i) は description（全リポジトリに届く）と `skillOverrides`（リポジトリごと・運用者が持つ）が担う。フラグを持つのは**無人経路そのものを一切望まない Skill** に限る（`collect` は登録前の人間承認が設計の中核であり、`fix` / `remove` は `merge` 経由で PR を作る側である）。

**上表の「対象外」は Claude Code に固有の判断である。** `disable-model-invocation` は Claude Code の frontmatter キーであり、**Codex はこれを読まない**（Codex が SKILL.md の frontmatter から認識するのは `name` と `description` の 2 つだけ）。Codex ではフラグを持つ Skill でも description が暗黙起動を決める材料になり、どれも書き込みを伴うので、暗黙起動した 1 本が残した変更に続けて `merge` が起動すれば既定ブランチまで届きうる。したがって**フラグを持つ配布 Skill は全件、description に「明示的に頼まれたときだけ使え・いつ使うな」を書く**（`Use this only when someone explicitly asks …` と `do not use it …`。代わりに呼ぶべき読み取り専用 Skill を名指しする）。向きは pushy ではなく `generate` / `merge` と同じ**止める側**である。Claude Code 側の代償はほぼ無い（それらはモデルに一覧表示されないので、変わるのは `/` メニューの説明文だけ）。`tests/test_skill_descriptions.py` がフラグを持つ配布 Skill 全件についてこの 2 句を固定する。

#### 自律起動を絞る手段は 2 層あり、所有者が違う

フラグを持たない書き込み系 3 本について、(i) を担うのは次の 2 つである。**フラグが配布物（`npx skills add` が上書きする）にあるのに対し、下段はそのリポジトリ自身の設定にあり、運用者が持ち続けられる。**

| 層 | 手段 | 届く先 |
|---|---|---|
| ① | `description` を絞る | **全リポジトリ**。`npx skills add` で既存の Wiki にも届く |
| ② | `.claude/settings.json` の `skillOverrides` | **そのリポジトリだけ**。新規リポジトリには `/wikicommit-init` が配る（`docs/DesignDoc-data.md` §3.1） |

**エージェントごとにどの層が効くかは違う。** 上の 2 層と frontmatter のフラグ（③）は、いずれも Claude Code を前提に組まれている:

| | 手段 | Claude Code | Codex | 置き場 |
|---|---|---|---|---|
| ① | `description` | 効く（フラグを持たない 8 本のみ。11 本は一覧表示されない） | **効く（配布 Skill すべて）** | SKILL.md |
| ② | `.claude/settings.json` の `skillOverrides` | 効く | **効かない**（Claude Code の設定ファイル） | リポジトリ |
| ③ | `disable-model-invocation: true` | 効く | **効かない**（Codex は読まない） | SKILL.md |
| ④ | `agents/openai.yaml` の `policy.allow_implicit_invocation: false` | 読まない | **効く見込み**（明示起動 `$skill` は通る） | Skill ディレクトリ |

**④ は ③ を持つ Skill にだけ置く。** キーは `policy:` の下に置く — トップレベルに書くと読まれない（OpenAI 公式の `openai/skills` の実ファイルが `policy:` の下に持つ）。`install.sh`（`find -type f`）・`.claude-plugin/plugin.json`（ディレクトリ単位）・公開スナップショット（`.claude/skills/wikicommit-*` の glob）は変更なしで運び、`npx skills add` は `--agent codex` / symlink 方式 / `--copy` / 再 `add` / lock からの復元のいずれでも残す（2026-09-24。`skills` CLI v1.7.0 で確認）。**利用者が手で足した `agents/openai.yaml` は再インストールで Skill ディレクトリごと置き換わって消える**ので、配布物に入れる以外に恒久的な形は無い。

**④ が実際に暗黙起動を止めるかは実機で確かめていない。** OpenAI 公式の `migrate-to-codex` は `disable-model-invocation` を「直接の対応物なし」とし、`policy.allow_implicit_invocation` を「意図は近いが同じ意味ではない」としている。①をフラグを持つ Skill でも書くのはそのためで、④が効かなかった場合でも description が判断材料として残る。**`tests/test_skill_descriptions.py` が ③ と ④ の対応を両方向で固定する** — フラグを持つ配布 Skill には `policy.allow_implicit_invocation: false` があり、持たない Skill が Codex でだけ止められていることもない。

#### Copilot CLI のシェル承認は配布物に書かない

Copilot CLI には、**起動した Skill が呼ぶシェルコマンドごとに承認を求める**という層がある。Skill の frontmatter に `allowed-tools: shell` と書けばその承認を事前に済ませられるが、**配布 Skill には全件書かない**（`tests/test_skill_descriptions.py` が配布 Skill の frontmatter に `allowed-tools` が無いことを固定する）。

- 絞れる粒度が粗い。Copilot CLI の起動フラグ `--allow-tool='shell(COMMAND)'` でもコマンド名まで（`git` / `gh` のみサブコマンドまで）で、最も細かくしても `shell(python)` は `python -c "..."` を通すので任意のコード実行とほぼ同じになる。WikiCommit は外部 URL の本文を読むので、公式ドキュメントが名指しする警告（プロンプトインジェクションによる任意のコマンド実行）がそのまま当たる
- 読み取り専用の Skill だけに書くこともしない。事前承認の範囲はシェル全体であって Skill の意図ではなく、読み取り専用の Skill も外部由来の文字列を扱う（`ask --include-source` はソース本文を載せ、`search` / `ask` / `quiz` はクエリをコマンドに埋め込む）
- 書かないので Claude Code・Codex への影響は無い（Claude Code でも `allowed-tools` は事前承認のキーであり、Copilot の使い勝手のために Claude Code 上の承認の挙動を変えない）
- 承認を減らしたい利用者には、README が `copilot --allow-tool='shell(python)'` を**利用者の判断で**付けられることと、その意味（実質的に任意のコード実行の許可）を案内する。**安全装置を外す判断は配布物ではなく利用者の手元に残す**（自律起動の抑止を運用者の `skillOverrides` に置くのと同じ置き場の考え方）
- 実機で確かめていないこと: `shell(python)` が `python3` やパス付きの呼び出しにも一致するか、フラグを付けた場合に承認がどの程度減るか

#### `skillOverrides` の値

`skillOverrides` の取りうる値は 4 つで、**軸が「Claude への見せ方を絞る」方向にしかない**（フラグを設定で打ち消すことはできない）:

| 値 | Listed to Claude | `/` メニュー | モデルが起動できるか |
|---|---|---|---|
| `on`（既定・未記載時） | 名前と description | あり | できる |
| `name-only` | 名前のみ | あり | **できる** |
| `user-invocable-only` | 隠す | あり | できない |
| `off` | 隠す | なし | できない |

**新規リポジトリには `name-only` を配る。** `user-invocable-only` を採らないのは、無人実行したい運用者が `on` に戻す必要があり、その瞬間に保護が全部外れる（全か無かのスイッチになる）ため。`name-only` は説明文＝自律トリガーの主機構だけを隠して名指しの起動経路を残すので、無人実行は切替なしで通る。

**このリポジトリ自身（`wikicommit-dev2`）は `user-invocable-only` にしてある。** ここには無人実行の必要が無く（クラウド自動化が使うのは `implement-issue` と `review-and-merge` である）、最も強い設定を選んでも失うものが無い一方、dev2 は最も多くのエージェントセッションが走り常に未コミットの変更がある場所だからである。

**したがって、説明文が唯一の防御になるのは②が届かない既存リポジトリである。**

#### description の強さは誤起動の代償で決める

**pushy さは読み取り専用の Skill でも一様ではない。** `ask` / `quiz` / `search` / `status` は読み取りしかせず、`.wikicommit/` が無ければ Skill 自身が止まるので強めに振ってよい — とくに `search` と `status` は「`grep` で代替できそうに見える」形をしており、公式が名指しする undertrigger（"Claude only consults skills for tasks it can't easily handle on its own"）にいちばん当たる。**`serve` だけは例外で、`npm run build` を実際に走らせる** ので、ページの内容を答えるためではなくプレビューが実際に要るときに呼べ、と書き分けてある。

**書き込み系の 3 本は向きが逆で、pushy に振ってはならない。** `generate` / `merge` / `translate` のリスクは undertrigger ではなく **overtrigger** であり（誤起動するとページが生成され、続けて `merge` が発火すればデフォルトブランチへマージされて公開される）、②が届かないリポジトリでは description が唯一の防御である。3 本とも「いつ使うか」に加えて**いつ使わないか**を明示し、代わりに呼ぶべき読み取り専用の Skill を名指しする。

**呼び出し元の Skill を「閉じた集合」として列挙しない。** `merge` の description は、どの Skill の後に使うかを Skill 名の列挙ではなく**性質**で述べる。選定基準は「未コミットのローカル変更を作るか」であり、文面はその基準そのものを述べ、変更の作り手を述べない — 現在の挿入句は "the uncommitted changes under `.wikicommit/`, including your own edits to its policy files" で、人が `.wikicommit/entity-policy.md` だけを手で編集した変更（そのファイルを書く Skill は存在しない）も射程に入る。具体性を上げたい場合は `wikicommit-status` が採っている **"and more" 型の開いた列挙**に倣う。

- 列挙は Skill が 1 本増えるたびに古くなり、古くなったことを知らせるものが何も無い
- 肯定節の閉じた列挙は**この Skill 自身の起動条件**なので、古くなると正当な起動を打ち消す（否定節に出てくる Skill 名は「代わりにこれを呼べ」という代替案であり、古くなっても指し先が消えるだけで働きが違う）
- フラグは選定基準にならない（フラグの有無と「未コミットの変更を作るか」は一致しない）
- CI では守れない。「書き込み系 Skill とは何か」は frontmatter からも本文の grep からも導けず、テストを置けば同期すべきリストが 2 本になるだけである。逆向きのテスト（他 Skill 名が N 個以上現れたら fail）も、閾値が恣意的で否定節の正当な Skill 名を区別できないので置かない

**`description` にコロンに続く空白（`:` ＋ スペース）を書いてはならない。** frontmatter はクォートされていない裸のスカラーなので、その並びがあると YAML はそこをマッピングとして読み、**frontmatter 全体がパースできなくなる**（`granularity` の箇条書きと同じ罠）。区切りが要るならダッシュ（`—`）を使う。`tests/test_skill_descriptions.py` が全 Skill について CI で止める。

#### 書き換えが効いたかを trigger eval で実測した

description が自律起動に効いているかは `skill-creator` の `scripts/run_eval.py`（trigger eval）で測り、クエリ集合と結果を `dev/skill-trigger-evals/` に置く。測る対象は自律起動しなかったときの損失が大きい `ask` / `search` / `status` である。

- **description は手書きのままとし、`improve_description.py` の生成文に差し替えない。** 生成文はこのリポジトリの frontmatter 規約（コロン＋空白を含まない）に違反し、overtrigger へ最適化する向きは undertrigger のリスクと非対称である（overtrigger の代償は余計な Skill が 1 回読まれることに留まるが、undertrigger の代償は `ask` の存在理由そのもの）。生成文の禁止節のうち外部仕様の 1 文（`Do not use for questions about external specifications, standards, APIs, libraries, or general software documentation`）だけは実在の overtrigger を消すが、手書き文へ移植するかは別の問いとして残っている（移植するなら移植後の文で測り直す）
- **測った数字は差し替えの根拠にならない。** positive のクエリがすべて「この Wiki では」と明示的に枠づけられており、禁止節が実際に噛む枠づけの無い自然な質問を試していない。**再検討の条件は、枠づけの無い positive をクエリ集合に足して測り直したとき**である。`quiz` / `serve` もそのときまで測らない
- `run_eval.py` は対象の 1 Skill だけを合成コマンドとして提示するため、`search` と `ask` のどちらを選ぶかという曖昧性解消は原理的に測れない。20 問 × 3 回で 3 文中 1 節の語句差を裁定することもできず、eval にできるのは回帰確認であって A/B の優劣判定ではない
- **クエリ集合は `dev/` に置き、配布物には入れない。** trigger eval のクエリ集合は標準が置き場所を定めていない（位置を固定しているのは `evals/evals.json` の方だけ）ため、Skill ディレクトリの外に置いても標準準拠を崩さない
- **測定文脈は「空のディレクトリ」ではない。** 利用者の実際の形は「`.wikicommit/` を持ち `CLAUDE.md` を持たないリポジトリ」であり、空ディレクトリで測ると数字が構造的に潰れる。再現手順とこの環境固有の制約（`claude -p` を 2 つ以上同時に走らせると即座に失敗するため `--num-workers 1` が必須）は `dev/skill-trigger-evals/README.md` にある

#### `evals/evals.json`（behavioral eval）は入れない

**理由は「測れない」ではない。「測るべきものは既に決定論的に測っており、残りは `expectations` の器に合わない」である。**

trigger eval と behavioral eval は別の機構である — 前者は `[{"query", "should_trigger"}]` を読み Skill 本体を**実行せず** description が読ませるかだけを見る一方、後者は `evals/evals.json` を読み Skill を実行して `expectations` の通過率を見る。`run_eval.py` は `evals.json` を 1 行も読まない。

このリポジトリは検証を決定論的スクリプトへ押し出す方針（§11.5 のスクリプト委譲パターン）を徹底しているため、behavioral eval だけが拾える残りが構造的に小さい。たとえば「エージェントが本当に pass ファイルを読んだか」は `record_run.py checkpoint --token` が**自分でそのファイルを開いて `pass_token` と突き合わせる**ので、LLM を回さずに答えが出る。同型のものが各所にある（`validate_frontmatter.py`・`check_*.py` 群・`review-rules.md` の `rules_version` echo 照合）。

したがって `evals.json` に残るのは決定論的に書けない部分だけであり、それは定義上**生成品質**である（`chain_of_thought` のレビュー品質・型名一覧を 2 段階にした後の Pass 2b の recall・Pass のサブエージェント化の A/B）。**これらは trigger eval でも behavioral eval でも解けない**（`expectations` が測るのは「出力が所定の性質を持つか」であり、要るのは「ゼロ件が正常な結果である非決定論的判定の recall が落ちたか」で、器が違う）。標準の手段は別の問題を解く道具であり、これらを測っていないのは標準を使っていないことによるものではない。

### 11.2 Skills 一覧

#### Skill 間の関係

下表の各 Skill がどう繋がるかの全体像。書き込み系の Skill はいずれもローカル書き出しまでで止まり、Git 操作は `wikicommit-merge` に集約される（`wikicommit-schema-propose`・`wikicommit-update`・`wikicommit-organize` は自分で PR を作る）。**このうち `generate` / `merge` / `translate` の 3 本は、人が `/name` と打つ以外にモデルからも起動できる**（無人実行の経路がこの 3 本で閉じるため。他の書き込み系 Skill は `disable-model-invocation: true` を持つ。§11.1 参照）。

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
  /wikicommit-relate      ページ同士の関係を人が決める → .wikicommit/relations.yml に記録
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
    （Pass 2b がその場での型追加を担うため、
      本 Skill の役割は事後検出の安全網である）
  /wikicommit-update         → インストール済み配布物と同期する PR を単独で作成
    （孤児の削除と review ファイルの差分適用はどちらも人間の判断であり、
      PR がその確認の場になる）
  /wikicommit-organize       → groups/<Type>.yml と Type の index.md を変える PR を単独で作成
    （分類が妥当かは PR 上で人が決める。ページは 1 枚も書き換えない）
```

| Skill | コマンド | 実装概要 |
|---|---|---|
| `wikicommit-init` | `/wikicommit-init` | `.wikicommit/` のディレクトリ構造・スキーマを生成。Skills のデフォルト設定を埋め込みから生成する（外部テンプレートリポジトリ依存なし）。theme 入力が非空の場合、theme 文だけから明らかに（obviously）必要と判断できる Schema.org 標準型に限定して型提案を行う（`wikicommit-collect`・`wikicommit-generate` Pass 2b との役割分担は `docs/DesignDoc-data.md` §3.3 参照） |
| `wikicommit-generate` | `/wikicommit-generate <path\|url>` / `/wikicommit-generate --regenerate <page\|--type <Type>\|--all>` | ソースを `.wikicommit/source/` に登録し、そのままページ生成まで実行。Git 操作は行わない。ハッシュを計算し管理ファイル（`.md`）を生成または更新。ディレクトリ指定時はファイルごとに個別生成。`--regenerate` は既存ページを現在の生成ルールで作り直す**ページ起点**のモード — 対象ページの `sources` を再取得し Pass 2 を飛ばして Pass 3・Pass 4 のみを実行、`review_status` を `pending` に戻す。`status: retracted` のソースだけは再取得せず落として作り直し、ページの `sources[]` からもそのエントリを外す（全件が `retracted` なページは作り直す材料が無いためスキップし `/wikicommit-remove` へ誘導する）。新規 Skill ではなくオプションである（Pass 1/3/4 を通常生成と共有し、差分は「Pass 2 を飛ばす」「`review_status` を戻す」「対象の指定方法」に限られる）。`--regenerate <page> --merge <page> [...]` は、人が「同一」と判断したページを 1 ページに統合する（残すページを全ページのソースで作り直し、吸収したページの名前を別名として持たせ、吸収したページを `removed_reason: merged` で下ろし、リンクを書き換える。`docs/DesignDoc-data.md` §4.5.2）。詳細は `docs/DesignDoc-pipeline.md` §6.1 |
| `wikicommit-merge` | `/wikicommit-merge` | `.wikicommit/` 配下の未コミット変更を対象に品質チェックを実行し、ブランチ作成・PR 作成・マージ・レビュー追跡 Issue 生成まで行う |
| `wikicommit-review` | `/wikicommit-review <page>` | frontmatter 補完・sources チェック・整合性チェック（`validate_frontmatter.py` を呼び出す）を行い、`sources` を再取得して独立した事実確認を実施し観点ごとの所見を人間に提示した上でレビュー完了を記録する（全文再掲はソースが取得できない場合や人間が希望した場合のみのフォールバック）。記録方法はページの経路で分岐: 対応するレビュー追跡Issue（`wikicommit-review`ラベル）があれば経路Aのページとみなし `gh issue close` する（`review-issue-close-sync.yml` が `review_status: reviewed` への書き換え・自動マージまで行う）。無ければ経路Bのページとみなし `review_status: reviewed` をローカルに書き込み、その後 `/wikicommit-merge` を呼ぶことで `reviewed` 状態のまま自動マージされる |
| `wikicommit-fix` | `/wikicommit-fix <issue-url>` / `/wikicommit-fix <page-path\|published-page-url> "<fix instruction>"` | フィードバック（Issueの本文+コメント、またはフリーテキスト指示）・対象ページ・sources 元文書をコンテキストとして LLM に渡し、修正案を提示。人間確認後 `/wikicommit-merge` で PR 作成（ページパス直接指定・公開Wiki URL指定にも対応）。対象ページが翻訳ページ（`translated_from` あり）で、指摘が翻訳固有ではなく内容由来（原文にも影響しうる）と判定した場合、修正対象を原文ページへリダイレクトするか確認する（リダイレクトしてもIssueへのリンクバックは同じIssue番号のまま）。マージ完了後に元 Issue へ返す完了コメント（Step 7）は、**Step 2 で特定した対象ページの `lang`**（＝報告者が実際に読んだページ）で描画する — リダイレクトが働いて原文ページを直した場合も、読んだページは変わらないためこちらに従う（追跡 Issue 本文が `primary_lang` を採るのとは読み手が違うため答えも違う。`docs/DesignDoc-pipeline.md` §6.2） |
| `wikicommit-remove` | `/wikicommit-remove <page>` | status: removed を付与する（ローカル変更）。翻訳ページも同時処理。その後 `/wikicommit-merge` で PR 作成 |
| `wikicommit-ask` | `/wikicommit-ask <question>` | `.wikicommit/entity/` を検索し、LLM が回答を生成。MCP なしで知識参照を可能にする |
| `wikicommit-search` | `/wikicommit-search <query> [--lang <lang>] [--no-expand]` | `.wikicommit/entity/` をキーワード検索し、結果を列挙する。クエリ語は同義語・上位語・略語へ拡張され（`--no-expand` で無効化）、さらに `config.yml` の対象言語ごとに翻訳して言語ごとに逐次検索し、結果をマージする（`translated_from` で結ばれた同一ページは1件に集約し、抑制された他言語版は `(also in: <lang>)` として表示する。`--lang` 明示時は言語をまたぐ fan-out をスキップ＝オプトアウト手段を兼ねる。ただし `<lang>` への翻訳は止めない）。対象言語は `config.yml` に加えて `.wikicommit/entity/` 直下に実在する言語ディレクトリも含める（全クエリが `--lang` を伴うため、含めないと未設定言語のページが端から届かなくなる）。`--limit` は言語数に関わらず言語ごと10件・マージ後10件まで |
| `wikicommit-status` | `/wikicommit-status` | 未処理ファイル数・未審査ページ数・孤立ページ数・wanted ページ数・Type セグメント取り違え数・スキーマファイル未整備の型数・expires_at 期限切れ数を表示。`check_orphans.py` / `check_wanted_pages.py` / `check_expires.py` / `check_ingest_freshness.py` / `check_translation_status.py` / `check_derivation_freshness.py` を呼び出して集計するほか、`check_actions_pr_permission.py` でGitHub Actions PR権限設定も、`check_property_wikilink_reinforcement.py` で型テンプレートのproperty-value WikiLink補強の非対称性も、`check_recurring_characters.py` で `properties.character` にプレーンテキストのまま埋もれた登場人物も、`check_unlinked_entity_mentions.py` で実在するページを指すのにリンクされていない `properties:` 値も、`check_installed_type_usage.py` でページが 0 件のインストール済み型・祖先型に落ちている可能性も、`check_self_referential_tags.py` でページ自身の title/type を繰り返すだけのタグも、`check_retracted_sources.py` で人間が取り下げたソースになお立っているページも、`check_schema_coverage.py` で専用スキーマファイルが無いまま使われている `type:` 値も、`check_name_collisions.py` で同じ名前に答える複数ページ（人が判断済みの組を除く）も確認する |
| `wikicommit-collect`（Phase 3〜） | `/wikicommit-collect` | `config.yml` の `theme` に基づき、ローカルフォルダおよび Web から未取り込みの関連ソース候補を探索し一覧提示する。引数なし（research guidance が渡されなかった）実行では、探索の前に Step 3.5（俯瞰ステップ）が走る（`wikicommit-synthesize` の Step 0 と同型のものを探索側に置いたもの）— `build_survey_view.py`・`check_wanted_pages.py`・`check_orphans.py` の 3 本を呼んで Wiki の現状を俯瞰し、着眼点を最大 5 件提案して人間が選ぶ。`build_survey_view.py` の `PAGE:` 行はソースの件数（`sources=N`）も持つので、被リンクが多いのに `sources=1` のページ — 「何が欠けているか」ではなく「**何が薄く支えられているか**」 — も着眼点の材料になる（`ORPHAN:` が出自付きで「端が薄い」を出すのと対になる。1 本の文書についてのページのように 1 件が正しい場合もあるので、判定ではなく材料として読む）。選ばれた着眼点はそのまま Step 2 が保持する research guidance になり（`theme` を置き換えない）、Step 4/5 がそれを使う。`theme` は Wiki 全体の内容スコープであり、1 回の探索の方向づけとしては粗すぎる — 俯瞰はそこに何を打てばよいかを知る手段である。**自動探索にはしない**: 判断するのは人間で、俯瞰は材料を出すだけである（idea support であって品質ゲートではない）。何も選ばれなければ何も探索せず停止し、非対話実行でも停止する（`/wikicommit-collect <guidance>` と明示すれば俯瞰を飛ばせる）。却下された着眼点はどこにも永続化しない — Step 8 が `source-policy.md` の `rejected:` に書くのは「人間が却下したソース URL」であって着眼点ではなく、混ぜない。`--index <url>` だけが渡された場合は guidance が空なので発動する（`--index` は探索の入口であって着眼点ではない）。`TYPE_MISMATCH:` は着眼点の候補にしない（実体は在りリンク 1 語の誤りで、要求される行動が `WANTED:` と正反対）。`/wikicommit-status` を丸ごと呼ぶこともしない（`check_ingest_freshness.py` が管理ファイルを書き換える副作用を持ち、探索の前に副作用を起こす理由が無い）。Claude Code のネイティブ Web 検索・既存 Skills を活用し専用クローラは自作しない。Web 探索は theme の抽象度そのままの広いクエリ 1 本ではなく、6 つのパス（theme の具体語・`filetype:pdf`・既登録ソースのホストへの `site:`・`theme`／`source-policy.md` が名指しする発信元への `site:`・`check_wanted_pages.py` の `WANTED:` を検索語にするパス・リポジトリホスト）からなるクエリ群として投げる（1 パスあたり最大 5 本・1 実行あたり最大 20 本。広いクエリ 1 本が返すのは分布のヘッドであり、theme が名指しする個人ブログ・小さな OSS リポジトリ等のテールには構造的に到達しないため。探索履歴は永続化せず、各パスは実行のたびに Wiki の現在の状態から導出される）。候補提示直後、候補群のタイトル・要約を俯瞰して `installed schema/` 外の Schema.org 標準型が明確に良い適合先と判断した場合、`wikicommit-generate` Pass 2b の対話実行時と同じ Enter ベース承認 UX で型を提案し、承認されれば `.wikicommit/schema/<Type>.md` をその場で新規作成する（候補提示自体が対話的なため、Pass 2b が非対話実行で候補を保留にする扱いはここには当たらない）。`.wikicommit/source-policy.md` の `index_only:`（またはコマンド引数 `--index <url>`）に該当するページは候補にせず、**その参照節から一次資料 URL を掘って候補に流し込む**（索引ページ自身は決して登録しない — 本文を読んで「何を書くか」を決めると、そのページが `sources:` に無いため Pass 4 の照合も帰属表示も効かない無帰属の二次的著作物になる）。候補は人間が確認・選択した分のみ `.wikicommit/source/` に登録（`wikicommit-generate` を内部呼び出し）。著作権・ライセンスリスクを踏まえ、登録前の人間承認を必須とする |
| `wikicommit-quiz`（Phase 3〜） | `/wikicommit-quiz [--topic <keyword>] [--lang <lang>] [--difficulty=easy\|medium\|hard]` | `.wikicommit/entity/` 全体から `wikicommit-search` 相当の検索で関連ページを収集し、LLM がクイズを生成して会話内に出力する。ファイル書き出しは行わない。`--topic` 指定時は `wikicommit-search` と同じクエリ語拡張・クロスリンガル検索（`--lang` でオプトアウト）を行う — 同一ページの複数言語版が両方ヒットすると同じ事実についての設問が2問できてしまうため、重複排除はここでは必須。出題・解説の言語は `--topic` の言語（省略時は `primary_lang`）に固定し、grounding ページの言語に引きずられない。`--topic` 省略時の分岐（`primary_lang` 配下からランダムサンプリング）はクエリ自体が存在しないため対象外 |
| `wikicommit-synthesize`（Phase 3〜） | `/wikicommit-synthesize [<topic>] [--max-grounding N]` | 指定した概念・用語について関連ページを収集し、LLM が新規ページを合成する。**根拠ページは `primary_lang` の原文だけを検索し（翻訳は根拠にしない）、`build_survey_view.py --pages` で縮約した title・description・見出しから「テーマを主題として扱っているか」を本文を読む前に選別し、既定 30 件（`--max-grounding` で変更可）で切る**。選別後に「M 件中 N 件を根拠にする」を表示し、上限で切ったページは完了報告に列挙する（`docs/DesignDoc-data.md` §4.5.1）。`generate` が外部ソースから作るのに対し、こちらは既存 `entity/` ページ群から作る。出力先は **`.wikicommit/view/<lang>/<slug>.md`** で、品質ゲート対象・`/wikicommit-merge` でPR化可能である。**`type:` を持たず**、代わりに任意の `kind`（`practice` / `landscape` / `comparison` / `pattern` / `timeline` / `debate` の 6 値。「複数ページを見て何をするか」を表し、Schema.org 型の「何についてか」とは直交する）を持つ — 型選択ステップは無く、同じ topic の 2 回の実行が別々のパスに解決されることも構造的に起きない。公開先は `content/<lang>/View/<slug>.md`、WikiLink は `[[View/<slug>]]`（`View` は予約 Type セグメント。言語を先頭に保つことで breadcrumbs / language-switcher / explorer の 3 プラグインが無改修で済む）。詳細は `docs/DesignDoc-data.md` §4.5.1。出自は `derived_from`（`{path, source_commit}` の配列）フロントマターに記録し、`sources` は書かない。本文生成後・書き出し前に、`wikicommit-generate` Pass 4 と同型のレビューサブエージェント（Step 5.5）がgrounding ページ群と照合する（返却形式は §4.6 のエージェント間 JSON をそのまま使い、`source_file` には grounding ページのパスが入る。再試行は `generate.max_retries` を流用し、上限超過時は書き出さずに停止・報告する。grounding ページ同士の食い違いは `page_at_fault: "other"` と同じ扱いで FAIL にせず完了報告に列挙する）。grounding set には `derived_from` を持つページを入れない（合成ページを通常ページの 1 段上に留める。索引からは除外しないため `/wikicommit-search` からは引き続き見つかる）。grounding のうち `review_status: pending` のページは本文生成の前に列挙して伝える（警告でありゲートではない）。書き出し後、そのページの言語の view index（`.wikicommit/view/<lang>/index.md`）を `rebuild_index.py` で再構築する（言語別）。引数なしで実行した場合は Step 0（俯瞰モード）が先行し、`build_survey_view.py` が返す Wiki 全体の縮約ビュー（各ページの title/type/tags/`properties.description`/`##` 見出し/発リンク + リンクグラフ由来のハブ・タグ集計）から、複数ページを横断して初めて見える着眼点を最大5件提案する（他 Skill 群と同じ 5 件閾値）。人間が選んだ着眼点がそのまま `<topic>` として Step 1 以降に合流し、選ばれなかった候補はどこにも永続化しない。候補提示は非決定論的（実行ごとに結果が変わる）であり、品質ゲートではなく着想支援である |
| `wikicommit-serve`（Phase 3〜） | `/wikicommit-serve [--build]` | `npm run preview` / `npm run build`（Quartz v5 のローカルビルド・プレビューサーバー）の薄いラッパー。Git 操作を行わない読み取り専用 Skill（`wikicommit-review` との名称衝突を避けて `wikicommit-preview` ではなくこの名前）。`quartz.config.yaml`（`/wikicommit-init --quartz`）の存在が前提。既存の `package.json` に WikiCommit のビルドスクリプトがマージされていない場合はその旨を案内して停止する |
| `wikicommit-translate`（Phase 3〜） | `/wikicommit-translate <page> [--lang <target>]` / `/wikicommit-translate` | 原文ページ全文 + `DefinedTerm/` 用語定義 + 原語↔訳語の対応表（対象言語の `DefinedTerm` ページの `title` のみ）を LLM コンテキストに注入して翻訳を生成し、`translated_from` / `source_commit` / `translated_at` を付与してローカル書き出しする（Git 操作は行わない）。引数なしの一括モードは作業リストを `DefinedTerm` 型のペアが先頭に来るよう並べ替えた上で（用語集を先に確定させてから本文を訳すため）、`check_translation_status.py` の `UNTRANSLATED` + `STALE` 件数が5件を超える場合、確認の上でその順序の先頭5件のみ処理できる（`wikicommit-generate` / `wikicommit-collect` と同じ閾値）。`--lang` 省略時は `config.yml` の `translation.targets` 全言語を対象にする（空配列の場合はエラー終了） |
| `wikicommit-update`（Phase 3.1〜） | `/wikicommit-update` | インストール済みの配布物とリポジトリを同期し、結果を PR にする。`wikicommit-schema-propose` と同じく**自前で PR を作り auto-merge しない** — 孤児の削除と `review` ファイルの差分適用はどちらも人間の判断であり、PR がその確認の場になる。処理は 9 段（版の突き合わせ → `check_distribution_freshness.py` によるドリフト検出 → `init.py --no-overwrite` による `overwrite` の適用 → 孤児削除の確認 → `review` の差分提示 → `wikicommit_version` の刻印 → 検証 → PR → 報告）。**`.claude/skills/` 自体の更新は Skill の外に置く** — 自分の SKILL.md を書き換えても実行中のエージェントは古い指示を持ったままになるため、`npx skills add` は人間が先に実行する前提とし、SKILL.md 冒頭でそれを案内する。`wikicommit-init --update` というフラグにはしない — 「無から作る」と「既にあるものを突き合わせて人間に見せる」は指示の性質が違い、フラグにすると init を叩くたびに使わない指示を運ぶことになる（SKILL.md は起動のたび全文が載る。§11.9）。**3-way merge は行わない**（配布リポジトリが単一コミットの積み重ねで base が復元できない。`docs/DesignDoc-data.md` §3.3）ため、`review` の扱いは 2-way diff + 人間の判断が上限になる。`quartz.config.yaml` の提示ではリポジトリ固有キー（`pageTitle` / `pageTitleSuffix` / `locale` / `baseUrl` / `links` / `theme` / `translation.*`。うち `pageTitle` / `pageTitleSuffix` / `locale` / `links` は init が `{...}` プレースホルダを置換して書くため、テンプレート側にはプレースホルダが残っている — 取り込ませると `{LOCALE}` がそのまま config に入り、YAML がロケール文字列ではなくマッピングとして読む）を差分の文脈に並べない — 検出条件を二重に持つのではなく、新しく現れたキーを見せるときに周辺のユーザー自身の設定でそれを埋もれさせないための緩和策である |
| `wikicommit-reconcile`（Phase 3.1〜） | `/wikicommit-reconcile --source <path\|url>\|--type <Type>\|--all` | ポリシー（`theme` / `entity-policy.md` / `source-policy.md`）・型テンプレート・生成ルールの変更を既存ページへ届けるため、対象ソースの管理ファイルを `status: pending` に戻す。**生成は行わない** — 次の `/wikicommit-generate` が既存の収集条件でそれを拾う。ページ 1 枚を決める入力 6 種のうち 3 種（ポリシー・型テンプレート・生成ルール）だけがキューを持たず、それらを読むのはいずれも Pass 2c であり、Pass 2c を通る入口は**ソースの内容が変わったときにしか開かない**（`--regenerate` は Pass 2c を実行しない）。とくにスイッチを **off に戻す**経路は既存のどのコマンドでも到達できない — `status: excluded` のソースは `/wikicommit-generate <url>` が `HASH_MATCH` で「変更なし」と報告し、`<path>` は `SKIP` で Pass 1 にも届かず、引数なしは収集対象外であり、**3 経路とも出力は成功系**である。検出は行わず**人間が対象を宣言する**（変えたのは本人であり、機械が言える新情報はスイッチが on であることの 1 ビットだけ。1 回きりの設定変更イベントに常設のヘルスチェックを置かない）。書き戻しは `set_frontmatter_field.py --require` で現在値を確認してから、人間の承認を経て行う。`check_ingest_freshness.py`（検出 → `status: outdated` → generate が拾う）と同じ形の一般化であり、`wikicommit-generate` には変更を要しない |
| `wikicommit-relate`（Phase 3.2〜） | `/wikicommit-relate [<Type/slug> ...]` | ページ同士の関係（同一 / 上位と下位 / 関連 / 別物 / 系列 / 保留）を人に決めてもらい、`.wikicommit/relations.yml` に記録する。名指しの入口と、`check_name_collisions.py` が挙げる名前の衝突を順に扱う引数なしの入口を持つ。記録した組は衝突として再び挙がらない。**ページを編集するのは系列の版の改名だけ**（`rename_page.py`。人が名前に同意した後、slug と title を年で修飾する）— 「同一」の統合は `/wikicommit-generate --regenerate --merge` が行う。非対話実行では何も書かない。Git 操作は行わない。設計は `docs/DesignDoc-data.md` §4.5.2 |
| `wikicommit-organize`（Phase 3.2〜） | `/wikicommit-organize <Type>` | 1 つの型のページをグループに分ける。`check_groups.py --type` で未分類ページ（1 回 30 件まで）を取り、`build_survey_view.py --pages` の縮約ビュー（本文は読まない）からグループと振り分けを提案し、人が承認したものだけを `.wikicommit/groups/<Type>.yml` に書く。続けて `rebuild_index.py` で各言語の `index.md` を見出しで分け、**自前でブランチと PR を作り auto-merge しない**（`wikicommit-schema-propose` / `wikicommit-update` と同じ）。**ページは 1 枚も書き換えない** — 分類をページの frontmatter に書くと分類のたびに全ページが内容変更扱いになり `reviewed` が `pending` に戻る。`.wikicommit/entity/` に未コミットの変更があれば始めない（index が PR に含まれないページを指すのを防ぐ）。`disable-model-invocation: true` と `agents/openai.yaml` を持つ。詳細は `docs/DesignDoc-data.md` §4.5.3 |
| `wikicommit-schema-propose`（Phase 3〜） | `/wikicommit-schema-propose` | `check_schema_coverage.py` で `.wikicommit/schema/` に専用ファイルのない `type:` 値を検出し、Schema.org 標準型として実在すれば標準型ファイル、実在しなければ `custom/` 型ファイルを新規追加する PR を作成する。ブランチ名 `wikicommit/schema-propose-<Type>` で重複提案を防止。`.wikicommit/schema/` への書き込みが唯一の役目で、既存ファイルの編集・削除は不可。他の PR 作成系 Skill と異なり **auto-merge しない**（人間レビュー必須）。その場での型追加は `wikicommit-generate` Pass 2b が主経路として担うので、本 Skill の役割は事後の安全網（Pass 2b を通らずに生成されたページの救済等）である |

### 11.3 Skill ディレクトリの構造

各 Skill は `SKILL.md` と、Skill のみが使う `scripts/` サブディレクトリ、そして SKILL.md 本体から出した指示ファイルを置く `references/` で構成する。この 3 つは Anthropic の Skill anatomy（`scripts/` / `references/` / `assets/`）に揃えたもので、`references/` に置くのは**進行的開示の第 3 層**（必要になったときだけ読む bundled resource）である。

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

#### `references/` に置く条件

- **置く条件は「SKILL.md 本体に無くても実行が壊れない」ことではなく、「入口によっては一度も読まれない」ことである。** `references/completion-notice.md` はソースを処理する実行なら必ず読むが、Step 0 で止まる実行と `--regenerate` では 1 バイトも読まれない。目的は総量の削減ではなく、**起動のたびに丸ごと載る量**を下げることにある（§11.6 の「固定分の内訳と、下げられるもの / 下げられないもの」と同じ区別）
- **配布は何も変わらない。** `install.sh` は `find "${skill_src}" -type f` の再帰コピーであり、`.claude-plugin/plugin.json` は Skill **ディレクトリ**を列挙するため、サブディレクトリは自動的に配布に乗る。`tests/test_skill_distribution_list_sync.py` が同期を強制するのは Skill の**一覧**であって Skill 内のファイル構成ではない
- **`tools/check_skill_md_lines.py` の 2 本立ての指標**は `instruction_files()` が `rglob("*.md")` なので `references/` 配下も指示の総面積に数え、本体だけが下がる。これは意図した挙動である（「本体 ↓ / 総面積 →」が「分割した」を意味する）
- **走査を自前で持つ検査は `references/` まで広げる。** `tests/test_review_rules_single_source.py` は同じ `check_skill_md_lines.instruction_files()` を import している — Skill ディレクトリの直下だけを歩くと、`.wikicommit/review-rules.md` に集約したレビュー規律が `references/*.md` に書き戻されても CI が緑のままになる。**新しく `references/` を使う Skill を足すときは、走査を自前で持つ箇所が他にないかを先に確認する**（分割が指標や検査の射程を黙って縮めるため）
- **`wikicommit-generate` の pass ファイル 5 本は `record_run.py` の `EXPECTED_PASSES` と 1 対 1 である。** 名前空間を新設せず checkpoint のパス名をそのまま使うため、**`--token` の照合先がファイル名で引ける**（`PASS_FILE_DIR` は `references`）。各ファイルの frontmatter が `pass_token` を持ち、`record_run.py` が**自分でディスクからそのファイルを開いて**突き合わせる — 照合先のパスを引数で受け取らないことが第三者性の根拠であり、呼び出し側がファイルを指定できるなら自分で書いたファイルを指せてしまう
- **保証するのは「そのファイルを開いた」ことに徹する。** トークンは内容のハッシュではなく手で置く不透明な値で、ファイルを編集しても上げる必要はない — ハッシュにすると編集のたびに書き換えが要り、忘れると偽の不一致で `checkpoint` が exit 1 になって実行が止まる（誤りの向きが安全側でない）。**ファイルを開いたが従わなかった場合は検出できない**（トークン行だけ grep することは防げない）。これは `review-rules.md` の `rules_version` echo がサブエージェント境界でしか成立しないのと対をなす限界であり、こちらは同一エージェントでもスクリプトが第三者として開くぶんだけ強い
- **compaction に対してはこの形のほうが強い。** 再添付されるのは各 Skill の先頭 5,000 トークンだけ（Claude Code の挙動）なので、本体が小さければ**窓が本体のほぼ全体を覆う**。checkpoint の打点指示も各 pass のファイルにあるので、本体の冒頭から長い実行の末尾まで生き延びる必要がない
- **20,000 B を超える reference ファイルには TOC を置く。** 公式ガイダンスは 300 行を閾値に挙げるが、このリポジトリの指示散文は 1 行 40〜170 B とばらつくため行数は読む量をほとんど言わない

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

#### Skill ツリーの位置を仮定してよい箇所・してはならない箇所

**Skill は `.claude/skills/` にあるとは限らない。** Claude Code はそこを読むが、Codex は `.agents/skills/` を読み、`npx skills add --agent codex` 単独では `.claude/skills/` は作られない（Copilot は公式ドキュメント上 `.github/skills/`・`.claude/skills/`・`.agents/skills/` のいずれも読むので、`.claude/skills/` に実体を置く限り当たらない見込みが高い — 実機では未確認）。上の図が `.claude/skills/` で描かれているのは開発リポジトリの配置であって、配布先の前提ではない。

| 誰が | Skill の場所を | 書き方 |
|---|---|---|
| 指示文（`SKILL.md`・`references/*.md`）が**同じ Skill 内**を指す | 仮定しない | Skill ディレクトリ相対（`references/pass1-extract.md`・`python scripts/add_source.py`） |
| 指示文が**別の Skill** を指す | 兄弟であることだけを仮定する | 兄弟 Skill 相対（`../wikicommit-init/scripts/init.py`） |
| `.wikicommit/scripts/` のスクリプトが Skill ツリーを**読みに行く** | 仮定しない | `_skill_tree.py` の探索順（`.claude/skills` → `.agents/skills`） |
| Skill 内スクリプトが自分のファイルを指す | 仮定しない | 自分の `__file__` から辿る |
| 人が手で打つ手順書（`guides/`）・人向けの案内文 | 仮定してよいが**併記する** | `.claude/skills/…` と書き、Codex の場合は `.agents/skills/` である旨を添える。スクリプトが印字する案内は自分の `__file__` から実際のパスを出す |

**指示文の相対パスが成り立つのは、両ランタイムが Skill の場所をエージェントに渡すからである。** Claude Code は Skill を起動すると本文の冒頭に `Base directory for this skill: <絶対パス>` を注入し、Codex は Skill 一覧に各 Skill のファイルパスを含める。agentskills.io 標準も「Skill 内の他ファイルは Skill ルートからの相対パスで参照せよ」と定め、Anthropic 公式 Skill（xlsx 等）は `python scripts/recalc.py` のようなスクリプト呼び出しまで Skill 相対で書き、"Script paths below are relative to this skill's directory." と 1 行断っている。WikiCommit も相対パスを持つ各ファイルの冒頭に同じ趣旨の断りを 1 つ置く。**コマンドは引き続きリポジトリルートで実行する** — 断りは「パスをリポジトリルートから綴り直せ」と述べており、スクリプトが `.wikicommit/` を読む処理は cwd に依存したまま壊れない。

**兄弟 Skill 相対（`../`）は agentskills.io の "Keep file references one level deep from `SKILL.md`" を意図して外れる。** 推奨であって禁止ではない。外れる理由は、WikiCommit の Skill 群が 1 つの配布物として同時にインストールされ、スクリプト（`add_source.py`・`init.py`）とテンプレート（`schema-authoring.md`・`check_distribution_freshness.py`）を共有するためである — `.claude/skills/` でも `.agents/skills/` でも全 Skill が同じ親ディレクトリに並ぶので、`../<skill>/` はどちらでも解決する。Codex が `../` を実際に解決するかは実機で未確認である。成り立たなかった場合でも、影響は Skill をまたぐ参照に限られ、同じ Skill 内の参照（`references/` へのポインタを含む）には及ばない。

**再混入は `tools/check_skill_tree_paths.py` が止める**（blocking。`docs/DesignDoc-TestSpec.md` L14）。

実行時に自分のディレクトリを解決する手順を指示文に書かせることはしない（標準が既に定めている書き方を独自の手順で再現することになる）。`--agent claude-code` の併用の必須化や symlink 配置の推奨で `.claude/skills/` の存在を保証することもしない（どちらも Codex 単独配置のサポートと矛盾し、後者は Windows で `core.symlinks` を持たない clone の Claude Code 側を壊しうる）。

### 11.4 将来のマルチエージェント対応

MVP では Claude Code のみを対応対象とする。`.wikicommit/schema/` は将来の全エージェントで共通利用できるように維持し、他エージェントへの対応時はそのエージェントが要求する配置場所に薄い連携ファイルを追加する。

| エージェント | エントリポイント |
|---|---|
| Claude Code | Skill 定義（`.wikicommit/schema/` を参照） |
| GitHub Copilot — VS Code エージェントモード | Skill 定義（`.claude/skills/`・`.agents/skills/`・`.github/skills/` のいずれも読む）。**対象・実機検証待ち** |
| GitHub Copilot CLI | 同上。**未検証**。配布 Skill は `allowed-tools` を書かない（§11.1「Copilot CLI のシェル承認は配布物に書かない」） |
| GitHub Copilot クラウドエージェント | 同上だが**非対応**（構造的に WikiCommit の Git フローと衝突する） |
| その他 | エージェント固有の設定ファイル → `.wikicommit/schema/` を参照 |

#### GitHub Copilot の 3 つの実行面

Copilot は **Codex とほぼ正反対の性質**を持つ（公式ドキュメント〈2026-09-24 確認〉による。実機ではない）— `.claude/skills/` も読み（固定パスで壊れない）、明示起動は `/<skill>`（`$` の読み替えが要らない）、VS Code は `disable-model-invocation` を尊重する（自律起動の抑止が既存の仕組みで効く）。**したがって Codex の結果は流用できず、面ごとに扱いを決めている**:

| 面 | 扱い | 理由 |
|---|---|---|
| VS Code エージェントモード | **対象にし、実機で検証する** | Codex で起きた 3 つの問題がいずれも発生しない見込みで、検証が最も安い |
| Copilot CLI | **README に「未検証」と書く** | 配布物には `allowed-tools: shell` を書かない（§11.1「Copilot CLI のシェル承認は配布物に書かない」）ので、試してもシェルコマンドごとの承認の往復が多いという既知の結果しか得られない |
| クラウドエージェント | **非対応とし、README に理由を書く** | 実機を見なくても構造的に衝突する — 自分で開く 1 本の PR の中で作業するため `/wikicommit-merge` が PR の中で別の PR を作ってマージすることになり、既定のファイアウォールで URL ソースも取得できない、セッションは 59 分が上限 |

**Copilot にしか無い問題 — 二重発見**: `.claude/skills/` と `.agents/skills/` の両方に Skill が置かれるインストール（`--agent claude-code --agent codex --copy`、および `--copy` なしで 2 つ以上のエージェントに入れた場合 — 実体が `.agents/skills/` に置かれ `.claude/skills/` はそこへのシンボリックリンクになる。§11.1）では、両方を読む Copilot に同名の Skill が 2 つずつ見える可能性がある。同名の扱いは文書に無い。VS Code で (1) `--agent claude-code --copy` のみ、(2) 両エージェント向け、の 2 通りを試して確かめる。README は当面「Copilot 単独なら `--agent claude-code` のみ」と案内する。**実機での確認は未了**であり、結果が出たらこの節と README を更新する。

#### 指示文の語彙 — ツール名と起動記法

配布 Skill の指示文は Claude Code の**ツールの固有名**（`Read tool`・`WebFetch`・`Write tool`・`Bash tool` 等）を使わず、**スラッシュコマンド記法**（`/wikicommit-*`）はそのまま使う。Codex にはこれらの名前のツールが無く、Skill の明示起動は `$wikicommit-generate` である（`/skills` は一覧を開くだけ）。**2 つは宛先が違うので別々に決めている**（§11.8 の「読み手が誰か」）。

| 語彙 | 読み手 | 決定 |
|---|---|---|
| ツール名 | エージェントのみ | **役割で書く**。`tools/check_skill_tool_names.py`（blocking。`docs/DesignDoc-TestSpec.md` L15）が再混入を止める |
| ソースの再取得（`wikicommit-fix` Step 3・`wikicommit-review` Step 4） | エージェント | **`add_source.py --fetch-url` を使う**。ツールの選択で取得内容が変わる箇所であり（エージェントによっては要約を返す）、`wikicommit-generate` と同じ取得経路に揃える。出力は `.wikicommit/.cache/refetch/` に置き、`ingest-fetch/` の抽出キャッシュを上書きしない |
| `/wikicommit-*`（指示文内の相互参照） | エージェント | **据え置く**。Skill 名として読めれば足り、全箇所を 2 表記にすると指示面積だけが増える |
| `/wikicommit-*`（利用者に届く出力） | 人 | **1 度だけ `$` の表記を併記する**。対象は `print_next_steps.py` の「次のステップ」案内と、`wikicommit-merge` Step 8 / Step 9 が GitHub に書き出す Issue 本文 — 後者は Claude Code のセッションを持たない読者が読む |

冒頭に読み替え表を置くことはしない（SKILL.md は起動のたび全文が載るため全 Skill 分の指示面積が増え、`references/` に置けば読まれる保証が無く、読み替えが起きたかは出力に現れない）。ツール名を役割で書く代償は Claude Code 側でどのツールを使うかの指示が緩むことだが、`Read tool` が担っていた含意は「全文を読め」（途中で切らない）であり、それは「in full」として書く。Codex での実機確認は未了である。

### 11.5 スクリプト委譲パターン

Skill のプロンプト（SKILL.md）は LLM への指示であり、決定論的な操作・全ファイル走査・グラフ解析のような**再現性・網羅性が必要な操作**を LLM だけで行うと漏れや誤差が生じる。このような操作はスクリプトに委譲し、エージェントがシェルから呼び出す。

スクリプトの置き場所は **ブートストラップと所有権** で決まる：

| 置き場所 | 何が置かれるか |
|---|---|
| `.claude/skills/<name>/scripts/` | `.wikicommit/scripts/` に依存**できない**もの（`wikicommit-init` の 4 本 — そのディレクトリを作る側である）と、その Skill だけのものとして意図的に自己完結させたもの |
| `.wikicommit/scripts/` | それ以外。リポジトリで Git 管理されるため全 Skill から参照でき、共有モジュール（`_wikilink.py` / `_frontmatter.py` / `_schemaorg_vocab.py`）を import できる |

#### 置き場所の判断基準

上の表は「呼び出し元が 1 Skill なら Skill 内・複数なら共有」ではない。共有側には呼び出し元が 1 Skill だけのスクリプトが多数ある（`wikicommit-status` だけが呼ぶもの等）。

**Skill 内が硬い制約なのは `wikicommit-init` の 4 本だけである。** あれらは `.wikicommit/scripts/` を**作る**側なので、そこに依存できない。残る Skill 内スクリプトの理由は同じ強さを持たない:

| Skill 内スクリプト | 理由 | 状態 |
|---|---|---|
| `add_source.py` | frontmatter を自前パースし `.wikicommit/scripts/` からの import を一切持たない自己完結スクリプト | 慣行 |
| `remove_page.py` | `normalize_entity_prefix()` 等を複製している。「サブプロセスの cwd から `.wikicommit/scripts/` が解決できるとは限らない」という理由は成立しない（全 SKILL.md の呼び出しはリポジトリルート相対であり、cwd への同じ仮定を同じコマンドラインで既に置いている）が、複製そのものは残してある | 崩れている |
| `resolve_source_cache_path.py` | `sys.path.insert(0, ".wikicommit/scripts")` で `_frontmatter` を import している | 反例 |

- **判断基準は「写しが何本増えるか」である。** Skill 内に置いて import を避けると共有モジュール（`_wikilink.py` 等）の写しを作ることになるもの（例: `build_onehop_context.py` は `WIKILINK_RE`・エンティティ / view 走査・`parse_wiki_path`・frontmatter 読み・クロス言語解決一式を要する）は共有側に置く。Skill 内に置いて import する形は、共有側に置くのと結果が同じで木をまたぐ import が 1 本増えるだけである
- **版ずれは判定材料にならない。** どちらの置き場でも効き、どちらも「静かに変わる」形を含む — import で版ずれが `ImportError` になるのは symbol が消えたか改名されたときだけであり、古い `_wikilink.py` が `WIKILINK_RE` を名前はそのままに別の文字クラスで持っていれば結果だけが黙って変わる。共有側には `wikicommit-generate` Step 0 の `check_distribution_freshness.py --only .wikicommit/scripts` という検出があるが、非ブロッキングの警告であり置き場所を決めるほどの差にはならない
- **Skill ツリーを読みに行く共有スクリプトは、その位置を `_skill_tree.py` から引く。** `.wikicommit/scripts/` のうち `record_run.py`（`--token` の照合先 `<skill>/references/<pass>.md`）と `check_distribution_freshness.py`（`wikicommit-init/scripts/` のテンプレート）が実行時に Skill ツリーを読む。`.claude/skills/` を固定で持つと、Codex 単独配置（`.agents/skills/` のみ）で前者は正しく手順を読んだ実行を `token: missing` と記録し、後者は「wikicommit-init が未インストール」として版ずれ検査を黙って空振りさせる。探索順（`.claude/skills` → `.agents/skills`）は `_skill_tree.py` に 1 か所だけ置く。Skill 内スクリプトには写しは要らない（自分の `__file__` から兄弟を辿れる）
- **両方に実体がある場合（`--copy` で 2 エージェントに入れた場合）**: 同じインストールから来た写しなので通常は同一バイトであり、順序は答えを変えない。食い違っている場合、`check_distribution_freshness.py` は `.claude/skills` 側と比較する（Claude Code が実行する写し）。`record_run.py` は **どちらかの写しが `--token` を裏づければ `ok`** とする — エージェントは自分のランタイムが読む写しを読んだのであり、このスクリプトにはどちらのランタイムかが分からないので、もう一方の写しが違うことを理由に「読まずに実行した」と記録してはならない。`mismatch` は「ディスク上のどの写しも裏づけない」を意味する。**照合先を引数で受け取る形にはしない** — スクリプトが自分でファイルを開くことが第三者性の根拠である

#### Skill 内スクリプト（`.claude/skills/<name>/scripts/`）

決定論的なファイル操作・パス計算・YAML 編集など、LLM に任せると再現性が下がる操作を担う。

| Skill | スクリプト | 役割 |
|---|---|---|
| `wikicommit-init` | `scripts/init.py` | ディレクトリ構造作成・`templates/` からのファイル展開 |
| `wikicommit-init` | `scripts/print_next_steps.py` | 「次のステップ」案内文の組み立て（3 変種のほぼ同一な散文を SKILL.md に重複させないため） |
| `wikicommit-init` | `scripts/_root_outputs.py` | ルート生成物の宣言的な一覧。上記 2 スクリプトが共有する単一の情報源で、`init.py` の verbatim コピーと `print_next_steps.py` の `git add` 案内の両方をここから組み立てる（下記「ルート生成物の一覧は 1 つに保つ」） |
| `wikicommit-generate` | `scripts/add_source.py` | 管理ファイルのパス計算・SHA-256・生成・status 更新・ソースの同一性判定（URL・ファイルパスとも、ファイル名を再計算せず管理ファイルを走査して `source.url` / `source.path` で照合する）・`source.license` の初期値決定（既知ドメイン対応表と `--license`。`docs/DesignDoc-data.md` §4.3）・登録時の partial extraction 通知（`partial_extraction_note()` — 静的取得で本文は取れるが一部が黙って落ちる URL 形〈GitHub の Issue / PR スレッド〉を、ブロックせず登録時に一度だけ知らせる。ShareAlike 通知と同じ形）。`--fetch-url` は独自 User-Agent 付きの `requests.Session` を `markitdown` の Python API に渡して URL を取得する。`--license-for-url` は同じ対応表を引くだけの読み取り専用モード（下記「Skill 内スクリプトへの越境呼び出し」）。`--check-path-cache` / `--path-cache-path` は `type: path` の抽出テキストキャッシュの有効性確認と置き場の印字（前者は read-only で `source.hash` に一切触れない — `type: path` のそれは生ファイルのハッシュであり、キャッシュのハッシュで上書きすると `check_ingest_freshness.py` の鮮度判定が壊れる。`docs/DesignDoc-pipeline.md` §6.1） |
| `wikicommit-generate` | `scripts/workflow_checks.py` | ドライバー（`driver.py`）が工程の条件・一覧・完了の確認に呼ぶ、この Skill 固有の判定。エンジンを他の Skill でも使えるよう、パス・`status` の値・パスの名前はここと `workflow.yaml` に置く。終了コード 0 ＝ はい、1 ＝ いいえ（理由は stdout）、`ITEM:` 行が一覧、`TOUCHED:` 行が工程が書いたと確認したファイル |
| `wikicommit-remove` | `scripts/remove_page.py` | frontmatter への `status: removed` / `removed_at` 付与 |
| `wikicommit-ask` | `scripts/resolve_source_cache_path.py` | ページの `sources[]` の 1 件から、そのソースの抽出テキストキャッシュを解決する。呼び出し元は `wikicommit-ask --include-source` と、ソースを読む前の `wikicommit-review` Step 4 / `wikicommit-fix` Step 3（越境呼び出し — 同一性キーの規則の写しを増やさないため。キャッシュが無ければ `add_source.py --fetch-url` で `.wikicommit/.cache/refetch/` に取得する）。**`--type url` / `--type path` の 2 モードを持つ** — `--type url` は `sources[].url` から `.wikicommit/source/url/` 配下を実走査して一致する管理ファイルを特定し、その実パスから scratch-path を導出して `.wikicommit/.cache/ingest-fetch/` 内のキャッシュを解決する。`--type path` は同じ実走査を `.wikicommit/source/path/`（`source.path` で照合）に対して行い、`.wikicommit/.cache/extract-path/` 内の**抽出テキスト**キャッシュを解決する — 管理ファイルの相対パスを**末尾の `.md` ごと**使う（`raw/paper.pdf.md`。拡張子違いの同名ファイルの衝突を避けるため。落として付け直すと衝突が戻る）。`.md`/`.txt` のソースはキャッシュを持たないため、呼び出し側は生ファイルを読む（`docs/DesignDoc-pipeline.md` §6.1）。URL から `url_to_filename()` を再計算しないのは、旧フラット命名の管理ファイル（自動移行されない）で実際の scratch-path と食い違うためである。**exit 1 は終了コードを変えずに印字で 2 つに分ける** — 管理ファイルが無ければ `UNREGISTERED: <識別子>`、キャッシュが無ければ `NO_CACHE: <置かれるはずの位置> (<管理ファイル>)`（review / fix / relate はどちらも同じフォールバックで答えるので行を読まない）。**両モードとも、キャッシュを探す前に管理ファイルの `status` を見る** — `retracted` なら `RETRACTED: <識別子> (<管理ファイルのパス>)` を印字して **exit code 2** を返す（exit 1 は既に 2 つの意味を畳んでおり、`type: path` の経路では呼び出し側が exit 1 を生ファイルを読むことで答えるため、そこに畳むと取り下げ済みソースが素通りする。後に置くと「たまたまキャッシュがあるソースだけ」を守ることになるので順序も先）。読むのは `retracted` だけである（他の `status` 値は取り込み処理の状態であって文書への評価ではない）。**`--settle <取得したファイル> --page-hash <sha256>`** は、ask が `.wikicommit/.cache/ask-fetch/` に取得した後（取得前に `check_extraction_quality.py check-fetch-capability`）と、review / fix が `refetch/` に取得した後に呼ぶ: ページの `sources[].hash`（「ページが書かれた版か＝抽出ガードを通った版か」）と管理ファイルの `source.hash`（「generate が今キャッシュとして期待している版か」）と**別々に**照合し、**後者が一致したときだけ** `ingest-fetch/` へ移す。2 つは一致するとは限らない（保留した `LOW_DENSITY:` の取得・破棄された強制リチェックは管理ファイルの hash だけを進める）。review / fix はキャッシュに移ったファイルを読み、移らなかった取得は読んだ後に消す（review の「版が違う」記録は `page=mismatch` から得る）。`ingest-fetch/` を書く主体は generate と `--settle` になるが、置き場所はどちらも管理ファイルのパスから同じ規則で導き、`--settle` は管理ファイルには書かない。`add_source.py` とは同じ「ファイル名を再計算せず `source.url` / `source.path` で照合する」規約を共有するが、実装は共有しない（`add_source.py` は自己完結スクリプトである） |

#### 共有スクリプト（`.wikicommit/scripts/`）

`/wikicommit-init` が生成し、リポジトリで Git 管理される。複数 Skills から呼ばれる。

| Skill | 委譲するスクリプト | 理由 |
|---|---|---|
| `wikicommit-merge` | `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_orphans.py` | 品質ゲートとして変更ファイル全件を網羅的に検証するため |
| `wikicommit-review` | `validate_frontmatter.py` | frontmatter 補完前の検証に使う。経路A・経路Bいずれのページに対しても使用する |
| `wikicommit-status` | `check_orphans.py` / `check_wanted_pages.py` / `check_expires.py` / `check_ingest_freshness.py` / `check_translation_status.py` / `check_derivation_freshness.py` | 全ファイル走査・有向グラフ解析・日付比較・翻訳陳腐化検出／未翻訳検出・合成ページ陳腐化検出を正確に行うため。`check_wanted_pages.py` は Type セグメント取り違え（`TYPE_MISMATCH`）の分離も担う |
| `wikicommit-status` | `validate_frontmatter.py` / `check_wikilinks.py --skip-type-mismatch` / `check_raw_html.py` | merge が変更ファイルにしか走らせない blocking な 3 本を、書かれた後の全ページに走らせて `ERROR:` 行だけを拾うため。3 本とも書かれた後に壊れうる（語彙・型テンプレートの更新・後からの削除）。`--skip-type-mismatch` は `check_wanted_pages.py` の `TYPE_MISMATCH:` との二重報告を除く。詳細は `docs/DesignDoc-ScriptSpec.md` の該当節 |
| `wikicommit-status` / `wikicommit-generate` / `wikicommit-merge` | `check_distribution_freshness.py` | インストール済みの配布物がテンプレートと一致しているかを全件走査で突き合わせるため。後 2 者は Step 0 で `--only .wikicommit/scripts` に絞って呼び、**テンプレート側の写しを実行する**（`.claude/skills/` と `.wikicommit/scripts/` は別々のコマンドで更新されるため、古いかもしれない側から検出器を呼ぶと検出器自身が版ずれで落ちる。止めずに警告するだけで、対象を 2 Skill に絞る基準も含め `docs/DesignDoc-ScriptSpec.md` の該当節参照）。`.wikicommit/scripts/`・`quartz-plugins/`・2 つの workflow・`*.cjs` は WikiCommit 自身の配布ペイロードであり再 init で更新されるが、そのリポジトリが更新を要するかを知る手段はこれしかない。分類（`update` 列）は `_root_outputs.py` が唯一の情報源で、`init.py` のコピーと`print_next_steps.py` の `git add` 案内も同じ列から導かれる |
| `wikicommit-status` / `wikicommit-merge` | `check_review_coverage.py` | 前者はレビュー記録（`.wikicommit/review/`）を全ページ走査で突き合わせ、集計・未レビュー・抜取候補・失効を出すため。後者は `--discarded-reason` を呼び、生成失敗トラッキング Issue の理由欄を `result: discarded` の最新記録から取るため（Pass 4 step 7 が `## Failure Reason` を `partial` 分岐で削除するため、管理ファイルだけを読むと理由が構造的に必ず `unknown` になる）。`record_review.py` が書いたものを読む唯一の主体であり、これが無ければ記録ツリーは常に空のまま残る受け皿になる。閾値も自動化も持たない — `RISKY:` / `COVERAGE:` を人が読んで `--regenerate` を叩けばループは閉じる |
| `wikicommit-status` | `check_run_records.py` | 実行 1 回を単位とする記録を読み戻すため。他の記録層はすべて成果物（ファイル・ソース・ページ・レビュー）を単位としており、**実行が完走したか**・**どれだけかかったか**を答えられない。とくに前者は、途中で死んだ実行が残す状態が「まだ順番が来ていない滞留」と見え方が同じで、ガード C・`rules_version` 不一致に至ってはファイルを 1 つも変えずに止まるため git に痕跡が残らない。`record_run.py` が書いたものを読む唯一の消費者である |
| `wikicommit-status` / `wikicommit-review` / `wikicommit-fix` | `check_retracted_sources.py` | 前者は人間が取り下げたソース（`status: retracted`）を `sources[]` に持つページを全ページ走査で列挙するため。後 2 者は `--list` を呼び、ソース文書を取得する**前に**取り下げ済みのものを証拠集合から外すため（人が信用できないと判断した文書に忠実であることを根拠にページを通さないため）。判定（識別子 → 管理ファイル）が既にこのファイルにあり、同一性キーの規則の写しを増やさないためここに置く。取り下げは再登録・再取り込みを構造的に止めるが、既に書かれたページには何も起こらない — その差を埋める経路が他に無い。**行動ではなく報告に留める**（`review_status` を戻しても何が失われたかは伝わらない）。どの経路〈`--regenerate`〈取り下げたソースを落として作り直す〉/ `/wikicommit-fix` / `/wikicommit-remove`〉を採るかは人間の判断であり、各所見に「そのページに残っている他のソースの件数」を添えることがその判断材料になる |
| `wikicommit-status` | `check_actions_pr_permission.py` | "Allow GitHub Actions to create and approve pull requests" 設定の再確認を `gh api` 経由で決定論的に行うため（この委譲先だけが `.wikicommit/` 配下の走査ではなく `gh` CLI 呼び出しを要する） |
| `wikicommit-status` | `check_schema_coverage.py` | `type:` 値に対応する専用スキーマファイルが無いページ（＝ `default.md` へのフォールバック下で生成され、その型の `granularity`・`properties:` 候補・本文テンプレートが適用されていないページ）を全ページ走査で継続的に可視化するため（Completion Notice は生成時の1回きり、`validate_frontmatter.py` の WARNING は変更ファイルにしか届かない） |
| `wikicommit-status` | `check_property_wikilink_reinforcement.py` | `.wikicommit/schema/` 全型テンプレートの `properties:` キーについて Schema.org RANGE 分類（`check_schema_org_type.py --show-range` と同じロジック）を機械的に突き合わせるため（テンプレート間の補強の非対称の再発検出） |
| `wikicommit-status` | `check_schema_files.py` | 書かれた schema ファイル自体を検証するため。`.wikicommit/schema/` に置かれるファイルの出所は 3 系統（配布テンプレート・実行時に Skill が書いた型・人間の手書き）あり、**CI のテストが守れるのは 1 つ目だけ**である一方、schema ファイルは書かれた後どの Skill も編集できない（narrow exception は追加のみ可）。property の検証は `check_schema_org_type.py`、祖先の解決は `_schemaorg_vocab.py`、`provenance` を読む関数は `check_installed_type_usage.py` のものを使う。`check_property_wikilink_reinforcement.py` とは同じディレクトリを走査するが問う内容が逆で、あちらは「テンプレートがもっと述べるべきか」（望ましさ）、こちらは「そもそも動く形で書かれているか」（壊れている）。`wikicommit-merge` の品質ゲートには入れない — 壊れた schema ファイルが 1 つあるだけで既存リポジトリがマージ不能になり、しかも直せるのはどの Skill も触れないファイルを開く人間だけである |
| `wikicommit-status` | `check_recurring_characters.py` | `properties.character` のプレーンテキスト値を全ページ横断で集計するため。`ShortStory.md`/`Book.md` が下す「この登場人物は独立ページに値するか」の判断を後から見直す仕組みが他に無く、`check_wanted_pages.py` は WikiLink しか読まないためプレーンテキストの名前は wanted page として計上されない。作品をまたぐ再登場は 1 回の生成実行の中からは見えないため、事後の横断集計でしか拾えない |
| `wikicommit-status` | `check_unlinked_entity_mentions.py` | エンティティ型を range に持つ `properties:` キーの値を既存ページと突き合わせるため。`check_wanted_pages.py` の鏡像 — あちらが「リンクはあるが実体がない」を見るのに対し、こちらは「実体はあるがリンクされていない」を見る。生成時の判断が取り込み順序に引きずられて割れても、`action: update` はそのページ自身のソースが再 ingest された時にしか起きないため自然には回復しない |
| `wikicommit-status` | `check_installed_type_usage.py` | インストール済みスキーマファイルと実際の `type:` 使用状況を全ページ走査で突き合わせるため。`check_schema_coverage.py` の対 — あちらは「使われている型にファイルが無い」を見るが、逆（ファイルが在るのに使われない）は他のどのゲートにも掛からない。祖先型は常に技術的に正しいため、インストール済みの具体型が選ばれなくても品質チェックはすべて通る |
| `wikicommit-status` | `check_self_referential_tags.py` | ページ自身の `title`／`type` を繰り返すだけのタグを全ページ走査で検出するため。生成時の指示だけに依存して検出手段が無いルールは drift する。`title`／`type` との文字列比較で決定論的に判定できる |
| `wikicommit-search` | `search_index.py` | FTS5 trigram インデックスの構築・bm25 ランキング・スニペット生成には SQLite クエリが必要なため（Phase 3〜。Grep ベースの Phase 1 実装から移行済み） |
| `wikicommit-translate` | `check_translation_status.py` / `rebuild_index.py` | 前者は一括モードの対象件数（`UNTRANSLATED` + `STALE`）算出に全ページ走査・翻訳有無判定を正確に行う必要があるため。後者は `index.md` 更新を LLM の記憶に委ねない（長い手順の末尾が落ちる）ため（`wikicommit-generate` と共有） |
| `wikicommit-synthesize` | `build_survey_view.py` | 引数なしの俯瞰モードで、Wiki 全体を1つのコンテキストに収まる縮約ビューへ落とすため。「全体を俯瞰する」以上、走査の網羅性そのものが機能の前提であり、SKILL.md のプローズ（grep の羅列）に委ねると取りこぼしが黙って結果を損なう。スクリプトは判断を行わない — 縮約ビューから着眼点を選ぶのは LLM の仕事で、そちらは本質的に非決定論的 |
| `wikicommit-synthesize` | `rebuild_index.py` | 合成ページを書き出しただけでは view インデックス（言語別）に載らず、合成ページはどのソースからも生成されない（`derived_from` のみを持つ）ため `wikicommit-generate` が走る契機が無いリポジトリでは無期限に未掲載のまま残るため。他 2 Skill と異なり、書き出した 1 ディレクトリのみを引数に指定して呼ぶ（`.wikicommit/view/<lang>`） |
| `wikicommit-generate` / `wikicommit-review` / `wikicommit-synthesize` / `wikicommit-translate` | `.wikicommit/review-rules.md`（スクリプトではなくデータだが、委譲の構造は同じ） | レビュー規律を各経路で言い直さないため（§11.6「レビュー規律は `.wikicommit/review-rules.md` にある」）。移すのは「何を検査するか」だけで、段取りは各 Skill に残る。`_root_outputs.py` に `update: overwrite` で登録し、リポジトリ側からの編集を許さない — 許すと Wiki が自分のレビューを黙って弱められる |
| `wikicommit-init` / `wikicommit-collect` / `wikicommit-generate` / `wikicommit-schema-propose` | `.wikicommit/schema-authoring.md`（同じくデータ） | 型ファイルの書き込み手順を 4 箇所で言い直さないため（下記「複数 Skill に重複した手順は共有データファイルへ一本化する」）。移すのは手順だけで、**判定**（提案の閾値・承認 UX・`provenance` の値）は各 Skill に残る — 4 経路の役割分担は証拠の強さの違いによるものであり、そこを統合すると「ソースを読む前に断定できるか」と「ソース本文から断定できるか」が同じバーになる。配布は `review-rules.md` と同形（`update: overwrite`）。読むのは**候補が承認された時点**であり、ファイルが無い場合はその候補だけを却下して報告する（実行は止めない） |
| `wikicommit-generate` / `wikicommit-translate` / `wikicommit-synthesize` / `wikicommit-merge` | `record_run.py` | 実行 1 回につき 1 ファイルを開いて閉じるため。対象をこの 4 つに絞る基準は「途中で死んだときに、中途半端な状態と『まだ順番が来ていない』状態が区別できなくなるもの」であり、`fix` / `remove`（単発かつ小さく差分そのものが結果）・`collect`（対話前提）・読み取り専用 Skill（状態を変えない）は入らない。開始と終了の打刻は**忘れても壊れない** — 開始があって終了が無い記録が、そのまま「完走しなかった」の答えになる（レビュー記録の `page_content_hash: ""` と同じ形）。記録は git で追跡せず、ローテーションでき、`wikicommit-merge` は記録を運ばない |
| `wikicommit-generate`（将来は他の多段の Skill）/ `wikicommit-merge` | `driver.py` | 前者は多段の工程の**順序**をスクリプトが持つため（§11.0「多段の Skill の進行はドライバーが持つ」）。`next` が 1 工程ずつ返し、`done` がディスクの確認と `pass_token` の照合を経て完了にする。状態は実行記録の `driver:` キーにあり、毎回ログからリプレイする。後者は `check-merge` を Step 3 の最初に呼び、開いたままの実行が触れたファイルを含む変更を止める。**エンジンは WikiCommit 固有の知識を持たない**（`tests/test_driver.py` が固定する） |
| `wikicommit-generate` / `wikicommit-review` / `wikicommit-synthesize` / `wikicommit-translate` / `review-issue-close-sync.yml` | `record_review.py` | レビュー 1 件を不変ファイルとして書き出すため。判定は LLM が下し、ファイル手術はスクリプトが行う。`source_quote` の除去・`page_content_hash` の計算・`reviewed_sources` の収集を呼び出し側の指示遵守に委ねないことが要点で、とくに `page_content_hash` は `reset_review_on_content_change.py` の 6 フィールド無視リストを **import** して使う（複製すると drift し、drift は「誤った鮮度を黙って報告する記録」として現れる） |
| `wikicommit-generate` | `check_schema_org_type.py --list-type-names` / `check_schema_org_type.py --describe` / `check_schema_org_type.py --list-installed-hierarchy` / `check_schema_coverage.py` / `rebuild_index.py` / `check_extraction_quality.py` / `reconcile_ingest_status.py` | 前 2 つと `check_schema_coverage.py` は Pass 2b の型の要否判断用で、`--list-type-names` が約 933 型の**名前だけ**をプリロードし、そこから絞り込んだ候補の説明文を `--describe` が引く（2 段階にするのは、この一覧が果たしているのが想起であって存在保証ではなく〈実在は候補承認後の `--type` が決定論的に確かめる〉、想起には検討しない型の説明文が要らないため）。あわせて未スキーマ化 type 文字列一覧で収束を誘導する。`--list-installed-hierarchy` は Pass 2c にインストール済み型同士の祖先／子孫関係を渡すため（祖先型は常に当てはまるため、関係を示さないと粗い型が既定で選ばれる — 語彙から決定論的に導ける情報なのでモデルの記憶に委ねない）。`rebuild_index.py` は全ソース処理後の `index.md` 更新を決定論的スクリプトに委譲し、長い多段生成の末尾でLLMが更新を忘れるリスクを排除するため。`check_extraction_quality.py` は「非空だが無意味」な抽出結果（既知JS-shellドメイン・低情報密度）および「取得能力の不足による partial extraction」の判定を、LLMの主観的判断ではなく決定論的ロジックに委ねるため（判定結果の扱いは3ガードで異なり、既知JS-shellドメインはそのソースをブロック、取得能力の不足は処理全体を停止、低情報密度は人間に続行可否を確認する警告である）。`reconcile_ingest_status.py` は `status: pending` の管理ファイルのうち内容が既に公開ページの `sources` に使われているものを検出・是正するため（§11.6「パス 4 の後処理と書き戻し」） |
| `wikicommit-generate` | `match_existing_names.py` | Pass 2c が抽出したエンティティの名前を、既存ページの `title` / `aliases` と照合するため（`action: update` の判定を「型と slug が同じ」だけにすると、既存ページが別名として持つ名前で呼ばれた概念に新しいページが作られる）。照合は正規化後の文字列一致だけで、意味の近さは扱わない（同義かどうかは人の判断）。型が違う一致・複数ページへの一致は `update` にせず Completion Notice に出し、一致したのに別物として新しいページを作った場合はその判断を `## Generation Notes` と Completion Notice に残す |
| `wikicommit-generate` | `build_onehop_context.py` | Pass 4 の check 8 が要る 1 ホップ近傍を、散文ではなくスクリプトで組み立てるため。使い捨ての正規表現は文字クラスの誤り（`-` を含まない等）でケバブケース slug に**例外にならず集合が静かに縮む**形で外れる。`WIKILINK_RE` は `_wikilink.py` に 1 つだけ置く。抽出だけでなく 3 つの skip 判定・クロス言語フォールバック・outbound 優先の dedup・5 件上限まで委譲する — いずれも**集合を縮める操作**であり同じ性質を持つため。`--regenerate` も同じスクリプトを呼ぶ |
| `wikicommit-update` | `check_distribution_freshness.py` / `rebuild_index.py` / `validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` / `check_orphans.py` | 前者はドリフト検出そのものを担い（`wikicommit-status` と共有）、残りは更新後の検証に使う。`wikicommit-init/scripts/init.py` も`--no-overwrite`（`overwrite` の適用）・`--update-version`（版の刻印）・`--add-config-keys`（欠落キーの加算）の3 経路で呼ぶ — Skill 内スクリプトへの越境呼び出しにあたるが、**同じ Skill が持つ設定ファイル生成のロジックそのもの**であり、複製すると `_root_outputs.py` の `update` 列が唯一の情報源であるという前提が崩れる |
| `wikicommit-reconcile` | `set_frontmatter_field.py` | 管理ファイルの `status` を `pending` に書き戻す。同スクリプトはパス非依存（frontmatter ブロックを持つ任意のファイルを受ける）であり、`--require KEY=VALUE` で現在値を確認してから書く冪等な経路を持つ。**検出用のスクリプトは置かない** — ポリシー変更の判定器は Pass 2c 自身であり、もう一度呼べないことだけが問題だった |
| `wikicommit-relate` / `wikicommit-status` | `check_name_collisions.py` / `record_relation.py`（relate のみ）/ `rename_page.py`（relate のみ）/ `build_survey_view.py --pages`（relate のみ） | 名前の衝突の検出（判断済みの組を外す）と判断の記録は、網羅性と再現性が要る決定論的な操作であり、指示に書くと「1 つ漏れても出力は成功に見える」形になる。status は衝突を 1 行として数え、relate はその組を順に人に尋ねる |
| `wikicommit-organize` / `wikicommit-status` | `check_groups.py` / `rebuild_index.py`（organize のみ）/ `build_survey_view.py --pages`（organize のみ） | グループファイルの検証・未分類ページの列挙・stale な slug の検出は決定論的に決まるので、Skill の散文に委ねない。読み込みと検証は `_groups.py` に 1 つだけ置き、`rebuild_index.py` と `convert_wikilinks.py` も同じものを import する — 3 つの読み手が別々に YAML を解釈すると、「不正なファイルはグループ無しとして扱う」が 1 箇所でだけ崩れる |
| `wikicommit-generate`（`--regenerate --merge`） | `merge_pages.py` / `rewrite_merged_links.py` / `wikicommit-remove/scripts/remove_page.py`（越境） | 統合を許すか（判断の記録）・ソースの和集合・統合由来の別名・リンクの書き換え・完了の確認は決定論的に決まる。とくに統合由来の別名は Pass 4 の added aliases から除く一覧そのものであり、エージェントの読みに委ねると照合の対象が実行ごとに揺れる。吸収したページの取り下げは既存の `remove_page.py` を兄弟 Skill 相対で呼ぶ（翻訳への伝播と index からの削除を写さないため） |
| `wikicommit-schema-propose` | `check_schema_coverage.py` / `check_schema_org_type.py` | schema/ 未カバー type の網羅的集計、および型・プロパティが Schema.org 語彙に実在するかの決定論的検証（オフライン・遅延生成、Git管理下の`.wikicommit/schemaorg-vocab.json`）が必要なため |
| `wikicommit-generate` / `wikicommit-collect` | `read_policy.py` | ポリシーファイルの本文が「配布時の記入例のままか」は配布した本文が手元にある以上バイト比較で決まり、LLM に判定させない（両ファイルの記入例はすべて除外を促す内容なので、誤適用は常に「書かれるはずだったものが書かれない」方向に働く）。スクリプトは記入例と HTML コメントを落とすだけで、散文の解釈は引き続き LLM が行う |
| `wikicommit-generate` / `wikicommit-collect` | `match_index_only.py` | `index_only:` がドメインとページの 2 形を取り、2 つの SKILL.md の散文が別々に照合すると規則がずれるため。collect はページのエントリを能動的に掘るための一覧（`list-pages`）も得る |
| `wikicommit-collect` | `check_extraction_quality.py`（`check-domain` のみ。`check-fetch-capability`・`check-density` は候補提示ステップでは使わない — 前者は取得を実際に行う Pass 1 の関心事、後者は取得後にしか判定できないため） | Web候補提示ステップで、既知JS-shellドメインの候補を `wikicommit-generate` と同じ判定ロジックで事前に除外するため |
| `wikicommit-collect` | `check_wanted_pages.py`（`WANTED:` 行のみ。`TYPE_MISMATCH:` は対象外 — 実体は別 Type に在るので欠けているものが無く、必要なのは新しいソースではなくリンク 1 語の修正であるため） | Web候補探索で「この Wiki が WikiLink で参照しているのに実体ページが無い概念」を検索語として使うため（Purpose → Knowledge Gap → Source の転換を新機構なしで行う）。取得失敗・`WANTED:` 0 件のときは黙って飛ばし実行をブロックしない（複数ある探索パスの 1 つに過ぎないため）。**限界**: `WANTED:` が持つ slug は言語中立な英語識別子であり、非英語 Wiki では原語の検索語に一致しないことがある |
| `wikicommit-collect` | `build_survey_view.py` / `check_orphans.py`、および `check_wanted_pages.py`（Step 3.5 では上記の探索語用途とは別に、`WANTED:` を着眼点の根拠として読む） | Step 3.5 の俯瞰ステップで、Wiki の現状を 1 つのコンテキストに収まる形で読むため。3 本はそれぞれ別の問いに答える — `build_survey_view.py` は「何があるか」（`TYPE:` 件数・`HUB:`・`TAG:`・各ページの見出しと発リンク。1〜2 ページしかない型が手つかずの領域として見える）、`check_wanted_pages.py` の `WANTED:` は「Wiki 自身が書きたいと表明した穴」、`check_orphans.py` の `ORPHAN:` は出自ソース付きなので「1 ページしか作っていないソース」＝薄い領域が見える。いずれも読み取り専用である |
| `wikicommit-collect` | `wikicommit-generate/scripts/add_source.py --license-for-url`（Skill 内スクリプトへの越境呼び出し。下記） | Web候補提示ステップで、登録時に記録されるのと同じ既知ライセンスを候補行に併記するため（ShareAlike の警告を登録の 1 段手前へ前倒しする） |

#### ルート生成物の一覧は 1 つに保つ

`init.py` が書き出すルートレベルのファイルと、`print_next_steps.py` がユーザーに提示する `git add` 案内は、`.claude/skills/wikicommit-init/scripts/_root_outputs.py` の宣言的な一覧 1 本から組み立てる（手で同期する 2 本のリストにすると、片方にだけ入ったファイルが案内から漏れ、初回 push の Pages ビルドが落ちるような壊れ方をする）。`print_next_steps.py` はここから `git add` 行を組み立て、`init.py` は verbatim コピーが可能なエントリ（`template` フィールドを持つもの）をこの一覧から駆動する。

- **「init.py が書き出す ＝ ユーザーがコミットする」に収まらない例外は一覧上で表現する**（呼び出し側の特殊分岐にしない）: (1) `.gitmodules` / `quartz` は案内には出るが誰も生成しない（ユーザーが `git submodule add` する。`origin="submodule"`）、(2) `.wikicommit/schemaorg-vocab.json` は型提案ステップが実際にネットワークへ出たときにしか存在しない（`condition="vocab_cache"`。`git add` は存在しない pathspec でコマンド全体が異常終了するため、無条件に並べると基盤ファイルのコミットごと落ちる）、(3) `package-lock.json` は `npm install` の副産物であり、`git add` 行から意図的に外して別コマンドとして案内する（`in_git_add=False`）
- **印字される `git add` の既定は `-A` であり、一覧はその横に置くフォールバックである。** 列挙には誰も生成しないパス（`.gitmodules` / `quartz`）が載り、`git add` は存在しない pathspec を渡されるとコマンド全体を中断する（exit 128・staged 0 件）ため、列挙をそのまま既定にすると Quartz を後回しにした利用者の基盤コミットが丸ごと落ちる。`.gitignore` は `init.py` 自身が書く（`--quartz` では Quartz セクションを追記する）ため、**新規リポジトリでは列挙と `-A` の結果が一致する**
- **列挙が効く場面は既存リポジトリへの後入れだけ**（`docs/DesignDoc-data.md` §3.1）なので、「WikiCommit と無関係な未追跡ファイルがあるなら `git status --short` で確認するか、以下を個別に stage する」という注記として `build_git_add()` の出力を再利用する。`condition="vocab_cache"` と `in_git_add=False` は既定の経路では不要だが**どちらも機構ごと残す** — 注記側の列挙では依然として abort しうるうえ、後者は「これは決定であって漏れではない」を記録するフィールドである
- **`-A` が列挙と一致するのは「この Wiki のために作ったリポジトリ」に限る。** `.gitignore` は `_root_outputs.py` 上 `update="review"`（＝`always_skip_existing`）であり、既にあるリポジトリに後入れした場合 `init.py` はこれを書かない。したがって `node_modules/`・`.wikicommit/.cache/`・`.wikicommit/run/` が ignore されておらず、`npm install` の後に `-A` を打つと `node_modules/` が丸ごとコミットに入る。`print_next_steps.py` はリポジトリではなくフラグだけを受け取る設計なので、分岐ではなく**注記で伝える** — 併せて、後入れ向けの列挙が `.gitmodules` / `quartz` を含む以上そちらは依然 abort しうることもその場で明示する（`wikicommit-update` SKILL.md も同じ注記を出す）
- **submodule**: 作業ツリーが汚れているだけ（submodule 内に未追跡ファイルがある）でポインタが動いていない場合、リポジトリルートの `git add -A` は何も stage しない。ポインタが実際に動いている場合のみ `quartz` が stage される（初回コミットではそれが望ましい）
- **テスト**: `tests/test_smoke_local.py` は注記側の列挙どおりに add した後に未追跡ファイルが残らないことを検証し（ドリフトが残りうるのは列挙の側）、既定が `-A` であること自体は別のテストが固定する。`tests/test_root_outputs.py` は Quartz 限定の生成物が `wikicommit-init/SKILL.md` の散文にすべて現れることを検証する（SKILL.md は静的な指示書で生成する主体が無いため、散文は自動生成の対象にしない。全変種で生成されるエントリ〈`.gitignore`・`.wikicommit/entity/`・`review-issue-close-sync.yml`〉は SKILL.md 中でパスとして現れないので対象外）
- **`init.py` の生成処理そのものを一覧から駆動するのは verbatim コピーに限る。** `config.yml` と `quartz.config.yaml` はプレースホルダー置換、`schema`/`scripts`/`quartz-plugins` はディレクトリツリー、`entity`/`source` は `.gitkeep` 付きディレクトリ作成であり、いずれも一覧には載るが（`template=None`）生成コードは `init.py` に残る

#### 委譲関係の全体像

上の 2 表を、スクリプト側から「どの Skill に呼ばれるか」で見た図。同じスクリプトが複数の Skill から呼ばれる箇所が、`.wikicommit/scripts/`（共有）と `.claude/skills/<name>/scripts/`（Skill 内）を分ける判断基準そのものになっている。

```
.wikicommit/scripts/（共有・/wikicommit-init が配布・Git 管理下）
────────────────────────────────────────────────────────────────────────
validate_frontmatter.py ─────────────┬── merge
                                     ├── review
                                     └── status（全ページ・ERROR 行のみ）
check_wikilinks.py ──────────────────┬── merge
                                     └── status（--skip-type-mismatch・ERROR 行のみ）
check_raw_html.py ───────────────────┬── merge
                                     └── status（全ページ・ERROR 行のみ）
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
driver.py ───────────────────────────┬── generate（start / next / done。record_run.py に保存を任せる）
                                     └── merge   （check-merge。Step 3 の最初）
record_review.py ────────────────────┬── generate（Pass 4。PASS と discarded の両方）
                                     ├── review    （Step 5）
                                     ├── synthesize（Step 5.5）
                                     ├── translate （Step 4 item 5。translate-check）
                                     └── review-issue-close-sync.yml（kind: human）
check_actions_pr_permission.py ────────── status   ※唯一 gh を呼ぶ
check_property_wikilink_reinforcement.py ─ status   ※唯一 schema/ の型テンプレート自体が走査対象
check_translation_status.py ─────────┬── status
                                     └── translate（一括モードの対象件数算出）
rebuild_index.py ────────────────────┬── generate
                                     └── translate
reconcile_ingest_status.py ────────────── generate
set_frontmatter_field.py ────────────┬── review      （reviewed_by を落とす）
                                     └── reconcile   （status を pending へ戻す）
check_extraction_quality.py ─────────┬── generate（check-domain + check-density）
                                     └── collect （check-domain のみ）
read_policy.py ──────────────────────┬── generate（Step 0 / Pass 2c 用の方針読み込み）
                                     └── collect （Step 2.5）
check_schema_coverage.py ────────────┬── generate（Pass 2c の収束誘導）
                                     └── schema-propose（検出源）
check_schema_org_type.py ────────────┬── generate（Pass 2b/2c/3）
                                     └── schema-propose
build_survey_view.py ────────────────┬── synthesize（俯瞰モード／Step 3 の --pages）
                                     ├── collect （Step 3.5 の俯瞰）
                                     └── relate  （--pages。判断材料）
check_name_collisions.py ────────────┬── status（Step 10。relations.yml の最初の読み手）
                                     └── relate（引数なしの入口）
record_relation.py ──────────────────┬── relate（.wikicommit/relations.yml へ 1 項目追記）
                                     └── merge_pages.py（append_record() を import）
merge_pages.py ────────────────────────── generate（--regenerate --merge。plan / record / check）
rewrite_merged_links.py ───────────────── generate（--regenerate --merge。吸収したページへのリンクの書き換え）
build_onehop_context.py ───────────────── generate（Pass 4 / --regenerate。check 8 の近傍）
match_existing_names.py ───────────────── generate（Pass 2c。title / aliases との名前照合）
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
                                           ├── collect（--license-for-url / --fetch-url。越境）
                                           ├── review / fix（--fetch-url のみ。越境）
                                           └── ask（--fetch-url のみ。--include-source。越境）
wikicommit-remove/scripts/remove_page.py
wikicommit-ask/scripts/resolve_source_cache_path.py ─┬── ask（--include-source・--settle）
                                                     ├── review（Step 4。--settle も。越境）
                                                     └── fix   （Step 3。--settle も。越境）
```

#### Skill 内スクリプトへの越境呼び出し

本節冒頭の置き場所の規則に対する意図的な例外として、Skill が別の Skill の Skill 内スクリプトを直接呼ぶ箇所がある（上図の「越境」）。いずれも取得・同一性判定・対応表の実装を 1 つに保つためである: `wikicommit-collect` が `add_source.py --license-for-url`（候補提示）と `--fetch-url`（Step 5.5 の索引ページの取得）を、`wikicommit-review` / `wikicommit-fix` が `add_source.py --fetch-url` と `wikicommit-ask` の `resolve_source_cache_path.py` を、`wikicommit-ask --include-source` がキャッシュの無い URL ソースの取得に `--fetch-url` を呼ぶ。

- **`add_source.py` の対応表を `.wikicommit/scripts/` へ移さない。** 移すべき実体は `KNOWN_SOURCE_LICENSES`（登録可能ドメイン → SPDX 識別子の対応表）とそれを引く 2 関数だが、`add_source.py` は `.wikicommit/scripts/` からの import を持たない自己完結スクリプトである（慣行であって硬い制約ではない。§11.5「置き場所の判断基準」）。共有モジュール化には (a) この慣行を壊す、(b) 対応表を 2 か所に複製する、のどちらかが要り、(b) は「登録時に記録される値」と「候補提示で見せる値」が食い違いうる形そのものを作る（人間は提示された条件で承認し、記録されるのは別の条件になる）
- **`--license-for-url <url>` は読み取り専用の照会モードである。** 対応表を引いて `LICENSE: <id>`／`LICENSE: <id> (share-alike)`／`UNKNOWN: <url>` のいずれかを出し、常に exit 0 で、何も書き込まない。`tests/test_add_source.py` は照会結果と、同じ URL を実際に登録した管理ファイルの `source.license` が一致することを検証し、2 経路の drift を CI で止める
- **越境は新しい依存ではない。** `wikicommit-collect` Step 8 は `wikicommit-generate` の SKILL.md（Step 0）を名指しで実行しており、この 2 Skill の間には元から依存関係がある
- **候補提示は「不明」を書かない。** 対応表が持つのは、そのサイトが自サイトのコンテンツ全体に対して明示しているライセンスだけ（初期値は Wikimedia 系 8 ドメイン）なので、実際の候補の大半は `UNKNOWN` になる。ほぼ全行に「ライセンス: 不明」が付くと読み手はその行を読み飛ばすので、候補一覧の前置きに 1 度だけ「ライセンスは確認済みのサイトにのみ表示され、無表示は『条件を把握していない』であって『制約が無い』ではない」と書く。`sources[].license` が不明をフィールドごと省略して表す（空文字列で表さない）のと同じ線引きを、提示側でも保つ

**スクリプト委譲が不要な Skills**: **現在は 1 つも無い**。書き込み系の Skill はいずれも決定論的な状態の読み書きを持つ（`wikicommit-fix` も `reset_review_on_content_change.py`・`check_retracted_sources.py --list` を呼ぶ）。新しい Skill について「ツールだけで足りる」と判断するときは、決定論的な状態の読み書きが本当に無いかを確かめる。

SKILL.md での記述例（`wikicommit-status`）:

```markdown
## 処理フロー

1. `python .wikicommit/scripts/check_orphans.py` を実行し、孤立ページ数を取得する
2. `python .wikicommit/scripts/check_expires.py` を実行し、expires_at 期限切れページを取得する
3. `python .wikicommit/scripts/check_ingest_freshness.py` を実行し、outdated な管理ファイルを取得する
4. `.wikicommit/source/` を走査して `status: pending` の管理ファイル数を集計する
5. 結果を整形して表示する
```

#### 複数 Skill に重複した手順は共有データファイルへ一本化する

上の委譲はいずれも「決定論的な操作をスクリプトへ」という軸だが、**スクリプトにできない手順（LLM が読む散文）が複数の Skill に複製されている**場合の判断基準は別に要る。

**基準は「**短い**文面は各自が持つ方が総コストで優る」である。** 裏返せば、短くない文面は各自が持つべきではない。実測して線を引く:

| 重複している手順 | サイト数 | 合計 | 判断 |
|---|---|---|---|
| レビュー規律（何を検査するか） | 3 | 約 27KB | 一本化済み（`.wikicommit/review-rules.md`） |
| 型ファイルの**書き込み手順** | 4 | 20,031 B | 一本化済み（`.wikicommit/schema-authoring.md`） |
| レビューの**振り付け**（渡すもの・echo 照合・`record_review.py` の呼び方） | 3 | 約 39KB | 保留 — 各 Skill 固有の状態に絡み、全部は出せない |
| 型ファイル書き込みの**譲れない 3 点**（property 検証・`Boundary —`・`provenance`） | 4 | 各 1 行 | **各サイトに残す** — 短いので基準の逆側 |

**分けるのは「手順」と「判定」の線である。** 型提案の 4 経路（`wikicommit-init` の theme 駆動・`wikicommit-collect` の Type Proposal・`wikicommit-generate` Pass 2b・`wikicommit-schema-propose`）が共有しているのは書き込み手順だけで、提案の閾値・承認 UX・`provenance` の値はサイトごとに違う。`docs/DesignDoc-data.md` §3.3 が「証拠の強さと実行タイミングの違いによる役割分担」として正当化しているのは**後者だけ**である。

**行き先が `.wikicommit/` のデータファイルになるのは、読み手が複数の Skill ディレクトリにまたがるときだけである。** 読み手が 1 つなら、その Skill ディレクトリ内のファイルでよい（`--regenerate` の手順を `wikicommit-generate/references/regenerate.md` に置くのがこれにあたる）。どちらも**配布リストの同期を必要としない** — `install.sh` は `find -type f` で再帰コピーし、`.claude-plugin/plugin.json` は Skill **ディレクトリ**を列挙するため、`tests/test_skill_distribution_list_sync.py` が強制する 6 箇所の同期は Skill を増やしたときにだけ発生する。

**「読んだこと」の検証は、読み手がサブエージェントのときにしか成立しない。** `review-rules.md` の `rules_version` echo が働くのは、サブエージェントが返す JSON を orchestrator が照合できるためで、**同じエージェントが読む共有ファイルでは自己申告に退化する**。その場合は読書ではなく**成果物**を検証する側に回る（型ファイルであれば property の実在・`granularity` の箇条書きが文字列としてパースされるか・`Boundary` 行の有無）。したがって `.wikicommit/schema-authoring.md` には `rules_version` 相当を置かない。

**ファイルが無いときに実行を止めるかは、その経路に必ず到達するかで決まる。** `review-rules.md` は全実行が到達し、進めると劣化したレビューが自分をレビューとして記録してしまうため、実行の最初に確認して無ければ止める。型追加はゼロ件が通常の結果であり、進めてもエンティティがインストール済みの型に落ちるだけ（候補ゼロの通常ケースと同じ結果）で、`check_schema_coverage.py` / `check_installed_type_usage.py` が既に報告するため、**候補が承認された時点で確認し、その候補だけを却下して報告する**。

---

#### 非対話実行が人間の判断に当たったときの扱い

非対話実行（サブエージェント経由・無人実行）が人間にしか下せない判断に当たったときの扱いは、ここで 1 箇所に述べる。新しい非対話分岐を書くときは、下表のどの行に当たるかを先に決める（行を足さない）。

| 扱い | 使う場面 | 実例 |
|---|---|---|
| **決めない**（情報提供のみ） | そもそも判断を要さない。報告するだけ | 言語不一致・partial extraction |
| **自動で決める** | 証拠が最も強く、かつ事後の確認経路が**実在する** | **現在は実例が無い**。ここへ入れる判断は、この 2 つの条件を実際に満たしているかを先に確かめること — `wikicommit-merge` の PR は数秒後に自動マージされ誰も読まないので、事後の確認経路にはならない。とくに型ファイルは編集できず、ページを再分類する Skill も無いので、誤った承認は取り返しがつかない |
| **既定を決めておく** | 待つ先が無いか、既定が明らかに安全側で、かつ取り返しがつく | Step 0 のポリシー確認（登録せず報告）・5 件ガード（(b) 先頭 5 件）・`wikicommit-merge` の warning 続行確認（中断） |
| **保留する** | **人間が見れば答えが変わりうる**判断で、かつ保留したものが後から拾われる経路がある | ガード A の `LOW_DENSITY:`・Pass 2b の閾値未達・`ambiguous`・`action: update` の既存ソースが取得できない（下記） |
| **失敗にする** | 決定論的な判定。人間が見ても答えが変わらない | ガード B・抽出結果が空／読み取り不能・YouTube の URL 形式違い |
| **処理全体を停止する** | 環境の問題であってソースの問題ではない | ガード C・`rules_version` 不一致・`NETWORK_UNAVAILABLE:` の連続 2 件（1 件目は下記） |

##### ネットワークの不在

ネットワークの不在はパッケージの不在（ガード C）と同じ「環境の問題」であり、404 と同じ箱に入れない（入れると、ネットワークが使えない環境 — Codex の既定サンドボックス〈`workspace-write` はネットワーク無効〉・プロキシ・オフライン — で全 URL ソースが誤った `failed` として記録され、次の `/wikicommit-merge` がソースごとに生成失敗トラッキング Issue を立てる）。`add_source.py --fetch-url` は例外の連鎖を次のように分ける:

| 例外の連鎖 | 何が起きたか | 分類 |
|---|---|---|
| `requests` の `ReadTimeout`、または urllib3 の `ReadTimeoutError` がある | 読み取りのタイムアウト（サーバーに届いている） | `ERROR:` |
| HTTP エラー・変換失敗 | そのサーバー・ソースの問題 | `ERROR:` |
| `SSLError` | TLS ハンドシェイクまで進んだ＝サーバーには届いており、証明書の失効・自己署名はそのサイト固有の問題（TLS を中継するプロキシ下では逆向きに誤るが、`failed` に落ちるだけである） | `ERROR:` |
| `ProtocolError` があり `MaxRetryError` を経由しない、**その URL にプロキシが効いていない**、かつ TLS ハンドシェイクの最中に送出されたものではない | サーバーがリクエストを受けてから切った | `ERROR:` |
| 同上だが、連鎖のどれかが `ssl` の `do_handshake` の中で送出された | https の TLS ハンドシェイク中のリセット（ファイアウォール・サンドボックスが接続を受け付けてから切る）。リクエストはまだ送られていない | `NETWORK_UNAVAILABLE:`（保留） |
| 同上で**プロキシが効いている** | サーバーの切断か、プロキシが https の CONNECT をリセットしたか区別できない（連鎖が完全に同じ） | `NETWORK_UNAVAILABLE:`（保留） |
| それ以外の `ConnectionError` 系列 | 接続段階の失敗（名前解決・接続拒否・接続タイムアウト・プロキシの拒否。いずれも urllib3 の再試行の枠 `MaxRetryError` を通る） | `NETWORK_UNAVAILABLE:`（exit 3） |

- requests は本文の受信中の読み取りタイムアウトを `ConnectionError`（中身は urllib3 の `ReadTimeoutError`）で送出し、サーバーがリクエストを受け取ってから閉じた・リセットした場合も `ConnectionError`（中身は `ProtocolError`）になるので、`ConnectionError` かどうかだけでは分けられない
- TCP 接続が成立した後の TLS ハンドシェイクでリセットされると、urllib3 はそれを読み取りの失敗と同じ `ProtocolError` にし、requests の既定（`read=False`）により `MaxRetryError` を経由せず送出する。違いは**送出された場所**だけなので、連鎖の各例外のトレースバックに `do_handshake`（標準ライブラリ `ssl` の関数）があるかで分ける。urllib3 の内部の関数名ではなく `ssl` の名前を見るのは、版で変わりにくいためである（名前が変わった場合は `ERROR:` に戻り、実ソケットで連鎖を作る tests がその時点で落ちる）。**https で一律に保留へ倒さない** — URL ソースの大半は https なので区別がほぼ消える
- プロキシが効いているかは `requests.utils.get_environ_proxies()` と `select_proxy()` で決定論的に分かる。区別できない形を保留に倒すのは、誤っても次の実行で拾われるためである（失敗に倒すと、本当にネットワークが無い環境で誤った `failed` と生成失敗の追跡 Issue が残る）
- **`fetch_url()` のすべてのリクエストに `FETCH_TIMEOUT`（接続 15 秒・読み取り 60 秒）を与える。** `markitdown` は `session.get()` をタイムアウト無しで呼び（requests の既定は無制限）、引数でタイムアウトを受け取らないので、`requests.Session` の側で既定にする。読み取りのタイムアウトは 1 回の読み取りごとであり、本文全体の上限ではない
- **1 件目は保留し、連続 2 件で停止する。** 1 件で停止しないのは、消えたドメイン（ソース固有の問題）も同じく名前解決の失敗になり、1 件ではどちらか区別できないためである。実行の最初に到達性を確認することもしない（確認先が恣意的で、特定ホストへ届くことは任意の URL へ届くことを意味しない。連続 2 件での停止が同じ役割を事後に果たす）
- 保留は上表の「保留する」行と同じ実現方法（`status` を書き換えず `## Deferred Reason` を書く）を使うが、**適用条件は「人間が見れば答えが変わる」ではなく「後で再試行すれば答えが変わる」**であり、対話実行でも保留する。強制リチェック由来でも `pending` に戻さない — 取得していないので `source.hash` は元のままで、ソースは何も失っていない
- `/wikicommit-merge` の事前確認（`.git` への書き込み可否・`gh auth status`）はまだ置いていない（Codex の中で書き込み可否をどう判定すれば正しいかが実機でしか分からないため）

##### `action: update` の既存ソースが取得できない場合

Pass 4 はページの `sources[]` の**全件**の抽出テキストに対してレビューするが、`action: update` のページは以前の実行が取り込んだ別のソースを持つ。その本文は抽出キャッシュ（git で追跡しない）にしか無く、クラウドセッションのような clone 直後の環境では取り直すことになり、取り直しは 403・404・プロキシの 502 で失敗しうる。**このときは保留する。** 取れたソースだけでレビューすると「取得できない」が「裏付けが無い」に変わって記述が消え、`failed_pages` に入れるとレビューで落ちたと記録され、`excluded` はポリシー判断を偽って二度と拾われない。保留だけが「何が起きたか」以上のことを言わない。

| 論点 | 決定 |
|---|---|
| 判定の位置 | **Pass 3 の前**（Pass 2c の末尾）。Pass 4 で気づくと、同じソースの他のページが先に書かれてしまう |
| 取り方 | `references/regenerate.md` step 1 の取得の箇条（管理ファイルを `source.url` / `source.path` で特定・`status: retracted` は外す・キャッシュ優先）。**「変わった・取れないソースはページを飛ばす」箇条は取り込まない** |
| hash 不一致 | 保留の理由にしない。取り直した版でレビューし、不一致をレビュー記録の本文に 1 行残す |
| 強制リチェック由来 | `status: pending` に戻す（Pass 1 が新しい `source.hash` を書き込み済みで、戻さないと次の実行が `HASH_MATCH:` で更新を失う）。人間の判断待ちの保留と同じで、`NETWORK_UNAVAILABLE:` とは逆である。ドライバーの `check-pass2c` が、キューに残らない保留を拒む |
| 対話実行 | 対話実行でも保留する（待つのは人ではなく、そのソースを取れる環境か、人による取り下げである） |
| `NETWORK_UNAVAILABLE:` | この保留には含めない。Pass 1 と同じ扱い（`status` を戻さず、連続 2 件で停止） |

**受け入れる代償**: 恒久的な 403 やクラウドのプロキシが拒むホストでは、そのホストの既存ソースを持つページはローカルで実行するまで更新されない。保留は Completion Notice と `/wikicommit-status` に出続け、人が取れないソースに `status: retracted` を書けば取得の規則で外れて進む。

**`excluded` と保留を定義外の理由で使わない**（Pass 4 step 7 と Pass 1 の保留の節に書いてある）。当てはまるものが無ければ、近いものに寄せず止まって報告する。

##### 保留の適用条件と実現方法

**保留の適用条件は「保留したものが後から拾われる経路が存在すること」である。** 無いところには当たらない — `wikicommit-init` の対話プロンプト（`exclude_living_persons`）は 1 回きりでファイルを作る操作なので待つ先が無く、フィールドの欠如も `false` として扱われるため「未決」を表現できない。既定値で進んで `NOTE:` を出す。

**保留の実現方法は粒度で 2 つに分かれる**（`docs/DesignDoc-data.md` §4.3・`docs/DesignDoc-pipeline.md` §6.1）:

| 粒度 | 実現方法 |
|---|---|
| ソース単位（ガード A・Pass 2b） | **`status` を書き換えずそこで止める**。既存の収集条件にそのまま乗るので、新しい `status` 値もスクリプトも要らない。理由は `## Deferred Reason` に書く |
| エンティティ単位（`ambiguous`） | ソースは `partial` へ進むので、`ambiguous_entities` に**待っていることを記録する**。収集条件には乗せず、解除は `/wikicommit-reconcile` |

**「保留する」は「永続化する」ではない。** 「later, maybe としか言わない間接的な信号」（型候補をフィールドに記録して後で拾わせる形）は拾われない。保留は候補を記録するのではなく**そのソースの処理を進めない**だけである。次の実行が同じソースを同じ状態から読み直し、同じ候補に到達する。

**この方針は呼び出し側のループ設計に掛かる。** サブエージェントの中は定義上ずっと非対話なので、保留が無ければバッチをサブエージェントに委ねたとき、ガード A の誤検知がそのまま `status: failed` になる。失敗と保留は報告に現れなければならない — `wikicommit-merge` Step 9 は `status: failed` も生成失敗 Issue の対象にし、`wikicommit-status` Step 15 は `failed` / `excluded` / 保留 / `ambiguous` をそれぞれ数える。

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
  ├─ 抽出テキストの主言語を ISO 639-1 で 1 つ判断し source.lang に書く
  │    （primary_lang と違えば Completion Notice にも列挙。生成の挙動は変わらない）
  └─ source-as-entity 判定 … ソース文書自身も独立した「作品」ならエンティティ候補に追加

[Pass 2b] 型の要否判断（ソース 1 件につき 1 回）
  │  check_schema_org_type.py --list-type-names（約 933 型の名前）と照合し、
  │  絞った候補の説明文だけを --describe で引いて、
  │  installed schema/ の外に明確に良い適合先があるか判断（ゼロ件が通常の結果）
  ├─ 対話実行   → Enter ベース承認 [y/N]（既定 N）
  └─ 非対話実行 → 候補があればそのソースを保留（status を動かさず ## Deferred Reason）
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

#### コンテキスト予算 — 固定分と、5 件ガードの二重の役割

`/wikicommit-generate` は**ソースを 1 件も読む前に**メイン文脈へ固定のオーバーヘッドを積む。下表の数字は 2026-09-13 の実測であり、Pass ごとの手順を `references/` へ出す前（`SKILL.md` 本体が約 162KB だった構成）の値である。その後の構成では測り直していないので、内訳の配分は現在の構成と一致しない。

| メイン文脈に積まれるもの | 概算トークン |
|---|---|
| 最初のソースを読む前に載る分（`wikicommit-generate/SKILL.md` 本体〈Skill 起動のたびに全文が載る。§11.9〉・Step 0 の手順・Schema.org 型名一覧〈`check_schema_org_type.py --list-type-names`。1 実行 1 回〉等） | 約 43K |
| ソースを処理する実行なら必ず読む別ファイル 2 本（`references/text-extraction-routing.md`・`references/completion-notice.md`。SKILL.md が **Neither is optional** と書く） | 約 6K |
| **固定小計** | **約 49K** |
| 1 件あたり（抽出テキスト全文・Pass ごとの指示・生成ページ本文〈パス 3 がパス 4 のために保持〉） | **ソース次第**。実測 2 例は約 15K（日本語 Wikipedia 記事 1 本）と約 22K（混在ワークロード 30 件の逆算） |

収まらなくなる件数は (窓 − 49K) ÷ 1 件あたりを**切り捨てた**値（＝収まる最大の件数）で書く。22K/件なら 200K で約 6 件・1M で約 43 件、15K/件なら約 10 件・約 63 件。**128K では 5 件ガードの既定（5 件）そのものが 22K/件で収まらない**（約 159K）。

**5 件ガードは 2 つの役割を同時に果たしている。** パス 1 の「1 回の収集が 5 件を超えたら人間に確認する」というガードは、**1 回の処理量を人間が制御する**ためのものだが、結果として**コンテキスト予算も律速している** — 上の表の 1 件あたりに掛かる係数がその件数だからである。ガードを緩める判断（5 件を 10 件にする等）は、必要コンテキストを件数に比例して動かす。ただし**ループを呼び出し側へ出す運用では、コンテキスト側は拘束しない** — 1 回の呼び出しが 5 件に収まる限り、この警告が当たるのは呼び出し側が同一コンテキストでループした場合である。5 件ガードは上限ではなくプロンプトであり、「全件処理」と答えることは想定された使い方である。

**compaction の壊れ方**: 上限を超える運用は避ける。Claude Code では compaction 後に再添付されるのは**各 Skill の先頭 5,000 トークンだけ**である（`code.claude.com/docs/en/skills`）。**これは Claude Code というハーネスの挙動であって、モデルの性質でも agentskills.io 標準の一部でもない** — 標準が共有するのは SKILL.md の形式と frontmatter までで、コンテキスト管理は各ハーネスの実装である。したがってバージョンで変わりうるし、他エージェントでは別の壊れ方をする。**この数字を配布物の設計閾値や CI のガードに焼き込まないこと**（根拠だけが残って前提が消えるのは、§11.9 が扱っているのと同じ失敗である）。窓の外に落ちた手順はエージェントの手元から消え、**エージェントは残りの手順を持たないまま実行を続け、出力は一見正常に見える。** SKILL.md 本体を小さく保ち、Pass ごとの手順と checkpoint の打点指示を `references/` の各ファイルに置いているのは、再添付の窓が本体のほぼ全体を覆うようにするためである（§11.3「`references/` に置く条件」）。

**窓を超えたときの挙動はハーネスごとに違う。** Copilot CLI は窓の約 80% で背景で要約を始め、履歴を要約と「元のユーザーの指示」・計画の状態に置き換える（`github/docs` の `content/copilot/concepts/agents/copilot-cli/context-management.md`）。Skill の本文を再添付するとは書かれていない。Codex は `models.json` に窓を使い切ったときの手順（メモを残して新しい窓へ移る）を持つ。**どちらでも Skill の手順が何割残るかは未確認**であり、README は Claude Code の挙動だけを具体的に書いて他は「エージェントによる」に留める。

**利用者向けの式・推奨件数・公式ドキュメントへのリンクは `README.md` / `README_ja.md` が正本である**（`CLAUDE.md` は公開スナップショットに含まれないため、公開側だけを読む利用者に届く場所を正本にした）。README 側は 1 節で完結する — Requirements → Context window が、式・1 件あたりを変数として見せる表・5 件ガードの位置づけ・compaction で何が起きるか・モデル設定ドキュメントへのリンクを持つ。**固定分の内訳を持つのは本節である。** README の書き方の規則:

- **固定分は 49K の側を書く**（49K のうち 43K が最初のソースを読む前に載る）。利用者が契約を選ぶときに要るのは 49K の側である
- **表は窓幅の行（128K / 200K / 272K / 1M）で持ち、エージェント名を書かない。** モデル名はエージェントごとの箇条書きとリンク先に任せる。Claude Code に固有の記述（モデル名・`[1m]`・先頭 5,000 トークンの再添付）は「Claude Code では」と限定して書く
- **1 件あたり・固定分の数字は Claude Code の実測であることを明記する**（他のハーネスでは読み込み方とトークンの数え方が違いうる）。窓幅の行は実測ではなく算術なので、他のハーネスの実測を待たずに置ける
- **128K の行を置く以上、128K では 5 件ガードの既定が収まらないことを書く**（書かないと表が黙って矛盾する）。案内するのは名指しで 1 件ずつ処理すること（`/wikicommit-generate <path|url>` は引数のソースだけを処理する）か、大きい窓のモデルへの切り替えである。5 件ガードの閾値を設定可能にはしない — ガードは「1 回の処理量を人が制御する」ためのもので、コンテキスト都合の値を設定として持ち込むと 2 つの役目がさらに絡む
- 272K の行は Codex の既定に合わせて置く

**窓幅の出典（2026-10-01 確認）**:

| エージェント | 既定の窓 | 一次情報 |
|---|---|---|
| Claude Code | モデルにより 200K / 1M | `code.claude.com/docs/en/model-config` |
| Codex | **272K**（一覧の全モデルの `context_window`。`max_context_window` は多くが 872K、`gpt-5.5` は 272K） | `openai/codex` の `codex-rs/models-manager/models.json`（`main`） |
| Copilot（VS Code・CLI・クラウドエージェント） | **公開されていない**。最新のモデルは VS Code と Copilot CLI で拡張 1M を選べる | `github/docs` の `content/copilot/reference/ai-models/supported-models.md`・`content/copilot/concepts/agents/copilot-cli/about-copilot-cli.md`（commit `10844e10c034`） |

Copilot の既定の窓は一次情報では確認できない（GitHub のドキュメントは「default context size」と書くだけで数字を出さない）。Copilot CLI では `/context` が使用中のモデルの窓を表示する（`content/copilot/concepts/agents/copilot-cli/context-management.md`）ので、実機ではそれを読んで確かめる。表の 128K の行はエージェントを名指ししない一般的な窓幅である。

#### 固定分の内訳と、下げられるもの / 下げられないもの

**`SKILL.md` 本体と `references/` を分けても、1 回の実行が会話に読み込む総量は減らない。** 減るのは**起動のたびに丸ごと載る量**だけであり、目的はそちらに置く。通常実行は全 Pass を通るので、Pass 単位でファイルを割っても主経路で読まない部分は生まれない。`references/` に出すのは**入口によっては一度も読まれない**区画（`--regenerate` の手順・Completion Notice・拡張子別ルーティング表等）と、各 Pass の手順（compaction に対して本体を小さく保つため）である。

- **`--regenerate` は Skill を割らずに別ファイル（`references/regenerate.md`）にする。** Pass 1 / 3 / 4 は通常生成と共有しており、ファイルを割る理由は単位が違い（ソース起点 vs ページ起点）モード排他だからである。**読まなければ手順が無いので必ず止まる**ため、読み飛ばしが静かな失敗にならない（共有データファイル `schema-authoring.md` が「候補を却下して続行」なのとは非対称で、こちらは「停止して報告」である）
- **Completion Notice へのポインタは Processing Flow（再添付の窓の内側）に表として置く。** 末尾にだけ置くと窓の外に落ち、ファイルごと丸ごと消えて誰も気づかない形に戻る
- **`record_run.py end` は `references/completion-notice.md` の側に置く。** 本体に置くと、ファイルを読み忘れた実行は記録が正常に閉じたまま報告だけが 1 行も出ない。移した先に置けば、読み忘れは**開いたままの記録**として残り `/wikicommit-status` が `INCOMPLETE_RUN:` を出す（`ended_at` の空が「完走しなかった」の答えになる）
- **`## Notes`（書き込み権限の契約）は本体に残す。** 小さく、ファイル末尾にあって元から窓の外なので、出しても入れても窓に届かない。窓に届いている必要がある半分（「Git 操作を行わない」）は frontmatter の説明文にあり、残る半分（`.wikicommit/schema/` への narrow exception）を行使できるのは Pass 2b だけである
- **`--token` はこの形でしか成立しない**（`docs/DesignDoc-ScriptSpec.md` の `record_run.py` の節・§11.3）。同一エージェントへの分割では「読んだと自分に申告する」だけになるが、`record_run.py` が第三者としてそのファイルを開いて `pass_token` を突き合わせるので、「パスファイルを読まずに即興で実行した」が検出できる

**指標は `tools/check_skill_md_lines.py` の 2 本である** — **指示の総面積**（Skill ディレクトリ配下の指示 `.md` 全件のバイト数。既定 40,000 B）と **`SKILL.md` 本体**（行 ＋ バイト。既定 500 行 ＝ Anthropic のガイダンスの値と単位のまま）。対で読むと「本体 ↓ / 総面積 →」がそのまま「分割した」を意味する（行数だけを測るガードは、同じ内容を分割しただけで「改善した」と報告する。測定対象を変えずに分割すると指標が実態を追わなくなる）。閾値の根拠は**トークン費用の代理指標**（約 4 バイト/トークンで約 10K トークン）と**実測分布の自然な gap** の 2 方向からで、**compaction の窓には置いていない**（上記のとおりハーネスに属する数のため）。行数をバイトに替えたのは、`.md` の密度が 41〜166 B/line と 4 倍ばらつき、行数が読む量をほとんど言わないためである。**この指標は「別ファイルに出す」と「別コンテキストへ渡す」を区別しない** — 前者は同じ会話に読み込まれ、後者は読み込まれないため、サブエージェント化した Skill はこの指標上、実際より高く出る（静的には区別できず、frontmatter のマーカーで区別する案は消費者が居ないうちは配らないので、スクリプトの docstring に注記を置く）。

`check_skill_md_lines.py` は `over 500` を WARNING として報告するだけで `exit=0` なので CI は通る。`wikicommit-init` と `wikicommit-merge` は本体の超過が残っており、`wikicommit-generate` と同じ手（進行的開示）で扱う（`wikicommit-init` は `CHANGELOG.md` / `changelog/` という配布ペイロードを抱えており事情が違う）。

##### Pass のサブエージェント化は採らない

**コンテキストの「ピーク」を下げられる案はサブエージェント化だけである。** Skill を割ってもコンテキストは累積するのでピークは下がらず、各 Skill の前置きが重複する分だけ増える。サブエージェントは別コンテキストなので、親には戻り値しか載らない（前例は `generate` Pass 4 と `synthesize` Step 5.5 のレビューサブエージェント）。

**採る場合の切り口は圧縮率ではなく「ファイルが書かれる瞬間」に置く。** そこで切れば受け渡し形式は既にあり（管理ファイル・scratch・schema ファイル・ページ）、**新しい scratch 形式を作らずに済む**。副次的に再開可能性が付き、checkpoint の打点位置と境界が一致する。

**ただし Pass 2c ｜ Pass 3 だけは割らない。** そこは `## Generation Notes` に落としたもの（`exclude` と `coverage_gap_note`）は書くが、Pass 3 が要る「これから作るものの一覧」は書かない — **記録が残るのは否定側だけ**である。分析 JSON（`entities[]`）の永続化を禁じる規則は無く、割らないのは、割れば新しい scratch 形式を作ることになり、かつ Pass 2c → Pass 3 の間には分析 JSON に載らない文脈がある（**載っていないものが何かを誰も知らない**）ため測れない劣化を招くからである（`docs/DesignDoc-data.md` §4.6 が永続化を禁じているのは Pass 4 のレビュー JSON であって分析 JSON ではない）。したがって単位は次の 4 つになる。

| | 中身 | 抽出テキストの読み込み |
|---|---|---|
| 親 | Step 0（登録・対話）、収集と 5 件ガード、**Pass 2b の承認と schema 書き込み**、リトライ制御、`status` 更新、Completion Notice | 0 回 |
| 単位 A | Pass 1 ＋ Pass 2a → scratch を書き、`{path, hash, ガード判定, summary}` を返す | 1 回目 |
| 単位 B | Pass 2c ＋ Pass 3 → scratch を読み、管理ファイル body とページを書く | 2 回目 |
| 単位 C | Pass 4 → scratch とページを読み、判定 JSON を返す（既存） | 3 回目 |

Pass 2b が親に来るのは、summary だけで判断でき本文が要らない（同 Pass が "grounded in the Pass 2a summary" と明記）うえ、人間の `[y/N]` がそこにあるためである。**本文の読み込みが 3 回になるのは対話のときだけ**で、非対話実行では単位 A と B を融合できるため、親 1 ＋ Pass 4 サブ 1 ＝ 2 回のまま親のピークだけが落ちる。

**この構成は採らない。** 判断は 2 つの目的について別々に下しており、2 つを並べて持つ（目的が違えば論拠も再判断の条件も違うため、片方で他方を上書きしない）。

| 目的 | 採らない理由 | 再判断の条件 |
|---|---|---|
| **ピーク** | (1) 5 件処理は 200K 環境に収まっておりピークがいま問題ではない、(2) **Pass 3 が門番である** — 抽出テキスト全文を要するのは Pass 2a / 2c / 3 / 4 で、Pass 3 を親に残すと親は本文を読まねばならず他を全部サブエージェントにしても可変費は減らない。そして Pass 3 は圧縮率が最悪で人間が内容を見る判断も最も効く、(3) Pass 2c → Pass 3 の間には分析 JSON に載らない文脈があり、同じ品質が出るかを測る eval 基盤がこのリポジトリに無い | 5 件ガードを緩めたくなったとき、または 1 実行が 200K に収まらなくなったとき |
| **SKILL.md 本体の肥大化** | (1) 公式ガイダンス（`skill-creator` の Skill Writing Guide）は超過時の処方として進行的開示を名指ししており（「500 行に近づいたら、階層をもう 1 層足し、次にどこを読めばよいかのポインタを明示せよ」。progressive disclosure は Metadata / SKILL.md body `<500 lines ideal` / Bundled resources の 3 層）、サブエージェント化は肥大化への対処としてどこにも現れない。進行的開示は同じ区画を同じだけ削り、本体はむしろ小さくなる（振り付けがポインタより高いため）、(2) ループ／バッチ処理は呼び出し側の責務であり、1 回の呼び出しは 5 件ガードの範囲に収まるので、固定オーバーヘッドの削減（サブエージェント化の唯一の測れる便益）は拘束しない、(3) 残る便益（工程分担の構造的強制、暗黙の結合が受け渡し契約として表に出ること）は実在するが測れず、コストは確実である — とくに単位 B の契約漏れは黙って劣化する（効果を測る手段が無い一方でコスト増が確実なものは採らない、という `chain_of_thought` と同じ基準） | (1) 呼び出し側の解決が**同一コンテキストでのループ**に落ち着いた場合、(2) 進行的開示の後も SKILL.md が 500 行を超えて**再び成長した**場合、(3) 暗黙の結合 2 件（ガード A の対話性が自己申告であること・Pass 2c → Pass 3 の受け渡しが分析 JSON に載っていないこと）が実害として現れた場合 |

**対話性の判定は親が 1 回行って渡す形にする必要がある**（どの構成でも）。SKILL.md は対話性を自己申告で判定し、その文言は `non-interactive/subagent-driven` である — 現在の設計は「サブエージェントの中に居る ＝ 非対話」と**定義している**ので、Pass を素朴にサブエージェント化すると、親が対話セッションで動いていても内側は必ず非対話と自己判定し、型候補を持つソースが対話セッションでも全部保留になる。上の 4 単位構成は Pass 2b を親に置くのでこれを踏まない。

#### パス設計

```
[パス 1] テキスト抽出
  ソースのファイル種別に応じた Skill でテキストを Markdown に変換する。
  変換結果が空または読み取り不能の場合は処理を中断し、ユーザーに案内する。
  type: url/wikicommit ソースは変換前に既知JS-shellドメインチェック（ガードB）を通す。
  変換成功後、全ソース種別で低情報密度チェック（ガードA）を通す（詳細後述）。

[パス 2] 分析（LLM → JSON）— 内部で 2a/2b/2c の3段階に分かれる
  2a: 抽出テキスト全体からサマリを作成する
  2b: サマリを俯瞰し、installed schema/ 外の Schema.org 標準型が明確に良い適合先なら
      その場で人間の Enter ベース承認を得て .wikicommit/schema/<Type>.md を新規作成する
      （対話実行時。非対話実行時は候補があればそのソースを保留にする）
  2c: .wikicommit/schema/ の型リスト（2b で追加された型を含む）を LLM に渡し、
      「何をページ化するか」を JSON で返させる。実際のページ本文はここでは生成しない。

[パス 3] ページ生成（LLM → ファイル境界プロトコル）
  パス 2 の JSON の entities リストを元に Wiki ページを生成する。
  出力は ---FILE: path--- / ---END FILE--- 境界プロトコルで構造化する。
  エンティティごとの実行順序・並列化・リトライ戦略はエージェントに委ねる。

[パス 4] ソース整合性レビュー（レビューサブエージェント）
  生成ページの各主張をソース元文書と照合する。
  FAIL のページは再生成（最大 max_retries 回。DesignDoc-data.md §4.6 形式の issues[].instruction を
  再生成プロンプトに明示的に渡す）または failed_pages に記録して書き出しをスキップする。
```

#### パス 4 の後処理と書き戻し

- **Pass 4 のレビューサブエージェントは `docs/DesignDoc-data.md` §4.6 のエージェント間 JSON で返す**（Pass 4 手順1が明示的に要求する）。FAIL の再生成では、その `issues[].instruction` を Pass 3 の再生成プロンプトへ明示的に渡す（"regenerate the page" とだけ書くと、判定が次の再生成に配線されない）
- **`max_retries` を超えたページは `failed_pages` に記録して書き出さない。** `failed_pages` が1件以上ある管理ファイルは Completion Notice で個別に列挙し（`action: update` のページが FAIL したとき、既存ページが古いまま取り残されたことは他のどこからも見えない）、`wikicommit-merge` Step 9 が専用ラベル（`wikicommit-generation-failure`）の生成失敗トラッキング Issue にする（Step 8 のレビュー追跡 Issue と同じ全件走査・マーカー埋め込みパターン。`docs/DesignDoc-pipeline.md` §6.2）
- **管理ファイルの `status` / `generated_pages` の取りこぼしは `reconcile_ingest_status.py` が是正する。** 長い多段生成の末尾でエージェントが特定ファイルへの書き戻しを忘れる系統の失敗であり、指示で埋めずスクリプトに委譲する。Pass 4 手順7 は現在処理中のソースの管理ファイルだけを扱い、他ファイルの反映はこのスクリプトに一本化する。スクリプトの範囲は完全に決定論的に決まる部分に限る:
  - **`status: pending` の管理ファイルだけを対象にする。** `outdated` は対象外 — `check_ingest_freshness.py` は `status: outdated` に遷移させる際に `source.hash` を前回生成時点の参照点として保持するので、公開ページの `sources` との一致は「ページが最新化された証拠」ではなく「ソース変更前に生成済みだった証拠」でしかなく、含めると再処理が必要という正しいシグナルを握りつぶす
  - **`source.hash` が空ならスキップする**（`type: url` の未フェッチソースがワイルドカード一致するのを防ぐ）
  - **一致した場合は常に `status: generated` だけを設定する。** `partial` / `excluded` / `failed` は Pass 2/4 のエンティティ単位の結果が必要でその場限りの情報なので遡って推定しない
  - 処理中のソースの成否を別ファイルの `status`（`## Failure Reason` を含む）に当てはめる「バッチ全体」の書き戻しを指示に足さない（無関係なエンティティの成否が交差汚染する）
- Pass 4 の検査項目（ページ本文中の個別の具体的事実〈日付・固有名詞的事実〉の逐一照合、`sources` に実在しない引用文書の `MISSING_SOURCE`、「命名した」と「発明した」の取り違え、孫引き出典）は `.wikicommit/review-rules.md` にある（下記「レビュー規律は `.wikicommit/review-rules.md` にある」）。孫引き出典については、**現在の `sources` がある文書に言及していることは、その文書自体が `sources` に個別に取り込まれていることの代わりにならない**（後者だけが `MISSING_SOURCE` 判定における「実在」の基準）。Pass 3 は対になる規律（Secondary citation discipline）を持ち、現在のソースが言及するに留まる別文書の日付・タイトル等の個別詳細をページ本文の確定事実として書かない
- 複数の具体的実装（あるいは製品・プロジェクト）が同一の広い概念を異なる形で体現している場合、そのうち 1 つを無条件に一般定義として先出ししない（Pass 3 と `DefinedTerm.md` の `granularity` の「複数の具体的実装の代表性」ルール。主定義を起源で選ぶ軸とは独立した、公平な提示順序の軸）
- Pass 4 の手順番号は他の SKILL.md・references から相互参照されるので、検査を足すときは既存の番号付き手順に段落として追記し、番号付き手順を挿入しない

#### 再生成モード（`--regenerate`）

- **パス 2 を実行しない**（2b も走らせない）。対象ページの frontmatter が `type`・`title`・slug・`lang` をすべて持っており「何をページ化するか」は確定している。再生成は既存ページの型を前提とする操作であり、型自体の妥当性を問い直す操作ではない。したがってパス構成は `パス 1（再取得）→ パス 3（生成）→ パス 4（レビュー）` になる。パス 1 の再取得は `sources` の全件を対象とするが、`status: retracted` のソースだけは取得せず落とす（`docs/DesignDoc-pipeline.md` §6.1）
- **ソース起点ではなくページ起点**である。1 つのソースが複数の型のページを生成している場合、ソース起点の再処理は無関係な型のページまで巻き込む。Wiki ページは `sources:` に自身の出自（`path`/`url` + `hash`）を全件持っているため、ページを起点にそのページの `sources` を再取得してそのページだけを作り直せる（複数ソースからマージされたページも `sources` に全件並んでいるため成立する）
- **新規 Skill ではなく `wikicommit-generate` のオプションである。** パス 1 / パス 3 / パス 4 を通常の生成とそのまま共有し、差分は「パス 2 を飛ばす」「`review_status` を `pending` に戻す」「対象の指定方法（引数が**ソースではなくページ**を指す）」の 3 点に限られる。引数の意味は `--regenerate` があるかどうかで判別し、引数が `.wikicommit/entity/` 配下に解決しない場合はエラーで停止する（パスの形から意図を推測しない — 打ち間違えたソースパスが「成功に見える no-op」になるのを防ぐため）
- 対象の選別・件数ガード・キャッシュ利用・ハッシュ不一致時の扱い・ソース管理ファイルへの書き戻しの要否は `docs/DesignDoc-pipeline.md` §6.1 の「再生成モード」節を参照

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

- `summary` はソース全体の 2〜3 文要約（`config.yml` の `theme` が空でも常に生成する）。ソース管理ファイル body の `## Summary` に書き込まれる（§4.3・`DesignDoc-data.md`）。言語は `primary_lang` とする。付記フィールド（`exclude_note`・`coverage_gap_note`）は `## Summary` ではなく **`## Generation Notes`** に書かれる（`## Summary` は `content/sources/` の公開ページに載る唯一の節であり、そこへ除外理由を書くと実在の人物名と内部識別子が読者に届く）。言語はこの `summary` と同じ（＝ `primary_lang`）で統一する（指定しないと付記フィールドにエージェントのセッション言語が漏れ込み、同一管理ファイル内で言語が混在する）。**見出しラベル自体（`## Summary`・`## Generation Notes`・`## User Notes`）は本文の言語（`primary_lang`）に関わらず常に固定の英語**（見出しラベルは機械が照合する識別子でありローカライズ対象外。詳細は `docs/DesignDoc-data.md` §4.3）
- `lang` はパス 2 実行前に `.wikicommit/config.yml` の `primary_lang` を読んで全エンティティに設定する。**この設定はソース文書自体の言語に関わらず常に行われる**（意図的な設計）——`primary_lang: ja` のリポジトリに英語ソースを ingest しても、生成されるページの `lang` は `en` にはならず `ja` になる（内容は要約・翻訳された上で統合される）。この暗黙の挙動に気づかないと、例えば翻訳品質を実在する外国語原文と突き合わせて検証する用途で、比較対象のはずのページ自体が既にその原文を読んで書かれており検証が無効化される、といった問題が起こりうる。そのため Pass 2a は抽出テキストが主として書かれている言語を ISO 639-1 で常に 1 つ答え、管理ファイルの `source.lang` に書く（「明白な不一致だけを旗立てる」形にしないのは、永続化したときに欠如が「同じ」と「微妙」の 2 つを指すため。俯瞰ページのソース言語別集計が読む。`docs/DesignDoc-data.md` §4.3「`source.lang`」）。`primary_lang` と違えば Completion Notice で一言注記する
- `action: update` かつ `existing_path` がある場合は、既存ページを LLM コンテキストに追加してから生成する（既存情報を失わず新情報を統合）
- **`existing_path` は `action: exclude` のエントリにも設定する**。照合は `action: update` のための既存ページ走査と同一で、`(lang, Type, slug)` は Pass 2c がそのエンティティに付けた値そのものである。**生成側はページを削除しない**（削除経路は `/wikicommit-remove` だけ）ため、今回除外されたエンティティに前回以前の実行が作ったページが公開されたまま残ることがあり、それを名指しする主体が他にいない。`## Generation Notes` が記録するのはエンティティの**タイトル**であり、ファイル名は言語中立な英語 slug で、その導出規則（普通名詞は英訳／確立した原綴り／それ以外はローマ字）は**逆算できない** — `primary_lang` が英語でない Wiki では、人は `title:` を grep することになる。**機械はそのエンティティに名前を付けた副産物として答えを既に持っている。**
  - **このフィールドは `exclude` では情報であり、何も駆動しない。** `create`/`update` では Pass 3 が既存ページを読む分岐を駆動するが、Pass 3 はその 2 つしか処理しないため、`exclude` の `existing_path` は読み込みも書き込みも起こさない。**暗黙にせず明記する**（書かれていない前提は drift する）
  - 報告先は **Completion Notice と `## Generation Notes` の両方**。どちらも既存の行への追記であり、新しい報告ブロックは足さない。前者は人が対処を決める瞬間の出力（`failed_pages` と同じ形）、後者は管理ファイルに残る写しで、`_write_source_page()` のホワイトリスト外なので非公開のまま
  - **報告は断定しない。** 述べるのは「このページは在り、今回の実行は作りも更新もしなかった」までである — 3 件のソースに支えられたページの 1 件が今回 off-theme と判定されただけ、という形は普通に起こるため、除外は削除の根拠にならない（`check_installed_type_usage.py` の `ANCESTOR_FALLBACK:` が「示唆であって断定ではない」と自ら書いているのと同じ姿勢）。強さは `exclude_reason` で分け、`/wikicommit-remove` を指すのは `privacy` グループのみ。**自動削除は行わない** — ポリシーが決めるのは「作らない」であって「消す」ではなく、削除は不可逆で、`removed_reason` の選択も人間の判断に属する
  - `wikicommit-status` の常設チェックは置かない（1 回きりのイベントに常設チェックを置く形になり、大半のページの正しい対処は「残す」なので所見が消えない）。**`--regenerate` では発火しない** — 同モードは Pass 2c を実行しないため、この報告はソース起点の実行にしか現れず、入口は `/wikicommit-reconcile` が `status` を戻して合流させる経路である
- `ambiguous: true` のエンティティはページ生成をスキップし、コンソールに記録してユーザーに型の確定を求める
- `action: exclude`（Phase 2〜）はページ化しないと判断したエンティティ。`exclude_reason` は **`theme_mismatch` / `privacy` の 2 値**で、`exclude_note`（除外理由の説明文。`## Generation Notes` に反映される。`summary` と同じ言語＝ `primary_lang` で書く）を伴う。いずれも人間の確認なしに自動でページ生成をスキップする。2 つは互いの変種ではなく独立した別軸の理由であり、判定も別々に行う:
  - `theme_mismatch`: `config.yml` の `theme` に照らして無関係（**関連性**の軸）。`theme` が空文字列の場合、LLM に**この判定だけを**行わせない（off-subject を理由とする除外が消えるだけで、`exclude` 全体を禁じるのではない — 下の `privacy` は別軸として引き続き効く。`/wikicommit-init` の既定は空の `theme` であり、ここで `exclude` 自体を禁じると entity-policy を設定した Wiki で許容性の判定が丸ごと黙って無効化される）
  - `privacy`: `.wikicommit/entity-policy.md` が書いてよくないと定めたもの（**許容性**の軸。`exclude_living_persons` スイッチと散文本文の両方が入力になる。`docs/DesignDoc-data.md` §3.5）。ファイルが無い・スイッチ off・散文が空のいずれでもこの判定自体を行わせない。**両方の理由が同じエンティティに当てはまる場合は `privacy` を記録する** — Wiki の主題が変わっても残る側の理由であるため

  `copyright` は **enum に加えず予約のまま据え置く**。ソース側で保護期間・ライセンスを確認して取り込む設計になっている以上、エンティティ単位で「著作権を理由にページを作らない」と判断する場面がほとんど残らず、消費者を得ないまま並べると「受け皿だけ存在して常に空のまま残る」形になる
- **ソースがすれ違いに引用しただけの文書は、そもそも `entities` に出さない**。ソースが別の話を書きながら 1 回だけ名前を出した文書（対比のための引用・関連研究の 1 行・参考文献リストの項目）はエンティティではない。逆に、ソースがその文書ないしそれが引用されている事実を**自分の主題として**扱っている場合（タイトルか中心的な主張がそれについてである）は通常のエンティティであり、他のルールがそのまま適用される。**両側を対にして書く** — 片側にしか書かれない境界は片側にしか適用されない。
  - 判定は `.wikicommit/review-rules.md` の check 1 / check 4 と**同じ主題性のテスト**を 1 段早く当てるだけである。**判別がつかない場合は passing mention 側に倒して抽出しない** — これは好みではなく、check 4 が同じ引き分けを同じ側に倒すためである。Pass 2c だけが不明瞭なケースで寛容だと、その差分がそのまま「抽出 → 生成 → 却下 → 記録 → 再実行」の無駄な 1 周を**構造的に保証する**
  - **登録の有無は判定に持ち込まない。** ソース登録簿（`.wikicommit/source/`）は Pass 2c のコンテキストに元から入っておらず、本ルールも走査を求めない。その文書が別途登録されていれば、そのソース自身の実行がページを作る。本ソースが寄与しなくなることは損失に見えるが、passing mention である以上そこに書ける事実は元から無い
  - **Pass 2a の source-as-entity 判定とは別物である。** あちらは「ソース文書**自身**をページ化するか」、こちらは「ソースが**引用した別の文書**をページ化するか」。1 回の実行で両方が発火しうる
  - **非抽出は痕跡を残さない。これは受け入れる。** `action: exclude` なら `## Generation Notes` と Completion Notice に 1 行残るのに対し、抽出しないことは無言である。3 つ目の `exclude_reason` を足せば記録は残るが、この軸は関連性でも許容性でもなく**証拠**であり、消費者のいない enum を配ることになる。**露出が限定的なのは片方向だけであり、だからこそ過剰適用してはならない。** passing mention を正しく落とす側は、どのみち Pass 4 が却下していたページが 1 段手前で消えるに留まる。一方、ソースが本当に主題として扱っている文書を誤って落とす側は対称ではない — そのページはレビューを通ったはずであり、`exclude_note` も Completion Notice の行も残さずに消えるうえ、書かれなかったページは orphan でも wanted page でもないのでどのヘルスチェックにも現れない。引き分けの倒し方は**本当に判別がつかない場合に限り**、タイトルか中心的な主張がその文書についてであれば抽出する
  - **抽出・執筆・レビューの 3 段が同じ境界を持つが、共通ルールの言い直しではない。** 3 段が下している判断は別物である — Pass 2c は**エンティティを作るか**、Pass 3 は**本文に別文書の日付・タイトルを確定事実として書くか**（Secondary citation discipline。**残す**）、Pass 4 は**FAIL にするか**。同じ命題の言い換えではなく、同じ境界を 3 つの異なる決定に当てている（`review-rules.md` の check 1 と check 4 が意図的に対になっているのと同じ関係）
- `slug` は言語中立な英語識別子とする（CLAUDE.md の WikiLink 節）ため、日本語発音の音写ではなく以下の優先順位で決定する:
  1. 普通名詞・概念語 → 英訳した slug にする（例: `キリマンジャロコーヒー` → `kilimanjaro-coffee`。`kirimanjaro-koohii` のような音写は不可）
  2. 固有名詞（人名・組織名・地名等）で英語圏に確立された原綴りがあるもの → その原綴りを使う（例: `スターバックス` → `starbucks`。`sutaabakkusu` は不可）
  3. 上記いずれにも該当しない固有名詞 → ローマ字表記でよい（例: `山田太郎` → `yamada-taro`）
- `expires_at` はソース本文が明示的な期限（申請締切・有効期限・年度区切り等）を述べている場合のみ `YYYY-MM-DD` を設定する。それ以外は `null`。日付を推測・逆算しない。複数の期限が併記されている場合（最後の `schema:GovernmentService` の例のように支給時期ごとに締切が異なる等）は、そのうち最も早い日付を採用する — この値は再チェックを促すためのフィールドであり、遅すぎるより早すぎる方が安全という判断（詳細は日付選定を含め `.claude/skills/wikicommit-generate/references/pass2c-entities.md` を参照）。Pass 3 はこの値を非 null のときのみページの `expires_at` frontmatter に書き込み、`null` のときは既存ページの `expires_at`（あれば）を変更しない。Pass 4（ソース整合性レビュー）は `expires_at` も他の主張と同様にソースとの照合対象に含める。**日付は「このページが読者に伝える内容が古くなる日」でなければならない** — 読者が行動する期限（申請締切・有効期間）は対象で、文書の経緯の中で第三者に宛てた締切（各国政府・会員・一般へのコメント・回答・提出の期限、会議の日程）は過ぎてもページの内容が古くならないので `null` にする。Pass 4 の check 1 は「ソースがその日付を述べているか」しか見ないのでこれを止めない（日付の意味の判定をレビュー規律に足すと `rules_version` を上げることになり、生成側の規則と決定論的な WARNING で足りる）。`expires_at <= generated_at` は判断を要さず決まるので指示文に書かず、`validate_frontmatter.py` が WARNING を出す（ERROR にしないのは手書き・旧版のページにもありうるため。書き出し前にドライバーの確認で落とすことはしない — 本文の日付とずれる書き換えを伴う）。
- `coverage_gap_note` は、そのエンティティの型スキーマファイルの `properties:` ブロックに受け皿がないドメイン固有の具体的な属性（対象年齢・道具・管轄自治体等）がソース本文に含まれていた場合のみ、単一の文字列として設定する（`exclude_note` と同じく配列にしない。1エンティティで複数の属性が不足していても1文にまとめる）。`create`/`update` エンティティのみが対象で、`exclude`/`ambiguous` エンティティには設定しない。何も不足がなければ `null`（通常はこちらが大半を占める想定）。1件以上存在する場合、`summary` と同じタイミングで管理ファイルの `## Generation Notes` に書かれる（エンティティごとに1文。公開される `## Summary` には書かない）。`summary` と同じ言語（＝ `primary_lang`）で書く。スキーマファイル（`.wikicommit/schema/`）への書き込みは一切行わない — 本フィールドは証拠収集のみを目的とし、ページ本文にはその情報を書く（`## Generation Notes` の記載場所自体は `docs/DesignDoc-data.md` §4.3 の ソース管理ファイルフォーマット参照）。
- 最後の `schema:GovernmentService` の例は、Pass 2b（下記）でこのソース向けに承認・新規作成された型を Pass 2c がそのまま使ってエンティティを生成した結果を示す。このエンティティが指すのは制度そのもの（対象者・支給額・支給時期）であり、**申請の手順は別の主題**である — 同じソースが手順も述べているなら、それは別の型の 2 つ目のエンティティになる（`docs/DesignDoc-data.md` §5.4・本節 Pass 2c の該当ルール）。この例を「1 ページに対して `GovernmentService` が正解で `HowTo` が不正解」と読まないこと。分析 JSON は「より良い型の候補」を記録するフィールドを持たない — 型の追加は Pass 2b がその場で行う（下記「パス 2b: 型の要否判断」）。

#### レビュー規律は `.wikicommit/review-rules.md` にある

パス 4 の「何を検査するか」は `.wikicommit/review-rules.md` にあり、`wikicommit-generate` Pass 4・`wikicommit-review` Step 4 手順 3・`wikicommit-synthesize` Step 5.5（と `wikicommit-translate` の照合）が読む。各経路に書くと食い違い、どれが正しいかを誰も決めていない状態になる（「短い文面は各自が持つ方が総コストで優る」の基準に照らして短くない。§11.5「複数 Skill に重複した手順は共有データファイルへ一本化する」）。

- **移したのは「何を検査するか」だけで、段取りは各 Skill に残る** — Pass 4 の step 4〜8（リトライ・`failed_pages`・書き出し・`reset_review_on_content_change.py`・`status` 更新）・`wikicommit-review` Step 5・`wikicommit-synthesize` の grounding set 構築。`tests/test_review_rules_single_source.py` が両方向を CI で固定する（規律が SKILL.md に書き戻されていないこと・段取りが Skill から消えていないこと）
- **両側から守る。** ルールファイル（受け手側）は「証拠として扱ってよいのは `SOURCE` と印されたブロックのみ」と定め、SKILL.md（渡し手側）は「サブエージェントに渡すのはページ・抽出テキスト**全文**・1 ホップ先の 3 つに限る」と定める。プロンプトを組み立てるのは Pass 3 でそのページを**自分で書いたエージェント**であり、そのコンテキストには渡すべきでないもの（Pass 2a の `summary`・Pass 2c の分析 JSON・前ラウンドの判定）が揃っている。**証拠拘束ルールはこれを止められない** — あれが禁じているのは「自分の**世界知識**で判定すること」であり、`summary` は世界知識ではないのでこのルールをすり抜ける。それでいて literal source text でもない。要約に対する照合は、ソースに対する照合ではない
- **`rules_version` の echo 検証**: SKILL.md は機構として全文がコンテキストに載るが、別ファイルはエージェントが読むことを選ぶ必要がある。読まなければレビューは「ページをソースと照合する」だけに落ち、**しかも出力は正常に見える**。ルールファイルの frontmatter に `rules_version` を置き、サブエージェントが返す JSON にそれを含めることを必須にして orchestrator が照合する。欠落・不一致なら 1 度だけ起動し直し、それでも駄目なら**処理全体を停止して報告する**（`generate.max_retries` を消費させない・`failed_pages` に落とさない。ガード C と同じ扱い — 環境・指示の問題であってページの欠陥ではなく、ページ側に記録すると誤った記録が残る）。`wikicommit-review` はサブエージェントを使わないため echo 検証が効かず、この限界はルールファイルと SKILL.md の両方に明記してある
- **ファイルが無い既存リポジトリは処理を停止する。** `.wikicommit/review-rules.md` は `_root_outputs.py` に `update: overwrite` で登録されており再 init で配布されるが、`npx skills add` で Skills だけ更新したリポジトリには無い。SKILL.md に最小限の規律を残すことはしない（「2 箇所に同じ規律がある」状態を作り直すため）。進めると、黙って劣化したレビューがレビューが行われたと主張する記録まで書く。停止時は `/wikicommit-init --no-overwrite` を案内する
- **`update: overwrite` は意図的で、`*-policy.md` 2 つとは逆である。** あちらは人間が書くファイルで `review`。こちらは WikiCommit の規律であり、編集可能にすると Wiki が自分のレビューを黙って弱められる。`review-policy.md` という名前にしないのも同じ理由で、`*-policy.md` という接尾辞は「ここに自分の方針を書いてよい」という誤ったシグナルになる

#### パス 2b: 型の要否判断

パス 2a（サマリ作成）とパス 2c（エンティティ抽出）の間に挟まる、ソース1件につき1回だけ実行するステップ。「`installed schema/` 内の型より明確に良い適合先がある」という判断を、後で別の Skill に拾わせる記録（間接的な信号）にせず、**その場で解決する**。間接的な信号は拾われない — `wikicommit-schema-propose` の検出源 `check_schema_coverage.py` は「既に `installed schema/` 内の型で生成済みのページ」を検出対象にできず、情報が構造的に失われる。

1. パス 2a のサマリと、`check_schema_org_type.py --list-type-names`（1 実行 1 回プリロードする約 933 型の**名前**の一覧。絞った候補の説明文は `--describe` で引く）を基に、`installed schema/` 外の Schema.org 標準型がこのソースの内容に明確に良く適合するか判断する（`installed schema/` に既にあるファイルは候補から除外。このバッチ内で既に追加された型も除外）。ゼロ件が通常の結果であり、無理に候補を出す必要はない。
2. 候補があれば、対話実行かどうかで分岐する（判定方法は既存の自己申告ロジック）: 対話実行なら Enter ベース UX で人間に個別確認する（デフォルト N）。非対話実行（サブエージェント経由等）なら、Enter プロンプト自体を表示せず、候補が 1 件でもあればそのソースを保留にする（§11.5 の保留。`status` を動かさず `## Deferred Reason` を書き、次のソースへ）。プロンプトなしの自動承認はしない（`docs/DesignDoc-data.md` §5.4「インストール済みに無い型 — Pass 2b がその場で足す」）。
3. 承認された型（対話承認のみ。`provenance: generate-interactive`）は `check_schema_org_type.py --type <Type> --property <Prop1> ...` で `recommended` プロパティ候補を検証した上で、`.wikicommit/schema/<Type>.md` を標準型フォーマット（§5.2・`DesignDoc-data.md`）でその場でローカルに新規作成する。`wikicommit-generate` の「Git 操作なし・schema/ 不可侵」契約に対する「追加のみ可・既存ファイル編集不可」の narrow exception。PR は経由しない — 通常の `.wikicommit/entity/`・`.wikicommit/source/` の変更と同じバッチとして `wikicommit-merge` が後で拾う（`.claude/skills/wikicommit-merge/SKILL.md` Step 2 item 4・Step 5）。（非対話自動承認が存在した期間に書かれた型は `provenance: generate-auto` を持つ。）
4. 却下・候補なしの型はどこにも永続化しない（間接的な警告機構を作らない）。却下した候補はその実行の Completion Notice に列挙する。事後の救済は `wikicommit-schema-propose` の役目とする。

パス 2c は、パス 2b で追加された型を含めて `.wikicommit/schema/` を再走査してから実行する。

#### 固有名詞エンティティ

Pass 2b の閾値（「明確に良く適合する」場合のみ提案する）は意図的に保守的だが、**候補エンティティが抽象的な用語・概念・方法論ではなく、固有名詞を持つ具体的な対象**（ソフトウェア製品・研究データセット/ベンチマーク・創作物・規格等、分野を問わない）である場合、`DefinedTerm` で技術的に表現できることは新型提案を見送る十分な理由にならない（`DefinedTerm.md` の `granularity`「ドメイン固有の用語・概念」は実質的に何にでも当てはまる受け皿であり、それを理由に見送ると Claude Code という製品や GAIA のようなベンチマークが `DefinedTerm` になる）。

- 抽象概念（例: 対応する標準型のない "vibe coding" のような方法論）に対する保守的な閾値は変えない — 閾値全体を緩めるのではなく、named-entity パターンに限定した部分的な緩和である
- `DefinedTerm.md` の `granularity` も、DefinedTerm が抽象概念の受け皿であり固有名詞を持つ具体的エンティティの第一選択ではないことを明記する（`.claude/skills/wikicommit-init/scripts/templates/schema/DefinedTerm.md`）
- 既存ページを別の型へ再分類する仕組みは無い。`check_schema_coverage.py` は「`type:` 値に対応する専用スキーマファイルが存在するか」のみを判定するため、型ファイルは存在するが選ばれた型が内容的に誤っているケースは検出できない。型変更＋本文再構成を PR 化する仕組みは将来検討課題として [DesignDoc-phases.md](DesignDoc-phases.md) Phase 3 節に記録してある

#### 物語ソースの登場人物

物語ソースの登場人物を `Person` ページへ昇格させるかの分かれ目は、登場回数でも実在性でもなく、**そのソースがその人物を「単独で紹介される対象」として書いているか「ある物語のなかの誰か」として書いているか**という語り口である。既存のルール（`ShortStory.md`/`Book.md` の `character` 行・`Person.md` の independent-subject 判定・Pass 3 の Property-value WikiLinks）は「作らない」側の判断材料しか与えないので、包含側の経路を 2 本定義する。いずれも「1 作品あたり最大 1 ページ + 再登場人物」に上限が付く（「名前のある登場人物すべて」は昇格対象にしない）:

- **軸 A（単一作品の主人公）**: その作品が**丸ごとその人物についての話である**なら、その人物は independent subject である。物語はその人物が何をし、どう置かれているかという独立した事実を述べており、それは他の Person ページに適用しているバーそのものである。架空であることは関係しない（`schema:Person` は公式に架空人物も含む）。その作品の筋書きの中で動くだけの脇役は昇格しない
- **軸 B（作品をまたぐ再登場）**: この Wiki が扱う 2 件以上の作品に登場する名前は、独立ページ候補として再評価する。再登場は単一の作品からは得られない「この人物は 1 つの筋書きを超えて存在する」という証拠である

**反映先**: 軸 A は `Person.md` の `granularity`（包含側）、軸 B は `ShortStory.md`/`Book.md` の `character` 行。**Pass 2c 側に独立した指示は置かない** — Pass 2c は各スキーマファイルの `wikicommit.granularity` ルールをコンテキストとして受け取るため（本節「SKILL.md への記述指針」パス 2）、型テンプレートに書けばそのまま抽出判断に届く。ルールの持ち主である型の側に置く方が、同じ内容を 2 か所に持つより整合する。

**軸 B は型テンプレートだけでは実行できない。** Pass 2c が受け取る既存ページ情報は「タイトル + パス」であって、他の作品ページの `properties.character` の中身ではない — 再登場は 1 回の生成実行の中からは原理的に見えない。`check_recurring_characters.py`（`docs/DesignDoc-ScriptSpec.md`）が事後に横断集計し、`wikicommit-status` Step 7 が報告する。`Person` ページが既に在るのにプレーンテキストのままの値は、要求される行動（リンクにする）が `RECURRING`（ページを作る）と正反対であるため、`check_unlinked_entity_mentions.py` の担当である。

全文ソースは登場人物それぞれについて独立した事実（役割・行動）を十分に述べるので脇役まで昇格しうる一方、概要記事のあらすじの中では登場人物は「筋書きの中の誰か」としてしか現れない。この差は上の線引きと矛盾しない（全文ソースなら軸 A のバーは自然に満たされ、概要ソースでも「その話が誰についての話か」は述べられているため主人公は拾える）。

#### 存命の個人の記述範囲

`Person.md` の `granularity` は、存命の個人のページをその人が自ら公表したもの（著作・発言・自称する役職）に寄せ、経歴・所属歴・生年月日といった一次資料での裏取りが要る事実はソースが述べていても書かない、と定める。同ファイルの「家族関係のプロパティ（`spouse`/`children`）・身体的属性（`height`/`weight`）はソースが述べていても書かない」と同型のルールであり、誤りのコストが最も高い対象への適用である。孫引き出典への規律（「書くなら裏を取れ」）とは別に、「そもそも書く量を減らす」を担う。

- **`properties:` のキーは削らない。** テンプレートは `affiliation` / `jobTitle` / `birthDate` を候補キーとして提示し続ける — 故人・歴史上の人物には有効であり、書かないと決めた項目は Pass 3 の「埋められないキーは省略する」ルールでキーごと落ちる（空文字列は残らない）
- **本文テンプレートの `## Background` には但し書きを置く。** 節の指示が "chronological activities, affiliations, and roles" のままでは、`granularity` と同じファイルの中で反対のことを Pass 3 に指示することになる（`properties:` と違って本文側には「埋められないキーは省略する」のような受け皿が無い）。`DefinedTerm.md` の `## When It Applies` が「他の 2 種類では丸ごと省く」と placeholder 自身に書いているのと同じ形
- **`.wikicommit/entity-policy.md` との分担**: あちらは「そもそもページを作るか」という型をまたぐ**許容性**の判断で、`exclude_living_persons` は既定 off。こちらは「作るとして何を書くか」という型スコープの**記述範囲**で、常に効く。両方入れても重複しない — 前者が off の Wiki でも後者は働く。`granularity` の該当箇条書きがこの分担を 1 文で述べ、そのファイル名を名指しする（配布物から参照してよいのは利用者のリポジトリに実在するパスであり、§11.9 の対象ではない）
- **既存ページへの遡及適用は行わない**（新旧混在を許容する方針）。既に経歴・所属歴を書いているページは `/wikicommit-fix` か `/wikicommit-generate --regenerate --type Person` が走るまで残る。どのページが対象かは `generated_with` の `grep` と `CHANGELOG.md` の記述をセットで見て人間が決める（`docs/DesignDoc-data.md` §3.3）。`Organization.md` への同種のルール（実体が個人〜数名の組織）は、型テンプレートではなく許容性（`entity-policy.md`）の側で扱う

#### ソース文書自体をエンティティ候補にする（source entity）

ソース文書自体が独立した識別性（著者・発行日・引用可能なタイトル）を持つ「作品」である場合、それ自体を `schema:ScholarlyArticle`・`schema:Report` 等のエンティティとしてページ化する（読者にとっての発見可能性・他ページからの引用可能性のため。ソース管理ファイルの `## Summary` は公開 Wiki のページにはならない）。新しい仕組みは作らず、既存のパスの指示に載せる:

1. Pass 2a が、ソース文書自体が独立した引用可能な「作品」としての識別性（タイトル・著者・発行日・DOI/URL等）を持つかを判断する（該当例: arXiv論文・公式ベンダーブログの製品発表・公式レポート/whitepaper・ニュース記事。非該当例: 個人ブログの技術解説記事〈識別性が薄い〉、行政の事務手続きページ〈「作品」ではなく「情報」寄り〉。継続更新される living resource も除く）。該当すればソース文書自体が追加のエンティティ候補として Pass 2b/2c に流れ込む — ソース内の言及エンティティの抽出を置き換えるものではない
2. Pass 2b の型の要否判断にこの候補もそのまま乗せる。デフォルト schema に `ScholarlyArticle` 等を新規追加することはしない
3. Pass 3 は、生成された source entity ページへの自然な言及を WikiLink として本文に含めてよい。`sources:`（hash付き、監査・鮮度検証用）の役割は変えず、2つの仕組みを混在させない

- `slug`・型解決・生成順序（`existing_path` 機構）は既存ロジックをそのまま使う。Pass 4 は既存の個別事実逐一検証で照合し、論文・ニュース記事等のメタデータ専用検証（DOI解決等）は行わない
- source entity ページの本文がソース管理ファイルの `## Summary` と内容的に重複することは許容し、デデュープ機構は置かない
- **`title` は原文どおりの言語で保持する**（本文・`lang` フィールドは通常通り `<primary_lang>`）。全エンティティ共通の「`title` は原則 `<primary_lang>`」に対する狭い例外 — 引用可能性がこの仕組みの目的である以上、タイトル自体を翻訳すると実在の作品名と一致しなくなる（`.claude/skills/wikicommit-generate/references/pass2c-entities.md`）

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

#### `properties:` 値の WikiLink 化

Pass 3 は `properties:` の各キーについて、`check_schema_org_type.py --show-range`（パス 2b 実行時に既にキャッシュ済み）が返す RANGE 分類（Entity-only / DataType-only / Mixed）に基づき、値を `[[Type/slug]]` 形式で書くかプレーンな値のまま書くかを判断する（詳細な判断基準は `docs/DesignDoc-data.md` §4.1「`properties:` の値を WikiLink 化する判断基準」、実装は `.claude/skills/wikicommit-generate/references/pass3-generate.md` の「Property-value WikiLinks」）。

- **判断は RANGE 分類のみで決まり、型テンプレートによらない一律ルールである。** `.wikicommit/schema/<Type>.md` の `granularity` のプロース補強や、`properties:` のプレースホルダーが `""` ではなく `"[[Type/slug]]"` の形で書かれているかとは独立である。型テンプレート側の個別 property 名指し補強は、テンプレートの著者が人間の可読性のために書いた注記であり、ルールの適用範囲を示すものではない（補強の無い同分類の property が適用除外だと誤読されないよう、標準型テンプレートでは Entity-only/Mixed の property に補強を揃えている — `Organization.md` の `foundingLocation`・`Person.md` の `affiliation`・`Place.md` の `containedInPlace`・`Event.md` の `organizer`/`performer`・`BlogPosting.md`/`NewsArticle.md` の `publisher` 等。テンプレート間の非対称は `check_property_wikilink_reinforcement.py` が検出する）
- **ページの存在有無は WikiLink 化の理由にならない。** Pass 3 は "Do not let \"the target page doesn't exist yet\" stop you from writing the WikiLink" と明示している（参照先不在が ERROR ではなく WARNING なのは、まだ無い概念を WikiLink 化せず地の文で書く萎縮を避けるため）。**値リスト単位でも確かめる**: リスト内で WikiLink とプレーンが混在するなら、プレーン側は参照先の型の independent-subject バーを満たさないという理由でなければならない（同じ ingest で作られた人物だけがリンクされ、後の ingest で作られた人物がプレーンのまま残る、という割れ方を防ぐ）
- 既存ページ一覧を Pass 3 のコンテキストに明示的に渡すことはしない — 「存在しないページにもリンクを書け」というルールが守られていれば不要な情報であり、渡すこと自体が「存在を確認してから書く」という読み方を追認しかねない
- 一度書かれた値を見直す経路は生成側に無い（`action: update` はそのページ自身のソースが再 ingest された時にしか起きない）ので、`check_unlinked_entity_mentions.py`（`docs/DesignDoc-ScriptSpec.md`）が事後に検出し `wikicommit-status` Step 8 が報告する。修正経路は `/wikicommit-fix` である。機械的な一括置換スクリプトは用意しない — 値がページのタイトルと一致することは根拠であって証明ではなく（同名の別主体がありうる）、`properties:` への自動書き込みをヘルスチェックの責務に含めるべきでもない
- **検出スクリプトの担当**: 「ページが**無い**名前が複数作品に再登場する」（昇格候補）は `check_recurring_characters.py`（`character` に限定。作品の同一性という概念を要するため）、「ページが**在る**のにリンクされていない」はエンティティ型を range に持つ全 `properties:` キーを対象とする `check_unlinked_entity_mentions.py`。要求される行動が正反対（ページを作る／リンクにする）であることが分割の基準であり、`check_wanted_pages.py` の `WANTED`/`TYPE_MISMATCH` の分割と同じ考え方に立つ

#### テキスト抽出 Skill ルーティング

研究調査（Anthropic 公式 Skills の採用状況・MarkItDown の業界収束）に基づく推奨マッピング。

| ファイル種別 | 使用 Skill | 備考 |
|---|---|---|
| `.md` / `.txt` | 直接読み込み（Skill 不要） | — |
| `.pdf`（テキスト型） | Anthropic 公式 `pdf`（優先）、未インストール時は `markitdown[pdf]` に自動フォールバック | `pdf` は137K インストール実績・テーブル/暗号化対応。フォールバックは本節「PDF・Office 形式のフォールバック」 |
| `.pdf`（スキャン型） | `ocr-and-documents`（NousResearch） | Marker-PDF による 90 言語 OCR |
| `.docx` | Anthropic 公式 `docx`（優先）、未インストール時は `markitdown` に自動フォールバック | tracked changes・コメント対応。フォールバックは本節「PDF・Office 形式のフォールバック」 |
| `.pptx` | Anthropic 公式 `pptx`（優先）、未インストール時は `markitdown` に自動フォールバック | 内部で MarkItDown を採用済み。フォールバックは同上 |
| `.xlsx` | Anthropic 公式 `xlsx`（優先）、未インストール時は `markitdown` に自動フォールバック | openpyxl ベース。フォールバックは同上 |
| `.epub` | `ebook-extractor`（フォールバックなし） | ebooklib + BeautifulSoup。`markitdown` では等価にカバーできないためフォールバック非対応 |
| URL（Webページ・PDF等への直リンク含む） | `markitdown`（Python パッケージ。Claude Skill ではない）を `add_source.py --fetch-url` 経由でPython APIとして呼び出す（本節「URL の抽出手段」） | 指定 URL のみ取得し、本文中のリンク先への追加取得は行わない。`markitdown` はHTTPレスポンスのContent-Type（mimetype・charset）に基づき変換方式・文字コードを判定するため、URL が直接 PDF 等を指す場合も追加の `type: path` 登録なしで処理できる |
| URL（YouTube 動画） | 同上（`markitdown`）**＋ `youtube-transcript-api`**（追加の Python パッケージ） | 未導入だと `markitdown` は字幕（`### Transcript`）を例外も警告もなく落とし、タイトル・キーワード・Runtime・概要欄だけを返す。Pass 1 のガードC（`check_extraction_quality.py check-fetch-capability`）が取得前にこれを検出して処理を停止し `pip install youtube-transcript-api` を案内する。対象は `youtube.com`/`youtu.be`/`m.youtube.com`（リダイレクト後に `https://www.youtube.com/watch?…` へ着地する形式）のみで、`music.youtube.com` はリダイレクトせず変換器自体が適用されないためガードBの既知不可ドメイン扱い。`/shorts/<id>`・`/playlist`・チャンネルページも変換器が適用されないため、取得後に `### Video Metadata` の有無を確認して `status: failed` とする（Pass 1 手順6）。パッケージ導入済みで字幕が無い動画は失敗扱いにせず Completion Notice にロールアップする |
| その他 | `markitdown`（フォールバック） | 20 種類以上をカバー |

未インストールの Skill・パッケージが必要な場合は処理前にユーザーへインストールコマンドを案内して中断する。

#### `max_retries` 超過を人間の判断で許す

`max_retries` は「何度やっても直らないページを諦める」ための上限だが、リトライのたびに**毎回別の欠陥**が見つかっているのは収束していないのではなく、レビューが働いている状態である。Pass 4 手順5 は、リトライが**新しい**欠陥を出し続けている場合に限り、破棄する前に人間へもう 1 回試すか尋ねてよいと定める。条件は 2 つ: **非対話実行では自分の判断で延長しない**、**同じ形で落ち続けるページは延長しない**。同じ欠陥の繰り返しと毎回別の欠陥を自動で区別して扱いを分けること・問題箇所を落として残りを書き出す選択肢を足すことはしない（Pass 4 の複雑さに見合わない）。

#### 表形式ソース（CSV/XLSX）

取り込みと読み取り（`markitdown` が Markdown 表に変換）は他の形式と同じで、問題になるのは抽出の**対象選定**と、生成されるページの**抽象度**である。

- **(i) 独立性の判定は行数ではなく列の内容で行う。** 散文では「言及の厚み」が独立性の代理指標として機能するが、表では全行が同じ厚み（1 行）になるためこの代理指標が壊れる（「独立した事実がない組織は作らない」を「1 行 ＝ incidental」と読むと、13 施設・8 施設を受託する指定管理者まで落ちる）。行が自分自身の属性を複数持つ（所在地・規模・期間・区分等）なら独立した事実であり、名前と 1 つの対応関係しか持たない行はそうではない。**1 つの主体が複数行を占める場合はその主体自身の行をまとめて読む** — 同じ対応関係の繰り返しは 1 つの対応関係のままだが、それらの行が主体に規模・幅・広がり（何件・どの期間・どの区分）を与えるなら、それはその主体についての属性である。表全体の行数そのものは判定に関係しない
- **(ii) 記述的情報を持たない対応表からは実体ページを作らない。** 例えば施設名／施設数／指定管理者／指定期間／選定／所管課の 6 列だけの表からは「誰が・いつまで管理するか」しか書けず、それは施設についての事実ではなく契約についての事実である。関係の行き先は 2 つ: 相手側のページが既に在れば `action: update` で記録し、無ければ記録しない（表自体は `sources` と `content/sources/` の公開ページから引き続き辿れる）。一方、**表が何についての表かという概念**（制度・事業・区分）は通常は実体を持つエンティティであり、集計値はそのページに**性格づけとして**書く（件数・偏り・幅）— 行を散文化して並べるのではなく
- 「もっと多く抽出せよ」が常に正しいわけではない。抽出件数が少ないことは、素材の量ではなく**種類**から見て妥当でありうる
- **(iii) Pass 3 は表データを散文化しない**（スキーマが想定する抽象度の指示に表形式の例示を持つ）。契約データは数年で陳腐化する一方 `expires_at` は付かないので、転記はページに**追跡されない期限**を静かに持ち込む
- **1 ソースあたりのエンティティ数の上限は置かない**
- 記述的情報を持たない対応表については、表を先に取り込んで後発ソースが `action: update` で統合する、という運用は成立しない（表は実体ページを作らず、後発ソースが作ったページに `action: update` で関係を足す向きになる）。**列に実際の属性を持つ表**（施設一覧に所在地・規模・開設年が含まれるような）を先に取り込んだ場合の統合は、まだ実地で確かめていない

#### ソースコード（`.kt`/`.py`/`.ts` 等）

上表では独立した行を設けず「その他 → `markitdown`」に含める。抽出は `markitdown` で機能しており、問題になりうるのは Pass 3 がソースの詳細度（内部関数名・正規表現ロジック）をそのまま転記することである。そのため `references/pass3-generate.md` が「スキーマが想定する抽象度をソースの詳細度に関わらず遵守する」と指示する（抽出ルーティングの側では扱わない）。

#### URL の抽出手段

URL は `add_source.py --fetch-url` が、WikiCommit 独自の User-Agent を設定した `requests.Session` を `markitdown` の Python API（`MarkItDown(requests_session=...)`）に渡して取得する。詳細な手順は `.claude/skills/wikicommit-generate/references/pass1-extract.md`、フロー図は `docs/DesignDoc-pipeline.md` §6.1。

- **エージェントの Web 取得ツール（WebFetch 等）を使わない。** 「小型モデルによる要約」を返すものがあり、Pass 1 の verbatim 保存の前提と矛盾し、大きいページが要約されると hash がページ更新検知として機能しない
- **独自 User-Agent を送る。** Wikipedia・Wikisource 等の Wikimedia 系ドメインは、空 User-Agent および `python-requests` 系の既定 UA を `403 Forbidden` で拒否する。`WikiCommit/1.0` のような単純な独自 UA 文字列で足りる（ブラウザ偽装は不要）
- **`curl` 等でローカルファイルに落としてから `markitdown` で変換しない。** `markitdown` は HTTP レスポンスを直接処理する場合 Content-Type ヘッダの `charset` を文字コード判定の権威的シグナルとして使うが、ローカルファイル経由ではこの情報が失われ統計的推測にフォールバックし、`<meta charset>` を持たず HTTP ヘッダだけで文字コードを宣言する非UTF-8サイトで文字化けする（verbatim の前提を壊す）。Python API に `requests.Session` を渡す方式なら User-Agent だけが変わり、変換方式・文字コードの自動判定は `markitdown` に直接 URL を渡す場合と同じに保たれる
- 取得をスクリプトに委譲するのは、URL フェッチという決定論的操作を SKILL.md のプロース手順として再現させず、`add_source.py` の `--check-hash`/`--write-hash` と同じ場所にコードとして一度だけ実装するためである（§11.5）
- `markitdown` は JS 実行不可・ログイン必須ページ非対応である。JS 実行前提の SPA サイトでは失敗ではなく「非空だが実質無意味」なシェル（ナビゲーション・ログインプロンプトのみ）が返り、空/読み取り不能の判定をすり抜けて成功記録されうるので、`check_extraction_quality.py`（`docs/DesignDoc-ScriptSpec.md`）の既知JS-shellドメインチェック（ガードB）・低情報密度チェック（ガードA）で止める（`docs/DesignDoc-pipeline.md` §6.1）

#### 抽出品質ガードの強度

**精度の異なる 2 ガードを同じ強度で扱わない。** ガードB（`check-domain`）は確認済みドメインに対する決定論的判定なので blocking（`status: failed`）である。ガードA（`check-density`）の `LOW_DENSITY:` は**人間に続行可否を確認する警告**であり、非対話実行時は保留する（§11.5 の表）。ガードAが検出したい JS シェル（ナビリンクの羅列＋埋め込みJSON/JS状態）は、リンクの多い正当な行政サイトや数値の多い統計資料とテキスト形状のレベルでほぼ区別がつかず、閾値調整では解けない — 誤検知の代償は1ソース分の再実行だが、真の空シェルを人間確認なしに通す代償は幻覚ページである。密度の計算は空白分割に頼らない（URL 境界でのトークン化・CJK 文字の重み付け・URL のパーセントデコード — 分かち書きしない日本語の地の文とパーセントエンコードされた URL が 1 トークンに融合するのを防ぐ）。`wikicommit-collect` はガードBのみを使う。

#### PDF・Office 形式のフォールバック

`.pdf`（テキスト型）・`.docx`・`.pptx`・`.xlsx` は、対応する Anthropic 公式 Skill を優先し、Skill が未インストール・未認識でも処理を中断せず `markitdown` へ自動フォールバックする（`.pdf` は `markitdown[pdf]`。`[pdf]` extra 付き。他の 3 型は追加 extra なしの標準インストール `pip install markitdown` で等価にカバーされる）。`npx skills add` 側の上流バグ（[vercel-labs/skills#744](https://github.com/vercel-labs/skills/issues/744)、[#851](https://github.com/vercel-labs/skills/issues/851)。`~/.agents/skills/` にインストールされ `.claude/skills/` へのシンボリックリンクが作られない）で公式 Skill が事実上インストールできない場合があるためで、「未インストールの Skill・パッケージが必要な場合は処理前にユーザーへインストールコマンドを案内して中断する」という一般則の例外である（`markitdown` 自体が未インストールの場合は中断する。`.claude/skills/wikicommit-generate/references/text-extraction-routing.md`）。

`.epub`（`ebook-extractor` 固有の抽出）と画像ファイル（OCR 固有の抽出）は `markitdown` で等価にカバーできないためフォールバックを持たず、Skill が未インストール・未認識の場合は一般則どおり処理を中断してインストールコマンドを案内する。

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
返却された `summary` を管理ファイル body の `## Summary` に上書きし、`exclude_note`/`coverage_gap_note` は `## Generation Notes` に分けて書く（`## User Notes` は変更しない）。

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

SKILL.md はエージェント（Claude Code）への指示書であり、実際に Bash コマンド文字列を組み立てて実行するのはエージェント自身である（§11.0）。GitHub Issue のタイトル・本文、`wikicommit-init` の `theme` プロンプト回答のように、SKILL.md の記述者が内容を制御できない自由記述テキストを CLI 引数に埋め込む手順を SKILL.md に書く場合、そのテキストにシェルメタ文字（`` ` ``・`$(...)`・`!`・`"` 等）が含まれていると、単純な `--flag "<text>"` のダブルクォート埋め込みではコマンドインジェクションが理論上成立しうる。

**ルール**: このような自由記述テキストを CLI 引数として渡す箇所は、必ず区切り文字をクォートしたヒアドキュメント（`<<'EOF'` ... `EOF`）経由のコマンド置換 `"$(cat <<'EOF' ... EOF)"` で渡す。ヒアドキュメントの区切り文字をクォートすると、ヒアドキュメント本文はシェルによる変数展開・コマンド置換の対象外になり、テキスト中にシェルメタ文字が含まれていても安全に扱える。この形式は `gh pr create --body` 等で元々 Skills 共通の慣習として使われていたもので、本ルールはそれを他の CLI 引数（`--title`・`--theme` 等）にも一般化したものであり、単一行の値・複数行の値のどちらでも同じ書き方で機能する（副次的な利点として、値が `=`-joined の1シェル単語になるため、`-` で始まるテキストが別オプションとして誤解釈される argparse の既知の問題も同時に回避できる）。

一方、`<lang>`・`<default branch>` のように、SKILL.md 記述者ではなく上流のスクリプト・コマンド（`validate_frontmatter.py`・`gh repo view` 等）による実在検証・形式検証を経た制約付き識別子は、このルールの対象外とする（本ルールが対象とするのは検証を経ていない自由記述テキストのみ）。除外の基準は「値が何らかのスクリプト・コマンドによって決定論的に検証されているか」であり、「一見システムが生成した識別子に見えるか」ではない。

- **`<Type>`・`<slug>` は原則として除外例に含めない。** `validate_frontmatter.py` は `type` フィールドが `schema:` プレフィックスで始まることしか検証しておらずプレフィックス以降の文字列には制約がなく、`<slug>` はページのファイル名がそのまま使われるだけで文字種を強制する仕組みがパイプライン上どこにも無い（例: `wikicommit-merge` のレビュー追跡 Issue タイトル `--title "Review: <Type>/<slug> (<lang>)"` はヒアドキュメントで渡す）。例外的に除外基準を満たす `<Type>` は、`wikicommit-schema-propose` の標準型パスのように `check_schema_org_type.py --type <Type>` の実在検証を経ており、かつ検証対象の語彙（Schema.org）自体が英数字 CamelCase 識別子のみで構成されると分かっている場合に限る（同 Skill のカスタム型パスの `<Type>` は命名規約への準拠を LLM が指示に基づき確認するのみで決定論的なスクリプト検証を経ないため、除外対象にならない）
- **候補 URL も対象である。** `wikicommit-collect` が候補 URL を CLI 引数として埋め込む箇所（step 5 の `check_extraction_quality.py check-domain`、step 6 の `add_source.py --license-for-url`）はヒアドキュメントで渡す。候補 URL は Web 検索の結果、あるいは step 5.5 が第三者の参考文献リストから verbatim に取り出したものであり、上流のスクリプトが形式を検証した値ではない。**URL は一見「制約付き識別子」に見えるため、除外例と取り違えやすい** — `&` を含む URL（`…/w/index.php?title=X&oldid=1` のような普通の permalink）が引用符なしで埋め込まれると、シェルが `&` で分割して前半をバックグラウンド実行し、後半をコマンドとして実行する。`check-domain` 側では、バックグラウンド実行の終了コード 0 が `OK:` と読まれ、この Wiki が除外すると決めたドメインが候補として通る
- **検索クエリも対象である。** 呼び出し先がローカルの読み取り専用スクリプト（`.wikicommit/scripts/search_index.py query "<query>"` 等）でも除外しない — `$(...)` やバッククォートによるコマンド置換は、そのシェルコマンド行が組み立てられた時点でシェル自身によって評価されるのであって、その後どのプログラムに引数が渡されるかとは無関係である。`wikicommit-ask`・`wikicommit-search`・`wikicommit-quiz`・`wikicommit-synthesize` の検索クエリ埋め込みはヒアドキュメントで渡す

### 11.8 ユーザー向け出力から内部の手順番号・設計語彙を排除するルール

SKILL.md の手順（`### Step N`・`#### Pass N` 等の見出しや、`Route A`/`Route B` のような設計上の呼称）は、あくまでエージェント自身がその Skill をどう実行するかを記述した内部構造であり、ユーザーがそれを知っている前提は成り立たない（§11.0 のエージェントネイティブ型設計そのものが、これらをユーザーへの説明契約ではなく実行順序の記述として導入したものであるため）。確認メッセージに「proceed to Step 5」と書く、完了案内のラベルに `Route A` を出す、他 Skill の内部手順番号に言及する、といった出力は、ユーザーには何を指すか分からない。

**ルール**: ユーザーに向けた確認プロンプト・完了メッセージ（Guidance After Completion・Completion Notice・Next steps 等、ユーザーが読むことを前提にした出力全般）は、以下の3種の内部語彙をそのまま露出させず、現在の状態と次に取るべきアクションを平易な言葉で説明する。SKILL.md の記述者は、手順の内部構造を指す語彙と、ユーザーに見せる語彙を明確に分けて書くこと — 例えば「このページには追跡 Issue があり、Close したので自動マージされます」のように、`Route A`/`Route B` のラベルではなく、そのラベルが表す実際の状態を直接説明する。

| 対象語彙 | 例 | ユーザーに届かない理由 |
|---|---|---|
| 内部手順番号 | `Step N` / `Pass N`（`Pass 2b` 等の枝番を含む） | §11.6 に定義があるが、`docs/` は配布スナップショットに含まれない |
| 設計語彙 | `Route A` / `Route B` | 同上。§11.0 のエージェントネイティブ型設計では実行順序の細部はエージェントに委ねる前提であり、`Pass 2b` という区切り自体がユーザーへの契約ではない |
| **内部トラッカー参照** | `Issue #NNN` / `PR #NNN` | 参照先が private リポジトリの Issue であり、**公開後も追跡手段が存在しない**。ユーザーから見れば `Pass 2b` と同程度に意味不明で、追跡不能な分だけ悪い |

内部トラッカー参照を落とすことによる設計トレーサビリティの喪失は、経緯を `docs/` に書くことで補う（§11.9「Issue 番号も残さない」）。

**テンプレート本文とエージェント向け指示を同じフェンス内に混在させない**。ユーザーに表示するフェンス済みテンプレートの**内側**に「Do not describe this as "reviewed before merge" to the user」のようなエージェント宛の指示を書くと、テンプレート本文と、そのテンプレートをどう使うかの指示との境界が崩れる。

**例外**: 読み手が開発者・レビュアーである成果物（GitHub の PR ボディ等）はこの限りではない。例えば `wikicommit-schema-propose` の PR Description Template 内の `<path from Step 1, one per line, up to 5>` はこの例外に該当する。**`wikicommit-merge` が生成するレビュー追跡 Issue の本文は例外に該当しない** — 「Claude Code のセッションを持たない読者が GitHub 上で直接 Close するだけでレビューに参加できる」ことを狙ったものであり、読み手は開発者ではなく Wiki の読者であるため。「Issue 本文だから例外」ではなく「読み手が誰か」で判定する。

#### CI による再発検出（`tools/check_skill_user_facing_vocabulary.py`）

**本ルールは散文だけでは維持できない**（ルールの制定後も新しい違反が通る）ので、**検出時に exit 1 を返すブロッキングチェック**として置く。`.github/workflows/test.yml` に配線済み。

**走査対象は `.claude/skills/wikicommit-*/SKILL.md` のフェンス済みコードブロックのうち、info string が無いか `markdown`/`md`/`text` のもの**（＝ Skill がユーザーへそのまま出力するブロック）。`bash`/`json`/`yaml` 等はコマンド・データ形式でありユーザー向け散文ではないためスキップする。

**例外の指定方法**: フェンスの直前の行に理由付きの HTML コメントを置く。理由が空のマーカーはそれ自体がエラーになる — 例外を足すたびに、上表の判定基準（読み手は誰か）を意識的に言い直させるため。

```markdown
<!-- skill-vocabulary-exception: PR body; its reader is the developer or reviewer deciding whether to merge -->
```

現時点の適用先は2つ: `wikicommit-schema-propose` の PR ボディ（読み手が開発者・レビュアー）と、`wikicommit-generate` の再生成モードのパス構成図（**そもそもユーザーに出力されないブロック**であり、エージェント向けの説明図）。後者が示すとおり、マーカーの意味は「開発者向け成果物である」より一段広く「**このブロックはユーザー向け出力ではない**」である。

**既知の限界**: 本チェックはフェンス済みテンプレートしか見ない。エージェントが手順指示の散文中にある「Step 5」という記述を読んで**自分の言葉で**確認質問を組み立てた場合の混入は、テンプレートに存在しない文言であるため**このチェックでは検出できない**。散文指示側のガードレールは引き続き必要であり、CI はそれを置き換えるものではなく補完するものである。

#### 実行時に生成された散文は検出しない

フェンス済みテンプレートに書かれていない文言 — エージェントがその場で組み立てた散文 — に内部識別子（`.wikicommit/` で始まるパス・`exclude_living_persons` 等の設定キー名・`granularity`・`generated_with`・`primary_lang`・`/wikicommit-*`・`Pass N`・`Step N`・`properties:`・`review_status`）が混ざる失敗クラスについて、**検出する仕組みは作らない**。同じ提案が「見落とし」として再び立つのを防ぐため、理由をここに置く。

- **検出が効きすぎる。** ソフトウェア・設定・ファイルパスを主題に含む Wiki では、本文にこれらの識別子を書くのが正しい記述である（`review_status` を定義するページはその語を書くことが仕事であり、「孤立ページ」の定義は `.wikicommit/entity/` というパスを書かなければ成り立たない）。識別子は文字列としては列挙でき検出も効くが、**検出したものが欠陥かどうかを識別子の側が何も語らない** — 判定に要るのは「そのページの主題がその識別子か」であり、それは文字列からは分からない（正規表現が肯定・否定の文脈を区別できないのと同じ壁）
- **非ブロッキングに落としても解けない。** 常時点灯する所見は読まれなくなる
- **実害を出す経路は閉じている。** LLM が**自分の実行について**散文を書く箇所はパイプライン上 2 つで、**どちらも公開されない** — Pass 2c の `exclude_note` / `coverage_gap_note`（`## Generation Notes`）と、Pass 1 / 3 / 4 が書く `## Failure Reason` であり、`_write_source_page()` のホワイトリストが `## User Notes` と並べて公開対象外にしている。残る 2 経路（Pass 3 のページ本文・Pass 2a の `## Summary`）が書くのは**ソースについて**であって実行についてではなく、そこに内部識別子が現れるのはソースがそれに言及している場合 — すなわち正当な記述の場合にほぼ限られる。Pass 3 の「そのソースが何を言っていないかを本文に書かない」というルールが、実行について書くことを既に禁じている
- **生成時の指示（Pass 3 / Pass 2c への追記）も足さない。** 同じ規律の言い直しを重ねると、起動のたびに載る指示の面積だけが増える（足すなら行動の側だけ）

本ルールの適用漏れは、Skill の実装時・改訂時に完了メッセージ・確認プロンプトのテンプレート文字列を書く箇所であれば毎回チェック対象になる — 他の横断ルール（§11.7 等）と同様、新しい該当箇所を追加する際はこのルールを踏まえること。なお §11.7 は散文だけで守られており、CI による検出を持たない。

### 11.9 配布物から開発リポジトリのパスを参照しないルール

`install.sh` が配布する Skill（`.claude/skills/wikicommit-*/` の SKILL.md・`references/`・`scripts/`）と、`wikicommit-init` がユーザーの wiki リポジトリへ展開する `scripts/templates/` のペイロード（`.wikicommit/scripts/*.py`・`quartz.config.yaml`・`.github/workflows/*.yml` になる）は、いずれも本リポジトリの `docs/`・`Issues/`・`dev/` を持たないリポジトリに着地する（`Issues/` は公開リポジトリにも含まれない — 開発リポジトリ側にのみ存在する記録である）。したがってこれらのディレクトリへのパス参照は、配布先では**原理的に追跡できない**。

そうした参照は「このファイルを読め」という命令形ではなく括弧内の出典注記（設計根拠）であることが多く、参照先が無くても Skill の実行自体は失敗しない。それでも実害は 3 つある: (1) SKILL.md は Skill 起動のたびに全文がエージェントのコンテキストに読み込まれるため、追跡不能なパス文字列を毎回のコンテキストで運び続ける、(2) OSS 利用者が設計根拠を追おうとしても追えない（`Issues/`・`dev/pilot-*.md` はホワイトリスト上フェーズに関わらず配布しないため、永久に追えない）、(3) LLM エージェントが参照先を読もうとして失敗し、無関係な探索に時間を使う。

**ルール**: 配布物の中に `docs/DesignDoc-*.md`・`Issues/`・`dev/` へのパスを書かない。`docs/` プレフィックスを外した素の `DesignDoc-data.md §4.2` のような書き方も同じく不可（同じ未配布ファイルを指しており、配布先では同様に追跡できないため）。設計根拠を残したい場合は次のいずれかにする:

- **要点を1文で内在化する**。参照先の内容を知らないとエージェントが判断できない場合はこちら（結果として短くなるとは限らないが、追跡不能なパスを残すよりは良い）
- **注記ごと削除する**。指示自体が SKILL.md 内で完結しており、参照先が「なぜそうなっているか」を示すだけの場合はこれで十分（大半がこれに当たる）

相対パスを絶対 URL（`https://github.com/wikicommit/wikicommit/blob/main/docs/...`）へ書き換える案は採らない — 追跡可能性は上がるが文字数がさらに増え、(1) のコンテキスト消費に逆行するため。

逆方向（`docs/DesignDoc-*.md` から SKILL.md への参照）は開発リポジトリ内に閉じているため本ルールの対象外であり、既存の多数の参照もそのまま維持する。追跡の担い手を「配布物 → docs」の双方向から「docs → 配布物」の一方向に寄せる、という整理になる。

`tools/check_distributed_path_refs.py`（`docs/DesignDoc-TestSpec.md` L9）が CI で blocking の回帰ガードとして走り、再混入をその場で止める。

#### Issue 番号も残さない

公開リポジトリは開発リポジトリのスナップショット push であり、Issue を 1 件も持たない。利用者から見ると `Issue #NNN` のような参照は `docs/DesignDoc-*.md` と同じく辿れない参照であり、上の理由 (1)〜(3) がそのまま当てはまる。開発者は経緯を配布物からではなく `docs/` から辿る（docs → 配布物の参照は上のとおり対象外として残る）ので、**経緯が `docs/` その他の開発ドキュメントに書かれていれば、配布物からは外してよい**。

配布物の指示文（`SKILL.md`・`references/*.md`・`templates/review-rules.md`・`templates/schema-authoring.md`）の文は 3 種類に分けて扱う:

| 種類 | 例 | 扱い |
|---|---|---|
| (a) 指示 | `add_source.py --fetch-url` で取得する | 残す |
| (b) 誤った代替案を封じる理由 | curl で落としてから変換すると charset ヘッダが失われ文字化けする | **1 文に縮めて残す** |
| (c) 経緯 | 以前は WebFetch だった／ある Issue の実装中に確認した／Issue 番号 | 外す |

- **(b) を (c) と一緒に消してはならない。** エージェントは指示の外側を即興で埋めるので、「なぜ curl ではないか」が無いと curl に切り替える余地が生まれる。判定の基準は「**この文を消したら、エージェントがもっともらしい別の手を取りうるか**」である。外す段落ごとに `docs/` 側に経緯があることを確かめ、無ければ先に `docs/` へ書く（`docs/` に他の置き場が無いものは `docs/history/DesignDoc-skills.md` のこの節に集めてある）
- **スクリプトが出力する文字列も同じ扱いにする**（実行時の `BLOCKED:` / `WARNING:` / 案内文、argparse の `description` / `help`）。どちらも読み手は Issue を引けず、実行時の出力は指示文と同じくエージェントのコンテキストに載る。コメント・docstring は読み手が開発者なので対象外。`templates/guides/*.md`（人が 1 度読む手順書）も対象外とする
- `tools/check_distributed_issue_refs.py`（`docs/DesignDoc-TestSpec.md` L16）が、スクリプトの出力は 0 件を blocking で、指示文は Skill ごとの件数の上限（減らす方向にしか動かないラチェット。現在はすべて 0）で守る。経緯の文（「以前は」等）は機械的に検出できないので、ガードが見るのは番号だけである
- **`CHANGELOG.md` は本規則の対象外**（`CONTRIBUTING.md` の「Issue 番号で指してください」は変えない）。同じく公開側では辿れないが、変更の記録であって毎回コンテキストに載る指示ではなく、番号は開発リポジトリ側の読み手（版を上げる人）にとっての索引として働くため
