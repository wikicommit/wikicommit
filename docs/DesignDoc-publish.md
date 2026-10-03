# WikiCommit — 公開・配信層・検索・MCP

> **対応DesignDoc**: 元 §8・§9・§10  
> §8（公開・配信層）は Phase 2 で Quartz v5 deploy と review_status バナーを実装。§9（検索）の全文検索（FTS5 trigram）は Phase 3（`wikicommit-ask` Skill が MCP を介さず直接クエリ）、§10（MCP）は Phase 5 以降（ホスト型・複数リポジトリ横断検索）。ベクトル検索（LanceDB + 多言語埋め込みモデル）は依存の重さを理由に Phase 3 では見送り、将来 Phase での再検討課題とした（§9.2 参照）。Phase 3 で計画していた自己ホスト MCP サーバーは撤回した — 単一リポジトリの検索・参照は Skills（`wikicommit-ask` / `wikicommit-search`）が代替できるため。Phase 4 は Tauri デスクトップのコンパニオンアプリがローカル git を直接操作する構成のため、ホスト型 MCP は Commons のクロスリポジトリ検索が必要になる Phase 5 まで導入しない。
>
> このファイルは**いま何が仕様か**を書く。各判断の経緯（以前の挙動・採らなかった案・実測の記録・Issue 番号ごとの議論）は [history/DesignDoc-publish.md](history/DesignDoc-publish.md) の同じ見出しの下にある。

---

## 8. 公開・配信層

### 8.1 SSG 選択

**Quartz v5 を採用**。`[[タイプ/ファイル名]]` 形式の WikiLink をネイティブサポートする唯一の主要 SSG で、GitHub Pages デプロイ用ワークフローが公式付属している。全文検索（FlexSearch ベース）・グラフビューも標準搭載。

- **Quartz v5 は npm パッケージとして配布されていない**。本体（`jackyzha0/quartz`）を git submodule として取り込み、設定ファイルは TypeScript ではなく YAML（`quartz.config.yaml`。`configuration`・`plugins`・`layout` の 3 セクション）で記述する。
- **ローカルプレビュー**: `/wikicommit-init --quartz` が生成する `package.json` には `npm run build`（ビルドのみ）・`npm run preview`（ビルド後にローカルサーバーを起動してブラウザで確認）が配線済みであり、GitHub Pages へのデプロイを待たずに手元で見た目を確認できる。
- **`--quartz` と `--quartz-pages` は分かれている**。`--quartz` はローカルビルド一式だけを生成し、`--quartz-pages`（`--quartz` 指定時のみ有効）が `deploy.yml` の生成と GitHub Pages（Source: GitHub Actions）の自動有効化を足す。`wikicommit-init` の Prerequisites も 2 段階の Y/n で聞く。手元で読みたいだけの運用者に、リポジトリ外への公開を強いないためである。`/wikicommit-merge` は Quartz / Pages に一切依存しない（`.wikicommit/entity/` の変更検出・品質チェック・Git/PR 操作のみで完結する）。
- **公開 URL は README.md へ自動で書き込まない**。次ステップ案内が `gh api repos/{owner}/{repo}/pages` の `html_url` を使った追記例（コピペ用の Markdown 片）を示すだけである。既存リポジトリの README.md は利用者独自の構成を持ちうるため、エージェントは README.md を編集しない（display-only。`.claude/skills/wikicommit-init/SKILL.md` の Notes）。
- **`syntax-highlighting` プラグインは配布テンプレート（`.claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml`）に含めない**。依存する `rehype-pretty-code`（Shiki ベース）が全言語の文法定義をバンドルするため他プラグインより突出して重く、GitHub Actions 標準ランナーでビルドが失敗する。`enabled: false` ではビルド自体はスキップされない（プラグインインストーラは `enabled` に関わらず列挙された全プラグインをクローン・ビルドし、`enabled` が効くのは適用段階だけ）ので、無効化にはエントリ自体の削除が要る。コードブロック自体の描画は `obsidian-flavored-markdown` / `github-flavored-markdown` が担うので、失うのはハイライト・コピーボタン・トークン単位の CSS クラスだけである。**再導入を検討する条件**: コード例中心のコンテンツ（HowTo 等）を多用する Wiki が増え、ハイライト・コピーボタンの需要が実際に現れたとき。そのときは上流（バンドルサイズ・Quartz 本体がビルド失敗の内容を握り潰して `"build failed"` とだけ出すこと）の状況を改めて確認する。
- **Quartz サブモジュールの更新手順は `.wikicommit/guides/updating-the-quartz-submodule.md` に置く**。ガイド棚は `update: overwrite` なので、再 init と `/wikicommit-update` で既存リポジトリにも届く（init 時にしか印字されない次ステップ案内では届かない）。WikiCommit のビルドは他人のリポジトリである `quartz/` の中へ書き込み、そのうち `postinstall` が `quartz/` 内で走らせる `npm install` による追跡ファイル `quartz/package-lock.json` の変更だけが `quartz/` 内の `git pull` を止める（`quartz/content`・`quartz/quartz.config.yaml`・`quartz/quartz.lock.json`・`quartz/.quartz/plugins/*` は未追跡で止めない）。ガイドは `(cd quartz && npm install)` を明示する — ルートの `npm install` は `postinstall` の `git submodule update` で、`git add quartz` 前の古いポインタへ黙って巻き戻すため。**`quartz/` 内を `npm ci` にして汚さない案は採らない** — `package.json` と lockfile がずれればビルド失敗になり、そのずれは上流 Quartz と利用者の npm の版で決まってこちらが制御できない。`.gitmodules` の `ignore = dirty` の案内・`.vscode/settings.json` の配布もしない（前者は表示の問いで更新の塞がりを解かず、後者は利用者のエディタ設定である）。

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

**未解決 WikiLink の表示**: `check_wikilinks.py` は「参照先ページがどの言語にも存在しない」ケースを ERROR ではなく WARNING として扱うため、参照先が解決できない `[[Type/slug]]` を含んだページも `wikicommit-merge` を通過しうる。ビルド前変換スクリプト（`convert_wikilinks.py`）は、そのような WikiLink をリンクにはせず、ブラケットを除いたプレーンテキスト `Type/slug` として出力する（`lang`/`current_type` が特定できない場合、および同言語・`primary_lang` いずれのターゲットファイルも存在しない場合の両方）。生の `[[Type/slug]]` というダブルブラケット構文がそのまま読者に表示されることはない。この変換は `unresolved_links` カウント・`SUMMARY:` 行の集計には影響しない（集計は変換前の判定結果に基づく）。

### 8.3 JSON-LD 埋め込み

Quartz プラグインとしてビルド時に実行。ページの `properties:` ブロック（型固有の Schema.org プロパティ。`title`/`tags`/`sameAs`/`wikidata` 等のトップレベル共通フィールドとは分離してネストされている）の値を、型ごとに定めたマッピングでそのまま JSON-LD のキーへ流し込む（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-jsonld/src/index.tsx` の `typeStr` 分岐を参照。マッピング自体は型ごとに決め打ちで、スキーマファイルから動的に読み取るわけではない）。

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

review_status: reviewed（同じ見出し・同じ本文・同じ生成情報のまま、行が 1 つ増える）
┌─────────────────────────────────────────────────────────────────────┐
│ ⚠️ LLM が自動生成したページです                                      │
│ 内容に誤りがある可能性があります。                                    │
│ 生成日: 2026-06-17  生成モデル: claude-sonnet-4-6                   │
│ 出典と照合: 2026-09-05  照合モデル: claude-opus-5[1m]                │
│ octocat が読み、明らかな問題は見つかりませんでした                   │
│ [気づいた点を報告する]（GitHub アカウントが必要）                       │
└─────────────────────────────────────────────────────────────────────┘

review_status: reviewed（reviewed_by が無い場合。route B のページなど）
┌─────────────────────────────────────────────────────────────────────┐
│ ⚠️ LLM が自動生成したページです                                      │
│ 内容に誤りがある可能性があります。                                    │
│ 生成日: 2026-06-17  生成モデル: claude-sonnet-4-6                   │
│ 出典と照合: 2026-09-05  照合モデル: claude-opus-5[1m]                │
│ 人が読み、明らかな問題は見つかりませんでした                         │
│ [気づいた点を報告する]（GitHub アカウントが必要）                       │
└─────────────────────────────────────────────────────────────────────┘
```

#### バナーは 1 つで、状態に応じて行を足す

- **分岐を 2 つ持たず、1 つのバナーが状態に応じて情報を足す**。LLM 生成である旨（翻訳ページでは `translated_at` / `translated_by`）は `review_status` に関わらず表示し、`reviewed` は警告を**取り除く**のではなく**行を 1 つ足す**（誰が読んだか）。人が読んでもページが LLM 生成でなくなるわけではなく（`review-issue-close-sync.yml` が書き換えるのは `review_status` と `reviewed_by` だけで、`generated_by` / `generated_at` は恒久的なフィールドである）、`reviewed` が意味するのは `docs/DesignDoc-pipeline.md` §6.3 の遷移表に書かれたものだけで、「LLM 生成であることが問題でなくなった」に相当する保証は無いためである。報告リンクは常時表示する。
- **見出しは状態によらず真である事実に固定する**。見出しは `LLM が自動生成したページです`（事実）、本文は `内容に誤りがある可能性があります。`（含意）である。**見出しを状態で入れ替えない** — 入れ替えると pending 側は何かを言わなければならず、言えるのは「このページはまだ誰も読んでいません」のような否定形だけになる。それは「書き込み権限を持つ誰かの読了が記録されていない」を、読んでいる人の前で偽になる形で宣言することになる。**`⚠️` も両状態で出す** — pending 限定にすると「レビューで警告が取り消される」という読みをマークアップに書くことになる。
- **状態は「読了行があるかどうか」で伝わる**（加えて修飾クラス `wikicommit-banner--pending` 等）。`reviewed_by` があれば `readBy`（`<login> が読み、明らかな問題は見つかりませんでした` / `Read by <login> — nothing obviously wrong stood out`）を出し、無ければ同じ文を名前なしで述べる `readByAPerson` を出す。名前が無いのは route B のページ（`/wikicommit-review` はローカル実行で GitHub login を得られない）とレビュアーの記録が始まる前にレビューされたページで、**行を出さないとこれらが pending と見分けられなくなる**。レビュアーの欠落は正常な状態であり、空ラベルや `unknown` プレースホルダーは出さない — 出すのは名前の代わりではなく、事実そのものの行である。
- **生成情報を出すかどうかは `review_status` ではなく生成スタンプの有無で判定する**。`review_status: reviewed` はビルド生成のナビゲーションページでバナーを黙らせるためのスタンプでもある（下記「ビルド生成のナビゲーションページにはバナーを出さない」）ので、`reviewed` を条件に生成情報を出すと、それらのページに「LLM が自動生成しました。生成日: 不明」が出る。**見るスタンプは、そのページで実際に描画する 1 組に限る** — 翻訳ページ（`translated_from` あり）なら `translated_at` / `translated_by`、それ以外なら `generated_at` / `generated_by`。4 つの和集合で判定すると、`generated_*` だけを持つ翻訳ページが「翻訳日: 不明 翻訳モデル: 不明」を出す。**`pending` はこの判定を免除する**（欠けたスタンプは `unknown` プレースホルダーで出す） — `pending` を書くのは `wikicommit-generate` / `-translate` / `-synthesize` だけなので、そのページは定義上生成を経ており、スタンプの欠落は埋めるべき穴である。生成スタンプを持たない古いレビュー済みページには生成情報が出ないが、それは正直な結果である。
- **この表示を「バッジ」と呼ばない**。実物は条件付きの見出しと行であり、独立した UI 部品ではない。ただし登録済み Issue と `CHANGELOG.md` の既発表エントリの用語は書き換えない（その時点の記録であるため）。
- バナーは frontmatter を読んでビルド時に描画するので、表示の変更は次のデプロイで全ページに反映され、ページ側の移行は要らない。検証は `WikiCommitBanner.test.tsx` の描画結果に対するアサーションで行う（このリポジトリには Quartz 本体が無く、レンダリング結果を目視できない）。

#### 出典との照合（AI レビュー）は publish 時にだけ注入する

Pass 4 は生成した全ページをソースと照合し、その判定は `.wikicommit/review/` に記録される（`docs/DesignDoc-data.md` §4.8）。バナーは有効な判定を持つページに「出典と照合: <日付> 照合モデル: <モデル>」の行を出す。

- **ページの frontmatter にコピーせず、`convert_wikilinks.py` が publish 時に `content/` 側だけへ注入する**（`ai_review_model` / `ai_review_at`）。コピーは古くなる — `/wikicommit-fix` がページを書き換えても、ページに書かれたコピーはそれを知らない。記録が `page_content_hash`（内容ハッシュ）を持つので、publish 時に「この判定は今公開しようとしているページにまだ有効か」を決定論的に判定できる。`.wikicommit/entity/` のページは 1 文字も変わらないため、`validate_frontmatter.py` に検証ルールは要らない。
- **判定が無い・最新の判定が `pass` でない・失効している・記録が読めない、の 4 つはいずれも「何も出さない」に落とす**。失効の判定は `check_review_coverage.py` の `stale_reasons()` をそのまま借りる — ページ本文の書き換えだけでなく、判定の根拠だったソースが変わった・ページから外れた場合も含む（`sources` は内容ハッシュが無視する bookkeeping フィールドであるため、ハッシュ比較だけでは捉えられない）。片方だけを実装すると `/wikicommit-status` と食い違うバナーになる。`pass` 以外を出さないのは、`wikicommit-review` が問題を見つけたとき `--result fail` をディスク上に残るページに対して記録するためである。記録はさかのぼって作れないため、記録の仕組みより前に生成されたページの空白は恒久的である。
- **文言は「何を照合したか」を述べ、「検証済み」と読める形にしない**。Pass 4 が見ているのはソース忠実性だけであり、網羅性は対象外、実在の人物・組織への害と読者自身の知識との食い違いはどの層も見ていない。`reviewed` の過大表明を直したのと同じ過ちを、機械の側で逆向きに繰り返さない。
- **指摘件数はページ単位に出さない**。「指摘 2 件」と出ると読者には品質の悪いページに見えるが、実際は指摘を受けて直っているので意味が逆になる。件数はサイト単位（§8.8.1 の俯瞰ページ）に寄せる。
- 翻訳ページの照合（`stage: translate-check`）は「出典と照合」ではなく「原文と照合:」（`aiReviewOriginalAt`）として出す（§8.8.1）。

#### 「このページのレビュー状況を見る」— レビュー追跡 Issue への導線

`review_status: pending` のページのバナーは、そのページのレビュー追跡 Issue（`wikicommit-merge` Step 8 が作る）へのリンクを出す。Claude Code のセッションを持たない読者も、GitHub 上で Close するだけでレビューに参加できる入口である。

- **リンク先は Issue 番号ではなく GitHub の Issue 検索 URL である**（`is:issue is:open label:wikicommit-review in:title "<Type>/<slug> (<lang>)"`）。追跡 Issue は PR マージ**後**に作られる一方、Quartz ビルドは同じマージがトリガーであり、番号は frontmatter にも無い。静的に組み立てられるのは Issue タイトル `Review: <Type>/<slug> (<lang>)` とラベル `wikicommit-review` だけなので、この 2 つで組み立てる。材料はすべて同コンポーネントが `reportUrl` に使っているもので足り、新しい frontmatter フィールド・書き戻し・再デプロイは要らない。
- **検索キーにページの `title` を使わない**。ページの再生成は `title` を変えうる一方 `type`/slug/`lang` は変えないため、`title` をキーにすると再生成のたびにリンクが外れる。
- **`is:open` を外さない**。再生成されたページは `reviewed` から `pending` に戻り、次の `wikicommit-merge` Step 8 が新しい追跡 Issue を立てるので、1 ページに同一タイトルの Issue が時系列で複数存在しうる。フィルタが無いと Close 済みの Issue を現在のレビュー先として提示してしまう。`state:open` ではなく `is:open` を使うのは GitHub 自身の Issue 一覧が出す形だからである。タイトルから `Review:` 接頭辞を落としているのは、ラベルが既に集合を絞っており、引用句の中で唯一のコロンだったため。
- **壊れ方が穏やかである**。Issue がまだ無い状態（Step 8 到達前・作成失敗）でも「検索結果 0 件」のページに着地するだけでリンク切れにならない。GitHub のタイトル検索はトークン単位のため、slug を延長した隣接ページ（`.../yamada-taro` と `.../yamada-taro-jr`）が同時に出ることはありうる — リンク文言が特定の Issue を開くと断定しないのはこのためである。
- **表示条件**: `review_status: pending` のときのみ。追跡 Issue が open である期間とページが `pending` である期間は `review-issue-close-sync.yml` によって一致する（Close → `reviewed` に書き換え → 再ビルドでリンクが消える）ため、Close 済み Issue へのリンクが残り続ける状態は構造的に発生しない。加えて `GITHUB_REPOSITORY`・`type`・`lang`・ページのファイルパスのいずれかが欠けている場合はリンクを出さない（検索キーを組み立てられないため。`reportUrl` の `"#"` フォールバックとは扱いを変えている）。この条件は副次的に、`type`/`lang` を持たない Quartz 生成のフォルダページ・タグページにリンクが出ることも防ぐ。
- **報告リンク（§8.5）はこれを置き換えるものではなく併置する**。あちらは `review_status` に関わらず常時表示され、レビュー済みページで誤りを見つけた読者の手段であり続ける。逆にレビュー済みページからレビュー追跡 Issue への導線は設けない（該当 Issue は Close 済みであるため）。

#### ビルド生成のナビゲーションページにはバナーを出さない

`WikiCommitBanner` は `review_status` が無い場合 `pending` にフォールバックする（LLM 生成ページで書き漏れた場合に安全側へ倒すための意図的な設計であり、変えない）。したがってバナーが出るべきでない機械生成のページの側で抑止する。手段は書き出し側があるかどうかで 2 つに分かれる。

- **WikiCommit が書き出すナビゲーションページには、書き出し側で `review_status: reviewed` を明示的にスタンプする**。対象は root `content/index.md`（`convert_wikilinks.py` の `generate_root_index()`）・`content/sources/` 配下の各ページと索引（同 `_write_source_page()`・`_write_sources_index()`・`_write_source_dir_index()`）・Type 別インデックス `.wikicommit/entity/<lang>/<Type>/index.md`（`rebuild_index.py`）・俯瞰ページ（§8.8.1）で、いずれも「LLM が書いた Wiki コンテンツではない」という同じ理由による。Type 別インデックスは `wikicommit-merge` のレビュー追跡 Issue の対象外でもある（Step 8 が明示的に除外する）。
- **Quartz 自身が生成するフォルダページ（`content/ja/` 等）・タグページはレイアウト設定で除外する**。対応する `.md` の実体がどこにも書き出されず、スタンプする書き出し側が存在しないためである。`quartz.config.yaml` の `layout.byPageType.folder` / `tag` の `exclude` に `wikicommit-banner` を加え、これらのページではコンポーネント自体を描画しない。この除外は常時表示の報告リンク（§8.5）も同時に落とす — 機械生成の目次に対して報告を出す先は無い。`tests/test_template_mirror_sync.py` が配布テンプレートの `exclude` に `wikicommit-banner` が入っていることを検証する。

**Type 別インデックスには 2 つの機構が層になっており、どちらも消してはならない**。Type 別インデックスは Quartz の「フォルダページ」として描画され、`index.md` の本文はフォルダページに取り込まれる（`index.md` があってもフォルダページは抑止されない）。

| | 効く範囲 | 届き方 |
|---|---|---|
| `review_status: reviewed` のスタンプ | 全 `wikicommit-banner` を `wikicommit-banner__report` へ落とす | `rebuild_index.py` ＝ `.wikicommit/scripts/` ＝ `update: overwrite`。**既存リポジトリにも届く** |
| `layout.byPageType.folder.exclude` | コンポーネント自体を描画しない | `quartz.config.yaml` ＝ `always_skip_existing`。**既存リポジトリには届かない** |

新規 init では `exclude` が先に効くのでスタンプは重複になるが、**`exclude` が届かない既存リポジトリではスタンプだけが効いている**。スタンプを「`exclude` があるから不要」として削ると、既に公開されている全リポジトリの Type 別インデックスにフルバナーが復活する。

- **判定を `WikiCommitBanner` 側に置かない**。同コンポーネントは `fileData.slug === "index"` のような Quartz 側のスラッグ命名規約に依存しない方針を採っている（§8.8「表示条件」と同じ）。
- `quartz.config.yaml` は `always_skip_existing=True` で生成されるため、`/wikicommit-init --quartz` を再実行しても `exclude` は届かない。既に公開している Wiki でフォルダ・タグページのバナーを消すには、`layout.byPageType.folder` / `tag` の `exclude` に `wikicommit-banner` を手で追記する（新旧混在を許容する）。

### 8.5 閲覧者フィードバック（Issue 起票）

閲覧者が Wiki ページの報告リンクをクリックすると、`wikicommit-banner` コンポーネント（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-banner/src/components/WikiCommitBanner.tsx` の `reportUrl`）が GitHub の `/issues/new?template=report.md&title=...&body=...` プレフィルURLへ直接リンクする。インラインフォーム・Bot 代理起票・Formspree/Netlify Forms 経由のメール通知は存在しない — SaaS/OSS のいずれの配布形態でも同じ直接リンク方式で動作する。

```
閲覧者が報告リンクをクリック
  ↓
GitHub の Issue 新規作成画面へ遷移（プレフィル済み。GitHub アカウントが必要）
  - タイトル: ページの type + title
  - 本文: ページの公開URL・言語
          （翻訳ページの場合は原文ページへの手がかりも）
          ＋「何を報告してほしいか」の案内（i18n 文字列から組み立てる）
  - ラベル: wikicommit-report（`.github/ISSUE_TEMPLATE/report.md` に固定）
  ↓
閲覧者自身の GitHub アカウントでそのまま Issue を起票
  ↓
メンテナーが /wikicommit-fix <issue-url> を実行
  ↓
通常の審査フロー（→ review_status: reviewed）
```

- **リンク自身が「GitHub アカウントが必要」と述べる**（`WikiCommitBanner` の `reportLinkAccountNote`。§8.4 の図）。未ログインで `/issues/new?template=…&title=…&body=…` を開くと `login?return_to=<元 URL 全体>` へ飛ばされ、フォームは見えない。事前入力は失われない（`return_to` に元 URL が丸ごと入り、認証後に復元される）ので、事実を 1 つ添えるだけで足りる。注記をリンクのラベル自体に折り込まないのは、ラベルが `.wikicommit-banner__link` として下線付き・色付きで描画され、注記まで同じ強さで出すと行動の呼びかけと競合するためである（バナーの視覚的な重さを増やさない）。
- **アカウント不要の受け皿は作らない**。インラインフォーム・Bot 代理起票・Formspree/Netlify Forms 経由のメール通知は、外部サービスに依存して「外部 DB を持たない」設計に反し、スパム対策と個人情報の受領という別種の運用を生む。`dev/PRD.md` §5.5 にある「GitHub アカウント不要」なインラインフォームの構想は撤回済みの当初案であり、将来実装の予定ではない（同節の記述は陳腐化している）。**参加募集の文言にもしない**（この Wiki は外部レビュアーを募らない）。

#### 報告リンクが「何を報告してほしいか」を伝える

機械が原理的に確認できない 2 つ — 実在の人物・組織への害と、読者自身の知識との食い違い — に最初に気づくのは、たいていその記事の当事者や詳しい読者である。彼らはリポジトリの Issue 一覧（レビュー追跡 Issue の本文）は見ないが、自分について書かれたページは見る。そこで全ページに常時表示される報告リンクに案内を載せる。

- **ラベルは「気づいた点を報告する」**（`Report something you noticed`）。「誤り」に限定しない。**バナーにチェックリストのブロックは追加しない** — 全ページ・全訪問で同じ行が出ると、常時点灯する警告と同じく読まれなくなる。
- **具体的な案内は事前入力される Issue 本文に置く**。3 項目（実在の人物・組織について書きすぎ・断定しすぎに感じた箇所／知っていることと食い違う箇所／他のページと言っていることが違うと感じた点）と、それ以外（誤字・古くなった情報・リンク切れなど）も歓迎する旨の 1 行である。ソースとの一致・WikiLink のリンク先といった読者が確かめられない項目は載せない。
- **`report.md` に直書きせず i18n 文字列から組み立てる**。`reportBody` は `t.reportBodyPage` 等から組み立てられているので、ページの言語に自動的に従う。リンクを経由せず `/issues/new` から直接開いた人のために、`report.md` 側にも簡潔な版を置く。
- **「以下のいずれかでなければ報告するな」と読める形にしない**が、**「その他、気づいたこと」のような包括的な受け皿も置かない**。報告リンクが立てるのは Issue であり、Issue は誰かが処理すべきものとして立つ以上、書く側に「直すべきだ」という確信が要る。確信に至る前の気づきは giscus（§8.5.1）の層が受ける。**どちらか一方に包括的な受け皿を作り直してはならない**（分担が崩れる）。
- **事前入力の案内は HTML コメントに包み、見出し（`## 報告内容` / `## Problem` 相当）を添える**。`body=` の事前入力はただのテキストなのでそのまま投稿され、`/wikicommit-fix` は Issue の本文全体をフィードバックとして読み論点ごとに分類するため、案内が残るとそれが偽の論点になる。`body=` は `report.md` 自身の `## Page` / `## Problem` 見出しを丸ごと置き換えるため、見出しは事前入力側が持つ。
- **チェックボックス（`- [ ]`）にしない**（attestation の UI であり、追跡 Issue の重さの一部である）。**追跡 Issue と同じ文面にしない** — 報告リンクは「気づいたら教えてください」（任意かつ部分的）、追跡 Issue は「Close する前にこの 2 つに目を留めてください」（ページが `reviewed` になり名前が付く）であり、同じ箇条書きをコピーすると片方が他方の劣化コピーに見える。
- **URL 長の上限**: `reportBody` は `encodeURIComponent` を通して URL クエリに載る（日本語は 1 文字が最悪 9 バイト）。GitHub 側の受け入れ限界は実測で約 6KB（約 7KB から接続断、約 16KB で `414 URI Too Long`）であり、`WikiCommitBanner.test.tsx` が上限 6,000 バイトを回帰テストとして固定する。文言を伸ばしすぎれば CI が落ちる。
- `report.md` は `always_skip_existing=True` で生成されるため再 init では届かないが、`quartz-plugins/` は `update: overwrite` なのでバナー側の案内は再 init で届く。

#### 翻訳ページからの報告と、フッターのリンク

- **翻訳ページ（`translated_from` あり）からの報告には、原文ページへの手がかりを 1 行足す**。`allFiles` から `translated_from` が指す原文ページを解決できれば、`WikiCommitSources.tsx` と同じロジック（`entityPathToRelativePath()`）で原文ページの公開 URL を算出して埋め込む（`/wikicommit-fix <published-page-url>` にそのまま渡せる）。解決できない場合（`cfg.baseUrl` 未設定・`allFiles` に一致するページがない・原文ページ自身が `status: removed`）は、`translated_from` の生値（`.wikicommit/entity/<lang>/<Type>/<slug>.md` 形式のパス）を埋め込む（`/wikicommit-fix <page-path>` にそのまま渡せる）。どちらのページを実際の修正対象にすべきかの判定は `/wikicommit-fix` 側（`docs/DesignDoc-skills.md` の `wikicommit-fix` 記載）が担い、本コンポーネントは判定材料を埋め込むだけに留める。
- **フッターの GitHub リンクは利用者のリポジトリを指す**。`quartz-community/footer` プラグインの既定（上流 Quartz のリポジトリと Discord へのリンク）をそのまま配ると、公開サイト上で最も目につく GitHub リンクが上流の SSG を指し、バナー内の報告リンクと食い違う。テンプレートの当該行は `GitHub: {REPO_URL}` プレースホルダーであり、`init.py` が生成時に置換する（`pageTitle` と同じ機構）。値は `wikicommit-init` SKILL.md が `--repo-url="$(gh repo view --json url -q .url)"` というコマンド置換の形で渡す（値がエージェントを経由しない）。
- **GitHub リモートが解決できない場合**（ローカルのみで初期化した・`gh` 未認証等。コマンド置換が空文字列に展開され、フラグ省略と同じ扱いになる）は、**`GitHub:` エントリごと削除して `links: {}` にする**。上流 Quartz の URL に戻すのは直そうとしている不具合そのものであり、リテラルの `{REPO_URL}` を設定ファイルに残すのはそれより悪い。footer プラグインは空の `links` を扱えるので、フッター自体はリンク一覧なしで描画される。この削除は `init.py` が `NOTE: quartz.config.yaml: no --repo-url resolved ...` 行で報告する（解決失敗が `gh` 自身の stderr にしか現れないため）。`Discord Community:` 行は対応する導線が無いので削除してある。
- `quartz.config.yaml` は `always_skip_existing=True` で生成されるため、既存リポジトリには届かない（既存利用者は当該行を手で編集する）。

### 8.5.1 気づき・報告・宣言の 3 層（giscus）

確信に至っていない気づきを書ける場所として、ページ上に giscus（GitHub Discussions を使うリアクション・コメント欄）を置く。§8.5 の報告リンクは `wikicommit-report` ラベルの **Issue を立てる**ため、書く側に「直すべきだ」という確信が要り、「なんとなく他のページと言っていることが違う気がする」を書く場所にならない。

| 層 | 場所 | 誰が | 何を | 必要な確信 |
|---|---|---|---|---|
| **気づき** | giscus（ページ上） | 誰でも・何度でも | 「気がする」の段階のもの。感想も含む | 不要 |
| **報告** | 報告リンク → `wikicommit-report` | GitHub アカウントを持つ誰でも | 直すべきだと確信したこと | 要る |
| **宣言** | レビュー追跡 Issue の Close | Close 権限（write / triage）を持つ人 | 読んだという表明。状態遷移 | — |

**この層が受けるものは、機械が原理的に届かない領域と重なる**。Pass 4 のページ間矛盾の検出は同一バッチ内で先に生成された兄弟ページしか見られず、**異なるバッチで生成された 2 ページ間の矛盾は原理的に届かない**。バッチをまたいで複数ページを保持している主体はシステム内に人間しかいない — 今日 A を読み、来週 B を読む人だけが、その 2 つを同時に持っている。パイロット（`saitama`）でも、公開まで到達した欠陥はページ間矛盾 3 件だけで、ハルシネーション・捏造・誤帰属・孫引き・年号誤りは 0 件だった。その気づきは「気がする」の段階で生まれるため、受け皿が Issue しか無ければ失われる。

giscus と報告リンクが受けるのは**同じ産物（欠陥への気づき）の確信度違い**であり、下書きと提出のような関係になる。確信が固まった場合は本人が報告リンクから別途 Issue を立てる — **giscus のコメントを Issue へ自動昇格させる機構は作らない**（どのコメントが確信に達したかを機械が判定できない）。分担を保つため、どちらの面にも包括的な受け皿を作り直さない。

#### リアクションを `review_status` に配線しない

技術的には可能（Discussions にも webhook イベントがある）が、4 つの理由で採らない。

1. **👍 は「読んだ」を意味しない。** 「良かった」であって「読んで報告することが無かった」ではない
2. **閾値に原理が無い。** リアクションは累積し `review_status` は 2 値。1 件で遷移か 3 件か、どの数字にも根拠が無い
3. **アクセス制御が壊れる。** Close には write / triage が要る。`reviewed` はこの Wiki が読者に対して行う主張であり、通りすがりの誰でも反転できる状態にするのは信頼モデルの変更そのものである
4. **作業リストが消える。** Discussion は最初の反応があって初めて生まれるため、**誰も触っていないページには Discussion が存在しない** — 「まだ誰にも読まれていないページ」の列挙ができなくなる

giscus は「**どれだけ届いたか**」（累積・終端なし）の軸で完結させ、「**届いたか**」（2 値・終端あり）の軸には接続しない。これにより `review_status` は 2 値のまま保たれ、信頼ラダーに第 3 の状態は生まれない。

#### 実装

`quartz.config.yaml` テンプレートの `github:quartz-community/comments` ブロックは `enabled: false` のまま配布し、**4 値（`repo` / `repoId` / `category` / `categoryId`）をプレースホルダーとして先置きしない**（大半のリポジトリで永久に空のまま残る受け皿を作らない）。有効化手順は `wikicommit-init` SKILL.md の「Enabling comments (giscus)」節に置き、前提 3 つ（public / giscus app / Discussions）と Announcements 型カテゴリ推奨を明記する。

**既存 Wiki には自動では届かない。** `quartz.config.yaml` は `_root_outputs.py` で `update: review` のため、再 init でも `/wikicommit-update` でも上書きされない。ブロック自体は既に存在するので `check_distribution_freshness.py` の `yaml_keys` 差分にも出ない — **有効化は各 Wiki の運用者が手で行う操作**になる。

**ビルド生成のナビゲーションページには出さない。** giscus はレイアウトの `afterBody` に入るため、放っておくと Type 別インデックス・view 別インデックス・root index・`content/sources/`・`content/overview/` にも付く。これらは知識のページではなくナビゲーションと集計であり、その下にコメント欄が並んでも受け取るものが無い。手段はプラグイン側にあり（frontmatter の `comments` が `false` なら描画しない）、**これらの経路は既に `review_status: reviewed` をスタンプしている（§8.4）ので、同じ場所に 1 キー足す**。判定を表示側（スラッグ命名の推測）に置かず書き出す側でフィールドを持たせる、という §8.4 の線引きもそのまま当てはまる。

**ただし frontmatter だけでは届かないビルド生成ページが 2 種類ある。** Quartz 自身が合成する folder ページと tag ページには対応する `.md` の実体がどこにも書き出されないため、スタンプする書き出し側が存在しない。とくに `content/<lang>/index.md` は書き出していないので、**言語トップ（`/ja/` 等）は必ず合成 folder ページになる**。`/tags/<tag>` も同様。この 2 種は `layout.byPageType.folder.exclude` / `tag.exclude` に `comments` を並べて除外する — 同じリストが同じ理由で `wikicommit-banner` を除外している（§8.4）。したがって除外は 2 系統あり、どちらか一方では覆えない: 書き出し側があるページは frontmatter、無いページはレイアウト設定である。

**UI 言語は 1 つに固定される。** `lang` はプラグイン設定の 1 値で、ページの `lang` frontmatter には追随しない（回避手段が無い）。多言語 Wiki では読者の言語とずれるが、`primary_lang` に合わせるのが既定として妥当である。

#### 受容済みのリスク

| リスク | 扱い |
|---|---|
| `github:quartz-community/*` への依存 | Quartz プラグインのビルド不安定（§8.1 の `syntax-highlighting` 等）に 1 本足すことになる。**元から不安定であるため受容**する |
| 空だと空に見える | 全ページに「0👍」が並ぶ。報告リンクは空でも空に見えないが、投票ウィジェットは空だと空に見える。**受容**する |
| アカウントを持たない読者には届かない | giscus のリアクション・コメントには GitHub アカウントと OAuth 認可が要る。**ただしこれは giscus が新たに作る壁ではない** — 報告リンクからの Issue 起票にも、追跡 Issue の Close にもアカウントが要る。giscus が足すのは OAuth 認可 1 回だけで、認可後のリアクションは 1 クリックであり **Issue 起票より軽い**。アカウントを持たない読者への扱いは §8.5 |

#### アクセスランキング・アナリティクスは含めない

GitHub Pages はアクセスログを提供しない（`analytics: null` が既定なのはそのため）ため第三者アナリティクスが必須になるが、**画像のホットリンクを退けた理由の 1 つが「読者のブラウザが第三者サーバーへリクエストを出すため、閲覧の事実と IP が漏れる」**である（§8.6）。画像で採った立場と逆のことを解析で全ページに対して行うことになる。GoatCounter や Plausible は cookie-less でこの問題は小さいが、第三者へのリクエストであること自体は変わらない。**やるなら画像の判断と立場を 1 つに揃える必要がある**ため別途とする。

---

### 8.6 画像・動画の埋め込み

新規の仕組みは不要。Quartz v5 標準の Obsidian Flavored Markdown プラグイン（`quartz.config.yaml` の `obsidian-flavored-markdown`）が標準 Markdown 構文のみで以下をすべてサポートしていることを、実際に Quartz ビルドを実行して確認してある（`enableInHtmlEmbed: false` のまま・設定変更なし）。

| 埋め込み対象 | 記法 | 挙動 |
|---|---|---|
| ローカル画像 | `![alt](../../assets/xxx.png)`（`.wikicommit/entity/<lang>/<Type>/<slug>.md` から `.wikicommit/entity/assets/` への相対パス。ファイル名規約は `docs/DesignDoc-data.md` §3.1 参照） | `<img>` としてそのまま表示（`convert_wikilinks.py` が `.wikicommit/entity/assets/` を `content/assets/` へミラーする） |
| 外部URL画像 | `![alt](https://example.com/image.jpg)` | `<img>` としてそのまま表示 |
| ローカル/外部動画ファイル（mp4・webm 等） | `![alt](path-or-url.mp4)` | `enableVideoEmbed`（デフォルト `true`）により自動で `<video controls>` に変換される |
| YouTube 動画 | `![alt](https://www.youtube.com/watch?v=xxxxxxxxxxx)` | `enableYouTubeEmbed`（デフォルト `true`）により URL を含む画像記法の `<img>` が自動で `<iframe class="external-embed youtube">` に変換される。**画像埋め込みと全く同じ標準 Markdown 構文**（`![alt](url)`）でよく、`<iframe>` を手書きする必要はない |

**ローカル画像は `convert_wikilinks.py` の `sync_assets()` が運ぶ**。`.wikicommit/entity/assets/` 配下の全ファイルを `content/assets/` へミラーし、削除済みファイルを stale cleanup する。カスタム型ページは公開時に `custom/` セグメントが落ちて 1 段浅くなるが、本文中の相対パス（`![](...)` の相対 `src`）は `rewrite_relative_links()` が書き換えるので、本文は常に `.wikicommit/entity/` から見た相対パスで書けばよい（`docs/DesignDoc-data.md` §3.1）。外部 URL 画像・YouTube・動画 URL はこの経路を通らない。

**公開サイト側の挙動を検証するときは、`content/` へ直接ファイルを置かず、`.wikicommit/entity/` を起点に `convert_wikilinks.py` を通す**。`content/` は `convert_wikilinks.py` の出力であり、手で置いたものは実行のたびに stale cleanup の対象になる。また `content/` に置けば表示されることを確かめても、`content/` へ運ぶ工程があることは確かめられない。

`enableYouTubeEmbed` / `enableVideoEmbed` はいずれも `quartz.config.yaml` テンプレートで明示的に上書きしていないため、デフォルト値 `true` が有効になっている。したがって `.claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml` の変更は不要。

#### `enableInHtmlEmbed` は変更しない

YouTube 埋め込みに `enableInHtmlEmbed: true` は要らない。

- `enableInHtmlEmbed` は Obsidian Flavored Markdown プラグイン内の話者向けオプションで、**生 HTML ブロック内に書かれた** `[[WikiLink]]` / `==highlight==` / `#tag` 記法を後処理でパースするかどうかのみを制御する。YouTube・動画埋め込みは上記の通り別の専用オプション（`enableYouTubeEmbed` / `enableVideoEmbed`）で処理されており、`enableInHtmlEmbed` とは無関係。
- **`<iframe>` 等の生 HTML タグを Markdown 本文に直接貼り付けた場合、`enableInHtmlEmbed` の値に関わらず常にそのまま出力される**ことを実際のビルド出力（`toHtml` 後の HTML）で確認した。Quartz コア（`quartz/processors/parse.ts`）が `remarkRehype(..., { allowDangerousHtml: true })` を常時有効にしており、プラグイン側のオプションでこれを無効化する経路がないため。

このため `enableInHtmlEmbed` を `true` に変更しても、WikiCommit が必要とする埋め込み機能（画像・動画・YouTube）は増えず、セキュリティ上のリスクも変化しない（生 HTML の通過は現状の `false` のままでも既に常時許可されている）。**`enableInHtmlEmbed: false` を変更せず維持する**。

#### 生 HTML がそのまま公開されるリスク

Wiki 本文に混入した `<script>` タグは、`enableInHtmlEmbed` の設定に関わらず常にそのまま HTML 出力に含まれ、閲覧者のブラウザで実行される（実際のビルド出力で確認済み）。経路A（`DesignDoc-pipeline.md §6.3`）では `review_status: pending` の LLM 生成ページが人間レビュー前に main マージ・公開されるため、ingest 元文書に埋め込まれた悪意ある HTML（間接プロンプトインジェクション等）や LLM のハルシネーションにより生 `<script>` / `<iframe>` がページ本文に混入した場合、レビュー前に公開サイトで実行されうる。対応は次節。

#### 生 HTML の扱い方針

画像・動画・YouTube の埋め込みは標準 Markdown 構文（`![alt](path-or-url)`）だけで完結しており、ページ本文が生 HTML タグを必要とする正当なユースケースは存在しない。この前提の下、**生成時の制約と `wikicommit-merge` でのブロッキング検証で生 HTML 自体を排除する**:

- `wikicommit-generate` の Pass 3（`.claude/skills/wikicommit-generate/SKILL.md`）に、ページ本文へ生 HTML タグを一切書かないという生成時制約を明記した（ソース文書自体が生 HTML を含む場合でも、意味を抽出するだけでマークアップはコピーしない）。
- `.wikicommit/scripts/check_raw_html.py`（新規）を `wikicommit-merge` の品質ゲートに追加した。ページ本文（frontmatter を除く）を対象に、コードフェンス（バッククォート3つ、または `~~~`）とインラインコード（バッククォートで囲んだ範囲）で囲まれた箇所（Markdown が地の文としてエスケープ表示するため実害がない）と、CommonMark オートリンク（`<https://...>`・`<user@example.com>`。Pass 3 のベア URL 対応で明示的に使われる記法）を除外した上で、`<tag ...>` 形式の生 HTML タグを1件でも検出したら blocking ERROR とする。タグの許可リスト（例: `<br>` だけ許可）は意図的に持たない — 「危険なタグだけ禁止」ではなく「生 HTML自体を一切禁止」という設計判断のため、サニタイズによる許可リストという (a) 案の性質を部分的に持ち込まないようにした。

**サニタイズ（許可リスト）は採らない** — 許可すべき生 HTML タグがそもそも存在しないので、許可リストを維持するコストに見合うメリットがない。**経路A（レビュー前の自動マージ・公開）の見直しも採らない** — このリスクはマージ時点で機械的に排除できるため、中核設計をこの 1 つのリスクのために変える必要はない。

詳細は `docs/DesignDoc-ScriptSpec.md`（`check_raw_html.py` の仕様）・`docs/DesignDoc-pipeline.md` §7（品質ゲート一覧への追加）を参照。

### 8.7 `tags` による多軸フィルタリング

`tags` フィールドが読者にとってどう機能するかは、Quartz v5（v5.0.0）本体と `quartz.config.yaml` が参照する `quartz-community` 配下のプラグイン（`tag-page`・`tag-list`・`search`・`content-index`）のソースと、`tags` を持つテストページでの実際のビルド出力（生成 HTML・`contentIndex.json`・コンパイル後の検索スクリプト）で確かめてある。ページへの `tags` の付与ルールは `docs/DesignDoc-data.md` §4.1 にある。

**確認できた挙動**:

| 機能 | 挙動 | デフォルト状態 |
|---|---|---|
| タグページ（`tag-page` プラグイン、`/tags/<tag>/`） | タグ1つにつき1ページを自動生成（例: `/tags/outdoor/` に `outdoor` を持つページのみ列挙）。`/tags/` は全タグの一覧＋各タグの内訳をまとめて表示。**単一タグの閲覧のみ**— 複数タグの AND/OR 絞り込み UI はこのページ自体には存在しない | 有効（WikiCommit テンプレートも同じ） |
| タグ一覧コンポーネント（`tag-list` プラグイン。ページ本文直下にタグクラウドを表示） | ページタイトル・メタ情報の直後、本文の直前に `<ul class="tags">` としてタグクラウドを表示し、`/tags/<tag>/` への内部リンクとして機能する | **有効**（WikiCommit の配布テンプレートで `enabled: true`。アップストリームの `quartz.config.default.yaml` では `enabled: false`） |
| 全文検索（`search` プラグイン、FlexSearch ベース、ツールバーに常設） | 検索ボックスに `#tag1 #tag2 キーワード` と入力すると、**指定した全タグを持つページに絞り込む（AND）**。自由文検索と組み合わせ可能。`#` を入力するとタグ名の自動補完ドロップダウンが出る。**OR 結合はサポートされない**（`parsed.tags.every(...)` による積集合のみ。`quartz-community/search` の `search.inline.ts` で確認） | 有効 |
| 検索インデックス（`content-index` プラグイン、`static/contentIndex.json`） | 各ページの `tags` 配列を正しくシリアライズしており、上記の `#tag` 絞り込みの検索対象になっている | 有効 |

**結論**: 「タグによる多軸フィルタリング」自体は Quartz v5 の標準機能（`search` プラグインの `#tag` 構文）としてすでに実装されており、AND 結合の複数タグ絞り込みが実際に機能する。カスタムコンポーネントの新規実装は不要と判断する。

**「タグのままで十分か、ページ化すべきか」の判断基準**（付与ルールとは別軸。「タグに退避したまま実体ページを持たない概念をどう扱うか」への回答）:

- タグのままで十分な用途: 横断的な絞り込みラベルとして使われるだけで、それ自体の説明・定義を必要としない概念（例: `outdoor`/`indoor` のようなカテゴリ）。`search` の `#tag` 構文が実際に機能するため、複数タグを組み合わせた絞り込みという用途は標準機能で満たされる
- ページ化すべき用途: そのタグ自体に固有の説明・定義・関連ページへの WikiLink が必要な概念（`schema:DefinedTerm` 等の独立ページに値する内容）。タグは frontmatter の平文文字列に過ぎず、WikiLink・本文・出典を持てないため、内容を持つべき概念をタグに逃がし続けると本文としては永久に存在しないままになる

#### タグの発見可能性

`#tag` 構文は便利だが、読者がそれに気づく手掛かりが要る。2 つを置く。

1. **`tag-list` を配布テンプレートで有効にする**（`.claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml`。`position: beforeBody`・`priority: 30`）。読者がどんなタグが存在するかを、`/tags/` ページの URL を知らなくても見られる。
2. **検索ボックスのプレースホルダーに `#tag` のヒントを出す**。`search` プラグインの `SearchOptions`（`enablePreview`/`fieldPriority` のみ）にはプレースホルダー文言を上書きする YAML オプションが無いため、フォーク（`../quartz-plugins/wikicommit-search`。他の `wikicommit-*` と同じフォーク方式）で行う。
   - **フォークの footprint は最小にしてある**。FlexSearch ベースの検索 UI 本体（`search.inline.ts`）・スタイル・30 ロケール分の i18n ファイルは上流から無改変でコピーし、`WikiCommitSearch.tsx` のプレースホルダー算出処理だけを `${searchBarPlaceholder} (#tag: ${tagFilterHint})` に変えている。`tagFilterHint` は全 30 ロケールに既存定義済みの文字列（例: en-US "Filter by tag" / ja-JP "タグでフィルター"）なので、新規の翻訳文字列は無い。生成 HTML には `placeholder="Search for something... (#tag: Filter by tag)"`（en-US）・`placeholder="何かを検索... (#tag: タグでフィルター)"`（ja-JP）が出る。
   - **`quartz/` submodule 内のファイル（`quartz/styles/custom.scss` 等）を編集しない** — CI が毎回フレッシュに `git submodule update` するため、その場限りの変更は失われ配布物にならない（WikiCommit の配布物は `.claude/skills/wikicommit-init/scripts/templates/` 配下のみ）。**検索ツールバーに静的ヒントの別コンポーネントを足す形も採らない** — 求めるのは検索ボックスの `placeholder` 自体である。

3. 上記2点の変更は `wikicommit-serve` Skill（`npm run build`/`preview`）が既存の `../quartz-plugins/*` ローカルパス解決の仕組みをそのまま使うため、他プラグインと同様に追加のビルド手順は不要。

### 8.7.1 グラフビューの動的フィルタ（`wikicommit-graph` フォーク）

`ai-driven-dev-wiki` パイロットの公開グラフで、ページ数が増えると全体を俯瞰できなくなる症状が2つ観測された: **(1) 多言語翻訳すると言語ごとに塊ができる**、**(2) 言語間で共通するタグがハブ化して他の有力なリンクが埋もれる**。

**この2つは同じ構造の裏表である**。`tags` は言語中立な英語識別子で翻訳ページも同じ値を持つ一方（§4.1・§4.2）、本文 WikiLink は `convert_wikilinks.py` が同一言語を優先して解決するため ja→ja / en→en のエッジしか基本的に出ず、原文と翻訳を結ぶ唯一の公式リンクである `translated_from` は frontmatter でありエッジにならない。**つまりタグは言語クラスタ間を繋ぐ唯一の橋であり、だからハブに見える** — グラフは構造を正直に描いている。
**素の `github:quartz-community/graph` では対応できない**。`D3Config` が持つのは `drag`/`zoom`/`depth`/`scale`/`repelForce`/`centerForce`/`linkDistance`/`fontSize`/`opacityScale`/`removeTags`/`showTags`/`focusOnHover`/`enableRadial` がすべてで、ページ単位の除外・言語・型・次数のフィルタをいずれも持たない（`removeTags` / `showTags` は upstream ではリンク構築でしか効かない。フォークはこの 2 キーを `filterNodes()` 側へ移してある — 下記「タグノードはノード集合の側で切る」）。しかもこれらはビルド時に `data-cfg` 属性へ JSON として焼き込まれ、UI から変更する手段がない。

**フォークの重さは差分ではなく足回りにある**（`package.json` の quartz マニフェスト・`tsup.config.ts`・`tsconfig` 2種・`eslint.config.js`・`vitest.config.ts`・`types/`）ため、追加する機能の数によらず同額である。したがって「`showTags` の動的トグルだけ」のためにフォークするのは割に合わず、逆に既存オプションだけで足りるなら YAML に焼き込むのが正しい。**判断は「フォークするか/しないか」の二択**であり、するなら言語・型・次数まで入れるのが費用対効果的である — `wikicommit-graph` は後者を採っている。

**808行の `graph.inline.ts` には D3 force simulation と PixiJS の描画本体がある。フィルタの動的化はそこに一切触れずに実現できる**（描画本体に触れているのは、後述のノードの形とラベルの不透明度の 2 件だけである）。動的化に必要な土台が既に揃っているため:

1. **設定は毎回読み直される** — `renderGraph()` の中で `JSON.parse(graph.dataset["cfg"])` している。起動時に一度読んで保持する作りではないため、`dataset.cfg` を書き換えて再レンダーすれば新しい設定が効く
2. **絞り込みのチョークポイントが1箇所に集約されている** — `neighbourhood` 確定後・`nodes` 構築前。リンク生成は既に両端を `neighbourhood.has()` でガードしているため、`neighbourhood` から要素を削るだけで下流（ノード生成・リンク生成・力学シミュレーション・衝突半径・描画）はすべて自動的に辻褄が合う
3. **再レンダー経路が既にある** — `showGlobalGraph()` が `cleanupGlobal()` → `renderGraph()` を呼ぶだけ

上流からの変更はソース中に `WikiCommit:` として印を付けてある。設定の読み取り・`neighbourhood` の絞り込み・コントロールバーの構築・クリック除外リスト・凡例・タグ疑似リンクの 2 分岐は描画本体の外側にあり、**描画本体に触れているのはノードの形による種別の区別とラベルの不透明度の一本化の 2 件だけである**。

#### 種別は形、訪問状態は色

**ノードの種別は形で区別する**: entity（と索引・root）は塗りつぶした円、tag は中空の円（`--tertiary` の 2px リング。upstream の規約）、source は四角である。色の割り当て（訪問状態）は upstream のまま変えない。

**色は使えなかった**。配布テーマのアクセントは `--secondary` と `--tertiary` の 2 つだけで、`--gray` を足しても 3 色、そのすべてが既に訪問状態（現在のページ / 訪問済み / 未訪問）に割り当て済みである。しかもダークモードでは 2 つのアクセントが `#7b97aa` と `#84a59d` で互いに近い。したがって「種類ごとに色を変える」は実際には「訪問状態の可視化を捨てる」か「テーマ外の色をフォークが独自に定義する（利用者がテーマを変えても追随しない）」のどちらかになる。

そこで **upstream が tag に対して既に採っている分担（種別＝形）をそのまま延長し、source を四角にしている**。色覚に依存せず、既存の訪問状態エンコードを壊さない。**描画側の分類は `nodeFilter` の `classifyNode()` 一本で行う** — 描画側で `nodeId.startsWith("tags/")` のように分類を書き直すと、新しい種別（source）の case を持たない二重実装になる。`classifyNode` は描画側に import しておく必要がある（この 1 行を落とすと、`@ts-nocheck` と eslint の除外対象であることが重なって型検査にも lint にもビルドにも掛からず、ブラウザが最初のノードを描く時点で `ReferenceError` になる）。四角の半辺は半径の 0.9 倍にしてある（半辺＝半径だと面積が円の 4/π 倍になり、隣の円より明らかに重く見えるため）。

**型（20 種）は形にも色にも載せない**。区別できる表現が無く、載せれば凡例が 20 行になる。型の絞り込みはコントロールバーの型フィルタが既に担当しており、そちらが「見たい型だけにする」正しい手段である。

**凡例をコントロールバーに置く**。凡例は「ページ」（形）と色 3 種（現在のページ / 訪問済み / 未訪問）の 4 項目で、タグと情報源の形の見本は対応するトグルの中に置く（下記「Sources / Tags の印はトグルが持つ」）。形も色も graph を見ただけでは推測できず、対で読むものだからである。スワッチは graph と同じテーマ変数・同じ形で描くので、片方だけがスタイル変更で置き去りになることが構造的に起きない。**形の側のスワッチだけは `--darkgray` を使う** — 3 つの状態色のどれでもないため「4 つ目の状態」と読まれず、かつ「ページ」と「未訪問」が同じ灰色の円にならない。形と色の 2 つの軸の間には改行を入れ、2 群として読めるようにしてある。ラベルは既存の `data-labels` 経路に乗り、`i18n/index.ts` の `Record<string, typeof enUS>` が全ロケールへの追加を型で強制する。

**採らなかった案**: 型名からハッシュで色相を振る（テーマ外の色が混ざり、20 種は色相で区別できず、色覚にも依存する）／色を種別へ付け替えて訪問状態を捨てる（訪問済みの可視化は upstream の機能であり、グラフを回遊の手掛かりにしている読者から取り上げることになる）。

**ブラウザでの目視確認は行っていない**（このリポジトリに Quartz 本体が無い）。機械的に検証してあるのは、分類が `classifyNode()` 一本であること・source が `rect` で描かれること・全ロケールが凡例ラベルを持つこと・スワッチがテーマ変数のみを使い訪問状態側が円のままであること（`test/legend.test.ts`）に限られる。

#### コントロールは自分の意味を説明する

- **次数の 2 入力はそれぞれ自分のキャプション（`degreeMin` / `degreeMax`）を持つ**。1 つのキャプションの下に区別のつかない数値入力を 2 つ並べると、どちらが下限か分からない。ラッパーは `<label>` ではなく `<div>` にする（各入力が自前の `<label>` を持つので、`<label>` の入れ子になる）。2 入力は縦に積まず横に並べる（バーは流しで伸びるので、2 行目はこの 1 フィールドだけを他より高くする）。`title` には「0 は境界なし」だけを置き（共有の 1 キー `degreeNoBound`）、ハードコードの英語を置かない。
- **`sync()` のキャレット保護は変えない**。値の書き戻しは「文字列が実際に異なるときだけ書く」（`change` が Enter で発火したときにキャレットが飛ぶのを避けるため。下記「バーは作り直さず、値だけを書き戻す」の `{field, sync}` 契約）。
- **タグは訪問の有無に関わらず `--tertiary`（「訪問済み」の色）で描かれる**（描画側の色の分岐が `visited.has(d.id) || classifyNode(d.id).kind === "tag"`。upstream の挙動）。**挙動ではなく説明で扱う** — タグから色の例外を外すと、凡例の文言を揃えるためだけに upstream の意図（タグは回遊の手掛かりであって訪問対象ではない）を壊す。その旨は Tags トグルの `title`（`legendTagsAlways`）に置く。
- **「訪問済み」の定義は凡例の `title`（`legendVisitedHint`）に置く**。実体は `localStorage` の `graph-visited` キーで、述べているのは「このブラウザでそのページを開いたことがあるか」だけである — セッション単位ではない（タブを閉じても残る）・サーバ側の記録ではない・`review_status` とは無関係（`reviewed` は「人が読んだ」という Wiki の記録）・端末やブラウザをまたがない。どれも読者が誤解しうる方向である。
- **キャプションと `title` の使い分けは「そのコントロールを操作するのに要るか」で決める**。下限か上限かは入力する前に知る必要があるので可視のキャプションに、タグの色の例外と `graph-visited` の定義は読み解くときの補足なので `title` に置く（凡例に散文を足すとバーの形が崩れ高さが増える）。`aria-label` は可視ラベルを置き換えてしまうため使わず、`aria-description` は対応が広くない。`title` はホバーしないと出ず、スクリーンリーダーでの読み上げも実装依存であることは既知の限界である。
- **これらは読者向けの文字列なので翻訳する**（コントロールバーは公開サイトの UI であり、読み手で決める線引きに従う）。ヒントの `0` は ASCII のまま書く — `input.value` は全ロケールで `String(0)` なので、ローカライズした数字（ペルシア語の `۰` 等）を使うと、説明している入力欄に決して現れない文字を名指すことになる。テストが全ロケールについてこれを固定する。
- **`graph-visited` を `review_status` に結び付けない**（別の軸であり、混ぜると `reviewed` の意味が弱まる）。**2 入力を 1 つのレンジスライダーにしない** — 上限は「ハブを隠す」ために使われる以上、具体的な数値を打てることに意味がある。
- 機械的に固定してあるのは、ヒントが `labels` 経路に乗っていること・ハードコード英語が残っていないこと・キーが 30 ロケールに揃っていること・キャレット保護が無変更であること・`<label>` の入れ子が無いことである（`test/legend.test.ts`）。ブラウザでの目視確認は行っていない。

#### Sources / Tags の印はトグルが持つ

- **Sources トグルには四角、Tags トグルには中空円のスワッチをボタンの中に置く**（`buildToggle()` の任意の 4 引数目 `swatch`〈`{modifier, hint}`〉）。凡例は「ページ」＋色 3 種の 4 項目で、タグ・情報源の行を持たない。バーに同じ語が 2 回（押せるトグルと押せない凡例の行）出ない・トグルが自己説明的になる（「情報源」という語だけでは四角いノードのことだと分からない）・凡例が非対話のまま保たれる・バーが短くなる。
- スワッチは**凡例と同じクラス**（`global-graph-controls__legend-swatch--*`）を使うので、2 つの印がスタイル変更で食い違うことは構造的に起きない。凡例のスワッチと同じく `aria-hidden="true"` で、スクリーンリーダーにはラベルだけが読まれる。タグ色の例外を述べるヒント（`legendTagsAlways`）はタグの印と一緒に Tags トグルの `title` に置く（キー名は 30 ロケールの互換のため据え置く）。押された状態の塗り（`--secondary`）の上では `--darkgray` の四角がライトモードで沈むため、押下中だけ `--light` の 1px リングを付ける。
- **トグルが何を出し入れするかの説明はコントロールの隣に属する** — 状態はコントロール自身が持つべきである（下記「コントロールバーは面を持ち、トグルは塗りで状態を示す」）のと同じ原則である。`{field, sync}` 契約は変えていないので、書き戻し経路はスワッチを知らない。
- **凡例の「ページ」の行は残す**。ページには対応するトグルが無い（off にすると entity ノードが全て消え、繋がっていた tag / source も prune で道連れになり、実質「グラフを空にする」ボタンになる）ので、印の置き場が凡例にしか無い。**トグルを off にしてもスワッチは消えない**（ボタンの塗りが消えるだけ）ので、「四角 ＝ 情報源」の説明は状態に関わらず残る。
- **凡例の項目自体をボタンにする案は採らない** — 凡例の一部だけが押せる状態になり、「ページ」は見た目が最も近いので押せそうに見えて押せず、色の項目にはトグルという概念自体が無い。「凡例は説明・コントロールは操作」という読者の最初の仮説を部分的にだけ裏切る形である。
- **形を持たないトグルにはスワッチを付けない**。索引ページは円で描かれ entity と見分けが付かない（索引のトグル自体も置かない。下記「型インデックスと言語ルートは既定で落とす」）。
- 機械的に検証してあるのは、凡例にタグ・情報源の行が無いこと・凡例が非対話であること・トグル内のスワッチが凡例と同じクラスで `aria-hidden` であること・押下中のリングがテーマ変数のみを使うこと（`test/legend.test.ts`）に限られる。ブラウザでの目視確認は行っていない。

#### ラベルの不透明度はホバーが先・ズームが後

数百〜千ノード規模（`wikicommit/ai-driven-dev-wiki` の 969 ノード。2026-09-21 の実測）のグローバルグラフでは、倍率だけでラベルの表示を決めると、既定の倍率ではラベルが 1 つも出ず、読める倍率まで寄せると全ノードのラベルが一斉に出て判読できない。ホバーしたときに、繋がっている相手の名前が読めなければならない。

**`renderLabels()` が `label.alpha` の唯一の書き手である。** ホバー経路が立てる `active` を `renderNodes()`（1 / 0.2）・`renderLinks()`（1 / 0.2）と同じく `renderLabels()` も読む。優先順位はホバーが先・ズームが後で、判定そのものは `src/util/labelOpacity.ts` にある（`nodeFilter.ts` / `controlBar.ts` を切り出したのと同じ理由 — inline スクリプトは `@ts-nocheck` かつビルド時に esbuild ローダーが組み立てるため、中身は型検査も単体テストもできない。**このリポジトリではグラフを目視できない**以上、真理値表を直接 assert できることが唯一の検証手段になる）。

**非近傍のラベルは 0 にする** — ノードとリンクが使う 0.2 ではない。0.2 の点はグラフの形を与え続けるが、0.2 の文字は判読できない重なりであり、そしてホバーする理由は名前を読むことである。

**`focusOnHover: false` では upstream の挙動（ズームだけがラベルを決める）に戻る。** ホバー中のノード自身のラベルは upstream でもこのフラグに依らず 1 になっていたので、そこも変えていない。

**ズームハンドラは `renderLabels()` を呼ぶだけである。** ラベルコンテナを走査しながら active なラベルの配列を `.indexOf()` で探す形にしない（969 ノードではズームやパンのたびに約 100 万回の比較になる）。現在は 1 回の線形走査で、ホバー中にズームしてもホバーが描いた区別は消えない。

**`pointerover` / `pointerleave` で alpha を退避・復元しない。** `renderLabels()` が毎回すべてを導出する以上不要であり、退避・復元を置くと `label.alpha` の書き手が 3 つ目として残る。

**生成時の `label.alpha = 0` だけは残す。** 最初の `renderPixiFromD3()` より前のフレームのための初期値であり、「ラベルの不透明度はどうあるべきか」についての 2 つ目の意見ではない。テストはこの 1 件を例外として明示的に数える。

**クリックによる選択の固定は入れない。** ホバーだけだとマウスを離した瞬間に消えるため読み比べができないが、`graph.inline.ts` にはクリックでページへ遷移する既存の挙動があり（`dragStartTime` でドラッグと区別している）、そこへ分岐を入れるのは**描画本体の中でも最も壊れやすい場所**に触ることになる。**`opacityScale` の式（upstream）と `fontSize` の既定も変えない** — 読めなさの主因は文字の大きさでも係数でもなく、出る条件だった。

**ブラウザでの目視確認は行っていない**。機械的に固定してあるのは、真理値表（ホバー / 近傍 / 非近傍 / `focusOnHover` off の 4 分岐と、ズームのランプが upstream のままであること）と、inline スクリプト側の構造（`label.alpha` の書き手が生成時の 1 件と `renderLabels()` だけであること・`renderNodes()` と同じ `active` を読むこと・`focusOnHover` で分岐すること・退避復元とズーム側の代入が無いこと・係数 `3.75` の写しが残っていないこと）である。

#### グローバルグラフのラベルは画面内の件数の上限で決める（`labelLimit`）

ホバーしていないときのラベルを倍率だけで決めると、件数を見ていないため、同じ倍率でも 50 ページの Wiki ではちょうどよく 1000 ページの Wiki では画面のほぼ全体が文字になる。中間の倍率では全ラベルが半透明で重なり、形も名前も伝えない。**グローバルグラフでは、ホバーしていないときのラベルを `labelLimit`（画面内に出すラベルの上限）で決める**。

- **選び方**: 画面（ビューポート）内のノードが上限以下なら全部、超えるなら次数の大きい順に上限件数だけ。**ページノードを先に選び、タグ・情報源ノードはページで枠が余ったときだけ次数順で埋める**（ハブ化したタグが読者の読みに来たページから上位を奪わないため）。同じ次数は id 順で、フレーム間で選ばれる集合がちらつかない。選ばれたラベルは 1、それ以外は 0 で、半透明の中間状態は無い。
- **ホバーが先である点は変わらない**。選択の結果は `labelAlpha()` に「ズームが決める値」の代わりに渡るだけで、ホバー中の規則（ホバー中・近傍は 1、それ以外は 0）がそのまま優先する。`label.alpha` の書き手も `renderLabels()` のままである。
- **選択は純粋関数 `selectLabels()`（`src/util/labelOpacity.ts`）にある**。ノードの座標・次数・種別とビューポート（シミュレーション座標）と上限を受け取って集合を返す。`renderLabels()` が呼ぶたびに計算し、上限が効いている間はシミュレーションの tick ごとにも `renderLabels()` を呼ぶ（レイアウトが落ち着くまでは画面内のノードが変わるため）。次数は描画対象のリンクから 1 回だけ数える。
- **`0` は「上限なし」で、倍率の規則（`opacityScale` のランプ）に戻る**。既定値は固定値 40（`quartz.config.yaml` の `globalGraph.labelLimit`。グラフ表示領域の面積から決める案は採らない）。
- **ローカルグラフには適用しない**。近傍だけでノード数が少なく、コントロールバーも出さないので、倍率の規則のままである。したがって `opacityScale` が効くのはローカルグラフと、`labelLimit: 0` のグローバルグラフだけである。
- **上限はコントロールバーから変えられ、変えてもグラフを作り直さない**。入力欄は次数の 2 入力の直後に 1 つだけ置き、凡例の行は増やさない。フィルタはノード集合を変えるので `showGlobalGraph()` で作り直すのが正しいが、上限はノード集合を変えず、作り直すとシミュレーションがランダムな初期位置からやり直してレイアウトが毎回崩れる。そのため `renderGraph()` はグローバルグラフの描画中、コンテナをキーに上限の setter を登録し（cleanup で自分の登録だけを外す）、`update()` は上限の変更だけをその setter へ渡して `renderLabels()` を呼び直す。setter がまだ無い（`app.init()` 待ちの）場合だけ作り直しに落ちる。
- **保存と Reset は他のフィルタと同じ規則に揃える** — YAML が既定、保存値（localStorage の 7 つ目のキー）は Reset まで優先する。**Reset の戻り先は固定値ではなく `quartz.config.yaml` の値**である。保存済みフィルタをマージした後の `dataset.cfg` からは YAML の値を読み戻せないため、`showGlobalGraph()` は最初のマージの前にサーバー描画の `data-cfg` を `data-cfg-default` に退避し、Reset はそこから読む。SPA ナビゲーションはコンテナをマークアップから作り直すので、退避も毎回 YAML から取り直される。
- **ラベル同士の重なり判定（ぶつかる片方を消す）は入れない**。まず件数の上限だけで足りるかを見る。
- **遡及しない**。`quartz-plugins/` は `update: overwrite` なので、次の update で届く。
- **ブラウザでの目視確認は行っていない**。機械的に固定してあるのは、`selectLabels()` の振る舞い（上限 0 で `null`・上限以下なら全部・画面外を数えない・次数順・ページ優先と余り枠の充填・同順位の id 順・上限を超えない）と `restingLabelAlpha()` の真理値表、inline スクリプト側の構造（上限をグローバルグラフだけに適用すること・選択が `renderLabels()` の中にあること・tick での再計算・上限の変更が作り直しを経由しないこと・保存キーと Reset の戻り先）である。

#### ノード分類は slug のパースで行う（`contentIndex` に型も言語も無い）

グラフが読む `contentIndex.json` のエントリは `{slug, filePath, title, links, tags, content, ...}` のみで、**任意の frontmatter は一切載らない**。したがって言語・型の判定はノードID（＝ Quartz の slug）のパースで行うほかなく、WikiCommit 固有のパス文法に依存するロジックをフォーク側に持つ。`contentIndex` に `lang`/`type` を載せる案（transformer プラグインの追加、または `content-index` のフォーク）はプラグインを1つ増やすことになり、slug パース程度で済む問題に対して割に合わないため採らない。

この分類は `src/util/nodeFilter.ts` に切り出して単体テストしてある（inline スクリプトから import する。`wikicommit-explorer` の `foldLang.ts` と同じ形）。判定順は `tags/` → `sources/` → `overview` → エンティティの 4 段で、この順序は発見的なものではなく、前3者が publish 層の予約接頭辞であることによる（下記「俯瞰ページはグラフから外す」）。エンティティの型名は**publish 後の形**である点に注意する — publish はカスタム型のパスから先頭の `custom/` を落とすため、`schema:custom/Decision` はグラフには `<lang>/Decision/<slug>` として届き、型名は `Decision` と読める（`custom/` を落とすのは先頭1つだけなので、`custom/custom/Decision` のように二重に付いた型だけは publish 後も `custom` セグメントが残る。第2セグメントの決め打ちではこの型が `custom` という1つの型に潰れるため、そこだけ第2・第3セグメントを連結する）。一方 `quartz.config.yaml` を人手で書く場合は `type:` の綴り（`custom/Decision`）を書くのが自然であり、これを弾くと該当ページが黙って全部消えるため、`types` フィルタは publish 後の綴りと `type:` の綴りの両方を受け付ける（コントロールバーが書き戻すのは常に publish 後の綴り）。

#### 俯瞰ページはグラフから外す

`content/overview/`（§8.8.1）は publish 層の予約接頭辞であり、**グローバルグラフから無条件に除外する**（トグルも凡例項目も持たない）。分類に登録しないと `classifyNode("overview/")` はエンティティ文法へ落ちて `{lang: "overview"}` になり、言語マルチセレクトに `overview` が言語として並び（単一言語 Wiki でもコントロールが出る）、実在の言語を選ぶと俯瞰ページ自体が消え、Top-N リストの数十本の発リンクでハブになり、**孤立ページ節が上位 20 件へリンクを張るためにその 20 ページが「リンクを持つページ」として描かれる** — `filterNodes()` 自身の「エンティティノードは決して prune しない — 何にも届かないページは孤立ページであり、それこそ読者が見られるべきものである」という規則を壊す。

- **トグルを与える案は採らない** — トグルの on 側に価値が無い（俯瞰ページのエッジは「ランキングに載っている」を意味し「参照している」ではなく、孤立ページ節は報告の正反対を描く）。コントロールバーは既に混んでおり、凡例の形は 3 種で埋まっている。**分類だけ直してハブ化を次数フィルタに委ねる案も採らない** — 次数フィルタは既定で効かない（`minDegree: 0` / `maxDegree: 0`）ので、孤立ページの嘘を恒久化する。俯瞰ページへの導線は root index と左ペイン最上段（§8.8.1）に残る。
- **除外は `filterNodes()` の中で、`all` を除外後の集合として作ることで行う。** `kept` から落とすと `narrowed = kept.size !== all.size` が常に真になり、既定の全体表示でも毎回 prune 経路へ入って `computeEntityDegrees()` の全走査が 2 回余計に走る（同関数のコメントが守っている早期 return を潰す）。出力は変わらないため、**これは単体テストでは守れない** — 2 つの実装は戻り値から区別できない。守るのはコードのコメントとレビューである。
- **root index（`/`）は残す。** `classifyNode()` はこれを `kind: "root"` と分類し、`filterNodes()` は除外しない。root index の発リンクは `<lang>/`・`sources`・`overview/` だけで、ハブ化もしなければ嘘もつかない。
- **`isIndex` は `false` にする。** `NodeInfo.isIndex` は「`<lang>/<Type>/index.md` の型インデックスか `<lang>` の言語ルート」と定義されたエンティティノード専用のフィールドであり、同じ予約接頭辞である `tags` / `sources` も `false` を返す。
- **既知の限界: ローカルグラフには残る。** `filterNodes()` はグローバルグラフでしか呼ばない（下記「適用範囲はグローバルグラフのみ」）ので、孤立ページのローカルグラフには「Overview」が隣接ノードとして残る。孤立かどうかを読むのはグローバルグラフであり、ローカルグラフは「このページの近傍」を見る別の面であるとして受け入れる。`data` の構築時点で落として両方から消す案は採らない（俯瞰ページ自身のローカルグラフが `data.get(url)?.title` を引けず、生の id をラベルにした単独ノードになる）。
- **`content/sources/` の索引ページは除外しない。** `_write_sources_index()` / `_write_source_dir_indexes()` も大きなハブだが、`showSources` トグルで丸ごと切れるため読者に逃げ道があり、索引を外すと prune の入力が変わって実測で決めた挙動が動く。したがって「build 生成の索引ページはグラフに出さない」という一般則は立てていない（entity 側の索引は下記「型インデックスと言語ルートは既定で落とす」が扱う）。
- **予約ツリーの登録漏れは CI で止める。** `convert_wikilinks.py` の `RESERVED_PUBLISH_TREES`（`sources` と `overview`）を正本とし、`tests/test_publish_reserved_trees.py` が各エントリが `nodeFilter.ts` と explorer の `sortTier` 2 写しの**いずれにも**現れることを検証する。grep 相当であり登録の正しさは見ない（コメント中の言及でも通る）し、`src/` しか見ないので `dist/` が古いままであることも捕まえない。捕まえたいのは「新しいツリーを作って登録し忘れる」失敗である。`tags` は Quartz が書くツリーで `convert_wikilinks.py` の所管ではなく、`assets` は非 `.md` のみでページを持たないので対象外。

#### 言語・型フィルタはエンティティノードにしか適用しない

タグノードは設計上どの言語にも属さず（ページと翻訳が同じタグを共有する）、root・source ノードも同様である。したがって1言語に絞り込んだときにこれらが道連れで消えてはならない — **消してしまうと、言語クラスタを繋ぐ唯一の橋を、言語を見比べようとした瞬間に失う**。タグは `showTags` / `removeTags` キー、sources は `showSources` キーで別に切る。build 生成の索引ページ（型インデックスと言語ルート）だけは逆で、`showIndexes` が**既定で落とす**（下記）。

#### タグノードはノード集合の側で切る

**Quartz はタグページを実ページとして `contentIndex.json` に書き出す**（`tags/agent-safety`・`tags/index` 等）。グローバルグラフのノード集合は `new Set(data.keys())` から作られるため、タグノードは `showTags` と無関係にそこへ入る。upstream の `showTags` が制御するのはもう 1 本の経路（ページ → タグの疑似リンクを積むか）だけなので、それだけで切ると**エッジだけが消えてリンクを 1 本も持たないタグノードが残る**（`wikicommit/ai-driven-dev-wiki` の 2026-09-21 の実測で 969 ノード中 123 件がタグで、全件が `links: []`）。

- **`showTags` / `removeTags` は `GraphFilterConfig` に置き、`filterNodes()` が `kind === "tag"` のノードを落とす**。絞り込みのチョークポイント（`neighbourhood` 確定後・`nodes` 構築前）に寄せる形であり、`showSources` と同じ機構になる。
- **リンク構築側は 2 分岐であり、両者は同じ規則の言い換えではない**。**グローバルグラフ（`depth < 0`）では疑似リンクを無条件に構築する** — そうしないと prune の「前」の次数（`pageDegreesBefore`）が既にタグリンクを抜かれた `links` から取られ、タグは「前」も 0 になって、「元から孤立しているノードを巻き添えにしない」ガードが逆に働く。**ローカルグラフ（`depth >= 0`）では `showTags` / `removeTags` で切る** — あちらでは `filterNodes()` が呼ばれないので、無条件に積むと Tags を off にしてもタグノードへ辿り着いてしまう。**同じ `links` 配列を両分岐が読むため、一方の都合で無条件化すると他方が壊れる。**
- **`removeTags` の照合は大文字小文字を無視する**。`removeTags` はページの `tags:` frontmatter の綴りを指す一方、公開されるタグページの slug は Quartz のスラッグ化で小文字になる。大小だけが違う 2 つのタグはどのみち 1 ページに解決されるため、畳んでも別のノードを併合することにはならない。
- **採らなかった案**: `validLinks` からタグを除外する（`showTags: true` のとき、どのページからも参照されていないタグページが描かれなくなる — 孤立していること自体が報告に値する）／`minDegree: 1` を既定にする（元からの孤立とフィルタ由来の孤立を混ぜる）／prune の条件から `pageDegreesBefore > 0` を外す（早期 return が残るうえ、元からの孤立を守るガードを外すことになる）。

**ただし、そのフィルタが繋がりを奪った tag / source ノードは落とす**。リンクは両端が残っている場合にしか描かれないため、残したこれらのノードは**リンクを 1 本も持たない点**になる。`wikicommit/ai-driven-dev-wiki` の規模（source ページだけで 100 件超）では型を 1 つ選ぶだけで画面の大半が孤立した点の雲になり、読者には「ノードが隠れた」ではなく**「リンクが切れた」**と映る。**この 2 つは矛盾しない** — 上の規則が守っているのは「まだ見えているページに繋がっているタグ」である。2 言語にまたがるタグは 1 言語に絞っても**残る側の言語のページに繋がったまま**なので、この prune では決して消えない。消えるのは「選ばれた型・言語のページを 1 つも持たないタグ」だけである。

判定は「**フィルタ後にページへ届く本数が 0 で、かつフィルタ前は 0 ではない**」の 1 つである。

**素の次数では答えられない**（素の次数版は source ノードに対して 1 度も発火しないことを実測で確認した）。公開される source ツリーは内部でリンクし合っている — `convert_wikilinks.py` の `_write_sources_index()` が全 source ページを `content/sources/index.md` から、`_write_source_dir_indexes()` がディレクトリ索引から再度リンクし、`generate_root_index()` が `sources` 自身をリンクする。これらの隣接ノードは**すべて `kind === "source"`** であり言語・型フィルタを素通りするため、**どれだけ絞り込んでも全 source ノードの次数は 1 以上のまま**になる。そこで prune が数えるのは「**entity ノードへ届くリンクの本数**」に限る — 「タグとソースは、ページを介してしか存在しない」を測れる形にしたものである。次数境界（`minDegree` / `maxDegree`）の側は素の次数を使う — あちらはコントロールバーの "Links per node" であり、読者に見えているリンクすべてを意味するためである。

この 1 つの判定が 3 つを同時に満たす:

- **孤立ページ・未使用ソースを隠さない**。元からページへ届かないノード（1 ページも生まなかった `status: failed` / `excluded` のソース、orphan ページ）はフィルタ前も 0 なので対象外である。孤立は WikiCommit が `check_orphans.py` で**報告する対象**であり、グラフがそれを黙って隠す層になってはならない
- **entity ノードは対象にしない**。選んだ型に属するページがリンクを持たないことは、そのページを隠す理由にならない
- **カスケードしない**。どの数も `kept`（prune と次数境界のどちらを適用する前）に対して 1 回だけ計算し、すべての判定を同じスナップショットから読む。下の「反復収束させない」と同じ理由・同じ形である

`minDegree: 1` でも孤立点は消えるが、ラベルが "Links per node" であるためこの用途に使えると気づく手段が無く、しかも**元から孤立しているノードを巻き添えにする**。「孤立ノードを隠す」トグルを足す案も、元からの孤立とフィルタ由来の孤立を混ぜるため 1 つ目の性質を自分で壊す — 直交する機能なので、必要になった時点で独立に足せる。

#### 型インデックスと言語ルートは既定で落とす（`showIndexes`）

**`NodeInfo.isIndex` が立つノード（`<lang>/<Type>/index.md` の型インデックスと `<lang>` の言語ルート）は、グローバルグラフから既定で落とす**。型インデックスは全ページへ機械的に `- [[Type/slug]]` を張るので、普通のページとして入れると巨大ハブになる（`wikicommit/ai-driven-dev-wiki` の公開 `contentIndex.json` の 2026-09-21 の実測で、`en/definedterm` の発リンクは 214 本、`en` 配下の実コンテンツページ 483 件の 44%。build 生成の索引ページ全体を起点とするエッジは 3,763 本中 1,160 本）。

- **`check_orphans.py` と数え方が一致する。** あちらは孤立判定で `index.md` をリンク元から除外する — インデックスのリンクは `rebuild_index.py` が全ページに機械的に張るものであり、「誰かがこのページを参照した」証拠ではないためである。型インデックスからのリンクしか持たないページはグローバルグラフで辺を持たない点として描かれ（entity ノードは prune されないので消えない）、`check_orphans.py` が孤立と呼ぶものとグラフの見た目が一致する。これが意図した見え方である。
- **既定は非表示で、`showIndexes` が戻す。** `GraphFilterConfig` / `D3Config` の `showIndexes?: boolean` は**省略時 `false`** であり、`showSources` / `showTags`（省略時は表示）とは極性が逆である。したがって実装の綴りも `!== false` ではなく `=== true` になる。

**コントロールバーには出さない — `quartz.config.yaml` でのみ戻せる**。`storeFilters()` が localStorage に書くキーは固定の 7 つ（フィルタ 6 つと `labelLimit`）で `showIndexes` を含まないため、YAML で `true` にした値が保存済みフィルタで潰れることもない。露出しない理由は、足す側の代償が大きく得られるものに実測が無いことである:

| 論点 | 露出した場合に起きること |
|---|---|
| 読者の動機 | 型インデックスをグラフに入れると巨大ハブになって構造を潰す。それを見たい読者が居るという実測は無い。**索引ページそのものはサイトのナビゲーション（Explorer・パンくず）から常に辿れる**ので、グラフから消えても読者が失うものは無い |
| 極性 | `showSources` / `showTags` は省略時に表示、`showIndexes` は省略時に非表示である。同じ見た目のボタンが並ぶと、初期状態で 1 つだけ非押下になり、「押されていない ＝ 何かが欠けている」と読まれる |
| 保存との衝突 | トグルにすると localStorage に載せる必要があり、YAML で `true` にした値が保存済みフィルタに潰されないという性質と衝突する。YAML と保存値のどちらが勝つかという、他のどのキーにも無い規則を 1 つ足すことになる |
| Reset の既定値 | Reset が `false` に戻すのか YAML の値に戻すのかを決める必要があり、どちらを選んでも他の 2 トグル（常に表示へ戻る）と振る舞いが揃わない |
| 印が無い | 索引ページは entity と同じ円で描かれるので、Sources / Tags のような形の見本を持てない。見本の無いボタンが 1 つだけ並ぶ |

**再開の条件は、グラフ上で索引ページを見たいという読者の要望が実際に現れたとき**であり、そのときは上の 4 つ（極性・保存・Reset・印）を `buildToggle()` の `{field, sync}` 契約のまま決める。運用者が自分の Wiki で常に表示したい場合は `quartz.config.yaml` の `showIndexes: true` を使う。

- **root index（`/`）は対象外である。** 条件は `kind === "entity" && isIndex` であり、`kind: "root"` の root index は残る（上記「俯瞰ページはグラフから外す」）。その結果 root index に残る発リンクは `sources` 1 本になり、`showSources` を off にすると root index は孤立点になる（`kind: "root"` は prune の対象〈`tag` / `source`〉ではないので消えはしない）。
- **除外の実装位置は俯瞰ページと同じ `all` の構築時点である**（`kept` から後で引くと早期 return を潰す）。
- **prune の挙動は動かない。** 型インデックスの発リンク先は entity ページだけであり、tag も source もインデックスをリンクしないため、tag / source の entity 次数は 1 も変わらない。**この主張はテストで固定してある** — 俯瞰ページと違い、`showIndexes` で両分岐に到達できるためである。
- **「Links per node」の数え方は変わる。** 次数境界が読む plain degree（`computeDegrees()`）から、インデックス由来の分が除かれる。既定（`minDegree: 0` / `maxDegree: 0`）の表示は動かない。機械が全ページに自動で張るリンクを「このページが持つリンク」として数えないのは、`check_orphans.py` と同じ数え方である。
- **単体テストの id は完全なエンティティパスで書く。** `classifyNode()` は単一セグメントの id を言語ルートとみなすため、`"a"` / `"hub"` のような略記のフィクスチャはインデックスとして落ちる。実運用では `content/` 直下の単一セグメントは `<lang>` か予約接頭辞しか現れないので、分類は正しい。
- **既知の限界: ローカルグラフには残る**（俯瞰ページと同じ）。ローカルグラフは「このページの近傍」を見る別の面であり、型インデックスはそこでは実際に辿れる隣人であるため受け入れる。
- **採らなかった案**: `kind: "index"` を新設する（`collectFacets()` が `kind !== "entity"` を弾くため型インデックスの言語・型がファセットから消える。既存の `isIndex` に消費者を与えるほうが小さい）／`maxDegree` で隠す（正当なハブページも巻き込み、既定 `maxDegree: 0` では効かない）／`rebuild_index.py` が `- [[Type/slug]]` を書くのをやめる（インデックスは読者が型ごとにページを辿るための実ページであり、**直すべきはグラフ側の読み方である**）／俯瞰ページと同じ無条件除外にする（型インデックスは読者が実際に辿る普通のページであり、その繋がりを見たい運用者がいてもおかしくない）。

#### 次数フィルタは1回だけ計算し、反復収束させない

ハブを隠すと隣接ノードの次数が下がるため、反復すると連鎖的にグラフが崩壊しうるうえ、ユーザーが結果を予測できない。「**いま表示されている範囲での次数**」という定義が一番説明しやすい。下限・上限の両方を持つ（「リンクが少ないものを除外」と「ハブノードを非表示」は同一機構の両端である）。上限フィルタはハブ化したタグノードにもそのまま効くため、タグ側の UI は一括トグルのみで足り、タグ個別のチェックボックスは初版に入れない（`removeTags` による恒久的・外科的な除外は従来どおり YAML で行える）。

#### 適用範囲はグローバルグラフのみ

ローカルグラフ（サイドバー、既定 `depth: 1`）には適用しない。`depth >= 0` の分岐は BFS で `neighbourhood` を構築するため、確定後に要素を削ると経路の途中を抜いて孤児ノードが残る。グローバルグラフ（`depth: -1`）は全ノードから始まるためこの問題を持たない。コントロールバーを置く物理的なスペースがあるのもモーダル側だけであり、制約と設計が一致している。

#### コントロールバーの配置と、素直に実装すると踏む落とし穴2つ

1. **`.global-graph-container` の中には置けない** — `renderGraph()` の `removeAllChildren(graph)` がコンテナを毎回空にするため、バーはコンテナの兄弟にする
2. **しかし兄弟に置くとクリックでモーダルが閉じる** — `documentClickHandler` が `.global-graph-container` / `.global-graph-icon` の外側のクリックで `hideGlobalGraph()` を呼ぶため、除外リストに `.global-graph-controls` を追加する必要がある

#### コントロールバーは面を持ち、トグルは塗りで状態を示す

バーは `.global-graph-container` の**外**に置くしかない（`renderGraph()` が毎回コンテナを空にする。上記の落とし穴 1）ため、面を与えないと `.global-graph-outer` の `backdrop-filter: blur(4px)` 越しに**モーダルを開いたページの本文の上へ直接浮く** — 背景が毎回違うことが、コントロールがコントロールに見えない主因だった。`background-color: var(--light)` / `border: 1px solid var(--lightgray)` / `border-radius` をコンテナと同じ 3 宣言で与え、2 枚のパネルとして読めるようにする。

Sources / Tags のトグルは **`aria-pressed` を持つ 2 状態のボタン**である。on と off の差は「チェックマークの有無」ではなく**塗りの有無**という面積のある差になり、バーの `font-size: 0.8rem` でも読める。Reset と同じ見た目の語彙になるため、バー全体が 1 つのコントロール群として読める。ネイティブの `<button>` にするのは、Tab・Space・Enter とフォーカスリングを自前で実装せずに保つためである。`buildToggle()` が返す `{field, sync}` の契約は変えない（下記「バーは作り直さず、値だけを書き戻す」の経路はトグルの見た目を知らない）。

**塗りの色は「両テーマで反転する変数どうし」で組む。** `--secondary` と `--light` はどちらもテーマで反転する（配布テーマで light: `#284b63` / `#faf8f8`、dark: `#7b97aa` / `#161618`）ため、片方が暗く片方が明るいという関係が両テーマで保たれる（実測コントラスト 8.72:1 / 5.89:1）。**hover で別のテーマ色へ差し替えてはならない** — `--tertiary` は最初の候補だったが**両テーマとも `#84a59d` で不変**であり、文字色の方だけが反転するため両方では読めない（ライトテーマで `--light` に対し実測 2.53:1、AA の 4.5:1 を下回る）。相対的な調整（`filter: brightness(0.92)`）にはこの非対称が無く（9.55:1 / 5.01:1）、押下状態が確立した色相もそのまま保てる。

`select, input` の一括指定は `select, input[type="number"]` に限定する。素の `input` はトグルにも当たり、`appearance: none` が無い以上 `background-color` / `border` がそこで効くかはエンジン依存で、ブロックを読んでも適用されるのかどうか分からない。

**トグルの状態をグラフ側（ノードの見え方）で伝える案は採らない** — グラフは結果であって設定の表示面ではなく、`showSources` を off にしたとき「消えたのか、元から無かったのか」を区別する手段がグラフ上に無い。状態はコントロール自身が持つべきである。

**バーとコンテナは `.global-graph-inner` というラッパーの中に置き、矩形の定義を 1 箇所に寄せる**（上の落とし穴 2 つはそのまま残る）。バーとコンテナをどちらも `position: fixed` にして同じ中央矩形に別々に手計算で合わせると、バーが使える縦幅が上に空く帯（10vh）に固定され、同じ数字を 2 箇所に持つ構造が次に高さを触ったときに同じ形で再発する。キャップを外しても `.global-graph-outer` の `overflow: hidden`（`backdrop-filter` があるため、これが fixed な子の containing block でもある）に切られるだけで解決しない。

`.global-graph-inner` が `position: fixed` で中央・`80vw × 80vh`・`display: flex; flex-direction: column` を持ち、バーは `flex: 0 0 auto`（内容なりの高さ）、コンテナは `flex: 1 1 auto; min-height: 0` で残りを取る。**`min-height: 0` は必須である** — flex アイテムの既定 `min-height: auto` は内容より縮まないため、バーが高くなるとコンテナがラッパーの下へはみ出す。

**バーは `max-height: 50%` + `overflow-y: auto` + `min-height: 0` を裾の保険として持つ** — `flex-shrink: 0` である以上、ビューポートが低く（横向きのスマートフォン・高さを半分にしたウィンドウ・ページズーム 200%）`size="8"` のリストが 2 行に折り返してバーが 80vh を超えると、グラフが 0px に潰れ、バー下端の Reset ボタンが `.global-graph-outer` の `overflow: hidden` の外へ押し出されてどこからも触れなくなる。通常の縦幅では発動しない。

**PIXI 側の描画コードは無改修だが、`renderGraph()` の採寸位置だけは動かした** — `graph.offsetWidth` / `Math.max(graph.offsetHeight, 250)` を読むのを **`renderControls()` の後**にしている。コンテナの高さがバーの高さに依存するようになったためで、**モーダルを初めて開いた時点でバーはまだ空のプレースホルダー**であり（`.global-graph-controls:empty { display: none }` で畳まれている）、その位置で測ると PIXI に 80vh 丸ごとを渡してしまい、直後に `renderControls()` がバーを埋めた分だけキャンバスがコンテナの下へはみ出す。2 回目以降の再描画はバーが既に埋まっているため正しく、**最初の 1 回だけが誤る**という形で現れる。

**クリック除外リストには `.global-graph-inner` も入れる**。バーとコンテナの隙間（ラッパーの `gap`）はモーダルの内側であり、そこを踏んで閉じるのは「あと 1 クリック足りない」種類の驚きになるため、閉じない側に倒す。モーダルを閉じる 3 経路（背景クリック・Esc・アイコン再クリック）はいずれも変わらない — 背景は `.global-graph-outer` の余白であり、ラッパーの外側なので閉じる。

複数選択リストの行数上限は `8` である（型が 20 種ある Wiki を操作できる窓。ラッパー化によってバーが内容なりの高さを取れるので意味を持つ）。**採らなかった案**: 数値をずらすだけ（コンテナとキャップの高さを個別に変える。同じ数字を 2 箇所に持つ構造こそが原因である）／バーをグラフの上にオーバーレイする（グラフを隠す。グラフは俯瞰のための面である）／折りたたみにする（常用しない操作向けの形であり、フィルタは連続操作するもの — 下記の値の書き戻しがフォーカスとスクロール位置を保つのはそのためである）。

**バーの中身はビルド時の TSX ではなく inline スクリプト側で組み立てる** — 言語・型の選択肢一覧は `contentIndex` から導出するものであり、それを持っているのはスクリプト側だけであるため。TSX 側は空のプレースホルダーと i18n ラベルを出すに留める。選択肢一覧は**フィルタ適用前**のノード集合から作る（1言語に絞った後に、戻るための他言語がドロップダウンから消えては困る）。

#### 状態の永続化

`dataset.cfg` の書き換えは SPA ナビゲーション（`nav` イベント）で DOM がサーバー描画のマークアップから作り直されると失われるため、フィルタ状態は localStorage に保持する（同スクリプトは既に `graph-visited` キーで localStorage を使っており前例がある）。

#### バーは作り直さず、値だけを書き戻す

**バーは操作のたびに作り直さない**。バーのどの操作も `update()` → `dataset.cfg` 書き換え → `showGlobalGraph()` → `renderGraph()` → `renderControls()` という経路を通るため、`renderControls()` が冒頭で `removeAllChildren(bar)` してバー全体を組み直すと、1 回のクリックやキー入力ごとにバーの DOM が丸ごと差し替わり、複数選択リストのフォーカスとスクロール位置が毎回失われる。

**バーの構造を決める入力は、操作によって変わる設定より狭い**: (1) 選択肢一覧（`collectFacets()` の結果。フィルタ適用前のノード集合から作るため、1言語に絞っても変化しない）と (2) ラベル（サーバー描画の `data-labels` から読む）の2つだけであり、どの option が選択されているか・トグルの状態・次数の上下限は**値**にすぎない。そこで両者から署名（`src/util/controlBar.ts` の `controlsSignature()`。単体テスト付き）を作り、前回と同じならバーを作り直さず各コントロールへ値を書き戻す。

**この書き戻しは省略できない**。作り直しをやめるだけだと、Reset ボタンが `dataset.cfg` を初期化する一方でコントロールの表示が古い選択のまま残り、**表示と実際のフィルタが食い違う** — フォーカスが飛ぶより悪い状態になる。同じ理由で、`update()` はバーの構築時に捕捉した `config` ではなく `graphContainer.dataset["cfg"]` を毎回読み直す（バーが1回のレンダーより長生きするようになった以上、捕捉した値は1回以上前の状態であり、そこへパッチを重ねると直前の変更を黙って巻き戻す）。

**再利用の条件は署名だけではなく、`graphContainer` の同一性も見る**（署名そのものは facet 一覧とラベルだけから作る文字列であり、DOM 要素は含めない — 要素は `controlsSignature()` の外で `===` 比較する）— バーに登録したリスナーはこの要素を閉じ込めているため。SPA ナビゲーションでモーダルのマークアップごと作り直された場合はバー要素自体が新しくなり、状態を引く `WeakMap` が空振りして自然に再構築へ倒れる。テーマ変更（`themechange` → `showGlobalGraph()`）では要素が同じままなので書き戻し経路に入り、`showGlobalGraph()` が localStorage の値を `dataset.cfg` へ再適用した後の設定が表示に反映される。

**ブラウザ上での動作確認は行っていない** — このリポジトリには Quartz 本体が無い。上記は inline スクリプトのコードからの読み取りに基づき、機械的に検証してあるのは署名の同値性（`src/util/controlBar.test.ts`）に限られる。

### 8.8 サイト概要表示（総ページ数・レビュー済み件数）

公開 Wiki サイトを訪れた読者が「このWikiには全部で何ページあるか」「そのうち何件が出典と照合され、何件を人が読んだか」を一目で把握できるよう、root index に件数を出す。新規プラグインは追加せず、既存の `wikicommit-banner`（§8.4 の review_status バナーと同一コンポーネント）が描く。

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

**ラベルと補足文**: 件数のラベルは `人が読んで確認` / `Read and checked by a person`（i18n の `siteSummaryReviewed`）で、その直下に何を数えた値かを述べる 1 行（`siteSummaryReviewNote`）を置く。補足文は数字を「ラベル名」で指す（「『人が読んで確認』はそのうち…」。「上の数字は」と書くと、指示対象が複数になったときに曖昧になる）。

- **数字は隠さない**。`0` を含めて出すのは正直さの表明である。ただし裸の数字だけだと初見の読者には「誰も関心を持っていないプロジェクト」に読めるので、**数字と補足文は必ず対で出す**。
- **参加の呼びかけ・リンクは加えない** — この Wiki は外部レビュアーを募らないため、参加できない相手への呼びかけになる。
- 俯瞰ページ側（§8.8.1）も同じ扱いで、2 つの文言は互いに矛盾させない（root index が俯瞰ページへリンクしているため、読者は続けて両方を見る）。

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

#### 言語選択リストと `site_description`

多言語 Wiki の root index は言語選択リストを本文に持ち、各行にその言語の説明と件数を添える。

**読者向けのサイト説明は `config.yml` の `site_description` が持つ**（**言語コード → 1〜3 文の文字列**のマッピング。`docs/DesignDoc-data.md` §3.3）。`convert_wikilinks.py` の `load_site_description()` が読み、`generate_root_index()` が**フロントマターではなく本文に**書き出す — 言語選択リストの各行に、その言語の説明を添える形になる。

```markdown
## 言語を選択

- [it](./it/) — Una base di conoscenza dedicata al Decameron di Giovanni Boccaccio.
- [en](./en/) — A knowledge base on Giovanni Boccaccio's Decameron.
- [ja](./ja/) — ジョヴァンニ・ボッカッチョ『デカメロン』の知識ベース。
```

- **`theme` を読者向けの表示に使わない**。`theme` は LLM 向けの内容スコープ指示であり（読むのは `wikicommit-generate` Pass 2c と `wikicommit-collect`。`docs/DesignDoc-data.md` §3.3）、読者向けに書かれた文ではない。値は 1 本しかないため書かれた言語のまま全読者に届き、生成器への命令文がトップページに出ることになる。`theme` を多言語化する案も採らない（読者向けに書かれていない文を訳す作業になる）。
- **バナーに描かせず本文に書く**。(1) 値が言語ごとのマッピングであり、フロントマターの単一文字列には収まらない。(2) 各説明をその言語のリンクの直下に置けば「テーマ:」に相当するキャプション自体が不要になる — **説明文はどの言語で書かれていてもその言語の読者に届くが、キャプションは届かない**。
- `langs` が 1 つだけで言語選択リストを出さない場合は、`primary_lang` の説明を「Wiki トップ」リンクの直下に 1 行だけ添える。**欠落は静かに落とす** — ある言語の説明が無ければその行に説明を添えないだけ、`site_description` 自体が無ければ説明なしの出力になる。値の内部の改行・連続空白は単一の空白に潰す（1 行の箇条書きに埋め込む以上、値が持つ空行は言語選択リストを分断してしまうため）。
- **`content/sources/`・`content/overview/` へは展開しない**。この 2 つも言語中立な入口ページだが、説明文を置く必然性が薄い。

**言語リストの出所は「`targets` ∪ 実ページを持つ言語」である**（`compute_langs()`）。`targets` にあるが実ページが無い言語はデッドリンクになるので `existing_lang_targets()` で落とし（`primary_lang` はこの絞り込みの対象外で常に先頭に置く）、実ページがあっても `targets` に無い言語は足す。後者はパイプラインが自分で作る — `/wikicommit-translate <page> --lang <lang>` は `config.yml` を触らずに翻訳ページを書き、手書きのページ追加・`primary_lang` の後からの変更・翻訳後の `targets` の削除でも同じ状態になる。root index は「言語を選ぶ」ためだけに存在するページであり、そこに無い言語は初訪問の読者にとって存在しないのと同じである。

- **`compute_langs()` は和集合を返す**（置き換えではない）。`existing_lang_targets()` はその言語配下に非 removed な `.md` が 1 つでもあれば通すのに対し、`published_langs` は解決できて実際に書き出されたページからしか導けないため、置き換えるとリンクされている言語が落ちうる。実在言語は `page_stats` の `lang` から distinct を取って導く — `.wikicommit/entity/*/` のディレクトリ走査では全言語共通アセット置き場 `assets/`（`docs/DesignDoc-data.md` §3.1）を言語として拾ってしまう。Type ディレクトリの `index.md` は除外し（最後のページを削除した後に残る `index.md` だけの言語に入口リンクを出さない）、**書き出しに失敗したページも除外する**（ソースを読めなかったページは `page_stats` には載るが公開ファイルは生成されない）。view ツリーは両者とも対象に含む。
- **並び順は `primary_lang` → `targets` の記述順 → 発見された言語（ソート順）**。`targets` の順序は書き手が決めたものなので保ち、発見分をその後ろへ回す。
- **ビルド時の WARNING は出さない**。「`targets` に無い言語がある」は正当な状態（`--lang` で意図的に作った言語）でも毎ビルド点灯し続け、常時点灯する警告は読まれなくなる。
- **`check_translation_status.py` の `UNTRANSLATED`/`STALE` 判定は変えない**。こちらも `targets` を見るため未掲載言語の翻訳は陳腐化を追跡されないが、それは「翻訳対象として管理するか」という別の問い（`targets` の本来の役割）であり、恒久的に運用するなら操作者が `targets` に足すのが正しい対処である。

#### 多言語 Wiki では件数を言語別にする

**多言語 Wiki（`len(langs) > 1`）では、件数を言語選択リストの各行に言語別に出し、フロントマターの `wikicommit_page_count` / `wikicommit_reviewed_count` を出力しない**。全言語の全ページを 1 本に足した数は、それを経験する読者が 1 人もいない（選んだ先の Wiki は 1 言語分である。翻訳は同じ知識の別言語版であって知識の量ではない）うえ、翻訳の分だけレビュー済み率を希釈して信頼ラダーの表明を一律に悲観的な方向へずらす。**ページ数だけ言語別にしてレビュー済みを合算のまま残すと、この歪みは残る** — 両方を分ける。

```markdown
## 言語を選択

- [ja](./ja/)（174 ページ / 人が読んで確認 174） — 『デカメロン』の知識ベース。
- [en](./en/)（174 ページ / 人が読んで確認 0） — A knowledge base on the Decameron.
```

- **件数はリンク直後の括弧に置き、`site_description` の em dash 枠はそのまま残す**。フロントマターをマッピング化してバナー側でリストを描く案は採らない（言語別の値は 1 つのフロントマター文字列に収まらず、root index は `lang` を持たないためバナーの文言が `cfg.locale` 1 本に解決される — `site_description` を本文に置いたのと同じ理由）。ラベルは `ROOT_INDEX_LABELS` / `DEFAULT_ROOT_INDEX_LABELS` の `counts` / `counts_one`（「出典と照合」を含む形は `counts_ai` / `counts_ai_one`。下記）で、root index の他の chrome と同じく `primary_lang` 固定とする。区切り文字を含む文字列全体をラベルに持つのは語順が言語で異なるためで、`counts_one` は英語の `1 pages` を避けるためだけに分けている。
- **2 フィールドを出力しないだけでバナーのサイト概要ブロックは描画されなくなる**（`WikiCommitBanner.tsx` は両フィールドが `number` であることを表示条件にしている）。合計は出さない — 出すと問題視している数を目立たせ続ける。単一言語 Wiki は言語リスト自体が出ないので、2 フィールドもバナーの表示もそのままである。
- **補足文は本文側へ移して必ず残す**。バナーが消えれば「その数字が何を数えたものか」を述べる 1 行も消える。**数字だけ移して注記を落とすのは不可** — `レビュー済み: 0` が「誰も関心を持っていないプロジェクト」に読める問題がそのまま戻る。文言は俯瞰ページ側（§8.8.1 の `reviewed_note`）と揃える。
- **件数は `page_stats` から数える**。`main()` の単一走査が既に各ページの `lang`・`review_status`・`is_index` を積んでおり、`generate_root_index()` はその後に呼ばれるため追加の走査は要らない。Type ディレクトリの `index.md` は除外し、view ページ（`.wikicommit/view/<lang>/<slug>.md`）は `lang` 付きで入るため**除外しない** — 俯瞰ページの `言語別ページ数` と同じ数になる。**0 件の言語でも落ちない**（`<lang>/<Type>/<slug>.md` に解決できるページを 1 枚も持たない言語もリストに載りうる）。どちらも `0` を出す。
- **単一言語 Wiki の合計は `page_stats` 由来に切り替えない**。切り替えれば §8.8.1 が「許容する」と書いている差分（`<lang>/<Type>/<slug>.md` に解決できない公開済みページを含むか否か）は消えるが、そのページ群はどの集計にも数えられなくなる。
- root index はビルドのたび上書き生成されるので、表示の変更は既存リポジトリにも次のデプロイで届く（遡及の考慮は要らない）。

**実装箇所**: `.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-banner/src/components/WikiCommitBanner.tsx`（レンダリング）、`.wikicommit/scripts/convert_wikilinks.py`（集計・埋め込み。`.claude/skills/wikicommit-init/scripts/templates/scripts/` に同一内容をミラー配布）。

#### 出典と照合の件数

root index は「人が読んで確認」に加えて「出典と照合」（Pass 4 の有効な判定を持つページ数）を出す。注記が「保証ではない」とだけ述べて、残るページも出典と照合済みであることに触れないと、初見の読者には「95 枚のうち 12 枚しか何もされていない」と読める（過小表明）。

- **0 のときは出さない。これは省略ではなく正確さのためである** — 記録の仕組みより前に生成された Wiki（記録はさかのぼって作れない）と、照合の記録を持たない言語はどちらも「記録が無い」のであって「照合していない」ではなく、`出典と照合 0` はそれを誤って後者として伝える。俯瞰ページの `generate_overview_page()` と同じ扱いである。
- **多言語ではサイト全体ではなく言語別にする**（`- [ja](./ja/)（12 ページ / 出典と照合 12 / 人が読んで確認 3）`）。翻訳ページは「出典と照合」に数えない（`translated_from` の有無で分ける。§8.8.1）ので、サイト全体で数えると翻訳の枚数で薄まる。順序は**全数 → 抜取**（俯瞰ページと同じ）。
- **注記は別キーにして条件付きで出す**（`ROOT_INDEX_LABELS` の `ai_counts_note`、バナーの `siteSummaryAiReviewNote`）。文言は俯瞰ページの `ai_reviewed_note` に揃え、**照合していないもの**（網羅性・実在の人物や組織への影響・読者自身の知識との食い違い）を名指しする — 照合したものだけを述べると、`reviewed` について避けた過大表明を向きを変えて作り直すことになる。**「抜取」「サンプリング」に相当する語は読者向け表示に入れない**（`RISKY:` が実際に選別として機能しているかは実測前であり、語だけ先に出すと形式的な抽出設計の存在を含意する）。

### 8.8.1 Wiki 全体の俯瞰ページ `content/overview/`

§8.8 の root index の数字だけでは「このWikiにはどんな知識が集まっていて、何が足りていないか」に答えられない。俯瞰ページは、散らばっている集計（とくに `check_wanted_pages.py` の wanted ページ — 他ページから参照されているが実体のない slug、すなわち「不足している部分」）を読者が見られる 1 枚にまとめる。

`convert_wikilinks.py` の `generate_overview_page()` が `content/overview/index.md` を生成する。`generate_root_index()`（§8.8）・`generate_source_pages()`（`content/sources/`）と同じ **build-generated ページ**であり、`.wikicommit/entity/` に実体を持たず、ビルドのたび上書き生成される。`generate_root_index()` がこのページへのリンクを出力するため、root index が情報源一覧と俯瞰ページの両方への入口になる。

**掲載する6セクション**:

| セクション | 内容 |
|---|---|
| 全体の数字 | 総ページ数 / **出典と照合済み（AI）率** / 人が読んで確認の率 / 型数 / 言語別ページ数 / 翻訳カバレッジ と、その一覧の直下に置く 2 つの補足文（人間レビュー側と AI レビュー側） |
| 知識の中心 | 被リンク数ランキング（ハブページ Top 20）。各行に**そのページに記録されているソースの件数**を添え、一覧の直前に何を数えた値かを述べる 1 文を置く。一覧の末尾に、同じ 1 本のソースだけに立つハブが 2 件以上あればそのソースと件数を出す |
| 型別の傾向 | 型ごとの件数・レビュー済み率・平均被リンク数・孤立件数 |
| 知識の不足 | wanted ページ（参照元件数順）・orphan ページ |
| 情報源の内訳 | 種別別・`status` 別・URL ホスト別・**抽出テキストの言語別**の件数と、情報源の種別 × 生成されたページの型のクロス集計 |
| タグ | 頻度ランキング |

型別件数は「全体の数字」に重複して並べず「型別の傾向」の表が兼ねる（同じ数字を2か所に持たない）。ランキングはすべて Top N で打ち切る。1枚の `overview/index.md` に `##` セクションを並べる構成であり、複数ページへの分割は「1枚に収まらなくなってから」扱う。

**集計はすべて既存の走査に相乗りする**。`main()` の全ページ1回走査（WikiLink 変換のために元々行っているもの）で各ページの `type` / `lang` / `tags` / `review_status` / 発リンクを蓄積し、ソース側の内訳は `generate_source_pages()` の管理ファイル走査に相乗りする。発リンクは `convert_file()` が置換パスで既に `WIKILINK_RE` を走らせているため、その戻り値として受け取る（`check_orphans.py` / `check_wanted_pages.py` が各自の全再走査で同じグラフを組み立てているのに対し、ビルド内で3つ目の走査を足さない）。ソース × 型のクロス集計は `_write_source_page()` が実際にリンクした `generated_pages[]` の実体から算出する — 存在確認・`status: removed` 除外というフィルタをリンク生成側と共有し、2つ目の写しがドリフトしないようにする。

**なぜ build-generated か**: 集計結果はビルドのたび再計算される値であり、人間のレビュー対象ではない。`.wikicommit/entity/` に置くと `review_status`・レビュー追跡 Issue・`wikicommit-merge` の品質ゲートにすべて乗り、「毎ビルド変わる数字にレビュー追跡 Issue が立つ」状態になる。root index と同じく `review_status: reviewed` を明示する（`WikiCommitBanner` の未レビュー警告はフィールドが無いと `pending` にフォールバックするため。§8.4）。`.wikicommit/report/` のような第3のトップレベルディレクトリも採らない — 主要スクリプト群がいずれも `.wikicommit/entity/` 決め打ちであり、全スクリプトに分岐が必要になる。

**副作用の有無で `/wikicommit-status` と境界を引く**: `check_ingest_freshness.py` は管理ファイルに `status: outdated` を書き戻すため**ビルドからは呼べない**（CI がリポジトリのファイルを書き換えることになる）。`check_expires.py` も、判定に使う「今日」がビルド時点で凍結し再ビルドまで古い表示が残るため載せない。読み取り専用の集計のみを overview に置き、書き戻しを伴うもの・時刻依存のものは運用者がオンデマンドで実行する `/wikicommit-status` 側に残す。

#### 出典との照合の集計（AI レビュー）

ページ単位のバナーは「照合を通過した事実」だけを出し、指摘件数は出さない（§8.4）。件数が意味を持つのは集約された後であり、その置き場がこの節である。

- **出すのは 3 つ**: 有効な判定を持つページ数 / 分母（下記）、照合したモデルの一覧、そして**指摘を受けて書き直された箇所の総数**（`ai_findings`。ページ数ではない — 3 回捕まったページは 1 回のページより、この検査に歯があることをよく示す）。集計は `page_stats` の `ai_review` に相乗りし、`convert_file()` が publish 時のスタンプに使うのと**同じ 1 回のルックアップ**を読む — 2 度引くと、バナーが出しているページ集合と俯瞰ページが数えている集合が食い違いうる。
- **`reviewed` キーを流用してはならない**。あのラベルは「人による」と言い切る形であり、機械の数をそこへ載せると曖昧さが戻る。キーは `ai_reviewed` / `ai_reviewed_note` / `ai_findings` である。
- **有効な判定が 1 件も無い Wiki では行ごと出さない**（`0 / 95` とは書かない）。ゼロは「照合が走って全部落ちた」と読めるが、実際には記録が残っていないだけである（記録はさかのぼって作れない）。**補足文も同時に出し入れする** — 数字だけ出して「何を照合したか」の 1 行を落とすと、数字だけが独り歩きする。
- **分母は翻訳ページを除いたページである**。翻訳ページは `sources` を持たず（`translated_from` で継承する）、ソースとの照合の対象にならない。分母に入れると、原文を全部照合済みの Wiki が 1 言語に全訳した瞬間に 50% に下がって見える — 翻訳を足すという Wiki を良くする行為が品質の低下として現れる。**分子も同じ条件で絞る**（翻訳ページに `/wikicommit-review` を AI が走らせれば `kind: ai` の記録が書かれ、分母だけを絞ると 100% を超えうる）。
- **黙って外さない**。翻訳ページが 1 件以上あれば、その件数を述べる行を AI の行の直下に出し、補足文にも「翻訳ページはこの照合の対象外であり、上の割合にも含めていない」の 1 文を足す。翻訳ページが 0 件の Wiki では行も 1 文も出ない。総ページ数と「人が読んで確認」の分母は変えない（翻訳ページも人は読めるため）。補足文の主語は「出典から生成されたページ」に限定する。
- **言語別には分けない**。ここで問題なのは言語ではなく「照合の記録を持ちえないページの種類」であり、判定の軸を言語に置くと、1 つの言語に原文と翻訳が混ざる構成で再び薄まる。`translated_from` の有無で分ければ構成によらず同じ答えになる（root index が言語別にするのは、言語ごとの入口という別の目的による。§8.8）。

**翻訳ページの照合は「原文と照合済み（AI）」として別に数える**。`wikicommit-translate` は翻訳ページを原文ページと照合し `stage: translate-check` として記録する（`docs/DesignDoc-data.md` §4.8）。**「出典と照合」には混ぜない** — 照合の相手はソースではなく原文ページである。表示は 3 か所で分かれる:

| 場所 | 表示 |
|---|---|
| ページのバナー | `load_ai_review()` が `stage` も返し、`convert_wikilinks.py` が `translate-check` のときだけ `ai_review_stage: "translate-check"` を刻印する。`WikiCommitBanner` はそれを見て `aiReviewOriginalAt`（「原文と照合:」）を出す。他の stage では刻印しない |
| ルート index の言語別件数 | 翻訳ページは「出典と照合」に数えない（`translated_from` で分ける。上と同じ軸） |
| 俯瞰ページ | 記録を持つ翻訳ページが 1 件以上あれば、翻訳ページの行を「原文と照合済み（AI）: M / N」（N は翻訳ページ総数）にし、何を照合したかの補足文（`translation_checked_note`）を添える。1 件も無ければ「翻訳ページ（原文との照合は記録されていません）」の行のまま |

`load_ai_review()` は `standing_verdict()` を stage で絞らずに読むので、stage の分岐を外すと `translate-check` の PASS が「出典と照合済み」として公開される。

- **view ページ（`derived_from`）は「出典と照合」に数えている**（`synthesize-step5.5` の記録）が、照合の相手は外部のソースではなく Wiki 内の grounding ページである。ラベルの意味の問題として未解決のまま記録しておく。
- **指摘の種類別内訳**: `ai_findings` の直下に、種類ごとの件数を入れ子の箇条書きで出す。ラベルは内部の enum 名（`HALLUCINATION` 等）ではなく読者向けの言葉（「出典に書かれていない記述」「出典と食い違う記述」「手元に無い文書に依拠した記述」「その他」）にする。**母集団は `ai_findings` と同じ**で、`load_ai_review()` の戻り値が種類別の件数を返すので、ルックアップは 1 回のまま、内訳の合計は構造上総数と一致する（合わないと読者はどちらかを誤りと読む）。enum 外の値と `type` の無い指摘は推測で振り分けず「その他」にまとめ、件数が 0 の種類は行ごと出さない。
- **`page_at_fault: other` は総数からも内訳からも外す**。これは「相手ページが誤っていそう」という非ブロッキングの報告で、そのページで書き直されたものではない。判定は値が文字列 `other` と一致するかだけで、ドリフトした値（`this` / `self`）は「このページの指摘」として残す。
- **「検査を通らず公開されなかったページ」の件数**を出す（0 件なら行ごと出さない）。数えるのは「最新の `kind: ai` 記録が `result: discarded` で、かつそのページがディスクに無い」ページで、entity と view の両方（synthesize Step 5.5 も破棄する）。**`action: update` の破棄は数えない** — 旧版が公開されたまま残り、「公開されなかった」が偽になる。後の実行で通ったページも、最新の記録が pass なので数えない（`check_review_coverage.py` の `latest_discarded()` は「最新の discarded 記録」を返すので流用できず、`latest_by_kind()` で最新の AI 記録そのものが discarded かを見る）。**ページ名は出さない** — 公開しないと決めた内容の見出しだけを公開することになるため。補足文は件数が Wiki の欠陥ではなく検査が働いた記録であることを述べる。
- **この件数のためだけに走査を 1 つ足している — 下の「既存の走査に相乗りする」原則の例外である**。ディスクに無いページの記録は全ページ走査からは届かないため、`count_unpublished_pages()` が `.wikicommit/review/` を 1 回歩く（ディスクに在るページのディレクトリは記録を読む前に飛ばす）。root index には出さない — 入口の数字は 3 つに留める。

**集計の単位はページではなく `Type/slug` キー**。WikiLink は言語を持たないため、ある原文ページとその翻訳は1つのノードとして数える。ページ単位で数えると、リンクが1本も増えていないのに Wiki が2言語目を持った瞬間に全ての数字が倍になる。ハブ行・参照元リンクのようにノードを1ページで代表させる箇所では、`primary_lang` のページを優先して選ぶ。

#### 情報源の言語別

`## 情報源の内訳` の小節として、管理ファイルの `source.lang`（Pass 2a が書く ISO 639-1。`docs/DesignDoc-data.md` §4.3）を数える 2 列の表を置く。集計は `generate_source_pages()` の `stats`（`lang_counts`）に相乗りし、追加の走査は無い。**ホスト別の表では代替できない** — ホスト名から言語は導けず、ホスト数は青天井で `OVERVIEW_HOST_LIMIT` の裾に非英語ホストが集中する（`wikicommit/ai-driven-dev-wiki` の 2026-09-21 の公開サイトで 66 ホスト中 19 が非英語、うち 11 が切り落とされていた）。言語数は有界なので、この表には件数上限を置かない。コードは言語名へローカライズしない。

- **表の直前に 1 文を置き**、`primary_lang` 以外の行が出るのは正常であり、そのソースから書かれたページが要約・翻訳を経ていることを意味する、と述べる（数字が誤読されうる箇所に 1 文を添える慣習）。
- **値を持たない管理ファイルは `last_generated_at` で 2 行に分け、どちらも表の最後に出す**。`last_generated_at` が空のものは「未処理」（`source_lang_unprocessed`。まだ一度も実行を完走していない — `add_source.py` が空の `lang:` と空の `last_generated_at:` を置き、Pass 2a まで埋まらない。`pending` で未取得・Pass 1 の失敗を含む）として「未記録」の前に出し、残りを「未記録」（言語の記録が始まる前に処理され、読み直されていない）とする。未処理は新しい Wiki で常に非ゼロになるキューの長さであり、1 行にまとめると古い取り込みがあるように読ませる。隠すと、英語ソースだらけの Wiki が記録済みの少数の言語だけでできているように見える。
  - 判定は `reconcile_ingest_status.py` と 5 件ガードの選定順序が「一度でも完走したか」の目印に使っているのと同じ値で、決定論的に分かれる。
  - `lang` を持つソースは `last_generated_at` が空でも（Pass 2a の後で保留されたもの）言語の行に数える。
  - `status: excluded` は `last_generated_at` が空でも「未記録」に数える — Pass 4 の `excluded` 分岐は完走した実行の末尾で書かれるが `last_generated_at` を書かないため、日付が無いことが未完走を意味しない。
  - Pass 1 で失敗したソースは「未処理」に入る（`status` 別の表が `failed` を別に数えているので、言語の表で細かく分けない）。

#### ハブ行のソース件数と、同じソースに立つハブ

**ハブ行に、そのページに記録されているソースの件数を添える**（`— 被リンク数: 24 / 情報源: 2`）。「中心が薄い」 — 最も参照されているページが 1 本の文書にしか立っていないこと — を見えるようにするためである。値は `page_stats` の `source_count` で、**既に読んでいる `sources[]` の長さから導く**（`has_manual_source` の導出と同じ読み取りに相乗りし、追加の I/O を発生させない）。

**指標が情報を持つのはハブの行だけである**。2 件目の `sources[]` エントリが付くのは `action: update` のときだけなので、非ハブはほぼ 100% 単一ソースになる（実測。キー単位で、`assets/` / `index.md` / `status: removed` を除外し、`sources[]` は `primary_lang` のページから取った）:

| | スナップショット | キー数 | 全キーの単一ソース率 | ハブ平均 | 非ハブ平均 | 上位20ハブの平均 | 上位20のうち単一ソース |
|---|---|---|---|---|---|---|---|
| `wikicommit/ai-driven-dev-wiki` | 2026-09-18（205 ページ） | 198 | 88% | 1.21 | 1.00 | 1.90 | 12 / 20 |
| `wikicommit/decameron-wiki` | 2026-08-23（549 ページ） | 174 | 83% | 1.86 | 1.00 | 3.35 | 2 / 20 |

この表の数字は上記スナップショット時点のクローンでの値であり、示しているのは絶対値ではなく関係の形である（指標は 2 つの Wiki を弁別する）。

**規範は「多ソースにせよ」ではなく「単一ソースのハブが見えない状態であってはならない」に置く**。正当な単一ソースのハブが 2 種類ある — source-as-entity ページ（そのページ自身がその文書についてのページなので構造上 1 件）と、1 本の論文が造語した用語（正直な出典が 1 本しか無い）。したがって補足文（`sources_count_note`）は (a) 記録されているソースの件数であって独立した裏付けの数ではないこと、(b) ある文書そのものについてのページは構造上 1 件になること、を述べる。**単一ソースを太字・記号で強調しない** — 1 であることが正しい場合がある以上、強調は判定になる。

| 論点 | 決定 | 理由 |
|---|---|---|
| 数える単位 | `sources[]` のエントリ数 | ホスト単位は独立性ではない（百科事典とそのミラーは別ホスト）。エントリ数は正直に数えられる唯一の量であり、独立した裏付けの数でないことは補足文が述べる |
| 翻訳ページ | 区画ごと省く | `sources[]` を持たず親から継承する（`docs/DesignDoc-data.md` §4.2）。`0` は「ソースが無いページ」に見える。`best_page_for_key` が `primary_lang` を優先するため、省略が効くのは原文の無いキーに限られる |
| view ページ | 区画ごと省く | `derived_from` であって `sources` ではない。件数を同じラベルで出すと別のものを数えることになる |
| `sources[].type: manual` | 数に含める | それはソースである |
| `status: retracted` のソース | 引かない | 引くには管理ファイルを読む必要があり、hub 集計に `.wikicommit/source/` への依存を持ち込む。取り下げ済みソースに立つページは `check_retracted_sources.py` が運用者へ報告している |
| source-as-entity ページ | フィルタしない | マーカーが無いので機械的に判定できない。型からの推定はヒューリスティックであって事実ではない。補足文で扱う |
| `/wikicommit-status` | 足さない | 全キーの大半が単一ソースであり、所見にすると常時点灯する |
| ページ単位のバナー | 出さない | ページ単位の数字は判定に読まれる。件数が意味を持つのは集約された後である（§8.4） |
| 型別の傾向に平均情報源数の列 | 足さない | 非ハブがほぼ単一ソースである以上、型全体の平均は「その型に何件ハブがあるか」を薄めて映すだけで、型そのものの性質を述べない |

**ラベルのキーは `sources`（`## 情報源の内訳` の見出し）と分け、`sources_count` / `sources_count_note` とする**（`reviewed` と `ai_reviewed` を分けたのと同じ規則）。英語ラベルも見出しの `Sources` と文字列を変えて `Sources recorded` にしてある。同じ件数は `build_survey_view.py` の `PAGE:` 行にも `sources=N` として出し、`/wikicommit-collect` Step 3.5 が「何が薄く支えられているか」を着眼点の材料にできるようにしてある（`docs/DesignDoc-ScriptSpec.md`）。

**同じソースに立つハブをまとめて出す**。行ごとの件数では集中は見えない（上の実測の ai-driven-dev では、上位 20 ハブのうち単一ソース 12 件中 **7 件が同じ 1 本の arXiv 論文**〈`arxiv.org/pdf/2509.06216`〉に由来していた）。Knowledge hubs 節の**末尾**（ハブ一覧の直後）に、「上位 20 件のうち、次の情報源だけに立つもの:」に続けて 1 ソース 1 行で `[<識別子>](<ソースページ>) — N 件` を出す。**新しい節は作らない**（俯瞰ページの目次を伸ばさない）。**判定ではなく報告である** — `sources_count_note` と同じ強さでその旨を直前の 1 文に書き、正当に集中する 2 つの形（ある文書そのものについてのページ・1 つの文書を主題とする Wiki）を併記する。

| 論点 | 決定 | 理由 |
|---|---|---|
| 母集団 | 表示している上位 `OVERVIEW_HUB_LIMIT`（20）件。文言で「上位 N 件のうち」と明示する | 読者が見ている行と数字が一致する。全ハブを母集団にすると被リンク 1 の端のページが大半を占め、「中心が薄い」という問いから外れる |
| 数えるもの | **単一ソースのハブだけ**を、その唯一のソースの識別子でまとめ、**2 件以上を占めるソースだけ**を出す | 複数ソースのハブまで数えると Wiki の主要記事（decameron の `it.wikipedia.org/wiki/Decameron` 等）が健全な Wiki でも点灯し、弁別性を失う見込みが高い（**未計測** — 含めたくなったら先に decameron で測ること） |
| 分母から外すもの | 翻訳ページ・view ページ（`source_count` が `None` のもの） | 識別子を持たない。行ごとの件数と同じ扱い |
| 識別子 | `sources[].url` / `sources[].path` の文字列そのもの | 導出ファイル名は旧命名規則の管理ファイルを取りこぼす。ホスト単位にしない理由は上の表と同じ |
| 「どの N 件か」 | 行に印を付けず、`content/sources/` のソースページへリンクする（`generated_pages` を列挙しているので辿れる）。ソースページが無い識別子は素のテキスト | 行の強調は判定になる |
| リンクの引き方 | `generate_source_pages()` が返す `source_stats` の `page_for_source`（`source.url` / `source.path` → 出力パス） | 同関数は全管理ファイルを既に走査しており、追加 I/O が無い |
| 該当なし | 行ごと出さない（「なし」とも書かない） | 集中していないことは報告すべき事実ではない |
| `status: retracted` | 引かない | 上の表と同じ |
| `/wikicommit-status` | **足さない** | 集中は普遍的ではない（上位 20 のうち単一ソースは decameron 2 件・ai-driven 12 件）ので「常時点灯」は理由にならない。根拠は別に 2 つある: (1) これは運用者がページ単位で直す欠陥ではなく Wiki の現在の形についての事実であり、status の所見は「これを直せ」と読まれるため、source-as-entity や 1 文書の Wiki で誤った行動を促す、(2) 集中を解く行動（別の情報源を探す）は `/wikicommit-collect` の俯瞰（Step 3.5）の領分である |

`page_stats` は同じ `sources[]` の読み取りから識別子（`source_ids`）も持つ — 追加の I/O は無い。俯瞰ページは build-generated なので、表示の変更は次のデプロイで全件に反映される。

**`check_orphans.py` / `check_wanted_pages.py` との意図的な3つの差分**（同じリンクグラフを別の目的で見るため、数字が一致しないことがある）:

- **`status: removed` のページは発リンクを寄与しない**。公開されないページのリンクは読者が辿れないため、公開サイトの俯瞰としてはこちらが正しい。結果として「removed ページからのリンクだけで参照されているページ」は、overview では orphan・`check_orphans.py` では被参照、と分かれうる。
- **slug が別の Type に実在する wanted キーは wanted に載せない**。それは Type セグメントの誤りであり、読者に「まだ書かれていないページ」として提示すると既存ページの重複を作らせてしまう。この種の指摘は `check_wanted_pages.py` の `TYPE_MISMATCH` が運用者向けに担う。同様に、removed ページへのリンクも wanted には載せない（`check_wikilinks.py` が ERROR として別途ブロックする）。
- **自己リンクは被リンクに数えない**。唯一の被リンクが自分自身であるページは overview では orphan になる（`check_orphans.py` は被参照として扱う）。

なお `<lang>/<Type>/<slug>.md` の形に解決できない `.md` はキーを持てないため overview のどの集計にも入らない一方、root index の `wikicommit_page_count`（§8.8）には数えられる。パイプラインの他の部分が Wiki ページとみなさない形のファイルであり、この差分は許容する。

wanted ページは定義上リンク先が存在しないため、`[[Type/slug]]` としてではなくコードスパンのキー名 + **参照元ページへのリンク**として描く。カスタム型の型名は publish 時のフラット化に合わせて `custom/` を落として表示する。見出し・ラベルは `ROOT_INDEX_LABELS` / `SOURCE_PAGE_LABELS` と同じ「`primary_lang` をキーにした辞書 + 英語デフォルト」パターン（§8.9.1）に従い、LLM は関与しない。

**スコープ外**: Wiki 全体の傾向を LLM が論述するページは**作らない方針に確定した**（鮮度追跡の仕組みと型名の選定という2つの未確定な設計判断を伴う一方、実際に欲しかった内容は決定論的な集計で表現できるため）。特定の着眼点に基づく合成は `/wikicommit-synthesize` の担当。build-generated ページは `.wikicommit/entity/` に実体を持たないため `search_index.py`（FTS5）の走査対象外で、`/wikicommit-ask` / `/wikicommit-search` には出ない（ブラウザ側の Quartz 標準検索にはビルド成果物として出る）— Wiki の状態を LLM に尋ねる用途は `/wikicommit-status` が担う。

**実装箇所**: `.wikicommit/scripts/convert_wikilinks.py`（`generate_overview_page()`・`OVERVIEW_LABELS`・`url_host()`。`.claude/skills/wikicommit-init/scripts/templates/scripts/` への symlink 経由で配布テンプレートにも反映される）。

#### 左ペインでの位置 — 予約ツリーは端へ寄せる

`wikicommit-explorer` の左ペインでは、publish 層の予約ツリーを Type フォルダの列の**端へ寄せる** — 横断して見るもの（`overview` / `View`）を先頭、個別のエンティティを中央、出自の記録（`sources`）を末尾に置く。並び順は `explorerSortFn` の `sortTier()` が決める。

```text
overview            ← 横断して見るもの（tier -2・root 限定）
View                ← 同上（tier -1・深さガード無し）
AdministrativeArea
DefinedTerm         ← 個別の事物（tier 0）
Organization
Person
Place
en                  ← 言語フォルダ（tier 1）
sources             ← 出自の記録（tier 2）
```

- **tier は `displayName` ではなく `slugSegment` で判定する**。tier 0 内の比較は `displayName`（そのフォルダの `index.md` の `title`）に対する `localeCompare` であり、俯瞰ページの `title` は `OVERVIEW_LABELS` から引かれるため、表示名で判定すると埋もれる位置が `primary_lang` によって変わる。`slugSegment` なら言語に依らず安定する。
- **比較先は publish 後の slug であり、Quartz は各セグメントを小文字化する**（`convert_wikilinks.py` の `_quartz_slugify_segment()` が移植している規則。`filePath: "en/View/index.md"` の slug は `"en/view/index"`）。`sources` / `overview` はディレクトリ名定数（`SOURCES_DIR_NAME` / `OVERVIEW_DIR_NAME`）で元から小文字だが、`View` は予約 Type セグメント（`VIEW_TYPE_SEGMENT`。PascalCase）なので、**tier の判定は小文字の `view` で書く**。`sortTier` の冒頭にこの不変条件をコメントとして書いてある。テストのノードは実物どおり `folder("view", "View")`（`displayName` は `"View"`）で作り、`contentIndex` の実データの形から slug を導くテストを持つ。`tests/test_publish_reserved_trees.py` も `VIEW_TYPE_SEGMENT.lower()` が両方の写しにリテラルとして現れることを見る（grep 相当であり、tier の正しさは見ない）。
- **`RESERVED_PUBLISH_TREES` に `View` を足さない** — あれは `convert_wikilinks.py` が `content/` 直下に予約するツリーの一覧であり、`View` は `content/<lang>/` の下にある別のものである。**`.toLowerCase()` も付けない**（`slugSegment` が大文字になる経路は無く、隣の 2 行と書き方が割れる）。
- **`overview` と `View` が隣接するのは偶然ではない** — `docs/DesignDoc-data.md` §4.5.1 は `kind: landscape` の view ページについて「数を書かない。数が要るなら build 生成の overview ページへリンクする」と定めており、2 つは互いを名指しする関係にある。読者にとってもどちらも「Wiki を見渡すもの」である。
- **tier 番号に負値を使い、既存の 3 値（0・1・2）には触れない**。`aTier - bTier` で比較しているため負値で問題がなく、既存の並び順テストが変わらずに通る。
- **root 限定ガードは `overview` にだけ付ける**。`foldLang.ts` は `node.slug` を書き換えないので、fold で root へ上がった View の `slugSegments` は `["ja", "view"]` のまま残る — 深さで絞るとまさにその場合に当たらない。ガード無しなら、兄弟言語フォルダを展開した中の `en/View` も同じ理由でその言語の Type 群の先頭に来る。`View` は予約 Type セグメントなので `content/<lang>/` の下では Type と衝突しないが、**`content/sources/` の下では衝突しうる**（あちらはリポジトリ内の任意のパスと URL のパスをそのままミラーするため、`src/View/` を持つリポジトリを取り込んだ Wiki では、そのフォルダが sources ツリーの中で兄弟の先頭に来る）。影響は tier 2 の 1 サブツリー内部の並び順に閉じるので直していない。`/wikicommit-synthesize` を一度も実行していない Wiki には `View` フォルダ自体が無く、`overview` だけが先頭に出る。
- **`sortTier` の写しは 2 つあり、CI が同期を強制する**。`explorerSortFn`（`WikiCommitExplorer.tsx`）と `defaultSortFn`（`wikicommit-explorer.inline.ts`）が同じ tier ロジックを持ち、後者は前者を復元できなかったときのフォールバックである。**フォールバックが効くのは「一瞬」ではない** — 木は `buildFileTrie()` の解決後に一度だけ描画されるため、`data-data-fns` が無い・その JSON や `sortFn` の復元に失敗した場合に `defaultSortFn` がそのページの並び順を最後まで決め、片方だけ直したときの症状は目視で見つけられない。`tests/test_explorer_sort_tier_sync.py` が 2 つの `sortTier` 本体を型注釈・コメント・セミコロン・空白を落として正規化したうえで突き合わせる（正規化が緩すぎて何も検出しなくなる状態を防ぐため、tier の値を 1 つ変えたら差が出ること・コロンに続く値が残ること・コメント内の対応しない波括弧で本体の終端がずれないことも同ファイルが確かめる）。**照合の対象は `sortTier` の本体だけである** — tier が同値のときの tie-break は `(a.displayName || "")` と `a.displayName` で既に食い違っており、そちらの drift はどのテストも見ていない。行頭アンカーで定数を探す `tests/test_quartz_plugins_lang_segment_sync.py` は関数本体の中のこの 2 つを見ない。
- **採らなかった案**: ディレクトリ名を並び順のために変える（`OVERVIEW_DIR_NAME` は公開 URL そのものであり、読者向けの識別子を歪めない）／`title` の先頭に記号を置く（表示名依存の並びを強める）／`overview` を `sources` の下に置く（俯瞰ページは「Wiki 全体の入口」であり、出自の記録の下に沈めると `View` とも離れる）／`filterFn` / `mapFn` で解く（この枠組みでは「1 つのフォルダの子を親へ持ち上げる」類の操作を表現できず、並び順は `sortFn` の担当である）。
- `quartz-plugins/` は `_root_outputs.py` 上 `update: overwrite` なので、変更は再 init または `/wikicommit-update` を実行したリポジトリから届き、公開サイトへの反映は次のデプロイを待つ（新旧混在を許容する）。

### 8.9 読者向けに表示されるフィールドの一覧

`.wikicommit/entity/<lang>/<Type>/<slug>.md` のフロントマターは複数の Quartz コンポーネントに分かれて読者に表示される。field 単位でどのコンポーネントが担うかを一覧する:

| フィールド | 表示コンポーネント | 節 |
|---|---|---|
| `title` | ページ見出し（`wikicommit-properties` 自身ではなく Quartz 標準の article-title 等） | — |
| `review_status`・`generated_at`・`generated_by`・`wikicommit_page_count` 等（サイト概要） | `wikicommit-banner` | §8.4・§8.8 |
| `sources`（+ `translated_from` 経由の継承） | `wikicommit-sources` | §8.10 |
| `sources[].license` ＋ 改変告知の固定文言 | `wikicommit-sources` | §8.10 |
| `derived_from`（合成ページの出自。+ `translated_from` 経由の継承） | `wikicommit-sources` | §8.10.1 |
| `description`/`tags`/`aliases`/`properties`（Schema.org 型固有プロパティ。`quartz.config.yaml` の `includedProperties` で選定） | `wikicommit-properties` | 本節 |
| `type`・`properties.*` の Schema.org マッピング（`<head>` への JSON-LD 埋め込み。UI 上は不可視） | `wikicommit-jsonld` | §8.3 |
| `lang`・`wikidata`・`sameAs` 等 | — （どのコンポーネントも UI に表示しない） | — |

型固有の Schema.org プロパティ（`properties:` 配下の `description`/`affiliation`/`jobTitle` 等）は、`wikicommit-jsonld` の JSON-LD 埋め込み（クローラー向け、UI 上は不可視）に加えて `wikicommit-properties` が UI に表示する。`wikidata`/`sameAs` 等（`docs/DesignDoc-data.md` §4.1 の「外部識別子」フィールド）は UI 上非表示である — これらを表示対象に含めるかどうかは `includedProperties` の設定範囲であり、別の判断を要する。

`wikicommit-properties`（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-properties/`）はこの非対称を解消する。Quartz v5 の必須プラグイン `github:quartz-community/note-properties`（フロントマター解析そのものを担う。無効化不可）を、他の `wikicommit-*` プラグインと同じ自前ディレクトリへのフォーク方式（`docs/DesignDoc-skills.md` §11 参照）で `wikicommit-properties` として取り込み、`quartz.config.yaml` テンプレートの参照を `github:quartz-community/note-properties` からこちらへ差し替えた。アップストリームからの実行時の挙動の変更点は次の1点のみ: `getVisibleProperties()`（表示対象プロパティの選定ロジック）が、選定後の値がプレーンオブジェクトであれば1階層だけ展開し、そのキーをトップレベルの行と同格で表示する。これにより `properties:` ブロック自体は1行の生 JSON ダンプとして表示されるのではなく、`description`/`affiliation`/`jobTitle` 等の個々のキーが他のトップレベルフィールドと見分けがつかない行として並ぶ。展開時に、同名のキーが既に選定済み（トップレベルフィールド、または `includedProperties` 内でより先に処理された別のオブジェクト）であれば上書きしない — カスタム型（`docs/DesignDoc-data.md` §5.3。標準型と異なり `domainIncludes` 検証の対象外）が誤って `properties.tags` のような WikiCommit 構造フィールドと同名のキーを宣言した場合に、ページの実際の `tags` を静かに破壊しないためのガード。WikiLink 由来の値（`[[Type/slug]]` 形式）・配列値の描画ロジックはアップストリームのものをそのまま使う（変更不要 — 展開後の値は文字列/配列として扱われ、既存のリンク描画がそのまま効く）。ネスト2階層以上のフラット化には対応しない（WikiCommit のスキーマ設計上、`properties:` の値がさらにオブジェクトになることは想定していない）。

`quartz.config.yaml` テンプレートの `includedProperties` に `properties` を追加し、この展開ロジックの対象に含めている。プロパティキー名の表示ラベル整形（`jobTitle` → "Job Title" のような人間可読化）は行わない — Schema.org 語彙自体が英語ベースであることは CLAUDE.md の既存方針（キーはすべて英語）と整合しており、無理に和訳・整形しない。

### 8.9.1 公開サイトの言語の境界: 識別子は言語中立・UI chrome はローカライズ

公開サイトでは、`convert_wikilinks.py` の `SOURCE_PAGE_LABELS`・`ROOT_INDEX_LABELS` 等が「情報源一覧」「種別」「元リンク」等をローカライズして表示する一方、Type（`Person`・`Place`・`GovernmentService` 等）は英語のまま表示される。中途半端に見えるが、**これが意図した境界である**:

| | 例 | 扱い |
|---|---|---|
| **識別子** | Type セグメント（`Person`）・slug（`yamada-taro`）・WikiLink | **言語中立の英語**。翻訳しない |
| **UI chrome** | ページ見出し・ラベル・ナビゲーションの語 | `primary_lang` にローカライズする |

識別子側は翻訳できない — WikiLink・slug・Type は言語中立の英語識別子として設計されており（CLAUDE.md の WikiLink 節）、`ja` ページの Type を和訳すると `[[Person/yamada-taro]]` が解決しなくなる。つまり選べるのは「UI chrome も英語に統一する」か「現状のまま」かの二択であり、前者は日本語 Wiki の読者にとって明確な後退である。中途半端に見えるのは事実だが、**識別子を翻訳できないことの帰結**であって、UI chrome を訳す判断の誤りではない。

`.wikicommit/source/` の管理ファイルの見出しラベルは `primary_lang` によらず固定の英語だが、それは非公開の内部管理ファイルだからであり、読者向けの公開ページには当てはまらない。

### 8.9.2 chrome の言語を決めるのは `quartz.config.yaml` の `locale`

§8.9.1 の「UI chrome は `primary_lang` にローカライズする」を chrome を描くプラグインへ届ける経路は、`quartz.config.yaml` の `locale` である。公開サイトの文言を出す仕組みは系統ごとに locale の決め方とロケール数が違う:

| | locale の決め方 | ロケール数 |
|---|---|---|
| WikiCommit 自前 3（banner / sources / properties） | **`frontmatter.lang` 優先** → `cfg.locale` → `en-US` | 10 |
| WikiCommit 自前 1（language-switcher） | `cfg.locale` のみ | 10 |
| `convert_wikilinks.py` のラベル辞書 4 家族（root index / source type / source page / overview） | `primary_lang`（サイト全体で 1 つ） | 10（英語は `DEFAULT_*`） |
| コミュニティ由来 3（explorer / graph / search） | `cfg.locale` のみ（サイト全体で 1 つ） | 30 |
| うち graph の `controls.*`（WikiCommit が足した操作 UI の文言） | 同上 | 30（下記の例外） |

**`init.py` が `primary_lang` から `locale` を導出する**。配布テンプレートの `locale` は `{LOCALE}` プレースホルダであり、`QUARTZ_LOCALE_BY_PRIMARY_LANG`（ISO 639-1 → BCP 47。値はコミュニティ由来 3 プラグインが実際に持つ 30 ロケールから採る）で置換する。固定値（`en-US`）のままだと、日本語 Wiki を既定の設定で公開したときにページ本文とバナーは日本語・サイドバーと検索とグラフは英語になる（ja-JP の訳は 3 プラグインすべてに存在するのに届かない）。対応が無い言語は `en-US` に据え置く — chrome はどのみち英語になるので、無いタグを書けば config だけが嘘をつく。**この表は自前プラグインの `LANG_TO_LOCALE`（自前プラグインが訳を持つ 10 言語）とは別物**であり、同じ名前にすると同期すべき 2 つに見えるため名前を分けてある。`tests/test_init.py` が、表の全エントリのロケールファイルが 3 プラグインすべてに実在することを検証する（上流でロケールが消えると、ビルド時には黙って英語へ落ちるため）。

**残る非対称は設定では解けない**。`locale` は 1 サイトに 1 つで、コミュニティ由来 3 つは per-page に切り替えられないため、多言語 Wiki では翻訳ページの chrome（explorer / graph / search）が `locale` の言語のまま残る。自前プラグインはページの `lang` に従うので、バナー・出典ボックスは 10 言語の内ならページの言語で描かれる。10 言語の外の言語（ko 等）のページでは、自前プラグインも `cfg.locale`（→ `en-US`）へ落ちる。この非対称は `quartz.config.yaml` の `locale` 行にコメントとして書いてある（この値が何を決めて何を決めないか）。

**採らなかった案**: (a) コミュニティ由来 3 つに `frontmatter.lang` を読ませる — 全ページで一致するが、ローカルに取り込んだコピーの描画ロジックを改造することになり、上流との差分を恒久的に抱える（`LANG_SEGMENT_RE` の同期は正規表現 1 本であって描画ロジックではない）。(b) 自前 4 プラグインを 30 ロケールに揃える — 使われる見込みに対して過大である（下記）。(c) `wikicommit-language-switcher` に `resolveLocale()` を導入する — 同プラグインが並べる言語名は自言語表記（`ja: "日本語"`）で読者のロケールに依存せず、`cfg.locale` に従うのは見出しラベルだけである。per-page 化は (a) と同じ問い。なお自前プラグインに言語を足すときは `LANG_TO_LOCALE` と `locales` の**両方**に足す必要があり、片方だけだと `resolveLocale` が `cfg.locale` へ落ちて、その言語のページに `locale` の言語のバナーが出る — これは `tests/test_ui_language_fallback_disclosure.py` が止める。

**既存の公開済みリポジトリには自動では届かない**。`quartz.config.yaml` は `update: review` であり再 init でも `/wikicommit-update` でも上書きされない。運用者が差分を見て `locale` の 1 行を取り込む。

#### WikiCommit 自前の UI 文字列は 10 言語 — 外部基準で決める

WikiCommit 自身が書く UI 文字列（上表の自前プラグイン 4 つとラベル辞書 4 家族）は、決まった外部基準の言語集合で持つ。言語を「どのパイロットがあるか」で足していくと、「なぜその言語か」の答えが「たまたまパイロットがあった」になり、次の言語で同じ判断を繰り返すことになる。

**対応言語は Wikipedia のポータル（wikipedia.org）に並ぶ 10 言語とし、それを超えて広げない**: en・ja・de・es・fr・it・ru・zh・pt・pl。

| 観点 | 決定 |
|---|---|
| 基準 | 外部基準（Wikipedia ポータル）。どのパイロットがあるかでは決めない |
| 地域サブタグ | `QUARTZ_LOCALE_BY_PRIMARY_LANG` と揃える（`zh` → `zh-CN`、`pt` → `pt-BR`、他は `de-DE` / `es-ES` / `fr-FR` / `it-IT` / `ru-RU` / `pl-PL`） |
| 訳文 | LLM が英語から作る。英語が正本であり、訳が英語より強い主張に読めたら訳を直す |
| 部分的な言語 | 置かない（TS は `Record<string, typeof enUS>` が、Python は角括弧アクセスが欠けを許さない） |
| 10 言語の外 | 英語へ落ちる。運用者には `init.py` が 1 度だけ `NOTE:` で知らせ、公開ページでは知らせない（読者は行動できず、公開ページにコストを掛けるため） |

**ポータルの並びは実物で確認できていない**。オーナーの方針は「実装着手時に wikipedia.org の実際の並びを確認して確定し、確認日を記録する」だったが、2026-09-30 の実装環境は外向き通信がプロキシで遮断されており（WebFetch・curl とも 403）、ウェブ検索で得た記述に基づいて上記 10 言語とした。**次に wikipedia.org を開ける環境で並びを確認し、食い違えばこの節とロケール集合を直す**。

**訳は英語が述べる以上を述べないように作る**（「checked against sources」は「照合した」であって「検証した」ではない）。機械翻訳した UI を読者向けに配らないという規則は採らない — その理由（訳が英語より強い主張に読めても誰も気づけない）は正しいが、それを理由に言語を止めると、10 言語の外で起きているのと同じ「英語の枠」がそれらの言語の Wiki にも残り続ける。キー・差し込み（`{pages}` 等）・Markdown の記号が英語と揃っていることは `tests/test_ui_translation_completeness.py` が機械的に確かめる。**訳の強さそのものは機械では確かめられない**ので、各ロケールファイルと辞書のコメントに「英語が正本」と書いてある。

**graph の `controls.*` が 30 言語を持つのは例外である**。graph はコミュニティ版 fork から取り込んだプラグインで、その既存ロケール集合（30）に WikiCommit が操作 UI の文言を足した。ロケールファイルの集合が先に決まっていたので 30 言語すべてに足したのであり、自前プラグインの目標ではない。

**対象の文字列**（英語で数えて 127）:

| 置き場 | キー数 |
|---|---|
| `wikicommit-banner` の `wikicommitBanner` | 29 |
| `wikicommit-sources` の `wikicommitSources` | 8 |
| `wikicommit-properties` の `wikicommitProperties` | 1 |
| `wikicommit-language-switcher` の `wikicommitLanguageSwitcher` | 1 |
| `ROOT_INDEX_LABELS` | 11 |
| `SOURCE_TYPE_LABELS` | 3 |
| `SOURCE_PAGE_LABELS` | 15 |
| `OVERVIEW_LABELS` | 59 |

**言語の集合は 4 か所で同期する**: 自前プラグイン 4 つの `locales`（うち 3 つは `LANG_TO_LOCALE` も）、ラベル辞書 4 家族、`init.py` の `WIKICOMMIT_UI_LANGS`。`tests/test_ui_language_fallback_disclosure.py` が食い違いを止める。**`/wikicommit-fix` Step 7 もこの集合に依存する** — 報告 Issue の本文にバナーが書く `Page:` / `Language:` の行はページの言語で描かれるため、Step 7 は 10 言語の綴りすべてを照合する。`tests/test_fix_completion_comment_language.py` がバナーのロケールファイルから綴りを読んで突き合わせる。

**採らなかった案**:

| 案 | 理由 |
|---|---|
| A 何もしない | README の実例（`decameron-wiki`、`primary_lang: it`）で原文ページの枠が英語のまま残る |
| B `it` だけ足す | 「なぜ `it` か」の答えが「たまたまパイロットがあった」になり、次の言語で同じ判断を繰り返す |
| C 30 言語に揃える | 127 文字列 × 28 言語は、使われる見込みに対して過大 |
| D 公開ページで開示する | 読者は行動できず、公開ページにコストを掛ける。それを覆す新しい事実が無い |
| E 各 Wiki がラベルを上書きする | 原理的には最もきれい（自前プラグインは `quartz.config.yaml` の `options:` を受け取れ、同ファイルと `config.yml` は `update: review` で上書きされないため置き場所は成立する）。ただし運用者に約 127 ラベルの記述を求め、上書きを読む処理を 5 箇所に足す必要があり、10 言語案より重い。将来の拡張として残す |

**既存の Wiki には `/wikicommit-update` で届く**。`quartz-plugins/` と `.wikicommit/scripts/` はどちらも `update: overwrite` なので、同期した次のビルドから原文ページの枠が `primary_lang` で描かれる。`quartz.config.yaml` の `locale`（上記）とは届き方が違う。

### 8.10 帰属・ライセンス・改変告知の表示

WikiCommit は外部ソースを取り込み、LLM が要約・再構成したページを公開サイトとして配信する。この配信自体が頒布行為であり、多くのソースのライセンス（CC BY-SA 4.0 等）は出典の提示だけでなく **ライセンス自体の表示** と **改変した旨の告知** を求める。

#### 4層構造と、①層を主役とする理由

| 層 | 何を書くか | 実装先 | 現状 |
|---|---|---|---|
| **① ページ単位**（法的な主役） | 出典リンク ＋ ライセンス名（＋ URI） ＋ 「要約・再構成した」旨 | `sources[].license` → `WikiCommitSources` | **実装済み** |
| ② サイト全体 | ページごとに条件が異なる旨と、各ページの出典欄を見よという案内 | `convert_wikilinks.py` が生成するルート index と `content/sources/index.md` | **実装済み**（フッターではない — 後述） |
| ③ リポジトリ | コードとコンテンツのライセンス分離 | ルートの `LICENSE` | 補助。**自動生成しない**（後述） |
| ④ README | 人間向けの要約と参照先 | `README.md` | **案内のみ**（`print_next_steps.py` の `_LICENSING_STEP` が推奨文面ごと提示する。自動生成・自動追記はしない） |

①を主役に据えるのは、読者が検索・外部リンクから個別ページに直接着地するためである。ルートの `LICENSE` やサイトフッターは多くの読者の目に触れないまま終わる一方、①はページが頒布される単位そのものに帰属表示を伴わせる。逆に①さえ正しければ②〜④は補助で足りる — ②④は①の代替ではなく上乗せである。

#### ① 層の実装

`WikiCommitSources`（`.claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-sources/`）が、出典1件ごとに次の2つを描画する。

1. **ライセンス名**: そのソースの `sources[].license`（`docs/DesignDoc-data.md` §4.1・§4.3）が非空のときのみ、出典リンクの直後に括弧書きで併記する。値が Creative Commons 系の SPDX 識別子（`CC-BY-SA-4.0`・`CC0-1.0` 等）であれば、識別子の**形から** deed URL を導出してリンクにする（対応表を持たないため、将来の CC バージョンにも保守なしで追従する）。それ以外の識別子（自治体独自の利用規約・`PDL-1.0`・`all-rights-reserved` 等）はプレーンテキストとして表示する。ライセンス名 ＋ URI という形は CC BY-SA §3(a) が求める「ライセンスの明示」に対応する
2. **改変告知の固定文言**: 出典リストの直下に、「このページは出典を LLM が要約・再構成したものであり逐語転載ではない」「表示されているライセンスは併記された出典に対するものであってページ全体に対するものではない」を表示する（`i18n` の `adaptationNotice`。ページの `lang` に応じて日本語／英語）。唯一の例外は**出典が `type: manual` のみのページ**で、この種別は「人間が直接書いた」ことを記録するもの（`docs/DesignDoc-data.md` §4.4）であるため、LLM が要約・再構成したという1文目はそのページでは事実に反する。この場合は2文目だけの短い文言（`licenseScopeNotice`）に切り替え、ライセンスを1件も表示していなければ何も出さない。`type: manual` 以外の出典が1件でもあれば通常の文言に戻る

あわせて `convert_wikilinks.py` の `generate_source_pages()` が、`content/sources/` 配下の公開ソースページ（管理ファイル1件につき1ページ）にも管理ファイルの `source.license` を1行として描画する — 同じ値が「ページから見た出典」と「出典そのもののページ」の両方で一致して見えるようにするため。値が空欄・欠如の場合は行ごと省略する（空行を描画すると「ライセンスが記録されている」と読めてしまうため。ページ側の空文字列を `validate_frontmatter.py` が弾くのと同じ理由）。

改変告知をページごとに記録せず固定文言にしたのは、WikiCommit が**生成する**ページが例外なく LLM による要約・再構成であるため、「改変した」がそれらのページで一律に真であり、個別のブックキーピングが情報を増やさないからである（上記の `type: manual` のみのページは、そもそも生成されたページではないという点でこの前提の外にある — 判定に必要な情報は `sources[].type` に既にあり、追加の記録は要らない）。

2文目（ライセンスの適用範囲の限定）を固定文言に含めているのは、1ページが複数ソースを統合しうる（`action: update` による統合は WikiCommit の中核的な挙動）ため、ソース行に併記されたライセンスをページ全体への宣言と読まれると誤りになるからである。ページ全体に対して単一のライセンスを主張する仕組みは意図的に持たない。

#### ②層をフッターに置かなかった理由と、④層の着地点

**② サイト全体**: 実装先を `quartz.config.yaml` の footer プラグインではなく、`convert_wikilinks.py` が生成する2枚のページ（ルート `content/index.md` と `content/sources/index.md`）にした。理由は 2 つある。

- **footer プラグイン（`github:quartz-community/footer`）は `links`（ラベル → URL のマッピング）しか受け取らない**。任意の散文を出すにはフォークするか専用コンポーネントを書くことになる。WikiCommit は既に 6 プラグインを self-vendor しているのでフォーク自体は前例のある手段だが、1 プラグイン ＝ npm パッケージ 1 つ（`dist/` のコミット・vitest・eslint・`tsup.config.ts`）であり、2 文の注意書きに対して釣り合わない
- **フッターに「リンク」だけを置く案も成立しない**。`links` の値は絶対 URL が前提で（既存エントリが `{REPO_URL}` ＝ GitHub リポジトリの完全 URL）、一方 `baseUrl` は GitHub Pages のプロジェクトページでは `<owner>.github.io/<repo>` になる。ルート相対の `/sources/` は**既定のデプロイ形態でちょうど壊れる**。公開サイトの URL は `init.py` の時点では分からない（`init.py` が受け取るのは `--repo-url` ＝ GitHub リポジトリの URL であって Pages の URL ではない）

②が対象とする読者 — 個別ページに着地するのではなくサイト全体を眺める読者 — が実際に到達するのはルート index と `content/sources/` である。この 2 枚はいずれも `convert_wikilinks.py` が生成する WikiCommit 所有のページであり、散文を自由に書ける。文面の本体は `content/sources/index.md`（「どこから来た情報で、どんな条件か」を問う読者が行き着く先）に 1 か所だけ置き、ルート index には要点だけを述べた短い但し書きを置く（但し書き自体はリンクを持たない — `content/sources/index.md` へはその直前に並ぶ `sources` リンクが導く）。ルート index では、2 つの入口リンク（`sources` と `overview`）の**後ろ**に置く — 行き先の提示ではなくサイト全体への但し書きであるため。

`content/sources/index.md` の文面は**登録ソースが 0 件でも表示する**。「この Wiki がどう作られているか」についての記述であって、現在の内容についての記述ではないため。あわせて「ライセンスが記録されていない ＝ 制約が無い」と読まれないよう明示する（`docs/DesignDoc-data.md` §4.1 の「不明を空文字列で表さない」と同じ線引きを、読者側の表示でも保つ）。

インデックス・ナビゲーションページに①の帰属表示が出ないこと自体は欠落ではない — これらのページはページタイトルとリンクだけで構成され、第三者の文章を含まないため、法的に required な表示は元から無い。②が足すのは法的な充足ではなく**方向づけ**である（「単一のライセンスがあるはず」と読まれることを防ぐ）。

**④ README**: 自動生成・自動追記のいずれも行わない。README.md は display-only（エージェントが編集しない。§8.1）であるため、この層で採れる着地点は案内だけになる。`print_next_steps.py` の `_LICENSING_STEP` に README 用の箇条書きを 1 つ置き、**そのまま貼れる推奨文面まで含めて**提示する（「ライセンスについても書いておきましょう」という抽象的な助言では、書く人が何を書けばよいか分からないまま終わる）。`_README_STEP_WITH_URL`（公開 URL へのリンク追加を「書かずに勧める」）と同じ形である。

#### `init.py` が `LICENSE` / `README.md` を生成しない理由

**生成しない**。WikiCommit リポジトリは、コード（`.wikicommit/scripts/`・`quartz-plugins/`）と、第三者ソース由来のコンテンツ（`.wikicommit/entity/`）という性質の異なる2つを同居させる。後者に単一のライセンスは存在しない — Wikipedia 由来のページは CC BY-SA、自治体サイト由来のページはその自治体の利用規約、学会論文由来のページは通常の著作権（そもそも再許諾する権利が無い）と、ページごとに異なる。ここでルートに `LICENSE` を1枚置いて「この Wiki は CC BY-SA 4.0」と宣言すると、**運用者が持っていない権利を許諾したことになる**。「ファイルが無い＝全権利留保」という GitHub の既定解釈にも問題はあるが、誤った許諾を自動生成するよりは安全側である。

代わりに `wikicommit-init` の「Next steps」最終項が、(a) コードのライセンスは通常の OSS の選択として運用者が決めること、(b) コンテンツのライセンスはページごとに `source.license` で記録すること、の2つを分けて案内する（`print_next_steps.py` の `_LICENSING_STEP`）。`README.md` は display-only のため、新規生成・自動編集のいずれも行わない。

#### WikiCommit が法的判断を代行しない線引き

ツールの責務は「記録する場所を用意し、記録された内容を表示する」ことに限定する。具体的には:

- `add_source.py` の既知ドメイン対応表（`docs/DesignDoc-data.md` §4.3）は、そのサイトが自ら明示しているライセンスを登録時の**初期値**として埋めるだけで、法的な確定ではない。個別ページが別条件を宣言していること（引用文・画像・転載記事等）はありうる
- `validate_frontmatter.py` は `sources[].license` の値の中身を検証しない（空文字列のみ弾く）。SPDX 語彙への照合も、ソースの実際の条件との突合も行わない
- LLM にライセンスを推定させる経路は設けない。ソースのライセンスは事実確認の対象であって、生成物の一部ではない
- 表示側も、記録された値をそのまま出すだけで、その値が当該利用を許すかどうかは判断しない

`sources[].license` は任意フィールドであり、欠如は「この機能より前に生成された」か「記録されていない」ことを意味する。既存リポジトリへの自動移行はせず新旧混在を許容する（`docs/DesignDoc-data.md` §4.3 等）。既存リポジトリで表示させたい場合は、管理ファイルとページの `license` を手で追記すれば次回ビルドから反映される。

---

### 8.10.1 合成ページの出自表示（`derived_from`）

WikiCommit のページは出自フィールドを3通り持ち、ページごとに排他である（`docs/DesignDoc-data.md` §4.2）: 通常ページの `sources`、翻訳ページの `translated_from`、合成ページの `derived_from`（`/wikicommit-synthesize`）。合成ページは既存ページの記述を再構成したものであるため、出自の提示が最も必要な種別である。出自を出さないと、読者から見て「`sources` を書き忘れた不備のあるページ」と外形上区別できない（`includedProperties` には `derived_from` が無く、`content/sources/` ツリーは `.wikicommit/source/` の管理ファイルから構築されるので合成ページは入らない）。

**新規プラグインは追加せず `wikicommit-sources` が描く**（サイト概要を `wikicommit-banner` が描くのと同じ形）。`resolveProvenance()` が `sources` と `derivations` の2つを返し、どちらかが非空なら出典ボックスを描画する。`derived_from` は `sources` と型が異なる（`{path, source_commit}` の配列）ため同じ配列に混ぜず、専用の見出し文（「このページは Wiki 内の以下のページを合成したものです:」）付きの別リストとして描く。

**出自ページが不在・`status: removed` の場合も、そのエントリを列挙する**（リンクは付けず「削除済み／未公開」と添える）。`translated_from` の分岐（親が `removed` なら継承しない）とは扱いを変えている — あちらは*継承元*の話であり継承しないという判断が成立するが、`derived_from` のエントリはそのページの出自そのものであり、黙って落とすと出自が1行足りないページが最初から出自を持たないページと見分けがつかなくなる。複数エントリのうち一部だけが欠けるケースは実際に起こりうる。

**翻訳ページからの継承も `derived_from` に広げる**。合成ページの翻訳は `translated_from` を持ち、その親の出自は `sources` ではなく `derived_from` にある。継承を `sources` だけに留めると、翻訳ページで何も表示されない状態が再現する。

**パス → リンクの変換は `translated_from` と共有する**。`derived_from[].path` は `translated_from` と同じ「リポジトリルートからの相対パス」形式のため、同ファイル内の変換関数 `entityPathToRelativePath()` をそのまま使う（`.wikicommit/wiki/` 旧プレフィックスの後方互換・`custom/` フラット化を含めて）。`WikiCommitBanner.tsx` に同名の複製がある（`docs/DesignDoc-data.md` §3.1 の消費箇所一覧）。

**陳腐化（`STALE`）は読者に見せない**。Quartz は静的サイトのため `git log` を実行できず、判定するにはビルド時に Python 側（`convert_wikilinks.py`）で計算してフロントマターに埋め込む必要がある（§8.8 のサイト概要と同じデータの流れ）。実装可能だが採らない — `source_commit` の不一致は「出自ページがそれ以降に更新された」だけを意味し、**その更新が合成ページの記述に影響したかどうかは判定していない**。出自ページの誤字修正1つで読者に「この記述は古い」と示すことになり、繰り返せば表示そのものが無視されるようになる。`check_derivation_freshness.py` と `/wikicommit-status` が運用者向けの検出手段として担い、運用者は必要なら合成ページを作り直す。

**スコープ外**: `wikicommit-jsonld` への `derived_from` のマッピング（Schema.org 語彙への対応付けは別の判断を要する）、合成ページを `content/sources/` ツリーに載せること（同ツリーは `.wikicommit/source/` 管理ファイルを走査対象とする設計）。

### 8.11 ブラウザタブ・OGP のタイトルにサイト名を載せる（`pageTitleSuffix`）

Quartz 本体の `Head.tsx` は `<title>` を次のように組み立てる。

```tsx
const titleSuffix = cfg.pageTitleSuffix ?? ""
const title =
  (fileData.frontmatter?.title ?? i18n(cfg.locale).propertyDefaults.title) + titleSuffix
```

つまり **`<title>` は「そのページの frontmatter `title`」＋「`pageTitleSuffix`」だけで決まり**、同じ値が `og:title` と `twitter:title` にもそのまま入る。`pageTitleSuffix` の既定値は空文字列なので、設定しなければ**どのページのタブにも、共有したリンクカードの見出しにもサイト名が出ない**（root index・`content/sources/`・`content/overview/`・Type 別インデックス・通常の Wiki ページのいずれも）。

| フィールド | 読者に届く場所 |
|---|---|
| `pageTitle` | 左サイドバーの `PageTitle` コンポーネントと、OGP の `og:site_name` |
| `pageTitleSuffix` | ブラウザのタブ（`<title>`）・`og:title`・`twitter:title` |

**`pageTitle` はこの 3 つに一切入らない**。したがってサイト名を既に `pageTitle` として持っていても、タブに載せる経路は `pageTitleSuffix` しか存在しない — Quartz 自身のドキュメントも同フィールドを "a string added to the end of the page title. This only applies to the browser tab title, not the title shown at the top of the page" と説明している。

`init.py` が `{PAGE_TITLE_SUFFIX}` を `" - <リポジトリのディレクトリ名>"` で置換する。`pageTitle`・footer の `{REPO_URL}` とまったく同じ置換機構であり、新しい仕組みは持ち込まない。区切りは Web 一般の `<title>` の慣例（`Page - Site`）に従う半角ハイフン ` - ` で、`yaml.dump(..., default_style='"')` を通すため先頭の空白が保たれる（素の YAML スカラーでは剥がれ、タブが `Wiki- my-wiki` になる）。

**root index の `title: "Wiki"` は変更しない**。(1) suffix だけでトップは `Wiki - decameron-wiki` のようになる。(2) トップの `title` にサイト名を入れようとすると、`convert_wikilinks.py`（`.wikicommit/config.yml` しか読まない）が `quartz.config.yaml` を読む新しい結合を作るか、`.wikicommit/config.yml` にサイト名フィールドを新設して `pageTitle` と二重管理にするかの二択になる — 後者は「消費者のいない／重複した受け皿を作らない」に触れる。(3) 左サイドバーの `PageTitle` に既にリポジトリ名が出ており、H1 が `Wiki` であることは冗長を避けている側である。

**`pageTitle` と `pageTitleSuffix` が同じ値を持つことは、テンプレートのコメントで受ける**。`init.py` が両方に同じリポジトリ名を埋めるため、あとから `pageTitle` だけを手編集した人は suffix を直し忘れうる。それでも**器を 1 本にする方向は採らない**: `<title>` を組み立てているのは Quartz 本体の `Head.tsx` であり、`cfg.pageTitle` を参照させるにはこのコンポーネントを `quartz-plugins/` 側で差し替えることになる。`<title>` の 1 行のために Head を fork するのは、得られる整合に対して重い。代わりにテンプレートの隣接する 2 行の場所に「この 2 つは同じ値を持つ。片方だけ変えないこと」というコメントを置く（`quartz.config.yaml` はいつでも手編集可能なプレーンな YAML ファイルであり、手編集する人の目に必ず入る場所に注意が置ければ足りる）。

#### 読者に「このサイトが何か」を伝える 3 つのフィールド

**4 つ目の器は作らない**。

| フィールド | 宛先 | 本数 | 置き場所 |
|---|---|---|---|
| `pageTitle` / `pageTitleSuffix` | 読者（**サイト名**） | 1 本・言語中立 | `quartz.config.yaml` |
| `site_description` | 読者（**紹介文**） | 言語ごとに 1 本 | `.wikicommit/config.yml`（§8.8） |
| `theme` | LLM（**内容スコープ**） | 1 本 | `.wikicommit/config.yml`（`docs/DesignDoc-data.md` §3.3） |

宛先が違えば別フィールドにする一方、**宛先も役割も同じものに新しい器を足さない**。サイト名は後者に当たるため、`site_description` には入れない。

**既存リポジトリへの自動移行は行わない**（`quartz.config.yaml` は `always_skip_existing=True` で書かれる）。手で `pageTitleSuffix: " - <サイト名>"` に書き換えれば同じ結果になり、その手順は `CHANGELOG.md` に書いた。ページの再生成は不要（`generated_with` の対象ではなく、ビルド設定の変更であるため）。

**ブラウザでの実表示確認は行っていない** — このリポジトリには Quartz 本体が無い。検証は `Head.tsx` のコードとテンプレートの生成物に対して行い、実表示はパイロットリポジトリへの反映時に確認する。

### 8.12 AI 向けの索引 `llms.txt`

clone していない AI（別のプロジェクトで作業している開発者のエージェント、シェルを持たないチャット）が公開 Wiki を引けるよう、`convert_wikilinks.py` が公開時に `content/llms.txt`（llmstxt.org の慣習）を書く。`.md` ではないので Quartz 組み込みの `Assets` emitter が同じ名前で `public/` へコピーし、`https://<site>/llms.txt` として公開される。`/wikicommit-ask`・`/wikicommit-search` は clone が前提なので、これが clone していない読み手の唯一の経路になる（§10）。検索の仕組みは持たない — 一覧を読ませて、必要なページだけを取りに行かせる。

```markdown
# <pageTitle>

> <site_description（primary_lang）>

The pages of this wiki are generated by an LLM ...（生成・照合・抜取の説明を 1 段落）

The lists below cover the N pages in `ja`; the site also has pages in `en`.

## Index
- [Person](https://<site>/ja/person/): 12 pages      ← Type フォルダ。件数の多い順

## Key pages
- [山田太郎](https://<site>/ja/person/yamada-taro): <properties.description>   ← 被リンクの多い順に 50 件

## Optional
- [Overview](https://<site>/overview/): ...
- [Sources](https://<site>/sources/): ...
```

| 決めたこと | 内容 | 理由 |
|---|---|---|
| どこで作るか | ビルド時に `content/llms.txt` へ書く。コミットしない | 常に最新で、ページを変えるたびの差分も出ない。俯瞰ページ（§8.8.1）・`wikicommit-groups.json` と同じ扱い |
| リンク先 | 公開サイトの HTML。URL は `quartz.config.yaml` の `baseUrl` から組む | 生の Markdown（`raw.githubusercontent.com`）はリポジトリが public であることを前提にし、WikiLink が変換前の形のまま読まれる。`baseUrl` は `deploy.yml` がビルド直前に Pages の URL へ書き換えるので、ビルド時に読めば公開 URL になる。`baseUrl` に scheme は無いので `https://` を付け、`localhost` だけ `http://` にする。読めなければサイトルート相対のリンクにする |
| slug | Quartz の `slugifyFilePath` と同じ規則（`quartz_asset_slug()`）で組む | Quartz は各セグメントを小文字にするので、`ja/Person/yamada-taro.md` は `ja/person/yamada-taro` で公開される |
| 並べるページ | Type 目次 ＋ 被リンク上位 50 件 ＋ `## Optional`（Overview・Sources） | 全ページを並べると慣習の大きさ（数 KB〜数十 KB）を超える。残りのページは Type 目次の先にある |
| 説明文 | `properties.description` を 1 行の平文にする（WikiLink は slug に、300 字で切る） | `[[Type/slug]]` はこのビルドでしか解決できない |
| 言語 | `primary_lang` のページだけ。他の言語は存在を 1 文で示す | 翻訳は原文と同じ問いに答えるので、並べても届く範囲は広がらず大きさだけが倍になる |
| 信頼度 | 冒頭の説明だけに書き、各行には載せない | 各ページの上部に状態が出ており（§8.4）、リンクを辿った AI はそこを読む。行に載せると行が長くなる |
| 文面の言語 | 固定の英語 | 宛先は AI であり読者向けの UI chrome（§8.9.1）ではない。サイト名と `site_description` はそのまま載せる |
| `llms-full.txt` | 出さない | 全文は大きくなりすぎる |

**`robots.txt` は WikiCommit も Quartz も書かない**。GitHub Pages のプロジェクトページ（`<owner>.github.io/<repo>`）では `robots.txt` はホストの直下（`<owner>.github.io/robots.txt`）にしか置けず、リポジトリ側からは制御できない。

**未確認のこと**: Pages 上で実際に `/llms.txt` が取れること、GitMCP などのサービスがこのファイルを読んで答えられることは、実際の公開サイトで確かめていない。`Assets` emitter がこのファイルを名前を変えずにコピーすることは Quartz のソース（`slugifyFilePath` は `.md`・`.html` 以外の拡張子を残し、`.txt` を扱うページ型は無い）から判断した。

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

#### 9.1.1 クエリ語の拡張（同義語・上位語・略語）

FTS5 は語彙が一致しないと何も返さない。ユーザーが「子ども手当」と入力し、Wiki ページが「児童手当」と書いていれば 0 件になる — Wiki がその話題を扱っているにもかかわらず、である。これを埋めるのが本来ベクトル検索（9.2）の役割だが Phase 3 では見送っているため、その**軽量な代替**として、エージェント自身の語彙知識によるクエリ語の拡張を置く。クロスリンガル検索を埋め込み空間ではなくエージェントのクエリ翻訳で実現した 9.3 と同じ発想を、同一言語内の語彙揺れに広げたものである。

**中心的な制約は FTS5 の暗黙 AND にある**。`search_index.py` は語ごとにフレーズ化して空白で連結するため、拡張語を同じクエリ文字列に足すと条件が**厳しくなり**、ヒットは増えるどころか消える（`"児童手当" "子ども手当"` は両方を含むページのみに一致する）。したがって「SKILL.md の指示文で拡張語をクエリに足す」という実装は成立せず、**拡張には OR セマンティクスが必要で、それはスクリプト側にしか置けない**。`search_index.py` の `--expand`（グループ内 OR・グループ間 AND）がこれを担う（`docs/DesignDoc-ScriptSpec.md`）。

**語群ごとに `query` を複数回呼び、Skill 側でマージする案**（スクリプト変更ゼロ。クロスリンガル検索が既に採っているパターン）は採らなかった。呼び出しをまたいだ bm25 スコアは比較不能であり、`wikicommit-ask` が言語間で「naive な近似で妥協する」と明記している問題がそのまま拡大する — 拡張語由来のノイズが原語由来の本命ヒットを押しのけても制御する手段がない。拡張語は「同じ意図の別表現」である以上、同一のランキング空間で評価されるべきである。

**拡張の対象は明示的に限定する**。trigram は部分一致であるため、活用形・複合語（「エンジニア」→「ソフトウェアエンジニア」）は既に無料で拾える。同義語・上位語・略語と正式名の対・英日の対応語・表記ゆれのみを拡張し、活用形・部分文字列で到達できる複合語・意味の重心がずれる関連語は拡張しない。上限は原語 1 語につき 2〜3 語・1 回の検索全体で 5 語程度とする（LLM に任せると際限なく広がるため）。3 文字未満の拡張語は生成しない（trigram で絶対に一致しないため無意味）。**辞書化・永続化は行わない** — 拡張はその場の LLM 判断で行い、シソーラスファイルは持たない（エージェントネイティブ型の設計方針、`docs/DesignDoc-skills.md` §11.0）。

適用範囲は `wikicommit-search` / `wikicommit-ask` / `wikicommit-synthesize` / `wikicommit-quiz` の 4 Skill で、いずれもデフォルト ON。**人間が結果を直接読む `wikicommit-search` だけが、実際に使った拡張語を結果に表示し、`--no-expand` で無効化できる** — 入力していない語がヒットの根拠になっている以上、黙って使うべきではないため。他の 3 つでは拡張は内部処理であり（`wikicommit-ask` の grounding 注記は別途その役割を果たす）表示しない。

**将来 `qmd` 等の既製ツール（9.2 の callout）を採用した場合、同ツールが持つクエリ拡張モデルと本機能の役割は重なる**。本機能はベクトル検索の代替であって前哨ではないため、その時点でどちらを残すかは採用判断と合わせて決める。

### 9.2 セマンティック検索（ベクトル）— 見送り（将来 Phase での再検討課題）

| フェーズ | モデル | 用途 |
|---|---|---|
| （未着手） | `multilingual-e5-base`（278M パラメーター） | コスト・速度のバランスが最良 |
| （未着手） | `BGE-M3` | Dense・Sparse・ColBERT を 1 モデルで統合 |

ベクトルストア候補は **LanceDB**（ローカルファイルベース、PostgreSQL 等の外部 DB 依存なし）。

**Phase 3 では採用しない**。torch / sentence-transformers 等の重量級依存の追加、数百 MB 規模のモデルダウンロード、ページ変更を検知して再エンベディングするインデックス管理パイプラインの実装が必要になり、他の Phase 1–3 実装（stdlib + PyYAML 程度の軽量スクリプト群）と比べて作業量が大きい。クロスリンガル検索は 9.3 の方式（エージェントによるクエリ翻訳 + FTS5 trigram）で代替できる。導入するかどうかは将来 Phase での再検討課題とする（フェーズ未確定）。

```python
import lancedb
import numpy as np

db = lancedb.connect("wiki_index")
table = db.create_table("pages", schema=...)
table.add([{"title": "...", "embedding": np.array(...)}])
results = table.search(query_embedding).limit(10).to_pandas()
```

**再検討するなら、自前の LanceDB 実装より既製ツール（`qmd` 等）の採用を優先候補とする**。`qmd`（ローカル動作・BM25 全文検索＋ベクトル検索＋LLM 再ランキングのハイブリッド、CLI と MCP server の両対応。Karpathy の LLM Wiki 提案〈gist: `karpathy/442a6bf555914893e9891c11519de94f`〉が検索基盤として推奨している）は、`lychee`/`markdownlint-cli2`/`markitdown` と同じ「外部ツールをシェルアウトで呼ぶ」既存パターン（§1.4）に乗せられ、再エンベディングのインデックス管理を `qmd update`/`qmd embed` に肩代わりさせられる。ただし埋め込みモデルのダウンロードそのものの重さ（デフォルトの `embeddinggemma-300M` で約 300MB、再ランカー・クエリ拡張モデルまで含めると計 GB 規模）は自前実装か既製ツールかに関わらず不可避である。CJK 対応が必要な場合は `Qwen3-Embedding-0.6B`（119 言語対応）へのモデル切り替えが可能（切替後は全件再埋め込みが必要）。BM25 とベクトルの統合方式は RRF（Reciprocal Rank Fusion、スコア正規化不要）。`qmd` 自身がローカルで LLM 推論（node-llama-cpp）を行う点は、推論がユーザーのローカルマシン上で完結するため §1.3「LLM 推論はユーザーが持ち込む」原則には抵触しない。

**再検討の時期は Phase 4 のローカル LLM 対応と合わせる**。`qmd` はローカル LLM 推論を前提とするツールであり、Phase 4 の Tauri デスクトップアプリにおけるローカル LLM（Ollama 等）対応と同じ前提（ローカル推論基盤）を必要とする。その対応自体は未決定である（当時の計画は `dev/roadmap-phase4-5.md` にある。同ファイルは公開対象外 — `docs/README.md` §3）。Phase 4 でローカル LLM 対応に着手するなら、その基盤の上で `qmd` 採用も併せて再検討し、見送るなら `qmd` 採用も見送る。

### 9.3 クロスリンガル検索の実装

Phase 3 では埋め込みモデルを使わず、**エージェントによるクエリ翻訳 + FTS5 trigram** でクロスリンガル検索を実現する。`wikicommit-ask` / `wikicommit-search` / `wikicommit-synthesize` / `wikicommit-quiz`（`--topic` 指定時のみ）の 4 Skill は、ユーザーのクエリ言語に加えて `.wikicommit/config.yml` の対象言語（`translation.targets` / `primary_lang`）へも Claude Code 自身がクエリを翻訳し、言語ごとに FTS5 trigram で検索して結果をマージする。専用の翻訳 API や埋め込みモデルを持たず、Skill の指示（SKILL.md）としてエージェントに翻訳を委ねる設計。

**検索の手順**（`wikicommit-ask` / `wikicommit-search` / `wikicommit-synthesize` / `wikicommit-quiz` で共通。`wikicommit-ask` が持つ構造を移植したもの）: クエリの言語を判定し、対象言語ごとにクエリ語を翻訳し、言語ごとに `search_index.py query --lang <lang>` を**逐次**実行し、結果をマージして同一ページの他言語版を重複排除する。`search_index.py` の `--lang` は省略可能なフィルタであり、省略時は全言語を検索するが、クエリが 1 つの言語でしか表現されていなければ他言語のページには trigram が一致しない — クロスリンガル化の本体は検索範囲ではなく語彙の翻訳である。

- **言語ごとの実行は必ず逐次とする** — `search_index.py query` はキャッシュ未生成時に `build`（`DROP` + 全件再構築）を自動実行するため、並列に呼ぶと「キャッシュ未生成」判定が競合して二重ビルドや SQLite のロック競合を起こす。
- **`--lang` 明示時は言語をまたぐ fan-out を行わない**（ユーザーが言語を絞った意図を Skill が上書きしない。`--lang` がそのままオプトアウト手段を兼ねる）。ただし**翻訳まで止めるわけではない** — `<lang>` がクエリの言語と異なる場合、クエリ語はやはり `<lang>` へ翻訳してから検索する。翻訳を止めると `--lang` が「絞り込み」ではなく「必ず空になる検索」になる。
- **検索対象言語は `config.yml` だけで閉じない**。クエリ言語・`primary_lang`・`targets` に加えて `.wikicommit/entity/` 直下に実在する言語ディレクトリも含める（`/wikicommit-translate <page> --lang en` は `targets` に関わらずページを作るため）。全クエリが `--lang` を伴う以上、含めないとそれらのページに端から届かなくなる。設定済みの言語を先に並べ、重複排除の優先順位で勝たせる。
- **`wikicommit-search` の `--limit` は言語数に関わらず言語ごと 10 件**とし、マージ後に 10 件へ絞る。言語ごと 5 件にすると、全ページが翻訳済みの 2 言語 Wiki では重複排除で結果が半分になる。`wikicommit-ask` が grounding 集合を言語で分割するのはヒット 1 件ごとに LLM コンテキストを消費するからであり、行を表示するだけの検索にはその制約がない。
- **重複排除の重みは Skill によって違う**。`wikicommit-quiz` では同一ページの複数言語版が残ると同じ事実についての設問が 2 問生成されるので、必ず排除する。あわせて `wikicommit-quiz` は出題・解説の言語を `--topic` の言語（省略時は `primary_lang`）に固定する（grounding が複数言語にまたがりうるため）。`wikicommit-search` では、抑制された他言語版の存在を `(also in: <lang>)` としてヒット行に併記する（集約で消えたことが分からないと、Wiki が実際より薄く見える）。
- **クロスランゲージのランキング厳密化は行わない**。言語ごとにコーパスサイズと trigram 分布が異なるため bm25 スコアの厳密な比較はできず、`wikicommit-ask` と同じく naive な近似で妥協する（将来 Phase の再検討課題）。

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
>
> Skills による代替は clone していることが前提である。clone していない読み手（公開 Wiki だけを見ている AI）には、検索の仕組みを持たない索引 `llms.txt`（§8.12）を公開サイトに置く。同義語の展開・言語をまたぐ検索・翻訳ページの集約はこの経路では得られず、それが要る利用はホスト型 MCP の範囲である。

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
