# テストについて

`wikicommit/wikicommit` を読みに来た方向けの前置きです（開発リポジトリでは
[`docs/DesignDoc-TestSpec.md`](../docs/DesignDoc-TestSpec.md) が仕様側の正本です）。

## 1. 日本語で書かれています

docstring・アサーションメッセージ・コメントの多くが日本語です。設計判断の記録を
そのままテストに書き付ける方針を採っているため（[`docs/README.md`](../docs/README.md) §1 と
同じ位置づけ）、「何を検証しているか」だけでなく「なぜその形で検証しているか」が
本文に書いてあります。英語で書かれたものと混在しており、揃える予定は今のところ
ありません。

## 2. `Issue #NNN` は非公開のトラッカーを指します

`docs/` と同じです（[`docs/README.md`](../docs/README.md) §2）。番号は
**WikiCommit を開発している非公開リポジトリ**の Issue を指しており、公開リポジトリでは
解決できません。リンクではなく、記述同士を束ねるラベルとして読んでください。

## 3. 公開リポジトリでは一部が skip されます

このリポジトリは公開対象のホワイトリストをコピーして作られるため、
`dev/`・`Issues/`・`CLAUDE.md`・`CONTRIBUTING.md`・`CHANGELOG_ja.md`・`.gitignore`・
`.wikicommit/config.yml` は含まれません。それらを読むテストは skip されます —
判定は [`_publication.py`](_publication.py) が 1 箇所で持っており、**ファイルが無いこと
自体は判定に使いません**（リネームと見分けが付かなくなるため）。skip されるのは
以下です。

| テスト | 読む先 |
|---|---|
| `test_check_issue_registration.py`（モジュール全体） | `dev/scripts/check_issue_registration.py` |
| `test_config_has_no_dead_review_block.py`（`[own]`） | このリポジトリ自身の `.wikicommit/config.yml` |
| `test_changelog_sync.py`（日本語版の位置づけ） | `CHANGELOG_ja.md` |
| `test_run_record_tree.py`（ルート側の `.gitignore`） | ルートの `.gitignore` |
| `test_commit_trailer_placeholders.py`（規約文の所在） | `CLAUDE.md` / `CONTRIBUTING.md` |

いずれも「公開されていないものを検査しない」だけで、配布物側の検査は公開リポジトリでも
そのまま走ります。
