"""Gemini API client for image generation."""

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


class GeminiAPIError(Exception):
    """Raised when Gemini API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class GenerationResult:
    """Result from image generation."""

    image_data: bytes
    text_response: str | None = None


class GeminiClient:
    """Client for Gemini image generation API (Nano Banana Pro)."""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        timeout: float = 120.0,
        enable_google_search: bool = True,
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.enable_google_search = enable_google_search

    def generate_image_with_reference(
        self,
        prompt: str,
        reference_image_path: Path | None,
        aspect_ratio: str,
        image_size: str,
        additional_references: list[Path] | None = None,
    ) -> GenerationResult:
        """
        Generate an image using reference images (Nano Banana Pro).

        Args:
            prompt: Text prompt for generation
            reference_image_path: Path to primary reference image (or None)
            aspect_ratio: Target aspect ratio (e.g., "1:1", "21:9")
            image_size: Target size ("1K", "2K", "4K")
            additional_references: Optional list of additional reference images

        Returns:
            GenerationResult with image data

        Raises:
            GeminiAPIError: If API returns an error
        """
        # Build parts list with reference images first, then prompt
        parts: list[dict[str, Any]] = []

        # Add primary reference image if provided
        if reference_image_path:
            with open(reference_image_path, "rb") as f:
                ref_base64 = base64.b64encode(f.read()).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": ref_base64,
                }
            })

        # Add additional reference images (Nano Banana Pro supports up to 14)
        if additional_references:
            for ref_path in additional_references[:13]:  # Max 14 total
                with open(ref_path, "rb") as f:
                    ref_base64 = base64.b64encode(f.read()).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": ref_base64,
                    }
                })

        # Add the text prompt
        parts.append({"text": prompt})

        # Build request payload
        request: dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": image_size,
                },
            },
        }

        # Enable Google Search tool for real-world knowledge (Nano Banana Pro feature)
        if self.enable_google_search:
            request["tools"] = [{"google_search": {}}]

        # Make API request
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.api_url,
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=request,
            )

        if response.status_code != 200:
            raise GeminiAPIError(
                f"HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        data = response.json()

        if "error" in data:
            error_msg = data["error"].get("message", str(data["error"]))
            raise GeminiAPIError(f"API Error: {error_msg}")

        if "candidates" not in data:
            raise GeminiAPIError(f"Unexpected response format: {str(data)[:200]}")

        # Extract image and text from response
        image_data = None
        text_response = None

        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                image_data = base64.b64decode(part["inlineData"]["data"])
            elif "text" in part:
                text = part["text"].strip()
                if text:
                    text_response = text

        if image_data is None:
            raise GeminiAPIError("No image in response")

        return GenerationResult(image_data=image_data, text_response=text_response)
