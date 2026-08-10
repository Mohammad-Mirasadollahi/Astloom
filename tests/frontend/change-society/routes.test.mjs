import assert from "node:assert/strict";
import test from "node:test";

import {APP_ROUTES, routeByPath, WORKSPACE_NAV_ROUTES} from "../../../archives/hackathon/frontend/lib/routes.ts";

test("WORKSPACE_NAV_ROUTES exposes canonical sidebar entries", () => {
  assert.equal(WORKSPACE_NAV_ROUTES.length, 4);
  assert.deepEqual(
    WORKSPACE_NAV_ROUTES.map(r => r.href),
    ["/overview", "/runs", "/settings", "/agents"],
  );
});

test("APP_ROUTES keeps canonical pages for routeByPath with unique hrefs", () => {
  assert.equal(APP_ROUTES.length, 5);
  const hrefs = new Set(APP_ROUTES.map(r => r.href));
  assert.equal(hrefs.size, 5);
  assert.ok(APP_ROUTES.some(r => r.href === "/runs" && r.id === "run"));
});

test("routeByPath resolves overview and trailing slashes", () => {
  assert.equal(routeByPath("/")?.id, "overview");
  assert.equal(routeByPath("/overview")?.id, "overview");
  assert.equal(routeByPath("/overview/")?.id, "overview");
  assert.equal(routeByPath("/dialogue"), undefined);
  assert.equal(routeByPath("/unknown"), undefined);
});
