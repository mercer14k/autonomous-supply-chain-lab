import { test, expect } from "../../apps/web/node_modules/@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

test("capture the real ten-day demonstration", async ({ page, request }) => {
  test.skip(
    process.env.LAB_SCREENSHOTS !== "1",
    "Opt-in documentation screenshot capture",
  );
  const headers = {
    Authorization: "Bearer local-demo-token",
    "Idempotency-Key": crypto.randomUUID(),
  };
  const created = await request.post("/api/v1/episodes", {
    headers,
    data: { config: { seed: 42, days: 30, policy: "agents", runtime: "none" } },
  });
  expect(created.ok()).toBeTruthy();
  const episode = await created.json();
  for (let day = 0; day < 10; day++) {
    const response = await request.post(`/api/v1/episodes/${episode.id}/step`, {
      headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
    });
    expect(response.ok()).toBeTruthy();
  }
  const directory = path.resolve(process.cwd(), "../../output/playwright");
  await mkdir(directory, { recursive: true });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.getByText(episode.id.slice(0, 8).toUpperCase(), { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("47,342 / 47,535 units served")).toBeVisible();
  await expect(
    page.locator('.scene-host[data-renderer="webgl"] canvas'),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(directory, "operations.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(
    page.getByText("600 inventory lines", { exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(directory, "inventory.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Operations", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: path.join(directory, "mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.getByRole("button", { name: "New episode", exact: true }).click();
  await page
    .getByLabel("Local model runtime", { exact: true })
    .selectOption("ollama");
  await expect(page.getByRole("dialog").getByRole("status")).not.toContainText(
    "Discovering installed",
  );
  await page.screenshot({
    path: path.join(directory, "model-picker.png"),
    fullPage: false,
  });
});
