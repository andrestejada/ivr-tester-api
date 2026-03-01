"""add_user_sync_trigger

Revision ID: abc123def456
Revises: 84a0eef84745
Create Date: 2026-03-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abc123def456'
down_revision: Union[str, Sequence[str], None] = '84a0eef84745'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Create user sync trigger function and trigger."""
    
    # Create function to handle new user registration from Supabase Auth
    op.execute("""
    create or replace function public.handle_new_user()
    returns trigger
    language plpgsql
    security definer set search_path = public
    as $$
    begin
      insert into public.profiles (id, email, full_name)
      values (
        new.id,
        new.email,
        new.raw_user_meta_data ->> 'full_name'
      )
      on conflict (id) do nothing;
      return new;
    end;
    $$;
    """)
    
    # Create trigger to execute the function
    op.execute("""
    drop trigger if exists on_auth_user_created on auth.users;
    create trigger on_auth_user_created
      after insert on auth.users
      for each row execute function public.handle_new_user();
    """)


def downgrade() -> None:
    """Downgrade schema - Remove user sync trigger and function."""
    
    # Drop trigger if exists
    op.execute("""
    drop trigger if exists on_auth_user_created on auth.users;
    """)
    
    # Drop function if exists
    op.execute("""
    drop function if exists public.handle_new_user() cascade;
    """)
