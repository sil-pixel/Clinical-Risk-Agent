# DCMFNet Questionnaire — Provisionally Approved MVP Copy

**Status:** **Provisionally approved by the product owner on 2026-09-15 for portfolio-MVP implementation.** The wording and listed response encodings may be implemented as written. This remains a research-only questionnaire and is not a validated clinical or diagnostic assessment. Any mismatch discovered during training-codebook verification must be brought back for review before public inference.

This document defines the provisionally approved user-facing English questions for the manually collected DCMFNet features supplied by the model owner. It preserves the feature keys so each item can be verified against the training-data dictionary during implementation.

## Important contract decisions required before implementation

1. The supplied Python ranges create **19 ADHD fields** (`range(1, 20)`) and **17 ASD fields** (`range(1, 18)`), not 20 and 18. The model artifacts also contain 19 `ADHD9` and 17 `ASD9` fields. No twentieth ADHD question or eighteenth ASD question may be added to the inference payload without retraining or revising the model schema.
2. The names recovered for the 19 ADHD and 17 ASD fields align with the domains and item counts of the **Autism–Tics, ADHD and other Comorbidities inventory (A-TAC)**. A-TAC is a parent/collateral interview, asks about childhood problems in a whole-life frame, and scores each item as `No = 0`, `Yes, to some extent = 0.5`, or `Yes = 1`. The five-point frequency scale requested here is therefore a proposed UI scale, **not a validated A-TAC scoring scheme**.
3. These questions are written as adult retrospective self-report because this MVP excludes minors. That use differs from the validated parent interview. It must not be described as a validated ADHD or ASD screen, diagnostic questionnaire, or clinical assessment.
4. Education, parental country of birth, sex, and bullying have the product-approved categorical encodings documented below. Their compatibility with the original training-data codes must still be verified before inference.
5. Product-approved numeric encodings are now documented for sex, education, parental country of birth, and bullying frequency. The data owner must still verify every encoding against the original training codebook and provide valid ranges, missing-value rules, item order, and transformations. Until that verification is complete, the backend must fail closed rather than send questionnaire values to DCMFNet.
6. The supplied feature groups contain **84 manual fields**. Adding the artifact's `SEX` field produces **85 manual fields**. The remaining sixteen PRS fields and four batch-by-PC fields are supplied by the approved versioned generic profile, producing the complete 105-input matrix.

### Proposed common frequency scale

Use this scale only where an item asks how often something occurred:

- **1 — Never**
- **2 — Rarely**
- **3 — Sometimes**
- **4 — Often**
- **5 — Very often**

The interface should include **“I do not remember”** as a non-scored state during drafting. Because every approved manual model field will ultimately be required, product and ML owners must decide whether this response makes the assessment ineligible or maps to a code supported by the original data dictionary. It must not be imputed in the browser.

## A. Substance use at age 15 (`SUD15`)

**Section prompt:** Thinking specifically about when you were 15 years old, how often did you do each of the following?

Use the proposed common frequency scale for A1–A6.

1. **A1 — `SUD15_Cigarettes15`:** At age 15, how often did you smoke cigarettes?
2. **A2 — `SUD15_Snuff15`:** At age 15, how often did you use snuff or another form of smokeless tobacco?
3. **A3 — `SUD15_Alcohol15`:** At age 15, how often did you drink alcohol?
4. **A4 — `SUD15_Cannabis15`:** At age 15, how often did you use cannabis or marijuana?
5. **A5 — `SUD15_OtherDrugs15`:** At age 15, how often did you use recreational or non-prescribed drugs other than cannabis or painkillers/opioids?
6. **A6 — `SUD15_Painkillers_opioids15`:** At age 15, how often did you use painkillers or opioids?

**Review note:** Confirm whether A6 means any use or only non-medical use, and confirm exactly which substances belong in A5. The UI must not add examples that alter the source category.

## B. Experiences and wellbeing (`SCZ15`)

These neutral questions collect the named historical features. They do not diagnose or label an experience.

Use the proposed common frequency scale for B1–B23. Unless stated otherwise, the time frame is **at age 15**.

1. **B1 — `SCZ15_PROD_seen_hallucinations9`:** At around age 9, how often did you see things that other people could not see?
2. **B2 — `SCZ15_Spied15`:** At age 15, how often did you feel that someone was spying on you?
3. **B3 — `SCZ15_Others_Read_thoughts15`:** At age 15, how often did you feel that other people could read your thoughts?
4. **B4 — `SCZ15_Special_messages15`:** At age 15, how often did you feel that messages from television, radio, the internet, signs, or other sources were meant especially for you?
5. **B5 — `SCZ15_Special_powers15`:** At age 15, how often did you feel that you had special powers that other people did not have?
6. **B6 — `SCZ15_Under_control_special_power15`:** At age 15, how often did you feel that an outside or special power was controlling your thoughts or actions?
7. **B7 — `SCZ15_Read_others_minds15`:** At age 15, how often did you feel that you could read other people's minds?
8. **B8 — `SCZ15_Seen_hallucinations15`:** At age 15, how often did you see things that other people could not see?
9. **B9 — `SCZ15_Extreme_excitement15`:** At age 15, how often did you experience unusually extreme excitement?
10. **B10 — `SCZ15_Irritable15`:** At age 15, how often did you feel unusually irritable?
11. **B11 — `SCZ15_Unrealistic_abilities15`:** At age 15, how often did you feel that your abilities were far greater than they realistically were?
12. **B12 — `SCZ15_Not_tired15`:** At age 15, how often did you need much less sleep than usual without feeling tired?
13. **B13 — `SCZ15_Too_much_energy15`:** At age 15, how often did you have an unusually high amount of energy?
14. **B14 — `SCZ15_Racing_thoughts15`:** At age 15, how often did your thoughts seem to race very quickly?
15. **B15 — `SCZ15_Talking_fast15`:** At age 15, how often did you speak much faster than usual?
16. **B16 — `SCZ15_Sexual_inappropriate15`:** At age 15, how often did you behave sexually in a way that was inappropriate for the situation?
17. **B17 — `SCZ15_Rage_attacks15`:** At age 15, how often did you experience sudden attacks of intense anger or rage?
18. **B18 — `SCZ15_Hear_voices15`:** At age 15, how often did you hear voices that other people could not hear?
19. **B19 — `SCZ15_headaches15`:** At age 15, how often did you have headaches?
20. **B20 — `SCZ15_worry15`:** At age 15, how often did you feel worried?
21. **B21 — `SCZ15_unhappy15`:** At age 15, how often did you feel unhappy?
22. **B22 — `SCZ15_lose_confidence15`:** At age 15, how often did you lose confidence in yourself?
23. **B23 — `SCZ15_easily_scared15`:** At age 15, how often were you easily scared?

**Review note:** The original reference period and anchors must be verified. “Other people could not see/hear” is neutral wording, but a clinician and lived-experience reviewer should approve the sensitive-item copy.

## C. Attention and activity around age 9 (`ADHD9`)

**Section prompt:** Thinking about yourself at around age 9, compared with other children of the same age, how often did each statement describe you?

Use the proposed common frequency scale for C1–C19.

1. **C1 — `ADHD9_var_1` (`fail_close_attention9`):** At around age 9, how often did you make careless mistakes or have difficulty paying close attention to details?
2. **C2 — `ADHD9_var_2` (`difficulty_with_attention9`):** At around age 9, how often did you have difficulty keeping your attention on tasks or activities?
3. **C3 — `ADHD9_var_3` (`not_listening9`):** At around age 9, how often did you seem not to listen when someone spoke directly to you?
4. **C4 — `ADHD9_var_4` (`difficulty_following_instructions9`):** At around age 9, how often did you have difficulty following instructions or completing tasks?
5. **C5 — `ADHD9_var_5` (`difficulty_organizing_tasks9`):** At around age 9, how often did you have difficulty organizing tasks and activities?
6. **C6 — `ADHD9_var_6` (`avoid_mental_effort_tasks9`):** At around age 9, how often did you avoid or dislike tasks that required sustained mental effort?
7. **C7 — `ADHD9_var_7` (`often_lose_things9`):** At around age 9, how often did you lose things needed for tasks or activities?
8. **C8 — `ADHD9_var_8` (`easily_distracted9`):** At around age 9, how often were you easily distracted by things around you?
9. **C9 — `ADHD9_var_9` (`often_forgetful9`):** At around age 9, how often were you forgetful in everyday activities?
10. **C10 — `ADHD9_var_10` (`difficulty_hold_still9`):** At around age 9, how often did you have difficulty sitting or keeping still when expected to do so?
11. **C11 — `ADHD9_var_11` (`often_move9`):** At around age 9, how often did you fidget or move your hands, feet, or body?
12. **C12 — `ADHD9_var_12` (`often_run9`):** At around age 9, how often did you run about or climb in situations where it was not expected?
13. **C13 — `ADHD9_var_13` (`difficulty_calm9`):** At around age 9, how often did you have difficulty playing or taking part in activities calmly or quietly?
14. **C14 — `ADHD9_var_14` (`often_motor9`):** At around age 9, how often were you constantly on the go, as if driven by a motor?
15. **C15 — `ADHD9_var_15` (`talk_excess9`):** At around age 9, how often did you talk excessively?
16. **C16 — `ADHD9_var_16` (`often_blurt_out9`):** At around age 9, how often did you answer before a question had been completed or blurt out answers?
17. **C17 — `ADHD9_var_17` (`difficulty_waiting9`):** At around age 9, how often did you have difficulty waiting for your turn?
18. **C18 — `ADHD9_var_18` (`often_interrupt9`):** At around age 9, how often did you interrupt or intrude on other people?
19. **C19 — `ADHD9_var_19` (`easily_bored9`):** At around age 9, how often did you become bored very easily?

**Instrument note:** The 19-field count matches the A-TAC ADHD domain (nine concentration/attention items and ten impulsiveness/activity items). These are plain-language draft statements tied to the recovered feature semantics, not a claim of verbatim or validated digital A-TAC administration.

## D. Communication, social interaction, and flexibility around age 9 (`ASD9`)

**Section prompt:** Thinking about yourself at around age 9, compared with other children of the same age, how often did each statement describe you?

Use the proposed common frequency scale for D1–D17.

1. **D1 — `ASD9_var_1` (`delay_language9`):** At around age 9, how often did delayed spoken-language development affect you?
2. **D2 — `ASD9_var_2` (`difficulty_converse9`):** At around age 9, how often did you have difficulty starting or maintaining a back-and-forth conversation?
3. **D3 — `ASD9_var_3` (`repeat_words9`):** At around age 9, how often did you repeat particular words or phrases?
4. **D4 — `ASD9_var_4` (`difficulty_pretend_play9`):** At around age 9, how often did you have difficulty with imaginative or pretend play?
5. **D5 — `ASD9_var_5` (`talk_too_high_low9`):** At around age 9, how often was your voice unusually high, low, loud, quiet, or otherwise different in tone?
6. **D6 — `ASD9_var_6` (`difficulty_on_track9`):** At around age 9, how often did you have difficulty staying on track during a conversation?
7. **D7 — `ASD9_var_7` (`difficulty_express9`):** At around age 9, how often did you have difficulty expressing your thoughts, feelings, or needs to other people?
8. **D8 — `ASD9_var_8` (`difficulty_socialize9`):** At around age 9, how often did you have difficulty socializing with other children?
9. **D9 — `ASD9_var_9` (`uninterested_sharing9`):** At around age 9, how often did you show little interest in sharing enjoyment, interests, or achievements with other people?
10. **D10 — `ASD9_var_10` (`own_terms9`):** At around age 9, how often did you want contact or activities with other people mainly on your own terms?
11. **D11 — `ASD9_var_11` (`difficulty_expect_behavior9`):** At around age 9, how often did you have difficulty understanding what other people expected you to do in social situations?
12. **D12 — `ASD9_var_12` (`easily_influenced9`):** At around age 9, how often were you easily influenced or persuaded by other people?
13. **D13 — `ASD9_var_13` (`absorbed_own9`):** At around age 9, how often did you become deeply absorbed in your own interests or activities?
14. **D14 — `ASD9_var_14` (`absorbed_problems9`):** At around age 9, how often did you become so absorbed in particular problems or topics that it was difficult to shift your attention?
15. **D15 — `ASD9_var_15` (`strange_movements9`):** At around age 9, how often did you make unusual or repetitive movements?
16. **D16 — `ASD9_var_16` (`absorbed_details9`):** At around age 9, how often did you focus strongly on details, sometimes more than on the overall situation?
17. **D17 — `ASD9_var_17` (`dislike_change9`):** At around age 9, how often did you become upset or uncomfortable when routines or plans changed?

**Instrument note:** The 17-field count matches the A-TAC ASD domain (six language, six social-interaction, and five flexibility items). The meanings of `difficulty_express9`, `easily_influenced9`, and `absorbed_problems9` especially require confirmation against the original study codebook.

## E. Bullying experiences at age 15 (`ACE15`)

Use this approved bullying-frequency scale for E1–E7:

- **1 — Never**
- **2 — Once a month**
- **3 — Once a week**
- **4 — More than once a week**
- **5 — More than once a day**

1. **E1 — `ACE15_other_bullying15`:** At age 15, how often did you experience a form of bullying not covered by the other questions in this section?
2. **E2 — `ACE15_bullied_often15`:** At age 15, how often were you bullied repeatedly?
3. **E3 — `ACE15_tease_bullying15`:** At age 15, how often were you teased, mocked, or called hurtful names?
4. **E4 — `ACE15_emotional_bullying15`:** At age 15, how often did you experience emotional bullying?
5. **E5 — `ACE15_rumours_bullying15`:** At age 15, how often did someone spread hurtful rumours about you?
6. **E6 — `ACE15_bullying_by_num15`:** At age 15, how often were you bullied by one or more people?
7. **E7 — `ACE15_bullying_time15`:** At age 15, how often did bullying continue or recur over time?

**Review note:** E1 needs the original preceding categories to make “other” meaningful. The approved answer labels measure occurrence frequency rather than a literal number of people or duration. The data owner must confirm that this interpretation matches `bullying_by_num15` and `bullying_time15`; otherwise these two fields require source-faithful controls before inference.

## F. Adverse experiences at age 18 (`ACE18`)

**Section prompt:** Thinking specifically about when you were 18 years old, how often did you experience each of the following?

Use the proposed common frequency scale for F1–F4.

1. **F1 — `ACE18_other_abuse18`:** At age 18, how often did you experience another form of abuse not covered by the other questions in this section?
2. **F2 — `ACE18_hate_crime18`:** At age 18, how often did you experience abuse, threats, or violence that you understood to be motivated by prejudice against a part of your identity?
3. **F3 — `ACE18_emotional_abuse18`:** At age 18, how often did you experience emotional abuse?
4. **F4 — `ACE18_witness_crime18`:** At age 18, how often did you witness a crime or serious violence?

**Review note:** The exact source definitions of “other abuse,” “hate crime,” and “witness crime” are required before these labels can be approved.

## G. Substance use at age 18 (`SUD18`)

**Section prompt:** Thinking specifically about when you were 18 years old, how often did you do each of the following?

Use the proposed common frequency scale for G1–G4.

1. **G1 — `SUD18_cigarettes18`:** At age 18, how often did you smoke cigarettes?
2. **G2 — `SUD18_snuff18`:** At age 18, how often did you use snuff or another form of smokeless tobacco?
3. **G3 — `SUD18_alcohol_often18`:** At age 18, how often did you drink alcohol?
4. **G4 — `SUD18_drugs_often18`:** At age 18, how often did you use recreational or non-prescribed drugs?

**Review note:** Confirm whether frequency refers to a typical week/month, the full year, or another reference period, and define which drugs G4 includes.

## H. Parental socioeconomic variables (`SES`)

These are not frequency questions. Education uses the numbered 1–5 categorical encoding below, not the common frequency scale.

Use this education encoding for H1 and H3:

- **1 — Primary**
- **2 — Secondary**
- **3 — High school**
- **4 — Bachelor's**
- **5 — Master's and above**

Use this country-of-birth encoding for H2 and H4:

- **1 — India**
- **0 — Elsewhere**

1. **H1 — `SES_education_father`:** What was the highest level of education completed by your father?
2. **H2 — `SES_birth_country_father`:** Was your father born in India or elsewhere?
3. **H3 — `SES_education_mother`:** What was the highest level of education completed by your mother?
4. **H4 — `SES_birth_country_mother`:** Was your mother born in India or elsewhere?

**Privacy and fairness review:** Country of birth is a sensitive population descriptor and must never be used to derive PRS, ethnicity, race, or genetic ancestry. Product, privacy, fairness, and ML owners must confirm that the approved binary encoding matches the trained model and is necessary and lawful in the India portfolio context. More inclusive parent/guardian wording may be preferable, but it cannot replace the trained construct without validation.

## I. Sex (`SEX`)

Use this approved binary encoding:

- **1 — Male**
- **2 — Female**

1. **I1 — `SEX`:** What is your sex?

**Review note:** This is the exact binary model input requested for the current artifact. The UI should state that these are the only values supported by this research model and must not infer the answer from gender identity, name, language, appearance, or any other response.

## J. Model inputs not entered by the user

- **Sixteen PRS fields:** not user-entered in the portfolio MVP; populated only by the disclosed `generic_genetic_profile_v1` artifact medians.
- **Four batch-by-PC interaction fields:** not user-entered; populated only by the same approved generic profile.

## Approval checklist

Product wording and response-option approval was granted on 2026-09-15. The remaining checks are implementation and release-verification tasks; findings that require changing the approved questionnaire must return to product review.

- [x] Product owner approved the questionnaire wording and listed response options for provisional MVP implementation.
- [x] Confirm 19 ADHD and 17 ASD fields for the current artifact.
- [ ] Provide the authoritative data dictionary and source questionnaire version for every feature.
- [ ] Confirm exact time frame for each age-tagged field.
- [ ] Confirm exact item order for `ADHD9_var_*` and `ASD9_var_*`.
- [ ] Decide whether retrospective adult self-report is acceptable; otherwise obtain a compatible validated adult instrument and retrain/revalidate the model.
- [ ] Approve response labels and source-faithful encodings; do not map the proposed 1–5 UI scale to model values by assumption.
- [ ] Verify that the approved bullying-frequency encoding matches the source meanings of `bullying_by_num15` and `bullying_time15`.
- [ ] Verify that the approved education and India/elsewhere encodings match the training-data codebook; define missing/unknown handling.
- [ ] Verify that the approved `SEX` values match the artifact's training encoding and document handling for users outside the model's supported binary categories.
- [ ] Complete clinical, lived-experience, accessibility, privacy, fairness, and legal review of sensitive wording.
- [ ] Validate the final electronic questionnaire and its scoring against the exact model training pipeline.

## Scientific provenance for the ADHD/ASD draft

- Larson T, et al. *The Autism–Tics, AD/HD and other Comorbidities inventory (A-TAC): further validation of a telephone interview for epidemiological research.* BMC Psychiatry. 2010;10:1. DOI: [10.1186/1471-244X-10-1](https://doi.org/10.1186/1471-244X-10-1). PMID: [20055988](https://pubmed.ncbi.nlm.nih.gov/20055988/).
- Mårland C, et al. *The Autism–Tics, ADHD and other Comorbidities inventory (A-TAC): previous and predictive validity.* BMC Psychiatry. 2017;17:403. DOI: [10.1186/s12888-017-1563-0](https://doi.org/10.1186/s12888-017-1563-0). PMID: [29258473](https://pubmed.ncbi.nlm.nih.gov/29258473/).

The publications describe A-TAC as a screening/research inventory rather than a diagnostic assessment and establish the 19-item ADHD and 17-item ASD domains and their original three-category scoring. Final implementation must use the authorized instrument/version and its usage terms, or clearly remain a separately validated project-specific questionnaire.
