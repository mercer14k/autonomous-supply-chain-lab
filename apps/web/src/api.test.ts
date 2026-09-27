import { describe, expect, it } from "vitest";
import { money, number, percent } from "./api";
describe("Unknown measurements remain distinct from zero", () => {
  it("does not fabricate rates before demand is observed", () => {
    expect(percent(null)).toBe("—");
    expect(percent(0)).toBe("0.0%");
    expect(percent(0.987)).toBe("98.7%");
  });
  it("formats modeled monetary values and missing measurements", () => {
    expect(money(1500)).toBe("$1,500");
    expect(money(undefined)).toBe("—");
    expect(number(0)).toBe("0");
  });
});
