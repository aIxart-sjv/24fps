/**
 * Pure functions mapping AI detection results onto exact video-player
 * positions and on-screen bounding-box rectangles. Extracted so this
 * frame/timestamp/coordinate math -- the part of "AI detection click ->
 * exact seek -> aligned overlay" most prone to silent, hard-to-notice bugs
 * -- is directly unit-testable, independent of DOM/video-element behavior.
 *
 * Every function here is honest about missing data: `null` return values
 * mean "no defensible mapping exists", never a fabricated 0/identity.
 */

import type { DisplayRect } from '../hooks/useVideoDisplayRect';
import type { RecordingResponse } from './apiTypes';

export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

/** A single-frame reference (an `AIResultResponse`, or a search sighting's
 * start point) -- the two fields this module actually needs. */
export interface FrameReference {
  frame_number: number;
  timestamp: string | null;
}

/**
 * Resolves the exact video-relative seek offset (seconds) for one
 * detection/sighting frame, in the preferred order from the task spec:
 *
 *   A. an already-anchored absolute timestamp (backend `timestamp`,
 *      relative to the recording's own normalized/original start), or
 *   B. `frame_number / recording.fps`, using the recording's *actual*
 *      source fps -- never a hardcoded 25/30/etc.
 *
 * Returns `null` (never 0) when neither is available: "do not invent a
 * timestamp."
 */
export function resolveSeekSeconds(
  frame: FrameReference,
  recording: Pick<RecordingResponse, 'start_normalized' | 'start_original' | 'fps'>
): number | null {
  const recordingStart = recording.start_normalized ?? recording.start_original;
  if (frame.timestamp && recordingStart) {
    const offsetSeconds =
      (new Date(frame.timestamp).getTime() - new Date(recordingStart).getTime()) / 1000;
    if (Number.isFinite(offsetSeconds) && offsetSeconds >= 0) return offsetSeconds;
  }
  if (recording.fps && recording.fps > 0) {
    return frame.frame_number / recording.fps;
  }
  return null;
}

/** A detection whose box is degenerate/out-of-bounds must be dropped, not
 * rendered (task: "If bounding box is malformed: do not crash"). */
export function hasUsableBox(bbox: BoundingBox): boolean {
  const { x_min, y_min, x_max, y_max } = bbox;
  return [x_min, y_min, x_max, y_max].every(Number.isFinite) && x_max > x_min && y_max > y_min;
}

/** How far (in frames, or frame-equivalent seconds when fps is unknown) a
 * detection sits from the current playback position -- used both to pick
 * "what's on screen right now" and, for a highlighted search result, to
 * find the nearest match immediately after a seek lands. */
export function frameDistance(
  frame: FrameReference,
  currentFrame: number | null,
  currentTime: number,
  recording: Pick<RecordingResponse, 'start_normalized' | 'start_original' | 'fps'>
): number {
  if (recording.fps && currentFrame !== null) {
    return Math.abs(frame.frame_number - currentFrame);
  }
  const recordingStart = recording.start_normalized ?? recording.start_original;
  if (frame.timestamp && recordingStart) {
    const offsetSeconds = (new Date(frame.timestamp).getTime() - new Date(recordingStart).getTime()) / 1000;
    return Math.abs(offsetSeconds - currentTime) * (recording.fps || 1);
  }
  return Infinity;
}

export interface OverlayRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Maps a detection's bounding box (in source-frame pixel coordinates) onto
 * the actual on-screen rectangle the video currently occupies, i.e.
 * normalizing by source dimensions and then scaling/offsetting by the
 * letterbox-aware `displayRect` (task: "The overlay must correspond to the
 * visible video pixels", "Do not simply position the box relative to the
 * outer card").
 *
 * Clamps the box to the source frame first (a detection recorded against
 * a slightly different frame size, or a box that runs off-frame, must not
 * render off the visible video) and returns `null` for a box that's
 * entirely degenerate after clamping -- never a crash, never a fabricated
 * rectangle.
 */
export function computeOverlayBoxRect(
  bbox: BoundingBox,
  sourceWidth: number,
  sourceHeight: number,
  displayRect: DisplayRect
): OverlayRect | null {
  const clampedXMin = Math.max(0, Math.min(bbox.x_min, sourceWidth));
  const clampedYMin = Math.max(0, Math.min(bbox.y_min, sourceHeight));
  const clampedXMax = Math.max(0, Math.min(bbox.x_max, sourceWidth));
  const clampedYMax = Math.max(0, Math.min(bbox.y_max, sourceHeight));
  if (clampedXMax <= clampedXMin || clampedYMax <= clampedYMin) return null;

  return {
    left: displayRect.left + (clampedXMin / sourceWidth) * displayRect.width,
    top: displayRect.top + (clampedYMin / sourceHeight) * displayRect.height,
    width: ((clampedXMax - clampedXMin) / sourceWidth) * displayRect.width,
    height: ((clampedYMax - clampedYMin) / sourceHeight) * displayRect.height,
  };
}
