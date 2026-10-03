import test from "node:test";
import assert from "node:assert/strict";
import { kappa, validateReview } from "./judgeAgreement.js";

test("Cohen kappa matches the hand-computed ordinal matrix", () => {
  const human = ["bad", "acceptable", "good"], judge = ["bad", "good", "good"];
  assert.equal(kappa(human, judge).value, 0.5);
  assert.ok(Math.abs(kappa(human, judge, "linear").value - 2 / 3) < 1e-10);
  assert.ok(Math.abs(kappa(human, judge, "quadratic").value - 0.8) < 1e-10);
  assert.equal(kappa([], []).value, null);
  assert.equal(kappa(["good"], ["good"]).value, null);
});

test("Import refuses changed fixtures or unlabelled confirmed reviews", () => {
  const packet = { case_sha256: "fixture", cases: [{ id: "a", question: "Question", human_reviewed: false }] };
  assert.equal(validateReview(packet, structuredClone(packet)).cases.length, 1);
  const altered = structuredClone(packet);
  altered.cases[0].question = "Changed";
  assert.throws(() => validateReview(packet, altered));
  const unlabelled = structuredClone(packet);
  unlabelled.cases[0].human_reviewed = true;
  assert.throws(() => validateReview(packet, unlabelled));
});
