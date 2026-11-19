# vo1dfull GitHub profile

## Install

1. Open `https://github.com/vo1dfull/vo1dfull`.
2. Upload the contents of this package to the repository root, preserving folders.
3. Commit to `main`.
4. Open **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions** if required by the publishing action.
5. Open **Actions → Update commit river → Run workflow** once.
6. After it succeeds, the README's commit river image will load from the `output` branch.

The workflow updates weekly and whenever the river generator changes. It uses the built-in `GITHUB_TOKEN`; no personal access token is needed.

## Notes

- The uploaded workstation photo is preserved unchanged at `assets/workstation.png`.
- The README keeps the contribution snake that you already generated at `output/github-snake.svg`.
- The river uses public GitHub commit contribution data for the last year. It is a compact SVG stream-style visualisation, not a live JavaScript chart.
- The two project tracks are intentionally descriptive placeholders until your Rust and cybersecurity repositories are ready.
