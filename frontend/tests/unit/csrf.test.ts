// Unit tests for the CSRF cookie helpers.

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { CSRF_COOKIE_NAME } from "@/api/contracts";
import { hasCsrfCookie, readCsrfCookie } from "@/auth/csrf";

function setCookieJar(cookies: string[]): void {
  Object.defineProperty(document, "cookie", {
    configurable: true,
    get: () => cookies.join("; "),
    set: (value: string) => {
      // Naive: append. Sufficient for these tests.
      cookies.push(value.split(";")[0]!);
    },
  });
}

describe("csrf helpers", () => {
  let originalDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    originalDescriptor = Object.getOwnPropertyDescriptor(document, "cookie");
  });

  afterEach(() => {
    if (originalDescriptor) {
      Object.defineProperty(document, "cookie", originalDescriptor);
    } else {
      // Restore a default empty cookie jar.
      Object.defineProperty(document, "cookie", {
        configurable: true,
        value: "",
      });
    }
  });

  it("returns null when the cookie is absent", () => {
    setCookieJar([]);
    expect(readCsrfCookie()).toBeNull();
    expect(hasCsrfCookie()).toBe(false);
  });

  it("parses the peiars_csrf cookie from a multi-cookie jar", () => {
    const token = "abc123:def456";
    setCookieJar([`other=1`, `${CSRF_COOKIE_NAME}=${token}`, `third=xyz`]);
    expect(readCsrfCookie()).toBe(token);
    expect(hasCsrfCookie()).toBe(true);
  });

  it("handles values that themselves contain '=' (joins rest)", () => {
    // Even though HMAC hex never contains '=', the helper splits on every
    // '=' and rejoins, so a value like "a=b" is preserved.
    setCookieJar([`${CSRF_COOKIE_NAME}=a=b`]);
    expect(readCsrfCookie()).toBe("a=b");
  });

  it("trims whitespace around the cookie name", () => {
    setCookieJar([` ${CSRF_COOKIE_NAME} =token123`]);
    expect(readCsrfCookie()).toBe("token123");
  });

  it("returns null for an empty cookie value", () => {
    setCookieJar([`${CSRF_COOKIE_NAME}=`]);
    expect(readCsrfCookie()).toBeNull();
    expect(hasCsrfCookie()).toBe(false);
  });

  it("returns null when document.cookie is the empty string", () => {
    setCookieJar([]);
    Object.defineProperty(document, "cookie", {
      configurable: true,
      value: "",
    });
    expect(readCsrfCookie()).toBeNull();
  });
});
