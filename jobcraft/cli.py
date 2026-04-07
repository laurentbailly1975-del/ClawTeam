"""JobCraft CLI — `jobcraft <command>`"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from jobcraft import store, scraper, ai, renderer

app = typer.Typer(
    name="jobcraft",
    help="Assistant de candidature propulsé par Claude.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _load_env() -> None:
    env_file = store.DATA_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _require_profile() -> dict:
    profile = store.load_profile()
    if not profile:
        console.print("[red]Aucun profil chargé.[/red] Lancez d'abord : [bold]jobcraft profile chemin/vers/profil.json[/bold]")
        raise typer.Exit(1)
    return profile


def _open_file(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)])
    elif sys.platform == "win32":
        os.startfile(str(path))
    else:
        subprocess.run(["xdg-open", str(path)])


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    store.init()
    _load_env()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@app.command()
def profile(
    path: Path = typer.Argument(..., help="Chemin vers votre profil JSON"),
) -> None:
    """Importer ou mettre à jour votre profil (JSON)."""
    if not path.exists():
        console.print(f"[red]Fichier introuvable : {path}[/red]")
        raise typer.Exit(1)
    data = json.loads(path.read_text())
    store.save_profile(data)
    name = data.get("name") or data.get("identity", {}).get("name", "?")
    console.print(f"[green]Profil importé :[/green] {name}")
    console.print(f"Stocké dans : {store.PROFILE_PATH}")


@app.command()
def add(
    url: str = typer.Argument(..., help="URL de l'offre"),
) -> None:
    """Ajouter une offre depuis une URL (scraping)."""
    store.init()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        progress.add_task("Récupération de l'offre...", total=None)
        try:
            job_data = scraper.scrape(url)
        except Exception as exc:
            console.print(f"[red]Erreur scraping :[/red] {exc}")
            raise typer.Exit(1)
    job_id = store.add_job(
        url=url,
        title=job_data.get("title", ""),
        company=job_data.get("company", ""),
        location=job_data.get("location", ""),
        contract_type=job_data.get("contract_type", ""),
        salary=job_data.get("salary", ""),
        text=job_data.get("text", ""),
    )
    console.print(Panel(
        f"[bold]#{job_id}[/bold]  {job_data.get('title', '—')}\n"
        f"[dim]{job_data.get('company', '')}  ·  {job_data.get('location', '')}[/dim]",
        title="[green]Offre ajoutée[/green]",
        border_style="green",
    ))
    console.print(f"Analysez avec : [bold]jobcraft analyze {job_id}[/bold]")


@app.command("list")
def list_jobs() -> None:
    """Lister toutes les offres enregistrées."""
    store.init()
    jobs = store.list_jobs()
    if not jobs:
        console.print("[dim]Aucune offre. Utilisez [bold]jobcraft add <url>[/bold][/dim]")
        return
    table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=4)
    table.add_column("Titre", min_width=28)
    table.add_column("Entreprise", min_width=18)
    table.add_column("Score", justify="center", width=7)
    table.add_column("Date", style="dim", width=12)
    for j in jobs:
        score = j.get("score")
        if score is None:
            score_text = Text("—", style="dim")
        elif score >= 75:
            score_text = Text(str(score), style="bold green")
        elif score >= 50:
            score_text = Text(str(score), style="yellow")
        else:
            score_text = Text(str(score), style="dim red")
        date_str = (j.get("added_at") or "")[:10]
        table.add_row(str(j["id"]), j.get("title") or "—", j.get("company") or "—", score_text, date_str)
    console.print(table)


@app.command()
def analyze(
    job_id: int = typer.Argument(..., help="ID de l'offre"),
) -> None:
    """Analyser une offre vs votre profil et calculer le score de matching."""
    store.init()
    profile = _require_profile()
    job = store.get_job(job_id)
    if not job:
        console.print(f"[red]Offre #{job_id} introuvable.[/red]")
        raise typer.Exit(1)
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        progress.add_task("Analyse en cours...", total=None)
        result = ai.analyze(profile, job["text"])
    store.update_analysis(job_id, result["score"], result)
    score = result["score"]
    score_color = "green" if score >= 75 else ("yellow" if score >= 50 else "red")
    console.print()
    console.print(Panel(
        f"Score global : [bold {score_color}]{score}/100[/bold {score_color}]",
        title=f"[bold]Analyse — {job.get('title', '#' + str(job_id))}[/bold]",
        border_style=score_color,
    ))
    breakdown = result.get("score_breakdown", {})
    if breakdown:
        t = Table(box=box.MINIMAL, show_header=False, padding=(0, 2))
        for k, v in breakdown.items():
            t.add_row(k.replace("_", " ").title(), f"[bold]{v}[/bold]")
        console.print(t)
    if result.get("strengths"):
        console.print("\n[bold green]Points forts à valoriser :[/bold green]")
        for s in result["strengths"]:
            console.print(f"  [green]✓[/green] {s}")
    if result.get("gaps"):
        console.print("\n[bold yellow]Points d'attention :[/bold yellow]")
        for g in result["gaps"]:
            console.print(f"  [yellow]△[/yellow] {g}")
    if result.get("narrative_angle"):
        console.print(f"\n[bold]Angle recommandé :[/bold] {result['narrative_angle']}")
    if result.get("recommendation"):
        console.print(f"\n[dim]{result['recommendation']}[/dim]")
    console.print(f"\nGénérez les documents : [bold]jobcraft generate {job_id}[/bold]")


@app.command()
def generate(
    job_id: int = typer.Argument(..., help="ID de l'offre"),
    instructions: Optional[str] = typer.Option(None, "--instructions", "-i"),
    open_after: bool = typer.Option(False, "--open", "-o"),
) -> None:
    """Générer CV et lettre de motivation pour une offre."""
    store.init()
    profile = _require_profile()
    job = store.get_job(job_id)
    if not job:
        console.print(f"[red]Offre #{job_id} introuvable.[/red]")
        raise typer.Exit(1)
    if not job.get("analysis"):
        console.print("[yellow]Analyse manquante — lancement automatique...[/yellow]")
        with Progress(SpinnerColumn(), TextColumn("Analyse..."), transient=True) as progress:
            progress.add_task("", total=None)
            analysis = ai.analyze(profile, job["text"])
        store.update_analysis(job_id, analysis["score"], analysis)
        job = store.get_job(job_id)
    analysis = job["analysis"]
    inst = instructions or "Aucune instruction spécifique."
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  transient=True) as progress:
        progress.add_task("Génération des documents...", total=None)
        docs = ai.generate(profile, job, analysis, inst)
    cv_html = renderer.render_cv(docs, job)
    cover_html = renderer.render_cover(docs, job)
    cv_path = store.save_doc_file(job_id, "cv.html", cv_html)
    cover_path = store.save_doc_file(job_id, "cover.html", cover_html)
    docs["_instructions_history"] = [inst]
    store.update_documents(job_id, docs)
    console.print(Panel(
        f"[green]CV :[/green]     {cv_path}\n[green]Lettre :[/green]  {cover_path}",
        title="[bold green]Documents générés[/bold green]",
        border_style="green",
    ))
    pdf_cv = store.docs_path(job_id) / "cv.pdf"
    pdf_cover = store.docs_path(job_id) / "cover.pdf"
    cv_ok = renderer.html_to_pdf(cv_path, pdf_cv)
    cover_ok = renderer.html_to_pdf(cover_path, pdf_cover)
    if cv_ok and cover_ok:
        console.print(f"[dim]PDF : {pdf_cv.parent}/cv.pdf + cover.pdf[/dim]")
    else:
        console.print("[dim]PDF non généré. Ouvrez les .html dans un navigateur → Imprimer → Enregistrer en PDF.[/dim]")
    console.print(f"\nAjustements : [bold]jobcraft tweak {job_id} \"votre instruction\"[/bold]")
    console.print(f"Ouvrir :       [bold]jobcraft view {job_id}[/bold]")
    if open_after:
        _open_file(cv_path)


@app.command()
def tweak(
    job_id: int = typer.Argument(..., help="ID de l'offre"),
    instruction: str = typer.Argument(..., help="Instruction de modification en langage naturel"),
) -> None:
    """Affiner les documents générés avec une instruction naturelle."""
    store.init()
    profile = _require_profile()
    job = store.get_job(job_id)
    if not job:
        console.print(f"[red]Offre #{job_id} introuvable.[/red]")
        raise typer.Exit(1)
    if not job.get("documents"):
        console.print("[red]Aucun document généré. Lancez d'abord [bold]jobcraft generate <id>[/bold][/red]")
        raise typer.Exit(1)
    previous_docs = job["documents"]
    analysis = job.get("analysis") or {}
    with Progress(SpinnerColumn(), TextColumn("Ajustement en cours..."), transient=True) as progress:
        progress.add_task("", total=None)
        docs = ai.refine(profile, job, analysis, previous_docs, instruction)
    cv_html = renderer.render_cv(docs, job)
    cover_html = renderer.render_cover(docs, job)
    cv_path = store.save_doc_file(job_id, "cv.html", cv_html)
    cover_path = store.save_doc_file(job_id, "cover.html", cover_html)
    history = previous_docs.get("_instructions_history", []) + [instruction]
    docs["_instructions_history"] = history
    store.update_documents(job_id, docs)
    renderer.html_to_pdf(cv_path, store.docs_path(job_id) / "cv.pdf")
    renderer.html_to_pdf(cover_path, store.docs_path(job_id) / "cover.pdf")
    console.print(f"[green]Documents mis à jour.[/green]  {cv_path.parent}/")
    console.print(f"Ouvrir : [bold]jobcraft view {job_id}[/bold]")


@app.command()
def view(
    job_id: int = typer.Argument(..., help="ID de l'offre"),
    doc: str = typer.Option("cv", "--doc", "-d", help="cv | cover | both"),
) -> None:
    """Ouvrir les documents générés dans le navigateur."""
    store.init()
    d = store.docs_path(job_id)
    files = {"cv": d / "cv.html", "cover": d / "cover.html"}
    if doc == "both":
        targets = list(files.values())
    elif doc in files:
        targets = [files[doc]]
    else:
        console.print("[red]doc doit être : cv | cover | both[/red]")
        raise typer.Exit(1)
    for p in targets:
        if p.exists():
            webbrowser.open(p.as_uri())
        else:
            console.print(f"[red]Fichier absent : {p}[/red] — générez d'abord les documents.")


@app.command()
def show(
    job_id: int = typer.Argument(..., help="ID de l'offre"),
) -> None:
    """Afficher les détails d'une offre."""
    store.init()
    job = store.get_job(job_id)
    if not job:
        console.print(f"[red]Offre #{job_id} introuvable.[/red]")
        raise typer.Exit(1)
    console.print(Panel(
        f"[bold]{job.get('title', '—')}[/bold]\n"
        f"[blue]{job.get('company', '')}[/blue]  ·  {job.get('location', '')}\n"
        f"[dim]{job.get('url', '')}[/dim]",
        title=f"Offre #{job_id}",
    ))
    if job.get("analysis"):
        a = job["analysis"]
        console.print(f"\n[bold]Score :[/bold] {a.get('score', '—')}/100")
        if a.get("narrative_angle"):
            console.print(f"[bold]Angle :[/bold] {a['narrative_angle']}")
    text = job.get("text", "")
    if text:
        console.print(f"\n[dim]{text[:800]}{'...' if len(text) > 800 else ''}[/dim]")


@app.command("delete")
def delete_job(
    job_id: int = typer.Argument(..., help="ID de l'offre à supprimer"),
) -> None:
    """Supprimer une offre et ses documents."""
    store.init()
    store.delete_job(job_id)
    import shutil
    d = store.docs_path(job_id)
    if d.exists():
        shutil.rmtree(d)
    console.print(f"[dim]Offre #{job_id} supprimée.[/dim]")


def main_entry() -> None:
    app()
