# Canvas Quiz Downloader

Standalone CLI located in this folder to minimize merge conflicts with top-level repo files.

## Setup
```bash
cp canvas_quiz_downloader/.env.example canvas_quiz_downloader/.env
# edit CANVAS_BASE_URL and CANVAS_API_TOKEN
```

## Run
```bash
python3 canvas_quiz_downloader/main.py --help
python3 canvas_quiz_downloader/main.py --debug
```

## Notes
- Output files are saved under `canvas_quiz_downloader/downloads/`.
- If you get `401 Unauthorized`, verify token validity and permissions.
