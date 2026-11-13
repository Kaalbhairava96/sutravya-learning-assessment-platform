#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
publish_dir="$repo_root/assessment-public"
if [[ -L "$publish_dir" ]]; then echo "Refusing to stage the public site through a symlink." >&2; exit 1; fi
rm -rf "$publish_dir"
mkdir -p "$publish_dir/assets"
source_files=(index.html awards.html syllabus.html hackathon.html sample-papers.html mock-test.html faqs.html contact.html login.html register.html registration.js team-prelaunch.html admin-login.html admin-login.js admin-portal.js admin-portal.css admin.html admin.js exam.html exam.js styles.css layout.css site.js sample-papers.js mock-test.js question-bank.js)
asset_files=(brand-home.svg brand-home-pathways.svg brand-home-learning.svg brand-home-hackathon.svg brand-home-recognition.svg brand-registration.svg brand-syllabus.svg brand-syllabus-map.svg brand-samples.svg brand-sample-explanation.svg brand-mock.svg brand-awards.svg brand-launchpad.svg brand-hackathon.svg brand-faq.svg brand-contact.svg brand-login.svg brand-team.svg brand-admin.svg brand-exam.svg brand-award-podium.svg brand-hackathon-award.svg favicon.svg sutravya-logo.png qualinova-logo.png healthcare-talent-search-og.jpg)
allowed=""
for file in "${source_files[@]}"; do
  [[ -f "$repo_root/$file" ]] || { echo "Missing required public file: $file" >&2; exit 1; }
  cp "$repo_root/$file" "$publish_dir/$file"
  allowed+="|./$file"
done
for file in "${asset_files[@]}"; do
  [[ -f "$repo_root/assets/$file" ]] || { echo "Missing required public asset: assets/$file" >&2; exit 1; }
  cp "$repo_root/assets/$file" "$publish_dir/assets/$file"
  allowed+="|./assets/$file"
done
while IFS= read -r relative_path; do
  case "$allowed|" in *"|$relative_path|"*) ;; *) echo "Unexpected file in public site bundle: $relative_path" >&2; exit 1 ;; esac
done < <(cd "$publish_dir" && find . -type f -print | sort)
if find "$publish_dir" -type f \( -name '.env' -o -name '*.db' -o -name '*.sqlite*' -o -name '*.xlsx' -o -iname '*answer*key*' \) | grep -q .; then
  echo "Refusing to publish restricted files." >&2; exit 1
fi
echo "Assessment microsite staged in assessment-public/ using the explicit file allowlist."
