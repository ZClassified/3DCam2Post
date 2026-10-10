"""
Clip identity: pairing L/R files from the cards and matching clips against the manifest.

Camera clip numbers are not unique (AVCHD may restart after formatting, several card
sets can carry the same numbers). Two signals are used, strongest first:

- P2 (3DP1): the GlobalClipID (UMID) from the clip XML. L and R share the same
  material number and differ only in the instance number, so pairing is exact.
- Both formats: both eyes of a take are recorded simultaneously, so their file
  timestamps are (nearly) identical.

Without either signal the logic falls back to the plain clip number (previous behaviour).
"""

from core.metadata import umid_material

# Max. timestamp difference between L and R of the same take (seconds)
PAIR_TOLERANCE = 120


def _other(eye):
    return "R" if eye == "L" else "L"


def eye_time_diff(clip, eye, mtime):
    """Distance between mtime and the other eye already present in the clip (None = unknown)."""
    other = _other(eye)
    t = clip.get(f"mtime_{other}")
    if not clip.get(f"path_{other}") or not t or not mtime:
        return None
    return abs(t - mtime)


def choose_pair_candidate(candidates, eye, mtime, path, umid=None):
    """
    Picks the clip a scanned file belongs to.
    candidates: clips with the same camera clip number and camera type.
    Returns the chosen clip, or None if a new entry must be created.
    """
    for c in candidates:
        if c.get(f"path_{eye}") == path:
            return c  # same file scanned again
    free = [c for c in candidates if not c.get(f"path_{eye}")]
    mat = umid_material(umid)
    scored = []
    for c in free:
        other = _other(eye)
        other_mat = umid_material(c.get(f"umid_{other}")) if c.get(f"path_{other}") else None
        if mat and other_mat:
            if mat != other_mat:
                continue  # different recording
            scored.append((-1, c))  # exact UMID pair beats everything
            continue
        d = eye_time_diff(c, eye, mtime)
        if d is not None and d > PAIR_TOLERANCE:
            continue  # other eye recorded at a different time -> different take
        scored.append((d if d is not None else PAIR_TOLERANCE, c))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0])
    return scored[0][1]


def entry_matches(entry, clip):
    """
    True if a manifest entry describes this clip.
    Legacy entries (no source info) match by clip number only.
    """
    known = {e: entry.get(f"src_{e}") for e in ("L", "R") if entry.get(f"src_{e}")}
    if not known:
        return True

    common = [e for e in known if clip.get(f"path_{e}")]
    for e in common:
        u_entry, u_clip = known[e].get("umid"), clip.get(f"umid_{e}")
        if u_entry and u_clip:
            if u_entry != u_clip:
                return False
            continue
        if known[e].get("size") != clip.get(f"size_{e}"):
            return False
        t_entry, t_clip = known[e].get("mtime"), clip.get(f"mtime_{e}")
        if t_entry and t_clip and abs(t_entry - t_clip) > 2:
            return False
    if common:
        return True

    # No overlapping eye (e.g. only the R card is inserted now)
    mats_entry = {umid_material(s.get("umid")) for s in known.values() if s.get("umid")}
    mats_clip = {umid_material(clip.get(f"umid_{e}")) for e in ("L", "R")
                 if clip.get(f"path_{e}") and clip.get(f"umid_{e}")}
    if mats_entry and mats_clip:
        return bool(mats_entry & mats_clip)
    times_entry = [s.get("mtime") for s in known.values() if s.get("mtime")]
    times_clip = [clip.get(f"mtime_{e}") for e in ("L", "R") if clip.get(f"path_{e}") and clip.get(f"mtime_{e}")]
    if times_entry and times_clip:
        return min(abs(a - b) for a in times_entry for b in times_clip) <= PAIR_TOLERANCE
    return True


def resolve_manifest_key(manifest, clip, taken):
    """
    Returns the manifest key for a clip: an existing matching entry, the plain clip
    number if unused, or a fresh "<id>~n" key. `taken` holds keys already assigned
    to other clips in the list.
    """
    cid = clip["id"]
    keys = [k for k in manifest if k == cid or k.startswith(f"{cid}~")]
    for k in sorted(keys, key=lambda k: (len(k), k)):
        if k not in taken and entry_matches(manifest[k], clip):
            return k
    if cid not in manifest and cid not in taken:
        return cid
    n = 2
    while f"{cid}~{n}" in manifest or f"{cid}~{n}" in taken:
        n += 1
    return f"{cid}~{n}"
