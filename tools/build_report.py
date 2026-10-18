#!/usr/bin/env python3
"""Compile the final, editable LaTeX report without changing its contents."""
from pathlib import Path
import argparse
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/report/FLOWER_Noise_Mismatch_Report.tex'
BUILD = ROOT / 'artifacts/build/report'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=SOURCE.with_suffix('.pdf'))
    args = parser.parse_args()
    if shutil.which('latexmk') is None:
        raise SystemExit('latexmk is required. Install a TeX distribution to compile the report.')
    BUILD.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error',
                             f'-outdir={BUILD}', SOURCE.name], cwd=SOURCE.parent,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (BUILD / 'build.log').write_text(result.stdout)
    if result.returncode:
        raise SystemExit(result.stdout[-10000:])
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD / SOURCE.with_suffix('.pdf').name, output)
    print(output)


if __name__ == '__main__':
    main()
