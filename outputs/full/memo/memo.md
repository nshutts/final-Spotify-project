# Decision memo: where the next quarter of Spotify product effort should go

**Recommendation: Usability.** The memo model (Jev, role `memo`) chose this area from the saved aggregates and evidence pack with probability 1.00.

This agrees with the baseline ranking: Usability has the highest combined priority score of the four candidate areas.

## Supporting numbers (baseline ranking)

Priority score = complaint count × mean severity = severity sum. Bracketed IDs are rows in `claims.csv`.

| Rank | Issue | Dominant problem (group role) | Complaints | Mean severity | Priority score |
|---|---|---|---|---|---|
| 1 | ISS-OTHER | general dissatisfaction with the app | 101,800 [C-ISS-OTHER-complaint_count] | 2.521621 [C-ISS-OTHER-mean_severity] | 256,701 [C-ISS-OTHER-priority_score] |
| 2 | ISS-USABILITY | too many or intrusive ads | 77,428 [C-ISS-USABILITY-complaint_count] | 2.643307 [C-ISS-USABILITY-mean_severity] | 204,666 [C-ISS-USABILITY-priority_score] |
| 3 | ISS-BILLING | mixed billing problems | 43,845 [C-ISS-BILLING-complaint_count] | 3.334861 [C-ISS-BILLING-mean_severity] | 146,217 [C-ISS-BILLING-priority_score] |
| 4 | ISS-PLAYBACK | mixed playback problems | 34,136 [C-ISS-PLAYBACK-complaint_count] | 3.441411 [C-ISS-PLAYBACK-mean_severity] | 117,476 [C-ISS-PLAYBACK-priority_score] |
| 5 | ISS-ACCESS | login or sign-in failures | 10,761 [C-ISS-ACCESS-complaint_count] | 3.931977 [C-ISS-ACCESS-mean_severity] | 42,312 [C-ISS-ACCESS-priority_score] |
| 6 | ISS-CATALOG | songs or artists missing or removed | 13,584 [C-ISS-CATALOG-complaint_count] | 2.707155 [C-ISS-CATALOG-mean_severity] | 36,774 [C-ISS-CATALOG-priority_score] |
| 7 | ISS-DOWNLOADS | offline mode not working | 6,343 [C-ISS-DOWNLOADS-complaint_count] | 3.399811 [C-ISS-DOWNLOADS-mean_severity] | 21,565 [C-ISS-DOWNLOADS-priority_score] |
| 8 | ISS-SUPPORT | unhelpful support | 819 [C-ISS-SUPPORT-complaint_count] | 3.256410 [C-ISS-SUPPORT-mean_severity] | 2,667 [C-ISS-SUPPORT-priority_score] |

All complaint and cancellation reviews: 288,716.

## The four candidate areas compared

| Area | Issues | Complaints | Share of all complaints | Priority score | Model probability |
|---|---|---|---|---|---|
| Usability | ISS-USABILITY | 77,428 | 26.8% | 204,666 | 1.00 |
| Access | ISS-ACCESS | 10,761 | 3.7% | 42,312 | 0.00 |
| Playback | ISS-PLAYBACK | 34,136 | 11.8% | 117,476 | 0.00 |
| Billing / support | ISS-BILLING, ISS-SUPPORT | 44,664 | 15.5% | 148,884 | 0.00 |

Billing / support combines ISS-BILLING and ISS-SUPPORT; its counts are sums of those two issue rows.

## Representative evidence

- Access · `0096d282-f6ee-4275-b41a-c009d19af1d2` (ISS-ACCESS, severity 5): "I'm not able to login to the app. Have tried logging in with email, with my credentials, using my phone number but to no avail. And this is after I've purchased the premium membership. I'm so disappoi"
- Access · `00991520-102d-4cbd-bacf-5a85dfd9a749` (ISS-ACCESS, severity 5): "I pay for a premium family membership and I find this app poor."
- Access · `0206e8af-1a8a-46b6-b187-123dc0a2230e` (ISS-ACCESS, severity 5): "You're better off paying for youtube music."
- Usability · `002aac37-eaec-476e-a7d7-5aff5738b2fa` (ISS-USABILITY, severity 5): "It's a paid subscription why am i still getting ads. Why is the most popular music streaming app so terrible. It constantly tells me when people on the same network are listening to something, Which I"
- Usability · `002d1569-94f2-45c2-823c-2c6cc9f6e996` (ISS-USABILITY, severity 5): "Ads on Premium Disgusting! They're obviously not part of the podcast I'm listening to because I've listened to it on yt, absolutely filthy work Spotify. I moved from Pandora to Spotify a few years ago"
- Usability · `003f607a-27d5-4cb6-aa8e-34974a530460` (ISS-USABILITY, severity 5): "Been premium member for years, I'm giving a 1 star revieuw today for ads during my podcast."
- Playback · `00dcd77f-d92b-4387-9aca-d12b586ed786` (ISS-PLAYBACK, severity 5): "(this part is updated) The all is terrible."
- Playback · `00e7dc8d-5e2a-4217-85b9-fe8e3b333e72` (ISS-PLAYBACK, severity 5): "Was good but now when I put on shuffle songs it plays the same songs in the exact order. I canceled my premium subscription after having it since thus service started due to all of the racism from pod"
- Playback · `00ec426e-1591-40ea-b0ca-6c4c516b893e` (ISS-PLAYBACK, severity 5): "Not working on any of my devices! What have you done this time? Pointless paying you for subscription that's not working!"
- Billing / support · `0001bbc9-830d-4913-9594-c50d0962249e` (ISS-BILLING, severity 5): "I hate this app because pay for repeat song and ad"
- Billing / support · `000c2b9a-d116-45dc-b8a8-7b3818d6e834` (ISS-BILLING, severity 5): "My favourite application for music hands down However, they charged me double ( took me off student plan) without notifying me, plus I'm still a studend"
- Billing / support · `0020b261-f01e-4f49-99a8-4f091229d667` (ISS-BILLING, severity 5): "I hate this app now, new update is just so senseless, you're now forcing people to buy spotify premium, such a lame thing to do, I really wish you go down with this update 👎🏻"

## Limitations

- Reviews are self-selected Google Play reviews from May 2022 to November 2023; they are not a sample of all users. Counts measure complaint volume in reviews, not prevalence among customers.
- Cancellation language is expressed intent, not observed churn. No revenue, plan tier or retention effect is calculated or implied.
- Labels come from an automated classifier (Jev). See the golden-set evaluation and verifier report for measured agreement and known errors.
- Coverage: 660,609 completed classifications and 0 quarantined records in this run.
- Topics are coarse issues (one per topic); sub-problems within an issue are named from a 25-quote sample and are indicative only.
