"""
PSC (persons with significant control / beneficial ownership) via the Registrum API.

Companies House publishes PSC data as raw codes and makes you chase corporate
owners up the register yourself. Registrum decodes the control types and can walk
the chain to the ultimate owners in one call.

Needs a Registrum API key (free tier: https://registrum.co.uk), NOT a Companies
House key -- different service, different auth (an X-API-Key header).

    export REGISTRUM_API_KEY=your_key_here
    python psc_example.py [company_number]
"""

import os
import sys

import requests

BASE_URL = "https://api.registrum.co.uk/v1"


def get(path: str, api_key: str) -> dict:
    response = requests.get(f"{BASE_URL}{path}", headers={"X-API-Key": api_key}, timeout=30)
    response.raise_for_status()
    return response.json()["data"]


def describe(psc: dict) -> str:
    if psc["kind"] == "exempt":  # chain only: e.g. a listed company
        return psc["note"]
    controls = ", ".join(psc["natures_of_control_decoded"])
    line = f"{psc['name']} ({psc['kind']}) -- {controls}"
    if psc["kind"] == "corporate-entity":
        # company_number is only set for a confirmed Companies House registration.
        # Otherwise it is null and the owner sits on some other register: print
        # that registry instead of inventing a UK company number.
        if psc.get("company_number"):
            line += f" [Companies House {psc['company_number']}]"
        else:
            line += f" [registry: {psc.get('registry_name')} {psc.get('registry_number')}, unconfirmed]"
    elif "verification_status" in psc:
        # ECCTA identity verification: "pending" is not a failure (deadline not yet
        # passed), "unknown" means no record, only "overdue" is a missed deadline.
        line += f" [identity verification: {psc['verification_status']}]"
    return line


def print_chain(pscs: list[dict], depth: int = 0) -> None:
    for psc in pscs:
        print("  " * (depth + 1) + describe(psc))
        if psc.get("terminal_reason") == "natural_person":
            print("  " * (depth + 2) + "-> ultimate owner (a person)")
        elif psc.get("children"):
            print_chain(psc["children"]["pscs"], depth + 1)
        elif psc.get("terminal_reason"):
            print("  " * (depth + 2) + f"-> chain stops: {psc['terminal_reason']}")


if __name__ == "__main__":
    api_key = os.environ.get("REGISTRUM_API_KEY", "")
    if not api_key:
        raise SystemExit("Set REGISTRUM_API_KEY -- free key at https://registrum.co.uk")

    number = sys.argv[1] if len(sys.argv) > 1 else "11006227"

    psc = get(f"/company/{number}/psc", api_key)
    if psc["has_psc_exemption"]:
        print("Exempt from PSC filing (e.g. a listed company)")
    print(f"Active PSCs: {psc['total_active']}")
    for p in psc["active_pscs"]:
        print(f"  {describe(p)}")

    chain = get(f"/company/{number}/psc/chain", api_key)
    print(f"Ownership chain for {chain['company_name']}:")
    print_chain(chain["pscs"])
