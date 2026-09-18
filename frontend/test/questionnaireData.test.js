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

test("questionnaire exposes 85 model questions and three opaque supplemental questions", () => {
  assert.equal(totalQuestionCount, 88);
  assert.equal(modelQuestionCount, 85);
  assert.equal(new Set(allQuestions.map((item) => item.id)).size, 88);
  assert.deepEqual(
    new Set(allQuestions.map((item) => item.id)),
    new Set(Array.from({ length: 88 }, (_, index) => `q${String(index + 1).padStart(3, "0")}`)),
  );
});

test("supplemental abuse questions are excluded from the model count", () => {
  const supplemental = allQuestions.filter((item) => item.supplemental);
  assert.deepEqual(supplemental.map((item) => item.id), ["q086", "q087", "q088"]);
  assert.ok(supplemental.every((item) => item.note.includes("not used by the current research model")));
});

test("age-15 substance prompts are explicitly retrospective", () => {
  const substanceSection = questionnaireSections[0];
  assert.ok(substanceSection.description.startsWith("Thinking back now"));
  assert.ok(substanceSection.questions.every((item) => item.prompt.startsWith("Thinking back")));
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
