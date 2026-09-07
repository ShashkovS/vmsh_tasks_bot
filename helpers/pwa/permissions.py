"""Fail-closed authorization rules for the three PWA audiences.

This module deliberately has no aiohttp or persistence dependency.  The auth
service turns repository records into the small immutable grants below, then
middleware and route services evaluate capabilities and object scope here.

The governing rules live in ``vmshpwa/dev/development-plan/05-phase-1-auth.md``
and ``vmshpwa/docs/authentication-and-security.md``.  In particular, a legacy
``USER_TYPE.ADMIN`` is global, while ``role='admin'`` on a ``staff_scopes`` row
never promotes a legacy teacher.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from helpers.consts import USER_TYPE
from models.pwa.auth import AuthAudience


_PUBLIC_ID = re.compile(r"[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?")


class PrincipalIntegrityError(ValueError):
    """Authenticated rows cannot safely form an authorization principal."""


class AuthenticationRequiredError(PermissionError):
    """The caller has no authenticated principal for the requested audience."""

    code = "authentication_required"


class AccessForbiddenError(PermissionError):
    """The principal is authenticated but lacks capability or object scope."""

    code = "forbidden"


class PrincipalRole(StrEnum):
    STUDENT = "student"
    FAMILY = "family"
    TEACHER = "teacher"
    ADMIN = "admin"


class StaffScopeRole(StrEnum):
    TEACHER = "teacher"
    ADMIN = "admin"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Capability(StrEnum):
    """Stable backend capabilities exposed to route middleware.

    Capabilities answer *what* an identity may do.  Course, group and student
    checks below independently answer *to which object* it may do it.
    """

    ACCOUNT_SESSIONS_MANAGE = "account.sessions.manage"
    SELF_READ = "self.read"
    COURSE_READ = "course.read"
    GROUP_READ = "group.read"
    OWN_WORK_READ = "own-work.read"
    SUBMISSION_MANAGE = "submission.manage"
    THREAD_MANAGE = "thread.manage"
    PROGRESS_READ = "progress.read"
    NEWS_READ = "news.read"
    NOTIFICATION_MANAGE = "notification.manage"
    FAMILY_CHILD_READ = "family-child.read"
    STUDENT_READ = "student.read"
    REVIEW_READ = "review.read"
    REVIEW_WRITE = "review.write"
    ORAL_MANAGE = "oral.manage"
    STUDENT_ACTIVE_GROUP_WRITE = "student.active-group.write"
    STATISTICS_READ = "statistics.read"
    PRODUCT_ANALYTICS_READ = "product-analytics.read"
    COURSE_MANAGE = "course.manage"
    GROUP_MANAGE = "group.manage"
    CONTENT_MANAGE = "content.manage"
    CHECKER_MANAGE = "checker.manage"
    BROADCAST_MANAGE = "broadcast.manage"
    CLASSROOM_MANAGE = "classroom.manage"
    AUDIT_READ = "audit.read"
    STAFF_MANAGE = "staff.manage"
    TELEGRAM_BINDING_MANAGE = "telegram-binding.manage"


_COMMON_CAPABILITIES = frozenset({Capability.ACCOUNT_SESSIONS_MANAGE})

_STUDENT_CAPABILITIES = _COMMON_CAPABILITIES | frozenset(
    {
        Capability.SELF_READ,
        Capability.COURSE_READ,
        Capability.GROUP_READ,
        Capability.OWN_WORK_READ,
        Capability.SUBMISSION_MANAGE,
        Capability.THREAD_MANAGE,
        Capability.PROGRESS_READ,
        Capability.NEWS_READ,
        Capability.NOTIFICATION_MANAGE,
    }
)

_FAMILY_CAPABILITIES = _COMMON_CAPABILITIES | frozenset(
    {
        Capability.SELF_READ,
        Capability.FAMILY_CHILD_READ,
        Capability.COURSE_READ,
        Capability.GROUP_READ,
        Capability.PROGRESS_READ,
        Capability.NEWS_READ,
        Capability.NOTIFICATION_MANAGE,
    }
)

_TEACHER_CAPABILITIES = _COMMON_CAPABILITIES | frozenset(
    {
        Capability.SELF_READ,
        Capability.COURSE_READ,
        Capability.GROUP_READ,
        Capability.STUDENT_READ,
        Capability.REVIEW_READ,
        Capability.REVIEW_WRITE,
        Capability.ORAL_MANAGE,
        Capability.STUDENT_ACTIVE_GROUP_WRITE,
        Capability.STATISTICS_READ,
    }
)

_TEACHER_SCOPED_CAPABILITIES = _TEACHER_CAPABILITIES - frozenset(
    {
        Capability.ACCOUNT_SESSIONS_MANAGE,
        Capability.SELF_READ,
    }
)

_ADMIN_ONLY_CAPABILITIES = frozenset(
    {
        Capability.COURSE_MANAGE,
        Capability.GROUP_MANAGE,
        Capability.CONTENT_MANAGE,
        Capability.CHECKER_MANAGE,
        Capability.BROADCAST_MANAGE,
        Capability.CLASSROOM_MANAGE,
        Capability.AUDIT_READ,
        Capability.PRODUCT_ANALYTICS_READ,
        Capability.STAFF_MANAGE,
        Capability.TELEGRAM_BINDING_MANAGE,
    }
)

_ADMIN_CAPABILITIES = _TEACHER_CAPABILITIES | _ADMIN_ONLY_CAPABILITIES


@dataclass(frozen=True, slots=True)
class CourseEnrollmentGrant:
    """Current per-student course/group access loaded from SQLite."""

    student_user_id: int
    course_public_id: str
    active_group_public_id: str
    allowed_group_public_ids: frozenset[str]
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE

    def __post_init__(self) -> None:
        _require_user_id(self.student_user_id)
        _require_public_id(self.course_public_id, label="course public ID")
        _require_public_id(
            self.active_group_public_id,
            label="active group public ID",
        )
        allowed = frozenset(self.allowed_group_public_ids)
        for group_public_id in allowed:
            _require_public_id(group_public_id, label="allowed group public ID")
        object.__setattr__(self, "allowed_group_public_ids", allowed)
        try:
            status = EnrollmentStatus(self.status)
        except (TypeError, ValueError) as error:
            raise PrincipalIntegrityError("Unknown enrollment status") from error
        object.__setattr__(self, "status", status)
        if status is EnrollmentStatus.ACTIVE and (
            not allowed or self.active_group_public_id not in allowed
        ):
            raise PrincipalIntegrityError(
                "Active enrollment requires its active group in allowed groups"
            )


@dataclass(frozen=True, slots=True)
class StaffScopeGrant:
    """One currently effective staff scope, expressed only in public IDs."""

    course_public_id: str
    group_public_id: str | None
    role: StaffScopeRole

    def __post_init__(self) -> None:
        _require_public_id(self.course_public_id, label="course public ID")
        if self.group_public_id is not None:
            _require_public_id(self.group_public_id, label="group public ID")
        try:
            role = StaffScopeRole(self.role)
        except (TypeError, ValueError) as error:
            raise PrincipalIntegrityError("Unknown staff scope role") from error
        object.__setattr__(self, "role", role)


class CourseEnrollmentRecordLike(Protocol):
    """Structural boundary implemented by ``db_methods.pwa.auth`` records."""

    course_public_id: str
    active_group_public_id: str
    enrollment_status: str
    allowed_groups: Iterable[object]


class StaffScopeRecordLike(Protocol):
    """Structural boundary implemented by ``db_methods.pwa.auth`` records."""

    course_public_id: str
    group_public_id: str | None
    role: object


def enrollment_grant_from_record(
    *,
    student_user_id: int,
    record: CourseEnrollmentRecordLike,
) -> CourseEnrollmentGrant:
    """Adapt a repository enrollment without importing the repository layer."""

    try:
        allowed_group_public_ids = frozenset(
            _record_public_id(group, attribute="group_public_id")
            for group in record.allowed_groups
        )
        status = EnrollmentStatus(record.enrollment_status)
    except (AttributeError, TypeError, ValueError) as error:
        raise PrincipalIntegrityError("Invalid course enrollment record") from error
    return CourseEnrollmentGrant(
        student_user_id=student_user_id,
        course_public_id=record.course_public_id,
        active_group_public_id=record.active_group_public_id,
        allowed_group_public_ids=allowed_group_public_ids,
        status=status,
    )


def staff_scope_grant_from_record(record: StaffScopeRecordLike) -> StaffScopeGrant:
    """Adapt an effective repository scope without a persistence dependency."""

    try:
        role = StaffScopeRole(str(record.role))
    except (AttributeError, TypeError, ValueError) as error:
        raise PrincipalIntegrityError("Invalid staff scope record") from error
    return StaffScopeGrant(
        course_public_id=record.course_public_id,
        group_public_id=record.group_public_id,
        role=role,
    )


@dataclass(frozen=True, slots=True)
class AuthorizationPrincipal:
    """Server-authoritative, immutable authorization context for one session."""

    account_public_id: str
    session_public_id: str
    session_version: int
    credential_version: int
    audience: AuthAudience
    role: PrincipalRole
    linked_user_id: int | None
    capabilities: frozenset[Capability]
    linked_student_user_ids: frozenset[int]
    enrollment_grants: tuple[CourseEnrollmentGrant, ...]
    staff_scope_grants: tuple[StaffScopeGrant, ...]

    def __post_init__(self) -> None:
        _require_public_id(self.account_public_id, label="account public ID")
        _require_public_id(self.session_public_id, label="session public ID")
        _require_positive_version(self.session_version, label="session version")
        _require_positive_version(
            self.credential_version,
            label="credential version",
        )
        try:
            audience = AuthAudience(self.audience)
            role = PrincipalRole(self.role)
            capabilities = frozenset(Capability(value) for value in self.capabilities)
        except (TypeError, ValueError) as error:
            raise PrincipalIntegrityError("Unknown principal enum value") from error
        object.__setattr__(self, "audience", audience)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "capabilities", capabilities)
        child_ids = frozenset(_checked_user_ids(self.linked_student_user_ids))
        enrollments = _normalize_enrollments(self.enrollment_grants)
        staff_scopes = _normalize_staff_scopes(self.staff_scope_grants)
        object.__setattr__(self, "linked_student_user_ids", child_ids)
        object.__setattr__(self, "enrollment_grants", enrollments)
        object.__setattr__(self, "staff_scope_grants", staff_scopes)

        expected_audience = {
            PrincipalRole.STUDENT: AuthAudience.STUDENT,
            PrincipalRole.FAMILY: AuthAudience.FAMILY,
            PrincipalRole.TEACHER: AuthAudience.STAFF,
            PrincipalRole.ADMIN: AuthAudience.STAFF,
        }[role]
        expected_capabilities = {
            PrincipalRole.STUDENT: _STUDENT_CAPABILITIES,
            PrincipalRole.FAMILY: _FAMILY_CAPABILITIES,
            PrincipalRole.TEACHER: _TEACHER_CAPABILITIES,
            PrincipalRole.ADMIN: _ADMIN_CAPABILITIES,
        }[role]
        if audience is not expected_audience or capabilities != expected_capabilities:
            raise PrincipalIntegrityError(
                "Principal role, audience and capabilities are inconsistent"
            )
        if role is PrincipalRole.STUDENT:
            if self.linked_user_id is None:
                raise PrincipalIntegrityError("Student principal has no user identity")
            _require_user_id(self.linked_user_id)
            if (
                child_ids
                or staff_scopes
                or any(
                    grant.student_user_id != self.linked_user_id
                    for grant in enrollments
                )
            ):
                raise PrincipalIntegrityError("Student principal has foreign grants")
        elif role is PrincipalRole.FAMILY:
            if (
                self.linked_user_id is not None
                or staff_scopes
                or any(grant.student_user_id not in child_ids for grant in enrollments)
            ):
                raise PrincipalIntegrityError("Family principal has foreign grants")
        else:
            if self.linked_user_id is None or child_ids or enrollments:
                raise PrincipalIntegrityError("Staff principal has foreign grants")
            _require_user_id(self.linked_user_id)

    @property
    def is_global_admin(self) -> bool:
        return self.role is PrincipalRole.ADMIN

    @property
    def capability_names(self) -> tuple[str, ...]:
        """Return a stable order for API serialization and cache keys."""

        return tuple(sorted(capability.value for capability in self.capabilities))

    def has_capability(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def owns_or_links_student(self, student_user_id: int) -> bool:
        """Check identity ownership without granting staff unscoped access."""

        if self.role is PrincipalRole.STUDENT:
            return self.linked_user_id == student_user_id
        if self.role is PrincipalRole.FAMILY:
            return student_user_id in self.linked_student_user_ids
        return self.is_global_admin

    def enrollment_for(
        self,
        *,
        student_user_id: int,
        course_public_id: str,
    ) -> CourseEnrollmentGrant | None:
        """Return one active enrollment; inactive rows never authorize."""

        for grant in self.enrollment_grants:
            if (
                grant.status is EnrollmentStatus.ACTIVE
                and grant.student_user_id == student_user_id
                and grant.course_public_id == course_public_id
            ):
                return grant
        return None

    def has_staff_course_access(self, course_public_id: str) -> bool:
        if self.is_global_admin:
            return True
        if self.role is not PrincipalRole.TEACHER:
            return False
        return any(
            scope.course_public_id == course_public_id
            for scope in self.staff_scope_grants
        )

    def has_staff_course_wide_scope(self, course_public_id: str) -> bool:
        if self.is_global_admin:
            return True
        if self.role is not PrincipalRole.TEACHER:
            return False
        return any(
            scope.course_public_id == course_public_id and scope.group_public_id is None
            for scope in self.staff_scope_grants
        )

    def has_staff_group_access(
        self,
        *,
        course_public_id: str,
        group_public_id: str,
    ) -> bool:
        if self.is_global_admin:
            return True
        if self.role is not PrincipalRole.TEACHER:
            return False
        return any(
            scope.course_public_id == course_public_id
            and (
                scope.group_public_id is None
                or scope.group_public_id == group_public_id
            )
            for scope in self.staff_scope_grants
        )

    def can_access_student(
        self,
        student_user_id: int,
        *,
        course_public_id: str | None = None,
        group_public_id: str | None = None,
    ) -> bool:
        """Check object ownership and, when present, its course/group scope.

        This method proves Student/Family ownership only. Staff must first load
        the target resource (or membership) from SQLite and authorize the
        *loaded* course/group through ``evaluate_access`` without combining an
        attacker-controlled student ID with an unrelated allowed group.
        """

        if group_public_id is not None and course_public_id is None:
            raise ValueError("A group authorization check requires its course")
        if self.is_global_admin:
            return True
        if self.role is PrincipalRole.TEACHER:
            return False
        if not self.owns_or_links_student(student_user_id):
            return False
        if course_public_id is None:
            return True
        enrollment = self.enrollment_for(
            student_user_id=student_user_id,
            course_public_id=course_public_id,
        )
        if enrollment is None:
            return False
        return (
            group_public_id is None
            or group_public_id in enrollment.allowed_group_public_ids
        )

    def can_access_course(
        self,
        course_public_id: str,
        *,
        student_user_id: int | None = None,
        require_course_wide: bool = False,
    ) -> bool:
        if self.is_global_admin:
            return True
        if self.role is PrincipalRole.TEACHER:
            if require_course_wide:
                return self.has_staff_course_wide_scope(course_public_id)
            return self.has_staff_course_access(course_public_id)
        if require_course_wide:
            return False
        target_student_id = self._resolve_student_target(student_user_id)
        if target_student_id is None:
            return False
        return (
            self.enrollment_for(
                student_user_id=target_student_id,
                course_public_id=course_public_id,
            )
            is not None
        )

    def can_access_group(
        self,
        *,
        course_public_id: str,
        group_public_id: str,
        student_user_id: int | None = None,
    ) -> bool:
        if self.is_global_admin:
            return True
        if self.role is PrincipalRole.TEACHER:
            return self.has_staff_group_access(
                course_public_id=course_public_id,
                group_public_id=group_public_id,
            )
        target_student_id = self._resolve_student_target(student_user_id)
        if target_student_id is None:
            return False
        enrollment = self.enrollment_for(
            student_user_id=target_student_id,
            course_public_id=course_public_id,
        )
        return (
            enrollment is not None
            and group_public_id in enrollment.allowed_group_public_ids
        )

    def _resolve_student_target(self, student_user_id: int | None) -> int | None:
        if self.role is PrincipalRole.STUDENT:
            if student_user_id is None:
                return self.linked_user_id
            return student_user_id if student_user_id == self.linked_user_id else None
        if self.role is PrincipalRole.FAMILY:
            # Family may link several children.  Requiring an explicit target
            # avoids accidentally using a different child's course access.
            if student_user_id in self.linked_student_user_ids:
                return student_user_id
            return None
        return None


class AccessOutcome(StrEnum):
    ALLOWED = "allowed"
    AUTHENTICATION_REQUIRED = "authentication_required"
    FORBIDDEN = "forbidden"


def build_authorization_principal(
    *,
    account_public_id: str,
    session_public_id: str,
    session_version: int,
    credential_version: int,
    audience: AuthAudience,
    linked_user_id: int | None,
    linked_user_type: int | USER_TYPE | None,
    family_child_user_ids: Iterable[int] = (),
    enrollment_grants: Iterable[CourseEnrollmentGrant] = (),
    staff_scope_grants: Iterable[StaffScopeGrant] = (),
) -> AuthorizationPrincipal:
    """Build a principal from already authenticated, currently valid rows.

    Any audience/user-type mismatch is data corruption or a stale account and
    raises ``PrincipalIntegrityError``.  The auth service should reject that
    session rather than inventing a less restricted role.
    """

    _require_public_id(account_public_id, label="account public ID")
    _require_public_id(session_public_id, label="session public ID")
    _require_positive_version(session_version, label="session version")
    _require_positive_version(credential_version, label="credential version")
    try:
        normalized_audience = AuthAudience(audience)
    except (TypeError, ValueError) as error:
        raise PrincipalIntegrityError("Unknown auth audience") from error
    user_type = _strict_user_type(linked_user_type)
    child_ids = frozenset(_checked_user_ids(family_child_user_ids))
    enrollments = _normalize_enrollments(enrollment_grants)
    staff_scopes = _normalize_staff_scopes(staff_scope_grants)

    if normalized_audience is AuthAudience.STUDENT:
        if linked_user_id is None or user_type is not USER_TYPE.STUDENT:
            raise PrincipalIntegrityError(
                "Student audience requires an exact legacy student identity"
            )
        _require_user_id(linked_user_id)
        if child_ids or staff_scopes:
            raise PrincipalIntegrityError("Student principal has foreign grants")
        if any(grant.student_user_id != linked_user_id for grant in enrollments):
            raise PrincipalIntegrityError("Student enrollment belongs to another user")
        role = PrincipalRole.STUDENT
        capabilities = _STUDENT_CAPABILITIES
    elif normalized_audience is AuthAudience.FAMILY:
        if linked_user_id is not None or user_type is not None:
            raise PrincipalIntegrityError(
                "Family audience must not reuse a legacy user identity"
            )
        if staff_scopes:
            raise PrincipalIntegrityError("Family principal has staff grants")
        if any(grant.student_user_id not in child_ids for grant in enrollments):
            raise PrincipalIntegrityError(
                "Family enrollment belongs to an unlinked child"
            )
        role = PrincipalRole.FAMILY
        capabilities = _FAMILY_CAPABILITIES
    else:
        if linked_user_id is None or user_type not in {
            USER_TYPE.TEACHER,
            USER_TYPE.ADMIN,
        }:
            raise PrincipalIntegrityError(
                "Staff audience requires an exact legacy teacher or admin identity"
            )
        _require_user_id(linked_user_id)
        if child_ids or enrollments:
            raise PrincipalIntegrityError("Staff principal has student grants")
        if user_type is USER_TYPE.ADMIN:
            role = PrincipalRole.ADMIN
            capabilities = _ADMIN_CAPABILITIES
        else:
            role = PrincipalRole.TEACHER
            capabilities = _TEACHER_CAPABILITIES

    return AuthorizationPrincipal(
        account_public_id=account_public_id,
        session_public_id=session_public_id,
        session_version=session_version,
        credential_version=credential_version,
        audience=normalized_audience,
        role=role,
        linked_user_id=linked_user_id,
        capabilities=capabilities,
        linked_student_user_ids=child_ids,
        enrollment_grants=enrollments,
        staff_scope_grants=staff_scopes,
    )


def evaluate_access(
    principal: AuthorizationPrincipal | None,
    *,
    expected_audience: AuthAudience,
    capability: Capability | None = None,
    student_user_id: int | None = None,
    course_public_id: str | None = None,
    group_public_id: str | None = None,
    require_course_wide: bool = False,
) -> AccessOutcome:
    """Evaluate authentication, capability and object scope in one place."""

    if group_public_id is not None and course_public_id is None:
        raise ValueError("A group authorization check requires its course")
    if require_course_wide and course_public_id is None:
        raise ValueError("A course-wide authorization check requires a course")
    if principal is None:
        return AccessOutcome.AUTHENTICATION_REQUIRED
    if principal.audience is not expected_audience:
        return AccessOutcome.FORBIDDEN
    if capability is not None and not principal.has_capability(capability):
        return AccessOutcome.FORBIDDEN
    if (
        principal.role is PrincipalRole.TEACHER
        and capability in _TEACHER_SCOPED_CAPABILITIES
        and course_public_id is None
    ):
        # Collection services must use an explicit scope-filtered repository
        # query. A bare capability check cannot prove that returned objects are
        # limited to the teacher's course/group grants.
        return AccessOutcome.FORBIDDEN
    if student_user_id is not None and not principal.can_access_student(
        student_user_id,
        course_public_id=course_public_id,
        group_public_id=group_public_id,
    ):
        return AccessOutcome.FORBIDDEN
    if student_user_id is None and group_public_id is not None:
        if not principal.can_access_group(
            course_public_id=course_public_id,
            group_public_id=group_public_id,
        ):
            return AccessOutcome.FORBIDDEN
    elif student_user_id is None and course_public_id is not None:
        if not principal.can_access_course(
            course_public_id,
            require_course_wide=require_course_wide,
        ):
            return AccessOutcome.FORBIDDEN
    elif student_user_id is not None and require_course_wide:
        # A teacher's student-scoped check may otherwise accept a concrete
        # group; explicitly requiring the full course must remain stricter.
        if not principal.has_staff_course_wide_scope(course_public_id):
            return AccessOutcome.FORBIDDEN
    return AccessOutcome.ALLOWED


def require_access(
    principal: AuthorizationPrincipal | None,
    *,
    expected_audience: AuthAudience,
    capability: Capability | None = None,
    student_user_id: int | None = None,
    course_public_id: str | None = None,
    group_public_id: str | None = None,
    require_course_wide: bool = False,
) -> AuthorizationPrincipal:
    """Return the principal or raise errors directly mappable to 401/403."""

    outcome = evaluate_access(
        principal,
        expected_audience=expected_audience,
        capability=capability,
        student_user_id=student_user_id,
        course_public_id=course_public_id,
        group_public_id=group_public_id,
        require_course_wide=require_course_wide,
    )
    if outcome is AccessOutcome.AUTHENTICATION_REQUIRED:
        raise AuthenticationRequiredError("Authentication is required")
    if outcome is AccessOutcome.FORBIDDEN:
        raise AccessForbiddenError("Access is forbidden")
    assert principal is not None
    return principal


def _normalize_enrollments(
    grants: Iterable[CourseEnrollmentGrant],
) -> tuple[CourseEnrollmentGrant, ...]:
    active = [grant for grant in grants if grant.status is EnrollmentStatus.ACTIVE]
    keys: set[tuple[int, str]] = set()
    for grant in active:
        key = (grant.student_user_id, grant.course_public_id)
        if key in keys:
            raise PrincipalIntegrityError(
                "Principal has multiple active enrollments for one student/course"
            )
        keys.add(key)
    return tuple(
        sorted(
            active,
            key=lambda grant: (grant.student_user_id, grant.course_public_id),
        )
    )


def _normalize_staff_scopes(
    grants: Iterable[StaffScopeGrant],
) -> tuple[StaffScopeGrant, ...]:
    unique: dict[tuple[str, str | None], StaffScopeGrant] = {}
    for grant in grants:
        key = (grant.course_public_id, grant.group_public_id)
        previous = unique.get(key)
        if previous is not None and previous.role is not grant.role:
            raise PrincipalIntegrityError("Conflicting staff roles for one scope")
        unique[key] = grant
    return tuple(
        sorted(
            unique.values(),
            key=lambda grant: (
                grant.course_public_id,
                grant.group_public_id is not None,
                grant.group_public_id or "",
            ),
        )
    )


def _strict_user_type(value: int | USER_TYPE | None) -> USER_TYPE | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise PrincipalIntegrityError("Legacy user type must be an integer")
    if int(value) == int(USER_TYPE.STUDENT):
        return USER_TYPE.STUDENT
    if int(value) == int(USER_TYPE.TEACHER):
        return USER_TYPE.TEACHER
    if int(value) == int(USER_TYPE.ADMIN):
        return USER_TYPE.ADMIN
    raise PrincipalIntegrityError("Unknown or inactive legacy user type")


def _checked_user_ids(values: Iterable[int]) -> tuple[int, ...]:
    checked: list[int] = []
    for value in values:
        _require_user_id(value)
        checked.append(value)
    return tuple(checked)


def _require_user_id(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PrincipalIntegrityError("Legacy user ID must be a positive integer")


def _record_public_id(record: object, *, attribute: str) -> str:
    try:
        value = getattr(record, attribute)
    except AttributeError as error:
        raise PrincipalIntegrityError("Invalid course enrollment record") from error
    if not isinstance(value, str):
        raise PrincipalIntegrityError("Invalid course enrollment record")
    return value


def _require_positive_version(value: int, *, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PrincipalIntegrityError(
            f"{label.capitalize()} must be a positive integer"
        )


def _require_public_id(value: str, *, label: str) -> None:
    if not isinstance(value, str) or _PUBLIC_ID.fullmatch(value) is None:
        raise PrincipalIntegrityError(f"Invalid {label}")


__all__ = [
    "AccessForbiddenError",
    "AccessOutcome",
    "AuthenticationRequiredError",
    "AuthorizationPrincipal",
    "Capability",
    "CourseEnrollmentGrant",
    "EnrollmentStatus",
    "PrincipalIntegrityError",
    "PrincipalRole",
    "StaffScopeGrant",
    "StaffScopeRole",
    "build_authorization_principal",
    "enrollment_grant_from_record",
    "evaluate_access",
    "require_access",
    "staff_scope_grant_from_record",
]
