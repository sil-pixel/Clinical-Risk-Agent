import assert from "node:assert/strict";
import test from "node:test";

import {
  DO_NOT_REMEMBER_ID,
  allQuestions,
  getOptionsForQuestion,
  modelQuestionCount,
  questionnaireSections,
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
  const substanceSection = questionnaireSections[0];
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

test("the exceptional age-nine experience keeps its original timeframe", () => {
  const question = allQuestions.find((item) => item.id === "q007");
  assert.match(question.prompt, /age 9/i);
});

test("section six places the catch-all experience last", () => {
  const section = questionnaireSections.find((item) => item.id === "s06");
  assert.equal(section.questions.at(-1).id, "q073");
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

test("memory-unknown state is not a scored option", () => {
  for (const item of allQuestions) {
    assert.ok(getOptionsForQuestion(item).every((option) => option.id !== DO_NOT_REMEMBER_ID));
  }
});
