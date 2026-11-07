"""Automated deployment script for Hugging Face Spaces."""

import argparse
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi, create_repo


def deploy_to_hf_space(token: str, space_id: str, is_private: bool = False) -> str:
    api = HfApi(token=token)

    print(f"Ensuring Space repository '{space_id}' exists...")
    try:
        create_repo(
            repo_id=space_id,
            repo_type="space",
            space_sdk="docker",
            private=is_private,
            token=token,
            exist_ok=True,
        )
        print("Space repository confirmed.")
    except Exception as exc:
        print(f"Notice during create_repo: {exc}")

    print("Uploading ResearchOS project files to Hugging Face Space...")
    root_dir = Path(__file__).resolve().parent.parent

    # Upload repository folder excluding local caches, virtual environments and locks
    ignore_patterns = [
        ".venv/**",
        ".git/**",
        "__pycache__/**",
        "*.pyc",
        ".pytest_cache/**",
        ".ruff_cache/**",
        ".researchos/locks/**",
    ]

    api.upload_folder(
        folder_path=str(root_dir),
        repo_id=space_id,
        repo_type="space",
        ignore_patterns=ignore_patterns,
        token=token,
    )

    space_url = f"https://huggingface.co/spaces/{space_id}"
    sse_url = f"https://{space_id.replace('/', '-')}.hf.space/sse"
    print("\n========================================================")
    print("SUCCESS: Deployed to Hugging Face Spaces!")
    print(f"Space Web URL:  {space_url}")
    print(f"MCP SSE URL:    {sse_url}")
    print("========================================================\n")
    return sse_url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy ResearchOS to Hugging Face Spaces")
    parser.add_argument("--token", default=os.environ.get("HF_TOKEN"), help="Hugging Face User Access Token (write)")
    parser.add_argument("--space", required=True, help="Space ID (e.g. username/researchos-mcp)")
    parser.add_argument("--private", action="store_true", help="Make Space private")
    args = parser.parse_args()

    if not args.token:
        print("Error: Hugging Face Token required via --token or HF_TOKEN env var.", file=sys.stderr)
        sys.exit(1)

    deploy_to_hf_space(token=args.token, space_id=args.space, is_private=args.private)
