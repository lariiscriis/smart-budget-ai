from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine


def main() -> None:
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text(
                    "SELECT DATABASE() AS database_name, "
                    "CURRENT_USER() AS database_user"
                )
            )
            row = result.mappings().one()

            print("Conexão com MySQL funcionando!")
            print(f"Banco: {row['database_name']}")
            print(f"Usuário: {row['database_user']}")

    except SQLAlchemyError:
        print(
            "Falha na conexão. Confira o serviço MySQL, "
            "a porta e as credenciais em backend/.env."
        )
        raise SystemExit(1) from None

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()