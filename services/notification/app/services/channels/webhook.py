"""WeChat Work and DingTalk webhook channels."""

import logging

import httpx

log = logging.getLogger(__name__)


async def send_wechat(*, webhook_url: str, title: str, body: str) -> None:
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"## {title}\n\n{body}",
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
    log.info("wechat_webhook_sent", extra={"status_code": resp.status_code})


async def send_dingtalk(*, webhook_url: str, title: str, body: str) -> None:
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"## {title}\n\n{body}",
        },
        "at": {"isAtAll": False},
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
    log.info("dingtalk_webhook_sent", extra={"status_code": resp.status_code})
