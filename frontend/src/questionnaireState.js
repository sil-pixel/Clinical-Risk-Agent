import { DO_NOT_REMEMBER_ID, allQuestions } from "./questionnaireData.js";

export const SESSION_TTL_MS = 30 * 60 * 1000;

export function getQuestionStatus(questionId, answers) {
  const answer = answers[questionId];
  if (!answer) return "unanswered";
  if (answer === DO_NOT_REMEMBER_ID) return "unknown";
  return "complete";
}

export function getSectionStatus(section, answers) {
  const statuses = section.questions.map((item) => getQuestionStatus(item.id, answers));
  return {
    answered: statuses.filter((status) => status !== "unanswered").length,
    complete: statuses.filter((status) => status === "complete").length,
    unansweredIds: section.questions
      .filter((item) => getQuestionStatus(item.id, answers) === "unanswered")
      .map((item) => item.id),
    unknownIds: section.questions
      .filter((item) => getQuestionStatus(item.id, answers) === "unknown")
      .map((item) => item.id),
  };
}

export function getQuestionnaireStatus(answers) {
  const statuses = allQuestions.map((item) => getQuestionStatus(item.id, answers));
  const answered = statuses.filter((status) => status !== "unanswered").length;
  const unknown = statuses.filter((status) => status === "unknown").length;
  const complete = statuses.filter((status) => status === "complete").length;
  return {
    answered,
    complete,
    unknown,
    unanswered: allQuestions.length - answered,
    ready: complete === allQuestions.length,
  };
}
