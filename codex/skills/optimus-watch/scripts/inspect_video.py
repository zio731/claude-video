#!/usr/bin/env python3
"""Local-only video evidence, adapted from claude-video. MIT license in ../LICENSE."""
from __future__ import annotations
import argparse
import json
import math
import shutil
import tempfile
from pathlib import Path
from download import download, fetch_captions, is_url
from frames import (auto_fps_focus, extract_at_timestamps, extract_keyframes,
                    extract_scene_or_uniform, get_metadata, merge_frames,
                    parse_time, parse_timestamps, validate_controls)
from transcribe import filter_range, format_transcript, normalize_segments, parse_vtt
from runtime import configure_stdio


def read_transcript(path):
    p = Path(path).expanduser().resolve()
    if p.suffix.lower() == '.json':
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        return normalize_segments({'segments': data} if isinstance(data, list) else data)
    return parse_vtt(str(p))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source')
    ap.add_argument('--detail', choices=['balanced','efficient','transcript'], default='balanced')
    ap.add_argument('--max-frames', type=int, default=24)
    ap.add_argument('--resolution', type=int, default=960)
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--timestamps')
    ap.add_argument('--transcript')
    ap.add_argument('--sub-lang', default='auto')
    ap.add_argument('--no-dedup', action='store_true')
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    start, end = parse_time(args.start), parse_time(args.end)
    validate_controls(args.resolution, args.max_frames, start, end)
    cues = parse_timestamps(args.timestamps)
    missing = [x for x in ('ffmpeg','ffprobe') if not shutil.which(x)]
    if is_url(args.source) and not shutil.which('yt-dlp'):
        missing.append('yt-dlp')
    if missing:
        ap.error('Missing executable(s): ' + ', '.join(missing) + '. No installer was run.')
    parent = Path(args.out_dir).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='optimus-watch-', dir=parent))
    segments, captions, issues = [], {}, []
    provenance = 'unavailable; speech was not analyzed'
    if args.transcript:
        segments = read_transcript(args.transcript)
        provenance = 'user-supplied timestamped transcript'
    if is_url(args.source):
        captions = fetch_captions(args.source, work/'download', sub_lang=args.sub_lang)
        issues.extend(captions.get('errors', []))
        if not args.transcript and captions.get('subtitle_path'):
            segments = parse_vtt(captions['subtitle_path'])
            provenance = captions.get('caption_track') or 'native captions'
    frames, meta = [], {}
    need_video = args.detail != 'transcript' or bool(cues)
    if need_video:
        try:
            media = download(args.source, work/'download', **({'context':captions} if is_url(args.source) else {}))
            source = media['video_path']
            meta = get_metadata(source)
            duration = meta['duration_seconds']
            if start is not None and duration > 0 and start >= duration:
                ap.error('--start is past the end of the video')
            actual_end = min(end, duration) if end is not None and duration > 0 else end or duration
            if not meta.get('has_video'):
                issues.append('No video stream; no visual evidence.')
            else:
                selected = []
                if cues:
                    selected, _ = extract_at_timestamps(source, work/'frames', cues,
                        resolution=args.resolution, max_frames=args.max_frames,
                        start_seconds=start, end_seconds=actual_end)
                remaining = args.max_frames - len(selected)
                if remaining > 0 and args.detail != 'transcript':
                    kwargs = dict(resolution=args.resolution, max_frames=remaining,
                                  start_seconds=start, end_seconds=actual_end, dedup=not args.no_dedup)
                    if args.detail == 'efficient':
                        frames, _ = extract_keyframes(source, work/'frames', **kwargs)
                    else:
                        fps, target = auto_fps_focus(max(0,actual_end-(start or 0)), max_frames=remaining)
                        frames, _ = extract_scene_or_uniform(source, work/'frames', fps=fps, target_frames=target, **kwargs)
                frames = merge_frames(frames, selected)
        except SystemExit as exc:
            issues.append(str(exc))
    segments = filter_range(segments, start, end)
    report = {'source': args.source, 'work_dir': str(work), 'metadata': meta,
              'frames': frames, 'transcript_provenance': provenance, 'segments':segments,
              'issues':issues, 'cloud_uploads':False, 'automatic_asr':False}
    evidence = work/'evidence.json'
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('# Video evidence (local extraction)\n')
    print(f'Evidence file: {evidence}\n')
    print('## Frames\n')
    for f in frames:
        print(f"- {f['timestamp_seconds']:.3f}s: {f['path']}")
    if not frames:
        print('No visual evidence extracted.')
    print(f'\n## Transcript\n\nSource: {provenance}\n')
    print(format_transcript(segments) if segments else 'No transcript in the selected interval.')
    if issues:
        print('\n## Limitations\n')
        print('\n'.join('- '+s for s in issues))
    return 0 if (frames or segments) else 1


if __name__ == '__main__':
    configure_stdio()
    raise SystemExit(main())
