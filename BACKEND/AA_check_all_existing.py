#!/usr/bin/env python3

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import aiohttp

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BLACKLIST_PATH = PROJECT_ROOT / "DATA" / "CHECK" / "BLACKLIST.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import SETTINGS as settings

DEFAULT_MAX_WORKERS = 30
DEFAULT_TIMEOUT_RETRIES = 2
DEFAULT_SEGMENT_SAMPLE_COUNT = 3
DEFAULT_MIN_SUCCESSFUL_SEGMENTS = 2
DEFAULT_MAX_SEGMENT_DURATION = 10.0


class SourceJob:
    def __init__(self, input_path: Path, output_path: Path) -> None:
        self.input_path = input_path
        self.output_path = output_path


class StreamCheckResult:
    def __init__(
        self,
        url: str,
        ok: bool,
        reason: str,
        elapsed: float,
        score: float = 0.0,
        throughput_ratio: float = 0.0,
        avg_segment_mbps: float = 0.0,
        required_mbps: float = 0.0,
        segments_ok: int = 0,
        segments_total: int = 0,
        jitter_ratio: float = 0.0,
        stall_count: int = 0,
        rebuffer_seconds: float = 0.0,
        avg_download_ratio: float = 0.0,
    ) -> None:
        self.url = url
        self.ok = ok
        self.reason = reason
        self.elapsed = elapsed
        self.score = score
        self.throughput_ratio = throughput_ratio
        self.avg_segment_mbps = avg_segment_mbps
        self.required_mbps = required_mbps
        self.segments_ok = segments_ok
        self.segments_total = segments_total
        self.jitter_ratio = jitter_ratio
        self.stall_count = stall_count
        self.rebuffer_seconds = rebuffer_seconds
        self.avg_download_ratio = avg_download_ratio


def _positive_int_setting(name: str, default: int) -> int:
    value = getattr(settings, name, default)
    if isinstance(value, int) and value > 0:
        return value
    return default


def _positive_float_setting(name: str, default: float) -> float:
    value: Any = getattr(settings, name, default)
    if isinstance(value, (int, float)) and float(value) > 0:
        return float(value)
    return default


def get_max_workers() -> int:
    return _positive_int_setting("CHECK_M3U8_MAX_WORKERS", DEFAULT_MAX_WORKERS)


def get_timeout_retries() -> int:
    return _positive_int_setting("CHECK_M3U8_TIMEOUT_RETRIES", DEFAULT_TIMEOUT_RETRIES)


def get_segment_sample_count() -> int:
    return _positive_int_setting("CHECK_M3U8_SEGMENT_SAMPLE_COUNT", DEFAULT_SEGMENT_SAMPLE_COUNT)


def get_min_successful_segments() -> int:
    return _positive_int_setting(
        "CHECK_M3U8_MIN_SUCCESSFUL_SEGMENTS", DEFAULT_MIN_SUCCESSFUL_SEGMENTS
    )


def get_max_segment_duration() -> float:
    return _positive_float_setting("CHECK_M3U8_MAX_SEGMENT_DURATION", DEFAULT_MAX_SEGMENT_DURATION)


def _path_from_setting(value: Any) -> Path:
    return Path(value).expanduser().resolve()


def _normalize_source_jobs(raw: Any) -> list[SourceJob]:
    jobs: list[SourceJob] = []
    if not isinstance(raw, list):
        return jobs
    for item in raw:
        if isinstance(item, str) and item.strip():
            input_path = _path_from_setting(item.strip())
            jobs.append(SourceJob(input_path=input_path, output_path=input_path))
            continue
        if isinstance(item, dict):
            input_value = item.get("input")
            if not isinstance(input_value, str) or not input_value.strip():
                continue
            output_value = item.get("output")
            input_path = _path_from_setting(input_value.strip())
            if isinstance(output_value, str) and output_value.strip():
                output_path = _path_from_setting(output_value.strip())
            else:
                output_path = input_path
            jobs.append(SourceJob(input_path=input_path, output_path=output_path))
    return jobs


def get_source_jobs() -> list[SourceJob]:
    configured = _normalize_source_jobs(getattr(settings, "CHECK_M3U8_SOURCE_JSON_FILES", None))
    if configured:
        return configured

    input_path = _path_from_setting(settings.CHECK_M3U8_JSON_FILE)
    output_value = getattr(settings, "CHECK_M3U8_OUTPUT_JSON_FILE", None)
    output_path = _path_from_setting(output_value) if output_value else input_path
    return [SourceJob(input_path=input_path, output_path=output_path)]


def load_urls_from_json(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    seen: set[str] = set()
    urls: list[str] = []
    for item in data:
        if not isinstance(item, str):
            continue
        url = item.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def save_urls_to_json(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=2)


def save_blacklist_with_merge(path: Path, failed_urls: list[str]) -> int:
    existing: list[str] = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            existing = [item.strip() for item in data if isinstance(item, str) and item.strip()]

    merged: list[str] = []
    seen: set[str] = set()
    for url in existing:
        if url in seen:
            continue
        seen.add(url)
        merged.append(url)

    added = 0
    for url in failed_urls:
        candidate = url.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        merged.append(candidate)
        added += 1

    save_urls_to_json(path, merged)
    return added


def _parse_attr_value(attr_line: str, key: str) -> str | None:
    marker = f"{key}="
    if marker not in attr_line:
        return None
    for part in attr_line.split(","):
        if part.startswith(marker):
            return part[len(marker):].strip().strip('"')
    return None


def _playlist_entries(playlist_text: str) -> list[str]:
    entries: list[str] = []
    for line in playlist_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def _segment_entries(playlist_text: str, playlist_url: str) -> list[tuple[str, float | None]]:
    segments: list[tuple[str, float | None]] = []
    pending_duration: float | None = None
    for raw_line in playlist_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            value = line.split(":", 1)[1].split(",", 1)[0].strip()
            try:
                pending_duration = float(value)
            except ValueError:
                pending_duration = None
            continue
        if line.startswith("#"):
            continue
        segments.append((urljoin(playlist_url, line), pending_duration))
        pending_duration = None
    return segments


async def _fetch_text(
    session: aiohttp.ClientSession, url: str, timeout_seconds: float, retries: int
) -> tuple[bool, str, float, str | None]:
    started = time.perf_counter()
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    timeout_count = 0
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, timeout=timeout) as response:
                elapsed = time.perf_counter() - started
                if response.status != 200:
                    return False, f"HTTP {response.status} (try {attempt}/{retries})", elapsed, None
                text = await response.text(errors="replace")
                return True, f"GET 200 (try {attempt}/{retries})", elapsed, text
        except asyncio.TimeoutError:
            timeout_count += 1
            continue
        except aiohttp.ClientError as exc:
            last_error = exc.__class__.__name__
            break
        except Exception:
            return False, "request error", time.perf_counter() - started, None
    elapsed = time.perf_counter() - started
    if timeout_count:
        return False, f"timeout ({timeout_count}/{retries})", elapsed, None
    if last_error:
        return False, f"client error ({last_error})", elapsed, None
    return False, "request error", elapsed, None


async def _download_segment(
    session: aiohttp.ClientSession, url: str, timeout_seconds: float, retries: int
) -> tuple[bool, str, float, int]:
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    for attempt in range(1, retries + 1):
        started = time.perf_counter()
        try:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return False, f"segment HTTP {response.status} (try {attempt}/{retries})", 0.0, 0
                payload = await response.read()
                elapsed = max(time.perf_counter() - started, 0.001)
                return True, "segment OK", elapsed, len(payload)
        except asyncio.TimeoutError:
            continue
        except aiohttp.ClientError as exc:
            return False, f"segment error ({exc.__class__.__name__})", 0.0, 0
        except Exception:
            return False, "segment request error", 0.0, 0
    return False, f"segment timeout ({retries}/{retries})", 0.0, 0


def _score_stream(
    success_ratio: float,
    throughput_ratio: float,
    jitter_ratio: float,
    latency_seconds: float,
    stall_count: int,
    rebuffer_seconds: float,
    avg_download_ratio: float,
) -> float:
    success_part = max(0.0, min(1.0, success_ratio)) * 50.0
    throughput_part = max(0.0, min(2.0, throughput_ratio)) / 2.0 * 35.0
    jitter_part = max(0.0, min(1.0, 1.0 - min(jitter_ratio, 1.0))) * 10.0
    latency_penalty = min(latency_seconds, 5.0) * 1.0
    rebuffer_penalty = min(rebuffer_seconds, 5.0) * 6.0
    stall_penalty = min(stall_count, 5) * 8.0
    # Download ratio models playback pressure: >1 means network is slower than media time.
    playback_pressure_penalty = max(0.0, avg_download_ratio - 1.0) * 20.0
    return max(
        0.0,
        min(
            100.0,
            success_part
            + throughput_part
            + jitter_part
            - latency_penalty
            - rebuffer_penalty
            - stall_penalty
            - playback_pressure_penalty,
        ),
    )


async def check_stream_quality(
    session: aiohttp.ClientSession,
    url: str,
    timeout_seconds: float,
    retries: int,
    segment_sample_count: int,
    min_successful_segments: int,
    max_segment_duration: float,
) -> StreamCheckResult:
    started = time.perf_counter()

    ok, reason, head_elapsed, playlist_text = await _fetch_text(session, url, timeout_seconds, retries)
    if not ok or not playlist_text:
        return StreamCheckResult(url=url, ok=False, reason=f"playlist: {reason}", elapsed=head_elapsed)

    media_playlist_url = url
    media_playlist_text = playlist_text
    required_bps = 0.0

    if "#EXT-X-STREAM-INF" in playlist_text:
        lines = [line.strip() for line in playlist_text.splitlines()]
        variants: list[tuple[float, str]] = []
        for idx, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF:"):
                continue
            attrs = line.split(":", 1)[1]
            bandwidth = _parse_attr_value(attrs, "BANDWIDTH")
            bw = float(bandwidth) if (bandwidth and bandwidth.isdigit()) else 0.0
            next_uri = ""
            for j in range(idx + 1, len(lines)):
                candidate = lines[j]
                if not candidate:
                    continue
                if candidate.startswith("#"):
                    break
                next_uri = candidate
                break
            if next_uri:
                variants.append((bw, urljoin(url, next_uri)))
        if not variants:
            return StreamCheckResult(
                url=url,
                ok=False,
                reason="master playlist without playable variants",
                elapsed=time.perf_counter() - started,
            )
        variants.sort(key=lambda item: item[0], reverse=True)
        required_bps = variants[0][0]
        media_playlist_url = variants[0][1]
        ok, reason, _, media_playlist_text = await _fetch_text(
            session, media_playlist_url, timeout_seconds, retries
        )
        if not ok or not media_playlist_text:
            return StreamCheckResult(
                url=url,
                ok=False,
                reason=f"variant playlist: {reason}",
                elapsed=time.perf_counter() - started,
            )

    segments = _segment_entries(media_playlist_text, media_playlist_url)
    if not segments:
        fallback_entries = _playlist_entries(media_playlist_text)
        segments = [(urljoin(media_playlist_url, entry), None) for entry in fallback_entries]
    if not segments:
        return StreamCheckResult(
            url=url,
            ok=False,
            reason="playlist has no media segments",
            elapsed=time.perf_counter() - started,
        )

    sampled = []
    for seg_url, seg_duration in segments:
        if len(sampled) >= segment_sample_count:
            break
        if seg_duration is not None and seg_duration > max_segment_duration:
            continue
        sampled.append((seg_url, seg_duration))
    if not sampled:
        sampled = segments[:segment_sample_count]

    segment_rates_bps: list[float] = []
    segment_durations: list[float] = []
    segment_bits: list[float] = []
    download_ratios: list[float] = []
    stall_count = 0
    rebuffer_seconds = 0.0
    buffered_seconds = 0.0
    playback_started = False
    errors: list[str] = []
    for seg_url, seg_duration in sampled:
        seg_ok, seg_reason, seg_elapsed, seg_bytes = await _download_segment(
            session, seg_url, timeout_seconds, retries
        )
        if not seg_ok or seg_bytes <= 0:
            errors.append(seg_reason)
            continue
        bps = (seg_bytes * 8.0) / seg_elapsed
        segment_rates_bps.append(bps)
        segment_bits.append(seg_bytes * 8.0)
        if seg_duration is not None and seg_duration > 0:
            segment_durations.append(seg_duration)
            download_ratios.append(seg_elapsed / seg_duration)
            if not playback_started:
                # Initial startup buffering should not be treated as rebuffering.
                buffered_seconds += seg_duration
                playback_started = True
                continue
            buffered_seconds -= seg_elapsed
            if buffered_seconds < 0:
                rebuffer_seconds += -buffered_seconds
                stall_count += 1
                buffered_seconds = 0.0
            buffered_seconds += seg_duration

    segments_total = len(sampled)
    segments_ok = len(segment_rates_bps)
    success_ratio = (segments_ok / segments_total) if segments_total else 0.0
    if segments_ok < min_successful_segments:
        reason_tail = errors[-1] if errors else "insufficient successful segments"
        return StreamCheckResult(
            url=url,
            ok=False,
            reason=f"segments {segments_ok}/{segments_total}; {reason_tail}",
            elapsed=time.perf_counter() - started,
            segments_ok=segments_ok,
            segments_total=segments_total,
        )

    avg_rate_bps = sum(segment_rates_bps) / segments_ok
    required_estimated_bps = 0.0
    if segment_durations and len(segment_durations) == len(segment_bits):
        total_dur = sum(segment_durations)
        if total_dur > 0:
            required_estimated_bps = sum(segment_bits) / total_dur
    if required_bps <= 0:
        required_bps = required_estimated_bps
    if required_bps <= 0:
        required_bps = avg_rate_bps

    throughput_ratio = avg_rate_bps / required_bps if required_bps > 0 else 0.0
    jitter_ratio = 0.0
    if len(segment_rates_bps) > 1 and avg_rate_bps > 0:
        jitter_ratio = statistics.pstdev(segment_rates_bps) / avg_rate_bps
    avg_download_ratio = sum(download_ratios) / len(download_ratios) if download_ratios else 0.0
    if stall_count > 1 or rebuffer_seconds > 1.0:
        return StreamCheckResult(
            url=url,
            ok=False,
            reason=f"stalls={stall_count}; rebuffer={rebuffer_seconds:.2f}s",
            elapsed=time.perf_counter() - started,
            throughput_ratio=throughput_ratio,
            avg_segment_mbps=avg_rate_bps / 1_000_000.0,
            required_mbps=required_bps / 1_000_000.0,
            segments_ok=segments_ok,
            segments_total=segments_total,
            jitter_ratio=jitter_ratio,
            stall_count=stall_count,
            rebuffer_seconds=rebuffer_seconds,
            avg_download_ratio=avg_download_ratio,
        )
    elapsed_total = time.perf_counter() - started
    score = _score_stream(
        success_ratio,
        throughput_ratio,
        jitter_ratio,
        head_elapsed,
        stall_count,
        rebuffer_seconds,
        avg_download_ratio,
    )
    risk_label = "low-risk"
    if stall_count > 0 or rebuffer_seconds > 0.25 or throughput_ratio < 1.1 or success_ratio < 1.0:
        risk_label = "high-risk"
    elif throughput_ratio < 1.35 or jitter_ratio > 0.35 or avg_download_ratio > 0.85:
        risk_label = "medium-risk"
    reason = (
        f"{risk_label}; seg_ok={segments_ok}/{segments_total}; "
        f"ratio={throughput_ratio:.2f}; jitter={jitter_ratio:.2f}; "
        f"stalls={stall_count}; rebuf={rebuffer_seconds:.2f}s; dl_ratio={avg_download_ratio:.2f}"
    )
    return StreamCheckResult(
        url=url,
        ok=True,
        reason=reason,
        elapsed=elapsed_total,
        score=score,
        throughput_ratio=throughput_ratio,
        avg_segment_mbps=avg_rate_bps / 1_000_000.0,
        required_mbps=required_bps / 1_000_000.0,
        segments_ok=segments_ok,
        segments_total=segments_total,
        jitter_ratio=jitter_ratio,
        stall_count=stall_count,
        rebuffer_seconds=rebuffer_seconds,
        avg_download_ratio=avg_download_ratio,
    )


async def run_checks(
    urls: list[str],
    timeout_seconds: float,
    max_workers: int,
    retries: int,
    segment_sample_count: int,
    min_successful_segments: int,
    max_segment_duration: float,
) -> list[StreamCheckResult]:
    headers = {
        "User-Agent": getattr(settings, "DEFAULT_USER_AGENT", "Mozilla/5.0"),
        "Accept": getattr(settings, "DEFAULT_ACCEPT_HEADER", "*/*"),
    }
    connector = aiohttp.TCPConnector(limit=max_workers, limit_per_host=max_workers)
    results: list[StreamCheckResult | None] = [None] * len(urls)
    done = 0

    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        async def run_one(index: int, url: str) -> tuple[int, StreamCheckResult]:
            row = await check_stream_quality(
                session=session,
                url=url,
                timeout_seconds=timeout_seconds,
                retries=retries,
                segment_sample_count=segment_sample_count,
                min_successful_segments=min_successful_segments,
                max_segment_duration=max_segment_duration,
            )
            return index, row

        total = len(urls)
        for start in range(0, total, max_workers):
            end = min(start + max_workers, total)
            batch_no = (start // max_workers) + 1
            batch_total = (total + max_workers - 1) // max_workers
            print(f"-- Batch {batch_no}/{batch_total}: items {start + 1}-{end} of {total} --")
            batch_tasks = [
                asyncio.create_task(run_one(index, urls[index]))
                for index in range(start, end)
            ]
            try:
                for completed in asyncio.as_completed(batch_tasks):
                    index, row = await completed
                    results[index] = row
                    done += 1
                    status = "OK" if row.ok else "FAIL"
                    print(
                        f"[{done}/{total}] {status} score={row.score:.1f} "
                        f"ratio={row.throughput_ratio:.2f} {row.url} ({row.reason}) [{row.elapsed:.2f}s]"
                    )
            except asyncio.CancelledError:
                for task in batch_tasks:
                    task.cancel()
                await asyncio.gather(*batch_tasks, return_exceptions=True)
                raise
            print(f"-- Batch {batch_no}/{batch_total} complete. Processed so far: {done}/{total} --")

    return [row for row in results if row is not None]


def main() -> int:
    total_started_at = time.perf_counter()

    try:
        reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure_stdout):
            reconfigure_stdout(encoding="utf-8", errors="replace")
    except Exception:
        pass

    timeout_seconds = _positive_float_setting("CHECK_M3U8_TIMEOUT_SECONDS", 5.0)
    retries = get_timeout_retries()
    max_workers_setting = get_max_workers()
    segment_sample_count = get_segment_sample_count()
    min_successful_segments = get_min_successful_segments()
    max_segment_duration = get_max_segment_duration()
    source_jobs = get_source_jobs()
    total_input_urls = 0
    total_output_urls = 0
    all_failed_urls: list[str] = []

    print(f"Source files to process: {len(source_jobs)}")
    print(
        f"Workers: up to {max_workers_setting}, timeout: {timeout_seconds}s, retries: {retries}, "
        f"segment sample: {segment_sample_count}, min successful: {min_successful_segments}, "
        f"max segment duration: {max_segment_duration}s"
    )

    for idx, job in enumerate(source_jobs, start=1):
        print(f"\n=== Source {idx}/{len(source_jobs)} ===")
        print(f"Input:  {job.input_path}")
        print(f"Output: {job.output_path}")
        if not job.input_path.exists():
            print("SKIP: input file not found.")
            continue

        try:
            urls = load_urls_from_json(job.input_path)
        except Exception as exc:
            print(f"SKIP: failed to read input JSON ({exc})")
            continue

        total = len(urls)
        total_input_urls += total
        max_workers = min(max_workers_setting, total or 1)
        print(f"Checking {total} URL(s)...")
        if total == 0:
            save_urls_to_json(job.output_path, [])
            print("No URLs found. Saved empty output.")
            continue

        try:
            completed_results = asyncio.run(
                run_checks(
                    urls=urls,
                    timeout_seconds=timeout_seconds,
                    max_workers=max_workers,
                    retries=retries,
                    segment_sample_count=segment_sample_count,
                    min_successful_segments=min_successful_segments,
                    max_segment_duration=max_segment_duration,
                )
            )
        except KeyboardInterrupt:
            print("\nStopped by user (Ctrl+C).")
            return 130
        processed_total = len(completed_results)
        if processed_total != total:
            print(f"WARNING: processed {processed_total} of {total} URL(s).")

        valid_rows = [row for row in completed_results if row.ok]
        failed_rows = [row for row in completed_results if not row.ok]
        valid_rows.sort(
            key=lambda row: (
                -row.score,
                -row.throughput_ratio,
                row.jitter_ratio,
                row.elapsed,
                row.url,
            )
        )
        sorted_urls = [row.url for row in valid_rows]
        all_failed_urls.extend(row.url for row in failed_rows)
        save_urls_to_json(job.output_path, sorted_urls)
        total_output_urls += len(sorted_urls)

        print(f"Processed: {processed_total}/{total}")
        print(f"Done: {len(valid_rows)}/{total} URL(s) passed playback-risk check.")
        print(f"Saved sorted working URLs to: {job.output_path}")
        if valid_rows:
            print("Top 10 by quality score:")
            for row in valid_rows[:10]:
                print(
                    f"- score={row.score:.1f}, ratio={row.throughput_ratio:.2f}, "
                    f"jitter={row.jitter_ratio:.2f}, url={row.url}"
                )

    added_to_blacklist = save_blacklist_with_merge(BLACKLIST_PATH, all_failed_urls)
    total_elapsed = time.perf_counter() - total_started_at
    print("\n=== Summary ===")
    print(f"Source files processed: {len(source_jobs)}")
    print(f"Input URLs total: {total_input_urls}")
    print(f"Working URLs total: {total_output_urls}")
    print(f"Failed URLs added to blacklist: {added_to_blacklist}")
    print(f"Blacklist saved to: {BLACKLIST_PATH}")
    print(f"Total elapsed: {total_elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
