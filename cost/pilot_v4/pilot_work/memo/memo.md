# Decision memo: where the next quarter of Spotify product effort should go

**Recommendation: Usability.** The memo model (Jev, role `memo`) chose this area from the saved aggregates and evidence pack with probability 1.00.

This agrees with the baseline ranking: Usability has the highest combined priority score of the four candidate areas.

## Supporting numbers (baseline ranking)

Priority score = complaint count × mean severity = severity sum. Bracketed IDs are rows in `claims.csv`.

| Rank | Issue | Dominant problem (group role) | Complaints | Mean severity | Priority score |
|---|---|---|---|---|---|
| 1 | ISS-USABILITY | too many or intrusive ads | 19 [C-ISS-USABILITY-complaint_count] | 2.473684 [C-ISS-USABILITY-mean_severity] | 47 [C-ISS-USABILITY-priority_score] |
| 2 | ISS-OTHER | general dissatisfaction with the app | 12 [C-ISS-OTHER-complaint_count] | 2.083333 [C-ISS-OTHER-mean_severity] | 25 [C-ISS-OTHER-priority_score] |
| 3 | ISS-BILLING | basic features locked behind Premium | 6 [C-ISS-BILLING-complaint_count] | 3.000000 [C-ISS-BILLING-mean_severity] | 18 [C-ISS-BILLING-priority_score] |
| 4 | ISS-PLAYBACK | mixed playback problems | 5 [C-ISS-PLAYBACK-complaint_count] | 3.600000 [C-ISS-PLAYBACK-mean_severity] | 18 [C-ISS-PLAYBACK-priority_score] |
| 5 | ISS-CATALOG | songs or artists missing or removed | 5 [C-ISS-CATALOG-complaint_count] | 1.800000 [C-ISS-CATALOG-mean_severity] | 9 [C-ISS-CATALOG-priority_score] |
| 6 | ISS-ACCESS | login or sign-in failures | 2 [C-ISS-ACCESS-complaint_count] | 4.000000 [C-ISS-ACCESS-mean_severity] | 8 [C-ISS-ACCESS-priority_score] |
| 7 | ISS-DOWNLOADS | offline mode not working | 2 [C-ISS-DOWNLOADS-complaint_count] | 3.000000 [C-ISS-DOWNLOADS-mean_severity] | 6 [C-ISS-DOWNLOADS-priority_score] |

All complaint and cancellation reviews: 51.

## The four candidate areas compared

| Area | Issues | Complaints | Share of all complaints | Priority score | Model probability |
|---|---|---|---|---|---|
| Usability | ISS-USABILITY | 19 | 37.2% | 47 | 1.00 |
| Access | ISS-ACCESS | 2 | 3.9% | 8 | 0.00 |
| Playback | ISS-PLAYBACK | 5 | 9.8% | 18 | 0.00 |
| Billing / support | ISS-BILLING | 6 | 11.8% | 18 | 0.00 |

Billing / support combines ISS-BILLING and ISS-SUPPORT; its counts are sums of those two issue rows.

## Representative evidence

- Access · `32fb340f-4f9f-4551-8dae-755221e58d6a` (ISS-ACCESS, severity 4): "It not letting me into my account and there are to many ads"
- Access · `de0a9cdf-8974-48bc-802f-331228df4619` (ISS-ACCESS, severity 4): "Will not except my password"
- Usability · `45c561b9-cc47-4d80-95d3-f0d20bc84af3` (ISS-USABILITY, severity 4): "The update made the app useless .... Uninstall krdia ye app ab bekar hai ... Wynk hi theek h"
- Usability · `9e5f9745-f8be-48d3-b9de-4d118507d94a` (ISS-USABILITY, severity 4): "Doesn't deserve even one star. Like what's the problem? We can't even go back few second to play music? WHAT IN THE WORLD IS THIS UPDATE? YOU PEOPLE NEED MORE MONEY?! gonna delete the app if they don'"
- Usability · `e5e6c55f-3069-4b7c-9807-f8b5d5bf2726` (ISS-USABILITY, severity 4): "Too many ads.... it's literally useless if u hv not taken premium"
- Playback · `46ff0c74-5e86-4e5b-b4cd-36201aab0f9e` (ISS-PLAYBACK, severity 4): "I am unable to use my Google assistant on the app.it says playing your Spotify playlist but do not play the songs"
- Playback · `4ab2089a-ffa8-49e7-a8a3-aeb583a96796` (ISS-PLAYBACK, severity 4): "Iam a premium user. But this app if i using wifi not able to connect Internet. But if using mobile data it will work. Some songs quality also very poor comparing to the YouTube music."
- Playback · `55cc3abf-c295-4591-8c3a-78085cfdefaa` (ISS-PLAYBACK, severity 4): "The latest update has caused my app to crash I cant open the app please fix."
- Billing / support · `a78d831a-69f4-428a-9235-cfdd9775c509` (ISS-BILLING, severity 4): "You can't even listen to music you want it just shuffles it, like what the hell? This app is killing it self and forcing you to pay premium for basic things like just listening to music."
- Billing / support · `ad730d1a-829a-4dc4-9561-7e1cd07e2c30` (ISS-BILLING, severity 4): "Why it requires premium just to play next music / to choose music ?? And why the specific part of song cannot be played ?"
- Billing / support · `21915fcd-9a35-48ba-b277-6296c4154603` (ISS-BILLING, severity 3): "This app the new update has made everthing premium and so usless i thought this app is good but no."

## Limitations

- Reviews are self-selected Google Play reviews from May 2022 to November 2023; they are not a sample of all users. Counts measure complaint volume in reviews, not prevalence among customers.
- Cancellation language is expressed intent, not observed churn. No revenue, plan tier or retention effect is calculated or implied.
- Labels come from an automated classifier (Jev). See the golden-set evaluation and verifier report for measured agreement and known errors.
- Coverage: 100 completed classifications and 0 quarantined records in this run.
- Topics are coarse issues (one per topic); sub-problems within an issue are named from a 25-quote sample and are indicative only.
