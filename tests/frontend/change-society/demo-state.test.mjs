import assert from "node:assert/strict";
import test from "node:test";

import {mapRunToDemoState, roleDisplayName, statusTone} from "../../../archives/hackathon/frontend/lib/demo-state.ts";

test("maps idle and transport failures to ready or degraded", () => {
  assert.equal(mapRunToDemoState(null, {apiReachable: true}), "ready");
  assert.equal(mapRunToDemoState(null, {apiReachable: false}), "degraded");
  assert.equal(mapRunToDemoState(null, {apiReachable: true, transportError: "offline"}), "degraded");
});

test("maps society lifecycle states for the judged demo", () => {
  assert.equal(mapRunToDemoState({state: "analyzing"}, {apiReachable: true}), "running");
  assert.equal(mapRunToDemoState({state: "awaiting_approval"}, {apiReachable: true}), "pending_approval");
  assert.equal(mapRunToDemoState({state: "completed"}, {apiReachable: true}), "completed");
  assert.equal(mapRunToDemoState({state: "failed"}, {apiReachable: true}), "failed");
});

test("formats role labels for the timeline", () => {
  assert.equal(roleDisplayName("policy_guardian"), "Policy Guardian");
});

test("statusTone maps demo view states to shell header tones", () => {
  assert.equal(statusTone("ready"), "idle");
  assert.equal(statusTone("running"), "active");
  assert.equal(statusTone("pending_approval"), "active");
  assert.equal(statusTone("completed"), "done");
  assert.equal(statusTone("failed"), "error");
  assert.equal(statusTone("degraded"), "error");
});

test("statusTone maps demo view states to shell header tones", () => {
  assert.equal(statusTone("ready"), "idle");
  assert.equal(statusTone("running"), "active");
  assert.equal(statusTone("pending_approval"), "active");
  assert.equal(statusTone("completed"), "done");
  assert.equal(statusTone("failed"), "error");
  assert.equal(statusTone("degraded"), "error");
});
