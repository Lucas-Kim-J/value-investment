import { describe, it, expect } from "vitest";
import { resolveHref } from "./docs";

describe("resolveHref", () => {
  it("resolves a relative doc link against the current doc dir, keeping the hash", () => {
    expect(resolveHref("../learning/valuation-cheatsheet.html#tool-1", "routine/glossary")).toEqual({
      to: "/doc/learning/valuation-cheatsheet",
      hash: "#tool-1",
    });
  });
});
