"""Standalone Bedrock connectivity check. Run before using bedrock_python/."""
import os
import sys

REQUIRED_KEYS = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID"]
WIDTH = 50


def _pass(msg=""):
    print(f"  \033[32mPASS\033[0m  {msg}")


def _fail(msg=""):
    print(f"  \033[31mFAIL\033[0m  {msg}")


def _step(n, total, desc):
    print(f"[{n}/{total}] {desc}...", end="", flush=True)


def main():
    print("=" * WIDTH)
    print("  FlightMode.ai — Bedrock Connectivity Check")
    print("=" * WIDTH)

    # Step 1: .env and required keys
    _step(1, 6, "Checking .env / env vars")
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
    if missing:
        _fail(f"Missing keys: {', '.join(missing)}")
        print(f"\n  FIX: Add these to your .env file in the project root.")
        sys.exit(1)
    _pass(f"All {len(REQUIRED_KEYS)} keys present")

    # Step 2: boto3
    _step(2, 6, "Checking boto3")
    try:
        import boto3
        _pass(f"boto3 {boto3.__version__}")
    except ImportError:
        _fail("boto3 not installed")
        print("\n  FIX: pip install boto3")
        sys.exit(1)

    # Step 3: pdfplumber
    _step(3, 6, "Checking pdfplumber")
    try:
        import pdfplumber
        _pass(f"pdfplumber {pdfplumber.__version__}")
    except ImportError:
        _fail("pdfplumber not installed")
        print("\n  FIX: pip install pdfplumber")
        sys.exit(1)

    # Step 4: AWS credentials via STS
    _step(4, 6, "Checking AWS credentials (STS)")
    try:
        sts = boto3.client(
            "sts",
            region_name=os.environ["AWS_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        identity = sts.get_caller_identity()
        account = identity.get("Account", "?")
        arn = identity.get("Arn", "?")
        _pass(f"account={account}  arn=...{arn[-30:]}")
    except Exception as e:
        _fail(str(e))
        print("\n  FIX: Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correct.")
        sys.exit(1)

    # Step 5: Bedrock model availability
    _step(5, 6, "Checking Bedrock model access")
    model_id = os.environ["BEDROCK_MODEL_ID"]
    try:
        bedrock = boto3.client(
            "bedrock",
            region_name=os.environ["AWS_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        response = bedrock.list_foundation_models()
        model_ids = [m["modelId"] for m in response.get("modelSummaries", [])]
        if model_id in model_ids:
            _pass(f"{model_id} found")
        else:
            # Model may still be invokable even if not listed (cross-region inference)
            _pass(f"Listed {len(model_ids)} models (target model not in list — will try invoke)")
    except Exception as e:
        err = str(e)
        if "AccessDenied" in err or "UnauthorizedOperation" in err:
            _fail("AccessDeniedException listing models")
            print(f"\n  FIX: Go to AWS Console → Bedrock → Model Access → {os.environ['AWS_REGION']}")
            print(f"       Request access to the model: {model_id}")
            print("       This can take 5–30 minutes to activate.")
        else:
            _fail(err[:100])
        sys.exit(1)

    # Step 6: Test invoke
    _step(6, 6, "Test inference call")
    try:
        import json
        bedrock_rt = boto3.client(
            "bedrock-runtime",
            region_name=os.environ["AWS_REGION"],
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "Say OK"}],
        }
        resp = bedrock_rt.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        result = json.loads(resp["body"].read())
        reply = result["content"][0]["text"].strip()
        _pass(f'response: "{reply}"')
    except Exception as e:
        err = str(e)
        _fail(err[:120])
        if "AccessDenied" in err:
            print(f"\n  FIX: Enable model access for {model_id} in the AWS Bedrock console.")
            print(f"       Region: {os.environ['AWS_REGION']}")
        elif "ValidationException" in err:
            print(f"\n  FIX: Model ID may be wrong: {model_id}")
            print("       Check available models in Bedrock console for your region.")
        sys.exit(1)

    print()
    print("=" * WIDTH)
    print("  All checks passed.")
    print(f"  Run: venv/Scripts/python -m bedrock_python")
    print("=" * WIDTH)
    sys.exit(0)


if __name__ == "__main__":
    main()
