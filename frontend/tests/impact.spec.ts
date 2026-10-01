import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import path from "node:path";

test("impact questions use import evidence and preserve request IDs through the proxy", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/repositories/demo");
  expect(created.status()).toBe(202);
  const repositoryId = (await created.json()).id;
  await expect
    .poll(async () => (await (await request.get(`/api/repositories/${repositoryId}`)).json()).status)
    .toBe("ready");
  await page.goto(`/repositories/${repositoryId}/ask`);
  const requestId = randomUUID();
  await page.setExtraHTTPHeaders({ "X-Request-ID": requestId });
  const queryResponse = page.waitForResponse(
    (response) => response.url().endsWith(`/api/repositories/${repositoryId}/query`),
  );
  await page.getByRole("textbox", { name: "Ask your repository" }).fill(
    "What will be affected if I modify validate_token?",
  );
  await page.getByRole("button", { name: "Send question", exact: true }).click();
  const response = await queryResponse;
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["x-request-id"]).toBe(requestId);
  const answer = await response.json();
  expect(answer.impact.path).toBe("shop/auth.py");
  expect(answer.impact.affected_files).toEqual(expect.arrayContaining([
    "shop/routes.py", "tests/test_auth.py",
  ]));
  expect(answer.citations.map((source: { file_path: string }) => source.file_path))
    .toEqual(expect.arrayContaining(["shop/auth.py", "shop/routes.py"]));
  await expect(page.locator(".answer-text").first()).toContainText("Potential impact");
  await expect(page.locator(".answer-text").first()).toContainText("shop/routes.py");
  await page.setExtraHTTPHeaders({});
  await page.getByRole("button", { name: "Inspect retrieval" }).click();
  await page.locator(".chat-scroll").evaluate((element) => { element.scrollTop = 0; });
  const screenshotDirectory = path.resolve(process.cwd(), "../docs/screenshots");
  await mkdir(screenshotDirectory, { recursive: true });
  await page.screenshot({ path: path.join(screenshotDirectory, "impact.png"), fullPage: true });
  await page.locator(".citation").filter({ hasText: "shop/routes.py" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator(".code-line.highlighted").first()).toBeVisible();
  await expect(page.locator(".code-viewer")).toContainText("from shop.auth import");
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "New conversation" }).click();
  await page.getByRole("textbox", { name: "Ask your repository" }).fill(
    "Which authentication files depend on MissingService?",
  );
  await page.getByRole("button", { name: "Send question", exact: true }).click();
  await expect(page.locator(".answer-text").first()).toContainText("without guessing");
  await expect(page.locator(".citation")).toHaveCount(0);
});
