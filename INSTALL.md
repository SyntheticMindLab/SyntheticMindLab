# Install (GitHub web or mobile browser)

## 0. Repo name (important)
A profile README only shows on github.com/SyntheticMindLab if the repo is named EXACTLY `SyntheticMindLab`
(your current repo is `SynthericMind`, which will not render on the profile).
Rename it: repo → Settings → General → Repository name → `SyntheticMindLab`. Keep it Public.
(If SyntheticMindLab is an ORGANIZATION, not a user, this kit's live stats won't work — tell me and I'll adapt it.)

## 1. Upload files (repo → Add file → Upload files; use the desktop-site view on mobile)
Keep this exact structure:

    SyntheticMindLab/
    ├── README.md
    ├── config.json
    ├── .github/workflows/dashboard.yml
    ├── .github/workflows/snake.yml
    ├── scripts/build_dashboard.py
    └── assets/src/{portrait.jpg, globe.jpg, worldmap.jpg}

GitHub's uploader drops hidden folders on some phones. If `.github` is missing, use Add file → Create new file,
type `.github/workflows/dashboard.yml` as the name (slashes create folders), paste the contents, commit. Repeat for snake.yml.

## 2. Allow Actions to write
Repo → Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save.

## 3. Run both workflows once
Repo → Actions tab → "Update LAB OS dashboard" → Run workflow. Then "Generate contribution snake" → Run workflow.
Order: either. When both are green, `assets/generated/*.svg` and the `output` branch exist and the README renders fully.

## 4. Optional: count private contributions
Create a classic token (scope `read:user`) → repo Settings → Secrets and variables → Actions → new secret `PROFILE_TOKEN`.

## 5. Customize
`config.json` → tagline lines, extra Skill Icons ids (https://skillicons.dev), max icons.
Language icons are auto-detected from your public repos.
