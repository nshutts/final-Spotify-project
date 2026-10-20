# Decision memo: where the next quarter of Spotify product effort should go

**Recommendation: Usability.** The memo model (Jev, role `memo`) chose this area from the saved aggregates and evidence pack with probability 0.99.

This agrees with the baseline ranking: Usability has the highest combined priority score of the four candidate areas.

## Supporting numbers (baseline ranking)

Priority score = complaint count × mean severity = severity sum. Bracketed IDs are rows in `claims.csv`.

| Rank | Issue | Dominant problem (group role) | Complaints | Mean severity | Priority score |
|---|---|---|---|---|---|
| 1 | ISS-USABILITY | shuffle and skip limits | 64 [C-ISS-USABILITY-complaint_count] | 2.562500 [C-ISS-USABILITY-mean_severity] | 164 [C-ISS-USABILITY-priority_score] |
| 2 | ISS-OTHER | dislike of a recent update | 66 [C-ISS-OTHER-complaint_count] | 2.424242 [C-ISS-OTHER-mean_severity] | 160 [C-ISS-OTHER-priority_score] |
| 3 | ISS-BILLING | basic features locked behind Premium | 38 [C-ISS-BILLING-complaint_count] | 3.052632 [C-ISS-BILLING-mean_severity] | 116 [C-ISS-BILLING-priority_score] |
| 4 | ISS-PLAYBACK | mixed playback problems | 29 [C-ISS-PLAYBACK-complaint_count] | 3.482759 [C-ISS-PLAYBACK-mean_severity] | 101 [C-ISS-PLAYBACK-priority_score] |
| 5 | ISS-ACCESS | login or sign-in failures | 14 [C-ISS-ACCESS-complaint_count] | 4.000000 [C-ISS-ACCESS-mean_severity] | 56 [C-ISS-ACCESS-priority_score] |
| 6 | ISS-CATALOG | songs or artists missing or removed | 13 [C-ISS-CATALOG-complaint_count] | 2.384615 [C-ISS-CATALOG-mean_severity] | 31 [C-ISS-CATALOG-priority_score] |
| 7 | ISS-DOWNLOADS | mixed download problems | 7 [C-ISS-DOWNLOADS-complaint_count] | 3.428571 [C-ISS-DOWNLOADS-mean_severity] | 24 [C-ISS-DOWNLOADS-priority_score] |
| 8 | ISS-SUPPORT | unhelpful support | 1 [C-ISS-SUPPORT-complaint_count] | 2.000000 [C-ISS-SUPPORT-mean_severity] | 2 [C-ISS-SUPPORT-priority_score] |

All complaint and cancellation reviews: 232.

## The four candidate areas compared

| Area | Issues | Complaints | Share of all complaints | Priority score | Model probability |
|---|---|---|---|---|---|
| Usability | ISS-USABILITY | 64 | 27.6% | 164 | 0.99 |
| Billing / support | ISS-BILLING, ISS-SUPPORT | 39 | 16.8% | 118 | 0.01 |
| Access | ISS-ACCESS | 14 | 6.0% | 56 | 0.00 |
| Playback | ISS-PLAYBACK | 29 | 12.5% | 101 | 0.00 |

Billing / support combines ISS-BILLING and ISS-SUPPORT; its counts are sums of those two issue rows.

## Representative evidence

- Access · `d87536c5-6fe0-4b38-b0b1-c47936e4a0d8` (ISS-ACCESS, severity 5): "Top algorithm, but again hacked ,can't even recover the playlists set by me last week ,cost over three hundred dollars,per week for nothing ,"
- Access · `0a7f2420-1b49-41fa-8cfc-0b2e178bea6b` (ISS-ACCESS, severity 4): "I was using the app normally with the phone in my pocket, and out of nowhere log me out, and now I'm not able to log in, it's appearing some kind of error all the time, and the up is up to date, and a"
- Access · `12efd15d-4d4f-4a71-8e71-69d03b6f983a` (ISS-ACCESS, severity 4): "I can't login to the app, it keep saying that there's no internet connection, whereas everything else on my phone is connected to the internet."
- Usability · `caa9bb7e-814c-4895-b872-10637419b9ba` (ISS-USABILITY, severity 5): "Can't switch between video and audio only podcasts. Too much email spam. I pay for premium, so just take my money and leave me alone. I don't want a Car Thing, merch, or emails about what I listened t"
- Usability · `2313bd8e-43bd-4777-bff9-3ae753288f0e` (ISS-USABILITY, severity 4): "It is absolutely useless after the latest update. There's nothing I can do without the "try premium" option popping up every damn time."
- Usability · `45c561b9-cc47-4d80-95d3-f0d20bc84af3` (ISS-USABILITY, severity 4): "The update made the app useless .... Uninstall krdia ye app ab bekar hai ... Wynk hi theek h"
- Playback · `a7b7539a-c8d3-4f4e-9edd-d46cd1b1fd12` (ISS-PLAYBACK, severity 5): "The very second I signed up for premium it stopped letting me play anything.. lol . Fastest cancelation of a service I've done, ever. Bye bye Spotify. Hello old friend, Bittorrent"
- Playback · `065c418e-7f18-42a3-b241-fe693b7a2b0c` (ISS-PLAYBACK, severity 4): "Black screen of death. Having to Uninstaller and reinstall after closing and opening app 5x to see if it would work."
- Playback · `06d4c78d-73b4-4b54-9ef3-3d5a0d18cb96` (ISS-PLAYBACK, severity 4): "It was working fine and all and would've gotten a 5 star if it hadn't been for this glitch I've started to experience just this December."
- Billing / support · `58511d69-67c2-4432-84d8-f3c556592f2b` (ISS-BILLING, severity 5): "I am not like now they are so much charges to listen music or replay again the music there is a charger so that's why I don't like it this app now 😕"
- Billing / support · `86adc9b6-be58-400c-9a08-aa082ff0535c` (ISS-BILLING, severity 5): "Very bad experience ever faced by any app. They are literally forcing us to purchase Spotify premium."
- Billing / support · `9db060c5-2ff5-493a-8a19-01a3da91ff1d` (ISS-BILLING, severity 5): "The made everything paid at this point they will take money to play the song almost all features are gone limited songs of your choice"

## Limitations

- Reviews are self-selected Google Play reviews from May 2022 to November 2023; they are not a sample of all users. Counts measure complaint volume in reviews, not prevalence among customers.
- Cancellation language is expressed intent, not observed churn. No revenue, plan tier or retention effect is calculated or implied.
- Labels come from an automated classifier (Jev). See the golden-set evaluation and verifier report for measured agreement and known errors.
- Coverage: 500 completed classifications and 0 quarantined records in this run.
- Topics are coarse issues (one per topic); sub-problems within an issue are named from a 25-quote sample and are indicative only.
