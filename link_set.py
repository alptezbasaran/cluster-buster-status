#!/usr/bin/env python
"""Link (or unlink) a subject set to a workflow — the driver that was an
uncommitted one-off when sets 001-126 were linked on 2026-07-09.

    source ~/.zooniverse_env
    ~/Desktop/projects/arm_grouping/.venv/bin/python link_set.py <display-name> \
        [--workflow 26736] [--unlink] [--dry-run]

Resolves the set by display name within project 23492 (errors on 0 or >1
matches), shows the workflow's linked-set count before and after. Linking a
set makes its unretired subjects immediately servable to volunteers.
"""

import argparse
import os
import sys

from panoptes_client import Panoptes, SubjectSet, Workflow

PROJECT_ID = "23492"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("display_name")
    ap.add_argument("--workflow", default="26736")
    ap.add_argument("--unlink", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    user, pw = os.environ.get("PANOPTES_USERNAME"), os.environ.get("PANOPTES_PASSWORD")
    if not user or not pw:
        print("PANOPTES_USERNAME / PANOPTES_PASSWORD not set (source ~/.zooniverse_env)")
        return 2
    Panoptes.connect(username=user, password=pw)

    matches = list(SubjectSet.where(project_id=PROJECT_ID, display_name=args.display_name))
    if len(matches) != 1:
        print(f"expected exactly 1 subject set named {args.display_name!r}, found {len(matches)}")
        return 2
    ss = matches[0]
    workflow = Workflow.find(args.workflow)
    linked = list(workflow.raw["links"].get("subject_sets", []))
    verb = "unlink" if args.unlink else "link"
    print(f"subject set : {ss.display_name!r} (id={ss.id})")
    print(f"workflow    : {workflow.display_name!r} (id={workflow.id}), "
          f"{len(linked)} sets currently linked")
    print(f"already linked: {ss.id in linked}")

    if args.dry_run:
        print(f"DRY RUN — would {verb} now")
        return 0
    if args.unlink:
        workflow.remove_subject_sets([ss])
    else:
        workflow.add_subject_sets([ss])
    workflow.reload()
    after = list(workflow.raw["links"].get("subject_sets", []))
    print(f"done: {verb}ed. workflow now has {len(after)} linked sets "
          f"(set present: {ss.id in after})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
