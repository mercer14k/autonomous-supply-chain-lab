import { test, expect } from "../../apps/web/node_modules/@playwright/test";

test("create, approve, inspect inventory, verify replay and export", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Operations control room" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "New episode", exact: true }).click();
  await page
    .getByLabel("Operating mode", { exact: true })
    .selectOption("approval");
  await page.getByLabel("Simulation days").fill("2");
  await page
    .getByRole("button", { name: "Create episode", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Step", exact: true }).click();
  await expect(page.getByText("OPERATOR REVIEW REQUIRED")).toBeVisible();
  await page.getByRole("button", { name: "Review evidence" }).click();
  await expect(page.getByRole("dialog")).toContainText("evidence_ids");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Approve & advance" }).click();
  await expect(page.getByText("OPERATOR REVIEW REQUIRED")).not.toBeVisible();
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Search inventory" })
    .fill("SKU-0001");
  await expect(
    page.getByText("3 inventory lines", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("No demand", { exact: true })).toHaveCount(3);
  await page
    .getByRole("button", { name: "Inspect", exact: false })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "synthetic-v1-seed-42-n-200",
  );
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Operations", exact: true }).click();
  await page.getByRole("button", { name: "Step", exact: true }).click();
  await page.getByRole("button", { name: "Reject plan", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Completed", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Experiments", exact: true }).click();
  await page
    .getByRole("button", { name: "Verify", exact: true })
    .first()
    .click();
  await expect(page.getByRole("status")).toContainText("Replay verified");
  const downloaded = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export episode", exact: false })
    .first()
    .click();
  expect((await downloaded).suggestedFilename()).toContain("episode-");
  expect(errors).toEqual([]);
});

test("malformed import remains visible and mobile layout stays within viewport", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Data & provenance", exact: true })
    .click();
  await page
    .locator("input[type=file]")
    .setInputFiles({
      name: "invalid.json",
      mimeType: "application/json",
      buffer: Buffer.from("{broken"),
    });
  await expect(page.getByRole("status")).toContainText("Dataset rejected");
  await page.getByRole("button", { name: "View report", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Malformed UTF-8 JSON");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  await page.getByRole("button", { name: "Operations", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Operations control room" }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
});
