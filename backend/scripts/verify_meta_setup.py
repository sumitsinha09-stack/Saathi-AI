import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import httpx
from backend.app.config import settings


async def run_diagnostics(auto_subscribe: bool = True) -> Dict[str, Any]:
    print("=" * 65)
    print("        Saathi AI — Automated Meta Graph API Diagnostics        ")
    print("=" * 65)

    token = settings.WHATSAPP_ACCESS_TOKEN.strip()
    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID.strip()
    waba_id = settings.WHATSAPP_BUSINESS_ACCOUNT_ID.strip()
    app_secret = settings.effective_app_secret.strip()
    version = settings.WHATSAPP_API_VERSION.strip() or "v21.0"
    base_url = "https://graph.facebook.com"

    results = {
        "token_valid": False,
        "phone_number_verified": False,
        "waba_verified": False,
        "waba_subscribed": False,
        "discovered_waba_id": None,
    }

    # 1. Inspect Environment Variables
    print("\n[1] Environment Variables:")
    print(f"  • Graph API Version: {version}")
    print(f"  • Phone Number ID: {phone_id or 'NOT CONFIGURED'}")

    is_token_placeholder = token in ("", "your_meta_access_token")
    is_secret_placeholder = app_secret in ("", "your_meta_app_secret", "your_whatsapp_app_secret")
    is_waba_placeholder = waba_id in ("", "your_whatsapp_business_account_id")

    if is_token_placeholder:
        print("  • WHATSAPP_ACCESS_TOKEN: ❌ PLACEHOLDER / MISSING ('your_meta_access_token')")
    else:
        print(f"  • WHATSAPP_ACCESS_TOKEN: ✅ CONFIGURED (len: {len(token)}, prefix: {token[:6]}...)")

    if is_secret_placeholder:
        print("  • META_APP_SECRET: ❌ PLACEHOLDER / MISSING ('your_meta_app_secret')")
    else:
        print(f"  • META_APP_SECRET: ✅ CONFIGURED (len: {len(app_secret)}, prefix: {app_secret[:4]}...)")

    if is_waba_placeholder:
        print("  • WHATSAPP_BUSINESS_ACCOUNT_ID: ⚠️  PLACEHOLDER / PENDING DISCOVERY")
    else:
        print(f"  • WHATSAPP_BUSINESS_ACCOUNT_ID: ✅ CONFIGURED ({waba_id})")

    if is_token_placeholder:
        print("\n" + "!" * 65)
        print("ACTION REQUIRED:")
        print("  Add your real WHATSAPP_ACCESS_TOKEN to .env to execute live Graph API diagnostics.")
        print("!" * 65 + "\n")
        return results

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 2. Check Token Validity & Debug Token Information
        print("\n[2] Token & Permission Inspection:")
        try:
            # Check /debug_token using the token itself
            debug_resp = await client.get(
                f"{base_url}/{version}/debug_token",
                params={"input_token": token},
                headers=headers,
            )
            if debug_resp.status_code == 200:
                data = debug_resp.json().get("data", {})
                is_valid = data.get("is_valid", False)
                scopes = data.get("scopes", [])
                app_id = data.get("app_id", "N/A")
                expires_at = data.get("expires_at", 0)
                exp_str = (
                    datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    if expires_at
                    else "Never (Permanent Token)"
                )
                print(f"  • Token Validity: {'✅ VALID' if is_valid else '❌ INVALID'}")
                print(f"  • Linked App ID: {app_id}")
                print(f"  • Token Scopes: {', '.join(scopes) if scopes else 'None'}")
                print(f"  • Expires At: {exp_str}")
                results["token_valid"] = is_valid
            else:
                # Fallback: check /me if debug_token needs app secret proof
                me_resp = await client.get(f"{base_url}/{version}/me", headers=headers)
                if me_resp.status_code == 200:
                    print("  • Token Validity: ✅ VALID (Verified via /me)")
                    results["token_valid"] = True
                else:
                    print(f"  • Token Validity: ❌ FAILED (HTTP {me_resp.status_code})")
                    print(f"    Error: {me_resp.text}")
        except Exception as exc:
            print(f"  • Token verification error: {exc}")

        # 3. Verify Phone Number ID & Auto-Discover WABA ID
        print("\n[3] Phone Number Verification & WABA Association:")
        effective_waba = waba_id if not is_waba_placeholder else None
        if phone_id and phone_id != "your_phone_number_id":
            phone_url = f"{base_url}/{version}/{phone_id}"
            fields = "id,display_phone_number,verified_name,quality_rating,code_verification_status,whatsapp_business_account"
            try:
                phone_resp = await client.get(phone_url, params={"fields": fields}, headers=headers)
                if phone_resp.status_code == 200:
                    pdata = phone_resp.json()
                    display_phone = pdata.get("display_phone_number", "N/A")
                    verified_name = pdata.get("verified_name", "N/A")
                    quality = pdata.get("quality_rating", "N/A")
                    code_ver = pdata.get("code_verification_status", "N/A")
                    waba_obj = pdata.get("whatsapp_business_account", {})
                    discovered_waba = waba_obj.get("id")

                    print(f"  • Phone Number ID: ✅ VERIFIED ({phone_id})")
                    print(f"  • Display Phone Number: {display_phone}")
                    print(f"  • Verified Name: {verified_name}")
                    print(f"  • Quality Rating: {quality}")
                    print(f"  • Verification Status: {code_ver}")

                    if discovered_waba:
                        print(f"  • Linked WABA ID: ✅ AUTO-DISCOVERED ({discovered_waba})")
                        results["discovered_waba_id"] = discovered_waba
                        effective_waba = discovered_waba
                    results["phone_number_verified"] = True
                else:
                    print(f"  • Phone verification failed: HTTP {phone_resp.status_code}")
                    print(f"    Response: {phone_resp.text}")
            except Exception as exc:
                print(f"  • Phone query error: {exc}")
        else:
            print("  • Phone Number ID is not configured.")

        # 4. Verify WABA Subscribed Apps & Enable messages Webhook
        print("\n[4] WhatsApp Business Account Subscribed Apps:")
        if effective_waba:
            sub_url = f"{base_url}/{version}/{effective_waba}/subscribed_apps"
            try:
                sub_resp = await client.get(sub_url, headers=headers)
                if sub_resp.status_code == 200:
                    sub_data = sub_resp.json().get("data", [])
                    print(f"  • WABA Association: ✅ VERIFIED")
                    results["waba_verified"] = True
                    print(f"  • Active Subscribed Apps: {len(sub_data)}")

                    if sub_data:
                        print("  • Webhook Delivery to App: ✅ ACTIVE")
                        results["waba_subscribed"] = True
                    else:
                        print("  • Webhook Delivery to App: ⚠️  NOT SUBSCRIBED")
                        if auto_subscribe:
                            print("  • Attempting automatic programmatic subscription...")
                            post_sub = await client.post(sub_url, headers=headers)
                            if post_sub.status_code == 200 and post_sub.json().get("success"):
                                print("  • Automatic Subscription: ✅ SUCCESS (App subscribed to WABA)")
                                results["waba_subscribed"] = True
                            else:
                                print(f"  • Automatic Subscription returned: {post_sub.text}")
                else:
                    print(f"  • WABA query failed: HTTP {sub_resp.status_code}")
                    print(f"    Response: {sub_resp.text}")
            except Exception as exc:
                print(f"  • WABA query error: {exc}")
        else:
            print("  • WABA ID could not be determined. Check Phone Number ID.")

    print("\n" + "=" * 65)
    return results


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
