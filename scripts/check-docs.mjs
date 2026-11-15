import { readFileSync, existsSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

// Structural QA for authored documents. Semantic review is recorded separately.
let links = 0;
for (const file of process.argv.slice(2)) {
  const body = readFileSync(file, 'utf8');
  if (!/^# .+/m.test(body)) throw new Error(`${file}: missing title`);
  if (body.includes('\uFFFD')) throw new Error(`${file}: invalid text encoding`);
  for (const [, target] of body.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
    if (/^(https?:|mailto:|#)/.test(target)) continue;
    const path = resolve(dirname(file), target.split('#')[0]);
    if (!existsSync(path) || !statSync(path).isFile()) {
      throw new Error(`${file}: missing link target ${target}`);
    }
    links++;
  }
  console.log(`PASS: ${file} title, encoding and local links`);
}
console.log(`PASS: ${links} local links resolved. Semantic review is not automated.`);
