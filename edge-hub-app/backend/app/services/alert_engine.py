"""
Alert Engine Service
Handles dispatching external notifications (e.g., Webhooks) when node events occur.
"""
import httpx
import logging
import asyncio

from ..models.node import Node
from ..models.site import Site

logger = logging.getLogger(__name__)


async def send_discord_alert(webhook_url: str, node: Node, site: Site) -> None:
    """Sends an offline alert to a Discord webhook."""
    payload = {
        "content": f"🚨 **EDGEHUB ALERT** 🚨\nNode **`{node.hostname}`** at site **`{site.name}`** is OFFLINE."
    }
    
    # Use httpx for non-blocking asynchronous HTTP calls
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            logger.info("Discord alert sent successfully for node: %s", node.hostname)
        except Exception as e:
            logger.error("Error sending Discord webhook for node %s: %s", node.hostname, e)

async def send_slack_alert(webhook_url: str, node: Node, site: Site) -> None:
    """Sends an offline alert to a Slack webhook."""
    # Note: Slack uses a single '*' for bold text, unlike Discord's '**'
    payload = {
        "text": f"🚨 *EDGEHUB ALERT* 🚨\nNode *`{node.hostname}`* at site *`{site.name}`* is OFFLINE."
    }
    
    # Use httpx for non-blocking asynchronous HTTP calls
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            logger.info("Slack alert sent successfully for node: %s", node.name)
        except Exception as e:
            logger.error("Error sending Slack webhook for node %s: %s", node.name, e)


async def dispatch_offline_alerts(node: Node, site: Site) -> None:
    """
    Checks which webhooks are configured for the site and dispatches them concurrently.
    """
    tasks = []
    
    if site.discord_webhook_url:
        tasks.append(send_discord_alert(site.discord_webhook_url, node, site))
        
    if site.slack_webhook_url:
        tasks.append(send_slack_alert(site.slack_webhook_url, node, site))
        
    # Execute all configured HTTP calls in parallel
    if tasks:
        await asyncio.gather(*tasks)

async def send_discord_recovery(webhook_url: str, node: Node, site: Site) -> None:
    """Sends a recovery alert to a Discord webhook."""
    payload = {
        "content": f"✅ **EDGEHUB RECOVERY** ✅\nNode **`{node.hostname}`** at site **`{site.name}`** is back ONLINE."
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            logger.info("Discord recovery alert sent successfully for node: %s", node.name)
        except Exception as e:
            logger.error("Error sending Discord recovery webhook for node %s: %s", node.name, e)


async def send_slack_recovery(webhook_url: str, node: Node, site: Site) -> None:
    """Sends a recovery alert to a Slack webhook."""
    payload = {
        "text": f"✅ *EDGEHUB RECOVERY* ✅\nNode *`{node.hostname}`* at site *`{site.name}`* is back ONLINE."
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            response.raise_for_status()
            logger.info("Slack recovery alert sent successfully for node: %s", node.name)
        except Exception as e:
            logger.error("Error sending Slack recovery webhook for node %s: %s", node.name, e)


async def dispatch_recovery_alerts(node: Node, site: Site) -> None:
    """
    Checks which webhooks are configured for the site and dispatches recovery alerts concurrently.
    """
    tasks = []
    
    if site.discord_webhook_url:
        tasks.append(send_discord_recovery(site.discord_webhook_url, node, site))
        
    if site.slack_webhook_url:
        tasks.append(send_slack_recovery(site.slack_webhook_url, node, site))
        
    if tasks:
        await asyncio.gather(*tasks)