"""
PolitmaTrader X Posting Service

A lightweight FastAPI microservice that receives webhook payloads
from the PolitmaTrader marketing system and posts them to X (Twitter).

Deploy to Railway alongside the main marketing system.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
import urllib.parse

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------
X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # optional inbound verification

logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("xposter")

app = FastAPI(title="PolitmaTrader X Poster", version="1.0.0")


# ---------------------------------------------------------------------------
# OAuth 1.0a signature (required by X API v2 for user-context posts)
# ---------------------------------------------------------------------------
def _percent_encode(s: str) -> str:
      return urllib.parse.quote(str(s), safe="")


def _build_oauth_header(method: str, url: str, body_params: dict | None = None) -> str:
      """Build a complete OAuth 1.0a Authorization header."""
      import secrets

    oauth_params = {
              "oauth_consumer_key": X_API_KEY,
              "oauth_nonce": secrets.token_hex(16),
              "oauth_signature_method": "HMAC-SHA1",
              "oauth_timestamp": str(int(time.time())),
              "oauth_token": X_ACCESS_TOKEN,
              "oauth_version": "1.0",
    }

    # Combine all params for signature base
    all_params = {**oauth_params}
    if body_params:
              all_params.update(body_params)

    # Sort and encode
    sorted_params = sorted(all_params.items())
    param_string = "&".join(f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted_params)

    # Signature base string
    base_string = f"{method.upper()}&{_percent_encode(url)}&{_percent_encode(param_string)}"

    # Signing key
    signing_key = f"{_percent_encode(X_API_SECRET)}&{_percent_encode(X_ACCESS_TOKEN_SECRET)}"

    # HMAC-SHA1 signature
    import hashlib
    import base64
    signature = base64.b64encode(
              hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()

    oauth_params["oauth_signature"] = signature

    # Build header string
    header_parts = ", ".join(
              f'{_percent_encode(k)}="{_percent_encode(v)}"'
              for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class PostRequest(BaseModel):
      asset_id: Optional[str] = None
      platform: Optional[str] = None
      format: Optional[str] = None
      hook: str
      body: str
      cta: str
      hashtags: str = ""
      visual_brief: Optional[str] = None
      scheduled_time: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def root():
      return {"service": "PolitmaTrader X Poster", "status": "ok"}


@app.get("/health")
def health():
      configured = all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET])
      return {
          "status": "ok" if configured else "unconfigured",
          "x_api_configured": configured,
      }


@app.post("/post")
async def create_post(payload: PostRequest, request: Request):
      """Receive a webhook payload and post it to X."""

    # Verify webhook signature if configured
      if WEBHOOK_SECRET:
                raw_body = await request.body()
                signature = request.headers.get("X-Webhook-Signature", "")
                expected = hmac.new(
                    WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(expected, signature):
                              raise HTTPException(status_code=401, detail="Invalid webhook signature")

            # Verify X credentials are configured
            if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
                      raise HTTPException(status_code=500, detail="X API credentials not configured")

    # Build tweet text
    parts = [payload.hook, "", payload.body, "", payload.cta]
    if payload.hashtags:
              parts.extend(["", payload.hashtags])
          tweet_text = "\n".join(parts)

    # X has a 280 character limit - truncate if needed
    if len(tweet_text) > 280:
              # Keep hook + cta + hashtags, shorten body
              reserved = f"{payload.hook}\n\n"
              suffix = f"\n\n{payload.cta}"
              if payload.hashtags:
                            suffix += f"\n\n{payload.hashtags}"
                        max_body = 280 - len(reserved) - len(suffix) - 3  # 3 for "..."
        if max_body > 20:
                      shortened_body = payload.body[:max_body].rstrip() + "..."
                      tweet_text = f"{reserved}{shortened_body}{suffix}"
else:
            # Just hook + cta
              tweet_text = f"{payload.hook}\n\n{payload.cta}"
            if len(tweet_text) > 280:
                              tweet_text = tweet_text[:277] + "..."

    logger.info("Posting tweet (%d chars) for asset %s", len(tweet_text), payload.asset_id)

    # Post to X API v2
    url = "https://api.twitter.com/2/tweets"
    auth_header = _build_oauth_header("POST", url)

    try:
              async with httpx.AsyncClient(timeout=30.0) as client:
                            response = await client.post(
                                              url,
                                              json={"text": tweet_text},
                                              headers={
                                                                    "Authorization": auth_header,
                                                                    "Content-Type": "application/json",
                                              },
                            )

            if response.status_code == 201:
                              data = response.json()
                              tweet_id = data.get("data", {}).get("id", "unknown")
                              logger.info("Tweet posted successfully: %s", tweet_id)
                              return {
                                  "external_post_id": tweet_id,
                                  "status": "published",
                                  "message": f"Posted to X: https://x.com/politmatrader/status/{tweet_id}",
                              }
else:
                error_detail = response.text[:500]
                  logger.error("X API error %s: %s", response.status_code, error_detail)
                raise HTTPException(
                                      status_code=502,
                                      detail=f"X API returned {response.status_code}: {error_detail}",
                )

except httpx.TimeoutException:
        logger.error("X API request timed out")
        raise HTTPException(status_code=504, detail="X API request timed out")
