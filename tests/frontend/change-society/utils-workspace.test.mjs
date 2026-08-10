import assert from "node:assert/strict";
import test from "node:test";

import {cn} from "../../../archives/hackathon/frontend/lib/utils.ts";

test("cn merges tailwind classes with last-wins for conflicts", () => {
  assert.equal(cn("px-2", "px-4"), "px-4");
  assert.equal(cn("text-sm", false && "hidden", "font-medium"), "text-sm font-medium");
});

test("panelClass pattern merges wsPanel with extras", () => {
  const wsPanel = "rounded-lg border border-border bg-card p-4 shadow-sm";
  const merged = cn(wsPanel, "mt-2");
  assert.ok(merged.includes("rounded-lg"));
  assert.ok(merged.includes("mt-2"));
});
