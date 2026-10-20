# Decision memo: where the next quarter of Spotify product effort should go

**Recommendation: Usability.** The memo model (Jev, role `memo`) chose this area from the saved aggregates and evidence pack with probability 1.00.

This agrees with the baseline ranking: Usability has the highest combined priority score of the four candidate areas.

## Supporting numbers (baseline ranking)

Priority score = complaint count × mean severity = severity sum. Bracketed IDs are rows in `claims.csv`.

| Rank | Issue | Dominant problem (group role) | Complaints | Mean severity | Priority score |
|---|---|---|---|---|---|
| 1 | ISS-USABILITY | too many or intrusive ads | 15 [C-ISS-USABILITY-complaint_count] | 2.666667 [C-ISS-USABILITY-mean_severity] | 40 [C-ISS-USABILITY-priority_score] |
| 2 | ISS-OTHER | general dissatisfaction with the app | 13 [C-ISS-OTHER-complaint_count] | 2.461538 [C-ISS-OTHER-mean_severity] | 32 [C-ISS-OTHER-priority_score] |
| 3 | ISS-BILLING | basic features locked behind Premium | 4 [C-ISS-BILLING-complaint_count] | 3.750000 [C-ISS-BILLING-mean_severity] | 15 [C-ISS-BILLING-priority_score] |
| 4 | ISS-PLAYBACK | mixed playback problems | 4 [C-ISS-PLAYBACK-complaint_count] | 3.500000 [C-ISS-PLAYBACK-mean_severity] | 14 [C-ISS-PLAYBACK-priority_score] |
| 5 | ISS-ACCESS | login or sign-in failures | 3 [C-ISS-ACCESS-complaint_count] | 3.666667 [C-ISS-ACCESS-mean_severity] | 11 [C-ISS-ACCESS-priority_score] |
| 6 | ISS-CATALOG | mixed catalog problems | 5 [C-ISS-CATALOG-complaint_count] | 2.000000 [C-ISS-CATALOG-mean_severity] | 10 [C-ISS-CATALOG-priority_score] |
| 7 | ISS-DOWNLOADS | offline mode not working | 2 [C-ISS-DOWNLOADS-complaint_count] | 3.000000 [C-ISS-DOWNLOADS-mean_severity] | 6 [C-ISS-DOWNLOADS-priority_score] |
| 8 | ISS-SUPPORT | unhelpful support | 1 [C-ISS-SUPPORT-complaint_count] | 2.000000 [C-ISS-SUPPORT-mean_severity] | 2 [C-ISS-SUPPORT-priority_score] |

All complaint and cancellation reviews: 47.

## The four candidate areas compared

| Area | Issues | Complaints | Share of all complaints | Priority score | Model probability |
|---|---|---|---|---|---|
| Usability | ISS-USABILITY | 15 | 31.9% | 40 | 1.00 |
| Access | ISS-ACCESS | 3 | 6.4% | 11 | 0.00 |
| Playback | ISS-PLAYBACK | 4 | 8.5% | 14 | 0.00 |
| Billing / support | ISS-BILLING, ISS-SUPPORT | 5 | 10.6% | 17 | 0.00 |

Billing / support combines ISS-BILLING and ISS-SUPPORT; its counts are sums of those two issue rows.

## Representative evidence

- Access · `32fb340f-4f9f-4551-8dae-755221e58d6a` (ISS-ACCESS, severity 4): "It not letting me into my account and there are to many ads"
- Access · `de0a9cdf-8974-48bc-802f-331228df4619` (ISS-ACCESS, severity 4): "Will not except my password"
- Access · `4ab2089a-ffa8-49e7-a8a3-aeb583a96796` (ISS-ACCESS, severity 3): "Iam a premium user. But this app if i using wifi not able to connect Internet. But if using mobile data it will work. Some songs quality also very poor comparing to the YouTube music."
- Usability · `89ea2c30-db8b-459d-8ab7-bbcb7f92c774` (ISS-USABILITY, severity 4): "What kind of stupidity is this? Na queue m lgte h gaane, na skip kr skte h, na random chla skte h, kya bkchodi h ye??? Jaruri h premium lena? Nhi lena bhai thodi to sharam kro saare paise tumhi kma lo"
- Usability · `035213ba-b1b9-411c-b028-70296e5f0e73` (ISS-USABILITY, severity 3): "I m using this app from 5 to 6 year but now m uninstald this app cz his premium adds are everywhere now ."
- Usability · `45c561b9-cc47-4d80-95d3-f0d20bc84af3` (ISS-USABILITY, severity 3): "The update made the app useless .... Uninstall krdia ye app ab bekar hai ... Wynk hi theek h"
- Playback · `55cc3abf-c295-4591-8c3a-78085cfdefaa` (ISS-PLAYBACK, severity 4): "The latest update has caused my app to crash I cant open the app please fix."
- Playback · `66a29b3c-c14d-440e-b722-b23e0c99ae82` (ISS-PLAYBACK, severity 4): "App is stuck on loading/logo screen"
- Playback · `46ff0c74-5e86-4e5b-b4cd-36201aab0f9e` (ISS-PLAYBACK, severity 3): "I am unable to use my Google assistant on the app.it says playing your Spotify playlist but do not play the songs"
- Billing / support · `a78d831a-69f4-428a-9235-cfdd9775c509` (ISS-BILLING, severity 4): "You can't even listen to music you want it just shuffles it, like what the hell? This app is killing it self and forcing you to pay premium for basic things like just listening to music."
- Billing / support · `ad730d1a-829a-4dc4-9561-7e1cd07e2c30` (ISS-BILLING, severity 4): "Why it requires premium just to play next music / to choose music ?? And why the specific part of song cannot be played ?"
- Billing / support · `d146397f-4a94-4980-be00-ae9212eca3a7` (ISS-BILLING, severity 4): "This was fine till the last update, now you can't even pick a certain song without Spotify premium, and now you can only skip 6 songs, like please just let the songs fit my mood!"

## Limitations

- Reviews are self-selected Google Play reviews from May 2022 to November 2023; they are not a sample of all users. Counts measure complaint volume in reviews, not prevalence among customers.
- Cancellation language is expressed intent, not observed churn. No revenue, plan tier or retention effect is calculated or implied.
- Labels come from an automated classifier (Jev). See the golden-set evaluation and verifier report for measured agreement and known errors.
- Coverage: 100 completed classifications and 0 quarantined records in this run.
- Topics are coarse issues (one per topic); sub-problems within an issue are named from a 25-quote sample and are indicative only.
