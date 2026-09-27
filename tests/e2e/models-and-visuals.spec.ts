import { test, expect } from "../../apps/web/node_modules/@playwright/test";

test("users select discovered or custom models without a Qwen default", async ({
  page,
}) => {
  await page.route("**/api/v1/models?runtime=*", async (route) => {
    const runtime = new URL(route.request().url()).searchParams.get("runtime");
    await route.fulfill({
      json: {
        runtime,
        available: true,
        models: [
          {
            id: "research/solver:custom-Q5",
            parameters: "14B",
            quantization: "Q5_K_M",
          },
        ],
        message: "Local models available",
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "New episode", exact: true }).click();
  await page
    .getByLabel("Local model runtime", { exact: true })
    .selectOption("ollama");
  await expect(page.getByLabel("Model ID", { exact: true })).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Create episode", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel("Available local models", { exact: true })
    .selectOption("research/solver:custom-Q5");
  await expect(page.getByLabel("Model ID", { exact: true })).toHaveValue(
    "research/solver:custom-Q5",
  );
  await page
    .getByLabel("Local model runtime", { exact: true })
    .selectOption("llamacpp");
  await expect(page.getByLabel("Model ID", { exact: true })).toHaveValue("");
  await page.getByLabel("Model ID", { exact: true }).fill("my-own-model.gguf");
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/episodes") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Create episode", exact: true })
    .click();
  const saved = await (await response).json();
  expect(saved.config.runtime).toBe("llamacpp");
  expect(saved.config.model).toBe("my-own-model.gguf");
  expect(saved.day).toBe(0);
  await expect(
    page.getByText("my-own-model.gguf", { exact: true }),
  ).toBeVisible();
});

test("offline discovery preserves manual model choice", async ({ page }) => {
  await page.route("**/api/v1/models?runtime=*", (route) =>
    route.fulfill({
      json: {
        runtime: "vllm",
        available: false,
        models: [],
        message: "Start the local runtime or enter its exact served model ID.",
      },
    }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "New episode", exact: true }).click();
  await page
    .getByLabel("Local model runtime", { exact: true })
    .selectOption("vllm");
  await expect(page.getByRole("dialog").getByRole("status")).toContainText(
    "Start the local runtime",
  );
  await page
    .getByLabel("Model ID", { exact: true })
    .fill("organization/local-instruct");
  await expect(
    page.getByRole("button", { name: "Create episode", exact: true }),
  ).toBeEnabled();
});

test("Three.js renders and motion controls work with reduced motion", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(
    page.locator('.scene-host[data-renderer="webgl"] canvas'),
  ).toBeVisible();
  await expect(page.locator(".scene-fallback")).not.toBeVisible();
  await page.getByRole("button", { name: "Pause network motion" }).click();
  await expect(
    page.getByRole("button", { name: "Resume network motion" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset network view" }).click();
  await expect(page.locator(".scene-host canvas")).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("region", { name: "Supply network visualization" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  ).toBe(false);
  expect(errors).toEqual([]);
});

test("network evidence remains usable without WebGL", async ({ page }) => {
  await page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      type: string,
      ...args: unknown[]
    ) {
      if (type === "webgl2") return null;
      return Reflect.apply(getContext, this, [type, ...args]);
    } as typeof getContext;
  });
  await page.goto("/");
  await expect(
    page.locator('.scene-host[data-renderer="unavailable"]'),
  ).toBeVisible();
  await expect(page.locator(".scene-fallback")).toContainText(
    "Network details remain available",
  );
  await page.getByRole("button", { name: "Chicago", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("warehouse evidence");
});
