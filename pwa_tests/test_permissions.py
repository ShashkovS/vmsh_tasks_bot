"""Phase-1 capability and object-scope authorization matrix."""

from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace

import pytest

from helpers.consts import USER_TYPE
from helpers.pwa.permissions import (
    AccessForbiddenError,
    AccessOutcome,
    AuthenticationRequiredError,
    Capability,
    CourseEnrollmentGrant,
    EnrollmentStatus,
    PrincipalIntegrityError,
    PrincipalRole,
    StaffScopeGrant,
    StaffScopeRole,
    build_authorization_principal,
    enrollment_grant_from_record,
    evaluate_access,
    require_access,
    staff_scope_grant_from_record,
)
from models.pwa.auth import AuthAudience


def _enrollment(
    student_user_id: int,
    course: str = "course-math",
    active_group: str = "group-beginner",
    allowed_groups: frozenset[str] = frozenset({"group-beginner", "group-continuing"}),
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> CourseEnrollmentGrant:
    return CourseEnrollmentGrant(
        student_user_id=student_user_id,
        course_public_id=course,
        active_group_public_id=active_group,
        allowed_group_public_ids=allowed_groups,
        status=status,
    )


def _student(*, student_user_id: int = 101, enrollments=None):
    return build_authorization_principal(
        account_public_id="account-student",
        session_public_id="session-student",
        session_version=2,
        credential_version=3,
        audience=AuthAudience.STUDENT,
        linked_user_id=student_user_id,
        linked_user_type=USER_TYPE.STUDENT,
        enrollment_grants=(
            (_enrollment(student_user_id),) if enrollments is None else enrollments
        ),
    )


def _family(*, children=(101, 102), enrollments=None):
    return build_authorization_principal(
        account_public_id="account-family",
        session_public_id="session-family",
        session_version=1,
        credential_version=1,
        audience=AuthAudience.FAMILY,
        linked_user_id=None,
        linked_user_type=None,
        family_child_user_ids=children,
        enrollment_grants=(
            (
                _enrollment(101),
                _enrollment(
                    102,
                    course="course-physics",
                    active_group="group-physics-a",
                    allowed_groups=frozenset({"group-physics-a"}),
                ),
            )
            if enrollments is None
            else enrollments
        ),
    )


def _teacher(*, scopes=None, user_type=USER_TYPE.TEACHER):
    return build_authorization_principal(
        account_public_id="account-staff",
        session_public_id="session-staff",
        session_version=4,
        credential_version=2,
        audience=AuthAudience.STAFF,
        linked_user_id=201,
        linked_user_type=user_type,
        staff_scope_grants=(
            (
                StaffScopeGrant(
                    "course-math",
                    None,
                    StaffScopeRole.TEACHER,
                ),
                StaffScopeGrant(
                    "course-physics",
                    "group-physics-a",
                    StaffScopeRole.TEACHER,
                ),
                StaffScopeGrant(
                    "course-cs",
                    "group-cs-a",
                    StaffScopeRole.ADMIN,
                ),
            )
            if scopes is None
            else scopes
        ),
    )


def _admin():
    return _teacher(scopes=(), user_type=USER_TYPE.ADMIN)


@pytest.mark.parametrize(
    ("principal_factory", "role", "audience"),
    [
        (_student, PrincipalRole.STUDENT, AuthAudience.STUDENT),
        (_family, PrincipalRole.FAMILY, AuthAudience.FAMILY),
        (_teacher, PrincipalRole.TEACHER, AuthAudience.STAFF),
        (_admin, PrincipalRole.ADMIN, AuthAudience.STAFF),
    ],
)
def test_builder_assigns_exact_role_and_audience(
    principal_factory,
    role,
    audience,
):
    principal = principal_factory()

    assert principal.role is role
    assert principal.audience is audience
    assert principal.capability_names == tuple(sorted(principal.capability_names))


@pytest.mark.parametrize(
    ("principal_factory", "capability", "expected"),
    [
        (_student, Capability.SUBMISSION_MANAGE, True),
        (_student, Capability.FAMILY_CHILD_READ, False),
        (_student, Capability.REVIEW_WRITE, False),
        (_family, Capability.FAMILY_CHILD_READ, True),
        (_family, Capability.SUBMISSION_MANAGE, False),
        (_family, Capability.REVIEW_READ, False),
        (_teacher, Capability.REVIEW_WRITE, True),
        (_teacher, Capability.CONTENT_MANAGE, False),
        (_teacher, Capability.CLASSROOM_MANAGE, False),
        (_admin, Capability.REVIEW_WRITE, True),
        (_admin, Capability.CONTENT_MANAGE, True),
        (_admin, Capability.AUDIT_READ, True),
    ],
)
def test_capability_matrix(principal_factory, capability, expected):
    assert principal_factory().has_capability(capability) is expected


@pytest.mark.parametrize(
    ("linked_user_id", "linked_user_type"),
    [
        (None, USER_TYPE.STUDENT),
        (101, None),
        (101, USER_TYPE.TEACHER),
        (101, USER_TYPE.DEACTIVATED_STUDENT),
        (101, USER_TYPE.UNKNOWN),
        (101, USER_TYPE.STUDENT | USER_TYPE.TEACHER),
    ],
)
def test_student_audience_fails_closed_for_wrong_or_inactive_user_type(
    linked_user_id,
    linked_user_type,
):
    with pytest.raises(PrincipalIntegrityError):
        build_authorization_principal(
            account_public_id="account-student",
            session_public_id="session-student",
            session_version=1,
            credential_version=1,
            audience=AuthAudience.STUDENT,
            linked_user_id=linked_user_id,
            linked_user_type=linked_user_type,
        )


@pytest.mark.parametrize(
    ("audience", "linked_user_id", "linked_user_type"),
    [
        (AuthAudience.FAMILY, 101, USER_TYPE.STUDENT),
        (AuthAudience.STAFF, None, None),
        (AuthAudience.STAFF, 101, USER_TYPE.STUDENT),
        (AuthAudience.STAFF, 201, USER_TYPE.DELETED),
        (
            AuthAudience.STAFF,
            201,
            USER_TYPE.TEACHER | USER_TYPE.ADMIN,
        ),
    ],
)
def test_other_audiences_fail_closed_for_wrong_user_identity(
    audience,
    linked_user_id,
    linked_user_type,
):
    with pytest.raises(PrincipalIntegrityError):
        build_authorization_principal(
            account_public_id="account-invalid",
            session_public_id="session-invalid",
            session_version=1,
            credential_version=1,
            audience=audience,
            linked_user_id=linked_user_id,
            linked_user_type=linked_user_type,
        )


def test_builder_rejects_grants_from_another_identity_boundary():
    with pytest.raises(PrincipalIntegrityError, match="another user"):
        _student(enrollments=(_enrollment(999),))

    with pytest.raises(PrincipalIntegrityError, match="unlinked child"):
        _family(children=(101,), enrollments=(_enrollment(102),))

    with pytest.raises(PrincipalIntegrityError, match="foreign grants"):
        build_authorization_principal(
            account_public_id="account-student",
            session_public_id="session-student",
            session_version=1,
            credential_version=1,
            audience=AuthAudience.STUDENT,
            linked_user_id=101,
            linked_user_type=USER_TYPE.STUDENT,
            staff_scope_grants=(
                StaffScopeGrant(
                    "course-math",
                    None,
                    StaffScopeRole.TEACHER,
                ),
            ),
        )


def test_student_is_limited_to_self_active_enrollment_and_allowed_groups():
    principal = _student(
        enrollments=(
            _enrollment(101),
            _enrollment(
                101,
                course="course-archived",
                active_group="group-old",
                allowed_groups=frozenset({"group-old"}),
                status=EnrollmentStatus.ARCHIVED,
            ),
        )
    )

    assert principal.can_access_student(101)
    assert not principal.can_access_student(102)
    assert principal.can_access_course("course-math")
    assert not principal.can_access_course("course-archived")
    assert principal.can_access_group(
        course_public_id="course-math",
        group_public_id="group-beginner",
    )
    assert principal.can_access_group(
        course_public_id="course-math",
        group_public_id="group-continuing",
    )
    assert not principal.can_access_group(
        course_public_id="course-math",
        group_public_id="group-expert",
    )
    assert not principal.can_access_course(
        "course-math",
        student_user_id=102,
    )


def test_family_requires_explicit_linked_child_for_course_and_group_access():
    principal = _family()

    assert principal.can_access_student(101)
    assert principal.can_access_student(102)
    assert not principal.can_access_student(103)
    assert not principal.can_access_course("course-math")
    assert principal.can_access_course("course-math", student_user_id=101)
    assert not principal.can_access_course("course-math", student_user_id=102)
    assert principal.can_access_group(
        course_public_id="course-physics",
        group_public_id="group-physics-a",
        student_user_id=102,
    )
    assert not principal.can_access_group(
        course_public_id="course-physics",
        group_public_id="group-physics-a",
        student_user_id=101,
    )


def test_teacher_course_wide_and_group_scopes_do_not_leak():
    principal = _teacher()

    assert principal.has_staff_course_access("course-math")
    assert principal.has_staff_course_wide_scope("course-math")
    assert principal.has_staff_group_access(
        course_public_id="course-math",
        group_public_id="group-any",
    )
    assert principal.has_staff_course_access("course-physics")
    assert not principal.has_staff_course_wide_scope("course-physics")
    assert principal.has_staff_group_access(
        course_public_id="course-physics",
        group_public_id="group-physics-a",
    )
    assert not principal.has_staff_group_access(
        course_public_id="course-physics",
        group_public_id="group-physics-b",
    )
    assert not principal.has_staff_course_access("course-unknown")

    # A student ID plus a permitted group is not proof of membership. Staff
    # checks authorize scope taken from a resource loaded by the service.
    assert not principal.can_access_student(101, course_public_id="course-math")
    assert not principal.can_access_student(
        101,
        course_public_id="course-physics",
        group_public_id="group-physics-a",
    )
    assert (
        evaluate_access(
            principal,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.STUDENT_READ,
            course_public_id="course-physics",
            group_public_id="group-physics-a",
        )
        is AccessOutcome.ALLOWED
    )


def test_admin_scope_row_does_not_promote_a_legacy_teacher():
    principal = _teacher(
        scopes=(
            StaffScopeGrant(
                "course-cs",
                None,
                StaffScopeRole.ADMIN,
            ),
        )
    )

    assert principal.role is PrincipalRole.TEACHER
    assert not principal.is_global_admin
    assert not principal.has_capability(Capability.CONTENT_MANAGE)
    assert not principal.has_capability(Capability.CLASSROOM_MANAGE)
    assert principal.has_staff_course_wide_scope("course-cs")
    assert not principal.has_staff_course_access("course-math")


@pytest.mark.parametrize(
    "admin_capability",
    [
        Capability.COURSE_MANAGE,
        Capability.GROUP_MANAGE,
        Capability.CONTENT_MANAGE,
        Capability.CHECKER_MANAGE,
        Capability.BROADCAST_MANAGE,
        Capability.CLASSROOM_MANAGE,
        Capability.AUDIT_READ,
        Capability.STAFF_MANAGE,
        Capability.TELEGRAM_BINDING_MANAGE,
    ],
)
def test_every_admin_capability_depends_on_legacy_admin_type(admin_capability):
    teacher_with_admin_scope = _teacher(
        scopes=(
            StaffScopeGrant(
                "course-math",
                None,
                StaffScopeRole.ADMIN,
            ),
        )
    )

    assert not teacher_with_admin_scope.has_capability(admin_capability)
    assert _admin().has_capability(admin_capability)


@pytest.mark.parametrize(
    ("course", "group"),
    [
        ("course-math", "group-beginner"),
        ("course-physics", "group-physics-a"),
        ("course-unknown", "group-unknown"),
    ],
)
def test_legacy_admin_is_global_without_stored_scopes(course, group):
    principal = _admin()

    assert principal.is_global_admin
    assert principal.has_staff_course_wide_scope(course)
    assert principal.has_staff_group_access(
        course_public_id=course,
        group_public_id=group,
    )
    assert principal.can_access_student(
        999,
        course_public_id=course,
        group_public_id=group,
    )


@pytest.mark.parametrize(
    "principal_factory",
    [_student, _family, _teacher, _admin],
)
@pytest.mark.parametrize("expected_audience", list(AuthAudience))
def test_audience_matrix_is_exact(principal_factory, expected_audience):
    principal = principal_factory()
    expected = (
        AccessOutcome.ALLOWED
        if principal.audience is expected_audience
        else AccessOutcome.FORBIDDEN
    )

    assert evaluate_access(principal, expected_audience=expected_audience) is expected


def test_anonymous_and_authenticated_forbidden_are_distinguishable():
    assert (
        evaluate_access(None, expected_audience=AuthAudience.STUDENT)
        is AccessOutcome.AUTHENTICATION_REQUIRED
    )
    assert (
        evaluate_access(
            _student(),
            expected_audience=AuthAudience.STUDENT,
            capability=Capability.AUDIT_READ,
        )
        is AccessOutcome.FORBIDDEN
    )

    with pytest.raises(AuthenticationRequiredError) as unauthenticated:
        require_access(None, expected_audience=AuthAudience.STUDENT)
    with pytest.raises(AccessForbiddenError) as forbidden:
        require_access(
            _student(),
            expected_audience=AuthAudience.STUDENT,
            capability=Capability.AUDIT_READ,
        )

    assert unauthenticated.value.code == "authentication_required"
    assert forbidden.value.code == "forbidden"


def test_evaluate_access_combines_capability_and_object_scope():
    teacher = _teacher()

    assert (
        evaluate_access(
            teacher,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.REVIEW_WRITE,
            course_public_id="course-physics",
            group_public_id="group-physics-a",
        )
        is AccessOutcome.ALLOWED
    )
    assert (
        evaluate_access(
            teacher,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.REVIEW_WRITE,
            course_public_id="course-physics",
            group_public_id="group-physics-b",
        )
        is AccessOutcome.FORBIDDEN
    )
    assert (
        evaluate_access(
            teacher,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.CONTENT_MANAGE,
            course_public_id="course-math",
            require_course_wide=True,
        )
        is AccessOutcome.FORBIDDEN
    )

    assert (
        evaluate_access(
            teacher,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.REVIEW_WRITE,
            student_user_id=101,
            course_public_id="course-physics",
            group_public_id="group-physics-a",
        )
        is AccessOutcome.FORBIDDEN
    )


def test_teacher_scoped_capability_without_object_scope_fails_closed():
    assert (
        evaluate_access(
            _teacher(),
            expected_audience=AuthAudience.STAFF,
            capability=Capability.REVIEW_WRITE,
        )
        is AccessOutcome.FORBIDDEN
    )


def test_course_wide_requirement_rejects_group_only_teacher_scope():
    principal = _teacher(
        scopes=(
            StaffScopeGrant(
                "course-physics",
                "group-physics-a",
                StaffScopeRole.TEACHER,
            ),
        )
    )

    assert (
        evaluate_access(
            principal,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.STATISTICS_READ,
            course_public_id="course-physics",
        )
        is AccessOutcome.ALLOWED
    )
    assert (
        evaluate_access(
            principal,
            expected_audience=AuthAudience.STAFF,
            capability=Capability.STATISTICS_READ,
            course_public_id="course-physics",
            require_course_wide=True,
        )
        is AccessOutcome.FORBIDDEN
    )


def test_principal_and_nested_scope_state_are_immutable():
    principal = _student()

    with pytest.raises(FrozenInstanceError):
        principal.role = PrincipalRole.ADMIN
    with pytest.raises(AttributeError):
        principal.capabilities.add(Capability.AUDIT_READ)
    with pytest.raises(AttributeError):
        principal.enrollment_grants[0].allowed_group_public_ids.add("group-expert")


def test_direct_principal_replacement_cannot_forge_role_or_capabilities():
    principal = _student()

    with pytest.raises(PrincipalIntegrityError, match="inconsistent"):
        replace(principal, role=PrincipalRole.ADMIN)
    with pytest.raises(PrincipalIntegrityError, match="inconsistent"):
        replace(
            principal,
            capabilities=principal.capabilities | {Capability.AUDIT_READ},
        )


def test_grants_are_sorted_deterministically_and_inactive_rows_are_removed():
    principal = build_authorization_principal(
        account_public_id="account-family",
        session_public_id="session-family",
        session_version=1,
        credential_version=1,
        audience=AuthAudience.FAMILY,
        linked_user_id=None,
        linked_user_type=None,
        family_child_user_ids=(102, 101, 102),
        enrollment_grants=(
            _enrollment(
                102,
                course="course-z",
                active_group="group-z",
                allowed_groups=frozenset({"group-z"}),
            ),
            _enrollment(101, course="course-a"),
            _enrollment(
                101,
                course="course-old",
                active_group="group-old",
                allowed_groups=frozenset({"group-old"}),
                status=EnrollmentStatus.PAUSED,
            ),
        ),
    )

    assert principal.linked_student_user_ids == frozenset({101, 102})
    assert [
        (grant.student_user_id, grant.course_public_id)
        for grant in principal.enrollment_grants
    ] == [(101, "course-a"), (102, "course-z")]


def test_duplicate_active_enrollment_and_conflicting_scope_fail_closed():
    with pytest.raises(PrincipalIntegrityError, match="multiple active"):
        _student(enrollments=(_enrollment(101), _enrollment(101)))

    with pytest.raises(PrincipalIntegrityError, match="Conflicting staff roles"):
        _teacher(
            scopes=(
                StaffScopeGrant(
                    "course-math",
                    None,
                    StaffScopeRole.TEACHER,
                ),
                StaffScopeGrant(
                    "course-math",
                    None,
                    StaffScopeRole.ADMIN,
                ),
            )
        )


def test_repository_record_adapters_use_public_ids_only():
    enrollment = enrollment_grant_from_record(
        student_user_id=101,
        record=SimpleNamespace(
            course_public_id="course-math",
            active_group_public_id="group-beginner",
            enrollment_status="active",
            allowed_groups=(
                SimpleNamespace(group_public_id="group-beginner"),
                SimpleNamespace(group_public_id="group-continuing"),
            ),
        ),
    )
    scope = staff_scope_grant_from_record(
        SimpleNamespace(
            course_public_id="course-math",
            group_public_id="group-beginner",
            role="teacher",
        )
    )

    assert enrollment.allowed_group_public_ids == frozenset(
        {"group-beginner", "group-continuing"}
    )
    assert scope == StaffScopeGrant(
        "course-math",
        "group-beginner",
        StaffScopeRole.TEACHER,
    )


@pytest.mark.parametrize("value", [None, 123])
def test_repository_enrollment_adapter_rejects_non_string_group_public_ids(value):
    with pytest.raises(PrincipalIntegrityError, match="enrollment record"):
        enrollment_grant_from_record(
            student_user_id=101,
            record=SimpleNamespace(
                course_public_id="course-math",
                active_group_public_id="group-beginner",
                enrollment_status="active",
                allowed_groups=(SimpleNamespace(group_public_id=value),),
            ),
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"account_public_id": "INVALID ID"},
        {"session_public_id": ""},
        {"session_version": 0},
        {"session_version": True},
        {"credential_version": -1},
        {"credential_version": "1"},
        {"audience": "unknown"},
        {"linked_user_id": 0},
        {"linked_user_id": -1},
    ],
)
def test_principal_identifiers_and_versions_fail_closed(kwargs):
    values = {
        "account_public_id": "account-student",
        "session_public_id": "session-student",
        "session_version": 1,
        "credential_version": 1,
        "audience": AuthAudience.STUDENT,
        "linked_user_id": 101,
        "linked_user_type": USER_TYPE.STUDENT,
    }
    values.update(kwargs)

    with pytest.raises(PrincipalIntegrityError):
        build_authorization_principal(**values)


def test_active_enrollment_requires_active_group_in_allowed_set():
    with pytest.raises(PrincipalIntegrityError, match="active group"):
        _enrollment(
            101,
            active_group="group-beginner",
            allowed_groups=frozenset({"group-continuing"}),
        )


def test_group_checks_without_course_are_programmer_errors():
    with pytest.raises(ValueError, match="requires its course"):
        _student().can_access_student(101, group_public_id="group-beginner")

    with pytest.raises(ValueError, match="requires its course"):
        evaluate_access(
            _student(),
            expected_audience=AuthAudience.STUDENT,
            group_public_id="group-beginner",
        )
