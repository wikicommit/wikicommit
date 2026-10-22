# スクリプト仕様書（経緯）

> [DesignDoc-ScriptSpec.md](../DesignDoc-ScriptSpec.md) の各節について、**なぜそうなったか・以前はどうだったか・何を採らなかったか**を残す。見出しは本文と揃えてあり、本文の節からここの同じ見出しを引けば経緯にたどり着く。いま何が仕様かは本文が正であり、ここの記述が本文と食い違う場合は本文を信じる（ここは書かれた時点の記録であり、後の変更で古くなった記述も直さずに残す）。
>
> 本ファイルは Issue #1143 で本文から切り出した。各コールアウトと本文の旧版の段落は移行時点の文面のまま（本文側の節への参照「下記」「上の」「本 Issue」「本節」等は移行前の配置と文脈を指す）。

## 共通規則

- **出力の言語**: stdout・stderr に出る文字列はすべて英語で書く（Issue #770）。読み手は運用者とエージェントであって読者ではないため、Issue #405 が管理ファイルの見出しについて下したのと同じ判断で固定の英語とする。コメント・docstring は日本語のまま据え置く（読み手が開発者であり `docs/` と揃う）。公開ページに出る読者向けラベル（`convert_wikilinks.py` の `ROOT_INDEX_LABELS` / `OVERVIEW_LABELS` / `SOURCE_*_LABELS`）はこの規則の対象外で、`primary_lang` で切り替わる。`tools/check_script_output_language.py` が CI で blocking の回帰ガードとして走るが、`print()` の引数しか見ないため、`_frontmatter.py` のようにメッセージを戻り値として返すスクリプト（同ファイル自身は英語化済みだが、走査には掛からない形である）は手作業で確認する

- **コメント・docstring に書くもの**（Issue #1329）: 配布スクリプトの総行数は 2026-08-01 の 2,746 行から 2026-10-15 の 21,694 行（約 1.0MB）へ約 8 倍になり、その時点の内訳はコード 11,575 行・docstring 5,766 行・コメント 2,114 行・空行 2,239 行だった。docstring とコメントには `Issue #` が 623 箇所（番号の種類は 199）あり、冒頭 docstring は 1 本あたり平均約 47 行で、ScriptSpec 本文と history を兼ねた小さな DesignDoc になっていた。Issue #1138 が DesignDoc で解いた問題（読まれるのは「いま何が仕様か」なのに経緯が一緒に読まれる）がスクリプトに残っていたため、同じ規則をスクリプトに広げた。実行時のコンテキストには影響しない（Skill はスクリプトを実行するだけで本文を読ませない）ので、効くのは開発時に読む負担と、`Issue #NNN` を辿れない配布先（Issue #1054 と同じ理由）の 2 つである。Issue #1054 の時点ではスクリプトの検査を「出力する文字列」に限り、コメント・docstring を対象外にしていた。ラチェット（`SCRIPT_CAPS`）は導入時点の件数で始め、1 ファイルずつ移しながら下げる（移行の順序は `Issue #` と行数の多いものから。最初に移したのは `check_review_coverage.py`）。ラチェットの対象は `tools/check_distributed_issue_refs.py` の `distributed_scripts()` と同じ 62 本で、Issue #1329 が数えた `templates/scripts/` の 54 本に、配布 Skill 直下の `scripts/`（`init.py`・`_root_outputs.py`・各 `workflow_checks.py` 等）を加えたもの — これらも `install.sh` が利用者のリポジトリに配るため

- **`SCRIPT_CAPS` を畳んだ**（Issue #1343）: コメント・docstring の検査は、導入時（Issue #1329）にはスクリプトごとの件数の上限表 `SCRIPT_CAPS`（`.claude/skills/` からのパスをキーにした 62 行）を持つラチェットだった。上限は下げるだけで、表に行の無い配布スクリプトと、配布スクリプトの無い行はどちらも ERROR、件数が上限を下回ると `NOTE:` が下げ先を示した。Issue #1343 が 9 本の PR（#1353〜#1360 と、最後の 22 本を移して表を畳んだもの）で全スクリプトの経緯を history の各見出しへ移し、全行が 0 になったため、完了条件どおり表を「0 件」の 1 規則に畳んだ。表のためだけにあった帳簿（行の過不足の ERROR と `NOTE:`）も外し、いまは参照 1 件ごとに行番号付きの ERROR を出す。指示文の `CAPS` は全 Skill が 0 だが、この変更の範囲外なので表のまま残した

## `.wikicommit/entity/` の走査は `_wikilink.py` に集約する

**`_wikilink.py` の docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 543 → 529、コード 178 → 178、docstring 221 → 216、コメント 88 → 79、空行 56 → 56（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 21 → 0（`Issue` の付かない `PR #109` も外した）。出力する文字列には `#NNN` は無い。他のスクリプトが import する共有モジュールなので、名前は 1 つも変えていない。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このモジュールは Issue #114。それまでは各スクリプトが `WIKILINK_RE` と path→(Type, slug) の変換関数をそれぞれ持っており、食い違っていた（`convert_wikilinks.py` の正規表現には、`check_orphans.py` / `check_wikilinks.py` が PR #109 で取り込んだ二重スラッシュを拒む修正が無かった）
- 表示名付きの `[[Type/slug|表示名]]` を受け付ける前は、この形はここで何にも一致せず、どのゲート（削除済みページの ERROR・孤立ページの件数・統合の書き換え・Pass 4 の 1 ホップの集合）も黙って通していた
- `ENTITY_DIR` は、9 本のスクリプト（と `templates/` の写し）がそれぞれ `ENTITY_DIR = Path(".wikicommit/entity")` を定義し直していたのをここへ集めたもの（Issue #487。Issue #477 のコードレビューで見つかった）。プロセスの cwd からの相対であることは集める前と同じ
- view ツリーは Issue #675。view ページに型を選ばせた結果が Issue #545 で、同じ話題の 2 回の実行が `custom/Practice/…` と `Practice/…` に分かれ、片方はどの WikiLink からも辿れなかった
- `VIEW_KINDS` のコメントが挙げる「空の受け皿を出荷しない」規則は Issue #553
- `normalize_name()` を共有する `check_recurring_characters.py` は Issue #560、`check_unlinked_entity_mentions.py` は Issue #561
- `.wikicommit/wiki/` → `entity/` の改名は Issue #477
- `is_entity_asset()`・`collect_entity_pages()` は Issue #677（この節の以下の記述）。`collect_entity_pages()` の docstring は、`check_wanted_pages.py` が index を走査するのは走査を共有する前にそうしていたからだと書き、条件が 18 箇所に独立に書かれ `assets/` の半分が 3 通りの意味に割れていたこと・うち 1 つが誤っていたこと・新しい挙動は無く、同じ走査を各規則の最も厳しく最もよく文書化された読みで行うことを書いていた
- Type 取り違えの判定（`build_slug_type_index()` の前のコメント）は Issue #563。view ページを `View` の Type で索引に入れるのは Issue #675
- 書かれていないページへのリンクを止めない扱い（`other_types_for_slug()`・`resolve_wikilink()`）は Issue #340
- ページの同一性と WikiLink 解決の 6 関数は、`build_onehop_context.py` が同じ解決を要したときに `check_wikilinks.py` から移った（Issue #947）。うち 3 つは既に他所に写しがあり、`load_primary_lang()` は `check_wikilinks.py`・`build_survey_view.py`・`convert_wikilinks.py` の 3 か所にあった — 4 つ目の写しは、Issue #677 がこのモジュールに集めて払うのをやめたコストそのものである。フォールバックの順序は関数ですらなく `check_wikilinks.py` の `main()` ループに直書きされていたので、2 つ目の呼び出し元はそのループを読んで書き直すしかなく、Pass 4 の 1 ホップの組み立ての Type/slug 抽出はそうして一から（誤って）書かれた。`resolve_wikilink()` の docstring も、これが関数でなかったことを書いていた
- `load_primary_lang()` の既定値 `"en"`: Issue #159 がツール全体の既定を `"ja"` から変え、Issue #376 がこれをそれに揃えた

`.wikicommit/entity/**/*.md` を走査して `assets/` と `index.md` を除く、という同じ判断が **18 箇所**に独立して書かれており、`assets/` の判定だけで **3 通りの意味論**に割れていた。うち `check_wikilinks.py` の被リンクインデックス構築は**実際に壊れていた** — 同スクリプトは絶対パスの `entity_dir`（`Path.cwd() / ENTITY_DIR`）を作る一方、`"assets" in wiki_page.parts` をそのフルパスに適用していたため、**リポジトリの祖先ディレクトリのどれかが `assets` という名前だと全ページがスキップされ、被リンクインデックスが空になる**。失われるのは削除フロー（`docs/DesignDoc-pipeline.md` §6.5）が依拠する参照切れ WikiLink の警告そのもので、**エラーにならず件数が減るだけ**なので `/wikicommit-remove` → `/wikicommit-merge` は正常に完了したように見える。

このケースは `_wikilink.py` の `build_slug_type_index()` が既に名指しで警告し、同関数では正しく修正済みだった — **正しい実装が同じファイルにあるのに、隣のループがコピー元の誤った形を保持していた**。

`_wikilink.py` に 2 つの関数を置き、全走査をそこへ寄せた:

**`assets/` の意味論は最も狭い定義に統一した**。`docs/DesignDoc-data.md` §3.1 が `.wikicommit/entity/assets/` を全言語共通の単一の置き場と定義しており、`<lang>/assets/` のようなものは仕様上存在しない。緩い定義（配下の任意セグメント）を採ると `assets` という名前の Type やスラッグを将来禁じることになる。

**`include_index=True` を渡すのは 3 箇所**: `rebuild_index.py`（最後のページが削除された Type ディレクトリは `index.md` しか残らないため、それ自体を見つける必要がある）・`check_wikilinks.py` の被リンク走査（`rebuild_index.py` が各ページの WikiLink を index に書くため、そこへのリンクは削除対象ページへの実在する参照である）・`check_wanted_pages.py`（集約前の挙動をそのまま保つ。「陳腐化した index のエントリを『誰かが書いてほしいページ』と数えるべきか」は走査の集約とは別の問いであるため、本 Issue では動かさない）。

**`validate_frontmatter.py` と `check_raw_html.py` は移行対象外**。この 2 本は `assets/` も `index.md` も除外せず全ファイルを検証する（前者は `index.md` の `sources` 必須を明示的に免除する分岐まで持つ）。対象は「グラフ・集計の対象となる本文ページ」ではなく「ディスク上の全 `.md`」であり、巻き込むとこのヘルパーの意味が薄まる。

**ページの同一性と WikiLink 解決も同じ理由で寄せた（Issue #947）**。`load_primary_lang()`・`page_lang()`（旧 `get_lang()`）・`is_removed()`・`link_target_path()`・`type_slug_from_wiki_path()`・`extract_wikilinks()` が `check_wikilinks.py` から移り、あわせて**フォールバックの順序そのもの**が `resolve_wikilink()` として関数になった — それまでは `check_wikilinks.py` の `main()` ループに直書きされており、2 つ目の呼び出し元は import できるものを持たず、そのループを読んで書き直すしかなかった。`load_primary_lang()` は `check_wikilinks.py` / `build_survey_view.py` / `convert_wikilinks.py` の **3 箇所に複製されていた**ため、3 本とも import に切り替えてある。**移設であって挙動の変更ではない**ので、既存の `tests/test_check_wikilinks.py` / `test_convert_wikilinks.py` / `test_build_survey_view.py` が回帰の検出を兼ねる。

`convert_wikilinks.py` の `is_in_assets()` はそのまま残す — publish 側で `output_dir` に対しても使われる（stale cleanup・`sync_assets()`）ため、entity ツリー専用の `collect_entity_pages()` では置き換えられない。同ファイルの `generate_overview_page()` は Type 取り違え判定を独自に持っていたが、`other_types_for_slug()` は index を引数で受け取る設計なので共有関数へ寄せた（走査は増えない — `page_stats` が既に持つ `type_raw` から index を組み立てるだけ）。

**既存リポジトリへの遡及適用は行わない**。`.wikicommit/scripts/` は `init.py` が展開する配布物であり、変更が届くのは新規 init するリポジトリのみ（本ドキュメント群が繰り返し採る「新旧混在を許容する」方針）。上記のバグは「リポジトリの祖先ディレクトリ名に `assets` が含まれる」場合にのみ発火するため、既存リポジトリで実際に踏んでいる可能性は低い。

## merge の blocking な 3 本は status が全ページに走らせる

blocking な（exit 1 を返す）ページ検査はスクリプト 4 本・所見 5 分類ある。`wikicommit-merge` は `check_orphans.py` 以外の 3 本を**変更ファイルにだけ**走らせる — 引数なしにすると、そのバッチが触れていないページの既存のエラーでバッチ全体が止まるためであり、これは正しい。問題は、**一度書かれたページに対してはそれ以降誰も 3 本を走らせていなかった**ことにある。

下 3 行はいずれも**書かれた後に壊れうる**。`type:` と `properties:` の検証は `.wikicommit/schemaorg-vocab.json` と `.wikicommit/schema/` を参照するので、語彙を取り直したり型テンプレートを取り込んだりすれば通っていたページが ERROR になる。経路 A のページは `pending` のまま公開されるので、生 HTML が残れば公開サイトで実行されうる（Issue #377）。削除フローの非対称設計（削除 PR は warning のみ）は、消し残った参照を後から誰かが報告することを前提にしている。それまでの唯一の検出器は `/wikicommit-update` Step 7 の全ページ走査で、これは Issue #571 の副産物であり、配布物を取り込むときにしか走らなかった。

**決定**:

- **新しいスクリプトは作らない**。status の Step 3 に 3 本を足す。集約用のスクリプトは ERROR 行を拾うためだけの層になり、`check_wanted_pages.py` を広げる案は 1 カテゴリしか埋めない
- **表示は 1 行に畳む**（`Blocking errors merge does not re-check: <N>`。1 件以上なら ERROR 行をその下に並べる）。Issue #864 / #867 の基準（ほぼ常に 0 の行を足す代償）に照らして 3 行にはしない。この行は healthy 判定を止める — 実際の欠陥で、直し方が行に書いてあり、実測では 0 だったので healthy に到達できなくなることはない

**実測**（2026-09-29。dev 版 `1d427aa` の 3 本を unscoped で実行）:

| パイロット | ページ数 | `validate_frontmatter.py` | `check_wikilinks.py` | `check_raw_html.py` |
|---|---|---|---|---|
| `wikicommit/decameron-wiki` | 522 | ERROR 0 / WARNING 27 | ERROR 0 / WARNING 6 | ERROR 0 |
| `wikicommit/ai-driven-dev-wiki` | 2,042 | ERROR 0 / WARNING 0 | ERROR 0 / WARNING 14 | ERROR 0 |

decameron の WARNING 27 件はすべて `index.md` の `review_status` 未設定（Issue #580 より前の index）で、`check_wikilinks.py` の WARNING は両方とも未解決リンクだった。「初回に大量に出て常時点灯する」（Issue #562）は起きず、当たるのは逆側の「ほぼ常に 0 の行」の代償である — 1 行に畳んだのはそのためである。

**`/wikicommit-update` Step 7 の全ページ走査は残す**。pre-existing かどうかの判定にこの走査が要るため。Step 8 / Step 9 の報告文面は「`/wikicommit-status` が毎回報告する」に書き直した。**遡及適用は行わない** — 既存パイロットの逸脱は、この変更が届いた後の最初の `/wikicommit-status` で列挙される。

## build_onehop_context.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 285 → 282、コード 162 → 162、docstring 73 → 70、コメント 22 → 22、空行 28 → 28（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 6 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- これをスクリプトにしたのは Issue #947。それまでは `references/pass4-review.md` が近傍の探し方を散文で書いており、入ってくるリンクには具体的な手順があったが、出ていくリンクには何も無かった。あるパイロットの実行ではその穴を使い捨ての正規表現 `\[\[([A-Za-z0-9_/]+)\]\]` が埋め、文字クラスに `-` が無いため `vibe-coding` や `spec-driven-development` に 1 つも一致しなかった。エラーは出ず、集合が小さくなっただけで出力は正しく見えた。後から計算し直すと 27 ページ中 24 ページで文脈が変わった
- slug を英語の kebab-case にする規則は Issue #193。決定論的な操作を実行のたびに散文から導き直さない規則は Issue #474
- docstring は、`_wikilink.py` の `WIKILINK_RE` が当時すでに 4 本のスクリプトのリンク抽出に使われていたと書いていた（いまはリンクを抽出する他のスクリプトがそれを使う、と書き直した）
- `MAX_PAGES = 5` を `wikicommit-ask` の 1 ホップ展開と同じ桁にしたのは Issue #459
- 書かれていないページへのリンクが正常で blocking でないことは Issue #340
- `.wikicommit/wiki/` から `entity/` への改名は Issue #477

### 目的

**それまでは散文の指示であり、しかも片側にしか書かれていなかった。** inbound 側は「`\[\[<Type>/<slug>\]\]` と**エスケープして** `Grep` せよ」と具体的で、ripgrep で `[[` が文字クラスになる罠まで名指ししていた一方、outbound 側は "the existing pages this page links to" という散文だけで、抽出方法を一切書いていなかった。

`wikicommit/ai-driven-dev-wiki` の実行では、その空白が使い捨ての正規表現 `\[\[([A-Za-z0-9_/]+)\]\]` で埋められた。**この文字クラスは `-` を含まない。** WikiCommit の slug は Issue #193 の規約で英語のケバブケース（`vibe-coding` / `context-engineering` / `spec-driven-development`）であるため、このパターンは `]]` まで届かず、そうした slug への発リンクに**完全に不一致になる**。

**そして誤りの向きが悪い** — 例外にはならず、**集合が静かに縮むだけで出力は正常に見える**。しかも 2 つの偶然が重なって気づきにくくなっていた: inbound 側が別実装で正しく動いたため集合は空にならず、ハイフンを含まない slug が 5 つ実在したため outbound もゼロにはならなかった。修正後に集合を再計算すると **27 件中 24 件で内容が変わった**。検出したのはレビュー側で、サブエージェントが「このページがリンクしている実在ページが one-hop コンテキストに渡されていない」と所見に書いた。

**正規のパーサは既にあり、4 本のスクリプトが既にこれを使っている** — `_wikilink.py` の `WIKILINK_RE` は Type 部（PascalCase・ハイフン無し）と slug 部（`[A-Za-z0-9_-]+`・ハイフン有り）を別のクラスで扱い、同ファイルのコメントがその理由を述べている。`check_orphans.py`・`build_survey_view.py`・`check_wanted_pages.py`・`check_wikilinks.py` はいずれも `WIKILINK_RE` で WikiLink を取っている。Issue #474 が名指しした形そのもの（完全に決定論的に判定できる操作を instruction として表現したために、実行のたびに即興の正規表現が書かれる）である。

**抽出だけでなく組み立て全体を委譲する。** 現在同じ段落が散文で LLM に委ねている 3 つの skip 判定（`index.md` / `status: removed` / レビュー対象ページの翻訳）・クロス言語フォールバック・outbound 優先の dedup・5 件上限も決定論的になる — これらはいずれも**集合を縮める操作**であり、同じ「静かに変わる」性質を持つ。

### 置き場所が `.wikicommit/scripts/` である理由

`docs/DesignDoc-skills.md` §11.5 の置き場所ルール（呼び出し元 1 Skill なら Skill 内）に素直に従うと Skill 内になるが、**そのルール自体が実態と食い違っている**ことが実地確認で判明した（同節「置き場所の判断基準」参照）。決め手は写しの数である — 本スクリプトが要するのは `WIKILINK_RE`・エンティティ / view 走査・`parse_wiki_path`・frontmatter 読み・クロス言語解決一式であり、Skill 内に置いて import を避けると **Issue #677 が集約したばかりのものの 3 つ目の写し**を作ることになる。共有側に置けば写しは 0 本で、既存 14 本（呼び出し元が 1 Skill だけの共有スクリプト）と同じ形に収まる。

### 3 つの skip 判定

**翻訳の判定は `normalize_entity_prefix()` を通す。** Issue #477 より前に書かれた翻訳ページは `translated_from` に旧 `.wikicommit/wiki/` プレフィックスを持ったまま残る（新旧混在を許容する方針のため自動移行されない）ので、生の文字列比較にすると**そうしたページが skip されずレビュアーに渡る**。

### view ツリーも対象に含める

entity ページは `[[View/<slug>]]` を張れ（`View` は予約 Type セグメント。Issue #675）、`link_target_path()` は既に view ツリーを解決する。check 8 が見るのは「ページ間矛盾」であり、view ページも矛盾しうる相手である。view ページ自身をレビュー対象に取ることもできる。

### 既知の限界

`references/pass4-review.md` が既に述べている 2 つをそのまま引き継ぐ。**同一バッチ内では、あるページは自分より先に生成された兄弟しか見られない**ため、ペアが片側からしか照合されない（あるいは全くされない）ことがある。**異なるバッチで生成された 2 ページ間の矛盾は原理的に届かない。** リポジトリ全体走査が両方への答えであり、意図的に作られていない。

**既に書かれたレビュー記録は書き換えない**（記録は不変。Issue #750）。縮んだ集合で下された記録が既存リポジトリに残るが、**再レビューを促す仕組みは作らない** — `STALE_REVIEW:` はページかソースが変わったときに出るものであり、「レビューの入力が足りなかった」はそこに乗らない。

## build_survey_view.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 293 → 293、コード 174 → 174、docstring 70 → 70、コメント 20 → 20、空行 29 → 29（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 7 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `<topic>` なしの `/wikicommit-synthesize` が Wiki 全体を見て題材を探すことは Issue #586
- `properties.description` を 2〜3 文に抑える設計は Issue #495
- `--pages`（名指ししたページだけを縮約し、集計の順位を省く）は Issue #1075
- ページが本文に H1 を持たない決まりは Issue #546
- view ページ（`--include-view` のときだけ含める・`sources` ではなく `derived_from` を持つ）は Issue #675
- ページが立つソースの数（翻訳ページと view ページでは None）は Issue #990

### 目的

**本文全体を読む案（チャンク分割 + サブエージェントの map-reduce）は採らなかった**。実行のたび Wiki 全文を読むコストに加え、横断パターンの証拠が2つのチャンクに分かれると双方のサブエージェントが「単独では平凡」として落とす分割ロスがあり、狙っている対象そのものに直撃する。将来の拡張余地として残し、その際は全ページ走査による矛盾検出（バッチをまたぐページ間矛盾。`docs/DesignDoc-pipeline.md` §7）と分割戦略・返却形式を共有する。

### 使用場面

- `wikicommit-synthesize` Skill：Step 3（`--pages`。根拠ページの候補を、本文を読む前に選別する。Issue #1075。下記）
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。research guidance が渡されなかった場合のみ。Issue #672）。同じ縮約ビューを別の問いに使う — synthesize が「既存ページから何を書けるか」を探すのに対し、collect は「何が足りていないか」を探すため、`check_wanted_pages.py` の `WANTED:` と `check_orphans.py` の `ORPHAN:`（出自ソース付き。Issue #570）を併せて読む。本スクリプト側の変更は不要だった

### `--pages` — 名指ししたページだけを縮約する

`/wikicommit-synthesize` Step 3 は、検索候補（数十件）のうち「テーマを主題として扱っているか」を**本文を読む前に**判定する。判定に使うのは title・`properties.description`・`##` 見出しで、1 ページ数行である。これをエージェントに各ファイルを読ませて拾わせると、候補数十件分の本文を結局読むことになり、選別を前に置いた意味が消える（Issue #1075 検討事項 1）。取り出しは決定論的な操作なので、既存の縮約ロジックを候補だけに適用するモードとして足した（Issue #474 の方針）。

- `PAGE:` 行の末尾に `path=<パス>` を付け、翻訳ページ（`translated_from`）には `translation`、合成ページ（view ページ、または `derived_from` を持つ entity ページ）には `synthesized` を付ける。**判定は frontmatter から行う** — 従来の `grep -l "^derived_from:"` は本文中に YAML 例として `derived_from:` を引用しただけのページにも一致し、frontmatter を読み直す 2 段目を要していた

## check_extraction_quality.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 450 → 449、コード 209 → 209、docstring 106 → 106、コメント 85 → 84、空行 50 → 50（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 14 → 0。出力する文字列には `#NNN` は無い。ただしこのスクリプトは `argparse.ArgumentParser(description=__doc__)` でモジュールの docstring を `--help` に出すため、docstring から経緯を外したことで `--help` の説明文も変わった（判定と出力そのものは変わらない）。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 空シェルの検出（ガード B・A の 2 つの検査）は Issue #425 が設計した。冒頭の docstring は x.com の事例の全容を Issue #425 に委ね、「Issue #425 が設計した 2 つの検査」を実装すると書いていた（ガード C は後から足した）。`KNOWN_JS_SHELL_DOMAINS` の x.com / twitter.com は Issue #425 が直接確かめた
- ガード C（`check-fetch-capability`）と、YouTube の字幕が黙って落ちる partial extraction、`music.youtube.com` をガード B に入れたことは Issue #574。`FETCH_CAPABILITY_REQUIREMENTS` のコメントは、これを Issue #425 が x.com で見つけたのと同じ出所の失敗が別の経路で起きたものと書いていた
- 2 つのガードの強さを分けたこと（B は blocking、A は人に確かめる WARNING）、`CJK_CHAR_WEIGHT`、URL の境界でトークンを切ること・URL を CJK と全角記号で止めること・URL をパーセントデコードして数えることは Issue #562
- `.wikicommit/source-policy.md` の `wikicommit.exclude_domains`（`policy_exclude_domains()`）は Issue #564

### 目的

`wikicommit-generate` Pass 1 の抽出失敗判定は従来「抽出テキストが空または読み取り不能」の場合のみ `status: failed` としており、JS実行が前提のSPAサイト等を静的フェッチ手段（`markitdown`・`curl`）で取得した際に生じる「非空だが無意味」な抽出結果（ナビゲーション・ログインプロンプト・埋め込みJSON状態等のシェルのみで、実際のページ内容を含まない）を検知できなかった（Issue #425）。本スクリプトはこれを補う3つの決定論的チェックを提供する:

- `check-domain`（ガードB・即効性）: 抽出を試みる前に、URLのドメインが「静的フェッチでは空シェルを返すことが確認済み」の既知不可ドメインかどうかを判定する。`x.com`/`twitter.com`/`music.youtube.com`（Issue #574 — YouTube Music は `www.youtube.com` へリダイレクトしないため `markitdown` の `YouTubeConverter` が適用されず、「お使いのブラウザ向けに最適化されていません」の185文字程度のシェルしか返さない）を初期エントリとする。精度は高いが、確認済みドメインしかカバーしない。

ガードCが独立した軸として必要な理由（Issue #574）: `markitdown` の `YouTubeConverter` は `youtube_transcript_api` が未導入だと `IS_YOUTUBE_TRANSCRIPT_CAPABLE = False` となり、**例外も警告も出さずに** `### Transcript` セクションごと出力から落とす。残るのはタイトル・キーワード・Runtime・概要欄で、これらは実際の自然文であるため、空シェルでも低密度でもない — 実測でガードAの比率は字幕ありで 0.93、字幕なしで 0.90、タイトル+Runtime のみの最小ケースでも 0.75 であり、閾値 0.3 をどう調整しても区別できない（長さではなく文字種で判定する設計そのものによる）。ガードBの既知不可ドメインに `youtube.com` を追加する案も、「静的フェッチで空シェルしか返さないことが確認済みのドメイン」という定義に反する（字幕込みなら十分な内容が取れる）ため採らなかった。つまりこれは「空シェル」でも「低密度」でもなく **partial extraction** であり、取得後のテキストを見る限り検出しようがない。取得前に「取得能力があるか」を確かめる別軸のチェックが要る。

**3つのガードの強度は同じではない**（Issue #562・#574）。ガードCはガードBと同じくブロッキングだが、失敗の意味が異なる — ガードBはそのソースを `status: failed` にして次のソースへ進むのに対し、ガードCは**処理全体を停止する**（`markitdown --version` の Prerequisite チェックと同じ扱い。環境の問題であってソースの問題ではないため、`status: failed` として記録してはならない）。ガードBの `BLOCKED:` は確認済みドメインに対する決定論的判定であり、`wikicommit-generate` Pass 1 はこれをブロッキング（`status: failed`）として扱う。ガードAの `LOW_DENSITY:` はテキスト形状のヒューリスティックにすぎず、Pass 1 はこれを**人間に続行可否を確認する警告**として扱う（非対話実行時のみ従来どおり `status: failed`。詳細は `docs/DesignDoc-pipeline.md` §6.1・`.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。本スクリプト自身の終了コードは両者とも `1` のままで、強度の違いは呼び出し側の扱いにある。

**このスクリプトが扱わない partial extraction がある（Issue #715）**。ガードC が扱うのは「必要なパッケージを入れれば `markitdown` が完全に取れる」種類の欠落だけであり、`importlib.util.find_spec()` による判定はその前提の上に立っている。GitHub の Issue / PR URL は本文が取れてコメントだけが黙って落ちるが、必要なのはパッケージではなく別の取得経路なので、この前提を満たさない — ガードC を一般化すると exit 1 の意味（処理全体を止めて `pip install` を案内する）が端的に誤りになる。ガードB は「空シェル」の定義に反し（本文は取れている）、ガードA は落ちているものが自然文なので形状で区別できない（実測 0.37〜0.53 で閾値を余裕を持って上回る）。

したがってこの失敗クラスは**本スクリプトではなく `add_source.py` の登録時通知**が扱う（`partial_extraction_note()` / `PARTIAL_EXTRACTION_URL_NOTES`。ブロックせず・`status` を変えず・登録時に一度だけ知らせる）。**ここに 4 つ目のガードを足さないこと** — ガードは Pass 1 の分岐を左右するものであり、ブロックしない判定を同じ場所に置くと、精度の異なる 2 ガードを同じ強度で扱っていた Issue #562 の混同を作り直すことになる。詳細と、次に 3 例目が出たときの判断手順は `docs/DesignDoc-pipeline.md` §6.1 の該当コールアウトを参照。

### コマンド

`check-density` は `<file>` を省略した場合、標準入力からテキストを読む（抽出テキストがファイルとして永続化されていないソース向け。詳細は `.claude/skills/wikicommit-generate/SKILL.md` Pass 1 参照）。**この分岐の対象は Issue #885 で `.md` / `.txt` のソース 1 つに狭まったが、無くなってはいない** — `type: path` の抽出結果も `.wikicommit/.cache/extract-path/` に残るようになったため他のソースはすべてファイル経路を通る一方、`.md` / `.txt` は生ファイルが抽出テキストそのものなので意図的にキャッシュせず、抽出テキストはその実行のコンテキストにしか存在しない。（`type: manual` はここには現れない — 管理ファイルの `source.type` は `path` / `url` / `wikicommit` のみで、`manual` はページ側の `sources[]` にしか現れる値であり、Pass 1 の抽出対象にならない。）

### 処理フロー（`check-density`）

1. テキストをトークン化する。空白区切りに加え、**URL の境界でもトークンを切る**（スキーム付き `https://…`・プロトコル相対 `//upload.wikimedia.org/…`・裸の `www.…`）。空白だけで切ると、分かち書きしない日本語では地の文とパーセントエンコードされたリンク先URLが1つの巨大トークンに融合し、次の手順のURL判定が地の文もろとも捨ててしまう（Issue #562）。空白で単語を区切る言語ではURLは元から独立したトークンなので、この変更は結果を変えない。また URL 自体は空白・Markdown のリンク/引用区切り文字に加え、**CJK 文字・全角記号でも終端する** — URI は ASCII のみで構成されるため実在のリンク先を途中で切ってしまうことはなく、逆にこれがないと分かち書きしない日本語では裸の URL（Markdown リンクと違い `)` で終わらない）が後続の地の文を丸ごと飲み込み、同じ融合が再発する
2. URL トークンは無条件に「非自然文的トークン」とする。それ以外のトークンは、以下のいずれかに該当する場合に「非自然文的トークン」と判定する:
   - `{`・`}`・`<`・`>`・`;`・`=` のいずれかを含む
   - `"` を2個以上、または `` ` `` を含む
   - 上記に該当せず、前後の記号を除去した中核部分の英字比率が70%未満
3. 各トークンの文字数を重みとして、「自然文的トークン」の文字数の割合（`natural-language character ratio`）を計算する（トークン数ではなく文字数で重み付けすることで、単語間にスペースを持たないCJK言語〈日本語等〉が不当に低く判定されることを防ぐ）。文字数の数え方には Issue #562 で2つの正規化を入れている:
   - CJK 文字は `CJK_CHAR_WEIGHT`（3）文字分として数える。CJK 文字1字が担う情報量はラテン文字1字よりはるかに多く（`extracted_tokens` の概算がラテン文字4字≒1トークンと見積もるのに対し、CJK は1字≒1トークン）、同じ重みで数えると同じリンク密度の同等な散文でも日本語だけが不当に低く出るため。この重みは CJK を含まないテキスト（ガードAが本来捕まえるべき ASCII の JS/ナビシェル）には定義上まったく影響しない
   - URL トークンはパーセントデコードした長さで数える。`%E3%81%95` は日本語1文字が転送エンコードで9文字に膨らんだものにすぎず、そのまま数えると日本語ページへのリンクが英語ページへの同じリンクの9倍のマークアップに見えてしまうため
4. 比率が `LOW_DENSITY_THRESHOLD`（0.3）未満であれば `LOW_DENSITY:`、以上であれば `OK:` を出力する。`LOW_DENSITY:` の場合は、非自然文と判定された文字の内訳（`links` / `numbers/tables` / `other markup` の割合）を同じ行に添える — 人間が続行可否を判断する材料として、リンクが多いだけの正当なページ・統計表・実際のスクリプトシェルを見分けられるようにするため（Issue #562）

> **既知の限界: 数表密度**（Issue #562）: 統計表・数値中心の資料（国勢調査の結果概要・統計書等）は、非自然文の正体がリンクではなく数値と表の `|` 記号であるため、手順1のURL境界トークン化では比率が回復しない（saitama パイロットの実測で 0.112 / 0.080 のまま変化なし）。これは実装の欠陥ではなく汎用ヒューリスティックとしての精度の限界であり、追加の検出ロジックは設けない — ガードAが警告どまりであること（上記）と、手順4の内訳が `numbers/tables` 優位として表示されることで、人間が続行を判断できる。`check_wanted_pages.py` の「地の文言及は対象外」と同じ種類の、意図して残した限界である。

## validate_frontmatter.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 718 → 716、コード 421 → 421、docstring 117 → 115、コメント 82 → 82、空行 98 → 98（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 20 → 0（`pre-Issue-#495` の形の参照も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- frontmatter の分割（`properties:` に Schema.org の語彙のフィールドを入れ、それ以外はトップレベルに置く）は Issue #495。平置きの検出の docstring は、検出する形を「Issue #495 より前の形」に戻ったものと書いていた
- `type:` が Schema.org の語彙に実在するかの検査は Issue #512
- `sources[].license` は Issue #558
- パスと `type:` の一致の検査（`validate_type_matches_path()`）は Issue #545。それまでは何も強制しておらず、`/wikicommit-synthesize` がカスタム型のページを非決定的にどちらの場所にも書いた。既存のゲートはどれも捕まえなかった（`validate_frontmatter.py` 自身もパスと `type:` を比べていなかった）
- view ページの規則（`VIEW_REQUIRED_FIELDS`・`is_view_page()`・`validate_view_page()`・引数なしで view ツリーも走査すること）は Issue #675
- `expires_at` が `generated_at` 以前のときの WARNING は Issue #1130。判断を要さないものを指示に書かずここで検査するのは Issue #474
- `generated_with` / `translated_with` は Issue #577、`reviewed_by` は Issue #663
- `source_commit` の空文字列を `check_translation_status.py` が STALE として扱う取り決め（`derived_from[].source_commit` も同じ）は Issue #409
- `.wikicommit/wiki/` 接頭辞は Issue #477 の改名より前の形

### フォーマット検証ルール

#### `properties:` のフォーマット

**トップレベルへの平置き検出**: 上記 1〜3・5 で型が解決できた場合（4 で ERROR になった場合を除く）、`properties:` の中身とは別に、フロントマターのトップレベルに存在するキーのうち構造的フィールド一覧（`title`/`lang`/`type`/`sources`/`tags`/`review_status`/`expires_at`/`generated_at`/`generated_by`/`generated_with`/`wikidata`/`sameAs`/`aliases`/`properties`/`translated_from`/`source_commit`/`translated_at`/`translated_by`/`translated_with`/`translator_notes`/`derived_from`/`status`/`removed_at`/`removed_reason`/`merged_into`）に含まれないものを走査し、それが実際にそのページの型（祖先型含む）に属する Schema.org プロパティである場合は ERROR とする（例: `description:` をトップレベルに平置きしたページ。`properties:` へのネストが必須という Issue #495 の設計を LLM や人間の書き忘れから機械的に守るためのガード）。型に属さない、または Schema.org 語彙に存在しないキーは対象外（無関係な独自フィールドを誤検知しないため）。

## check_wikilinks.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 355 → 352、コード 201 → 201、docstring 37 → 35、コメント 82 → 81、空行 35 → 35（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 10 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 引数なしで全ページを検査するのは Issue #571。それまでは `OK: 0 files checked` を出して exit 0 で終わっていた
- `--changed` と `--deleted` の両方に入ったページに両方の検査を掛けるのは Issue #1257。それまでは被リンクの検査がそのページで飛ばされ、`wikicommit-merge` は削除するページを `--changed` にも入れるので、変更が 1 回の呼び出しに収まったときに削除フローが約束する WARNING が出なかった。docstring はこれに続けて、merge は今は 2 つを分けて呼ぶと書いていた
- `--skip-type-mismatch` は Issue #976
- `load_primary_lang` / `page_lang` / `is_removed` / `link_target_path` / `type_slug_from_wiki_path` は、`build_onehop_context.py` が同じ解決を要したときに `_wikilink.py` へ移った（Issue #947）
- 書かれていないページへのリンクを ERROR から WARNING に下げたのは Issue #340。Type セグメントの取り違えを WARNING にすると `check_wanted_pages.py` が既にあるページの複製を作るよう勧めることになる、という点は Issue #563
- 被リンク索引の走査を `collect_entity_pages()` に替えたのは Issue #677。それまでの `"assets" in wiki_page.parts` は絶対パスに掛けていたため、`assets` という名前のディレクトリの下にあるリポジトリでは全ページを飛ばし、`--deleted` の WARNING が黙って出なくなっていた

### コマンド

- **引数なし**: `.wikicommit/entity/` 配下の全ページ（`assets/` を除く）を検査対象にする（Issue #571）。`--changed` 相当だが、**同一コミット内新規追加の例外は無効**にする — あの例外は「参照先はまだ存在しないがこの変更が追加する」という意味であり、対象集合が「既にディスク上にある全ページ」であるときには意味を持たない。有効なままだと全リンクがその分岐を通り、`<primary_lang>` にしか存在しないページへの他言語ページからのリンクが「翻訳ページ未作成」の WARNING を出さずに黙って通ってしまう（このモードが出しうる 2 種類の WARNING の片方が原理的に出なくなる）。`status: removed` ページへのリンクは通常の存在確認経路が同じ ERROR を出す。従来は `OK: 0 files checked, 0 errors, 0 warnings` を出して終了コード 0 で終わっており、**正常なチェックの成功と区別がつかない出力**だった（他の多くのスクリプトは引数なしで全ファイルを対象にするため、このスクリプトだけが逆の挙動でもあった）。`--deleted` は引数なしモードでは空のまま — 「この変更でこれらのファイルが removed になる」という意味は差分の中にしか存在せず、差分の外に対応物が無い。既に `status: removed` を持つページは従来どおり `--changed` 側から辿られる。引数なしモードでは、**自身が `status: removed` のページはリンク元として検査しない**（Issue #976）— 公開されないページの発リンクは何も壊さず、報告しても誰も二度と編集しないので消えない所見になる（A を削除した後で A が指す B を削除すると、以後 A に ERROR が残り続ける）。`wikicommit-merge` は常に `--changed` を渡すため、差分スコープの挙動は変わらない

### 処理フロー

1. `--changed` の各ファイルから `[[Type/slug]]` パターンを抽出する
2. 各 WikiLink について以下を検証する:
   - `<lang>` の決定: チェック対象ファイルの `lang` フィールドを基準言語とする
   - 参照先の解決順序（`[[Type/slug]]` に lang は含まれないため以下の順で検索）:
     1. `.wikicommit/entity/<lang>/<Type>/<slug>.md` が存在すれば OK
     2. 上記が存在せず、`.wikicommit/config.yml` の `primary_lang` での `.wikicommit/entity/<primary_lang>/<Type>/<slug>.md` が存在する場合 → WARNING のみ（翻訳ページ未作成）
     3. いずれの言語にも存在せず、**同じ slug のページが別の Type に実在する** → **ERROR**（Issue #563。実在する Type を名指しする。詳細は下記）
     4. いずれの言語・いずれの Type にも存在しない → **WARNING**（Issue #340。旧 ERROR。ブロックすると LLM・人間の双方が「まだ無い概念は WikiLink 化せず地の文のまま書く」を選びがちになり、複数ソースで繰り返し言及される一般概念がページ化されないまま埋もれる問題があったため緩和した。集計は `check_wanted_pages.py` が別途担う）
   - 参照先ページの `status` が `removed` か → removed の場合は ERROR（変更なし。CLAUDE.md の orphan 検出の非対称設計が指す、削除フローの順序制約回避のための意図的なブロック）
   - 例外: `--changed` 内に同じ `<lang>/<Type>/<slug>` で新規追加されるファイルが存在する場合は上記 ERROR / WARNING としない（同一コミット内の新規追加ページへのリンク）
3. `--deleted` が指定された場合、削除対象ページへの被リンクを `.wikicommit/entity/` 全体から検索する → 残存する被リンクがあれば WARNING

#### WikiLink の形

> **別名付きの形を受け付け、形の合わない `[[...]]` を報告するようにした（Issue #1304、2026-10-16）**: それまで `WIKILINK_RE` は `[[Type/slug]]` だけに合い、`[[Type/slug|表示名]]` などそれ以外の `[[...]]` は変換・未解決 WARNING・被リンク・削除済みページの ERROR・統合時の書き換え・Pass 4 の 1 ホップ近傍のどれにも掛からず、どこにも報告されなかった。Issue #1290 の調査中に見つかり、比較実験で生成が実際に別名付きの形を書いた。パイロット `wikicommit/ai-driven-dev-wiki`（`cfdc0f3`）の entity と view に 26 件（16 ファイル、うち 13 が翻訳ページ）あり、26 件すべてが別名付きだった。他の 4 パイロットには 0 件。禁止して Pass 3 と翻訳に書かせない案（b）も検討したが、AI が自然に書く形であり、翻訳では表示名を訳したくなるため禁止しても再発しやすいとして、メンテナが受け付ける案（a）を決めた。表示名はグループ 3 として末尾に足し、`findall` で 2 要素を受けていた 4 本（`check_orphans.py`・`check_wikilinks.py`・`check_wanted_pages.py`・`build_survey_view.py`）は `extract_wikilinks()` に替えた。形の合わない `[[...]]` を WARNING にしたのは、Issue #340 と同じく ERROR にすると地の文に逃げる方向に働くため。

#### Type セグメントの取り違え

`[[Type/slug]]` は Type セグメントと slug の**両方**が一致して初めて解決するため、slug は合っているが Type だけを間違えた WikiLink は「参照先が存在しない」として扱われる。しかし実体はリポジトリに在るので、正しい対処は新規ページの作成ではなく**リンク 1 語の修正**であり、上記 4.（Issue #340 の WARNING）とは行動が正反対になる。両者はメッセージ上まったく区別がつかず、`check_wanted_pages.py` に至っては「これから作るべきページ」として提示してしまう（そのとおりに作れば内容の重複した 2 ページができ、`check_orphans.py` の重複判定は `type` が違うため検出しない）。

- **Issue #340 の緩和と衝突しない**: #340 が ERROR を避けた理由は、ブロックすると書き手が「まだ無い概念は WikiLink 化せず地の文で書く」という回避行動を取り、繰り返し言及される概念がページ化されないまま埋もれることにあった。このケースにはその回避行動が存在しない — 参照先は既にページを持っており「まだ無い概念」ではないため、WikiLink 化をやめる動機が生まれない。実在しない slug への WikiLink は WARNING のまま変わらない。

### 終了コード

Issue #340 で「参照先ページが存在しない」ケースを ERROR から WARNING に変更したため、blocking ケースは一度 `status: removed` へのリンクのみになった。Issue #563 でそこに「別 Type に同名 slug が実在する未解決 WikiLink」が加わっている。終了コードの仕組み自体（`total_errors > 0` で `1`）は一貫して変更していない。

## check_raw_html.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 203 → 202、コード 93 → 93、docstring 66 → 66、コメント 16 → 15、空行 28 → 28（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 3 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 未レビューのまま自動マージ・公開されたページの `<script>` / `<iframe>` が人のレビューより先に読者のブラウザで実行される穴を、マージ時の blocking なゲートで塞いだのは Issue #377。docstring の「an allowlist is exactly the sanitize-list design this Issue chose not to build」の「this Issue」はこの番号を指していた（いまは「this script」と書く）
- どこを生 HTML と数えるかを CommonMark のパーサー（`markdown-it-py`）の生 HTML トークンで決めるのは Issue #1322
- view ページの本文も同じ生 HTML の禁止に掛けるのは Issue #675

Issue #1322（2026-10-15）: 判定をコードの範囲の正規表現（`FENCE_RE` と `INLINE_CODE_RE`。前者は 3 文字の区切りで開いて同じ 3 文字の行で閉じる形、後者は 1 文字のバッククォートで囲む形だけを読んだ）でコードを空白に塗りつぶしてから `<tag ...>` を探す 2 段構えから、`markdown-it-py` の生 HTML のトークンで判定する形に改めた。旧 regex は区切りを常に 3 文字として扱い、閉じる記号の前の字下げを許さず、インラインコードを 1 文字のバッククォートでしか認識しなかったので、(1) 4 文字のフェンスの中の 3 文字の行、(2) 字下げ 3 の閉じるフェンス、(3) `~~~~` の中の `~~~`、(4) 2 文字区切りのインラインコードのそれぞれの後ろに置いた `<script>` を検出しなかった。Quartz が使う micromark 4.0.0（`allowDangerousHtml: true`）では 4 つとも `<script>` がそのまま出力されることを確かめている。regex を直して追いかける案と、依存を増やさず行ごとのパーサを自前で書く案は、CommonMark の規則（リスト内・ブロック引用内のブロックなど）を 1 つずつ再現することになり、ずれが残るたびにゲートに穴が開くので採らなかった。依存を避けたい事情が出てきたら再検討する。

この変更で期待値が変わったもの: 閉じていないフェンスの後ろの HTML は、旧 regex が一致しなかったため検出されていたが、CommonMark では文書の末尾までコードなので検出しなくなった（描画もコードになる）。旧 `HTML_TAG_RE` が読めなかったハイフンを含むタグ名（`<my-el onmouseover=...>`）は検出するようになった。旧 docstring・本文が既知の限界としていた「`a<b>c` のような不等式の誤検知」は、CommonMark 自身がタグとして読み描画するものなので、誤検知の扱いから外した。

## check_orphans.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 171 → 168、コード 108 → 108、docstring 33 → 30、コメント 1 → 1、空行 29 → 29（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 2 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- view ページを孤立の報告から外しつつ、そのリンクは被リンクに数えるのは Issue #675
- ORPHAN 行にページの `sources` の短い識別子を添えるのは Issue #570。docstring は、`wikicommit/saitama-city-wiki` の監査で孤立 6 ページはすべて他にページを 1 つも生まなかったソースから来ており、対象の全体の構造を扱う 2 つのソースから来たページはどれも到達可能だったこと、それが 1 リポジトリの観測でありかつ部分的に自己成就的（構造を扱うソースは定義上すべてにリンクする）なので所見ではなく仮説であることを書いていた（いまは仮説の中身と、出所を出すことがそれを確かめられるようにする、とだけ書く）

### 定義

`ORPHAN:` 行にはそのページの `sources`（`path`／`url`／`author`）を添える（Issue #570）。孤立の次に問う価値があるのは「どのソースが作ったか」であり、`wikicommit/saitama-city-wiki` の監査ではorphan 6 件すべてが「他に 1 ページも作っていないソース」由来である一方、対象全体の構造を述べる 2 ソース由来のページは全域で到達可能だった。ただし 1 リポジトリの観察であり、構造を述べるソースは定義上あらゆるページにリンクする側なので半ば同語反復でもある — **検証すべき仮説**であり、出自を印字することがそもそも検証を可能にする。`sources` を持たないページは `(no sources)` と出す。

## check_wanted_pages.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 125 → 124、コード 64 → 64、docstring 23 → 23、コメント 23 → 22、空行 15 → 15（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 6 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 書かれていないページへのリンクを `check_wikilinks.py` が ERROR から WARNING に下げたのは Issue #340。下げたことで、多くのソースから参照される概念がどこにも単独では現れなくなり、このスクリプトがその見え方を取り戻した
- TYPE_MISMATCH を WANTED から分けたのは Issue #563
- 素の文字列でしか言及されない概念が見えない限界は Issue #318
- ページの走査を共有したのは Issue #677。Type の索引を参照元にも裏付けのファイルにも数える扱いは共有する前のままにした。コメントは、古くなった索引の項目を「誰かがこのページを書いてほしい」に数えるべきかは走査をまとめることとは別の問いだから元のままにした、と書いていた
- view ページを両側に数えるのは Issue #675

### 目的

`.wikicommit/entity/` 全体を走査し、`[[Type/slug]]` で参照されているが、どの言語にも実体ページが存在しない slug（wanted page）を集計する。あわせて、実体が無いのは Type セグメントの取り違えが原因である（同じ slug が別 Type に実在する）ものを `TYPE_MISMATCH` として分離する（Issue #563）。`check_orphans.py` と対になる設計: orphan が「被リンクゼロのページ」を検出するのに対し、本スクリプトは「リンクはあるが実体がないページ」を検出する。Issue #340 で `check_wikilinks.py` の「参照先ページが存在しない」ケースが ERROR から WARNING に緩和されたことに伴い、その集計・可視化を担う。

### 処理フロー

既知の限界（Issue #318 に明記済み）: WikiLink 構文が一度も使われていない地の文言及（太字のみ等）は対象外。

## check_expires.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 75 → 75、コード 49 → 49、docstring 7 → 7、コメント 3 → 3、空行 16 → 16（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- view ページも `expires_at` を他のページと同じ条件で持ち、両方のツリーを確かめるのは Issue #675

## check_translation_status.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 175 → 174、コード 107 → 107、docstring 30 → 29、コメント 13 → 13、空行 25 → 25（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 4 → 0（`pre-Issue-#477` の形の参照も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- pathspec に `:(literal)` を付けるのは Issue #369（Issue #115 と同じ修正）
- view ページも翻訳の対象として走査するのは Issue #675
- コメントは `.wikicommit/wiki/` から `entity/` への改名（Issue #477）より前の値を「pre-Issue-#477 の値」と呼んでいた

> **命名の経緯（Issue #280）**: 当初 `check_translation_freshness.py` という名称だったが、「freshness（陳腐化）」は「存在するものが最新か」を問う語であり、`STALE`（翻訳はあるが原文更新に追従していない）・`MISSING_SOURCE`（翻訳はあるが原文が消えた）はこの定義に収まる。一方で本 Issue が追加した `UNTRANSLATED`（そもそも翻訳が1つも存在しない）は「存在するかどうか」という別種の問いであり、`freshness` という名前がこれを検出するのは実態と合わないため `check_translation_status.py` に改名した（分割ではなく改名を選んだ理由は、ページ走査ロジックの重複を避けるため）。

## check_derivation_freshness.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 121 → 120、コード 66 → 66、docstring 27 → 26、コメント 9 → 9、空行 19 → 19（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 3 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- pathspec に `:(literal)` を付けるのは Issue #369（Issue #115 と同じ修正）
- `derived_from` を持つページを view ツリーに書くのは Issue #675（コメントは「Issue #675 以降そこに書かれる」と書いていた）

### 目的

`wikicommit-synthesize`（Issue #283）が出力したページの `derived_from`（`{path, source_commit}` の配列）各エントリについて、出自ページの `source_commit` と現在 HEAD コミットを比較し、陳腐化した合成ページを検出する。`check_translation_status.py` の `STALE`/`MISSING_SOURCE` ロジック（単一の `translated_from`/`source_commit`）を配列用に切り出した新規スクリプト（既存スクリプトの改修ではなく新設。翻訳陳腐化スクリプトへの改修依存を作らないための設計判断）。

## check_ingest_freshness.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 160 → 160、コード 96 → 96、docstring 23 → 23、コメント 12 → 12、空行 29 → 29（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 3 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `_frontmatter.py` への集約（読む側だけ）は Issue #231。コメントは、`status:` を書き換えるための `FRONTMATTER_RE` をその集約の範囲外と書いていた（いまは `_frontmatter.py` の範囲外と書く）
- `retracted` は Issue #737。`reconcile_ingest_status.py` の対象に `outdated` が無いことは Issue #474

## read_policy.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 151 → 147、コード 52 → 52、docstring 65 → 61、コメント 17 → 17、空行 17 → 17（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 3 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #844。docstring は、それまで判定は 2 つの SKILL.md の 4 か所で繰り返された 1 文が行っており、どれも読んだばかりの本文が「still the shipped comment」かを LLM に判断させていたと書いていた
- docstring は、それを Issue #474 が名指しした形（完全に決定論的な操作を指示として書く）と呼んでいた
- 誤読は書くべきページを抑える側にだけ倒れることについて、docstring は、あるパイロットがすでにその向きに進み `Person` のページが 1 つも無くなったと書いていた
- `strip_frontmatter()` が正規表現を使わず `_frontmatter.py` に任せる理由（そのモジュールの docstring が挙げるもの）は Issue #212

### 目的

`.wikicommit/source-policy.md` と `.wikicommit/entity-policy.md` は、本文全体をコメントアウトした記入例として配布される。設計（`docs/DesignDoc-data.md` §3.4・§3.5）は「本文が空・またはテンプレートのコメントのままなら散文方針は無いものとして扱う」と定めていたが、**その判定を行っていたのは 2 つの SKILL.md に散った 4 箇所の同じ文**であり、いずれも「いま読んだ本文が配布時のコメントのままか」を LLM に判定させていた。

**これは Issue #474 が名指しした形である** — 完全に決定論的に判定できる操作を instruction として表現したことで、非決定論的な失敗モードを持ち込んでいた。配布した本文は手元にあるのだから、判定するものは何も無い。

**しかも誤りの向きが片側に寄っている**。両ファイルの記入例はすべて「除外を促す」内容（一次資料を優先する・個人ブログを取り込まない・非公人・実在の未成年者・係争中の事案）であり、誤適用は常に「書かれるはずだったものが書かれない」方向にしか働かない。`wikicommit/saitama-city-wiki` が `theme` による除外だけで `Person` 型 0 ページになり歴史上の人物 3 名まで巻き込んだ（§3.5）実例は、まさにその方向である。

### 判定規則 — 「HTML コメントは方針ではない」

両テンプレートは記入例を HTML コメントに入れており、どちらも「自分の方針を書いたらこのコメントを消せ」と本文自身が指示している。人が書く方針は普通の散文である。したがってコメントを除去し、残ったものが方針である。**この機能追加より前に初期化されたリポジトリにも移行は要らない** — そちらの本文もコメントだからである。

### 既知の限界

**方針をコメントの中に書いた場合は届かない**。上記の 1 つ目・3 つ目の `NONE:` がその状態を名指しするが、それを読むのは実行の出力であり、人が見ていなければ気づかれない。**配布時の記入例をその場で書き換えた場合（`<!-- wikicommit:example` を残したまま中身を書き換えた場合）と、誰も触っていない場合は、ディスク上で同じ形になるため区別できない** — どちらの版が配布したかに依存しない規則を採った以上これは原理的な限界であり、1 つ目の `NONE:` は区別できない旨を両方書く形にしてある。`check_distribution_freshness.py` に `UNTOUCHED:` 相当の所見を足す案は採らなかった — 両ファイルは `compare="frontmatter_keys"` で本文を見ない設計（Issue #712。本文はユーザーのものなのでバイト差分は常に点灯する）であり、しかも記入例のままであることは init 直後の**大半のリポジトリで正常な状態**なので、足せば常時点灯する所見になる（Issue #562 が読まれなくなると警告した形）。

**`config.yml` は対象外**。コメント 25 行は純粋に人間向けで、LLM が使うのは `theme` / `primary_lang` / `max_retries` / `base_types` の**値だけ**である。値だけを返すスクリプトに委譲すれば約 470 トークンが消えるが、効果が小さい一方で読む Skill がほぼ全部なので変更面積が最大になる。**そして本 Issue が扱ったのは量ではない** — `config.yml` のコメントは方針として誤適用されうる散文ではないため、同じ欠陥を持たない。

## match_index_only.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 187 → 183、コード 98 → 98、docstring 59 → 55、コメント 8 → 8、空行 22 → 22（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 5 → 0。出力する文字列には `#NNN` は無い。ただしこのスクリプトは `argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])` でモジュールの docstring の 1 行目を `--help` に出すため、1 行目から `(Issue #1032)` を外したことで `--help` の説明文も変わった（照合と出力そのものは変わらない）。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #1032。それまでは照合を 2 つの SKILL.md（`wikicommit-collect` の step 5 と `wikicommit-generate` の step 0）の散文で行い、その規則がパスを捨てていたため、どの項目もホスト全体を意味していた。docstring は、散文の 2 つの写しが別々にずれていく形を Issue #474 が名指しした形（決定論的な操作を指示として書く）と書いていた
- `index_only:` は Issue #570
- パスやクエリを持つ項目は、Issue #1032 より前はホスト全体を意味し、いまはその 1 ページを意味する。docstring は、公開パイロットにそうした項目を持つものは無かった（2026-09-25 に確認）こと、持っていた利用者には CHANGELOG.md がそう書いていることを書いていた

### 目的

`.wikicommit/source-policy.md` の `index_only:` に URL が該当するかを判定する（Issue #1032）。エントリは 2 形あり、形が意味を決める — パスが無ければ**ドメイン**（そのホスト全体）、パスがあれば**ページ**（その 1 ページ）。従来この照合は `wikicommit-collect` Step 5 と `wikicommit-generate` Step 0 の散文が行っており、規則はパスを捨てていた。規則が 2 形に増えると 2 か所の散文が別々にずれる余地が大きくなるため、決定論的な照合をここに 1 つだけ置く（Issue #474）。設計判断の全体は `docs/DesignDoc-data.md` §3.4「`index_only`」。

## match_existing_names.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 145 → 145、コード 94 → 94、docstring 36 → 36、コメント 1 → 1、空行 14 → 14（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #1096

### 目的

Pass 2c が `action: update` にするのは「型と slug が同じ既存ページがある」ときだけだった。したがって、既存ページが**別名**として持つ名前で別のソースがその概念を呼ぶと、新しいページが作られる（`wikicommit/ai-driven-dev-wiki` の `function-calling` と、別名 "Function calling" を持つ `tool-use-design-pattern` の並存。Issue #1096）。型テンプレートの「別名は別ページにせず `aliases` に書け」は書く側の規則であり、照合する側に対応する規則が無かった — 片側にしか書かれない境界は片側にしか効かない（Issue #550 と同じ形）。

照合は決定論的に書けるので、指示文ではなくスクリプトにした（Issue #474）。副次的に、既存ページの別名を LLM のコンテキストへ載せる必要も無くなる。

### 終了コード

**既存の重複ページへの遡及は行わない**。既に並存しているページは、人が統合するまで残る。

## check_distribution_freshness.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 722 → 719、コード 389 → 389、docstring 169 → 166、コメント 89 → 89、空行 75 → 75（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 13 → 0（`Issue` の付かない `(#950)` も外した）。出力する文字列には `#NNN` は無い。ただしこのスクリプトは `argparse.ArgumentParser(description=__doc__)` でモジュールの docstring を `--help` に出すため、docstring から経緯を外したことで `--help` の説明文も変わった（判定と出力そのものは変わらない）。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- リポジトリが持つものを 3 種類に分け、WikiCommit 自身の配布物を利用者の持ち物と分けたのは Issue #712。それまでは 2 種類目を 1 種類目と同じに扱っていたため、1 版前に init したリポジトリは古いワークフロー・古いプラグインの `dist/`・古いビルドスクリプトを黙って使い続け、気づくにはクローンして手で diff するしかなかった
- Skill ツリーを `.agents/skills/` にも探すのは Issue #1021。それまでは `.claude/skills/` だけを見ていたため、Codex だけに入れたリポジトリで「wikicommit-init is not installed」とすべて 0 の要約が出た
- `.wikicommit/scripts` の `OUTDATED` 行にだけ帰結を添えるのは Issue #930。帰結だけを述べて止めるのは Issue #935 — それまでは末尾に「Run /wikicommit-update.」があった
- variant を `quartz.config.yaml` と `deploy.yml` の有無から読むのは Issue #335
- `config.yml` の `wikicommit_version` は Issue #577 で書くようになった
- 識別子の候補を `source` 以外に推測しないのは、消費者の無い受け皿（Issue #553）になるため
- リストの要素を識別子で比較すること（`_list_element_paths()`）と、`quartz.config.yaml` の値の検査（`_quartz_value_findings()`）は Issue #950。リストの手前で止まっていたときは `plugins` の 47 件が 1 つのパスに潰れ、メンテナが「検出されない」と挙げたドリフト 5 件のうち 4 件がこの形だった。5 件目の `comments`（Issue #755）は 3 つのパイロットのうち 2 つで欠けていたが、誰も書き留めていなかった。要素のマッピングの中に降りない理由に挙げた giscus について、docstring は「それを有効にすることこそ、そのプラグインを出荷した Issue の目的だった」と書いていた
- `pageTitleSuffix` が `configuration` の下に入ったのは Issue #679
- `.claude/settings.json` の比較（`_json_keys()`）は Issue #953

### 目的

Issue #712 以前は 2 番目が 1 番目と同じ扱いだったため、1 つ前の版で init したリポジトリは古い workflow・古いプラグイン `dist/`・古いビルドスクリプトを黙って使い続け、それを知る手段は clone して手で突き合わせることしか無かった（パイロット 3 件が実際に同一の旧版を抱えていた）。init 側は Issue #712 で更新されるようになり、本スクリプトは**そのリポジトリが更新を要するかを見る側**を担う。

**分類表は持たない**。どのパスがどの扱いかは `.claude/skills/wikicommit-init/scripts/_root_outputs.py` の `update` 列が唯一の情報源であり、`init.py` のコピーと `print_next_steps.py` の `git add` 案内も同じ列から導かれる。ここに 2 つ目のリストを持つことは、その列が消したドリフトを作り直すことになる（Issue #642 と同じ理由）。

### 使用場面

- `wikicommit-generate` / `wikicommit-merge` Skill：Step 0（`--only .wikicommit/scripts`。実行開始時の版ずれ検査。Issue #930。下記コールアウト）

### コマンド

`--only <path>` は `_root_outputs.py` の 1 エントリだけに絞る（下記コールアウト）。**`--only` の値がどのエントリにも一致しない場合は `WARNING:` を出す** — 黙って 0 件を返すと、打ち間違いが「差分なし」と区別できなくなり、このフラグが捕まえようとしている silent wrong answer をこのフラグ自身が作ることになる。**実在するエントリでも、このスクリプトが比較しないもの（`update: skip`・テンプレートを持たないもの）を名指した場合は同じく `WARNING:` を出す** — 出力は文字どおり同じ「クリーンな `SUMMARY:`」であり、区別する材料が読み手に無いため（`quartz_pages` 変種では 9 エントリがこれに当たる）。したがって呼び出し側は `OUTDATED:` だけでなく `MISSING:` / `ORPHAN:` / `WARNING:` も報告する（両 SKILL.md がこれを明記する）。あわせて `--only` 指定時は `VERSION:` 行を出さない（下記「使えない判定が 1 つある」のとおり `synced` は再 init しただけのリポジトリで古いまま残るため、全体レポートの中でバイト比較と並んでいるぶんには無害だが、1 行だけの検査では最も目立つ出力が誤っていることになる）。

> **2 つの配布物の版ずれを、実行の開始時に見る（Issue #930）**: WikiCommit がユーザーのリポジトリに置くものは 2 つあり、**別々のコマンドで更新される** — 指示書（`.claude/skills/`）は人間が `npx skills add` を叩き、道具（`.wikicommit/scripts/`）は `/wikicommit-update` または `/wikicommit-init --no-overwrite` が更新する。片方だけ更新すると「新しい指示書 ＋ 古い道具」になる。
>
> **問題はエラーが出ないことではなく、出たエラーが原因を名指ししないことである**。版ずれの現れ方は 3 通りで、危ないのは 3 番目だけである:
>
> | 指示書が変わった内容 | 古い道具の反応 |
> |---|---|
> | 新しいオプションを付けて呼ぶ | `unrecognized arguments` で落ちる → その場で分かる |
> | 新しいスクリプトを呼ぶ | ファイルが無い → その場で分かる |
> | **既存のオプションの参照先だけが変わった** | **落ちるとは限らず、落ちても見当違いの場所を指す** |
>
> Issue #925 がちょうど 3 番目だった — `record_run.py --token` はオプション名も引数の形も変わらず、**中で見に行くディレクトリだけが `passes/` から `references/` へ変わった**（Issue #911）。古い `record_run.py` は存在しない `passes/` を見て `token: missing` を書く。その値の意味は「このエージェントは手順を読まずに走らせた」であり、**正しく読んだ実行を失敗側として記録する**。誤りの向きが Issue #797 の設計（打たなければ「実行されていない」と報告され、逆は起こらない）と逆になる。
>
> **検出器は新しく作らない。`check_distribution_freshness.py` が既にこれを見ている。** そして重要な性質として、**この検出は自分自身が古くても正しく報告できる** — 比較の基準（`_root_outputs.py` とテンプレート本体）がどちらも新しい側にあるためである。一般化すると次のようになり、これが「新しい検出を足さない」ことの根拠になる:
>
> | スクリプトの性質 | 自分の陳腐化を診断できるか |
> |---|---|
> | 特定の期待（定数・パス・フォーマット）を埋め込んでいる | **できない**。古い版は新しい期待を知らない（#925 の `record_run.py` がこれ） |
> | テンプレートと突き合わせる generic な比較 | **できる**。基準が新しい側にあるため |
>
> 前者は 1 つ増えるたびに穴が 1 つ増える一方、後者は 1 本あれば全部を覆う。したがって残る論点は**いつ走らせるか**だけだった。
>
> **呼ぶのはテンプレート側の写しであり、`.wikicommit/scripts/` の写しではない**（両 SKILL.md がこれを明記する）。後者は**まさに古いかもしれない半分**であり、そこから呼ぶと `--only` が `unrecognized arguments` で落ちて、検出器自身が上表の 1 行目になる。テンプレート側の写しはそれを呼ぶ SKILL.md と常に同じスナップショットから来る（両方 `npx skills add` が更新する）ため、版ずれの影響を原理的に受けない。`/wikicommit-update` Step 2 が別の理由（古いリポジトリには `.wikicommit/scripts/` 側が無い）で同じフォールバックを既に持っており、形はそれと同じである。**一般則として、検出器もそれを呼ぶ指示も `npx skills add` が更新する側に置く。**
>
> **この規則は「ゼロ surface 案」を排除する**。書き込み系 4 Skill はいずれも冒頭で `record_run.py start` を呼ぶため、そこに検査を入れれば SKILL.md を 1 行も増やさずに 4 つを覆えるように見える。しかし `record_run.py` は古い側にあるので、版ずれしたリポジトリではその呼び出し自体が存在しない — **古い半分に同梱された検出器は、必要なときに限って発火しない。**
>
> **止めない。警告に留める**（`wikicommit-generate` の `review-rules.md` 検査〈Issue #888〉が停止するのとは強度が違う）。あちらが停止するのは帰結が既知かつ全面的（ルールを読まないレビューが「レビューした」と主張する記録を書く）だからである。こちらは**差分があること**は分かっても**その差分が今回の実行に効くか**が機械には分からない。版ずれの大半は無害（無関係なスクリプトにオプションが 1 つ増えただけ等）であり、そこで generate を止めるのは防ごうとしている失敗より悪い。上表の 3 番目だけは停止に値するが、**それを見分ける手段が無い**というのがこの判断の全体である。
>
> **対象は `wikicommit-generate` と `wikicommit-merge` の 2 つとする。** 選定の基準は依存するスクリプトの本数ではない（実測では status 18・generate 10・collect / synthesize 6・merge 5・translate 4 であり、generate は書き込み系で最多だが決定的な差ではないうえ、単純な引数で 10 本呼ぶことは構造化された引数で 1 本呼ぶより版ずれに弱くない）。採ったのは**位置**である:
>
> | Skill | 選ぶ理由 |
> |---|---|
> | `wikicommit-generate` | 主経路の**最も早い地点**。中断コストがほぼゼロで、#925 の実害（誤った実行記録が書かれる）より前に止まれる。`--token` / `checkpoint` という期待を引数に埋め込む呼び出しを持つ唯一の Skill でもある |
> | `wikicommit-merge` | **全書き込み経路の合流点**。`fix` / `remove` / `review` / `translate` / `synthesize` / `reconcile` はすべて最後にここへ来る。かつ品質ゲート 4 本を走らせる、既定ブランチ手前の最後の門である |
>
> **残りを外す理由は「依存が薄いから」ではなく「全部 merge に合流するから」**であり、この形なら後から「なぜ他は入れないのか」に答えられる。merge 側の版ずれの誤りの向きは generate 側と逆である点は記録しておく — 古い品質ゲートは**落とすべきものを通す**（偽陰性）のであって、#925 のように正しいものを失敗と記録する（偽陽性）のではない。どちらも実害だが、同じものではない。
>
> **代償を 2 つ引き受ける**。(1) generate → merge を続けて叩くセッションでは同じ検査が 2 回走る（同じ答えを 2 回出す）。黙っている場合は何も出力しないため実害は薄い。(2) merge 側の警告は作業が終わった後に出るため、そのバッチは版ずれ下で走り終えている — 止めない設計なので致命的ではないが、早い側の generate を同時に入れる理由でもある。
>
> **`--only` は速度のためではない**（実測: 全体で 0.113 秒、`quartz-plugins` の 327 ファイル / 4.9MB の片側読みで 0.044 秒。LLM 推論の隣では無視できる）。絞る理由は**報告の関連性**である。実行開始時に `quartz-plugins`・workflow・`*.cjs` の版ずれを報告しても、読み手は**いまその場で何もできない**（帰結は公開サイトと CI であって今回の実行ではない）。`review` 側（`config.yml`・`schema/`）に至っては差分があるのが正常な場合すらある。hot path に出す行を「今回の実行の指示が誤りうる」ものだけに絞らないと、Issue #562 / #864 / #867 が警戒した力学が**検査の頻度ではなく報告の側**で起きる — 読まれない行が 1 本増える。
>
> **帰結を述べる文は `.wikicommit/scripts` にのみ付ける**。全 `OUTDATED:` 行に共通の接尾辞として足すのは誤りで、`quartz-plugins` の帰結は「公開サイトが古い」であって「記録が誤る」ではない。パス固有の分岐は同じ関数に前例がある（`entry.path == "quartz-plugins"` の dev-artifact 除外）。
>
> **その文は帰結を述べて終わり、対処のコマンドを名指ししない（Issue #935）**。当初は `Run /wikicommit-update.` で締めていたが、この検査を走らせるのは 4 Skill・6 行で、**うち 3 行を `/wikicommit-update` 自身が持つ** — Step 2 の 2 行（本体とフォールバック。論理的には 1 箇所）では冗長であり、Step 7 に至っては**いま走った更新が効かなかったことの報告**なので、そこで同じコマンドを勧めることは失敗した操作の再試行を指示することになる（Issue #930 が消そうとした「出たエラーが原因を名指ししない」形が、規模を小さくして残っていた）。帰結の前半は 4 呼び出し元すべてで正しいまま残り、対処の指示は各 SKILL.md が文脈付きで既に持つ（`status` は Step 11 の説明文、`generate` / `merge` は Step 0 の段落、`update` は自分がその操作である）。**`--only` でのゲートと `--caller` フラグは退けた** — 前者は `--only` を付けない `status`（案内は正しい）と `update` Step 7（案内は誤り）が同じ側に落ちるため条件として成立せず、後者は 1 文の分岐のために受け皿を配ることになる（Issue #553）。`tests/test_check_distribution_freshness.py` が、行が帰結を述べることと**コマンドを名指ししないこと**の両方を固定する。
>
> **`VERSION: synced=` を版ずれの信号に使ってはならない**（下記「使えない判定が 1 つある」）。`synced` を書き換えるのは `/wikicommit-update` だけで、`/wikicommit-init --no-overwrite` は `.wikicommit/scripts/` を必ず更新する（Issue #647）一方 `config.yml` は wholesale でスキップする（Issue #713）。**再 init で正しく同期したリポジトリでも `synced` は古いまま残る**ため、ずれていないのにずれていると報告する。バイト比較にはこの誤検知が無く、同一版内の未リリース差分まで捉えるぶん厳密に強い。
>
> **開発リポジトリでは再現できない**。ここでは `.wikicommit/scripts` がテンプレートへのシンボリックリンクであり、2 つの半分が文字通り同じファイルなので**構造上ずれようがない**。実際 Issue #925 も踏んで見つかったのではなく PR レビューの推論で見つかっている。この失敗クラスが surface する経路は「利用者の環境」か「レビューでの推論」の 2 つに限られるため、機械的な検出を持つ価値は通常より高い側にある。`tests/test_check_distribution_freshness.py` の該当テストが一時ディレクトリに実ツリーを組み立てるのはこのためである（リポジトリ自身に対しては版ずれを作れない）。
>
> **既存リポジトリへの遡及は行わない**（本ドキュメント群が繰り返し採る「新旧混在を許容する」方針）。変更が届くのは次に Skills を更新したリポジトリからである。**予防の側は README が既に持つ**（Issue #925 が `README.md` / `README_ja.md` の Installation に Updating later として追加済み）が、それだけでは足りない — **README を読むのはインストールする人であって、そのリポジトリで後から `/wikicommit-generate` を叩く人ではない**。無人実行・サブエージェント経由ならそこに読む人がそもそもいない。

### 比較の仕方（`update` 列ごと）

常に出ている警告は読まれなくなる — Issue #562 が低情報密度ガードを blocking から降格した理由がまさにこれであり、差分検出全体が無視されるようになればこの仕組みが機能しない。したがって `review` は**加算的なシグナルでのみ報告する**: テンプレートにあってローカルに無いもの。値を変えたこと・散文を書き換えたことは報告しない。

> **`lines` の簡約は `_root_outputs.py` 側にも写しがある（Issue #873）**。`init.py` / `print_next_steps.py` が「このリポジトリの `.gitignore` に WikiCommit のパターンが揃っているか」を判定するのに同じ包含判定を要するが、**Skill 内スクリプトから `.wikicommit/scripts/` を import することはできない**（`add_source.py` が同ディレクトリからの import を 1 つも持たない設計制約と同じ。`docs/DesignDoc-skills.md` §11.5）。`remove_page.py` が `normalize_entity_prefix()` を複製しているのと同じ扱いとし、2 つの写しを許容する。**簡約そのもの（空行とコメントを落とす）は同一だが、2 つは同じ答えを返す関数ではない** — `_root_outputs.py` 側は (1) 報告が対処の手順を兼ねるため行の順序を保ち、(2) **variant に応じて `gitignore-quartz.txt` も要求集合に含める**（`content/` / `.quartz-cache/` / `quartz/public/`）。こちら側は下記「既知の限界」のとおり `templates/.gitignore` しか見ないため、`--quartz` リポジトリで Quartz 側のパターンが欠けていても `OUTDATED` にはならない。片方を他方に寄せて統合しないこと。
>
> **キーの比較は再帰的に行う（ドット区切りのパス）**。Issue 本文は「トップレベルキー」としていたが、同じ Issue が挙げている実例 `pageTitleSuffix`（Issue #679）は `configuration:` の下にある。`quartz.config.yaml` のトップレベルキーは `configuration`/`layout`/`plugins` の 3 つで今後増えないため、トップレベルのみの比較では**この機能が意図した用途に対して恒久的に何も報告しない**。
>
> **テンプレート側の `{NAME}` プレースホルダーは比較前に無害化する**。YAML はクォートされていない `{THEME}` をフロー マッピングとして読むため、`theme: {THEME}` は「`theme.THEME` という入れ子キー」に見え、実際の値を持つ config.yml には当然そのキーが無い。無害化しないと、**init 直後のリポジトリが自分の `config.yml` と `quartz.config.yaml` を永久に `OUTDATED` として報告する**（実装中に clean init に対して実行して発見した）。`options: {}` のような本物の空マッピングは正規表現に一致しないためそのまま解釈される。**置換先は空文字列ではなく素のスカラー**にする — プレースホルダーは常に裸で書かれているとは限らず、`config.yml` の 1 行目は `wikicommit_version: "{VERSION}"` とクォートの内側にあるため、`""` で置換すると引用符が 4 つ並んで**テンプレート全体が YAML として読めなくなる**。そうなるとテンプレート側のキー集合が空になり、`テンプレート − ローカル` も空になるので、**`config.yml` は上流で増えたキーを永久に報告しない** — 比較が止まっているのに正常な結果に見える。なお、テンプレート側のパースに失敗した場合は `WARNING:` を 1 行出す（空のキー集合は「上流で何も増えていない」と見分けがつかないため）。
>
> **リストへも降りる — キーで止めると 47 プラグインが 1 本のパスに畳まれる（Issue #950）**。`_key_paths()` は当初「リストの中身はユーザーの値であってスキーマではない」としてマッピングのキーだけを辿っていた。実測すると `quartz.config.yaml` のキーパスは 61 本で、**うち `plugins` 以下は `plugins` の 1 本だけ**だった — プラグインの追加・削除・ローカルビルドへの差し替えも、`layout.byPageType.*.exclude` への項目追加も、**どれも既存リポジトリには一切報告されない**。手順書が「自動検出されない手作業」として挙げていた 5 点のうち 4 点がこの形であり、しかもその列挙自体が 1 点（`comments`。Issue #755）を取りこぼしたまま 3 パイロット中 2 件で欠落していた。**列挙ではなくリストそのものを比較するのが本則である**（案 B 単独を採らなかった理由。Issue #842 / #556 が繰り返した「列挙は 1 つ欠けると静かに落ちる」）。
>
> 降下には 3 つの制約があり、いずれも 3 パイロットの実クローンに当てて決まった。**起票時の草案が案 A（リストへ降りる）を退けた理由「ユーザーが意図的に消したエントリを毎回報告する」は、実測では 1 件も起きなかった** — このファイルで「ユーザーの内容判断」を持つリストは `configuration.ignorePatterns` の 1 本だけであり、実際に点灯するのは `exclude`（WikiCommit のコンポーネント名）と `plugins[].source` だからである。
>
> | 制約 | 内容 | 外したときに何が起きるか（実測） |
> |---|---|---|
> | 1 | **加算のみ**（テンプレート − ローカル） | 減算方向にすると、ユーザーが足したものを全部報告する |
> | 2 | **位置ではなく識別子で照合する**（スカラーは値そのもの、マッピングは `source` の値） | 上流がプラグインを 1 本足した瞬間に 47 件すべてがずれる |
> | 3 | **リスト要素のマッピングの内側へは降りない** | `enabled` を見ると giscus を意図的に有効化したリポジトリが誤検知になり（**その機能を入れた Issue #755 の利用者が最初の誤検知になる**）、`options` を見るとフッターの `{REPO_URL}` がテンプレート側でプレースホルダーのままなので**3 件とも必ず差分になる** |
>
> したがって `plugins` について見るのは**どのプラグインが在るか**だけで、`enabled` / `order` / `options` は見ない。**識別子は `source` のみとし、`name` / `id` を推測で足さない** — テンプレート群でマッピングのリストは `plugins` 1 本だけであり、2 つ目の候補は消費者のいない受け皿になる（Issue #553）。識別子を持たない要素は**比較せず飛ばす**（劣化の向きが「今日と同じ沈黙」であり、ノイズにはならない）。
>
> **変更したのは `_key_paths()` 1 関数で足りる。** 同関数は `yaml_keys` / `json_keys` / `frontmatter_keys` の 3 モードが共有するが、加算的比較はテンプレート側が持つものしか報告しないため、**テンプレート側にリストが無ければ挙動は 1 ビットも変わらない**。実測: `config.yml` はテンプレート側のリストが `schema.base_types`（11 件。`translation.targets` はプレースホルダーなのでスカラーになる）のみで 3 件とも完全一致＝誤検知 0、**上流が基本型を足したときに初めて報告されるという純増**になる。ポリシーファイル 2 つ（`frontmatter_keys`）は空リストのみ、`.claude/settings.json`（`json_keys`）はリストを持たないため、どちらも**変化なし**。`COMPARISONS` にも `_root_outputs.py` にも新しい値は要らない。

### ORPHAN は `overwrite` のツリーにのみ報告する

削除は行わない（本 Issue のスコープ外。誤検出時の被害が非対称に大きいため、削除は後続の update フローが人間の確認を取って行う）。

### 既知の限界

**`configuration.ignorePatterns` はこのファイルで唯一「ユーザーの内容判断」を持つリストであり、既知の誤検知候補である**（Issue #950）。ユーザーが `private` を公開したくて消した場合、既存の 1 行の中に 1 項目が増える形で点灯し続ける。それでも対象に含めるのは 3 つの理由による: (1) 3 パイロットの実測で 3 件とも一致しており現に発現していない、(2) `.gitignore` の `compare: lines` が既に同じ性質（ユーザーが消した行を報告し続ける）を受け入れている前例がある、(3) 除外すると小さな列挙を持つことになり、上流が `configuration` にリストを足したときに覆われない。

**ローカル側にしか無いエントリは、どの設計でも構造的に検出できない**（同）。`quartz.config.yaml` のフッターに残っている Discord 行がこれにあたる — 見るには減算比較が要るが、それはユーザーが足したものを全部報告する向きであり、上記の制約 1 が退けたものである。**1 行の手作業として残す**。プラグインの `enabled` / `options` の上流変更も同じく「今日と同じ沈黙」に留める（制約 3）。

`package.json` は `review` かつバイト比較のため（Issue #712 の分類表どおり）、**init 前から自前の `package.json` を持っていたリポジトリでは毎回 `OUTDATED` が出続ける** — `init.py` はその場合コピーをスキップするので、テンプレートと一致することが構造的にありえない。上記 5 ファイルと同じ「常時点灯」の形だが、扱いを変えていない理由は 2 つある: (1) 大半のリポジトリはテンプレートをそのまま受け取るため一致し、点灯が普遍的ではない（`.gitignore` は `--quartz` の全リポジトリで必ず点灯する点が決定的に異なる）、(2) この点灯は実際に行動を促す — Issue #556 は新しい `*.cjs` が `package.json` の `postinstall` から呼ばれず全 Pages ビルドが失敗した事例であり、「テンプレートの `package.json` が変わった」は取り込むべきものがあるという正しいシグナルである。

> **この保留は Issue #950 の実測で解消し、据え置きで確定した**。3 パイロットとも配布テンプレートと**完全にバイト一致していた** — 上記の限界は実在するが未発現である。さらに、加算的比較へ移すと **Issue #556 の再発を検出できなくなる**: あれで変わったのは `scripts.postinstall` の**値**であり、加算的比較には原理的に見えない。両者を貫く軸はこう置ける — **ローカルが設計上テンプレートから乖離するファイルは加算的に、テンプレートが全体にわたって正本であるファイルはバイトで比較する**。`quartz.config.yaml` が前者、`package.json` が後者であり、同じ Issue で片方だけを動かしたのはこの軸に従った結果である。

## search_index.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 493 → 493、コード 273 → 273、docstring 109 → 109、コメント 51 → 51、空行 60 → 60（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 9 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- タイトルのヒットを本文のヒットよりはるかに重くすること、スニペットを一致箇所の前後約 32 文字にすること（`SNIPPET_MAX_TOKENS = 64`）は Issue #126 の仕様として書いていた
- `aliases` をタイトルと同じ重みにするのは Issue #1078
- view ページを entity ページと一緒に索引に入れるのは Issue #675。合成の根拠集合から view ページを外したのは Issue #674 で、それは検索には及ばない
- 位置引数の語を FTS5 の暗黙の AND で並べるのではなく、`--expand` のグループを「グループ内 OR・グループ間 AND」で組むこと、短い語が残るグループと残らないグループで警告を分けることは Issue #581
- 3 文字未満の語がどこにも一致しないことを知らせるのは Issue #274

### `build` サブコマンド

**fingerprint**（Issue #1061）: `collect_pages()` と同じページ集合（entity ＋ view、`assets/` と `index.md` を除く）について、`(パス, st_mtime_ns, st_size)` を 1 行ずつ並べた列の SHA-256（先頭にインデックスの形式番号 `INDEX_FORMAT` を混ぜる — ページが 1 つも変わっていなくても、列や索引の仕方を変えた版のスクリプトが古い形式のインデックスを使い続けないため。`_build()` の出力の形を変えたら上げる）。ページの追加・削除・編集をすべて捕まえる（削除すると集合から 1 行消える。最新 mtime だけを比べる形では削除を捕まえられない）。`git pull`・`/wikicommit-fix`・`/wikicommit-remove`・Close 同期による `review_status` の書き換えもファイルが変わるので同じように拾う。読むのは `stat()` だけでページの中身は読まない（判定は `query` のたびに走るため。実測 1,100 ページで約 9 ms、全件の作り直しは約 1 秒）。`git checkout` や clone で mtime だけが変わると中身が同じでも作り直すが、誤りは「約 1 秒余計にかかる」側に倒れるので受け入れる

### `query` サブコマンド

1. 現在のページ集合の fingerprint を計算し、インデックスの `meta` テーブルに記録された値と比べる。インデックスが無い・`meta` テーブルが無い（この変更より前に作られた）・読めない・値が違う、のいずれでも先に作り直してから検索する。既存のインデックスを作り直したときは `NOTE: search index was stale (<理由>); rebuilding` を 1 行出す（`SUMMARY:` 行の形式は変えない — 呼び出し側は `hits=` を読んでいる）。fingerprint を読む接続は作り直しの前に閉じる（Windows では開いているファイルに対する `os.replace()` が失敗するため）。別プロセスが同時に開いていて置き換えに失敗した場合は、一時ファイルを消し、`WARNING:` を出して古いインデックスのまま検索する（検索は止めない）

   > **以前は「ファイルが存在しないときだけ」作っていた（Issue #1061）**。ファイルがあれば中身が古くても何も確かめずに使い、`build` を呼ぶ Skill は 1 つも無かったため、最初の検索のときに作られたインデックスがその後ずっと使われた。`wikicommit/ai-driven-dev-wiki`（2026-09-25）では実ページ 1,080 に対しインデックスは 373 ページ（すべて en）で、ja の検索は必ず 0 件になり、それが出力のどこにも現れず「Wiki にその知識が無い」と区別できなかった。**generate / translate / synthesize の最後に `build` を呼ばせる案は採らない** — 指示に頼る形で、手順の末尾が落ちる失敗クラス（Issue #406 / #474）を再現するうえ、`git pull`・`/wikicommit-fix`・`/wikicommit-remove`・Close 同期には届かない。**`query` のたびに必ず作り直す案も採らない** — search / ask は言語ごとに `query` を何回か呼ぶので 1 回の実行で数秒かかる
2. `MATCH` 演算子で全文検索する。MATCH 式の組み立ては指定形式で分かれる:
   - **位置引数**: 空白区切りの各語を個別にフレーズクエリとしてクォートし、暗黙の AND で連結する（ユーザー入力をそのまま FTS5 クエリ構文として解釈すると `-`・`"` 等でクエリ構文エラーになりうるため語ごとにクォートする。クエリ全体を単一フレーズにすると隣接した語順の完全一致でしか検索できなくなるため、キーワード検索として機能するよう語ごとに分割する）
   - **`--expand`**（Issue #581）: 各 `--expand` の値を `|` で分割して 1 グループとし（各語は前後の空白を除去し、内部の連続空白も 1 個の半角空白に潰す — 複数語の語は 1 つの隣接フレーズとして扱う一方、語の中に改行が残ると `SUMMARY:` 行が複数行に割れて、行単位で `hits=` を読む呼び出し側が値を取り落とすため）、**グループ内は OR・グループ間は AND** の式を組み立てる（`("児童手当" OR "子ども手当") AND ("申請手続き")`）。各語のクォート・`"` の `""` エスケープは位置引数と同一のルールで行う。単一語のグループも含め**すべてのグループを括弧で囲み、明示的な `AND` で連結する** — FTS5 は括弧で囲んだ式と裸のフレーズの並置（`("a" OR "b") "c"`）も、括弧同士の並置も構文エラーとするため、グループが 1 つでも存在する時点で明示的な演算子が必須になる。空白区切りの語を空文字列に潰す・分割記号 `|` 自体を語に含める、といったケースは扱わない（前者は落とし、後者は現実的な検索語に現れないため専用のエスケープ構文を設けない）
   - `trigram` トークナイザは3文字未満の連続文字列からはトークンを作れないため、3文字未満の語はどのページの本文とも絶対に一致しない（クエリ構文エラーにはならず、常に無条件で不一致になる）。この判定は Skill 側（LLM）に委ねず本スクリプトが行う（`docs/DesignDoc-skills.md` §11.5 のスクリプト委譲パターンに従う）。警告の文言は指定形式と、**グループ内に 3 文字以上の語が残るかどうか**で 3 通りに分かれる:

### 出力フォーマット（`query`）

`SUMMARY:` の `query=` は指定形式で内容が変わる。位置引数では従来どおり生のクエリをダブルクォートで囲んで出力する。`--expand` では**実際に実行した MATCH 式**をそのまま出力する（引用符を自前で含むため外側のクォートは付けない。落とされた語は式に現れない）:

## check_schema_coverage.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 69 → 69、コード 31 → 31、docstring 24 → 24、コメント 1 → 1、空行 13 → 13（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 2 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `wikicommit-schema-propose` は Issue #285
- 型の文字列を完全一致だけで集計する既知の限界（同じ概念が少しずつ違う型の文字列に分かれうる）は、docstring によれば Issue #285 の設計メモに書かれていた

### 目的

`.wikicommit/entity/**/*.md` を走査し、`type:` フロントマターの値が `.wikicommit/schema/` に専用のスキーマファイルを持たない（`default.md` へのフォールバックのみで表現されている）ページを検出する。`wikicommit-generate` Pass 2 のコンテキスト注入（型文字列の再利用誘導）と、`wikicommit-schema-propose`（Issue #285）の検出源の両方から使われる。

### 使用場面

> **`wikicommit-status` から呼ぶ理由（Issue #575）**: `default.md` へのフォールバック自体は §5.4 が定める正規の挙動だが、フォールバックするとその型の `granularity`・`properties:` 候補キー・本文テンプレートが丸ごと適用されなくなる。にもかかわらず、生成されたページは一見正常で `validate_frontmatter.py` の必須フィールド検証も通る（`default.md` の required だけが適用されるため）。
>
> 問題は、これが起きたことを**継続的に見せる経路が無かった**ことにある。`wikicommit-generate` はそのページを生成した実行の Completion Notice でしか報告せず（Issue #575 でこの報告自体を追加した）、`validate_frontmatter.py` の WARNING は `wikicommit-merge` が**変更ファイルにのみ**実行するため、スキーマファイルを後から移動・リネーム・削除した場合、そのコミット以降に変更されないページは二度と再検証されない。**壊れる契機（`.wikicommit/schema/` の編集）と検証の契機（ページの変更）が一致しない**ため、両者はすれ違い続ける。本スクリプトは全ページを毎回走査するので、「今この瞬間に何ページが影響下にあるか」を直接見せられる。
>
> `validate_frontmatter.py` の当該 WARNING は**現状維持**とする（ERROR に格上げしない）。専用ファイルを持たない型は正常系であり、ブロックすると Pass 2b〈Issue #315〉以前に生成されたページを持つ既存リポジトリが軒並みマージ不能になる。スキーマファイルの移動・削除を git 履歴から追う案も採らない — 本スクリプトが「結果として今どうなっているか」を直接見るのに対し経路を追う分だけ複雑で、しかも最初からファイルが無いケース（古い版で init したリポジトリ）を拾えない。

## check_schema_org_type.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 332 → 327、コード 165 → 165、docstring 131 → 126、コメント 2 → 2、空行 34 → 34（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 12 → 0（`Issues #496/#497` の形の 2 つ目も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `wikicommit-schema-propose` の判断と対になる決定論的な検査であることは Issue #285
- 型の想起を `--list-type-names` と `--describe` の 2 段にしたのは Issue #798。それまでは型を提案する 3 つの Skill が、実行のたびに無条件に、処理するソースの数にかかわらず、933 件の名前と説明（147 KB）をメインのコンテキストに受け取っていた。名前と説明を全件出す `--list-types` は、3 つの Skill が 2 段の形に移って呼び出し元が無くなったので、併存させずに削除した（消費者の無い受け皿は Issue #553）
- `--list-installed-hierarchy` は Issue #565、`--show-range` は Issue #496、`--list-properties` は Issue #497。型ごとのテンプレートファイルを事前生成する案は Issue #497 の背景で退けた
- 語彙の読み込みと継承チェーンの判定を `_schemaorg_vocab.py` に移したのは Issue #495。Issue #496 / #497 がそれを広げた

### 使用場面

語彙の読み込み・キャッシュ（`.wikicommit/schemaorg-vocab.json`）・`domainIncludes`/`rangeIncludes`/`rdfs:subClassOf` 継承チェーン判定のロジックは `.wikicommit/scripts/_schemaorg_vocab.py`（`_frontmatter.py`/`_wikilink.py` と同じ、複数スクリプトが import する共有モジュール）に切り出されている（Issue #495、`rangeIncludes`/DataType 判定は Issue #496 で追加）。`validate_frontmatter.py` の `properties:` フィールド検証（同スクリプトの節を参照）もこのモジュールを共有し、CLI としての本スクリプトとロジックが乖離しないようにしている。本スクリプト自身は CLI 引数のパース・出力整形のみを担う薄いラッパー。

### 保存先（Git管理下）

`.wikicommit/schemaorg-vocab.json` に遅延生成する（`search_index.py` の「初回クエリ時に build を自動実行する」パターンと同じ）。取得元 URL は上記の公式配布 URL に固定。TTL・自動更新は設けない — Schema.org 語彙の改訂頻度は低く、古い内容の実害は「新しい型が使えない」程度に留まるため。

`search_index.sqlite3` 等の `.wikicommit/.cache/`（`.gitignore` 除外）配下のファイルとは異なり、本ファイルは `.wikicommit/.cache/` の外（`.wikicommit/schemaorg-vocab.json`）に置き、Git 管理対象とする。理由: `search_index.sqlite3` は実行のたびに全件再構築される真の使い捨てキャッシュ（消しても実害ゼロ）だが、本ファイルはネットワーク取得コストのある準静的な参照データであり、削除すると次回実行時に毎回ネットワーク取得が再発生する。`.cache/` という名前が与える「気軽に消してよい」という印象と実際の性質が食い違っていたため、`llm-agent-research-wiki` パイロットでの指摘（`Issues/registered/p3-117-schemaorg-vocab-cache-placement.md`（非公開の開発リポジトリ側の記録））を受けてGit管理下に切り出した。副次的な効果として、クローン直後から使え、複数人・複数マシン間でのネットワーク取得の重複コストも避けられる。

再生成したい場合はユーザーが `.wikicommit/schemaorg-vocab.json` を手動削除して再実行する。Git管理下にあるため、再生成後の差分は他の追跡ファイルと同様に通常のコミット・PRレビューを経て反映される（`wikicommit-merge` が `.wikicommit/schemaorg-vocab.json` の新規作成を検出しコミットに含める。`.claude/skills/wikicommit-merge/SKILL.md` Step 2 参照）。`--type`/`--list-type-names`/`--describe`/`--show-range`/`--list-properties` のどの呼び出しもこの同じファイルを共有する。`rangeIncludes`/`is_datatype`（Issue #496 で追加されたキー）・property の `comment`（Issue #497 で追加されたキー）を含まない旧形式のキャッシュは手動削除不要 ── `_schemaorg_vocab.py` の `load_or_build_index()` が `_is_well_shaped_index()` でこの形状不一致を自動検出し、再取得・再構築する（各 `types` エントリに `is_datatype`、各 `properties` エントリに `range`/`comment` キーが揃っているかまで検証する。外側の `{"types": dict, "properties": dict}` の型だけでは、旧形式のキャッシュを誤って正常として受理してしまい、`--show-range` が黙って何も報告しなくなる、`--list-properties` の説明列が常に空になる、または `is_in_datatype_lineage()` がキー欠落を `is_datatype: false` と誤認して DataType 型をエンティティ型として誤分類する、という複数のサイレント劣化を招くため）。

### 処理フロー（`--type` + `--list-properties`）

新しい型スキーマファイルを書く際に「この型が Schema.org 上でどんな property を持ちうるか」を一覧するための、オンデマンド表示モード（Issue #497）。933型分の全 property 一覧を静的ファイルとして事前生成・保存する方式（`.wikicommit/schema/template/` 等）は不採用とした — `.wikicommit/schemaorg-vocab.json`（Issue #319）という単一の情報源と二重管理になるうえ、全property入りのテンプレートはスキーマ層が本来持つ「絞り込みによる認知負荷低減」という目的（Issue #495 が型レベルの `recommended` を廃止した理由と同根）と衝突するため。

### 処理フロー（`--list-type-names` / `--describe`）— 型の想起は 2 段階

**分けた理由は、この一覧が果たしているのが想起であって存在保証ではないため**である。型が実在するかは候補が承認された後の `--type <Type> --property ...` が決定論的に確かめており、一覧の役目は「モデルが思いつかない型を候補に上げさせる」ことに尽きる。想起には、誰も検討していない 928 型の説明文は要らない。

| | 実測 |
|---|---|
| 旧 `--list-types`（全 933 型の名前 + 説明） | 147,421 B（約 37K トークン） |
| `--list-type-names`（名前のみ） | 13,441 B（約 3.4K トークン） |
| `--describe` 3 件 | 170 B |
| **合計** | **約 14 KB（−90%）** |

これは `/wikicommit-generate` の固定オーバーヘッドをソース件数によらず約 84K → 約 51K トークンに下げる（利用者向けの数字は `README.md` の Requirements → Context window が正本）。

**`--list-types` は残さず削除した**（Issue #798 の検討事項 5）。3 Skill が 2 段階へ移った時点で呼び出し元が 0 になり、「どの Skill も使っていないが配布はされているモード」を仕様に残すことは、Issue #553 が確立した「消費者のいない受け皿を配らない」に反する。しかも残せば、プリロードすべきでないと決めたばかりの高価な経路を仕様書が宣伝し続けることになる。同じ需要は `--describe` がオンデマンドで満たす。

**`--describe` は語彙に無い名前を ERROR にする**（同 検討事項 6）。黙って落とすと、段階 1 が 933 件の実在する名前を渡している以上「戻ってこなかった名前＝モデルの創作」であることが承認ステップまで伝わらない。1 件でも該当すれば終了コード 1 を返すが、実在した分は通常どおり出力する（呼び出し側が有効な候補だけで進めるため）。

**この削減は測れない**（同 検討事項 1）。説明文を落として型提案の recall が落ちたかを判定する eval 基盤はこのリポジトリに無く、Issue #669 が `chain_of_thought` を実装せず削除したときと同じ状況にある（削減は確実・品質劣化は判定不能）。壊れ方が軽いこと（型提案は元々ゼロ件が通常の結果で、`wikicommit-schema-propose` と `check_schema_coverage.py` が事後の安全網として残る）を根拠に採ったうえで、**次のパイロットの観察項目**として「`provenance` が `init-theme` / `collect` / `generate-interactive` / `generate-auto` の型が実際に生まれるか」を記録する — それが recall を落としていないことの唯一の間接的な証拠になる。

## rebuild_index.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 330 → 325、コード 171 → 171、docstring 83 → 80、コメント 42 → 40、空行 34 → 34（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 9 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- index.md の更新をスクリプトにしたのは Issue #406。それまでは、LLM エージェントが長い複数段の実行の末尾で「全ソース/ペアの後に 1 回」行うことを覚えておく手順だった（決定論的な全ディレクトリ走査をエージェントの記憶に任せていた）
- view の言語ディレクトリの索引（`[[View/<slug>]]` を並べ、予約された `View` セグメントを題にする）は Issue #675
- Type の索引の frontmatter に `review_status: reviewed` を書くのは Issue #580（最後のページが消えた Type ディレクトリの index.md も再構築するのは、`review_status` の無い frontmatter が残ると WikiCommitBanner が「未レビュー」の警告を出し続けるため、という docstring の理由も同じ番号を付けていた）。コメントは、Type の索引が `convert_wikilinks.py` ではなくここで書かれ、`.wikicommit/entity/` の下に実ファイルを持つことが、そもそもその慣習から外れた理由だと書いていた
- `comments: false` を併せて書くのは Issue #741
- 1 行を WikiLink だけにしたのは Issue #678。それまでの `— {title}` は全言語の全 Type 索引の全行で "Title — Title" と出ていた。コメントは、外した `— {title}` がリンクの文字列同士を偶然区切っていたと書いていた（行頭に `-` を付ける理由）
- グループごとの `## <label>` の節に分けるのは Issue #1035

### 目的

Type ディレクトリの `index.md`（1 行 1 件の `- [[Type/slug]]` 箇条書き）を、ディレクトリを実際にスキャンして決定論的に再構築する。従来この更新は `wikicommit-generate`/`wikicommit-translate` の SKILL.md が「全ソース/ペア処理後に1回だけ」という手順としてLLMエージェントの記憶に委ねており、長い多段生成の末尾に置かれた「最後にこれも忘れずに」という位置づけの手順だったため、ソース件数が多いバッチほど実行し忘れるリスクがあった（Issue #406）。本スクリプトへの委譲により、対象ディレクトリを指定しさえすれば取りこぼしが構造的に起こらなくなる。

### 使用場面

`wikicommit-synthesize` の行は、合成ページがまだ `.wikicommit/entity/<lang>/<Type>/` に書かれていた時期（Issue #547 で index の再構築を足した時点）の「そのページの Type ディレクトリ 1 件を引数に指定」という記述のまま残っていた。Issue #675 で合成ページの置き場が view ツリー（`.wikicommit/view/<lang>/`）に移り、`wikicommit-synthesize/SKILL.md` は view ツリーの言語ディレクトリを渡すように変わったが、この節は追従していなかった。同様に、グループファイルを書いた後に index を作り直す `wikicommit-organize`（Issue #1035）、検証ステップで引数なしで呼ぶ `wikicommit-update`、`rebuild_index()` を import する `rename_page.py`（Issue #1095 から分割した改名）も挙がっていなかった。Issue #1160 で、呼び出し元の現在の呼び方に揃えた。

### コマンド

- 引数なし: `.wikicommit/entity/` 配下で、`.md` ファイルを直接含むディレクトリ（`<lang>/<Type>/` 以深。ネストした custom 型も対象）をすべて自動検出して再構築する。過去の実行が書いた `index.md` しか残っていないディレクトリも対象に含める — 最後のページが `/wikicommit-remove` で削除された Type ディレクトリはページを1つも持たないため、「ページを持つディレクトリ」だけを検出対象にすると、その `index.md` が二度と再構築されず古い一覧のまま（かつ Issue #580 以前の `review_status` なしの frontmatter のまま）残り続ける

### 処理フロー

1. 対象ディレクトリごとに、ディレクトリパスを `.wikicommit/entity/<lang>/<Type>/` として解析する（`<Type>` はネスト custom 型の場合 `/` を含みうる）。ディレクトリが存在しない、または `.wikicommit/entity/` 配下の `<lang>/<Type>` 形式として解決できない場合は WARNING を出して当該ディレクトリをスキップする（他の対象ディレクトリの処理は継続する）
2. ディレクトリ直下の `*.md`（`index.md` を除く）を走査し、各ページの frontmatter を読む。frontmatter のパースに失敗したページ、`title` フィールドがないページは WARNING を出して index.md への掲載から除外する。`status: removed` のページも除外する（サイレント。孤立検出等と同じ既存の除外方針）
3. 残ったページをファイル名（slug）の昇順でソートする
4. `index.md` を書き出す:
   - frontmatter: `title`（そのディレクトリの `<Type>` の末尾セグメントのみ。例: `custom/Decision` → `"Decision"`。Issue #320 — `"<Type> Index"` ではなく bare Type name を使う）・`lang`・`type`（`schema:<Type>` の完全形）・`review_status: reviewed`（Issue #580）

     `review_status: reviewed` は `convert_wikilinks.py` の `generate_root_index()`・`_write_source_page()`・`_write_sources_index()`・`_write_source_dir_index()` が既に同じ理由で行っているスタンプと同じもの: `index.md` はビルド生成のナビゲーションページであって LLM が書いた Wiki コンテンツではないため、`WikiCommitBanner` の未レビュー警告を表示すべきでない（同コンポーネントはフィールドが無い場合 `pending` にフォールバックする — LLM 生成ページで書き漏れた場合に安全側へ倒すための意図的な設計であり、これ自体は変更しない）。Type 別インデックスは `convert_wikilinks.py` ではなく本スクリプトが生成し、しかも root index や source ページと違って `.wikicommit/entity/` 配下に実体を持つため、この慣習の適用対象から構造的に外れていた。

     除外の判定を `WikiCommitBanner` 側（`fileData.slug === "index"` 等）に置く案は採らない。同コンポーネントは Quartz のスラッグ命名規約に依存しない方針を明示している（`docs/DesignDoc-publish.md` §8）ため、書き出す側でフィールドを持たせる方が一貫する。なお `index.md` は `wikicommit-merge` のレビュー追跡 Issue の対象外でもあるため、バナーを見た読者が対応する Issue を探しても存在しない、という点でも表示は誤りだった。

     **既存リポジトリの是正**: 本スクリプトは対象ディレクトリの `index.md` を毎回フルスキャンから全上書きするため、次回 `/wikicommit-generate`・`/wikicommit-translate`・`/wikicommit-synthesize` が走った Type ディレクトリから順に自動的に是正される。一括移行の仕組みは用意しない — 全 Type を即座に是正したい場合は引数なしの `python .wikicommit/scripts/rebuild_index.py` を 1 回実行すれば足りる。
   - body: 各ページ1行、`- [[<Type>/<slug>]]` の箇条書き（slug 昇順）。**タイトルを接尾辞として付けない**（Issue #678。下記コールアウト参照）
   - 既存の `index.md` があれば全体を上書きする（差分マージではなく毎回フルスキャンからの再構築。手書きの前文等があっても保持しない）
5. 対象ディレクトリすべての処理後、`SUMMARY:` 行を1行出力する

> **行にタイトルを付けない理由（Issue #678）**: `convert_wikilinks.py` の `convert_file()` は WikiLink を**参照先ページの `title`** で描画するため、`[[Type/slug]] — {title}` という行は公開サイト上で `Adaptive Context Compaction — Adaptive Context Compaction` のようにタイトルの重複になる。Type 別インデックスは Wiki を回遊する主要な入口の 1 つであり、全型・全言語の**全行**がこの形になっていた。
>
> **この接尾辞は無意味に置かれたものではない**。同じファイルが 2 つの文脈で読まれ、片方でだけ重複する:
>
> | 読み手 | `[[Person/yamada-taro]] — 山田太郎` の見え方 |
> |---|---|
> | リポジトリ上（GitHub・エディタ） | GitHub は `[[...]]` を描画しないため、接尾辞がタイトルを伝える唯一の要素になる |
> | 公開サイト（Quartz） | WikiLink が参照先の `title` に置き換わるため `山田太郎 — 山田太郎` になる |
>
> この非対称は `rebuild_index.py` 単体を読んでも `convert_wikilinks.py` 単体を読んでも見えない。**生表示でタイトルが読めなくなることは受け入れる** — slug は言語中立の英語識別子（Issue #193）であり非英語 Wiki では可読性が落ちるが、(a) その情報は同じディレクトリのファイル名そのものが持ち、(b) この読み手は運用者であって読者ではなく、(c) 代償として読者向けの主要な回遊面すべてに重複が出続けることの方が大きい。
>
> なお `convert_wikilinks.py` が書き出す他の一覧（`_write_sources_index()` / `_write_source_dir_index()` / `generate_overview_page()`）はいずれも素の Markdown リンク `[{title}]({link})` を書いており、この問題を持たない。WikiLink を使っているのは Type 別インデックスだけである。
>
> **接尾辞を落とすだけでは足りず、行を箇条書き（先頭の `-` + 空白）にする**。インデックスの各行は空行を挟まない連続行であり、CommonMark はこれを 1 つの段落に畳む — 配布する `quartz.config.yaml` は `hard-line-breaks` プラグインを `enabled: false` で出荷しているため、ソフト改行は `<br>` にならない。つまり公開ページ側では**元から**全行が 1 段落に連結されており、接尾辞の `{title}` とその前の em dash が偶然その区切りとして働いていた。マーカーを付けずに接尾辞だけ落とすと、リンクの文字列同士が空白 1 個で隣接した 1 本の長い行になる（`BYOLLM ファイル境界プロトコル OKF（Open Knowledge Format） 孤立ページ …`）— 読者向けの主要な回遊面を直そうとして別の形で読めなくすることになる。`convert_wikilinks.py` が書き出す他の一覧（下記）が例外なく `- [{title}]({link})` を書いているのはこれと同じ理由であり、Type 別インデックスだけがマーカーを持っていなかった。
>
> **インデックス本文の書式を読み取るコードは 1 箇所ある**: `wikicommit-remove` の `remove_page.py` の `remove_index_entry()` は、`index.md` を全面再構築するのではなく該当行だけを行頭アンカーの正規表現で落とす（`main()` から呼ばれる）。同関数は先頭のリストマーカーを任意扱いにしてあり、`- [[Type/slug]]`（現行）・`[[Type/slug]]`・`[[Type/slug]] — Title`（いずれも旧書式。既存リポジトリは遡及移行しないため残る）の 3 形式すべてに一致する。**行の書式を変える際はここも併せて見ること** — 一致しなくなっても例外にはならず、`status: removed` のページを指す行が残り、次の `/wikicommit-merge` が `check_wikilinks.py` の「`status: removed` のページへのリンクです」ERROR でブロックされる形でしか現れない。同関数は行を落とした後、下に空行しか残らない `##` 見出し（次の `##` 見出しかファイル末尾まで）も併せて落とす — グループファイルを持つ型の index は `## <表示名>` で区切られ、`rebuild_index.py` はページの無い節（グループ・未分類とも）を出さないため、最後の 1 ページを消した節の見出しだけが次の再構築まで公開されるのを防ぐ（Issue #1136）。`index.md` を `rebuild_index.py` で再構築する案は採らなかった — 旧書式の行やフロントマターまで書き直す差分が削除 PR に混ざり（旧書式は遡及移行しない方針）、Skill 側のスクリプトから利用者リポジトリの `.wikicommit/scripts/` への依存も増えるため、触れるのは消した行と空になった見出しに限る。
>
> **他のチェックには影響しない**（実装時に確認済み）: `check_orphans.py` は `index.md` をリンク元として明示的にスキップするため孤立判定は変わらず、`search_index.py` の `build` は `index.md` を索引対象から除外するため検索結果も変わらない。`check_wikilinks.py` は引数なしモードでインデックスの WikiLink も検証するが、リンクは実在ページのディレクトリ走査から生成されるため構成上必ず解決する（`WIKILINK_RE` は行内の部分一致であり、リストマーカーの有無に左右されない）。
>
> **採らなかった案**: publish 時に `convert_file()` 側で接尾辞を strip する（`is_index` を渡す）。両方の読み手を満たせて、`rewrite_relative_links()`・`flatten_custom_type()`（Issue #576）という publish 時変換の前例にも乗るが、**インデックス本文の書式を書く側と publish 側が「行のどこからどこまでがタイトルか」まで knowing する状態**を作り、`rebuild_index.py` が書式を変えた瞬間に strip が黙って効かなくなる。これはこのリポジトリが繰り返し踏んできた drift の形そのものである（Issue #114・#487・#677）。上記の `remove_index_entry()` も書式を知る 2 つ目の箇所ではあるが、参照するのは行頭の WikiLink までであり、行の残りには一切依存しない（`.*` で捨てる）ため、この drift の形には当たらない。
>
> **遡及移行は不要**。本スクリプトは対象ディレクトリの `index.md` を毎回フルスキャンから全上書きするため、次に `/wikicommit-generate`・`/wikicommit-translate`・`/wikicommit-synthesize` が走った Type ディレクトリから順に是正される（Issue #580 のスタンプ追加時と同じ経路）。全型を即座に揃えたい場合は引数なしの `python .wikicommit/scripts/rebuild_index.py` を 1 回実行すれば足りる。公開サイトへの反映は次のデプロイを待つ。

### グループファイルを持つ型

`.wikicommit/groups/<Type>.yml`（`docs/DesignDoc-data.md` §4.5.3）がある型では、本文を `## <表示名>` の見出しで分ける。グループはファイルの順、各グループ内は slug 順、ページが 1 件も無いグループは見出しごと省き、どのグループにも無いページは最後の未分類の見出し（ja「未分類」・en「Unclassified」、ファイルの `unclassified_label` が優先）の下に置く。表示名は index の `lang` で選ぶ。ファイルが無い型は従来どおり見出しの無い 1 列である。ファイルが不正なときは `WARNING:` を出して見出し無しで書く（ビルドを止めない。詳細は `check_groups.py`）。書き換えるのは `index.md` だけで、ページには触れない。

### view ツリーの言語別 index

Issue #675 で view ツリーを足したとき、実装（`rebuild_view_index()`）・docstring・スクリプト一覧の行は view ツリーの言語別 `index.md` を述べるように変わったが、この節の「目的」「コマンド」「処理フロー」「出力フォーマット」は Type ディレクトリしか書いていなかった。ScriptSpec の分割（Issue #1143）の最中に、同じファイルの一覧と節の食い違いとして見つかり、Issue #1160 でこの小節を足して節だけで view の index の書き方が分かるようにした。あわせて、Type の index の frontmatter の記述に `comments: false`（Issue #741 で足した）が抜けていたのを補った。

`kind` で見出しを分けない判断は Issue #675 の実装時のもの（`rebuild_view_index()` の docstring に同じ理由がある）。

## convert_wikilinks.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 3,986 → 3,781、コード 2,402 → 2,402、docstring 674 → 546、コメント 688 → 611、空行 222 → 222（docstring 内の空行は docstring に数える）。`Issue #` はコメント・docstring で 172 → 0。

**仕様の置き場**: 移行前は ScriptSpec に節が無く、仕様は docstring と `docs/DesignDoc-publish.md` §8 に分かれていた。読者に見える面（文言・表示条件・件数の意味）は publish §8 がすでに詳しく持っていたので正本のまま残し、ScriptSpec にはスクリプトとしての入出力と処理の契約（出力パスの 3 段の割り当て・`custom/` の扱い・相対リンクの書き換え順・照合の注入・前回の出力の掃除・ビルドがリポジトリを変えないこと）だけを書く節を起こした。§11.5 の共有スクリプト表に仕様を置く `add_source.py` / `resolve_source_cache_path.py` と違い、このスクリプトは Skill から呼ばれないため §11.5 に行が無く、置き場を選ぶ余地は ScriptSpec か publish §8 かだった。

**分けるかの判断（Issue #1343）: 分けない**。移行後の 3,781 行の内訳は、10 言語の UI 文字列（`*_LABELS` の 8 つの辞書）が 1,132 行、俯瞰ページ 431 行、`main()` 340 行、root index 133 行、ソースページ 122 + 112 行、WikiLink 変換 132 行、`llms.txt` 105 行、アセット 88 行、グループのマニフェスト 55 行だった。分けない理由は次のとおり:

- どの出力も `main()` の 1 回のページ走査の結果（`page_stats`・被リンク・書いたパスの集合）を材料にしている。別スクリプトにすると走査を出力の数だけ繰り返すか、走査の結果を受け渡す形を新たに作ることになる。前回の出力の掃除はこのビルドが書いた全パスの和を要るので、掃除だけを残しても分けた先の書いたパスを集めなければならない
- 関数は既に出力ごとに分かれており、1 つの出力を直すときに他の出力のコードを読む必要は無い
- 利用者のリポジトリでは `.wikicommit/scripts/` がツリーごと配られる（`_root_outputs.py` の `update: overwrite`）ので、モジュールを足すこと自体は `/wikicommit-update` と `check_distribution_freshness.py` を壊さないが、得るものが無い
- 分ける候補として最も大きいのは UI 文字列の辞書（約 30%）だが、それはデータであって読む負担になる処理ではなく、`tests/test_ui_translation_completeness.py` 等が `convert_wikilinks` から import しているため、移すとテストの import 先も変わる。読む負担の問題は docstring・コメントの移行で解き、辞書は動かさなかった

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `content/sources/` は Issue #476 で、ページの `sources` を逆に引いて言語ごとに集める `content/<lang>/sources.md` を置き換えた（管理ファイルのツリーを直接写す「反転」）。WikiLink のグラフの外に置くこと（プレーンな Markdown リンク）はそのとき受け入れた制約。中間ディレクトリの `index.md` は、Quartz の `folder-page` プラグインがこのツリーには生成しなかったため Issue #493 で足した。そこでの `/index` の衝突は、URL ソースの素のドメインとパスの衝突（Issue #213）と同じ種類の問題
- `generated_pages[]` の `.wikicommit/wiki/` 接頭辞は Issue #477 の改名より前の形。`## Summary` の日本語見出しは Issue #405 で管理ファイルの見出しを英語に固定する前の形で、`## Retraction Reason`（Issue #737）にはそれが無い
- `path_href()` は `WikiCommitSources.tsx` の `pathHref()` と手で揃えている（Issue #212）
- 予約ツリー（`RESERVED_PUBLISH_TREES`）は Issue #957。Issue #585 が `overview` を足したとき、グラフとエクスプローラのどちらにも登録しておらず、それぞれ黙って偽の言語・余計なフォルダが出た
- 照合の注入（`ai_review_model` / `ai_review_at`）は Issue #751。ページにコピーしないのは、コピーが古くなる失敗（Issue #705）を一度経験しているため。記録の無い空白は Issue #750 より前のページで、記録はさかのぼって作れない。`reviewed_by`（Issue #663）と名前を分けた。`pass` 以外を出さないこと・古い `pass` に戻らないことも同じ Issue。改名したページが古い slug の記録で判定されるのは Issue #1162。翻訳の照合（`ai_review_stage`・「原文と照合」）は Issue #1031
- 指摘の種類の集計（`FINDING_TYPES`・`OTHER`）、`page_at_fault: other` を数えないこと、公開されなかったページの件数（`count_unpublished_pages()`）は Issue #1063
- frontmatter への挿入を YAML の読み書きにしないのは、読み書きで設定ファイルのコメントを失った Issue #713 のため
- UI 文字列の 10 言語は Issue #1017 で決めた。それ以前は ja だけで、「その言語の Wiki が現れたら足す」はパイロットがたまたま使った言語を理由に足すことになっていた。英語に落ちたことを公開ページで告げない判断は Issue #825（理由は 3 つ: 告知では失われたものが戻らない、言語中立の印は見えていることを繰り返すだけ、誰も行動できない常設の告知になる。バナーにはすでに 2 つの Issue が文言を足さないよう抑えている）
- root index: Quartz の FolderPage が root の index を作らず `index.xml` が `/` で配られる問題は Quartz 側の GitHub Issue #75。既にファイルがあれば書かない分岐は、前回のローカルビルドの出力を凍結させたため Issue #358 で外した。サイト全体の件数（Issue #407）、`theme` の埋め込みをやめた Issue #670、`site_description` は Issue #671、多言語 Wiki での言語別件数は Issue #730（Issue #664 の注記を言語一覧の下へ持ち越した）、照合済みの件数は Issue #769、`targets` に無い言語の取りこぼしは Issue #731（`existing_lang_targets()` は Issue #190）、サイト全体の帰属・ライセンスの注記は Issue #645（ページごとの注記は Issue #558）
- 件数の注記の文言: 裸の数字が「誰も関心を持っていない」に読める（Issue #664）、人の確認が設計上一部であると述べる（Issue #800）、抜取の語彙を使わない（Issue #769 — `RISKY:` が良く選べているかは未測定）、`reviewed` は人の読み手を名指しする（Issue #664・#740）ので機械の件数を同じラベルに置かない（Issue #751）、照合が見ないもの（網羅性は Issue #722、害と読者自身の知識は Issue #723）、ソース件数のキーを `sources` と分ける（Issue #990）
- 俯瞰ページは Issue #585。照合の割合から翻訳を外したのは Issue #1030（翻訳は記録を持たないので分母に入れると割合を下げ続けた。`/wikicommit-review` を翻訳に走らせると 100% を超えうるので分子も絞る）。Issue #769 が root index を言語で分けたのとは目的が違うので、言語ではなく `translated_from` で分ける。翻訳の照合が 1 件でもあれば Issue #1030 の「記録されていない」行を Issue #1031 の割合に置き換える。ハブ行のソース件数は Issue #990、同じソースに立つハブは Issue #1006（ソースの同一性は Issue #572 / #573 の命名規則と揃える）、ソースの言語別は Issue #989、未処理のソースを「未記録」と分けたのは Issue #1135、Type の取り違えを wanted から外すのは Issue #563、`other_types_for_slug()` の共有は Issue #677、view ページを孤立ページから外すのは Issue #675、`comments: false` は Issue #741（書き出す側で決めるのは Issue #580 と同じ考え）
- `source.lang` の言語行は Issue #1007、`lang: no` を YAML 1.1 の `False` と区別するのは Issue #1193 の後続。パイロット Wiki に引用符なしの `lang: no` を持つ `www.ssb.no` のソースが 2 件あった
- view ツリー（`View` セグメント・3 段目の割り当て・相対リンクを書き換えない）は Issue #675
- `custom/` を公開時に落とすのは Issue #576（エクスプローラ・パンくず・フォルダページ・URL に意味の無いフォルダが出ていた）。entity 側に残すのは、落とすと `rebuild_index.py` が `type: schema:Decision` を書き、`validate_frontmatter.py` が拒否するため（Issue #512）。出力パスの割り当ては当初 2 段で、view ツリーを足したとき 3 段にした（コメントには「Two passes」が残っていた）
- 本文の相対リンクの書き換えが実際の不具合になったのは、Issue #589 でローカル画像が公開サイトに届くようになってから。`sync_assets()` も Issue #589 で、それ以前は推奨していた相対パスの画像が公開サイトで 404 になっていた（推奨を確かめたとき、ファイルを `content/` に直接置いていた）。`gitignore: true` の glob が `content/` を隠さないことは globby に対して直接確かめた
- 前回の出力の掃除は Issue #271。`removed` のページを `content/` に書かないのも同じ Issue
- グループのマニフェストは Issue #1035。frontmatter のフィールドにしないのは、Quartz の content index に届かず読み手の無い受け皿になる（Issue #553）ため
- `llms.txt` の記述（`description`）を `page_stats` に持たせたのは Issue #1117。「Key pages」の上限 50 は、パイロット Wiki が 2 言語で 1,000 ページを超えていたことから

## reconcile_ingest_status.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 227 → 224、コード 93 → 93、docstring 82 → 79、コメント 25 → 25、空行 27 → 27（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 6 → 0（うち 1 つは行をまたいで `Issue` と `#474` が分かれたもの）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトが救う状態（長いバッチで、別の管理ファイルの実行で書かれたページがこのファイルのハッシュを引くが、このファイルの `status` / `generated_pages` が書き戻されず `pending` のまま残る）は Issue #474。この修正の初期版は SKILL.md の散文（インラインの「バッチ全体のスコープ」規則と、実行の終わりの grep による掃き出し）で解こうとし、コードレビューがその設計を非決定論的で安全でないと判断した
- `generated_pages` が空のファイルだけを対象にする条件は Issue #874。docstring は、この条件を当初書かなかったのは、ページを作り直させるために `pending` へ戻すものがそれまで無かったからだと書き、`add_source.py` を「その値を書くもう 1 つの書き手」と呼び、要求キューの Skill について「いまは意図して `pending` を書くものもある」と書いていた

### 目的

`status: pending` のまま放置されている ソース管理ファイルのうち、実はその `source.hash` が既に公開ページの `sources[]` に使われているもの（＝内容は既に取り込まれているのに、そのソース自身の管理ファイルへの書き戻しだけが行われなかったもの）を検出し、`status: generated`・`generated_pages`・`last_generated_at` を書き戻す（Issue #474）。`ai-driven-dev-wiki`（round2）パイロットで、複数の関連ソースが同一エンティティのページを共同更新した際、そのうち一部の管理ファイルが `status: pending`・`generated_pages: []` のまま取り残される事例が確認された。

当初はこの照合・書き戻しを `wikicommit-generate` SKILL.md の instruction（LLMへの散文指示 + grep）として実装したが、`/code-review --fix` の多角的レビューで、この instruction ベースの設計自体が複数の実害あるバグを抱えていることが判明した（詳細は `docs/history/DesignDoc-skills.md` §11.6「パス 4 の後処理と書き戻し」を参照）。最も重大だったのは、`status: outdated` のファイルは `check_ingest_freshness.py` が意図的に `source.hash` を書き換えずに残す（前回生成時点の参照点として機能させるため）ため、`outdated` ファイルに対して同じ hash 一致判定を適用すると、「ソースが変更され再処理が必要」という正しいシグナルを「既に反映済み」と誤認して握りつぶしてしまう欠陥だった。本スクリプトはこの反省を踏まえ、`status: pending` のみを対象とし（`outdated` は明示的に対象外）、一致した場合は常に `status: generated` のみを設定する（`partial`/`excluded`/`failed` への遡及推定は行わない — それらは Pass 2/4 のエンティティ単位の結果が必要で、その場限りの情報のため後から再構築できない）。

> **`generated_pages` が非空なら触らない — ポリシー起点の requeue を黙って取り消さないため（Issue #874）**: 本スクリプトが救おうとしている形は、同スクリプトの docstring 自身が述べるとおり「**ページは書かれたが、この管理ファイル自身の `status` / `generated_pages` が書き戻されなかった**」ものであり、それは `generated_pages` が空のまま残ったファイルである。この条件が元々書かれていなかったのは、**当時は「再処理させるために」`pending` を書く主体が居なかった**ためである。`pending` を書くもう 1 つの経路 — `add_source.py` が `outdated` なファイルのハッシュ一致を見て `pending` へ戻す経路（`update_frontmatter_status()` は `status` 行しか触らないため、前回実行の `generated_pages` はそのまま残る）— も同じ形をしており、本条件はそちらにも等しく効く。**そしてそれが正しい** — ソースが元に戻された以上、次の実行で Pass 1 が拾って作り直すべきであり、`generated` へ即座に戻してよいものではない。
>
> 現在は居る。ポリシー・型テンプレート・生成ルールの変更を既存ページへ届ける唯一の経路は、そのソースを `status: pending` に戻して次の `/wikicommit-generate` に Pass 2c をもう一度通させることであり（`--regenerate` は Pass 2c を実行しない。Issue #578）、requeue Skill がそれを行う。この条件が無いと、requeue されたファイルは**必ず**上記 3 条件すべてに一致する — ページを作ったソースの hash は定義上そのページの `sources[]` に現れるためである — ので、generate が実行の最後に本スクリプトを呼んだ時点で `generated` へ書き戻される。**しかも出力は `RECONCILED:` という成功系のメッセージである。** 5 件ガード（Issue #567）と組み合わさると、これは例外ではなく通常の経路になる: 50 件を requeue → generate が 5 件だけ処理 → 実行末尾の本スクリプトが残り 45 件を `generated` へ戻す → 二度と拾われない。
>
> **3 つの requeue 起点を守るのはそれぞれ別の条件であり、1 つのコードから他の 2 つは見えない**ため、ここに書いておく:
>
> | requeue の起点 | 何が守るか |
> |---|---|
> | `generated` / `partial`（ページが作られていた） | **この `generated_pages` の条件**。ページを作った以上 hash は必ず引用されているので、既存の 3 条件では落ちない |
> | `excluded`（ページを 1 枚も作っていない） | **既存のハッシュ一致条件**。1 枚も作っていない以上その hash はどのページの `sources[]` にも現れない |
> | `excluded`（以前のゆるいポリシーではページを作っていた） | **`last_generated_at` の条件**。上の 2 つを**両方すり抜ける** |
>
> 2 つ目はポリシーのスイッチを**off に戻す**経路そのものであり、requeue Skill が存在する理由の本題である。
>
> 3 つ目は当初この表に無く、2 つ目の説明（「`excluded` ＝ ページを 1 枚も作っていない」）が**常には成り立たない**ことを見落としていた。Pass 4 手順7 の `excluded` 分岐は `generated_pages` を書かない一方、**以前の実行が作ったページはディスクに残る** — 生成経路にページを消す手段は無い（削除は `/wikicommit-remove` の担当）— ので、そのページは変わっていない hash を引用し続ける。したがってこのファイルは `generated_pages` が空（1 つ目の条件を通過）かつ hash が一致（2 つ目の条件を通過）となり、requeue すると届かなかった generate の末尾で `generated` へ書き戻される。**到達経路は例外的ではない**: ポリシーを厳しくして requeue → generate で全件除外 → 緩めて再び requeue、という requeue Skill の本来の往復を 2 周するだけである。
>
> **3 つ目の条件が問うのは「何を作ったか」ではなく「一度でも実行を完走したか」である**。`add_source.py` は管理ファイルの新規作成時に `last_generated_at:` を**空の値で**書き、これを埋めるのは完走した実行だけなので、日付が入っていることは「この `pending` はその完走より後に、意図して書かれた」ことを意味する。Issue #474 が救おうとしている形は構造上ここが空である — そのページを書いたのは**別の**管理ファイルの実行であり、こちらは一度も書き戻されていないためである（`tests/test_reconcile_ingest_status.py::test_the_issue_474_case_still_reconciles` がこの両立を固定する）。
>
> **新しい `status` 値（`requeued` 等）を足す案は採らない** — 曖昧さは原理的に消えるが、`status` を読む全消費者（Pass 1 の収集条件・`add_source.py` の分岐・`check_ingest_freshness.py` の `CHECKABLE_STATUSES`・`wikicommit-status` の集計）に分岐が増える。**generate が本スクリプトを呼ぶのをやめる案も不可**（Issue #474 が解決した問題が戻る）。

### 処理フロー

1. `.wikicommit/entity/**/*.md`（`index.md` を除く）を走査し、各ページの `sources[].hash`（`sha256:` プレフィックスを除いた16進文字列）から「hash → そのhashを引用しているページパスのリスト」のマップを構築する
2. `.wikicommit/source/**/*.md` を走査し、`status: pending` の管理ファイルのみを対象にする（`pending` 以外は対象外。特に `outdated` は上記の理由により明示的に除外する）
3. 対象ファイルの `generated_pages` が非空の場合はスキップする（Issue #874。下記コールアウト参照）
4. 対象ファイルが `last_generated_at` を持つ場合はスキップする（同上）
5. 対象ファイルの `source.hash` が空文字列・未設定の場合はスキップする（`type: url` ソースが Pass 1 でまだフェッチされていない場合に発生しうる。空文字列を許すと事実上すべてのページに一致してしまうため）
6. 1で構築したマップにこのhashが存在すれば、一致したページパスを重複排除・昇順ソートした上で、`status: generated`・`generated_pages`（一致したページパスのYAML flow-styleリスト）・`last_generated_at`（実行日）を書き戻す。`## Failure Reason` セクションが存在すれば削除する（Pass 4 手順7の `generated` 分岐と同じ扱い。Issue #408）
7. 全管理ファイル処理後、`SUMMARY:` 行を1行出力する

## reset_review_on_content_change.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 276 → 274、コード 130 → 130、docstring 99 → 97、コメント 14 → 14、空行 33 → 33（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 7 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #724。それまでは `reviewed` なページの本文を書き換える 2 経路がどちらも `reviewed` の主張を動かさないまま文章だけを差し替えていた — `wikicommit-generate` Pass 3 の `action: update` は既存の `reviewed` を明示的に維持する規則を持ち、`wikicommit-fix` は規則自体が無く、Edit してそのまま終わっていた
- Pass 4 が `expires_at` をソースとの照合対象にしているのは Issue #279
- 決定論的に判定できる操作を SKILL.md の散文に書くと非決定論的な失敗モードを持ち込む、という理由は Issue #474
- `.wikicommit/view/` 配下のページも受け付けるのは Issue #675
- `index.md` を除外する理由（`rebuild_index.py` が `review_status: reviewed` を刻む）は Issue #580
- 旧ディレクトリ `.wikicommit/wiki/` から `entity/` への改名は Issue #477

### 目的

信頼ラダーの上段（`review_status: reviewed` と、Issue #663 以降そこに添えられる `reviewed_by` の実名）は「この文章を人間が読んだ」という主張である。ところがページを書き込む 6 経路のうち 2 つが、その主張を動かさないまま文章だけを差し替えていた（Issue #724）。

後者の方が鋭い — `/wikicommit-fix` は「レビュー済みの内容が誤っていた」から起動されるものであり、しかも公開ページの報告リンクは `review_status` に関わらず常時表示される（Issue #245）ため、`reviewed` なページの誤りを読者が報告するのは**設計上の主経路**である。結果として、そのレビューが見落としたからこそ書き直された文章に、レビュアーの実名が付き続けていた。

加えて `wikicommit-merge` Step 8 は `pending` のページにしか追跡 Issue を作らないため、更新された `reviewed` ページは**恒久的に再レビューされない終端状態**になっていた。

### コマンド

`<page>` は `.wikicommit/entity/` または `.wikicommit/view/` 配下のページ（Issue #477 以前の `.wikicommit/wiki/` 接頭辞も受け付ける。`index.md` は下記の処理フロー 2 のとおり除外する）。**両ツリーを受け付けることが要件である** — `wikicommit-fix` は Issue #675 以降どちらの接頭辞も対象に取り、view ページも `review_status` と追跡 Issue を持つため、entity ツリーだけを見るとその半分が黙って素通りする。

### 処理フロー

1. 引数が `.wikicommit/entity/` / `.wikicommit/view/` / 旧 `.wikicommit/wiki/` のいずれの配下でもなければ ERROR（誤ったパスが黙って no-op になるのを防ぐ）
2. `index.md` は `SKIP:`。`rebuild_index.py` がビルド生成のナビゲーションページとして書き出し、まさにその理由で `review_status: reviewed` を刻む唯一のページである（Issue #580）— 人間のレビューを経ていない `reviewed` がここだけは正当であり、降格させると `wikicommit-merge` Step 8 が index を追跡 Issue の対象外にしている以上**戻す経路が無いまま公開サイトに未レビューバナーが出続ける**。他の全走査スクリプトと同じ除外である（`wikicommit-fix` の公開 URL 逆引きは `**/*.md` を glob するため index も候補に入りうる）
3. 作業ツリー側のページを読み frontmatter と本文に分ける。パースできなければ ERROR
4. `review_status` が `reviewed` でなければ `SKIP:`（降格すべき主張が無い）
5. `git show HEAD:<path>` で前版を取得する。**比較先を HEAD にする**ことで、同一バッチ内で未コミットのまま 2 回更新された場合も正しく振る舞う（HEAD は依然として人間がレビューしえた最後の版である）。追跡されていなければ `SKIP:` — 新規作成は元から `pending` であり、比較すべき前版が存在しない。取得結果は**バイト列で受け取り、作業ツリー側の読み込みと同じ規則で自前でデコードする**（`utf-8-sig` ＋ 改行コードの正規化）— `subprocess` の `text=True` に任せるとロケール依存のコーデックになり、非 UTF-8 ロケール（Windows ネイティブ Python の cp932 / cp1252 等）では非 ASCII ページで `UnicodeDecodeError` が実行全体を途中で落とし、latin-1 系ロケールでは例外にすらならず文字化けした HEAD 版と突き合わせて全ページが無条件に降格する。BOM を落とすのも同じ対称性のためで、落とさないと HEAD 側だけ `---` 始まりと認識されず「frontmatter 無し・本文＝ファイル全体」に見えるため、1 文字も変えていないページが「内容が変わった」と判定される（`_frontmatter.py` がスクリプト間の BOM 扱いの食い違いを実バグとして名指ししているのと同じ種類の非対称である）
6. bookkeeping を除いた frontmatter フィールドを突き合わせ、本文は改行コードと前後の空行のみ正規化して比較する（内容の差は吸収しない）。HEAD 側の frontmatter が読めない場合は stderr に `WARNING:` を出したうえで**内容が変わったものとして扱う** — 誤って戻す代償は追跡 Issue が 1 件増えることだが、誤って維持する代償は人間が読んでいない文章に署名が残ることである
7. 一致すれば `UNCHANGED:`（何も書き換えない）。異なれば `set_frontmatter_field.py` の `apply_frontmatter_fields()` を in-process で呼び、`review_status: pending` を設定して `reviewed_by` を落とし `RESET:` を出す（Issue #705 の「`reviewed_by` は常に `review_status` に従わせる」という既存の規範。1 回の呼び出しで両方を行う）

### 既知の限界

`properties.description` が 1 文変わった場合と句読点だけが変わった場合を区別しない。テキスト一致で判定する以上これは避けられず、再生成モードの valve も同じ割り切りをしている。**既に陳腐化した `reviewed` を抱えた既存ページへの遡及適用も行わない**（本ドキュメント群が一貫して採る「新旧混在を許容する」方針）— 次にそのページが更新されるか人間が直すまで残る。

## record_review.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 639 → 636、コード 274 → 274、docstring 278 → 275、コメント 27 → 27、空行 60 → 60（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 20 → 0（`Issue` の付かない `#570`・`pre-Issue-#477` と、行をまたいで `Issue` と分かれた `#429`・`#474`・`#750` も外した）。出力する文字列には `#NNN` は無い。

冒頭の docstring は、このスクリプトが無い状態を「Pass 4 は判定を捨てる。Pass 4 step 1 が agent-to-agent の JSON を "never written to disk or Git" と明言している」と現在形で書いていた。いまの `references/pass4-review.md` にはこの文言が無いので、「記録が無ければ」という条件の形に書き直した。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #750。Pass 4 の 8 種の検査は、根拠の結び付けが Issue #442、細かな事実の検証と命名か捏造かが Issue #451、二次引用が Issue #473、帰属の正しさと単一ソースの無帰属の言い回しが Issue #429、ソース同士の不一致と 1 ホップのページ間の矛盾が Issue #566
- `/wikicommit-fix` の書き換えで `reset_review_on_content_change.py` が `review_status` を `pending` に戻すのは Issue #724
- 設定ファイルのコメントを丸ごと失った round-trip は Issue #713
- モデル ID の `claude-opus-5[1m]` という綴りを実データで見たのは Issue #559
- findings を本文に置くと集計スクリプトが散文を解析することになる — Issue #474 が名指しした失敗の形
- `sources[].license` は Issue #558 / #570
- 3 回のラウンドが 3 つの別の問題を見つけたのは Issue #571
- 射影が互換面であること（「この形式は自由に変えてよい」と読まない）は Issue #750
- 翻訳の証拠（`translated_from` + `source_commit`）と、`translate-check` の `discarded` で証拠を読まないことは Issue #1031
- `wikicommit-synthesize` の `MISSING_SOURCE` が `source_file` を空にするのは Issue #674
- スタンプを最新記録まで切り上げるのは Issue #991。記録が不変であることは Issue #750
- `model` / `reviewer` の当てはまらない側を空で置かないのは、Issue #553 が退ける形だから
- `stage: issue-close` に `skill_blob` が付かないのは Issue #750 の検討事項 5

### 目的

`wikicommit-generate` Pass 4 は生成した全ページに 8 種類の検査を掛けながら、その判定を 1 バイトも残していなかった（Issue #750。詳細と設計判断は `docs/DesignDoc-data.md` §4.8）。本スクリプトはその判定を、ページ単位のディレクトリに**レビュー単位の不変ファイル**として書き出す。

### コマンド

`--skill-blob` に渡すのは `.wikicommit/review-rules.md` の blob hash である（Issue #752 — 規律がそのファイルへ移ったため。`rules_version` との役割の違いは `docs/DesignDoc-data.md` §4.8 参照）。

`<page>` は `.wikicommit/entity/` または `.wikicommit/view/` 配下のページ（Issue #477 以前の `.wikicommit/wiki/` 接頭辞も受け付け、記録は `entity/` 配下に寄せる — 記録はページについてのものであり、後から `git mv` したリポジトリの履歴が 2 つに割れないようにするため）。**ディスク上に存在しなくてよい** — `result: discarded` がまさにその場合である。

### `page_at_fault` は検証も消費もされていない

`page_at_fault` は `FINDING_FIELDS` の射影に乗って記録されるが、**値を検証する箇所も読む主体も 1 つも無い**。`type` には enum 外のときの `WARNING:`（as-is で記録する）があるが、`page_at_fault` にはそれも無い。

**その結果、実データの 67% が仕様外だった**。`wikicommit/ai-driven-dev-wiki` のレビュー記録 705 件のうち、このフィールドを持つ 95 件の内訳は `this` 52・`under-review` 17・`other` 14・`self` 12 で、仕様の 2 値（`under-review` / `other`）に当たるのは 31 件だけである。**誤りは片側に寄っていた** — `other` は素の英単語なので綴り違いが 1 件も無く、このプロジェクトの造語である `under-review` だけが負けている。

**原因は `review-rules.md` の返却形式の節（Part 1 rule 4）にあった**。同じ JSON オブジェクトの兄弟フィールド `type` はそこで値を列挙しており、仕様外は 303 件中 2 件（0.7%）に留まる一方、`page_at_fault` は「cross-page エントリにだけ付く」としか書かれず、2 値は 240 行あまり後の check 8 の散文にしか無かった。同一文書・同一モデル・同一出力オブジェクトで、違いは返却形式の節が値を述べているかどうかだけである。**対処は rule 4 に 2 値を明記したこと**（`type` と同じ形。`rules_version` 3 → 4）。

**本スクリプトに検証は足していない**。`type` の低い drift 率は警告の産物ではない — 仕様外の `type` 2 件は警告が出たうえで記録に残っている。値を書くのはレビューサブエージェントで、警告が出る先は `record_review.py` を実行する orchestrator であり、両者は別のコンテキストにいるので警告は誰の行動も変えない。argparse の `choices` による強制も使えない（値は `--json` の中にあり、強制は「記録を書かない」か「フィールドを落とす」のどちらかで、いずれも仕様外の値より悪い）。**効果の測定にも警告は要らない** — 記録は受け取った値をそのまま持つので、rule 4 を直した後の記録（`rules_version: 4` 以降）を数えれば drift が残ったかが分かる。

**`this` / `self` を `under-review` へ正規化もしない**。仕様が静かに 4 値になるうえ、rule 4 が効けば新しい記録には現れなくなり、表を持つ理由自体が消える。効果を測ってから判断する。**既存の記録は書き換えない**（記録は不変。Issue #750）。

**「相手が悪い」（`other`）の行き先は本節の対象外**である。同じ調査で、告発した側が `RISKY:` に載り、最も告発された側は載らないことが分かっている（`RISKY:` は findings を `page_at_fault` を見ずに数える）。ただし告発先を引くには `page_at_fault` と `source_file` が信頼できる必要があり、いまはどちらも満たさないので、rule 4 の効果が出た後の実データで判断する。

**効果の測定（Issue #1384）**: パイロット 2 つ（ai-driven-dev-wiki・world-of-work-wiki）の記録を配布版ごとに数えた。`page_at_fault` の仕様外の値（`this` 52・`self` 23）、`type` の欠落 57 件、語彙外の `type` 6 件は、すべて 0.6.1・0.7.0 の記録だった。rule 4 を直した後の 0.8.0 以降の記録 756 件（0.8.0 が 687、0.9.0 が 8、0.10.0 が 61）では、どれも 0 件だった。正規化の表を持つ理由は無くなったので、本節の判断を維持した。同じ Issue で findings の欠落だけを拒むようにしたが、あちらは orchestrator 自身の誤りであり、エラーが直せる者に届く（`docs/DesignDoc-data.md` §4.8）。

## check_review_coverage.py

**docstring・コメントから経緯を移した（Issue #1329）**: 移す前後の行数は、総行数 851 → 687、コード 383 → 383、docstring 288 → 155、コメント 115 → 84、空行 65 → 65（docstring 内の空行は docstring に数える）。`Issue #` はコメント・docstring で 40 → 0。冒頭 docstring にあった仕様（各行がどの記録を読むか・閾値を持たないこと・孤児の記録を報告しないこと・改名と統合の扱い）は本文の同じ節にすべてあったため、docstring 側を消すだけにした。docstring・コメントにあって本節に無かった経緯は次のとおり:

- `--discarded-reason` は、`partial` 分岐が `## Failure Reason` を消すため生成失敗トラッキング Issue の理由欄が構造的に `unknown` になっていた問題（Issue #969）から生まれた
- `--discarded-reason` が `nargs="*"` なのは、Pass 1 で失敗したソース（`failed_pages` が空）も Step 9 の対象にした Issue #910 のため
- 破棄された記録で `round` を印字するのは、ラウンドごとに別の欠陥が出うる（Issue #571）ため
- 改名したページが古い slug の AI 記録を引き継ぐのは Issue #1162、翻訳ページが改名後に `STALE_REVIEW:` になる扱いは Issue #1246
- `kind: ai` の本文を `human_notes` に数えないのは、それが Pass 4 の非ブロッキングな観察（Issue #834）だから
- 翻訳ページの `translated_from` / `source_commit` を証拠として突き合わせるのは Issue #1031、`source_identity()` の照合キーは Issue #572 / #573 の命名規則と揃えたもの
- `ACCEPTED_PREFIXES` の 3 つ目は Issue #477 以前の `.wikicommit/wiki/` 接頭辞
- `/wikicommit-fix` の編集は `review_status` を `pending` に戻す（Issue #724）ので人の側は自己修正するが、機械の判定が失効したことを記録するのはこのスクリプトだけである

### 目的

`record_review.py` が書いた記録を読み戻す（Issue #750）。**消費者が同時に存在すること**が要件である（Issue #553）— 読む主体が無ければ、記録ツリーは常に空のまま残る受け皿になる。

1 つ目には `human_notes` が含まれる（Issue #952）— standing な human 記録のうち、**散文本文を持つ件数**である。数えるのは**有無であって中身ではない**（一語のコメントも長文も 1 件）。

**すべての行が「standing な記録」1 件を読む**（Issue #766）— そのページを**今の姿のまま判定した最新の記録**である。kind の別だけが行ごとに違う（`ai_reviewed` / `COVERAGE:` は AI、`human_reviewed` は human、`RISKY:` は kind を問わず、`STALE_REVIEW:` / `RETRACTED_EVIDENCE:` は AI）。唯一の例外は `SUMMARY: findings=` で、こちらは歴史的な量として全記録を合算する。

### `--discarded-reason` — 破棄されたページの理由を引く

`wikicommit-merge` Step 9 の生成失敗トラッキング Issue は、理由をソース管理ファイルの `## Failure Reason` から取る。ところが Pass 4 step 7 は**その節を `partial` 分岐で削除する**（`failed` ではないため。Issue #408）。そして `partial` こそが**普通の失敗の形**である — 1 ソースから複数エンティティを切り出す設計上、全件失敗は例外的であり、Step 9 が最も多く立てるのは `partial` 由来の Issue である。結果として理由欄は**構造的に必ず `unknown`** になり、同じ本文が「Investigate the failure reason above」と指示していた（設計が意図して消した理由を調査せよ、と言っていることになる）。

**理由自体は存在する** — 同じ実行が `.wikicommit/review/` に書いた `result: discarded` の記録に、完全な形で残っている。Issue #750 はこの記録を「**破棄されたページの記録こそ最も価値がある**」と明言しており、**書く側は既にそう設計されていて、読む側だけが繋がっていなかった**（Issue #452 は #750 より前に入ったため、当時は読む先が存在しなかった）。

**Step 9 のインライン Python に走査を足す案（検討事項 1 の (a)）は採らなかった。** 最新の判定は `record_sort_key()` が正であり（**素のファイル名の辞書順ではない** — 同一秒の衝突サフィックス `-2` が `-` < `.` のため未サフィックスより前に来る）、そのキーを共有しない実装は誤った「最新」を拾う。既存スクリプトに照会モードを足す形は Issue #928 が `check_retracted_sources.py --list` で採った先例と同型である。

**`source_file` を印字しない理由**: 実データのとおり `.wikicommit/.cache/ingest-fetch/…` という **gitignored なマシンローカルのキャッシュ**を指しており、別の clone・別のマシン・キャッシュ削除後には存在しない。ただし**どの種類のファイルか**は言う価値があるので、Issue #566 が確立したのと同じ判別子（`.wikicommit/entity/` ないし `.wikicommit/view/` 配下なら別のページ、それ以外ならソースの抽出テキスト）で `at lines <N-M> of the extracted source text` / `... of another page` と添える。

**記録が無い場合は `unknown` と書かない。** `NO_RECORD:` を返し、Step 9 は「理由は記録されていない」と書く。記録ツリー導入（Issue #750）より前の失敗と、`.wikicommit/review/` を持たない古いリポジトリがこれに当たる — **「理由が分からない」と「理由が記録されていない」は別のことであり**、後者は読み手に探しに行かなくてよいと伝える。

**`partial` 分岐が `## Failure Reason` を削除する設計自体は変えない**（検討事項 6 を明示的に退ける）。変えれば Step 9 は無改修で済むが、「`partial` は `failed` ではないので失敗理由を残さない」という Pass 4 の整理（Issue #408）を崩し、**同じ情報を 2 箇所に持つ**ことになる。

### 処理フロー

1. `.wikicommit/review/` が無ければ全 0 と `NOTE:` を出して終了する — 「まだ一度もレビューを記録していない」と「全部 0 だった」は別の状態であり、区別せずに 0 だけを出すと後者に見える
2. 各ページの記録ファイルを `record_review.py` の `record_sort_key()` 順（＝時刻順）に読む。**素のファイル名の辞書順ではない** — 同一秒の衝突サフィックス（`...-ai-2.md`）は `-` が `.` より小さいため `...-ai.md` の**前**に来るので、辞書順で最後のファイルを取ると「その秒の最も古い記録」を最新として拾う。書き手（採番）と読み手（最新の判定）が同じキーを共有する
3. **standing な記録（kind を問わない）が 1 件も無ければ** `UNREVIEWED:`。ほとんどの場合それは「記録が 1 件も無い」ことだが、**記録はあるが全件が `result: discarded` だった**場合も含む（Issue #766）— 破棄された判定は捨てられた下書きを見たものであり、ディスク上の本文について何も述べていない。後者では行に注記を添えて状態を区別する — 全件が `result: discarded` なら `(<N> record(s) exist, but every one was discarded; none judged the page as it now stands)`、そうでなければ `(<N> record(s) exist, but none carries a page_content_hash, so none judged the page as it now stands)`。**注記の理由は `result` から読む**（standing でなくした空ハッシュからではない）— 両者は `record_review.py` が書くものについては一致するが、このツリーは人間が手で書けることを意図している（Issue #750）ため、`page_content_hash` を持たない手書きの記録を「破棄された」と言うと、存在しなかった破棄を探しに行かせることになる
4. **書き出されたページを判定した最新の記録 1 件**（kind を問わず `page_content_hash` が非空のもの）を見て、その `attempts >= 2` または findings が 1 件以上あれば `RISKY:` — **これが抜取の設計図**である（Issue #760。下記コールアウト参照）
5. **書き出されたページを実際に判定した最新の `kind: ai` 記録**（`page_content_hash` が非空のもの）について失効を判定する。`result: discarded` の記録は空ハッシュを持ち、ディスク上のページについて何も述べていないため対象にしない — Pass 4 step 5 は `action: update` のエンティティに対しても`discarded` を記録し、そのとき既存ページはそのまま残る一方 `reviewed_sources` は `--sources-from`（＝取り込もうとしていたソース）から作られるので、ページ側に無いのが当然のソースと突き合わせて`source no longer on the page` を永久に報告し、しかも本当に有効な直前の判定を隠してしまう:
   - `page_content_hash` を再計算して不一致なら `STALE_REVIEW:`（`page content changed since <日付>`）。空ハッシュ（`discarded`）はスキップ
   - `reviewed_sources` の各エントリを現在のページの `sources[]` / `derived_from` と識別子（`url` / `path`）で突き合わせ、`hash` / `source_commit` が変わっていれば `STALE_REVIEW:`（`source changed: <識別子>`）、ページから消えていれば `source no longer on the page: <識別子>`
   - `reviewed_sources` に `status: retracted` のソース（Issue #737）が含まれていれば `RETRACTED_EVIDENCE:`
6. `SUMMARY:` と、モデルごとの `COVERAGE:` を出す。`ai_reviewed` / `human_reviewed` と `COVERAGE:` の `pages` / `findings` / `attempts>=2` はいずれも standing な記録から数える。`COVERAGE:` の 4 つ目の数（`<N> discarded`）だけは別で、**そのページの最新の AI 記録が `result: discarded` であり、かつそれをこのモデルが書いたページ数**を数える — standing な記録には現れない「投げ捨てられた試行」を、カバレッジを水増ししない位置に置くためのもの。**モデルごとの最新ではなくページごとの最新で判定する** — この数は「`RISKY:` が黙っている理由」を説明するために在るので、後から別のレビューが今の本文を判定していれば説明すべき沈黙自体が無く、追い越された破棄は数えない

> **`RISKY:` は履歴ではなく「今立っている判定」1 件だけを見る（Issue #760）**: 当初この行はそのページの**全記録**にわたって `max(attempts)` と findings 件数を集計していた。記録は不変で削除もされない（Issue #750 の設計の中核）ため、**一度でもリトライされた・一度でも指摘を受けたページは、その後どれだけクリーンに再レビューされても永久に `RISKY:` から外れない**。取り込みを続ける Wiki ではこの一覧が Wiki 全体へ収束していき、そうなった時点で何も選別していない — Issue #562 が低情報密度ガードを blocking から降格させたときと同じ力学である。
>
> **これは新しい方針の持ち込みではなく、同じ `main()` が既に持っていた 3 通りのうちどれに寄せるかの選択だった**。`COVERAGE:` は最新の AI 記録 1 件だけを見、`STALE_REVIEW:` / `RETRACTED_EVIDENCE:` は `standing_verdict()`（書き出されたページを判定した最新の AI 記録）を見る一方、`RISKY:` だけが全記録を見ていた。**Issue #760 の案 (b)（最新の判定のみ）を採る**。
>
> **Issue #760 が (b) の弱点として挙げた「『2 回目でようやく通った』という履歴が消える」は成立しない**。Pass 4 は 1 レビューにつき 1 記録を書き、その記録自身が `attempts` を持つ（全ラウンドの findings も `round` 付きでフラットに載る。`docs/DesignDoc-data.md` §4.8）。したがって 2 回目で通ったページの記録がそのまま standing な判定であり、`attempts: 2` は引き続き報告される — 落ちるのは**より新しいレビューが現在の本文を判定した後**だけであり、それはその履歴がページを説明しなくなった時点そのものである。
>
> **kind は問わない**（`standing_verdict()` ではなく新設の `standing_review()` を使う）。Issue #760 検討事項 1 が指摘するとおり `/wikicommit-review` は人間の判定にも `--result fail` と findings を書けるため、`kind: ai` に限ると人間の指摘が一度も `RISKY:` に出ないという、旧実装より悪い取りこぼしになる。**`STALE_REVIEW:` 側は `standing_verdict()`（AI のみ）のまま変えていない** — あちらが突き合わせるのは機械が見た `reviewed_sources` であり、Issue #760 のスコープ外である。
>
> **`result: discarded` の記録は数えない**（同 検討事項 2）。`page_content_hash` が空の記録は書き出されなかったページについての判定であり、ディスク上のページについて何も述べていない — `standing_review()` がそれを飛ばすことで、この論点は案 (b) と同時に決まる。
>
> **案 (c)（最後の人間レビュー以降に絞る）は独立した機構としては採らない**（同 検討事項 3）。人間レビューが一度も無い Wiki では (a) と同じに退化するうえ、「人間が読んだことを RISKY の抑制シグナルとして使えるか」は実データを見ないと決められない、と Issue #760 自身が述べている。ただし人間の記録も**後続のレビューとして普通に standing になりうる**ため、人がそのページを読んで `result: pass` を記録すれば結果として一覧から外れる — 新しい規則ではなく、同じ規則が一様に適用された帰結である。
>
> **`SUMMARY: findings=` は意図的に累積のまま**とする。あちらが答えるのは「この Wiki の一生でレビューが何件捕まえたか」という歴史的な量であり、現在の状態ではない。
>
> **既存の記録への遡及処理は行わない**（記録の不変性は Issue #750 の設計の中核）。変わるのは読み方だけであり、記録は 1 バイトも書き換えない。
>
> **閾値は導入していない**。本 Issue が問うたのは「どの記録を見るか」であって「何件から警告するか」ではない（下記「閾値・合否判定・自動化は入れない」はそのまま有効）。
>
> **そして 2 つの基準は独立していない — AI の記録に関しては実質 `attempts >= 2` 単独で動く（Issue #765）**: 上の手順 4 は `attempts >= 2` **または** findings >= 1 という OR だが、**この 2 項は独立に効かない**。finding が出れば FAIL し、再生成され、`attempts` が増える。逆に finding が無ければリトライする理由が無い。したがって、**AI レビューが書く記録に関しては** `attempts == 1` かつ findings を持つものはほとんど生じない（例外は下記の 2 経路）。
>
> `wikicommit/ai-driven-dev-wiki` の 28 ページ（29 記録・単一バッチ・単一日・単一モデル・`rules_version: 1`）を数えた実測（2026-09-12）では、`attempts == 1` かつ findings > 0 の記録は **0 件**であり、`RISKY:` の 12 件は「`attempts >= 2` の 12 件」と**完全に一致した**。
>
> **findings 側が独立に効く経路は 2 つある**。(1) `page_at_fault: "other"` しか持たないページ — あれは非ブロッキングで `result: PASS` のまま `issues[]` に載る（Issue #566）ため、リトライを起こさずに findings だけを増やせる。実測にも 1 件あったが、そのページは blocking な findings も持っており `attempts == 2` でもあったため、区別は付かなかった。(2) **人間のレビュー** — `wikicommit-review` Step 5 は再生成ループを持たず常に `--attempts 1` で記録するため、`--result fail` の記録は**必ず** `attempts == 1` かつ findings > 0 になる。これは `standing_review()` が `kind` を問わない理由そのもの（`kind: ai` に絞ると人間の findings を取り落とす。Issue #760）であり、`tests/test_check_review_coverage.py::test_a_human_finding_makes_a_page_risky` が CI で固定している。**下記のとおり実測ではこの経路が 0 件だったため、生じないのではなく測れていない。**
>
> **それでも OR を維持し、`attempts` と findings で扱いを分けない**（Issue #765 の決定）。分けるべき材料が実測から出なかったためであり、片方を落とせば上記 2 経路（とくに人間の findings）が消える。ここに書いてあるのは「2 つの基準がある」という読み方を実態に合わせるための注記であって、判定ロジックの変更ではない。
>
> **実測の限界**: 1 リポジトリ・1 バッチ・28 ページの観察であり、`human_reviewed` は 0 だった（そのリポジトリでは追跡 Issue を Close したときの同期経路自体が止まっていたため、**「人が読まなかった」ことを意味しない**）。**したがって上の経路 (2) は観測されえなかった** — 「`attempts >= 2` 単独で動く」という上の要約が当てはまるのは AI の記録に限られ、人間の記録が入りはじめた時点で当てはまらなくなる。あわせて「最後の人間レビュー以降に絞る」案（Issue #760 検討事項 3）は**不要と分かったのではなく測れなかった**ものとして、引き続き採らないまま残る。

**`RETRACTED_EVIDENCE:` と `check_retracted_sources.py` は二重報告ではない**（Issue #750 検討事項 7）。あちらは「取り下げ済みソースを `sources[]` になお持つ**ページ**」を報告する。こちらが言えるのは、`reviewed_sources` にしか無い情報 — **その取り下げ済みソースが、判定を下した時点で証拠として使われていたのか**（前者は判定自体が撤回された証拠に依っていたことを意味し、レビュー後に足された場合は意味しない）。

> **`discarded` の記録しか持たないページを、数えるのをやめて名指しする（Issue #766）**: Issue #760 が `RISKY:` を standing な判定 1 件に絞った結果、**`result: discarded` の記録しか持たないページがどの per-page 行にも現れなくなった** — `UNREVIEWED:` は「記録が 1 件も無い」ページだけを見ており、`RISKY:` も `STALE_REVIEW:` も破棄された記録を飛ばすためである。一方 `SUMMARY: ai_reviewed` と `COVERAGE:` は `latest_by_kind()` を使っており破棄された記録を飛ばさないので、**そのページは「レビュー済み」として数えられながら、ディスク上の本文を判定した記録は 1 件も無い**という状態になっていた。`COVERAGE:` が「1 pages with attempts>=2」と言うのに対応する `RISKY:` がどこにも無い、という食い違いも同じ原因である。到達経路は仮定ではない — `action: update` のエンティティで Pass 4 が `max_retries` を使い切ると既存ページはディスクに残ったまま `discarded` が記録され、そのページが記録ツリー導入より前に生成されていれば他の記録を持たない。
>
> **原因は 1 つで、`main()` が「このページの記録」を 3 通りの別々の定義で読んでいたことにある**。Issue #760 が `RISKY:` を standing へ寄せた後も、集計と `UNREVIEWED:` だけが「最新の AI 記録（判定していなくてもよい）」「記録が存在するか」という別の規則のまま取り残されていた。したがって採ったのは**定義を 1 本にすること**であり、Issue #766 が並べた案の (a)＋(b)＋(d) の組み合わせにあたる。
>
> | 案 | 採否 | 理由 |
> |---|---|---|
> | (a) `ai_reviewed` から除く | **採用** | 「レビュー済み」の分子は「今の本文を判定した記録があるページ」でなければ、カバレッジがそのまま過大表明になる |
> | (b) `UNREVIEWED:` に出す | **採用**（注記付き） | 下記 |
> | (c) `DISCARDED_ONLY:` 行を足す | 不採用 | 下記 |
> | (d) `COVERAGE:` も飛ばす | **採用**（`discarded` 列付き） | 下記 |
>
> **(b) と (c) は「行が出ないこと」を直す 2 案であり、決め手は per-page 行ではなく `wikicommit-status` Step 17 の側にある**。per-page 行はヒットが 0 なら 1 行も出ないので、`DISCARDED_ONLY:` を足すこと自体は静かである。しかし Step 17 はカテゴリごとに**必ず 1 行**を描画するため、(c) は「ほぼ常に 0」の 6 行目をレビューカバレッジ表示に恒久的に足すことになる（Issue #562 が名指しした、常時点灯する所見が読まれなくなる力学の裏返し — こちらは常時 0 の行が読まれなくなる）。(b) の弱点として Issue #766 が挙げた「`UNREVIEWED:` の現在の意味（記録が 1 件も無い）と食い違う」は、**行に注記を添えることで引き受けた**: 2 つの状態は「誰かがこのページを見なければならない」という同じ行動を要求するので 1 本の一覧でよく、注記があれば読み手は破棄が繰り返された方を区別して原因を追える。**注記を持つのは後者だけ**（`tests/test_check_review_coverage.py` が両方向を固定する）。
>
> **(d) の弱点（破棄された判定がモデル別の集計から丸ごと落ちる）は、`COVERAGE:` に 4 つ目の数を足して引き受けた**。`<N> discarded` は「そのページの最新の AI 記録が破棄されており、それを書いたのがこのモデルだったページ数」であり、standing な 3 つの数とは性質が違うことがその位置で分かる。これがあると、**`COVERAGE:` が静かな `RISKY:` と食い違って見えるのではなく、なぜ静かなのかを自分で説明する**。新しい行ではなく既存行の 1 列なので Step 17 の行数は 5 のまま変わらない。`SUMMARY: findings=` は Issue #766 のスコープ外の指示どおり**累積のまま**（破棄された判定の findings も数え続ける）であり、`COVERAGE:` に揃えていない。
>
> **`kind: human` の `discarded` は現時点で到達しない**（`--result discarded` を書く呼び出し元は `wikicommit-generate` Pass 4 と `wikicommit-synthesize` Step 5.5 の 2 つだけで、どちらも `--kind ai`）。それでも `human_reviewed` も standing で数えるようにしたのは、**挙動が 1 ビットも変わらない**一方で、Issue #766 が「構造上ある歪み」と名指しした非対称が残らないためである。
>
> **既存の記録への遡及処理は行わない**（記録の不変性は Issue #750 の設計の中核）。変わるのは読み方だけで、記録は 1 バイトも書き換えない。**閾値も導入していない**。

**統合によるリンクの書き換えを失効と数えない（Issue #1133）**: Issue #1119 の `rewrite_merged_links.py` は書き換えたページの `review_status` を保つが、`page_content_hash` は一致しなくなるため、書き換えた全ページが `STALE_REVIEW:` に出続けていた。`relations.yml` の統合の項目を逆にたどり、全置換で戻した版のハッシュも試す形にした（記録の形式は変えない）。経緯と退けた案は `docs/history/DesignDoc-data.md` §4.5.2「統合」。公開時のバナー（`convert_wikilinks.py`、Issue #751）は独自にハッシュを比較していたので、同じ `matches_recorded_content()` を使うよう揃えた — 片方だけ直すと、`/wikicommit-status` が失効と言わないページで公開側だけが判定を伏せる。

### `human_notes` — 経路 A の Close に一言が来たかを数える

`review-issue-close-sync.yml` は Close した本人の最新コメントを記録の散文本文にする（Issue #762）。**コメントが 1 件も無ければ本文なしの記録を書く** — 同 Issue が「沈黙して閉じるのは正常な閉じ方であり、失敗ではない」と定めた正規の分岐である。

**問題は、来ても来なくても他のどの出力も同じに見えることだった。** `wikicommit/ai-driven-dev-wiki` でコメント無し 2 件・コメント付き 1 件を Close した実測では、ワークフローの全ステップ・`review_status`・`reviewed_by`・`deploy.yml` の再ビルド・公開バナーの読了行・`human_reviewed` の計上が**全件同一**で、違いは記録の散文本文が空であることだけだった。

**数える理由は 1 つに絞れる。** `docs/DesignDoc-pipeline.md` §6.3 自身が「委任された Close 権限は機械では担保できない」と認めており、`Read by <login>` はこのプロジェクトの中心的な主張（Issue #800 の (1)）である。`reviewed_by` も `Reviewed-by:` トレーラーも「誰が閉じたか」しか言わず、**記録の散文本文だけが「読んだ」ことの痕跡**になる。`human_reviewed` はその 3 件が何かに裏づけられているかを読めない。

**置き場が `COVERAGE:` ではなく `SUMMARY:` なのは構造による。** `COVERAGE:` は `standing_ai.get("model")` で束ねた**モデル別**の行だが、`kind: human` の記録は `model` を持たない（`record_review.py` は human に `reviewer` を書き、`--model` を必須にするのは `--kind ai` の側だけである）— 載せる先が無い。`SUMMARY:` は既に `human_reviewed` を持っており、数えたいのはその内訳である。**行は 1 本も増えず、キーが 1 つ増えるだけ**なので、Issue #864 の「行を増やさず列を足す」形は保たれる。

**3 つの規範のいずれにも当たらない**: Issue #553（frontmatter のキーも語彙も増えない。数えるのはディスク上に既にある事実で、消費者は `/wikicommit-status` を読む運用者として同時に存在する）・Issue #562 / #864 / #867（per-page 行にしないので Step 17 の行数は変わらない）・Issue #834 / #866（あの 2 度が拒んだのは観察の**中身**の構造化であり、ここで数えるのは**有無**である）。

### 既知の限界

1. **一語のコメントも長文も同じ 1 件である。** 測れるのは「**依頼が届いたか**」であって「読まれたか」ではない
2. **`RISKY:` の選定が機能しているかは測れない。** それに要るのは件数ではなく**本文の中身と `RISKY:` の対応**であり、人が読んで初めて分かる。Issue #765 が closed の時点で残した限界（人間側は「生じないのではなく測れていない」）はそのまま残る
3. **「引っかかった」は引き続き記録されない。** `review-issue-close-sync.yml` は `--result pass` を固定で渡す（`docs/DesignDoc-pipeline.md` §6.3）

**孤児の記録は報告しない**（Issue #750 検討事項 3）。ページが削除されても記録は残す方針のため、実在しないページの記録が蓄積する。報告するか放置するかは実データが溜まってから決める — 今それを足すと、誰も求めていないものと引き換えに毎回 1 行増える。

**閾値・合否判定・自動化は入れない**。実測が無い状態で決めた閾値は推測にすぎない。人が `RISKY:` / `COVERAGE:` を読んで `/wikicommit-generate --regenerate`（Issue #578）を叩けばループは人力で閉じる。

## record_run.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 687 → 678、コード 309 → 309、docstring 225 → 220、コメント 87 → 83、空行 66 → 66（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 29 → 0（`Issue` の付かない `#452`・`#474` と、行をまたいで `Issue` と分かれた `#567`・`#574`・`#911` も外した）。出力する文字列には `#NNN` は無い。

docstring の `end` の段落は「`end` はこのファイル唯一の read-modify-write」と書いていた。`checkpoint` も同じ形を採る（下の「read-modify-write のコスト」）ので、本文の節に合わせて「`end` と `checkpoint` は read-modify-write」と書き直した。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 実行 1 回を単位とする記録（このスクリプト）と `KEEP_RECORDS` の件数によるローテーションは Issue #790。1 イベント 1 記録・追記せず新規作成という形はレビュー記録（Issue #750）のもので、レビュー記録を公開サイトに表示するのは Issue #751
- 「実行は完走したか」の段落の、途中で死んだ実行と見分けが付かない滞留は Issue #567 が扱ったもの（キューがそこまで到達しなかった）。ファイルを 1 つも変えずに止まる halt の 2 経路は、ガード C が Issue #574、`rules_version` 不一致が Issue #752
- 「どれだけかかったか」について、パイロットの手順には書かれたときから「リポジトリあたりの所要時間」の列が空のまま残っていた
- `schemaorg-vocab.json` を `.wikicommit/.cache/` の外に出したのは Issue #319
- 終了の打刻忘れ（長い多段フローの末尾の手順が落ちる）は、Issue #406・#452・#474 がそれぞれ一度ずつ直した失敗の形。`page_content_hash: ""` を「ページが書かれなかった」とする形は Issue #750
- read-modify-write はレビュー記録（Issue #750）が意図的に避けた形。`config.yml` が YAML の round-trip でコメントの記入例を丸ごと失ったのは Issue #713
- コスト・トークン数を記録しないのは、Issue #784 が同じ理由で配布ファイルから課金の数字を外したのに揃えたもの
- `checkpoint`・`EXPECTED_PASSES`・空の `passes: []` を `start` が書くこと・照合の第三者をスクリプト自身とすること（`pass_files_for()` が照合先を引数で受け取らない）は Issue #797。Issue #406・#452・#474 は同じクラス（長い多段フローの末尾の手順が黙って走らない）で、3 件とも公開済みのパイロットリポジトリを人が後から監査して見つけ、3 件とも手順を決定論的スクリプトへ委譲して直した。サブエージェントが読んだことを照合できたのは Issue #752 で、`wikicommit-review` はサブエージェントを使わないので照合が効かないという限界も同じ Issue が記録している
- `check_run_records.py` が消費者であることは、消費者の無い受け皿を Issue #553 が退けているため
- `REGENERATE_PASSES` の `--regenerate`（Pass 2 を実行しない）は Issue #578
- パスファイルを `references/` に置くのは Issue #911。「`--token` を送る呼び出し元がまだ無いので動かしてよい」というのが Issue #911 の挙げた理由だったが、それは誤りだった（Issue #925）。インストール済みの wiki は `.claude/skills/` と `.wikicommit/scripts/` を別のコマンドで更新するので、トークンを送る Skill と古いディレクトリを見るスクリプトが並びうる。その移動はほかの理由でも安全ではなかった — 移動の時点で、古いディレクトリを見るスクリプトの版を持つインストール済みの wiki がすでにあった
- `token:` に消費者を与えるのを `mismatch` を持つ記録が実在するまで見送るのは Issue #925
- `allocate_run_path()` がスタンプを既存の最新記録まで切り上げるのは Issue #991（`record_review.py` の `allocate_record_path()` と同じ欠陥・同じ修正）
- Skill ツリーを `.agents/skills/` にも探すのは Issue #1021

### 目的

このリポジトリの記録層は 4 つあり、**そのすべてが成果物を単位にしている** — git 履歴はファイル、ソース管理ファイルはソース 1 件、レビュー記録（Issue #750）はレビュー 1 件、追跡 Issue はページ 1 枚。**実行 1 回を単位とする記録が無い**ため、次の 3 つに答えられなかった（Issue #790）。

### git で追跡しない

レビュー記録を追跡した 3 つの理由は、いずれも実行記録には当てはまらない。

追跡する代償は実在する: generate のたびに 1 ファイルが PR へ混ざり、**git では削除に意味がないため保持期間を決められない**。追跡しないことで、ローテーションが可能になり、`wikicommit-merge` は無改修で済み、lychee / markdownlint のスコープ確認も要らない（`git diff` に一切現れないため）。

**`.wikicommit/.cache/` には入れない**。あそこは再構築できる派生データ（`search_index.sqlite3`）の置き場であり、実行記録は再構築できない。Issue #319 が `schemaorg-vocab.json` をそこから出したのは、この鏡像の理由（「気軽に消してよい」という名前の含意と実際の性質のずれ）による。

代わりに諦めるもの（いずれも受け入れる）: クラウドセッションの記録は VM とともに消える（その実行の未コミット成果物も同時に消えるので整合する）、clone 先からは見えない、「このページはいつ作られたか」は**区間**としてしか答えられない — ただし上記のとおり点の時刻はそもそも存在しないので、追跡しても得られるのは区間だけだった。

### 記録のフォーマット（`.wikicommit/run/<YYYYMMDD>-<HHMMSS>-<skill>.md`）

**本文は常に空である。** 他の `.md` 記録（`## Summary`・`## Failure Reason`・レビュー記録の散文）はいずれも frontmatter で表せないものを本文に持つが、実行記録は全項目がスカラーかリストで本文に書くことがない。JSON も検討したが**他の記録に形を揃える**方を採った。空いているから何か書く、を誘わないため、本文を持たないことをここに明記する。

**`ended_at` の空文字列が「閉じられなかった」の信号である**（Issue #750 が `page_content_hash: ""` を「ページが書かれなかった」と定義したのと同じ形）。長い多段フローの末尾で終了の打刻を忘れるのは Issue #406 / #452 / #474 が繰り返し踏んだクラスだが、**ここでは直す必要がない** — 開始があって終了が無い記録は、そのまま問い 2 の答えの片方になる。

**ただし問い 2（実行は完走したか）はこのフィールド 1 つでは決まらない**。halt の 2 経路（ガード C〈Issue #574〉・`rules_version` 不一致〈Issue #752〉）は `end --halted-reason` で記録を**閉じる**ため `ended_at` を持つ。読み手側の述語は `check_run_records.py` の `finished_normally()`（閉じていて、かつ halt していない）であり、経緯は同スクリプトの節「halt して閉じた実行も `INCOMPLETE_RUN:` に出る」を参照（Issue #872）。**新しい消費者を書くときに `ended_at` だけを見ないこと** — それが Issue #872 が直した誤りそのものである。

`end` はこのファイル唯一の read-modify-write であり、Issue #750 が意図的に避けた形である。ここで安全なのは一般化しない理由による: 実行記録は本文もコメントも持たないため YAML の round-trip で失うものが無い（`config.yml` はまさにそれでコメント記入例を丸ごと失った。Issue #713）。

### `checkpoint` — 実行の**どこまで**を残す

> **`wikicommit-generate` の打点は、Issue #1085 以降 `driver.py` が書く。** 工程の定義で `stamp: true` の工程が `done` で完了したとき、ドライバーが `make_stamp()` で同じ形の打点を `passes` に足す。打点は工程の**入口**ではなく**完了**の時刻になり、トークンの照合は `done` で行われて合わなければ工程を完了にしない（下記の「exit 1 は実行を止めない」「`token:` の 4 値を読む機械は無い」という限界は、ドライバー経由の実行では解消する — 照合の失敗が、その工程を完了にしない理由として実際に使われる）。`record_run.py checkpoint` 自体は残り、ドライバーを使わない呼び出し元のために動く。記録の開き方も `open_record()` を共有するので、`check_run_records.py` は変更なしで両方を読む。

`ended_at` が答えるのは実行**全体**の生死だけで、その内側で何が起きたかには答えない。空いていた 2 つの問いはどちらもこのリポジトリが実際に払ったコストである:

| 問い | checkpoint 以前 | checkpoint 後 |
|---|---|---|
| どこで止まったか | `ended_at` が空、としか言えない。ガード C（Issue #574）・`rules_version` 不一致（Issue #752）は**ファイルを 1 つも変えずに止まる**ため run 記録が唯一の痕跡で、その痕跡が位置を持たなかった | **最後に到達したパスが残る** |
| パスが丸ごと飛ばされたか | 検出不能。Issue #406 / #452 / #474 は同一のクラス（長い多段フローの末尾で手順が落ちる）で、**3 件とも公開済みパイロットを人が手で監査して初めて見つかった** | **打点の欠落として検出** |

3 件とも解決策は「決定論的スクリプトへの委譲」だったが、**委譲したスクリプトを呼ぶ手順そのものが落ちた場合は同じ形で再発する**。打点はその 1 段外側に立つ。

#### 照合の第三者はスクリプト自身である

Issue #752 が `rules_version` の echo 検証を成立させられたのは、サブエージェントが JSON を返し orchestrator がそれを照合するという **2 者**がいたためで、同 Issue 自身が「`wikicommit-review` はサブエージェントを使わないため echo 検証が効かない」と限界を明記している。単一エージェントでは「自分が読んだと自分に申告する」だけになり何も検証しない。

`--token` を渡すと `record_run.py` が `<Skill ツリー>/<skill>/references/<pass>.md`（Skill ツリーは `.claude/skills` → `.agents/skills` の順に探す。Issue #1021。どちらかの写しが裏づければ `ok`）を**自分でディスクから開いて** frontmatter の `pass_token` と突き合わせる。**照合先のパスは引数で受け取らない** — 呼び出し側がファイルを指定できるなら、自分で書いたファイルを指すこともできてしまい、第三者性が消える。

**`--token` は SKILL.md のパス分割（進行的開示）を前提とする**が、本機能はその分割に依存しない — パスファイルが無い段階では `--token` を渡さず `--pass` だけで打点し、上表の上 2 行はそれで成立する。3 行目だけが分割後に効くようになる。

**`token:` の 4 値を読む機械は 1 つも無い**（`check_run_records.py` は `token` を読まず、`MISSING_PASS:` が見るのは打点の**有無**だけである）。したがって照合の失敗が届く先は exit 1 だけであり、それを受け取るのは**その照合が対象にしているエージェント自身**である — Issue #752 が `rules_version` について明示した限界（単一のエージェントが自分に対して読んだと申告しても何も検証しない）に、判定の返り先の側から戻ることになる。上の契約はこの exit 1 を無効化するので、結果として `mismatch` は記録されるが誰にも報告されない。

**`token:` に消費者を与える**（`/wikicommit-status` が人間に報告する）のがこの問いの残り半分だが、**いまは作らない** — `token: mismatch` を持つ実行記録がまだ 1 件も存在せず（`--token` を送る呼び出し元ができたのは Issue #911 であり、その後の記録が蓄積していない）、報告の形も閾値も実測なしに決めることになる。Issue #669 が `chain_of_thought` について採った基準（効果を測る手段が無い一方でコストは確実に発生する）がそのまま当たる。**再開の条件は「`token: mismatch` を持つ記録が実在したとき」**であり、そのときには実データが最初から揃っている（Issue #925）。

#### read-modify-write のコスト

`end` は Issue #790 が「このファイル唯一の read-modify-write」としていたが、打点も同じ形を採るため回数が増える。**ソース 5 件 × パス 5 つ ＝ 25 回で実測 1.27 秒（1 回あたり約 51 ms）、記録ファイルは約 2.5 KB。** Issue #790 が RMW を許した根拠（実行記録は本文もコメントも持たないので YAML の round-trip で失うものが無い）は回数によらず成立し、実行時間の大半は LLM 推論であるため相対的な影響は無い。

#### 既知の限界: compaction は打点の指示を落としうる

打点忘れの誤りの向きは `ended_at` と同じで安全側である（打たなければ「実行されていない」と報告され、逆は起こらない）。ただしこれは**打点の指示がコンテキストに残っていること**に依存する — 分割前の `wikicommit-generate/SKILL.md` では Pass 2 以降の打点指示がファイル冒頭から遠く、context compaction がそれを落としたまま実行が続きうる。その場合、実際には走ったパスが `MISSING_PASS:` として報告される（偽陽性）。この非対称は SKILL.md のパスごとの分割が入るまで残る。SKILL.md 側にも同じ限界を明記してある。

**クラウドセッションでは記録が VM とともに消える**（Issue #790 が明記した代償）。そして無人実行こそ compaction をいちばん踏む経路であり、**検証手段がいちばん検証したい環境で残らない**。git 追跡対象にする案は Issue #790 が理由を挙げて退けているため蒸し返さず、代わりに `wikicommit-generate` の Completion Notice が打点の要約を 1 行出す（PR 本文経由でそこだけは残る）。

### ローテーション

> **その順序が壁時計に依存していたため、後方ステップで最新の実行を削除しうる状態だった（Issue #991）**。`allocate_run_path()` は `datetime.now()` のスタンプをそのまま使っており、ホストが時計を後方へ動かすコンテナでは連続する 2 件が逆順のスタンプを得る。現在は**そのディレクトリに既にある最新記録まで切り上げてから採番する**（`record_review.py` の `allocate_record_path()` とまったく同じ形。決定の全体は `docs/DesignDoc-data.md` §4.8）。**採番はファイル名ではなくスタンプを見る**（`next_seq()`）— skill スラッグは `run_sort_key()` の一部ではないため、`generate` の隣へ切り上げた `merge` の記録は空いている `<stamp>-merge.md` を取って**同値になり**、安定ソートである `sorted()` は `LAST_RUN:` の選択もこのローテーションの削除対象も `glob()` の順に委ねてしまう。同じ理由で、ローテーションがそのスタンプの seq 1 を削って空けた未サフィックスの名前も再利用しない（再利用すると最新の実行が最古の位置に着地する）。こちらの影響が一段重いのは、`run_sort_key()` が `LAST_RUN:` の選択だけでなく**このローテーションが何を消すか**も決めるためである。

## skill_workflow.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 1,106 → 1,106、コード 731 → 731、docstring 197 → 197、コメント 30 → 30、空行 148 → 148（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 7 → 0（`Issue` の付かない `#406`・`#474`・`#452`・`#947` も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このエンジンは Issue #1085。「Skill workflow」という呼び名（CI のワークフローと区別する）と、`driver.py` からの改名・状態のキーを `driver:` から `workflow:` に替えたことは Issue #1203
- docstring は、長い Skill をそれまで記憶で進めていた（エージェントが手順全体を読み、どこにいるかを覚えていた）と書き、公開パイロットで見つかった失敗がすべてその形だった例として、末尾の手順が走らなかった（#406）・書き戻しが起きなかった（#474）・結果が渡されなかった（#452）・散文だけだったため即興になった（#947）を挙げていた
- 定義ファイルとそのハッシュのフィールドは Issue #1209 まで `workflow` / `workflow_sha256` だった

> **`human` 工程の `finishes_on` と `check-merge --except-run`（Issue #1094）**: `wikicommit-merge` をドライバーに載せたときに足した 2 つで、どちらも merge 固有の知識ではなく形の一般化である。前者は Step 3 の warning の続行確認で利用者が「やめる」と答えた場合のためにある — 以前の merge はこの場合、実行記録を開いたまま中断していたが、利用者が決めて止めた実行を `INCOMPLETE_RUN:` に数える理由は無く、`finish_if_empty`（「No changes to merge」）と同じく正常な終わりとして閉じる。halt を流用する案は、`check_run_records.py` が失敗と区別できなくなるため採らなかった。後者は、Issue #1085 の時点では merge が `record_run.py start` で記録を開いていて `driver:` キーを持たず、`open_runs()` に現れなかったため要らなかった。merge 自身がドライバーで進むようになると、自分の実行が開いたまま `check-merge` を呼ぶことになる。merge の工程は `TOUCHED:` を出さないので今の定義では重ならないが、それに頼ると「merge の確認スクリプトが `TOUCHED:` を出したら自分を止める」という離れた不変条件が生まれるため、名指しで除く形にした。
>
> **状態の中の定義ファイルのフィールドを `workflow` → `definition` に改名（Issue #1209）**: Issue #1203 が状態キーを `driver:` → `workflow:` にした結果、状態が自前の `workflow`（定義ファイルのパス）を持って `record["workflow"]["workflow"]` という入れ子ができた（PR #1205 のコードレビューの指摘）。3 案を比べた — (1) 現状のまま用語を DesignDoc に明記する: 読み違えの余地が残る。(2) 状態キーを `workflow_state:` などに変える: PR #1205 が決めたばかりのディスク上の形式を変え、旧キーが `driver:`・`workflow:` の 2 つになって、共有モジュールも使う `run_state()` が 3 キーを試すことになる。(3) 状態の中のフィールドを `definition` / `definition_sha256` に変える: 読み替えがエンジンの `load_run()` の中で閉じ、確認スクリプトの側（状態キー名を持たない）に影響しない。(3) を採った。旧フィールド名の記録は状態キーが `workflow:` でも `driver:` でも `next` で再開でき、次の書き込みで新しい名前へ移ることを `tests/test_skill_workflow.py` が確かめる。

## check_run_records.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 395 → 389、コード 153 → 153、docstring 178 → 172、コメント 24 → 24、空行 40 → 40（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 18 → 0（`Issue` の付かない `#452`・`#474` も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #790。消費者の無い受け皿は Issue #553 が退ける形
- `INCOMPLETE_RUN:` の段落の、まだ順番が来ていない滞留は Issue #567、halt の 2 経路はガード C が Issue #574・`rules_version` 不一致が Issue #752。halt は `ended_at` が「完走した」の代理指標だった間、完走側に落ちていた（`end --halted-reason` が `ended_at` を書くため。Issue #872）
- `MISSING_PASS:` は Issue #406・#452・#474 の形 — 3 件とも長いフローの末尾の手順が黙って走らなかったもので、3 件とも公開済みのリポジトリを人が後から監査して見つけた（Issue #797）
- `passes` キーを持たない記録は Issue #797 より前に書かれたもの。`passes: []` を報告するのは Issue #864 で、部分的な欠落だけを報告していた間は、失敗が全面的なところでこの行が沈黙していた。`passes: []` を「打点より前の記録」として扱うことが、まさにその場合を隠していた
- `has_checkpoints()` の docstring は、ガード C の halt をこの門番の例に挙げていた。Issue #872 からガード C の halt は `halted_reason` を持つので `finished_normally` ではなく、この門番に到達しない
- `work_recorded()` の「常時点灯する行は読まれなくなる」は、Issue #562 が低情報密度ガードを降格させたときに量った力学
- `finished_normally()`・`describe_last()` が halt に 1 語添えること・`main()` が述語を共有して `MISSING_PASS:` から halt を外すことは Issue #872。`ended_at` が「完走した」の代わりを務めていた間、halt は完走側に落ちて `MISSING_PASS:` に「finished, but ... left no stamp」と出ていた。`describe_incomplete()` の docstring は、`end --halted-reason` が `ended_at` を書き続ける理由（halt までの経過時間）を同じ Issue に結び付けていた

### 目的

`record_run.py` が書いた記録を読み戻す。**消費者が同時に存在すること**が要件である（Issue #553）— 読む主体が無ければ、記録ツリーは常に空のまま残る受け皿になる。

**3 行とも `wikicommit-status` Step 14 が読み、Step 17 が 1 行ずつ表示する**（Issue #835）。`MISSING_PASS:` だけは配線されておらず、計算された結果がそのまま捨てられていた — 落ちていたのは Issue #797 が答えようとした 2 つの問いのうち「パスが丸ごと飛ばされたか」の側であり、それは Issue #406 / #452 / #474 が 3 度繰り返した失敗クラスに対する検出そのものである。`tests/test_run_record_surface_wiring.py` が、このスクリプトが stdout に出す全接頭辞を SKILL.md が参照していることを CI で固定する（書く側と読む側が別ファイルにあり、片方だけ足しても何も壊れないため）。

**`passes` キーを持たない記録については、パスについて何も出力しない**。Issue #797 以前に書かれた記録がこれに当たり、報告のしようがない。

**一方 `passes: []`（打点が 1 つも無い）は報告する（Issue #864）**。2 つは別の状態であり、`start` が空リストを**明示的に**書くのはまさにそれを区別するためだが、判定が `has_checkpoints()`（打点が 1 件以上あるか）を門番にしていたため両方が同じ側に落ちていた。**結果として最悪のケースだけが報告されなかった** — context compaction が落とす範囲は「一部のパス」とは限らず、全部落ちれば記録は `passes: []` になり `missing_pass=0` と表示される。部分的に落ちたときだけ報告され、全部落ちたときは沈黙する、という向きである（唯一の痕跡は `LAST_RUN:` が `<N> pass(es)` の区画を落とすことだが、同行は 1 件しか出さない）。現在は `records_passes()` が `passes` キーの有無で判定する。

**ただし zero-stamp の記録は「その実行が実際に何かをした」ことが記録から読めるときだけ報告する**（`work_recorded()`。`sources` / `pages` が非空、または `outcome` に 0 でない値がある）。門番が要るのは、**打点ゼロで完走するのが正常かつ最も普通な経路が実在する**ためである — 引数なしの `/wikicommit-generate` は処理対象の管理ファイルが 1 件も無ければ「No management files to process」と言って終了し（Pass 1 手順 2）、最新状態の Wiki ではそれが通常の結末になる。無条件に報告すると大半の実行でこの行が点灯し、常時点灯する行は読まれなくなる（Issue #562 が低情報密度ガードを降格させたときと同じ力学）。Step 0 で止まった実行も `sources` / `pages` / `outcome` のいずれも記録していないため、専用の規則なしにこの門番で落ちる。

**打点しない Skill に対する誤検知は構造的に起こらない**（Issue #864 の検討事項 2）。`expected_passes()` は `EXPECTED_PASSES` に無い Skill に対して `()` を返し、報告の条件は `missing_passes()` が非空であることを要求するため、`wikicommit-translate` / `wikicommit-synthesize` / `wikicommit-merge` の `passes: []` は行を 1 本も出さない。将来 `EXPECTED_PASSES` に Skill を追加したときに初めてこの軸が効きはじめる、という意味でも既存の仕組みに乗っている。

**halt して閉じた実行も `INCOMPLETE_RUN:` に出る（Issue #872）**。halt の 2 経路（ガード C〈Issue #574〉・`rules_version` 不一致〈Issue #752〉）は `record_run.py end --halted-reason` で記録を**閉じる**ため `ended_at` を持つ。`ended_at` を「完走したか」の代理指標にしていた間、halt は完走側に落ち、**2 通りに割れていた** — 打点に欠落が残る場合は `MISSING_PASS:` に `finished, but ...` として出て（halt に対して "finished" は偽であり、Pass 2c 以降に到達しないのは halt の意味そのものであって「飛ばした」ではない）、欠落が無い場合は 1 行も出なかった。とくに後者は構造的で、`EXPECTED_PASSES` は `wikicommit-generate` の 1 エントリしか持たないため、**`wikicommit-synthesize` / `wikicommit-translate` / `wikicommit-merge` の halt は期待パスが空 ＝ 欠落も空となり、`MISSING_PASS:` に出る余地が原理的に無い**。

**直したのは代理指標そのものである**。`finished_normally()` が「閉じていて、かつ halt していない」を判定し、`INCOMPLETE_RUN:` と `MISSING_PASS:` の両方をそこから導く — `MISSING_PASS:` 側から halt を外す分岐は書かない（同じ述語から自動的に落ちる）。判定材料は `halted_reason` だけなので、`EXPECTED_PASSES` を持たない Skill の halt も同じ 1 行が覆う。

**`HALTED_RUN:` は新設しない**。(1) 述語が 2 つになり、手編集で `halted_reason` を持ち `ended_at` が空の記録は両方の行に出るため優先規則が要る、(2) `wikicommit-status` Step 17 の run 行が 3 → 4 になり、しかもほぼ常に 0 の行になる（Issue #864 が「列を足して行数を保つ」を選び、Issue #867 が `POLICY_DRIFT:` の 1 行を退けたのと同じ力学）、(3) 意味の上でも 3 行は「直近」「正常に完走しなかった」「正常に完走したが飛ばした」に答えており、halt は 2 番目に属する。**`end --halted-reason` が `ended_at` を書かない形にもしない** — やることは同じなのに halt までの所要時間が失われる。ガード C の halt（取得前・即座）と `rules_version` 不一致の halt（Pass 4 到達後）は経過時間が桁違いであり、そこが読めなくなる代償に見合わない。

**打刻忘れもここに出る**。これは欠陥ではなく上記の「誤りの向き」の帰結として受け入れる。

### 既知の限界

**打点の欠落は、パスが走らなかったことの間接的な証拠にすぎない**。指示が context compaction で落ちれば、走ったパスも打点を残さない（`record_run.py` の同名の節を参照）。誤りの向きは安全側 — 本当に飛ばされたパスが「走った」と報告されることはない — だが、`MISSING_PASS:` の偽陽性は SKILL.md のパス分割が入るまで残る。

**zero-stamp の報告は `end` が仕事を記録していることに依存する**（Issue #864）。compaction が打点の指示を落とす実行では、同じく末尾にある `end` の `--source` / `--page` / `--outcome` も落ちうる — フラグを 1 つも付けずに閉じられた記録は `work_recorded()` が偽になり、引き続き報告されない。`end` 自体が呼ばれなければ `ended_at` が空になり `INCOMPLETE_RUN:` が拾うため、**取りこぼしが残るのは「`end` は呼ばれたがフラグが全部落ちた」という 1 通りに絞られる**。指示上は `end` とそのフラグが同じ 1 行にあるため、この組み合わせは起こりにくい。**`wikicommit-status` Step 14 の説明はこの取りこぼしを明記する** — `missing_pass=0` が「パスを飛ばしていない」ことの証明ではない、と運用者が読む側に書いておく必要があるのは、`docs/` が配布されないためである。

**途中で halt した実行が `MISSING_PASS:` に「finished」と書かれる問題は、Issue #872 が解消した**（同 Issue はここから切り出した草案である）。`end --halted-reason` は `ended_at` を書くため、当時 halt した実行は `INCOMPLETE_RUN:`（`ended_at` が空であることを条件としていた）ではなく完走側に落ち、打点が 1 件以上あれば「finished, but … left no stamp」と報告されていた。現在は `finished_normally()` が判定を担い、halt は `INCOMPLETE_RUN:` に出る（上記「halt して閉じた実行も…」参照）。zero-stamp 側の報告とは干渉しない — guard C / `rules_version` の halt はいずれも `halted_reason` を持つため、`MISSING_PASS:` の門番に到達しない。

## check_retracted_sources.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 224 → 224、コード 86 → 86、docstring 109 → 109、コメント 9 → 9、空行 20 → 20（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 10 → 0（うち 1 つは行をまたいで `Issue` と `#918` が分かれたもの。`Issue #572 / #573` の並記の 2 つ目も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトと「報告して止める」判断は Issue #737。Issue #737 は、レビュー追跡 Issue のテンプレートがページのソースの健全さを問わないことから始まった
- `review_status` を戻さない理由に挙げた規則（内容が変わったかを決定論的なスクリプトに委ねる）は Issue #724
- `--regenerate` が取り下げたソースを `sources[]` から落とすのは Issue #744
- view ページの間接参照を `wikicommit-synthesize` に読ませない理由の「参照側の 3 つ目の解釈者」は Issue #553
- `--list` は Issue #928。`resolve_source_cache_path.py` の取り下げのガードは Issue #918 で、`/wikicommit-review` と `/wikicommit-fix` はそこを通らないため、取り下げたソースを正しいものとして読んでいた
- 識別子の照合を `add_source.py` と揃える（`source.path` / `source.url`）のは Issue #572 / #573

### 目的

`status: retracted`（Issue #737）は、人間が登録済みのソースを読み、内容が信用できないと判断して以後の取り込み対象から外したことを表す。この値を書くと**そのソースが再び取り込まれることは構造的に止まる**（`add_source.py` が `RETRACTED` を返して再登録せず、`check_ingest_freshness.py` が `outdated` へ書き戻さない）が、**既にそのソースから書かれたページには何も起こらない** — それらは `sources[]` にそのソースを持ったまま、何の印も付かずに残る。本スクリプトはその穴を、**行動ではなく報告で**塞ぐ。

- **`review_status` を `pending` に戻す案は Issue #724 の規範と噛み合わない**。あちらは「内容が実際に変わったか」を決定論的スクリプト（`reset_review_on_content_change.py`）に委譲し、人間のレビューが要るか否かを非決定論的な判定に委ねないと明記した。取り下げでは**内容が変わらない** — 変わるのはその内容の根拠であり、同じ機構では表現できない
- **戻しても何が失われたかは伝わらない**。追跡 Issue のテンプレートは `sources` の妥当性を問わない（Issue #737 の出発点そのもの）ため、`pending` は「読み直せ」とは言うが「何を直せ」を言わない

そのページに対して既存 3 経路のどれを使うかは人間の判断であり、本スクリプトの役目はその判断材料を出すことに尽きる（Issue #713 が `/wikicommit-update` で採ったのと同じ形）: 残りのソースで作り直すなら `/wikicommit-generate --regenerate`（Issue #744 が取り下げたソースを落として作り直す挙動を入れた。残りが 1 件以上あることが条件。ただし再生成モードは `sources[].type: manual` を 1 件でも持つページを除外する一方、この「残り件数」は `manual` エントリを 1 件として数えるため、残りが `manual` のみのページは `/wikicommit-fix` に回る）、記述を手で直すなら `/wikicommit-fix`、ページごと下ろすなら `/wikicommit-remove`。**所見に添える「残りのソース件数」がこの選択を決める数**である。

### `--list` — 参照側 2 経路のためのガード

**新しいスクリプトを作らずここに足した理由**は `docs/DesignDoc-data.md` §4.3「`retracted`」の参照側のガードにある（要点: 判定は既にこのファイルにあり、同一性キーの規則〈Issue #572 / #573〉の写しを増やさない。§11.5 の置き場所の規則もこれで満たされる）。**ルックアップにはしない** — 識別子を受け取って 1 件を答える形は `check_*` の「走査して報告する」という形から外れる。突き合わせは呼び出し側が行う。

**呼び出し側はこのモードが無い場合に止まってはならない**。`.wikicommit/scripts/` が古いリポジトリには存在せず、その場合の劣化は「Issue #928 より前の挙動に戻る」だけである。ただし無言で劣化させず、その旨を報告して続行する（`docs/DesignDoc-data.md` §4.3）。

### view ツリーの扱い

**間接的な影響（取り下げられたソースに立つ entity ページを grounding にしている view ページ）は本スクリプトの対象外**とする。`derived_from` を辿るのは `check_derivation_freshness.py` の役目である。**ただしそのカバレッジは条件付きである（Issue #928 で明示した）** — あちらが発火するのは grounding ページが**実際に書き換えられた**ときであり、取り下げはページを 1 バイトも変えない。したがってカバーされるのは「人が取り下げに対処した後」（`--regenerate` で grounding ページが変わる → view ページが STALE）だけで、**grounding ページが取り下げ済みソースに立ったまま誰も何もしていない状態には届かない**。それでも対象外にする理由は別にある（`docs/DesignDoc-data.md` §4.3。要点: 2 ホップの間接のために `status` の解釈者を増やすより、直接の半分をこのスクリプトが grounding ページ自身として名指しする方が、人は 1 ホップ手前で同じ情報を受け取れる）。この条件付きであることを書かずに済ませると、次に読む人が「あれが見ている」と読む。

## check_actions_pr_permission.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 114 → 114、コード 61 → 61、docstring 32 → 32、コメント 2 → 2、空行 19 → 19（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 3 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `review-issue-close-sync.yml` の `Commit and open PR` がこのリポジトリ設定に依存することは Issue #313
- `wikicommit-init` が初期化時にこの設定を有効にしようとする（best-effort）のは Issue #403
- その試みが痕跡を残さず失敗し、後になってレビュアーが追跡 Issue を閉じたときに誰も見ない Actions のログの奥でワークフローが失敗して初めて表に出ることは Issue #478

### 目的

"Allow GitHub Actions to create and approve pull requests"（Settings → Actions → General → Workflow permissions）リポジトリ設定が有効かを確認する。`review-issue-close-sync.yml`（Issue #313）の `Commit and open PR` ステップはこの設定に依存しており、無効なまま放置されると自動マージが失敗する（Issue #403）。`wikicommit-init` はこの設定をベストエフォートで自動有効化しようと試みるが、その試行が失敗しても通常の操作では痕跡が残らない — 失敗が顕在化するのはレビュー追跡Issueをcloseした数日後、しかもGitHub Actionsのログの中という運用者・読者どちらの目にも普段触れない場所でしかない（Issue #478）。本スクリプトは `wikicommit-status` の定期実行のたびにこの設定を再確認することで、ドリフトを事故ではなく能動的に検知できるようにする。

### 処理フロー

1. `.github/workflows/review-issue-close-sync.yml` が存在しなければ、この設定を必要としないリポジトリと判断し `OK`（`SUMMARY: enabled=n/a`）で即終了する
2. `gh auth status` が失敗する場合、設定を確認できない旨を `WARNING`（`SUMMARY: enabled=unknown`）として出力する（沈黙させない — 「検知できないこと」自体が Issue #478 の問題であるため、確認不能をサイレントスキップすると同じ穴を繰り返すことになる）
3. `gh repo view --json nameWithOwner -q .nameWithOwner` でリポジトリを特定できない場合も同様に `WARNING`（`SUMMARY: enabled=unknown`）
4. `gh api repos/{owner}/{repo}/actions/permissions/workflow` を呼び出す。呼び出し自体が失敗した場合（権限不足等）も `WARNING`（`SUMMARY: enabled=unknown`）
5. レスポンスJSONが解析できない場合も `WARNING`（`SUMMARY: enabled=unknown` — レスポンスの中身を確認できない以上、真偽いずれかを断定しない）
6. 解析できた場合、`can_approve_pull_request_reviews` が `true` なら `OK`（`SUMMARY: enabled=true`）。`false` なら `WARNING`（`SUMMARY: enabled=false`）とし、有効化コマンド（`gh api -X PUT repos/{owner}/{repo}/actions/permissions/workflow -F can_approve_pull_request_reviews=true -f default_workflow_permissions=<同レスポンスの値をそのまま再送>`）をメッセージに含める

**読み取り専用**（`wikicommit-init` の Step 3 と異なり、この設定を自動修復しない）: `wikicommit-status` は定期ヘルスチェックであり、ユーザーの目に触れないままリポジトリ設定を書き換えるのは踏み込みすぎと判断した。有効化コマンド自体は `wikicommit-init` Step 3 と同じ `gh api -X PUT ...` をそのまま提示する。

## check_property_wikilink_reinforcement.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 215 → 209、コード 85 → 85、docstring 76 → 69、コメント 27 → 28、空行 27 → 27（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 14 → 0（うち 1 つは行をまたいで `Issue` と `#550` が分かれたもの）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 範囲の分類（entity-only / mixed）は Issue #496
- このスクリプトは Issue #539。Issue #523 が補強の抜けを 1 つ手で見つけて直し（BlogPosting.md / NewsArticle.md の `publisher` は、補強のある `author` と同じ entity-only の範囲を持ちながら補強が無かった）、その PR への `/code-review --fix` が同じ `--show-range` の照合を繰り返して他の標準型テンプレートに同じ形を 4 つ見つけた（Organization.md の foundingLocation、Person.md の affiliation、Place.md の containedInPlace、Event.md の organizer / performer）。「補強」の 2 つの形と、それを型テンプレートの標準にしたのも Issue #523
- 文字列でない `granularity` の箇条書きに WARNING を出すのは Issue #649
- 箇条書きにリンクを指す手掛かりを求めるのは Issue #650。言及だけの判定は、HowTo.md の境界の規則が `HowTo.tool` を消したのが Issue #550、`tool` / `supply` を空のまま置けと書いた箇条書きが両方を消したのが Issue #551

### 目的

Issue #523 は `BlogPosting.md`/`NewsArticle.md` の `publisher`（`author` と同一の Entity-only 分類だが補強なし）という非対称性を `check_schema_org_type.py --show-range` による手動照合で発見・修正し、同じ照合を他の標準型テンプレートに広げたところ `Organization.md` の `foundingLocation`・`Person.md` の `affiliation`・`Place.md` の `containedInPlace`・`Event.md` の `organizer`/`performer` にも同型の非対称性が見つかった（`docs/DesignDoc-skills.md` §11.6「`properties:` 値の WikiLink 化」。見つけた経緯は `docs/history/DesignDoc-skills.md` の同じ節）。この照合は一度限りの手動監査であり、`--show-range` は「型テンプレートが property を名指しで補強しているか」と「その property の RANGE 分類」を機械的に突き合わせられるだけの情報を既に持っていたにもかかわらず、これを自動化するスクリプトが存在しなかった。本スクリプトはこの照合を自動化する（Issue #539）。

「補強」の定義は Issue #523 が実際に適用した2つの形をそのまま踏襲する: (1) `wikicommit.granularity` のプローズに、property 名を単語境界付きで言及し**かつリンク化を指し示す**（property 名を取り除いた残りに `[[` または `link` を含む。大文字小文字を区別しないため `WikiLink`・`linked` も該当する。property 名自体を手掛かりに数えないのは、`originalMediaLink` のように名前に `link` を含む property が自分の名前だけで条件を満たしてしまうのを防ぐため）箇条書きがある、または (2) `properties:` のプレースホルダー値（文字列またはリストの要素）に `[[...]]` という WikiLink トークンが既に含まれている。いずれも持たない Entity-only/Mixed な property を `UNREINFORCED` として報告する。

> **言及だけでは補強とみなさない（Issue #650）**: (1) は当初 property 名への言及のみを条件としていたが、正規表現は文脈を見ないため、**その property を否定する散文でも補強と判定されていた**。Issue #550 では `HowTo` の境界ルールの末尾「…the service, tool, or concept they operate on」が `HowTo.tool` を、Issue #551 では「`tool` と `supply` は物理的な手順向けで空になることが多い。書かずに置け」という箇条書きが `HowTo.tool` と `HowTo.supply` を、それぞれ報告から消していた。1件目は言い換えで解消できたが、2件目はその2つの property を名指しすることが箇条書きの目的そのものであるため言い換えができない — 散文が property に言及する必要がある限り、言及のみを条件とする判定では避けられない誤判定である。
>
> **この誤判定を消しても、判定は肯定・否定を見分けられるようにはならない**。「`tool` の値はリンクにするな」と書けば依然として補強と判定される（正規表現に文脈は解けない。Issue #550 / #551 が「既知の衝突パターンの機械的検査」を採らなかったのと同じ限界）。本 Issue が縮めたのは誤判定の範囲であって、種類ではない。取りこぼす側の劣化（リンク化を促す意図の箇条書きが `[[`・`link` のどちらも含まない言い回しで書かれていた場合、`UNREINFORCED` として報告される）は、非ブロッキングな気づきが1行増えるだけであり安全側に倒れている。
>
> Issue #523 が実際に書いた補強はすべてこの条件を満たすため、既存の配布テンプレートには回帰が無い（`HowTo.tool` / `HowTo.supply` の2件が報告に戻り、他は変化しない）。

### 処理フロー

1. `.wikicommit/schema/**/*.md` を走査する
2. 各ファイルの `type:` が `schema:` プレフィックスを持ち、かつ `custom/` で始まらない場合のみ対象とする（それ以外はスキップ）
3. `properties:` が dict であることを確認し（そうでなければこのファイルはスキップする）、`wikicommit.granularity` から検査に使える箇条書き（文字列のもの）を集める。文字列でない箇条書き・リストでない `granularity` は WARNING を出した上で対象外にする（`granularity_strings()`。Issue #649。下記コールアウト参照。WARNING は `properties:` を持つファイルにのみ出る — この WARNING の役目は直後の `UNREINFORCED:` が誤検出であることを説明することであり、`properties:` が無ければ説明すべき所見自体が生まれない）
4. `properties:` の各キーについて、`check_schema_org_type.py --show-range` と同じ RANGE 分類ロジック（`_schemaorg_vocab.py` の `entity_range_candidates()`）でエンティティ型候補を取得する。語彙に存在しない、またはエンティティ型候補が空（DataType-only、または `rangeIncludes` 自体が未宣言）の場合はスキップする
5. 残ったキー（Entity-only/Mixed）について、上記の「補強」定義（`granularity` 言及または `properties:` 値中の `[[...]]` トークン）を満たすか確認する
6. 満たさない場合、`UNREINFORCED:` として報告する

> **コロンを含む `granularity` 箇条書きは検査から外れる — 黙って外さない（Issue #649）**: クォートされていない YAML リスト項目にトップレベルの `key: value` 形状が現れると、YAML はそれをスカラーではなく単一キーのマッピングとして読む。`is_reinforced()` はプローズを走査する以上、文字列でない箇条書きを扱えない。問題はそこではなく、**扱えないことが出力に現れなかった**ことにある — 型テンプレートの著者が property 名をその箇条書きの中で補強していても、コロンを含んでいたというだけで補強が無かったことになり、`UNREINFORCED` の誤検出になる。しかも報告を見た人間がテンプレートを読むと補強は確かに書いてあるため、スクリプトの誤りではなく人間の見落としに見える。
>
> **箇条書きをマッピングから文字列に復元して検査する案（Issue #649 の対応方針 2）は採らない**。コロンを含む箇条書きは `granularity` を読むあらゆる消費者にとっての落とし穴であり、直すべき場所は型スキーマファイル自身である。ここで復元すると、直すべき形そのものを隠してしまう。
>
> **`.wikicommit/schema/` に置かれるファイルの出所は3系統あり、CI が守れるのは1つだけ**: 配布テンプレートは `tests/test_schema_template_boundary_rules.py` が「全 `granularity` 箇条書きが文字列としてパースされること」を強制する（Issue #550）。一方、`wikicommit-generate` Pass 2b / `wikicommit-schema-propose` が実行時に書いた型ファイルと、人間が直接手書きした型ファイル（`provenance: manual`）はそのテストの射程外にある。そのため予防は**書く側**にも置き、`granularity` を書く4経路（`wikicommit-init` の型提案・`wikicommit-collect` の Type Proposal・`wikicommit-generate` Pass 2b・`wikicommit-schema-propose`）が承認時に読む `.wikicommit/schema-authoring.md` が「箇条書きは文字列としてパースされる形で書く（`Boundary — …`。`Boundary: …` は不可、`#` も不可）」を明記する（Issue #886 以前は 4 経路の SKILL.md それぞれが同じ段落を持っており、同 Issue がそれを共有ファイルへ一本化した。各 SKILL.md に 1 行ずつ残るのは `Boundary —` の一点のみで、空白を伴う `#` の危険は共有ファイル側にしかない — **4 経路の SKILL.md を grep してこの規律が消えたと読まないこと**）。**既存の利用者リポジトリへの遡及対応は行わない**（本ドキュメント群で繰り返し採っている「新旧混在を許容する」方針）— 既にコロンで書かれた箇条書きは、この WARNING を見た人間が `.wikicommit/schema/` を直接編集するまで残る。

## check_recurring_characters.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 188 → 188、コード 84 → 84、docstring 69 → 69、コメント 13 → 13、空行 22 → 22（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 6 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #560
- `check_wanted_pages.py` が素の文字列の名前を数えない限界は Issue #318（docstring はそれを `properties:` の値に当てはめたものと書いていた）
- 既にある Person ページを指すべき値を WikiLink にすることは Issue #496、それを `character` だけでなく entity を範囲に持つ `properties:` のキー全体で報告する `check_unlinked_entity_mentions.py` は Issue #561
- slug の規則（英語の識別子・種類ごとに翻訳か翻字）は Issue #193
- `check_wanted_pages.py` の TYPE_MISMATCH の区別は Issue #563

### 目的

この取りこぼしは既存のどのチェックにも掛からない。`check_wanted_pages.py` は `[[Type/slug]]` 形式の WikiLink しか読まないため、プレーンテキストの名前は wanted page として計上すらされない（Issue #318 が明記した「WikiLink 構文が一度も使われていない言及は対象外」という限界が、`properties:` の値についても同じように効く）。`check_orphans.py` は既に存在するページへの被リンクの話であって無関係。結果として `wikicommit/decameron-wiki` は健全な数字を返し続け、その裏で 4 話の主人公である Calandrino が「Calandrino」という同一のプレーンテキストとして 4 回独立に列挙されるだけで、ページを 1 つも持っていなかった（Issue #560）。

**既に `Person` ページがある名前は本スクリプトの担当ではない** — 書くべきページは無く、値を WikiLink にすればよいだけ（Issue #496）であり、要求される行動が正反対だからである。こちらは `check_unlinked_entity_mentions.py`（Issue #561）が `character` に限らずエンティティ型を range に持つ全ての `properties:` キーについて報告する。本スクリプトもページの存在は読むが、それは昇格候補の一覧からその名前を外すためだけに使う。

**軸の限定**: 本スクリプトが扱えるのは Issue #560 の言う軸 B（作品をまたぐ再登場）だけである。軸 A（1 作品にしか登場しないが、その作品が丸ごとその人物についての話である主人公）は 1 ページにしか現れないため、横断集計では原理的に検出できない — こちらは生成時に `Person.md` の `granularity` が下す判断であり、事後のチェックの担当ではない。

### 処理フロー

1. 対象ページの frontmatter を読む。`status: removed` のページは対象外（既存の除外方針と同じ）
2. `PERSON_VALUED_PROPERTIES`（現状 `character` のみ）の下の文字列値を集める。値が `[[Type/slug]]` 形式そのものである場合はスキップする（ルールが求めている状態そのものであるため）。定数を増やしてよいのは「プレーンテキストのままであることが正規の結果でもある」という同じ性質を持つキーに限る
3. あわせて、`Person` 型のページについて `title` と `aliases` の各値を正規化したものから `Person/<slug>` への索引を作る（言語を問わない。slug は言語中立であるため、どの言語のページでもその名前に答えられる）。`aliases` も索引に含めるのは、`title` だけで突き合わせると「よりフォーマルな形でページ化されている」人物（`Person/ser-ciappelletto`・title `"Ser Ciappelletto"` に対して、作品側はプレーンテキストの `Ciappelletto`）が `RECURRING` として報告され、既にページがある人物について「ページを作れ」と促してしまうため — `check_wanted_pages.py` の `TYPE_MISMATCH`（Issue #563）が防いでいるのと同じ種類の重複であり、しかも title が異なるため `check_orphans.py` の重複ページ判定にも掛からない
4. 名前の突き合わせは NFKC 正規化 + casefold + 連続空白の単一化で行う（`check_orphans.py` が重複ページ判定でタイトルに適用しているものと同じ正規化）
5. 作品の同一性は**ファイルパスではなく `<Type>/<slug>`** で数える。1 つの物語の it/en/ja 版は 1 件であり、そうしないと多言語 Wiki は登場人物全員を「再登場」として報告してしまう
6. `Person` ページがある名前は除外し、無く 2 件以上の作品に現れる名前を `RECURRING` として報告する

### 既知の限界

- **軸 A は検出しない**（上記）

## check_unlinked_entity_mentions.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 189 → 190、コード 91 → 91、docstring 67 → 68、コメント 10 → 10、空行 21 → 21（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 5 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #561
- Pass 3 が `properties:` の値を WikiLink にするかを Schema.org の範囲だけで決めることは Issue #496
- 本文の散文を対象にしないことについて、docstring は「Issue #318 の限界は自由な文には残る」と書いていた（`check_wanted_pages.py` が素の文字列でしか言及されない概念を見ない限界。本文ではそう書き直した）。`properties:` の値が定義上短く構造化されていることは Issue #495
- slug を言語中立の英語の識別子にする規則は Issue #193

### 目的

Pass 3 は `properties:` の値を WikiLink にするかどうかを Schema.org の RANGE 分類のみで決め（Issue #496）、その指示は「参照先ページが未作成であることを理由に WikiLink を諦めるな」と**名指しで**述べている。それにもかかわらず `wikicommit/decameron-wiki` の `Book/decameron.md` は、`character` に並ぶ 10 人の語り手のうち、**同じ ingest で先にページが書かれた 8 人だけが WikiLink 化され、後の ingest でページが作られた 2 人がプレーンテキストのまま**になっていた。同一 property・同一値リスト・同一型・同一の資格で、分かれ目は取り込み順序だけである。

しかも自然には回復しない。`action: update` はそのページ自身を対象とするソースが再 ingest されたときにしか起きないため、後から `Person/filostrato` を作った ingest には Book ページを見直す理由が無い。既存のチェックにも掛からない — `check_wikilinks.py` は書かれた WikiLink しか見ず、`check_orphans.py` は参照先ページが他ページから被リンクを持つ場合（実際に持っていた）に取りこぼす。

対象は `properties:` の値に限り、本文の地の文は扱わない。地の文についての Issue #318 の限界はそのまま残る — 一方 `properties:` の値は定義上「短く構造化された値」（Issue #495）であり、これが既存ページとの機械的な突き合わせを成立させている。

### 修正の経路

`/wikicommit-fix <page-path> "<instruction>"` で参照元ページを個別に直す。**機械的な一括置換のスクリプトは用意しない**（Issue #561 の対応方針 4 に対する判断）: 値がページのタイトルと一致することは根拠であって証明ではなく（同名の別主体がありうる）、`properties:` への自動書き込みをヘルスチェックの責務に含めるべきでもない。既存の公開済みパイロットリポジトリへの遡及修正も行わない（同 5。運用者が `wikicommit-fix` で個別対応する）。

### 既知の限界

- **本文の地の文は対象外**（上記。Issue #318 の限界）

## check_installed_type_usage.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 180 → 181、コード 99 → 99、docstring 54 → 55、コメント 4 → 4、空行 23 → 23（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 4 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #565。docstring は、入っている型ファイルを前にしてページが無い形を「それまで何も探していなかった」と書いていた
- 同じ力（祖先の型に落ちる）が `DefinedTerm` に働くことを見つけ、型を*提案する*側で手当てしたのは Issue #447
- `provenance` フィールドは Issue #519

### 目的

`wikicommit/saitama-city-wiki` は `Park.md`・`Museum.md` を人間の承認を経てインストールしていたにもかかわらず、公園 7 件・博物館 2 件を素の `Place` として生成していた — しかも**型ファイルを追加したのと同じバッチ**で（型リストが古かったのではない）。その間 `check_schema_coverage.py` は 0 件を報告し続けた。`Place` にはスキーマファイルがあるためである。

原因は手違いではなく構造にある。Schema.org 上 `Park`・`Museum` は `Place` の子孫型なので、公園を `Place` として書くことは**誤りではなく、粒度が粗いだけ**である。そして祖先型は常に利用可能で、常により馴染みがあり、常に技術的に正しい。Issue #447 が `DefinedTerm` について発見したのと同じ力学が、型を**提案する**段（Pass 2b。#447 の対象）ではなく、インストール済みの型を**選ぶ**段（Pass 2c）で働いている。

**既存ページの型の再分類は本スクリプト（および Issue #565）のスコープ外**である（Issue #447 も同じ判断をしている）。型変更はディレクトリ移動と、そのページを指す全 WikiLink の Type セグメント書き換えを伴う（`docs/DesignDoc-data.md` §5.5）。本チェックの目的は、次のバッチが正しい粒度で生成されるよう早期にパターンを捕まえることにある。

## check_self_referential_tags.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 135 → 133、コード 65 → 65、docstring 45 → 43、コメント 7 → 7、空行 18 → 18（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 3 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #571
- タイトル・型と同じタグを散文で禁じたのは Issue #275。docstring は、再発の例としてパイロットの `Place/minuma-tanbo.md`（`見沼田んぼ`）・`Place/saitama-shintoshin.md`（`さいたま新都心`）と、自分のカテゴリでタグ付けされた 5 ページを挙げていた（下の「目的」の段落と同じ例）
- `check_property_wikilink_reinforcement.py` は Issue #539

### 目的

`tags` は「複数ページを横断して同じ概念で括る」ためのフィールドである（`docs/DesignDoc-data.md` §4.1・Issue #275）。ページ自身の `title` と同じタグはそのページ自身としか括れず、`type` と同じタグは `type:` フィールドが既に述べていることの繰り返しになる。どちらも Issue #275 が散文で明示的に禁じたが、**その後のパイロットで両方とも再発した**（`Place/minuma-tanbo.md` の `tags: [見沼田んぼ, ...]`、`Place/saitama-shintoshin.md` の `tags: [さいたま新都心, ...]`、および型と実質重複するカテゴリタグ 5 件）。

生成時の指示だけに依存し**検出手段が無い**ルールは drift する。`check_property_wikilink_reinforcement.py`（Issue #539）が「一度限りの手動監査を自動化する」のと同じ位置づけである。

## check_schema_files.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 400 → 394、コード 205 → 205、docstring 134 → 129、コメント 27 → 26、空行 34 → 34（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 11 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #889。それまでは `wikicommit-generate` の指示が「Nothing validates a schema file」と書いており、そのとおりだった。道具（`check_schema_org_type.py`・`_schemaorg_vocab.py`・`provenance_of()`）は揃っていて、ファイルに対して走らせる主体だけが無かった。`granularity_raw_bullets()` を単純に保つのは Issue #889 の 2 点目
- `TRUNCATED_BULLET`（空白の後の `#` がコメントを開いて行の残りを落とす）は、Issue #649 が「何も警告しない」と名指しした失敗
- `provenance` の 7 つの値と、欠けていることを「そのフィールドより前に作られた」と定義したのは Issue #519
- `TYPE_PATH_MISMATCH` はページ側で Issue #545 が足した検査と同じもの
- `NO_RATIONALE` は Issue #548
- `granularity` の散文の良し悪しを判定しないのは、Issue #552 が同じ結論に達して指示の強化で止めたため
- ファイルをサブディレクトリに移すと型が見つからなくなる問題は Issue #575
- `Boundary with NewsArticle: ...` は、Issue #550 がコロンを em ダッシュに替える前に 3 つのテンプレートが持っていた形

### 目的

`wikicommit-generate` SKILL.md 自身がこう書いていた — **Nothing validates a schema file**。そしてそれは正確だった。

**道具は全部あった** — property の検証は `check_schema_org_type.py`、祖先の解決は `_schemaorg_vocab.py`、`provenance` を読む関数は `check_installed_type_usage.py` の `provenance_of()` にある（同スクリプトは `default` かどうかだけを見て、値が enum に属するかは問わない）。欠けていたのは、それらをファイルに対して走らせる主体である。

### 使用場面

**`check_property_wikilink_reinforcement.py` と統合はしない**（Issue #889 検討事項 3 の結論）。走査は 2 回になるが、問う内容が逆である — あちらの所見は「テンプレートがもっと述べるべきか」という**望ましさ**であり、`description` のように常に出ることを承知で残している行を持つ。こちらは「そもそも動く形で書かれているか」という**壊れている**の報告で、1 件でも出れば見る価値がある。1 つの `SUMMARY:` に混ぜると、後者が前者の既知のノイズに埋もれる。

### 報告しないもの

- **`provenance` の欠如**。Issue #519 がその不在を「この機能追加より前に作られた」と定義しているため、報告すれば古いリポジトリ全件が正しい状態について点灯する
- **`granularity` の散文の妥当性**。規則が**正しいか**はここでは判定できない（Issue #552 が同じ結論に達し、指示の補強で止まっている）。見るのは形だけである

### `in_distributed_templates` — 実データで決めた所見の範囲

`SUMMARY:` は `files` / `findings` に加えて `in_distributed_templates`（`provenance: default` のファイルに出た件数）を出し、非ゼロなら `NOTE:` 行を添える。**`provenance: default` のファイルに出た所見は「誰かが書き間違えた」ではなく「このリポジトリが古いテンプレートの写しを持っている」を意味する** — これらの規約のいくつかは、テンプレートが最初に配られた後で足されたものである（Issue #550 の `Boundary`・Issue #649 の YAML 文字列規律）。対処は上流の差分を取り込むことであり、それは `check_distribution_freshness.py` が同じファイルについて報告する。テンプレートを手で直すと次の同期で元に戻る。

実測（2026-09-12。公開パイロット 3 件）:

| リポジトリ | files | findings | うち `default` | 内訳 |
|---|---|---|---|---|
| `wikicommit/ai-driven-dev-wiki` | 14 | **0** | 0 | — |
| `wikicommit/saitama-city-wiki` | 19 | **7** | **0** | `NO_BOUNDARY` 7（全件が実行時に書かれた型。8 ファイル中 7） |
| `wikicommit/decameron-wiki` | 14 | **15** | **13** | `NO_BOUNDARY` 10・`MAPPING_BULLET` 3・`TRUNCATED_BULLET` 2 |

**`TRUNCATED_BULLET` は真陽性だった。** decameron の `DefinedTerm.md` は `granularity` の 2 本が空白を伴う `#` で切れており、1 本は約 1,000 字の規則が **723 字**で終わっていた（`(Issue #447)` より後ろが丸ごと消え、続く 1 文の指示も失われている）。**現在の配布テンプレートではクォートされて修正済み**であり、つまりこれは「上流で直った後、古い写しだけが壊れたまま残っていた」形である — この 1 件が、`default` のファイルを黙って除外せず件数として出すことにした理由である。

**`provenance: default` を丸ごと除外する案は採らなかった**。15 件が 2 件になって読みやすくはなるが、上記の沈黙した切り詰めのような実害が見えなくなる。代わりに件数を分けて、どちらが自分の書いたものかを読み手が 1 行で判別できるようにした（Issue #562 が名指しした「常時点灯すると読まれなくなる」への対処を、所見を隠すのではなく数を読めるようにすることで行う）。

### 既知の限界

- **`provenance` を持たないファイルは `default` 側に数えられない**。値が無ければ古い配布テンプレートか古い実行時ファイルかを区別する手段が無いため、リポジトリ側として数える。実測の 3 パイロットでは全ファイルが `provenance` を持っていた

### 終了コード

**`wikicommit-merge` の品質ゲートに入れない**（Issue #889 の「採らなかった案」）。壊れた schema ファイルを 1 つ持っているだけで既存リポジトリがマージ不能になる。`validate_frontmatter.py` の `type:` 検証（Issue #512）が ERROR なのは、そこがページ側であり `wikicommit-generate` がその場で直せるからであり、こちらの対処はどの Skill も触れないファイルを人間が開くことである。

## record_relation.py / check_name_collisions.py

`/wikicommit-relate`（Issue #1095）が使う 2 本。設計判断の全体（関係の語彙・置き場所・形式）は `docs/DesignDoc-data.md` §4.5.2 にある。

**`record_relation.py` の docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 191 → 191、コード 124 → 124、docstring 44 → 44、コメント 4 → 4、空行 19 → 19（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

`record_relation.py` の docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #1095

**`check_name_collisions.py` の docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 136 → 136、コード 86 → 86、docstring 37 → 37、コメント 1 → 1、空行 12 → 12（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 2 → 0。出力する文字列には `#NNN` は無い。

`check_name_collisions.py` の docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #1095
- 生成が既存のページをタイトルと別名でも照合するのは Issue #1096（docstring は「Issue #1096 以降」と書いていた）

### check_name_collisions.py

終了コード: 常に `0`（報告のみ。`/wikicommit-merge` の品質ゲートには入れない — 入れると既存のパイロットがマージ不能になる）。

## check_groups.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 129 → 129、コード 87 → 87、docstring 29 → 29、コメント 1 → 1、空行 12 → 12（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 2 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- グループファイルは Issue #1035
- グループファイルを持たない Type を報告しない理由（常に点いている行は読まれなくなる）は Issue #562

## check_external_links.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 335 → 335、コード 229 → 229、docstring 68 → 68、コメント 9 → 9、空行 29 → 29（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 7 → 0（うち 3 つは行をまたいで `Issue` と `#1243` が分かれたもの）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #1182
- `/wikicommit-merge` の lychee がそのバッチで変わったページだけを見るのは Issue #1196
- 所見を `{"kind", "pages", "text"}` の形で持ち、文言の書き出しに頼らないこと、それより前の素の文字列のファイルの扱い（進捗ファイルは捨てて最初から・結果ファイルは `read_legacy_findings()` が読む）は Issue #1243

## merge_pages.py / rewrite_merged_links.py

`/wikicommit-generate --regenerate <残すページ> --merge <吸収するページ> [...]`（Issue #1119）が使う 2 本。設計判断の全体は `docs/DesignDoc-data.md` §4.5.2 の「統合」の節にある。本文の書き直し（Pass 3 / 4）はエージェントが行い、統合に関わる**決定論的な部分**をこの 2 本が持つ（Issue #474）。

**`merge_pages.py` の docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 368 → 368、コード 263 → 263、docstring 54 → 54、コメント 1 → 1、空行 50 → 50（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

`merge_pages.py` の docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #1119

**`rewrite_merged_links.py` の docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 179 → 178、コード 110 → 110、docstring 46 → 45、コメント 6 → 6、空行 17 → 17（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 2 → 0。出力する文字列には `#NNN` は無い。

`rewrite_merged_links.py` の docstring・コメントにあって本文に無かった経緯は次のとおり:

- このスクリプトは Issue #1119
- 書き換えだけでは片付かないものを示す 2 つの注記（`SELF_LINK:` / `ALSO_LINKED:`）は Issue #1131

## rename_page.py

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 290 → 290、コード 190 → 190、docstring 59 → 59、コメント 9 → 9、空行 32 → 32（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `check_review_coverage.py` と公開バナーが `renamed_at` の項目を辿ってレビュー記録に戻るのは Issue #1162

## init.py

**ScriptSpec に節を持たないスクリプトの置き場（Issue #1343。メンテナの判断で、最初に当てはめたのが本節）**: 本文に節を持たないスクリプトは、本文に節を起こさない。仕様は今ある場所を正本のままにする — 共有スクリプトなら `docs/DesignDoc-skills.md` §11.5 の委譲表、`init.py` なら `docs/DesignDoc-data.md` §3.1・§3.3（何をどこに配り再 init で何が更新されるかは `_root_outputs.py` の `update` 列）と `docs/DesignDoc-skills.md` §11.1。docstring にある仕様の文はそのまま残してよく、移すのは経緯だけである。経緯の置き場として、このファイルにスクリプト名の見出しを起こす（本文の節と揃えた見出しの後、付録の前に置く）。`convert_wikilinks.py` は Skill から呼ばれず §11.5 に行が無かったため、この判断の前に本文へ節を起こしている（上の同名の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 1,276 → 1,265、コード 723 → 723、docstring 173 → 168、コメント 279 → 273、空行 101 → 101（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 46 → 0。`Issue` の付かない `#NNN`（`#374`・`#160`・`#211`・`#93`・`#94`）もコメント・docstring からは外した。`--update-theme` の `--help` に残る `(#374 — ...)` は出力する文字列であり、この移行（コメント・docstring）の範囲外なので残した — `tools/check_distributed_issue_refs.py` の出力の検査は `Issue #NNN` の形しか見ないため、これを検出しない。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `_version.py` が利用者のリポジトリに届く唯一の版の出所であること（`.claude-plugin/plugin.json` は配布リポジトリに残る）は Issue #577。`copy_tree()` が `__pycache__` を刈るのも同じ Issue（開発リポジトリでは `.wikicommit/scripts` が `templates/scripts` へのシンボリックリンクなので、スクリプトを 1 度走らせると `.pyc` が溜まる）。`wikicommit_version` を持たない `config.yml` は Issue #577 より前に作られたもの。`node_modules/` を走査の前に刈る（`os.walk()` にした）のは #211
- 再 init は `.wikicommit/scripts/` を `--no-overwrite` の下でも上書きする（Issue #647）。具体的に壊れていたのは `_version.py` で、古いまま残ると `generated_with` / `translated_with` が新しい Skill で作ったページを古い版で作ったと主張した。この扱いは Issue #712 で `_root_outputs.py` の `update` 列に宣言する形へ移った。`copy_tree()` が消さないため、上流で改名したスクリプトの古い名前が残るのは Issue #583
- コピーのフラグを `_root_outputs.py` の `update` 列から引く `_flags()` は Issue #712。呼び出し箇所ごとにリテラルで書いていたため、`.wikicommit/config.yml` と `.wikicommit/schema/` がフラグを持たず、利用者のテーマ・`targets`・手で直した型テンプレートを守るのが `--no-overwrite` だけになっていた
- ルートに置く素のコピーを `_root_outputs.py` の 1 つの一覧から作り、`print_next_steps.py` の `git add` 案内も同じ一覧から作るのは Issue #642。一覧が 2 つあったため、`install-local-plugins.cjs` がコミットを促されないまま配られた（Issue #556）
- `quartz.config.yaml` を `copy_file()` ではなく `write_file()` で書き、`pageTitle` の既定をリポジトリのディレクトリ名にしたのは Issue #317。`pageTitleSuffix` に同じ名前を ` - ` 付きで入れたのは Issue #679 で、それまでの空の既定では、サイト全体のどのタブ・`og:title`・`twitter:title` にもサイト名が載らず、トップページは「Wiki」とだけ表示されていた
- フッターの `{REPO_URL}` は Issue #557。フッターのプラグインが Quartz 自身のリポジトリを GitHub のリンクとして持っていたため、生成した Wiki のいちばん目立つリンクが上流の SSG を指していた（`pageTitle` に Issue #317 でリポジトリごとの既定を与えたのと同じ理由）。リモートが解決できずリンクを落としたときに `NOTE:` を出すのも同じ Issue
- `quartz.config.yaml` の `locale` を `primary_lang` から決める表は Issue #771。それ以前はテンプレートに `locale: en-US` が固定で書かれ init が置換しなかったため、日本語の Wiki は本文とバナーが日本語、サイドバー・検索・グラフが英語で配られた（翻訳はあったが届いていなかった）
- WikiCommit 自身がラベルを持つ 10 言語は Issue #1017 で Wikipedia のポータルから決めた。その言語に無い `primary_lang` を選んだ運用者にだけ告げる（公開ページでは告げない）判断は Issue #825
- 改行の慣習（CRLF / LF / 混在）を保って書き戻す `_read_keeping_newline()` / `_write_with_newline()`、および `_VERSION_LINE_RE` の `[^\r\n]*` は Issue #1189
- `config.yml` を YAML の読み書きではなく文字列で書き換える理由（コメントにしか書かれていない例が失われる）は Issue #713。その例として挙げた `site_description` の言語別の例は Issue #671 で足したもの。`entity-policy.md` のスイッチ（`--exclude-living-persons`）も同じ理由で文字列で書き換える（Issue #837）。`--update-version`・`--add-config-keys`・プレースホルダの既定値（`_CONFIG_PLACEHOLDER_DEFAULTS`）も Issue #713。`{VERSION}` を引用符で二重に包んで `wikicommit_version: ""0.2.0""` を書いた不具合が実際にあり、`check_distribution_freshness.py` が自身の置換について同じ罠を記録している（Issue #712）
- `re.sub` の置換に文字列ではなく lambda を渡す理由は `set_frontmatter_field.py` の Issue #371
- `--update-theme`（`--theme` は再 init では効かない）は #374、`theme` フィールドは #160 で足した。`theme` を持たない `config.yml` はそれより前のもの
- `--update-theme` の `--help` に残っていた `(#374 — ...)` は Issue #1376 で番号を外し、理由（再実行では `--no-overwrite` が既存の `config.yml` を丸ごと飛ばすので `--theme` は効かない）だけを残した。同じ Issue で `tools/check_distributed_issue_refs.py` の配布スクリプトの検査が素の `#NNN`（2 桁以上）と `Issue-#NNN` も数えるようになった
- `.claude/settings.json` の `skillOverrides` を鍵ごとにマージするのは Issue #953。テンプレートが名指す 3 つの Skill は Issue #945 で `disable-model-invocation` を外し（無人実行の経路を開くため）、通りすがりの依頼で起動されうるようになった
- README は Issue #1034。init が README.md を編集しないと決めたのは Issue #282 で、README が無いときはその理由が成り立たないので書く。LLM が書いた文を含まないことが基盤コミット（Issue #843）に載せられる理由。英語だけなのは、ja / en 以外の言語も予定しているため `primary_lang` で切り替えていない
- `.wikicommit/guides/` は Issue #846。配布物が開発リポジトリの `docs/` を指してはならないのは `docs/DesignDoc-skills.md` §11.9
- `.wikicommit/review/` を空で作るのは Issue #750（レビュー記録）
- `quartz-plugins/` から vitest 関連（#93）・eslint 関連（#94）のファイルを除く
- `GITIGNORE_READY:` を Quartz の `.gitignore` 追記の後に出すのは Issue #873。SKILL.md が `.gitignore` の中身を読まずにこの 1 行だけを読むのは Issue #474（決定論的な判定をスクリプトに持たせる）

## add_source.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.5 の委譲表の `add_source.py` の行。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 1,854 → 1,850、コード 945 → 945、docstring 431 → 425、コメント 269 → 271、空行 209 → 209（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 41 → 0。`Issue` の付かない `#NNN`（`#191`・`#192`・`#213`・`#269`・`#310`・`#425`・`#567`・`#570`・`#572`・`#573`・`#715`・`#951`・`#958` 等）もコメント・docstring からは外した。出力する文字列に残る 3 か所 — `--check-path-cache` / `--path-cache-path` の `ERROR:` の理由（`a pre-Issue-#476 .wikicommit/ingest/ tree is never auto-migrated`。2 か所）と `--fetch-url` の `--help`（`..., #527)`）— はこの移行（コメント・docstring）の範囲外なので残した。`tools/check_distributed_issue_refs.py` の出力の検査は `Issue #NNN` の形しか見ないため、どちらも検出しない。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- スクリプトを Skill 内ではなく `.wikicommit/scripts/` に置くのは Issue #1210（wikicommit-collect・wikicommit-ask・`resolve_source_cache_path.py` も `--fetch-url` 等を呼ぶため）。`resolve_source_cache_path.py` が `add_source.py` を隣から呼ぶのも同じ Issue
- 独自 User-Agent（`USER_AGENT`）と `--fetch-url` が `markitdown` の Python API に UA 付きの `requests.Session` を渡す形は Issue #527（既定の python-requests UA が Wikimedia 系ドメインに 403 で拒否された）
- 出力する文字列に残っていた 3 か所の番号は Issue #1376 で外した。`--fetch-url` の `--help` の `#527` は外すだけで意味が通る。`--check-path-cache` / `--path-cache-path` の `ERROR:` の理由の `a pre-Issue-#476 .wikicommit/ingest/ tree` は `a legacy .wikicommit/ingest/ tree` にした — Issue #476 は管理ファイルの置き場を `.wikicommit/ingest/` から `.wikicommit/source/` へ改名したもので、それより前に作られたツリーを自動では移行しない
- `KNOWN_SOURCE_LICENSES` と `source.license` の初期値（明示指定 > 既知ドメイン対応表 > 空欄）は Issue #558。`--license-for-url`（登録より 1 歩前に同じ表を引く読み取り専用モード）は Issue #646
- `SHARE_ALIKE_LICENSE_PREFIXES` と登録時の ShareAlike 通知は Issue #570（Creative Commons ほか）。強い・弱いコピーレフトを足したのは Issue #951 で、弱いコピーレフトも一律で入れるのはその検討事項 1、通知を「負いうる」と書いて断定しないのは検討事項 2 の結論。`eupl`・`cpl`・`ms-rl` を足し CeCILL を意図的に入れなかったのは Issue #958。「評判ではなく条項で判定する」「確認済みのものだけを持つ」はこの表の規律として Issue #425 で決めたもの
- `PARTIAL_EXTRACTION_URL_NOTES` と登録時の partial extraction 通知は Issue #715。partial extraction という失敗クラスは Issue #574 が YouTube（字幕が黙って落ちる。ガード C）について定義したもので、GitHub の Issue / PR スレッドはその 2 例目だった
- `type: url` の同一性を導出ファイル名ではなく `source.url` の走査で判定し、クエリを残して `normalize_url_for_identity()`（トラッキングパラメータを落とし並べ替える）を通すのは Issue #572。それ以前はクエリを落としていたため、`https://www.youtube.com/watch?v=<id>` がすべて同じ `watch` に潰れ、2 本目の動画の登録が 1 本目の管理ファイルに対して黙って成功を報告していた。導出名が埋まっているときにハッシュ接尾辞付きの代替パスへ退避すること、長い名前をハッシュ付きで切り詰めること（`_MAX_STEM_BYTES`）、`youtu.be/<id>` と `youtube.com/watch?v=<id>` を同一視しないこと（サイト固有の知識が要る）も同じ Issue
- `type: path` の同一性を `source.path` の走査で判定し、管理ファイル名を拡張子の置き換え（`with_suffix(".md")`）から付け足し（`raw/paper.pdf.md`）に変えたのは Issue #573。それ以前は `raw/paper.pdf` と `raw/paper.docx` が同じ管理ファイルに解決し、後から登録した方が既存ソースを `status: outdated` に誤って書き換えていた（登録したはずのファイルはどこにも記録されなかった）。`type: url` 側の Issue #572 と同じ柱
- 管理ファイルをホスト名のディレクトリに分けたのは Issue #191（それ以前は全 URL が 1 つのディレクトリにフラットに置かれた）。非 ASCII のパーセントエンコードだけを復号し `%2F` 等の ASCII は残すのは Issue #192。素のドメインの URL を `{host}/index` ではなく `<host>.md` にし、ホストの無い URL を拒否するのは Issue #213。どの命名変更も自動移行はせず、同一性を走査で判定するので不要になっている
- バックスラッシュ区切りのパスを `/` に正規化する（`normalize_source_path()`・`_yaml_single_quote()`）のは Issue #269
- `source.lang` の空の行を雛形に置くのは Issue #989。消費者（俯瞰ページのソース言語別集計）が同じ変更で入っていたので、受け皿だけ配る形（Issue #553）には当たらないと判断した
- `status: retracted` を `RETRACTED` で返し（`SKIP` に落とさない — Issue #737 の穴 (2)）、`## Retraction Reason` を 1 行に畳んで添えるのは Issue #737。人間にしか書けない値であることは証拠拘束ルール（Issue #442）から、理由を散文で残す形は `## Failure Reason`（Issue #408）から来ている
- `failed_pages` の有無で `partial` を分けるのは Issue #567。Issue #992 より前はポリシー除外のみのソースも `partial` になっていた（今は Pass 4 が `generated` にする）ため、古い管理ファイルにはそれが残る
- 完結済みの URL（`generated` / `failed` / `excluded`、および `failed_pages` の無い `partial`）を `RECHECK` で返すのは Issue #310
- `--write-hash` は Issue #157 のスクリプト委譲パターン。`--check-hash`（キャッシュ済みスクラッチの再利用）は Issue #278
- `type: path` の抽出テキストキャッシュ（`--check-path-cache` / `--path-cache-path`。`.wikicommit/.cache/extract-path/`）は Issue #885。URL 側の scratch と木を分けて既存の URL キャッシュを失効させずに衝突を無くした判断は、Issue #583 が改名を見送ったのと同じ代償計算。`.wikicommit/source/path/` の外の管理ファイルに `None` を返すのは、Issue #476 の改名（`.wikicommit/ingest/` → `.wikicommit/source/`）が自動移行されないため
- `--check-path-cache` の `RAW` / `extract=` をシンボリックリンクの解決先の拡張子で判定するのは Issue #1216（`--obtain` 側の同じ扱いは Issue #1208）。存在の判定とハッシュも同じ 1 回の解決に対して行うのは Issue #1242。リポジトリ外の判定を存在の判定より前に置くのは Issue #1207
- `FETCH_TIMEOUT` は Issue #1038。それ以前は `markitdown` がタイムアウト無しで `session.get()` を呼び、ヘッダを送って止まったサーバーがハーネスに殺されるまで実行を止めていた（何も記録されなかった）。`NETWORK_UNAVAILABLE`（exit 3）を `ERROR` から分けたのは Issue #1020 で、サーバーに届いた後の失敗を `ERROR` 側に戻す `_is_connection_failure()` の除外は Issue #1038。連続したら止める線引きはガード C（Issue #574）と同じ

## resolve_source_cache_path.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.5 の委譲表の `resolve_source_cache_path.py` の行。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 959 → 959、コード 442 → 442、docstring 390 → 390、コメント 42 → 42、空行 85 → 85（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 40 → 0（`Issue` の付かない `#191`・`#192`・`#572`・`#573` も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- スクリプトは `wikicommit-ask` の `--include-source`（Issue #470）のバックエンドとして作られた
- 識別子からファイル名を再計算せず管理ファイルを走査するのは、Issue #191（旧フラット命名）・#192（旧パーセントエンコード命名）・#572（クエリを落としていた命名）・#573（拡張子を置き換えていた命名）より前に登録された管理ファイルが自動移行されないため。`add_source.py` の登録側の走査（Issue #572 / #573）と同じ判定
- `type: path` のキャッシュの木（`.wikicommit/.cache/extract-path/`）は Issue #885。管理ファイルの相対パスを末尾の `.md` ごとそのまま使う規則は Issue #1326 — `with_suffix("")` で `.md` を落としていたため、`pdf-2606.05608.md` が `pdf-2606.md` になり、接頭辞が同じ別ソース（`pdf-2606.17799.md`）とキャッシュが重なって、別ソースの本文を返し `--settle` ではその置き場所を上書きしていた
- 識別子を argv ではなく stdin から読むのは Issue #375
- exit 1 の 2 つの意味を `UNREGISTERED:` / `NO_CACHE:` で分け、`--settle` を足したのは Issue #1036。それ以前、clean checkout ではキャッシュが常に空なので、`--include-source` は URL ソースを毎回諦めていた。review / fix が `.wikicommit/.cache/refetch/` に取得した後で `--settle` を呼ぶのは Issue #1137
- `--type path` の `OUTSIDE:` は Issue #1206
- `--obtain` は Issue #1190。それ以前はキャッシュ照会・`type: path` キャッシュの版の照合・`add_source.py --fetch-url`・`--settle`・scratch の扱いを SKILL.md の散文で順に指示していた。`UNAVAILABLE: outside` は Issue #1201。`type: path` の拡張子と返すパスをシンボリックリンクの解決先にしたのは Issue #1208（範囲の検査と読む先を 1 回の解決で決めるのも同じ）、generate の Pass 1 も同じ解決先を見るようにしたのは Issue #1216
- `--obtain-sources` は Issue #1211。それ以前は review / fix が取得の前に `check_retracted_sources.py --list` を別に走らせていた。行に元の識別子を併記しないのは Issue #1216。時間の区切り（`--budget` / `--from` / `CONTINUE:`）は Issue #1240
- 子プロセスとの入出力を UTF-8 に固定し（`run_fetch()`）、このスクリプト自身の出力も UTF-8 にする（`use_utf8_streams()`）のは Issue #1256 — 子が成功した後で、cp1252 の端末やパイプでこのスクリプト自身の `print` が `UnicodeEncodeError` を送出していた。非 UTF-8 のロケールで argv に URL を載せられないときに 1 行で返すのと、ファイル名の綴りの違いを吸収する `_same_identifier()` は Issue #1265（登録済みの非 ASCII のソースが `UNREGISTERED` になり、`path` の経路では `status: retracted` を越えて生ファイルが読まれていた）
- `add_source.py` を隣の `.wikicommit/scripts/` から呼ぶのは Issue #1210
- 取り下げ済みソースを exit 2（`RETRACTED:`）で伝えるのは Issue #918。それまで取り込み側（Issue #737）では再登録も `outdated` への復帰も止まるのに、参照側（`--include-source`）にはガードが 1 つも無かった。人間にしか書けない値であることは証拠拘束ルール（Issue #442）から。`retracted` 以外の `status` を見ないのは Issue #553 の「消費者と同時に足す」。frontmatter が壊れた管理ファイルに `WARNING:` を出すのも、`status: retracted` が手書きの値（Issue #737）であるため

## _root_outputs.py

本文に節を持たない（仕様は `docs/DesignDoc-data.md` §3.3〈再 init の挙動をこのモジュールの `update` 列が決める〉と、`docs/DesignDoc-skills.md` §11.5 の委譲表の `_root_outputs.py` の行・「ルート生成物の一覧は 1 つに保つ」。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 672 → 662、コード 298 → 298、docstring 183 → 179、コメント 134 → 128、空行 57 → 57（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 34 → 0。`Issue` の付かない `#93`・`#94`・`#557`・`#313`（`Issue #317 / #557` のような並記の 2 つ目を含む）もコメント・docstring からは外した。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このモジュールは Issue #642。それまで `init.py` が書くファイルと `print_next_steps.py` が `git add` を促すファイルは手で保守する 2 つの一覧で（SKILL.md の散文を数えれば 3 つ）、`install-local-plugins.cjs` が `init.py` にだけ足され（Issue #434）案内から漏れたため、`--quartz --quartz-pages` で初期化したすべてのリポジトリが最初の GitHub Pages ビルドで `postinstall` の MODULE_NOT_FOUND を出して失敗した（Issue #556。パイロット 2 つで再現）。Issue #556 はそのずれを*検出する*テストを足し、Issue #642 は 2 つ目の一覧そのものを無くした
- `package-lock.json` を `in_git_add=False` にして別のコマンドで案内するのは Issue #556
- 既定の案内を `git add -A` にしたのは Issue #842。それより前は選択的な列挙が既定だったので、`vocab_cache` の条件と `in_git_add=False` が、存在しないパスで基盤コミットが abort するのを防いでいた。Issue #842 の後も、列挙は既存のリポジトリ向けのフォールバックとして下に残るので、両方を残した
- `update` 列（`UPDATE_POLICIES`）・`copy_flags()`・`is_quartz_plugin_dev_artifact()` をこのモジュールに置き init と鮮度チェックで共有するのは Issue #712。除外する開発用ファイルは vitest 関連が #93、eslint 関連が #94
- `COMPARISONS` が常時点灯する警告を避ける理由として挙げていた先例は、Issue #562 が低密度ガードを同じ理由で格下げしたこと
- `condition="readme_created"` と `README.md` の行は Issue #1034。`README_LICENSE_TEXT` はライセンス表示の第 4 層（Issue #645）で、init と `print_next_steps.py` が 1 つの文字列を共有する形にしたのは Issue #1034
- `.agents` / `skills-lock.json` の行は、`npx skills add` が 2 つ以上のエージェントを対象にすると実体を `.agents/skills/<name>/` に置き `.claude/skills/<name>` をそこへのシンボリックリンクにすること（Issue #555）による。`origin=install`・`update=skip` にしたのは Issue #948
- `.claude/settings.json` の行（`skillOverrides`）は Issue #953。対象の 3 つの Skill は Issue #945 で `disable-model-invocation` を外したもの
- `.wikicommit/entity-policy.md` は Issue #667、`.wikicommit/review-rules.md` は Issue #752、`.wikicommit/schema-authoring.md` は Issue #886（型を足す 4 つの経路がそれぞれ手順の全体を持っていた）
- `.wikicommit/guides` は Issue #846。それまで giscus の手順は 600 行のエージェント向け指示ファイルの末尾にしか無く（そのファイル自身が「聞かれたら見せる」と書いていた）、人に指し示す置き場が無かった。最初は 1 ファイルだったが、2 本目で何も変えずに済むようツリーとして登録した
- `.wikicommit/view` は Issue #675、`.wikicommit/review` は Issue #750、`.wikicommit/groups` は Issue #1035（空の受け皿を配らないのは Issue #553）
- `quartz.config.yaml` を置換で書くのは Issue #317（`pageTitle`）と Issue #557（フッターの URL）。`deploy.yml` を `--quartz-pages` だけに絞ったのは Issue #335、`review-issue-close-sync.yml` を全 variant に配るのは Issue #313。`.github/ISSUE_TEMPLATE/report.md` はバナーの報告リンク（Issue #245 / #313）の受け先で、Quartz 限定なのはバナーが Quartz プラグインであるため（Issue #339）
- `missing_gitignore_patterns()` は Issue #873。それまで基盤コミットの申し出は「この実行が `.gitignore` を書いたか」（`SKIPPED: .gitignore` のログ）で判定しており、2 回目以降の init では WikiCommit 自身が作ったリポジトリでも申し出が止まっていた。テンプレートに後から入ったパターンの例として挙げた `.wikicommit/run/` は Issue #790

## print_next_steps.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.5 の委譲表の `print_next_steps.py` の行と「ルート生成物の一覧は 1 つに保つ」。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 700 → 690、コード 429 → 429、docstring 51 → 49、コメント 163 → 155、空行 57 → 57（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 29 → 0。`Issue` の付かない `#NNN` は無かった。出力する文字列（案内文・argparse の引数）には `#NNN` は無い。ただしこのスクリプトは `argparse.ArgumentParser(description=__doc__)` でモジュールの docstring を `--help` に出すため、docstring から `(Issue #350)` と経緯を外したことで `--help` の説明文も変わった（案内の出力そのものは変わらない）。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- スクリプトは Issue #350。それまで SKILL.md は `--quartz` / `--quartz-pages` の組み合わせごとにほぼ同じ案内を 3 つ書いており、その重複で SKILL.md が推奨行数を超えていた
- テンプレートのパスをこのファイルの位置から求める `_templates_display()` は Issue #1021（Skill が `.agents/skills/` に置かれる場合がある）
- コミット手順の前置きが「これはあなただけが実行するもの」と言わなくなったのは Issue #843。それまで挙げていた 2 つの理由（`.wikicommit/schema/` に書けない・`main` に直接コミットできない）はどちらも既に成り立っていなかった — init が明らかな型の判断で型ファイルを直接書くのは Issue #490 で、禁じられているのは著作であってコミットではない。断られた・非対話・失敗の経路でこの案内をそのまま残すのは、この手順を足した Issue #86 の対処を弱めないため。Quartz のセットアップが残っている間は申し出を延期し、手順を除いた案内を再表示してから申し出るのは Issue #865
- 既定を `git add -A` にしたのは Issue #842。それまでの選択的な列挙は誰も生成しない `.gitmodules` / `quartz` を含み、`git add` が存在しないパス 1 つで全体を abort するため（実測で exit 128・0 ファイル）、案内を順に写すと基盤コミット全体が落ちた — Issue #86 がこの手順で防ごうとした状態そのもの
- 既存の `.gitignore` が WikiCommit のパターンを持たない場合を、以前は「このスクリプトはフラグを渡されるだけでリポジトリを見ない（`--gitignore-skipped` のようなフラグも無い）」という理由で両方の場合を覆う散文で書いていた。これは基盤コミットの申し出と同じ誤った前提で（Issue #873）、`.gitignore` を読んで 2 つの注記を出し分ける形に改めた。`--repo-root` をこのスクリプトにも持たせたのも同じ変更
- 存在しないかもしれないパスの注意書きに `.agents` / `skills-lock.json` が加わったのは Issue #948。行を実行時に折り返すのは、2 パス用に置いた固定の改行が 4 パスになったとき 124 桁まで伸びたため
- `package-lock.json` の注記を `in_git_add=False` で列挙から外すのは Issue #556 の対応方針 3 の結論で、`in_git_add=False` を残すのも Issue #556 の再発防止。Issue #842 で既定が `-A` になり、既定の経路では注記が要らなくなった後も残している
- `git add` の行を `_root_outputs.py` から作るのは Issue #642（2 つの一覧のずれが `--quartz-pages` の最初の Pages ビルドを壊した Issue #556 による）
- LICENSE を書かないのは Issue #558。README の項目はライセンス表示の第 4 層（Issue #645）で、README を表示専用にし編集しないと決めたのは Issue #282。サイト全体の層は第 2 層
- `.wikicommit/guides/` への案内は Issue #846。全 variant に出すようになったのは、Quartz と無関係なガイドが Issue #867 で加わってから — それまでは棚にあった唯一のガイドが Quartz のプラグインに関するものだったので、Quartz の variant に限っていた
- `build_licensing_step()` が README を作った実行では README の項目を省く・`--readme-created` は Issue #1034（既存の README に触れないのは Issue #282）
- `.wikicommit/schemaorg-vocab.json` は Issue #319。init の中でこれを作りうる最初の工程が明らかな型の判断（Issue #490）で、それより前は generate / collect だけが作っていた（その出力は merge でコミットされる）。条件が選択的な列挙だけを左右するようになったのは Issue #842
- `npm run install-plugins` が成功していれば手順から省くのは Issue #380
- Codex の呼び出し方（`$wikicommit-…`）の注記は Issue #1015
- 手順番号が 2 桁になる場合の字下げは、Issue #846 で 10 手順の一覧が初めて現れた（`quartz_pages` で lychee も markitdown も入っていない場合）ため

## _schemaorg_vocab.py

本文に節を持たない（仕様は本文の `check_schema_org_type.py` の節 — 語彙を読み込んで共有することは「使用場面」、キャッシュの置き場と再取得は「保存先（Git管理下）」 — と、`docs/DesignDoc-skills.md` §11.5 の置き場所の表〈共有モジュール〉。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 353 → 344、コード 140 → 140、docstring 166 → 157、コメント 5 → 5、空行 42 → 42（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 15 → 0（`pre-Issue-#495`・`pre-Issue-#496` の形の参照も外した）。出力する文字列には `#NNN` は無い。他のスクリプトが import する共有モジュールなので、名前は 1 つも変えていない。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このモジュールは Issue #495 で `check_schema_org_type.py` から切り出した。`validate_frontmatter.py` に新しく入った `properties:` の domainIncludes 検査が同じ語彙の読み込みと継承チェーンを要したため。切り出す前の同じロジックは `check_schema_org_type.py` にあり、自分で `ERROR: ...` 行を出していた。`property_in_domain()` を共有にしたのも同じ Issue
- `rangeIncludes` / DataType の参照（`range`・`is_datatype`、`is_in_datatype_lineage()`）は Issue #496。`URL` がその動機になった例。これらのキーを持たないキャッシュ（Issue #496 より前の版が書いたもの）は自動で作り直す
- property の `comment` と `properties_available_to()`（`--list-properties`）は Issue #497。Issue #495 が旧 `recommended` フィールドの「書き始めの手掛かり」としての役割を外したため
- `.wikicommit/schemaorg-vocab.json` を Git で追跡するのは Issue #319
- 古いキャッシュの代償が軽くなくなった（`validate_frontmatter.py` の型の実在検査が ERROR を出す）のは Issue #512
- テスト用の環境変数 `WIKICOMMIT_TEST_SCHEMA_ORG_JSONLD` は Issue #285
- `load_or_build_index()` がすべての失敗を `(None, error_message)` に畳むのは、`validate_frontmatter.py` が wikicommit-merge のたびにこれを呼ぶようになったため。それまではたまに呼ばれる `check_schema_org_type.py` の CLI だけがこの経路を通っていた。同じ docstring は呼び出し元を「the two callers」と数えていたが、いまは 6 本が呼ぶので数を外した
- 導入済みの下位型を推測させずに示す（`installed_descendants()`）のは Issue #565

## _frontmatter.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.5 の置き場所の表〈共有モジュール〉。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 151 → 147、コード 47 → 47、docstring 83 → 79、コメント 0 → 0、空行 21 → 21（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 5 → 0（うち 1 つは行をまたいで `Issue` と `#232` が分かれたもの）。出力する文字列には `#NNN` は無い。他のスクリプトが import する共有モジュールなので、名前は 1 つも変えていない。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このモジュールへの集約は 2 段で、`convert_wikilinks.py`・`check_wikilinks.py`・`check_orphans.py`・`check_translation_status.py`・`validate_frontmatter.py` が Issue #212、`check_expires.py`・`check_ingest_freshness.py`・`search_index.py` が Issue #231。それまでは各スクリプトが `---\n...\n---` の抽出を自前で持ち、実際のバグになる形で食い違っていた — BOM は `utf-8-sig` で読むものと素の `utf-8` で読むものがあり、BOM 付きのページ（一部の Windows のエディタが書く）は半数のスクリプトで frontmatter が黙って検出されなかった。空のブロックは、集約前の 5 本のうち 4 本が正規表現で抽出しており、`validate_frontmatter.py` だけが行の走査で正しく扱っていた。このモジュールはその行の走査を引き継いだ
- 集約の前例として `_wikilink.py`（Issue #114）を挙げていた
- `parse_frontmatter_cached()` のキャッシュは Issue #232。`check_wikilinks.py` と `convert_wikilinks.py` が同じ `@lru_cache` の包みをそれぞれ持つようになっていたのを、ここにまとめたのは Issue #266

## _groups.py

本文に節を持たない（仕様は `docs/DesignDoc-data.md` §4.5.3。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 180 → 180、コード 109 → 109、docstring 37 → 37、コメント 10 → 10、空行 24 → 24（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 4 → 0。出力する文字列には `#NNN` は無い。他のスクリプトが import する共有モジュールなので、名前は 1 つも変えていない。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- グループファイルは Issue #1035
- 内容が変わった `reviewed` ページを `pending` に戻す `reset_review_on_content_change.py` は Issue #724
- slug を言語中立にする規則は Issue #193
- ラベルを言語ごとに持つ形（`site_description` と同じ形）は Issue #671

## _skill_tree.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.3「Skill ツリーの位置を仮定してよい箇所・してはならない箇所」と §11.5「置き場所の判断基準」の `_skill_tree.py` の項。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 44 → 44、コード 11 → 11、docstring 27 → 27、コメント 0 → 0、空行 6 → 6（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 4 → 0。出力する文字列には `#NNN` は無い。他のスクリプトが import する共有モジュールなので、名前は 1 つも変えていない。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このモジュールは Issue #1021。それまで `record_run.py` と `check_distribution_freshness.py` はどちらも `.claude/skills/` を固定で持っており、Codex だけに入れたリポジトリでは、前者が正しく読んだパスを `token: missing` と記録し（Issue #925 が版ずれについて直したばかりの向き）、後者が「wikicommit-init is not installed」とすべて 0 の要約を出して、Issue #930 が実行の最初に置いた版ずれの検査が黙って空になった
- `.claude/skills` を先に探す理由について、docstring は「Issue #1021 より前に動いていたすべてのリポジトリで、このスクリプトの答えをそれまでと同じに保つ」と書いていた

## set_frontmatter_field.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.5 の委譲表の `set_frontmatter_field.py` を挙げる行と、同じ節のスクリプト依存図。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 287 → 283、コード 148 → 148、docstring 90 → 86、コメント 9 → 9、空行 40 → 40（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 6 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 共有実装にしたのは Issue #371。それまでこの部分書き換えは 3 箇所に独立実装として重複していた — `wikicommit-review` の SKILL.md Step 5（`review_status` を無条件で `reviewed` に上書き）、`review-issue-close-sync.yml`（`pending` のときだけ上書き）、`remove_page.py`（`status` / `removed_at` 等の複数フィールドを足す。当時は `wikicommit-remove` の Skill 内）。本スクリプトは前の 2 つを置き換え、`remove_page.py` は Issue #371 の完了条件で対応範囲の外とした
- `remove_page.py` が `.wikicommit/scripts/` に移ったのは Issue #1210（複数フィールドを 1 回で書く処理は自前のまま）
- `--unset` は Issue #705
- `FrontmatterFileError` と `apply_frontmatter_fields()` をプロセス内で使えるようにしたのは Issue #724（`reset_review_on_content_change.py` のため）

## remove_page.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.5 の委譲表の `remove_page.py` を挙げる行と、`docs/DesignDoc-pipeline.md` §6.5・`docs/DesignDoc-data.md` §4.5。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 292 → 291、コード 189 → 189、docstring 54 → 53、コメント 8 → 8、空行 41 → 41（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 5 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- `wikicommit-remove` の Skill 内から `.wikicommit/scripts/` に移したのは Issue #1210。それまでは Skill 内のスクリプトとして自己完結の慣行に従い、frontmatter の読み取りの写しを持っていた
- `.wikicommit/wiki/` から `entity/` への改名は Issue #477
- `rebuild_index.py` が `- [[<type>/<slug>]]` を書くようになったのは Issue #678。docstring は、それ以前はリストマーカーなしで、さらに `— <title>` の接尾辞が付いていたと書いていた
- 空になった `##` 見出しを落とす `_drop_empty_sections()` は Issue #1136。グループごとの節（`_grouped_body()`）は Issue #1035

## wikicommit-merge/scripts/workflow_checks.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.0 の Skill ワークフローエンジンと §11.5「置き場所の判断基準」の Skill ごとの `workflow_checks.py` の項、merge の工程は `docs/DesignDoc-pipeline.md` §6.2。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 1,025 → 1,024、コード 650 → 650、docstring 163 → 162、コメント 81 → 81、空行 131 → 131（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 5 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 各 Skill の検査が同じように読むヘルパーを `.wikicommit/scripts/_workflow_checks.py` に置いたのは Issue #1219
- `path_argvs()` が 1 本のコマンド行を `limit` 文字以内に収める（インタプリタ・スクリプトのパス・フラグも数える）のは Issue #1263
- `wikilink_argvs()` が `--changed` と `--deleted` を別々の呼び出しに分けるのは Issue #1257
- `links` とバッチの回し方（`check_external_links.check_link_batches()`）を共有する、`/wikicommit-status` の全ページの検査は Issue #1182。構造化した所見を返しつつ、実行の `lychee.json` には文言だけを残すことは Issue #1243

## check_quartz_setup.py

本文に節を持たない（`docs/DesignDoc-skills.md` §11.5「置き場所の判断基準」の `wikicommit-init` の 4 本の 1 つで、仕様は docstring と `wikicommit-init` の SKILL.md の Step 3.d。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 71 → 71、コード 33 → 33、docstring 24 → 24、コメント 2 → 2、空行 12 → 12（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0（`Issue` の付かない `#229` も外した）。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- Quartz のセットアップ状態の判定をこのスクリプトにしたのは Issue #229。docstring は、この状態機械の判定をそれまではエージェントが読んでいた（「previously agent-read」）と書いていた
- `quartz/` があるときに `npm run install-plugins` を best-effort で試し `install_plugins_ok` を返すのは Issue #380

## _version.py

本文に節を持たない（仕様は `docs/DesignDoc-data.md` §3.3「`wikicommit_version` — 最後に同期した版」。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 69 → 69、コード 5 → 5、docstring 54 → 54、コメント 5 → 5、空行 5 → 5（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- インストール先のリポジトリまで届く唯一の版の出所にしたのは Issue #577

## _workflow_checks.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.5「置き場所の判断基準」の `_workflow_checks.py` の項。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 177 → 175、コード 86 → 86、docstring 51 → 49、コメント 7 → 7、空行 33 → 33（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- このモジュールは Issue #1219。docstring は、それまで各 Skill の `workflow_checks.py` は単独で動くように書かれ、共有するヘルパーがそれぞれに写されて、写しがずれ始めていた — `read_markdown` が 2 つの Skill では `(frontmatter, body)` を、3 つ目では frontmatter だけを返し、2 つの `records_since` は引数も戻り値も違っていた — と書き、実行記録やレビュー記録の読み方を直すには写しを全部探す必要があったと書いていた（いまは、各 Skill に写したヘルパーはずれ、読み方を直すたびに写しを全部探すことになる、とだけ書く）

## wikicommit-generate/scripts/workflow_checks.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.0 の Skill ワークフローエンジンと §11.5「Skill 内スクリプト」の表の `wikicommit-generate` の行、generate の工程は `docs/DesignDoc-pipeline.md` §6.1。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 629 → 629、コード 432 → 432、docstring 68 → 68、コメント 44 → 44、空行 85 → 85（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 3 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 各 Skill の検査が同じように読むヘルパーを `.wikicommit/scripts/_workflow_checks.py` に置いたのは Issue #1219（4 つの写しが持つブートストラップのコメントは同じ形のまま外した）
- `MOVED_SCRIPTS` の 3 本を Skill 内の `scripts/` から `.wikicommit/scripts/` に移したのは Issue #1210
- `page_in_lang_dir()` の docstring が書く不具合（入力されたままの `<Type>/<slug>` がレビューの工程の記録するパスに一致せず、`merge-absorb` が「not ready」として飛ばされ、実行は成功を報告したまま統合が途中で止まった）は Issue #1131

## wikicommit-synthesize/scripts/workflow_checks.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.0 の Skill ワークフローエンジンと §11.5「Skill 内スクリプト」の表の `wikicommit-synthesize` の行。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 426 → 426、コード 315 → 315、docstring 41 → 41、コメント 22 → 22、空行 48 → 48（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 各 Skill の検査が同じように読むヘルパーを `.wikicommit/scripts/_workflow_checks.py` に置いたのは Issue #1219

## wikicommit-translate/scripts/workflow_checks.py

本文に節を持たない（仕様は `docs/DesignDoc-skills.md` §11.0 の Skill ワークフローエンジンと §11.5「Skill 内スクリプト」の表の `wikicommit-translate` の行、translate の工程は `docs/DesignDoc-pipeline.md` §6.4。置き場の判断は上の `init.py` の見出し）。

**docstring・コメントから経緯を移した（Issue #1343。規則は Issue #1329）**: 移す前後の行数は、総行数 400 → 400、コード 272 → 272、docstring 41 → 41、コメント 35 → 35、空行 52 → 52（docstring 内の空行は docstring に数える。数え方は `convert_wikilinks.py` の記録と同じ）。`Issue #` はコメント・docstring で 1 → 0。出力する文字列には `#NNN` は無い。

docstring・コメントにあって本文に無かった経緯は次のとおり:

- 各 Skill の検査が同じように読むヘルパーを `.wikicommit/scripts/_workflow_checks.py` に置いたのは Issue #1219

## check_source_overlap.py

**新設（Issue #1380。生成側の規則は Issue #1379）**: 2026-10-18 に `ai-driven-dev-wiki` の BlogPosting 26 枚と DefinedTerm 10 枚を元記事と比べたところ、6 語以上一致する語の割合は 3〜39%（中央値 約 19%）で、BlogPosting の型には以前から「逐語で言い直さない」規則があったのに効いていなかった（`dev/source-overlap-2026-10/results.md`）。Issue #1379 が Pass 3 に「自分の言葉で書く・ソースの順に追わない」を足して 8 枚を作り直すと平均 32% → 7% に下がり、対照（旧規則で作り直したもの）は 32% のまま変わらなかった（`dev/source-overlap-2026-10/results-regenerate-2026-10-19.md`）。規則が効いているかはこうした測り方が無いと分からないため、同じ数え方を配布スクリプトにした。

試作の `dev/source-overlap-2026-10/measure.py` との違い:

- **比べる相手**: 試作は元記事の HTML をタグを剥がしただけで読んでいた（ナビゲーション等のページの外枠が混ざる）。本スクリプトは Pass 1 が残した抽出テキストのキャッシュ（markitdown の出力）を読む。生成が実際に読んだ本文と比べるためである
- **ページ側の除外**: 試作は frontmatter・`## Generation Notes`・WikiLink の記法を除くだけだった。引用符・コード・引用ブロック・表を除き、除いた箇所で本文を切るようにした。そのため同じページでも値が下がる（`ai-driven-dev-wiki` 全体の中央値は 10%。試作で測った 36 枚の中央値 約 19% と直接は比べられない）。作り直した 8 枚の対照・新規則の値は試作とほぼ同じだった（対照 20〜37% ／ 試作 22〜39%、新規則 0〜11% ／ 試作 2〜12%）
- **Key Points の並び順**: 試作は Key Points が元記事の順に並ぶ率も出していたが、位置が取れる項目が少ないと率が粗く（Issue #1379 の計測でも 3〜7 項目）、閾値を置ける量にならないので入れなかった
- **日本語・中国語**: 試作は `[a-z0-9']+` だけを語にしていたので、かな・漢字の本文は 0 語だった。1 文字を 1 トークンとし、一致の長さを別に持つ（`--cjk-n`）。Issue #1380 が名指しした 3 つの Wiki には ja のソースから書かれた ja のページが無かった（`ai-driven-dev-wiki` の ja ページで `translated_from` を持たない 13 枚はすべて `index.md`）ので、`saitama-city-wiki` で決めた

閾値を決めるときに退けたもの:

- **15%**: Issue の草案の時点の目安（試作の中央値 約 19% の少し下）。本スクリプトの数え方では `ai-driven-dev-wiki` の 354 / 1,076 枚が報告され、新しい規則のページの最大 11% との間に余裕も無い
- **ページの語数による下限を大きく取る**: 草案では「固有名詞・術語が多い短いページは割合が上がりやすい」と見ていたが、`ai-driven-dev-wiki` では 150 語未満のページ（24 枚）の中央値 14%、150〜300 語 14%、300〜600 語 10%、600 語以上 9% で、差は小さかった。100 語未満は 9 枚しかなく、1 つの一致で割合が大きく動く範囲だけを外した
- **`--cjk-n 16`**: 偶然の一致は 90% 点・99% 点とも 3% 以下に下がるが、写したページの割合も下がる（中央値 41% → 34%）。12 文字で偶然の一致は 90% 点 1% であり、報告されたページの最長一致は 100〜240 文字だった

## 付録: 本文の行に付いていた Issue 番号と書き換えた表・図の行（移行時点）

本文を現在形に書き直す際に、見出し・表の行・コードブロック（図）の行、および Issue 番号だけを外した段落の行から `Issue #NNN` と経緯を外した。どの記述がどの検討に由来するかを辿れるよう、書き換えた行を移行時点の文面のまま、当時の見出しごとに残す（散文の段落の旧版は上の各節にある）。

### `.wikicommit/entity/` の走査は `_wikilink.py` に集約する（Issue #677）（旧見出し）

（見出しのみ）

### `.wikicommit/view/` を走査するかはスクリプトごとに決める（Issue #675）（旧見出し）

```text
| 主消費者 | `check_derivation_freshness.py` | `derived_from` を持つページの主な置き場が view ツリーになった。**entity ツリーの走査は続ける** — 本 Issue 以前に書かれた合成ページはそこに残る（自動移行しない） |
| 含める（所見は entity ページにしか出ない） | `check_retracted_sources.py` | view ページは `sources[]` を持たないので直接は一致しないが、走査対象から外さない — 走査の対象と所見の有無は別の話であり、除外すると「view ページは見ていない」という事実が読む側から消える（Issue #737） |
| どちらも走査しない | `record_run.py`・`check_run_records.py` | 対象は `.wikicommit/run/` であり、ページを 1 枚も読まない（Issue #790） |
| 両方を受け付ける（走査はしない） | `reset_review_on_content_change.py`・`record_review.py` | ツリーを歩かず引数のページだけを見るため上の 3 分類には当たらないが、受け付ける接頭辞は `.wikicommit/entity/` と `.wikicommit/view/` の両方である。呼び出し元の `wikicommit-fix` が両ツリーを対象に取るため、entity だけに絞るとその半分が黙って素通りする（Issue #724） |
```

### merge の blocking な 3 本は status が全ページに走らせる（Issue #976）（旧見出し）

```text
| `check_wikilinks.py` — `status: removed` ページへのリンク | 素通り | **Step 3 が報告する（本 Issue で追加）** |
| `validate_frontmatter.py` ERROR | 素通り | **同上** |
| `check_raw_html.py` ERROR | 素通り | **同上** |
```

### スクリプト一覧（旧見出し）

```text
| `check_raw_html.py` | ページ本文中の生 HTML タグ検出（Issue #377） | blocking エラーあり |
| `read_policy.py` | ポリシーファイルが実際に述べている散文方針の抽出（記入例・HTML コメントを除去。読み取り専用。Issue #844） | なし（常に 0） |
| `match_index_only.py` | `source-policy.md` の `index_only:`（ドメインとページの 2 形）に URL が該当するかの判定（読み取り専用。Issue #1032） | なし（常に 0） |
| `match_existing_names.py` | Pass 2c が抽出したエンティティの名前を、既存ページの `title` / `aliases` と照合（読み取り専用。Issue #1096） | 標準入力が JSON のリストでない（exit 2） |
| `check_schema_org_type.py` | Schema.org 語彙に対する型・プロパティの実在検証、型名一覧の取得と候補型の説明文の取得（2 段階。Issue #798）（`wikicommit-generate`・`wikicommit-schema-propose` 共有） | 型が語彙に存在しない、プロパティが型（祖先型含む）に属さない、語彙の取得・パースに失敗、または `--type`/`--list-type-names`/`--describe`/`--list-installed-hierarchy` のいずれも未指定 |
| `build_survey_view.py` | Wiki 全体を1つのコンテキストに収まる縮約ビューへ落とす（`wikicommit-synthesize` の俯瞰モード〈Issue #586〉と `wikicommit-collect` の Step 3.5〈Issue #672〉が共有。`--include-view` を渡さない限り view ツリーは対象外。Issue #675） | なし（常に 0） |
| `build_onehop_context.py` | Pass 4 の check 8 が要る 1 ホップ近傍の組み立て（`wikicommit-generate` の Pass 4 と `--regenerate` が共有。Issue #947） | `--page-path` が entity / view ツリーの外を指す |
| `rebuild_index.py` | Type ディレクトリの `index.md`、および view ツリーの言語別 `index.md` を決定論的に再構築（`wikicommit-generate`・`wikicommit-translate`・`wikicommit-synthesize` 共有。Issue #406・#547・#675） | なし（常に 0） |
| `check_extraction_quality.py` | 既知JS-shellドメイン判定（ブロッキング）・取得能力の事前チェック（ブロッキング。Issue #574）・抽出テキストの低情報密度判定（警告。Issue #562）（`wikicommit-generate`・`wikicommit-collect` 共有。Issue #425） | ドメインが既知不可リストに一致（`check-domain`）、必要な追加パッケージが未導入（`check-fetch-capability`）、抽出テキストが低密度（`check-density`）、または対象ファイルが読み込めない |
| `reconcile_ingest_status.py` | `status: pending` のソース管理ファイルのうち内容が既に公開ページの `sources` に使われているものを検出し `status: generated` に是正（Issue #474。意図して requeue されたファイルは 3 つの条件が守る。Issue #874） | なし（常に 0） |
| `reset_review_on_content_change.py` | 内容が書き換わった `reviewed` ページを `pending` へ戻し `reviewed_by` を落とす（`wikicommit-generate` Pass 4・`wikicommit-fix` 共有。Issue #724） | 引数が entity/view ツリーの外を指す、ページが存在しない、frontmatter がパースできない |
| `record_review.py` | レビュー 1 件を `.wikicommit/review/` 配下の不変ファイルとして記録（`wikicommit-generate` Pass 4・`wikicommit-review`・`wikicommit-synthesize`・`review-issue-close-sync.yml` 共有。Issue #750） | 引数が entity/view ツリーの外を指す、`--kind ai` に `--model` が無い、`--result` が `discarded` 以外なのにページが存在しない、JSON が壊れている、書き込みに失敗 |
| `check_review_coverage.py` | レビュー記録の集計・未レビュー／抜取候補／失効の列挙（`wikicommit-status` 専用。Issue #750） | なし（常に 0） |
| `record_run.py` | 実行 1 回を 1 ファイルとして記録（`start` で開き `end` で閉じる。4 つの書き込み系 Skill が共有。Issue #790） | 引数不正、`end` に渡されたパスが存在しない、`--outcome` の値が整数でない、frontmatter が読めない |
| `driver.py` | 多段の Skill の工程の順序を持つ（`start` / `next` / `done` / `status` / `check-merge` / `abandon`。`wikicommit-generate` と `wikicommit-merge`。Issue #1085） | `done` が受け付けなかった（今の工程でない・確認に失敗・トークンが合わない）、`check-merge` が止めた。使い方の誤り・壊れた工程の定義は exit 2 |
| `check_run_records.py` | 直近の実行と完走しなかった実行の報告（`wikicommit-status` 専用。Issue #790） | なし（常に 0） |
| `check_retracted_sources.py` | 人間が取り下げたソース（`status: retracted`）を `sources[]` に持つページの検出（`wikicommit-status`。Issue #737）と、取り下げ済みソースの一覧（`--list`。`wikicommit-review` / `wikicommit-fix` がソースを読む前のガードに使う。Issue #928） | なし（常に 0） |
| `check_actions_pr_permission.py` | "Allow GitHub Actions to create and approve pull requests" リポジトリ設定の確認（`wikicommit-status` 専用。Issue #478） | なし（常に 0） |
| `check_recurring_characters.py` | `properties.character` にプレーンテキストで列挙された登場人物のうち、複数作品に再登場するが Person ページを持たないものの検出（`wikicommit-status` 専用。Issue #560） | なし（常に 0） |
| `check_self_referential_tags.py` | ページ自身の `title`／`type` を繰り返すだけのタグの検出（`wikicommit-status` 専用。Issue #571） | なし（常に 0） |
| `check_installed_type_usage.py` | インストール済みスキーマファイルのうちページが 0 件のもの・より具体的な子孫型がインストール済みなのに祖先型でページが書かれているものの検出（`check_schema_coverage.py` の対。`wikicommit-status` 専用。Issue #565） | なし（常に 0） |
| `check_unlinked_entity_mentions.py` | エンティティ型を range に持つ `properties:` キーの値が、実在するページを指すのにプレーンテキストで書かれているものの検出（`check_wanted_pages.py` の鏡像。`wikicommit-status` 専用。Issue #561） | なし（常に 0） |
| `check_property_wikilink_reinforcement.py` | 型テンプレートの Entity-only/Mixed な `properties:` キーのうち、WikiLink化への補強（`granularity` 言及・`[[Type/slug]]` プレースホルダー）を持たないものの検出（`wikicommit-status` 専用。Issue #539） | なし（常に 0） |
| `check_schema_files.py` | 書かれた型ファイル自体が動く形になっているかの検証（`wikicommit-status` 専用。Issue #889） | なし（常に 0） |
| `check_name_collisions.py` | 同じ名前（タイトル・別名）に答える複数ページの検出。`.wikicommit/relations.yml` で判断済みの組を外す（`wikicommit-status`・`wikicommit-relate` 共有。Issue #1095） | なし（常に 0） |
| `check_groups.py` | `.wikicommit/groups/<Type>.yml` の検証・型ごとの未分類 / stale の件数、`--type` で未分類ページの一覧（`wikicommit-status`・`wikicommit-organize` 共有。Issue #1035） | なし（常に 0） |
| `record_relation.py` | 人が決めたページ同士の関係を `.wikicommit/relations.yml` に 1 項目追記（`wikicommit-relate` 専用。Issue #1095） | 引数不正・存在しないページ・ファイルがリストとして読めない（何も書かない） |
| `merge_pages.py` | 「同一」のページの統合の計画・記録・確認（`plan` / `record` / `check`。`wikicommit-generate --regenerate --merge` 専用。Issue #1119） | 統合を許さない（判断の記録が無い・翻訳・`manual` ソース・ハッシュの食い違い等）、`check` で未完了の部分がある |
| `rewrite_merged_links.py` | `merged_into` をたどって、吸収されたページへの WikiLink を残すページへ書き換える（同上。Issue #1119） | なし（常に 0） |
```

### build_onehop_context.py — 目的（旧見出し）

```text
Pass 4 の check 8（WikiLink 1 ホップ以内のページ間矛盾。Issue #566）は、レビューサブエージェントへ渡す追加コンテキストとして「このページが指す既存ページ」＋「このページを指すページ」を要求する。この集合を組み立てるのが本スクリプトである（Issue #947）。
```

### build_onehop_context.py — 置き場所が `.wikicommit/scripts/` である理由（Issue #947）（旧見出し）

（見出しのみ）

### build_onehop_context.py — 処理フロー（旧見出し）

```text
2. stdin の本文から `extract_wikilinks()`（＝ `WIKILINK_RE`）で `[[Type/slug]]` を出現順に取り、`resolve_wikilink()` で解決する。解決順序は `docs/DesignDoc-pipeline.md` §6.4 のクロス言語フォールバック（同 lang → `primary_lang` → 未解決）。**未解決のリンクは何も言わずに落とす** — まだ誰も書いていないページを指すことは正常かつ非ブロッキングであり（Issue #340）、それを報告するのは `check_wanted_pages.py` の仕事である
```

### build_survey_view.py — 目的（旧見出し）

```text
`/wikicommit-synthesize` を引数なしで実行した場合（俯瞰モード。Issue #586）、「何について書くか」自体を Wiki 全体から見つける必要がある。Wiki の全文は1つのコンテキストに入らないため、本スクリプトは各ページを「横断的な構造を担う数行」— `title`・`type`・`tags`・`properties.description`・`##` 見出し・発リンク — に縮約し、リンクグラフから算出した集計（ハブ・タグ・型）を添えて出力する。
```

### build_survey_view.py — `--pages` — 名指ししたページだけを縮約する（Issue #1075）（旧見出し）

（見出しのみ）

### build_survey_view.py — 出力フォーマット（旧見出し）

```text
`sources=N` はそのページの `sources[]` のエントリ数である（Issue #990）。`/wikicommit-collect` Step 3.5 が「中心概念が 1 本の資料にしか立っていない」ことを着眼点の材料にするためのもので、`check_orphans.py` の `ORPHAN:` が出自付きで「端が薄い」を出すのと対になる。**翻訳ページ（親から継承する）と view ページ（`derived_from` であって `sources` ではない）では区画ごと省く** — `0` は「ソースが無い」と読めるため。**`HUB:` 行には置かない** — `HUB:` はキー単位で、そこに出すと「どのページの `sources[]` を代表させるか」の判定がもう 1 箇所要る。`HUB:` に出るキーには必ず対応する `PAGE:` 行がある（`hubs` は `listed_keys` でフィルタされる）ので、単位の不一致を作らずに同じ情報が届く。frontmatter の読み取りは `title` / `tags` と同じ 1 回に相乗りし、走査は増えない。数字の意味と決定事項の全体は `docs/DesignDoc-publish.md` §8.8.1「ハブ行のソース件数と、同じソースに立つハブ」にある（経緯は `docs/history/DesignDoc-publish.md` の同じ見出し）。
```

### check_extraction_quality.py — 目的（旧見出し）

```text
- `check-fetch-capability`（ガードC・取得能力の事前チェック。Issue #574）: 抽出を試みる前に、URLのホストが「完全な抽出に追加の Python パッケージを要する」既知ホストかどうかを判定し、要する場合はそのパッケージが実際に import 可能かを確認する。初期エントリは YouTube 系ホスト（`youtube.com`/`youtu.be`/`m.youtube.com` — この3ホストはリダイレクト解決後にいずれも `https://www.youtube.com/watch?…` に着地し、実測でバイト単位で同一の抽出結果になる）と `youtube_transcript_api`。`music.youtube.com` はリダイレクトしないため `YouTubeConverter` 自体が適用されず、パッケージを入れても解決しない — こちらはガードB（`KNOWN_JS_SHELL_DOMAINS`）の担当。判定はホスト単位であり、同じホスト上の `/watch?v=…` と `/shorts/<id>`・`/playlist`・チャンネルページを区別しない（後者も `YouTubeConverter` の前方一致要件を満たさず抽出できないが、ガードCは「そのホストが要するパッケージが導入済みか」しか保証しない — 残りは `wikicommit-generate` Pass 1 手順6の抽出結果の形状チェックが担う）。
```

### check_extraction_quality.py — 処理フロー（`check-domain`）（旧見出し）

```text
3. `.wikicommit/source-policy.md` の `wikicommit.exclude_domains`（Issue #564。`docs/DesignDoc-data.md` §3.4）を読み、**組み込みリストとの和集合**として同じ判定を行う。一致すれば `BLOCKED:`（組み込み側とは別のメッセージ。どちらのリストで落ちたかを呼び出し側が区別できる）を出力して終了する
```

### check_extraction_quality.py — 処理フロー（`check-density`）（旧見出し）

```text
4. 比率が `LOW_DENSITY_THRESHOLD`（0.3）未満であれば `LOW_DENSITY:`、以上であれば `OK:` を出力する。`LOW_DENSITY:` の場合は、非自然文と判定された文字の内訳（`links` / `numbers/tables` / `other markup` の割合）を同じ行に添える — 人間が続行可否を判断する材料として、リンクが多いだけの正当なページ・統計表・実際のスクリプトシェルを見分けられるようにするため（Issue #562）
```

### check_extraction_quality.py — 終了コード（旧見出し）

```text
- `check-fetch-capability`: `0` = 追加パッケージ不要、または必要なパッケージが導入済み、`1` = 必要なパッケージが未導入。`1` は呼び出し側にとって「処理全体を停止して `pip install` を案内する」シグナルであり、そのソースを `status: failed` にするシグナルではない（Issue #574）
```

### validate_frontmatter.py — 使用場面（旧見出し）

```text
- `wikicommit-status` Skill：Step 3。引数なしで全ページに対して実行し、`ERROR:` 行だけを拾う（Issue #976。冒頭の「merge の blocking な 3 本は status が全ページに走らせる」節）
```

### validate_frontmatter.py — Wiki ページ共通フィールド（旧見出し）

```text
| `type` | string | `schema:` プレフィックスで始まること。`custom/` プレフィックスを持たず（`type_name` が `custom/` で始まらず）、かつ Schema.org 語彙（`.wikicommit/schemaorg-vocab.json`）にも実在しない場合は ERROR（Issue #512。誤字・命名規約違反等の検出。`custom/` プレフィックスを持つ型、および語彙が取得できない場合はこの検証をスキップする — 前者は Schema.org 語彙に存在しないことが正規の設計であるため、後者は §5.2 の `properties:` フォーマット検証と同じ理由で非ブロッキングとする）。`.wikicommit/schema/<Type>.md` というローカルファイルが実際に存在するかどうかとは独立の判定であり、両者は食い違いうる — ローカルファイルがなければ `resolve_type_schema()` 側の別の WARNING（「スキーマファイルが見つかりません」）も同時に出る。この ERROR はキャッシュの鮮度にも影響される点に注意: `.wikicommit/schemaorg-vocab.json` は TTL を持たず手動削除でのみ再取得されるため（`_schemaorg_vocab.py`）、Schema.org 側で新しく追加された型を使ったページは、そのリポジトリのキャッシュが再取得されるまで本 ERROR で `wikicommit-merge` がブロックされ続ける。対処はキャッシュファイルを手動削除して再実行すること。**あわせて、ページのファイルパスと `type:` の一致も検証する**（Issue #545）: `.wikicommit/entity/<lang>/<Type>/<slug>.md` に置かれたページの `type:` は `schema:<Type>` でなければならず、custom 型では `custom/` サブパスを含む（`schema:custom/Decision` は `.wikicommit/entity/<lang>/custom/Decision/` に置く。`_wikilink.py` の `parse_wiki_path()` がパスから `(lang, type, slug)` を導出する）。不一致は ERROR。`<lang>/<Type>/<slug>.md` の形に解決できないファイル（`.wikicommit/entity/` 直下に置かれたページ、Issue #477 以前の `.wikicommit/wiki/` プレフィックスのままのページ）はこの検証の対象外とし、何も報告しない（新旧混在を許容する方針）。`type:` 自体が欠落している・`schema:` プレフィックスを持たない場合も、それぞれ別に報告済みのため重ねて報告しない |
| `expires_at` | string | `YYYY-MM-DD` 形式。`generated_at` と両方あり、`expires_at <= generated_at` なら WARNING（Issue #1130。生成した時点で既に過ぎている日付は「この日を過ぎたら読み直せ」という予定として働かず、`check_expires.py` が生成直後から EXPIRED を出す。多くは文書の経緯にある第三者宛ての締切〈各国政府へのコメント期限等〉を取り違えたもの。判断を要さず決まるので指示文ではなくここで見る〈Issue #474〉。手書き・旧版のページにもありうるので ERROR にはしない。`/wikicommit-generate --regenerate` は `expires_at` を保つので、直すのは人の手である） |
| `generated_with` | string | 空文字列不可。このページを生成した WikiCommit 自身の版（Issue #577。任意フィールドで、欠如は「この機能追加より前に生成された」ことを意味する。semver パターンへの照合は行わない — モデル ID を正規化表に照合しないのと同じ理由） |
```

### validate_frontmatter.py — `sources` 各要素のフォーマット（旧見出し）

```text
| （全要素） | `license` | 任意。存在する場合は空でない文字列（空文字列は ERROR。「不明」はフィールドごと省略して表す）。値の中身は検証しない — SPDX 語彙への照合もソースの実際の条件との突合も行わない（Issue #558。`docs/DesignDoc-publish.md` §8.10） |
```

### validate_frontmatter.py — `properties:` のフォーマット（Issue #495）（旧見出し）

```text
4. 型が語彙に存在しない場合は ERROR（Issue #512。`type` フィールドに対する ERROR — 上記「Wiki ページ共通フィールド」表の `type` 行と同じ検証をここで実行する。誤字・命名規約違反等で `.wikicommit/schema/<誤った型名>.md` というローカルファイルさえ存在すれば `resolve_type_schema()` は WARNING すら出さずに通過してしまうため、`properties:` を検証する `validate_schema_properties()` 側でも独立に検証する）。この場合、`properties:` の各キー検証・下記のトップレベル平置き検出のいずれも実行せず打ち切る（型の祖先チェーンが解決できないため、いずれも判定不能）。
```

### validate_frontmatter.py — 翻訳ページ追加フィールド（`translated_from` が存在するページ）（旧見出し）

```text
| `translated_from` | 必須 | リポジトリルートからの相対パス（例: `.wikicommit/entity/ja/Person/yamada-taro.md`）。対象ファイルが実在すること（Issue #477 以前に書かれた `.wikicommit/wiki/` プレフィックスのままの値も `_wikilink.py` の `resolve_stored_entity_path()` 経由で解決を試みる。`docs/DesignDoc-data.md` §3.1「旧ディレクトリ名 `.wikicommit/wiki/` の後方互換」参照） |
| `source_commit` | 必須 | 40文字の git コミットハッシュ（`[0-9a-f]{40}`）、または空文字列（Issue #409 — `wikicommit-translate` は原文ページに commit が無い場合〈生成直後でまだ `wikicommit-merge` されていない等〉、空文字列のまま書き込む。`check_translation_status.py` はこれを正しく `STALE` として検知する） |
| `translated_by` | 任意 | 空文字列不可（`generated_by` と同じフォーマット制約。翻訳実行モデル ID。Issue #453） |
| `translated_with` | 任意 | 空文字列不可（`generated_with` と同じフォーマット制約。この翻訳を生成した WikiCommit 自身の版。Issue #577） |
| `translator_notes` | 任意 | list 型（各要素は string）。各要素の内容自体（`YYYY-MM-DD: <note>` 形式）に対する機械検証は行わない（`## User Notes` と同じ、フリーテキストの人間/LLM向けメモのため。Issue #524） |
```

### validate_frontmatter.py — 合成ページ追加フィールド（`derived_from` が存在するページ）（旧見出し）

```text
| `derived_from[].path` | 必須 | リポジトリルートからの相対パス。対象ファイルが実在すること（`translated_from` と同じく Issue #477 以前の `.wikicommit/wiki/` プレフィックス値も解決を試みる） |
```

### check_wikilinks.py — 使用場面（旧見出し）

```text
- `wikicommit-status` Skill：Step 3。引数なし・`--skip-type-mismatch` 付きで全ページに対して実行し、`ERROR:` 行だけを拾う（Issue #976。冒頭の「merge の blocking な 3 本は status が全ページに走らせる」節）
```

### check_wikilinks.py — コマンド（旧見出し）

```text
- `--skip-type-mismatch`: Type セグメント取り違えの ERROR（下記）を出さない（Issue #976）。その所見は `check_wanted_pages.py` が `TYPE_MISMATCH:` として報告しているため、両方を走らせる `wikicommit-status` が同じ所見を 2 回出さないためのフラグである。WARNING にも落とさない — 実在するページを「存在しない」と言うことになり、この分岐が避けようとしている誤りそのものになる。**落とすのは `<Type>/<slug>` がどの言語にも実在しない場合に限る** — それが `check_wanted_pages.py` が `TYPE_MISMATCH:` を出す条件であり、第 3 の言語や removed ページとしてだけ実在する場合は向こうが黙るので、ここの ERROR が唯一の報告になる。`status: removed` へのリンクの ERROR はフラグに関わらず出る。`wikicommit-merge` はこのフラグを渡さない（merge では引き続きブロックする）。重複の除去を SKILL.md の散文（メッセージの文言での除外）に委ねないのは、決定論的に判定できるものを指示に書くことになり（Issue #474）、文言が変わると黙って二重報告に戻るためである
```

### check_wikilinks.py — Type セグメントの取り違え（Issue #563）（旧見出し）

（見出しのみ）

### check_raw_html.py — 目的（旧見出し）

```text
Wiki ページ本文（frontmatter を除く）に生 HTML タグ（`<script>`・`<iframe>` 等）が混入していないかを検証する。CLAUDE.md・`docs/DesignDoc-publish.md` §8.6 が定める「画像・動画・YouTube の埋め込みは標準 Markdown 構文 `![alt](path-or-url)` のみで行う」という設計の下では、ページ本文が生 HTML タグを必要とする正当なユースケースは存在しない。一方 Quartz コアは `remarkRehype(..., { allowDangerousHtml: true })` を常時有効にしており、`enableInHtmlEmbed`（Obsidian Flavored Markdown プラグインのオプション）の値に関わらず生 HTML を常にそのまま HTML 出力へ通す。経路A（`docs/DesignDoc-pipeline.md` §6.3）では `review_status: pending` の LLM 生成ページが人間レビュー前に一旦 main マージ・公開されるため、ingest 元文書に埋め込まれた悪意ある HTML（間接プロンプトインジェクション等）や LLM のハルシネーションで生 `<script>`/`<iframe>` がページ本文に混入すると、レビュー前に公開サイトで実行されうる（Issue #377）。本スクリプトはこれを `wikicommit-merge` のブロッキング品質ゲートとして防ぐ。
```

### check_raw_html.py — 使用場面（旧見出し）

```text
- `wikicommit-status` Skill：Step 3。引数なしで全ページに対して実行し、`ERROR:` 行だけを拾う（Issue #976。冒頭の「merge の blocking な 3 本は status が全ページに走らせる」節）
```

### check_orphans.py — 使用場面（旧見出し）

```text
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。research guidance が渡されなかった場合のみ。Issue #672）。`ORPHAN:` 行のみを使い、`DUPLICATE:` 行は使わない — 両ページとも実在するので欠けているものが無く、新しいソースでは解消しないため。**このとき終了コード 1（重複あり）は失敗ではない**: `wikicommit-merge` が同じ終了コードをブロッキングとして扱うのは重複がマージを止めるからであり、俯瞰とは無関係
```

### check_wanted_pages.py — 使用場面（旧見出し）

```text
- `wikicommit-collect` Skill：Web候補探索のクエリ群のうち 1 パス分の検索語として（Issue #666。`WANTED:` 行のみを使い `TYPE_MISMATCH:` 行は使わない — 後者は実体が別 Type に在るので欠けているものが無く、必要なのは新しいソースではなくリンク 1 語の修正であるため）。取得失敗・`WANTED:` 0 件のときは黙って飛ばし、実行をブロックしない
- `wikicommit-collect` Skill：Step 3.5（俯瞰ステップ。Issue #672）。同じ `WANTED:` 行を、探索語ではなく「Wiki 自身が書きたいと表明した穴」として着眼点の根拠に読む。引数なし実行では上の探索語用途と同じ実行の中で両方が要るが、両者の間に `.wikicommit/entity/` へ書き込む手順は無いため、Step 3.5 が読んだ出力を Step 5 が再利用する（走査は 1 回でよい）
```

### check_wanted_pages.py — 処理フロー（旧見出し）

```text
3. 参照されているが実体なしの `Type/slug` のうち、**同じ slug が別の Type に実在するもの**を `TYPE_MISMATCH` として分離して報告する（Issue #563）。判定は `check_wikilinks.py` と同じ `_wikilink.py` の共有関数（`build_slug_type_index()` / `other_types_for_slug()`）で行うため、除外規則（`index.md`・`status: removed` ページを候補にしない）・探索範囲（言語を問わない）も同一になる
```

### read_policy.py — 既知の限界（旧見出し）

```text
**`.wikicommit/review-rules.md` も対象外**。あちらは `update: overwrite` で WikiCommit 自身の規律を持ち、記入例ではない（Issue #752）。
```

### match_existing_names.py — 決定事項（旧見出し）

```text
| 対象の言語 | `primary_lang` のみ。原文は `primary_lang` で書かれ、翻訳ページは `aliases` を持たない（`/wikicommit-translate` が写さない。Issue #1078） |
| LLM のコンテキスト | 既存ページの別名は渡さない。照合をスクリプトが行うので、既存ページ一覧は従来どおり「タイトル＋パス」で足りる |
```

### check_distribution_freshness.py — 目的（旧見出し）

```text
インストール済みの配布物が、`wikicommit-init` Skill が現在同梱しているテンプレートと一致しているかを報告する（Issue #712）。命名は `check_ingest_freshness.py` / `check_derivation_freshness.py` と同じ「記録されたものが今も最新か」の系譜だが、**副作用を持たない**（`check_ingest_freshness.py` と異なり管理ファイルを書き換えない）。
```

### check_distribution_freshness.py — 比較の仕方（`update` 列ごと）（旧見出し）

```text
| `.gitignore` | init が `--quartz` 時に Quartz セクションを追記する（**Issue #712 の実装中に実測で判明した。Issue 本文の分類表はこれをバイト比較側に置いていた**） |
```

### check_distribution_freshness.py — `quartz.config.yaml` の 2 つは、テンプレート比較では原理的に答えられない（Issue #950）（旧見出し）

（見出しのみ）

### check_distribution_freshness.py — ORPHAN は `overwrite` のツリーにのみ報告する（旧見出し）

```text
`copy_tree` は削除を行わないため、上流でリネームされたスクリプトは旧名のまま残る（Issue #583）。これを `ORPHAN:` として報告するが、**対象は `update: overwrite` のツリーに限る** — `.wikicommit/schema/` は `review` であり、テンプレートに無いファイルはユーザーが書いたカスタム型か Pass 2b が追加した型であって孤児ではない。ここを区別しないと `ORPHAN:` 行が正反対の 2 つを意味することになる。
```

### check_distribution_freshness.py — 劣化の仕方（旧見出し）

```text
| `wikicommit-init` が `.agents/skills/` にだけある（Codex 単独配置） | **未インストールとは扱わない**。Skill ツリーは `_skill_tree.py` の探索順（`.claude/skills` → `.agents/skills`）で引く（Issue #1021）。以前は `.claude/skills/` 固定だったため、Skill が在るのに別の場所にあることを「無い」と区別できず、上の行の劣化に黙って落ちていた |
| `wikicommit_version` が無い | `synced=unknown` と表示する。版は読者向けの情報であり比較を左右しないため、それ以外は通常どおり動く（Issue #577 より前に init されたリポジトリが該当） |
```

### search_index.py — 使用場面（旧見出し）

```text
- `wikicommit-synthesize` / `wikicommit-quiz` Skill：関連ページの収集（いずれも `--expand` 経由。Issue #581）
```

### search_index.py — `build` サブコマンド（旧見出し）

```text
2. 各ページから `title`・`lang`・`type`・`tags`・`review_status`・本文（frontmatter を除いた Markdown 全文）・`aliases`（Issue #1078。ソースの原語の表記が別名にしか残らない場合があり、翻訳先に無い言語ではそこが唯一の置き場になるため）を抽出する。frontmatter が YAML として解析できない、またはマッピング型でない場合はそのページ全体をインデックス対象から除外する（`status: removed` かどうか判定できないページを誤って検索可能にしないための安全側の挙動）
```

### check_schema_coverage.py — 使用場面（旧見出し）

```text
- `wikicommit-status` Skill：Step 6（定期ヘルスチェック。Issue #575）
```

### check_schema_coverage.py — 処理フロー（旧見出し）

```text
4. 型文字列は完全一致でのみ集計する。正規化・fuzzy matching は行わない（決定論的に保つための意図的な単純化。同じ概念が複数の型文字列に分かれたまま残りうるという既知の限界が伴う。Issue #285）
```

### check_schema_org_type.py — 目的（旧見出し）

```text
Schema.org の公式機械可読語彙ダンプ（`https://schema.org/version/latest/schemaorg-current-https.jsonld`）に対して、型・プロパティが実在するかを検証する。`wikicommit-generate` Pass 2b（Issue #315。その場での型提案・追加）と `wikicommit-schema-propose`（Issue #285。事後検出）が生成する型ファイル提案の、決定論的な裏付けとして使う。検証できるのは「型・プロパティが実在するか」という**存在の正しさ**のみで、「このWikiの内容に意味的にふさわしいか」という**適合性の判断**は LLM と人間レビューに委ねる。
```

### check_schema_org_type.py — 使用場面（旧見出し）

```text
- `wikicommit-generate` Skill：Pass 2b のプロンプトに Schema.org 型名の一覧をプリロードし（`--list-type-names`）、絞り込んだ候補の説明文だけを引くため（`--describe`）。Pass 2b の型・プロパティ実在検証にも使う（`--type`/`--property`）。Pass 3 が `properties:` の値を WikiLink 化すべきか判断する材料にも使う（`--show-range`。Issue #496）。Pass 2b が新規型の候補プロパティを選ぶ際、型が持ちうるプロパティ一覧を閲覧する材料にも使う（`--list-properties`。Issue #497）
```

### check_schema_org_type.py — コマンド（旧見出し）

```text
`--type` / `--list-type-names` / `--describe` / `--list-installed-hierarchy` のいずれか 1 つを指定する。すべて省略した場合はエラー（`--list-properties` 単独指定時は「`--list-properties` には `--type` の指定が必要です」という専用のエラーメッセージになる）。優先順位: `--list-type-names` が指定されていれば他の全フラグを無視してこのモード。次に `--describe`、次に `--list-installed-hierarchy` が指定されていれば同様に他の全フラグを無視してこのモード（Issue #798・#565）。次に `--type` + `--list-properties` が指定されていればこのモード（`--property`/`--show-range` は無視）。それ以外は `--type`（+ 任意で `--property`/`--show-range`）の既存の検証モード。
```

### check_schema_org_type.py — 保存先（Git管理下・Issue #319）（旧見出し）

（見出しのみ）

### check_schema_org_type.py — 処理フロー（`--list-installed-hierarchy`。Issue #565）（旧見出し）

（見出しのみ）

### check_schema_org_type.py — 処理フロー（`--list-type-names` / `--describe`）— 型の想起は 2 段階（Issue #798）（旧見出し）

（見出しのみ）

### rebuild_index.py — 使用場面（旧見出し）

```text
- `wikicommit-synthesize` Skill：合成ページを書き出した直後、そのページの Type ディレクトリ 1 件のみを引数に指定して呼び出す（Issue #547）。他 2 Skill が引数なしで全 Type ディレクトリを走査するのは「長いバッチの末尾で対象ディレクトリの追跡を取りこぼさないため」であり、1 ページしか書かず `<lang>`/`<Type>` が確定している本 Skill にはその理由が当てはまらない。引数指定にすることで、対話実行される本 Skill の副作用が該当ディレクトリの外へ広がらない
```

### rebuild_index.py — グループファイルを持つ型（Issue #1035）（旧見出し）

（見出しのみ）

### reconcile_ingest_status.py — 処理フロー（旧見出し）

```text
6. 1で構築したマップにこのhashが存在すれば、一致したページパスを重複排除・昇順ソートした上で、`status: generated`・`generated_pages`（一致したページパスのYAML flow-styleリスト）・`last_generated_at`（実行日）を書き戻す。`## Failure Reason` セクションが存在すれば削除する（Pass 4 手順7の `generated` 分岐と同じ扱い。Issue #408）
```

### reset_review_on_content_change.py — 目的（旧見出し）

```text
| **`wikicommit-generate` Pass 3 の `action: update`** | **`reviewed` を維持していた** |
| **`wikicommit-fix`** | **規則が無く、触れていなかった** |
```

### reset_review_on_content_change.py — 内容フィールドと bookkeeping フィールドの線引き（旧見出し）

```text
`expires_at` は内容側に残す — Pass 4 がこれを他の主張と同様にソースとの照合対象にしている（Issue #279）以上、検証対象の主張である。`translator_notes`（`wikicommit-fix` Step 5 が追記する翻訳固有の申し送り）は性質上 bookkeeping 寄りに見えるが、同じ Edit で本文も変わっているのが通常なので実質的な差が出ず、ignore リストを増やさない側に倒してある。
```

### reset_review_on_content_change.py — プローズの手順にしない理由（旧見出し）

```text
完全に決定論的に判定できる操作を SKILL.md の instruction として書くと、非決定論的な失敗モードを持ち込む（Issue #474）。しかも本件は「人間のレビューが要るか否か」を左右する判定であり、再生成モードの valve が同じ理由で比較を意味的同一性ではなくテキスト一致にしているのと同じ配慮が要る。
```

### record_review.py — 目的（旧見出し）

```text
**判定は LLM が下し、ファイル手術はスクリプトが行う**（Issue #474）。`set_frontmatter_field.py` / `reset_review_on_content_change.py` と同じ形だが、こちらは**既存ファイルを一切読まず・書き換えず、新規作成のみ**を行う。
```

### record_review.py — 使用場面（旧見出し）

```text
- `wikicommit-translate` Step 4 item 5：PASS・retry 上限超過の両方（`stage: translate-check`。Issue #1031）
- `.github/workflows/review-issue-close-sync.yml`：`review_status` を書き換えるのと同じコミットで。Close した本人の最新コメントを `--note-file` で渡し、記録の散文本文にする（Issue #762。選別と injection 上の扱いは `docs/DesignDoc-data.md` §4.8 参照）
```

### record_review.py — 処理フロー（旧見出し）

```text
3. `issues[]` を `FINDING_FIELDS`（`round` / `type` / `claim` / `source_file` / `source_lines` / `instruction` / `page_at_fault`）に射影する。**`source_quote` は呼び出し側が渡してきても落ちる**。`round` が無い場合は 1 を補う。`source_file` の**空文字列は残す** — `wikicommit-synthesize` の `MISSING_SOURCE` は定義上どの grounding ページも当てはまらないため意図的に空にする（Issue #674）ので、キーごと落とすと「呼び出し側が入れ忘れた」と区別できなくなる
5. `reviewed_sources` を、ページの `sources[]`（view ページは `derived_from`）から取る。`--sources-from` が指定されていればそちらを優先する（ページが存在しない `discarded` 用）。翻訳ページは `sources` を持たないので `{path: translated_from, source_commit}` の 1 要素を組み立てる（`page_evidence_entries()`。`check_review_coverage.py` の失効判定も同じ関数を import して使い、記録側と読み取り側で「このページの証拠」の定義が割れないようにしている）。`--stage translate-check --result discarded` のときは読まず空にする — ディスクにあるのは古い翻訳であり、その `source_commit` は今回照合した原文の版ではない（Issue #1031）
```

### record_review.py — `page_at_fault` は検証も消費もされていない（Issue #987）（旧見出し）

（見出しのみ）

### check_review_coverage.py — 使用場面（旧見出し）

```text
- `wikicommit-merge` Skill：Step 9（`--discarded-reason`。生成失敗トラッキング Issue の理由欄。Issue #969）
```

### check_review_coverage.py — `--discarded-reason` — 破棄されたページの理由を引く（Issue #969）（旧見出し）

```text
| `round` | **記録が 2 ラウンド以上を持つときだけ印字する** | 破棄された記録は全ラウンドをフラットに持つ（`docs/DesignDoc-data.md` §4.8。Issue #571 の実測では 3 回とも別の欠陥だった）ため、番号が無いと 3 回の試行が 3 つの同時並行の問題に読める。1 ラウンドしか無い通常の記録では出さない |
**`instruction` を verbatim にする理由**: この文は再生成プロンプトに渡すために書かれたものであって読者向けではなく、命令形で書かれている（`docs/DesignDoc-skills.md` §11.8 の「読み手が誰か」で判定する軸に当たる）。それでも要約しないのは、要約とは**この step が下していない判断を書き直すこと**であり、しかもこの記録の価値はその具体性そのものだからである。記録ツリーは人が読める形で設計されており（Issue #750）、この文はページが存在しない理由について現存する最も具体的な記述である。
**ページを 1 件も渡さない呼び出しは正常であり、`pages=0` と答える。** Step 9 の 2 つ目の対象（Pass 1 で失敗した `status: failed` のソース。Issue #910）は `failed_pages` が空なので、呼び出し側の展開はフラグだけを残す — そこで argparse の usage エラー（exit 2）を返すと、常に 0 という契約が破れるうえ、呼び出し側からは「この版にこのモードが無い」と区別が付かない。
```

### check_review_coverage.py — `human_notes` — 経路 A の Close に一言が来たかを数える（Issue #952）（旧見出し）

```text
**`kind: ai` の本文は数えない。** あちらは Pass 4 の非ブロッキングな観察（Issue #834）であって人の読了の痕跡ではなく、混ぜると 1 つの数が 2 つの別のものを指す。
```

### check_review_coverage.py — 既知の限界（旧見出し）

```text
**`human_notes` が答えないもの（Issue #952）**:
```

### record_run.py — 目的（旧見出し）

```text
| 問い | 既存の層が答えられない理由 |
| 実行は完走したか | 途中で死ぬと一部が `pending`・一部が `generated` で止まり、Issue #567 が扱った「まだ順番が来ていない滞留」と**見え方が同じ**。ガード C（Issue #574）・`rules_version` 不一致（Issue #752）はファイルを 1 つも変えずに止まるため git に痕跡がゼロ |
```

### record_run.py — git で追跡しない（Issue #750 とは逆）（旧見出し）

```text
| Issue #750 が追跡された理由 | 実行記録は |
| 公開ページの表示に使う（Issue #751） | 何も表示しない。`convert_wikilinks.py` はこのツリーを歩かない |
```

### record_run.py — 記録のフォーマット（`.wikicommit/run/<YYYYMMDD>-<HHMMSS>-<skill>.md`）（旧見出し）

```text
passes:                                  # Issue #797。空リストなら「打点なし」
```

### record_run.py — `checkpoint` — 実行の**どこまで**を残す（Issue #797）（旧見出し）

（見出しのみ）

### record_run.py — read-modify-write のコスト（実測）（旧見出し）

（見出しのみ）

### record_run.py — 既知の限界: compaction は分割前の Pass 2 以降の打点指示を落としうる（旧見出し）

（見出しのみ）

### record_run.py — 記録しないもの（旧見出し）

```text
| コスト・トークン数 | その実行を回した運用者自身の契約・課金の事情であり、この記録の対象である実行の**外形**ではない（Issue #784 と同じカテゴリ） |
```

### driver.py — 目的（旧見出し）

```text
多段の Skill の**工程の順序**をエージェントの記憶からスクリプトへ移す（Issue #1085。設計の全体と、捏造に耐えないことを受け入れる理由は `docs/DesignDoc-skills.md` §11.0「多段の Skill の進行はドライバーが持つ — 判断はエージェントが持つ」）。エージェントは `next` が返す 1 工程だけを行い、`done` で報告する。ドライバーはその工程の確認スクリプトでディスクを見て、通れば記録して次を返し、通らなければ同じ工程を返す。
```

### check_run_records.py — 目的（旧見出し）

```text
| `MISSING_PASS:` | **正常に完走したのに打点の無いパスがある**実行はどれか（Issue #797） |
```

### check_retracted_sources.py — 目的（旧見出し）

```text
「報告に留める」ことは意図的な決定である（Issue #737）:
```

### check_retracted_sources.py — 処理フロー（旧見出し）

```text
1. `.wikicommit/source/**/*.md` を走査し、`status: retracted` な管理ファイルの `source.path` / `source.url` を「取り下げられた識別子 → 管理ファイルのパス」の対応表にする。**識別子をキーにするのは、それが `add_source.py` の同一性判定（Issue #572 / #573）が使うキーであり、かつページの `sources[]` エントリが持つ値そのものだからである** — 導出された管理ファイル名をキーにすると、旧命名規則で作られた管理ファイル（自動移行しない）を取りこぼす
```

### check_retracted_sources.py — `--list` — 参照側 2 経路のためのガード（Issue #928）（旧見出し）

（見出しのみ）

### check_property_wikilink_reinforcement.py — 出力フォーマット（旧見出し）

```text
検査対象から外れた `granularity` 箇条書きがある場合（Issue #649。`UNREINFORCED:` の直前に出るため、誤検出であることがその場で読み取れる）:
```

### check_recurring_characters.py — 既知の限界（旧見出し）

```text
- **再登場の計数はプレーンテキストで書かれた作品しか数えない**。ページがまだ無い人物について、ある作品が既に `[[Person/slug]]` と書いている場合、その作品は閾値に算入されない（リンク 1 件 + プレーンテキスト 1 件では何も報告されない）。両者を突き合わせるにはプレーンテキストの名前から slug を導く必要があるが、slug の決定規則（英語識別子・種別に応じた英訳／原綴り／ローマ字。Issue #193）は逆算できるものではないため行わない。宙に浮いたリンク自体は `check_wanted_pages.py` の所見であり、`Person` ページが作られた時点でプレーンテキスト側は `check_unlinked_entity_mentions.py` が拾う
```

### check_unlinked_entity_mentions.py — 目的（旧見出し）

```text
`check_wanted_pages.py` の鏡像。あちらが「リンクはあるが実体がない」を検出するのに対し、本スクリプトは**「実体はあるがリンクされていない」**を検出する（Issue #561）。
```

### check_unlinked_entity_mentions.py — 処理フロー（旧見出し）

```text
2. 全ページの frontmatter を読み（`status: removed` は対象外）、正規化した `title`・`aliases` の各値・`slug` から `(型, slug)` への索引を作る。`slug` も索引に含めるのは、英語で書かれた Wiki では値と slug が一致しうるため（他言語では値は Wiki の言語で書かれ、slug は言語中立な英語識別子であるため〈Issue #193〉一致しないのが普通）
```

### check_installed_type_usage.py — 目的（旧見出し）

```text
`check_schema_coverage.py` の対。あちらが「使われている `type:` にスキーマファイルが無い」を検出するのに対し、本スクリプトは**「スキーマファイルが在るのにページが無い」**を検出する（Issue #565）。
| `UNUSED` | 型ファイルがあるのにページが 0 件 | 型の判断自体が誤っていたか、生成がその型に手を伸ばしていないか。`provenance: default` の型は対象外 — Wiki の主題に関わらず一律配布されるため、0 件であること自体に情報が無い。`provenance` が**無い**ファイルはその機能追加（Issue #519）より前に作られたことを意味するため、`config.yml` の `schema.base_types` が代わりの判断材料になる（そうしないと、それ以前に初期化された Wiki は配布された基本型を丸ごと報告してしまう） |
```

### check_schema_files.py — 目的（旧見出し）

```text
| 出所 | `provenance` | 従来の検証 |
| 配布テンプレート | `default` | ⭕ `tests/test_schema_template_*.py` 4 本 |
```

### check_schema_files.py — 所見の種類（旧見出し）

```text
| `BAD_PROPERTY` | `properties:` のキーが Schema.org 語彙に実在しない、またはその型（祖先型を含む）の `domainIncludes` に属さない。**ページ側の `properties:` には `validate_frontmatter.py` が同じ検証をしている**（Issue #495）一方、そのページが生成された元のテンプレートに対しては一度も走っていなかった |
| `MAPPING_BULLET` | `granularity` の箇条書きが、クォートされていない `": "` によってマッピングに化けている（Issue #649）。文字列で絞り込む全消費者がその箇条書きを飛ばす |
| `TRUNCATED_BULLET` | `granularity` の生の行にクォートされていない、空白を伴う `#` があり、YAML のコメントとして行の残りが落ちている。**これは他の何も気づけない唯一の形である**（Issue #649 が明記） — 値は文字列のままなので一見正常で、欠けた半分は単に無い |
| `NO_BOUNDARY` | `Boundary` で始まる箇条書きが 1 本も無い（`granularity` が空の場合は対象外 — 規則が 0 本であることと、規則があるのに境界が無いことは別である）。**マッピングに化けた箇条書きはそのキーを見る** — `Boundary with X: ...` は Issue #550 が em ダッシュに置き換える前に 3 つの配布テンプレートが持っていた形であり、`MAPPING_BULLET` に加えて「`Boundary` で始まる箇条書きが無い」と述べれば、そこに在るものを無いと言うことになる |
| `BAD_PROVENANCE` | `provenance` が 7 値（Issue #519）のいずれでもない。**欠如は報告しない**（下記） |
| `TYPE_PATH_MISMATCH` | `type:` がファイルパスから導かれる型名と食い違う。型を決めるのはパスの導出だけ（§5.1）なので、食い違えばそのファイルは**何も定義していない**。ページ側には Issue #545 の同じ検証がある |
| `NO_RATIONALE` | カスタム型に `wikicommit.rationale` が無い（Issue #548）。語彙の外にある型では、その散文が「なぜこの型が存在するか」の唯一の恒久的な記録である |
```

### check_groups.py — 目的（旧見出し）

```text
`.wikicommit/groups/<Type>.yml`（`docs/DesignDoc-data.md` §4.5.3）を読み、未分類のページ・実在しない slug・読めないファイルを報告する（Issue #1035）。読み込みと検証は `_groups.py` にあり、`rebuild_index.py` と `convert_wikilinks.py` も同じものを import する。
```

### check_groups.py — コマンド（旧見出し）

```text
- **引数なし**（`/wikicommit-status` Step 10）: グループファイルごとに `TYPE:` を 1 行、読めないファイルには `ERROR:` を出す。**グループファイルを持たない型は報告しない** — 全型が常に点灯する行は読まれなくなる（Issue #562）
```
