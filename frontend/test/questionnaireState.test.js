import assert from "node:assert/strict";
import test from "node:test";

import { allQuestions, questionnaireSections } from "../src/questionnaireData.js";
import { getQuestionnaireStatus, getSectionStatus, SESSION_TTL_MS } from "../src/questionnaireState.js";

test("session expiry is exactly thirty minutes", () => {
  assert.equal(SESSION_TTL_MS, 1_800_000);
});

test("a fully answered section is complete", () => {
  const section = questionnaireSections[0];
  const answers = Object.fromEntries(section.questions.map((item) => [item.id, "o01"]));

  assert.deepEqual(getSectionStatus(section, answers), {
    answered: section.questions.length,
    complete: section.questions.length,
    unansweredIds: [],
  });
});

test("questionnaire is ready only when every answer is scoreable", () => {
  const answers = Object.fromEntries(allQuestions.map((item) => [item.id, "o01"]));
  assert.equal(getQuestionnaireStatus(answers).ready, true);

  delete answers.q085;
  const status = getQuestionnaireStatus(answers);
  assert.equal(status.ready, false);
  assert.equal(status.unanswered, 1);
});
