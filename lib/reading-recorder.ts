export type ReadingCheckpoint = { current_page: number; seconds: number; request_id: string };

/** Foreground elapsed time and an ordered, retryable checkpoint outbox. */
export class ReadingRecorder {
  queue: ReadingCheckpoint[];
  page: number;
  private milliseconds = 0;
  private last: number;
  private running = false;
  private sending = false;
  private failed = false;
  private rejected: ReadingCheckpoint | null = null;

  constructor(private options: {
    page: number; pending: ReadingCheckpoint[]; now: () => number; id: () => string;
    active: () => boolean; send: (data: ReadingCheckpoint) => Promise<unknown>;
    persist: (pending: ReadingCheckpoint[]) => void;
    status: (error: boolean, rejected?: ReadingCheckpoint) => void;
    maxPage?: number; unavailable?: (error: unknown) => boolean;
  }) {
    this.queue = options.pending;
    this.page = Math.max(1, Math.min(this.queue.at(-1)?.current_page ?? options.page,
      options.maxPage ?? Infinity)); // Clamp the displayed position, never the queued payload.
    this.last = options.now();
  }

  tick() {
    const now = this.options.now();
    // Long timer gaps indicate suspension/sleep, not continuous observed reading.
    if (this.running && this.options.active()) this.milliseconds += Math.min(2000, Math.max(0, now - this.last));
    this.last = now;
  }

  visible(value: boolean) {
    this.tick();
    this.running = value;
    if (!value) this.checkpoint();
  }

  turn(page: number) {
    if (page === this.page) return;
    this.tick();
    this.checkpoint();
    this.page = page;
    this.checkpoint(true);
  }

  checkpoint(position = false) {
    this.tick();
    if (!this.options.active()) return;
    const seconds = Math.floor(this.milliseconds / 1000);
    if (seconds || position) {
      this.milliseconds -= seconds * 1000;
      this.queue.push({ current_page: this.page, seconds, request_id: this.options.id() });
      this.options.persist(this.queue);
    }
    if (!this.failed) void this.drain();
  }

  retry() { this.failed = false; void this.drain(); }

  discardUnavailable() {
    // Only an explicitly rejected head can be discarded, never an in-flight or generic failed save.
    if (this.sending || !this.options.active() || !this.rejected || this.queue[0] !== this.rejected) return;
    this.queue.shift();
    this.rejected = null;
    this.options.persist(this.queue);
    this.options.status(false);
    this.retry();
  }

  private async drain() {
    if (this.sending || !this.options.active()) return;
    this.sending = true;
    try {
      while (this.queue.length && this.options.active()) {
        await this.options.send(this.queue[0]);
        this.queue.shift();
        this.rejected = null;
        this.options.persist(this.queue);
        this.options.status(false);
      }
    } catch (error) {
      this.failed = true;
      this.rejected = this.options.unavailable?.(error) ? this.queue[0] : null;
      this.options.status(true, this.rejected ?? undefined);
    } finally { this.sending = false; }
  }
}
