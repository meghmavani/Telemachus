"""Operator principal resolution: is this process running as the pinned operator?

Resolves the Windows security identifier (SID) of the account the
Telemachus *process* runs as, read from the process token, and compares
it with an explicitly configured operator SID (``authorization.operator_sid``).

What a match establishes, and nothing more: the process token's account
SID equals the SID the operator pinned in configuration. It is an
account-identity check under a configured policy. It is **not**
authentication of a person, not evidence that anyone is at the keyboard,
and not approval of anything. The threat model excludes malicious
software already running as the same Windows user, which could act with
this account's identity regardless.

The SID is never taken from environment variables (``USERNAME``,
``USER``), ``getpass.getuser()``, ``os.getlogin()``, display names,
``Identity.creator``, configuration text other than the pin itself,
chat input, model output or caller context. An absent, blank or
malformed pin, or an unresolvable process identity, fails closed.

This module does not issue, record or verify grants, read approval
input, or touch the Constitution, pipeline, CLI, tools or Runtime.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

# S-1-<identifier authority>-<sub-authority>... : at least one and at most
# 15 sub-authorities (SID_MAX_SUB_AUTHORITIES), no leading zeros, upper-case
# "S" as produced by ConvertSidToStringSidW.
_SID_RE = re.compile(r"^S-1-(0|[1-9][0-9]*)((?:-(?:0|[1-9][0-9]*)){1,15})$")
_MAX_IDENTIFIER_AUTHORITY = 2**48 - 1
_MAX_SUB_AUTHORITY = 2**32 - 1


def is_well_formed_sid(value: object) -> bool:
    """Whether ``value`` is a canonical Windows SID string."""
    if type(value) is not str:
        return False
    match = _SID_RE.match(value)
    if match is None:
        return False
    if int(match.group(1)) > _MAX_IDENTIFIER_AUTHORITY:
        return False
    return all(int(part) <= _MAX_SUB_AUTHORITY for part in match.group(2)[1:].split("-"))


class ProcessIdentityError(RuntimeError):
    """The process account SID could not be obtained."""


# Low-level boundary: returns the process account SID string or raises.
ProcessSidSource = Callable[[], str]


def windows_process_sid() -> str:
    """Return the SID string of the account in this process's token.

    Uses ``OpenProcessToken`` on the current process (not the thread, so
    impersonation does not change the answer), ``GetTokenInformation``
    with ``TokenUser``, and ``ConvertSidToStringSidW``. The token handle
    is closed and the converted string freed with ``LocalFree`` on every
    path.

    Raises:
        ProcessIdentityError: On non-Windows platforms or on any
            Win32 failure.
    """
    if sys.platform != "win32":
        raise ProcessIdentityError(
            f"process SID lookup requires Windows (platform is {sys.platform!r})"
        )

    import ctypes
    from ctypes import wintypes

    token_query = 0x0008
    token_user_class = 1  # TokenUser
    error_insufficient_buffer = 122

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

    def _fail(call: str) -> ProcessIdentityError:
        return ProcessIdentityError(
            f"{call} failed (Win32 error {ctypes.get_last_error()})"
        )

    token = wintypes.HANDLE()
    # GetCurrentProcess returns a pseudo-handle that must not be closed.
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), token_query, ctypes.byref(token)
    ):
        raise _fail("OpenProcessToken")
    try:
        needed = wintypes.DWORD(0)
        advapi32.GetTokenInformation(token, token_user_class, None, 0, ctypes.byref(needed))
        if ctypes.get_last_error() != error_insufficient_buffer or needed.value == 0:
            raise _fail("GetTokenInformation (size query)")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(
            token, token_user_class, buffer, needed, ctypes.byref(needed)
        ):
            raise _fail("GetTokenInformation")
        # TOKEN_USER begins with SID_AND_ATTRIBUTES, whose first field is PSID.
        sid_pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents.value
        if not sid_pointer:
            raise ProcessIdentityError("TokenUser contained no SID")
        sid_string = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(sid_pointer, ctypes.byref(sid_string)):
            raise _fail("ConvertSidToStringSidW")
        try:
            value = sid_string.value
        finally:
            kernel32.LocalFree(ctypes.cast(sid_string, wintypes.HLOCAL))
    finally:
        kernel32.CloseHandle(token)

    if not value:
        raise ProcessIdentityError("ConvertSidToStringSidW returned an empty string")
    return value


class OperatorMatch(Enum):
    """Result of comparing the process account with the pinned operator.

    Only ``MATCHES_PINNED_OPERATOR`` is a positive result, and it means
    an account-identity match, not authentication or approval.
    """

    MATCHES_PINNED_OPERATOR = "matches_pinned_operator"
    DIFFERENT_ACCOUNT = "different_account"
    NO_OPERATOR_PINNED = "no_operator_pinned"
    INVALID_OPERATOR_PIN = "invalid_operator_pin"
    PROCESS_IDENTITY_UNAVAILABLE = "process_identity_unavailable"


@dataclass(frozen=True)
class OperatorResolution:
    """Outcome of ``resolve_operator()``.

    Attributes:
        status: What was found.
        process_sid: The process account SID, if it was resolved.
        pinned_sid: The configured pin, if one was set (even if malformed).
        detail: Human-readable explanation; not used for control flow.
    """

    status: OperatorMatch
    process_sid: str | None = None
    pinned_sid: str | None = None
    detail: str = ""

    @property
    def matches_pinned_operator(self) -> bool:
        """True only for an exact SID match with a valid configured pin."""
        return self.status is OperatorMatch.MATCHES_PINNED_OPERATOR


def resolve_operator(
    pinned_sid: str | None,
    *,
    sid_source: ProcessSidSource = windows_process_sid,
) -> OperatorResolution:
    """Compare the process account SID with the configured operator pin.

    Args:
        pinned_sid: ``authorization.operator_sid`` from configuration.
            ``None`` or blank means no operator is pinned. Never filled
            in from the current account.
        sid_source: Where the process SID comes from. Production uses
            ``windows_process_sid``; tests inject a fake.

    Returns:
        An ``OperatorResolution``. Every failure is a non-matching status;
        this function does not raise for them.
    """
    if pinned_sid is None or (type(pinned_sid) is str and not pinned_sid.strip()):
        return OperatorResolution(
            OperatorMatch.NO_OPERATOR_PINNED, detail="no authorization.operator_sid configured"
        )
    if not is_well_formed_sid(pinned_sid):
        return OperatorResolution(
            OperatorMatch.INVALID_OPERATOR_PIN,
            pinned_sid=str(pinned_sid),
            detail="configured operator_sid is not a well-formed SID",
        )

    try:
        process_sid = sid_source()
    except Exception as exc:  # any lookup failure fails closed
        return OperatorResolution(
            OperatorMatch.PROCESS_IDENTITY_UNAVAILABLE, pinned_sid=pinned_sid, detail=str(exc)
        )
    if not is_well_formed_sid(process_sid):
        return OperatorResolution(
            OperatorMatch.PROCESS_IDENTITY_UNAVAILABLE,
            pinned_sid=pinned_sid,
            detail="process identity source returned a malformed SID",
        )

    if process_sid != pinned_sid:
        return OperatorResolution(
            OperatorMatch.DIFFERENT_ACCOUNT,
            process_sid=process_sid,
            pinned_sid=pinned_sid,
            detail="process account SID does not match the pinned operator",
        )
    return OperatorResolution(
        OperatorMatch.MATCHES_PINNED_OPERATOR, process_sid=process_sid, pinned_sid=pinned_sid
    )
