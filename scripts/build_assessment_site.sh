#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
publish_dir="$repo_root/assessment-public"

if [[ -L "$publish_dir" ]]; then
  echo "Refusing to stage the public site through a symlink." >&2
  exit 1
fi
mkdir -p "$publish_dir/assets"

# Stage only the registration microsite allowlist. Never publish the repository root.
for file in index.html contact.html login.html styles.css visuals.css exam.css site.js; do
  [[ -f "$repo_root/$file" ]] || { echo "Missing required public file: $file" >&2; exit 1; }
  cp "$repo_root/$file" "$publish_dir/$file"
done
for file in assets/contact-hero.svg assets/handshake.svg assets/qualinova-logo.png assets/sutravya-logo.png; do
  [[ -f "$repo_root/$file" ]] || { echo "Missing required public asset: $file" >&2; exit 1; }
  cp "$repo_root/$file" "$publish_dir/$file"
done

# Fail closed if a stale or unexpected file remains in a reused build directory.
while IFS= read -r relative_path; do
  case "$relative_path" in
    ./index.html|./contact.html|./login.html|./styles.css|./visuals.css|./exam.css|./site.js|\
    ./assets/contact-hero.svg|./assets/handshake.svg|./assets/qualinova-logo.png|./assets/sutravya-logo.png)
      ;;
    *) echo "Unexpected file in public site bundle: $relative_path" >&2; exit 1 ;;
  esac
done < <(cd "$publish_dir" && find . -type f -print | sort)

if find "$publish_dir" -type f \( -name '.env' -o -name '*.db' -o -name '*.sqlite*' -o -name '*.xlsx' -o -iname '*answer*key*' \) | grep -q .; then
  echo "Refusing to publish restricted files." >&2
  exit 1
fi

echo "Assessment microsite staged in assessment-public/ using the explicit file allowlist."
