# WikiCommit — 公開・配信層・検索・MCP

> **対応DesignDoc**: 元 §8・§9・§10  
> §8（公開・配信層）は Phase 2 で Quartz v5 deploy と review_status バナーを実装。§9（検索）の全文検索（FTS5 trigram）は Phase 3（`wikicommit-ask` Skill が MCP を介さず直接クエリ）、§10（MCP）は Phase 5 以降（ホスト型・複数リポジトリ横断検索）。ベクトル検索（LanceDB + 多言語埋め込みモデル）は依存の重さを理由に Phase 3 では見送り、将来 Phase での再検討課題とした（§9.2 参照）。Phase 3 で計画していた自己ホスト MCP サーバーは撤回した — 単一リポジトリの検索・参照は Skills（`wikicommit-ask` / `wikicommit-search`）が代替できるため。Phase 4 は Tauri デスクトップのコンパニオンアプリがローカル git を直接操作する構成のため、ホスト型 MCP は Commons のクロスリポジトリ検索が必要になる Phase 5 まで導入しない。

---

## 8. 公開・配信層

### 8.1 SSG 選択

**Quartz v5 を採用**。`[[タイプ/ファイル名]]` 形式の WikiLink をネイティブサポートする唯一の主要 SSG で、GitHub Pages デプロイ用ワークフローが公式付属している。全文検索（FlexSearch ベース）・グラフビューも標準搭載。

> **実装時の補足**: Quartz v5 は npm パッケージとして配布されていない。本体（`jackyzha0/quartz`）を git submodule として取り込み、設定ファイルは TypeScript ではなく YAML（`quartz.config.yaml`。`configuration`・`plugins`・`layout` の3セクション）で記述する。詳細は Issue #41（p2-010）の実装（PR #55）を参照。

<!-- -->

> **ローカルプレビュー**: `/wikicommit-init --quartz` が生成する `package.json` には `npm run build`（ビルドのみ）・`npm run preview`（ビルド後にローカルサーバーを起動してブラウザで確認）が配線済み。GitHub Pages へのデプロイを待たずに手元で見た目を確認できる（Issue #240）。

<!-- -->

> **公開URLの案内（README.md への追記提案、Issue #282）**: `/wikicommit-init --quartz --quartz-pages` は GitHub Pages（Source: GitHub Actions）を自動有効化するが、有効化後の URL をリポジトリのどこにも書き残さないままだと、README.md やリポジトリトップから公開Wikiへ辿れない。そのため次ステップ案内に `gh api repos/{owner}/{repo}/pages` の `html_url` を使った README.md への追記例（コピペ用の Markdown 片）を追加した。README.md 自体の自動編集は行わない（既存リポジトリに後付けする場合、README.md は既にユーザー独自の構成を持つ可能性が高く、中身を知らないファイルへの自動挿入は既存の見出し構成を壊すリスクがあるため。`.claude/skills/wikicommit-init/SKILL.md` の Notes 参照）。
>
> **`--quartz` と `--quartz-pages` の分離（Issue #335）**: 当初 `--quartz` 単体が「ローカルビルド・プレビュー」と「GitHub Pages への自動公開（`deploy.yml` の生成 + Pages 自動有効化）」を1つのフラグに束ねていたため、「Obsidian等でローカルの `.wikicommit/entity/` を読む・Quartzのビルド結果を手元で確認したいだけで、リポジトリ外への公開はまだしたくない」という運用者が、`wikicommit-init` の時点で意図せず GitHub Pages を有効化させられてしまう問題があった（`Paperwork-Navigator-wikicommit-pilot` パイロットでの指摘）。`--quartz`（ローカルビルド一式のみ生成）と `--quartz-pages`（`--quartz` 指定時のみ有効。`deploy.yml` 生成 + Pages 自動有効化を追加）に分割し、`wikicommit-init` の Prerequisites も2段階の Y/n プロンプトに変更した。`/wikicommit-merge` 自体はこの分割以前から Quartz/Pages に一切依存しておらず（`.wikicommit/entity/` の変更検出・品質チェック・Git/PR操作のみで完結）、変更不要であることを確認済み。
>
> **`syntax-highlighting` プラグインをデフォルトテンプレートから除外（Issue #449）**: `ai-driven-dev-wiki` を Organization へ移管し public 化する検証ドライラン中、`deploy.yml` の Quartz ビルドが `syntax-highlighting` プラグインのビルド失敗で止まる問題が判明した。原因の切り分けは Quartz 本体（`jackyzha0/quartz` の `plugin-git-handlers.js`）がビルド失敗時のエラー内容（メッセージ・stderr等）を握り潰し `"build failed"` とだけ表示するため CI ログからは特定できなかったが、実地調査で以下が判明した: (1) `syntax-highlighting` は依存する `rehype-pretty-code`（Shikiベース）が全言語の文法定義をバンドルに含めるため出力が `dist/index.js` 10.3MB・sourcemap 14MB と他プラグイン（数十KB程度）より突出して大きい、(2) ローカルの潤沢なリソース環境（16コア・15GB RAM）では全48プラグインのビルドが成功する一方、GitHub Actions 標準ランナー（2コア・7GB程度）でのみ失敗が再現する — `runParallel`（Quartz本体の bounded concurrency 実装）がこの1プラグインだけ突出して重いビルドを他47プラグインと同時に走らせることによるリソース不足が濃厚（確定的な証明には至らず）、(3) `quartz.config.yaml` の `enabled: false` はビルド自体をスキップしない（プラグインインストーラは `enabled` に関わらず列挙された全プラグインをクローン・ビルドする。適用段階でのみ `enabled` が効く）ためエントリ自体の削除が必要、(4) 提供機能（コードブロックのシンタックスハイライト・コピーボタン・トークン単位CSSクラス付与の3点のみ。コードブロック自体の描画は `obsidian-flavored-markdown`/`github-flavored-markdown` 側が独立して担当）に対し実際の利用頻度が低い（`ai-driven-dev-wiki` パイロット48ページ中コードフェンスを含むページは2件のみ）。上流（`quartz-community/syntax-highlighting` のバンドルサイズ・Quartz本体のエラー握り潰し）の修正待ちにはせず、即座に全パイロットの `deploy.yml` 失敗を解消できることを優先し、`.claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml` から `syntax-highlighting` エントリ自体を削除してデフォルト無効化した。**再検討の条件**: コード例中心のコンテンツタイプ（HowTo等）を多用するパイロットが増え、シンタックスハイライト・コピーボタンの需要が実際に顕在化した場合。その際は上流の状況（バンドルサイズ・エラー握り潰しの改善有無）を改めて確認した上で再導入を検討する。この対応は本 Issue のドライラン以前から存在するテンプレートにのみ適用され、既存に `--quartz` 済みのパイロットリポジトリ（`--no-overwrite` のため `/wikicommit-init` 再実行では自動反映されない）には別途手動での周知・追従が必要。

### 8.2 WikiLink の解決方法

`[[Type/slug]]` を標準 Markdown リンクに展開してから SSG に渡す。

```
ビルド前変換スクリプト（pre-build step）
  ↓
[[Person/yamada-taro]] → ../Person/yamada-taro.md（別 Type ディレクトリからの相対パス）
                         または ./yamada-taro.md（同 Type ディレクトリ内からの相対パス）
  ↓
SSG（Quartz v5）に渡す
```

ファイル名は言語中立の英語識別子で統一する（例: `auth.md`、`yamada-taro.md`）。タイトルや本文は各言語で記述する。

> **未解決 WikiLink の表示仕様（Issue #431）**: `check_wikilinks.py` は「参照先ページがどの言語にも存在しない」ケースを ERROR ではなく WARNING として扱う（Issue #340）ため、参照先が解決できない `[[Type/slug]]` を含んだページも `wikicommit-merge` を通過しうる。この場合、ビルド前変換スクリプト（`convert_wikilinks.py`）は当該 WikiLink をリンクにはせず、ブラケットを除いたプレーンテキスト `Type/slug` として出力する（`lang`/`current_type` が特定できない場合、および同言語・`primary_lang` いずれのターゲットファイルも存在しない場合の両方でこの挙動になる）。生の `[[Type/slug]]` というダブルブラケット構文がそのまま読者に表示されることはない。この変換は `unresolved_links` カウント・`SUMMARY:` 行の集計には影響しない（集計は変換前の判定結果に基づくため）。

### 8.3 JSON-LD 埋め込み

Quartz プラグインとしてビルド時に実行。ページの `properties:` ブロック（Issue #495 — 型固有の Schema.org プロパティが `title`/`tags`/`sameAs`/`wikidata` 等のトップレベル共通フィールドと分離してネストされている）の値を、型ごとに定めたマッピングでそのまま JSON-LD のキーへ流し込む（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-jsonld/src/index.tsx` の `typeStr` 分岐を参照。マッピング自体は型ごとに決め打ちで、スキーマファイルから動的に読み取るわけではない）。

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "山田太郎",
  "description": "CompanyA のシニアエンジニア...",
  "affiliation": { "@type": "Organization", "name": "CompanyA" },
  "jobTitle": "シニアエンジニア"
}
</script>
```

本文の散文は JSON-LD に含めない。`description` フィールドには frontmatter の情報のみ使用する。

### 8.4 review_status の可視化

```
review_status: pending
┌─────────────────────────────────────────────────────────────────────┐
│ ⚠️ LLM が自動生成したページです                                      │
│ 内容に誤りがある可能性があります。                                    │
│ 生成日: 2026-06-17  生成モデル: claude-sonnet-4-6                   │
│ 出典と照合: 2026-09-05  照合モデル: claude-opus-5[1m]                │
│ [このページのレビュー状況を見る]      [気づいた点を報告する]（GitHub アカウントが必要）│
└─────────────────────────────────────────────────────────────────────┘

review_status: reviewed（Issue #739。同じ見出し・同じ本文・同じ生成情報のまま、行が 1 つ増える）
┌─────────────────────────────────────────────────────────────────────┐
│ ⚠️ LLM が自動生成したページです                                      │
│ 内容に誤りがある可能性があります。                                    │
│ 生成日: 2026-06-17  生成モデル: claude-sonnet-4-6                   │
│ 出典と照合: 2026-09-05  照合モデル: claude-opus-5[1m]                │
│ 読んだ人: octocat                                                    │
│ [気づいた点を報告する]（GitHub アカウントが必要）                       │
└─────────────────────────────────────────────────────────────────────┘

review_status: reviewed（reviewed_by が無い場合。route B のページなど）
┌─────────────────────────────────────────────────────────────────────┐
│ ⚠️ LLM が自動生成したページです                                      │
│ 内容に誤りがある可能性があります。                                    │
│ 生成日: 2026-06-17  生成モデル: claude-sonnet-4-6                   │
│ 出典と照合: 2026-09-05  照合モデル: claude-opus-5[1m]                │
│ 人が読みました                                                        │
│ [気づいた点を報告する]（GitHub アカウントが必要）                       │
└─────────────────────────────────────────────────────────────────────┘
```

> **レビュー済みページも LLM 生成であることを表示する（Issue #739）**: かつてバナーは `review_status` で 2 つの分岐に分かれており、`reviewed` 側が返すのはレビュー者名（あれば）と報告リンクだけだった。`generated_at` も `generated_by` も出ず、**誰かが追跡 Issue を Close した瞬間に、そのページが LLM 生成であるという事実が表示から消えていた**。
>
> **これは表示の好みではなく事実の欠落である**。人が読んでもページが LLM 生成でなくなるわけではない — `review-issue-close-sync.yml` が書き換えるのは `review_status` と `reviewed_by` だけで、`generated_by` / `generated_at` は恒久的なフィールドである。事実は変わらないのに事実の表示だけが消えていた。副作用として **`reviewed` が過大表明になっていた**: 警告が消える設計は「人が見たことでこの警告は解消された」と読めるが、`reviewed` が実際に意味するのは `docs/DesignDoc-pipeline.md` §6.3 の遷移表に書かれたものだけであり（Issue #723）、そこに「LLM 生成であることが問題でなくなった」に相当する保証は無い（Issue #722 は網羅性が評価対象でないことも明文化している）。
>
> **分岐を 2 つ持たず、1 つのバナーが状態に応じて情報を足す形にした**。LLM 生成である旨（翻訳ページでは `translated_at` / `translated_by`）は `review_status` に関わらず表示し、`reviewed` は警告を**取り除く**のではなく**行を 1 つ足す**（誰が読んだか）。報告リンクは従来どおり常時表示（Issue #245。変更なし）。この形にすると「レビューとは情報が 1 つ増えることであって、警告が取り消されることではない」という関係が、マークアップそのものに現れる。
>
> **当初は `⚠️` を pending だけに残し、見出しを状態で切り替えていた**（当時の文言は `reviewed` 側が「このページは人が確認済みです」→ Issue #740 で「このページは人が読みました」、pending 側が「このページはまだ誰も読んでいません」）。**Issue #774 がこの 2 つを取り消した** — 下記コールアウト参照。区別の手がかりも 3 つ（修飾クラス・アイコン・見出し）から 2 つ（修飾クラス・読了行の有無）に減っている。区別できないと読者は「人が読んだかどうか」を見分けられず、`reviewed` を表示する意味自体が消える、という要件は変わらない。
>
> **見出しを状態によらず真である事実に固定した（Issue #774）**: pending 側の見出し「このページはまだ誰も読んでいません」は、**それを読んでいる人の前で偽になる**。実際に述べていたのは「書き込み権限を持つ誰かの読了が記録されていない」であり、読者の大半はその区別を持っていない。Issue #740 が `review_status` を「主張」から「出来事」へ移したのは正しいが、その出来事を**否定形で読者に向けて宣言する**ところまでは要求していなかった。
>
> **原因は見出しが入れ替えだったことにある**。Issue #739 が掲げた原則は「レビューは行を**足す**のであって警告を取り消すのではない」だが、見出しに関してはいまも入れ替え（`isPending ? t.title : t.titleReviewed`）だった。入れ替えである限り pending 側は何かを言わなければならず、言えることは否定形しか無い。現在の見出しは両状態で真である事実（`LLM が自動生成したページです`）を述べ、`reviewed` はそこに行を足す。**状態は「行があるかどうか」で伝わり**、しかもそちらのほうが正確である（読者が「記録が無い」を「誰も読んでいない」と読まされずに済む）。
>
> **Issue #751 が先に入っていることが前提である**。機械側の照合が表示されるようになったので、pending から読了の主張を落としても「このページには何も行われていない」とは読まれない。
>
> **見出しと本文を「事実」と「含意」に分けた**（Issue #774 の検討事項 4）。見出しが `LLM が自動生成したページです`、本文が `内容に誤りがある可能性があります。` で、それ以前は両者がほぼ同じことを言っていた。
>
> **`⚠️` は両状態で出す**（同 検討事項 3）。従来この アイコンは「まだ誰も読んでいない」に紐づいており、その主張を落とすと指す先は「LLM 生成である」になる — それは `reviewed` でも真である。pending 限定のまま残すと「レビューで警告が取り消される」という、Issue #739 が否定した読みを再びマークアップに書くことになる。
>
> **`reviewed_by` が無いページには名前なしの行を出す**（同 検討事項 2。従来の判断を反転させた）。以前は「『人が読んだ』という事実は見出しが既に運んでいる」ため行が不要だったが、その見出しが無くなった。route B のページ（`/wikicommit-review` はローカル実行で GitHub login を得られない）と Issue #663 より前にレビューされたページには名前が無く、**行を出さないとこれらが pending と見分けられなくなる**。名前がある場合は `readBy`（`<login> が読み、明らかな問題は見つかりませんでした` / `Read by <login> — nothing obviously wrong stood out`。Issue #800 以前は `読んだ人: <login>` という素のラベルだった）が「人が読んだこと」と「誰が」の両方を述べるため、2 行に分けると「読んだ」が重複する。名前が無い場合の `readByAPerson` は同じ文を名前なしで述べる。Issue #663 の「レビュアーの欠落は正常な状態であり、空ラベルも `unknown` プレースホルダーも出さない」という扱いは維持される — 出すのは名前の代わりではなく、事実そのものの行である。
>
> **`reviewed` の行は残した**（同 検討事項 1）。消すと `reviewed_by` の表示先が無くなり Issue #663 を巻き戻すことになる。
>
> **この表示を「バッジ」と呼ぶのをやめた**（同 3 節）。散文はこれを一貫して「バッジ」と呼んでいたが、**どこにも定義が無く、しかも語が実物より強い** — 実物は三項演算子 1 つと条件付きの `<p>` 1 つであり、独立した UI 部品ですらない。この Issue が触った箇所（`WikiCommitBanner.tsx` のコメントと `wikicommit-generate/SKILL.md` の 2 箇所）は実物の名前で書き直した。**リポジトリ全体の一括置換はしない** — 登録済み Issue と `CHANGELOG.md` の既発表エントリは「その時点で何をどう考えたか」の記録であり、後から用語を書き換えると記録でなくなる（Issue #583 が ingest の語について引いたのと同じ線）。
>
> **既存の公開済みリポジトリは再ビルドで自動的に新しい表示になる**（`content/` はビルドのたび書き直される）。`review_status` の値・追跡 Issue・`review-issue-close-sync.yml` は変更していない。
>
> **判定は `review_status` ではなく生成スタンプの有無で行う**。これが実装上の要点である — `review_status: reviewed` は、**ビルド生成のナビゲーションページでバナーを黙らせるためのスタンプでもある**（下記 Issue #580 のコールアウト）。`reviewed` を条件に生成情報を出すと、root `content/index.md`・`content/sources/` 配下・Type 別インデックスに「LLM が自動生成しました。生成日: 不明」が出ることになり、Issue #580 が直した問題を作り直してしまう。それらのページは生成スタンプを 1 つも持たないため、スタンプの有無を条件にすれば従来どおりのマークアップのまま残る。**見るスタンプは、そのページで実際に描画する 1 組に限る** — 翻訳ページ（`translated_from` あり）なら `translated_at` / `translated_by`、それ以外なら `generated_at` / `generated_by`。4 つの和集合で判定すると、`generated_*` だけを持つ翻訳ページがバナーを開いた上で「翻訳日: 不明 翻訳モデル: 不明」を出す — この判定がまさに避けようとしている「中身の無い生成情報」そのものになる。**`pending` はこの判定を免除する**（従来どおり `unknown` プレースホルダーを出す） — `pending` を書くのは `wikicommit-generate` / `-translate` / `-synthesize` だけなので、そのページは定義上生成を経ており、スタンプの欠落は埋めるべき穴である（Issue #663 が `reviewed_by` について記録したのと同じ非対称）。
>
> **既存ページへの遡及は要らない**。バナーは frontmatter を読んでビルド時に描画するため、次のデプロイで全ページに反映される。ページ側の変更は 1 件も無い。生成スタンプを持たない古いレビュー済みページには生成情報が出ないが、これは正直な結果である（このリポジトリはそのページが何で書かれたかを知らない）。**レンダリング結果の目視確認は行っていない**（このリポジトリには Quartz 本体が無い。Issue #81）— 検証は `WikiCommitBanner.test.tsx` の描画結果に対するアサーションによる。

<!-- -->

> **AI レビューを通過した事実を表示する — ただし publish 時にのみ注入する（Issue #751）**: Pass 4 は生成した全ページに 8 種類の検査を掛けており（証拠拘束〈#442〉・個別事実の逐一検証と命名 vs 発明〈#451〉・孫引き出典〈#473〉・帰属の取り違え〈#429〉・ソース間の食い違いと 1 ホップのページ間矛盾〈#566〉）、Issue #750 以降その判定は `.wikicommit/review/` に記録される。**しかし読者にはそれが一切見えていなかった** — 上の #739 が直した「`reviewed` は過大表明である」の**逆向きの誤差**であり、機械が実際にやっていることのほうが過小表明されていた。
>
> **ページの frontmatter にコピーせず、`convert_wikilinks.py` が publish 時に `content/` 側だけへ注入する**（`ai_review_model` / `ai_review_at`）。決め手はコピーが古くなることである — `/wikicommit-fix` がページを書き換えても、ページに書かれたコピーはそれを知らない。Issue #750 が `target_commit` ではなく内容ハッシュ（`page_content_hash`）を選んだ効きがここで出て、publish 時に「この判定は今公開しようとしているページにまだ有効か」を決定論的に判定できる。**コピーが古くなる**という失敗は Issue #705（`reviewed_by` が前のレビュアーの名前を残す）で既に一度踏んでいる。`convert_wikilinks.py` は `content/` 側にだけ `review_status: reviewed` をスタンプする形を既に持っており（Issue #580）、記録ツリーを 2 本目の入力にするのはその反復である（publish 時にだけ形を変える前例としては Issue #576 の `custom/` フラット化もある）。**副次的に、`.wikicommit/entity/` のページが 1 文字も変わらないため `validate_frontmatter.py` に新しい検証ルールが 1 つも要らない。**
>
> **判定が無い・最新の判定が `pass` でない・失効している・記録が読めない、の 4 つはいずれも「何も出さない」に落とす**。失効の判定は `check_review_coverage.py` の `stale_reasons()` をそのまま借りる — ページ本文の書き換えだけでなく、判定の根拠だったソースが変わった・ページから外れた場合も含む（`sources` は内容ハッシュが無視する bookkeeping フィールドであるため、ハッシュ比較だけでは捉えられない）。ここで片方だけを実装すると、まさにこの機能が避けようとしている「`/wikicommit-status` と食い違うバナー」になる。`pass` 以外を出さないのは、`wikicommit-review` が事実確認で問題を見つけたとき `--result fail` を**ディスク上に残るページ**に対して記録するためで、それを「出典と照合済み」として出すと、最新の照合に落ちたページにだけ通過のバッジが付く。ページ側からこれらは区別できず、区別する必要も無い（いずれも従来どおりの表示になる。新旧混在を許容する既存方針）。記録はさかのぼって作れない（Issue #750）ため、この機能追加より前に生成されたページの空白は恒久的である。
>
> **文言は「何を照合したか」を述べ、「検証済み」と読める形にしない**。Pass 4 が見ているのはソース忠実性だけであり、網羅性は明示的に対象外（Issue #722）、実在の人物・組織への害と読者自身の知識との食い違いはどの層も見ていない（Issue #723）。これは Issue #740 が `reviewed` について直そうとしている罠とまったく同じ形であり、**同じ Issue 群の中で同じ過ちを逆向きに繰り返してはならない**。
>
> **指摘件数はページ単位に出さない**。「指摘 2 件」と出ると読者には品質の悪いページに見えるが、実際は指摘を受けて直っているので意味が逆になる。件数はサイト単位（§8.8.1 の俯瞰ページ）に寄せた。
>
> **公開サイトでの目視確認は未実施**（このリポジトリに Quartz 本体が無いため。Issue #81）。`Issues/p3.1-102-ai-review-banner-visual-check.md` に別項目として記録した（Issue #657 / #658 と同じ形）。

<!-- -->

> **「このページのレビュー状況を見る」— レビュー追跡 Issue への導線（Issue #579）**: バナーは長らく「このページは未レビューです」と述べながら、**そのレビューを完結させる場所（`wikicommit-merge` Step 8 が作るレビュー追跡 Issue。Issue #313）へ辿り着く手段を持っていなかった**。Issue #313 が利点として挙げる「Claude Code のセッションを持たない読者も GitHub 上で Close するだけでレビューに参加できる」という入口が、公開サイト側に存在しないままだった（本節の図はこのボタンを当初から描いていたが、その説明は Issue #281 の旧「後レビュー用 PR」方式のままで、実装も存在しなかった）。
>
> **Issue 番号はビルド時に分からない**。追跡 Issue は PR マージ**後**に作られる一方、Quartz ビルドは同じマージがトリガーであり、番号は frontmatter にも無い。静的に組み立てられるのは Issue タイトル `Review: <Type>/<slug> (<lang>)` とラベル `wikicommit-review` だけなので、この2つで GitHub の Issue **検索 URL** を組み立てる（`is:issue is:open label:wikicommit-review in:title "<Type>/<slug> (<lang>)"`）。材料はすべて同コンポーネントが既に `reportUrl` に使っているもので足り、新しい frontmatter フィールド・書き戻し・再デプロイは要らない。
>
> **検索キーにページの `title` を使わない**。Issue タイトルが `title` を含まないというだけでなく、ページの再生成は `title` を変えうる一方 `type`/slug/`lang` は変えない（再生成はページ起点であり既存の型と slug を前提とする操作のため）ので、`title` をキーにすると再生成のたびにリンクが外れる。
>
> **`is:open` が再生成対応の要**。再生成されたページは `reviewed` から `pending` に戻り、次の `wikicommit-merge` Step 8 が**新しい**追跡 Issue を立てる（Step 8 のスキップ判定は open な Issue のみを見る）。結果として1ページに同一タイトルの Issue が時系列で複数存在しうるため、フィルタが無いと**Close 済みの Issue を現在のレビュー先として提示してしまう** — 「リンクが無い」より悪い誤誘導になる。`state:open` ではなく `is:open` を使うのは、GitHub 自身の Issue 一覧が出す形（`?q=is%3Aissue+is%3Aopen`）だからである。タイトルから `Review:` 接頭辞を落としているのは、`label:wikicommit-review` が既に集合を絞っており識別力を持たない一方、引用句の中で唯一のコロンだったため。
>
> **壊れ方が穏やかであること**が検索方式を選んだ理由の一つでもある。Issue がまだ無い状態（Step 8 到達前・作成失敗）でも「検索結果 0 件」のページに着地するだけでリンク切れにならない。GitHub のタイトル検索はトークン単位のため、slug を延長した隣接ページ（`.../yamada-taro` と `.../yamada-taro-jr`）が同時に出ることはありうるが、ラベルと状態のフィルタで一覧は短く保たれる — リンク文言が特定の Issue を開くと断定しないのはこのためである。
>
> **表示条件**: `review_status: pending` のときのみ。追跡 Issue が open である期間とページが `pending` である期間は `review-issue-close-sync.yml` によって一致する（Close → `reviewed` に書き換え → 再ビルドでバナー自体が消える）ため、「Close 済み Issue へのリンクが残り続ける」状態は構造的に発生しない。加えて `GITHUB_REPOSITORY`・`type`・`lang`・ページのファイルパスのいずれかが欠けている場合はリンクを出さない（検索キーを組み立てられないため。`reportUrl` の `"#"` フォールバックとは扱いを変えている）。この条件は副次的に、`type`/`lang` を持たない Quartz 生成のフォルダページ・タグページにリンクが出ることも防ぐ（下記の Issue #580 コールアウトが扱う WikiCommit 生成のナビゲーションページとは別系統で、あちらは `review_status: reviewed` のスタンプによってそもそもバナー自体が出ない）。
>
> **報告リンク（§8.5）はこれを置き換えるものではなく併置する**。あちらは `review_status` に関わらず常時表示され（Issue #245）、レビュー済みページで誤りを見つけた読者の手段であり続ける。逆にレビュー済みページからレビュー追跡 Issue への導線は設けない — 該当 Issue は Close 済みであり、誘導する価値が薄いため。

<!-- -->

> **ビルド生成のナビゲーションページはバナーの対象外（Issue #580）**: `WikiCommitBanner` は `review_status` が無い場合 `pending` にフォールバックする（LLM 生成ページで書き漏れた場合に安全側へ倒すための意図的な設計）。したがって、機械が組み立てるナビゲーションページには書き出し側で `review_status: reviewed` を明示的にスタンプする。対象は3種類あり、いずれも「LLM が書いた Wiki コンテンツではない」という同じ理由による: root `content/index.md`（`convert_wikilinks.py` の `generate_root_index()`。Issue #407）・`content/sources/` 配下の各ページと索引（同 `_write_source_page()`・`_write_sources_index()`・`_write_source_dir_index()`。Issue #476）・Type 別インデックス `.wikicommit/entity/<lang>/<Type>/index.md`（`rebuild_index.py`。Issue #580）。最後の 1 つは他の 2 つと違って `.wikicommit/entity/` 配下に実体を持ち、生成元スクリプトも異なるため、この慣習から構造的に漏れていた。
>
> **この 3 種は「WikiCommit が書き出すナビゲーションページ」の全件であって、バナーが誤表示されうるページの全件ではない**。Quartz 自身が生成するフォルダページ（`content/ja/` 等）・タグページには対応する `.md` の実体がどこにも書き出されず、スタンプする書き出し側が存在しないため、このスタンプの慣習では覆えない。**残る 2 種はスタンプではなくレイアウト設定で解決する**（Issue #648）: `quartz.config.yaml` の `layout.byPageType.folder` / `tag` の `exclude` に `wikicommit-banner` を加え、これらのページではコンポーネント自体を描画しない。`review_status` のフォールバック（未設定なら `pending`）はそのまま維持する — あれは LLM 生成ページでの書き漏れを安全側へ倒すための設計であり、バナーが出るべきでない機械生成ページの側で抑止する方が、フォールバックの意味を変えるより副作用が小さい。
>
> この除外は `review_status: pending` のバナー本体だけでなく、常時表示の報告リンク（§8.5）も同時に落とす — 機械生成の目次に対して「この内容に問題があれば報告」を出す先が無い以上、こちらも消えるのが正しい。Issue #579 のレビュー追跡 Issue へのリンクは、`type`/`lang` が欠ければリンクを出さないという別系統の条件により、この変更以前からフォルダ・タグページには出ていなかった。
>
> **既存リポジトリへの遡及適用は行われない**。`quartz.config.yaml` は `always_skip_existing=True` で生成されるため、`/wikicommit-init --quartz` を再実行しても `SKIPPED: quartz.config.yaml (already exists)` となりこの 2 行は届かない（§8.5 の Issue #557 と同じ制約）。既に公開している Wiki でフォルダ・タグページのバナーを消すには、`layout.byPageType.folder` / `tag` の `exclude` に `wikicommit-banner` を手で追記する。本ドキュメント群で繰り返し採っている「新旧混在を許容する」方針をここでも踏襲する。
>
> **レンダリング結果の目視確認は行っていない**。このリポジトリには Quartz 本体が無く（Issue #81）、上記は `quartz.config.yaml` とコンポーネントのコードからの読み取りに基づく。`tests/test_template_mirror_sync.py` が配布テンプレートの `exclude` に `wikicommit-banner` が入っていることを CI で検証し、設定側の回帰だけは止める。
>
> `index.md` は `wikicommit-merge` のレビュー追跡 Issue の対象外でもあるため（同 Step 8 が明示的に除外）、バナーを見た読者が対応する Issue を探しても存在しない、という点でも表示は誤りだった。判定を `WikiCommitBanner` 側に置かないのは §8.8「表示条件」と同じ理由による — 同コンポーネントは `fileData.slug === "index"` のような Quartz 側のスラッグ命名規約に依存しない方針を採っている。

### 8.5 閲覧者フィードバック（Issue 起票）

閲覧者が Wiki ページの報告リンクをクリックすると、`wikicommit-banner` コンポーネント（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-banner/src/components/WikiCommitBanner.tsx` の `reportUrl`）が GitHub の `/issues/new?template=report.md&title=...&body=...` プレフィルURLへ直接リンクする。インラインフォーム・Bot 代理起票・Formspree/Netlify Forms 経由のメール通知は存在しない — SaaS/OSS のいずれの配布形態でも同じ直接リンク方式で動作する。

```
閲覧者が報告リンクをクリック
  ↓
GitHub の Issue 新規作成画面へ遷移（プレフィル済み。GitHub アカウントが必要）
  - タイトル: ページの type + title
  - 本文: ページの公開URL・言語
          （翻訳ページの場合は原文ページへの手がかりも。Issue #528）
          ＋「何を報告してほしいか」の案内（Issue #738。i18n 文字列から組み立てる）
  - ラベル: wikicommit-report（`.github/ISSUE_TEMPLATE/report.md` に固定）
  ↓
閲覧者自身の GitHub アカウントでそのまま Issue を起票
  ↓
メンテナーが /wikicommit-fix <issue-url> を実行
  ↓
通常の審査フロー（→ review_status: reviewed）
```

> **リンク自身が「GitHub アカウントが必要」と述べる（Issue #742）**: 上のフロー図が 2 行目で述べている事実は、**クリックする前の読者には見えていなかった** — 未ログインで `/issues/new?template=…&title=…&body=…` を開くと `login?return_to=<元 URL 全体>` へ飛ばされ、フォームは一切見えない。Issue #665 が「できないことをできると書いている」状態を権限の層で直したのと同じ形の誤りが、アカウントの層に残っていたことになる。**事前入力は失われない**（`return_to` に `template=` / `title=` / `body=` を含む元 URL が丸ごと入り、認証後に復元される）ため、残る欠陥は「リンクが予告なくログイン壁に着地すること」だけであり、対応も報告リンクの隣に事実を 1 つ添えるに留めた（`WikiCommitBanner` の `reportLinkAccountNote`。§8.4 の図に反映済み）。**アカウント不要の受け皿は作らない**（外部サービスは「外部 DB を持たない」設計に反し、スパム対策と個人情報の受領という別種の運用を生む。上記 Issue #538 の撤回と同じ結論）。**参加募集の文言にもしない**のは Issue #665 と同じ線引きである。文言をリンクのラベル自体に折り込まなかったのは、ラベルが `.wikicommit-banner__link` として下線付き・色付きで描画されるためで、注記まで同じ強さで出すと行動の呼びかけと競合する（Issue #738 と共有する「バナーの視覚的な重さを増やさない」制約）。詳しい経緯は `docs/DesignDoc-pipeline.md` §6.2 の Issue #665 コールアウト末尾を参照。
>
> **本節はもともと「GitHub アカウント不要」なインラインフォーム + Bot/Formspree 経由の代理起票として構想されていた（`dev/PRD.md` §5.5「閲覧者が GitHub アカウントなしで誤りを報告できる」）が、これは撤回済みの当初案であり将来実装の予定ではない（Issue #538）**: この機能を最初に実装した Issue #43（p2-012、Phase 2）の完了条件は当初から「誤りを報告するリンクが GitHub Issues の新規作成フォームへ遷移する」であり、インラインフォーム・Bot 代理起票・Formspree/Netlify Forms は Phase 2 の実装時点で一度も作られていない。以降の変更（Issue #245 の常時表示化・Issue #453 の翻訳ページ対応・Issue #528 の原文ページへの手がかり追加）もすべてこの直接リンク方式を前提に積み上げられており、インラインフォーム方式へ戻す・追加実装する計画を示す Issue は他に存在しない（本 Issue 起票時点での検索で確認済み）。`dev/PRD.md` §5.5 の当該記述はこの簡略化を反映しておらず陳腐化しているが、修正は本 Issue のスコープ外とする。
>
> **報告リンクが「何を報告してほしいか」を伝える（Issue #738）**: Issue #723 が「（人にしか確認できません）」と印を付けた 2 項目（実在の人物・組織への害／レビュアー自身の知識との食い違い）は、**それに気づける可能性が最も高い人には届いていなかった**。この 4 項目が書かれているのは `wikicommit-merge` Step 8 が生成するレビュー追跡 Issue の本文だけで、それを読むのはリポジトリの Issue 一覧を見に行く人 — 実質的に運用者本人に限られる。とりわけ害の項目に最初に気づくのは**たいていその記事の当事者本人**であり、当事者は Issue 一覧を見ないが自分について書かれたページは見る。一方、報告リンクは Issue #245 以降 `review_status` に関わらず全ページに常時表示されており、読者は全員これを見ているのに、リンクが開く `report.md` は「何が間違っているか」としか書いていなかった。
>
> **ページに載せられるのは 4 項目のうち 2 つだけである**。項目 1（内容がソース元文書と一致しているか）は読者がソースを取得しない限り実行できず、項目 2（WikiLink のリンク先）は読者が見ているのがレンダリング済みのリンクであるため `[[Type/slug]]` の話が届かない。ページ側に意味があるのは #723 が印を付けた 2 つだけで、これは偶然ではない — その印の基準が「機械が原理的にできないこと」であり、それは実質的に「読むだけで気づけること」だからである。
>
> **置き場所は 2 つに分け、どちらも薄い版にした**:
>
> | 置き場所 | 得るもの | 払うもの |
> |---|---|---|
> | バナーに 2 項目を常設 | 読む**前**に何を見ればよいか分かる | 全ページ・全訪問で同じ 2 行。Issue #562 が blocking から降格させた「常時点灯する警告は読まれなくなる」が、1 ページ 1 回ではなく毎回になる |
> | 事前入力される Issue 本文 | 報告すると決めた瞬間に、何を書けばよいか分かる | 読む前には効かない |
>
> **バナーにはチェックリストのブロックを追加しない**。代わりに `reportLink` のラベルを「誤りを報告する」→「気づいた点を報告する」（`Report an issue` → `Report something you noticed`）に改めた — 文字列 1 つの変更で「誤り」への限定が外れ、バナーの視覚的な重さは 1 文字も増えない。具体的な 3 項目は事前入力される Issue 本文に置く。
>
> **`report.md` に直書きせず i18n 文字列から組み立てる**。`report.md` はリポジトリに 1 ファイルしかなく言語を持たない一方、`reportBody` は `t.reportBodyPage` 等から組み立てられているため、そこに足せばページの言語に自動的に従う（日本語ページから来た読者が英語のプロンプトを見ることがない）。ただしリンクを経由せず `/issues/new` から直接開いた人には事前入力が効かないため、`report.md` 側にも簡潔な版を置く（同ファイルの既存コメントが元からこのケースを想定していた）。
>
> **「以下のいずれかでなければ報告するな」と読める形にしない** — 誤字・古い情報・リンク切れも当然受け付けるため、箇条書きの後に 1 行そう明記する。ただし**「その他、気づいたこと」のような包括的な受け皿は置かない**: 報告リンクが立てるのは Issue であり、**Issue は誰かが処理すべきものとして立つ**以上、書く側に「直すべきだ」という確信が要る。確信に至る前の半端な気づき（時間をおいて複数ページを読む人しか持てないもので、Issue #566 がバッチをまたぐ矛盾について「原理的に届かない」と認めた領域）を書ける場所は別に要るが、それは Issue ではない — Issue #741（giscus）がその層を扱う。**どちらか一方に包括的な受け皿を作り直してはならない**（分担が崩れる）。
>
> **事前入力の案内は HTML コメントに包み、`## Problem` 見出しを添える**。`report.md` のプロンプトはすべて HTML コメントであり Issue の投稿時に消えるが、`body=` の事前入力はただのテキストなので**そのまま投稿される** — 実害は見た目ではなく、`/wikicommit-fix` が Issue の本文全体をフィードバックとして読み「各論点を個別に分類する」（Issue #529）ことにある。常設の 3 箇条書きが毎回の報告に残れば、それが 3 件の論点として扱われ、根拠のない修正案を生む。あわせて `body=` は `report.md` 自身の `## Page` / `## Problem` 見出しを丸ごと置き換えるため、見出しを事前入力側が持たないと**書く場所が無いまま案内で終わる**（ページ情報の各行は自分でラベルを持つので、そちらに見出しは要らない）。
>
> **チェックボックス形式にしない**。`- [ ]` は attestation の UI であり、「確認した」に印を入れさせる形は追跡 Issue の 4 項目が持つ重さの一部である。報告テンプレートでは平の箇条書きにする。
>
> **追跡 Issue と同じ文面にしない**。Issue #740 が同じ 2 項目を追跡 Issue 側にも置くが、聞かれている行為が違う — 報告リンクは「気づいたら教えてください」（Issue が 1 件立つ。任意かつ部分的）、追跡 Issue は「Close する前にこの 2 つに目を留めてください」（ページが `reviewed` になり、名前が付く）。同じ箇条書きをコピーすると、片方が他方の劣化コピーに見えて、どちらも読まれなくなる。
>
> **URL 長の実測**: `reportBody` は `encodeURIComponent` を通して URL クエリに載る。日本語は最悪ケース（1 文字が UTF-8 で 3 バイト、パーセントエンコードで 9 バイト）であり、`saitama-city-wiki` 相当の実パス・実タイトルで組み立てた最終文言の URL 全長は **2,209 バイト**だった。GitHub 側の受け入れ限界は実測で「約 6KB までは 200、約 7KB から接続断、約 16KB で `414 URI Too Long`」であり、約 2.7 倍の余裕がある。`WikiCommitBanner.test.tsx` がこの上限（6,000）を回帰テストとして固定しているため、文言を伸ばしすぎれば CI が落ちる。
>
> **既存リポジトリへの遡及適用は行われない**。`report.md` は `always_skip_existing=True` で生成されるため再 init では届かない（§8.5 の Issue #557 と同じ制約）が、`quartz-plugins/` は `update: overwrite`（Issue #712）なのでバナー側の案内は再 init で届く。

<!-- -->

> **翻訳ページからの報告に原文ページへの手がかりを含める（Issue #528）**: プレフィルされる Issue 本文には元々ページの公開URL・言語のみが含まれていたが、対象ページが翻訳ページ（`translated_from` あり）の場合、原文ページへの手がかりを追加の行として含めるようにした: `allFiles` から `translated_from` が指す原文ページを解決できれば、`WikiCommitSources.tsx`（`entityPathToRelativePath()`。インライン `sources` ボックスの継承元ページ解決ロジック）と同じロジックで原文ページの公開URLを算出して埋め込む — このURLは `/wikicommit-fix <published-page-url> "<instruction>"`（Issue #454 の Published-URL-driven ルート）にそのまま渡せる形式になる。解決できない場合（`cfg.baseUrl` 未設定・`allFiles` に一致するページがない・原文ページ自身が `status: removed`）は、`translated_from` の生値（`.wikicommit/entity/<lang>/<Type>/<slug>.md` 形式のパス）をそのまま埋め込む — こちらは `/wikicommit-fix <page-path> "<instruction>"`（page-path-driven ルート）にそのまま渡せる。翻訳固有の指摘か内容由来の指摘かでどちらのページを実際の修正対象にすべきかの判定・確認ロジックは `/wikicommit-fix` 側（Issue #529、`docs/DesignDoc-skills.md` の `wikicommit-fix` 記載参照）が担い、本コンポーネントは判定材料をIssue本文に埋め込むだけに留める。
>
> **フッターの GitHub リンクも同じ「利用者のリポジトリ」を指す（Issue #557）**: `quartz-community/footer` プラグインの既定設定は `GitHub: https://github.com/jackyzha0/quartz` と `Discord Community: https://discord.gg/...` の2リンクで、そのまま配布すると、公開サイト上でもっとも目につく GitHub リンクが上流の SSG リポジトリを指す状態になっていた。本節が説明する「読む → Issue を起票する → レビュー追跡 Issue を Close して `reviewed` に昇格させる」という導線は読者が対象リポジトリに辿り着けることを前提にしており、バナー内の報告リンク（正しく利用者のリポジトリを指す）と同一サイト内で食い違ってもいた。
>
> 対応は `pageTitle` に対する Issue #317 と同じ機構 — テンプレートの当該行を `GitHub: {REPO_URL}` プレースホルダーにし、`init.py` が生成時に置換する。値は `wikicommit-init` SKILL.md が `--repo-url="$(gh repo view --json url -q .url)"` というコマンド置換の形で渡す（エージェントが自分で解決した URL を貼るのではなくコマンド置換として書くことで、値がエージェントを経由しない）。
>
> **GitHub リモートが解決できない場合**（ローカルのみで初期化した・`gh` 未認証等。上記コマンド置換は空文字列に展開され、フラグ省略と同じ扱いになる）は、**`GitHub:` エントリごと削除して `links: {}` にする**。上流 Quartz の URL に戻すのは修正しようとしている不具合そのものであり、リテラルの `{REPO_URL}` を設定ファイルに残すのはそれより悪いため。footer プラグイン自身が `opts?.links ?? []` で空を扱えるため、フッター自体はリンク一覧なしで描画され続ける（Quartz 自身のクレジット表記はプラグインが別途描画するもので影響を受けない）。この削除は `init.py` が `NOTE: quartz.config.yaml: no --repo-url resolved ...` 行で報告する — `--repo-url` はコマンド置換として渡されるため、解決失敗が `gh` 自身の stderr にしか現れず、SKILL.md が要求する「ユーザーへの通知」の判断材料が他に無いため。
>
> `Discord Community:` 行は WikiCommit 側に対応する導線がなく置換先が存在しないため、リターゲットではなく削除した。既存リポジトリへの遡及適用は行わない — `quartz.config.yaml` は `always_skip_existing=True` で生成されるため再 init しても上書きされず、本ドキュメント群で繰り返し採っている「新旧混在を許容する」方針をここでも踏襲する（既存利用者は当該2行を手で編集する）。

### 8.5.1 気づき・報告・宣言の 3 層（giscus。Issue #741）

**確信に至っていない気づきを書ける場所が、この Wiki のどこにも無かった。** §8.5 の報告リンクは `wikicommit-report` ラベルの **Issue を立てる**ため、書く側に「直すべきだ」という確信が要る。「これ面白いな」「なんとなく他のページと言っていることが違う気がする」を Issue にするのは形が合わず、結果そういう気づきは書かれないまま消えていた。

| 層 | 場所 | 誰が | 何を | 必要な確信 |
|---|---|---|---|---|
| **気づき** | giscus（ページ上） | 誰でも・何度でも | 「気がする」の段階のもの。感想も含む | 不要 |
| **報告** | 報告リンク → `wikicommit-report` | GitHub アカウントを持つ誰でも（Issue #742） | 直すべきだと確信したこと | 要る |
| **宣言** | レビュー追跡 Issue の Close | Close 権限を持つ人（Issue #665） | 読んだという表明。状態遷移 | — |

**消えているものが、機械が原理的に届かない領域と重なる**のが要点である。Issue #566 はページ間矛盾の検出について 2 つの限界を**解決せずに受け入れた**と明記している — 同一バッチ内では先に生成された兄弟しか見られず、**異なるバッチで生成された 2 ページ間の矛盾は原理的に届かない**。つまりバッチをまたいで複数ページを保持している主体は、システム内に**人間しかいない**。今日 A を読み、来週 B を読む人だけが、その 2 つを同時に持っている。そして `dev/pilot-saitama-wiki.md` の実測がこれを裏づける — 公開まで到達した欠陥は**ページ間矛盾 3 件だけ**で、ハルシネーション・捏造・誤帰属・孫引き・年号誤りは 0 件だった。その気づきは「気がする」の段階で生まれるため、受け皿が Issue しか無ければ確信に至らなかったものは失われる。

giscus と報告リンクが受けるのは**同じ産物（欠陥への気づき）の確信度違い**であり、下書きと提出のような関係になる。確信が固まった場合は本人が報告リンクから別途 Issue を立てる — **giscus のコメントを Issue へ自動昇格させる機構は作らない**（どのコメントが確信に達したかを機械が判定できない）。分担を保つため、どちらの面にも包括的な受け皿を作り直さない。

#### リアクションを `review_status` に配線しない

技術的には可能（Discussions にも webhook イベントがある）が、4 つの理由で採らない。

1. **👍 は「読んだ」を意味しない。** 「良かった」であって「読んで報告することが無かった」ではない
2. **閾値に原理が無い。** リアクションは累積し `review_status` は 2 値。1 件で遷移か 3 件か、どの数字にも根拠が無い
3. **アクセス制御が壊れる。** Close には write / triage が要る（Issue #665）。`reviewed` はこの Wiki が読者に対して行う主張であり、通りすがりの誰でも反転できる状態にするのは信頼モデルの変更そのものである
4. **作業リストが消える。** Discussion は最初の反応があって初めて生まれるため、**誰も触っていないページには Discussion が存在しない** — 「まだ誰にも読まれていないページ」の列挙ができなくなる

giscus は「**どれだけ届いたか**」（累積・終端なし）の軸で完結させ、「**届いたか**」（2 値・終端あり）の軸には接続しない。この分離により Issue #669 の懸念（信頼ラダーの第 3 の状態）にも当たらない。

#### 実装

`quartz.config.yaml` テンプレートの `github:quartz-community/comments` ブロックは `enabled: false` のまま配布し、**4 値（`repo` / `repoId` / `category` / `categoryId`）をプレースホルダーとして先置きしない**（Issue #553 — 大半のリポジトリで永久に空のまま残る）。有効化手順は `wikicommit-init` SKILL.md の「Enabling comments (giscus)」節に置き、前提 3 つ（public / giscus app / Discussions）と Announcements 型カテゴリ推奨を明記する。

**既存 Wiki には自動では届かない。** `quartz.config.yaml` は `_root_outputs.py` で `update: review`（Issue #712）のため、再 init でも `/wikicommit-update` でも上書きされない。ブロック自体は既に存在するので `check_distribution_freshness.py` の `yaml_keys` 差分にも出ない — **有効化は各 Wiki の運用者が手で行う操作**になる。

**ビルド生成のナビゲーションページには出さない。** giscus はレイアウトの `afterBody` に入るため、放っておくと Type 別インデックス・view 別インデックス・root index・`content/sources/`・`content/overview/` にも付く。これらは知識のページではなくナビゲーションと集計であり、その下にコメント欄が並んでも受け取るものが無い。手段はプラグイン側に既にあり（frontmatter の `comments` が `false` なら描画しない）、**これらの経路は Issue #580 / #664 の理由で既に `review_status: reviewed` をスタンプしているため、まったく同じ場所に 1 キー足すだけで済む**。判定を表示側（スラッグ命名の推測）に置かず書き出す側でフィールドを持たせる、という Issue #580 の線引きもそのまま当てはまる。

**ただし frontmatter だけでは届かないビルド生成ページが 2 種類ある。** Quartz 自身が合成する folder ページと tag ページには対応する `.md` の実体がどこにも書き出されないため、スタンプする書き出し側が存在しない。とくに `content/<lang>/index.md` は書き出していないので、**言語トップ（`/ja/` 等）は必ず合成 folder ページになる**。`/tags/<tag>` も同様。この 2 種は `layout.byPageType.folder.exclude` / `tag.exclude` に `comments` を並べて除外する — **同じファイルの同じリストが、まったく同じ理由（スタンプする書き出し側が存在しない）で既に `wikicommit-banner` を除外している**（Issue #648）。したがって除外は 2 系統あり、どちらか一方では覆えない: 書き出し側があるページは frontmatter、無いページはレイアウト設定である。

**UI 言語は 1 つに固定される。** `lang` はプラグイン設定の 1 値で、ページの `lang` frontmatter には追随しない（回避手段が無い）。多言語 Wiki では読者の言語とずれるが、`primary_lang` に合わせるのが既定として妥当である。

#### 受容済みのリスク

| リスク | 扱い |
|---|---|
| `github:quartz-community/*` への依存 | ビルド不安定の系譜（Issue #332 / #382 / #426 / #443 / #449）に 1 本足すことになる。**元から不安定であるため受容**する |
| 空だと空に見える | 全ページに「0👍」が並ぶ。報告リンクは空でも空に見えないが、投票ウィジェットは空だと空に見える。**受容**する |
| アカウントを持たない読者には届かない | giscus のリアクション・コメントには GitHub アカウントと OAuth 認可が要る。**ただしこれは giscus が新たに作る壁ではない** — 報告リンクからの Issue 起票にも、追跡 Issue の Close にもアカウントが要る。giscus が足すのは OAuth 認可 1 回だけで、認可後のリアクションは 1 クリックであり **Issue 起票より軽い**。アカウントを持たない読者への経路は Issue #742 で扱う |

#### アクセスランキング・アナリティクスは含めない

GitHub Pages はアクセスログを提供しない（`analytics: null` が既定なのはそのため）ため第三者アナリティクスが必須になるが、**画像のホットリンクを退けた理由の 1 つが「読者のブラウザが第三者サーバーへリクエストを出すため、閲覧の事実と IP が漏れる」**である（§8.6）。画像で採った立場と逆のことを解析で全ページに対して行うことになる。GoatCounter や Plausible は cookie-less でこの問題は小さいが、第三者へのリクエストであること自体は変わらない。**やるなら画像の判断と立場を 1 つに揃える必要がある**ため別途とする。

---

### 8.6 画像・動画の埋め込み（Issue #167 実地検証済み）

新規の仕組みは不要。Quartz v5 標準の Obsidian Flavored Markdown プラグイン（`quartz.config.yaml` の `obsidian-flavored-markdown`）が標準 Markdown 構文のみで以下をすべてサポートしていることを、実際に Quartz ビルドを実行して確認した（`enableInHtmlEmbed: false` のまま・設定変更なし）。

| 埋め込み対象 | 記法 | 挙動 |
|---|---|---|
| ローカル画像 | `![alt](../../assets/xxx.png)`（`.wikicommit/entity/<lang>/<Type>/<slug>.md` から `.wikicommit/entity/assets/` への相対パス。ファイル名規約は `docs/DesignDoc-data.md` §3.1 参照） | `<img>` としてそのまま表示（`convert_wikilinks.py` が `.wikicommit/entity/assets/` を `content/assets/` へミラーする。Issue #589） |
| 外部URL画像 | `![alt](https://example.com/image.jpg)` | `<img>` としてそのまま表示 |
| ローカル/外部動画ファイル（mp4・webm 等） | `![alt](path-or-url.mp4)` | `enableVideoEmbed`（デフォルト `true`）により自動で `<video controls>` に変換される |
| YouTube 動画 | `![alt](https://www.youtube.com/watch?v=xxxxxxxxxxx)` | `enableYouTubeEmbed`（デフォルト `true`）により URL を含む画像記法の `<img>` が自動で `<iframe class="external-embed youtube">` に変換される。**画像埋め込みと全く同じ標準 Markdown 構文**（`![alt](url)`）でよく、`<iframe>` を手書きする必要はない |

> **ローカル画像の行だけは実パイプラインを通した検証ではなかった（Issue #589 で修正）**: 上表の検証（Issue #167）は Quartz の `content/` ツリーへ直接ファイルを置いて行われたため、「`content/` に置けば表示される」ことしか確かめておらず、**`.wikicommit/entity/assets/` を `content/` へ運ぶ工程が実パイプラインのどこにも存在しない**ことを見落としていた（`convert_wikilinks.py` の `main()` は `rglob("*.md")` しか走査せず、`prebuild-symlinks.cjs`・`package.json` の `build`/`preview`・`deploy.yml` のいずれにもアセットのコピー工程が無かった）。そのため上表が推奨する相対パスは公開サイトで 404 になっていた。外部URL画像・YouTube・動画URLはこの経路を通らないため、壊れていたのはローカル画像の行だけである。Issue #589 で `convert_wikilinks.py` に `sync_assets()` を追加し、`.wikicommit/entity/assets/` 配下の全ファイルを `content/assets/` へミラー（および削除済みファイルの stale cleanup）するようにした。実ビルドで `content/assets/diagram.png` → `public/assets/diagram.png` および `<img src="../.././../assets/diagram.png">` としてページに描画されることを確認済み。
>
> 同種の齟齬の再発防止として、公開サイト側の挙動を検証する際は `content/` へ直接ファイルを置くのではなく、`.wikicommit/entity/` を起点に `convert_wikilinks.py` を通して確認すること（`content/` は `convert_wikilinks.py` の出力であり、手で置いたものは実行のたびに stale cleanup の対象になる — Issue #271）。
>
> **custom 型ページのフラット化（Issue #576）との干渉**: Issue #576 は custom 型ページの出力先を `content/<lang>/custom/<Type>/` から `content/<lang>/<Type>/` へ 1 段浅くする。`![alt](...)` は素の Markdown リンクで `convert_file()` の WikiLink 変換対象外のため、本文に書かれた相対パスはそのまま出力され、フラット化と同時に壊れる。両 Issue のうち後に実装される Issue #576 側で、フラット化の際に本文中の相対パス（`![](...)` の相対 `src`）も併せて書き換えることとする（Issue #589 実装時に決定・#576 にも記録済み）。

`enableYouTubeEmbed` / `enableVideoEmbed` はいずれも `quartz.config.yaml` テンプレートで明示的に上書きしていないため、デフォルト値 `true` が有効になっている。したがって `.claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml` の変更は不要。

#### `enableInHtmlEmbed` は変更しない

Issue #167 の当初仮説は「YouTube 埋め込みには `enableInHtmlEmbed: true` が必要」だったが、実地検証の結果これは誤りと判明した。

- `enableInHtmlEmbed` は Obsidian Flavored Markdown プラグイン内の話者向けオプションで、**生 HTML ブロック内に書かれた** `[[WikiLink]]` / `==highlight==` / `#tag` 記法を後処理でパースするかどうかのみを制御する。YouTube・動画埋め込みは上記の通り別の専用オプション（`enableYouTubeEmbed` / `enableVideoEmbed`）で処理されており、`enableInHtmlEmbed` とは無関係。
- **`<iframe>` 等の生 HTML タグを Markdown 本文に直接貼り付けた場合、`enableInHtmlEmbed` の値に関わらず常にそのまま出力される**ことを実際のビルド出力（`toHtml` 後の HTML）で確認した。Quartz コア（`quartz/processors/parse.ts`）が `remarkRehype(..., { allowDangerousHtml: true })` を常時有効にしており、プラグイン側のオプションでこれを無効化する経路がないため。

このため `enableInHtmlEmbed` を `true` に変更しても、WikiCommit が必要とする埋め込み機能（画像・動画・YouTube）は増えず、セキュリティ上のリスクも変化しない（生 HTML の通過は現状の `false` のままでも既に常時許可されている）。**`enableInHtmlEmbed: false` を変更せず維持する**。

#### 検証で判明した既存のリスク（本 Issue のスコープ外・別Issueで追跡）

上記の検証中に、Wiki 本文に混入した `<script>` タグが `enableInHtmlEmbed` の設定に関わらず常にそのまま HTML 出力に含まれ、閲覧者のブラウザで実行されることを実際のビルド出力で確認した。経路A（`DesignDoc-pipeline.md §6.3`）では `review_status: pending` の LLM 生成ページが人間レビュー前に一旦 main マージ・公開される設計のため、ingest 元文書に埋め込まれた悪意ある HTML（間接プロンプトインジェクション等）や LLM のハルシネーションにより生 `<script>` / `<iframe>` がページ本文に混入した場合、レビュー前に公開サイトで実行されうる。これは `enableInHtmlEmbed` の値とは無関係に既に存在するリスクであり、本 Issue の完了条件（`enableInHtmlEmbed` の要否検討）の範囲外のため、別 Issue（#377）で HTML サニタイズ方針を検討した。対応結果は次節参照。

#### 生 HTML の扱い方針（Issue #377）

上記リスクへの対応として、本節冒頭の表が確認した通り画像・動画・YouTube の埋め込みは標準 Markdown 構文（`![alt](path-or-url)`）だけで完結しており、ページ本文が生 HTML タグを必要とする正当なユースケースは存在しないと結論づけた。この前提の下、Issue #377 が挙げた3案（a. サニタイズ処理の追加、b. 生成時制約 + `wikicommit-merge` でのブロッキング検証、c. 経路A自体の見直し）のうち **b を採用**した:

- `wikicommit-generate` の Pass 3（`.claude/skills/wikicommit-generate/SKILL.md`）に、ページ本文へ生 HTML タグを一切書かないという生成時制約を明記した（ソース文書自体が生 HTML を含む場合でも、意味を抽出するだけでマークアップはコピーしない）。
- `.wikicommit/scripts/check_raw_html.py`（新規）を `wikicommit-merge` の品質ゲートに追加した。ページ本文（frontmatter を除く）を対象に、コードフェンス（バッククォート3つ、または `~~~`）とインラインコード（バッククォートで囲んだ範囲）で囲まれた箇所（Markdown が地の文としてエスケープ表示するため実害がない）と、CommonMark オートリンク（`<https://...>`・`<user@example.com>`。Pass 3 のベア URL 対応で明示的に使われる記法）を除外した上で、`<tag ...>` 形式の生 HTML タグを1件でも検出したら blocking ERROR とする。タグの許可リスト（例: `<br>` だけ許可）は意図的に持たない — 「危険なタグだけ禁止」ではなく「生 HTML自体を一切禁止」という設計判断のため、サニタイズによる許可リストという (a) 案の性質を部分的に持ち込まないようにした。

a 案（サニタイズ）・c 案（経路Aの設計見直し）は不採用: a はそもそも許可すべき生 HTML タグが存在しない（前提が成立しない）ため、許可リストを維持するコストに見合うメリットがない。c は経路A全体（レビュー前の自動マージ・公開）という中核設計を、この1つのリスクのためだけに見直す影響範囲の大きさに見合わないと判断した — b で「レビュー前に公開されうる生 HTML」自体をマージ時点で機械的に排除できるため、経路Aの設計そのものは変更不要という結論に至った。

詳細は `docs/DesignDoc-ScriptSpec.md`（`check_raw_html.py` の仕様）・`docs/DesignDoc-pipeline.md` §7（品質ゲート一覧への追加）を参照。

### 8.7 `tags` による多軸フィルタリング — 実地検証結果（Issue #287）

`tags` フィールドが読者にとって実際にどう機能するか（Quartz v5 のタグページ・タグ一覧コンポーネント・全文検索プラグインが `tags` をどう扱うか）は、`docs/DesignDoc-data.md` §4.1 の付与ルール整備（Issue #275）とは別に未検証だった。`jackyzha0/quartz`（v5.0.0）本体と、`quartz.config.yaml` が参照する `quartz-community` 配下の該当プラグイン（`tag-page`・`tag-list`・`search`・`content-index`）のソースを実際にクローンし、さらに `tags` を持つテストページ4件（`indoor`/`strategy`/`outdoor`/`children`/`hiding`/`running` の6タグ）で実際に `npx quartz plugin install` → `npx quartz build` まで実行して生成物を確認した（ソースコードの読解だけでなく、実際のビルド出力・`contentIndex.json`・コンパイル後の検索スクリプトバンドルで裏付け済み）。

**確認できた挙動**:

| 機能 | 挙動 | デフォルト状態 |
|---|---|---|
| タグページ（`tag-page` プラグイン、`/tags/<tag>/`） | タグ1つにつき1ページを自動生成（例: `/tags/outdoor/` に `outdoor` を持つページのみ列挙）。`/tags/` は全タグの一覧＋各タグの内訳をまとめて表示。**単一タグの閲覧のみ**— 複数タグの AND/OR 絞り込み UI はこのページ自体には存在しない | 有効（WikiCommit テンプレートも同じ） |
| タグ一覧コンポーネント（`tag-list` プラグイン。ページ本文直下にタグクラウドを表示） | プラグイン自体は存在するが、**`quartz.config.default.yaml`（アップストリームのデフォルト）でも WikiCommit の配布テンプレート（`.claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml`）でも `enabled: false`** | **無効**（要対応、後述） |
| 全文検索（`search` プラグイン、FlexSearch ベース、ツールバーに常設） | 検索ボックスに `#tag1 #tag2 キーワード` と入力すると、**指定した全タグを持つページに絞り込む（AND）**。自由文検索と組み合わせ可能。`#` を入力するとタグ名の自動補完ドロップダウンが出る。**OR 結合はサポートされない**（`parsed.tags.every(...)` による積集合のみ。`quartz-community/search` の `search.inline.ts` で確認） | 有効 |
| 検索インデックス（`content-index` プラグイン、`static/contentIndex.json`） | 各ページの `tags` 配列を正しくシリアライズしており、上記の `#tag` 絞り込みの検索対象になっている | 有効 |

**結論**: 「タグによる多軸フィルタリング」自体は Quartz v5 の標準機能（`search` プラグインの `#tag` 構文）としてすでに実装されており、AND 結合の複数タグ絞り込みが実際に機能する。カスタムコンポーネントの新規実装は不要と判断する。

一方で、この機能の**発見可能性（discoverability）が低い**ことが実地検証で判明した:

- 検索ボックスのプレースホルダーは `"Search for something..."` のままで、`#tag` 構文のヒントがどこにも表示されない（`quartz-community/search` の `en-US.ts` ロケール定義を確認）
- `tag-list`（タグクラウド）が無効なため、読者はそもそもどんなタグが存在するか一覧できる場所が `/tags/` ページ（明示的に URL を知る/リンクを辿る必要がある）以外にない

**「タグのままで十分か、ページ化すべきか」の暫定判断基準**（Issue #275 が扱う「付与ルール」とは別軸。`dev/issue_candidate.md`「実質的なギャップ: タグへの退避」への回答）:

- タグのままで十分な用途: 横断的な絞り込みラベルとして使われるだけで、それ自体の説明・定義を必要としない概念（例: `outdoor`/`indoor` のようなカテゴリ）。`search` の `#tag` 構文が実際に機能するため、複数タグを組み合わせた絞り込みという用途は標準機能で満たされる
- ページ化すべき用途: そのタグ自体に固有の説明・定義・関連ページへの WikiLink が必要な概念（`schema:DefinedTerm` 等の独立ページに値する内容）。タグは frontmatter の平文文字列に過ぎず、WikiLink・本文・出典を持てないため、内容を持つべき概念をタグに逃がし続けると本文としては永久に存在しないままになる

**機能不足の判定と後続対応**: 絞り込み機能そのものは標準機能で足りているため、カスタムコンポーネントの新規実装は不要。ただし発見可能性のギャップ（プレースホルダーのヒント欠如・`tag-list` 無効）は実際の読者体験を損なう低リスクな改善余地であり、`Issues/p3-109-tags-search-discoverability-gap.md`（草案（非公開の開発リポジトリ側の記録））として別Issue化した（Issue #312）。

#### 発見可能性ギャップの対応結果（Issue #312）

1. **`tag-list` を配布テンプレートで有効化した**（`.claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml`）。設定は `enabled: false` → `true` のみ（`position: beforeBody`・`priority: 30` は既存のコメントアウト値のまま変更なし）。実際にビルドして確認したところ、ページタイトル・メタ情報の直後、本文の直前に `<ul class="tags">` としてタグクラウドが表示され、`/tags/<tag>/` への内部リンクとして機能した。

2. **検索ボックスのプレースホルダーへの `#tag` ヒント追加は、フォークで対応した**（`../quartz-plugins/wikicommit-search`。既存の `wikicommit-banner`/`wikicommit-breadcrumbs` 等と同じフォーク方式）。`search` プラグインの `SearchOptions`（`enablePreview`/`fieldPriority` のみ）にはプレースホルダー文言を上書きする YAML オプションが存在しない（`quartz-community/search` の `Search.tsx` を確認済み）ため、config だけでの対応は不可能と判明した。
   - **フォークの footprint を最小化した判断**: `search` プラグイン自体は FlexSearch ベースの検索 UI 本体（`search.inline.ts`、957行）を含む複雑なコンポーネントだが、変更が必要なのはプレースホルダー文字列を組み立てる `Search.tsx`（72行）の1箇所のみ。`search.inline.ts`・スタイル・30 ロケール分の i18n ファイルはすべて上流から無改変でコピーし、`WikiCommitSearch.tsx` のプレースホルダー算出処理だけを `${searchBarPlaceholder} (#tag: ${tagFilterHint})` に変更した。`tagFilterHint`（タグ自動補完ドロップダウン用に全30ロケールへ既存定義済みの文字列。例: en-US "Filter by tag" / ja-JP "タグでフィルター"）を再利用したため、新規の翻訳文字列を追加する必要がなかった。
   - **上書きできないことを確認する過程で検討したが不採用にした代替案**: (a) Quartz コアの `quartz/styles/custom.scss` を編集する案 — この方式は `quartz/` submodule 内のファイルを直接編集するため、CI が毎回フレッシュに `git submodule update` するとその場限りの変更が失われ、恒久的な配布物にならない（WikiCommit の配布物は `.claude/skills/wikicommit-init/scripts/templates/` 配下のみ）。(b) 検索ツールバー内に静的ヒントテキスト用の新規小型コンポーネントを追加する案 — Issue が求める対象は検索ボックスの `placeholder` 自体であり、別コンポーネントで代替すると要件を満たさないため見送った。
   - 実際に `npx quartz build` を実行して確認: `placeholder="Search for something... (#tag: Filter by tag)"`（en-US）・`placeholder="何かを検索... (#tag: タグでフィルター)"`（ja-JP）が生成 HTML に出力されることを確認済み。

3. 上記2点の変更は `wikicommit-serve` Skill（`npm run build`/`preview`）が既存の `../quartz-plugins/*` ローカルパス解決の仕組みをそのまま使うため、他プラグインと同様に追加のビルド手順は不要。

### 8.7.1 グラフビューの動的フィルタ（`wikicommit-graph` フォーク。Issue #584）

`ai-driven-dev-wiki` パイロットの公開グラフで、ページ数が増えると全体を俯瞰できなくなる症状が2つ観測された: **(1) 多言語翻訳すると言語ごとに塊ができる**、**(2) 言語間で共通するタグがハブ化して他の有力なリンクが埋もれる**。

**この2つは同じ構造の裏表である**。`tags` は言語中立な英語識別子で翻訳ページも同じ値を持つ一方（§4.1・§4.2）、本文 WikiLink は `convert_wikilinks.py` が同一言語を優先して解決するため ja→ja / en→en のエッジしか基本的に出ず、原文と翻訳を結ぶ唯一の公式リンクである `translated_from` は frontmatter でありエッジにならない。**つまりタグは言語クラスタ間を繋ぐ唯一の橋であり、だからハブに見える** — グラフは構造を正直に描いている。

> **当初 `content/<lang>/sources.md` が支配的なハブになるという症状も記録されていたが、これは Issue #476 で解消済み**であることをパイロットで確認した。現在は情報源1件＝1ページのツリー（`content/sources/`）になっており、各ソースページは自身の `generated_pages` にしかリンクしない。代わりにノード総数が増えたため、症状は「単一の巨大ハブ」から「全体量が多すぎる」側へ移っている。

**素の `github:quartz-community/graph` では対応できない**。`D3Config` が持つのは `drag`/`zoom`/`depth`/`scale`/`repelForce`/`centerForce`/`linkDistance`/`fontSize`/`opacityScale`/`removeTags`/`showTags`/`focusOnHover`/`enableRadial` がすべてで、ページ単位の除外・言語・型・次数のフィルタをいずれも持たない（`removeTags` はタグ疑似ノードを消すのみでページノードには効かない）。しかもこれらはビルド時に `data-cfg` 属性へ JSON として焼き込まれ、UI から変更する手段がない。

**フォークの重さは差分ではなく足回りにある**（`package.json` の quartz マニフェスト・`tsup.config.ts`・`tsconfig` 2種・`eslint.config.js`・`vitest.config.ts`・`types/`）ため、追加する機能の数によらず同額である。したがって「`showTags` の動的トグルだけ」のためにフォークするのは割に合わず、逆に既存オプションだけで足りるなら YAML に焼き込むのが正しい。**判断は「フォークするか/しないか」の二択**であり、するなら言語・型・次数まで入れるのが費用対効果的である — 本 Issue は後者を採った。

**808行の `graph.inline.ts` には D3 force simulation と PixiJS の描画本体があるが、そこには一切触れていない**。動的化に必要な土台が既に揃っていたため:

1. **設定は毎回読み直される** — `renderGraph()` の中で `JSON.parse(graph.dataset["cfg"])` している。起動時に一度読んで保持する作りではないため、`dataset.cfg` を書き換えて再レンダーすれば新しい設定が効く
2. **絞り込みのチョークポイントが1箇所に集約されている** — `neighbourhood` 確定後・`nodes` 構築前。リンク生成は既に両端を `neighbourhood.has()` でガードしているため、`neighbourhood` から要素を削るだけで下流（ノード生成・リンク生成・力学シミュレーション・衝突半径・描画）はすべて自動的に辻褄が合う
3. **再レンダー経路が既にある** — `showGlobalGraph()` が `cleanupGlobal()` → `renderGraph()` を呼ぶだけ

上流からの変更は4箇所のみで、いずれもソース中に `WikiCommit:` として印を付けてある。

#### ノード分類は slug のパースで行う（`contentIndex` に型も言語も無い）

グラフが読む `contentIndex.json` のエントリは `{slug, filePath, title, links, tags, content, ...}` のみで、**任意の frontmatter は一切載らない**。したがって言語・型の判定はノードID（＝ Quartz の slug）のパースで行うほかなく、WikiCommit 固有のパス文法に依存するロジックをフォーク側に持つ。`contentIndex` に `lang`/`type` を載せる案（transformer プラグインの追加、または `content-index` のフォーク）はプラグインを1つ増やすことになり、slug パース程度で済む問題に対して割に合わないため採らない。

この分類は `src/util/nodeFilter.ts` に切り出して単体テストしてある（inline スクリプトから import する。`wikicommit-explorer` の `foldLang.ts` と同じ形）。判定順は `tags/` → `sources/` → エンティティで、この順序は発見的なものではなく、前2者が publish 層の予約接頭辞であることによる。エンティティの型名は**publish 後の形**である点に注意する — publish はカスタム型のパスから先頭の `custom/` を落とす（Issue #576）ため、`schema:custom/Decision` はグラフには `<lang>/Decision/<slug>` として届き、型名は `Decision` と読める（`custom/` を落とすのは先頭1つだけなので、`custom/custom/Decision` のように二重に付いた型だけは publish 後も `custom` セグメントが残る。第2セグメントの決め打ちではこの型が `custom` という1つの型に潰れるため、そこだけ第2・第3セグメントを連結する）。一方 `quartz.config.yaml` を人手で書く場合は `type:` の綴り（`custom/Decision`）を書くのが自然であり、これを弾くと該当ページが黙って全部消えるため、`types` フィルタは publish 後の綴りと `type:` の綴りの両方を受け付ける（コントロールバーが書き戻すのは常に publish 後の綴り）。

#### 言語・型フィルタはエンティティノードにしか適用しない

タグノードは設計上どの言語にも属さず（ページと翻訳が同じタグを共有する）、root・source ノードも同様である。したがって1言語に絞り込んだときにこれらが道連れで消えてはならない — **消してしまうと、言語クラスタを繋ぐ唯一の橋を、言語を見比べようとした瞬間に失う**。タグは既存の `showTags` キー、sources は `showSources` キーで別に切る。

#### 次数フィルタは1回だけ計算し、反復収束させない

ハブを隠すと隣接ノードの次数が下がるため、反復すると連鎖的にグラフが崩壊しうるうえ、ユーザーが結果を予測できない。「**いま表示されている範囲での次数**」という定義が一番説明しやすい。下限・上限の両方を持つ（「リンクが少ないものを除外」と「ハブノードを非表示」は同一機構の両端である）。上限フィルタはハブ化したタグノードにもそのまま効くため、タグ側の UI は一括トグルのみで足り、タグ個別のチェックボックスは初版に入れない（`removeTags` による恒久的・外科的な除外は従来どおり YAML で行える）。

#### 適用範囲はグローバルグラフのみ

ローカルグラフ（サイドバー、既定 `depth: 1`）には適用しない。`depth >= 0` の分岐は BFS で `neighbourhood` を構築するため、確定後に要素を削ると経路の途中を抜いて孤児ノードが残る。グローバルグラフ（`depth: -1`）は全ノードから始まるためこの問題を持たない。コントロールバーを置く物理的なスペースがあるのもモーダル側だけであり、制約と設計が一致している。

#### コントロールバーの配置と、素直に実装すると踏む落とし穴2つ

1. **`.global-graph-container` の中には置けない** — `renderGraph()` の `removeAllChildren(graph)` がコンテナを毎回空にするため、バーは `.global-graph-outer` 直下の兄弟にする
2. **しかし兄弟に置くとクリックでモーダルが閉じる** — `documentClickHandler` が `.global-graph-container` / `.global-graph-icon` の外側のクリックで `hideGlobalGraph()` を呼ぶため、除外リストに `.global-graph-controls` を追加する必要がある

また `.global-graph-container` は `position: fixed` + `translate(-50%,-50%)` で中央に浮いているため、バーは同じ矩形に合わせた独自の絶対配置を持つ。**バーの中身はビルド時の TSX ではなく inline スクリプト側で組み立てる** — 言語・型の選択肢一覧は `contentIndex` から導出するものであり、それを持っているのはスクリプト側だけであるため。TSX 側は空のプレースホルダーと i18n ラベルを出すに留める。選択肢一覧は**フィルタ適用前**のノード集合から作る（1言語に絞った後に、戻るための他言語がドロップダウンから消えては困る）。

#### 状態の永続化

`dataset.cfg` の書き換えは SPA ナビゲーション（`nav` イベント）で DOM がサーバー描画のマークアップから作り直されると失われるため、フィルタ状態は localStorage に保持する（同スクリプトは既に `graph-visited` キーで localStorage を使っており前例がある）。

#### バーは作り直さず、値だけを書き戻す（Issue #651）

初版の `renderControls()` は冒頭で `removeAllChildren(bar)` を呼び、バー全体を毎回ゼロから組み直していた。バーのどの操作も `update()` → `dataset.cfg` 書き換え → `showGlobalGraph()` → `renderGraph()` → `renderControls()` という経路を通るため、**1回のクリックやキー入力ごとにバーの DOM が丸ごと差し替わり**、複数選択リストのフォーカスとスクロール位置が毎回失われていた（グラフの再描画とフィルタ結果自体は正しく、壊れていたのは操作の連続性だけである）。

**バーの構造を決める入力は、操作によって変わる設定より狭い**: (1) 選択肢一覧（`collectFacets()` の結果。フィルタ適用前のノード集合から作るため、1言語に絞っても変化しない）と (2) ラベル（サーバー描画の `data-labels` から読む）の2つだけであり、どの option が選択されているか・トグルの状態・次数の上下限は**値**にすぎない。そこで両者から署名（`src/util/controlBar.ts` の `controlsSignature()`。単体テスト付き）を作り、前回と同じならバーを作り直さず各コントロールへ値を書き戻す。

**この書き戻しは省略できない**。作り直しをやめるだけだと、Reset ボタンが `dataset.cfg` を初期化する一方でコントロールの表示が古い選択のまま残り、**表示と実際のフィルタが食い違う** — フォーカスが飛ぶより悪い状態になる。同じ理由で、`update()` はバーの構築時に捕捉した `config` ではなく `graphContainer.dataset["cfg"]` を毎回読み直す（バーが1回のレンダーより長生きするようになった以上、捕捉した値は1回以上前の状態であり、そこへパッチを重ねると直前の変更を黙って巻き戻す）。

**再利用の条件は署名だけではなく、`graphContainer` の同一性も見る**（署名そのものは facet 一覧とラベルだけから作る文字列であり、DOM 要素は含めない — 要素は `controlsSignature()` の外で `===` 比較する）— バーに登録したリスナーはこの要素を閉じ込めているため。SPA ナビゲーションでモーダルのマークアップごと作り直された場合はバー要素自体が新しくなり、状態を引く `WeakMap` が空振りして自然に再構築へ倒れる。テーマ変更（`themechange` → `showGlobalGraph()`）では要素が同じままなので書き戻し経路に入り、`showGlobalGraph()` が localStorage の値を `dataset.cfg` へ再適用した後の設定が表示に反映される。

**ブラウザ上での動作確認は行っていない** — このリポジトリには Quartz 本体が無い（Issue #81）。上記は inline スクリプトのコードからの読み取りに基づき、機械的に検証してあるのは署名の同値性（`src/util/controlBar.test.ts`）に限られる。

### 8.8 サイト概要表示（総ページ数・レビュー済み件数）（Issue #407）

公開 Wiki サイトを訪れた読者が「このWikiには全部で何ページあるか」「そのうち何件がレビュー済みか」を一目で把握できる場所がなかった問題への対応。新規プラグインは追加せず、既存の `wikicommit-banner`（§8.4 の review_status バナーと同一コンポーネント）を拡張した。

```
┌─────────────────────────────────────────────────────────────────────┐
│ 総ページ数: 95  出典と照合: 83  人が読んで確認: 12                    │
│ ページは LLM が生成した時点で公開されます。出典との照合は全ページに   │
│ 対して機械が行い、「人が読んで確認」はそのうち人が最後まで読み、      │
│ 明らかな問題を見つけなかった件数です。人による確認は設計上一部の      │
│ ページのみであり、この数字が総数に達することは目指していません。      │
│ 網羅的な品質保証でもありません。                                      │
│ 「出典と照合」は生成時に、ページの記述をその出典と照合した件数です。  │
│ 照合しているのは出典との一致だけで、網羅性・実在の人物や組織への      │
│ 影響・読者自身の知識との食い違いは見ていません。                      │
└─────────────────────────────────────────────────────────────────────┘
```

> **ラベルと補足文（Issue #664）**: 件数のラベルは `人が読んで確認` / `Read and checked by a person`（i18n の `siteSummaryReviewed`。Issue #664 当時は `人によるレビュー済み` / `Human-reviewed` だったが、Issue #740 が `review_status` の意味を「到達」へ定義し直したのに合わせて改め、Issue #800 が `reviewed` の 2 つ目の表明（読んでいて明らかに変だと思う点は無かった）を足したのに合わせて再度改めた）で、その直下に何を数えた値かを述べる 1 行（`siteSummaryReviewNote`）を置く。`レビュー済み: 0` という裸の数字は正直さの表明として設計したものだが、初見の読者には「誰も関心を持っていないプロジェクト」に読め、同じ数字が意図と逆に働いていた。**数字は隠さない**（隠すと `0` を出すという当初の判断そのものを裏切る）。**参加の呼びかけ・リンクは加えない** — この Wiki は外部レビュアーを募らないため、参加できない相手への呼びかけになる。俯瞰ページ側（§8.8.1）も同じ扱いで、2 つの文言は互いに矛盾させない（root index が俯瞰ページへリンクしているため、読者は続けて両方を見る）。

**データの流れ**: Quartz は静的サイトジェネレータであり、実行時に `.wikicommit/entity/` や `.wikicommit/config.yml` を直接読めない（Quartz コンポーネントに渡される `allFiles` は content/ にミラーされた md ファイルのみで、リポジトリ直下の `.wikicommit/config.yml` はそこに含まれない）。そのため集計は Python 側（ビルド時に一度だけ実行される `.wikicommit/scripts/convert_wikilinks.py`）で行い、結果を build-generated な `content/index.md`（§8.4 の root index。`.wikicommit/entity/` には実体を持たない、常に上書き生成されるナビゲーションページ）の frontmatter に埋め込む:

```yaml
---
title: "Wiki"
review_status: reviewed
wikicommit_page_count: 42
wikicommit_reviewed_count: 30
---
```

- `wikicommit_page_count`/`wikicommit_reviewed_count`: `convert_wikilinks.py` の `main()` が既存の全ページ走査（WikiLink 変換のために元々1回だけ全 `.wikicommit/entity/**/*.md` を走査している）に相乗りして集計する。対象は言語を問わず全ページ（`status: removed` と、Type ディレクトリの `index.md` — `rebuild_index.py` が生成する自動ナビゲーションページ — は除外。`docs/DesignDoc-ScriptSpec.md` の他スクリプトと同じ除外方針）。`review_status: reviewed` のページ数を分子とする。

**表示条件**: `WikiCommitBanner.tsx` は `frontmatter.wikicommit_page_count`/`wikicommit_reviewed_count` の**有無**でサイト概要ブロックを描画するかどうかを判定する（`fileData.slug === "index"` のような Quartz 側のスラッグ命名規約には依存しない — 上記2フィールドを持つページはこの root index.md だけなので、結果的に root ページにのみ表示される。将来 Quartz のスラッグ生成ロジックが変わっても壊れない設計)。

> **`theme` の行は廃止した（Issue #670）**: 当初この概要ブロックには 3 行目として `テーマ: <config.yml の theme>` があり、`convert_wikilinks.py` の `load_theme()` が読んだ値を `wikicommit_theme` フロントマターへ埋め、`WikiCommitBanner.tsx` が描画していた。`load_theme()`・`wikicommit_theme`・i18n の `siteSummaryTheme`・`.wikicommit-site-summary__theme` はいずれも削除済みで、**総ページ数・レビュー済み件数は残す**（数値は言語に依存しないため、この問題を持たない）。
>
> 廃止の理由は「訳されていない」ことではなく、**そもそも読者向けに書かれた文ではない**ことにある。`theme` は `docs/DesignDoc-data.md` §3.3・Issue #564 が定義するとおり **LLM 向けの内容スコープ指示**であり、読む主体は `wikicommit-generate` Pass 2c と `wikicommit-collect` であって読者ではない。値は 1 本しかないため書かれた言語のまま全読者に届き（`wikicommit/decameron-wiki` は `primary_lang: it` の 3 言語サイトで、英語・日本語の読者にはイタリア語の theme が読めなかった）、しかも実際の値には Issue #564 が `.wikicommit/source-policy.md` へ分離したはずのソース選定方針が混在して、生成器への命令文がそのままトップページに出ていた。`theme` を多言語化する案は採らない — LLM 側の消費者は 1 本あれば足りるのに値を増やす一方、読者向けに書かれていない文を訳す作業になるためである。
>
> **読者向けのサイト説明は、読者向けに書かれた別のフィールドとして持つ**。それは後続 Issue（Issue #671）の担当であり、本 Issue は受け皿だけを残さない（Issue #553）ために i18n キーごと削除している — 必要になった時点でそちらが改めて追加する。
>
> **既存の公開サイトへの遡及対応は不要**。`content/index.md` はビルドのたび全上書きされるため次回のデプロイで自然に消える。`config.yml` の `theme` の値自体は書き換えない（LLM 向けの値としては引き続き有効。ソース方針の混在は Issue #564 が「自動移行は行わない」と決着済み）。
>
> **読者向けのサイト説明は `site_description` が持つ（Issue #671）**: `config.yml` の `site_description`（**言語コード → 1〜3 文の文字列**のマッピング。`docs/DesignDoc-data.md` §3.3）を `convert_wikilinks.py` の `load_site_description()` が読み、`generate_root_index()` が**フロントマターではなく本文に**書き出す — 言語選択リストの各行に、その言語の説明を添える形になる。
>
> ```markdown
> ## 言語を選択
>
> - [it](./it/) — Una base di conoscenza dedicata al Decameron di Giovanni Boccaccio.
> - [en](./en/) — A knowledge base on Giovanni Boccaccio's Decameron.
> - [ja](./ja/) — ジョヴァンニ・ボッカッチョ『デカメロン』の知識ベース。
> ```
>
> **バナーに描かせず本文に書く理由は 2 つある**。(1) 値が言語ごとのマッピングであり、`wikicommit_theme` のようなフロントマターの単一文字列には収まらない。(2) 各説明をその言語のリンクの直下に置けば「テーマ:」に相当するキャプション自体が不要になり、バナー i18n が `en-US`/`ja-JP` の 2 ロケールしか持たないという制約に引っかからない — **説明文はどの言語で書かれていてもその言語の読者に届くが、キャプションは届かない**。総ページ数・レビュー済み件数のバナー表示（本節本体）はそのまま残る。
>
> 対象言語は `langs` のみで、うち翻訳対象言語は `existing_lang_targets()` が絞ったもの（実ページが 1 件も無い言語にはリンクを出さないという Issue #190 の安全弁をそのまま踏襲する）。`primary_lang` はこの絞り込みの対象外で `compute_langs()` が常に先頭に置くため、実ページを持たない `primary_lang` にも従来どおりリンクが出る — 説明文はそこに 1 行添わるだけで、リンクを新たに作りはしない。`langs` が 1 つだけで言語選択リストを出さない場合は、`primary_lang` の説明を「Wiki トップ」リンクの直下に 1 行だけ添える。**欠落は静かに落とす** — ある言語の説明が無ければその行に説明を添えないだけ、`site_description` 自体が無ければ従来どおりの出力になる。値の内部の改行・連続空白は単一の空白に潰す（1 行の箇条書きに埋め込む以上、値が持つ空行はその言語選択リストを分断してしまうため）。
>
> **`content/sources/`・`content/overview/` へは展開しない**。この 2 つも言語中立な入口ページだが、説明文を置く必然性が薄い。

<!-- -->

> **言語リストの出所は「`targets` ∪ 実ページを持つ言語」である（Issue #731）**: 上の `site_description` の記述が述べる `existing_lang_targets()` による絞り込みは、`targets` を**狭める**方向にしか働かない。そのため**実ページがあっても `targets` に無い言語は、root index にリンクごと出なかった** — Issue #190 はこの関数を「`targets` にあるが実ページが無い言語がデッドリンクになる」問題への対策として入れたが、その逆は当時の検討に入っていない。
>
> **この状態はパイプラインが自分で作る**。`/wikicommit-translate <page> --lang <lang>` は `config.yml` を触らずに翻訳ページを書き、しかも `targets` が空のときのエラーメッセージ自体が「`--lang <lang>` を指定するか `config.yml` の `targets` を設定してください」と `config.yml` を編集しない側の選択肢を案内している。他にも手書きでページを追加した場合・`primary_lang` を後から変更した場合（旧 primary が未掲載言語になる）・翻訳を作った後に `targets` を削った場合に同じ状態になる。
>
> 壊れているのは**サイトの入口だけ**である。`wikicommit-explorer`・`wikicommit-language-switcher`・俯瞰ページ（§8.8.1 の `言語別ページ数` は `page_stats` 由来）はいずれも published tree から言語を導くため未掲載言語も出るし、`wikicommit-search` は Issue #582 で同じ補正を済ませている。それでも直す価値があるのは、root index が「言語を選ぶ」ためだけに存在するページであり、そこに無い言語は初訪問の読者にとって存在しないのと同じだからである（かつ読者は root index のリンクから俯瞰ページへ行けるので、片方にしか無い言語をその場で見つけてしまう）。
>
> **`compute_langs()` は `targets` に実ページを持つ言語を足した和集合を返す**（置き換えではない）。`existing_lang_targets()` はその言語配下に非 removed な `.md` が 1 つでもあれば通す（`<lang>/<Type>/<slug>.md` の形に解決できないファイルしか持たない言語も含む）のに対し、`published_langs` は解決できて実際に書き出されたページからしか導けないため、置き換えると現状リンクされている言語が落ちうる。両者とも view ツリー（Issue #675）を対象に含むので、そこは差にならない。実在言語は `page_stats` の `lang` から distinct を取って導く — `.wikicommit/entity/*/` のディレクトリ走査では全言語共通アセット置き場 `assets/`（`docs/DesignDoc-data.md` §3.1）を言語として拾ってしまう。Type ディレクトリの `index.md` は `existing_lang_targets()` と同じ理由（最後のページを削除した後に残る `index.md` だけの言語に入口リンクを出さない）で除外し、**書き出しに失敗したページも除外する** — ソースを読めなかったページは `page_stats` には載る（俯瞰ページはこれを数える）が公開ファイルは 1 つも 生成されないため、その言語だけを持つ Wiki で入口にデッドリンクが出てしまう。
>
> **並び順は `primary_lang` → `targets` の記述順 → 発見された言語（ソート順）**。`targets` の順序は書き手が決めたものなので保ち、発見分をその後ろへ回すことで既存 Wiki の表示順は変わらない。
>
> **ビルド時の WARNING は出さない**。「`targets` に無い言語がある」と知らせれば下記の翻訳鮮度の穴に気づけるが、正当な状態（`--lang` で意図的に作った言語）でも毎ビルド点灯し続ける — Issue #562 が「常時点灯する警告は読まれなくなる」として低情報密度ガードを降格させたのと同じ力学に当たる。
>
> **`check_translation_status.py` の `UNTRANSLATED`/`STALE` 判定は変えない**。こちらも `targets` を見るため未掲載言語の翻訳は陳腐化を追跡されないが、それは「翻訳対象として管理するか」という別の問い（`targets` の本来の役割）であり、恒久的に運用するなら操作者が `targets` に足すのが正しい対処である。本節の変更はそれを不要にするものではない。**遡及適用も不要** — root index はビルドのたび上書き生成されるため、既存リポジトリも次のデプロイで自動的に新しい言語リストになる。

<!-- -->

> なお、トップページの単一言語問題は theme だけではない — `ROOT_INDEX_LABELS` / `SOURCE_PAGE_LABELS` / `OVERVIEW_LABELS` は `ja` エントリしか持たず、それ以外の `primary_lang` では英語の既定値に落ちる。この軸は本 Issue の対象外として別に扱う。

<!-- -->

> **多言語 Wiki では件数を言語別にし、フロントマターの 2 フィールドを出力しない（Issue #730）**: 上記の 2 つの数字は `index.md` を除いた**全言語の全ページ**を 1 本に足したものだった。`decameron-wiki`（it/en/ja 各 174 ページ）なら「総ページ数: 522」と出る。実害は 2 つあり、2 つ目の方が重い。
>
> 1. **その数を経験する読者が 1 人もいない**。root index は言語を選ぶ画面であり、選んだ先の Wiki は 174 ページである。翻訳は同じ知識の別言語版であって知識の量ではない。
> 2. **レビュー済み率が翻訳で希釈される**。ja が 100% レビュー済みでも it/en が 0% なら全体では 33% と出る。この数字は Issue #664 で「LLM が書いた直後に公開され、そのうち人が読んだ件数」という信頼ラダーの表明として位置づけ直された経緯があり、翻訳を分母に足すとその表明が実態より悲観的な方向へ一律にずれる。**ページ数だけ言語別にしてレビュー済みを合算のまま残すと、この歪みは残る** — 両方を分ける。
>
> **言語別の件数は本文の言語リンク直下に置く**。フロントマターをマッピング化してバナー側でリストを描く案は採らない — Issue #671 が `site_description` について同じ形で一度却下している分岐であり（言語別の値は 1 つのフロントマター文字列に収まらない／バナーの i18n は 2 ロケールしか持たず、root index は `lang` を持たないため `cfg.locale` 1 本に解決される）、同 Issue が採った形に件数も乗せる:
>
> ```markdown
> ## 言語を選択
>
> - [ja](./ja/)（174 ページ / レビュー済み 174） — 『デカメロン』の知識ベース。
> - [en](./en/)（174 ページ / レビュー済み 0） — A knowledge base on the Decameron.
> ```
>
> `site_description` の em dash 枠はそのまま残し、件数はリンク直後の括弧に置く（Issue #671 の出力形を壊さない）。ラベルは `ROOT_INDEX_LABELS` / `DEFAULT_ROOT_INDEX_LABELS` の `counts` / `counts_one` で、root index の他の chrome と同じく `primary_lang` 固定とする（既存の制約と同じであり新たな悪化はない）。区切り文字を含む文字列全体をラベルに持つのは語順が言語で異なるためで、`counts_one` は英語の `1 pages` を避けるためだけに分けている（日本語は同一文字列）。
>
> **多言語のときは `wikicommit_page_count` / `wikicommit_reviewed_count` を出力しない**。`WikiCommitBanner.tsx` は両フィールドが `number` であることを表示条件にしているため、これだけでサイト概要ブロックが描画されなくなり、**同コンポーネントの変更は不要**。合計は出さない — 出すと「522」と「174×3」が並び、問題視している数を目立たせ続ける。単一言語 Wiki は言語リスト自体が出ない（`len(langs) > 1` ゲート）ため、2 フィールドもバナーの表示も従来どおりとする。
>
> **Issue #664 の補足文は本文側へ移して必ず残す**。上記のとおりフィールドを出力しなければバナーごと消えるが、消えるのは数字だけではなく「その数字が何を数えたものか」を述べる 1 行も同じである。**数字だけ移して注記を落とすのは不可** — Issue #664 が解いた問題（`レビュー済み: 0` が「誰も関心を持っていないプロジェクト」に読める）がそのまま戻る。文言は俯瞰ページ側（§8.8.1 の `reviewed_note`）と揃える（root index が俯瞰ページへリンクしているため、読者は続けて両方を見る）。
>
> **件数は `page_stats` から数える**。`main()` の単一走査が既に各ページの `lang`・`review_status`・`is_index` を積んでおり、`generate_root_index()` はその後に呼ばれるため追加の走査は要らない。Type ディレクトリの `index.md` は他の集計と同じく除外し、view ページ（`.wikicommit/view/<lang>/<slug>.md`）は `lang` 付きで入るため**除外しない** — 俯瞰ページの `言語別ページ数` と同じ数になる。**0 件の言語でも落ちない**: `existing_lang_targets()` は非 removed な `.md` が 1 つでもあれば通し、`primary_lang` はそのフィルタの対象外（`compute_langs()` が常に先頭に置く）なので、`<lang>/<Type>/<slug>.md` に解決できるページを 1 枚も持たない言語がリストに載りうる。どちらも `0` を出す。
>
> **単一言語 Wiki の合計は `page_stats` 由来に切り替えない**。切り替えれば §8.8.1 が「許容する」と書いている差分（`<lang>/<Type>/<slug>.md` に解決できない公開済みページを含むか否か）は消えるが、そのページ群はどの集計にも数えられなくなる — 現状は root index の合計にだけ入っている。本 Issue が直そうとしているのは「多言語で意味を成さない 1 本の数字」であって単一言語の集計母数ではないため、動かす範囲をそこに限る。
>
> **遡及適用の考慮は不要**。root index はビルドのたび上書き生成される build-generated ページなので、既存リポジトリも次のデプロイで自動的に新しい表示になる（本ドキュメント群が通常採る「新旧混在を許容する」方針が当てはまらない数少ない箇所）。

**実装箇所**: `.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-banner/src/components/WikiCommitBanner.tsx`（レンダリング）、`.wikicommit/scripts/convert_wikilinks.py`（集計・埋め込み。`.claude/skills/wikicommit-init/scripts/templates/scripts/` に同一内容をミラー配布）。

> **AI レビューの件数もここに出す（Issue #769）**: Issue #751 は Pass 4 の判定を読者に見せたが、**届いた面が 3 つのうち 2 つだった** — 各ページのバナーと俯瞰ページには出る一方、**トップページには出なかった**。トップページは公開 Wiki の入口であり、しかも Issue #664 が「数字だけだと最悪の読まれ方をする」と判断して注記を足した場所そのものである。3 面のうち、その配慮が最も要る面にだけ届いていなかったことになる。
>
> 欠けていたことの形は「弱める側（Issue #740）だけが反映され、足す側（Issue #750 / #751）が俯瞰ページ止まりになっている」である。注記は「保証ではない」「完成度ではない」とは書くが、**残るページも出典と照合済みである**ことに一言も触れず、初見の読者には「95 枚のうち 12 枚しか何もされていない」と読める。Issue #750 が名指しした「過大表明と過小表明が同時に起きている」の後者にあたり、同 Issue が挙げた 2 通りの直し方（弱める／実際にやっていることを足す）のうち後者がここに届いていなかった。
>
> **0 のときは出さない。これは省略ではなく正確さのためである** — 記録ツリー導入より前に生成された Wiki（Issue #750 は遡及生成しない）と、翻訳ページしかない言語（`wikicommit-translate` の品質チェックは意図的に記録しない）はどちらも「記録が無い」のであって「照合していない」ではなく、`出典と照合 0` はそれを誤って後者として伝える。`generate_overview_page()` が既に `if ai_reviewed:` で同じ扱いをしており、その踏襲になる。副次的に、記録が 1 件も無いリポジトリでは出力がバイト一致のまま変わらない。
>
> **多言語ではサイト全体ではなく言語別にする**（Issue #730 と同じ判断で、理由がより強く当てはまる）。翻訳ページは記録を持たないため、サイト全体で数えると翻訳の枚数で薄まる — #730 が「翻訳がレビュー済み比率を薄める」として分割した、まさにその形である。数字が 3 つ並ぶ密度（`- [ja](./ja/)（12 ページ / 出典と照合 12 / 人が読んで確認 3）`）は読める範囲として許容する。順序は**全数 → 抜取**（俯瞰ページと同じ）。
>
> **注記は別キーにして条件付きで出す**（`ROOT_INDEX_LABELS` の `ai_counts_note`、バナーの `siteSummaryAiReviewNote`）。文言は俯瞰ページの `ai_reviewed_note` に揃え、**照合していないもの**を名指しする — 照合したものだけを述べると、Issue #740 が `reviewed` について直した過大表明を向きを変えて作り直すことになる。**「抜取」「サンプリング」に相当する語は読者向け表示に入れない**（`RISKY:` が実際に選別として機能しているかは実測前であり、語だけ先に出すと形式的な抽出設計の存在を含意する）。
>
> **あわせて「上の数字は」を直した**。`siteSummaryReviewNote` と俯瞰ページの `reviewed_note` はどちらも「上の数字は」「The count above is」と書いており、俯瞰ページでは Issue #751 が同じリストに `ai_reviewed` の行を足した時点で既に指示対象が 2 つあった。ラベル名で指す形（「『人が読んで確認』はそのうち…」。ラベル自体は Issue #800 で改めた）に変えている。`ROOT_INDEX_LABELS` の `counts_note` は Issue #730 の時点で既にこの形であり対象外で、これで 3 つの注記の書き方が揃う。

### 8.8.1 Wiki 全体の俯瞰ページ `content/overview/`（Issue #585）

§8.8 が root index に載せた2つの数字だけでは「このWikiにはどんな知識が集まっていて、何が足りていないか」に答えられない。俯瞰に使える情報は複数の場所に散っており、特に `check_wanted_pages.py` が集計する wanted ページ（他ページから参照されているが実体のない slug）— まさに「不足している部分」そのもの — は `/wikicommit-status` のコンソール出力にしか現れず、運用者が能動的に叩かない限り誰の目にも触れなかった。

`convert_wikilinks.py` の `generate_overview_page()` が `content/overview/index.md` を生成する。`generate_root_index()`（§8.8）・`generate_source_pages()`（Issue #476）と同じ **build-generated ページ**であり、`.wikicommit/entity/` に実体を持たず、ビルドのたび上書き生成される。`generate_root_index()` がこのページへのリンクを出力するため、root index が情報源一覧と俯瞰ページの両方への入口になる。

**掲載する6セクション**:

| セクション | 内容 |
|---|---|
| 全体の数字 | 総ページ数 / **出典と照合済み（AI）率**（Issue #751）/ 人が読んで確認の率 / 型数 / 言語別ページ数 / 翻訳カバレッジ と、その一覧の直下に置く 2 つの補足文（Issue #664 の人間レビュー側と、Issue #751 の AI レビュー側） |
| 知識の中心 | 被リンク数ランキング（ハブページ Top 20） |
| 型別の傾向 | 型ごとの件数・レビュー済み率・平均被リンク数・孤立件数 |
| 知識の不足 | wanted ページ（参照元件数順）・orphan ページ |
| 情報源の内訳 | 種別別・`status` 別・URL ホスト別の件数と、情報源の種別 × 生成されたページの型のクロス集計 |
| タグ | 頻度ランキング |

型別件数は「全体の数字」に重複して並べず「型別の傾向」の表が兼ねる（同じ数字を2か所に持たない）。ランキングはすべて Top N で打ち切る — 初版は1枚の `overview/index.md` に `##` セクションを並べる構成であり、複数ページへの分割は「1枚に収まらなくなってから」別 Issue で扱う。

**集計はすべて既存の走査に相乗りする**。`main()` の全ページ1回走査（WikiLink 変換のために元々行っているもの）で各ページの `type` / `lang` / `tags` / `review_status` / 発リンクを蓄積し、ソース側の内訳は `generate_source_pages()` の管理ファイル走査に相乗りする。発リンクは `convert_file()` が置換パスで既に `WIKILINK_RE` を走らせているため、その戻り値として受け取る（`check_orphans.py` / `check_wanted_pages.py` が各自の全再走査で同じグラフを組み立てているのに対し、ビルド内で3つ目の走査を足さない）。ソース × 型のクロス集計は `_write_source_page()` が実際にリンクした `generated_pages[]` の実体から算出する — 存在確認・`status: removed` 除外というフィルタをリンク生成側と共有し、2つ目の写しがドリフトしないようにする。

**なぜ build-generated か**: 集計結果はビルドのたび再計算される値であり、人間のレビュー対象ではない。`.wikicommit/entity/` に置くと `review_status`・レビュー追跡 Issue（Issue #313）・`wikicommit-merge` の品質ゲートにすべて乗り、「毎ビルド変わる数字にレビュー追跡 Issue が立つ」状態になる。root index が同じ理由で `review_status: reviewed` を明示している前例に倣う（`WikiCommitBanner` の未レビュー警告はフィールドが無いと `pending` にフォールバックするため、明示が必要）。`.wikicommit/report/` のような第3のトップレベルディレクトリも採らない — 主要スクリプト群がいずれも `.wikicommit/entity/` 決め打ちであり、全スクリプトに分岐が必要になる。

**副作用の有無で `/wikicommit-status` と境界を引く**: `check_ingest_freshness.py` は管理ファイルに `status: outdated` を書き戻すため**ビルドからは呼べない**（CI がリポジトリのファイルを書き換えることになる）。`check_expires.py` も、判定に使う「今日」がビルド時点で凍結し再ビルドまで古い表示が残るため載せない。読み取り専用の集計のみを overview に置き、書き戻しを伴うもの・時刻依存のものは運用者がオンデマンドで実行する `/wikicommit-status` 側に残す。

> **AI レビューのサイト単位の数はここに置く（Issue #751）**: ページ単位のバナーは「照合を通過した事実」だけを出し、**指摘件数は出さない** — 「指摘 2 件」はそのページが悪いように読めるが、実際には指摘を受けて直っているので意味が逆になる。件数が意味を持つのは集約された後であり、その置き場がこの節である。
>
> 出すのは 3 つ: 有効な判定を持つページ数 / 総ページ数、照合したモデルの一覧、そして**指摘を受けて書き直された箇所の総数**（`ai_findings`。ページ数ではない — 3 回捕まったページは 1 回のページより、この検査に歯があることをよく示す）。集計は `page_stats` の `ai_review` に相乗りし、`convert_file()` が publish 時のスタンプに使うのと**同じ 1 回のルックアップ**を読む — 2 度引くと、バナーが出しているページ集合と俯瞰ページが数えている集合が食い違いうる。
>
> **`reviewed` キーを流用してはならない**。Issue #664 はあのラベルを「人による」と言い切る形に直したものであり、機械の数をそこへ載せると #664 が消した曖昧さがそのまま戻る。`ai_reviewed` / `ai_reviewed_note` / `ai_findings` を新設した。
>
> **有効な判定が 1 件も無い Wiki では行ごと出さない**（`0 / 95` とは書かない）。ゼロは「照合が走って全部落ちた」と読めるが、実際には走った上で記録が残っていない（Issue #750 — 記録はさかのぼって作れない）。**補足文も同時に出し入れする** — 数字だけ出して「何を照合したか」の 1 行を落とすと、Issue #664 が人間レビュー側で解いたのと同じ問題（数字だけが独り歩きする）を機械側で作ることになる。

**集計の単位はページではなく `Type/slug` キー**。WikiLink は言語を持たないため、ある原文ページとその翻訳は1つのノードとして数える。ページ単位で数えると、リンクが1本も増えていないのに Wiki が2言語目を持った瞬間に全ての数字が倍になる。ハブ行・参照元リンクのようにノードを1ページで代表させる箇所では、`primary_lang` のページを優先して選ぶ。

**`check_orphans.py` / `check_wanted_pages.py` との意図的な3つの差分**（同じリンクグラフを別の目的で見るため、数字が一致しないことがある）:

- **`status: removed` のページは発リンクを寄与しない**。公開されないページのリンクは読者が辿れないため、公開サイトの俯瞰としてはこちらが正しい。結果として「removed ページからのリンクだけで参照されているページ」は、overview では orphan・`check_orphans.py` では被参照、と分かれうる。
- **slug が別の Type に実在する wanted キーは wanted に載せない**。Issue #563 が確立したとおりそれは Type セグメントの誤りであり、読者に「まだ書かれていないページ」として提示すると既存ページの重複を作らせてしまう。この種の指摘は `check_wanted_pages.py` の `TYPE_MISMATCH` が運用者向けに担う。同様に、removed ページへのリンクも wanted には載せない（`check_wikilinks.py` が ERROR として別途ブロックする）。
- **自己リンクは被リンクに数えない**。唯一の被リンクが自分自身であるページは overview では orphan になる（`check_orphans.py` は被参照として扱う）。

なお `<lang>/<Type>/<slug>.md` の形に解決できない `.md` はキーを持てないため overview のどの集計にも入らない一方、root index の `wikicommit_page_count`（§8.8）には数えられる。パイプラインの他の部分が Wiki ページとみなさない形のファイルであり、この差分は許容する。

wanted ページは定義上リンク先が存在しないため、`[[Type/slug]]` としてではなくコードスパンのキー名 + **参照元ページへのリンク**として描く。カスタム型の型名は publish 時のフラット化（Issue #576）に合わせて `custom/` を落として表示する。見出し・ラベルは `ROOT_INDEX_LABELS` / `SOURCE_PAGE_LABELS` と同じ「`primary_lang` をキーにした辞書 + 英語デフォルト」パターン（§8.9.1）に従い、LLM は関与しない。

**スコープ外**: Wiki 全体の傾向を LLM が論述するページは**作らない方針に確定した**（鮮度追跡の仕組みと型名の選定という2つの未確定な設計判断を伴う一方、実際に欲しかった内容は決定論的な集計で表現できるため）。特定の着眼点に基づく合成は `/wikicommit-synthesize` の担当。build-generated ページは `.wikicommit/entity/` に実体を持たないため `search_index.py`（FTS5）の走査対象外で、`/wikicommit-ask` / `/wikicommit-search` には出ない（ブラウザ側の Quartz 標準検索にはビルド成果物として出る）— Wiki の状態を LLM に尋ねる用途は `/wikicommit-status` が担う。

**実装箇所**: `.wikicommit/scripts/convert_wikilinks.py`（`generate_overview_page()`・`OVERVIEW_LABELS`・`url_host()`。`.claude/skills/wikicommit-init/scripts/templates/scripts/` への symlink 経由で配布テンプレートにも反映される）。

### 8.9 読者向けに表示されるフィールドの一覧（Issue #509）

`.wikicommit/entity/<lang>/<Type>/<slug>.md` のフロントマターは複数の Quartz コンポーネントに分かれて読者に表示される。field 単位でどのコンポーネントが担うかを一覧する:

| フィールド | 表示コンポーネント | 節 |
|---|---|---|
| `title` | ページ見出し（`wikicommit-properties` 自身ではなく Quartz 標準の article-title 等） | — |
| `review_status`・`generated_at`・`generated_by`・`wikicommit_page_count` 等（サイト概要） | `wikicommit-banner` | §8.4・§8.8 |
| `sources`（+ `translated_from` 経由の継承） | `wikicommit-sources` | §8.10 |
| `sources[].license` ＋ 改変告知の固定文言 | `wikicommit-sources` | §8.10 |
| `derived_from`（合成ページの出自。+ `translated_from` 経由の継承） | `wikicommit-sources` | §8.10.1 |
| `description`/`tags`/`aliases`/`properties`（Schema.org 型固有プロパティ、Issue #495。`quartz.config.yaml` の `includedProperties` で選定） | `wikicommit-properties` | 本節 |
| `type`・`properties.*` の Schema.org マッピング（`<head>` への JSON-LD 埋め込み。UI 上は不可視） | `wikicommit-jsonld` | §8.3 |
| `lang`・`wikidata`・`sameAs` 等 | — （現状どのコンポーネントも UI に表示しない。本 Issue のスコープ外） | — |

Issue #495 が `properties:` にネスト化するまで、型固有の Schema.org プロパティ（`description`/`affiliation`/`jobTitle` 等）は `wikicommit-jsonld` が読む JSON-LD 埋め込み（クローラー向け、UI 上は不可視）以外のどこにも表示されておらず、`generated_at`/`sources` 等の WikiCommit 独自フィールドは見えるのに Schema.org 語彙側のフィールドだけ読者から隠れているという非対称な状態だった。本 Issue が解消するのはこの非対称のうち `properties:` の可視化のみで、上表最終行の `wikidata`/`sameAs` 等（`docs/DesignDoc-data.md` §4.1 の「外部識別子」フィールド）は引き続き UI 上非表示のまま残る — これらを表示対象に含めるかどうかは `includedProperties` の設定範囲であり、本 Issue とは別の判断が必要なため対象外とした。

`wikicommit-properties`（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-properties/`）はこの非対称を解消する。Quartz v5 の必須プラグイン `github:quartz-community/note-properties`（フロントマター解析そのものを担う。無効化不可）を、他の `wikicommit-*` プラグインと同じ自前ディレクトリへのフォーク方式（`docs/DesignDoc-skills.md` §11 参照）で `wikicommit-properties` として取り込み、`quartz.config.yaml` テンプレートの参照を `github:quartz-community/note-properties` からこちらへ差し替えた。アップストリームからの実行時の挙動の変更点は次の1点のみ: `getVisibleProperties()`（表示対象プロパティの選定ロジック）が、選定後の値がプレーンオブジェクトであれば1階層だけ展開し、そのキーをトップレベルの行と同格で表示する。これにより `properties:` ブロック自体は1行の生 JSON ダンプとして表示されるのではなく、`description`/`affiliation`/`jobTitle` 等の個々のキーが他のトップレベルフィールドと見分けがつかない行として並ぶ。展開時に、同名のキーが既に選定済み（トップレベルフィールド、または `includedProperties` 内でより先に処理された別のオブジェクト）であれば上書きしない — カスタム型（`docs/DesignDoc-data.md` §5.3。標準型と異なり `domainIncludes` 検証の対象外）が誤って `properties.tags` のような WikiCommit 構造フィールドと同名のキーを宣言した場合に、ページの実際の `tags` を静かに破壊しないためのガード。WikiLink 由来の値（`[[Type/slug]]` 形式）・配列値の描画ロジックはアップストリームのものをそのまま使う（変更不要 — 展開後の値は文字列/配列として扱われ、既存のリンク描画がそのまま効く）。ネスト2階層以上のフラット化には対応しない（WikiCommit のスキーマ設計上、`properties:` の値がさらにオブジェクトになることは想定していない）。

`quartz.config.yaml` テンプレートの `includedProperties` に `properties` を追加し、この展開ロジックの対象に含めている。プロパティキー名の表示ラベル整形（`jobTitle` → "Job Title" のような人間可読化）は行わない — Schema.org 語彙自体が英語ベースであることは CLAUDE.md の既存方針（キーはすべて英語）と整合しており、無理に和訳・整形しない。

### 8.9.1 公開サイトの言語の境界: 識別子は言語中立・UI chrome はローカライズ（Issue #571）

公開サイトでは、`convert_wikilinks.py` の `SOURCE_PAGE_LABELS`・`ROOT_INDEX_LABELS` が `ja` 訳を持ち「情報源一覧」「種別」「元リンク」等と表示される一方、Type（`Person`・`Place`・`GovernmentService` 等）は英語のまま表示される。パイロットのユーザーから「Schema.org のタイプは英語のままなのに、ここだけ翻訳する理由が分からず変な感じ」という指摘があった。

**現状維持とし、境界を明文化する**（Issue #571 の対応方針 (b)）。境界はこう引く:

| | 例 | 扱い |
|---|---|---|
| **識別子** | Type セグメント（`Person`）・slug（`yamada-taro`）・WikiLink | **言語中立の英語**。翻訳しない |
| **UI chrome** | ページ見出し・ラベル・ナビゲーションの語 | `primary_lang` にローカライズする |

識別子側は翻訳できない — WikiLink・slug・Type は言語中立の英語識別子として設計されており（CLAUDE.md の WikiLink 節）、`ja` ページの Type を和訳すると `[[Person/yamada-taro]]` が解決しなくなる。つまり選べるのは「UI chrome も英語に統一する」か「現状のまま」かの二択であり、前者は日本語 Wiki の読者にとって明確な後退である。中途半端に見えるのは事実だが、**識別子を翻訳できないことの帰結**であって、UI chrome を訳す判断の誤りではない。

Issue #405（`.wikicommit/source/` の見出しラベルを `primary_lang` によらず固定の英語にした）とは対象が異なるため、そのまま流用はできない — あちらは非公開の内部管理ファイルであり、こちらは読者向けの公開ページである。

### 8.9.2 chrome の言語を決めるのは `quartz.config.yaml` の `locale`（Issue #771）

§8.9.1 が「UI chrome は `primary_lang` にローカライズする」と定めた一方、**その値が chrome を描くプラグインへ届く経路は用意されていなかった**。公開サイトの文言を出す仕組みは 3 系統あり、locale の決め方もロケール数も揃っていない:

| | locale の決め方 | ロケール数 |
|---|---|---|
| WikiCommit 自前 3（banner / sources / properties） | **`frontmatter.lang` 優先** → `cfg.locale` → `en-US`（Issue #378） | 2（en-US / ja-JP） |
| WikiCommit 自前 1（language-switcher） | `cfg.locale` のみ | 2 |
| コミュニティ由来 3（explorer / graph / search） | `cfg.locale` のみ（サイト全体で 1 つ） | 30 |

そして `/wikicommit-init --quartz` が配る `quartz.config.yaml` は `locale: en-US` を**プレースホルダではない固定値**として持ち、`init.py` はここを置換していなかった。結果、**日本語 Wiki を既定の設定で公開すると、ページ本文とバナーは日本語・サイドバーと検索とグラフは英語**になる。ja-JP の訳は 3 プラグインすべてに存在しており、翻訳が無いのではなく**到達していなかった**。

Issue #378 が直したのは逆向きの症状（サイト locale が `ja-JP` だと `en/` の翻訳ページにも日本語キャプションが出る）で、対象は自前プラグインだけだった。あの修正以降 WikiCommit が書いた面は常に正しく見えるため、見落とされたのは同じページの**周りの chrome** である。

**対応は `init.py` が `primary_lang` から `locale` を導出することに限る**。テンプレートに `{LOCALE}` プレースホルダを置き、`QUARTZ_LOCALE_BY_PRIMARY_LANG`（ISO 639-1 → BCP 47。値はコミュニティ由来 3 プラグインが実際に持つ 30 ロケールから採る）で置換する。対応が無い言語は `en-US` に据え置く — chrome はどのみち英語になるので、無い タグを書けば config だけが嘘をつく。**この表は自前プラグインの `LANG_TO_LOCALE`（自前プラグインが訳を持つ 2 言語）とは別物**であり、同じ名前にすると同期すべき 2 つに見えるため名前を分けてある。`tests/test_init.py` が、表の全エントリのロケールファイルが 3 プラグインすべてに実在することを検証する（上流でロケールが消えると、ビルド時には黙って英語へ落ちるため）。

**残る非対称は設定では解けない**。`locale` は 1 サイトに 1 つで、コミュニティ由来 3 つは per-page に切り替えられないため、多言語 Wiki では翻訳ページの chrome が原文言語のまま残る:

| `locale` | ja ページ | en ページ | it ページ |
|---|---|---|---|
| `en-US` | バナー ja / chrome **en** | 一致（en） | バナー en / chrome en |
| `ja-JP` | 一致（ja） | バナー en / chrome **ja** | バナー **ja** / chrome ja |
| `it-IT` | バナー ja / chrome **it** | バナー en / chrome **it** | バナー **en** / chrome it |

3 行目の it 列は、自前プラグインが `it` のロケールを持たないため**バナーだけ英語**になることを示す。2 行目の it 列は、`LANG_TO_LOCALE` を素通りした結果 `cfg.locale` がそのまま採用され**イタリア語ページに日本語のバナーが出る**ことを示す。この非対称は `quartz.config.yaml` の `locale` 行にコメントとして書いた（この値が何を決めて何を決めないか。それまでこの行には説明が 1 文字も無かった）。

**採らなかった案**: (a) コミュニティ由来 3 つに `frontmatter.lang` を読ませる — 全セルが一致するが、ローカルに取り込んだコピーの描画ロジックを改造することになり、上流との差分を恒久的に抱える（Issue #228 の `LANG_SEGMENT_RE` は正規表現 1 本の同期であって描画ロジックではない）。(b) 自前 4 プラグインを 30 ロケールに揃える — 訳文の調達手段が無く、機械翻訳した UI 文字列を読者向けの文言として配ることになる（Issue #671 が `theme` を読者向けに流用しないと決めたのと同じ線）。(c) 自前プラグインへロケールを先回りして足す — Issue #553 の「消費者と同時に足す」に従い、その言語の Wiki が現れた時点で**訳文と一緒に**足す（`LANG_TO_LOCALE` と `locales` の**両方**に足す必要がある。片方だけだと `resolveLocale` が `cfg.locale` へ落ち、上表 2 行目の症状を再現する）。(d) `wikicommit-language-switcher` に `resolveLocale()` を導入する — 同プラグインが並べる言語名は自言語表記（`ja: "日本語"`）で読者のロケールに依存せず、`cfg.locale` に従うのは見出しラベルだけである。per-page 化は (a) と同じ問い

**既存の公開済みリポジトリには自動では届かない**。`quartz.config.yaml` は `update: review` であり再 init でも `/wikicommit-update` でも上書きされない。運用者が差分を見て `locale` の 1 行を取り込む。

### 8.10 帰属・ライセンス・改変告知の表示（Issue #558）

WikiCommit は外部ソースを取り込み、LLM が要約・再構成したページを公開サイトとして配信する。この配信自体が頒布行為であり、多くのソースのライセンス（CC BY-SA 4.0 等）は出典の提示だけでなく **ライセンス自体の表示** と **改変した旨の告知** を求める。Issue #558 以前はどちらを表現する場所も存在せず、`WikiCommitSources` は出典リンクだけを描画していた。

#### 4層構造と、①層を主役とする理由

| 層 | 何を書くか | 実装先 | 現状 |
|---|---|---|---|
| **① ページ単位**（法的な主役） | 出典リンク ＋ ライセンス名（＋ URI） ＋ 「要約・再構成した」旨 | `sources[].license` → `WikiCommitSources` | **実装済み**（Issue #558） |
| ② サイト全体 | ページごとに条件が異なる旨と、各ページの出典欄を見よという案内 | `convert_wikilinks.py` が生成するルート index と `content/sources/index.md` | **実装済み**（Issue #645。フッターではない — 後述） |
| ③ リポジトリ | コードとコンテンツのライセンス分離 | ルートの `LICENSE` | 補助。**自動生成しない**（後述） |
| ④ README | 人間向けの要約と参照先 | `README.md` | **案内のみ**（Issue #645。`print_next_steps.py` の `_LICENSING_STEP` が推奨文面ごと提示する。自動生成・自動追記はしない） |

①を主役に据えるのは、読者が検索・外部リンクから個別ページに直接着地するためである。ルートの `LICENSE` やサイトフッターは多くの読者の目に触れないまま終わる一方、①はページが頒布される単位そのものに帰属表示を伴わせる。逆に①さえ正しければ②〜④は補助で足りる。②④に着手した Issue #645 でもこの位置づけは変えていない — ②④は①の代替ではなく上乗せである。

#### ① 層の実装

`WikiCommitSources`（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-sources/`）が、出典1件ごとに次の2つを描画する。

1. **ライセンス名**: そのソースの `sources[].license`（`docs/DesignDoc-data.md` §4.1・§4.3）が非空のときのみ、出典リンクの直後に括弧書きで併記する。値が Creative Commons 系の SPDX 識別子（`CC-BY-SA-4.0`・`CC0-1.0` 等）であれば、識別子の**形から** deed URL を導出してリンクにする（対応表を持たないため、将来の CC バージョンにも保守なしで追従する）。それ以外の識別子（自治体独自の利用規約・`PDL-1.0`・`all-rights-reserved` 等）はプレーンテキストとして表示する。ライセンス名 ＋ URI という形は CC BY-SA §3(a) が求める「ライセンスの明示」に対応する
2. **改変告知の固定文言**: 出典リストの直下に、「このページは出典を LLM が要約・再構成したものであり逐語転載ではない」「表示されているライセンスは併記された出典に対するものであってページ全体に対するものではない」を表示する（`i18n` の `adaptationNotice`。ページの `lang` に応じて日本語／英語）。唯一の例外は**出典が `type: manual` のみのページ**で、この種別は「人間が直接書いた」ことを記録するもの（`docs/DesignDoc-data.md` §4.4）であるため、LLM が要約・再構成したという1文目はそのページでは事実に反する。この場合は2文目だけの短い文言（`licenseScopeNotice`）に切り替え、ライセンスを1件も表示していなければ何も出さない。`type: manual` 以外の出典が1件でもあれば通常の文言に戻る

あわせて `convert_wikilinks.py` の `generate_source_pages()` が、`content/sources/` 配下の公開ソースページ（Issue #476。管理ファイル1件につき1ページ）にも管理ファイルの `source.license` を1行として描画する — 同じ値が「ページから見た出典」と「出典そのもののページ」の両方で一致して見えるようにするため。値が空欄・欠如の場合は行ごと省略する（空行を描画すると「ライセンスが記録されている」と読めてしまうため。ページ側の空文字列を `validate_frontmatter.py` が弾くのと同じ理由）。

改変告知をページごとに記録せず固定文言にしたのは、WikiCommit が**生成する**ページが例外なく LLM による要約・再構成であるため、「改変した」がそれらのページで一律に真であり、個別のブックキーピングが情報を増やさないからである（上記の `type: manual` のみのページは、そもそも生成されたページではないという点でこの前提の外にある — 判定に必要な情報は `sources[].type` に既にあり、追加の記録は要らない）。

2文目（ライセンスの適用範囲の限定）を固定文言に含めているのは、1ページが複数ソースを統合しうる（`action: update` による統合は WikiCommit の中核的な挙動）ため、ソース行に併記されたライセンスをページ全体への宣言と読まれると誤りになるからである。ページ全体に対して単一のライセンスを主張する仕組みは、本 Issue では意図的に用意していない。

#### ②層をフッターに置かなかった理由と、④層の着地点（Issue #645）

**② サイト全体**: 実装先を `quartz.config.yaml` の footer プラグインではなく、`convert_wikilinks.py` が生成する2枚のページ（ルート `content/index.md` と `content/sources/index.md`）にした。理由は 2 つある。

- **footer プラグイン（`github:quartz-community/footer`）は `links`（ラベル → URL のマッピング）しか受け取らない**。任意の散文を出すにはフォークするか専用コンポーネントを書くことになる。WikiCommit は既に 6 プラグインを self-vendor しているのでフォーク自体は前例のある手段だが、1 プラグイン ＝ npm パッケージ 1 つ（`dist/` のコミット・vitest・eslint・`tsup.config.ts`）であり、2 文の注意書きに対して釣り合わない
- **フッターに「リンク」だけを置く案も成立しない**。`links` の値は絶対 URL が前提で（既存エントリが `{REPO_URL}` ＝ GitHub リポジトリの完全 URL）、一方 `baseUrl` は GitHub Pages のプロジェクトページでは `<owner>.github.io/<repo>` になる。ルート相対の `/sources/` は**既定のデプロイ形態でちょうど壊れる**。公開サイトの URL は `init.py` の時点では分からない（`init.py` が受け取るのは `--repo-url` ＝ GitHub リポジトリの URL であって Pages の URL ではない）

②が対象とする読者 — 個別ページに着地するのではなくサイト全体を眺める読者 — が実際に到達するのはルート index と `content/sources/` である。この 2 枚はいずれも `convert_wikilinks.py` が生成する WikiCommit 所有のページであり、散文を自由に書ける。文面の本体は `content/sources/index.md`（「どこから来た情報で、どんな条件か」を問う読者が行き着く先）に 1 か所だけ置き、ルート index には要点だけを述べた短い但し書きを置く（但し書き自体はリンクを持たない — `content/sources/index.md` へはその直前に並ぶ `sources` リンクが導く）。ルート index では、2 つの入口リンク（`sources` と `overview`）の**後ろ**に置く — 行き先の提示ではなくサイト全体への但し書きであるため。

`content/sources/index.md` の文面は**登録ソースが 0 件でも表示する**。「この Wiki がどう作られているか」についての記述であって、現在の内容についての記述ではないため。あわせて「ライセンスが記録されていない ＝ 制約が無い」と読まれないよう明示する（`docs/DesignDoc-data.md` §4.1 の「不明を空文字列で表さない」と同じ線引きを、読者側の表示でも保つ）。

インデックス・ナビゲーションページに①の帰属表示が出ないこと自体は欠落ではない — これらのページはページタイトルとリンクだけで構成され、第三者の文章を含まないため、法的に required な表示は元から無い。②が足すのは法的な充足ではなく**方向づけ**である（「単一のライセンスがあるはず」と読まれることを防ぐ）。

**④ README**: 自動生成・自動追記のいずれも行わない。Issue #282 が README.md を display-only（エージェントが編集しない）と定めているため、この層で採れる着地点は案内だけになる。`print_next_steps.py` の `_LICENSING_STEP` に README 用の箇条書きを 1 つ足し、**そのまま貼れる推奨文面まで含めて**提示する形にした（「ライセンスについても書いておきましょう」という抽象的な助言では、書く人が何を書けばよいか分からないまま終わる）。既存の `_README_STEP_WITH_URL`（公開 URL へのリンク追加を「書かずに勧める」）と同じ形であり、方針として一貫する。

#### `init.py` が `LICENSE` / `README.md` を生成しない理由

**生成しない**（Issue #558 の完了条件のうち「要否の決定」に対する結論）。WikiCommit リポジトリは、コード（`.wikicommit/scripts/`・`quartz-plugins/`）と、第三者ソース由来のコンテンツ（`.wikicommit/entity/`）という性質の異なる2つを同居させる。後者に単一のライセンスは存在しない — Wikipedia 由来のページは CC BY-SA、自治体サイト由来のページはその自治体の利用規約、学会論文由来のページは通常の著作権（そもそも再許諾する権利が無い）と、ページごとに異なる。ここでルートに `LICENSE` を1枚置いて「この Wiki は CC BY-SA 4.0」と宣言すると、**運用者が持っていない権利を許諾したことになる**。「ファイルが無い＝全権利留保」という GitHub の既定解釈にも問題はあるが、誤った許諾を自動生成するよりは安全側である。

代わりに `wikicommit-init` の「Next steps」最終項が、(a) コードのライセンスは通常の OSS の選択として運用者が決めること、(b) コンテンツのライセンスはページごとに `source.license` で記録すること、の2つを分けて案内する（`print_next_steps.py` の `_LICENSING_STEP`）。`README.md` は Issue #282 が display-only（エージェントが編集しない）方針を確立済みのため、本 Issue でも新規生成・自動編集のいずれも行わない。

#### WikiCommit が法的判断を代行しない線引き

ツールの責務は「記録する場所を用意し、記録された内容を表示する」ことに限定する。具体的には:

- `add_source.py` の既知ドメイン対応表（`docs/DesignDoc-data.md` §4.3）は、そのサイトが自ら明示しているライセンスを登録時の**初期値**として埋めるだけで、法的な確定ではない。個別ページが別条件を宣言していること（引用文・画像・転載記事等）はありうる
- `validate_frontmatter.py` は `sources[].license` の値の中身を検証しない（空文字列のみ弾く）。SPDX 語彙への照合も、ソースの実際の条件との突合も行わない
- LLM にライセンスを推定させる経路は設けない（Issue #558 の対応方針 2(b) を採らなかった）。ソースのライセンスは事実確認の対象であって、生成物の一部ではない
- 表示側も、記録された値をそのまま出すだけで、その値が当該利用を許すかどうかは判断しない

既に公開済みのパイロットリポジトリ（`wikicommit/decameron-wiki`・`wikicommit/ai-driven-dev-wiki` 等）への遡及適用は行わない。`sources[].license` は任意フィールドであり、欠如は「この機能追加より前に生成された」ことを意味する — 本ドキュメント群が繰り返し採ってきた「自動移行せず新旧混在を許容する」方針（`docs/DesignDoc-data.md` §4.3 等）に従う。既存リポジトリで表示させたい場合は、管理ファイルとページの `license` を手で追記すれば次回ビルドから反映される。

---

### 8.10.1 合成ページの出自表示（`derived_from`。Issue #587）

WikiCommit のページは出自フィールドを3通り持ち、ページごとに排他である（`docs/DesignDoc-data.md` §4.2）: 通常ページの `sources`、翻訳ページの `translated_from`、合成ページの `derived_from`（`/wikicommit-synthesize`。Issue #283）。このうち**合成ページだけ読者向けの表示経路が1つも存在しなかった** — `WikiCommitSources` の `resolveSources()` は「自身の `sources` → `translated_from` 経由の継承」しか見ず、どちらも無ければ空を返してボックスごと消えていた。`quartz.config.yaml` の `includedProperties` にも `derived_from` は含まれず、`content/sources/` ツリーは `.wikicommit/source/` の管理ファイルから構築される（Issue #476）ため外部ソースを持たない合成ページは構造的に入らない。

結果として読者から見た合成ページは**出自の表示が何も無いページ**になり、「`sources` を書き忘れた不備のあるページ」と外形上まったく同じだった。しかも合成ページは既存ページの記述を再構成したものであるため、出自の提示が最も必要な種別である。

**新規プラグインは追加せず `wikicommit-sources` を拡張した**（Issue #407 が `wikicommit-banner` を拡張してサイト概要を足したのと同じ形）。`resolveSources()` を `resolveProvenance()` に置き換え、`sources`（従来どおり）と `derivations`（新規）の2つを返す。どちらかが非空なら出典ボックスを描画する。`derived_from` は `sources` と型が異なる（`{path, source_commit}` の配列）ため同じ配列に混ぜず、専用の見出し文（「このページは Wiki 内の以下のページを合成したものです:」）付きの別リストとして描く。

**出自ページが不在・`status: removed` の場合も、そのエントリを列挙する**（リンクは付けず「削除済み／未公開」と添える）。`translated_from` の既存分岐（親が `removed` なら継承しない）とは扱いを変えている — あちらは*継承元*の話であり継承しないという判断が成立するが、`derived_from` のエントリはそのページの出自そのものであり、黙って落とすと**本節が解消しようとしている状態（出自が1行足りないページが、最初から出自を持たないページと見分けがつかない）を部分的に再現してしまう**。複数エントリのうち一部だけが欠けるケースがあるため、この差は実際に起こりうる。

**翻訳ページからの継承も `derived_from` に広げた**。合成ページの翻訳は `translated_from` を持ち、その親の出自は `sources` ではなく `derived_from` にある。継承を `sources` だけに留めると、翻訳ページで本 Issue とまったく同じ「何も表示されない」状態が再現する。

**パス → リンクの変換は `translated_from` と共有する**。`derived_from[].path` は `translated_from` と同じ「リポジトリルートからの相対パス」形式のため、同ファイル内の変換関数をそのまま使う（Issue #477 の `.wikicommit/wiki/` 旧プレフィックス後方互換・Issue #576 の `custom/` フラット化を含めて）。用途がフィールド1つに閉じなくなったため `translatedFromToRelativePath()` → `entityPathToRelativePath()` に改名し、`WikiCommitBanner.tsx` の複製も同時に改名した（`docs/DesignDoc-data.md` §3.1 の消費箇所一覧に追記済み）。

**陳腐化（`STALE`）は読者に見せない**（Issue #587 の判断事項）。Quartz は静的サイトのため `git log` を実行できず、判定するにはビルド時に Python 側（`convert_wikilinks.py`）で計算してフロントマターに埋め込む必要がある（§8.8 のサイト概要と同じデータの流れ）。実装可能だが採らない — `source_commit` の不一致は「出自ページがそれ以降に更新された」だけを意味し、**その更新が合成ページの記述に影響したかどうかは判定していない**。出自ページの誤字修正1つで読者に「この記述は古い」と示すことになり、繰り返せば表示そのものが無視されるようになる。`check_derivation_freshness.py` と `/wikicommit-status` が運用者向けの検出手段として引き続き担い、運用者は必要なら合成ページを作り直す。読者が出自ページを辿れること自体は本節の実装で達成される。

**スコープ外**: `wikicommit-jsonld` への `derived_from` のマッピング（Schema.org 語彙への対応付けは別の判断を要する）、合成ページを `content/sources/` ツリーに載せること（同ツリーは `.wikicommit/source/` 管理ファイルを走査対象とする設計）。

### 8.11 ブラウザタブ・OGP のタイトルにサイト名を載せる（`pageTitleSuffix`。Issue #679）

Quartz 本体の `Head.tsx` は `<title>` を次のように組み立てる。

```tsx
const titleSuffix = cfg.pageTitleSuffix ?? ""
const title =
  (fileData.frontmatter?.title ?? i18n(cfg.locale).propertyDefaults.title) + titleSuffix
```

つまり **`<title>` は「そのページの frontmatter `title`」＋「`pageTitleSuffix`」だけで決まり**、同じ値が `og:title` と `twitter:title` にもそのまま入る。`pageTitleSuffix` の既定値は空文字列だったため、**どのページのタブにもサイト名が出ていなかった**。

| フィールド | 読者に届く場所 |
|---|---|
| `pageTitle` | 左サイドバーの `PageTitle` コンポーネントと、OGP の `og:site_name` |
| `pageTitleSuffix` | ブラウザのタブ（`<title>`）・`og:title`・`twitter:title` |

**`pageTitle` はこの 3 つに一切入らない**。したがってサイト名を既に `pageTitle` として持っていても、タブに載せる経路は `pageTitleSuffix` しか存在しない — Quartz 自身のドキュメントも同フィールドを "a string added to the end of the page title. This only applies to the browser tab title, not the title shown at the top of the page" と説明している。

**波及範囲はトップページに限らなかった**。発見の契機は「トップページのタイトルが `Wiki` としか出ない」という報告だったが、原因は `title` が総称語であることではなく suffix が空であることにあり、`content/sources/`（`Sources`）・`content/overview/`（`Overview`）・Type 別インデックス（`Person`。Issue #320 が意図してこの形にした）・通常の Wiki ページ（`山田太郎`）のいずれもサイト名を持っていなかった。`og:title` も同じ値であるため、**どのページを共有してもリンクカードの見出しにサイト名が出ない**。複数のパイロット Wiki を並行して公開している現状では、この「見出しだけを見る場面」が実際に多い。

`init.py` が `{PAGE_TITLE_SUFFIX}` を `" - <リポジトリのディレクトリ名>"` で置換する。**Issue #317（`pageTitle`）・Issue #557（footer の `{REPO_URL}`）とまったく同じ置換機構**であり、新しい仕組みは持ち込まない。区切りは Web 一般の `<title>` の慣例（`Page - Site`）に従う半角ハイフン ` - ` で、`yaml.dump(..., default_style='"')` を通すため先頭の空白が保たれる（素の YAML スカラーでは剥がれ、タブが `Wiki- my-wiki` になる）。

**root index の `title: "Wiki"` は変更しない**。(1) 報告された実害は suffix だけで消える（トップは `Wiki - decameron-wiki` になる）。(2) トップの `title` にサイト名を入れようとすると、`convert_wikilinks.py`（`.wikicommit/config.yml` しか読まない）が `quartz.config.yaml` を読む新しい結合を作るか、`.wikicommit/config.yml` にサイト名フィールドを新設して `pageTitle` と二重管理にするかの二択になる — 後者は Issue #553 の「消費者のいない／重複した受け皿を作らない」に触れる。(3) 左サイドバーの `PageTitle` に既にリポジトリ名が出ており、H1 が `Wiki` であることは冗長を避けている側である。

**`pageTitle` と `pageTitleSuffix` が同じ値を持つことは、テンプレートのコメントで受ける**。`init.py` が両方に同じリポジトリ名を埋めるため、あとから `pageTitle` だけを手編集した人は suffix を直し忘れる — このリポジトリが繰り返し踏んできた drift の形である（Issue #114・#487・#677）。それでも**器を 1 本にする方向は採らない**: `<title>` を組み立てているのは Quartz 本体の `Head.tsx` であり、`cfg.pageTitle` を参照させるにはこのコンポーネントを `quartz-plugins/` 側で差し替えることになる。`<title>` の 1 行のために Head を fork するのは、得られる整合に対して重い。代わりにテンプレートの当該 2 行は隣接しているので、その場に「この 2 つは同じ値を持つ。片方だけ変えないこと」というコメントを置く（`quartz.config.yaml` は Issue #317 が「いつでも手編集可能なプレーンな YAML フィールド」と位置づけたファイルであり、手編集する人の目に必ず入る場所に注意が置ければ足りる）。

#### 読者に「このサイトが何か」を伝える 3 つのフィールド

**4 つ目の器は作らない**。

| フィールド | 宛先 | 本数 | 置き場所 |
|---|---|---|---|
| `pageTitle` / `pageTitleSuffix` | 読者（**サイト名**） | 1 本・言語中立 | `quartz.config.yaml` |
| `site_description` | 読者（**紹介文**） | 言語ごとに 1 本 | `.wikicommit/config.yml`（Issue #671。§8.8） |
| `theme` | LLM（**内容スコープ**） | 1 本 | `.wikicommit/config.yml`（`docs/DesignDoc-data.md` §3.3） |

宛先が違えば別フィールドにする（Issue #564）一方、**宛先も役割も同じものに新しい器を足さない**（Issue #553）。サイト名は後者に当たるため、`site_description` には入れない。

**既存リポジトリへの自動移行は行わない**（`quartz.config.yaml` は `always_skip_existing=True` で書かれる）。手で `pageTitleSuffix: " - <サイト名>"` に書き換えれば同じ結果になり、その手順は `CHANGELOG.md` に書いた。ページの再生成は不要（`generated_with` の対象ではなく、ビルド設定の変更であるため）。

**ブラウザでの実表示確認は行っていない** — このリポジトリには Quartz 本体が無い（Issue #81）。検証は `Head.tsx` のコードとテンプレートの生成物に対して行い、実表示はパイロットリポジトリへの反映時に確認する。

---

## 9. 検索エンジン実装

### 9.1 全文検索（キーワード）

全文検索はフェーズと使用場面によって 3 つの実装を使い分ける。

| 実装 | フェーズ | 使用場面 | 動作場所 |
|---|---|---|---|
| grep（ファイル直読み） | Phase 1 | `/wikicommit-ask` / `/wikicommit-search` Skills | ローカル（Skills がファイルシステムに直接アクセス） |
| FTS5 trigram（SQLite 3.38+） | Phase 3 以降 | `/wikicommit-ask` / `/wikicommit-search` Skills（grep から移行）。Phase 5 以降はホスト型 MCP サーバー経由の検索（複数リポジトリ横断）でも同一実装を再利用 | ローカル（Phase 3）/ サーバー（Phase 5 以降のホスト型 MCP） |
| Quartz v5 標準の検索プラグイン（FlexSearch ベース） | 全フェーズ | 静的サイト（GitHub Pages）上のブラウザ検索 | ブラウザ（クライアント側） |

**FTS5 trigram**: CJK（日本語・中国語・韓国語）を外部依存なしで処理できる唯一の標準実装。Python 標準ライブラリの `sqlite3` モジュールでそのまま利用でき、追加インストールが不要なため Skills から呼ぶ実装として採用する。

```sql
CREATE VIRTUAL TABLE wiki_fts USING fts5(
  title, body, tags, type, lang,
  tokenize='trigram'  -- CJK 対応
);
```

トライグラム（3文字スライディングウィンドウ）による部分一致のため、形態素解析ほどの検索精度はない（活用形の揺れを吸収できない等）。Phase 3 時点ではこの精度で十分と判断し、埋め込みベースのセマンティック検索（9.2）は見送る。

#### 9.1.1 クエリ語の拡張（同義語・上位語・略語。Issue #581）

FTS5 は語彙が一致しないと何も返さない。ユーザーが「子ども手当」と入力し、Wiki ページが「児童手当」と書いていれば 0 件になる — Wiki がその話題を扱っているにもかかわらず、である。これを埋めるのが本来ベクトル検索（9.2）の役割だが Phase 3 では見送っているため、その**軽量な代替**として、エージェント自身の語彙知識によるクエリ語の拡張を置く。クロスリンガル検索を埋め込み空間ではなくエージェントのクエリ翻訳で実現した 9.3 と同じ発想を、同一言語内の語彙揺れに広げたものである。

**中心的な制約は FTS5 の暗黙 AND にある**。`search_index.py` は語ごとにフレーズ化して空白で連結するため、拡張語を同じクエリ文字列に足すと条件が**厳しくなり**、ヒットは増えるどころか消える（`"児童手当" "子ども手当"` は両方を含むページのみに一致する）。したがって「SKILL.md の指示文で拡張語をクエリに足す」という実装は成立せず、**拡張には OR セマンティクスが必要で、それはスクリプト側にしか置けない**。`search_index.py` の `--expand`（グループ内 OR・グループ間 AND）がこれを担う（`docs/DesignDoc-ScriptSpec.md`）。

**語群ごとに `query` を複数回呼び、Skill 側でマージする案**（スクリプト変更ゼロ。クロスリンガル検索が既に採っているパターン）は採らなかった。呼び出しをまたいだ bm25 スコアは比較不能であり、`wikicommit-ask` が言語間で「naive な近似で妥協する」と明記している問題がそのまま拡大する — 拡張語由来のノイズが原語由来の本命ヒットを押しのけても制御する手段がない。拡張語は「同じ意図の別表現」である以上、同一のランキング空間で評価されるべきである。

**拡張の対象は明示的に限定する**。trigram は部分一致であるため、活用形・複合語（「エンジニア」→「ソフトウェアエンジニア」）は既に無料で拾える。同義語・上位語・略語と正式名の対・英日の対応語・表記ゆれのみを拡張し、活用形・部分文字列で到達できる複合語・意味の重心がずれる関連語は拡張しない。上限は原語 1 語につき 2〜3 語・1 回の検索全体で 5 語程度とする（LLM に任せると際限なく広がるため）。3 文字未満の拡張語は生成しない（trigram で絶対に一致しないため無意味。Issue #274）。**辞書化・永続化は行わない** — 拡張はその場の LLM 判断で行い、シソーラスファイルは持たない（エージェントネイティブ型の設計方針、`docs/DesignDoc-skills.md` §11.0）。

適用範囲は `wikicommit-search` / `wikicommit-ask` / `wikicommit-synthesize` / `wikicommit-quiz` の 4 Skill で、いずれもデフォルト ON。**人間が結果を直接読む `wikicommit-search` だけが、実際に使った拡張語を結果に表示し、`--no-expand` で無効化できる** — 入力していない語がヒットの根拠になっている以上、黙って使うべきではないため。他の 3 つでは拡張は内部処理であり（`wikicommit-ask` の grounding 注記は別途その役割を果たす）表示しない。

**将来 `qmd` 等の既製ツール（9.2 の callout）を採用した場合、同ツールが持つクエリ拡張モデルと本機能の役割は重なる**。本機能はベクトル検索の代替であって前哨ではないため、その時点でどちらを残すかは採用判断と合わせて決める。

### 9.2 セマンティック検索（ベクトル）— 見送り（将来 Phase での再検討課題）

| フェーズ | モデル | 用途 |
|---|---|---|
| （未着手） | `multilingual-e5-base`（278M パラメーター） | コスト・速度のバランスが最良 |
| （未着手） | `BGE-M3` | Dense・Sparse・ColBERT を 1 モデルで統合 |

ベクトルストア候補は **LanceDB**（ローカルファイルベース、PostgreSQL 等の外部 DB 依存なし）。

> **Phase 3 では採用しない**: torch / sentence-transformers 等の重量級依存の追加、数百 MB 規模のモデルダウンロード、ページ変更を検知して再エンベディングするインデックス管理パイプラインの実装が必要になり、他の Phase 1–3 実装（stdlib + PyYAML 程度の軽量スクリプト群）と比べて作業量が大きい。クロスリンガル検索は 9.3 の方式（エージェントによるクエリ翻訳 + FTS5 trigram）で代替できるため、Phase 3 では LanceDB を導入しない。導入するかどうかは将来 Phase での再検討課題とする（フェーズ未確定）。

```python
import lancedb
import numpy as np

db = lancedb.connect("wiki_index")
table = db.create_table("pages", schema=...)
table.add([{"title": "...", "embedding": np.array(...)}])
results = table.search(query_embedding).limit(10).to_pandas()
```

<!-- -->

> **既製ツール(`qmd` 等)採用という代替案(未確定)**: Karpathy の LLM Wiki 提案(gist: `karpathy/442a6bf555914893e9891c11519de94f`)は、上記のような自前の LanceDB 実装ではなく、`qmd`(ローカル動作・BM25 全文検索＋ベクトル検索＋LLM 再ランキングのハイブリッド、CLI と MCP server の両対応)という既製 OSS ツールを検索基盤としてそのまま呼ぶ運用を推奨している。`lychee`/`markdownlint-cli2`/`markitdown` と同じ「外部ツールをシェルアウトで呼ぶ」既存パターン(§1.4)に乗せられるため、上記懸念のうち「ページ変更を検知して再エンベディングするインデックス管理パイプラインの実装」は `qmd update`/`qmd embed` に肩代わりさせられ消える。ただし埋め込みモデルのダウンロードそのものの重さ(デフォルトの `embeddinggemma-300M` で約 300MB、再ランカー・クエリ拡張モデルまで含めると計 GB 規模)は自前実装か既製ツールかに関わらず不可避で、この点だけは引き続き Phase 3 見送りの理由として残る。CJK 対応が必要な場合は `Qwen3-Embedding-0.6B`(119 言語対応)へのモデル切り替えが可能(切替後は全件再埋め込みが必要)。BM25 とベクトルの統合方式は RRF(Reciprocal Rank Fusion、スコア正規化不要でシンプル)。`qmd` 自身がローカルで LLM 推論(node-llama-cpp)を行う点は、WikiCommit というプラットフォーム自体が推論コストを負うわけではない(ユーザーのローカルマシン上で完結する)ため §1.3「LLM 推論はユーザーが持ち込む」原則(推論コストをユーザー側に負わせる)には抵触しない。セマンティック検索を再検討するとすれば、自前の LanceDB 実装より `qmd` のような既製ツールの採用を優先候補とする。

再検討の時期は「将来 Phase」と漠然と書いていたが、`qmd` はローカル LLM 推論を前提とするツールであり、これは Phase 4 の Tauri デスクトップアプリで検討されているローカル LLM(Ollama 等)対応(ユーザー自身の LLM をローカルで動かす実行系が必要。`dev/roadmap-phase4-5.md` の「ローカル LLM(Ollama 等)対応は未決定」節参照。同ファイルは公開対象外 — `docs/README.md` §3)と同じ前提(ローカル推論基盤)を必要とする。したがって両者は独立に検討するのではなく、Phase 4 でローカル LLM 対応に着手するなら、その基盤の上で `qmd` 採用も併せて再検討するのが筋が良い。Phase 4 でローカル LLM 対応自体を見送るなら、`qmd` 採用の前提も同時に崩れるため、こちらも見送りが妥当。

### 9.3 クロスリンガル検索の実装

Phase 3 では埋め込みモデルを使わず、**エージェントによるクエリ翻訳 + FTS5 trigram** でクロスリンガル検索を実現する。`wikicommit-ask` / `wikicommit-search` / `wikicommit-synthesize` / `wikicommit-quiz`（`--topic` 指定時のみ）の 4 Skill は、ユーザーのクエリ言語に加えて `.wikicommit/config.yml` の対象言語（`translation.targets` / `primary_lang`）へも Claude Code 自身がクエリを翻訳し、言語ごとに FTS5 trigram で検索して結果をマージする。専用の翻訳 API や埋め込みモデルを持たず、Skill の指示（SKILL.md）としてエージェントに翻訳を委ねる設計。

> **`wikicommit-search` / `wikicommit-quiz` は Issue #582 まで未実装だった**: 本節はもともと実装主体として `wikicommit-ask` / `wikicommit-search` を名指ししていたが、実際に実装されていたのは `wikicommit-ask` と（本節が名指ししていなかった）`wikicommit-synthesize` の 2 つで、`wikicommit-search` には存在しなかった — 設計と実装のドリフトである。`wikicommit-quiz` は `--topic` で同じ `search_index.py query` を呼ぶため同じ欠落を抱えていた。
>
> **欠落の正体は検索範囲ではなく語彙にあった**。`search_index.py` の `--lang` は省略可能なフィルタであり、省略時は言語で絞らない — つまり両 Skill は元から全言語のページを検索対象にしていた。にもかかわらず他言語のページに到達できなかったのは、**クエリが 1 つの言語でしか表現されていなかった**ためである。日本語で「認証フロー」と入力すると英語ページ `Authentication Flow` は検索対象に含まれてはいるが trigram が一致しない。固有名詞やラテン文字の術語（`Quartz`・`FTS5` 等）が偶然共有されている場合にだけ、見かけ上クロスリンガルに動いているように見えていた。したがって対応は「フィルタを外す」ことではなく、`wikicommit-ask` が既に持つ「言語判定 → 言語ごとに翻訳 → 逐次実行 → マージ → 同一ページの重複排除」の構造の移植だった。
>
> **`--lang` 明示時は言語をまたぐ fan-out を行わない**（両 Skill 共通。`wikicommit-quiz` には本 Issue で `--lang` を新設した）。ユーザーが言語を絞った意図を Skill が上書きすべきではないため、`--lang` がそのままオプトアウト手段を兼ねる。ただし**翻訳まで止めるわけではない** — `<lang>` がクエリの言語と異なる場合、クエリ語はやはり `<lang>` へ翻訳してから検索する。ある言語の語で別の言語のページを引いても構造上ゼロ件にしかならず、翻訳を止めると `--lang` が「絞り込み」ではなく「必ず空になる検索」になってしまうため。言語ごとの実行は**必ず逐次**とする — `search_index.py query` はキャッシュ未生成時に `build`（`DROP` + 全件再構築）を自動実行するため、並列に呼ぶと「キャッシュ未生成」判定が競合して二重ビルドや SQLite のロック競合を起こす。
>
> **検索対象言語は `config.yml` だけで閉じない**。全クエリが `--lang` を伴うようになったことで、それまで無フィルタだった検索が閉じた集合になる。`/wikicommit-translate <page> --lang en` は `targets` の設定に関わらず `.wikicommit/entity/en/` を作るため、`config.yml` が言及しない言語のページが実在しうる — それらは従来「検索対象ではあるが語彙が一致したときだけ届く」状態だったのが、`--lang` の導入によって**端から届かなくなる**。そのため対象言語リストには、クエリ言語・`primary_lang`・`targets` に加えて `.wikicommit/entity/` 直下に実在する言語ディレクトリも含める。これは検索を広げるためではなく、狭めないための措置である（設定済みの言語を先に並べ、重複排除の優先順位で勝たせる）。
>
> **`--limit` は言語数に関わらず言語ごと 10 件**とし、マージ後に 10 件へ絞る。言語ごと 5 件（`wikicommit-ask` が grounding 集合に対して採っている形）にすると、**この機能が対象とする Wiki でこそ結果が減る** — 全ページが翻訳済みの2言語 Wiki では両言語のクエリが同じ 10 ページを別言語で返し、重複排除で1組に潰れるため、無フィルタの `--limit 10` が 10 件返していたところが 5 件になる。`wikicommit-ask` が分割するのはヒット1件ごとに LLM コンテキストを消費するからであり、こちらは行を表示するだけなのでその制約がない。
>
> **重複排除の重みは Skill によって違う**。`wikicommit-search` では同一ページの複数言語版が並ぶのは「見づらい」で済むが、`wikicommit-quiz` では同じ事実についての設問が 2 問生成され、3〜5 問しかないクイズの出題内容そのものが壊れる。あわせて `wikicommit-quiz` は出題・解説の言語を `--topic` の言語（省略時は `primary_lang`）に固定する — クロスリンガル化により grounding が複数言語にまたがりうるため、規定がないと設問ごとに言語が変わる。`wikicommit-search` 側では、抑制された他言語版の存在を `(also in: <lang>)` としてヒット行に併記する（集約で消えたことが分からないと、Wiki が実際より薄く見える）。
>
> **クロスランゲージのランキング厳密化は行わない**。言語ごとにコーパスサイズと trigram 分布が異なるため bm25 スコアの厳密な比較はできず、`wikicommit-ask` が明記している「naive な近似で妥協する」をそのまま踏襲する（将来 Phase の再検討課題）。

```
日本語クエリ「認証フロー」
  → Skill が config.yml の targets（例: en）へエージェント自身が翻訳
  → 「認証フロー」（ja）と「Authentication Flow」（en）の両方で FTS5 trigram 検索を実行
  → 結果をマージして提示
```

将来的に埋め込みベースのセマンティック検索（LanceDB + 多言語埋め込みモデル）を導入する場合は、同一の埋め込み空間に複数言語を配置できるため、クロスリンガル検索を追加実装なしで自然に実現できる（9.2 参照）。

```
日本語クエリ「認証フロー」→ 多言語埋め込み → ベクトル化
                                              ↓ 類似度検索
英語ページ「Authentication Flow」 ← 同一空間に存在 → 検索結果にヒット
```

言語ごとに検索インデックスを分離する設計は不要。

### 9.4 MCP 経由での検索 API（Phase 5 以降・ホスト型）

```
search_wiki(query, lang=None, type=None, tags=None)
  → 言語パラメーターなし: 全言語を横断（クロスリンガル）
  → lang="ja": 日本語ページのみ
  → type="Person": 型でフィルタ
```

---

## 10. MCP サーバー設計（Phase 5 以降・ホスト型のみ）

> Phase 3 で計画していた自己ホスト MCP サーバー（単一リポジトリ向け）は撤回した。`wikicommit-ask` / `wikicommit-search` Skills が同じ役割（`.wikicommit/entity/` の検索・参照）を Git チェックアウト内で直接果たせるため、単一リポジトリ用に別プロトコル層を持つ必要がない。以下の設計は複数リポジトリ横断検索が必要になる Phase 5（Commons）のホスト型 MCP にのみ適用する。Phase 4 の Tauri デスクトップアプリはローカル git チェックアウトを直接操作するため、この MCP を必要としない。

### 10.1 ツール一覧

```
# .wikicommit/entity/ 層（高速・構造化）
search_wiki            # キーワード・タグ・セマンティック検索（多言語対応）
get_page               # 特定ページ取得（sources フィールドでソースファイルへのリンクあり）
list_pages             # タイプ・タグで一覧取得
search_by_frontmatter  # メタデータ（type・tags・expires_at 等）でフィルタ
get_backlinks          # 特定ページへの被リンク一覧
find_related           # WikiLink グラフを辿って関連ページを探索（depth 指定可）

# ソース層（ファイルシステム / URL 直接アクセス）
get_source             # sources のパスを辿って元文書を取得
```

### 10.2 レスポンスへの `review_status` 付与

```json
{
  "title": "山田太郎",
  "type": "schema:Person",
  "review_status": "pending",
  "content": "...",
  "sources": [...]
}
```

LLM が `pending` ページを参照する際に未レビューであることを認識できるようにする。MCP クライアント（エージェント）は `review_status` を下流の推論の信頼度に反映できる。

### 10.3 Phase 別の実装形態

| フェーズ | 実装形態 | 対象 |
|---|---|---|
| MVP〜OSS（Phase 1〜3・Skills） | Skills（`wikicommit-ask` / `wikicommit-search`）が `.wikicommit/entity/` を直接ファイル読み込み。単一リポジトリの検索・参照は MCP なしで完結するため、自己ホスト MCP サーバーは提供しない | 個人・開発者・OSS コミュニティ |
| Phase 4（Tauri デスクトップ） | コンパニオンアプリがローカルの git チェックアウトを直接操作。単一リポジトリの検索・参照は引き続き MCP なしで完結する | 個人・開発者（デスクトップアプリ利用者） |
| SaaS（Phase 5 以降・Commons） | ホスト型 MCP サーバー。複数リポジトリ横断検索（単一リポジトリの Git チェックアウト外に出るため Skills / デスクトップアプリでは代替できない） | 複数のリポジトリを横断して参照する必要がある利用 |
