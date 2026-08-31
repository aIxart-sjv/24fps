import { describe, expect, it } from 'vitest';
import {
  computeOverlayBoxRect,
  frameDistance,
  hasUsableBox,
  resolveSeekSeconds,
  type BoundingBox,
} from './videoMapping';
import type { DisplayRect } from '../hooks/useVideoDisplayRect';
import type { RecordingResponse } from './apiTypes';

function makeRecording(overrides: Partial<RecordingResponse> = {}): Pick<
  RecordingResponse,
  'start_normalized' | 'start_original' | 'fps'
> {
  return {
    start_normalized: null,
    start_original: null,
    fps: null,
    ...overrides,
  };
}

describe('resolveSeekSeconds (frame -> exact video position)', () => {
  it('maps frame 0 to 0 seconds via fps', () => {
    expect(resolveSeekSeconds({ frame_number: 0, timestamp: null }, makeRecording({ fps: 25 }))).toBe(0);
  });

  it('maps frame 25 to 1.0s at 25fps', () => {
    expect(resolveSeekSeconds({ frame_number: 25, timestamp: null }, makeRecording({ fps: 25 }))).toBeCloseTo(1.0);
  });

  it('maps frame 50 to 2.0s at 25fps', () => {
    expect(resolveSeekSeconds({ frame_number: 50, timestamp: null }, makeRecording({ fps: 25 }))).toBeCloseTo(2.0);
  });

  it('maps frame 100 to 100/fps seconds at a non-standard 24fps source', () => {
    expect(resolveSeekSeconds({ frame_number: 100, timestamp: null }, makeRecording({ fps: 24 }))).toBeCloseTo(
      100 / 24
    );
  });

  it('maps an arbitrary frame (250) using the recording actual fps, never a hardcoded rate', () => {
    // Same frame_number, two different real source fps -> two different
    // correct answers. A hardcoded-fps implementation would fail one of these.
    expect(resolveSeekSeconds({ frame_number: 250, timestamp: null }, makeRecording({ fps: 30 }))).toBeCloseTo(
      250 / 30
    );
    expect(resolveSeekSeconds({ frame_number: 250, timestamp: null }, makeRecording({ fps: 12.5 }))).toBeCloseTo(
      250 / 12.5
    );
  });

  it('prefers an anchored backend timestamp over a frame/fps computation when both are available', () => {
    const recording = makeRecording({ start_normalized: '2026-01-01T00:00:00Z', fps: 25 });
    // frame_number implies 2s (50/25), but the real timestamp says 9s --
    // the timestamp must win (it's the authoritative, non-derived value).
    const seconds = resolveSeekSeconds(
      { frame_number: 50, timestamp: '2026-01-01T00:00:09Z' },
      recording
    );
    expect(seconds).toBeCloseTo(9);
  });

  it('supports a variable/non-integer fps source when no timestamp is available', () => {
    expect(resolveSeekSeconds({ frame_number: 47, timestamp: null }, makeRecording({ fps: 29.97 }))).toBeCloseTo(
      47 / 29.97
    );
  });

  it('returns null (never 0) when there is no timestamp and no fps', () => {
    expect(resolveSeekSeconds({ frame_number: 250, timestamp: null }, makeRecording())).toBeNull();
  });

  it('returns null when a timestamp exists but the recording has no anchoring start and no fps', () => {
    expect(
      resolveSeekSeconds({ frame_number: 250, timestamp: '2026-01-01T00:00:09Z' }, makeRecording())
    ).toBeNull();
  });

  it('falls back to frame/fps when a timestamp is present but the recording start is missing', () => {
    expect(
      resolveSeekSeconds(
        { frame_number: 50, timestamp: '2026-01-01T00:00:09Z' },
        makeRecording({ fps: 25 })
      )
    ).toBeCloseTo(2);
  });
});

describe('hasUsableBox', () => {
  const valid: BoundingBox = { x_min: 10, y_min: 10, x_max: 100, y_max: 100 };

  it('accepts a well-formed box', () => {
    expect(hasUsableBox(valid)).toBe(true);
  });

  it('rejects a box with x_max <= x_min', () => {
    expect(hasUsableBox({ ...valid, x_max: 10 })).toBe(false);
  });

  it('rejects a box with y_max <= y_min', () => {
    expect(hasUsableBox({ ...valid, y_max: 10 })).toBe(false);
  });

  it('rejects a box containing NaN/Infinity rather than crashing', () => {
    expect(hasUsableBox({ ...valid, x_min: NaN })).toBe(false);
    expect(hasUsableBox({ ...valid, y_max: Infinity })).toBe(false);
  });
});

describe('frameDistance', () => {
  it('is 0 for an exact frame match when fps is known', () => {
    expect(
      frameDistance({ frame_number: 250, timestamp: null }, 250, 10, makeRecording({ fps: 25 }))
    ).toBe(0);
  });

  it('grows with frame offset when fps is known', () => {
    expect(
      frameDistance({ frame_number: 260, timestamp: null }, 250, 10, makeRecording({ fps: 25 }))
    ).toBe(10);
  });

  it('is Infinity (never mistaken for a match) with no fps and no anchored timestamp', () => {
    expect(frameDistance({ frame_number: 250, timestamp: null }, null, 10, makeRecording())).toBe(Infinity);
  });
});

describe('computeOverlayBoxRect (source-frame pixels -> displayed video rectangle)', () => {
  const fullFrameRect: DisplayRect = { left: 0, top: 0, width: 1920, height: 1080, videoWidth: 1920, videoHeight: 1080 };

  it('maps a box 1:1 when the displayed rect matches the source resolution exactly', () => {
    const rect = computeOverlayBoxRect({ x_min: 100, y_min: 200, x_max: 300, y_max: 400 }, 1920, 1080, fullFrameRect);
    expect(rect).toEqual({ left: 100, top: 200, width: 200, height: 200 });
  });

  it('scales down proportionally for a resized (smaller on-screen) video', () => {
    // Half-size display of the same 1920x1080 source.
    const halfRect: DisplayRect = { left: 0, top: 0, width: 960, height: 540, videoWidth: 1920, videoHeight: 1080 };
    const rect = computeOverlayBoxRect({ x_min: 100, y_min: 200, x_max: 300, y_max: 400 }, 1920, 1080, halfRect);
    expect(rect).toEqual({ left: 50, top: 100, width: 100, height: 100 });
  });

  it('offsets by the letterbox bars when the video is pillarboxed inside a wider container', () => {
    // A 16:9 source letterboxed with vertical bars inside a squarer container.
    const pillarboxed: DisplayRect = { left: 200, top: 0, width: 800, height: 450, videoWidth: 1920, videoHeight: 1080 };
    const rect = computeOverlayBoxRect({ x_min: 0, y_min: 0, x_max: 1920, y_max: 1080 }, 1920, 1080, pillarboxed);
    expect(rect).toEqual({ left: 200, top: 0, width: 800, height: 450 });
  });

  it('clamps a box that runs past the source frame edge instead of rendering off-video', () => {
    const rect = computeOverlayBoxRect({ x_min: -50, y_min: -50, x_max: 2000, y_max: 1100 }, 1920, 1080, fullFrameRect);
    expect(rect).toEqual({ left: 0, top: 0, width: 1920, height: 1080 });
  });

  it('returns null for a degenerate box after clamping, rather than a zero-size or negative rectangle', () => {
    // Entirely outside the source frame on the right edge.
    const rect = computeOverlayBoxRect({ x_min: 2000, y_min: 2000, x_max: 2100, y_max: 2100 }, 1920, 1080, fullFrameRect);
    expect(rect).toBeNull();
  });
});
