#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
publish_dir="$repo_root/assessment-public"
if [[ -L "$publish_dir" ]]; then echo "Refusing to stage the public site through a symlink." >&2; exit 1; fi
mkdir -p "$publish_dir/assets"
for file in index.html awards.html syllabus.html sample-papers.html faqs.html contact.html login.html team-prelaunch.html styles.css site.js; do
  [[ -f "$repo_root/$file" ]] || { echo "Missing required public file: $file" >&2; exit 1; }
  cp "$repo_root/$file" "$publish_dir/$file"
done
for file in assets/awards-hero.svg assets/contact-hero.svg assets/faq-hero.svg assets/favicon.svg assets/handshake.svg assets/nurse-tech.svg assets/qualinova-logo.png assets/sample-hero.svg assets/sutravya-logo.png assets/syllabus-hero.svg assets/hero-registration.webp assets/hero-free.webp assets/hero-talent.webp assets/healthcare-talent-search-og.jpg; do
  [[ -f "$repo_root/$file" ]] || { echo "Missing required public asset: $file" >&2; exit 1; }
  cp "$repo_root/$file" "$publish_dir/$file"
done
allowed='./index.html|./awards.html|./syllabus.html|./sample-papers.html|./faqs.html|./contact.html|./login.html|./team-prelaunch.html|./styles.css|./site.js|./assets/awards-hero.svg|./assets/contact-hero.svg|./assets/faq-hero.svg|./assets/favicon.svg|./assets/handshake.svg|./assets/nurse-tech.svg|./assets/qualinova-logo.png|./assets/sample-hero.svg|./assets/sutravya-logo.png|./assets/syllabus-hero.svg|./assets/hero-registration.webp|./assets/hero-free.webp|./assets/hero-talent.webp|./assets/healthcare-talent-search-og.jpg'
while IFS= read -r relative_path; do
  case "|$allowed|" in *"|$relative_path|"*) ;; *) echo "Unexpected file in public site bundle: $relative_path" >&2; exit 1 ;; esac
done < <(cd "$publish_dir" && find . -type f -print | sort)
if find "$publish_dir" -type f \( -name '.env' -o -name '*.db' -o -name '*.sqlite*' -o -name '*.xlsx' -o -iname '*answer*key*' \) | grep -q .; then
  echo "Refusing to publish restricted files." >&2; exit 1
fi
echo "Assessment microsite staged in assessment-public/ using the explicit file allowlist."
