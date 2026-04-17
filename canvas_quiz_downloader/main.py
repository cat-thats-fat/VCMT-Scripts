#!/usr/bin/env python3
"""Interactive Canvas quiz downloader.

What this tool can download for a selected quiz:
1) Quiz report CSV (student_analysis or item_analysis)
2) Per-student quiz submission JSON snapshots
3) Any attachment files referenced on each submission payload

Configuration sources (highest precedence first):
1) Shell environment variables
2) `.env` in current working directory
3) `.env` next to this script (inside canvas_quiz_downloader/)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

LOGGER = logging.getLogger("canvas_quiz_downloader")


@dataclass(slots=True)
class CanvasConfig:
    base_url: str
    api_token: str
    timeout_seconds: int = 30


class CanvasClient:
    def __init__(self, config: CanvasConfig) -> None:
        self.base_url = config.base_url.rstrip("/")
        self.api_token = config.api_token
        self.timeout_seconds = config.timeout_seconds

    def _headers(self, *, include_content_type: bool = True) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        if include_content_type:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        return headers

    def _request(
        self,
        method: str,
        path_or_url: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        *,
        absolute_url: bool = False,
    ) -> tuple[Any, dict[str, str]]:
        if absolute_url:
            url = path_or_url
        else:
            url = urljoin(f"{self.base_url}/", path_or_url.lstrip("/"))

        if params:
            encoded_params = urlencode(params, doseq=True)
            url = f"{url}{'&' if '?' in url else '?'}{encoded_params}"

        payload = urlencode(data, doseq=True).encode("utf-8") if data else None
        LOGGER.debug("HTTP %s %s", method.upper(), url)

        request = Request(url=url, method=method.upper(), headers=self._headers(), data=payload)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                headers = {k: v for k, v in response.headers.items()}
                if not raw:
                    return None, headers
                text = raw.decode("utf-8")
                return json.loads(text), headers
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401:
                raise RuntimeError(
                    "Canvas API returned 401 Unauthorized. "
                    "Check CANVAS_API_TOKEN in your environment/.env and ensure token has not expired. "
                    f"URL={url} RESPONSE={details}"
                ) from exc
            raise RuntimeError(f"Canvas API HTTP {exc.code} on {url}: {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to connect to Canvas ({url}): {exc.reason}") from exc

    @staticmethod
    def _next_link(link_header: str | None) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                match = re.search(r"<([^>]+)>", part)
                if match:
                    return match.group(1)
        return None

    def _extract_items(self, response: Any, item_key: str | None = None) -> list[dict[str, Any]]:
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        if isinstance(response, dict):
            if item_key and isinstance(response.get(item_key), list):
                return [item for item in response[item_key] if isinstance(item, dict)]
            for value in response.values():
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _paginated_get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        item_key: str | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        response, headers = self._request("GET", path, params=params)
        items.extend(self._extract_items(response, item_key=item_key))

        next_url = self._next_link(headers.get("Link"))
        while next_url:
            LOGGER.debug("Following pagination link: %s", next_url)
            response, headers = self._request("GET", next_url, absolute_url=True)
            items.extend(self._extract_items(response, item_key=item_key))
            next_url = self._next_link(headers.get("Link"))
        return items

    def list_active_courses(self) -> list[dict[str, Any]]:
        return self._paginated_get(
            "/api/v1/courses",
            params={"enrollment_state": "active", "per_page": 100},
        )

    def list_quizzes(self, course_id: int) -> list[dict[str, Any]]:
        return self._paginated_get(
            f"/api/v1/courses/{course_id}/quizzes",
            params={"per_page": 100},
        )

    def list_quiz_submissions(self, course_id: int, quiz_id: int) -> list[dict[str, Any]]:
        return self._paginated_get(
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/submissions",
            params={"include[]": ["user", "submission"], "per_page": 100},
            item_key="quiz_submissions",
        )

    def get_quiz_submission(self, course_id: int, quiz_id: int, submission_id: int) -> dict[str, Any]:
        submission, _ = self._request(
            "GET",
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/submissions/{submission_id}",
            params={"include[]": ["user", "submission"]},
        )
        if not isinstance(submission, dict):
            raise RuntimeError(f"Unexpected payload for submission {submission_id}.")
        return submission

    def create_quiz_report(self, course_id: int, quiz_id: int, report_type: str) -> dict[str, Any]:
        report, _ = self._request(
            "POST",
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/reports",
            data={
                "quiz_report[report_type]": report_type,
                "quiz_report[includes_all_versions]": "true",
            },
        )
        if not isinstance(report, dict):
            raise RuntimeError("Unexpected Canvas response while creating quiz report.")
        return report

    def get_quiz_report(self, course_id: int, quiz_id: int, report_id: int) -> dict[str, Any]:
        report, _ = self._request(
            "GET",
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/reports/{report_id}",
        )
        if not isinstance(report, dict):
            raise RuntimeError("Unexpected Canvas response while fetching quiz report.")
        return report

    def download_binary(self, url: str, destination: Path) -> None:
        LOGGER.debug("Downloading file from %s -> %s", url, destination)
        request = Request(url, method="GET", headers=self._headers(include_content_type=False))
        with urlopen(request, timeout=self.timeout_seconds) as response:
            destination.write_bytes(response.read())


def configure_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def read_dotenv_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def load_env_from_default_locations() -> tuple[dict[str, str], list[Path]]:
    loaded: dict[str, str] = {}
    used_paths: list[Path] = []
    script_dir = Path(__file__).resolve().parent
    candidate_paths = [Path.cwd() / ".env", script_dir / ".env"]

    for env_path in candidate_paths:
        values = read_dotenv_file(env_path)
        if not values:
            continue
        for key, value in values.items():
            if key not in os.environ:
                os.environ[key] = value
                loaded[key] = value
        used_paths.append(env_path)

    return loaded, used_paths


def mask_token(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]}"


def iso_to_local(raw: str | None) -> str:
    if not raw:
        return "(no date)"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    return dt.strftime("%Y-%m-%d %H:%M")


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._") or "unnamed"


def prompt_selection(items: list[dict[str, Any]], title_fn, subtitle_fn) -> dict[str, Any]:
    for idx, item in enumerate(items, start=1):
        print(f"[{idx}] {title_fn(item)}")
        subtitle = subtitle_fn(item)
        if subtitle:
            print(f"     {subtitle}")

    while True:
        raw = input("\nEnter selection number: ").strip()
        if raw.isdigit():
            chosen_idx = int(raw)
            if 1 <= chosen_idx <= len(items):
                return items[chosen_idx - 1]
        print("Invalid selection. Try again.")


def choose_course(courses: list[dict[str, Any]]) -> dict[str, Any]:
    named = [course for course in courses if course.get("name")]
    named.sort(key=lambda c: str(c.get("name", "")).lower())
    if not named:
        raise RuntimeError("No active named courses found.")

    print("\nAvailable cohorts (active courses):")
    return prompt_selection(
        named,
        title_fn=lambda c: f"{c.get('name')} (ID: {c.get('id')})",
        subtitle_fn=lambda c: c.get("course_code", ""),
    )


def choose_quiz(quizzes: list[dict[str, Any]]) -> dict[str, Any]:
    if not quizzes:
        raise RuntimeError("No quizzes found for this course.")

    def date_key(q: dict[str, Any]) -> str:
        return str(q.get("due_at") or q.get("unlock_at") or q.get("updated_at") or "")

    recent = sorted(quizzes, key=date_key, reverse=True)[:20]
    print("\nMost recent quizzes (up to 20):")
    return prompt_selection(
        recent,
        title_fn=lambda q: f"{q.get('title', 'Untitled Quiz')} (ID: {q.get('id')})",
        subtitle_fn=lambda q: f"due: {iso_to_local(q.get('due_at'))} | updated: {iso_to_local(q.get('updated_at'))}",
    )


def wait_for_report_file(client: CanvasClient, course_id: int, quiz_id: int, report: dict[str, Any]) -> dict[str, Any]:
    report_id = int(report["id"])
    deadline = time.time() + (5 * 60)

    while not report.get("file"):
        if time.time() > deadline:
            raise RuntimeError("Timed out waiting for report generation.")
        time.sleep(2)
        report = client.get_quiz_report(course_id=course_id, quiz_id=quiz_id, report_id=report_id)
        LOGGER.info("Still generating report... progress_url=%s", report.get("progress_url") or "(none)")

    return report


def download_report(client: CanvasClient, course_id: int, quiz: dict[str, Any], destination_root: Path) -> Path:
    quiz_id = int(quiz["id"])
    report_type = input("Report type [student_analysis/item_analysis] (default: student_analysis): ").strip() or "student_analysis"
    if report_type not in {"student_analysis", "item_analysis"}:
        raise RuntimeError("Invalid report type; use student_analysis or item_analysis.")

    LOGGER.info("Creating quiz report...")
    report = client.create_quiz_report(course_id=course_id, quiz_id=quiz_id, report_type=report_type)
    LOGGER.info("Report requested (id=%s)", report.get("id"))
    report = wait_for_report_file(client, course_id=course_id, quiz_id=quiz_id, report=report)

    file_obj = report.get("file") or {}
    file_url = file_obj.get("url")
    if not file_url:
        raise RuntimeError("Report completed but no file URL was returned.")

    filename = file_obj.get("filename") or f"{sanitize_filename(quiz.get('title', f'quiz_{quiz_id}'))}_{report_type}.csv"
    report_path = destination_root / sanitize_filename(filename)
    client.download_binary(file_url, report_path)
    LOGGER.info("Downloaded report: %s", report_path)
    return report_path


def collect_submission_attachments(submission_payload: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    nested_submission = submission_payload.get("submission")
    if isinstance(nested_submission, dict):
        nested_attachments = nested_submission.get("attachments")
        if isinstance(nested_attachments, list):
            attachments.extend([a for a in nested_attachments if isinstance(a, dict)])

    top_level = submission_payload.get("attachments")
    if isinstance(top_level, list):
        attachments.extend([a for a in top_level if isinstance(a, dict)])

    deduped: dict[str, dict[str, Any]] = {}
    for item in attachments:
        key = str(item.get("id") or item.get("url") or item.get("filename") or len(deduped))
        deduped[key] = item
    return list(deduped.values())


def download_all_submission_data(
    client: CanvasClient,
    course_id: int,
    quiz: dict[str, Any],
    destination_root: Path,
) -> tuple[int, int]:
    quiz_id = int(quiz["id"])
    submissions = client.list_quiz_submissions(course_id=course_id, quiz_id=quiz_id)
    if not submissions:
        LOGGER.warning("No quiz submissions returned for this quiz.")
        return 0, 0

    submission_dir = destination_root / "submissions"
    files_dir = destination_root / "submission_files"
    submission_dir.mkdir(parents=True, exist_ok=True)
    files_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files = 0
    for idx, s in enumerate(submissions, start=1):
        submission_id = s.get("id")
        if submission_id is None:
            LOGGER.debug("Skipping submission with no id: %s", s)
            continue

        LOGGER.info("Fetching submission %s/%s (id=%s)", idx, len(submissions), submission_id)
        details = client.get_quiz_submission(course_id=course_id, quiz_id=quiz_id, submission_id=int(submission_id))

        user_id = details.get("user_id") or s.get("user_id") or "unknown_user"
        attempt = details.get("attempt") or s.get("attempt") or "attempt"
        state = (details.get("workflow_state") or s.get("workflow_state") or "unknown").lower()

        snapshot_name = f"user_{user_id}_submission_{submission_id}_attempt_{attempt}_{state}.json"
        snapshot_path = submission_dir / sanitize_filename(snapshot_name)
        snapshot_path.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")

        for attachment in collect_submission_attachments(details):
            url = attachment.get("url")
            if not url:
                continue
            filename = sanitize_filename(str(attachment.get("filename") or f"attachment_{attachment.get('id', 'file')}"))
            output_path = files_dir / f"user_{user_id}_{filename}"
            try:
                client.download_binary(url=url, destination=output_path)
                downloaded_files += 1
            except Exception as exc:
                LOGGER.warning("Failed to download attachment for submission %s: %s", submission_id, exc)

    return len(submissions), downloaded_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Canvas quiz reports + student submission artifacts")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_logging(debug=args.debug)

    loaded_values, used_env_paths = load_env_from_default_locations()
    if used_env_paths:
        LOGGER.info("Loaded .env values from: %s", ", ".join(str(path) for path in used_env_paths))
    if loaded_values:
        LOGGER.debug("Keys loaded from .env: %s", sorted(loaded_values.keys()))

    base_url = os.environ.get("CANVAS_BASE_URL", "").strip()
    api_token = os.environ.get("CANVAS_API_TOKEN", "").strip()

    if base_url:
        LOGGER.info("Canvas base URL: %s", base_url)
    if api_token:
        LOGGER.info("Canvas API token detected: %s", mask_token(api_token))

    if not base_url:
        base_url = input("Canvas base URL (e.g., https://school.instructure.com): ").strip()
    if not api_token:
        api_token = input("Canvas API token: ").strip()

    if not base_url or not api_token:
        print("CANVAS_BASE_URL and CANVAS_API_TOKEN are required.")
        print("Tip: create canvas_quiz_downloader/.env with those values.")
        return 1

    client = CanvasClient(CanvasConfig(base_url=base_url, api_token=api_token))

    LOGGER.info("Fetching active cohorts/courses...")
    course = choose_course(client.list_active_courses())
    course_id = int(course["id"])

    LOGGER.info("Fetching quizzes for course %s...", course_id)
    quiz = choose_quiz(client.list_quizzes(course_id))

    script_dir = Path(__file__).resolve().parent
    output_root = script_dir / "downloads"
    folder_name = sanitize_filename(f"course_{course_id}_{quiz.get('id')}_{quiz.get('title', 'quiz')}")
    destination_root = output_root / folder_name
    destination_root.mkdir(parents=True, exist_ok=True)

    report_path = download_report(client=client, course_id=course_id, quiz=quiz, destination_root=destination_root)

    LOGGER.info("Downloading each student submission payload (and any attachments)...")
    submission_count, attachment_count = download_all_submission_data(
        client=client,
        course_id=course_id,
        quiz=quiz,
        destination_root=destination_root,
    )

    print("\nDone.")
    print(f"Report: {report_path.resolve()}")
    print(f"Submission snapshots saved: {submission_count}")
    print(f"Attachment files downloaded: {attachment_count}")
    print(f"Output folder: {destination_root.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
    except Exception as exc:
        LOGGER.exception("Unhandled error")
        print(f"Error: {exc}")
        raise SystemExit(1)
