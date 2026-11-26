from alembic import context
from app.models import Base
from app.config import settings


def run():
    if context.is_offline_mode():
        context.configure(
            url=settings().database_url,
            target_metadata=Base.metadata,
            literal_binds=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        from app.db import engine

        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()


run()
