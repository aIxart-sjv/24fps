import { useEffect, useState, type RefObject } from 'react';

export interface DisplayRect {
  left: number;
  top: number;
  width: number;
  height: number;
  /** The video's own intrinsic decoded resolution -- the authoritative
   * coordinate space AI detection bounding boxes are expressed in.
   * Preferred over `Recording.width/height` (which can be null/stale)
   * whenever the video element has already loaded metadata. */
  videoWidth: number;
  videoHeight: number;
}

/**
 * Tracks the actual on-screen rectangle a `<video>` element's decoded
 * frame occupies inside its container, accounting for `object-fit:
 * contain` letterboxing (task: "Handle cases where video aspect ratio
 * != container aspect ratio... Calculate the actual displayed video
 * rectangle").
 *
 * Recomputed on `loadedmetadata`, on any container/video resize (via
 * `ResizeObserver`), and on window resize -- never calculated once and
 * left fixed (task: "Do not calculate the box once and leave it
 * fixed").
 */
export function useVideoDisplayRect(videoRef: RefObject<HTMLVideoElement | null>): DisplayRect | null {
  const [rect, setRect] = useState<DisplayRect | null>(null);
  // `videoRef.current` is only populated once the <video> element actually
  // mounts, which in this app happens on a *later* render than the one
  // that first runs effects here (the player shows a loading state until
  // its preview-artifact fetch resolves). A plain `useEffect(..., [videoRef])`
  // would fire exactly once with `videoRef.current === null` and never
  // again, since the ref object's identity never changes -- silently
  // leaving `rect` (and therefore every bounding-box overlay) permanently
  // null. Mirroring the ref into state on every render lets the setup
  // effect below correctly re-run once the DOM node actually appears.
  const [videoEl, setVideoEl] = useState<HTMLVideoElement | null>(null);
  useEffect(() => {
    setVideoEl(videoRef.current);
  });

  useEffect(() => {
    const video = videoEl;
    if (!video) return undefined;

    const compute = () => {
      const containerWidth = video.clientWidth;
      const containerHeight = video.clientHeight;
      const videoWidth = video.videoWidth;
      const videoHeight = video.videoHeight;
      if (!containerWidth || !containerHeight || !videoWidth || !videoHeight) {
        setRect(null);
        return;
      }

      const containerRatio = containerWidth / containerHeight;
      const videoRatio = videoWidth / videoHeight;

      let width: number;
      let height: number;
      let left: number;
      let top: number;

      if (videoRatio > containerRatio) {
        // Video is relatively wider than the container -- it fills the
        // container's width, with letterbox bars above/below.
        width = containerWidth;
        height = containerWidth / videoRatio;
        left = 0;
        top = (containerHeight - height) / 2;
      } else {
        // Video is relatively taller -- fills height, letterbox on the sides.
        height = containerHeight;
        width = containerHeight * videoRatio;
        top = 0;
        left = (containerWidth - width) / 2;
      }

      setRect({ left, top, width, height, videoWidth, videoHeight });
    };

    compute();
    video.addEventListener('loadedmetadata', compute);
    // Not all browsers fire a 'resize' event on <video>, but Chrome does
    // when the intrinsic size becomes known -- harmless to also listen.
    video.addEventListener('resize', compute);

    const resizeObserver = new ResizeObserver(compute);
    resizeObserver.observe(video);
    window.addEventListener('resize', compute);

    return () => {
      video.removeEventListener('loadedmetadata', compute);
      video.removeEventListener('resize', compute);
      resizeObserver.disconnect();
      window.removeEventListener('resize', compute);
    };
  }, [videoEl]);

  return rect;
}
