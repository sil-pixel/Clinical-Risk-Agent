import assert from "node:assert/strict";
import test from "node:test";

import { allQuestions, DO_NOT_REMEMBER_ID, questionnaireSections } from "../src/questionnaireData.js";
import { getQuestionnaireStatus, getSectionStatus, SESSION_TTL_MS } from "../src/questionnaireState.js";

test("session expiry is exactly thirty minutes", () => {
  assert.equal(SESSION_TTL_MS, 1_800_000);
});

test("unknown answers are answered but do not make a section complete", () => {
  const section = questionnaireSections[0];
  const answers = Object.fromEntries(section.questions.map((item) => [item.id, "o01"]));
  answers[section.questions[0].id] = DO_NOT_REMEMBER_ID;

  assert.deepEqual(getSectionStatus(section, answers), {
    answered: section.questions.length,
    complete: section.questions.length - 1,
    unansweredIds: [],
    unknownIds: [section.questions[0].id],
  });
});

test("questionnaire is ready only when every answer is scoreable", () => {
  const answers = Object.fromEntries(allQuestions.map((item) => [item.id, "o01"]));
  assert.equal(getQuestionnaireStatus(answers).ready, true);

  answers.q085 = DO_NOT_REMEMBER_ID;
  const status = getQuestionnaireStatus(answers);
  assert.equal(status.ready, false);
  assert.equal(status.unknown, 1);
  assert.equal(status.unanswered, 0);
});
