/**
 * Reveals a growing text snapshot at word boundaries.
 *
 * The realtime layer intentionally remains unaware of this class: callers feed
 * it the latest durable/cumulative message text and it animates toward it.
 */
export class StreamingTextController {
  constructor({ onUpdate, schedule, cancel, prefersReducedMotion } = {}) {
    this.onUpdate = onUpdate || (() => {});
    this.schedule = schedule || ((callback, delay) => window.setTimeout(callback, delay));
    this.cancelSchedule = cancel || ((handle) => window.clearTimeout(handle));
    this.prefersReducedMotion = prefersReducedMotion || (() => (
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ));
    this.displayed = '';
    this.target = '';
    this._handle = null;
    this._disposed = false;
  }

  setTarget(text, { finished = false } = {}) {
    if (this._disposed) return;
    const next = text || '';

    // Some deployments forward raw response.text.delta chunks instead of a
    // cumulative snapshot. While streaming, append those chunks to the target
    // buffer; terminal snapshots always replace it authoritatively.
    const isDelta = !finished && this.target && !next.startsWith(this.target);
    const resolved = isDelta ? this.target + next : next;

    // A non-prefix update is a persisted-message reconciliation (or a server
    // correction), not a delta. Apply it atomically so stale text never leaks.
    if (!resolved.startsWith(this.displayed)) {
      this._publish(resolved);
    }
    this.target = resolved;

    if (finished || this.prefersReducedMotion()) {
      this.flush();
      return;
    }
    if (this.displayed !== this.target) this._ensureScheduled();
  }

  flush() {
    this._cancel();
    if (this.displayed !== this.target) this._publish(this.target);
  }

  dispose() {
    this._disposed = true;
    this._cancel();
  }

  _ensureScheduled() {
    if (this._handle !== null || this._disposed) return;
    const remaining = this.target.length - this.displayed.length;
    const delay = remaining > 240 ? 18 : remaining > 80 ? 30 : 52;
    this._handle = this.schedule(() => {
      this._handle = null;
      this._tick();
    }, delay);
  }

  _tick() {
    if (this._disposed || this.displayed === this.target) return;
    const remaining = this.target.slice(this.displayed.length);
    const wordCount = (remaining.match(/\S+/g) || []).length;
    const wordsThisFrame = wordCount > 30 ? 5 : wordCount > 12 ? 3 : wordCount > 5 ? 2 : 1;
    let end = 0;
    const chunks = remaining.matchAll(/\S+\s*|\s+/g);
    for (let index = 0; index < wordsThisFrame; index += 1) {
      const chunk = chunks.next();
      if (chunk.done) break;
      end = chunk.value.index + chunk.value[0].length;
    }
    // This preserves the exact Markdown source; only the visible prefix moves.
    this._publish(this.displayed + remaining.slice(0, end || remaining.length));
    if (this.displayed !== this.target) this._ensureScheduled();
  }

  _publish(value) {
    this.displayed = value;
    this.onUpdate(value);
  }

  _cancel() {
    if (this._handle === null) return;
    this.cancelSchedule(this._handle);
    this._handle = null;
  }
}
