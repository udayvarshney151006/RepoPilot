import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const screenshotDirectory = path.resolve(process.cwd(), "../docs/screenshots");

// Integration test: a live backend and frontend are required. No requests are mocked.
test("index demo, ask with sources, inspect files and dependencies, evaluate, and review a patch", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const health = await request.get("/api/health");
  expect(
    health.ok(),
    "Backend must be reachable through the Next.js proxy",
  ).toBeTruthy();
  await mkdir(screenshotDirectory, { recursive: true });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Less searching/ }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(screenshotDirectory, "landing.png"),
    fullPage: true,
  });
  await page.goto("/dashboard?import=1");
  await page.getByRole("button", { name: "Try the demo repository" }).click();
  await expect(page).toHaveURL(/\/repositories\/[a-f0-9-]+$/);
  const repoId = new URL(page.url()).pathname.split("/").at(-1)!;
  await expect
    .poll(
      async () => {
        const response = await request.get(`/api/repositories/${repoId}`);
        return (await response.json()).status;
      },
      { timeout: 60000 },
    )
    .toBe("ready");
  await page.goto(`/repositories/${repoId}/ask`);
  await page
    .getByRole("textbox", { name: "Ask your repository" })
    .fill("How does authentication work?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".citation").first()).toBeVisible();
  await page.locator(".citation").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator(".code-line.highlighted").first()).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Inspect retrieval" }).click();
  await expect(
    page.getByRole("heading", { name: "Retrieval inspector" }),
  ).toBeVisible();
  await expect(page.locator(".retrieval-result").first()).toBeVisible();
  await page.locator(".chat-scroll").evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: path.join(screenshotDirectory, "workspace.png"),
    fullPage: true,
  });
  await page.goto(`/repositories/${repoId}/files`);
  await page.getByRole("button", { name: "checkout.py", exact: true }).click();
  await expect(page.locator(".code-header")).toContainText("checkout.py");
  await expect(page.locator(".symbol-chip").first()).toBeVisible();
  await page.goto(`/repositories/${repoId}/dependencies`);
  await expect(
    page.getByRole("img", { name: "Repository file import graph" }),
  ).toBeVisible();
  await expect(page.locator(".graph-node")).not.toHaveCount(0);
  await page.locator(".graph-node").first().click();
  await expect(page.locator(".graph-detail-heading h3")).not.toBeEmpty();
  await page.goto(`/repositories/${repoId}/evaluations`);
  await page
    .getByRole("button", { name: "Run evaluation", exact: true })
    .click();
  await expect(page.locator(".metric-table tbody tr")).toHaveCount(4, {
    timeout: 60000,
  });
  await expect(page.locator(".metric-table")).toContainText(
    "Hybrid + reranker",
  );
  await page.screenshot({
    path: path.join(screenshotDirectory, "evaluations.png"),
    fullPage: true,
  });
  await page.goto(`/repositories/${repoId}/agent`);
  await page
    .getByRole("textbox", { name: "What should the agent investigate?" })
    .fill(
      "POST /checkout returns 500 when an item omits quantity. Investigate and propose a fix.",
    );
  await page.getByRole("button", { name: "Start investigation" }).click();
  await expect(page.getByRole("button", { name: "Approve patch" })).toBeVisible(
    { timeout: 60000 },
  );
  await expect(page.locator(".trace-step")).not.toHaveCount(0);
  await expect(page.locator(".diff-viewer")).toContainText("quantity");
  await expect(page.locator(".test-results")).toContainText("unavailable");
  await page.screenshot({
    path: path.join(screenshotDirectory, "agent.png"),
    fullPage: true,
  });
  // Rejection is a real API decision and must leave the source unchanged.
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(page.locator(".run-detail-title .badge")).toHaveText("rejected");
  await page.goto(`/repositories/${repoId}/settings`);
  await expect(
    page.getByRole("heading", { name: "Public configuration" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("landing and repository navigation remain usable on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Less searching/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page
    .getByRole("link", { name: "Connect repository", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Connect a repository" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();
  await expect(
    page.getByRole("heading", { name: "Repositories", exact: true }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  expect(overflow).toBeFalsy();
});

test("ZIP upload passes the bounded API proxy and produces indexed source", async ({
  page,
  request,
}) => {
  await page.goto("/dashboard?import=1");
  await page.getByRole("button", { name: "ZIP upload", exact: true }).click();
  await page
    .getByLabel("Upload repository ZIP")
    .setInputFiles(
      path.resolve(process.cwd(), "tests/fixtures/tiny-repository.zip"),
    );
  await expect(page).toHaveURL(/\/repositories\/[a-f0-9-]+$/);
  const repositoryId = new URL(page.url()).pathname.split("/").at(-1)!;
  await expect
    .poll(
      async () =>
        (await (await request.get(`/api/repositories/${repositoryId}`)).json())
          .status,
      { timeout: 60000 },
    )
    .toBe("ready");
  const files = await (
    await request.get(`/api/repositories/${repositoryId}/files`)
  ).json();
  expect(files.map((file: { path: string }) => file.path)).toContain(
    "calculator.py",
  );
  await page.goto(`/repositories/${repositoryId}/files`);
  await page
    .getByRole("button", { name: "calculator.py", exact: true })
    .click();
  await expect(page.locator(".code-viewer")).toContainText("def add");
});
