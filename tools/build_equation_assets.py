#!/usr/bin/env python3
"""Render high-resolution equation assets for the English project report."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/build/report-equations"


def render(name: str, expression: str, width: float, height: float = 0.72) -> None:
    fig = plt.figure(figsize=(width, height), dpi=320)
    fig.patch.set_alpha(0)
    fig.text(0.5, 0.5, expression, ha="center", va="center", fontsize=16, color="#111111")
    fig.savefig(OUTPUT / name, dpi=320, transparent=True, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    render("measurement.png", r"$y=Hx+n,\qquad n\sim\mathcal{N}(0,\sigma_{\mathrm{true}}^2I)$", 5.8)
    render("flow-path.png", r"$X_t=(1-t)X_0+tX_1,\qquad \hat{x}_1(x_t)=x_t+(1-t)v_\theta(x_t,t)$", 7.0)
    render(
        "destination-proof.png",
        r"$v^*(x_t,t)=\mathbb{E}[X_1-X_0\mid X_t=x_t]\;\Longrightarrow\;"
        r"\mathbb{E}[X_1\mid X_t=x_t]=x_t+(1-t)v^*(x_t,t)$",
        8.8,
    )
    render(
        "gaussian-posterior.png",
        r"$\Sigma_t=(\nu_t^{-2}I+\sigma_a^{-2}H^\mathsf{T}H)^{-1},\qquad "
        r"\mu_t=\Sigma_t(\nu_t^{-2}\hat{x}_1+\sigma_a^{-2}H^\mathsf{T}y)$",
        8.6,
    )
    render(
        "proximal-objective.png",
        r"$\mu_t=\arg\min_x\left\{\frac{\lVert Hx-y\rVert_2^2}{2\sigma_a^2}+"
        r"\frac{\lVert x-\hat{x}_1\rVert_2^2}{2\nu_t^2}\right\}$",
        7.4,
    )
    render(
        "progression.png",
        r"$x_{t+\Delta t}=(t+\Delta t)\,\tilde{x}_1+(1-t-\Delta t)\,\epsilon$",
        6.7,
    )
    render(
        "ancestral.png",
        r"$p(x_{t+\Delta t}\mid y)=\int p(x_{t+\Delta t}\mid x_t,y)\,p(x_t\mid y)\,dx_t$",
        7.0,
    )
    render(
        "delta-psnr.png",
        r"$\Delta\mathrm{PSNR}_i(r)=\mathrm{PSNR}_i(r)-\mathrm{PSNR}_i(1),\qquad "
        r"r=\sigma_{\mathrm{assumed}}/\sigma_{\mathrm{true}}$",
        7.5,
    )
    print(f"Equation assets written to {OUTPUT}")


if __name__ == "__main__":
    main()
