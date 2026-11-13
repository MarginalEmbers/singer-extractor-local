export const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

export function formatTime(value, decimal = false) {
  const seconds = Math.max(0, Number.isFinite(value) ? value : 0);
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return String(minutes).padStart(2, "0") + ":" + String(remainder).padStart(2, "0") +
    (decimal ? "." + Math.floor((seconds % 1) * 10 + 0.00001) : "");
}

export function selectionBetween(anchor, cursor, duration, minimum = 0.01) {
  const low = clamp(Math.min(anchor, cursor), 0, Math.max(0, duration - minimum));
  return [low, clamp(Math.max(anchor, cursor), low + minimum, duration)];
}

export function isCovered(coverage, start, end, tolerance = 0.0001) {
  return coverage.some(([a, b]) => a <= start + tolerance && b >= end - tolerance);
}

export function visibleWindow(duration, zoom, left) {
  const span = duration / clamp(zoom, 1, 32);
  return { start: clamp(left, 0, Math.max(0, duration - span)), span };
}

/** One playback clock for every track. Switching a buffer reuses its exact time and bounds. */
export class AudioTransport {
  constructor(contextFactory = () => new AudioContext()) {
    this.contextFactory = contextFactory;
    this.context = null;
    this.node = null;
    this.gainNode = null;
    this.volume = 0.75;
    this.offset = 0;
    this.end = 0;
    this.loopStart = 0;
    this.loop = false;
    this.playing = false;
    this.startedAt = 0;
    this.serial = 0;
    this.onEnded = null;
  }

  getContext() {
    if (!this.context) {
      this.context = this.contextFactory();
      this.gainNode = this.context.createGain();
      this.gainNode.gain.value = this.volume;
      this.gainNode.connect(this.context.destination);
    }
    return this.context;
  }

  setVolume(value) {
    this.volume = clamp(value, 0, 1);
    if (this.gainNode) this.gainNode.gain.value = this.volume;
  }

  position() {
    if (!this.playing) return this.offset;
    const raw = this.offset + this.context.currentTime - this.startedAt;
    if (this.loop && raw >= this.end) {
      return this.loopStart + (raw - this.loopStart) % (this.end - this.loopStart);
    }
    return Math.min(raw, this.end);
  }

  detach() {
    if (this.node) {
      this.node.onended = null;
      try { this.node.stop(); } catch { /* Already ended. */ }
      this.node.disconnect();
      this.node = null;
    }
  }

  pause() {
    this.offset = this.position();
    this.serial++;
    this.detach();
    this.playing = false;
    return this.offset;
  }

  async play(buffer, position, end = buffer.duration, loop = false, loopStart = position) {
    const context = this.getContext();
    const token = ++this.serial;
    this.detach();
    this.playing = false;
    await context.resume();
    if (token !== this.serial) return;
    const finish = clamp(end, 0, buffer.duration);
    const begin = clamp(position, 0, finish);
    if (finish - begin < 0.00001) { this.offset = finish; return; }
    const node = context.createBufferSource();
    node.buffer = buffer;
    node.loop = loop;
    node.loopStart = clamp(loopStart, 0, finish - 0.00001);
    node.loopEnd = finish;
    node.connect(this.gainNode);
    this.node = node;
    this.offset = begin;
    this.end = finish;
    this.loopStart = node.loopStart;
    this.loop = loop;
    this.startedAt = context.currentTime;
    this.playing = true;
    node.onended = () => {
      if (token !== this.serial) return;
      this.offset = finish;
      this.playing = false;
      this.node = null;
      this.onEnded?.();
    };
    node.start(0, begin);
    if (!loop) node.stop(context.currentTime + finish - begin);
  }

  async switchBuffer(buffer) {
    const position = this.position();
    const wasPlaying = this.playing;
    const end = this.end, loop = this.loop, loopStart = this.loopStart;
    if (wasPlaying) await this.play(buffer, position, end, loop, loopStart);
    else this.offset = position;
    return position;
  }
}
