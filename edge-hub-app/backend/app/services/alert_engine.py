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


async def send_discord_alert(webhook_url: str, node: Node, site: Site, retries: int = 3) -> None:
    """Sends an offline alert to a Discord webhook with 429 rate limit handling."""
    payload = {
        "content": f"🚨 **EDGEHUB ALERT** 🚨\nNode **`{node.hostname}`** at site **`{site.name}`** is OFFLINE."
    }
    
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                
                # Handling Discord Rate Limit
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
                return  # Success, exit the loop and function
                
            except Exception as e:
                if attempt == retries - 1:
                    logger.error("Error sending Discord webhook for node %s after %d attempts: %s", node.hostname, retries, e)
                else:
                    await asyncio.sleep(1.0) # Small delay before retrying generic network errors


async def send_slack_alert(webhook_url: str, node: Node, site: Site, retries: int = 3) -> None:
    """Sends an offline alert to a Slack webhook with 429 rate limit handling."""
    payload = {
        "text": f"🚨 *EDGEHUB ALERT* 🚨\nNode *`{node.hostname}`* at site *`{site.name}`* is OFFLINE."
    }
    
    async with httpx.AsyncClient() as client:
        for attempt in range(retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=5.0)
                
                # Handling Slack Rate Limit (Usually in Headers)
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
    """Checks which webhooks are configured for the site and dispatches them concurrently."""
    tasks = []
    
    if site.discord_webhook_url:
        tasks.append(send_discord_alert(site.discord_webhook_url, node, site))
        
    if site.slack_webhook_url:
        tasks.append(send_slack_alert(site.slack_webhook_url, node, site))
        
    if tasks:
        await asyncio.gather(*tasks)


async def send_discord_recovery(webhook_url: str, node: Node, site: Site, retries: int = 3) -> None:
    """Sends a recovery alert to a Discord webhook with 429 rate limit handling."""
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
    """Sends a recovery alert to a Slack webhook with 429 rate limit handling."""
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
    """Checks which webhooks are configured for the site and dispatches recovery alerts concurrently."""
    tasks = []
    
    if site.discord_webhook_url:
        tasks.append(send_discord_recovery(site.discord_webhook_url, node, site))
        
    if site.slack_webhook_url:
        tasks.append(send_slack_recovery(site.slack_webhook_url, node, site))
        
    if tasks:
        await asyncio.gather(*tasks)