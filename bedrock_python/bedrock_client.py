"""Thin wrapper around AWS Bedrock InvokeModel for Anthropic Claude models."""
import json
import os

from dotenv import load_dotenv

load_dotenv()

MAX_CHARS = 150_000


class BedrockError(Exception):
    def __init__(self, message: str, error_type: str = "unknown"):
        super().__init__(message)
        self.error_type = error_type


def _client():
    import boto3
    return boto3.client(
        "bedrock-runtime",
        region_name=os.environ["AWS_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
    )


def invoke(prompt: str, max_tokens: int = 4096) -> str:
    """Send a prompt to Bedrock and return the text response."""
    if len(prompt) > MAX_CHARS:
        prompt = prompt[:MAX_CHARS] + "\n\n[TEXT TRUNCATED]"

    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        client = _client()
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    except ImportError:
        raise BedrockError("boto3 is not installed. Run: pip install boto3", "import_error")

    except Exception as e:
        err = str(e)
        if "NoCredentialsError" in type(e).__name__ or "PartialCredentials" in type(e).__name__:
            raise BedrockError(
                "AWS credentials not found. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env",
                "credentials",
            )
        if "AccessDenied" in err or "UnauthorizedOperation" in err:
            region = os.environ.get("AWS_REGION", "?")
            raise BedrockError(
                f"Access denied to model {model_id}. "
                f"Enable model access in AWS Console → Bedrock → Model Access → {region}",
                "access_denied",
            )
        if "ValidationException" in err:
            # Retry with aggressively truncated prompt
            short_prompt = prompt[:50_000] + "\n\n[TEXT TRUNCATED FOR LENGTH]"
            body["messages"][0]["content"] = short_prompt
            try:
                client = _client()
                response = client.invoke_model(
                    modelId=model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body),
                )
                result = json.loads(response["body"].read())
                return result["content"][0]["text"]
            except Exception as e2:
                raise BedrockError(f"Bedrock ValidationException: {e2}", "validation")
        raise BedrockError(f"Bedrock error: {err}", "unknown")
