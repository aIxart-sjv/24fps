"""
Business logic for case management.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Case, CaseStatus
from app.schemas.case import CaseCreateRequest, CaseUpdateRequest


class CaseManager:
    """Service layer for forensic case operations."""

    @staticmethod
    def create_case(db: Session, request: CaseCreateRequest) -> Case:
        """Create a new forensic case.

        Args:
            db: Database session.
            request: Case creation request.

        Returns:
            The created Case ORM object.

        Raises:
            ValueError: If case_id is not unique.
        """
        existing = db.query(Case).filter(Case.case_id == request.case_id).first()
        if existing:
            raise ValueError(f"Case with case_id {request.case_id!r} already exists")

        case = Case(
            case_id=request.case_id,
            case_number=request.case_number,
            name=request.name,
            description=request.description,
            examiner=request.examiner,
            reference_time=request.reference_time,
            status=CaseStatus.DRAFT,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def get_case(db: Session, case_id: int) -> Case | None:
        """Retrieve a case by ID.

        Args:
            db: Database session.
            case_id: Case primary key.

        Returns:
            The Case object or None if not found.
        """
        return db.query(Case).filter(Case.id == case_id).first()

    @staticmethod
    def get_case_by_case_id(db: Session, case_id: str) -> Case | None:
        """Retrieve a case by case_id identifier.

        Args:
            db: Database session.
            case_id: Case identifier string.

        Returns:
            The Case object or None if not found.
        """
        return db.query(Case).filter(Case.case_id == case_id).first()

    @staticmethod
    def list_cases(db: Session, skip: int = 0, limit: int = 100) -> list[Case]:
        """List all cases with pagination.

        Args:
            db: Database session.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            List of Case objects.
        """
        return db.query(Case).offset(skip).limit(limit).all()

    @staticmethod
    def update_case(db: Session, case_id: int, request: CaseUpdateRequest) -> Case | None:
        """Update an existing case.

        Args:
            db: Database session.
            case_id: Case primary key.
            request: Case update request.

        Returns:
            The updated Case object or None if not found.
        """
        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            return None

        if request.name is not None:
            case.name = request.name
        if request.description is not None:
            case.description = request.description
        if request.examiner is not None:
            case.examiner = request.examiner
        if request.status is not None:
            case.status = request.status
        if request.reference_time is not None:
            case.reference_time = request.reference_time

        db.commit()
        db.refresh(case)
        return case
