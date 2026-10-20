# Decision memo: where the next quarter of Spotify product effort should go

**Recommendation: Usability.** The memo model (Jev, role `memo`) chose this area from the saved aggregates and evidence pack with probability 1.00.

This agrees with the baseline ranking: Usability has the highest combined priority score of the four candidate areas.

## Supporting numbers (baseline ranking)

Priority score = complaint count × mean severity = severity sum. Bracketed IDs are rows in `claims.csv`.

| Rank | Issue | Dominant problem (group role) | Complaints | Mean severity | Priority score |
|---|---|---|---|---|---|
| 1 | ISS-OTHER | mixed other complaints | 1,458 [C-ISS-OTHER-complaint_count] | 2.471193 [C-ISS-OTHER-mean_severity] | 3,603 [C-ISS-OTHER-priority_score] |
| 2 | ISS-USABILITY | too many or intrusive ads | 1,222 [C-ISS-USABILITY-complaint_count] | 2.606383 [C-ISS-USABILITY-mean_severity] | 3,185 [C-ISS-USABILITY-priority_score] |
| 3 | ISS-BILLING | basic features locked behind Premium | 678 [C-ISS-BILLING-complaint_count] | 3.116519 [C-ISS-BILLING-mean_severity] | 2,113 [C-ISS-BILLING-priority_score] |
| 4 | ISS-PLAYBACK | songs stop, pause or skip | 526 [C-ISS-PLAYBACK-complaint_count] | 3.469582 [C-ISS-PLAYBACK-mean_severity] | 1,825 [C-ISS-PLAYBACK-priority_score] |
| 5 | ISS-ACCESS | login or sign-in failures | 162 [C-ISS-ACCESS-complaint_count] | 3.858025 [C-ISS-ACCESS-mean_severity] | 625 [C-ISS-ACCESS-priority_score] |
| 6 | ISS-CATALOG | songs or artists missing or removed | 194 [C-ISS-CATALOG-complaint_count] | 2.742268 [C-ISS-CATALOG-mean_severity] | 532 [C-ISS-CATALOG-priority_score] |
| 7 | ISS-DOWNLOADS | mixed download problems | 88 [C-ISS-DOWNLOADS-complaint_count] | 3.329545 [C-ISS-DOWNLOADS-mean_severity] | 293 [C-ISS-DOWNLOADS-priority_score] |
| 8 | ISS-SUPPORT | unhelpful support | 8 [C-ISS-SUPPORT-complaint_count] | 3.750000 [C-ISS-SUPPORT-mean_severity] | 30 [C-ISS-SUPPORT-priority_score] |

All complaint and cancellation reviews: 4,336.

## The four candidate areas compared

| Area | Issues | Complaints | Share of all complaints | Priority score | Model probability |
|---|---|---|---|---|---|
| Usability | ISS-USABILITY | 1,222 | 28.2% | 3,185 | 1.00 |
| Access | ISS-ACCESS | 162 | 3.7% | 625 | 0.00 |
| Playback | ISS-PLAYBACK | 526 | 12.1% | 1,825 | 0.00 |
| Billing / support | ISS-BILLING, ISS-SUPPORT | 686 | 15.8% | 2,143 | 0.00 |

Billing / support combines ISS-BILLING and ISS-SUPPORT; its counts are sums of those two issue rows.

## Representative evidence

- Access · `305c3fe1-109c-4f52-b7c4-5b95bb526035` (ISS-ACCESS, severity 5): "Why am I paying for this? Unable to login, can not reach tech support. Looks like the account was hacked."
- Access · `45d07c5b-1110-422a-8c4d-7f128042697c` (ISS-ACCESS, severity 5): "My account was hacked and your webchat, Facebook and Twitter team are not helping me. Our email team are not responding to me. I pay for family account and I cannot use it. Great service until it goes"
- Access · `55123d02-711d-4e41-b644-06e2c3c4db18` (ISS-ACCESS, severity 5): "Whenever I close the app it always logs me out and it did it this time and I had 1300 liked songs and lost all of them"
- Usability · `035213ba-b1b9-411c-b028-70296e5f0e73` (ISS-USABILITY, severity 5): "I m using this app from 5 to 6 year but now m uninstald this app cz his premium adds are everywhere now ."
- Usability · `08d3a5a9-1ec1-4b10-a5c8-393da33843e1` (ISS-USABILITY, severity 5): "For free subscription I find this to be a cancerous and even dangerous app while driving."
- Usability · `117770a7-cec9-4bc3-8a9f-a5d6f3544b5d` (ISS-USABILITY, severity 5): "This app is not good it trase our history and their are many ads in it and it is very difficult to use."
- Playback · `00168741-ef81-4267-9cb9-b82ad5b43a8c` (ISS-PLAYBACK, severity 5): "You took away the ability to watch video podcasts on my TV. This is literally the reason I have a paid subscription."
- Playback · `03102040-7e33-4643-91a7-65ec9ed383f9` (ISS-PLAYBACK, severity 5): "Would give a ZERO star if could."
- Playback · `0bf68fb6-2ebc-4035-a0ce-1e306b44f0e9` (ISS-PLAYBACK, severity 5): "It abruptly stops and can't play songs anymore. Also, i tried the mini premium paid for it 2x yet i wasn't able to have the said 1 day subscription. Didn't went through the hassle of figuring out the "
- Billing / support · `01bae9e0-2ad4-4ce4-98ee-aaac1fa9235a` (ISS-BILLING, severity 5): "Yo estoy pagando el Spotify premium, para que me cuenten el stream que hago y ahorita le quitan eso, APRENDAN A MÁS QUE SEA DISIMULAR PORQUE LO QUE HICIERON ES UN ROBO AL OJO"
- Billing / support · `065e5b47-02ab-4524-a309-068d8c51f3f1` (ISS-BILLING, severity 5): "Why am i getting ads on podcasts on my premium account? What is the point of paying a premium!!"
- Billing / support · `16f22d8d-1583-44c1-ab8c-17485612e9ee` (ISS-BILLING, severity 5): "Worst app ever this app is charging me for playback and"

## Limitations

- Reviews are self-selected Google Play reviews from May 2022 to November 2023; they are not a sample of all users. Counts measure complaint volume in reviews, not prevalence among customers.
- Cancellation language is expressed intent, not observed churn. No revenue, plan tier or retention effect is calculated or implied.
- Labels come from an automated classifier (Jev). See the golden-set evaluation and verifier report for measured agreement and known errors.
- Coverage: 10,000 completed classifications and 0 quarantined records in this run.
- Topics are coarse issues (one per topic); sub-problems within an issue are named from a 25-quote sample and are indicative only.
