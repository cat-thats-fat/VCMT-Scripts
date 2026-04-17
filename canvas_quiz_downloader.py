#!/usr/bin/env python3
"""Interactive Canvas quiz report downloader.

Workflow:
1. Lists active courses (used as "cohorts").
2. Lets you pick a course.
3. Lists most recent quizzes for that course.
4. Creates a quiz report and polls until Canvas generates a downloadable file.
5. Downloads report into ./downloads.

Environment variables:
- CANVAS_BASE_URL (example: https://school.instructure.com)
- CANVAS_API_TOKEN
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


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

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _request(
        self,
        method: str,
        path_or_url: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        absolute_url: bool = False,
    ) -> tuple[Any, dict[str, str]]:
        if absolute_url:
            url = path_or_url
        else:
            url = urljoin(f"{self.base_url}/", path_or_url.lstrip("/"))

        if params:
            encoded_params = urlencode(params, doseq=True)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{encoded_params}"

        payload = None
        if data is not None:
            payload = urlencode(data, doseq=True).encode("utf-8")

        request = Request(url=url, method=method.upper(), headers=self._headers(), data=payload)

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                headers = {k: v for k, v in response.headers.items()}
                if not body:
                    return None, headers
                return json.loads(body), headers
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Canvas API HTTP {exc.code} on {url}: {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to connect to Canvas ({url}): {exc.reason}") from exc

    def _get_next_page_url(self, link_header: str | None) -> str | None:
        if not link_header:
            return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                match = re.search(r"<([^>]+)>", part)
                if match:
                    return match.group(1)
        return None

    def _paginated_get(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        all_items: list[dict[str, Any]] = []
        response, headers = self._request("GET", path, params=params)
        if isinstance(response, list):
            all_items.extend(response)
        elif isinstance(response, dict):
            # Some endpoints nest results.
            for value in response.values():
                if isinstance(value, list):
                    all_items.extend(value)

        next_url = self._get_next_page_url(headers.get("Link"))
        while next_url:
            response, headers = self._request("GET", next_url, absolute_url=True)
            if isinstance(response, list):
                all_items.extend(response)
            next_url = self._get_next_page_url(headers.get("Link"))

        return all_items

    def list_active_courses(self) -> list[dict[str, Any]]:
        return self._paginated_get(
            "/api/v1/courses",
            params={
                "enrollment_state": "active",
                "per_page": 100,
            },
        )

    def list_quizzes(self, course_id: int) -> list[dict[str, Any]]:
        return self._paginated_get(
            f"/api/v1/courses/{course_id}/quizzes",
            params={"per_page": 100},
        )

    def create_quiz_report(self, course_id: int, quiz_id: int, report_type: str = "student_analysis") -> dict[str, Any]:
        report, _ = self._request(
            "POST",
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/reports",
            data={
                "quiz_report[report_type]": report_type,
                "quiz_report[includes_all_versions]": "true",
            },
        )
        if not isinstance(report, dict):
            raise RuntimeError("Unexpected Canvas response while creating report.")
        return report

    def get_quiz_report(self, course_id: int, quiz_id: int, report_id: int) -> dict[str, Any]:
        report, _ = self._request(
            "GET",
            f"/api/v1/courses/{course_id}/quizzes/{quiz_id}/reports/{report_id}",
        )
        if not isinstance(report, dict):
            raise RuntimeError("Unexpected Canvas response while getting report.")
        return report

    def download_file(self, download_url: str, destination: Path) -> None:
        request = Request(download_url, method="GET", headers={"Authorization": f"Bearer {self.api_token}"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            destination.write_bytes(response.read())


def prompt_selection(items: list[dict[str, Any]], title_fn, subtitle_fn) -> dict[str, Any]:
    for idx, item in enumerate(items, start=1):
        print(f"[{idx}] {title_fn(item)}")
        subtitle = subtitle_fn(item)
        if subtitle:
            print(f"     {subtitle}")

    while True:
        raw = input("\nEnter selection number: ").strip()
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(items):
                return items[choice - 1]
        print("Invalid selection. Try again.")


def iso_to_local(dt_str: str | None) -> str:
    if not dt_str:
        return "(no date)"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return dt_str


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_") or "quiz_report"


def choose_course(courses: list[dict[str, Any]]) -> dict[str, Any]:
    active_named = [c for c in courses if c.get("name")]
    active_named.sort(key=lambda c: c.get("name", "").lower())
    print("\nAvailable cohorts (active Canvas courses):")
    return prompt_selection(
        active_named,
        title_fn=lambda c: f"{c.get('name')} (ID: {c.get('id')})",
        subtitle_fn=lambda c: c.get("course_code", ""),
    )


def choose_quiz(quizzes: list[dict[str, Any]]) -> dict[str, Any]:
    if not quizzes:
        raise RuntimeError("No quizzes found for this course.")

    def sort_key(quiz: dict[str, Any]) -> str:
        return quiz.get("due_at") or quiz.get("unlock_at") or quiz.get("updated_at") or ""

    sorted_quizzes = sorted(quizzes, key=sort_key, reverse=True)
    latest = sorted_quizzes[:20]

    print("\nMost recent quizzes (showing up to 20):")
    return prompt_selection(
        latest,
        title_fn=lambda q: f"{q.get('title', 'Untitled Quiz')} (ID: {q.get('id')})",
        subtitle_fn=lambda q: f"due: {iso_to_local(q.get('due_at'))} | updated: {iso_to_local(q.get('updated_at'))}",
    )


def main() -> int:
    base_url = os.environ.get("CANVAS_BASE_URL", "").strip()
    api_token = os.environ.get("CANVAS_API_TOKEN", "").strip()

    if not base_url:
        base_url = input("Canvas base URL (e.g., https://school.instructure.com): ").strip()
    if not api_token:
        api_token = input("Canvas API token: ").strip()

    if not base_url or not api_token:
        print("CANVAS_BASE_URL and CANVAS_API_TOKEN are required.")
        return 1

    client = CanvasClient(CanvasConfig(base_url=base_url, api_token=api_token))

    print("\nFetching active cohorts/courses from Canvas...")
    courses = client.list_active_courses()
    if not courses:
        raise RuntimeError("No active courses found for this account.")

    course = choose_course(courses)
    course_id = int(course["id"])

    print(f"\nFetching quizzes for course {course_id}...")
    quizzes = client.list_quizzes(course_id)
    quiz = choose_quiz(quizzes)
    quiz_id = int(quiz["id"])

    report_type = input("Report type [student_analysis/item_analysis] (default: student_analysis): ").strip() or "student_analysis"
    if report_type not in {"student_analysis", "item_analysis"}:
        raise RuntimeError("Invalid report type. Must be student_analysis or item_analysis.")

    print("\nCreating quiz report...")
    report = client.create_quiz_report(course_id=course_id, quiz_id=quiz_id, report_type=report_type)
    report_id = int(report["id"])
    print(f"Report created with ID {report_id}. Polling until file is ready...")

    poll_seconds = 2
    deadline = time.time() + 60 * 5
    file_obj = report.get("file")

    while not file_obj:
        if time.time() > deadline:
            raise RuntimeError("Timed out waiting for quiz report generation.")
        time.sleep(poll_seconds)
        report = client.get_quiz_report(course_id=course_id, quiz_id=quiz_id, report_id=report_id)
        file_obj = report.get("file")
        progress = report.get("progress_url", "")
        print(f"Still generating... progress endpoint: {progress or '(none)'}")

    download_url = file_obj.get("url")
    if not download_url:
        raise RuntimeError("Report completed but no file URL was returned.")

    downloads_dir = Path("downloads")
    downloads_dir.mkdir(parents=True, exist_ok=True)

    quiz_name = sanitize_filename(quiz.get("title", f"quiz_{quiz_id}"))
    default_name = file_obj.get("filename") or f"{quiz_name}_{report_type}.csv"
    output_path = downloads_dir / default_name

    print(f"\nDownloading report to: {output_path}")
    client.download_file(download_url=download_url, destination=output_path)
    print(f"Done. Saved: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(130)
    except Exception as exc:  # keep CLI errors friendly
        print(f"Error: {exc}")
        raise SystemExit(1)
