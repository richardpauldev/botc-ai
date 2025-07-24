# Common role definitions and utilities used across the project.

from typing import Dict, List, Optional

# Mapping from role name to the fields relevant for information claims.
ROLE_FIELDS: Dict[str, List[str]] = {
    "Washerwoman": ["seen_role", "seen_players"],
    "Librarian": ["seen_role", "seen_players"],
    "Investigator": ["seen_role", "seen_players"],
    "Undertaker": ["night_results"],
    "Ravenkeeper": ["seen_player", "seen_role", "night"],
    "Slayer": ["night", "shot_player", "died"],
    "Virgin": ["night", "first_nominator", "died"],
    "Empath": ["night_results"],
    "Fortune Teller": ["night_results"],
    "Chef": ["pairs"],
}

# Roles that typically provide ongoing information
ONGOING_INFO_ROLES = {
    "Empath",
    "Fortune Teller",
    "Undertaker",
    "Ravenkeeper",
    "Virgin",
    "Slayer",
}

# Roles that are primarily informational (used by controllers and deduction).
INFO_ROLES = {
    "Washerwoman",
    "Librarian",
    "Investigator",
    "Chef",
    "Empath",
    "Fortune Teller",
    "Undertaker",
    "Ravenkeeper",
}

# Subfields for structured night_results entries.
_NR_SUBFIELDS = {
    "undertaker": ["night", "executed_player", "seen_role"],
    "empath": ["night", "num_evil", "neighbor1", "neighbor2"],
    "fortune teller": ["night", "ping", "player1", "player2"],
}

def construct_info_claim_dict(player: str, claim: dict) -> Optional[dict]:
    """Construct a simplified info-claim dictionary from a raw claim."""
    role = claim.get("role")
    if not role:
        return None

    fields = ROLE_FIELDS.get(role)
    if not fields:
        return None

    info = {"type": role.lower(), "claimer": player}

    for f in fields:
        value = claim.get(f)
        if f == "night_results":
            if isinstance(value, list):
                subfields = _NR_SUBFIELDS.get(role.lower())
                if subfields:
                    info[f] = [
                        {k: entry.get(k) for k in subfields}
                        for entry in value
                    ]
                else:
                    info[f] = value
            else:
                info[f] = []
        else:
            info[f] = value
    return info
