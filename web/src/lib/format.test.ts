import { describe, it, expect } from "vitest";
import { dataFreshness } from "./format";

describe("dataFreshness", () => {
  it("treats a fresh fetch (no cache age) as just updated", () => {
    expect(dataFreshness(undefined)).toBe("数据刚刚更新");
    expect(dataFreshness(0)).toBe("数据刚刚更新");
  });

  it("treats anything under a minute as just updated", () => {
    expect(dataFreshness(59)).toBe("数据刚刚更新");
  });

  it("renders minutes", () => {
    expect(dataFreshness(60)).toBe("数据更新于 1 分钟前");
    expect(dataFreshness(3599)).toBe("数据更新于 59 分钟前");
  });

  it("renders hours", () => {
    expect(dataFreshness(3600)).toBe("数据更新于 1 小时前");
    expect(dataFreshness(7200)).toBe("数据更新于 2 小时前");
    expect(dataFreshness(86399)).toBe("数据更新于 23 小时前");
  });

  it("renders days", () => {
    expect(dataFreshness(86400)).toBe("数据更新于 1 天前");
    expect(dataFreshness(90000)).toBe("数据更新于 1 天前");
  });
});
