# -*- coding: ascii -*-
"""ACLTD 2.0 authenticated append-only ledger. Standard library only."""
import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import sys
import threading
import time
from acltd_legacy import strict_loads, verify_legacy

ACLTD_VERSION = "2.0.0"
SCHEMA_VERSION = "acltd-2.0"
GENESIS_HASH = "0" * 64
KNOWN_ENTRY_SCHEMAS = (SCHEMA_VERSION,)
KNOWN_KINDS = ("turn", "fact", "decision", "gap", "note", "checkpoint_intent",
               "checkpoint_commit", "repair", "migration")
TORN_TAIL = "linha final incompleta: use repair_torn_tail com aprova\u00e7\u00e3o"
_locks = {}
_guard = threading.Lock()
_local = threading.local()
_verified = {}


class LedgerError(Exception):
    """Fail-closed storage/authentication error."""


class LedgerBusy(LedgerError):
    """Ledger ocupado; retryable contention, not corruption."""


def _canon(obj):
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as e:
        raise LedgerError("objeto nao canonizavel: " + str(e)) from None


def _key(key):
    try:
        value = key() if callable(key) else key
    except Exception:
        raise LedgerError("fornecedor de chave falhou") from None
    if not isinstance(value, bytes) or not value:
        raise LedgerError("chave bytes nao vazia obrigatoria")
    return value


def _mac(obj, key):
    return hmac.new(_key(key), _canon(obj).encode("ascii"), hashlib.sha256).hexdigest()


def _entry_hash(obj):
    return hashlib.sha256(_canon(obj).encode("ascii")).hexdigest()


def _authenticate(obj, key, label):
    work = dict(obj)
    claimed = work.pop("mac", None)
    if not isinstance(claimed, str) or not hmac.compare_digest(claimed, _mac(work, key)):
        raise LedgerError(label + ": MAC invalido")


def _seal(obj, key):
    obj["mac"] = _mac(obj, key)
    return obj


def encode_data(value, encrypt=None):
    raw = _canon(value).encode("ascii")
    if encrypt is None:
        return value
    try:
        encoded = encrypt(raw)
        if not isinstance(encoded, bytes):
            raise ValueError()
        return base64.b64encode(encoded).decode("ascii")
    except Exception:
        raise LedgerError("gancho encrypt falhou (bytes obrigatorios)") from None


def decode_data(value, encrypted, decrypt=None):
    if not encrypted:
        return value
    if decrypt is None:
        raise LedgerError("decrypt obrigatorio para dados cifrados")
    try:
        raw = decrypt(base64.b64decode(value, validate=True))
        if not isinstance(raw, bytes):
            raise ValueError()
        return strict_loads(raw.decode("ascii"))
    except Exception:
        raise LedgerError("gancho decrypt ou dados cifrados invalidos") from None


def default_anchor_path(ledger_path):
    return os.fspath(ledger_path) + ".anchor"


@contextmanager
def ledger_lock(ledger_path, timeout=10.0):
    """Reentrant per thread, exclusive across OS processes. Never unlink lock."""
    try:
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not 0 <= timeout < float("inf"):
            raise LedgerError("lock_timeout invalido")
        name = os.path.normcase(os.path.realpath(ledger_path))
        with _guard:
            mutex = _locks.setdefault(name, threading.RLock())
        deadline = time.monotonic() + timeout
        if not mutex.acquire(timeout=timeout):
            raise LedgerBusy("ledger ocupado")
        try:
            held = getattr(_local, "held", {})
            if name in held:
                yield
                return
            os.makedirs(os.path.dirname(name), exist_ok=True)
            with open(name + ".lock", "a+b") as handle:
                # Windows permits locking beyond EOF; no racing byte writes.
                while True:
                    try:
                        if os.name == "nt":
                            import msvcrt
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except (OSError, IOError):
                        if time.monotonic() >= deadline:
                            raise LedgerBusy("ledger ocupado") from None
                        time.sleep(min(0.01, max(0, deadline - time.monotonic())))
                held[name] = True
                _local.held = held
                try:
                    yield
                finally:
                    del held[name]
                    if os.name == "nt":
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            mutex.release()
    except (OSError, ValueError, TypeError) as e:
        raise LedgerError("I/O lock: " + str(e)) from None


def fsync_directory(path):
    """POSIX rename durability. Windows has no stdlib directory flush."""
    if os.name != "nt":
        fd = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path, raw):
    # Caller owns the ledger lock for anchor AND checkpoint replacement.
    tmp = os.fspath(path) + ".tmp"
    with open(tmp, "wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    fsync_directory(path)


def _write_anchor(anchor_path, seq, head_hash, key=None, offset=0, end=0):
    anchor = _seal({"schema": "acltd-anchor-2.0", "seq": seq, "hash": head_hash,
                    "offset": offset, "end": end}, key)
    atomic_write(anchor_path, _canon(anchor).encode("ascii"))


def _read_anchor(path, key):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        a = strict_loads(raw.decode("ascii"))
        if not isinstance(a, dict) or a.get("schema") != "acltd-anchor-2.0":
            raise LedgerError("ancora com schema desconhecido")
        _authenticate(a, key, "ancora")
        if (type(a.get("seq")) is not int or a["seq"] < 0
                or type(a.get("offset")) is not int or type(a.get("end")) is not int
                or not 0 <= a["offset"] < a["end"] or not isinstance(a.get("hash"), str)):
            raise LedgerError("ancora invalida: campos seq/hash/offset/end")
        if raw != _canon(a).encode("ascii"):
            raise LedgerError("ancora nao canonica")
        return a
    except (OSError, ValueError, TypeError, RecursionError) as e:
        raise LedgerError("ancora invalida: " + str(e)) from None


def _parse_line(raw):
    try:
        text = raw.decode("ascii")
        obj = strict_loads(text)
        if not isinstance(obj, dict) or text != _canon(obj):
            raise LedgerError("linha nao canonica")
        if obj.get("schema") != SCHEMA_VERSION:
            raise LedgerError("schema desconhecido; legado somente verify_legacy")
        if obj.get("kind") not in KNOWN_KINDS:
            raise LedgerError("kind desconhecido")
        if type(obj.get("encrypted")) is not bool:
            raise LedgerError("flag encrypted invalida")
        if not isinstance(obj.get("payload"), str if obj["encrypted"] else dict):
            raise LedgerError("payload invalido")
        if obj["encrypted"]:
            base64.b64decode(obj["payload"], validate=True)
        return obj
    except (ValueError, TypeError, RecursionError) as e:
        raise LedgerError("linha invalida: " + str(e)) from None


def _read_entries(ledger_path):
    try:
        if not os.path.exists(ledger_path):
            return []
        with open(ledger_path, "rb") as f:
            raw = f.read()
        if raw and not raw.endswith(b"\n"):
            raise LedgerError(TORN_TAIL)
        return [_parse_line(line) for line in raw.split(b"\n")[:-1]]
    except OSError as e:
        raise LedgerError("leitura do ledger falhou: " + str(e)) from None


def _check_entry(obj, seq, prev, key):
    if type(obj.get("seq")) is not int or obj["seq"] != seq:
        raise LedgerError("seq nao monotonico")
    if obj.get("prev_hash") != prev:
        raise LedgerError("quebra de cadeia prev_hash")
    if type(obj.get("external_action_allowed")) is not int or obj["external_action_allowed"] != 0:
        raise LedgerError("invariante fail-closed violada")
    work = dict(obj)
    claimed = work.pop("hash", None)
    if claimed != _entry_hash(work):
        raise LedgerError("hash adulterado")
    _authenticate(work, key, "entrada")


def _head_matches(expected, seq, digest):
    if expected is None:
        return
    if isinstance(expected, dict):
        match = expected == {"seq": seq, "head_hash": digest}
    else:
        match = isinstance(expected, (tuple, list)) and list(expected) == [seq, digest]
    if not match:
        raise LedgerError("cabeca externa divergente (expected_head)")


def _verify(ledger_path, anchor_path, key, expected_head=None):
    entries = _read_entries(ledger_path)
    prev = GENESIS_HASH
    offsets = []
    offset = 0
    for seq, obj in enumerate(entries):
        _check_entry(obj, seq, prev, key)
        end = offset + len(_canon(obj)) + 1
        offsets.append((offset, end))
        offset = end
        prev = obj["hash"]
    a = _read_anchor(anchor_path, key)
    if entries and a is None:
        raise LedgerError("ledger nao vazio sem ancora")
    if a is not None:
        seq = a["seq"]
        if seq >= len(entries):
            raise LedgerError("ledger truncado abaixo da ancora (rollback)")
        if (a["hash"] != entries[seq]["hash"]
                or (a["offset"], a["end"]) != offsets[seq]):
            raise LedgerError("ledger divergente da ancora")
        if len(entries) - 1 - seq > 1:
            raise LedgerError("ancora atrasada demais")
    _head_matches(expected_head, len(entries) - 1, prev)
    return {"entries": len(entries), "head_hash": prev, "anchored": a is not None}


def verify_chain(ledger_path, anchor_path=None, *, key=None, expected_head=None,
                 lock_timeout=10.0):
    """Full verification mandatory at mission open and restore. Busy raises."""
    try:
        key = _key(key)
        with ledger_lock(ledger_path, lock_timeout):
            det = _verify(ledger_path, anchor_path or default_anchor_path(ledger_path), key, expected_head)
            return True, det
    except LedgerBusy:
        raise
    except (LedgerError, OSError, ValueError, TypeError, RecursionError) as e:
        return False, {"error": str(e), "fail_closed": True}


def _fingerprint(path):
    if not os.path.exists(path):
        return None
    s = os.stat(path)
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _tail_head(lp, ap, key):
    """Only authenticated anchor's head and at most one unanchored entry."""
    a = _read_anchor(ap, key)
    size = os.path.getsize(lp) if os.path.exists(lp) else 0
    if a is None:
        if size:
            raise LedgerError("ledger nao vazio sem ancora")
        return -1, GENESIS_HASH
    if size < a["end"]:
        raise LedgerError("ledger truncado abaixo da ancora")
    with open(lp, "rb") as f:
        f.seek(a["offset"])
        raw = f.read(a["end"] - a["offset"])
        if not raw.endswith(b"\n"):
            raise LedgerError(TORN_TAIL)
        obj = _parse_line(raw[:-1])
        _check_entry(obj, a["seq"], obj.get("prev_hash"), key)
        if obj["hash"] != a["hash"]:
            raise LedgerError("ledger divergente da ancora")
        tail = f.read()
    if tail:
        if not tail.endswith(b"\n"):
            raise LedgerError(TORN_TAIL)
        if tail.count(b"\n") != 1:
            raise LedgerError("ancora atrasada demais")
        next_obj = _parse_line(tail[:-1])
        _check_entry(next_obj, obj["seq"] + 1, obj["hash"], key)
        obj = next_obj
    return obj["seq"], obj["hash"]


def append_entry(ledger_path, kind, payload, agent="unknown", anchor_path=None,
                 *, key=None, on_head=None, encrypt=None, lock_timeout=10.0):
    key = _key(key)
    if kind not in KNOWN_KINDS or not isinstance(payload, dict) or not isinstance(agent, str):
        raise LedgerError("kind/payload/agent invalido")
    if on_head is not None and not callable(on_head):
        raise LedgerError("on_head deve ser funcao")
    encoded = encode_data(payload, encrypt)
    try:
        lp = os.fspath(ledger_path)
        ap = anchor_path or default_anchor_path(lp)
        with ledger_lock(lp, lock_timeout):
            identity = (os.path.realpath(lp), os.path.realpath(ap), hashlib.sha256(key).digest())
            fingerprint = (_fingerprint(lp), _fingerprint(ap))
            # Full on opening in each process and on unexpected external changes.
            # Normal own appends authenticate only the anchor and tail.
            if identity not in _verified or _verified[identity] != fingerprint:
                _verify(lp, ap, key)
            seq, prev = _tail_head(lp, ap, key)
            obj = _seal({"schema": SCHEMA_VERSION, "seq": seq + 1,
                         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                         "agent": agent, "kind": kind, "payload": encoded,
                         "encrypted": encrypt is not None,
                         "external_action_allowed": 0, "prev_hash": prev}, key)
            obj["hash"] = _entry_hash(obj)
            offset = os.path.getsize(lp) if os.path.exists(lp) else 0
            with open(ledger_path, "a", encoding="ascii", newline="\n") as f:
                f.write(_canon(obj) + "\n")
                f.flush()
                os.fsync(f.fileno())
            if offset == 0:
                fsync_directory(lp)
            _write_anchor(ap, obj["seq"], obj["hash"], key, offset, offset + len(_canon(obj)) + 1)
            _verified[identity] = (_fingerprint(lp), _fingerprint(ap))
            if on_head:
                try:
                    on_head(obj["seq"], obj["hash"])
                except Exception:
                    raise LedgerError("on_head falhou; append local ja persistido; reconciliar cabeca externa") from None
            return obj
    except (OSError, ValueError, TypeError, RecursionError) as e:
        raise LedgerError("append I/O/estrutura falhou; verificar estado persistido: " + str(e)) from None


def last_entries_of_kind(ledger_path, kind, *, key=None, decrypt=None, anchor_path=None):
    with ledger_lock(ledger_path):
        ok, det = verify_chain(ledger_path, anchor_path, key=key)
        if not ok:
            raise LedgerError(str(det))
        result = []
        for obj in _read_entries(ledger_path):
            if obj["kind"] == kind:
                obj["payload"] = decode_data(obj["payload"], obj["encrypted"], decrypt)
                result.append(obj)
        return result


def approval_text(value, field="approver"):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\v\f\x85\u2028\u2029"):
        raise LedgerError(field + " obrigatorio, texto de uma linha")
    return value


def repair_torn_tail(ledger_path, key, approver, reason, *, anchor_path=None,
                     encrypt=None, on_head=None, lock_timeout=10.0):
    key = _key(key)
    approval_text(approver)
    approval_text(reason, "reason")
    try:
        ap = anchor_path or default_anchor_path(ledger_path)
        with ledger_lock(ledger_path, lock_timeout):
            with open(ledger_path, "rb") as f:
                raw = f.read()
            cut = raw.rfind(b"\n") + 1
            tail = raw[cut:]
            if not tail:
                raise LedgerError("sem linha final incompleta")
            try:
                # Complete canonical JSON missing ONLY LF must never be cut,
                # even if its schema/MAC is wrong. Human investigation required.
                obj = strict_loads(tail.decode("ascii"))
                canonical = isinstance(obj, dict) and _canon(obj).encode("ascii") == tail
            except (ValueError, LedgerError, RecursionError):
                canonical = False
            if canonical:
                raise LedgerError("linha final canonica sem LF: reparo destrutivo recusado")
            # Verify complete prefix and anchor BEFORE truncating anything.
            entries = [_parse_line(line) for line in raw[:cut].split(b"\n")[:-1]]
            prev = GENESIS_HASH
            offsets = []
            pos = 0
            for seq, obj in enumerate(entries):
                _check_entry(obj, seq, prev, key)
                end = pos + len(_canon(obj)) + 1
                offsets.append((pos, end))
                pos = end
                prev = obj["hash"]
            a = _read_anchor(ap, key)
            if entries:
                if (a is None or a["seq"] >= len(entries) or len(entries)-1-a["seq"] > 1
                        or a["hash"] != entries[a["seq"]]["hash"]
                        or (a["offset"], a["end"]) != offsets[a["seq"]]):
                    raise LedgerError("prefixo/ancora invalido; reparo recusado")
            elif a is not None:
                raise LedgerError("ancora alem do prefixo; reparo recusado")
            if on_head is not None and not callable(on_head):
                raise LedgerError("on_head deve ser funcao")
            payload = {"removed_bytes": len(tail),
                       "removed_sha256": hashlib.sha256(tail).hexdigest(),
                       "approver": approver, "reason": reason}
            # Build/authenticate the whole audit entry BEFORE touching bytes.
            encoded = encode_data(payload, encrypt)
            obj = _seal({"schema": SCHEMA_VERSION, "seq": len(entries),
                         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                         "agent": "acltd_repair", "kind": "repair", "payload": encoded,
                         "encrypted": encrypt is not None, "external_action_allowed": 0,
                         "prev_hash": prev}, key)
            obj["hash"] = _entry_hash(obj)
            line = (_canon(obj) + "\n").encode("ascii")
            with open(ledger_path, "r+b") as f:
                f.truncate(cut)
                f.seek(cut)
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            _write_anchor(ap, obj["seq"], obj["hash"], key, cut, cut + len(line))
            if on_head is not None:
                try:
                    on_head(obj["seq"], obj["hash"])
                except Exception:
                    raise LedgerError("on_head falhou; reparo local ja persistido; reconciliar cabeca externa") from None
            return obj
    except (OSError, ValueError, TypeError, RecursionError) as e:
        raise LedgerError("reparo I/O/estrutura falhou: " + str(e)) from None


def migrate_from_legacy(legacy_path, ledger_path, key, approver, *, legacy_anchor_path=None,
                        on_head=None, encrypt=None):
    approval_text(approver)
    _key(key)
    with ledger_lock(legacy_path), ledger_lock(ledger_path):
        if os.path.realpath(legacy_path) == os.path.realpath(ledger_path) or os.path.exists(ledger_path) or os.path.exists(default_anchor_path(ledger_path)):
            raise LedgerError("migracao exige diario NOVO em caminho distinto")
        ok, det = verify_legacy(legacy_path, legacy_anchor_path)
        if not ok or not det.get("entries"):
            raise LedgerError("legado invalido/vazio: " + str(det))
        return append_entry(ledger_path, "migration", {"legacy_head": det["head_hash"],
                            "legacy_entries": det["entries"], "approver": approver,
                            "legacy_authenticated": False}, key=key, on_head=on_head, encrypt=encrypt)


if __name__ == "__main__":
    print(json.dumps({"ok": False, "external_action_allowed": 0,
                      "error": "use API com chave bytes/funcao; CLI nao recebe segredos"}))
    sys.exit(2)
