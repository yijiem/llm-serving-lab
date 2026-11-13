# Reviewed submissions

This directory is intentionally empty of completed learner results. For each completed lab create a directory, for example `submissions/lab03/`, containing:

1. A report copied from `templates/report.md` and filled with your own observations.
2. The exact commands and non-sensitive environment settings.
3. Selected JSON evidence copied from `runs/` after review.
4. A summary and references to the code commit used.

Keep failed trials that affect your conclusion. Clearly distinguish fixture tests from live inference. Do not include credentials, personal prompts, private documents, model weights, binaries, or unnecessary logs. Validate the copied evidence too; copying or editing can introduce errors.

```sh
python3 -m serving_lab validate submissions/lab03/*.json --require-live
git diff --stat
git status --short
```

Then stage the specific intended files, inspect `git diff --cached`, and commit when ready. Avoid `git add -f runs/` and avoid publishing broad directory dumps.
