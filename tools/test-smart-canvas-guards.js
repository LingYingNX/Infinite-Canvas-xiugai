const assert = require('node:assert/strict');
const fs = require('node:fs');

const source = fs.readFileSync('static/js/smart-canvas.js', 'utf8');

assert.ok(!source.includes('promptInput.innerHTML = subject.promptDraftHtml'), 'stored prompt HTML must not be rendered');
assert.ok(!source.includes('promptInput.innerHTML = hasToken'), 'stored prompt HTML token branch must not return');
assert.ok(source.includes('const rebuilt = promptHtmlWithMentionTokens(text, subject.runPromptRefs || []);'), 'prompt drafts must be rebuilt safely');
assert.ok(source.includes('canvasSaveRetryTimer'), 'failed smart-canvas saves need retry state');
assert.ok(source.includes("window.addEventListener('beforeunload', event =>"), 'dirty canvases need an unload warning');

console.log('smart-canvas prompt safety and save retry guards: ok');
