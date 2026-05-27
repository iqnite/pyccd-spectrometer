from __future__ import annotations

from bisect import bisect_left, bisect_right
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


_CATALOG_CACHE: dict[str, tuple[float | None, list["SpectralLine"]]] = {}
_WAVELENGTH_INDEX_CACHE: dict[int, tuple[int, list[float]]] = {}


@dataclass(frozen=True)
class SpectralLine:
    element: str
    wavelength_nm: float
    ion_stage: str | None = None
    observed_wavelength_nm: float | None = None
    ritz_wavelength_nm: float | None = None
    uncertainty_nm: float | None = None
    relative_intensity: float | None = None
    transition_strength: float | None = None
    line_type: str | None = None
    source: str | None = None

    @property
    def match_wavelength_nm(self) -> float:
        if self.ritz_wavelength_nm is not None:
            return self.ritz_wavelength_nm
        if self.observed_wavelength_nm is not None:
            return self.observed_wavelength_nm
        return self.wavelength_nm


@dataclass(frozen=True)
class LineMatch:
    line: SpectralLine
    distance_nm: float
    score: float
    observed_wavelength_nm: float
    observed_intensity: float | None = None


@dataclass(frozen=True)
class ElementMatch:
    element: str
    score: float
    supporting_lines: tuple[LineMatch, ...]


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(__file__))).resolve()
    return Path(__file__).resolve().parents[1]


def _catalog_path(filename: str = "element_emission_lines.json") -> Path:
    return _repo_root() / filename


def _coerce_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _parse_line_record(element: str, record) -> SpectralLine | None:
    if isinstance(record, (int, float)):
        return SpectralLine(element=element, wavelength_nm=float(record))

    if isinstance(record, dict):
        wavelength = _coerce_float(
            record.get("ritz_wavelength_nm")
            or record.get("observed_wavelength_nm")
            or record.get("wavelength_nm")
            or record.get("wavelength")
        )
        if wavelength is None:
            return None

        ion_stage = record.get("ion_stage") or record.get("spectrum")
        return SpectralLine(
            element=element,
            wavelength_nm=wavelength,
            ion_stage=str(ion_stage) if ion_stage is not None else None,
            observed_wavelength_nm=_coerce_float(record.get("observed_wavelength_nm")),
            ritz_wavelength_nm=_coerce_float(record.get("ritz_wavelength_nm")),
            uncertainty_nm=_coerce_float(record.get("uncertainty_nm")),
            relative_intensity=_coerce_float(record.get("relative_intensity")),
            transition_strength=_coerce_float(
                record.get("transition_strength") or record.get("aki") or record.get("fik")
            ),
            line_type=record.get("line_type") or record.get("type"),
            source=record.get("source"),
        )

    return None


def load_line_catalog(filename: str = "element_emission_lines.json") -> list[SpectralLine]:
    path = _catalog_path(filename)
    cache_key = str(path)
    try:
        mtime = path.stat().st_mtime
    except Exception:
        mtime = None

    cached = _CATALOG_CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        if filename != "element_emission_lines.json":
            # Graceful fallback for older installs/builds that may not yet ship
            # the NIST-derived catalog.
            return load_line_catalog("element_emission_lines.json")
        return []

    lines: list[SpectralLine] = []
    if isinstance(data, dict):
        for element, records in data.items():
            if not isinstance(records, list):
                continue
            for record in records:
                parsed = _parse_line_record(str(element), record)
                if parsed is not None:
                    lines.append(parsed)
    elif isinstance(data, list):
        for record in data:
            if isinstance(record, dict) and "element" in record:
                parsed = _parse_line_record(str(record["element"]), record)
                if parsed is not None:
                    lines.append(parsed)

    sorted_lines = sorted(lines, key=lambda line: line.match_wavelength_nm)
    _CATALOG_CACHE[cache_key] = (mtime, sorted_lines)
    return sorted_lines


def lines_as_legacy_tuples(lines: Sequence[SpectralLine]) -> list[tuple[float, str]]:
    return [(line.match_wavelength_nm, line.element) for line in lines]


def _default_tolerance_nm(line: SpectralLine, fallback_nm: float) -> float:
    if line.uncertainty_nm and line.uncertainty_nm > 0:
        return max(fallback_nm, line.uncertainty_nm * 3.0)
    return fallback_nm


def _get_sorted_wavelengths_nm(lines: Sequence[SpectralLine]) -> list[float]:
    """Return match-wavelengths for a sorted `lines` sequence.

    For performance, cache the computed float list for list/tuple inputs.
    """
    if isinstance(lines, (list, tuple)):
        key = id(lines)
        cached = _WAVELENGTH_INDEX_CACHE.get(key)
        if cached is not None and cached[0] == len(lines):
            return cached[1]

        wl = [line.match_wavelength_nm for line in lines]
        _WAVELENGTH_INDEX_CACHE[key] = (len(lines), wl)
        return wl

    return [line.match_wavelength_nm for line in lines]


def score_peak_against_lines(
    wavelength_nm: float,
    lines: Sequence[SpectralLine],
    *,
    max_distance_nm: float = 3.0,
    min_score: float = 0.1,
    observed_intensity: float | None = None,
) -> list[LineMatch]:
    # Convert to an indexable sequence for slicing.
    if not isinstance(lines, (list, tuple)):
        lines = list(lines)

    w = float(wavelength_nm)
    wavelengths = _get_sorted_wavelengths_nm(lines)
    left = bisect_left(wavelengths, w - float(max_distance_nm))
    right = bisect_right(wavelengths, w + float(max_distance_nm))

    matches: list[LineMatch] = []
    for line in lines[left:right]:
        target_nm = line.match_wavelength_nm
        distance_nm = abs(w - target_nm)
        tolerance_nm = _default_tolerance_nm(line, max_distance_nm)
        if distance_nm > tolerance_nm:
            continue

        proximity = 1.0 - (distance_nm / tolerance_nm)
        proximity = max(0.0, min(1.0, proximity))

        strength_bonus = 1.0
        if line.relative_intensity is not None:
            strength_bonus += min(0.25, math.log10(max(line.relative_intensity, 1.0)) / 20.0)
        if line.transition_strength is not None:
            strength_bonus += min(0.20, math.log10(max(line.transition_strength, 1.0)) / 40.0)

        score = proximity * strength_bonus
        # boost score if the observed peak is strong (observed_intensity in 0..1)
        if observed_intensity is not None:
            try:
                obs_factor = 0.5 + 0.5 * float(observed_intensity)
            except Exception:
                obs_factor = 1.0
            score *= obs_factor
        if score >= min_score:
            matches.append(
                LineMatch(
                    line=line,
                    distance_nm=distance_nm,
                    score=score,
                    observed_wavelength_nm=w,
                    observed_intensity=observed_intensity,
                )
            )

    matches.sort(key=lambda match: (-match.score, match.distance_nm, match.line.element))
    return matches


def rank_elements_for_peaks(
    peak_wavelengths_nm: Iterable[float],
    lines: Sequence[SpectralLine],
    *,
    max_distance_nm: float = 3.0,
    prominence_weight: float = 1.8,
    missing_line_penalty_weight: float = 1.2,
    expected_top_k: int | None = None,
) -> list[ElementMatch]:
    """Rank candidate elements for a set of detected peak wavelengths.

    Scoring notes:
    - Individual line matches are weighted by proximity and relative intensity.
    - Per-element, a consistent wavelength shift across supporting lines
      is allowed and rewarded (small stddev of offsets -> boost).
    - Missing prominent expected lines (within the observed range) impose
      a penalty proportional to their summed prominence.
    """

    element_scores: dict[str, list[LineMatch]] = {}

    # Accept either plain wavelengths or (wavelength, intensity) pairs
    peak_list: list[tuple[float, float]] = []
    for p in peak_wavelengths_nm:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                wl = float(p[0])
                it = float(p[1])
            except Exception:
                continue
        else:
            try:
                wl = float(p)
                it = 1.0
            except Exception:
                continue
        peak_list.append((wl, it))

    # normalize observed intensities to 0..1
    obs_ints = [it for _, it in peak_list]
    max_obs = max(obs_ints) if obs_ints else 1.0
    norm_peaks = [(wl, (it / max_obs) if max_obs > 0 else 0.0) for wl, it in peak_list]

    for wavelength_nm, obs_int in norm_peaks:
        # Prevent "dense" elements (e.g., Fe) from winning purely by having
        # many nearby catalog lines: take only the best line match per element
        # for each detected peak.
        best_for_element: dict[str, LineMatch] = {}
        for match in score_peak_against_lines(
            float(wavelength_nm),
            lines,
            max_distance_nm=max_distance_nm,
            observed_intensity=obs_int,
        ):
            key = match.line.element
            prev = best_for_element.get(key)
            if prev is None or match.score > prev.score:
                best_for_element[key] = match

        for element, best_match in best_for_element.items():
            element_scores.setdefault(element, []).append(best_match)

    ranked: list[ElementMatch] = []
    peaks = [wl for wl, _ in norm_peaks]
    if expected_top_k is None:
        expected_top_k = max(1, len(peaks))

    overall_min = min(peaks) - max_distance_nm
    overall_max = max(peaks) + max_distance_nm

    for element, supporting_lines in element_scores.items():
        # Compute prominence and basic stats
        n_obs = len(supporting_lines)
        prominences_observed = 0.0
        offsets = []
        scores = []
        max_rel_intensity = 0.0
        for lm in supporting_lines:
            ri = lm.line.relative_intensity or 1.0
            prom = math.log10(max(ri, 1.0))
            obs_int = lm.observed_intensity if lm.observed_intensity is not None else 1.0
            prominences_observed += prom * obs_int
            offsets.append(lm.observed_wavelength_nm - lm.line.match_wavelength_nm)
            scores.append(lm.score)
            max_rel_intensity = max(max_rel_intensity, ri * obs_int)

        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.0

        # spacing consistency: compare observed diffs to catalog diffs
        spacing_score = 0.0
        if n_obs >= 2:
            obs_sorted = sorted(supporting_lines, key=lambda m: m.observed_wavelength_nm)
            obs_diffs = [obs_sorted[i+1].observed_wavelength_nm - obs_sorted[i].observed_wavelength_nm for i in range(len(obs_sorted)-1)]
            cat_diffs = [obs_sorted[i+1].line.match_wavelength_nm - obs_sorted[i].line.match_wavelength_nm for i in range(len(obs_sorted)-1)]
            rel_errors = []
            for od, cd in zip(obs_diffs, cat_diffs):
                if cd <= 0:
                    continue
                rel_errors.append(abs(od - cd) / cd)
            if rel_errors:
                rel_mean = sum(rel_errors) / len(rel_errors)
                # smaller relative mean -> higher spacing_score; scale so 0.03 -> score ~0
                spacing_score = max(0.0, 1.0 - (rel_mean / 0.03))

        # Compute expected prominent lines for this element within observed window
        element_catalog_lines = [l for l in lines if l.element == element and overall_min <= l.match_wavelength_nm <= overall_max]
        element_catalog_lines.sort(key=lambda l: -(math.log10(max((l.relative_intensity or 1.0), 1.0))))
        expected_lines = element_catalog_lines[:expected_top_k]
        expected_prominence = sum(math.log10(max((l.relative_intensity or 1.0), 1.0)) for l in expected_lines)

        # coverage and prominence factors
        match_coverage = min(1.0, n_obs / max(1, expected_top_k))
        prominence_bonus = min(2.0, prominences_observed / max(1.0, expected_top_k))

        # missing prominent lines penalty (fraction missing scaled by weight, capped at 1.0)
        missing_penalty = 0.0
        if expected_prominence > 0:
            missing = max(0.0, expected_prominence - prominences_observed)
            missing_frac = (missing / expected_prominence)
            missing_penalty = min(1.0, missing_frac * missing_line_penalty_weight)

        # base aggregation: average score scaled by prominence and coverage
        base = avg_score * (1.0 + prominence_bonus * 1.5) * (0.3 + 0.7 * match_coverage)

        # spacing gives a small multiplicative boost
        base *= 1.0 + (spacing_score * 0.5)

        # penalize elements with only weak prominent matches
        if max_rel_intensity < 100.0:
            base *= 0.5

        # penalize single-line support (less reliable)
        if n_obs <= 1:
            base *= 0.5

        # apply missing penalty multiplicatively
        final_score = max(0.0, base * (1.0 - missing_penalty))

        ranked.append(
            ElementMatch(
                element=element,
                score=final_score,
                supporting_lines=tuple(
                    sorted(supporting_lines, key=lambda match: (-match.score, match.distance_nm))
                ),
            )
        )

    ranked.sort(key=lambda match: (-match.score, match.element))
    return ranked
