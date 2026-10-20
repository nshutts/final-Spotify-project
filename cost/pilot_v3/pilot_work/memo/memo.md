# Decision memo: where the next quarter of Spotify product effort should go

**Recommendation: Usability.** The memo model (Jev, role `memo`) chose this area from the saved aggregates and evidence pack with probability 1.00.

This agrees with the baseline ranking: Usability has the highest combined priority score of the four candidate areas.

## Supporting numbers (baseline ranking)

Priority score = complaint count × mean severity = severity sum. Bracketed IDs are rows in `claims.csv`.

| Rank | Issue | Dominant problem (group role) | Complaints | Mean severity | Priority score |
|---|---|---|---|---|---|
| 1 | ISS-USABILITY | too many or intrusive ads | 16 [C-ISS-USABILITY-complaint_count] | 2.687500 [C-ISS-USABILITY-mean_severity] | 43 [C-ISS-USABILITY-priority_score] |
| 2 | ISS-OTHER | general dissatisfaction with the app | 13 [C-ISS-OTHER-complaint_count] | 1.923077 [C-ISS-OTHER-mean_severity] | 25 [C-ISS-OTHER-priority_score] |
| 3 | ISS-BILLING | basic features locked behind Premium | 7 [C-ISS-BILLING-complaint_count] | 2.857143 [C-ISS-BILLING-mean_severity] | 20 [C-ISS-BILLING-priority_score] |
| 4 | ISS-PLAYBACK | mixed playback problems | 5 [C-ISS-PLAYBACK-complaint_count] | 3.800000 [C-ISS-PLAYBACK-mean_severity] | 19 [C-ISS-PLAYBACK-priority_score] |
| 5 | ISS-CATALOG | mixed catalog problems | 6 [C-ISS-CATALOG-complaint_count] | 2.500000 [C-ISS-CATALOG-mean_severity] | 15 [C-ISS-CATALOG-priority_score] |
| 6 | ISS-ACCESS | login or sign-in failures | 2 [C-ISS-ACCESS-complaint_count] | 4.000000 [C-ISS-ACCESS-mean_severity] | 8 [C-ISS-ACCESS-priority_score] |
| 7 | ISS-DOWNLOADS | offline mode not working | 2 [C-ISS-DOWNLOADS-complaint_count] | 4.000000 [C-ISS-DOWNLOADS-mean_severity] | 8 [C-ISS-DOWNLOADS-priority_score] |

All complaint and cancellation reviews: 51.

## The four candidate areas compared

| Area | Issues | Complaints | Share of all complaints | Priority score | Model probability |
|---|---|---|---|---|---|
| Usability | ISS-USABILITY | 16 | 31.4% | 43 | 1.00 |
| Access | ISS-ACCESS | 2 | 3.9% | 8 | 0.00 |
| Playback | ISS-PLAYBACK | 5 | 9.8% | 19 | 0.00 |
| Billing / support | ISS-BILLING | 7 | 13.7% | 20 | 0.00 |

Billing / support combines ISS-BILLING and ISS-SUPPORT; its counts are sums of those two issue rows.

## Representative evidence

- Access · `32fb340f-4f9f-4551-8dae-755221e58d6a` (ISS-ACCESS, severity 4): "It not letting me into my account and there are to many ads"
- Access · `de0a9cdf-8974-48bc-802f-331228df4619` (ISS-ACCESS, severity 4): "Will not except my password"
- Usability · `45c561b9-cc47-4d80-95d3-f0d20bc84af3` (ISS-USABILITY, severity 4): "The update made the app useless .... Uninstall krdia ye app ab bekar hai ... Wynk hi theek h"
- Usability · `5c9c17d3-9d6a-4fa1-a2a4-ae98eefbbd25` (ISS-USABILITY, severity 3): "Your new features are really bad thing that I found because it plays any song of the Playlist randomly it really really disappointing for and listeners who don't need disturbance in their song pattern"
- Usability · `7084ced1-0428-4093-9328-442f74719b4f` (ISS-USABILITY, severity 3): "I am using Spotify from past two years From last update they removed basic features of music player"
- Playback · `46ff0c74-5e86-4e5b-b4cd-36201aab0f9e` (ISS-PLAYBACK, severity 4): "I am unable to use my Google assistant on the app.it says playing your Spotify playlist but do not play the songs"
- Playback · `4ab2089a-ffa8-49e7-a8a3-aeb583a96796` (ISS-PLAYBACK, severity 4): "Iam a premium user. But this app if i using wifi not able to connect Internet. But if using mobile data it will work. Some songs quality also very poor comparing to the YouTube music."
- Playback · `55cc3abf-c295-4591-8c3a-78085cfdefaa` (ISS-PLAYBACK, severity 4): "The latest update has caused my app to crash I cant open the app please fix."
- Billing / support · `21915fcd-9a35-48ba-b277-6296c4154603` (ISS-BILLING, severity 3): "This app the new update has made everthing premium and so usless i thought this app is good but no."
- Billing / support · `88439ec2-7c49-4c57-bedb-c5e098692aff` (ISS-BILLING, severity 3): "I would request to remove all the new features .what's the point if we dont get to go back to the same song or skip songs..or choose .its not fair ..to restrict all the features jst so people would pu"
- Billing / support · `a3605554-5c3a-441d-836e-e9fdea83eb2e` (ISS-BILLING, severity 3): "Recent update really sucks. The ability to skip a song or go to previous song has been removed from non subscribed users."

## Limitations

- Reviews are self-selected Google Play reviews from May 2022 to November 2023; they are not a sample of all users. Counts measure complaint volume in reviews, not prevalence among customers.
- Cancellation language is expressed intent, not observed churn. No revenue, plan tier or retention effect is calculated or implied.
- Labels come from an automated classifier (Jev). See the golden-set evaluation and verifier report for measured agreement and known errors.
- Coverage: 100 completed classifications and 0 quarantined records in this run.
- Topics are coarse issues (one per topic); sub-problems within an issue are named from a 25-quote sample and are indicative only.
