# 品質ゲート仕様書

> **バージョン**: 0.3（Draft）
> **作成日**: 2026-06-28
> **対応DesignDoc**: [DesignDoc-pipeline.md](DesignDoc-pipeline.md) §7

`wikicommit-merge` が実行する品質チェックの仕様。各チェックの blocking / warning 分類とマージ条件を定義する。Python スクリプトへの委譲仕様は [DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) を参照。

> **設計上のトレードオフ（意図的）**: 品質チェックは `wikicommit-merge` Skill を経由した場合にのみ実行される。`git push` → `gh pr create` → 手動マージという直接操作ではすべてのチェックがバイパスされる。これは GitHub Actions による強制から Skill 実行による任意への意図的な移行であり、MVP フェーズでは開発者が限定的なため許容する。Phase 3 以降で GitHub Actions による二重ガードの導入を検討する。

---

## チェック一覧

| チェック | 実行スクリプト / ツール | フェーズ |
|---|---|---|
| フロントマター検証 | `validate_frontmatter.py` | Phase 1 |
| WikiLink 検証 | `check_wikilinks.py` | Phase 2 |
| 生 HTML 検出 | `check_raw_html.py` | Phase 3 |
| 外部リンク検証 | lychee | Phase 2 |
| スタイル | markdownlint-cli2 | Phase 2 |
| 孤立ページ・重複ページ | `check_orphans.py` | Phase 1 |

この 6 本が `wikicommit-merge` の実行する全チェックであり、この順に実行する。

**鮮度チェックはこの一覧に含まれない** — PR チェックではなく `/wikicommit-status` 側で走る（下記「鮮度チェック」節）。同節が挙げる 3 本は代表例であり、`/wikicommit-status` が実際に呼ぶスクリプトはこれより多い。**全数と各スクリプトの入出力は [DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) が正本**であり、ここに二重の表を持たない（同じ一覧を 2 か所で保守すると、片方だけが古くなる）。

---

## フロントマター検証

実装: `validate_frontmatter.py`（変更ファイルのみを引数として渡す）

| チェック | blocking / warning |
|---|---|
| 必須フィールド欠落（title, lang, type, sources） | blocking（`translated_from` が存在する翻訳ページ、および `index.md` は sources を除く） |
| `type` が `schema:` で始まらない | blocking |
| `type` がページのディレクトリと一致しない（`custom/` サブパスの欠落等。Issue #545） | blocking（`<lang>/<Type>/<slug>.md` の形に解決できないページは対象外） |
| `review_status` が許可値以外 | blocking |
| `sources[].type` が未定義 | blocking |
| `sources[].hash` が `sha256:` 形式でない | blocking |
| `sources[].path` のファイルがリポジトリ内に存在しない | blocking |
| `translated_from` のファイルが存在しない | blocking |
| `source_commit` が 40 文字でない | blocking |
| `expires_at` が `YYYY-MM-DD` 形式でない | blocking |
| `review_status` 未設定 | warning（pending として扱う） |

---

## WikiLink 検証

実装: `check_wikilinks.py`

PR の種別（追加 / 削除）によって挙動が異なる。

**PR 種別の判定**: `wikicommit-merge` Skill が `git show HEAD:<path>` で変更前の frontmatter を確認し、旧 `status` が `removed` でなく現 `status` が `removed` であるファイルを「削除対象ファイル」として特定する。そのようなファイルが含まれる場合を「削除フロー」とし、`check_wikilinks.py` の `--deleted` に渡す。

| 状況 | blocking / warning |
|---|---|
| 追加・変更：`status: removed` ページへの WikiLink | blocking |
| 追加・変更：存在しないページへの WikiLink（同じ slug が別 Type に実在する） | blocking（Issue #563。参照先の実体は在り、正しい対処はリンクの Type セグメント 1 語の修正であるため、下記 Issue #340 の緩和理由が当てはまらない。ERROR メッセージが実在する Type を名指しする） |
| 追加・変更：存在しないページへの WikiLink（どの Type にも実体なし） | warning のみ（Issue #340 で blocking から緩和。ブロックすると書き手が「まだ無い概念は WikiLink 化せず地の文で書く」を選びがちになり、繰り返し言及される概念がページ化されないまま埋もれるため。集計は `check_wanted_pages.py` が別途担う。なお同一コミット内で新規追加されるページへのリンクはそもそもリンク先候補として扱い、この行の対象にならない） |
| 削除フロー：削除対象ページへの被リンクが残っている | warning のみ |

---

## 生 HTML 検出

実装: `check_raw_html.py`（変更ファイルのみを引数として渡す）

| チェック | blocking / warning |
|---|---|
| ページ本文に生 HTML タグ（`<tag ...>` / `</tag>`）が含まれる | blocking（Issue #377） |

frontmatter は対象外。コードフェンス・インラインコードで囲まれた範囲、および CommonMark のオートリンク（`<https://example.com>`）は除外する。

**許可リストは持たない**（「危険なタグだけ禁止」ではなく「生 HTML 自体を禁止」）。画像・動画・YouTube の埋め込みは標準 Markdown 構文 `![alt](path-or-url)` だけで足りるため、ページ本文が生 HTML を必要とする正当なケースが存在しない。一方 Quartz コアは `allowDangerousHtml` を常時有効にしており、経路 A では `review_status: pending` の LLM 生成ページが人間のレビュー前に公開されるため、ソース文書由来の `<script>` / `<iframe>` がそのまま実行されうる。詳細は [DesignDoc-publish.md](DesignDoc-publish.md) §8.6 参照。

---

## 外部リンク検証

実装: [lychee](https://github.com/lycheeverse/lychee-action)

対象: `sources[].url`（`type: url` / `type: wikicommit`）および本文中の `https://` リンク

| チェック | blocking / warning |
|---|---|
| HTTP 4xx（存在しない） | warning |
| タイムアウト・接続エラー | warning（ネットワーク環境依存のため） |

lychee 設定（`.lychee.toml`）:

```toml
exclude_path = []
timeout = 10
max_retries = 2
# GitHub レート制限を避けるためトークンを設定する（secrets.GITHUB_TOKEN または環境変数 GITHUB_TOKEN）
github_token = "${GITHUB_TOKEN}"
```

---

## スタイル検証

実装: `markdownlint-cli2`

対象: `.wikicommit/entity/**/*.md`

`.markdownlint.json` 設定方針:

| ルール | 設定 |
|---|---|
| MD041（first-line-heading） | 無効化（frontmatter があるため） |
| MD013（line-length） | 無効化（日本語は折り返しが読みにくさに直結しないため） |
| MD033（no-inline-html） | 無効化（review_status バナー等で HTML を使う可能性があるため） |

**blocking / warning**: 常に warning のみ（Phase 2）。Phase 3 以降で blocking 化を検討。

---

## 孤立ページ・重複ページ検出

実装: `check_orphans.py`

| チェック | blocking / warning |
|---|---|
| orphan（孤立ページ）検出 | warning のみ |
| 重複ページ検出 | blocking |

**orphan 対象外**: `<Type>/index.md` および `status: removed` のページ。

---

## 鮮度チェック（定期実行 or `/wikicommit-status`）

PR チェックには含めない。`/wikicommit-status` 実行時、または定期バッチとして手動実行する。

**下表は代表的な 3 本であり全数ではない**。`/wikicommit-status` が呼ぶスクリプトはこれより多く、各スクリプトの入出力・終了コードを含めた全数は [DesignDoc-ScriptSpec.md](DesignDoc-ScriptSpec.md) が正本である（上記「チェック一覧」の注記と同じ理由で、ここに同じ表を持たない）。

| チェック | スクリプト | 出力 |
|---|---|---|
| `expires_at` 期限切れ | `check_expires.py` | コンソールに warning 出力 |
| 翻訳陳腐化・未翻訳検出 | `check_translation_status.py` | コンソールに warning 出力 |
| ingest ハッシュずれ | `check_ingest_freshness.py` | 管理ファイルの `status` を `outdated` に書き換え（サイドエフェクトあり） |

---

## マージ条件

| 経路 | 条件 | Merge 後の review_status |
|---|---|---|
| 経路 A: 自動生成（wikicommit-generate → wikicommit-merge） | 品質チェック全 blocking PASS | `pending`（レビュー追跡 Issue の Close 待ち） |
| 経路 A: レビュー追跡 Issue | 人間による Close（マージ自体は `review-issue-close-sync.yml` が自動実行。Issue #313） | `reviewed`（Issue Close をトリガーに自動更新） |
| 経路 B: 手動作成（wikicommit-review → wikicommit-merge） | 品質チェック全 blocking PASS | `reviewed`（wikicommit-review がローカルで設定済み） |

`style` チェックと `orphan` の warning はマージをブロックしない。
