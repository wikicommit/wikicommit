# WikiCommit — パイプライン実装

> **対応DesignDoc**: 元 §6・§7（品質ゲート詳細は [DesignDoc-CISpec.md](DesignDoc-CISpec.md) を参照）
>
> このファイルは**いま何が仕様か**を書く。各判断の経緯（以前の挙動・採らなかった案・実測の記録・Issue 番号ごとの議論）は [history/DesignDoc-pipeline.md](history/DesignDoc-pipeline.md) の同じ見出しの下にある。

---

## 6. パイプライン実装

### 6.1 Ingest（`/wikicommit-generate`）

ソースの登録と Wiki ページ生成を一括で行う。Git 操作は行わない。

リポジトリに新規追加した生ソースファイル（例: `raw/paper-2024.pdf`）は untracked のまま残り、`wikicommit-merge`（§6.2 ステップ 2 の 3.）が未追跡分だけをコミットに含める。既に追跡済みのファイルを登録した場合は何もしない。

#### 対応ソース種別

| ソース | コマンド例 | 管理ファイル生成先 |
|---|---|---|
| リポジトリ内ファイル | `/wikicommit-generate raw/paper-2024.pdf` | `.wikicommit/source/path/raw/paper-2024.pdf.md`（元の拡張子を保持。既に同じ `source.path` を持つ管理ファイルがあればその実パスを使う） |
| リポジトリ内ファイル | `/wikicommit-generate src/auth.py` | `.wikicommit/source/path/src/auth.py.md` |
| リポジトリ内ディレクトリ | `/wikicommit-generate src/ --include "**/*.py"` | `.wikicommit/source/path/src/` 配下にファイルごとに生成 |
| 外部 URL | `/wikicommit-generate https://example.com/article` | `.wikicommit/source/url/example.com/article.md`（ホスト名ディレクトリ + パス+クエリのファイル名。既に同じ `source.url` を持つ管理ファイルがあればその実パスを使う。詳細は [DesignDoc-data.md §4.3](DesignDoc-data.md) 参照） |

#### 処理フロー

```
引数を解析してソース種別を判定
  ├─ ファイルパス → type: path
  ├─ ディレクトリパス → 配下ファイルを走査して type: path を複数生成
  └─ https:// URL → type: url
  ↓
対応する .wikicommit/source/ パスに管理ファイルが存在するか確認
  ├─ 存在しない → ハッシュを計算して新規作成（status: pending）
  └─ 存在する
      ├─ ハッシュ一致かつ status が outdated → status を pending に戻す（ソースが元に戻った。
      │                                        Pass 1 が拾って作り直す — 出自が戻っただけで
      │                                        生成をやり直していない状態を generated と呼ばない）
      ├─ ハッシュ一致 → スキップ（変更なし）
      └─ ハッシュ不一致 → hash を更新・status を pending に変更
  ↓
処理対象の管理ファイルに対してページ生成を実行（§11.6 多段生成アルゴリズム）
  ※ 対象は status が pending / outdated、および partial かつ failed_pages が非空のもの
  ※ 保留したソース（誰も答えなかった質問・ネットワーク待ち）は status を書き換えないので、この条件にそのまま残る
  ↓（管理ファイルごとに順次処理）
source.type に基づいてソースを取得
  ├─ type: path → 抽出キャッシュ（.wikicommit/.cache/extract-path/）が
  │              今のファイルの版に対して有効なら抽出せずそれを読む
  │              （.md/.txt は対象外 — 生ファイルが抽出テキストそのもの）→
  │              無効ならファイル直接読み込み
  ├─ type: url → 既知JS-shellドメインチェック（ガードB）→ 取得能力チェック（ガードC）→ OK なら独自UA付きでmarkitdown
  └─ type: wikicommit → 同上（独自UA付きmarkitdown・フェデレーション取得）
  ↓ 抽出 Skill でテキスト変換
  ↓ 失敗（空・読み取り不能・既知JS-shellドメインでブロック） → そのソースをスキップ（エラーをコンソールに出力）
  ↓ 取得が接続段階で失敗（NETWORK_UNAVAILABLE。名前解決・接続拒否・プロキシ拒否） → status を変えず保留（## Deferred Reason）。連続 2 件で処理全体を停止（環境の問題であってソースの問題ではない）
  ↓ 低情報密度チェック（ガードA）→ 低密度ならそのソースを保留（対話・非対話を問わない。続行可否はソースごとの繰り返しの後にまとめて尋ねる）
LLM への入力:
  - 抽出テキスト
  - .wikicommit/schema/ 型候補リスト
  - 管理ファイル body の ## User Notes（あれば）
  - .wikicommit/entity/ の既存ページ一覧
  - .wikicommit/config.yml の theme（空なら関連性の判定なし）
  - .wikicommit/entity-policy.md（exclude_living_persons と散文本文。
    無い・off・散文が空なら許容性の判定なし）
  ↓
LLM が分析 JSON を生成（§11.6 パス 2）。エンティティごとに action を判定:
  ├─ create      → 新規ページを作成
  ├─ update      → 既存ページに新情報を統合
  ├─ ambiguous   → スキップしコンソールに記録（型を人間が確定するまで保留）
  └─ exclude     → ページ化しないと判断。exclude_reason / exclude_note を記録（人間確認なしで自動スキップ）
      ※ theme_mismatch（関連性）と privacy（許容性）の2軸を独立に判定する
      ※ theme が空なら theme_mismatch の判定のみ行わない。entity-policy.md が
        空・未設定なら privacy の判定のみ行わない（両方なら全生成）
  ↓
分析 JSON の summary を管理ファイル body の ## Summary に書き込む（ソースの内容だけ）
  ↓
exclude したエンティティの理由と coverage_gap_note は ## Generation Notes に分けて書く
  ※ ## Summary は content/sources/ の公開ページに載る唯一の節であるため
  ↓（create / update のエンティティのみ。update の既存ソースが取得できなければそのソースを保留）
[レビューサブエージェント] 各ページをソース元文書と照合
  ├─ PASS → ローカルに書き出し
  └─ FAIL → 再生成（最大 generate.max_retries 回）
              上限超過 → そのページをスキップ。エラーをコンソールに出力
  ↓（次の管理ファイルへ）
全管理ファイルの処理完了後:
影響を受けた Type ディレクトリの index.md をローカルで更新
  ↓
各管理ファイルの status をローカルで即時更新:
  ├─ 失敗・ambiguous なし、1件以上は成功        → status: generated、generated_pages を記録
  │   （exclude が混ざっていてもよい。除外は ## Generation Notes と Completion Notice に残る）
  ├─ 一部失敗 or ambiguous あり                 → status: partial、generated_pages と failed_pages を記録
  ├─ 全エンティティが exclude（成功 0 件）      → status: excluded
  └─ 全エンティティが生成失敗                  → status: failed
```

**Pass 2c を通る入口は 3 つある**: (1) 上の収集条件（ソースの内容が変わったとき）、(2) `/wikicommit-generate <path|url>` の名指し、(3) `/wikicommit-reconcile` が管理ファイルを `status: pending` に戻すこと。ポリシー（`theme` / `entity-policy.md` / `source-policy.md`）・型テンプレート・生成ルールの変更を既存ページへ届ける経路は (3) だけである — `--regenerate` は Pass 2c を実行しない。とくに `status: excluded` のソースは (1)(2) では Pass 2c に届かない（出力はいずれも成功系）。requeue されたソースは Pass 1 の通常経路に入るので `HASH_MATCH` でフェッチを省き、実行末尾の `reconcile_ingest_status.py` は requeue を取り消さない（`docs/DesignDoc-ScriptSpec.md`）。

**`action: update` の既存ソースが取得できない場合はそのソースを保留する**。Pass 2c の末尾で `action: update` のページが持つ既存ソースの本文を揃え（`references/regenerate.md` step 1 の取得の箇条。hash 不一致は止めない）、1 件でも `ERROR:` で取れなければそのソースでは何も書かない。強制リチェック由来のソースは `status: pending` に戻す。判断の全体は `docs/DesignDoc-skills.md` §11.5。

**保留は `status` に値を足さずに表現する**。ガード A の `LOW_DENSITY:` と Pass 2b の候補は、対話・非対話を問わず `status` を書き換えず `## Deferred Reason` を書いて次のソースへ進む。ソースごとの繰り返しが終わった後、人がいれば保留分をまとめて尋ね、答えたソースだけを同じ実行の中で Pass 1〜4 にもう一度通す（`docs/DesignDoc-skills.md` §11.5「保留した質問は繰り返しの後にまとめて尋ねる」）。人がいない・答えなかった保留は上の収集条件にそのまま残る（`docs/DesignDoc-data.md` §4.3）。

**`ambiguous` は収集条件に乗せない**。`status: partial` かつ `failed_pages` が空のソースは読み直しても同じ `ambiguous: true` を返すだけであり、`ambiguous_entities` に記録して `/wikicommit-reconcile` で解除する。

##### 取得の詳細

- **URL は `add_source.py --fetch-url` が取得する**。`markitdown` の Python API に WikiCommit 独自 User-Agent の `requests.Session` を渡す。`markitdown <url>` を直接呼ばない（既定 UA を Wikimedia 系が 403 で拒否する）。curl で落としてから変換する形も採らない（HTTP ヘッダの charset が失われ、ヘッダだけで文字コードを宣言するサイトで文字化けする）。エージェントの Web 取得ツールも使わない（要約を返しうる）
- **URL ソースの鮮度**: `check_ingest_freshness.py` は `type: path` しか監視しない。URL は `/wikicommit-generate <url>` の再実行で確かめる — 処理が完結済み（`generated` / `failed` / `excluded`、および `failed_pages` が空の `partial`）なら `add_source.py` が `RECHECK` を返し、Pass 1 は必ず再フェッチしてハッシュを比べる。一致すれば何も書き換えず「変更なし」と報告し、不一致なら Pass 1〜4 を通す。`pending` / `outdated` / `failed_pages` が非空の `partial` は `SKIP`（既にキューにある）
- **抽出ガードは強度が 3 段階ある**（`check_extraction_quality.py`）:

  | ガード | 判定 | 扱い |
  |---|---|---|
  | B `check-domain` | 静的取得で空シェルを返すことが確認済みのドメイン（＋ `source-policy.md` の `exclude_domains`） | そのソースを `status: failed` |
  | C `check-fetch-capability` | 完全な取得に追加パッケージが要るホストで、それが未導入 | **処理全体を停止**して `pip install` を案内（`status: failed` にしない） |
  | A `check-density` | 抽出テキストの自然文の割合が低い（ヒューリスティック） | 保留し、繰り返しの後にまとめて続行可否を尋ねる（非対話実行では尋ねずキューに残す） |

  取得後に YouTube の抽出結果が `### Video Metadata` の形をしていなければ `status: failed`。導入済みで字幕が無い動画は Completion Notice にロールアップする
- **partial extraction（取得は成功し本文も本物だが一部が欠ける）はガードではなく登録時の通知で扱う**。GitHub の Issue / PR URL（本文は取れるがコメントが落ちる）がこれに当たり、`add_source.py` が登録時に一度だけ知らせる。ブロックしない — 本文だけで十分なソースが実在するため。**3 つのガードのどれかを調整して届かせようとしないこと**（A は欠落が自然文なら区別できず、B は空シェルの定義に反し、C はパッケージを入れれば完全に取れることを前提にしている）。新しい例が出たら、その欠落が取得前に URL の形だけから決定論的に分かるかを確かめ、分かるなら通知に 1 行足す。`gh` 経由の取得経路は作らない（認証・hash の意味・覆る議論という未解決の論点を持つ）
- **抽出テキストのキャッシュは木が 2 つある**:

  | | 木 | 相対パスの基準 | 末尾の `.md` |
  |---|---|---|---|
  | `type: url` / `wikicommit` | `.wikicommit/.cache/ingest-fetch/` | `.wikicommit/source/url/` | 落として付け直す |
  | `type: path` | `.wikicommit/.cache/extract-path/` | `.wikicommit/source/path/` | **そのまま残す**（`paper.pdf` と `paper.docx` を別キャッシュにするため） |

  統合しない（衝突しうる・URL キャッシュの一斉失効に見合わない）。`type: path` の `source.hash` は**生ファイル**のハッシュなので、有効性は生ファイル側で判定し（`add_source.py --check-path-cache`。read-only）、**キャッシュを `--write-hash` に渡してはならない**。`.md` / `.txt` はキャッシュしない。**生で読むか抽出するか（とどの抽出 Skill か）は `source.path` のシンボリックリンクを辿った解決先の拡張子で決め、その判定はエージェントではなくスクリプトが行う** — `--check-path-cache` が `.md` / `.txt` なら `RAW: <解決先>`、それ以外で無効なら `CACHE_STALE: <キャッシュ> extract=<解決先>` を印字し、review / fix の `resolve_source_cache_path.py --obtain` も同じ集合・同じ解決先で `READ:` / `EXTRACT:` を分ける（リンク名で判定すると、PDF を指す `.md` 名のリンクで生成は PDF のバイトを読み照合は抽出テキストを読む — 別のテキストになる）。キャッシュの位置はリンク名でも解決先でもなく管理ファイルから決まるので、generate が書いた抽出結果に review / fix が当たる。読み手は `resolve_source_cache_path.py --type path` に一本化する。抽出ツールの版が変わってもキャッシュは失効せず、`.gitignore` 配下なのでマシンごとである

#### 再生成モード（`--regenerate`）

手順の置き場は `.claude/skills/wikicommit-generate/references/regenerate.md` であり、`SKILL.md` には分岐とそのファイルを読む指示だけがある。ファイルが読めない場合は停止して報告する。Skill は割らない（Pass 1 / 3 / 4 を通常生成と共有するため）。本節はそのファイルの内容の正本である。

既に生成済みの Wiki ページを、現在のスキーマテンプレート・生成ルールで作り直すモード。通常フローはソース起点で `generated` を `SKIP` するため、「ソースは変わっていないが生成ルールが変わった」はこのモードでしか表現できない。

```
/wikicommit-generate --regenerate <page-path>     # 単一ページ
/wikicommit-generate --regenerate --type <Type>   # 型単位（全言語）
/wikicommit-generate --regenerate --all           # 全対象ページ（5件超なら確認）
/wikicommit-generate --regenerate <page-path> --merge <page-path> [...]   # 「同一」のページの統合
```

**統合（`--merge`）**: `/wikicommit-relate` で「同一」と記録したページを 1 ページに畳む。残すページを全ページのソースで作り直し（Pass 4 は和集合の全ソースに照合する）、PASS して書き出した後にだけエンジンの `merge-absorb` 工程（`references/merge.md`）が統合の記録・吸収したページの取り下げ・リンクの書き換えを行う。設計は `docs/DesignDoc-data.md` §4.5.2 の「統合」の節、スクリプトは `docs/DesignDoc-ScriptSpec.md` の `merge_pages.py` / `rewrite_merged_links.py`。

```
対象ページを選別（下記「対象外」に該当するものを除外し、除外理由を都度報告）
  ↓ 5件超過 → 全件処理 / 先頭5件のみ をユーザーに確認（generate/collect/translate と同じ閾値）
ページの sources: を再取得（Pass 1 の抽出ルールをそのまま使う）
  ├─ status: retracted のソース → 取得しない。落として残りで作り直し、
  │                                ページの sources: からもそのエントリを外す
  ├─ type: url/wikicommit → キャッシュ（.wikicommit/.cache/ingest-fetch/）の SHA-256 が
  │                          ページ記録の hash と一致すれば再フェッチしない
  │                          （管理ファイルは source.url の実走査で特定する。
  │                            add_source.py --check-hash は管理ファイル側の
  │                            現在の hash と比較するため、この用途には使わない）
  ├─ type: path → 抽出キャッシュ（.wikicommit/.cache/extract-path/）が有効なら
  │              抽出をやり直さない
  └─ 再取得結果の hash がページ記録の hash と食い違う
        → そのページは再生成しない。既存の outdated フロー（/wikicommit-generate <path|url>）へ誘導
  ↓
Pass 3（生成）— action: update・existing_path = そのページ自身として実行
  ↓
Pass 4（レビュー）— 変更なし。max_retries 超過なら既存ページをそのまま残す
  ↓
rebuild_index.py（title が変わりうるため）
```

**Pass 2・Pass 2b は実行しない**。対象ページの frontmatter が `type`/`title`/slug/`lang` をすべて持っており、抽出すべきエンティティが確定しているため。ページ起点にするのは、ソース起点の再処理だと 1 つのソースが生成した無関係な型のページまで巻き込むためである（ページは `sources:` に出自を全件持つので、複数ソースからマージされたページもページ単位で作り直せる）。

**再生成後は `review_status: pending` に戻し、`reviewed_by` を出力に含めない**（§6.3「内容が書き換わったページ」と同じ原則）。`pending` に戻ったページは次の `/wikicommit-merge` の全ページ走査が拾って追跡 Issue を作る（スキップ判定は open な Issue のみを見る）。**安全弁**: 再生成結果が既存ページと 5 フィールド（`review_status`/`reviewed_by`/`generated_at`/`generated_by`/`generated_with`）を除いてバイト一致する場合のみ `review_status` と `reviewed_by` を維持する。`reviewed_by` も比較から除外しないと、それを持つページで弁が決して発火しない。判定はテキスト一致であって意味的同一性ではない（非決定的な判定に人間のレビューの要否を委ねない）。

**対象外**（該当ページはスキップし、理由を都度報告する）:

| 対象外 | 理由 |
|---|---|
| `index.md`・`status: removed` のページ | 生成物ではない / 公開対象外 |
| `translated_from` を持つページ（翻訳） | `/wikicommit-translate` の所管。原文ページを再生成すれば `check_translation_status.py` が `STALE` として検出する |
| `derived_from` を持つページ（合成） | 同上（`/wikicommit-synthesize`・`check_derivation_freshness.py`） |
| `sources` が無い / `sources[].type: manual` を 1 件でも含むページ | 再取得できるソースが存在しない。残りだけで作り直すと manual 由来の記述が黙って消える |
| `sources` の**全件**が `status: retracted` のページ | 作り直す材料が残らない。`/wikicommit-remove` へ誘導する。**1 件でも残るページはスキップしない** |

**取り下げたソース（`status: retracted`）は落として作り直し、ページの `sources[]` からもエントリを外す**。変更された・再取得できないソースとは扱いが逆である — そちらは内容がまだ必要なのに手に入らないのでページごとスキップし、取り下げはその内容が要らないと判断されたものなので落とす。`sources[]` に残すと、ページが使っていない裏付けを主張し、Pass 4 がその文書に照合し続け、`check_retracted_sources.py` が報告し続ける。取り下げの記録は管理ファイル・`## Retraction Reason`・`git log` に残る。エントリを落とせば unchanged-output valve は発火しえず、ページは必ず `pending` に戻る。対象ページの一覧は `check_retracted_sources.py`（`wikicommit-status` Step 12）が出すので、専用の選択子（`--retracted` 等）は作らない。

**ソース管理ファイルへの書き戻しは一切行わない**。`generated_pages` は変わらず、`last_generated_at` もこの操作が記録すべき値ではない。Pass 1・Pass 4 は取得と生成の部分だけを流用し、Pass 1 の `--write-hash`・`extracted_tokens`・`status: failed`／`## Failure Reason`、Pass 4 手順5（`failed_pages`）・手順7（`status` 更新）は実行しない。とくに `--write-hash` を実行すると `status` は `generated` のまま hash だけが進み、折り込みを拒否したソース変更が以後 `HASH_MATCH` で見えなくなる。ガードに引っかかった・再取得できないソースは、管理ファイルを `failed` にせず**そのページごとスキップして報告する**（残りだけで作り直すと、そのソース由来の記述が黙って消える）。

**「どのページが古いか」の機械的検出は行わない**。対象はページ frontmatter の `generated_with` を `grep` した結果と `CHANGELOG.md` の記述を見て人間が決める（版の粒度は型より粗いので、この 2 つはセットで使う）。

**`granularity` 変更に伴うページの分割・統合、および既存ページの型再分類は対象外**。前者は「どのページが存在すべきか」自体が変わる操作であり、後者は「型自体が誤っている」ページが対象で問題が異なる（[DesignDoc-phases.md](DesignDoc-phases.md) に着手フェーズ未確定として記録）。

### 6.2 Merge（`/wikicommit-merge`）

ブランチは `wikicommit/merge-<YYYYMMDD>-<HHMMSS>` 形式とする（`issue-NNN` 規約は Issue 駆動の開発ブランチ向けであり、自動生成の一時ブランチには適用しない）。

#### 処理フロー

```
.wikicommit/ 配下の未コミット変更（Wiki ページ・管理ファイル・index.md）を検出
  ↓ 変更なし → 「マージ対象がありません」と表示して終了
品質チェックを実行（順次）:
  # 変数定義（以下のコマンド呼び出しで使用）
  # <変更 .md ファイル>    = git diff --name-only -- '.wikicommit/entity/**/*.md' で取得した変更ファイルのパス一覧
  # <削除対象ファイル>     = 上記のうち、git show HEAD:<path> で旧 frontmatter を確認して旧 status が removed でなく
  #                          現 status が removed であるファイルのパス一覧（削除フロー判定。存在しない場合は --deleted を省略）
  # <新規ソースファイル>   = 変更された .wikicommit/source/**/*.md（削除された管理ファイルは除く）の
  #                          source.path（source.type: path のみ）のうち、git status --porcelain で
  #                          `??`（untracked）と判定されたパスの一覧（既に追跡済みの既存ファイルや、
  #                          追跡済みだが未コミットの変更があるファイルは含めない）。
  #                          `.gitignore` 除外・非 ASCII パス・glob メタ文字を含むパスのいずれでも
  #                          誤判定しない（具体的な git コマンドは SKILL.md ステップ 2 の 3. 参照）
  python .wikicommit/scripts/validate_frontmatter.py <変更 .md ファイル>
  python .wikicommit/scripts/check_wikilinks.py --changed <変更 .md ファイル> [--deleted <削除対象ファイル>]
  lychee --config .lychee.toml                        # 外部リンク検証（sources URL・本文 https://）
  markdownlint-cli2 <変更 .md ファイル>               # スタイル検証（warning のみ）
  python .wikicommit/scripts/check_orphans.py         # 孤立ページ・重複ページ検出
  ↓ blocking エラーあり → エラー内容を表示して中断（対話・非対話を問わない）
  ↓ warning のみ → 内容を表示してユーザーに続行確認
  ↓              （非対話実行では確認せず、warning を記録して続行する）
ブランチ作成（wikicommit/merge-<YYYYMMDD>-<HHMMSS>）
  ↓
変更ファイルと <新規ソースファイル> をコミット
  ↓
PR 作成（本文に warning の件数と先頭数件を書く） → `mergeStateStatus` が `CLEAN` になるまで `gh pr view --json state,mergeStateStatus` でポーリング（最大 300 秒・10 秒間隔。lychee の外部リンク検証に数分かかるため） → `--auto` なしで `gh pr merge --squash`
  ↓ `state: CLOSED` または `mergeStateStatus` が `DIRTY`/`BLOCKED`（待っても解消しない終端状態） → 即座にポーリングを打ち切りエラー表示して中断
  ↓ 上記以外でタイムアウト → エラーを表示して中断（マージしていない以上、次のレビュー追跡 Issue 作成へは進まない）
                   残存ブランチ・PR のクリーンアップ手順: `gh pr close <PR番号>` → `git push origin --delete <ブランチ名>` → /wikicommit-merge を再実行
  ↓（PR マージ確認後）
レビュー追跡 Issue を Wiki ページ単位で作成（review_status: pending のページのみ）:
  - 対象: `.wikicommit/entity/` 配下の全ページを main 上で走査し（今回のバッチに限らない — 作成に失敗したページや
    別経路で pending になったページを次回以降に必ず拾うため）、review_status が pending のページ
    （index.md と status: removed のページは対象外。経路 B は reviewed 設定済みのため対象外）
  - 1回の実行で対象ページ全件について Issue を生成する（上限は設けない。ページごとの作成の間に 2 秒の sleep を挟む）
  - Issue のラベル: `wikicommit-review`
  - Issue 本文に機械可読マーカー `<!-- wikicommit-page: .wikicommit/entity/<lang>/<Type>/<slug>.md -->` を埋め込む
    （重複作成防止・後続の自動処理の両方がこれを頼りにページを特定する）
  ※ 既に同じページを指す open な `wikicommit-review` ラベル Issue があるページはスキップ。open な Issue は
    `gh api "repos/{owner}/{repo}/issues?labels=wikicommit-review&state=open&per_page=100" --paginate` で全件取得し、
    `body` をマーカーで照合する。`gh issue list --search`（検索インデックスが HTML コメントを扱う保証が無い）と
    `gh issue list --label … --limit 1000`（検索 API を通り 1000 件で警告なく止まる）は使わない。
    Step 9 と `wikicommit-review` Step 5 も同じ取得方法を使う
  ↓
生成失敗トラッキング Issue をソース管理ファイル単位で作成（`failed_pages` が空でない管理ファイル、および status: failed）
  - レビュー追跡 Issue と同じ全件走査・マーカー埋め込みパターン。ラベルは `wikicommit-generation-failure`
  - Close しても自動書き換えは走らない可視化専用の Issue — 再試行するには `/wikicommit-generate` を再実行する
  ※ 理由欄はレビュー記録から取る: `check_review_coverage.py --discarded-reason <failed_pages...>` が
    `result: discarded` の最新記録から `type` / `source_lines` / `instruction` を返す（`source_file` は印字しない）。
    `## Failure Reason` がある場合（status: failed）はそちらを、どちらも無い場合は「記録されていない」と書く
    （`unknown` とは書かない）。Pass 4 は `partial` 分岐で `## Failure Reason` を削除するため、管理ファイルだけでは足りない
  ※ 「gap を許容する」出口は `## User Notes` で実現する: ① `## User Notes` にページ化しない旨と理由を書く →
    ② `status: failed` なら先に `pending` へ書き戻し、`/wikicommit-generate <このソース>` を名指しで実行する →
    ③ `failed_pages` が空になったことを確認する → ④ `/wikicommit-merge` のあと Close する。
    重複判定は open な Issue しか見ないので、`failed_pages` が非空のまま Close すると次の実行が立て直す。
    名指しの 1 回で同じソースの成功済みページも action: update で書き直され、内容が変われば pending に戻る
  ※ 上の出口は `failed_pages` が非空の Issue 用である。`failed_pages` が空（Pass 1 で失敗した status: failed）の Issue は
    本文の手順を分け、エンティティ前提の手順を出さない: (a) 一時的な失敗なら `status` を `pending` に戻して名指しで再実行（`generated_pages` を持つ再チェック失敗なら `pending` にせず名指しの再チェックだけを行い、変更なしなら `generated` に戻して `## Failure Reason` を消す — `pending` はキャッシュから全ページを作り直す）、
    (b) 取得できない URL ソース（403 等）なら管理ファイルを削除し（`generated_pages` を持つ再チェック失敗なら削除せず `generated` に戻し `## Failure Reason` を消す）、
    `source-policy.md` の `rejected:` に URL・理由・日付を足し（同じサイトの別文書も拒まれるなら `exclude_domains:`）、
    merge のあと Close する（`type: path` は登録時に `source.hash` が更新済みで URL も無いため対象外 — ファイルを直して (a) か、ファイルと管理ファイルを削除する）。`status: retracted` は勧めない（「取得は完全だが内容が信用できない」を意味し、公開ページに取り下げと出る）
  ↓（GitHub Actions により自動実行）
main マージをトリガーに `.github/workflows/deploy.yml` が起動し、Quartz v5 ビルド → GitHub Pages 公開（§8 参照）
```

**工程の順序はエンジンが持つ**（`.claude/skills/wikicommit-merge/workflow.yaml`。仕組みは `docs/DesignDoc-skills.md` §11.0）。上の流れのうち、版ずれの確認・デフォルトブランチの解決・変更の検出・開いた実行の検出はエンジンが自分で実行する `script` 工程、品質チェック・コミット・PR 作成・マージ待ち・2 種類の Issue 作成・完了報告はエージェントが手順ファイル（`references/`）を読んで行う `agent` 工程、warning の続行確認は `human` 工程である。コミット・PR・マージの各工程は、ディスク（ブランチ・未コミットの残り）・remote（ブランチの push）・GitHub（PR が `MERGED`）を見る確認が通るまで完了にならない。デフォルトブランチ・warning・PR 番号は実行記録に置くので、途中で止まった merge は `skill_workflow.py next` で同じ工程から再開でき、再開した工程は同じ PR を見る。

**非対話実行は warning で止まらない — 記録して続行する**。warning は §7 の分類で例外なく「常にマージ可」であり、Step 3 の確認が担うのは人に見せることだけである。無人実行では作業ツリー自体が永続しないので、中断すると `generate` の出力が失われる。PR 本文にはツールごとの件数＋先頭 3〜5 件＋`(+N more)` を書き（全件逐語にしない）、本文は対話実行でも同一にする。**blocking（`ERROR:` / `DUPLICATE:`）は対話・非対話を問わず中断する**（ブランチを作る前に止まるので作業ツリーは残る）。

**`gh pr merge --auto` に依存しない**。auto-merge は `allow_auto_merge` 設定に依存し、GitHub Free の private リポジトリでは有効化できない。品質チェックは PR 作成前にローカルで済んでいるので、待つのは `mergeStateStatus` の計算だけである。`review-issue-close-sync.yml` の "Auto-merge on quality pass" ステップも同じ。

#### レビュー追跡 Issue 本文テンプレート

対象ページの frontmatter がどの出自フィールドを持つかでテンプレートを 3 分岐する: `translated_from`（翻訳ページ）、`derived_from`（合成ページ）、どちらも無し（`sources` ベースページ）。3 フィールドはページごとに排他（§4.2）なので常に 1 つが適用される。翻訳ページは `generated_at`/`generated_by` の代わりに `translated_at`/`translated_by` を持つ。「操作方法」・ラベル・マーカー形式は 3 バリアントで共通であり、`review-issue-close-sync.yml` はページの出自に依存しない。

**本文は `primary_lang` で描画する**。SKILL.md 上のテンプレートは英語だが、Step 8 が `config.yml` の `translation.primary_lang` で描画する（`en`・値なし・読めない場合は英語のまま）。ページの `lang` ではなく `primary_lang` を使う — 読むのは Close 権限を持つ運用者であり、それはリポジトリの性質だからである（`targets` を持つ Wiki で 1 人の運用者に 2 言語の Issue が届かないように）。**翻訳しないもの**: マーカー行（`review-issue-close-sync.yml` が完全一致で照合する）・Issue タイトル・実際に打つ／目で追う文字列（コマンド名・パス・frontmatter のキーと値・ラベル）・フィールドの値そのもの（literal な `unknown` を含む）。共通の「操作方法」も翻訳する。

**この結論を `/wikicommit-fix` Step 7 の完了コメントへ読み替えてはならない** — あちらの読み手はページを読んだ外部の報告者なので、対象ページの `lang` で描画する。`.github/ISSUE_TEMPLATE/report.md` はリポジトリに 1 つしかないので英語のまま。

##### 共通の「操作方法」セクション（全バリアント共通）

以下を「## 読んだら」とマーカー行の間に、全バリアントでそのまま挿入する:

```markdown
## 操作方法

この Issue を Close するには、このリポジトリへの書き込み権限（Organization 所有のリポジトリでは triage 権限）が必要です。自分が立てていない Issue を Close できるのはリポジトリのオーナー・コラボレーター・triage 権限以上を持つ人に限られ、それ以外の閲覧者には Close ボタン自体が表示されません。権限を持たずにこのページの誤りを指摘したい場合は、代わりにご自身で新しい Issue を立ててください。自分のアカウントで立てるだけなので権限は不要で、その内容は `/wikicommit-fix` が読み取ります。公開済みの Wiki であれば、ページ上部のバナーにある報告リンクが、対象ページを埋めた状態でこれを行います（このリンクの文言はページの言語に従うため、日本語ページでは「気づいた点を報告する」と表示されます）。
ページ本文を読んで問題なければ、この Issue を Close するだけで構いません。`.github/workflows/review-issue-close-sync.yml`（Issue #313）が Close を検知して `review_status` を `reviewed` に書き換え、品質チェック通過後に自動マージします。Approve というPR操作は不要で、GitHub の Web/モバイル UI から Close するだけで完結します。
修正が必要な場合は、指摘をコメントに書いてこの Issue を開けたままにしてください。**修正はあなたが行う必要はありません**（`/wikicommit-fix <このIssueのURL>` が本文とコメントを読み取ります）。修正が反映された後で Close します。
**受け取ったこと・気づいたことをコメントに書くのは、この Issue の目的そのものです** — それ以上何もする必要はありません。
**ただし「直してほしい」というコメントは、それだけでは直りません** — Close 時に自動実行される処理はこの Issue 本文末尾のマーカー行のみを読み、コメントの中身は一切参照しないため、修正依頼を書いただけで Close するとその修正は行われないままマージされます。実際に反映させるには `/wikicommit-fix <このIssueのURL>` を明示的に実行してください（Issue の本文とコメントの両方を読み取って修正案を提示します）。修正が反映されてからこの Issue を Close してください。
**2 種類のコメントだけは例外です。どちらもページ本文ではなくソースについての話であり、`/wikicommit-fix` はソースに一切触れられないためです。**
**ページが本来書かれるべきだった文書の URL** — `/wikicommit-generate <url>` を実行し、続けて `/wikicommit-merge` を実行してください（その文書の内容は、それを元に書かれたページへ統合され、そのページが再び読まれるのを待つ状態に戻ります。この Issue が翻訳ページ・合成ページを追跡している場合、それはこのページではなく出自元のページです）。それらを実行できない場合でも、コメントに URL を残せば実行できる人に渡ります — ただし登録が済むまでこの Issue は Close しないでください。Close するとこのページはそのまま `reviewed` として確定します。
**ソース自体が誤っているという指摘** — こちらがもう 1 つです。この判断に到達できる自動チェックは 1 つもありません。この Wiki の検査はすべてソースを「ページを測る基準」として扱うため、**ソースの誤りを忠実に写したページは全部の検査を通ります**。どのソースの何が誤っているかをコメントに書いてください。書き込み権限を持つ人がその管理ファイルに `status: retracted` と理由を書き、`/wikicommit-status` がそのソースに立っている全ページを列挙します。挙げるのはこのページ自身が書かれた元の文書だけにしてください — この Issue が翻訳ページ・合成ページを追跡している場合、このページは自分のソースを持たず、その文書は出自元のページに属するため、指摘先はそちらになります。反映されるまでこの Issue は Close しないでください（理由は上と同じです）。
```

##### `sources` ベースページ（`translated_from` も `derived_from` も無し）

```markdown
## レビュー対象

- ページ: `.wikicommit/entity/<lang>/<Type>/<slug>.md`
- 生成日: <generated_at>
- 生成モデル: <generated_by>

## 読んだら

読んだら、**このページから何を受け取ったか**を一言だけコメントに書いて Close してください（Close 時のコメント欄にそのまま書けます）。要約でなくて構いません。「ここが意外だった」「既に知っていることばかりだった」でも十分です。

**これは理解度のテストではありません。** このページの知識が実際に人に渡ったことの記録です。Close が述べるのは 2 つです — このページの知識が人に渡ったこと、そして**読んでいて明らかに変だと思う点は無かった**こと。内容が正しいことの保証ではありません。

このページは生成時に、書き起こしの元になった資料と機械が照合済みです（公開ページ上部に表示されている場合は、そこにモデルと日付が出ます）。以下はどの自動チェックも見ていないので、読んでいて気づいたことがあれば同じコメントに書いてください。**探しに行く必要はありません。**

- 実在の人物・組織について、書きすぎ・断定しすぎに感じた箇所、係争中の主張が確定事実として書かれている箇所、記録する理由の無い私的な事柄。このページを作るかどうかは生成時に `.wikicommit/entity-policy.md` に照らして判断済みだが、**その中の記述は誰も見ていない**
- あなたが知っていることと食い違う箇所、またはどのソースも扱っていない重要な事実。**URL がある場合はコメントに URL を書いてください** — コメントの他の内容と違い、URL だけは先へ渡ります（下記「操作方法」参照）。`/wikicommit-generate <url>` で登録するとこのページに統合され、統合後は再び読まれるのを待つ状態に戻ります。書き込み権限があればご自身で実行してください。無い場合はコメントに残せば、実行できる人がそこから拾えます
- 他のページと言っていることが違うと感じた点。機械は同じバッチで先に作られたページとしか照合できないため、時間をおいて複数ページを読む人にしか見つかりません
- **ページではなく、ページが書かれた元のソース自体がおかしいと思った点**。これは別の話であり、「ページは問題ない」ではカバーされません — 自動チェックはすべてページを**ソースに照らして**測るため、ソースの誤りを忠実に写したページは全部の検査を通ります。このページが `sources:` に挙げている文書のどれかが信用できないと分かっている場合、どれのどこがそうかを書いてください（この指摘はコメントのままでも先へ渡ります。下記「操作方法」参照）
- `<Type>` がこの主題にとって妥当な型か。また `.wikicommit/schema/<Type>.md` の `properties:` に並ぶキーがこの型に合っているか。この型はこのページの執筆中に自動で追加されたもので、Schema.org 語彙に実在することは機械的に検証済みだが、この主題に**ふさわしいか**を見た自動チェックは無い <!-- 実装向けの注記であり、条件の成否に関わらずこの HTML コメント自体は Issue 本文へ出さない。この行を含めるのは Pass 2b（Issue #315）が追加した型のページのみで、判定は `.wikicommit/schema/<Type>.md` の `wikicommit.provenance` が `generate-interactive` / `generate-auto` かどうかで行う（Issue #729）。条件を満たさない場合は行ごと落とす -->

**引っかかる点があった場合は、コメントに書くだけで構いません。その場合はこの Issue を Close しないでください** — 修正はあなたが行う必要はなく、修正が反映された後で権限を持つ人が Close します。

公開済みの Wiki であれば、ページ上の報告リンクが同じ種類のことを、気づいた読者なら誰からでも受け取ります。この Issue はその一段上にあり、Close はこの Wiki が「このページは人が読んだ」と記録する操作です（だから書き込み権限が要ります）。


<上記の共通「操作方法」セクションをそのまま挿入>

<!-- wikicommit-page: .wikicommit/entity/<lang>/<Type>/<slug>.md -->
```

##### 翻訳ページ（`translated_from` あり）

```markdown
## レビュー対象

- ページ: `.wikicommit/entity/<lang>/<Type>/<slug>.md`
- 翻訳元: `<translated_from>`（原文ページ。このIssueは翻訳ページ自身の `review_status` のみを追跡する — 原文ページはすでに `reviewed` 済みの場合も、経路Aを一度も経由せず自身のIssueを持たない場合もあり、常に別Issueが存在するとは限らない）
- 翻訳日: <translated_at>
- 翻訳モデル: <translated_by>

## 読んだら

読んだら、**このページから何を受け取ったか**を一言だけコメントに書いて Close してください（Close 時のコメント欄にそのまま書けます）。要約でなくて構いません。「ここが意外だった」「既に知っていることばかりだった」でも十分です。

**これは理解度のテストではありません。** このページの知識が実際に人に渡ったことの記録です。Close が述べるのは 2 つです — このページの知識が人に渡ったこと、そして**読んでいて明らかに変だと思う点は無かった**こと。内容が正しいことの保証ではありません。

このページは生成時に、原文ページに対する翻訳品質チェックを通っています。以下はどの自動チェックも見ていないので、読んでいて気づいたことがあれば同じコメントに書いてください。**探しに行く必要はありません。**

- 原文の意味を運べていない箇所、不自然な直訳、`DefinedTerm/` の用語集と訳語が食い違う箇所
- 実在の人物・組織について、書きすぎ・断定しすぎに感じた箇所、係争中の主張が確定事実として書かれている箇所、記録する理由の無い私的な事柄。このページを作るかどうかは生成時に `.wikicommit/entity-policy.md` に照らして判断済みだが、**その中の記述は誰も見ていない**

事実そのものが古い・誤っている場合、直すべきは翻訳元の原文ページであってこのページではありません（このページへの修正は、次に原文が変わって再翻訳が走った時点で上書きされます）。ソースについても同じで、このページは自分のソースを持たず、その背後にある文書の問題は原文ページのソースに属します。

**引っかかる点があった場合は、コメントに書くだけで構いません。その場合はこの Issue を Close しないでください** — 修正はあなたが行う必要はなく、修正が反映された後で権限を持つ人が Close します。

公開済みの Wiki であれば、ページ上の報告リンクが同じ種類のことを、気づいた読者なら誰からでも受け取ります。この Issue はその一段上にあり、Close はこの Wiki が「このページは人が読んだ」と記録する操作です（だから書き込み権限が要ります）。


<上記の共通「操作方法」セクションをそのまま挿入>

<!-- wikicommit-page: .wikicommit/entity/<lang>/<Type>/<slug>.md -->
```

##### 合成ページ（`derived_from` あり）

```markdown
## レビュー対象

- ページ: `.wikicommit/entity/<lang>/<Type>/<slug>.md`
- 合成元: `<derived_from[0].path>`, `<derived_from[1].path>`, ...（`derived_from` の各要素を列挙）
- 生成日: <generated_at>
- 生成モデル: <generated_by>

## 読んだら

読んだら、**このページから何を受け取ったか**を一言だけコメントに書いて Close してください（Close 時のコメント欄にそのまま書けます）。要約でなくて構いません。「ここが意外だった」「既に知っていることばかりだった」でも十分です。

**これは理解度のテストではありません。** このページの知識が実際に人に渡ったことの記録です。Close が述べるのは 2 つです — このページの知識が人に渡ったこと、そして**読んでいて明らかに変だと思う点は無かった**こと。内容が正しいことの保証ではありません。

このページの主張は 1 件ずつ、「合成元」に列挙されたページと機械が照合済みです。以下はどの自動チェックも見ていないので、読んでいて気づいたことがあれば同じコメントに書いてください。**探しに行く必要はありません。**

- 実在の人物・組織について、書きすぎ・断定しすぎに感じた箇所、係争中の主張が確定事実として書かれている箇所、記録する理由の無い私的な事柄。このページを作るかどうかは生成時に `.wikicommit/entity-policy.md` に照らして判断済みだが、**その中の記述は誰も見ていない**

このバリアントでは上の項目が最も効きます。このページに対する自動チェックはすべて、主張を 1 件ずつ「合成元」のページと突き合わせるものであり、**複数の記述を並べたことで初めて生じる含意**はどの層も見ていません — そして記述を並べることこそ、このページがやっていることです。

組み合わせ方ではなく事実そのものが誤っている場合、直すべきはそれを述べている「合成元」のページです。ソースについても同じで、このページは自分のソースを持たず、その背後にある文書の問題は、それを元に書かれた「合成元」のページに属します。

**引っかかる点があった場合は、コメントに書くだけで構いません。その場合はこの Issue を Close しないでください** — 修正はあなたが行う必要はなく、修正が反映された後で権限を持つ人が Close します。

公開済みの Wiki であれば、ページ上の報告リンクが同じ種類のことを、気づいた読者なら誰からでも受け取ります。この Issue はその一段上にあり、Close はこの Wiki が「このページは人が読んだ」と記録する操作です（だから書き込み権限が要ります）。


<上記の共通「操作方法」セクションをそのまま挿入>

<!-- wikicommit-page: .wikicommit/entity/<lang>/<Type>/<slug>.md -->
```

**各テンプレートの要件**（文面を変えるときに保つもの。経緯は history の同じ見出し）:

- **Close には権限が要ることを書き、権限が無い読者には「自分で新しい Issue を立てる」を代替経路として示す**。報告リンクは近道として併記するに留める（`--quartz` なしの Wiki にはバナーが無い）。ラベル文字列は引用せず機能で説明する（ラベルはページの言語に従う）。参加募集の文言にはしない
- **チェックボックスを置かない**。主たる問いは「このページから何を受け取ったか」の一言であり、「これは理解度のテストではありません」を必ず書く。Close が述べるのは 2 つ（知識が人に渡ったこと・読んでいて明らかに変だと思う点は無かったこと）であり、**「探しに行く必要はありません」を消さない**（消すと負の証明に戻る）
- **気づきの箇条書きは機械が見ていないものに限る**: 害（全バリアント）、レビュアー固有の知識との食い違い・バッチをまたぐページ間矛盾・ソース自体の妥当性（`sources` バリアントのみ — 翻訳・合成では問題の文書が出自元のページに属するため）。前置きで機械側の照合が済んでいることを述べる。報告リンクと文面を同一にしない（宛先が違う）
- **URL とソースの誤りの 2 つだけはコメントが先へ渡る例外である**（`/wikicommit-fix` はソースに触れられない）。「操作方法」は統合先を「それを元に書かれたページ」と書く（翻訳・合成では出自元）。どちらにも「反映されるまで Close しない」を必ず添える
- **型選択の行は、`.wikicommit/schema/<Type>.md` の `wikicommit.provenance` が `generate-interactive` / `generate-auto` の型のページにだけ含める**（このバッチで追加されたか、ではなく）。行そのものに「ふさわしいかを見た自動チェックは無い」と書く。条件はフェンスの外の指示として書き、満たさなければ行ごと落とす
- 文面の存在は `tests/test_tracking_issue_checklist.py` が固定する

マーカー行は HTML コメントのため GitHub の Issue 画面には表示されない（`gh issue view --json body` では取得できる）。

#### レビュー追跡 Issue と Close 同期

レビューの単位はページ 1 枚であり（1 ページ ＝ 1 Issue ＝ 1 Close。`docs/DesignDoc-architecture.md` §1.6）、PR の Approve ではなく Issue の Close をレビュー完了とする（GitHub は PR 作成者本人の Approve を許さない）。経路 A の一括 PR と経路 B（`wikicommit-review`）はこの仕組みの対象外である。

**Issue Close 検知後の自動処理**: `.github/workflows/review-issue-close-sync.yml`（`/wikicommit-init` が Quartz 選択に関わらず常に配布）が `issues.closed` で起動し、ラベルが `wikicommit-review` の Issue だけを処理する。

1. 本文のマーカーからページパスを取得し、main 上でそのページが実在し `review_status: pending` のままかを確認する（違えば no-op — 冪等性）
2. `wikicommit/review-<lang>-<Type>-<slug>` ブランチで `review_status` を `reviewed` に、`reviewed_by` を Close した人の login にし、レビュー記録（`stage: issue-close`。Close した本人の最新コメントを本文にする）を同じコミットに書く。トレーラーは `Reviewed-by: <表示名> <<login>@users.noreply.github.com>`（§6.7）
3. `validate_frontmatter.py` / `check_wikilinks.py` の PASS のみを条件に自動マージする（追加の人間承認は要求しない）
4. マージ後に `gh workflow run deploy.yml --ref <default branch>` で Pages を再ビルドする — `GITHUB_TOKEN` による push は他のワークフローの `on: push` を起動しないため。`deploy.yml` が無ければ何もしない。dispatch の失敗は error でジョブを落とす（静かに取りこぼすと、公開サイトだけが未レビューのまま残る）。`permissions:` に `actions: write` が要る

**Close コメントの扱い**: 採るのは `closed_by` 本人の最新コメント 1 件（`--paginate` で全件取り、`created_at`（同秒は `id`）の最大をこちら側で選ぶ — `direction` パラメータはこのエンドポイントでは無視される）。本文はシェルのコマンドラインに載せず、ファイル経由で `record_review.py --note-file` に渡す。コメントが無ければ本文なしの記録を書く（正常な閉じ方）。取得・選別の失敗は `::warning::` を出して本文なしに劣化し、ジョブを落とさない。

**未決事項**: Close 後に再オープンされても `review_status` を `pending` に自動で戻さない。再レビューが要る場合は人間がページを書き換える。

### 6.3 Review

#### 経路 A: 自動生成フロー

```
/wikicommit-generate → ローカルに Wiki ページ生成（review_status: pending で出力）
  ↓
/wikicommit-merge → 品質チェック → PR → 自動マージ → レビュー追跡 Issue 作成
  ↓
レビュー追跡 Issue（wikicommit-review ラベル）の内容を GitHub 上、または /wikicommit-review 経由で確認
  ├─ 問題なし → Issue を Close（review-issue-close-sync.yml が検知して review_status を reviewed に書き換え、
  │              品質チェック通過後に自動マージ）
  └─ 問題あり → ページを修正（/wikicommit-fix 等）→ 修正が main に反映されてから Issue を Close（同上、自動マージ）
     ※ 既に reviewed のページを /wikicommit-fix が書き換えた場合は review_status が pending へ戻る
```

#### 経路 B: 人間起点・修正フロー

```
.wikicommit/entity/ にページを手動作成・編集
  ↓
/wikicommit-review（任意だが推奨）
  [1] frontmatter 補完（必須フィールドが欠けていたら LLM が補完提案）
  [2] sources チェック（なければ type: manual の設定を促す）
  [3] 整合性チェック（sources: がある場合、hash と sources.path の実ファイルを比較し不一致を指摘）
  [4] sources を取得し、独立した事実確認を実施 → 所見を提示し人間に明示確認を求める
      - 取得は resolve_source_cache_path.py --obtain-sources（全エントリを 1 コマンドで。取り下げ済みは読まない。まず抽出キャッシュ、無ければ type: path は抽出 Skill・
        URL は add_source.py --fetch-url）。エージェントの Web 取得ツールは使わず、管理ファイルにも書き込まない
      - 照合に使った URL の版の hash がページの sources[].hash と違えば、所見ではなくレビュー記録の本文に 1 行残す
      - 全文再掲はソースが取得できない場合や人間が希望した場合のみのフォールバック
  [5] 対応するレビュー追跡 Issue の有無を確認（経路B は通常無い）→ 無ければ review_status: reviewed をローカルに書き込む
  ↓
/wikicommit-merge → 品質チェック → PR 作成（review_status: reviewed の変更を含む） → 自動マージ
  （review_status: reviewed のページはレビュー追跡 Issue 生成の対象外）
```

`/wikicommit-review` は経路Aのページ（レビュー追跡 Issueが存在するページ）に対しても使える。その場合はステップ[5]で対応する Issue が見つかるため、ローカルに書き込む代わりに `gh issue close` でその Issue を Close する（詳細は下記 review_status 遷移表、および `.claude/skills/wikicommit-review/SKILL.md`）。

#### 内容が書き換わったページは `reviewed` のまま残さない

`reviewed` と `reviewed_by` は「この文章を人間が読んだ」という主張であり、ページの内容が書き換わればその主張は事実でなくなる。ページを書き込む 6 経路はすべて、内容が変わったページを `pending` に戻す:

| 経路 | 挙動 |
|---|---|
| `action: create`・`--regenerate`・`wikicommit-translate`・`wikicommit-synthesize` | `pending` を書く |
| `wikicommit-generate` Pass 3 の `action: update` | 内容が変われば `pending`（Pass 4 step 6 がスクリプトを実行） |
| `wikicommit-fix` | 同上（Step 5 でスクリプトを実行） |

**「常に `pending` に戻す」は採らない**（取り込みを続ける Wiki で `reviewed` が到達不能になる）。**内容が実際に変わったか**で判定し、判定は決定論的スクリプト `reset_review_on_content_change.py`（`docs/DesignDoc-ScriptSpec.md`）に委譲する。

線引きは 6 フィールドの ignore リスト（`generated_at` / `generated_by` / `generated_with` / `review_status` / `reviewed_by` / `sources[]`）で、それ以外の frontmatter と本文はすべて内容として扱う。**`sources[]` を bookkeeping 側に置くことが要である** — `action: update` はほぼ必ずソースを追記するので、内容とみなすと「常に戻す」に潰れる。`expires_at` は内容側（Pass 4 の照合対象）。

**第 3 の状態（`reviewed-stale` 等）は導入しない**。`wikicommit-merge` Step 8 は変更不要で、`pending` を走査する既存の挙動が戻ったページを拾う。既存ページへの遡及適用は行わない。`wikicommit-fix` が戻した場合、その場で `/wikicommit-review <page>` を実行すれば再署名できる旨を Skill の報告に含める。

#### review_status 遷移

| ステータス | 意味 | 設定タイミング | Wiki ページの表示 |
|---|---|---|---|
| `pending` | **まだ誰も読んでいない**（このページの知識はまだ誰にも渡っていない）。品質チェックは通過済みであり、Pass 4 による出典との照合も済んでいる — **欠けているのは到達であって、検査ではない** | `wikicommit-generate` 生成時に frontmatter へ埋め込み。**`reviewed` からの復帰もある** — `action: update` / `--regenerate` / `wikicommit-fix` が内容を書き換えた場合、`reset_review_on_content_change.py` が `pending` に戻して `reviewed_by` を落とす | ⚠️ LLM 生成であることを述べるバナー（読了に関する行は出ない） |
| `reviewed` | **表明していること**は 2 つ: (1) このページを人が最後まで読んだ — すなわち**この Wiki の知識が、生成した機械以外の少なくとも 1 人に渡った**。(2) **読んでいて明らかに変だと思う点は無かった**。**表明していないこと**: 内容が正しいこと（出典との照合は Pass 4 が行い、`.wikicommit/review/` に記録され公開ページにも表示される）・網羅性・世界が変わったが手元のどのソースも反映していない事実 | **経路 A**: レビュー追跡 Issue を Close 後、`review-issue-close-sync.yml` が書き換えて自動マージ<br>**経路 B**: `wikicommit-review` がローカルに書き込み → `wikicommit-merge` で自動マージ | 同じバナーに**読了の行が 1 行増える**（見出し・本文・生成情報は `pending` と同一 — レビューは行を足すのであって警告を取り消すのではない）。経路 A では `reviewed_by` の login、名前が無い場合は「人が読みました」。経路 B は `reviewed_by` を消す（前回の経路 A のレビュアー名を残さない） |

**`review_status` は「出来事」の器である**。1 回の読みは 3 つの産物を生む — (a) 欠陥への気づき（主張。giscus / 報告 Issue へ）、(b) 受け取った知識（出来事。`review_status` の Close）、(c) 価値の判断（量。giscus）。2 値のフィールドが運べるのは (b) である。(2) の「明らかに変だと思う点は無かった」は**ページについてではなく読みについて**の主張であり、読み終えた時点で終わる（「このページに問題は無い」は負の証明になる）。この区別を落とさないこと。

**表示文字列と定義文だけを変え、識別子は据え置く**: `review_status` / `reviewed_by` / `wikicommit-review` ラベル / ワークフローのファイル名 / Skill 名 / `Reviewed-by:` トレーラー。とくにラベルを改名すると open な追跡 Issue の重複判定が外れ、全ページ分が重複起票される。

**AI レビューは全件・人間レビューは一部（抜取）**。抜取の候補は `check_review_coverage.py` の `RISKY:` が選ぶ。閾値もカバレッジ率の目標値も置かない。抜取対象だけに追跡 Issue を立てる形にはしない（読みたい人が読めるページを機械が先に決めることになる）。既存実践との対応は [DesignDoc-architecture.md](DesignDoc-architecture.md) §15。

**既知の限界**: (1) 委任された Close 権限（triage ロール）で読まずに Close されることは機械では防げない（§6.7 のトレーラーの改ざん耐性と同じく、権限管理に帰着する）。(2) 経路 A は「引っかかった」を記録できない（`review-issue-close-sync.yml` は `--result pass` を固定で渡す）。Close に一言が来たかは `check_review_coverage.py` の `SUMMARY:` の `human_notes` が数える。Close 時に 1 ビットを取る仕掛けは、一致率を読む主体が実在したときに再開する。

### 6.4 翻訳パイプライン

翻訳パイプラインは「誰が・いつ呼ぶか（無人トリガー vs 対話実行）」と「1ページあたりの処理内容（原文全文 + 用語集注入 → 翻訳生成 → 品質チェック → フィールド付与）」を分けて考える。後者は呼び出し元によらず共通であり、**Phase 3 では対話実行版（`/wikicommit-translate`）を、Phase 4 では無人トリガー版を提供する**。

**用語集を先に確定させてから本文を訳す**。呼び出し元によらず `DefinedTerm` 型のページを他の型より先に翻訳する（一括モードの並べ替え。単体モードには並べ替える作業リストが無い）。注入する用語集は 2 つ — (a) 原語の `DefinedTerm` ページ全文（意味）と (b) 原語↔訳語の対応表（対象言語の `DefinedTerm` ページの `title` だけを読む。basename が結合キー）。対応表は品質チェックの突き合わせにも使い、`translator_notes` が対応表に優先する。`DefinedTerm` ページ自身を訳すときは、そのページ自身の用語を対応表から除外する（旧訳を拾って引き戻されるため）。

**ソースの原語の表記を翻訳に使う**。原文ページの `aliases` に翻訳先の言語の別名があれば `title` と本文の当該用語に使う。優先順位は `translator_notes` ＞ 翻訳先言語の別名 ＞ DefinedTerm 対応表 ＞ 翻訳者自身の訳。別名の言語は LLM が判断し、確信が無ければ使わない。**翻訳ページには原文ページの `aliases` を写さない**（別名はサイト直下のリダイレクト URL になり、同じ URL を取り合う）。決定事項の全体は `docs/DesignDoc-data.md` §4.1。

**品質チェックは翻訳した本人ではなくサブエージェントが行い、記録する**。渡すものは 3 つに限る:

| 渡すもの | 扱い |
|---|---|
| 翻訳ページ（まだ書き出していない） | 照合対象 |
| 原文ページ（全文） | **唯一の `SOURCE`** |
| 用語対応表と `translator_notes` | 参照資料（`SOURCE` ではない） |

**原文ページのソース文書は渡さない**（原文自身の誤りを翻訳のせいにする）。検査の内容は `review-rules.md` の `translate-check` 節にあり、`rules_version` を orchestrator が照合する（欠落・不一致なら 1 度だけ起動し直し、それでも駄目なら実行全体を停止）。`review-rules.md` が無ければ実行の最初に停止し `/wikicommit-init --no-overwrite` を案内する。FAIL は `issues[].instruction` を渡して `generate.max_retries` 回まで作り直し、**上限を超えたら書き出さない**（新規は `UNTRANSLATED`、訳し直しは古い翻訳が `STALE` のまま残る）。記録は `.wikicommit/review/` に `stage: translate-check` で書く（`docs/DesignDoc-data.md` §4.8・`docs/DesignDoc-publish.md` §8.8.1）。

#### Phase 4: 無人トリガー版（`main` マージが起点）

MVP（Phase 1–3）スコープ外。main マージをトリガーに人間の介在なしで LLM を呼ぶ無人実行が前提であり、`claude-code-action` を導入する Phase 4 の SaaS 実行基盤に合わせる。

```
原文ページ（translated_from を持たないページ）が main にマージ
  ↓
変更を検知（`claude-code-action` の GitHub Actions ワークフローとして実装。具体的なトリガー条件は実装時に確定する）
  ↓（処理対象を DefinedTerm 型のページが先に来るよう並べ替える）
  ↓（変更された原文ページ × config.yml の targets 言語 の組み合わせごとに処理）
├─ LLM が翻訳を生成（新規・更新いずれも無条件に全文再翻訳。既存の翻訳ページ本文は一切読まない
│  完全ブラインドな再翻訳だが、既存の翻訳ページに translator_notes フィールドがあればそれだけは
│  読み込み・尊重し、新しい出力にもそのまま引き継ぐ — docs/DesignDoc-data.md §4.2 参照）
│    入力: 原文ページ（全文）+ DefinedTerm/ の用語定義（訳語統一のため注入）+ 原語↔訳語の
│          対応表（対象言語の DefinedTerm ページの title のみ）+ 既存翻訳ページの
│          translator_notes（あれば）
│    出力: 翻訳ページ（以下のフィールド付き）
│      translated_from: <原文ページのパス>
│      source_commit:   <翻訳実行時点の原文ページ HEAD コミットハッシュ>
│                       （git log -1 --format=%H -- <原文パス> で取得）
│      translated_at:   <翻訳実行日 YYYY-MM-DD>
│      translated_by:   <翻訳実行モデル ID>（generated_by と同じ自己申告パターン）
│      translator_notes: <既存の翻訳ページから引き継いだ値。無ければ省略>
│
├─ [translate-check サブエージェント] 翻訳・原文ページ（SOURCE）・対応表と translator_notes（参照資料）
│  だけを渡して照合（意味のずれ・加筆・訳漏れ・用語の不一致・構造の破損）
│    PASS → 書き出す → record_review.py --stage translate-check --result pass
│    FAIL → issues[].instruction を渡して再生成（最大 generate.max_retries 回）
│           上限超過 → 書き出さない → --result discarded、完了報告に列挙
│
└─ /wikicommit-merge で翻訳 PR を作成
     merge 後の review_status は原文に関わらず pending
```

#### Phase 3: 対話実行版（`/wikicommit-translate`）

Phase 3 では人間が対話的に呼び出す `/wikicommit-translate` Skill を提供する。1ページあたりの処理内容（用語集注入・フィールド付与・品質チェック）は上記 Phase 4 版と同一であり、差分は「誰が・いつ呼ぶか」と「Git 操作を行わない」点のみ。

```
/wikicommit-translate <page> [--lang <target>]   # 1ページ単体翻訳
/wikicommit-translate [--lang <target>]          # ページなし: 一括モード（--lang はその言語の組に絞る）
```

```
[1ページ単体モード]
対象ページ + --lang（省略時は config.yml の translation.targets 全言語）を確定
  ↓（target 言語ごとに）
LLM が翻訳を生成（Phase 4 版と同じ入出力仕様。対応表は「その時点で存在する翻訳済み
  DefinedTerm ページ」だけになる — 単体モードには並べ替える作業リストが無いため）
  ↓
[translate-check サブエージェント] Phase 4 版と同じ照合・再試行・記録
  ↓ PASS のときのみ
ローカルに書き出し（review_status は原文に関わらず無条件で pending）
```

```
[一括モード（ページ引数なし）]
python .wikicommit/scripts/check_translation_status.py を実行
  ↓
UNTRANSLATED 件数 + STALE 件数（(原文ページ, target言語) の組の合算）を算出
  （--lang があればその言語の組だけに絞る）
  ↓
作業リストを DefinedTerm 型のペアが先頭に来るよう並べ替える（群内はパス昇順）
  ↓ 5件超過（wikicommit-generate / wikicommit-collect と同じ閾値）
件数を提示し (a) 全件処理 / (b) この順序の先頭5件のみ処理・残りは次回実行に回す をユーザーに確認
  ↓ 5件以下
確認なしで全件を1ページ単体モードと同じ処理で順次実行
```

`--lang` 未指定時、`config.yml` の `translation.targets` が空配列の場合はエラー終了し、「対象言語がありません。`--lang <lang>` を指定するか `config.yml` の `targets` を設定してください」と案内する。ページなしで `--lang` が `targets` に無く、その言語の翻訳もまだ無い言語を指すときも preflight で止め、「その言語は `targets` に無いので一括モードでは対象が見つからない。ページを指定するか `targets` に加える」と案内する — `check_translation_status.py` は UNTRANSLATED を `targets` の言語についてしか報告せず、STALE は既にある翻訳についてしか報告しないため、絞った結果は必ず空になり、黙って「0 件」で終えると `--lang` が効かなかったことが分からない。`targets` に無くても翻訳が既にある言語（単体モードで作った・`targets` から外した）は止めない — その STALE は報告されるので、絞り込みで更新できる。ページなしの `--lang` は拒否せず絞り込みとして扱う（「英訳だけ溜まっているものを片付けたい」という使い方をそのまま叶える）。

**工程の順序はエンジンが持つ**（`.claude/skills/wikicommit-translate/workflow.yaml`。仕組みは `docs/DesignDoc-skills.md` §11.0）。設定・`review-rules.md`・引数の検査、組の収集と並べ替え、`index.md` の再構築はエンジンが自分で実行する `script` 工程、5 件超の確認は一括モードのときだけの `human` 工程（非対話の既定は先頭 5 件）、1 組の翻訳・照合・記録・書き出しはエージェントが `references/translate-page.md` を読んで行う組ごとの `agent` 工程である。組の工程は、翻訳ページ（`translated_from`・`lang`・`source_commit`・`review_status: pending`）と、その実行の中で書かれた `translate-check` の記録がディスクに揃うまで完了にならない（discard した組は `result: discarded` の記録だけ）。「その実行の中で」は実行記録の `started_at` と記録のファイル名の時刻で判定するので、`started_at` が読めない実行記録では記録を全件受け入れるのではなく組のチェックを失敗させる（受け入れると以前の実行の pass 記録で組が通る。synthesize の `check-page` も同じ向き）。組の一覧と各組の結果は実行記録に置くので、途中で止まった一括翻訳は `skill_workflow.py next` で次の組から再開できる。

出力はローカル書き出しのみ。コミット・PR 作成は行わず、ユーザーが別途 `/wikicommit-merge` を呼ぶ（`wikicommit-generate` / `wikicommit-review` と同じ「対話実行・ローカル書き出しのみ」パターン）。

#### 翻訳の鮮度チェック・未翻訳検出

```
/wikicommit-status（または check_translation_status.py の定期実行）
  ↓
翻訳ページの source_commit と親ページの現 HEAD を比較 → ミスマッチで STALE
原文ページ × config.yml の targets の組み合わせで翻訳ページの有無を確認 → 存在しなければ UNTRANSLATED
  ↓
warning を表示（STALE は再翻訳、UNTRANSLATED は `/wikicommit-translate` の実行を提案）
```

#### WikiLink のクロス言語フォールバック

```
.wikicommit/entity/en/ ページ内の [[Person/yamada-taro]] の解決順序:
  1. .wikicommit/entity/en/Person/yamada-taro.md  → あれば使う
  2. .wikicommit/entity/ja/Person/yamada-taro.md  → translated_from を辿った親言語
  3. どの言語にも存在しない → 品質チェックが blocking エラー

翻訳ページが未作成 → warning のみ（非ブロッキング）
```

このフォールバックロジックはビルド前変換スクリプトと `wikicommit-ask` Skill の両方に実装する（Phase 5 以降のホスト型 MCP でも同ロジックを再利用する）。

### 6.5 削除フロー

```
/wikicommit-remove <page>
  ↓
対象ページに status: removed / removed_at / removed_reason を付与（ローカル変更）
├─ translated_from で紐づく翻訳ページも同様に処理
└─ 影響を受けた Type ディレクトリの index.md から該当エントリを削除
  ↓
/wikicommit-merge → 品質チェック → PR 作成
  ↓ 参照切れ WikiLink を検出 → 警告（非ブロッキング）
PR マージ → 公開 Wiki から非表示（ファイルは残る）
  ↓
（任意）/wikicommit-cleanup-links で参照切れ修正 PR を作成
（任意）ハード削除 PR を別途作成
```

**`status: removed` のページは `content/` へビルドされない**。「公開 Wiki から非表示」はリンク・索引から外れるだけでなく、ページ自身も `convert_wikilinks.py --output` に書き出されないことを意味する（書き出すと直接 URL で読める）。`convert_wikilinks.py` は変換ループで `status: removed` をスキップし、前回の実行が書き出した `content/` の `.md` のうち今回再生成されなかったものを削除する（stale cleanup）。

### 6.6 参照フロー（`/wikicommit-ask` / `/wikicommit-search`）

#### `/wikicommit-search <query>`

```
.wikicommit/entity/ 配下の全 .md ファイルをキーワードマッチ
  ↓
タイトル・タグ・本文を対象にファイル名検索（grep）
  ↓
ヒットしたページのタイトル・type・review_status・パスを一覧表示
  ↓
結果ゼロ → 「該当ページなし」と表示して終了
```

#### `/wikicommit-ask <question>`

```
/wikicommit-search で関連ページを取得（上位 5〜10 件）
  ↓
ヒットページの本文中の WikiLink（[[Type/slug]]）を1ホップ辿り、質問への関連性が高いものだけ
  追加取得（ヒット1件につき2〜3件・合計5件程度を上限）
  ↓
ヒットページ＋追加取得ページの本文を LLM のコンテキストに注入
  ↓
LLM が質問と同じ言語で回答
  ├─ 参照したページの review_status が pending の場合は回答冒頭に注記
  │   「⚠️ This answer references pages nobody has read yet: ...」（書式は wikicommit-search の ⚠️ Unreviewed 表示に揃える）
  └─ ヒットゼロの場合は「該当する知識が見つかりませんでした」と回答
```

### 6.7 Git コミットトレーラー規約

コミット author は常に人間ユーザー（Claude Code の実行者）となる。LLM の関与はトレーラーで記録する。

```
Co-Authored-By: <Claude display name> <noreply@anthropic.com>  # LLM が生成（GitHub 標準形式）
Generated-By:   <current model ID>                             # 生成モデルの精密なバージョン追跡
Reviewed-By-AI: <current model ID>                             # LLM がレビューした場合
Signed-off-by:  Taro Yamada <taro@users.noreply.github.com>    # 人間が承認（人間のみで作業した場合。CONTRIBUTING.md 参照）
Reviewed-by:    Taro Yamada <taro@users.noreply.github.com>    # レビュー追跡Issueを Close した人（経路A）
```

**`<current model ID>` / `<Claude display name>` は穴埋め対象であり、サンプルのリテラルではない**。

- **`Generated-By` / `Reviewed-By-AI`**: ランタイムが報告するモデル ID をそのまま書く（接尾辞を落とさない・短縮・正規化しない。`claude-opus-5[1m]` の `[1m]` は実際のモデル選択サフィックスである）。モデル ID の正規化表は持たず、機械検証も課さない（表に無い ＝ 不正、にならないため）
- **`Co-Authored-By`**: 実行中のモデルの表示名を書き、確信が無ければ素の `Claude` と書く。メールアドレス `noreply@anthropic.com` は固定（GitHub の共同作成者リンクはメールで解決される）
- **`Reviewed-by`**: `review-issue-close-sync.yml` が `gh api repos/{owner}/{repo}/issues/{number}` でライブ再取得した `closed_by.login` から機械的に組み立てる（イベントペイロードの `closed_by` は空で届く）。`Signed-off-by` と分けるのは、DCO の「変更内容への法的な保証」と「ページを読んでレビュー完了とみなした」を区別するため。対象はレビュー追跡 Issue の Close のみ
- **改ざん耐性の範囲**: `closed_by` は GitHub の認証に基づく事実だが、トレーラー自体は検証されない自由記述であり、書き込み権限を持つ人なら同じトレーラーのコミットを直接 push できる。それは元々持つ権限の範囲内であり、実害の起点はリポジトリの権限管理に帰着する。署名コミットの必須化は将来の検討課題とする

**配布物の規約: `Co-Authored-By` は実行中のモデルのベンダーで決め、表に無ければ書かない**。上のブロックはこのリポジトリ自身の開発規約であり、配布 Skill の規約は次の表である。Git に書く配布 Skill 5 本（`wikicommit-merge` / `wikicommit-schema-propose` / `wikicommit-update` / `wikicommit-init` の基盤コミット / `wikicommit-organize`）が使う:

| `Generated-By` に書くモデル ID の先頭 | 書く `Co-Authored-By` |
|---|---|
| `claude-`（Bedrock の `us.anthropic.claude-…` のように `anthropic.` で終わる接頭辞の後に来る場合を含む） | `<Claude display name> <noreply@anthropic.com>`（表示名が不確かなら `Claude`） |
| `gpt-` または `codex` | `Codex <noreply@openai.com>`（表示名は固定） |
| それ以外 | **書かない**（`Generated-By` だけを書く） |

判定はハーネスではなくモデルで、`Generated-By` の値の先頭で行う（1 つのハーネスが複数ベンダーのモデルを走らせうる）。トレーラー段落の写しは各 Skill に置き、`tests/test_commit_trailer_vendor_table.py` が一致を固定する。**`Reviewed-By-AI:` は配布 Skill が書かない**。既存コミットは書き換えない。

---

## 7. 品質ゲート — 概要

詳細は [DesignDoc-CISpec.md](DesignDoc-CISpec.md) を参照。

### チェック種別と実行主体

| レイヤー | チェック内容 | 実行者 |
|---|---|---|
| 構造 | スキーマ適合・sources フィールド存在 | `wikicommit-merge`（`validate_frontmatter.py` を呼び出し） |
| WikiLink | WikiLink 参照先存在確認・removed ページへのリンク検出・Type セグメント取り違え検出 | `wikicommit-merge`（`check_wikilinks.py` を呼び出し） |
| コンテンツ安全性 | ページ本文中の生 HTML タグ検出 | `wikicommit-merge`（`check_raw_html.py` を呼び出し） |
| 外部リンク | sources URL・本文中 https:// リンクの疎通確認 | `wikicommit-merge`（`lychee` を呼び出し） |
| スタイル | Markdown フォーマット統一 | `wikicommit-merge`（`markdownlint-cli2` を呼び出し） |
| グラフ | 孤立ページ（orphan）検出・重複ページ検出 | `wikicommit-merge`（`check_orphans.py` を呼び出し） |
| グラフ | wanted（被参照だが実体なし）ページ検出・Type セグメント取り違えの分離 | `wikicommit-status`（`check_wanted_pages.py` を呼び出し。全ページ走査が必要なため diff ベースの `wikicommit-merge` ではなく `wikicommit-status` 側） |
| 鮮度 | `expires_at` 超過・翻訳陳腐化・ingest ハッシュずれ | `wikicommit-status`（定期実行）または `/wikicommit-status` |
| 内容 | 元文書との整合性・ソース間の食い違い・**WikiLink 1ホップ以内の**ページ間矛盾検出。**判定は `.wikicommit/review/` に記録される**（PASS したページと `failed_pages` に落ちたページの両方） | `wikicommit-generate` の生成エージェントループ内（ユーザー自身の LLM 契約で実行） |
| 内容 | 合成ページ（view ページ）と grounding ページ群の照合（裏付けの無い主張の検出・grounding ページ同士の食い違いの報告）、および `kind` の `Boundary` 検査 | `wikicommit-synthesize` Step 5.5 のレビューサブエージェント（同上） |
| 内容 | 翻訳ページと原文ページの照合（意味のずれ・加筆・訳漏れ・用語の不一致・構造の破損） | `wikicommit-translate` Step 4 のレビューサブエージェント（同上） |

**検査の内容は `.wikicommit/review-rules.md` にある**。「全経路共通の規律」と「経路ごとの差分」が構造的に分かれており、段取り（リトライ・`failed_pages`・書き出し・`status` 更新）は各 Skill に残る。規律を変えたら `rules_version` を上げる（記録側の `skill_blob` は自動で変わるが、`rules_version` は手で上げないと記録が嘘をつく）。

**check 1（claim support）と check 4（ページが持たない引用文書）の境界は「主題性」である**。ソース自身が自分の主題として述べた別文書についての事実は check 1 の範囲であり、check 4 が FAIL にするのはソースが別のことを書きながら名前を出しただけ（passing mention）の文書に限る。ただしページが事実の出どころとしてタイトル・URL・日付付きの投稿を**引用している**場合は引き続き check 4 の対象である。判別が付かない場合は passing mention として FAIL に倒す。境界は check 1 側・check 4 側の両方に書く。

**内容レイヤーの照合範囲**:

- **ソース間の食い違い**（同一ページ・複数ソース）: その事実の主題を自分の主題として扱っている側を採る（一覧・目録の 1 行は、その項目を主題とする文書より弱い証拠）
- **WikiLink 1 ホップ以内のページ間矛盾**: 既存ページへの outbound と、そのページを参照する既存ページを、合計 5 件まで追加コンテキストとして渡す（outbound 優先。組み立ては `build_onehop_context.py`）。レビュー中のページが誤っていれば FAIL、相手側が誤っていそうなら FAIL にせず Completion Notice に報告する（`page_at_fault: "other"`）
- **限界**: 同一バッチでは先に生成されたページしか見えず、異なるバッチの 2 ページ間の矛盾には届かない。リポジトリ全体走査（リンククラスタ単位の map-reduce・独立した監査 Skill が有力）は将来の課題とする

**合成ページの照合**（`wikicommit-synthesize` Step 5.5）: Pass 4 と同型で、返却形式は §4.6 のエージェント間 JSON、`source_file` には grounding ページのパスが入る。再試行は `generate.max_retries` を流用し、上限超過時は書き出さずに停止して報告する。grounding ページ同士の食い違いは FAIL にせず完了報告に列挙する。grounding set から `derived_from` を持つページを除外する（合成ページを通常ページの 1 段上に留める。索引からは除外しない）。grounding のうち `pending` のページは本文生成の前に列挙して伝える（警告でありゲートではない）。

### 機械レビューが評価しないもの

WikiCommit の機械レビューは「生成ページが与えられたソースに忠実か」を見るものであり、**網羅性**（他の資料を調べれば足せる情報があるか）は評価対象ではない。規律は `review-rules.md` にある。

| ルール | 内容 |
|---|---|
| **網羅性は基準ではない** | ソースが述べているのにページが書いていないことは、それ自体では欠陥ではない。何を書き何を書かないかは型テンプレートの `granularity` と Pass 3 の抽象度ルールが決めており、レビューはその判断を再評価しない。合成ページ側では「ソース」を grounding ページに読み替える |
| **外部調査は行わない** | 判断がつかないときに Web 検索・未登録文書の取得へ出ない。例外はソースの記述自体が疑わしくそれを確かめないとレビューが成立しない場合に限り、その旨を所見に明記する |

**「FAIL にしてよいのは、ソースに無いことをページが述べている場合に限る」という形で書いてはならない**。FAIL 条件の網羅列挙として読め、帰属の取り違え・無帰属の単一ソース定式化・ソース間の食い違いで弱い側を採った場合という他の FAIL を弱める。書くのは**不足の側だけを免責する非対称**である。

**外部調査の禁止は証拠拘束の言い直しではない** — 証拠拘束は「自分の知識で判定するな」、こちらは「調べに行くな」（行動の側）。`wikicommit-review` Step 4 のソース取得は**登録済み**ソースの再取得であって外部調査ではない。

#### `MISSING_SOURCE` は登録候補として拾う

Pass 4 がページの引用・言及する文書が `sources` に無いとして `MISSING_SOURCE` で FAIL させた文書を、書き出し確定後に「登録候補になりうる文書」として 1 行ずつ報告する（報告するがブロックしない。登録は `/wikicommit-generate <url>` → `action: update` が担う）。

- **収集は Pass 4 の各回で行い**（最後に残ったものには何も残っていない）、出力は書き出し確定後に一度だけ・**文書単位に畳む**
- **URL が無い場合は特定可能なタイトルで報告し、どちらも無ければ報告しない**
- **`failed_pages` との二重報告を避ける** — ある文書を挙げたページがすべて破棄された場合はその旨をその行に添える
- **`wikicommit-synthesize` Step 5.5 の `MISSING_SOURCE` は対象外**（「どの grounding ページもその主張を述べていない」意味で、指すべき外部文書が無い）
- **`wikicommit-review` Step 4 は所見 1 件として報告する**。突き合わせ先は Step 4 手順 1 が実際に集めたソース集合（翻訳ページは `sources` を親から継承するため）。`derived_from` ページは対象外

網羅性を機械的に検出する仕組みは作らない。既存ページへの遡及適用も行わない。

### orphan 検出の設計

| 操作 | 挙動 |
|---|---|
| 削除フロー（status: removed 付与） | 参照切れを **warning のみ**（マージ可） |
| 新規追加 | `status: removed` なページへの WikiLink を **ブロック** |
| 新規追加（参照先ページがどの言語にも存在しない） | **warning のみ**（常にマージ可。ブロックすると「WikiLink 化をやめて地の文で書く」を誘う。集計は `check_wanted_pages.py` が担う） |
| 新規追加（参照先ページは無いが、同じ slug が別 Type に実在する） | **ブロック**（実体は在り、正しい対処はリンク 1 語の修正であるため。ERROR メッセージが実在する Type を名指しする） |
| orphan（被リンクゼロ）ページ | **warning のみ**（常にマージ可） |
| wanted（被参照だが実体なし）ページ | **warning のみ**（常にマージ可。`wikicommit-status` の `check_wanted_pages.py` が全ページ横断で集計） |
| 重複ページ | **ブロック** |

### マージ条件

| 経路 | 条件 | Merge 後の review_status |
|---|---|---|
| 経路 A: 自動生成（wikicommit-generate → wikicommit-merge） | 品質チェック全 blocking PASS | `pending`（レビュー追跡 Issue の Close 待ち） |
| 経路 A: レビュー追跡 Issue | 人間による Close（マージ自体は `review-issue-close-sync.yml` が自動実行） | `reviewed`（Issue Close をトリガーに自動更新） |
| 経路 B: 手動作成（wikicommit-review → wikicommit-merge） | 品質チェック全 blocking PASS | `reviewed`（wikicommit-review がローカルで設定済み） |

**warning はどの経路でもマージ可否に影響しない**。本節の 2 つの表に現れる warning（orphan・wanted・未解決 WikiLink・lychee・markdownlint）は例外なく「常にマージ可」であり、`wikicommit-merge` Step 3 の確認が担っているのは人に見せることである。人がいない実行では確認せず、warning を PR 本文に記録して続行する（§6.2）。`ERROR:` / `DUPLICATE:` は対話・非対話を問わず中断する。
