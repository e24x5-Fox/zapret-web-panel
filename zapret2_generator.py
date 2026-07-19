#!/usr/bin/env python3
"""
Self-contained bypass-strategy generator for zapret2 (winws2.exe, Lua
lua-desync functions) — the zapret2 counterpart to zapret_generator.py.

Builds candidate winws2.exe command lines from known lua-desync functions
(fake, multisplit, multidisorder, fakedsplit, fakeddisorder, hostfakesplit,
syndata — zapret2's Lua rewrite of zapret1's --dpi-desync methods, defined
in lua/zapret-antidpi.lua; their argument names below were read directly
from that file's own doc-comments above each function, not guessed),
tests each through the same connectivity checks zapret_tester uses for
zapret1, and returns the best-performing one(s).

Unlike zapret1's generator, only the HTTP and TLS lua-desync chains are
part of the search space. Everything else — the WinDivert filter
constructor flags, the lua-init library loads, the QUIC profiles, and the
wireguard/stun/discord catch-all profile — is kept fixed exactly as
shipped in bol-van/zapret-win-bundle's preset2_example.cmd, since that
skeleton is already known-working (verified by hand against real traffic
earlier in this project), and QUIC/UDP fake blobs aren't the kind of
"method" choice this search is about.

Two modes, same split as zapret_generator.py:
  - "simple":   one (tls_method, http_method) pair per candidate, drawn
                from a short curated list.
  - "advanced": every tls_method combined with every http_method (stage 1
                survey), then the top 2 candidates get a small refine pass
                over repeats/tcp_seq (stage 2) — the zapret2 analogue of
                zapret1's fooling/cutoff refine step, since zapret2 has no
                single "--dpi-desync-fooling" switch: fooling here is a
                handful of independent args (tcp_seq, tcp_md5, ...).
"""

import subprocess
import time
import uuid
from pathlib import Path

import zapret_tester as zt
import zapret2_engine as z2
from i18n import t

# --------------------------------------------------------------------------- #
# fixed skeleton — WinDivert filter setup, lua library loads, QUIC profiles,
# and the wireguard/stun/discord catch-all profile, verbatim from
# bol-van/zapret-win-bundle's preset2_example.cmd. Only the HTTP/TLS
# lua-desync chains below are part of the search space.
# --------------------------------------------------------------------------- #

FIXED_HEAD = (
    'start "zapret2-gen" /min "%~dp0winws2.exe" ^\n'
    '--wf-tcp-out=80,443 ^\n'
    '--lua-init=@"%~dp0lua\\zapret-lib.lua" --lua-init=@"%~dp0lua\\zapret-antidpi.lua" ^\n'
    '--lua-init="fake_default_tls = tls_mod(fake_default_tls,\'rnd,rndsni\')" ^\n'
    '--blob=quic_google:@"%~dp0files\\quic_initial_www_google_com.bin" ^\n'
    '--wf-raw-part=@"%~dp0windivert.filter\\windivert_part.discord_media.txt" ^\n'
    '--wf-raw-part=@"%~dp0windivert.filter\\windivert_part.stun.txt" ^\n'
    '--wf-raw-part=@"%~dp0windivert.filter\\windivert_part.wireguard.txt" ^\n'
    '--wf-raw-part=@"%~dp0windivert.filter\\windivert_part.quic_initial_ietf.txt" ^\n'
)

FIXED_QUIC_SLOTS = (
    '--filter-udp=443 --filter-l7=quic --hostlist="%~dp0files\\list-youtube.txt" ^\n'
    '  --payload=quic_initial ^\n'
    '   --lua-desync=fake:blob=quic_google:repeats=11 ^\n'
    '  --new ^\n'
    '--filter-udp=443 --filter-l7=quic ^\n'
    '  --payload=quic_initial ^\n'
    '   --lua-desync=fake:blob=fake_default_quic:repeats=11'
)

FIXED_TAIL_SLOT = (
    '--filter-l7=wireguard,stun,discord ^\n'
    '  --payload=wireguard_initiation,wireguard_cookie,stun,discord_ip_discovery ^\n'
    '   --lua-desync=fake:blob=0x00000000000000000000000000000000:repeats=2'
)


def _http_slot(chain: str) -> str:
    return (
        '--filter-tcp=80 --filter-l7=http ^\n'
        '  --out-range=-d10 ^\n'
        '  --payload=http_req ^\n'
        f'   --lua-desync={chain}'
    )


def _tls_slot(chain: str, hostlist: bool) -> str:
    hl = ' --hostlist="%~dp0files\\list-youtube.txt"' if hostlist else ""
    return (
        f'--filter-tcp=443 --filter-l7=tls{hl} ^\n'
        '  --out-range=-d10 ^\n'
        '  --payload=tls_client_hello ^\n'
        f'   --lua-desync={chain}'
    )


def build_cmd_text(name: str, tls_chain: str, http_chain: str) -> str:
    slots = [
        _http_slot(http_chain),
        _tls_slot(tls_chain, hostlist=True),
        _tls_slot(tls_chain, hostlist=False),
        FIXED_QUIC_SLOTS,
        FIXED_TAIL_SLOT,
    ]
    body = " ^\n  --new ^\n".join(slots)
    return f"{FIXED_HEAD}{body}\n"


# --------------------------------------------------------------------------- #
# method search space — lua-desync chains for the HTTP and TLS payload
# slots. Argument names (blob, pos, tcp_md5, ip_autottl, tls_mod, repeats,
# midhost...) come straight from the doc-comments in
# lua/zapret-antidpi.lua above each function; nothing here is guessed.
# --------------------------------------------------------------------------- #

TLS_METHODS = {
    "fake_multidisorder": (
        'fake:blob=fake_default_tls:tcp_md5:repeats={repeats}:tls_mod=rnd,dupsid,sni=www.google.com{seq} ^\n'
        '   --lua-desync=multidisorder:pos=1,midsld'
    ),
    "fake_multisplit": (
        'fake:blob=fake_default_tls:tcp_md5:repeats={repeats}:tls_mod=rnd,dupsid{seq} ^\n'
        '   --lua-desync=multisplit:pos=1,midsld'
    ),
    "fake_fakedsplit": (
        'fake:blob=fake_default_tls:tcp_md5:repeats={repeats}:tls_mod=rnd,dupsid{seq} ^\n'
        '   --lua-desync=fakedsplit:pos=midsld'
    ),
    "fake_fakeddisorder": (
        'fake:blob=fake_default_tls:tcp_md5:repeats={repeats}:tls_mod=rnd,dupsid{seq} ^\n'
        '   --lua-desync=fakeddisorder:pos=midsld'
    ),
    "hostfakesplit": 'hostfakesplit:repeats={repeats}',
    "syndata_multidisorder": (
        'syndata:tls_mod=rnd,rndsni ^\n'
        '   --lua-desync=multidisorder:pos=1,midsld'
    ),
}

HTTP_METHODS = {
    "fake_fakedsplit": (
        'fake:blob=fake_default_http:tcp_md5:ip_autottl=-2,3-20:ip6_autottl=-2,3-20{seq} ^\n'
        '   --lua-desync=fakedsplit:ip_autottl=-2,3-20:ip6_autottl=-2,3-20'
    ),
    "fake_multisplit": (
        'fake:blob=fake_default_http:tcp_md5:ip_autottl=-2,3-20:ip6_autottl=-2,3-20{seq} ^\n'
        '   --lua-desync=multisplit:ip_autottl=-2,3-20:ip6_autottl=-2,3-20'
    ),
    "fake_multidisorder": (
        'fake:blob=fake_default_http:tcp_md5:ip_autottl=-2,3-20:ip6_autottl=-2,3-20{seq} ^\n'
        '   --lua-desync=multidisorder:ip_autottl=-2,3-20:ip6_autottl=-2,3-20'
    ),
    "hostfakesplit": 'hostfakesplit:repeats=4',
}


def _fmt(template: str, repeats=6, tcp_seq=None) -> str:
    seq = f":tcp_seq={tcp_seq}" if tcp_seq is not None else ""
    if "{repeats}" in template or "{seq}" in template:
        return template.format(repeats=repeats, seq=seq)
    return template


# --------------------------------------------------------------------------- #
# SIMPLE mode search space — curated (tls_method, http_method) pairs
# --------------------------------------------------------------------------- #

SIMPLE_SPACE = [
    ("simple_fake_multidisorder", "fake_multidisorder", "fake_multidisorder"),
    ("simple_fake_multisplit", "fake_multisplit", "fake_multisplit"),
    ("simple_fake_fakedsplit", "fake_fakedsplit", "fake_fakedsplit"),
    ("simple_hostfakesplit", "hostfakesplit", "hostfakesplit"),
    ("simple_syndata", "syndata_multidisorder", "fake_fakedsplit"),
]


def _stage1_candidates():
    """Every (tls_key, http_key) pair — the zapret2 analogue of zapret1's
    hostlist/ipset method split: TLS and HTTP traffic may need different
    treatment, so both get searched independently."""
    for tk in TLS_METHODS:
        for hk in HTTP_METHODS:
            yield f"adv_{tk}+{hk}", tk, hk


def _stage2_refine(tls_key, http_key):
    """Refine repeats/tcp_seq around a winning stage-1 pair — there's no
    single zapret1-style '--dpi-desync-fooling' switch here, so the knobs
    that matter are the individual fooling args already used in the
    proven preset2_example.cmd (tcp_md5 always on; tcp_seq and repeats
    are what actually varies between its own two TLS profiles)."""
    for repeats in (4, 6, 11):
        for tcp_seq in (None, -10000):
            name = f"adv_{tls_key}+{http_key}_refine_r{repeats}_seq{tcp_seq or 0}"
            yield name, repeats, tcp_seq


# --------------------------------------------------------------------------- #
# launch/kill for a generated candidate — mirrors zapret_tester's
# test_one_strategy, but for winws2.exe.
# --------------------------------------------------------------------------- #

def _test_one_candidate(engine_dir: Path, cmd_text: str, targets, log, lang):
    tmp_path = engine_dir / f"_gen2_{uuid.uuid4().hex[:8]}.cmd"
    tmp_path.write_text(cmd_text, encoding="utf-8")
    try:
        z2.kill_winws2()
        z2._ensure_windivert_free()
        time.sleep(1)
        subprocess.Popen(
            ["cmd", "/c", str(tmp_path)],
            cwd=str(engine_dir),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        waited = 0.0
        while waited < zt.STRATEGY_WARMUP_SECONDS + 5:
            if z2.winws2_running():
                break
            time.sleep(0.5)
            waited += 0.5
        time.sleep(zt.STRATEGY_WARMUP_SECONDS)

        if not z2.winws2_running():
            log(t(lang, "strategy_didnt_start"))
            return None

        service_results = {}
        for service, hosts in targets.items():
            hits = 0
            detail = []
            for host, kind in hosts:
                ok, info, elapsed = zt.check_target(host, kind)
                detail.append((host, ok, info, elapsed))
                if ok:
                    hits += 1
            service_results[service] = {"score": hits, "total": len(hosts), "detail": detail}
            log(f"    {service:<10} {hits}/{len(hosts)}")

        z2.kill_winws2()
        return service_results
    finally:
        tmp_path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# baseline (no bypass at all)
# --------------------------------------------------------------------------- #

def _measure_baseline(targets, log, lang):
    z2.kill_winws2()
    time.sleep(1)
    log(t(lang, "gen_baseline_start"))
    service_results = {}
    for service, hosts in targets.items():
        hits = 0
        detail = []
        for host, kind in hosts:
            ok, info, elapsed = zt.check_target(host, kind)
            detail.append((host, ok, info, elapsed))
            if ok:
                hits += 1
        service_results[service] = {"score": hits, "total": len(hosts), "detail": detail}
    for service, data in service_results.items():
        log(f"    {service:<10} {data['score']}/{data['total']}")
    return service_results


def _baseline_total(baseline):
    return sum(d["score"] for d in baseline.values())


def _is_inconclusive(baseline, overall_best):
    if not overall_best:
        return False
    best_total = sum(d["score"] for d in overall_best[1].values())
    return best_total <= _baseline_total(baseline)


# --------------------------------------------------------------------------- #
# search loops
# --------------------------------------------------------------------------- #

def _run_simple(engine_dir, targets, log, should_stop, lang):
    all_results, texts = {}, {}
    total = len(SIMPLE_SPACE)
    for i, (name, tls_key, http_key) in enumerate(SIMPLE_SPACE, 1):
        if should_stop():
            log(t(lang, "stopped_by_user"))
            break
        log(f"[{i}/{total}] {name}")
        tls_chain = _fmt(TLS_METHODS[tls_key], repeats=6)
        http_chain = _fmt(HTTP_METHODS[http_key])
        cmd_text = build_cmd_text(name, tls_chain, http_chain)
        res = _test_one_candidate(engine_dir, cmd_text, targets, log, lang)
        if res:
            all_results[name] = res
            texts[name] = cmd_text
    return all_results, texts


def _run_advanced(engine_dir, targets, log, should_stop, lang):
    all_results, texts = {}, {}

    stage1 = list(_stage1_candidates())
    log(t(lang, "gen_stage1", count=len(stage1)))
    for i, (name, tls_key, http_key) in enumerate(stage1, 1):
        if should_stop():
            return all_results, texts
        log(f"[{i}/{len(stage1)}] {name}")
        tls_chain = _fmt(TLS_METHODS[tls_key], repeats=6)
        http_chain = _fmt(HTTP_METHODS[http_key])
        cmd_text = build_cmd_text(name, tls_chain, http_chain)
        res = _test_one_candidate(engine_dir, cmd_text, targets, log, lang)
        if res:
            all_results[name] = res
            texts[name] = cmd_text

    if not all_results or should_stop():
        return all_results, texts

    def overall(res):
        return sum(d["score"] for d in res.values())

    top2_names = sorted(all_results, key=lambda n: overall(all_results[n]), reverse=True)[:2]
    key_lookup = {name: (tk, hk) for name, tk, hk in stage1}

    stage2 = []
    for name in top2_names:
        tk, hk = key_lookup[name]
        stage2.extend((n, tk, hk, r, s) for n, r, s in _stage2_refine(tk, hk))

    log(t(lang, "gen_stage2", count=len(stage2), winners=", ".join(top2_names)))
    for i, (name, tls_key, http_key, repeats, tcp_seq) in enumerate(stage2, 1):
        if should_stop():
            break
        log(f"[{i}/{len(stage2)}] {name}")
        tls_chain = _fmt(TLS_METHODS[tls_key], repeats=repeats, tcp_seq=tcp_seq)
        http_chain = _fmt(HTTP_METHODS[http_key], repeats=repeats, tcp_seq=tcp_seq)
        cmd_text = build_cmd_text(name, tls_chain, http_chain)
        res = _test_one_candidate(engine_dir, cmd_text, targets, log, lang)
        if res:
            all_results[name] = res
            texts[name] = cmd_text

    return all_results, texts


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #

def run_generator(engine_dir: Path, mode: str, targets=None, log=lambda m: None,
                   should_stop=lambda: False, lang="ru"):
    """Same return shape as zapret_generator.run_generator:
    (all_results, best_per_service, overall_best, texts, baseline, inconclusive)."""
    if mode not in ("simple", "advanced"):
        raise ValueError(f"unknown generator mode: {mode}")

    targets = zt.TARGETS if targets is None else targets
    original_snapshot = z2.snapshot_winws2()
    try:
        baseline = _measure_baseline(targets, log, lang)
        if should_stop():
            return {}, {}, None, {}, baseline, False
        if mode == "simple":
            all_results, texts = _run_simple(engine_dir, targets, log, should_stop, lang)
        else:
            all_results, texts = _run_advanced(engine_dir, targets, log, should_stop, lang)
    finally:
        z2.kill_winws2()
        z2.restore_winws2(original_snapshot)

    best_per_service, overall_best = zt.summarize(all_results)
    inconclusive = _is_inconclusive(baseline, overall_best)
    if inconclusive:
        log(t(lang, "gen_inconclusive_warning"))
    return all_results, best_per_service, overall_best, texts, baseline, inconclusive


def save_candidate(engine_dir: Path, texts: dict, candidate_name: str, save_as: str) -> Path:
    """Persist a winning generated candidate as a normal .cmd profile in
    the engine folder, so it shows up like any other zapret2 profile."""
    if candidate_name not in texts:
        raise ValueError(f"unknown candidate: {candidate_name}")
    safe_name = save_as if save_as.lower().endswith(".cmd") else f"{save_as}.cmd"
    out_path = engine_dir / safe_name
    out_path.write_text(texts[candidate_name], encoding="utf-8")
    return out_path
