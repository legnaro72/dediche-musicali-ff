"""
CLI per aggiornare il feedback persistente di una dedica.

Esempi:
  python scripts/save_feedback.py vote 2026-05-15-scarabocchi-olly --voto 8 --pensiero "Testo"
  python scripts/save_feedback.py reaction 2026-05-15-scarabocchi-olly --reaction heart --previous like
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.dedication_feedback import update_reaction, update_vote


def main() -> int:
    parser = argparse.ArgumentParser(description="Salva feedback su data/dedications/*.json")
    subparsers = parser.add_subparsers(dest="command", required=True)

    vote_parser = subparsers.add_parser("vote", help="Salva voto e pensiero")
    vote_parser.add_argument("dedication_id")
    vote_parser.add_argument("--voto", required=True, type=int)
    vote_parser.add_argument("--pensiero", default="")
    vote_parser.add_argument("--user-id", required=True)
    vote_parser.add_argument("--user-name", required=True)

    reaction_parser = subparsers.add_parser("reaction", help="Aggiorna una reazione")
    reaction_parser.add_argument("dedication_id")
    reaction_parser.add_argument("--reaction", required=True, choices=("down", "like", "heart", "sun"))
    reaction_parser.add_argument("--previous", default=None, choices=("down", "like", "heart", "sun"))
    reaction_parser.add_argument("--user-id", required=True)
    reaction_parser.add_argument("--user-name", required=True)

    args = parser.parse_args()
    if args.command == "vote":
        updated = update_vote(args.dedication_id, args.voto, args.pensiero, user_id=args.user_id, user_name=args.user_name)
    else:
        updated = update_reaction(args.dedication_id, args.reaction, args.previous, user_id=args.user_id, user_name=args.user_name)

    print(json.dumps({
        "ok": True,
        "id": updated.get("id"),
        "votoPilly": updated.get("votoPilly"),
        "pensieroPilly": updated.get("pensieroPilly"),
        "reactions": updated.get("reactions"),
        "votes": updated.get("votes", []),
        "thoughts": updated.get("thoughts", []),
        "reactionEntries": updated.get("reactionEntries", []),
        "updated_at": updated.get("updated_at"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
