import { allQuestions } from "./questionnaireData.js";

export const SESSION_TTL_MS = 30 * 60 * 1000;

/** Report whether a public questionnaire question has a selected answer. */
export function getQuestionStatus(questionId, answers) {
  const answer = answers[questionId];
  if (!answer) return "unanswered";
  return "complete";
}

/** Count completed answers and identify unanswered questions within one section. */
export function getSectionStatus(section, answers) {
  const statuses = section.questions.map((item) => getQuestionStatus(item.id, answers));
  return {
    answered: statuses.filter((status) => status === "complete").length,
    complete: statuses.filter((status) => status === "complete").length,
    unansweredIds: section.questions
      .filter((item) => getQuestionStatus(item.id, answers) === "unanswered")
      .map((item) => item.id),
  };
}

/** Summarize overall completion and readiness for questionnaire submission. */
export function getQuestionnaireStatus(answers) {
  const statuses = allQuestions.map((item) => getQuestionStatus(item.id, answers));
  const answered = statuses.filter((status) => status === "complete").length;
  const complete = statuses.filter((status) => status === "complete").length;
  return {
    answered,
    complete,
    unanswered: allQuestions.length - answered,
    ready: complete === allQuestions.length,
  };
}
