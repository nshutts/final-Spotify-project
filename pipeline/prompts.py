"""Versioned questions for every model role. All roles use Jev (TypeSafe).

Each role has its own instructions, inputs and outputs:
  enrich  - labels one review text (topic, intent, severity, sentiment)
  verify  - independently re-labels a sampled review with differently worded questions,
            never seeing the enrich answer
  group   - names the dominant problem inside one issue from a bounded evidence pack
  memo    - chooses the recommended product priority from saved aggregates and evidence

Wording is deliberately short: Jev bills input tokens and the questions are sent with every
review, so question length drives the cost of the full run.
"""

ENRICH_VERSION = "enrich-v4"
VERIFY_VERSION = "verify-v1"
GROUP_VERSION = "group-v1"
MEMO_VERSION = "memo-v1"
SCHEMA_VERSION = "schema-v3"

TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
INTENTS = ("cancellation", "complaint", "request", "praise", "unclear")   # precedence order

# enrich-v4: compressed wording. The v3 pilot (2026-10-20) measured ~813 billed input tokens per request,
# almost all from question text (~0.44 tokens per character of question JSON), projecting to ~$17 for the
# full run against a $10 cap. v4 keeps the same labels and order in about a third of the characters; the
# contract's detailed rules (tie-breaks, premium-only controls, boycott slogans) are no longer spelled out to
# the model, which is a measured quality trade-off reported in the evaluation. v3 is kept below for the record.
ENRICH_QUESTIONS = {
    "topic": {"type": "choice", "instructions": "Main topic (most severe problem)",
              "criteria": {"access": "login, account", "usability": "controls, ads", "playback": "won't play, crashes",
                           "downloads": "offline", "catalog": "songs, search, lyrics", "billing": "price, premium",
                           "support": "customer support", "other": "general"}},
    "intent": {"type": "choice", "instructions": "Intent",
               "criteria": {"cancellation": "quitting", "complaint": "negative", "request": "wants change",
                            "praise": "positive", "unclear": "meaningless"}},
    "severity": {"type": "choice", "instructions": "Problem severity",
                 "criteria": {"1": "none", "2": "annoyance", "3": "degraded", "4": "blocked",
                              "5": "money or privacy harm"}},
    "sentiment": {"type": "score", "instructions": "Sentiment",
                  "criteria": ["very negative", "negative", "neutral", "positive", "very positive"]},
}

ENRICH_QUESTIONS_V3 = {
    "topic": {
        "type": "choice",
        "instructions": ("Main topic of this Spotify app review. With several problems pick the most "
                         "severe, then the first mentioned. For praise pick the first praised feature."),
        "criteria": {
            "access": "login, signup, password, account access",
            "usability": "navigation, controls, layout, queue or playlist management, ads",
            "playback": "playback failure, crashes, lag, connection, audio quality",
            "downloads": "downloads, offline listening, saved music",
            "catalog": "missing songs or artists, search, recommendations, lyrics",
            "billing": "price, charges, subscription, paywall, premium-only features",
            "support": "contacting customer support, support response",
            "other": "general praise or criticism, unrelated or unclear text",
        },
    },
    "intent": {
        "type": "choice",
        "instructions": "Reviewer intent. Use the first option that applies.",
        "criteria": {
            "cancellation": "says they are leaving, uninstalling, cancelling, or threatening to",
            "complaint": "any negative experience, including mixed reviews or just 'bad app'",
            "request": "asks for a change without reporting a failure",
            "praise": "positive, no problem reported",
            "unclear": "meaningless, unrelated, or a bare boycott slogan",
        },
    },
    "severity": {
        "type": "choice",
        "instructions": ("Severity of the most serious problem the text describes. "
                         "Ignore angry tone and cancellation threats."),
        "criteria": {
            "1": "no problem: praise, unclear text, or a pure feature request",
            "2": "dislike, generic criticism, or minor annoyance",
            "3": "a feature degraded or restricted, some use remains",
            "4": "a core task blocked, e.g. cannot log in or play music",
            "5": "explicit serious money, privacy, or data harm",
        },
    },
    "sentiment": {
        "type": "score",
        "instructions": "Overall sentiment of the text.",
        "criteria": ["very negative", "negative", "neutral or mixed", "positive", "very positive"],
    },
}

# The verifier asks the same label questions in different words, as a separate role.
VERIFY_QUESTIONS = {
    "topic": {
        "type": "choice",
        "instructions": ("Which product area does this review mainly concern? If it raises several "
                         "issues, choose the area of the worst one; if praise, the first praised area."),
        "criteria": {
            "access": "signing in, creating or recovering an account",
            "usability": "app layout, controls, navigation, managing queue or playlists, advertising",
            "playback": "music not playing, app crashing or freezing, buffering, sound quality",
            "downloads": "downloading songs, offline mode, saved or downloaded music",
            "catalog": "song or artist availability, search results, recommendations, lyrics",
            "billing": "cost, payments, subscription plans, features locked behind Premium",
            "support": "reaching Spotify customer service or its replies",
            "other": "nothing specific: general opinion, off-topic or unreadable",
        },
    },
    "intent": {
        "type": "choice",
        "instructions": "What is the reviewer doing? Take the earliest option in this list that fits.",
        "criteria": {
            "cancellation": "announces quitting, deleting the app, ending a subscription, or threatens it",
            "complaint": "reports something bad or criticises the app, even alongside praise",
            "request": "suggests a feature or change without describing a failure",
            "praise": "only positive comments",
            "unclear": "no evaluable meaning, unrelated text, or slogan only",
        },
    },
    "severity": {
        "type": "choice",
        "instructions": "How much does the described problem hurt use of the app? Judge the facts, not the tone.",
        "criteria": {
            "1": "no problem described",
            "2": "an annoyance or general dislike only",
            "3": "something works badly or is limited, but the app is still usable",
            "4": "the user cannot do a core task at all",
            "5": "money lost, privacy breached, or data lost, stated explicitly",
        },
    },
}

# Candidate problem names per issue for the group role (Jev picks the dominant one from examples).
GROUP_CANDIDATES = {
    "access": ["login or sign-in failures", "account locked, hacked or lost", "signup or verification problems",
               "mixed access problems"],
    "usability": ["too many or intrusive ads", "unwanted UI or redesign changes", "shuffle and skip limits",
                  "playlist or queue management", "mixed usability problems"],
    "playback": ["app crashes or will not open", "songs stop, pause or skip", "connection or loading errors",
                 "audio quality or volume", "mixed playback problems"],
    "downloads": ["downloads disappear", "offline mode not working", "cannot download", "mixed download problems"],
    "catalog": ["songs or artists missing or removed", "lyrics unavailable", "poor recommendations",
                "search problems", "mixed catalog problems"],
    "billing": ["price too high", "basic features locked behind Premium", "unexpected charges or refunds",
                "premium not activating", "mixed billing problems"],
    "support": ["no response from support", "unhelpful support", "mixed support problems"],
    "other": ["general dissatisfaction with the app", "dislike of a recent update",
              "political or boycott statements", "mixed other complaints"],
}

# The memo role chooses among the four candidate areas named in the assignment question.
MEMO_AREAS = {
    "access": "login and account access problems",
    "usability": "controls, navigation and ad interruptions",
    "playback": "playback failures, crashes and lag",
    "billing_support": "pricing, paywalls, charges and customer support",
}
MEMO_QUESTIONS = {
    "priority": {
        "type": "choice",
        "instructions": ("Using only these saved complaint metrics and evidence, which product area should "
                         "receive the next quarter of product effort? Weigh complaint volume and severity."),
        "criteria": MEMO_AREAS,
    },
}


def label_config(model):
    return f"{model}|{ENRICH_VERSION}|{SCHEMA_VERSION}"
