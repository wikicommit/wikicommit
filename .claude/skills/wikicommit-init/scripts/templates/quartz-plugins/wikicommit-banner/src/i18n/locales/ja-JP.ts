export default {
  components: {
    wikicommitBanner: {
      // Issue #740: `review_status` is a two-valued field, which makes it
      // structurally a container for an *event* — it happened, or it has not
      // yet. What it held until now was a *claim* about the page, and a claim
      // has content, which is why the content had to be bolted on as a
      // checklist. The heading follows the field back to what it can actually
      // carry: nobody has read this page yet. That is a fact about reach, not
      // a defect in the page — and after Issue #751 the machine's own source
      // check is stated a line below, so "nobody has read it" can no longer be
      // misread as "nothing has been done to it".
      title: "このページはまだ誰も読んでいません",
      body: "LLM が自動生成しました。内容に誤りがある可能性があります。",
      generatedAt: "生成日:",
      generatedBy: "生成モデル:",
      translatedAt: "翻訳日:",
      translatedBy: "翻訳モデル:",
      reviewedBy: "読んだ人:",
      // Issue #739: the reviewed state adds a line rather than removing the
      // warning, so it needs a heading of its own. Wording it as "a person
      // checked this" and no further keeps it to what `reviewed` actually
      // means (Issue #723's transition table); anything stronger would be a
      // guarantee nobody made. It also carries the fact for a reviewed page
      // with no `reviewed_by` — route B pages and anything reviewed before
      // that field existed — so no name-less placeholder line is needed.
      titleReviewed: "このページは人が読みました",
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
      siteSummaryReviewed: "人が読んだページ:",
      siteSummaryReviewNote: "ページは LLM が生成した時点で公開されます。上の数字は、そのうち人が最後まで読んだ件数です — Wiki の完成度でも、内容の正しさの保証でもありません。",
    },
  },
}
