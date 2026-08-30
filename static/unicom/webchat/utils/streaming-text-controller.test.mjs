import assert from 'node:assert/strict';
import test from 'node:test';
import { StreamingTextController } from './streaming-text-controller.mjs';

function harness({ reducedMotion = false } = {}) {
  const callbacks = new Map();
  const cancelled = [];
  const updates = [];
  let id = 0;
  const controller = new StreamingTextController({
    onUpdate: (text) => updates.push(text),
    schedule: (callback) => { callbacks.set(++id, callback); return id; },
    cancel: (handle) => { cancelled.push(handle); callbacks.delete(handle); },
    prefersReducedMotion: () => reducedMotion,
  });
  const frame = () => {
    const entry = callbacks.entries().next().value;
    assert.ok(entry, 'expected an animation callback');
    callbacks.delete(entry[0]);
    entry[1]();
  };
  return { controller, updates, callbacks, cancelled, frame };
}

test('reveals small deltas one word at a time', () => {
  const h = harness();
  h.controller.setTarget('Hello smooth world');
  assert.deepEqual(h.updates, []);
  h.frame();
  assert.equal(h.updates.at(-1), 'Hello ');
  h.frame();
  assert.equal(h.updates.at(-1), 'Hello smooth ');
  h.frame();
  assert.equal(h.updates.at(-1), 'Hello smooth world');
});

test('buffers raw non-cumulative delta chunks', () => {
  const h = harness();
  h.controller.setTarget('Hello ');
  h.frame();
  h.controller.setTarget('world');
  h.frame();
  while (h.callbacks.size) h.frame();
  assert.equal(h.updates.at(-1), 'Hello world');
});

test('accelerates through a burst while preserving exact source text', () => {
  const h = harness();
  const burst = Array.from({ length: 35 }, (_, i) => `word${i}`).join(' ');
  h.controller.setTarget(burst);
  h.frame();
  assert.equal((h.updates.at(-1).match(/\S+/g) || []).length, 5);
  while (h.callbacks.size) h.frame();
  assert.equal(h.updates.at(-1), burst);
});

test('completion flushes buffered text and cancels pending work', () => {
  const h = harness();
  h.controller.setTarget('One two three');
  h.frame();
  h.controller.setTarget('One two three four', { finished: true });
  assert.equal(h.updates.at(-1), 'One two three four');
  assert.equal(h.callbacks.size, 0);
  assert.equal(h.cancelled.length, 1);
});

test('dispose cancels animation and ignores later updates', () => {
  const h = harness();
  h.controller.setTarget('Still generating words');
  h.controller.dispose();
  h.controller.setTarget('ignored', { finished: true });
  assert.equal(h.callbacks.size, 0);
  assert.deepEqual(h.updates, []);
});

test('reduced motion reveals every update immediately', () => {
  const h = harness({ reducedMotion: true });
  h.controller.setTarget('Accessible response');
  assert.deepEqual(h.updates, ['Accessible response']);
  assert.equal(h.callbacks.size, 0);
});
