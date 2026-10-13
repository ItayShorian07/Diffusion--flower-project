#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base_url="https://huggingface.co/mehrsapo/flower-weights/resolve/main"

for relative_path in \
  model/celeba/ot/model_final.pt \
  model/afhq_cat/ot/model_final.pt; do
  destination="$project_root/$relative_path"
  mkdir -p "$(dirname "$destination")"
  if [[ ! -f "$destination" ]]; then
    echo "Downloading $relative_path"
    curl -L --fail --retry 5 --retry-delay 2 "$base_url/$relative_path" -o "$destination"
  fi
done

echo "Prepared the two official FLOWER OT checkpoints"
