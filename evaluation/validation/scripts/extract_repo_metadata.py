#!/usr/bin/env python3
"""
RDIP Silver Standard — Layer A: Automated Repository Metadata Extraction

Parses GitHub repos to extract RDIP-mappable metadata:
  - requirements.txt → SoftwareDependency (name + version)
  - Dockerfile → EnvironmentSpec (base image, CUDA)
  - environment.yml → conda deps + environment
  - setup.py / pyproject.toml → SoftwareApplication metadata
  - *.py files → random seed values (grep pattern)
  - GitHub API → license, contributors, stars

Usage:
  python extract_repo_metadata.py --csv repo_list.csv --output-dir silver/repos
  python extract_repo_metadata.py --csv repo_list.csv --output-dir silver/repos --limit 5  # test on 5
"""

import csv
import json
import os
import re
import subprocess
import sys
import argparse
from pathlib import Path


def parse_requirements(req_path: str) -> list:
    """Parse requirements.txt into (name, version, constraint) tuples."""
    deps = []
    if not os.path.exists(req_path):
        return deps
    with open(req_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-'):
                continue
            # Handle: package==1.0, package>=1.0, package~=1.0, package
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)\s*([><=~!]+)?\s*([0-9a-zA-Z\.\*]+)?', line)
            if match:
                name = match.group(1)
                constraint = match.group(2) or ''
                version = match.group(3) or ''
                deps.append({
                    "name": name,
                    "version": version,
                    "constraint": constraint,
                    "source": "requirements.txt"
                })
    return deps


def parse_dockerfile(docker_path: str) -> dict:
    """Parse Dockerfile for base image, CUDA, OS info."""
    env = {"source": "Dockerfile"}
    if not os.path.exists(docker_path):
        return env
    with open(docker_path) as f:
        content = f.read()
    # FROM directive
    from_match = re.search(r'^FROM\s+(.+?)(?:\s+AS|\s*$)', content, re.MULTILINE)
    if from_match:
        env["base_image"] = from_match.group(1).strip()
        img = env["base_image"].lower()
        # Extract CUDA version from image name
        cuda_match = re.search(r'cuda[:\-_]?(\d+\.\d+(?:\.\d+)?)', img)
        if cuda_match:
            env["cuda_version"] = cuda_match.group(1)
        # Extract Python version
        py_match = re.search(r'python[:\-_]?(\d+\.\d+)', img)
        if py_match:
            env["python_version"] = py_match.group(1)
        # Extract OS hints
        if 'ubuntu' in img:
            os_match = re.search(r'ubuntu[:\-_]?(\d+\.\d+)', img)
            env["os"] = f"Ubuntu {os_match.group(1)}" if os_match else "Ubuntu"
        elif 'centos' in img:
            env["os"] = "CentOS"
        elif 'alpine' in img:
            env["os"] = "Alpine"
    return env


def parse_conda_env(env_path: str) -> dict:
    """Parse environment.yml / environment.yaml for conda dependencies."""
    result = {"deps": [], "source": "conda"}
    if not os.path.exists(env_path):
        return result
    try:
        # Simple YAML parsing without PyYAML
        with open(env_path) as f:
            content = f.read()
        # Extract dependencies section
        in_deps = False
        in_pip = False
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('dependencies:'):
                in_deps = True
                continue
            if in_deps and stripped.startswith('- pip:'):
                in_pip = True
                continue
            if in_deps and not stripped.startswith('-') and not stripped.startswith('#') and stripped and not in_pip:
                in_deps = False
                in_pip = False
                continue
            if in_deps and stripped.startswith('- '):
                pkg = stripped[2:].strip()
                if '=' in pkg:
                    parts = re.split(r'[=<>]+', pkg)
                    name = parts[0]
                    version = parts[-1] if len(parts) > 1 else ''
                else:
                    name = pkg
                    version = ''
                result["deps"].append({"name": name, "version": version})
        # Extract name
        name_match = re.search(r'^name:\s*(.+)', content, re.MULTILINE)
        if name_match:
            result["env_name"] = name_match.group(1).strip()
    except Exception:
        pass
    return result


def find_seeds(repo_dir: str) -> list:
    """Grep for random seed patterns in Python files."""
    seeds = []
    seed_patterns = [
        r'(?:random\.seed|np\.random\.seed|torch\.manual_seed|'
        r'torch\.cuda\.manual_seed|seed_everything|set_seed|'
        r'SEED\s*=|seed\s*=)\s*\(?\s*(\d+)',
    ]
    try:
        for root, dirs, files in os.walk(repo_dir):
            # Skip hidden dirs and common non-code dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                      ('__pycache__', 'node_modules', '.git', 'venv', 'env')]
            for fname in files:
                if fname.endswith('.py'):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, errors='ignore') as f:
                            content = f.read()
                        for pattern in seed_patterns:
                            for match in re.finditer(pattern, content):
                                seed_val = match.group(1)
                                seeds.append({
                                    "value": seed_val,
                                    "file": os.path.relpath(fpath, repo_dir),
                                    "context": match.group(0)[:80]
                                })
                    except Exception:
                        continue
    except Exception:
        pass
    # Deduplicate by value
    seen = set()
    unique = []
    for s in seeds:
        if s["value"] not in seen:
            seen.add(s["value"])
            unique.append(s)
    return unique


def extract_repo(study_id: str, repo_url: str, clone_dir: str) -> dict:
    """Extract all metadata from a single repo."""
    result = {
        "study_id": study_id,
        "repo_url": repo_url,
        "software_dependencies": [],
        "environment": {},
        "conda": {},
        "seeds": [],
        "license": "",
        "errors": []
    }

    # Shallow clone
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", repo_url, clone_dir],
            timeout=120, capture_output=True, text=True
        )
    except Exception as e:
        result["errors"].append(f"Clone failed: {e}")
        return result

    if not os.path.exists(clone_dir):
        result["errors"].append("Clone directory not created")
        return result

    # Parse requirements.txt
    for req_name in ['requirements.txt', 'requirements/base.txt', 'requirements/main.txt']:
        req_path = os.path.join(clone_dir, req_name)
        deps = parse_requirements(req_path)
        if deps:
            result["software_dependencies"].extend(deps)
            break

    # Parse Dockerfile
    for docker_name in ['Dockerfile', 'docker/Dockerfile', '.devcontainer/Dockerfile']:
        docker_path = os.path.join(clone_dir, docker_name)
        if os.path.exists(docker_path):
            result["environment"] = parse_dockerfile(docker_path)
            break

    # Parse conda environment
    for env_name in ['environment.yml', 'environment.yaml', 'conda_env.yml']:
        env_path = os.path.join(clone_dir, env_name)
        if os.path.exists(env_path):
            result["conda"] = parse_conda_env(env_path)
            break

    # Find seeds
    result["seeds"] = find_seeds(clone_dir)

    # Check license
    for lic_name in ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'COPYING']:
        lic_path = os.path.join(clone_dir, lic_name)
        if os.path.exists(lic_path):
            with open(lic_path, errors='ignore') as f:
                first_lines = f.read(500)
            if 'MIT' in first_lines:
                result["license"] = "MIT"
            elif 'Apache' in first_lines:
                result["license"] = "Apache-2.0"
            elif 'GNU GENERAL PUBLIC' in first_lines:
                result["license"] = "GPL"
            elif 'BSD' in first_lines:
                result["license"] = "BSD"
            else:
                result["license"] = "Other"
            break

    # Cleanup
    subprocess.run(["rm", "-rf", clone_dir], capture_output=True)

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract repo metadata for RDIP silver standard")
    parser.add_argument("--csv", required=True, help="Path to repo_list.csv")
    parser.add_argument("--output-dir", required=True, help="Output directory for JSON files")
    parser.add_argument("--limit", type=int, default=0, help="Limit to N repos (0=all)")
    parser.add_argument("--clone-dir", default="/tmp/rdip_clones", help="Temp dir for cloning")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.clone_dir, exist_ok=True)

    with open(args.csv, newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if args.limit > 0:
        rows = rows[:args.limit]

    print(f"Processing {len(rows)} repositories...\n")

    for i, row in enumerate(rows):
        study_id = row.get('study_id', '').strip()
        repo_url = row.get('repo_url', '').strip()

        if not study_id or not repo_url:
            continue

        output_path = os.path.join(args.output_dir, f"{study_id}_repo.json")
        if os.path.exists(output_path):
            print(f"  [{i+1}/{len(rows)}] SKIP {study_id} (already extracted)")
            continue

        print(f"  [{i+1}/{len(rows)}] {study_id}: {repo_url}")
        clone_path = os.path.join(args.clone_dir, study_id)

        result = extract_repo(study_id, repo_url, clone_path)

        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)

        n_deps = len(result["software_dependencies"])
        n_seeds = len(result["seeds"])
        has_env = bool(result["environment"].get("base_image"))
        print(f"           → {n_deps} deps, {n_seeds} seeds, env={'yes' if has_env else 'no'}, "
              f"license={result['license'] or 'none'}")

    print(f"\nDone. Results in {args.output_dir}/")


if __name__ == "__main__":
    main()
