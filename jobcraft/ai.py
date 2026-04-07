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
    """Extract JSON from LLM response, tolerating markdown code blocks."""
    # Try to find ```json ... ``` block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Try raw JSON
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON found in response:\n{text[:500]}")


# ─── Analysis ────────────────────────────────────────────────────────────────

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
  "strengths": ["point fort 1 à valoriser", "point fort 2", ...],
  "gaps": ["manque ou écart 1 avec piste de mitigation", ...],
  "ats_keywords": ["mot-clé critique 1", "mot-clé 2", ...],
  "narrative_angle": "angle de positionnement recommandé en 1-2 phrases",
  "recommendation": "évaluation honnête et directe en 2-3 phrases"
}}"""


def analyze(profile: dict[str, Any], job_text: str) -> dict[str, Any]:
    client = _client()
    profile_str = json.dumps(profile, ensure_ascii=False, indent=2)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=ANALYSIS_SYSTEM,
        messages=[{
            "role": "user",
            "content": ANALYSIS_USER.format(profile=profile_str, job_text=job_text[:6000]),
        }],
    )
    return _extract_json(msg.content[0].text)


# ─── Document generation ──────────────────────────────────────────────────────

GENERATION_SYSTEM = """Tu es un rédacteur expert en CV et lettres de motivation, \
spécialisé sur le marché français. Tu produis des documents au niveau d'un très bon \
rédacteur humain expérimenté.

RÈGLES CV — non négociables :
- Chaque bullet point commence par un verbe d'action fort au passé (Conçu, Piloté, Réduit, Déployé...)
- Toutes les réalisations sont chiffrées ou contextualisées (%, €, durée, taille équipe)
- Les mots-clés ATS de l'offre sont intégrés naturellement dans le texte
- Seules les infos pertinentes pour CE poste sont incluses
- Le titre professionnel reflète exactement ce que cherche le recruteur

RÈGLES LETTRE — non négociables :
- Accroche directe et situationnelle (jamais "je vous contacte pour postuler à...")
- Absolument interdits : "dynamique", "passionné(e)", "je suis convaincu(e) que", \
"dans l'attente de votre retour", "votre entreprise en pleine croissance", "challenges"
- Ton : professionnel mais humain, comme quelqu'un qui s'exprime très bien
- Structure : contexte/accroche → valeur concrète apportée → fit culturel → appel à l'action discret
- Longueur : 3 paragraphes, 280-350 mots max
- Pas de mise en forme lourde (pas de bullet points dans la lettre)

Tu réponds UNIQUEMENT avec du JSON valide."""

GENERATION_USER = """Profil candidat :
{profile}

Offre d'emploi :
{job_text}

Analyse de correspondance :
{analysis}

Instructions spécifiques : {instructions}

Génère le contenu des documents en JSON :
{{
  "cv": {{
    "header": {{
      "name": "...",
      "title": "titre calqué sur l'offre",
      "tagline": "phrase d'accroche percutante (1 ligne)",
      "contact": {{"email": "...", "phone": "...", "location": "...", "linkedin": "...", "other": "..."}}
    }},
    "experiences": [
      {{
        "role": "...",
        "company": "...",
        "period": "...",
        "location": "...",
        "bullets": ["réalisation chiffrée 1", "réalisation 2", ...]
      }}
    ],
    "education": [
      {{"degree": "...", "school": "...", "year": "...", "detail": "..."}}
    ],
    "skills": {{
      "technical": ["skill 1", "skill 2", ...],
      "tools": ["outil 1", ...],
      "soft": ["soft skill 1", ...]
    }},
    "languages": [{{"lang": "...", "level": "..."}}],
    "certifications": ["cert 1", ...],
    "projects": [
      {{"name": "...", "description": "...", "tech": "..."}}
    ]
  }},
  "cover_letter": {{
    "paragraphs": ["paragraphe 1", "paragraphe 2", "paragraphe 3"],
    "closing": "formule de clôture naturelle et courte"
  }}
}}"""


def generate(
    profile: dict[str, Any],
    job: dict[str, Any],
    analysis: dict[str, Any],
    instructions: str = "Aucune instruction spécifique.",
) -> dict[str, Any]:
    client = _client()
    profile_str = json.dumps(profile, ensure_ascii=False, indent=2)
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2)
    job_text = f"Titre : {job.get('title', '')}\nEntreprise : {job.get('company', '')}\n\n{job.get('text', '')}"

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=GENERATION_SYSTEM,
        messages=[{
            "role": "user",
            "content": GENERATION_USER.format(
                profile=profile_str,
                job_text=job_text[:5000],
                analysis=analysis_str,
                instructions=instructions,
            ),
        }],
    )
    return _extract_json(msg.content[0].text)


def refine(
    profile: dict[str, Any],
    job: dict[str, Any],
    analysis: dict[str, Any],
    previous_docs: dict[str, Any],
    instruction: str,
) -> dict[str, Any]:
    """Refine existing documents with a natural language instruction."""
    client = _client()
    profile_str = json.dumps(profile, ensure_ascii=False, indent=2)
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2)
    prev_str = json.dumps(previous_docs, ensure_ascii=False, indent=2)
    job_text = f"Titre : {job.get('title', '')}\nEntreprise : {job.get('company', '')}\n\n{job.get('text', '')}"

    system = GENERATION_SYSTEM + """

Tu modifies des documents EXISTANTS selon une instruction précise.
Ne change que ce qui est demandé. Conserve ce qui est déjà bon."""

    user = f"""Documents actuels :
{prev_str}

Offre d'emploi :
{job_text[:3000]}

Profil candidat (référence) :
{profile_str[:3000]}

Analyse :
{analysis_str}

Instruction de modification : {instruction}

Retourne les documents complets modifiés dans le même format JSON."""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return _extract_json(msg.content[0].text)
