"""Thin wrapper around AWS Bedrock InvokeModel for Anthropic Claude models."""
import base64
import json
import os

from dotenv import load_dotenv

load_dotenv()

MAX_CHARS = 150_000
# Bedrock inline document limit is 4.5 MB base64-encoded (~3.3 MB raw)
PDF_NATIVE_MAX_BYTES = 3_300_000


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


def _model_id() -> str:
    return os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")


def _call(body: dict) -> str:
    """Execute a Bedrock invoke_model call and return the text content."""
    model_id = _model_id()
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
        if "ValidationException" in err and "document" in err.lower():
            raise BedrockError(
                f"Model {model_id} does not support native PDF document blocks. "
                "Upgrade to anthropic.claude-3-5-haiku-20241022-v1:0 or newer.",
                "document_unsupported",
            )
        raise BedrockError(f"Bedrock error: {err}", "unknown")


def invoke(prompt: str, max_tokens: int = 4096) -> str:
    """Send a text prompt to Bedrock and return the response."""
    if len(prompt) > MAX_CHARS:
        prompt = prompt[:MAX_CHARS] + "\n\n[TEXT TRUNCATED]"

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        return _call(body)
    except BedrockError as e:
        if "validation" not in e.error_type:
            raise
        # Retry with aggressively truncated prompt on ValidationException
        body["messages"][0]["content"] = prompt[:50_000] + "\n\n[TEXT TRUNCATED FOR LENGTH]"
        return _call(body)


def invoke_with_pdf(pdf_bytes: bytes, prompt: str, max_tokens: int = 4096) -> str:
    """Send a PDF document directly to Bedrock alongside a text prompt.

    Claude reads the PDF natively — no text extraction needed. Falls back
    to ValueError if the PDF exceeds the inline size limit (caller should
    then use the text-extraction path instead).
    """
    if len(pdf_bytes) > PDF_NATIVE_MAX_BYTES:
        raise ValueError(
            f"PDF too large for native mode ({len(pdf_bytes)/1024:.0f} KB > "
            f"{PDF_NATIVE_MAX_BYTES/1024:.0f} KB limit). Use text-extraction fallback."
        )

    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }
    return _call(body)
