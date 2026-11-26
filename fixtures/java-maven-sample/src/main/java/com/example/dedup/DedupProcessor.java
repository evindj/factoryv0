package com.example.dedup;

import java.util.HashSet;
import java.util.Set;
import java.util.function.Consumer;

/**
 * Applies each request id's effect at most once. Implements the design verified in Dedup.tla
 * (Atomic = TRUE): ids are atomically claimed, then marked done after the effect is applied. A
 * duplicate of an in-flight id is not acknowledged (the client retries later).
 */
public final class DedupProcessor {

  /** Result of {@link #process}. */
  public enum Outcome {
    APPLIED,
    ALREADY_DONE,
    IN_PROGRESS;

    /** Whether the caller may acknowledge the request to the client. */
    public boolean acknowledge() {
      return this != IN_PROGRESS;
    }
  }

  private final Object lock = new Object();
  private final Set<String> claimed = new HashSet<>();
  private final Set<String> done = new HashSet<>();
  private final Consumer<String> onClaimed;

  public DedupProcessor() {
    this(id -> {});
  }

  /** {@code onClaimed} is a test seam that runs between claiming an id and applying it. */
  public DedupProcessor(Consumer<String> onClaimed) {
    this.onClaimed = onClaimed;
  }

  public Outcome process(String requestId, Runnable effect) {
    synchronized (lock) {
      if (done.contains(requestId)) {
        return Outcome.ALREADY_DONE;
      }
      if (!claimed.add(requestId)) {
        return Outcome.IN_PROGRESS;
      }
    }
    try {
      onClaimed.accept(requestId);
      effect.run();
    } catch (RuntimeException | Error e) {
      synchronized (lock) {
        claimed.remove(requestId);
      }
      throw e;
    }
    synchronized (lock) {
      done.add(requestId);
    }
    return Outcome.APPLIED;
  }
}
