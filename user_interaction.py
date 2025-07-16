import os
import openai
import json
import re

openai.api_key = os.getenv("OPENAI_API_KEY")

print(openai.api_key)

SYSTEM_PROMPT = """
You are a Blood on the Clocktower claim extractor. Your job is to extract structured claims from user text. 
Output ONLY valid JSON matching the exact schema below, no extra explanation.

Schema:
{
  "claimant": string | null,
  "role": string | null,
  "info": {
    "suspects": [string] | null,
    "evil_role": string | null
  } | null
}

If any value is missing, set it to null.
Example:
Input: "I'm the Investigator, and I know that either Steven or Bella is the poisoner."
Output: {
  "claimant": null,
  "role": "Investigator",
  "info": {
    "suspects": ["Steven", "Bella"],
    "evil_role": "Poisoner"
  }
}
"""

ROLE_SCHEMAS = {
    "Investigator": {
        "abbreviations": ["Investigator", "Inv"],
        "description": "Extract claims about being the Investigator. Output the suspects and evil role.",
        "schema": """
        {
          "claimant": string | null,
          "role": "Investigator",
          "info": {
            "suspects": [string] | null,
            "evil_role": string | null
          } | null
        }
        """,
        "sample_input": "I am the Investigator. Steven or Bella is the Poisoner.",
        "sample_output": {
            "claimant": None,
            "role": "Investigator",
            "info": {"suspects": ["Steven", "Bella"], "evil_role": "Poisoner"},
        },
    },
    "Washerwoman": {
        "abbreviations": ["Washerwoman", "WW", "washer woman"],
        "description": "Extract claims about being the Washerwoman. Output the two names and the role.",
        "schema": """
        {
          "claimant": string | null,
          "role": "Washerwoman",
          "info": {
            "seen_role": string | null,
            "players_seen": [string] | null
          } | null
        }
        """,
        "sample_input": "I'm the Washerwoman. I saw that either Jack or Alice is the Librarian.",
        "sample_output": {
            "claimant": None,
            "role": "Washerwoman",
            "info": {"seen_role": "Librarian", "players_seen": ["Jack", "Alice"]},
        },
    },
    "Librarian": {
        "abbreviations": ["Librarian", "Lib"],
        "description": "Extract claims about being the Librarian. The claim should include the two players and the outsider role they are shown.",
        "schema": """
      {
        "claimant": string | null,
        "role": "Librarian",
        "info": {
          "seen_role": string | null,
          "seen_players": [string, string] | null
        } | null
      }
      """,
        "sample_inputs_outputs": [
            # Example 1: Normal two-player, one role claim
            {
                "input": "I'm the Librarian. I saw that either Steve or Bella is the Recluse.",
                "output": {
                    "claimant": None,
                    "role": "Librarian",
                    "info": {
                        "seen_role": "Recluse",
                        "seen_players": ["Steve", "Bella"],
                    },
                },
            },
            # Example 2: No outsiders seen
            {
                "input": "I'm the Librarian. I saw no outsiders.",
                "output": {
                    "claimant": None,
                    "role": "Librarian",
                    "info": {"seen_role": None, "seen_players": None},
                },
            },
        ],
    },
    "Chef": {
        "abbreviations": ["Chef"],
        "description": "Extract claims about being the Chef. The claim should state the number of pairs of evil players sitting next to each other.",
        "schema": """
    {
      "claimant": string | null,
      "role": "Chef",
      "info": {
        "evil_pairs": int | null
      } | null
    }
    """,
        "sample_input": "I'm the Chef. I got a 1.",
        "sample_output": {"claimant": None, "role": "Chef", "info": {"evil_pairs": 1}},
    },
    "Empath": {
        "abbreviations": ["Empath", "Emp"],
        "description": "Extract claims about being the Empath. The claim should include the number of evil players among their two living neighbors, and, if given, the night and neighbor names.",
        "schema": """
    {
      "claimant": string | null,
      "role": "Empath",
      "info": {
        "night": int | null,
        "neighbors": [string, string] | null,
        "num_evil": int | null
      } | null
    }
    """,
        "sample_inputs_outputs": [
            # Example 1: Night specified
            {
                "input": "I'm the Empath. On night 1, I got a 0.",
                "output": {
                    "claimant": None,
                    "role": "Empath",
                    "info": {"night": 1, "neighbors": None, "num_evil": 0},
                },
            },
            # Example 2: 'Last night', with neighbors named
            {
                "input": "I'm the Empath. Last night I got a 1 between Steve and Alice.",
                "output": {
                    "claimant": None,
                    "role": "Empath",
                    "info": {
                        "night": None,  # 'last night' to be resolved later
                        "neighbors": ["Steve", "Alice"],
                        "num_evil": 1,
                    },
                },
            },
        ],
    },
    "Fortune Teller": {
        "abbreviations": ["Fortune Teller", "FT", "F.T."],
        "description": "Extract claims about being the Fortune Teller. Each claim should state which two players were checked, on what night (if specified), and whether a ping (demon found) was received.",
        "schema": """
    {
      "claimant": string | null,
      "role": "Fortune Teller",
      "night_results": [
        {
          "night": int | null,
          "players_checked": [string, string] | null,
          "ping": bool | null
        }
      ] | null
    }
    """,
        "sample_inputs_outputs": [
            {
                "input": "I'm the Fortune Teller. I checked Steve and Bella on night 1 and got a ping. Last night, I checked myself and Tyler and got a no.",
                "output": {
                    "claimant": None,
                    "role": "Fortune Teller",
                    "night_results": [
                        {
                            "night": 1,
                            "players_checked": ["Steve", "Bella"],
                            "ping": True,
                        },
                        {
                            "night": None,
                            "players_checked": [None, "Tyler"],
                            "ping": False,
                        },
                    ],
                },
            },
        ],
    },
    "Monk": {
        "abbreviations": ["Monk"],
        "description": "Extract claims about being the Monk. Each claim should state which player was protected on a given night, if specified.",
        "schema": """
    {
      "claimant": string | null,
      "role": "Monk",
      "night_results": [
        {
          "night": int | null,
          "protected_player": string | null
        }
      ] | null
    }
    """,
        "sample_inputs_outputs": [
            {
                "input": "I'm the Monk. On night 2, I protected Alice. Last night I chose Susan. ",
                "output": {
                    "claimant": None,
                    "role": "Monk",
                    "night_results": [
                        {"night": 2, "protected_player": "Alice"},
                        {"night": None, "protected_player": "Susan"},
                    ],
                },
            },
        ],
    },
    "Butler": {
        "abbreviations": ["Butler"],
        "description": "Extract claims about being the Butler. Each claim should include which player they chose as their master and what night, if specified.",
        "schema": """
    {
      "claimant": string | null,
      "role": "Butler",
      "night_results": [
        {
          "night": int | null,
          "assigned_master": string | null
        } 
      ]| null
    }
    """,
        "sample_inputs_outputs": [
            # Example 1: Night specified
            {
                "input": "I'm the butler, and on night 1 decided to choose Bob. Last night Keith was my master.",
                "output": {
                    "claimant": None,
                    "role": "Butler",
                    "night_results": [
                        {"night": 1, "master": "Bob"},
                        {"night": None, "master": "Keith"},
                    ],
                },
            },
        ],
    },
}


# Add more roles as needed
ABBREV_TO_ROLE = {}
for rolename, data in ROLE_SCHEMAS.items():
    for abbr in data["abbreviations"]:
        ABBREV_TO_ROLE[abbr.lower()] = rolename

def find_roles_in_text(user_text):
    roles_found = set()
    user_text_lower = user_text.lower()
    for abbr, role in ABBREV_TO_ROLE.items():
        if re.search(r'\b' + re.escape(abbr) + r'\b', user_text_lower):
            roles_found.add(role)
    return sorted(roles_found)

def build_system_prompt(roles):
    prompt = [
        "You are a Blood on the Clocktower claim extractor. Your job is to extract structured claims from user text.",
        "Output ONLY valid JSON matching one of the exact schemas below, no extra explanation.",
        "If any value is missing, set it to null.",
        ""
    ]
    for role in roles:
        data = ROLE_SCHEMAS[role]
        prompt.append(f"Role: {role} (abbreviations: {', '.join(data['abbreviations'])})")
        prompt.append(f"Description: {data['description']}")
        prompt.append("Schema:")
        prompt.append(data['schema'].strip())
        # Handle single or multiple examples
        if "sample_inputs_outputs" in data:
            for ex in data["sample_inputs_outputs"]:
                prompt.append(f"Example input: {ex['input']}")
                prompt.append("Example output:")
                prompt.append(json.dumps(ex['output'], indent=2))
        elif "sample_input" in data and "sample_output" in data:
            prompt.append(f"Example input: {data['sample_input']}")
            prompt.append("Example output:")
            prompt.append(json.dumps(data['sample_output'], indent=2))
        prompt.append("")
    return "\n".join(prompt)


def extract_claim(user_input):
    roles = find_roles_in_text(user_input)
    if not roles:
        print("No roles mentioned")
        return
    prompt = build_system_prompt(roles)
    print(prompt)
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f'Input: "{user_input}"'},
        ],
        response_format={"type": "json_object"},
    )
    # The API will return the message as JSON, so parse it
    result = response.choices[0].message.content
    return json.loads(result)


if __name__ == "__main__":
    print("Enter a Blood on the Clocktower claim:")
    claim = input("> ")
    extracted = extract_claim(claim)
    print("\nStructured Output:")
    print(json.dumps(extracted, indent=2))
