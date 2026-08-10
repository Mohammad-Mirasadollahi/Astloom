import assert from "node:assert/strict";
import test from "node:test";

test("getApiBaseUrl uses same-origin proxy by default in browser", async () => {
  const originalWindow = globalThis.window;
  const originalEnv = process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL;
  const originalProxy = process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY;

  delete process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL;
  delete process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    writable: true,
    value: {location: {protocol: "http:", hostname: "192.168.1.150"}},
  });

  try {
    const {getApiBaseUrl} = await import("../../../archives/hackathon/frontend/lib/api-base-url.ts");
    assert.equal(getApiBaseUrl(), "/change-society-api");
  } finally {
    process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL = originalEnv;
    process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY = originalProxy;
    if (originalWindow === undefined) {
      delete globalThis.window;
    } else {
      Object.defineProperty(globalThis, "window", {configurable: true, value: originalWindow});
    }
  }
});

test("getApiBaseUrl keeps proxy when env is localhost on LAN", async () => {
  const originalWindow = globalThis.window;
  const originalEnv = process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL;
  const originalProxy = process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY;

  process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL = "http://localhost:32500";
  delete process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY;
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    writable: true,
    value: {location: {protocol: "http:", hostname: "192.168.1.150"}},
  });

  try {
    const {getApiBaseUrl} = await import("../../../archives/hackathon/frontend/lib/api-base-url.ts");
    assert.equal(getApiBaseUrl(), "/change-society-api");
  } finally {
    process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL = originalEnv;
    process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY = originalProxy;
    if (originalWindow === undefined) {
      delete globalThis.window;
    } else {
      Object.defineProperty(globalThis, "window", {configurable: true, value: originalWindow});
    }
  }
});

test("getApiBaseUrl maps localhost env to LAN host when proxy disabled", async () => {
  const originalWindow = globalThis.window;
  const originalEnv = process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL;
  const originalProxy = process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY;

  process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL = "http://localhost:32500";
  process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY = "false";
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    writable: true,
    value: {location: {protocol: "http:", hostname: "192.168.1.150"}},
  });

  try {
    const {getApiBaseUrl} = await import("../../../archives/hackathon/frontend/lib/api-base-url.ts");
    assert.equal(getApiBaseUrl(), "http://192.168.1.150:32500");
  } finally {
    process.env.NEXT_PUBLIC_CHANGE_SOCIETY_API_URL = originalEnv;
    process.env.NEXT_PUBLIC_CHANGE_SOCIETY_USE_PROXY = originalProxy;
    if (originalWindow === undefined) {
      delete globalThis.window;
    } else {
      Object.defineProperty(globalThis, "window", {configurable: true, value: originalWindow});
    }
  }
});
