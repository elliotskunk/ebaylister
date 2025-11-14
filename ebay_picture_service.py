"""
eBay Picture Service (EPS) Integration
Upload images to eBay's picture service and get back URLs for use in listings.
"""
import os
import base64
import logging
import requests
from xml.etree import ElementTree as ET
from typing import Optional

log = logging.getLogger(__name__)

TRADING_API_URL = "https://api.ebay.com/ws/api.dll"
SITE_ID = "3"  # UK
COMPAT_LEVEL = "1147"


class EPSError(RuntimeError):
    """Error uploading to eBay Picture Service"""
    pass


def upload_image_to_eps(token: str, image_bytes: bytes, image_name: str = "item.jpg") -> str:
    """
    Upload an image to eBay Picture Service (EPS) using the Trading API.

    Args:
        token: eBay OAuth access token
        image_bytes: Raw image bytes
        image_name: Name for the image file

    Returns:
        str: Public URL of the uploaded image on eBay's servers

    Raises:
        EPSError: If upload fails
    """
    # Encode image to base64
    b64_image = base64.b64encode(image_bytes).decode('utf-8')

    # Build XML request for UploadSiteHostedPictures
    xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
<UploadSiteHostedPicturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
    <RequesterCredentials>
        <eBayAuthToken>{escape_xml(token)}</eBayAuthToken>
    </RequesterCredentials>
    <WarningLevel>High</WarningLevel>
    <PictureData>{b64_image}</PictureData>
    <PictureName>{escape_xml(image_name)}</PictureName>
    <PictureSet>Supersize</PictureSet>
</UploadSiteHostedPicturesRequest>"""

    headers = {
        "X-EBAY-API-CALL-NAME": "UploadSiteHostedPictures",
        "X-EBAY-API-SITEID": SITE_ID,
        "X-EBAY-API-COMPATIBILITY-LEVEL": COMPAT_LEVEL,
        "X-EBAY-API-IAF-TOKEN": token,
        "Content-Type": "text/xml; charset=utf-8",
    }

    try:
        log.info(f"Uploading image to EPS: {image_name} ({len(image_bytes)} bytes)")
        response = requests.post(
            TRADING_API_URL,
            headers=headers,
            data=xml_request.encode('utf-8'),
            timeout=60  # Image uploads can take longer
        )
        response.raise_for_status()

        # Parse XML response
        root = ET.fromstring(response.text)
        ns = {"e": "urn:ebay:apis:eBLBaseComponents"}

        # Check for errors
        ack = root.find(".//e:Ack", ns)
        if ack is not None and ack.text in ("Failure", "PartialFailure"):
            error_msg = root.find(".//e:Errors/e:LongMessage", ns)
            error_text = error_msg.text if error_msg is not None else "Unknown error"
            log.error(f"EPS upload failed: {error_text}")
            raise EPSError(f"EPS upload failed: {error_text}")

        # Extract the full-size URL
        full_url = root.find(".//e:SiteHostedPictureDetails/e:FullURL", ns)
        if full_url is None or not full_url.text:
            log.error(f"No URL returned from EPS. Response: {response.text[:500]}")
            raise EPSError("No image URL returned from eBay Picture Service")

        image_url = full_url.text
        log.info(f"Successfully uploaded image to EPS: {image_url}")
        return image_url

    except requests.RequestException as e:
        log.exception("HTTP error uploading to EPS")
        raise EPSError(f"HTTP error uploading image: {e}")
    except ET.ParseError as e:
        log.exception("XML parse error from EPS response")
        raise EPSError(f"Invalid XML response from EPS: {e}")


def upload_multiple_images_to_eps(token: str, images_data: list[tuple[bytes, str]]) -> list[str]:
    """
    Upload multiple images to EPS.

    Args:
        token: eBay OAuth access token
        images_data: List of (image_bytes, image_name) tuples

    Returns:
        list[str]: List of public URLs for uploaded images

    Raises:
        EPSError: If any upload fails
    """
    urls = []
    for i, (image_bytes, image_name) in enumerate(images_data, 1):
        try:
            url = upload_image_to_eps(token, image_bytes, image_name)
            urls.append(url)
        except EPSError as e:
            log.error(f"Failed to upload image {i}/{len(images_data)}: {e}")
            raise EPSError(f"Failed to upload image {i}: {e}")

    log.info(f"Successfully uploaded {len(urls)} images to EPS")
    return urls


def escape_xml(s: str) -> str:
    """Escape special XML characters"""
    return (s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
