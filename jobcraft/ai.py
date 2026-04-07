"""Claude API calls for analysis and document generation."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic

MODEL = os.getenv("JOBCRAFT_MODEL", "claude-sonnet-4-6")


def _client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it or add it to ~/.jobcraft/.env"
        )
    return anthropic.Anthropic(api_key=api_key)


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in response:\n{text[:500]}")


ANALYSIS_SYSTEM = """Tu es un expert en recrutement avec 20 ans d'expérience en France.
Tu analyses la correspondance entre un profil candidat et une offre d'emploi.
Tu réponds UNIQUEMENT avec du JSON valide, sans aucun texte autour."""

ANALYSIS_USER = """Profil candidat :
{profile}

Offre d'emploi :
{job_text}

Analyse la correspondance et retourne ce JSON :
{{
  "score": <entier 0-100>,
  "score_breakdown": {{
    "competences_techniques": <0-100>,
    "niveau_seniorite": <0-100>,
    "secteur_contexte": <0-100>,
    "soft_skills": <0-100>
  }},
  "strengths": ["point fort 1", ...],
  "gaps": ["écart 1 avec mitigation", ...],
  "ats_keywords": ["mot-clé 1", ...],
  "narrative_angle": "angle recommandé en 1-2 phrases",
  "recommendation": "évaluation honnête en 2-3 phrases"
}}"""


def analyze(profile: dict[str, Any], job_text: str) -> dict[str, Any]:
    client = _client()
    profile_str = json.dumps(profile, ensure_ascii=False, indent=2)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": ANALYSIS_USER.format(profile=profile_str, job_text=job_text[:6000])}],
    )
    return _extract_json(msg.content[0].text)


GENERATION_SYSTEM = """Tu es un rédacteur expert en CV et lettres de motivation, spécialisé sur le marché français.
Tu produis des documents au niveau d'un très bon rédacteur humain expérimenté.

RÈGLES CV :
- Chaque bullet point commence par un verbe d'action fort au passé
- Toutes les réalisations sont chiffrées ou contextualisées
- Les mots-clés ATS de l'offre sont intégrés naturellement
- Seules les infos pertinentes pour CE poste sont incluses

RÈGLES LETTRE :
- Accroche directe (jamais "je vous contacte pour postuler à...")
- Interdits : "dynamique", "passionné(e)", "je suis convaincu(e) que", "dans l'attente de votre retour"
- Ton : professionnel mais humain
- Structure : accroche → valeur apportée → fit → appel à l'action
- 3 paragraphes, 280-350 mots

Tu réponds UNIQUEMENT avec du JSON valide."""

GENERATION_USER = """Profil : {profile}

Offre : {job_text}

Analyse : {analysis}

Instructions : {instructions}

Génère en JSON :
{{
  "cv": {{
    "header": {{"name": "", "title": "", "tagline": "", "contact": {{"email": "", "phone": "", "location": "", "linkedin": "", "other": ""}}}},
    "experiences": [{{"role": "", "company": "", "period": "", "location": "", "bullets": []}}],
    "education": [{{"degree": "", "school": "", "year": "", "detail": ""}}],
    "skills": {{"technical": [], "tools": [], "soft": []}},
    "languages": [{{"lang": "", "level": ""}}],
    "certifications": [],
    "projects": [{{"name": "", "description": "", "tech": ""}}]
  }},
  "cover_letter": {{"paragraphs": ["", "", ""], "closing": ""}}
}}"""


def generate(profile: dict[str, Any], job: dict[str, Any], analysis: dict[str, Any], instructions: str = "Aucune.") -> dict[str, Any]:
    client = _client()
    job_text = f"Titre : {job.get('title', '')}\nEntreprise : {job.get('company', '')}\n\n{job.get('text', '')}"
    msg = client.messages.create(
        model=MODEL, max_tokens=4000, system=GENERATION_SYSTEM,
        messages=[{"role": "user", "content": GENERATION_USER.format(
            profile=json.dumps(profile, ensure_ascii=False, indent=2),
            job_text=job_text[:5000],
            analysis=json.dumps(analysis, ensure_ascii=False, indent=2),
            instructions=instructions,
        )}],
    )
    return _extract_json(msg.content[0].text)


def refine(profile: dict[str, Any], job: dict[str, Any], analysis: dict[str, Any], previous_docs: dict[str, Any], instruction: str) -> dict[str, Any]:
    client = _client()
    job_text = f"Titre : {job.get('title', '')}\nEntreprise : {job.get('company', '')}\n\n{job.get('text', '')}"
    system = GENERATION_SYSTEM + "\n\nTu modifies des documents EXISTANTS. Ne change que ce qui est demandé."
    user = f"Documents actuels :\n{json.dumps(previous_docs, ensure_ascii=False, indent=2)}\n\nOffre :\n{job_text[:3000]}\n\nProfil :\n{json.dumps(profile, ensure_ascii=False, indent=2)[:3000]}\n\nInstruction : {instruction}\n\nRetourne les documents complets modifiés dans le même format JSON."
    msg = client.messages.create(
        model=MODEL, max_tokens=4000, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return _extract_json(msg.content[0].text)
