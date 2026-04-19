# Clone the empty repo
git clone https://github.com/<your-username>/governed-ai-data-access.git
cd governed-ai-data-access

# Unzip the bundle; the -j flag strips the top-level directory so files land
# directly in the repo root rather than in a nested governed-ai-data-access-starter/
# subfolder. We use a staging dir because -j also flattens all directories,
# which is not what we want for docs/ scripts/ spec/.
unzip ../governed-ai-data-access-starter.zip -d /tmp/starter
cp -r /tmp/starter/governed-ai-data-access-starter/. .
rm -rf /tmp/starter

# Add a .gitignore before the first commit so we do not track build artifacts
cat > .gitignore <<'EOF'
# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/

# dbt
dataset/dbt/target/
dataset/dbt/dbt_packages/
dataset/dbt/logs/
dataset/dbt/profiles.yml

# Build artifacts derivable from the workbook
spec/generated/

# Synthea output
tmp/

# Local env and secrets
.envrc
*.key
*.json
!package.json
!package-lock.json

# OS / editor cruft
.DS_Store
.idea/
.vscode/
EOF

git add .
git status                    # confirm what is staged before committing
git commit -m "Initial scaffolding: pipeline plan, spec, scripts, Makefile"
git push origin main