export default {
  components: {
    wikicommitBanner: {
      // Issue #774: the heading states a fact that is true of the page in
      // either state, so it no longer swaps. "Nobody has read this page yet"
      // (Issue #740) was false in front of the person reading it: what it
      // actually said was that no read by someone with write access had been
      // recorded, a distinction most readers do not hold. Dropping it is what
      // finally makes the heading obey Issue #739's principle — review adds a
      // line, it does not retract a warning — because a heading that swaps
      // forces the pending side to say *something*, and the only thing left to
      // say there is a negation. Issue #751 had to land first: with the
      // machine's own source check stated a line below, dropping the claim
      // about reading cannot be read as "nothing has been done to this page".
      title: "LLM が自動生成したページです",
      // Split from the heading (Issue #774): the heading carries the fact, this
      // carries what follows from it. Before the split the two said nearly the
      // same thing.
      body: "内容に誤りがある可能性があります。",
      generatedAt: "生成日:",
      generatedBy: "生成モデル:",
      translatedAt: "翻訳日:",
      translatedBy: "翻訳モデル:",
      // Issue #800: a sentence with a {name} placeholder rather than a bare
      // "label: value" pair, because the line now states what the reading
      // found as well as who did it. The renderer splits on {name} and puts
      // the profile link in the gap. `counts` in convert_wikilinks.py already
      // uses placeholders this way, so this is not a new pattern here.
      readBy: "{name} が読み、明らかな問題は見つかりませんでした",
      // Issue #774: what `titleReviewed` used to be, moved out of the heading
      // and into the line review adds. It is shown only when `reviewed_by` is
      // absent — a route B page (`/wikicommit-review` runs locally and cannot
      // obtain a GitHub login) or one reviewed before that field existed. With
      // a name, the `readBy` line below says the same thing and says who,
      // and printing both would repeat "read" twice. Having this fallback is
      // what keeps the two states distinguishable without depending on
      // `reviewed_by` being present.
      readByAPerson: "人が読み、明らかな問題は見つかりませんでした",
      // Issue #751: what the machine check actually compared, stamped onto the
      // published copy of the page by convert_wikilinks.py and present on no
      // page in .wikicommit/entity/. Worded as "checked against its sources"
      // rather than "reviewed" or "verified": Pass 4 compares the page with the
      // documents it was written from and nothing else — completeness is
      // explicitly out of scope (Issue #722), and harm and conflicts with the
      // reader's own knowledge are seen by no layer at all (Issue #723).
      // Over-claiming here would repeat, in the opposite direction, the error
      // Issue #740 is correcting for `reviewed`.
      aiReviewAt: "出典と照合:",
      aiReviewBy: "照合モデル:",
      unknown: "不明",
      reviewStatusLink: "このページのレビュー状況を見る",
      reportLink: "気づいた点を報告する",
      // Issue #742: for a reader without a GitHub account this link lands on a
      // login wall — `/issues/new?...` redirects to `login?return_to=<the whole
      // URL>`, so the form is never shown. Issue #665 fixed the same shape of
      // error one layer up (the tracking Issue told readers to close an Issue
      // they have no permission to close); this is the layer below it. The
      // prefilled title and body do survive signing in, so the only thing left
      // to fix is that the link gives no warning — hence a statement of fact,
      // not a recruiting line. Kept out of the link label so the call to action
      // stays the loudest thing in the row (the visual-weight constraint this
      // shares with Issue #738).
      reportLinkAccountNote: "（GitHub アカウントが必要）",
      reportTitlePrefix: "[報告]",
      reportBodyPage: "ページ:",
      reportBodyLanguage: "言語:",
      reportBodyOriginal: "原文ページ:",
      // Issue #738: the two checklist items Issue #723 marked "only a person
      // can check this" reach only whoever browses the repository's Issue
      // list — in practice the operator. The reader most likely to notice the
      // harm item is usually the subject of the page, who never opens that
      // list but does read the page. This guidance rides the report link
      // instead, which every reader sees.
      reportBodyGuidanceHeading:
        "以下は自動チェックでは見つけられない種類の問題です。当てはまるものがあれば書いてください（探しに行く必要はありません。読んでいて気づいたことだけで構いません）。",
      reportBodyGuidanceHarm: "- 実在の人物・組織について、書きすぎ・断定しすぎに感じた箇所",
      reportBodyGuidanceKnowledge: "- あなたが知っていることと食い違う箇所（URL があれば添えてください）",
      reportBodyGuidanceContradiction: "- 他のページと言っていることが違うと感じた点",
      // Not a closed list: a typo, a stale fact or a dead link is just as
      // welcome. Stated so the bullets above do not read as "report nothing
      // else".
      reportBodyGuidanceFooter: "上記以外（誤字・古くなった情報・リンク切れなど）も歓迎します。",
      // The heading gives the reporter a marked place to write. `body=`
      // replaces report.md's own `## Page` / `## Problem` headings entirely, so
      // without this the prefilled body ends at the guidance and there is
      // nowhere obvious to type. The page facts above need no heading of their
      // own — each line already labels itself.
      reportBodyProblemHeading: "## 報告内容",
      siteSummaryPages: "総ページ数:",
      siteSummaryReviewed: "人が読んで確認:",
      siteSummaryReviewNote: "ページは LLM が生成した時点で公開されます。出典との照合は機械が行い、「人が読んで確認」はそのうち人が最後まで読み、明らかな問題を見つけなかった件数です。人による確認は設計上一部のページのみであり、この数字が総数に達することは目指していません。網羅的な品質保証でもありません。",
      siteSummaryAiReviewed: "出典と照合:",
      siteSummaryAiReviewNote: "「出典と照合」は生成時に、ページの記述をその出典と照合した件数です。照合しているのは出典との一致だけで、網羅性・実在の人物や組織への影響・読者自身の知識との食い違いは見ていません。",
    },
  },
}
