import { expect, test } from "@playwright/test";
import { closeSync, ftruncateSync, openSync } from "node:fs";

test.skip(process.env.RUN_LARGE_UPLOAD_TEST !== "1", "Run explicitly for the 200MB upload check");

test("uploads a real 201MB browser file directly in sequential chunks", async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  await page.addInitScript(() => {
    const createElement = document.createElement.bind(document);
    document.createElement = ((tagName: string, options?: ElementCreationOptions) => {
      const element = createElement(tagName, options);
      if (tagName.toLowerCase() === "video") {
        Object.defineProperty(element, "duration", { configurable: true, get: () => 2400 });
        Object.defineProperty(element, "src", {
          configurable: true,
          set: () => queueMicrotask(() =>
            (element as HTMLVideoElement).onloadedmetadata?.(new Event("loadedmetadata")),
          ),
        });
      }
      return element;
    }) as typeof document.createElement;
  });
  const chunkRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "PUT" && request.url().includes("/chunks/")) {
      chunkRequests.push(request.url());
    }
  });
  const videoPath = testInfo.outputPath("large-lecture.mp4");
  const videoFile = openSync(videoPath, "w");
  ftruncateSync(videoFile, 201 * 1024 * 1024);
  closeSync(videoFile);

  await page.goto("/signup");
  await page.getByLabel("Email").fill(`large-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL("/");
  await page.getByLabel("Choose a lecture video").setInputFiles(videoPath);
  await page.getByRole("button", { name: "Create adaptive lecture" }).click();

  await expect(page).toHaveURL(/\/lectures\/[a-f0-9-]+$/, { timeout: 180_000 });
  expect(chunkRequests).toHaveLength(26);
  expect(chunkRequests.every((url) => new URL(url).origin === "http://127.0.0.1:8100")).toBe(
    true,
  );
});
