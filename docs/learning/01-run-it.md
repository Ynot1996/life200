# Lesson 1: run it

Goal: see the project working on your machine.

Install uv, the tool that manages Python and packages:

```bash
brew install uv
```

Go to the project folder. Every command in these lessons is run from here; `make` only works
in the folder that contains the `Makefile`.

```bash
cd ~/Desktop/Applications/life200
```

Install the project's packages:

```bash
make install
```

Run all the checks:

```bash
make check
```

Start the API:

```bash
make dev
```

Leave that terminal open: the API only runs while `make dev` is running. Stop it with Ctrl+C.

Open http://localhost:8000/docs. Click `GET /health`, then **Try it out**, then **Execute**.
You should see `{"status": "ok", "version": "0.1.0"}`.

## What just happened

- `make` runs the short commands defined in `Makefile`. Open it; it is 20 lines.
- `make install` created `backend/.venv` (this project's private Python) from `backend/uv.lock`.
- `make dev` started a web server that reloads when you save a file.

## Try it

Install the commit hook, so formatting is fixed automatically on every `git commit`:

```bash
uv tool install pre-commit && pre-commit install
```

`backend/uv.lock` is already committed. CI needs it to install the same versions you have.
