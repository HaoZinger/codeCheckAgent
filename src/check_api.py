#!/usr/bin/env python3
"""Quick API connectivity test for CodeCheckAgent providers."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI


def test_provider(name: str, api_key: str, base_url: str, model: str):
    """Test a single provider with a minimal request."""
    print(f"\n{'='*50}")
    print(f"  Testing: {name}")
    print(f"  Model:   {model}")
    print(f"  Base:    {base_url or '(OpenAI default)'}")
    print(f"{'='*50}")

    if not api_key:
        print("  SKIP: no API key set")
        return False

    masked = api_key[:8] + "..." if len(api_key) > 8 else "***"
    print(f"  Key:     {masked}")

    try:
        kwargs = {"api_key": api_key, "timeout": 30.0}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say hello in one word."}],
            max_tokens=20,
            temperature=0,
        )

        content = response.choices[0].message.content
        finish = response.choices[0].finish_reason

        if content:
            print(f"  [OK] Response: {content!r}")
            print(f"  [OK] Finish:   {finish}")
            return True
        else:
            print(f"  [FAIL] Empty response (finish_reason={finish})")
            return False

    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    import argparse
    from src.config import PROVIDER_PRESETS

    p = argparse.ArgumentParser(description="Test LLM provider connectivity")
    p.add_argument("--provider", "-p", default="deepseek-v4",
                   choices=list(PROVIDER_PRESETS.keys()),
                   help="Provider to test")
    p.add_argument("--model", "-m", default=None,
                   help="Model name (overrides preset default)")
    p.add_argument("--api-key", "-k", default=None,
                   help="API key")
    p.add_argument("--api-base", default=None,
                   help="API base URL (overrides preset)")
    args = p.parse_args()

    preset = PROVIDER_PRESETS[args.provider]
    api_key = args.api_key or os.environ.get(preset.api_key_env) or os.environ.get("OPENAI_API_KEY")
    base_url = args.api_base or preset.api_base
    model = args.model or preset.default_model

    if not api_key:
        print(f"ERROR: No API key found for {args.provider}")
        print(f"Set {preset.api_key_env} environment variable or use --api-key")
        sys.exit(1)

    ok = test_provider(args.provider, api_key, base_url, model)

    if ok:
        print(f"\n[OK] {args.provider} is working correctly!")
        sys.exit(0)
    else:
        print(f"\n[FAIL] {args.provider} connection failed.")
        print(f"Tips:")
        print(f"  1. Verify the API key is correct")
        print(f"  2. Check the model name: '{model}'")
        print(f"  3. Try --model deepseek-chat (latest DeepSeek model)")
        print(f"  4. Check the API base URL: {base_url}")
        sys.exit(1)