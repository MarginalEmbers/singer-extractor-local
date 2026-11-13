import test from "node:test";
import assert from "node:assert/strict";
import { AudioTransport, selectionBetween, visibleWindow, isCovered, formatTime } from "../singer_extractor/web/timeline.mjs";

class Context {
  currentTime = 0;
  nodes = [];
  destination = {};
  async resume() {}
  createGain() { return { gain: { value: 0 }, connect() {} }; }
  createBufferSource() {
    const node = { connect() {}, disconnect() {}, start(time, offset) { this.offset = offset; }, stop() {} };
    this.nodes.push(node); return node;
  }
}

test("reverse drag and zoom clamp at song boundaries", () => {
  assert.deepEqual(selectionBetween(8, 2, 10), [2, 8]);
  assert.deepEqual(selectionBetween(-3, 50, 10), [0, 10]);
  assert.deepEqual(visibleWindow(100, 4, 90), { start: 75, span: 25 });
  assert.equal(isCovered([[1, 4], [5, 8]], 2, 6), false);
  assert.equal(isCovered([[1, 4]], 1, 4), true);
  assert.equal(formatTime(61.25, true), "01:01.2");
});

test("track switch preserves time, loop range, and pause point", async () => {
  const context = new Context(), transport = new AudioTransport(() => context);
  const original = { duration: 12 }, target = { duration: 12 };
  await transport.play(original, 2, 8, true, 2);
  context.currentTime = 3.75;
  assert.equal(await transport.switchBuffer(target), 5.75);
  assert.equal(transport.node.buffer, target);
  assert.equal(transport.node.offset, 5.75);
  assert.equal(transport.node.loopStart, 2);
  assert.equal(transport.node.loopEnd, 8);
  context.currentTime = 7;
  assert.equal(transport.position(), 3);
  assert.equal(transport.pause(), 3);
  context.currentTime = 20;
  assert.equal(transport.position(), 3);
  assert.equal(transport.playing, false);
});

test("natural completion reaches its bound and late resume cannot restart after pause", async () => {
  const context = new Context(), transport = new AudioTransport(() => context);
  await transport.play({ duration: 10 }, 1, 4);
  transport.node.onended();
  assert.equal(transport.position(), 4);
  assert.equal(transport.playing, false);
  let resume;
  context.resume = () => new Promise(resolve => { resume = resolve; });
  const pending = transport.play({ duration: 10 }, 2, 5);
  transport.pause(); resume(); await pending;
  assert.equal(transport.playing, false);
  assert.equal(context.nodes.length, 1);
});
