import assert from "node:assert/strict";
import test from "node:test";

import {
  allQuestions,
  getOptionsForQuestion,
  modelQuestionCount,
  questionnaireSections,
  questionnaireVersion,
  totalQuestionCount,
} from "../src/questionnaireData.js";

const forbiddenPublicPatterns = [
  /A-?TAC/i,
  /DCMFNet/i,
  /SUD\d/i,
  /SCZ\d/i,
  /ADHD\d/i,
  /ASD\d/i,
  /ACE\d/i,
  /_var_/i,
  /generic_genetic/i,
];

test("questionnaire exposes exactly 85 opaque model questions", () => {
  assert.equal(totalQuestionCount, 85);
  assert.equal(modelQuestionCount, 85);
  assert.equal(new Set(allQuestions.map((item) => item.id)).size, 85);
  assert.deepEqual(
    new Set(allQuestions.map((item) => item.id)),
    new Set(Array.from({ length: 85 }, (_, index) => `q${String(index + 1).padStart(3, "0")}`)),
  );
});

test("age-15 substance prompts are explicitly retrospective", () => {
  const substanceSection = questionnaireSections.find((section) => section.id === "s01");
  assert.ok(substanceSection.description.startsWith("Thinking back now"));
  assert.ok(
    substanceSection.questions.every((item) =>
      /^(Thinking back to when|When) you were about 15/.test(item.prompt),
    ),
  );
});

test("public tobacco wording uses India-relevant smokeless products", () => {
  const publicCopy = JSON.stringify(questionnaireSections);
  assert.doesNotMatch(publicCopy, /snuff/i);
  assert.match(publicCopy, /gutkha/i);
  assert.match(publicCopy, /khaini/i);
  assert.match(publicCopy, /zarda/i);
  assert.match(publicCopy, /paan with tobacco/i);
});

test("public copy avoids known ambiguous or awkward constructions", () => {
  const publicCopy = JSON.stringify(questionnaireSections);
  const rejectedPhrases = [
    /experience seeing/i,
    /how recently had you .* at that time/i,
    /strongly avoid/i,
    /according to your own preferred conditions/i,
    /during the previous few months/i,
    /supplemental/i,
  ];
  for (const phrase of rejectedPhrases) {
    assert.doesNotMatch(publicCopy, phrase);
  }
});

test("the revised visual-experience question uses the approved age-fifteen timeframe", () => {
  const question = allQuestions.find((item) => item.id === "q007");
  assert.match(question.prompt, /age 15/i);
  assert.equal(questionnaireVersion, "prototype_questionnaire_v2");
});

test("the age-eighteen experience section places the catch-all question last", () => {
  const section = questionnaireSections.find((item) => item.id === "s06");
  assert.equal(section.questions.at(-1).id, "q076");
  assert.match(section.questions.at(-1).prompt, /not covered by the other questions/i);
});

test("the other-bullying caption describes the six grouped types in plain language", () => {
  const question = allQuestions.find((item) => item.id === "q072");
  assert.match(question.note, /race or ethnicity/i);
  assert.match(question.note, /sexual comments or behaviour/i);
  assert.match(question.note, /online bullying/i);
  assert.match(question.note, /money or belongings/i);
  assert.match(question.note, /threats/i);
  assert.match(question.note, /physical bullying/i);
  assert.doesNotMatch(question.note, /_bullying15/);
});

test("the other-events caption describes the five grouped experiences in plain language", () => {
  const question = allQuestions.find((item) => item.id === "q076");
  assert.match(question.note, /sexual abuse or assault/i);
  assert.match(question.note, /physical abuse/i);
  assert.match(question.note, /neglect of basic physical needs/i);
  assert.match(question.note, /witnessing physical violence/i);
  assert.doesNotMatch(question.note, /_abuse18|_assault18|_neglect18|_violence18/);
});

test("sections start with sex and family, then progress through ages nine, fifteen and eighteen", () => {
  assert.deepEqual(questionnaireSections.map((section) => section.id), [
    "s09", "s08", "s03", "s04", "s01", "s02", "s05", "s06", "s07",
  ]);
  questionnaireSections.forEach((section, index) => {
    assert.equal(section.eyebrow, `Section ${index + 1} of 9`);
  });
  assert.deepEqual(allQuestions.slice(0, 5).map((item) => item.id), [
    "q085", "q081", "q082", "q083", "q084",
  ]);
});

test("revised bullying IDs keep frequency, number and duration option sets aligned", () => {
  const section = questionnaireSections.find((item) => item.id === "s05");
  assert.deepEqual(section.questions.map((item) => [item.id, item.optionSet]), [
    ["q066", "bullyingFrequency"], ["q067", "bullyingFrequency"],
    ["q068", "bullyingFrequency"], ["q069", "bullyingFrequency"],
    ["q070", "bullyingPeople"], ["q071", "bullyingDuration"],
    ["q072", "bullyingFrequency"],
  ]);
  assert.match(section.questions.at(-1).prompt, /not covered by the other examples/i);
});

test("every section and question has descriptive copy and options", () => {
  assert.equal(questionnaireSections.length, 9);
  for (const section of questionnaireSections) {
    assert.ok(section.title.length > 0);
    assert.ok(section.description.length > 0);
    assert.ok(section.questions.length > 0);
    for (const item of section.questions) {
      assert.ok(item.prompt.length > 10);
      const options = getOptionsForQuestion(item);
      assert.ok(options.length >= 2);
      assert.equal(new Set(options.map((option) => option.id)).size, options.length);
      for (const option of options) {
        assert.ok(option.label.length > 0);
        assert.doesNotMatch(option.label, /^\d+$/);
      }
    }
  }
});

test("public questionnaire copy contains no internal model identifiers", () => {
  const publicCopy = JSON.stringify(questionnaireSections);
  for (const pattern of forbiddenPublicPatterns) {
    assert.doesNotMatch(publicCopy, pattern);
  }
});

test("questionnaire offers only scored options", () => {
  for (const item of allQuestions) {
    assert.ok(getOptionsForQuestion(item).every((option) => /^o\d{2}$/.test(option.id)));
  }
});
