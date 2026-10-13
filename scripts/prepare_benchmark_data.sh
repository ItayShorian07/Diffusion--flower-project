#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

celeba_archive="$project_root/data/celeba/img_align_celeba.zip"
celeba_target="$project_root/data/celeba/paper_random20_seed2026"
celeba_manifest="$project_root/data_splits/celeba_paper100_random20_seed2026.txt"
celeba_url="https://huggingface.co/datasets/Yuehao/celeba/resolve/main/img_align_celeba.zip?download=true"

mkdir -p "$(dirname "$celeba_archive")" "$celeba_target"
if [[ ! -f "$celeba_archive" ]]; then
  echo "Downloading the CelebA aligned-image archive (about 1.4 GB)"
  curl -L --fail --retry 5 --retry-delay 2 "$celeba_url" -o "$celeba_archive"
fi

first_celeba="$(head -n 1 "$celeba_manifest")"
celeba_member="$(unzip -Z1 "$celeba_archive" | awk -v name="$first_celeba" 'index($0, name) == length($0) - length(name) + 1 { found = $0 } END { print found }')"
if [[ -z "$celeba_member" ]]; then
  echo "Could not locate $first_celeba in $celeba_archive" >&2
  exit 1
fi
celeba_prefix="${celeba_member%$first_celeba}"
celeba_members=()
while IFS= read -r filename; do
  [[ -n "$filename" ]] && celeba_members+=("${celeba_prefix}${filename}")
done < "$celeba_manifest"
unzip -j -o "$celeba_archive" "${celeba_members[@]}" -d "$celeba_target"

afhq_archive="$project_root/data/afhq.zip"
afhq_target="$project_root/data/afhq_cat/test/cat"
afhq_manifest="$project_root/data_splits/afhq_paper100_random20_seed2026.txt"
afhq_url="https://www.dropbox.com/s/t9l9o3vsx2jai3z/afhq.zip?dl=1"

mkdir -p "$afhq_target"
if [[ ! -f "$afhq_archive" ]]; then
  echo "Downloading the AFHQ archive (about 700 MB)"
  curl -L --fail --retry 5 --retry-delay 2 "$afhq_url" -o "$afhq_archive"
fi
afhq_members=()
while IFS= read -r filename; do
  [[ -n "$filename" ]] && afhq_members+=("afhq/val/cat/${filename}")
done < "$afhq_manifest"
unzip -j -o "$afhq_archive" "${afhq_members[@]}" -d "$afhq_target"

celeba_count="$(find "$celeba_target" -maxdepth 1 -type f -name '*.jpg' | wc -l | tr -d ' ')"
afhq_count="$(find "$afhq_target" -maxdepth 1 -type f -name '*.jpg' | wc -l | tr -d ' ')"
if [[ "$celeba_count" != "20" || "$afhq_count" != "20" ]]; then
  echo "Expected 20 selected images per dataset; found CelebA=$celeba_count AFHQ-Cat=$afhq_count" >&2
  exit 1
fi
echo "Prepared 20 CelebA and 20 AFHQ-Cat benchmark images"
