"""
Alert Engine Service
Handles dispatching external notifications (e.g., Webhooks) when node events occur.
Includes automatic retry handling for HTTP 429 Too Many Requests.
"""
import httpx
import logging
import asyncio

from ..models.node import Node
from ..models.site import Site

logger = logging.getLogger(__name__)

# ==========================================
# 1. OFFLINE ALERTS
# ==========================================

async def send_discord_alert(webhook_url: str, node: Node, site: Site, retries: int = 3) -> None:
    payload = {
        "content": f"🚨 **EDGEHUB ALERT** 🚨\nNode **`{node.hostname}`** at site **`{site.name}`** is OFFLINE."
    }
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                if response.status_code == 429:
                    try:
                        wait_time = float(response.json().get("retry_after", 1.0))
                    except Exception:
                        wait_time = 1.0
                    logger.warning(f"⚠️ Discord Rate Limit (429) hit for node {node.hostname}. Retrying in {wait_time}s (Attempt {attempt + 1}/{retries})")
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                logger.info("Discord alert sent successfully for node: %s", node.hostname)
                return
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("Error sending Discord webhook for node %s after %d attempts: %s", node.hostname, retries, e)
                else:
                    await asyncio.sleep(1.0)


async def send_slack_alert(webhook_url: str, node: Node, site: Site, retries: int = 3) -> None:
    payload = {
        "text": f"🚨 *EDGEHUB ALERT* 🚨\nNode *`{node.hostname}`* at site *`{site.name}`* is OFFLINE."
    }
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                if response.status_code == 429:
                    wait_time = float(response.headers.get("Retry-After", 1.0))
                    logger.warning(f"⚠️ Slack Rate Limit (429) hit for node {node.hostname}. Retrying in {wait_time}s (Attempt {attempt + 1}/{retries})")
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                logger.info("Slack alert sent successfully for node: %s", node.hostname)
                return
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("Error sending Slack webhook for node %s after %d attempts: %s", node.hostname, retries, e)
                else:
                    await asyncio.sleep(1.0)


async def dispatch_offline_alerts(node: Node, site: Site) -> None:
    tasks = []
    if site.discord_webhook_url:
        tasks.append(send_discord_alert(site.discord_webhook_url, node, site))
    if site.slack_webhook_url:
        tasks.append(send_slack_alert(site.slack_webhook_url, node, site))
    if tasks:
        await asyncio.gather(*tasks)

# ==========================================
# 2. RECOVERY ALERTS
# ==========================================

async def send_discord_recovery(webhook_url: str, node: Node, site: Site, retries: int = 3) -> None:
    payload = {
        "content": f"✅ **EDGEHUB RECOVERY** ✅\nNode **`{node.hostname}`** at site **`{site.name}`** is back ONLINE."
    }
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                if response.status_code == 429:
                    try:
                        wait_time = float(response.json().get("retry_after", 1.0))
                    except Exception:
                        wait_time = 1.0
                    logger.warning(f"⚠️ Discord Rate Limit hit during recovery for node {node.hostname}. Retrying in {wait_time}s (Attempt {attempt + 1}/{retries})")
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                logger.info("Discord recovery alert sent successfully for node: %s", node.hostname)
                return
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("Error sending Discord recovery webhook for node %s after %d attempts: %s", node.hostname, retries, e)
                else:
                    await asyncio.sleep(1.0)


async def send_slack_recovery(webhook_url: str, node: Node, site: Site, retries: int = 3) -> None:
    payload = {
        "text": f"✅ *EDGEHUB RECOVERY* ✅\nNode *`{node.hostname}`* at site *`{site.name}`* is back ONLINE."
    }
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                if response.status_code == 429:
                    wait_time = float(response.headers.get("Retry-After", 1.0))
                    logger.warning(f"⚠️ Slack Rate Limit hit during recovery for node {node.hostname}. Retrying in {wait_time}s (Attempt {attempt + 1}/{retries})")
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                logger.info("Slack recovery alert sent successfully for node: %s", node.hostname)
                return
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("Error sending Slack recovery webhook for node %s after %d attempts: %s", node.hostname, retries, e)
                else:
                    await asyncio.sleep(1.0)


async def dispatch_recovery_alerts(node: Node, site: Site) -> None:
    tasks = []
    if site.discord_webhook_url:
        tasks.append(send_discord_recovery(site.discord_webhook_url, node, site))
    if site.slack_webhook_url:
        tasks.append(send_slack_recovery(site.slack_webhook_url, node, site))
    if tasks:
        await asyncio.gather(*tasks)

# ==========================================
# 3. METRIC ALERTS (CPU / TEMP / DISK)
# ==========================================

async def send_discord_metric(webhook_url: str, node_hostname: str, message: str, retries: int = 3) -> None:
    payload = {"content": message}
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                if response.status_code == 429:
                    try:
                        wait_time = float(response.json().get("retry_after", 1.0))
                    except Exception:
                        wait_time = 1.0
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                return
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("Discord metric alert error for node %s: %s", node_hostname, e)
                else:
                    await asyncio.sleep(1.0)


async def send_slack_metric(webhook_url: str, node_hostname: str, message: str, retries: int = 3) -> None:
    payload = {"text": message}
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                if response.status_code == 429:
                    wait_time = float(response.headers.get("Retry-After", 1.0))
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                return
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("Slack metric alert error for node %s: %s", node_hostname, e)
                else:
                    await asyncio.sleep(1.0)


async def dispatch_metric_alert(
    # ✅ Solo primitivi — nessun oggetto SQLAlchemy
    node_hostname: str,
    node_id: str,
    site_name: str,
    discord_webhook_url: str | None,
    slack_webhook_url: str | None,
    metric_type: str,
    current_value: float,
    threshold: float,
) -> None:
    display_name = node_hostname or node_id[:8]
    
    if metric_type == "TEMP":
        title = f"🔥 **HIGH TEMPERATURE**: Node `{display_name}` at site `{site_name}`"
        desc  = f"Sensor reporting critical thermal load: **{current_value:.1f}°C** (Threshold: {threshold}°C)"
    elif metric_type == "CPU":
        title = f"⚠️ **HIGH CPU LOAD**: Node `{display_name}` at site `{site_name}`"
        desc  = f"System sustained heavy load: **{current_value:.1f}%** (Threshold: {threshold}%)"
    else:  # DISK
        title = f"💾 **STORAGE CRITICAL**: Node `{display_name}` at site `{site_name}`"
        desc  = f"Storage nearing capacity: **{current_value:.1f}%** (Threshold: {threshold}%)"

    message = f"{title}\n{desc}"

    tasks = []
    if discord_webhook_url:
        tasks.append(send_discord_metric(discord_webhook_url, node_hostname, message))
    if slack_webhook_url:
        tasks.append(send_slack_metric(slack_webhook_url, node_hostname, message))
    if tasks:
        await asyncio.gather(*tasks)