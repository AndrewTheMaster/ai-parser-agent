"""Typer CLI: run-extract, run-lookup, run-all."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from app.config import load_pipeline_config
from app.graphs.legal_terms_graph import run_extract_only, run_full_pipeline, run_lookup_only
from app.reports.export_results import export_json, export_xlsx

app = typer.Typer(no_args_is_help=True, help="Legal terms agent (LangGraph + Black's PDF index).")


def _resolve_dictionary_paths(dictionary_dir: Path, pattern: str) -> list[Path]:
    if not dictionary_dir.exists() or not dictionary_dir.is_dir():
        raise typer.BadParameter(f"Dictionary directory does not exist: {dictionary_dir}")
    paths = sorted(dictionary_dir.glob(pattern))
    return [p for p in paths if p.is_file()]


@app.command("run-extract")
def run_extract(
    input_path: list[Path] = typer.Option(..., "--input", "-i", help="DOCX/PDF textbook file(s)."),
    out_json: Optional[Path] = typer.Option(None, "--out-json", help="Write extracted terms JSON."),
) -> None:
    """Extract term candidates from textbook pages (requires local LLM)."""
    terms = run_extract_only(input_paths=input_path, cfg=load_pipeline_config())
    typer.echo(f"Extracted {len(terms)} term candidates.")
    if out_json:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps([t.model_dump() for t in terms], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        typer.echo(f"Wrote {out_json}")


@app.command("run-lookup")
def run_lookup(
    terms_file: Path = typer.Option(..., "--terms", "-t", help="Plain text list / bullet list of terms."),
    dictionary_dir: Path = typer.Option(
        Path("."),
        "--dictionary-dir",
        help="Directory containing dictionary PDF files.",
    ),
    dictionary_glob: str = typer.Option(
        "*.pdf",
        "--dictionary-glob",
        help="Glob pattern applied inside --dictionary-dir.",
    ),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
    index_cache: Optional[Path] = typer.Option(
        Path(".cache/blacks_index.pkl"),
        "--index-cache",
        help="Pickle cache for dictionary index (speeds up repeat runs).",
    ),
    no_index_cache: bool = typer.Option(False, "--no-index-cache", help="Disable reading/writing cache."),
    enable_ru: bool = typer.Option(False, "--enable-ru", help="Optional RU law mapping + translation."),
    ru_corpus: list[Path] = typer.Option(
        [],
        "--ru-corpus",
        help="Optional .txt files with Russian legal texts for mini-RAG.",
    ),
) -> None:
    """Lookup definitions for a fixed term list against dictionary PDFs."""
    dict_paths = _resolve_dictionary_paths(dictionary_dir, dictionary_glob)
    if not dict_paths:
        raise typer.BadParameter(
            f"No dictionary PDFs matched glob {dictionary_glob!r} in {dictionary_dir}"
        )
    cache_path = None if no_index_cache else index_cache
    results = run_lookup_only(
        terms_file=terms_file,
        dictionary_paths=dict_paths,
        output_dir=output_dir,
        enable_ru_law=enable_ru,
        ru_corpus_paths=ru_corpus or None,
        index_cache_path=cache_path,
        cfg=load_pipeline_config(),
    )
    typer.echo(
        f"Wrote {output_dir / 'results.json'}, {output_dir / 'results.xlsx'}, "
        f"{output_dir / 'results_human.xlsx'} ({len(results)} rows)."
    )


@app.command("run-all")
def run_all(
    input_path: list[Path] = typer.Option(
        [],
        "--input",
        "-i",
        help="DOCX/PDF textbook file(s). Optional if --terms is provided.",
    ),
    terms_file: Optional[Path] = typer.Option(None, "--terms", "-t", help="Optional fixed term list file."),
    dictionary_dir: Path = typer.Option(
        Path("."),
        "--dictionary-dir",
        help="Directory containing dictionary PDF files.",
    ),
    dictionary_glob: str = typer.Option(
        "*.pdf",
        "--dictionary-glob",
        help="Glob pattern applied inside --dictionary-dir.",
    ),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
    index_cache: Optional[Path] = typer.Option(
        Path(".cache/blacks_index.pkl"),
        "--index-cache",
        help="Pickle cache for dictionary index.",
    ),
    no_index_cache: bool = typer.Option(False, "--no-index-cache"),
    enable_ru: bool = typer.Option(False, "--enable-ru"),
    ru_corpus: list[Path] = typer.Option([], "--ru-corpus"),
) -> None:
    """End-to-end: extract (LLM) or use --terms, lookup Black's, validate, export."""
    if not input_path and not terms_file:
        raise typer.BadParameter("Provide --input and/or --terms.")
    dict_paths = _resolve_dictionary_paths(dictionary_dir, dictionary_glob)
    if not dict_paths:
        raise typer.BadParameter(
            f"No dictionary PDFs matched glob {dictionary_glob!r} in {dictionary_dir}"
        )
    cache_path = None if no_index_cache else index_cache
    results = run_full_pipeline(
        input_paths=input_path,
        dictionary_paths=dict_paths,
        output_dir=output_dir,
        terms_file=terms_file,
        enable_ru_law=enable_ru,
        ru_corpus_paths=ru_corpus or None,
        index_cache_path=cache_path,
        cfg=load_pipeline_config(),
    )
    typer.echo(
        f"Done. {len(results)} rows -> {output_dir.resolve()} "
        f"(see results_human.xlsx for non-technical view)"
    )


@app.command("run-simple")
def run_simple(
    terms_file: Path = typer.Option(..., "--terms", "-t", help="TXT with one word/phrase per line."),
    dictionary_dir: Path = typer.Option(..., "--dictionary-dir", help="Folder with dictionary PDFs."),
    output_dir: Path = typer.Option(Path("output_simple"), "--output", "-o"),
    dictionary_glob: str = typer.Option("*.pdf", "--dictionary-glob"),
) -> None:
    """
    Simple mode for non-technical users: terms in -> human-friendly table out.
    """
    dict_paths = _resolve_dictionary_paths(dictionary_dir, dictionary_glob)
    if not dict_paths:
        raise typer.BadParameter(
            f"No dictionary PDFs matched glob {dictionary_glob!r} in {dictionary_dir}"
        )
    results = run_lookup_only(
        terms_file=terms_file,
        dictionary_paths=dict_paths,
        output_dir=output_dir,
        enable_ru_law=False,
        ru_corpus_paths=None,
        index_cache_path=Path(".cache/dictionary_index.pkl"),
        cfg=load_pipeline_config(),
    )
    typer.echo(
        f"Done. Open {output_dir / 'results_human.xlsx'} "
        f"(rows: {len(results)})"
    )


@app.command("export-only")
def export_only(
    results_json: Path = typer.Option(..., "--results-json"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
) -> None:
    """Re-export JSON results to XLSX (expects results.json schema from this tool)."""
    from app.schemas.term import TermWithRuMapping

    data = json.loads(results_json.read_text(encoding="utf-8"))
    results = [TermWithRuMapping.model_validate(x) for x in data]
    output_dir.mkdir(parents=True, exist_ok=True)
    export_json(results, output_dir / "results.reexport.json")
    export_xlsx(results, output_dir / "results.reexport.xlsx")
    typer.echo(f"Wrote Excel to {output_dir / 'results.reexport.xlsx'}")


if __name__ == "__main__":
    app()
