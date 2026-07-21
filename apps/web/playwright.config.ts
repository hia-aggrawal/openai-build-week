import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "cd ../api && ../../.venv/bin/alembic upgrade head && ../../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100",
      url: "http://127.0.0.1:8100/api/health",
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
      env: {
        APP_ENV: "test",
        DATABASE_URL: "sqlite:///./playwright.db",
        MEDIA_STORAGE_PATH: "./playwright-media",
        PROCESSING_MODE: "mock",
        TRANSCRIPTION_PROVIDER: "mock",
        CLASSIFICATION_PROVIDER: "mock",
        MOCK_STAGE_DELAY_SECONDS: "0.2",
        FRONTEND_ORIGIN: "http://127.0.0.1:3100",
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100",
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
      env: {
        API_ORIGIN: "http://127.0.0.1:8100",
        NEXT_PUBLIC_API_ORIGIN: "http://127.0.0.1:8100",
      },
    },
  ],
});
