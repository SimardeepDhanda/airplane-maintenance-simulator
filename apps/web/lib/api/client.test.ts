import { describe, expect, it } from "vitest";
import { buildUrl } from "./client";

describe("buildUrl", () => {
  it("drops empty values and repeats array params", () => {
    const url = new URL(
      buildUrl("/api/v1/engines", {
        status: ["critical", "review"],
        page: 2,
        station: "",
        x: null,
      }),
    );
    expect(url.pathname).toBe("/api/v1/engines");
    expect(url.searchParams.getAll("status")).toEqual(["critical", "review"]);
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.has("station")).toBe(false);
    expect(url.searchParams.has("x")).toBe(false);
  });
});
