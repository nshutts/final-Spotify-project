# Labeling guide (human labels for the golden 50 and the development 40)

Label the review text itself. Stars are metadata: do not set topic, intent, sentiment, or severity from the star rating. Examples below are written for this guide, not taken from the dataset.

## Columns you fill in

| Column | What to enter |
|---|---|
| `topic` | One of: access, usability, playback, downloads, catalog, billing, support, other |
| `intent` | One of: cancellation, complaint, request, praise, unclear |
| `sentiment` | One of: -1, -0.5, 0, 0.5, 1 |
| `severity` | An integer 1 to 5 |
| `entities` | Feature words the review names, separated by `;`. Leave blank if none. |
| `evidence_quote` | Copy the exact words from the review that support your labels. Use the full text if the review is short. |
| `needs_review` | `yes` if you're unsure or the context is missing, otherwise `no` |

Keep `review_id` and the source columns exactly as they are.

## Topic (one primary topic)

- **access:** login, signup, password, account access.
  - Example: "Can't log in, it keeps saying my password is wrong." → access
- **usability:** navigation, controls, layout, queue or playlist management, ad interruptions.
  - Example: "Too many ads between songs." → usability
- **playback:** playback failures, crashes, lag, connection failures, audio quality.
  - Example: "Songs freeze every few seconds." → playback
- **downloads:** downloading, saved music, offline listening, downloads disappearing.
  - Example: "My downloaded playlist vanished." → downloads
- **catalog:** missing songs or artists, search, recommendations, lyrics.
  - Example: "My favourite band is not on here." → catalog
- **billing:** price, charges, subscriptions, paywalls, premium entitlement.
  - Example: "I was charged twice this month." → billing
  - Note: mentioning a paid plan alone is not billing. "Premium is great" is praise, so the topic is `other` unless a specific feature is praised.
- **support:** contacting support and the response.
  - Example: "Support never answered my email." → support
- **other:** general praise or criticism, unrelated content, or no supported specific topic.
  - Example: "Bad app." → other

When two topics both apply, choose the topic of the most severe specific problem. If tied, choose the first one mentioned.

## Intent (precedence: cancellation, complaint, request, praise, unclear)

- **cancellation:** explicitly leaving, uninstalling, cancelling, or threatening to.
  - Example: "Deleting this app and cancelling my plan." → cancellation
- **complaint:** a negative experience, including mixed praise and criticism.
  - Example: "Good music, but the app crashes constantly." → complaint
- **request:** a desired change without a reported failure.
  - Example: "Please add a sleep timer." → request
- **praise:** positive comment with no reported problem.
  - Example: "Love the new mixes." → praise
- **unclear:** bare boycott slogans, meaningless text, or no content to evaluate.
  - Example: "Boycott!" with no reason → unclear
  - A slogan with a product complaint or personal departure is not unclear.

## Sentiment (overall feeling of the text)

- **-1:** very negative, strong anger or dislike.
- **-0.5:** negative, clear dissatisfaction without strong anger.
- **0:** neutral or mixed.
- **0.5:** positive, clear satisfaction.
- **1:** very positive, strong enthusiasm.

## Severity (the most serious specific problem)

- **1:** no reported problem: praise, unclear content, or a pure feature request.
- **2:** dislike, generic criticism, minor annoyance, or cosmetic issue. No functional loss.
  - Example: "Ugly colours." → 2
- **3:** a degraded or restricted function. Some use or a workaround remains.
  - Example: "Shuffle doesn't work on my phone, but I can still play albums." → 3
- **4:** a core task is clearly blocked, such as being unable to log in or play music.
  - Example: "I can't log in at all since the update." → 4
- **5:** explicit serious financial, privacy, or data harm.
  - Example: "My card was charged for a plan I never bought and I can't get a refund." → 5
  - An expensive plan, a crash, or angry language alone does not make it a 5.

Stars, angry language, or cancellation intent alone do not set severity.

## Entities

Write the feature words the review explicitly names, such as `download`, `playlist`, `login`, `podcast`, separated by `;`. Do not add words the review doesn't contain.

## Evidence quote

Copy the words that support your labels, exactly as they appear. Short reviews: use the full text. Long reviews: the sentence that best supports your labels. The quote must be an exact piece of the review, including punctuation.

## When to mark needs_review

Mark `yes` when:
- the text is too short or unclear to decide between two labels,
- the text is in a language you can't read well,
- a label depends on context the review doesn't provide.

Still enter your best label, so the disagreement is visible.

## Procedure

1. Read the whole review before choosing any label.
2. Pick topic, intent, severity, and sentiment from the text alone.
3. Fill in entities and evidence_quote last, copying the text exactly.
4. Save the file as CSV, keeping every row and column.
