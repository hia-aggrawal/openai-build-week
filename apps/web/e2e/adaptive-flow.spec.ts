import { expect, test } from "@playwright/test";

async function createAccount(page: import("@playwright/test").Page) {
  await page.goto("/signup");
  await page.getByLabel("Email").fill(`e2e-${Date.now()}-${Math.random()}@example.com`);
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL("/");
}

test("logged-out visitors are redirected and can end an authenticated session", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL("/login");

  await createAccount(page);
  await page.getByRole("button", { name: "Log out" }).click();

  await expect(page).toHaveURL("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("desktop hero keeps the heading clear of the upload card", async ({ page }) => {
  await createAccount(page);
  await expect(page.getByRole("link", { name: "Library" })).toBeVisible();

  for (const width of [1000, 1100, 1200, 1400]) {
    await page.setViewportSize({ width, height: 900 });
    const heading = await page.getByRole("heading", { name: /Spend time where/ }).boundingBox();
    const card = await page.locator(".upload-card").boundingBox();

    expect(heading).not.toBeNull();
    expect(card).not.toBeNull();
    expect(heading!.x + heading!.width).toBeLessThanOrEqual(card!.x);
    expect(card!.x + card!.width).toBeLessThanOrEqual(width);
  }

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await expect(page.getByRole("link", { name: "StudyFlow home" })).toBeVisible();
  const header = await page.locator(".site-header").boundingBox();
  expect(header).not.toBeNull();
  expect(header!.y).toBeLessThanOrEqual(1);

  await page.getByRole("link", { name: "Library" }).click();
  await expect(page).toHaveURL("/library");
  await expect(page.getByRole("heading", { name: "Your lectures" })).toBeVisible();
  await expect(page.getByText(/Use the \+ button above/)).toBeVisible();
  await page.getByRole("button", { name: "Upload a lecture" }).click();
  await expect(page.getByRole("dialog", { name: "Upload a lecture" })).toBeVisible();
  await page.getByRole("button", { name: "Close upload dialog" }).click();
  await expect(page.getByRole("link", { name: "Library" })).toHaveCount(0);
});

test("upload processes into an adaptive player and changes speed", async ({ page }) => {
  await page.addInitScript(() => {
    const createElement = document.createElement.bind(document);
    document.createElement = ((tagName: string, options?: ElementCreationOptions) => {
      const element = createElement(tagName, options);
      if (tagName.toLowerCase() === "video") {
        let source = "";
        Object.defineProperty(element, "duration", { configurable: true, get: () => 80 });
        Object.defineProperty(element, "src", {
          configurable: true,
          get: () => source,
          set: (value: string) => {
            source = value;
            queueMicrotask(() => (element as HTMLVideoElement).onloadedmetadata?.(new Event("loadedmetadata")));
          },
        });
      }
      return element;
    }) as typeof document.createElement;
  });

  await createAccount(page);
  await page.getByLabel("Lecture title optional").fill("Adaptive systems lecture");
  await page.getByLabel("Choose a lecture video").setInputFiles({
    name: "lecture.webm",
    mimeType: "video/webm",
    buffer: Buffer.from("studyflow-e2e-video"),
  });
  await page.getByRole("button", { name: "Create adaptive lecture" }).click();

  await expect(page).toHaveURL(/\/lectures\/[a-f0-9-]+$/);
  await expect(page.getByText("Preparing your lecture")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Adaptive systems lecture" })).toBeVisible();
  await expect(page.getByLabel("Adaptive playback timeline")).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Adaptive systems lecture" })).toBeVisible();
  await expect(page.getByLabel("Adaptive playback timeline")).toBeVisible();

  const video = page.locator("video");
  const captions = video.locator('track[kind="captions"]');
  await expect(captions).toHaveAttribute("srclang", "en");
  await expect(captions).toHaveAttribute("label", "English");
  await expect(captions).toHaveAttribute(
    "src",
    /\/api\/lectures\/[a-f0-9-]+\/captions\.vtt$/,
  );
  await video.evaluate((element) => {
    const media = element as HTMLVideoElement;
    Object.defineProperty(media, "currentTime", {
      configurable: true,
      writable: true,
      value: 0,
    });
    let paused = true;
    Object.defineProperty(media, "paused", {
      configurable: true,
      get: () => paused,
    });
    media.play = () => {
      paused = false;
      media.dataset.playState = "playing";
      media.dispatchEvent(new Event("play"));
      return Promise.resolve();
    };
    media.pause = () => {
      paused = true;
      media.dataset.playState = "paused";
      media.dispatchEvent(new Event("pause"));
    };
  });
  await expect(page.getByRole("button", { name: "-10s" })).toBeVisible();
  await expect(page.getByRole("button", { name: "+10s" })).toBeVisible();
  await video.click({ position: { x: 20, y: 20 } });
  await expect(video).toHaveAttribute("data-play-state", "playing");
  await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();
  await video.click({ position: { x: 20, y: 20 } });
  await expect(video).toHaveAttribute("data-play-state", "paused");

  await page.getByRole("button", { name: "Enter fullscreen" }).click();
  await expect
    .poll(() => page.evaluate(() => document.fullscreenElement?.classList.contains("video-shell")))
    .toBe(true);
  await expect(page.getByLabel("Video controls")).toBeVisible();
  const paceScrubber = page.getByRole("slider", { name: "Lecture pace seek bar" });
  await expect(paceScrubber).toBeVisible();
  const paceSegments = paceScrubber.locator(".player-pace-segment");
  await expect(paceSegments).not.toHaveCount(0);
  const scrubberBounds = await paceScrubber.boundingBox();
  expect(scrubberBounds).not.toBeNull();
  await page.mouse.move(
    scrubberBounds!.x + scrubberBounds!.width * 0.25,
    scrubberBounds!.y + scrubberBounds!.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    scrubberBounds!.x + scrubberBounds!.width * 0.75,
    scrubberBounds!.y + scrubberBounds!.height / 2,
  );
  await page.mouse.up();
  await expect
    .poll(() => video.evaluate((element) => (element as HTMLVideoElement).currentTime))
    .toBeCloseTo(60, 0);
  await video.click({ position: { x: 20, y: 20 } });
  await expect(video).toHaveAttribute("data-play-state", "playing");
  await video.click({ position: { x: 20, y: 20 } });
  await expect(video).toHaveAttribute("data-play-state", "paused");
  const fullscreenControls = await page.getByLabel("Video controls").boundingBox();
  const fullscreenViewport = page.viewportSize();
  expect(fullscreenControls).not.toBeNull();
  expect(fullscreenViewport).not.toBeNull();
  expect(fullscreenControls!.y + fullscreenControls!.height).toBeLessThanOrEqual(
    fullscreenViewport!.height,
  );
  await page.getByRole("button", { name: "Exit fullscreen" }).click();
  await expect.poll(() => page.evaluate(() => document.fullscreenElement)).toBeNull();

  await video.evaluate((element) => {
    (element as HTMLVideoElement).currentTime = 5;
  });
  await page.getByRole("button", { name: "-10s" }).click();
  await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).currentTime)).toBe(0);
  await page.getByRole("button", { name: "+10s" }).click();
  await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).currentTime)).toBe(10);
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).currentTime)).toBe(20);
  await page.keyboard.press("k");
  await expect(video).toHaveAttribute("data-play-state", "playing");
  await page.keyboard.press("Space");
  await expect(video).toHaveAttribute("data-play-state", "paused");
  await page.keyboard.press("m");
  await expect.poll(() => video.evaluate((element) => (element as HTMLVideoElement).muted)).toBe(true);

  await video.evaluate((element) => {
    Object.defineProperty(element, "currentTime", {
      configurable: true,
      writable: true,
      value: 41,
    });
    element.dispatchEvent(new Event("timeupdate"));
  });

  await expect(page.getByText("1×")).toBeVisible();
  await expect
    .poll(() => video.evaluate((element) => (element as HTMLVideoElement).playbackRate))
    .toBe(1);

  await expect(page.getByRole("link", { name: "Library" })).toBeVisible();
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page).toHaveURL("/library");
  const library = page.locator("#your-lectures");
  const completedLecture = library.locator("article").filter({ hasText: "Adaptive systems lecture" });
  await expect(completedLecture.getByRole("link", { name: /Adaptive systems lecture/ })).toBeVisible();
  await expect(completedLecture.getByText("completed")).toBeVisible();
});
