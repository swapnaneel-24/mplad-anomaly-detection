// Unit tests for the ApiError predicates.

import { describe, expect, it } from "vitest";
import { ApiError } from "@/api/client";

function makeError(opts: Partial<ConstructorParameters<typeof ApiError>[0]>): ApiError {
  return new ApiError({
    status: opts.status ?? 0,
    code: opts.code ?? "REQUEST_FAILED",
    message: opts.message ?? "boom",
    requestId: opts.requestId ?? null,
    aborted: opts.aborted ?? false,
    timedOut: opts.timedOut ?? false,
    network: opts.network ?? false,
    details: opts.details,
  });
}

describe("ApiError predicates", () => {
  it("isUnauthorized: status === 401", () => {
    expect(makeError({ status: 401 }).isUnauthorized).toBe(true);
    expect(makeError({ status: 403 }).isUnauthorized).toBe(false);
    expect(makeError({ status: 0, network: true }).isUnauthorized).toBe(false);
  });

  it("isForbidden: status === 403", () => {
    expect(makeError({ status: 403 }).isForbidden).toBe(true);
    expect(makeError({ status: 401 }).isForbidden).toBe(false);
  });

  it("isRateLimited: status === 429", () => {
    expect(makeError({ status: 429 }).isRateLimited).toBe(true);
    expect(makeError({ status: 401 }).isRateLimited).toBe(false);
  });

  it("isServiceNotReady: status === 503 OR code === SERVICE_NOT_READY", () => {
    expect(makeError({ status: 503 }).isServiceNotReady).toBe(true);
    expect(makeError({ status: 500, code: "SERVICE_NOT_READY" }).isServiceNotReady).toBe(true);
    expect(makeError({ status: 500 }).isServiceNotReady).toBe(false);
  });

  it("isNetwork: network flag set (status 0)", () => {
    expect(makeError({ status: 0, network: true }).isNetwork).toBe(true);
    expect(makeError({ status: 0, timedOut: true }).isNetwork).toBe(false);
    expect(makeError({ status: 500 }).isNetwork).toBe(false);
  });
});
