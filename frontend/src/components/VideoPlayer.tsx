/**
 * VideoPlayer — HTML5 video player with imperative seek API.
 *
 * Usage:
 *   const ref = useRef<VideoPlayerHandle>(null);
 *   ref.current?.seekTo(timestamp);
 *
 *   <VideoPlayer ref={ref} src={url} onTimeUpdate={setTime} />
 */

import { forwardRef, useImperativeHandle, useRef } from 'react';

export interface VideoPlayerHandle {
  seekTo: (timestamp: number) => void;
  play: () => void;
  pause: () => void;
  get currentTime(): number;
}

interface Props {
  src?: string;
  onTimeUpdate?: (time: number) => void;
  className?: string;
}

export const VideoPlayer = forwardRef<VideoPlayerHandle, Props>(
  function VideoPlayer({ src, onTimeUpdate, className }, ref) {
    const videoRef = useRef<HTMLVideoElement>(null);

    useImperativeHandle(ref, () => ({
      seekTo(timestamp: number) {
        if (videoRef.current) {
          videoRef.current.currentTime = timestamp;
        }
      },
      play() {
        videoRef.current?.play().catch(() => {});
      },
      pause() {
        videoRef.current?.pause();
      },
      get currentTime() {
        return videoRef.current?.currentTime ?? 0;
      },
    }));

    if (src) {
      return (
        <video
          ref={videoRef}
          src={src}
          controls
          className={className ?? 'w-full bg-black aspect-video border-2 border-bg-border'}
          onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
        />
      );
    }

    return (
      <div className="w-full aspect-video bg-bg-elevated border-2 border-bg-border flex flex-col items-center justify-center gap-3 text-center px-6">
        <span className="font-display text-5xl text-text-muted leading-none">▶</span>
        <p className="font-mono text-xs text-text-muted leading-relaxed">
          Video playback available with a real recording.
          <br />
          Timeline markers are still interactive.
        </p>
      </div>
    );
  }
);

export default VideoPlayer;
