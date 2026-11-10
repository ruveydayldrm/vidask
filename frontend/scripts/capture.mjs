// Captures README screenshots + a demo recording using the locally installed
// Edge/Chrome (playwright-core, no browser download).
//
//   node scripts/capture.mjs [videoId]
//
// Requires the API on :8000 (with the video processed) and the web app on :3000.
import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const OUT = path.join(ROOT, "docs", "images");
const FRAMES = path.join(OUT, "_frames");
const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const VIDEO_ID = process.argv[2] ?? "tKCURAMFdd4";
const QUESTION = process.env.QUESTION ?? "What does writing @log_function above say_hello actually do?";
const CHANNEL = process.env.BROWSER_CHANNEL ?? "msedge";

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: CHANNEL, headless: true });

async function newPage({ theme = "dark", lang = "en", width = 1440, height = 900 } = {}) {
  const ctx = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 2,
    colorScheme: theme,
  });
  await ctx.addInitScript(
    ([t, l]) => {
      localStorage.setItem("theme", t);
      localStorage.setItem("vidask.lang", l);
    },
    [theme, lang],
  );
  return { ctx, page: await ctx.newPage() };
}

const shot = (page, name) => page.screenshot({ path: path.join(OUT, name) });

// 1. Home with an animated preview -------------------------------------------
for (const theme of ["light", "dark"]) {
  const { ctx, page } = await newPage({ theme });
  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.fill("#url", `https://youtu.be/${VIDEO_ID}`);
  await page.waitForSelector("form img[src*='ytimg']", { timeout: 30_000 });
  await page.waitForTimeout(900);
  await shot(page, `home-${theme}.png`);
  await ctx.close();
}

// 2. Workspace: ask → stream → hover + click a citation (frames → demo.gif) ----
{
  const { ctx, page } = await newPage({ theme: "dark" });
  await page.goto(`${WEB}/v/${VIDEO_ID}`, { waitUntil: "networkidle" });
  await page.waitForSelector("#question");
  await page.waitForTimeout(2500); // let the player paint
  // Grab a frame every ~350 ms for the demo GIF (assembled with ffmpeg afterwards).
  mkdirSync(FRAMES, { recursive: true });
  let frame = 0;
  let recording = true;
  const recorder = (async () => {
    while (recording) {
      await page
        .screenshot({ path: path.join(FRAMES, `${String(frame++).padStart(4, "0")}.png`), scale: "css" })
        .catch(() => {});
      await new Promise((r) => setTimeout(r, 350));
    }
  })();
  await page.click("#question");
  await page.keyboard.type(QUESTION, { delay: 25 });
  await page.keyboard.press("Enter");
  await page.waitForSelector("button[data-ts]", { timeout: 240_000 });
  await page.waitForFunction(() => !document.querySelector("[aria-busy='true']"), null, {
    timeout: 240_000,
  });
  const chip = page.locator(".prose-answer button[data-ts]").first();
  await chip.hover();
  await page.waitForTimeout(900);
  await page.getByRole("tab", { name: /transcript/i }).click();
  await chip.click();
  await page.waitForTimeout(2200);
  recording = false;
  await recorder;
  await chip.hover();
  await page.waitForTimeout(700);
  await shot(page, "workspace.png");
  await page.getByRole("tab", { name: /chapters/i }).click();
  await page.waitForTimeout(700);
  await shot(page, "workspace-chapters.png");
  await ctx.close();
}

// 3. Light workspace (summary) and mobile -----------------------------------
{
  const { ctx, page } = await newPage({ theme: "light", lang: "tr" });
  await page.goto(`${WEB}/v/${VIDEO_ID}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await shot(page, "workspace-light-tr.png");
  await ctx.close();
}
{
  const { ctx, page } = await newPage({ theme: "dark", width: 390, height: 844 });
  await page.goto(`${WEB}/v/${VIDEO_ID}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await shot(page, "mobile.png");
  await ctx.close();
}

await browser.close();

// Assemble the GIF: drop identical frames during the LLM wait, palette for quality.
const frames = readdirSync(FRAMES).filter((f) => f.endsWith(".png")).length;
if (frames > 0) {
  const ff = spawnSync(
    "ffmpeg",
    [
      "-y", "-loglevel", "error", "-framerate", "3", "-i", path.join(FRAMES, "%04d.png"),
      "-vf",
      "mpdecimate=hi=512:lo=256:frac=0.5,setpts=N/3/TB,scale=1100:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=160[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
      "-loop", "0", path.join(OUT, "demo.gif"),
    ],
    { stdio: "inherit" },
  );
  if (ff.status !== 0) console.warn("ffmpeg failed; frames kept in", FRAMES);
  else rmSync(FRAMES, { recursive: true, force: true });
}
console.log(`✔ ${frames} frames, screenshots in ${path.relative(ROOT, OUT)}`);
