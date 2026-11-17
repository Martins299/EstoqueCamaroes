"""Isola automaticamente consultas ORM pelos dados do estabelecimento autenticado."""

from flask import has_request_context
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria


_installed = False


def install_tenant_isolation():
    global _installed
    if _installed:
        return
    _installed = True

    @event.listens_for(Session, "do_orm_execute")
    def filter_tenant_rows(execute_state):
        if not execute_state.is_select or execute_state.is_column_load or not has_request_context():
            return
        from .models import User
        if any(description.get("entity") is User for description in execute_state.statement.column_descriptions):
            return
        if not current_user.is_authenticated:
            return
        tenant_id = current_user.establishment_id
        from .models import Chamber, Classification, Lot, Movement, Presentation

        statement = execute_state.statement
        for model in (Chamber, Classification, Lot, Movement, Presentation):
            statement = statement.options(
                with_loader_criteria(
                    model,
                    model.establishment_id == tenant_id,
                    include_aliases=True,
                )
            )
        execute_state.statement = statement

    @event.listens_for(Session, "before_flush")
    def assign_tenant_id(session, _flush_context, _instances):
        if not has_request_context() or not current_user.is_authenticated:
            return
        tenant_id = current_user.establishment_id
        from .models import Chamber, Classification, Lot, Movement, Presentation

        for item in session.new:
            if isinstance(item, (Chamber, Classification, Lot, Movement, Presentation)) and item.establishment_id is None:
                item.establishment_id = tenant_id
