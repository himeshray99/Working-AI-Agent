import base64
import os
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image


MODEL_DEFAULT = "@cf/black-forest-labs/flux-2-klein-9b"


def _cloudflare_credentials():
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not api_token:
        raise RuntimeError(
            "Cloudflare credentials missing. Set CLOUDFLARE_ACCOUNT_ID and "
            "CLOUDFLARE_API_TOKEN in your local .env file."
        )
    return account_id, api_token


def _download_reference(url: str) -> bytes:
    response = requests.get(
        url, timeout=45, headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()
    image = Image.open(BytesIO(response.content)).convert("RGB")
    # FLUX.2 Klein reference images must be small; keep within 480x480.
    image.thumbnail((480, 480))
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def generate_with_cloudflare(
    sku: str, image_url: str, prompt: str, output_dir: Path
) -> str:
    account_id, api_token = _cloudflare_credentials()
    model = os.getenv("CLOUDFLARE_IMAGE_MODEL", MODEL_DEFAULT)
    image_bytes = _download_reference(image_url)

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{model}"
    )
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {api_token}"},
        data={"prompt": prompt, "width": "1024", "height": "768"},
        files={"input_image_0": ("product.png", image_bytes, "image/png")},
        timeout=int(os.getenv("CLOUDFLARE_IMAGE_TIMEOUT", "300")),
    )
    if not response.ok:
        # Do not include response headers or request credentials in errors.
        raise RuntimeError(
            f"Cloudflare image request failed with HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError("Cloudflare returned an unsuccessful image-generation response.")
    image_b64 = (payload.get("result") or {}).get("image")
    if not image_b64:
        raise RuntimeError("Cloudflare response did not contain a generated image.")
    image_data = base64.b64decode(image_b64)

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_sku = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(sku))
    final_path = output_dir / f"{safe_sku}.png"
    final_path.write_bytes(image_data)
    return str(final_path)


def run_image_agent(product: dict, output_dir: Path):
    sku = str(product.get("sku") or product.get("SKU") or "unknown")
    image_url = product.get("Image URL 1") or product.get("image_url")
    if not image_url or not str(image_url).startswith(("https://", "http://")):
        return {"sku": sku, "status": "skipped", "reason": "No valid source image URL"}

    prompt = (
        "Use the furniture in reference image 0 as the product reference. Preserve its "
        "recognisable design, silhouette, upholstery colour, materials, proportions and "
        "visible features as closely as possible. Place it naturally in a tasteful modern "
        "home interior with realistic lighting and shadows. Photorealistic commercial "
        "furniture lifestyle photography. Do not add logos, text, or accessories that "
        "are not supported by the reference. The result is a lifestyle interpretation; "
        "review product fidelity before publication."
    )
    try:
        path = generate_with_cloudflare(sku, str(image_url), prompt, output_dir)
        return {"sku": sku, "status": "generated", "path": path,
                "provider": "Cloudflare Workers AI", "model": os.getenv(
                    "CLOUDFLARE_IMAGE_MODEL", MODEL_DEFAULT
                )}
    except Exception as exc:
        return {"sku": sku, "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}"}
