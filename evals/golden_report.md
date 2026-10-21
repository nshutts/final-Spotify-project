# Golden-set evaluation (50 hand-labelled reviews)

Rules were declared before this evaluation ran (docs/EVALUATION_RULES.md). Golden labels were never model inputs.

- Predictions found: 50/50 (missing or quarantined count as wrong on every field)
- Ambiguous cases (marked by the labeller): 11
- Topic agreement: 42/50 (84%)
- Intent agreement: 47/50 (94%)
- Severity exact agreement: 39/50 (78%); MAE 0.24
- Sentiment MAE 0.1368; within ±0.5: 48/50
- Evidence quote exact substring (code): 50/50.
- Evidence quote supports the predicted topic and intent (judged per review): 42/50; reasons for each 'no' in golden_cases.csv.
- Entities: 27 predicted, 0 unsupported additions; 5 of 27 human entities missed
- needs_review: both yes 1, model yes/human no 3, model no/human yes 10, both no 36; precision 0.25, recall 0.0909; topic/intent errors flagged for review: 2/11

## Topic confusion (rows = human label, columns = model)

| human \ model | access | usability | playback | downloads | catalog | billing | support | other |
|---|---|---|---|---|---|---|---|---|
| usability |  | 7 |  |  |  | 1 |  |  |
| playback |  | 1 | 4 |  |  |  |  |  |
| downloads |  |  |  | 1 |  |  |  |  |
| catalog |  | 1 |  |  | 3 |  |  | 2 |
| billing |  | 2 |  |  |  | 1 |  |  |
| other |  |  |  |  |  | 1 |  | 26 |

## Disagreements

| review_id | text | field | human | model | ambiguous |
|---|---|---|---|---|---|
| 292ce26a | Staff must be full of mentally ill kool-aid heads. Banning conservativ | severity | 2 | 3 | yes |
| 1fc8b08f | Duo Premium .... No ads at all! | topic | usability | billing | no |
| ac6cd66d | Lhat ng song nasa spotify | intent | praise | request | yes |
| 46842184 | asem, lirik nya kdang gaada kek mana?? | severity | 3 | 2 | yes |
| 657f1b77 | Hate This application 👎 | severity | 2 | 3 | no |
| 5de7f95b | We are boycotting Swedish app in our protest against Sweden for their  | intent | unclear | complaint | yes |
| 5de7f95b | We are boycotting Swedish app in our protest against Sweden for their  | severity | 1 | 2 | yes |
| de48c99b | I LOVE that I was able to put in only a few songs I like and Spotify g | topic | catalog | other | no |
| 372d4e67 | Please ye ads ko thoda kumm Karo harr ek song ke baad ad 🙏🙄 | intent | complaint | request | no |
| 3ddb3f4e | Deleting this App. The new update suck, we can't choose our fvrt songs | topic | billing | usability | no |
| 3ddb3f4e | Deleting this App. The new update suck, we can't choose our fvrt songs | severity | 3 | 4 | no |
| 16d640e9 | It's my best music app but now it's not...everything basic features is | severity | 3 | 4 | yes |
| 46c0b49f | Are you out of your mind? This is dangerous! Listening to music in a n | severity | 2 | 3 | yes |
| 283b5843 | Beth, we all got to give me a free dollar to go with 3 months, bro I c | topic | other | billing | no |
| 8c0546b0 | 1-Lyrics not getting loaded, 2-can't go back to or start song where to | topic | catalog | usability | no |
| b58dd6f0 | The only thing Spotify lacks is the ability to organize saved  albums/ | severity | 1 | 2 | no |
| dceb14e7 | I gave one star because I can't give any less than that. the new updat | topic | playback | usability | yes |
| 5fba12ea | I find Spotify very good, it finds and play whatever music you want an | topic | catalog | other | no |
| ac4e860a | paying for subscribing but unable to play in offline mode really? | severity | 3 | 5 | no |
| d2f3874f | Too expensive and the free version is pretty much unusable with consta | topic | billing | usability | yes |
| d2f3874f | Too expensive and the free version is pretty much unusable with consta | severity | 2 | 3 | yes |
| 99b93e31 | This update very bad for everyone.old Spotify. we all want. | severity | 2 | 3 | no |
