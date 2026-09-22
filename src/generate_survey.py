"""Generate the weekly VLA (Vision-Language-Action) research news digest.

Called from the `weekly_survey.yml` GitHub Actions workflow. Builds a prompt
describing the desired digest, asks the Claude Code CLI to search the web and
write the digest, and saves the result under `surveys/`.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SURVEYS_DIR = REPO_ROOT / "surveys"
LOOKBACK_DAYS = 7

PROMPT_TEMPLATE = """\
過去1週間以内に公開された VLA (Vision-Language-Action) 関連のニュース・論文・製品発表を \
日英問わず検索し、各項目について (a) タイトル, (b) 分類(論文/製品/業界動向), \
(c) 1〜4項目の日本語箇条書き要約, (d) 出典リンク, を Markdown 箇条書きでまとめてください。\
読了1〜2分程度に収まる分量に絞ってください。

以下は過去{lookback_days}日分に既に取り上げたトピックです。これらと重複する話題は除外してください。

{past_digests}
"""

NO_PAST_DIGESTS_PLACEHOLDER = "(過去{lookback_days}日分の記事はありません)"


def main() -> None:
    past_digests = _load_recent_digests(SURVEYS_DIR, LOOKBACK_DAYS)
    prompt = _build_prompt(past_digests)
    digest = _run_claude(prompt)
    output_path = _write_digest(SURVEYS_DIR, digest)
    print(f"Wrote digest to {output_path}")


def _load_recent_digests(surveys_dir: Path, lookback_days: int) -> str:
    """Concatenate the content of digests published within the lookback window.

    Used to tell Claude which topics were already covered so it can exclude
    duplicates from the new digest.

    Parameters
    ----------
    surveys_dir : Path
        Directory containing past `YYYY-MM-DD.md` digest files.
    lookback_days : int
        Number of days back (inclusive of today) to consider.

    Returns
    -------
    str
        Concatenated Markdown content of recent digests, or a placeholder
        message if none exist.

    Reads:
      - surveys/YYYY-MM-DD.md
    """
    if not surveys_dir.is_dir():
        return NO_PAST_DIGESTS_PLACEHOLDER.format(lookback_days=lookback_days)

    cutoff_date = dt.date.today() - dt.timedelta(days=lookback_days)
    recent_contents: list[str] = []
    for digest_path in sorted(surveys_dir.glob("*.md")):
        digest_date = _parse_digest_date(digest_path)
        if digest_date is None or digest_date < cutoff_date:
            continue
        recent_contents.append(f"## {digest_path.name}\n\n{digest_path.read_text()}")

    if not recent_contents:
        return NO_PAST_DIGESTS_PLACEHOLDER.format(lookback_days=lookback_days)
    return "\n\n".join(recent_contents)


def _parse_digest_date(digest_path: Path) -> dt.date | None:
    """Parse the `YYYY-MM-DD` date encoded in a digest file name."""
    try:
        return dt.datetime.strptime(digest_path.stem, "%Y-%m-%d").date()
    except ValueError:
        return None


def _build_prompt(past_digests: str) -> str:
    """Assemble the instruction prompt sent to the Claude Code CLI."""
    return PROMPT_TEMPLATE.format(lookback_days=LOOKBACK_DAYS, past_digests=past_digests)


def _run_claude(prompt: str) -> str:
    """Invoke the Claude Code CLI to research and draft the digest.

    The prompt is passed as an argv element (no shell involved), so
    user-controlled content in `past_digests` cannot trigger shell
    injection.

    Parameters
    ----------
    prompt : str
        Instruction prompt describing the digest to generate.

    Returns
    -------
    str
        The digest text produced by Claude, on stdout.
    """
    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "WebSearch,WebFetch"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() + "\n"


def _write_digest(surveys_dir: Path, digest: str) -> Path:
    """Save the generated digest to today's dated file.

    Generates:
      - surveys/YYYY-MM-DD.md
    """
    surveys_dir.mkdir(parents=True, exist_ok=True)
    output_path = surveys_dir / f"{dt.date.today():%Y-%m-%d}.md"
    output_path.write_text(digest)
    return output_path


if __name__ == "__main__":
    main()
