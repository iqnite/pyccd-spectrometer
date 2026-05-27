import math
import tkinter as tk
from tkinter import ttk
from typing import Iterable, Sequence


class IdentificationDialog:
    """Dialog showing ranked element matches with detailed scoring columns."""

    def __init__(self, master, peaks: Iterable[float], ranked_matches, config, catalog_lines=None):
        # Accept peaks as floats or (wavelength, intensity) tuples
        parsed_peaks: list[float] = []
        for p in peaks:
            if isinstance(p, (list, tuple)) and len(p) >= 1:
                try:
                    parsed_peaks.append(float(p[0]))
                except Exception:
                    pass
            else:
                try:
                    parsed_peaks.append(float(p))
                except Exception:
                    pass
        peaks = parsed_peaks
        peak_count = max(1, len(peaks))
        try:
            max_distance_nm = float(getattr(config, "line_match_max_distance_nm", 3.0) or 3.0)
        except Exception:
            max_distance_nm = 3.0

        self.top = tk.Toplevel(master)
        self.top.title("Identification Results")
        self.top.transient(master)
        self.top.grab_set()

        frm = ttk.Frame(self.top, padding=8)
        frm.grid(row=0, column=0, sticky="nsew")
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(0, weight=1)

        # Header
        hdr = ttk.Label(frm, text="Top candidates", font=(None, 12, "bold"))
        hdr.grid(row=0, column=0, sticky="w")

        # Treeview for ranked elements with detailed columns
        cols = ("element", "line_pct", "intensity_pct", "avg_distance", "coverage", "support")
        tree = ttk.Treeview(frm, columns=cols, show="headings", height=8)
        tree.heading("element", text="Element")
        tree.heading("line_pct", text="Line %")
        tree.heading("intensity_pct", text="Intensity %")
        tree.heading("avg_distance", text="Avg Δnm")
        tree.heading("coverage", text="Coverage")
        tree.heading("support", text="Supporting lines (top)")
        tree.column("element", width=90, anchor="w")
        tree.column("line_pct", width=80, anchor="center")
        tree.column("intensity_pct", width=90, anchor="center")
        tree.column("avg_distance", width=90, anchor="center")
        tree.column("coverage", width=80, anchor="center")
        tree.column("support", width=240, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew", pady=(6, 6))

        # Fill with ranked matches and compute detailed metrics per element
        for match in ranked_matches:
            element = getattr(match, "element", str(match))
            supporting = getattr(match, "supporting_lines", ())

            # Line-match percent: average proximity-based score per expected peak
            line_score_sum = 0.0
            distances = []
            observed_prom = 0.0
            for lm in supporting:
                try:
                    line_score_sum += lm.score
                    distances.append(lm.distance_nm)
                    obs_int = lm.observed_intensity if getattr(lm, 'observed_intensity', None) is not None else 1.0
                    ri = lm.line.relative_intensity or 1.0
                    observed_prom += math.log10(max(ri, 1.0)) * obs_int
                except Exception:
                    pass

            avg_line_pct = 0.0
            if peak_count > 0:
                avg_line_pct = min(100.0, (line_score_sum / peak_count) * 100.0)

            # Intensity percent: observed prominences vs expected prominences from catalog
            intensity_pct = 0.0
            catalog = catalog_lines
            expected_prominence = 0.0
            if catalog is not None:
                elines = [
                    l for l in catalog
                    if getattr(l, 'element', None) == element
                    and min(peaks) - max_distance_nm <= l.match_wavelength_nm <= max(peaks) + max_distance_nm
                ]
                elines.sort(key=lambda l: -(math.log10(max((l.relative_intensity or 1.0), 1.0))))
                top = elines[:max(1, peak_count)]
                expected_prominence = sum(math.log10(max((l.relative_intensity or 1.0), 1.0)) for l in top)

            if expected_prominence > 0:
                intensity_pct = max(0.0, min(100.0, (observed_prom / expected_prominence) * 100.0))

            avg_distance = float(sum(distances) / len(distances)) if distances else 0.0
            coverage_pct = min(100.0, (len(supporting) / max(1, peak_count)) * 100.0)

            # Format top supporting lines as "wavelength:nm(score)" list
            sup_items = []
            for lm in list(supporting)[:6]:
                try:
                    wl = getattr(lm.line, "match_wavelength_nm", lm.line.wavelength_nm)
                    sup_items.append(f"{wl:.2f}nm({lm.score:.2f})")
                except Exception:
                    pass

            tree.insert(
                "",
                "end",
                values=(
                    element,
                    f"{avg_line_pct:.1f}%",
                    f"{intensity_pct:.1f}%",
                    f"{avg_distance:.2f}nm",
                    f"{coverage_pct:.0f}%",
                    f"{', '.join(sup_items)}",
                ),
            )

        # Per-peak summary
        lbl = ttk.Label(frm, text="Peaks used:")
        lbl.grid(row=2, column=0, sticky="w")
        peaks_text = ", ".join(f"{p:.2f}nm" for p in peaks)
        pe = ttk.Label(frm, text=peaks_text, wraplength=520)
        pe.grid(row=3, column=0, sticky="w", pady=(2, 8))

        # Close button
        btn = ttk.Button(frm, text="Close", command=self.close)
        btn.grid(row=4, column=0, sticky="e")

        # Make dialog resizable and expand tree
        frm.rowconfigure(1, weight=1)
        frm.columnconfigure(0, weight=1)

    def close(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        try:
            self.top.destroy()
        except Exception:
            pass
