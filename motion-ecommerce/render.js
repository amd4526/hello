// Renders index.html frame by frame and pipes the frames into ffmpeg.
// Usage: node render.js [out.mp4] [fps] [--stills t1,t2,...]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

const DURATION = 27;
const args = process.argv.slice(2);
const stillsIdx = args.indexOf('--stills');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('file://' + path.join(__dirname, 'index.html'));
  await page.evaluate(() => document.fonts.ready);

  if (stillsIdx !== -1) {
    for (const t of args[stillsIdx + 1].split(',').map(Number)) {
      await page.evaluate(t => window.seek(t), t);
      await page.screenshot({ path: path.join(args[stillsIdx + 2] || '.', `still_${t}.png`) });
    }
    await browser.close();
    return;
  }

  const out = args[0] || 'video_silent.mp4';
  const fps = +(args[1] || 30);
  const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out],
    { stdio: ['pipe', 'inherit', 'inherit'] });

  const total = Math.round(DURATION * fps);
  for (let f = 0; f < total; f++) {
    await page.evaluate(t => window.seek(t), f / fps);
    const buf = await page.screenshot({ type: 'jpeg', quality: 98 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % fps === 0) process.stderr.write(`\rframe ${f}/${total}`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
  console.error('\ndone →', out);
})();
